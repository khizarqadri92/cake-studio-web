"""cms: settings, homepage, navigation, pages, banners, testimonials

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "website_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("group", sa.String(50), nullable=False, unique=True),
        sa.Column("value", postgresql.JSONB, nullable=False, server_default="{}"),
        *ts(),
    )
    op.create_table(
        "homepage_sections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("content", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_visible", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *ts(),
    )
    op.create_index("ix_homepage_sections_sort_order", "homepage_sections", ["sort_order"])
    op.create_table(
        "navigation_menus",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location", sa.String(20), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("navigation_menus.id", ondelete="CASCADE")),
        sa.Column("open_in_new_tab", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *ts(),
    )
    op.create_index("ix_nav_location_order", "navigation_menus", ["location", "sort_order"])
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body_html", sa.Text, nullable=False, server_default=""),
        sa.Column("meta_title", sa.String(200)),
        sa.Column("meta_description", sa.String(300)),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *ts(),
    )
    op.create_index("ix_pages_deleted_at", "pages", ["deleted_at"])
    op.create_table(
        "banners",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(300), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(500)),
        sa.Column("link_url", sa.String(500)),
        sa.Column("placement", sa.String(30), nullable=False, server_default="home_promo"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *ts(),
    )
    op.create_table(
        "testimonials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False, server_default="5"),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *ts(),
    )


def downgrade() -> None:
    for t in ["testimonials", "banners", "pages", "navigation_menus", "homepage_sections", "website_settings"]:
        op.drop_table(t)
