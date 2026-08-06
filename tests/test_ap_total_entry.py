from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from domain.ap_lifecycle import money
from services.ap_orchestration_service import APOrchestrationService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeAPRepository:
    def __init__(self) -> None:
        self.created: dict | None = None

    def get_bill(self, _bill_id: str):
        return None

    def create_bill(self, bill: dict) -> dict:
        self.created = dict(bill)
        return dict(bill)


class _FakeExpenseGateway:
    def __init__(self) -> None:
        self.saved: dict | None = None

    def save_ap_expense(self, payload: dict) -> dict:
        self.saved = dict(payload)
        return {"ok": True, "transactionId": payload["transactionId"]}


def test_taxable_total_entry_derives_subtotal_and_hst_exactly() -> None:
    normalized = APOrchestrationService.normalize_bill_amounts(
        {"Total": "5677.41", "TaxExempt": False, "AmountEntryMode": "total"}
    )

    assert money(normalized["Subtotal"]) == Decimal("5024.26")
    assert money(normalized["TaxAmount"]) == Decimal("653.15")
    assert money(normalized["Subtotal"]) + money(normalized["TaxAmount"]) == money(normalized["Total"])


def test_tax_exempt_total_entry_derives_zero_tax() -> None:
    normalized = APOrchestrationService.normalize_bill_amounts(
        {"Total": "100.00", "TaxExempt": True, "AmountEntryMode": "total"}
    )

    assert money(normalized["Subtotal"]) == Decimal("100.00")
    assert money(normalized["TaxAmount"]) == Decimal("0.00")


def test_create_bill_uses_the_total_entry_breakdown_for_both_records() -> None:
    repository = _FakeAPRepository()
    gateway = _FakeExpenseGateway()
    service = APOrchestrationService(repository, gateway)

    service.create_bill(
        {
            "APBillID": "APB-TOTAL-1",
            "Vendor": "LIHDC Professional Corporation",
            "VendorInvoiceNumber": "Settlement-2026-07-01",
            "InvoiceDate": "2026-07-01",
            "Total": "5677.41",
            "TaxExempt": False,
            "AmountEntryMode": "total",
        }
    )

    assert repository.created is not None
    assert gateway.saved is not None
    assert money(repository.created["Subtotal"]) == Decimal("5024.26")
    assert money(repository.created["TaxAmount"]) == Decimal("653.15")
    assert money(gateway.saved["amount"]) == Decimal("5677.41")
    assert money(gateway.saved["taxAmount"]) == Decimal("653.15")


def test_setoff_uses_a_receivable_selection_workflow_not_free_text() -> None:
    qml = (PROJECT_ROOT / "src" / "qml" / "views" / "AccountsPayableView.qml").read_text(
        encoding="utf-8"
    )

    assert "id: setoffAllocationDialog" in qml
    assert "Choose receivables to set off" in qml
    assert "listOpenPaymentInvoices" in qml
    assert "Set-off amount" in qml
    assert "function validateSetoffAllocations()" in qml
    assert "id: setoffAllocationsField" not in qml
    assert "ScrollBar.vertical.policy: ScrollBar.AsNeeded" in qml
