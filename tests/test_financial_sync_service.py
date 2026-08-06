from __future__ import annotations

from decimal import Decimal

from services.financial_sync_service import FinancialSyncService


def test_canonical_source_receivables_consolidates_legacy_duplicates_and_credit_signs() -> None:
    source = {
        "Receivables": [
            # Old source contains two rows for this invoice; the one with a
            # ledger-supported $47 balance is the authoritative one.
            {"InvoiceNum": "25-0051", "Total_Invoiced": 0, "Amount_Paid": 0, "Credits/Adj": 47, "Balance_Due": 47, "Status": "PENDING"},
            {"InvoiceNum": "25-0051", "Total_Invoiced": 47, "Amount_Paid": 0, "Credits/Adj": 47, "Balance_Due": 94, "Status": "PENDING"},
            # Source credits use the inverse of CSPM's storage convention.
            {"InvoiceNum": "26-0074", "Total_Invoiced": 5474.86, "Amount_Paid": 5313.50, "Credits/Adj": -161.36, "Balance_Due": 0, "Status": "PAID"},
            # Footer must never become a receivable.
            {"InvoiceNum": "Total", "Total_Invoiced": 999, "Balance_Due": 999},
        ],
        "Ledger": [
            {"Reference": "25-0051", "Receivable": 47},
            {"Reference": "26-0074", "Receivable": 5474.86},
            {"Reference": "26-0074", "Collected": 5313.50, "Receivable": -5313.50},
            {"Reference": "26-0074", "Write Off": 161.36, "Receivable": -161.36},
        ],
        "Invoice Log": [
            {"Invoice #": "25-0051", "Aggregate Billed to Client": 47},
            {"Invoice #": "26-0074", "Aggregate Billed to Client": 5474.86},
        ],
    }

    rows, warnings = FinancialSyncService._canonical_source_receivables(source)
    by_invoice = {row["InvoiceNum"]: row for row in rows}

    assert set(by_invoice) == {"25-0051", "26-0074"}
    assert by_invoice["25-0051"]["Total_Invoiced"] == 47.0
    assert by_invoice["25-0051"]["Balance_Due"] == 47.0
    assert by_invoice["25-0051"]["Credits/Adj"] == 0.0
    assert by_invoice["26-0074"]["Balance_Due"] == 0.0
    assert by_invoice["26-0074"]["Credits/Adj"] == 161.36
    assert any("Consolidated 2" in warning for warning in warnings)


def test_source_productivity_treats_zero_hour_legacy_flat_fees_as_fees() -> None:
    metrics = FinancialSyncService._source_metrics({
        "Dockets": [
            {"Time (in hrs)": 0, "Hourly Rate/Flat Fee": 1500, "Amount to CS": 525},
            {"Time (in hrs)": 2, "Hourly Rate/Flat Fee": 100, "Amount to CS": 140},
        ],
        "Ledger": [],
        "Receivables": [],
    })

    assert Decimal(str(metrics["productivityHours"])) == Decimal("2.00")
    assert Decimal(str(metrics["productivityGross"])) == Decimal("725.00")
    assert Decimal(str(metrics["productivityNet"])) == Decimal("665.00")
