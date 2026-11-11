"""Qurilmalar: ruxsat so'rovlari, qurilmalar ro'yxati, majburiy xodimlar, sozlamalar, login tarixi va xavfsizlik hodisalari."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require_any
from app.models.auth import AuditLog, Role, User, UserSession
from app.models.devices import UserDevice
from app.services import devices as svc
from app.services.audit import audit
from app.timeutil import now

router = APIRouter(prefix="/v1/devices", tags=["devices"])

can_read = require_any("devices.read", "devices.manage")
can_manage = require_any("devices.manage")
ONLINE_MIN = 15
SECURITY_ACTIONS = ("auth.login_failed", "auth.login_blocked", "auth.device_pending", "auth.device_blocked", "auth.device_unknown")


def _out(d: UserDevice, names: dict[int, tuple[str, str]], online_since) -> dict[str, Any]:
    n = names.get(d.user_id, ("—", ""))
    return {
        "id": d.id, "user": {"id": d.user_id, "name": n[0], "login": n[1]}, "label": d.label, "user_agent": d.user_agent,
        "first_ip": d.first_ip, "last_ip": d.last_ip, "status": d.status, "is_primary": d.is_primary,
        "first_seen": d.first_seen, "last_seen": d.last_seen, "online": d.last_seen >= online_since,
    }  # fmt: skip


async def _names(db: AsyncSession, ids: set[int]) -> dict[int, tuple[str, str]]:
    return {u.id: (u.full_name, u.login) for u in (await db.scalars(select(User).where(User.id.in_(ids or {0})))).all()}


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    online_since = now() - timedelta(minutes=ONLINE_MIN)
    total = await db.scalar(select(func.count()).select_from(UserDevice))
    by = dict((await db.execute(select(UserDevice.status, func.count()).group_by(UserDevice.status))).all())
    sessions_online = await db.scalar(select(func.count(func.distinct(UserSession.user_id))).where(UserSession.revoked_at.is_(None), UserSession.last_used_at >= online_since))
    suspicious = await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action.in_(SECURITY_ACTIONS), AuditLog.created_at >= now() - timedelta(days=7)))
    return {"total": total or 0, "online": sessions_online or 0, "pending": by.get("pending", 0), "blocked": by.get("blocked", 0), "suspicious_7d": suspicious or 0}


@router.get("")
async def list_devices(status: str | None = Query(default=None, pattern="^(approved|pending|blocked)$"), q: str | None = None, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
                       db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):  # fmt: skip
    stmt = select(UserDevice).join(User, User.id == UserDevice.user_id)
    if status:
        stmt = stmt.where(UserDevice.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.full_name.ilike(like) | User.login.ilike(like) | UserDevice.last_ip.ilike(like))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(stmt.order_by(UserDevice.last_seen.desc()).offset((page - 1) * size).limit(size))).all()
    names = await _names(db, {d.user_id for d in rows})
    since = now() - timedelta(minutes=ONLINE_MIN)
    return {"total": total, "page": page, "size": size, "items": [_out(d, names, since) for d in rows]}


@router.post("/{did}/{action}")
async def act(did: int, action: str, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    """approve (tasdiqlash: shu qurilma asosiy bo'ladi, eski kutayotganlar yopiladi), reject, block, unblock, primary."""
    d = await db.get(UserDevice, did)
    if not d:
        raise error(404, "not_found")
    if action in ("approve", "primary"):
        d.status = "approved"
        await db.execute(update(UserDevice).where(UserDevice.user_id == d.user_id, UserDevice.id != d.id).values(is_primary=False))
        d.is_primary = True
        if action == "approve":
            await db.execute(update(UserDevice).where(UserDevice.user_id == d.user_id, UserDevice.id != d.id, UserDevice.status == "pending").values(status="blocked"))
    elif action in ("reject", "block"):
        d.status, d.is_primary = "blocked", False
        await db.execute(update(UserSession).where(UserSession.user_id == d.user_id, UserSession.revoked_at.is_(None), UserSession.user_agent == d.user_agent, UserSession.ip == d.last_ip).values(revoked_at=now()))
    elif action == "unblock":
        d.status = "approved"
    else:
        raise error(404, "not_found")
    d.decided_by, d.decided_at = auth.user.id, now()
    await audit(db, request, f"device.{action}", actor=auth.user, entity="user_device", entity_id=d.id, data={"user_id": d.user_id})
    await db.commit()
    return _out(d, await _names(db, {d.user_id}), now() - timedelta(minutes=ONLINE_MIN))


@router.delete("/{did}", status_code=204)
async def remove(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    d = await db.get(UserDevice, did)
    if d:
        await db.delete(d)
        await audit(db, request, "device.delete", actor=auth.user, entity="user_device", entity_id=did)
        await db.commit()


class SettingsIn(BaseModel):
    enforce_roles: list[str] = Field(default_factory=list, max_length=50)
    enforce_user_ids: list[int] = Field(default_factory=list, max_length=5000)
    auto_approve_first: bool = True


@router.get("/settings")
async def get_settings_(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    s = await svc.settings(db)
    await db.commit()
    roles = (await db.scalars(select(Role).order_by(Role.key))).all()
    users = await _names(db, set(s.enforce_user_ids or []))
    return {"enforce_roles": s.enforce_roles or [], "enforce_users": [{"id": i, "name": users.get(i, ("—", ""))[0]} for i in s.enforce_user_ids or []],
            "auto_approve_first": s.auto_approve_first, "roles": [{"key": r.key, "name": r.name_uz} for r in roles]}  # fmt: skip


@router.put("/settings")
async def put_settings(body: SettingsIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    s = await svc.settings(db)
    s.enforce_roles, s.enforce_user_ids, s.auto_approve_first, s.updated_at = sorted(set(body.enforce_roles)), sorted(set(body.enforce_user_ids)), body.auto_approve_first, now()
    await audit(db, request, "device.settings", actor=auth.user, data=body.model_dump())
    await db.commit()
    return {"ok": True}


@router.get("/logins")
async def logins(security: bool = False, q: str | None = None, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    """Login tarixi (audit jurnalidan). `security=true` — faqat xavfsizlik hodisalari: noto'g'ri parol, bloklangan, begona qurilma."""
    stmt = select(AuditLog).where(AuditLog.action.in_(SECURITY_ACTIONS if security else ("auth.login", *SECURITY_ACTIONS)))
    if q:
        stmt = stmt.where(AuditLog.actor_login.ilike(f"%{q.strip()}%") | AuditLog.ip.ilike(f"%{q.strip()}%"))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "items": [{"id": r.id, "at": r.created_at, "action": r.action.removeprefix("auth."), "login": r.actor_login, "ip": r.ip, "device": svc.label(r.user_agent)} for r in rows]}
