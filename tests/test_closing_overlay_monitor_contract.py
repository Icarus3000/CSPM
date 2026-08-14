from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _function_body(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_close_transition_freezes_the_visible_surface_monitor_before_animation() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )

    assert "property var closingOverlayGeometry: null" in shell
    capture = _function_body(
        shell,
        "    function captureClosingOverlayGeometry() {",
        "    function closingCanvasRect() {",
    )
    # The native window position is authoritative at close time; hostX/Y can
    # lag one monitor move behind on Windows.
    assert "var actualHostX = Math.round(mainWin.x);" in capture
    assert "var actualHostY = Math.round(mainWin.y);" in capture
    assert "screenForPoint(centerX, centerY" in capture
    assert "adoptTargetScreen(sourceScreen, true);" in capture
    assert '"sourceScreen": sourceScreen' in capture

    transition = _function_body(
        shell,
        "    function transitionToClosing() {",
        "    // ============================================================\n    // CANVAS TRANSITION ANIMATION",
    )
    assert "clearClosingOverlayGeometry();" in transition
    assert "captureClosingOverlayGeometry();" in transition
    assert transition.index("captureClosingOverlayGeometry();") < transition.index(
        'animationPhase = "closing";'
    )


def test_closing_overlay_is_pinned_before_its_first_visible_frame() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    create_overlay = _function_body(
        shell,
        "    function createClosingOverlayWithSnapshot(snapshotUrl) {",
        "    function closeTargetGlobalPoint() {",
    )

    assert '"visible": false' in create_overlay
    assert 'overlayProps["screen"] = sourceScreen;' in create_overlay
    assert "overlayObj.screen = sourceScreen;" in create_overlay
    assert "overlayObj.visible = true;" in create_overlay
    assert create_overlay.index('"visible": false') < create_overlay.index(
        "overlayObj.visible = true;"
    )
