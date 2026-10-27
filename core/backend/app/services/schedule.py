"""Grafik: smena davomiyligi, kunlik jadvalni aniqlash (resolve), bayramlar."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employees import Employee
from app.models.schedule import Holiday, ScheduleEntry, ShiftTemplate, WorkGroup

# Mamlakatdagi qat'iy (har yili bir sanadagi) bayramlar. Harakatlanuvchi bayramlar (Ro'za hayit,
# Qurbon hayit) sanasi har yili o'zgaradi va qo'lda kiritiladi: taxmin qilinmaydi.
FIXED_HOLIDAYS_UZ = [
    (1, 1, "Yangi yil"),
    (3, 8, "Xalqaro xotin-qizlar kuni"),
    (3, 21, "Navro'z bayrami"),
    (5, 9, "Xotira va qadrlash kuni"),
    (9, 1, "Mustaqillik kuni"),
    (10, 1, "O'qituvchi va murabbiylar kuni"),
    (12, 8, "Konstitutsiya kuni"),
]  # fmt: skip


def shift_minutes(start: time, end: time) -> int:
    """Smena davomiyligi (daqiqa). end <= start: keyingi kunga o'tadi; teng: 24 soat."""
    s = start.hour * 60 + start.minute
    e = end.hour * 60 + end.minute
    return (e - s) if e > s else (1440 - s + e)


def is_overnight(start: time, end: time) -> bool:
    return end <= start


def shift_window(shift: ShiftTemplate, day: date) -> tuple[datetime, datetime]:
    """`day` sanasida boshlanadigan smenaning haqiqiy boshlanish/tugash vaqti (mahalliy, naive)."""
    start = datetime.combine(day, shift.start_time)
    return start, start + timedelta(minutes=shift_minutes(shift.start_time, shift.end_time))


@dataclass
class Resolved:
    date: date
    working: bool
    shift_id: int | None
    reason: str  # entry | entry_off | holiday | weekly_off | default | no_shift | no_group
    holiday: str | None = None
    explicit: bool = False


@dataclass
class DayContext:
    groups: dict[int, WorkGroup]
    default_group: WorkGroup | None
    holidays: dict[date, Holiday]


def holidays_in_range(rows: list[Holiday], start: date, end: date) -> dict[date, Holiday]:
    """Yillik (year=None) va aniq yildagi bayramlarni sanalarga yoyadi. Aniq yil yozuvi yillikdan ustun."""
    out: dict[date, Holiday] = {}
    day = start
    by_md: dict[tuple[int, int], list[Holiday]] = defaultdict(list)
    for h in rows:
        by_md[(h.month, h.day)].append(h)
    while day <= end:
        candidates = by_md.get((day.month, day.day), [])
        exact = next((h for h in candidates if h.year == day.year), None)
        yearly = next((h for h in candidates if h.year is None), None)
        chosen = exact or yearly
        if chosen:
            out[day] = chosen
        day += timedelta(days=1)
    return out


def resolve_day(
    emp_group_id: int | None, day: date, entry: ScheduleEntry | None, ctx: DayContext
) -> Resolved:
    """Ustuvorlik: aniq yozuv > bayram > haftalik dam > guruhning standart smenasi."""
    if entry is not None:
        if entry.shift_id is None:
            return Resolved(day, False, None, "entry_off", explicit=True)
        return Resolved(day, True, entry.shift_id, "entry", explicit=True)

    group = ctx.groups.get(emp_group_id) if emp_group_id else None
    group = group or ctx.default_group
    if group is None:
        return Resolved(day, True, None, "no_group")

    holiday = ctx.holidays.get(day)
    if holiday and group.observe_holidays:
        if holiday.kind == "holiday":
            return Resolved(day, False, None, "holiday", holiday=holiday.name)
        # Ko'chirilgan ish kuni: haftalik damga qaramay ishlanadi
        return Resolved(day, True, group.default_shift_id, "default", holiday=holiday.name)
    if day.weekday() in (group.weekly_off_days or []):
        return Resolved(day, False, None, "weekly_off")
    if group.default_shift_id is None:
        return Resolved(day, True, None, "no_shift")
    return Resolved(day, True, group.default_shift_id, "default")


async def group_condition(db: AsyncSession, group_id: int):
    """Xodimlarni guruh bo'yicha tanlash sharti. Standart guruhga guruhi belgilanmagan xodimlar ham kiradi."""
    group = await db.get(WorkGroup, group_id)
    if group and group.is_default:
        return or_(Employee.work_group_id == group_id, Employee.work_group_id.is_(None))
    return Employee.work_group_id == group_id


async def load_context(db: AsyncSession, start: date, end: date) -> DayContext:
    groups = {g.id: g for g in (await db.scalars(select(WorkGroup))).all()}
    default = next((g for g in groups.values() if g.is_default), None)
    rows = (
        await db.scalars(
            select(Holiday).where(
                or_(Holiday.year.is_(None), Holiday.year.between(start.year, end.year))
            )
        )
    ).all()
    return DayContext(groups, default, holidays_in_range(list(rows), start, end))


async def resolve_range(
    db: AsyncSession, employees: list[Employee], start: date, end: date
) -> dict[int, list[Resolved]]:
    """Har xodim uchun [start, end] kunlari jadvali."""
    ctx = await load_context(db, start, end)
    ids = [e.id for e in employees]
    entries: dict[tuple[int, date], ScheduleEntry] = {}
    if ids:
        for en in (
            await db.scalars(
                select(ScheduleEntry).where(
                    ScheduleEntry.employee_id.in_(ids), ScheduleEntry.date.between(start, end)
                )
            )
        ).all():
            entries[(en.employee_id, en.date)] = en
    out: dict[int, list[Resolved]] = {}
    for e in employees:
        days = []
        d = start
        while d <= end:
            days.append(resolve_day(e.work_group_id, d, entries.get((e.id, d)), ctx))
            d += timedelta(days=1)
        out[e.id] = days
    return out


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def shift_out(s: ShiftTemplate) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "code": s.code,
        "kind": s.kind,
        "start_time": s.start_time.strftime("%H:%M"),
        "end_time": s.end_time.strftime("%H:%M"),
        "overnight": is_overnight(s.start_time, s.end_time),
        "duration_minutes": shift_minutes(s.start_time, s.end_time),
        "break_minutes": s.break_minutes,
        "late_grace_minutes": s.late_grace_minutes,
        "early_leave_grace_minutes": s.early_leave_grace_minutes,
        "min_work_minutes": s.min_work_minutes,
        "track_lateness": s.track_lateness,
        "color": s.color,
        "sort_order": s.sort_order,
        "is_active": s.is_active,
    }
