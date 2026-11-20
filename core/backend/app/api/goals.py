from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.goals import CompanyStrategy, Goal, GoalChange, GoalPlan, GoalTask
from app.models.org import Department
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import now

router = APIRouter(prefix="/v1/org/goals", tags=["goals"])

register_template("goals.submitted", {"uz": "Maqsadlar tasdiqqa yuborildi", "ru": "Цели отправлены на утверждение"}, {"uz": "{dept}: {year}-yil", "ru": "{dept}: {year} г."}, "info")
register_template("goals.decided", {"uz": "Maqsadlar bo'yicha qaror", "ru": "Решение по целям"}, {"uz": "{dept} ({year}): {result}", "ru": "{dept} ({year}): {result}"}, "info")
register_template("goals.change", {"uz": "Maqsadni o'zgartirish so'rovi", "ru": "Запрос на изменение цели"}, {"uz": "{dept}: {reason}", "ru": "{dept}: {reason}"}, "warning")

FIELDS = ("title", "specific", "metric", "unit", "baseline", "target", "achievable", "relevant", "deadline", "owner_user_id", "sort_order")


class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    specific: str | None = Field(default=None, max_length=2000)
    metric: str = Field(min_length=1, max_length=120)
    unit: str | None = Field(default=None, max_length=20)
    baseline: float | None = None
    target: float
    achievable: str | None = Field(default=None, max_length=2000)
    relevant: str | None = Field(default=None, max_length=2000)
    deadline: date
    owner_user_id: int | None = None
    sort_order: int = 0


class ChangeIn(BaseModel):
    action: Literal["add", "update", "remove"]
    goal_id: int | None = None
    values: GoalIn | None = None
    reason: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _shape(self) -> "ChangeIn":
        if self.action != "add" and not self.goal_id:
            raise ValueError("goal_id kerak")
        if self.action != "remove" and not self.values:
            raise ValueError("values kerak")
        return self


class ProgressIn(BaseModel):
    current: float | None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    owner_user_id: int | None = None
    due_date: date | None = None
    progress: int = Field(default=0, ge=0, le=100)
    note: str | None = Field(default=None, max_length=2000)
    sort_order: int = 0


class TaskProgressIn(BaseModel):
    progress: int = Field(ge=0, le=100)


SWOT_KEYS = ("strengths", "weaknesses", "opportunities", "threats")


class SwotIn(BaseModel):
    strengths: list[str] = Field(default_factory=list, max_length=30)
    weaknesses: list[str] = Field(default_factory=list, max_length=30)
    opportunities: list[str] = Field(default_factory=list, max_length=30)
    threats: list[str] = Field(default_factory=list, max_length=30)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class DecideIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


def _year(year: int | None) -> int:
    return year or now().year


def progress(g: Goal) -> int | None:
    if g.current is None:
        return None
    base = g.baseline or 0.0
    if g.target == base:
        return 100 if g.current >= g.target else 0
    return max(0, min(999, round((g.current - base) / (g.target - base) * 100)))


def task_progress(tasks: list[GoalTask]) -> int | None:
    return round(sum(t.progress for t in tasks) / len(tasks)) if tasks else None


def effective_progress(g: Goal, tasks: list[GoalTask]) -> int | None:
    """Reyting uchun: o'lchov kiritilgan bo'lsa o'shani, aks holda vazifalar o'rtacha progressini olamiz."""
    p = progress(g)
    return p if p is not None else task_progress(tasks)


async def _tasks_by_goal(db: AsyncSession, goal_ids: list[int]) -> dict[int, list[GoalTask]]:
    out: dict[int, list[GoalTask]] = {}
    if goal_ids:
        for t in (await db.scalars(select(GoalTask).where(GoalTask.goal_id.in_(goal_ids)).order_by(GoalTask.sort_order, GoalTask.id))).all():
            out.setdefault(t.goal_id, []).append(t)
    return out


def _task_out(t: GoalTask, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": t.id, "goal_id": t.goal_id, "title": t.title, "owner_user_id": t.owner_user_id, "owner": names.get(t.owner_user_id) if t.owner_user_id else None,  # type: ignore[arg-type]
        "due_date": t.due_date, "progress": t.progress, "note": t.note, "sort_order": t.sort_order,
    }  # fmt: skip


async def _dept(db: AsyncSession, dept_id: int) -> Department:
    d = await db.get(Department, dept_id)
    if not d:
        raise error(404, "not_found")
    return d


def _can_edit(auth: AuthContext, dept: Department) -> bool:
    return auth.can("goals.manage") or dept.head_user_id == auth.user.id


def _need_read(auth: AuthContext, dept: Department | None = None) -> None:
    if not (auth.can("org.read") or auth.can("goals.manage") or (dept and dept.head_user_id == auth.user.id)):
        raise error(403, "forbidden")


def _need_edit(auth: AuthContext, dept: Department) -> None:
    if not _can_edit(auth, dept):
        raise error(403, "forbidden")


def _need_approve(auth: AuthContext) -> None:
    if not auth.can("goals.approve"):
        raise error(403, "forbidden")


async def _plan(db: AsyncSession, dept_id: int, year: int, create: bool = False) -> GoalPlan | None:
    plan = await db.scalar(select(GoalPlan).where(GoalPlan.department_id == dept_id, GoalPlan.year == year))
    if not plan and create:
        plan = GoalPlan(department_id=dept_id, year=year, status="draft")
        db.add(plan)
        await db.flush()
    return plan


async def _goal(db: AsyncSession, gid: int) -> tuple[Goal, GoalPlan, Department]:
    g = await db.get(Goal, gid)
    if not g or g.removed_at:
        raise error(404, "not_found")
    plan = await db.get(GoalPlan, g.plan_id)
    return g, plan, await _dept(db, plan.department_id)  # type: ignore[union-attr,arg-type]


async def _check_values(db: AsyncSession, v: GoalIn, year: int) -> None:
    if v.deadline.year != year:
        raise error(422, "deadline_year", year=year)
    if v.owner_user_id and not await db.get(User, v.owner_user_id):
        raise error(422, "owner_not_found")


def _snapshot(g: Goal) -> dict[str, Any]:
    return GoalIn.model_validate({f: getattr(g, f) for f in FIELDS}).model_dump(mode="json")


def _apply(g: Goal, v: GoalIn) -> None:
    for f in FIELDS:
        setattr(g, f, getattr(v, f))


async def _names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids.discard(None)
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())  # type: ignore[arg-type]


def _goal_out(g: Goal, names: dict[int, str], tasks: list[GoalTask] | None = None) -> dict[str, Any]:
    tasks = tasks or []
    return {
        "id": g.id, **_snapshot(g), "current": g.current, "progress": progress(g), "owner": names.get(g.owner_user_id) if g.owner_user_id else None,  # type: ignore[arg-type]
        "tasks": [_task_out(t, names) for t in tasks], "task_progress": task_progress(tasks), "effective_progress": effective_progress(g, tasks),
    }  # fmt: skip


async def _approvers(db: AsyncSession, exclude: int) -> list[int]:
    return [u for u in await users_with_permission(db, "goals.approve") if u != exclude]


@router.get("")
async def overview(year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_read(auth)
    y = _year(year)
    depts = (await db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.sort_order, Department.name))).all()
    plans = {p.department_id: p for p in (await db.scalars(select(GoalPlan).where(GoalPlan.year == y))).all()}
    goals: dict[int, list[Goal]] = {}
    for g in (await db.scalars(select(Goal).where(Goal.plan_id.in_([p.id for p in plans.values()]), Goal.removed_at.is_(None)))).all() if plans else []:
        goals.setdefault(g.plan_id, []).append(g)
    pending = dict((await db.execute(select(GoalChange.plan_id, func.count()).where(GoalChange.status == "pending").group_by(GoalChange.plan_id))).all())
    tasks = await _tasks_by_goal(db, [g.id for gs in goals.values() for g in gs])
    rows = []
    for d in depts:
        p = plans.get(d.id)
        gs = goals.get(p.id, []) if p else []
        pr = [x for x in (effective_progress(g, tasks.get(g.id, [])) for g in gs) if x is not None]
        rows.append({
            "id": d.id, "name": d.name, "parent_id": d.parent_id, "status": p.status if p else None, "goals": len(gs),
            "tasks": sum(len(tasks.get(g.id, [])) for g in gs),
            "progress": round(sum(min(x, 100) for x in pr) / len(pr)) if pr else None, "pending_changes": pending.get(p.id, 0) if p else 0,
        })  # fmt: skip
    return {"year": y, "departments": rows, "can_approve": auth.can("goals.approve")}


@router.get("/departments/{dept_id}")
async def department_goals(dept_id: int, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    dept = await _dept(db, dept_id)
    _need_read(auth, dept)
    y = _year(year)
    plan = await _plan(db, dept_id, y)
    goals = (await db.scalars(select(Goal).where(Goal.plan_id == plan.id, Goal.removed_at.is_(None)).order_by(Goal.sort_order, Goal.id))).all() if plan else []
    changes = (await db.scalars(select(GoalChange).where(GoalChange.plan_id == plan.id).order_by(GoalChange.id.desc()))).all() if plan else []
    tasks = await _tasks_by_goal(db, [g.id for g in goals])
    names = await _names(db, {g.owner_user_id for g in goals} | {t.owner_user_id for ts in tasks.values() for t in ts} | {c.requested_by for c in changes} | {c.decided_by for c in changes} | ({plan.approved_by, plan.submitted_by} if plan else set()))
    return {
        "year": y,
        "department": {"id": dept.id, "name": dept.name, "yqm": dept.yqm, "head_user_id": dept.head_user_id},
        "plan": {
            "status": plan.status, "note": plan.note, "submitted_at": plan.submitted_at, "submitted_by": names.get(plan.submitted_by),  # type: ignore[arg-type]
            "approved_at": plan.approved_at, "approved_by": names.get(plan.approved_by),  # type: ignore[arg-type]
        } if plan else None,
        "goals": [_goal_out(g, names, tasks.get(g.id)) for g in goals],
        "changes": [{
            "id": c.id, "goal_id": c.goal_id, "action": c.action, "before": c.before, "after": c.after, "reason": c.reason, "status": c.status,
            "requested_by": names.get(c.requested_by), "created_at": c.created_at,  # type: ignore[arg-type]
            "decided_by": names.get(c.decided_by), "decided_at": c.decided_at, "decision_note": c.decision_note,  # type: ignore[arg-type]
        } for c in changes],
        "can_edit": _can_edit(auth, dept),
        "can_approve": auth.can("goals.approve"),
    }  # fmt: skip


@router.post("/departments/{dept_id}", status_code=201)
async def add_goal(dept_id: int, body: GoalIn, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    dept = await _dept(db, dept_id)
    _need_edit(auth, dept)
    y = _year(year)
    plan = await _plan(db, dept_id, y, create=True)
    if plan.status != "draft":  # type: ignore[union-attr]
        raise error(409, "plan_locked")
    await _check_values(db, body, y)
    g = Goal(plan_id=plan.id)  # type: ignore[union-attr]
    _apply(g, body)
    db.add(g)
    await db.commit()
    return {"id": g.id}


@router.put("/items/{gid}")
async def update_goal(gid: int, body: GoalIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    g, plan, dept = await _goal(db, gid)
    _need_edit(auth, dept)
    if plan.status != "draft":
        raise error(409, "plan_locked")
    await _check_values(db, body, plan.year)
    _apply(g, body)
    await db.commit()
    return {"id": g.id}


@router.delete("/items/{gid}", status_code=204)
async def delete_goal(gid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    g, plan, dept = await _goal(db, gid)
    _need_edit(auth, dept)
    if plan.status != "draft":
        raise error(409, "plan_locked")
    await db.delete(g)
    await db.commit()


@router.put("/items/{gid}/progress")
async def set_progress(gid: int, body: ProgressIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    g, plan, dept = await _goal(db, gid)
    if not (_can_edit(auth, dept) or g.owner_user_id == auth.user.id):
        raise error(403, "forbidden")
    if plan.status != "approved":
        raise error(409, "plan_not_approved")
    g.current = body.current
    await db.commit()
    return {"current": g.current, "progress": progress(g)}


# --- Haftalik vazifalar: maqsad kichik qadamlarga bo'linadi; reja tasdiqlangandan keyin ham yuritiladi ---


async def _task(db: AsyncSession, tid: int) -> tuple[GoalTask, Goal, Department]:
    t = await db.get(GoalTask, tid)
    if not t:
        raise error(404, "not_found")
    g, _plan_, dept = await _goal(db, t.goal_id)
    return t, g, dept


def _need_task_edit(auth: AuthContext, g: Goal, dept: Department) -> None:
    if not (_can_edit(auth, dept) or g.owner_user_id == auth.user.id):
        raise error(403, "forbidden")


@router.post("/items/{gid}/tasks", status_code=201)
async def add_task(gid: int, body: TaskIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    g, _plan_, dept = await _goal(db, gid)
    _need_task_edit(auth, g, dept)
    if body.owner_user_id and not await db.get(User, body.owner_user_id):
        raise error(422, "owner_not_found")
    t = GoalTask(goal_id=g.id, **body.model_dump())
    db.add(t)
    await db.commit()
    return {"id": t.id}


@router.put("/tasks/{tid}")
async def update_task(tid: int, body: TaskIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    t, g, dept = await _task(db, tid)
    _need_task_edit(auth, g, dept)
    if body.owner_user_id and not await db.get(User, body.owner_user_id):
        raise error(422, "owner_not_found")
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    await db.commit()
    return {"id": t.id}


@router.put("/tasks/{tid}/progress")
async def set_task_progress(tid: int, body: TaskProgressIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    t, g, dept = await _task(db, tid)
    if not (_can_edit(auth, dept) or g.owner_user_id == auth.user.id or t.owner_user_id == auth.user.id):
        raise error(403, "forbidden")
    t.progress = body.progress
    await db.commit()
    return {"progress": t.progress}


@router.delete("/tasks/{tid}", status_code=204)
async def delete_task(tid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    t, g, dept = await _task(db, tid)
    _need_task_edit(auth, g, dept)
    await db.delete(t)
    await db.commit()


# --- Yillik kompaniya strategiyasi: SWOT tahlil ---


def _swot_out(s: CompanyStrategy | None, y: int, auth: AuthContext) -> dict[str, Any]:
    data = (s.swot if s else None) or {}
    return {"year": y, **{k: list(data.get(k) or []) for k in SWOT_KEYS}, "updated_at": s.updated_at if s else None, "can_edit": auth.can("goals.manage") or auth.can("hrdocs.manage")}


@router.get("/strategy")
async def get_strategy(year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not (auth.can("hrdocs.read") or auth.can("org.read") or auth.can("goals.manage")):
        raise error(403, "forbidden")
    y = _year(year)
    s = await db.scalar(select(CompanyStrategy).where(CompanyStrategy.year == y))
    return _swot_out(s, y, auth)


@router.put("/strategy")
async def put_strategy(body: SwotIn, request: Request, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not (auth.can("goals.manage") or auth.can("hrdocs.manage")):
        raise error(403, "forbidden")
    y = _year(year)
    s = await db.scalar(select(CompanyStrategy).where(CompanyStrategy.year == y))
    if not s:
        s = CompanyStrategy(year=y)
        db.add(s)
    s.swot = {k: [x.strip()[:300] for x in getattr(body, k) if x.strip()] for k in SWOT_KEYS}
    s.updated_by = auth.user.id
    await audit(db, request, "strategy.swot", actor=auth.user, entity="company_strategy", entity_id=y, data={"year": y})
    await db.commit()
    await db.refresh(s)
    return _swot_out(s, y, auth)


async def _decide_notify(db: AsyncSession, plan: GoalPlan, dept: Department, auth: AuthContext, result: str) -> list:
    to = {u for u in (plan.submitted_by, dept.head_user_id) if u and u != auth.user.id}
    return await notify(db, to, "goals.decided", params={"dept": dept.name, "year": plan.year, "result": result}, link=f"/org/goals/{dept.id}?year={plan.year}") if to else []


@router.post("/departments/{dept_id}/submit")
async def submit(dept_id: int, request: Request, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    dept = await _dept(db, dept_id)
    _need_edit(auth, dept)
    plan = await _plan(db, dept_id, _year(year))
    if not plan or plan.status != "draft":
        raise error(409, "plan_not_draft")
    if not await db.scalar(select(func.count()).select_from(Goal).where(Goal.plan_id == plan.id, Goal.removed_at.is_(None))):
        raise error(422, "no_goals")
    plan.status, plan.note, plan.submitted_by, plan.submitted_at = "pending", None, auth.user.id, now()
    to = await _approvers(db, auth.user.id)
    notes = await notify(db, to, "goals.submitted", params={"dept": dept.name, "year": plan.year}, link=f"/org/goals/{dept.id}?year={plan.year}") if to else []
    await audit(db, request, "goals.submit", actor=auth.user, entity="department", entity_id=dept.id, data={"year": plan.year})
    await db.commit()
    await deliver(request.app, notes)
    return {"status": plan.status}


@router.post("/departments/{dept_id}/approve")
async def approve(dept_id: int, request: Request, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_approve(auth)
    dept = await _dept(db, dept_id)
    plan = await _plan(db, dept_id, _year(year))
    if not plan or plan.status == "approved":
        raise error(409, "plan_not_pending")
    if not await db.scalar(select(func.count()).select_from(Goal).where(Goal.plan_id == plan.id, Goal.removed_at.is_(None))):
        raise error(422, "no_goals")
    plan.status, plan.note, plan.approved_by, plan.approved_at = "approved", None, auth.user.id, now()
    notes = await _decide_notify(db, plan, dept, auth, "tasdiqlandi")
    await audit(db, request, "goals.approve", actor=auth.user, entity="department", entity_id=dept.id, data={"year": plan.year})
    await db.commit()
    await deliver(request.app, notes)
    return {"status": plan.status}


@router.post("/departments/{dept_id}/return")
async def return_plan(dept_id: int, body: NoteIn, request: Request, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_approve(auth)
    dept = await _dept(db, dept_id)
    plan = await _plan(db, dept_id, _year(year))
    if not plan or plan.status != "pending":
        raise error(409, "plan_not_pending")
    plan.status, plan.note = "draft", body.note.strip()
    notes = await _decide_notify(db, plan, dept, auth, f"qaytarildi: {plan.note}")
    await audit(db, request, "goals.return", actor=auth.user, entity="department", entity_id=dept.id, data={"year": plan.year})
    await db.commit()
    await deliver(request.app, notes)
    return {"status": plan.status}


@router.post("/departments/{dept_id}/changes", status_code=201)
async def request_change(dept_id: int, body: ChangeIn, request: Request, year: int | None = Query(default=None, ge=2000, le=2100), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    dept = await _dept(db, dept_id)
    _need_edit(auth, dept)
    plan = await _plan(db, dept_id, _year(year))
    if not plan or plan.status != "approved":
        raise error(409, "plan_not_approved")
    before = None
    if body.goal_id:
        g = await db.get(Goal, body.goal_id)
        if not g or g.plan_id != plan.id or g.removed_at:
            raise error(404, "not_found")
        if await db.scalar(select(GoalChange.id).where(GoalChange.goal_id == g.id, GoalChange.status == "pending")):
            raise error(409, "change_pending")
        before = _snapshot(g)
    if body.values:
        await _check_values(db, body.values, plan.year)
    c = GoalChange(plan_id=plan.id, goal_id=body.goal_id, action=body.action, before=before, after=body.values.model_dump(mode="json") if body.values else None, reason=body.reason.strip(), status="pending", requested_by=auth.user.id)
    db.add(c)
    to = await _approvers(db, auth.user.id)
    notes = await notify(db, to, "goals.change", params={"dept": dept.name, "reason": c.reason}, link=f"/org/goals/{dept.id}?year={plan.year}") if to else []
    await audit(db, request, "goals.change_request", actor=auth.user, entity="department", entity_id=dept.id, data={"year": plan.year, "action": body.action, "goal_id": body.goal_id})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": c.id}


@router.post("/changes/{cid}/decide")
async def decide_change(cid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_approve(auth)
    c = await db.get(GoalChange, cid)
    if not c:
        raise error(404, "not_found")
    if c.status != "pending":
        raise error(409, "already_decided")
    plan = await db.get(GoalPlan, c.plan_id)
    dept = await _dept(db, plan.department_id)  # type: ignore[union-attr]
    if body.approve:
        g = await db.get(Goal, c.goal_id) if c.goal_id else None
        if c.action != "add" and (not g or g.removed_at):
            raise error(409, "goal_missing")
        if c.action == "add":
            g = Goal(plan_id=plan.id)  # type: ignore[union-attr]
            db.add(g)
        if c.action == "remove":
            g.removed_at = now()  # type: ignore[union-attr]
        else:
            _apply(g, GoalIn.model_validate(c.after))  # type: ignore[arg-type]
        await db.flush()
        c.goal_id = g.id  # type: ignore[union-attr]
    c.status, c.decided_by, c.decided_at, c.decision_note = ("approved" if body.approve else "rejected"), auth.user.id, now(), (body.note or "").strip() or None
    to = [c.requested_by] if c.requested_by and c.requested_by != auth.user.id else []
    result = "o'zgarish tasdiqlandi" if body.approve else "o'zgarish rad etildi"
    notes = await notify(db, to, "goals.decided", params={"dept": dept.name, "year": plan.year, "result": result}, link=f"/org/goals/{dept.id}?year={plan.year}") if to else []  # type: ignore[union-attr]
    await audit(db, request, "goals.change_decide", actor=auth.user, entity="department", entity_id=dept.id, data={"change_id": c.id, "approve": body.approve})
    await db.commit()
    await deliver(request.app, notes)
    return {"status": c.status, "goal_id": c.goal_id}
