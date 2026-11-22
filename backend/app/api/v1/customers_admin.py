from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Customer, Order, User
from app.services import audit, shop

router = APIRouter(prefix="/admin/customers", tags=["customers-admin"])
c_read, c_write = require_permission("customers.read"), require_permission("customers.write")
SALE = Order.status.notin_(("cancelled", "refunded"))


def _live(db: Session, cid: int) -> Customer:
    c = db.get(Customer, cid)
    if c is None or c.deleted_at is not None:
        raise HTTPException(404, "Customer not found")
    return c


def _stats(db: Session, ids: list[int]) -> dict[int, tuple[int, Decimal]]:
    if not ids:
        return {}
    rows = db.execute(select(Order.customer_id, func.count(), func.coalesce(func.sum(case((SALE, Order.total), else_=0)), 0))
                      .where(Order.customer_id.in_(ids)).group_by(Order.customer_id)).all()
    return {r[0]: (r[1], Decimal(r[2])) for r in rows}


def _row(c: Customer, st: dict) -> dict:
    n, spent = st.get(c.id, (0, Decimal(0)))
    return {"id": c.id, "full_name": c.full_name, "phone": c.phone, "email": c.email, "orders": n, "total_spent": str(spent),
            "created_at": c.created_at.isoformat() if c.created_at else None}


@router.get("")
def list_customers(q: str | None = None, page: int = 1, page_size: int = 25, db: Session = Depends(get_db), _: User = Depends(c_read)):
    page_size = max(1, min(page_size, 100))
    stmt = select(Customer).where(Customer.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(Customer.full_name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Customer.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    st = _stats(db, [c.id for c in rows])
    return {"items": [_row(c, st) for c in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{cid}")
def customer_detail(cid: int, db: Session = Depends(get_db), _: User = Depends(c_read)):
    c = _live(db, cid)
    orders = db.scalars(select(Order).where(Order.customer_id == cid).order_by(Order.id.desc()).limit(100)).all()
    return _row(c, _stats(db, [cid])) | {"internal_notes": c.internal_notes, "orders_list": [
        {"id": o.id, "order_number": o.order_number, "status": o.status, "total": str(o.total), "delivery_date": o.delivery_date.isoformat(),
         "created_at": o.created_at.isoformat()} for o in orders]}


class CustomerIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=7, max_length=32)
    email: EmailStr | None = None


@router.put("/{cid}")
def update_customer(cid: int, d: CustomerIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    c = _live(db, cid)
    try:
        phone = shop.normalize_phone(d.phone)
    except shop.CheckoutError as e:
        raise HTTPException(422, e.message)
    c.full_name, c.phone, c.email = d.full_name.strip(), phone, d.email.lower() if d.email else None
    audit.record(db, a, "customer.update", "customers", cid)
    try:  # past orders keep their own contact snapshot; only the profile changes
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another customer already uses that phone number")
    return _row(c, _stats(db, [cid]))


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@router.post("/{cid}/notes")
def add_note(cid: int, d: NoteIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    c = _live(db, cid)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    c.internal_notes = f"{c.internal_notes}\n[{stamp} {a.full_name}] {d.note.strip()}".strip()
    audit.record(db, a, "customer.note", "customers", cid)
    db.commit()
    return {"internal_notes": c.internal_notes}
