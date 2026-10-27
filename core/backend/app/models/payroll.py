from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class PayScheme(Base, TimestampMixin):
    """Xodimning ish haqi sxemasi (versiyalangan: `effective_from`). Oy uchun oy oxiridagi eng yangi sxema qo'llanadi."""

    __tablename__ = "pay_schemes"
    __table_args__ = (Index("ix_pay_schemes_employee", "employee_id", "effective_from"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    effective_from: Mapped[date] = mapped_column(Date)
    fixed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # oylik oklad
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)  # savdodan foiz
    plan_bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # reja bajarilsa qo'shimcha
    kpi_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # KPI bonusining maksimumi
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PayItem(Base, TimestampMixin):
    """Oylik kiritmalar: savdo (fakt), reja, KPI bali, bonus, avans, ushlanma. `period` = 'YYYY-MM'."""

    __tablename__ = "pay_items"
    __table_args__ = (Index("ix_pay_items_period", "period", "kind"), Index("ix_pay_items_employee", "employee_id", "period"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(7))
    kind: Mapped[str] = mapped_column(String(10))  # sales | plan | kpi | bonus | advance | deduction
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # kpi uchun 0..100 ball
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PayrollRun(Base, TimestampMixin):
    """Oylik hisob-kitob. Holat: draft | approved | paid. Tasdiqlangach satrlar o'zgarmaydi (muhrlangan)."""

    __tablename__ = "payroll_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    settings: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PayrollLine(Base):
    """Xodim bo'yicha hisob: barcha summalar hisoblangan paytda muhrlanadi, `details` da tafsilot."""

    __tablename__ = "payroll_lines"
    __table_args__ = (UniqueConstraint("run_id", "employee_id", name="uq_payroll_line"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    employee_name: Mapped[str] = mapped_column(String(250))
    employee_no: Mapped[int | None] = mapped_column(Integer)
    branch_name: Mapped[str | None] = mapped_column(String(200))
    department_name: Mapped[str | None] = mapped_column(String(200))
    plan_days: Mapped[int] = mapped_column(Integer, default=0)
    paid_days: Mapped[int] = mapped_column(Integer, default=0)
    fixed: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    commission: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    plan_bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    kpi_bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    penalties: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    taxable: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    inps: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    advance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    to_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
