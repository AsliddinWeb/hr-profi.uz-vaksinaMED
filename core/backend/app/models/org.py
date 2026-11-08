from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Department(Base, TimestampMixin):
    """Bo'lim. `parent_id` orqali daraxt (org-chart)."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    head_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20), default="office")  # office|pharmacy|warehouse|other
    color: Mapped[str | None] = mapped_column(String(7))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    yqm: Mapped[str | None] = mapped_column(Text)  # yakuniy qimmatli mahsulot (bo'lim natijasi)
    # shajarada bo'lim qaysi lavozim ostida chiziladi (masalan Moliya -> Ta'sischi, boshqalar -> Direktor)
    reports_to_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL", use_alter=True, name="fk_departments_reports_to_position"))


class Position(Base, TimestampMixin):
    """Lavozim. `department_id` bo'sh bo'lsa umumiy lavozim."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    yqm: Mapped[str | None] = mapped_column(Text)  # lavozimning yakuniy qimmatli mahsuloti
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))  # kimga bo'ysunadi
    slots: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # shtat birligi (o'rinlar soni)
    is_head: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # bo'lim boshlig'i lavozimi


class Branch(Base, TimestampMixin):
    """Filial (dorixona). Joylashuv va geofence davomat uchun (F6)."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(300))
    district: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    coordinator_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    geofence_radius_m: Mapped[int] = mapped_column(Integer, default=100)
    # Apteka profili (F14): lavozim bo'yicha xodim me'yori, ish vaqti
    staff_norm: Mapped[dict] = mapped_column(JSONB, default=lambda: {"manager": 1, "pharmacist": 2, "intern": 0})
    open_time: Mapped[time | None] = mapped_column(Time)
    close_time: Mapped[time | None] = mapped_column(Time)
    is_24h: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    pharmacy_note: Mapped[str | None] = mapped_column(Text)
    # Davomat QR kodini bekor qilish uchun (oshirilsa eski QR lar ishlamaydi)
    qr_epoch: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
