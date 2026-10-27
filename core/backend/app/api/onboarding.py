"""Preboarding (7 kun: kunlik hisobot, fidbek, qaror), oflayn darslar va kadrovik (hujjat/buyruq)."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.internship import (
    ClassAttendee,
    ClassSession,
    HireDocs,
    InternshipDaily,
    InternshipEnrollment,
    InternshipFeedback,
    InternshipProgram,
)
from app.models.org import Branch, Position
from app.services import internship as svc
from app.services import onboarding as osvc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_dt_fmt, now, tz

router = APIRouter(prefix="/v1/internship", tags=["onboarding"])
kadr_router = APIRouter(prefix="/v1/kadr", tags=["kadr"])


async def _enr(db: AsyncSession, eid: int, auth: AuthContext, *, lock: bool = False) -> tuple[InternshipEnrollment, Employee | None]:
    stmt = select(InternshipEnrollment).where(InternshipEnrollment.id == eid)
    e = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, e.employee_id) if e else None
    branch = await osvc.branch_of(db, emp)
    seen = e and (svc.can_view(auth, e, emp) or (branch and auth.user.id in (branch.manager_user_id, branch.coordinator_user_id)))
    if not e or not seen:
        raise error(404, "not_found")
    return e, emp


def _role_for(auth: AuthContext, e: InternshipEnrollment, branch: Branch | None) -> str | None:
    if svc.is_mentor(auth, e):
        return "trainer"
    if branch and auth.user.id in (branch.manager_user_id, branch.coordinator_user_id):
        return "zav"
    if svc.can_manage(auth):
        return "hr"
    return None


# --- 7 kunlik preboarding -----------------------------------------------------------------


class DailyIn(BaseModel):
    seen: str | None = Field(default=None, max_length=2000)
    understood: str | None = Field(default=None, max_length=2000)
    done: str | None = Field(default=None, max_length=2000)


@router.get("/enrollments/{eid}/daily")
async def daily(eid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    e, emp = await _enr(db, eid, auth)
    branch = await osvc.branch_of(db, emp)
    rows = {d.day_no: d for d in (await db.scalars(select(InternshipDaily).where(InternshipDaily.enrollment_id == e.id))).all()}
    fb = list((await db.scalars(select(InternshipFeedback).where(InternshipFeedback.enrollment_id == e.id).order_by(InternshipFeedback.id))).all())
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({f.author_id for f in fb if f.author_id})))).all()} if fb else {}
    today = osvc.day_no(e.started_at, now())
    days = []
    if e.phase == "preboarding":
        for n in range(1, osvc.DAYS + 1):
            d = rows.get(n)
            days.append({
                "day_no": n, "seen": d.seen if d else None, "understood": d.understood if d else None, "done": d.done if d else None, "open": n <= today,
                "feedback": [{"id": f.id, "role": f.role, "text": f.text, "author": names.get(f.author_id or 0), "created_at": f.created_at} for f in fb if f.day_no == n],
            })  # fmt: skip
    live = e.status in ("active", "ready")
    return {
        "phase": e.phase, "today": today, "days": days,
        "decision": {"value": e.day7_decision, "note": e.day7_note, "at": e.day7_at, "next_enrollment_id": e.next_enrollment_id},
        "can": {
            "report": e.phase == "preboarding" and live and svc.is_intern(auth, emp), "feedback": e.phase == "preboarding" and _role_for(auth, e, branch) is not None,
            "decide": e.phase == "preboarding" and svc.can_manage(auth) and e.day7_decision is None and e.status != "cancelled", "package": svc.can_manage(auth),
        },
    }  # fmt: skip


@router.put("/enrollments/{eid}/daily/{day}")
async def save_daily(eid: int, day: int, body: DailyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    e, emp = await _enr(db, eid, auth, lock=True)
    if not svc.is_intern(auth, emp):
        raise error(403, "forbidden")
    if e.phase != "preboarding" or e.status not in ("active", "ready"):
        raise error(409, "invalid_transition")
    if not 1 <= day <= osvc.DAYS or day > osvc.day_no(e.started_at, now()):
        raise error(400, "day_invalid")
    d = await db.scalar(select(InternshipDaily).where(InternshipDaily.enrollment_id == e.id, InternshipDaily.day_no == day))
    if d is None:
        d = InternshipDaily(enrollment_id=e.id, day_no=day)
        db.add(d)
    d.seen, d.understood, d.done = (body.seen or "").strip() or None, (body.understood or "").strip() or None, (body.done or "").strip() or None
    branch = await osvc.branch_of(db, emp)
    await audit(db, request, "internship.daily", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"day": day})
    await db.commit()
    return {"ok": True, "branch": branch.name if branch else None}


class FeedbackIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


@router.post("/enrollments/{eid}/daily/{day}/feedback", status_code=201)
async def add_feedback(eid: int, day: int, body: FeedbackIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    e, emp = await _enr(db, eid, auth)
    role = _role_for(auth, e, await osvc.branch_of(db, emp))
    if role is None or e.phase != "preboarding":
        raise error(403, "forbidden")
    if not 1 <= day <= osvc.DAYS:
        raise error(400, "day_invalid")
    db.add(InternshipFeedback(enrollment_id=e.id, day_no=day, author_id=auth.user.id, role=role, text=body.text.strip()))
    notes = await notify(db, [emp.user_id] if emp and emp.user_id and emp.user_id != auth.user.id else [], "internship.package", params={"text": f"Fidbek ({day}-kun): {body.text.strip()}"}, link=f"/internship/enrollments/{e.id}") if emp else []
    await audit(db, request, "internship.feedback", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"day": day, "role": role})
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True, "role": role}


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(fit|not_fit)$")
    note: str | None = Field(default=None, max_length=1000)
    program_id: int | None = None


@router.post("/enrollments/{eid}/decision")
async def decide(eid: int, body: DecisionIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """7-kun qarori (HR menejer/trener): mos -> lavozim bo'yicha onboarding avtomatik ochiladi; mos emas -> stajirovka bekor."""
    if not svc.can_manage(auth):
        raise error(403, "forbidden")
    e, emp = await _enr(db, eid, auth, lock=True)
    if e.phase != "preboarding" or e.status == "cancelled":
        raise error(409, "invalid_transition")
    if e.day7_decision:
        raise error(409, "already_decided")
    note = (body.note or "").strip() or None
    if body.decision == "not_fit" and not note:
        raise error(400, "note_required")
    moment = now()
    e.day7_decision, e.day7_note, e.day7_by, e.day7_at = body.decision, note, auth.user.id, moment
    notes: list = []
    nxt = None
    if body.decision == "fit":
        if e.status != "completed":
            e.status, e.completed_at, e.completed_by = "completed", moment, auth.user.id
        program = await db.get(InternshipProgram, body.program_id) if body.program_id else None
        if body.program_id and (program is None or program.phase != "onboarding" or not program.is_active):
            raise error(400, "program_invalid")
        if emp:
            nxt, notes = await osvc.start_onboarding(db, e, emp, auth.user.id, moment, program)
    else:
        e.status = "cancelled"
    branch = await osvc.branch_of(db, emp)
    targets = {u for u in (emp.user_id if emp else None, e.mentor_id, branch.manager_user_id if branch else None, branch.coordinator_user_id if branch else None) if u and u != auth.user.id}
    if targets:
        notes += await notify(db, list(targets), "internship.decision", link=f"/internship/enrollments/{e.id}", params={"intern": emp.full_name if emp else "", "result": "mos" if body.decision == "fit" else "mos emas", "note": note or ""})
    await audit(db, request, "internship.decision", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"decision": body.decision, "onboarding": nxt.id if nxt else None}, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return {"decision": body.decision, "next_enrollment_id": nxt.id if nxt else None, "onboarding_program_missing": body.decision == "fit" and nxt is None}


@router.post("/enrollments/{eid}/package")
async def resend_package(eid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.can_manage(auth):
        raise error(403, "forbidden")
    e, _ = await _enr(db, eid, auth)
    notes = await osvc.send_package(db, e)
    await audit(db, request, "internship.package", actor=auth.user, entity="internship_enrollment", entity_id=e.id)
    await db.commit()
    await deliver(request.app, notes)
    return {"sent": len(notes)}


# --- Oflayn darslar -----------------------------------------------------------------------


class ClassIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: str = Field(default="lesson", pattern="^(lesson|practice)$")
    starts_at: datetime
    place: str | None = Field(default=None, max_length=200)
    trainer_id: int | None = None
    employee_ids: list[int] = Field(min_length=1, max_length=80)


def _class_out(c: ClassSession, att: list[tuple[ClassAttendee, Employee]], trainer: str | None) -> dict[str, Any]:
    return {
        "id": c.id, "title": c.title, "kind": c.kind, "starts_at": c.starts_at, "place": c.place, "trainer": {"id": c.trainer_id, "name": trainer} if c.trainer_id else None,
        "attendance_marked_at": c.attendance_marked_at, "count": len(att), "present": sum(1 for a, _ in att if a.present),
        "attendees": [{"employee_id": e.id, "name": e.full_name, "present": a.present} for a, e in att],
    }  # fmt: skip


async def _attendees(db: AsyncSession, cid: int) -> list[tuple[ClassAttendee, Employee]]:
    return [(a, e) for a, e in (await db.execute(select(ClassAttendee, Employee).join(Employee, Employee.id == ClassAttendee.employee_id).where(ClassAttendee.session_id == cid).order_by(Employee.full_name))).all()]


@router.post("/classes", status_code=201)
async def create_class(body: ClassIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.can_manage(auth):
        raise error(403, "forbidden")
    ids = list(dict.fromkeys(body.employee_ids))
    emps = list((await db.scalars(select(Employee).where(Employee.id.in_(ids), Employee.status == "active"))).all())
    if len(emps) != len(ids):
        raise error(400, "unknown_employee")
    if body.trainer_id is not None and body.trainer_id not in set(await users_with_permission(db, "internship.own")) | set(await users_with_permission(db, "internship.manage")):
        raise error(400, "unknown_mentor")
    when = body.starts_at if body.starts_at.tzinfo else body.starts_at.replace(tzinfo=tz())
    c = ClassSession(title=body.title.strip(), kind=body.kind, starts_at=when, place=(body.place or "").strip() or None, trainer_id=body.trainer_id, created_by=auth.user.id)
    db.add(c)
    await db.flush()
    for e in emps:
        db.add(ClassAttendee(session_id=c.id, employee_id=e.id))
    branches = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_({e.branch_id for e in emps if e.branch_id})))).all()} if any(e.branch_id for e in emps) else {}
    targets = {u for e in emps for u in (e.user_id, branches[e.branch_id].manager_user_id if e.branch_id in branches else None) if u} | ({c.trainer_id} if c.trainer_id else set())
    notes = await notify(db, list(targets - {auth.user.id}), "class.invite", link=f"/internship/classes/{c.id}", params={"title": c.title, "when": local_dt_fmt(when), "place": c.place or "—"})
    await audit(db, request, "internship.class_create", actor=auth.user, entity="class_session", entity_id=c.id, data={"attendees": len(emps)})
    await db.commit()
    await deliver(request.app, notes)
    return _class_out(c, await _attendees(db, c.id), None)


@router.get("/classes")
async def list_classes(scope: str = Query(default="upcoming", pattern="^(upcoming|past)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    stmt = select(ClassSession)
    if not svc.sees_all(auth):
        mine = select(ClassAttendee.session_id).join(Employee, Employee.id == ClassAttendee.employee_id).where(Employee.user_id == auth.user.id)
        stmt = stmt.where((ClassSession.trainer_id == auth.user.id) | ClassSession.id.in_(mine))
    cutoff = now() - timedelta(hours=3)
    stmt = stmt.where(ClassSession.starts_at >= cutoff).order_by(ClassSession.starts_at) if scope == "upcoming" else stmt.where(ClassSession.starts_at < cutoff).order_by(ClassSession.starts_at.desc()).limit(100)
    rows = list((await db.scalars(stmt)).all())
    tnames = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({c.trainer_id for c in rows if c.trainer_id})))).all()} if rows else {}
    out = []
    for c in rows:
        out.append(_class_out(c, await _attendees(db, c.id), tnames.get(c.trainer_id or 0)))
    return out


async def _class(db: AsyncSession, cid: int, auth: AuthContext) -> ClassSession:
    c = await db.get(ClassSession, cid)
    if not c:
        raise error(404, "not_found")
    if not (svc.sees_all(auth) or c.trainer_id == auth.user.id or any(e.user_id == auth.user.id for _, e in await _attendees(db, cid))):
        raise error(404, "not_found")
    return c


@router.get("/classes/{cid}")
async def get_class(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    c = await _class(db, cid, auth)
    t = await db.get(User, c.trainer_id) if c.trainer_id else None
    out = _class_out(c, await _attendees(db, cid), t.full_name if t else None)
    out["can_mark"] = svc.can_manage(auth) or c.trainer_id == auth.user.id
    return out


class MarksIn(BaseModel):
    marks: list[dict[str, Any]] = Field(min_length=1, max_length=120)


@router.post("/classes/{cid}/attendance")
async def mark_attendance(cid: int, body: MarksIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Qatnashuv: kelmaganlar haqida mudir va trenerga xabar boradi."""
    c = await _class(db, cid, auth)
    if not (svc.can_manage(auth) or c.trainer_id == auth.user.id):
        raise error(403, "forbidden")
    att = {e.id: (a, e) for a, e in await _attendees(db, cid)}
    absent: list[Employee] = []
    for m in body.marks:
        eid, present = m.get("employee_id"), m.get("present")
        if eid not in att or not isinstance(present, bool):
            raise error(400, "marks_invalid")
        a, e = att[eid]
        if a.present is not False and present is False:
            absent.append(e)
        a.present = present
    c.attendance_marked_at = now()
    branches = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_({e.branch_id for e in absent if e.branch_id})))).all()} if absent else {}
    notes: list = []
    for e in absent:
        b = branches.get(e.branch_id or 0)
        targets = {u for u in (b.manager_user_id if b else None, c.trainer_id) if u and u != auth.user.id}
        if targets:
            notes += await notify(db, list(targets), "class.absent", link=f"/internship/classes/{c.id}", params={"intern": e.full_name, "title": c.title, "when": local_dt_fmt(c.starts_at)})
    await audit(db, request, "internship.class_attendance", actor=auth.user, entity="class_session", entity_id=c.id, data={"absent": len(absent)})
    await db.commit()
    await deliver(request.app, notes)
    return {"absent": len(absent)}


@router.delete("/classes/{cid}", status_code=204)
async def delete_class(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.can_manage(auth):
        raise error(403, "forbidden")
    c = await db.get(ClassSession, cid)
    if not c:
        raise error(404, "not_found")
    await db.delete(c)
    await db.commit()


# --- Kadrovik -----------------------------------------------------------------------------


def _kadr_guard(auth: AuthContext) -> None:
    if not svc.has(auth, "employees.documents"):
        raise error(403, "forbidden")


@kadr_router.get("")
async def kadr_list(days: int = Query(default=60, ge=1, le=365), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Yaqinda ishga olingan xodimlar: hujjat va buyruq holati."""
    _kadr_guard(auth)
    since = date.today() - timedelta(days=days)
    rows = (await db.execute(select(Employee, HireDocs).join(HireDocs, HireDocs.employee_id == Employee.id, isouter=True).where(Employee.status == "active", Employee.hire_date >= since).order_by(Employee.hire_date.desc()))).all()
    pos = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    br = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    return [
        {
            "employee_id": e.id, "name": e.full_name, "position": pos.get(e.position_id or 0), "branch": br.get(e.branch_id or 0), "hire_date": e.hire_date,
            "status": osvc.kadr_status(d), "docs_received_at": d.docs_received_at if d else None, "docs_note": d.docs_note if d else None,
            "order_ready_at": d.order_ready_at if d else None, "order_no": d.order_no if d else None,
        }  # fmt: skip
        for e, d in rows
    ]


async def _kadr_notify(db: AsyncSession, emp: Employee, actor_id: int, kind: str, params: dict[str, Any]) -> list:
    branch = await osvc.branch_of(db, emp)
    targets = {u for u in (emp.user_id, branch.manager_user_id if branch else None, *await users_with_permission(db, "recruit.approve")) if u and u != actor_id}
    return await notify(db, list(targets), kind, link=f"/employees/{emp.id}", params=params) if targets else []


async def _docs(db: AsyncSession, eid: int) -> tuple[Employee, HireDocs]:
    emp = await db.get(Employee, eid)
    if not emp:
        raise error(404, "not_found")
    d = await db.scalar(select(HireDocs).where(HireDocs.employee_id == eid))
    if d is None:
        d = HireDocs(employee_id=eid)
        db.add(d)
        await db.flush()
    return emp, d


class DocsIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@kadr_router.post("/{employee_id}/docs")
async def docs_received(employee_id: int, body: DocsIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _kadr_guard(auth)
    emp, d = await _docs(db, employee_id)
    if d.docs_received_at:
        raise error(409, "already_decided")
    d.docs_received_at, d.docs_received_by, d.docs_note = now(), auth.user.id, (body.note or "").strip() or None
    notes = await _kadr_notify(db, emp, auth.user.id, "kadr.docs", {"employee": emp.full_name})
    await audit(db, request, "kadr.docs", actor=auth.user, entity="employee", entity_id=emp.id)
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True}


class OrderIn(BaseModel):
    order_no: str | None = Field(default=None, max_length=40)


@kadr_router.post("/{employee_id}/order")
async def order_ready(employee_id: int, body: OrderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _kadr_guard(auth)
    emp, d = await _docs(db, employee_id)
    if not d.docs_received_at:
        raise error(409, "docs_required")
    if d.order_ready_at:
        raise error(409, "already_decided")
    d.order_ready_at, d.order_ready_by, d.order_no = now(), auth.user.id, (body.order_no or "").strip() or None
    notes = await _kadr_notify(db, emp, auth.user.id, "kadr.order", {"employee": emp.full_name, "order": f"№{d.order_no}" if d.order_no else ""})
    await audit(db, request, "kadr.order", actor=auth.user, entity="employee", entity_id=emp.id, data={"order_no": d.order_no})
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True}

