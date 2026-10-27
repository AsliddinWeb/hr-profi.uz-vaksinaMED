"""O'sish: lavozim zinapoyasi, o'sish takliflari (HRD tasdig'i), yig'ma baho va baholash sozlamalari."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import TransferIn, transfer_one
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.growth import CareerLevel, HrSetting, Promotion
from app.models.org import Branch, Position
from app.rbac import matches
from app.services import growth as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/growth", tags=["growth"])


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def _need(auth: AuthContext, *perms: str) -> None:
    if not any(has(auth, p) for p in perms):
        raise error(403, "forbidden")


# --- Zinapoya -----------------------------------------------------------------------------


class LevelIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    position_id: int | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    is_active: bool = True


class LaddersIn(BaseModel):
    levels: list[LevelIn] = Field(max_length=20)


def _level_out(lv: CareerLevel, pos: dict[int, str]) -> dict[str, Any]:
    return {"id": lv.id, "name": lv.name, "position_id": lv.position_id, "position": pos.get(lv.position_id or 0), "salary_min": lv.salary_min, "salary_max": lv.salary_max, "is_active": lv.is_active}


@router.get("/levels")
async def get_levels(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "career.read", "career.manage", "career.propose", "attestation.read", "attestation.manage")
    pos = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    return [_level_out(lv, pos) for lv in await svc.levels(db, active_only=False)]


@router.put("/levels")
async def put_levels(body: LaddersIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Zinapoyani almashtiradi (ro'yxat tartibi = daraja tartibi). Ro'yxatda bo'lmagan daraja o'chiriladi (tarix saqlanadi)."""
    _need(auth, "career.manage")
    seen_positions: set[int] = set()
    for lv in body.levels:
        if lv.position_id:
            if not await db.get(Position, lv.position_id):
                raise error(400, "unknown_reference")
            if lv.position_id in seen_positions:
                raise error(400, "position_duplicate")
            seen_positions.add(lv.position_id)
    existing = {lv.id: lv for lv in await svc.levels(db, active_only=False)}
    keep: set[int] = set()
    for i, item in enumerate(body.levels):
        lv = existing.get(item.id or 0)
        if lv is None:
            lv = CareerLevel()
            db.add(lv)
        lv.name, lv.position_id, lv.salary_min, lv.salary_max, lv.is_active, lv.sort_order = item.name.strip(), item.position_id, item.salary_min, item.salary_max, item.is_active, i
        await db.flush()
        keep.add(lv.id)
    for lid, lv in existing.items():
        if lid not in keep:
            await db.delete(lv)
    await audit(db, request, "growth.levels", actor=auth.user, entity="career_level", entity_id=0, data={"count": len(body.levels)})
    await db.commit()
    pos = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    return [_level_out(lv, pos) for lv in await svc.levels(db, active_only=False)]


# --- Sozlamalar ---------------------------------------------------------------------------


class SettingIn(BaseModel):
    value: dict[str, float]


@router.get("/settings/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "career.read", "career.manage", "attestation.read", "attestation.manage")
    if key not in svc.DEFAULTS:
        raise error(404, "not_found")
    return await svc.get_setting(db, key)


@router.put("/settings/{key}")
async def put_setting(key: str, body: SettingIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "career.manage")
    if key not in svc.DEFAULTS:
        raise error(404, "not_found")
    value = {k: v for k, v in body.value.items() if k in svc.DEFAULTS[key]}
    if any(v < 0 for v in value.values()) or (key == "attestation" and not 0 <= value.get("pass_score", 0) <= 100):
        raise error(400, "value_invalid")
    row = await db.get(HrSetting, key)
    if row is None:
        row = HrSetting(key=key, value={})
        db.add(row)
    row.value, row.updated_by, row.updated_at = value, auth.user.id, now()
    await audit(db, request, "growth.setting", actor=auth.user, entity="hr_setting", entity_id=0, data={"key": key, **value})
    await db.commit()
    return await svc.get_setting(db, key)


# --- O'sish takliflari --------------------------------------------------------------------


async def _promo_out(db: AsyncSession, rows: list[Promotion]) -> list[dict[str, Any]]:
    emps = {e.id: e for e in (await db.scalars(select(Employee).where(Employee.id.in_({p.employee_id for p in rows})))).all()} if rows else {}
    lv = {x.id: x.name for x in await svc.levels(db, active_only=False)}
    return [
        {
            "id": p.id, "employee": {"id": p.employee_id, "name": emps[p.employee_id].full_name if p.employee_id in emps else None}, "from": lv.get(p.from_level_id or 0), "to": lv.get(p.to_level_id or 0),
            "status": p.status, "source": p.source, "basis": p.basis, "decision_note": p.decision_note, "decided_at": p.decided_at, "effective_date": p.effective_date, "created_at": p.created_at,
        }  # fmt: skip
        for p in rows
    ]


@router.get("/promotions")
async def list_promotions(status: str | None = Query(default=None, pattern="^(proposed|applied|rejected)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "career.read", "career.manage", "career.propose")
    stmt = select(Promotion).order_by(Promotion.id.desc()).limit(200)
    if status:
        stmt = stmt.where(Promotion.status == status)
    out = await _promo_out(db, list((await db.scalars(stmt)).all()))
    return {"items": out, "can_decide": has(auth, "career.manage")}


class ProposeIn(BaseModel):
    employee_id: int
    to_level_id: int
    basis: str | None = Field(default=None, max_length=1000)


@router.post("/promotions", status_code=201)
async def propose(body: ProposeIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "career.propose", "career.manage")
    emp = await db.get(Employee, body.employee_id)
    to = await db.get(CareerLevel, body.to_level_id)
    if not emp or emp.status != "active" or not to or not to.is_active:
        raise error(400, "unknown_reference")
    lvls = await svc.levels(db)
    cur = svc.level_of(emp, lvls)
    if cur is not None and to.sort_order <= cur.sort_order:
        raise error(400, "level_not_higher")
    if await db.scalar(select(Promotion.id).where(Promotion.employee_id == emp.id, Promotion.status == "proposed")):
        raise error(409, "promotion_exists")
    p = Promotion(employee_id=emp.id, from_level_id=cur.id if cur else None, to_level_id=to.id, status="proposed", source="manual", basis=(body.basis or "").strip() or None, proposed_by=auth.user.id)
    db.add(p)
    await db.flush()
    from app.services.answers import users_with_permission  # noqa: PLC0415

    notes = await notify(db, [u for u in await users_with_permission(db, "career.manage") if u != auth.user.id], "career.proposed", params={"employee": emp.full_name, "from_level": cur.name if cur else "—", "to_level": to.name}, link="/career")
    await audit(db, request, "growth.propose", actor=auth.user, entity="promotion", entity_id=p.id, data={"employee_id": emp.id, "to": to.name})
    await db.commit()
    await deliver(request.app, notes)
    return (await _promo_out(db, [p]))[0]


class PromoDecideIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)
    effective_date: date | None = None


@router.post("/promotions/{pid}/decide")
async def decide_promotion(pid: int, body: PromoDecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HRD: tasdiqlasa xodimning lavozimi o'zgaradi (tarix va bildirishnoma bilan), rad etsa izoh shart."""
    _need(auth, "career.manage")
    p = await db.scalar(select(Promotion).where(Promotion.id == pid).with_for_update())
    if not p:
        raise error(404, "not_found")
    if p.status != "proposed":
        raise error(409, "already_decided")
    emp = await db.get(Employee, p.employee_id)
    to = await db.get(CareerLevel, p.to_level_id) if p.to_level_id else None
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    moment = now()
    notes: list = []
    if body.action == "approve":
        if not emp or not to or not to.position_id:
            raise error(409, "level_without_position")
        eff = body.effective_date or local_date(moment)
        _, notes = await transfer_one(db, emp, TransferIn(position_id=to.position_id, effective_date=eff, note=f"O'sish: {to.name}"), auth)
        p.status, p.effective_date = "applied", eff
    else:
        p.status = "rejected"
    p.decided_by, p.decided_at, p.decision_note = auth.user.id, moment, note
    targets = [u for u in {p.proposed_by} if u and u != auth.user.id]
    if targets and emp:
        notes += await notify(db, targets, "career.decided", params={"employee": emp.full_name, "result": "tasdiqlandi" if body.action == "approve" else "rad etildi", "note": note or ""}, link="/career")
    await audit(db, request, f"growth.promotion_{body.action}", actor=auth.user, entity="promotion", entity_id=p.id, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return (await _promo_out(db, [p]))[0]


# --- Yig'ma baho --------------------------------------------------------------------------


def _scope_branches(auth: AuthContext):
    return select(Branch.id).where((Branch.manager_user_id == auth.user.id) | (Branch.coordinator_user_id == auth.user.id))


@router.get("/performance")
async def performance(branch_id: int | None = None, limit: int = Query(default=100, ge=1, le=150), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Xodimlarning yig'ma bahosi (past ball birinchi). HR hammasini, mudir/koordinator o'z filiallarini ko'radi."""
    _need(auth, "performance.read", "performance.own")
    stmt = select(Employee).where(Employee.status == "active")
    if not has(auth, "performance.read"):
        stmt = stmt.where(Employee.branch_id.in_(_scope_branches(auth)))
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    emps = list((await db.scalars(stmt.order_by(Employee.full_name).limit(limit))).all())
    weights, today = await svc.get_setting(db, "score_weights"), local_date(now())
    br = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    rows = []
    for e in emps:
        r = await svc.employee_score(db, e, today, weights)
        rows.append({"employee": {"id": e.id, "name": e.full_name}, "branch": br.get(e.branch_id or 0), **r})
    rows.sort(key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else 0))
    return {"weights": weights, "items": rows}


@router.get("/performance/{employee_id}")
async def performance_one(employee_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise error(404, "not_found")
    own = emp.user_id == auth.user.id
    scoped = has(auth, "performance.own") and emp.branch_id in set((await db.scalars(_scope_branches(auth))).all())
    if not (own or has(auth, "performance.read") or scoped):
        raise error(404, "not_found")
    return {"employee": {"id": emp.id, "name": emp.full_name}, **await svc.employee_score(db, emp, local_date(now()))}
