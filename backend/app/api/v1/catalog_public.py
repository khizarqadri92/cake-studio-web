from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Product, ProductCategory
from app.services.catalog import to_spec
from app.services.pricing import PricingError, Selection, from_price, price_line

router = APIRouter(prefix="/public", tags=["catalog-public"])


def _card(p: Product) -> dict:
    spec = to_spec(p)
    in_stock = True
    if p.track_stock:
        in_stock = (sum(v.stock_qty for v in p.variants if v.is_active) if p.product_type == "variable" else p.stock_qty) > 0
    return {
        "id": p.id, "slug": p.slug, "name": p.name, "category_id": p.category_id,
        "image": p.images[0].url if p.images else None,
        "from_price": str(from_price(spec)), "has_options": p.product_type == "variable" or bool(p.option_groups),
        "on_sale": p.sale_price is not None or any(v.sale_price is not None for v in p.variants),
        "is_available": p.is_available, "in_stock": in_stock and p.is_available,
        "is_featured": p.is_featured, "is_bestseller": p.is_bestseller,
    }


def _live():
    return (Product.deleted_at.is_(None), Product.is_available.is_(True))


@router.get("/categories")
def categories(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=30"
    rows = db.scalars(select(ProductCategory).where(ProductCategory.deleted_at.is_(None), ProductCategory.is_active.is_(True))
                      .order_by(ProductCategory.sort_order, ProductCategory.id)).all()
    return [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description,
             "image_url": c.image_url, "parent_id": c.parent_id} for c in rows]


@router.get("/products")
def list_products(
    q: str | None = None, category: str | None = None,
    min_price: Decimal | None = Query(None, ge=0), max_price: Decimal | None = Query(None, ge=0),
    featured: bool | None = None, bestseller: bool | None = None,
    sort: Literal["popular", "price_asc", "price_desc", "latest"] = "latest",
    page: int = 1, page_size: int = 12, db: Session = Depends(get_db),
):
    page, page_size = max(page, 1), max(1, min(page_size, 48))
    stmt = select(Product).where(*_live())
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q.strip()[:80]}%"))
    if category:
        cat = db.scalar(select(ProductCategory).where(ProductCategory.slug == category, ProductCategory.deleted_at.is_(None)))
        ids = [cat.id] if cat else []
        if cat:  # include direct children
            ids += list(db.scalars(select(ProductCategory.id).where(ProductCategory.parent_id == cat.id)))
        stmt = stmt.where(Product.category_id.in_(ids or [-1]))
    price = func.coalesce(Product.sale_price, Product.base_price)
    if min_price is not None:
        stmt = stmt.where(price >= min_price)
    if max_price is not None:
        stmt = stmt.where(price <= max_price)
    if featured is not None:
        stmt = stmt.where(Product.is_featured.is_(featured))
    if bestseller is not None:
        stmt = stmt.where(Product.is_bestseller.is_(bestseller))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"popular": (Product.sales_count.desc(), Product.id.desc()), "price_asc": (price.asc(), Product.id),
             "price_desc": (price.desc(), Product.id), "latest": (Product.id.desc(),)}[sort]
    rows = db.scalars(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_card(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/products/{slug}")
def product_detail(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Product).where(Product.slug == slug, *_live()))
    if p is None:
        raise HTTPException(404, "Product not found")
    cat = db.get(ProductCategory, p.category_id) if p.category_id else None
    return {
        **_card(p), "description": p.description, "product_type": p.product_type,
        "category": {"name": cat.name, "slug": cat.slug} if cat else None,
        "images": [{"url": i.url, "alt": i.alt} for i in p.images],
        "variants": [{"id": v.id, "name": v.name, "kind": v.kind, "price": str(v.price),
                      "sale_price": None if v.sale_price is None else str(v.sale_price),
                      "in_stock": (not p.track_stock) or v.stock_qty > 0} for v in p.variants if v.is_active],
        "option_groups": [{"id": g.id, "name": g.name, "is_required": g.is_required,
                           "choices": [{"id": c.id, "label": c.label, "price_delta": str(c.price_delta)}
                                       for c in g.choices if c.is_active]} for g in p.option_groups],
        "addons": [{"id": a.id, "name": a.name, "price": str(a.price)} for a in p.addons if a.is_active],
        "allows_message": p.allows_message, "message_max_length": p.message_max_length,
        "prep_time_hours": p.prep_time_hours,
        "meta_title": p.meta_title or p.name, "meta_description": p.meta_description,
    }


class QuoteIn(BaseModel):
    variant_id: int | None = None
    choice_ids: list[int] = []
    addon_ids: list[int] = []
    quantity: int = 1
    message: str | None = None


@router.post("/products/{product_id}/price")
def quote(product_id: int, data: QuoteIn, db: Session = Depends(get_db)):
    """Authoritative price for a selection. The storefront shows this; checkout recomputes it."""
    p = db.scalar(select(Product).where(Product.id == product_id, *_live()))
    if p is None:
        raise HTTPException(404, "Product not found")
    try:
        r = price_line(to_spec(p), Selection(**data.model_dump()))
    except PricingError as e:
        raise HTTPException(422, str(e))
    return {"unit_price": str(r.unit_price), "line_total": str(r.line_total), "quantity": r.quantity,
            "breakdown": {"base": str(r.unit_base), "options": str(r.options_total), "addons": str(r.addons_total)}}
