import copy
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_CLIENT_PROFILES,
    TBL_CLIENTS,
    TBL_DISBURSEMENTS,
    TBL_INVOICE_LOG,
    TBL_LEDGER,
    TBL_MATTERS,
    TBL_PARENTS,
    TBL_RECEIVABLES,
    TBL_TIME,
    TBL_TRANSACTIONS_MASTER,
    TBL_DRAFT_INVOICES,
)
from services.invoice_draft_service import InvoiceDraftService


class _InvoiceReversalRepo:
    _client_parent_lookup = ExcelRepo._client_parent_lookup
    _date_iso = ExcelRepo._date_iso
    _parse_date_value = ExcelRepo._parse_date_value
    _parse_float = ExcelRepo._parse_float

    def __init__(self):
        self._next_id = 0
        self.bulk_writes = []
        self.tables = {
            TBL_PARENTS.table: [{sc.COL_PARENT_ID: "LEVI", sc.COL_PARENT_NAME: "Leviathan Private Network"}],
            TBL_CLIENTS.table: [{sc.COL_CLIENT_ID: "ALXX", sc.COL_CLIENT_NAME: "AL ADVISOR"}],
            TBL_CLIENT_PROFILES.table: [{
                sc.COL_PROFILE_CLIENT_ID: "ALXX",
                sc.COL_PROFILE_DISPLAY_NAME: "AL ADVISOR",
                sc.COL_PROFILE_PARENT_ID: "LEVI",
                sc.COL_PROFILE_PARENT_NAME: "Leviathan Private Network",
            }],
            TBL_MATTERS.table: [{
                sc.COL_MATTER_ID: "MAT-AL",
                sc.COL_MATTER_NAME: "Tax Planning",
                sc.COL_MATTER_CLIENT_ID: "ALXX",
                sc.COL_MATTER_CLIENT_NAME: "AL ADVISOR",
                sc.COL_MATTER_PARENT_ID: "LEVI",
            }],
            TBL_TIME.table: [{
                sc.COL_TIME_ENTRY_ID: "TIME-1",
                sc.COL_TIME_DATE: "2026-05-05",
                sc.COL_TIME_CLIENT_ID: "ALXX",
                sc.COL_TIME_MATTER_ID: "MAT-AL",
                sc.COL_TIME_PARENT_ID: "LEVI",
                sc.COL_TIME_DESC: "review transaction documents",
                sc.COL_TIME_HOURS: 0.3,
                sc.COL_TIME_GROSS: 142.5,
                sc.COL_TIME_TOTAL: 161.02,
                sc.COL_TIME_STATUS: "Billed",
                sc.COL_TIME_INVOICE_REF: "26-0057",
                sc.COL_TIME_INVOICE_STATUS: "Billed",
                sc.COL_TIME_INVOICE_DATE: "2026-05-31",
                sc.COL_TIME_INVOICE_TOTAL: 161.03,
                sc.COL_TIME_INVOICE_AMOUNT_PAID: 0,
                sc.COL_TIME_INVOICE_BALANCE_DUE: 161.03,
            }],
            TBL_DISBURSEMENTS.table: [],
            TBL_RECEIVABLES.table: [{
                sc.COL_RECV_INVOICE_NUM: "26-0057",
                sc.COL_RECV_DATE: "2026-05-31",
                sc.COL_RECV_CLIENT: "Leviathan Private Network",
                sc.COL_RECV_WORK_CLIENT: "AL ADVISOR",
                sc.COL_RECV_TOTAL_INVOICED: 161.03,
                sc.COL_RECV_AMOUNT_PAID: 0,
                sc.COL_RECV_CREDITS_ADJ: 0,
                sc.COL_RECV_BALANCE_DUE: 161.03,
                sc.COL_RECV_STATUS: "Pending",
            }],
            TBL_INVOICE_LOG.table: [{
                sc.COL_INV_INVOICE_NUM: "26-0057",
                sc.COL_INV_CLIENT_NAME: "AL ADVISOR",
                sc.COL_INV_BILL_TO_CLIENT: "Leviathan Private Network",
                sc.COL_INV_INVOICE_DATE: "2026-05-31",
                sc.COL_INV_TOTAL_FEES: 142.5,
                sc.COL_INV_TOTAL_DISBURSEMENTS: 0,
                sc.COL_INV_TOTAL_TAX: 18.53,
                sc.COL_INV_AGGREGATE_BILLED: 161.03,
            }],
            TBL_LEDGER.table: [{
                sc.COL_LEDGER_ID: "LED-ORIGINAL",
                sc.COL_LEDGER_REFERENCE: "26-0057",
                sc.COL_LEDGER_BILLINGS_EXCL_HST: 142.5,
                sc.COL_LEDGER_HST_COLLECTED: 18.53,
                sc.COL_LEDGER_RECEIVABLE: 161.03,
            }],
            TBL_TRANSACTIONS_MASTER.table: [{
                sc.COL_TXN_ID: "TXN-ORIGINAL",
                sc.COL_TXN_INVOICE_REF: "26-0057",
                sc.COL_TXN_AMOUNT: 142.5,
                sc.COL_TXN_TAX_AMOUNT: 18.53,
            }],
            TBL_DRAFT_INVOICES.table: [],
        }

    def ensure_schema(self):
        return None

    def _read_table_rows(self, table):
        table_key = getattr(table, "table", table)
        return [dict(row) for row in self.tables.get(table_key, [])]

    def _write_table_rows(self, table, rows):
        table_key = getattr(table, "table", table)
        self.tables[table_key] = [dict(row) for row in rows]

    def _write_table_rows_bulk(self, table_rows):
        snapshot = {}
        for table, rows in table_rows.items():
            table_key = getattr(table, "table", table)
            copied_rows = [dict(row) for row in rows]
            self.tables[table_key] = copied_rows
            snapshot[table_key] = copied_rows
        self.bulk_writes.append(snapshot)

    def _new_id(self, prefix):
        self._next_id += 1
        return f"{prefix}-{self._next_id}"


def test_reversal_returns_only_the_linked_wip_and_hides_void_invoice_ledger_rows():
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)

    assert service.reverse_invoice("26-0057") is True

    docket = repo.tables[TBL_TIME.table][0]
    assert docket[sc.COL_TIME_CLIENT_ID] == "ALXX"
    assert docket[sc.COL_TIME_MATTER_ID] == "MAT-AL"
    assert docket[sc.COL_TIME_INVOICE_REF] == ""
    assert docket[sc.COL_TIME_STATUS] == "Draft"
    assert docket[sc.COL_TIME_INVOICE_STATUS] == "Unbilled"
    assert docket.get(sc.COL_TIME_PAYMENT_STATUS, "") == ""

    receivable = repo.tables[TBL_RECEIVABLES.table][0]
    assert receivable[sc.COL_RECV_STATUS] == "Void"
    assert receivable[sc.COL_RECV_BALANCE_DUE] == "0.00"
    assert [row[sc.COL_INV_INVOICE_NUM] for row in repo.tables[TBL_INVOICE_LOG.table]] == [
        "26-0057",
        "26-0057-V",
    ]
    assert repo.tables[TBL_INVOICE_LOG.table][-1][sc.COL_INV_AGGREGATE_BILLED] == "-161.03"
    assert repo.tables[TBL_LEDGER.table][-1][sc.COL_LEDGER_REFERENCE] == "26-0057-V"
    assert repo.tables[TBL_TRANSACTIONS_MASTER.table][-1][sc.COL_TXN_INVOICE_REF] == "26-0057-V"

    # A second click is idempotent: it cannot create a second financial reversal.
    assert service.reverse_invoice("26-0057") is True
    assert len(repo.tables[TBL_INVOICE_LOG.table]) == 2
    assert len(repo.tables[TBL_LEDGER.table]) == 2
    assert len(repo.tables[TBL_TRANSACTIONS_MASTER.table]) == 2

    report = ExcelRepo.get_client_ledger_report(repo, {"clientId": "ALXX"})
    assert report["ok"] is True
    assert [(row["type"], row["description"]) for row in report["entries"]] == [
        ("Time", "review transaction documents"),
    ]
    assert report["entries"][0]["status"] == "WIP"


def test_correct_and_reissue_suggests_the_original_number_without_locking_the_replacement():
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)

    result = service.correct_invoice_for_reissue("26-0057")

    assert result["invoiceNum"] == "26-0057"
    assert result["timeEntryCount"] == 1
    docket = repo.tables[TBL_TIME.table][0]
    assert docket[sc.COL_TIME_INVOICE_REF] == ""
    assert docket[sc.COL_TIME_INVOICE_STATUS] == "Unbilled"
    assert docket[sc.COL_TIME_REISSUE_INVOICE_NUM] == "26-0057"

    # The original financial rows remain as internal audit evidence, but the
    # exact number is free for the corrected replacement.
    assert [row[sc.COL_INV_INVOICE_NUM] for row in repo.tables[TBL_INVOICE_LOG.table]] == [
        "26-0057-SUPERSEDED",
        "26-0057-V",
    ]
    assert repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_INVOICE_NUM] == "26-0057-SUPERSEDED"
    assert repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_STATUS] == "Superseded"
    assert repo.tables[TBL_LEDGER.table][0][sc.COL_LEDGER_REFERENCE] == "26-0057-SUPERSEDED"
    assert repo.tables[TBL_TRANSACTIONS_MASTER.table][0][sc.COL_TXN_INVOICE_REF] == "26-0057-SUPERSEDED"

    # The superseded original and its reversal are audit-only evidence.  They
    # must not leak into the client-facing ledger while the corrected invoice
    # is being prepared.
    report = ExcelRepo.get_client_ledger_report(repo, {"clientId": "ALXX"})
    assert [(row["type"], row["description"]) for row in report["entries"]] == [
        ("Time", "review transaction documents"),
    ]

    draft_num = service.create_draft("ALXX", "AL ADVISOR", ["TIME-1"])
    draft = repo.tables[TBL_DRAFT_INVOICES.table][0]
    assert draft[sc.COL_DRAFT_REISSUE_INVOICE_NUM] == "26-0057"

    assert service.finalize_draft(draft_num, "26-0058", "") is True
    assert repo.tables[TBL_TIME.table][0][sc.COL_TIME_INVOICE_REF] == "26-0058"
    assert repo.tables[TBL_TIME.table][0][sc.COL_TIME_REISSUE_INVOICE_NUM] == ""
    assert any(
        row[sc.COL_INV_INVOICE_NUM] == "26-0058"
        for row in repo.tables[TBL_INVOICE_LOG.table]
    )


def test_removing_wip_from_a_correction_draft_releases_the_old_number_suggestion():
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)

    service.correct_invoice_for_reissue("26-0057")
    service.create_draft("ALXX", "AL ADVISOR", ["TIME-1"])

    service.remove_line_item("TIME-1", delete_completely=False)

    docket = repo.tables[TBL_TIME.table][0]
    assert docket[sc.COL_TIME_INVOICE_REF] == ""
    assert docket[sc.COL_TIME_INVOICE_STATUS] == "Unbilled"
    assert docket.get(sc.COL_TIME_REISSUE_INVOICE_NUM, "") == ""


def test_finalize_can_reclaim_a_previously_voided_unpaid_invoice_number():
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)

    assert service.reverse_invoice("26-0057") is True
    status = service.invoice_number_reuse_status("26-0057")
    assert status["state"] == "reclaimable_void"
    assert status["canUse"] is True

    draft_num = service.create_draft("ALXX", "AL ADVISOR", ["TIME-1"])
    assert service.finalize_draft(draft_num, "26-0057", "") is True

    assert [row[sc.COL_INV_INVOICE_NUM] for row in repo.tables[TBL_INVOICE_LOG.table]] == [
        "26-0057-SUPERSEDED",
        "26-0057-V",
        "26-0057",
    ]
    assert repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_INVOICE_NUM] == "26-0057-SUPERSEDED"
    assert repo.tables[TBL_RECEIVABLES.table][-1][sc.COL_RECV_INVOICE_NUM] == "26-0057"
    assert repo.tables[TBL_RECEIVABLES.table][-1][sc.COL_RECV_STATUS] == "Unpaid"


def test_finalization_commits_all_financial_tables_in_one_bulk_write():
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)

    draft_num = service.create_draft("ALXX", "AL ADVISOR", ["TIME-1"])
    repo.bulk_writes.clear()

    assert service.finalize_draft(draft_num, "26-0058", "") is True

    assert len(repo.bulk_writes) == 1
    assert set(repo.bulk_writes[0]) == {
        TBL_TIME.table,
        TBL_DISBURSEMENTS.table,
        TBL_RECEIVABLES.table,
        TBL_INVOICE_LOG.table,
        TBL_LEDGER.table,
        TBL_DRAFT_INVOICES.table,
    }


def test_paid_or_credited_void_number_cannot_be_reclaimed():
    repo = _InvoiceReversalRepo()
    repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_STATUS] = "Void"
    repo.tables[TBL_RECEIVABLES.table][0][sc.COL_RECV_AMOUNT_PAID] = "1.00"
    service = InvoiceDraftService(repo)

    status = service.invoice_number_reuse_status("26-0057")

    assert status["canUse"] is False
    assert status["state"] == "used"
    assert "paid or credited" in status["message"]


def test_reversal_moves_only_a_user_selected_pdf_without_overwriting_an_archive(tmp_path):
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)
    source_pdf = tmp_path / "invoice-26-0057.pdf"
    source_pdf.write_bytes(b"invoice evidence")

    assert service.reverse_invoice(
        "26-0057",
        source_pdf_path=str(source_pdf),
        pdf_action="move",
    ) is True

    archived_pdf = tmp_path / "REVERSED" / source_pdf.name
    assert not source_pdf.exists()
    assert archived_pdf.read_bytes() == b"invoice evidence"


def test_reversal_rejects_missing_explicit_pdf_before_changing_financial_records(tmp_path):
    repo = _InvoiceReversalRepo()
    service = InvoiceDraftService(repo)
    before = copy.deepcopy(repo.tables)

    with pytest.raises(ValueError, match="Select the existing invoice PDF"):
        service.reverse_invoice(
            "26-0057",
            source_pdf_path=str(tmp_path / "missing.pdf"),
            pdf_action="move",
        )

    assert repo.tables == before


def test_invoice_reversal_dialog_keeps_actions_visible_and_makes_pdf_optional():
    source = (PROJECT_ROOT / "src" / "qml" / "views" / "InvoiceReversalView.qml").read_text(encoding="utf-8")

    assert 'property string pdfAction: "keep"' in source
    assert 'height: Math.min(parent.height - 24, 560)' in source
    assert 'id: reversalOptionsScroll' in source
    assert 'ScrollBar.vertical.policy: ScrollBar.AsNeeded' in source
    assert 'text: "No PDF available? Leave \\"Keep PDF\\" selected and continue."' in source
    assert 'text: "Correct & Reissue"' in source
    assert 'text: "Reverse Only"' in source
    assert "property bool operationInProgress: false" in source
    assert 'onClicked: reverseDialog.pdfAction = "keep"' in source
    assert 'onClicked: reverseDialog.pdfAction = "move"' in source
    assert 'onClicked: reverseDialog.pdfAction = "delete"' in source
    assert "ButtonGroup { id: pdfActionGroup }" not in source
    assert "RadioButton {" not in source
    assert "Working safely... CSPM is preparing the correction." in source
