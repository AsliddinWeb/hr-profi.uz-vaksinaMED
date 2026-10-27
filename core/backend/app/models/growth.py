from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class HrSetting(Base):
    """HR sozlamalari (attestatsiya mezoni, yig'ma ball og'irliklari): kalit -> JSON."""

    __tablename__ = "hr_settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerLevel(Base, TimestampMixin):
    """Lavozim zinapoyasi (stajyor -> farmatsevt -> katta farmatsevt -> mudir -> koordinator). Har daraja tashkiliy lavozimga bog'lanadi."""

    __tablename__ = "career_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Attestation(Base, TimestampMixin):
    """Oylik attestatsiya: test va amaliy ball, trener/mudir/koordinator fidbeki va HR qarori."""

    __tablename__ = "attestations"
    __table_args__ = (UniqueConstraint("employee_id", "month", name="uq_attestation_month"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    level_id: Mapped[int | None] = mapped_column(ForeignKey("career_levels.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | scored | decided
    test_score: Mapped[float | None] = mapped_column(Float)
    practical_score: Mapped[float | None] = mapped_column(Float)
    total: Mapped[float | None] = mapped_column(Float)
    feedbacks: Mapped[list] = mapped_column(JSONB, default=list)  # [{role, author, text, at}]
    decision: Mapped[str | None] = mapped_column(String(14))  # passed | retake | extra_lessons
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Promotion(Base, TimestampMixin):
    """O'sish taklifi: yaratiladi (qo'lda yoki attestatsiyalardan avtomatik) -> HRD tasdiqlaydi -> lavozim o'zgaradi."""

    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    from_level_id: Mapped[int | None] = mapped_column(ForeignKey("career_levels.id", ondelete="SET NULL"))
    to_level_id: Mapped[int | None] = mapped_column(ForeignKey("career_levels.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="proposed")  # proposed | applied | rejected
    source: Mapped[str] = mapped_column(String(8), default="manual")  # manual | auto
    basis: Mapped[str | None] = mapped_column(Text)
    proposed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
