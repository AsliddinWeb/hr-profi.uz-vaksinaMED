"""recruit yadrosi: kompetensiya kartochkasi versiyalari, telefon egaligi tarixi, anketa, suhbat takliflari, SLA

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("position_requirements", sa.Column("profile", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("position_requirements", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "position_requirement_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("position_id", "version", name="uq_position_requirement_version"),
    )
    op.create_index("ix_position_requirement_versions_position_id", "position_requirement_versions", ["position_id"])
    op.add_column("vacancies", sa.Column("sla_warned_at", TS))
    op.add_column("vacancies", sa.Column("sla_overdue_at", TS))
    op.add_column("vacancy_channels", sa.Column("closed_at", TS))
    op.add_column("candidates", sa.Column("pinfl", sa.String(14)))
    op.add_column("candidates", sa.Column("profile", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("candidates", sa.Column("profile_token", sa.String(24)))
    op.add_column("candidates", sa.Column("profile_confirmed_at", TS))
    op.create_index("ix_candidates_pinfl", "candidates", ["pinfl"])
    op.create_unique_constraint("uq_candidates_profile_token", "candidates", ["profile_token"])
    op.add_column("applications", sa.Column("reject_code", sa.String(16)))
    op.add_column("applications", sa.Column("match_score", sa.Integer()))
    op.add_column("applications", sa.Column("match_detail", postgresql.JSONB()))
    op.add_column("recruit_calls", sa.Column("callback_date", sa.Date()))
    op.create_table(
        "candidate_phones",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(13), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("ended_at", TS),
    )
    op.create_index("ix_candidate_phones_candidate_id", "candidate_phones", ["candidate_id"])
    op.create_index("ix_candidate_phones_phone", "candidate_phones", ["phone"])
    # mavjud nomzodlarning joriy raqamini tarixga yozamiz
    op.execute("INSERT INTO candidate_phones (candidate_id, phone, started_at) SELECT id, phone, created_at FROM candidates WHERE phone IS NOT NULL")
    op.create_table(
        "interview_invites",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(24), nullable=False, unique=True),
        sa.Column("slots", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mode", sa.String(8), nullable=False, server_default="offline"),
        sa.Column("place", sa.String(200)),
        sa.Column("map_url", sa.String(300)),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("meeting_url", sa.String(300)),
        sa.Column("status", sa.String(10), nullable=False, server_default="sent"),
        sa.Column("chosen_at", TS),
        sa.Column("reply", sa.String(12)),
        sa.Column("replied_at", TS),
        sa.Column("reminded_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reminded_2h", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_interview_invites_app", "interview_invites", ["application_id", "status"])


def downgrade() -> None:
    op.drop_table("interview_invites")
    op.drop_table("candidate_phones")
    op.drop_column("recruit_calls", "callback_date")
    for c in ("match_detail", "match_score", "reject_code"):
        op.drop_column("applications", c)
    op.drop_constraint("uq_candidates_profile_token", "candidates")
    op.drop_index("ix_candidates_pinfl", table_name="candidates")
    for c in ("profile_confirmed_at", "profile_token", "profile", "pinfl"):
        op.drop_column("candidates", c)
    op.drop_column("vacancy_channels", "closed_at")
    op.drop_column("vacancies", "sla_overdue_at")
    op.drop_column("vacancies", "sla_warned_at")
    op.drop_table("position_requirement_versions")
    op.drop_column("position_requirements", "version")
    op.drop_column("position_requirements", "profile")
