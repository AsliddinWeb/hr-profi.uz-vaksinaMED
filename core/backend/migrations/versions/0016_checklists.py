"""checklists: checklist_templates, checklist_visits, checklist_files

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_checklist_templates_name ON checklist_templates (lower(name))")
    op.create_table(
        "checklist_visits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("checklist_templates.id", ondelete="SET NULL")),
        sa.Column("template_name", sa.String(160), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("coordinator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("submitted_at", TS),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("distance_m", sa.Integer()),
        sa.Column("geo_ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("geo_reason", sa.String(300)),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("note", sa.Text()),
        sa.Column("score", sa.Float()),
        sa.Column("critical_fails", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_checklist_visits_branch", "checklist_visits", ["branch_id", "submitted_at"])
    op.create_index("ix_checklist_visits_coord", "checklist_visits", ["coordinator_id", "status"])
    op.create_table(
        "checklist_files",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("visit_id", sa.BigInteger(), sa.ForeignKey("checklist_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(16)),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("mime", sa.String(80), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checklist_files_visit_id", "checklist_files", ["visit_id"])


def downgrade() -> None:
    for t in ("checklist_files", "checklist_visits", "checklist_templates"):
        op.drop_table(t)
