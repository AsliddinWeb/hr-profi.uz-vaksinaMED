"""Avtomatik tushuntirish xati: davomatdagi qoidabuzarlik (kechikish, kelmaslik, erta ketish, ketish belgilanmagan)
uchun xat va «tasdiq kutilmoqda» jarimasi o'zi yaratiladi.

Oqim: 1) xodim xatni o'qiydi va sababni o'zi yozadi -> 2) tasdiqlaydi (QR qo'yiladi) -> 3) imzosini chizadi.
Xat imzolanmaguncha xodim keyingi «Keldim» ni belgilay olmaydi. Faktlar (vaqtlar, bosqich, chora) yaratilganda
muhrlanadi: keyin qoida yoki smena o'zgarsa ham xat matni o'zgarmaydi.
"""

import base64
import re
import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import error
from app.models.attendance import AttendanceRecord
from app.models.auth import User
from app.models.employees import Employee
from app.models.letters import ExplanationLetter, LetterTemplate
from app.models.org import Branch, Department, Position
from app.models.penalties import Penalty, PenaltyRuleVersion
from app.models.schedule import ShiftTemplate
from app.services import letters as lsvc
from app.services import penalties as psvc
from app.services.notifications import notify, register_template
from app.timeutil import local_date, localize

OPEN = lsvc.OPEN
MIN_WORDS = 6
MIN_CHARS = 40
MAX_SIGNATURE_BYTES = 300_000
MONTHS_UZ = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr")
WEEKDAYS_UZ = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")

register_template(
    "letters.auto",
    {"uz": "Tushuntirish xati yozishingiz kerak", "ru": "Нужно написать объяснительную"},
    {
        "uz": "{incident}, {incident_date}. Xat imzolanmaguncha keyingi «Keldim» belgilanmaydi.",
        "ru": "{incident}, {incident_date}. Пока письмо не подписано, следующая отметка «Пришёл» недоступна.",
    },
    "danger",
)


def enabled(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("auto_letters", True))


def _hm(dt: datetime | None) -> str | None:
    return localize(dt).strftime("%H:%M") if dt else None


def _money(v: Decimal | float | int) -> str:
    return f"{int(v):,}".replace(",", " ")


def long_date(d: date) -> str:
    return f"{d.year}-yil {d.day}-{MONTHS_UZ[d.month - 1]} ({WEEKDAYS_UZ[d.weekday()]})"


async def month_count(db: AsyncSession, emp_id: int, day: date) -> int:
    """Shu oy ichidagi (shu kungacha, shu kun ham) hisobga olinadigan avtomatik qoidabuzarliklar soni."""
    start = day.replace(day=1)
    return await db.scalar(
        select(func.count()).select_from(Penalty).where(
            Penalty.employee_id == emp_id, Penalty.source == "auto", Penalty.status.in_(psvc.LIVE),
            Penalty.incident_date >= start, Penalty.incident_date <= day,
        )
    ) or 0  # fmt: skip


async def build_facts(db: AsyncSession, emp: Employee, itype: str, day: date, rec: AttendanceRecord | None, shift: ShiftTemplate | None, penalty: Penalty, cfg: dict[str, Any]) -> dict[str, Any]:
    dept = await db.get(Department, emp.department_id) if emp.department_id else None
    pos = await db.get(Position, emp.position_id) if emp.position_id else None
    branch = await db.get(Branch, (rec.branch_id if rec and rec.branch_id else None) or emp.branch_id) if (rec and rec.branch_id) or emp.branch_id else None
    coord = await db.get(User, branch.coordinator_user_id) if branch and branch.coordinator_user_id else None
    steps = cfg["steps"]
    nxt = steps[min(penalty.step, len(steps) - 1)] if penalty.step < len(steps) else None
    start = rec.planned_start if rec else None
    end = rec.planned_end if rec else None
    if rec is None and shift is not None:
        from app.services.attendance import planned_window

        start, end = planned_window(shift, day)
    return {
        "incident": itype, "incident_label": lsvc.INCIDENT_UZ[itype], "date": day.isoformat(), "date_long": long_date(day),
        "employee": emp.full_name, "employee_phone": emp.phone, "position": pos.name if pos else None,
        "department": dept.name if dept else None, "branch": branch.name if branch else None,
        "branch_phone": branch.phone if branch else None,
        "coordinator": coord.full_name if coord else None, "coordinator_phone": coord.phone if coord else None,
        "shift": shift.name if shift else None, "planned_start": _hm(start), "planned_end": _hm(end),
        "late_grace": shift.late_grace_minutes if shift else 0, "early_grace": shift.early_leave_grace_minutes if shift else 0,
        "check_in": _hm(rec.check_in_at) if rec else None, "check_out": _hm(rec.check_out_at) if rec else None,
        "late_minutes": rec.late_minutes if rec else 0, "early_minutes": rec.early_leave_minutes if rec else 0,
        "month_count": await month_count(db, emp.id, day),
        "step": penalty.step, "measure": penalty.label, "amount": float(penalty.amount),
        "next_step": nxt["step"] if nxt and nxt["step"] != penalty.step else None,
        "next_measure": nxt["label"] if nxt and nxt["step"] != penalty.step else None,
        "next_amount": float(nxt["amount"]) if nxt and nxt["step"] != penalty.step else None,
        "steps": [{"step": s["step"], "label": s["label"], "amount": float(s["amount"]), "block_days": s["block_days"]} for s in steps],
    }  # fmt: skip


async def create(db: AsyncSession, emp: Employee, itype: str, day: date, rec: AttendanceRecord | None, shift: ShiftTemplate | None, penalty: Penalty, rules: PenaltyRuleVersion, moment: datetime):
    """Jarimaga bog'langan avtomatik xatni yaratadi. Bir jarimaga bitta xat."""
    if await db.scalar(select(ExplanationLetter.id).where(ExplanationLetter.penalty_id == penalty.id)):
        return None, []
    tpl = await db.scalar(select(LetterTemplate).where(LetterTemplate.is_default.is_(True)))
    letter = ExplanationLetter(
        number=await lsvc.next_number(db, local_date(moment).year), code=secrets.token_urlsafe(12), employee_id=emp.id,
        template_id=tpl.id if tpl else None, incident_type=itype, incident_date=day, due_date=None, requested_by=None,
        requested_at=moment, status="requested", auto=True, penalty_id=penalty.id,
        facts=await build_facts(db, emp, itype, day, rec, shift, penalty, rules.config),
    )  # fmt: skip
    db.add(letter)
    await db.flush()
    lsvc.add_event(db, letter, "requested", None, "avtomatik")
    notes = []
    if emp.user_id:
        notes = await notify(db, [emp.user_id], "letters.auto", link="/", params={"incident": lsvc.INCIDENT_UZ[itype], "incident_date": lsvc.fmt_date(day)})
    return letter, notes


async def on_violation(db: AsyncSession, emp: Employee, itype: str, rec: AttendanceRecord, moment: datetime):
    """Belgilash paytida aniqlangan qoidabuzarlik (kechikish, erta ketish): jarima (tasdiq kutilmoqda) + xat."""
    try:
        rules = await psvc.current_rules(db)
    except Exception:  # qoida hali yo'q: hech narsa qilinmaydi
        return []
    cfg = rules.config
    trig = cfg["triggers"].get(itype)
    minutes = rec.late_minutes if itype == "late" else rec.early_leave_minutes
    if not enabled(cfg) or not trig or not trig["enabled"] or minutes < max(trig["min_minutes"], 1):
        return []
    day = rec.work_date
    if await db.scalar(select(Penalty.id).where(Penalty.employee_id == emp.id, Penalty.incident_date == day, Penalty.incident_type == itype, Penalty.source == "auto")):
        return []
    step = psvc.step_for(await psvc.count_prior(db, emp.id, itype, day, cfg), cfg)
    details = {"status": itype, "late_minutes" if itype == "late" else "early_minutes": minutes}
    p = Penalty(
        employee_id=emp.id, incident_type=itype, incident_date=day, source="auto", rule_version_id=rules.id, step=step["step"],
        label=step["label"], amount=Decimal(str(step["amount"])), block_days=step["block_days"], details=details, status="pending",
    )  # fmt: skip
    db.add(p)
    await db.flush()
    shift = await db.get(ShiftTemplate, rec.shift_id) if rec.shift_id else None
    _, notes = await create(db, emp, itype, day, rec, shift, p, rules, moment)
    return notes


async def open_letter(db: AsyncSession, emp_id: int) -> ExplanationLetter | None:
    return await db.scalar(
        select(ExplanationLetter).where(ExplanationLetter.employee_id == emp_id, ExplanationLetter.auto.is_(True), ExplanationLetter.status.in_(OPEN)).order_by(ExplanationLetter.id).limit(1)
    )


# --- Matn -------------------------------------------------------------------------------


def _who(f: dict[str, Any], company: str) -> str:
    place = f.get("branch") or f.get("department")
    where = f"«{company}»ning {place}da" if place else f"«{company}»da"  # «Chilonzor filiali» -> «Chilonzor filialida»
    return f"Men, {f['employee']}, {where} {f.get('position') or 'xodim'} lavozimida faoliyat yuritaman."


def incident_text(f: dict[str, Any]) -> str:
    shift = f"{f['shift']} bo'yicha " if f.get("shift") else ""
    n = f.get("month_count") or 1
    tail = f" Ushbu holat platformadagi davomat tizimida qayd etilgan hamda joriy oy davomidagi {n}-qoidabuzarlik hisoblanadi."
    i = f["incident"]
    if i == "late":
        return f"{f['date_long']} kuni {shift}ish vaqtim soat {f['planned_start']} da boshlanishi belgilangan bo'lishiga qaramay, ishga soat {f['check_in']} da keldim, ya'ni {f['late_minutes']} daqiqaga kechikdim." + tail
    if i == "early_leave":
        return f"{f['date_long']} kuni {shift}ish vaqtim soat {f['planned_end']} da tugashi belgilangan bo'lishiga qaramay, ishdan soat {f['check_out']} da, ya'ni {f['early_minutes']} daqiqa oldin ketdim." + tail
    if i == "absent":
        when = f" (soat {f['planned_start']} – {f['planned_end']})" if f.get("planned_start") else ""
        return f"{f['date_long']} kuni {shift}ishga chiqishim belgilangan bo'lishiga qaramay{when}, ishga kelmadim." + tail
    return f"{f['date_long']} kuni ishga soat {f.get('check_in') or '—'} da kelib, ishdan ketish vaqtimni platformada belgilamadim." + tail


def basis_text(f: dict[str, Any]) -> str | None:
    i = f["incident"]
    if i == "late" and f.get("planned_start"):
        return (
            f"Asos: smena soat {f['planned_start']} da boshlanadi, {f['late_grace']} daqiqa imtiyoz beriladi. Imtiyozdan oshgani uchun "
            f"kechikish smena boshlanishidan hisoblanadi: {f['check_in']} − {f['planned_start']} = {f['late_minutes']} daqiqa."
        )
    if i == "early_leave" and f.get("planned_end"):
        return (
            f"Asos: smena soat {f['planned_end']} da tugaydi, {f['early_grace']} daqiqa imtiyoz beriladi. Imtiyozdan oshgani uchun "
            f"erta ketish smena tugashigacha hisoblanadi: {f['planned_end']} − {f['check_out']} = {f['early_minutes']} daqiqa."
        )
    if i == "absent":
        return "Asos: grafik bo'yicha ish kuni bo'lgan, davomat tizimida kelish qayd etilmagan va tasdiqlangan ruxsat (javob) yo'q."
    if i == "no_checkout":
        return "Asos: ichki tartib qoidalariga ko'ra ishdan ketish vaqti platformada belgilanishi shart."
    return None


PROMISE = {
    "late": "ish joyimga belgilangan vaqtdan kamida 10–15 daqiqa oldin yetib kelishga, kechikish ehtimoli tug'ilganda esa bu haqda bevosita rahbarimni oldindan xabardor qilishga",
    "early_leave": "ish vaqti tugaguncha ish joyimda bo'lishga, erta ketish zarurati tug'ilganda esa rahbarimdan oldindan ruxsat olishga",
    "absent": "grafik bo'yicha belgilangan har bir ish kunida ishga chiqishga, kela olmasam esa oldindan javob olishga",
    "no_checkout": "har bir ish kuni oxirida ketish vaqtimni platformada belgilashga",
}


def measure_text(f: dict[str, Any]) -> str:
    amount = f" ({_money(f['amount'])} so'm)" if f.get("amount") else ""
    promise = PROMISE.get(f["incident"])
    tail = f", {promise} majburiyat olaman." if promise else " majburiyat olaman."
    return f"Ushbu holat uchun belgilangan intizomiy chora — {f['measure']}{amount} — bilan tanishdim. Shuningdek, bundan buyon ichki mehnat tartibi qoidalariga qat'iy rioya qilishga" + tail


def escalation_text(f: dict[str, Any]) -> str:
    return (
        "Ushbu holat qayta takrorlansa, menga nisbatan quyidagi bosqichlarda ko'rsatilgan choralar hamda rahbariyat tomonidan "
        "tayinlanadigan intizomiy jazo (hayfsan, jarima, mehnat shartnomasini bekor qilish) qo'llanilishiga roziman va e'tirozim yo'q."
    )


def next_text(f: dict[str, Any]) -> str | None:
    if not f.get("next_measure"):
        return None
    amount = f" ({_money(f['next_amount'])} so'm)" if f.get("next_amount") else ""
    return f"Keyingi ({f['next_step']}-) holatda: {f['next_measure']}{amount}."


PREAMBLE = (
    "Men mazkur tushuntirish xatini yozishdan oldin yolg'on ma'lumot bermaslik va vaziyat (holat) haqida to'g'ri ma'lumot berish "
    "lozimligi haqida ogohlantirildim hamda faqat to'g'ri ma'lumot beraman."
)


def document(letter: ExplanationLetter, company: str, recipient: str) -> dict[str, Any]:
    """Xat hujjati (frontend ko'rinishi, PDF va imzolangan nusxa uchun yagona manba)."""
    f = letter.facts or {}
    return {
        "recipient": recipient, "company": company, "title": "TUSHUNTIRISH XATI",
        "subtitle": f"{f.get('incident_label', '').capitalize()} · {lsvc.fmt_date(letter.incident_date)} · joriy oydagi {f.get('month_count') or 1}-qoidabuzarlik",
        "measure_line": f"{f.get('measure', '')}" + (f" ({_money(f['amount'])} so'm)" if f.get("amount") else ""),
        "preamble": PREAMBLE, "intro": _who(f, company), "incident": incident_text(f), "basis": basis_text(f),
        "explanation": letter.explanation, "explanation_lead": "Mazkur holat quyidagi sabab bilan yuz berdi:",
        "measure": measure_text(f), "escalation": escalation_text(f), "next": next_text(f),
        "closing": f"Ushbu tushuntirish xatini {company} platformasida to'liq o'qib, mazmuni bilan tanishib chiqdim va rozilik bildirgan holda o'z imzom bilan tasdiqlayman. Undagi barcha ma'lumotlar to'g'ri.",
        "steps": f.get("steps") or [], "step": f.get("step"),
    }  # fmt: skip


def document_text(doc: dict[str, Any]) -> str:
    parts = [
        doc["preamble"], f"{doc['intro']} {doc['incident']}", doc.get("basis"), f"{doc['explanation_lead']} {doc.get('explanation') or ''}",
        doc["measure"], doc["escalation"], doc.get("next"), doc["closing"],
    ]  # fmt: skip
    return "\n\n".join(p for p in parts if p)


async def recipient_line(db: AsyncSession, letter: ExplanationLetter, company: str) -> str:
    tpl = await db.get(LetterTemplate, letter.template_id) if letter.template_id else None
    line = (tpl.recipient_line if tpl else "") or "HR direktoriga"
    return lsvc.render(line, {"company": company})


# --- Xodim amallari ---------------------------------------------------------------------


def check_explanation(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) < MIN_CHARS or len(t.split(" ")) < MIN_WORDS:
        raise error(400, "explanation_short", min_words=MIN_WORDS, min_chars=MIN_CHARS)
    return t


def confirm(db: AsyncSession, letter: ExplanationLetter, explanation: str, actor_id: int, moment: datetime) -> None:
    """1-qadam: sabab yozilib, xat to'liq o'qilgani tasdiqlanadi. QR shu paytdan ko'rinadi."""
    if not letter.auto or letter.status not in OPEN:
        raise error(409, "letter_not_open")
    letter.explanation = check_explanation(explanation)
    letter.confirmed_at = moment
    lsvc.add_event(db, letter, "confirmed", actor_id)


def check_signature(data_url: str) -> str:
    m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", (data_url or "").strip())
    if not m:
        raise error(400, "signature_invalid")
    try:
        raw = base64.b64decode(m.group(1), validate=True)
    except ValueError:
        raise error(400, "signature_invalid") from None
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > MAX_SIGNATURE_BYTES or len(raw) < 200:
        raise error(400, "signature_invalid")
    return data_url.strip()


async def sign(db: AsyncSession, letter: ExplanationLetter, emp: Employee, user: User, signature: str, company: str, ip: str | None, moment: datetime):
    """3-qadam: chizilgan imzo bilan topshiriladi. Matn muhrlanadi, ko'rib chiquvchilarga xabar boradi."""
    if not letter.auto or letter.status not in OPEN:
        raise error(409, "letter_not_open")
    if letter.confirmed_at is None or not letter.explanation:
        raise error(409, "letter_not_confirmed")
    letter.signature_image = check_signature(signature)
    doc = document(letter, company, await recipient_line(db, letter, company))
    letter.snapshot = {
        "title": doc["title"], "recipient": doc["recipient"], "body": document_text(doc), "employee_name": emp.full_name,
        "company": company, "date": lsvc.fmt_date(local_date(moment)), "incident": f"{doc['subtitle']}",
    }  # fmt: skip
    letter.submitted_at = moment
    letter.signature = {"user_id": user.id, "name": user.full_name, "at": moment.isoformat(), "ip": ip, "method": "drawn"}
    letter.content_hash = lsvc.content_hash(letter)
    letter.status = "submitted"
    letter.review_note = None
    lsvc.add_event(db, letter, "submitted", user.id)
    from app.services.answers import users_with_permission  # circular importdan qochish

    reviewers = await users_with_permission(db, "letters.review")
    return await notify(db, [u for u in reviewers if u != user.id], "letters.submitted", link=f"/letters/{letter.id}", params={"name": emp.full_name, "number": letter.number})

