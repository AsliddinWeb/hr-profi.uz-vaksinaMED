"""Javob olish: ruxsat so'rovlari (kunlik/soatlik), koordinator -> HR, kalendar, tarix."""

import asyncio
import calendar
from datetime import date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.answers import LeaveEvent, LeaveRequest
from app.models.auth import User
from app.models.employees import Employee
from app.services import answers as svc
from app.services import answers_report as rep
from app.services import answers_report_export as rexp
from app.services import attendance as att
from app.services import leave_statement as stmt
from app.services.audit import audit, client_ip
from app.services.notifications import deliver
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/answers", tags=["answers"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


class RequestIn(BaseModel):
    kind: str = Field(pattern="^(day|hourly)$")
    reason_type: str = Field(pattern="^(sick|family|personal|business|other)$")
    reason: str | None = Field(default=None, max_length=1000)
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.reason_type == "other" and len((self.reason or "").strip()) < 3:
            raise ValueError("reason_required")
        return self


async def _emp(db: AsyncSession, emp_id: int) -> Employee:
    e = await db.get(Employee, emp_id)
    if not e:
        raise error(404, "not_found")
    return e


async def _load(db: AsyncSession, request_id: int, auth: AuthContext) -> tuple[LeaveRequest, Employee]:
    req = await db.get(LeaveRequest, request_id)
    if not req:
        raise error(404, "not_found")
    emp = await _emp(db, req.employee_id)
    if not svc.can_view(auth, req, emp):
        raise error(404, "not_found")  # ko'rish huquqi yo'q: mavjudligini ham oshkor qilmaymiz
    return req, emp


@router.post("/requests", status_code=201)
async def create(
    body: RequestIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("answers.request")),
):
    emp = await att.current_employee(db, auth.user.id)
    moment = now()
    end = body.end_date or body.start_date
    if body.kind == "hourly":
        end = body.start_date
    svc.validate(body.kind, body.start_date, end, body.start_time, body.end_time, local_date(moment))
    await svc.check_overlap(db, emp.id, body.kind, body.start_date, end, body.start_time, body.end_time)
    req, notes = await svc.create_request(
        db, emp, auth.user, kind=body.kind, reason_type=body.reason_type, reason=body.reason, start_date=body.start_date,
        end_date=end, start_time=body.start_time if body.kind == "hourly" else None,
        end_time=body.end_time if body.kind == "hourly" else None, moment=moment,
    )  # fmt: skip
    await audit(db, request, "answers.submit", actor=auth.user, entity="leave_request", entity_id=req.id,
                data={"kind": req.kind, "period": svc.period_text(req)})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return svc.request_out(req, emp, can_cancel=True)


@router.get("/requests")
async def list_requests(
    scope: str = Query(default="all", pattern="^(mine|inbox|all)$"),
    status: str | None = Query(default=None, pattern="^(pending|pending_coordinator|pending_hr|approved|rejected|cancelled)$"),
    q: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    """mine: o'zimniki; inbox: qaror kutayotganlar (menga); all: ko'ra oladiganlarim."""
    stmt = select(LeaveRequest, Employee).join(Employee, Employee.id == LeaveRequest.employee_id)
    if scope == "mine":
        stmt = stmt.where(Employee.user_id == auth.user.id)
    else:
        clause = svc.visible_clause(auth, Employee.user_id)
        if clause is not None:
            stmt = stmt.where(clause)
        elif not (svc.has(auth, "answers.read") or svc.has(auth, "answers.manage")):
            raise error(403, "forbidden")
    if scope == "inbox":
        if svc.has(auth, "answers.manage"):
            stmt = stmt.where(LeaveRequest.status.in_(svc.PENDING))
        elif svc.has(auth, "answers.decide"):
            stmt = stmt.where(LeaveRequest.status == "pending_coordinator", LeaveRequest.coordinator_user_id == auth.user.id)
        else:
            raise error(403, "forbidden")
        stmt = stmt.where(Employee.user_id.is_distinct_from(auth.user.id))
    if status == "pending":
        stmt = stmt.where(LeaveRequest.status.in_(svc.PENDING))
    elif status:
        stmt = stmt.where(LeaveRequest.status == status)
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    if start:
        stmt = stmt.where(LeaveRequest.end_date >= start)
    if end:
        stmt = stmt.where(LeaveRequest.start_date <= end)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = LeaveRequest.submitted_at.asc() if scope == "inbox" else LeaveRequest.submitted_at.desc()
    rows = (await db.execute(stmt.order_by(order).offset((page - 1) * size).limit(size))).all()
    today = local_date(now())
    return {
        "total": total or 0, "page": page, "size": size,
        "items": [
            svc.request_out(r, e, can_decide_=svc.can_decide(auth, r, e),
                            can_cancel=e.user_id == auth.user.id and r.status in svc.ACTIVE and not (r.status == "approved" and r.start_date <= today))
            for r, e in rows
        ],
    }  # fmt: skip


@router.get("/requests/{request_id}")
async def detail(request_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    req, emp = await _load(db, request_id, auth)
    events = (await db.scalars(select(LeaveEvent).where(LeaveEvent.request_id == req.id).order_by(LeaveEvent.id))).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({e.actor_id for e in events if e.actor_id} | ({req.coordinator_user_id} if req.coordinator_user_id else set()))))).all()}
    today = local_date(now())
    out = svc.request_out(
        req, emp, can_decide_=svc.can_decide(auth, req, emp),
        can_cancel=emp.user_id == auth.user.id and req.status in svc.ACTIVE and not (req.status == "approved" and req.start_date <= today),
    )  # fmt: skip
    out["coordinator"] = names.get(req.coordinator_user_id) if req.coordinator_user_id else None
    out["events"] = [
        {"id": e.id, "action": e.action, "level": e.level, "note": e.note, "actor": names.get(e.actor_id) if e.actor_id else None, "created_at": e.created_at}
        for e in events
    ]  # fmt: skip
    return out


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/requests/{request_id}/decision")
async def decision(
    request_id: int,
    body: DecisionIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("answers.decide", "answers.manage")),
):
    req = await db.scalar(select(LeaveRequest).where(LeaveRequest.id == request_id).with_for_update())
    if not req:
        raise error(404, "not_found")
    emp = await _emp(db, req.employee_id)
    if not svc.can_view(auth, req, emp):
        raise error(404, "not_found")
    notes = await svc.decide(db, req, emp, auth, body.action, body.note, now())
    issued = await stmt.ensure(db, req, emp, now()) if req.status == "approved" else False
    await audit(db, request, f"answers.{req.status}", actor=auth.user, entity="leave_request", entity_id=req.id,
                data={"employee_id": emp.id, "period": svc.period_text(req), "level": req.decided_level}, note=req.decision_note)  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    if issued and emp.user_id:  # bildirgi xodimning Telegramiga PDF sifatida yuboriladi (ulangan bo'lsa)
        await request.app.state.queue.enqueue("deliver_statement_telegram", req.id)
    return svc.request_out(req, emp)


@router.post("/requests/{request_id}/cancel")
async def cancel(
    request_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("answers.request")),
):
    req = await db.scalar(select(LeaveRequest).where(LeaveRequest.id == request_id).with_for_update())
    if not req:
        raise error(404, "not_found")
    emp = await _emp(db, req.employee_id)
    await svc.cancel(db, req, emp, auth, local_date(now()))
    await audit(db, request, "answers.cancel", actor=auth.user, entity="leave_request", entity_id=req.id)
    await db.commit()
    return svc.request_out(req, emp)


@router.get("/inbox/count")
async def inbox_count(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)) -> dict[str, int]:
    """Menga qaror kutayotgan so'rovlar soni (menyu belgisi uchun)."""
    stmt = select(func.count()).select_from(LeaveRequest).join(Employee, Employee.id == LeaveRequest.employee_id).where(Employee.user_id.is_distinct_from(auth.user.id))
    if svc.has(auth, "answers.manage"):
        stmt = stmt.where(LeaveRequest.status.in_(svc.PENDING))
    elif svc.has(auth, "answers.decide"):
        stmt = stmt.where(LeaveRequest.status == "pending_coordinator", LeaveRequest.coordinator_user_id == auth.user.id)
    else:
        return {"count": 0}
    return {"count": await db.scalar(stmt) or 0}


@router.get("/calendar")
async def calendar_view(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    branch_id: int | None = None,
    department_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, Any]:
    """Oy kalendari: tasdiqlangan va kutilayotgan so'rovlar (kim qachon yo'q)."""
    y, m = int(month[:4]), int(month[5:])
    start, end = date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    stmt = (
        select(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(LeaveRequest.status.in_(("approved", *svc.PENDING)), LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
    )
    clause = svc.visible_clause(auth, Employee.user_id)
    if clause is not None:
        stmt = stmt.where(clause)
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    rows = (await db.execute(stmt.order_by(LeaveRequest.start_date, Employee.full_name))).all()
    return {
        "month": month, "start": start, "end": end,
        "items": [
            {"id": r.id, "employee": {"id": e.id, "full_name": e.full_name}, "kind": r.kind, "reason_type": r.reason_type, "status": r.status,
             "start_date": r.start_date, "end_date": r.end_date,
             "start_time": r.start_time.strftime("%H:%M") if r.start_time else None, "end_time": r.end_time.strftime("%H:%M") if r.end_time else None}
            for r, e in rows
        ],
    }  # fmt: skip


async def _report(db: AsyncSession, auth: AuthContext, month: str, branch_id: int | None, q: str | None):
    if not any(svc.has(auth, p) for p in ("answers.read", "answers.manage", "answers.decide")):
        raise error(403, "forbidden")
    items = await rep.collect(db, auth, month, branch_id=branch_id, q=q)
    return items, rep.summarize(items, month)


@router.get("/report")
async def report(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    status: str | None = Query(default=None, pattern="^(all|pending|pending_coordinator|pending_hr|approved|rejected|cancelled)$"),
    branch_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, Any]:
    """Javob olish holati: KPI, kunlik kalendar, xodimlar reytingi va (sahifalangan) so'rovlar kartochkalari."""
    items, summary = await _report(db, auth, month, branch_id, q)
    shown = rep.filter_status(items, status)
    return {**summary, "total": len(shown), "page": page, "size": size, "items": shown[(page - 1) * size : page * size]}


@router.get("/report/export")
async def report_export(
    request: Request,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    format: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    lang: str = Query(default="uz", pattern="^(uz|ru)$"),
    status: str | None = Query(default=None, pattern="^(all|pending|pending_coordinator|pending_hr|approved|rejected|cancelled)$"),
    branch_id: int | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    items, summary = await _report(db, auth, month, branch_id, q)
    shown = rep.filter_status(items, status)
    await audit(db, request, "answers.export", actor=auth.user, entity="leave_request", data={"month": month, "format": format, "rows": len(shown)})
    await db.commit()
    if format == "xlsx":
        content = await asyncio.to_thread(rexp.build_xlsx, shown, summary, lang)
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="javob-holat-{month}.xlsx"'})
    t = rexp.L["ru" if lang == "ru" else "uz"]
    parts = [t["status_low"].get(status, "") if status and status not in ("all", "pending") else "", q or ""]
    generated = datetime.now(tz()).strftime("%d.%m.%Y %H:%M")
    content = await asyncio.to_thread(rexp.build_pdf, shown, summary, lang, ", ".join(p for p in parts if p), generated, len(items) >= rep.MAX_ROWS)
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="javob-holat-{month}.pdf"'})


@router.get("/requests/{request_id}/statement")
async def statement(request_id: int, request: Request, lang: str = Query(default="uz", pattern="^(uz|ru)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Elektron bildirgi (PDF): faqat tasdiqlangan so'rov uchun; xodimning o'zi, koordinator va HR ko'radi."""
    req, emp = await _load(db, request_id, auth)
    if req.status != "approved":
        raise error(409, "not_approved")
    if await stmt.ensure(db, req, emp, now()):
        await db.commit()
    cfg = getattr(request.app.state, "client_config", None)
    company = (cfg.brand.get("name") if cfg else None) or "HR-Profi"
    content = await stmt.build_pdf(db, req, emp, f"{_base_url(request)}/verify/leave/{req.statement_code}", company, lang)
    await audit(db, request, "answers.statement", actor=auth.user, entity="leave_request", entity_id=req.id)
    await db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{req.statement_no}.pdf"'})


@public_router.get("/leave/{code}")
async def verify_statement(code: str, request: Request, hash: str | None = Query(default=None, max_length=64), db: AsyncSession = Depends(get_session)):
    """QR orqali bildirgini tekshirish: sabab ko'rsatilmaydi, faqat mavjudligi, holati va yaxlitligi."""
    redis = request.app.state.redis
    rk = f"rl:verify:{client_ip(request)}"
    n = await redis.incr(rk)
    if n == 1:
        await redis.expire(rk, 60)
    if n > 60:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(rk), 1))
    req = await db.scalar(select(LeaveRequest).where(LeaveRequest.statement_code == code[:40]))
    if not req:
        raise error(404, "not_found")
    return stmt.public_view(req, await _emp(db, req.employee_id), hash)
