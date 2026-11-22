"""Cart pricing and the checkout transaction. Everything monetary is recomputed here from the DB; nothing the
client sends about prices is trusted."""
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (Cart, Coupon, CouponUsage, Customer, DeliverySlot, Order, OrderItem, OrderStatusHistory,
                        Payment, PaymentMethod, Product, ProductVariant, WebsiteSetting, BlockedDate)
from app.services.coupons import CartLine, CouponError, CouponSpec, apply_coupon
from app.services.pricing import PricedLine, PricingError, Selection, price_line
from app.services.catalog import to_spec
from app.services.scheduling import ScheduleError, SlotSpec, validate_choice
from app.services.settings_schema import defaults
from app.services.totals import DeliveryRules, TaxRules, Totals, compute_totals

CANCELLED = ("cancelled", "refunded")


class CheckoutError(Exception):
    """Customer-facing problem (HTTP 422/409 at the API layer)."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.message, self.status = message, status


def get_group(db: Session, group: str) -> dict:
    row = db.scalar(select(WebsiteSetting).where(WebsiteSetting.group == group))
    return {**defaults(group), **(row.value if row else {})}


def store_now(db: Session) -> datetime:
    tz = ZoneInfo(get_group(db, "checkout")["timezone"])
    return datetime.now(tz).replace(tzinfo=None)  # naive store-local time, as scheduling.py expects


def normalize_phone(raw: str) -> str:
    s = re.sub(r"[\s\-().]", "", raw or "")
    plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if not 7 <= len(digits) <= 15:
        raise CheckoutError("Please enter a valid phone number")
    return ("+" if plus else "") + digits


@dataclass
class CartLinePriced:
    item_id: int
    product: Product | None
    priced: PricedLine | None
    error: str | None
    variant_name: str | None = None
    option_labels: list[dict] | None = None
    addon_rows: list[dict] | None = None


def price_cart(db: Session, cart: Cart) -> list[CartLinePriced]:
    out = []
    for it in cart.items:
        p = db.get(Product, it.product_id)
        if p is None or p.deleted_at is not None or not p.is_available:
            out.append(CartLinePriced(it.id, p, None, "This product is no longer available"))
            continue
        try:
            r = price_line(to_spec(p), Selection(it.variant_id, list(it.choice_ids), list(it.addon_ids), it.quantity, it.message))
        except PricingError as e:
            out.append(CartLinePriced(it.id, p, None, str(e)))
            continue
        variant = next((v for v in p.variants if v.id == r.variant_id), None)
        opts = [{"group": g.name, "label": c.label, "delta": str(c.price_delta)}
                for g in p.option_groups for c in g.choices if c.id in r.choice_ids]
        adds = [{"name": a.name, "price": str(a.price)} for a in p.addons if a.id in r.addon_ids]
        out.append(CartLinePriced(it.id, p, r, None, variant.name if variant else None, opts, adds))
    return out


def coupon_spec(c: Coupon) -> CouponSpec:
    return CouponSpec(
        code=c.code, kind=c.kind, value=Decimal(c.value), is_active=c.is_active and c.deleted_at is None,
        min_order=None if c.min_order is None else Decimal(c.min_order),
        max_discount=None if c.max_discount is None else Decimal(c.max_discount),
        starts_at=c.starts_at, expires_at=c.expires_at, usage_limit=c.usage_limit, used_count=c.used_count,
        per_customer_limit=c.per_customer_limit, first_order_only=c.first_order_only,
        product_ids=frozenset(c.product_ids or []), category_ids=frozenset(c.category_ids or []))


def find_coupon(db: Session, code: str, lock: bool = False) -> Coupon | None:
    q = select(Coupon).where(Coupon.code == code.strip().upper(), Coupon.deleted_at.is_(None))
    return db.scalar(q.with_for_update() if lock else q)


def rules(db: Session) -> tuple[DeliveryRules, TaxRules]:
    ck, gen = get_group(db, "checkout"), get_group(db, "general")
    free = ck["free_delivery_over"]
    return (DeliveryRules(Decimal(str(ck["delivery_fee"])), None if free is None else Decimal(str(free))),
            TaxRules(gen["tax_enabled"], Decimal(str(gen["tax_rate_percent"])), gen["tax_inclusive"]))


def cart_summary(db: Session, cart: Cart, fulfillment: str, *, customer_prior_orders: int | None = None,
                 customer_uses: int = 0) -> dict:
    lines = price_cart(db, cart)
    ok = [l for l in lines if l.priced]
    subtotal = sum((l.priced.line_total for l in ok), Decimal(0))
    discount, coupon_error = Decimal(0), None
    if cart.coupon_code and ok:
        c = find_coupon(db, cart.coupon_code)
        if c is None:
            coupon_error = "Coupon not found"
        else:
            try:
                discount = apply_coupon(
                    coupon_spec(c), [CartLine(l.product.id, l.product.category_id, l.priced.line_total) for l in ok],
                    datetime.now(timezone.utc), prior_orders=customer_prior_orders, customer_uses=customer_uses)
            except CouponError as e:
                coupon_error = str(e)
    d, t = rules(db)
    totals = compute_totals(subtotal, discount, fulfillment, d, t) if ok else None
    return {"lines": lines, "totals": totals, "coupon_error": coupon_error}


def _booked(db: Session, slot_id: int, day: date) -> int:
    return db.scalar(select(func.count()).select_from(Order).where(
        Order.slot_id == slot_id, Order.delivery_date == day, Order.status.notin_(CANCELLED))) or 0


def new_order_number(db: Session, day: date) -> str:
    for _ in range(20):
        n = f"CS-{day:%y%m%d}-{secrets.token_hex(2).upper()}"
        if db.scalar(select(Order.id).where(Order.order_number == n)) is None:
            return n
    raise CheckoutError("Could not allocate an order number, please retry", 503)


def place_order(db: Session, *, cart_token: str, name: str, phone: str, email: str | None, fulfillment: str,
                address: dict | None, day: date, slot_id: int, payment_code: str, customer_notes: str = "",
                idempotency_key: str | None = None, account_id: int | None = None) -> Order:
    if idempotency_key:
        existing = db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing:
            return existing  # same request retried: return the original order, never create a second

    cart = db.scalar(select(Cart).where(Cart.token == cart_token))
    if cart is None or not cart.items:
        raise CheckoutError("Your cart is empty")
    phone = normalize_phone(phone)

    priced = price_cart(db, cart)
    bad = [l.error for l in priced if l.error]
    if bad:
        raise CheckoutError("Please review your cart: " + "; ".join(dict.fromkeys(bad)))

    pm = db.scalar(select(PaymentMethod).where(PaymentMethod.code == payment_code, PaymentMethod.is_active.is_(True)))
    if pm is None or pm.applies_to not in ("both", fulfillment):
        raise CheckoutError("That payment method is not available for this order")

    ck = get_group(db, "checkout")
    now = store_now(db)
    prep = max(l.product.prep_time_hours for l in priced)

    # Lock the slot row so concurrent checkouts cannot both take the last place.
    slot = db.scalar(select(DeliverySlot).where(DeliverySlot.id == slot_id).with_for_update())
    if slot is None:
        raise CheckoutError("Please choose a valid time slot")
    blocked = {b.day for b in db.scalars(select(BlockedDate))}
    try:
        validate_choice(
            slot.id, day=day, now=now, prep_hours=prep, min_prep_hours=ck["min_prep_hours"],
            max_days_ahead=ck["max_days_ahead"], blocked=blocked, booked={slot.id: _booked(db, slot.id, day)},
            slots=[SlotSpec(slot.id, slot.start_time, slot.end_time, slot.max_orders, frozenset(slot.weekdays), slot.is_active)])
    except ScheduleError as e:
        raise CheckoutError(str(e), 409)
    slot_label = f"{slot.start_time:%H:%M}-{slot.end_time:%H:%M}"

    customer = db.scalar(select(Customer).where(Customer.phone == phone))
    if customer is None:
        customer = Customer(full_name=name.strip(), phone=phone, email=email)
        db.add(customer)
        db.flush()
    elif email and not customer.email:
        customer.email = email
    prior = db.scalar(select(func.count()).select_from(Order).where(
        Order.customer_id == customer.id, Order.status.notin_(CANCELLED))) or 0

    subtotal = sum((l.priced.line_total for l in priced), Decimal(0))
    discount, coupon = Decimal(0), None
    if cart.coupon_code:
        coupon = find_coupon(db, cart.coupon_code, lock=True)
        if coupon is None:
            raise CheckoutError("Coupon not found")
        uses = db.scalar(select(func.count()).select_from(CouponUsage).where(
            CouponUsage.coupon_id == coupon.id, CouponUsage.customer_id == customer.id)) or 0
        try:
            discount = apply_coupon(
                coupon_spec(coupon), [CartLine(l.product.id, l.product.category_id, l.priced.line_total) for l in priced],
                datetime.now(timezone.utc), prior_orders=prior, customer_uses=uses)
        except CouponError as e:
            raise CheckoutError(str(e))
    d, t = rules(db)
    totals: Totals = compute_totals(subtotal, discount, fulfillment, d, t)

    # Stock: conditional UPDATEs are atomic, so two buyers cannot both take the last unit.
    for l in priced:
        p, r = l.product, l.priced
        if not p.track_stock:
            continue
        if r.variant_id is not None:
            ok = db.execute(update(ProductVariant).where(ProductVariant.id == r.variant_id, ProductVariant.stock_qty >= r.quantity)
                            .values(stock_qty=ProductVariant.stock_qty - r.quantity)).rowcount
        else:
            ok = 1
        ok2 = db.execute(update(Product).where(Product.id == p.id, Product.stock_qty >= r.quantity)
                         .values(stock_qty=Product.stock_qty - r.quantity)).rowcount
        if not ok or not ok2:
            raise CheckoutError(f"Sorry, '{p.name}' just sold out", 409)

    cat_ids = {l.product.id: l.product.category_id for l in priced}
    order = Order(
        order_number=new_order_number(db, now.date()), idempotency_key=idempotency_key, customer_id=customer.id, account_id=account_id,
        customer_name=name.strip(), customer_phone=phone, customer_email=email, fulfillment=fulfillment,
        address_line=(address or {}).get("line"), city=(address or {}).get("city"),
        postal_code=(address or {}).get("postal_code"), delivery_instructions=(address or {}).get("instructions"),
        delivery_date=day, slot_id=slot.id, slot_label=slot_label,
        subtotal=totals.subtotal, discount=totals.discount, delivery_fee=totals.delivery_fee, tax=totals.tax,
        total=totals.total, coupon_code=coupon.code if coupon else None, payment_method_code=pm.code,
        customer_notes=customer_notes or "")
    ci = {i.id: i for i in cart.items}
    for l in priced:
        r = l.priced
        order.items.append(OrderItem(
            product_id=l.product.id, product_name=l.product.name, variant_id=r.variant_id, variant_name=l.variant_name,
            options=l.option_labels, addons=l.addon_rows, message=r.message, instructions=ci[l.item_id].instructions,
            unit_price=r.unit_price, quantity=r.quantity, line_total=r.line_total, category_id=cat_ids[l.product.id]))
    order.history.append(OrderStatusHistory(from_status=None, to_status="pending_confirmation", note="Order placed",
                                            created_at=datetime.now(timezone.utc)))
    order.payments.append(Payment(method_code=pm.code, amount=totals.total, status="pending"))
    db.add(order)
    db.flush()
    if coupon:
        won = db.execute(update(Coupon).where(Coupon.id == coupon.id, (Coupon.usage_limit.is_(None)) | (Coupon.used_count < Coupon.usage_limit))
                         .values(used_count=Coupon.used_count + 1)).rowcount
        if not won:
            raise CheckoutError("This coupon has reached its usage limit")
        db.add(CouponUsage(coupon_id=coupon.id, order_id=order.id, customer_id=customer.id, discount=totals.discount,
                           created_at=datetime.now(timezone.utc)))
    db.delete(cart)
    from app.services import notify  # local import: notify imports this module

    notify.enqueue_for_order(db, order, "order_placed")
    db.commit()
    return order
