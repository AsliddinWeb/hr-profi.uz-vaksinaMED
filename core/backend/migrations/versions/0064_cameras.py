"""Kameralar nazorati: IP kameralar, kompyuter/telefon kamera stansiyalari va holat jurnali

Revision ID: 0064
Revises: 0063
"""
import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False, server_default="ip"),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("brand", sa.String(40), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("host", sa.String(200), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("station_token", sa.String(32), nullable=True, unique=True),
        sa.Column("device_info", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_online_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cameras_branch_id", "cameras", ["branch_id"])
    op.create_index("ix_cameras_status", "cameras", ["status"])
    op.create_table(
        "camera_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("message", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_camera_events_camera_id", "camera_events", ["camera_id"])
    op.create_index("ix_camera_events_created_at", "camera_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("camera_events")
    op.drop_table("cameras")
