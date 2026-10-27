"""Ehtiyojlar: kategoriyalar, so'rovlar, 4 bosqichli oqim, izoh, fayl, tarix, tahlil."""

from datetime import date, datetime
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
from app.models.needs import NeedCategory, NeedComment, NeedEvent, NeedFile, NeedRequest
from app.models.org import Branch
from app.services import needs as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/needs", tags=["needs"])
MAX_FILES = 20


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("needs.own", "needs.work", "needs.dispatch", "needs.manage")
Manager = require_any("needs.manage")


async def _need(db: AsyncSession, need_id: int, auth: AuthContext, *, lock: bool = False) -> NeedRequest:
    stmt = select(NeedRequest).where(NeedRequest.id == need_id)
    n = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not n or not svc.can_view(auth, n):
        raise error(404, "not_found")
    return n


async def _lookups(db: AsyncSession) -> tuple[dict[int, str], dict[int, str]]:
    cats = {c.id: c.name for c in (await db.scalars(select(NeedCategory))).all()}
    brs = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    return cats, brs


async def _counts(db: AsyncSession, ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not ids:
        return {}, {}
    c = dict((await db.execute(select(NeedComment.need_id, func.count()).where(NeedComment.need_id.in_(ids)).group_by(NeedComment.need_id))).all())
    f = dict((await db.execute(select(NeedFile.need_id, func.count()).where(NeedFile.need_id.in_(ids)).group_by(NeedFile.need_id))).all())
    return c, f


async def _out_many(db: AsyncSession, rows: list[NeedRequest]) -> list[dict[str, Any]]:
    names = await svc.names(db, {x for n in rows for x in (n.requester_id, n.assignee_id)})
    cats, brs = await _lookups(db)
    comments, files = await _counts(db, [n.id for n in rows])
    moment = now()
    return [svc.need_out(n, names, cats, brs, moment, comments.get(n.id, 0), files.get(n.id, 0)) for n in rows]


def _flags(auth: AuthContext, n: NeedRequest) -> dict[str, bool]:
    return {
        "edit": svc.can_edit(auth, n), "assign": svc.can_assign(auth, n), "complete": svc.can_complete(auth, n),
        "confirm": svc.can_confirm(auth, n), "cancel": svc.can_cancel(auth, n), "collaborate": svc.can_view(auth, n) and n.status != "cancelled",
    }  # fmt: skip


# --- Yordamchi -------------------------------------------------------------------------


@router.get("/assignees")
async def assignees(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Ijrochi bo'la oladigan (needs.work) faol foydalanuvchilar."""
    ids = await users_with_permission(db, "needs.work")
    if not ids:
        return []
    stmt = select(User.id, User.full_name).where(User.is_active.is_(True), User.id.in_(ids))
    if q and q.strip():
        stmt = stmt.where(User.full_name.ilike(f"%{q.strip()}%"))
    return [{"id": r.id, "name": r.full_name} for r in (await db.execute(stmt.order_by(User.full_name).limit(30))).all()]


@router.get("/branches")
async def branches(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """So'rovda filial tanlash uchun (filiallarni o'qish huquqisiz ham)."""
    rows = (await db.execute(select(Branch.id, Branch.name).order_by(Branch.name))).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Yon panel belgilari: menga kelganlar / tasdiq kutayotganlar / tayinlanmaganlar."""
    N, uid = NeedRequest, auth.user.id

    async def n(*c):
        return await db.scalar(select(func.count()).select_from(N).where(*c)) or 0

    return {
        "todo": await n(N.assignee_id == uid, N.status == "assigned"),
        "to_confirm": await n(N.requester_id == uid, N.status == "completed"),
        "unassigned": await n(N.status == "requested") if svc.dispatcher(auth) else 0,
    }


# --- Kategoriyalar ----------------------------------------------------------------------


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    default_assignee_id: int | None = None
    sla_days: int | None = Field(default=None, ge=1, le=365)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True


def _cat_out(c: NeedCategory, names: dict[int, str], used: int = 0) -> dict[str, Any]:
    return {
        "id": c.id, "name": c.name, "description": c.description, "sla_days": c.sla_days, "sort_order": c.sort_order, "is_active": c.is_active,
        "default_assignee": {"id": c.default_assignee_id, "name": names.get(c.default_assignee_id or 0)} if c.default_assignee_id else None,
        "used": used,
    }  # fmt: skip


async def _check_assignee(db: AsyncSession, uid: int | None) -> None:
    if uid is not None and not await svc.worker_ok(db, uid):
        raise error(400, "unknown_assignee")


@router.get("/categories")
async def categories(all: bool = False, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    stmt = select(NeedCategory).order_by(NeedCategory.sort_order, NeedCategory.name)
    if not (all and svc.has(auth, "needs.manage")):
        stmt = stmt.where(NeedCategory.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    names = await svc.names(db, {c.default_assignee_id for c in rows})
    used = dict((await db.execute(select(NeedRequest.category_id, func.count()).group_by(NeedRequest.category_id))).all())
    return [_cat_out(c, names, used.get(c.id, 0)) for c in rows]


@router.get("/categories/{cat_id}")
async def category(cat_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(NeedCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.post("/categories", status_code=201)
async def create_category(body: CategoryIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    await _check_assignee(db, body.default_assignee_id)
    c = NeedCategory(**{**body.model_dump(), "name": body.name.strip()})
    db.add(c)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "category_exists") from None
    await audit(db, request, "needs.category_create", actor=auth.user, entity="need_category", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.put("/categories/{cat_id}")
async def update_category(cat_id: int, body: CategoryIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(NeedCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    await _check_assignee(db, body.default_assignee_id)
    for k, v in {**body.model_dump(), "name": body.name.strip()}.items():
        setattr(c, k, v)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "category_exists") from None
    await audit(db, request, "needs.category_update", actor=auth.user, entity="need_category", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return _cat_out(c, await svc.names(db, {c.default_assignee_id}))


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(cat_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    c = await db.get(NeedCategory, cat_id)
    if not c:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(NeedRequest).where(NeedRequest.category_id == c.id)):
        raise error(409, "category_in_use")
    await audit(db, request, "needs.category_delete", actor=auth.user, entity="need_category", entity_id=c.id, data={"name": c.name})
    await db.delete(c)
    await db.commit()


# --- Tahlil -----------------------------------------------------------------------------


@router.get("/analytics")
async def analytics(
    start: date,
    end: date,
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    if end < start or (end - start).days > 92:
        raise error(400, "range_invalid", max_days=92)
    if scope == "all":
        if not svc.dispatcher(auth):
            raise error(403, "forbidden")
        clause = None
    else:
        clause = or_(NeedRequest.requester_id == auth.user.id, NeedRequest.assignee_id == auth.user.id)
    return await svc.analytics(db, start, end, clause)


# --- So'rovlar --------------------------------------------------------------------------


class NeedIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    category_id: int | None = None
    branch_id: int | None = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_at: datetime | None = None


async def _validate_refs(db: AsyncSession, body: NeedIn) -> NeedCategory | None:
    cat = None
    if body.category_id is not None:
        cat = await db.get(NeedCategory, body.category_id)
        if not cat or not cat.is_active:
            raise error(400, "unknown_category")
    if body.branch_id is not None and not await db.get(Branch, body.branch_id):
        raise error(400, "unknown_branch")
    return cat


@router.get("")
async def listing(
    scope: str = Query(default="mine", pattern="^(mine|assigned|all)$"),
    status: str | None = Query(default=None, pattern="^(requested|assigned|completed|confirmed|cancelled|open)$"),
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
    N, uid = NeedRequest, auth.user.id
    conds: list = []
    if scope == "mine":
        conds.append(N.requester_id == uid)
    elif scope == "assigned":
        conds.append(N.assignee_id == uid)
    elif not svc.dispatcher(auth):
        raise error(403, "forbidden")
    if status == "open":
        conds.append(N.status.in_(svc.ACTIVE))
    elif status:
        conds.append(N.status == status)
    if category_id:
        conds.append(N.category_id == category_id)
    if branch_id:
        conds.append(N.branch_id == branch_id)
    if priority:
        conds.append(N.priority == priority)
    if assignee_id:
        conds.append(N.assignee_id == assignee_id)
    if overdue:
        conds += [N.status.in_(svc.OPEN), N.due_at < now()]
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(N.title.ilike(like), N.number.ilike(like)))
    total = await db.scalar(select(func.count()).select_from(N).where(*conds)) or 0
    rows = (await db.scalars(select(N).where(*conds).order_by(N.requested_at.desc(), N.id.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "page": page, "size": size, "items": await _out_many(db, list(rows))}


@router.post("", status_code=201)
async def create(body: NeedIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    cat = await _validate_refs(db, body)
    n, notes = await svc.create(db, auth, title=body.title, description=body.description, category=cat, branch_id=body.branch_id, priority=body.priority, due_at=body.due_at, moment=now())
    await audit(db, request, "needs.request", actor=auth.user, entity="need", entity_id=n.id, data={"number": n.number, "title": n.title, "assignee_id": n.assignee_id})
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [n]))[0]


@router.get("/{need_id}")
async def detail(need_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth)
    out = (await _out_many(db, [n]))[0]
    events = (await db.scalars(select(NeedEvent).where(NeedEvent.need_id == n.id).order_by(NeedEvent.id))).all()
    names = await svc.names(db, {e.actor_id for e in events})
    return {
        **out, "description": n.description, "report": n.report, "confirm_note": n.confirm_note, "can": _flags(auth, n),
        "events": [{"id": e.id, "action": e.action, "note": e.note, "data": e.data, "actor": names.get(e.actor_id or 0), "created_at": e.created_at} for e in events],
    }  # fmt: skip


@router.put("/{need_id}")
async def update(need_id: int, body: NeedIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    if not svc.can_edit(auth, n):
        raise error(409 if n.status not in svc.OPEN else 403, "invalid_transition" if n.status not in svc.OPEN else "forbidden")
    await _validate_refs(db, body)
    changed = {k: str(v) for k, v in {"title": body.title, "priority": body.priority, "category_id": body.category_id, "branch_id": body.branch_id, "due_at": body.due_at}.items() if getattr(n, k) != v}
    n.title, n.description, n.category_id, n.branch_id, n.priority = body.title.strip(), (body.description or "").strip() or None, body.category_id, body.branch_id, body.priority
    if body.due_at != n.due_at:
        n.due_at, n.notified_soon, n.notified_overdue = body.due_at, False, False
    svc.log(db, n, auth.user.id, "updated", data={"changed": sorted(changed)})
    await audit(db, request, "needs.update", actor=auth.user, entity="need", entity_id=n.id, data={"number": n.number, "changed": sorted(changed)})
    await db.commit()
    return (await _out_many(db, [n]))[0]


class AssignIn(BaseModel):
    assignee_id: int
    note: str | None = Field(default=None, max_length=1000)


class ReportIn(BaseModel):
    report: str = Field(min_length=3, max_length=10000)


class ConfirmIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    note: str | None = Field(default=None, max_length=1000)


class NoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


async def _finish(db, request, auth, n: NeedRequest, action: str, notes, data: dict | None = None):
    await audit(db, request, f"needs.{action}", actor=auth.user, entity="need", entity_id=n.id, data={"number": n.number, "status": n.status, **(data or {})})
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [n]))[0]


@router.post("/{need_id}/assign")
async def assign(need_id: int, body: AssignIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    notes = await svc.assign(db, n, auth, body.assignee_id, body.note, now())
    return await _finish(db, request, auth, n, "assign", notes, {"assignee_id": body.assignee_id})


@router.post("/{need_id}/complete")
async def complete(need_id: int, body: ReportIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    notes = await svc.complete(db, n, auth, body.report, now())
    return await _finish(db, request, auth, n, "complete", notes)


@router.post("/{need_id}/confirm")
async def confirm(need_id: int, body: ConfirmIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    notes = await svc.confirm(db, n, auth, body.rating, body.note, now())
    return await _finish(db, request, auth, n, "confirm", notes, {"rating": body.rating})


@router.post("/{need_id}/return")
async def send_back(need_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    notes = await svc.send_back(db, n, auth, body.note)
    return await _finish(db, request, auth, n, "return", notes, {"note": body.note})


@router.post("/{need_id}/cancel")
async def cancel(need_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth, lock=True)
    notes = await svc.cancel(db, n, auth, body.note)
    return await _finish(db, request, auth, n, "cancel", notes, {"note": body.note})


# --- Izohlar ----------------------------------------------------------------------------


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


def _comment_out(c: NeedComment, names: dict[int, str]) -> dict[str, Any]:
    return {"id": c.id, "author": {"id": c.author_id, "name": names.get(c.author_id or 0)}, "body": c.body, "created_at": c.created_at}


@router.get("/{need_id}/comments")
async def comments(need_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth)
    rows = (await db.scalars(select(NeedComment).where(NeedComment.need_id == n.id).order_by(NeedComment.id).limit(300))).all()
    names = await svc.names(db, {c.author_id for c in rows})
    return [_comment_out(c, names) for c in rows]


@router.post("/{need_id}/comments", status_code=201)
async def add_comment(need_id: int, body: CommentIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth)
    if n.status == "cancelled":
        raise error(409, "invalid_transition")
    c = NeedComment(need_id=n.id, author_id=auth.user.id, body=body.body.strip())
    db.add(c)
    await db.flush()
    targets = {u for u in (n.requester_id, n.assignee_id) if u and u != auth.user.id}
    notes = await notify(db, list(targets), "needs.comment", link=f"/needs/{n.id}", params={"author": auth.user.full_name, "number": n.number})
    await db.commit()
    await deliver(request.app, notes)
    return _comment_out(c, {auth.user.id: auth.user.full_name})


# --- Fayllar ----------------------------------------------------------------------------


def _file_out(f: NeedFile, names: dict[int, str]) -> dict[str, Any]:
    return {"id": f.id, "filename": f.filename, "mime": f.mime, "size": f.size, "uploaded_by": names.get(f.uploaded_by or 0), "created_at": f.created_at}


@router.get("/{need_id}/files")
async def files(need_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth)
    rows = (await db.scalars(select(NeedFile).where(NeedFile.need_id == n.id).order_by(NeedFile.id))).all()
    names = await svc.names(db, {f.uploaded_by for f in rows})
    return [_file_out(f, names) for f in rows]


@router.post("/{need_id}/files", status_code=201)
async def upload_file(need_id: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n = await _need(db, need_id, auth)
    if n.status == "cancelled":
        raise error(409, "invalid_transition")
    if (await db.scalar(select(func.count()).select_from(NeedFile).where(NeedFile.need_id == n.id)) or 0) >= MAX_FILES:
        raise error(409, "too_many_files", max=MAX_FILES)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"needs/{n.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    f = NeedFile(need_id=n.id, uploaded_by=auth.user.id, key=key, filename=up.filename, mime=up.mime, size=len(up.data))
    db.add(f)
    await db.flush()
    svc.log(db, n, auth.user.id, "file_added", data={"filename": f.filename})
    await db.commit()
    return _file_out(f, {auth.user.id: auth.user.full_name})


async def _file(db: AsyncSession, need_id: int, file_id: int, auth: AuthContext) -> tuple[NeedRequest, NeedFile]:
    n = await _need(db, need_id, auth)
    f = await db.get(NeedFile, file_id)
    if not f or f.need_id != n.id:
        raise error(404, "not_found")
    return n, f


@router.get("/{need_id}/files/{file_id}")
async def download_file(need_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _, f = await _file(db, need_id, file_id, auth)
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.filename)}"}
    return StreamingResponse(request.app.state.storage.stream(f.key), media_type=f.mime, headers=headers)


@router.delete("/{need_id}/files/{file_id}", status_code=204)
async def delete_file(need_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    n, f = await _file(db, need_id, file_id, auth)
    if not (f.uploaded_by == auth.user.id or svc.dispatcher(auth)):
        raise error(403, "forbidden")
    svc.log(db, n, auth.user.id, "file_removed", data={"filename": f.filename})
    key = f.key
    await db.delete(f)
    await db.commit()
    await request.app.state.storage.delete(key)
