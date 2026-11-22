from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String,
                        Text, Time, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

Money = Numeric(12, 2)

ORDER_STATUSES = ("pending_confirmation", "confirmed", "in_preparation", "ready_for_pickup",
                  "out_for_delivery", "delivered", "cancelled", "refunded")


class Customer(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(32), unique=True)  # normalised digits (+ optional leading +)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    internal_notes: Mapped[str] = mapped_column(Text, default="")


class DeliverySlot(Base, TimestampMixin):
    __tablename__ = "delivery_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    max_orders: Mapped[int] = mapped_column(Integer, default=5)
    weekdays: Mapped[list] = mapped_column(JSONB, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlockedDate(Base):
    __tablename__ = "blocked_dates"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    reason: Mapped[str] = mapped_column(String(200), default="")


class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # cod | bank_transfer | online | pay_on_pickup
    name: Mapped[str] = mapped_column(String(100))
    instructions: Mapped[str] = mapped_column(Text, default="")  # e.g. bank account details shown at checkout
    applies_to: Mapped[str] = mapped_column(String(10), default="both")  # delivery | pickup | both
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Coupon(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "coupons"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # stored upper-case
    kind: Mapped[str] = mapped_column(String(10))  # fixed | percent
    value: Mapped[Decimal] = mapped_column(Money)
    min_order: Mapped[Decimal | None] = mapped_column(Money)
    max_discount: Mapped[Decimal | None] = mapped_column(Money)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer)
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False)
    product_ids: Mapped[list] = mapped_column(JSONB, default=list)
    category_ids: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("value >= 0", name="ck_coupon_value"),)


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)  # unguessable; held by the browser
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    items: Mapped[list["CartItem"]] = relationship(cascade="all, delete-orphan", order_by="CartItem.id", lazy="selectin")


class CartItem(Base):
    __tablename__ = "cart_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[int | None] = mapped_column(Integer)
    choice_ids: Mapped[list] = mapped_column(JSONB, default=list)
    addon_ids: Mapped[list] = mapped_column(JSONB, default=list)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    message: Mapped[str | None] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(String(500))


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_status_created", "status", "created_at"),
                      Index("ix_orders_slot_day", "slot_id", "delivery_date"))
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(24), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_confirmation", index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("customer_accounts.id", ondelete="SET NULL"), index=True)
    # snapshots: order history must not change when a customer or product is edited later
    customer_name: Mapped[str] = mapped_column(String(150))
    customer_phone: Mapped[str] = mapped_column(String(32), index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255))
    fulfillment: Mapped[str] = mapped_column(String(10))  # delivery | pickup
    address_line: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    delivery_instructions: Mapped[str | None] = mapped_column(String(500))
    delivery_date: Mapped[date] = mapped_column(Date)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_slots.id", ondelete="SET NULL"))
    slot_label: Mapped[str] = mapped_column(String(40))
    subtotal: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(Money, default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Money, default=0)
    tax: Mapped[Decimal] = mapped_column(Money, default=0)
    total: Mapped[Decimal] = mapped_column(Money)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    payment_method_code: Mapped[str] = mapped_column(String(30))
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")  # unpaid|partially_paid|paid|refunded
    ingredients_deducted: Mapped[bool] = mapped_column(Boolean, default=False)  # BOM stock already taken for this order
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    customer_notes: Mapped[str] = mapped_column(Text, default="")  # visible to the customer
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", order_by="OrderItem.id", lazy="selectin")
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        cascade="all, delete-orphan", order_by="OrderStatusHistory.id", lazy="selectin")
    payments: Mapped[list["Payment"]] = relationship(cascade="all, delete-orphan", order_by="Payment.id", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    product_name: Mapped[str] = mapped_column(String(200))
    variant_id: Mapped[int | None] = mapped_column(Integer)  # to restore variant stock on cancellation
    variant_name: Mapped[str | None] = mapped_column(String(100))
    options: Mapped[list] = mapped_column(JSONB, default=list)  # [{"group": "Flavour", "label": "Chocolate", "delta": "0.00"}]
    addons: Mapped[list] = mapped_column(JSONB, default=list)  # [{"name": "Candles", "price": "3.00"}]
    message: Mapped[str | None] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(String(500))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[Decimal] = mapped_column(Money)
    category_id: Mapped[int | None] = mapped_column(Integer)  # for category-wise reports


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    method_code: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Money)  # negative for refunds
    status: Mapped[str] = mapped_column(String(15), default="pending")  # pending|verified|failed|refunded
    reference: Mapped[str | None] = mapped_column(String(120))
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    gateway_payload: Mapped[dict | None] = mapped_column(JSONB)


class CouponUsage(Base):
    __tablename__ = "coupon_usage"
    __table_args__ = (UniqueConstraint("order_id", name="uq_coupon_usage_order"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    discount: Mapped[Decimal] = mapped_column(Money)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    """Outbox for customer email/WhatsApp (processed by the worker) and in-app staff alerts."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_due", "status", "next_attempt_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(10))  # email | whatsapp | inapp
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)  # inapp only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Supplier(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    contact_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str] = mapped_column(Text, default="")


class InventoryItem(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="ingredient")  # raw_material | ingredient | packaging
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    low_stock_threshold: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    cost_per_unit: Mapped[Decimal] = mapped_column(Money, default=0)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # purchase | usage | adjustment | waste | order_deduction | order_return
    qty_change: Mapped[Decimal] = mapped_column(Numeric(14, 3))  # signed
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reference: Mapped[str | None] = mapped_column(String(60))  # e.g. "order:CS-..." or "po:PO-..."
    note: Mapped[str] = mapped_column(String(300), default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(12), default="ordered")  # ordered | received | cancelled
    notes: Mapped[str] = mapped_column(Text, default="")
    total_cost: Mapped[Decimal] = mapped_column(Money, default=0)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["PurchaseOrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal] = mapped_column(Money)


class ProductRecipe(Base):
    """Ingredient quantity needed per ONE unit sold. variant_id NULL = default recipe for the product."""

    __tablename__ = "product_recipes"
    __table_args__ = (UniqueConstraint("product_id", "variant_id", "item_id", name="uq_recipe_line"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"))
    qty_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 4))


class CustomCakeRequest(Base, TimestampMixin):
    __tablename__ = "custom_cake_requests"
    __table_args__ = (Index("ix_ccr_status_created", "status", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="new")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    customer_name: Mapped[str] = mapped_column(String(150))
    customer_phone: Mapped[str] = mapped_column(String(32), index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255))
    occasion: Mapped[str] = mapped_column(String(100))
    flavour: Mapped[str] = mapped_column(String(100))
    size_or_weight: Mapped[str] = mapped_column(String(100))
    design_notes: Mapped[str] = mapped_column(Text, default="")
    message: Mapped[str | None] = mapped_column(String(200))
    reference_images: Mapped[list] = mapped_column(JSONB, default=list)
    required_date: Mapped[date] = mapped_column(Date)
    required_time: Mapped[time | None] = mapped_column(Time)
    instructions: Mapped[str] = mapped_column(Text, default="")
    quoted_price: Mapped[Decimal | None] = mapped_column(Money)
    quote_note: Mapped[str] = mapped_column(Text, default="")
    quote_valid_until: Mapped[date | None] = mapped_column(Date)
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quoted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    internal_notes: Mapped[str] = mapped_column(Text, default="")


class CustomerAccount(Base, TimestampMixin, SoftDeleteMixin):
    """Login identity for shoppers. Deliberately NOT linked to guest `customers` rows by phone number:
    a phone number proves nothing, so history is linked by account_id and by verified e-mail only."""

    __tablename__ = "customer_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(32))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    addresses: Mapped[list["CustomerAddress"]] = relationship(cascade="all, delete-orphan", order_by="CustomerAddress.id", lazy="selectin")


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(50), default="Home")
    line: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    instructions: Mapped[str | None] = mapped_column(String(500))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class AccountToken(Base):
    __tablename__ = "account_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # verify | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_review_order_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("customer_accounts.id", ondelete="SET NULL"))
    reviewer_name: Mapped[str] = mapped_column(String(120))  # first name only is shown publicly
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
