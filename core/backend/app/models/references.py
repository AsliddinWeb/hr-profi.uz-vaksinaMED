from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class EmploymentReference(Base, TimestampMixin):
    """Berilgan ish joyi ma'lumotnomasi; QR tekshiruv uchun o'zgarmas nusxa saqlanadi."""

    __tablename__ = "employment_references"
    __table_args__ = (Index("ix_employment_references_employee", "employee_id", "issued_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="issued")  # issued | cancelled
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
