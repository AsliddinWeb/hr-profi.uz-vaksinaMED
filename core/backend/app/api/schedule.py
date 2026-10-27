"""Grafik: doska (oylik jadval), xodim oyi, grafik tuzish (apply)."""

import calendar
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import get_employee
from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.employees import Employee
from app.models.org import Position
from app.models.schedule import ScheduleEntry, SchedulePattern, ShiftTemplate, WorkGroup
from app.services import schedule as svc
from app.services.audit import audit
from app.services.org import descendants, load_departments

router = APIRouter(prefix="/v1/schedule", tags=["schedule"])

MAX_BOARD_DAYS = 42
MAX_APPLY_DAYS = 366
MAX_APPLY_EMPLOYEES = 1000


def _cell(r: svc.Resolved) -> dict[str, Any]:
    return {
        "working": r.working,
        "shift_id": r.shift_id,
        "reason": r.reason,
        "explicit": r.explicit,
        "holiday": r.holiday,
    }


async def _shift_map(db: AsyncSession) -> dict[int, dict[str, Any]]:
    return {s.id: svc.shift_out(s) for s in (await db.scalars(select(ShiftTemplate))).all()}


def _filter_employees(stmt, *, q, department_ids, branch_id, group_cond, employee_ids=None):
    stmt = stmt.where(Employee.status == "active")
    if employee_ids is not None:
        stmt = stmt.where(Employee.id.in_(employee_ids))
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    if department_ids:
        stmt = stmt.where(Employee.department_id.in_(department_ids))
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    if group_cond is not None:
        stmt = stmt.where(group_cond)
    return stmt


async def _dept_ids(db: AsyncSession, department_id: int | None) -> set[int]:
    if not department_id:
        return set()
    return {department_id} | descendants(await load_departments(db), department_id)


@router.get("/board")
async def board(
    start: date,
    end: date,
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    """Oylik/haftalik jadval: har xodim uchun kunlar bo'yicha aniqlangan smena."""
    if end < start or (end - start).days + 1 > MAX_BOARD_DAYS:
        raise error(400, "range_invalid", max_days=MAX_BOARD_DAYS)
    stmt = _filter_employees(
        select(Employee), q=q, department_ids=await _dept_ids(db, department_id),
        branch_id=branch_id, group_cond=(await svc.group_condition(db, group_id) if group_id else None),
    )  # fmt: skip
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    employees = (
        await db.scalars(stmt.order_by(Employee.full_name, Employee.id).offset((page - 1) * size).limit(size))
    ).all()

    ctx = await svc.load_context(db, start, end)
    resolved = await svc.resolve_range(db, list(employees), start, end)
    positions = {
        p.id: p.name
        for p in (await db.scalars(select(Position).where(Position.id.in_({e.position_id for e in employees if e.position_id})))).all()
    } if employees else {}
    groups = ctx.groups

    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "days": [
            {
                "date": d,
                "weekday": d.weekday(),
                "holiday": ({"name": ctx.holidays[d].name, "kind": ctx.holidays[d].kind} if d in ctx.holidays else None),
            }
            for d in svc.daterange(start, end)
        ],
        "shifts": await _shift_map(db),
        "rows": [
            {
                "employee": {
                    "id": e.id,
                    "employee_no": e.employee_no,
                    "full_name": e.full_name,
                    "position": positions.get(e.position_id),
                    "group": (groups[e.work_group_id].name if e.work_group_id in groups else (ctx.default_group.name if ctx.default_group else None)),
                },
                "cells": [_cell(r) for r in resolved[e.id]],
            }
            for e in employees
        ],
    }


@router.get("/employees/{employee_id}")
async def employee_month(
    employee_id: int,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    emp = await get_employee(db, employee_id)
    year, mon = int(month[:4]), int(month[5:])
    start = date(year, mon, 1)
    end = date(year, mon, calendar.monthrange(year, mon)[1])
    resolved = (await svc.resolve_range(db, [emp], start, end))[emp.id]
    group = await db.get(WorkGroup, emp.work_group_id) if emp.work_group_id else None
    if group is None:
        group = (await svc.load_context(db, start, end)).default_group
    return {
        "employee": {"id": emp.id, "employee_no": emp.employee_no, "full_name": emp.full_name, "status": emp.status},
        "group": {"id": group.id, "name": group.name, "attendance_required": group.attendance_required} if group else None,
        "shifts": await _shift_map(db),
        "days": [{"date": r.date, "weekday": r.date.weekday(), **_cell(r)} for r in resolved],
    }


# --- Grafik tuzish -------------------------------------------------------------------


class ApplyIn(BaseModel):
    # Kimga (kamida bittasi)
    employee_ids: list[int] | None = Field(default=None, max_length=MAX_APPLY_EMPLOYEES)
    group_id: int | None = None
    department_id: int | None = None
    branch_id: int | None = None
    # Qachon
    start: date
    end: date
    weekdays: list[int] = [0, 1, 2, 3, 4, 5, 6]
    # Nima
    mode: str = Field(pattern="^(shift|off|pattern|clear)$")
    shift_id: int | None = None
    pattern_id: int | None = None
    start_index: int = Field(default=0, ge=0, le=59)
    stagger: bool = False
    skip_holidays: bool = False
    overwrite: bool = True
    dry_run: bool = True

    @model_validator(mode="after")
    def _check(self):
        if not any([self.employee_ids, self.group_id, self.department_id, self.branch_id]):
            raise ValueError("no_target")
        if self.end < self.start or (self.end - self.start).days + 1 > MAX_APPLY_DAYS:
            raise ValueError("range_invalid")
        if any(d < 0 or d > 6 for d in self.weekdays) or not self.weekdays:
            raise ValueError("weekday_invalid")
        if self.mode == "shift" and self.shift_id is None:
            raise ValueError("shift_required")
        if self.mode == "pattern" and self.pattern_id is None:
            raise ValueError("pattern_required")
        return self


@router.post("/apply")
async def apply(
    body: ApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.edit")),
):
    """Tanlangan xodimlarga sana oralig'ida grafik yozadi (yoki tozalaydi). `dry_run` faqat hisoblaydi."""
    shift = None
    if body.mode == "shift":
        shift = await db.get(ShiftTemplate, body.shift_id)
        if not shift or not shift.is_active:
            raise error(400, "unknown_shift")
    pattern = None
    if body.mode == "pattern":
        pattern = await db.get(SchedulePattern, body.pattern_id)
        if not pattern or not pattern.is_active:
            raise error(400, "unknown_pattern")

    stmt = select(Employee).where(Employee.status == "active")
    conds = []
    if body.employee_ids:
        conds.append(Employee.id.in_(body.employee_ids))
    if body.group_id:
        conds.append(await svc.group_condition(db, body.group_id))
    if body.department_id:
        conds.append(Employee.department_id.in_(await _dept_ids(db, body.department_id)))
    if body.branch_id:
        conds.append(Employee.branch_id == body.branch_id)
    # Bir nechta mezon berilsa HAMMASI birga (kesishma) qo'llanadi
    for c in conds:
        stmt = stmt.where(c)
    employees = (await db.scalars(stmt.order_by(Employee.full_name, Employee.id))).all()
    if len(employees) > MAX_APPLY_EMPLOYEES:
        raise error(400, "too_many_employees", max=MAX_APPLY_EMPLOYEES)
    if not employees:
        raise error(400, "no_employees")

    ctx = await svc.load_context(db, body.start, body.end)
    ids = [e.id for e in employees]
    existing = {
        (en.employee_id, en.date): en
        for en in (
            await db.scalars(
                select(ScheduleEntry).where(
                    ScheduleEntry.employee_id.in_(ids), ScheduleEntry.date.between(body.start, body.end)
                )
            )
        ).all()
    }

    wanted: list[tuple[int, date, int | None, str]] = []  # (employee, date, shift_id, source)
    to_delete: list[tuple[int, date]] = []
    skipped = 0
    cycle = pattern.cycle if pattern else []
    for n, emp in enumerate(employees):
        offset = body.start_index + (n if body.stagger else 0)
        for i, day in enumerate(svc.daterange(body.start, body.end)):
            if day.weekday() not in body.weekdays:
                continue
            if body.skip_holidays and day in ctx.holidays and ctx.holidays[day].kind == "holiday":
                continue
            has = (emp.id, day) in existing
            if body.mode == "clear":
                if has:
                    to_delete.append((emp.id, day))
                continue
            if has and not body.overwrite:
                skipped += 1
                continue
            if body.mode == "shift":
                wanted.append((emp.id, day, shift.id, "bulk"))  # type: ignore[union-attr]
            elif body.mode == "off":
                wanted.append((emp.id, day, None, "bulk"))
            else:
                slot = cycle[(offset + i) % len(cycle)]
                wanted.append((emp.id, day, slot.get("shift_id"), "pattern"))

    to_update = sum(1 for e, d, _s, _src in wanted if (e, d) in existing)
    result = {
        "employees": len(employees),
        "to_create": len(wanted) - to_update,
        "to_update": to_update,
        "to_delete": len(to_delete),
        "skipped": skipped,
        "applied": False,
    }
    if body.dry_run:
        return result

    for chunk_start in range(0, len(wanted), 2000):
        rows = [
            {"employee_id": e, "date": d, "shift_id": s, "source": src, "created_by": auth.user.id}
            for e, d, s, src in wanted[chunk_start : chunk_start + 2000]
        ]
        ins = pg_insert(ScheduleEntry).values(rows)
        await db.execute(
            ins.on_conflict_do_update(
                constraint="uq_schedule_entries_employee_date",
                set_={"shift_id": ins.excluded.shift_id, "source": ins.excluded.source, "created_by": ins.excluded.created_by},
            )
        )
    if to_delete:
        for e_id in {e for e, _ in to_delete}:
            days = [d for e, d in to_delete if e == e_id]
            await db.execute(delete(ScheduleEntry).where(ScheduleEntry.employee_id == e_id, ScheduleEntry.date.in_(days)))
    await audit(
        db, request, "schedule.apply", actor=auth.user, entity="schedule",
        data={"mode": body.mode, "start": str(body.start), "end": str(body.end), **{k: v for k, v in result.items() if k != "applied"}},
    )  # fmt: skip
    await db.commit()
    result["applied"] = True
    return result


class DaysIn(BaseModel):
    dates: list[date] = Field(min_length=1, max_length=62)
    mode: str = Field(pattern="^(shift|off|clear)$")
    shift_id: int | None = None


@router.post("/employees/{employee_id}/days")
async def set_days(
    employee_id: int,
    body: DaysIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.edit")),
):
    """Bitta xodimning tanlangan kunlariga smena/dam belgilaydi yoki tozalaydi (guruh qoidasiga qaytadi)."""
    emp = await get_employee(db, employee_id)
    if emp.status != "active":
        raise error(409, "employee_dismissed")
    days = sorted(set(body.dates))
    if body.mode == "shift":
        shift = await db.get(ShiftTemplate, body.shift_id) if body.shift_id else None
        if not shift or not shift.is_active:
            raise error(400, "unknown_shift")
    if body.mode == "clear":
        await db.execute(delete(ScheduleEntry).where(ScheduleEntry.employee_id == emp.id, ScheduleEntry.date.in_(days)))
    else:
        sid = body.shift_id if body.mode == "shift" else None
        ins = pg_insert(ScheduleEntry).values(
            [{"employee_id": emp.id, "date": d, "shift_id": sid, "source": "manual", "created_by": auth.user.id} for d in days]
        )
        await db.execute(
            ins.on_conflict_do_update(
                constraint="uq_schedule_entries_employee_date",
                set_={"shift_id": ins.excluded.shift_id, "source": ins.excluded.source, "created_by": ins.excluded.created_by},
            )
        )
    await audit(db, request, "schedule.days", actor=auth.user, entity="employee", entity_id=emp.id,
                data={"mode": body.mode, "dates": len(days), "shift_id": body.shift_id})  # fmt: skip
    await db.commit()
    return {"updated": len(days)}

