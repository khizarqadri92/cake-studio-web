"""inventory, suppliers, purchase orders, recipes

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None
TZ = sa.DateTime(timezone=True)
M = sa.Numeric(12, 2)
Q = sa.Numeric(14, 3)


def ts():
    return [sa.Column("created_at", TZ, server_default=sa.func.now()), sa.Column("updated_at", TZ, server_default=sa.func.now())]


def upgrade() -> None:
    op.create_table("suppliers",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(150), nullable=False),
        sa.Column("contact_name", sa.String(150)), sa.Column("phone", sa.String(40)), sa.Column("email", sa.String(255)),
        sa.Column("address", sa.String(300)), sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("deleted_at", TZ, index=True), *ts())
    op.create_table("inventory_items",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(150), nullable=False),
        sa.Column("sku", sa.String(64), unique=True), sa.Column("kind", sa.String(20), nullable=False, server_default="ingredient"),
        sa.Column("unit", sa.String(20), nullable=False, server_default="kg"),
        sa.Column("stock_qty", Q, nullable=False, server_default="0"), sa.Column("low_stock_threshold", Q, nullable=False, server_default="0"),
        sa.Column("cost_per_unit", M, nullable=False, server_default="0"),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", TZ, index=True), *ts())
    op.create_table("inventory_transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("qty_change", Q, nullable=False),
        sa.Column("balance_after", Q, nullable=False), sa.Column("reference", sa.String(60)),
        sa.Column("note", sa.String(300), nullable=False, server_default=""),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TZ, nullable=False))
    op.create_table("purchase_orders",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(12), nullable=False, server_default="ordered"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("total_cost", M, nullable=False, server_default="0"), sa.Column("received_at", TZ), *ts())
    op.create_table("purchase_order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_order_id", sa.Integer, sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", Q, nullable=False), sa.Column("unit_cost", M, nullable=False))
    op.create_table("product_recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("variant_id", sa.Integer, sa.ForeignKey("product_variants.id", ondelete="CASCADE")),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qty_per_unit", sa.Numeric(14, 4), nullable=False),
        sa.UniqueConstraint("product_id", "variant_id", "item_id", name="uq_recipe_line"))
    op.add_column("orders", sa.Column("ingredients_deducted", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("orders", "ingredients_deducted")
    for t in ["product_recipes", "purchase_order_items", "purchase_orders", "inventory_transactions", "inventory_items", "suppliers"]:
        op.drop_table(t)
