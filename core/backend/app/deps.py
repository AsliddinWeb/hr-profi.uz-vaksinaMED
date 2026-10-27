import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from app.db import get_session
from app.models.auth import User, UserSession
from app.rbac import matches
from app.security import decode_access_token
from app.services.auth import now

ACCESS_COOKIE = "vh_access"
REFRESH_COOKIE = "vh_refresh"


def error(status: int, code: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, **extra})


@dataclass
class AuthContext:
    user: User
    session_id: uuid.UUID
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return matches(self.permissions, permission)


async def load_auth(request: HTTPConnection, session: AsyncSession) -> AuthContext:
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    if not payload:
        raise error(401, "not_authenticated")
    try:
        sid = uuid.UUID(payload["sid"])
        uid = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise error(401, "not_authenticated") from exc

    us = await session.get(UserSession, sid)
    if (
        not us
        or us.user_id != uid
        or us.revoked_at is not None
        or us.expires_at <= now()
        or not us.user.is_active
    ):
        raise error(401, "not_authenticated")
    user = us.user
    return AuthContext(user, sid, frozenset(user.role.permission_keys))


async def get_auth_any(request: Request, session: AsyncSession = Depends(get_session)):
    """Autentifikatsiya (parol almashtirish talab qilinayotgan foydalanuvchi ham o'tadi)."""
    return await load_auth(request, session)


async def get_auth(auth: AuthContext = Depends(get_auth_any)) -> AuthContext:
    if auth.user.must_change_password:
        raise error(403, "password_change_required")
    return auth


def require(permission: str):
    async def dependency(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not auth.can(permission):
            raise error(403, "forbidden", permission=permission)
        return auth

    return dependency


def require_any(*permissions: str):
    """Ruxsatlardan kamida bittasi bo'lsa o'tadi."""

    async def dependency(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(auth.can(p) for p in permissions):
            raise error(403, "forbidden", permission=permissions[0])
        return auth

    return dependency
