"""Continuation overlays preserve invoice content and quiet client/date chrome.

Real ReportLab pages pass through the production PDF merge. Text visitors
inspect header/body/footer regions independently; no WebEngine is launched.
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))

from backend.controllers.billing_controller import BillingController
from services.invoice_document_service import InvoiceDocumentService


GRAY = (148 / 255, 163 / 255, 184 / 255)
FOOTER = "CORY SCHNEIDER LAW OFFICE  |  INVOICE 26-9991"
FIRST_HEADER = "Original first-page branding and invoice details"


def _fragments(page):
    """Return text with its effective page position, face, size and fill."""
    fragments = []
    fill = (0.0, 0.0, 0.0)
    states = []

    def operand(operator, operands, _cm, _tm):
        nonlocal fill
        if operator == b"q":
            states.append(fill)
        elif operator == b"Q" and states:
            fill = states.pop()
        elif operator == b"rg":
            fill = tuple(float(value) for value in operands)
        elif operator == b"g":
            fill = (float(operands[0]),) * 3

    def text(value, cm, tm, font, size):
        value = value.strip()
        if not value:
            return
        fragments.append({
            "text": value,
            "x": float(tm[4] * cm[0] + tm[5] * cm[2] + cm[4]),
            "y": float(tm[4] * cm[1] + tm[5] * cm[3] + cm[5]),
            "font": str((font or {}).get("/BaseFont", "")),
            "size": float(size), "fill": fill,
        })

    page.extract_text(visitor_operand_before=operand, visitor_text=text)
    return fragments


def _region(page, lower, upper):
    return [part for part in _fragments(page) if lower <= part["y"] <= upper]


def _text(parts):
    return " ".join(part["text"] for part in parts)


def _source_pdf(path):
    document = canvas.Canvas(str(path), pagesize=letter)
    for index in range(3):
        if index == 0:
            document.setFont("Helvetica-Bold", 16)
            document.setFillColorRGB(0.1, 0.15, 0.2)
            document.drawString(57.6, 756, FIRST_HEADER)
        document.setFillColorRGB(0.1, 0.1, 0.1)
        document.setFont("Helvetica", 11)
        document.drawString(57.6, 620, f"ORIGINAL BODY PAGE {index + 1}")
        document.drawString(57.6, 580, "Services and preserved totals: $1,234.50")
        document.setFont("Helvetica-Bold", 8)
        document.setFillColorRGB(0.25, 0.3, 0.35)
        document.drawString(57.6, 34, FOOTER)
        document.showPage()
    document.save()


def _merge(tmp_path, html):
    source = tmp_path / "first-pass.pdf"
    destination = tmp_path / "invoice.pdf"
    _source_pdf(source)
    original = PdfReader(source)
    original_body = [_region(page, 60, 700) for page in original.pages]
    original_footer = [[part for part in _region(page, 0, 60) if part["text"] == FOOTER]
                       for page in original.pages]
    original_first_header = _region(original.pages[0], 730, 790)
    result = BillingController._merge_pdf_export_impl(str(source), str(destination), html)
    assert result == {"path": str(destination), "pages": 3}
    assert not source.exists()
    rendered = PdfReader(destination)
    assert len(rendered.pages) == 3
    for index, page in enumerate(rendered.pages):
        assert tuple(float(value) for value in page.mediabox) == (0, 0, *letter)
        assert _region(page, 60, 700) == original_body[index]
        assert [part for part in _region(page, 0, 60) if part["text"] == FOOTER] == original_footer[index]
        label = f"PAGE {index + 1} OF 3"
        counters = [part for part in _region(page, 0, 60) if part["text"] == label]
        assert len(counters) == 1
        assert counters[0]["y"] == 34
        assert counters[0]["x"] + stringWidth(label, "Helvetica", 8) == pytest.approx(554.4, abs=0.001)
        assert counters[0]["font"] == "/Helvetica"
        assert counters[0]["size"] == 8
    assert _region(rendered.pages[0], 730, 790) == original_first_header
    return rendered


def _metadata(client, date, invoice="26-9991"):
    return ('<meta name="invoice-meta" '
            f'data-client="{escape(client, quote=True)}" '
            f'data-date="{escape(date, quote=True)}" '
            f'data-invoice="{escape(invoice, quote=True)}">')


def _assert_quiet_header(parts):
    for part in parts:
        assert part["font"] == "/Helvetica"
        assert part["size"] == 8.5
        assert part["fill"] == pytest.approx(GRAY, abs=1e-6)
        assert part["y"] == 756
    combined = _text(parts)
    assert "CORY SCHNEIDER" not in combined
    assert "INVOICE" not in combined
    assert "26-9991" not in combined


def test_continuation_header_contains_only_client_and_date_with_original_footer(tmp_path):
    client = 'Élodie & François "Test" Ltd.'
    date = 'October 15, 2026'
    invoice = _merge(tmp_path, _metadata(client, date))
    for page in invoice.pages[1:]:
        parts = _region(page, 730, 790)
        assert [part["text"] for part in parts] == [client, date]
        _assert_quiet_header(parts)
        assert parts[0]["x"] == pytest.approx(57.6)
        assert parts[1]["x"] + stringWidth(date, "Helvetica", 8.5) == pytest.approx(554.4, abs=0.001)


def test_long_client_ellipsizes_at_same_font_size_without_meeting_date(tmp_path):
    client = 'A & B "International Holdings" ' * 24
    date = 'Thursday, October 15, 2026'
    invoice = _merge(tmp_path, _metadata(client, date))
    for page in invoice.pages[1:]:
        parts = _region(page, 730, 790)
        assert len(parts) == 2
        _assert_quiet_header(parts)
        client_part, date_part = parts
        assert date_part["text"] == date
        assert client_part["text"].endswith("…")
        assert client.startswith(client_part["text"][:-1])
        assert client_part["x"] + stringWidth(client_part["text"], "Helvetica", 8.5) <= date_part["x"] - 16 + 0.001


def test_literal_entity_text_is_decoded_only_once(tmp_path):
    client = 'Literal &amp; Partners "North"'
    invoice = _merge(tmp_path, _metadata(client, "October 15, 2026"))
    for page in invoice.pages[1:]:
        assert _region(page, 730, 790)[0]["text"] == client


@pytest.mark.parametrize("html,expected", [
    ("<html><body>No metadata</body></html>", []),
    ('<meta data-client="" data-date="">', []),
    ('<meta data-client="Only &amp; Client">', ["Only & Client"]),
    ('<meta data-date="October 15, 2026">', ["October 15, 2026"]),
])
def test_missing_metadata_is_safe_and_preserves_content(tmp_path, html, expected):
    invoice = _merge(tmp_path, html)
    for page in invoice.pages[1:]:
        parts = _region(page, 730, 790)
        assert [part["text"] for part in parts] == expected
        _assert_quiet_header(parts)


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "invoice-meta":
            self.tags.append(attributes)


def test_a2_template_escapes_metadata_and_merge_decodes_it_once(tmp_path):
    values = {"billing_client_name": 'A & B "Holdings" <East> Ltd.',
              "invoice_number_raw": '26-"99"&<X>', "date": 'October 15 & "2026"'}
    payload = {**values, "total_due": 0, "total_fees": 0, "total_tax": 0,
               "discount_amount": 0, "agency_split_amount": 0, "disbursement_total": 0,
               "net_professional_fees": 0, "total_hours": 0}
    html = InvoiceDocumentService(str(ROOT / "src/templates/invoices")).generate_html("Concept_A2", payload)
    parser = _MetadataParser()
    parser.feed(html)
    assert parser.tags == [{"name": "invoice-meta", "data-client": values["billing_client_name"],
                            "data-invoice": values["invoice_number_raw"], "data-date": values["date"]}]
    raw = re.search(r'<meta name="invoice-meta"[^>]*>', html).group()
    assert "&amp;" in raw and "&lt;" in raw
    assert '"Holdings"' not in raw
    invoice = _merge(tmp_path, html)
    for page in invoice.pages[1:]:
        parts = _region(page, 730, 790)
        assert [part["text"] for part in parts] == [values["billing_client_name"], values["date"]]
        _assert_quiet_header(parts)
