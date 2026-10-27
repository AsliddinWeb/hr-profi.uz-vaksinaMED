from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth, require
from app.models.auth import Role, User
from app.models.notifications import Notification
from app.realtime import publish
from app.services.audit import audit
from app.services.notifications import deliver, notify, serialize

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    stmt = select(Notification).where(Notification.user_id == auth.user.id)
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Notification.id.desc()).offset((page - 1) * size).limit(size)
        )
    ).all()
    return {"total": total or 0, "page": page, "size": size, "items": [serialize(n) for n in rows]}


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)
):
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == auth.user.id, Notification.read_at.is_(None))
    )
    return {"count": count or 0}


async def _sync_unread(request: Request, db: AsyncSession, user_id: int) -> None:
    """Boshqa ochiq qurilmalar/tablar hisoblagichini yangilaydi."""
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    await publish(request.app.state.redis, [user_id], "unread", {"count": count or 0})


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == auth.user.id,  # faqat o'zinikini
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    if result.rowcount == 0 and not await db.scalar(
        select(Notification.id).where(
            Notification.id == notification_id, Notification.user_id == auth.user.id
        )
    ):
        raise error(404, "not_found")
    await _sync_unread(request, db, auth.user.id)


@router.post("/read-all", status_code=204)
async def mark_all_read(
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == auth.user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    await _sync_unread(request, db, auth.user.id)


class BroadcastIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str | None = Field(default=None, max_length=1000)
    title_ru: str | None = Field(default=None, max_length=120)
    body_ru: str | None = Field(default=None, max_length=1000)
    link: str | None = Field(default=None, max_length=300, pattern=r"^/[^\s]*$")
    everyone: bool = False
    role_keys: list[str] = []
    user_ids: list[int] = []
    severity: str = Field(default="info", pattern="^(info|success|warning|danger)$")


@router.post("/broadcast")
async def broadcast(
    body: BroadcastIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("notifications.send")),
):
    if not (body.everyone or body.role_keys or body.user_ids):
        raise error(400, "no_recipients")

    stmt = select(User.id).where(User.is_active.is_(True))
    if not body.everyone:
        conds = []
        if body.role_keys:
            conds.append(User.role_id.in_(select(Role.id).where(Role.key.in_(body.role_keys))))
        if body.user_ids:
            conds.append(User.id.in_(body.user_ids))
        from sqlalchemy import or_

        stmt = stmt.where(or_(*conds))
    ids = list((await db.scalars(stmt)).all())
    if not ids:
        raise error(400, "no_recipients")

    notes = await notify(
        db,
        ids,
        "system.broadcast",
        title={"uz": body.title, "ru": body.title_ru or body.title},
        body=(
            {"uz": body.body, "ru": body.body_ru or body.body}
            if body.body
            else None
        ),
        link=body.link,
        severity=body.severity,
    )
    await audit(
        db, request, "notification.broadcast", actor=auth.user, entity="notification",
        data={"recipients": len(ids), "everyone": body.everyone, "roles": body.role_keys,
              "title": body.title},
    )  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return {"recipients": len(ids)}
