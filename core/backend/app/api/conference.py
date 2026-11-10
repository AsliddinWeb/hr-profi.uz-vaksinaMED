"""Onlayn konferensiya / dars (100 kishigacha) — oflayn darslar o'rniga.

Rejalashtirish (auditoriya: hamma, lavozim, filial, bo'lim) -> qatnashchilarga bildirishnoma -> LiveKit xonasi
(kirish tokeni, qatnashuv yurak urishi bilan hisoblanadi) -> tugagach: qatnashchilarga avtomatik topshiriqlar,
kelmaganlarga yozuvni ko'rish topshirig'i, qatnashuv hisoboti.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, get_auth, require_any
from app.models.auth import User
from app.models.employees import Employee
from app.models.smart import Conference, ConferenceAttendee
from app.models.tasks import Task
from app.rbac import matches
from app.services import calls
from app.services import tasks as task_svc
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import now

router = APIRouter(prefix="/v1/conferences", tags=["conferences"])
Manage = require_any("conference.manage")
LIVE_WINDOW_S = 75
MAX_CAPACITY = 100

register_template("conference.scheduled", {"uz": "Onlayn dars rejalashtirildi", "ru": "Запланировано онлайн-занятие"}, {"uz": "{title}: {when}", "ru": "{title}: {when}"}, "info")
register_template("conference.started", {"uz": "Onlayn dars boshlandi", "ru": "Онлайн-занятие началось"}, {"uz": "{title} — qo'shiling", "ru": "{title} — подключайтесь"}, "warning")


class AudienceIn(BaseModel):
    all: bool = False
    position_ids: list[int] = Field(default_factory=list, max_length=50)
    branch_ids: list[int] = Field(default_factory=list, max_length=200)
    department_ids: list[int] = Field(default_factory=list, max_length=50)


class TaskSpec(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_days: int = Field(default=3, ge=0, le=60)


class ConferenceIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime
    duration_min: int = Field(default=60, ge=10, le=480)
    capacity: int = Field(default=MAX_CAPACITY, ge=2, le=MAX_CAPACITY)
    audience: AudienceIn = Field(default_factory=AudienceIn)
    tasks: list[TaskSpec] = Field(default_factory=list, max_length=10)
    auto_tasks_for_absent: bool = True
    recording_url: str | None = Field(default=None, max_length=500)


def _can_manage(auth: AuthContext) -> bool:
    return matches(auth.permissions, "conference.manage")


async def audience_users(db: AsyncSession, aud: dict[str, Any]) -> list[int]:
    """Auditoriyadagi faol foydalanuvchilar (xodim kartochkasi bo'yicha). `all` — barcha faol xodimlar."""
    stmt = select(User.id).join(Employee, Employee.user_id == User.id).where(User.is_active.is_(True), Employee.status == "active")
    if not aud.get("all"):
        conds = []
        if aud.get("position_ids"):
            conds.append(Employee.position_id.in_(aud["position_ids"]))
        if aud.get("branch_ids"):
            conds.append(Employee.branch_id.in_(aud["branch_ids"]))
        if aud.get("department_ids"):
            conds.append(Employee.department_id.in_(aud["department_ids"]))
        if not conds:
            return []
        from sqlalchemy import or_  # noqa: PLC0415

        stmt = stmt.where(or_(*conds))
    return [r for (r,) in (await db.execute(stmt.limit(5000))).all()]


async def _invited(db: AsyncSession, c: Conference) -> set[int]:
    return set(await audience_users(db, c.audience or {})) | ({c.host_id} if c.host_id else set())


async def _out(db: AsyncSession, c: Conference, auth: AuthContext, moment: datetime) -> dict[str, Any]:
    live = await db.scalar(select(func.count()).select_from(ConferenceAttendee).where(ConferenceAttendee.conference_id == c.id, ConferenceAttendee.last_seen_at >= moment - timedelta(seconds=LIVE_WINDOW_S))) or 0
    attended = await db.scalar(select(func.count()).select_from(ConferenceAttendee).where(ConferenceAttendee.conference_id == c.id)) or 0
    host = await db.get(User, c.host_id) if c.host_id else None
    return {
        "id": c.id, "title": c.title, "description": c.description, "starts_at": c.starts_at, "duration_min": c.duration_min, "capacity": c.capacity,
        "audience": c.audience, "status": c.status, "tasks": c.tasks, "auto_tasks_for_absent": c.auto_tasks_for_absent, "recording_url": c.recording_url,
        "started_at": c.started_at, "ended_at": c.ended_at, "host": {"id": host.id, "name": host.full_name} if host else None,
        "online": live, "attended": attended, "report": c.report if c.status == "ended" else None,
        "can": {"manage": _can_manage(auth), "host": c.host_id == auth.user.id or _can_manage(auth)},
    }  # fmt: skip


async def _get(db: AsyncSession, cid: int, auth: AuthContext, *, lock: bool = False) -> Conference:
    stmt = select(Conference).where(Conference.id == cid)
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not c:
        raise error(404, "not_found")
    if not (_can_manage(auth) or matches(auth.permissions, "conference.read") or auth.user.id in await _invited(db, c)):
        raise error(404, "not_found")
    return c


@router.get("")
async def list_(scope: str = Query(default="upcoming", pattern="^(upcoming|past|all)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    moment = now()
    stmt = select(Conference).order_by(Conference.starts_at.desc() if scope == "past" else Conference.starts_at).limit(200)
    if scope == "upcoming":
        stmt = stmt.where(Conference.status.in_(("scheduled", "live")))
    elif scope == "past":
        stmt = stmt.where(Conference.status.in_(("ended", "cancelled")))
    rows = (await db.scalars(stmt)).all()
    if not (_can_manage(auth) or matches(auth.permissions, "conference.read")):
        mine = [c for c in rows if auth.user.id == c.host_id or auth.user.id in set(await audience_users(db, c.audience or {}))]
        rows = mine
    return {"items": [await _out(db, c, auth, moment) for c in rows], "can_manage": _can_manage(auth)}


@router.post("", status_code=201)
async def create(body: ConferenceIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    aud = body.audience.model_dump()
    if not aud["all"] and not (aud["position_ids"] or aud["branch_ids"] or aud["department_ids"]):
        raise error(400, "audience_required")
    c = Conference(title=body.title.strip(), description=body.description, room=f"conf-{secrets.token_hex(8)}", host_id=auth.user.id, starts_at=body.starts_at,
                   duration_min=body.duration_min, capacity=body.capacity, audience=aud, tasks=[t.model_dump() for t in body.tasks],
                   auto_tasks_for_absent=body.auto_tasks_for_absent, recording_url=body.recording_url, created_by=auth.user.id)  # fmt: skip
    db.add(c)
    await db.flush()
    targets = [u for u in await audience_users(db, aud) if u != auth.user.id]
    notes = await notify(db, targets, "conference.scheduled", link=f"/conferences/{c.id}", params={"title": c.title, "when": c.starts_at.strftime("%d.%m %H:%M")})
    await audit(db, request, "conference.create", actor=auth.user, entity="conference", entity_id=c.id, data={"invited": len(targets)})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, c, auth, now())


@router.get("/{cid}")
async def get_one(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    return await _out(db, await _get(db, cid, auth), auth, now())


class PatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=10, le=480)
    tasks: list[TaskSpec] | None = Field(default=None, max_length=10)
    recording_url: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(cancelled)$")


@router.patch("/{cid}")
async def patch(cid: int, body: PatchIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await _get(db, cid, auth, lock=True)
    sent = body.model_fields_set
    for f in ("title", "description", "starts_at", "duration_min", "recording_url"):
        if f in sent and getattr(body, f) is not None:
            setattr(c, f, getattr(body, f))
    if "tasks" in sent and body.tasks is not None:
        c.tasks = [t.model_dump() for t in body.tasks]
    if body.status == "cancelled" and c.status == "scheduled":
        c.status = "cancelled"
    await db.commit()
    return await _out(db, c, auth, now())


@router.post("/{cid}/join")
async def join(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Xonaga kirish tokeni. Boshlovchi kirsa dars "live" bo'ladi. 100 kishilik chegara onlayn qatnashchilar bo'yicha."""
    c = await _get(db, cid, auth, lock=True)
    moment = now()
    host = c.host_id == auth.user.id or _can_manage(auth)
    if c.status in ("ended", "cancelled"):
        raise error(409, "conference_closed")
    if c.status == "scheduled" and not host and moment < c.starts_at - timedelta(minutes=15):
        raise error(409, "not_started")
    if not calls.enabled():
        raise error(503, "video_disabled")
    online = await db.scalar(select(func.count()).select_from(ConferenceAttendee).where(ConferenceAttendee.conference_id == c.id, ConferenceAttendee.user_id != auth.user.id, ConferenceAttendee.last_seen_at >= moment - timedelta(seconds=LIVE_WINDOW_S))) or 0
    if online >= c.capacity:
        raise error(409, "conference_full", capacity=c.capacity)
    notes: list[Any] = []
    if host and c.status == "scheduled":
        c.status, c.started_at = "live", moment
        notes = await notify(db, [u for u in await audience_users(db, c.audience or {}) if u != auth.user.id], "conference.started", link=f"/conferences/{c.id}/room", params={"title": c.title})
    a = await db.scalar(select(ConferenceAttendee).where(ConferenceAttendee.conference_id == c.id, ConferenceAttendee.user_id == auth.user.id))
    if a:
        a.joins, a.last_seen_at = a.joins + 1, moment
    else:
        db.add(ConferenceAttendee(conference_id=c.id, user_id=auth.user.id, first_join_at=moment, last_seen_at=moment))
    grant = {"roomJoin": True, "room": c.room, "canPublish": True, "canSubscribe": True, "canPublishData": True, "roomAdmin": host}
    token = calls._sign({"name": auth.user.full_name, "video": grant}, (c.duration_min + 60) * 60, calls.identity_of(auth.user.id))
    await db.commit()
    await deliver(request.app, notes)
    return {"token": token, "url": get_settings().livekit_public_url or None, "room": c.room, "host": host, "title": c.title}


@router.post("/{cid}/heartbeat", status_code=204)
async def heartbeat(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Har ~30 soniyada: qatnashuv vaqti (ikki yurak urishi orasi 75 soniyadan oshsa, uzilish deb hisoblanadi)."""
    moment = now()
    a = await db.scalar(select(ConferenceAttendee).where(ConferenceAttendee.conference_id == cid, ConferenceAttendee.user_id == auth.user.id).with_for_update())
    if not a:
        raise error(404, "not_found")
    gap = (moment - a.last_seen_at).total_seconds()
    if 0 < gap <= LIVE_WINDOW_S:
        a.seconds += int(gap)
    a.last_seen_at = moment
    await db.commit()


async def build_report(db: AsyncSession, c: Conference) -> dict[str, Any]:
    invited = await _invited(db, c)
    rows = (await db.execute(select(ConferenceAttendee, User.full_name).join(User, User.id == ConferenceAttendee.user_id).where(ConferenceAttendee.conference_id == c.id))).all()
    full = c.duration_min * 60
    people = [{"user_id": a.user_id, "name": n, "minutes": round(a.seconds / 60), "pct": min(100, round(a.seconds / full * 100)) if full else 0, "joins": a.joins} for a, n in rows]
    came = {p["user_id"] for p in people}
    absent_ids = sorted(invited - came)
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(absent_ids)))).all()} if absent_ids else {}
    return {
        "invited": len(invited), "attended": len(came & invited) if invited else len(came), "attendance_pct": round(len(came & invited) / len(invited) * 100) if invited else 0,
        "avg_minutes": round(sum(p["minutes"] for p in people) / len(people)) if people else 0,
        "people": sorted(people, key=lambda x: -x["minutes"]), "absent": [{"user_id": u, "name": names.get(u, "—")} for u in absent_ids][:500],
    }  # fmt: skip


@router.post("/{cid}/end")
async def end(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Darsni yakunlash: hisobot, qatnashchilarga topshiriqlar, kelmaganlarga yozuvni ko'rish topshirig'i."""
    c = await _get(db, cid, auth, lock=True)
    if not (c.host_id == auth.user.id or _can_manage(auth)):
        raise error(403, "forbidden")
    if c.status in ("ended", "cancelled"):
        raise error(409, "conference_closed")
    moment = now()
    c.status, c.ended_at = "ended", moment
    report = await build_report(db, c)
    created = 0
    attendees = [p["user_id"] for p in report["people"] if p["user_id"] != c.host_id]
    for spec in c.tasks or []:
        for uid in attendees:
            t = Task(title=spec["title"][:200], description=(spec.get("description") or "") + f"\n\nOnlayn dars: {c.title}", priority="normal",
                     due_at=moment + timedelta(days=int(spec.get("due_days") or 3)), creator_id=c.host_id or auth.user.id, assignee_id=uid,
                     position=await task_svc.next_position(db, "todo"), labels=["onlayn-dars"])  # fmt: skip
            db.add(t)
            created += 1
    if c.auto_tasks_for_absent:
        for p in report["absent"]:
            if p["user_id"] == c.host_id:
                continue
            desc = f"Siz «{c.title}» onlayn darsida qatnashmadingiz. " + (f"Yozuvni ko'ring: {c.recording_url}" if c.recording_url else "Material va yozuvni boshlovchidan oling.")
            db.add(Task(title=f"Darsni o'zlashtirish: {c.title}"[:200], description=desc, priority="high", due_at=moment + timedelta(days=2),
                        creator_id=c.host_id or auth.user.id, assignee_id=p["user_id"], position=await task_svc.next_position(db, "todo"), labels=["onlayn-dars", "qatnashmagan"]))  # fmt: skip
            created += 1
    c.report = {**report, "tasks_created": created}
    await audit(db, request, "conference.end", actor=auth.user, entity="conference", entity_id=c.id, data={"attended": report["attended"], "tasks": created})
    await db.commit()
    return await _out(db, c, auth, moment)
