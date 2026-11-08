"""prebording: video hodisalari (pauza, orqaga qaytish, «tushunmadim», ovozli izoh)

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internship_video_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("internship_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),  # pause | rewind | confused | voice
        sa.Column("pos", sa.Integer(), nullable=False),  # video joyi (s)
        sa.Column("to_pos", sa.Integer(), nullable=True),  # rewind: qaytgan joyi
        sa.Column("note", sa.Text(), nullable=True),  # matn yoki ovozdan olingan matn
        sa.Column("audio_key", sa.String(300), nullable=True),
        sa.Column("audio_mime", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_internship_video_events_step", "internship_video_events", ["step_id", "kind"])
    op.create_index("ix_internship_video_events_enr", "internship_video_events", ["enrollment_id"])


def downgrade() -> None:
    op.drop_table("internship_video_events")
