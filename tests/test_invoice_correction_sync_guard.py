from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from domain.ap_schema import AP_BILLS_SHEET, AP_PAYMENTS_SHEET
from services.financial_sync_service import FinancialSyncError, FinancialSyncService
from services.paths import AppPaths


INVOICE = "26-9992"


def source_rows():
    rows = {name: [] for name in FinancialSyncService.SOURCE_SHEETS}
    rows["Dockets"] = [{"Date": "2026-08-31"}]
    rows["Ledger"] = [{"Date": "2026-08-31"}]
    return rows


def target_rows(correction="billingCorrections", invoice_date="2026-07-31"):
    rows = {name: [] for name in (
        "Parents", "Clients", "ClientProfiles", "Matters", "TimeEntries", "Dockets",
        "Disbursements", "Ledger", "Receivables", "Invoice Log", "HST_Log", "Transactions",
        "TransactionAccounts", "TransactionCategories", AP_BILLS_SHEET, AP_PAYMENTS_SHEET,
    )}
    rows["Invoice Log"] = [{
        sc.COL_INV_INVOICE_NUM: INVOICE,
        sc.COL_INV_INVOICE_DATE: invoice_date,
        sc.COL_INV_BILL_TO_SNAPSHOT: json.dumps({correction: [{"reason": "Synthetic audited correction"}]}),
    }]
    return rows


@pytest.mark.parametrize("correction", ["billingCorrections", "amountCorrections"])
def test_historical_invoice_correction_requires_review(correction):
    source, target = source_rows(), target_rows(correction)
    before = deepcopy(target)
    assert FinancialSyncService._audited_invoice_replacement_conflicts(source, target) == [INVOICE]
    assert target == before


@pytest.mark.parametrize("table,column", [
    ("Invoice Log", "Invoice #"), ("Receivables", "InvoiceNum"),
    ("Dockets", "Invoice #"), ("Ledger", "Reference"), ("Disbursements", "Invoice"),
])
def test_source_invoice_overlap_blocks_even_a_later_correction(table, column):
    source, target = source_rows(), target_rows(invoice_date="2026-09-30")
    source[table].append({column: INVOICE.lower()})
    assert FinancialSyncService._audited_invoice_replacement_conflicts(source, target) == [INVOICE]


@pytest.mark.parametrize("table,reference,dated", [
    ("Receivables", sc.COL_RECV_INVOICE_NUM, sc.COL_RECV_DATE),
    ("TimeEntries", sc.COL_TIME_INVOICE_REF, sc.COL_TIME_DATE),
    ("Disbursements", sc.COL_DISB_INVOICE_REF, sc.COL_DISB_DATE),
    ("Ledger", sc.COL_LEDGER_REFERENCE, sc.COL_LEDGER_DATE),
    ("Transactions", sc.COL_TXN_INVOICE_REF, sc.COL_TXN_DATE),
])
def test_linked_historical_rows_block_even_when_invoice_log_would_survive(table, reference, dated):
    source, target = source_rows(), target_rows(invoice_date="2026-09-30")
    target[table] = [{reference: INVOICE, dated: "2026-08-31"}]
    assert FinancialSyncService._audited_invoice_replacement_conflicts(source, target) == [INVOICE]


def test_unrelated_post_cutoff_correction_remains_allowed():
    source, target = source_rows(), target_rows(invoice_date="2026-09-30")
    target["TimeEntries"] = [{sc.COL_TIME_INVOICE_REF: INVOICE, sc.COL_TIME_DATE: "2026-09-01"}]
    target["Ledger"] = [{sc.COL_LEDGER_REFERENCE: INVOICE, sc.COL_LEDGER_DATE: "2026-09-30"}]
    assert FinancialSyncService._audited_invoice_replacement_conflicts(source, target) == []


@pytest.mark.parametrize("snapshot", ["", "invalid", "[]", '{"billingCorrections":[]}'])
def test_ordinary_invoice_without_audited_correction_uses_existing_sync_policy(snapshot):
    target = target_rows()
    target["Invoice Log"][0][sc.COL_INV_BILL_TO_SNAPSHOT] = snapshot
    assert FinancialSyncService._audited_invoice_replacement_conflicts(source_rows(), target) == []


def test_preview_and_candidate_build_refuse_without_copying_or_writing(tmp_path, monkeypatch):
    source_file, target_file = tmp_path / "source.xlsm", tmp_path / "CSPM.xlsm"
    source_file.write_bytes(b"SYNTHETIC-SOURCE")
    target_file.write_bytes(b"SYNTHETIC-TARGET")
    service = FinancialSyncService(AppPaths(tmp_path, tmp_path))
    monkeypatch.setattr(service, "_read_source", lambda _path: source_rows())
    monkeypatch.setattr(service, "_read_target", lambda _path: target_rows())
    preview = service.preview(source_file, target_file)
    assert preview["ok"] is False
    assert preview["summary"]["auditedInvoiceConflicts"] == [INVOICE]
    assert any("audited invoice corrections" in error for error in preview["errors"])
    output = tmp_path / "candidate"
    built = service.build_candidate(source_file, output, target_file)
    assert built["ok"] is False
    assert built["phase"] == "preview"
    assert not output.exists()
    assert source_file.read_bytes() == b"SYNTHETIC-SOURCE"
    assert target_file.read_bytes() == b"SYNTHETIC-TARGET"


def test_direct_candidate_application_refuses_before_workbook_save(tmp_path, monkeypatch):
    candidate = tmp_path / "CSPM.xlsm"
    candidate.write_bytes(b"SYNTHETIC-CANDIDATE")
    service = FinancialSyncService(AppPaths(tmp_path, tmp_path))
    monkeypatch.setattr(service, "_read_target", lambda _path: target_rows("amountCorrections"))
    def unexpected_open(*_args, **_kwargs):
        pytest.fail("The correction guard must refuse before opening the candidate for editing")
    monkeypatch.setattr("services.financial_sync_service.load_workbook", unexpected_open)
    with pytest.raises(FinancialSyncError, match="audited invoice corrections"):
        service._apply_to_candidate(source_rows(), candidate)
    assert candidate.read_bytes() == b"SYNTHETIC-CANDIDATE"
