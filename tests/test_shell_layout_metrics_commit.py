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


def qml_harness(actual_geometry=False):
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
                                       "settledPaddingPx",
                                       "commitProfessionalWindowTransitionTarget"))
    header_metrics = "\n".join(declaration(header_source, name)
                               for name in ("compactHeightPx", "logoSidePx", "titlePixelSize",
                                            "controlButtonSizePx", "controlGlyphSizePx"))
    harness = """import QtQml
QtObject {
    id: mainWin
    property bool layoutRepairEnabled: true
    property bool geometryTransitionSuppressed: false
    property bool uiMaximized: false
    property string animationPhase: "settled"
    property bool isClosing: false
    property bool isMinimizing: false
    property bool isRestoringFromMinimize: false
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
    property int glowPadding: 17
    property bool useExactSettledCanvasPadding: true
    property bool lowPerformanceMode: false
    property var layoutRatios: ({settledCanvasAreaScale: 1.05,
        settledPaddingPct: 0.011, settledPaddingLowPerfPct: 0.008})
    property var targetScreen: null
    property var integrationObservations: []
    property string failIntegrationStage: ""
    function observeIntegration(name) {
        integrationObservations.push({stage: name, actualW: finalW, actualH: finalH,
            publishedW: uiMetrics.contentW, publishedH: uiMetrics.contentH,
            scalePercent: uiMetrics.scalePercent, padding: glowPadding});
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
        width = finalW + 2 * glowPadding;
        height = finalH + 2 * glowPadding;
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
    # Include the real padding notification even for the integration spies.
    # It must not revise the canvas ahead of the host inside the commit hold.
    padding_handler = block(source, r"onGlowPaddingChanged:\s*\{")
    harness = harness.replace("    property int glowPadding: 17", "    property int glowPadding: 17\n" + padding_handler)
    if actual_geometry:
        for name in ("applyHostEnvelopeForTarget", "updateCanvasGeometry"):
            stub = block(harness, r"function " + name + r"\([^)]*\)\s*\{")
            actual = block(source, r"function " + name + r"\([^)]*\)\s*\{")
            harness = harness.replace(stub, actual)
        harness = harness.replace("    property var targetScreen: null", """    property var targetScreen: ({virtualX: 0, virtualY: 0, width: 1920, height: 1080})
    property bool professionalNativeWindowState: false
    property bool detachedMode: false
    property string startupPhase: "settled"
    property bool maximizeAnimInProgress: false
    property string dragStrategy: "fallback"
    property int usableX: 0
    property int usableY: 0
    property var activeVisibleRect: ({x: 0, y: 0, w: 1920, h: 1040})
    property int hostX: 0
    property int hostY: 0
    property int hostW: 1
    property int hostH: 1
    property int canvasX: 0
    property int canvasY: 0
    property int canvasW: 1
    property int canvasH: 1
    property int contentLocalX: 0
    property int contentLocalY: 0
    property int canvasLocalX: 0
    property int canvasLocalY: 0
""")
        harness = harness.replace("        usableW = screen.width;", "        usableX = screen.virtualX;\n        usableY = screen.virtualY;\n        usableW = screen.width;")
        harness = harness[:-1] + block(source, r"function settledHostPaddingPx\([^)]*\)\s*\{") + "\n}"
    return harness


def create_shell(actual_geometry=False):
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml_harness(actual_geometry).encode("utf-8"), QUrl("file:///shell_metrics_test.qml"))
    assert component.isReady(), component.errorString()
    item = component.createWithInitialProperties({"finalW": 1100, "finalH": 760})
    assert item is not None, component.errorString()
    engine.globalObject().setProperty("shell", engine.newQObject(item))
    return application, engine, component, item


@pytest.fixture
def shell():
    application, engine, component, item = create_shell()
    yield engine, item
    item.deleteLater()
    application.processEvents()


@pytest.fixture
def geometry_shell():
    application, engine, component, item = create_shell(actual_geometry=True)
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


@pytest.mark.parametrize("initial_padding", [0, 7, 17, 80])
@pytest.mark.parametrize("width,height", [(1100, 760), (760, 540), (1500, 880), (480, 320)])
def test_target_host_uses_its_own_padding_independently_of_startup_geometry(
        shell, initial_padding, width, height):
    engine, item = shell
    item.setProperty("glowPadding", initial_padding)
    item.setProperty("uiMaximized", True)
    item.setProperty("integrationObservations", [])
    expected = evaluate(engine, f"shell.settledPaddingPx({width}, {height})")
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    f"{{x:-1250,y:129,w:{width},h:{height}}}, null)")
    assert item.property("glowPadding") == expected
    observations = evaluate(engine, "shell.integrationObservations")
    assert [entry["padding"] for entry in observations if entry["stage"] in ("host", "canvas")] == [expected, expected]
    assert (item.property("width"), item.property("height")) == (width + 2 * expected, height + 2 * expected)
    # Finishing the same target does not introduce a new perimeter revision.
    evaluate(engine, "shell.applyHostEnvelopeForTarget(); shell.updateCanvasGeometry()")
    assert (item.property("width"), item.property("height")) == (width + 2 * expected, height + 2 * expected)


def test_ordinary_transition_keeps_original_padding_policy(shell):
    engine, item = shell
    item.setProperty("layoutRepairEnabled", False)
    item.setProperty("glowPadding", 37)
    evaluate(engine, "shell.commitProfessionalWindowTransitionTarget('restore', "
                    "{x:-1250,y:129,w:1100,h:760}, null)")
    assert item.property("glowPadding") == 37


@pytest.mark.parametrize("kind,width,height,monitor_w,monitor_h,scale,desired,bounded", [
    ("restore", 1100, 760, 1920, 1040, 100, 11, 11),
    ("restore", 760, 540, 1920, 1040, 125, 8, 8),
    ("restore", 1500, 880, 1920, 1040, 100, 14, 14),
    ("restore", 480, 320, 1600, 900, 225, 5, 5),
    ("restore", 1000, 760, 1024, 768, 100, 11, 4),
    ("restore", 880, 460, 900, 474, 225, 7, 7),
    ("maximize", 1920, 1040, 1920, 1040, 100, 17, 0),
])
def test_actual_host_and_canvas_publish_matching_target_before_metrics(
        geometry_shell, kind, width, height, monitor_w, monitor_h, scale, desired, bounded):
    engine, item = geometry_shell
    item.setProperty("uiMaximized", True)
    item.setProperty("glowPadding", 80)
    seen = []

    def publication():
        seen.append({name: item.property(name) for name in (
            "glowPadding", "hostX", "hostY", "hostW", "hostH",
            "canvasX", "canvasY", "canvasW", "canvasH", "contentLocalX", "contentLocalY")})

    item.uiMetricsChanged.connect(publication)
    x, y = (-1920, -1080) if kind == "maximize" else (-1510, -895)
    evaluate(engine, f"shell.commitProfessionalWindowTransitionTarget('{kind}', "
                    f"{{x:{x},y:{y},w:{width},h:{height}}}, "
                    f"{{virtualX:-1920,virtualY:-1080,width:{monitor_w},height:{monitor_h},scalePercent:{scale}}})")
    expected = {
        "glowPadding": desired,
        "hostX": x - bounded, "hostY": y - bounded,
        "hostW": width + 2 * bounded, "hostH": height + 2 * bounded,
        "canvasX": x - bounded, "canvasY": y - bounded,
        "canvasW": width + 2 * bounded, "canvasH": height + 2 * bounded,
        "contentLocalX": bounded, "contentLocalY": bounded,
    }
    assert seen == [expected]
    assert (metrics(item)["contentW"], metrics(item)["contentH"], metrics(item)["scalePercent"]) == (
        width, height, scale)
    # Target capture and live reveal consume the same native perimeter;
    # repeating settled geometry cannot introduce a terminal correction.
    evaluate(engine, "shell.applyHostEnvelopeForTarget(); shell.updateCanvasGeometry()")
    assert {name: item.property(name) for name in expected} == expected
    assert item.property("canvasLocalX") == item.property("canvasLocalY") == 0


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
