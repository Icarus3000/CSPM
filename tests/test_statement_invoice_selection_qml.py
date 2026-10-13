"""Exercise actual statement filter/selection bindings without WebEngine or data."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_statement_filters_clear_stale_selections_and_restore_in_workspace():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Statement selection checks passed" in result.stdout


def run_probe():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

    application = QGuiApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(
        ROOT / "src/qml/views/StatementOfAccountView.qml")))
    assert component.isReady(), component.errorString()
    view = component.createWithInitialProperties({"width": 1100, "height": 760})
    assert view is not None, component.errorString()

    def evaluate(source):
        expression = QQmlExpression(QQmlEngine.contextForObject(view), view, source)
        value = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        value = value[0] if isinstance(value, tuple) else value
        return value.toVariant() if hasattr(value, "toVariant") else value

    evaluate('setBillingClient("Sample Billing Client", false)')
    first_request_id = evaluate('nextRequestId("statement-preview")')
    other_view = component.createWithInitialProperties({"width": 1100, "height": 760})
    assert other_view is not None, component.errorString()
    other_expression = QQmlExpression(QQmlEngine.contextForObject(other_view), other_view,
                                     'nextRequestId("statement-preview")')
    other_request_id = other_expression.evaluate()
    other_request_id = other_request_id[0] if isinstance(other_request_id, tuple) else other_request_id
    assert not other_expression.hasError(), other_expression.error().toString()
    assert first_request_id != other_request_id
    assert first_request_id.startswith("statement-preview-")
    assert evaluate('basePayload().invoiceStatus') == "open"
    assert evaluate('basePayload().invoiceDateFrom') == ""
    assert evaluate('basePayload().invoiceDateTo') == ""
    evaluate('applyOpenInvoicesResponse({ok:true, availableInvoices:[{invoice:"26-0100", balanceDue:75}]})')
    assert evaluate('selectedInvoiceCount()') == 1
    assert evaluate('selectedBalance()') == 75
    evaluate('statementRequestId = "statement-open-invoices-OLD"')
    view.setProperty("invoiceStatus", "paid")
    assert evaluate('selectedInvoiceCount()') == 0
    assert evaluate('statementRequestId') == ""
    assert evaluate('basePayload().openItemsOnly') is False
    assert evaluate('basePayload().invoiceStatus') == "paid"
    evaluate('applyOpenInvoicesResponse({ok:true, availableInvoices:[{invoice:"26-0101", balanceDue:0}]})')
    assert evaluate('selectedInvoiceCount()') == 1
    assert evaluate('selectedBalance()') == 0
    view.setProperty("invoiceDateFrom", "2026-01-01")
    assert evaluate('selectedInvoiceCount()') == 0
    view.setProperty("invoiceDateTo", "2026-07-31")
    view.setProperty("asOfDateText", "2026-10-13")
    saved = evaluate('snapshotState()')
    assert saved == {
        "statementBillingClient": "Sample Billing Client",
        "statementAsOfDate": "2026-10-13",
        "statementInvoiceStatus": "paid",
        "statementInvoiceDateFrom": "2026-01-01",
        "statementInvoiceDateTo": "2026-07-31",
    }
    evaluate('invoiceStatus="open"; invoiceDateFrom=""; invoiceDateTo=""; setBillingClient("",false)')
    evaluate('applyState({statementBillingClient:"Sample Billing Client", statementAsOfDate:"2026-10-13",'
             'statementInvoiceStatus:"paid",statementInvoiceDateFrom:"2026-01-01",statementInvoiceDateTo:"2026-07-31"})')
    assert evaluate('snapshotState()') == saved
    evaluate('applyOpenInvoicesResponse({ok:true, availableInvoices:[{invoice:"26-0101",balanceDue:0},{invoice:"26-0102",balanceDue:0}]})')
    evaluate('setInvoiceSelected("26-0101", false)')
    assert evaluate('selectedInvoiceNumbers()') == ["26-0102"]
    view.setProperty("asOfDateText", "2026-10-12")
    assert evaluate('selectedInvoiceCount()') == 0
    # Controls remain usable on the smaller standard workspace and do not
    # collapse their labels/values into the same short row.
    application.processEvents()
    for name in ("statementInvoiceStatusInput", "statementInvoiceDateFromInput", "statementInvoiceDateToInput"):
        from PySide6.QtCore import QObject
        control = view.findChild(QObject, name)
        assert control is not None
        assert control.property("height") >= 48
        assert control.property("width") >= 150
        if name == "statementInvoiceStatusInput":
            assert control.property("currentIndex") == 1
            assert control.property("editText") == "Paid"
    print("Statement selection checks passed")
    other_view.deleteLater()
    view.deleteLater()
    application.processEvents()


if __name__ == "__main__":
    run_probe()
