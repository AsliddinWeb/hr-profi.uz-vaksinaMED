"""logistics: vehicles, vehicle_documents, driver_profiles, trips, gps_points, fuel_logs

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _ts():
    return [sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False), sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False)]


def _fk(table, ondelete):
    return sa.ForeignKey(f"{table}.id", ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plate", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="car"),
        sa.Column("fuel_type", sa.String(10), nullable=False, server_default="petrol"),
        sa.Column("fuel_norm", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("tank_l", sa.Integer()),
        sa.Column("odometer_km", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("branch_id", sa.Integer(), _fk("branches", "SET NULL")),
        sa.Column("status", sa.String(8), nullable=False, server_default="active"),
        sa.Column("note", sa.String(300)),
        *_ts(),
    )
    op.execute("CREATE UNIQUE INDEX uq_vehicles_plate ON vehicles (upper(plate))")
    op.create_table(
        "vehicle_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), _fk("vehicles", "CASCADE"), nullable=False),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("number", sa.String(60)),
        sa.Column("issued_at", sa.Date()),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("notified_stage", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_vehicle_documents_vehicle_id", "vehicle_documents", ["vehicle_id"])
    op.create_table(
        "driver_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False, unique=True),
        sa.Column("license_no", sa.String(30)),
        sa.Column("categories", sa.String(30)),
        sa.Column("license_expires", sa.Date()),
        sa.Column("note", sa.String(300)),
        sa.Column("notified_stage", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_table(
        "trips",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), _fk("vehicles", "RESTRICT"), nullable=False),
        sa.Column("driver_id", sa.Integer(), _fk("employees", "RESTRICT"), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("origin", sa.String(200)),
        sa.Column("destination", sa.String(200)),
        sa.Column("planned_start", TS),
        sa.Column("status", sa.String(10), nullable=False, server_default="planned"),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.Column("start_odometer", sa.Integer()),
        sa.Column("end_odometer", sa.Integer()),
        sa.Column("distance_km", sa.Numeric(9, 1)),
        sa.Column("gps_km", sa.Numeric(9, 1)),
        sa.Column("fuel_norm_l", sa.Numeric(9, 2)),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), _fk("users", "SET NULL")),
        *_ts(),
    )
    op.create_index("ix_trips_driver_status", "trips", ["driver_id", "status"])
    op.create_index("ix_trips_vehicle_status", "trips", ["vehicle_id", "status"])
    op.create_table(
        "gps_points",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), _fk("vehicles", "CASCADE"), nullable=False),
        sa.Column("trip_id", sa.BigInteger(), _fk("trips", "CASCADE"), nullable=False),
        sa.Column("driver_id", sa.Integer(), _fk("employees", "CASCADE"), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("speed_kmh", sa.Float()),
        sa.Column("accuracy_m", sa.Float()),
        sa.Column("heading", sa.Float()),
        sa.Column("recorded_at", TS, nullable=False),
        sa.Column("received_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gps_trip_time", "gps_points", ["trip_id", "recorded_at"], unique=True)
    op.create_index("ix_gps_vehicle_time", "gps_points", ["vehicle_id", "recorded_at"])
    op.create_index("ix_gps_driver_time", "gps_points", ["driver_id", "recorded_at"])
    op.create_table(
        "fuel_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), _fk("vehicles", "CASCADE"), nullable=False),
        sa.Column("trip_id", sa.BigInteger(), _fk("trips", "SET NULL")),
        sa.Column("driver_id", sa.Integer(), _fk("employees", "SET NULL")),
        sa.Column("fueled_at", TS, nullable=False),
        sa.Column("liters", sa.Numeric(8, 2), nullable=False),
        sa.Column("price_per_liter", sa.Numeric(10, 2)),
        sa.Column("total", sa.Numeric(14, 2)),
        sa.Column("odometer_km", sa.Integer()),
        sa.Column("station", sa.String(120)),
        sa.Column("full_tank", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), _fk("users", "SET NULL")),
        *_ts(),
    )
    op.create_index("ix_fuel_vehicle_time", "fuel_logs", ["vehicle_id", "fueled_at"])


def downgrade() -> None:
    for t in ("fuel_logs", "gps_points", "trips", "driver_profiles", "vehicle_documents", "vehicles"):
        op.drop_table(t)
