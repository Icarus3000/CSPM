from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from repositories.excel_repo import ExcelRepo


class _PaymentInvoiceFilterRepo:
    """Read-only repository double for Payment Entry's shared invoice list."""

    _money_round = ExcelRepo._money_round
    _payment_invoice_matter_contexts = ExcelRepo._payment_invoice_matter_contexts
    list_open_payment_invoices = ExcelRepo.list_open_payment_invoices

    def __init__(self) -> None:
        self.source_rows = [
            {
                "invoice": "26-0950",
                "date": "2026-07-01",
                "client": "Boundary Client",
                "billingClient": "Boundary Billing",
                "workClient": "Boundary Client",
                "status": "Open",
                "ageDays": 10,
                "bucketLabel": "0-30",
                "invoiceTotal": 1900.00,
                "paid": 900.00,
                "credits": 50.00,
                "balance": 950.00,
            },
            {
                "invoice": "26-1000",
                "date": "2026-07-02",
                "client": "Northstar Client",
                "billingClient": "Northstar Holdings",
                "workClient": "Northstar Client",
                "status": "Partial",
                "ageDays": 9,
                "bucketLabel": "0-30",
                "invoiceTotal": 2000.00,
                "paid": 900.00,
                "credits": 100.00,
                "balance": 1000.00,
            },
            {
                "invoice": "26-1050",
                "date": "2026-07-03",
                "client": "Acme Client",
                "billingClient": "Acme Billing",
                "workClient": "Acme Client",
                "status": "Unpaid",
                "ageDays": 8,
                "bucketLabel": "0-30",
                "invoiceTotal": 1050.00,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 1050.00,
            },
            {
                "invoice": "26-0949",
                "date": "2026-07-04",
                "client": None,
                "billingClient": None,
                "workClient": None,
                "status": "Open",
                "ageDays": 7,
                "bucketLabel": "0-30",
                "invoiceTotal": 949.99,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 949.99,
            },
            {
                "invoice": "26-1051",
                "date": "2026-07-05",
                "client": "Outside Client",
                "billingClient": "Outside Billing",
                "workClient": "Outside Client",
                "status": "Open",
                "ageDays": 6,
                "bucketLabel": "0-30",
                "invoiceTotal": 1050.01,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 1050.01,
            },
            {
                "invoice": "26-2000",
                "date": "2026-07-06",
                "client": "Paid Client",
                "billingClient": "Paid Billing",
                "workClient": "Paid Client",
                "status": "Paid",
                "ageDays": 5,
                "bucketLabel": "0-30",
                "invoiceTotal": 1000.00,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 1000.00,
            },
            {
                "invoice": "26-2001",
                "date": "2026-07-07",
                "client": "Reversed Client",
                "billingClient": "Reversed Billing",
                "workClient": "Reversed Client",
                "status": "Reversed",
                "ageDays": 4,
                "bucketLabel": "0-30",
                "invoiceTotal": 1000.00,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 1000.00,
            },
            {
                "invoice": "26-2002",
                "date": "2026-07-08",
                "client": "Void Client",
                "billingClient": "Void Billing",
                "workClient": "Void Client",
                "status": "Voided",
                "ageDays": 3,
                "bucketLabel": "0-30",
                "invoiceTotal": 1000.00,
                "paid": 0.00,
                "credits": 0.00,
                "balance": 1000.00,
            },
        ]
        self.original_rows = deepcopy(self.source_rows)
        self.calls = []

    def ar_aging_report(self, payload):
        self.calls.append(dict(payload))
        return {"ok": True, "rows": deepcopy(self.source_rows)}

    def _canonical_ar_ledger(self, _payload):
        return {
            "ok": True,
            "events": [
                {
                    "invoice": "26-1000",
                    "workContexts": [{"matter": "Employment Advice"}],
                },
                {
                    "invoice": "26-1050",
                    "workContexts": [{"matterDescription": "Acquisition Review"}],
                },
            ],
        }


def _invoices(repo: _PaymentInvoiceFilterRepo, query: str) -> list[str]:
    return [row["invoice"] for row in repo.list_open_payment_invoices({"query": query})]


def test_payment_invoice_filtering_matches_all_supported_text_fields_and_preserves_order():
    repo = _PaymentInvoiceFilterRepo()

    assert _invoices(repo, "26-1000") == ["26-1000"]
    assert _invoices(repo, "north") == ["26-1000"]
    assert _invoices(repo, "MENT adv") == ["26-1000"]
    assert _invoices(repo, "holdings") == ["26-1000"]
    assert _invoices(repo, "  acQuIsItIon  ") == ["26-1050"]
    assert _invoices(repo, "") == ["26-0950", "26-1000", "26-1050", "26-0949", "26-1051"]
    assert all(call["query"] == "" for call in repo.calls)


def test_payment_invoice_filtering_uses_displayed_balance_with_decimal_inclusive_boundaries():
    expected = ["26-0950", "26-1000", "26-1050"]
    for amount_query in ("1000", "1,000", "$1,000", "1000.00", "$1,000.00"):
        assert _invoices(_PaymentInvoiceFilterRepo(), amount_query) == expected

    repo = _PaymentInvoiceFilterRepo()
    assert "26-0949" not in _invoices(repo, "1000")
    assert "26-1051" not in _invoices(repo, "1000")
    assert "26-1000" not in _invoices(repo, "2000")


def test_payment_invoice_filtering_handles_nulls_partial_currency_and_ineligible_rows_without_writes():
    repo = _PaymentInvoiceFilterRepo()

    assert _invoices(repo, "26-0949") == ["26-0949"]
    assert _invoices(repo, "$") == ["26-0950", "26-1000", "26-1050", "26-0949", "26-1051"]
    assert _invoices(repo, "1000.") == ["26-0950", "26-1000", "26-1050"]
    open_rows = repo.list_open_payment_invoices({})
    selected = next(row for row in open_rows if row["invoice"] == "26-1000")
    assert selected["credits"] == 100.00
    assert selected["balance"] == 1000.00
    assert {row["invoice"] for row in open_rows}.isdisjoint({"26-2000", "26-2001", "26-2002"})
    assert repo.source_rows == repo.original_rows
