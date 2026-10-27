"""Telegram hisobini ulash: bir martalik kod (Redis, 10 daqiqa) -> botga `/start <kod>`."""

import secrets
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User

CODE_TTL = 600
_KEY = "tg:link:"


async def create_link_code(redis: Redis, user_id: int) -> str:
    code = secrets.token_urlsafe(9)  # 12 belgi, taxmin qilib bo'lmaydi
    await redis.set(f"{_KEY}{code}", user_id, ex=CODE_TTL)
    return code


async def consume_link_code(redis: Redis, code: str) -> int | None:
    """Kodni bir marta ishlatish (GETDEL): qayta ishlatib bo'lmaydi."""
    value = await redis.getdel(f"{_KEY}{code}")
    return int(value) if value else None


async def link_user(
    session: AsyncSession, user_id: int, chat_id: int, username: str | None
) -> User | None:
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        return None
    # Bitta Telegram chat faqat bitta hisobga ulanadi (unique): eskisidan uzamiz
    await session.execute(
        update(User)
        .where(User.telegram_chat_id == chat_id, User.id != user_id)
        .values(telegram_chat_id=None, telegram_username=None, telegram_linked_at=None)
    )
    user.telegram_chat_id = chat_id
    user.telegram_username = username
    user.telegram_notify = True
    user.telegram_linked_at = datetime.now(UTC)
    await session.flush()
    return user


async def unlink_user(session: AsyncSession, user: User) -> None:
    user.telegram_chat_id = None
    user.telegram_username = None
    user.telegram_linked_at = None
    await session.flush()


async def user_by_chat(session: AsyncSession, chat_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_chat_id == chat_id))
