"""calls: calls, call_participants

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("media", sa.String(5), nullable=False, server_default="video"),
        sa.Column("title", sa.String(200)),
        sa.Column("room_name", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("scheduled_at", TS),
        sa.Column("ring_until", TS),
        sa.Column("started_at", TS),
        sa.Column("ended_at", TS),
        sa.Column("ended_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("end_reason", sa.String(12)),
        sa.Column("empty_since", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calls_status", "calls", ["status"])
    op.create_index("ix_calls_host", "calls", ["host_id"])
    op.create_table(
        "call_participants",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(8), nullable=False, server_default="invitee"),
        sa.Column("status", sa.String(8), nullable=False, server_default="invited"),
        sa.Column("invited_at", TS, nullable=False),
        sa.Column("first_joined_at", TS),
        sa.Column("last_joined_at", TS),
        sa.Column("left_at", TS),
        sa.Column("total_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("call_id", "user_id", name="uq_call_participant"),
    )
    op.create_index("ix_call_participants_call_id", "call_participants", ["call_id"])
    op.create_index("ix_call_participants_user", "call_participants", ["user_id"])


def downgrade() -> None:
    op.drop_table("call_participants")
    op.drop_table("calls")
