"""E'lonlar: tasdiqlangan zayavkadan e'lon qoralamasi -> AI tekshiruv -> joylar -> tasdiq -> vakansiya; zayavkada kompetensiya kartochkasi

Revision ID: 0060
Revises: 0059
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hire_requests", sa.Column("card", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.BigInteger(), sa.ForeignKey("hire_requests.id", ondelete="SET NULL"), index=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("channels", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("ai_review", JSONB()),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="SET NULL")),
        sa.Column("recruiter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_announcements_status", "announcements", ["status"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_column("hire_requests", "card")
