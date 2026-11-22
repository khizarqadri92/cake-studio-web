"""customer accounts, addresses, account tokens

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table("customer_accounts",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(32)), sa.Column("email_verified_at", TZ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("last_login_at", TZ),
        sa.Column("deleted_at", TZ, index=True),
        sa.Column("created_at", TZ, server_default=sa.func.now()), sa.Column("updated_at", TZ, server_default=sa.func.now()))
    op.create_table("customer_addresses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("label", sa.String(50), nullable=False, server_default="Home"), sa.Column("line", sa.String(300), nullable=False),
        sa.Column("city", sa.String(100), nullable=False), sa.Column("postal_code", sa.String(20)),
        sa.Column("instructions", sa.String(500)), sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table("account_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(10), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", TZ, nullable=False), sa.Column("used_at", TZ))
    op.alter_column("refresh_tokens", "user_id", existing_type=sa.Integer, nullable=True)
    op.add_column("refresh_tokens", sa.Column("account_id", sa.Integer, sa.ForeignKey("customer_accounts.id", ondelete="CASCADE")))
    op.create_index("ix_refresh_tokens_account_id", "refresh_tokens", ["account_id"])
    op.add_column("orders", sa.Column("account_id", sa.Integer, sa.ForeignKey("customer_accounts.id", ondelete="SET NULL")))
    op.create_index("ix_orders_account_id", "orders", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_account_id", "orders")
    op.drop_column("orders", "account_id")
    op.drop_index("ix_refresh_tokens_account_id", "refresh_tokens")
    op.drop_column("refresh_tokens", "account_id")
    op.execute("DELETE FROM refresh_tokens WHERE user_id IS NULL")
    op.alter_column("refresh_tokens", "user_id", existing_type=sa.Integer, nullable=False)
    for t in ["account_tokens", "customer_addresses", "customer_accounts"]:
        op.drop_table(t)
