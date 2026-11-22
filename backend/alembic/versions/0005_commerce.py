"""commerce: customers, slots, payment methods, coupons, carts, orders, payments

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

M = sa.Numeric(12, 2)
TZ = sa.DateTime(timezone=True)


def ts():
    return [sa.Column("created_at", TZ, server_default=sa.func.now()), sa.Column("updated_at", TZ, server_default=sa.func.now())]


def fkc(name, target, ondelete="CASCADE", nullable=False, index=False):
    return sa.Column(name, sa.Integer, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def upgrade() -> None:
    op.create_table("customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False, unique=True),
        sa.Column("email", sa.String(255), index=True),
        sa.Column("internal_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("deleted_at", TZ, index=True), *ts())
    op.create_table("delivery_slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("start_time", sa.Time, nullable=False), sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("max_orders", sa.Integer, nullable=False, server_default="5"),
        sa.Column("weekdays", pg.JSONB, nullable=False, server_default="[0,1,2,3,4,5,6]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()), *ts())
    op.create_table("blocked_dates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("day", sa.Date, nullable=False, unique=True),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""))
    op.create_table("payment_methods",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("instructions", sa.Text, nullable=False, server_default=""),
        sa.Column("applies_to", sa.String(10), nullable=False, server_default="both"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"), *ts())
    op.create_table("coupons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("value", M, nullable=False),
        sa.Column("min_order", M), sa.Column("max_discount", M),
        sa.Column("starts_at", TZ), sa.Column("expires_at", TZ),
        sa.Column("usage_limit", sa.Integer), sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("per_customer_limit", sa.Integer),
        sa.Column("first_order_only", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("product_ids", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("category_ids", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", TZ, index=True), *ts(),
        sa.CheckConstraint("value >= 0", name="ck_coupon_value"))
    op.create_table("carts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        fkc("customer_id", "customers.id", "SET NULL", True),
        sa.Column("coupon_code", sa.String(40)), *ts())
    op.create_table("cart_items",
        sa.Column("id", sa.Integer, primary_key=True),
        fkc("cart_id", "carts.id", index=True), fkc("product_id", "products.id"),
        sa.Column("variant_id", sa.Integer),
        sa.Column("choice_ids", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("addon_ids", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("message", sa.String(200)), sa.Column("instructions", sa.String(500)))
    op.create_table("orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_number", sa.String(24), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(64), unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_confirmation", index=True),
        fkc("customer_id", "customers.id", "SET NULL", True, True),
        fkc("assigned_to_id", "users.id", "SET NULL", True),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False, index=True),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("fulfillment", sa.String(10), nullable=False),
        sa.Column("address_line", sa.String(300)), sa.Column("city", sa.String(100)), sa.Column("postal_code", sa.String(20)),
        sa.Column("delivery_instructions", sa.String(500)),
        sa.Column("delivery_date", sa.Date, nullable=False),
        fkc("slot_id", "delivery_slots.id", "SET NULL", True),
        sa.Column("slot_label", sa.String(40), nullable=False),
        sa.Column("subtotal", M, nullable=False), sa.Column("discount", M, nullable=False, server_default="0"),
        sa.Column("delivery_fee", M, nullable=False, server_default="0"), sa.Column("tax", M, nullable=False, server_default="0"),
        sa.Column("total", M, nullable=False),
        sa.Column("coupon_code", sa.String(40)),
        sa.Column("payment_method_code", sa.String(30), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="unpaid"),
        sa.Column("internal_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("customer_notes", sa.Text, nullable=False, server_default=""), *ts())
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])
    op.create_index("ix_orders_slot_day", "orders", ["slot_id", "delivery_date"])
    op.create_table("order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        fkc("order_id", "orders.id", index=True), fkc("product_id", "products.id", "SET NULL", True),
        sa.Column("product_name", sa.String(200), nullable=False), sa.Column("variant_id", sa.Integer),
        sa.Column("variant_name", sa.String(100)),
        sa.Column("options", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("addons", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("message", sa.String(200)), sa.Column("instructions", sa.String(500)),
        sa.Column("unit_price", M, nullable=False), sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("line_total", M, nullable=False), sa.Column("category_id", sa.Integer))
    op.create_table("order_status_history",
        sa.Column("id", sa.Integer, primary_key=True),
        fkc("order_id", "orders.id", index=True),
        sa.Column("from_status", sa.String(30)), sa.Column("to_status", sa.String(30), nullable=False),
        fkc("changed_by_id", "users.id", "SET NULL", True),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", TZ, nullable=False))
    op.create_table("payments",
        sa.Column("id", sa.Integer, primary_key=True),
        fkc("order_id", "orders.id", index=True),
        sa.Column("method_code", sa.String(30), nullable=False), sa.Column("amount", M, nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="pending"),
        sa.Column("reference", sa.String(120)), fkc("recorded_by_id", "users.id", "SET NULL", True),
        sa.Column("gateway_payload", pg.JSONB), *ts())
    op.create_table("coupon_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        fkc("coupon_id", "coupons.id", index=True), fkc("order_id", "orders.id"),
        fkc("customer_id", "customers.id", "SET NULL", True, True),
        sa.Column("discount", M, nullable=False), sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("order_id", name="uq_coupon_usage_order"))


def downgrade() -> None:
    for t in ["coupon_usage", "payments", "order_status_history", "order_items", "orders", "cart_items", "carts",
              "coupons", "payment_methods", "blocked_dates", "delivery_slots", "customers"]:
        op.drop_table(t)
