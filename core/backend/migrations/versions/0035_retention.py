"""retention: retention_cases, retention_meetings, offboardings

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "retention_cases",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("risk_level", sa.String(6), nullable=False, server_default="medium"),
        sa.Column("source", sa.String(8), nullable=False, server_default="manual"),
        sa.Column("reported_by", sa.Integer(), _user()), sa.Column("note", sa.Text()),
        sa.Column("notice_date", sa.Date()), sa.Column("planned_leave_date", sa.Date()),
        sa.Column("hr_note", sa.Text()), sa.Column("hr_by", sa.Integer(), _user()), sa.Column("hr_at", TS),
        sa.Column("trainer_note", sa.Text()), sa.Column("trainer_by", sa.Integer(), _user()), sa.Column("trainer_at", TS),
        sa.Column("auditor_note", sa.Text()), sa.Column("auditor_by", sa.Integer(), _user()), sa.Column("auditor_at", TS),
        sa.Column("decision", sa.String(6)), sa.Column("decision_note", sa.Text()), sa.Column("decision_by", sa.Integer(), _user()), sa.Column("decision_at", TS),
        sa.Column("last_discussed_on", sa.Date()),
        sa.Column("events", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_retention_cases_employee_id", "retention_cases", ["employee_id"])
    op.create_index("ix_retention_cases_status", "retention_cases", ["status"])
    op.create_table(
        "retention_meetings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("case_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Integer(), _user()),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_retention_meetings_held_on", "retention_meetings", ["held_on"])
    op.create_table(
        "offboardings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("retention_cases.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("leave_date", sa.Date()), sa.Column("reason_type", sa.String(10)), sa.Column("reason_text", sa.Text()), sa.Column("prevent_text", sa.Text()),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("exit_by", sa.Integer(), _user()), sa.Column("exit_at", TS),
        sa.Column("measures", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("approved_by", sa.Integer(), _user()), sa.Column("approved_at", TS),
        sa.Column("completed_by", sa.Integer(), _user()), sa.Column("completed_at", TS),
        sa.Column("access_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), _user()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_offboardings_employee_id", "offboardings", ["employee_id"])
    op.create_index("ix_offboardings_status", "offboardings", ["status"])


def downgrade() -> None:
    for t in ("offboardings", "retention_meetings", "retention_cases"):
        op.drop_table(t)
