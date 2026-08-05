"""
Win+Shift+Arrow monitor-move interception via two complementary mechanisms:

  _WinShiftArrowOverrideFilter — QAbstractNativeEventFilter (WM_KEYDOWN level).
  _WinShiftArrowLowLevelHook  — WH_KEYBOARD_LL hook (OS hook level, higher priority).

Both route the move to the active CSPM window via QML property dispatch instead of
letting the OS shell move the window natively.

Extracted from main.py. Only active on Windows.
"""
import ctypes
from collections import deque
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer
from PySide6.QtGui import QGuiApplication

from platform.win_constants import (
    _KBDLLHOOKSTRUCT,
    _MSG,
    HC_ACTION,
    KEY_REPEAT_FLAG,
    VK_CONTROL,
    VK_LEFT,
    VK_LWIN,
    VK_MENU,
    VK_RIGHT,
    VK_RWIN,
    VK_SHIFT,
    WIN_SHIFT_TARGET_WINDOW_NAMES,
    WH_KEYBOARD_LL,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
)


class _WinShiftArrowOverrideFilter(QAbstractNativeEventFilter):
    """Override Win+Shift+Arrow monitor move to use app-level geometry logic."""

    def __init__(self, main_window: Any) -> None:
        super().__init__()
        self._main_window = main_window
        self._queued_moves: deque[tuple[int, dict[str, int], Any]] = deque()
        self._dispatch_pending = False

    @staticmethod
    def _is_vk_down(vk_code: int) -> bool:
        try:
            return bool(ctypes.windll.user32.GetKeyState(vk_code) & 0x8000)
        except Exception:
            return False

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    @staticmethod
    def _as_map(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _window_object_name(window_obj: Any) -> str:
        if window_obj is None:
            return ""
        try:
            value = window_obj.objectName()
            if value is None:
                return ""
            return str(value)
        except Exception:
            return ""

    def _is_target_window(self, window_obj: Any) -> bool:
        return self._window_object_name(window_obj) in WIN_SHIFT_TARGET_WINDOW_NAMES

    @staticmethod
    def _window_has_property(window_obj: Any, property_name: str) -> bool:
        if window_obj is None:
            return False
        try:
            meta = window_obj.metaObject()
            if meta is None:
                return False
            return int(meta.indexOfProperty(property_name)) >= 0
        except Exception:
            return False

    def _resolve_target_window(self, preferred_window: Any | None = None) -> Any | None:
        if self._is_target_window(preferred_window):
            return preferred_window

        try:
            focused = QGuiApplication.focusWindow()
            if self._is_target_window(focused):
                return focused
        except Exception:
            pass

        try:
            active_window_fn = getattr(QGuiApplication, "activeWindow", None)
            if callable(active_window_fn):
                active = active_window_fn()
                if self._is_target_window(active):
                    return active
        except Exception:
            pass

        try:
            top_level_windows = list(QGuiApplication.topLevelWindows())
        except Exception:
            top_level_windows = []
        for window_obj in top_level_windows:
            if not self._is_target_window(window_obj):
                continue
            try:
                if bool(window_obj.isActive()):
                    return window_obj
            except Exception:
                pass

        if self._is_target_window(self._main_window):
            return self._main_window
        return preferred_window

    @staticmethod
    def _window_geometry(window_obj: Any) -> tuple[int, int, int, int]:
        if window_obj is None:
            return 0, 0, 1, 1
        try:
            gx = int(round(float(window_obj.x())))
        except Exception:
            gx = 0
        try:
            gy = int(round(float(window_obj.y())))
        except Exception:
            gy = 0
        try:
            gw = max(1, int(round(float(window_obj.width()))))
        except Exception:
            gw = 1
        try:
            gh = max(1, int(round(float(window_obj.height()))))
        except Exception:
            gh = 1
        return gx, gy, gw, gh

    def _capture_source_snapshot(self, target_window: Any | None = None) -> dict[str, int]:
        window_obj = target_window if target_window is not None else self._main_window
        if window_obj is None:
            return {
                "finalX": 0,
                "finalY": 0,
                "finalW": 1,
                "finalH": 1,
                "rectX": 0,
                "rectY": 0,
                "rectW": 1,
                "rectH": 1,
            }

        geo_x, geo_y, geo_w, geo_h = self._window_geometry(window_obj)
        final_x = self._as_int(window_obj.property("finalX"), geo_x)
        final_y = self._as_int(window_obj.property("finalY"), geo_y)
        final_w = max(1, self._as_int(window_obj.property("finalW"), geo_w))
        final_h = max(1, self._as_int(window_obj.property("finalH"), geo_h))

        active = self._as_map(window_obj.property("activeVisibleRect"))
        rect_x = self._as_int(active.get("x"), final_x)
        rect_y = self._as_int(active.get("y"), final_y)
        rect_w = self._as_int(active.get("w"), 0)
        rect_h = self._as_int(active.get("h"), 0)

        if rect_w <= 0 or rect_h <= 0:
            rect_x = self._as_int(window_obj.property("usableX"), final_x)
            rect_y = self._as_int(window_obj.property("usableY"), final_y)
            rect_w = self._as_int(window_obj.property("usableW"), 0)
            rect_h = self._as_int(window_obj.property("usableH"), 0)

        if rect_w <= 0 or rect_h <= 0:
            rect_x = final_x
            rect_y = final_y
            rect_w = final_w
            rect_h = final_h

        return {
            "finalX": final_x,
            "finalY": final_y,
            "finalW": final_w,
            "finalH": final_h,
            "rectX": rect_x,
            "rectY": rect_y,
            "rectW": max(1, rect_w),
            "rectH": max(1, rect_h),
        }

    def _dispatch_to_window(self, target_window: Any, direction: int, snapshot: dict[str, int]) -> None:
        if target_window is None:
            return

        supports_props = self._window_has_property(target_window, "osWinShiftMoveSeq")
        if supports_props:
            try:
                seq_raw = target_window.property("osWinShiftMoveSeq")
                seq = int(seq_raw) if seq_raw is not None else 0
            except Exception:
                seq = 0
            try:
                target_window.setProperty("osWinShiftSourceFinalX", int(snapshot.get("finalX", 0)))
                target_window.setProperty("osWinShiftSourceFinalY", int(snapshot.get("finalY", 0)))
                target_window.setProperty("osWinShiftSourceFinalW", int(snapshot.get("finalW", 1)))
                target_window.setProperty("osWinShiftSourceFinalH", int(snapshot.get("finalH", 1)))
                target_window.setProperty("osWinShiftSourceRectX", int(snapshot.get("rectX", 0)))
                target_window.setProperty("osWinShiftSourceRectY", int(snapshot.get("rectY", 0)))
                target_window.setProperty("osWinShiftSourceRectW", int(snapshot.get("rectW", 1)))
                target_window.setProperty("osWinShiftSourceRectH", int(snapshot.get("rectH", 1)))
                target_window.setProperty("osWinShiftMoveDirection", int(direction))
                target_window.setProperty("osWinShiftMoveSeq", seq + 1)
                return
            except Exception:
                pass

        invoke_fn = getattr(target_window, "requestAdjacentScreenMove", None)
        if callable(invoke_fn):
            try:
                invoke_fn(int(direction), "Win+Shift native override", snapshot)
            except Exception:
                pass

    def _queue_dispatch(self, direction: int, source_snapshot: dict[str, int], target_window: Any) -> None:
        self._queued_moves.append((-1 if direction < 0 else 1, source_snapshot, target_window))
        if self._dispatch_pending:
            return
        self._dispatch_pending = True
        QTimer.singleShot(0, self._dispatch_move_request)

    def _dispatch_move_request(self) -> None:
        self._dispatch_pending = False
        if self._main_window is None and not self._queued_moves:
            self._queued_moves.clear()
            return

        while self._queued_moves:
            direction, snapshot, preferred_window = self._queued_moves.popleft()
            target_window = self._resolve_target_window(preferred_window)
            if target_window is None:
                continue
            self._dispatch_to_window(target_window, direction, snapshot)

    def nativeEventFilter(self, event_type: Any, message: Any):  # type: ignore[override]
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

        if msg.message not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return False, 0

        vk = int(msg.wParam) if msg.wParam is not None else 0
        if vk not in (VK_LEFT, VK_RIGHT):
            return False, 0

        if not self._is_vk_down(VK_SHIFT):
            return False, 0
        if not (self._is_vk_down(VK_LWIN) or self._is_vk_down(VK_RWIN)):
            return False, 0
        if self._is_vk_down(VK_CONTROL) or self._is_vk_down(VK_MENU):
            return False, 0

        # Consume repeats to prevent rapid-fire monitor hops when key is held.
        lparam = int(msg.lParam) if msg.lParam is not None else 0
        if (lparam & KEY_REPEAT_FLAG) != 0:
            return True, 0

        direction = -1 if vk == VK_LEFT else 1
        target_window = self._resolve_target_window()
        source_snapshot = self._capture_source_snapshot(target_window)
        self._queue_dispatch(direction, source_snapshot, target_window)
        return True, 0


class _WinShiftArrowLowLevelHook(QObject):
    """Preempt Win+Shift+Arrow at OS hook level and route to app monitor-move logic."""

    def __init__(self, main_window: Any) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._hook = None
        self._dispatch_pending = False
        self._queued_moves: deque[tuple[int, dict[str, int], Any]] = deque()
        self._arrow_latch: dict[int, bool] = {VK_LEFT: False, VK_RIGHT: False}
        self._win_combo_armed = False
        self._armed_target_window: Any | None = None
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        from ctypes import wintypes
        self._proc_type = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self._proc = self._proc_type(self._keyboard_proc)
        self._user32.SetWindowsHookExW.argtypes = [ctypes.c_int, self._proc_type, wintypes.HINSTANCE, wintypes.DWORD]
        self._user32.SetWindowsHookExW.restype = wintypes.HANDLE
        self._user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self._user32.CallNextHookEx.restype = wintypes.LPARAM
        self._user32.GetForegroundWindow.argtypes = []
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        self._kernel32.GetLastError.restype = wintypes.DWORD

        module_handle = self._kernel32.GetModuleHandleW(None)
        self._hook = self._user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, module_handle, 0)
        if not self._hook:
            self._hook = self._user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)

    def uninstall(self) -> None:
        if self._hook:
            try:
                self._user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None

    @staticmethod
    def _is_vk_down(vk_code: int) -> bool:
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
        except Exception:
            return False

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    @staticmethod
    def _as_map(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _window_object_name(window_obj: Any) -> str:
        if window_obj is None:
            return ""
        try:
            value = window_obj.objectName()
            if value is None:
                return ""
            return str(value)
        except Exception:
            return ""

    def _is_target_window(self, window_obj: Any) -> bool:
        return self._window_object_name(window_obj) in WIN_SHIFT_TARGET_WINDOW_NAMES

    @staticmethod
    def _window_has_property(window_obj: Any, property_name: str) -> bool:
        if window_obj is None:
            return False
        try:
            meta = window_obj.metaObject()
            if meta is None:
                return False
            return int(meta.indexOfProperty(property_name)) >= 0
        except Exception:
            return False

    def _resolve_target_window(self, preferred_window: Any | None = None) -> Any | None:
        if self._is_target_window(preferred_window):
            return preferred_window

        try:
            focused = QGuiApplication.focusWindow()
            if self._is_target_window(focused):
                return focused
        except Exception:
            pass

        try:
            active_window_fn = getattr(QGuiApplication, "activeWindow", None)
            if callable(active_window_fn):
                active = active_window_fn()
                if self._is_target_window(active):
                    return active
        except Exception:
            pass

        try:
            top_level_windows = list(QGuiApplication.topLevelWindows())
        except Exception:
            top_level_windows = []
        for window_obj in top_level_windows:
            if not self._is_target_window(window_obj):
                continue
            try:
                if bool(window_obj.isActive()):
                    return window_obj
            except Exception:
                pass

        if self._is_target_window(self._main_window):
            return self._main_window
        return preferred_window

    @staticmethod
    def _window_geometry(window_obj: Any) -> tuple[int, int, int, int]:
        if window_obj is None:
            return 0, 0, 1, 1
        try:
            gx = int(round(float(window_obj.x())))
        except Exception:
            gx = 0
        try:
            gy = int(round(float(window_obj.y())))
        except Exception:
            gy = 0
        try:
            gw = max(1, int(round(float(window_obj.width()))))
        except Exception:
            gw = 1
        try:
            gh = max(1, int(round(float(window_obj.height()))))
        except Exception:
            gh = 1
        return gx, gy, gw, gh

    @staticmethod
    def _window_hwnd(window_obj: Any) -> int:
        if window_obj is None:
            return 0
        try:
            return int(window_obj.winId())
        except Exception:
            return 0

    def _capture_source_snapshot(self, target_window: Any | None = None) -> dict[str, int]:
        window_obj = target_window if target_window is not None else self._main_window
        if window_obj is None:
            return {
                "finalX": 0,
                "finalY": 0,
                "finalW": 1,
                "finalH": 1,
                "rectX": 0,
                "rectY": 0,
                "rectW": 1,
                "rectH": 1,
            }

        geo_x, geo_y, geo_w, geo_h = self._window_geometry(window_obj)
        final_x = self._as_int(window_obj.property("finalX"), geo_x)
        final_y = self._as_int(window_obj.property("finalY"), geo_y)
        final_w = max(1, self._as_int(window_obj.property("finalW"), geo_w))
        final_h = max(1, self._as_int(window_obj.property("finalH"), geo_h))

        active = self._as_map(window_obj.property("activeVisibleRect"))
        rect_x = self._as_int(active.get("x"), final_x)
        rect_y = self._as_int(active.get("y"), final_y)
        rect_w = self._as_int(active.get("w"), 0)
        rect_h = self._as_int(active.get("h"), 0)

        if rect_w <= 0 or rect_h <= 0:
            rect_x = self._as_int(window_obj.property("usableX"), final_x)
            rect_y = self._as_int(window_obj.property("usableY"), final_y)
            rect_w = self._as_int(window_obj.property("usableW"), 0)
            rect_h = self._as_int(window_obj.property("usableH"), 0)

        if rect_w <= 0 or rect_h <= 0:
            rect_x = final_x
            rect_y = final_y
            rect_w = final_w
            rect_h = final_h

        return {
            "finalX": final_x,
            "finalY": final_y,
            "finalW": final_w,
            "finalH": final_h,
            "rectX": rect_x,
            "rectY": rect_y,
            "rectW": max(1, rect_w),
            "rectH": max(1, rect_h),
        }

    def _should_intercept_combo(self) -> bool:
        if not self._is_vk_down(VK_SHIFT):
            return False
        if not (self._is_vk_down(VK_LWIN) or self._is_vk_down(VK_RWIN)):
            return False
        if self._is_vk_down(VK_CONTROL) or self._is_vk_down(VK_MENU):
            return False
        return True

    def _is_window_active(self) -> bool:
        target_window = self._resolve_target_window(self._armed_target_window)
        if target_window is None or not self._is_target_window(target_window):
            return False
        try:
            if not bool(target_window.isActive()):
                return False
        except Exception:
            return False
        target_hwnd = self._window_hwnd(target_window)
        if target_hwnd <= 0:
            return False
        try:
            foreground_hwnd = int(self._user32.GetForegroundWindow())
        except Exception:
            foreground_hwnd = 0
        if foreground_hwnd > 0 and foreground_hwnd != target_hwnd:
            return False
        return True

    def _dispatch_to_window(self, target_window: Any, direction: int, snapshot: dict[str, int]) -> None:
        if target_window is None:
            return

        supports_props = self._window_has_property(target_window, "osWinShiftMoveSeq")
        if supports_props:
            try:
                seq_raw = target_window.property("osWinShiftMoveSeq")
                seq = int(seq_raw) if seq_raw is not None else 0
            except Exception:
                seq = 0
            try:
                target_window.setProperty("osWinShiftSourceFinalX", int(snapshot.get("finalX", 0)))
                target_window.setProperty("osWinShiftSourceFinalY", int(snapshot.get("finalY", 0)))
                target_window.setProperty("osWinShiftSourceFinalW", int(snapshot.get("finalW", 1)))
                target_window.setProperty("osWinShiftSourceFinalH", int(snapshot.get("finalH", 1)))
                target_window.setProperty("osWinShiftSourceRectX", int(snapshot.get("rectX", 0)))
                target_window.setProperty("osWinShiftSourceRectY", int(snapshot.get("rectY", 0)))
                target_window.setProperty("osWinShiftSourceRectW", int(snapshot.get("rectW", 1)))
                target_window.setProperty("osWinShiftSourceRectH", int(snapshot.get("rectH", 1)))
                target_window.setProperty("osWinShiftMoveDirection", int(direction))
                target_window.setProperty("osWinShiftMoveSeq", seq + 1)
                return
            except Exception:
                pass

        invoke_fn = getattr(target_window, "requestAdjacentScreenMove", None)
        if callable(invoke_fn):
            try:
                invoke_fn(int(direction), "Win+Shift native override", snapshot)
            except Exception:
                pass

    def _queue_dispatch(self, direction: int, source_snapshot: dict[str, int], target_window: Any) -> None:
        self._queued_moves.append((-1 if direction < 0 else 1, source_snapshot, target_window))
        if self._dispatch_pending:
            return
        self._dispatch_pending = True
        QTimer.singleShot(0, self._dispatch_move_request)

    def _dispatch_move_request(self) -> None:
        self._dispatch_pending = False
        if self._main_window is None and not self._queued_moves:
            self._queued_moves.clear()
            return

        while self._queued_moves:
            direction, snapshot, preferred_window = self._queued_moves.popleft()
            target_window = self._resolve_target_window(preferred_window)
            if target_window is None:
                continue
            self._dispatch_to_window(target_window, direction, snapshot)

    def _keyboard_proc(self, n_code: int, w_param: Any, l_param: Any) -> int:
        if n_code != HC_ACTION:
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        msg = int(w_param)
        if msg not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        try:
            kb = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
        except Exception:
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        vk = int(kb.vkCode)
        if vk in (VK_LWIN, VK_RWIN):
            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if self._is_window_active():
                    self._armed_target_window = self._resolve_target_window()
                    self._win_combo_armed = self._armed_target_window is not None
                else:
                    self._armed_target_window = None
                    self._win_combo_armed = False
            else:
                self._win_combo_armed = False
                self._armed_target_window = None
                self._arrow_latch[VK_LEFT] = False
                self._arrow_latch[VK_RIGHT] = False
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        if vk not in (VK_LEFT, VK_RIGHT):
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        if msg in (WM_KEYUP, WM_SYSKEYUP):
            self._arrow_latch[vk] = False
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        if not self._is_window_active():
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        if not self._should_intercept_combo():
            self._arrow_latch[vk] = False
            return int(self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param))

        # If held, suppress repeat events to mirror non-autorepeat shortcut behavior.
        if self._arrow_latch.get(vk, False):
            return 1

        self._arrow_latch[vk] = True
        direction = -1 if vk == VK_LEFT else 1
        target_window = self._resolve_target_window(self._armed_target_window)
        source_snapshot = self._capture_source_snapshot(target_window)
        self._queue_dispatch(direction, source_snapshot, target_window)
        # Non-zero return prevents the OS shell Win+Shift monitor move for this app interaction.
        return 1
