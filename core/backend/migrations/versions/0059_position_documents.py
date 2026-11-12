"""Lavozim hujjatlari, onlayn imzo, lavozim uchun shaxsiy hujjatlar; xodim hujjatining tekshiruv holati

Revision ID: 0059
Revises: 0058
"""
import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "position_doc_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hr_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("position_id", "document_id", name="uq_position_doc"),
    )
    op.create_table(
        "position_required_docs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.UniqueConstraint("position_id", "kind", "title", name="uq_position_required_doc"),
    )
    op.create_table(
        "document_signatures",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hr_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
        sa.UniqueConstraint("document_id", "version", "user_id", name="uq_document_signature"),
    )
    op.add_column("employee_documents", sa.Column("status", sa.String(10), nullable=False, server_default="approved"))
    op.add_column("employee_documents", sa.Column("review_note", sa.Text()))


def downgrade() -> None:
    op.drop_column("employee_documents", "review_note")
    op.drop_column("employee_documents", "status")
    op.drop_table("document_signatures")
    op.drop_table("position_required_docs")
    op.drop_table("position_doc_links")
