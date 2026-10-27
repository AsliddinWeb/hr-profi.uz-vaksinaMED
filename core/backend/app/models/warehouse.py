from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Warehouse(Base, TimestampMixin):
    """Ombor: xodimlari = `work_group_id` guruhidagi faol xodimlar (erkin grafikli smena guruhi).

    `min_on_duty` — smena oynasi davomida bir vaqtda kamida nechta xodim ishda bo'lishi kerak.
    """

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    work_group_id: Mapped[int] = mapped_column(ForeignKey("work_groups.id", ondelete="RESTRICT"))
    min_on_duty: Mapped[int] = mapped_column(Integer, default=1)
    max_shift_hours: Mapped[int] = mapped_column(Integer, default=16)  # shundan uzoq ochiq smena: ogohlantirish
    alert_grace_min: Mapped[int] = mapped_column(Integer, default=20)  # yetishmovchilik shuncha davom etsa xabar
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ogohlantirish holati (takror xabar bermaslik uchun)
    gap_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gap_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    alerted_records: Mapped[list] = mapped_column(JSONB, default=list)
