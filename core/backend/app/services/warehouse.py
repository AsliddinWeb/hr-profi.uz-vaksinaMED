"""Omborxona: erkin grafikli smena oynasi, kim ishda (holat), yetishmovchilik va nazorat hisobi."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.employees import Employee
from app.models.schedule import ShiftTemplate, WorkGroup
from app.models.warehouse import Warehouse
from app.rbac import matches
from app.services import schedule as sched
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, localize

register_template("warehouse.gap", {"uz": "Omborda xodim yetishmayapti", "ru": "На складе не хватает сотрудников"}, {"uz": "{warehouse}: ishda {on_duty}, kerak {need}", "ru": "{warehouse}: на смене {on_duty}, нужно {need}"}, "danger")
register_template("warehouse.long_shift", {"uz": "Omborda smena juda uzoq", "ru": "Слишком долгая смена на складе"}, {"uz": "{employee}: {hours} soatdan beri ishda", "ru": "{employee}: на смене уже {hours} ч"}, "warning")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def window_for(shift: ShiftTemplate, moment: datetime) -> tuple[date, datetime, datetime]:
    """`moment` ga tegishli smena oynasi: (smena sanasi, boshlanishi, tugashi). Oyna tugagan, yangisi hali boshlanmagan bo'lsa, oxirgisi."""
    today = local_date(moment)
    for d in (today, today - timedelta(days=1)):
        s, e = sched.shift_window(shift, d)
        s, e = localize(s), localize(e)
        if s <= moment < e:
            return d, s, e
    s, e = sched.shift_window(shift, today)
    ls, le = localize(s), localize(e)
    if moment < ls:  # bugungi oyna hali boshlanmagan: oxirgi tugagan oyna kecha
        ys, ye = sched.shift_window(shift, today - timedelta(days=1))
        return today - timedelta(days=1), localize(ys), localize(ye)
    return today, ls, le


@dataclass
class Interval:
    start: datetime
    end: datetime


def coverage(intervals: list[Interval], w_start: datetime, w_end: datetime, min_on_duty: int) -> dict[str, int]:
    """Oyna ichida: eng ko'p/eng kam bir vaqtdagi xodimlar va yetishmovchilik (daqiqa). Oraliqlar oynaga kesiladi."""
    cuts = sorted({w_start, w_end, *[min(max(i.start, w_start), w_end) for i in intervals], *[min(max(i.end, w_start), w_end) for i in intervals]})
    peak = 0
    low = None
    gap = 0
    for a, b in zip(cuts, cuts[1:], strict=False):
        if b <= a:
            continue
        n = sum(1 for i in intervals if i.start <= a and i.end >= b)
        peak = max(peak, n)
        low = n if low is None else min(low, n)
        if n < min_on_duty:
            gap += int((b - a).total_seconds() // 60)
    return {"peak": peak, "lowest": low or 0, "gap_minutes": gap}


async def staff_of(db: AsyncSession, wh: Warehouse) -> list[Employee]:
    stmt = select(Employee).where(Employee.work_group_id == wh.work_group_id, Employee.status == "active").order_by(Employee.full_name, Employee.id)
    return list((await db.scalars(stmt)).all())


async def shift_of(db: AsyncSession, wh: Warehouse) -> tuple[WorkGroup, ShiftTemplate | None]:
    g = await db.get(WorkGroup, wh.work_group_id)
    sh = await db.get(ShiftTemplate, g.default_shift_id) if g and g.default_shift_id else None
    return g, sh  # type: ignore[return-value]


def minutes_so_far(rec, shift: ShiftTemplate | None, moment: datetime) -> int:
    span = int((moment - rec.check_in_at).total_seconds() // 60)
    brk = shift.break_minutes if shift else 0
    return max(span - brk if brk and span > brk else span, 0)


async def status(db: AsyncSession, wh: Warehouse, moment: datetime) -> dict[str, Any]:
    """Hozirgi holat: kim ishda, qancha ishlagan, minimumga yetdimi, yetishmovchilik bormi."""
    from app.api.attendance import _rows  # tabel bilan bir manba

    g, shift = await shift_of(db, wh)
    staff = await staff_of(db, wh)
    out: dict[str, Any] = {"warehouse": {"id": wh.id, "name": wh.name, "min_on_duty": wh.min_on_duty, "max_shift_hours": wh.max_shift_hours, "is_active": wh.is_active}, "staff": [], "in_window": False, "window": None}
    if shift is None:
        out.update(on_duty=0, expected=0, gap=False, long_open=[], no_shift=True)
        return out
    wdate, w_start, w_end = window_for(shift, moment)
    in_window = w_start <= moment < w_end
    rows = await _rows(db, staff, wdate, wdate) if staff else {}
    min_work = shift.min_work_minutes or 0
    items, on_duty, expected, long_open = [], 0, 0, []
    for e in staff:
        d = rows[e.id][0]
        rec, st = d["record"], d["status"]
        if d["cell"].working:
            expected += 1
        item: dict[str, Any] = {"employee": {"id": e.id, "name": e.full_name, "employee_no": e.employee_no}, "status": st, "scheduled": bool(d["cell"].working), "check_in_at": None, "check_out_at": None, "worked_minutes": 0, "on_duty": False, "met_min": None, "remaining_minutes": None}
        if rec:
            item["check_in_at"], item["check_out_at"] = rec.check_in_at, rec.check_out_at
            if rec.check_out_at is None:
                m = minutes_so_far(rec, shift, moment)
                item.update(on_duty=True, worked_minutes=m, met_min=m >= min_work if min_work else None, remaining_minutes=max(min_work - m, 0) if min_work else None)
                on_duty += 1
                if m > wh.max_shift_hours * 60:
                    long_open.append({"employee_id": e.id, "name": e.full_name, "record_id": rec.id, "hours": round(m / 60, 1)})
            else:
                item.update(worked_minutes=rec.worked_minutes, met_min=rec.worked_minutes >= min_work if min_work else None)
        items.append(item)
    out.update(
        staff=items, on_duty=on_duty, expected=expected, in_window=in_window, long_open=long_open, no_shift=False,
        gap=bool(in_window and wh.is_active and on_duty < wh.min_on_duty), window={"date": wdate, "start": w_start, "end": w_end, "min_work_minutes": min_work, "kind": shift.kind, "shift": shift.name},
    )  # fmt: skip
    return out


async def control(db: AsyncSession, wh: Warehouse, start: date, end: date, moment: datetime) -> dict[str, Any]:
    """Nazorat hisoboti: xodimlar bo'yicha ishlagan kunlar/soatlar/minimumdan kam kunlar va kunlar bo'yicha yetishmovchilik."""
    from app.api.attendance import _rows
    from app.models.attendance import AttendanceRecord

    g, shift = await shift_of(db, wh)
    staff = await staff_of(db, wh)
    if shift is None:
        return {"start": start, "end": end, "employees": [], "days": [], "totals": {}, "no_shift": True}
    min_work = shift.min_work_minutes or 0
    rows = await _rows(db, staff, start, end) if staff else {}
    ids = [e.id for e in staff]
    recs: list[AttendanceRecord] = []
    if ids:
        recs = list((await db.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id.in_(ids), AttendanceRecord.work_date.between(start, end)))).all())
    emp_rows = []
    for e in staff:
        ds = rows[e.id]
        recd = [d["record"] for d in ds if d["record"] is not None]
        closed = [r for r in recd if r.check_out_at is not None]
        total = sum(r.worked_minutes for r in closed)
        emp_rows.append({
            "employee": {"id": e.id, "name": e.full_name, "employee_no": e.employee_no}, "days": len(recd), "scheduled": sum(1 for d in ds if d["cell"].working),
            "worked_minutes": total, "avg_minutes": round(total / len(closed)) if closed else 0, "longest_minutes": max((r.worked_minutes for r in closed), default=0),
            "below_min": sum(1 for d in ds if d["status"] == "incomplete"), "absent": sum(1 for d in ds if d["status"] == "absent"), "no_checkout": sum(1 for d in ds if d["status"] == "no_checkout"),
            "leave": sum(1 for d in ds if d["status"] == "leave"),
        })  # fmt: skip
    by_day: dict[date, list[AttendanceRecord]] = {}
    for r in recs:
        by_day.setdefault(r.work_date, []).append(r)
    days = []
    d = start
    while d <= end:
        w_start, w_end = (localize(x) for x in sched.shift_window(shift, d))
        if w_start > moment:
            break
        until = min(w_end, moment)
        ivs = [Interval(r.check_in_at, r.check_out_at or until) for r in by_day.get(d, [])]
        cov = coverage(ivs, w_start, until, wh.min_on_duty)
        days.append({"date": d, "staff_in": len(by_day.get(d, [])), **cov, "window_minutes": int((until - w_start).total_seconds() // 60), "open": sum(1 for r in by_day.get(d, []) if r.check_out_at is None and w_end <= moment)})
        d += timedelta(days=1)
    totals = {
        "worked_hours": round(sum(r["worked_minutes"] for r in emp_rows) / 60, 1), "below_min": sum(r["below_min"] for r in emp_rows), "absent": sum(r["absent"] for r in emp_rows),
        "gap_minutes": sum(x["gap_minutes"] for x in days), "gap_days": sum(1 for x in days if x["gap_minutes"] > 0), "min_work_minutes": min_work,
    }  # fmt: skip
    return {"start": start, "end": end, "employees": emp_rows, "days": days, "totals": totals, "no_shift": False}


async def watch(db: AsyncSession, moment: datetime) -> tuple[int, list]:
    """Har 10 daqiqada: yetishmovchilik grace dan oshsa va juda uzoq smenalar uchun bir martadan xabar."""
    notes: list = []
    sent = 0
    managers = await users_with_permission(db, "warehouse.manage")
    for wh in (await db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True)))).all():
        st = await status(db, wh, moment)
        if st.get("no_shift"):
            continue
        if st["gap"]:
            if wh.gap_since is None:
                wh.gap_since = moment
            elif not wh.gap_notified and moment - wh.gap_since >= timedelta(minutes=wh.alert_grace_min):
                wh.gap_notified = True
                sent += 1
                notes += await notify(db, managers, "warehouse.gap", link=f"/warehouse/{wh.id}", params={"warehouse": wh.name, "on_duty": st["on_duty"], "need": wh.min_on_duty})
        else:
            wh.gap_since, wh.gap_notified = None, False
        alerted = set(wh.alerted_records or [])
        for lo in st["long_open"]:
            if lo["record_id"] not in alerted:
                alerted.add(lo["record_id"])
                sent += 1
                notes += await notify(db, managers, "warehouse.long_shift", link=f"/warehouse/{wh.id}", params={"employee": lo["name"], "hours": lo["hours"]})
        wh.alerted_records = sorted(alerted)[-200:]
    return sent, notes

