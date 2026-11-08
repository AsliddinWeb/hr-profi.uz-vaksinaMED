"""tashkiliy tuzilma shajarasi: lavozim kimga bo'ysunadi, shtat soni, boshliq lavozimi; bo'lim qaysi lavozimga bo'ysunadi

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("parent_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL"), nullable=True))
    op.add_column("positions", sa.Column("slots", sa.Integer(), server_default="1", nullable=False))
    op.add_column("positions", sa.Column("is_head", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("departments", sa.Column("reports_to_position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL"), nullable=True))
    # mavjud "... boshlig'i" lavozimlarini boshliq deb belgilash
    op.execute("UPDATE positions SET is_head = true WHERE lower(name) LIKE '%boshlig%' OR lower(name) LIKE '%начальник%'")


def downgrade() -> None:
    op.drop_column("departments", "reports_to_position_id")
    op.drop_column("positions", "is_head")
    op.drop_column("positions", "slots")
    op.drop_column("positions", "parent_id")
