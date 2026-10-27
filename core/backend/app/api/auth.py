import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    AuthContext,
    error,
    get_auth_any,
)
from app.models.auth import User, UserSession
from app.security import hash_password, validate_password_strength, verify_password
from app.services import auth as svc
from app.services.audit import audit, client_ip
from app.services.notifications import deliver, notify

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(max_length=256)


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    locale: str | None = Field(default=None, pattern="^(uz|ru)$")


def me_payload(auth: AuthContext) -> dict:
    u = auth.user
    return {
        "id": u.id,
        "login": u.login,
        "full_name": u.full_name,
        "phone": u.phone,
        "locale": u.locale,
        "must_change_password": u.must_change_password,
        "role": {"key": u.role.key, "name_uz": u.role.name_uz, "name_ru": u.role.name_ru},
        "permissions": sorted(auth.permissions),
    }


def _secure(request: Request) -> bool:
    mode = get_settings().cookie_secure
    return request.url.scheme == "https" if mode == "auto" else mode == "true"


def set_auth_cookies(response: Response, request: Request, access: str, refresh: str) -> None:
    s = get_settings()
    common = {"httponly": True, "samesite": "lax", "secure": _secure(request)}
    response.set_cookie(ACCESS_COOKIE, access, max_age=s.access_ttl_minutes * 60, path="/", **common)
    response.set_cookie(
        REFRESH_COOKIE, refresh, max_age=s.refresh_ttl_days * 86400, path="/api/auth", **common
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


async def _auth_payload(user: User) -> AuthContext:
    return AuthContext(user, uuid.UUID(int=0), frozenset(user.role.permission_keys))


@router.post("/login")
async def login(
    body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_session)
):
    login_name = body.login.strip().lower()
    ip = client_ip(request)
    redis = request.app.state.redis

    try:
        await svc.check_login_allowed(redis, login_name, ip)
    except svc.RateLimited as exc:
        await audit(db, request, "auth.login_blocked", actor_login=login_name)
        await db.commit()
        raise error(429, "too_many_attempts", retry_after=exc.retry_after) from exc

    user = await svc.authenticate(db, login_name, body.password)
    if not user:
        await svc.register_failure(redis, login_name, ip)
        await audit(db, request, "auth.login_failed", actor_login=login_name)
        await db.commit()
        raise error(401, "invalid_credentials")

    await svc.clear_failures(redis, login_name, ip)
    access, refresh = await svc.start_session(db, user, ip, request.headers.get("user-agent"))
    await audit(db, request, "auth.login", actor=user, entity="user", entity_id=user.id)
    await db.commit()
    set_auth_cookies(response, request, access, refresh)
    return me_payload(await _auth_payload(user))


@router.post("/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_session)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise error(401, "not_authenticated")
    try:
        user, access, new_refresh, _ = await svc.rotate_refresh(db, token)
    except svc.RefreshError as exc:
        if str(exc) == "reuse":
            await audit(db, request, "auth.refresh_reuse_detected")
            await db.commit()
        clear_auth_cookies(response)
        raise error(401, "not_authenticated") from exc
    await db.commit()
    set_auth_cookies(response, request, access, new_refresh)
    return me_payload(await _auth_payload(user))


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_any),
):
    await svc.revoke_session(db, auth.session_id)
    await audit(db, request, "auth.logout", actor=auth.user)
    await db.commit()
    clear_auth_cookies(response)


@router.post("/logout-all", status_code=204)
async def logout_all(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_any),
):
    await svc.revoke_user_sessions(db, auth.user.id)
    await audit(db, request, "auth.logout_all", actor=auth.user)
    await db.commit()
    clear_auth_cookies(response)


@router.get("/me")
async def me(auth: AuthContext = Depends(get_auth_any)):
    return me_payload(auth)


@router.patch("/me")
async def update_me(
    body: ProfileIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_any),
):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(auth.user, key, value)
    if changes:
        await audit(db, request, "profile.update", actor=auth.user, data=changes)
        await db.commit()
    return me_payload(auth)


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_any),
):
    user = auth.user
    if not verify_password(body.old_password, user.password_hash):
        raise error(400, "wrong_old_password")
    problem = validate_password_strength(body.new_password, user.login)
    if problem:
        raise error(400, problem)
    if body.old_password == body.new_password:
        raise error(400, "password_unchanged")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await svc.revoke_user_sessions(db, user.id, except_sid=auth.session_id)
    await audit(db, request, "auth.password_changed", actor=user, entity="user", entity_id=user.id)
    notes = await notify(db, [user.id], "security.password_changed")
    await db.commit()
    await deliver(request.app, notes)


class SessionOut(BaseModel):
    id: uuid.UUID
    ip: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime
    current: bool


@router.get("/sessions", response_model=list[SessionOut])
async def my_sessions(
    db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth_any)
):
    rows = (
        await db.scalars(
            select(UserSession)
            .where(
                UserSession.user_id == auth.user.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > svc.now(),
            )
            .order_by(UserSession.last_used_at.desc())
        )
    ).all()
    return [
        SessionOut(
            id=r.id,
            ip=r.ip,
            user_agent=r.user_agent,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            current=r.id == auth.session_id,
        )
        for r in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_my_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_any),
):
    us = await db.get(UserSession, session_id)
    if not us or us.user_id != auth.user.id:
        raise error(404, "not_found")
    await svc.revoke_session(db, session_id)
    await audit(db, request, "auth.session_revoked", actor=auth.user, entity_id=session_id)
    await db.commit()
