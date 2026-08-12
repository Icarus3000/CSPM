import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_INVOICE_LOG,
    TBL_LEDGER,
    TBL_RECEIVABLES,
    TBL_TRANSACTIONS_MASTER,
)


class _RepairRepo:
    repair_rogue_vendor_receivables = ExcelRepo.repair_rogue_vendor_receivables

    def __init__(self):
        self.tables = {
            TBL_RECEIVABLES.table: [
                {sc.COL_RECV_INVOICE_NUM: "25-0062", sc.COL_RECV_CLIENT: "CIPO", sc.COL_RECV_WORK_CLIENT: "CIPO"},
                {sc.COL_RECV_INVOICE_NUM: "25-0062", sc.COL_RECV_CLIENT: "Tremendis Group", sc.COL_RECV_WORK_CLIENT: ""},
                {sc.COL_RECV_INVOICE_NUM: "2447773", sc.COL_RECV_CLIENT: "CIPO", sc.COL_RECV_WORK_CLIENT: "CIPO"},
                {sc.COL_RECV_INVOICE_NUM: "26-0110", sc.COL_RECV_CLIENT: "CIPO", sc.COL_RECV_WORK_CLIENT: "CIPO"},
            ],
            TBL_INVOICE_LOG.table: [
                {sc.COL_INV_INVOICE_NUM: "25-0062", sc.COL_INV_CLIENT_NAME: "CIPO", sc.COL_INV_SUB_CLIENT: "CIPO", sc.COL_INV_BILL_TO_CLIENT: "CIPO"},
                {sc.COL_INV_INVOICE_NUM: "25-0062", sc.COL_INV_CLIENT_NAME: "Tremendis Group", sc.COL_INV_SUB_CLIENT: "", sc.COL_INV_BILL_TO_CLIENT: "Tremendis Group"},
                {sc.COL_INV_INVOICE_NUM: "2447773", sc.COL_INV_CLIENT_NAME: "CIPO", sc.COL_INV_SUB_CLIENT: "CIPO", sc.COL_INV_BILL_TO_CLIENT: "CIPO"},
                {sc.COL_INV_INVOICE_NUM: "26-0110", sc.COL_INV_CLIENT_NAME: "CIPO", sc.COL_INV_SUB_CLIENT: "CIPO", sc.COL_INV_BILL_TO_CLIENT: "CIPO"},
            ],
            TBL_TRANSACTIONS_MASTER.table: [
                {sc.COL_TXN_INVOICE_REF: "25-0062", sc.COL_TXN_TYPE: "Expense", sc.COL_TXN_CLIENT: "CIPO"},
                {sc.COL_TXN_INVOICE_REF: "2447773", sc.COL_TXN_TYPE: "Expense", sc.COL_TXN_CLIENT: "CIPO"},
                {sc.COL_TXN_INVOICE_REF: "26-0110", sc.COL_TXN_TYPE: "Income", sc.COL_TXN_CLIENT: "CIPO"},
            ],
            TBL_LEDGER.table: [
                {sc.COL_LEDGER_REFERENCE: "25-0062", sc.COL_LEDGER_CLIENT_VENDOR: "CIPO", sc.COL_LEDGER_WORK_CLIENT: "CIPO", sc.COL_LEDGER_DESCRIPTION: "Adjustment applied - Legacy data cleanup - rogue vendor row"},
                {sc.COL_LEDGER_REFERENCE: "25-0062", sc.COL_LEDGER_CLIENT_VENDOR: "CIPO", sc.COL_LEDGER_WORK_CLIENT: "", sc.COL_LEDGER_DESCRIPTION: "Trademark filing fee"},
            ],
        }
        self.writes = []

    def ensure_schema(self):
        return None

    def _read_table_rows_bulk(self, refs):
        return {ref.table: [dict(row) for row in self.tables.get(ref.table, [])] for ref in refs}

    def _write_table_rows_bulk(self, snapshots):
        self.writes.append(snapshots)
        for ref, rows in snapshots.items():
            self.tables[ref.table] = [dict(row) for row in rows]


def test_repair_removes_only_vendor_expense_artifacts_and_is_idempotent():
    repo = _RepairRepo()

    plan = repo.repair_rogue_vendor_receivables("CIPO", apply=False)

    assert plan["applied"] is False
    assert plan["rogueInvoiceRefs"] == ["2447773", "25-0062"]
    assert plan["removed"] == {
        "receivables": 2,
        "invoiceLog": 2,
        "ledgerCleanupArtifacts": 1,
        "transactions": 0,
        "disbursements": 0,
    }
    assert repo.writes == []

    applied = repo.repair_rogue_vendor_receivables("CIPO", apply=True)

    assert applied["applied"] is True
    assert {row[sc.COL_RECV_INVOICE_NUM] for row in repo.tables[TBL_RECEIVABLES.table]} == {"25-0062", "26-0110"}
    assert {row[sc.COL_INV_CLIENT_NAME] for row in repo.tables[TBL_INVOICE_LOG.table]} == {"Tremendis Group", "CIPO"}
    assert len(repo.tables[TBL_LEDGER.table]) == 1
    assert repo.tables[TBL_TRANSACTIONS_MASTER.table] == [
        {sc.COL_TXN_INVOICE_REF: "25-0062", sc.COL_TXN_TYPE: "Expense", sc.COL_TXN_CLIENT: "CIPO"},
        {sc.COL_TXN_INVOICE_REF: "2447773", sc.COL_TXN_TYPE: "Expense", sc.COL_TXN_CLIENT: "CIPO"},
        {sc.COL_TXN_INVOICE_REF: "26-0110", sc.COL_TXN_TYPE: "Income", sc.COL_TXN_CLIENT: "CIPO"},
    ]

    repeat = repo.repair_rogue_vendor_receivables("CIPO", apply=True)
    assert repeat["applied"] is False
    assert repeat["removed"]["receivables"] == 0
