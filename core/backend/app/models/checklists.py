from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
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


class ChecklistTemplate(Base, TimestampMixin):
    """Koordinator tekshiruv shabloni. `items`: [{id, section, text, kind: yesno|score, weight, required, critical}]."""

    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(300))
    items: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ChecklistVisit(Base, TimestampMixin):
    """Filialga borish: GPS tasdig'i, shablon nusxasi (`answers`) va hisoblangan ball."""

    __tablename__ = "checklist_visits"
    __table_args__ = (
        Index("ix_checklist_visits_branch", "branch_id", "submitted_at"),
        Index("ix_checklist_visits_coord", "coordinator_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("checklist_templates.id", ondelete="SET NULL"))
    template_name: Mapped[str] = mapped_column(String(160))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    coordinator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | submitted
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    geo_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    geo_reason: Mapped[str | None] = mapped_column(String(300))  # filialdan tashqarida boshlangan bo'lsa sabab
    answers: Mapped[list] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)  # 0..100
    critical_fails: Mapped[int] = mapped_column(Integer, default=0)


class ChecklistFile(Base):
    __tablename__ = "checklist_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("checklist_visits.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(String(16))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
