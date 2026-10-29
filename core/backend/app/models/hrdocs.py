from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class HrDocument(Base, TimestampMixin):
    """HR hujjatlar kutubxonasi: kompaniya missiyasi, nizom, jarayonlar... Matn va/yoki fayl; versiyalar; «tanishdim» tasdig'i."""

    __tablename__ = "hr_documents"
    __table_args__ = (Index("ix_hr_documents_category", "category", "sort_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(40), unique=True)  # tayyor kartochkalar uchun (mission, charter, ...)
    category: Mapped[str] = mapped_column(String(20))  # strategy | policy | process | system | culture
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(300))
    file_name: Mapped[str | None] = mapped_column(String(160))
    file_mime: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=0)  # oxirgi e'lon qilingan versiya (0 = hali e'lon qilinmagan)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | published
    requires_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    roles: Mapped[list] = mapped_column(JSONB, default=list)  # bo'sh = hamma; aks holda faqat shu rol kalitlari
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class HrDocumentVersion(Base):
    __tablename__ = "hr_document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_hr_document_versions"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("hr_documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(300))
    file_name: Mapped[str | None] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(String(300))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HrDocumentAck(Base):
    """Foydalanuvchi hujjatning qaysi versiyasi bilan tanishganini tasdiqlagan."""

    __tablename__ = "hr_document_acks"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_hr_document_acks"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("hr_documents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StaffDocument(Base, TimestampMixin):
    """Xodim elektron hujjati: ariza (xodim yozadi, HR ko'rib chiqadi) yoki buyruq (HR tayyorlaydi, imzolaydi, xodim tanishadi)."""

    __tablename__ = "staff_documents"
    __table_args__ = (Index("ix_staff_documents_employee", "employee_id", "kind"), Index("ix_staff_documents_status", "kind", "status"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))  # application | order
    subtype: Mapped[str] = mapped_column(String(12))  # ariza: vacation|unpaid|resign|transfer|other; buyruq: hire|transfer|vacation|dismiss|other
    number: Mapped[str | None] = mapped_column(String(20), unique=True)  # AR-2026-0001 / BY-2026-0001
    code: Mapped[str | None] = mapped_column(String(32), unique=True)  # ochiq tekshiruv kodi (QR)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # ariza: submitted | approved | rejected | cancelled; buyruq: draft | issued | cancelled
    status: Mapped[str] = mapped_column(String(12))
    related_id: Mapped[int | None] = mapped_column(ForeignKey("staff_documents.id", ondelete="SET NULL"))  # buyruq qaysi arizaga asoslangan
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    signed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
