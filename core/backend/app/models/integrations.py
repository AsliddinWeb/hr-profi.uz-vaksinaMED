from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class ApiKey(Base):
    """Tashqi tizim (Dori, FOM, 1C...) uchun API kaliti. Kalit faqat yaratilganda ko'rsatiladi; bazada faqat SHA-256 hash."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(12), unique=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[list] = mapped_column(JSONB, default=list)  # metrics:write | employees:read | branches:read
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BranchDailyMetric(Base):
    """Filialning kunlik savdosi va rejasi (tashqi tizimdan API orqali keladi)."""

    __tablename__ = "branch_daily_metrics"
    __table_args__ = (UniqueConstraint("branch_id", "metric_date", name="uq_branch_metric_day"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    sales: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    plan: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    receipts: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), default="api")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Complaint(Base, TimestampMixin):
    """Xodim shikoyati / murojaati: HR ko'rib chiqadi va javob beradi (ilgari Telegramda yurgan)."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(10))  # salary | manager | schedule | conditions | colleague | system | other
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="new")  # new | in_progress | resolved | rejected
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    response: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history: Mapped[list] = mapped_column(JSONB, default=list)  # [{action, actor, text, at}]
