"""Integratsiyalar jurnali (Telegram yuborishlari natijasi)

Revision ID: 0063
Revises: 0062
"""
import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ref", sa.String(64), nullable=True),
        sa.Column("message", sa.String(300), nullable=True),
    )
    op.create_index("ix_integration_logs_created_at", "integration_logs", ["created_at"])
    op.create_index("ix_integration_logs_provider", "integration_logs", ["provider"])


def downgrade() -> None:
    op.drop_table("integration_logs")
