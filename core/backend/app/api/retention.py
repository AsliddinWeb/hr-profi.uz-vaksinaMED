"""Ushlab qolish (ketish xavfi), haftalik uchrashuv, offboarding va nazorat paneli."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import DismissIn, dismiss_one
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch
from app.models.retention import Offboarding, RetentionCase, RetentionMeeting
from app.models.tasks import Task
from app.services import retention as svc
from app.services import tasks as task_svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/retention", tags=["retention"])
off_router = APIRouter(prefix="/v1/offboarding", tags=["offboarding"])
control_router = APIRouter(prefix="/v1/control", tags=["control"])

RISK_UZ = {"low": "past", "medium": "o'rta", "high": "yuqori"}


def _need(auth: AuthContext, *perms: str) -> None:
    if not any(svc.has(auth, p) for p in perms):
        raise error(403, "forbidden")


async def _case_ctx(db: AsyncSession, cid: int, auth: AuthContext, *, lock: bool = False) -> tuple[RetentionCase, Employee, Branch | None]:
    stmt = select(RetentionCase).where(RetentionCase.id == cid)
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, c.employee_id) if c else None
    branch = await db.get(Branch, emp.branch_id) if emp and emp.branch_id else None
    if not c or not emp or not (svc.sees_all(auth) or svc.is_branch_lead(auth, branch) or auth.user.id in await svc.mentor_ids(db, emp.id)):
        raise error(404, "not_found")
    return c, emp, branch


def _case_out(c: RetentionCase, emp: Employee, branch: Branch | None, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": c.id, "status": c.status, "risk_level": c.risk_level, "source": c.source, "employee": {"id": emp.id, "name": emp.full_name}, "branch": branch.name if branch else None,
        "note": c.note, "notice_date": c.notice_date, "planned_leave_date": c.planned_leave_date, "reported_by": names.get(c.reported_by or 0), "created_at": c.created_at,
        "hr": {"note": c.hr_note, "by": names.get(c.hr_by or 0), "at": c.hr_at}, "trainer": {"note": c.trainer_note, "by": names.get(c.trainer_by or 0), "at": c.trainer_at},
        "auditor": {"note": c.auditor_note, "by": names.get(c.auditor_by or 0), "at": c.auditor_at},
        "decision": c.decision, "decision_note": c.decision_note, "decision_at": c.decision_at, "last_discussed_on": c.last_discussed_on, "events": c.events or [],
    }  # fmt: skip


async def _names(db: AsyncSession, cases: list[RetentionCase]) -> dict[int, str]:
    ids = {u for c in cases for u in (c.reported_by, c.hr_by, c.trainer_by, c.auditor_by, c.decision_by) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


class CaseIn(BaseModel):
    employee_id: int
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    note: str = Field(min_length=3, max_length=2000)
    notice_date: date | None = None
    planned_leave_date: date | None = None


@router.post("/cases", status_code=201)
async def create_case(body: CaseIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Mudir/koordinator ketish xavfini bildiradi (yoki xodim ketish haqida ogohlantirgan: sana bilan). HR menejerga xabar boradi."""
    _need(auth, "retention.report", "retention.manage")
    emp = await db.get(Employee, body.employee_id)
    if not emp or emp.status != "active":
        raise error(400, "unknown_employee")
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    if not (svc.has(auth, "retention.manage") or svc.is_branch_lead(auth, branch)):
        raise error(403, "forbidden")
    if await db.scalar(select(RetentionCase.id).where(RetentionCase.employee_id == emp.id, RetentionCase.status == "open")):
        raise error(409, "case_exists")
    moment = now()
    c = RetentionCase(
        employee_id=emp.id, status="open", risk_level="high" if body.notice_date else body.risk_level, source="notice" if body.notice_date else "manual", reported_by=auth.user.id,
        note=body.note.strip(), notice_date=body.notice_date, planned_leave_date=body.planned_leave_date, events=[],
    )  # fmt: skip
    svc.add_event(c, auth.user.full_name, "created", c.note, moment)
    db.add(c)
    await db.flush()
    notes = await notify(
        db, [u for u in await users_with_permission(db, "retention.manage") if u != auth.user.id], "retention.new", link=f"/retention/{c.id}",
        params={"employee": emp.full_name, "branch": branch.name if branch else "—", "risk": RISK_UZ[c.risk_level]},
    )  # fmt: skip
    await audit(db, request, "retention.create", actor=auth.user, entity="retention_case", entity_id=c.id, data={"employee_id": emp.id, "source": c.source})
    await db.commit()
    await deliver(request.app, notes)
    return _case_out(c, emp, branch, await _names(db, [c]))


@router.get("/cases")
async def list_cases(status: str | None = Query(default=None, pattern="^(open|retained|leaving)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "retention.report", "retention.manage", "retention.read", "retention.audit")
    stmt = select(RetentionCase, Employee).join(Employee, Employee.id == RetentionCase.employee_id)
    if not svc.sees_all(auth):
        stmt = stmt.where(Employee.branch_id.in_(select(Branch.id).where((Branch.manager_user_id == auth.user.id) | (Branch.coordinator_user_id == auth.user.id))))
    if status:
        stmt = stmt.where(RetentionCase.status == status)
    rows = (await db.execute(stmt.order_by(RetentionCase.id.desc()).limit(200))).all()
    names = await _names(db, [c for c, _ in rows])
    br = {b.id: b for b in (await db.scalars(select(Branch))).all()}
    return [_case_out(c, e, br.get(e.branch_id or 0), names) for c, e in rows]


@router.get("/cases/{cid}")
async def get_case(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    c, emp, branch = await _case_ctx(db, cid, auth)
    out = _case_out(c, emp, branch, await _names(db, [c]))
    mentor = auth.user.id in await svc.mentor_ids(db, emp.id)
    live = c.status == "open"
    out["can"] = {"interview": live and svc.has(auth, "retention.manage"), "trainer": live and (mentor or svc.has(auth, "retention.manage")), "audit": live and svc.has(auth, "retention.audit"), "decide": live and svc.has(auth, "retention.manage")}
    return out


class NoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=3000)


async def _step(request: Request, db: AsyncSession, auth: AuthContext, cid: int, role: str, note: str) -> dict[str, Any]:
    c, emp, branch = await _case_ctx(db, cid, auth, lock=True)
    if c.status != "open":
        raise error(409, "already_decided")
    moment = now()
    note = note.strip()
    labels = {"hr": "HR suhbati", "trainer": "Trener yechimi", "auditor": "Auditor xulosasi"}
    setattr(c, f"{role}_note", note)
    setattr(c, f"{role}_by", auth.user.id)
    setattr(c, f"{role}_at", moment)
    svc.add_event(c, auth.user.full_name, role, note, moment)
    targets = {u for u in [*await users_with_permission(db, "retention.manage"), *await users_with_permission(db, "retention.read")] if u != auth.user.id}
    notes = await notify(db, list(targets), "retention.step", link=f"/retention/{c.id}", params={"employee": emp.full_name, "text": f"{labels[role]}: {note[:120]}"})
    await audit(db, request, f"retention.{role}", actor=auth.user, entity="retention_case", entity_id=c.id)
    await db.commit()
    await deliver(request.app, notes)
    return _case_out(c, emp, branch, await _names(db, [c]))


@router.post("/cases/{cid}/interview")
async def interview(cid: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "retention.manage")
    return await _step(request, db, auth, cid, "hr", body.note)


@router.post("/cases/{cid}/trainer")
async def trainer(cid: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    c, emp, _ = await _case_ctx(db, cid, auth)
    if not (svc.has(auth, "retention.manage") or auth.user.id in await svc.mentor_ids(db, emp.id)):
        raise error(403, "forbidden")
    return await _step(request, db, auth, cid, "trainer", body.note)


@router.post("/cases/{cid}/audit")
async def audit_case(cid: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "retention.audit")
    return await _step(request, db, auth, cid, "auditor", body.note)


class DecideIn(BaseModel):
    decision: str = Field(pattern="^(stay|leave)$")
    note: str | None = Field(default=None, max_length=2000)
    leave_date: date | None = None


@router.post("/cases/{cid}/decide")
async def decide(cid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Qaror: qoladi (holat yopiladi) yoki ketadi (offboarding avtomatik ochiladi)."""
    _need(auth, "retention.manage")
    c, emp, branch = await _case_ctx(db, cid, auth, lock=True)
    if c.status != "open":
        raise error(409, "already_decided")
    note = (body.note or "").strip() or None
    if body.decision == "stay" and not (c.hr_at or note):
        raise error(409, "interview_required")
    moment = now()
    c.decision, c.decision_note, c.decision_by, c.decision_at = body.decision, note, auth.user.id, moment
    c.status = "retained" if body.decision == "stay" else "leaving"
    svc.add_event(c, auth.user.full_name, "decision", f"{body.decision}: {note or ''}", moment)
    off = None
    if body.decision == "leave":
        off = Offboarding(employee_id=emp.id, case_id=c.id, status="open", leave_date=body.leave_date or c.planned_leave_date, risks=[], measures=[], created_by=auth.user.id)
        db.add(off)
        await db.flush()
    targets = {u for u in [c.reported_by, *await users_with_permission(db, "retention.read"), *await svc.lead_ids(db, emp)] if u and u != auth.user.id}
    notes = await notify(db, list(targets), "retention.decided", link=f"/retention/{c.id}", params={"employee": emp.full_name, "result": "qoladi" if body.decision == "stay" else "ketadi: offboarding boshlandi"})
    if off:
        notes += await notify(db, [u for u in await users_with_permission(db, "retention.manage") if u != auth.user.id], "offboarding.opened", link=f"/offboarding/{off.id}", params={"employee": emp.full_name})
    await audit(db, request, "retention.decide", actor=auth.user, entity="retention_case", entity_id=c.id, data={"decision": body.decision, "offboarding": off.id if off else None}, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return {**_case_out(c, emp, branch, await _names(db, [c])), "offboarding_id": off.id if off else None}


# --- Haftalik uchrashuv -------------------------------------------------------------------


class MeetingIn(BaseModel):
    held_on: date
    summary: str = Field(min_length=3, max_length=3000)
    case_ids: list[int] = Field(default_factory=list, max_length=100)


@router.post("/meetings", status_code=201)
async def add_meeting(body: MeetingIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Haftalik uchrashuv xulosasi: muhokama qilingan ochiq holatlar belgilanadi; HRD va auditorga xabar boradi."""
    _need(auth, "retention.manage")
    cases = list((await db.scalars(select(RetentionCase).where(RetentionCase.id.in_(body.case_ids), RetentionCase.status == "open"))).all()) if body.case_ids else []
    moment = now()
    for c in cases:
        c.last_discussed_on = body.held_on
        svc.add_event(c, auth.user.full_name, "meeting", body.summary.strip()[:300], moment)
    m = RetentionMeeting(held_on=body.held_on, summary=body.summary.strip(), case_ids=[c.id for c in cases], created_by=auth.user.id, created_at=moment)
    db.add(m)
    await db.flush()
    targets = [u for u in await users_with_permission(db, "retention.read") if u != auth.user.id]
    notes = await notify(db, targets, "retention.meeting", link="/retention", params={"summary": f"{body.held_on:%d.%m.%Y}: {body.summary.strip()[:150]}"})
    await audit(db, request, "retention.meeting", actor=auth.user, entity="retention_meeting", entity_id=m.id, data={"cases": len(cases)})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": m.id, "cases": len(cases)}


@router.get("/meetings")
async def list_meetings(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "retention.manage", "retention.read", "retention.audit")
    return [{"id": m.id, "held_on": m.held_on, "summary": m.summary, "cases": len(m.case_ids or [])} for m in await svc.meetings_recent(db)]


# --- Offboarding --------------------------------------------------------------------------


async def _off_ctx(db: AsyncSession, oid: int, auth: AuthContext, *, lock: bool = False) -> tuple[Offboarding, Employee]:
    _need(auth, "retention.manage", "retention.read", "retention.audit")
    stmt = select(Offboarding).where(Offboarding.id == oid)
    o = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, o.employee_id) if o else None
    if not o or not emp:
        raise error(404, "not_found")
    return o, emp


def _off_out(o: Offboarding, emp: Employee, names: dict[int, str], tasks: dict[int, Task] | None = None) -> dict[str, Any]:
    tasks = tasks or {}
    return {
        "id": o.id, "status": o.status, "employee": {"id": emp.id, "name": emp.full_name}, "leave_date": o.leave_date, "reason_type": o.reason_type, "reason_text": o.reason_text,
        "prevent_text": o.prevent_text, "risks": o.risks or [], "exit_at": o.exit_at, "exit_by": names.get(o.exit_by or 0), "approved_at": o.approved_at, "approved_by": names.get(o.approved_by or 0),
        "completed_at": o.completed_at, "access_closed": o.access_closed, "case_id": o.case_id,
        "measures": [{**m, "assignee": names.get(m.get("assignee_id") or 0), "status": tasks[m["task_id"]].status if m.get("task_id") in tasks else None} for m in (o.measures or [])],
    }  # fmt: skip


async def _off_names(db: AsyncSession, os_: list[Offboarding]) -> dict[int, str]:
    ids = {u for o in os_ for u in (o.exit_by, o.approved_by, *[m.get("assignee_id") for m in (o.measures or [])]) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


class OffIn(BaseModel):
    employee_id: int
    leave_date: date | None = None


@off_router.post("", status_code=201)
async def create_offboarding(body: OffIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Ushlab qolish holatisiz ham boshlash mumkin (xodimni ketkazish qarori yoki to'g'ridan-to'g'ri ariza)."""
    _need(auth, "retention.manage")
    emp = await db.get(Employee, body.employee_id)
    if not emp or emp.status != "active":
        raise error(400, "unknown_employee")
    if await db.scalar(select(Offboarding.id).where(Offboarding.employee_id == emp.id, Offboarding.status == "open")):
        raise error(409, "case_exists")
    o = Offboarding(employee_id=emp.id, status="open", leave_date=body.leave_date, risks=[], measures=[], created_by=auth.user.id)
    db.add(o)
    await db.flush()
    await audit(db, request, "offboarding.create", actor=auth.user, entity="offboarding", entity_id=o.id, data={"employee_id": emp.id})
    await db.commit()
    return _off_out(o, emp, {})


@off_router.get("")
async def list_offboardings(status: str | None = Query(default=None, pattern="^(open|completed|cancelled)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "retention.manage", "retention.read", "retention.audit")
    stmt = select(Offboarding, Employee).join(Employee, Employee.id == Offboarding.employee_id).order_by(Offboarding.id.desc()).limit(200)
    if status:
        stmt = stmt.where(Offboarding.status == status)
    rows = (await db.execute(stmt)).all()
    names = await _off_names(db, [o for o, _ in rows])
    return [_off_out(o, e, names) for o, e in rows]


@off_router.get("/analytics")
async def analytics(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Ketish sabablari bazasi: sabab, xavf va filial bo'yicha (takrorlanayotgan muammolar)."""
    _need(auth, "retention.manage", "retention.read", "retention.audit")
    if end < start or (end - start).days > 400:
        raise error(400, "range_invalid", max_days=400)
    rows = (await db.execute(select(Offboarding, Employee).join(Employee, Employee.id == Offboarding.employee_id).where(Offboarding.exit_at.is_not(None), func.date(Offboarding.exit_at) >= start, func.date(Offboarding.exit_at) <= end))).all()
    reasons: dict[str, int] = {}
    risks: dict[str, int] = {}
    branches: dict[str, int] = {}
    br = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    for o, e in rows:
        reasons[o.reason_type or "other"] = reasons.get(o.reason_type or "other", 0) + 1
        for r in o.risks or []:
            risks[r] = risks.get(r, 0) + 1
        key = br.get(e.branch_id or 0, "—")
        branches[key] = branches.get(key, 0) + 1
    return {"total": len(rows), "reasons": reasons, "risks": risks, "branches": dict(sorted(branches.items(), key=lambda x: -x[1]))}


@off_router.get("/{oid}")
async def get_offboarding(oid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    o, emp = await _off_ctx(db, oid, auth)
    ids = [m["task_id"] for m in (o.measures or []) if m.get("task_id")]
    tasks = {t.id: t for t in (await db.scalars(select(Task).where(Task.id.in_(ids)))).all()} if ids else {}
    out = _off_out(o, emp, await _off_names(db, [o]), tasks)
    out["can"] = {"exit": o.status == "open" and svc.has(auth, "retention.manage"), "approve": o.status == "open" and o.exit_at is not None and o.approved_at is None and svc.has(auth, "retention.approve"), "complete": o.status == "open" and svc.has(auth, "retention.manage")}
    return out


class ExitIn(BaseModel):
    reason_type: str = Field(pattern=f"^({'|'.join(svc.REASONS)})$")
    reason_text: str = Field(min_length=3, max_length=3000)
    prevent_text: str | None = Field(default=None, max_length=3000)
    risks: list[str] = Field(default_factory=list, max_length=5)


@off_router.post("/{oid}/exit")
async def exit_interview(oid: int, body: ExitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Exit-intervyu: ketish sababi (xodimning so'zlari), ichkarida oldini olish va xavflar bazaga yoziladi; HRD ga xabar."""
    _need(auth, "retention.manage")
    o, emp = await _off_ctx(db, oid, auth, lock=True)
    if o.status != "open":
        raise error(409, "already_decided")
    if any(r not in svc.RISKS for r in body.risks):
        raise error(400, "risk_invalid")
    o.reason_type, o.reason_text, o.prevent_text, o.risks = body.reason_type, body.reason_text.strip(), (body.prevent_text or "").strip() or None, list(dict.fromkeys(body.risks))
    o.exit_by, o.exit_at = auth.user.id, now()
    notes = await notify(db, [u for u in await users_with_permission(db, "retention.approve") if u != auth.user.id], "offboarding.reasons", link=f"/offboarding/{o.id}", params={"employee": emp.full_name, "text": body.reason_text.strip()[:120]})
    await audit(db, request, "offboarding.exit", actor=auth.user, entity="offboarding", entity_id=o.id, data={"reason": body.reason_type, "risks": o.risks})
    await db.commit()
    await deliver(request.app, notes)
    return _off_out(o, emp, await _off_names(db, [o]))


class MeasureIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    assignee_id: int | None = None
    due_at: datetime | None = None


class MeasuresIn(BaseModel):
    measures: list[MeasureIn] = Field(min_length=1, max_length=10)


@off_router.post("/{oid}/measures", status_code=201)
async def add_measures(oid: int, body: MeasuresIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Choralar topshiriqlarga aylanadi (Topshiriqlar moduli): mas'ul, muddat; muddat o'tsa nazorat panelida ko'rinadi."""
    _need(auth, "retention.manage")
    o, emp = await _off_ctx(db, oid, auth, lock=True)
    if o.status != "open":
        raise error(409, "already_decided")
    added, notes = [], []
    for m in body.measures:
        await task_svc.validate_people(db, auth, m.assignee_id, [])
        t = Task(title=m.title.strip(), description=f"Offboarding: {emp.full_name}", priority="high", due_at=m.due_at, creator_id=auth.user.id, assignee_id=m.assignee_id, watchers=[], labels=["nazorat", f"offboarding-{o.id}"], status="todo", created_at=now())
        t.position = await task_svc.next_position(db, "todo")
        db.add(t)
        await db.flush()
        task_svc.log(db, t, auth.user.id, "created")
        added.append({"task_id": t.id, "title": t.title, "assignee_id": t.assignee_id, "due": m.due_at.isoformat() if m.due_at else None})
        if t.assignee_id and t.assignee_id != auth.user.id:
            notes += await notify(db, [t.assignee_id], "tasks.assigned", link=f"/tasks/{t.id}", params={"title": t.title})
    o.measures = [*(o.measures or []), *added]
    await audit(db, request, "offboarding.measures", actor=auth.user, entity="offboarding", entity_id=o.id, data={"count": len(added)})
    await db.commit()
    await deliver(request.app, notes)
    return {"added": len(added)}


@off_router.post("/{oid}/approve")
async def approve(oid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HRD: exit-intervyu xulosasi va choralarni ko'rib tasdiqlaydi."""
    _need(auth, "retention.approve")
    o, emp = await _off_ctx(db, oid, auth, lock=True)
    if o.status != "open" or o.exit_at is None:
        raise error(409, "exit_required")
    if o.approved_at:
        raise error(409, "already_decided")
    o.approved_by, o.approved_at = auth.user.id, now()
    await audit(db, request, "offboarding.approve", actor=auth.user, entity="offboarding", entity_id=o.id)
    await db.commit()
    return _off_out(o, emp, await _off_names(db, [o]))


class CompleteIn(BaseModel):
    leave_date: date
    note: str | None = Field(default=None, max_length=500)


@off_router.post("/{oid}/complete")
async def complete(oid: int, body: CompleteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Rasmiylashtirish: xodim bo'shatiladi, tizim dostupi yopiladi, kadrovik va HR ga xabar. Exit-intervyu shart."""
    _need(auth, "retention.manage")
    if not svc.has(auth, "employees.dismiss"):
        raise error(403, "forbidden")
    o, emp = await _off_ctx(db, oid, auth, lock=True)
    if o.status != "open":
        raise error(409, "already_decided")
    if o.exit_at is None:
        raise error(409, "exit_required")
    reason = {"fired": "discipline", "other": "other"}.get(o.reason_type or "", "own_will")
    await dismiss_one(db, emp, DismissIn(date=body.leave_date, reason=reason, note=(body.note or o.reason_text or "")[:500], block_account=True), auth)
    o.status, o.leave_date, o.completed_by, o.completed_at, o.access_closed = "completed", body.leave_date, auth.user.id, now(), True
    targets = {u for u in [*await users_with_permission(db, "employees.documents"), *await users_with_permission(db, "retention.read")] if u != auth.user.id}
    notes = await notify(db, list(targets), "offboarding.done", link=f"/offboarding/{o.id}", params={"employee": emp.full_name})
    await audit(db, request, "offboarding.complete", actor=auth.user, entity="offboarding", entity_id=o.id, data={"employee_id": emp.id, "date": str(body.leave_date)})
    await db.commit()
    await request.app.state.events.emit("employee.dismissed", employee_id=emp.id, full_name=emp.full_name, date=body.leave_date, reason=reason)
    await deliver(request.app, notes)
    return _off_out(o, emp, await _off_names(db, [o]))


# --- Nazorat paneli -----------------------------------------------------------------------


@control_router.get("/overview")
async def overview(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "control.read")
    out = await svc.control_overview(db, now())
    cfg = await svc.growth.get_setting(db, "retention")
    last = await db.scalar(select(func.max(RetentionMeeting.held_on)))
    out["meeting"] = {"last": last, "due": svc.meeting_due(last, local_date(now()), int(cfg["meeting_gap_days"]))}
    return out
