from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class NeedCategory(Base, TimestampMixin):
    """Ehtiyoj turi (ta'mirlash, xo'jalik, IT, kanselyariya...): standart ijrochi va muddat (SLA)."""

    __tablename__ = "need_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(300))
    default_assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sla_days: Mapped[int | None] = mapped_column(Integer)  # muddat berilmasa: yaratilgandan necha kun
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NeedRequest(Base, TimestampMixin):
    """Ehtiyoj: so'rash -> ijrochi -> bajarish -> tasdiq. Holat: requested | assigned | completed | confirmed | cancelled."""

    __tablename__ = "need_requests"
    __table_args__ = (
        Index("ix_need_requests_status", "status"),
        Index("ix_need_requests_assignee", "assignee_id", "status"),
        Index("ix_need_requests_requester", "requester_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)  # E-2026-0001
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("need_categories.id", ondelete="SET NULL"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    priority: Mapped[str] = mapped_column(String(8), default="normal")
    status: Mapped[str] = mapped_column(String(12), default="requested")
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report: Mapped[str | None] = mapped_column(Text)  # ijrochining hisoboti
    rating: Mapped[int | None] = mapped_column(Integer)  # 1..5, tasdiqlashda
    confirm_note: Mapped[str | None] = mapped_column(Text)
    return_count: Mapped[int] = mapped_column(Integer, default=0)
    notified_soon: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_overdue: Mapped[bool] = mapped_column(Boolean, default=False)


class NeedEvent(Base):
    __tablename__ = "need_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("need_requests.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(12))  # requested | assigned | completed | confirmed | returned | cancelled | updated | overdue
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NeedComment(Base):
    __tablename__ = "need_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("need_requests.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NeedFile(Base):
    __tablename__ = "need_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("need_requests.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
