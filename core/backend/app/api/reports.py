"""Hisobotlar markazi: katalog, hisobot tuzish, tarix, jadvalli hisobotlar (alohida CRUD sahifalar)."""

from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.reports import ReportRun, ReportSchedule
from app.rbac import matches
from app.services import reports as svc
from app.services.audit import audit
from app.services.notifications import deliver
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/reports", tags=["reports"])


def need(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(matches(auth.permissions, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Read = need("reports.read", "reports.manage")
Manage = need("reports.manage")


def _catalog(auth: AuthContext) -> list[dict[str, Any]]:
    return [{"type": k, "title": {"uz": v[0], "ru": v[1]}, "needs_period": v[3]} for k, v in svc.CATALOG.items() if svc.allowed(auth.permissions, k)]


@router.get("/types")
async def types(auth: AuthContext = Depends(Read)):
    return {"types": _catalog(auth), "periods": list(svc.PERIODS), "max_days": svc.MAX_DAYS}


class RunIn(BaseModel):
    type: str
    start: date | None = None
    end: date | None = None
    format: str = Field(default="xlsx", pattern="^(xlsx|pdf)$")
    lang: str = Field(default="uz", pattern="^(uz|ru)$")


def _run_out(r: ReportRun, names: dict[int, str] | None = None, sched: dict[int, str] | None = None) -> dict[str, Any]:
    return {
        "id": r.id, "type": r.report_type, "start": r.start_date, "end": r.end_date, "format": r.format, "lang": r.lang, "status": r.status, "error": r.error,
        "filename": r.filename, "size": r.file_size, "rows": r.row_count, "created_at": r.created_at,
        "schedule": {"id": r.schedule_id, "name": (sched or {}).get(r.schedule_id or 0)} if r.schedule_id else None,
        "created_by": (names or {}).get(r.created_by or 0),
    }  # fmt: skip


@router.post("/run", status_code=201)
async def run(body: RunIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    if not svc.allowed(auth.permissions, body.type):
        raise error(403 if body.type in svc.CATALOG else 400, "forbidden" if body.type in svc.CATALOG else "unknown_report")
    if svc.CATALOG[body.type][3] and (body.start is None or body.end is None):
        raise error(400, "range_required")
    start = body.start or local_date(now())
    end = body.end or start
    r = await svc.generate(db, request.app.state.storage, rtype=body.type, start=start, end=end, fmt=body.format, lang=body.lang, user_id=auth.user.id, moment=now())
    await audit(db, request, "reports.run", actor=auth.user, entity="report", entity_id=r.id, data={"type": body.type, "start": str(start), "end": str(end), "format": body.format, "status": r.status})
    await db.commit()
    return _run_out(r, {auth.user.id: auth.user.full_name})


@router.get("/runs")
async def runs(
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    type: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    R = ReportRun
    if scope == "all":
        if not matches(auth.permissions, "reports.manage"):
            raise error(403, "forbidden")
        conds: list = []
    else:
        # o'zi tuzgan yoki unga jo'natilgan (jadval bo'yicha)
        conds = [or_(R.created_by == auth.user.id, R.recipient_ids.contains([auth.user.id]))]
    if type:
        conds.append(R.report_type == type)
    total = await db.scalar(select(func.count()).select_from(R).where(*conds)) or 0
    rows = list((await db.scalars(select(R).where(*conds).order_by(R.id.desc()).offset((page - 1) * size).limit(size))).all())
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_([r.created_by for r in rows if r.created_by])))).all()} if rows else {}
    sched = {s.id: s.name for s in (await db.scalars(select(ReportSchedule).where(ReportSchedule.id.in_([r.schedule_id for r in rows if r.schedule_id])))).all()} if rows else {}
    return {"total": total, "page": page, "size": size, "items": [_run_out(r, names, sched) for r in rows]}


@router.get("/runs/{run_id}/file")
async def download(run_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    r = await db.get(ReportRun, run_id)
    if not r or not svc.can_download(auth, r):
        raise error(404, "not_found")
    if r.status != "ok" or not r.file_key:
        raise error(409, "report_failed")
    await audit(db, request, "reports.download", actor=auth.user, entity="report", entity_id=r.id, data={"type": r.report_type})
    await db.commit()
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"attachment; filename*=UTF-8''{quote(r.filename or 'hisobot')}"}
    return StreamingResponse(request.app.state.storage.stream(r.file_key), media_type=svc.MIME[r.format], headers=headers)


# --- Jadvallar --------------------------------------------------------------------------


class ScheduleIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    report_type: str
    period: str = Field(default="last_week", pattern="^(yesterday|last_7d|last_week|this_month|last_month)$")
    format: str = Field(default="xlsx", pattern="^(xlsx|pdf)$")
    lang: str = Field(default="uz", pattern="^(uz|ru)$")
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int | None = Field(default=None, ge=0, le=6)
    month_day: int | None = Field(default=None, ge=1, le=28)
    recipient_ids: list[int] = Field(min_length=1, max_length=50)
    channels: list[str] = Field(default_factory=lambda: ["app"])
    is_active: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.frequency == "weekly" and self.weekday is None:
            raise ValueError("weekday_required")
        if self.frequency == "monthly" and self.month_day is None:
            raise ValueError("month_day_required")
        if not set(self.channels) <= {"app", "telegram"} or not self.channels:
            raise ValueError("bad_channels")
        return self


async def _schedule_out(db: AsyncSession, s: ReportSchedule) -> dict[str, Any]:
    users = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_(list(s.recipient_ids or []))))).all()} if s.recipient_ids else {}
    return {
        "id": s.id, "name": s.name, "report_type": s.report_type, "period": s.period, "format": s.format, "lang": s.lang, "frequency": s.frequency, "hour": s.hour, "minute": s.minute,
        "weekday": s.weekday, "month_day": s.month_day, "channels": s.channels, "is_active": s.is_active, "last_run_at": s.last_run_at, "next_run_at": s.next_run_at, "last_status": s.last_status,
        "recipients": [{"id": i, "name": users[i].full_name if i in users else None, "telegram": bool(users[i].telegram_chat_id) if i in users else False} for i in (s.recipient_ids or [])],
    }  # fmt: skip


async def _validate(db: AsyncSession, body: ScheduleIn, auth: AuthContext) -> list[int]:
    if not svc.allowed(auth.permissions, body.report_type):
        raise error(403 if body.report_type in svc.CATALOG else 400, "forbidden" if body.report_type in svc.CATALOG else "unknown_report")
    ids = list(dict.fromkeys(body.recipient_ids))
    found = set((await db.scalars(select(User.id).where(User.id.in_(ids), User.is_active.is_(True)))).all())
    if found != set(ids):
        raise error(400, "unknown_user")
    return ids


@router.get("/users")
async def users(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    stmt = select(User.id, User.full_name, User.telegram_chat_id).where(User.is_active.is_(True))
    if q and q.strip():
        stmt = stmt.where(User.full_name.ilike(f"%{q.strip()}%"))
    return [{"id": r.id, "name": r.full_name, "telegram": bool(r.telegram_chat_id)} for r in (await db.execute(stmt.order_by(User.full_name).limit(30))).all()]


@router.get("/schedules")
async def schedules(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    rows = (await db.scalars(select(ReportSchedule).order_by(ReportSchedule.id.desc()))).all()
    return [await _schedule_out(db, s) for s in rows]


@router.get("/schedules/{sid}")
async def schedule(sid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = await db.get(ReportSchedule, sid)
    if not s:
        raise error(404, "not_found")
    return await _schedule_out(db, s)


def _apply(s: ReportSchedule, body: ScheduleIn, ids: list[int]) -> None:
    s.name, s.report_type, s.period, s.format, s.lang = body.name.strip(), body.report_type, body.period, body.format, body.lang
    s.frequency, s.hour, s.minute = body.frequency, body.hour, body.minute
    s.weekday = body.weekday if body.frequency == "weekly" else None
    s.month_day = body.month_day if body.frequency == "monthly" else None
    s.recipient_ids, s.channels, s.is_active = ids, sorted(set(body.channels)), body.is_active
    s.next_run_at = svc.next_run(s, now()) if s.is_active else None


@router.post("/schedules", status_code=201)
async def create_schedule(body: ScheduleIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    ids = await _validate(db, body, auth)
    s = ReportSchedule(created_by=auth.user.id)
    _apply(s, body, ids)
    db.add(s)
    await db.flush()
    await audit(db, request, "reports.schedule_create", actor=auth.user, entity="report_schedule", entity_id=s.id, data={"name": s.name, "type": s.report_type, "recipients": ids})
    await db.commit()
    return await _schedule_out(db, s)


@router.put("/schedules/{sid}")
async def update_schedule(sid: int, body: ScheduleIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = await db.get(ReportSchedule, sid)
    if not s:
        raise error(404, "not_found")
    ids = await _validate(db, body, auth)
    _apply(s, body, ids)
    await audit(db, request, "reports.schedule_update", actor=auth.user, entity="report_schedule", entity_id=s.id, data={"name": s.name, "recipients": ids})
    await db.commit()
    return await _schedule_out(db, s)


@router.delete("/schedules/{sid}", status_code=204)
async def delete_schedule(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    s = await db.get(ReportSchedule, sid)
    if not s:
        raise error(404, "not_found")
    await audit(db, request, "reports.schedule_delete", actor=auth.user, entity="report_schedule", entity_id=s.id, data={"name": s.name})
    await db.delete(s)
    await db.commit()


@router.post("/schedules/{sid}/run")
async def run_now(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Jadvalni hoziroq ishga tushiradi (qabul qiluvchilarga yuboriladi)."""
    s = await db.get(ReportSchedule, sid)
    if not s:
        raise error(404, "not_found")
    r, notes, tg = await svc.run_schedule(db, request.app.state.storage, s, now())
    await audit(db, request, "reports.schedule_run", actor=auth.user, entity="report_schedule", entity_id=s.id, data={"run": r.id, "status": r.status})
    await db.commit()
    await deliver(request.app, notes, telegram=False)
    for uid in tg:
        await request.app.state.queue.enqueue("deliver_report_telegram", r.id, uid)
    return _run_out(r, {auth.user.id: auth.user.full_name}, {s.id: s.name})
