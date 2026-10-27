"""Ko'chma davomat va jonli kuzatuv: ruxsat+rozilik, sessiya, trek, xavfsizlik hodisalari.

Maxfiylik: trek faqat (1) HR ruxsat bergan, (2) xodim rozilik bergan va (3) xodim ish kunini boshlagan sessiyada,
(4) ruxsat etilgan vaqt oynasida yoziladi; xodim istalgan payt tugatishi yoki rozilikni qaytarib olishi mumkin.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.geo import haversine_m, valid_coordinates
from app.models.attendance import AttendanceRecord
from app.models.employees import Employee
from app.models.mobile import MobileEvent, MobilePermit, MobilePoint, MobileSession
from app.models.schedule import ShiftTemplate
from app.rbac import matches
from app.services import attendance as att
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, localize

MAX_ACCURACY_M = 100.0
MAX_SPEED_KMH = 250.0
LOW_BATTERY = 15
BATTERY_RESET = 30
SIGNAL_LOST_MIN = 10
WINDOW_GRACE_MIN = 30
RETENTION_DAYS = 90
MAX_BATCH = 100
KINDS = ("sos", "low_battery", "permission_lost", "gps_off", "signal_lost", "signal_back", "auto_closed")
SEVERITY = {"sos": "critical", "permission_lost": "warning", "gps_off": "warning", "low_battery": "warning", "signal_lost": "warning", "signal_back": "info", "auto_closed": "info"}

register_template("mobile.sos", {"uz": "SOS: yordam kerak!", "ru": "SOS: нужна помощь!"}, {"uz": "{employee}", "ru": "{employee}"}, "danger")
register_template("mobile.event", {"uz": "Kuzatuv hodisasi", "ru": "Событие отслеживания"}, {"uz": "{employee}: {what}", "ru": "{employee}: {what}"}, "warning")
register_template("mobile.granted", {"uz": "Kuzatuv ruxsati berildi", "ru": "Выдано разрешение на отслеживание"}, {"uz": "Ish kunini boshlashdan oldin rozilik bering", "ru": "Дайте согласие перед началом рабочего дня"}, "info")


def segment_m(a: tuple[float, float, datetime], b: tuple[float, float, datetime]) -> float | None:
    """Ikki nuqta orasidagi masofa (m); vaqt tartibsiz yoki tezlik imkonsiz bo'lsa None (GPS "sakrashi")."""
    dt = (b[2] - a[2]).total_seconds()
    d = haversine_m(a[0], a[1], b[0], b[1])
    if dt <= 0 or d / dt * 3.6 > MAX_SPEED_KMH:
        return None
    return d


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def can_read(auth: AuthContext) -> bool:
    return has(auth, "mobile.read") or has(auth, "mobile.manage")


def window_dt(permit: MobilePermit, day: date) -> tuple[datetime, datetime]:
    return localize(datetime.combine(day, permit.window_start)), localize(datetime.combine(day, permit.window_end))


def in_window(permit: MobilePermit, moment: datetime) -> bool:
    start, end = window_dt(permit, local_date(moment))
    return start <= moment <= end


def check_ready(permit: MobilePermit | None, moment: datetime) -> MobilePermit:
    if permit is None or not permit.enabled:
        raise error(403, "no_permit")
    if permit.consent_at is None:
        raise error(409, "consent_required")
    if not in_window(permit, moment):
        raise error(409, "outside_hours", start=permit.window_start.strftime("%H:%M"), end=permit.window_end.strftime("%H:%M"))
    return permit


async def employee_of(db: AsyncSession, auth: AuthContext) -> Employee:
    e = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id, Employee.status == "active"))
    if not e:
        raise error(403, "no_employee")
    return e


async def permit_of(db: AsyncSession, employee_id: int) -> MobilePermit | None:
    return await db.scalar(select(MobilePermit).where(MobilePermit.employee_id == employee_id))


async def active_session(db: AsyncSession, employee_id: int, *, lock: bool = False) -> MobileSession | None:
    stmt = select(MobileSession).where(MobileSession.employee_id == employee_id, MobileSession.status == "active").order_by(MobileSession.id.desc()).limit(1)
    return await db.scalar(stmt.with_for_update() if lock else stmt)


# --- Hodisalar ----------------------------------------------------------------------------


async def add_event(db: AsyncSession, emp: Employee, s: MobileSession | None, kind: str, moment: datetime, *, data: dict[str, Any] | None = None, lat: float | None = None, lng: float | None = None):
    ev = MobileEvent(session_id=s.id if s else None, employee_id=emp.id, kind=kind, severity=SEVERITY[kind], data=data, lat=lat, lng=lng, created_at=moment)
    db.add(ev)
    await db.flush()
    notes: list = []
    if kind in ("sos", "permission_lost", "gps_off", "low_battery", "signal_lost"):
        managers = await users_with_permission(db, "mobile.manage")
        if kind == "sos":
            notes = await notify(db, managers, "mobile.sos", link=f"/mobile/events?focus={ev.id}", params={"employee": emp.full_name})
        else:
            notes = await notify(db, managers, "mobile.event", link=f"/mobile/events?focus={ev.id}", params={"employee": emp.full_name, "what": kind})
    return ev, notes


# --- Davomat ------------------------------------------------------------------------------


async def attendance_check_in(db: AsyncSession, emp: Employee, moment: datetime, lat: float | None, lng: float | None) -> AttendanceRecord | None:
    """Ish kuni boshlanganda davomat: ochiq yozuv bo'lsa unga tegmaydi; yo'q bo'lsa `mobile` usulida yangi yozuv. Aks holda (masalan bugun allaqachon yopilgan) None."""
    open_rec = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.check_out_at.is_(None), AttendanceRecord.check_in_at >= moment - timedelta(hours=att.MAX_SHIFT_HOURS)))
    if open_rec:
        return None
    work_date, shift = await att._context(db, emp, moment)
    if await db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == work_date)):
        return None
    start, end = att.planned_window(shift, work_date)
    loc = valid_coordinates(lat, lng)
    rec = AttendanceRecord(
        employee_id=emp.id, work_date=work_date, shift_id=shift.id if shift else None, planned_start=start, planned_end=end, shift_kind=shift.kind if shift else None, track_lateness=bool(shift and shift.track_lateness),
        check_in_at=moment, in_method="mobile", in_lat=Decimal(str(round(lat, 6))) if loc else None, in_lng=Decimal(str(round(lng, 6))) if loc else None,  # type: ignore[arg-type]
    )  # fmt: skip
    att.apply_metrics(rec, shift)
    db.add(rec)
    await db.flush()
    return rec


async def attendance_check_out(db: AsyncSession, s: MobileSession, moment: datetime, lat: float | None, lng: float | None) -> None:
    if not (s.attendance_created and s.attendance_id):
        return
    rec = await db.get(AttendanceRecord, s.attendance_id)
    if not rec or rec.check_out_at is not None:
        return
    rec.check_out_at = max(moment, rec.check_in_at + timedelta(minutes=1))
    rec.out_method = "mobile"
    if valid_coordinates(lat, lng):
        rec.out_lat, rec.out_lng = Decimal(str(round(lat, 6))), Decimal(str(round(lng, 6)))  # type: ignore[arg-type]
    shift = await db.get(ShiftTemplate, rec.shift_id) if rec.shift_id else None
    att.apply_metrics(rec, shift)


async def end_session(db: AsyncSession, s: MobileSession, moment: datetime, reason: str, *, auto: bool = False, lat: float | None = None, lng: float | None = None) -> None:
    s.status, s.ended_at, s.end_reason = ("auto_closed" if auto else "ended"), moment, reason
    s.end_lat, s.end_lng = (lat, lng) if valid_coordinates(lat, lng) else (None, None)
    await attendance_check_out(db, s, moment, lat, lng)


# --- Nuqtalar -----------------------------------------------------------------------------


async def ingest(db: AsyncSession, emp: Employee, s: MobileSession, points: list[dict[str, Any]], device: dict[str, Any], moment: datetime):
    """Nuqtalarni saqlaydi (aniqlik, vaqt, takror, "sakrash" filtri) va qurilma holatidan hodisalar chiqaradi. (saqlangan, o'tkazib yuborilgan, xabarlar)."""
    notes: list = []
    last = await db.scalar(select(MobilePoint).where(MobilePoint.session_id == s.id).order_by(MobilePoint.recorded_at.desc()).limit(1))
    seen = {r for (r,) in (await db.execute(select(MobilePoint.recorded_at).where(MobilePoint.session_id == s.id, MobilePoint.recorded_at.in_([p["at"] for p in points])))).all()} if points else set()
    saved = skipped = 0
    meters = 0.0
    chain: list[tuple[float, float, datetime]] = [(last.lat, last.lng, last.recorded_at)] if last else []
    battery = device.get("battery")
    for p in sorted(points, key=lambda x: x["at"]):
        acc = p.get("accuracy")
        bad = p["at"] in seen or p["at"] > moment + timedelta(minutes=2) or p["at"] < s.started_at - timedelta(minutes=5) or not valid_coordinates(p["lat"], p["lng"]) or (acc is not None and acc > MAX_ACCURACY_M)
        step = 0.0
        if not bad and chain:
            m = segment_m(chain[-1], (p["lat"], p["lng"], p["at"]))
            if m is None:
                bad = True  # imkonsiz tezlik: GPS "sakrashi"
            else:
                step = m
        if bad:
            skipped += 1
            continue
        seen.add(p["at"])
        meters += step
        db.add(MobilePoint(session_id=s.id, employee_id=emp.id, lat=p["lat"], lng=p["lng"], accuracy_m=acc, speed_kmh=p.get("speed"), heading=p.get("heading"), battery=battery, charging=device.get("charging"), recorded_at=p["at"]))
        chain.append((p["lat"], p["lng"], p["at"]))
        saved += 1
    if saved:
        s.distance_km = Decimal(str(s.distance_km)) + Decimal(str(round(meters / 1000, 3)))
        s.points_count += saved
        s.last_point_at = max(c[2] for c in chain)
        if s.signal_lost:
            s.signal_lost = False
            _, n = await add_event(db, emp, s, "signal_back", moment)
            notes += n
    # qurilma holati
    if battery is not None:
        s.last_battery = battery
        charging = bool(device.get("charging"))
        if battery <= LOW_BATTERY and not charging and not s.low_battery_alerted:
            s.low_battery_alerted = True
            _, n = await add_event(db, emp, s, "low_battery", moment, data={"battery": battery})
            notes += n
        elif battery >= BATTERY_RESET or charging:
            s.low_battery_alerted = False
    perm = device.get("permission")
    if perm:
        if perm != "granted" and s.last_permission != perm:
            _, n = await add_event(db, emp, s, "permission_lost", moment, data={"state": perm})
            notes += n
        s.last_permission = perm
    gps = device.get("gps_enabled")
    if gps is False and not s.gps_off:
        s.gps_off = True
        _, n = await add_event(db, emp, s, "gps_off", moment)
        notes += n
    elif gps is True:
        s.gps_off = False
    return saved, skipped, notes


async def watch(db: AsyncSession, moment: datetime) -> tuple[int, list]:
    """Faol sessiyalar: signal uzilishi (bir martadan) va ruxsat oynasi tugagach avtomatik yopish; kuniga bir marta eski nuqtalarni o'chirish."""
    from sqlalchemy import delete

    notes: list = []
    count = 0
    for s in (await db.scalars(select(MobileSession).where(MobileSession.status == "active"))).all():
        emp = await db.get(Employee, s.employee_id)
        p = await permit_of(db, s.employee_id)
        if emp is None:
            continue
        if p is not None:
            _, w_end = window_dt(p, local_date(s.started_at))
            if moment > w_end + timedelta(minutes=WINDOW_GRACE_MIN):
                await end_session(db, s, min(moment, w_end), "window", auto=True)
                _, n = await add_event(db, emp, s, "auto_closed", moment)
                notes += n
                count += 1
                continue
        if not s.signal_lost and moment - (s.last_point_at or s.started_at) > timedelta(minutes=SIGNAL_LOST_MIN):
            s.signal_lost = True
            _, n = await add_event(db, emp, s, "signal_lost", moment, data={"last_point_at": (s.last_point_at or s.started_at).isoformat(), "battery": s.last_battery})
            notes += n
            count += 1
    if moment.hour == 3 and moment.minute < 2:
        await db.execute(delete(MobilePoint).where(MobilePoint.recorded_at < moment - timedelta(days=RETENTION_DAYS)))
    return count, notes
