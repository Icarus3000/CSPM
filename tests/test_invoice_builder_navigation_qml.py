"""Execute the real Invoice Builder navigation handlers without WebEngine."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "src/qml/views/InvoiceBuilderView.qml"


def test_reactive_draft_deep_links_loader_replay_and_explicit_refresh():
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe"],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Invoice navigation checks passed" in result.stdout


def _probe():
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    # Run source handlers verbatim in their own QtObject. The surrounding view
    # contains WebEngine; this state-only harness creates no window or renderer.
    source = VIEW.read_text()

    def block(pattern):
        match = re.search(pattern + r".*?^    \}", source, re.MULTILINE | re.DOTALL)
        assert match, pattern
        return match.group()

    handlers = [block(r"^    onDraftNumChanged: \{"),
                block(r"^    Component\.onCompleted: \{")]
    functions = [block(r"^    function " + name + r"\(")
                 for name in ("applyInitialState", "_loadDrafts", "_selectDraft")]
    qml = '''import QtQml
pragma ComponentBehavior: Bound
QtObject {
    id: root
    property string draftNum: ""
    property string selectedDraftNum: ""
    property bool isFinalized: false
    property string finalInvoiceNum: ""
    property var selectedDraftData: null
    property var draftLineItems: []
    property var draftMatterOptions: []
    property string previewHtml: ""
    property bool isLoading: false
    property bool isPreviewLoading: false
    property string selectedConcept: "Concept_A2"
    property QtObject billingBackend: QtObject {
        property int listRequests: 0
        property var workspaceRequests: []
        function loadDrafts() { ++listRequests }
        function getCachedPreviewHtml(number) { return "cached:" + number }
        function loadDraftWorkspace(number, concept) {
            workspaceRequests = workspaceRequests.concat([{number: number, concept: concept}])
        }
    }
''' + "\n".join(handlers + functions) + "\n}"
    app = QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml.encode(), QUrl.fromLocalFile(str(ROOT / "tests/invoice_navigation_probe.qml")))
    assert component.isReady(), [error.toString() for error in component.errors()]
    item = component.createWithInitialProperties({"draftNum": "D-INITIAL"})
    assert item is not None, [error.toString() for error in component.errors()]
    engine.globalObject().setProperty("probe", engine.newQObject(item))

    def evaluate(expression):
        value = engine.evaluate(expression)
        assert not value.isError(), value.toString()
        return value

    def requests():
        return json.loads(evaluate("JSON.stringify(probe.billingBackend.workspaceRequests)").toString())

    assert [r["number"] for r in requests()] == ["D-INITIAL"]
    evaluate('probe.applyInitialState({draftNum: "D-INITIAL"})')
    assert len(requests()) == 1, "Loader replay duplicated the initial workspace request"
    item.setProperty("draftNum", "D-REACTIVE")
    assert requests()[-1] == {"number": "D-REACTIVE", "concept": "Concept_A2"}
    assert len(requests()) == 2
    evaluate('probe.applyInitialState({draftId: " D-ALIAS "})')
    assert item.property("draftNum") == "D-ALIAS"
    evaluate('probe.applyInitialState({invoiceDraftId: "D-THIRD"})')
    assert item.property("selectedDraftNum") == "D-THIRD"
    assert len(requests()) == 4
    for expression in ('null', '{}', '"invalid"', '{focusNodeId: "C03"}'):
        evaluate("probe.applyInitialState(" + expression + ")")
    assert len(requests()) == 4
    # A deliberate same-row click still requests a fresh snapshot.
    evaluate('probe._selectDraft("D-THIRD")')
    assert len(requests()) == 5
    evaluate('probe.applyInitialState({draftNum: "D-FIRST", draftId: "D-IGNORED"})')
    assert item.property("selectedDraftNum") == "D-FIRST"
    assert len(requests()) == 6
    # Navigation can return to the routed draft after the user selected another.
    evaluate('probe._selectDraft("D-OTHER")')
    evaluate('probe.applyInitialState({draftNum: "D-FIRST"})')
    assert item.property("selectedDraftNum") == "D-FIRST"
    assert len(requests()) == 8
    assert item.property("previewHtml") == "cached:D-FIRST"
    item.deleteLater()
    app.processEvents()
    print("Invoice navigation checks passed")


if __name__ == "__main__" and sys.argv[1:] == ["--probe"]:
    _probe()
