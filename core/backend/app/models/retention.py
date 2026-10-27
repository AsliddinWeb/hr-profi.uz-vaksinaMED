from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class RetentionCase(Base, TimestampMixin):
    """Ushlab qolish: ketish xavfi aniqlangan xodim. Mudir/koordinator xabar beradi -> HR suhbat -> trener yechimi ->
    haftalik uchrashuv va auditor xulosasi -> qaror (qoladi / ketadi; ketsa offboarding ochiladi)."""

    __tablename__ = "retention_cases"
    __table_args__ = (Index("ix_retention_cases_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | retained | leaving
    risk_level: Mapped[str] = mapped_column(String(6), default="medium")  # low | medium | high
    source: Mapped[str] = mapped_column(String(8), default="manual")  # manual | auto | notice
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    notice_date: Mapped[date | None] = mapped_column(Date)  # xodim ketish haqida ogohlantirgan sana
    planned_leave_date: Mapped[date | None] = mapped_column(Date)
    hr_note: Mapped[str | None] = mapped_column(Text)
    hr_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    hr_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trainer_note: Mapped[str | None] = mapped_column(Text)
    trainer_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    trainer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auditor_note: Mapped[str | None] = mapped_column(Text)
    auditor_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    auditor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(6))  # stay | leave
    decision_note: Mapped[str | None] = mapped_column(Text)
    decision_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_discussed_on: Mapped[date | None] = mapped_column(Date)
    events: Mapped[list] = mapped_column(JSONB, default=list)  # [{action, actor, text, at}]


class RetentionMeeting(Base):
    """Haftalik uchrashuv: koordinator, HR, trener, zaveduyushiy va auditor; muhokama qilingan holatlar."""

    __tablename__ = "retention_meetings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    held_on: Mapped[date] = mapped_column(Date, index=True)
    summary: Mapped[str] = mapped_column(Text)
    case_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Offboarding(Base, TimestampMixin):
    """Offboarding: exit-intervyu (sabab, ichkarida oldini olish, xavflar), choralar (vazifalar) va rasmiylashtirish."""

    __tablename__ = "offboardings"
    __table_args__ = (Index("ix_offboardings_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("retention_cases.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | completed | cancelled
    leave_date: Mapped[date | None] = mapped_column(Date)
    reason_type: Mapped[str | None] = mapped_column(String(10))  # salary | manager | workload | team | growth | personal | offer | fired | other
    reason_text: Mapped[str | None] = mapped_column(Text)
    prevent_text: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[list] = mapped_column(JSONB, default=list)  # shortage | access | understaff | others_leaving | competitor
    exit_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    measures: Mapped[list] = mapped_column(JSONB, default=list)  # [{task_id, title, assignee_id, due}]
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
