import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from decimal import Decimal
from copy import deepcopy

from domain import schema_constants as sc
from services.invoice_draft_service import InvoiceDraftService


class _MemoryRepo:
    def __init__(self):
        self.tables = {
            sc.TBL_TIME: [
                {
                    sc.COL_TIME_ENTRY_ID: "T-1",
                    sc.COL_TIME_DATE: "2026-06-25",
                    sc.COL_TIME_CLIENT_ID: "C_TEST",
                    sc.COL_TIME_DESC: "Legal Research",
                    sc.COL_TIME_GROSS: "1000.00",
                    sc.COL_TIME_NET: "1000.00",
                    sc.COL_TIME_HST: "130.00",
                    sc.COL_TIME_TOTAL: "1130.00",
                },
                {
                    sc.COL_TIME_ENTRY_ID: "T-2",
                    sc.COL_TIME_DATE: "2026-06-26",
                    sc.COL_TIME_CLIENT_ID: "C_TEST",
                    sc.COL_TIME_DESC: "Contract Drafting",
                    sc.COL_TIME_GROSS: "2000.00",
                    sc.COL_TIME_NET: "2000.00",
                    sc.COL_TIME_HST: "260.00",
                    sc.COL_TIME_TOTAL: "2260.00",
                },
            ],
            sc.TBL_DISBURSEMENTS: [],
            sc.TBL_DRAFT_INVOICES: [],
            sc.TBL_INVOICE_LOG: [],
            sc.TBL_RECEIVABLES: [],
            sc.TBL_LEDGER: [],
        }

    def _read_table_rows(self, table):
        return deepcopy(self.tables.get(table, []))

    def _write_table_rows(self, table, rows):
        self.tables[table] = deepcopy(rows)

    def _write_table_rows_bulk(self, table_map):
        for table, rows in table_map.items():
            self.tables[table] = deepcopy(rows)

    def _new_id(self, prefix):
        return f"{prefix}_12345"


def test_flat_discount_calculation_and_finalization():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)

    draft_num = service.create_draft(
        "C_TEST",
        "Test Client",
        ["T-1", "T-2"],
    )

    # Initial totals: $3,000 net fees, $390 HST, $3,390 total
    draft = service.get_draft(draft_num)
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "3000.00"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "390.00"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "3390.00"

    # Apply Flat discount of $1,000 (Case-insensitive check with 'flat')
    service.apply_discount(draft_num, "flat", Decimal("1000.00"))
    draft = service.get_draft(draft_num)
    assert draft[sc.COL_DRAFT_DISCOUNT_TYPE] == "Flat"
    assert draft[sc.COL_DRAFT_DISCOUNT_VALUE] == "1000.00"
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "2000.00"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "260.00"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "2260.00"

    # Finalize invoice as 26-9999
    res = service.finalize_draft(draft_num, "26-9999", "C:/test.pdf")
    assert res is True

    # Verify Invoice Log
    inv_log = repo.tables[sc.TBL_INVOICE_LOG]
    assert len(inv_log) == 1
    assert inv_log[0][sc.COL_INV_INVOICE_NUM] == "26-9999"
    assert inv_log[0][sc.COL_INV_TOTAL_FEES] == "2000.00"
    assert inv_log[0][sc.COL_INV_TOTAL_TAX] == "260.00"
    assert inv_log[0][sc.COL_INV_AGGREGATE_BILLED] == "2260.00"

    # Verify Receivables
    recv = repo.tables[sc.TBL_RECEIVABLES]
    assert len(recv) == 1
    assert recv[0][sc.COL_RECV_TOTAL_INVOICED] == "2260.00"
    assert recv[0][sc.COL_RECV_BALANCE_DUE] == "2260.00"

    # Verify Ledger
    ledger = repo.tables[sc.TBL_LEDGER]
    assert len(ledger) == 1
    assert ledger[0][sc.COL_LEDGER_BILLINGS_EXCL_HST] == "2000.00"
    assert ledger[0][sc.COL_LEDGER_HST_COLLECTED] == "260.00"
    assert ledger[0][sc.COL_LEDGER_RECEIVABLE] == "2260.00"

    # Verify WIP adjustment row in TBL_TIME
    time_rows = repo.tables[sc.TBL_TIME]
    assert len(time_rows) == 3
    discount_row = next(r for r in time_rows if "Courtesy Discount" in str(r.get(sc.COL_TIME_DESC)))
    assert discount_row[sc.COL_TIME_NET] == "-1000.00"
    assert discount_row[sc.COL_TIME_HST] == "-130.00"
    assert discount_row[sc.COL_TIME_TOTAL] == "-1130.00"
    assert discount_row[sc.COL_TIME_INVOICE_REF] == "26-9999"


def test_percentage_discount_calculation_and_finalization():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)

    draft_num = service.create_draft(
        "C_TEST",
        "Test Client",
        ["T-1", "T-2"],
    )

    # Apply 10% discount (Case-insensitive check with 'percentage')
    service.apply_discount(draft_num, "percentage", Decimal("10.0"))
    draft = service.get_draft(draft_num)
    assert draft[sc.COL_DRAFT_DISCOUNT_TYPE] == "Percentage"
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "2700.00"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "351.00"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "3051.00"

    # Finalize invoice as 26-9998
    res = service.finalize_draft(draft_num, "26-9998", "C:/test.pdf")
    assert res is True

    # Verify WIP discount row
    time_rows = repo.tables[sc.TBL_TIME]
    discount_row = next(r for r in time_rows if "Courtesy Discount" in str(r.get(sc.COL_TIME_DESC)))
    assert discount_row[sc.COL_TIME_NET] == "-300.00"
    assert discount_row[sc.COL_TIME_HST] == "-39.00"
    assert discount_row[sc.COL_TIME_TOTAL] == "-339.00"
