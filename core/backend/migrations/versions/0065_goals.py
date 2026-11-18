import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def _user_fk(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "goal_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("note", sa.Text(), nullable=True),
        _user_fk("submitted_by"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        _user_fk("approved_by"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.UniqueConstraint("department_id", "year", name="uq_goal_plan_dept_year"),
    )
    op.create_index("ix_goal_plans_department_id", "goal_plans", ["department_id"])
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("goal_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("specific", sa.Text(), nullable=True),
        sa.Column("metric", sa.String(120), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("baseline", sa.Float(), nullable=True),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("current", sa.Float(), nullable=True),
        sa.Column("achievable", sa.Text(), nullable=True),
        sa.Column("relevant", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=False),
        _user_fk("owner_user_id"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_goals_plan_id", "goals", ["plan_id"])
    op.create_table(
        "goal_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("goal_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("before", JSONB(), nullable=True),
        sa.Column("after", JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        _user_fk("requested_by"),
        _user_fk("decided_by"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_goal_changes_plan_id", "goal_changes", ["plan_id"])


def downgrade() -> None:
    op.drop_table("goal_changes")
    op.drop_table("goals")
    op.drop_table("goal_plans")
