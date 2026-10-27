"""Tushuntirish xatlari: so'rash, yozish + elektron imzo, ko'rib chiqish, tekshirish kodi."""

import hashlib
import json
import re
import secrets
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.employees import Employee
from app.models.letters import ExplanationLetter, LetterEvent, LetterTemplate
from app.models.org import Branch, Department, Position
from app.rbac import matches
from app.services.notifications import notify, register_template
from app.timeutil import local_date

INCIDENTS = ("late", "absent", "early_leave", "no_checkout", "discipline", "other")
INCIDENT_UZ = {
    "late": "ishga kechikish", "absent": "ishga kelmaslik", "early_leave": "ishdan erta ketish",
    "no_checkout": "ketish belgilanmaganligi", "discipline": "intizomiy holat", "other": "boshqa holat",
}  # fmt: skip
OPEN = ("requested", "returned")
PLACEHOLDERS = ("employee_name", "position", "department", "branch", "incident_date", "incident", "explanation", "date", "company", "number")
MAX_TEXT = 5000

register_template(
    "letters.requested",
    {"uz": "Tushuntirish xati so'raldi", "ru": "Запрошена объяснительная"},
    {"uz": "{number}: {incident}, {incident_date}. Muddat: {due}", "ru": "{number}: {incident}, {incident_date}. Срок: {due}"},
    "warning",
)
register_template(
    "letters.submitted",
    {"uz": "Tushuntirish xati topshirildi", "ru": "Объяснительная подана"},
    {"uz": "{name}: {number}", "ru": "{name}: {number}"},
    "info",
)
register_template(
    "letters.accepted",
    {"uz": "Tushuntirish xatingiz qabul qilindi", "ru": "Ваша объяснительная принята"},
    {"uz": "{number}", "ru": "{number}"},
    "success",
)
register_template(
    "letters.returned",
    {"uz": "Tushuntirish xatingiz qaytarildi", "ru": "Ваша объяснительная возвращена"},
    {"uz": "{number}. Sabab: {note}", "ru": "{number}. Причина: {note}"},
    "danger",
)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


# --- Shablon matni ---------------------------------------------------------------------


def render(template: str, ctx: dict[str, str]) -> str:
    """`{nom}` belgilarini almashtiradi. Faqat ruxsat etilgan nomlar; atribut/indeks ishlatib bo'lmaydi."""
    return re.sub(r"\{(\w+)\}", lambda m: ctx.get(m.group(1), m.group(0)) if m.group(1) in PLACEHOLDERS else m.group(0), template)


def unknown_placeholders(*texts: str) -> list[str]:
    found = {m for t in texts for m in re.findall(r"\{([^{}]*)\}", t or "")}
    return sorted(found - set(PLACEHOLDERS))


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


async def employee_context(db: AsyncSession, emp: Employee, company: str) -> dict[str, str]:
    dept = await db.get(Department, emp.department_id) if emp.department_id else None
    pos = await db.get(Position, emp.position_id) if emp.position_id else None
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    return {
        "employee_name": emp.full_name, "position": pos.name if pos else "—", "department": dept.name if dept else "—",
        "branch": branch.name if branch else "—", "company": company,
    }  # fmt: skip


# --- Hayot sikli ------------------------------------------------------------------------


async def next_number(db: AsyncSession, year: int) -> str:
    n = await db.scalar(text("SELECT nextval('letter_no_seq')"))
    return f"TX-{year}-{int(n):04d}"


def add_event(db: AsyncSession, letter: ExplanationLetter, action: str, actor_id: int | None, note: str | None = None, data: dict | None = None) -> None:
    db.add(LetterEvent(letter_id=letter.id, action=action, actor_id=actor_id, note=note, data=data))


async def can_issue_to(db: AsyncSession, auth: AuthContext, emp: Employee) -> bool:
    if has(auth, "letters.manage"):
        return True
    if not has(auth, "letters.issue") or emp.user_id == auth.user.id:
        return False
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    return bool(branch and branch.coordinator_user_id == auth.user.id)


def can_view(auth: AuthContext, letter: ExplanationLetter, emp: Employee) -> bool:
    return emp.user_id == auth.user.id or has(auth, "letters.read") or letter.requested_by == auth.user.id


def can_review(auth: AuthContext, letter: ExplanationLetter, emp: Employee) -> bool:
    if letter.status != "submitted" or emp.user_id == auth.user.id:
        return False
    return has(auth, "letters.review") or (has(auth, "letters.issue") and letter.requested_by == auth.user.id)


def can_cancel(auth: AuthContext, letter: ExplanationLetter) -> bool:
    return letter.status in OPEN and (has(auth, "letters.manage") or letter.requested_by == auth.user.id)


async def issue(db: AsyncSession, auth: AuthContext, emp: Employee, template: LetterTemplate, *, incident_type, incident_date, incident_note, due_date, moment: datetime):
    if emp.status != "active":
        raise error(409, "employee_dismissed")
    number = await next_number(db, local_date(moment).year)
    letter = ExplanationLetter(
        number=number, code=secrets.token_urlsafe(12), employee_id=emp.id, template_id=template.id, incident_type=incident_type,
        incident_date=incident_date, incident_note=(incident_note or "").strip() or None, due_date=due_date,
        requested_by=auth.user.id, requested_at=moment, status="requested",
    )  # fmt: skip
    db.add(letter)
    await db.flush()
    add_event(db, letter, "requested", auth.user.id, letter.incident_note)
    notes = []
    if emp.user_id:
        notes = await notify(
            db, [emp.user_id], "letters.requested", link=f"/letters/{letter.id}",
            params={"number": number, "incident": INCIDENT_UZ[incident_type], "incident_date": fmt_date(incident_date), "due": fmt_date(due_date) if due_date else "—"},
        )  # fmt: skip
    return letter, notes


def content_hash(letter: ExplanationLetter) -> str:
    payload = {
        "number": letter.number, "code": letter.code, "employee_id": letter.employee_id, "snapshot": letter.snapshot,
        "explanation": letter.explanation, "signature": letter.signature,
    }  # fmt: skip
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def submit(db: AsyncSession, letter: ExplanationLetter, emp: Employee, auth: AuthContext, template: LetterTemplate | None, explanation: str, company: str, ip: str | None, moment: datetime):
    """Xodim yozgan matnni elektron imzolab topshiradi. Matn va shablon shu paytda muhrlanadi."""
    if emp.user_id != auth.user.id:
        raise error(403, "forbidden")
    if letter.status not in OPEN:
        raise error(409, "letter_not_open")
    text_ = explanation.strip()
    if len(text_) < 10:
        raise error(400, "explanation_short")
    ctx = await employee_context(db, emp, company)
    ctx |= {
        "incident_date": fmt_date(letter.incident_date), "incident": INCIDENT_UZ[letter.incident_type], "explanation": text_,
        "date": fmt_date(local_date(moment)), "number": letter.number,
    }  # fmt: skip
    tpl = template
    letter.snapshot = {
        "title": render(tpl.title if tpl else "TUSHUNTIRISH XATI", ctx),
        "recipient": render(tpl.recipient_line if tpl else "", ctx),
        "body": render(tpl.body_template if tpl else "{explanation}", ctx),
        "employee_name": emp.full_name, "company": company, "date": ctx["date"],
        "incident": f"{ctx['incident']} ({ctx['incident_date']})",
    }  # fmt: skip
    letter.explanation = text_
    letter.submitted_at = moment
    letter.signature = {"user_id": auth.user.id, "name": auth.user.full_name, "at": moment.isoformat(), "ip": ip, "method": "password"}
    letter.content_hash = content_hash(letter)
    letter.status = "submitted"
    letter.review_note = None
    add_event(db, letter, "submitted", auth.user.id)
    reviewers = [letter.requested_by] if letter.requested_by else []
    from app.services.answers import users_with_permission  # circular importdan qochish

    reviewers = list(dict.fromkeys(reviewers + await users_with_permission(db, "letters.review")))
    notes = await notify(db, [u for u in reviewers if u != auth.user.id], "letters.submitted", link=f"/letters/{letter.id}", params={"name": emp.full_name, "number": letter.number})
    return notes


async def review(db: AsyncSession, letter: ExplanationLetter, emp: Employee, auth: AuthContext, action: str, note: str | None, moment: datetime):
    if letter.status != "submitted":
        raise error(409, "letter_not_submitted")
    if not can_review(auth, letter, emp):
        raise error(403, "forbidden")
    note = (note or "").strip() or None
    if action == "return" and not note:
        raise error(400, "note_required")
    letter.status = "accepted" if action == "accept" else "returned"
    letter.reviewed_by, letter.reviewed_at, letter.review_note = auth.user.id, moment, note
    add_event(db, letter, letter.status, auth.user.id, note)
    return await notify(db, [emp.user_id] if emp.user_id else [], f"letters.{letter.status}", link=f"/letters/{letter.id}", params={"number": letter.number, "note": note or ""})


async def get_template(db: AsyncSession, template_id: int | None) -> LetterTemplate:
    if template_id:
        t = await db.get(LetterTemplate, template_id)
        if not t or not t.is_active:
            raise error(400, "unknown_template")
        return t
    t = await db.scalar(select(LetterTemplate).where(LetterTemplate.is_default.is_(True)))
    if not t:
        raise error(409, "no_default_template")
    return t


def letter_out(letter: ExplanationLetter, emp: Employee, *, today: date, auth: AuthContext | None = None, requester: str | None = None) -> dict[str, Any]:
    overdue = bool(letter.status in OPEN and letter.due_date and letter.due_date < today)
    out = {
        "id": letter.id, "number": letter.number, "code": letter.code,
        "employee": {"id": emp.id, "employee_no": emp.employee_no, "full_name": emp.full_name},
        "incident_type": letter.incident_type, "incident_date": letter.incident_date, "incident_note": letter.incident_note,
        "due_date": letter.due_date, "overdue": overdue, "status": letter.status, "requested_at": letter.requested_at,
        "requested_by": requester, "submitted_at": letter.submitted_at, "reviewed_at": letter.reviewed_at, "review_note": letter.review_note,
        "has_scan": letter.scan_key is not None, "scan_filename": letter.scan_filename, "template_id": letter.template_id,
        "signed": letter.signature is not None, "content_hash": letter.content_hash,
    }  # fmt: skip
    if auth is not None:
        out["can_write"] = emp.user_id == auth.user.id and letter.status in OPEN
        out["can_review"] = can_review(auth, letter, emp)
        out["can_cancel"] = can_cancel(auth, letter)
        out["can_scan"] = letter.status in ("submitted", "accepted") and (emp.user_id == auth.user.id or has(auth, "letters.review"))
    return out


def public_view(letter: ExplanationLetter, emp: Employee, provided_hash: str | None) -> dict[str, Any]:
    """Ochiq tekshiruv: matn va shaxsiy ma'lumotsiz, faqat hujjat mavjudligi, holati va yaxlitligi."""
    parts = emp.full_name.split()
    short = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else (parts[0] if parts else "—")
    intact = bool(letter.content_hash) and content_hash(letter) == letter.content_hash
    return {
        "valid": letter.status in ("submitted", "accepted", "returned") and letter.signature is not None,
        "intact": intact, "number": letter.number, "employee": short, "status": letter.status,
        "incident_type": letter.incident_type, "incident_date": letter.incident_date,
        "signed_at": letter.signature.get("at") if letter.signature else None,
        "hash_prefix": (letter.content_hash or "")[:16],
        "hash_match": (provided_hash.strip().lower() == (letter.content_hash or "")[: len(provided_hash.strip())]) if provided_hash and provided_hash.strip() else None,
    }  # fmt: skip


DEFAULT_BODY = (
    "Men, {employee_name}, {department} bo'limi, {position}, {incident_date} sanasidagi holat ({incident}) bo'yicha "
    "quyidagilarni tushuntiraman:\n\n{explanation}\n\nIsh tartibi buzilishi takrorlanmasligini ma'lum qilaman."
)


async def ensure_default_template(db: AsyncSession) -> None:
    """Standart shablon yo'q bo'lsa yaratadi (migratsiya ham qo'shadi; bu yerda test/qayta tiklash uchun)."""
    if await db.scalar(select(LetterTemplate.id).where(LetterTemplate.is_default.is_(True))):
        return
    db.add(LetterTemplate(name="Standart tushuntirish xati", title="TUSHUNTIRISH XATI", recipient_line="HR direktoriga",
                          body_template=DEFAULT_BODY, is_default=True))  # fmt: skip
    await db.commit()
