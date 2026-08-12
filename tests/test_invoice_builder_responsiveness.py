import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


def test_finalization_and_draft_refresh_stay_off_the_qml_thread():
    controller = Path("src/python/backend/controllers/billing_controller.py").read_text(encoding="utf-8")
    qml = Path("src/qml/views/InvoiceBuilderView.qml").read_text(encoding="utf-8")
    excel_repo = Path("src/python/repositories/excel_repo.py").read_text(encoding="utf-8")
    draft_service = Path("src/python/services/invoice_draft_service.py").read_text(encoding="utf-8")

    assert "draftsLoaded = Signal('QVariantList')" in controller
    assert "def loadDrafts(self):" in controller
    assert 'Worker(self.listDrafts, name="loadDrafts")' in controller
    assert "finalizedInvoiceHtmlReady = Signal(str, str, str)" in controller
    assert "def loadFinalizedInvoiceHtml(self, draft_num, final_invoice_num):" in controller
    assert "invoiceNumberReuseStatusLoaded = Signal(str, 'QVariantMap')" in controller
    assert "def loadInvoiceNumberReuseStatus(self, invoice_num):" in controller

    assert "billingBackend.loadDrafts()" in qml
    assert "billingBackend.loadFinalizedInvoiceHtml(root.selectedDraftNum, root.pendingFinalizeInvoiceNum)" in qml
    assert "billingBackend.loadInvoiceNumberReuseStatus(requestedNum)" in qml
    assert "billingBackend.loadNextInvoiceNumber()" in qml
    assert "root.finalInvoiceNum = String(result.invoiceNum || root.pendingFinalizeInvoiceNum)" in qml
    assert "var finalHtml = root.billingBackend.getFinalizedHtml" not in qml
    assert "CSPM is safely completing this step. Keep this window open." in qml
    assert 'name="mergeInvoicePdf"' in controller
    assert "def _merge_pdf_export_impl" in controller
    assert "def _write_table_rows_bulk" in excel_repo
    assert "self._write_tables_once({" in draft_service


def test_initial_draft_selection_uses_one_background_workspace_payload():
    controller = Path("src/python/backend/controllers/billing_controller.py").read_text(encoding="utf-8")
    qml = Path("src/qml/views/InvoiceBuilderView.qml").read_text(encoding="utf-8")

    assert "draftWorkspaceLoaded = Signal(str, 'QVariantMap')" in controller
    assert "def loadDraftWorkspace(self, draft_num, template_name" in controller
    assert 'name="loadDraftWorkspace"' in controller
    assert "def _load_draft_workspace_impl" in controller
    assert "_read_table_rows_bulk([" in controller

    assert "billingBackend.loadDraftWorkspace(draftNum, root.selectedConcept)" in qml
    assert "function onDraftWorkspaceLoaded(draftNum, workspace)" in qml
    assert "selectedDraftData = billingBackend.getDraft(draftNum)" not in qml
    assert "draftLineItems = billingBackend.getDraftLineItems(draftNum)" not in qml


def test_pdf_post_processing_can_run_without_webengine(tmp_path):
    """The worker's CPU/I/O portion is independently safe to run off-thread."""
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from backend.controllers.billing_controller import BillingController

    first_pass = tmp_path / "first-pass.pdf"
    output = tmp_path / "final.pdf"
    pdf_canvas = canvas.Canvas(str(first_pass), pagesize=letter)
    pdf_canvas.drawString(72, 720, "First page")
    pdf_canvas.showPage()
    pdf_canvas.drawString(72, 720, "Second page")
    pdf_canvas.save()

    result = BillingController._merge_pdf_export_impl(
        str(first_pass),
        str(output),
        '<div data-client="Test Client" data-invoice="INV-1" data-date="2026-08-11"></div>',
    )

    assert result == {"path": str(output), "pages": 2}
    assert len(PdfReader(str(output)).pages) == 2
    assert not first_pass.exists()
