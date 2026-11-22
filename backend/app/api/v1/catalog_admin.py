from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (Flavour, OptionChoice, OptionGroup, Product, ProductAddon, ProductCategory,
                        ProductImage, ProductVariant, User)
from app.services import audit
from app.services.pricing import effective
from app.services.storage import get_storage, UploadError
from app.services.text import slugify, unique_slug

router = APIRouter(prefix="/admin", tags=["catalog-admin"])
cat_read, cat_write = require_permission("categories.read"), require_permission("categories.write")
prod_read, prod_write = require_permission("products.read"), require_permission("products.write")

Price = Field(ge=0, max_digits=12, decimal_places=2)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReorderIn(BaseModel):
    ids: list[int]


def _reorder(db: Session, model, ids: list[int]) -> None:
    rows = {r.id: r for r in db.scalars(select(model).where(model.id.in_(ids)))}
    if set(rows) != set(ids) or len(ids) != len(set(ids)):
        raise HTTPException(422, "ids must be unique and all exist")
    for pos, i in enumerate(ids):
        rows[i].sort_order = pos


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Conflicts with an existing record (duplicate name, slug or SKU?)")


# ---------------- categories ----------------
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    description: str = ""
    image_url: str | None = None
    parent_id: int | None = None
    is_active: bool = True


class CategoryOut(ORM):
    id: int
    name: str
    slug: str
    description: str
    image_url: str | None
    parent_id: int | None
    is_active: bool
    sort_order: int


def _live_category(db: Session, id_: int) -> ProductCategory:
    c = db.get(ProductCategory, id_)
    if c is None or c.deleted_at is not None:
        raise HTTPException(404, "Category not found")
    return c


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(cat_read)):
    return list(db.scalars(select(ProductCategory).where(ProductCategory.deleted_at.is_(None))
                           .order_by(ProductCategory.sort_order, ProductCategory.id)))


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: Session = Depends(get_db), actor: User = Depends(cat_write)):
    slug = data.slug or unique_slug(slugify(data.name), lambda s: db.scalar(select(ProductCategory.id).where(ProductCategory.slug == s)) is not None)
    last = db.scalar(select(func.max(ProductCategory.sort_order))) or 0
    c = ProductCategory(**{**data.model_dump(exclude={"slug"}), "slug": slug}, sort_order=last + 1)
    if data.parent_id is not None:
        _live_category(db, data.parent_id)
    db.add(c)
    db.flush()
    audit.record(db, actor, "category.create", "product_categories", c.id)
    _commit(db)
    return c


@router.put("/categories/reorder", response_model=list[CategoryOut])
def reorder_categories(data: ReorderIn, db: Session = Depends(get_db), actor: User = Depends(cat_write)):
    _reorder(db, ProductCategory, data.ids)
    audit.record(db, actor, "category.reorder", "product_categories", None, {"ids": data.ids})
    db.commit()
    return list_categories(db, actor)


@router.put("/categories/{cid}", response_model=CategoryOut)
def update_category(cid: int, data: CategoryIn, db: Session = Depends(get_db), actor: User = Depends(cat_write)):
    c = _live_category(db, cid)
    if data.parent_id == cid:
        raise HTTPException(422, "A category cannot be its own parent")
    for k, v in data.model_dump(exclude={"slug"}).items():
        setattr(c, k, v)
    if data.slug:
        c.slug = data.slug
    audit.record(db, actor, "category.update", "product_categories", c.id)
    _commit(db)
    return c


@router.delete("/categories/{cid}", status_code=204)
def delete_category(cid: int, db: Session = Depends(get_db), actor: User = Depends(cat_write)):
    c = _live_category(db, cid)
    c.deleted_at = datetime.now(timezone.utc)
    c.is_active = False
    c.slug = f"{c.slug}--deleted-{c.id}"
    for p in db.scalars(select(Product).where(Product.category_id == cid)):
        p.category_id = None  # products stay; admin can recategorise
    audit.record(db, actor, "category.delete", "product_categories", c.id)
    db.commit()


# ---------------- flavours ----------------
class FlavourIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_active: bool = True


class FlavourOut(ORM, FlavourIn):
    id: int
    sort_order: int


@router.get("/flavours", response_model=list[FlavourOut])
def list_flavours(db: Session = Depends(get_db), _: User = Depends(prod_read)):
    return list(db.scalars(select(Flavour).order_by(Flavour.sort_order, Flavour.name)))


@router.post("/flavours", response_model=FlavourOut, status_code=201)
def create_flavour(data: FlavourIn, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    f = Flavour(**data.model_dump())
    db.add(f)
    _commit(db)
    return f


@router.put("/flavours/{fid}", response_model=FlavourOut)
def update_flavour(fid: int, data: FlavourIn, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    f = db.get(Flavour, fid)
    if not f:
        raise HTTPException(404, "Flavour not found")
    f.name, f.is_active = data.name, data.is_active
    _commit(db)
    return f


@router.delete("/flavours/{fid}", status_code=204)
def delete_flavour(fid: int, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    f = db.get(Flavour, fid)
    if not f:
        raise HTTPException(404, "Flavour not found")
    db.delete(f)
    db.commit()


# ---------------- products ----------------
class ImageIn(ORM):
    url: str = Field(min_length=1, max_length=500, pattern=r"^(/media/|https://)")
    alt: str = Field("", max_length=200)


class VariantIn(ORM):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["size", "weight"] = "size"
    sku: str | None = Field(None, max_length=64)
    price: Decimal = Price
    sale_price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    stock_qty: int = Field(0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def _sale(self):
        if self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("sale_price cannot exceed price")
        return self


class ChoiceIn(ORM):
    id: int | None = None
    label: str = Field(min_length=1, max_length=100)
    flavour_id: int | None = None
    price_delta: Decimal = Field(Decimal(0), max_digits=12, decimal_places=2)
    is_active: bool = True


class GroupIn(ORM):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    is_required: bool = True
    choices: list[ChoiceIn] = Field(min_length=1)


class AddonIn(ORM):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Price
    is_active: bool = True


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=220)
    description: str = ""
    category_id: int | None = None
    product_type: Literal["simple", "variable"] = "simple"
    base_price: Decimal = Field(Decimal(0), ge=0, max_digits=12, decimal_places=2)
    sale_price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    sku: str | None = Field(None, max_length=64)
    track_stock: bool = False
    stock_qty: int = Field(0, ge=0)
    low_stock_threshold: int = Field(5, ge=0)
    is_available: bool = True
    is_featured: bool = False
    is_bestseller: bool = False
    allows_message: bool = False
    message_max_length: int = Field(40, ge=1, le=200)
    prep_time_hours: int = Field(24, ge=0, le=720)
    meta_title: str | None = Field(None, max_length=200)
    meta_description: str | None = Field(None, max_length=300)
    images: list[ImageIn] = []
    variants: list[VariantIn] = []
    option_groups: list[GroupIn] = []
    addons: list[AddonIn] = []

    @model_validator(mode="after")
    def _rules(self):
        if self.product_type == "variable":
            if not any(v.is_active for v in self.variants):
                raise ValueError("variable products need at least one active variant")
        else:
            if self.variants:
                raise ValueError("simple products cannot have variants")
            if self.sale_price is not None and self.sale_price > self.base_price:
                raise ValueError("sale_price cannot exceed base_price")
        return self


class ProductOut(ORM):
    id: int
    name: str
    slug: str
    description: str
    category_id: int | None
    product_type: str
    base_price: Decimal
    sale_price: Decimal | None
    sku: str | None
    track_stock: bool
    stock_qty: int
    low_stock_threshold: int
    is_available: bool
    is_featured: bool
    is_bestseller: bool
    allows_message: bool
    message_max_length: int
    prep_time_hours: int
    sales_count: int
    meta_title: str | None
    meta_description: str | None
    images: list[ImageIn]
    variants: list[VariantIn]
    option_groups: list[GroupIn]
    addons: list[AddonIn]


def _live_product(db: Session, id_: int) -> Product:
    p = db.get(Product, id_)
    if p is None or p.deleted_at is not None:
        raise HTTPException(404, "Product not found")
    return p


def _apply(db: Session, p: Product, d: ProductIn) -> None:
    if d.category_id is not None:
        _live_category(db, d.category_id)
    scalars = d.model_dump(exclude={"images", "variants", "option_groups", "addons", "slug"})
    for k, v in scalars.items():
        setattr(p, k, v)
    if d.product_type == "variable":  # denormalised "from" price for listing/filtering
        active = [v for v in d.variants if v.is_active]
        p.base_price = min(v.price for v in active)
        p.sale_price = None
        p.stock_qty = sum(v.stock_qty for v in active)
    # Images, option groups and add-ons are replaced wholesale. Orders snapshot names/prices, so history is safe;
    # carts holding an old option id will show a 'review your cart' error and the customer re-selects.
    p.images = [ProductImage(url=i.url, alt=i.alt, sort_order=n) for n, i in enumerate(d.images)]
    # Variants are reconciled by id (not recreated) so recipes and any references to them survive an edit.
    existing = {v.id: v for v in p.variants}
    kept: list[ProductVariant] = []
    for n, v in enumerate(d.variants):
        data = v.model_dump(exclude={"id"})
        if v.id is not None:
            ev = existing.get(v.id)
            if ev is None:
                raise HTTPException(422, f"Unknown variant id {v.id}")
            for k, val in data.items():
                setattr(ev, k, val)
            ev.sort_order = n
            kept.append(ev)
        else:
            kept.append(ProductVariant(**data, sort_order=n))
    p.variants = kept  # variants omitted from the request are deleted (orphan cascade)
    p.option_groups = [
        OptionGroup(name=g.name, is_required=g.is_required, sort_order=n,
                    choices=[OptionChoice(**c.model_dump(exclude={"id"}), sort_order=m) for m, c in enumerate(g.choices)])
        for n, g in enumerate(d.option_groups)
    ]
    p.addons = [ProductAddon(**a.model_dump(exclude={"id"}), sort_order=n) for n, a in enumerate(d.addons)]


@router.get("/products")
def list_products(q: str | None = None, category_id: int | None = None, page: int = 1, page_size: int = 20,
                  db: Session = Depends(get_db), _: User = Depends(prod_read)):
    page_size = max(1, min(page_size, 100))
    stmt = select(Product).where(Product.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.sku.ilike(like))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Product.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"items": [ProductOut.model_validate(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/products/low-stock")
def low_stock(db: Session = Depends(get_db), _: User = Depends(prod_read)):
    rows = db.scalars(select(Product).where(Product.deleted_at.is_(None), Product.track_stock.is_(True),
                                            Product.stock_qty <= Product.low_stock_threshold)
                      .order_by(Product.stock_qty)).all()
    return [{"id": r.id, "name": r.name, "stock_qty": r.stock_qty, "threshold": r.low_stock_threshold} for r in rows]


@router.get("/products/{pid}", response_model=ProductOut)
def get_product(pid: int, db: Session = Depends(get_db), _: User = Depends(prod_read)):
    return _live_product(db, pid)


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductIn, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    slug = data.slug or unique_slug(slugify(data.name), lambda s: db.scalar(select(Product.id).where(Product.slug == s)) is not None)
    p = Product(slug=slug)
    _apply(db, p, data)
    db.add(p)
    db.flush()
    audit.record(db, actor, "product.create", "products", p.id)
    _commit(db)
    return p


@router.put("/products/{pid}", response_model=ProductOut)
def update_product(pid: int, data: ProductIn, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    p = _live_product(db, pid)
    if data.slug:
        p.slug = data.slug
    _apply(db, p, data)
    audit.record(db, actor, "product.update", "products", p.id)
    _commit(db)
    return p


@router.delete("/products/{pid}", status_code=204)
def delete_product(pid: int, db: Session = Depends(get_db), actor: User = Depends(prod_write)):
    p = _live_product(db, pid)
    p.deleted_at = datetime.now(timezone.utc)
    p.is_available = False
    p.slug = f"{p.slug}--deleted-{p.id}"
    if p.sku:
        p.sku = f"{p.sku}--deleted-{p.id}"
    audit.record(db, actor, "product.delete", "products", p.id)
    db.commit()


# ---------------- image upload ----------------
@router.post("/uploads/image")
async def upload_image(file: UploadFile = File(...), actor: User = Depends(prod_write)):
    storage = get_storage()
    data = await file.read(storage.max_bytes + 1)  # never read more than the cap
    try:
        url = storage.save(data)
    except UploadError as e:
        raise HTTPException(422, str(e))
    return {"url": url}
