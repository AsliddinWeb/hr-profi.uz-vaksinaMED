"""internship: programs, steps, enrollments, progress

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "internship_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("sequential", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_internship_programs_name ON internship_programs (lower(name))")
    op.create_table(
        "internship_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("internship_programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("url", sa.String(500)),
        sa.Column("file_key", sa.String(300)),
        sa.Column("file_name", sa.String(200)),
        sa.Column("file_mime", sa.String(80)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("questions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("pass_score", sa.Integer()),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_internship_steps_program", "internship_steps", ["program_id", "position"])
    op.create_table(
        "internship_enrollments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("internship_programs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("ready_at", TS),
        sa.Column("completed_at", TS),
        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("final_score", sa.Float()),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_ts(),
    )
    op.create_index("ix_internship_enrollments_employee", "internship_enrollments", ["employee_id", "status"])
    op.create_table(
        "internship_progress",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("internship_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("score", sa.Integer()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", TS),
        sa.UniqueConstraint("enrollment_id", "step_id", name="uq_internship_progress"),
    )
    op.create_index("ix_internship_progress_enrollment_id", "internship_progress", ["enrollment_id"])


def downgrade() -> None:
    for t in ("internship_progress", "internship_enrollments", "internship_steps", "internship_programs"):
        op.drop_table(t)
