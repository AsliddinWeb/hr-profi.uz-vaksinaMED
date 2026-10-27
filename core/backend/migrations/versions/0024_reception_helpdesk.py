"""reception + helpdesk: visits, ticket_categories, tickets, ticket_events, ticket_files

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _fk(table, ondelete):
    return sa.ForeignKey(f"{table}.id", ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visitor_name", sa.String(160), nullable=False),
        sa.Column("visitor_phone", sa.String(32)),
        sa.Column("company", sa.String(120)),
        sa.Column("purpose", sa.String(12), nullable=False, server_default="meeting"),
        sa.Column("host_id", sa.Integer(), _fk("employees", "SET NULL")),
        sa.Column("branch_id", sa.Integer(), _fk("branches", "SET NULL")),
        sa.Column("expected_at", TS),
        sa.Column("arrived_at", TS),
        sa.Column("left_at", TS),
        sa.Column("status", sa.String(10), nullable=False, server_default="expected"),
        sa.Column("badge_no", sa.String(20)),
        sa.Column("doc_info", sa.String(60)),
        sa.Column("vehicle_plate", sa.String(16)),
        sa.Column("note", sa.Text()),
        sa.Column("registered_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("checked_in_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("checked_out_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_visits_status", "visits", ["status"])
    op.create_index("ix_visits_expected", "visits", ["expected_at"])
    op.create_index("ix_visits_arrived", "visits", ["arrived_at"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_no_seq")
    op.create_table(
        "ticket_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("default_assignee_id", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.execute("CREATE UNIQUE INDEX uq_ticket_categories_name ON ticket_categories (lower(name))")
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category_id", sa.Integer(), _fk("ticket_categories", "SET NULL")),
        sa.Column("priority", sa.String(8), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("requester_id", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("assignee_id", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("branch_id", sa.Integer(), _fk("branches", "SET NULL")),
        sa.Column("device_info", sa.String(200)),
        sa.Column("opened_at", TS, nullable=False),
        sa.Column("first_response_at", TS),
        sa.Column("resolved_at", TS),
        sa.Column("closed_at", TS),
        sa.Column("due_at", TS),
        sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution", sa.Text()),
        sa.Column("rating", sa.Integer()),
        sa.Column("rating_comment", sa.Text()),
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_requester", "tickets", ["requester_id"])
    op.create_index("ix_tickets_assignee", "tickets", ["assignee_id", "status"])
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.BigInteger(), _fk("tickets", "CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("from_status", sa.String(12)),
        sa.Column("to_status", sa.String(12)),
        sa.Column("note", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])
    op.create_table(
        "ticket_files",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.BigInteger(), _fk("tickets", "CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), _fk("users", "SET NULL")),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("mime", sa.String(80), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ticket_files_ticket_id", "ticket_files", ["ticket_id"])
    op.bulk_insert(
        sa.table("ticket_categories", sa.column("name", sa.String), sa.column("sort_order", sa.Integer)),
        [{"name": "Kompyuter va noutbuk", "sort_order": 1}, {"name": "Printer va skaner", "sort_order": 2}, {"name": "Internet va tarmoq", "sort_order": 3}, {"name": "Dastur (1C, Excel, tizim)", "sort_order": 4}, {"name": "Hisob va parol", "sort_order": 5}, {"name": "Boshqa", "sort_order": 9}],
    )


def downgrade() -> None:
    for t in ("ticket_files", "ticket_events", "tickets", "ticket_categories", "visits"):
        op.drop_table(t)
    op.execute("DROP SEQUENCE IF EXISTS ticket_no_seq")
