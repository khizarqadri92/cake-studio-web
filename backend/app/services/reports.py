"""Report aggregation (pure). Input rows are plain dicts so the maths is testable without a database.

order dict: {id, day: date (store-local), status, total: Decimal, payment_method, customer_id, customer_name,
             customer_phone, items: [{product_id, name, category_id, category_name, qty, line_total: Decimal}]}
Sales/revenue count every order except cancelled and refunded ones.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

NOT_SALES = {"cancelled", "refunded"}
ZERO = Decimal(0)


def is_sale(o: dict) -> bool:
    return o["status"] not in NOT_SALES


def period_key(d: date, granularity: str) -> str:
    if granularity == "day":
        return d.isoformat()
    if granularity == "week":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if granularity == "month":
        return f"{d.year}-{d.month:02d}"
    if granularity == "year":
        return str(d.year)
    raise ValueError("granularity must be day, week, month or year")


def sales_by_period(orders: list[dict], granularity: str) -> list[dict]:
    acc: dict[str, list] = defaultdict(lambda: [0, ZERO])
    for o in orders:
        if is_sale(o):
            a = acc[period_key(o["day"], granularity)]
            a[0] += 1
            a[1] += o["total"]
    return [{"period": k, "orders": v[0], "revenue": v[1], "average_order": (v[1] / v[0]).quantize(Decimal("0.01")) if v[0] else ZERO}
            for k, v in sorted(acc.items())]


def daily_series(orders: list[dict], start: date, end: date) -> list[dict]:
    """Every day in [start, end] (zero-filled) so charts have no gaps."""
    by = {r["period"]: r for r in sales_by_period(orders, "day")}
    out, d = [], start
    while d <= end:
        r = by.get(d.isoformat())
        out.append({"period": d.isoformat(), "orders": r["orders"] if r else 0, "revenue": r["revenue"] if r else ZERO})
        d += timedelta(days=1)
    return out


def product_sales(orders: list[dict]) -> list[dict]:
    acc: dict = defaultdict(lambda: [0, ZERO, ""])
    for o in orders:
        if not is_sale(o):
            continue
        for i in o["items"]:
            a = acc[(i["product_id"], i["name"])]
            a[0] += i["qty"]
            a[1] += i["line_total"]
    rows = [{"product": k[1], "quantity": v[0], "revenue": v[1]} for k, v in acc.items()]
    return sorted(rows, key=lambda r: (-r["revenue"], r["product"]))


def best_sellers(orders: list[dict], limit: int = 10) -> list[dict]:
    rows = sorted(product_sales(orders), key=lambda r: (-r["quantity"], -r["revenue"], r["product"]))
    return rows[:limit]


def category_sales(orders: list[dict]) -> list[dict]:
    acc: dict = defaultdict(lambda: [0, ZERO])
    for o in orders:
        if not is_sale(o):
            continue
        for i in o["items"]:
            a = acc[i.get("category_name") or "Uncategorised"]
            a[0] += i["qty"]
            a[1] += i["line_total"]
    return sorted(({"category": k, "quantity": v[0], "revenue": v[1]} for k, v in acc.items()), key=lambda r: (-r["revenue"], r["category"]))


def order_status(orders: list[dict]) -> list[dict]:
    acc: dict = defaultdict(lambda: [0, ZERO])
    for o in orders:
        a = acc[o["status"]]
        a[0] += 1
        a[1] += o["total"]
    return [{"status": k, "orders": v[0], "value": v[1]} for k, v in sorted(acc.items())]


def payment_methods(orders: list[dict]) -> list[dict]:
    acc: dict = defaultdict(lambda: [0, ZERO])
    for o in orders:
        if is_sale(o):
            a = acc[o["payment_method"]]
            a[0] += 1
            a[1] += o["total"]
    return [{"method": k, "orders": v[0], "revenue": v[1]} for k, v in sorted(acc.items())]


def customer_purchases(orders: list[dict]) -> list[dict]:
    acc: dict = {}
    for o in orders:
        if not is_sale(o):
            continue
        a = acc.setdefault(o["customer_phone"], {"customer": o["customer_name"], "phone": o["customer_phone"], "orders": 0, "total_spent": ZERO})
        a["orders"] += 1
        a["total_spent"] += o["total"]
    return sorted(acc.values(), key=lambda r: (-r["total_spent"], r["customer"]))


def cancelled_orders(orders: list[dict]) -> list[dict]:
    return [{"order_id": o["id"], "order_number": o.get("order_number", ""), "date": o["day"].isoformat(), "customer": o["customer_name"],
             "status": o["status"], "value": o["total"]} for o in orders if o["status"] in NOT_SALES]


def dashboard(orders: list[dict], start: date, end: date, today: date) -> dict:
    sales = [o for o in orders if is_sale(o)]
    month_start = today.replace(day=1)
    counts = {s: 0 for s in ("pending_confirmation", "completed", "cancelled")}
    for o in orders:
        if o["status"] == "pending_confirmation":
            counts["pending_confirmation"] += 1
        elif o["status"] == "delivered":
            counts["completed"] += 1
        elif o["status"] in NOT_SALES:
            counts["cancelled"] += 1
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "total_sales": sum((o["total"] for o in sales), ZERO),  # within the selected range
        "total_orders": len(orders),
        "pending_orders": counts["pending_confirmation"],
        "completed_orders": counts["completed"],
        "cancelled_orders": counts["cancelled"],
        "sales_series": daily_series(orders, start, end),
        "status_chart": order_status(orders),
        "best_sellers": best_sellers(orders, 5),
        "today_sales": sum((o["total"] for o in sales if o["day"] == today), ZERO),
        "month_revenue": sum((o["total"] for o in sales if month_start <= o["day"] <= today), ZERO),
    }
