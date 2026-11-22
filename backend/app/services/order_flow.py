"""Order lifecycle rules (pure)."""
from decimal import Decimal

STATUS_LABELS = {
    "pending_confirmation": "Pending confirmation", "confirmed": "Confirmed", "in_preparation": "In preparation",
    "ready_for_pickup": "Ready for pickup", "out_for_delivery": "Out for delivery", "delivered": "Delivered",
    "cancelled": "Cancelled", "refunded": "Refunded",
}
_BASE = {
    "pending_confirmation": {"confirmed", "cancelled"},
    "confirmed": {"in_preparation", "cancelled"},
    "in_preparation": {"ready_for_pickup", "out_for_delivery", "cancelled"},
    "ready_for_pickup": {"delivered", "cancelled"},
    "out_for_delivery": {"delivered", "cancelled"},
    "delivered": {"refunded"},
    "cancelled": {"refunded"},
    "refunded": set(),
}
TERMINAL = {"delivered", "cancelled", "refunded"}


class FlowError(ValueError):
    pass


def allowed_next(status: str, fulfillment: str) -> set[str]:
    nxt = set(_BASE.get(status, set()))
    # pickup orders are never "out for delivery"; delivery orders are never "ready for pickup"
    nxt.discard("out_for_delivery" if fulfillment == "pickup" else "ready_for_pickup")
    return nxt


def check_transition(status: str, new: str, fulfillment: str) -> None:
    if new not in STATUS_LABELS:
        raise FlowError(f"Unknown status '{new}'")
    if new not in allowed_next(status, fulfillment):
        raise FlowError(f"Cannot change an order from '{STATUS_LABELS.get(status, status)}' to '{STATUS_LABELS[new]}'")


def net_paid(payments: list[tuple[Decimal, str]]) -> Decimal:
    """payments = [(amount, status)]. Only verified rows count; refunds are negative amounts."""
    return sum((a for a, s in payments if s == "verified"), Decimal(0))


def payment_status(total: Decimal, payments: list[tuple[Decimal, str]]) -> str:
    verified = [a for a, s in payments if s == "verified"]
    net = sum(verified, Decimal(0))
    if any(a < 0 for a in verified) and net <= 0:
        return "refunded"
    if net >= total and total > 0:
        return "paid"
    if net > 0:
        return "partially_paid"
    return "unpaid"


def check_refund(amount: Decimal, payments: list[tuple[Decimal, str]]) -> None:
    if amount <= 0:
        raise FlowError("Refund amount must be positive")
    if amount > net_paid(payments):
        raise FlowError("Refund cannot exceed the amount paid")
