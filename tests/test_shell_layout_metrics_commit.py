"""Exercise the actual shell metrics binding in QtQml, without a window.

The production functions and property handlers are extracted at test time. Only
screen/host integration is stubbed: these checks certify QML publication, not
native geometry atomicity, physical pixels, rendering, or transition timing.
"""
from pathlib import Path
import re

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "src/qml/DetachedShellWindow.qml"
HEADER = ROOT / "src/qml/components/ProfessionalTopHeader.qml"


def block(source, pattern):
    match = re.search(pattern, source)
    assert match, pattern
    depth = 1
    end = match.end()
    while depth:
        assert end < len(source), pattern
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


def declaration(source, name):
    match = re.search(
        r"^\s*(?:readonly )?property \w+ " + re.escape(name) + r":.*$",
        source, re.MULTILINE,
    )
    assert match, name
    return match.group().strip()


def qml_harness():
    source = SHELL.read_text(encoding="utf-8")
    header_source = HEADER.read_text(encoding="utf-8")
    geometry = "\n".join(declaration(source, name)
                         for name in ("finalX", "finalY", "finalW", "finalH"))
    handlers = "\n".join(block(source, r"on" + name + r"Changed:\s*\{")
                         for name in ("FinalW", "FinalH"))
    metrics_binding = re.search(
        r"property bool layoutMetricsCommitInProgress:.*?(?=\n\s*function computeUiMetrics)",
        source, re.DOTALL,
    )
    assert metrics_binding
    functions = "\n".join(block(source, r"function " + name + r"\([^)]*\)\s*\{")
                          for name in ("computeUiMetrics", "ratioToPixels", "metricFloorPx",
                                       "commitProfessionalWindowTransitionTarget"))
    header_metrics = "\n".join(declaration(header_source, name)
                               for name in ("compactHeightPx", "logoSidePx", "titlePixelSize",
                                            "controlButtonSizePx", "controlGlyphSizePx"))
    return """import QtQml
QtObject {
    id: mainWin
    property bool layoutRepairEnabled: true
    property bool geometryTransitionSuppressed: false
    property bool uiMaximized: false
    property var maximizedOwnerScreen: ({name: "original"})
    property bool userResizeInProgress: false
    property bool userMoveInProgress: false
    property real resizeStartFinalW: 1100
    property real resizeStartFinalH: 760
    property int width: 1100
    property int height: 760
    property int usableW: 1920
    property int usableH: 1040
    property int monitorScalePercent: 100
    property var targetScreen: null
    property var integrationObservations: []
    property string failIntegrationStage: ""
    function observeIntegration(name) {
        integrationObservations.push({stage: name, actualW: finalW, actualH: finalH,
            publishedW: uiMetrics.contentW, publishedH: uiMetrics.contentH,
            scalePercent: uiMetrics.scalePercent});
        if (name === failIntegrationStage) throw new Error("integration failed: " + name);
    }
    function adoptTargetScreen(screen, immediate) {
        targetScreen = screen;
        usableW = screen.width;
        usableH = screen.height;
        monitorScalePercent = screen.scalePercent;
        observeIntegration("screen");
    }
    function updateTargetScreenFromFinalCenter() { observeIntegration("center"); }
    function refreshActiveVisibleRect() { observeIntegration("visibleRect"); }
    function applyHostEnvelopeForTarget() {
        width = finalW;
        height = finalH;
        observeIntegration("host");
    }
    function updateCanvasGeometry() { observeIntegration("canvas"); }
    property QtObject header: QtObject {
        id: topHeaderRoot
        property int width: mainWin.finalW
        property int height: compactHeightPx
""" + header_metrics + """
    }
""" + geometry + "\n" + handlers + "\n" + metrics_binding.group() + "\n" + "\n".join(
        declaration(source, name) for name in ("frozenContentW", "frozenContentH")
    ) + "\n" + functions + "\n}"


@pytest.fixture
def shell():
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml_harness().encode("utf-8"), QUrl("file:///shell_metrics_test.qml"))
    assert component.isReady(), component.errorString()
    item = component.createWithInitialProperties({"finalW": 1100, "finalH": 760})
    assert item is not None, component.errorString()
    engine.globalObject().setProperty("shell", engine.newQObject(item))
    yield engine, item
    item.deleteLater()
    application.processEvents()


def evaluate(engine, code):
    result = engine.evaluate(code)
    assert not result.isError(), result.toString()
    return result.toVariant()


def metrics(item):
    value = item.property("uiMetrics")
    return value.toVariant() if hasattr(value, "toVariant") else value


def header_metrics(engine):
    return evaluate(engine, "[shell.header.compactHeightPx, shell.header.logoSidePx, "
                    "shell.header.titlePixelSize, shell.header.controlButtonSizePx, "
                    "shell.header.controlGlyphSizePx]")


@pytest.mark.parametrize("kind,x,y,width,height,scale", [
    ("maximize", 0, 0, 1920, 1040, 100),
    ("maximize", -1920, -1080, 1920, 1040, 125),
    ("maximize", -3840, 0, 1600, 1000, 225),
    ("restore", -1020, -620, 480, 320, 100),
    ("restore", 309, 129, 1122, 782, 125),
    ("restore", -1200, 24, 880, 680, 225),
])
def test_commit_publishes_one_complete_target_and_preserves_header(
        shell, kind, x, y, width, height, scale):
    engine, item = shell
    initial = metrics(item)
    seen = []
    item.uiMetricsChanged.connect(lambda: seen.append(metrics(item)))
    before_header = header_metrics(engine)
    evaluate(engine, f"shell.commitProfessionalWindowTransitionTarget('{kind}', "
                    f"{{x:{x},y:{y},w:{width},h:{height}}}, "
                    f"{{width:1920,height:1040,scalePercent:{scale}}})")
    assert len(seen) == 1, seen
    assert (seen[0]["contentW"], seen[0]["contentH"], seen[0]["scalePercent"]) == (
        width, height, scale)
    assert metrics(item) == seen[0]
    assert (item.property("finalX"), item.property("finalY")) == (x, y)
    assert item.property("uiMaximized") is (kind == "maximize")
    assert item.property("layoutMetricsCommitInProgress") is False
    assert item.property("geometryTransitionSuppressed") is True
    observations = evaluate(engine, "shell.integrationObservations")
    assert [entry["stage"] for entry in observations] == ["screen", "visibleRect", "host", "canvas"]
    assert all((entry["actualW"], entry["actualH"]) == (width, height)
               for entry in observations)
    assert all((entry["publishedW"], entry["publishedH"], entry["scalePercent"]) == (
        initial["contentW"], initial["contentH"], initial["scalePercent"])
        for entry in observations)
    assert header_metrics(engine) == before_header == [72, 56, 18, 32, 12]


def test_ordinary_resize_invalidates_committed_snapshot_and_remains_reactive(shell):
    engine, item = shell
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:0,y:0,w:1920,h:1040}, null)")
    assert evaluate(engine, "shell.layoutMetricsSnapshot !== null")
    item.setProperty("finalW", 960)
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (960, 1040)
    item.setProperty("finalH", 640)
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (960, 640)
    item.setProperty("finalW", 800)
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (800, 640)


@pytest.mark.parametrize("property_name,value,metric_name,expected", [
    ("monitorScalePercent", 225, "scalePercent", 225),
    ("usableW", 1600, "monitorW", 1600),
    ("usableH", 900, "monitorH", 900),
])
def test_same_size_monitor_or_dpi_change_invalidates_the_snapshot(
        shell, property_name, value, metric_name, expected):
    engine, item = shell
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:-1920,y:0,w:1920,h:1040}, null)")
    assert evaluate(engine, "shell.layoutMetricsSnapshot !== null")
    item.setProperty(property_name, value)
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    assert metrics(item)[metric_name] == expected
    assert (item.property("finalW"), item.property("finalH")) == (1920, 1040)
    if property_name == "monitorScalePercent":
        assert metrics(item)["fontFloorTitlePx"] == 27


@pytest.mark.parametrize("dimension,value,metric_name", [
    ("width", 1440, "monitorW"), ("height", 900, "monitorH"),
])
def test_monitor_fallback_geometry_remains_live_after_a_commit(shell, dimension, value, metric_name):
    engine, item = shell
    item.setProperty("usableW", 0)
    item.setProperty("usableH", 0)
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    "{x:-900,y:-120,w:1100,h:760}, null)")
    assert evaluate(engine, "shell.layoutMetricsSnapshot !== null")
    item.setProperty(dimension, value)
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    assert metrics(item)[metric_name] == value
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (1100, 760)


def test_screen_descriptor_fallback_invalidates_after_same_size_move(shell):
    engine, item = shell
    item.setProperty("usableW", 0)
    item.setProperty("usableH", 0)
    item.setProperty("targetScreen", {"width": 1920, "height": 1080})
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    "{x:-900,y:-120,w:1100,h:760}, null)")
    assert metrics(item)["monitorW"] == 1920
    item.setProperty("targetScreen", {"width": 1600, "height": 1000})
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    assert (metrics(item)["monitorW"], metrics(item)["monitorH"]) == (1600, 1000)
    assert (item.property("finalW"), item.property("finalH")) == (1100, 760)


@pytest.mark.parametrize("interaction", ["userResizeInProgress", "userMoveInProgress"])
def test_interactive_geometry_retains_frozen_content_then_adopts_final_layout(shell, interaction):
    engine, item = shell
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:0,y:0,w:1920,h:1040}, null)")
    item.setProperty("resizeStartFinalW", 1920)
    item.setProperty("resizeStartFinalH", 1040)
    item.setProperty(interaction, True)
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    item.setProperty("finalW", 1000)
    item.setProperty("finalH", 700)
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (1920, 1040)
    item.setProperty(interaction, False)
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (1000, 700)
    assert (item.property("frozenContentW"), item.property("frozenContentH")) == (1000, 700)


def test_geometry_signals_remain_separate_while_metrics_are_batched(shell):
    engine, item = shell
    dimensions = []
    item.finalWChanged.connect(lambda: dimensions.append((item.property("finalW"), item.property("finalH"))))
    item.finalHChanged.connect(lambda: dimensions.append((item.property("finalW"), item.property("finalH"))))
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:0,y:0,w:1920,h:1040}, null)")
    assert dimensions == [(1920, 760), (1920, 1040)]
    assert metrics(item)["contentH"] == 1040


def test_fractional_negative_target_rect_publishes_the_rounded_geometry(shell):
    engine, item = shell
    seen = []
    item.uiMetricsChanged.connect(lambda: seen.append(metrics(item)))
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    "{x:-101.5,y:-99.51,w:1100.6,h:759.5}, null)")
    assert (item.property("finalX"), item.property("finalY"),
            item.property("finalW"), item.property("finalH")) == (-101, -100, 1101, 760)
    assert [(entry["contentW"], entry["contentH"]) for entry in seen] == [(1101, 760)]


def test_default_path_keeps_original_geometry_publication_behavior(shell):
    engine, item = shell
    item.setProperty("layoutRepairEnabled", False)
    seen = []
    item.uiMetricsChanged.connect(lambda: seen.append(metrics(item)))
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:0,y:0,w:1920,h:1040}, null)")
    assert [(entry["contentW"], entry["contentH"]) for entry in seen] == [(1920, 760), (1920, 1040)]
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")


@pytest.mark.parametrize("scale,expected", [
    (100, (14, 12, 11, 10)),
    (125, (15, 15, 11, 10)),
    (225, (27, 27, 18, 16)),
])
def test_target_font_floors_use_completed_geometry_and_target_dpi(shell, scale, expected):
    engine, item = shell
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('maximize', "
                    "{x:-1920,y:-1080,w:1920,h:1040}, "
                    f"{{width:1920,height:1040,scalePercent:{scale}}})")
    current = metrics(item)
    assert tuple(current[key] for key in ("fontFloorTitlePx", "fontFloorIconPx",
                                         "fontFloorBodyPx", "fontFloorLabelPx")) == expected


def test_repeated_maximize_restore_commits_release_the_hold_each_time(shell):
    engine, item = shell
    seen = []
    item.uiMetricsChanged.connect(lambda: seen.append(metrics(item)))
    evaluate(engine, """
        for (var i = 0; i < 3; i++) {
            shell.commitProfessionalWindowTransitionTarget('maximize',
                {x:-1920,y:0,w:1920,h:1040}, null);
            shell.commitProfessionalWindowTransitionTarget('restore',
                {x:-1250,y:129,w:1100,h:760}, null);
        }
    """)
    assert [(entry["contentW"], entry["contentH"]) for entry in seen] == [(1920, 1040), (1100, 760)] * 3
    assert item.property("layoutMetricsCommitInProgress") is False
    assert item.property("maximizedOwnerScreen") is None


@pytest.mark.parametrize("repair_enabled", [False, True])
@pytest.mark.parametrize("stage", ["screen", "center", "visibleRect", "host", "canvas"])
def test_integration_failure_rethrows_and_releases_metrics_hold(shell, repair_enabled, stage):
    engine, item = shell
    item.setProperty("layoutRepairEnabled", repair_enabled)
    item.setProperty("failIntegrationStage", stage)
    screen = "null" if stage == "center" else "{width:1920,height:1040,scalePercent:225}"
    result = engine.evaluate("shell.commitProfessionalWindowTransitionTarget('maximize', "
                             "{x:-1920,y:-1080,w:1920,h:1040}, " + screen + ")")
    assert result.isError()
    assert result.toString() == "Error: integration failed: " + stage
    assert item.property("layoutMetricsCommitInProgress") is False
    assert evaluate(engine, "shell.layoutMetricsSnapshot === null")
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (1920, 1040)
    if stage != "center":
        assert metrics(item)["scalePercent"] == 225
    item.setProperty("finalW", 900)
    item.setProperty("finalH", 600)
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (900, 600)
    item.setProperty("failIntegrationStage", "")
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    "{x:-1000,y:129,w:1100,h:760}, null)")
    assert (metrics(item)["contentW"], metrics(item)["contentH"]) == (1100, 760)
    assert item.property("layoutMetricsCommitInProgress") is False
