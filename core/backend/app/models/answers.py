from datetime import date, datetime, time

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class LeaveRequest(Base, TimestampMixin):
    """Javob olish: xodimning kunlik yoki soatlik ruxsat so'rovi. Koordinator -> (8 soatda javob bo'lmasa) HR."""

    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_requests_dates", "start_date", "end_date"),
        Index("ix_leave_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # day | hourly
    reason_type: Mapped[str] = mapped_column(String(12))  # sick | family | personal | business | other
    reason: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)  # soatlikda start_date bilan bir xil
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)

    # pending_coordinator | pending_hr | approved | rejected | cancelled
    status: Mapped[str] = mapped_column(String(20))
    coordinator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    escalate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_level: Mapped[str | None] = mapped_column(String(12))  # coordinator | hr
    decision_note: Mapped[str | None] = mapped_column(Text)


class LeaveEvent(Base):
    """So'rov tarixi: yuborildi, eskalatsiya, tasdiq/rad, bekor."""

    __tablename__ = "leave_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(12))  # submitted | escalated | approved | rejected | cancelled
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    level: Mapped[str | None] = mapped_column(String(12))
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
