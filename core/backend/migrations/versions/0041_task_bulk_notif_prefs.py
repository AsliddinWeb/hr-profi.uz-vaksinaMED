"""tasks: accepted_at, batch_id; notification_prefs

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column("tasks", sa.Column("batch_id", sa.String(16)))
    op.create_index("ix_tasks_batch_id", "tasks", ["batch_id"])
    op.create_table(
        "notification_prefs",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("muted", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_prefs")
    op.drop_index("ix_tasks_batch_id", table_name="tasks")
    op.drop_column("tasks", "batch_id")
    op.drop_column("tasks", "accepted_at")
