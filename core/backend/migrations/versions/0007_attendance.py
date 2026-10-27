"""attendance: attendance_records, attendance_corrections, branches.qr_epoch

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("branches", sa.Column("qr_epoch", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shift_templates.id", ondelete="SET NULL")),
        sa.Column("planned_start", TS),
        sa.Column("planned_end", TS),
        sa.Column("shift_kind", sa.String(10)),
        sa.Column("track_lateness", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("check_in_at", TS, nullable=False),
        sa.Column("check_out_at", TS),
        sa.Column("in_method", sa.String(10), nullable=False),
        sa.Column("out_method", sa.String(10)),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("in_lat", sa.Numeric(9, 6)),
        sa.Column("in_lng", sa.Numeric(9, 6)),
        sa.Column("in_distance_m", sa.Integer()),
        sa.Column("out_lat", sa.Numeric(9, 6)),
        sa.Column("out_lng", sa.Numeric(9, 6)),
        sa.Column("out_distance_m", sa.Integer()),
        sa.Column("late_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("early_leave_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),
    )
    op.create_index("ix_attendance_records_employee_id", "attendance_records", ["employee_id"])
    op.create_index("ix_attendance_work_date", "attendance_records", ["work_date"])
    op.create_table(
        "attendance_corrections",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB()),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attendance_corrections_employee_id", "attendance_corrections", ["employee_id"])


def downgrade() -> None:
    op.drop_table("attendance_corrections")
    op.drop_table("attendance_records")
    op.drop_column("branches", "qr_epoch")
