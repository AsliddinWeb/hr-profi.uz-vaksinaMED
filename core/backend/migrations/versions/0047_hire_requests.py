"""rekruting: bo'lim zayafkalari (hire_requests), qo'ng'iroq yo'nalishi (kiruvchi/chiquvchi)

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("recruit_calls", sa.Column("direction", sa.String(3), server_default="out", nullable=False))  # in | out
    op.create_table(
        "hire_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("number", sa.String(20), unique=True, nullable=False),  # ZY-2026-0001
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL"), nullable=False),
        sa.Column("count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("urgency", sa.String(8), server_default="normal", nullable=False),  # low | normal | urgent
        sa.Column("needed_from", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),  # kompetensiya kartochkasidan avto-to'ldiriladi, tahrirlanadi
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(10), server_default="pending", nullable=False),  # pending | approved | rejected | cancelled
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", TS, nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_hire_requests_status", "hire_requests", ["status"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS hire_request_no_seq")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS hire_request_no_seq")
    op.drop_table("hire_requests")
    op.drop_column("recruit_calls", "direction")
