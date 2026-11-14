"""E'lon kanali xarajati: manba bo'yicha cost per hire

Revision ID: 0061
Revises: 0060
"""
import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancy_channels", sa.Column("cost", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("vacancy_channels", "cost")
