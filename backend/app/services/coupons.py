"""Coupon rules (pure). Returns the discount amount or raises CouponError with a customer-facing reason."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


class CouponError(ValueError):
    pass


@dataclass(frozen=True)
class CouponSpec:
    code: str
    kind: str  # fixed | percent
    value: Decimal
    is_active: bool = True
    min_order: Decimal | None = None
    max_discount: Decimal | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = None  # total redemptions
    used_count: int = 0
    per_customer_limit: int | None = None
    first_order_only: bool = False
    product_ids: frozenset[int] = field(default_factory=frozenset)  # empty = all products
    category_ids: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CartLine:
    product_id: int
    category_id: int | None
    line_total: Decimal


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def apply_coupon(c: CouponSpec, lines: list[CartLine], now: datetime, *, prior_orders: int | None,
                 customer_uses: int = 0) -> Decimal:
    """`prior_orders` is None for a guest we cannot identify (first-order coupons then need a phone/email match
    resolved by the caller; pass 0 only when verified as a new customer)."""
    if not c.is_active:
        raise CouponError("This coupon is not active")
    if c.starts_at and now < c.starts_at:
        raise CouponError("This coupon is not valid yet")
    if c.expires_at and now > c.expires_at:
        raise CouponError("This coupon has expired")
    if c.usage_limit is not None and c.used_count >= c.usage_limit:
        raise CouponError("This coupon has reached its usage limit")
    if c.per_customer_limit is not None and customer_uses >= c.per_customer_limit:
        raise CouponError("You have already used this coupon the maximum number of times")
    if c.first_order_only and (prior_orders is None or prior_orders > 0):
        raise CouponError("This coupon is for first orders only")

    subtotal = sum((l.line_total for l in lines), Decimal(0))
    if c.min_order is not None and subtotal < c.min_order:
        raise CouponError(f"Minimum order of {c.min_order} required")

    scoped = bool(c.product_ids or c.category_ids)
    eligible = sum(
        (l.line_total for l in lines
         if not scoped or l.product_id in c.product_ids or (l.category_id is not None and l.category_id in c.category_ids)),
        Decimal(0),
    )
    if eligible <= 0:
        raise CouponError("This coupon does not apply to the items in your cart")

    if c.kind == "percent":
        d = eligible * c.value / 100
    elif c.kind == "fixed":
        d = c.value
    else:
        raise CouponError("Invalid coupon")
    if c.max_discount is not None:
        d = min(d, c.max_discount)
    return _q(max(Decimal(0), min(d, eligible)))  # never discount more than the eligible amount
