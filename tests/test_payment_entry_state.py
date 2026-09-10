from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYMENT_VIEW = (ROOT / "src" / "qml" / "views" / "PaymentEntryView.qml").read_text(
    encoding="utf-8"
)
HOST_VIEW = (ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(
    encoding="utf-8"
)
COLLECTION_DIALOG = (
    ROOT / "src" / "qml" / "views" / "BillingClientARCollectionDialog.qml"
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


def test_payment_entry_launches_billing_client_ar_collection_workflow():
    assert 'text: "Collect billing-client A/R"' in PAYMENT_VIEW
    assert 'text: "Collect A/R"' in PAYMENT_VIEW
    assert "billingClientCollectionDialog.openForBillingClient(preferred)" in PAYMENT_VIEW
    assert "root.runBillingClientReceipt(payload)" in PAYMENT_VIEW
    assert 'text: "Billing Client A/R Collection"' in COLLECTION_DIALOG
    assert 'label: "Billing client"' in COLLECTION_DIALOG
    assert 'label: "Amount received ($)"' in COLLECTION_DIALOG
    assert 'label: "Payment method"' in COLLECTION_DIALOG
    assert 'label: "General deposit account"' in COLLECTION_DIALOG
    assert 'label: "Reference / Cheque #"' in COLLECTION_DIALOG
    assert '"Allocate shown oldest first" : "Allocate oldest first"' in COLLECTION_DIALOG
    assert 'text: dialog.postInProgress ? "Posting..." : "Post Received Payment"' in COLLECTION_DIALOG
    assert '"allocations": allocations' in COLLECTION_DIALOG
    assert "Allocated total must exactly equal the amount received." in COLLECTION_DIALOG
    assert "trust receipts and trust-to-general transfers are not implemented" in COLLECTION_DIALOG


def test_billing_client_receipt_uses_a_dedicated_async_controller_signal():
    controller = (
        ROOT / "src" / "python" / "backend" / "controllers" / "docketing_controller.py"
    ).read_text(encoding="utf-8")
    assert "billingClientReceiptSaveFinished = Signal(dict)" in controller
    assert "def postBillingClientReceipt(self, payload):" in controller
    assert "self._excel_repo.post_billing_client_receipt" in controller
    assert "function onBillingClientReceiptSaveFinished(result)" in PAYMENT_VIEW


def test_collection_filter_targets_invoice_client_or_matter_and_keeps_allocations_stable():
    assert 'label: "Filter invoice, client or matter"' in COLLECTION_DIALOG
    assert "function _filteredAllocationRows()" in COLLECTION_DIALOG
    assert '_clean(row && row.invoice)' in COLLECTION_DIALOG
    assert '_clean(row && row.client)' in COLLECTION_DIALOG
    assert '_clean(row && row.matter)' in COLLECTION_DIALOG
    assert 'text: dialog.invoiceFilterText ? "Allocate shown oldest first"' in COLLECTION_DIALOG
    assert "allocationRows[index].allocation = _clean(value)" in COLLECTION_DIALOG
    assert "allocationRevision += 1" in COLLECTION_DIALOG
    assert "dialog.setAllocation(allocationDelegate.modelData.sourceIndex, text)" in COLLECTION_DIALOG
    assert "allocationList.positionViewAtIndex(allocationDelegate.index, ListView.Contain)" in COLLECTION_DIALOG
