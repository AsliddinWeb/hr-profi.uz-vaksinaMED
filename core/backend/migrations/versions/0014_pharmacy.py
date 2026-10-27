"""pharmacy: branches profil ustunlari, staff_needs

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("branches", sa.Column("staff_norm", postgresql.JSONB(), nullable=False, server_default='{"manager": 1, "pharmacist": 2, "intern": 0}'))
    op.add_column("branches", sa.Column("open_time", sa.Time()))
    op.add_column("branches", sa.Column("close_time", sa.Time()))
    op.add_column("branches", sa.Column("is_24h", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("branches", sa.Column("pharmacy_note", sa.Text()))
    op.create_table(
        "staff_needs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("urgency", sa.String(8), nullable=False, server_default="normal"),
        sa.Column("needed_from", sa.Date()),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("closed_at", TS),
        sa.Column("close_note", sa.Text()),
    )
    op.create_index("ix_staff_needs_branch_status", "staff_needs", ["branch_id", "status"])


def downgrade() -> None:
    op.drop_table("staff_needs")
    for c in ("pharmacy_note", "is_24h", "close_time", "open_time", "staff_norm"):
        op.drop_column("branches", c)
