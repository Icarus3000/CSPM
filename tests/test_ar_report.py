import pytest
from datetime import date
from src.python.repositories.excel_repo import ExcelRepo
from src.python.domain.schema_constants import (
    TBL_RECEIVABLES, TBL_INVOICE_LOG, TBL_LEDGER, TBL_PARENTS, TBL_CLIENTS, TBL_CLIENT_PROFILES,
    COL_RECV_INVOICE_NUM, COL_RECV_TOTAL_INVOICED, COL_RECV_AMOUNT_PAID, COL_RECV_CREDITS_ADJ, COL_RECV_BALANCE_DUE, COL_RECV_STATUS, COL_RECV_CLIENT, COL_RECV_WORK_CLIENT, COL_RECV_DATE,
    COL_INV_INVOICE_NUM, COL_INV_TOTAL_TAX, COL_INV_AGGREGATE_BILLED,
    COL_LEDGER_REFERENCE, COL_LEDGER_BILLINGS_EXCL_HST, COL_LEDGER_RECEIVABLE, COL_LEDGER_CLIENT_VENDOR, COL_LEDGER_DATE
)

def test_ar_report_net_tax_allocation(mocker):
    repo = ExcelRepo("dummy.xlsm")
    
    mock_tables = {
        TBL_RECEIVABLES.table: [
            # Fully unpaid, has invoice log
            {COL_RECV_INVOICE_NUM: "26-0001", COL_RECV_TOTAL_INVOICED: "1130.00", COL_RECV_AMOUNT_PAID: "0.00", COL_RECV_CREDITS_ADJ: "0.00", COL_RECV_BALANCE_DUE: "1130.00", COL_RECV_STATUS: "Open", COL_RECV_CLIENT: "Test Client", COL_RECV_DATE: "45300"},
            # Partially paid, has invoice log (50% paid)
            {COL_RECV_INVOICE_NUM: "26-0002", COL_RECV_TOTAL_INVOICED: "1130.00", COL_RECV_AMOUNT_PAID: "565.00", COL_RECV_CREDITS_ADJ: "0.00", COL_RECV_BALANCE_DUE: "565.00", COL_RECV_STATUS: "Open", COL_RECV_CLIENT: "Test Client", COL_RECV_DATE: "45300"},
            # Legacy invoice, no invoice log
            {COL_RECV_INVOICE_NUM: "20-0001", COL_RECV_TOTAL_INVOICED: "1130.00", COL_RECV_AMOUNT_PAID: "0.00", COL_RECV_CREDITS_ADJ: "0.00", COL_RECV_BALANCE_DUE: "1130.00", COL_RECV_STATUS: "Open", COL_RECV_CLIENT: "Test Client", COL_RECV_DATE: "45300"},
        ],
        TBL_INVOICE_LOG.table: [
            {COL_INV_INVOICE_NUM: "26-0001", COL_INV_TOTAL_TAX: "130.00", COL_INV_AGGREGATE_BILLED: "1130.00"},
            {COL_INV_INVOICE_NUM: "26-0002", COL_INV_TOTAL_TAX: "130.00", COL_INV_AGGREGATE_BILLED: "1130.00"},
        ],
        TBL_LEDGER.table: [],
        TBL_PARENTS.table: [],
        TBL_CLIENTS.table: [],
        TBL_CLIENT_PROFILES.table: []
    }
    mocker.patch.object(repo, "_read_table_rows", side_effect=lambda t: mock_tables.get(t.table, []))
    
    result = repo.ar_aging_report()
    
    rows = result["rows"]
    issues = result["issueRows"]
    cards = {c["label"]: c["value"] for c in result["cards"]}
    
    row_1 = next(r for r in rows if r["invoice"] == "26-0001")
    assert row_1["balance"] == 1130.00
    assert row_1["balanceNet"] == 1000.00
    
    row_2 = next(r for r in rows if r["invoice"] == "26-0002")
    assert row_2["balance"] == 565.00
    assert row_2["balanceNet"] == 500.00 # 565 - (565 * (130/1130)) = 500
    
    row_3 = next(r for r in rows if r["invoice"] == "20-0001")
    assert row_3["balance"] == 1130.00
    assert row_3["balanceNet"] == 1130.00
    
    assert len(issues) == 1
    assert issues[0]["reference"] == "20-0001"
    
    assert cards["Gross A/R, including HST"] == 1130 + 565 + 1130
    assert cards["A/R excluding HST"] == 1000 + 500 + 1130
