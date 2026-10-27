from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class AttendanceRecord(Base, TimestampMixin):
    """Bir smena uchun keldi/ketdi. `work_date` = smena boshlangan sana (tungi smenada ketish keyingi kunda)."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),
        Index("ix_attendance_work_date", "work_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shift_templates.id", ondelete="SET NULL"))
    # Smena vaqti yozuv paytida muhrlanadi: keyin smena o'zgarsa ham tarix buzilmaydi
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shift_kind: Mapped[str | None] = mapped_column(String(10))
    track_lateness: Mapped[bool] = mapped_column(Boolean, default=True)

    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_method: Mapped[str] = mapped_column(String(10))  # qr | gps | manual | face
    out_method: Mapped[str | None] = mapped_column(String(10))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    in_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    in_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    in_distance_m: Mapped[int | None] = mapped_column(Integer)
    out_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    out_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    out_distance_m: Mapped[int | None] = mapped_column(Integer)

    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("migration_batches.id", ondelete="SET NULL"), index=True)


class AttendanceCorrection(Base):
    """Qo'lda tuzatishlar tarixi: kim, nima uchun, oldin/keyin qanday edi."""

    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(10))  # create | update | delete
    reason: Mapped[str] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
