from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class MobilePermit(Base, TimestampMixin):
    """Ko'chma davomat/kuzatuv ruxsati. Kuzatuv faqat ikki shart bajarilsa ishlaydi: HR ruxsat bergan (`enabled`) va xodimning o'zi rozilik bergan (`consent_at`)."""

    __tablename__ = "mobile_permits"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_s: Mapped[int] = mapped_column(Integer, default=60)
    window_start: Mapped[time] = mapped_column(Time, default=time(8, 0))
    window_end: Mapped[time] = mapped_column(Time, default=time(20, 0))
    note: Mapped[str | None] = mapped_column(String(300))
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MobileSession(Base):
    """Ish kuni sessiyasi: xodim "boshlash" bosgandan "tugatish"gacha. Trek faqat shu paytda yoziladi."""

    __tablename__ = "mobile_sessions"
    __table_args__ = (Index("ix_mobile_sessions_employee", "employee_id", "started_at"), Index("ix_mobile_sessions_status", "status"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | ended | auto_closed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(20))  # user | window | permit_revoked | consent_revoked
    attendance_id: Mapped[int | None] = mapped_column(ForeignKey("attendance_records.id", ondelete="SET NULL"))
    attendance_created: Mapped[bool] = mapped_column(Boolean, default=False)
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lng: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    points_count: Mapped[int] = mapped_column(Integer, default=0)
    last_point_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_battery: Mapped[int | None] = mapped_column(Integer)
    last_permission: Mapped[str | None] = mapped_column(String(10))
    gps_off: Mapped[bool] = mapped_column(Boolean, default=False)
    signal_lost: Mapped[bool] = mapped_column(Boolean, default=False)
    low_battery_alerted: Mapped[bool] = mapped_column(Boolean, default=False)


class MobilePoint(Base):
    __tablename__ = "mobile_points"
    __table_args__ = (Index("ix_mobile_points_session_time", "session_id", "recorded_at", unique=True), Index("ix_mobile_points_time", "recorded_at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mobile_sessions.id", ondelete="CASCADE"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    battery: Mapped[int | None] = mapped_column(Integer)
    charging: Mapped[bool | None] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MobileEvent(Base):
    """Xavfsizlik hodisasi. kind: sos | low_battery | permission_lost | gps_off | signal_lost | signal_back | auto_closed."""

    __tablename__ = "mobile_events"
    __table_args__ = (Index("ix_mobile_events_time", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_sessions.id", ondelete="SET NULL"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(8), default="info")  # info | warning | critical
    data: Mapped[dict | None] = mapped_column(JSONB)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ack_note: Mapped[str | None] = mapped_column(Text)
