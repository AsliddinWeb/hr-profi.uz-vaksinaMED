"""Xodim segmentlari (har kompaniya o'zi qo'shadi/o'zgartiradi) va segment bo'yicha davomat dashboardi; kompaniya sozlamalari."""

from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth, require_any
from app.models.attendance import AttendanceRecord
from app.models.company import CompanySetting, EmployeeSegment
from app.models.employees import Employee
from app.models.org import Department, Position
from app.services import company as svc
from app.services.audit import audit
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/segments", tags=["segments"])
settings_router = APIRouter(prefix="/v1/company-settings", tags=["segments"])

Manage = require_any("org.manage")


def _out(s: EmployeeSegment, count: int | None = None) -> dict[str, Any]:
    return {"id": s.id, "name": s.name, "description": s.description, "scope": s.scope, "department_ids": s.department_ids or [], "position_ids": s.position_ids or [],
            "color": s.color, "sort_order": s.sort_order, "is_active": s.is_active, "employees": count}  # fmt: skip


async def _count(db: AsyncSession, s: EmployeeSegment) -> int:
    stmt = svc.apply_segment(select(func.count()).select_from(Employee).where(Employee.status == "active"), s)
    return await db.scalar(stmt) or 0


@router.get("")
async def list_segments(all: bool = False, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(get_auth)):  # noqa: A002
    return [_out(s, await _count(db, s)) for s in await svc.segments(db, active_only=not all)]


class SegmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    scope: str = Field(default="all", pattern="^(all|office|branch)$")
    department_ids: list[int] = Field(default_factory=list, max_length=500)
    position_ids: list[int] = Field(default_factory=list, max_length=500)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    sort_order: int = 0
    is_active: bool = True


@router.post("", status_code=201)
async def create(body: SegmentIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = EmployeeSegment(**body.model_dump())
    db.add(s)
    await db.flush()
    await audit(db, request, "segment.create", actor=auth.user, entity="segment", entity_id=s.id, data={"name": s.name})
    await db.commit()
    return _out(s, await _count(db, s))


@router.put("/{sid}")
async def update(sid: int, body: SegmentIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = await db.get(EmployeeSegment, sid)
    if not s:
        raise error(404, "not_found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.updated_at = now()
    await audit(db, request, "segment.update", actor=auth.user, entity="segment", entity_id=s.id)
    await db.commit()
    return _out(s, await _count(db, s))


@router.delete("/{sid}", status_code=204)
async def delete(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = await db.get(EmployeeSegment, sid)
    if s:
        await db.delete(s)
        await audit(db, request, "segment.delete", actor=auth.user, entity="segment", entity_id=sid)
        await db.commit()


@router.get("/{sid}/dashboard")
async def dashboard(sid: int, start: date, end: date, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("attendance.read"))):
    """Davomat tahlili shu segment xodimlari uchun: KPI, kunlik dinamika, bo'limlar jadvali, top intizomli/kechikuvchilar, lavozim bo'yicha, so'nggi kelishlar."""
    from app.api.attendance import MAX_DASHBOARD_DAYS, _filtered, _rows  # noqa: PLC0415
    from app.services.attendance_report import aggregate  # noqa: PLC0415

    s = await db.get(EmployeeSegment, sid)
    if not s:
        raise error(404, "not_found")
    if end < start or (end - start).days + 1 > MAX_DASHBOARD_DAYS:
        raise error(400, "range_invalid", max_days=MAX_DASHBOARD_DAYS)
    stmt = svc.apply_segment(await _filtered(db, q=None, department_id=None, branch_id=None, group_id=None), s)
    employees = list((await db.scalars(stmt.order_by(Employee.full_name, Employee.id).limit(5000))).all())
    rows = await _rows(db, employees, start, end)
    from app.models.org import Branch  # noqa: PLC0415

    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    branches = {b.id: (f"№{b.number} {b.name}" if b.number else b.name) for b in (await db.scalars(select(Branch))).all()}
    out = aggregate(employees, rows, start, end, depts, branches, top=10)
    ids = [e.id for e in employees]
    s_dt = datetime.combine(start, time.min, tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz())
    recs = (await db.execute(select(AttendanceRecord.employee_id, AttendanceRecord.late_minutes).where(AttendanceRecord.employee_id.in_(ids or [0]), AttendanceRecord.check_in_at >= s_dt, AttendanceRecord.check_in_at < e_dt))).all()
    came, late = Counter(r[0] for r in recs), Counter(r[0] for r in recs if r[1])
    names = {e.id: e.full_name for e in employees}
    disciplined = sorted((eid for eid in came if not late.get(eid)), key=lambda eid: (-came[eid], names.get(eid, "")))[:5]
    positions = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    by_pos: dict[str, dict[str, int]] = {}
    for e in employees:
        key = positions.get(e.position_id or 0, "—")
        x = by_pos.setdefault(key, {"employees": 0, "came": 0, "late": 0})
        x["employees"] += 1
        x["came"] += 1 if came.get(e.id) else 0
        x["late"] += 1 if late.get(e.id) else 0
    today = local_date(now())
    t0 = datetime.combine(today, time.min, tzinfo=tz())
    recent = (await db.execute(select(AttendanceRecord.employee_id, AttendanceRecord.check_in_at, AttendanceRecord.late_minutes).where(AttendanceRecord.employee_id.in_(ids or [0]), AttendanceRecord.check_in_at >= t0).order_by(AttendanceRecord.check_in_at.desc()).limit(10))).all()
    emp_dept = {e.id: depts.get(e.department_id or 0) for e in employees}
    out |= {
        "segment": _out(s, len(employees)),
        "top_disciplined": [{"id": eid, "name": names.get(eid), "days": came[eid]} for eid in disciplined],
        "by_position": sorted([{"name": k, **v} for k, v in by_pos.items()], key=lambda r: -r["employees"]),
        "recent": [{"id": eid, "name": names.get(eid), "department": emp_dept.get(eid), "at": at, "late_minutes": lm} for eid, at, lm in recent],
    }
    return out


@settings_router.get("")
async def get_settings_(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(get_auth)):
    return {"values": await svc.all_settings(db), "limits": {k: {"default": d, "min": lo, "max": hi} for k, (d, lo, hi) in svc.SETTINGS.items()}}


@settings_router.put("")
async def put_settings(body: dict[str, int], request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    for k, v in body.items():
        if k not in svc.SETTINGS:
            raise error(422, "unknown_setting", key=k)
        _, lo, hi = svc.SETTINGS[k]
        if not lo <= int(v) <= hi:
            raise error(422, "out_of_range", key=k, min=lo, max=hi)
    for k, v in body.items():
        row = await db.get(CompanySetting, k)
        if row:
            row.value, row.updated_at = int(v), now()
        else:
            db.add(CompanySetting(key=k, value=int(v)))
    await audit(db, request, "company.settings", actor=auth.user, data=body)
    await db.commit()
    return {"values": await svc.all_settings(db)}
