import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import optional_account, rate_limit
from app.db.session import get_db
from app.models import BlockedDate, Cart, CartItem, DeliverySlot, Order, PaymentMethod, Product
from app.services import shop
from app.services.pricing import PricingError, Selection, price_line
from app.services.catalog import to_spec
from app.services.scheduling import SlotSpec, available_slots

router = APIRouter(tags=["cart-checkout"])
MAX_ITEMS = 50


def _cart(db: Session, token: str) -> Cart:
    c = db.scalar(select(Cart).where(Cart.token == token))
    if c is None:
        raise HTTPException(404, "Cart not found")
    return c


def _render(db: Session, cart: Cart, fulfillment: str) -> dict:
    s = shop.cart_summary(db, cart, fulfillment)
    t = s["totals"]
    items = []
    for l in s["lines"]:
        row = {"id": l.item_id, "product_id": l.product.id if l.product else None,
               "name": l.product.name if l.product else "Unavailable product", "error": l.error}
        if l.priced:
            p = l.priced
            row |= {"slug": l.product.slug, "image": l.product.images[0].url if l.product.images else None,
                    "variant": l.variant_name, "options": [f"{o['group']}: {o['label']}" for o in l.option_labels],
                    "addons": [a["name"] for a in l.addon_rows], "message": p.message, "quantity": p.quantity,
                    "unit_price": str(p.unit_price), "line_total": str(p.line_total)}
        items.append(row)
    return {"token": cart.token, "items": items, "coupon_code": cart.coupon_code, "coupon_error": s["coupon_error"],
            "totals": None if t is None else {k: str(v) for k, v in vars(t).items()}}


@router.post("/cart", status_code=201, dependencies=[Depends(rate_limit("cart", 30, 60))])
def create_cart(db: Session = Depends(get_db)):
    cart = Cart(token=secrets.token_urlsafe(32))
    db.add(cart)
    db.commit()
    return {"token": cart.token}


@router.get("/cart/{token}")
def get_cart(token: str, fulfillment: Literal["delivery", "pickup"] = "delivery", db: Session = Depends(get_db)):
    return _render(db, _cart(db, token), fulfillment)


class ItemIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    choice_ids: list[int] = Field(default_factory=list, max_length=20)
    addon_ids: list[int] = Field(default_factory=list, max_length=20)
    quantity: int = Field(1, ge=1, le=100)
    message: str | None = Field(None, max_length=200)
    instructions: str | None = Field(None, max_length=500)


@router.post("/cart/{token}/items", status_code=201)
def add_item(token: str, data: ItemIn, db: Session = Depends(get_db)):
    cart = _cart(db, token)
    if len(cart.items) >= MAX_ITEMS:
        raise HTTPException(422, "Cart is full")
    p = db.scalar(select(Product).where(Product.id == data.product_id, Product.deleted_at.is_(None)))
    if p is None:
        raise HTTPException(404, "Product not found")
    try:  # validate now so the customer gets immediate feedback; checkout re-validates anyway
        price_line(to_spec(p), Selection(data.variant_id, data.choice_ids, data.addon_ids, data.quantity, data.message))
    except PricingError as e:
        raise HTTPException(422, str(e))
    cart.items.append(CartItem(**data.model_dump()))
    db.commit()
    return _render(db, cart, "delivery")


class QtyIn(BaseModel):
    quantity: int = Field(ge=1, le=100)


@router.patch("/cart/{token}/items/{item_id}")
def set_quantity(token: str, item_id: int, data: QtyIn, db: Session = Depends(get_db)):
    cart = _cart(db, token)
    it = next((i for i in cart.items if i.id == item_id), None)
    if it is None:
        raise HTTPException(404, "Item not found")
    it.quantity = data.quantity
    db.commit()
    return _render(db, cart, "delivery")


@router.delete("/cart/{token}/items/{item_id}")
def remove_item(token: str, item_id: int, db: Session = Depends(get_db)):
    cart = _cart(db, token)
    it = next((i for i in cart.items if i.id == item_id), None)
    if it is None:
        raise HTTPException(404, "Item not found")
    cart.items.remove(it)
    db.commit()
    return _render(db, cart, "delivery")


class CouponIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


@router.put("/cart/{token}/coupon")
def apply_cart_coupon(token: str, data: CouponIn, db: Session = Depends(get_db)):
    cart = _cart(db, token)
    code = data.code.strip().upper()
    cart.coupon_code = code
    db.flush()
    out = _render(db, cart, "delivery")
    if out["coupon_error"]:  # don't keep a coupon that can't be applied
        db.rollback()
        raise HTTPException(422, out["coupon_error"])
    db.commit()
    return out


@router.delete("/cart/{token}/coupon")
def remove_cart_coupon(token: str, db: Session = Depends(get_db)):
    cart = _cart(db, token)
    cart.coupon_code = None
    db.commit()
    return _render(db, cart, "delivery")


# ---- scheduling & payment options ----
@router.get("/public/delivery/slots")
def slots(day: date, cart_token: str | None = None, db: Session = Depends(get_db)):
    ck = shop.get_group(db, "checkout")
    prep = 0
    if cart_token:
        cart = db.scalar(select(Cart).where(Cart.token == cart_token))
        if cart and cart.items:
            prep = max((db.get(Product, i.product_id).prep_time_hours for i in cart.items if db.get(Product, i.product_id)), default=0)
    specs = [SlotSpec(s.id, s.start_time, s.end_time, s.max_orders, frozenset(s.weekdays), s.is_active)
             for s in db.scalars(select(DeliverySlot))]
    booked = {s.id: shop._booked(db, s.id, day) for s in specs}
    out = available_slots(day, shop.store_now(db), prep, specs, {b.day for b in db.scalars(select(BlockedDate))}, booked,
                          min_prep_hours=ck["min_prep_hours"], max_days_ahead=ck["max_days_ahead"])
    return [{"slot_id": a.slot_id, "start": a.start.strftime("%H:%M"), "end": a.end.strftime("%H:%M"), "remaining": a.remaining} for a in out]


@router.get("/public/payment-methods")
def payment_methods(fulfillment: Literal["delivery", "pickup"] = "delivery", db: Session = Depends(get_db)):
    rows = db.scalars(select(PaymentMethod).where(PaymentMethod.is_active.is_(True)).order_by(PaymentMethod.sort_order)).all()
    return [{"code": m.code, "name": m.name, "instructions": m.instructions} for m in rows if m.applies_to in ("both", fulfillment)]


# ---- checkout ----
class AddressIn(BaseModel):
    line: str = Field(min_length=3, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    instructions: str | None = Field(None, max_length=500)


class CheckoutIn(BaseModel):
    cart_token: str
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=7, max_length=32)
    email: EmailStr | None = None
    fulfillment: Literal["delivery", "pickup"]
    address: AddressIn | None = None
    day: date
    slot_id: int
    payment_method: str = Field(max_length=30)
    notes: str = Field("", max_length=500)

    @model_validator(mode="after")
    def _addr(self):
        if self.fulfillment == "delivery" and self.address is None:
            raise ValueError("A delivery address is required for home delivery")
        return self


@router.post("/checkout", status_code=201, dependencies=[Depends(rate_limit("checkout", 10, 60))])
def checkout(data: CheckoutIn, idempotency_key: str | None = Header(None, max_length=64), db: Session = Depends(get_db),
             account=Depends(optional_account)):
    try:
        o = shop.place_order(
            db, cart_token=data.cart_token, name=data.full_name, phone=data.phone,
            email=data.email.lower() if data.email else None, fulfillment=data.fulfillment,
            address=data.address.model_dump() if data.address else None, day=data.day, slot_id=data.slot_id,
            payment_code=data.payment_method, customer_notes=data.notes, idempotency_key=idempotency_key,
            account_id=account.id if account else None)
    except shop.CheckoutError as e:
        db.rollback()  # undo partial work (stock, customer, locks)
        raise HTTPException(e.status, e.message)
    except IntegrityError:
        # Concurrent retry with the same idempotency key lost the race on the unique constraint:
        # return the order the winner created. Anything else is a real conflict.
        db.rollback()
        o = db.scalar(select(Order).where(Order.idempotency_key == idempotency_key)) if idempotency_key else None
        if o is None:
            raise HTTPException(409, "Could not place the order, please try again")
    pm = db.scalar(select(PaymentMethod).where(PaymentMethod.code == o.payment_method_code))
    return {"order_number": o.order_number, "status": o.status, "total": str(o.total), "payment_method": o.payment_method_code,
            "payment_instructions": pm.instructions if pm else "", "delivery_date": o.delivery_date.isoformat(), "slot": o.slot_label}
