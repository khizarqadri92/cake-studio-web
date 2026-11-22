"""DB operations for the custom cake quotation workflow."""
import re
import secrets
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import (BlockedDate, Customer, CustomCakeRequest, DeliverySlot, Order, OrderItem, OrderStatusHistory,
                        Payment, PaymentMethod)
from app.services import notify, shop
from app.core.config import get_settings
from app.services.custom_cake_flow import (CakeFlowError, check_transition, is_quote_expired, validate_images,
                                           validate_quote, validate_required_date)
from app.services.scheduling import ScheduleError, SlotSpec, validate_choice
from app.services.totals import compute_totals


def _upsert_customer(db, name: str, phone: str, email: str | None) -> Customer:
    c = db.scalar(select(Customer).where(Customer.phone == phone))
    if c is None:
        c = Customer(full_name=name.strip(), phone=phone, email=email)
        db.add(c)
        db.flush()
    elif email and not c.email:
        c.email = email
    return c


def submit(db, *, name, phone, email, occasion, flavour, size_or_weight, design_notes, message, images, required_date: date,
           required_time: time | None, instructions) -> CustomCakeRequest:
    phone = shop.normalize_phone(phone)  # raises CheckoutError
    ck = shop.get_group(db, "checkout")
    validate_required_date(required_date, shop.store_now(db).date(), ck["custom_cake_min_days"])
    validate_images(images, public_base=get_settings().s3_public_base_url or None)
    customer = _upsert_customer(db, name, phone, email)
    for _ in range(20):
        ref = f"CC-{shop.store_now(db):%y%m%d}-{secrets.token_hex(2).upper()}"
        if db.scalar(select(CustomCakeRequest.id).where(CustomCakeRequest.reference == ref)) is None:
            break
    else:
        raise CakeFlowError("Could not allocate a reference, please retry")
    r = CustomCakeRequest(reference=ref, customer_id=customer.id, customer_name=name.strip(), customer_phone=phone, customer_email=email,
                          occasion=occasion.strip(), flavour=flavour.strip(), size_or_weight=size_or_weight.strip(),
                          design_notes=design_notes or "", message=(message or "").strip() or None, reference_images=images,
                          required_date=required_date, required_time=required_time, instructions=instructions or "")
    db.add(r)
    db.flush()
    notify.enqueue_custom_cake(db, r, "request_received")
    return r


def set_quote(db, r: CustomCakeRequest, actor, price: Decimal, note: str, valid_until: date | None) -> None:
    check_transition(r.status, "quoted")
    validate_quote(price, valid_until, shop.store_now(db).date(), r.required_date)
    r.status, r.quoted_price, r.quote_note, r.quote_valid_until = "quoted", price, note.strip(), valid_until
    r.quoted_at, r.quoted_by_id = datetime.now(timezone.utc), actor.id
    notify.enqueue_custom_cake(db, r, "quote_ready")


def customer_respond(db, r: CustomCakeRequest, accept: bool) -> None:
    if r.status != "quoted":
        raise CakeFlowError("There is no open quote to respond to")
    if accept and is_quote_expired(r.quote_valid_until, shop.store_now(db).date()):
        check_transition("quoted", "expired")
        r.status = "expired"
        db.commit()  # persist the expiry, then tell the customer
        raise CakeFlowError("This quote has expired. Please contact us for an updated quote.")
    new = "approved" if accept else "declined"
    check_transition(r.status, new)
    r.status = new


def convert_to_order(db, r: CustomCakeRequest, actor, *, fulfillment: str, address: dict | None, day: date, slot_id: int,
                     payment_code: str) -> Order:
    if r.status != "approved":
        raise CakeFlowError("Only an approved quotation can be converted to an order")
    pm = db.scalar(select(PaymentMethod).where(PaymentMethod.code == payment_code, PaymentMethod.is_active.is_(True)))
    if pm is None or pm.applies_to not in ("both", fulfillment):
        raise CakeFlowError("That payment method is not available for this order")
    ck, now = shop.get_group(db, "checkout"), shop.store_now(db)
    slot = db.scalar(select(DeliverySlot).where(DeliverySlot.id == slot_id).with_for_update())
    if slot is None:
        raise CakeFlowError("Please choose a valid time slot")
    try:  # the quotation already allowed for preparation time, so only capacity/blocked-day/weekday rules apply here
        validate_choice(slot.id, day=day, now=now, prep_hours=0, min_prep_hours=0, max_days_ahead=ck["max_days_ahead"],
                        blocked={b.day for b in db.scalars(select(BlockedDate))}, booked={slot.id: shop._booked(db, slot.id, day)},
                        slots=[SlotSpec(slot.id, slot.start_time, slot.end_time, slot.max_orders, frozenset(slot.weekdays), slot.is_active)])
    except ScheduleError as e:
        raise CakeFlowError(str(e))
    d, t = shop.rules(db)
    totals = compute_totals(Decimal(r.quoted_price), Decimal(0), fulfillment, d, t)
    o = Order(order_number=shop.new_order_number(db, now.date()), customer_id=r.customer_id, customer_name=r.customer_name,
              customer_phone=r.customer_phone, customer_email=r.customer_email, fulfillment=fulfillment,
              address_line=(address or {}).get("line"), city=(address or {}).get("city"), postal_code=(address or {}).get("postal_code"),
              delivery_instructions=(address or {}).get("instructions"), delivery_date=day, slot_id=slot.id,
              slot_label=f"{slot.start_time:%H:%M}-{slot.end_time:%H:%M}", subtotal=totals.subtotal, discount=totals.discount,
              delivery_fee=totals.delivery_fee, tax=totals.tax, total=totals.total, payment_method_code=pm.code,
              customer_notes=f"Custom cake {r.reference}")
    o.items.append(OrderItem(product_id=None, product_name=f"Custom cake ({r.occasion})", variant_name=r.size_or_weight,
                             options=[{"group": "Flavour", "label": r.flavour, "delta": "0.00"}], addons=[], message=r.message,
                             instructions=(r.design_notes or "")[:500] or None, unit_price=r.quoted_price, quantity=1,
                             line_total=r.quoted_price))
    o.history.append(OrderStatusHistory(from_status=None, to_status="pending_confirmation", changed_by_id=actor.id,
                                        note=f"Converted from custom cake request {r.reference}", created_at=datetime.now(timezone.utc)))
    o.payments.append(Payment(method_code=pm.code, amount=totals.total, status="pending"))
    db.add(o)
    db.flush()
    r.status, r.order_id = "converted", o.id
    notify.enqueue_for_order(db, o, "order_placed")
    return o
