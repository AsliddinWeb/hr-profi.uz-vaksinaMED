"""employees, employee_events, employee_documents

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE employee_no_seq START 1")
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_no", sa.Integer(), server_default=sa.text("nextval('employee_no_seq')"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("middle_name", sa.String(80)),
        sa.Column("full_name", sa.String(250), nullable=False),
        sa.Column("birth_date", sa.Date()),
        sa.Column("gender", sa.String(1)),
        sa.Column("phone", sa.String(13)),
        sa.Column("phone2", sa.String(13)),
        sa.Column("email", sa.String(120)),
        sa.Column("address", sa.String(300)),
        sa.Column("passport_no", sa.String(12)),
        sa.Column("pinfl", sa.String(14)),
        sa.Column("photo_key", sa.String(300)),
        sa.Column("photo_mime", sa.String(60)),
        sa.Column(
            "department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="RESTRICT")
        ),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="RESTRICT")),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("hire_date", sa.Date()),
        sa.Column("dismissal_date", sa.Date()),
        sa.Column("dismissal_reason", sa.String(20)),
        sa.Column("dismissal_note", sa.String(500)),
        *_ts(),
        sa.UniqueConstraint("employee_no", name="uq_employees_employee_no"),
        sa.UniqueConstraint("user_id", name="uq_employees_user_id"),
        sa.UniqueConstraint("passport_no", name="uq_employees_passport_no"),
        sa.UniqueConstraint("pinfl", name="uq_employees_pinfl"),
    )
    op.create_index("ix_employees_full_name", "employees", ["full_name"])
    op.create_index("ix_employees_phone", "employees", ["phone"])
    op.create_index("ix_employees_status", "employees", ["status"])
    op.create_index("ix_employees_department_id", "employees", ["department_id"])
    op.create_index("ix_employees_branch_id", "employees", ["branch_id"])

    op.create_table(
        "employee_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("note", sa.String(500)),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_employee_events_employee", "employee_events", ["employee_id", "effective_date"]
    )

    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("file_key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("mime", sa.String(80), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.Date()),
        sa.Column("expires_at", sa.Date()),
        sa.Column("note", sa.Text()),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_ts(),
    )
    op.create_index("ix_employee_documents_employee", "employee_documents", ["employee_id"])


def downgrade() -> None:
    op.drop_table("employee_documents")
    op.drop_table("employee_events")
    op.drop_table("employees")
    op.execute("DROP SEQUENCE employee_no_seq")
