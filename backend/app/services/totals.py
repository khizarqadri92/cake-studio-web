"""Order totals (pure): subtotal - discount + delivery (+ tax if tax-exclusive)."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
_q = lambda v: Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)  # noqa: E731


@dataclass(frozen=True)
class DeliveryRules:
    fee: Decimal = Decimal(0)
    free_over: Decimal | None = None  # subtotal-after-discount at/above which delivery is free


@dataclass(frozen=True)
class TaxRules:
    enabled: bool = False
    rate_percent: Decimal = Decimal(0)
    inclusive: bool = True


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    tax: Decimal
    total: Decimal


def compute_totals(subtotal: Decimal, discount: Decimal, fulfillment: str, delivery: DeliveryRules, tax: TaxRules) -> Totals:
    if fulfillment not in ("delivery", "pickup"):
        raise ValueError("fulfillment must be delivery or pickup")
    subtotal, discount = _q(subtotal), _q(min(discount, subtotal))
    net = subtotal - discount
    fee = Decimal(0)
    if fulfillment == "delivery" and not (delivery.free_over is not None and net >= delivery.free_over):
        fee = _q(delivery.fee)
    tax_amt = Decimal(0)
    if tax.enabled and tax.rate_percent > 0:
        base = net + fee  # tax applies to goods and delivery
        tax_amt = _q(base * tax.rate_percent / (100 + tax.rate_percent)) if tax.inclusive else _q(base * tax.rate_percent / 100)
    total = net + fee + (0 if tax.inclusive else tax_amt)
    return Totals(subtotal, discount, fee, tax_amt, _q(total))
