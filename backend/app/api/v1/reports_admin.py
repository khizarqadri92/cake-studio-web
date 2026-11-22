from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import InventoryItem, Order, Product, ProductCategory, User
from app.services import exporters, reports, shop

router = APIRouter(prefix="/admin", tags=["reports"])
MAX_DAYS, MAX_ORDERS = 1830, 100_000


def _str(v):
    """Decimals -> strings so money never passes through binary floats in JSON."""
    if isinstance(v, Decimal):
        return str(v.quantize(Decimal("0.01")))
    if isinstance(v, dict):
        return {k: _str(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_str(x) for x in v]
    return v


def _range(start: date | None, end: date | None, tz: ZoneInfo) -> tuple[date, date]:
    today = datetime.now(tz).date()
    end = end or today
    start = start or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, "'from' must not be after 'to'")
    if (end - start).days > MAX_DAYS:
        raise HTTPException(422, f"Date range is limited to {MAX_DAYS} days")
    return start, end


def load_orders(db: Session, start: date, end: date, tz: ZoneInfo) -> list[dict]:
    lo = datetime.combine(start, time.min, tzinfo=tz)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    rows = db.scalars(select(Order).where(Order.created_at >= lo, Order.created_at < hi).limit(MAX_ORDERS + 1)).all()
    if len(rows) > MAX_ORDERS:
        raise HTTPException(422, "Too many orders in this range; choose a shorter period")
    cat_ids = {i.category_id for o in rows for i in o.items if i.category_id}
    cats = {c.id: c.name for c in db.scalars(select(ProductCategory).where(ProductCategory.id.in_(cat_ids)))} if cat_ids else {}
    return [{"id": o.id, "order_number": o.order_number, "day": o.created_at.astimezone(tz).date(), "status": o.status,
             "total": Decimal(o.total), "payment_method": o.payment_method_code, "customer_id": o.customer_id,
             "customer_name": o.customer_name, "customer_phone": o.customer_phone,
             "items": [{"product_id": i.product_id, "name": i.product_name, "category_id": i.category_id,
                        "category_name": cats.get(i.category_id), "qty": i.quantity, "line_total": Decimal(i.line_total)} for i in o.items]}
            for o in rows]


@router.get("/dashboard")
def dashboard(date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
              _: User = Depends(require_permission("dashboard.read"))):
    tz = ZoneInfo(shop.get_group(db, "checkout")["timezone"])
    start, end = _range(date_from, date_to, tz)
    today = datetime.now(tz).date()
    # today's / this month's sales are independent of the chosen range, so load them separately
    month_start = today.replace(day=1)
    orders = load_orders(db, start, end, tz)
    base = reports.dashboard(orders, start, end, today)
    ctx = load_orders(db, min(month_start, start), max(today, end), tz) if (month_start < start or today > end) else orders
    base["today_sales"] = sum((o["total"] for o in ctx if reports.is_sale(o) and o["day"] == today), Decimal(0))
    base["month_revenue"] = sum((o["total"] for o in ctx if reports.is_sale(o) and month_start <= o["day"] <= today), Decimal(0))
    all_time = db.scalars(select(Order.total).where(Order.status.notin_(reports.NOT_SALES))).all()
    base["all_time_sales"] = sum((Decimal(t) for t in all_time), Decimal(0))
    low_products = db.scalars(select(Product).where(Product.deleted_at.is_(None), Product.track_stock.is_(True),
                                                    Product.stock_qty <= Product.low_stock_threshold).order_by(Product.stock_qty).limit(10)).all()
    low_items = db.scalars(select(InventoryItem).where(InventoryItem.deleted_at.is_(None), InventoryItem.is_active.is_(True),
                                                       InventoryItem.stock_qty <= InventoryItem.low_stock_threshold).order_by(InventoryItem.stock_qty).limit(10)).all()
    recent = db.scalars(select(Order).order_by(Order.id.desc()).limit(8)).all()
    base["low_stock_products"] = [{"id": p.id, "name": p.name, "stock": p.stock_qty} for p in low_products]
    base["low_stock_ingredients"] = [{"id": i.id, "name": i.name, "stock": str(i.stock_qty), "unit": i.unit} for i in low_items]
    base["recent_orders"] = [{"id": o.id, "order_number": o.order_number, "customer": o.customer_name, "status": o.status,
                              "total": o.total, "at": o.created_at.isoformat()} for o in recent]
    return _str(base)


def _inventory_rows(db: Session):
    return [{"item": i.name, "kind": i.kind, "unit": i.unit, "stock": i.stock_qty, "threshold": i.low_stock_threshold,
             "status": "LOW" if i.stock_qty <= i.low_stock_threshold else "ok", "value": Decimal(i.stock_qty) * Decimal(i.cost_per_unit)}
            for i in db.scalars(select(InventoryItem).where(InventoryItem.deleted_at.is_(None)).order_by(InventoryItem.name))]


M, N = "Revenue", "Orders"
REPORTS: dict[str, tuple[str, list[tuple[str, str]], callable]] = {
    "daily_sales": ("Daily sales", [("period", "Day"), ("orders", N), ("revenue", M), ("average_order", "Avg order")], lambda o, db: reports.sales_by_period(o, "day")),
    "weekly_sales": ("Weekly sales", [("period", "Week"), ("orders", N), ("revenue", M), ("average_order", "Avg order")], lambda o, db: reports.sales_by_period(o, "week")),
    "monthly_sales": ("Monthly sales", [("period", "Month"), ("orders", N), ("revenue", M), ("average_order", "Avg order")], lambda o, db: reports.sales_by_period(o, "month")),
    "annual_sales": ("Annual sales", [("period", "Year"), ("orders", N), ("revenue", M), ("average_order", "Avg order")], lambda o, db: reports.sales_by_period(o, "year")),
    "product_sales": ("Product-wise sales", [("product", "Product"), ("quantity", "Qty"), ("revenue", M)], lambda o, db: reports.product_sales(o)),
    "category_sales": ("Category-wise sales", [("category", "Category"), ("quantity", "Qty"), ("revenue", M)], lambda o, db: reports.category_sales(o)),
    "order_status": ("Order status", [("status", "Status"), ("orders", N), ("value", "Value")], lambda o, db: reports.order_status(o)),
    "payment_methods": ("Payment methods", [("method", "Method"), ("orders", N), ("revenue", M)], lambda o, db: reports.payment_methods(o)),
    "customer_purchases": ("Customer purchases", [("customer", "Customer"), ("phone", "Phone"), ("orders", N), ("total_spent", "Total spent")], lambda o, db: reports.customer_purchases(o)),
    "best_sellers": ("Best-selling products", [("product", "Product"), ("quantity", "Qty"), ("revenue", M)], lambda o, db: reports.best_sellers(o, 20)),
    "cancelled_orders": ("Cancelled orders", [("order_number", "Order"), ("date", "Date"), ("customer", "Customer"), ("status", "Status"), ("value", "Value")], lambda o, db: reports.cancelled_orders(o)),
    "inventory": ("Inventory", [("item", "Item"), ("kind", "Type"), ("unit", "Unit"), ("stock", "Stock"), ("threshold", "Low-stock at"), ("status", "Status"), ("value", "Stock value")], None),
}


@router.get("/reports/{report_type}")
def report(report_type: str, date_from: date | None = None, date_to: date | None = None,
           format: Literal["json", "xlsx", "pdf"] = "json", db: Session = Depends(get_db),
           _: User = Depends(require_permission("reports.read"))):
    if report_type not in REPORTS:
        raise HTTPException(404, "Unknown report")
    title, cols, build = REPORTS[report_type]
    tz = ZoneInfo(shop.get_group(db, "checkout")["timezone"])
    start, end = _range(date_from, date_to, tz)
    rows = _inventory_rows(db) if build is None else build(load_orders(db, start, end, tz), db)
    sub = "Current stock" if build is None else f"{start.isoformat()} to {end.isoformat()}"
    if format == "json":
        return {"title": title, "range": sub, "columns": [{"key": k, "label": h} for k, h in cols], "rows": _str(rows)}
    fname = f"{report_type}_{start}_{end}"
    if format == "xlsx":
        return Response(exporters.to_xlsx(title, cols, rows), headers={"Content-Disposition": f'attachment; filename="{fname}.xlsx"'},
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return Response(exporters.to_pdf(title, sub, cols, rows), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})
