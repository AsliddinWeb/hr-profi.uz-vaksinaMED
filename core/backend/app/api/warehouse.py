"""Omborxona: omborlar, xodimlar tarkibi, hozirgi holat (kim ishda) va nazorat hisoboti."""

from datetime import date, time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.org import Branch
from app.models.schedule import ShiftTemplate, WorkGroup
from app.models.warehouse import Warehouse
from app.services import warehouse as svc
from app.services.audit import audit
from app.timeutil import now

router = APIRouter(prefix="/v1/warehouse", tags=["warehouse"])


def require(perm: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not svc.has(auth, perm):
            raise error(403, "forbidden")
        return auth

    return dep


Read = require("warehouse.read")
Manage = require("warehouse.manage")


class ShiftPreset(BaseModel):
    start: time = time(8, 0)
    end: time = time(7, 0)
    min_hours: float = Field(default=9, ge=0, le=24)


class WarehouseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    branch_id: int | None = None
    work_group_id: int | None = None  # bo'sh bo'lsa, `shift` bo'yicha erkin smena va guruh avtomatik yaratiladi
    shift: ShiftPreset = ShiftPreset()
    min_on_duty: int = Field(default=1, ge=0, le=100)
    max_shift_hours: int = Field(default=16, ge=1, le=48)
    alert_grace_min: int = Field(default=20, ge=0, le=240)
    is_active: bool = True


async def _wh(db: AsyncSession, wid: int) -> Warehouse:
    w = await db.get(Warehouse, wid)
    if not w:
        raise error(404, "not_found")
    return w


async def _out(db: AsyncSession, w: Warehouse, with_status: bool = True) -> dict[str, Any]:
    g, sh = await svc.shift_of(db, w)
    branch = await db.get(Branch, w.branch_id) if w.branch_id else None
    out = {
        "id": w.id, "name": w.name, "branch": {"id": branch.id, "name": branch.name} if branch else None, "work_group": {"id": g.id, "name": g.name} if g else None,
        "shift": {"id": sh.id, "name": sh.name, "kind": sh.kind, "start": sh.start_time.strftime("%H:%M"), "end": sh.end_time.strftime("%H:%M"), "min_work_minutes": sh.min_work_minutes} if sh else None,
        "min_on_duty": w.min_on_duty, "max_shift_hours": w.max_shift_hours, "alert_grace_min": w.alert_grace_min, "is_active": w.is_active,
    }  # fmt: skip
    if with_status:
        st = await svc.status(db, w, now())
        out["status"] = {"on_duty": st["on_duty"], "expected": st["expected"], "gap": st["gap"], "in_window": st["in_window"], "staff": len(st["staff"]), "long_open": len(st["long_open"])}
    return out


@router.get("")
async def warehouses(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    rows = (await db.scalars(select(Warehouse).order_by(Warehouse.name))).all()
    return [await _out(db, w) for w in rows]


@router.get("/status")
async def all_status(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    """Hamma faol omborlarning to'liq holati (bosh sahifa)."""
    rows = (await db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.name))).all()
    moment = now()
    return [await svc.status(db, w, moment) for w in rows]


async def _preset(db: AsyncSession, body: WarehouseIn) -> WorkGroup:
    min_minutes = round(body.shift.min_hours * 60) or None
    sh = ShiftTemplate(name=f"{body.name}: erkin {body.shift.start:%H:%M}–{body.shift.end:%H:%M}", kind="flexible", start_time=body.shift.start, end_time=body.shift.end, min_work_minutes=min_minutes, track_lateness=False)
    db.add(sh)
    await db.flush()
    g = WorkGroup(name=body.name, category="warehouse", default_shift_id=sh.id, weekly_off_days=[], observe_holidays=False, attendance_required=True, is_default=False)
    db.add(g)
    await db.flush()
    return g


async def _check_refs(db: AsyncSession, body: WarehouseIn, own_id: int | None = None) -> None:
    if body.branch_id and not await db.get(Branch, body.branch_id):
        raise error(400, "unknown_branch")
    if body.work_group_id:
        g = await db.get(WorkGroup, body.work_group_id)
        if not g or g.is_default:
            raise error(400, "unknown_group")
        taken = await db.scalar(select(Warehouse.id).where(Warehouse.work_group_id == g.id, Warehouse.id != (own_id or 0)))
        if taken:
            raise error(409, "group_taken")


@router.post("", status_code=201)
async def create(body: WarehouseIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    await _check_refs(db, body)
    if await db.scalar(select(Warehouse.id).where(func.lower(Warehouse.name) == body.name.strip().lower())):
        raise error(409, "warehouse_exists")
    try:
        gid = body.work_group_id or (await _preset(db, body)).id
    except IntegrityError:
        raise error(409, "group_name_taken") from None
    w = Warehouse(name=body.name.strip(), branch_id=body.branch_id, work_group_id=gid, min_on_duty=body.min_on_duty, max_shift_hours=body.max_shift_hours, alert_grace_min=body.alert_grace_min, is_active=body.is_active)
    db.add(w)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "warehouse_exists") from None
    await audit(db, request, "warehouse.create", actor=auth.user, entity="warehouse", entity_id=w.id, data={"name": w.name, "group_id": gid, "auto_group": body.work_group_id is None})
    await db.commit()
    return await _out(db, w)


@router.get("/{wid}")
async def one(wid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    return await _out(db, await _wh(db, wid))


@router.put("/{wid}")
async def update(wid: int, body: WarehouseIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    w = await _wh(db, wid)
    await _check_refs(db, body, w.id)
    if body.work_group_id and body.work_group_id != w.work_group_id:
        w.work_group_id = body.work_group_id
    w.name, w.branch_id, w.min_on_duty, w.max_shift_hours, w.alert_grace_min, w.is_active = body.name.strip(), body.branch_id, body.min_on_duty, body.max_shift_hours, body.alert_grace_min, body.is_active
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "warehouse_exists") from None
    await audit(db, request, "warehouse.update", actor=auth.user, entity="warehouse", entity_id=w.id, data={"name": w.name, "min_on_duty": w.min_on_duty})
    await db.commit()
    return await _out(db, w)


@router.delete("/{wid}", status_code=204)
async def delete(wid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    w = await _wh(db, wid)
    await audit(db, request, "warehouse.delete", actor=auth.user, entity="warehouse", entity_id=w.id, data={"name": w.name})
    await db.delete(w)  # guruh va smena saqlanadi: xodimlar grafigi buzilmaydi
    await db.commit()


@router.get("/{wid}/status")
async def status(wid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    return await svc.status(db, await _wh(db, wid), now())


@router.get("/{wid}/control")
async def control(wid: int, start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    if end < start or (end - start).days + 1 > 42:
        raise error(400, "range_invalid", max_days=42)
    return await svc.control(db, await _wh(db, wid), start, end, now())


# --- Xodimlar tarkibi ---------------------------------------------------------------------


class StaffIn(BaseModel):
    employee_id: int


@router.get("/{wid}/staff")
async def staff(wid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    w = await _wh(db, wid)
    return [{"id": e.id, "name": e.full_name, "employee_no": e.employee_no, "phone": e.phone, "has_account": e.user_id is not None} for e in await svc.staff_of(db, w)]


@router.post("/{wid}/staff", status_code=201)
async def add_staff(wid: int, body: StaffIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    w = await _wh(db, wid)
    e = await db.get(Employee, body.employee_id)
    if not e or e.status != "active":
        raise error(400, "unknown_employee")
    if e.work_group_id == w.work_group_id:
        raise error(409, "already_in_warehouse")
    other = await db.scalar(select(Warehouse).where(Warehouse.work_group_id == e.work_group_id)) if e.work_group_id else None
    previous = e.work_group_id
    e.work_group_id = w.work_group_id
    await audit(db, request, "warehouse.staff_add", actor=auth.user, entity="warehouse", entity_id=w.id, data={"employee_id": e.id, "previous_group_id": previous, "moved_from_warehouse": other.name if other else None})
    await db.commit()
    return {"id": e.id, "name": e.full_name, "moved_from": other.name if other else None}


@router.delete("/{wid}/staff/{eid}", status_code=204)
async def remove_staff(wid: int, eid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    w = await _wh(db, wid)
    e = await db.get(Employee, eid)
    if not e or e.work_group_id != w.work_group_id:
        raise error(404, "not_found")
    e.work_group_id = None  # standart guruhga qaytadi
    await audit(db, request, "warehouse.staff_remove", actor=auth.user, entity="warehouse", entity_id=w.id, data={"employee_id": e.id})
    await db.commit()

