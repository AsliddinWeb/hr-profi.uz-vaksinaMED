"""example: client_note jadvali (extension migratsiyasi misoli)

Revision ID: ext0001
Revises:
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "ext0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("client_note")
