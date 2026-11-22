"""Excel and PDF export of tabular report data."""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(v):
    """Neutralise spreadsheet formula injection: customer-controlled text such as '=HYPERLINK(...)'
    must never be interpreted as a formula when staff open the export."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, str) and v.startswith(_FORMULA_START):
        return "'" + v
    return v


def _text(v) -> str:
    return f"{v:,.2f}" if isinstance(v, Decimal) else str(v)


def to_xlsx(title: str, columns: list[tuple[str, str]], rows: list[dict]) -> bytes:
    """columns = [(key, header)]."""
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append([h for _, h in columns])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF8F0")
    for r in rows:
        ws.append([_cell(r.get(k, "")) for k, _ in columns])
    for idx, (k, h) in enumerate(columns, start=1):
        width = max([len(h)] + [len(_text(r.get(k, ""))) for r in rows[:200]]) + 2
        ws.column_dimensions[ws.cell(1, idx).column_letter].width = min(width, 50)
    ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(title: str, subtitle: str, columns: list[tuple[str, str]], rows: list[dict]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=title)
    ss = getSampleStyleSheet()
    cellstyle = ss["BodyText"]
    cellstyle.fontSize = 8
    data = [[h for _, h in columns]] + [[Paragraph(escape(_text(r.get(k, ""))), cellstyle) for k, _ in columns] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF8F0")), ("FONTSIZE", (0, 0), (-1, 0), 8),
                           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph(escape(title), ss["Title"]), Paragraph(escape(subtitle), ss["Normal"]), Spacer(1, 8)]
    story.append(t if rows else Paragraph("No data for this period.", ss["Normal"]))
    doc.build(story)
    return buf.getvalue()
