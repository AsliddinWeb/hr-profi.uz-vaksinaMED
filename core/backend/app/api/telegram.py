from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.services import telegram_link as link
from app.services.audit import audit

router = APIRouter(prefix="/v1/telegram", tags=["telegram"])


async def _bot_username(request: Request) -> str | None:
    s = get_settings()
    if s.telegram_bot_username:
        return s.telegram_bot_username.lstrip("@")
    return await request.app.state.redis.get("telegram:bot_username")


def _status(user, enabled: bool, username: str | None) -> dict:
    return {
        "enabled": enabled,  # bot sozlanganmi (token bor)
        "bot_username": username,
        "linked": user.telegram_chat_id is not None,
        "telegram_username": user.telegram_username,
        "notify": user.telegram_notify,
        "linked_at": user.telegram_linked_at,
    }


@router.get("/status")
async def status(request: Request, auth: AuthContext = Depends(get_auth)):
    enabled = bool(get_settings().telegram_bot_token)
    return _status(auth.user, enabled, await _bot_username(request) if enabled else None)


@router.post("/link-code")
async def link_code(request: Request, auth: AuthContext = Depends(get_auth)):
    if not get_settings().telegram_bot_token:
        raise error(409, "telegram_disabled")
    username = await _bot_username(request)
    if not username:
        # Bot hali ishga tushmagan (getMe bajarilmagan)
        raise error(503, "telegram_bot_unavailable")
    code = await link.create_link_code(request.app.state.redis, auth.user.id)
    return {
        "code": code,
        "url": f"https://t.me/{username}?start={code}",
        "expires_in": link.CODE_TTL,
    }


class PrefsIn(BaseModel):
    notify: bool


@router.patch("")
async def set_prefs(
    body: PrefsIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    if auth.user.telegram_chat_id is None:
        raise error(409, "telegram_not_linked")
    auth.user.telegram_notify = body.notify
    await db.commit()
    return _status(auth.user, True, await _bot_username(request))


@router.delete("", status_code=204)
async def unlink(
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    if auth.user.telegram_chat_id is not None:
        await link.unlink_user(db, auth.user)
        await audit(db, request, "telegram.unlink", actor=auth.user, entity="user", entity_id=auth.user.id)
        await db.commit()
