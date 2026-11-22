from datetime import date
from decimal import Decimal as D
from io import BytesIO

from openpyxl import load_workbook

from app.services import reports as R
from app.services.exporters import to_pdf, to_xlsx


def order(id, day, status, total, pm="cod", phone="1", name="A", items=()):
    return {"id": id, "day": day, "status": status, "total": D(total), "payment_method": pm, "customer_id": 1,
            "customer_name": name, "customer_phone": phone, "order_number": f"CS-{id}", "items": list(items)}


def item(pid, name, qty, total, cat="Cakes"):
    return {"product_id": pid, "name": name, "category_id": 1, "category_name": cat, "qty": qty, "line_total": D(total)}


ORDERS = [
    order(1, date(2026, 11, 16), "delivered", "100", items=[item(1, "Choco", 2, "60"), item(2, "Brownie", 4, "40", "Brownies")]),
    order(2, date(2026, 11, 17), "confirmed", "50", pm="bank_transfer", phone="2", name="B", items=[item(1, "Choco", 1, "50")]),
    order(3, date(2026, 11, 17), "cancelled", "999", items=[item(1, "Choco", 9, "999")]),
    order(4, date(2026, 12, 1), "pending_confirmation", "30", phone="2", name="B", items=[item(2, "Brownie", 3, "30", "Brownies")]),
    order(5, date(2026, 11, 18), "refunded", "70"),
]


def test_cancelled_and_refunded_excluded_from_sales():
    s = R.sales_by_period(ORDERS, "day")
    assert [(r["period"], r["orders"], r["revenue"]) for r in s] == [("2026-11-16", 1, D("100")), ("2026-11-17", 1, D("50")), ("2026-12-01", 1, D("30"))]


def test_period_granularity():
    assert R.period_key(date(2026, 1, 1), "week") == "2026-W01"
    assert R.period_key(date(2025, 12, 29), "week") == "2026-W01"  # ISO week belongs to next year
    m = R.sales_by_period(ORDERS, "month")
    assert [(r["period"], r["revenue"]) for r in m] == [("2026-11", D("150")), ("2026-12", D("30"))]
    assert R.sales_by_period(ORDERS, "year")[0]["orders"] == 3
    assert m[0]["average_order"] == D("75.00")


def test_products_categories_best_sellers():
    p = R.product_sales(ORDERS)
    assert p[0] == {"product": "Choco", "quantity": 3, "revenue": D("110")}  # cancelled 9 not counted
    assert R.best_sellers(ORDERS, 1)[0]["product"] == "Brownie"  # 7 units beats 3
    assert {c["category"]: c["revenue"] for c in R.category_sales(ORDERS)} == {"Cakes": D("110"), "Brownies": D("70")}


def test_status_payment_customers_cancelled():
    assert {r["status"]: r["orders"] for r in R.order_status(ORDERS)}["cancelled"] == 1
    assert {r["method"]: r["revenue"] for r in R.payment_methods(ORDERS)} == {"cod": D("130"), "bank_transfer": D("50")}
    c = R.customer_purchases(ORDERS)
    assert (c[0]["customer"], c[0]["total_spent"]) == ("A", D("100"))
    assert [r["order_id"] for r in R.cancelled_orders(ORDERS)] == [3, 5]


def test_dashboard_and_zero_filled_series():
    d = R.dashboard(ORDERS, date(2026, 11, 15), date(2026, 11, 19), today=date(2026, 11, 17))
    assert [r["period"] for r in d["sales_series"]] == [f"2026-11-{n}" for n in range(15, 20)]
    assert [r["revenue"] for r in d["sales_series"]] == [0, D("100"), D("50"), 0, 0]
    assert d["today_sales"] == D("50") and d["month_revenue"] == D("150")
    assert (d["pending_orders"], d["completed_orders"], d["cancelled_orders"]) == (1, 1, 2)


def test_xlsx_neutralises_formula_injection_and_keeps_numbers():
    cols = [("customer", "Customer"), ("total", "Total")]
    wb = load_workbook(BytesIO(to_xlsx("Test", cols, [{"customer": "=HYPERLINK(\"http://evil\")", "total": D("12.5")}, {"customer": "Ok", "total": D("1")}])))
    ws = wb.active
    assert ws["A1"].value == "Customer" and ws["A2"].value.startswith("'=") and ws["B2"].value == 12.5 and ws["A3"].value == "Ok"
    assert ws["A2"].data_type == "s"


def test_pdf_export_valid_even_with_markup_and_empty():
    cols = [("a", "A")]
    assert to_pdf("T", "range", cols, [{"a": "<b>x</b> & y"}]).startswith(b"%PDF")
    assert to_pdf("T", "range", cols, []).startswith(b"%PDF")
