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


class Reminder(Base, TimestampMixin):
    """Eslatma: bir martalik yoki takrorlanuvchi. `next_at` — keyingi ishga tushish vaqti (None = tugagan)."""

    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_due", "next_at"), Index("ix_reminders_owner", "owner_id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))  # ichki yo'l, masalan /tasks/5
    recipients: Mapped[list] = mapped_column(JSONB, default=list)  # egasidan tashqari xabar oluvchilar

    repeat: Mapped[str] = mapped_column(String(8), default="once")  # once | daily | weekly | monthly | yearly
    interval: Mapped[int] = mapped_column(Integer, default=1)  # har N kun/hafta/oy/yil
    weekdays: Mapped[list] = mapped_column(JSONB, default=list)  # haftalik: 0=Du..6=Ya
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # boshlanish (vaqt va sana tayanch)
    until: Mapped[date | None] = mapped_column(Date)  # shu sanagacha (kiritilgan)

    telegram: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snooze_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fire_count: Mapped[int] = mapped_column(Integer, default=0)


class ReminderEvent(Base):
    __tablename__ = "reminder_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(12))  # created | updated | fired | snoozed | done | paused | resumed
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
