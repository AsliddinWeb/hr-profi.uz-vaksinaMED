"""Topshiriqlar: ro'yxat, kanban, kalendar, izoh (chat), fayl, tarix, shablon, tahlil."""

import calendar
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.tasks import Task, TaskComment, TaskEvent, TaskFile, TaskTemplate
from app.services import tasks as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now, tz

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("tasks.own", "tasks.read", "tasks.manage")
Manager = require_any("tasks.manage")


async def _task(db: AsyncSession, task_id: int, auth: AuthContext, *, lock: bool = False) -> Task:
    stmt = select(Task).where(Task.id == task_id)
    t = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not t or not svc.can_view(auth, t):
        raise error(404, "not_found")
    return t


# --- Yordamchi ro'yxatlar ---------------------------------------------------------------


@router.get("/assignees")
async def assignees(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Ijrochi/kuzatuvchi tanlash uchun faol foydalanuvchilar (faqat ism)."""
    stmt = select(User.id, User.full_name).where(User.is_active.is_(True))
    if q and q.strip():
        stmt = stmt.where(User.full_name.ilike(f"%{q.strip()}%"))
    rows = (await db.execute(stmt.order_by(User.full_name).limit(15))).all()
    return [{"id": r.id, "name": r.full_name} for r in rows]


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)) -> dict[str, int]:
    """Menyu belgisi: menga biriktirilgan ochiq va muddati o'tgan topshiriqlar."""
    base = [Task.assignee_id == auth.user.id, Task.status != "done", Task.archived_at.is_(None)]
    open_n = await db.scalar(select(func.count()).select_from(Task).where(*base)) or 0
    late = await db.scalar(select(func.count()).select_from(Task).where(*base, Task.due_at < now())) or 0
    return {"open": open_n, "overdue": late}


# --- Ro'yxat, kanban, kalendar ----------------------------------------------------------


def _filters(auth: AuthContext, scope: str, assignee_id, priority, q, label, overdue) -> list[Any]:
    me = auth.user.id
    conds: list[Any] = [Task.archived_at.is_(None)]
    if scope == "mine":
        conds.append(Task.assignee_id == me)
    elif scope == "created":
        conds.append(Task.creator_id == me)
    elif scope == "watching":
        conds.append(Task.watchers.contains([me]))
    else:
        clause = svc.visible_clause(auth)
        if clause is not None:
            conds.append(clause)
    if assignee_id:
        conds.append(Task.assignee_id == assignee_id)
    if priority:
        conds.append(Task.priority == priority)
    if q and q.strip():
        conds.append(Task.title.ilike(f"%{q.strip()}%"))
    if label:
        conds.append(Task.labels.contains([label]))
    if overdue:
        conds.append(Task.status != "done")
        conds.append(Task.due_at < now())
    return conds


SCOPE = Query(default="mine", pattern="^(mine|created|watching|all)$")
PRIO = Query(default=None, pattern="^(low|normal|high|urgent)$")


@router.get("")
async def list_tasks(
    scope: str = SCOPE,
    status: str | None = Query(default=None, pattern="^(todo|in_progress|review|done|open)$"),
    assignee_id: int | None = None,
    priority: str | None = PRIO,
    q: str | None = None,
    label: str | None = None,
    overdue: bool = False,
    sort: str = Query(default="due", pattern="^(due|created|priority)$"),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    conds = _filters(auth, scope, assignee_id, priority, q, label, overdue)
    if status == "open":
        conds.append(Task.status != "done")
    elif status:
        conds.append(Task.status == status)
    total = await db.scalar(select(func.count()).select_from(Task).where(*conds)) or 0
    prio_rank = case((Task.priority == "urgent", 0), (Task.priority == "high", 1), (Task.priority == "normal", 2), else_=3)
    order = {"due": [Task.due_at.asc().nulls_last(), Task.id.desc()], "created": [Task.id.desc()], "priority": [prio_rank, Task.due_at.asc().nulls_last()]}[sort]
    rows = (await db.scalars(select(Task).where(*conds).order_by(*order).offset((page - 1) * size).limit(size))).all()
    names = await svc.user_names(db, list(rows))
    comments, files = await svc.counts(db, [t.id for t in rows])
    moment = now()
    return {"total": total, "page": page, "size": size, "items": [svc.task_out(t, names, moment, comments.get(t.id, 0), files.get(t.id, 0)) for t in rows]}


@router.get("/board")
async def board(
    scope: str = SCOPE,
    assignee_id: int | None = None,
    priority: str | None = PRIO,
    q: str | None = None,
    label: str | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    """Kanban: 4 ustun. Bajarilganlar faqat oxirgi 14 kundagilar; har ustunda <= 100 karta."""
    moment = now()
    conds = _filters(auth, scope, assignee_id, priority, q, label, False)
    columns: dict[str, Any] = {}
    all_tasks: list[Task] = []
    for status in svc.STATUSES:
        extra = [Task.status == status]
        if status == "done":
            extra.append(Task.completed_at >= moment - timedelta(days=14))
        total = await db.scalar(select(func.count()).select_from(Task).where(*conds, *extra)) or 0
        rows = list((await db.scalars(select(Task).where(*conds, *extra).order_by(Task.position, Task.id).limit(100))).all())
        columns[status] = {"total": total, "tasks": rows}
        all_tasks += rows
    names = await svc.user_names(db, all_tasks)
    comments, files = await svc.counts(db, [t.id for t in all_tasks])
    return {s: {"total": c["total"], "tasks": [svc.task_out(t, names, moment, comments.get(t.id, 0), files.get(t.id, 0)) for t in c["tasks"]]} for s, c in columns.items()}


@router.get("/calendar")
async def calendar_view(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    scope: str = SCOPE,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    """Oy kalendari: muddati shu oyga to'g'ri kelgan topshiriqlar."""
    y, m = int(month[:4]), int(month[5:])
    start = datetime(y, m, 1, tzinfo=tz())
    end = datetime(y, m, calendar.monthrange(y, m)[1], tzinfo=tz()) + timedelta(days=1)
    conds = _filters(auth, scope, None, None, None, None, False)
    rows = (await db.scalars(select(Task).where(*conds, Task.due_at >= start, Task.due_at < end).order_by(Task.due_at))).all()
    names = await svc.user_names(db, list(rows))
    moment = now()
    return {"month": month, "items": [svc.task_out(t, names, moment) for t in rows]}


# --- Yaratish va tahrirlash -------------------------------------------------------------


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_at: datetime | None = None
    assignee_id: int | None = None
    watchers: list[int] = []
    labels: list[str] = []
    template_id: int | None = None


@router.post("", status_code=201)
async def create(body: TaskIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    await svc.validate_people(db, auth, body.assignee_id, body.watchers)
    t = Task(
        title=body.title.strip(), description=(body.description or "").strip() or None, priority=body.priority,
        due_at=body.due_at, creator_id=auth.user.id, assignee_id=body.assignee_id, watchers=sorted(set(body.watchers)),
        labels=svc.clean_labels(body.labels), status="todo", template_id=body.template_id, created_at=now(),
    )  # fmt: skip
    t.position = await svc.next_position(db, "todo")
    db.add(t)
    await db.flush()
    svc.log(db, t, auth.user.id, "created")
    notes = []
    if t.assignee_id and t.assignee_id != auth.user.id:
        notes = await notify(db, [t.assignee_id], "tasks.assigned", link=f"/tasks/{t.id}", params={"title": t.title})
    await audit(db, request, "tasks.create", actor=auth.user, entity="task", entity_id=t.id, data={"assignee_id": t.assignee_id})
    await db.commit()
    await deliver(request.app, notes)
    names = await svc.user_names(db, [t])
    return svc.task_out(t, names, now())


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
        if not svc.sees_all(auth):
            raise error(403, "forbidden")
        clause = None
    else:
        clause = (Task.assignee_id == auth.user.id) | (Task.creator_id == auth.user.id)
    return await svc.analytics(db, start, end, clause)


# --- Shablonlar -------------------------------------------------------------------------


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_days: int | None = Field(default=None, ge=0, le=365)
    labels: list[str] = []
    is_active: bool = True


def template_out(t: TaskTemplate) -> dict[str, Any]:
    return {"id": t.id, "name": t.name, "title": t.title, "description": t.description, "priority": t.priority, "due_days": t.due_days, "labels": t.labels or [], "is_active": t.is_active}


@router.get("/templates")
async def templates(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    rows = (await db.scalars(select(TaskTemplate).order_by(TaskTemplate.name))).all()
    return [template_out(t) for t in rows if t.is_active or svc.has(auth, "tasks.manage")]


@router.get("/templates/{template_id}")
async def template_one(template_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Access)):
    t = await db.get(TaskTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    return template_out(t)


@router.post("/templates", status_code=201)
async def template_create(body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = TaskTemplate(**body.model_dump(exclude={"labels"}), labels=svc.clean_labels(body.labels))
    db.add(t)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "template_name_taken") from exc
    await audit(db, request, "tasks.template_create", actor=auth.user, entity="task_template", entity_id=t.id)
    await db.commit()
    return template_out(t)


@router.put("/templates/{template_id}")
async def template_update(template_id: int, body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = await db.get(TaskTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    for k, v in body.model_dump(exclude={"labels"}).items():
        setattr(t, k, v)
    t.labels = svc.clean_labels(body.labels)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "template_name_taken") from exc
    await audit(db, request, "tasks.template_update", actor=auth.user, entity="task_template", entity_id=t.id)
    await db.commit()
    return template_out(t)


@router.delete("/templates/{template_id}", status_code=204)
async def template_delete(template_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = await db.get(TaskTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    await audit(db, request, "tasks.template_delete", actor=auth.user, entity="task_template", entity_id=t.id, data={"name": t.name})
    await db.delete(t)
    await db.commit()


# --- Bitta topshiriq --------------------------------------------------------------------


@router.get("/{task_id}")
async def detail(task_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth)
    names = await svc.user_names(db, [t])
    comments, files = await svc.counts(db, [t.id])
    out = svc.task_out(t, names, now(), comments.get(t.id, 0), files.get(t.id, 0))
    out["description"] = t.description
    out["watchers"] = [{"id": u, "name": names.get(u)} for u in (t.watchers or [])]
    out["can_edit"] = svc.can_edit(auth, t)
    out["can_collaborate"] = svc.can_collaborate(auth, t)
    out["allowed_status"] = [s for s in svc.STATUSES if svc.can_move(auth, t, s)]
    events = (await db.scalars(select(TaskEvent).where(TaskEvent.task_id == t.id).order_by(TaskEvent.id))).all()
    actor_names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({e.actor_id for e in events if e.actor_id})))).all()} if events else {}
    out["events"] = [{"id": e.id, "action": e.action, "data": e.data, "actor": actor_names.get(e.actor_id or 0), "created_at": e.created_at} for e in events]
    return out


@router.put("/{task_id}")
async def update(task_id: int, body: TaskIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth, lock=True)
    if not svc.can_edit(auth, t):
        raise error(403, "forbidden")
    await svc.validate_people(db, auth, body.assignee_id, body.watchers)
    changes: dict[str, Any] = {}
    new = {
        "title": body.title.strip(), "description": (body.description or "").strip() or None, "priority": body.priority,
        "due_at": body.due_at, "assignee_id": body.assignee_id, "watchers": sorted(set(body.watchers)), "labels": svc.clean_labels(body.labels),
    }  # fmt: skip
    for k, v in new.items():
        old = getattr(t, k)
        if old != v:
            changes[k] = {"from": str(old) if k == "due_at" and old else old, "to": str(v) if k == "due_at" and v else v}
            setattr(t, k, v)
    if "due_at" in changes:
        t.notified_soon = t.notified_overdue = False
    notes = []
    if changes:
        svc.log(db, t, auth.user.id, "updated", {k: v for k, v in changes.items() if k != "description"} | ({"description": True} if "description" in changes else {}))
        if "assignee_id" in changes and t.assignee_id and t.assignee_id != auth.user.id:
            notes = await notify(db, [t.assignee_id], "tasks.assigned", link=f"/tasks/{t.id}", params={"title": t.title})
    await audit(db, request, "tasks.update", actor=auth.user, entity="task", entity_id=t.id, data={"fields": sorted(changes)})
    await db.commit()
    await deliver(request.app, notes)
    return svc.task_out(t, await svc.user_names(db, [t]), now())


class MoveIn(BaseModel):
    status: str = Field(pattern="^(todo|in_progress|review|done)$")
    before_id: int | None = None


@router.post("/{task_id}/move")
async def move(task_id: int, body: MoveIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Kartani ustunga ko'chirish (kanban) yoki holatni o'zgartirish."""
    t = await _task(db, task_id, auth, lock=True)
    notes = await svc.set_status(db, t, auth, body.status, body.before_id, now())
    await db.commit()
    await deliver(request.app, notes)
    return svc.task_out(t, await svc.user_names(db, [t]), now())


@router.delete("/{task_id}", status_code=204)
async def archive(task_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth, lock=True)
    if not svc.can_edit(auth, t):
        raise error(403, "forbidden")
    t.archived_at = now()
    svc.log(db, t, auth.user.id, "archived")
    await audit(db, request, "tasks.archive", actor=auth.user, entity="task", entity_id=t.id)
    await db.commit()


# --- Izohlar (chat) ---------------------------------------------------------------------


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


def _comment_out(c: TaskComment, names: dict[int, str]) -> dict[str, Any]:
    return {"id": c.id, "author": {"id": c.author_id, "name": names.get(c.author_id or 0)}, "body": c.body, "created_at": c.created_at}


@router.get("/{task_id}/comments")
async def comments(task_id: int, after_id: int = 0, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth)
    rows = (await db.scalars(select(TaskComment).where(TaskComment.task_id == t.id, TaskComment.id > after_id).order_by(TaskComment.id).limit(200))).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({c.author_id for c in rows if c.author_id})))).all()} if rows else {}
    return [_comment_out(c, names) for c in rows]


@router.post("/{task_id}/comments", status_code=201)
async def add_comment(task_id: int, body: CommentIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth)
    if not svc.can_collaborate(auth, t):
        raise error(403, "forbidden")
    c = TaskComment(task_id=t.id, author_id=auth.user.id, body=body.body.strip())
    db.add(c)
    await db.flush()
    svc.log(db, t, auth.user.id, "commented", {"comment_id": c.id})
    notes = await notify(db, [u for u in svc.participants(t) if u != auth.user.id], "tasks.comment", link=f"/tasks/{t.id}", params={"author": auth.user.full_name, "title": t.title})
    await db.commit()
    await deliver(request.app, notes)
    return _comment_out(c, {auth.user.id: auth.user.full_name})


# --- Fayllar ----------------------------------------------------------------------------


def _file_out(f: TaskFile, names: dict[int, str]) -> dict[str, Any]:
    return {"id": f.id, "filename": f.filename, "mime": f.mime, "size": f.size, "uploaded_by": names.get(f.uploaded_by or 0), "created_at": f.created_at}


@router.get("/{task_id}/files")
async def files(task_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth)
    rows = (await db.scalars(select(TaskFile).where(TaskFile.task_id == t.id).order_by(TaskFile.id))).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({f.uploaded_by for f in rows if f.uploaded_by})))).all()} if rows else {}
    return [_file_out(f, names) for f in rows]


@router.post("/{task_id}/files", status_code=201)
async def upload_file(task_id: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await _task(db, task_id, auth)
    if not svc.can_collaborate(auth, t):
        raise error(403, "forbidden")
    if (await db.scalar(select(func.count()).select_from(TaskFile).where(TaskFile.task_id == t.id)) or 0) >= svc.MAX_FILES:
        raise error(409, "too_many_files", max=svc.MAX_FILES)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"tasks/{t.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    f = TaskFile(task_id=t.id, uploaded_by=auth.user.id, key=key, filename=up.filename, mime=up.mime, size=len(up.data))
    db.add(f)
    await db.flush()
    svc.log(db, t, auth.user.id, "file_added", {"filename": f.filename})
    await db.commit()
    return _file_out(f, {auth.user.id: auth.user.full_name})


async def _file(db: AsyncSession, task_id: int, file_id: int, auth: AuthContext) -> tuple[Task, TaskFile]:
    t = await _task(db, task_id, auth)
    f = await db.get(TaskFile, file_id)
    if not f or f.task_id != t.id:
        raise error(404, "not_found")
    return t, f


@router.get("/{task_id}/files/{file_id}")
async def download_file(task_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _, f = await _file(db, task_id, file_id, auth)
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.filename)}"}
    return StreamingResponse(request.app.state.storage.stream(f.key), media_type=f.mime, headers=headers)


@router.delete("/{task_id}/files/{file_id}", status_code=204)
async def delete_file(task_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t, f = await _file(db, task_id, file_id, auth)
    if not (f.uploaded_by == auth.user.id or svc.can_edit(auth, t)):
        raise error(403, "forbidden")
    svc.log(db, t, auth.user.id, "file_removed", {"filename": f.filename})
    key = f.key
    await db.delete(f)
    await db.commit()
    await request.app.state.storage.delete(key)

