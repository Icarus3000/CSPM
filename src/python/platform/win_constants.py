"""
Windows API constants and ctypes structures shared across platform modules.
Extracted from main.py. Only safe to import on sys.platform == "win32".
"""
import ctypes
from ctypes import wintypes

ULONG_PTR = ctypes.c_size_t
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
GA_ROOT = 2

VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEY_REPEAT_FLAG = 0x40000000
WIN_SHIFT_TARGET_WINDOW_NAMES = {"CSPMMainWindow", "CSPMFloatingDocketWindow"}


class _POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hWnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]
