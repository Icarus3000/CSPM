"""Current A/R enrichment and actual QML filtering, using synthetic records."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))

from backend.controllers.billing_controller import BillingController
from domain import schema_constants as sc
from repositories.excel_repo import TBL_INVOICE_LOG, TBL_RECEIVABLES


class DirectoryRepo:
    def __init__(self, receivables):
        self.bulk_reads = 0
        self.receivables = receivables

    def _read_table_rows_bulk(self, tables):
        self.bulk_reads += 1
        return {
            table.table: (
                [{sc.COL_INV_INVOICE_NUM: f"26-{number:04}",
                  sc.COL_INV_CLIENT_NAME: "Example Client",
                  sc.COL_INV_AGGREGATE_BILLED: 9999}
                 for number in range(1, 10)]
                if table.table == TBL_INVOICE_LOG.table else
                self.receivables if table.table == TBL_RECEIVABLES.table else []
            )
            for table in tables
        }


def receivable(number, balance, paid=0, credits=0, status="Pending"):
    return {
        sc.COL_RECV_INVOICE_NUM: f"26-{number:04}",
        sc.COL_RECV_BALANCE_DUE: balance,
        sc.COL_RECV_AMOUNT_PAID: paid,
        sc.COL_RECV_CREDITS_ADJ: credits,
        sc.COL_RECV_STATUS: status,
        sc.COL_RECV_CLIENT: "Example Billing Client",
    }


def test_directory_enriches_current_balances_in_one_read_and_keeps_unknown_distinct():
    repo = DirectoryRepo([
        receivable(1, "90.045", paid="10.005"),
        receivable(2, 0, credits=100, status="Closed"),
        receivable(3, 80, credits=20),
        receivable(4, ""),
        receivable(5, "NaN"),
        receivable(6, -10, paid=110),
        receivable(7, 20), receivable(7, 30),
        receivable(8, 0, status="Reversed"),
        receivable(9, 0, status="Superseded"),
    ])
    rows = BillingController(repo, None, None).listFinalizedInvoices()
    by_number = {row[sc.COL_INV_INVOICE_NUM]: row for row in rows}
    assert repo.bulk_reads == 1
    partial = by_number["26-0001"]
    assert partial["BalanceDue"] == 90.05
    assert partial["BalanceDueCents"] == 9005
    assert partial["AmountPaidCents"] == 1001
    assert partial["DirectoryStatus"] == "Partially Paid"
    assert partial["BillingClient"] == "Example Billing Client"
    assert partial[sc.COL_INV_AGGREGATE_BILLED] == 9999
    assert by_number["26-0002"]["DirectoryStatus"] == "Paid"
    assert by_number["26-0002"]["BalanceDueCents"] == 0
    assert by_number["26-0003"]["DirectoryStatus"] == "Unpaid"
    assert by_number["26-0003"]["CreditsAdj"] == 20
    assert by_number["26-0006"]["DirectoryStatus"] == "Credit balance"
    for number in (4, 5, 7):
        assert by_number[f"26-{number:04}"]["BalanceKnown"] is False
        assert by_number[f"26-{number:04}"]["BalanceDueCents"] is None
        assert by_number[f"26-{number:04}"]["DirectoryStatus"] == "Unavailable"
    assert "26-0008" not in by_number
    assert "26-0009" not in by_number


def test_directory_log_without_receivable_is_not_a_zero_balance_invoice():
    rows = BillingController(DirectoryRepo([]), None, None).listFinalizedInvoices()
    assert all(row["BalanceKnown"] is False and row["BalanceDue"] is None for row in rows)


def function_source(name, path=None):
    source = (path or ROOT / "src/qml/views/InvoiceReversalView.qml").read_text(encoding="utf-8")
    start = source.index("function " + name + "(")
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


@pytest.fixture
def js_engine():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QJSEngine()
    result = engine.evaluate("\n".join(function_source(name) for name in (
        "_directoryAmountRange", "_directoryMoney", "_directoryInvoiceMatches",
        "_filterInvoices", "_applyInvoices", "snapshotState", "applyJumpState",
    )))
    assert not result.isError(), result.toString()
    yield engine
    # Keep the application alive for the lifetime of the engine.
    assert application is not None


def evaluate(engine, source):
    result = engine.evaluate(source)
    assert not result.isError(), result.toString()
    return result.toVariant()


@pytest.mark.parametrize("query,lower,upper", [
    ("1000", 90000, 110000), ("$1,000.00", 90000, 110000),
    ("100.05", 9005, 11005), (".50", 45, 55),
    ("100.", 9000, 11000), ("0", 0, 0), ("-100", -11000, -9000),
])
def test_currency_queries_have_inclusive_cent_safe_ten_percent_bounds(js_engine, query, lower, upper):
    assert evaluate(js_engine, f"_directoryAmountRange({json.dumps(query)})") == {
        "lowerCents": lower, "upperCents": upper,
    }


@pytest.mark.parametrize("query", ["26-0100", "Example", "$", "1,00", "100.005", "1e3", "NaN"])
def test_invoice_references_text_and_malformed_currency_are_not_coerced(js_engine, query):
    assert evaluate(js_engine, f"_directoryAmountRange({json.dumps(query)})") is None


def test_numeric_search_uses_only_remaining_balance_and_combines_with_status(js_engine):
    base = {"InvoiceNum": "26-0100", "ClientName": "Example", "BalanceKnown": True,
            "BalanceDueCents": 9000, "AmountPaidCents": 1000, "AggregateBilled": 5000}
    for cents, expected in [(8999, False), (9000, True), (11000, True), (11001, False)]:
        row = dict(base, BalanceDueCents=cents)
        assert evaluate(js_engine, "_directoryInvoiceMatches(" + json.dumps(row)
                        + ", '100', _directoryAmountRange('100'), 'partial')") is expected
    # Even an invoice-number substring match cannot bypass numeric amount bounds.
    row = dict(base, BalanceDueCents=20000)
    assert evaluate(js_engine, "_directoryInvoiceMatches(" + json.dumps(row)
                    + ", '100', _directoryAmountRange('100'), 'all')") is False
    assert evaluate(js_engine, "_directoryInvoiceMatches(" + json.dumps(row)
                    + ", '26-0100', null, 'all')") is True


@pytest.mark.parametrize("known,balance,paid,status,expected", [
    (True, 0, 0, "paid", True), (False, 0, 0, "paid", False),
    (True, 10000, 0, "partial", False), (True, 5000, 5000, "partial", True),
    (True, 5000, 5000, "owing", True), (True, 10000, 0, "owing", True),
    (True, 0, 10000, "owing", False), (True, -1000, 11000, "owing", False),
])
def test_payment_status_filters_distinguish_cash_partial_credits_and_unknown(
        js_engine, known, balance, paid, status, expected):
    row = {"BalanceKnown": known, "BalanceDueCents": balance, "AmountPaidCents": paid}
    assert evaluate(js_engine, "_directoryInvoiceMatches(" + json.dumps(row)
                    + ", '', null, " + json.dumps(status) + ")") is expected


def test_snapshot_restore_and_local_filter_do_not_reload_workbooks_or_details(js_engine):
    evaluate(js_engine, """
var root = this;
var _hasInvoiceSnapshot = true, _allInvoices = [], invoicesModel = [];
var invoiceDirectorySearchText = '', invoiceDirectoryStatusFilter = 'all';
var selectedInvoiceNum = '', selectedInvoiceData = null;
var selectedInvoiceSummary = null, selectedPaymentHistory = [];
var billingCorrectionContext = null, billingCorrectionLoading = false;
var invoiceDetailsLoading = false, invoiceListLoading = false;
var invoiceStatusFilter = {editText: ''}, detailReads = 0;
function _refreshSelectedInvoiceDetails() { detailReads++; }
function _selectInvoice(number) { selectedInvoiceNum = number; }
""")
    rows = [{"InvoiceNum": "26-0001", "ClientName": "Example",
             "BalanceKnown": True, "BalanceDueCents": 10000, "AmountPaidCents": 0}]
    evaluate(js_engine, "_applyInvoices(" + json.dumps(rows) + ");")
    state = {"invoiceDirectorySearchText": "100", "invoiceDirectoryStatusFilter": "owing",
             "selectedInvoiceNum": "26-0001"}
    evaluate(js_engine, "applyJumpState(" + json.dumps(state) + "); _filterInvoices(false);")
    assert evaluate(js_engine, "snapshotState()") == state
    assert evaluate(js_engine, "invoicesModel.length") == 1
    assert evaluate(js_engine, "detailReads") == 0
    # A refreshed payment snapshot removes the now-paid invoice from owing.
    paid_rows = [dict(rows[0], BalanceDueCents=0, AmountPaidCents=10000)]
    evaluate(js_engine, "_applyInvoices(" + json.dumps(paid_rows) + ");")
    assert evaluate(js_engine, "invoicesModel.length") == 0
    assert evaluate(js_engine, "selectedInvoiceNum") == ""
    assert evaluate(js_engine, "invoiceDirectorySearchText") == "100"
    assert evaluate(js_engine, "invoiceDirectoryStatusFilter") == "owing"


def test_work_tab_host_captures_directory_search_status_and_selection(js_engine):
    state = {"invoiceDirectorySearchText": "$100", "invoiceDirectoryStatusFilter": "partial",
             "selectedInvoiceNum": "26-0001"}
    host_function = function_source(
        "snapshotState", ROOT / "src/qml/views/PlaceholderSubmenuView.qml"
    ).replace("function snapshotState(", "function hostSnapshotState(", 1)
    evaluate(js_engine, """
var root = {currentNode: function(){return null;},
    activeIsStatementOfAccount: function(){return false;},
    activeIsInvoiceDirectory: function(){return true;}};
var queryInput = {text: ''}, clientDirectoryMode = 'all', matterDirectoryMode = 'all';
var statementOfAccountLoader = {item: null};
var invoiceDirectoryView = {snapshotState: function(){return DIRECTORY_STATE;}};
""".replace("DIRECTORY_STATE", json.dumps(state)))
    snapshot = evaluate(js_engine, host_function + ";hostSnapshotState();")
    for key, value in state.items():
        assert snapshot[key] == value


def test_actual_directory_qml_component_filters_and_restores_without_webengine():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--qml-probe"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Directory QML checks passed" in result.stdout


def run_qml_probe():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
    application = QGuiApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "src/qml/views/InvoiceReversalView.qml")))
    assert component.isReady(), component.errorString()
    view = component.create()
    assert view is not None, component.errorString()
    view.setProperty("width", 1100)
    view.setProperty("height", 760)

    def expression(code):
        item = QQmlExpression(QQmlEngine.contextForObject(view), view, code)
        value = item.evaluate()
        assert not item.hasError(), item.error().toString()
        value = value[0] if isinstance(value, tuple) else value
        return value.toVariant() if hasattr(value, "toVariant") else value

    rows = [{"InvoiceNum": "26-0001", "ClientName": "Example", "InvoiceDate": "2026-10-01",
             "BalanceKnown": True, "BalanceDueCents": 10000, "AmountPaidCents": 0,
             "DirectoryStatus": "Unpaid"},
            {"InvoiceNum": "26-0002", "ClientName": "Example", "InvoiceDate": "2026-10-01",
             "BalanceKnown": True, "BalanceDueCents": 0, "AmountPaidCents": 10000,
             "DirectoryStatus": "Paid"}]
    expression("_applyInvoices(" + json.dumps(rows) + ")")
    assert expression("invoicesModel.length") == 2
    expression("applyJumpState({invoiceDirectorySearchText:'100', invoiceDirectoryStatusFilter:'owing'})")
    application.processEvents()
    assert expression("invoicesModel.length") == 1
    assert expression("snapshotState().invoiceDirectorySearchText") == "100"
    expression("applyJumpState({invoiceDirectorySearchText:'0', invoiceDirectoryStatusFilter:'paid'})")
    application.processEvents()
    assert expression("invoicesModel.length") == 1
    assert expression("invoicesModel[0].InvoiceNum") == "26-0002"
    assert expression("_directoryMoney(110000)") == "$1,100.00"
    view.deleteLater()
    application.processEvents()
    print("Directory QML checks passed")


if __name__ == "__main__" and "--qml-probe" in sys.argv:
    run_qml_probe()
