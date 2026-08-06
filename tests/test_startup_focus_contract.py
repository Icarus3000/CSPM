from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _function_body(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_startup_does_not_make_the_main_window_topmost_or_reclaim_focus() -> None:
    qml = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    main_py = (PROJECT_ROOT / "src" / "python" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "BRUTE FORCE FOCUS LOCK" not in qml
    assert "Qt.WindowStaysOnTopHint" not in qml

    splash_restore = _function_body(
        main_py,
        "    def _restore_main_foreground_after_native_splash() -> None:",
        "    def _on_native_splash_fade_finished() -> None:",
    )
    assert "forceLaunchFocusLight" in splash_restore
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
        "    def _on_native_splash_fade_finished() -> None:",
        "    if custom_splash is not None:",
    )
    assert "QTimer.singleShot(0, _restore_main_foreground_after_native_splash)" in fade_finished
    assert "for delay_ms" not in fade_finished


def test_app_controller_foreground_helper_uses_only_regular_qt_activation() -> None:
    controller = (
        PROJECT_ROOT / "src" / "python" / "backend" / "app_controller.py"
    ).read_text(encoding="utf-8")
    foreground_helper = _function_body(
        controller,
        "    def _force_window_foreground(self, target, trace_label: str):",
        "    @Slot(QObject, result=bool)",
    )

    assert "requestActivate" in foreground_helper
    for prohibited_call in (
        "SetWindowPos(",
        "SetForegroundWindow(",
        "SetActiveWindow(",
        "SetFocus(",
        "BringWindowToTop(",
    ):
        assert prohibited_call not in foreground_helper


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
