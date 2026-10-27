"""reports: report_schedules, report_runs

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("report_type", sa.String(24), nullable=False),
        sa.Column("period", sa.String(12), nullable=False, server_default="last_week"),
        sa.Column("format", sa.String(4), nullable=False, server_default="xlsx"),
        sa.Column("lang", sa.String(2), nullable=False, server_default="uz"),
        sa.Column("frequency", sa.String(8), nullable=False, server_default="weekly"),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weekday", sa.Integer()),
        sa.Column("month_day", sa.Integer()),
        sa.Column("recipient_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("channels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", TS),
        sa.Column("next_run_at", TS),
        sa.Column("last_status", sa.String(8)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_schedules_due", "report_schedules", ["is_active", "next_run_at"])
    op.create_table(
        "report_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("report_schedules.id", ondelete="SET NULL")),
        sa.Column("report_type", sa.String(24), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("format", sa.String(4), nullable=False),
        sa.Column("lang", sa.String(2), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("file_key", sa.String(300)),
        sa.Column("filename", sa.String(200)),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recipient_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_runs_user", "report_runs", ["created_by", "created_at"])


def downgrade() -> None:
    op.drop_table("report_runs")
    op.drop_table("report_schedules")
