"""Koordinator davomat hisoboti: ko'rish, qo'lda yuborish va koordinatorning sabab/chora izohi."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth, require
from app.models.attendance_issues import AttendanceExplanation
from app.models.employees import Employee
from app.models.org import Branch
from app.services import coord_report as svc
from app.services.attendance_issues import has, is_hr, sees_all
from app.services.audit import audit
from app.services.notifications import deliver
from app.timeutil import local_date, localize, now

router = APIRouter(prefix="/v1/coord-report", tags=["coord-report"])


def _moment_for(day: date) -> datetime:
    current = now()
    if day >= local_date(current):
        return current
    return localize(datetime.combine(day, datetime.min.time())) + timedelta(hours=23, minutes=59)


def _scope(auth: AuthContext) -> int | None:
    """None = hamma koordinatorlar (HR/ko'rish huquqi); aks holda faqat o'zining filiallari."""
    if sees_all(auth):
        return None
    if has(auth, "answers.decide"):
        return auth.user.id
    raise error(403, "forbidden")


def _exp_out(x: AttendanceExplanation, current: datetime) -> dict:
    return {
        "id": x.id, "status": x.status, "reason": x.reason, "measures": x.measures,
        "due_at": x.due_at.isoformat(), "submitted_at": x.submitted_at.isoformat() if x.submitted_at else None,
        "overdue": x.status == "pending" and x.due_at <= current,
    }  # fmt: skip


@router.get("")
async def report(
    date_: date | None = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    scope = _scope(auth)
    day = date_ or local_date(now())
    moment = _moment_for(day)
    data = await svc.build(db, day, moment, coordinator_id=scope)
    exps = {(x.employee_id, x.kind): x for x in (await db.scalars(select(AttendanceExplanation).where(AttendanceExplanation.work_date == day))).all()}
    pending = overdue = 0
    for c in data["coordinators"]:
        for g in c["shifts"]:
            for it in g["absent"] + g["late"]:
                x = exps.get((it["employee_id"], it["kind"]))
                it["explanation"] = _exp_out(x, moment) if x else None
                if x and x.status == "pending":
                    pending += 1
                    overdue += x.due_at <= moment
    data["pending"], data["overdue"] = pending, overdue
    data["can_send"] = is_hr(auth)
    return data


class ExplainIn(BaseModel):
    employee_id: int
    work_date: date
    kind: str = Field(pattern="^(absent|late)$")
    reason: str = Field(min_length=3, max_length=1000)
    measures: str = Field(min_length=3, max_length=1000)


@router.post("/explain")
async def explain(body: ExplainIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    emp = await db.get(Employee, body.employee_id)
    branch = await db.get(Branch, emp.branch_id) if emp and emp.branch_id else None
    if not emp or not branch:
        raise error(404, "not_found")
    if not (is_hr(auth) or (has(auth, "answers.decide") and branch.coordinator_user_id == auth.user.id)):
        raise error(403, "forbidden")
    moment = now()
    x = await db.scalar(select(AttendanceExplanation).where(AttendanceExplanation.employee_id == emp.id, AttendanceExplanation.work_date == body.work_date, AttendanceExplanation.kind == body.kind))
    if x is None:
        # hisobotda haqiqatan shunday holat bormi (o'zboshimchalik bilan yozuv yaratib bo'lmaydi)
        data = await svc.build(db, body.work_date, _moment_for(body.work_date), coordinator_id=branch.coordinator_user_id)
        if not any(it["employee_id"] == emp.id and it["kind"] == body.kind for c in data["coordinators"] for g in c["shifts"] for it in g["absent"] + g["late"]):
            raise error(404, "not_found")
        x = AttendanceExplanation(employee_id=emp.id, work_date=body.work_date, kind=body.kind, coordinator_user_id=branch.coordinator_user_id, due_at=moment + timedelta(hours=svc.EXPLAIN_HOURS))
        db.add(x)
    x.reason, x.measures = body.reason.strip(), body.measures.strip()
    x.status, x.submitted_at, x.submitted_by = "submitted", moment, auth.user.id
    await db.flush()
    await audit(db, request, "attendance.explain", actor=auth.user, entity="attendance_explanation", entity_id=x.id, data={"employee_id": emp.id, "date": str(body.work_date), "kind": body.kind})
    await db.commit()
    return _exp_out(x, moment)


@router.post("/send")
async def send_now(request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("attendance.edit"))):
    """HR: hisobotni hozirning o'zida tuzib, koordinatorlar va HR ga yuboradi (izoh qatorlari ham yaratiladi)."""
    notes = await svc.run_daily(db, now())
    await db.commit()
    await deliver(request.app, notes)
    return {"sent": len(notes)}
