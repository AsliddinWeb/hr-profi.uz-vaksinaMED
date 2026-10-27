"""Ehtiyojlar: 4 bosqichli oqim (so'rash -> ijrochi -> bajarish -> tasdiq), muddat nazorati, tahlil."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import AuditLog, User
from app.models.needs import NeedCategory, NeedComment, NeedEvent, NeedFile, NeedRequest
from app.models.org import Branch
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, now, tz

PRIORITIES = ("low", "normal", "high", "urgent")
OPEN = ("requested", "assigned")
ACTIVE = ("requested", "assigned", "completed")
SOON_HOURS = 24

register_template("needs.new", {"uz": "Yangi ehtiyoj so'rovi", "ru": "Новая заявка на потребность"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "info")
register_template("needs.assigned", {"uz": "Sizga ehtiyoj biriktirildi", "ru": "Вам назначена потребность"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "info")
register_template("needs.assigned_requester", {"uz": "So'rovingizga ijrochi tayinlandi", "ru": "По вашей заявке назначен исполнитель"}, {"uz": "{number}: {assignee}", "ru": "{number}: {assignee}"}, "success")
register_template("needs.completed", {"uz": "Ehtiyoj bajarildi: tasdiqlang", "ru": "Потребность выполнена: подтвердите"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "success")
register_template("needs.confirmed", {"uz": "Ehtiyoj tasdiqlandi", "ru": "Потребность подтверждена"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "success")
register_template("needs.returned", {"uz": "Bajarilgan ish qaytarildi", "ru": "Выполнение возвращено"}, {"uz": "{number}: {note}", "ru": "{number}: {note}"}, "danger")
register_template("needs.cancelled", {"uz": "Ehtiyoj bekor qilindi", "ru": "Потребность отменена"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "warning")
register_template("needs.due_soon", {"uz": "Ehtiyoj muddati yaqin", "ru": "Срок потребности близок"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "warning")
register_template("needs.overdue", {"uz": "Ehtiyoj muddati o'tdi", "ru": "Потребность просрочена"}, {"uz": "{number}: {title}", "ru": "{number}: {title}"}, "danger")
register_template("needs.comment", {"uz": "Ehtiyojga yangi izoh", "ru": "Новый комментарий к потребности"}, {"uz": "{author}: {number}", "ru": "{author}: {number}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def dispatcher(auth: AuthContext) -> bool:
    return has(auth, "needs.dispatch") or has(auth, "needs.manage")


def can_view(auth: AuthContext, n: NeedRequest) -> bool:
    return n.requester_id == auth.user.id or n.assignee_id == auth.user.id or dispatcher(auth)


def is_requester(auth: AuthContext, n: NeedRequest) -> bool:
    return n.requester_id == auth.user.id


def can_edit(auth: AuthContext, n: NeedRequest) -> bool:
    if n.status == "requested":
        return is_requester(auth, n) or dispatcher(auth)
    return n.status == "assigned" and dispatcher(auth)


def can_assign(auth: AuthContext, n: NeedRequest) -> bool:
    return dispatcher(auth) and n.status in OPEN


def can_complete(auth: AuthContext, n: NeedRequest) -> bool:
    return n.status == "assigned" and n.assignee_id == auth.user.id and has(auth, "needs.work")


def can_confirm(auth: AuthContext, n: NeedRequest) -> bool:
    return n.status == "completed" and (is_requester(auth, n) or dispatcher(auth))


def can_cancel(auth: AuthContext, n: NeedRequest) -> bool:
    if n.status in OPEN:
        return is_requester(auth, n) or dispatcher(auth)
    return n.status == "completed" and dispatcher(auth)


def log(db: AsyncSession, n: NeedRequest, actor_id: int | None, action: str, note: str | None = None, data: dict | None = None) -> None:
    db.add(NeedEvent(need_id=n.id, actor_id=actor_id, action=action, note=note, data=data))


async def next_number(db: AsyncSession, year: int) -> str:
    seq = await db.scalar(text("SELECT nextval('need_no_seq')"))
    return f"E-{year}-{int(seq):04d}"


async def worker_ok(db: AsyncSession, user_id: int | None) -> bool:
    """Ijrochi bo'la oladimi: faol foydalanuvchi va `needs.work` huquqi bor."""
    if not user_id:
        return False
    return user_id in set(await users_with_permission(db, "needs.work"))


def params_of(n: NeedRequest, **extra: Any) -> dict[str, Any]:
    return {"number": n.number, "title": n.title, **extra}


async def create(db: AsyncSession, auth: AuthContext, *, title, description, category: NeedCategory | None, branch_id, priority, due_at, moment: datetime):
    n = NeedRequest(
        number=await next_number(db, local_date(moment).year), title=title.strip(), description=(description or "").strip() or None,
        category_id=category.id if category else None, branch_id=branch_id, priority=priority, status="requested", requester_id=auth.user.id,
        due_at=due_at or (moment + timedelta(days=category.sla_days) if category and category.sla_days else None), requested_at=moment,
    )  # fmt: skip
    db.add(n)
    await db.flush()
    log(db, n, auth.user.id, "requested")
    notes = []
    if category and await worker_ok(db, category.default_assignee_id):
        n.assignee_id, n.status, n.assigned_at = category.default_assignee_id, "assigned", moment
        log(db, n, None, "assigned", data={"assignee_id": n.assignee_id, "auto": True})
        notes += await notify(db, [n.assignee_id], "needs.assigned", link=f"/needs/{n.id}", params=params_of(n))
    else:
        targets = [u for u in await users_with_permission(db, "needs.dispatch") if u != auth.user.id]
        notes += await notify(db, targets, "needs.new", link=f"/needs/{n.id}", params=params_of(n))
    return n, notes


async def assign(db: AsyncSession, n: NeedRequest, auth: AuthContext, assignee_id: int, note: str | None, moment: datetime):
    if not can_assign(auth, n):
        raise error(409 if n.status not in OPEN else 403, "invalid_transition" if n.status not in OPEN else "forbidden")
    if not await worker_ok(db, assignee_id):
        raise error(400, "unknown_assignee")
    prev = n.assignee_id
    n.assignee_id, n.status, n.assigned_at = assignee_id, "assigned", moment
    n.notified_soon = n.notified_overdue = False
    log(db, n, auth.user.id, "assigned", (note or "").strip() or None, {"assignee_id": assignee_id, "previous": prev})
    assignee = await db.get(User, assignee_id)
    notes = await notify(db, [assignee_id], "needs.assigned", link=f"/needs/{n.id}", params=params_of(n))
    if n.requester_id and n.requester_id != auth.user.id:
        notes += await notify(db, [n.requester_id], "needs.assigned_requester", link=f"/needs/{n.id}", params=params_of(n, assignee=assignee.full_name if assignee else ""))
    return notes


async def complete(db: AsyncSession, n: NeedRequest, auth: AuthContext, report: str, moment: datetime):
    if not can_complete(auth, n):
        raise error(409 if n.status != "assigned" else 403, "invalid_transition" if n.status != "assigned" else "forbidden")
    text_ = report.strip()
    if len(text_) < 3:
        raise error(400, "report_required")
    n.status, n.report, n.completed_at = "completed", text_, moment
    log(db, n, auth.user.id, "completed", text_)
    return await notify(db, [n.requester_id] if n.requester_id and n.requester_id != auth.user.id else [], "needs.completed", link=f"/needs/{n.id}", params=params_of(n))


async def confirm(db: AsyncSession, n: NeedRequest, auth: AuthContext, rating: int | None, note: str | None, moment: datetime):
    if not can_confirm(auth, n):
        raise error(409 if n.status != "completed" else 403, "invalid_transition" if n.status != "completed" else "forbidden")
    n.status, n.confirmed_at, n.rating, n.confirm_note = "confirmed", moment, rating, (note or "").strip() or None
    log(db, n, auth.user.id, "confirmed", n.confirm_note, {"rating": rating})
    return await notify(db, [n.assignee_id] if n.assignee_id and n.assignee_id != auth.user.id else [], "needs.confirmed", link=f"/needs/{n.id}", params=params_of(n))


async def send_back(db: AsyncSession, n: NeedRequest, auth: AuthContext, note: str | None):
    if not can_confirm(auth, n):
        raise error(409 if n.status != "completed" else 403, "invalid_transition" if n.status != "completed" else "forbidden")
    text_ = (note or "").strip()
    if len(text_) < 3:
        raise error(400, "note_required")
    n.status, n.completed_at, n.return_count = "assigned", None, n.return_count + 1
    n.notified_soon = n.notified_overdue = False
    log(db, n, auth.user.id, "returned", text_)
    return await notify(db, [n.assignee_id] if n.assignee_id else [], "needs.returned", link=f"/needs/{n.id}", params=params_of(n, note=text_))


async def cancel(db: AsyncSession, n: NeedRequest, auth: AuthContext, note: str | None):
    if not can_cancel(auth, n):
        raise error(409 if n.status not in ACTIVE else 403, "invalid_transition" if n.status not in ACTIVE else "forbidden")
    text_ = (note or "").strip()
    if len(text_) < 3:
        raise error(400, "note_required")
    n.status = "cancelled"
    log(db, n, auth.user.id, "cancelled", text_)
    targets = {u for u in (n.requester_id, n.assignee_id) if u and u != auth.user.id}
    return await notify(db, list(targets), "needs.cancelled", link=f"/needs/{n.id}", params=params_of(n))


async def check_deadlines(db: AsyncSession, moment: datetime):
    """Yaqinlashgan/o'tgan muddatlar: ijrochiga (yoki tayinlanmagan bo'lsa dispetcherlarga) bir martadan; o'tganlar auditga ham yoziladi."""
    base = and_(NeedRequest.status.in_(OPEN), NeedRequest.due_at.is_not(None))
    notes: list = []
    dispatchers = await users_with_permission(db, "needs.dispatch")
    soon = (await db.scalars(select(NeedRequest).where(base, NeedRequest.due_at > moment, NeedRequest.due_at <= moment + timedelta(hours=SOON_HOURS), NeedRequest.notified_soon.is_(False)))).all()
    for n in soon:
        n.notified_soon = True
        notes += await notify(db, [n.assignee_id] if n.assignee_id else dispatchers, "needs.due_soon", link=f"/needs/{n.id}", params=params_of(n))
    late = (await db.scalars(select(NeedRequest).where(base, NeedRequest.due_at <= moment, NeedRequest.notified_overdue.is_(False)))).all()
    for n in late:
        n.notified_overdue = True
        log(db, n, None, "overdue")
        db.add(AuditLog(action="needs.overdue", entity="need", entity_id=str(n.id), data={"number": n.number, "due_at": n.due_at.isoformat() if n.due_at else None}))
        targets = {u for u in [n.assignee_id, *dispatchers] if u}
        notes += await notify(db, list(targets), "needs.overdue", link=f"/needs/{n.id}", params=params_of(n))
    return len(soon), len(late), notes


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


def need_out(n: NeedRequest, user_names: dict[int, str], cats: dict[int, str], branches: dict[int, str], moment: datetime, comments: int = 0, files: int = 0) -> dict[str, Any]:
    overdue = bool(n.due_at and n.status in OPEN and n.due_at < moment)
    return {
        "id": n.id, "number": n.number, "title": n.title, "status": n.status, "priority": n.priority, "due_at": n.due_at, "overdue": overdue,
        "category": {"id": n.category_id, "name": cats.get(n.category_id or 0)} if n.category_id else None,
        "branch": {"id": n.branch_id, "name": branches.get(n.branch_id or 0)} if n.branch_id else None,
        "requester": {"id": n.requester_id, "name": user_names.get(n.requester_id or 0)} if n.requester_id else None,
        "assignee": {"id": n.assignee_id, "name": user_names.get(n.assignee_id or 0)} if n.assignee_id else None,
        "requested_at": n.requested_at, "assigned_at": n.assigned_at, "completed_at": n.completed_at, "confirmed_at": n.confirmed_at,
        "return_count": n.return_count, "rating": n.rating, "comments": comments, "files": files,
    }  # fmt: skip


async def analytics(db: AsyncSession, start: date, end: date, clause) -> dict[str, Any]:
    moment = now()
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    base = [clause] if clause is not None else []
    N = NeedRequest
    created_in = and_(N.requested_at >= s_dt, N.requested_at < e_dt)
    done_in = and_(N.completed_at >= s_dt, N.completed_at < e_dt, N.status.in_(("completed", "confirmed")))
    count = lambda *c: select(func.count()).select_from(N).where(*base, *c)  # noqa: E731
    created = await db.scalar(count(created_in)) or 0
    completed = await db.scalar(count(done_in)) or 0
    confirmed = await db.scalar(count(N.status == "confirmed", N.confirmed_at >= s_dt, N.confirmed_at < e_dt)) or 0
    open_now = await db.scalar(count(N.status.in_(ACTIVE))) or 0
    overdue = await db.scalar(count(N.status.in_(OPEN), N.due_at < moment)) or 0
    unassigned = await db.scalar(count(N.status == "requested")) or 0
    with_due = await db.scalar(count(done_in, N.due_at.is_not(None))) or 0
    on_time = await db.scalar(count(done_in, N.due_at.is_not(None), N.completed_at <= N.due_at)) or 0
    returned = await db.scalar(count(done_in, N.return_count > 0)) or 0
    avg_s = await db.scalar(select(func.avg(func.extract("epoch", N.completed_at - N.requested_at))).where(*base, done_in))
    avg_rating = await db.scalar(select(func.avg(N.rating)).where(*base, N.rating.is_not(None), N.confirmed_at >= s_dt, N.confirmed_at < e_dt))
    by_status = dict((await db.execute(select(N.status, func.count()).where(*base).group_by(N.status))).all())

    day = lambda col: func.date(func.timezone(literal_column("'Asia/Tashkent'"), col))  # noqa: E731
    cdays = dict((await db.execute(select(day(N.requested_at), func.count()).where(*base, created_in).group_by(day(N.requested_at)))).all())
    ddays = dict((await db.execute(select(day(N.completed_at), func.count()).where(*base, done_in).group_by(day(N.completed_at)))).all())
    trend, d = [], start
    while d <= end:
        trend.append({"date": d, "created": cdays.get(d, 0), "completed": ddays.get(d, 0)})
        d += timedelta(days=1)

    def group(col):
        return (
            select(
                col, func.count().filter(created_in).label("created"), func.count().filter(done_in).label("done"),
                func.count().filter(N.status.in_(ACTIVE)).label("open"), func.count().filter(N.status.in_(OPEN), N.due_at < moment).label("overdue"),
                func.avg(func.extract("epoch", N.completed_at - N.requested_at)).filter(done_in).label("avg_s"),
                func.avg(N.rating).label("rating"),
            ).where(*base).group_by(col)
        )  # fmt: skip

    def row(r, label):
        return {"name": label, "created": r.created, "done": r.done, "open": r.open, "overdue": r.overdue,
                "avg_hours": round(r.avg_s / 3600, 1) if r.avg_s else None, "rating": round(float(r.rating), 2) if r.rating else None}  # fmt: skip

    cat_rows = (await db.execute(group(N.category_id))).all()
    exe_rows = (await db.execute(group(N.assignee_id).where(N.assignee_id.is_not(None)))).all()
    br_rows = (await db.execute(group(N.branch_id))).all()
    cats = {c.id: c.name for c in (await db.scalars(select(NeedCategory))).all()}
    users = await names(db, {r[0] for r in exe_rows})
    brs = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    return {
        "start": start, "end": end,
        "kpis": {"created": created, "completed": completed, "confirmed": confirmed, "open": open_now, "overdue": overdue, "unassigned": unassigned,
                 "on_time_rate": round(on_time / with_due, 4) if with_due else None, "return_rate": round(returned / completed, 4) if completed else None,
                 "avg_hours": round(avg_s / 3600, 1) if avg_s else None, "avg_rating": round(float(avg_rating), 2) if avg_rating else None},
        "by_status": {s: by_status.get(s, 0) for s in ("requested", "assigned", "completed", "confirmed", "cancelled")},
        "trend": trend,
        "by_category": sorted([row(r, cats.get(r[0] or 0)) for r in cat_rows], key=lambda x: -x["created"]),
        "by_executor": sorted([row(r, users.get(r[0])) for r in exe_rows], key=lambda x: (-x["overdue"], -x["open"])),
        "by_branch": sorted([row(r, brs.get(r[0] or 0)) for r in br_rows], key=lambda x: -x["created"])[:30],
    }  # fmt: skip


__all__ = ["NeedComment", "NeedFile"]
