"""needs: need_categories, need_requests, need_events, need_comments, need_files, need_no_seq

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS need_no_seq")
    op.create_table(
        "need_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("default_assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("sla_days", sa.Integer()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_need_categories_name ON need_categories (lower(name))")
    op.create_table(
        "need_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("need_categories.id", ondelete="SET NULL")),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("priority", sa.String(8), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(12), nullable=False, server_default="requested"),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("due_at", TS),
        sa.Column("requested_at", TS, nullable=False),
        sa.Column("assigned_at", TS),
        sa.Column("completed_at", TS),
        sa.Column("confirmed_at", TS),
        sa.Column("report", sa.Text()),
        sa.Column("rating", sa.Integer()),
        sa.Column("confirm_note", sa.Text()),
        sa.Column("return_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notified_soon", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notified_overdue", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
    )
    op.create_index("ix_need_requests_status", "need_requests", ["status"])
    op.create_index("ix_need_requests_assignee", "need_requests", ["assignee_id", "status"])
    op.create_index("ix_need_requests_requester", "need_requests", ["requester_id"])
    for table, cols in (
        ("need_events", [sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("action", sa.String(12), nullable=False), sa.Column("note", sa.Text()), sa.Column("data", postgresql.JSONB())]),
        ("need_comments", [sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("body", sa.Text(), nullable=False)]),
        ("need_files", [sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("key", sa.String(300), nullable=False), sa.Column("filename", sa.String(200), nullable=False), sa.Column("mime", sa.String(80), nullable=False), sa.Column("size", sa.Integer(), nullable=False)]),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("need_id", sa.BigInteger(), sa.ForeignKey("need_requests.id", ondelete="CASCADE"), nullable=False),
            *cols,
            sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        )
        op.create_index(f"ix_{table}_need_id", table, ["need_id"])
    op.bulk_insert(
        sa.table("need_categories", sa.column("name", sa.String), sa.column("sla_days", sa.Integer), sa.column("sort_order", sa.Integer)),
        [{"name": "Ta'mirlash va xo'jalik", "sla_days": 3, "sort_order": 1}, {"name": "Kompyuter va IT", "sla_days": 2, "sort_order": 2}, {"name": "Kanselyariya va materiallar", "sla_days": 5, "sort_order": 3}, {"name": "Boshqa", "sla_days": 7, "sort_order": 9}],
    )


def downgrade() -> None:
    for t in ("need_files", "need_comments", "need_events", "need_requests", "need_categories"):
        op.drop_table(t)
    op.execute("DROP SEQUENCE IF EXISTS need_no_seq")
