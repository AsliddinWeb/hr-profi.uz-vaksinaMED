from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiSettings(Base):
    """Bitta qator (id=1): AI ni yoqish/o'chirish, model, kunlik limit, funksiyalar."""

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    model: Mapped[str] = mapped_column(String(80), default="claude-haiku-5-5")
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)  # bir foydalanuvchiga kuniga so'rovlar
    features: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"summary": true, "resume": true, "ticket": true}
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiRequest(Base):
    """Har bir AI so'rovi: kim, qaysi funksiya, token hisobi (xarajat va audit uchun). Matn saqlanmaydi."""

    __tablename__ = "ai_requests"
    __table_args__ = (Index("ix_ai_requests_user_day", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    feature: Mapped[str] = mapped_column(String(12))
    entity: Mapped[str | None] = mapped_column(String(16))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(String(120))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiSummary(Base):
    """Xulosa keshi: kirish matni o'zgarmasa qayta so'ralmaydi."""

    __tablename__ = "ai_summaries"
    __table_args__ = (UniqueConstraint("entity", "entity_id", "lang", name="uq_ai_summary"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    lang: Mapped[str] = mapped_column(String(2))
    input_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
