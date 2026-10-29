"""hr_documents (+versions, acks), staff_documents (ariza/buyruq), raqam ketma-ketliklari

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "hr_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(40), unique=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(300)),
        sa.Column("body", sa.Text()),
        sa.Column("file_key", sa.String(300)),
        sa.Column("file_name", sa.String(160)),
        sa.Column("file_mime", sa.String(100)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("requires_ack", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("roles", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", TS),
        sa.Column("updated_by", sa.Integer(), _user()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_documents_category", "hr_documents", ["category", "sort_order"])
    op.create_table(
        "hr_document_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hr_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("file_key", sa.String(300)),
        sa.Column("file_name", sa.String(160)),
        sa.Column("note", sa.String(300)),
        sa.Column("changed_by", sa.Integer(), _user()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "version", name="uq_hr_document_versions"),
    )
    op.create_index("ix_hr_document_versions_document_id", "hr_document_versions", ["document_id"])
    op.create_table(
        "hr_document_acks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hr_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", TS, nullable=False),
        sa.UniqueConstraint("document_id", "user_id", name="uq_hr_document_acks"),
    )
    op.create_index("ix_hr_document_acks_document_id", "hr_document_acks", ["document_id"])
    op.create_index("ix_hr_document_acks_user_id", "hr_document_acks", ["user_id"])
    op.create_table(
        "staff_documents",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("subtype", sa.String(12), nullable=False),
        sa.Column("number", sa.String(20), unique=True),
        sa.Column("code", sa.String(32), unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("related_id", sa.BigInteger(), sa.ForeignKey("staff_documents.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.Integer(), _user()),
        sa.Column("decided_by", sa.Integer(), _user()),
        sa.Column("decided_at", TS),
        sa.Column("decision_note", sa.Text()),
        sa.Column("signed_by", sa.Integer(), _user()),
        sa.Column("signed_at", TS),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("acknowledged_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_staff_documents_employee", "staff_documents", ["employee_id", "kind"])
    op.create_index("ix_staff_documents_status", "staff_documents", ["kind", "status"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS staff_app_no_seq")
    op.execute("CREATE SEQUENCE IF NOT EXISTS staff_order_no_seq")


def downgrade() -> None:
    for t in ("staff_documents", "hr_document_acks", "hr_document_versions", "hr_documents"):
        op.drop_table(t)
    op.execute("DROP SEQUENCE IF EXISTS staff_app_no_seq")
    op.execute("DROP SEQUENCE IF EXISTS staff_order_no_seq")
