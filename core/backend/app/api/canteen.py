"""Abet: kunlik menyu, baholash (QR yoki ilova), izohlar va javoblar, tahlil."""

import asyncio
import io
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import segno
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.canteen import CanteenDish, CanteenMenu, CanteenRating
from app.models.employees import Employee
from app.services import canteen as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/canteen", tags=["canteen"])
MAX_DISHES = 30


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("canteen.own", "canteen.read", "canteen.manage")
Reader = require_any("canteen.read", "canteen.manage")
Manager = require_any("canteen.manage")


# --- Menyu --------------------------------------------------------------------------------


class DishIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="main", pattern="^(soup|main|salad|side|drink|dessert|other)$")
    description: str | None = Field(default=None, max_length=300)


class MenuIn(BaseModel):
    menu_date: date
    note: str | None = Field(default=None, max_length=300)
    dishes: list[DishIn] = Field(min_length=1, max_length=MAX_DISHES)


async def _summaries(db: AsyncSession, menu_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Menyu bo'yicha umumiy o'rtacha/soni va har taom bahosi."""
    if not menu_ids:
        return {}
    R = CanteenRating
    rows = (await db.execute(select(R.menu_id, R.dish_id, func.count(), func.avg(R.stars)).where(R.menu_id.in_(menu_ids)).group_by(R.menu_id, R.dish_id))).all()
    out: dict[int, dict[str, Any]] = {i: {"overall": None, "count": 0, "dishes": {}} for i in menu_ids}
    for mid, did, n, avg in rows:
        v = {"avg": round(float(avg), 2), "count": n}
        if did is None:
            out[mid]["overall"], out[mid]["count"] = v["avg"], n
        else:
            out[mid]["dishes"][did] = v
    return out


def _menu_out(m: CanteenMenu, dishes: list[CanteenDish], summary: dict[str, Any] | None) -> dict[str, Any]:
    ds = summary["dishes"] if summary else {}
    return {
        "id": m.id, "menu_date": m.menu_date, "note": m.note,
        "dishes": [{"id": d.id, "name": d.name, "kind": d.kind, "description": d.description, **({"avg": ds[d.id]["avg"], "count": ds[d.id]["count"]} if summary and d.id in ds else {"avg": None, "count": 0})} for d in dishes],
        "rating": {"avg": summary["overall"], "count": summary["count"]} if summary is not None else None,
    }  # fmt: skip


async def _dishes(db: AsyncSession, menu_ids: list[int]) -> dict[int, list[CanteenDish]]:
    out: dict[int, list[CanteenDish]] = defaultdict(list)
    if menu_ids:
        for d in (await db.scalars(select(CanteenDish).where(CanteenDish.menu_id.in_(menu_ids)).order_by(CanteenDish.position, CanteenDish.id))).all():
            out[d.menu_id].append(d)
    return out


async def _menus_out(db: AsyncSession, rows: list[CanteenMenu], auth: AuthContext) -> list[dict[str, Any]]:
    ids = [m.id for m in rows]
    ds = await _dishes(db, ids)
    sm = await _summaries(db, ids) if svc.can_read(auth) else {}
    return [_menu_out(m, ds.get(m.id, []), sm.get(m.id) if svc.can_read(auth) else None) for m in rows]


async def _menu(db: AsyncSession, mid: int) -> CanteenMenu:
    m = await db.get(CanteenMenu, mid)
    if not m:
        raise error(404, "not_found")
    return m


@router.get("/menus")
async def menus(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    if end < start or (end - start).days > 92:
        raise error(400, "range_invalid", max_days=92)
    rows = (await db.scalars(select(CanteenMenu).where(CanteenMenu.menu_date.between(start, end)).order_by(CanteenMenu.menu_date))).all()
    return await _menus_out(db, list(rows), auth)


async def _mine(db: AsyncSession, menu_id: int, auth: AuthContext) -> dict[str, Any]:
    """Joriy xodimning shu menyudagi baholari."""
    e = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id))
    if not e:
        return {"overall": None, "dishes": {}}
    rows = (await db.scalars(select(CanteenRating).where(CanteenRating.menu_id == menu_id, CanteenRating.employee_id == e.id))).all()
    out: dict[str, Any] = {"overall": None, "dishes": {}}
    for r in rows:
        v = {"stars": r.stars, "comment": r.comment, "anonymous": r.anonymous, "reply": r.reply}
        if r.dish_id is None:
            out["overall"] = v
        else:
            out["dishes"][r.dish_id] = {"stars": r.stars}
    return out


async def _menu_detail(db: AsyncSession, m: CanteenMenu, auth: AuthContext) -> dict[str, Any]:
    out = (await _menus_out(db, [m], auth))[0]
    st = await svc.get_settings_row(db)
    out["can_rate"] = svc.rating_open(m.menu_date, local_date(now()), st.rating_days)
    out["require_qr"] = st.require_qr
    out["mine"] = await _mine(db, m.id, auth)
    return out


@router.get("/menus/today")
async def today_menu(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    m = await db.scalar(select(CanteenMenu).where(CanteenMenu.menu_date == local_date(now())))
    return await _menu_detail(db, m, auth) if m else None


@router.get("/menus/{mid}")
async def menu(mid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    return await _menu_detail(db, await _menu(db, mid), auth)


async def _save_dishes(db: AsyncSession, m: CanteenMenu, dishes: list[DishIn]) -> None:
    existing = {d.id: d for d in (await db.scalars(select(CanteenDish).where(CanteenDish.menu_id == m.id))).all()}
    keep: set[int] = set()
    for i, d in enumerate(dishes):
        row = existing.get(d.id) if d.id else None
        if row is None:
            db.add(CanteenDish(menu_id=m.id, position=i, name=d.name.strip(), kind=d.kind, description=(d.description or "").strip() or None))
        else:
            row.position, row.name, row.kind, row.description = i, d.name.strip(), d.kind, (d.description or "").strip() or None
            keep.add(row.id)
    for did, row in existing.items():
        if did not in keep:
            await db.delete(row)  # taomning baholari ham o'chadi


@router.post("/menus", status_code=201)
async def create_menu(body: MenuIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    if await db.scalar(select(CanteenMenu.id).where(CanteenMenu.menu_date == body.menu_date)):
        raise error(409, "menu_exists")
    m = CanteenMenu(menu_date=body.menu_date, note=(body.note or "").strip() or None, created_by=auth.user.id)
    db.add(m)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "menu_exists") from None
    await _save_dishes(db, m, body.dishes)
    await audit(db, request, "canteen.menu_create", actor=auth.user, entity="canteen_menu", entity_id=m.id, data={"date": str(m.menu_date), "dishes": len(body.dishes)})
    await db.commit()
    return await _menu_detail(db, m, auth)


@router.put("/menus/{mid}")
async def update_menu(mid: int, body: MenuIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    m = await _menu(db, mid)
    if body.menu_date != m.menu_date:
        if await db.scalar(select(func.count()).select_from(CanteenRating).where(CanteenRating.menu_id == m.id)):
            raise error(409, "menu_has_ratings")
        if await db.scalar(select(CanteenMenu.id).where(CanteenMenu.menu_date == body.menu_date)):
            raise error(409, "menu_exists")
    m.menu_date, m.note = body.menu_date, (body.note or "").strip() or None
    await _save_dishes(db, m, body.dishes)
    await audit(db, request, "canteen.menu_update", actor=auth.user, entity="canteen_menu", entity_id=m.id, data={"date": str(m.menu_date), "dishes": len(body.dishes)})
    await db.commit()
    return await _menu_detail(db, m, auth)


@router.delete("/menus/{mid}", status_code=204)
async def delete_menu(mid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    m = await _menu(db, mid)
    if await db.scalar(select(func.count()).select_from(CanteenRating).where(CanteenRating.menu_id == m.id)):
        raise error(409, "menu_has_ratings")
    await audit(db, request, "canteen.menu_delete", actor=auth.user, entity="canteen_menu", entity_id=m.id, data={"date": str(m.menu_date)})
    await db.delete(m)
    await db.commit()


# --- Baholash -----------------------------------------------------------------------------


class OverallIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    anonymous: bool = False


class DishRateIn(BaseModel):
    dish_id: int
    stars: int | None = Field(default=None, ge=1, le=5)  # None = bahoni olib tashlash


class RateIn(BaseModel):
    overall: OverallIn | None = None
    dishes: list[DishRateIn] = []
    qr: str | None = Field(default=None, max_length=100)


@router.post("/menus/{mid}/rate")
async def rate(mid: int, body: RateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    if body.overall is None and not body.dishes:
        raise error(400, "nothing_to_rate")
    m = await _menu(db, mid)
    emp = await svc.my_employee(db, auth)
    st = await svc.get_settings_row(db)
    if not svc.rating_open(m.menu_date, local_date(now()), st.rating_days):
        raise error(409, "rating_closed")
    via_qr = svc.qr_valid(body.qr, st.qr_epoch)
    if st.require_qr and not via_qr:
        raise error(400, "qr_required")
    dish_ids = {d.id for d in (await db.scalars(select(CanteenDish).where(CanteenDish.menu_id == m.id))).all()}
    if any(d.dish_id not in dish_ids for d in body.dishes):
        raise error(400, "unknown_dish")
    R = CanteenRating
    existing = {r.dish_id: r for r in (await db.scalars(select(R).where(R.menu_id == m.id, R.employee_id == emp.id))).all()}
    notes = []
    if body.overall is not None:
        o = body.overall
        comment = (o.comment or "").strip() or None
        r = existing.get(None)
        if r is None:
            r = R(menu_id=m.id, dish_id=None, employee_id=emp.id, stars=o.stars)
            db.add(r)
        r.stars, r.comment, r.anonymous, r.via_qr = o.stars, comment, o.anonymous, via_qr
        if o.stars <= svc.LOW_STARS:
            managers = [u for u in await users_with_permission(db, "canteen.manage") if u != auth.user.id]
            notes = await notify(db, managers, "canteen.low_rating", link="/canteen/comments", params={"date": m.menu_date.strftime("%d.%m"), "stars": o.stars, "comment": (comment or "")[:80]})
    for d in body.dishes:
        r = existing.get(d.dish_id)
        if d.stars is None:
            if r is not None:
                await db.delete(r)
            continue
        if r is None:
            db.add(R(menu_id=m.id, dish_id=d.dish_id, employee_id=emp.id, stars=d.stars, via_qr=via_qr))
        else:
            r.stars, r.via_qr = d.stars, via_qr
    await db.flush()
    await db.commit()
    await deliver(request.app, notes)
    return await _menu_detail(db, m, auth)


@router.delete("/menus/{mid}/rate", status_code=204)
async def retract(mid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    m = await _menu(db, mid)
    emp = await svc.my_employee(db, auth)
    st = await svc.get_settings_row(db)
    if not svc.rating_open(m.menu_date, local_date(now()), st.rating_days):
        raise error(409, "rating_closed")
    for r in (await db.scalars(select(CanteenRating).where(CanteenRating.menu_id == m.id, CanteenRating.employee_id == emp.id))).all():
        await db.delete(r)
    await db.commit()


# --- Izohlar va javoblar ------------------------------------------------------------------


@router.get("/ratings")
async def ratings(
    start: date,
    end: date,
    max_stars: int | None = Query(default=None, ge=1, le=5),
    commented: bool = True,
    unanswered: bool = False,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Reader),
):
    """Kunning umumiy baholari (izohlar). Anonim baho ismi faqat `canteen.manage` ga ko'rinadi."""
    if end < start or (end - start).days > 366:
        raise error(400, "range_invalid", max_days=366)
    R = CanteenRating
    conds: list = [R.dish_id.is_(None), CanteenMenu.menu_date.between(start, end)]
    if max_stars:
        conds.append(R.stars <= max_stars)
    if commented:
        conds.append(R.comment.is_not(None))
    if unanswered:
        conds.append(R.reply.is_(None))
    stmt = select(R, CanteenMenu.menu_date).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(*conds)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(CanteenMenu.menu_date.desc(), R.id.desc()).offset((page - 1) * size).limit(size))).all()
    emps = {e.id: e.full_name for e in (await db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r, _ in rows})))).all()} if rows else {}
    manage = svc.has(auth, "canteen.manage")
    items = [
        {"id": r.id, "menu_id": r.menu_id, "menu_date": d, "stars": r.stars, "comment": r.comment, "anonymous": r.anonymous, "via_qr": r.via_qr, "created_at": r.created_at,
         "employee": (emps.get(r.employee_id) if (manage or not r.anonymous) else None), "reply": r.reply, "replied_at": r.replied_at}
        for r, d in rows
    ]  # fmt: skip
    return {"total": total, "page": page, "size": size, "items": items}


class ReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)


@router.post("/ratings/{rid}/reply")
async def reply(rid: int, body: ReplyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    r = await db.get(CanteenRating, rid)
    if not r or r.dish_id is not None:
        raise error(404, "not_found")
    r.reply, r.replied_by, r.replied_at = body.reply.strip(), auth.user.id, now()
    emp = await db.get(Employee, r.employee_id)
    m = await db.get(CanteenMenu, r.menu_id)
    notes = await notify(db, [emp.user_id] if emp and emp.user_id else [], "canteen.reply", link="/canteen", params={"date": m.menu_date.strftime("%d.%m") if m else "", "reply": r.reply[:100]})
    await audit(db, request, "canteen.reply", actor=auth.user, entity="canteen_rating", entity_id=r.id, data={"menu_id": r.menu_id})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": r.id, "reply": r.reply, "replied_at": r.replied_at}


# --- Tahlil -------------------------------------------------------------------------------


@router.get("/analytics")
async def analytics(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Reader)):
    if end < start or (end - start).days > 366:
        raise error(400, "range_invalid", max_days=366)
    R = CanteenRating
    in_range = CanteenMenu.menu_date.between(start, end)
    over = (await db.execute(select(CanteenMenu.menu_date, R.stars, R.employee_id).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(R.dish_id.is_(None), in_range))).all()
    n = len(over)
    dist = {s: sum(1 for _, st, _ in over if st == s) for s in range(1, 6)}
    by_day: dict[date, list[int]] = defaultdict(list)
    for d, st, _ in over:
        by_day[d].append(st)
    menu_days = {m for (m,) in (await db.execute(select(CanteenMenu.menu_date).where(in_range))).all()}
    trend = []
    day = start
    while day <= end:
        v = by_day.get(day)
        if day in menu_days or v:
            trend.append({"date": day, "avg": round(sum(v) / len(v), 2) if v else None, "count": len(v or [])})
        day += timedelta(days=1)
    dish_rows = (await db.execute(select(CanteenDish.name, CanteenDish.kind, R.stars, CanteenMenu.menu_date).join(R, R.dish_id == CanteenDish.id).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(in_range))).all()
    agg: dict[str, dict[str, Any]] = {}
    for name, kind, stars, d in dish_rows:
        a = agg.setdefault(name.strip().lower(), {"name": name.strip(), "kind": kind, "sum": 0, "count": 0, "days": set()})
        a["sum"] += stars
        a["count"] += 1
        a["days"].add(d)
    dishes = sorted(
        [{"name": a["name"], "kind": a["kind"], "avg": round(a["sum"] / a["count"], 2), "count": a["count"], "days": len(a["days"])} for a in agg.values()],
        key=lambda x: (-x["avg"], -x["count"]),
    )  # fmt: skip
    active = await db.scalar(select(func.count()).select_from(Employee).where(Employee.status == "active")) or 0
    raters = len({e for _, _, e in over})
    commented = await db.scalar(select(func.count()).select_from(R).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(R.dish_id.is_(None), R.comment.is_not(None), in_range)) or 0
    unanswered = await db.scalar(select(func.count()).select_from(R).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(R.dish_id.is_(None), R.comment.is_not(None), R.reply.is_(None), in_range)) or 0
    via_qr = await db.scalar(select(func.count()).select_from(R).join(CanteenMenu, CanteenMenu.id == R.menu_id).where(R.dish_id.is_(None), R.via_qr.is_(True), in_range)) or 0
    return {
        "start": start, "end": end,
        "kpis": {"menus": len(menu_days), "ratings": n, "raters": raters, "active_employees": active, "avg": round(sum(s for _, s, _ in over) / n, 2) if n else None,
                 "low_share": round(sum(1 for _, s, _ in over if s <= svc.LOW_STARS) / n, 4) if n else None, "via_qr": via_qr, "commented": commented, "unanswered": unanswered},
        "distribution": dist, "trend": trend, "dishes": dishes,
    }  # fmt: skip


# --- QR va sozlamalar ---------------------------------------------------------------------


@router.get("/qr")
async def qr(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    st = await svc.get_settings_row(db)
    token = svc.make_qr_token(st.qr_epoch)
    url = f"{_base_url(request)}/canteen/rate?t={token}"

    def render() -> str:
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False, svgns=True, nl=False)
        return buf.getvalue().decode()

    await db.commit()
    return {"token": token, "url": url, "svg": await asyncio.to_thread(render), "epoch": st.qr_epoch}


@router.post("/qr/rotate")
async def rotate_qr(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    st = await svc.get_settings_row(db)
    st.qr_epoch += 1
    await audit(db, request, "canteen.qr_rotate", actor=auth.user, entity="canteen", data={"epoch": st.qr_epoch})
    await db.commit()
    return {"epoch": st.qr_epoch}


@router.get("/qr/resolve")
async def resolve_qr(t: str, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """QR dan kelgan token tekshiriladi va bugungi menyu qaytariladi."""
    st = await svc.get_settings_row(db)
    if not svc.qr_valid(t, st.qr_epoch):
        raise error(400, "qr_invalid")
    m = await db.scalar(select(CanteenMenu).where(CanteenMenu.menu_date == local_date(now())))
    await db.commit()
    return {"menu": await _menu_detail(db, m, auth) if m else None}


class SettingsIn(BaseModel):
    require_qr: bool
    rating_days: int = Field(ge=0, le=14)


@router.get("/settings")
async def get_settings_(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    st = await svc.get_settings_row(db)
    await db.commit()
    return {"require_qr": st.require_qr, "rating_days": st.rating_days}


@router.put("/settings")
async def put_settings(body: SettingsIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    st = await svc.get_settings_row(db)
    st.require_qr, st.rating_days = body.require_qr, body.rating_days
    await audit(db, request, "canteen.settings", actor=auth.user, entity="canteen", data=body.model_dump())
    await db.commit()
    return {"require_qr": st.require_qr, "rating_days": st.rating_days}

