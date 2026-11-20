from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class GoalPlan(Base, TimestampMixin):

    __tablename__ = "goal_plans"
    __table_args__ = (UniqueConstraint("department_id", "year", name="uq_goal_plan_dept_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    note: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Goal(Base, TimestampMixin):

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("goal_plans.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    specific: Mapped[str | None] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(20))
    baseline: Mapped[float | None] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)
    current: Mapped[float | None] = mapped_column(Float)
    achievable: Mapped[str | None] = mapped_column(Text)
    relevant: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date] = mapped_column(Date)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoalChange(Base):

    __tablename__ = "goal_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("goal_plans.id", ondelete="CASCADE"), index=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(8))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoalTask(Base, TimestampMixin):
    """Maqsad bo'yicha haftalik vazifa: bo'lim maqsadni kichik qadamlarga bo'ladi va progressni har hafta yangilaydi."""

    __tablename__ = "goal_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    note: Mapped[str | None] = mapped_column(Text)  # to'siq / keyingi qadam
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CompanyStrategy(Base, TimestampMixin):
    """Yillik kompaniya strategiyasi: SWOT tahlil (kuchli/zaif tomonlar, imkoniyat/xavflar)."""

    __tablename__ = "company_strategy"
    __table_args__ = (UniqueConstraint("year", name="uq_company_strategy_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    swot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
