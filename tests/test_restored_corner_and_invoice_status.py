"""Exercise the actual QML calculations without a window or WebEngine."""
import json
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = QCoreApplication.instance() or QCoreApplication([])


def function_source(path, name):
    source = path.read_text(encoding="utf-8")
    start = source.index("function " + name + "(")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


@pytest.mark.parametrize("canvas_width,canvas_height,maximized,expected", [
    (1920, 1040, False, 12), (3840, 2160, False, 12),
    (1447, 860, False, 12), (1920, 1040, True, 1),
])
def test_professional_corner_radius_does_not_use_a_stale_monitor_sized_canvas(
        canvas_width, canvas_height, maximized, expected):
    engine = QJSEngine()
    shell = ROOT / "src/qml/DetachedShellWindow.qml"
    context = {"appRef": {"appStyle": "Professional"}, "animationPhase": "settled",
               "userResizeInProgress": False, "uiMaximized": maximized,
               "usableW": 1920, "usableH": 1040}
    code = "var mainWin=" + json.dumps(context) + ";"
    code += f"var canvasW={canvas_width},canvasH={canvas_height};"
    code += "function chromeCornerRadiusPx(){return 0;}"
    code += "function resizeVisualWidthPx(){return 1425;}function resizeVisualHeightPx(){return 838;}"
    code += "function settledPaddingPx(){return 11;}"
    code += function_source(shell, "canvasFrameCornerRadiusPx")
    code += function_source(shell, "shellVisualCornerRadiusPx")
    result = engine.evaluate(code + ";shellVisualCornerRadiusPx();")
    assert not result.isError(), result.toString()
    assert result.toNumber() == expected


@pytest.mark.parametrize("status,balance,paid,expected", [
    ("Void", 0, 0, "Reversed"), ("Reversed", 0, 0, "Reversed"),
    ("Cancelled", 0, 0, "Reversed"), ("Superseded", 0, 0, "Superseded"),
    ("Closed", 0, 0, "Closed"), ("Pending", 100, 0, "Unpaid"),
    ("Pending", 50, 50, "Partially Paid"), ("Paid", 0, 100, "Paid"),
])
def test_invoice_status_respects_lifecycle_before_zero_balance(status, balance, paid, expected):
    engine = QJSEngine()
    function = function_source(ROOT / "src/qml/views/InvoiceReversalView.qml", "_displayInvoiceStatus")
    summary = {"Status": status, "BalanceDue": balance, "AmountPaid": paid}
    result = engine.evaluate(function + ";_displayInvoiceStatus(" + json.dumps(summary) + ");")
    assert not result.isError(), result.toString()
    assert result.toString() == expected
