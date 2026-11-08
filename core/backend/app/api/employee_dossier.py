"""Xodimning "shaxsiy ishi" (dosye): ishga qabuldagi barcha hujjat va ma'lumotlar bitta joyda — rezyume/anketa,
qaysi e'lon va havola orqali kelgani, zayafka, suhbat natijalari, testlar, mehnat shartnomasi, buyruqlar,
staj va oyma-oy ish haqi."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.auth import User
from app.models.employees import Employee, EmployeeDocument
from app.models.hrdocs import StaffDocument
from app.models.org import Branch, Department, Position
from app.models.payroll import PayrollLine, PayrollRun
from app.models.recruit import (
    Application,
    Candidate,
    CandidateFile,
    CandidateTest,
    HireRequest,
    InterviewScore,
    SourceLink,
    Vacancy,
)
from app.rbac import matches
from app.services import recruit_core as core
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/employees", tags=["employees"])


def tenure(start: date | None, end: date | None) -> dict[str, int] | None:
    """Ishga kirgan kundan (yoki bo'shagan kungacha) to'liq yil va oy, jami kun."""
    if not start:
        return None
    end = end or local_date(now())
    months = max(
        0,
        (end.year - start.year) * 12
        + (end.month - start.month)
        - (1 if end.day < start.day else 0),
    )
    return {"years": months // 12, "months": months % 12, "total_days": max(0, (end - start).days)}


async def _recruitment(db: AsyncSession, emp_id: int) -> dict[str, Any] | None:
    a = await db.scalar(
        select(Application)
        .where(Application.employee_id == emp_id)
        .order_by(Application.id.desc())
        .limit(1)
    )
    if not a:
        return None
    c = await db.get(Candidate, a.candidate_id)
    v = await db.get(Vacancy, a.vacancy_id)
    link = await db.get(SourceLink, a.source_link_id) if a.source_link_id else None
    req = (
        await db.scalar(select(HireRequest).where(HireRequest.vacancy_id == a.vacancy_id))
        if v
        else None
    )
    files = (
        await db.scalars(
            select(CandidateFile)
            .where(CandidateFile.candidate_id == a.candidate_id)
            .order_by(CandidateFile.id)
        )
    ).all()
    tests = (
        await db.scalars(select(CandidateTest).where(CandidateTest.application_id == a.id))
    ).all()
    scores = (
        await db.scalars(select(InterviewScore).where(InterviewScore.application_id == a.id))
    ).all()
    uid = {x for x in (a.recruiter_id, *(s.interviewer_id for s in scores)) if x}
    names = (
        {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(uid)))).all()}
        if uid
        else {}
    )
    prof = (await core.build_profile(db, c))["fields"] if c else {}
    return {
        "application_id": a.id, "candidate_id": a.candidate_id, "applied_at": a.applied_at, "hired_at": a.hired_at,
        "vacancy": {"id": v.id, "title": v.title} if v else None,
        "source": (c.source if c else None), "link": {"label": link.label, "channel": link.channel, "code": link.code} if link else None,
        "request": {"id": req.id, "number": req.number} if req else None,
        "recruiter": names.get(a.recruiter_id or 0),
        "interview": {
            "at": a.interview_at, "rating": a.rating, "hard_skill": a.hard_skill, "soft_skill": a.soft_skill, "notes": a.interview_notes,
            "match_score": a.match_score, "ai": (a.ai_scan or {}).get("summary") if a.ai_scan else None,
            "scorecards": [{"interviewer": names.get(s.interviewer_id), "scores": s.scores, "notes": s.notes} for s in scores],
        },
        "tests": [{"score": t.score_pct, "status": t.status, "submitted_at": t.submitted_at} for t in tests],
        "anketa": prof, "resume_text": (c.resume_text or "")[:3000] if c else None,
        "files": [{"id": f.id, "name": f.filename, "size": f.size} for f in files],
    }  # fmt: skip


@router.get("/{emp_id}/dossier")
async def dossier(
    emp_id: int,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.read")),
):
    e = await db.get(Employee, emp_id)
    if not e:
        raise error(404, "not_found")
    pos = await db.get(Position, e.position_id) if e.position_id else None
    dep = await db.get(Department, e.department_id) if e.department_id else None
    br = await db.get(Branch, e.branch_id) if e.branch_id else None
    see_docs = matches(auth.permissions, "employees.documents")
    docs = (
        (
            await db.scalars(
                select(EmployeeDocument)
                .where(EmployeeDocument.employee_id == e.id)
                .order_by(EmployeeDocument.id.desc())
            )
        ).all()
        if see_docs
        else []
    )
    orders = (
        await db.scalars(
            select(StaffDocument)
            .where(StaffDocument.employee_id == e.id)
            .order_by(StaffDocument.id.desc())
            .limit(100)
        )
    ).all()
    pay: list[dict[str, Any]] = []
    see_pay = matches(auth.permissions, "payroll.read")
    if see_pay:
        rows = (
            await db.execute(
                select(PayrollRun.period, PayrollRun.status, PayrollLine)
                .join(PayrollLine, PayrollLine.run_id == PayrollRun.id)
                .where(PayrollLine.employee_id == e.id)
                .order_by(PayrollRun.period.desc())
                .limit(36)
            )
        ).all()
        pay = [
            {"period": per, "status": st, "paid_days": ln.paid_days, "plan_days": ln.plan_days, "gross": float(ln.gross), "bonus": float(ln.plan_bonus + ln.kpi_bonus + ln.bonus), "penalties": float(ln.penalties), "net": float(ln.net), "to_pay": float(ln.to_pay)}
            for per, st, ln in rows
        ]  # fmt: skip
    return {
        "employee": {
            "id": e.id, "employee_no": e.employee_no, "full_name": e.full_name, "phone": e.phone, "status": e.status, "hire_date": e.hire_date, "dismissal_date": e.dismissal_date,
            "position": pos.name if pos else None, "department": dep.name if dep else None, "branch": br.name if br else None, "photo": bool(e.photo_key),
        },
        "tenure": tenure(e.hire_date, e.dismissal_date),
        "recruitment": await _recruitment(db, e.id),
        "documents": [{"id": d.id, "kind": d.kind, "title": d.title, "filename": d.filename, "issued_at": d.issued_at, "expires_at": d.expires_at} for d in docs],
        "orders": [{"id": o.id, "kind": o.kind, "subtype": o.subtype, "number": o.number, "title": o.title, "status": o.status, "start_date": o.start_date, "signed_at": o.signed_at, "created_at": o.created_at} for o in orders],
        "payroll": pay, "can": {"documents": see_docs, "payroll": see_pay},
    }  # fmt: skip
