"""Resepshin: mehmon qaydi (oldindan yozilgan -> keldi -> ketdi), kelmaganlarni yopish, hisobot."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch
from app.models.reception import Visit
from app.rbac import matches
from app.services.notifications import notify, register_template
from app.timeutil import local_date, tz

PURPOSES = ("meeting", "interview", "delivery", "service", "other")
NO_SHOW_HOURS = 4

register_template("reception.arrived", {"uz": "Mehmoningiz keldi", "ru": "Ваш гость пришёл"}, {"uz": "{visitor} resepshinda", "ru": "{visitor} на ресепшн"}, "info")
register_template("reception.expected", {"uz": "Sizga mehmon ro'yxatga olindi", "ru": "К вам зарегистрирован гость"}, {"uz": "{visitor}", "ru": "{visitor}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def desk(auth: AuthContext) -> bool:
    return has(auth, "reception.desk")


def viewer(auth: AuthContext) -> bool:
    return desk(auth) or has(auth, "reception.read")


def can_view(auth: AuthContext, v: Visit) -> bool:
    return viewer(auth) or v.registered_by == auth.user.id


def can_edit(auth: AuthContext, v: Visit) -> bool:
    if v.status == "expected":
        return desk(auth) or v.registered_by == auth.user.id
    return v.status == "arrived" and desk(auth)


def can_cancel(auth: AuthContext, v: Visit) -> bool:
    return v.status == "expected" and (desk(auth) or v.registered_by == auth.user.id)


async def host_user(db: AsyncSession, v: Visit) -> int | None:
    if not v.host_id:
        return None
    emp = await db.get(Employee, v.host_id)
    return emp.user_id if emp else None


async def register(db: AsyncSession, auth: AuthContext, data: dict[str, Any], moment: datetime):
    """Oldindan yozish (expected_at bilan) yoki resepshinda bevosita (arrive=True) ro'yxatga olish."""
    arrive = bool(data.pop("arrive", False))
    if arrive and not desk(auth):
        raise error(403, "forbidden")
    v = Visit(**data, status="expected", registered_by=auth.user.id)
    db.add(v)
    await db.flush()
    notes: list = []
    if arrive:
        notes += await mark_arrived(db, v, auth, moment, force=True)
    else:
        uid = await host_user(db, v)
        if uid and uid != auth.user.id:
            notes += await notify(db, [uid], "reception.expected", link=f"/reception/{v.id}", params={"visitor": v.visitor_name})
    return v, notes


async def mark_arrived(db: AsyncSession, v: Visit, auth: AuthContext, moment: datetime, badge_no: str | None = None, force: bool = False):
    if not force and not desk(auth):
        raise error(403, "forbidden")
    if v.status != "expected":
        raise error(409, "invalid_transition")
    v.status, v.arrived_at, v.checked_in_by = "arrived", moment, auth.user.id
    if badge_no:
        v.badge_no = badge_no.strip() or v.badge_no
    uid = await host_user(db, v)
    return await notify(db, [uid] if uid else [], "reception.arrived", link=f"/reception/{v.id}", params={"visitor": v.visitor_name})


async def mark_left(db: AsyncSession, v: Visit, auth: AuthContext, moment: datetime):
    if not desk(auth):
        raise error(403, "forbidden")
    if v.status != "arrived":
        raise error(409, "invalid_transition")
    v.status, v.left_at, v.checked_out_by = "left", moment, auth.user.id


async def cancel(db: AsyncSession, v: Visit, auth: AuthContext):
    if not can_cancel(auth, v):
        raise error(409 if v.status != "expected" else 403, "invalid_transition" if v.status != "expected" else "forbidden")
    v.status = "cancelled"


async def watch(db: AsyncSession, moment: datetime) -> int:
    """Kutilgan vaqtdan 4 soat o'tgan, kelmagan mehmonlar -> no_show."""
    rows = (await db.scalars(select(Visit).where(Visit.status == "expected", Visit.expected_at.is_not(None), Visit.expected_at <= moment - timedelta(hours=NO_SHOW_HOURS)))).all()
    for v in rows:
        v.status = "no_show"
    return len(rows)


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


def visit_out(v: Visit, hosts: dict[int, str], branches: dict[int, str], users: dict[int, str]) -> dict[str, Any]:
    inside = v.status == "arrived"
    return {
        "id": v.id, "visitor_name": v.visitor_name, "visitor_phone": v.visitor_phone, "company": v.company, "purpose": v.purpose, "status": v.status,
        "host": {"id": v.host_id, "name": hosts.get(v.host_id or 0)} if v.host_id else None,
        "branch": {"id": v.branch_id, "name": branches.get(v.branch_id or 0)} if v.branch_id else None,
        "expected_at": v.expected_at, "arrived_at": v.arrived_at, "left_at": v.left_at, "inside": inside,
        "badge_no": v.badge_no, "doc_info": v.doc_info, "vehicle_plate": v.vehicle_plate, "note": v.note,
        "registered_by": users.get(v.registered_by or 0), "checked_in_by": users.get(v.checked_in_by or 0), "checked_out_by": users.get(v.checked_out_by or 0),
        "created_at": v.created_at,
    }  # fmt: skip


async def lookups(db: AsyncSession, rows: list[Visit]):
    host_ids = {v.host_id for v in rows if v.host_id}
    hosts = {e.id: e.full_name for e in (await db.scalars(select(Employee).where(Employee.id.in_(host_ids)))).all()} if host_ids else {}
    branches = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    users = await names(db, {x for v in rows for x in (v.registered_by, v.checked_in_by, v.checked_out_by)})
    return hosts, branches, users


async def report(db: AsyncSession, start: date, end: date, branch_id: int | None) -> dict[str, Any]:
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    V = Visit
    base = [V.arrived_at >= s_dt, V.arrived_at < e_dt] + ([V.branch_id == branch_id] if branch_id else [])
    total = await db.scalar(select(func.count()).select_from(V).where(*base)) or 0
    avg_s = await db.scalar(select(func.avg(func.extract("epoch", V.left_at - V.arrived_at))).where(*base, V.left_at.is_not(None)))
    by_purpose = dict((await db.execute(select(V.purpose, func.count()).where(*base).group_by(V.purpose))).all())
    inside = await db.scalar(select(func.count()).select_from(V).where(V.status == "arrived")) or 0
    no_show = await db.scalar(select(func.count()).select_from(V).where(V.status == "no_show", V.expected_at >= s_dt, V.expected_at < e_dt)) or 0
    day = func.date(func.timezone(literal_column("'Asia/Tashkent'"), V.arrived_at))
    days = dict((await db.execute(select(day, func.count()).where(*base).group_by(day))).all())
    trend, d = [], start
    while d <= end:
        trend.append({"date": d, "count": days.get(d, 0)})
        d += timedelta(days=1)
    host_rows = (await db.execute(select(V.host_id, func.count()).where(*base, V.host_id.is_not(None)).group_by(V.host_id).order_by(func.count().desc()).limit(10))).all()
    hosts = {e.id: e.full_name for e in (await db.scalars(select(Employee).where(Employee.id.in_([r[0] for r in host_rows])))).all()} if host_rows else {}
    return {
        "start": start, "end": end, "total": total, "inside_now": inside, "no_show": no_show,
        "avg_minutes": round(avg_s / 60, 1) if avg_s else None,
        "by_purpose": {p: by_purpose.get(p, 0) for p in PURPOSES}, "trend": trend,
        "top_hosts": [{"name": hosts.get(r[0]), "count": r[1]} for r in host_rows],
    }  # fmt: skip


__all__ = ["local_date"]
