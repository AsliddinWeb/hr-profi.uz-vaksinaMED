from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, require
from app.models.auth import AuditLog

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(
    action: str | None = None,
    actor_id: int | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("audit.read")),
):
    stmt = select(AuditLog)
    if action:
        # "auth." kabi prefiks yoki to'liq nom
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "actor_id": r.actor_id,
                "actor_login": r.actor_login,
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "ip": r.ip,
                "data": r.data,
                "note": r.note,
            }
            for r in rows
        ],
    }
