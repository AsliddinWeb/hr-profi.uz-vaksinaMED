"""canteen: settings, menus, dishes, ratings

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "canteen_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("qr_epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("require_qr", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rating_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("INSERT INTO canteen_settings (id, qr_epoch, require_qr, rating_days) VALUES (1, 0, false, 1)")
    op.create_table(
        "canteen_menus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("menu_date", sa.Date(), nullable=False, unique=True),
        sa.Column("note", sa.String(300)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "canteen_dishes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("menu_id", sa.Integer(), sa.ForeignKey("canteen_menus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="main"),
        sa.Column("description", sa.String(300)),
    )
    op.create_index("ix_canteen_dishes_menu_id", "canteen_dishes", ["menu_id"])
    op.create_table(
        "canteen_ratings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("menu_id", sa.Integer(), sa.ForeignKey("canteen_menus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dish_id", sa.BigInteger(), sa.ForeignKey("canteen_dishes.id", ondelete="CASCADE")),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("via_qr", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reply", sa.Text()),
        sa.Column("replied_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("replied_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_canteen_ratings_menu_id", "canteen_ratings", ["menu_id"])
    op.create_index("uq_canteen_rating_overall", "canteen_ratings", ["menu_id", "employee_id"], unique=True, postgresql_where=sa.text("dish_id IS NULL"))
    op.create_index("uq_canteen_rating_dish", "canteen_ratings", ["menu_id", "employee_id", "dish_id"], unique=True, postgresql_where=sa.text("dish_id IS NOT NULL"))


def downgrade() -> None:
    for t in ("canteen_ratings", "canteen_dishes", "canteen_menus", "canteen_settings"):
        op.drop_table(t)
