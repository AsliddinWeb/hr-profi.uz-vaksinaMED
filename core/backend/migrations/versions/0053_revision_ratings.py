"""Reviziya (filial ichki auditi) va mijozlar baholashi (filial QR)

Revision ID: 0053
Revises: 0052
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "revision_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revizor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(12), nullable=False, server_default="cycle"),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="assigned"),
        sa.Column("note", sa.Text()),
        sa.Column("result_note", sa.Text()),
        sa.Column("shortage_amount", sa.Numeric(14, 2)),
        sa.Column("score", sa.SmallInteger()),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("accepted_at", TS),
        sa.Column("started_at", TS),
        sa.Column("submitted_at", TS),
        sa.Column("decided_at", TS),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_revision_tasks_branch", "revision_tasks", ["branch_id", "status"])
    op.create_index("ix_revision_tasks_date", "revision_tasks", ["planned_date"])
    op.create_index("ix_revision_tasks_revizor_user_id", "revision_tasks", ["revizor_user_id"])
    op.create_table(
        "branch_rating_qr",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("token", sa.String(40), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(8), nullable=False, server_default="active"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "customer_ratings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(10), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("stars", sa.SmallInteger(), nullable=False),
        sa.Column("cleanliness", sa.SmallInteger()),
        sa.Column("assortment", sa.SmallInteger()),
        sa.Column("comment", sa.Text()),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("qr_version", sa.Integer()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_ratings_branch", "customer_ratings", ["branch_id", "created_at"])
    op.create_index("ix_customer_ratings_employee_id", "customer_ratings", ["employee_id"])


def downgrade() -> None:
    op.drop_table("customer_ratings")
    op.drop_table("branch_rating_qr")
    op.drop_table("revision_tasks")
