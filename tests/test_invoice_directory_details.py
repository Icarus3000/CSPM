import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_DISBURSEMENTS,
    TBL_LEDGER,
    TBL_RECEIVABLES,
    TBL_TIME,
    TBL_TRANSACTIONS_MASTER,
)


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
        ("2026-06-14", 75.0),
        ("2026-06-02", 125.0),
    ]
    assert all(row["type"] == "Payment" for row in history)
    assert {row["reference"] for row in history} == {"TXN-HISTORIC", "TXN-POSTED"}


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


def test_saved_payment_can_be_loaded_and_amended_without_creating_a_second_payment():
    repo = _PaymentEditRepo()

    loaded = repo.get_invoice_payment_entry("TXN-PAY")
    assert loaded["ok"] is True
    assert loaded["invoice"] == "26-0102"
    assert loaded["amount"] == 100.0

    updated = repo.update_invoice_payment(
        {
            "paymentId": "TXN-PAY",
            "date": "2026-06-04",
            "amount": 60.0,
            "method": "Cheque",
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
    assert repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_STATUS] == "Partial"


def test_invoice_directory_has_matter_detail_payment_dates_and_taller_cards():
    source = (
        PROJECT_ROOT / "src" / "qml" / "views" / "InvoiceReversalView.qml"
    ).read_text(encoding="utf-8")

    assert "property var selectedPaymentHistory: []" in source
    assert "root.appController.listInvoicePaymentHistory(root.selectedInvoiceNum)" in source
    assert "function onPaymentSaveFinished(result)" in source
    assert "root._refreshSelectedInvoiceDetails()" in source
    assert 'text: "Matter:"' in source
    assert "root.selectedInvoiceSummary.MatterDetails" in source
    assert "root._paymentDateLabel(modelData.date)" in source
    assert "property int invoiceCardHeight: root.compactLayout ? 195 : 215" in source
    assert "Layout.minimumHeight: root.invoiceCardHeight" in source
    assert "Layout.maximumHeight: root.invoiceCardHeight" in source
    assert "width: 125" in source
    assert "height: 40" in source
    assert "function _openPaymentEntry(invoiceNumber, paymentId)" in source
    assert "root.ledgerAmountColumnWidth" in source
    assert "root.ledgerDateColumnWidth" in source
