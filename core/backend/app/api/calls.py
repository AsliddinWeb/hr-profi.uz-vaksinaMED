"""Qo'ng'iroqlar: bevosita qo'ng'iroq va konferensiya (LiveKit), tarix, webhook."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.calls import Call, CallParticipant
from app.services import calls as svc
from app.services.audit import audit
from app.services.notifications import deliver
from app.timeutil import now

router = APIRouter(prefix="/v1/calls", tags=["calls"])


async def Access(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not (svc.has(auth, "calls.own") or svc.viewer(auth)):
        raise error(403, "forbidden")
    return auth


async def _call(db: AsyncSession, call_id: int, auth: AuthContext, *, lock: bool = False) -> Call:
    stmt = select(Call).where(Call.id == call_id)
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not c:
        raise error(404, "not_found")
    if not svc.can_view(auth, await svc.participants(db, c.id)):
        raise error(404, "not_found")
    return c


async def _out(db: AsyncSession, c: Call, auth: AuthContext) -> dict[str, Any]:
    parts = await svc.participants(db, c.id)
    nm = await svc.names(db, {c.host_id, *(p.user_id for p in parts)})
    out = svc.call_out(c, parts, nm, auth.user.id)
    me = out["me"]
    live = c.status in svc.LIVE
    out["can"] = {
        "join": bool(me) and live and not (me["status"] == "declined" and c.kind == "direct"),
        "decline": bool(me) and me["role"] == "invitee" and live and me["status"] in ("invited", "missed"),
        "end": live and (c.host_id == auth.user.id or svc.admin(auth)),
        "edit": c.kind == "conference" and c.status == "scheduled" and c.host_id == auth.user.id,
    }
    return out


@router.get("/config")
async def config(auth: AuthContext = Depends(Access)):
    return {"enabled": svc.enabled(), "public_url": get_settings().livekit_public_url or None, "ring_seconds": svc.RING_SECONDS}


@router.get("/users")
async def users(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    stmt = select(User.id, User.full_name).where(User.is_active.is_(True), User.id != auth.user.id)
    if q and q.strip():
        stmt = stmt.where(User.full_name.ilike(f"%{q.strip()}%"))
    return [{"id": r.id, "name": r.full_name} for r in (await db.execute(stmt.order_by(User.full_name).limit(30))).all()]


@router.get("/incoming")
async def incoming(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Menga qo'ng'iroq qilinayotganlar (jiringlayotgan, muddati o'tmagan)."""
    moment = now()
    rows = (await db.scalars(
        select(Call).join(CallParticipant, CallParticipant.call_id == Call.id)
        .where(Call.kind == "direct", Call.status == "ringing", Call.ring_until > moment, CallParticipant.user_id == auth.user.id, CallParticipant.role == "invitee", CallParticipant.status == "invited")
        .order_by(Call.id.desc()).limit(5)
    )).all()  # fmt: skip
    nm = await svc.names(db, {c.host_id for c in rows})
    return [{"id": c.id, "media": c.media, "caller": nm.get(c.host_id or 0), "ring_until": c.ring_until} for c in rows]


@router.get("")
async def listing(
    scope: str = Query(default="mine", pattern="^(mine|live|all)$"),
    status: str | None = Query(default=None, pattern="^(ringing|scheduled|active|ended|declined|missed|cancelled)$"),
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    C, P = Call, CallParticipant
    conds: list = []
    if scope == "all":
        if not svc.viewer(auth):
            raise error(403, "forbidden")
    else:
        conds.append(C.id.in_(select(P.call_id).where(P.user_id == auth.user.id)))
    if scope == "live":
        conds.append(C.status.in_(("scheduled", "active", "ringing")))
    if status:
        conds.append(C.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(C.title.ilike(like), C.id.in_(select(P.call_id).join(User, User.id == P.user_id).where(User.full_name.ilike(like)))))
    total = await db.scalar(select(func.count()).select_from(C).where(*conds)) or 0
    order = (C.created_at.desc(), C.id.desc()) if scope != "live" else (func.coalesce(C.scheduled_at, C.created_at), C.id)
    rows = list((await db.scalars(select(C).where(*conds).order_by(*order).offset((page - 1) * size).limit(size))).all())
    ids = [c.id for c in rows]
    parts = list((await db.scalars(select(P).where(P.call_id.in_(ids)).order_by(P.id))).all()) if ids else []
    nm = await svc.names(db, {x for c in rows for x in (c.host_id,)} | {p.user_id for p in parts})
    items = []
    for c in rows:
        out = svc.call_out(c, [p for p in parts if p.call_id == c.id], nm, auth.user.id)
        items.append(out)
    return {"total": total, "page": page, "size": size, "items": items}


class CallIn(BaseModel):
    kind: str = Field(default="direct", pattern="^(direct|conference)$")
    media: str = Field(default="video", pattern="^(audio|video)$")
    title: str | None = Field(default=None, max_length=200)
    scheduled_at: datetime | None = None
    invitee_ids: list[int] = Field(default_factory=list, max_length=60)


@router.post("", status_code=201)
async def create(body: CallIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    if not svc.has(auth, "calls.own"):
        raise error(403, "forbidden")
    c, notes = await svc.create(db, auth, kind=body.kind, media=body.media, title=body.title, scheduled_at=body.scheduled_at, invitee_ids=body.invitee_ids, moment=now())
    await audit(db, request, "calls.create", actor=auth.user, entity="call", entity_id=c.id, data={"kind": c.kind, "media": c.media, "invitees": body.invitee_ids})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, c, auth)


@router.post("/webhook")
async def webhook(request: Request, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_session)):
    """LiveKit server chaqiradi (ichki tarmoq). Imzo va tana hash i tekshiriladi."""
    event = svc.verify_webhook(await request.body(), authorization)
    await svc.handle_webhook(db, event, now())
    await db.commit()
    return {"ok": True}


@router.get("/{call_id}")
async def detail(call_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    return await _out(db, await _call(db, call_id, auth), auth)


@router.put("/{call_id}")
async def update(call_id: int, body: CallIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    c = await _call(db, call_id, auth, lock=True)
    notes = await svc.update_conference(db, c, auth, title=body.title, media=body.media, scheduled_at=body.scheduled_at, invitee_ids=body.invitee_ids, moment=now())
    await audit(db, request, "calls.update", actor=auth.user, entity="call", entity_id=c.id, data={"invitees": body.invitee_ids})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, c, auth)


@router.post("/{call_id}/token")
async def token(call_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    c = await _call(db, call_id, auth, lock=True)
    tok = await svc.join(db, c, auth, now())
    await db.commit()
    s = get_settings()
    return {"token": tok, "url": s.livekit_public_url or None, "room": c.room_name, "identity": svc.identity_of(auth.user.id), "media": c.media}


@router.post("/{call_id}/leave")
async def leave(call_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    c = await _call(db, call_id, auth, lock=True)
    await svc.leave(db, c, auth.user.id, now())
    await db.commit()
    return await _out(db, c, auth)


@router.post("/{call_id}/decline")
async def decline(call_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    c = await _call(db, call_id, auth, lock=True)
    notes = await svc.decline(db, c, auth, now())
    await audit(db, request, "calls.decline", actor=auth.user, entity="call", entity_id=c.id, data={})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, c, auth)


@router.post("/{call_id}/end")
async def end(call_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    c = await _call(db, call_id, auth, lock=True)
    await svc.end(db, c, auth, now())
    await audit(db, request, "calls.end", actor=auth.user, entity="call", entity_id=c.id, data={"by_host": c.host_id == auth.user.id})
    await db.commit()
    return await _out(db, c, auth)
