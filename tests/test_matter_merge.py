from copy import deepcopy
from pathlib import Path

from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_DISBURSEMENTS,
    TBL_MATTERS,
    TBL_TIME,
    TBL_TRANSACTIONS_MASTER,
)


class _MemoryMatterMergeRepo:
    """Small in-memory contract for the matter-merge table update path."""

    def __init__(self):
        self.tables = {
            TBL_MATTERS.table: [
                {
                    sc.COL_MATTER_ID: "source-matter",
                    sc.COL_MATTER_STATUS: "Active",
                    sc.COL_MATTER_NOTES: "",
                    sc.COL_MATTER_UPDATED: "",
                    "displayName": "Source Matter",
                    "matterName": "Source Matter",
                    "matterNumber": "SRC-001",
                },
                {
                    sc.COL_MATTER_ID: "target-matter",
                    sc.COL_MATTER_STATUS: "Active",
                    sc.COL_MATTER_NOTES: "",
                    sc.COL_MATTER_UPDATED: "",
                    "displayName": "Target Matter",
                    "matterName": "Target Matter",
                    "matterNumber": "TGT-001",
                },
            ],
            TBL_TIME.table: [{sc.COL_TIME_MATTER_ID: "source-matter", sc.COL_TIME_LOCK_AUDIT: ""}],
            TBL_DISBURSEMENTS.table: [{sc.COL_DISB_MATTER_ID: "source-matter"}],
            TBL_TRANSACTIONS_MASTER.table: [
                {
                    sc.COL_TXN_MATTER: "source-matter",
                    sc.COL_TXN_UPDATED_AT: "",
                    sc.COL_TXN_NOTES: "",
                }
            ],
        }

    def ensure_schema(self):
        return None

    def _read_table_rows(self, table):
        return deepcopy(self.tables[table.table])

    def _replace_table_rows(self, table, rows):
        self.tables[table.table] = deepcopy(rows)

    def _find_matter_row(self, matter_id):
        for row in self.tables[TBL_MATTERS.table]:
            if row[sc.COL_MATTER_ID] == matter_id:
                return deepcopy(row)
        return None

    def check_matter_dependencies(self, _matter_id):
        return {
            "ok": True,
            "canDelete": True,
            "totalDependencies": 0,
        }

    def _delete_row_by_key_hard(self, table, key_column, key_value):
        before = self.tables[table.table]
        after = [row for row in before if row.get(key_column) != key_value]
        self.tables[table.table] = after
        return len(after) != len(before)

    @staticmethod
    def _canonicalize_matter_row(row):
        return dict(row)

    @staticmethod
    def _canonicalize_time_row(row):
        return dict(row)

    @staticmethod
    def _canonicalize_row(_table, row):
        return dict(row)

    @staticmethod
    def _canonicalize_transaction_row(row):
        return dict(row)

    @staticmethod
    def _append_note_line(existing, note):
        return f"{existing}\n{note}".strip()

    def get_matter_profile(self, matter_id):
        for row in self.tables[TBL_MATTERS.table]:
            if row[sc.COL_MATTER_ID] == matter_id:
                return {
                    "ok": True,
                    "matter": {
                        "matterId": row[sc.COL_MATTER_ID],
                        "displayName": row["displayName"],
                        "matterName": row["matterName"],
                        "matterNumber": row["matterNumber"],
                        "status": row[sc.COL_MATTER_STATUS],
                    },
                }
        return {"ok": False}


def test_matter_merge_reassigns_disbursements_with_the_generic_canonicalizer():
    repo = _MemoryMatterMergeRepo()

    result = ExcelRepo._merge_duplicate_matters(
        repo,
        {"sourceKey": "source-matter", "targetKey": "target-matter"},
    )

    assert result["ok"] is True
    assert result["counts"] == {
        "matters": 1,
        "timeEntries": 1,
        "disbursements": 1,
        "transactions": 1,
    }
    assert repo.tables[TBL_DISBURSEMENTS.table][0][sc.COL_DISB_MATTER_ID] == "target-matter"
    assert repo.tables[TBL_MATTERS.table][0][sc.COL_MATTER_STATUS] == "Archived"


def test_merge_success_dialog_requires_a_second_delete_confirmation_and_reports_feedback():
    dialog_source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "qml"
        / "views"
        / "placeholder"
        / "MatterMergeSuccessDialog.qml"
    ).read_text(encoding="utf-8")

    assert "function requestPermanentDelete()" in dialog_source
    assert "function permanentlyDeleteMatter()" in dialog_source
    assert 'text: "Delete permanently…"' in dialog_source
    assert "onClicked: rootDialog.requestPermanentDelete()" in dialog_source
    assert 'text: rootDialog.actionInProgress ? "Deleting…" : "Delete permanently"' in dialog_source
    assert 'rootDialog.finishAction("Old matter permanently deleted.", "success")' in dialog_source
    assert 'rootDialog.finishAction("Matter kept archived.", "success")' in dialog_source
    assert "SemanticTheme.destructive" in dialog_source


def test_archived_matter_delete_rejects_active_matters_and_deletes_only_when_safe():
    repo = _MemoryMatterMergeRepo()

    active_result = ExcelRepo.delete_archived_matter_profile(repo, "source-matter")
    assert active_result["ok"] is False
    assert "Only archived matters" in active_result["message"]

    repo.tables[TBL_MATTERS.table][0][sc.COL_MATTER_STATUS] = "Archived"
    deleted_result = ExcelRepo.delete_archived_matter_profile(repo, "source-matter")
    assert deleted_result["ok"] is True
    assert repo._find_matter_row("source-matter") is None


def test_archived_delete_is_available_from_the_directory_and_profile_with_confirmation():
    root = Path(__file__).resolve().parents[1]
    directory_source = (root / "src" / "qml" / "views" / "placeholder" / "MatterDirectoryPanel.qml").read_text(encoding="utf-8")
    profile_source = (root / "src" / "qml" / "views" / "placeholder" / "MatterProfilePanel.qml").read_text(encoding="utf-8")
    dialog_source = (root / "src" / "qml" / "views" / "placeholder" / "ArchivedMatterDeleteDialog.qml").read_text(encoding="utf-8")

    assert 'text: "Delete archived matter…"' in directory_source
    assert "mouse.button === Qt.RightButton && matterDirectoryRow.archived" in directory_source
    assert "ArchivedMatterDeleteDialog" in directory_source
    assert 'text: "Delete Archived"' in profile_source
    assert "ArchivedMatterDeleteDialog" in profile_source
    assert "checkMatterDependencies(rootDialog.matterId)" in dialog_source
    assert "deleteArchivedMatterProfile(rootDialog.matterId)" in dialog_source
    assert 'text: rootDialog.deleting ? "Deleting…" : "Delete permanently"' in dialog_source
