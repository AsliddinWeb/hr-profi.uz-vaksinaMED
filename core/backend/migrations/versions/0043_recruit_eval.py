"""recruit baholash: suhbat ballari, test banki va nomzod testlari, fon tekshiruvi, yakuniy xulosa, offer javobi

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "interview_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text()),
        *_ts(),
        sa.UniqueConstraint("application_id", "interviewer_id", name="uq_interview_score"),
    )
    op.create_index("ix_interview_scores_application_id", "interview_scores", ["application_id"])
    op.create_table(
        "test_banks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.Column("time_limit_min", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("questions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), _user()),
        *_ts(),
    )
    op.create_table(
        "candidate_tests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("test_banks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token", sa.String(24), nullable=False, unique=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="assigned"),
        sa.Column("started_at", TS),
        sa.Column("deadline_at", TS),
        sa.Column("submitted_at", TS),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score_pct", sa.Integer()),
        sa.Column("passed", sa.Boolean()),
        sa.Column("created_by", sa.Integer(), _user()),
        *_ts(),
    )
    op.create_index("ix_candidate_tests_app", "candidate_tests", ["application_id"])
    op.create_table(
        "background_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("consent_token", sa.String(24), nullable=False, unique=True),
        sa.Column("consent_at", TS),
        sa.Column("consent_ip", sa.String(64)),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False, server_default="consent_pending"),
        sa.Column("decision", sa.String(8)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("checked_by", sa.Integer(), _user()),
        sa.Column("finished_at", TS),
        sa.Column("created_by", sa.Integer(), _user()),
        *_ts(),
    )
    op.add_column("applications", sa.Column("offer_schedule", sa.String(200)))
    op.add_column("applications", sa.Column("offer_probation_days", sa.Integer()))
    op.add_column("applications", sa.Column("offer_token", sa.String(24)))
    op.add_column("applications", sa.Column("offer_response", sa.String(10)))
    op.add_column("applications", sa.Column("offer_response_at", TS))
    op.add_column("applications", sa.Column("offer_decline_reason", sa.String(300)))
    op.add_column("applications", sa.Column("conclusion", postgresql.JSONB()))
    op.create_unique_constraint("uq_applications_offer_token", "applications", ["offer_token"])


def downgrade() -> None:
    op.drop_constraint("uq_applications_offer_token", "applications")
    for c in ("conclusion", "offer_decline_reason", "offer_response_at", "offer_response", "offer_token", "offer_probation_days", "offer_schedule"):
        op.drop_column("applications", c)
    for t in ("background_checks", "candidate_tests", "test_banks", "interview_scores"):
        op.drop_table(t)
