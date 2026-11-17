"""Kameralar nazorati: filiallardagi IP kameralar, kompyuter va telefon kameralari (kamera stansiyasi)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(8), default="ip")  # ip | webcam | phone
    location: Mapped[str | None] = mapped_column(String(120))  # kirish, kassa, ombor...
    brand: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    host: Mapped[str | None] = mapped_column(String(200))  # IP kamera: IP yoki domen
    port: Mapped[int | None] = mapped_column(Integer)  # odatda 554 (RTSP) yoki 80
    station_token: Mapped[str | None] = mapped_column(String(32), unique=True)  # kompyuter/telefon stansiyasi havolasi
    device_info: Mapped[str | None] = mapped_column(String(200))  # stansiya: brauzer/qurilma
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(8), default="unknown")  # unknown | online | offline
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CameraEvent(Base):
    """Holat o'zgarishlari jurnali (onlayn <-> oflayn): ishlash foizi va tarix uchun."""

    __tablename__ = "camera_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(8))
    message: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
