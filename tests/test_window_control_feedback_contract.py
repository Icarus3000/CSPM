from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_window_controls_have_visible_hover_and_pressed_feedback():
    header = (PROJECT_ROOT / "src" / "qml" / "components" / "ProfessionalTopHeader.qml").read_text(encoding="utf-8")
    legacy = (PROJECT_ROOT / "src" / "qml" / "components" / "TitleBarButton.qml").read_text(encoding="utf-8")

    assert 'controlHoverFill: topHeaderRoot.headerLight ? "#DCE8F8" : "#2D4361"' in header
    assert "minimizeButton.down" in header
    assert "maximizeButton.down" in header
    assert "closeButton.down" in header
    assert "control.down" in legacy
    assert "ColorAnimation { duration: 45 }" in legacy


def test_professional_window_motion_starts_without_waiting_for_a_frame_capture():
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(encoding="utf-8")
    minimize_overlay = (PROJECT_ROOT / "src" / "qml" / "MinimizeOverlay.qml").read_text(encoding="utf-8")

    # Keep the existing motion, but avoid making its first visible frame wait
    # on a high-DPI grabToImage handoff.
    assert 'mainWin.startCloseMotion("professional-immediate")' in shell
    assert 'mainWin.createMinimizeOverlayWithSnapshot("")' in shell
    assert "? snapshotContent : liveContent" in minimize_overlay
    assert "id: liveContent" in minimize_overlay
    assert "MainContent {" in minimize_overlay
