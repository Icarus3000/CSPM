from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _function_body(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_maximize_and_restore_follow_the_current_native_window_monitor() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )

    remember = _function_body(
        shell,
        "    function rememberRestoreGeometry(sourceScreenOverride) {",
        "    function activeVisibleRectForMaximize() {",
    )
    assert "restoreSourceVisibleX = Math.round(sourceRect.x);" in remember
    assert "restoreSourceVisibleY = Math.round(sourceRect.y);" in remember
    assert "restoreSourceVisibleW = Math.max(1, Math.round(sourceRect.w));" in remember
    assert "restoreSourceVisibleH = Math.max(1, Math.round(sourceRect.h));" in remember
    assert "adoptTargetScreen(sourceScreenOverride, true);" in remember

    control_monitor = _function_body(
        shell,
        "    function monitorOwningWindowControl() {",
        "    function topEdgeSnapTargetForDragRelease() {",
    )
    assert "nativeHostRectForWindowControl()" in control_monitor
    assert "screenForPoint(centerX, centerY, null)" in control_monitor

    host_rect = _function_body(
        shell,
        "    function nativeHostRectForWindowControl() {",
        "    function monitorOwningWindowControl() {",
    )
    assert '"x": Math.round(mainWin.x)' in host_rect
    assert '"y": Math.round(mainWin.y)' in host_rect
    assert '"w": Math.max(1, Math.round(mainWin.width))' in host_rect
    assert '"h": Math.max(1, Math.round(mainWin.height))' in host_rect

    maximize = _function_body(
        shell,
        "    function maximizeWindowToVisibleRect(screenOverride) {",
        "    function defaultRestoreRect(rectOverride) {",
    )
    assert "var commandScreen = screenOverride ? screenOverride : monitorOwningWindowControl();" in maximize
    assert "maximizedOwnerScreen = commandScreen;" in maximize
    assert "professionalMaximizeFxAnimation.restart();" in maximize

    toggle = _function_body(
        shell,
        "    function toggleWindowMaximize() {",
        "    function beginHeaderDrag(preDragX, preDragY) {",
    )
    assert "var commandScreen = monitorOwningWindowControl();" in toggle
    assert "rememberRestoreGeometry(commandScreen);" in toggle
    assert "maximizeWindowToVisibleRect(commandScreen);" in toggle

    resolve = _function_body(
        shell,
        "    function resolveRestoreRectFromMaximized(cursorPos, cursorAnchored) {",
        "    function restoreFromMaximized(cursorPos, cursorAnchored) {",
    )
    # Clicking restore must use the native host's current monitor rather than
    # replaying absolute desktop X/Y or a stale maximize cache. Drag-restore
    # remains cursor anchored.
    assert "if (!cursorAnchored && restoreGeometryValid)" in resolve
    assert "destination = restoreGlyphDestinationScreen();" in resolve
    assert "visibleRectForScreen(destinationScreen, destinationInfo)" in resolve
    assert "var relativeCenterX = clampNumber(" in resolve
    assert "var relativeCenterY = clampNumber(" in resolve
    assert "destinationRect.x + (relativeCenterX * destinationW)" in resolve
    assert "destinationRect.y + (relativeCenterY * destinationH)" in resolve
    assert 'phaseLog("RESTORE-MAX", "Mapped saved normal rect' in resolve
    assert 'lagLog("[RESTORE-MAX] destination="' in resolve

    destination = _function_body(
        shell,
        "    function restoreGlyphDestinationScreen() {",
        "    function resolveRestoreRectFromMaximized(cursorPos, cursorAnchored) {",
    )
    assert "nativeHostRectForWindowControl()" in destination
    assert "live-native-window-owner" in destination
    assert "maximize-owner-fallback" in destination

    restore = _function_body(
        shell,
        "    function restoreFromMaximized(cursorPos, cursorAnchored) {",
        "    function restoreFromMaximizedForDrag(cursorPos) {",
    )
    assert "var restoreDestination = !cursorAnchored ? restoreGlyphDestinationScreen() : null;" in restore
    assert "var restoreScreen = restoreDestination ? restoreDestination.screen : null;" in restore
    assert "adoptTargetScreen(restoreScreen, true);" in restore
    assert "professionalRestoreMaxFxAnimation.restart();" in restore


def test_professional_maximize_restore_uses_a_short_frozen_surface_transform() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )

    # The Professional shell uses direct GPU hardware-accelerated texture transforms
    # on contentLayer with zero-latency cubic easing.
    assert "property real maximizeRenderX: 0.0" in shell
    assert "property real maximizeRenderY: 0.0" in shell
    assert "property real maximizeRenderW: 1.0" in shell
    assert "property real maximizeRenderH: 1.0" in shell
    assert "property real maximizeStartFinalX: 0.0" in shell
    assert "property real maximizeTargetFinalX: 0.0" in shell
    assert "id: professionalMaximizeFxAnimation" in shell
    assert "id: professionalRestoreMaxFxAnimation" in shell
    assert 'property: "maximizeRenderX"' in shell
    assert 'property: "maximizeRenderY"' in shell
    assert 'property: "maximizeRenderW"' in shell
    assert 'property: "maximizeRenderH"' in shell
    assert "layer.enabled: mainWin.userResizeInProgress || mainWin.maximizeAnimInProgress" in shell
    assert "easing.type: Easing.OutCubic" in shell


def test_modern_combo_box_height_is_independent_of_its_implicit_height() -> None:
    combo = (PROJECT_ROOT / "src" / "qml" / "components" / "ModernComboBox.qml").read_text(
        encoding="utf-8"
    )

    # Fusion derives implicitHeight from padding. Padding must therefore not
    # read control.height, which initially derives from implicitHeight.
    padding = _function_body(
        combo,
        "    topPadding: control.hasLabel",
        "    TextMetrics {\n        id: displayMetrics",
    )
    assert "control.height" not in padding


def test_close_keeps_the_window_visible_until_it_reaches_the_center_pinpoint() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    jelly = (PROJECT_ROOT / "src" / "qml" / "components" / "JellyController.qml").read_text(
        encoding="utf-8"
    )

    # The live QML shell owns the first long act; only after it has collapsed
    # can the Canvas draw the burst, hold, and inward plasma implosion.
    assert "duration: 1120" in jelly
    close_progress = _function_body(
        jelly,
        "    onCloseProgressChanged: {",
        "    // ============================================================\n    // MINIMIZE & RESTORE",
    )
    assert "if (p < 0.44)" in close_progress
    assert "var suckP = p / 0.44;" in close_progress
    assert "opacityVal = 1.0;" in close_progress
    assert "scaleX = 0.001;" in close_progress
    assert "opacityVal = 0.0;" in close_progress

    # The particle sequence uses exactly the same handoff boundary, avoiding
    # a burst that overtakes a still full-size app window.
    assert "// CLOSE ANIMATION: visible shrink -> supernova -> hold -> implosion." in shell
    assert "if (p < 0.44)" in shell
    assert "var burstP = (p - 0.44) / 0.13;" in shell
    assert "var hangP = (p - 0.57) / 0.13;" in shell
    assert "var fizzleP = (p - 0.70) / 0.30;" in shell


def test_startup_screen_is_locked_to_splash_monitor_until_settled() -> None:
    shell = (PROJECT_ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(
        encoding="utf-8"
    )
    # resolveTargetScreen must strictly select the startup launch screen where
    # the CS splash was launched until the main window has settled.
    resolve = _function_body(
        shell,
        "    function resolveTargetScreen() {",
        "    function persistMainWindowLayout() {",
    )
    assert "if (!mainWin.isSettled && mainWin.startupLaunchScreenLocked && mainWin.targetScreen)" in resolve
    assert "return mainWin.targetScreen;" in resolve
