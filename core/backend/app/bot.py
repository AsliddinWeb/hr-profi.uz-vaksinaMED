"""Telegram bot (long polling). `python -m app.bot`.

Vazifasi: hisobni ulash (`/start <kod>`), `/stop`, `/status`, `/help`. Bildirishnoma YUBORISH worker'da
(`deliver_telegram`). Token bo'lmasa servis hech narsa qilmay kutadi (konteyner qayta ishga tushmaydi).
"""

import asyncio
import json
import logging
import re
import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.models.recruit import Candidate, SourceLink, Vacancy
from app.realtime import publish
from app.services import employees as emp_svc
from app.services import recruit_sources as rsrc
from app.services import telegram_link as link
from app.services.notifications import notify, serialize
from app.telegram import TelegramClient, TelegramError, esc
from app.timeutil import local_date, now

log = logging.getLogger("vaksina.bot")

LEAVE_TEXTS = {
    "uz": {
        "denied": "Bu buyruq faqat HR va koordinatorlar uchun.", "head": "📊 <b>Javob olish</b> — oxirgi {days} kun va kelgusi {ahead} kun",
        "totals": "Jami filial: <b>{total}</b> · javob olinganlar bor: <b>{with_leave}</b> filial · <b>{requests}</b> ta so'rov", "empty": "Bu davrda so'rovlar yo'q.",
        "today": "bugun", "ago": "{n} kun oldin", "ahead": "{n} kundan keyin", "ongoing": "hozir davom etmoqda", "cont": "(davomi)",
        "st": {"approved": "✅", "pending_coordinator": "⏳", "pending_hr": "⏳"}, "hourly": "soatlik",
        "no_statements": "Tasdiqlangan javob bildirgilari yo'q.", "not_linked": "Bu Telegram hisobga ulanmagan.", "no_employee": "Sizga xodim kartochkasi biriktirilmagan.",
        "doc": "Javob olish bildirgisi {no}",
    },
    "ru": {
        "denied": "Эта команда только для HR и координаторов.", "head": "📊 <b>Отсутствия</b> — последние {days} дн. и ближайшие {ahead} дн.",
        "totals": "Всего филиалов: <b>{total}</b> · с отсутствиями: <b>{with_leave}</b> · заявок: <b>{requests}</b>", "empty": "За этот период заявок нет.",
        "today": "сегодня", "ago": "{n} дн. назад", "ahead": "через {n} дн.", "ongoing": "сейчас отсутствует", "cont": "(продолжение)",
        "st": {"approved": "✅", "pending_coordinator": "⏳", "pending_hr": "⏳"}, "hourly": "почасовая",
        "no_statements": "Одобренных уведомлений нет.", "not_linked": "Этот Telegram не подключён.", "no_employee": "За вами не закреплена карточка сотрудника.",
        "doc": "Уведомление об отсутствии {no}",
    },
}
LIMIT = 3800


def overview_messages(data: dict, lang: str, days: int, ahead: int) -> list[str]:
    """Filial bo'yicha ro'yxat: Telegram xabar chegarasidan oshmasligi uchun bir necha xabarga bo'linadi."""
    c = LEAVE_TEXTS.get(lang, LEAVE_TEXTS["uz"])
    head = f"{c['head'].format(days=days, ahead=ahead)}\n{c['totals'].format(total=data['total_branches'], with_leave=data['with_leave'], requests=data['requests'])}"
    if not data["branches"]:
        return [f"{head}\n\n{c['empty']}"]
    blocks = []
    for b in data["branches"]:
        lines = [f"📍 <b>{esc(b['name'])}</b> ({len(b['items'])})"]
        for it in b["items"]:
            n = it["days_ago"]
            when = c["ongoing"] if it["ongoing"] else (c["today"] if n == 0 else (c["ago"].format(n=n) if n > 0 else c["ahead"].format(n=-n)))
            span = it["start_date"].strftime("%d.%m") + (f"–{it['end_date']:%d.%m}" if it["end_date"] != it["start_date"] else "")
            if it["kind"] == "hourly" and it["start_time"]:
                span += f" {it['start_time']}–{it['end_time']}"
            lines.append(f"{c['st'].get(it['status'], '•')} {esc(it['employee'])} — {when} ({span})")
        blocks.append("\n".join(lines))
    out, cur = [], head
    for blk in blocks:
        if len(cur) + len(blk) + 2 > LIMIT and cur != head:
            out.append(cur)
            cur = f"{c['cont']}"
        cur += "\n\n" + blk
    out.append(cur)
    return out


async def _send_statements(user, session, client, chat_id: int) -> None:
    """/bildirgi: xodimning oxirgi tasdiqlangan javob bildirgilarini PDF sifatida yuboradi."""
    from app.extensions import load_client_config
    from app.models.answers import LeaveRequest
    from app.models.employees import Employee
    from app.services import leave_statement as stmt

    c = LEAVE_TEXTS.get(user.locale, LEAVE_TEXTS["uz"])
    emp = await session.scalar(select(Employee).where(Employee.user_id == user.id))
    if not emp:
        await client.send_message(chat_id, c["no_employee"])
        return
    reqs = list((await session.scalars(select(LeaveRequest).where(LeaveRequest.employee_id == emp.id, LeaveRequest.status == "approved").order_by(LeaveRequest.start_date.desc()).limit(3))).all())
    if not reqs:
        await client.send_message(chat_id, c["no_statements"])
        return
    settings = get_settings()
    company = load_client_config(settings.client_dir).brand.get("name") or "HR-Profi"
    for r in reqs:
        if await stmt.ensure(session, r, emp, now()):
            await session.commit()
        url = f"{settings.public_url.rstrip('/')}/verify/leave/{r.statement_code}" if settings.public_url else str(r.statement_code)
        pdf = await stmt.build_pdf(session, r, emp, url, company, user.locale)
        await client.send_document(chat_id, f"{r.statement_no}.pdf", pdf, c["doc"].format(no=r.statement_no))

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")

TEXTS = {
    "uz": {
        "help": "Bu bot HR-Profi bildirishnomalarini yuboradi.\n\nUlash: tizimda Profil → Telegram bo'limidan havolani oching.\n/status — holat\n/stop — bildirishnomalarni o'chirish\n/javob — javob olish hisoboti (HR, koordinator)\n/bildirgi — o'z bildirgilarim",
        "linked": "✅ Hisob ulandi: <b>{name}</b>. Endi bildirishnomalar shu yerga keladi.",
        "bad_code": "❌ Kod noto'g'ri yoki muddati o'tgan. Tizimda yangi havola oling.",
        "not_linked": "Bu Telegram hisobga ulanmagan. Tizimda Profil → Telegram orqali ulang.",
        "status_on": "Ulangan: <b>{name}</b>\nBildirishnomalar: yoqilgan",
        "status_off": "Ulangan: <b>{name}</b>\nBildirishnomalar: o'chirilgan (/start bilan qayta yoqing)",
        "stopped": "🔕 Bildirishnomalar o'chirildi. Qayta yoqish: /start",
        "resumed": "🔔 Bildirishnomalar yoqildi.",
        "private_only": "Botni faqat shaxsiy chatda ishlating.",
    },
    "ru": {
        "help": "Этот бот отправляет уведомления HR-Profi.\n\nПодключение: в системе откройте Профиль → Telegram и перейдите по ссылке.\n/status — состояние\n/stop — отключить уведомления\n/javob — отчёт по отсутствиям (HR, координатор)\n/bildirgi — мои уведомления",
        "linked": "✅ Аккаунт подключён: <b>{name}</b>. Теперь уведомления будут приходить сюда.",
        "bad_code": "❌ Код неверный или истёк. Получите новую ссылку в системе.",
        "not_linked": "Этот Telegram не подключён. Подключите через Профиль → Telegram в системе.",
        "status_on": "Подключено: <b>{name}</b>\nУведомления: включены",
        "status_off": "Подключено: <b>{name}</b>\nУведомления: отключены (включите через /start)",
        "stopped": "🔕 Уведомления отключены. Включить снова: /start",
        "resumed": "🔔 Уведомления включены.",
        "private_only": "Используйте бота только в личном чате.",
    },
}


CAND_STATE_TTL = 3600
CANDIDATE_TEXTS = {
    "closed": "Bu vakansiya yopilgan yoki havola yaroqsiz.",
    "ask_name": "«{title}» vakansiyasi.\nF.I.Sh. ingizni yozing:",
    "ask_phone": "Rahmat, {name}! Endi telefon raqamingizni yozing (masalan, +998901234567):",
    "bad_phone": "Telefon raqami noto'g'ri. Qayta yozing (masalan, +998901234567):",
    "short_name": "Iltimos, F.I.Sh. ni to'liq yozing:",
    "done": "✅ Arizangiz qabul qilindi. Rezyumeingizni matn ko'rinishida shu yerga yuborishingiz mumkin. HR siz bilan bog'lanadi.",
    "dup": "Siz bu vakansiyaga allaqachon ariza topshirgansiz. HR siz bilan bog'lanadi.",
    "resume": "✅ Rezyume qabul qilindi.",
}


def _t(lang: str, key: str, **kw: str) -> str:
    return TEXTS.get(lang, TEXTS["uz"])[key].format(**kw)


def _bilingual(key: str) -> str:
    return f"{_t('uz', key)}\n\n{_t('ru', key)}"


async def _candidate_flow(update_text: str, command: str, arg: str, *, chat_id: int, session, redis: Redis, reply) -> bool:
    """Nomzod oqimi: `/start apply_<kod>` -> F.I.Sh. -> telefon -> ariza (manba havola kodidan). True: xabar shu oqimda ishlandi."""
    key = f"cand:{chat_id}"
    c = CANDIDATE_TEXTS
    if command == "/start" and arg.startswith("apply_"):
        code = arg[6:]
        lk = await session.scalar(select(SourceLink).where(SourceLink.code == code[:16])) if CODE_RE.match(code) else None
        v = await session.get(Vacancy, lk.vacancy_id) if lk else None
        if not lk or not v or not lk.is_active or v.status != "open":
            await reply(c["closed"])
            return True
        lk.clicks += 1
        await session.commit()
        await redis.set(key, json.dumps({"code": lk.code, "step": "name"}), ex=CAND_STATE_TTL)
        await reply(c["ask_name"].format(title=esc(v.title)))
        return True
    if command.startswith("/"):
        return False
    raw = await redis.get(key)
    if raw:
        st = json.loads(raw)
        text = update_text.strip()
        if st["step"] == "name":
            if len(text) < 3:
                await reply(c["short_name"])
                return True
            st.update(step="phone", name=text[:250])
            await redis.set(key, json.dumps(st), ex=CAND_STATE_TTL)
            await reply(c["ask_phone"].format(name=esc(st["name"])))
            return True
        try:
            phone = emp_svc.normalize_phone(text)
        except ValueError:
            phone = None
        if not phone:
            await reply(c["bad_phone"])
            return True
        lk = await session.scalar(select(SourceLink).where(SourceLink.code == st["code"]))
        v = await session.get(Vacancy, lk.vacancy_id) if lk else None
        if not lk or not v or not lk.is_active or v.status != "open":
            await redis.delete(key)
            await reply(c["closed"])
            return True
        status, _, notes = await rsrc.submit_application(session, lk, v, full_name=st["name"], phone=phone, note=None, chat_id=chat_id, moment=now())
        await session.commit()
        await redis.delete(key)
        for n in notes:  # bot'da arq navbati yo'q: ilova ichida realtime xabar
            await publish(redis, [n.user_id], "notification", {"notification": serialize(n)})
        await reply(c["dup" if status == "duplicate" else "done"])
        return True
    cand = await session.scalar(select(Candidate).where(Candidate.telegram_chat_id == chat_id))
    if cand and len(update_text.strip()) >= 100:  # nomzod rezyumesini matn ko'rinishida yuboradi
        cand.resume_text = ((cand.resume_text + "\n\n") if cand.resume_text else "") + update_text.strip()[:8000]
        await session.commit()
        await reply(c["resume"])
        return True
    return False


async def handle_update(
    update: dict,
    *,
    client: TelegramClient,
    redis: Redis,
    sessions: async_sessionmaker,
) -> None:
    """Bitta Telegram update'ini qayta ishlaydi (testlanadigan, tarmoqsiz mantiq)."""
    msg = update.get("message")
    if not msg or "text" not in msg:
        return
    chat = msg["chat"]
    chat_id = chat["id"]

    async def reply(text: str) -> None:
        try:
            await client.send_message(chat_id, text)
        except TelegramError:
            log.warning("Telegram javobi yuborilmadi (chat %s)", chat_id)

    if chat.get("type") != "private":
        await reply(_bilingual("private_only"))
        return

    parts = msg["text"].strip().split(maxsplit=1)
    command = parts[0].split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    async with sessions() as session:
        user = await link.user_by_chat(session, chat_id)

        if user is None and await _candidate_flow(msg["text"], command, arg, chat_id=chat_id, session=session, redis=redis, reply=reply):
            return

        if command == "/start" and arg:
            if not CODE_RE.match(arg):
                await reply(_bilingual("bad_code"))
                return
            uid = await link.consume_link_code(redis, arg)
            linked = await link.link_user(session, uid, chat_id, msg.get("from", {}).get("username")) if uid else None
            if not linked:
                await reply(_bilingual("bad_code"))
                return
            notes = await notify(session, [linked.id], "telegram.linked")
            await session.commit()
            await reply(_t(linked.locale, "linked", name=esc(linked.full_name)))
            # Realtime: profil holati va bildirishnoma. Telegramga qayta yuborilmaydi (allaqachon javob berdik)
            await publish(redis, [linked.id], "telegram", {"changed": True})
            await publish(redis, [linked.id], "notification", {"notification": serialize(notes[0])})
            return

        if command == "/start":
            if user and not user.telegram_notify:
                user.telegram_notify = True
                await session.commit()
                await reply(_t(user.locale, "resumed"))
            else:
                await reply(_t(user.locale, "help") if user else _bilingual("help"))
            return

        if command == "/stop":
            if not user:
                await reply(_bilingual("not_linked"))
                return
            user.telegram_notify = False
            await session.commit()
            await reply(_t(user.locale, "stopped"))
            await publish(redis, [user.id], "telegram", {"changed": True})
            return

        if command in ("/javob", "/bildirgi"):
            if not user:
                await reply(_bilingual("not_linked"))
                return
            c = LEAVE_TEXTS.get(user.locale, LEAVE_TEXTS["uz"])
            if command == "/bildirgi":
                try:
                    await _send_statements(user, session, client, chat_id)
                except TelegramError:
                    log.warning("Bildirgi yuborilmadi (chat %s)", chat_id)
                return
            from app.deps import AuthContext
            from app.services import answers as ans
            from app.services import answers_report as rep

            auth = AuthContext(user, uuid.uuid4(), frozenset(user.role.permission_keys))
            if not any(ans.has(auth, p) for p in ("answers.read", "answers.manage", "answers.decide")):
                await reply(c["denied"])
                return
            days = int(arg) if arg.isdigit() and 1 <= int(arg) <= 90 else 30
            data = await rep.bot_overview(session, auth, local_date(now()), days=days, ahead=14)
            for text in overview_messages(data, user.locale, days, 14):
                await reply(text)
            return

        if command == "/status":
            if not user:
                await reply(_bilingual("not_linked"))
                return
            key = "status_on" if user.telegram_notify else "status_off"
            await reply(_t(user.locale, key, name=esc(user.full_name)))
            return

        await reply(_t(user.locale, "help") if user else _bilingual("help"))


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN berilmagan: bot o'chirilgan, kutilmoqda")
        await asyncio.Event().wait()

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    client = TelegramClient(settings.telegram_bot_token)
    try:
        me = await client.get_me()
        await redis.set("telegram:bot_username", me["username"])
        log.info("Bot ishga tushdi: @%s", me["username"])

        offset = int(await redis.get("telegram:offset") or 0) or None
        backoff = 1
        while True:
            try:
                updates = await client.get_updates(offset)
                backoff = 1
            except TelegramError as exc:
                log.warning("getUpdates xatosi: %s (%ss kutiladi)", exc.description, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await handle_update(update, client=client, redis=redis, sessions=SessionLocal)
                except Exception:  # noqa: BLE001
                    log.exception("Update qayta ishlanmadi: %s", update.get("update_id"))
            if updates:
                await redis.set("telegram:offset", offset)
    finally:
        await client.close()
        await redis.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
