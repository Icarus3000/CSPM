"""Ordinary CSPM adapter for the preserved native GPU transaction.

No collectors, external fixtures, pixel readbacks, alternate engines, or mutable
diagnostic selectors are imported. The bridge retains its 350/240/100 ms limits.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Property, Qt, QTimer, Signal, Slot
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from shiboken6 import isValid

from backend.motion_settings import read_mode, system_reduced_motion

log = logging.getLogger("motion")


def bridge_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "native" / "cspm_native_motion.dll"
    return Path(__file__).resolve().parents[3] / "outputs" / "native_cleanroom" / "cspm_native_motion.dll"


class NativeBridge:
    def __init__(self, path: Path):
        if sys.platform != "win32":
            raise OSError("Native GPU motion requires Windows D3D11")
        self.dll = ctypes.CDLL(str(path))
        pointer, uint, scalar = ctypes.c_void_p, ctypes.c_uint, ctypes.c_float
        signatures = {
            "cspm_comp_abi_version": ([], uint),
            "cspm_gpu_capture": ([pointer, ctypes.POINTER(uint), ctypes.POINTER(uint)], pointer),
            "cspm_gpu_release": ([pointer], None),
            "cspm_comp_create_from_frame_with_source_band": ([pointer, ctypes.c_size_t, *([ctypes.c_int] * 4)], pointer),
            "cspm_comp_defer_source_visibility": ([pointer], ctypes.c_int),
            "cspm_comp_transfer_source_visibility": ([pointer, ctypes.c_size_t], ctypes.c_int),
            "cspm_comp_raise_source_visibility": ([pointer], ctypes.c_int),
            "cspm_comp_set_source_frame": ([pointer, pointer, *([scalar] * 6)], ctypes.c_int),
            "cspm_comp_start": ([pointer, *([scalar] * 4), uint, uint], ctypes.c_int),
            "cspm_comp_set_target_frame": ([pointer, pointer], ctypes.c_int),
            "cspm_comp_status": ([pointer], uint),
            "cspm_comp_finish": ([pointer], ctypes.c_int),
            "cspm_comp_destroy": ([pointer], None),
            "cspm_comp_error": ([pointer, ctypes.c_char_p, uint], uint),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = arguments, result
        if self.dll.cspm_comp_abi_version() != 1:
            raise OSError("Native bridge ABI mismatch")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        for name, arguments, result in (
            ("GetClientRect", [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            ("ClientToScreen", [wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            ("IsWindowEnabled", [wintypes.HWND], wintypes.BOOL),
            ("IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
            ("EnableWindow", [wintypes.HWND, wintypes.BOOL], wintypes.BOOL),
            ("ShowWindow", [wintypes.HWND, ctypes.c_int], wintypes.BOOL),
            ("GetForegroundWindow", [], wintypes.HWND),
        ):
            function = getattr(self.user, name)
            function.argtypes, function.restype = arguments, result

    def error(self, host=None) -> str:
        buffer = ctypes.create_string_buffer(1024)
        self.dll.cspm_comp_error(host, buffer, len(buffer))
        return buffer.value.decode("utf-8", errors="replace")

    def client(self, window) -> list[int]:
        rectangle, origin = wintypes.RECT(), wintypes.POINT()
        hwnd = int(window.winId())
        if not self.user.GetClientRect(hwnd, ctypes.byref(rectangle)) or not self.user.ClientToScreen(hwnd, ctypes.byref(origin)):
            raise RuntimeError("Native client geometry unavailable")
        return [origin.x, origin.y, rectangle.right, rectangle.bottom]

    def require(self, accepted, host=None) -> None:
        if not accepted:
            raise RuntimeError(self.error(host) or "Native operation rejected")


class NativeMotion(QObject):
    targetRequested = Signal(QObject, int)
    finished = Signal(QObject, int, str)
    fallbackRequested = Signal(QObject, int, str)
    _captureReady = Signal(object, object)
    _cleanupReady = Signal(object, str)

    def __init__(self, parent=None, *, bridge_factory=NativeBridge):
        super().__init__(parent)
        self._mode = read_mode()
        self._system_reduced = system_reduced_motion()
        self._bridge: NativeBridge | None = None
        self._unavailable = ""
        self._transaction = None
        self._retiring = False
        if self._mode == "native" and not self._system_reduced:
            try:
                self._bridge = bridge_factory(bridge_path())
            except (OSError, AttributeError, RuntimeError) as exc:
                self._unavailable = type(exc).__name__
                log.warning("Native bridge unavailable; operations use legacy fallback (%s)", self._unavailable)
        self._captureReady.connect(self._captured, Qt.ConnectionType.QueuedConnection)
        self._cleanupReady.connect(self._cleanup_done, Qt.ConnectionType.QueuedConnection)

    def _require_bridge(self) -> NativeBridge:
        if self._bridge is None:
            raise RuntimeError("Native transaction has no owning bridge")
        return self._bridge

    @Property(str, constant=True)
    def engine(self):
        return self._mode

    @Property(bool, constant=True)
    def reducedMotion(self):
        return self._mode == "reduced" or self._system_reduced

    @Property(bool, constant=True)
    def layoutRepair(self):
        return self._mode == "native" and not self.reducedMotion

    @Property(bool, constant=True)
    def activationRepair(self):
        return True

    @Property(bool, constant=True)
    def available(self):
        return self._bridge is not None

    @Slot(str, str, str)
    def record(self, direction, used, reason):
        log.info("motion direction=%s requested=%s used=%s reason=%s", direction, self._mode, used, reason)

    @Slot(QObject, int, "QVariantMap", "QVariantMap", float, float, result=bool)
    def begin(self, window, sequence, source, target, header, right_fixed):
        direction = str(window.property("professionalWindowTransitionKind"))
        if self._bridge is None:
            self.record(direction, "legacy-fallback", "bridge-unavailable" if self._mode == "native" else "local-preference")
            return False
        if self._transaction is not None or self._retiring:
            self.record(direction, "legacy-fallback", "owned-transaction-or-cleanup-active")
            return False
        if not isinstance(window, QQuickWindow) or not window.isVisible() or window.opacity() != 1:
            self.record(direction, "legacy-fallback", "live-source-unavailable")
            return False
        try:
            physical = self._bridge.client(window)
            screen = window.screen()
            dpr = window.devicePixelRatio()
            # Windows monitor origins are already physical in Qt's virtual
            # desktop. Scale offsets within the screen, never desktop origins.
            screen_origin = screen.geometry().topLeft()
            goal = [round(screen_origin.x() + (target["x"] - screen_origin.x()) * dpr),
                    round(screen_origin.y() + (target["y"] - screen_origin.y()) * dpr),
                    round(target["w"] * dpr), round(target["h"] * dpr)]
            # The target host includes settled restored padding. QML supplies
            # it explicitly so the physical GPU extent must match exactly.
            if direction == "restore":
                padding = float(target.get("padding", 0))
                goal = [goal[0] - round(padding*dpr), goal[1] - round(padding*dpr),
                        goal[2] + 2*round(padding*dpr), goal[3] + 2*round(padding*dpr)]
            area = screen.availableGeometry()
            # Preserve the retained Home/taskbar pixel failures as unsupported
            # sources; refuse them before any host visibility or native motion.
            bounds = [screen_origin.x() + (area.x()-screen_origin.x())*dpr,
                      screen_origin.y() + (area.y()-screen_origin.y())*dpr,
                      area.width()*dpr, area.height()*dpr]
            if (physical[0] < bounds[0] or physical[1] < bounds[1]
                    or physical[0]+physical[2] > bounds[0]+bounds[2]
                    or physical[1]+physical[3] > bounds[1]+bounds[3]):
                raise RuntimeError("source-outside-monitor-work-area")
            if (goal[0] < bounds[0] or goal[1] < bounds[1]
                    or goal[0]+goal[2] > bounds[0]+bounds[2]
                    or goal[1]+goal[3] > bounds[1]+bounds[3]):
                raise RuntimeError("target-outside-source-monitor-work-area")
            if not self._bridge.user.IsWindowEnabled(int(window.winId())):
                raise RuntimeError("source-input-not-enabled")
            left, top = min(physical[0], goal[0])-32, min(physical[1], goal[1])-32
            envelope = [left, top, max(physical[0]+physical[2], goal[0]+goal[2])+32-left,
                        max(physical[1]+physical[3], goal[1]+goal[3])+32-top]
            transaction: dict[str, Any] = dict(window=window, sequence=sequence, direction=direction, source=physical,
                target=goal, envelope=envelope, host=None, header=header*dpr, right=right_fixed*dpr,
                input=None, started=False, visibility_transferred=False, pending=None, capture=False, frame_ready=False,
                foreground=int(self._bridge.user.GetForegroundWindow() or 0) == int(window.winId()),
                saved_focus=window.activeFocusItem(), cancelled=False, frames=[], lock=threading.Lock())
            self._transaction = transaction
            transaction["destroy_callback"] = lambda *_: self._window_destroyed(transaction)
            window.destroyed.connect(transaction["destroy_callback"])
            self._request_capture(transaction, "source")
            return True
        except Exception as exc:
            self._transaction = None
            self.record(direction, "legacy-fallback", str(exc))
            return False

    def _request_capture(self, transaction, kind):
        window = transaction["window"]
        transaction["pending"] = kind
        transaction["geometry"] = self._require_bridge().client(window)
        if not transaction["capture"]:
            transaction["callback"] = lambda: self._on_render(transaction)
            window.afterRenderPassRecording.connect(transaction["callback"], Qt.ConnectionType.DirectConnection)
            transaction["capture"] = True
        window.update()
        QTimer.singleShot(1800, lambda: self._capture_deadline(transaction, kind))

    def _capture_deadline(self, transaction, kind):
        if self._transaction is transaction and transaction["pending"] == kind:
            self._recover(transaction, "gpu-capture-timeout")

    def _on_render(self, transaction):
        # Render-thread callback owns its frame until delivery/cleanup. The
        # lock also prevents teardown releasing an in-flight native host.
        with transaction["lock"]:
            if transaction["cancelled"] or not transaction["pending"]:
                return
            kind, transaction["pending"] = transaction["pending"], None
            result = {"kind": kind}
            window, bridge = transaction["window"], self._require_bridge()
            try:
                renderer = window.rendererInterface()
                if renderer.graphicsApi() != QSGRendererInterface.GraphicsApi.Direct3D11:
                    raise RuntimeError("renderer-is-not-D3D11")
                window.beginExternalCommands()
                try:
                    context = renderer.getResource(window, QSGRendererInterface.Resource.DeviceContextResource)
                    if context is None or not int(context):
                        raise RuntimeError("D3D11-device-context-unavailable")
                    width, height = ctypes.c_uint(), ctypes.c_uint()
                    frame = bridge.dll.cspm_gpu_capture(int(context), ctypes.byref(width), ctypes.byref(height))
                    bridge.require(frame)
                    transaction["frames"].append(frame)
                    result.update(frame=frame, size=[width.value, height.value])
                    expected = transaction["source" if kind == "source" else "target"]
                    if result["size"] != expected[2:]:
                        raise RuntimeError("GPU-frame-extent-mismatch")
                finally:
                    window.endExternalCommands()
                if kind == "target":
                    bridge.require(bridge.dll.cspm_comp_set_target_frame(transaction["host"], frame), transaction["host"])
            except Exception as exc:
                result["error"] = str(exc)
            self._captureReady.emit(transaction, result)

    @Slot(object, object)
    def _captured(self, transaction, result):
        if self._transaction is not transaction or transaction["cancelled"]:
            return
        window, bridge = transaction["window"], self._require_bridge()
        if result.get("error"):
            self._recover(transaction, result["error"])
            return
        try:
            if result["kind"] == "source":
                if bridge.client(window) != transaction["source"]:
                    raise RuntimeError("source-changed-during-capture")
                source, target, envelope = transaction["source"], transaction["target"], transaction["envelope"]
                dll = bridge.dll
                host = dll.cspm_comp_create_from_frame_with_source_band(result["frame"], int(window.winId()), *envelope)
                transaction["host"] = host
                bridge.require(host)
                bridge.require(dll.cspm_comp_defer_source_visibility(host), host)
                pad_y = max(0, (source[3]-window.property("finalH")*window.devicePixelRatio())/2)
                pad_x = max(0, (source[2]-window.property("finalW")*window.devicePixelRatio())/2)
                bridge.require(dll.cspm_comp_set_source_frame(host, result["frame"],
                    source[0]-envelope[0], source[1]-envelope[1], source[2], source[3],
                    transaction["header"]+pad_y, transaction["right"]+pad_x), host)
                transaction["input"] = bool(bridge.user.IsWindowEnabled(int(window.winId())))
                window.setProperty("professionalWindowTransitionActive", True)
                bridge.user.EnableWindow(int(window.winId()), False)
                # Mark recovery ownership before calling the potentially
                # partial visibility transfer, exactly as the audited adapter.
                transaction["visibility_transferred"] = True
                bridge.require(dll.cspm_comp_transfer_source_visibility(host, int(window.winId())), host)
                window.setOpacity(0)
                window.show()
                if not bridge.user.IsWindowVisible(int(window.winId())):
                    bridge.user.ShowWindow(int(window.winId()), 4)  # SW_SHOWNOACTIVATE, owned source only.
                if not bridge.user.IsWindowVisible(int(window.winId())):
                    raise RuntimeError("hidden-live-rendering-unavailable")
                if bridge.client(window) != source:
                    raise RuntimeError("source-transfer-changed-geometry")
                bridge.require(dll.cspm_comp_raise_source_visibility(host), host)
                bridge.require(dll.cspm_comp_start(host, target[0]-envelope[0], target[1]-envelope[1],
                    target[2], target[3], 350, 240), host)
                transaction["started"] = True
                transaction["begin_time"] = time.monotonic()
                self.targetRequested.emit(window, transaction["sequence"])
                self._poll(transaction)
            else:
                transaction["frame_ready"] = True
        except Exception as exc:
            self._recover(transaction, str(exc))

    @Slot(QObject, int)
    def captureTarget(self, window, sequence):
        transaction = self._transaction
        if transaction is None or transaction["window"] is not window or transaction["sequence"] != sequence:
            return
        try:
            if self._require_bridge().client(window) != transaction["target"]:
                raise RuntimeError("target-native-client-mismatch")
            self._request_capture(transaction, "target")
        except Exception as exc:
            self._recover(transaction, str(exc))

    def _poll(self, transaction):
        if self._transaction is not transaction or transaction["cancelled"]:
            return
        status = self._require_bridge().dll.cspm_comp_status(transaction["host"])
        if status & 16:
            self._recover(transaction, self._require_bridge().error(transaction["host"]))
        elif status & 4:
            window = transaction["window"]
            callback = lambda: self._live_ready(transaction)
            transaction["live_callback"] = callback
            window.frameSwapped.connect(callback, Qt.ConnectionType.QueuedConnection)
            window.setOpacity(1)
            window.update()
            QTimer.singleShot(750, lambda: self._recover(transaction, "live-handoff-frame-timeout")
                if self._transaction is transaction and not transaction["cancelled"] else None)
        elif time.monotonic()-transaction["begin_time"] > 1.5:
            self._recover(transaction, "native-endpoint-timeout")
        else:
            QTimer.singleShot(8, lambda: self._poll(transaction))

    def _live_ready(self, transaction):
        if self._transaction is transaction and not transaction["cancelled"]:
            try:
                bridge = self._require_bridge()
                bridge.require(bridge.dll.cspm_comp_finish(transaction["host"]), transaction["host"])
                self.record(transaction["direction"], "native", "endpoint-submitted-and-live-frame-returned")
                self._release(transaction, "native")
            except Exception as exc:
                self._recover(transaction, str(exc))

    def _recover(self, transaction, reason):
        if self._transaction is not transaction or transaction["cancelled"]:
            return
        transferred = transaction["visibility_transferred"]
        self.record(transaction["direction"],
                    "post-transfer-failure" if transferred else "pre-motion-rejection", reason)
        # A partially accepted transfer must recover directly to the target,
        # even if native start itself failed. Never capture it as a new source.
        self._release(transaction, "safe-rejection" if transferred else "legacy-fallback")

    def _window_destroyed(self, transaction):
        if self._transaction is transaction and not transaction["cancelled"]:
            self._release(transaction, "safe-rejection")

    @Slot()
    def shutdown(self):
        if self._transaction is not None:
            self._release(self._transaction, "safe-rejection")

    @Slot(QObject)
    def cancelWindow(self, window):
        if self._transaction is not None and self._transaction["window"] is window:
            self.record(self._transaction["direction"], "safe-rejection", "window-lifecycle-cancellation")
            self._release(self._transaction, "safe-rejection")

    def _release(self, transaction, outcome):
        # GUI state recovery precedes bounded native teardown. A worker owns
        # every native pointer through teardown; new operations fall back while
        # retirement is pending. Never retry native destruction after timeout.
        transaction["cancelled"] = True
        window = transaction["window"]
        bridge = self._require_bridge()
        if isValid(window):
            if transaction.get("destroy_callback"):
                window.destroyed.disconnect(transaction["destroy_callback"])
            if transaction.get("capture"):
                window.afterRenderPassRecording.disconnect(transaction["callback"])
            if transaction.get("live_callback"):
                window.frameSwapped.disconnect(transaction["live_callback"])
            window.setOpacity(1)
            window.show()
            if not bridge.user.IsWindowVisible(int(window.winId())):
                bridge.user.ShowWindow(int(window.winId()), 4)
            if transaction["input"] is not None:
                bridge.user.EnableWindow(int(window.winId()), transaction["input"])
            visible = bool(bridge.user.IsWindowVisible(int(window.winId())))
            input_restored = (transaction["input"] is None or
                              bool(bridge.user.IsWindowEnabled(int(window.winId()))) == transaction["input"])
            log.log(logging.INFO if visible and input_restored else logging.ERROR,
                    "motion live-return outcome=%s visibility_transferred=%s motion_started=%s "
                    "visible=%s input_restored=%s recovery=%s", outcome,
                    transaction["visibility_transferred"], transaction["started"],
                    visible, input_restored, "passed" if visible and input_restored else "FAILED")
            if transaction["foreground"] and int(bridge.user.GetForegroundWindow() or 0) == int(window.winId()):
                window.requestActivate()
                focus = transaction["saved_focus"]
                if focus is not None and isValid(focus):
                    focus.forceActiveFocus()
        self._retiring = True
        self._transaction = None

        def retire():
            with transaction["lock"]:
                if transaction["host"]:
                    bridge.dll.cspm_comp_destroy(transaction["host"])
                for frame in transaction["frames"]:
                    bridge.dll.cspm_gpu_release(frame)
                transaction["frames"].clear()
            if isValid(self):
                self._cleanupReady.emit(transaction, outcome)

        # Keep the Python runtime alive until owned native teardown finishes.
        worker = threading.Thread(target=retire, name="CSPM-native-motion-cleanup", daemon=False)
        worker.start()

    @Slot(object, str)
    def _cleanup_done(self, transaction, outcome):
        self._retiring = False
        window = transaction["window"]
        if isValid(window):
            if outcome == "legacy-fallback":
                self.fallbackRequested.emit(window, transaction["sequence"], "source-preparation-rejected")
            else:
                self.finished.emit(window, transaction["sequence"], outcome)
