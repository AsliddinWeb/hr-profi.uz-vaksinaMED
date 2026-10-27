"""AI yordamchisi (xulosa, rezyume/ticket avto-to'ldirish, sozlamalar, foydalanish) va global qidiruv."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.ai import AiRequest
from app.rbac import matches
from app.services import ai as svc
from app.services import search as search_svc
from app.services.audit import audit
from app.timeutil import now

router = APIRouter(prefix="/v1", tags=["ai"])


def need(perm: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not matches(auth.permissions, perm):
            raise error(403, "forbidden")
        return auth

    return dep


Use = need("ai.use")
Manage = need("ai.manage")


@router.get("/search")
async def search(q: str = Query(min_length=2, max_length=100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    return await search_svc.search(db, auth, q)


async def _settings_out(db: AsyncSession) -> dict[str, Any]:
    cfg = await svc.get_cfg(db)
    return {"configured": svc.configured(), "enabled": cfg.enabled, "model": cfg.model, "daily_limit": cfg.daily_limit, "features": {f: bool((cfg.features or {}).get(f, True)) for f in svc.FEATURES}, "updated_at": cfg.updated_at}


@router.get("/ai/status")
async def status(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Use)):
    cfg = await svc.get_cfg(db)
    used = await svc.used_today(db, auth.user.id, now())
    return {
        "configured": svc.configured(), "enabled": cfg.enabled and svc.configured(), "features": {f: svc.feature_on(cfg, f) for f in svc.FEATURES},
        "remaining": max(0, cfg.daily_limit - used), "limit": cfg.daily_limit,
    }  # fmt: skip


class SettingsIn(BaseModel):
    enabled: bool = True
    model: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._:\-]+$")
    daily_limit: int = Field(ge=1, le=1000)
    features: dict[str, bool] = Field(default_factory=dict)


@router.get("/ai/settings")
async def get_settings_(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    return await _settings_out(db)


@router.put("/ai/settings")
async def put_settings(body: SettingsIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    cfg = await svc.get_cfg(db)
    cfg.enabled, cfg.model, cfg.daily_limit = body.enabled, body.model, body.daily_limit
    cfg.features = {f: bool(body.features.get(f, True)) for f in svc.FEATURES}
    cfg.updated_by, cfg.updated_at = auth.user.id, now()
    await audit(db, request, "ai.settings", actor=auth.user, entity="ai", entity_id=1, data={"enabled": cfg.enabled, "model": cfg.model, "limit": cfg.daily_limit, "features": cfg.features})
    await db.commit()
    return await _settings_out(db)


@router.get("/ai/usage")
async def usage(days: int = Query(default=30, ge=1, le=90), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    return await svc.usage(db, days)


class SummarizeIn(BaseModel):
    entity: str = Field(pattern="^(ticket|need|task|candidate)$")
    id: int
    lang: str = Field(default="uz", pattern="^(uz|ru)$")
    refresh: bool = False


@router.post("/ai/summarize")
async def summarize(body: SummarizeIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Use)):
    out = await svc.summarize(db, auth, body.entity, body.id, body.lang, body.refresh)
    await db.commit()
    return out


class TextIn(BaseModel):
    text: str = Field(min_length=10, max_length=50000)


@router.post("/ai/ticket-suggest")
async def ticket_suggest(body: TextIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Use)):
    if not matches(auth.permissions, "helpdesk.own"):
        raise error(403, "forbidden")
    return {"fields": await svc.suggest_ticket(db, auth, body.text)}


@router.get("/ai/requests-count")
async def requests_count(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    return {"total": await db.scalar(select(func.count()).select_from(AiRequest)) or 0}
