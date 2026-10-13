"""Read-only synthetic coverage for statement status, invoice dates and cutoff."""

import sys
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo
from services import report_pdf_exporter


def _invoice(number, *, total=1000.0, paid=0.0, adjustment=0.0, balance=None,
             status="Unpaid", invoice_date="2026-04-01", client="Example Client"):
    return {
        sc.COL_RECV_INVOICE_NUM: number,
        sc.COL_RECV_DATE: invoice_date,
        sc.COL_RECV_CLIENT: client,
        sc.COL_RECV_TOTAL_INVOICED: total,
        sc.COL_RECV_AMOUNT_PAID: paid,
        sc.COL_RECV_CREDITS_ADJ: adjustment,
        sc.COL_RECV_BALANCE_DUE: total - paid - adjustment if balance is None else balance,
        sc.COL_RECV_STATUS: status,
    }


def _settlement(number, payment_date, *, payment=0.0, adjustment=0.0):
    return {
        sc.COL_LEDGER_REFERENCE: number,
        sc.COL_LEDGER_DATE: payment_date,
        sc.COL_LEDGER_COLLECTED: payment,
        sc.COL_LEDGER_WRITE_OFF: adjustment,
    }


class _MemoryStatementRepo:
    _money_round = ExcelRepo._money_round
    _parse_date_value = ExcelRepo._parse_date_value
    _client_parent_lookup = ExcelRepo._client_parent_lookup
    _canonical_ar_ledger = ExcelRepo._canonical_ar_ledger
    _statement_open_invoice_candidates = ExcelRepo._statement_open_invoice_candidates

    def __init__(self, invoices, settlements=()):
        self.tables = {
            "tblReceivables": invoices,
            "tblLedger": list(settlements),
        }

    def ensure_schema(self):
        pass

    def _read_table_rows(self, reference):
        return self.tables.get(reference.table, [])

    def _read_legacy_docket_rows(self):
        return []


def _report(repo, **filters):
    return ExcelRepo.statement_of_account_report(repo, {
        "billingClient": "Example Client",
        "asOfDate": "2026-08-31",
        **filters,
    })


def test_paid_and_all_scopes_include_settled_invoices_with_zero_due():
    repo = _MemoryStatementRepo([
        _invoice("26-0001"),
        _invoice("26-0002", paid=400, status="Partially Paid"),
        _invoice("26-0003", paid=1000, status="Paid"),
    ])
    open_report = _report(repo)
    paid_report = _report(repo, invoiceStatus="paid")
    all_report = _report(repo, invoiceStatus="all")

    assert [row["invoice"] for row in open_report["rows"]] == ["26-0001", "26-0002"]
    assert [row["status"] for row in open_report["rows"]] == ["Unpaid", "Partially Paid"]
    assert paid_report["summary"]["amountDue"] == 0
    assert paid_report["rows"][0]["status"] == "Paid"
    assert paid_report["rows"][0]["statusKey"] == "paid"
    assert paid_report["rows"][0]["balanceDueFormatted"] == "$0.00"
    assert paid_report["sections"][1]["title"] == "Paid Invoices"
    assert "Paid invoices only" in paid_report["filterSummary"]
    assert all_report["summary"]["amountDue"] == 1600
    assert len(all_report["rows"]) == 3
    assert "All invoice dates" in all_report["filterSummary"]


def test_invoice_date_range_is_inclusive_and_does_not_filter_payment_dates():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=300, invoice_date="2026-04-01"),
        _invoice("26-0002", invoice_date="2026-04-30"),
        _invoice("26-0003", invoice_date="2026-03-31"),
        _invoice("26-0004", invoice_date="2026-05-01"),
    ], [_settlement("26-0001", "2026-06-20", payment=300)])
    result = _report(repo, invoiceDateFrom="2026-04-01", invoiceDateTo="2026-04-30")

    assert [row["invoice"] for row in result["rows"]] == ["26-0001", "26-0002"]
    assert result["rows"][0]["paidCredits"] == 300
    assert result["rows"][0]["balanceDue"] == 700
    assert result["summary"]["amountDue"] == 1700
    assert result["exportPayload"]["statement"]["invoiceDateFrom"] == "2026-04-01"
    assert "Invoice dates: 2026-04-01 to 2026-04-30" in result["filterSummary"]


def test_statement_cutoff_restores_later_payment_for_a_currently_paid_invoice():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=1000, status="Paid"),
    ], [
        _settlement("26-0001", "2026-06-15", payment=250),
        _settlement("26-0001", "2026-07-15", payment=750),
    ])
    historical = _report(repo, asOfDate="2026-06-30")
    settled = _report(repo, asOfDate="2026-07-31", invoiceStatus="paid")

    assert historical["rows"][0]["status"] == "Partially Paid"
    assert historical["rows"][0]["paidCredits"] == 250
    assert historical["rows"][0]["balanceDue"] == 750
    assert settled["rows"][0]["paidCredits"] == 1000
    assert settled["rows"][0]["balanceDue"] == 0
    assert _report(repo, asOfDate="2026-06-30", invoiceStatus="paid")["rows"] == []


def test_statement_cutoff_restores_later_adjustment_and_keeps_legacy_rounding_private():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=500, adjustment=100.01),
    ], [
        _settlement("26-0001", "2026-06-15", payment=500),
        _settlement("26-0001", "2026-07-15", adjustment=100),
    ])
    historical = _report(repo, asOfDate="2026-06-30")
    current = _report(repo)

    assert historical["rows"][0]["invoiceTotal"] == 999.99
    assert historical["rows"][0]["paidCredits"] == 500
    assert historical["rows"][0]["balanceDue"] == 499.99
    assert current["rows"][0]["invoiceTotal"] == 899.99
    assert current["rows"][0]["paidCredits"] == 500
    assert current["rows"][0]["balanceDue"] == 399.99


def test_missing_current_balance_fields_use_complete_dated_ledger_at_cutoff():
    invoice = _invoice("26-0001", paid=1000, status="Paid")
    invoice.pop(sc.COL_RECV_BALANCE_DUE)
    repo = _MemoryStatementRepo([invoice], [
        _settlement("26-0001", "2026-06-15", payment=1000),
    ])

    historical = _report(repo, asOfDate="2026-05-31")
    current = _report(repo, invoiceStatus="paid")
    assert historical["rows"][0]["balanceDue"] == 1000
    assert current["rows"][0]["balanceDue"] == 0


@pytest.mark.parametrize("complete_snapshot", [True, False])
def test_signed_payment_reversal_restores_historical_paid_and_current_open(complete_snapshot):
    invoice = _invoice("26-0001")
    if not complete_snapshot:
        invoice.pop(sc.COL_RECV_BALANCE_DUE)
    repo = _MemoryStatementRepo([invoice], [
        _settlement("26-0001", "2026-06-15", payment=1000),
        _settlement("26-0001", "2026-07-15", payment=-1000),
    ])

    historical = _report(repo, asOfDate="2026-06-30", invoiceStatus="paid")
    current = _report(repo)
    assert historical["rows"][0]["paidCredits"] == 1000
    assert historical["rows"][0]["balanceDue"] == 0
    assert current["rows"][0]["paidCredits"] == 0
    assert current["rows"][0]["balanceDue"] == 1000
    assert current["rows"][0]["status"] == "Unpaid"


def test_signed_adjustment_reversal_restores_historical_adjusted_total():
    repo = _MemoryStatementRepo([_invoice("26-0001")], [
        _settlement("26-0001", "2026-06-15", adjustment=100),
        _settlement("26-0001", "2026-07-15", adjustment=-100),
    ])
    historical = _report(repo, asOfDate="2026-06-30")
    current = _report(repo)
    assert historical["rows"][0]["invoiceTotal"] == 900
    assert historical["rows"][0]["balanceDue"] == 900
    assert historical["rows"][0]["paidCredits"] == 0
    assert historical["rows"][0]["status"] == "Unpaid"
    assert current["rows"][0]["invoiceTotal"] == 1000


def test_fallback_credit_only_adjustment_is_not_classified_as_a_partial_payment():
    invoice = _invoice("26-0001", adjustment=100)
    invoice.pop(sc.COL_RECV_BALANCE_DUE)
    repo = _MemoryStatementRepo([invoice], [
        _settlement("26-0001", "2026-06-15", adjustment=100),
    ])
    row = _report(repo)["rows"][0]
    assert row["paidCredits"] == 100
    assert row["balanceDue"] == 900
    assert row["status"] == "Unpaid"


@pytest.mark.parametrize("filter_name, filter_value, expected", [
    ("invoiceDateFrom", "2026-04-30", ["26-0002", "26-0003"]),
    ("invoiceDateTo", "2026-04-01", ["26-0001"]),
])
def test_open_ended_invoice_date_filters(filter_name, filter_value, expected):
    repo = _MemoryStatementRepo([
        _invoice("26-0001", invoice_date="2026-04-01"),
        _invoice("26-0002", invoice_date="2026-04-30"),
        _invoice("26-0003", invoice_date="2026-05-01"),
    ])
    result = _report(repo, **{filter_name: filter_value})
    assert [row["invoice"] for row in result["rows"]] == expected


def test_legacy_event_range_filters_do_not_truncate_statement_payment_history():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=250, invoice_date="2026-04-01"),
    ], [_settlement("26-0001", "2026-05-01", payment=250)])

    result = _report(repo, startDate="2026-06-01", fromDate="2026-06-01", endDate="2026-04-15")
    assert result["rows"][0]["balanceDue"] == 750
    assert result["asOfDate"] == "2026-08-31"


@pytest.mark.parametrize("filters, message", [
    ({"invoiceDateFrom": "invalid"}, "Invoice date From"),
    ({"invoiceDateTo": "2026-02-31"}, "Invoice date To"),
    ({"invoiceDateFrom": "2026-08-01", "invoiceDateTo": "2026-07-01"}, "on or before"),
    ({"asOfDate": "invalid"}, "Statement Date"),
    ({"invoiceStatus": "reversed"}, "Open, Paid, or All"),
])
def test_invalid_statement_filters_return_actionable_messages(filters, message):
    result = _report(_MemoryStatementRepo([]), **filters)
    assert result["ok"] is False
    assert message in result["message"]


@pytest.mark.parametrize("status", ["Void", "Voided", "Cancelled", "Canceled", "Reversed", "Superseded", "Draft"])
def test_all_scope_excludes_invalid_invoice_lifecycle_records(status):
    repo = _MemoryStatementRepo([_invoice("26-0001", paid=1000, status=status)])
    assert _report(repo, invoiceStatus="all")["rows"] == []
    assert ExcelRepo.list_statement_billing_clients(repo) == []


def test_paid_label_with_unsettled_current_balance_does_not_create_a_paid_invoice():
    repo = _MemoryStatementRepo([_invoice("26-0001", status="Paid")])
    assert _report(repo, invoiceStatus="all")["rows"] == []
    assert ExcelRepo.list_statement_billing_clients(repo) == []


def test_selection_cannot_reintroduce_invoices_outside_current_status_and_date_filters():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=1000, status="Paid"),
        _invoice("26-0002", invoice_date="2026-05-01"),
        _invoice("26-0003", invoice_date="2026-04-01"),
    ])
    result = _report(repo, invoiceDateTo="2026-04-30", selectedInvoiceNumbers=["26-0001", "26-0002", "26-0003"])
    empty = _report(repo, selectedInvoiceNumbers=[])

    assert result["selectedInvoiceNumbers"] == ["26-0003"]
    assert result["summary"]["amountDue"] == 1000
    assert empty["rows"] == []
    assert empty["summary"]["amountDue"] == 0
    assert len(empty["availableInvoices"]) == 2


def test_billing_client_choices_include_paid_only_accounts_and_exclude_vendor_artifacts():
    repo = _MemoryStatementRepo([
        _invoice("26-0001", paid=1000, status="Paid", client="Paid Client"),
        _invoice("26-0002", client="Open Client"),
        _invoice("26-0003", paid=500, client="Open Client"),
        _invoice("SUPPLIER-123", client="Expense Vendor"),
        _invoice("26-0004", total=0, balance=0, client="Empty Artifact"),
    ])
    choices = ExcelRepo.list_statement_billing_clients(repo)
    assert [row["name"] for row in choices] == ["Open Client", "Paid Client"]
    assert choices[0]["invoiceCount"] == 2
    assert choices[0]["openInvoiceCount"] == 2
    assert choices[0]["openBalance"] == 1500
    assert choices[1]["invoiceCount"] == 1
    assert choices[1]["paidInvoiceCount"] == 1
    assert choices[1]["openInvoiceCount"] == 0


@pytest.mark.parametrize("invalid_balance", [None, "", "invalid", "NaN", "Infinity"])
def test_missing_or_invalid_current_balance_does_not_create_a_paid_client_choice(invalid_balance):
    invoice = _invoice("26-0001", status="Paid")
    invoice[sc.COL_RECV_BALANCE_DUE] = invalid_balance
    repo = _MemoryStatementRepo([invoice])
    assert ExcelRepo.list_statement_billing_clients(repo) == []
    assert _report(repo, invoiceStatus="paid")["rows"] == []


def test_paid_statement_pdf_uses_accurate_section_label_without_changing_header(tmp_path, monkeypatch):
    titles = []
    section_title = report_pdf_exporter._section_title
    header_configs = []

    def capture_title(title, styles):
        titles.append(title)
        return section_title(title, styles)

    def capture_header(_canvas, _document, config, _logo_path):
        header_configs.append(config)

    monkeypatch.setattr(report_pdf_exporter, "_section_title", capture_title)
    monkeypatch.setattr(report_pdf_exporter, "_draw_header_footer", capture_header)
    result = _report(_MemoryStatementRepo([_invoice("26-0001", paid=1000, status="Paid")]),
                     invoiceStatus="paid", invoiceDateFrom="2026-04-01", invoiceDateTo="2026-04-30")
    pdf = report_pdf_exporter.generate_statement_of_account_pdf({
        **result,
        "statement": result["exportPayload"]["statement"],
    }, str(tmp_path), "")

    assert Path(pdf).read_bytes().startswith(b"%PDF")
    assert "Paid Invoices" in titles
    assert "Outstanding Invoices" not in titles
    assert header_configs[0]["headerLogoWidth"] == 64.8
    assert header_configs[0]["headerLogoHeight"] == 41.04
    assert header_configs[0]["headerLogoBottomAligned"] is True
