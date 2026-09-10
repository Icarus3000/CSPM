from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_window_controls_have_visible_hover_and_pressed_feedback():
    header = (PROJECT_ROOT / "src" / "qml" / "components" / "ProfessionalTopHeader.qml").read_text(encoding="utf-8")
    legacy = (PROJECT_ROOT / "src" / "qml" / "components" / "TitleBarButton.qml").read_text(encoding="utf-8")

    assert 'controlHoverFill: topHeaderRoot.headerLight ? "#DCE8F8" : "#2D4361"' in header
    assert "minimizeMouseArea.pressed" in header
    assert "maximizeButton.down" in header
    assert "closeButton.down" in header
    assert "btnMouseArea.pressed" in legacy
    assert "ColorAnimation { duration: 45 }" in legacy


def test_professional_window_motion_reuses_the_accepted_frozen_overlay_handoff():
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(encoding="utf-8")
    minimize_overlay = (PROJECT_ROOT / "src" / "qml" / "MinimizeOverlay.qml").read_text(encoding="utf-8")
    maximize_overlay = (PROJECT_ROOT / "src" / "qml" / "MaximizeOverlay.qml").read_text(encoding="utf-8")

    # Close/minimize remain the proven baseline. Professional maximize/restore
    # now uses the same first-painted frozen-surface handoff instead of moving
    # and resizing the live shell on every frame.
    assert 'mainWin.startCloseMotion("singularity-inplace")' in shell
    assert "createClosingOverlayWithSnapshot(snapUrl)" in shell
    assert "createMinimizeOverlayWithSnapshot(snapUrl)" in shell
    assert "? snapshotContent : liveContent" in minimize_overlay
    assert "id: liveContent" in minimize_overlay
    assert "MainContent {" in minimize_overlay
    assert "contentLayer.grabToImage(function(result)" in shell
    assert "maximizeOverlayComponent.createObject" in shell
    assert "mainWin.opacity = 0.0;" in shell
    assert "overlayObj.startTransition();" in shell
    assert "ChromeSurface {" in maximize_overlay
    assert "MainContent {" in maximize_overlay
    assert "roundedSurfaceMaskEnabled: false" in maximize_overlay
    assert "transitionProgress" in maximize_overlay
