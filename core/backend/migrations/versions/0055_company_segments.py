"""Kompaniyaga moslanadigan xodim segmentlari va sozlamalar (Ofis / Dorixona / Hammasi — standart)

Revision ID: 0055
Revises: 0054
"""
import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(200)),
        sa.Column("scope", sa.String(8), nullable=False, server_default="all"),
        sa.Column("department_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("position_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("color", sa.String(16)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "company_settings",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("value", sa.JSON()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "INSERT INTO employee_segments (name, description, scope, sort_order, color) VALUES "
        "('Ofis', 'Ofis xodimlari (filialga biriktirilmagan)', 'office', 1, '#2563eb'), "
        "('Dorixona', 'Filial xodimlari: mudir, farmasevt, stajyor', 'branch', 2, '#16a34a'), "
        "('Hammasi', 'Ofis va filiallar birgalikda', 'all', 3, '#64748b')"
    )
    op.execute("""INSERT INTO company_settings (key, value) VALUES ('checklists.month_limit', '4'), ('revisions.cycle_days', '90')""")


def downgrade() -> None:
    op.drop_table("company_settings")
    op.drop_table("employee_segments")
