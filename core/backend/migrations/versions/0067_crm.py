import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

# Boshlang'ich voronka: nomi, ehtimollik %, yutildi?, avtomatik faoliyat, turi, necha kunda
STAGES = [
    ("Yangi", 10, False, "Mijozga qo'ng'iroq qilish", "call", 1),
    ("Malakali", 30, False, "Ehtiyojni aniqlash uchrashuvi", "meeting", 2),
    ("Taklif", 60, False, "Tijorat taklifini yuborish", "email", 1),
    ("Muzokara", 80, False, "Shartnoma shartlarini kelishish", "call", 2),
    ("Yutildi", 100, True, None, "task", 1),
]


def _user_fk(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    stages = op.create_table(
        "crm_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_activity", sa.String(160), nullable=True),
        sa.Column("auto_activity_kind", sa.String(10), nullable=False, server_default="call"),
        sa.Column("auto_activity_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_stamps(),
    )
    op.create_table(
        "crm_deals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(160), nullable=True),
        sa.Column("contact_name", sa.String(160), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(160), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expected_close", sa.Date(), nullable=True),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("crm_stages.id", ondelete="RESTRICT"), nullable=False),
        _user_fk("owner_id"),
        _user_fk("created_by"),
        sa.Column("position", sa.Float(), nullable=False, server_default="0"),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(300), nullable=True),
        sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_crm_deals_stage_id", "crm_deals", ["stage_id"])
    op.create_index("ix_crm_deals_stage", "crm_deals", ["stage_id", "position"])
    op.create_index("ix_crm_deals_owner", "crm_deals", ["owner_id"])
    op.create_table(
        "crm_activities",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("deal_id", sa.BigInteger(), sa.ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="call"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        _user_fk("assignee_id"),
        _user_fk("created_by"),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        _user_fk("done_by"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notified_overdue", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_stamps(),
    )
    op.create_index("ix_crm_activities_deal_id", "crm_activities", ["deal_id"])
    op.create_index("ix_crm_activities_open", "crm_activities", ["assignee_id", "done_at", "due_date"])
    op.create_table(
        "crm_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("deal_id", sa.BigInteger(), sa.ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("data", JSONB(), nullable=True),
        _user_fk("author_id"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_messages_deal_id", "crm_messages", ["deal_id"])
    op.bulk_insert(
        stages,
        [
            {"name": n, "probability": p, "sort_order": i, "is_won": w, "auto_activity": a, "auto_activity_kind": k, "auto_activity_days": d, "is_active": True}
            for i, (n, p, w, a, k, d) in enumerate(STAGES)
        ],
    )


def downgrade() -> None:
    op.drop_table("crm_messages")
    op.drop_table("crm_activities")
    op.drop_table("crm_deals")
    op.drop_table("crm_stages")
