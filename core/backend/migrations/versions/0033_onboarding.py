"""onboarding: dastur fazalari, 7 kunlik hisobot va fidbek, 7-kun qarori, oflayn darslar, kadrovik hujjatlari

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.add_column("internship_programs", sa.Column("phase", sa.String(12), nullable=False, server_default="preboarding"))
    op.add_column("internship_programs", sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")))
    op.add_column("internship_programs", sa.Column("duration_days", sa.Integer()))
    op.add_column("internship_enrollments", sa.Column("phase", sa.String(12), nullable=False, server_default="preboarding"))
    op.add_column("internship_enrollments", sa.Column("day7_decision", sa.String(8)))
    op.add_column("internship_enrollments", sa.Column("day7_note", sa.Text()))
    op.add_column("internship_enrollments", sa.Column("day7_by", sa.Integer(), _user()))
    op.add_column("internship_enrollments", sa.Column("day7_at", TS))
    op.add_column("internship_enrollments", sa.Column("next_enrollment_id", sa.BigInteger()))

    op.create_table(
        "internship_daily",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_no", sa.Integer(), nullable=False),
        sa.Column("seen", sa.Text()), sa.Column("understood", sa.Text()), sa.Column("done", sa.Text()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("enrollment_id", "day_no", name="uq_internship_daily"),
    )
    op.create_index("ix_internship_daily_enrollment_id", "internship_daily", ["enrollment_id"])
    op.create_table(
        "internship_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_no", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), _user()),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_internship_feedback_enrollment_id", "internship_feedback", ["enrollment_id"])
    op.create_table(
        "class_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="lesson"),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("place", sa.String(200)),
        sa.Column("trainer_id", sa.Integer(), _user()),
        sa.Column("created_by", sa.Integer(), _user()),
        sa.Column("attendance_marked_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_class_sessions_starts_at", "class_sessions", ["starts_at"])
    op.create_table(
        "class_attendees",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("present", sa.Boolean()),
        sa.UniqueConstraint("session_id", "employee_id", name="uq_class_attendee"),
    )
    op.create_index("ix_class_attendees_session_id", "class_attendees", ["session_id"])
    op.create_index("ix_class_attendees_employee_id", "class_attendees", ["employee_id"])
    op.create_table(
        "hire_docs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("docs_received_at", TS), sa.Column("docs_received_by", sa.Integer(), _user()), sa.Column("docs_note", sa.Text()),
        sa.Column("order_ready_at", TS), sa.Column("order_ready_by", sa.Integer(), _user()), sa.Column("order_no", sa.String(40)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for t in ("hire_docs", "class_attendees", "class_sessions", "internship_feedback", "internship_daily"):
        op.drop_table(t)
    for c in ("next_enrollment_id", "day7_at", "day7_by", "day7_note", "day7_decision", "phase"):
        op.drop_column("internship_enrollments", c)
    for c in ("duration_days", "position_id", "phase"):
        op.drop_column("internship_programs", c)
