"""Lavozim hujjatlari: lavozimga biriktirilgan HR hujjatlar (yo'riqnoma, qoidalar), onlayn imzo va xodimdan so'raladigan shaxsiy hujjatlar."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PositionDocLink(Base):
    """Lavozimdagi xodim tanishib imzolashi kerak bo'lgan hujjat (HR hujjatlar kutubxonasidan)."""

    __tablename__ = "position_doc_links"
    __table_args__ = (UniqueConstraint("position_id", "document_id", name="uq_position_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("hr_documents.id", ondelete="CASCADE"), index=True)


class PositionRequiredDoc(Base):
    """Lavozim uchun xodimdan so'raladigan shaxsiy hujjat (rasm, pasport, diplom, tibbiy daftarcha...)."""

    __tablename__ = "position_required_docs"
    __table_args__ = (UniqueConstraint("position_id", "kind", "title", name="uq_position_required_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))


class DocumentSignature(Base):
    """Xodimning hujjat versiyasiga qo'ygan onlayn imzosi (chizilgan imzo rasmi, vaqt, qurilma)."""

    __tablename__ = "document_signatures"
    __table_args__ = (UniqueConstraint("document_id", "version", "user_id", name="uq_document_signature"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("hr_documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    signature: Mapped[str] = mapped_column(Text)  # data:image/png;base64,...
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
