import logging
from datetime import UTC, datetime, timedelta

from arq import Retry, cron
from arq.connections import RedisSettings
from sqlalchemy import delete

from app.config import get_settings
from app.db import SessionLocal
from app.extensions import WorkerRegistry, load_worker_extension
from app.models.auth import User
from app.models.notifications import Notification
from app.services.telegram_link import unlink_user
from app.telegram import TelegramClient, TelegramError, esc

log = logging.getLogger("vaksina.worker")
settings = get_settings()


async def ping(ctx: dict) -> str:
    return "pong"


async def heartbeat(ctx: dict) -> None:
    await ctx["redis"].set("worker:heartbeat", datetime.now(UTC).isoformat(), ex=120)


def telegram_text(n: Notification, lang: str) -> str:
    title = n.title_ru if lang == "ru" else n.title_uz
    body = n.body_ru if lang == "ru" else n.body_uz
    parts = [f"<b>{esc(title)}</b>"]
    if body:
        parts.append(esc(body))
    if n.link and settings.public_url:
        parts.append(f"{esc(settings.public_url.rstrip('/'))}{esc(n.link)}")
    return "\n".join(parts)


async def deliver_telegram(ctx: dict, notification_id: int) -> str:
    """Bildirishnomani foydalanuvchining ulangan Telegram chatiga yuboradi."""
    client: TelegramClient | None = ctx.get("telegram")
    if client is None:
        return "disabled"
    async with SessionLocal() as session:
        n = await session.get(Notification, notification_id)
        if n is None:
            return "gone"
        user = await session.get(User, n.user_id)
        if not user or not user.is_active or not user.telegram_chat_id or not user.telegram_notify:
            return "skipped"
        try:
            await client.send_message(user.telegram_chat_id, telegram_text(n, user.locale))
        except TelegramError as exc:
            if exc.chat_unreachable:
                await unlink_user(session, user)
                await session.commit()
                log.info("Telegram chat yetib bo'lmaydi, foydalanuvchi %s uzildi", user.id)
                return "unlinked"
            if exc.retry_after:
                raise Retry(defer=exc.retry_after) from exc
            raise Retry(defer=ctx.get("job_try", 1) * 15) from exc
        return "sent"


async def cleanup_notifications(ctx: dict) -> int:
    """O'qilgan bildirishnomalar 30 kundan, hammasi 180 kundan keyin o'chiriladi."""
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        result = await session.execute(
            delete(Notification).where(
                (Notification.read_at < now - timedelta(days=30))
                | (Notification.created_at < now - timedelta(days=180))
            )
        )
        await session.commit()
        return result.rowcount or 0


async def purge_face_templates(ctx: dict) -> dict:
    """Saqlash muddati o'tgan, bo'shatilgan xodimlarning va rozilik qaytarilgan yuz shablonlarini o'chiradi."""
    from app.services.face import purge_templates

    async with SessionLocal() as session:
        return await purge_templates(session)


class _QueueAdapter:
    """arq `ctx['redis']` ni `deliver()` kutadigan `app.state.queue` ko'rinishiga keltiradi."""

    def __init__(self, redis):
        self.redis = redis

    async def enqueue(self, function, *args, defer_seconds=None):
        await self.redis.enqueue_job(function, *args)


async def escalate_leave_requests(ctx: dict) -> int:
    """Koordinator muddatida (standart 8 soat) javob bermagan ruxsat so'rovlarini HR ga o'tkazadi."""
    from types import SimpleNamespace

    from app.services.answers import escalate_due
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        due, notes = await escalate_due(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return len(due)


async def scan_penalties(ctx: dict) -> dict:
    """Qoidada `auto_scan` yoqilgan bo'lsa, oxirgi 3 tugagan kun uchun jarimalarni hisoblaydi (takrorlanmaydi)."""
    from datetime import timedelta

    from app.services.penalties import current_rules, scan_range
    from app.timeutil import local_date, now

    async with SessionLocal() as session:
        rules = await current_rules(session)
        if not rules.config.get("auto_scan"):
            return {"skipped": True}
        today = local_date(now())
        result = await scan_range(session, today - timedelta(days=3), today - timedelta(days=1), dry_run=False, moment=now())
        await session.commit()
        return result


async def release_penalty_blocks(ctx: dict) -> int:
    """Muddati o'tgan vaqtincha bloklarni olib tashlaydi (hisobni qayta yoqadi)."""
    from app.services.penalties import release_expired_blocks
    from app.timeutil import now

    async with SessionLocal() as session:
        n = await release_expired_blocks(session, now())
        await session.commit()
        return n


async def task_deadlines(ctx: dict) -> dict:
    """Topshiriq muddatlari: 24 soat qolganda va muddat o'tganda ijrochiga (va yaratuvchiga) bir martadan xabar beradi."""
    from types import SimpleNamespace

    from app.services.notifications import deliver
    from app.services.tasks import check_deadlines
    from app.timeutil import now

    async with SessionLocal() as session:
        soon, late, notes = await check_deadlines(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return {"soon": soon, "overdue": late}


async def need_deadlines(ctx: dict) -> dict:
    """Ehtiyoj muddatlari: 24 soat qolganda va o'tganda bir martadan xabar (o'tgani auditga ham yoziladi)."""
    from types import SimpleNamespace

    from app.services.needs import check_deadlines
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        soon, late, notes = await check_deadlines(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return {"soon": soon, "overdue": late}


async def logistics_expiry(ctx: dict) -> int:
    """Mashina hujjatlari va haydovchi guvohnomalari muddati: har bosqich (30/7 kun, o'tgan) uchun bir martadan xabar."""
    from types import SimpleNamespace

    from app.services.logistics import check_expiry
    from app.services.notifications import deliver
    from app.timeutil import local_date, now

    async with SessionLocal() as session:
        count, notes = await check_expiry(session, local_date(now()))
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return count


async def warehouse_watch(ctx: dict) -> int:
    """Ombor nazorati: xodim yetishmovchiligi (grace dan keyin) va juda uzoq ochiq smenalar uchun bir martadan xabar."""
    from types import SimpleNamespace

    from app.services.notifications import deliver
    from app.services.warehouse import watch
    from app.timeutil import now

    async with SessionLocal() as session:
        sent, notes = await watch(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return sent


async def calls_watch(ctx: dict) -> dict:
    """Qo'ng'iroqlar: 45 s javobsizlar -> o'tkazib yuborilgan, bo'sh konferensiyalar va eskirganlarni yopish."""
    from types import SimpleNamespace

    from app.services import calls
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        missed, closed, notes = await calls.watch(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return {"missed": missed, "closed": closed}


async def desk_watch(ctx: dict) -> dict:
    """Resepshin va AyTi: kelmagan mehmonlarni yopish, SLA muddati o'tgan ticketlarni belgilash, tasdiqlanmagan hal qilinganlarni avto yopish."""
    from types import SimpleNamespace

    from app.services import helpdesk, reception
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        no_show = await reception.watch(session, now())
        late, closed, notes = await helpdesk.watch(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return {"no_show": no_show, "sla": late, "closed": closed}


async def mobile_watch(ctx: dict) -> int:
    """Ko'chma kuzatuv: signal uzilishi (10 daq), ruxsat oynasi tugaganda sessiyani avtomatik yopish, eski nuqtalarni tozalash."""
    from types import SimpleNamespace

    from app.services.mobile import watch
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        count, notes = await watch(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return count


async def fire_reminders(ctx: dict) -> int:
    """Vaqti kelgan eslatmalarni (ilova ichida va, tanlangan bo'lsa, Telegramga) yuboradi. Har daqiqada."""
    from types import SimpleNamespace

    from app.services.notifications import deliver
    from app.services.reminders import fire_due
    from app.timeutil import now

    async with SessionLocal() as session:
        count, with_tg, without_tg = await fire_due(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, with_tg)  # type: ignore[arg-type]
    await deliver(app, without_tg, telegram=False)  # type: ignore[arg-type]
    return count


async def coord_report_job(ctx: dict) -> str:
    """Har kuni 20:00 (Toshkent) koordinatorlarga davomat hisoboti va izoh qatorlari; kuniga bir marta (Redis kaliti)."""
    from types import SimpleNamespace

    from app.services import coord_report
    from app.services.notifications import deliver
    from app.timeutil import local_date, now, tz

    moment = now()
    local = moment.astimezone(tz())
    if not (local.hour == 20 and local.minute < 10):
        return "skip"
    if not await ctx["redis"].set(f"coord-report:{local_date(moment)}", "1", ex=86400, nx=True):
        return "done"
    async with SessionLocal() as session:
        notes = await coord_report.run_daily(session, moment)
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"sent {len(notes)}"


async def explanation_deadlines(ctx: dict) -> int:
    """Muddati o'tgan, javobsiz izohlar haqida HR va koordinatorga xabar beradi."""
    from types import SimpleNamespace

    from app.services import coord_report
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        notes = await coord_report.overdue_check(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return len(notes)


async def report_scheduler(ctx: dict) -> dict:
    """Muddati kelgan jadvalli hisobotlarni tuzadi va yuboradi (har daqiqa); soatiga bir marta eski fayllarni tozalaydi."""
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.models.reports import ReportSchedule
    from app.services import reports
    from app.services.notifications import deliver
    from app.timeutil import now

    storage = ctx.get("storage")
    if storage is None:
        return {"ran": 0}
    moment = now()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    ran = purged = 0
    async with SessionLocal() as session:
        due_ids = list((await session.scalars(select(ReportSchedule.id).where(ReportSchedule.is_active.is_(True), ReportSchedule.next_run_at <= moment))).all())
    for sid in due_ids:  # har jadval alohida tranzaksiyada: bittasining xatosi boshqasini to'xtatmaydi
        async with SessionLocal() as session:
            s = await session.get(ReportSchedule, sid)
            if s is None or not s.is_active or (s.next_run_at and s.next_run_at > moment):
                continue
            run, notes, tg = await reports.run_schedule(session, storage, s, moment)
            await session.commit()
        await deliver(app, notes, telegram=False)  # type: ignore[arg-type]
        for uid in tg:
            await ctx["redis"].enqueue_job("deliver_report_telegram", run.id, uid)
        ran += 1
    if moment.minute == 10:
        async with SessionLocal() as session:
            purged = await reports.purge_runs(session, storage, moment)
            await session.commit()
    return {"ran": ran, "purged": purged}


async def deliver_report_telegram(ctx: dict, run_id: int, user_id: int) -> str:
    """Hisobot faylini foydalanuvchining Telegram chatiga hujjat sifatida yuboradi."""
    from app.models.reports import ReportRun
    from app.services import reports

    client: TelegramClient | None = ctx.get("telegram")
    storage = ctx.get("storage")
    if client is None or storage is None:
        return "disabled"
    async with SessionLocal() as session:
        run = await session.get(ReportRun, run_id)
        user = await session.get(User, user_id)
        if not run or not run.file_key or not user or not user.is_active or not user.telegram_chat_id:
            return "skipped"
        title = reports.CATALOG[run.report_type][1 if user.locale == "ru" else 0]
        data = await reports.read_file(storage, run.file_key)
        try:
            await client.send_document(user.telegram_chat_id, run.filename or "hisobot", data, f"{title}\n{run.start_date:%d.%m.%Y} – {run.end_date:%d.%m.%Y}")
        except TelegramError as exc:
            if exc.chat_unreachable:
                await unlink_user(session, user)
                await session.commit()
                return "unlinked"
            if exc.retry_after:
                raise Retry(defer=exc.retry_after) from exc
            raise Retry(defer=ctx.get("job_try", 1) * 15) from exc
        return "sent"


async def deliver_statement_telegram(ctx: dict, request_id: int) -> str:
    """Tasdiqlangan javob bildirgisini (PDF) xodimning Telegram chatiga yuboradi."""
    from app.config import get_settings
    from app.extensions import load_client_config
    from app.models.answers import LeaveRequest
    from app.models.employees import Employee
    from app.services import leave_statement as stmt

    client: TelegramClient | None = ctx.get("telegram")
    if client is None:
        return "disabled"
    async with SessionLocal() as session:
        req = await session.get(LeaveRequest, request_id)
        emp = await session.get(Employee, req.employee_id) if req else None
        user = await session.get(User, emp.user_id) if emp and emp.user_id else None
        if not req or req.status != "approved" or not req.statement_code or not user or not user.is_active or not user.telegram_chat_id or not user.telegram_notify:
            return "skipped"
        settings = get_settings()
        company = load_client_config(settings.client_dir).brand.get("name") or "HR-Profi"
        url = f"{settings.public_url.rstrip('/')}/verify/leave/{req.statement_code}" if settings.public_url else req.statement_code
        pdf = await stmt.build_pdf(session, req, emp, url, company, user.locale)
        caption = ("✅ Javob olish tasdiqlandi. Bildirgi biriktirildi." if user.locale != "ru" else "✅ Отсутствие одобрено. Уведомление во вложении.") + f"\n{req.statement_no}"
        try:
            await client.send_document(user.telegram_chat_id, f"{req.statement_no}.pdf", pdf, caption)
        except TelegramError as exc:
            if exc.chat_unreachable:
                await unlink_user(session, user)
                await session.commit()
                return "unlinked"
            if exc.retry_after:
                raise Retry(defer=exc.retry_after) from exc
            raise Retry(defer=ctx.get("job_try", 1) * 15) from exc
        return "sent"


async def deliver_candidate_telegram(ctx: dict, chat_id: int, text: str) -> str:
    """Nomzodga (botga yozgan) Telegram xabari: suhbatga taklif, job offer."""
    client: TelegramClient | None = ctx.get("telegram")
    if client is None:
        return "disabled"
    try:
        await client.send_message(chat_id, esc(text))
    except TelegramError as exc:
        if exc.chat_unreachable:
            return "unreachable"
        if exc.retry_after:
            raise Retry(defer=exc.retry_after) from exc
        raise Retry(defer=ctx.get("job_try", 1) * 15) from exc
    return "sent"


async def attestation_job(ctx: dict) -> str:
    """Oyning oxirgi kuni 09:00 dan keyin oylik attestatsiyani ochadi (oyiga bir marta, Redis kaliti)."""
    from calendar import monthrange
    from types import SimpleNamespace

    from app.services import growth
    from app.services.notifications import deliver
    from app.timeutil import local_date, now, tz

    moment = now()
    local = moment.astimezone(tz())
    day = local_date(moment)
    if day.day != monthrange(day.year, day.month)[1] or local.hour < 9:
        return "skip"
    month = growth.month_of(day)
    if not await ctx["redis"].set(f"attestation-open:{month}", "1", ex=40 * 86400, nx=True):
        return "done"
    async with SessionLocal() as session:
        created, notes = await growth.open_cycle(session, month, moment)
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"opened {created}"


async def retention_scan_job(ctx: dict) -> str:
    """Dushanba 06:00 dan keyin (haftada bir marta): past yig'ma ballli xodimlar uchun ketish xavfi holatlarini ochadi."""
    from types import SimpleNamespace

    from app.services import retention
    from app.services.notifications import deliver
    from app.timeutil import local_date, now, tz

    moment = now()
    local = moment.astimezone(tz())
    if local.weekday() != 0 or local.hour < 6:
        return "skip"
    if not await ctx["redis"].set(f"retention-scan:{local_date(moment)}", "1", ex=8 * 86400, nx=True):
        return "done"
    async with SessionLocal() as session:
        created, notes = await retention.auto_scan(session, moment)
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"created {created}"


async def rotation_job(ctx: dict) -> str:
    """Rotatsiyalar: boshlanish sanasi kelganini faollashtiradi, muddati o'tganini uy filialiga qaytaradi."""
    from types import SimpleNamespace

    from app.services import rotations
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        notes = await rotations.run_due(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"notified {len(notes)}"


async def duty_overdue_job(ctx: dict) -> str:
    """Ish chek-listlari: muddati o'tib bajarilmaganlar uchun xodimga va filial mas'ullariga (bir marta) xabar yuboradi."""
    from types import SimpleNamespace

    from app.services import duty
    from app.services.notifications import deliver
    from app.timeutil import now

    async with SessionLocal() as session:
        notes = await duty.overdue_scan(session, now())
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"notified {len(notes)}"


async def control_digest_job(ctx: dict) -> str:
    """Har kuni 09:00 dan keyin HRD va HR auditorga kechikkan jarayonlar xulosasi (bo'lsa)."""
    from types import SimpleNamespace

    from app.services import retention
    from app.services.answers import users_with_permission
    from app.services.notifications import deliver, notify
    from app.timeutil import local_date, now, tz

    moment = now()
    local = moment.astimezone(tz())
    if local.hour < 9:
        return "skip"
    if not await ctx["redis"].set(f"control-digest:{local_date(moment)}", "1", ex=2 * 86400, nx=True):
        return "done"
    labels = {
        "interview_overdue": "HR suhbati kechikdi", "decision_overdue": "qaror kechikdi", "no_meeting": "haftalik uchrashuvsiz", "exit_missing": "exit-intervyu yo'q", "tasks_overdue": "vazifa muddati o'tdi",
        "day7_pending": "7-kun qarori yo'q", "vacancies_overdue": "vakansiya muddati o'tdi", "attestation_stale": "attestatsiya kechikdi",
    }
    async with SessionLocal() as session:
        data = await retention.control_overview(session, moment)
        if not data["total"]:
            return "empty"
        text = "; ".join(f"{labels[k]}: {n}" for k, n in data["counts"].items() if n)
        notes = await notify(session, await users_with_permission(session, "control.read"), "control.digest", params={"text": text}, link="/control")
        await session.commit()
    app = SimpleNamespace(state=SimpleNamespace(redis=ctx["redis"], queue=_QueueAdapter(ctx["redis"])))
    await deliver(app, notes)  # type: ignore[arg-type]
    return f"sent {len(notes)}"


async def startup(ctx: dict) -> None:
    from app.storage import MinioStorage

    ctx["storage"] = MinioStorage(settings.minio_endpoint, settings.minio_root_user, settings.minio_root_password, settings.minio_bucket, settings.minio_secure)
    if settings.telegram_bot_token:
        ctx["telegram"] = TelegramClient(settings.telegram_bot_token)


async def shutdown(ctx: dict) -> None:
    if client := ctx.get("telegram"):
        await client.close()


_registry = WorkerRegistry(
    functions=[ping, deliver_telegram, cleanup_notifications, purge_face_templates, escalate_leave_requests, scan_penalties, release_penalty_blocks, task_deadlines, need_deadlines, fire_reminders, logistics_expiry, warehouse_watch, mobile_watch, desk_watch, calls_watch, report_scheduler, deliver_report_telegram, deliver_statement_telegram, coord_report_job, explanation_deadlines, deliver_candidate_telegram, attestation_job, retention_scan_job, rotation_job, duty_overdue_job, control_digest_job],
    cron_jobs=[
        cron(heartbeat, second={0, 30}),
        cron(cleanup_notifications, hour={3}, minute={15}),
        cron(purge_face_templates, hour={3}, minute={45}),
        cron(escalate_leave_requests, minute=set(range(0, 60, 5))),
        cron(scan_penalties, hour={2}, minute={30}),
        cron(release_penalty_blocks, minute={5}),
        cron(task_deadlines, minute={0, 15, 30, 45}),
        cron(need_deadlines, minute={5, 20, 35, 50}),
        cron(fire_reminders),
        cron(mobile_watch, minute=set(range(1, 60, 2))),
        cron(desk_watch, minute={5, 20, 35, 50}),
        cron(calls_watch, second={0, 20, 40}),
        cron(report_scheduler, second={15}),
        cron(coord_report_job, minute=set(range(0, 60, 5))),
        cron(explanation_deadlines, minute={10, 40}),
        cron(attestation_job, minute={20}),
        cron(retention_scan_job, minute={25}),
        cron(rotation_job, minute=set(range(3, 60, 10))),
        cron(duty_overdue_job, minute={7, 22, 37, 52}),
        cron(control_digest_job, minute={35}),
        cron(warehouse_watch, minute={2, 12, 22, 32, 42, 52}),
        cron(logistics_expiry, hour={8}, minute={10}),
    ],
)
load_worker_extension(settings.client_dir, _registry)


class WorkerSettings:
    functions = _registry.functions
    cron_jobs = _registry.cron_jobs
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 4
