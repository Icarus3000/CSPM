import os
import html
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

def build_html(payload):
    config = payload.get("config", {})
    def esc(value):
        return html.escape(str(value if value is not None else ""))

    doc = ["<html><body style='font-family: Arial, sans-serif; font-size: 9pt; color: #111827; margin: 0; padding: 0;'>"]

    if config.get("detail"):
        doc.append("<div style='border: 1px solid #d7deea; border-radius: 8px; overflow: hidden; margin: 6px 0 14px 0; padding-top: 4px;'>")
        doc.append("<table style='width: 100%; border-collapse: collapse;'>")
        doc.append(
            "<colgroup>"
            "<col style='width:9%;' />"
            "<col style='width:14%;' />"
            "<col style='width:12%;' />"
            "<col style='width:26%;' />"
            "<col style='width:12%;' />"
            "<col style='width:13%;' />"
            "<col style='width:14%;' />"
            "</colgroup>"
        )
        doc.append("<thead><tr style='background:#eef3fb;'>")
        for heading in ["Date", "Client", "Matter", "Description", "Hours", "Gross", "Status"]:
            align = "right" if heading in ("Hours", "Gross") else "left"
            doc.append(
                f"<th style='text-align:{align}; border-bottom:1px solid #d7deea; padding:6px 8px; font-size:8.5pt; color:#1f2a44;'>{heading}</th>"
            )
        doc.append("</tr></thead><tbody>")

        rows = payload.get("rows", [])
        if rows:
            for idx, row in enumerate(rows):
                bg = "#ffffff" if idx % 2 == 0 else "#f8fbff"
                hours = float(row.get("hours", 0.0) or 0.0)
                gross = float(row.get("grossToClient", 0.0) or 0.0)
                doc.append(f"<tr style='background:{bg};'>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top;'>{esc(row.get('date',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top;'>{esc(row.get('clientName',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top;'>{esc(row.get('matterName',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top;'>{esc(row.get('description',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top; text-align:right;'>{hours:.2f}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top; text-align:right;'>${gross:.2f}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; vertical-align:top;'>{esc(row.get('status',''))}</td>")
                doc.append("</tr>")
        else:
            doc.append("<tr><td colspan='7' style='padding:10px 8px; color:#6b7280; font-style:italic;'>No detail rows returned.</td></tr>")
        doc.append("</tbody></table></div>")

    if config.get("summary"):
        doc.append("<div style='border: 1px solid #d7deea; border-radius: 8px; overflow: hidden; margin: 10px 0 12px 0;'>")
        doc.append("<div style='padding:8px 8px 6px 8px; background:#eef3fb; border-bottom:1px solid #d7deea; font-size:9pt; font-weight:700; color:#1f2a44;'>Summary by Matter</div>")
        doc.append("<table style='width: 100%; border-collapse: collapse;'>")
        doc.append("<colgroup><col style='width:34%;' /><col style='width:30%;' /><col style='width:12%;' /><col style='width:12%;' /><col style='width:12%;' /></colgroup>")
        doc.append("<thead><tr>")
        for heading in ["Matter", "Client", "Entries", "Hours", "Gross"]:
            align = "right" if heading in ("Entries", "Hours", "Gross") else "left"
            doc.append(f"<th style='text-align:{align}; border-bottom:1px solid #d7deea; padding:5px 8px; font-size:8.5pt; color:#4a5a78;'>{heading}</th>")
        doc.append("</tr></thead><tbody>")
        summary_rows = payload.get("summaryRows", [])
        if summary_rows:
            for idx, row in enumerate(summary_rows):
                bg = "#ffffff" if idx % 2 == 0 else "#f8fbff"
                doc.append(f"<tr style='background:{bg};'>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7;'>{esc(row.get('matterName',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7;'>{esc(row.get('clientName',''))}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>{int(row.get('entryCount',0) or 0)}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>{float(row.get('totalHours',0.0) or 0.0):.2f}</td>")
                doc.append(f"<td style='padding:5px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>${float(row.get('totalGrossToClient',0.0) or 0.0):.2f}</td>")
                doc.append("</tr>")
        else:
            doc.append("<tr><td colspan='5' style='padding:10px 8px; color:#6b7280; font-style:italic;'>No summary rows returned.</td></tr>")
        doc.append("</tbody></table></div>")

    if config.get("aggregate"):
        totals = payload.get("totals", {})
        entries = len(payload.get("rows", []))
        hours = float(totals.get("totalHours", 0.0) or 0.0)
        gross = float(totals.get("totalGrossToClient", 0.0) or 0.0)
        hst_rate = float(config.get("hstRate", 13.0))
        hst = gross * (hst_rate / 100.0)
        total = gross + hst

        doc.append("<div style='border: 1px solid #d7deea; border-radius: 8px; overflow: hidden; margin: 10px 0 12px 0;'>")
        doc.append("<div style='padding:8px 8px 6px 8px; background:#eef3fb; border-bottom:1px solid #d7deea; font-size:9pt; font-weight:700; color:#1f2a44;'>Aggregate Summary</div>")
        doc.append("<table style='width: 100%; border-collapse: collapse; font-size:8.5pt; color:#2f3b52;'><tbody>")
        doc.append(f"<tr><td style='padding:3px 8px; border-bottom:1px solid #edf1f7; width:40%;'><b>Entries</b></td><td style='padding:3px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>{entries}</td></tr>")
        doc.append(f"<tr><td style='padding:3px 8px; border-bottom:1px solid #edf1f7;'><b>Hours</b></td><td style='padding:3px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>{hours:.2f}</td></tr>")
        doc.append(f"<tr><td style='padding:3px 8px; border-bottom:1px solid #edf1f7;'><b>Gross (pre-HST)</b></td><td style='padding:3px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>${gross:.2f}</td></tr>")
        doc.append(f"<tr><td style='padding:3px 8px; border-bottom:1px solid #edf1f7;'><b>HST ({hst_rate:.1f}%)</b></td><td style='padding:3px 8px; border-bottom:1px solid #edf1f7; text-align:right;'>${hst:.2f}</td></tr>")
        doc.append(f"<tr><td style='padding:3px 8px;'><b>Total</b></td><td style='padding:3px 8px; text-align:right;'><b>${total:.2f}</b></td></tr>")
        doc.append("</tbody></table></div>")

    if config.get("selections"):
        filters = payload.get("filters", {})
        sort_dir = "Ascending" if payload.get("sortAscending") else "Descending"
        sections = []
        if config.get("detail"):
            sections.append("Detail")
        if config.get("summary"):
            sections.append("Summary")
        if config.get("aggregate"):
            sections.append("Aggregate")

        doc.append("<div style='border: 1px solid #d7deea; border-radius: 8px; overflow: hidden; margin: 10px 0 8px 0;'>")
        doc.append("<div style='padding:8px 8px 6px 8px; background:#eef3fb; border-bottom:1px solid #d7deea; font-size:9pt; font-weight:700; color:#1f2a44;'>Report Selections</div>")
        doc.append("<table style='width: 100%; border-collapse: collapse; font-size:8.5pt;'><tbody>")
        rows = [
            ("Requested by", str(config.get("firmAttorney", config.get("requestedBy", "")))),  # from config["firmAttorney"]
            ("Finished", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Date Range", f"{filters.get('fromDate','')} to {filters.get('toDate','')}"),
            ("Status Scope", filters.get("statusMode", "")),
            ("Client Filter", filters.get("clientFilter") or "All Clients"),
            ("Matter Filter", filters.get("matterFilter") or "All Matters"),
            ("Search Term", filters.get("query") or "(none)"),
            ("Sort Order", f"{payload.get('sortKey','date')} ({sort_dir})"),
            ("Sections", ", ".join(sections) if sections else "(none)"),
            ("HST Rate", f"{config.get('hstRate', 13.0)}%"),
        ]
        for idx, (label, value) in enumerate(rows):
            border = " border-bottom:1px solid #edf1f7;" if idx < len(rows) - 1 else ""
            doc.append(
                f"<tr>"
                f"<td style='padding:3px 8px; width:30%; color:#4a5a78;{border}'><b>{esc(label)}</b></td>"
                f"<td style='padding:3px 8px; color:#2f3b52;{border}'>{esc(value)}</td>"
                f"</tr>"
            )
        doc.append("</tbody></table></div>")

    doc.append("</body></html>")
    return "".join(doc)

def _safe_text(value):
    return "" if value is None else str(value)


def _escaped(value):
    return html.escape(_safe_text(value))


def _money(value):
    try:
        return f"${float(value or 0.0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _hours(value):
    try:
        return f"{float(value or 0.0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _paragraph(value, style):
    return Paragraph(_escaped(value), style)


def _table_style(header=True, span_empty=False):
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7deea")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2a44")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]))
    if span_empty:
        style.append(("SPAN", (0, 1), (-1, 1)))
    return TableStyle(style)


def _section_title(text, styles):
    return Paragraph(_escaped(text), styles["sectionTitle"])


def _draw_header_footer(canvas, doc, config, logo_path):
    canvas.saveState()
    width, height = doc.pagesize
    left = doc.leftMargin
    right = width - doc.rightMargin
    top = height - 0.45 * inch

    logo_drawn = False
    if logo_path and os.path.exists(logo_path):
        ext = os.path.splitext(str(logo_path))[1].lower()
        if ext in {".png", ".jpg", ".jpeg"}:
            try:
                canvas.drawImage(
                    str(logo_path),
                    left,
                    top - 0.42 * inch,
                    width=0.38 * inch,
                    height=0.38 * inch,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                logo_drawn = True
            except Exception:
                logo_drawn = False

    text_left = left + (0.48 * inch if logo_drawn else 0)
    canvas.setFillColor(colors.HexColor("#111827"))
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(text_left, top, _safe_text(config.get("firmName") or "Cory Schneider Law Office")[:80])

    canvas.setFont("Helvetica", 7.0)
    contact = _safe_text(
        config.get("firmContact")
        or "14 Parsons Court, Thornhill, ON L4K 6Z4\n416-725-9364\ncory@coryschneiderlaw.ca"
    )
    for idx, line in enumerate(contact.splitlines()[:5]):
        canvas.drawString(text_left, top - 11 - (idx * 8.5), line[:96])

    canvas.setFont("Helvetica", 7.5)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    canvas.drawRightString(right, top, f"Generated: {generated}")
    canvas.drawRightString(right, top - 11, f"Page {doc.page}")

    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawCentredString(width / 2.0, top - 0.72 * inch, "Docket Activity Report")
    canvas.setStrokeColor(colors.HexColor("#2979FF"))
    canvas.setLineWidth(0.75)
    canvas.line(left, top - 0.84 * inch, right, top - 0.84 * inch)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#4b5563"))
    canvas.drawCentredString(
        width / 2.0,
        0.34 * inch,
        f"Confidential - For client use only | Generated by CSPM {generated}",
    )
    canvas.restoreState()


def _build_story(payload, styles, available_width):
    config = dict(payload.get("config", {}) or {})
    story = []

    if config.get("detail"):
        story.append(_section_title("Detail", styles))
        headers = ["Date", "Client", "Matter", "Description", "Hours", "Gross", "Status"]
        data = [[_paragraph(h, styles["tableHeader"]) for h in headers]]
        rows = payload.get("rows", []) or []
        if rows:
            for row in rows:
                data.append(
                    [
                        _paragraph(row.get("date", ""), styles["cell"]),
                        _paragraph(row.get("clientName", ""), styles["cell"]),
                        _paragraph(row.get("matterName", ""), styles["cell"]),
                        _paragraph(row.get("description", ""), styles["cell"]),
                        _paragraph(_hours(row.get("hours", 0.0)), styles["cellRight"]),
                        _paragraph(_money(row.get("grossToClient", 0.0)), styles["cellRight"]),
                        _paragraph(row.get("status", ""), styles["cell"]),
                    ]
                )
            span_empty = False
        else:
            data.append([_paragraph("No detail rows returned.", styles["muted"])] + [""] * 6)
            span_empty = True
        widths = [0.09, 0.15, 0.14, 0.28, 0.09, 0.12, 0.13]
        story.append(Table(data, colWidths=[available_width * w for w in widths], repeatRows=1, style=_table_style(span_empty=span_empty)))
        story.append(Spacer(1, 0.16 * inch))

    if config.get("summary"):
        story.append(_section_title("Summary by Matter", styles))
        headers = ["Matter", "Client", "Entries", "Hours", "Gross"]
        data = [[_paragraph(h, styles["tableHeader"]) for h in headers]]
        summary_rows = payload.get("summaryRows", []) or []
        if summary_rows:
            for row in summary_rows:
                data.append(
                    [
                        _paragraph(row.get("matterName", ""), styles["cell"]),
                        _paragraph(row.get("clientName", ""), styles["cell"]),
                        _paragraph(int(row.get("entryCount", 0) or 0), styles["cellRight"]),
                        _paragraph(_hours(row.get("totalHours", 0.0)), styles["cellRight"]),
                        _paragraph(_money(row.get("totalGrossToClient", 0.0)), styles["cellRight"]),
                    ]
                )
            span_empty = False
        else:
            data.append([_paragraph("No summary rows returned.", styles["muted"])] + [""] * 4)
            span_empty = True
        widths = [0.34, 0.30, 0.12, 0.12, 0.12]
        story.append(Table(data, colWidths=[available_width * w for w in widths], repeatRows=1, style=_table_style(span_empty=span_empty)))
        story.append(Spacer(1, 0.16 * inch))

    if config.get("aggregate"):
        story.append(_section_title("Aggregate Summary", styles))
        totals = payload.get("totals", {}) or {}
        gross = float(totals.get("totalGrossToClient", 0.0) or 0.0)
        hst_rate = float(config.get("hstRate", 13.0) or 13.0)
        hst = gross * (hst_rate / 100.0)
        data = [
            [_paragraph("Entries", styles["tableHeader"]), _paragraph(len(payload.get("rows", []) or []), styles["cellRight"])],
            [_paragraph("Hours", styles["tableHeader"]), _paragraph(_hours(totals.get("totalHours", 0.0)), styles["cellRight"])],
            [_paragraph("Gross (pre-HST)", styles["tableHeader"]), _paragraph(_money(gross), styles["cellRight"])],
            [_paragraph(f"HST ({hst_rate:.1f}%)", styles["tableHeader"]), _paragraph(_money(hst), styles["cellRight"])],
            [_paragraph("Total", styles["tableHeader"]), _paragraph(_money(gross + hst), styles["cellRight"])],
        ]
        story.append(Table(data, colWidths=[available_width * 0.50, available_width * 0.50], style=_table_style(header=False)))
        story.append(Spacer(1, 0.16 * inch))

    if config.get("selections"):
        story.append(_section_title("Report Selections", styles))
        filters = payload.get("filters", {}) or {}
        sort_dir = "Ascending" if payload.get("sortAscending") else "Descending"
        sections = []
        if config.get("detail"):
            sections.append("Detail")
        if config.get("summary"):
            sections.append("Summary")
        if config.get("aggregate"):
            sections.append("Aggregate")
        rows = [
            ("Requested by", config.get("firmAttorney", config.get("requestedBy", ""))),
            ("Finished", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Date Range", f"{filters.get('fromDate', '')} to {filters.get('toDate', '')}"),
            ("Status Scope", filters.get("statusMode", "")),
            ("Client Filter", filters.get("clientFilter") or "All Clients"),
            ("Matter Filter", filters.get("matterFilter") or "All Matters"),
            ("Search Term", filters.get("query") or "(none)"),
            ("Sort Order", f"{payload.get('sortKey', 'date')} ({sort_dir})"),
            ("Sections", ", ".join(sections) if sections else "(none)"),
            ("HST Rate", f"{config.get('hstRate', 13.0)}%"),
        ]
        data = [[_paragraph(label, styles["tableHeader"]), _paragraph(value, styles["cell"])] for label, value in rows]
        story.append(Table(data, colWidths=[available_width * 0.30, available_width * 0.70], style=_table_style(header=False)))

    if not story:
        story.append(Paragraph("No report sections selected.", styles["muted"]))

    return story


def _styles():
    base = getSampleStyleSheet()
    return {
        "sectionTitle": ParagraphStyle(
            "DocketSectionTitle",
            parent=base["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#1f2a44"),
            spaceAfter=5,
        ),
        "tableHeader": ParagraphStyle(
            "DocketTableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=8.5,
            textColor=colors.HexColor("#1f2a44"),
        ),
        "cell": ParagraphStyle(
            "DocketCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=8.4,
            textColor=colors.HexColor("#111827"),
        ),
        "cellRight": ParagraphStyle(
            "DocketCellRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=8.4,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#111827"),
        ),
        "muted": ParagraphStyle(
            "DocketMuted",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.4,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6b7280"),
        ),
    }


def generate_docket_pdf(payload, export_dir, logo_path):
    os.makedirs(export_dir, exist_ok=True)
    payload = dict(payload or {})
    config = dict(payload.get("config", {}) or {})

    orientation = str(config.get("orientation") or config.get("pageOrientation") or "").strip().lower()
    if orientation == "portrait":
        page_size = letter
    elif orientation == "landscape":
        page_size = landscape(letter)
    else:
        page_size = landscape(letter) if config.get("detail") else letter
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = os.path.join(export_dir, f"DocketActivityReport_{stamp}.pdf")

    doc = SimpleDocTemplate(
        filepath,
        pagesize=page_size,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=1.55 * inch,
        bottomMargin=0.62 * inch,
        title="Docket Activity Report",
        author=_safe_text(config.get("firmName") or "CSPM"),
    )
    styles = _styles()
    story = _build_story(payload, styles, doc.width)
    draw_page = lambda canvas, document: _draw_header_footer(canvas, document, config, logo_path)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return filepath
