"""Kompaniya sozlamalari va xodim segmentlari bo'yicha yordamchilar."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanySetting, EmployeeSegment
from app.models.employees import Employee

# Ruxsat etilgan sozlamalar: kalit -> (standart qiymat, min, max)
SETTINGS: dict[str, tuple[int, int, int]] = {
    "checklists.month_limit": (4, 1, 31),
    "revisions.cycle_days": (90, 7, 730),
    "revisions.soon_days": (14, 1, 90),
}


async def get_setting(db: AsyncSession, key: str) -> int:
    default = SETTINGS[key][0]
    row = await db.get(CompanySetting, key)
    try:
        return int(row.value) if row and row.value is not None else default
    except (TypeError, ValueError):
        return default


async def all_settings(db: AsyncSession) -> dict[str, Any]:
    return {k: await get_setting(db, k) for k in SETTINGS}


def apply_segment(stmt, seg: EmployeeSegment | None):
    """Employee so'roviga segment shartlarini qo'shadi."""
    if seg is None:
        return stmt
    if seg.scope == "office":
        stmt = stmt.where(Employee.branch_id.is_(None))
    elif seg.scope == "branch":
        stmt = stmt.where(Employee.branch_id.is_not(None))
    if seg.department_ids:
        stmt = stmt.where(Employee.department_id.in_(seg.department_ids))
    if seg.position_ids:
        stmt = stmt.where(Employee.position_id.in_(seg.position_ids))
    return stmt


async def segments(db: AsyncSession, active_only: bool = True) -> list[EmployeeSegment]:
    stmt = select(EmployeeSegment).order_by(EmployeeSegment.sort_order, EmployeeSegment.id)
    if active_only:
        stmt = stmt.where(EmployeeSegment.is_active.is_(True))
    return list((await db.scalars(stmt)).all())


def segment_conditions(seg: EmployeeSegment | None) -> list:
    """Segment shartlari ro'yxat ko'rinishida (Employee jadvali so'rovda bo'lishi kerak)."""
    if seg is None:
        return []
    conds: list = []
    if seg.scope == "office":
        conds.append(Employee.branch_id.is_(None))
    elif seg.scope == "branch":
        conds.append(Employee.branch_id.is_not(None))
    if seg.department_ids:
        conds.append(Employee.department_id.in_(seg.department_ids))
    if seg.position_ids:
        conds.append(Employee.position_id.in_(seg.position_ids))
    return conds


async def segment_counts(db: AsyncSession, count_stmt_for) -> dict[int, int]:
    """Har faol segment uchun son: `count_stmt_for(conds)` -> count so'rovi."""
    out: dict[int, int] = {}
    for s in await segments(db):
        out[s.id] = await db.scalar(count_stmt_for(segment_conditions(s))) or 0
    return out


async def load_segment(db: AsyncSession, segment_id: int | None) -> EmployeeSegment | None:
    return await db.get(EmployeeSegment, segment_id) if segment_id else None
