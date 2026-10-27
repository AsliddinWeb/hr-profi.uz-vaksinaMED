"""face: face_consents, face_templates, face_attempts

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "face_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("given_at", TS, nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("revoked_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "face_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pose", sa.String(10), nullable=False),
        sa.Column("vector_enc", sa.LargeBinary(), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("last_verified_at", TS),
    )
    op.create_index("ix_face_templates_employee_id", "face_templates", ["employee_id"])
    op.create_table(
        "face_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("purpose", sa.String(10), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("liveness_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(40)),
        sa.Column("frames", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_face_attempts_employee_id", "face_attempts", ["employee_id"])


def downgrade() -> None:
    op.drop_table("face_attempts")
    op.drop_table("face_templates")
    op.drop_table("face_consents")
