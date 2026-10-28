"""«Javob olish holati»: oylik hisobot (KPI, kalendar, xodimlar reytingi) va boyitilgan so'rovlar ro'yxati.

Bir xil ma'lumot ekran, Excel va PDF uchun ishlatiladi (`collect` -> `summarize`)."""

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.answers import LeaveEvent, LeaveRequest
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch
from app.models.schedule import ScheduleEntry, ShiftTemplate, WorkGroup
from app.services import answers as svc
from app.timeutil import tz

STATUSES = ("pending_coordinator", "pending_hr", "approved", "rejected", "cancelled")
MAX_ROWS = 3000
DAY_MINUTES = 8 * 60


def month_range(month: str) -> tuple[date, date]:
    y, m = int(month[:4]), int(month[5:])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def duration(r: LeaveRequest) -> tuple[int, int | None]:
    """(kunlar soni, soatlik bo'lsa daqiqalar)."""
    if r.kind == "hourly" and r.start_time and r.end_time:
        return 1, max(0, svc.minutes(r.end_time) - svc.minutes(r.start_time))
    return (r.end_date - r.start_date).days + 1, None


def shift_text(s: ShiftTemplate | None) -> str | None:
    return f"{s.start_time:%H:%M}–{s.end_time:%H:%M}" if s and s.start_time and s.end_time else None


async def collect(db: AsyncSession, auth: AuthContext, month: str, *, branch_id: int | None = None, q: str | None = None) -> list[dict[str, Any]]:
    """Oy bilan kesishadigan so'rovlar (barcha holatda), filial/qidiruv bo'yicha; foydalanuvchi ko'ra oladiganlari."""
    start, end = month_range(month)
    stmt = (
        select(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
        .order_by(LeaveRequest.submitted_at.desc())
        .limit(MAX_ROWS)
    )
    clause = svc.visible_clause(auth, Employee.user_id)
    if clause is not None:
        stmt = stmt.where(clause)
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    req_ids = [r.id for r, _ in rows]
    emp_ids = {e.id for _, e in rows}
    branches = {b.id: b for b in (await db.scalars(select(Branch))).all()}
    groups = {g.id: g for g in (await db.scalars(select(WorkGroup))).all()}
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    entries = {(en.employee_id, en.date): en.shift_id for en in (await db.scalars(select(ScheduleEntry).where(ScheduleEntry.employee_id.in_(emp_ids), ScheduleEntry.date >= start, ScheduleEntry.date <= end))).all()}
    events: dict[int, list[LeaveEvent]] = defaultdict(list)
    for ev in (await db.scalars(select(LeaveEvent).where(LeaveEvent.request_id.in_(req_ids)).order_by(LeaveEvent.created_at, LeaveEvent.id))).all():
        events[ev.request_id].append(ev)
    user_ids = {u for r, _ in rows for u in (r.coordinator_user_id, r.decided_by) if u} | {b.coordinator_user_id for b in branches.values() if b.coordinator_user_id} | {ev.actor_id for evs in events.values() for ev in evs if ev.actor_id}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()} if user_ids else {}
    out: list[dict[str, Any]] = []
    for r, e in rows:
        branch = branches.get(e.branch_id or 0)
        shift_id = entries[(e.id, r.start_date)] if (e.id, r.start_date) in entries else (groups[e.work_group_id].default_shift_id if e.work_group_id in groups else None)
        days, mins = duration(r)
        coord_id = r.coordinator_user_id or (branch.coordinator_user_id if branch else None)
        out.append({
            **svc.request_out(r, e),
            "branch": {"id": branch.id, "name": branch.name} if branch else None,
            "shift": shift_text(shifts.get(shift_id or 0)),
            "coordinator": names.get(coord_id or 0),
            "days": days, "minutes": mins,
            "decided_by": names.get(r.decided_by or 0),
            "events": [{"action": ev.action, "actor": names.get(ev.actor_id or 0), "level": ev.level, "note": ev.note, "at": ev.created_at} for ev in events.get(r.id, [])],
        })  # fmt: skip
    return out


def summarize(items: list[dict[str, Any]], month: str) -> dict[str, Any]:
    """KPI (barcha holat bo'yicha), kunlik soni (faol so'rovlar), xodimlar reytingi (tasdiqlanganlar) va filiallar ro'yxati."""
    start, end = month_range(month)
    kpis = {"total": len(items), "people": len({i["employee"]["id"] for i in items}), **{s: 0 for s in STATUSES}}
    days: dict[date, int] = defaultdict(int)
    people: dict[int, dict[str, Any]] = {}
    for it in items:
        kpis[it["status"]] += 1
        if it["status"] in ("approved", "pending_coordinator", "pending_hr"):
            d = max(it["start_date"], start)
            while d <= min(it["end_date"], end):
                days[d] += 1
                d += timedelta(days=1)
        if it["status"] == "approved":
            p = people.setdefault(it["employee"]["id"], {"employee": it["employee"], "branch": it["branch"], "count": 0, "day_requests": 0, "days": 0, "hourly": 0, "hourly_minutes": 0})
            p["count"] += 1
            if it["minutes"] is None:
                p["day_requests"] += 1
                p["days"] += it["days"]
            else:
                p["hourly"] += 1
                p["hourly_minutes"] += it["minutes"]
    branches = {i["branch"]["id"]: i["branch"]["name"] for i in items if i["branch"]}
    return {
        "month": month, "start": start, "end": end, "kpis": kpis,
        "days": {d.isoformat(): n for d, n in sorted(days.items())},
        "people": sorted(people.values(), key=lambda p: (-p["count"], p["employee"]["full_name"])),
        "branches": [{"id": k, "name": v} for k, v in sorted(branches.items(), key=lambda kv: kv[1])],
    }  # fmt: skip


def filter_status(items: list[dict[str, Any]], status: str | None) -> list[dict[str, Any]]:
    if not status or status == "all":
        return items
    if status == "pending":
        return [i for i in items if i["status"] in svc.PENDING]
    return [i for i in items if i["status"] == status]


def local_dt(moment: datetime | None) -> datetime | None:
    return moment.astimezone(tz()) if moment else None


async def bot_overview(db: AsyncSession, auth: AuthContext, today: date, days: int = 30, ahead: int = 14) -> dict[str, Any]:
    """Bot uchun: jami filial soni va filial bo'yicha (tasdiqlangan/kutilayotgan) so'rovlar, necha kun oldin/keyin ekani bilan."""
    stmt = (
        select(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(LeaveRequest.status.in_(("approved", *svc.PENDING)), LeaveRequest.end_date >= today - timedelta(days=days), LeaveRequest.start_date <= today + timedelta(days=ahead))
        .order_by(LeaveRequest.start_date.desc())
        .limit(MAX_ROWS)
    )
    clause = svc.visible_clause(auth, Employee.user_id)
    if clause is not None:
        stmt = stmt.where(clause)
    rows = (await db.execute(stmt)).all()
    all_branches = list((await db.scalars(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number, Branch.name))).all())
    see_all = svc.has(auth, "answers.read") or svc.has(auth, "answers.manage")
    mine = all_branches if see_all else [b for b in all_branches if b.coordinator_user_id == auth.user.id]
    by_branch = {b.id: b for b in all_branches}
    groups: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for r, e in rows:
        delta = (today - r.start_date).days
        groups[e.branch_id].append({
            "employee": e.full_name, "status": r.status, "kind": r.kind, "start_date": r.start_date, "end_date": r.end_date,
            "start_time": r.start_time.strftime("%H:%M") if r.start_time else None, "end_time": r.end_time.strftime("%H:%M") if r.end_time else None,
            "ongoing": r.start_date <= today <= r.end_date, "days_ago": delta,
        })  # fmt: skip
    branches = [{"name": (by_branch[k].name if k in by_branch else "—"), "items": v} for k, v in sorted(groups.items(), key=lambda kv: (by_branch[kv[0]].number or 0) if kv[0] in by_branch else 10**9)]
    return {"total_branches": len(mine), "with_leave": len(groups), "requests": len(rows), "branches": branches}
