"""Bir nechta tahrirlanadigan tashkiliy tuzilma

Revision ID: 0052
Revises: 0051
"""
import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "org_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(300)),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_org_structures_default", "org_structures", ["is_default"], unique=True, postgresql_where=sa.text("is_default"))
    op.create_table(
        "org_structure_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("org_structures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("parent_position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("structure_id", "position_id", name="uq_org_structure_position"),
    )
    op.create_index("ix_org_structure_positions_structure_id", "org_structure_positions", ["structure_id"])
    op.create_index("ix_org_structure_positions_position_id", "org_structure_positions", ["position_id"])
    op.create_table(
        "org_structure_departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("org_structures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("reports_to_position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL")),
        sa.UniqueConstraint("structure_id", "department_id", name="uq_org_structure_department"),
    )
    op.create_index("ix_org_structure_departments_structure_id", "org_structure_departments", ["structure_id"])
    op.create_index("ix_org_structure_departments_department_id", "org_structure_departments", ["department_id"])

    op.execute("INSERT INTO org_structures (name, description, is_default) VALUES ('Asosiy tuzilma', 'Boshlang‘ich tuzilma: hozirgi bo‘ysunish tartibidan nusxa.', true)")
    op.execute("""
        INSERT INTO org_structure_positions (structure_id, position_id, department_id, parent_position_id, sort_order)
        SELECT s.id, p.id, p.department_id, p.parent_id, p.sort_order
        FROM org_structures s CROSS JOIN positions p WHERE s.is_default
    """)
    op.execute("""
        INSERT INTO org_structure_departments (structure_id, department_id, parent_department_id, reports_to_position_id)
        SELECT s.id, d.id, d.parent_id, d.reports_to_position_id
        FROM org_structures s CROSS JOIN departments d WHERE s.is_default
    """)


def downgrade() -> None:
    op.drop_index("ix_org_structure_departments_department_id", table_name="org_structure_departments")
    op.drop_index("ix_org_structure_departments_structure_id", table_name="org_structure_departments")
    op.drop_table("org_structure_departments")
    op.drop_index("ix_org_structure_positions_position_id", table_name="org_structure_positions")
    op.drop_index("ix_org_structure_positions_structure_id", table_name="org_structure_positions")
    op.drop_table("org_structure_positions")
    op.drop_index("uq_org_structures_default", table_name="org_structures")
    op.drop_table("org_structures")
