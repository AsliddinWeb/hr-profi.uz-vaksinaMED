"""AyTi: ticket kategoriyalari, ticketlar, oqim (olish/tayinlash/kutish/hal qilish/yopish/qayta ochish), izoh, fayl, tahlil."""

from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.helpdesk import Ticket, TicketCategory, TicketEvent, TicketFile
from app.models.org import Branch
from app.services import helpdesk as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/helpdesk", tags=["helpdesk"])
MAX_FILES = 20


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("helpdesk.own", "helpdesk.work", "helpdesk.read", "helpdesk.manage")
Staff = require_any("helpdesk.work", "helpdesk.read", "helpdesk.manage")
Manager = require_any("helpdesk.manage")


async def _ticket(db: AsyncSession, ticket_id: int, auth: AuthContext, *, lock: bool = False) -> Ticket:
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    t = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not t or not svc.can_view(auth, t):
        raise error(404, "not_found")
    return t


async def _lookups(db: AsyncSession):
    cats = {c.id: c.name for c in (await db.scalars(select(TicketCategory))).all()}
    brs = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    return cats, brs


async def _counts(db: AsyncSession, ids: list[int]):
    if not ids:
        return {}, {}
    c = dict((await db.execute(select(TicketEvent.ticket_id, func.count()).where(TicketEvent.ticket_id.in_(ids), TicketEvent.action == "comment").group_by(TicketEvent.ticket_id))).all())
    f = dict((await db.execute(select(TicketFile.ticket_id, func.count()).where(TicketFile.ticket_id.in_(ids)).group_by(TicketFile.ticket_id))).all())
    return c, f


async def _out_many(db: AsyncSession, rows: list[Ticket]) -> list[dict[str, Any]]:
    names = await svc.names(db, {x for t in rows for x in (t.requester_id, t.assignee_id)})
    cats, brs = await _lookups(db)
    comments, files = await _counts(db, [t.id for t in rows])
    moment = now()
    return [svc.ticket_out(t, names, cats, brs, moment, comments.get(t.id, 0), files.get(t.id, 0)) for t in rows]


def _flags(auth: AuthContext, t: Ticket) -> dict[str, bool]:
    return {
        "edit": svc.can_edit(auth, t), "take": svc.can_take(auth, t), "assign": svc.can_assign(auth, t), "work": svc.can_work(auth, t),
        "close": svc.can_close(auth, t), "reopen": svc.can_reopen(auth, t), "cancel": svc.can_cancel(auth, t),
        "internal": svc.staff(auth), "collaborate": t.status != "cancelled" and svc.can_view(auth, t),
    }  # fmt: skip


@router.get("/assignees")
async def assignees(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Staff)):
    ids = await users_with_permission(db, "helpdesk.work")
    if not ids:
        return []
    stmt = select(User.id, User.full_name).where(User.is_active.is_(True), User.id.in_(ids))
    if q and q.strip():
        stmt = stmt.where(User.full_name.ilike(f"%{q.strip()}%"))
    return [{"id": r.id, "name": r.full_name} for r in (await db.execute(stmt.order_by(User.full_name).limit(30))).all()]


@router.get("/branches")
async def branches(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    rows = (await db.execute(select(Branch.id, Branch.name).order_by(Branch.name))).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    T, uid = Ticket, auth.user.id

    async def n(*c):
        return await db.scalar(select(func.count()).select_from(T).where(*c)) or 0

    return {
        "todo": await n(T.assignee_id == uid, T.status.in_(svc.OPEN)),
        "to_confirm": await n(T.requester_id == uid, T.status == "resolved"),
        "waiting_me": await n(T.requester_id == uid, T.status == "waiting"),
        "queue": await n(T.status == "new", T.assignee_id.is_(None)) if svc.staff(auth) else 0,
    }


# --- Kategoriyalar ----------------------------------------------------------------------


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    default_assignee_id: int | None = None
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True


def _cat_out(c: TicketCategory, names: dict[int, str], used: int = 0) -> dict[str, Any]:
    return {
        "id": c.id, "name": c.name, "description": c.description, "sort_order": c.sort_order, "is_active": c.is_active,
        "default_assignee": {"id": c.default_assignee_id, "name": names.get(c.default_assignee_id or 0)} if c.default_assignee_id else None, "used": used,
    }  # fmt: skip


async def _check_assignee(db: AsyncSession, uid: int | None) -> None:
    if uid is not None and not await svc.helpers(db, uid):
        raise error(400, "unknown_assignee")


@router.get("/categories")
async def categories(all: bool = False, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    stmt = select(TicketCategory).order_by(TicketCategory.sort_order, TicketCategory.name)
    if not (all and svc.manager(auth)):
        stmt = stmt.where(TicketCategory.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    names = await svc.names(db, {c.default_assignee_id for c in rows})
    used = dict((await db.execute(select(Ticket.category_id, func.count()).group_by(Ticket.category_id))).all())
    return [_cat_out(c, names, used.get(c.id, 0)) for c in rows]


@router.get("/categories/{cat_id}")
async def category(cat_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(TicketCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.post("/categories", status_code=201)
async def create_category(body: CategoryIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    await _check_assignee(db, body.default_assignee_id)
    c = TicketCategory(**{**body.model_dump(), "name": body.name.strip()})
    db.add(c)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "category_exists") from None
    await audit(db, request, "helpdesk.category_create", actor=auth.user, entity="ticket_category", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.put("/categories/{cat_id}")
async def update_category(cat_id: int, body: CategoryIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(TicketCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    await _check_assignee(db, body.default_assignee_id)
    for k, v in {**body.model_dump(), "name": body.name.strip()}.items():
        setattr(c, k, v)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "category_exists") from None
    await audit(db, request, "helpdesk.category_update", actor=auth.user, entity="ticket_category", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(cat_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(TicketCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.category_id == c.id)):
        raise error(409, "category_in_use")
    await audit(db, request, "helpdesk.category_delete", actor=auth.user, entity="ticket_category", entity_id=c.id, data={"name": c.name})
    await db.delete(c)
    await db.commit()


@router.get("/analytics")
async def analytics(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Staff)):
    if end < start or (end - start).days > 92:
        raise error(400, "range_invalid", max_days=92)
    return await svc.analytics(db, start, end)


# --- Ticketlar --------------------------------------------------------------------------


class TicketIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    category_id: int | None = None
    branch_id: int | None = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    device_info: str | None = Field(default=None, max_length=200)


async def _validate_refs(db: AsyncSession, body: TicketIn) -> TicketCategory | None:
    cat = None
    if body.category_id is not None:
        cat = await db.get(TicketCategory, body.category_id)
        if not cat or not cat.is_active:
            raise error(400, "unknown_category")
    if body.branch_id is not None and not await db.get(Branch, body.branch_id):
        raise error(400, "unknown_branch")
    return cat


@router.get("")
async def listing(
    scope: str = Query(default="mine", pattern="^(mine|assigned|queue|all)$"),
    status: str | None = Query(default=None, pattern="^(new|in_progress|waiting|resolved|closed|cancelled|open)$"),
    category_id: int | None = None,
    branch_id: int | None = None,
    priority: str | None = Query(default=None, pattern="^(low|normal|high|urgent)$"),
    assignee_id: int | None = None,
    overdue: bool = False,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    T, uid = Ticket, auth.user.id
    conds: list = []
    if scope == "mine":
        conds.append(T.requester_id == uid)
    elif scope == "assigned":
        conds.append(T.assignee_id == uid)
    elif not svc.staff(auth):
        raise error(403, "forbidden")
    elif scope == "queue":
        conds += [T.status == "new", T.assignee_id.is_(None)]
    if status == "open":
        conds.append(T.status.in_(svc.ACTIVE))
    elif status:
        conds.append(T.status == status)
    if category_id:
        conds.append(T.category_id == category_id)
    if branch_id:
        conds.append(T.branch_id == branch_id)
    if priority:
        conds.append(T.priority == priority)
    if assignee_id:
        conds.append(T.assignee_id == assignee_id)
    if overdue:
        conds += [T.status.in_(svc.OPEN), T.due_at < now()]
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(T.title.ilike(like), T.number.ilike(like)))
    total = await db.scalar(select(func.count()).select_from(T).where(*conds)) or 0
    rows = (await db.scalars(select(T).where(*conds).order_by(T.opened_at.desc(), T.id.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "page": page, "size": size, "items": await _out_many(db, list(rows))}


@router.post("", status_code=201)
async def create(body: TicketIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    cat = await _validate_refs(db, body)
    t, notes = await svc.create(db, auth, title=body.title, description=body.description, category=cat, branch_id=body.branch_id, priority=body.priority, device_info=body.device_info, moment=now())
    await audit(db, request, "helpdesk.create", actor=auth.user, entity="ticket", entity_id=t.id, data={"number": t.number, "priority": t.priority, "assignee_id": t.assignee_id})
    await db.commit()
    await deliver(request.app, notes)
    await request.app.state.events.emit("ticket.created", ticket_id=t.id, number=t.number, priority=t.priority, title=t.title)
    return (await _out_many(db, [t]))[0]


@router.get("/{ticket_id}")
async def detail(ticket_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    out = (await _out_many(db, [t]))[0]
    events = (await db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == t.id).order_by(TicketEvent.id))).all()
    internal_ok = svc.staff(auth)
    events = [e for e in events if internal_ok or not (e.data or {}).get("internal")]
    names = await svc.names(db, {e.actor_id for e in events})
    return {
        **out, "description": t.description, "resolution": t.resolution, "rating_comment": t.rating_comment, "can": _flags(auth, t),
        "events": [{"id": e.id, "action": e.action, "from_status": e.from_status, "to_status": e.to_status, "note": e.note, "data": e.data, "actor": names.get(e.actor_id or 0), "actor_id": e.actor_id, "created_at": e.created_at} for e in events],
    }  # fmt: skip


@router.put("/{ticket_id}")
async def update(ticket_id: int, body: TicketIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    if not svc.can_edit(auth, t):
        raise error(409 if t.status != "new" else 403, "invalid_transition" if t.status != "new" else "forbidden")
    await _validate_refs(db, body)
    changed = sorted(k for k, v in {"title": body.title, "priority": body.priority, "category_id": body.category_id, "branch_id": body.branch_id}.items() if getattr(t, k) != v)
    if body.priority != t.priority:
        from datetime import timedelta

        t.due_at = t.opened_at + timedelta(hours=svc.SLA_HOURS[body.priority])
        t.sla_breached = False
    t.title, t.description, t.category_id, t.branch_id, t.priority = body.title.strip(), (body.description or "").strip() or None, body.category_id, body.branch_id, body.priority
    t.device_info = (body.device_info or "").strip() or None
    svc.log(db, t, auth.user.id, "edited", data={"changed": changed})
    await audit(db, request, "helpdesk.update", actor=auth.user, entity="ticket", entity_id=t.id, data={"number": t.number, "changed": changed})
    await db.commit()
    return (await _out_many(db, [t]))[0]


class AssignIn(BaseModel):
    assignee_id: int
    note: str | None = Field(default=None, max_length=1000)


class NoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=3, max_length=10000)


class CloseIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


async def _finish(db, request, auth, t: Ticket, action: str, notes, data: dict | None = None):
    await audit(db, request, f"helpdesk.{action}", actor=auth.user, entity="ticket", entity_id=t.id, data={"number": t.number, "status": t.status, **(data or {})})
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [t]))[0]


@router.post("/{ticket_id}/take")
async def take(ticket_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "take", await svc.take(db, t, auth, now()))


@router.post("/{ticket_id}/assign")
async def assign(ticket_id: int, body: AssignIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "assign", await svc.assign(db, t, auth, body.assignee_id, body.note, now()), {"assignee_id": body.assignee_id})


@router.post("/{ticket_id}/wait")
async def wait(ticket_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "wait", await svc.set_waiting(db, t, auth, body.note, now()))


@router.post("/{ticket_id}/resume")
async def resume(ticket_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "resume", await svc.resume(db, t, auth, now()))


@router.post("/{ticket_id}/resolve")
async def resolve(ticket_id: int, body: ResolveIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "resolve", await svc.resolve(db, t, auth, body.resolution, now()))


@router.post("/{ticket_id}/close")
async def close(ticket_id: int, body: CloseIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "close", await svc.close(db, t, auth, body.rating, body.comment, now()), {"rating": body.rating})


@router.post("/{ticket_id}/reopen")
async def reopen(ticket_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "reopen", await svc.reopen(db, t, auth, body.note, now()))


@router.post("/{ticket_id}/cancel")
async def cancel(ticket_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth, lock=True)
    return await _finish(db, request, auth, t, "cancel", await svc.cancel(db, t, auth, body.note))


# --- Izohlar (tarix jadvalida; ichki izoh so'rovchiga ko'rinmaydi) ------------------------


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    internal: bool = False


@router.post("/{ticket_id}/comments", status_code=201)
async def add_comment(ticket_id: int, body: CommentIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    if t.status == "cancelled":
        raise error(409, "invalid_transition")
    if body.internal and not svc.staff(auth):
        raise error(403, "forbidden")
    svc.log(db, t, auth.user.id, "comment", body.body.strip(), data={"internal": True} if body.internal else None)
    if svc.staff(auth) and t.first_response_at is None and not body.internal:
        t.first_response_at = now()
    notes: list = []
    if not body.internal:
        targets = {u for u in (t.requester_id, t.assignee_id) if u and u != auth.user.id}
        notes = await notify(db, list(targets), "helpdesk.comment", link=f"/helpdesk/{t.id}", params={"number": t.number, "title": t.title})
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True}


# --- Fayllar ----------------------------------------------------------------------------


def _file_out(f: TicketFile, names: dict[int, str]) -> dict[str, Any]:
    return {"id": f.id, "filename": f.filename, "mime": f.mime, "size": f.size, "uploaded_by": names.get(f.uploaded_by or 0), "created_at": f.created_at}


@router.get("/{ticket_id}/files")
async def files(ticket_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    rows = (await db.scalars(select(TicketFile).where(TicketFile.ticket_id == t.id).order_by(TicketFile.id))).all()
    names = await svc.names(db, {f.uploaded_by for f in rows})
    return [_file_out(f, names) for f in rows]


@router.post("/{ticket_id}/files", status_code=201)
async def upload_file(ticket_id: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    if t.status == "cancelled":
        raise error(409, "invalid_transition")
    if (await db.scalar(select(func.count()).select_from(TicketFile).where(TicketFile.ticket_id == t.id)) or 0) >= MAX_FILES:
        raise error(409, "too_many_files", max=MAX_FILES)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"helpdesk/{t.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    f = TicketFile(ticket_id=t.id, uploaded_by=auth.user.id, key=key, filename=up.filename, mime=up.mime, size=len(up.data))
    db.add(f)
    await db.flush()
    svc.log(db, t, auth.user.id, "edited", data={"file_added": f.filename})
    await db.commit()
    return _file_out(f, {auth.user.id: auth.user.full_name})


@router.get("/{ticket_id}/files/{file_id}")
async def download_file(ticket_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    f = await db.get(TicketFile, file_id)
    if not f or f.ticket_id != t.id:
        raise error(404, "not_found")
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.filename)}"}
    return StreamingResponse(request.app.state.storage.stream(f.key), media_type=f.mime, headers=headers)


@router.delete("/{ticket_id}/files/{file_id}", status_code=204)
async def delete_file(ticket_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _ticket(db, ticket_id, auth)
    f = await db.get(TicketFile, file_id)
    if not f or f.ticket_id != t.id:
        raise error(404, "not_found")
    if not (f.uploaded_by == auth.user.id or svc.manager(auth)):
        raise error(403, "forbidden")
    key = f.key
    await db.delete(f)
    await db.commit()
    await request.app.state.storage.delete(key)
