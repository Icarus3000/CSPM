"""Safe checks for disposable profiling edits; no GUI or WebEngine runtime."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/diagnostics"))
from target_layout_fanout import (CURRENT_VARIANTS, HIDDEN_SCALAR_JS, TRACE_JS, VARIANTS, _hold_metric_fonts, _wrap_helpers,
                                  instrument_mirror, instrument_qt_blur)


TARGETS = (
    "DetachedShellWindow.qml",
    "views/PlaceholderSubmenuView.qml",
    "components/ModernTextField.qml",
    "components/ModernComboBox.qml",
    "components/PillButton.qml",
    "components/ProductivityReportPanel.qml",
)


def hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


@pytest.fixture
def mirror(tmp_path):
    tree = tmp_path / "logs/fanout-check/tree"
    for relative in TARGETS:
        destination = tree / "src/qml" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = (ROOT / "src/qml" / relative).read_text(encoding="utf-8")
        if relative == "DetachedShellWindow.qml":
            # The parent fixture adds this boundary marker before fanout.
            source = source.replace("    id: mainWin\n", "    id: mainWin\n"
                "    function cleanRoomNativeProfileMark(name) {\n"
                "        if (!cleanRoomNativeProfileEnabled) return;\n"
                "    }\n", 1)
        destination.write_text(source, encoding="utf-8")
    source = ROOT / "src/qml/components/LayoutMetricsGate.qml"
    (tree / "src/qml/components/LayoutMetricsGate.qml").write_bytes(source.read_bytes())
    return tree


def test_current_counts_instrument_every_target_and_leave_originals_unchanged(mirror):
    before = {relative: hashlib.sha256((ROOT / "src/qml" / relative).read_bytes()).hexdigest()
              for relative in TARGETS}
    changed = instrument_mirror(mirror, "counts")
    assert set(changed) == {"src/qml/" + relative for relative in TARGETS} | {"src/qml/FanoutTrace.js"}
    assert 'FanoutTrace.value("Shell.uiMetricsCompute"' in changed["src/qml/DetachedShellWindow.qml"]
    assert 'FanoutTrace.stage = name;' in changed["src/qml/DetachedShellWindow.qml"]
    assert 'FanoutTrace.value("Placeholder.responsiveMetricsPublication"' in changed["src/qml/views/PlaceholderSubmenuView.qml"]
    assert '\n    }), visible)' in changed["src/qml/views/PlaceholderSubmenuView.qml"]
    assert 'FanoutTrace.value("Report.shortCanvasEvaluation", root.height < 650, visible)' in changed["src/qml/components/ProductivityReportPanel.qml"]
    for relative, source in changed.items():
        assert (mirror / relative).read_text(encoding="utf-8") == source
    assert before == {relative: hashlib.sha256((ROOT / "src/qml" / relative).read_bytes()).hexdigest()
                      for relative in TARGETS}


@pytest.mark.parametrize("variant", [variant for variant in VARIANTS if variant not in CURRENT_VARIANTS])
def test_historical_variants_reject_retained_repair_without_any_writes(mirror, variant):
    before = hashes(mirror)
    with pytest.raises(ValueError, match="requires the pre-repair source"):
        instrument_mirror(mirror, variant)
    assert hashes(mirror) == before


def test_missing_last_counts_target_fails_before_writing_any_instrumentation(mirror):
    path = mirror / "src/qml/components/ProductivityReportPanel.qml"
    path.write_text(path.read_text(encoding="utf-8").replace("root.height < 650", "root.height < 640"), encoding="utf-8")
    before = hashes(mirror)
    with pytest.raises(ValueError, match="Report.shortCanvas"):
        instrument_mirror(mirror, "counts")
    assert hashes(mirror) == before


def test_fresh_mirror_required_for_repeated_instrumentation(mirror):
    instrument_mirror(mirror, "counts")
    before = hashes(mirror)
    with pytest.raises(ValueError, match="fresh disposable mirror"):
        instrument_mirror(mirror, "counts")
    assert hashes(mirror) == before


def test_publication_costs_time_setter_propagation_and_keep_helpers_unmodified(mirror):
    changed = instrument_mirror(mirror, "publication-costs")
    gate = changed["src/qml/components/LayoutMetricsGate.qml"]
    assert 'try { snapshot = next } finally { FanoutTrace.leave(publicationToken) }' in gate
    assert 'finally { FanoutTrace.leave(gateToken) }' in gate
    assert 'FanoutTrace.watchTree(mainWin.contentItem)' in changed["src/qml/DetachedShellWindow.qml"]
    assert 'FanoutTrace.enter("DetachedShellWindow.computeUiMetrics"' in changed["src/qml/DetachedShellWindow.qml"]
    assert 'FanoutTrace.enter("DetachedShellWindow.ratioToPixels"' not in changed["src/qml/DetachedShellWindow.qml"]
    for component in ("ModernTextField", "ModernComboBox", "PillButton"):
        source = changed["src/qml/components/" + component + ".qml"]
        assert 'diagnosticOwner: control' in source
        assert 'FanoutTrace.enter("' + component + '.ratioPx"' not in source


@pytest.mark.parametrize("variant", ["counts", "publication-costs"])
def test_quiet_variants_skip_tree_discovery_and_publication_instrumentation(mirror, variant):
    changed = instrument_mirror(mirror, variant, collect_counts=False)
    shell = changed["src/qml/DetachedShellWindow.qml"]
    assert "FanoutTrace.watchTree" not in shell
    assert "FanoutTrace.stage = name" not in shell
    assert "FanoutTrace.enter(" not in shell
    assert "FanoutTrace.value(" not in shell
    assert "src/qml/components/LayoutMetricsGate.qml" not in changed
    for component in ("ModernTextField", "ModernComboBox", "PillButton"):
        assert "diagnosticOwner" not in changed["src/qml/components/" + component + ".qml"]
    placeholder = changed["src/qml/views/PlaceholderSubmenuView.qml"]
    assert "FanoutTrace.value(" not in placeholder
    assert "FanoutTrace.enter(" not in placeholder
    assert "src/qml/components/ProductivityReportPanel.qml" not in changed
    assert "function fontPixelSize(" in placeholder
    assert "root.fontPixelSize(this," in placeholder


@pytest.mark.parametrize("variant", ["counts", "publication-costs"])
def test_actual_quiet_hooks_do_not_touch_the_tree_or_enable_counters(mirror, variant):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine

    changed = instrument_mirror(mirror, variant, collect_counts=False)
    shell = changed["src/qml/DetachedShellWindow.qml"]
    hooks = "\n".join(line.strip() for line in shell.splitlines()
                      if line.strip().startswith("function cleanRoomFanout"))
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QJSEngine()
    result = engine.evaluate("var touched = 0; var FanoutTrace = {"
        "begin: function() { ++touched; throw new Error('counter start'); },"
        "finish: function() { ++touched; throw new Error('counter finish'); },"
        "watchTree: function() { ++touched; throw new Error('tree discovery'); }};"
        "var mainWin = {get contentItem() { ++touched; throw new Error('tree access'); }};"
        + hooks + "\ncleanRoomFanoutBegin(); var rows = cleanRoomFanoutFinish();"
        "[touched, Object.keys(rows).length];")
    assert not result.isError(), result.toString()
    assert result.toVariant() == [0, 0]
    application.processEvents()


def test_missing_gate_publication_fails_before_any_mirror_write(mirror):
    path = mirror / "src/qml/components/LayoutMetricsGate.qml"
    path.write_text(path.read_text(encoding="utf-8").replace("snapshot = next", "snapshot = null"), encoding="utf-8")
    before = hashes(mirror)
    with pytest.raises(ValueError, match="publication"):
        instrument_mirror(mirror, "publication-costs")
    assert hashes(mirror) == before


def test_instrumented_gate_preserves_visibility_catchup_and_measures_publication(mirror):
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    instrument_mirror(mirror, "publication-costs")
    path = mirror / "src/qml/components/LayoutMetricsGate.qml"
    path.write_text(path.read_text(encoding="utf-8").replace("    id: gate\n", "    id: gate\n"
        "    function diagnosticBegin() { FanoutTrace.begin() }\n"
        "    function diagnosticFinish() { return FanoutTrace.finish() }\n"), encoding="utf-8")
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    assert component.isReady(), component.errorString()
    gate = component.create()
    assert gate is not None, component.errorString()
    engine.globalObject().setProperty("gate", engine.newQObject(gate))
    result = engine.evaluate("gate.diagnosticBegin(); gate.inputMetrics = {contentW: 1100, contentH: 760};"
        "gate.active = true; gate.active = false; gate.inputMetrics = {contentW: 1920, contentH: 1040};"
        "var held = gate.snapshot.contentW; gate.active = true;"
        "var current = gate.snapshot.contentW; var recorded = gate.diagnosticFinish();"
        "[held, current, gate.revision];")
    assert not result.isError(), result.toString()
    assert result.toVariant() == [1100, 1920, 2]
    rows = engine.globalObject().property("recorded").toVariant()
    assert rows["begin:Gate.snapshotPublication/:visible"]["count"] == 2
    assert rows["begin:Gate.publish/:hidden"]["count"] == 3
    assert rows["begin:Gate.publish/:visible"]["count"] == 2
    assert all(row["exclusiveMs"] <= row["helperMs"] for row in rows.values())
    gate.deleteLater()
    application.processEvents()


def test_tree_observer_sees_actual_hidden_font_and_implicit_notifications():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--watch-probe"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No-window observer checks passed" in result.stdout


def test_hidden_font_isolation_refuses_to_wrap_the_retained_runtime_repair(mirror):
    before = hashes(mirror)
    with pytest.raises(ValueError, match="requires source without the retained font metrics repair"):
        instrument_mirror(mirror, "hidden-font-scalars")
    assert hashes(mirror) == before


def test_hidden_font_scalar_isolation_preserves_full_multiline_and_inline_expressions():
    source = '''Text { font.pixelSize: root.ratioPx(0.1, 9); font.weight: Font.Bold }
Text {
    font.pixelSize: root.isProMode
        ? 12
        : root.ratioPx(
            0.1,
            root.metricFloor("body", 9))
    font.weight: Font.Bold
}
Text { font.pixelSize: 15 }
'''
    wrapped, count = _hold_metric_fonts(source)
    assert count == 2
    assert '), root.layoutRepairEnabled); font.weight: Font.Bold }' in wrapped
    assert 'root.metricFloor("body", 9))), root.layoutRepairEnabled)' in wrapped
    assert 'Text { font.pixelSize: 15 }' in wrapped


def test_actual_hidden_font_scalar_retains_layout_and_catches_up_synchronously():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--scalar-probe"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No-window scalar catchup checks passed" in result.stdout


def test_helpers_skip_quoted_and_commented_braces_and_preserve_following_source():
    source = '''function ratioPx(ratio) {
        var punctuation = "}";
        // a closing brace } in a comment
        /* an opening brace { in a comment */
        if (ratio) { return ratio; }
        return 1;
    }
    property int following: 2
    '''
    wrapped = _wrap_helpers(source, "Example", ("ratioPx",))
    assert wrapped.count("finally { FanoutTrace.leave(probeToken); }") == 1
    assert wrapped.endswith("    property int following: 2\n    ")
    assert 'var punctuation = "}";' in wrapped
    with pytest.raises(ValueError, match="Unterminated"):
        _wrap_helpers("function ratioPx() { return 1;", "Example", ("ratioPx",))


def test_actual_trace_counts_throwing_helper_once_and_preserves_value_identity():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine

    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QJSEngine()
    trace_body = "\n".join(TRACE_JS.splitlines()[1:])
    trace_exports = "return {begin:begin,enter:enter,leave:leave,value:value,finish:finish};"
    wrapped = _wrap_helpers("function ratioPx() { throw new Error('expected'); }", "Example", ("ratioPx",))
    result = engine.evaluate("var FanoutTrace = (function() {" + trace_body + trace_exports
        + "})(); var visible = true;" + wrapped)
    assert not result.isError(), result.toString()
    result = engine.evaluate("FanoutTrace.begin(); var original = {width: 1};"
        "var identityPreserved = FanoutTrace.value('Publication', original, false) === original;"
        "try { ratioPx(); } catch (expected) {}"
        "var observed = FanoutTrace.finish(); identityPreserved;")
    assert result.toBool()
    observed = engine.globalObject().property("observed").toVariant()
    assert observed["begin:Example.ratioPx:visible"]["count"] == 1
    assert observed["begin:Publication:hidden"]["count"] == 1
    application.processEvents()


@pytest.mark.parametrize("instrument", [instrument_mirror, instrument_qt_blur])
def test_both_entry_points_refuse_application_directory(instrument):
    with pytest.raises(ValueError, match="logs/<audit>/tree"):
        if instrument is instrument_mirror:
            instrument(ROOT, "counts")
        else:
            instrument(ROOT)


def test_qt_copy_is_isolated_and_all_patched_qmldirs_are_reported(mirror, tmp_path, monkeypatch):
    from PySide6.QtCore import QLibraryInfo

    imports = tmp_path / "installed-imports"
    original = imports / "Qt5Compat/GraphicalEffects"
    original.mkdir(parents=True)
    (original / "qmldir").write_text("module Qt5Compat.GraphicalEffects\nprefer :/qt-project.org/imports/Qt5Compat/GraphicalEffects/\n", encoding="utf-8")
    (original / "private").mkdir()
    (original / "private/qmldir").write_text("module Qt5Compat.GraphicalEffects.private\nprefer :/embedded/private/\n", encoding="utf-8")
    (original / "GaussianBlur.qml").write_text('''import QtQuick
Item {
    id: root
    function _rebuildShaders() { var params = { radius: 1 }; return params; }
}
''', encoding="utf-8")
    before = hashes(imports)
    monkeypatch.setattr(QLibraryInfo, "path", lambda unused: str(imports))
    instrument_mirror(mirror, "counts")
    changed = instrument_qt_blur(mirror)
    assert set(changed) == {
        "imports/Qt5Compat/GraphicalEffects/qmldir",
        "imports/Qt5Compat/GraphicalEffects/private/qmldir",
        "imports/Qt5Compat/GraphicalEffects/GaussianBlur.qml",
    }
    assert 'FanoutTrace.owner(root.source)' in changed["imports/Qt5Compat/GraphicalEffects/GaussianBlur.qml"]
    assert hashes(imports) == before
    for relative, patched in changed.items():
        assert (mirror / relative).read_text(encoding="utf-8") == patched
    with pytest.raises(ValueError, match="fresh imports destination"):
        instrument_qt_blur(mirror)


def test_qt_copy_requires_matching_trace_before_writing(mirror):
    (mirror / "src/qml/FanoutTrace.js").write_text(TRACE_JS + "// different instrumentation\n", encoding="utf-8")
    with pytest.raises(ValueError, match="matching mirror trace"):
        instrument_qt_blur(mirror)
    assert not (mirror / "imports").exists()


def run_watch_probe():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    application = QGuiApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
Item {
    property int requestedFont: 12
    property bool pageVisible: false
    Item {
        visible: parent.pageVisible
        Text { text: "Synthetic label"; font.pixelSize: parent.parent.requestedFont }
    }
}''', QUrl("file:///no_window_observer.qml"))
    assert component.isReady(), component.errorString()
    item = component.create()
    assert item is not None, component.errorString()
    engine.globalObject().setProperty("item", engine.newQObject(item))
    trace_body = "\n".join(TRACE_JS.splitlines()[1:])
    result = engine.evaluate("var trace = (function() {" + trace_body
        + "return {begin:begin, watchTree:watchTree, finish:finish};})();"
        "trace.begin(); trace.watchTree(item); trace.watchTree(item);"
        "item.requestedFont = 21; var rows = trace.finish();")
    assert not result.isError(), result.toString()
    rows = engine.globalObject().property("rows").toVariant()
    font_rows = [row for key, row in rows.items() if ":Item.font/" in key and key.endswith(":hidden")]
    assert len(font_rows) == 1, rows
    assert font_rows[0]["count"] == 1  # Duplicate watch does not connect twice.
    assert font_rows[0]["minimumValue"] == font_rows[0]["maximumValue"] == 21
    assert any(":Item.implicitHeight/" in key and key.endswith(":hidden") for key in rows), rows
    item.deleteLater()
    application.processEvents()
    print("No-window observer checks passed")


if __name__ == "__main__" and sys.argv[1:] == ["--watch-probe"]:
    run_watch_probe()


def run_scalar_probe():
    from tempfile import TemporaryDirectory
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    application = QGuiApplication([])
    engine = QQmlEngine()
    with TemporaryDirectory() as temporary:
        path = Path(temporary)
        (path / "HiddenScalars.js").write_text(HIDDEN_SCALAR_JS, encoding="utf-8")
        component = QQmlComponent(engine)
        component.setData(b'''import QtQuick
import "HiddenScalars.js" as HiddenScalars
Item {
    id: fixture
    property int requestedFont: 12
    property bool pageVisible: true
    property bool repair: true
    property real pageOpacity: 1
    property alias actualFont: label.font.pixelSize
    property alias preservedText: label.text
    Item {
        visible: fixture.pageVisible
        opacity: fixture.pageOpacity
        Text {
            id: label
            text: "Preserved draft"
            font.pixelSize: HiddenScalars.scalar(this, "font.pixelSize", fixture.requestedFont, fixture.repair)
        }
    }
}''', QUrl.fromLocalFile(str(path / "no_window_scalar.qml")))
        assert component.isReady(), component.errorString()
        item = component.create()
        assert item is not None, component.errorString()
        assert item.property("actualFont") == 12
        item.setProperty("pageVisible", False)
        item.setProperty("requestedFont", 21)
        assert item.property("actualFont") == 12
        item.setProperty("pageVisible", True)
        assert item.property("actualFont") == 21  # No event processing before catchup.
        item.setProperty("requestedFont", 24)
        assert item.property("actualFont") == 24
        item.setProperty("pageOpacity", 0)
        item.setProperty("requestedFont", 27)
        assert item.property("actualFont") == 27  # Target layout remains live at opacity zero.
        item.setProperty("pageVisible", False)
        item.setProperty("repair", False)
        item.setProperty("requestedFont", 30)
        assert item.property("actualFont") == 30
        assert item.property("preservedText") == "Preserved draft"
        item.deleteLater()
        application.processEvents()
    print("No-window scalar catchup checks passed")


if __name__ == "__main__" and sys.argv[1:] == ["--scalar-probe"]:
    run_scalar_probe()
