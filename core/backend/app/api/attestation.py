"""Oylik attestatsiya: davrni ochish, ball, fidbek, HR qarori va hisobot."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.growth import Attestation, CareerLevel
from app.models.internship import InternshipEnrollment
from app.models.org import Branch
from app.rbac import matches
from app.services import growth as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/attestation", tags=["attestation"])


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "attestation.read") or has(auth, "attestation.manage")


async def _ctx(db: AsyncSession, a: Attestation) -> tuple[Employee, Branch | None, bool]:
    emp = await db.get(Employee, a.employee_id)
    branch = await db.get(Branch, emp.branch_id) if emp and emp.branch_id else None
    mentor = bool(emp and await db.scalar(select(InternshipEnrollment.id).where(InternshipEnrollment.employee_id == emp.id, InternshipEnrollment.mentor_id.is_not(None)).limit(1)))
    return emp, branch, mentor  # type: ignore[return-value]


async def _mentor_ids(db: AsyncSession, emp_id: int) -> set[int]:
    return {m for m in (await db.scalars(select(InternshipEnrollment.mentor_id).where(InternshipEnrollment.employee_id == emp_id))).all() if m}


def _role(auth: AuthContext, emp: Employee, branch: Branch | None, mentors: set[int]) -> str | None:
    if auth.user.id in mentors:
        return "trainer"
    if branch and auth.user.id == branch.manager_user_id:
        return "zav"
    if branch and auth.user.id == branch.coordinator_user_id:
        return "coordinator"
    if has(auth, "attestation.manage"):
        return "hr"
    return None


async def _load(db: AsyncSession, aid: int, auth: AuthContext, *, lock: bool = False) -> tuple[Attestation, Employee, Branch | None, set[int]]:
    stmt = select(Attestation).where(Attestation.id == aid)
    a = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, a.employee_id) if a else None
    if not a or not emp:
        raise error(404, "not_found")
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    mentors = await _mentor_ids(db, emp.id)
    own = emp.user_id == auth.user.id
    if not (own or sees_all(auth) or _role(auth, emp, branch, mentors)):
        raise error(404, "not_found")
    return a, emp, branch, mentors


def _out(a: Attestation, emp: Employee, branch: Branch | None, lv: CareerLevel | None, cfg: dict[str, Any], auth: AuthContext, mentors: set[int]) -> dict[str, Any]:
    role = _role(auth, emp, branch, mentors)
    live = a.status != "decided"
    return {
        "id": a.id, "month": a.month, "status": a.status, "employee": {"id": emp.id, "name": emp.full_name}, "branch": branch.name if branch else None,
        "level": lv.name if lv else None, "test_score": a.test_score, "practical_score": a.practical_score, "total": a.total, "pass_score": cfg["pass_score"],
        "passes": a.total is not None and a.total >= cfg["pass_score"], "feedbacks": a.feedbacks or [], "decision": a.decision, "decision_note": a.decision_note, "decided_at": a.decided_at,
        "can": {"score": live and (role in ("trainer", "hr")), "feedback": live and role is not None, "decide": live and has(auth, "attestation.manage")},
    }  # fmt: skip


@router.post("/cycles", status_code=201)
async def open_cycle(request: Request, month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR: oy attestatsiyasini ochadi (standart: joriy oy). Takroriy chaqiruv yangi qator yaratmaydi."""
    if not has(auth, "attestation.manage"):
        raise error(403, "forbidden")
    moment = now()
    created, notes = await svc.open_cycle(db, month or svc.month_of(local_date(moment)), moment)
    await audit(db, request, "attestation.open", actor=auth.user, entity="attestation", entity_id=0, data={"month": month, "created": created})
    await db.commit()
    await deliver(request.app, notes)
    return {"created": created}


@router.get("")
async def list_attestations(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    status: str | None = Query(default=None, pattern="^(open|scored|decided)$"),
    scope: str = Query(default="all", pattern="^(mine|all)$"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    stmt = select(Attestation, Employee).join(Employee, Employee.id == Attestation.employee_id)
    if scope == "mine":
        stmt = stmt.where(Employee.user_id == auth.user.id)
    elif not sees_all(auth):
        mine_branches = select(Branch.id).where((Branch.manager_user_id == auth.user.id) | (Branch.coordinator_user_id == auth.user.id))
        mentored = select(InternshipEnrollment.employee_id).where(InternshipEnrollment.mentor_id == auth.user.id)
        stmt = stmt.where((Employee.user_id == auth.user.id) | Employee.branch_id.in_(mine_branches) | Employee.id.in_(mentored))
    if month:
        stmt = stmt.where(Attestation.month == month)
    if status:
        stmt = stmt.where(Attestation.status == status)
    rows = (await db.execute(stmt.order_by(Attestation.month.desc(), Employee.full_name).limit(300))).all()
    cfg = await svc.get_setting(db, "attestation")
    lv = {x.id: x for x in await svc.levels(db, active_only=False)}
    br = {b.id: b for b in (await db.scalars(select(Branch))).all()}
    return [_out(a, e, br.get(e.branch_id or 0), lv.get(a.level_id or 0), cfg, auth, set()) for a, e in rows]


@router.get("/report")
async def report(month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HRD hisoboti: lavozim bo'yicha natijalar."""
    if not sees_all(auth):
        raise error(403, "forbidden")
    lv = {x.id: x.name for x in await svc.levels(db, active_only=False)}
    rows = (await db.execute(select(Attestation.level_id, Attestation.status, Attestation.decision, func.count(), func.avg(Attestation.total)).where(Attestation.month == month).group_by(Attestation.level_id, Attestation.status, Attestation.decision))).all()
    out: dict[int | None, dict[str, Any]] = {}
    for lid, st, dec, n, avg in rows:
        d = out.setdefault(lid, {"level": lv.get(lid or 0), "total": 0, "open": 0, "scored": 0, "passed": 0, "retake": 0, "extra_lessons": 0, "avg": None})
        d["total"] += n
        if st != "decided":
            d[st] += n
        elif dec:
            d[dec] += n
        if avg is not None:
            d["avg"] = round(float(avg), 1)
    return {"month": month, "levels": list(out.values())}


@router.get("/{aid}")
async def one(aid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    a, emp, branch, mentors = await _load(db, aid, auth)
    return _out(a, emp, branch, await db.get(CareerLevel, a.level_id) if a.level_id else None, await svc.get_setting(db, "attestation"), auth, mentors)


class ScoresIn(BaseModel):
    test_score: float | None = Field(default=None, ge=0, le=100)
    practical_score: float | None = Field(default=None, ge=0, le=100)


@router.post("/{aid}/scores")
async def set_scores(aid: int, body: ScoresIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    a, emp, branch, mentors = await _load(db, aid, auth, lock=True)
    if _role(auth, emp, branch, mentors) not in ("trainer", "hr"):
        raise error(403, "forbidden")
    if a.status == "decided":
        raise error(409, "already_decided")
    if body.test_score is None and body.practical_score is None:
        raise error(400, "scores_required")
    if body.test_score is not None:
        a.test_score = body.test_score
    if body.practical_score is not None:
        a.practical_score = body.practical_score
    cfg = await svc.get_setting(db, "attestation")
    a.total, a.status = svc.total_score(a.test_score, a.practical_score, cfg), "scored"
    await audit(db, request, "attestation.scores", actor=auth.user, entity="attestation", entity_id=a.id, data={"total": a.total})
    await db.commit()
    return _out(a, emp, branch, await db.get(CareerLevel, a.level_id) if a.level_id else None, cfg, auth, mentors)


class FeedbackIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


@router.post("/{aid}/feedback", status_code=201)
async def add_feedback(aid: int, body: FeedbackIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    a, emp, branch, mentors = await _load(db, aid, auth, lock=True)
    role = _role(auth, emp, branch, mentors)
    if role is None or a.status == "decided":
        raise error(403, "forbidden")
    a.feedbacks = [*(a.feedbacks or []), {"role": role, "author": auth.user.full_name, "text": body.text.strip(), "at": now().isoformat()}]
    await audit(db, request, "attestation.feedback", actor=auth.user, entity="attestation", entity_id=a.id, data={"role": role})
    await db.commit()
    return {"ok": True, "role": role}


class DecideIn(BaseModel):
    decision: str = Field(pattern=f"^({svc.DECISIONS})$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/{aid}/decide")
async def decide(aid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR qarori: o'tdi / qayta topshiradi / qo'shimcha dars. Natija xodim, HR va HRD ga yetkaziladi; «o'tdi» ketma-ket bo'lsa o'sish taklifi yaratiladi."""
    if not has(auth, "attestation.manage"):
        raise error(403, "forbidden")
    a, emp, branch, mentors = await _load(db, aid, auth, lock=True)
    if a.status == "decided":
        raise error(409, "already_decided")
    if a.total is None:
        raise error(409, "scores_required")
    cfg = await svc.get_setting(db, "attestation")
    note = (body.note or "").strip() or None
    if body.decision == "passed" and a.total < cfg["pass_score"] and not note:
        raise error(400, "note_required")  # mezondan past bo'lsa, istisno sababi shart
    moment = now()
    a.decision, a.decision_note, a.decided_by, a.decided_at, a.status = body.decision, note, auth.user.id, moment, "decided"
    notes = await notify(db, [u for u in {emp.user_id} if u], "attestation.decided", params={"employee": emp.full_name, "result": svc.RESULT_UZ[body.decision], "note": note or ""}, link="/attestation")
    if body.decision == "passed":
        _, pn = await svc.maybe_propose(db, emp, moment)
        notes += pn
    await audit(db, request, "attestation.decide", actor=auth.user, entity="attestation", entity_id=a.id, data={"decision": body.decision, "total": a.total}, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return _out(a, emp, branch, await db.get(CareerLevel, a.level_id) if a.level_id else None, cfg, auth, mentors)

