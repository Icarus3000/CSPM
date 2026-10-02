"""Sandbox-safe placement and custom-animation isolation tests (no HWND)."""
import ctypes
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QRect, Qt

spec = importlib.util.spec_from_file_location(
    "cspm_native_state_test", Path(__file__).resolve().parents[1]
    / "src/python/platform/native_window_state.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def session_for(window):
    session = native._NativeWindowSession.__new__(native._NativeWindowSession)
    QObject.__init__(session)
    session.window = window
    session.hwnd = 123
    session.frame_enabled = True
    return session


def test_repeated_native_frame_preparation_does_not_change_flags_or_refresh_geometry():
    session = session_for(SimpleNamespace())
    # A real frame setup would access flags/HWND methods. With an active
    # session, the second maximize/restore must leave those untouched.
    session.set_frame_enabled(True)
    assert session.frame_enabled is True


@pytest.mark.parametrize("owner, maximized, expected", [
    (False, False, False), (False, True, False),
    (True, False, False), (True, True, True),
])
def test_restored_window_monitor_shortcuts_keep_the_existing_dpi_pipeline(owner, maximized, expected):
    values = {"professionalNativeWindowState": owner, "uiMaximized": maximized}
    window = SimpleNamespace(property=lambda key: values.get(key))
    assert native.native_maximize_owns_monitor_move(window) is expected


def test_restored_interaction_returns_geometry_ownership_without_a_window_state_change():
    properties = {"animationPhase": "settled", "professionalNativeWindowState": True}
    operations = []
    window = SimpleNamespace(
        property=lambda key: properties.get(key),
        setProperty=lambda key, value: properties.update({key: value}),
        geometry=lambda: QRect(-1500, 80, 900, 650),
        windowState=lambda: Qt.WindowNoState,
        setWindowState=lambda state: operations.append(("state", state)),
        setGeometry=lambda rect: operations.append(("geometry", rect)),
    )
    session = session_for(window)
    session.disable_dwm_transition = lambda disabled: operations.append(("dwm-disabled", disabled))
    session.set_frame_enabled = lambda enabled: operations.append(("frame", enabled))
    session.release_for_custom_transition(force=True)
    assert properties["professionalNativeWindowState"] is False
    assert operations == [("dwm-disabled", True), ("frame", False),
                          ("geometry", QRect(-1500, 80, 900, 650)), ("dwm-disabled", False)]
    assert properties["professionalNativeGeometrySyncInProgress"] is False


@pytest.mark.parametrize("flag", ["isClosing", "isMinimizing", "isRestoringFromMinimize"])
def test_custom_transition_releases_native_state_without_moving_the_visible_window(flag):
    properties = {"animationPhase": "settled", flag: True, "professionalNativeWindowState": True}
    geometry = QRect(1920, 1, 1920, 1040)
    operations = []
    window = SimpleNamespace(
        property=lambda key: properties.get(key),
        setProperty=lambda key, value: properties.update({key: value}),
        geometry=lambda: geometry,
        windowState=lambda: Qt.WindowMaximized,
        setWindowState=lambda state: operations.append(("state", state)),
        setGeometry=lambda rect: operations.append(("geometry", rect)),
    )
    session = session_for(window)
    session.disable_dwm_transition = lambda disabled: operations.append(("dwm-disabled", disabled))
    session.set_frame_enabled = lambda enabled: operations.append(("frame", enabled))
    session.release_for_custom_transition()
    assert properties["professionalNativeWindowState"] is False
    assert operations == [("dwm-disabled", True), ("state", Qt.WindowNoState),
                          ("frame", False), ("geometry", geometry), ("dwm-disabled", False)]


def test_geometry_bindings_are_suspended_until_custom_frame_and_bounds_are_restored():
    properties = {"animationPhase": "settled", "professionalNativeWindowState": True}
    bounds = [QRect(400, 200, 1100, 760)]
    window = SimpleNamespace(property=lambda key: properties.get(key),
                             setProperty=lambda key, value: properties.update({key: value}),
                             geometry=lambda: bounds[0], windowState=lambda: Qt.WindowNoState,
                             setGeometry=lambda rect: bounds.__setitem__(0, rect))
    session = session_for(window)
    session.disable_dwm_transition = lambda _: None

    def frame_change(_):
        assert properties["professionalNativeWindowState"] is True
        assert properties["professionalNativeGeometrySyncInProgress"] is True
        bounds[0] = QRect(392, 169, 1116, 799)  # Native frame margin change.

    session.set_frame_enabled = frame_change
    session.release_for_custom_transition(force=True)
    assert bounds[0] == QRect(400, 200, 1100, 760)
    assert properties["professionalNativeWindowState"] is False


@pytest.mark.parametrize("message", [native.WM_NCUAHDRAWCAPTION, native.WM_NCUAHDRAWFRAME])
def test_native_themed_caption_paint_cannot_leak_over_custom_header(message):
    event_filter = native._NativeFrameFilter()
    event_filter.sessions[123] = SimpleNamespace(frame_enabled=True)
    msg = native.wintypes.MSG(hWnd=123, message=message)
    assert event_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (True, 0)


def test_windows_initiated_frame_refresh_discards_stale_copied_pixels():
    event_filter = native._NativeFrameFilter()
    event_filter.sessions[123] = SimpleNamespace(frame_enabled=True)
    position = native.WINDOWPOS(flags=0x37)
    msg = native.wintypes.MSG(hWnd=123, message=native.WM_WINDOWPOSCHANGING,
                             lParam=ctypes.addressof(position))
    assert event_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (False, 0)
    assert position.flags == 0x137


def test_activation_updates_windows_state_without_repainting_native_caption():
    calls = []
    event_filter = native._NativeFrameFilter()
    event_filter.sessions[123] = SimpleNamespace(frame_enabled=True,
        user32=SimpleNamespace(DefWindowProcW=lambda *args: calls.append(args) or 1))
    msg = native.wintypes.MSG(hWnd=123, message=native.WM_NCACTIVATE, wParam=1)
    assert event_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (True, 1)
    assert calls == [(123, native.WM_NCACTIVATE, 1, -1)]


def test_mixed_dpi_normal_placement_uses_monitor_relative_coordinates_and_workspace_offset():
    written = []
    window = SimpleNamespace(devicePixelRatio=lambda: 1.5,
                             screen=lambda: SimpleNamespace(geometry=lambda: QRect(-1707, 0, 1707, 960)))
    session = session_for(window)

    def monitor_info(_handle, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(native.MONITORINFO)).contents
        info.rcMonitor = native.wintypes.RECT(-2560, 0, 0, 1440)
        info.rcWork = native.wintypes.RECT(-2500, 40, 0, 1440)
        return True

    def get_placement(_handle, pointer):
        placement = ctypes.cast(pointer, ctypes.POINTER(native.WINDOWPLACEMENT)).contents
        placement.flags = 7
        placement.showCmd = 3
        return True

    def set_placement(_handle, pointer):
        placement = ctypes.cast(pointer, ctypes.POINTER(native.WINDOWPLACEMENT)).contents
        r = placement.rcNormalPosition
        written.append((placement.flags, placement.showCmd, r.left, r.top, r.right, r.bottom))
        return True

    session.user32 = SimpleNamespace(MonitorFromWindow=lambda *_: 1,
                                     GetMonitorInfoW=monitor_info,
                                     GetWindowPlacement=get_placement,
                                     SetWindowPlacement=set_placement)
    session.seed_normal_placement({"x": -1607, "y": 100, "w": 800, "h": 500})
    assert written == [(7, 3, -2470, 110, -1270, 860)]


@pytest.mark.parametrize("maximized, expected", [
    (True, (60, 40, 1920, 1040)),
    (False, (-8, -8, 1928, 1048)),
])
def test_custom_client_area_fits_work_area_only_in_native_maximized_state(maximized, expected):
    def monitor_info(_handle, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(native.MONITORINFO)).contents
        info.rcWork = native.wintypes.RECT(60, 40, 1920, 1040)
        return True

    event_filter = native._NativeFrameFilter()
    event_filter.sessions[123] = SimpleNamespace(
        hwnd=123, frame_enabled=True,
        user32=SimpleNamespace(IsZoomed=lambda *_: maximized,
                               MonitorFromWindow=lambda *_: 1,
                               GetMonitorInfoW=monitor_info))
    rect = native.wintypes.RECT(-8, -8, 1928, 1048)
    message = native.wintypes.MSG()
    message.hWnd = 123
    message.message = native.WM_NCCALCSIZE
    message.wParam = 1
    message.lParam = ctypes.addressof(rect)
    assert event_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message)) == (True, 0)
    assert (rect.left, rect.top, rect.right, rect.bottom) == expected
