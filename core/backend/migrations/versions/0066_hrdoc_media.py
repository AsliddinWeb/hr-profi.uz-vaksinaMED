import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hr_documents", sa.Column("media", JSONB(), server_default="[]", nullable=False))


def downgrade() -> None:
    op.drop_column("hr_documents", "media")
