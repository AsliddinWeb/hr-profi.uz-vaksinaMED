"""Shikoyat va murojaatlar: xodim yuboradi (ixtiyoriy anonim), HR ko'rib chiqadi va javob beradi."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.integrations import Complaint
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import now

router = APIRouter(prefix="/v1/complaints", tags=["complaints"])
CATEGORIES = "salary|manager|schedule|conditions|colleague|system|other"

register_template("complaint.new", {"uz": "Yangi shikoyat/murojaat", "ru": "Новая жалоба/обращение"}, {"uz": "{title}", "ru": "{title}"}, "warning")
register_template("complaint.answer", {"uz": "Murojaatingizga javob", "ru": "Ответ на ваше обращение"}, {"uz": "{title}: {result}. {text}", "ru": "{title}: {result}. {text}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def _out(c: Complaint, auth: AuthContext, names: dict[int, str]) -> dict[str, Any]:
    own = c.author_user_id == auth.user.id
    manage = has(auth, "complaints.manage")
    show_author = own or (manage and not c.is_anonymous)
    return {
        "id": c.id, "category": c.category, "title": c.title, "text": c.text, "status": c.status, "is_anonymous": c.is_anonymous, "created_at": c.created_at,
        "author": names.get(c.author_user_id or 0) if show_author else None, "assignee": names.get(c.assignee_id or 0), "response": c.response, "resolved_at": c.resolved_at,
        "history": [{**h, "actor": h.get("actor") if (h.get("action") != "created" or show_author) else None} for h in (c.history or [])],
        "own": own, "can_handle": manage and c.status in ("new", "in_progress"),
    }  # fmt: skip


async def _names(db: AsyncSession, rows: list[Complaint]) -> dict[int, str]:
    ids = {u for c in rows for u in (c.author_user_id, c.assignee_id) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


class ComplaintIn(BaseModel):
    category: str = Field(pattern=f"^({CATEGORIES})$")
    title: str = Field(min_length=3, max_length=200)
    text: str = Field(min_length=5, max_length=5000)
    is_anonymous: bool = False


@router.post("", status_code=201)
async def create(body: ComplaintIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not has(auth, "complaints.own"):
        raise error(403, "forbidden")
    emp = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id))
    moment = now()
    c = Complaint(author_user_id=auth.user.id, is_anonymous=body.is_anonymous, branch_id=emp.branch_id if emp else None, category=body.category, title=body.title.strip(), text=body.text.strip(), status="new", history=[])
    c.history = [{"action": "created", "actor": auth.user.full_name, "text": None, "at": moment.isoformat()}]
    db.add(c)
    await db.flush()
    notes = await notify(db, [u for u in await users_with_permission(db, "complaints.manage") if u != auth.user.id], "complaint.new", link=f"/complaints/{c.id}", params={"title": c.title})
    await audit(db, request, "complaint.create", actor=auth.user, entity="complaint", entity_id=c.id, data={"category": c.category, "anonymous": c.is_anonymous})
    await db.commit()
    await deliver(request.app, notes)
    return _out(c, auth, await _names(db, [c]))


@router.get("")
async def list_complaints(scope: str = Query(default="mine", pattern="^(mine|inbox)$"), status: str | None = Query(default=None, pattern="^(new|in_progress|resolved|rejected)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    stmt = select(Complaint).order_by(Complaint.id.desc()).limit(200)
    if scope == "inbox":
        if not has(auth, "complaints.manage"):
            raise error(403, "forbidden")
    else:
        stmt = stmt.where(Complaint.author_user_id == auth.user.id)
    if status:
        stmt = stmt.where(Complaint.status == status)
    rows = list((await db.scalars(stmt)).all())
    names = await _names(db, rows)
    return [_out(c, auth, names) for c in rows]


async def _load(db: AsyncSession, cid: int, auth: AuthContext, *, lock: bool = False) -> Complaint:
    stmt = select(Complaint).where(Complaint.id == cid)
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not c or not (c.author_user_id == auth.user.id or has(auth, "complaints.manage")):
        raise error(404, "not_found")
    return c


@router.get("/{cid}")
async def get_one(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    c = await _load(db, cid, auth)
    return _out(c, auth, await _names(db, [c]))


@router.post("/{cid}/take")
async def take(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not has(auth, "complaints.manage"):
        raise error(403, "forbidden")
    c = await _load(db, cid, auth, lock=True)
    if c.status not in ("new", "in_progress"):
        raise error(409, "already_decided")
    c.status, c.assignee_id = "in_progress", auth.user.id
    c.history = [*(c.history or []), {"action": "taken", "actor": auth.user.full_name, "text": None, "at": now().isoformat()}]
    await audit(db, request, "complaint.take", actor=auth.user, entity="complaint", entity_id=c.id)
    await db.commit()
    return _out(c, auth, await _names(db, [c]))


class AnswerIn(BaseModel):
    action: str = Field(pattern="^(resolve|reject)$")
    response: str = Field(min_length=3, max_length=3000)


@router.post("/{cid}/answer")
async def answer(cid: int, body: AnswerIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR javob beradi (hal qilindi / rad etildi). Muallif (anonim bo'lsa ham) javobni ilova ichida oladi, HR esa muallifni ko'rmaydi."""
    if not has(auth, "complaints.manage"):
        raise error(403, "forbidden")
    c = await _load(db, cid, auth, lock=True)
    if c.status not in ("new", "in_progress"):
        raise error(409, "already_decided")
    moment = now()
    c.status = "resolved" if body.action == "resolve" else "rejected"
    c.response, c.resolved_at, c.assignee_id = body.response.strip(), moment, c.assignee_id or auth.user.id
    c.history = [*(c.history or []), {"action": c.status, "actor": auth.user.full_name, "text": c.response, "at": moment.isoformat()}]
    notes = await notify(db, [c.author_user_id] if c.author_user_id else [], "complaint.answer", link=f"/complaints/{c.id}", params={"title": c.title, "result": "hal qilindi" if c.status == "resolved" else "rad etildi", "text": c.response[:200]})
    await audit(db, request, f"complaint.{body.action}", actor=auth.user, entity="complaint", entity_id=c.id)
    await db.commit()
    await deliver(request.app, notes)
    return _out(c, auth, await _names(db, [c]))
