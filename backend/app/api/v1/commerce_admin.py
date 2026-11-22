from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import BlockedDate, Coupon, DeliverySlot, PaymentMethod, User
from app.services import audit

router = APIRouter(prefix="/admin", tags=["commerce-admin"])
cfg_read, cfg_write = require_permission("settings.read"), require_permission("settings.write")
cp_read, cp_write = require_permission("coupons.read"), require_permission("coupons.write")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Conflicts with an existing record")


def _get(db, model, id_):
    o = db.get(model, id_)
    if o is None or getattr(o, "deleted_at", None) is not None:
        raise HTTPException(404, "Not found")
    return o


# ---- delivery slots ----
class SlotIn(BaseModel):
    start_time: time
    end_time: time
    max_orders: int = Field(5, ge=1, le=1000)
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    is_active: bool = True

    @model_validator(mode="after")
    def _v(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if not self.weekdays or any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("weekdays must be 0 (Mon) to 6 (Sun)")
        self.weekdays = sorted(set(self.weekdays))
        return self


class SlotOut(ORM, SlotIn):
    id: int


@router.get("/delivery-slots", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db), _: User = Depends(cfg_read)):
    return list(db.scalars(select(DeliverySlot).order_by(DeliverySlot.start_time)))


@router.post("/delivery-slots", response_model=SlotOut, status_code=201)
def create_slot(d: SlotIn, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    s = DeliverySlot(**d.model_dump())
    db.add(s)
    db.flush()
    audit.record(db, a, "slot.create", "delivery_slots", s.id)
    _commit(db)
    return s


@router.put("/delivery-slots/{sid}", response_model=SlotOut)
def update_slot(sid: int, d: SlotIn, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    s = _get(db, DeliverySlot, sid)
    for k, v in d.model_dump().items():
        setattr(s, k, v)
    audit.record(db, a, "slot.update", "delivery_slots", sid)
    _commit(db)
    return s


@router.delete("/delivery-slots/{sid}", status_code=204)
def delete_slot(sid: int, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    db.delete(_get(db, DeliverySlot, sid))  # orders keep their slot_label snapshot (FK is SET NULL)
    audit.record(db, a, "slot.delete", "delivery_slots", sid)
    db.commit()


# ---- blocked dates ----
class BlockedIn(BaseModel):
    day: date
    reason: str = Field("", max_length=200)


class BlockedOut(ORM, BlockedIn):
    id: int


@router.get("/blocked-dates", response_model=list[BlockedOut])
def list_blocked(db: Session = Depends(get_db), _: User = Depends(cfg_read)):
    return list(db.scalars(select(BlockedDate).order_by(BlockedDate.day)))


@router.post("/blocked-dates", response_model=BlockedOut, status_code=201)
def block_date(d: BlockedIn, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    b = BlockedDate(**d.model_dump())
    db.add(b)
    _commit(db)
    return b


@router.delete("/blocked-dates/{bid}", status_code=204)
def unblock(bid: int, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    db.delete(_get(db, BlockedDate, bid))
    db.commit()


# ---- payment methods ----
class PMIn(BaseModel):
    code: Literal["cod", "bank_transfer", "online", "pay_on_pickup"]
    name: str = Field(min_length=1, max_length=100)
    instructions: str = Field("", max_length=2000)
    applies_to: Literal["delivery", "pickup", "both"] = "both"
    is_active: bool = True


class PMOut(ORM, PMIn):
    id: int
    sort_order: int


@router.get("/payment-methods", response_model=list[PMOut])
def list_pm(db: Session = Depends(get_db), _: User = Depends(cfg_read)):
    return list(db.scalars(select(PaymentMethod).order_by(PaymentMethod.sort_order)))


@router.put("/payment-methods/{pid}", response_model=PMOut)
def update_pm(pid: int, d: PMIn, db: Session = Depends(get_db), a: User = Depends(cfg_write)):
    m = _get(db, PaymentMethod, pid)
    m.name, m.instructions, m.applies_to, m.is_active = d.name, d.instructions, d.applies_to, d.is_active
    audit.record(db, a, "payment_method.update", "payment_methods", pid)
    db.commit()
    return m


# ---- coupons ----
class CouponIn(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["fixed", "percent"]
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    min_order: Decimal | None = Field(None, ge=0)
    max_discount: Decimal | None = Field(None, gt=0)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = Field(None, ge=1)
    per_customer_limit: int | None = Field(None, ge=1)
    first_order_only: bool = False
    product_ids: list[int] = []
    category_ids: list[int] = []
    is_active: bool = True

    @model_validator(mode="after")
    def _v(self):
        if self.kind == "percent" and self.value > 100:
            raise ValueError("percentage cannot exceed 100")
        if self.starts_at and self.expires_at and self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be after starts_at")
        self.code = self.code.upper()
        return self


class CouponOut(ORM, CouponIn):
    id: int
    used_count: int


@router.get("/coupons", response_model=list[CouponOut])
def list_coupons(db: Session = Depends(get_db), _: User = Depends(cp_read)):
    return list(db.scalars(select(Coupon).where(Coupon.deleted_at.is_(None)).order_by(Coupon.id.desc())))


@router.post("/coupons", response_model=CouponOut, status_code=201)
def create_coupon(d: CouponIn, db: Session = Depends(get_db), a: User = Depends(cp_write)):
    c = Coupon(**d.model_dump())
    db.add(c)
    db.flush()
    audit.record(db, a, "coupon.create", "coupons", c.id)
    _commit(db)
    return c


@router.put("/coupons/{cid}", response_model=CouponOut)
def update_coupon(cid: int, d: CouponIn, db: Session = Depends(get_db), a: User = Depends(cp_write)):
    c = _get(db, Coupon, cid)
    for k, v in d.model_dump().items():
        setattr(c, k, v)
    audit.record(db, a, "coupon.update", "coupons", cid)
    _commit(db)
    return c


@router.delete("/coupons/{cid}", status_code=204)
def delete_coupon(cid: int, db: Session = Depends(get_db), a: User = Depends(cp_write)):
    from datetime import timezone

    c = _get(db, Coupon, cid)
    c.deleted_at, c.is_active = datetime.now(timezone.utc), False
    c.code = f"{c.code}--DEL{c.id}"[:40]
    audit.record(db, a, "coupon.delete", "coupons", cid)
    db.commit()
