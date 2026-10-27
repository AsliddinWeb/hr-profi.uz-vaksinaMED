from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Avtomobil. `fuel_norm` — 100 km ga litr (me'yor)."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="car")  # car | van | truck | moto | other
    fuel_type: Mapped[str] = mapped_column(String(10), default="petrol")  # petrol | diesel | gas | propane | electric
    fuel_norm: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    tank_l: Mapped[int | None] = mapped_column(Integer)
    odometer_km: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(8), default="active")  # active | service | retired
    note: Mapped[str | None] = mapped_column(String(300))


class VehicleDocument(Base, TimestampMixin):
    """Hujjat va muddati: texpasport, sug'urta, texnik ko'rik, ruxsatnoma. `notified_stage`: 0 | 1 (30 kun) | 2 (7 kun) | 3 (muddati o'tgan)."""

    __tablename__ = "vehicle_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(14))  # tech_passport | insurance | osago | inspection | permit | other
    number: Mapped[str | None] = mapped_column(String(60))
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))
    notified_stage: Mapped[int] = mapped_column(Integer, default=0)


class DriverProfile(Base, TimestampMixin):
    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    license_no: Mapped[str | None] = mapped_column(String(30))
    categories: Mapped[str | None] = mapped_column(String(30))
    license_expires: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))
    notified_stage: Mapped[int] = mapped_column(Integer, default=0)


class Trip(Base, TimestampMixin):
    """Reys. Holat: planned | active | completed | cancelled."""

    __tablename__ = "trips"
    __table_args__ = (Index("ix_trips_driver_status", "driver_id", "status"), Index("ix_trips_vehicle_status", "vehicle_id", "status"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    purpose: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str | None] = mapped_column(String(200))
    destination: Mapped[str | None] = mapped_column(String(200))
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="planned")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_odometer: Mapped[int | None] = mapped_column(Integer)
    end_odometer: Mapped[int | None] = mapped_column(Integer)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(9, 1))  # odometr farqi
    gps_km: Mapped[Decimal | None] = mapped_column(Numeric(9, 1))  # GPS trek bo'yicha
    fuel_norm_l: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))  # me'yor bo'yicha litr (yakunlanganda muhrlanadi)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class GpsPoint(Base):
    __tablename__ = "gps_points"
    __table_args__ = (Index("ix_gps_trip_time", "trip_id", "recorded_at", unique=True), Index("ix_gps_vehicle_time", "vehicle_id", "recorded_at"), Index("ix_gps_driver_time", "driver_id", "recorded_at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FuelLog(Base, TimestampMixin):
    __tablename__ = "fuel_logs"
    __table_args__ = (Index("ix_fuel_vehicle_time", "vehicle_id", "fueled_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    fueled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    liters: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    price_per_liter: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    odometer_km: Mapped[int | None] = mapped_column(Integer)
    station: Mapped[str | None] = mapped_column(String(120))
    full_tank: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
