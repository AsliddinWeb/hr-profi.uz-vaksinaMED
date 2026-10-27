"""zayafka tasdig'i (staff_needs), lavozim talablari, vakansiya kanallari, manba linklari

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("staff_needs", sa.Column("approval", sa.String(12), nullable=False, server_default="approved"))
    op.add_column("staff_needs", sa.Column("reason_type", sa.String(12)))
    op.add_column("staff_needs", sa.Column("shift_note", sa.String(120)))
    op.add_column("staff_needs", sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")))
    op.add_column("staff_needs", sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="SET NULL")))
    op.add_column("staff_needs", sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("staff_needs", sa.Column("reviewed_at", TS))
    op.add_column("staff_needs", sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("staff_needs", sa.Column("approved_at", TS))
    op.add_column("staff_needs", sa.Column("decision_note", sa.Text()))

    op.create_table(
        "position_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("requirements", sa.Text()),
        sa.Column("competencies", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ad_template", sa.Text()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "vacancy_channels",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("url", sa.String(300)),
        sa.Column("note", sa.String(300)),
        sa.Column("posted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("posted_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vacancy_channels_vacancy_id", "vacancy_channels", ["vacancy_id"])
    op.create_table(
        "source_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("label", sa.String(120)),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_links_vacancy_id", "source_links", ["vacancy_id"])
    op.add_column("applications", sa.Column("source_link_id", sa.Integer(), sa.ForeignKey("source_links.id", ondelete="SET NULL")))
    op.create_index("ix_applications_source_link_id", "applications", ["source_link_id"])


def downgrade() -> None:
    op.drop_column("applications", "source_link_id")
    op.drop_table("source_links")
    op.drop_table("vacancy_channels")
    op.drop_table("position_requirements")
    for c in ("decision_note", "approved_at", "approved_by", "reviewed_at", "reviewed_by", "vacancy_id", "position_id", "shift_note", "reason_type", "approval"):
        op.drop_column("staff_needs", c)
