from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class FaceConsent(Base, TimestampMixin):
    """Biometrik ma'lumotga xodimning O'ZI bergan rozilik (versiyalangan). Qaytarib olinsa shablonlar o'chadi."""

    __tablename__ = "face_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    version: Mapped[str] = mapped_column(String(30))
    given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FaceTemplate(Base):
    """Yuz shabloni (embedding), AES-GCM bilan shifrlangan. Rasm hech qachon saqlanmaydi."""

    __tablename__ = "face_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    pose: Mapped[str] = mapped_column(String(10))  # center | left | right
    vector_enc: Mapped[bytes] = mapped_column(LargeBinary)
    model: Mapped[str] = mapped_column(String(60))
    quality: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FaceAttempt(Base):
    """Tekshiruv urinishlari (rasmsiz): FAR/FRR o'lchovi va xavfsizlik nazorati uchun."""

    __tablename__ = "face_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    purpose: Mapped[str] = mapped_column(String(10))  # enroll | verify
    success: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    liveness_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(40))
    frames: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
