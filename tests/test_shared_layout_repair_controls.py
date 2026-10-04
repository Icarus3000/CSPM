"""Actual shared-control QML bindings, isolated without a window or WebEngine.

These checks exercise effective parent visibility, synchronous metric adoption
and shadow parameters. They do not establish polish/render timing, shader build
counts, physical pixels, or complete transition qualification.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ("ModernTextField", "ModernComboBox", "PillButton", "HomeGrid")


@pytest.mark.parametrize("control", CONTROLS)
@pytest.mark.parametrize("repair", [False, True])
def test_actual_controls_hidden_visible_dpi_theme_and_shadow_parameters(control, repair):
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    environment.pop("PYTHONPATH", None)
    environment.pop("CSPM_EXPERIMENTAL_LAYOUT_REPAIR", None)
    environment.pop("CSPM_EXPERIMENTAL_TRANSITION", None)
    environment.pop("CSPM_EXPERIMENTAL_REDUCED_MOTION", None)
    if repair:
        environment["CSPM_EXPERIMENTAL_LAYOUT_REPAIR"] = "1"
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe", control, str(int(repair))],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QML binding checks passed" in result.stdout


def run_probe(control_name: str, repair: bool):
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
    from PySide6.QtQuick import QQuickItem

    sys.path.append(str(ROOT / "src/python"))
    from backend.transition_experiment import TransitionExperiment

    application = QGuiApplication([])
    engine = QQmlEngine()
    selector = TransitionExperiment()
    assert selector.engine == "production"
    assert selector.layoutRepair is repair
    engine.rootContext().setContextProperty("transitionExperiment", selector)
    qml = '''import QtQuick
import "../src/qml/components"
import "../src/qml/views"
Item {
    id: fixture
    width: 1100
    height: 760
    property bool pageVisible: true
    property string style: "Professional"
    property var theme: ({mode: "light", bg: "#FFFFFF", panel: "#FFFFFF", panel2: "#F0F2F4",
        text: "#152235", accent: "#315078"})
    property var metricPayload: ({contentW: 1100, contentH: 760,
        scalePercent: 100, fontFloorBodyPx: 11, fontFloorLabelPx: 10})
    Item {
        id: page
        objectName: "page"
        visible: fixture.pageVisible
        anchors.fill: parent
        CONTROL {
            objectName: "control"
            width: page.width
            height: page.height
            metrics: fixture.metricPayload
            t: fixture.theme
            EXTRA
        }
    }
}
'''.replace("CONTROL", control_name).replace("EXTRA", "" if control_name == "HomeGrid" else (
        'appStyle: fixture.style' if control_name == "ModernComboBox"
        else 'appStyle: fixture.style\n            text: "Preserved draft"'))
    component = QQmlComponent(engine)
    component.setData(qml.encode("utf-8"), QUrl.fromLocalFile(str(Path(__file__).resolve())))
    assert component.isReady(), component.errorString()
    fixture = component.create()
    assert fixture is not None, component.errorString()
    control = fixture.findChild(QQuickItem, "control")
    assert control is not None

    def evaluate(item, source):
        expression = QQmlExpression(QQmlEngine.contextForObject(item), item, source)
        result = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        result = result[0] if isinstance(result, tuple) else result
        return result.toVariant() if hasattr(result, "toVariant") else result

    def metrics():
        return evaluate(control, "layoutMetrics")

    def gates():
        return [child for child in control.findChildren(QObject)
                if child.metaObject().indexOfProperty("inputMetrics") >= 0
                and child.metaObject().indexOfProperty("revision") >= 0]

    def shadows():
        return [child for child in control.findChildren(QObject)
                if child.metaObject().className().split("_QMLTYPE_")[0] == "DropShadow"]

    def expected_shadow():
        unit = min(metrics()["contentW"], metrics()["contentH"])
        if repair and fixture.property("style") == "Professional":
            return 0, 9
        if control_name == "PillButton":
            return max(1, round(unit * 0.0085)), max(5, round(unit * 0.018))
        radius = 4 if fixture.property("style") == "Professional" else max(4, round(unit * 0.011 * 1.8))
        return radius, max(10, round(unit * 0.011 * 4))

    def assert_shadows_current():
        if control_name == "HomeGrid":
            return
        actual = shadows()
        assert len(actual) == 1, [child.metaObject().className() for child in control.findChildren(QObject)]
        assert (actual[0].property("radius"), actual[0].property("samples")) == expected_shadow()

    if control_name == "PillButton":
        # A disabled Item layer defers its effect object until a rendering
        # context exists. Instantiate its actual declarative component in its
        # original QML context to inspect the bindings without creating a window.
        effect = evaluate(control, "background.layer.effect.createObject(background)")
        assert effect is not None

    initial = metrics()
    assert initial["contentW"] == 1100
    assert control.property("visible") is True
    assert control.property("layoutRepairEnabled") is repair
    assert_shadows_current()
    if control_name == "ModernComboBox":
        control.setProperty("fullModel", ["Kept option", "Another option"])
        control.setProperty("currentIndex", 1)
        saved_model = evaluate(control, "JSON.stringify(fullModel)")
    saved_text = control.property("text") if control_name != "HomeGrid" else None
    revisions = [gate.property("revision") for gate in gates()]
    shadow_changes = []
    for shadow in shadows():
        shadow.radiusChanged.connect(lambda: shadow_changes.append("radius"))
        shadow.samplesChanged.connect(lambda: shadow_changes.append("samples"))

    fixture.setProperty("pageVisible", False)
    assert control.property("visible") is False  # Effective ancestor visibility.
    next_metrics = {"contentW": 1920, "contentH": 1040, "scalePercent": 225,
                    "fontFloorBodyPx": 24, "fontFloorLabelPx": 22}
    fixture.setProperty("metricPayload", {**next_metrics, "contentH": 760})
    fixture.setProperty("metricPayload", next_metrics)
    fixture.setProperty("width", 1920)
    fixture.setProperty("height", 1040)
    assert metrics() == (initial if repair else next_metrics)
    if repair:
        assert [gate.property("revision") for gate in gates()] == revisions
        assert shadow_changes == []
    # Theme remains reactive while layout metrics are held.
    fixture.setProperty("theme", {"mode": "dark", "bg": "#13202F", "panel": "#13202F", "panel2": "#192738",
                                  "text": "#FAFAFA", "accent": "#53749A"})
    assert evaluate(control, "t.text") == "#FAFAFA"
    if control_name in ("ModernTextField", "ModernComboBox"):
        assert evaluate(control, "tokenInk.r > 0.9") is True
    elif control_name == "PillButton":
        assert evaluate(control, "proInk.r > 0.9") is True
    else:
        assert evaluate(control, "textColor.r > 0.9") is True
    assert_shadows_current()

    # No event processing between making visible and checking the actual control.
    fixture.setProperty("pageVisible", True)
    assert metrics() == next_metrics
    assert control.property("visible") is True
    if repair:
        assert [gate.property("revision") for gate in gates()] == [revision + 1 for revision in revisions]
        if control_name == "HomeGrid":
            frames = [child for child in control.childItems()
                      if child.metaObject().className().startswith("QQuickRectangle")]
            assert len(frames) == 1
            assert (frames[0].width(), frames[0].height()) == (1920, 1040)
        else:
            assert shadow_changes == []  # Disabled shader inputs remain fixed.
    assert_shadows_current()
    if control_name != "HomeGrid":
        assert control.property("text") == saved_text
    if control_name == "ModernComboBox":
        assert evaluate(control, "JSON.stringify(fullModel)") == saved_model
        assert control.property("currentIndex") == 1

    # Visible controls receive further DPI/size updates without hiding first.
    visible_metrics = {**next_metrics, "contentW": 1600, "contentH": 900,
                       "scalePercent": 125, "fontFloorBodyPx": 15, "fontFloorLabelPx": 14}
    fixture.setProperty("metricPayload", visible_metrics)
    assert metrics() == visible_metrics
    if control_name != "HomeGrid":
        assert evaluate(control, 'metricFloor("fontFloorBodyPx", 1)') == 15
    assert_shadows_current()
    # Re-enable shadows at the current geometry, then resize while enabled.
    if control_name != "HomeGrid":
        fixture.setProperty("style", "Console")
        assert_shadows_current()
        fixture.setProperty("metricPayload", {**visible_metrics, "contentW": 2000, "contentH": 1200})
        assert_shadows_current()
        fixture.setProperty("pageVisible", False)
        fixture.setProperty("metricPayload", next_metrics)
        fixture.setProperty("style", "Professional")
        assert_shadows_current()
        fixture.setProperty("style", "Console")
        fixture.setProperty("pageVisible", True)
        assert metrics() == next_metrics
        assert_shadows_current()
    print("QML binding checks passed")
    fixture.deleteLater()
    application.processEvents()


if __name__ == "__main__":
    assert len(sys.argv) == 4 and sys.argv[1] == "--probe"
    run_probe(sys.argv[2], sys.argv[3] == "1")
