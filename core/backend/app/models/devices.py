"""Qurilma xavfsizligi: xodim qaysi qurilmadan kirgani, asosiy qurilma, begona qurilmadan kirishga ruxsat so'rovi va bloklash."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserDevice(Base):
    """Brauzer/ilova qurilmasi (`device_key` — brauzerda saqlanadigan tasodifiy ID). status: approved | pending | blocked."""

    __tablename__ = "user_devices"
    __table_args__ = (UniqueConstraint("user_id", "device_key", name="uq_user_device"), Index("ix_user_devices_status", "status"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(120))  # "Chrome · Windows"
    user_agent: Mapped[str | None] = mapped_column(String(300))
    first_ip: Mapped[str | None] = mapped_column(String(64))
    last_ip: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10), default="approved")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceSettings(Base):
    """Yagona qator (id=1). `enforce_roles` / `enforce_user_ids` — qurilma nazorati majburiy bo'lganlar:
    ular faqat tasdiqlangan qurilmadan kira oladi, yangi qurilma uchun ruxsat so'rovi yaratiladi."""

    __tablename__ = "device_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enforce_roles: Mapped[list] = mapped_column(JSON, default=list)
    enforce_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    auto_approve_first: Mapped[bool] = mapped_column(Boolean, default=True)  # birinchi qurilma avtomatik asosiy bo'ladi
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
