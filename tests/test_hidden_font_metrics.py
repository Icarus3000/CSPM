"""Offscreen Qt Quick semantics; no window, WebEngine or desktop capture."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "src/qml/views/PlaceholderSubmenuView.qml"
FONT_METRICS = ROOT / "src/qml/standards/HiddenFontMetrics.js"
FONT_GATES = ROOT / "src/qml/components"


@pytest.fixture(scope="module")
def observed():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software",
                       PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe"],
                            cwd=ROOT, env=environment, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_default_without_experiment_keeps_hidden_font_bindings_live(observed):
    assert observed["ordinary"] == {"enabled": False, "font": 29, "notifications": 1}


def test_hidden_ancestor_holds_font_and_implicit_size_without_freezing_data(observed):
    hidden = observed["hidden"]
    assert hidden["font"] == 12
    assert hidden["notifications"] == 0
    assert hidden["implicitHeight"] == hidden["beforeHeight"]
    assert hidden["explicitChildVisible"] is False
    assert hidden["text"] == "Draft changed while hidden"
    assert hidden["model"] == "Model changed while hidden"


def test_font_catches_up_to_latest_input_synchronously_on_show(observed):
    assert observed["shown"] == {"font": 29, "secondFont": 35, "notifications": 1}


def test_visible_opacity_zero_target_font_remains_current(observed):
    assert observed["transparent"] == {"font": 32, "secondFont": 37,
                                       "notifications": 1, "visible": True}


def test_independent_hidden_owners_do_not_share_cached_font_values(observed):
    assert observed["owners"] == [12, 16]


def test_initially_hidden_item_seeds_input_and_catches_up_on_show(observed):
    assert observed["initiallyHidden"] == [12, 12, 29]


def test_disabling_and_reenabling_repair_keeps_latest_disabled_input(observed):
    assert observed["toggle"] == [33, 33, 41]


def test_missing_or_nonvisual_owner_passes_input_through(observed):
    assert observed["nonvisual"] == [18, 22]


def test_no_desktop_window_is_constructed(observed):
    assert observed["windows"] == 0


def run_probe():
    from PySide6.QtCore import Property, QObject, QUrl, Signal
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    class Experiment(QObject):
        changed = Signal()

        def __init__(self):
            super().__init__()
            self._enabled = True

        def get_enabled(self):
            return self._enabled

        def set_enabled(self, value):
            if self._enabled != value:
                self._enabled = value
                self.changed.emit()

        layoutRepair = Property(bool, get_enabled, set_enabled, notify=changed)

    source = VIEW.read_text(encoding="utf-8")
    helper = re.search(r"    function fontPixelSize\(owner, value\) \{.*?\n    \}",
                       source, re.S).group()
    enabled = re.search(r"    readonly property bool layoutRepairEnabled:.*?\n        && layoutDevelopment.layoutRepair",
                        source, re.S).group()
    application = QGuiApplication([])
    # The imported library and view helper are the retained runtime code.
    qml = ("import QtQuick\nimport \"" + FONT_METRICS.as_uri() + "\" as HiddenFontMetrics\n"
           "import \"" + FONT_GATES.as_uri() + "\"\nItem {\n    id: root\n" + enabled + "\n" + helper + "\n" + '''
    property int requestedFont: 12
    property int requestedSecondFont: 16
    property bool pageVisible: true
    property real pageOpacity: 1
    property int notifications: 0
    property alias actualFont: label.font.pixelSize
    property alias actualSecondFont: second.font.pixelSize
    property alias actualHeight: label.implicitHeight
    property alias childVisible: label.visible
    property alias draft: editor.text
    function modelDraft() { return rows.get(0).draft }
    function updateModel(value) { rows.setProperty(0, "draft", value) }
    ListModel { id: rows; ListElement { draft: "Model before" } }
    Item {
        visible: root.pageVisible
        opacity: root.pageOpacity
        Item {
            visible: true
            Text {
                id: label
                text: "Stable metrics label"
                property HiddenFontGate cspmFontGate: HiddenFontGate {
                    inputPixelSize: root.requestedFont
                    active: !root.layoutRepairEnabled || label.visible
                }
                font.pixelSize: cspmFontGate.pixelSize
                onFontChanged: ++root.notifications
            }
            Text {
                id: second
                text: "Independent owner"
                property HiddenFontGate cspmFontGate: HiddenFontGate {
                    inputPixelSize: root.requestedSecondFont
                    active: !root.layoutRepairEnabled || second.visible
                }
                font.pixelSize: cspmFontGate.pixelSize
            }
            TextEdit { id: editor; text: "Draft before" }
        }
    }
}''').encode("utf-8")
    objects = []

    def fixture(experiment=None, initially_hidden=False):
        engine = QQmlEngine()
        if experiment is not None:
            engine.rootContext().setContextProperty("layoutDevelopment", experiment)
        component = QQmlComponent(engine)
        component.setData(qml, QUrl.fromLocalFile(str(VIEW.parent / "no_window_font_probe.qml")))
        assert component.isReady(), component.errorString()
        item = component.createWithInitialProperties({"pageVisible": not initially_hidden})
        assert item is not None, component.errorString()
        engine.globalObject().setProperty("item", engine.newQObject(item))
        item.setProperty("notifications", 0)
        objects.append((engine, component, item))
        return engine, item

    observed = {}
    ordinary_engine, ordinary = fixture()
    ordinary.setProperty("pageVisible", False)
    ordinary.setProperty("requestedFont", 29)
    observed["ordinary"] = {"enabled": ordinary.property("layoutRepairEnabled"),
                            "font": ordinary.property("actualFont"),
                            "notifications": ordinary.property("notifications")}
    experiment = Experiment()
    engine, item = fixture(experiment)
    before_height = item.property("actualHeight")
    item.setProperty("pageVisible", False)
    for value in (21, 25, 29):
        item.setProperty("requestedFont", value)
    item.setProperty("requestedSecondFont", 35)
    item.setProperty("draft", "Draft changed while hidden")
    result = engine.evaluate('item.updateModel("Model changed while hidden"); item.modelDraft()')
    assert not result.isError(), result.toString()
    observed["owners"] = [item.property("actualFont"), item.property("actualSecondFont")]
    observed["hidden"] = {"font": item.property("actualFont"),
                          "notifications": item.property("notifications"),
                          "beforeHeight": before_height,
                          "implicitHeight": item.property("actualHeight"),
                          "explicitChildVisible": item.property("childVisible"),
                          "text": item.property("draft"), "model": result.toString()}
    item.setProperty("pageVisible", True)
    observed["shown"] = {"font": item.property("actualFont"),
                         "secondFont": item.property("actualSecondFont"),
                         "notifications": item.property("notifications")}
    item.setProperty("notifications", 0)
    item.setProperty("pageOpacity", 0)
    item.setProperty("requestedFont", 32)
    item.setProperty("requestedSecondFont", 37)
    observed["transparent"] = {"font": item.property("actualFont"),
                               "secondFont": item.property("actualSecondFont"),
                               "notifications": item.property("notifications"),
                               "visible": item.property("childVisible")}
    _, initially_hidden = fixture(experiment, initially_hidden=True)
    seeded = initially_hidden.property("actualFont")
    initially_hidden.setProperty("requestedFont", 29)
    held = initially_hidden.property("actualFont")
    initially_hidden.setProperty("pageVisible", True)
    observed["initiallyHidden"] = [seeded, held, initially_hidden.property("actualFont")]
    initially_hidden.setProperty("pageVisible", False)
    experiment.set_enabled(False)
    initially_hidden.setProperty("requestedFont", 33)
    disabled = initially_hidden.property("actualFont")
    experiment.set_enabled(True)
    reenabled = initially_hidden.property("actualFont")
    initially_hidden.setProperty("requestedFont", 41)
    initially_hidden.setProperty("pageVisible", True)
    observed["toggle"] = [disabled, reenabled, initially_hidden.property("actualFont")]
    result = engine.evaluate('item.fontPixelSize(null, 18)')
    assert not result.isError(), result.toString()
    result2 = engine.evaluate('item.fontPixelSize({}, 22)')
    assert not result2.isError(), result2.toString()
    observed["nonvisual"] = [result.toInt(), result2.toInt()]
    observed["windows"] = len(application.topLevelWindows())
    for _, _, obj in objects:
        obj.deleteLater()
    application.processEvents()
    print(json.dumps(observed))


if __name__ == "__main__" and sys.argv[1:] == ["--probe"]:
    run_probe()
