"""attendance_issues: davomat muammosi so'rovlari

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "attendance_issues",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("method_tried", sa.String(8), nullable=False),
        sa.Column("claimed_in", TS),
        sa.Column("claimed_out", TS),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("coordinator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", TS),
        sa.Column("decision_note", sa.Text()),
        sa.Column("record_id", sa.BigInteger()),
        sa.Column("history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attendance_issues_employee_id", "attendance_issues", ["employee_id"])
    op.create_index("ix_attendance_issues_status", "attendance_issues", ["status"])


def downgrade() -> None:
    op.drop_table("attendance_issues")
