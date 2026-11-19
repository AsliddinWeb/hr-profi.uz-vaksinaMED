"""CRM: savdo voronkasi (bitimlar), rejalashtirilgan faoliyatlar va o'ng paneldagi muhokama (xabar, eslatma, tarix)."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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


class CrmStage(Base, TimestampMixin):
    """Voronka bosqichi. Bitim shu bosqichga o'tganda ehtimollik va (ixtiyoriy) avtomatik faoliyat qo'yiladi."""

    __tablename__ = "crm_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    probability: Mapped[int] = mapped_column(Integer, default=10)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_activity: Mapped[str | None] = mapped_column(String(160))  # bosqichga o'tganda yaratiladigan faoliyat nomi
    auto_activity_kind: Mapped[str] = mapped_column(String(10), default="call")
    auto_activity_days: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CrmDeal(Base, TimestampMixin):
    """Bitim (imkoniyat). Kanban ustuni = `stage_id`, ustun ichidagi tartib = `position`."""

    __tablename__ = "crm_deals"
    __table_args__ = (
        Index("ix_crm_deals_stage", "stage_id", "position"),
        Index("ix_crm_deals_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(160))
    contact_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(160))
    amount: Mapped[float] = mapped_column(Float, default=0)
    probability: Mapped[int] = mapped_column(Integer, default=10)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0..3 yulduz
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    source: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    expected_close: Mapped[date | None] = mapped_column(Date)
    stage_id: Mapped[int] = mapped_column(ForeignKey("crm_stages.id", ondelete="RESTRICT"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    position: Mapped[float] = mapped_column(Float, default=0)
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_reason: Mapped[str | None] = mapped_column(String(300))
    stage_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrmActivity(Base, TimestampMixin):
    """Rejalashtirilgan faoliyat: qo'ng'iroq, uchrashuv, xat, vazifa. Muddati o'tsa mas'ulga bir marta xabar boradi."""

    __tablename__ = "crm_activities"
    __table_args__ = (Index("ix_crm_activities_open", "assignee_id", "done_at", "due_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("crm_deals.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="call")  # call | meeting | email | task
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    result: Mapped[str | None] = mapped_column(Text)
    auto: Mapped[bool] = mapped_column(Boolean, default=False)  # bosqich avtomatikasi yaratgan
    notified_overdue: Mapped[bool] = mapped_column(Boolean, default=False)


class CrmMessage(Base):
    """O'ng paneldagi lenta: xabar (message), ichki eslatma (note) va avtomatik yozuv (event: bosqich, maydon, faoliyat)."""

    __tablename__ = "crm_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("crm_deals.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # message | note | event
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
