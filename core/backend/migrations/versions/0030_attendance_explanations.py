"""attendance_explanations: koordinator hisobotidagi izohlar

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "attendance_explanations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("coordinator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text()),
        sa.Column("measures", sa.Text()),
        sa.Column("due_at", TS, nullable=False),
        sa.Column("submitted_at", TS),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("overdue_notified_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "work_date", "kind", name="uq_attendance_explanation"),
    )
    op.create_index("ix_attendance_explanations_employee_id", "attendance_explanations", ["employee_id"])
    op.create_index("ix_attendance_explanations_coordinator_user_id", "attendance_explanations", ["coordinator_user_id"])
    op.create_index("ix_attendance_explanations_status", "attendance_explanations", ["status", "due_at"])


def downgrade() -> None:
    op.drop_table("attendance_explanations")
