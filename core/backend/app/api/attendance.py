"""Davomat: keldi/ketdi, QR, kunlik hisobot, tabel, qo'lda tuzatish."""

import asyncio
import io
from datetime import date, datetime, timedelta
from typing import Any

import segno
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import get_employee
from app.api.schedule import MAX_BOARD_DAYS, _dept_ids, _filter_employees
from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.attendance import AttendanceCorrection, AttendanceRecord
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.models.schedule import ShiftTemplate, WorkGroup
from app.services import attendance as svc
from app.services import schedule as sched
from app.services.answers import approved_leave_days
from app.services.attendance_pdf import build_pdf
from app.services.attendance_report import aggregate
from app.services.audit import audit
from app.services.xlsx_safe import harden
from app.timeutil import local_date, localize, now, tz

router = APIRouter(prefix="/v1/attendance", tags=["attendance"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_EXPORT_EMPLOYEES = 3000
STATUSES = (
    "off holiday future pending absent working present late early late_early no_checkout "
    "incomplete unscheduled leave exempt no_shift"
).split()
# Tabelda "ishga kelgan" hisoblanadigan holatlar
ATTENDED = {"present", "late", "early", "late_early", "working", "no_checkout", "incomplete", "unscheduled"}


def record_out(r: AttendanceRecord, shift: ShiftTemplate | None = None) -> dict[str, Any]:
    return {
        "id": r.id,
        "employee_id": r.employee_id,
        "work_date": r.work_date,
        "shift_id": r.shift_id,
        "shift_name": shift.name if shift else None,
        "planned_start": r.planned_start,
        "planned_end": r.planned_end,
        "check_in_at": r.check_in_at,
        "check_out_at": r.check_out_at,
        "in_method": r.in_method,
        "out_method": r.out_method,
        "branch_id": r.branch_id,
        "in_distance_m": r.in_distance_m,
        "out_distance_m": r.out_distance_m,
        "late_minutes": r.late_minutes,
        "early_leave_minutes": r.early_leave_minutes,
        "worked_minutes": r.worked_minutes,
        "is_manual": r.is_manual,
        "note": r.note,
    }


# --- Xodimning o'zi ---------------------------------------------------------------------


@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("attendance.punch"))
):
    emp = await svc.current_employee(db, auth.user.id)
    moment = now()
    today = local_date(moment)
    cell = (await sched.resolve_range(db, [emp], today, today))[emp.id][0]
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    open_rec = await db.scalar(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.employee_id == emp.id,
            AttendanceRecord.check_out_at.is_(None),
            AttendanceRecord.check_in_at >= moment - timedelta(hours=svc.MAX_SHIFT_HOURS),
        )
        .order_by(AttendanceRecord.check_in_at.desc())
        .limit(1)
    )
    recent = (
        await db.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.employee_id == emp.id)
            .order_by(AttendanceRecord.check_in_at.desc())
            .limit(10)
        )
    ).all()
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    shift = shifts.get(cell.shift_id) if cell.shift_id else None
    return {
        "employee": {"id": emp.id, "full_name": emp.full_name},
        "today": today,
        "now": moment,
        "schedule": {
            "working": cell.working,
            "reason": cell.reason,
            "shift": sched.shift_out(shift) if shift else None,
        },
        "open_record": record_out(open_rec, shifts.get(open_rec.shift_id)) if open_rec else None,
        "recent": [record_out(r, shifts.get(r.shift_id)) for r in recent],
        "branch": (
            {"id": branch.id, "name": branch.name, "has_geo": branch.latitude is not None, "radius": branch.geofence_radius_m}
            if branch
            else None
        ),
    }


class PunchIn(BaseModel):
    method: str = Field(pattern="^(qr|gps)$")
    token: str | None = Field(default=None, max_length=100)
    lat: float | None = None
    lng: float | None = None
    accuracy: float | None = Field(default=None, ge=0)


@router.post("/punch")
async def punch(
    body: PunchIn,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.punch")),
):
    emp = await svc.current_employee(db, auth.user.id)
    try:
        action, rec = await svc.punch(
            db, emp, method=body.method, token=body.token, lat=body.lat, lng=body.lng, accuracy=body.accuracy
        )
    except Exception:
        await db.rollback()
        raise
    await db.commit()
    shift = await db.get(ShiftTemplate, rec.shift_id) if rec.shift_id else None
    return {"action": action, "record": record_out(rec, shift)}


# --- QR ---------------------------------------------------------------------------------


def _base_url(request: Request) -> str:
    configured = get_settings().public_url.rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{request.headers.get('host', request.url.netloc)}"


async def _branch(db: AsyncSession, branch_id: int) -> Branch:
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise error(404, "not_found")
    return branch


@router.get("/branches/{branch_id}/qr")
async def branch_qr(
    branch_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.qr")),
):
    branch = await _branch(db, branch_id)
    moment = now()
    token = svc.make_qr_token(branch, moment)
    url = f"{_base_url(request)}/attendance/punch?t={token}"

    def render() -> str:
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False, svgns=True, nl=False)
        return buf.getvalue().decode()

    return {
        "branch": {"id": branch.id, "number": branch.number, "name": branch.name, "has_geo": branch.latitude is not None},
        "token": token,
        "url": url,
        "svg": await asyncio.to_thread(render),
        "expires_in": svc.QR_WINDOW_S - int(moment.timestamp()) % svc.QR_WINDOW_S,
    }


@router.post("/branches/{branch_id}/qr/rotate")
async def rotate_qr(
    branch_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.qr")),
):
    """Barcha eski QR kodlarni bekor qiladi (masalan, QR rasmi tarqalib ketsa)."""
    branch = await _branch(db, branch_id)
    branch.qr_epoch += 1
    await audit(db, request, "attendance.qr_rotate", actor=auth.user, entity="branch", entity_id=branch.id,
                data={"epoch": branch.qr_epoch})  # fmt: skip
    await db.commit()
    return {"epoch": branch.qr_epoch}


# --- Kunlik va tabel hisoboti -----------------------------------------------------------


async def _rows(db: AsyncSession, employees: list[Employee], start: date, end: date):
    """Har xodim uchun [start, end] kunlari: holat kodi + yozuv."""
    moment = now()
    ctx = await sched.load_context(db, start, end)
    resolved = await sched.resolve_range(db, employees, start, end)
    ids = [e.id for e in employees]
    records: dict[tuple[int, date], AttendanceRecord] = {}
    if ids:
        for r in (
            await db.scalars(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id.in_(ids), AttendanceRecord.work_date.between(start, end)
                )
            )
        ).all():
            records[(r.employee_id, r.work_date)] = r
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    leaves = await approved_leave_days(db, ids, start, end)
    out: dict[int, list[dict[str, Any]]] = {}
    for e in employees:
        group = ctx.groups.get(e.work_group_id) if e.work_group_id else None
        group = group or ctx.default_group
        required = group.attendance_required if group else True
        days = []
        for cell in resolved[e.id]:
            rec = records.get((e.id, cell.date))
            shift = shifts.get(rec.shift_id if rec and rec.shift_id else cell.shift_id or 0)
            status = svc.day_status(cell, rec, shift, cell.date, moment, required, cell.date in leaves.get(e.id, ()))
            days.append({"date": cell.date, "status": status, "cell": cell, "record": rec, "shift": shift})
        out[e.id] = days
    return out


async def _filtered(db: AsyncSession, *, q, department_id, branch_id, group_id, stmt_only=False):
    stmt = _filter_employees(
        select(Employee), q=q, department_ids=await _dept_ids(db, department_id), branch_id=branch_id,
        group_cond=(await sched.group_condition(db, group_id) if group_id else None),
    )  # fmt: skip
    return stmt


@router.get("/daily")
async def daily(
    date_: date = Query(alias="date"),
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    stmt = await _filtered(db, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    employees = list((await db.scalars(stmt.order_by(Employee.full_name, Employee.id).limit(MAX_EXPORT_EMPLOYEES))).all())
    rows = await _rows(db, employees, date_, date_)
    summary: dict[str, int] = dict.fromkeys(STATUSES, 0)
    items = []
    for e in employees:
        d = rows[e.id][0]
        summary[d["status"]] += 1
        if status and d["status"] != status:
            continue
        rec, shift = d["record"], d["shift"]
        items.append({
            "employee": {"id": e.id, "employee_no": e.employee_no, "full_name": e.full_name},
            "status": d["status"],
            "shift": {"id": shift.id, "name": shift.name, "start_time": shift.start_time.strftime("%H:%M"), "end_time": shift.end_time.strftime("%H:%M")} if shift else None,
            "record": record_out(rec, shift) if rec else None,
        })  # fmt: skip
    total = len(items)
    return {
        "date": date_,
        "total": total,
        "page": page,
        "size": size,
        "summary": summary,
        "items": items[(page - 1) * size : page * size],
    }


def _totals(days: list[dict[str, Any]]) -> dict[str, int]:
    recs = [d["record"] for d in days if d["record"] is not None]
    return {
        "worked_days": sum(1 for d in days if d["status"] in ATTENDED),
        "absent": sum(1 for d in days if d["status"] == "absent"),
        "late_count": sum(1 for r in recs if r.late_minutes),
        "late_minutes": sum(r.late_minutes for r in recs),
        "early_count": sum(1 for r in recs if r.early_leave_minutes),
        "early_minutes": sum(r.early_leave_minutes for r in recs),
        "worked_minutes": sum(r.worked_minutes for r in recs),
        "no_checkout": sum(1 for d in days if d["status"] == "no_checkout"),
        "scheduled_days": sum(1 for d in days if d["cell"].working or d["record"] is not None),
    }


@router.get("/timesheet")
async def timesheet(
    start: date,
    end: date,
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    """Tabel: xodimlar x kunlar. Hafta, oy yoki ixtiyoriy davr (<= 42 kun)."""
    if end < start or (end - start).days + 1 > MAX_BOARD_DAYS:
        raise error(400, "range_invalid", max_days=MAX_BOARD_DAYS)
    stmt = await _filtered(db, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    employees = list(
        (await db.scalars(stmt.order_by(Employee.full_name, Employee.id).offset((page - 1) * size).limit(size))).all()
    )
    rows = await _rows(db, employees, start, end)
    positions = (
        {p.id: p.name for p in (await db.scalars(select(Position).where(Position.id.in_({e.position_id for e in employees if e.position_id})))).all()}
        if employees else {}
    )  # fmt: skip
    ctx = await sched.load_context(db, start, end)
    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "days": [
            {"date": d, "weekday": d.weekday(), "holiday": ctx.holidays[d].name if d in ctx.holidays else None}
            for d in sched.daterange(start, end)
        ],
        "rows": [
            {
                "employee": {"id": e.id, "employee_no": e.employee_no, "full_name": e.full_name, "position": positions.get(e.position_id)},
                "cells": [
                    {"status": d["status"], "record_id": d["record"].id if d["record"] else None,
                     "late": d["record"].late_minutes if d["record"] else 0,
                     "worked": d["record"].worked_minutes if d["record"] else 0}
                    for d in rows[e.id]
                ],
                "totals": _totals(rows[e.id]),
            }
            for e in employees
        ],
    }  # fmt: skip


MAX_DASHBOARD_DAYS = 62


async def _dashboard(db: AsyncSession, start: date, end: date, *, q, department_id, branch_id, group_id) -> dict[str, Any]:
    if end < start or (end - start).days + 1 > MAX_DASHBOARD_DAYS:
        raise error(400, "range_invalid", max_days=MAX_DASHBOARD_DAYS)
    stmt = await _filtered(db, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    employees = list((await db.scalars(stmt.order_by(Employee.full_name, Employee.id).limit(MAX_EXPORT_EMPLOYEES))).all())
    rows = await _rows(db, employees, start, end)
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    branches = {b.id: (f"№{b.number} {b.name}" if b.number else b.name) for b in (await db.scalars(select(Branch))).all()}
    return aggregate(employees, rows, start, end, depts, branches)


@router.get("/dashboard")
async def dashboard(
    start: date,
    end: date,
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    """Davomat tahlili: ko'rsatkichlar, kunlik dinamika, bo'lim/filial kesimi, eng ko'p kechikuvchi va kelmaganlar.
    Raqamlar tabel bilan bir manbadan (`day_status`) hisoblanadi. `previous` — oldingi teng davr ko'rsatkichlari (taqqoslash uchun)."""
    out = await _dashboard(db, start, end, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev = await _dashboard(db, prev_end - timedelta(days=days - 1), prev_end, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    out["previous"] = {"start": prev["start"], "end": prev["end"], "kpis": prev["kpis"]}
    return out


@router.get("/dashboard/pdf")
async def dashboard_pdf(
    request: Request,
    start: date,
    end: date,
    lang: str = Query(default="uz", pattern="^(uz|ru)$"),
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.read")),
):
    data = await _dashboard(db, start, end, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    parts = []
    if q:
        parts.append(q)
    if department_id and (d := await db.get(Department, department_id)):
        parts.append(d.name)
    if branch_id and (b := await db.get(Branch, branch_id)):
        parts.append(b.name)
    if group_id and (g := await db.get(WorkGroup, group_id)):
        parts.append(g.name)
    generated = now().astimezone(tz()).strftime("%d.%m.%Y %H:%M")
    content = await asyncio.to_thread(build_pdf, data, lang, ", ".join(parts) or "—", generated)
    await audit(db, request, "attendance.export_pdf", actor=auth.user, entity="attendance", data={"start": str(start), "end": str(end)})
    await db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="davomat-{start}-{end}.pdf"'})


@router.get("/timesheet/export")
async def timesheet_export(
    request: Request,
    start: date,
    end: date,
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    group_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.read")),
):
    if end < start or (end - start).days + 1 > 62:
        raise error(400, "range_invalid", max_days=62)
    stmt = await _filtered(db, q=q, department_id=department_id, branch_id=branch_id, group_id=group_id)
    employees = list((await db.scalars(stmt.order_by(Employee.full_name, Employee.id).limit(MAX_EXPORT_EMPLOYEES))).all())
    rows = await _rows(db, employees, start, end)
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    content = await asyncio.to_thread(_timesheet_xlsx, employees, rows, depts, start, end)
    await audit(db, request, "attendance.export", actor=auth.user, entity="attendance",
                data={"start": str(start), "end": str(end), "count": len(employees)})  # fmt: skip
    await db.commit()
    name = f"tabel-{start}-{end}.xlsx"
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


CODES = {
    "present": "+", "late": "K", "early": "E", "late_early": "KE", "working": "…", "no_checkout": "?",
    "incomplete": "!", "unscheduled": "+", "absent": "Y", "off": "D", "holiday": "B", "future": "", "pending": "",
    "exempt": "", "no_shift": "", "leave": "R",
}  # fmt: skip


def _timesheet_xlsx(employees, rows, depts, start: date, end: date) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Tabel"
    days = list(sched.daterange(start, end))
    head = ["№", "F.I.SH", "Bo'lim"] + [d.strftime("%d") for d in days]
    head += ["Ishlagan kun", "Kelmagan", "Kechikish (marta)", "Kechikish (daq)", "Erta ketish (daq)", "Ishlagan soat"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for i, e in enumerate(employees, 1):
        d = rows[e.id]
        t = _totals(d)
        ws.append(
            [i, e.full_name, depts.get(e.department_id, "")]
            + [CODES.get(x["status"], "") for x in d]
            + [t["worked_days"], t["absent"], t["late_count"], t["late_minutes"], t["early_minutes"], round(t["worked_minutes"] / 60, 1)]
        )
    ws.append([])
    ws.append(["Belgilar: + keldi, K kechikdi, E erta ketdi, KE ikkalasi, … ishda, ? ketish belgilanmagan, ! kam ishladi, Y kelmadi, R ruxsat bilan, D dam, B bayram"])
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 20
    ws.freeze_panes = "D2"
    buf = io.BytesIO()
    harden(wb)
    wb.save(buf)
    return buf.getvalue()


# --- Xodim tarixi va qo'lda tuzatish ----------------------------------------------------


@router.get("/employees/{employee_id}/records")
async def employee_records(
    employee_id: int,
    start: date,
    end: date,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    if end < start or (end - start).days > 366:
        raise error(400, "range_invalid")
    emp = await get_employee(db, employee_id)
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    recs = (
        await db.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date.between(start, end))
            .order_by(AttendanceRecord.work_date.desc())
        )
    ).all()
    return {"employee": {"id": emp.id, "full_name": emp.full_name}, "items": [record_out(r, shifts.get(r.shift_id or 0)) for r in recs]}


@router.get("/employees/{employee_id}/day")
async def employee_day(
    employee_id: int,
    day: date,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    """Qo'lda tuzatish formasi uchun: kun grafigi va (bor bo'lsa) yozuv."""
    emp = await get_employee(db, employee_id)
    cell = (await sched.resolve_range(db, [emp], day, day))[emp.id][0]
    rec = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == day))
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    shift = shifts.get(cell.shift_id) if cell.shift_id else None
    return {
        "employee": {"id": emp.id, "full_name": emp.full_name, "status": emp.status},
        "date": day,
        "scheduled_shift": sched.shift_out(shift) if shift else None,
        "reason": cell.reason,
        "record": record_out(rec, shifts.get(rec.shift_id or 0)) if rec else None,
    }


@router.get("/records/{record_id}")
async def get_record(
    record_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("attendance.read")),
):
    rec = await db.get(AttendanceRecord, record_id)
    if not rec:
        raise error(404, "not_found")
    emp = await db.get(Employee, rec.employee_id)
    shift = await db.get(ShiftTemplate, rec.shift_id) if rec.shift_id else None
    history = (
        await db.scalars(
            select(AttendanceCorrection)
            .where(AttendanceCorrection.employee_id == rec.employee_id, AttendanceCorrection.work_date == rec.work_date)
            .order_by(AttendanceCorrection.id.desc())
        )
    ).all()
    return {
        **record_out(rec, shift),
        "employee": {"id": emp.id, "full_name": emp.full_name} if emp else None,
        "corrections": [
            {"id": c.id, "action": c.action, "reason": c.reason, "before": c.before, "after": c.after, "actor_id": c.actor_id, "created_at": c.created_at}
            for c in history
        ],
    }  # fmt: skip


class RecordIn(BaseModel):
    check_in_at: datetime
    check_out_at: datetime | None = None
    shift_id: int | None = None
    note: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class RecordCreate(RecordIn):
    employee_id: int
    work_date: date


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else localize(dt)


async def _fill(db: AsyncSession, rec: AttendanceRecord, body: RecordIn) -> None:
    shift = None
    if body.shift_id is not None:
        shift = await db.get(ShiftTemplate, body.shift_id)
        if not shift:
            raise error(400, "unknown_shift")
    check_in, check_out = _aware(body.check_in_at), _aware(body.check_out_at)
    assert check_in is not None
    svc.validate_times(check_in, check_out, rec.work_date)
    rec.shift_id = shift.id if shift else None
    rec.shift_kind = shift.kind if shift else None
    rec.track_lateness = bool(shift and shift.track_lateness)
    rec.planned_start, rec.planned_end = svc.planned_window(shift, rec.work_date)
    rec.check_in_at, rec.check_out_at = check_in, check_out
    rec.in_method = "manual"
    rec.out_method = "manual" if check_out else None
    rec.is_manual = True
    rec.note = (body.note or "").strip() or None
    svc.apply_metrics(rec, shift)


@router.post("/records", status_code=201)
async def create_record(
    body: RecordCreate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.edit")),
):
    emp = await get_employee(db, body.employee_id)
    if await db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == body.work_date)):
        raise error(409, "record_exists")
    rec = AttendanceRecord(employee_id=emp.id, work_date=body.work_date, created_by=auth.user.id, check_in_at=now(), in_method="manual")
    await _fill(db, rec, body)
    db.add(rec)
    await db.flush()
    db.add(AttendanceCorrection(employee_id=emp.id, work_date=rec.work_date, action="create", reason=body.reason.strip(),
                                after=svc.record_snapshot(rec), actor_id=auth.user.id))  # fmt: skip
    await audit(db, request, "attendance.correct", actor=auth.user, entity="attendance", entity_id=rec.id,
                data={"action": "create", "employee_id": emp.id, "date": str(rec.work_date)}, note=body.reason.strip())  # fmt: skip
    await db.commit()
    return record_out(rec)


@router.put("/records/{record_id}")
async def update_record(
    record_id: int,
    body: RecordIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.edit")),
):
    rec = await db.get(AttendanceRecord, record_id)
    if not rec:
        raise error(404, "not_found")
    before = svc.record_snapshot(rec)
    await _fill(db, rec, body)
    db.add(AttendanceCorrection(employee_id=rec.employee_id, work_date=rec.work_date, action="update", reason=body.reason.strip(),
                                before=before, after=svc.record_snapshot(rec), actor_id=auth.user.id))  # fmt: skip
    await audit(db, request, "attendance.correct", actor=auth.user, entity="attendance", entity_id=rec.id,
                data={"action": "update", "employee_id": rec.employee_id, "date": str(rec.work_date)}, note=body.reason.strip())  # fmt: skip
    await db.commit()
    return record_out(rec)


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    record_id: int,
    request: Request,
    reason: str = Query(min_length=3, max_length=500),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("attendance.edit")),
):
    rec = await db.get(AttendanceRecord, record_id)
    if not rec:
        raise error(404, "not_found")
    db.add(AttendanceCorrection(employee_id=rec.employee_id, work_date=rec.work_date, action="delete", reason=reason.strip(),
                                before=svc.record_snapshot(rec), actor_id=auth.user.id))  # fmt: skip
    await audit(db, request, "attendance.correct", actor=auth.user, entity="attendance", entity_id=rec.id,
                data={"action": "delete", "employee_id": rec.employee_id, "date": str(rec.work_date)}, note=reason.strip())  # fmt: skip
    await db.delete(rec)
    await db.commit()

