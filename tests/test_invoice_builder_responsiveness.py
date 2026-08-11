from pathlib import Path


def test_finalization_and_draft_refresh_stay_off_the_qml_thread():
    controller = Path("src/python/backend/controllers/billing_controller.py").read_text(encoding="utf-8")
    qml = Path("src/qml/views/InvoiceBuilderView.qml").read_text(encoding="utf-8")

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
