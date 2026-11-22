"""Pricing engine. Pure functions over plain dataclasses so it is unit-testable without a DB.

unit price = (variant price | product price, sale price wins if set)
           + sum(price_delta of selected option choices)
           + sum(price of selected add-ons)
line total = unit price * quantity
Cart, checkout and custom-cake conversion must all go through `price_line`.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


class PricingError(ValueError):
    pass


@dataclass(frozen=True)
class Choice:
    id: int
    price_delta: Decimal
    is_active: bool = True


@dataclass(frozen=True)
class Group:
    id: int
    name: str
    is_required: bool
    choices: tuple[Choice, ...]


@dataclass(frozen=True)
class Variant:
    id: int
    price: Decimal
    sale_price: Decimal | None = None
    stock_qty: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class Addon:
    id: int
    price: Decimal
    is_active: bool = True


@dataclass(frozen=True)
class ProductSpec:
    id: int
    product_type: str  # simple | variable
    base_price: Decimal
    sale_price: Decimal | None = None
    is_available: bool = True
    track_stock: bool = False
    stock_qty: int = 0
    allows_message: bool = False
    message_max_length: int = 40
    variants: tuple[Variant, ...] = ()
    groups: tuple[Group, ...] = ()
    addons: tuple[Addon, ...] = ()


@dataclass
class Selection:
    variant_id: int | None = None
    choice_ids: list[int] = field(default_factory=list)  # one per group
    addon_ids: list[int] = field(default_factory=list)
    quantity: int = 1
    message: str | None = None


@dataclass
class PricedLine:
    unit_base: Decimal
    options_total: Decimal
    addons_total: Decimal
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    variant_id: int | None
    choice_ids: list[int]
    addon_ids: list[int]
    message: str | None


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def effective(price: Decimal, sale: Decimal | None) -> Decimal:
    return sale if sale is not None and sale < price else price


def price_line(p: ProductSpec, sel: Selection) -> PricedLine:
    if not p.is_available:
        raise PricingError("Product is not available")
    if sel.quantity < 1 or sel.quantity > 100:
        raise PricingError("Quantity must be between 1 and 100")

    # --- base: variant or product ---
    variant_id = None
    stock_left = p.stock_qty if p.track_stock else None
    if p.product_type == "variable":
        active = {v.id: v for v in p.variants if v.is_active}
        if sel.variant_id not in active:
            raise PricingError("A valid size/weight must be selected")
        v = active[sel.variant_id]
        base = effective(v.price, v.sale_price)
        variant_id = v.id
        stock_left = v.stock_qty if p.track_stock else None
    else:
        if sel.variant_id is not None:
            raise PricingError("Product has no variants")
        base = effective(p.base_price, p.sale_price)
    if stock_left is not None and sel.quantity > stock_left:
        raise PricingError(f"Only {max(stock_left, 0)} in stock")

    # --- option groups: at most one choice per group, required groups must be answered ---
    chosen: dict[int, Choice] = {}
    by_choice = {c.id: (g, c) for g in p.groups for c in g.choices}
    for cid in sel.choice_ids:
        if cid not in by_choice:
            raise PricingError(f"Unknown option {cid}")
        g, c = by_choice[cid]
        if not c.is_active:
            raise PricingError("Selected option is no longer available")
        if g.id in chosen:
            raise PricingError(f"Only one choice allowed for '{g.name}'")
        chosen[g.id] = c
    for g in p.groups:
        if g.is_required and g.id not in chosen and any(c.is_active for c in g.choices):
            raise PricingError(f"Please choose an option for '{g.name}'")
    options_total = sum((c.price_delta for c in chosen.values()), Decimal(0))

    # --- add-ons (each at most once) ---
    if len(set(sel.addon_ids)) != len(sel.addon_ids):
        raise PricingError("Duplicate add-on")
    addon_map = {a.id: a for a in p.addons}
    addons_total = Decimal(0)
    for aid in sel.addon_ids:
        a = addon_map.get(aid)
        if a is None or not a.is_active:
            raise PricingError(f"Invalid add-on {aid}")
        addons_total += a.price

    # --- message ---
    msg = (sel.message or "").strip() or None
    if msg:
        if not p.allows_message:
            raise PricingError("This product does not support a message")
        if len(msg) > p.message_max_length:
            raise PricingError(f"Message is limited to {p.message_max_length} characters")

    unit = _q(base + options_total + addons_total)
    if unit < 0:
        raise PricingError("Invalid total")
    return PricedLine(
        unit_base=_q(base), options_total=_q(options_total), addons_total=_q(addons_total),
        unit_price=unit, quantity=sel.quantity, line_total=_q(unit * sel.quantity),
        variant_id=variant_id, choice_ids=[c.id for c in chosen.values()],
        addon_ids=list(sel.addon_ids), message=msg,
    )


def from_price(p: ProductSpec) -> Decimal:
    """Lowest possible base price, for 'From $X' display / listing filters."""
    if p.product_type == "variable":
        prices = [effective(v.price, v.sale_price) for v in p.variants if v.is_active]
        return _q(min(prices)) if prices else _q(p.base_price)
    return _q(effective(p.base_price, p.sale_price))
