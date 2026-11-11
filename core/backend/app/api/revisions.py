"""Reviziya bo'limi: filial sikli (oxirgi reviziyadan keyingi muddat), revizor vazifalari va kalendar.
Jarayon: boshliq biriktiradi -> revizor qabul qiladi -> boshlaydi -> natija (kamomad, ball, izoh) topshiradi -> boshliq tasdiqlaydi yoki qaytaradi."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require_any
from app.models.auth import User
from app.models.branch_ops import RevisionTask
from app.models.org import Branch
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.company import get_setting
from app.services.notifications import deliver, notify, register_template
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/revisions", tags=["revisions"])

CYCLE_DAYS = 90  # filial har 90 kunda bir marta to'liq reviziyadan o'tadi
SOON_DAYS = 14
OPEN = ("assigned", "accepted", "in_progress", "review")
KINDS = ("cycle", "shortage", "inventory", "check")

register_template("revision.assigned", {"uz": "Reviziya biriktirildi", "ru": "Назначена ревизия"},
                  {"uz": "{branch} · {date}", "ru": "{branch} · {date}"})  # fmt: skip
register_template("revision.submitted", {"uz": "Reviziya natijasi topshirildi", "ru": "Сдан результат ревизии"},
                  {"uz": "{branch}: tekshirib tasdiqlang", "ru": "{branch}: проверьте и подтвердите"})  # fmt: skip
register_template("revision.decided", {"uz": "Reviziya natijasi ko'rib chiqildi", "ru": "Результат ревизии рассмотрен"},
                  {"uz": "{branch}: {decision}", "ru": "{branch}: {decision}"})  # fmt: skip

can_read = require_any("revision.read", "revision.manage", "revision.own")


def _manager(auth: AuthContext) -> bool:
    return matches(auth.permissions, "revision.manage") or matches(auth.permissions, "revision.read")


def _bname(b: Branch | None) -> str:
    if not b:
        return "—"
    return f"№{b.number} {b.name}" if b.number else b.name


async def _users(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()}


def _out(t: RevisionTask, branch: Branch | None, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": t.id, "branch": {"id": t.branch_id, "name": _bname(branch)}, "kind": t.kind, "status": t.status,
        "planned_date": t.planned_date, "note": t.note, "result_note": t.result_note,
        "shortage_amount": float(t.shortage_amount) if t.shortage_amount is not None else None, "score": t.score,
        "revizor": {"id": t.revizor_user_id, "name": names.get(t.revizor_user_id or 0)} if t.revizor_user_id else None,
        "assigned_by": names.get(t.assigned_by or 0), "decision_note": t.decision_note,
        "accepted_at": t.accepted_at, "started_at": t.started_at, "submitted_at": t.submitted_at, "decided_at": t.decided_at,
        "created_at": t.created_at,
    }  # fmt: skip


async def _scope(db: AsyncSession, auth: AuthContext):
    stmt = select(RevisionTask)
    if not _manager(auth):
        stmt = stmt.where(RevisionTask.revizor_user_id == auth.user.id)
    return stmt


@router.get("/branches")
async def branches(q: str | None = None, status: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    """Filiallar sikli: oxirgi tasdiqlangan reviziya, keyingi muddat va holat (overdue/soon/in_progress/on_plan/never)."""
    today = local_date(now())
    cycle_days, soon_days = await get_setting(db, "revisions.cycle_days"), await get_setting(db, "revisions.soon_days")
    bstmt = select(Branch).where(Branch.is_active.is_(True))
    if q:
        bstmt = bstmt.where(Branch.name.ilike(f"%{q.strip()}%"))
    blist = (await db.scalars(bstmt.order_by(Branch.number.nulls_last(), Branch.name))).all()
    last_done = dict((await db.execute(select(RevisionTask.branch_id, func.max(RevisionTask.planned_date)).where(RevisionTask.status == "done").group_by(RevisionTask.branch_id))).all())
    open_rows = (await db.scalars(select(RevisionTask).where(RevisionTask.status.in_(OPEN)).order_by(RevisionTask.planned_date))).all()
    if not _manager(auth):
        mine = {t.branch_id for t in open_rows if t.revizor_user_id == auth.user.id} | {
            b for (b,) in (await db.execute(select(RevisionTask.branch_id).where(RevisionTask.revizor_user_id == auth.user.id))).all()}
        blist = [b for b in blist if b.id in mine]
    open_by: dict[int, RevisionTask] = {}
    for t in open_rows:
        open_by.setdefault(t.branch_id, t)
    names = await _users(db, {t.revizor_user_id for t in open_by.values()} | {b.manager_user_id for b in blist} | {b.coordinator_user_id for b in blist})
    items, counts = [], dict.fromkeys(("overdue", "cycle_done", "soon", "in_progress", "on_plan", "never"), 0)
    for b in blist:
        last = last_done.get(b.id)
        due = last + timedelta(days=cycle_days) if last else None
        t = open_by.get(b.id)
        if t:
            st = "in_progress"
        elif last is None:
            st = "never"
        elif due < today:
            st = "overdue"
        elif (due - today).days < soon_days:
            st = "soon"
        else:
            st = "on_plan"
        counts[st] += 1
        if last:
            counts["cycle_done"] += 1
        if status and status != st:
            continue
        items.append({"id": b.id, "name": _bname(b), "manager": names.get(b.manager_user_id or 0), "coordinator": names.get(b.coordinator_user_id or 0),
                      "last_done": last, "next_due": due, "days_left": (due - today).days if due else None, "status": st,
                      "open_task": {"id": t.id, "status": t.status, "planned_date": t.planned_date, "revizor": names.get(t.revizor_user_id or 0)} if t else None})  # fmt: skip
    return {"cycle_days": cycle_days, "counts": counts, "items": items}


@router.get("/branches/{bid}/history")
async def branch_history(bid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    b = await db.get(Branch, bid)
    if not b:
        raise error(404, "not_found")
    rows = (await db.scalars((await _scope(db, auth)).where(RevisionTask.branch_id == bid).order_by(RevisionTask.planned_date.desc()).limit(50))).all()
    names = await _users(db, {t.revizor_user_id for t in rows} | {t.assigned_by for t in rows})
    return {"branch": {"id": b.id, "name": _bname(b)}, "items": [_out(t, b, names) for t in rows]}


@router.get("/tasks")
async def tasks(status: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    """Vazifalar: tekshiruvda, kechikkan, bugun, kelajakda. Revizor faqat o'zinikini ko'radi."""
    today = local_date(now())
    stmt = (await _scope(db, auth)).where(RevisionTask.status.in_(OPEN))
    if status:
        stmt = stmt.where(RevisionTask.status == status)
    rows = (await db.scalars(stmt.order_by(RevisionTask.planned_date))).all()
    branches_ = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_({t.branch_id for t in rows} or {0})))).all()}
    names = await _users(db, {t.revizor_user_id for t in rows} | {t.assigned_by for t in rows})
    groups: dict[str, list] = {"review": [], "overdue": [], "today": [], "future": []}
    for t in rows:
        key = "review" if t.status == "review" else "overdue" if t.planned_date < today else "today" if t.planned_date == today else "future"
        groups[key].append(_out(t, branches_.get(t.branch_id), names))
    return {"counts": {k: len(v) for k, v in groups.items()}, **groups}


@router.get("/calendar")
async def calendar(month: str = Query(pattern=r"^\d{4}-\d{2}$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    y, m = map(int, month.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    rows = (await db.scalars((await _scope(db, auth)).where(RevisionTask.planned_date >= start, RevisionTask.planned_date < end).order_by(RevisionTask.planned_date))).all()
    branches_ = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_({t.branch_id for t in rows} or {0})))).all()}
    names = await _users(db, {t.revizor_user_id for t in rows})
    return {"month": month, "items": [_out(t, branches_.get(t.branch_id), names) for t in rows]}


@router.get("/revizors")
async def revizors(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("revision.manage"))):
    ids = set(await users_with_permission(db, "revision.own")) | set(await users_with_permission(db, "revision.manage"))
    users = (await db.scalars(select(User).where(User.id.in_(ids or {0}), User.is_active.is_(True)).order_by(User.full_name))).all()
    return [{"id": u.id, "name": u.full_name} for u in users]


class TaskIn(BaseModel):
    branch_id: int
    revizor_user_id: int
    planned_date: date
    kind: str = Field(default="cycle", pattern="^(cycle|shortage|inventory|check)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("revision.manage"))):
    b = await db.get(Branch, body.branch_id)
    if not b or not await db.get(User, body.revizor_user_id):
        raise error(404, "not_found")
    if await db.scalar(select(RevisionTask.id).where(RevisionTask.branch_id == b.id, RevisionTask.status.in_(OPEN))):
        raise error(409, "revision_open")
    t = RevisionTask(branch_id=b.id, revizor_user_id=body.revizor_user_id, planned_date=body.planned_date, kind=body.kind, note=body.note, assigned_by=auth.user.id)
    db.add(t)
    await db.flush()
    rows = await notify(db, [body.revizor_user_id], "revision.assigned", params={"branch": _bname(b), "date": body.planned_date.strftime("%d.%m.%Y")}, link="/revisions?tab=tasks")
    await db.commit()
    await deliver(request.app, rows)
    return _out(t, b, await _users(db, {t.revizor_user_id, t.assigned_by}))


class ResultIn(BaseModel):
    result_note: str | None = Field(default=None, max_length=4000)
    shortage_amount: Decimal | None = Field(default=None, ge=0)
    score: int | None = Field(default=None, ge=0, le=100)


class DecideIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


async def _load(db: AsyncSession, tid: int) -> tuple[RevisionTask, Branch | None]:
    t = await db.get(RevisionTask, tid)
    if not t:
        raise error(404, "not_found")
    return t, await db.get(Branch, t.branch_id)


def _need(t: RevisionTask, *allowed: str) -> None:
    if t.status not in allowed:
        raise error(409, "bad_status", status=t.status)


def _own(t: RevisionTask, auth: AuthContext) -> None:
    if t.revizor_user_id != auth.user.id and not matches(auth.permissions, "revision.manage"):
        raise error(403, "forbidden")


@router.post("/tasks/{tid}/{action}")
async def act(tid: int, action: str, request: Request, body: dict[str, Any] | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    """Amallar: accept, start, submit (natija), approve, return (qayta ishlashga), cancel."""
    t, b = await _load(db, tid)
    moment = now()
    rows: list = []
    if action == "accept":
        _own(t, auth)
        _need(t, "assigned")
        t.status, t.accepted_at = "accepted", moment
    elif action == "start":
        _own(t, auth)
        _need(t, "assigned", "accepted")
        t.status, t.started_at = "in_progress", moment
        t.accepted_at = t.accepted_at or moment
    elif action == "submit":
        _own(t, auth)
        _need(t, "accepted", "in_progress")
        data = ResultIn(**(body or {}))
        t.result_note, t.shortage_amount, t.score = data.result_note, data.shortage_amount, data.score
        t.status, t.submitted_at = "review", moment
        t.started_at = t.started_at or moment
        managers = set(await users_with_permission(db, "revision.manage")) | ({t.assigned_by} if t.assigned_by else set())
        rows = await notify(db, managers - {auth.user.id} or managers, "revision.submitted", params={"branch": _bname(b)}, link="/revisions?tab=tasks")
    elif action in ("approve", "return", "cancel"):
        if not matches(auth.permissions, "revision.manage"):
            raise error(403, "forbidden")
        note = DecideIn(**(body or {})).note
        if action == "approve":
            _need(t, "review")
            t.status = "done"
        elif action == "return":
            _need(t, "review")
            t.status = "in_progress"
        else:
            _need(t, *OPEN)
            t.status = "cancelled"
        t.decided_at, t.decided_by, t.decision_note = moment, auth.user.id, note
        if t.revizor_user_id and action != "cancel":
            label = {"approve": "tasdiqlandi", "return": "qayta ishlashga qaytarildi"}[action]
            rows = await notify(db, [t.revizor_user_id], "revision.decided", params={"branch": _bname(b), "decision": label}, link="/revisions?tab=tasks")
    else:
        raise error(404, "not_found")
    await db.commit()
    if rows:
        await deliver(request.app, rows)
    return _out(t, b, await _users(db, {t.revizor_user_id, t.assigned_by}))


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_read)):
    today = local_date(now())
    stmt = await _scope(db, auth)
    total_shortage = await db.scalar(select(func.coalesce(func.sum(RevisionTask.shortage_amount), 0)).where(RevisionTask.status == "done", RevisionTask.decided_at >= now() - timedelta(days=30)))
    overdue = await db.scalar(select(func.count()).select_from(stmt.where(RevisionTask.status.in_(OPEN), RevisionTask.planned_date < today, RevisionTask.status != "review").subquery()))
    return {"shortage_30d": float(total_shortage or 0), "overdue_tasks": overdue or 0}
