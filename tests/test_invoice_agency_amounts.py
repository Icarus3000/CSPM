from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from backend.controllers.billing_controller import BillingController
from domain import schema_constants as sc
from services.invoice_document_service import InvoiceDocumentService
from services.invoice_draft_service import InvoiceDraftService


INVOICE_NUM = "26-9990"
CLIENT_ID = "CLIENT-SHARE-TEST"
PARENT_ID = "PARENT-SHARE-TEST"
MATTER_ID = "MATTER-SHARE-TEST"


class _MemoryRepo:
    def __init__(self):
        self.bulk_writes = 0
        self.single_writes = 0
        self.fail_bulk = False
        self.tables = {
            sc.TBL_TIME: [self._time_row(index, gross, net, tax) for index, gross, net, tax in (
                (1, "212.50", "148.75", "19.34"),
                (2, "425.00", "297.50", "38.68"),
                (3, "382.50", "267.75", "34.81"),
                (4, "977.50", "684.25", "88.95"),
            )],
            sc.TBL_DISBURSEMENTS: [],
            sc.TBL_DRAFT_INVOICES: [],
            sc.TBL_INVOICE_LOG: [],
            sc.TBL_RECEIVABLES: [],
            sc.TBL_LEDGER: [],
            sc.TBL_TRANSACTIONS_MASTER: [],
            sc.TBL_MATTERS: [{
                sc.COL_MATTER_ID: MATTER_ID,
                sc.COL_MATTER_CLIENT_ID: CLIENT_ID,
                sc.COL_MATTER_NAME: "Synthetic share matter",
            }],
        }

    @staticmethod
    def _time_row(index, gross, net, tax):
        return {
            sc.COL_TIME_ENTRY_ID: f"SHARE-T-{index}",
            sc.COL_TIME_DATE: "2026-09-01",
            sc.COL_TIME_CLIENT_ID: CLIENT_ID,
            sc.COL_TIME_MATTER_ID: MATTER_ID,
            sc.COL_TIME_DESC: f"Synthetic work {index}",
            sc.COL_TIME_HOURS: "1.0",
            sc.COL_TIME_RATE: gross,
            sc.COL_TIME_SHARE_PCT: "70",
            sc.COL_TIME_GROSS: gross,
            sc.COL_TIME_NET: net,
            sc.COL_TIME_HST: tax,
            sc.COL_TIME_TOTAL: str(Decimal(net) + Decimal(tax)),
            sc.COL_TIME_STATUS: "Unbilled",
            sc.COL_TIME_INVOICE_STATUS: "Unbilled",
            sc.COL_TIME_INVOICE_REF: "",
            sc.COL_TIME_LOCK_AUDIT: "",
        }

    def _read_table_rows(self, table):
        return deepcopy(self.tables.get(getattr(table, "table", table), []))

    def _read_table_rows_bulk(self, tables):
        return {table: self._read_table_rows(table) for table in tables}

    def _write_table_rows(self, table, rows):
        self.single_writes += 1
        self.tables[table] = deepcopy(rows)

    def _write_table_rows_bulk(self, table_rows):
        if self.fail_bulk:
            raise OSError("synthetic atomic replacement failure")
        self.bulk_writes += 1
        for table, rows in table_rows.items():
            self.tables[table] = deepcopy(rows)

    def _new_id(self, prefix):
        return f"{prefix}-SHARE-TEST"

    def get_client_profile(self, client_id):
        if str(client_id) == PARENT_ID:
            return {"ok": True, "client": {
                "clientId": PARENT_ID, "clientName": "LIHDC Professional Corporation",
            }}
        if str(client_id) == CLIENT_ID:
            return {"ok": True, "client": {
                "clientId": CLIENT_ID, "clientName": "Synthetic Share Client",
                "parentClientId": PARENT_ID, "parentClientName": "LIHDC Professional Corporation",
            }}
        return {"ok": False}

    def get_matter_profile(self, matter_id):
        return {"ok": True, "matter": {
            "matterId": MATTER_ID, "clientId": CLIENT_ID,
            "matterName": "Synthetic share matter", "matterNumber": "TEST-SHARE-1",
        }}


def _draft(repo, service):
    return service.create_draft(
        CLIENT_ID, "Synthetic Share Client",
        [row[sc.COL_TIME_ENTRY_ID] for row in repo.tables[sc.TBL_TIME]],
    )


def _payload(repo, service, draft_num):
    documents = InvoiceDocumentService(str(PROJECT_ROOT / "src" / "templates" / "invoices"))
    return BillingController(repo, service, documents)._build_invoice_payload(draft_num)


def _corrupt_invoice():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    service.finalize_draft(_draft(repo, service), INVOICE_NUM, "")
    invoice = repo.tables[sc.TBL_INVOICE_LOG][0]
    invoice[sc.COL_INV_TOTAL_FEES] = "978.78"
    invoice[sc.COL_INV_TOTAL_TAX] = "127.24"
    invoice[sc.COL_INV_AGGREGATE_BILLED] = "1106.02"
    receivable = repo.tables[sc.TBL_RECEIVABLES][0]
    receivable[sc.COL_RECV_TOTAL_INVOICED] = "1106.02"
    receivable[sc.COL_RECV_BALANCE_DUE] = "1106.02"
    ledger = repo.tables[sc.TBL_LEDGER][0]
    ledger[sc.COL_LEDGER_BILLINGS_EXCL_HST] = "978.78"
    ledger[sc.COL_LEDGER_HST_COLLECTED] = "127.24"
    ledger[sc.COL_LEDGER_RECEIVABLE] = "1106.02"
    for row in repo.tables[sc.TBL_TIME]:
        row[sc.COL_TIME_INVOICE_TOTAL] = "1106.02"
        row[sc.COL_TIME_INVOICE_BALANCE_DUE] = "1106.02"
    repo.bulk_writes = 0
    repo.single_writes = 0
    return repo, service


def test_parent_lihdc_split_uses_gross_once_and_matches_document_aggregate_hst():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    draft_num = _draft(repo, service)
    draft = service.get_draft(draft_num)
    payload = _payload(repo, service, draft_num)

    assert draft[sc.COL_DRAFT_AGENCY_SPLIT_PERCENT] == "30.0"
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "1398.25"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "181.77"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "1580.02"
    assert payload["gross_professional_fees"] == 1997.5
    assert payload["net_professional_fees"] == 1398.25
    assert payload["total_tax"] == 181.77
    assert payload["total_due"] == 1580.02
    assert sum(Decimal(row[sc.COL_TIME_HST]) for row in repo.tables[sc.TBL_TIME]) == Decimal("181.78")


def test_finalization_recalculates_stale_double_deduction_totals():
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    draft_num = _draft(repo, service)
    draft = repo.tables[sc.TBL_DRAFT_INVOICES][0]
    draft[sc.COL_DRAFT_TOTAL_FEES] = "978.78"
    draft[sc.COL_DRAFT_TOTAL_TAX] = "127.24"
    draft[sc.COL_DRAFT_TOTAL_DUE] = "1106.02"
    earned = [(row[sc.COL_TIME_NET], row[sc.COL_TIME_HST]) for row in repo.tables[sc.TBL_TIME]]

    assert service.finalize_draft(draft_num, INVOICE_NUM, "") is True
    assert repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_TOTAL_FEES] == "1398.25"
    assert repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_TOTAL_TAX] == "181.77"
    assert repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_AGGREGATE_BILLED] == "1580.02"
    assert repo.tables[sc.TBL_RECEIVABLES][0][sc.COL_RECV_BALANCE_DUE] == "1580.02"
    assert repo.tables[sc.TBL_LEDGER][0][sc.COL_LEDGER_RECEIVABLE] == "1580.02"
    assert [(row[sc.COL_TIME_NET], row[sc.COL_TIME_HST]) for row in repo.tables[sc.TBL_TIME]] == earned
    assert {row[sc.COL_TIME_INVOICE_TOTAL] for row in repo.tables[sc.TBL_TIME]} == {"1580.02"}


def test_half_cent_hst_uses_identical_decimal_rounding_for_document_and_accounting():
    repo = _MemoryRepo()
    repo.tables[sc.TBL_TIME] = [repo._time_row(1, "2635.00", "1844.50", "239.78")]
    service = InvoiceDraftService(repo)
    draft_num = _draft(repo, service)
    draft = service.get_draft(draft_num)
    payload = _payload(repo, service, draft_num)
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "239.79"
    assert payload["total_tax"] == 239.79
    assert payload["total_due"] == 2084.29
    assert service.finalize_draft(draft_num, INVOICE_NUM, "") is True
    assert repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_AGGREGATE_BILLED] == "2084.29"


@pytest.mark.parametrize("split,fees,tax,total", [
    ("20", "1598.00", "207.74", "1805.74"),
    ("0", "1997.50", "259.68", "2257.18"),
])
def test_explicit_split_changes_match_document_and_do_not_use_stored_lawyer_share(split, fees, tax, total):
    repo = _MemoryRepo()
    service = InvoiceDraftService(repo)
    draft_num = _draft(repo, service)
    service.apply_agency_split(draft_num, Decimal(split))
    draft = service.get_draft(draft_num)
    payload = _payload(repo, service, draft_num)
    assert draft[sc.COL_DRAFT_TOTAL_FEES] == fees
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == tax
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == total
    assert payload["total_due"] == pytest.approx(float(total))


def test_targeted_repair_is_atomic_audited_and_idempotent():
    repo, service = _corrupt_invoice()
    unrelated = {sc.COL_INV_INVOICE_NUM: "26-9991", sc.COL_INV_AGGREGATE_BILLED: "22.60"}
    repo.tables[sc.TBL_INVOICE_LOG].append(deepcopy(unrelated))
    original_snapshot = json.loads(repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_BILL_TO_SNAPSHOT])
    original_snapshot["customPreservedData"] = {"value": "preserve"}
    repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_BILL_TO_SNAPSHOT] = json.dumps(original_snapshot)
    before_time = deepcopy(repo.tables[sc.TBL_TIME])

    result = service.repair_finalized_invoice_amounts(
        INVOICE_NUM, expected_total="1580.02", reason="Synthetic double agency deduction correction"
    )
    assert result["total"] == 1580.02
    assert result["tax"] == 181.77
    assert result["updated"] is True
    assert repo.bulk_writes == 1
    assert repo.single_writes == 0
    assert repo.tables[sc.TBL_INVOICE_LOG][1] == unrelated
    for old, new in zip(before_time, repo.tables[sc.TBL_TIME]):
        for key, value in old.items():
            if key not in {sc.COL_TIME_INVOICE_TOTAL, sc.COL_TIME_INVOICE_BALANCE_DUE}:
                assert new[key] == value
    snapshot = json.loads(repo.tables[sc.TBL_INVOICE_LOG][0][sc.COL_INV_BILL_TO_SNAPSHOT])
    assert {key: snapshot[key] for key in original_snapshot} == original_snapshot
    assert snapshot["amountCorrections"][0]["before"]["total"] == "1106.02"
    assert snapshot["amountCorrections"][0]["after"]["total"] == "1580.02"

    saved = deepcopy(repo.tables)
    assert service.repair_finalized_invoice_amounts(INVOICE_NUM, expected_total="1580.02")["updated"] is False
    assert repo.tables == saved
    assert repo.bulk_writes == 1


@pytest.mark.parametrize("expected", ["1580.03", "1106.02", "0", "NaN", "invalid"])
def test_targeted_repair_rejects_unverified_expected_total_without_write(expected):
    repo, service = _corrupt_invoice()
    before = deepcopy(repo.tables)
    with pytest.raises(ValueError):
        service.repair_finalized_invoice_amounts(INVOICE_NUM, expected_total=expected)
    assert repo.tables == before
    assert repo.bulk_writes == 0


@pytest.mark.parametrize("unsafe", ["paid", "credit", "void", "duplicate", "discount", "transaction"])
def test_targeted_repair_refuses_ambiguous_or_nonactive_financial_history(unsafe):
    repo, service = _corrupt_invoice()
    if unsafe == "paid":
        repo.tables[sc.TBL_RECEIVABLES][0][sc.COL_RECV_AMOUNT_PAID] = "1.00"
    elif unsafe == "credit":
        repo.tables[sc.TBL_RECEIVABLES][0][sc.COL_RECV_CREDITS_ADJ] = "1.00"
    elif unsafe == "void":
        repo.tables[sc.TBL_RECEIVABLES][0][sc.COL_RECV_STATUS] = "Void"
    elif unsafe == "duplicate":
        repo.tables[sc.TBL_INVOICE_LOG].append(deepcopy(repo.tables[sc.TBL_INVOICE_LOG][0]))
    elif unsafe == "discount":
        repo.tables[sc.TBL_TIME][0][sc.COL_TIME_LOCK_AUDIT] = "EntryType:InvoiceAdjustment"
    else:
        repo.tables[sc.TBL_TRANSACTIONS_MASTER].append({sc.COL_TXN_INVOICE_REF: INVOICE_NUM})
    before = deepcopy(repo.tables)
    with pytest.raises(ValueError):
        service.repair_finalized_invoice_amounts(INVOICE_NUM, expected_total="1580.02")
    assert repo.tables == before
    assert repo.bulk_writes == 0


def test_atomic_repair_failure_does_not_partially_update_tables():
    repo, service = _corrupt_invoice()
    before = deepcopy(repo.tables)
    repo.fail_bulk = True
    with pytest.raises(OSError, match="atomic replacement"):
        service.repair_finalized_invoice_amounts(INVOICE_NUM, expected_total="1580.02")
    assert repo.tables == before
    assert repo.single_writes == 0


def test_historical_repair_preserves_verified_issued_document_half_cent_tax():
    repo, service = _corrupt_invoice()
    row = repo.tables[sc.TBL_TIME][0]
    row[sc.COL_TIME_GROSS] = "2635.00"
    row[sc.COL_TIME_NET] = "1844.50"
    row[sc.COL_TIME_HST] = "239.78"
    row[sc.COL_TIME_TOTAL] = "2084.28"
    repo.tables[sc.TBL_TIME] = [row]
    result = service.repair_finalized_invoice_amounts(
        INVOICE_NUM, expected_total="2084.28", expected_tax="239.78",
        reason="Preserve verified issued PDF rounding",
    )
    assert result["fees"] == 1844.5
    assert result["tax"] == 239.78
    assert result["total"] == 2084.28
    assert repo.tables[sc.TBL_TIME][0][sc.COL_TIME_HST] == "239.78"
    assert repo.tables[sc.TBL_RECEIVABLES][0][sc.COL_RECV_BALANCE_DUE] == "2084.28"


@pytest.mark.parametrize("expected_total,expected_tax", [
    (None, "181.77"), ("1580.02", "181.75"), ("1580.02", "NaN"),
    ("1580.02", "invalid"), ("1580.02", "181.78"),
])
def test_historical_tax_override_requires_matching_confirmed_total_and_rounding_only(expected_total, expected_tax):
    repo, service = _corrupt_invoice()
    before = deepcopy(repo.tables)
    with pytest.raises(ValueError):
        service.repair_finalized_invoice_amounts(
            INVOICE_NUM, expected_total=expected_total, expected_tax=expected_tax,
        )
    assert repo.tables == before
    assert repo.bulk_writes == 0


def test_targeted_repair_keeps_tax_exempt_disbursements_out_of_aggregate_hst():
    repo, service = _corrupt_invoice()
    repo.tables[sc.TBL_DISBURSEMENTS] = [
        {sc.COL_DISB_ID: "EXEMPT", sc.COL_DISB_AMOUNT: "10.00",
         sc.COL_DISB_TAX_EXEMPT: "True", sc.COL_DISB_INVOICE_REF: INVOICE_NUM},
        {sc.COL_DISB_ID: "TAXABLE", sc.COL_DISB_AMOUNT: "20.00",
         sc.COL_DISB_TAX_EXEMPT: "False", sc.COL_DISB_INVOICE_REF: INVOICE_NUM},
    ]
    disbursements = deepcopy(repo.tables[sc.TBL_DISBURSEMENTS])
    result = service.repair_finalized_invoice_amounts(INVOICE_NUM, expected_total="1612.62")
    assert result["tax"] == 184.37
    assert result["disbursements"] == 30.0
    assert repo.tables[sc.TBL_DISBURSEMENTS] == disbursements
