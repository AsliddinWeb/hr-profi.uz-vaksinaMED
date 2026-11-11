"""Kofe-ledi: choy/kofe buyurtmalari

Revision ID: 0057
Revises: 0056
"""
import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coffee_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place", sa.String(120), nullable=False),
        sa.Column("items", sa.String(300), nullable=False),
        sa.Column("guests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(300)),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("handled_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("done_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_coffee_orders_status", "coffee_orders", ["status"])
    op.create_index("ix_coffee_orders_requested_by", "coffee_orders", ["requested_by"])


def downgrade() -> None:
    op.drop_table("coffee_orders")
