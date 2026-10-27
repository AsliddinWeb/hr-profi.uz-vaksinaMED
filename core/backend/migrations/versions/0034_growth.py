"""growth: hr_settings, career_levels, attestations, promotions

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "hr_settings",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_by", sa.Integer(), _user()),
        sa.Column("updated_at", TS),
    )
    op.create_table(
        "career_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("salary_min", sa.Integer()), sa.Column("salary_max", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "attestations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey("career_levels.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(8), nullable=False, server_default="open"),
        sa.Column("test_score", sa.Float()), sa.Column("practical_score", sa.Float()), sa.Column("total", sa.Float()),
        sa.Column("feedbacks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("decision", sa.String(14)), sa.Column("decision_note", sa.Text()),
        sa.Column("decided_by", sa.Integer(), _user()), sa.Column("decided_at", TS), sa.Column("opened_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "month", name="uq_attestation_month"),
    )
    op.create_index("ix_attestations_employee_id", "attestations", ["employee_id"])
    op.create_index("ix_attestations_month", "attestations", ["month"])
    op.create_table(
        "promotions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_level_id", sa.Integer(), sa.ForeignKey("career_levels.id", ondelete="SET NULL")),
        sa.Column("to_level_id", sa.Integer(), sa.ForeignKey("career_levels.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="proposed"),
        sa.Column("source", sa.String(8), nullable=False, server_default="manual"),
        sa.Column("basis", sa.Text()),
        sa.Column("proposed_by", sa.Integer(), _user()), sa.Column("decided_by", sa.Integer(), _user()),
        sa.Column("decided_at", TS), sa.Column("decision_note", sa.Text()), sa.Column("effective_date", sa.Date()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_promotions_employee_id", "promotions", ["employee_id"])


def downgrade() -> None:
    for t in ("promotions", "attestations", "career_levels", "hr_settings"):
        op.drop_table(t)
