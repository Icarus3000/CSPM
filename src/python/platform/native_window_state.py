"""Windows-owned maximize/restore underneath CSPM's client-drawn chrome.

The native frame exists for DWM's state transition contract only. Its painting
and non-client sizing stay suppressed; QML still draws every title-bar control.
Other CSPM transitions release this contract before changing the native host.
"""
import ctypes
import logging
import sys
import time
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QRect, Qt
from PySide6.QtGui import QGuiApplication, QRegion

log = logging.getLogger(__name__)
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
FRAME_STYLE = WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
WM_NCCALCSIZE = 0x0083
WM_NCPAINT = 0x0085
WM_NCACTIVATE = 0x0086
WM_GETMINMAXINFO = 0x0024
DWMWA_TRANSITIONS_FORCEDISABLED = 3


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT),
                ("showCmd", wintypes.UINT), ("ptMinPosition", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT), ("rcNormalPosition", wintypes.RECT)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class MINMAXINFO(ctypes.Structure):
    _fields_ = [("ptReserved", wintypes.POINT), ("ptMaxSize", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT), ("ptMinTrackSize", wintypes.POINT),
                ("ptMaxTrackSize", wintypes.POINT)]


def uses_native_window_state(window):
    return window is not None and bool(window.property("professionalNativeWindowState"))


def native_maximize_owns_monitor_move(window):
    # Restored windows retain CSPM's existing monitor/DPI movement pipeline.
    return uses_native_window_state(window) and bool(window.property("uiMaximized"))


def native_window_is_maximized(window):
    app = QGuiApplication.instance()
    event_filter = getattr(app, "_professional_native_frame_filter", None)
    session = event_filter.sessions.get(int(window.winId())) if event_filter and window else None
    return bool(session and session.user32.IsZoomed(session.hwnd))


class _NativeFrameFilter(QAbstractNativeEventFilter):
    def __init__(self):
        super().__init__()
        self.sessions = {}

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        session = self.sessions.get(int(msg.hWnd or 0))
        if session is None or not session.frame_enabled:
            return False, 0
        if msg.message == WM_NCCALCSIZE:
            if session.user32.IsZoomed(session.hwnd):
                monitor = session.user32.MonitorFromWindow(session.hwnd, 2)
                info = MONITORINFO(); info.cbSize = ctypes.sizeof(info)
                if monitor and session.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    # A maximized native frame extends beyond the monitor.
                    # Keep its client surface exactly inside the work area;
                    # the title bar remains entirely application-drawn.
                    rect = ctypes.cast(msg.lParam, ctypes.POINTER(wintypes.RECT)).contents
                    rect.left = max(rect.left, info.rcWork.left)
                    rect.top = max(rect.top, info.rcWork.top)
                    rect.right = min(rect.right, info.rcWork.right)
                    rect.bottom = min(rect.bottom, info.rcWork.bottom)
            return True, 0
        if msg.message == WM_NCPAINT:
            return True, 0
        if msg.message == WM_NCACTIVATE:
            return True, 1
        if msg.message == WM_GETMINMAXINFO:
            monitor = session.user32.MonitorFromWindow(session.hwnd, 2)
            info = MONITORINFO(); info.cbSize = ctypes.sizeof(info)
            if monitor and session.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                mm = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
                mm.ptMaxPosition.x = info.rcWork.left - info.rcMonitor.left
                mm.ptMaxPosition.y = info.rcWork.top - info.rcMonitor.top
                mm.ptMaxSize.x = info.rcWork.right - info.rcWork.left
                mm.ptMaxSize.y = info.rcWork.bottom - info.rcWork.top
                mm.ptMaxTrackSize = mm.ptMaxSize
                mm.ptMinTrackSize.x = max(1, session.window.minimumWidth())
                mm.ptMinTrackSize.y = max(1, session.window.minimumHeight())
                return True, 0
        return False, 0


class _NativeWindowSession(QObject):
    def __init__(self, window, event_filter):
        super().__init__(window)
        self.window = window
        self.hwnd = int(window.winId())
        self.frame_enabled = False
        self.original_flags = window.flags()
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        u = self.user32
        u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
        u.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.IsZoomed.argtypes = [wintypes.HWND]
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        self.original_frame_bits = int(u.GetWindowLongPtrW(self.hwnd, -16)) & FRAME_STYLE
        self.original_extended_bits = int(u.GetWindowLongPtrW(self.hwnd, -20)) & 0x00080100
        event_filter.sessions[self.hwnd] = self
        self.destroyed.connect(lambda: event_filter.sessions.pop(self.hwnd, None))
        for name in ("isClosingChanged", "isMinimizingChanged",
                     "isRestoringFromMinimizeChanged", "animationPhaseChanged"):
            signal = getattr(window, name, None)
            if signal is not None:
                signal.connect(self.release_for_custom_transition)

    def set_frame_enabled(self, enabled):
        if self.frame_enabled == enabled:
            return
        self.frame_enabled = enabled
        if enabled:
            # Qt's FramelessWindowHint uses MoveWindow rather than ShowWindow
            # and corrects native maximized geometry again in WM_SIZE. Declare
            # a real native frame, then suppress its visible NC area in our
            # filter. This keeps Qt and DWM on the same window-state contract.
            flags = (Qt.WindowType(int(self.original_flags) & ~int(Qt.FramelessWindowHint))
                     | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                     | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
            self.window.setFlags(flags)
        else:
            self.window.setFlags(self.original_flags)
        style = int(self.user32.GetWindowLongPtrW(self.hwnd, -16))
        bits = FRAME_STYLE if enabled else self.original_frame_bits
        self.user32.SetWindowLongPtrW(self.hwnd, -16, (style & ~FRAME_STYLE) | bits)
        # The settled shell is fully opaque. Keep the layered-opacity style
        # exclusively for the existing custom open/close/taskbar pipelines.
        exstyle = int(self.user32.GetWindowLongPtrW(self.hwnd, -20))
        exbits = 0 if enabled else self.original_extended_bits
        self.user32.SetWindowLongPtrW(self.hwnd, -20, (exstyle & ~0x00080100) | exbits)
        # Refresh non-client sizing without moving, activating, or changing Z order.
        # Discard copied client pixels when refreshing the frame; the Qt
        # scene must paint the surface at its current dimensions.
        self.user32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0137)

    def disable_dwm_transition(self, disabled):
        value = wintypes.BOOL(disabled)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(self.hwnd), DWMWA_TRANSITIONS_FORCEDISABLED,
            ctypes.byref(value), ctypes.sizeof(value))

    def release_for_custom_transition(self, *_args, force=False):
        w = self.window
        custom = (str(w.property("animationPhase")) != "settled"
                  or any(bool(w.property(name)) for name in
                         ("isClosing", "isMinimizing", "isRestoringFromMinimize")))
        if not (custom or force) or not self.frame_enabled:
            return
        w.setProperty("professionalNativeWindowState", False)
        # Retain the visible rectangle and QML's UI state while surrendering
        # native maximized state to the existing custom animation controller.
        geometry = QRect(w.geometry())
        self.disable_dwm_transition(True)
        try:
            if w.windowState() == Qt.WindowMaximized:
                w.setWindowState(Qt.WindowNoState)
                w.setGeometry(geometry)
            self.set_frame_enabled(False)
        finally:
            self.disable_dwm_transition(False)

    def request(self, maximized, restored_rect):
        started = time.perf_counter()
        w = self.window
        w.setProperty("professionalNativeWindowState", True)
        w.setMask(QRegion())
        self.set_frame_enabled(True)
        if not maximized and w.windowState() != Qt.WindowMaximized:
            # A maximized startup/taskbar return retains the approved custom
            # choreography. Adopt its already-visible state without animating.
            self.disable_dwm_transition(True)
            try:
                self.user32.ShowWindow(self.hwnd, 3)
            finally:
                self.disable_dwm_transition(False)
            self.seed_normal_placement(restored_rect)
        if maximized:
            w.showMaximized()
        else:
            w.showNormal()
        log.info("Professional native %s hwnd=%s zoomed=%s geometry=%s elapsedMs=%.1f",
                 "maximize" if maximized else "restore", self.hwnd,
                 bool(self.user32.IsZoomed(self.hwnd)), w.geometry(),
                 (time.perf_counter() - started) * 1000)
        return True

    def seed_normal_placement(self, restored_rect):
        if not isinstance(restored_rect, dict):
            return
        monitor = self.user32.MonitorFromWindow(self.hwnd, 2)
        info = MONITORINFO(); info.cbSize = ctypes.sizeof(info)
        if not monitor or not self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return
        # WINDOWPLACEMENT coordinates use the monitor workspace; the QML
        # rectangle uses Qt logical desktop coordinates. Convert at its DPR.
        dpr = float(self.window.devicePixelRatio())
        screen_rect = self.window.screen().geometry()
        x = info.rcMonitor.left + round((float(restored_rect["x"]) - screen_rect.x()) * dpr)
        y = info.rcMonitor.top + round((float(restored_rect["y"]) - screen_rect.y()) * dpr)
        x -= info.rcWork.left - info.rcMonitor.left
        y -= info.rcWork.top - info.rcMonitor.top
        width = max(1, round(float(restored_rect["w"]) * dpr))
        height = max(1, round(float(restored_rect["h"]) * dpr))
        placement = WINDOWPLACEMENT(); placement.length = ctypes.sizeof(placement)
        if self.user32.GetWindowPlacement(self.hwnd, ctypes.byref(placement)):
            placement.rcNormalPosition = wintypes.RECT(x, y, x + width, y + height)
            self.user32.SetWindowPlacement(self.hwnd, ctypes.byref(placement))


def request_native_window_state(window, maximized, restored_rect):
    if not sys.platform.startswith("win") or window is None:
        return False
    app = QGuiApplication.instance()
    if app is None or str(window.property("appStyle")) != "Professional":
        return False
    if str(window.property("animationPhase")) != "settled" or any(
            bool(window.property(name)) for name in
            ("isClosing", "isMinimizing", "isRestoringFromMinimize")):
        return False
    event_filter = getattr(app, "_professional_native_frame_filter", None)
    if event_filter is None:
        event_filter = _NativeFrameFilter()
        app.installNativeEventFilter(event_filter)
        app._professional_native_frame_filter = event_filter
    session = event_filter.sessions.get(int(window.winId()))
    if session is None:
        session = _NativeWindowSession(window, event_filter)
    return session.request(bool(maximized), restored_rect)
