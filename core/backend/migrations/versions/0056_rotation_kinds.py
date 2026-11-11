"""Rotatsiya turlari (doimiy, muddatli, haftalik, kunlik), hafta kunlari va smena

Revision ID: 0056
Revises: 0055
"""
import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rotations", sa.Column("kind", sa.String(10), nullable=False, server_default="temporary"))
    op.add_column("rotations", sa.Column("weekdays", sa.String(20)))
    op.add_column("rotations", sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shift_templates.id", ondelete="SET NULL")))


def downgrade() -> None:
    op.drop_column("rotations", "shift_id")
    op.drop_column("rotations", "weekdays")
    op.drop_column("rotations", "kind")
