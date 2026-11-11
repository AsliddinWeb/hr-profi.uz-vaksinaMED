"""Lavozim vazifalari va ish joyi ma'lumotnomalari

Revision ID: 0051
Revises: 0050
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("duties", postgresql.JSONB(), server_default="[]", nullable=False))
    op.create_table(
        "employment_references",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(12), server_default="issued", nullable=False),
        sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_employment_references_employee", "employment_references", ["employee_id", "issued_at"])


def downgrade() -> None:
    op.drop_index("ix_employment_references_employee", table_name="employment_references")
    op.drop_table("employment_references")
    op.drop_column("positions", "duties")
