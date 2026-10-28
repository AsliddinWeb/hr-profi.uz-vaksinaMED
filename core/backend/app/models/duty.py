from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class DutyChecklist(Base, TimestampMixin):
    """Ish chek-listi: bo'limga (shu bo'limdagi hamma) yoki lavozimga biriktiriladi. Xodim kunlik/haftalik to'ldiradi.
    `items`: [{id, text, kind: yesno|score, required}]."""

    __tablename__ = "duty_checklists"
    __table_args__ = (Index("ix_duty_checklists_dept", "department_id"), Index("ix_duty_checklists_pos", "position_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(300))
    scope: Mapped[str] = mapped_column(String(10))  # department | position
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"))
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"))
    frequency: Mapped[str] = mapped_column(String(8), default="daily")  # daily | weekly
    deadline_time: Mapped[time] = mapped_column(Time, default=time(20, 0))  # shu vaqtgacha to'ldirilmasa kechikkan hisoblanadi
    items: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class DutyRun(Base, TimestampMixin):
    """Xodimning davr (kun/hafta) uchun chek-list natijasi. `completed_at` bo'sh: bajarilmagan (kechikish xabari yuborilgan bo'lishi mumkin)."""

    __tablename__ = "duty_runs"
    __table_args__ = (UniqueConstraint("checklist_id", "employee_id", "period_date", name="uq_duty_runs_period"), Index("ix_duty_runs_period", "period_date"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("duty_checklists.id", ondelete="CASCADE"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    period_date: Mapped[date] = mapped_column(Date)  # kunlik: o'sha kun; haftalik: hafta dushanbasi
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)  # {item_id: true|false|1..5}
    note: Mapped[str | None] = mapped_column(Text)
    score_pct: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    late: Mapped[bool] = mapped_column(Boolean, default=False)  # muddatdan keyin topshirilgan
    late_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
