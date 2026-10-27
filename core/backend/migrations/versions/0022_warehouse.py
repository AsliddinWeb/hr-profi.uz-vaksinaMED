"""warehouse: warehouses

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("work_group_id", sa.Integer(), sa.ForeignKey("work_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("min_on_duty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_shift_hours", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("alert_grace_min", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("gap_since", TS),
        sa.Column("gap_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("alerted_records", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.execute("CREATE UNIQUE INDEX uq_warehouses_name ON warehouses (lower(name))")


def downgrade() -> None:
    op.drop_table("warehouses")
