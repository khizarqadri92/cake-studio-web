"""Stock movements. Every change goes through `move` so each one has a ledger row and a running balance."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryTransaction, Order, ProductRecipe
from app.services.bom import requirements


class InventoryError(ValueError):
    pass


def move(db: Session, item_id: int, change: Decimal, kind: str, user_id: int | None, reference: str | None = None,
         note: str = "") -> InventoryTransaction:
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.deleted_at.is_(None)).with_for_update())
    if item is None:
        raise InventoryError("Inventory item not found")
    item.stock_qty = Decimal(item.stock_qty) + change
    tx = InventoryTransaction(item_id=item.id, kind=kind, qty_change=change, balance_after=item.stock_qty, reference=reference,
                              note=note[:300], user_id=user_id, created_at=datetime.now(timezone.utc))
    db.add(tx)
    return tx


def deduct_for_order(db: Session, o: Order, user_id: int | None) -> None:
    """Take recipe ingredients for the order. Idempotent. Stock may go negative on purpose (the bakery still has
    to bake the order); negative/low balances surface in the low-stock list instead of blocking sales."""
    if o.ingredients_deducted:
        return
    pids = {i.product_id for i in o.items if i.product_id}
    recipes = [(r.product_id, r.variant_id, r.item_id, Decimal(r.qty_per_unit))
               for r in db.scalars(select(ProductRecipe).where(ProductRecipe.product_id.in_(pids)))] if pids else []
    need = requirements([(i.product_id, i.variant_id, i.quantity) for i in o.items if i.product_id], recipes)
    for item_id, qty in sorted(need.items()):
        move(db, item_id, -qty, "order_deduction", user_id, f"order:{o.order_number}", "Recipe ingredients")
    o.ingredients_deducted = True


def restore_for_order(db: Session, o: Order, user_id: int | None) -> None:
    """Return exactly what was deducted (read from the ledger, so later recipe edits cannot cause drift)."""
    if not o.ingredients_deducted:
        return
    ref = f"order:{o.order_number}"
    net: dict[int, Decimal] = defaultdict(Decimal)
    for t in db.scalars(select(InventoryTransaction).where(InventoryTransaction.reference == ref,
                                                           InventoryTransaction.kind.in_(("order_deduction", "order_return")))):
        net[t.item_id] += Decimal(t.qty_change)
    for item_id, qty in sorted(net.items()):
        if qty < 0:
            move(db, item_id, -qty, "order_return", user_id, ref, "Order cancelled")
    o.ingredients_deducted = False
