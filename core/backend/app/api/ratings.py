"""Mijozlar baholashi: har filial uchun QR. Mijoz smenadagi xodimni yoki dorixonani (umumiy, tozalik, tanlov) baholaydi.
Past baho (1-2 yulduz) shikoyat hisoblanadi: filial mudiri va koordinatoriga xabar ketadi. Mijoz ismi/telefoni faqat boshqaruvchilarga ko'rinadi."""

import io
import secrets
from datetime import timedelta
from typing import Any

import segno
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.recruit_sources import _rate
from app.db import get_session
from app.deps import AuthContext, error, require_any
from app.models.attendance import AttendanceRecord
from app.models.auth import User
from app.models.branch_ops import BranchRatingQr, CustomerRating
from app.models.employees import Employee
from app.models.org import Branch, Position
from app.rbac import matches
from app.services.notifications import deliver, notify, register_template
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/ratings", tags=["ratings"])
public_router = APIRouter(prefix="/v1/public/rate", tags=["public"])

register_template("rating.complaint", {"uz": "Mijoz past baho qo'ydi", "ru": "Клиент поставил низкую оценку"},
                  {"uz": "{branch}: {stars}★ — {comment}", "ru": "{branch}: {stars}★ — {comment}"})  # fmt: skip

can_read = require_any("ratings.read", "ratings.manage", "ratings.own")
LEVELS = {5: "A'lo", 4: "Yaxshi", 3: "Qoniqarli", 2: "Yomon", 1: "Juda yomon"}


def _bname(b: Branch | None) -> str:
    if not b:
        return "—"
    return f"№{b.number} {b.name}" if b.number else b.name


def _base(request: Request) -> str:
    from app.api.letters import _base_url  # noqa: PLC0415

    return _base_url(request)


async def _branch_scope(db: AsyncSession, auth: AuthContext) -> set[int] | None:
    """None = hamma filial (boshqaruv). Aks holda mudir/koordinator o'z filiallari."""
    if matches(auth.permissions, "ratings.read") or matches(auth.permissions, "ratings.manage"):
        return None
    rows = (await db.execute(select(Branch.id).where((Branch.manager_user_id == auth.user.id) | (Branch.coordinator_user_id == auth.user.id)))).all()
    return {r for (r,) in rows}


# --- QR kodlar ---


@router.get("/qr")
async def qr_list(q: str | None = None, status: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    stmt = select(Branch).where(Branch.is_active.is_(True))
    if q:
        stmt = stmt.where(Branch.name.ilike(f"%{q.strip()}%"))
    scope = await _branch_scope(db, auth)
    if scope is not None:
        stmt = stmt.where(Branch.id.in_(scope or {0}))
    blist = (await db.scalars(stmt.order_by(Branch.number.nulls_last(), Branch.name))).all()
    qrs = {r.branch_id: r for r in (await db.scalars(select(BranchRatingQr))).all()}
    mids = {b.manager_user_id for b in blist if b.manager_user_id}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(mids or {0})))).all()}
    items, counts = [], {"branches": len(blist), "active": 0, "none": 0, "blocked": 0}
    for b in blist:
        r = qrs.get(b.id)
        st = r.status if r else "none"
        counts[st] += 1
        if status and status != st:
            continue
        items.append({"branch_id": b.id, "name": _bname(b), "manager": names.get(b.manager_user_id or 0), "status": st,
                      "version": r.version if r else None, "url": f"{_base_and_path(r)}" if r else None})  # fmt: skip
    return {"counts": counts, "items": items}


def _base_and_path(r: BranchRatingQr) -> str:
    return f"/baho/{r.token}"


def _new_token() -> str:
    return secrets.token_urlsafe(18)


@router.post("/qr/all")
async def qr_create_all(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("ratings.manage"))):
    have = {b for (b,) in (await db.execute(select(BranchRatingQr.branch_id))).all()}
    created = 0
    for (bid,) in (await db.execute(select(Branch.id).where(Branch.is_active.is_(True)))).all():
        if bid not in have:
            db.add(BranchRatingQr(branch_id=bid, token=_new_token()))
            created += 1
    await db.commit()
    return {"created": created}


@router.post("/qr/{bid}/{action}")
async def qr_action(bid: int, action: str, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("ratings.manage"))):
    """create (yo'q bo'lsa), rotate (almashtirish: yangi token, versiya +1), block, unblock."""
    if not await db.get(Branch, bid):
        raise error(404, "not_found")
    r = await db.scalar(select(BranchRatingQr).where(BranchRatingQr.branch_id == bid))
    if action == "create":
        if not r:
            r = BranchRatingQr(branch_id=bid, token=_new_token())
            db.add(r)
    elif not r:
        raise error(404, "not_found")
    elif action == "rotate":
        r.token, r.version, r.status = _new_token(), r.version + 1, "active"
    elif action in ("block", "unblock"):
        r.status = "blocked" if action == "block" else "active"
    else:
        raise error(404, "not_found")
    r.updated_at = now()
    await db.commit()
    return {"branch_id": bid, "status": r.status, "version": r.version, "url": _base_and_path(r)}


@router.delete("/qr/{bid}", status_code=204)
async def qr_delete(bid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("ratings.manage"))):
    r = await db.scalar(select(BranchRatingQr).where(BranchRatingQr.branch_id == bid))
    if r:
        await db.delete(r)
        await db.commit()
    return Response(status_code=204)


@router.get("/qr/{bid}/svg")
async def qr_svg(bid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    r = await db.scalar(select(BranchRatingQr).where(BranchRatingQr.branch_id == bid))
    if not r:
        raise error(404, "not_found")
    buf = io.BytesIO()
    segno.make(f"{_base(request)}{_base_and_path(r)}", error="m").save(buf, kind="svg", scale=8, border=1, dark="#4c1d95")
    return Response(buf.getvalue(), media_type="image/svg+xml")


# --- Baholar ---


def _filters(stmt, target, branch_id, stars, complaints, days, scope):
    stmt = stmt.where(CustomerRating.target == target) if target else stmt
    if branch_id:
        stmt = stmt.where(CustomerRating.branch_id == branch_id)
    if stars:
        stmt = stmt.where(CustomerRating.stars == stars)
    if complaints:
        stmt = stmt.where(CustomerRating.stars <= 2)
    if days:
        stmt = stmt.where(CustomerRating.created_at >= now() - timedelta(days=days))
    if scope is not None:
        stmt = stmt.where(CustomerRating.branch_id.in_(scope or {0}))
    return stmt


async def _rows(db, auth, target, branch_id, stars, complaints, days, limit=500) -> list[dict[str, Any]]:
    scope = await _branch_scope(db, auth)
    stmt = _filters(select(CustomerRating), target, branch_id, stars, complaints, days, scope)
    rows = (await db.scalars(stmt.order_by(CustomerRating.created_at.desc()).limit(limit))).all()
    bids = {r.branch_id for r in rows}
    branches = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_(bids or {0})))).all()}
    uids = {b.manager_user_id for b in branches.values()} | {b.coordinator_user_id for b in branches.values()}
    users = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({i for i in uids if i} or {0})))).all()}
    emps = {e.id: e.full_name for e in (await db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows if r.employee_id} or {0})))).all()}
    see_client = matches(auth.permissions, "ratings.manage") or matches(auth.permissions, "ratings.read")
    out = []
    for r in rows:
        b = branches.get(r.branch_id)
        out.append({
            "id": r.id, "created_at": r.created_at, "target": r.target, "branch": {"id": r.branch_id, "name": _bname(b)},
            "manager": users.get(b.manager_user_id or 0) if b else None, "coordinator": users.get(b.coordinator_user_id or 0) if b else None,
            "employee": {"id": r.employee_id, "name": emps.get(r.employee_id)} if r.employee_id else None,
            "stars": r.stars, "cleanliness": LEVELS.get(r.cleanliness or 0), "assortment": LEVELS.get(r.assortment or 0), "comment": r.comment,
            "customer": {"name": r.customer_name, "phone": r.customer_phone} if see_client else None,
        })  # fmt: skip
    return out


@router.get("")
async def list_ratings(target: str | None = Query(default=None, pattern="^(employee|pharmacy)$"), branch_id: int | None = None, stars: int | None = Query(default=None, ge=1, le=5),
                       complaints: bool = False, days: int | None = Query(default=None, ge=1, le=366), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):  # fmt: skip
    items = await _rows(db, auth, target, branch_id, stars, complaints, days)
    avg = round(sum(i["stars"] for i in items) / len(items), 2) if items else None
    return {"count": len(items), "avg": avg, "low": sum(1 for i in items if i["stars"] <= 2), "items": items}


@router.get("/stats")
async def stats(branch_id: int | None = None, complaints: bool = False, days: int | None = Query(default=None, ge=1, le=366), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    scope = await _branch_scope(db, auth)
    base = _filters(select(CustomerRating), None, branch_id, None, complaints, days, scope).subquery()
    total, avg, low = (await db.execute(select(func.count(), func.avg(base.c.stars), func.count().filter(base.c.stars <= 2)))).one()
    by_branch = (await db.execute(select(base.c.branch_id, func.avg(base.c.stars), func.count()).group_by(base.c.branch_id).order_by(func.avg(base.c.stars)))).all()
    by_emp = (await db.execute(select(base.c.employee_id, func.avg(base.c.stars), func.count()).where(base.c.employee_id.is_not(None)).group_by(base.c.employee_id).order_by(func.avg(base.c.stars)).limit(20))).all()
    bnames = {b.id: _bname(b) for b in (await db.scalars(select(Branch).where(Branch.id.in_({r[0] for r in by_branch} or {0})))).all()}
    enames = {e.id: e.full_name for e in (await db.scalars(select(Employee).where(Employee.id.in_({r[0] for r in by_emp} or {0})))).all()}
    dist = dict((await db.execute(select(base.c.stars, func.count()).group_by(base.c.stars))).all())
    return {
        "total": total, "avg": round(float(avg), 2) if avg else None, "complaints": low, "distribution": {s: dist.get(s, 0) for s in range(5, 0, -1)},
        "branches": [{"id": b, "name": bnames.get(b), "avg": round(float(a), 2), "count": c} for b, a, c in by_branch],
        "employees": [{"id": e, "name": enames.get(e), "avg": round(float(a), 2), "count": c} for e, a, c in by_emp],
    }  # fmt: skip


@router.get("/export")
async def export(target: str | None = Query(default=None, pattern="^(employee|pharmacy)$"), branch_id: int | None = None, complaints: bool = False, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    items = await _rows(db, auth, target, branch_id, None, complaints, None, limit=20000)
    wb = Workbook()
    ws = wb.active
    ws.title = "Baholar"
    ws.append(["Sana", "Turi", "Filial", "Mudir", "Koordinator", "Xodim", "Baho", "Tozalik", "Tanlov", "Izoh", "Mijoz", "Telefon"])
    for i in items:
        c = i["customer"] or {}
        ws.append([i["created_at"].astimezone(tz()).strftime("%d.%m.%Y %H:%M"), "Xodim" if i["target"] == "employee" else "Dorixona", i["branch"]["name"], i["manager"], i["coordinator"],
                   (i["employee"] or {}).get("name"), i["stars"], i["cleanliness"], i["assortment"], i["comment"], c.get("name"), c.get("phone")])  # fmt: skip
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="mijozlar-baholari.xlsx"'})


# --- Ommaviy sahifa (mijoz) ---


async def _qr_by_token(db: AsyncSession, token: str) -> tuple[BranchRatingQr, Branch]:
    r = await db.scalar(select(BranchRatingQr).where(BranchRatingQr.token == token))
    b = await db.get(Branch, r.branch_id) if r else None
    if not r or not b or r.status != "active":
        raise error(404, "qr_invalid")
    return r, b


async def _on_shift(db: AsyncSession, branch_id: int) -> list[dict[str, Any]]:
    """Hozir smenada: bugun shu filialda kelgan va hali ketmagan xodimlar."""
    today = local_date(now())
    rows = (await db.execute(
        select(Employee.id, Employee.full_name, Position.name)
        .join(AttendanceRecord, AttendanceRecord.employee_id == Employee.id)
        .outerjoin(Position, Position.id == Employee.position_id)
        .where(AttendanceRecord.work_date == today, AttendanceRecord.check_out_at.is_(None), (AttendanceRecord.branch_id == branch_id) | ((AttendanceRecord.branch_id.is_(None)) & (Employee.branch_id == branch_id)))
        .distinct()
    )).all()  # fmt: skip
    return [{"id": i, "name": n, "position": p} for i, n, p in rows]


@public_router.get("/{token}")
async def public_get(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "rate_view", 120, 60)
    _, b = await _qr_by_token(db, token)
    return {"branch": _bname(b), "staff": await _on_shift(db, b.id)}


class RateIn(BaseModel):
    target: str = Field(pattern="^(employee|pharmacy)$")
    employee_id: int | None = None
    stars: int = Field(ge=1, le=5)
    cleanliness: int | None = Field(default=None, ge=1, le=5)
    assortment: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^\+?998\d{9}$")


@public_router.post("/{token}", status_code=201)
async def public_rate(token: str, body: RateIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "rate_post", 10, 3600)
    r, b = await _qr_by_token(db, token)
    if body.target == "employee":
        if not body.employee_id or body.employee_id not in {s["id"] for s in await _on_shift(db, b.id)}:
            raise error(422, "employee_not_on_shift")
    elif body.cleanliness is None or body.assortment is None:
        raise error(422, "fields_required")
    phone = body.phone if body.phone.startswith("+") else f"+{body.phone}"
    since = now() - timedelta(hours=6)
    if await db.scalar(select(CustomerRating.id).where(CustomerRating.branch_id == b.id, CustomerRating.customer_phone == phone, CustomerRating.target == body.target,
                                                       CustomerRating.employee_id.is_(None) if body.employee_id is None else CustomerRating.employee_id == body.employee_id,
                                                       CustomerRating.created_at >= since)):  # fmt: skip
        raise error(429, "already_rated")
    row = CustomerRating(branch_id=b.id, target=body.target, employee_id=body.employee_id if body.target == "employee" else None, stars=body.stars,
                         cleanliness=body.cleanliness if body.target == "pharmacy" else None, assortment=body.assortment if body.target == "pharmacy" else None,
                         comment=(body.comment or "").strip() or None, customer_name=body.name.strip(), customer_phone=phone, qr_version=r.version)  # fmt: skip
    db.add(row)
    notes = []
    if body.stars <= 2:
        to = {u for u in (b.manager_user_id, b.coordinator_user_id) if u}
        if to:
            notes = await notify(db, to, "rating.complaint", params={"branch": _bname(b), "stars": body.stars, "comment": (body.comment or "—")[:120]}, link="/ratings?tab=pharmacy" if body.target == "pharmacy" else "/ratings?tab=employee", severity="warning")
    await db.commit()
    if notes:
        await deliver(request.app, notes)
    return {"ok": True}



