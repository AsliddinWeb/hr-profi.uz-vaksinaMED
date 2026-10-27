from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Employee(Base, TimestampMixin):
    """Xodim kartasi. Tizimga kirish hisobi (`user_id`) ixtiyoriy."""

    __tablename__ = "employees"
    __table_args__ = (Index("ix_employees_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_no: Mapped[int] = mapped_column(
        Integer, server_default=text("nextval('employee_no_seq')"), unique=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )

    last_name: Mapped[str] = mapped_column(String(80))
    first_name: Mapped[str] = mapped_column(String(80))
    middle_name: Mapped[str | None] = mapped_column(String(80))
    full_name: Mapped[str] = mapped_column(String(250), index=True)  # qidiruv/saralash uchun
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(1))  # m | f
    phone: Mapped[str | None] = mapped_column(String(13), index=True)  # +998XXXXXXXXX
    phone2: Mapped[str | None] = mapped_column(String(13))
    email: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(300))
    passport_no: Mapped[str | None] = mapped_column(String(12), unique=True)
    pinfl: Mapped[str | None] = mapped_column(String(14), unique=True)

    photo_key: Mapped[str | None] = mapped_column(String(300))
    photo_mime: Mapped[str | None] = mapped_column(String(60))

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"))
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )

    work_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_groups.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(String(12), default="active")  # active | dismissed
    hire_date: Mapped[date | None] = mapped_column(Date)
    dismissal_date: Mapped[date | None] = mapped_column(Date)
    dismissal_reason: Mapped[str | None] = mapped_column(String(20))
    dismissal_note: Mapped[str | None] = mapped_column(String(500))
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("migration_batches.id", ondelete="SET NULL"), index=True
    )  # eski tizimdan import qilingan bo'lsa: qaysi paket (F29)


class EmployeeEvent(Base):
    """Ish tarixi: ishga olish, o'tkazish, bo'shatish, tiklash, birlashtirish..."""

    __tablename__ = "employee_events"
    __table_args__ = (Index("ix_employee_events_employee", "employee_id", "effective_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[date] = mapped_column(Date)
    data: Mapped[dict | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmployeeDocument(Base, TimestampMixin):
    __tablename__ = "employee_documents"
    __table_args__ = (Index("ix_employee_documents_employee", "employee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # passport|contract|diploma|medical|certificate|other
    title: Mapped[str] = mapped_column(String(160))
    file_key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

