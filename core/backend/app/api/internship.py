"""Stajirovka: dasturlar va bosqichlar, biriktirish, stajyor yo'li (progress), testlar, tasdiqlash."""

from datetime import date, timedelta
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
from app.models.employees import Employee
from app.models.internship import (
    InternshipEnrollment,
    InternshipProgram,
    InternshipProgress,
    InternshipStep,
)
from app.services import internship as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/internship", tags=["internship"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("internship.own", "internship.read", "internship.manage")
Manager = require_any("internship.manage")


# --- Dasturlar ----------------------------------------------------------------------------


class ProgramIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    pass_score: int = Field(default=70, ge=1, le=100)
    sequential: bool = True
    is_active: bool = True
    phase: str = Field(default="preboarding", pattern="^(preboarding|onboarding)$")
    position_id: int | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)


def _program_out(p: InternshipProgram, steps: int = 0, enrolled: int = 0) -> dict[str, Any]:
    return {"id": p.id, "name": p.name, "description": p.description, "pass_score": p.pass_score, "sequential": p.sequential, "is_active": p.is_active, "steps": steps, "enrolled": enrolled, "phase": p.phase, "position_id": p.position_id, "duration_days": p.duration_days}


async def _program(db: AsyncSession, pid: int) -> InternshipProgram:
    p = await db.get(InternshipProgram, pid)
    if not p:
        raise error(404, "not_found")
    return p


@router.get("/programs")
async def programs(all: bool = False, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    stmt = select(InternshipProgram).order_by(InternshipProgram.name)
    if not (all and svc.sees_all(auth)):
        stmt = stmt.where(InternshipProgram.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    sc = dict((await db.execute(select(InternshipStep.program_id, func.count()).group_by(InternshipStep.program_id))).all())
    ec = dict((await db.execute(select(InternshipEnrollment.program_id, func.count()).group_by(InternshipEnrollment.program_id))).all())
    return [_program_out(p, sc.get(p.id, 0), ec.get(p.id, 0)) for p in rows]


@router.post("/programs", status_code=201)
async def create_program(body: ProgramIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = InternshipProgram(**{**body.model_dump(), "name": body.name.strip(), "description": (body.description or "").strip() or None})
    db.add(p)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "program_exists") from None
    await audit(db, request, "internship.program_create", actor=auth.user, entity="internship_program", entity_id=p.id, data={"name": p.name})
    await db.commit()
    return _program_out(p)


@router.get("/programs/{pid}")
async def program(pid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    p = await _program(db, pid)
    steps = await svc.steps_of(db, p.id)
    reveal = svc.can_manage(auth)
    return {**_program_out(p, len(steps)), "steps_list": [svc.step_out(s, reveal=reveal) for s in steps]}


@router.put("/programs/{pid}")
async def update_program(pid: int, body: ProgramIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = await _program(db, pid)
    for k, v in {**body.model_dump(), "name": body.name.strip(), "description": (body.description or "").strip() or None}.items():
        setattr(p, k, v)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "program_exists") from None
    await audit(db, request, "internship.program_update", actor=auth.user, entity="internship_program", entity_id=p.id, data={"name": p.name})
    await db.commit()
    return _program_out(p)


@router.delete("/programs/{pid}", status_code=204)
async def delete_program(pid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = await _program(db, pid)
    if await db.scalar(select(func.count()).select_from(InternshipEnrollment).where(InternshipEnrollment.program_id == p.id)):
        raise error(409, "program_in_use")
    keys = [s.file_key for s in await svc.steps_of(db, p.id) if s.file_key]
    await audit(db, request, "internship.program_delete", actor=auth.user, entity="internship_program", entity_id=p.id, data={"name": p.name})
    await db.delete(p)
    await db.commit()
    for k in keys:
        await request.app.state.storage.delete(k)


# --- Bosqichlar ---------------------------------------------------------------------------


class QuestionIn(BaseModel):
    id: str | None = Field(default=None, max_length=16)
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    correct: list[int] = Field(min_length=1)


class StepIn(BaseModel):
    kind: str = Field(pattern="^(video|document|text|test)$")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    url: str | None = Field(default=None, max_length=500)
    questions: list[QuestionIn] = []
    pass_score: int | None = Field(default=None, ge=1, le=100)
    max_attempts: int = Field(default=3, ge=0, le=20)
    required: bool = True


def _check_step(b: StepIn) -> dict[str, Any]:
    url = (b.url or "").strip() or None
    if url and not url.lower().startswith(("http://", "https://")):
        raise error(400, "url_invalid")
    if b.kind == "video" and not url:
        raise error(400, "url_required")
    qs = svc.clean_questions([q.model_dump() for q in b.questions]) if b.kind == "test" else []
    if b.kind == "test" and not qs:
        raise error(400, "questions_invalid")
    return {"kind": b.kind, "title": b.title.strip(), "description": (b.description or "").strip() or None, "url": url, "questions": qs, "pass_score": b.pass_score if b.kind == "test" else None, "max_attempts": b.max_attempts, "required": b.required}


async def _step(db: AsyncSession, sid: int) -> InternshipStep:
    s = await db.get(InternshipStep, sid)
    if not s:
        raise error(404, "not_found")
    return s


@router.post("/programs/{pid}/steps", status_code=201)
async def create_step(pid: int, body: StepIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = await _program(db, pid)
    last = await db.scalar(select(func.max(InternshipStep.position)).where(InternshipStep.program_id == p.id))
    s = InternshipStep(program_id=p.id, position=(last if last is not None else -1) + 1, **_check_step(body))
    db.add(s)
    await db.flush()
    await audit(db, request, "internship.step_create", actor=auth.user, entity="internship_step", entity_id=s.id, data={"program_id": p.id, "title": s.title, "kind": s.kind})
    await db.commit()
    return svc.step_out(s, reveal=True)


@router.get("/steps/{sid}")
async def step(sid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    s = await _step(db, sid)
    if not svc.sees_all(auth) and not await _enrolled_in(db, auth, s.program_id):
        raise error(404, "not_found")
    return svc.step_out(s, reveal=svc.can_manage(auth))


async def _enrolled_in(db: AsyncSession, auth: AuthContext, program_id: int) -> bool:
    stmt = select(InternshipEnrollment.id).join(Employee, Employee.id == InternshipEnrollment.employee_id).where(
        InternshipEnrollment.program_id == program_id, or_(Employee.user_id == auth.user.id, InternshipEnrollment.mentor_id == auth.user.id)
    )  # fmt: skip
    return bool(await db.scalar(stmt.limit(1)))


@router.put("/steps/{sid}")
async def update_step(sid: int, body: StepIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s = await _step(db, sid)
    for k, v in _check_step(body).items():
        setattr(s, k, v)
    await audit(db, request, "internship.step_update", actor=auth.user, entity="internship_step", entity_id=s.id, data={"title": s.title})
    await db.commit()
    return svc.step_out(s, reveal=True)


@router.delete("/steps/{sid}", status_code=204)
async def delete_step(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s = await _step(db, sid)
    key = s.file_key
    await audit(db, request, "internship.step_delete", actor=auth.user, entity="internship_step", entity_id=s.id, data={"title": s.title})
    await db.delete(s)
    await db.commit()
    if key:
        await request.app.state.storage.delete(key)


class OrderIn(BaseModel):
    ids: list[int]


@router.put("/programs/{pid}/order")
async def reorder(pid: int, body: OrderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    steps = await svc.steps_of(db, pid)
    if sorted(body.ids) != sorted(s.id for s in steps):
        raise error(400, "order_invalid")
    by_id = {s.id: s for s in steps}
    for i, sid in enumerate(body.ids):
        by_id[sid].position = i
    await audit(db, request, "internship.reorder", actor=auth.user, entity="internship_program", entity_id=pid)
    await db.commit()
    return {"ok": True}


@router.post("/steps/{sid}/file", status_code=201)
async def upload_step_file(sid: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s = await _step(db, sid)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"internship/{s.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    old = s.file_key
    s.file_key, s.file_name, s.file_mime, s.file_size = key, up.filename, up.mime, len(up.data)
    await db.commit()
    if old:
        await request.app.state.storage.delete(old)
    return svc.step_out(s, reveal=True)


@router.get("/steps/{sid}/file")
async def download_step_file(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    s = await _step(db, sid)
    if not s.file_key or (not svc.sees_all(auth) and not await _enrolled_in(db, auth, s.program_id)):
        raise error(404, "not_found")
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"inline; filename*=UTF-8''{quote(s.file_name or 'file')}"}
    return StreamingResponse(request.app.state.storage.stream(s.file_key), media_type=s.file_mime or "application/octet-stream", headers=headers)


@router.delete("/steps/{sid}/file", status_code=204)
async def delete_step_file(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s = await _step(db, sid)
    key = s.file_key
    s.file_key = s.file_name = s.file_mime = s.file_size = None
    await db.commit()
    if key:
        await request.app.state.storage.delete(key)


# --- Biriktirish (enrollment) -------------------------------------------------------------


@router.get("/employees")
async def employees(q: str = Query(min_length=2), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    stmt = select(Employee).where(Employee.status == "active", Employee.full_name.ilike(f"%{q.strip()}%")).order_by(Employee.full_name).limit(15)
    return [{"id": e.id, "name": e.full_name, "phone": e.phone, "has_account": e.user_id is not None} for e in (await db.scalars(stmt)).all()]


@router.get("/mentors")
async def mentors(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    ids = await users_with_permission(db, "internship.own")
    if not ids:
        return []
    rows = (await db.execute(select(User.id, User.full_name).where(User.is_active.is_(True), User.id.in_(ids)).order_by(User.full_name))).all()
    return [{"id": r.id, "name": r.full_name} for r in rows]


class EnrollIn(BaseModel):
    program_id: int
    employee_id: int
    mentor_id: int | None = None
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)


async def _enrollment(db: AsyncSession, eid: int, auth: AuthContext, *, lock: bool = False) -> tuple[InternshipEnrollment, Employee | None]:
    stmt = select(InternshipEnrollment).where(InternshipEnrollment.id == eid)
    e = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, e.employee_id) if e else None
    if not e or not svc.can_view(auth, e, emp):
        raise error(404, "not_found")
    return e, emp


async def _rows_out(db: AsyncSession, rows: list[InternshipEnrollment]) -> list[dict[str, Any]]:
    if not rows:
        return []
    emps = {e.id: e for e in (await db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows})))).all()}
    progs = {p.id: p for p in (await db.scalars(select(InternshipProgram).where(InternshipProgram.id.in_({r.program_id for r in rows})))).all()}
    mentors_ = await _names(db, {r.mentor_id for r in rows})
    out = []
    for r in rows:
        steps = await svc.steps_of(db, r.program_id)
        s = svc.summarize(steps, await svc.progress_of(db, r.id))
        emp = emps.get(r.employee_id)
        out.append({
            "id": r.id, "status": r.status, "phase": r.phase, "day7_decision": r.day7_decision, "started_at": r.started_at, "due_date": r.due_date, "ready_at": r.ready_at, "completed_at": r.completed_at, "final_score": r.final_score,
            "program": {"id": r.program_id, "name": progs[r.program_id].name}, "employee": {"id": r.employee_id, "name": emp.full_name if emp else None},
            "mentor": {"id": r.mentor_id, "name": mentors_.get(r.mentor_id or 0)} if r.mentor_id else None, "progress": s,
            "overdue": bool(r.due_date and r.status == "active" and r.due_date < now().date()),
        })  # fmt: skip
    return out


async def _names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()} if ids2 else {}


@router.post("/enrollments", status_code=201)
async def enroll(body: EnrollIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = await _program(db, body.program_id)
    if not p.is_active:
        raise error(400, "program_inactive")
    if not await db.scalar(select(func.count()).select_from(InternshipStep).where(InternshipStep.program_id == p.id, InternshipStep.required.is_(True))):
        raise error(409, "program_empty")
    emp = await db.get(Employee, body.employee_id)
    if not emp or emp.status != "active":
        raise error(400, "unknown_employee")
    if body.mentor_id is not None and body.mentor_id not in set(await users_with_permission(db, "internship.own")):
        raise error(400, "unknown_mentor")
    if await db.scalar(select(InternshipEnrollment.id).where(InternshipEnrollment.employee_id == emp.id, InternshipEnrollment.program_id == p.id, InternshipEnrollment.status.in_(("active", "ready")))):
        raise error(409, "already_enrolled")
    started = now()
    due = body.due_date or (started.date() + timedelta(days=p.duration_days) if p.duration_days else None)
    e = InternshipEnrollment(program_id=p.id, employee_id=emp.id, mentor_id=body.mentor_id, status="active", started_at=started, due_date=due, note=(body.note or "").strip() or None, created_by=auth.user.id, phase=p.phase)
    db.add(e)
    await db.flush()
    await audit(db, request, "internship.enroll", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"program_id": p.id, "employee_id": emp.id, "mentor_id": e.mentor_id})
    targets = [u for u in {emp.user_id, e.mentor_id} if u and u != auth.user.id]
    notes = await notify(db, targets, "internship.enrolled", link=f"/internship/enrollments/{e.id}", params={"program": p.name, "intern": emp.full_name})
    await db.commit()
    await deliver(request.app, notes)
    return (await _rows_out(db, [e]))[0]


@router.get("/enrollments")
async def enrollments(
    scope: str = Query(default="mine", pattern="^(mine|mentor|all)$"),
    status: str | None = Query(default=None, pattern="^(active|ready|completed|cancelled|open)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    E = InternshipEnrollment
    conds: list = []
    if scope == "mine":
        conds.append(E.employee_id.in_(select(Employee.id).where(Employee.user_id == auth.user.id)))
    elif scope == "mentor":
        conds.append(E.mentor_id == auth.user.id)
    elif not svc.sees_all(auth):
        raise error(403, "forbidden")
    if status == "open":
        conds.append(E.status.in_(("active", "ready")))
    elif status:
        conds.append(E.status == status)
    total = await db.scalar(select(func.count()).select_from(E).where(*conds)) or 0
    rows = (await db.scalars(select(E).where(*conds).order_by(E.started_at.desc(), E.id.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "page": page, "size": size, "items": await _rows_out(db, list(rows))}


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    E, uid = InternshipEnrollment, auth.user.id
    mine = await db.scalar(select(func.count()).select_from(E).where(E.status == "active", E.employee_id.in_(select(Employee.id).where(Employee.user_id == uid)))) or 0
    to_confirm_q = select(func.count()).select_from(E).where(E.status == "ready")
    if not svc.can_manage(auth):
        to_confirm_q = to_confirm_q.where(E.mentor_id == uid)
    return {"my_active": mine, "to_confirm": await db.scalar(to_confirm_q) or 0}


@router.get("/enrollments/{eid}")
async def enrollment(eid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    e, emp = await _enrollment(db, eid, auth)
    p = await _program(db, e.program_id)
    steps = await svc.steps_of(db, p.id)
    states = svc.step_states(p, steps, await svc.progress_of(db, e.id))
    base = (await _rows_out(db, [e]))[0]
    reveal = svc.can_manage(auth)
    return {
        **base, "note": e.note, "pass_score": p.pass_score, "sequential": p.sequential,
        "can": {"confirm": e.status == "ready" and svc.can_supervise(auth, e), "cancel": e.status in ("active", "ready") and svc.can_manage(auth), "reset": svc.can_supervise(auth, e) and e.status in ("active", "ready"), "learn": svc.is_intern(auth, emp) and e.status == "active"},
        "steps": [{**svc.step_out(x["step"], reveal=reveal), "state": x["state"], "score": x["score"], "attempts": x["attempts"], "completed_at": x["completed_at"]} for x in states],
    }  # fmt: skip


async def _learning_step(db: AsyncSession, eid: int, sid: int, auth: AuthContext):
    """Stajyorning o'zi o'qiydigan bosqich: faqat o'z faol stajirovkasi va ochiq (qulflanmagan) bosqich."""
    e, emp = await _enrollment(db, eid, auth, lock=True)
    if not svc.is_intern(auth, emp):
        raise error(403, "forbidden")
    if e.status != "active":
        raise error(409, "invalid_transition")
    p = await _program(db, e.program_id)
    steps = await svc.steps_of(db, p.id)
    state = next((x for x in svc.step_states(p, steps, await svc.progress_of(db, e.id)) if x["step"].id == sid), None)
    if state is None:
        raise error(404, "not_found")
    if state["state"] == "locked":
        raise error(409, "step_locked")
    return e, emp, p, state["step"], state


@router.post("/enrollments/{eid}/steps/{sid}/done")
async def mark_done(eid: int, sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    e, emp, p, s, _ = await _learning_step(db, eid, sid, auth)
    if s.kind == "test":
        raise error(400, "use_submit")
    moment = now()
    await svc.complete_step(db, e, s, moment)
    notes = await svc.check_ready(db, e, p, emp.full_name if emp else "", moment)
    await audit(db, request, "internship.step_done", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"step_id": s.id, "status": e.status})
    await db.commit()
    await deliver(request.app, notes)
    return await enrollment(eid, db, auth)


class SubmitIn(BaseModel):
    answers: dict[str, list[int]]


@router.post("/enrollments/{eid}/steps/{sid}/submit")
async def submit_test(eid: int, sid: int, body: SubmitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    e, emp, p, s, state = await _learning_step(db, eid, sid, auth)
    if s.kind != "test":
        raise error(400, "not_a_test")
    if state["state"] == "done":
        raise error(409, "already_done")
    if s.max_attempts and state["attempts"] >= s.max_attempts:
        raise error(409, "attempts_exhausted", max=s.max_attempts)
    score, wrong = svc.grade(s, body.answers)
    passed = score >= svc.threshold(s, p)
    moment = now()
    prog = await svc.complete_step(db, e, s, moment, score=score, done=passed)
    prog.attempts += 1
    notes = await svc.check_ready(db, e, p, emp.full_name if emp else "", moment) if passed else []
    await audit(db, request, "internship.test", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"step_id": s.id, "score": score, "passed": passed, "attempt": prog.attempts})
    await db.commit()
    await deliver(request.app, notes)
    left = max(s.max_attempts - prog.attempts, 0) if s.max_attempts else None
    return {"score": score, "passed": passed, "wrong": [] if passed else wrong, "threshold": svc.threshold(s, p), "attempts": prog.attempts, "attempts_left": left, "status": e.status}


@router.post("/enrollments/{eid}/steps/{sid}/reset")
async def reset_step(eid: int, sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Murabbiy/boshqaruvchi: bosqichni qayta ochadi (urinishlar nolga, bajarilgan belgisi olinadi)."""
    e, _ = await _enrollment(db, eid, auth, lock=True)
    if not svc.can_supervise(auth, e) or e.status not in ("active", "ready"):
        raise error(403, "forbidden")
    p = (await db.scalars(select(InternshipProgress).where(InternshipProgress.enrollment_id == e.id, InternshipProgress.step_id == sid))).first()
    if not p:
        raise error(404, "not_found")
    p.done, p.attempts, p.score, p.completed_at = False, 0, None, None
    if e.status == "ready":
        e.status, e.ready_at, e.final_score = "active", None, None
    await audit(db, request, "internship.reset", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"step_id": sid})
    await db.commit()
    return await enrollment(eid, db, auth)


class ConfirmIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.post("/enrollments/{eid}/confirm")
async def confirm(eid: int, body: ConfirmIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    e, emp = await _enrollment(db, eid, auth, lock=True)
    if not svc.can_supervise(auth, e):
        raise error(403, "forbidden")
    if e.status != "ready":
        raise error(409, "invalid_transition")
    e.status, e.completed_at, e.completed_by = "completed", now(), auth.user.id
    if body.note and body.note.strip():
        e.note = ((e.note + "\n") if e.note else "") + body.note.strip()
    p = await _program(db, e.program_id)
    await audit(db, request, "internship.confirm", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"employee_id": e.employee_id, "score": e.final_score})
    notes = await notify(db, [emp.user_id] if emp and emp.user_id and emp.user_id != auth.user.id else [], "internship.completed", link=f"/internship/enrollments/{e.id}", params={"program": p.name})
    await db.commit()
    await deliver(request.app, notes)
    return await enrollment(eid, db, auth)


@router.post("/enrollments/{eid}/cancel")
async def cancel(eid: int, body: ConfirmIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    e, _ = await _enrollment(db, eid, auth, lock=True)
    if e.status not in ("active", "ready"):
        raise error(409, "invalid_transition")
    e.status = "cancelled"
    if body.note and body.note.strip():
        e.note = ((e.note + "\n") if e.note else "") + body.note.strip()
    await audit(db, request, "internship.cancel", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"employee_id": e.employee_id})
    await db.commit()
    return await enrollment(eid, db, auth)
