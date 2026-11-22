"""DB-level order operations shared by the admin API: status changes with side effects, payments, refunds."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models import Coupon, CouponUsage, Order, OrderStatusHistory, Payment, Product, ProductVariant, User
from app.services import inventory_ops, notify, shop
from app.services.order_flow import FlowError, check_refund, check_transition, net_paid, payment_status


def _pairs(o: Order) -> list[tuple[Decimal, str]]:
    return [(Decimal(p.amount), p.status) for p in o.payments]


def recalc_payment_status(o: Order) -> None:
    o.payment_status = payment_status(Decimal(o.total), _pairs(o))


def paid_amount(o: Order) -> Decimal:
    return net_paid(_pairs(o))


def _restore_stock_and_coupon(db: Session, o: Order) -> None:
    for it in o.items:
        if it.product_id is None:
            continue
        p = db.get(Product, it.product_id)
        if p is None or not p.track_stock:
            continue
        if it.variant_id is not None:
            db.execute(update(ProductVariant).where(ProductVariant.id == it.variant_id)
                       .values(stock_qty=ProductVariant.stock_qty + it.quantity))
        db.execute(update(Product).where(Product.id == p.id).values(stock_qty=Product.stock_qty + it.quantity))
    if o.coupon_code:
        removed = db.execute(delete(CouponUsage).where(CouponUsage.order_id == o.id)).rowcount
        if removed:  # the redemption no longer counts toward limits
            db.execute(update(Coupon).where(Coupon.code == o.coupon_code, Coupon.used_count > 0)
                       .values(used_count=Coupon.used_count - 1))


def change_status(db: Session, o: Order, new: str, actor: User, note: str = "") -> None:
    check_transition(o.status, new, o.fulfillment)
    if new == "refunded" and paid_amount(o) > 0:
        raise FlowError("Record a refund for the money collected before marking the order refunded")
    old = o.status
    o.status = new
    o.history.append(OrderStatusHistory(from_status=old, to_status=new, changed_by_id=actor.id, note=note[:500],
                                        created_at=datetime.now(timezone.utc)))
    deduct_on = shop.get_group(db, "inventory")["deduct_on"]
    if new == deduct_on:
        inventory_ops.deduct_for_order(db, o, actor.id)
    if new == "cancelled":
        inventory_ops.restore_for_order(db, o, actor.id)
        _restore_stock_and_coupon(db, o)
    elif new == "delivered":
        for it in o.items:
            if it.product_id:
                db.execute(update(Product).where(Product.id == it.product_id).values(sales_count=Product.sales_count + it.quantity))
    db.flush()
    notify.enqueue_for_order(db, o, "status_changed", note)


def record_payment(o: Order, actor: User, method: str, amount: Decimal, reference: str | None) -> Payment:
    if amount <= 0:
        raise FlowError("Payment amount must be positive")
    if o.status in ("cancelled", "refunded"):
        raise FlowError("Cannot record a payment on a cancelled or refunded order")
    if paid_amount(o) + amount > Decimal(o.total):
        raise FlowError("Payment would exceed the order total")
    p = Payment(method_code=method, amount=amount, status="verified", reference=reference, recorded_by_id=actor.id)
    o.payments.append(p)
    recalc_payment_status(o)
    return p


def verify_payment(o: Order, payment_id: int, actor: User, ok: bool, reference: str | None) -> Payment:
    p = next((x for x in o.payments if x.id == payment_id), None)
    if p is None:
        raise FlowError("Payment not found")
    if p.status != "pending":
        raise FlowError("Only pending payments can be verified or rejected")
    if ok and paid_amount(o) + Decimal(p.amount) > Decimal(o.total):
        raise FlowError("Payment would exceed the order total")
    p.status = "verified" if ok else "failed"
    p.recorded_by_id = actor.id
    if reference:
        p.reference = reference
    recalc_payment_status(o)
    return p


def record_refund(o: Order, actor: User, amount: Decimal, reference: str | None) -> Payment:
    check_refund(amount, _pairs(o))
    method = next((p.method_code for p in o.payments if p.status == "verified" and p.amount > 0), o.payment_method_code)
    r = Payment(method_code=method, amount=-amount, status="verified", reference=reference, recorded_by_id=actor.id)
    o.payments.append(r)
    recalc_payment_status(o)
    return r
