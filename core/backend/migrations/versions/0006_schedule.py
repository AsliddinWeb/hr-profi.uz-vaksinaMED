"""schedule: shift_templates, work_groups, schedule_patterns, schedule_entries, holidays

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "shift_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("code", sa.String(4)),
        sa.Column("kind", sa.String(10), nullable=False, server_default="fixed"),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("late_grace_minutes", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("early_leave_grace_minutes", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("min_work_minutes", sa.SmallInteger()),
        sa.Column("track_lateness", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("color", sa.String(7)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_shift_templates_name ON shift_templates (lower(name))")

    op.create_table(
        "work_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="office"),
        sa.Column("description", sa.String(300)),
        sa.Column(
            "default_shift_id", sa.Integer(), sa.ForeignKey("shift_templates.id", ondelete="RESTRICT")
        ),
        sa.Column("weekly_off_days", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("observe_holidays", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("attendance_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_work_groups_name ON work_groups (lower(name))")
    # Faqat bitta standart guruh bo'lishi mumkin
    op.execute("CREATE UNIQUE INDEX uq_work_groups_single_default ON work_groups (is_default) WHERE is_default")

    op.create_table(
        "schedule_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("cycle", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_schedule_patterns_name ON schedule_patterns (lower(name))")

    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shift_templates.id", ondelete="RESTRICT")),
        sa.Column("source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "date", name="uq_schedule_entries_employee_date"),
    )
    op.create_index("ix_schedule_entries_employee_id", "schedule_entries", ["employee_id"])
    op.create_index("ix_schedule_entries_date", "schedule_entries", ["date"])

    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.SmallInteger()),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="holiday"),
        sa.Column("note", sa.Text()),
    )
    op.execute("CREATE UNIQUE INDEX uq_holidays_date ON holidays (COALESCE(year, 0), month, day)")

    op.add_column(
        "employees",
        sa.Column("work_group_id", sa.Integer(), sa.ForeignKey("work_groups.id", ondelete="SET NULL")),
    )
    op.create_index("ix_employees_work_group_id", "employees", ["work_group_id"])


def downgrade() -> None:
    op.drop_index("ix_employees_work_group_id", table_name="employees")
    op.drop_column("employees", "work_group_id")
    op.drop_table("holidays")
    op.drop_table("schedule_entries")
    op.drop_table("schedule_patterns")
    op.drop_table("work_groups")
    op.drop_table("shift_templates")
