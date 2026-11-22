"""Invoice rendering from a plain dict (no DB access), as printable HTML and as PDF (reportlab)."""
from html import escape
from io import BytesIO
from xml.sax.saxutils import escape as xesc

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# invoice dict shape:
# {site_name, address, phone, email, number, date, status, payment_status, customer:{name,phone,email,address},
#  fulfillment, schedule, currency, items:[{name, detail, qty, unit, total}],
#  subtotal, discount, delivery_fee, tax, total, paid, balance}


def _money(cur: str, v) -> str:
    return f"{cur} {float(v):,.2f}"


def _rows(inv: dict) -> list[tuple[str, str]]:
    cur, rows = inv["currency"], [("Subtotal", _money(inv["currency"], inv["subtotal"]))]
    if float(inv["discount"]) > 0:
        rows.append(("Discount", "-" + _money(cur, inv["discount"])))
    rows.append(("Delivery", _money(cur, inv["delivery_fee"])))
    if float(inv["tax"]) > 0:
        rows.append(("Tax", _money(cur, inv["tax"])))
    rows += [("Total", _money(cur, inv["total"])), ("Paid", _money(cur, inv["paid"])), ("Balance due", _money(cur, inv["balance"]))]
    return rows


def render_html(inv: dict) -> str:
    cur = inv["currency"]
    items = "".join(
        f"<tr><td>{escape(i['name'])}<br><small>{escape(i['detail'])}</small></td><td>{i['qty']}</td>"
        f"<td>{_money(cur, i['unit'])}</td><td>{_money(cur, i['total'])}</td></tr>" for i in inv["items"])
    totals = "".join(f"<tr><td colspan='3' align='right'>{k}</td><td>{escape(v)}</td></tr>" for k, v in _rows(inv))
    c = inv["customer"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Invoice {escape(inv['number'])}</title>
<style>body{{font-family:Arial,sans-serif;max-width:800px;margin:2rem auto;color:#3e2723}}table{{width:100%;border-collapse:collapse}}
td,th{{padding:8px;border-bottom:1px solid #eee;text-align:left}}th{{background:#fff8f0}}@media print{{button{{display:none}}}}</style></head><body>
<button onclick="window.print()">Print</button>
<h1>{escape(inv['site_name'])}</h1><p>{escape(inv.get('address') or '')}<br>{escape(inv.get('phone') or '')} {escape(inv.get('email') or '')}</p>
<h2>Invoice {escape(inv['number'])}</h2><p>Date: {escape(inv['date'])} · Status: {escape(inv['status'])} · Payment: {escape(inv['payment_status'])}</p>
<p><b>Bill to:</b> {escape(c['name'])}<br>{escape(c.get('phone') or '')}<br>{escape(c.get('email') or '')}<br>{escape(c.get('address') or '')}</p>
<p><b>{escape(inv['fulfillment'])}:</b> {escape(inv['schedule'])}</p>
<table><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Total</th></tr>{items}{totals}</table></body></html>"""


def render_pdf(inv: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"Invoice {inv['number']}")
    ss = getSampleStyleSheet()
    p = lambda text, st="Normal": Paragraph(xesc(str(text)).replace("\n", "<br/>"), ss[st])  # noqa: E731 (user text is escaped)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=colors.grey)
    cur, c = inv["currency"], inv["customer"]
    story = [p(inv["site_name"], "Title"), p(" · ".join(x for x in (inv.get("address"), inv.get("phone"), inv.get("email")) if x)),
             Spacer(1, 8), p(f"Invoice {inv['number']}", "Heading2"),
             p(f"Date: {inv['date']}   Status: {inv['status']}   Payment: {inv['payment_status']}"), Spacer(1, 6),
             p(f"Bill to: {c['name']}\n{c.get('phone') or ''}\n{c.get('email') or ''}\n{c.get('address') or ''}"), Spacer(1, 4),
             p(f"{inv['fulfillment']}: {inv['schedule']}"), Spacer(1, 10)]
    data = [["Item", "Qty", "Unit", "Total"]]
    for i in inv["items"]:
        data.append([Paragraph(xesc(i["name"]) + (f"<br/><font size=8 color=grey>{xesc(i['detail'])}</font>" if i["detail"] else ""), ss["Normal"]),
                     str(i["qty"]), _money(cur, i["unit"]), _money(cur, i["total"])])
    n_items = len(data)
    for k, v in _rows(inv):
        data.append(["", "", k, v])
    t = Table(data, colWidths=[90 * mm, 15 * mm, 33 * mm, 33 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF8F0")), ("LINEBELOW", (0, 0), (-1, n_items - 1), 0.25, colors.lightgrey),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("FONTNAME", (2, -3), (-1, -3), "Helvetica-Bold")]))
    story += [t, Spacer(1, 14), Paragraph("Thank you for your order.", small)]
    doc.build(story)
    return buf.getvalue()
