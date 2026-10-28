"""Rotatsiya: filialdan filialga vaqtincha o'tkazish (tasdiq, avtomatik boshlash va qaytarish)."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.employees import Employee
from app.models.org import Branch
from app.models.rotations import Rotation
from app.rbac import matches
from app.services import employees as emp_svc
from app.services.notifications import notify, register_template
from app.timeutil import local_date

OPEN = ("pending", "approved", "active")
MAX_DAYS = 366

register_template("rotation.requested", {"uz": "Rotatsiya so'rovi", "ru": "Запрос на ротацию"}, {"uz": "{employee}: {from_branch} → {to_branch}, {period}", "ru": "{employee}: {from_branch} → {to_branch}, {period}"}, "info")
register_template("rotation.decided", {"uz": "Rotatsiya qarori", "ru": "Решение по ротации"}, {"uz": "{employee}: {result} ({from_branch} → {to_branch})", "ru": "{employee}: {result} ({from_branch} → {to_branch})"}, "info")
register_template("rotation.started", {"uz": "Rotatsiya boshlandi", "ru": "Ротация началась"}, {"uz": "{employee}: {to_branch} filialida, {end} gacha", "ru": "{employee}: в филиале {to_branch} до {end}"}, "info")
register_template("rotation.finished", {"uz": "Rotatsiya tugadi", "ru": "Ротация завершена"}, {"uz": "{employee}: {from_branch} filialiga qaytdi", "ru": "{employee}: вернулся в филиал {from_branch}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "rotations.read") or has(auth, "rotations.manage")


def touches(auth: AuthContext, rot: Rotation, branches: dict[int, Branch], emp: Employee | None = None) -> bool:
    """Foydalanuvchi shu rotatsiyani ko'ra oladimi: HR/auditor hammasini, mudir/koordinator o'z filiallari bilan bog'liqni, xodim o'zinikini."""
    if sees_all(auth) or rot.requested_by == auth.user.id or (emp is not None and emp.user_id == auth.user.id):
        return True
    return any(b and auth.user.id in (b.manager_user_id, b.coordinator_user_id) for b in (branches.get(rot.from_branch_id), branches.get(rot.to_branch_id)))


def period(rot: Rotation) -> str:
    return f"{rot.start_date:%d.%m.%Y} – {rot.end_date:%d.%m.%Y}"


def lead_ids(*branches: Branch | None) -> list[int]:
    return list(dict.fromkeys(u for b in branches if b for u in (b.manager_user_id, b.coordinator_user_id) if u))


async def validate_new(db: AsyncSession, emp: Employee, to_branch_id: int, start: date, end: date, today: date) -> None:
    if emp.status != "active":
        raise error(409, "employee_dismissed")
    if await db.scalar(select(Rotation.id).where(Rotation.employee_id == emp.id, Rotation.status.in_(OPEN)).limit(1)):
        raise error(409, "rotation_exists")
    if not emp.branch_id:
        raise error(400, "no_home_branch")
    if emp.branch_id == to_branch_id:
        raise error(400, "same_branch")
    if end < start:
        raise error(400, "date_range_invalid")
    if end < today:
        raise error(400, "date_in_past")
    if (end - start).days > MAX_DAYS:
        raise error(400, "period_too_long")
    if not await db.get(Branch, to_branch_id):
        raise error(400, "unknown_branch")


async def _start(db: AsyncSession, rot: Rotation, emp: Employee, moment: datetime) -> list:
    emp.branch_id = rot.to_branch_id
    rot.status, rot.started_at = "active", moment
    emp_svc.add_event(db, emp.id, "rotation_start", rot.start_date, data={"from": rot.from_branch_id, "to": rot.to_branch_id, "end": str(rot.end_date)}, note=rot.reason, actor_id=rot.decided_by)
    return await _notify_both(db, rot, emp, "rotation.started", {"end": f"{rot.end_date:%d.%m.%Y}"})


async def _finish(db: AsyncSession, rot: Rotation, emp: Employee, moment: datetime, status: str = "completed") -> list:
    """Xodim hali rotatsiya filialida bo'lsa uy filialiga qaytaradi (HR bu orada boshqa filialga o'tkazgan bo'lsa tegmaydi)."""
    if rot.status == "active" and emp.branch_id == rot.to_branch_id:
        emp.branch_id = rot.from_branch_id
    was_active = rot.status == "active"
    rot.status, rot.finished_at = status, moment
    if not was_active:
        return []
    emp_svc.add_event(db, emp.id, "rotation_end", local_date(moment), data={"from": rot.to_branch_id, "to": rot.from_branch_id}, actor_id=None)
    return await _notify_both(db, rot, emp, "rotation.finished", {})


async def _notify_both(db: AsyncSession, rot: Rotation, emp: Employee, kind: str, extra: dict) -> list:
    fb, tb = await db.get(Branch, rot.from_branch_id), await db.get(Branch, rot.to_branch_id)
    targets = list(dict.fromkeys([*([emp.user_id] if emp.user_id else []), *lead_ids(fb, tb)]))
    params = {"employee": emp.full_name, "from_branch": fb.name if fb else "—", "to_branch": tb.name if tb else "—", **extra}
    return await notify(db, targets, kind, params=params, link="/org/rotations")


async def approve(db: AsyncSession, rot: Rotation, emp: Employee, auth: AuthContext, note: str | None, moment: datetime) -> list:
    rot.status, rot.decided_by, rot.decided_at, rot.decision_note = "approved", auth.user.id, moment, note
    if rot.start_date <= local_date(moment) <= rot.end_date:
        return await _start(db, rot, emp, moment)
    return await _notify_both(db, rot, emp, "rotation.decided", {"result": "tasdiqlandi"})


async def reject(db: AsyncSession, rot: Rotation, emp: Employee, auth: AuthContext, note: str | None, moment: datetime) -> list:
    rot.status, rot.decided_by, rot.decided_at, rot.decision_note, rot.finished_at = "rejected", auth.user.id, moment, note, moment
    return await _notify_both(db, rot, emp, "rotation.decided", {"result": "rad etildi"})


async def cancel(db: AsyncSession, rot: Rotation, emp: Employee, moment: datetime) -> list:
    return await _finish(db, rot, emp, moment, status="cancelled")


async def run_due(db: AsyncSession, moment: datetime) -> list:
    """Kunlik/5 daqiqalik vazifa: boshlanishi kerak bo'lganlarni boshlaydi, muddati o'tganlarni qaytaradi."""
    today = local_date(moment)
    notes: list = []
    due_end = (await db.scalars(select(Rotation).where(Rotation.status == "active", Rotation.end_date < today).with_for_update(skip_locked=True))).all()
    for rot in due_end:
        emp = await db.get(Employee, rot.employee_id)
        if emp:
            notes += await _finish(db, rot, emp, moment)
    due_start = (await db.scalars(select(Rotation).where(Rotation.status == "approved", Rotation.start_date <= today).with_for_update(skip_locked=True))).all()
    for rot in due_start:
        emp = await db.get(Employee, rot.employee_id)
        if not emp or emp.status != "active":
            rot.status, rot.finished_at = "cancelled", moment
        elif rot.end_date < today:
            rot.status, rot.finished_at = "completed", moment  # boshlanmasdan muddati o'tib ketgan
        else:
            notes += await _start(db, rot, emp, moment)
    return notes
