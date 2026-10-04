"""Bounded GPU-only native composition capability test in the populated app.

Private workbooks/settings are copied to ignored isolated profiles. Public Qt
native context handles are passed opaquely to typed C++; no Python COM vtables,
Qt ABI emulation, or CPU framebuffer feeds presentation. Desktop pixel evidence
is collected separately and never supplies source/target content.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import cProfile
import faulthandler
from functools import wraps
from target_layout_fanout import VARIANTS, instrument_mirror, instrument_qt_blur
from native_presentation_observer import (configure_observer, native_observation,
    native_present_trace, DesktopFrameObserver, FreshPresentationGate)


WORKSPACES = {"productivity": (3, "D10"), "time-entry": (1, "B01"),
              "client-directory": (0, "A01"), "invoice-preview": (2, "C03"), "home": None}


def configure_fixture_source(source, first_direction, workspace, restored_size):
    """Change only disposable startup/settings and navigation; never prepare a target."""
    def replace_once(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError("Disposable startup/navigation anchor is unavailable or ambiguous")
        source = source.replace(old, new, 1)
    width, height = restored_size
    replace_once('mainWindowLayout={"maximized": False, "hasExactRect": True,',
                 'mainWindowLayout={"maximized": ' + str(first_direction == "restore") + ', "hasExactRect": True,')
    replace_once('"width": 1100, "height": 760,', f'"width": {width}, "height": {height},')
    old = 'self.evaluate("_probeWindow.mainContentRef.option3OpenWorkspaceForTile(3, \'D10\', {})")'
    route = WORKSPACES[workspace]
    navigation = (f'self.evaluate("_probeWindow.mainContentRef.option3OpenWorkspaceForTile({route[0]}, \'{route[1]}\', {{}})")'
                  if route else 'self.evaluate("true")')
    replace_once(old, navigation)
    if route is None:
        replace_once('if not self.expected_tab:', 'if False:  # Home has no work tab.')
    return source


def import_render_target(result, host, expected_client, set_target, native_error, clock=time.perf_counter):
    """Import this verified resized GPU frame without waiting for GUI notification.

    The SDK worker still enforces its unchanged clock deadline and keyed mutex.
    No Qt object access, GUI cleanup or readiness gate is performed here.
    """
    if result.get("client") != expected_client or result.get("size") != expected_client[2:]:
        raise RuntimeError("Target texture/client differs from predetermined physical endpoint")
    if not host or not result.get("frame"):
        raise RuntimeError("Target import requires an owned host and GPU frame")
    result["targetImportStarted"] = clock()
    result["targetImported"] = bool(set_target(host, result["frame"]))
    result["targetImportFinished"] = clock()
    if not result["targetImported"]:
        result["targetImportError"] = native_error(host)


def profile_shell_source(source):
    """Instrument only the disposable target-commit function, using a QML clock.

    Date.now() keeps statement observations out of Python and its GIL. The
    fixture calibrates this millisecond wall clock against perf_counter for
    each transaction; render/Qt signal callbacks have a separate GIL caveat.
    """
    start = source.index("    function commitProfessionalWindowTransitionTarget(")
    end = source.index("\n    function finishProfessionalWindowTransition(", start)
    function = source[start:end]
    statements = (
        ("suppression", "geometryTransitionSuppressed = true;"),
        ("finalX", "finalX = Math.round(targetRect.x);"),
        ("finalY", "finalY = Math.round(targetRect.y);"),
        ("finalW", "finalW = Math.max(1, Math.round(targetRect.w));"),
        ("finalH", "finalH = Math.max(1, Math.round(targetRect.h));"),
        ("uiMaximized", 'uiMaximized = kind === "maximize";'),
        ("adoptTargetScreen", "adoptTargetScreen(targetScreenOverride, true);"),
        ("updateTargetScreen", "updateTargetScreenFromFinalCenter();"),
        ("refreshVisibleRect", "refreshActiveVisibleRect();"),
        ("hostEnvelope", "applyHostEnvelopeForTarget();"),
        ("canvasGeometry", "updateCanvasGeometry();"),
        ("clearMaximizedOwner", "maximizedOwnerScreen = null;"),
    )
    if "layoutMetricsSnapshot = computeUiMetrics();" in function:
        statements += (
            ("metricsHold", "layoutMetricsSnapshot = uiMetrics;"),
            ("metricsPublication", "layoutMetricsSnapshot = computeUiMetrics();"),
        )
    if "glowPadding = settledPaddingPx(finalW, finalH);" in function:
        statements += (("settledPadding", "glowPadding = settledPaddingPx(finalW, finalH);"),)
    for name, statement in statements:
        if function.count(statement) != 1:
            raise RuntimeError("Target profiling statement is unavailable or ambiguous: " + name)
        function = function.replace(statement,
            'cleanRoomNativeProfileMark("before:' + name + '");\n        ' + statement
            + '\n        cleanRoomNativeProfileMark("after:' + name + '");')
    source = source[:start] + function + source[end:]
    declaration = "    id: mainWin\n"
    if source.count(declaration) != 1:
        raise RuntimeError("Disposable target profiling cannot identify the shell root")
    helpers = '''    property bool cleanRoomNativeProfileEnabled: false
    property var cleanRoomNativeProfileMarkers: []
    function cleanRoomNativeProfileMark(name) {
        if (!cleanRoomNativeProfileEnabled) return;
        cleanRoomNativeProfileMarkers.push({
            "boundary": name, "wallMs": Date.now(),
            "qtWidth": width, "qtHeight": height,
            "finalWidth": finalW, "finalHeight": finalH,
            "uiMaximized": uiMaximized
        });
    }
'''
    return source.replace(declaration, declaration + helpers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-label", required=True)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--gui-delay-ms", type=int, default=80)
    parser.add_argument("--duration-ms", type=int, default=350)
    parser.add_argument("--blend-start-ms", type=int, default=240)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--prepared-target", action="store_true",
        help="Capability isolation only: render target before motion; initial wait counts in complete timing")
    parser.add_argument("--endpoint-pixels", action="store_true",
        help="Compare desktop pixels in RAM; never supplies presentation pixels")
    parser.add_argument("--pixels", action="store_true")
    parser.add_argument("--bridge-dll", default="cspm_cleanroom_composition.dll",
        help="Built DLL filename within outputs/native_cleanroom")
    parser.add_argument("--endpoint-hold-ms", type=int, default=0,
        help="Diagnostic endpoint submission-to-desktop wait; included in full timing")
    parser.add_argument("--profile-boundaries", action="store_true",
        help="Disposable QML statement and one-shot Qt/render boundary observations; buffered logging")
    parser.add_argument("--fanout-variant", choices=VARIANTS,
        help="Targeted helper counters and a disposable layout isolation; requires --profile-boundaries")
    parser.add_argument("--fanout-quiet", action="store_true",
        help="Apply the disposable variant without helper counters or modified Qt module")
    parser.add_argument("--profile-python-commit", action="store_true",
        help="Save ignored cProfile of callbacks invoked synchronously by target commit")
    parser.add_argument("--layout-repair", action="store_true",
        help="Opt into the process-local shared-control repair; production remains default")
    parser.add_argument("--qt-render-timings", action="store_true",
        help="Enable Qt's own stage timers in the ignored runtime log")
    parser.add_argument("--qt-layout-polish", action="store_true",
        help="Pair Qt layout polish entry/exit boundaries after commit, with object metadata")
    parser.add_argument("--layout-only", action="store_true",
        help="Repeated geometry/render isolation; no native motion or transition qualification")
    parser.add_argument("--render-target-import", action="store_true",
        help="Import the verified target in its render callback; native deadline remains unchanged")
    parser.add_argument("--first-direction", choices=("maximize", "restore"), default="maximize",
        help="Cold restore starts maximized through disposable launch settings")
    parser.add_argument("--workspace", choices=WORKSPACES, default="productivity")
    parser.add_argument("--keep-visible", action="store_true",
        help="Keep the disposable source above other windows for physical pixel measurements")
    parser.add_argument("--physical-diagnostics", action="store_true",
        help="Record fresh desktop acquisitions, window state and deferred spatial pixel diagnostics")
    parser.add_argument("--source-observation-only", action="store_true",
        help="Source sampling isolation only; no native motion or target preparation")
    parser.add_argument("--source-unlocked", action="store_true",
        help="Source-only causal control without input-state changes; cannot qualify input restoration")
    parser.add_argument("--source-markers", action="store_true",
        help="Source-only marker-overlay control, independent of the external motion collector")
    parser.add_argument("--restored-size", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"), default=(1100, 760))
    args = parser.parse_args()
    if args.endpoint_pixels:
        args.physical_diagnostics = True
    if args.physical_diagnostics or args.source_observation_only:
        args.endpoint_pixels = True
        args.keep_visible = True
        if args.endpoint_hold_ms:
            parser.error("Fresh physical qualification cannot use a configured endpoint hold")
    if args.source_unlocked and not args.source_observation_only:
        parser.error("unlocked input is a source-only diagnostic control")
    if args.source_markers and not args.source_observation_only:
        parser.error("independent marker injection is a source-only diagnostic control")
    if args.fanout_variant and not args.profile_boundaries:
        parser.error("fanout variants require disposable boundary profiling")
    if args.fanout_quiet and not args.fanout_variant:
        parser.error("quiet fanout requires an explicit isolation variant")
    if args.layout_only and (args.prepared_target or args.capture_only or args.endpoint_hold_ms):
        parser.error("layout-only isolation cannot prepare targets, skip capture, or hold motion endpoints")
    if args.render_target_import and (args.prepared_target or args.capture_only or args.layout_only):
        parser.error("render target import is a cold native motion isolation")
    if not 700 <= args.restored_size[0] <= 1550 or not 540 <= args.restored_size[1] <= 900:
        parser.error("restored size must fit this bounded output-0 diagnostic fixture")
    if not args.audit_label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.audit_label):
        parser.error("audit label must use letters, numbers, underscore or hyphen")
    if not 1 <= args.cycles <= 12 or not 0 <= args.gui_delay_ms <= 1000 or not 100 <= args.duration_ms <= 1000 or not 0 < args.blend_start_ms < args.duration_ms:
        parser.error("bounded cycles/delay/duration/transfer deadline required")
    if not 0 <= args.endpoint_hold_ms <= 300:
        parser.error("diagnostic endpoint hold must be between 0 and 300 ms")
    root = Path(__file__).resolve().parents[2]
    audit = root / "logs" / args.audit_label
    audit.mkdir(parents=True, exist_ok=False)
    stack_log = (audit / "python_stacks.txt").open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(45, repeat=True, file=stack_log)
    provenance_paths = (
        "scripts/diagnostics/native_gpu_transition_spike.py",
        "scripts/diagnostics/target_layout_fanout.py",
        "scripts/diagnostics/window_transition_probe.py",
        "scripts/diagnostics/native_presentation_observer.py",
        "scripts/diagnostics/source_pixel_analysis.py",
        "scripts/build_cleanroom_native.ps1",
        "src/native/cleanroom_composition/cleanroom_composition.cpp",
        "src/python/main.py",
        "src/python/backend/transition_experiment.py",
        "src/qml/DetachedShellWindow.qml",
        "src/qml/components/LayoutMetricsGate.qml",
        "src/qml/components/ModernTextField.qml",
        "src/qml/components/ModernComboBox.qml",
        "src/qml/components/PillButton.qml",
        "src/qml/views/HomeGrid.qml",
    )
    source_provenance = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in provenance_paths}
    mirror = None
    mirror_provenance = {}
    if args.profile_boundaries:
        mirror = audit / "tree"
        for name in ("src/qml", "src/assets", "assets"):
            shutil.copytree(root / name, mirror / name)
        shell_path = mirror / "src/qml/DetachedShellWindow.qml"
        shell_path.write_text(profile_shell_source(shell_path.read_text(encoding="utf-8")),
            encoding="utf-8")
        if args.fanout_variant:
            for name, changed_source in instrument_mirror(mirror, args.fanout_variant,
                    collect_counts=not args.fanout_quiet).items():
                mirror_provenance[name] = hashlib.sha256(changed_source.encode("utf-8")).hexdigest()
            if not args.fanout_quiet:
                for name, changed_source in instrument_qt_blur(mirror).items():
                    mirror_provenance[name] = hashlib.sha256(changed_source.encode("utf-8")).hexdigest()
        mirror_provenance["src/qml/DetachedShellWindow.qml"] = hashlib.sha256(shell_path.read_bytes()).hexdigest()
    bridge_directory = (root / "outputs/native_cleanroom").resolve()
    dll_path = (bridge_directory / args.bridge_dll).resolve()
    if dll_path.parent != bridge_directory or dll_path.suffix.lower() != ".dll":
        parser.error("bridge DLL must be a filename within outputs/native_cleanroom")
    dll = ctypes.CDLL(str(dll_path))
    dll_hash = hashlib.sha256(dll_path.read_bytes()).hexdigest()
    void, uint, flt = ctypes.c_void_p, ctypes.c_uint, ctypes.c_float
    signatures = {
        "cspm_comp_abi_version": ([], uint),
        "cspm_gpu_capture": ([void, ctypes.POINTER(uint), ctypes.POINTER(uint)], void),
        "cspm_gpu_release": ([void], None),
        "cspm_comp_create_from_frame": ([void, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], void),
        "cspm_comp_set_source_frame": ([void, void, flt, flt, flt, flt, flt, flt], ctypes.c_int),
        "cspm_comp_start": ([void, flt, flt, flt, flt, uint, uint], ctypes.c_int),
        "cspm_comp_set_target_frame": ([void, void], ctypes.c_int),
        "cspm_comp_status": ([void], uint),
        "cspm_comp_elapsed_ms": ([void], ctypes.c_double),
        "cspm_comp_finish": ([void], ctypes.c_int),
        "cspm_comp_destroy": ([void], None),
        "cspm_comp_error": ([void, ctypes.c_char_p, uint], uint),
    }
    for name, (inputs, output) in signatures.items():
        function = getattr(dll, name)
        function.argtypes, function.restype = inputs, output
    if dll.cspm_comp_abi_version() != 1:
        raise RuntimeError("Native bridge ABI does not match the bounded spike")
    configure_observer(dll)
    if hasattr(dll, "cspm_comp_presentation"):
        dll.cspm_comp_presentation.argtypes = [void, ctypes.POINTER(uint), ctypes.POINTER(uint), ctypes.POINTER(uint)]
        dll.cspm_comp_presentation.restype = ctypes.c_int
    def native_error(host=None):
        buffer = ctypes.create_string_buffer(1024)
        dll.cspm_comp_error(host, buffer, len(buffer))
        return buffer.value.decode("utf-8", errors="replace")
    original = Path(os.environ["LOCALAPPDATA"]) / "CSPM"
    protected = [original / "user_settings.json", *(original / "data" / name for name in ("CSPM.xlsm", "Dockets.xlsm"))]
    hashes = lambda: {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    before = hashes()
    (audit / "protected_hashes_start.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    os.environ["CSPM_MACHINE_ID_FILE"] = str(audit / "disposable_profile/machine_id.json")
    os.environ["CSPM_EXPERIMENTAL_TRANSITION"] = "production"
    os.environ["CSPM_EXPERIMENTAL_LAYOUT_REPAIR"] = "1" if args.layout_repair else "0"
    if args.qt_render_timings:
        os.environ["QSG_RENDER_TIMING"] = "1"
    probe = root / "scripts/diagnostics/window_transition_probe.py"
    source = probe.read_text(encoding="utf-8")
    source = source[:source.index("\nentry._capture_startup_launch_context = diagnostic_launch_context")]
    source = source.replace('AUDIT = ROOT / "logs/window_transition_diagnostic"', "AUDIT = Path(" + repr(str(audit)) + ")")
    source = configure_fixture_source(source, args.first_direction, args.workspace, args.restored_size)
    # Disable Python per-frame instrumentation inherited from historical fixture.
    for names in ("('beforeFrameBegin','beforeSynchronizing','afterSynchronizing','beforeRendering','afterRendering','afterFrameEnd','frameSwapped')", "('xChanged','yChanged','widthChanged','heightChanged','finalXChanged','finalYChanged','finalWChanged','finalHChanged')"):
        source = source.replace("for name in " + names + ":", "for name in ():")
    if not args.pixels:
        source = source.replace("from pixel_tracker_process import PixelTracker, SENSORS", '''from pixel_tracker_process import SENSORS
class PixelTracker:
    def __init__(self, *_): pass
    def start(self): pass
    def stop(self): pass
    def command(self, name): pass
''')
    if not args.pixels and not args.source_markers:
        # A source/full-frame comparison needs the actual application pixels
        # unless synthetic markers are explicitly part of the observer.
        source = source.replace("for (name, rgb), (px,py) in zip(SENSORS, positions):",
            "for (name, rgb), (px,py) in ():")
    else:
        marker_statement = "self.evaluate('Qt.createQmlObject('+json.dumps(code)+',_probeWindow.contentLayerRef,'+json.dumps('ReviewPixel_'+name)+'); true')"
        if source.count(marker_statement) != 1:
            raise RuntimeError("Disposable movement-marker creation anchor is unavailable or ambiguous")
        source = source.replace(marker_statement, "self.create_probe_marker(code, name)")
    sys.path.insert(0, str(probe.parent))
    context = {"__file__": str(probe), "__name__": "native_gpu_fixture"}
    exec(compile(source, str(probe), "exec"), context)
    entry, base = context["entry"], context["ProbeApplication"]
    from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal, QLoggingCategory
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QSGRendererInterface, QQuickItem
    from shiboken6 import isValid, getCppPointer

    if mirror is not None:
        class ProfileEngine(QQmlApplicationEngine):
            def __init__(self, *values):
                super().__init__(*values)
                if args.fanout_variant and not args.fanout_quiet:
                    self.addImportPath(str(mirror / "imports"))
            def load(self, url):
                local = url.toLocalFile() if isinstance(url, QUrl) else str(url)
                if Path(local).name == "Main.qml":
                    url = QUrl.fromLocalFile(str(mirror / "src/qml/Main.qml"))
                return super().load(url)
        entry.QQmlApplicationEngine = ProfileEngine

    class Captured(QObject):
        ready = Signal(object)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user.IsWindowEnabled.argtypes = [wintypes.HWND]
    user.IsWindowEnabled.restype = wintypes.BOOL
    user.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
    def client(window):
        rect, origin = wintypes.RECT(), wintypes.POINT()
        hwnd = int(window.winId())
        if not user.GetClientRect(hwnd, ctypes.byref(rect)) or not user.ClientToScreen(hwnd, ctypes.byref(origin)):
            raise RuntimeError("Native client geometry unavailable")
        return [origin.x, origin.y, rect.right, rect.bottom]

    def guarded(method):
        """A Qt callback exception must become a bounded failed trial."""
        @wraps(method)
        def invoke(self, *values):
            if self.finished and method.__name__ != "captured":
                return
            try:
                return method(self, *values)
            except Exception as exc:
                self.fail("fixture integration", method.__name__ + ": " + str(exc))
        return invoke

    class NativeSpike(base):
        def __init__(self, argv):
            self.rows, self.frames = [], []
            self.host = None
            self.capture_request = None
            self.capture_connected = False
            self.live_handoff_connected = False
            self.capture_in_progress = False
            self.completion_pending = False
            self.webengine_probe = None
            self.capture_signal = None
            self.started_native = None
            self.current = None
            self.finished = False
            self.completed = 0
            self.desktop_camera = None
            self.source_desktop = None
            self.target_desktop = None
            self.pixel_pairs = []
            self.pixel_regions = {}
            self.target_pixel_regions = {}
            self.sensor_components = []
            self.sensor_items = []
            self.snapshot_observations = {}
            self.input_was_enabled = None
            self.desktop_observer = DesktopFrameObserver()
            self.observation_pending = None
            self.witness_rect = None
            self.witness_revision = 0
            self.boundary_rows = []
            self.fanout_rows = []
            self.qt_timing_rows = []
            self.qt_layout_rows = []
            self.qt_layout_objects = {}
            self.qt_target_capture_pending = False
            self.profile_armed = False
            self.profile_seen = set()
            self.profile_connections = {}
            self.profile_clock = None
            self.profile_cycle = None
            self.buffered_output_written = False
            super().__init__(argv)
            self.surface_timer.stop()

        def trace_surfaces(self):
            return

        def wait_ready(self):
            windows = [w for w in self.topLevelWindows() if w.objectName() == "CSPMMainWindow"]
            if windows and windows[0].property("startupCinematicBloomActive"):
                return
            super().wait_ready()

        @guarded
        def begin_cycles(self):
            self.record("fixture-begin-cycles")
            if args.workspace == "invoice-preview":
                if self.webengine_probe is None:
                    views = [item for item in self.window.findChildren(QObject)
                             if "WebEngineView" in item.metaObject().className()]
                    if not views:
                        QTimer.singleShot(100, self.begin_cycles)
                        return
                    self.engine.rootContext().setContextProperty("diagnosticInvoiceView", views[0])
                    self.engine.globalObject().setProperty("diagnosticInvoiceView", self.engine.newQObject(views[0]))
                    observer = '''import QtQuick
import QtWebEngine
Item {
    id: probe
    property bool ready: false
    property bool failed: false
    visible: false
    Connections {
        target: diagnosticInvoiceView
        function onLoadingChanged(request) {
            if (request.status === WebEngineView.LoadSucceededStatus) probe.ready = true
            if (request.status === WebEngineView.LoadFailedStatus) probe.failed = true
        }
    }
}'''
                    self.webengine_probe = self.evaluate("Qt.createQmlObject(" + json.dumps(observer)
                        + ", _probeWindow.contentItem, 'NativeReadinessWebEngineObserver')").toQObject()
                    html = "<html><body style='background:#f5f7fa;color:#203047;font:20px Segoe UI'><h1>Readiness preview</h1><p>Live Chromium content in the existing invoice preview.</p></body></html>"
                    self.evaluate("diagnosticInvoiceView.loadHtml(" + json.dumps(html) + "); true")
                    self.record("webengine-html-requested", scope="synthetic HTML in existing preview; no invoice action")
                    QTimer.singleShot(100, self.begin_cycles)
                    return
                if self.webengine_probe.property("failed"):
                    raise RuntimeError("Existing invoice WebEngine preview failed synthetic HTML load")
                if not self.webengine_probe.property("ready"):
                    QTimer.singleShot(100, self.begin_cycles)
                    return
                self.record("webengine-html-ready", scope="actual Chromium load success; PDF not exercised")
            if args.keep_visible:
                self.record("fixture-source-z-order-begin")
                user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, uint]
                if not user.SetWindowPos(int(self.window.winId()), -1, 0, 0, 0, 0, 0x13):
                    raise RuntimeError("Diagnostic source z-order unavailable")
                self.window.update()
                self.window.requestActivate()
                user.SetForegroundWindow.argtypes = [wintypes.HWND]
                user.SetForegroundWindow.restype = wintypes.BOOL
                activated = bool(user.SetForegroundWindow(int(self.window.winId())))
                self.record("fixture-source-activation", apiAccepted=activated,
                    scope="Foreground is independently checked before each source comparison")
                self.record("fixture-source-z-order-end")
            self.capture_signal = Captured(self)
            self.capture_signal.ready.connect(self.captured, Qt.QueuedConnection)
            if args.first_direction == "restore":
                if not self.window.property("uiMaximized") or not self.window.property("restoreGeometryValid"):
                    raise RuntimeError("Cold restore requires a persisted maximized source and saved normal rectangle")
                self.normal = {"final" + axis: self.window.property("restoreFinal" + axis) for axis in "XYWH"}
                # Query only the source's settled padding before the command;
                # do not lay out or render the restored target in advance.
                area = self.window.screen().availableGeometry()
                target_pad = self.evaluate("_probeWindow.settledPaddingPx(" + str(self.normal["finalW"])
                    + ", " + str(self.normal["finalH"]) + ")").toNumber()
                pad = min(round(target_pad),
                          max(0, (area.width() - self.normal["finalW"]) // 2),
                          max(0, (area.height() - self.normal["finalH"]) // 2))
                dpr = self.window.devicePixelRatio()
                self.normal_client = [round((self.normal["finalX"] - pad) * dpr),
                    round((self.normal["finalY"] - pad) * dpr),
                    round((self.normal["finalW"] + 2 * pad) * dpr),
                    round((self.normal["finalH"] + 2 * pad) * dpr)]
            else:
                self.normal = {name: self.window.property(name) for name in ("finalX", "finalY", "finalW", "finalH")}
                self.normal_client = client(self.window)
            if args.qt_layout_polish:
                for item in self.window.findChildren(QQuickItem):
                    class_name = item.metaObject().className()
                    if not any(name in class_name for name in ("GridLayout", "RowLayout", "ColumnLayout")):
                        continue
                    ancestors = []
                    parent = item
                    for _ in range(8):
                        if parent is None:
                            break
                        qml_context = QQmlApplicationEngine.contextForObject(parent)
                        ancestors.append({"class": parent.metaObject().className(),
                            "id": qml_context.nameForObject(parent) if qml_context else ""})
                        parent = parent.parentItem()
                    self.qt_layout_objects[hex(getCppPointer(item)[0])] = {
                        "visible": item.isVisible(), "size": [item.width(), item.height()],
                        "ancestors": ancestors}
            if args.endpoint_pixels:
                self.record("fixture-desktop-camera-begin")
                dependencies = os.environ.get("CSPM_PIXEL_DEPENDENCIES")
                if dependencies:
                    sys.path.insert(0, dependencies)
                import dxcam
                self.desktop_camera = dxcam.create(device_idx=0, output_idx=0,
                    output_color="BGRA", processor_backend="numpy", max_buffer_len=2)
                self.desktop_observer = DesktopFrameObserver()
                self.record("capture-session-start", qpcSeconds=self.desktop_observer.started_seconds)
                self.record("fixture-desktop-camera-end")
                if args.physical_diagnostics or args.source_observation_only:
                    from source_pixel_analysis import grab_observed, window_observation, compare_pixels, physical_regions
                    self.grab_observed = grab_observed
                    self.window_observation = window_observation
                    self.analyze_pixels = compare_pixels
                    self.physical_regions = physical_regions
            super().begin_cycles()

        def create_probe_marker(self, code, name):
            # Direct component construction releases the Python GIL during QML
            # compilation. Keep blocking Qt.createQmlObject out of JS evaluate.
            component = QQmlComponent(self.engine)
            component.setData(code.encode("utf-8"), QUrl("file:///NativeReviewPixel_" + name + ".qml"))
            if not component.isReady():
                raise RuntimeError("Movement marker failed to compile: " + component.errorString())
            parent = self.evaluate("_probeWindow.contentLayerRef").toQObject()
            if parent is None:
                raise RuntimeError("Movement marker parent unavailable")
            item = component.createWithInitialProperties({"parent": parent})
            if item is None:
                raise RuntimeError("Movement marker failed to instantiate: " + component.errorString())
            item.setParent(parent)
            self.sensor_components.append(component)
            self.sensor_items.append(item)

        def request_capture(self, kind):
            self.capture_request = {"kind": kind, "requested": time.perf_counter(), "client": client(self.window)}
            requested = self.capture_request
            if not self.capture_connected:
                self.window.afterRenderPassRecording.connect(self.on_render, Qt.DirectConnection)
                self.capture_connected = True
            self.window.update()
            QTimer.singleShot(1800, lambda: self.capture_deadline(requested))

        def capture_deadline(self, requested):
            if not self.finished and self.capture_request is requested:
                self.fail("native texture access", "No main render callback within 1800 ms")

        def on_render(self):
            request = self.capture_request
            if request is None or self.finished or self.completion_pending:
                return
            self.capture_in_progress = True
            self.capture_request = None
            if self.capture_connected:
                self.window.afterRenderPassRecording.disconnect(self.on_render)
                self.capture_connected = False
            result = dict(request)
            result["renderCallback"] = time.perf_counter()
            try:
                renderer = self.window.rendererInterface()
                result["graphicsApi"] = renderer.graphicsApi().name
                if renderer.graphicsApi() != QSGRendererInterface.Direct3D11:
                    raise RuntimeError("Actual Qt renderer is not Direct3D11")
                self.window.beginExternalCommands()
                try:
                    native = renderer.getResource(self.window, QSGRendererInterface.DeviceContextResource)
                    if native is None or not int(native):
                        raise RuntimeError("Public Qt native device context unavailable")
                    width, height = uint(), uint()
                    frame = dll.cspm_gpu_capture(int(native), ctypes.byref(width), ctypes.byref(height))
                    if not frame:
                        raise RuntimeError(native_error())
                    # Own the frame immediately, including errors during
                    # endExternalCommands and undelivered queued notifications.
                    self.frames.append(frame)
                    result.update(frame=frame, size=[width.value, height.value], gpuOnly=True)
                finally:
                    self.window.endExternalCommands()
            except Exception as exc:
                result["error"] = str(exc)
            result["captureFinished"] = time.perf_counter()
            if args.render_target_import and request["kind"] == "target" and not result.get("error"):
                try:
                    import_render_target(result, self.host, self.target_client,
                        dll.cspm_comp_set_target_frame, native_error)
                except Exception as exc:
                    result["error"] = str(exc)
            self.capture_in_progress = False
            self.capture_signal.ready.emit(result)

        def record(self, name, **data):
            row = {"event": name, "t": time.perf_counter(), "cycle": self.completed, **data}
            self.rows.append(row)
            if not args.profile_boundaries:
                print(json.dumps(row), flush=True)

        def profile_signal(self, name, geometry=False):
            if not self.profile_armed or name in self.profile_seen:
                return
            self.profile_seen.add(name)
            row = {"boundary": name, "t": time.perf_counter(), "cycle": self.profile_cycle,
                "clock": "perf_counter at Python/GIL callback entry"}
            if geometry:
                try:
                    row.update(qtSize=[self.window.width(), self.window.height()],
                        nativeClient=client(self.window))
                except Exception as exc:
                    row["observationError"] = str(exc)
            self.boundary_rows.append(row)
            self.disconnect_profile_signal(name)

        def disconnect_profile_signal(self, name):
            connection = self.profile_connections.pop(name, None)
            if connection is not None:
                signal, callback = connection
                signal.disconnect(callback)

        def begin_target_profile(self):
            if not args.profile_boundaries:
                return
            before_calibration = time.perf_counter()
            wall_ms = self.evaluate("Date.now()").toNumber()
            after_calibration = time.perf_counter()
            self.profile_clock = {"wallMs": wall_ms,
                "perfCounterMidpoint": (before_calibration + after_calibration) / 2,
                "calibrationBracketMs": (after_calibration - before_calibration) * 1000,
                "wallResolutionMs": 1}
            self.record("profile-clock-calibration", **self.profile_clock)
            self.evaluate("_probeWindow.cleanRoomNativeProfileMarkers = []; "
                "_probeWindow.cleanRoomNativeProfileEnabled = true")
            if args.fanout_variant:
                self.evaluate("_probeWindow.cleanRoomFanoutBegin()")
            self.profile_seen = set()
            self.profile_cycle = self.completed
            self.profile_armed = True
            # Each callback disconnects after one observation, and any remaining
            # connections are removed when target capture is delivered. Avoid
            # repeatedly acquiring the GIL for later frames or lifecycle work.
            for name in ("beforeFrameBegin", "beforeSynchronizing", "afterSynchronizing",
                    "beforeRendering", "afterRenderPassRecording", "afterRendering", "frameSwapped"):
                signal = getattr(self.window, name)
                key = "render:" + name
                callback = lambda *_, n=key: self.profile_signal(n)
                self.profile_connections[key] = (signal, callback)
                signal.connect(callback, Qt.DirectConnection)
            for name in ("widthChanged", "heightChanged"):
                signal = getattr(self.window, name)
                key = "adoption:" + name
                callback = lambda *_, n=key: self.profile_signal(n, geometry=True)
                self.profile_connections[key] = (signal, callback)
                signal.connect(callback, Qt.DirectConnection)

        def finish_target_profile(self):
            if not args.profile_boundaries or not self.profile_armed:
                return
            self.profile_armed = False
            for name in list(self.profile_connections):
                self.disconnect_profile_signal(name)
            self.evaluate("_probeWindow.cleanRoomNativeProfileEnabled = false")
            if args.fanout_variant:
                counts = self.evaluate("_probeWindow.cleanRoomFanoutFinish()").toVariant()
                self.fanout_rows.append({"cycle": self.profile_cycle, "counts": counts})
            markers = self.window.property("cleanRoomNativeProfileMarkers")
            if hasattr(markers, "toVariant"):
                markers = markers.toVariant()
            for marker in markers or []:
                self.boundary_rows.append({**marker, "cycle": self.profile_cycle,
                    "t": self.profile_clock["perfCounterMidpoint"]
                        + (marker["wallMs"] - self.profile_clock["wallMs"]) / 1000,
                    "clock": "QML Date.now calibrated to perf_counter; 1 ms resolution"})

        def presentation_telemetry(self):
            if not self.host or not hasattr(dll, "cspm_comp_presentation"):
                return {"scope": "unavailable; native status is submission only"}
            submitted, displayed, result = uint(), uint(), uint()
            dll.cspm_comp_presentation(self.host, ctypes.byref(submitted), ctypes.byref(displayed), ctypes.byref(result))
            return {"submitted": submitted.value, "displayed": displayed.value,
                "statisticsHRESULT": "0x%08X" % result.value,
                "scope": "DXGI statistics; desktop collector remains decisive"}

        @guarded
        def step(self):
            if self.completed >= args.cycles:
                self.complete()
                return
            maximize = (self.completed % 2 == 0) == (args.first_direction == "maximize")
            kind = "maximize" if maximize else "restore"
            self.window_state = "normal" if maximize else "maximized"
            self.current = {"kind": kind, "command": time.perf_counter(), "sourceClient": client(self.window)}
            self.tracker.command("native-" + kind)
            self.record("command", kind=kind, sourceClient=self.current["sourceClient"])
            if args.physical_diagnostics or args.source_observation_only:
                self.witness_rect = None
                # WebEngine may have changed focus after initial setup. This
                # is fixture placement before sampling, never target warming.
                self.window.requestActivate()
                user.SetForegroundWindow(int(self.window.winId()))
                self.state_observation("source-request")
                foreground = self.window_observation(int(self.window.winId())).get("foregroundHwnd")
                issued = time.perf_counter()
                self.window.update()
                self.observe_desktop(self.current["sourceClient"], "source-command", issued,
                    {"qtOpacity": 1.0, "live.foregroundHwnd": foreground,
                     "live.clientXYWH": self.current["sourceClient"]},
                    self.source_reference_observed)
                return
            self.source_reference_observed(self.desktop_pixels(self.current["sourceClient"], "source-command"))

        def source_reference_observed(self, pixels):
            self.source_desktop = pixels
            if not args.source_unlocked:
                self.lock_input()
            else:
                self.record("source-unlocked-control", scope="No input-state change; cannot qualify input restoration")
            self.request_capture("source")

        def lock_input(self):
            if self.input_was_enabled is not None:
                raise RuntimeError("Diagnostic input guard already owns a transaction")
            hwnd = int(self.window.winId())
            self.input_was_enabled = bool(user.IsWindowEnabled(hwnd))
            self.record("input-lock-issued", previouslyEnabled=self.input_was_enabled)
            self.evaluate("_probeWindow.professionalWindowTransitionActive = true")
            user.EnableWindow(hwnd, False)
            self.record("input-locked", nativeEnabled=bool(user.IsWindowEnabled(hwnd)),
                qmlInteractive=self.evaluate("_probeWindow.mainContentRef.isInteractive").toBool())

        def unlock_input(self):
            if self.input_was_enabled is None or self.window is None or not isValid(self.window):
                return
            self.record("input-restore-issued")
            self.evaluate("_probeWindow.professionalWindowTransitionActive = false")
            user.EnableWindow(int(self.window.winId()), self.input_was_enabled)
            self.record("input-restored", nativeEnabled=bool(user.IsWindowEnabled(int(self.window.winId()))),
                qmlInteractive=self.evaluate("_probeWindow.mainContentRef.isInteractive").toBool())
            if bool(user.IsWindowEnabled(int(self.window.winId()))) != self.input_was_enabled:
                context["failures"].append("native input enabled state did not return to its saved value")
            self.input_was_enabled = None

        def observation_state(self):
            native = native_observation(dll, self.host)
            state = {"live": self.window_observation(int(self.window.winId())),
                "qtDpr": self.window.devicePixelRatio(), "qtOpacity": self.window.opacity(),
                "windowState": self.window_state,
                "transitionGeneration": self.completed + 1,
                "presentationRevision": self.witness_revision,
                "compositionCommitGeneration": 1 if native.get("sourceCommitReturnSeconds", 0) else 0,
                "finalGeometry": [self.window.property("final" + axis) for axis in "XYWH"],
                "glowPadding": self.window.property("glowPadding"),
                "cornerRadius": self.evaluate("_probeWindow.shellVisualCornerRadiusPx()").toNumber(),
                "native": native}
            if self.host and hasattr(dll, "cspm_comp_hwnd"):
                state["transition"] = self.window_observation(dll.cspm_comp_hwnd(self.host))
            if self.webengine_probe is not None:
                state["webengine"] = {"htmlReady": bool(self.webengine_probe.property("ready")),
                    "failed": bool(self.webengine_probe.property("failed"))}
            return state

        def state_observation(self, label):
            if not (args.physical_diagnostics or args.source_observation_only):
                return
            self.record("physical-window-state", label=label, **self.observation_state())

        def configure_witness(self, physical, target):
            # Select a visible margin in this bounded output-0 fixture. The
            # shader separately rejects any overlap with either client.
            left, top, width, height = self.envelope
            right, bottom = min(1920, left + width), min(1080, top + height)
            def overlap(a, b):
                return a[0] < b[0]+b[2] and a[0]+a[2] > b[0] and a[1] < b[1]+b[3] and a[1]+a[3] > b[1]
            candidates = [[physical[0]+8, max(physical[1]+physical[3],target[1]+target[3])+8, 8, 8],
                [max(0, left)+8, bottom-16, 8, 8],
                [right-16, max(0, top)+8, 8, 8]]
            if not args.source_observation_only:
                candidates[0], candidates[1] = candidates[1], candidates[0]
            self.witness_rect = next((box for box in candidates if box[0]>=0 and box[1]>=0
                and box[0]>=left and box[1]>=top and box[0]+8<=right and box[1]+8<=bottom
                and not overlap(box, physical) and not overlap(box, target)), None)
            if self.witness_rect is None or not hasattr(dll, "cspm_comp_set_observer_witness"):
                raise RuntimeError("Qualification requires an observable same-swapchain witness outside both clients")
            self.witness_revision = (os.getpid() % 30000) * 2 + self.completed * 2 + 1
            self.refresh_witness()

        def refresh_witness(self):
            dll.cspm_comp_set_observer_witness.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            dll.cspm_comp_set_observer_witness.restype = ctypes.c_int
            x, y = self.witness_rect[:2]
            if not dll.cspm_comp_set_observer_witness(self.host, x-self.envelope[0], y-self.envelope[1], self.witness_revision):
                raise RuntimeError("Diagnostic visual witness rejected: " + native_error(self.host))

        def observe_desktop(self, rectangle, label, after_seconds, expected_state, callback, phase=None):
            if self.observation_pending is not None:
                raise RuntimeError("One desktop observation may be pending")
            bounds = list(rectangle)
            if self.witness_rect:
                x,y,w,h = bounds; wx,wy,ww,wh = self.witness_rect
                bounds = [min(x,wx), min(y,wy), max(x+w,wx+ww)-min(x,wx), max(y+h,wy+wh)-min(y,wy)]
            witness = {"revision": self.witness_revision, "phase": phase, "exact": True} if phase else None
            expected_state = {"live.hwnd": int(self.window.winId()), "live.visible": True,
                "live.iconic": False, "live.cloaked": 0,
                "windowState": self.window_state, "transitionGeneration": self.completed + 1,
                "presentationRevision": self.witness_revision, **expected_state}
            if self.host:
                expected_state["transition.hwnd"] = dll.cspm_comp_hwnd(self.host)
            gate = FreshPresentationGate(self.desktop_observer, bounds, after_seconds,
                expected_state=expected_state, expected_witness=witness)
            self.observation_pending = (gate, list(rectangle), bounds, label, callback, phase)
            self.poll_desktop_observation()

        @guarded
        def poll_desktop_observation(self):
            if self.finished or self.observation_pending is None:
                return
            gate, rectangle, bounds, label, callback, phase = self.observation_pending
            before = self.observation_state()
            pixels, metadata = self.grab_observed(self.desktop_camera, bounds)
            after = self.observation_state()
            if pixels is not None and self.witness_rect:
                wx,wy,ww,wh = self.witness_rect
                patch = pixels[wy-bounds[1]:wy-bounds[1]+wh, wx-bounds[0]:wx-bounds[0]+ww]
                import numpy as np
                expected_bgra = np.array([phase or 0, (self.witness_revision>>8)&255, self.witness_revision&255, 255], dtype=np.uint8)
                exact = phase is not None and bool(np.all(patch[:,:,:3] == expected_bgra[:3]))
                # With the host removed, none of the pixels may retain the
                # source/endpoint witness (an independent disappearance check).
                absent = not bool(np.any(np.all(patch[:,:,:3] == np.array([3,(self.witness_revision>>8)&255,self.witness_revision&255]), axis=2)))
                absent &= not bool(np.any(np.all(patch[:,:,:3] == np.array([1,(self.witness_revision>>8)&255,self.witness_revision&255]), axis=2)))
                metadata["visualWitness"] = {"revision": self.witness_revision, "phase": phase, "exact": exact}
                metadata["witnessMatchedPixels"] = int(np.count_nonzero(np.all(patch[:,:,:3] == expected_bgra[:3], axis=2)))
                metadata["witnessRectangleXYWH"] = self.witness_rect
                before["witnessAbsent"] = after["witnessAbsent"] = absent
            accepted, evidence = gate.poll(pixels, metadata, state_before=before, state_after=after)
            if evidence["status"] == "PENDING":
                QTimer.singleShot(8, self.poll_desktop_observation)
                return
            self.observation_pending = None
            self.snapshot_observations[label] = evidence
            self.record("desktop-observation", label=label, comparisonRectangleXYWH=rectangle, **evidence)
            self.record("physical-window-state", label=label, **after)
            if accepted is None:
                self.fail("physical observer", label + ": " + str(evidence.get("reason", evidence.get("status"))))
                return
            x,y,w,h = rectangle
            callback(accepted[y-bounds[1]:y-bounds[1]+h, x-bounds[0]:x-bounds[0]+w].copy())

        def record_pixel_regions(self, physical, name):
            dpr = self.window.devicePixelRatio()
            header = self.evaluate("_probeWindow.mainContentRef.professionalTransitionHeaderMetrics()").toVariant()
            content = self.evaluate("(function() { var c = _probeWindow.contentLayerRef; "
                "var p = c.mapToItem(_probeWindow.contentItem, 0, 0); "
                "return [p.x,p.y,c.width,c.height]; })()").toVariant()
            content_rect = [physical[0] + round(content[0] * dpr),
                physical[1] + round(content[1] * dpr), round(content[2] * dpr), round(content[3] * dpr)]
            regions = self.physical_regions(physical, physical, content_rect,
                header_height_px=round(header.x() * dpr), border_px=0)
            destination = self.pixel_regions if name == "source" else self.target_pixel_regions
            destination[self.completed] = regions
            self.record("physical-" + name + "-regions", contentXYWH=content_rect,
                headerHeightPx=round(header.x() * dpr), borderClassification="unavailable; no border width inferred")

        def desktop_pixels(self, rectangle, label="desktop"):
            if self.desktop_camera is None:
                return None
            x, y, width, height = rectangle
            # This measurement fixture uses only output 0; negative/mixed-DPI
            # physical acceptance is not claimed from this single-display crop.
            if x < 0 or y < 0 or x + width > 1920 or y + height > 1080:
                raise RuntimeError("Endpoint measurement crop exceeds output 0")
            if args.physical_diagnostics or args.source_observation_only:
                pixels, observation = self.grab_observed(self.desktop_camera, rectangle)
                self.snapshot_observations[label] = observation
                self.record("desktop-acquisition", label=label, **observation)
                self.state_observation(label)
                if pixels is None:
                    self.record("desktop-acquisition-unavailable", label=label)
                    return None
                return pixels
            pixels = self.desktop_camera.grab(region=(x, y, x + width, y + height), new_frame_only=False)
            if pixels is None:
                raise RuntimeError("DXGI endpoint measurement unavailable")
            return pixels.copy()

        def compare_pixels(self, name, old, new):
            if old is None or new is None:
                self.record(name, status="UNMEASURED")
                if args.endpoint_pixels and name != "source-live-to-overlap-pixels":
                    context["failures"].append(name + ": required fresh desktop acquisition unavailable")
                return
            if args.physical_diagnostics or args.source_observation_only:
                self.pixel_pairs.append((self.completed, name, old, new))
                self.record(name, status="PENDING", scope="owned RAM snapshots; spatial comparison follows timed work")
                return
            import numpy as np
            if old.shape != new.shape:
                self.record(name, status="FAIL", reason="different physical pixel arrays")
                context["failures"].append(name + ": array dimensions differ")
                return
            delta = np.abs(old.astype(np.int16) - new.astype(np.int16))
            different = int(np.count_nonzero(np.any(delta != 0, axis=2)))
            # All values are nonsensitive aggregate metrics. Images remain in RAM.
            self.record(name, status="PASS" if different == 0 else "FAIL", differentPixels=different,
                maxChannelDifference=int(delta.max()), meanChannelDifference=float(delta.mean()),
                luminanceDifference=float(np.mean(new[:, :, :3]) - np.mean(old[:, :, :3])))
            if different:
                context["failures"].append(name + ": physical pixels differ")

        @guarded
        def captured(self, result):
            if self.finished:
                return
            if self.completion_pending:
                self.complete()
                return
            self.record("gpu-capture", **{key: value for key, value in result.items() if key != "frame"})
            if result.get("error"):
                self.fail("native texture access", result["error"])
                return
            if result["kind"] == "target":
                if args.physical_diagnostics:
                    self.record_pixel_regions(result["client"], "target")
                self.finish_target_profile()
                self.qt_target_capture_pending = False
                if args.qt_layout_polish:
                    QLoggingCategory.setFilterRules("qt.quick.layouts.debug=false\nqt.scenegraph.time.*.debug=true")
                if args.layout_only:
                    if result["client"] != self.target_client:
                        self.fail("physical-pixel mapping", "Layout isolation target differs from planned client")
                        return
                    self.record("layout-profile-ready", actualClient=client(self.window))
                    self.window.setOpacity(1)
                    self.evaluate("_probeWindow.geometryTransitionSuppressed = false")
                    self.unlock_input()
                    dll.cspm_comp_destroy(self.host)
                    self.host = None
                    for frame in self.frames:
                        dll.cspm_gpu_release(frame)
                    self.frames.clear()
                    self.completed += 1
                    QTimer.singleShot(500, self.step)
                    return
            if args.capture_only:
                self.completed += 1
                self.complete()
                return
            if result["kind"] == "source":
                physical = result["client"]
                screen = self.window.screen()
                area = screen.availableGeometry()
                dpr = self.window.devicePixelRatio()
                if self.current["kind"] == "maximize":
                    self.goal = {"x": area.x(), "y": area.y(), "w": area.width(), "h": area.height()}
                    target = [round(area.x() * dpr), round(area.y() * dpr), round(area.width() * dpr), round(area.height() * dpr)]
                else:
                    self.goal = dict(x=self.normal["finalX"], y=self.normal["finalY"], w=self.normal["finalW"], h=self.normal["finalH"])
                    target = self.normal_client
                self.target_client = list(target)
                left, top = min(physical[0], target[0]) - 32, min(physical[1], target[1]) - 32
                right = max(physical[0] + physical[2], target[0] + target[2]) + 32
                bottom = max(physical[1] + physical[3], target[1] + target[3]) + 32
                self.envelope = [left, top, right - left, bottom - top]
                self.host = dll.cspm_comp_create_from_frame(result["frame"], *self.envelope)
                if not self.host:
                    self.fail("DirectComposition presentation", native_error())
                    return
                if args.physical_diagnostics or args.source_observation_only:
                    self.configure_witness(physical, physical if args.source_observation_only else target)
                header = self.evaluate("_probeWindow.mainContentRef.professionalTransitionHeaderMetrics()").toVariant()
                if args.physical_diagnostics or args.source_observation_only:
                    self.record_pixel_regions(physical, "source")
                pad_y = max(0, (physical[3] - self.window.property("finalH") * dpr) / 2)
                header_height = pad_y + header.x() * dpr
                right_fixed = header.y() * dpr + max(0, (physical[2] - self.window.property("finalW") * dpr) / 2)
                if not dll.cspm_comp_set_source_frame(self.host, result["frame"], physical[0] - left, physical[1] - top, physical[2], physical[3], header_height, right_fixed):
                    self.fail("DirectComposition presentation", native_error(self.host))
                    return
                self.record("source-composition-committed", source=physical, target=target, envelope=self.envelope)
                self.state_observation("source-commit")
                if args.physical_diagnostics or args.source_observation_only:
                    native = native_observation(dll, self.host)
                    self.observe_desktop(physical, "source-overlap",
                        max(native["sourceShowReturnSeconds"], native["lastPresentReturnSeconds"]),
                        {"qtOpacity": 1.0, "transition.visible": True, "live.clientXYWH": physical},
                        self.after_source_coverage, phase=1)
                else:
                    QTimer.singleShot(70, self.after_source_coverage)
            else:
                if result["client"] != self.target_client:
                    self.record("physical-target-plan-mismatch", planned=self.target_client, actual=result["client"])
                    self.fail("physical-pixel mapping", "Actual target native client differs from predetermined endpoint")
                    return
                imported = result.get("targetImported") if args.render_target_import else dll.cspm_comp_set_target_frame(self.host, result["frame"])
                if not imported:
                    if args.render_target_import:
                        self.record("target-render-import-rejected", started=result.get("targetImportStarted"),
                            finished=result.get("targetImportFinished"))
                    self.fail("target readiness", native_error(self.host))
                    return
                self.record("target-gpu-composition-committed", elapsedMs=dll.cspm_comp_elapsed_ms(self.host),
                    importThread="render" if args.render_target_import else "GUI",
                    importStarted=result.get("targetImportStarted"), importFinished=result.get("targetImportFinished"))
                if args.prepared_target:
                    self.start_native()
                else:
                    self.poll_native()

        @guarded
        def after_source_coverage(self, pixels=None):
            if args.physical_diagnostics or args.source_observation_only:
                self.source_overlap = pixels
                self.compare_pixels("source-live-to-overlap-pixels", self.source_desktop, self.source_overlap)
            self.window.setOpacity(0)
            if args.physical_diagnostics or args.source_observation_only:
                self.witness_revision += 1
                self.refresh_witness()
                native = native_observation(dll, self.host)
                self.observe_desktop(self.current["sourceClient"], "source-hidden", native["lastPresentReturnSeconds"],
                    {"qtOpacity": 0.0, "transition.visible": True,
                     "live.clientXYWH": self.current["sourceClient"]}, self.after_source_hidden, phase=1)
            else:
                QTimer.singleShot(35, self.after_source_hidden)

        @guarded
        def after_source_hidden(self, pixels=None):
            self.source_native_desktop = (pixels if args.physical_diagnostics or args.source_observation_only
                else self.desktop_pixels(self.current["sourceClient"], "source-hidden"))
            self.compare_pixels("source-live-to-gpu-pixels", self.source_desktop,
                self.source_native_desktop)
            if args.source_observation_only:
                if not dll.cspm_comp_finish(self.host):
                    self.fail("source visibility control", native_error(self.host))
                    return
                self.record("source-native-hide-control", native=native_observation(dll, self.host))
                native = native_observation(dll, self.host)
                self.observe_desktop(self.current["sourceClient"], "source-native-removed", native["hostHideReturnSeconds"],
                    {"qtOpacity": 0.0, "transition.visible": False, "witnessAbsent": True},
                    self.source_removal_observation)
                return
            if args.prepared_target:
                self.prepare_live_target()
            elif args.layout_only:
                self.record("layout-profile-start", scope="static source coverage, no native motion")
                self.prepare_live_target()
            else:
                self.start_native()

        @guarded
        def source_removal_observation(self, removed):
            self.compare_pixels("source-gpu-to-native-removed-pixels", self.source_native_desktop, removed)
            self.completed += 1
            self.complete()

        @guarded
        def start_native(self):
            self.window_state = "maximizing" if self.current["kind"] == "maximize" else "restoring"
            self.window.setOpacity(0)
            target = self.target_client
            if not dll.cspm_comp_start(self.host, target[0] - self.envelope[0], target[1] - self.envelope[1], target[2], target[3], args.duration_ms, args.blend_start_ms):
                self.fail("DirectComposition presentation", native_error(self.host))
                return
            self.started_native = time.perf_counter()
            self.record("native-clock-start", durationMs=args.duration_ms, transferDeadlineMs=args.blend_start_ms)
            delay_start = time.perf_counter()
            time.sleep(args.gui_delay_ms / 1000)
            self.record("intentional-gui-delay-end", measuredMs=(time.perf_counter() - delay_start) * 1000)
            if args.prepared_target:
                self.poll_native()
            else:
                self.prepare_live_target()

        @guarded
        def prepare_live_target(self):
            goal = json.dumps(self.goal)
            kind = json.dumps(self.current["kind"])
            self.qt_target_capture_pending = True
            self.begin_target_profile()
            self.record("layout-begin")
            command = "_probeWindow.geometryTransitionSuppressed = true; _probeWindow.commitProfessionalWindowTransitionTarget(" + kind + ", " + goal + ", _probeWindow.screen)"
            if args.profile_python_commit:
                profiler = cProfile.Profile()
                profiler.runcall(self.evaluate, command)
                profiler.dump_stats(str(audit / ("commit_%d.pstats" % self.completed)))
            else:
                self.evaluate(command)
            self.record("layout-committed", actualClient=client(self.window))
            if args.qt_layout_polish:
                QLoggingCategory.setFilterRules("qt.quick.layouts.debug=true\nqt.scenegraph.time.*.debug=true")
            self.request_capture("target")

        @guarded
        def poll_native(self):
            if self.finished or not self.host:
                return
            status = dll.cspm_comp_status(self.host)
            if status & 16:
                self.fail("DirectComposition presentation", native_error(self.host))
                return
            if status & 4:
                self.record("native-endpoint-submitted", elapsedMs=dll.cspm_comp_elapsed_ms(self.host),
                    diagnosticHoldMs=args.endpoint_hold_ms, presentation=self.presentation_telemetry(),
                    native=native_observation(dll, self.host))
                if args.physical_diagnostics:
                    self.measure_endpoint()
                else:
                    QTimer.singleShot(args.endpoint_hold_ms, self.measure_endpoint)
            else:
                QTimer.singleShot(8, self.poll_native)

        @guarded
        def measure_endpoint(self):
            self.record("desktop-endpoint-measurement", elapsedMs=dll.cspm_comp_elapsed_ms(self.host),
                presentation=self.presentation_telemetry())
            if args.physical_diagnostics:
                native = native_observation(dll, self.host)
                self.observe_desktop(self.target_client, "target-endpoint", native["endpointPresentReturnSeconds"],
                    {"qtOpacity": 0.0, "transition.visible": True,
                     "live.clientXYWH": self.target_client, "native.lastFrameMotion": 1.0,
                     "native.lastFrameContent": 1.0}, self.endpoint_observed, phase=3)
                return
            self.endpoint_observed(self.desktop_pixels(self.target_client, "target-endpoint"))

        def endpoint_observed(self, pixels):
            self.window_state = "maximized" if self.current["kind"] == "maximize" else "restored"
            self.target_desktop = pixels
            if args.physical_diagnostics:
                self.live_handoff_connected = True
                self.window.frameSwapped.connect(self.live_host_frame, Qt.QueuedConnection)
            self.window.setOpacity(1)
            self.record("live-host-revealed")
            self.window.update()
            if args.physical_diagnostics:
                QTimer.singleShot(750, self.live_host_deadline)
            else:
                QTimer.singleShot(100, self.handoff)

        @guarded
        def live_host_frame(self):
            if not self.live_handoff_connected or self.finished:
                return
            self.window.frameSwapped.disconnect(self.live_host_frame)
            self.live_handoff_connected = False
            self.record("first-live-host-frame", scope="Queued Qt frame notification; matching desktop follows native removal")
            self.handoff()

        def live_host_deadline(self):
            if self.live_handoff_connected and not self.finished:
                self.fail("live-HWND handoff", "No submitted live-host frame before bounded observation deadline")

        @guarded
        def handoff(self):
            if self.finished:
                return
            if not dll.cspm_comp_finish(self.host):
                self.fail("live-HWND handoff", native_error(self.host))
                return
            if args.physical_diagnostics:
                native = native_observation(dll, self.host)
                self.observe_desktop(self.target_client, "target-live", native["hostHideReturnSeconds"],
                    {"qtOpacity": 1.0, "transition.visible": False, "witnessAbsent": True,
                     "live.clientXYWH": self.target_client}, self.handoff_compare)
            else:
                QTimer.singleShot(40, self.handoff_compare)

        @guarded
        def handoff_compare(self, pixels=None):
            if self.finished:
                return
            self.record("live-handoff", actualClient=client(self.window),
                commandToLiveMs=(time.perf_counter() - self.current["command"]) * 1000)
            self.compare_pixels("gpu-to-live-target-pixels", self.target_desktop,
                pixels if args.physical_diagnostics else self.desktop_pixels(self.target_client, "target-live"))
            self.state_observation("host-hidden")
            self.record("native-present-history", **native_present_trace(dll, self.host))
            dll.cspm_comp_destroy(self.host)
            self.host = None
            for frame in self.frames:
                dll.cspm_gpu_release(frame)
            self.frames.clear()
            self.evaluate("_probeWindow.geometryTransitionSuppressed = false; _probeWindow.updateCanvasGeometry()")
            self.unlock_input()
            if client(self.window) != self.target_client:
                context["failures"].append("Input restoration changed the qualified target client geometry")
            self.state_observation("input-restored")
            self.completed += 1
            QTimer.singleShot(200, self.step)

        def fail(self, category, error):
            context["failures"].append(category + ": " + error)
            self.record("qualification-failure", category=category, error=error)
            self.complete()

        def timeout(self):
            if self.finished:
                return
            self.fail("fixture deadline", "Populated spike exceeded 120 seconds")

        def complete(self):
            if self.finished:
                return
            if self.capture_in_progress:
                if not self.completion_pending:
                    self.completion_pending = True
                    QTimer.singleShot(10, self.complete)
                else:
                    QTimer.singleShot(10, self.complete)
                return
            self.finished = True
            self.observation_pending = None
            if self.live_handoff_connected:
                self.window.frameSwapped.disconnect(self.live_host_frame)
                self.live_handoff_connected = False
            self.qt_target_capture_pending = False
            self.capture_request = None
            if self.capture_connected:
                self.window.afterRenderPassRecording.disconnect(self.on_render)
                self.capture_connected = False
            if self.profile_armed:
                try:
                    self.finish_target_profile()
                except Exception as exc:
                    self.profile_armed = False
                    self.boundary_rows.append({"boundary": "profile-collection-error",
                        "cycle": self.profile_cycle, "t": time.perf_counter(), "error": str(exc)})
            if self.window is not None and isValid(self.window):
                self.window.setOpacity(1)
                self.unlock_input()
            if self.host:
                self.record("native-present-history", **native_present_trace(dll, self.host))
                dll.cspm_comp_destroy(self.host)
                self.host = None
            for frame in self.frames:
                dll.cspm_gpu_release(frame)
            self.frames.clear()
            for cycle, name, old, new in self.pixel_pairs:
                regions = self.target_pixel_regions if name == "gpu-to-live-target-pixels" else self.pixel_regions
                try:
                    analysis = self.analyze_pixels(old, new, regions=regions.get(cycle))
                except Exception as exc:
                    self.record("physical-pixel-analysis-failure", comparison=name, sampledCycle=cycle, error=str(exc))
                    context["failures"].append(name + ": spatial analysis failed: " + str(exc))
                    continue
                self.record("physical-pixel-analysis", comparison=name, sampledCycle=cycle,
                    contentDelivery=("newly delivered unchanged client pixels" if analysis.get("differentPixels") == 0
                        else "newly delivered changed client pixels"),
                    contentDeliveryScope="Owned compared arrays; acquisition evidence is recorded separately", **analysis)
                if name == "source-gpu-to-native-removed-pixels":
                    if analysis.get("rgbDifferentPixels", 0) == 0:
                        context["failures"].append("source removal was not physically observed")
                elif analysis["status"] != "PASS":
                    context["failures"].append(name + ": physical pixels differ")
            self.pixel_pairs.clear()
            self.record("observed-content-deliveries", scope="Deferred owned-array identity, separate from acquisition freshness",
                snapshots=[{"label": label, "observerGeneration": proof["frame"]["observerGeneration"],
                    "sha256": hashlib.sha256(pixels.tobytes()).hexdigest()}
                    for label, pixels in (("source-live", self.source_desktop), ("source-native", getattr(self,"source_native_desktop",None)),
                        ("target-native", self.target_desktop)) if pixels is not None
                    for proof in [self.snapshot_observations.get({"source-live":"source-command", "source-native":"source-hidden", "target-native":"target-endpoint"}[label])]
                    if proof is not None and proof["status"] == "PASS"])
            if self.desktop_camera is not None:
                self.desktop_camera.release()
                self.desktop_camera = None
            self.record("spike-finished", completeCycles=self.completed)
            if self.window is not None and isValid(self.window):
                try:
                    self.evaluate("_probeWindow.geometryTransitionSuppressed = false; _probeWindow.requestCloseAnimation()")
                except Exception as exc:
                    context["failures"].append("fixture close: " + str(exc))
            QTimer.singleShot(2000, self.quit)

        def write_results(self):
            if hasattr(self, "tracker"):
                try:
                    self.tracker.stop()
                except Exception as exc:
                    context["failures"].append("physical collector: " + str(exc))
            payload = {"configuration": vars(args), "dllHash": dll_hash,
                "sourceProvenance": {"scope": "SHA-256 read at fixture startup, before application launch",
                    "sources": source_provenance, "disposableMirror": mirror_provenance},
                "events": self.rows,
                "profileBoundaries": sorted(self.boundary_rows, key=lambda row: row["t"]),
                "fanoutCounts": self.fanout_rows,
                "qtStageTimings": self.qt_timing_rows,
                "qtLayoutPolish": self.qt_layout_rows,
                "qtLayoutObjects": self.qt_layout_objects,
                "profileScope": ("QML statements are millisecond wall-clock observations calibrated per cycle. "
                    "Qt adoption/render signals are one-shot Python callbacks that require the GIL. "
                    "Render observations may span frames while target commit/capture is pending; "
                    "they do not isolate pure Qt work, GPU completion, WebEngine readiness or scanout. "
                    "Profiling buffers fixture event printing until results are written."
                    if args.profile_boundaries else "not enabled"),
                "completedCycles": self.completed, "failures": context["failures"],
                "measurementScope": "GPU transfer and native status; physical geometry needs separate collector analysis",
                "coldCandidateQualification": "NOT QUALIFYING" if args.prepared_target or args.capture_only or args.layout_only or args.source_observation_only else "FAIL" if context["failures"] else "REQUIRES ALL PHYSICAL GATES",
                "presentationCpuReadbacks": 0, "presentationCpuUploads": 0}
            (audit / "native_gpu_spike.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if args.profile_boundaries and not self.buffered_output_written:
                self.buffered_output_written = True
                for row in self.rows:
                    print(json.dumps(row), flush=True)

    entry._capture_startup_launch_context = lambda: {"screenIndex": 0, "cursorX": 900, "cursorY": 500}
    entry.QApplication = NativeSpike
    if args.qt_render_timings or args.qt_layout_polish:
        original_qt_handler = entry._qt_message_handler
        def qt_stage_handler(mode, context, message):
            category = str(context.category or "")
            app = NativeSpike.instance()
            if category == "qt.quick.layouts":
                if app and app.qt_target_capture_pending and str(message).startswith("updatePolish()"):
                    app.qt_layout_rows.append({"cycle": app.completed, "t": time.perf_counter(),
                        "message": str(message), "scope": "Qt polish entry/exit; Python GIL and debug overhead"})
                return
            if category.startswith("qt.scenegraph.time"):
                if app and app.qt_target_capture_pending:
                    app.qt_timing_rows.append({"cycle": app.completed, "t": time.perf_counter(),
                        "category": category, "message": str(message),
                        "scope": "Qt stage timers; message delivery requires Python GIL"})
                return
            original_qt_handler(mode, context, message)
        entry._qt_message_handler = qt_stage_handler
    try:
        entry.main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            context["failures"].append("entry exit=" + str(exc.code))
    finally:
        app = NativeSpike.instance()
        if app:
            if not app.finished:
                app.complete()
            app.write_results()
        else:
            context["failures"].append("fixture integration: application exited before creating the diagnostic owner")
            (audit / "fixture_failure.json").write_text(json.dumps({"failures": context["failures"],
                "scope": "No diagnostic application owner; no transition or pixel qualification"}, indent=2), encoding="utf-8")
        after = hashes()
        (audit / "protected_hashes.json").write_text(json.dumps({"before": before, "after": after, "unchanged": before == after}, indent=2), encoding="utf-8")
        if before != after:
            raise RuntimeError("Protected production files changed")
        faulthandler.cancel_dump_traceback_later()
        stack_log.close()
    print(json.dumps({"audit": str(audit), "failures": context["failures"]}), flush=True)
    raise SystemExit(1 if context["failures"] else 0)


if __name__ == "__main__":
    main()
