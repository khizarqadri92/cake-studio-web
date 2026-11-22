import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import rate_limit
from app.db.session import get_db
from app.models import Order
from app.services.order_flow import STATUS_LABELS

router = APIRouter(prefix="/orders", tags=["orders-public"])
_digits = lambda s: re.sub(r"\D", "", s or "")  # noqa: E731


@router.get("/track", dependencies=[Depends(rate_limit("track", 10, 60))])
def track(order_number: str, phone: str, db: Session = Depends(get_db)):
    """Order number + phone number must both match. Every mismatch returns the same 404 so the endpoint
    cannot be used to discover which order numbers or phone numbers exist."""
    o = db.scalar(select(Order).where(Order.order_number == order_number.strip().upper()))
    if o is None or not _digits(phone) or _digits(phone) != _digits(o.customer_phone):
        raise HTTPException(404, "We couldn't find an order with those details")
    return order_view(o)


def order_view(o: Order) -> dict:
    """Customer-safe order representation (no internal notes, no staff identities)."""
    return {
        "order_number": o.order_number, "status": o.status, "status_label": STATUS_LABELS[o.status],
        "fulfillment": o.fulfillment, "delivery_date": o.delivery_date.isoformat(), "slot": o.slot_label,
        "payment_status": o.payment_status, "customer_note": o.customer_notes,
        "items": [{"name": i.product_name, "detail": " · ".join(filter(None, [i.variant_name, *[x["label"] for x in i.options]])),
                   "quantity": i.quantity, "line_total": str(i.line_total)} for i in o.items],
        "totals": {"subtotal": str(o.subtotal), "discount": str(o.discount), "delivery_fee": str(o.delivery_fee),
                   "tax": str(o.tax), "total": str(o.total)},
        "timeline": [{"status": h.to_status, "label": STATUS_LABELS.get(h.to_status, h.to_status),
                      "at": h.created_at.isoformat(), "note": h.note} for h in o.history],
    }
