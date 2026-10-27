"""penalties: penalty_rule_versions, penalties

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-22
"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# Boshlang'ich qoidalar: MISOL summalar, mijoz o'z siyosatiga moslab yangi versiya yaratadi.
DEFAULT = {
    "auto_scan": False,
    "window_days": 90,
    "count_mode": "all",
    "triggers": {
        "late": {"enabled": True, "min_minutes": 10},
        "early_leave": {"enabled": True, "min_minutes": 10},
        "absent": {"enabled": True, "min_minutes": 0},
        "no_checkout": {"enabled": False, "min_minutes": 0},
    },
    "steps": [
        {"step": 1, "label": "Og'zaki ogohlantirish", "amount": 0, "block_days": 0},
        {"step": 2, "label": "Yozma ogohlantirish", "amount": 0, "block_days": 0},
        {"step": 3, "label": "Jarima (1-daraja)", "amount": 50000, "block_days": 0},
        {"step": 4, "label": "Jarima (2-daraja)", "amount": 100000, "block_days": 0},
        {"step": 5, "label": "Jarima (3-daraja)", "amount": 200000, "block_days": 0},
        {"step": 6, "label": "Jarima va vaqtincha blok", "amount": 200000, "block_days": 3},
    ],
}


def upgrade() -> None:
    op.create_table(
        "penalty_rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.execute(sa.text("INSERT INTO penalty_rule_versions (version, config, note) VALUES (1, CAST(:c AS jsonb), :n)").bindparams(c=json.dumps(DEFAULT), n="Boshlang'ich (misol) qoidalar"))
    op.create_table(
        "penalties",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_type", sa.String(14), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("rule_version_id", sa.Integer(), sa.ForeignKey("penalty_rule_versions.id", ondelete="SET NULL")),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("block_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", TS),
        sa.Column("decision_note", sa.Text()),
        sa.Column("block_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_until", sa.Date()),
        sa.Column("unblocked_at", TS),
    )
    op.create_index("ix_penalties_employee_date", "penalties", ["employee_id", "incident_date"])
    op.create_index("ix_penalties_status", "penalties", ["status"])
    op.execute("CREATE UNIQUE INDEX uq_penalties_auto ON penalties (employee_id, incident_date, incident_type) WHERE source = 'auto'")


def downgrade() -> None:
    op.drop_table("penalties")
    op.drop_table("penalty_rule_versions")
