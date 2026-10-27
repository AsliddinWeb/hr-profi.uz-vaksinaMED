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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PenaltyRuleVersion(Base):
    """Jarima qoidalari versiyasi. O'zgartirish yangi versiya yaratadi: eski jarimalar o'z versiyasiga bog'langan qoladi."""

    __tablename__ = "penalty_rule_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    config: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Penalty(Base):
    """Jarima/ogohlantirish/blok. Qoida qiymatlari (bosqich, summa, blok kunlari) hisoblangan paytda muhrlanadi."""

    __tablename__ = "penalties"
    __table_args__ = (
        Index("ix_penalties_employee_date", "employee_id", "incident_date"),
        Index("ix_penalties_status", "status"),
        # Avtomatik hisob qayta ishga tushsa takrorlanmasin
        Index("uq_penalties_auto", "employee_id", "incident_date", "incident_type", unique=True, postgresql_where=text("source = 'auto'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    incident_type: Mapped[str] = mapped_column(String(14))  # late | absent | early_leave | no_checkout | discipline | other
    incident_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(8))  # auto | manual
    rule_version_id: Mapped[int | None] = mapped_column(ForeignKey("penalty_rule_versions.id", ondelete="SET NULL"))
    step: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    block_days: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(10))  # pending | approved | cancelled
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    # Blok: tasdiqlanganda foydalanuvchi hisobi vaqtincha o'chiriladi
    block_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_until: Mapped[date | None] = mapped_column(Date)
    unblocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
