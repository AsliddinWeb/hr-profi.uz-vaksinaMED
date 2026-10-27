"""recruit: suhbat natijasi, fon tekshiruv, AI skaner, job offer, qo'ng'iroqlar jurnali, nomzod Telegram chat

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _user_fk():
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    cols = [
        sa.Column("experience_level", sa.String(8)), sa.Column("hard_skill", sa.Integer()), sa.Column("soft_skill", sa.Integer()),
        sa.Column("interview_notes", sa.Text()), sa.Column("interviewed_by", sa.Integer(), _user_fk()), sa.Column("interviewed_at", TS),
        sa.Column("bg_status", sa.String(8)), sa.Column("bg_note", sa.Text()), sa.Column("bg_by", sa.Integer(), _user_fk()), sa.Column("bg_at", TS),
        sa.Column("ai_scan", postgresql.JSONB()), sa.Column("ai_scan_at", TS),
        sa.Column("offer_status", sa.String(12)), sa.Column("offer_level", sa.String(10)), sa.Column("offer_salary", sa.Integer()),
        sa.Column("offer_start", sa.Date()), sa.Column("offer_note", sa.Text()), sa.Column("offer_by", sa.Integer(), _user_fk()),
        sa.Column("offer_decided_by", sa.Integer(), _user_fk()), sa.Column("offer_decided_at", TS), sa.Column("offer_decision_note", sa.Text()),
        sa.Column("offer_sent_at", TS),
    ]
    for c in cols:
        op.add_column("applications", c)
    op.add_column("candidates", sa.Column("telegram_chat_id", sa.BigInteger(), unique=True))
    op.create_table(
        "recruit_calls",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("recruiter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(13)),
        sa.Column("candidate_id", sa.BigInteger(), sa.ForeignKey("candidates.id", ondelete="SET NULL")),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="SET NULL")),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("called_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recruit_calls_recruiter_id", "recruit_calls", ["recruiter_id"])
    op.create_index("ix_recruit_calls_called_at", "recruit_calls", ["called_at"])


def downgrade() -> None:
    op.drop_table("recruit_calls")
    op.drop_column("candidates", "telegram_chat_id")
    for c in ("offer_sent_at", "offer_decision_note", "offer_decided_at", "offer_decided_by", "offer_by", "offer_note", "offer_start", "offer_salary", "offer_level", "offer_status",
              "ai_scan_at", "ai_scan", "bg_at", "bg_by", "bg_note", "bg_status", "interviewed_at", "interviewed_by", "interview_notes", "soft_skill", "hard_skill", "experience_level"):
        op.drop_column("applications", c)
