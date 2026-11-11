"""Qurilma xavfsizligi: foydalanuvchi qurilmalari va majburiy nazorat sozlamalari

Revision ID: 0054
Revises: 0053
"""
import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("first_ip", sa.String(64)),
        sa.Column("last_ip", sa.String(64)),
        sa.Column("status", sa.String(10), nullable=False, server_default="approved"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", TS),
        sa.UniqueConstraint("user_id", "device_key", name="uq_user_device"),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.create_index("ix_user_devices_status", "user_devices", ["status"])
    op.create_table(
        "device_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enforce_roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enforce_user_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("auto_approve_first", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("device_settings")
    op.drop_table("user_devices")
