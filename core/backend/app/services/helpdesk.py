"""AyTi ticketlar: new -> in_progress <-> waiting -> resolved -> closed (reopen mumkin), SLA nazorati, tahlil."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import AuditLog, User
from app.models.helpdesk import Ticket, TicketCategory, TicketEvent
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, now, tz

PRIORITIES = ("low", "normal", "high", "urgent")
SLA_HOURS = {"urgent": 4, "high": 8, "normal": 24, "low": 72}
OPEN = ("new", "in_progress", "waiting")
ACTIVE = (*OPEN, "resolved")
AUTO_CLOSE_HOURS = 72

for _k, _uz, _ru, _lvl in (
    ("new", "Yangi AyTi ticket", "Новая заявка в ИТ", "info"),
    ("assigned", "Sizga ticket biriktirildi", "Вам назначена заявка", "info"),
    ("taken", "Ticketingiz ishga olindi", "Ваша заявка взята в работу", "info"),
    ("resolved", "Ticket hal qilindi: tasdiqlang", "Заявка решена: подтвердите", "success"),
    ("reopened", "Ticket qayta ochildi", "Заявка открыта повторно", "warning"),
    ("waiting", "Ticket sizdan javob kutmoqda", "Заявка ждёт вашего ответа", "warning"),
    ("comment", "Ticketga yangi izoh", "Новый комментарий к заявке", "info"),
    ("sla", "Ticket SLA muddati o'tdi", "Просрочен SLA заявки", "danger"),
):
    register_template(f"helpdesk.{_k}", {"uz": _uz, "ru": _ru}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, _lvl)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def staff(auth: AuthContext) -> bool:
    return has(auth, "helpdesk.work") or has(auth, "helpdesk.manage") or has(auth, "helpdesk.read")


def manager(auth: AuthContext) -> bool:
    return has(auth, "helpdesk.manage")


def is_requester(auth: AuthContext, t: Ticket) -> bool:
    return t.requester_id == auth.user.id


def can_view(auth: AuthContext, t: Ticket) -> bool:
    return is_requester(auth, t) or staff(auth)


def can_work(auth: AuthContext, t: Ticket) -> bool:
    """Ijrochi yoki menejer ticketni yuritishi mumkin."""
    return t.status in OPEN and (manager(auth) or (has(auth, "helpdesk.work") and t.assignee_id in (None, auth.user.id)))


def can_take(auth: AuthContext, t: Ticket) -> bool:
    return t.status == "new" and t.assignee_id is None and has(auth, "helpdesk.work")


def can_assign(auth: AuthContext, t: Ticket) -> bool:
    return manager(auth) and t.status in OPEN


def can_resolve(auth: AuthContext, t: Ticket) -> bool:
    return can_work(auth, t)


def can_close(auth: AuthContext, t: Ticket) -> bool:
    return t.status == "resolved" and (is_requester(auth, t) or manager(auth))


def can_reopen(auth: AuthContext, t: Ticket) -> bool:
    return t.status in ("resolved", "closed") and (is_requester(auth, t) or manager(auth))


def can_cancel(auth: AuthContext, t: Ticket) -> bool:
    return t.status in OPEN and (is_requester(auth, t) or manager(auth))


def can_edit(auth: AuthContext, t: Ticket) -> bool:
    return t.status == "new" and (is_requester(auth, t) or manager(auth))


def log(db: AsyncSession, t: Ticket, actor_id: int | None, action: str, note: str | None = None, *, from_status: str | None = None, to_status: str | None = None, data: dict | None = None) -> None:
    db.add(TicketEvent(ticket_id=t.id, actor_id=actor_id, action=action, note=note, from_status=from_status, to_status=to_status, data=data))


def params_of(t: Ticket, **extra: Any) -> dict[str, Any]:
    return {"number": t.number, "title": t.title, **extra}


async def next_number(db: AsyncSession, year: int) -> str:
    seq = await db.scalar(text("SELECT nextval('ticket_no_seq')"))
    return f"T-{year}-{int(seq):04d}"


async def helpers(db: AsyncSession, user_id: int | None) -> bool:
    return bool(user_id) and user_id in set(await users_with_permission(db, "helpdesk.work"))


def set_status(db: AsyncSession, t: Ticket, actor_id: int | None, to: str, note: str | None = None, data: dict | None = None) -> None:
    prev = t.status
    t.status = to
    log(db, t, actor_id, "status", note, from_status=prev, to_status=to, data=data)


async def create(db: AsyncSession, auth: AuthContext, *, title, description, category: TicketCategory | None, branch_id, priority, device_info, moment: datetime):
    t = Ticket(
        number=await next_number(db, local_date(moment).year), title=title.strip(), description=(description or "").strip() or None,
        category_id=category.id if category else None, branch_id=branch_id, priority=priority, status="new", requester_id=auth.user.id,
        device_info=(device_info or "").strip() or None, opened_at=moment, due_at=moment + timedelta(hours=SLA_HOURS[priority]),
    )  # fmt: skip
    db.add(t)
    await db.flush()
    log(db, t, auth.user.id, "created")
    notes: list = []
    if category and category.default_assignee_id and await helpers(db, category.default_assignee_id):
        t.assignee_id = category.default_assignee_id
        log(db, t, None, "assigned", data={"assignee_id": t.assignee_id, "auto": True})
        notes += await notify(db, [t.assignee_id], "helpdesk.assigned", link=f"/helpdesk/{t.id}", params=params_of(t))
    else:
        targets = [u for u in await users_with_permission(db, "helpdesk.work") if u != auth.user.id]
        notes += await notify(db, targets, "helpdesk.new", link=f"/helpdesk/{t.id}", params=params_of(t))
    return t, notes


def _touch_response(t: Ticket, moment: datetime) -> None:
    if t.first_response_at is None:
        t.first_response_at = moment


async def take(db: AsyncSession, t: Ticket, auth: AuthContext, moment: datetime):
    if not can_take(auth, t):
        raise error(409 if t.status != "new" or t.assignee_id else 403, "invalid_transition" if t.status != "new" or t.assignee_id else "forbidden")
    t.assignee_id = auth.user.id
    log(db, t, auth.user.id, "assigned", data={"assignee_id": auth.user.id, "self": True})
    set_status(db, t, auth.user.id, "in_progress")
    _touch_response(t, moment)
    return await notify(db, [t.requester_id] if t.requester_id and t.requester_id != auth.user.id else [], "helpdesk.taken", link=f"/helpdesk/{t.id}", params=params_of(t))


async def assign(db: AsyncSession, t: Ticket, auth: AuthContext, assignee_id: int, note: str | None, moment: datetime):
    if not can_assign(auth, t):
        raise error(409 if t.status not in OPEN else 403, "invalid_transition" if t.status not in OPEN else "forbidden")
    if not await helpers(db, assignee_id):
        raise error(400, "unknown_assignee")
    prev = t.assignee_id
    t.assignee_id = assignee_id
    log(db, t, auth.user.id, "assigned", (note or "").strip() or None, data={"assignee_id": assignee_id, "previous": prev})
    if t.status == "new":
        set_status(db, t, auth.user.id, "in_progress")
    return await notify(db, [assignee_id] if assignee_id != auth.user.id else [], "helpdesk.assigned", link=f"/helpdesk/{t.id}", params=params_of(t))


async def set_waiting(db: AsyncSession, t: Ticket, auth: AuthContext, note: str, moment: datetime):
    """Ijrochi: foydalanuvchidan ma'lumot kutilmoqda (waiting) yoki qayta ishga olindi (in_progress)."""
    if not can_work(auth, t):
        raise error(409 if t.status not in OPEN else 403, "invalid_transition" if t.status not in OPEN else "forbidden")
    text_ = note.strip()
    if len(text_) < 3:
        raise error(400, "note_required")
    if t.assignee_id is None:
        t.assignee_id = auth.user.id
    set_status(db, t, auth.user.id, "waiting", text_)
    _touch_response(t, moment)
    return await notify(db, [t.requester_id] if t.requester_id and t.requester_id != auth.user.id else [], "helpdesk.waiting", link=f"/helpdesk/{t.id}", params=params_of(t))


async def resume(db: AsyncSession, t: Ticket, auth: AuthContext, moment: datetime):
    if t.status not in ("new", "waiting") or not can_work(auth, t):
        raise error(409 if t.status not in ("new", "waiting") else 403, "invalid_transition" if t.status not in ("new", "waiting") else "forbidden")
    if t.assignee_id is None:
        t.assignee_id = auth.user.id
    set_status(db, t, auth.user.id, "in_progress")
    _touch_response(t, moment)
    return []


async def resolve(db: AsyncSession, t: Ticket, auth: AuthContext, resolution: str, moment: datetime):
    if not can_resolve(auth, t):
        raise error(409 if t.status not in OPEN else 403, "invalid_transition" if t.status not in OPEN else "forbidden")
    text_ = resolution.strip()
    if len(text_) < 3:
        raise error(400, "resolution_required")
    if t.assignee_id is None:
        t.assignee_id = auth.user.id
    t.resolution, t.resolved_at = text_, moment
    _touch_response(t, moment)
    t.sla_breached = bool(t.due_at and moment > t.due_at) or t.sla_breached
    set_status(db, t, auth.user.id, "resolved", text_)
    return await notify(db, [t.requester_id] if t.requester_id and t.requester_id != auth.user.id else [], "helpdesk.resolved", link=f"/helpdesk/{t.id}", params=params_of(t))


async def close(db: AsyncSession, t: Ticket, auth: AuthContext, rating: int | None, comment: str | None, moment: datetime):
    if not can_close(auth, t):
        raise error(409 if t.status != "resolved" else 403, "invalid_transition" if t.status != "resolved" else "forbidden")
    t.closed_at, t.rating, t.rating_comment = moment, rating, (comment or "").strip() or None
    set_status(db, t, auth.user.id, "closed", t.rating_comment, {"rating": rating})
    return []


async def reopen(db: AsyncSession, t: Ticket, auth: AuthContext, note: str, moment: datetime):
    if not can_reopen(auth, t):
        raise error(409 if t.status not in ("resolved", "closed") else 403, "invalid_transition" if t.status not in ("resolved", "closed") else "forbidden")
    text_ = note.strip()
    if len(text_) < 3:
        raise error(400, "note_required")
    t.resolved_at = t.closed_at = None
    t.reopen_count += 1
    t.rating = t.rating_comment = None
    set_status(db, t, auth.user.id, "in_progress" if t.assignee_id else "new", text_)
    return await notify(db, [t.assignee_id] if t.assignee_id and t.assignee_id != auth.user.id else await users_with_permission(db, "helpdesk.work"), "helpdesk.reopened", link=f"/helpdesk/{t.id}", params=params_of(t))


async def cancel(db: AsyncSession, t: Ticket, auth: AuthContext, note: str):
    if not can_cancel(auth, t):
        raise error(409 if t.status not in OPEN else 403, "invalid_transition" if t.status not in OPEN else "forbidden")
    text_ = note.strip()
    if len(text_) < 3:
        raise error(400, "note_required")
    set_status(db, t, auth.user.id, "cancelled", text_)
    return []


async def watch(db: AsyncSession, moment: datetime):
    """SLA muddati o'tgan ochiq ticketlarni belgilaydi (bir martadan xabar + audit), 72 soatdan beri tasdiqlanmagan hal qilinganlarni yopadi."""
    notes: list = []
    managers = await users_with_permission(db, "helpdesk.manage")
    late = (await db.scalars(select(Ticket).where(Ticket.status.in_(OPEN), Ticket.due_at <= moment, Ticket.sla_breached.is_(False)))).all()
    for t in late:
        t.sla_breached = True
        log(db, t, None, "sla")
        db.add(AuditLog(action="helpdesk.sla_breached", entity="ticket", entity_id=str(t.id), data={"number": t.number, "priority": t.priority}))
        notes += await notify(db, list({u for u in [t.assignee_id, *managers] if u}), "helpdesk.sla", link=f"/helpdesk/{t.id}", params=params_of(t))
    stale = (await db.scalars(select(Ticket).where(Ticket.status == "resolved", Ticket.resolved_at <= moment - timedelta(hours=AUTO_CLOSE_HOURS)))).all()
    for t in stale:
        t.closed_at = moment
        set_status(db, t, None, "closed", None, {"auto": True})
    return len(late), len(stale), notes


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


def ticket_out(t: Ticket, user_names: dict[int, str], cats: dict[int, str], branches: dict[int, str], moment: datetime, comments: int = 0, files: int = 0) -> dict[str, Any]:
    overdue = bool(t.due_at and t.status in OPEN and t.due_at < moment)
    return {
        "id": t.id, "number": t.number, "title": t.title, "status": t.status, "priority": t.priority, "due_at": t.due_at, "overdue": overdue,
        "sla_breached": t.sla_breached or overdue,
        "category": {"id": t.category_id, "name": cats.get(t.category_id or 0)} if t.category_id else None,
        "branch": {"id": t.branch_id, "name": branches.get(t.branch_id or 0)} if t.branch_id else None,
        "requester": {"id": t.requester_id, "name": user_names.get(t.requester_id or 0)} if t.requester_id else None,
        "assignee": {"id": t.assignee_id, "name": user_names.get(t.assignee_id or 0)} if t.assignee_id else None,
        "opened_at": t.opened_at, "first_response_at": t.first_response_at, "resolved_at": t.resolved_at, "closed_at": t.closed_at,
        "rating": t.rating, "reopen_count": t.reopen_count, "device_info": t.device_info, "comments": comments, "files": files,
    }  # fmt: skip


async def analytics(db: AsyncSession, start: date, end: date) -> dict[str, Any]:
    moment = now()
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    T = Ticket
    created_in = and_(T.opened_at >= s_dt, T.opened_at < e_dt)
    done_in = and_(T.resolved_at >= s_dt, T.resolved_at < e_dt)
    count = lambda *c: select(func.count()).select_from(T).where(*c)  # noqa: E731
    created = await db.scalar(count(created_in)) or 0
    resolved = await db.scalar(count(done_in)) or 0
    open_now = await db.scalar(count(T.status.in_(OPEN))) or 0
    unassigned = await db.scalar(count(T.status == "new", T.assignee_id.is_(None))) or 0
    overdue = await db.scalar(count(T.status.in_(OPEN), T.due_at < moment)) or 0
    on_time = await db.scalar(count(done_in, T.resolved_at <= T.due_at)) or 0
    reopened = await db.scalar(count(created_in, T.reopen_count > 0)) or 0
    avg_res = await db.scalar(select(func.avg(func.extract("epoch", T.resolved_at - T.opened_at))).where(done_in))
    avg_resp = await db.scalar(select(func.avg(func.extract("epoch", T.first_response_at - T.opened_at))).where(created_in, T.first_response_at.is_not(None)))
    avg_rating = await db.scalar(select(func.avg(T.rating)).where(T.rating.is_not(None), T.closed_at >= s_dt, T.closed_at < e_dt))
    by_status = dict((await db.execute(select(T.status, func.count()).group_by(T.status))).all())
    by_priority = dict((await db.execute(select(T.priority, func.count()).where(created_in).group_by(T.priority))).all())

    def group(col):
        return select(
            col, func.count().filter(created_in).label("created"), func.count().filter(done_in).label("done"),
            func.count().filter(T.status.in_(OPEN)).label("open"), func.count().filter(T.status.in_(OPEN), T.due_at < moment).label("overdue"),
            func.avg(func.extract("epoch", T.resolved_at - T.opened_at)).filter(done_in).label("avg_s"), func.avg(T.rating).label("rating"),
        ).group_by(col)  # fmt: skip

    def row(r, label):
        return {"name": label, "created": r.created, "done": r.done, "open": r.open, "overdue": r.overdue,
                "avg_hours": round(r.avg_s / 3600, 1) if r.avg_s else None, "rating": round(float(r.rating), 2) if r.rating else None}  # fmt: skip

    cat_rows = (await db.execute(group(T.category_id))).all()
    exe_rows = (await db.execute(group(T.assignee_id).where(T.assignee_id.is_not(None)))).all()
    cats = {c.id: c.name for c in (await db.scalars(select(TicketCategory))).all()}
    users = await names(db, {r[0] for r in exe_rows})
    return {
        "start": start, "end": end,
        "kpis": {"created": created, "resolved": resolved, "open": open_now, "overdue": overdue, "unassigned": unassigned,
                 "sla_rate": round(on_time / resolved, 4) if resolved else None, "reopen_rate": round(reopened / created, 4) if created else None,
                 "avg_resolution_hours": round(avg_res / 3600, 1) if avg_res else None, "avg_response_minutes": round(avg_resp / 60, 1) if avg_resp else None,
                 "avg_rating": round(float(avg_rating), 2) if avg_rating else None},
        "by_status": {s: by_status.get(s, 0) for s in ("new", "in_progress", "waiting", "resolved", "closed", "cancelled")},
        "by_priority": {p: by_priority.get(p, 0) for p in PRIORITIES},
        "by_category": sorted([row(r, cats.get(r[0] or 0)) for r in cat_rows], key=lambda x: -x["created"]),
        "by_executor": sorted([row(r, users.get(r[0])) for r in exe_rows], key=lambda x: (-x["overdue"], -x["open"])),
    }  # fmt: skip
