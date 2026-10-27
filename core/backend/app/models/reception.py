from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Visit(Base):
    """Mehmon qaydi. Holat: expected | arrived | left | cancelled | no_show."""

    __tablename__ = "visits"
    __table_args__ = (Index("ix_visits_status", "status"), Index("ix_visits_expected", "expected_at"), Index("ix_visits_arrived", "arrived_at"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visitor_name: Mapped[str] = mapped_column(String(160))
    visitor_phone: Mapped[str | None] = mapped_column(String(32))
    company: Mapped[str | None] = mapped_column(String(120))
    purpose: Mapped[str] = mapped_column(String(12), default="meeting")  # meeting | interview | delivery | service | other
    host_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="expected")
    badge_no: Mapped[str | None] = mapped_column(String(20))
    doc_info: Mapped[str | None] = mapped_column(String(60))
    vehicle_plate: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    registered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    checked_in_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    checked_out_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
