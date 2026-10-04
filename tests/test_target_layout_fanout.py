"""Safe checks for disposable profiling edits; no GUI or WebEngine runtime."""
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/diagnostics"))
from target_layout_fanout import (TRACE_JS, VARIANTS, _wrap_helpers,
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


@pytest.mark.parametrize("variant", [variant for variant in VARIANTS if variant != "counts"])
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
