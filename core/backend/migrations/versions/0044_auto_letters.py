"""avtomatik tushuntirish xati: qoidabuzarlik faktlari, jarima bog'lanishi, tasdiqlash va chizilgan imzo

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("explanation_letters", sa.Column("auto", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("explanation_letters", sa.Column("penalty_id", sa.BigInteger(), sa.ForeignKey("penalties.id", ondelete="SET NULL"), nullable=True))
    op.add_column("explanation_letters", sa.Column("facts", postgresql.JSONB(), nullable=True))
    op.add_column("explanation_letters", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("explanation_letters", sa.Column("signature_image", sa.Text(), nullable=True))
    op.create_index(
        "ix_letters_auto_open", "explanation_letters", ["employee_id"],
        postgresql_where=sa.text("auto AND status IN ('requested', 'returned')"),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_index("ix_letters_auto_open", table_name="explanation_letters")
    for col in ("signature_image", "confirmed_at", "facts", "penalty_id", "auto"):
        op.drop_column("explanation_letters", col)
