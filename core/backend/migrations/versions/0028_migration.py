"""migration: migration_batches, migration_mappings, migration_legacy_ids, migration_checks + import_batch_id

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "migration_batches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("dataset", sa.String(12), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("file_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("headers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mapping", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("issues", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("applied_at", TS),
        sa.Column("rolled_back_at", TS),
    )
    op.create_table(
        "migration_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("dataset", sa.String(12), nullable=False),
        sa.Column("mapping", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "migration_legacy_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("entity", sa.String(12), nullable=False),
        sa.Column("legacy_id", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("migration_batches.id", ondelete="CASCADE")),
        sa.UniqueConstraint("entity", "legacy_id", name="uq_legacy_entity_id"),
    )
    op.create_index("ix_legacy_entity", "migration_legacy_ids", ["entity", "entity_id"])
    op.create_table(
        "migration_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("metric", sa.String(24), nullable=False),
        sa.Column("period", sa.String(7)),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("expected", sa.Numeric(14, 2), nullable=False),
        sa.Column("tolerance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    for table in ("employees", "attendance_records"):
        op.add_column(table, sa.Column("import_batch_id", sa.BigInteger(), sa.ForeignKey("migration_batches.id", ondelete="SET NULL")))
        op.create_index(f"ix_{table}_import_batch", table, ["import_batch_id"])


def downgrade() -> None:
    for table in ("attendance_records", "employees"):
        op.drop_index(f"ix_{table}_import_batch", table_name=table)
        op.drop_column(table, "import_batch_id")
    op.drop_table("migration_checks")
    op.drop_table("migration_legacy_ids")
    op.drop_table("migration_mappings")
    op.drop_table("migration_batches")
