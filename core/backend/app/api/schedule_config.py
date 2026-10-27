"""Smena turlari, ish guruhlari, grafik shablonlari va bayramlar."""

from datetime import date, time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.employees import Employee
from app.models.schedule import Holiday, ScheduleEntry, SchedulePattern, ShiftTemplate, WorkGroup
from app.services.audit import audit
from app.services.schedule import FIXED_HOLIDAYS_UZ, shift_minutes, shift_out

router = APIRouter(prefix="/v1/schedule", tags=["schedule-config"])

COLOR = r"^#[0-9a-fA-F]{6}$"
CATEGORIES = "^(office|pharmacy|warehouse|security|other)$"


async def _commit(db: AsyncSession, code: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, code) from exc


# --- Smena turlari --------------------------------------------------------------------


class ShiftBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str | None = Field(default=None, max_length=4)
    kind: str = Field(default="fixed", pattern="^(fixed|flexible)$")
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0, le=600)
    late_grace_minutes: int = Field(default=0, ge=0, le=240)
    early_leave_grace_minutes: int = Field(default=0, ge=0, le=240)
    min_work_minutes: int | None = Field(default=None, ge=1, le=1440)
    track_lateness: bool | None = None
    color: str | None = Field(default=None, pattern=COLOR)
    sort_order: int = 0

    @field_validator("start_time", "end_time")
    @classmethod
    def _no_seconds(cls, v: time) -> time:
        return v.replace(second=0, microsecond=0)

    @model_validator(mode="after")
    def _rules(self):
        duration = shift_minutes(self.start_time, self.end_time)
        if self.break_minutes >= duration:
            raise ValueError("break_too_long")
        if self.min_work_minutes is not None and self.min_work_minutes > duration:
            raise ValueError("min_work_too_long")
        return self


class ShiftIn(ShiftBase):
    is_active: bool = True


async def _shift(db: AsyncSession, shift_id: int) -> ShiftTemplate:
    s = await db.get(ShiftTemplate, shift_id)
    if not s:
        raise error(404, "not_found")
    return s


@router.get("/shifts")
async def list_shifts(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("schedule.read"))
):
    rows = (await db.scalars(select(ShiftTemplate).order_by(ShiftTemplate.sort_order, ShiftTemplate.name))).all()
    return [shift_out(s) for s in rows]


@router.get("/shifts/{shift_id}")
async def get_shift(
    shift_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    return shift_out(await _shift(db, shift_id))


def _apply_shift(s: ShiftTemplate, body: ShiftBase) -> None:
    s.name = body.name.strip()
    s.code = (body.code or "").strip().upper() or None
    s.kind = body.kind
    s.start_time, s.end_time = body.start_time, body.end_time
    s.break_minutes = body.break_minutes
    s.late_grace_minutes = body.late_grace_minutes
    s.early_leave_grace_minutes = body.early_leave_grace_minutes
    s.min_work_minutes = body.min_work_minutes
    # Erkin grafikda kechikish kuzatilmaydi (standart), qat'iy smenada kuzatiladi
    s.track_lateness = body.track_lateness if body.track_lateness is not None else body.kind == "fixed"
    s.color = body.color
    s.sort_order = body.sort_order


@router.post("/shifts", status_code=201)
async def create_shift(
    body: ShiftIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    s = ShiftTemplate(is_active=body.is_active)
    _apply_shift(s, body)
    db.add(s)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "shift_name_taken") from exc
    await audit(db, request, "schedule.shift_create", actor=auth.user, entity="shift", entity_id=s.id,
                data={"name": s.name})  # fmt: skip
    await db.commit()
    return shift_out(s)


@router.put("/shifts/{shift_id}")
async def update_shift(
    shift_id: int,
    body: ShiftIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    s = await _shift(db, shift_id)
    _apply_shift(s, body)
    s.is_active = body.is_active
    await audit(db, request, "schedule.shift_update", actor=auth.user, entity="shift", entity_id=s.id,
                data={"name": s.name})  # fmt: skip
    await _commit(db, "shift_name_taken")
    return shift_out(s)


async def _shift_in_use(db: AsyncSession, shift_id: int) -> str | None:
    if await db.scalar(select(func.count()).select_from(WorkGroup).where(WorkGroup.default_shift_id == shift_id)):
        return "group"
    if await db.scalar(select(func.count()).select_from(ScheduleEntry).where(ScheduleEntry.shift_id == shift_id)):
        return "entries"
    for p in (await db.scalars(select(SchedulePattern))).all():
        if any(slot.get("shift_id") == shift_id for slot in p.cycle):
            return "pattern"
    return None


@router.delete("/shifts/{shift_id}", status_code=204)
async def delete_shift(
    shift_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    s = await _shift(db, shift_id)
    used = await _shift_in_use(db, s.id)
    if used:
        raise error(409, "shift_in_use", used_by=used)
    await audit(db, request, "schedule.shift_delete", actor=auth.user, entity="shift", entity_id=s.id,
                data={"name": s.name})  # fmt: skip
    await db.delete(s)
    await db.commit()


# --- Ish guruhlari -------------------------------------------------------------------


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(default="office", pattern=CATEGORIES)
    description: str | None = Field(default=None, max_length=300)
    default_shift_id: int | None = None
    weekly_off_days: list[int] = []
    observe_holidays: bool = True
    attendance_required: bool = True
    is_default: bool = False
    sort_order: int = 0
    is_active: bool = True

    @field_validator("weekly_off_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        days = sorted(set(v))
        if any(d < 0 or d > 6 for d in days):
            raise ValueError("weekday_invalid")
        if len(days) > 6:
            raise ValueError("all_days_off")
        return days


def group_out(g: WorkGroup, members: int = 0, shift_name: str | None = None) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "category": g.category,
        "description": g.description,
        "default_shift_id": g.default_shift_id,
        "default_shift_name": shift_name,
        "weekly_off_days": g.weekly_off_days or [],
        "observe_holidays": g.observe_holidays,
        "attendance_required": g.attendance_required,
        "is_default": g.is_default,
        "sort_order": g.sort_order,
        "is_active": g.is_active,
        "members": members,
    }


async def _group_member_counts(db: AsyncSession) -> dict[int, int]:
    rows = (
        await db.execute(
            select(Employee.work_group_id, func.count())
            .where(Employee.work_group_id.is_not(None), Employee.status == "active")
            .group_by(Employee.work_group_id)
        )
    ).all()
    counts = dict(rows)
    # Guruhi belgilanmagan xodimlar standart guruhga kiradi
    default = await db.scalar(select(WorkGroup.id).where(WorkGroup.is_default.is_(True)))
    if default is not None:
        unassigned = await db.scalar(
            select(func.count()).select_from(Employee).where(Employee.work_group_id.is_(None), Employee.status == "active")
        )
        counts[default] = counts.get(default, 0) + (unassigned or 0)
    return counts


async def _check_group(db: AsyncSession, body: GroupIn) -> None:
    if body.default_shift_id is not None:
        shift = await db.get(ShiftTemplate, body.default_shift_id)
        if not shift or not shift.is_active:
            raise error(400, "unknown_shift")


@router.get("/groups")
async def list_groups(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("schedule.read"))
):
    groups = (await db.scalars(select(WorkGroup).order_by(WorkGroup.sort_order, WorkGroup.name))).all()
    counts = await _group_member_counts(db)
    shifts = {s.id: s.name for s in (await db.scalars(select(ShiftTemplate))).all()}
    return [group_out(g, counts.get(g.id, 0), shifts.get(g.default_shift_id)) for g in groups]


@router.get("/groups/{group_id}")
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    g = await db.get(WorkGroup, group_id)
    if not g:
        raise error(404, "not_found")
    counts = await _group_member_counts(db)
    shift = await db.get(ShiftTemplate, g.default_shift_id) if g.default_shift_id else None
    return group_out(g, counts.get(g.id, 0), shift.name if shift else None)


def _apply_group(g: WorkGroup, body: GroupIn) -> None:
    g.name = body.name.strip()
    g.category = body.category
    g.description = (body.description or "").strip() or None
    g.default_shift_id = body.default_shift_id
    g.weekly_off_days = body.weekly_off_days
    g.observe_holidays = body.observe_holidays
    g.attendance_required = body.attendance_required
    g.sort_order = body.sort_order
    g.is_active = body.is_active


@router.post("/groups", status_code=201)
async def create_group(
    body: GroupIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    await _check_group(db, body)
    g = WorkGroup(is_default=False)
    _apply_group(g, body)
    db.add(g)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "group_name_taken") from exc
    if body.is_default:
        await _make_default(db, g)
    await audit(db, request, "schedule.group_create", actor=auth.user, entity="work_group", entity_id=g.id,
                data={"name": g.name})  # fmt: skip
    await db.commit()
    return group_out(g)


async def _make_default(db: AsyncSession, g: WorkGroup) -> None:
    await db.execute(update(WorkGroup).where(WorkGroup.id != g.id).values(is_default=False))
    g.is_default = True
    await db.flush()


@router.put("/groups/{group_id}")
async def update_group(
    group_id: int,
    body: GroupIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    g = await db.get(WorkGroup, group_id)
    if not g:
        raise error(404, "not_found")
    await _check_group(db, body)
    if g.is_default and not body.is_default:
        raise error(409, "default_group_required")  # boshqa guruhni standart qiling
    if not body.is_active and g.is_default:
        raise error(409, "default_group_required")
    _apply_group(g, body)
    if body.is_default and not g.is_default:
        await _make_default(db, g)
    await audit(db, request, "schedule.group_update", actor=auth.user, entity="work_group", entity_id=g.id,
                data={"name": g.name})  # fmt: skip
    await _commit(db, "group_name_taken")
    return group_out(g)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    g = await db.get(WorkGroup, group_id)
    if not g:
        raise error(404, "not_found")
    if g.is_default:
        raise error(409, "default_group_required")
    if await db.scalar(select(func.count()).select_from(Employee).where(Employee.work_group_id == g.id)):
        raise error(409, "group_has_members")
    await audit(db, request, "schedule.group_delete", actor=auth.user, entity="work_group", entity_id=g.id,
                data={"name": g.name})  # fmt: skip
    await db.delete(g)
    await db.commit()


# --- Grafik shablonlari --------------------------------------------------------------


class Slot(BaseModel):
    shift_id: int | None = None


class PatternIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    cycle: list[Slot] = Field(min_length=1, max_length=60)
    is_active: bool = True


def pattern_out(p: SchedulePattern) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "cycle": p.cycle,
        "length": len(p.cycle),
        "work_days": sum(1 for s in p.cycle if s.get("shift_id") is not None),
        "is_active": p.is_active,
    }


async def _check_pattern(db: AsyncSession, body: PatternIn) -> None:
    ids = {s.shift_id for s in body.cycle if s.shift_id is not None}
    if not ids:
        raise error(400, "pattern_no_work_days")
    found = set((await db.scalars(select(ShiftTemplate.id).where(ShiftTemplate.id.in_(ids), ShiftTemplate.is_active.is_(True)))).all())
    if found != ids:
        raise error(400, "unknown_shift")


@router.get("/patterns")
async def list_patterns(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("schedule.read"))
):
    rows = (await db.scalars(select(SchedulePattern).order_by(SchedulePattern.name))).all()
    return [pattern_out(p) for p in rows]


@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    p = await db.get(SchedulePattern, pattern_id)
    if not p:
        raise error(404, "not_found")
    return pattern_out(p)


@router.post("/patterns", status_code=201)
async def create_pattern(
    body: PatternIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    await _check_pattern(db, body)
    p = SchedulePattern(name=body.name.strip(), description=(body.description or "").strip() or None,
                        cycle=[s.model_dump() for s in body.cycle], is_active=body.is_active)  # fmt: skip
    db.add(p)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "pattern_name_taken") from exc
    await audit(db, request, "schedule.pattern_create", actor=auth.user, entity="pattern", entity_id=p.id,
                data={"name": p.name})  # fmt: skip
    await db.commit()
    return pattern_out(p)


@router.put("/patterns/{pattern_id}")
async def update_pattern(
    pattern_id: int,
    body: PatternIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    p = await db.get(SchedulePattern, pattern_id)
    if not p:
        raise error(404, "not_found")
    await _check_pattern(db, body)
    p.name = body.name.strip()
    p.description = (body.description or "").strip() or None
    p.cycle = [s.model_dump() for s in body.cycle]
    p.is_active = body.is_active
    await audit(db, request, "schedule.pattern_update", actor=auth.user, entity="pattern", entity_id=p.id,
                data={"name": p.name})  # fmt: skip
    await _commit(db, "pattern_name_taken")
    return pattern_out(p)


@router.delete("/patterns/{pattern_id}", status_code=204)
async def delete_pattern(
    pattern_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    p = await db.get(SchedulePattern, pattern_id)
    if not p:
        raise error(404, "not_found")
    await audit(db, request, "schedule.pattern_delete", actor=auth.user, entity="pattern", entity_id=p.id,
                data={"name": p.name})  # fmt: skip
    await db.delete(p)
    await db.commit()


# --- Bayramlar ------------------------------------------------------------------------


class HolidayIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="holiday", pattern="^(holiday|workday)$")
    yearly: bool = False
    date: date
    note: str | None = Field(default=None, max_length=1000)


def holiday_out(h: Holiday) -> dict[str, Any]:
    return {
        "id": h.id,
        "name": h.name,
        "kind": h.kind,
        "yearly": h.year is None,
        "year": h.year,
        "month": h.month,
        "day": h.day,
        # Yillik yozuvlar uchun ko'rsatish sanasi (qayta tahrirlashda formaga tushadi)
        "date": f"{h.year or 2000:04d}-{h.month:02d}-{h.day:02d}",
        "note": h.note,
    }


@router.get("/holidays")
async def list_holidays(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    stmt = select(Holiday)
    if year:
        stmt = stmt.where((Holiday.year == year) | Holiday.year.is_(None))
    rows = (await db.scalars(stmt.order_by(Holiday.month, Holiday.day))).all()
    return [holiday_out(h) for h in rows]


@router.get("/holidays/{holiday_id}")
async def get_holiday(
    holiday_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("schedule.read")),
):
    h = await db.get(Holiday, holiday_id)
    if not h:
        raise error(404, "not_found")
    return holiday_out(h)


def _apply_holiday(h: Holiday, body: HolidayIn) -> None:
    h.year = None if body.yearly else body.date.year
    h.month, h.day = body.date.month, body.date.day
    h.name = body.name.strip()
    h.kind = body.kind
    h.note = (body.note or "").strip() or None


class SeedIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    yearly: bool = False


@router.post("/holidays/seed", status_code=201)
async def seed_holidays(
    body: SeedIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    """O'zbekistonning har yili bir sanadagi bayramlarini qo'shadi. Mavjudlari o'tkazib yuboriladi."""
    existing = {(h.year, h.month, h.day) for h in (await db.scalars(select(Holiday))).all()}
    year = None if body.yearly else body.year
    created = 0
    for month, day, name in FIXED_HOLIDAYS_UZ:
        if (year, month, day) in existing or (None, month, day) in existing:
            continue
        db.add(Holiday(year=year, month=month, day=day, name=name, kind="holiday"))
        created += 1
    await audit(db, request, "schedule.holiday_seed", actor=auth.user, entity="holiday",
                data={"year": body.year, "yearly": body.yearly, "created": created})  # fmt: skip
    await db.commit()
    return {"created": created, "skipped": len(FIXED_HOLIDAYS_UZ) - created}


@router.post("/holidays", status_code=201)
async def create_holiday(
    body: HolidayIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    h = Holiday()
    _apply_holiday(h, body)
    db.add(h)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "holiday_date_taken") from exc
    await audit(db, request, "schedule.holiday_create", actor=auth.user, entity="holiday", entity_id=h.id,
                data={"name": h.name, "date": str(body.date), "kind": h.kind})  # fmt: skip
    await db.commit()
    return holiday_out(h)


@router.put("/holidays/{holiday_id}")
async def update_holiday(
    holiday_id: int,
    body: HolidayIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    h = await db.get(Holiday, holiday_id)
    if not h:
        raise error(404, "not_found")
    _apply_holiday(h, body)
    await audit(db, request, "schedule.holiday_update", actor=auth.user, entity="holiday", entity_id=h.id,
                data={"name": h.name, "date": str(body.date)})  # fmt: skip
    await _commit(db, "holiday_date_taken")
    return holiday_out(h)


@router.delete("/holidays/{holiday_id}", status_code=204)
async def delete_holiday(
    holiday_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("schedule.manage")),
):
    h = await db.get(Holiday, holiday_id)
    if not h:
        raise error(404, "not_found")
    await audit(db, request, "schedule.holiday_delete", actor=auth.user, entity="holiday", entity_id=h.id,
                data={"name": h.name})  # fmt: skip
    await db.delete(h)
    await db.commit()
