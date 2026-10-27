"""Ko'chma davomat va jonli kuzatuv: ruxsatlar, xodim sahifasi (rozilik, ish kuni, trek, SOS), jonli xarita, hodisalar."""

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.mobile import MobileEvent, MobilePermit, MobilePoint, MobileSession
from app.services import mobile as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/mobile", tags=["mobile"])


def require(perm: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not svc.has(auth, perm):
            raise error(403, "forbidden")
        return auth

    return dep


Own = require("mobile.own")
Manage = require("mobile.manage")


async def _reader(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not svc.can_read(auth):
        raise error(403, "forbidden")
    return auth


Read = _reader


async def _names(db: AsyncSession, ids: set[int]) -> dict[int, Employee]:
    return {e.id: e for e in (await db.scalars(select(Employee).where(Employee.id.in_(ids)))).all()} if ids else {}


# --- Ruxsatlar ----------------------------------------------------------------------------


class PermitIn(BaseModel):
    enabled: bool = True
    interval_s: int = Field(default=60, ge=15, le=600)
    window_start: time = time(8, 0)
    window_end: time = time(20, 0)
    note: str | None = Field(default=None, max_length=300)


def _permit_out(p: MobilePermit, e: Employee | None, active: MobileSession | None = None) -> dict[str, Any]:
    return {
        "employee": {"id": p.employee_id, "name": e.full_name if e else None, "phone": e.phone if e else None, "has_account": bool(e and e.user_id)}, "enabled": p.enabled, "interval_s": p.interval_s,
        "window_start": p.window_start.strftime("%H:%M"), "window_end": p.window_end.strftime("%H:%M"), "note": p.note, "consent_at": p.consent_at, "active_session_id": active.id if active else None,
    }  # fmt: skip


@router.get("/permits")
async def permits(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    rows = (await db.scalars(select(MobilePermit))).all()
    emps = await _names(db, {p.employee_id for p in rows})
    act = {s.employee_id: s for s in (await db.scalars(select(MobileSession).where(MobileSession.status == "active"))).all()}
    out = [_permit_out(p, emps.get(p.employee_id), act.get(p.employee_id)) for p in rows]
    return sorted(out, key=lambda x: x["employee"]["name"] or "")


@router.get("/permits/{eid}")
async def permit(eid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    e = await db.get(Employee, eid)
    if not e:
        raise error(404, "not_found")
    p = await svc.permit_of(db, eid)
    if not p:
        return {"employee": {"id": e.id, "name": e.full_name, "phone": e.phone, "has_account": e.user_id is not None}, "enabled": False, "interval_s": 60, "window_start": "08:00", "window_end": "20:00", "note": None, "consent_at": None, "active_session_id": None, "exists": False}
    return {**_permit_out(p, e, await svc.active_session(db, eid)), "exists": True}


@router.put("/permits/{eid}")
async def put_permit(eid: int, body: PermitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    e = await db.get(Employee, eid)
    if not e or e.status != "active":
        raise error(400, "unknown_employee")
    if body.window_end <= body.window_start:
        raise error(400, "window_invalid")
    p = await svc.permit_of(db, eid)
    new = p is None
    if p is None:
        p = MobilePermit(employee_id=eid, granted_by=auth.user.id)
        db.add(p)
    was_enabled = p.enabled and not new
    p.enabled, p.interval_s, p.window_start, p.window_end, p.note = body.enabled, body.interval_s, body.window_start, body.window_end, (body.note or "").strip() or None
    moment = now()
    s = await svc.active_session(db, eid, lock=True)
    if s and not body.enabled:
        await svc.end_session(db, s, moment, "permit_revoked")
    notes = []
    if body.enabled and (new or not was_enabled) and e.user_id and e.user_id != auth.user.id:
        notes = await notify(db, [e.user_id], "mobile.granted", link="/mobile/my")
    await db.flush()
    await audit(db, request, "mobile.permit_save", actor=auth.user, entity="mobile_permit", entity_id=p.id, data={"employee_id": eid, "enabled": p.enabled, "window": f"{p.window_start:%H:%M}-{p.window_end:%H:%M}", "interval_s": p.interval_s})
    await db.commit()
    await deliver(request.app, notes)
    return {**_permit_out(p, e, None if (s and not body.enabled) else await svc.active_session(db, eid)), "exists": True}


@router.delete("/permits/{eid}", status_code=204)
async def delete_permit(eid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    p = await svc.permit_of(db, eid)
    if not p:
        raise error(404, "not_found")
    s = await svc.active_session(db, eid, lock=True)
    if s:
        await svc.end_session(db, s, now(), "permit_revoked")
    await audit(db, request, "mobile.permit_delete", actor=auth.user, entity="mobile_permit", entity_id=p.id, data={"employee_id": eid})
    await db.delete(p)
    await db.commit()


# --- Xodim sahifasi -----------------------------------------------------------------------


def _session_out(s: MobileSession | None) -> dict[str, Any] | None:
    if not s:
        return None
    return {"id": s.id, "status": s.status, "started_at": s.started_at, "ended_at": s.ended_at, "distance_km": float(s.distance_km), "points_count": s.points_count, "last_point_at": s.last_point_at, "last_battery": s.last_battery, "end_reason": s.end_reason}


@router.get("/my")
async def my(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    p = await svc.permit_of(db, e.id)
    s = await svc.active_session(db, e.id)
    moment = now()
    reason = None
    if p is None or not p.enabled:
        reason = "no_permit"
    elif p.consent_at is None:
        reason = "consent_required"
    elif not svc.in_window(p, moment):
        reason = "outside_hours"
    return {
        "employee": {"id": e.id, "name": e.full_name}, "permit": {"enabled": p.enabled, "interval_s": p.interval_s, "window_start": p.window_start.strftime("%H:%M"), "window_end": p.window_end.strftime("%H:%M"), "consent_at": p.consent_at} if p else None,
        "session": _session_out(s), "can_start": reason is None and s is None, "reason": reason,
        "privacy": {"retention_days": svc.RETENTION_DAYS, "only_in_session": True},
    }  # fmt: skip


@router.post("/my/consent")
async def consent(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    p = await svc.permit_of(db, e.id)
    if not p or not p.enabled:
        raise error(403, "no_permit")
    p.consent_at = now()
    await audit(db, request, "mobile.consent", actor=auth.user, entity="mobile_permit", entity_id=p.id, data={"employee_id": e.id})
    await db.commit()
    return {"consent_at": p.consent_at}


@router.delete("/my/consent", status_code=204)
async def revoke_consent(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    p = await svc.permit_of(db, e.id)
    if not p:
        raise error(404, "not_found")
    s = await svc.active_session(db, e.id, lock=True)
    if s:
        await svc.end_session(db, s, now(), "consent_revoked")
    p.consent_at = None
    await audit(db, request, "mobile.consent_revoke", actor=auth.user, entity="mobile_permit", entity_id=p.id, data={"employee_id": e.id})
    await db.commit()


class StartIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    permission: str = Field(default="granted", pattern="^(granted|denied|prompt|unknown)$")
    battery: int | None = Field(default=None, ge=0, le=100)


@router.post("/my/start", status_code=201)
async def start(body: StartIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    moment = now()
    svc.check_ready(await svc.permit_of(db, e.id), moment)
    if body.permission != "granted":
        raise error(400, "location_permission_required")
    if await svc.active_session(db, e.id, lock=True):
        raise error(409, "session_active")
    rec = await svc.attendance_check_in(db, e, moment, body.lat, body.lng)
    s = MobileSession(employee_id=e.id, status="active", started_at=moment, attendance_id=rec.id if rec else None, attendance_created=rec is not None, start_lat=body.lat, start_lng=body.lng, last_battery=body.battery, last_permission=body.permission)
    db.add(s)
    await db.flush()
    await audit(db, request, "mobile.start", actor=auth.user, entity="mobile_session", entity_id=s.id, data={"employee_id": e.id, "attendance": "created" if rec else "existing_or_none"})
    await db.commit()
    return _session_out(s)


class StopIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.post("/my/stop")
async def stop(body: StopIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    s = await svc.active_session(db, e.id, lock=True)
    if not s:
        raise error(409, "no_session")
    await svc.end_session(db, s, now(), "user", lat=body.lat, lng=body.lng)
    await audit(db, request, "mobile.stop", actor=auth.user, entity="mobile_session", entity_id=s.id, data={"employee_id": e.id, "distance_km": float(s.distance_km), "points": s.points_count})
    await db.commit()
    return _session_out(s)


class PointIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)
    speed: float | None = Field(default=None, ge=0, le=500)
    heading: float | None = Field(default=None, ge=0, le=360)
    at: datetime


class DeviceIn(BaseModel):
    battery: int | None = Field(default=None, ge=0, le=100)
    charging: bool | None = None
    permission: str | None = Field(default=None, pattern="^(granted|denied|prompt|unknown)$")
    gps_enabled: bool | None = None


class PointsIn(BaseModel):
    points: list[PointIn] = Field(default=[], max_length=svc.MAX_BATCH)
    device: DeviceIn = DeviceIn()


@router.post("/my/points")
async def points(body: PointsIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    e = await svc.employee_of(db, auth)
    moment = now()
    s = await svc.active_session(db, e.id, lock=True)
    if not s:
        raise error(409, "no_session")
    p = await svc.permit_of(db, e.id)
    if p is None or not p.enabled or p.consent_at is None:
        await svc.end_session(db, s, moment, "permit_revoked" if p is None or not p.enabled else "consent_revoked", auto=True)
        await db.commit()
        raise error(409, "session_closed")
    _, w_end = svc.window_dt(p, local_date(s.started_at))
    if moment > w_end + timedelta(minutes=svc.WINDOW_GRACE_MIN):
        await svc.end_session(db, s, min(moment, w_end), "window", auto=True)
        ev, notes = await svc.add_event(db, e, s, "auto_closed", moment)
        await db.commit()
        await deliver(request.app, notes)
        raise error(409, "session_closed")
    pts = [{"lat": x.lat, "lng": x.lng, "accuracy": x.accuracy, "speed": x.speed, "heading": x.heading, "at": x.at} for x in body.points]
    saved, skipped, notes = await svc.ingest(db, e, s, pts, body.device.model_dump(), moment)
    await db.commit()
    await deliver(request.app, notes)
    return {"saved": saved, "skipped": skipped, "interval_s": p.interval_s, "session": _session_out(s)}


class SosIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=500)
    battery: int | None = Field(default=None, ge=0, le=100)


@router.post("/my/sos", status_code=201)
async def sos(body: SosIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    """Favqulodda signal: darhol menejerlarga (ilova va Telegram) yuboriladi. Sessiyasiz ham ishlaydi."""
    e = await svc.employee_of(db, auth)
    s = await svc.active_session(db, e.id)
    ev, notes = await svc.add_event(db, e, s, "sos", now(), data={"note": (body.note or "").strip() or None, "battery": body.battery}, lat=body.lat, lng=body.lng)
    await audit(db, request, "mobile.sos", actor=auth.user, entity="mobile_event", entity_id=ev.id, data={"employee_id": e.id})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": ev.id}


# --- Jonli xarita, sessiyalar, hodisalar --------------------------------------------------


@router.get("/live")
async def live(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    """Faol sessiyalarning oxirgi joylashuvi (har so'rov auditga yozilmaydi: jonli ko'rinish; trek tarixi esa yoziladi)."""
    rows = list((await db.scalars(select(MobileSession).where(MobileSession.status == "active"))).all())
    if not rows:
        return []
    last = select(MobilePoint.session_id, func.max(MobilePoint.recorded_at).label("t")).where(MobilePoint.session_id.in_([s.id for s in rows])).group_by(MobilePoint.session_id).subquery()
    pts = {p.session_id: p for p in (await db.scalars(select(MobilePoint).join(last, (MobilePoint.session_id == last.c.session_id) & (MobilePoint.recorded_at == last.c.t)))).all()}
    emps = await _names(db, {s.employee_id for s in rows})
    open_ev = dict((await db.execute(select(MobileEvent.employee_id, func.count()).where(MobileEvent.acknowledged_at.is_(None), MobileEvent.severity != "info").group_by(MobileEvent.employee_id))).all())
    moment = now()
    out = []
    for s in rows:
        p = pts.get(s.id)
        e = emps.get(s.employee_id)
        out.append({
            "session_id": s.id, "employee": {"id": s.employee_id, "name": e.full_name if e else None}, "started_at": s.started_at, "lat": p.lat if p else s.start_lat, "lng": p.lng if p else s.start_lng,
            "accuracy": p.accuracy_m if p else None, "speed": p.speed_kmh if p else None, "at": p.recorded_at if p else s.started_at, "battery": s.last_battery, "permission": s.last_permission, "gps_off": s.gps_off,
            "stale": (moment - (s.last_point_at or s.started_at)) > timedelta(minutes=svc.SIGNAL_LOST_MIN), "distance_km": float(s.distance_km), "open_events": open_ev.get(s.employee_id, 0),
        })  # fmt: skip
    return out


@router.get("/sessions")
async def sessions(
    employee_id: int | None = None,
    status: str | None = Query(default=None, pattern="^(active|ended|auto_closed)$"),
    start: date | None = None,
    end: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    S = MobileSession
    conds: list = []
    if employee_id:
        conds.append(S.employee_id == employee_id)
    if status:
        conds.append(S.status == status)
    if start:
        conds.append(S.started_at >= datetime.combine(start, datetime.min.time(), tzinfo=tz()))
    if end:
        conds.append(S.started_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz()))
    total = await db.scalar(select(func.count()).select_from(S).where(*conds)) or 0
    rows = (await db.scalars(select(S).where(*conds).order_by(S.started_at.desc(), S.id.desc()).offset((page - 1) * size).limit(size))).all()
    emps = await _names(db, {s.employee_id for s in rows})
    return {"total": total, "page": page, "size": size, "items": [{**_session_out(s), "employee": {"id": s.employee_id, "name": emps[s.employee_id].full_name if s.employee_id in emps else None}} for s in rows]}  # type: ignore[dict-item]


async def _session(db: AsyncSession, sid: int) -> MobileSession:
    s = await db.get(MobileSession, sid)
    if not s:
        raise error(404, "not_found")
    return s


@router.get("/sessions/{sid}")
async def session(sid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    s = await _session(db, sid)
    e = await db.get(Employee, s.employee_id)
    evs = (await db.scalars(select(MobileEvent).where(MobileEvent.session_id == s.id).order_by(MobileEvent.created_at))).all()
    return {**_session_out(s), "employee": {"id": s.employee_id, "name": e.full_name if e else None}, "attendance_id": s.attendance_id, "attendance_created": s.attendance_created, "events": [_event_out(x, e) for x in evs]}  # type: ignore[dict-item]


@router.get("/sessions/{sid}/track")
async def session_track(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    """Trek tarixini ko'rish maxfiy ma'lumot: har ko'rish auditga yoziladi."""
    s = await _session(db, sid)
    pts = (await db.scalars(select(MobilePoint).where(MobilePoint.session_id == s.id).order_by(MobilePoint.recorded_at))).all()
    await audit(db, request, "mobile.view_track", actor=auth.user, entity="mobile_session", entity_id=s.id, data={"employee_id": s.employee_id})
    await db.commit()
    step = max(1, len(pts) // 1000)
    return {"session_id": s.id, "total": len(pts), "points": [{"lat": p.lat, "lng": p.lng, "speed": p.speed_kmh, "battery": p.battery, "at": p.recorded_at} for p in pts[::step]]}


def _event_out(ev: MobileEvent, e: Employee | None) -> dict[str, Any]:
    return {"id": ev.id, "session_id": ev.session_id, "employee": {"id": ev.employee_id, "name": e.full_name if e else None}, "kind": ev.kind, "severity": ev.severity, "data": ev.data, "lat": ev.lat, "lng": ev.lng, "created_at": ev.created_at, "acknowledged_at": ev.acknowledged_at, "ack_note": ev.ack_note}  # fmt: skip


@router.get("/events")
async def events(
    kind: str | None = None,
    open_only: bool = False,
    employee_id: int | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    E = MobileEvent
    conds: list = []
    if kind:
        conds.append(E.kind == kind)
    if open_only:
        conds += [E.acknowledged_at.is_(None), E.severity != "info"]
    if employee_id:
        conds.append(E.employee_id == employee_id)
    total = await db.scalar(select(func.count()).select_from(E).where(*conds)) or 0
    rows = (await db.scalars(select(E).where(*conds).order_by(E.created_at.desc(), E.id.desc()).offset((page - 1) * size).limit(size))).all()
    emps = await _names(db, {r.employee_id for r in rows})
    return {"total": total, "page": page, "size": size, "items": [_event_out(r, emps.get(r.employee_id)) for r in rows]}


class AckIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.post("/events/{eid}/ack")
async def ack(eid: int, body: AckIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    ev = await db.get(MobileEvent, eid)
    if not ev:
        raise error(404, "not_found")
    if ev.acknowledged_at:
        raise error(409, "already_acknowledged")
    ev.acknowledged_at, ev.acknowledged_by, ev.ack_note = now(), auth.user.id, (body.note or "").strip() or None
    await audit(db, request, "mobile.ack", actor=auth.user, entity="mobile_event", entity_id=ev.id, data={"kind": ev.kind})
    await db.commit()
    return _event_out(ev, await db.get(Employee, ev.employee_id))
