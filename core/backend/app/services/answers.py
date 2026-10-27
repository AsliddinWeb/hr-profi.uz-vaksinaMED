"""Javob olish: so'rov yaratish, yo'naltirish (koordinator -> HR), qaror, eskalatsiya."""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import AuthContext, error
from app.models.answers import LeaveEvent, LeaveRequest
from app.models.auth import Role, User
from app.models.employees import Employee
from app.models.org import Branch
from app.rbac import matches
from app.services.notifications import notify, register_template

REASONS = ("sick", "family", "personal", "business", "other")
ACTIVE = ("pending_coordinator", "pending_hr", "approved")
PENDING = ("pending_coordinator", "pending_hr")
MAX_DAYS = 31
BACKDATE_DAYS = 7  # o'tgan sanaga (masalan, kasallik) shuncha kun orqaga so'rov berish mumkin
MIN_HOURLY_MIN = 15
MAX_HOURLY_MIN = 720

register_template(
    "answers.new",
    {"uz": "Yangi ruxsat so'rovi", "ru": "Новая заявка на отсутствие"},
    {"uz": "{name}: {period}", "ru": "{name}: {period}"},
    "info",
)
register_template(
    "answers.escalated",
    {"uz": "So'rov HR ga o'tdi: javob berilmadi", "ru": "Заявка передана в HR: нет ответа"},
    {"uz": "{name}: {period}. Koordinator {hours} soat ichida javob bermadi.", "ru": "{name}: {period}. Координатор не ответил в течение {hours} ч."},
    "warning",
)
register_template(
    "answers.approved",
    {"uz": "Ruxsat so'rovingiz tasdiqlandi", "ru": "Ваша заявка одобрена"},
    {"uz": "{period}", "ru": "{period}"},
    "success",
)
register_template(
    "answers.rejected",
    {"uz": "Ruxsat so'rovingiz rad etildi", "ru": "Ваша заявка отклонена"},
    {"uz": "{period}. Sabab: {note}", "ru": "{period}. Причина: {note}"},
    "danger",
)
register_template(
    "answers.escalated_employee",
    {"uz": "So'rovingiz HR ga yuborildi", "ru": "Ваша заявка передана в HR"},
    {"uz": "{period}", "ru": "{period}"},
    "info",
)


def period_text(r: LeaveRequest) -> str:
    d1 = r.start_date.strftime("%d.%m.%Y")
    if r.kind == "hourly" and r.start_time and r.end_time:
        return f"{d1} {r.start_time:%H:%M}–{r.end_time:%H:%M}"
    if r.end_date != r.start_date:
        return f"{d1} – {r.end_date.strftime('%d.%m.%Y')}"
    return d1


def minutes(t: time) -> int:
    return t.hour * 60 + t.minute


async def users_with_permission(db: AsyncSession, perm: str) -> list[int]:
    roles = (await db.scalars(select(Role))).all()
    role_ids = [r.id for r in roles if matches(frozenset(r.permission_keys), perm)]
    if not role_ids:
        return []
    return list((await db.scalars(select(User.id).where(User.role_id.in_(role_ids), User.is_active.is_(True)))).all())


async def route_for(db: AsyncSession, emp: Employee) -> int | None:
    """Xodim filialining koordinatori (faol va o'zi emas) yoki None (to'g'ridan-to'g'ri HR)."""
    if not emp.branch_id:
        return None
    branch = await db.get(Branch, emp.branch_id)
    uid = branch.coordinator_user_id if branch else None
    if not uid or uid == emp.user_id:
        return None
    user = await db.get(User, uid)
    return uid if user and user.is_active else None


def validate(kind: str, start: date, end: date, st: time | None, et: time | None, today: date) -> None:
    if start < today - timedelta(days=BACKDATE_DAYS):
        raise error(400, "date_too_old", days=BACKDATE_DAYS)
    if kind == "day":
        if end < start:
            raise error(400, "range_invalid")
        if (end - start).days + 1 > MAX_DAYS:
            raise error(400, "range_too_long", max_days=MAX_DAYS)
        return
    if st is None or et is None or minutes(et) <= minutes(st):
        raise error(400, "time_invalid")
    span = minutes(et) - minutes(st)
    if span < MIN_HOURLY_MIN or span > MAX_HOURLY_MIN:
        raise error(400, "hourly_length", min=MIN_HOURLY_MIN, max=MAX_HOURLY_MIN)


async def check_overlap(db: AsyncSession, emp_id: int, kind: str, start: date, end: date, st: time | None, et: time | None) -> None:
    rows = (
        await db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == emp_id, LeaveRequest.status.in_(ACTIVE), LeaveRequest.start_date <= end, LeaveRequest.end_date >= start
            )
        )
    ).all()
    for r in rows:
        if kind == "day" or r.kind == "day":
            raise error(409, "overlap")
        # ikkalasi soatlik, bir kunda: vaqt kesishmasi
        if st and et and r.start_time and r.end_time and minutes(st) < minutes(r.end_time) and minutes(et) > minutes(r.start_time):
            raise error(409, "overlap")


def add_event(db: AsyncSession, req: LeaveRequest, action: str, actor_id: int | None, level: str | None = None, note: str | None = None) -> None:
    db.add(LeaveEvent(request_id=req.id, action=action, actor_id=actor_id, level=level, note=note))


async def create_request(db: AsyncSession, emp: Employee, actor: User, *, kind, reason_type, reason, start_date, end_date, start_time, end_time, moment: datetime):
    """So'rov yaratadi va koordinatorga (yoki koordinator bo'lmasa HR ga) yo'naltiradi. (so'rov, bildirishnomalar)."""
    coordinator = await route_for(db, emp)
    req = LeaveRequest(
        employee_id=emp.id, kind=kind, reason_type=reason_type, reason=(reason or "").strip() or None,
        start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time,
        status="pending_coordinator" if coordinator else "pending_hr", coordinator_user_id=coordinator,
        submitted_at=moment,
        escalate_at=moment + timedelta(hours=get_settings().answers_escalation_hours) if coordinator else None,
    )  # fmt: skip
    db.add(req)
    await db.flush()
    add_event(db, req, "submitted", actor.id, "coordinator" if coordinator else "hr")
    targets = [coordinator] if coordinator else await users_with_permission(db, "answers.manage")
    params = {"name": emp.full_name, "period": period_text(req)}
    notes = await notify(db, [t for t in targets if t != actor.id], "answers.new", params=params, link=f"/answers/{req.id}")
    return req, notes


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def can_decide(auth: AuthContext, req: LeaveRequest, emp: Employee) -> bool:
    if req.status not in PENDING or emp.user_id == auth.user.id:
        return False
    if has(auth, "answers.manage"):
        return True
    return has(auth, "answers.decide") and req.status == "pending_coordinator" and req.coordinator_user_id == auth.user.id


def can_view(auth: AuthContext, req: LeaveRequest, emp: Employee) -> bool:
    return (
        emp.user_id == auth.user.id
        or has(auth, "answers.read")
        or has(auth, "answers.manage")
        or (has(auth, "answers.decide") and req.coordinator_user_id == auth.user.id)
    )


def visible_clause(auth: AuthContext, emp_user_col):
    """SQL sharti: foydalanuvchi qaysi so'rovlarni ko'ra oladi."""
    if has(auth, "answers.read") or has(auth, "answers.manage"):
        return None
    conds = [emp_user_col == auth.user.id]
    if has(auth, "answers.decide"):
        conds.append(LeaveRequest.coordinator_user_id == auth.user.id)
    return or_(*conds)


async def decide(db: AsyncSession, req: LeaveRequest, emp: Employee, auth: AuthContext, action: str, note: str | None, moment: datetime):
    if not can_decide(auth, req, emp):
        if req.status not in PENDING:
            raise error(409, "already_decided")
        raise error(403, "forbidden")
    note = (note or "").strip() or None
    if action == "reject" and not note:
        raise error(400, "note_required")
    level = "hr" if has(auth, "answers.manage") else "coordinator"
    req.status = "approved" if action == "approve" else "rejected"
    req.decided_by, req.decided_at, req.decided_level, req.decision_note = auth.user.id, moment, level, note
    req.escalate_at = None
    add_event(db, req, "approved" if action == "approve" else "rejected", auth.user.id, level, note)
    params = {"period": period_text(req), "note": note or ""}
    notes = await notify(db, [emp.user_id] if emp.user_id else [], f"answers.{req.status}", params=params, link=f"/answers/{req.id}")
    return notes


async def cancel(db: AsyncSession, req: LeaveRequest, emp: Employee, auth: AuthContext, today: date):
    if emp.user_id != auth.user.id:
        raise error(403, "forbidden")
    if req.status not in ACTIVE or (req.status == "approved" and req.start_date <= today):
        raise error(409, "cannot_cancel")
    req.status = "cancelled"
    req.escalate_at = None
    add_event(db, req, "cancelled", auth.user.id)


async def escalate_due(db: AsyncSession, moment: datetime):
    """Koordinator muddatida javob bermagan so'rovlarni HR ga o'tkazadi. Bildirishnomalarni qaytaradi."""
    hours = get_settings().answers_escalation_hours
    due = (
        await db.scalars(
            select(LeaveRequest).where(LeaveRequest.status == "pending_coordinator", LeaveRequest.escalate_at <= moment).with_for_update(skip_locked=True)
        )
    ).all()
    notes = []
    hr = await users_with_permission(db, "answers.manage") if due else []
    for req in due:
        emp = await db.get(Employee, req.employee_id)
        req.status, req.escalated_at, req.escalate_at = "pending_hr", moment, None
        add_event(db, req, "escalated", None, "hr", f"{hours}h")
        params = {"name": emp.full_name if emp else "", "period": period_text(req), "hours": hours}
        notes += await notify(db, hr, "answers.escalated", params=params, link=f"/answers/{req.id}")
        if emp and emp.user_id:
            notes += await notify(db, [emp.user_id], "answers.escalated_employee", params=params, link=f"/answers/{req.id}")
    return due, notes


async def approved_leave_days(db: AsyncSession, employee_ids: list[int], start: date, end: date) -> dict[int, set[date]]:
    """Tasdiqlangan KUNLIK ruxsatlar (davomatda 'ruxsatli' holat)."""
    out: dict[int, set[date]] = {}
    if not employee_ids:
        return out
    rows = (
        await db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id.in_(employee_ids), LeaveRequest.kind == "day", LeaveRequest.status == "approved",
                LeaveRequest.start_date <= end, LeaveRequest.end_date >= start,
            )
        )
    ).all()  # fmt: skip
    for r in rows:
        d = max(r.start_date, start)
        while d <= min(r.end_date, end):
            out.setdefault(r.employee_id, set()).add(d)
            d += timedelta(days=1)
    return out


def request_out(r: LeaveRequest, emp: Employee, *, moment: datetime | None = None, can_decide_: bool = False, can_cancel: bool = False) -> dict[str, Any]:
    return {
        "id": r.id,
        "employee": {"id": emp.id, "employee_no": emp.employee_no, "full_name": emp.full_name},
        "kind": r.kind, "reason_type": r.reason_type, "reason": r.reason,
        "start_date": r.start_date, "end_date": r.end_date,
        "start_time": r.start_time.strftime("%H:%M") if r.start_time else None,
        "end_time": r.end_time.strftime("%H:%M") if r.end_time else None,
        "status": r.status, "submitted_at": r.submitted_at, "escalate_at": r.escalate_at, "escalated_at": r.escalated_at,
        "decided_at": r.decided_at, "decided_level": r.decided_level, "decision_note": r.decision_note,
        "can_decide": can_decide_, "can_cancel": can_cancel,
    }  # fmt: skip
