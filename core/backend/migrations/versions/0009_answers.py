"""answers: leave_requests, leave_events

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("reason_type", sa.String(12), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time()),
        sa.Column("end_time", sa.Time()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("coordinator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("submitted_at", TS, nullable=False),
        sa.Column("escalate_at", TS),
        sa.Column("escalated_at", TS),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", TS),
        sa.Column("decided_level", sa.String(12)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_requests_dates", "leave_requests", ["start_date", "end_date"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])
    op.create_table(
        "leave_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("request_id", sa.BigInteger(), sa.ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("level", sa.String(12)),
        sa.Column("note", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leave_events_request_id", "leave_events", ["request_id"])


def downgrade() -> None:
    op.drop_table("leave_events")
    op.drop_table("leave_requests")
