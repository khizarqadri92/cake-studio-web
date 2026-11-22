import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import optional_account, rate_limit, require_permission
from app.db.session import get_db
from app.models import Order, Product, Review, User
from app.services import audit
from app.services.review_rules import STATUSES, Eligibility, ReviewError, check_new_review, summarize

public = APIRouter(tags=["reviews"])
admin = APIRouter(prefix="/admin/reviews", tags=["reviews-admin"])
r_read, r_write = require_permission("products.read"), require_permission("products.write")
_digits = lambda s: re.sub(r"\D", "", s or "")  # noqa: E731


def _public_row(r: Review) -> dict:
    return {"id": r.id, "name": r.reviewer_name, "rating": r.rating, "comment": r.comment, "at": r.created_at.date().isoformat() if r.created_at else None}


@public.get("/public/products/{slug}/reviews")
def product_reviews(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Product).where(Product.slug == slug, Product.deleted_at.is_(None)))
    if p is None:
        raise HTTPException(404, "Product not found")
    rows = db.scalars(select(Review).where(Review.product_id == p.id, Review.status == "approved").order_by(Review.id.desc())).all()
    return summarize([r.rating for r in rows]) | {"items": [_public_row(r) for r in rows[:30]]}


class ReviewIn(BaseModel):
    product_id: int
    order_number: str = Field(min_length=3, max_length=40)
    phone: str | None = Field(None, max_length=32)  # not needed when logged in as the order's owner
    rating: int
    comment: str = Field("", max_length=3000)


@public.post("/reviews", status_code=201, dependencies=[Depends(rate_limit("review", 5, 60))])
def submit_review(d: ReviewIn, db: Session = Depends(get_db), account=Depends(optional_account)):
    nf = HTTPException(404, "We couldn't find a matching order")  # same answer for every mismatch (no enumeration)
    o = db.scalar(select(Order).where(Order.order_number == d.order_number.strip().upper()))
    if o is None:
        raise nf
    owner = account is not None and (o.account_id == account.id or (account.email_verified_at is not None and (o.customer_email or "").lower() == account.email))
    if not owner and (not _digits(d.phone) or _digits(d.phone) != _digits(o.customer_phone)):
        raise nf
    done = db.scalar(select(func.count()).select_from(Review).where(Review.order_id == o.id, Review.product_id == d.product_id)) or 0
    try:
        comment = check_new_review(rating=d.rating, comment=d.comment, product_id=d.product_id, already_reviewed=done > 0,
                                   order=Eligibility(o.status, frozenset(i.product_id for i in o.items if i.product_id)))
    except ReviewError as e:
        raise HTTPException(422, str(e))
    name = (account.full_name if owner and account else o.customer_name).split()[0][:60]
    db.add(Review(product_id=d.product_id, order_id=o.id, account_id=account.id if owner and account else None, reviewer_name=name, rating=d.rating, comment=comment))
    try:
        db.commit()
    except IntegrityError:  # double-submit race on the unique (order, product)
        db.rollback()
        raise HTTPException(422, "You've already reviewed this product for this order")
    return {"ok": True, "message": "Thank you! Your review will appear once it has been approved."}


# ---- moderation ----
@admin.get("")
def list_reviews(status: str | None = None, page: int = 1, page_size: int = 25, db: Session = Depends(get_db), _: User = Depends(r_read)):
    page_size = max(1, min(page_size, 100))
    stmt = select(Review, Product.name).join(Product, Product.id == Review.product_id)
    if status:
        if status not in STATUSES:
            raise HTTPException(422, "Unknown status")
        stmt = stmt.where(Review.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Review.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [{"id": r.id, "product": pname, "product_id": r.product_id, "order_id": r.order_id, "name": r.reviewer_name,
                                       "rating": r.rating, "comment": r.comment, "status": r.status, "at": r.created_at.isoformat() if r.created_at else None} for r, pname in rows]}


class StatusIn(BaseModel):
    status: str


@admin.put("/{rid}")
def moderate(rid: int, d: StatusIn, db: Session = Depends(get_db), actor: User = Depends(r_write)):
    if d.status not in STATUSES:
        raise HTTPException(422, "Unknown status")
    r = db.get(Review, rid)
    if r is None:
        raise HTTPException(404, "Review not found")
    r.status = d.status
    audit.record(db, actor, "review.moderate", "reviews", rid, {"status": d.status})
    db.commit()
    return {"id": r.id, "status": r.status}


@admin.delete("/{rid}", status_code=204)
def delete_review(rid: int, db: Session = Depends(get_db), actor: User = Depends(r_write)):
    r = db.get(Review, rid)
    if r is None:
        raise HTTPException(404, "Review not found")
    db.delete(r)
    audit.record(db, actor, "review.delete", "reviews", rid)
    db.commit()
