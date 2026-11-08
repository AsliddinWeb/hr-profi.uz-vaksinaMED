"""tashkiliy tuzilma: bo'lim va lavozimning YaQM (yakuniy qimmatli mahsuloti)

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("yqm", sa.Text(), nullable=True))
    op.add_column("positions", sa.Column("yqm", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("positions", "yqm")
    op.drop_column("departments", "yqm")
