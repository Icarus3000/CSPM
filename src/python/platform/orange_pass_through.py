"""
_OutsideOrangePassThroughFilter — native event filter that makes the OS treat
pointer events outside the orange canvas rectangle as click-through (HTTRANSPARENT).

Extracted from main.py. Only active on Windows.
"""
import ctypes
from typing import Any, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PySide6.QtGui import QCursor

from platform.win_constants import (
    _KBDLLHOOKSTRUCT,  # noqa: F401 (re-exported for convenience)
    _MSG,
    _POINT,  # noqa: F401
    GA_ROOT,
    HTTRANSPARENT,
    WM_NCHITTEST,
)


class _OutsideOrangePassThroughFilter(QAbstractNativeEventFilter):
    """Pass mouse input to the OS outside the orange frame rectangle."""

    def __init__(self, main_window: Any) -> None:
        super().__init__()
        import time
        self._time = time
        self._main_window = main_window
        self._hwnd = int(main_window.winId()) if main_window is not None else 0
        self._user32 = ctypes.windll.user32
        self._cached_orange_rect: Optional[
            Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
        ] = None
        self._cached_orange_time = 0.0
        self._cached_recovery_rect: Optional[
            Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
        ] = None
        self._cached_recovery_time = 0.0
        try:
            from ctypes import wintypes
            self._user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            self._user32.GetAncestor.restype = wintypes.HWND
        except Exception:
            pass

    @staticmethod
    def _as_map(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    def _refresh_hwnd(self) -> None:
        if self._main_window is None:
            self._hwnd = 0
            return
        if QCoreApplication.closingDown():
            self._hwnd = 0
            return
        try:
            if bool(self._main_window.property("isClosing")) or bool(self._main_window.property("forceClose")):
                self._hwnd = 0
                return
        except Exception:
            pass
        try:
            is_visible_fn = getattr(self._main_window, "isVisible", None)
            if callable(is_visible_fn) and not bool(is_visible_fn()):
                self._hwnd = 0
                return
        except Exception:
            pass

        if self._hwnd > 0:
            return
        try:
            current = int(self._main_window.winId())
            self._hwnd = current if current > 0 else 0
        except Exception:
            self._hwnd = 0

    def shutdown(self) -> None:
        self._main_window = None
        self._hwnd = 0

    def _matches_hwnd(self, msg_hwnd: int) -> bool:
        if msg_hwnd <= 0 or self._hwnd <= 0:
            return False
        if msg_hwnd == self._hwnd:
            return True
        try:
            from ctypes import wintypes
            root_hwnd = int(self._user32.GetAncestor(wintypes.HWND(msg_hwnd), GA_ROOT))
        except Exception:
            root_hwnd = 0
        return root_hwnd == self._hwnd

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    def _inside_recovery_band(self, gx: int, gy: int) -> bool:
        if self._main_window is None:
            return False
            
        now = self._time.perf_counter()
        cached_rect = self._cached_recovery_rect
        if cached_rect is not None and (now - self._cached_recovery_time < 0.05):
            left, right, top, bottom = cached_rect
            if left is None or right is None or top is None or bottom is None:
                return False
            return left <= gx < right and top <= gy < bottom

        try:
            if not bool(self._main_window.property("recoveryBandEnabled")):
                self._cached_recovery_rect = (None, None, None, None)
                self._cached_recovery_time = now
                return False
        except Exception:
            self._cached_recovery_rect = (None, None, None, None)
            self._cached_recovery_time = now
            return False

        active = self._as_map(self._main_window.property("activeVisibleRect"))
        ax = self._as_int(active.get("x"), 0)
        ay = self._as_int(active.get("y"), 0)
        aw = max(1, self._as_int(active.get("w"), 1))
        ah = max(1, self._as_int(active.get("h"), 1))
        
        if aw <= 0 or ah <= 0:
            self._cached_recovery_rect = (None, None, None, None)
            self._cached_recovery_time = now
            return False

        band_h = max(1, self._as_int(self._main_window.property("recoveryBandHeight"), 1))
        left = ax
        top = ay
        right = left + aw
        bottom = top + band_h
        
        self._cached_recovery_rect = (left, right, top, bottom)
        self._cached_recovery_time = now
        
        return left <= gx < right and top <= gy < bottom

    def _inside_orange_rect(self, gx: int, gy: int) -> bool:
        if self._main_window is None:
            return True
            
        now = self._time.perf_counter()
        cached_rect = self._cached_orange_rect
        if cached_rect is not None and (now - self._cached_orange_time < 0.05):
            left, right, top, bottom = cached_rect
            if left is None or right is None or top is None or bottom is None:
                return True
            return left <= gx < right and top <= gy < bottom

        launch_configured = bool(self._main_window.property("launchConfigured"))
        if not launch_configured:
            self._cached_orange_rect = (None, None, None, None)
            self._cached_orange_time = now
            return True

        window_x = self._as_int(self._main_window.property("x"))
        window_y = self._as_int(self._main_window.property("y"))
        canvas_local_x = self._as_int(self._main_window.property("canvasLocalX"))
        canvas_local_y = self._as_int(self._main_window.property("canvasLocalY"))
        canvas_w = max(1, self._as_int(self._main_window.property("canvasW"), 1))
        canvas_h = max(1, self._as_int(self._main_window.property("canvasH"), 1))

        left = window_x + canvas_local_x
        top = window_y + canvas_local_y
        right = left + canvas_w
        bottom = top + canvas_h
        
        self._cached_orange_rect = (left, right, top, bottom)
        self._cached_orange_time = now
        
        return left <= gx < right and top <= gy < bottom

    def nativeEventFilter(self, event_type: Any, message: Any):  # type: ignore[override]
        self._refresh_hwnd()
        if self._hwnd == 0:
            return False, 0
        win = self._main_window
        if win is None:
            return False, 0

        # Keep full pointer ownership while user interacts with move/resize.
        # Pass-through during interaction causes choppy/jittery movement.
        try:
            if bool(win.property("userMoveInProgress")) or bool(
                win.property("userResizeInProgress")
            ):
                return False, 0
        except Exception:
            pass

        try:
            raw_type = bytes(event_type)
        except Exception:
            raw_type = str(event_type).encode("utf-8", errors="ignore")
        if raw_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0

        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
        except Exception:
            return False, 0

        msg_hwnd = int(msg.hWnd) if msg.hWnd else 0
        if msg.message != WM_NCHITTEST:
            return False, 0
        if not self._matches_hwnd(msg_hwnd):
            return False, 0

        cursor_pos = QCursor.pos()
        if self._inside_orange_rect(cursor_pos.x(), cursor_pos.y()) or self._inside_recovery_band(
            cursor_pos.x(), cursor_pos.y()
        ):
            return False, 0
        return True, HTTRANSPARENT
