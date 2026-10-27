from datetime import date, datetime

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class ReportSchedule(Base, TimestampMixin):
    """Jadvalli hisobot: davr (period), format, chastota va qabul qiluvchilar. Keyingi ishga tushish `next_run_at` da."""

    __tablename__ = "report_schedules"
    __table_args__ = (Index("ix_report_schedules_due", "is_active", "next_run_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    report_type: Mapped[str] = mapped_column(String(24))
    period: Mapped[str] = mapped_column(String(12), default="last_week")  # yesterday | last_7d | last_week | this_month | last_month
    format: Mapped[str] = mapped_column(String(4), default="xlsx")  # xlsx | pdf
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    frequency: Mapped[str] = mapped_column(String(8), default="weekly")  # daily | weekly | monthly
    hour: Mapped[int] = mapped_column(Integer, default=8)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    weekday: Mapped[int | None] = mapped_column(Integer)  # 0=dushanba (weekly)
    month_day: Mapped[int | None] = mapped_column(Integer)  # 1..28 (monthly)
    recipient_ids: Mapped[list] = mapped_column(JSONB, default=list)
    channels: Mapped[list] = mapped_column(JSONB, default=list)  # ["app", "telegram"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(8))  # ok | failed
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ReportRun(Base):
    """Tayyor hisobot fayli (qo'lda yoki jadval bo'yicha). Fayl MinIO da, muddati o'tgach (90 kun) o'chiriladi."""

    __tablename__ = "report_runs"
    __table_args__ = (Index("ix_report_runs_user", "created_by", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("report_schedules.id", ondelete="SET NULL"))
    report_type: Mapped[str] = mapped_column(String(24))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    format: Mapped[str] = mapped_column(String(4))
    lang: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(8))  # ok | failed
    error: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(300))
    filename: Mapped[str | None] = mapped_column(String(200))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    recipient_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
