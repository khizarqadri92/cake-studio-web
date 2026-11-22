import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import rate_limit, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models import CustomCakeRequest, User
from app.services import audit, custom_cakes, shop
from app.services.custom_cake_flow import CakeFlowError, check_transition
from app.services.storage import get_storage, UploadError

public = APIRouter(tags=["custom-cakes"])
admin = APIRouter(prefix="/admin/custom-cakes", tags=["custom-cakes-admin"])
c_read, c_write = require_permission("orders.read"), require_permission("orders.write")
_digits = lambda s: re.sub(r"\D", "", s or "")  # noqa: E731


def _wrap(fn, db: Session, *a, **k):
    """Run a service call, mapping its customer-facing errors to HTTP 422 and undoing partial work."""
    try:
        return fn(db, *a, **k)
    except (CakeFlowError, shop.CheckoutError) as e:
        db.rollback()
        raise HTTPException(422, getattr(e, "message", None) or str(e))


# ------------------------------ public ------------------------------
@public.post("/public/uploads/image", dependencies=[Depends(rate_limit("upload", 10, 60))])
async def public_upload(file: UploadFile = File(...)):
    storage = get_storage()
    data = await file.read(storage.max_bytes + 1)
    try:
        return {"url": storage.save(data)}
    except UploadError as e:
        raise HTTPException(422, str(e))


class RequestIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=7, max_length=32)
    email: EmailStr | None = None
    occasion: str = Field(min_length=1, max_length=100)
    flavour: str = Field(min_length=1, max_length=100)
    size_or_weight: str = Field(min_length=1, max_length=100)
    design_notes: str = Field("", max_length=2000)
    message: str | None = Field(None, max_length=200)
    reference_images: list[str] = Field(default_factory=list, max_length=3)
    required_date: date
    required_time: time | None = None
    instructions: str = Field("", max_length=2000)


@public.post("/custom-cakes", status_code=201, dependencies=[Depends(rate_limit("custom_cake", 5, 60))])
def create_request(d: RequestIn, db: Session = Depends(get_db)):
    r = _wrap(custom_cakes.submit, db, name=d.full_name, phone=d.phone, email=d.email.lower() if d.email else None,
              occasion=d.occasion, flavour=d.flavour, size_or_weight=d.size_or_weight, design_notes=d.design_notes,
              message=d.message, images=d.reference_images, required_date=d.required_date, required_time=d.required_time,
              instructions=d.instructions)
    db.commit()
    return {"reference": r.reference, "status": r.status}


def _public_view(r: CustomCakeRequest, cur: str) -> dict:
    return {"reference": r.reference, "status": r.status, "occasion": r.occasion, "flavour": r.flavour,
            "size_or_weight": r.size_or_weight, "required_date": r.required_date.isoformat(),
            "quoted_price": str(r.quoted_price) if r.quoted_price is not None else None, "currency": cur,
            "quote_note": r.quote_note, "quote_valid_until": r.quote_valid_until.isoformat() if r.quote_valid_until else None}


def _find(db: Session, reference: str, phone: str) -> CustomCakeRequest:
    r = db.scalar(select(CustomCakeRequest).where(CustomCakeRequest.reference == reference.strip().upper()))
    if r is None or not _digits(phone) or _digits(phone) != _digits(r.customer_phone):
        raise HTTPException(404, "We couldn't find a request with those details")  # same answer for every mismatch
    return r


@public.get("/custom-cakes/status", dependencies=[Depends(rate_limit("cc_status", 10, 60))])
def request_status(reference: str, phone: str, db: Session = Depends(get_db)):
    return _public_view(_find(db, reference, phone), shop.get_group(db, "general")["currency_code"])


class RespondIn(BaseModel):
    reference: str
    phone: str
    accept: bool


@public.post("/custom-cakes/respond", dependencies=[Depends(rate_limit("cc_respond", 10, 60))])
def respond(d: RespondIn, db: Session = Depends(get_db)):
    r = db.scalar(select(CustomCakeRequest).where(CustomCakeRequest.reference == d.reference.strip().upper()).with_for_update())
    if r is None or not _digits(d.phone) or _digits(d.phone) != _digits(r.customer_phone):
        raise HTTPException(404, "We couldn't find a request with those details")
    _wrap(custom_cakes.customer_respond, db, r, d.accept)
    db.commit()
    return _public_view(r, shop.get_group(db, "general")["currency_code"])


# ------------------------------ admin ------------------------------
def _admin_view(r: CustomCakeRequest) -> dict:
    return {"id": r.id, "reference": r.reference, "status": r.status, "customer": {"name": r.customer_name, "phone": r.customer_phone, "email": r.customer_email},
            "occasion": r.occasion, "flavour": r.flavour, "size_or_weight": r.size_or_weight, "design_notes": r.design_notes,
            "message": r.message, "reference_images": r.reference_images, "required_date": r.required_date.isoformat(),
            "required_time": r.required_time.strftime("%H:%M") if r.required_time else None, "instructions": r.instructions,
            "quoted_price": str(r.quoted_price) if r.quoted_price is not None else None, "quote_note": r.quote_note,
            "quote_valid_until": r.quote_valid_until.isoformat() if r.quote_valid_until else None, "order_id": r.order_id,
            "internal_notes": r.internal_notes, "created_at": r.created_at.isoformat() if r.created_at else None}


def _get(db: Session, rid: int, lock: bool = False) -> CustomCakeRequest:
    q = select(CustomCakeRequest).where(CustomCakeRequest.id == rid)
    r = db.scalar(q.with_for_update() if lock else q)
    if r is None:
        raise HTTPException(404, "Request not found")
    return r


@admin.get("")
def list_requests(status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 25,
                  db: Session = Depends(get_db), _: User = Depends(c_read)):
    page_size = max(1, min(page_size, 100))
    stmt = select(CustomCakeRequest)
    if status:
        stmt = stmt.where(CustomCakeRequest.status == status)
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(CustomCakeRequest.reference.ilike(like), CustomCakeRequest.customer_name.ilike(like), CustomCakeRequest.customer_phone.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(CustomCakeRequest.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "items": [_admin_view(r) for r in rows]}


@admin.get("/{rid}")
def get_request(rid: int, db: Session = Depends(get_db), _: User = Depends(c_read)):
    return _admin_view(_get(db, rid))


class QuoteIn(BaseModel):
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str = Field("", max_length=1000)
    valid_until: date | None = None


@admin.post("/{rid}/quote")
def quote(rid: int, d: QuoteIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    r = _get(db, rid, lock=True)
    _wrap(custom_cakes.set_quote, db, r, a, d.price, d.note, d.valid_until)
    audit.record(db, a, "custom_cake.quote", "custom_cake_requests", r.id, {"price": str(d.price)})
    db.commit()
    return _admin_view(r)


class DecisionIn(BaseModel):
    action: Literal["approve", "decline"]  # staff recording a decision the customer gave by phone/chat


@admin.post("/{rid}/decision")
def decision(rid: int, d: DecisionIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    r = _get(db, rid, lock=True)
    new = "approved" if d.action == "approve" else "declined"
    try:
        check_transition(r.status, new)
    except CakeFlowError as e:
        raise HTTPException(422, str(e))
    if new == "approved" and r.quoted_price is None:
        raise HTTPException(422, "Quote a price before approving")
    r.status = new
    audit.record(db, a, f"custom_cake.{d.action}", "custom_cake_requests", r.id)
    db.commit()
    return _admin_view(r)


class ConvertIn(BaseModel):
    fulfillment: Literal["delivery", "pickup"]
    address: dict | None = None
    day: date
    slot_id: int
    payment_method: str = Field(max_length=30)

    @model_validator(mode="after")
    def _addr(self):
        if self.fulfillment == "delivery":
            a = self.address or {}
            if len(str(a.get("line", "")).strip()) < 3 or not str(a.get("city", "")).strip():
                raise ValueError("Delivery address (line, city) is required")
            self.address = {k: str(a.get(k) or "").strip()[:300] or None for k in ("line", "city", "postal_code", "instructions")}
        else:
            self.address = None
        return self


@admin.post("/{rid}/convert", status_code=201)
def convert(rid: int, d: ConvertIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    r = _get(db, rid, lock=True)
    o = _wrap(custom_cakes.convert_to_order, db, r, a, fulfillment=d.fulfillment, address=d.address, day=d.day,
              slot_id=d.slot_id, payment_code=d.payment_method)
    audit.record(db, a, "custom_cake.convert", "custom_cake_requests", r.id, {"order": o.order_number})
    db.commit()
    return {"order_id": o.id, "order_number": o.order_number, "request": _admin_view(r)}


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@admin.post("/{rid}/notes")
def add_note(rid: int, d: NoteIn, db: Session = Depends(get_db), a: User = Depends(c_write)):
    r = _get(db, rid)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    r.internal_notes = f"{r.internal_notes}\n[{stamp} {a.full_name}] {d.note.strip()}".strip()
    db.commit()
    return _admin_view(r)
