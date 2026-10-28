"""leave_requests: elektron bildirgi (raqam, tekshiruv kodi, xesh)

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leave_requests", sa.Column("statement_no", sa.String(20)))
    op.add_column("leave_requests", sa.Column("statement_code", sa.String(32)))
    op.add_column("leave_requests", sa.Column("statement_hash", sa.String(64)))
    op.add_column("leave_requests", sa.Column("statement_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_leave_requests_statement_no", "leave_requests", ["statement_no"])
    op.create_unique_constraint("uq_leave_requests_statement_code", "leave_requests", ["statement_code"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS leave_no_seq")


def downgrade() -> None:
    op.drop_constraint("uq_leave_requests_statement_code", "leave_requests")
    op.drop_constraint("uq_leave_requests_statement_no", "leave_requests")
    for c in ("statement_at", "statement_hash", "statement_code", "statement_no"):
        op.drop_column("leave_requests", c)
    op.execute("DROP SEQUENCE IF EXISTS leave_no_seq")
