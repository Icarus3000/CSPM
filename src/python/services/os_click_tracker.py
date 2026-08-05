from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

if sys.platform.startswith("win"):
    import ctypes
    from ctypes import wintypes

# Win32: GetCursorPos returns cursor position in screen coordinates.
# Win32: WH_MOUSE_LL hook requires a message loop.

WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207

WH_MOUSE_LL = 14
HC_ACTION = 0

if sys.platform.startswith("win"):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:
    user32 = None
    kernel32 = None

# wintypes.ULONG_PTR is not present on some Python builds; define safely.
if sys.platform.startswith("win"):
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


@dataclass
class ClickPoint:
    x: int
    y: int


def get_cursor_pos() -> ClickPoint:
    if not sys.platform.startswith("win"):
        return ClickPoint(0, 0)
    assert user32 is not None
    pt = wintypes.POINT()
    ok = user32.GetCursorPos(ctypes.byref(pt))
    if not ok:
        return ClickPoint(0, 0)
    return ClickPoint(int(pt.x), int(pt.y))


class OSClickTracker:
    def __init__(self, on_click):
        self.on_click = on_click
        self._hook = None
        self._thread = None
        self._stop_evt = threading.Event()
        self._proc_ref = None

    def start(self) -> None:
        if not sys.platform.startswith("win"):
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="OSClickTracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not sys.platform.startswith("win"):
            return
        assert user32 is not None
        self._stop_evt.set()
        try:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
        except Exception:
            pass
        self._hook = None

    def _run(self) -> None:
        assert user32 is not None
        assert kernel32 is not None
        active_user32 = user32
        active_kernel32 = kernel32
        LowLevelMouseProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", wintypes.POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        @LowLevelMouseProc
        def hook_proc(nCode, wParam, lParam):
            if nCode == HC_ACTION:
                msg = int(wParam)
                if msg in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN):
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    try:
                        self.on_click(int(ms.pt.x), int(ms.pt.y))
                    except Exception:
                        pass
            # Always pass to next hook unless intentionally blocking.
            return active_user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._proc_ref = hook_proc

        hmod = active_kernel32.GetModuleHandleW(None)
        self._hook = active_user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc, hmod, 0)
        if not self._hook:
            return

        msg = wintypes.MSG()
        PM_REMOVE = 0x0001
        while not self._stop_evt.is_set():
            while active_user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                active_user32.TranslateMessage(ctypes.byref(msg))
                active_user32.DispatchMessageW(ctypes.byref(msg))
            active_user32.Sleep(10)
