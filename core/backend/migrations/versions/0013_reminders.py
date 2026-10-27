"""reminders: reminders, reminder_events

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("link", sa.String(300)),
        sa.Column("recipients", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("repeat", sa.String(8), nullable=False, server_default="once"),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("weekdays", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("first_at", TS, nullable=False),
        sa.Column("until", sa.Date()),
        sa.Column("telegram", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_at", TS),
        sa.Column("snooze_at", TS),
        sa.Column("last_fired_at", TS),
        sa.Column("last_ack_at", TS),
        sa.Column("fire_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reminders_due", "reminders", ["next_at"])
    op.create_index("ix_reminders_owner", "reminders", ["owner_id"])
    op.create_table(
        "reminder_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reminder_id", sa.BigInteger(), sa.ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reminder_events_reminder_id", "reminder_events", ["reminder_id"])


def downgrade() -> None:
    op.drop_table("reminder_events")
    op.drop_table("reminders")
