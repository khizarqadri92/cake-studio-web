from app.services.invoice import render_html, render_pdf

INV = {
    "site_name": "Cake Studio", "address": "1 Baker St", "phone": "123", "email": "a@b.c", "number": "CS-261117-AB12",
    "date": "2026-11-17", "status": "Confirmed", "payment_status": "unpaid",
    "customer": {"name": "Ayesha <script>alert(1)</script>", "phone": "+9230000", "email": "x@y.z", "address": "Street 5, Lahore"},
    "fulfillment": "Delivery", "schedule": "2026-11-20 10:00-13:00", "currency": "USD",
    "items": [{"name": "Choco & Cream <b>Cake</b>", "detail": "1 kg · Eggless", "qty": 2, "unit": "30.00", "total": "60.00"}],
    "subtotal": "60.00", "discount": "5.00", "delivery_fee": "5.00", "tax": "0", "total": "60.00", "paid": "0", "balance": "60.00",
}


def test_html_escapes_user_text():
    h = render_html(INV)
    assert "<script>alert(1)</script>" not in h and "&lt;script&gt;" in h
    assert "CS-261117-AB12" in h and "USD 60.00" in h and "-USD 5.00" in h


def test_pdf_is_valid_and_survives_markup_in_names():
    pdf = render_pdf(INV)
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF") and len(pdf) > 1500
