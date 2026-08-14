import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    # Append so the repository's platform package cannot shadow stdlib platform.
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo


class _SummaryRepo:
    """Only the numeric helpers required by the pure summary calculation."""

    _money_round = ExcelRepo._money_round
    _parse_float = ExcelRepo._parse_float


class _DeleteGuardRepo:
    _matter_financial_blocker_message = ExcelRepo._matter_financial_blocker_message
    _matter_delete_blocker_message = ExcelRepo._matter_delete_blocker_message

    @staticmethod
    def check_matter_dependencies(_matter_id):
        return {
            "ok": True,
            "canDelete": False,
            "financialSummary": {
                "hasFinancialBlockers": True,
                "unbilledWipCount": 1,
                "unbilledWipAmount": 113.0,
                "unpaidInvoiceCount": 1,
                "unpaidInvoiceAmount": 226.0,
            },
        }


def test_matter_financial_summary_uses_the_matter_link_not_the_billing_client():
    repo = _SummaryRepo()
    summary = ExcelRepo._matter_financial_summary_from_rows(
        repo,
        "matter-1",
        [
            {
                sc.COL_TIME_ENTRY_ID: "T-unbilled",
                sc.COL_TIME_MATTER_ID: "matter-1",
                sc.COL_TIME_STATUS: "Draft",
                sc.COL_TIME_INVOICE_REF: "",
                sc.COL_TIME_TOTAL: 113.0,
            },
            {
                sc.COL_TIME_ENTRY_ID: "T-billed-1",
                sc.COL_TIME_MATTER_ID: "matter-1",
                sc.COL_TIME_STATUS: "Billed",
                sc.COL_TIME_INVOICE_REF: "26-0111",
                sc.COL_TIME_TOTAL: 226.0,
            },
            {
                sc.COL_TIME_ENTRY_ID: "T-other-matter",
                sc.COL_TIME_MATTER_ID: "matter-2",
                sc.COL_TIME_STATUS: "Billed",
                sc.COL_TIME_INVOICE_REF: "26-0222",
                sc.COL_TIME_TOTAL: 999.0,
            },
        ],
        [],
        [
            {
                sc.COL_RECV_INVOICE_NUM: "26-0111",
                sc.COL_RECV_BALANCE_DUE: 226.0,
                sc.COL_RECV_STATUS: "Open",
            },
            {
                sc.COL_RECV_INVOICE_NUM: "26-0222",
                sc.COL_RECV_BALANCE_DUE: 999.0,
                sc.COL_RECV_STATUS: "Open",
            },
        ],
    )

    assert summary["unbilledWipCount"] == 1
    assert summary["unbilledWipAmount"] == 113.0
    assert summary["unpaidInvoiceCount"] == 1
    assert summary["unpaidInvoiceAmount"] == 226.0
    assert [row["invoiceNum"] for row in summary["unpaidInvoices"]] == ["26-0111"]


def test_permanent_deletion_is_blocked_when_the_matter_has_wip_or_unpaid_ar():
    result = ExcelRepo.delete_matter_profile(_DeleteGuardRepo(), "matter-1")

    assert result["ok"] is False
    assert "unbilled WIP" in result["message"]
    assert "unpaid invoice" in result["message"]


def test_matter_financial_summary_blocks_archiving_when_a_linked_draft_exists():
    repo = _SummaryRepo()
    summary = ExcelRepo._matter_financial_summary_from_rows(
        repo,
        "matter-1",
        [{
            sc.COL_TIME_ENTRY_ID: "T-draft",
            sc.COL_TIME_MATTER_ID: "matter-1",
            sc.COL_TIME_STATUS: "Draft",
            sc.COL_TIME_INVOICE_REF: "DRAFT-26-0032",
            sc.COL_TIME_TOTAL: 100.0,
        }],
        [],
        [],
        [{sc.COL_DRAFT_INVOICE_NUM: "DRAFT-26-0032"}],
    )

    assert summary["draftInvoiceCount"] == 1
    assert summary["draftInvoices"] == ["DRAFT-26-0032"]
    assert summary["hasFinancialBlockers"] is True
    assert "draft invoice" in ExcelRepo._matter_financial_blocker_message(
        repo, summary, action="archive this matter"
    )


def test_matter_screens_expose_financial_work_and_sized_delete_buttons():
    root = Path(__file__).resolve().parents[1]
    wizard = (root / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(encoding="utf-8")
    profile = (root / "src" / "qml" / "views" / "placeholder" / "MatterProfilePanel.qml").read_text(encoding="utf-8")

    assert "Status cannot be changed while this matter has" in wizard
    assert 'text: "Open WIP Ledger"' in wizard
    assert '"statusModeText": "Unbilled WIP"' in wizard
    assert "openMatterInvoice(String(modelData.invoiceNum || \"\"))" in wizard
    assert "Layout.minimumWidth: root.ratioPxW(0.174, 174)" in wizard
    assert "Layout.minimumHeight: root.fieldHeightPx" in wizard
    assert 'text: "WIP & unpaid invoices"' in profile
    assert "openMatterInvoice(String(modelData.invoiceNum || \"\"))" in profile


def test_matter_editor_prevents_silent_loss_and_verifies_a_renamed_profile_before_returning():
    root = Path(__file__).resolve().parents[1]
    wizard = (root / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(encoding="utf-8")

    assert 'root.matterEditMode ? "Save Matter & Return" : "Save Matter"' in wizard
    assert "if (root.dirty) {\n                discardMatterEditPopup.open()" in wizard
    assert 'text: "Discard unsaved matter changes?"' in wizard
    assert 'text: "Keep Editing"' in wizard
    assert 'text: "Discard Changes"' in wizard
    assert "var verification = ({})" in wizard
    assert "appRef.getMatterProfile(lastSavedMatterId)" in wizard
    assert "Matter changes could not be verified in the workbook" in wizard
    assert "Matter profile updated and reloaded from the workbook." in wizard
