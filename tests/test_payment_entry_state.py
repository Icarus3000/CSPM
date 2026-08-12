from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYMENT_VIEW = (ROOT / "src" / "qml" / "views" / "PaymentEntryView.qml").read_text(
    encoding="utf-8"
)
HOST_VIEW = (ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(
    encoding="utf-8"
)


def test_payment_entry_retains_invoice_selection_across_list_refreshes():
    assert 'property string selectedInvoiceKey: ""' in PAYMENT_VIEW
    assert '"selectedInvoiceNum": selectedInvoiceNumber()' in PAYMENT_VIEW
    assert "selectedInvoiceKey = _clean(selectedInvoice.invoice)" in PAYMENT_VIEW
    assert "selectedInvoiceIndex = -1\n            }" in PAYMENT_VIEW
    assert "selectedInvoice = ({})\n                    historyRows = []" not in PAYMENT_VIEW


def test_payment_entry_restores_every_in_progress_financial_field():
    assert "state.invoiceNum || state.selectedInvoiceNum || selectedInvoice.invoice" in PAYMENT_VIEW
    assert "payload.adjustmentAmount !== undefined" in PAYMENT_VIEW
    assert "adjustmentReasonInput.text = _clean(payload.adjustmentReason)" in PAYMENT_VIEW


def test_payment_entry_state_is_preserved_by_its_parent_workspace():
    assert 'paymentEntryView && typeof paymentEntryView.snapshotState === "function"' in HOST_VIEW
    assert "var paymentState = paymentEntryView.snapshotState()" in HOST_VIEW
