"""Filial nazorati: reviziya (ichki audit) va mijozlar baholashi (filial QR orqali)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RevisionTask(Base):
    """Filial reviziyasi: bo'lim boshlig'i revizorga biriktiradi -> revizor qabul qiladi -> o'tkazadi -> natijani topshiradi -> boshliq tasdiqlaydi.
    status: assigned | accepted | in_progress | review | done | cancelled."""

    __tablename__ = "revision_tasks"
    __table_args__ = (Index("ix_revision_tasks_branch", "branch_id", "status"), Index("ix_revision_tasks_date", "planned_date"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    revizor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="cycle")  # cycle | shortage | inventory | check
    planned_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="assigned")
    note: Mapped[str | None] = mapped_column(Text)
    result_note: Mapped[str | None] = mapped_column(Text)
    shortage_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # kamomad (so'm)
    score: Mapped[int | None] = mapped_column(SmallInteger)  # 0..100
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BranchRatingQr(Base):
    """Filialning mijoz baholash QR kodi. `version` almashtirilganda oshadi (eski QR ishlamay qoladi). status: active | blocked."""

    __tablename__ = "branch_rating_qr"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), unique=True)
    token: Mapped[str] = mapped_column(String(40), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(8), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerRating(Base):
    """Mijoz bahosi. target: employee (smenadagi xodim) | pharmacy (filial: umumiy, tozalik, tanlov)."""

    __tablename__ = "customer_ratings"
    __table_args__ = (Index("ix_customer_ratings_branch", "branch_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    target: Mapped[str] = mapped_column(String(10))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    stars: Mapped[int] = mapped_column(SmallInteger)
    cleanliness: Mapped[int | None] = mapped_column(SmallInteger)  # 1..5 (5 = A'lo)
    assortment: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(20))
    qr_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
