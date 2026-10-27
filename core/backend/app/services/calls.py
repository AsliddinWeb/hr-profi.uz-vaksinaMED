"""Qo'ng'iroqlar (LiveKit): xona, token, qo'ng'iroq/konferensiya holatlari, qatnashchilar vaqti, webhook va nazorat."""

import base64
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import AuthContext, error
from app.models.auth import User
from app.models.calls import Call, CallParticipant
from app.rbac import matches
from app.services.notifications import notify, register_template

RING_SECONDS = 45
EARLY_JOIN_MINUTES = 15
EMPTY_END_MINUTES = 15
STALE_HOURS = 12
TOKEN_TTL_SECONDS = 2 * 3600
LIVE = ("ringing", "scheduled", "active")

for _k, _uz, _ru, _body_uz, _body_ru, _lvl in (
    ("incoming", "Kiruvchi qo'ng'iroq", "Входящий звонок", "{caller}", "{caller}", "info"),
    ("invited", "Konferensiyaga taklif", "Приглашение на конференцию", "{caller}: {title}", "{caller}: {title}", "info"),
    ("missed", "O'tkazib yuborilgan qo'ng'iroq", "Пропущенный звонок", "{caller}", "{caller}", "warning"),
    ("declined", "Qo'ng'iroq rad etildi", "Звонок отклонён", "{name}", "{name}", "warning"),
):
    register_template(f"calls.{_k}", {"uz": _uz, "ru": _ru}, {"uz": _body_uz, "ru": _body_ru}, _lvl)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def admin(auth: AuthContext) -> bool:
    return has(auth, "calls.manage")


def viewer(auth: AuthContext) -> bool:
    return has(auth, "calls.read") or admin(auth)


def enabled() -> bool:
    s = get_settings()
    return bool(s.livekit_api_key and s.livekit_api_secret)


def identity_of(user_id: int) -> str:
    return f"u{user_id}"


def user_of(identity: str) -> int | None:
    return int(identity[1:]) if identity.startswith("u") and identity[1:].isdigit() else None


def _sign(claims: dict[str, Any], ttl: int, identity: str | None = None) -> str:
    s = get_settings()
    now_ = int(time.time())
    payload = {"iss": s.livekit_api_key, "nbf": now_ - 5, "exp": now_ + ttl, **claims}
    if identity:
        payload["sub"] = identity
    return jwt.encode(payload, s.livekit_api_secret, algorithm="HS256")


def make_token(user: User, call: Call) -> str:
    """Brauzer uchun xonaga kirish tokeni. Kamera, mikrofon va ekran ulashish ruxsat etilgan."""
    grant = {"roomJoin": True, "room": call.room_name, "canPublish": True, "canSubscribe": True, "canPublishData": True}
    return _sign({"name": user.full_name, "video": grant, "metadata": f'{{"user_id":{user.id}}}'}, TOKEN_TTL_SECONDS, identity_of(user.id))


async def _twirp(method: str, body: dict[str, Any], room: str) -> bool:
    """LiveKit server API (RoomService). Xato asosiy amalni buzmasligi kerak."""
    s = get_settings()
    token = _sign({"video": {"roomCreate": True, "roomAdmin": True, "room": room}}, 60)
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.post(f"{s.livekit_internal_url}/twirp/livekit.RoomService/{method}", json=body, headers={"Authorization": f"Bearer {token}"})
        return r.status_code < 300
    except httpx.HTTPError:
        return False


async def close_room(call: Call) -> bool:
    if not enabled():
        return False
    return await _twirp("DeleteRoom", {"room": call.room_name}, call.room_name)


def verify_webhook(body: bytes, authorization: str | None) -> dict[str, Any]:
    """LiveKit webhook: Authorization = JWT (sir bilan imzolangan), `sha256` = tananing base64 hash."""
    s = get_settings()
    if not enabled() or not authorization:
        raise error(401, "invalid_webhook")
    try:
        claims = jwt.decode(authorization.removeprefix("Bearer ").strip(), s.livekit_api_secret, algorithms=["HS256"], issuer=s.livekit_api_key)
    except jwt.PyJWTError:
        raise error(401, "invalid_webhook") from None
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    if claims.get("sha256") != digest:
        raise error(401, "invalid_webhook")
    import json

    try:
        return json.loads(body)
    except ValueError:
        raise error(400, "invalid_webhook") from None


def new_room() -> str:
    return "call-" + secrets.token_hex(8)


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


async def participants(db: AsyncSession, call_id: int) -> list[CallParticipant]:
    return list((await db.scalars(select(CallParticipant).where(CallParticipant.call_id == call_id).order_by(CallParticipant.id))).all())


def my_part(parts: list[CallParticipant], user_id: int) -> CallParticipant | None:
    return next((p for p in parts if p.user_id == user_id), None)


def can_view(auth: AuthContext, parts: list[CallParticipant]) -> bool:
    return viewer(auth) or my_part(parts, auth.user.id) is not None


async def valid_invitees(db: AsyncSession, ids: list[int], me: int) -> list[int]:
    uniq = list(dict.fromkeys(i for i in ids if i != me))
    if not uniq:
        return []
    found = set((await db.scalars(select(User.id).where(User.id.in_(uniq), User.is_active.is_(True)))).all())
    if found != set(uniq):
        raise error(400, "unknown_user")
    return uniq


async def create(db: AsyncSession, auth: AuthContext, *, kind: str, media: str, title: str | None, scheduled_at: datetime | None, invitee_ids: list[int], moment: datetime):
    if not enabled():
        raise error(503, "calls_disabled")
    invitees = await valid_invitees(db, invitee_ids, auth.user.id)
    if not invitees:
        raise error(400, "invitee_required")
    if kind == "direct":
        if len(invitees) != 1:
            raise error(400, "direct_one_user")
        dup = await db.scalar(
            select(func.count()).select_from(Call).join(CallParticipant, CallParticipant.call_id == Call.id)
            .where(Call.host_id == auth.user.id, Call.kind == "direct", Call.status == "ringing", CallParticipant.user_id == invitees[0], Call.ring_until > moment)
        )  # fmt: skip
        if dup:
            raise error(409, "already_calling")
    elif len(invitees) > 49:
        raise error(400, "too_many_invitees", max=49)
    call = Call(
        kind=kind, media=media, title=(title or "").strip() or None, room_name=new_room(), status="ringing" if kind == "direct" else "scheduled",
        host_id=auth.user.id, scheduled_at=scheduled_at if kind == "conference" else None, ring_until=moment + timedelta(seconds=RING_SECONDS) if kind == "direct" else None,
    )  # fmt: skip
    db.add(call)
    await db.flush()
    db.add(CallParticipant(call_id=call.id, user_id=auth.user.id, role="host", status="invited", invited_at=moment))
    for uid in invitees:
        db.add(CallParticipant(call_id=call.id, user_id=uid, status="invited", invited_at=moment))
    await db.flush()
    link = f"/calls/{call.id}"
    if kind == "direct":
        notes = await notify(db, invitees, "calls.incoming", link=link, params={"caller": auth.user.full_name})
    else:
        notes = await notify(db, invitees, "calls.invited", link=link, params={"caller": auth.user.full_name, "title": call.title or ""})
    return call, notes


def _close_session(p: CallParticipant, moment: datetime) -> None:
    if p.status == "joined":
        start = p.last_joined_at or moment
        p.total_seconds += max(0, int((moment - start).total_seconds()))
        p.status, p.left_at = "left", moment


def _mark_joined(call: Call, p: CallParticipant, moment: datetime) -> None:
    if p.status != "joined":
        p.status, p.last_joined_at, p.left_at = "joined", moment, None
        p.first_joined_at = p.first_joined_at or moment
    if call.status in ("ringing", "scheduled") and (call.kind == "conference" or p.role == "invitee"):
        call.status, call.started_at = "active", call.started_at or moment
    call.empty_since = None


def _finish(call: Call, status: str, actor_id: int | None, reason: str | None, moment: datetime) -> None:
    call.status, call.ended_at, call.ended_by, call.end_reason = status, moment, actor_id, reason


async def join(db: AsyncSession, call: Call, auth: AuthContext, moment: datetime) -> str:
    if not enabled():
        raise error(503, "calls_disabled")
    parts = await participants(db, call.id)
    p = my_part(parts, auth.user.id)
    if not p:
        raise error(404, "not_found")
    if call.status not in LIVE or (call.status == "ringing" and call.ring_until and call.ring_until <= moment and p.role == "invitee"):
        raise error(409, "invalid_transition")
    if p.status == "declined" and call.kind == "direct":
        raise error(409, "invalid_transition")
    if call.kind == "conference" and p.role == "invitee" and call.status == "scheduled" and call.scheduled_at and moment < call.scheduled_at - timedelta(minutes=EARLY_JOIN_MINUTES):
        raise error(409, "too_early")
    _mark_joined(call, p, moment)
    return make_token(auth.user, call)


async def leave(db: AsyncSession, call: Call, user_id: int, moment: datetime) -> None:
    parts = await participants(db, call.id)
    p = my_part(parts, user_id)
    if not p:
        return
    _close_session(p, moment)
    await after_change(call, parts, p, moment)


async def after_change(call: Call, parts: list[CallParticipant], who: CallParticipant | None, moment: datetime) -> None:
    online = [x for x in parts if x.status == "joined"]
    if call.status == "ringing" and who and who.role == "host" and not online:
        _finish(call, "cancelled", who.user_id, "host", moment)
        for x in parts:
            if x.status == "invited":
                x.status = "missed"
        return
    if call.status == "active" and not online:
        if call.kind == "direct":
            _finish(call, "ended", None, "empty", moment)
            await close_room(call)
        else:
            call.empty_since = call.empty_since or moment


async def decline(db: AsyncSession, call: Call, auth: AuthContext, moment: datetime):
    parts = await participants(db, call.id)
    p = my_part(parts, auth.user.id)
    if not p or p.role != "invitee":
        raise error(404, "not_found")
    if call.status not in LIVE or p.status not in ("invited", "missed"):
        raise error(409, "invalid_transition")
    p.status = "declined"
    notes: list = []
    if call.kind == "direct":
        _finish(call, "declined", auth.user.id, None, moment)
        if call.host_id:
            notes = await notify(db, [call.host_id], "calls.declined", link=f"/calls/{call.id}", params={"name": auth.user.full_name})
    return notes


async def end(db: AsyncSession, call: Call, auth: AuthContext, moment: datetime) -> None:
    if call.host_id != auth.user.id and not admin(auth):
        raise error(403, "forbidden")
    if call.status not in LIVE:
        raise error(409, "invalid_transition")
    parts = await participants(db, call.id)
    for x in parts:
        _close_session(x, moment)
        if x.status == "invited":
            x.status = "missed" if call.status == "ringing" else x.status
    _finish(call, "ended" if call.started_at else "cancelled", auth.user.id, "host" if call.host_id == auth.user.id else "admin", moment)
    await close_room(call)


async def update_conference(db: AsyncSession, call: Call, auth: AuthContext, *, title, media, scheduled_at, invitee_ids: list[int], moment: datetime):
    if call.kind != "conference" or call.host_id != auth.user.id:
        raise error(403, "forbidden")
    if call.status != "scheduled":
        raise error(409, "invalid_transition")
    invitees = await valid_invitees(db, invitee_ids, auth.user.id)
    if not invitees:
        raise error(400, "invitee_required")
    if len(invitees) > 49:
        raise error(400, "too_many_invitees", max=49)
    call.title, call.media, call.scheduled_at = (title or "").strip() or None, media, scheduled_at
    parts = await participants(db, call.id)
    have = {p.user_id: p for p in parts}
    for p in parts:
        if p.role == "invitee" and p.user_id not in invitees:
            await db.delete(p)
    fresh = [u for u in invitees if u not in have]
    for uid in fresh:
        db.add(CallParticipant(call_id=call.id, user_id=uid, status="invited", invited_at=moment))
    await db.flush()
    return await notify(db, fresh, "calls.invited", link=f"/calls/{call.id}", params={"caller": auth.user.full_name, "title": call.title or ""})


async def handle_webhook(db: AsyncSession, event: dict[str, Any], moment: datetime) -> None:
    """participant_joined / participant_left / room_finished: mijoz /leave ni chaqira olmagan hollarni to'g'rilaydi."""
    kind = event.get("event")
    room = (event.get("room") or {}).get("name")
    if not room:
        return
    call = await db.scalar(select(Call).where(Call.room_name == room).with_for_update())
    if not call:
        return
    if kind == "room_finished":
        if call.status in LIVE and call.status == "active":
            for x in await participants(db, call.id):
                _close_session(x, moment)
            _finish(call, "ended", None, "empty", moment)
        return
    uid = user_of((event.get("participant") or {}).get("identity", ""))
    if uid is None:
        return
    parts = await participants(db, call.id)
    p = my_part(parts, uid)
    if not p:
        return
    if kind == "participant_joined" and call.status in LIVE:
        _mark_joined(call, p, moment)
    elif kind == "participant_left":
        _close_session(p, moment)
        await after_change(call, parts, p, moment)


async def watch(db: AsyncSession, moment: datetime):
    """Javobsiz qo'ng'iroqlar (45 s) -> missed; bo'sh konferensiya 15 daq -> ended; 12 soatdan oshgan yoki hech boshlanmagan rejalar yopiladi."""
    notes: list = []
    ringing = (await db.scalars(select(Call).where(Call.status == "ringing", Call.ring_until <= moment))).all()
    for c in ringing:
        parts = await participants(db, c.id)
        callees = [p.user_id for p in parts if p.role == "invitee" and p.status == "invited"]
        for p in parts:
            if p.status == "invited" and p.role == "invitee":
                p.status = "missed"
            _close_session(p, moment)
        _finish(c, "missed", None, None, moment)
        await close_room(c)
        caller = (await names(db, {c.host_id})).get(c.host_id or 0, "")
        notes += await notify(db, callees, "calls.missed", link=f"/calls/{c.id}", params={"caller": caller})
    empty = (await db.scalars(select(Call).where(Call.status == "active", Call.empty_since.is_not(None), Call.empty_since <= moment - timedelta(minutes=EMPTY_END_MINUTES)))).all()
    stale = (await db.scalars(select(Call).where(Call.status == "active", Call.started_at <= moment - timedelta(hours=STALE_HOURS)))).all()
    unused = (await db.scalars(select(Call).where(Call.status == "scheduled", func.coalesce(Call.scheduled_at, Call.created_at) <= moment - timedelta(hours=6)))).all()
    for c, reason in [(x, "empty") for x in empty] + [(x, "stale") for x in stale if x not in empty]:
        for p in await participants(db, c.id):
            _close_session(p, moment)
        _finish(c, "ended", None, reason, moment)
        await close_room(c)
    for c in unused:
        _finish(c, "cancelled", None, "stale", moment)
    return len(ringing), len(empty) + len(stale) + len(unused), notes


def duration(call: Call) -> int | None:
    if call.started_at and call.ended_at:
        return max(0, int((call.ended_at - call.started_at).total_seconds()))
    return None


def part_out(p: CallParticipant, user_names: dict[int, str]) -> dict[str, Any]:
    return {
        "user_id": p.user_id, "name": user_names.get(p.user_id), "role": p.role, "status": p.status,
        "first_joined_at": p.first_joined_at, "left_at": p.left_at, "seconds": p.total_seconds,
    }  # fmt: skip


def call_out(call: Call, parts: list[CallParticipant], user_names: dict[int, str], me: int) -> dict[str, Any]:
    mine = my_part(parts, me)
    others = [p for p in parts if p.user_id != me]
    return {
        "id": call.id, "kind": call.kind, "media": call.media, "title": call.title, "status": call.status,
        "host": {"id": call.host_id, "name": user_names.get(call.host_id or 0)} if call.host_id else None,
        "scheduled_at": call.scheduled_at, "ring_until": call.ring_until, "started_at": call.started_at, "ended_at": call.ended_at,
        "end_reason": call.end_reason, "duration": duration(call), "created_at": call.created_at,
        "participants": [part_out(p, user_names) for p in parts], "online": sum(1 for p in parts if p.status == "joined"),
        "me": {"role": mine.role, "status": mine.status} if mine else None,
        "peer": user_names.get(others[0].user_id) if call.kind == "direct" and others else None,
    }  # fmt: skip
