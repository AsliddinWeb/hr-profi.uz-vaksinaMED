"""Topshiriqlar: ruxsatlar, holat qoidalari, kanban tartibi, tarix, bildirishnomalar, muddat nazorati, tahlil."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import User
from app.models.tasks import Task, TaskComment, TaskEvent, TaskFile
from app.rbac import matches
from app.services.notifications import notify, register_template
from app.timeutil import local_date, now, tz

STATUSES = ("todo", "in_progress", "review", "done")
PRIORITIES = ("low", "normal", "high", "urgent")
MAX_WATCHERS = 10
MAX_LABELS = 5
MAX_FILES = 20
SOON_HOURS = 24
STEP = 1000.0

register_template("tasks.assigned", {"uz": "Sizga topshiriq berildi", "ru": "Вам назначено поручение"}, {"uz": "{title}", "ru": "{title}"}, "info")
register_template("tasks.status", {"uz": "Topshiriq holati o'zgardi", "ru": "Статус поручения изменён"}, {"uz": "{title}: {status}", "ru": "{title}: {status}"}, "info")
register_template("tasks.comment", {"uz": "Topshiriqqa yangi izoh", "ru": "Новый комментарий к поручению"}, {"uz": "{author}: {title}", "ru": "{author}: {title}"}, "info")
register_template("tasks.due_soon", {"uz": "Topshiriq muddati yaqin", "ru": "Срок поручения близок"}, {"uz": "{title} — {due}", "ru": "{title} — {due}"}, "warning")
register_template("tasks.overdue", {"uz": "Topshiriq muddati o'tdi", "ru": "Поручение просрочено"}, {"uz": "{title} — {due}", "ru": "{title} — {due}"}, "danger")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "tasks.read") or has(auth, "tasks.manage")


def is_participant(task: Task, uid: int) -> bool:
    return task.creator_id == uid or task.assignee_id == uid or uid in (task.watchers or [])


def can_view(auth: AuthContext, task: Task) -> bool:
    return is_participant(task, auth.user.id) or sees_all(auth)


def can_edit(auth: AuthContext, task: Task) -> bool:
    return task.archived_at is None and (task.creator_id == auth.user.id or has(auth, "tasks.manage"))


def can_collaborate(auth: AuthContext, task: Task) -> bool:
    """Izoh, fayl, holatni o'zgartirish: ishtirokchilar va boshqaruvchilar."""
    return task.archived_at is None and (is_participant(task, auth.user.id) or has(auth, "tasks.manage"))


def can_move(auth: AuthContext, task: Task, new_status: str) -> bool:
    if task.archived_at is not None:
        return False
    me = auth.user.id
    manage = has(auth, "tasks.manage")
    owner = task.creator_id == me or manage
    if not (owner or task.assignee_id == me):
        return False
    if new_status == "done":
        return owner or (task.creator_id == task.assignee_id == me)  # bajaruvchi "tekshiruv"gacha olib boradi, yopish yaratuvchida
    if task.status == "done":
        return owner  # qayta ochish
    return True


STATUS_UZ = {"todo": "Bajarilishi kerak", "in_progress": "Jarayonda", "review": "Tekshiruvda", "done": "Bajarildi"}


def log(db: AsyncSession, task: Task, actor_id: int | None, action: str, data: dict | None = None) -> None:
    db.add(TaskEvent(task_id=task.id, actor_id=actor_id, action=action, data=data))


def participants(task: Task) -> list[int]:
    return list(dict.fromkeys([u for u in [task.creator_id, task.assignee_id, *(task.watchers or [])] if u]))


async def active_users(db: AsyncSession, ids: list[int]) -> dict[int, User]:
    if not ids:
        return {}
    return {u.id: u for u in (await db.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True)))).all()}


async def validate_people(db: AsyncSession, auth: AuthContext, assignee_id: int | None, watchers: list[int]) -> None:
    if assignee_id is not None and assignee_id != auth.user.id and not (has(auth, "tasks.assign") or has(auth, "tasks.manage")):
        raise error(403, "cannot_assign_others")
    if len(set(watchers)) > MAX_WATCHERS:
        raise error(400, "too_many_watchers", max=MAX_WATCHERS)
    wanted = [u for u in [assignee_id, *watchers] if u]
    found = await active_users(db, wanted)
    if any(u not in found for u in wanted):
        raise error(400, "unknown_user")


def clean_labels(labels: list[str]) -> list[str]:
    out = []
    for raw in labels:
        s = raw.strip()[:24]
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)
    if len(out) > MAX_LABELS:
        raise error(400, "too_many_labels", max=MAX_LABELS)
    return out


async def next_position(db: AsyncSession, status: str) -> float:
    top = await db.scalar(select(func.max(Task.position)).where(Task.status == status, Task.archived_at.is_(None)))
    return (top or 0.0) + STEP


async def place(db: AsyncSession, task: Task, status: str, before_id: int | None) -> None:
    """Kartani `status` ustunida `before_id` kartasidan oldinga (yo'q bo'lsa oxiriga) qo'yadi."""
    if before_id is None:
        task.position = await next_position(db, status)
        return
    before = await db.get(Task, before_id)
    if not before or before.status != status or before.archived_at is not None or before.id == task.id:
        task.position = await next_position(db, status)
        return
    prev = await db.scalar(
        select(func.max(Task.position)).where(Task.status == status, Task.archived_at.is_(None), Task.position < before.position, Task.id != task.id)
    )
    task.position = (prev + before.position) / 2 if prev is not None else before.position - STEP


async def set_status(db: AsyncSession, task: Task, auth: AuthContext, new_status: str, before_id: int | None, moment: datetime):
    if new_status not in STATUSES:
        raise error(400, "status_invalid")
    if not can_move(auth, task, new_status):
        raise error(403, "forbidden")
    old = task.status
    if old != new_status:
        task.status = new_status
        task.completed_at = moment if new_status == "done" else None
        if new_status != "done":
            task.notified_soon = task.notified_overdue = False
        log(db, task, auth.user.id, "status", {"from": old, "to": new_status})
    await place(db, task, new_status, before_id)
    notes = []
    if old != new_status:
        others = [u for u in participants(task) if u != auth.user.id]
        notes = await notify(db, others, "tasks.status", link=f"/tasks/{task.id}", params={"title": task.title, "status": STATUS_UZ[new_status]})
    return notes


# --- Muddat nazorati ---------------------------------------------------------------------


async def check_deadlines(db: AsyncSession, moment: datetime):
    """Yaqinlashgan (24 soat) va o'tgan muddatlar haqida bir martadan xabar beradi."""
    base = and_(Task.status != "done", Task.archived_at.is_(None), Task.due_at.is_not(None))
    notes: list = []
    soon = (await db.scalars(select(Task).where(base, Task.due_at > moment, Task.due_at <= moment + timedelta(hours=SOON_HOURS), Task.notified_soon.is_(False)))).all()
    for t in soon:
        t.notified_soon = True
        if t.assignee_id:
            notes += await notify(db, [t.assignee_id], "tasks.due_soon", link=f"/tasks/{t.id}", params={"title": t.title, "due": fmt_due(t.due_at)})
    late = (await db.scalars(select(Task).where(base, Task.due_at <= moment, Task.notified_overdue.is_(False)))).all()
    for t in late:
        t.notified_overdue = True
        log(db, t, None, "overdue")
        notes += await notify(db, [u for u in {t.assignee_id, t.creator_id} if u], "tasks.overdue", link=f"/tasks/{t.id}", params={"title": t.title, "due": fmt_due(t.due_at)})
    return len(soon), len(late), notes


def fmt_due(dt: datetime | None) -> str:
    return dt.astimezone(tz()).strftime("%d.%m.%Y %H:%M") if dt else "—"


# --- Serializatsiya ---------------------------------------------------------------------


async def counts(db: AsyncSession, ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not ids:
        return {}, {}
    c = dict((await db.execute(select(TaskComment.task_id, func.count()).where(TaskComment.task_id.in_(ids)).group_by(TaskComment.task_id))).all())
    f = dict((await db.execute(select(TaskFile.task_id, func.count()).where(TaskFile.task_id.in_(ids)).group_by(TaskFile.task_id))).all())
    return c, f


async def user_names(db: AsyncSession, tasks: list[Task]) -> dict[int, str]:
    ids = {u for t in tasks for u in (t.creator_id, t.assignee_id, *(t.watchers or [])) if u}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()}


def task_out(t: Task, names: dict[int, str], moment: datetime, comments: int = 0, files: int = 0) -> dict[str, Any]:
    overdue = bool(t.due_at and t.status != "done" and t.due_at < moment)
    return {
        "id": t.id, "title": t.title, "status": t.status, "priority": t.priority, "due_at": t.due_at, "overdue": overdue,
        "labels": t.labels or [], "position": t.position, "completed_at": t.completed_at, "created_at": t.created_at,
        "creator": {"id": t.creator_id, "name": names.get(t.creator_id or 0)} if t.creator_id else None,
        "assignee": {"id": t.assignee_id, "name": names.get(t.assignee_id or 0)} if t.assignee_id else None,
        "comments": comments, "files": files, "archived": t.archived_at is not None,
    }  # fmt: skip


def visible_clause(auth: AuthContext):
    if sees_all(auth):
        return None
    me = auth.user.id
    return or_(Task.creator_id == me, Task.assignee_id == me, Task.watchers.contains([me]))


# --- Tahlil -----------------------------------------------------------------------------


async def analytics(db: AsyncSession, start, end, clause) -> dict[str, Any]:
    """Tahlil: raqamlar xuddi shu so'rovlardan; `clause` ko'rinish chegarasi (o'zimniki yoki hammasi)."""
    moment = now()
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    base = [Task.archived_at.is_(None)] + ([clause] if clause is not None else [])
    created_in = and_(Task.created_at >= s_dt, Task.created_at < e_dt)
    done_in = and_(Task.completed_at >= s_dt, Task.completed_at < e_dt, Task.status == "done")

    created = await db.scalar(select(func.count()).where(*base, created_in)) or 0
    completed = await db.scalar(select(func.count()).where(*base, done_in)) or 0
    open_now = await db.scalar(select(func.count()).where(*base, Task.status != "done")) or 0
    overdue_now = await db.scalar(select(func.count()).where(*base, Task.status != "done", Task.due_at < moment)) or 0
    with_due = await db.scalar(select(func.count()).where(*base, done_in, Task.due_at.is_not(None))) or 0
    on_time = await db.scalar(select(func.count()).where(*base, done_in, Task.due_at.is_not(None), Task.completed_at <= Task.due_at)) or 0
    avg_seconds = await db.scalar(select(func.avg(func.extract("epoch", Task.completed_at - Task.created_at))).where(*base, done_in))

    by_status = dict((await db.execute(select(Task.status, func.count()).where(*base).group_by(Task.status))).all())
    by_priority = dict((await db.execute(select(Task.priority, func.count()).where(*base, Task.status != "done").group_by(Task.priority))).all())

    day = lambda col: func.date(func.timezone(literal_column("'Asia/Tashkent'"), col))  # noqa: E731
    created_by_day = dict((await db.execute(select(day(Task.created_at), func.count()).where(*base, created_in).group_by(day(Task.created_at)))).all())
    done_by_day = dict((await db.execute(select(day(Task.completed_at), func.count()).where(*base, done_in).group_by(day(Task.completed_at)))).all())
    trend = []
    d = start
    while d <= end:
        trend.append({"date": d, "created": created_by_day.get(d, 0), "completed": done_by_day.get(d, 0)})
        d += timedelta(days=1)

    rows = (
        await db.execute(
            select(
                Task.assignee_id,
                func.count().filter(created_in).label("assigned"),
                func.count().filter(done_in).label("done"),
                func.count().filter(Task.status != "done").label("open"),
                func.count().filter(Task.status != "done", Task.due_at < moment).label("overdue"),
                func.avg(func.extract("epoch", Task.completed_at - Task.created_at)).filter(done_in).label("avg_s"),
            )
            .where(*base, Task.assignee_id.is_not(None))
            .group_by(Task.assignee_id)
        )
    ).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_([r.assignee_id for r in rows])))).all()} if rows else {}
    by_assignee = sorted(
        ({"user": {"id": r.assignee_id, "name": names.get(r.assignee_id)}, "assigned": r.assigned, "done": r.done, "open": r.open,
          "overdue": r.overdue, "avg_hours": round(r.avg_s / 3600, 1) if r.avg_s else None} for r in rows),
        key=lambda x: (-x["overdue"], -x["open"]),
    )  # fmt: skip
    return {
        "start": start, "end": end,
        "kpis": {"created": created, "completed": completed, "open": open_now, "overdue": overdue_now,
                 "on_time_rate": round(on_time / with_due, 4) if with_due else None,
                 "avg_hours": round(avg_seconds / 3600, 1) if avg_seconds else None},
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "by_priority": {p: by_priority.get(p, 0) for p in PRIORITIES},
        "trend": trend, "by_assignee": by_assignee, "today": local_date(moment),
    }  # fmt: skip

