"""Kompetensiyalar bazasi va lavozim profillari (rekruting zayafkasidan oldin tasdiqlanadi)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin

CATEGORIES = ("hard", "soft", "management", "knowledge", "experience")


class Competency(Base, TimestampMixin):
    """Kompaniya bo'yicha yagona kompetensiya (Hard/Soft skill, boshqaruv, bilim, tajriba). Daraja L1–L5."""

    __tablename__ = "competencies"
    __table_args__ = (Index("ix_competencies_category", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(12))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PositionProfile(Base, TimestampMixin):
    """Lavozim profili versiyasi: draft -> pending -> approved | returned. Zayafka faqat approved versiya asosida."""

    __tablename__ = "position_profiles"
    __table_args__ = (Index("ix_position_profiles_position", "position_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | pending | approved | returned | archived
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    filled_pct: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)


class ProfileCompetency(Base):
    """Profilga bog'langan kompetensiya: talab va ideal daraja, majburiyligi, baholash usuli."""

    __tablename__ = "profile_competencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("position_profiles.id", ondelete="CASCADE"), index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"), index=True)
    required_level: Mapped[int] = mapped_column(SmallInteger, default=3)
    ideal_level: Mapped[int] = mapped_column(SmallInteger, default=4)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    method: Mapped[str] = mapped_column(String(12), default="interview")  # practical | test | portfolio | interview
