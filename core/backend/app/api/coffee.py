"""Kofe-ledi: xodim choy/kofe buyurtma qiladi, kofe-ledi (yoki resepshin) qabul qilib yetkazadi."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.reception import CoffeeOrder
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.notifications import deliver, notify, register_template
from app.timeutil import now

router = APIRouter(prefix="/v1/reception/coffee", tags=["reception"])
OPEN = ("new", "accepted")

register_template("coffee.new", {"uz": "Yangi choy/kofe buyurtmasi", "ru": "Новый заказ чай/кофе"}, {"uz": "{place}: {items} ({guests} kishi)", "ru": "{place}: {items} ({guests} чел.)"}, "info")
register_template("coffee.done", {"uz": "Buyurtmangiz yetkazildi", "ru": "Ваш заказ доставлен"}, {"uz": "{place}: {items}", "ru": "{place}: {items}"}, "success")


def serves(auth: AuthContext) -> bool:
    return matches(auth.permissions, "reception.coffee") or matches(auth.permissions, "reception.desk")


class OrderIn(BaseModel):
    place: str = Field(min_length=2, max_length=120)
    items: str = Field(min_length=2, max_length=300)
    guests: int = Field(default=1, ge=1, le=100)
    note: str | None = Field(default=None, max_length=300)


async def _out(db: AsyncSession, rows: list[CoffeeOrder]) -> list[dict[str, Any]]:
    ids = {u for r in rows for u in (r.requested_by, r.handled_by) if u}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    return [
        {"id": r.id, "place": r.place, "items": r.items, "guests": r.guests, "note": r.note, "status": r.status,
         "requested_by": names.get(r.requested_by or 0), "handled_by": names.get(r.handled_by or 0), "mine": False,
         "created_at": r.created_at, "accepted_at": r.accepted_at, "done_at": r.done_at}
        for r in rows
    ]  # fmt: skip


@router.get("")
async def list_orders(scope: str = Query(default="mine", pattern="^(mine|all)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    stmt = select(CoffeeOrder).order_by(case((CoffeeOrder.status.in_(OPEN), 0), else_=1), CoffeeOrder.id.desc()).limit(200)
    if scope == "all":
        if not serves(auth):
            raise error(403, "forbidden")
    else:
        stmt = stmt.where(CoffeeOrder.requested_by == auth.user.id)
    rows = list((await db.scalars(stmt)).all())
    out = await _out(db, rows)
    for o, r in zip(out, rows, strict=True):
        o["mine"] = r.requested_by == auth.user.id
    return {"items": out, "can_serve": serves(auth)}


@router.post("", status_code=201)
async def create_order(body: OrderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    o = CoffeeOrder(place=body.place.strip(), items=body.items.strip(), guests=body.guests, note=(body.note or "").strip() or None, requested_by=auth.user.id)
    db.add(o)
    await db.flush()
    targets = [u for u in dict.fromkeys([*await users_with_permission(db, "reception.coffee"), *await users_with_permission(db, "reception.desk")]) if u != auth.user.id]
    notes = await notify(db, targets, "coffee.new", params={"place": o.place, "items": o.items, "guests": o.guests}, link="/reception/coffee")
    await db.commit()
    await deliver(request.app, notes)
    return (await _out(db, [o]))[0]


@router.post("/{oid}/{action}")
async def act(oid: int, action: str, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    o = await db.scalar(select(CoffeeOrder).where(CoffeeOrder.id == oid).with_for_update())
    if not o:
        raise error(404, "not_found")
    if o.status not in OPEN:
        raise error(409, "already_closed")
    moment = now()
    notes: list = []
    if action == "cancel":
        if not (serves(auth) or o.requested_by == auth.user.id):
            raise error(403, "forbidden")
        o.status = "cancelled"
    elif action in ("accept", "done"):
        if not serves(auth):
            raise error(403, "forbidden")
        o.handled_by = auth.user.id
        if action == "accept":
            o.status, o.accepted_at = "accepted", moment
        else:
            o.status, o.done_at = "done", moment
            if o.requested_by and o.requested_by != auth.user.id:
                notes = await notify(db, [o.requested_by], "coffee.done", params={"place": o.place, "items": o.items}, link="/reception/coffee")
    else:
        raise error(404, "not_found")
    await db.commit()
    await deliver(request.app, notes)
    return (await _out(db, [o]))[0]
