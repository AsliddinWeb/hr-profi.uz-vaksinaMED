"""letters: letter_templates, explanation_letters, letter_events, letter_no_seq

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

DEFAULT_BODY = (
    "Men, {employee_name}, {department} bo'limi, {position}, {incident_date} sanasidagi holat ({incident}) bo'yicha "
    "quyidagilarni tushuntiraman:\n\n{explanation}\n\nIsh tartibi buzilishi takrorlanmasligini ma'lum qilaman."
)
DEFAULT_INSTRUCTIONS = (
    "Nima bo'lganini aniq va qisqa yozing: sana, vaqt, sabab. Mavjud bo'lsa tasdiqlovchi holatni (kasallik, transport, ruxsat) ko'rsating."
)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS letter_no_seq")
    op.create_table(
        "letter_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("recipient_line", sa.String(300), nullable=False, server_default=""),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.execute("CREATE UNIQUE INDEX uq_letter_templates_name ON letter_templates (lower(name))")
    op.execute("CREATE UNIQUE INDEX uq_letter_templates_single_default ON letter_templates (is_default) WHERE is_default")
    op.bulk_insert(
        sa.table(
            "letter_templates",
            sa.column("name", sa.String), sa.column("title", sa.String), sa.column("recipient_line", sa.String),
            sa.column("body_template", sa.Text), sa.column("instructions", sa.Text), sa.column("is_default", sa.Boolean),
        ),
        [{"name": "Standart tushuntirish xati", "title": "TUSHUNTIRISH XATI", "recipient_line": "HR direktoriga",
          "body_template": DEFAULT_BODY, "instructions": DEFAULT_INSTRUCTIONS, "is_default": True}],
    )
    op.create_table(
        "explanation_letters",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("letter_templates.id", ondelete="SET NULL")),
        sa.Column("incident_type", sa.String(14), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("incident_note", sa.Text()),
        sa.Column("due_date", sa.Date()),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("requested_at", TS, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("submitted_at", TS),
        sa.Column("snapshot", postgresql.JSONB()),
        sa.Column("signature", postgresql.JSONB()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", TS),
        sa.Column("review_note", sa.Text()),
        sa.Column("scan_key", sa.String(300)),
        sa.Column("scan_mime", sa.String(60)),
        sa.Column("scan_filename", sa.String(200)),
        sa.Column("scan_size", sa.Integer()),
        sa.Column("scan_uploaded_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_explanation_letters_employee_id", "explanation_letters", ["employee_id"])
    op.create_index("ix_letters_status", "explanation_letters", ["status"])
    op.create_table(
        "letter_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("letter_id", sa.BigInteger(), sa.ForeignKey("explanation_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_letter_events_letter_id", "letter_events", ["letter_id"])


def downgrade() -> None:
    op.drop_table("letter_events")
    op.drop_table("explanation_letters")
    op.drop_table("letter_templates")
    op.execute("DROP SEQUENCE IF EXISTS letter_no_seq")
