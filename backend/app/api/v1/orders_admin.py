from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import Notification, Order, User
from app.services import audit, invoice, order_ops, shop
from app.services.order_flow import STATUS_LABELS, FlowError, allowed_next

router = APIRouter(prefix="/admin", tags=["orders-admin"])
o_read, o_write = require_permission("orders.read"), require_permission("orders.write")
pay_read, pay_write = require_permission("payments.read"), require_permission("payments.write")


def _order(db: Session, oid: int) -> Order:
    o = db.get(Order, oid)
    if o is None:
        raise HTTPException(404, "Order not found")
    return o


def _flow(fn, *a, **k):
    try:
        return fn(*a, **k)
    except FlowError as e:
        raise HTTPException(422, str(e))


def _summary(o: Order) -> dict:
    return {"id": o.id, "order_number": o.order_number, "status": o.status, "customer_name": o.customer_name,
            "customer_phone": o.customer_phone, "fulfillment": o.fulfillment, "delivery_date": o.delivery_date.isoformat(),
            "slot": o.slot_label, "total": str(o.total), "payment_status": o.payment_status,
            "payment_method": o.payment_method_code, "assigned_to_id": o.assigned_to_id, "created_at": o.created_at.isoformat()}


def _detail(o: Order) -> dict:
    paid = order_ops.paid_amount(o)
    return _summary(o) | {
        "customer_email": o.customer_email, "customer_id": o.customer_id,
        "address": {"line": o.address_line, "city": o.city, "postal_code": o.postal_code, "instructions": o.delivery_instructions},
        "subtotal": str(o.subtotal), "discount": str(o.discount), "delivery_fee": str(o.delivery_fee), "tax": str(o.tax),
        "coupon_code": o.coupon_code, "paid": str(paid), "balance": str(Decimal(o.total) - paid),
        "internal_notes": o.internal_notes, "customer_notes": o.customer_notes,
        "allowed_next": sorted(allowed_next(o.status, o.fulfillment)),
        "items": [{"id": i.id, "name": i.product_name, "variant": i.variant_name, "options": i.options, "addons": i.addons,
                   "message": i.message, "instructions": i.instructions, "quantity": i.quantity,
                   "unit_price": str(i.unit_price), "line_total": str(i.line_total)} for i in o.items],
        "history": [{"from": h.from_status, "to": h.to_status, "by": h.changed_by_id, "note": h.note, "at": h.created_at.isoformat()} for h in o.history],
        "payments": [{"id": p.id, "method": p.method_code, "amount": str(p.amount), "status": p.status,
                      "reference": p.reference, "at": p.created_at.isoformat() if p.created_at else None} for p in o.payments],
    }


@router.get("/orders")
def list_orders(status: str | None = None, q: str | None = None, fulfillment: Literal["delivery", "pickup"] | None = None,
                payment_status: str | None = None, assigned_to: int | None = None,
                date_from: date | None = None, date_to: date | None = None, delivery_on: date | None = None,
                page: int = 1, page_size: int = 20, db: Session = Depends(get_db), _: User = Depends(o_read)):
    page, page_size = max(page, 1), max(1, min(page_size, 100))
    stmt = select(Order)
    if status:
        if status not in STATUS_LABELS:
            raise HTTPException(422, "Unknown status")
        stmt = stmt.where(Order.status == status)
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(Order.order_number.ilike(like), Order.customer_name.ilike(like),
                              Order.customer_phone.ilike(like), Order.customer_email.ilike(like)))
    if fulfillment:
        stmt = stmt.where(Order.fulfillment == fulfillment)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if assigned_to:
        stmt = stmt.where(Order.assigned_to_id == assigned_to)
    if date_from:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        stmt = stmt.where(Order.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    if delivery_on:
        stmt = stmt.where(Order.delivery_date == delivery_on)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Order.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_summary(o) for o in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/orders/{oid}")
def get_order(oid: int, db: Session = Depends(get_db), _: User = Depends(o_read)):
    return _detail(_order(db, oid))


class StatusIn(BaseModel):
    status: str
    note: str = Field("", max_length=500)  # shown to the customer in the timeline and the notification


@router.post("/orders/{oid}/status")
def set_status(oid: int, d: StatusIn, db: Session = Depends(get_db), actor: User = Depends(o_write)):
    o = db.scalar(select(Order).where(Order.id == oid).with_for_update())  # serialise concurrent status changes
    if o is None:
        raise HTTPException(404, "Order not found")
    old = o.status
    _flow(order_ops.change_status, db, o, d.status, actor, d.note)
    audit.record(db, actor, "order.status", "orders", o.id, {"from": old, "to": d.status})
    db.commit()
    return _detail(o)


class AssignIn(BaseModel):
    user_id: int | None


@router.post("/orders/{oid}/assign")
def assign(oid: int, d: AssignIn, db: Session = Depends(get_db), actor: User = Depends(o_write)):
    o = _order(db, oid)
    if d.user_id is not None:
        u = db.get(User, d.user_id)
        if u is None or not u.is_active or u.deleted_at is not None:
            raise HTTPException(422, "User not found or inactive")
    o.assigned_to_id = d.user_id
    audit.record(db, actor, "order.assign", "orders", o.id, {"user_id": d.user_id})
    db.commit()
    return _detail(o)


class NotesIn(BaseModel):
    internal_note: str | None = Field(None, max_length=2000)  # appended, never overwrites history
    customer_note: str | None = Field(None, max_length=2000)  # replaces the note the customer sees when tracking


@router.post("/orders/{oid}/notes")
def notes(oid: int, d: NotesIn, db: Session = Depends(get_db), actor: User = Depends(o_write)):
    o = _order(db, oid)
    if d.internal_note and d.internal_note.strip():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        o.internal_notes = f"{o.internal_notes}\n[{stamp} {actor.full_name}] {d.internal_note.strip()}".strip()
    if d.customer_note is not None:
        o.customer_notes = d.customer_note.strip()
    audit.record(db, actor, "order.notes", "orders", o.id)
    db.commit()
    return _detail(o)


class PaymentIn(BaseModel):
    method: Literal["cod", "bank_transfer", "online", "pay_on_pickup", "cash", "card_terminal"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(None, max_length=120)


@router.post("/orders/{oid}/payments", status_code=201)
def add_payment(oid: int, d: PaymentIn, db: Session = Depends(get_db), actor: User = Depends(pay_write)):
    o = db.scalar(select(Order).where(Order.id == oid).with_for_update())
    if o is None:
        raise HTTPException(404, "Order not found")
    _flow(order_ops.record_payment, o, actor, d.method, d.amount, d.reference)
    audit.record(db, actor, "payment.record", "orders", o.id, {"amount": str(d.amount), "method": d.method})
    db.commit()
    return _detail(o)


class VerifyIn(BaseModel):
    approve: bool
    reference: str | None = Field(None, max_length=120)


@router.post("/orders/{oid}/payments/{pid}/verify")
def verify(oid: int, pid: int, d: VerifyIn, db: Session = Depends(get_db), actor: User = Depends(pay_write)):
    o = db.scalar(select(Order).where(Order.id == oid).with_for_update())
    if o is None:
        raise HTTPException(404, "Order not found")
    _flow(order_ops.verify_payment, o, pid, actor, d.approve, d.reference)
    audit.record(db, actor, "payment.verify", "orders", o.id, {"payment_id": pid, "approved": d.approve})
    db.commit()
    return _detail(o)


class RefundIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(None, max_length=120)


@router.post("/orders/{oid}/refunds", status_code=201)
def refund(oid: int, d: RefundIn, db: Session = Depends(get_db), actor: User = Depends(pay_write)):
    o = db.scalar(select(Order).where(Order.id == oid).with_for_update())
    if o is None:
        raise HTTPException(404, "Order not found")
    _flow(order_ops.record_refund, o, actor, d.amount, d.reference)
    audit.record(db, actor, "payment.refund", "orders", o.id, {"amount": str(d.amount)})
    db.commit()
    return _detail(o)


def _invoice_data(db: Session, o: Order) -> dict:
    g = shop.get_group(db, "general")
    paid = order_ops.paid_amount(o)
    addr = ", ".join(x for x in (o.address_line, o.city, o.postal_code) if x)
    return {
        "site_name": g["site_name"], "address": g["address"], "phone": g["phone"], "email": g["email"],
        "number": o.order_number, "date": o.created_at.date().isoformat() if o.created_at else "",
        "status": STATUS_LABELS[o.status], "payment_status": o.payment_status.replace("_", " "),
        "customer": {"name": o.customer_name, "phone": o.customer_phone, "email": o.customer_email, "address": addr},
        "fulfillment": "Home delivery" if o.fulfillment == "delivery" else "Store pickup",
        "schedule": f"{o.delivery_date.isoformat()} {o.slot_label}", "currency": g["currency_code"],
        "items": [{"name": i.product_name,
                   "detail": " · ".join(filter(None, [i.variant_name, *[x["label"] for x in i.options], *[f"+ {a['name']}" for a in i.addons],
                                                      f"Message: {i.message}" if i.message else None])),
                   "qty": i.quantity, "unit": i.unit_price, "total": i.line_total} for i in o.items],
        "subtotal": o.subtotal, "discount": o.discount, "delivery_fee": o.delivery_fee, "tax": o.tax, "total": o.total,
        "paid": paid, "balance": Decimal(o.total) - paid,
    }


@router.get("/orders/{oid}/invoice", response_class=Response)
def invoice_html(oid: int, db: Session = Depends(get_db), _: User = Depends(o_read)):
    """Printable HTML. Sent with a restrictive CSP because the page contains customer-supplied text."""
    o = _order(db, oid)
    return Response(invoice.render_html(_invoice_data(db, o)), media_type="text/html",
                    headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})


@router.get("/orders/{oid}/invoice.pdf", response_class=Response)
def invoice_pdf(oid: int, db: Session = Depends(get_db), _: User = Depends(o_read)):
    o = _order(db, oid)
    return Response(invoice.render_pdf(_invoice_data(db, o)), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="invoice-{o.order_number}.pdf"'})


@router.get("/staff")
def assignable_staff(db: Session = Depends(get_db), _: User = Depends(o_read)):
    rows = db.scalars(select(User).where(User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.full_name)).all()
    return [{"id": u.id, "name": u.full_name, "roles": [r.name for r in u.roles]} for u in rows]


# ---- staff notification bell ----
@router.get("/notifications")
def staff_notifications(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(Notification).where(Notification.channel == "inapp").order_by(Notification.id.desc()).limit(30)).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.channel == "inapp", Notification.is_read.is_(False)))
    return {"unread": unread, "items": [{"id": n.id, "title": n.subject, "body": n.body, "order_id": n.order_id,
                                         "is_read": n.is_read, "at": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.channel == "inapp", Notification.is_read.is_(False)).values(is_read=True))
    db.commit()
