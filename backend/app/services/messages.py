"""Customer notification text (pure). Plain text so it works for email and WhatsApp alike."""
from dataclasses import dataclass
from decimal import Decimal

from app.services.order_flow import STATUS_LABELS


@dataclass(frozen=True)
class OrderView:
    number: str
    customer_name: str
    status: str
    fulfillment: str
    day: str
    slot: str
    total: Decimal
    currency: str
    note: str = ""


def render(event: str, o: OrderView, site_name: str) -> tuple[str, str]:
    """event: order_placed | status_changed -> (subject, body)."""
    first = (o.customer_name.split() or ["there"])[0]
    when = f"{o.day} ({o.slot})"
    where = "pickup" if o.fulfillment == "pickup" else "delivery"
    total = f"{o.currency} {o.total:.2f}"
    if event == "order_placed":
        return (f"{site_name}: we received your order {o.number}",
                f"Hi {first},\n\nThank you for your order {o.number} with {site_name}.\n"
                f"Total: {total}\nRequested {where}: {when}\n\n"
                "We'll confirm it shortly. You can track it any time with your order number and phone number.")
    label = STATUS_LABELS.get(o.status, o.status)
    body = f"Hi {first},\n\nYour order {o.number} is now: {label}.\n"
    if o.status in ("ready_for_pickup", "out_for_delivery", "delivered", "confirmed"):
        body += f"Scheduled {where}: {when}\n"
    if o.note:
        body += f"\nNote from us: {o.note}\n"
    return f"{site_name}: order {o.number} is {label.lower()}", body + f"\nThank you for choosing {site_name}."


def render_custom(event: str, ref: str, name: str, site_name: str, status_url: str, *, price: Decimal | None = None,
                  currency: str = "", valid_until: str | None = None, note: str = "") -> tuple[str, str]:
    first = (name.split() or ["there"])[0]
    if event == "request_received":
        return (f"{site_name}: we received your custom cake request {ref}",
                f"Hi {first},\n\nThanks for your custom cake request {ref}. We'll review it and send you a price quote soon.\n"
                f"You can check its status any time: {status_url}")
    body = f"Hi {first},\n\nYour custom cake request {ref} has been quoted at {currency} {price:.2f}.\n"
    if valid_until:
        body += f"This quote is valid until {valid_until}.\n"
    if note:
        body += f"\nNote from us: {note}\n"
    body += f"\nPlease approve or decline the quote here: {status_url}"
    return f"{site_name}: your custom cake quote ({ref})", body
