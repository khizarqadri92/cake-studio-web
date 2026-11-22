from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

Money = Numeric(12, 2)


class ProductCategory(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(500))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Flavour(Base, TimestampMixin):
    __tablename__ = "flavours"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="ck_product_base_price"),
        CheckConstraint("sale_price IS NULL OR (sale_price >= 0 AND sale_price <= base_price)", name="ck_product_sale_price"),
        Index("ix_products_listing", "is_available", "category_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    product_type: Mapped[str] = mapped_column(String(10), default="simple")  # simple | variable
    # For variable products base_price/sale_price hold the lowest variant price ("from" price).
    base_price: Mapped[Decimal] = mapped_column(Money, default=0)
    sale_price: Mapped[Decimal | None] = mapped_column(Money)
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)
    track_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bestseller: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_message: Mapped[bool] = mapped_column(Boolean, default=False)
    message_max_length: Mapped[int] = mapped_column(Integer, default=40)
    prep_time_hours: Mapped[int] = mapped_column(Integer, default=24)
    sales_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(300))

    images: Mapped[list["ProductImage"]] = relationship(
        cascade="all, delete-orphan", order_by="ProductImage.sort_order", lazy="selectin")
    variants: Mapped[list["ProductVariant"]] = relationship(
        cascade="all, delete-orphan", order_by="ProductVariant.sort_order", lazy="selectin")
    option_groups: Mapped[list["OptionGroup"]] = relationship(
        cascade="all, delete-orphan", order_by="OptionGroup.sort_order", lazy="selectin")
    addons: Mapped[list["ProductAddon"]] = relationship(
        cascade="all, delete-orphan", order_by="ProductAddon.sort_order", lazy="selectin")


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    alt: Mapped[str] = mapped_column(String(200), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ProductVariant(Base):
    """Size / weight axis. Has its own absolute price, SKU and stock (variable products only)."""

    __tablename__ = "product_variants"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_variant_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))  # "1 kg", "6 inch", "Box of 6"
    kind: Mapped[str] = mapped_column(String(10), default="size")  # size | weight
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)
    price: Mapped[Decimal] = mapped_column(Money)
    sale_price: Mapped[Decimal | None] = mapped_column(Money)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class OptionGroup(Base):
    """Flavour, filling, egg/eggless... each choice adds a (possibly zero) price delta."""

    __tablename__ = "product_option_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    choices: Mapped[list["OptionChoice"]] = relationship(
        cascade="all, delete-orphan", order_by="OptionChoice.sort_order", lazy="selectin")


class OptionChoice(Base):
    __tablename__ = "product_option_choices"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("product_option_groups.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    flavour_id: Mapped[int | None] = mapped_column(ForeignKey("flavours.id", ondelete="SET NULL"))
    price_delta: Mapped[Decimal] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ProductAddon(Base):
    __tablename__ = "product_addons"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))  # "Candles", "Greeting card"
    price: Mapped[Decimal] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
