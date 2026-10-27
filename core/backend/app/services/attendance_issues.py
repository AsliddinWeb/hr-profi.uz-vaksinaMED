"""Davomat muammosi: ko'rish huquqi, marshrut (koordinator -> HR), bildirishnoma shablonlari, tuzatishni qo'llash."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.attendance import AttendanceCorrection, AttendanceRecord
from app.models.attendance_issues import AttendanceIssue
from app.models.employees import Employee
from app.models.org import Branch
from app.models.schedule import ShiftTemplate
from app.rbac import matches
from app.services import attendance as att
from app.services.answers import route_for, users_with_permission
from app.services.notifications import register_template

PENDING = ("pending_coordinator", "pending_hr")
BACKDATE_DAYS = 14
KINDS = "missed_in|missed_out|wrong_checkout|other"
METHODS = "qr|face|gps|other"

register_template(
    "attendance_issue.new",
    {"uz": "Davomat muammosi", "ru": "Проблема с отметкой"},
    {"uz": "{name}: {date} kuni belgilash muammosi", "ru": "{name}: проблема с отметкой за {date}"},
    "warning",
)
register_template(
    "attendance_issue.verified",
    {"uz": "Davomat muammosi koordinator tomonidan tasdiqlandi", "ru": "Проблема с отметкой подтверждена координатором"},
    {"uz": "{name}: {date}. Qaror kutilmoqda.", "ru": "{name}: {date}. Ожидает решения."},
    "info",
)
register_template(
    "attendance_issue.approved",
    {"uz": "Davomat tuzatildi", "ru": "Отметка исправлена"},
    {"uz": "{date} kuni davomatingiz tuzatildi", "ru": "Ваша отметка за {date} исправлена"},
    "success",
)
register_template(
    "attendance_issue.rejected",
    {"uz": "Davomat so'rovi rad etildi", "ru": "Запрос по отметке отклонён"},
    {"uz": "{date}. Sabab: {note}", "ru": "{date}. Причина: {note}"},
    "danger",
)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def is_hr(auth: AuthContext) -> bool:
    return has(auth, "attendance.edit")


def can_verify(auth: AuthContext, issue: AttendanceIssue, emp: Employee) -> bool:
    if issue.status not in PENDING or emp.user_id == auth.user.id:
        return False
    if is_hr(auth):
        return issue.status == "pending_coordinator"
    return has(auth, "answers.decide") and issue.status == "pending_coordinator" and issue.coordinator_user_id == auth.user.id


def can_decide(auth: AuthContext, issue: AttendanceIssue, emp: Employee) -> bool:
    return issue.status in PENDING and emp.user_id != auth.user.id and is_hr(auth)


def sees_all(auth: AuthContext) -> bool:
    """HR yoki faqat ko'rish huquqi bor rol. Koordinator (answers.decide) attendance.read ga ega bo'lsa ham faqat o'z filiallarini ko'radi."""
    return is_hr(auth) or (has(auth, "attendance.read") and not has(auth, "answers.decide"))


def can_view(auth: AuthContext, issue: AttendanceIssue, emp: Employee) -> bool:
    return emp.user_id == auth.user.id or sees_all(auth) or (has(auth, "answers.decide") and issue.coordinator_user_id == auth.user.id)


def visible_clause(auth: AuthContext, emp_user_col):
    if sees_all(auth):
        return None
    conds = [emp_user_col == auth.user.id]
    if has(auth, "answers.decide"):
        conds.append(AttendanceIssue.coordinator_user_id == auth.user.id)
    return or_(*conds)


def add_history(issue: AttendanceIssue, action: str, actor: str | None, level: str | None, note: str | None, moment: datetime) -> None:
    issue.history = [*(issue.history or []), {"action": action, "actor": actor, "level": level, "note": note, "at": moment.isoformat()}]


async def initial_route(db: AsyncSession, emp: Employee) -> tuple[str, int | None, list[int]]:
    """(holat, koordinator, bildirishnoma oluvchilar): koordinator bo'lsa avval unga, aks holda HR ga."""
    coordinator = await route_for(db, emp)
    if coordinator:
        return "pending_coordinator", coordinator, [coordinator]
    return "pending_hr", None, await users_with_permission(db, "attendance.edit")


async def apply_fix(db: AsyncSession, issue: AttendanceIssue, emp: Employee, actor_id: int, check_in: datetime | None, check_out: datetime | None, note: str | None) -> AttendanceRecord:
    """Tasdiqlangan so'rov bo'yicha yozuvni yaratadi/yangilaydi va tuzatish tarixiga yozadi."""
    from app.api.attendance import RecordIn, _fill  # noqa: PLC0415  (api -> service sikli oldini olish)

    rec = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == issue.work_date))
    t_in = check_in or issue.claimed_in or (rec.check_in_at if rec else None)
    if t_in is None:
        raise error(400, "time_required")
    if check_out is not None:
        t_out: datetime | None = check_out
    elif issue.claimed_out is not None:
        t_out = issue.claimed_out
    elif issue.kind == "wrong_checkout":
        t_out = None  # noto'g'ri ketish belgisi olib tashlanadi
    else:
        t_out = rec.check_out_at if rec else None
    reason = (note or issue.comment).strip()[:480]
    before = att.record_snapshot(rec) if rec else None
    shift_id = rec.shift_id if rec else None
    if rec is None:
        _, shift = await att._context(db, emp, t_in)
        shift_id = shift.id if shift else None
        rec = AttendanceRecord(employee_id=emp.id, work_date=issue.work_date, created_by=actor_id, check_in_at=t_in, in_method="manual")
        db.add(rec)
    elif shift_id is not None and await db.get(ShiftTemplate, shift_id) is None:
        shift_id = None
    await _fill(db, rec, RecordIn(check_in_at=t_in, check_out_at=t_out, shift_id=shift_id, note=f"Davomat muammosi #{issue.id}", reason=reason or "Davomat muammosi"))
    await db.flush()
    db.add(
        AttendanceCorrection(
            employee_id=emp.id, work_date=issue.work_date, action="create" if before is None else "update",
            reason=f"Davomat muammosi #{issue.id}: {reason}"[:500], before=before, after=att.record_snapshot(rec), actor_id=actor_id,
        )
    )
    return rec


def out(issue: AttendanceIssue, emp: Employee, branch: Branch | None, auth: AuthContext) -> dict[str, Any]:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "id": issue.id,
        "employee": {"id": emp.id, "employee_no": emp.employee_no, "full_name": emp.full_name},
        "branch": branch.name if branch else None,
        "work_date": issue.work_date.isoformat(),
        "kind": issue.kind,
        "method_tried": issue.method_tried,
        "claimed_in": iso(issue.claimed_in),
        "claimed_out": iso(issue.claimed_out),
        "comment": issue.comment,
        "status": issue.status,
        "decided_at": iso(issue.decided_at),
        "decision_note": issue.decision_note,
        "created_at": iso(issue.created_at),
        "history": issue.history or [],
        "can_verify": can_verify(auth, issue, emp),
        "can_decide": can_decide(auth, issue, emp),
        "can_cancel": emp.user_id == auth.user.id and issue.status in PENDING,
    }


def check_date(work_date: date, today: date) -> None:
    if work_date > today:
        raise error(400, "date_future")
    if (today - work_date).days > BACKDATE_DAYS:
        raise error(400, "date_too_old", days=BACKDATE_DAYS)
