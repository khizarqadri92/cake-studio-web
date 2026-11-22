"""product reviews

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table("reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("customer_accounts.id", ondelete="SET NULL")),
        sa.Column("reviewer_name", sa.String(120), nullable=False), sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", TZ, server_default=sa.func.now()), sa.Column("updated_at", TZ, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "product_id", name="uq_review_order_product"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"))


def downgrade() -> None:
    op.drop_table("reviews")
