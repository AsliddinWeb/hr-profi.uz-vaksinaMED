"""Rotatsiya: filialdan filialga vaqtincha o'tkazish (so'rov -> HR tasdig'i -> avtomatik boshlash/qaytarish)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch
from app.models.rotations import Rotation
from app.services import rotations as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/rotations", tags=["rotations"])


class RotationIn(BaseModel):
    employee_id: int
    to_branch_id: int
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=300)


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=500)


async def _branches(db: AsyncSession) -> dict[int, Branch]:
    return {b.id: b for b in (await db.scalars(select(Branch))).all()}


def _out(r: Rotation, emp: Employee | None, branches: dict[int, Branch], names: dict[int, str]) -> dict[str, Any]:
    fb, tb = branches.get(r.from_branch_id), branches.get(r.to_branch_id)
    return {
        "id": r.id, "status": r.status, "employee": {"id": emp.id, "name": emp.full_name} if emp else None,
        "from_branch": {"id": r.from_branch_id, "name": fb.name if fb else None}, "to_branch": {"id": r.to_branch_id, "name": tb.name if tb else None},
        "start_date": r.start_date, "end_date": r.end_date, "reason": r.reason, "requested_by": names.get(r.requested_by or 0), "decided_by": names.get(r.decided_by or 0),
        "decided_at": r.decided_at, "decision_note": r.decision_note, "started_at": r.started_at, "finished_at": r.finished_at, "created_at": r.created_at,
    }  # fmt: skip


async def _names(db: AsyncSession, rows: list[Rotation]) -> dict[int, str]:
    ids = {u for r in rows for u in (r.requested_by, r.decided_by) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


async def _load(db: AsyncSession, rid: int, auth: AuthContext, *, lock: bool = False) -> tuple[Rotation, Employee, dict[int, Branch]]:
    stmt = select(Rotation).where(Rotation.id == rid)
    rot = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, rot.employee_id) if rot else None
    branches = await _branches(db)
    if not rot or not emp or not svc.touches(auth, rot, branches, emp):
        raise error(404, "not_found")
    return rot, emp, branches


@router.get("/branches")
async def branch_options(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Qabul qiluvchi filial tanlovi: `branches.read` bo'lmagan mudir/koordinator uchun ham (faqat id, raqam, nom)."""
    if not (svc.has(auth, "rotations.manage") or svc.has(auth, "rotations.request")):
        raise error(403, "forbidden")
    rows = (await db.scalars(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number, Branch.name))).all()
    return [{"id": b.id, "number": b.number, "name": b.name} for b in rows]


@router.get("")
async def list_rotations(
    status: str | None = Query(default=None, pattern="^(open|pending|approved|active|completed|rejected|cancelled)$"),
    employee_id: int | None = None,
    branch_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    if not (svc.sees_all(auth) or svc.has(auth, "rotations.request") or svc.has(auth, "rotations.own")):
        raise error(403, "forbidden")
    stmt = select(Rotation).order_by(Rotation.id.desc()).limit(500)
    if status == "open":
        stmt = stmt.where(Rotation.status.in_(svc.OPEN))
    elif status:
        stmt = stmt.where(Rotation.status == status)
    if employee_id:
        stmt = stmt.where(Rotation.employee_id == employee_id)
    if branch_id:
        stmt = stmt.where((Rotation.from_branch_id == branch_id) | (Rotation.to_branch_id == branch_id))
    rows = list((await db.scalars(stmt)).all())
    branches = await _branches(db)
    emps = {e.id: e for e in (await db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows})))).all()} if rows else {}
    names = await _names(db, rows)
    return [_out(r, emps.get(r.employee_id), branches, names) for r in rows if svc.touches(auth, r, branches, emps.get(r.employee_id))]


@router.post("", status_code=201)
async def create_rotation(body: RotationIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR (`rotations.manage`) yaratsa darhol tasdiqlanadi; mudir/koordinator (`rotations.request`) yaratsa HR tasdig'ini kutadi."""
    manage = svc.has(auth, "rotations.manage")
    if not (manage or svc.has(auth, "rotations.request")):
        raise error(403, "forbidden")
    moment = now()
    emp = await db.get(Employee, body.employee_id)
    if not emp:
        raise error(404, "not_found")
    branches = await _branches(db)
    home = branches.get(emp.branch_id or 0)
    if not manage and not (home and auth.user.id in (home.manager_user_id, home.coordinator_user_id)):
        raise error(403, "not_your_branch")
    await svc.validate_new(db, emp, body.to_branch_id, body.start_date, body.end_date, local_date(moment))
    rot = Rotation(employee_id=emp.id, from_branch_id=emp.branch_id, to_branch_id=body.to_branch_id, start_date=body.start_date, end_date=body.end_date, reason=body.reason.strip(), status="pending", requested_by=auth.user.id)  # type: ignore[arg-type]
    db.add(rot)
    await db.flush()
    notes: list = []
    if manage:
        notes = await svc.approve(db, rot, emp, auth, None, moment)
    else:
        hr = await users_with_permission(db, "rotations.manage")
        fb, tb = branches.get(rot.from_branch_id), branches.get(rot.to_branch_id)
        notes = await notify(db, hr, "rotation.requested", params={"employee": emp.full_name, "from_branch": fb.name if fb else "—", "to_branch": tb.name if tb else "—", "period": svc.period(rot)}, link=f"/org/rotations/{rot.id}")
    await audit(db, request, "rotation.create", actor=auth.user, entity="rotation", entity_id=rot.id, data={"employee_id": emp.id, "to": rot.to_branch_id, "status": rot.status})
    await db.commit()
    await deliver(request.app, notes)
    return _out(rot, emp, branches, await _names(db, [rot]))


@router.get("/{rid}")
async def get_rotation(rid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    rot, emp, branches = await _load(db, rid, auth)
    return _out(rot, emp, branches, await _names(db, [rot]))


@router.post("/{rid}/decide")
async def decide(rid: int, body: DecisionIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.has(auth, "rotations.manage"):
        raise error(403, "forbidden")
    rot, emp, branches = await _load(db, rid, auth, lock=True)
    if rot.status != "pending":
        raise error(409, "already_decided")
    moment = now()
    if body.action == "approve":
        if rot.end_date < local_date(moment):
            raise error(400, "date_in_past")
        if emp.status != "active":
            raise error(409, "employee_dismissed")
        notes = await svc.approve(db, rot, emp, auth, body.note, moment)
    else:
        notes = await svc.reject(db, rot, emp, auth, body.note, moment)
    await audit(db, request, f"rotation.{body.action}", actor=auth.user, entity="rotation", entity_id=rot.id, data={"status": rot.status})
    await db.commit()
    await deliver(request.app, notes)
    return _out(rot, emp, branches, await _names(db, [rot]))


@router.post("/{rid}/cancel")
async def cancel_rotation(rid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Kutilayotgan, tasdiqlangan yoki faol rotatsiyani bekor qiladi (faol bo'lsa xodim darhol uy filialiga qaytadi)."""
    rot, emp, branches = await _load(db, rid=rid, auth=auth, lock=True)
    if not (svc.has(auth, "rotations.manage") or (rot.requested_by == auth.user.id and rot.status == "pending")):
        raise error(403, "forbidden")
    if rot.status not in svc.OPEN:
        raise error(409, "already_closed")
    notes = await svc.cancel(db, rot, emp, now())
    await audit(db, request, "rotation.cancel", actor=auth.user, entity="rotation", entity_id=rot.id, data={})
    await db.commit()
    await deliver(request.app, notes)
    return _out(rot, emp, branches, await _names(db, [rot]))
