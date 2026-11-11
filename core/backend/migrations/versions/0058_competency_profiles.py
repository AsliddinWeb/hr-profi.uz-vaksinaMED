"""Kompetensiyalar bazasi, lavozim profillari va zayafkaning profilga bog'lanishi

Revision ID: 0058
Revises: 0057
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "competencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(12), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_competencies_category", "competencies", ["category"])
    op.create_table(
        "position_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("filled_pct", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text()),
        *_ts(),
    )
    op.create_index("ix_position_profiles_position", "position_profiles", ["position_id", "status"])
    op.create_table(
        "profile_competencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("position_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("required_level", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("ideal_level", sa.SmallInteger(), nullable=False, server_default="4"),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("method", sa.String(12), nullable=False, server_default="interview"),
    )
    op.add_column("hire_requests", sa.Column("profile_id", sa.Integer(), sa.ForeignKey("position_profiles.id", ondelete="SET NULL")))


def downgrade() -> None:
    op.drop_column("hire_requests", "profile_id")
    op.drop_table("profile_competencies")
    op.drop_table("position_profiles")
    op.drop_table("competencies")
