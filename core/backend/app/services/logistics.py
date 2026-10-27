"""Logistika: GPS trek masofasi, hujjat muddati bosqichlari, yoqilg'i me'yori."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.geo import haversine_m, valid_coordinates
from app.models.employees import Employee
from app.models.logistics import DriverProfile, GpsPoint, Vehicle, VehicleDocument
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

DOC_KINDS = ("tech_passport", "insurance", "osago", "inspection", "permit", "other")
MAX_ACCURACY_M = 100.0  # shundan yomon aniqlikdagi nuqta tashlab yuboriladi
MAX_SPEED_KMH = 220.0  # nuqtalar orasidagi ruxsat etilgan eng katta tezlik (GPS "sakrash"ni kesadi)
STALE_MIN = 5  # shuncha daqiqa signal bo'lmasa, mashina "signalsiz"
MAX_BATCH = 100

register_template("logistics.expiry", {"uz": "Hujjat muddati", "ru": "Срок документа"}, {"uz": "{subject}: {what} ({status})", "ru": "{subject}: {what} ({status})"}, "warning")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "logistics.read") or has(auth, "logistics.manage")


def can_manage(auth: AuthContext) -> bool:
    return has(auth, "logistics.manage")


def dec(v: Any, places: str = "0.1") -> Decimal:
    return Decimal(str(v)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def path_km(points: list[tuple[float, float, datetime]]) -> Decimal:
    """Trek uzunligi (km). Vaqt bo'yicha tartiblangan nuqtalar; imkonsiz tezlikdagi "sakrash"lar hisobga olinmaydi."""
    total = 0.0
    for (a_lat, a_lng, a_t), (b_lat, b_lng, b_t) in zip(points, points[1:], strict=False):
        d = haversine_m(a_lat, a_lng, b_lat, b_lng)
        dt = (b_t - a_t).total_seconds()
        if dt <= 0 or d / dt * 3.6 > MAX_SPEED_KMH:
            continue
        total += d
    return dec(total / 1000)


def clean_point(p: dict[str, Any]) -> bool:
    if not valid_coordinates(p.get("lat"), p.get("lng")):
        return False
    acc = p.get("accuracy")
    return acc is None or acc <= MAX_ACCURACY_M


def norm_liters(distance_km: Decimal | float | None, norm: Decimal | float) -> Decimal:
    return dec(Decimal(str(distance_km or 0)) * Decimal(str(norm)) / 100, "0.01")


def doc_stage(expires: date, today: date) -> int:
    """0 = muddat uzoq; 1 = 30 kun ichida; 2 = 7 kun ichida; 3 = muddati o'tgan."""
    days = (expires - today).days
    return 3 if days < 0 else 2 if days <= 7 else 1 if days <= 30 else 0


async def check_expiry(db: AsyncSession, today: date) -> tuple[int, list]:
    """Hujjat va guvohnoma muddati: har bosqich uchun bir martadan logistika menejerlariga xabar."""
    managers = await users_with_permission(db, "logistics.manage")
    notes: list = []
    count = 0
    plates = {v.id: v.plate for v in (await db.scalars(select(Vehicle))).all()}
    for d in (await db.scalars(select(VehicleDocument))).all():
        stage = doc_stage(d.expires_at, today)
        if stage > d.notified_stage:
            d.notified_stage = stage
            count += 1
            notes += await notify(db, managers, "logistics.expiry", link=f"/logistics/vehicles/{d.vehicle_id}", params={"subject": plates.get(d.vehicle_id, "—"), "what": d.kind, "status": d.expires_at.strftime("%d.%m.%Y")})
    emps = {e.id: e.full_name for e in (await db.scalars(select(Employee))).all()}
    for p in (await db.scalars(select(DriverProfile).where(DriverProfile.license_expires.is_not(None)))).all():
        stage = doc_stage(p.license_expires, today)  # type: ignore[arg-type]
        if stage > p.notified_stage:
            p.notified_stage = stage
            count += 1
            notes += await notify(db, managers, "logistics.expiry", link=f"/logistics/drivers/{p.employee_id}/edit", params={"subject": emps.get(p.employee_id, "—"), "what": "license", "status": p.license_expires.strftime("%d.%m.%Y")})  # type: ignore[union-attr]
    return count, notes


async def vehicle_points(db: AsyncSession, trip_id: int) -> list[GpsPoint]:
    return list((await db.scalars(select(GpsPoint).where(GpsPoint.trip_id == trip_id).order_by(GpsPoint.recorded_at))).all())
