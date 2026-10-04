"""Passive bounded input-delivery tracing for one owned disposable window.

No key is injected, consumed, delayed or accepted by this helper. Native ingress,
Qt window delivery, activation state and GUI timer gaps are distinct evidence.
Rows stay in memory until stop(); importing this module does not load Qt.
"""
from __future__ import annotations

import math
import time


SCOPE = ("Passive owned disposable-window F24/activation observations and GUI "
         "heartbeat; no input injection, acceptance, physical latency or scanout proof")


class InputDeliveryTrace:
    def __init__(self, window, *, disposable=False, capacity=1024,
                 heartbeat_ms=25, clock=time.perf_counter, adapter=None):
        if disposable is not True:
            raise ValueError("Input trace requires an explicitly disposable fixture")
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("Input trace capacity must be an integer in 1..4096")
        if (type(heartbeat_ms) not in (int, float) or not math.isfinite(heartbeat_ms)
                or not 1 <= heartbeat_ms <= 1000):
            raise ValueError("Input trace heartbeat must be finite in 1..1000 ms")
        self.window, self.adapter, self.clock = window, adapter, clock
        self.capacity, self.heartbeat_ms = capacity, heartbeat_ms
        self.rows, self.dropped_rows, self.observation_errors = [], 0, 0
        self.started = self.closed = self.pending = False
        self.cycle, self.previous_heartbeat = None, None
        self.stop_result = None

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise RuntimeError("Input trace requires finite QPC seconds")
        return value

    def _append(self, kind, **values):
        if self.closed:
            return
        if len(self.rows) >= self.capacity:
            self.dropped_rows += 1
            return
        self.rows.append({"kind": kind, "t": self._now(), "cycle": self.cycle,
                          "witnessPending": self.pending, **values})

    def observe(self, kind, **values):
        # These callbacks run inside passive filters/signals. Reporting errors
        # must never affect the event's delivery or propagate into Qt.
        if kind == "trace-observation-error":
            self.observation_errors += 1
        try:
            self._append(kind, state=self.adapter.snapshot(self.window), **values)
        except Exception:
            self.observation_errors += 1

    def heartbeat(self):
        if self.closed or not self.pending:
            return
        try:
            now = self._now()
            gap = None if self.previous_heartbeat is None else (now - self.previous_heartbeat) * 1000
            self.previous_heartbeat = now
            self.observe("gui-heartbeat", gapMs=gap)
        except Exception:
            self.observation_errors += 1

    def start(self):
        if self.started or self.closed:
            raise RuntimeError("Input trace can start only once")
        self.started = True
        if self.adapter is None:
            self.adapter = _QtTraceAdapter()
        if not self.adapter.owns(self.window):
            raise RuntimeError("Input trace HWND is not owned by this fixture process")
        try:
            self.adapter.install(self.window, self.observe, self.heartbeat, self.heartbeat_ms)
            self.observe("trace-started")
        except Exception:
            self.stop()
            raise
        return self

    def set_pending(self, pending, *, cycle):
        if self.closed:
            return
        if not self.started or type(pending) is not bool:
            raise RuntimeError("Input trace pending state requires a started trace and boolean")
        self.cycle, self.pending = cycle, pending
        self.previous_heartbeat = self._now() if pending else None
        self.adapter.set_heartbeat(pending)
        self.observe("witness-pending-changed")

    def stop(self):
        if self.closed:
            return self.stop_result
        self.observe("trace-stopping") if self.started and self.adapter is not None else None
        self.closed, self.pending = True, False
        cleanup_errors = []
        if self.adapter is not None:
            try:
                cleanup_errors = self.adapter.dispose(self.window)
            except Exception:
                cleanup_errors = ["trace adapter cleanup failed"]
        self.stop_result = {"status": "COMPLETE" if not (
                cleanup_errors or self.observation_errors or self.dropped_rows) else "INCOMPLETE",
            "events": list(self.rows), "capacity": self.capacity,
            "droppedRows": self.dropped_rows, "observationErrors": self.observation_errors,
            "cleanupErrors": cleanup_errors, "heartbeatIntervalMs": self.heartbeat_ms,
            "scope": SCOPE}
        return self.stop_result


class _QtTraceAdapter:
    """Lazily install passive filters, with all observations scoped to one HWND."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        import os
        from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QObject, QTimer
        from PySide6.QtGui import QGuiApplication
        from shiboken6 import isValid
        self.ctypes, self.wintypes, self.pid = ctypes, wintypes, os.getpid()
        self.NativeFilter, self.QEvent, self.QObject, self.QTimer = QAbstractNativeEventFilter, QEvent, QObject, QTimer
        self.app, self.is_valid = QGuiApplication.instance(), isValid
        self.native_filter = self.qt_filter = self.timer = None
        self.connections = []
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user.GetForegroundWindow.argtypes, self.user.GetForegroundWindow.restype = [], wintypes.HWND
        self.user.GetFocus.argtypes, self.user.GetFocus.restype = [], wintypes.HWND
        self.user.GetActiveWindow.argtypes, self.user.GetActiveWindow.restype = [], wintypes.HWND
        self.user.IsWindowEnabled.argtypes, self.user.IsWindowEnabled.restype = [wintypes.HWND], wintypes.BOOL

    def owns(self, window):
        if not self.is_valid(window):
            return False
        process = self.wintypes.DWORD()
        thread = self.user.GetWindowThreadProcessId(int(window.winId()), self.ctypes.byref(process))
        return bool(thread) and process.value == self.pid

    def snapshot(self, window):
        if not self.is_valid(window):
            return {"ownedWindowAvailable": False}
        hwnd = int(window.winId())
        focus = window.activeFocusItem()
        return {"ownedWindowAvailable": True,
            "nativeForegroundOwned": int(self.user.GetForegroundWindow() or 0) == hwnd,
            "nativeFocusOwned": int(self.user.GetFocus() or 0) == hwnd,
            "nativeActiveOwned": int(self.user.GetActiveWindow() or 0) == hwnd,
            "nativeEnabled": bool(self.user.IsWindowEnabled(hwnd)),
            "qtActive": bool(window.isActive()),
            "applicationState": int(self.app.applicationState().value),
            "qtFocusWindowOwned": self.app.focusWindow() == window,
            "qtActiveFocusItemPresent": focus is not None,
            "qtFocusObjectIsActiveItem": focus is not None and self.app.focusObject() == focus}

    def install(self, window, observe, heartbeat, heartbeat_ms):
        adapter, hwnd = self, int(window.winId())
        native_kinds = {0x0006: "activate", 0x0007: "set-focus", 0x0008: "kill-focus",
                        0x000A: "enable", 0x0018: "show-window", 0x0086: "nc-activate"}

        class NativeFilter(self.NativeFilter):
            def nativeEventFilter(self, event_type, message):
                try:
                    if bytes(event_type) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                        return False, 0
                    msg = adapter.ctypes.cast(int(message), adapter.ctypes.POINTER(adapter.wintypes.MSG)).contents
                    if int(msg.hWnd or 0) != hwnd:
                        return False, 0
                    kind = native_kinds.get(int(msg.message))
                    if msg.message in (0x0100, 0x0101) and int(msg.wParam) == 0x87:
                        kind = "f24-press" if msg.message == 0x0100 else "f24-release"
                    if kind:
                        observe("native-ingress", messageKind=kind, messageId=int(msg.message),
                                messageTimeMs=int(msg.time))
                except Exception:
                    # An observational native filter must never consume input.
                    try:
                        observe("trace-observation-error", stage="native-filter")
                    except Exception:
                        pass
                return False, 0

        class WindowFilter(self.QObject):
            def eventFilter(self, watched, event):
                try:
                    if watched != window:
                        return False
                    kind = event.type()
                    if kind in (adapter.QEvent.KeyPress, adapter.QEvent.KeyRelease):
                        if event.key() == 0x01000047:
                            observe("qt-window-key", eventKind="press" if kind == adapter.QEvent.KeyPress else "release",
                                    autoRepeat=bool(event.isAutoRepeat()))
                    elif kind in (adapter.QEvent.FocusIn, adapter.QEvent.FocusOut,
                            adapter.QEvent.WindowActivate, adapter.QEvent.WindowDeactivate,
                            adapter.QEvent.EnabledChange, adapter.QEvent.Show, adapter.QEvent.Hide):
                        observe("qt-window-state-event", eventType=int(kind.value))
                except Exception:
                    try:
                        observe("trace-observation-error", stage="qt-window-filter")
                    except Exception:
                        pass
                return False

        self.native_filter, self.qt_filter = NativeFilter(), WindowFilter(window)
        self.app.installNativeEventFilter(self.native_filter)
        window.installEventFilter(self.qt_filter)
        self.timer = self.QTimer(window)
        self.timer.setInterval(math.ceil(heartbeat_ms))
        self.timer.timeout.connect(heartbeat)
        for signal, kind in ((window.activeChanged, "qt-active-changed"),
                (window.activeFocusItemChanged, "qt-active-focus-item-changed"),
                (self.app.applicationStateChanged, "qt-application-state-changed"),
                (self.app.focusWindowChanged, "qt-focus-window-changed"),
                (self.app.focusObjectChanged, "qt-focus-object-changed")):
            def callback(*_args, event_kind=kind):
                observe(event_kind)
            signal.connect(callback)
            self.connections.append((signal, callback))

    def set_heartbeat(self, enabled):
        if self.timer is not None and self.is_valid(self.timer):
            self.timer.start() if enabled else self.timer.stop()

    def dispose(self, window):
        errors = []
        operations = []
        if self.timer is not None and self.is_valid(self.timer):
            operations.extend((self.timer.stop, self.timer.deleteLater))
        if self.native_filter is not None:
            operations.append(lambda: self.app.removeNativeEventFilter(self.native_filter))
        if self.qt_filter is not None and self.is_valid(self.qt_filter):
            if self.is_valid(window):
                operations.append(lambda: window.removeEventFilter(self.qt_filter))
            operations.append(self.qt_filter.deleteLater)
        operations.extend(lambda signal=signal, callback=callback: signal.disconnect(callback)
                          for signal, callback in self.connections)
        for operation in operations:
            try:
                operation()
            except Exception:
                errors.append("owned trace cleanup operation failed")
        self.connections.clear()
        self.native_filter = self.qt_filter = self.timer = None
        return errors
