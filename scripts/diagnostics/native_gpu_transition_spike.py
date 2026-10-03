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
from functools import wraps


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
    args = parser.parse_args()
    if not args.audit_label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.audit_label):
        parser.error("audit label must use letters, numbers, underscore or hyphen")
    if not 1 <= args.cycles <= 12 or not 0 <= args.gui_delay_ms <= 1000 or not 100 <= args.duration_ms <= 1000 or not 0 < args.blend_start_ms < args.duration_ms:
        parser.error("bounded cycles/delay/duration/transfer deadline required")
    if not 0 <= args.endpoint_hold_ms <= 300:
        parser.error("diagnostic endpoint hold must be between 0 and 300 ms")
    root = Path(__file__).resolve().parents[2]
    audit = root / "logs" / args.audit_label
    audit.mkdir(parents=True, exist_ok=False)
    provenance_paths = (
        "scripts/diagnostics/native_gpu_transition_spike.py",
        "scripts/diagnostics/window_transition_probe.py",
        "scripts/build_cleanroom_native.ps1",
        "src/native/cleanroom_composition/cleanroom_composition.cpp",
        "src/python/main.py",
        "src/python/backend/transition_experiment.py",
        "src/qml/DetachedShellWindow.qml",
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
    os.environ["CSPM_MACHINE_ID_FILE"] = str(audit / "disposable_profile/machine_id.json")
    os.environ["CSPM_EXPERIMENTAL_TRANSITION"] = "production"
    probe = root / "scripts/diagnostics/window_transition_probe.py"
    source = probe.read_text(encoding="utf-8")
    source = source[:source.index("\nentry._capture_startup_launch_context = diagnostic_launch_context")]
    source = source.replace('AUDIT = ROOT / "logs/window_transition_diagnostic"', "AUDIT = Path(" + repr(str(audit)) + ")")
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
    sys.path.insert(0, str(probe.parent))
    context = {"__file__": str(probe), "__name__": "native_gpu_fixture"}
    exec(compile(source, str(probe), "exec"), context)
    entry, base = context["entry"], context["ProbeApplication"]
    from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QSGRendererInterface
    from shiboken6 import isValid

    if mirror is not None:
        class ProfileEngine(QQmlApplicationEngine):
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
            self.capture_signal = None
            self.started_native = None
            self.current = None
            self.finished = False
            self.completed = 0
            self.desktop_camera = None
            self.source_desktop = None
            self.target_desktop = None
            self.boundary_rows = []
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
            self.capture_signal = Captured(self)
            self.capture_signal.ready.connect(self.captured, Qt.QueuedConnection)
            self.window.afterRenderPassRecording.connect(self.on_render, Qt.DirectConnection)
            self.normal = {name: self.window.property(name) for name in ("finalX", "finalY", "finalW", "finalH")}
            self.normal_client = client(self.window)
            if args.endpoint_pixels:
                dependencies = os.environ.get("CSPM_PIXEL_DEPENDENCIES")
                if dependencies:
                    sys.path.insert(0, dependencies)
                import dxcam
                self.desktop_camera = dxcam.create(device_idx=0, output_idx=0,
                    output_color="BGRA", processor_backend="numpy", max_buffer_len=2)
            super().begin_cycles()

        def request_capture(self, kind):
            self.capture_request = {"kind": kind, "requested": time.perf_counter(), "client": client(self.window)}
            requested = self.capture_request
            self.window.update()
            QTimer.singleShot(1800, lambda: self.capture_deadline(requested))

        def capture_deadline(self, requested):
            if not self.finished and self.capture_request is requested:
                self.fail("native texture access", "No main render callback within 1800 ms")

        def on_render(self):
            request = self.capture_request
            if request is None:
                return
            self.capture_request = None
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
                    result.update(frame=frame, size=[width.value, height.value], gpuOnly=True)
                finally:
                    self.window.endExternalCommands()
            except Exception as exc:
                result["error"] = str(exc)
            result["captureFinished"] = time.perf_counter()
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
            kind = "maximize" if self.completed % 2 == 0 else "restore"
            self.current = {"kind": kind, "command": time.perf_counter(), "sourceClient": client(self.window)}
            self.tracker.command("native-" + kind)
            self.record("command", kind=kind)
            self.source_desktop = self.desktop_pixels(self.current["sourceClient"])
            self.request_capture("source")

        def desktop_pixels(self, rectangle):
            if self.desktop_camera is None:
                return None
            x, y, width, height = rectangle
            # This measurement fixture uses only output 0; negative/mixed-DPI
            # physical acceptance is not claimed from this single-display crop.
            if x < 0 or y < 0 or x + width > 1920 or y + height > 1080:
                raise RuntimeError("Endpoint measurement crop exceeds output 0")
            pixels = self.desktop_camera.grab(region=(x, y, x + width, y + height), new_frame_only=False)
            if pixels is None:
                raise RuntimeError("DXGI endpoint measurement unavailable")
            return pixels.copy()

        def compare_pixels(self, name, old, new):
            if old is None or new is None:
                self.record(name, status="UNMEASURED")
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
                if result.get("frame"):
                    dll.cspm_gpu_release(result["frame"])
                return
            self.record("gpu-capture", **{key: value for key, value in result.items() if key != "frame"})
            if result.get("error"):
                self.fail("native texture access", result["error"])
                return
            self.frames.append(result["frame"])
            if result["kind"] == "target":
                self.finish_target_profile()
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
                header = self.evaluate("_probeWindow.mainContentRef.professionalTransitionHeaderMetrics()").toVariant()
                pad_y = max(0, (physical[3] - self.window.property("finalH") * dpr) / 2)
                header_height = pad_y + header.x() * dpr
                right_fixed = header.y() * dpr + max(0, (physical[2] - self.window.property("finalW") * dpr) / 2)
                if not dll.cspm_comp_set_source_frame(self.host, result["frame"], physical[0] - left, physical[1] - top, physical[2], physical[3], header_height, right_fixed):
                    self.fail("DirectComposition presentation", native_error(self.host))
                    return
                self.record("source-composition-committed", source=physical, target=target, envelope=self.envelope)
                QTimer.singleShot(70, self.after_source_coverage)
            else:
                if result["client"] != self.target_client:
                    self.record("physical-target-plan-mismatch", planned=self.target_client, actual=result["client"])
                    self.fail("physical-pixel mapping", "Actual target native client differs from predetermined endpoint")
                    return
                if not dll.cspm_comp_set_target_frame(self.host, result["frame"]):
                    self.fail("target readiness", native_error(self.host))
                    return
                self.record("target-gpu-composition-committed", elapsedMs=dll.cspm_comp_elapsed_ms(self.host))
                if args.prepared_target:
                    self.start_native()
                else:
                    self.poll_native()

        @guarded
        def after_source_coverage(self):
            self.window.setOpacity(0)
            QTimer.singleShot(35, self.after_source_hidden)

        @guarded
        def after_source_hidden(self):
            self.compare_pixels("source-live-to-gpu-pixels", self.source_desktop,
                self.desktop_pixels(self.current["sourceClient"]))
            if args.prepared_target:
                self.prepare_live_target()
            else:
                self.start_native()

        @guarded
        def start_native(self):
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
            self.begin_target_profile()
            self.record("layout-begin")
            self.evaluate("_probeWindow.geometryTransitionSuppressed = true; _probeWindow.commitProfessionalWindowTransitionTarget(" + kind + ", " + goal + ", _probeWindow.screen)")
            self.record("layout-committed", actualClient=client(self.window))
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
                    diagnosticHoldMs=args.endpoint_hold_ms, presentation=self.presentation_telemetry())
                QTimer.singleShot(args.endpoint_hold_ms, self.measure_endpoint)
            else:
                QTimer.singleShot(8, self.poll_native)

        @guarded
        def measure_endpoint(self):
            self.record("desktop-endpoint-measurement", elapsedMs=dll.cspm_comp_elapsed_ms(self.host),
                presentation=self.presentation_telemetry())
            self.target_desktop = self.desktop_pixels(self.target_client)
            self.window.setOpacity(1)
            self.record("live-host-revealed")
            self.window.update()
            QTimer.singleShot(100, self.handoff)

        @guarded
        def handoff(self):
            if self.finished:
                return
            if not dll.cspm_comp_finish(self.host):
                self.fail("live-HWND handoff", native_error(self.host))
                return
            QTimer.singleShot(40, self.handoff_compare)

        @guarded
        def handoff_compare(self):
            if self.finished:
                return
            self.record("live-handoff", actualClient=client(self.window),
                commandToLiveMs=(time.perf_counter() - self.current["command"]) * 1000)
            self.compare_pixels("gpu-to-live-target-pixels", self.target_desktop,
                self.desktop_pixels(self.target_client))
            dll.cspm_comp_destroy(self.host)
            self.host = None
            for frame in self.frames:
                dll.cspm_gpu_release(frame)
            self.frames.clear()
            self.evaluate("_probeWindow.geometryTransitionSuppressed = false; _probeWindow.updateCanvasGeometry()")
            self.completed += 1
            QTimer.singleShot(200, self.step)

        def fail(self, category, error):
            context["failures"].append(category + ": " + error)
            self.record("qualification-failure", category=category, error=error)
            self.complete()

        def timeout(self):
            self.fail("fixture deadline", "Populated spike exceeded 120 seconds")

        def complete(self):
            if self.finished:
                return
            self.finished = True
            self.capture_request = None
            if self.profile_armed:
                try:
                    self.finish_target_profile()
                except Exception as exc:
                    self.profile_armed = False
                    self.boundary_rows.append({"boundary": "profile-collection-error",
                        "cycle": self.profile_cycle, "t": time.perf_counter(), "error": str(exc)})
            if self.window is not None and isValid(self.window):
                self.window.setOpacity(1)
            if self.host:
                dll.cspm_comp_destroy(self.host)
                self.host = None
            for frame in self.frames:
                dll.cspm_gpu_release(frame)
            self.frames.clear()
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
                "profileScope": ("QML statements are millisecond wall-clock observations calibrated per cycle. "
                    "Qt adoption/render signals are one-shot Python callbacks that require the GIL. "
                    "Render observations may span frames while target commit/capture is pending; "
                    "they do not isolate pure Qt work, GPU completion, WebEngine readiness or scanout. "
                    "Profiling buffers fixture event printing until results are written."
                    if args.profile_boundaries else "not enabled"),
                "completedCycles": self.completed, "failures": context["failures"],
                "measurementScope": "GPU transfer and native status; physical geometry needs separate collector analysis",
                "coldCandidateQualification": "NOT QUALIFYING" if args.prepared_target or args.capture_only else "FAIL" if context["failures"] else "REQUIRES ALL PHYSICAL GATES",
                "presentationCpuReadbacks": 0, "presentationCpuUploads": 0}
            (audit / "native_gpu_spike.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if args.profile_boundaries and not self.buffered_output_written:
                self.buffered_output_written = True
                for row in self.rows:
                    print(json.dumps(row), flush=True)

    entry._capture_startup_launch_context = lambda: {"screenIndex": 0, "cursorX": 900, "cursorY": 500}
    entry.QApplication = NativeSpike
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
        after = hashes()
        (audit / "protected_hashes.json").write_text(json.dumps({"before": before, "after": after, "unchanged": before == after}, indent=2), encoding="utf-8")
        if before != after:
            raise RuntimeError("Protected production files changed")
    print(json.dumps({"audit": str(audit), "failures": context["failures"]}), flush=True)
    raise SystemExit(1 if context["failures"] else 0)


if __name__ == "__main__":
    main()
