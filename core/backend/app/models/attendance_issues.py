from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class AttendanceIssue(Base, TimestampMixin):
    """Davomat muammosi: xodim belgilash o'tmagan yoki noto'g'ri yozilganini bildiradi.
    Koordinator tasdiqlaydi -> HR qaror chiqaradi va tasdiqlansa yozuv avtomatik tuzatiladi (tuzatish tarixi bilan)."""

    __tablename__ = "attendance_issues"
    __table_args__ = (Index("ix_attendance_issues_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(14))  # missed_in | missed_out | wrong_checkout | other
    method_tried: Mapped[str] = mapped_column(String(8))  # qr | face | gps | other
    claimed_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str] = mapped_column(Text)
    # pending_coordinator | pending_hr | approved | rejected | cancelled
    status: Mapped[str] = mapped_column(String(20))
    coordinator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[int | None] = mapped_column(BigInteger)  # tuzatilgan davomat yozuvi
    history: Mapped[list] = mapped_column(JSONB, default=list)  # [{action, actor, level, note, at}]


class AttendanceExplanation(Base, TimestampMixin):
    """Koordinator hisobotidagi har bir kelmagan/kechikkan xodim uchun koordinatorning sabab va chorasi (HR ga hisobot)."""

    __tablename__ = "attendance_explanations"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", "kind", name="uq_attendance_explanation"),
        Index("ix_attendance_explanations_status", "status", "due_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(8))  # absent | late
    coordinator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | submitted
    reason: Mapped[str | None] = mapped_column(Text)
    measures: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    overdue_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
