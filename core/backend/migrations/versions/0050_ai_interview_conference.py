"""AI suhbat, ovoz chiqarib o'qish va onlayn konferensiyalar

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ai_interviews",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("token", sa.String(24), unique=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id", ondelete="CASCADE"), index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), index=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), server_default="sent", nullable=False),
        sa.Column("questions", JSONB, server_default="[]", nullable=False),
        sa.Column("answers", JSONB, server_default="{}", nullable=False),
        sa.Column("scores", JSONB, server_default="{}", nullable=False),
        sa.Column("hard_pct", sa.Integer()),
        sa.Column("soft_pct", sa.Integer()),
        sa.Column("summary", sa.Text()),
        sa.Column("lang", sa.String(2), server_default="uz", nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", TS),
        sa.Column("graded_at", TS),
    )
    op.create_table(
        "read_aloud_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("internship_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("accuracy", sa.Integer(), nullable=False),
        sa.Column("missed", JSONB, server_default="[]", nullable=False),
        sa.Column("duration_s", sa.Integer()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "conferences",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("room", sa.String(64), unique=True, nullable=False),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("duration_min", sa.Integer(), server_default="60", nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="100", nullable=False),
        sa.Column("audience", JSONB, server_default="{}", nullable=False),
        sa.Column("status", sa.String(10), server_default="scheduled", nullable=False),
        sa.Column("tasks", JSONB, server_default="[]", nullable=False),
        sa.Column("auto_tasks_for_absent", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("recording_url", sa.String(500)),
        sa.Column("started_at", TS),
        sa.Column("ended_at", TS),
        sa.Column("report", JSONB, server_default="{}", nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conferences_starts_at", "conferences", ["starts_at"])
    op.create_table(
        "conference_attendees",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("conference_id", sa.BigInteger(), sa.ForeignKey("conferences.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_join_at", TS, nullable=False),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("joins", sa.Integer(), server_default="1", nullable=False),
        sa.UniqueConstraint("conference_id", "user_id", name="uq_conference_attendee"),
    )


def downgrade() -> None:
    op.drop_table("conference_attendees")
    op.drop_index("ix_conferences_starts_at", table_name="conferences")
    op.drop_table("conferences")
    op.drop_table("read_aloud_attempts")
    op.drop_table("ai_interviews")
