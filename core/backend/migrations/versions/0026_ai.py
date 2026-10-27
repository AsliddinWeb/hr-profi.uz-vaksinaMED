"""ai: ai_settings, ai_requests, ai_summaries + qidiruv uchun trigram indekslar

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("model", sa.String(80), nullable=False, server_default="claude-haiku-5-5"),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("features", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.execute("INSERT INTO ai_settings (id, features) VALUES (1, '{\"summary\": true, \"resume\": true, \"ticket\": true}'::jsonb)")
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("feature", sa.String(12), nullable=False),
        sa.Column("entity", sa.String(16)),
        sa.Column("entity_id", sa.BigInteger()),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.String(120)),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_requests_user_day", "ai_requests", ["user_id", "created_at"])
    op.create_table(
        "ai_summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("entity", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("lang", sa.String(2), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entity", "entity_id", "lang", name="uq_ai_summary"),
    )
    # Global qidiruv (ILIKE '%q%') tez ishlashi uchun trigram indekslar
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, col in (
        ("employees_name", "employees", "full_name"), ("candidates_name", "candidates", "full_name"), ("tasks_title", "tasks", "title"),
        ("tickets_title", "tickets", "title"), ("needs_title", "need_requests", "title"), ("visits_name", "visits", "visitor_name"),
    ):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_trgm_{name} ON {table} USING gin ({col} gin_trgm_ops)")


def downgrade() -> None:
    for name in ("employees_name", "candidates_name", "tasks_title", "tickets_title", "needs_title", "visits_name"):
        op.execute(f"DROP INDEX IF EXISTS ix_trgm_{name}")
    op.drop_table("ai_summaries")
    op.drop_table("ai_requests")
    op.drop_table("ai_settings")
