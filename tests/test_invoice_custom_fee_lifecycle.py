from __future__ import annotations

import copy
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from services.invoice_draft_service import InvoiceDraftService


DRAFT_NUM = "DRAFT-2026-0001"
DRAFT_ID = "DRAFT-ID-0001"
CLIENT_ID = "CLIENT-0001"
MATTER_ID = "MATTER-0001"


class _MemoryRepo:
    def __init__(self):
        self._lock = threading.RLock()
        self._ids = 0
        self.fail_bulk_before_once = False
        self.fail_bulk_after_once = False
        self.bulk_writes = 0
        self.tables = {
            sc.TBL_DRAFT_INVOICES: [{
                sc.COL_DRAFT_ID: DRAFT_ID,
                sc.COL_DRAFT_INVOICE_NUM: DRAFT_NUM,
                sc.COL_DRAFT_CLIENT_ID: CLIENT_ID,
                sc.COL_DRAFT_CLIENT_NAME: "Lifecycle Client",
                sc.COL_DRAFT_DATE: "2026-08-30",
                sc.COL_DRAFT_DISCOUNT_TYPE: "None",
                sc.COL_DRAFT_DISCOUNT_VALUE: "0.00",
                sc.COL_DRAFT_AGENCY_SPLIT_PERCENT: "0.00",
                sc.COL_DRAFT_IS_FLAT_FEE: "False",
                sc.COL_DRAFT_TOTAL_FEES: "100.00",
                sc.COL_DRAFT_TOTAL_TAX: "13.00",
                sc.COL_DRAFT_TOTAL_DUE: "113.00",
                sc.COL_DRAFT_REISSUE_INVOICE_NUM: "",
                sc.COL_DRAFT_BILL_TO_SNAPSHOT: "",
            }],
            sc.TBL_TIME: [{
                sc.COL_TIME_ENTRY_ID: "TIME-ORDINARY-1",
                sc.COL_TIME_DATE: "2026-08-29",
                sc.COL_TIME_CLIENT_ID: CLIENT_ID,
                sc.COL_TIME_MATTER_ID: MATTER_ID,
                sc.COL_TIME_PARENT_ID: "",
                sc.COL_TIME_DESC: "Ordinary docket",
                sc.COL_TIME_HOURS: "1.0",
                sc.COL_TIME_RATE: "100.0",
                sc.COL_TIME_GROSS: "100.00",
                sc.COL_TIME_NET: "100.00",
                sc.COL_TIME_HST: "13.00",
                sc.COL_TIME_TOTAL: "113.00",
                sc.COL_TIME_STATUS: "Draft",
                sc.COL_TIME_INVOICE_REF: DRAFT_NUM,
                sc.COL_TIME_INVOICE_STATUS: "Draft",
                sc.COL_TIME_PAYMENT_STATUS: "",
                sc.COL_TIME_INVOICE_TOTAL: "0.00",
                sc.COL_TIME_INVOICE_AMOUNT_PAID: "0.00",
                sc.COL_TIME_INVOICE_BALANCE_DUE: "0.00",
                sc.COL_TIME_REISSUE_INVOICE_NUM: "",
                sc.COL_TIME_LOCK_AUDIT: "",
            }],
            sc.TBL_DISBURSEMENTS: [{
                "DisbursementID": "DISB-1",
                sc.COL_DISB_MATTER_ID: MATTER_ID,
                sc.COL_DISB_AMOUNT: "10.00",
                sc.COL_DISB_INVOICE_REF: DRAFT_NUM,
                sc.COL_DISB_REISSUE_INVOICE_NUM: "",
            }],
            sc.TBL_MATTERS: [{
                sc.COL_MATTER_ID: MATTER_ID,
                sc.COL_MATTER_CLIENT_ID: CLIENT_ID,
                sc.COL_MATTER_PARENT_ID: "",
                sc.COL_MATTER_NUMBER: "26-0001",
                sc.COL_MATTER_NAME: "Lifecycle Matter",
            }],
            sc.TBL_RECEIVABLES: [],
            sc.TBL_INVOICE_LOG: [],
            sc.TBL_LEDGER: [],
            sc.TBL_TRANSACTIONS_MASTER: [],
        }

    def _read_table_rows(self, table):
        with self._lock:
            return copy.deepcopy(self.tables.get(table, []))

    def _read_table_rows_bulk(self, tables):
        with self._lock:
            return {table: copy.deepcopy(self.tables.get(table, [])) for table in tables}

    def _write_table_rows(self, table, rows):
        with self._lock:
            self.tables[table] = copy.deepcopy(rows)

    def _write_table_rows_bulk(self, table_rows):
        with self._lock:
            if self.fail_bulk_before_once:
                self.fail_bulk_before_once = False
                raise OSError("simulated failure before atomic replacement")
            for table, rows in table_rows.items():
                self.tables[table] = copy.deepcopy(rows)
            self.bulk_writes += 1
            if self.fail_bulk_after_once:
                self.fail_bulk_after_once = False
                raise OSError("simulated lost acknowledgement after atomic replacement")

    def _new_id(self, prefix):
        with self._lock:
            self._ids += 1
            return f"{prefix}-{self._ids}"


def _request(request_id: str, *, description: str = "Special advisory fee", amount=250):
    return {
        "requestId": request_id,
        "date": "2026-08-30",
        "description": description,
        "amount": amount,
        "matterId": MATTER_ID,
        "isFee": True,
    }


def _custom_fees(repo: _MemoryRepo):
    return [
        row
        for row in repo.tables[sc.TBL_TIME]
        if "FeeOrigin:InvoiceDraft" in str(row.get(sc.COL_TIME_LOCK_AUDIT) or "")
    ]


def test_one_request_is_idempotent_but_two_deliberate_requests_may_match_content():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)

    first = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_request_0001"))
    duplicate = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_request_0001"))
    second = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_request_0002"))

    assert first["entryId"] == duplicate["entryId"]
    assert duplicate["alreadyCreated"] is True
    assert second["entryId"] != first["entryId"]
    assert len(_custom_fees(repo)) == 2
    assert {row[sc.COL_TIME_MATTER_ID] for row in _custom_fees(repo)} == {MATTER_ID}


def test_simultaneous_duplicate_calls_create_one_stable_line():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda _: service.add_custom_fee_line(
                    DRAFT_NUM,
                    _request("CFR_concurrent_0001"),
                ),
                range(6),
            )
        )

    assert len({result["entryId"] for result in results}) == 1
    assert len(_custom_fees(repo)) == 1


def test_lost_write_acknowledgement_recovers_and_same_request_retry_is_safe():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    repo.fail_bulk_after_once = True

    recovered = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_uncertain_0001"))
    retried = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_uncertain_0001"))

    assert recovered["recovered"] is True
    assert recovered["entryId"] == retried["entryId"]
    assert len(_custom_fees(repo)) == 1


def test_failed_add_before_atomic_write_retries_with_same_request_without_duplicate():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    repo.fail_bulk_before_once = True

    with pytest.raises(RuntimeError, match="Retry this same request"):
        service.add_custom_fee_line(DRAFT_NUM, _request("CFR_retry_before01"))
    assert _custom_fees(repo) == []

    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_retry_before01"))
    assert created["alreadyCreated"] is False
    assert len(_custom_fees(repo)) == 1


def test_disbursement_represented_matter_is_valid_without_an_existing_time_line():
    repo = _MemoryRepo()
    repo.tables[sc.TBL_TIME] = []
    service = InvoiceDraftService(repo)

    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_disb_only_001"))

    assert created["ok"] is True
    assert _custom_fees(repo)[0][sc.COL_TIME_MATTER_ID] == MATTER_ID


def test_edit_preserves_identity_and_reopen_does_not_duplicate():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_edit_00000001"))

    service.update_line_item(
        DRAFT_NUM,
        created["entryId"],
        {"description": "Revised special fee", "amount": 300},
    )
    reopened = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_edit_00000001"))
    row = _custom_fees(repo)[0]

    assert reopened["entryId"] == created["entryId"]
    assert len(_custom_fees(repo)) == 1
    assert row[sc.COL_TIME_DESC] == "Revised special fee"
    assert row[sc.COL_TIME_NET] == "300.00"
    assert row[sc.COL_TIME_LOCK_AUDIT].count("RequestID:CFR_edit_00000001") == 1


def test_replay_refuses_a_billed_fee_while_its_owner_draft_still_exists():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_split_guard_01"))
    row = next(
        item for item in repo.tables[sc.TBL_TIME]
        if item[sc.COL_TIME_ENTRY_ID] == created["entryId"]
    )
    row[sc.COL_TIME_INVOICE_REF] = "26-PARTIAL"
    row[sc.COL_TIME_INVOICE_STATUS] = "Billed"
    row[sc.COL_TIME_STATUS] = "Billed"
    row[sc.COL_TIME_LOCK_AUDIT] = row[sc.COL_TIME_LOCK_AUDIT].replace(
        "CustomFeeState:Draft",
        "CustomFeeState:Finalized || FinalInvoice:26-PARTIAL",
    )

    with pytest.raises(RuntimeError, match="billed-and-draft state"):
        service.add_custom_fee_line(DRAFT_NUM, _request("CFR_split_guard_01"))

    assert len(_custom_fees(repo)) == 1


def test_remove_deletes_only_exact_custom_fee_and_releases_ordinary_wip():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    first = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_remove_00001"))
    second = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_remove_00002"))

    result = service.remove_line_item(DRAFT_NUM, first["entryId"], False)
    assert result["removedCustomFee"] is True
    assert [row[sc.COL_TIME_ENTRY_ID] for row in _custom_fees(repo)] == [second["entryId"]]
    assert any(row[sc.COL_TIME_ENTRY_ID] == "TIME-ORDINARY-1" for row in repo.tables[sc.TBL_TIME])

    with pytest.raises(ValueError, match="Only an exclusively draft-owned custom fee"):
        service.remove_line_item(DRAFT_NUM, "TIME-ORDINARY-1", True)
    ordinary = next(row for row in repo.tables[sc.TBL_TIME] if row[sc.COL_TIME_ENTRY_ID] == "TIME-ORDINARY-1")
    assert ordinary[sc.COL_TIME_INVOICE_REF] == DRAFT_NUM

    released = service.remove_line_item(DRAFT_NUM, "TIME-ORDINARY-1", False)
    assert released["releasedToWip"] is True
    ordinary = next(row for row in repo.tables[sc.TBL_TIME] if row[sc.COL_TIME_ENTRY_ID] == "TIME-ORDINARY-1")
    assert ordinary[sc.COL_TIME_INVOICE_REF] == ""
    assert ordinary[sc.COL_TIME_STATUS] == "Unbilled"


def test_abandon_draft_destroys_custom_fee_but_releases_ordinary_work():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    service.add_custom_fee_line(DRAFT_NUM, _request("CFR_abandon_0001"))

    assert service.delete_draft(DRAFT_NUM) is True

    assert _custom_fees(repo) == []
    ordinary = next(row for row in repo.tables[sc.TBL_TIME] if row[sc.COL_TIME_ENTRY_ID] == "TIME-ORDINARY-1")
    assert ordinary[sc.COL_TIME_INVOICE_REF] == ""
    assert ordinary[sc.COL_TIME_STATUS] == "Unbilled"
    assert repo.tables[sc.TBL_DISBURSEMENTS][0][sc.COL_DISB_INVOICE_REF] == ""
    assert repo.tables[sc.TBL_DRAFT_INVOICES] == []


def test_financial_dependency_blocks_custom_fee_edit_remove_and_draft_delete():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_dependency_01"))
    repo.tables[sc.TBL_TRANSACTIONS_MASTER].append({"CustomFeeLink": created["entryId"]})
    before = copy.deepcopy(repo.tables)

    with pytest.raises(ValueError, match="financial dependency"):
        service.update_line_item(DRAFT_NUM, created["entryId"], {"amount": 400})
    with pytest.raises(ValueError, match="financial dependency"):
        service.remove_line_item(DRAFT_NUM, created["entryId"], False)
    with pytest.raises(ValueError, match="financial dependency"):
        service.delete_draft(DRAFT_NUM)

    assert repo.tables == before


def test_finalize_is_exactly_once_and_retry_recognizes_completed_footprint():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_finalize_0001"))

    assert service.finalize_draft(DRAFT_NUM, "26-8001", "") is True
    retry = service.finalize_draft(DRAFT_NUM, "26-8001", "")

    assert retry["alreadyFinalized"] is True
    assert len(repo.tables[sc.TBL_RECEIVABLES]) == 1
    assert len(repo.tables[sc.TBL_INVOICE_LOG]) == 1
    assert len(repo.tables[sc.TBL_LEDGER]) == 1
    finalized = next(
        row for row in repo.tables[sc.TBL_TIME]
        if row[sc.COL_TIME_ENTRY_ID] == created["entryId"]
    )
    assert finalized[sc.COL_TIME_INVOICE_REF] == "26-8001"
    assert finalized[sc.COL_TIME_STATUS] == "Billed"
    assert "CustomFeeState:Finalized" in finalized[sc.COL_TIME_LOCK_AUDIT]
    assert "FinalInvoice:26-8001" in finalized[sc.COL_TIME_LOCK_AUDIT]
    assert finalized[sc.COL_TIME_MATTER_ID] == MATTER_ID
    with pytest.raises(RuntimeError, match="completion footprint is inconsistent"):
        service.finalize_draft(DRAFT_NUM, "26-DIFFERENT", "")


def test_finalize_recovers_lost_acknowledgement_without_billed_and_draft_split():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    service.add_custom_fee_line(DRAFT_NUM, _request("CFR_finalize_lost1"))
    repo.fail_bulk_after_once = True

    result = service.finalize_draft(DRAFT_NUM, "26-8002", "")
    retried = service.finalize_draft(DRAFT_NUM, "26-8002", "")

    assert result["alreadyFinalized"] is True
    assert retried["alreadyFinalized"] is True
    assert repo.tables[sc.TBL_DRAFT_INVOICES] == []
    assert len(repo.tables[sc.TBL_RECEIVABLES]) == 1
    assert len(repo.tables[sc.TBL_INVOICE_LOG]) == 1
    assert len(repo.tables[sc.TBL_LEDGER]) == 1


def test_failed_finalize_before_atomic_write_keeps_draft_and_retry_succeeds():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    created = service.add_custom_fee_line(DRAFT_NUM, _request("CFR_finalize_fail1"))
    before = copy.deepcopy(repo.tables)
    repo.fail_bulk_before_once = True

    with pytest.raises(RuntimeError, match="Retry with the same invoice number"):
        service.finalize_draft(DRAFT_NUM, "26-8003", "")
    assert repo.tables == before

    assert service.finalize_draft(DRAFT_NUM, "26-8003", "") is True
    finalized = next(
        row for row in repo.tables[sc.TBL_TIME]
        if row[sc.COL_TIME_ENTRY_ID] == created["entryId"]
    )
    assert finalized[sc.COL_TIME_INVOICE_REF] == "26-8003"
    assert not any(
        row.get(sc.COL_TIME_INVOICE_REF) == DRAFT_NUM
        for row in repo.tables[sc.TBL_TIME]
    )


def test_qml_and_controller_use_request_identity_pending_guard_and_real_matter():
    view = (PROJECT_ROOT / "src" / "qml" / "views" / "InvoiceBuilderView.qml").read_text(
        encoding="utf-8"
    )
    controller = (
        PROJECT_ROOT / "src" / "python" / "backend" / "controllers" / "billing_controller.py"
    ).read_text(encoding="utf-8")

    assert '"matterId": "Custom Fee"' not in view
    assert "newCustomFeeRequestId" in view
    assert "submissionPending" in view
    assert "customFeeMatterOptions" in view
    assert "draftMatterOptions" in view
    assert "addDraftCustomFee" in view
    assert "customFeeLineCompleted" in controller
    assert "_custom_fee_requests_in_progress" in controller
    assert '"matterOptions": matter_options' in controller
    assert "COL_DISB_INVOICE_REF" in controller
