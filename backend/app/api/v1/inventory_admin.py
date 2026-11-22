from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (InventoryItem, InventoryTransaction, Product, ProductRecipe, ProductVariant, PurchaseOrder,
                        PurchaseOrderItem, Supplier, User)
from app.services import audit, inventory_ops

router = APIRouter(prefix="/admin", tags=["inventory-admin"])
inv_read, inv_write = require_permission("inventory.read"), require_permission("inventory.write")
Qty = Field(gt=0, max_digits=14, decimal_places=3)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Conflicts with an existing record (duplicate SKU?)")


def _live(db, model, id_, label):
    o = db.get(model, id_)
    if o is None or getattr(o, "deleted_at", None) is not None:
        raise HTTPException(404, f"{label} not found")
    return o


def _inv(fn, *a, **k):
    try:
        return fn(*a, **k)
    except inventory_ops.InventoryError as e:
        raise HTTPException(422, str(e))


# ---------------- suppliers ----------------
class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_name: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=255)
    address: str | None = Field(None, max_length=300)
    notes: str = ""


class SupplierOut(ORM, SupplierIn):
    id: int


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(inv_read)):
    return list(db.scalars(select(Supplier).where(Supplier.deleted_at.is_(None)).order_by(Supplier.name)))


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(d: SupplierIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    s = Supplier(**d.model_dump())
    db.add(s)
    db.flush()
    audit.record(db, a, "supplier.create", "suppliers", s.id)
    db.commit()
    return s


@router.put("/suppliers/{sid}", response_model=SupplierOut)
def update_supplier(sid: int, d: SupplierIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    s = _live(db, Supplier, sid, "Supplier")
    for k, v in d.model_dump().items():
        setattr(s, k, v)
    audit.record(db, a, "supplier.update", "suppliers", sid)
    db.commit()
    return s


@router.delete("/suppliers/{sid}", status_code=204)
def delete_supplier(sid: int, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    _live(db, Supplier, sid, "Supplier").deleted_at = datetime.now(timezone.utc)
    audit.record(db, a, "supplier.delete", "suppliers", sid)
    db.commit()


# ---------------- items ----------------
class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    sku: str | None = Field(None, max_length=64)
    kind: Literal["raw_material", "ingredient", "packaging"] = "ingredient"
    unit: str = Field("kg", min_length=1, max_length=20)
    low_stock_threshold: Decimal = Field(Decimal(0), ge=0, max_digits=14, decimal_places=3)
    cost_per_unit: Decimal = Field(Decimal(0), ge=0, max_digits=12, decimal_places=2)
    supplier_id: int | None = None
    is_active: bool = True


class ItemCreate(ItemIn):
    opening_stock: Decimal = Field(Decimal(0), ge=0, max_digits=14, decimal_places=3)


class ItemOut(ORM, ItemIn):
    id: int
    stock_qty: Decimal


@router.get("/inventory/items")
def list_items(q: str | None = None, kind: str | None = None, low_stock: bool = False, page: int = 1, page_size: int = 50,
               db: Session = Depends(get_db), _: User = Depends(inv_read)):
    page_size = max(1, min(page_size, 200))
    stmt = select(InventoryItem).where(InventoryItem.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(InventoryItem.name.ilike(like), InventoryItem.sku.ilike(like)))
    if kind:
        stmt = stmt.where(InventoryItem.kind == kind)
    if low_stock:
        stmt = stmt.where(InventoryItem.stock_qty <= InventoryItem.low_stock_threshold)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(InventoryItem.name).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"items": [ItemOut.model_validate(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/inventory/items", response_model=ItemOut, status_code=201)
def create_item(d: ItemCreate, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    if d.supplier_id is not None:
        _live(db, Supplier, d.supplier_id, "Supplier")
    item = InventoryItem(**d.model_dump(exclude={"opening_stock"}), stock_qty=0)
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate SKU")
    if d.opening_stock > 0:
        inventory_ops.move(db, item.id, d.opening_stock, "adjustment", a.id, None, "Opening stock")
    audit.record(db, a, "inventory_item.create", "inventory_items", item.id)
    _commit(db)
    return item


@router.put("/inventory/items/{iid}", response_model=ItemOut)
def update_item(iid: int, d: ItemIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    item = _live(db, InventoryItem, iid, "Item")  # stock changes only via /adjust so the ledger stays complete
    if d.supplier_id is not None:
        _live(db, Supplier, d.supplier_id, "Supplier")
    for k, v in d.model_dump().items():
        setattr(item, k, v)
    audit.record(db, a, "inventory_item.update", "inventory_items", iid)
    _commit(db)
    return item


@router.delete("/inventory/items/{iid}", status_code=204)
def delete_item(iid: int, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    item = _live(db, InventoryItem, iid, "Item")
    item.deleted_at, item.is_active = datetime.now(timezone.utc), False
    if item.sku:
        item.sku = f"{item.sku}--deleted-{item.id}"
    db.query(ProductRecipe).filter(ProductRecipe.item_id == iid).delete()  # a deleted ingredient must not be deducted
    audit.record(db, a, "inventory_item.delete", "inventory_items", iid)
    db.commit()


class AdjustIn(BaseModel):
    kind: Literal["purchase", "usage", "waste", "adjustment"]
    quantity: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=3)  # purchase/usage/waste
    set_to: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=3)  # adjustment: counted stock
    note: str = Field("", max_length=300)

    @model_validator(mode="after")
    def _v(self):
        if self.kind == "adjustment":
            if self.set_to is None:
                raise ValueError("set_to (the counted quantity) is required for an adjustment")
        elif self.quantity is None:
            raise ValueError("quantity is required")
        return self


@router.post("/inventory/items/{iid}/adjust")
def adjust(iid: int, d: AdjustIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    item = _live(db, InventoryItem, iid, "Item")
    if d.kind == "adjustment":
        change = d.set_to - Decimal(item.stock_qty)
        if change == 0:
            raise HTTPException(422, "Counted quantity equals the current stock")
    else:
        change = d.quantity if d.kind == "purchase" else -d.quantity
    tx = _inv(inventory_ops.move, db, iid, change, d.kind, a.id, None, d.note)
    audit.record(db, a, "inventory.adjust", "inventory_items", iid, {"kind": d.kind, "change": str(change)})
    db.commit()
    return {"item_id": iid, "change": str(change), "balance": str(tx.balance_after)}


@router.get("/inventory/transactions")
def transactions(item_id: int | None = None, page: int = 1, page_size: int = 50, db: Session = Depends(get_db), _: User = Depends(inv_read)):
    page_size = max(1, min(page_size, 200))
    stmt = select(InventoryTransaction)
    if item_id:
        stmt = stmt.where(InventoryTransaction.item_id == item_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(InventoryTransaction.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [{"id": t.id, "item_id": t.item_id, "kind": t.kind, "change": str(t.qty_change), "balance": str(t.balance_after),
                                       "reference": t.reference, "note": t.note, "user_id": t.user_id, "at": t.created_at.isoformat()} for t in rows]}


# ---------------- purchase orders ----------------
class POLine(BaseModel):
    item_id: int
    quantity: Decimal = Qty
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class POIn(BaseModel):
    supplier_id: int | None = None
    notes: str = Field("", max_length=1000)
    items: list[POLine] = Field(min_length=1, max_length=100)


def _po_out(p: PurchaseOrder) -> dict:
    return {"id": p.id, "number": p.number, "supplier_id": p.supplier_id, "status": p.status, "notes": p.notes,
            "total_cost": str(p.total_cost), "received_at": p.received_at.isoformat() if p.received_at else None,
            "items": [{"item_id": i.item_id, "quantity": str(i.quantity), "unit_cost": str(i.unit_cost)} for i in p.items]}


@router.get("/purchase-orders")
def list_pos(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(inv_read)):
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.id.desc()).limit(200)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    return [_po_out(p) for p in db.scalars(stmt)]


@router.post("/purchase-orders", status_code=201)
def create_po(d: POIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    if d.supplier_id is not None:
        _live(db, Supplier, d.supplier_id, "Supplier")
    ids = [l.item_id for l in d.items]
    found = set(db.scalars(select(InventoryItem.id).where(InventoryItem.id.in_(ids), InventoryItem.deleted_at.is_(None))))
    if found != set(ids):
        raise HTTPException(422, "Unknown inventory item in order")
    po = PurchaseOrder(number="PO-TMP", supplier_id=d.supplier_id, notes=d.notes,
                       total_cost=sum((l.quantity * l.unit_cost for l in d.items), Decimal(0)).quantize(Decimal("0.01")))
    po.items = [PurchaseOrderItem(item_id=l.item_id, quantity=l.quantity, unit_cost=l.unit_cost) for l in d.items]
    db.add(po)
    db.flush()
    po.number = f"PO-{datetime.now(timezone.utc):%y%m%d}-{po.id:04d}"
    audit.record(db, a, "purchase_order.create", "purchase_orders", po.id)
    _commit(db)
    return _po_out(po)


@router.get("/purchase-orders/{pid}")
def get_po(pid: int, db: Session = Depends(get_db), _: User = Depends(inv_read)):
    return _po_out(_live(db, PurchaseOrder, pid, "Purchase order"))


@router.post("/purchase-orders/{pid}/receive")
def receive_po(pid: int, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == pid).with_for_update())  # no double receipt
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    if po.status != "ordered":
        raise HTTPException(422, f"Only an ordered purchase order can be received (this one is {po.status})")
    for l in po.items:
        _inv(inventory_ops.move, db, l.item_id, Decimal(l.quantity), "purchase", a.id, f"po:{po.number}", "Purchase received")
        item = db.get(InventoryItem, l.item_id)
        item.cost_per_unit = l.unit_cost  # latest purchase cost
    po.status, po.received_at = "received", datetime.now(timezone.utc)
    audit.record(db, a, "purchase_order.receive", "purchase_orders", po.id)
    db.commit()
    return _po_out(po)


@router.post("/purchase-orders/{pid}/cancel")
def cancel_po(pid: int, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == pid).with_for_update())
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    if po.status != "ordered":
        raise HTTPException(422, "Only an ordered purchase order can be cancelled")
    po.status = "cancelled"
    audit.record(db, a, "purchase_order.cancel", "purchase_orders", po.id)
    db.commit()
    return _po_out(po)


# ---------------- recipes (BOM) ----------------
class RecipeLine(BaseModel):
    variant_id: int | None = None
    item_id: int
    qty_per_unit: Decimal = Field(gt=0, max_digits=14, decimal_places=4)


class RecipeIn(BaseModel):
    lines: list[RecipeLine] = Field(max_length=200)


def _recipe_out(db: Session, pid: int) -> list[dict]:
    rows = db.scalars(select(ProductRecipe).where(ProductRecipe.product_id == pid).order_by(ProductRecipe.variant_id, ProductRecipe.item_id))
    return [{"variant_id": r.variant_id, "item_id": r.item_id, "qty_per_unit": str(r.qty_per_unit)} for r in rows]


@router.get("/products/{pid}/recipe")
def get_recipe(pid: int, db: Session = Depends(get_db), _: User = Depends(inv_read)):
    _live(db, Product, pid, "Product")
    return _recipe_out(db, pid)


@router.put("/products/{pid}/recipe")
def put_recipe(pid: int, d: RecipeIn, db: Session = Depends(get_db), a: User = Depends(inv_write)):
    _live(db, Product, pid, "Product")
    keys = [(l.variant_id, l.item_id) for l in d.lines]
    if len(keys) != len(set(keys)):
        raise HTTPException(422, "Duplicate ingredient in the same recipe")
    valid_items = set(db.scalars(select(InventoryItem.id).where(InventoryItem.id.in_({l.item_id for l in d.lines}), InventoryItem.deleted_at.is_(None))))
    if {l.item_id for l in d.lines} - valid_items:
        raise HTTPException(422, "Unknown inventory item in recipe")
    variants = {v for l in d.lines if (v := l.variant_id) is not None}
    if variants and variants - set(db.scalars(select(ProductVariant.id).where(ProductVariant.product_id == pid, ProductVariant.id.in_(variants)))):
        raise HTTPException(422, "Variant does not belong to this product")
    db.query(ProductRecipe).filter(ProductRecipe.product_id == pid).delete()
    db.add_all(ProductRecipe(product_id=pid, variant_id=l.variant_id, item_id=l.item_id, qty_per_unit=l.qty_per_unit) for l in d.lines)
    audit.record(db, a, "recipe.update", "products", pid)
    db.commit()
    return _recipe_out(db, pid)
