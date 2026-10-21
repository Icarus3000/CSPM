"""Manual tray entry contracts without production data or a visible window."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.controllers.tray_controller import TrayController, TrayRecordedEntry


@pytest.fixture
def manual_tray():
    qt = QCoreApplication.instance() or QCoreApplication([])
    backend = SimpleNamespace(_excel_repo=None, _theme_name="Dark")
    backend.saveTimeDocketEntry = MagicMock(return_value={"ok": True, "entryId": "T-SAVED"})
    tray = TrayController(backend)
    yield tray, backend
    tray._timer.stop()
    tray._sqlite_edit_debounce_timer.stop()
    tray._exit_failsafe_timer.stop()
    qt.processEvents()


@pytest.mark.parametrize("duration", ["", "nonsense", "0", "-1"])
def test_invalid_manual_time_does_not_start_or_save(manual_tray, duration):
    tray, backend = manual_tray
    commands = []
    tray.mainTimerCommandRequested.connect(commands.append)
    assert tray.saveManualTimeEntry("Client", "Matter", "Review", duration) is False
    backend.saveTimeDocketEntry.assert_not_called()
    assert tray._timers == [] and tray._entries == [] and commands == []


def test_new_manual_entry_preserves_existing_draft_and_never_starts_timer(manual_tray):
    tray, backend = manual_tray
    draft_id = tray.createNewDraftTab()
    commands = []
    tray.mainTimerCommandRequested.connect(commands.append)
    assert tray.saveManualTimeEntry("Client", "Matter", "Review", "45m") is True
    assert any(d["tabId"] == draft_id for d in tray._draft_tabs)
    assert tray._timers == []
    assert tray._entries[0]._exact_seconds == 2700
    payload = backend.saveTimeDocketEntry.call_args.args[0]
    assert payload["entryId"] == "" and payload["rawSeconds"] == 2700
    assert not any(c.get("action") in {"start_new", "resume"} for c in commands)


@pytest.mark.parametrize("save_result", [{"ok": False}, {}, {"ok": True}, RuntimeError("Read-only data")])
def test_failed_manual_save_preserves_selected_draft(manual_tray, save_result):
    tray, backend = manual_tray
    draft_id = tray.createNewDraftTab()
    before = [dict(d) for d in tray._draft_tabs]
    if isinstance(save_result, Exception):
        backend.saveTimeDocketEntry.side_effect = save_result
    else:
        backend.saveTimeDocketEntry.return_value = save_result
    assert tray.saveSelectedManualTimeEntry("Client", "Matter", "Review", "0.5") is False
    assert tray._draft_tabs == before and tray.selectedTabId == draft_id
    assert tray._timers == [] and tray._entries == []


def test_selected_manual_save_updates_same_saved_entry(manual_tray):
    tray, backend = manual_tray
    original = TrayRecordedEntry("T-ORIGINAL", dt.date.today().isoformat(), 1.0,
                                 "Old Client", "Old Matter", "09:00", exact_seconds=3600,
                                 description="Old narrative", parent=tray)
    tray._entries = [original]
    tray._selected_tab_id = "entry:T-ORIGINAL"
    backend.saveTimeDocketEntry.return_value = {"ok": True, "entryId": "T-ORIGINAL"}
    assert tray.saveSelectedManualTimeEntry("Client", "Matter", "Review", "30m") is True
    payload = backend.saveTimeDocketEntry.call_args.args[0]
    assert payload["entryId"] == "T-ORIGINAL" and payload["isLegacyUpdate"] is True
    assert len(tray._entries) == 1 and tray._entries[0] is original
    assert original._exact_seconds == 1800 and original.description == "Review"
    assert original.client_display_name == "Client" and original.matter_display_name == "Matter"
    assert tray._timers == []


def test_real_flyout_suggestions_and_save_controls():
    script = r'''
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem

root = Path.cwd()
sys.path.insert(0, str(root / "src/python"))
from backend.controllers.tray_controller import TrayController

app = QGuiApplication([])
backend = SimpleNamespace(_excel_repo=None, _theme_name="Dark")
backend.saveTimeDocketEntry = MagicMock(return_value={"ok": True, "entryId": "T-UI"})
tray = TrayController(backend)
directory = [
    {"matterId": "M1", "matterNumber": "ONE-001", "matterName": "First matter", "clientName": "One Client", "clientId": "C1"},
    {"matterId": "M2", "matterNumber": "MANY-001", "matterName": "Second matter", "clientName": "Many Client", "clientId": "C2"},
    {"matterId": "M3", "matterNumber": "MANY-002", "matterName": "Third matter", "clientName": "Many Client", "clientId": "C2"},
]
backend.listActiveMatterDirectory = lambda: directory
backend.listActiveMatterNames = lambda: ["ONE-001", "MANY-001", "MANY-002"]
backend.listActiveClientNames = lambda: ["One Client", "Many Client"]
engine = QQmlEngine()
engine.rootContext().setContextProperty("trayController", tray)
component = QQmlComponent(engine, QUrl.fromLocalFile(str(root / "src/qml/tray/TrayTimekeepingFlyout.qml")))
assert component.isReady(), [e.toString() for e in component.errors()]
item = component.create()
assert item is not None, [e.toString() for e in component.errors()]
item.setProperty("width", 540)
item.setProperty("height", 400)

def invoke(source):
    expression = QQmlExpression(QQmlEngine.contextForObject(item), item, source)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result[0] if isinstance(result, tuple) else result

def field(name):
    control = item.findChild(QObject, name)
    assert control is not None, name
    return control

invoke("openNewTimerPicker(false)")
client = field("trayNewClientInput")
matter = field("trayNewMatterInput")
duration = field("trayNewTimeInput")
assert client.property("text") == "" and matter.property("text") == ""
# Exercise the real delegate's click handler: this used to throw flyout undefined.
client.setProperty("text", "One Client")
matter.setProperty("text", "stale matter search")
item.setProperty("activeDropdownTarget", "client")
invoke("refreshNewTimerSuggestions()")
invoke("suggestionListView.forceLayout()")
app.processEvents()
def visual_descendants(control):
    for child in control.childItems():
        yield child
        yield from visual_descendants(child)
clicks = [control for control in visual_descendants(item)
          if control.objectName() == "trayPickerSuggestionClickArea"]
assert clicks, "client suggestion delegate was not instantiated"
engine.globalObject().setProperty("suggestionClick", engine.newQObject(clicks[0]))
click_result = engine.evaluate("suggestionClick.clicked(null)")
assert not click_result.isError(), click_result.toString()
assert client.property("text") == "One Client"
assert "ONE-001" in matter.property("text"), matter.property("text")
# A client with several matters clears the old matter and presents its choices.
item.setProperty("activeDropdownTarget", "client")
invoke('selectPickerSuggestion("Many Client")')
assert matter.property("text") == ""
assert item.property("activeDropdownTarget") == "matter"
assert len(tray.filterMattersByClient("Many Client")) == 2
# Selecting a matter fills its client.
item.setProperty("activeDropdownTarget", "matter")
invoke('selectPickerSuggestion("ONE-001 — First matter")')
assert client.property("text") == "One Client"
# Save with missing/invalid time stays open and never starts a timer.
duration.setProperty("text", "")
invoke("commitManualSaveFromPicker()")
assert item.property("newTimerPickerOpen") is True
assert item.property("pickerErrorText")
backend.saveTimeDocketEntry.assert_not_called()
duration.setProperty("text", "30m")
backend.saveTimeDocketEntry.return_value = {"ok": False, "message": "Read-only"}
invoke("commitManualSaveFromPicker()")
assert item.property("newTimerPickerOpen") is True
assert tray._timers == [] and tray._entries == []
backend.saveTimeDocketEntry.return_value = {"ok": True, "entryId": "T-UI"}
invoke("commitManualSaveFromPicker()")
assert item.property("newTimerPickerOpen") is False
assert tray._timers == [] and tray._entries[0]._exact_seconds == 1800
tray._timer.stop()
tray._sqlite_edit_debounce_timer.stop()
tray._exit_failsafe_timer.stop()
item.deleteLater()
app.processEvents()
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
