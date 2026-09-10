from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYMENT_VIEW = (ROOT / "src" / "qml" / "views" / "PaymentEntryView.qml").read_text(
    encoding="utf-8"
)
HOST_VIEW = (ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(
    encoding="utf-8"
)
QUICK_PAYMENT_DIALOG = (
    ROOT / "src" / "qml" / "views" / "QuickPaymentDialog.qml"
).read_text(encoding="utf-8")


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


def test_routed_payment_prefills_the_resolved_balance_and_includes_deposit_account():
    assert 'property string _pendingFullAmountInvoiceKey: ""' in PAYMENT_VIEW
    assert "function _applyPendingFullAmountIfResolved()" in PAYMENT_VIEW
    assert "_applyPendingFullAmountIfResolved()" in PAYMENT_VIEW
    assert '"depositAccount": _clean(depositAccountCode)' in PAYMENT_VIEW
    assert 'label: "Deposit account"' in PAYMENT_VIEW
    assert "root.loadDepositAccounts()" in PAYMENT_VIEW


def test_payment_entry_state_is_preserved_by_its_parent_workspace():
    assert 'paymentEntryView && typeof paymentEntryView.snapshotState === "function"' in HOST_VIEW
    assert "var paymentState = paymentEntryView.snapshotState()" in HOST_VIEW


def test_payment_entry_exposes_exact_party_filters_and_preserves_them_in_state():
    assert 'fullModel: ["All open invoices", "Client", "Billing client"]' in PAYMENT_VIEW
    assert '"partyType": partyFilterMode' in PAYMENT_VIEW
    assert '"partyValue": partyFilterValue' in PAYMENT_VIEW
    assert '"partyFilterMode": partyFilterMode' in PAYMENT_VIEW
    assert '"partyFilterValue": partyFilterValue' in PAYMENT_VIEW


def test_each_open_invoice_can_launch_the_full_quick_payment_dialog():
    assert 'text: "Add Payment"' in PAYMENT_VIEW
    assert "quickPaymentDialog.openForInvoice(row)" in PAYMENT_VIEW
    assert "root.runQuickPayment(payload)" in PAYMENT_VIEW
    assert 'text: "Record Payment"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Payment ($)"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Adjustment ($)"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Adjustment reason"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Mode"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Method"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Deposit account"' in QUICK_PAYMENT_DIALOG
    assert 'label: "Reference / Cheque #"' in QUICK_PAYMENT_DIALOG
    assert 'text: dialog.postInProgress ? "Posting..." : "Post Payment"' in QUICK_PAYMENT_DIALOG
