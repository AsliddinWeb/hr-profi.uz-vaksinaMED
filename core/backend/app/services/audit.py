from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AuditLog, User

SENSITIVE_KEYS = {"password", "new_password", "old_password", "temp_password", "token"}


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _scrub(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return data
    return {k: ("***" if k in SENSITIVE_KEYS else v) for k, v in data.items()}


async def audit(
    session: AsyncSession,
    request: Request,
    action: str,
    *,
    actor: User | None = None,
    actor_login: str | None = None,
    entity: str | None = None,
    entity_id: Any = None,
    data: dict[str, Any] | None = None,
    note: str | None = None,
) -> None:
    """Audit yozuvini JORIY tranzaksiyaga qo'shadi (amal bilan birga commit bo'ladi)."""
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_login=actor.login if actor else actor_login,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
            data=_scrub(data),
            note=note,
        )
    )
