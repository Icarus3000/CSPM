import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo, TBL_DRAFT_INVOICES, TBL_MATTERS, TBL_TIME


class _MemoryRepo:
    _append_note_line = ExcelRepo._append_note_line
    _ensure_matter_is_open_for_new_entry = ExcelRepo._ensure_matter_is_open_for_new_entry
    _is_matter_row_active = ExcelRepo._is_matter_row_active
    _money_round = ExcelRepo._money_round
    _parse_float = ExcelRepo._parse_float
    reconcile_wip_entries = ExcelRepo.reconcile_wip_entries
    reopen_matter_for_docketing = ExcelRepo.reopen_matter_for_docketing

    def __init__(self):
        self.tables = {
            TBL_TIME.table: [{
                sc.COL_TIME_ENTRY_ID: "T-1",
                sc.COL_TIME_STATUS: "Draft",
                sc.COL_TIME_INVOICE_STATUS: "Unbilled",
                sc.COL_TIME_INVOICE_REF: "SEE SUFFOLK 26-0080",
                sc.COL_TIME_LOCK_AUDIT: "Legacy transfer note",
            }],
            TBL_DRAFT_INVOICES.table: [],
            TBL_MATTERS.table: [{
                sc.COL_MATTER_ID: "M-1",
                sc.COL_MATTER_NUMBER: "BORK-LEVI-EST-26-0032",
                sc.COL_MATTER_NAME: "Wills & Estates",
                sc.COL_MATTER_STATUS: "Archived",
                sc.COL_MATTER_NOTES: "",
            }],
        }

    def ensure_schema(self):
        return None

    @staticmethod
    def _canonicalize_time_row(row):
        return dict(row)

    @staticmethod
    def _canonicalize_matter_row(row):
        return dict(row)

    def _read_table_rows(self, table_ref):
        table_name = getattr(table_ref, "table", table_ref)
        return [dict(row) for row in self.tables.get(table_name, [])]

    def _write_table_rows_bulk(self, table_rows):
        for table_ref, rows in table_rows.items():
            table_name = getattr(table_ref, "table", table_ref)
            self.tables[table_name] = [dict(row) for row in rows]

    def _find_matter_row(self, matter_id):
        for row in self.tables[TBL_MATTERS.table]:
            if row.get(sc.COL_MATTER_ID) == matter_id:
                return dict(row)
        return None


def test_reconcile_marks_historical_wip_read_only_and_keeps_audit_note():
    repo = _MemoryRepo()

    result = repo.reconcile_wip_entries(
        ["T-1"], "26-0080", "Historical transfer settled through Suffolk."
    )

    assert result["ok"] is True
    row = repo.tables[TBL_TIME.table][0]
    assert row[sc.COL_TIME_STATUS] == "Reconciled"
    assert row[sc.COL_TIME_INVOICE_STATUS] == "Reconciled"
    assert row[sc.COL_TIME_INVOICE_REF] == "26-0080"
    assert "Legacy transfer note" in row[sc.COL_TIME_LOCK_AUDIT]
    assert "WIP reconciled to 26-0080" in row[sc.COL_TIME_LOCK_AUDIT]


def test_reconcile_refuses_an_entry_attached_to_a_real_draft_invoice():
    repo = _MemoryRepo()
    repo.tables[TBL_TIME.table][0][sc.COL_TIME_INVOICE_REF] = "DRAFT-26-0032"
    repo.tables[TBL_DRAFT_INVOICES.table] = [{sc.COL_DRAFT_INVOICE_NUM: "DRAFT-26-0032"}]

    result = repo.reconcile_wip_entries(["T-1"], "26-0080", "Historical transfer.")

    assert result["ok"] is False
    assert "Delete or finalize" in result["message"]
    assert repo.tables[TBL_TIME.table][0][sc.COL_TIME_STATUS] == "Draft"


def test_reconcile_requires_explicit_confirmation_for_a_nonzero_total():
    repo = _MemoryRepo()
    repo.tables[TBL_TIME.table][0][sc.COL_TIME_NET] = 148.75

    blocked = repo.reconcile_wip_entries(["T-1"], "26-0080", "Historical transfer.")

    assert blocked["ok"] is False
    assert blocked["requiresNonzeroConfirmation"] is True
    assert blocked["selectedTotal"] == 148.75
    assert repo.tables[TBL_TIME.table][0][sc.COL_TIME_STATUS] == "Draft"

    confirmed = repo.reconcile_wip_entries(
        ["T-1"], "26-0080", "Intentional non-zero closure.", allow_nonzero_total=True
    )

    assert confirmed["ok"] is True
    assert confirmed["selectedTotal"] == 148.75


def test_archived_matter_requires_exact_phrase_and_reopen_is_audited():
    repo = _MemoryRepo()
    matter = repo.tables[TBL_MATTERS.table][0]

    with pytest.raises(ValueError, match="No time entry was saved"):
        repo._ensure_matter_is_open_for_new_entry(matter, "time")

    rejected = repo.reopen_matter_for_docketing("M-1", "time", "REOPEN BORK")
    assert rejected["ok"] is False
    assert repo.tables[TBL_MATTERS.table][0][sc.COL_MATTER_STATUS] == "Archived"

    reopened = repo.reopen_matter_for_docketing(
        "M-1", "time", "REOPEN BORK-LEVI-EST-26-0032"
    )
    assert reopened["ok"] is True
    saved = repo.tables[TBL_MATTERS.table][0]
    assert saved[sc.COL_MATTER_STATUS] == "Open"
    assert "Re-opened for a new time entry" in saved[sc.COL_MATTER_NOTES]
