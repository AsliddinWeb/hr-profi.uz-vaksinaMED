from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class ShiftTemplate(Base, TimestampMixin):
    """Smena turi. `kind=fixed`: aniq soat; `flexible`: erkin grafik (oyna ichida istalgan vaqtda).

    `end_time <= start_time` bo'lsa smena keyingi kunga o'tadi (tungi); teng bo'lsa sutkalik (24 soat).
    """

    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str | None] = mapped_column(String(4))  # grafik doskasidagi qisqa belgi
    kind: Mapped[str] = mapped_column(String(10), default="fixed")
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(SmallInteger, default=0)
    late_grace_minutes: Mapped[int] = mapped_column(SmallInteger, default=0)
    early_leave_grace_minutes: Mapped[int] = mapped_column(SmallInteger, default=0)
    min_work_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    track_lateness: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str | None] = mapped_column(String(7))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkGroup(Base, TimestampMixin):
    """Xodimlar guruhi (ish rejimi qoidalari): ofis, dorixona, ombor, xavfsizlik..."""

    __tablename__ = "work_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(20), default="office")  # office|pharmacy|warehouse|security|other
    description: Mapped[str | None] = mapped_column(String(300))
    default_shift_id: Mapped[int | None] = mapped_column(
        ForeignKey("shift_templates.id", ondelete="RESTRICT")
    )
    weekly_off_days: Mapped[list] = mapped_column(JSONB, default=list)  # 0=Dushanba ... 6=Yakshanba
    observe_holidays: Mapped[bool] = mapped_column(Boolean, default=True)
    attendance_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SchedulePattern(Base, TimestampMixin):
    """Aylanma grafik shabloni (masalan 2/2): `cycle` = [{"shift_id": int | null}, ...]."""

    __tablename__ = "schedule_patterns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    cycle: Mapped[list] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ScheduleEntry(Base):
    """Xodimning aniq sanadagi grafigi. `shift_id` bo'sh = dam kuni. Yozuv yo'q bo'lsa guruh qoidalari amal qiladi."""

    __tablename__ = "schedule_entries"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_schedule_entries_employee_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shift_templates.id", ondelete="RESTRICT"))
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | pattern | bulk
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Holiday(Base):
    """Bayram yoki ko'chirilgan ish kuni. `year` bo'sh = har yili (month/day bo'yicha)."""

    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int | None] = mapped_column(SmallInteger)
    month: Mapped[int] = mapped_column(SmallInteger)
    day: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="holiday")  # holiday | workday
    note: Mapped[str | None] = mapped_column(Text)
