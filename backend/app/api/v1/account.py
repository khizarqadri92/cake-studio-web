from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_account
from app.db.session import get_db
from app.models import CustomerAccount, CustomerAddress, Order
from app.services import shop
from app.api.v1.orders_public import order_view

router = APIRouter(prefix="/account", tags=["account"])
MAX_ADDRESSES = 10


def _owned(a: CustomerAccount):
    """Orders placed while logged in, plus orders placed with the account's e-mail once that e-mail is verified."""
    cond = Order.account_id == a.id
    if a.email_verified_at is not None:
        cond = or_(cond, func.lower(Order.customer_email) == a.email)
    return cond


def _addr(x: CustomerAddress) -> dict:
    return {"id": x.id, "label": x.label, "line": x.line, "city": x.city, "postal_code": x.postal_code,
            "instructions": x.instructions, "is_default": x.is_default}


@router.get("/me")
def me(a: CustomerAccount = Depends(get_current_account)):
    return {"id": a.id, "email": a.email, "full_name": a.full_name, "phone": a.phone, "email_verified": a.email_verified_at is not None,
            "addresses": [_addr(x) for x in a.addresses]}


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(None, max_length=32)


@router.put("/me")
def update_me(d: ProfileIn, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    try:
        a.phone = shop.normalize_phone(d.phone) if d.phone else None
    except shop.CheckoutError as e:
        raise HTTPException(422, e.message)
    a.full_name = d.full_name.strip()
    db.commit()
    return me(a)


class AddressIn(BaseModel):
    label: str = Field("Home", max_length=50)
    line: str = Field(min_length=3, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    instructions: str | None = Field(None, max_length=500)
    is_default: bool = False


def _set_default(a: CustomerAccount, keep: CustomerAddress) -> None:
    for x in a.addresses:
        x.is_default = x is keep


@router.post("/addresses", status_code=201)
def add_address(d: AddressIn, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    if len(a.addresses) >= MAX_ADDRESSES:
        raise HTTPException(422, f"You can save up to {MAX_ADDRESSES} addresses")
    x = CustomerAddress(**d.model_dump(exclude={"is_default"}))
    a.addresses.append(x)
    db.flush()
    if d.is_default or len(a.addresses) == 1:
        _set_default(a, x)
    db.commit()
    return _addr(x)


def _mine(a: CustomerAccount, aid: int) -> CustomerAddress:
    x = next((x for x in a.addresses if x.id == aid), None)
    if x is None:
        raise HTTPException(404, "Address not found")  # also the answer for someone else's address id
    return x


@router.put("/addresses/{aid}")
def update_address(aid: int, d: AddressIn, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    x = _mine(a, aid)
    for k, v in d.model_dump(exclude={"is_default"}).items():
        setattr(x, k, v)
    if d.is_default:
        _set_default(a, x)
    db.commit()
    return _addr(x)


@router.delete("/addresses/{aid}", status_code=204)
def delete_address(aid: int, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    x = _mine(a, aid)
    was_default = x.is_default
    a.addresses.remove(x)
    if was_default and a.addresses:
        a.addresses[0].is_default = True
    db.commit()


@router.get("/orders")
def my_orders(page: int = 1, page_size: int = 20, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    page_size = max(1, min(page_size, 50))
    stmt = select(Order).where(_owned(a))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Order.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [{"order_number": o.order_number, "status": o.status, "total": str(o.total),
                                       "delivery_date": o.delivery_date.isoformat(), "created_at": o.created_at.isoformat()} for o in rows]}


@router.get("/orders/{order_number}")
def my_order(order_number: str, a: CustomerAccount = Depends(get_current_account), db: Session = Depends(get_db)):
    o = db.scalar(select(Order).where(Order.order_number == order_number.upper(), _owned(a)))
    if o is None:
        raise HTTPException(404, "Order not found")
    return order_view(o)
