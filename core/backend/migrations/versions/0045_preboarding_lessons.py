"""prebording: dars bosqichi (video + slayd + test), auditoriya, e'lon, ko'rish nazorati, kamera/mikrofon kuzatuvi

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
MONITOR_DEFAULT = '{"camera": true, "live": true, "record": true, "snapshots": true}'


def upgrade() -> None:
    op.add_column("internship_steps", sa.Column("slides_url", sa.String(500), nullable=True))
    op.add_column("internship_steps", sa.Column("audience", sa.String(10), server_default="all", nullable=False))
    op.add_column("internship_steps", sa.Column("published", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("internship_steps", sa.Column("min_video_seconds", sa.Integer(), nullable=True))
    op.add_column("internship_steps", sa.Column("min_slides_seconds", sa.Integer(), nullable=True))
    op.add_column("internship_programs", sa.Column("monitoring", postgresql.JSONB(), server_default=sa.text(f"'{MONITOR_DEFAULT}'::jsonb"), nullable=False))
    op.add_column("internship_enrollments", sa.Column("monitor_consent_at", TS, nullable=True))

    op.create_table(
        "internship_views",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("internship_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),  # video | slides
        sa.Column("seconds", sa.Integer(), server_default="0", nullable=False),  # haqiqatda ko'rilgan (faol oyna, 1x)
        sa.Column("duration", sa.Integer(), nullable=True),  # video uzunligi (YouTube)
        sa.Column("max_pos", sa.Integer(), server_default="0", nullable=False),  # eng uzoq ko'rilgan joy (s)
        sa.Column("done", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("enrollment_id", "step_id", "kind", name="uq_internship_views"),
    )
    op.create_table(
        "internship_monitor",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("enrollment_id", sa.BigInteger(), sa.ForeignKey("internship_enrollments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("internship_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("room", sa.String(80), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("ended_at", TS, nullable=True),
        sa.Column("clips", postgresql.JSONB(), server_default="[]", nullable=False),  # [{key, at, size, mime}]
        sa.Column("snapshots", postgresql.JSONB(), server_default="[]", nullable=False),  # [{key, at}]
        sa.Column("events", postgresql.JSONB(), server_default="[]", nullable=False),  # [{at, kind}] kamera o'chdi, oyna yashirildi...
    )


def downgrade() -> None:
    op.drop_table("internship_monitor")
    op.drop_table("internship_views")
    op.drop_column("internship_enrollments", "monitor_consent_at")
    op.drop_column("internship_programs", "monitoring")
    for col in ("min_slides_seconds", "min_video_seconds", "published", "audience", "slides_url"):
        op.drop_column("internship_steps", col)
