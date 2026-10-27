"""integrations: api_keys, branch_daily_metrics; complaints

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False, unique=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), _user()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", TS), sa.Column("revoked_at", TS),
    )
    op.create_table(
        "branch_daily_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("sales", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("plan", sa.Numeric(16, 2)), sa.Column("receipts", sa.Integer()),
        sa.Column("source", sa.String(40), nullable=False, server_default="api"),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("branch_id", "metric_date", name="uq_branch_metric_day"),
    )
    op.create_index("ix_branch_daily_metrics_branch_id", "branch_daily_metrics", ["branch_id"])
    op.create_index("ix_branch_daily_metrics_metric_date", "branch_daily_metrics", ["metric_date"])
    op.create_table(
        "complaints",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("author_user_id", sa.Integer(), _user()),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("category", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("assignee_id", sa.Integer(), _user()),
        sa.Column("response", sa.Text()), sa.Column("resolved_at", TS),
        sa.Column("history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_complaints_author_user_id", "complaints", ["author_user_id"])


def downgrade() -> None:
    for t in ("complaints", "branch_daily_metrics", "api_keys"):
        op.drop_table(t)
