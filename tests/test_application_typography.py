"""Actual Qt font coverage and QML family resolution, without WebEngine/windows."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "src/qml/assets/fonts"


@pytest.fixture(scope="module")
def typography():
    # Other suites legitimately create a QCoreApplication for their JS probes.
    # It cannot be upgraded to QGuiApplication; keep font/GUI work isolated.
    return None


def _isolated_assertion(name):
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe", name],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Typography check passed" in result.stdout


def _configured_application():
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])
    spec = importlib.util.spec_from_file_location(
        "cspm_application_typography", ROOT / "src/python/backend/application_typography.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_family = app.font().family()
    result = module.configure_application_typography(app, ROOT)
    return app, result, original_family


def test_every_ui_private_use_glyph_has_a_real_nonempty_qt_outline(typography):
    if typography is None:
        _isolated_assertion("test_every_ui_private_use_glyph_has_a_real_nonempty_qt_outline")
        return
    from PySide6.QtGui import QFont, QFontInfo, QRawFont

    font = QFont("CSPM Symbols")
    font.setPixelSize(20)
    raw = QRawFont.fromFont(font)
    assert raw.isValid()
    assert QFontInfo(font).family() == "CSPM Symbols"
    private_codes = set()
    for path in (ROOT / "src/qml").rglob("*"):
        if path.suffix in (".qml", ".js"):
            private_codes.update(int(code, 16) for code in re.findall(
                r"\\u([eEfF][0-9a-fA-F]{3})", path.read_text()))
    assert private_codes
    for code in private_codes:
        glyphs = raw.glyphIndexesForString(chr(code))
        assert raw.supportsCharacter(code), f"Missing UI glyph U+{code:04X}"
        assert len(glyphs) == 1 and glyphs[0] != 0, f"Fallback glyph U+{code:04X}"
        assert not raw.pathForGlyph(glyphs[0]).isEmpty(), f"Blank UI glyph U+{code:04X}"


def test_tray_calendar_and_console_symbols_resolve_without_emoji_fonts(typography):
    if typography is None:
        _isolated_assertion("test_tray_calendar_and_console_symbols_resolve_without_emoji_fonts")
        return
    from PySide6.QtGui import QFont, QRawFont

    metadata = json.loads((FONT_DIR / "CSPMSymbols.json").read_text())
    assert hashlib.sha256((FONT_DIR / "CSPMSymbols.ttf").read_bytes()).hexdigest() == metadata["font_sha256"]
    font = QFont("CSPM Symbols")
    font.setPixelSize(16)
    raw = QRawFont.fromFont(font)
    for code in metadata["unicode_icons"]:
        glyphs = raw.glyphIndexesForString(chr(int(code, 16)))
        assert glyphs and glyphs[0] != 0, f"Missing utility symbol U+{code}"
        assert not raw.pathForGlyph(glyphs[0]).isEmpty(), f"Blank utility symbol U+{code}"


def test_qml_controls_use_registered_platform_families(typography):
    if typography is None:
        _isolated_assertion("test_qml_controls_use_registered_platform_families")
        return
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    app, result, original_family = typography
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
import "../src/qml/standards/AppTypography.js" as AppTypography
QtObject {
    property string body: AppTypography.textFamily()
    property string billing: AppTypography.interFamily()
    property string icons: AppTypography.iconFamily()
    property string symbols: AppTypography.symbolFamily()
    property string mono: AppTypography.monoFamily("Consolas")
}''', QUrl.fromLocalFile(str(ROOT / "tests/typography_probe.qml")))
    assert component.isReady(), [error.toString() for error in component.errors()]
    item = component.create()
    assert item is not None, [error.toString() for error in component.errors()]
    if sys.platform == "win32":
        assert app.font().family() == original_family
        assert item.property("body") == "Segoe UI"
        assert item.property("billing") == "Inter"
        assert item.property("icons") == "Segoe MDL2 Assets"
        assert item.property("mono") == "Consolas"
    else:
        assert item.property("body") == result["text"]
        assert item.property("billing") == result["text"]
        assert item.property("icons") == "CSPM Symbols"
        assert item.property("symbols") == "CSPM Symbols"
        assert item.property("mono") == "monospace"
    del item
    del component
    del engine


def test_complete_tray_qml_loads_with_timer_rows_and_portable_symbols(typography):
    if typography is None:
        _isolated_assertion("test_complete_tray_qml_loads_with_timer_rows_and_portable_symbols")
        return
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    app, _, _ = typography
    engine = QQmlEngine()
    mock_component = QQmlComponent(engine)
    mock_component.setData(b'''import QtQuick
QtObject {
    property bool isDarkMode: false
    property string currentDate: "October 14, 2026"
    property string recordedTodayFormatted: "00:30:00"
    property string activeNowFormatted: "00:01:05"
    property string totalTodayFormatted: "00:31:05"
    property var missingDescriptionEntries: []
    property var activeTimers: [{id: "timer-test", isRunning: true, elapsedSeconds: 65,
        clientName: "Example client", matterName: "Example matter", description: "Synthetic timer"}]
    property var recordedEntries: [{id: "entry-test", decimalHours: 0.5, timeStr: "09:00",
        clientName: "Example client", matterName: "Example matter", description: "Synthetic docket"}]
    signal flyoutGeometryCalculated(int x, int y, int w, int h)
    signal promptMissingDescriptions()
    signal showTrayToast(string message)
    function formatElapsed(value) { return "00:01:05" }
    function availableClients() { return [] }
    function availableMatters() { return [] }
    function filterClients(value) { return [] }
    function filterMattersByClient(value) { return [] }
    function filterMattersByClientAndText(client, text) { return [] }
}''', QUrl.fromLocalFile(str(ROOT / "tests/tray_context_probe.qml")))
    assert mock_component.isReady(), [error.toString() for error in mock_component.errors()]
    mock = mock_component.create()
    assert mock is not None
    engine.rootContext().setContextProperty("trayController", mock)
    tray = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "src/qml/tray/TrayRoot.qml")))
    assert tray.isReady(), [error.toString() for error in tray.errors()]
    item = tray.create()
    assert item is not None, [error.toString() for error in tray.errors()]
    app.processEvents()
    item.deleteLater()
    app.processEvents()
    del tray
    del engine


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--probe":
    assertion = globals()[sys.argv[2]]
    assertion(_configured_application())
    print("Typography check passed")
