"""Bo'lim/lavozim ish chek-listlari: shablonlar, xodimning «Mening chek-listim» va koordinator/HR nazorati."""

from datetime import date, time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.duty import DutyChecklist, DutyRun
from app.models.employees import Employee
from app.models.org import Department, Position
from app.services import duty as svc
from app.services.audit import audit
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/duty", tags=["duty"])


class ItemIn(BaseModel):
    id: str | None = Field(default=None, max_length=16)
    text: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="yesno", pattern="^(yesno|score)$")
    required: bool = True


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=300)
    scope: str = Field(pattern="^(department|position)$")
    department_id: int | None = None
    position_id: int | None = None
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")
    deadline_time: time = time(20, 0)
    is_active: bool = True
    items: list[ItemIn] = Field(min_length=1, max_length=svc.MAX_ITEMS)


class SubmitIn(BaseModel):
    answers: dict[str, Any]
    note: str | None = Field(default=None, max_length=1000)


def _need(auth: AuthContext, *perms: str) -> None:
    if not any(svc.has(auth, p) for p in perms):
        raise error(403, "forbidden")


async def _validate_target(db: AsyncSession, body: TemplateIn) -> tuple[int | None, int | None]:
    if body.scope == "department":
        if not body.department_id or not await db.get(Department, body.department_id):
            raise error(400, "unknown_department")
        return body.department_id, None
    pos = await db.get(Position, body.position_id) if body.position_id else None
    if not pos:
        raise error(400, "unknown_position")
    return pos.department_id, pos.id


@router.get("/templates")
async def list_templates(department_id: int | None = None, position_id: int | None = None, active: bool | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.read", "duty.manage", "duty.control")
    stmt = select(DutyChecklist).order_by(DutyChecklist.name)
    if department_id:
        pos_ids = select(Position.id).where(Position.department_id == department_id)
        stmt = stmt.where((DutyChecklist.department_id == department_id) | (DutyChecklist.position_id.in_(pos_ids)))
    if position_id:
        stmt = stmt.where(DutyChecklist.position_id == position_id)
    if active is not None:
        stmt = stmt.where(DutyChecklist.is_active.is_(active))
    names = await svc.names_map(db)
    return [svc.template_out(c, names, with_items=False) for c in (await db.scalars(stmt)).all()]


@router.post("/templates", status_code=201)
async def create_template(body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.manage")
    dept, pos = await _validate_target(db, body)
    cl = DutyChecklist(name=body.name.strip(), description=body.description, scope=body.scope, department_id=dept if body.scope == "department" else None, position_id=pos,
                       frequency=body.frequency, deadline_time=body.deadline_time, items=svc.clean_items([i.model_dump() for i in body.items]), is_active=body.is_active, created_by=auth.user.id)  # fmt: skip
    db.add(cl)
    await db.flush()
    await audit(db, request, "duty.create", actor=auth.user, entity="duty_checklist", entity_id=cl.id, data={"scope": cl.scope})
    await db.commit()
    return svc.template_out(cl, await svc.names_map(db))


@router.get("/templates/{cid}")
async def get_template(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.read", "duty.manage", "duty.control")
    cl = await db.get(DutyChecklist, cid)
    if not cl:
        raise error(404, "not_found")
    return svc.template_out(cl, await svc.names_map(db))


@router.put("/templates/{cid}")
async def update_template(cid: int, body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.manage")
    cl = await db.get(DutyChecklist, cid)
    if not cl:
        raise error(404, "not_found")
    dept, pos = await _validate_target(db, body)
    cl.name, cl.description, cl.scope, cl.frequency, cl.deadline_time, cl.is_active = body.name.strip(), body.description, body.scope, body.frequency, body.deadline_time, body.is_active
    cl.department_id, cl.position_id = (dept if body.scope == "department" else None), pos
    cl.items = svc.clean_items([i.model_dump() for i in body.items])
    await audit(db, request, "duty.update", actor=auth.user, entity="duty_checklist", entity_id=cl.id)
    await db.commit()
    return svc.template_out(cl, await svc.names_map(db))


@router.delete("/templates/{cid}", status_code=204)
async def delete_template(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.manage")
    cl = await db.get(DutyChecklist, cid)
    if not cl:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(DutyRun).where(DutyRun.checklist_id == cid, DutyRun.completed_at.is_not(None))):
        raise error(409, "in_use")  # natijalari bor: o'chirish o'rniga nofaol qiling
    await audit(db, request, "duty.delete", actor=auth.user, entity="duty_checklist", entity_id=cid)
    await db.delete(cl)
    await db.commit()


async def _my_employee(db: AsyncSession, auth: AuthContext) -> Employee | None:
    return await db.scalar(select(Employee).where(Employee.user_id == auth.user.id, Employee.status == "active"))


def _run_out(r: DutyRun | None) -> dict[str, Any] | None:
    return {"answers": r.answers, "note": r.note, "score_pct": r.score_pct, "completed_at": r.completed_at, "late": r.late} if r and r.completed_at else None


@router.get("/my")
async def my_checklists(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Menga biriktirilgan (lavozim va bo'lim bo'yicha) joriy kun/hafta chek-listlari."""
    _need(auth, "duty.own")
    emp = await _my_employee(db, auth)
    if not emp:
        return {"employee": None, "items": []}
    moment = now()
    today = local_date(moment)
    out = []
    for cl in await svc.applicable(db, emp):
        start = svc.period_start(cl.frequency, today)
        run = await db.scalar(select(DutyRun).where(DutyRun.checklist_id == cl.id, DutyRun.employee_id == emp.id, DutyRun.period_date == start))
        out.append({"checklist": svc.template_out(cl), "period_start": start, "due_at": svc.due_at(cl, start), "status": svc.run_status(cl, run, start, moment), "run": _run_out(run)})
    return {"employee": {"id": emp.id, "name": emp.full_name}, "items": out}


@router.put("/my/{cid}")
async def submit(cid: int, body: SubmitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "duty.own")
    emp = await _my_employee(db, auth)
    cl = await db.get(DutyChecklist, cid)
    if not emp or not cl or not cl.is_active or cl not in await svc.applicable(db, emp):
        raise error(404, "not_found")
    moment = now()
    start = svc.period_start(cl.frequency, local_date(moment))
    answers, score = svc.check_answers(cl.items, body.answers)
    run = await db.scalar(select(DutyRun).where(DutyRun.checklist_id == cl.id, DutyRun.employee_id == emp.id, DutyRun.period_date == start).with_for_update())
    if run is None:
        run = DutyRun(checklist_id=cl.id, employee_id=emp.id, period_date=start)
        db.add(run)
    run.answers, run.note, run.score_pct = answers, (body.note or "").strip() or None, score
    first = run.completed_at is None
    run.completed_at = run.completed_at or moment
    run.late = run.late or (first and moment > svc.due_at(cl, start))
    await audit(db, request, "duty.submit", actor=auth.user, entity="duty_checklist", entity_id=cl.id, data={"score": score, "late": run.late})
    await db.commit()
    return {"status": "done", "run": _run_out(run), "score_pct": score}


@router.get("/control")
async def control(
    day: date | None = Query(default=None, alias="date"),
    branch_id: int | None = None,
    department_id: int | None = None,
    position_id: int | None = None,
    status: str | None = Query(default=None, pattern="^(all|done|open|overdue)$"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    """Nazorat: kim chek-listni bajargan, kim bajarmagan (HR hammani, mudir/koordinator o'z filiallarini ko'radi)."""
    _need(auth, "duty.read", "duty.manage", "duty.control")
    moment = now()
    return await svc.control(db, auth, day or local_date(moment), moment, branch_id=branch_id, department_id=department_id, position_id=position_id, status=status)
