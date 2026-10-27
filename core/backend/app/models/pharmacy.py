from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StaffNeed(Base):
    """«Xodim kerak»: filialga yetishmayotgan xodim so'rovi (keyinroq vakansiyaga aylanadi: F17)."""

    __tablename__ = "staff_needs"
    __table_args__ = (Index("ix_staff_needs_branch_status", "branch_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(12))  # manager | pharmacist | intern | other
    count: Mapped[int] = mapped_column(Integer, default=1)
    urgency: Mapped[str] = mapped_column(String(8), default="normal")  # low | normal | urgent
    needed_from: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | filled | cancelled
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_note: Mapped[str | None] = mapped_column(Text)
    # Zayafka tasdig'i: pending_hr (HR menejer) -> pending_hrd (HRD) -> approved | rejected. Eski qatorlar tasdiqlangan hisoblanadi.
    approval: Mapped[str] = mapped_column(String(12), default="pending_hr", server_default="approved")
    reason_type: Mapped[str | None] = mapped_column(String(12))  # departure | new_branch | workload | other
    shift_note: Mapped[str | None] = mapped_column(String(120))
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
