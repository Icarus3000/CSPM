import sys
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_DISBURSEMENTS,
    TBL_INVOICE_LOG,
    TBL_LEDGER,
    TBL_MATTERS,
    TBL_RECEIVABLES,
    TBL_TIME,
    TBL_TRANSACTIONS_MASTER,
    with_financial_write_batch,
)
from backend.controllers.billing_controller import BillingController


class _PaymentHistoryRepo:
    _money_round = ExcelRepo._money_round
    _date_iso = ExcelRepo._date_iso
    _parse_date_value = ExcelRepo._parse_date_value

    def __init__(self):
        self.transactions = [
            {
                "invoiceRef": "26-0101",
                "transactionId": "TXN-INVOICE",
                "txnDate": "2026-05-01",
                "type": "Income",
                "fromAccount": "Operating",
                "amount": 500.0,
                "notes": "Client Fees",
            },
            {
                "invoiceRef": "26-0101",
                "transactionId": "TXN-POSTED",
                "txnDate": "2026-06-02",
                "type": "Income",
                "fromAccount": "EFT",
                "amount": 125.0,
                "notes": "EFT applied to invoice 26-0101",
            },
            {
                "invoiceRef": "26-0101",
                "transactionId": "TXN-HISTORIC",
                "txnDate": "2026-06-14",
                "type": "Income",
                "fromAccount": "Cheque",
                "amount": 75.0,
                "notes": "Payment received from client",
            },
            {
                "invoiceRef": "26-0101",
                "transactionId": "TXN-NOT-A-PAYMENT",
                "txnDate": "2026-06-15",
                "type": "Transfer",
                "fromAccount": "Operating",
                "amount": 75.0,
                "notes": "Payment for 26-0101",
            },
            {
                "invoiceRef": "26-0101",
                "transactionId": "TXN-SETOFF",
                "txnDate": "2026-06-20",
                "type": "Transfer",
                "fromAccount": "Operating",
                "toAccount": "Settlement clearing",
                "amount": 80.0,
                "notes": "Payment for 26-0101 (Set-off — settlement agreement)",
            },
        ]
        self.ledger = [
            {
                sc.COL_LEDGER_REFERENCE: "26-0101",
                sc.COL_LEDGER_DATE: "2026-06-02",
                sc.COL_LEDGER_COLLECTED: 125.0,
                sc.COL_LEDGER_WRITE_OFF: 0.0,
                sc.COL_LEDGER_TRX_ID: "TXN-POSTED",
                sc.COL_LEDGER_EXTERNAL_REF_ID: "",
                sc.COL_LEDGER_ID: "LED-1",
                sc.COL_LEDGER_CATEGORY: "EFT",
                sc.COL_LEDGER_DESCRIPTION: "Payment applied to invoice 26-0101",
            }
        ]

    def list_transactions(self, _filters):
        return self.transactions

    def _read_table_rows(self, table):
        assert table == TBL_LEDGER
        return self.ledger


def test_invoice_payment_history_keeps_each_payment_once_and_excludes_invoice_revenue():
    repo = _PaymentHistoryRepo()

    history = ExcelRepo.list_invoice_payment_history(repo, "26-0101")

    assert [(row["date"], row["amount"]) for row in history] == [
        ("2026-06-20", 80.0),
        ("2026-06-14", 75.0),
        ("2026-06-02", 125.0),
    ]
    assert [row["type"] for row in history] == ["Settlement set-off", "Payment", "Payment"]
    assert {row["reference"] for row in history} == {"TXN-SETOFF", "TXN-HISTORIC", "TXN-POSTED"}
    set_off = history[0]
    assert set_off["displayLabel"] == "Settlement set-off — settlement agreement"
    assert set_off["openTarget"] == "transaction"
    assert set_off["transactionPayload"]["transactionId"] == "TXN-SETOFF"


class _GovernedSetoffPaymentHistoryRepo(_PaymentHistoryRepo):
    def _list_ap_setoff_invoice_activity(self, invoice_ref):
        assert invoice_ref == "26-0101"
        return [{
            "date": "2026-06-20",
            "type": "Settlement set-off",
            "displayLabel": "Settlement set-off — settlement agreement",
            "paymentId": "APP-SET-1",
            "transactionId": "",
            "ledgerId": "",
            "editable": True,
            "reference": "APP-SET-1",
            "method": "Accounts Receivable - Set-off",
            "amount": 80.0,
            "notes": "Verified settlement set-off.",
            "source": "A/P Set-off",
            "openTarget": "ap_setoff",
            "apBillId": "APB-SET-1",
            "apPaymentId": "APP-SET-1",
        }]


def test_invoice_payment_history_prefers_governed_ap_setoff_over_legacy_transfer_row():
    history = ExcelRepo.list_invoice_payment_history(_GovernedSetoffPaymentHistoryRepo(), "26-0101")

    set_off = next(row for row in history if row["type"] == "Settlement set-off")
    assert set_off["paymentId"] == "APP-SET-1"
    assert set_off["openTarget"] == "ap_setoff"
    assert set_off["apBillId"] == "APB-SET-1"
    assert set_off["apPaymentId"] == "APP-SET-1"
    assert all(row.get("transactionId") != "TXN-SETOFF" for row in history)


class _PaymentEditRepo:
    _money_round = ExcelRepo._money_round
    _date_iso = ExcelRepo._date_iso
    _parse_date_value = ExcelRepo._parse_date_value
    _payment_invoice_snapshot = ExcelRepo._payment_invoice_snapshot
    _invoice_payment_record = ExcelRepo._invoice_payment_record
    get_invoice_payment_entry = ExcelRepo.get_invoice_payment_entry
    update_invoice_payment = ExcelRepo.update_invoice_payment

    def __init__(self):
        self.tables = {
            TBL_TRANSACTIONS_MASTER.table: [
                {
                    sc.COL_TXN_ID: "TXN-PAY",
                    sc.COL_TXN_DATE: "2026-06-01",
                    sc.COL_TXN_TYPE: "Income",
                    sc.COL_TXN_FROM_ACCOUNT: "EFT",
                    sc.COL_TXN_AMOUNT: 100.0,
                    sc.COL_TXN_INVOICE_REF: "26-0102",
                    sc.COL_TXN_NOTES: "EFT applied to invoice 26-0102",
                    sc.COL_TXN_CLEARED_AT: "2026-06-01",
                    sc.COL_TXN_UPDATED_AT: "",
                }
            ],
            TBL_LEDGER.table: [
                {
                    sc.COL_LEDGER_ID: "LED-PAY",
                    sc.COL_LEDGER_DATE: "2026-06-01",
                    sc.COL_LEDGER_REFERENCE: "26-0102",
                    sc.COL_LEDGER_COLLECTED: 100.0,
                    sc.COL_LEDGER_WRITE_OFF: 0.0,
                    sc.COL_LEDGER_TRX_ID: "TXN-PAY",
                    sc.COL_LEDGER_EXTERNAL_REF_ID: "EFT-001",
                    sc.COL_LEDGER_CATEGORY: "EFT",
                    sc.COL_LEDGER_DESCRIPTION: "Payment applied to invoice 26-0102 (EFT)",
                    sc.COL_LEDGER_RECEIVABLE: -100.0,
                    sc.COL_LEDGER_ORIGINAL_AMOUNT: 100.0,
                }
            ],
            TBL_RECEIVABLES.table: [
                {
                    sc.COL_RECV_INVOICE_NUM: "26-0102",
                    sc.COL_RECV_DATE: "2026-05-01",
                    sc.COL_RECV_CLIENT: "Example Client",
                    sc.COL_RECV_WORK_CLIENT: "Example Client",
                    sc.COL_RECV_TOTAL_INVOICED: 100.0,
                    sc.COL_RECV_AMOUNT_PAID: 100.0,
                    sc.COL_RECV_CREDITS_ADJ: 0.0,
                    sc.COL_RECV_BALANCE_DUE: 0.0,
                    sc.COL_RECV_STATUS: "Paid",
                }
            ],
            TBL_TIME.table: [],
            TBL_DISBURSEMENTS.table: [],
        }

    def ensure_schema(self):
        return None

    def _read_table_rows(self, table):
        return [dict(row) for row in self.tables[table.table]]

    def _replace_table_rows(self, table, rows):
        self.tables[table.table] = [dict(row) for row in rows]


class _FinancialBatchProbe:
    def __init__(self):
        self._import_batch_active = False
        self.batch_count = 0
        self.was_batched = False

    @contextmanager
    def import_batch(self):
        self.batch_count += 1
        self._import_batch_active = True
        metrics = {"dirtyTables": 3, "saveSeconds": 0.01}
        try:
            yield metrics
        finally:
            self._import_batch_active = False

    @with_financial_write_batch
    def post(self):
        self.was_batched = self._import_batch_active
        return {"ok": True}


def test_financial_mutation_uses_one_outer_workbook_batch():
    repo = _FinancialBatchProbe()

    assert repo.post() == {"ok": True}
    assert repo.was_batched is True
    assert repo.batch_count == 1


def test_saved_payment_can_be_loaded_and_amended_without_creating_a_second_payment():
    repo = _PaymentEditRepo()

    loaded = repo.get_invoice_payment_entry("TXN-PAY")
    assert loaded["ok"] is True
    assert loaded["invoice"] == "26-0102"
    assert loaded["amount"] == 100.0
    assert loaded["depositAccount"] == "EFT"

    updated = repo.update_invoice_payment(
        {
            "paymentId": "TXN-PAY",
            "date": "2026-06-04",
            "amount": 60.0,
            "method": "Cheque",
            "depositAccount": "CIBC_CHEQUING",
            "reference": "CHQ-77",
            "notes": "Corrected amount",
        }
    )

    assert updated["ok"] is True
    assert updated["afterBalance"] == 40.0
    assert updated["invoiceRow"]["paid"] == 60.0
    assert updated["invoiceRow"]["balance"] == 40.0
    assert repo.tables[TBL_LEDGER.table][0][sc.COL_LEDGER_COLLECTED] == 60.0
    assert repo.tables[TBL_LEDGER.table][0][sc.COL_LEDGER_DATE] == "2026-06-04"
    assert repo.tables[TBL_TRANSACTIONS_MASTER.table][0][sc.COL_TXN_AMOUNT] == 60.0
    assert repo.tables[TBL_TRANSACTIONS_MASTER.table][0][sc.COL_TXN_FROM_ACCOUNT] == "CIBC_CHEQUING"
    assert repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_STATUS] == "Partial"


class _BillingClientReceiptRepo:
    _money_round = ExcelRepo._money_round
    _date_iso = ExcelRepo._date_iso
    _parse_date_value = ExcelRepo._parse_date_value
    _payment_invoice_snapshot = ExcelRepo._payment_invoice_snapshot
    post_billing_client_receipt = ExcelRepo.post_billing_client_receipt

    def __init__(self):
        self.sequence = 0
        self.saved_transaction_payloads = []
        self.tables = {
            TBL_TRANSACTIONS_MASTER.table: [],
            TBL_LEDGER.table: [],
            TBL_RECEIVABLES.table: [
                {
                    sc.COL_RECV_INVOICE_NUM: "26-0201",
                    sc.COL_RECV_DATE: "2026-05-01",
                    sc.COL_RECV_CLIENT: "Billing Parent Inc.",
                    sc.COL_RECV_WORK_CLIENT: "Operating Company A",
                    sc.COL_RECV_TOTAL_INVOICED: 100.0,
                    sc.COL_RECV_AMOUNT_PAID: 0.0,
                    sc.COL_RECV_CREDITS_ADJ: 0.0,
                    sc.COL_RECV_BALANCE_DUE: 100.0,
                    sc.COL_RECV_STATUS: "Open",
                },
                {
                    sc.COL_RECV_INVOICE_NUM: "26-0202",
                    sc.COL_RECV_DATE: "2026-05-15",
                    sc.COL_RECV_CLIENT: "Billing Parent Inc.",
                    sc.COL_RECV_WORK_CLIENT: "Operating Company B",
                    sc.COL_RECV_TOTAL_INVOICED: 200.0,
                    sc.COL_RECV_AMOUNT_PAID: 25.0,
                    sc.COL_RECV_CREDITS_ADJ: 0.0,
                    sc.COL_RECV_BALANCE_DUE: 175.0,
                    sc.COL_RECV_STATUS: "Partial",
                },
            ],
            TBL_TIME.table: [
                {sc.COL_TIME_INVOICE_REF: "26-0201"},
                {sc.COL_TIME_INVOICE_REF: "26-0202"},
            ],
            TBL_DISBURSEMENTS.table: [
                {sc.COL_DISB_INVOICE_REF: "26-0202"},
            ],
        }

    def ensure_schema(self):
        return None

    def _read_table_rows(self, table):
        return [dict(row) for row in self.tables[table.table]]

    def _replace_table_rows(self, table, rows):
        self.tables[table.table] = [dict(row) for row in rows]

    def _append_row_to_table(self, table, row):
        self.tables[table.table].append(dict(row))

    def _new_id(self, prefix):
        self.sequence += 1
        return f"{prefix}-TEST-{self.sequence}"

    def save_transaction(self, payload):
        stored = dict(payload)
        self.saved_transaction_payloads.append(stored)
        self.tables[TBL_TRANSACTIONS_MASTER.table].append(
            {
                sc.COL_TXN_ID: stored["transactionId"],
                sc.COL_TXN_AMOUNT: stored["amount"],
                sc.COL_TXN_INVOICE_REF: stored["invoiceRef"],
                sc.COL_TXN_EXPENSE_DETAILS: stored["expenseDetails"],
            }
        )
        return {
            "ok": True,
            "transactionId": stored["transactionId"],
        }


def test_billing_client_receipt_creates_one_bank_transaction_and_separate_allocations():
    repo = _BillingClientReceiptRepo()

    result = repo.post_billing_client_receipt(
        {
            "billingClient": "Billing Parent Inc.",
            "date": "2026-06-20",
            "totalAmount": 250.0,
            "method": "EFT",
            "depositAccount": "CIBC_GENERAL",
            "reference": "EFT-900",
            "notes": "June remittance",
            "allocations": [
                {"invoice": "26-0201", "amount": 100.0},
                {"invoice": "26-0202", "amount": 150.0},
            ],
        }
    )

    assert result["ok"] is True
    assert result["allocationCount"] == 2
    assert len(repo.saved_transaction_payloads) == 1
    transaction = repo.saved_transaction_payloads[0]
    assert transaction["amount"] == 250.0
    assert transaction["payee"] == "Billing Parent Inc."
    assert transaction["fromAccount"] == "CIBC_GENERAL"
    assert transaction["invoiceRef"] == "MULTI:26-0201,26-0202"

    ledger_rows = repo.tables[TBL_LEDGER.table]
    assert len(ledger_rows) == 2
    assert {row[sc.COL_LEDGER_TRX_ID] for row in ledger_rows} == {result["receiptId"]}
    assert {row[sc.COL_LEDGER_REFERENCE] for row in ledger_rows} == {"26-0201", "26-0202"}
    assert sum(row[sc.COL_LEDGER_COLLECTED] for row in ledger_rows) == 250.0

    receivables = {
        row[sc.COL_RECV_INVOICE_NUM]: row
        for row in repo.tables[TBL_RECEIVABLES.table]
    }
    assert receivables["26-0201"][sc.COL_RECV_BALANCE_DUE] == 0.0
    assert receivables["26-0201"][sc.COL_RECV_STATUS] == "Paid"
    assert receivables["26-0202"][sc.COL_RECV_BALANCE_DUE] == 25.0
    assert receivables["26-0202"][sc.COL_RECV_STATUS] == "Partial"
    assert repo.tables[TBL_TIME.table][0][sc.COL_TIME_PAYMENT_STATUS] == "Paid"
    assert repo.tables[TBL_TIME.table][1][sc.COL_TIME_PAYMENT_STATUS] == "Partial"
    assert repo.tables[TBL_DISBURSEMENTS.table][0][sc.COL_DISB_INVOICE_BALANCE_DUE] == 25.0


def test_billing_client_receipt_rejects_unbalanced_or_cross_client_allocations_before_writing():
    repo = _BillingClientReceiptRepo()
    base = {
        "billingClient": "Billing Parent Inc.",
        "date": "2026-06-20",
        "totalAmount": 100.0,
        "method": "Cheque",
        "depositAccount": "CIBC_GENERAL",
        "allocations": [{"invoice": "26-0201", "amount": 90.0}],
    }

    try:
        repo.post_billing_client_receipt(base)
        assert False, "Expected an unbalanced allocation to be rejected."
    except ValueError as exc:
        assert "must equal amount received" in str(exc)

    cross_client = dict(base)
    cross_client["totalAmount"] = 100.0
    cross_client["allocations"] = [{"invoice": "26-0201", "amount": 100.0}]
    cross_client["billingClient"] = "Different Billing Client"
    try:
        repo.post_billing_client_receipt(cross_client)
        assert False, "Expected a cross-client allocation to be rejected."
    except ValueError as exc:
        assert "belongs to billing client" in str(exc)

    assert repo.saved_transaction_payloads == []
    assert repo.tables[TBL_LEDGER.table] == []


def test_multi_invoice_receipt_history_is_not_editable_as_one_invoice_payment():
    repo = _PaymentHistoryRepo()
    repo.ledger.append(
        {
            sc.COL_LEDGER_REFERENCE: "26-0102",
            sc.COL_LEDGER_DATE: "2026-06-02",
            sc.COL_LEDGER_COLLECTED: 25.0,
            sc.COL_LEDGER_WRITE_OFF: 0.0,
            sc.COL_LEDGER_TRX_ID: "TXN-POSTED",
            sc.COL_LEDGER_EXTERNAL_REF_ID: "",
            sc.COL_LEDGER_ID: "LED-2",
            sc.COL_LEDGER_CATEGORY: "EFT",
            sc.COL_LEDGER_DESCRIPTION: "Receipt TXN-POSTED allocated to invoice 26-0102",
        }
    )

    history = ExcelRepo.list_invoice_payment_history(repo, "26-0101")
    allocated = next(row for row in history if row["transactionId"] == "TXN-POSTED")

    assert allocated["type"] == "Allocated receipt"
    assert allocated["multiInvoiceReceipt"] is True
    assert allocated["editable"] is False
    assert allocated["openTarget"] == "receipt"


def test_multi_invoice_receipt_is_rejected_by_single_invoice_editor():
    repo = _PaymentEditRepo()
    repo.tables[TBL_LEDGER.table].append(
        {
            sc.COL_LEDGER_ID: "LED-SECOND",
            sc.COL_LEDGER_DATE: "2026-06-01",
            sc.COL_LEDGER_REFERENCE: "26-OTHER",
            sc.COL_LEDGER_COLLECTED: 25.0,
            sc.COL_LEDGER_WRITE_OFF: 0.0,
            sc.COL_LEDGER_TRX_ID: "TXN-PAY",
            sc.COL_LEDGER_EXTERNAL_REF_ID: "EFT-001",
        }
    )

    loaded = repo.get_invoice_payment_entry("TXN-PAY")

    assert loaded["ok"] is False
    assert "allocated across multiple invoices" in loaded["message"]


class _InvoiceDirectoryRepo:
    def __init__(self):
        self.tables = {
            TBL_INVOICE_LOG.table: [
                {
                    sc.COL_INV_INVOICE_NUM: "26-0201",
                    sc.COL_INV_CLIENT_NAME: "North Shore Inc.",
                    sc.COL_INV_INVOICE_DATE: "2026-06-01",
                },
                {
                    sc.COL_INV_INVOICE_NUM: "26-0202",
                    sc.COL_INV_CLIENT_NAME: "Solo Client",
                    sc.COL_INV_INVOICE_DATE: "2026-06-01",
                },
            ],
            TBL_TIME.table: [
                {
                    sc.COL_TIME_INVOICE_REF: "26-0201",
                    sc.COL_TIME_MATTER_ID: "MAT-NORTH",
                }
            ],
            TBL_DISBURSEMENTS.table: [],
            TBL_TRANSACTIONS_MASTER.table: [],
            TBL_MATTERS.table: [
                {
                    sc.COL_MATTER_ID: "MAT-NORTH",
                    sc.COL_MATTER_CLIENT_NAME: "North Shore Inc.",
                    sc.COL_MATTER_DESCRIPTION: "Corporate reorganization",
                    sc.COL_MATTER_OPEN_DATE: "2026-01-01",
                },
                {
                    sc.COL_MATTER_ID: "MAT-SOLO",
                    sc.COL_MATTER_CLIENT_NAME: "Solo Client",
                    sc.COL_MATTER_DESCRIPTION: "Trademark renewal",
                    sc.COL_MATTER_OPEN_DATE: "2026-01-01",
                },
            ],
        }

    def _read_table_rows(self, table):
        return [dict(row) for row in self.tables[table.table]]


def test_finalized_invoice_list_includes_plain_english_matter_description():
    controller = BillingController(_InvoiceDirectoryRepo(), None, None)

    rows = controller.listFinalizedInvoices()

    assert rows[0]["MatterDescription"] == "Corporate reorganization"
    # Historic records without linked time/disbursement data use the same
    # cautious single-matter fallback as the invoice detail card.
    assert rows[1]["MatterDescription"] == "Trademark renewal"


def test_invoice_directory_has_matter_detail_payment_tabs_and_taller_cards():
    source = (
        PROJECT_ROOT / "src" / "qml" / "views" / "InvoiceReversalView.qml"
    ).read_text(encoding="utf-8")
    main_content = (
        PROJECT_ROOT / "src" / "qml" / "views" / "MainContent.qml"
    ).read_text(encoding="utf-8")
    pathways = (
        PROJECT_ROOT / "src" / "qml" / "standards" / "ModulePathways.js"
    ).read_text(encoding="utf-8")
    transaction_master = (
        PROJECT_ROOT / "src" / "qml" / "views" / "TransactionsMasterView.qml"
    ).read_text(encoding="utf-8")
    submenu = (
        PROJECT_ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml"
    ).read_text(encoding="utf-8")
    transaction_combo = (
        PROJECT_ROOT / "src" / "qml" / "components" / "ModernComboBox.qml"
    ).read_text(encoding="utf-8")

    assert "property var selectedPaymentHistory: []" in source
    assert "billingBackend.loadInvoiceDirectoryDetails(root.selectedInvoiceNum)" in source
    assert "billingBackend.loadFinalizedInvoices()" in source
    assert "function _applyInvoices(rawInvoices)" in source
    assert "root._refreshSelectedInvoiceDetails()" in source
    assert "function onInvoiceDirectoryDetailsLoaded(payload)" in source
    assert 'property string st: loading ? "Loading..."' in source
    assert "function _displayInvoiceStatus(summary)" in source
    assert 'if (raw === "pending" || raw === "unpaid") return "Unpaid"' in source
    assert 'st === "Unpaid" || st === "Partially Paid"' in source
    assert "function onPaymentSaveFinished(result)" in source
    assert "root._refreshSelectedInvoiceDetails()" in source
    assert 'text: "Matter:"' in source
    assert "root.selectedInvoiceSummary.MatterDetails" in source
    assert "modelData.MatterDescription" in source
    assert 'text: "Matter · " + invoiceDirectoryRow.matterDescription' in source
    assert "ToolTip.text: matterDescription" in source
    assert "root._paymentDateLabel(modelData.date)" in source
    assert "property int invoiceCardHeight: root.compactLayout ? 232 : 255" in source
    assert "Layout.minimumHeight: root.invoiceCardHeight" in source
    assert "Layout.maximumHeight: root.invoiceCardHeight" in source
    assert "width: 144" in source
    assert "height: 46" in source
    assert "function _openPaymentEntry(invoiceNumber, paymentId, clientName)" in source
    assert "function _paymentWorkspaceState(invoiceNumber, paymentId, clientName)" in source
    assert "function _transactionWorkspaceState(invoiceNumber, historyRow, clientName)" in source
    assert "function _openPaymentHistoryRecord(historyRow)" in source
    assert "root.workspaceOpenRequested(2, \"C11\", transactionState)" in source
    assert "modelData.displayLabel" in source
    assert '"deferTabStateUntilActivated": true' in source
    assert "modelData.paymentId" in source
    assert "root.selectedPaymentHistory.length * 24" in source
    assert "root.ledgerAmountColumnWidth" in source
    assert "root.ledgerDateColumnWidth" in source
    assert "if (tabParams.activate !== false && !tabParams.deferTabStateUntilActivated)" in main_content
    assert "targetState.deferTabStateUntilActivated" in main_content
    assert '"id": "C07"' in pathways
    assert '"tabType": "payment", "singleInstance": false' in pathways
    assert '"id": "C11"' in pathways
    assert '"tabType": "transaction", "singleInstance": false' in pathways
    assert "if (!state || !state.payload) return" in transaction_master
    assert "categoryText = _clean(payload.categoryCode)" in transaction_master
    assert "property bool editingStoredTransaction: false" in transaction_master
    assert "preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction" in transaction_master
    assert "if (!editingStoredTransaction)" in transaction_master
    assert "Draft-entry rules must never erase the stored context" in transaction_master
    assert "property bool preserveUnknownEditTextOnModelChanged: false" in transaction_combo
    assert "control.preserveUnknownEditTextOnModelChanged === true" in transaction_combo
    assert "editingStoredTransaction = false" in transaction_master
    assert "transactionMasterView.applyState(state)" in submenu
    assert "item.applyState(root._pendingStateForLoader)" in submenu


def test_invoice_directory_backend_uses_workers_and_single_workbook_bulk_reads():
    source = (
        PROJECT_ROOT / "src" / "python" / "backend" / "controllers" / "billing_controller.py"
    ).read_text(encoding="utf-8")

    assert "finalizedInvoicesLoaded = Signal('QVariantList')" in source
    assert "invoiceDirectoryDetailsLoaded = Signal('QVariantMap')" in source
    assert "def loadFinalizedInvoices(self):" in source
    assert 'Worker(self._list_finalized_invoices_impl, name="loadFinalizedInvoices")' in source
    assert "def loadInvoiceDirectoryDetails(self, invoice_num):" in source
    assert 'name="loadInvoiceDirectoryDetails"' in source
    assert "_read_table_rows_bulk" in source
    assert "def _start_invoice_reversal_worker(" in source
    assert 'name=f"invoice-{action}"' in source
