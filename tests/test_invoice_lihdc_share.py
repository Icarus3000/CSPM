from copy import deepcopy

from domain import schema_constants as sc
from services.invoice_draft_service import InvoiceDraftService


class _MemoryRepo:
    def __init__(self):
        self.tables = {
            sc.TBL_TIME: [{
                sc.COL_TIME_ENTRY_ID: "T-1",
                sc.COL_TIME_DATE: "2026-06-25",
                sc.COL_TIME_GROSS: "316.00",
                sc.COL_TIME_NET: "221.20",
                sc.COL_TIME_HST: "28.76",
                sc.COL_TIME_TOTAL: "249.96",
            }],
            sc.TBL_DISBURSEMENTS: [],
            sc.TBL_DRAFT_INVOICES: [],
        }

    def _read_table_rows(self, table):
        return deepcopy(self.tables.get(table, []))

    def _write_table_rows(self, table, rows):
        self.tables[table] = deepcopy(rows)


def test_lihdc_draft_does_not_apply_lawyer_share_twice():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)

    draft_num = service.create_draft(
        "LIHDC",
        "LIHDC Professional Corporation",
        ["T-1"],
    )

    draft = repo.tables[sc.TBL_DRAFT_INVOICES][0]
    assert draft[sc.COL_DRAFT_INVOICE_NUM] == draft_num
    assert draft[sc.COL_DRAFT_AGENCY_SPLIT_PERCENT] == "0.0"
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "221.20"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "28.76"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "249.96"
