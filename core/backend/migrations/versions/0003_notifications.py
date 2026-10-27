"""notifications va users.telegram_*

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_chat_id", sa.BigInteger()))
    op.add_column("users", sa.Column("telegram_username", sa.String(64)))
    op.add_column(
        "users",
        sa.Column("telegram_notify", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("telegram_linked_at", TS))
    op.create_unique_constraint("uq_users_telegram_chat_id", "users", ["telegram_chat_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False, server_default="info"),
        sa.Column("title_uz", sa.String(200), nullable=False),
        sa.Column("title_ru", sa.String(200), nullable=False),
        sa.Column("body_uz", sa.Text()),
        sa.Column("body_ru", sa.Text()),
        sa.Column("link", sa.String(300)),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", TS),
    )
    op.create_index(
        "ix_notifications_user_read_created", "notifications", ["user_id", "read_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_constraint("uq_users_telegram_chat_id", "users", type_="unique")
    for col in ("telegram_linked_at", "telegram_notify", "telegram_username", "telegram_chat_id"):
        op.drop_column("users", col)
