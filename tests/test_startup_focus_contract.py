from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _function_body(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_startup_claims_foreground_once_without_persistent_topmost_state() -> None:
    qml = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    main_py = (PROJECT_ROOT / "src" / "python" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "BRUTE FORCE FOCUS LOCK" not in qml
    main_window_setup = _function_body(
        qml,
        "    // ============================================================\n    // WINDOW SETUP",
        "    onHostXChanged:",
    )
    assert "Qt.WindowStaysOnTopHint" not in main_window_setup

    splash_restore = _function_body(
        main_py,
        "    def _restore_main_foreground_after_native_splash() -> None:",
        "    def _bind_native_splash_to_main_window(main_window) -> None:",
    )
    assert 'controller, "claimInitialMainWindowForeground", None' in splash_restore
    for prohibited_call in (
        "SetWindowPos(",
        "SetForegroundWindow(",
        "SetActiveWindow(",
        "SetFocus(",
        "BringWindowToTop(",
    ):
        assert prohibited_call not in splash_restore

    fade_finished = _function_body(
        main_py,
        "    def _release_cinematic_launch_gate() -> None:",
        "    if custom_splash is not None:",
    )
    assert "QTimer.singleShot(0, _restore_main_foreground_after_native_splash)" in fade_finished
    assert fade_finished.count("_restore_main_foreground_after_native_splash") == 1
    assert "460" not in fade_finished
    assert "for delay_ms" not in fade_finished


def test_initial_foreground_claim_is_one_shot_and_immediately_demotes_topmost() -> None:
    controller = (
        PROJECT_ROOT / "src" / "python" / "backend" / "app_controller.py"
    ).read_text(encoding="utf-8")
    foreground_helper = _function_body(
        controller,
        "    def claimInitialMainWindowForeground(self) -> bool:",
        "    @Slot(QObject, result=bool)",
    )

    assert 'getattr(self, "_initial_main_foreground_claimed", False)' in foreground_helper
    assert "self._initial_main_foreground_claimed = True" in foreground_helper
    assert "requestActivate" in foreground_helper
    assert "user32.SetWindowPos(hwnd, hwnd_type(-1)" in foreground_helper
    assert "user32.SetWindowPos(hwnd, hwnd_type(-2)" in foreground_helper
    assert foreground_helper.index("hwnd_type(-1)") < foreground_helper.index(
        "hwnd_type(-2)"
    )
    assert "user32.SetForegroundWindow(hwnd)" in foreground_helper
    assert "user32.BringWindowToTop(hwnd)" in foreground_helper


def test_settled_shell_host_is_limited_to_the_visible_canvas() -> None:
    qml = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    host_function = _function_body(
        qml,
        "    function applyHostEnvelopeForTarget() {",
        "    function ensureHostContainsRect(",
    )

    assert "function settledHostPaddingPx(refW, refH)" in qml
    assert "var canvasPad = settledHostPaddingPx(refW, refH);" in host_function
    assert "hostX = Math.round(finalX - canvasPad);" in host_function
    assert "hostW = Math.max(1, Math.round(safeFinalW + (canvasPad * 2)));" in host_function


def test_backend_boot_is_triggered_by_settlement_not_focus_code() -> None:
    qml = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    settle_function = _function_body(
        qml,
        "    function transitionToSettled() {",
        "    function transitionToClosing() {",
    )

    assert "if (!mainWin.detachedMode) {\n            mainWin.triggerDeferredBackendBoot();" in settle_function
