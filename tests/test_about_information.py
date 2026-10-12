"""About truth/privacy and actual offscreen QML/clipboard checks; no WebEngine."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.about import AboutInformation, UNAVAILABLE, copy_text, version_information

SPEC = importlib.util.spec_from_file_location("about_release_builder", ROOT / "scripts/build_release.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

VERSION = {"version": "2.4.0", "codename": "Phase 9", "build": "1"}
STAMP = "2026-10-12T14:09:08.123456+00:00"
SHA = "a" * 40


def metadata():
    return dict(schemaVersion=2, sourceSha=SHA, sourceStatus="clean", buildTimestampUtc=STAMP,
                version="2.4.0", codename="Phase 9", versionBuild="1")


def test_packaging_uses_one_exact_invocation_instant_and_existing_version(tmp_path, monkeypatch):
    calls = []
    def output(command, **kwargs):
        calls.append(command)
        return SHA + "\n" if command[1] == "rev-parse" else ""
    monkeypatch.setattr(BUILDER.subprocess, "check_output", output)
    bridge = tmp_path / "native.dll"
    bridge.write_bytes(b"synthetic native binary")
    invoked = datetime(2026, 10, 12, 10, 9, 8, 123456, tzinfo=timezone(timedelta(hours=-4)))
    result = BUILDER.release_provenance(tmp_path, bridge, VERSION, invoked)
    assert result["buildTimestampUtc"] == STAMP
    assert result["version"] == "2.4.0"
    assert result["codename"] == "Phase 9" and result["versionBuild"] == "1"
    assert result["sourceSha"] == SHA and result["sourceStatus"] == "clean"
    assert result["sourceDirty"] is False
    assert result["nativeDllSha256"] == hashlib.sha256(bridge.read_bytes()).hexdigest().upper()
    assert "executableSha256" not in result
    assert calls[-1] == ["git", "status", "--porcelain", "--untracked-files=all"]
    assert [path.name for path in tmp_path.iterdir()] == ["native.dll"]


@pytest.mark.parametrize("status", [" M src/python/main.py\n", "?? new_source.py\n"])
def test_dirty_or_untracked_source_cannot_be_called_clean(tmp_path, monkeypatch, status):
    monkeypatch.setattr(BUILDER.subprocess, "check_output",
                        lambda command, **kwargs: SHA if command[1] == "rev-parse" else status)
    bridge = tmp_path / "native.dll"
    bridge.write_bytes(b"synthetic")
    result = BUILDER.release_provenance(tmp_path, bridge, VERSION, datetime.now(timezone.utc))
    assert result["sourceDirty"] is True and result["sourceStatus"] == "modified"


def test_packaging_rejects_naive_time(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        BUILDER.release_provenance(tmp_path, tmp_path / "unused", VERSION, datetime(2026, 10, 12))


def test_about_hashes_actual_executable_and_local_time_is_same_instant(tmp_path):
    exe = tmp_path / "CSPM.exe"
    exe.write_bytes(b"installed synthetic executable")
    local_tz = timezone(timedelta(hours=-4))
    result = version_information(metadata(), VERSION, executable=exe, motion="native", local_timezone=local_tz)
    assert result["executableSha256"] == hashlib.sha256(exe.read_bytes()).hexdigest().upper()
    assert result["buildUtc"] == STAMP + " (UTC)"
    assert result["buildLocal"] == "2026-10-12T10:09:08.123456-04:00"
    assert datetime.fromisoformat(result["buildLocal"]) == datetime.fromisoformat(STAMP)


@pytest.mark.parametrize("timestamp", [None, "", "not a date", "2026-10-12T14:09:08", "2026-10-12T10:09:08-04:00"])
def test_about_does_not_guess_missing_or_invalid_build_time(timestamp):
    payload = metadata()
    payload["buildTimestampUtc"] = timestamp
    result = version_information(payload, VERSION, executable=None, motion="native")
    assert result["buildUtc"] == result["buildLocal"] == UNAVAILABLE


def test_clipboard_whitelist_rejects_private_values_and_ignores_extra_fields():
    private = "C:/Users/PrivateUser/workbooks/client-secret.xlsm"
    payload = dict(version=private, codename=private, versionBuild=private, sourceSha=private,
                   sourceStatus=[private], buildTimestampUtc=private, repository=private,
                   username=private, credentials=private, clients=[private], executableSha256=private)
    result = version_information(payload, VERSION, executable=None, motion="legacy")
    copied = copy_text(result)
    for forbidden in (private, "PrivateUser", "client-secret", "workbooks", "credentials", "C:/"):
        assert forbidden not in copied
    assert "Product: CSPM" in copied and "Motion preference: legacy" in copied


@pytest.fixture(scope="module")
def gui():
    instance = QGuiApplication.instance()
    if instance is not None and not isinstance(instance, QGuiApplication):
        pytest.skip("Run About UI/clipboard checks separately from a QCoreApplication fixture")
    return instance or QGuiApplication([])


@pytest.fixture
def provider(tmp_path):
    (tmp_path / "version.json").write_text(json.dumps(VERSION))
    (tmp_path / "release-provenance.json").write_text(json.dumps(metadata()))
    exe = tmp_path / "CSPM.exe"
    exe.write_bytes(b"runtime synthetic")
    return AboutInformation(SimpleNamespace(engine="native", reducedMotion=False), root=tmp_path,
                            executable=exe, frozen=True)


def test_runtime_clipboard_is_safe_and_reports_actual_preferences(gui, provider):
    for preference in ("native", "legacy", "reduced"):
        provider._motion.engine = preference
        assert provider.copyVersionInformation(False)
        assert f"Motion preference: {preference}" in gui.clipboard().text()
    provider._motion.engine = "native"
    provider._motion.reducedMotion = True
    assert provider.information(False)["motionPreference"] == "reduced"
    provider._motion.reducedMotion = False
    assert provider.information(True)["motionPreference"] == "reduced"
    copied = gui.clipboard().text()
    assert STAMP in copied and SHA in copied
    assert str(provider._root) not in copied and str(provider._executable) not in copied


def test_frozen_missing_metadata_never_substitutes_runtime_or_source_times(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.about.subprocess.check_output", lambda *a, **k: pytest.fail("Frozen About consulted Git"))
    provider = AboutInformation(SimpleNamespace(engine="legacy", reducedMotion=False), root=tmp_path,
                                executable=tmp_path / "missing.exe", frozen=True)
    result = provider.information(False)
    assert result["buildUtc"] == result["sourceSha"] == result["executableSha256"] == UNAVAILABLE


def test_actual_qml_dialog_displays_snapshot_and_copy_action(gui, provider):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("testAboutInformation", provider)
    imports = QUrl.fromLocalFile(str(ROOT / "src/qml/components")).toString()
    source = f'''import QtQuick
import QtQuick.Controls
import "{imports}"
ApplicationWindow {{
    width: 900; height: 700; visible: false
    AboutDialog {{ informationProvider: testAboutInformation; t: ({{}}) }}
}}'''
    engine.loadData(source.encode())
    assert engine.rootObjects(), "About QML failed to load"
    window = engine.rootObjects()[0]
    dialog = window.findChild(QObject, "CSPMAboutDialog")
    assert dialog is not None
    assert QMetaObject.invokeMethod(dialog, "open")
    gui.processEvents()
    text = window.findChild(QObject, "CSPMAboutVersionText")
    assert text is not None and text.property("readOnly")
    assert SHA in text.property("text") and STAMP in text.property("text")
    button = window.findChild(QObject, "CSPMAboutCopyButton")
    assert button is not None and button.property("activeFocusOnTab")
    assert QMetaObject.invokeMethod(button, "clicked")
    assert "Source status: clean" in gui.clipboard().text()
    QMetaObject.invokeMethod(dialog, "close")
    window.close()
    engine.deleteLater()
    gui.processEvents()


def test_ui_menu_shortcut_and_packaging_contracts():
    menu = (ROOT / "src/qml/components/SettingsMenu.qml").read_text(encoding="utf-8")
    shell = (ROOT / "src/qml/DetachedShellWindow.qml").read_text(encoding="utf-8")
    builder = (ROOT / "scripts/build_release.py").read_text(encoding="utf-8")
    assert 'objectName: "CSPMAboutMenuItem"' in menu and 'Accessible.name: "About CSPM"' in menu
    assert "root.aboutRequested()" in menu and "onAboutRequested: aboutDialog.open()" in shell
    assert 'sequence: "Ctrl+Shift+A"' in shell
    assert builder.count('"--specpath", str(build_dir / "specs")') == 2
    assert 'Source identity changed during packaging' in builder
