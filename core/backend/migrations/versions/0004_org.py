"""org: departments, positions, branches

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
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
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "parent_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="RESTRICT")
        ),
        sa.Column("head_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(20), nullable=False, server_default="office"),
        sa.Column("color", sa.String(7)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    # Bir xil ota ostida bir xil nomli bo'lim bo'lmaydi (katta-kichik harfsiz)
    op.execute(
        "CREATE UNIQUE INDEX uq_departments_parent_name "
        "ON departments (COALESCE(parent_id, 0), lower(name))"
    )
    op.create_index("ix_departments_parent_id", "departments", ["parent_id"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE")
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_positions_department_name "
        "ON positions (COALESCE(department_id, 0), lower(name))"
    )

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer()),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("address", sa.String(300)),
        sa.Column("district", sa.String(100)),
        sa.Column("phone", sa.String(32)),
        sa.Column(
            "department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")
        ),
        sa.Column(
            "manager_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "coordinator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("geofence_radius_m", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("opened_at", TS),
        *_ts(),
        sa.UniqueConstraint("number", name="uq_branches_number"),
        sa.CheckConstraint("geofence_radius_m BETWEEN 10 AND 5000", name="ck_branches_radius"),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_branches_coords_pair"
        ),
    )
    op.create_index("ix_branches_coordinator_user_id", "branches", ["coordinator_user_id"])
    op.create_index("ix_branches_manager_user_id", "branches", ["manager_user_id"])


def downgrade() -> None:
    op.drop_table("branches")
    op.drop_table("positions")
    op.drop_table("departments")
