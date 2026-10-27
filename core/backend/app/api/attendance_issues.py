"""Davomat muammosi: xodim so'rovi -> koordinator tasdig'i -> HR qarori (tasdiqlansa yozuv tuzatiladi)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _aware
from app.db import get_session
from app.deps import AuthContext, error, get_auth, require
from app.models.attendance_issues import AttendanceIssue
from app.models.employees import Employee
from app.models.org import Branch
from app.services import attendance as att
from app.services import attendance_issues as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/attendance-issues", tags=["attendance-issues"])


class IssueIn(BaseModel):
    work_date: date
    kind: str = Field(pattern=f"^({svc.KINDS})$")
    method_tried: str = Field(pattern=f"^({svc.METHODS})$")
    claimed_in: datetime | None = None
    claimed_out: datetime | None = None
    comment: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def _check(self):
        if self.kind in ("missed_in", "missed_out") and not (self.claimed_in or self.claimed_out):
            raise ValueError("time_required")
        if self.claimed_in and self.claimed_out and self.claimed_out <= self.claimed_in:
            raise ValueError("out_before_in")
        return self


class NoteIn(BaseModel):
    action: str = Field(pattern="^(confirm|reject|approve)$")
    note: str | None = Field(default=None, max_length=500)
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


async def _load(db: AsyncSession, issue_id: int, auth: AuthContext) -> tuple[AttendanceIssue, Employee]:
    issue = await db.get(AttendanceIssue, issue_id)
    emp = await db.get(Employee, issue.employee_id) if issue else None
    if not issue or not emp or not svc.can_view(auth, issue, emp):
        raise error(404, "not_found")
    return issue, emp


async def _out(db: AsyncSession, issue: AttendanceIssue, emp: Employee, auth: AuthContext) -> dict:
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    return svc.out(issue, emp, branch, auth)


@router.post("", status_code=201)
async def create(
    body: IssueIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.punch")),
):
    emp = await att.current_employee(db, auth.user.id)
    moment = now()
    svc.check_date(body.work_date, local_date(moment))
    if await db.scalar(
        select(AttendanceIssue.id).where(
            AttendanceIssue.employee_id == emp.id, AttendanceIssue.work_date == body.work_date, AttendanceIssue.status.in_(svc.PENDING)
        )
    ):
        raise error(409, "issue_exists")
    status, coordinator, targets = await svc.initial_route(db, emp)
    issue = AttendanceIssue(
        employee_id=emp.id, work_date=body.work_date, kind=body.kind, method_tried=body.method_tried,
        claimed_in=_aware(body.claimed_in), claimed_out=_aware(body.claimed_out), comment=body.comment.strip(),
        status=status, coordinator_user_id=coordinator, history=[],
    )  # fmt: skip
    svc.add_history(issue, "submitted", emp.full_name, None, None, moment)
    db.add(issue)
    await db.flush()
    notes = await notify(
        db, [t for t in targets if t != auth.user.id], "attendance_issue.new",
        params={"name": emp.full_name, "date": body.work_date.strftime("%d.%m.%Y")}, link=f"/attendance/issues/{issue.id}",
    )  # fmt: skip
    await audit(db, request, "attendance_issue.submit", actor=auth.user, entity="attendance_issue", entity_id=issue.id, data={"date": str(body.work_date), "kind": body.kind})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, issue, emp, auth)


@router.get("")
async def list_issues(
    scope: str = Query(default="all", pattern="^(mine|inbox|all)$"),
    status: str | None = Query(default=None, pattern="^(pending|pending_coordinator|pending_hr|approved|rejected|cancelled)$"),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    """mine: o'zimniki; inbox: menga qaror kutayotganlar; all: ko'ra oladiganlarim."""
    stmt = select(AttendanceIssue, Employee).join(Employee, Employee.id == AttendanceIssue.employee_id)
    if scope == "mine":
        stmt = stmt.where(Employee.user_id == auth.user.id)
    else:
        clause = svc.visible_clause(auth, Employee.user_id)
        if clause is not None:
            stmt = stmt.where(clause)
        elif not svc.sees_all(auth):
            raise error(403, "forbidden")
    if scope == "inbox":
        if svc.is_hr(auth):
            stmt = stmt.where(AttendanceIssue.status.in_(svc.PENDING))
        elif svc.has(auth, "answers.decide"):
            stmt = stmt.where(AttendanceIssue.status == "pending_coordinator", AttendanceIssue.coordinator_user_id == auth.user.id)
        else:
            raise error(403, "forbidden")
        stmt = stmt.where(Employee.user_id.is_distinct_from(auth.user.id))
    if status == "pending":
        stmt = stmt.where(AttendanceIssue.status.in_(svc.PENDING))
    elif status:
        stmt = stmt.where(AttendanceIssue.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = AttendanceIssue.created_at.asc() if scope == "inbox" else AttendanceIssue.created_at.desc()
    rows = (await db.execute(stmt.order_by(order).offset((page - 1) * size).limit(size))).all()
    branches = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_({e.branch_id for _, e in rows if e.branch_id})))).all()} if rows else {}
    return {
        "total": total or 0, "page": page, "size": size,
        "items": [svc.out(i, e, branches.get(e.branch_id), auth) for i, e in rows],
    }  # fmt: skip


@router.get("/{issue_id}")
async def detail(issue_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    issue, emp = await _load(db, issue_id, auth)
    return await _out(db, issue, emp, auth)


@router.post("/{issue_id}/verify")
async def verify(issue_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Koordinator (yoki HR) so'rovni o'zi bilgan holatga qarab tasdiqlaydi yoki rad etadi."""
    issue, emp = await _load(db, issue_id, auth)
    if body.action not in ("confirm", "reject"):
        raise error(400, "bad_action")
    if not svc.can_verify(auth, issue, emp):
        raise error(409 if issue.status not in svc.PENDING else 403, "already_decided" if issue.status not in svc.PENDING else "forbidden")
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    moment = now()
    level = "hr" if svc.is_hr(auth) else "coordinator"
    notes = []
    date_s = issue.work_date.strftime("%d.%m.%Y")
    if body.action == "confirm":
        issue.status = "pending_hr"
        svc.add_history(issue, "verified", auth.user.full_name, level, note, moment)
        notes = await notify(db, await svc.users_with_permission(db, "attendance.edit"), "attendance_issue.verified", params={"name": emp.full_name, "date": date_s}, link=f"/attendance/issues/{issue.id}")
    else:
        issue.status, issue.decided_by, issue.decided_at, issue.decision_note = "rejected", auth.user.id, moment, note
        svc.add_history(issue, "rejected", auth.user.full_name, level, note, moment)
        notes = await notify(db, [emp.user_id] if emp.user_id else [], "attendance_issue.rejected", params={"date": date_s, "note": note or ""}, link=f"/attendance/issues/{issue.id}")
    await audit(db, request, f"attendance_issue.{body.action}", actor=auth.user, entity="attendance_issue", entity_id=issue.id, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, issue, emp, auth)


@router.post("/{issue_id}/decide")
async def decide(issue_id: int, body: NoteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR yakuniy qaror: tasdiqlansa davomat yozuvi tuzatish tarixi bilan yaratiladi/yangilanadi."""
    issue, emp = await _load(db, issue_id, auth)
    if body.action not in ("approve", "reject"):
        raise error(400, "bad_action")
    if issue.status not in svc.PENDING:
        raise error(409, "already_decided")
    if not svc.can_decide(auth, issue, emp):
        raise error(403, "forbidden")
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    moment = now()
    date_s = issue.work_date.strftime("%d.%m.%Y")
    if body.action == "approve":
        rec = await svc.apply_fix(db, issue, emp, auth.user.id, _aware(body.check_in_at), _aware(body.check_out_at), note)
        issue.status, issue.record_id = "approved", rec.id
        kind, params = "attendance_issue.approved", {"date": date_s}
    else:
        issue.status = "rejected"
        kind, params = "attendance_issue.rejected", {"date": date_s, "note": note or ""}
    issue.decided_by, issue.decided_at, issue.decision_note = auth.user.id, moment, note
    svc.add_history(issue, issue.status, auth.user.full_name, "hr", note, moment)
    notes = await notify(db, [emp.user_id] if emp.user_id else [], kind, params=params, link=f"/attendance/issues/{issue.id}")
    await audit(db, request, f"attendance_issue.{body.action}", actor=auth.user, entity="attendance_issue", entity_id=issue.id, data={"record_id": issue.record_id}, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, issue, emp, auth)


@router.post("/{issue_id}/cancel")
async def cancel(issue_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    issue, emp = await _load(db, issue_id, auth)
    if emp.user_id != auth.user.id:
        raise error(403, "forbidden")
    if issue.status not in svc.PENDING:
        raise error(409, "cannot_cancel")
    issue.status = "cancelled"
    svc.add_history(issue, "cancelled", emp.full_name, None, None, now())
    await audit(db, request, "attendance_issue.cancel", actor=auth.user, entity="attendance_issue", entity_id=issue.id)
    await db.commit()
    return await _out(db, issue, emp, auth)
