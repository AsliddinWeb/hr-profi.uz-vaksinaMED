import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.auth import User, UserSession
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    needs_rehash,
    new_refresh_token,
    verify_password,
)

MAX_FAILS = 5
LOCK_SECONDS = 15 * 60


def now() -> datetime:
    return datetime.now(UTC)


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


async def check_login_allowed(redis: Redis, login: str, ip: str | None) -> None:
    key = f"rl:login:{login}:{ip}"
    fails = int(await redis.get(key) or 0)
    if fails >= MAX_FAILS:
        raise RateLimited(max(await redis.ttl(key), 1))


async def register_failure(redis: Redis, login: str, ip: str | None) -> None:
    key = f"rl:login:{login}:{ip}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, LOCK_SECONDS)


async def clear_failures(redis: Redis, login: str, ip: str | None) -> None:
    await redis.delete(f"rl:login:{login}:{ip}")


async def authenticate(session: AsyncSession, login: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.login == login))
    ok = verify_password(password, user.password_hash if user else None)
    if not user or not ok or not user.is_active:
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


async def start_session(
    session: AsyncSession, user: User, ip: str | None, user_agent: str | None
) -> tuple[str, str]:
    """Yangi sessiya. (access_token, refresh_token) qaytaradi."""
    s = get_settings()
    sid = uuid.uuid4()
    refresh, token_hash = new_refresh_token(str(sid))
    session.add(
        UserSession(
            id=sid,
            user_id=user.id,
            token_hash=token_hash,
            ip=ip,
            user_agent=(user_agent or "")[:300] or None,
            expires_at=now() + timedelta(days=s.refresh_ttl_days),
        )
    )
    user.last_login_at = now()
    await session.flush()
    return create_access_token(user.id, str(sid)), refresh


class RefreshError(Exception):
    pass


async def rotate_refresh(session: AsyncSession, token: str) -> tuple[User, str, str, uuid.UUID]:
    """Refresh tokenni almashtiradi. Qayta ishlatilgan (eski) token bo'lsa sessiyani yopadi."""
    try:
        sid_s, secret = token.split(".", 1)
        sid = uuid.UUID(sid_s)
    except ValueError as exc:
        raise RefreshError("malformed") from exc

    us = await session.get(UserSession, sid)
    if not us or us.revoked_at is not None or us.expires_at <= now():
        raise RefreshError("invalid")
    if us.token_hash != hash_token(secret):
        # Token o'g'irlangan bo'lishi mumkin: sessiyani yopamiz
        us.revoked_at = now()
        await session.commit()
        raise RefreshError("reuse")
    user = us.user
    if not user.is_active:
        raise RefreshError("inactive")

    new_token, new_hash = new_refresh_token(str(sid))
    us.token_hash = new_hash
    us.last_used_at = now()
    us.expires_at = now() + timedelta(days=get_settings().refresh_ttl_days)
    await session.flush()
    return user, create_access_token(user.id, str(sid)), new_token, sid


async def revoke_session(session: AsyncSession, sid: uuid.UUID) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.id == sid, UserSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )


async def revoke_user_sessions(
    session: AsyncSession, user_id: int, except_sid: uuid.UUID | None = None
) -> None:
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    if except_sid:
        stmt = stmt.where(UserSession.id != except_sid)
    await session.execute(stmt)
