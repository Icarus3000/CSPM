import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from backend.controllers.billing_controller import BillingController
from domain import schema_constants as sc
from repositories.excel_repo import TBL_CLIENTS, TBL_MATTERS, TBL_TIME


class _Paths:
    def workbook_path(self):
        return Path("C:/test/CSPM.xlsm")


class _WipRepo:
    def __init__(self):
        self.paths = _Paths()
        self.signature = "100:200"
        self.bulk_requests = []
        self.tables = {
            TBL_CLIENTS.table: [
                {sc.COL_CLIENT_ID: "CLIENT-1", sc.COL_CLIENT_NAME: "AL ADVISOR"},
                {sc.COL_CLIENT_ID: "BILL-1", sc.COL_CLIENT_NAME: "Leviathan Private Network"},
            ],
            sc.TBL_CLIENT_PROFILES: [{
                sc.COL_PROFILE_CLIENT_ID: "CLIENT-1",
                sc.COL_PROFILE_PARENT_ID: "BILL-1",
            }],
            sc.TBL_PARENTS: [{
                sc.COL_PARENT_ID: "BILL-1",
                sc.COL_PARENT_NAME: "Leviathan Private Network",
            }],
            TBL_MATTERS.table: [{
                sc.COL_MATTER_ID: "MAT-1",
                sc.COL_MATTER_NAME: "Tax Planning",
                sc.COL_MATTER_NUMBER: "MAT-26-0057",
            }],
            TBL_TIME.table: [{
                sc.COL_TIME_ENTRY_ID: "TIME-1",
                sc.COL_TIME_DATE: "2026-05-05",
                sc.COL_TIME_CLIENT_ID: "CLIENT-1",
                sc.COL_TIME_MATTER_ID: "MAT-1",
                sc.COL_TIME_PARENT_ID: "BILL-1",
                sc.COL_TIME_DESC: "review transaction document",
                sc.COL_TIME_HOURS: 0.3,
                sc.COL_TIME_RATE: 475,
                sc.COL_TIME_NET: 142.5,
                sc.COL_TIME_HST: 18.53,
                sc.COL_TIME_SHARE_PCT: 100,
                sc.COL_TIME_GROSS: 142.5,
                sc.COL_TIME_SECONDS: 1080,
                sc.COL_TIME_STATUS: "Draft",
                sc.COL_TIME_INVOICE_STATUS: "Unbilled",
            }],
        }

    def _workbook_signature(self, _path):
        return self.signature

    @staticmethod
    def _parse_float(value):
        return float(value) if value not in (None, "") else None

    def _read_table_rows_bulk(self, table_refs):
        self.bulk_requests.append(list(table_refs))
        result = {}
        for table_ref in table_refs:
            table_name = getattr(table_ref, "table", table_ref)
            result[table_name] = [dict(row) for row in self.tables.get(table_name, [])]
        return result


def _controller(repo):
    return BillingController(repo, invoice_draft_service=None, invoice_document_service=None)


def test_wip_loader_uses_one_bulk_snapshot_and_preserves_wip_identity():
    repo = _WipRepo()
    controller = _controller(repo)

    payload = controller._load_unbilled_wip_impl(repo.signature)

    assert len(repo.bulk_requests) == 1
    assert len(repo.bulk_requests[0]) == 5
    assert payload["signature"] == repo.signature
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["entryId"] == "TIME-1"
    assert row["clientName"] == "AL ADVISOR"
    assert row["parentName"] == "Leviathan Private Network"
    assert row["matterName"] == "Tax Planning - 26-0057"


def test_wip_cache_avoids_a_second_worker_until_forced_refresh():
    repo = _WipRepo()
    controller = _controller(repo)
    started_workers = []
    delivered = []
    controller._start_worker = started_workers.append
    controller.wipDataLoaded.connect(lambda rows: delivered.append(list(rows)))

    controller.loadUnbilledWip()
    assert len(started_workers) == 1

    payload = controller._load_unbilled_wip_impl(repo.signature)
    controller._on_wip_loaded(started_workers[0], payload)
    assert len(delivered) == 1

    controller.loadUnbilledWip()
    assert len(started_workers) == 1
    assert len(delivered) == 2

    controller.loadUnbilledWip(True)
    assert len(started_workers) == 2
