"""Davomat: QR token, keldi/ketdi belgilash, kech/erta hisobi, kun holati."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import error
from app.geo import haversine_m, valid_coordinates
from app.models.attendance import AttendanceRecord
from app.models.employees import Employee
from app.models.org import Branch
from app.models.schedule import ShiftTemplate
from app.services import schedule as sched
from app.timeutil import local_date, localize, now

QR_WINDOW_S = 60  # QR har daqiqa yangilanadi; joriy va oldingi oyna qabul qilinadi
PUNCH_BEFORE_MIN = 180  # smena boshlanishidan shuncha oldin kelishni belgilash mumkin
PUNCH_AFTER_MIN = 180  # smena tugagandan keyin shuncha vaqt ichida ketishni belgilash mumkin
MIN_GAP_S = 60  # ketma-ket belgilash orasidagi minimal vaqt
MAX_ACCURACY_M = 150  # GPS aniqligi shundan yomon bo'lsa rad etiladi
MAX_SHIFT_HOURS = 36


# --- QR ---------------------------------------------------------------------------------


def _sig(branch_id: int, epoch: int, window: int) -> str:
    key = get_settings().secret_key.encode()
    msg = f"attendance-qr:{branch_id}:{epoch}:{window}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:20]


def make_qr_token(branch: Branch, moment: datetime | None = None) -> str:
    window = int((moment or now()).timestamp()) // QR_WINDOW_S
    return f"{branch.id}.{window}.{_sig(branch.id, branch.qr_epoch, window)}"


async def verify_qr_token(db: AsyncSession, token: str, moment: datetime | None = None) -> Branch:
    try:
        branch_id_s, window_s, sig = token.strip().split(".")
        branch_id, window = int(branch_id_s), int(window_s)
    except ValueError:
        raise error(400, "qr_invalid") from None
    branch = await db.get(Branch, branch_id)
    if not branch or not branch.is_active:
        raise error(400, "qr_invalid")
    current = int((moment or now()).timestamp()) // QR_WINDOW_S
    if not hmac.compare_digest(sig, _sig(branch.id, branch.qr_epoch, window)):
        raise error(400, "qr_invalid")
    if window > current or current - window > 1:
        raise error(400, "qr_expired")
    return branch


# --- Hisoblash --------------------------------------------------------------------------


@dataclass
class Metrics:
    late: int
    early: int
    worked: int


def compute_metrics(
    shift: ShiftTemplate | None,
    planned_start: datetime | None,
    planned_end: datetime | None,
    check_in: datetime,
    check_out: datetime | None,
) -> Metrics:
    """Kechikish/erta ketish (imtiyozdan oshsa, smena vaqtidan boshlab) va sof ishlagan daqiqalar."""
    late = early = worked = 0
    track = bool(shift and shift.track_lateness)
    if track and planned_start:
        delta = int((check_in - planned_start).total_seconds() // 60)
        if delta > shift.late_grace_minutes:  # type: ignore[union-attr]
            late = delta
    if check_out:
        span = int((check_out - check_in).total_seconds() // 60)
        brk = shift.break_minutes if shift else 0
        worked = span - brk if brk and span > brk else span
        if track and planned_end:
            delta = int((planned_end - check_out).total_seconds() // 60)
            if delta > shift.early_leave_grace_minutes:  # type: ignore[union-attr]
                early = delta
    return Metrics(late, early, max(worked, 0))


def planned_window(shift: ShiftTemplate | None, day: date) -> tuple[datetime | None, datetime | None]:
    if shift is None:
        return None, None
    start, end = sched.shift_window(shift, day)
    return localize(start), localize(end)


def apply_metrics(rec: AttendanceRecord, shift: ShiftTemplate | None) -> None:
    m = compute_metrics(shift, rec.planned_start, rec.planned_end, rec.check_in_at, rec.check_out_at)
    rec.late_minutes, rec.early_leave_minutes, rec.worked_minutes = m.late, m.early, m.worked


# --- Kun holati -------------------------------------------------------------------------


def day_status(
    cell: sched.Resolved,
    rec: AttendanceRecord | None,
    shift: ShiftTemplate | None,
    day: date,
    moment: datetime,
    attendance_required: bool = True,
    leave: bool = False,
) -> str:
    """Tabel/hisobot kodi: off | holiday | future | pending | absent | working | present | late |
    early | late_early | no_checkout | incomplete | unscheduled | leave | exempt | no_shift."""
    today = local_date(moment)
    if rec is not None:
        if rec.check_out_at is None:
            end = rec.planned_end
            over = (end is not None and moment > end + timedelta(minutes=PUNCH_AFTER_MIN)) or (
                end is None and moment - rec.check_in_at > timedelta(hours=MAX_SHIFT_HOURS // 3)
            )
            return "no_checkout" if over or day < today else "working"
        if not cell.working and rec.shift_id is None and not rec.planned_start:
            return "unscheduled"
        if shift and shift.kind == "flexible" and shift.min_work_minutes and rec.worked_minutes < shift.min_work_minutes:
            return "incomplete"
        if rec.late_minutes and rec.early_leave_minutes:
            return "late_early"
        if rec.late_minutes:
            return "late"
        if rec.early_leave_minutes:
            return "early"
        return "present"
    if not cell.working:
        return "holiday" if cell.reason == "holiday" else "off"
    if leave:
        return "leave"  # tasdiqlangan kunlik ruxsat (javob olish)
    if not attendance_required:
        return "exempt"
    if shift is None:
        return "no_shift"
    if day > today:
        return "future"
    _, end = planned_window(shift, day)
    if day == today and end is not None and moment <= end:
        return "pending"
    return "absent"


# --- Belgilash --------------------------------------------------------------------------


async def current_employee(db: AsyncSession, user_id: int) -> Employee:
    emp = await db.scalar(select(Employee).where(Employee.user_id == user_id))
    if not emp:
        raise error(409, "no_employee_profile")
    if emp.status != "active":
        raise error(409, "employee_dismissed")
    return emp


def check_location(branch: Branch | None, lat: float | None, lng: float | None, accuracy: float | None, method: str) -> int | None:
    """Geofence tekshiruvi. Masofani (metr) qaytaradi, filialda koordinata bo'lmasa None."""
    has_geo = bool(branch and branch.latitude is not None and branch.longitude is not None)
    if not has_geo:
        if method == "gps":
            raise error(409, "branch_no_geo")
        return None
    if not valid_coordinates(lat, lng):
        raise error(400, "location_required")
    if accuracy is not None and accuracy > MAX_ACCURACY_M:
        raise error(400, "accuracy_too_low", accuracy=round(accuracy), max=MAX_ACCURACY_M)
    dist = round(haversine_m(lat, lng, float(branch.latitude), float(branch.longitude)))  # type: ignore[arg-type, union-attr]
    if dist > branch.geofence_radius_m:  # type: ignore[union-attr]
        raise error(400, "outside_geofence", distance=dist, radius=branch.geofence_radius_m)  # type: ignore[union-attr]
    return dist


async def _context(db: AsyncSession, emp: Employee, moment: datetime):
    """Hozirgi vaqtga mos (hali yopilmagan) smena kuni: (work_date, shift) yoki None."""
    today = local_date(moment)
    cells = (await sched.resolve_range(db, [emp], today - timedelta(days=1), today + timedelta(days=1)))[emp.id]
    taken = {
        r.work_date
        for r in (
            await db.scalars(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == emp.id,
                    AttendanceRecord.work_date.between(today - timedelta(days=1), today + timedelta(days=1)),
                )
            )
        ).all()
    }
    shifts = {s.id: s for s in (await db.scalars(select(ShiftTemplate))).all()}
    best: tuple[float, date, ShiftTemplate] | None = None
    for cell in cells:
        if not cell.working or cell.shift_id is None or cell.date in taken:
            continue
        shift = shifts[cell.shift_id]
        start, end = planned_window(shift, cell.date)
        assert start and end
        if start - timedelta(minutes=PUNCH_BEFORE_MIN) <= moment <= end + timedelta(minutes=PUNCH_AFTER_MIN):
            dist = abs((moment - start).total_seconds())
            if best is None or dist < best[0]:
                best = (dist, cell.date, shift)
    return (best[1], best[2]) if best else (today, None)


async def punch(
    db: AsyncSession,
    emp: Employee,
    *,
    method: str,
    token: str | None,
    lat: float | None,
    lng: float | None,
    accuracy: float | None,
    moment: datetime | None = None,
) -> tuple[str, AttendanceRecord]:
    """Ochiq yozuv bo'lsa ketish, bo'lmasa kelish. ('check_in'|'check_out', yozuv)."""
    moment = moment or now()
    if method == "qr":
        if not token:
            raise error(400, "qr_invalid")
        branch = await verify_qr_token(db, token, moment)
    else:
        branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
        if branch is None:
            raise error(409, "no_branch")
    dist = check_location(branch, lat, lng, accuracy, method)
    loc = {"lat": Decimal(str(round(lat, 6))), "lng": Decimal(str(round(lng, 6)))} if valid_coordinates(lat, lng) else {"lat": None, "lng": None}  # type: ignore[arg-type]

    open_rec = await db.scalar(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.employee_id == emp.id,
            AttendanceRecord.check_out_at.is_(None),
            AttendanceRecord.check_in_at >= moment - timedelta(hours=MAX_SHIFT_HOURS),
        )
        .order_by(AttendanceRecord.check_in_at.desc())
        .limit(1)
        .with_for_update()
    )
    if open_rec:
        if (moment - open_rec.check_in_at).total_seconds() < MIN_GAP_S:
            raise error(429, "too_soon")
        open_rec.check_out_at = moment
        open_rec.out_method = method
        open_rec.out_lat, open_rec.out_lng, open_rec.out_distance_m = loc["lat"], loc["lng"], dist
        shift = await db.get(ShiftTemplate, open_rec.shift_id) if open_rec.shift_id else None
        apply_metrics(open_rec, shift)
        await db.flush()
        return "check_out", open_rec

    work_date, shift = await _context(db, emp, moment)
    if await db.scalar(
        select(AttendanceRecord.id).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == work_date)
    ):
        raise error(409, "already_checked_out")
    start, end = planned_window(shift, work_date)
    rec = AttendanceRecord(
        employee_id=emp.id, work_date=work_date, shift_id=shift.id if shift else None,
        planned_start=start, planned_end=end, shift_kind=shift.kind if shift else None,
        track_lateness=bool(shift and shift.track_lateness), check_in_at=moment, in_method=method,
        branch_id=branch.id if branch else None, in_lat=loc["lat"], in_lng=loc["lng"], in_distance_m=dist,
    )  # fmt: skip
    apply_metrics(rec, shift)
    db.add(rec)
    await db.flush()
    return "check_in", rec


# --- Qo'lda tuzatish --------------------------------------------------------------------


def record_snapshot(r: AttendanceRecord) -> dict[str, Any]:
    return {
        "check_in_at": r.check_in_at.isoformat(),
        "check_out_at": r.check_out_at.isoformat() if r.check_out_at else None,
        "shift_id": r.shift_id,
        "late_minutes": r.late_minutes,
        "early_leave_minutes": r.early_leave_minutes,
        "worked_minutes": r.worked_minutes,
        "note": r.note,
    }


def validate_times(check_in: datetime, check_out: datetime | None, work_date: date) -> None:
    if check_out is not None:
        if check_out <= check_in:
            raise error(400, "out_before_in")
        if check_out - check_in > timedelta(hours=MAX_SHIFT_HOURS):
            raise error(400, "shift_too_long")
    if abs((local_date(check_in) - work_date).days) > 1:
        raise error(400, "time_date_mismatch")
