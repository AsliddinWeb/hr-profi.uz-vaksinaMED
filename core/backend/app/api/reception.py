"""Resepshin: mehmon qaydi, oldindan ro'yxat, kirish/chiqish, hisobot."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.org import Branch
from app.models.reception import Visit
from app.services import reception as svc
from app.services.audit import audit
from app.services.notifications import deliver
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/reception", tags=["reception"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("reception.own", "reception.desk", "reception.read")
Desk = require_any("reception.desk")
Viewer = require_any("reception.desk", "reception.read")


async def _visit(db: AsyncSession, visit_id: int, auth: AuthContext, *, lock: bool = False) -> Visit:
    stmt = select(Visit).where(Visit.id == visit_id)
    v = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not v or not svc.can_view(auth, v):
        raise error(404, "not_found")
    return v


async def _one(db: AsyncSession, v: Visit) -> dict[str, Any]:
    hosts, branches, users = await svc.lookups(db, [v])
    return svc.visit_out(v, hosts, branches, users) | {"can": {"edit": False}}


def _flags(auth: AuthContext, v: Visit) -> dict[str, bool]:
    return {"edit": svc.can_edit(auth, v), "arrive": svc.desk(auth) and v.status == "expected", "leave": svc.desk(auth) and v.status == "arrived", "cancel": svc.can_cancel(auth, v)}


@router.get("/hosts")
async def hosts(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Mehmon kimga kelishini tanlash: faol xodimlar."""
    stmt = select(Employee.id, Employee.full_name).where(Employee.status == "active")
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    return [{"id": r.id, "name": r.full_name} for r in (await db.execute(stmt.order_by(Employee.full_name).limit(30))).all()]


@router.get("/branches")
async def branches(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    rows = (await db.execute(select(Branch.id, Branch.name).order_by(Branch.name))).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    today = local_date(now())
    V = Visit

    async def n(*c):
        return await db.scalar(select(func.count()).select_from(V).where(*c)) or 0

    from datetime import datetime as dt

    from app.timeutil import tz

    s_dt = dt.combine(today, dt.min.time(), tzinfo=tz())
    return {
        "inside": await n(V.status == "arrived"),
        "expected_today": await n(V.status == "expected", V.expected_at >= s_dt),
        "arrived_today": await n(V.arrived_at >= s_dt),
    }


@router.get("/report")
async def report(start: date, end: date, branch_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    if end < start or (end - start).days > 92:
        raise error(400, "range_invalid", max_days=92)
    return await svc.report(db, start, end, branch_id)


class VisitIn(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=160)
    visitor_phone: str | None = Field(default=None, max_length=32)
    company: str | None = Field(default=None, max_length=120)
    purpose: str = Field(default="meeting", pattern="^(meeting|interview|delivery|service|other)$")
    host_id: int | None = None
    branch_id: int | None = None
    expected_at: datetime | None = None
    doc_info: str | None = Field(default=None, max_length=60)
    vehicle_plate: str | None = Field(default=None, max_length=16)
    badge_no: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=2000)
    arrive: bool = False


async def _check_refs(db: AsyncSession, body: VisitIn) -> None:
    if body.host_id is not None and not await db.get(Employee, body.host_id):
        raise error(400, "unknown_host")
    if body.branch_id is not None and not await db.get(Branch, body.branch_id):
        raise error(400, "unknown_branch")


def _clean(body: VisitIn) -> dict[str, Any]:
    data = body.model_dump(exclude={"arrive"})
    for k in ("visitor_name", "visitor_phone", "company", "doc_info", "vehicle_plate", "badge_no", "note"):
        data[k] = (data[k] or "").strip() or None
    return data


@router.get("")
async def listing(
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    status: str | None = Query(default=None, pattern="^(expected|arrived|left|cancelled|no_show|open)$"),
    date_: date | None = Query(default=None, alias="date"),
    branch_id: int | None = None,
    host_id: int | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    V = Visit
    conds: list = []
    if scope == "mine":
        conds.append(V.registered_by == auth.user.id)
    elif not svc.viewer(auth):
        raise error(403, "forbidden")
    if status == "open":
        conds.append(V.status.in_(("expected", "arrived")))
    elif status:
        conds.append(V.status == status)
    if date_:
        from app.timeutil import tz

        s_dt = datetime.combine(date_, datetime.min.time(), tzinfo=tz())
        day_end = datetime.combine(date_, datetime.max.time(), tzinfo=tz())
        conds.append(or_((V.arrived_at >= s_dt) & (V.arrived_at <= day_end), (V.expected_at >= s_dt) & (V.expected_at <= day_end)))
    if branch_id:
        conds.append(V.branch_id == branch_id)
    if host_id:
        conds.append(V.host_id == host_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(V.visitor_name.ilike(like), V.company.ilike(like), V.visitor_phone.ilike(like), V.vehicle_plate.ilike(like)))
    total = await db.scalar(select(func.count()).select_from(V).where(*conds)) or 0
    order = (V.status != "arrived", func.coalesce(V.arrived_at, V.expected_at, V.created_at).desc(), V.id.desc())
    rows = list((await db.scalars(select(V).where(*conds).order_by(*order).offset((page - 1) * size).limit(size))).all())
    hosts_, branches_, users = await svc.lookups(db, rows)
    return {"total": total, "page": page, "size": size, "items": [svc.visit_out(v, hosts_, branches_, users) for v in rows]}


@router.post("", status_code=201)
async def create(body: VisitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    await _check_refs(db, body)
    data = _clean(body)
    if not body.arrive and not data["expected_at"]:
        raise error(400, "expected_required")
    if svc.desk(auth) is False:
        data["badge_no"] = None
    v, notes = await svc.register(db, auth, {**data, "arrive": body.arrive}, now())
    await audit(db, request, "reception.register", actor=auth.user, entity="visit", entity_id=v.id, data={"visitor": v.visitor_name, "arrive": body.arrive})
    await db.commit()
    await deliver(request.app, notes)
    return await _one(db, v) | {"can": _flags(auth, v)}


@router.get("/{visit_id}")
async def detail(visit_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth)
    return (await _one(db, v)) | {"can": _flags(auth, v)}


@router.put("/{visit_id}")
async def update(visit_id: int, body: VisitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth, lock=True)
    if not svc.can_edit(auth, v):
        raise error(409 if v.status not in ("expected", "arrived") else 403, "invalid_transition" if v.status not in ("expected", "arrived") else "forbidden")
    await _check_refs(db, body)
    data = _clean(body)
    if v.status == "expected" and not data["expected_at"]:
        raise error(400, "expected_required")
    if not svc.desk(auth):
        data.pop("badge_no")
    for k, val in data.items():
        setattr(v, k, val)
    await audit(db, request, "reception.update", actor=auth.user, entity="visit", entity_id=v.id, data={"visitor": v.visitor_name})
    await db.commit()
    return (await _one(db, v)) | {"can": _flags(auth, v)}


class ArriveIn(BaseModel):
    badge_no: str | None = Field(default=None, max_length=20)


@router.post("/{visit_id}/arrive")
async def arrive(visit_id: int, body: ArriveIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Desk)):
    v = await _visit(db, visit_id, auth, lock=True)
    notes = await svc.mark_arrived(db, v, auth, now(), body.badge_no)
    await audit(db, request, "reception.arrive", actor=auth.user, entity="visit", entity_id=v.id, data={"visitor": v.visitor_name})
    await db.commit()
    await deliver(request.app, notes)
    return (await _one(db, v)) | {"can": _flags(auth, v)}


@router.post("/{visit_id}/leave")
async def leave(visit_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Desk)):
    v = await _visit(db, visit_id, auth, lock=True)
    await svc.mark_left(db, v, auth, now())
    await audit(db, request, "reception.leave", actor=auth.user, entity="visit", entity_id=v.id, data={"visitor": v.visitor_name})
    await db.commit()
    return (await _one(db, v)) | {"can": _flags(auth, v)}


@router.post("/{visit_id}/cancel")
async def cancel(visit_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth, lock=True)
    await svc.cancel(db, v, auth)
    await audit(db, request, "reception.cancel", actor=auth.user, entity="visit", entity_id=v.id, data={"visitor": v.visitor_name})
    await db.commit()
    return (await _one(db, v)) | {"can": _flags(auth, v)}
