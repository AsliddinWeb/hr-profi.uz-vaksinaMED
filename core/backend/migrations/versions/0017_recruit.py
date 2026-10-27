"""recruit: vacancies, candidates, applications, application_events, candidate_files

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def _fk(table, col="id", ondelete="SET NULL"):
    return sa.ForeignKey(f"{table}.{col}", ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("branch_id", sa.Integer(), _fk("branches")),
        sa.Column("department_id", sa.Integer(), _fk("departments")),
        sa.Column("position_id", sa.Integer(), _fk("positions")),
        sa.Column("description", sa.Text()),
        sa.Column("requirements", sa.Text()),
        sa.Column("salary_from", sa.Integer()),
        sa.Column("salary_to", sa.Integer()),
        sa.Column("openings", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(8), nullable=False, server_default="draft"),
        sa.Column("recruiter_id", sa.Integer(), _fk("users")),
        sa.Column("deadline", sa.Date()),
        sa.Column("opened_at", TS),
        sa.Column("closed_at", TS),
        sa.Column("created_by", sa.Integer(), _fk("users")),
        *_ts(),
    )
    op.create_index("ix_vacancies_status", "vacancies", ["status"])
    op.create_table(
        "candidates",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("full_name", sa.String(250), nullable=False),
        sa.Column("phone", sa.String(13)),
        sa.Column("email", sa.String(120)),
        sa.Column("birth_date", sa.Date()),
        sa.Column("address", sa.String(300)),
        sa.Column("source", sa.String(40)),
        sa.Column("skills", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("resume_text", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), _fk("users")),
        *_ts(),
    )
    op.create_index("ix_candidates_full_name", "candidates", ["full_name"])
    op.create_index("ix_candidates_phone", "candidates", ["phone"])
    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), _fk("vacancies", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), _fk("candidates", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(10), nullable=False, server_default="new"),
        sa.Column("rating", sa.Integer()),
        sa.Column("reject_reason", sa.String(300)),
        sa.Column("interview_at", TS),
        sa.Column("recruiter_id", sa.Integer(), _fk("users")),
        sa.Column("applied_at", TS, nullable=False),
        sa.Column("stage_changed_at", TS, nullable=False),
        sa.Column("employee_id", sa.Integer(), _fk("employees")),
        sa.Column("hired_at", TS),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("vacancy_id", "candidate_id", name="uq_application"),
        *_ts(),
    )
    op.create_index("ix_applications_stage", "applications", ["vacancy_id", "stage"])
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), _fk("applications", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), _fk("users")),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("from_stage", sa.String(10)),
        sa.Column("to_stage", sa.String(10)),
        sa.Column("note", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])
    op.create_table(
        "candidate_files",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), _fk("candidates", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), _fk("users")),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("mime", sa.String(80), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidate_files_candidate_id", "candidate_files", ["candidate_id"])


def downgrade() -> None:
    for t in ("candidate_files", "application_events", "applications", "candidates", "vacancies"):
        op.drop_table(t)
