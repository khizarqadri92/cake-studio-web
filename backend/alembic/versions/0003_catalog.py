"""catalog: categories, flavours, products, variants, options, add-ons

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

M = sa.Numeric(12, 2)


def ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def fk(col, target, ondelete="CASCADE", nullable=False, index=True):
    return sa.Column(col, sa.Integer, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("image_url", sa.String(500)),
        fk("parent_id", "product_categories.id", "SET NULL", True, False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), index=True),
        *ts(),
    )
    op.create_table(
        "flavours",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *ts(),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("category_id", "product_categories.id", "SET NULL", True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("product_type", sa.String(10), nullable=False, server_default="simple"),
        sa.Column("base_price", M, nullable=False, server_default="0"),
        sa.Column("sale_price", M),
        sa.Column("sku", sa.String(64), unique=True),
        sa.Column("track_stock", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("stock_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer, nullable=False, server_default="5"),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_bestseller", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("allows_message", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("message_max_length", sa.Integer, nullable=False, server_default="40"),
        sa.Column("prep_time_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("sales_count", sa.Integer, nullable=False, server_default="0", index=True),
        sa.Column("meta_title", sa.String(200)),
        sa.Column("meta_description", sa.String(300)),
        sa.Column("deleted_at", sa.DateTime(timezone=True), index=True),
        *ts(),
        sa.CheckConstraint("base_price >= 0", name="ck_product_base_price"),
        sa.CheckConstraint("sale_price IS NULL OR (sale_price >= 0 AND sale_price <= base_price)", name="ck_product_sale_price"),
    )
    op.create_index("ix_products_listing", "products", ["is_available", "category_id"])
    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("product_id", "products.id"),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("alt", sa.String(200), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("product_id", "products.id"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="size"),
        sa.Column("sku", sa.String(64), unique=True),
        sa.Column("price", M, nullable=False),
        sa.Column("sale_price", M),
        sa.Column("stock_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("price >= 0", name="ck_variant_price"),
    )
    op.create_table(
        "product_option_groups",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("product_id", "products.id"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "product_option_choices",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("group_id", "product_option_groups.id"),
        sa.Column("label", sa.String(100), nullable=False),
        fk("flavour_id", "flavours.id", "SET NULL", True, False),
        sa.Column("price_delta", M, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "product_addons",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("product_id", "products.id"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price", M, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    for t in ["product_addons", "product_option_choices", "product_option_groups", "product_variants",
              "product_images", "products", "flavours", "product_categories"]:
        op.drop_table(t)
