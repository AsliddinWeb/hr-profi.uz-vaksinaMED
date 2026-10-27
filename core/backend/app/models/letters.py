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


class LetterTemplate(Base, TimestampMixin):
    """Tushuntirish xati shabloni. Matnda {employee_name} {position} {department} {incident_date} {incident} {explanation} {date} {company} {number}."""

    __tablename__ = "letter_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    recipient_line: Mapped[str] = mapped_column(String(300), default="")
    body_template: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)  # xodimga ko'rsatma (yozishdan oldin)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExplanationLetter(Base, TimestampMixin):
    """Tushuntirish xati: HR so'raydi -> xodim yozadi va elektron imzolaydi -> HR qabul qiladi/qaytaradi. QR orqali tekshiriladi."""

    __tablename__ = "explanation_letters"
    __table_args__ = (Index("ix_letters_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)  # TX-2026-0001
    code: Mapped[str] = mapped_column(String(32), unique=True)  # ochiq tekshiruv kodi (QR)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("letter_templates.id", ondelete="SET NULL"))

    incident_type: Mapped[str] = mapped_column(String(14))  # late | absent | early_leave | no_checkout | discipline | other
    incident_date: Mapped[date] = mapped_column(Date)
    incident_note: Mapped[str | None] = mapped_column(Text)  # nimani tushuntirish kerak
    due_date: Mapped[date | None] = mapped_column(Date)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # requested | submitted | accepted | returned | cancelled
    status: Mapped[str] = mapped_column(String(12))
    explanation: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict | None] = mapped_column(JSONB)  # imzolash paytidagi to'liq matn (keyin shablon o'zgarsa ham buzilmaydi)
    signature: Mapped[dict | None] = mapped_column(JSONB)  # {user_id, name, at, ip}
    content_hash: Mapped[str | None] = mapped_column(String(64))

    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    scan_key: Mapped[str | None] = mapped_column(String(300))
    scan_mime: Mapped[str | None] = mapped_column(String(60))
    scan_filename: Mapped[str | None] = mapped_column(String(200))
    scan_size: Mapped[int | None] = mapped_column(Integer)
    scan_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LetterEvent(Base):
    __tablename__ = "letter_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("explanation_letters.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(12))  # requested | submitted | accepted | returned | cancelled | scanned
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
