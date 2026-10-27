"""payroll: pay_schemes, pay_items, payroll_runs, payroll_lines

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
MONEY = sa.Numeric(14, 2)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def _m(name):
    return sa.Column(name, MONEY, nullable=False, server_default="0")


def upgrade() -> None:
    op.create_table(
        "pay_schemes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        _m("fixed_amount"),
        sa.Column("commission_percent", sa.Numeric(6, 3), nullable=False, server_default="0"),
        _m("plan_bonus"),
        _m("kpi_amount"),
        sa.Column("note", sa.String(300)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_ts(),
    )
    op.create_index("ix_pay_schemes_employee", "pay_schemes", ["employee_id", "effective_from"])
    op.create_table(
        "pay_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_ts(),
    )
    op.create_index("ix_pay_items_period", "pay_items", ["period", "kind"])
    op.create_index("ix_pay_items_employee", "pay_items", ["employee_id", "period"])
    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period", sa.String(7), nullable=False, unique=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("calculated_at", TS),
        sa.Column("approved_at", TS),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("paid_at", TS),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_ts(),
    )
    op.create_table(
        "payroll_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_name", sa.String(250), nullable=False),
        sa.Column("employee_no", sa.Integer()),
        sa.Column("branch_name", sa.String(200)),
        sa.Column("department_name", sa.String(200)),
        sa.Column("plan_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paid_days", sa.Integer(), nullable=False, server_default="0"),
        *[_m(c) for c in ("fixed", "commission", "plan_bonus", "kpi_bonus", "bonus", "gross", "penalties", "deductions", "taxable", "tax", "inps", "net", "advance", "to_pay")],
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_payroll_line"),
    )
    op.create_index("ix_payroll_lines_run_id", "payroll_lines", ["run_id"])
    op.create_index("ix_payroll_lines_employee_id", "payroll_lines", ["employee_id"])


def downgrade() -> None:
    for t in ("payroll_lines", "payroll_runs", "pay_items", "pay_schemes"):
        op.drop_table(t)
