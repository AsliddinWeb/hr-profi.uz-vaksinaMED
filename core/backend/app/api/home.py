"""Bosh sahifa dashboardi: har bir bo'lim bo'yicha asosiy raqamlar bitta so'rovda (davomat, topshiriqlar,
javob/ta'til, muammolar, ish zanjiri: zayafka -> vakansiya -> nomzod -> ishga qabul -> prebording -> dars).
Har bo'lim faqat tegishli ruxsati bor foydalanuvchiga qaytariladi."""

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, get_auth
from app.models.answers import LeaveRequest
from app.models.attendance_issues import AttendanceIssue
from app.models.employees import Employee
from app.models.helpdesk import Ticket
from app.models.integrations import Complaint
from app.models.internship import InternshipEnrollment
from app.models.letters import ExplanationLetter
from app.models.needs import NeedRequest
from app.models.penalties import Penalty
from app.models.recruit import Application, Candidate, HireRequest, Vacancy
from app.models.smart import Conference
from app.models.tasks import Task
from app.rbac import matches
from app.services import answers as answers_svc
from app.services import attendance_issues as issues_svc
from app.services import helpdesk as desk_svc
from app.services import letters as letters_svc
from app.services import needs as needs_svc
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/home", tags=["home"])


def _any(auth: AuthContext, *perms: str) -> bool:
    return any(matches(auth.permissions, p) for p in perms)


def _dt(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=tz())


async def _count(db: AsyncSession, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def _attendance(db: AsyncSession, today: date, days: int) -> dict[str, Any]:
    from app.api.attendance import _dashboard  # noqa: PLC0415

    start = today - timedelta(days=days - 1)
    data = await _dashboard(db, start, today, q=None, department_id=None, branch_id=None, group_id=None)
    day = await _dashboard(db, today, today, q=None, department_id=None, branch_id=None, group_id=None)
    k = day["kpis"]
    return {
        "today": {"came": k.get("attended", 0), "absent": k.get("absent", 0), "late": k.get("late_count", 0), "no_checkout": k.get("no_checkout", 0),
                  "rate": k.get("rate"), "punctuality": k.get("punctuality")},
        "trend": [{"date": x["date"], "came": x.get("attended", 0), "late": x.get("late", 0), "absent": x.get("absent", 0)} for x in data["trend"]],
        "top_late": [{"id": p["employee"]["id"], "name": p["employee"]["full_name"], "n": p["late_count"]} for p in data.get("top_late", [])[:5]],
    }  # fmt: skip


async def _tasks(db: AsyncSession, today: date, days: int) -> dict[str, Any]:
    moment = now()
    start = _dt(today - timedelta(days=days - 1))
    live = Task.archived_at.is_(None)
    by_status = dict((await db.execute(select(Task.status, func.count()).where(live).group_by(Task.status))).all())
    overdue = await _count(db, Task, live, Task.status != "done", Task.due_at.is_not(None), Task.due_at < moment)
    done_rows = (await db.execute(select(Task.completed_at).where(Task.completed_at >= start))).all()
    per_day = Counter(local_date(c).isoformat() for (c,) in done_rows)
    created = (await db.execute(select(Task.created_at).where(Task.created_at >= start))).all()
    created_day = Counter(local_date(c).isoformat() for (c,) in created)
    total = sum(by_status.values())
    return {
        "todo": by_status.get("todo", 0), "in_progress": by_status.get("in_progress", 0), "review": by_status.get("review", 0), "done": by_status.get("done", 0),
        "overdue": overdue, "done_rate": round(by_status.get("done", 0) / total * 100) if total else None, "done_period": len(done_rows),
        "trend": [{"date": (today - timedelta(days=days - 1 - i)).isoformat(), "done": per_day.get((today - timedelta(days=days - 1 - i)).isoformat(), 0),
                   "created": created_day.get((today - timedelta(days=days - 1 - i)).isoformat(), 0)} for i in range(days)],
    }  # fmt: skip


async def _answers(db: AsyncSession, today: date) -> dict[str, Any]:
    month_start = today.replace(day=1)
    on_leave = await db.scalar(
        select(func.count(func.distinct(LeaveRequest.employee_id))).where(LeaveRequest.status == "approved", LeaveRequest.start_date <= today, LeaveRequest.end_date >= today)
    ) or 0  # fmt: skip
    upcoming = await _count(db, LeaveRequest, LeaveRequest.status == "approved", LeaveRequest.start_date > today, LeaveRequest.start_date <= today + timedelta(days=7))
    by = dict((await db.execute(select(LeaveRequest.status, func.count()).where(LeaveRequest.created_at >= _dt(month_start)).group_by(LeaveRequest.status))).all())
    reasons = dict((await db.execute(select(LeaveRequest.reason_type, func.count()).where(LeaveRequest.status == "approved", LeaveRequest.created_at >= _dt(month_start)).group_by(LeaveRequest.reason_type))).all())
    return {
        "pending": await _count(db, LeaveRequest, LeaveRequest.status.in_(answers_svc.PENDING)), "approved_month": by.get("approved", 0),
        "rejected_month": by.get("rejected", 0), "on_leave_today": on_leave, "upcoming_7d": upcoming, "reasons": reasons,
    }  # fmt: skip


async def _problems(db: AsyncSession, today: date, auth: AuthContext) -> dict[str, Any]:
    month = _dt(today.replace(day=1))
    out: dict[str, Any] = {}
    if _any(auth, "attendance.edit", "attendance.read", "answers.decide"):
        out["attendance_issues"] = await _count(db, AttendanceIssue, AttendanceIssue.status.in_(issues_svc.PENDING))
    if _any(auth, "letters.read", "letters.manage", "letters.review"):
        out["letters_open"] = await _count(db, ExplanationLetter, ExplanationLetter.status.in_(letters_svc.OPEN))
        out["letters_month"] = await _count(db, ExplanationLetter, ExplanationLetter.requested_at >= month)
    if _any(auth, "penalties.read", "penalties.manage", "penalties.approve"):
        out["penalties_pending"] = await _count(db, Penalty, Penalty.status == "pending")
        out["penalties_month"] = await _count(db, Penalty, Penalty.status != "cancelled", Penalty.incident_date >= today.replace(day=1))
    if _any(auth, "helpdesk.read", "helpdesk.manage"):
        out["tickets_open"] = await _count(db, Ticket, Ticket.status.in_(desk_svc.OPEN))
    if _any(auth, "complaints.read", "complaints.manage"):
        out["complaints_new"] = await _count(db, Complaint, Complaint.status.in_(("new", "in_progress")))
    if _any(auth, "letters.read", "letters.manage", "penalties.read", "penalties.manage"):
        rows = (await db.execute(
            select(Employee.id, Employee.full_name, func.count(ExplanationLetter.id))
            .join(ExplanationLetter, ExplanationLetter.employee_id == Employee.id)
            .where(ExplanationLetter.requested_at >= month).group_by(Employee.id, Employee.full_name)
            .order_by(func.count(ExplanationLetter.id).desc()).limit(5)
        )).all()  # fmt: skip
        out["people_month"] = await db.scalar(select(func.count(func.distinct(ExplanationLetter.employee_id))).where(ExplanationLetter.requested_at >= month)) or 0
        out["top_people"] = [{"id": i, "name": n, "n": c} for i, n, c in rows]
    return out


async def _chain(db: AsyncSession, today: date, auth: AuthContext) -> list[dict[str, Any]]:
    """Ish zanjiri: har bosqichda nechta ish turibdi (birinchi bosqichdan oxirgisigacha)."""
    steps: list[dict[str, Any]] = []
    d7, d30 = _dt(today - timedelta(days=6)), _dt(today - timedelta(days=29))
    if _any(auth, "recruit.read", "recruit.manage", "recruit.approve"):
        steps.append({"key": "requests", "to": "/recruit/requests", "value": await _count(db, HireRequest, HireRequest.status == "pending"), "sub": await _count(db, HireRequest, HireRequest.created_at >= d30)})
        steps.append({"key": "vacancies", "to": "/recruit", "value": await _count(db, Vacancy, Vacancy.status == "open"), "sub": None})
        steps.append({"key": "candidates", "to": "/recruit/candidates", "value": await _count(db, Candidate, Candidate.created_at >= d7), "sub": await _count(db, Application, Application.stage.in_(("new", "screening")), Application.is_active.is_(True))})
        steps.append({"key": "interviews", "to": "/recruit", "value": await _count(db, Application, Application.stage.in_(("interview", "offer")), Application.is_active.is_(True)), "sub": None})
        steps.append({"key": "hired", "to": "/recruit/funnel", "value": await _count(db, Application, Application.hired_at >= d30), "sub": None})
    if _any(auth, "internship.read", "internship.manage"):
        steps.append({"key": "preboarding", "to": "/preboarding", "value": await _count(db, InternshipEnrollment, InternshipEnrollment.status == "active"),
                      "sub": await _count(db, InternshipEnrollment, InternshipEnrollment.status == "completed", InternshipEnrollment.completed_at >= d30)})  # fmt: skip
    if _any(auth, "conference.read", "conference.manage", "conference.own"):
        steps.append({"key": "conferences", "to": "/conferences", "value": await _count(db, Conference, Conference.status.in_(("scheduled", "live")), Conference.starts_at >= _dt(today)),
                      "sub": await _count(db, Conference, Conference.status == "ended", Conference.ended_at >= d30)})  # fmt: skip
    if _any(auth, "needs.read", "needs.manage"):
        steps.append({"key": "needs", "to": "/needs", "value": await _count(db, NeedRequest, NeedRequest.status.in_(needs_svc.OPEN)), "sub": None})
    return steps


@router.get("/overview")
async def overview(days: int = Query(default=7, ge=3, le=31), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    today = local_date(now())
    out: dict[str, Any] = {"date": today, "days": days}
    if _any(auth, "attendance.read"):
        out["attendance"] = await _attendance(db, today, days)
    if _any(auth, "tasks.read", "tasks.manage"):
        out["tasks"] = await _tasks(db, today, days)
    if _any(auth, "answers.decide", "answers.read", "attendance.read"):
        out["answers"] = await _answers(db, today)
    problems = await _problems(db, today, auth)
    if problems:
        out["problems"] = problems
    chain = await _chain(db, today, auth)
    if chain:
        out["chain"] = chain
    out["headcount"] = await _count(db, Employee, Employee.status == "active") if _any(auth, "employees.read") else None
    return out



