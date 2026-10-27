from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
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


class MigrationBatch(Base):
    """Eski tizimdan bitta fayl importi. status: draft | previewed | applied | rolled_back."""

    __tablename__ = "migration_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset: Mapped[str] = mapped_column(String(12))  # employees | attendance
    filename: Mapped[str] = mapped_column(String(200))
    file_key: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    headers: Mapped[list] = mapped_column(JSONB, default=list)
    mapping: Mapped[dict] = mapped_column(JSONB, default=dict)  # {maydon: fayl sarlavhasi}
    options: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # qatorlar, yaratilgan, o'tkazilgan, xato, solishtirish
    issues: Mapped[list] = mapped_column(JSONB, default=list)  # birinchi 500 muammoli qator
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MigrationMapping(Base, TimestampMixin):
    """Saqlangan ustun moslashtirishi (shablon): keyingi fayllarda qayta ishlatiladi."""

    __tablename__ = "migration_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    dataset: Mapped[str] = mapped_column(String(12))
    mapping: Mapped[dict] = mapped_column(JSONB, default=dict)
    options: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class MigrationLegacyId(Base):
    """Eski tizimdagi identifikator -> yangi yozuv (davomat tarixi xodimga shu orqali bog'lanadi)."""

    __tablename__ = "migration_legacy_ids"
    __table_args__ = (UniqueConstraint("entity", "legacy_id", name="uq_legacy_entity_id"), Index("ix_legacy_entity", "entity", "entity_id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity: Mapped[str] = mapped_column(String(12))  # employee
    legacy_id: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("migration_batches.id", ondelete="CASCADE"))


class MigrationCheck(Base, TimestampMixin):
    """Eski tizimning nazorat summasi: yangi tizim raqami bilan solishtiriladi (`/migration/reconcile`)."""

    __tablename__ = "migration_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    metric: Mapped[str] = mapped_column(String(24))  # employees_total | employees_active | employees_dismissed | attendance_records | attendance_hours
    period: Mapped[str | None] = mapped_column(String(7))  # YYYY-MM (davomat uchun)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    expected: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tolerance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

