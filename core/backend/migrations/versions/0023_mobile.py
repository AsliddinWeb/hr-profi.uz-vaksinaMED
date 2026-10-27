"""mobile: mobile_permits, mobile_sessions, mobile_points, mobile_events

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _fk(table, ondelete):
    return sa.ForeignKey(f"{table}.id", ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "mobile_permits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_s", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("window_start", sa.Time(), nullable=False, server_default="08:00"),
        sa.Column("window_end", sa.Time(), nullable=False, server_default="20:00"),
        sa.Column("note", sa.String(300)),
        sa.Column("granted_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("consent_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "mobile_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("ended_at", TS),
        sa.Column("end_reason", sa.String(20)),
        sa.Column("attendance_id", sa.BigInteger(), _fk("attendance_records", "SET NULL")),
        sa.Column("attendance_created", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("start_lat", sa.Float()),
        sa.Column("start_lng", sa.Float()),
        sa.Column("end_lat", sa.Float()),
        sa.Column("end_lng", sa.Float()),
        sa.Column("distance_km", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("points_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_point_at", TS),
        sa.Column("last_battery", sa.Integer()),
        sa.Column("last_permission", sa.String(10)),
        sa.Column("gps_off", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signal_lost", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("low_battery_alerted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_mobile_sessions_employee", "mobile_sessions", ["employee_id", "started_at"])
    op.create_index("ix_mobile_sessions_status", "mobile_sessions", ["status"])
    op.create_table(
        "mobile_points",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), _fk("mobile_sessions", "CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float()),
        sa.Column("speed_kmh", sa.Float()),
        sa.Column("heading", sa.Float()),
        sa.Column("battery", sa.Integer()),
        sa.Column("charging", sa.Boolean()),
        sa.Column("recorded_at", TS, nullable=False),
    )
    op.create_index("ix_mobile_points_session_time", "mobile_points", ["session_id", "recorded_at"], unique=True)
    op.create_index("ix_mobile_points_time", "mobile_points", ["recorded_at"])
    op.create_table(
        "mobile_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), _fk("mobile_sessions", "SET NULL")),
        sa.Column("employee_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False, server_default="info"),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("acknowledged_at", TS),
        sa.Column("acknowledged_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("ack_note", sa.Text()),
    )
    op.create_index("ix_mobile_events_time", "mobile_events", ["created_at"])


def downgrade() -> None:
    for t in ("mobile_events", "mobile_points", "mobile_sessions", "mobile_permits"):
        op.drop_table(t)
