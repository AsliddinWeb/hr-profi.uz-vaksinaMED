"""duty_checklists, duty_runs: bo'lim/lavozim ish chek-listlari

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "duty_checklists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE")),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE")),
        sa.Column("frequency", sa.String(8), nullable=False, server_default="daily"),
        sa.Column("deadline_time", sa.Time(), nullable=False, server_default="20:00"),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_duty_checklists_dept", "duty_checklists", ["department_id"])
    op.create_index("ix_duty_checklists_pos", "duty_checklists", ["position_id"])
    op.create_table(
        "duty_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("duty_checklists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text()),
        sa.Column("score_pct", sa.Integer()),
        sa.Column("completed_at", TS),
        sa.Column("late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("late_notified_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("checklist_id", "employee_id", "period_date", name="uq_duty_runs_period"),
    )
    op.create_index("ix_duty_runs_employee_id", "duty_runs", ["employee_id"])
    op.create_index("ix_duty_runs_period", "duty_runs", ["period_date"])


def downgrade() -> None:
    op.drop_table("duty_runs")
    op.drop_table("duty_checklists")
