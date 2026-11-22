"""custom cake requests

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table("custom_cake_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reference", sa.String(24), nullable=False, unique=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id", ondelete="SET NULL"), index=True),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False, index=True),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("occasion", sa.String(100), nullable=False), sa.Column("flavour", sa.String(100), nullable=False),
        sa.Column("size_or_weight", sa.String(100), nullable=False),
        sa.Column("design_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("message", sa.String(200)),
        sa.Column("reference_images", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("required_date", sa.Date, nullable=False), sa.Column("required_time", sa.Time),
        sa.Column("instructions", sa.Text, nullable=False, server_default=""),
        sa.Column("quoted_price", sa.Numeric(12, 2)), sa.Column("quote_note", sa.Text, nullable=False, server_default=""),
        sa.Column("quote_valid_until", sa.Date), sa.Column("quoted_at", TZ),
        sa.Column("quoted_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("internal_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", TZ, server_default=sa.func.now()), sa.Column("updated_at", TZ, server_default=sa.func.now()))
    op.create_index("ix_ccr_status_created", "custom_cake_requests", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("custom_cake_requests")
