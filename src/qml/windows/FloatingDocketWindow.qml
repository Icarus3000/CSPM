import QtQuick
import QtQuick.Window
import "../components"
import "../views"
import "../standards/ThemeBridge.js" as ThemeBridge
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: floatWin
    title: (panelTaskbarTitle && panelTaskbarTitle.length > 0) ? panelTaskbarTitle : ("CSPM - " + panelTitle)
    objectName: "CSPMFloatingDocketWindow"

    visible: false
    color: SemanticTheme.surfaceApp(floatWin.t, floatWin.appStyle)
    transientParent: null
    flags: Qt.Window
        | Qt.FramelessWindowHint
        | Qt.NoDropShadowWindowHint
        | Qt.WindowSystemMenuHint
        | Qt.WindowMinimizeButtonHint
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowCloseButtonHint

    property alias mainContentRef: mainContent

    property string panelTitle: "Module"
    property string panelTaskbarTitle: ""

    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property string appStyle: (appRef && appRef.appStyle) ? String(appRef.appStyle) : "Professional"
    property bool soundEffectsEnabled: !(appRef && appRef.soundEffectsEnabled === false)
    property var t: {
        try {
            if (appRef && appRef.theme && appRef.theme.bg) return appRef.theme
        } catch (e) {
        }
        return {
            "bg": "#000000",
            "accent": "#2979FF",
            "text": "#FFFFFF",
            "glow": "#FF1744"
        }
    }

    function cloneThemeObject(themeObj) {
        return ThemeBridge.cloneThemeObject(themeObj)
    }

    function resolveAppRef() {
        return appRef
    }

    function themeForName(themeName) {
        return ThemeBridge.themeForName(resolveAppRef(), themeName)
    }

    function applyThemeSelection(themeName, pickedPayload) {
        var localTheme = ThemeBridge.applyThemeSelection(resolveAppRef(), themeName, pickedPayload)
        if (localTheme && localTheme.bg) {
            floatWin.t = localTheme
            return
        }
        if (pickedPayload && pickedPayload.bg) {
            floatWin.t = ThemeBridge.cloneThemeObject(pickedPayload)
            return
        }
    }

    function syncThemeFromApp() {
        var payload = ThemeBridge.syncThemeFromApp(resolveAppRef())
        if (!payload || !payload.bg) return false
        floatWin.t = payload
        return true
    }

    function syncSoundEffectsFromApp() {
        var resolvedAppRef = resolveAppRef()
        var nextEnabled = true
        try {
            nextEnabled = !(resolvedAppRef && resolvedAppRef.soundEffectsEnabled === false)
        } catch (e) {
            nextEnabled = true
        }
        floatWin.soundEffectsEnabled = nextEnabled
        if (settingsMenu) {
            settingsMenu.soundEnabled = nextEnabled
        }
        return nextEnabled
    }

    function applySoundEffectsEnabled(enabled) {
        var nextEnabled = !!enabled
        floatWin.soundEffectsEnabled = nextEnabled
        if (settingsMenu) {
            settingsMenu.soundEnabled = nextEnabled
        }
        return true
    }

    property string instanceId: ""
    property rect originRect: Qt.rect(0, 0, 120, 90)
    property rect hostWindowRect: Qt.rect(0, 0, 1220, 920)
    property int initialTileIndex: 0
    property var initialPanelState: null

    property color monitorFrameColor: "#00E5FF"
    property color canvasFrameColor: "#FF8C00"
    // Toggle expertDebugMode to true to re-enable the neon monitor/geometry boundary overlays
    property bool expertDebugMode: false
    property bool debugFrameEnabled: expertDebugMode

    property bool uiMaximized: false
    property bool restoreGeometryValid: false
    property int restoreFinalX: 0
    property int restoreFinalY: 0
    property int restoreFinalW: 1
    property int restoreFinalH: 1
    property bool userMoveInProgress: false
    property string animationPhase: "settled"
    property bool maximizeAnimInProgress: false
    property bool isMinimizing: false
    property bool isRestoringFromMinimize: false
    property bool isClosing: false
    property bool wasWindowMinimized: false
    property bool minimizeRestorePending: false
    property int osWinShiftMoveDirection: 0
    property int osWinShiftMoveSeq: 0
    property int osWinShiftSourceFinalX: 0
    property int osWinShiftSourceFinalY: 0
    property int osWinShiftSourceFinalW: 1
    property int osWinShiftSourceFinalH: 1
    property int osWinShiftSourceRectX: 0
    property int osWinShiftSourceRectY: 0
    property int osWinShiftSourceRectW: 1
    property int osWinShiftSourceRectH: 1
    property bool dragReleaseSnapEnabled: true
    property bool dragReleaseCenterLockEnabled: true
    property bool dragReleaseCursorSampleEnabled: false

    property real dragFxScaleX: 1.0
    property real dragFxScaleY: 1.0
    property real dragFxTransX: 0.0
    property real dragFxTransY: 0.0
    property real dragFxRotate: 0.0
    property real dragFxVelX: 0.0
    property real dragFxVelY: 0.0

    property real maximizeFxScaleX: 1.0
    property real maximizeFxScaleY: 1.0
    property real maximizeFxTransX: 0.0
    property real maximizeFxTransY: 0.0
    property real maximizeFxRotate: 0.0

    property real minimizeFxScaleX: 1.0
    property real minimizeFxScaleY: 1.0
    property real minimizeFxTransX: 0.0
    property real minimizeFxTransY: 0.0
    property real minimizeFxRotate: 0.0

    property bool _exitDestroying: false
    property bool _closeStarted: false
    property bool _openedOnce: false
    property bool _didCloseEmitted: false
    property string dragStrategy: "none"
    // Cursor-anchored drag is the stable path across mixed-DPI/multi-monitor setups.
    property bool preferTranslationDrag: false
    // Keep a single drag driver active to avoid pointer-fighting jitter.
    property bool dragPollingEnabled: false
    // Disable drag deformation/envelope FX while stabilizing drag smoothness.
    property bool dragVisualFxEnabled: true
    property bool dragHasCursorAnchor: false
    property real dragStartCursorX: 0
    property real dragStartCursorY: 0
    property bool _interactionEnvelopeActive: false
    property bool _interactionEnvelopeMutating: false
    property int _interactionEnvelopePadApplied: 0
    property int interactionEnvelopePadPx: Math.max(0, _interactionEnvelopePadApplied)
    property int metricsMonitorW: Math.max(1, floatWin.width)
    property int metricsMonitorH: Math.max(1, floatWin.height)
    property int canvasPadBasePx: ratioToPixels(
        layoutRatios.contentCanvasPadPct,
        Math.max(1, floatWin.width),
        Math.max(1, floatWin.height),
        1
    )
    property int canvasPadPx: (uiMaximized || maximizeAnimInProgress) ? 0 : canvasPadBasePx
    property int contentInsetPx: canvasPadPx + interactionEnvelopePadPx
    property int contentAreaW: Math.max(1, floatWin.width - (contentInsetPx * 2))
    property int contentAreaH: Math.max(1, floatWin.height - (contentInsetPx * 2))
    property real _dragStartWindowX: 0
    property real _dragStartWindowY: 0

    property var activeVisibleRect: ({
        "x": 0,
        "y": 0,
        "w": Math.max(1, floatWin.width),
        "h": Math.max(1, floatWin.height)
    })

    property var layoutRatios: ({
        "spawnOffsetXPct": 0.060,
        "spawnOffsetYPct": 0.055,
        "fallbackWidthPct": 0.62,
        "fallbackHeightPct": 0.70,
        "openStageOneDurationPct": 0.084,
        "openStageTwoDurationPct": 0.122,
        "openStageThreeDurationPct": 0.161,
        "contentCanvasPadPct": 0.0108,
        "dragEnvelopePadPct": 0.084,
        "dragFxScalePct": 0.0009,
        "dragFxTranslatePct": 0.26,
        "dragFxRotatePct": 0.026,
        "dragFxMaxScaleDelta": 0.085,
        "dragFxReleaseDurationPct": 0.170,
        "maximizeFxDurationPct": 0.196,
        "minimizeFxDurationPct": 0.174,
        "resizeMinWidthPct": 0.240,
        "resizeMinHeightPct": 0.260,
        "themePickerRightPct": 0.020,
        "themePickerTopPct": 0.040,
        "monitorFrameCorePct": 0.0024,
        "monitorFrameGlowPct": 0.0068,
        "canvasFrameCorePct": 0.0030,
        "canvasFrameGlowPct": 0.0080
    })

    property var uiMetrics: ({
        "monitorW": Math.max(1, metricsMonitorW),
        "monitorH": Math.max(1, metricsMonitorH),
        "contentW": Math.max(1, contentAreaW),
        "contentH": Math.max(1, contentAreaH),
        "scalePercent": (floatWin.screen && typeof floatWin.screen.devicePixelRatio === "number")
            ? Math.max(1, Math.round(floatWin.screen.devicePixelRatio * 100.0))
            : 100,
        "fontFloorTitlePx": ratioToPixels(0.0130, Math.max(1, contentAreaW), Math.max(1, contentAreaH), 12),
        "fontFloorIconPx": ratioToPixels(0.0120, Math.max(1, contentAreaW), Math.max(1, contentAreaH), 12),
        "fontFloorBodyPx": ratioToPixels(0.0109, Math.max(1, contentAreaW), Math.max(1, contentAreaH), 9),
        "fontFloorLabelPx": ratioToPixels(0.0098, Math.max(1, contentAreaW), Math.max(1, contentAreaH), 8)
    })

    property int monitorFrameThickness: ratioToPixels(
        layoutRatios.monitorFrameCorePct,
        Math.max(1, activeVisibleRect.w),
        Math.max(1, activeVisibleRect.h),
        1
    )
    property int monitorFrameGlowThickness: ratioToPixels(
        layoutRatios.monitorFrameGlowPct,
        Math.max(1, activeVisibleRect.w),
        Math.max(1, activeVisibleRect.h),
        monitorFrameThickness + 1
    )
    property int canvasFrameThickness: ratioToPixels(
        layoutRatios.canvasFrameCorePct,
        Math.max(1, activeVisibleRect.w),
        Math.max(1, activeVisibleRect.h),
        1
    )
    property int canvasFrameGlowThickness: ratioToPixels(
        layoutRatios.canvasFrameGlowPct,
        Math.max(1, activeVisibleRect.w),
        Math.max(1, activeVisibleRect.h),
        canvasFrameThickness + 1
    )

    signal didClose(string instanceId)
    signal requestDetach(int tileIndex, string titleText, var state, rect originRect)

    function setPanelTaskbarTitle(nextTitle) {
        if (nextTitle === undefined || nextTitle === null) {
            panelTaskbarTitle = ""
            return
        }
        panelTaskbarTitle = String(nextTitle)
    }

    function ratioToPixels(ratio, referenceW, referenceH, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        var rw = Math.max(1, referenceW || 1)
        var rh = Math.max(1, referenceH || 1)
        return Math.max(floorPx, Math.round(Math.min(rw, rh) * ratio))
    }

    function transitionDurationMs(ratio, minMs) {
        var unit = Math.min(Math.max(1, width), Math.max(1, height))
        return Math.max(Math.max(1, Math.round(minMs || 1)), Math.round(unit * ratio))
    }

    function clampNumber(v, lo, hi) {
        var val = isFinite(v) ? v : 0
        var minVal = (typeof lo === "number") ? lo : val
        var maxVal = (typeof hi === "number") ? hi : val
        if (val < minVal) return minVal
        if (val > maxVal) return maxVal
        return val
    }

    function currentContentRect() {
        var pad = Math.max(0, Math.round(_interactionEnvelopePadApplied))
        return {
            "x": Math.round(x + pad),
            "y": Math.round(y + pad),
            "w": Math.max(1, Math.round(width - (pad * 2))),
            "h": Math.max(1, Math.round(height - (pad * 2)))
        }
    }

    function dragInteractionEnvelopePadPx() {
        if (uiMaximized || maximizeAnimInProgress) return 0
        var rectObj = activeVisibleRectForMaximize()
        var refW = Math.max(1, (rectObj && rectObj.w > 0) ? rectObj.w : Math.max(1, width))
        var refH = Math.max(1, (rectObj && rectObj.h > 0) ? rectObj.h : Math.max(1, height))
        return ratioToPixels(layoutRatios.dragEnvelopePadPct, refW, refH, 1)
    }

    function applyInteractionEnvelopePad(nextPad) {
        var desiredPad = Math.max(0, Math.round(nextPad))
        var currentPad = Math.max(0, Math.round(_interactionEnvelopePadApplied))
        if (desiredPad === currentPad || _interactionEnvelopeMutating) return false

        var rect = currentContentRect()
        _interactionEnvelopeMutating = true
        _interactionEnvelopePadApplied = desiredPad
        x = Math.round(rect.x - desiredPad)
        y = Math.round(rect.y - desiredPad)
        width = Math.max(1, Math.round(rect.w + (desiredPad * 2)))
        height = Math.max(1, Math.round(rect.h + (desiredPad * 2)))
        _interactionEnvelopeMutating = false
        return true
    }

    function syncInteractionEnvelopePad() {
        if (!dragVisualFxEnabled) {
            applyInteractionEnvelopePad(0)
            return
        }
        var shouldHold = (_interactionEnvelopeActive || dragFxReleaseAnimation.running)
        var desiredPad = shouldHold ? dragInteractionEnvelopePadPx() : 0
        applyInteractionEnvelopePad(desiredPad)
    }

    function setInteractionEnvelopeActive(active) {
        if (!dragVisualFxEnabled) {
            _interactionEnvelopeActive = false
            applyInteractionEnvelopePad(0)
            return
        }
        _interactionEnvelopeActive = !!active
        syncInteractionEnvelopePad()
    }

    function collapseInteractionEnvelopeNow() {
        _interactionEnvelopeActive = false
        if (dragFxReleaseAnimation.running) dragFxReleaseAnimation.stop()
        applyInteractionEnvelopePad(0)
    }

    function resetDragFxState() {
        dragFxScaleX = 1.0
        dragFxScaleY = 1.0
        dragFxTransX = 0.0
        dragFxTransY = 0.0
        dragFxRotate = 0.0
        dragFxVelX = 0.0
        dragFxVelY = 0.0
    }

    function applyDragFxFromDelta(dx, dy) {
        if (!dragVisualFxEnabled) return
        if (!userMoveInProgress || isClosing || maximizeAnimInProgress || isMinimizing || isRestoringFromMinimize) return
        if (!isFinite(dx) || !isFinite(dy)) return
        if (Math.abs(dx) < 0.45 && Math.abs(dy) < 0.45) return

        dragFxVelX = (dragFxVelX * 0.70) + (dx * 0.30)
        dragFxVelY = (dragFxVelY * 0.70) + (dy * 0.30)
        var vdx = dragFxVelX
        var vdy = dragFxVelY
        var vSpeed = Math.sqrt((vdx * vdx) + (vdy * vdy))
        if (!isFinite(vSpeed) || vSpeed <= 0.0001) return

        var refUnit = Math.max(1, Math.min(Math.max(1, contentAreaW), Math.max(1, contentAreaH)))
        var speedRef = clampNumber(Math.round(refUnit * 0.040), 18, 64)
        var speedNorm = clampNumber(vSpeed / speedRef, 0.0, 1.0)

        var invSpeed = 1.0 / vSpeed
        var dirX = vdx * invSpeed
        var dirY = vdy * invSpeed
        var absDirX = Math.abs(dirX)
        var absDirY = Math.abs(dirY)

        var stretch = 0.020 + (0.110 * speedNorm)
        var targetScaleX = 1.0 + (stretch * (absDirX - absDirY))
        var targetScaleY = 1.0 + (stretch * (absDirY - absDirX))
        targetScaleX = clampNumber(targetScaleX, 0.88, 1.15)
        targetScaleY = clampNumber(targetScaleY, 0.88, 1.15)

        var targetTransX = 0.0
        var targetTransY = 0.0
        var targetRotate = clampNumber((vdx * 0.120) + (vdy * 0.028), -6.2, 6.2)

        var response = 0.36
        dragFxScaleX = dragFxScaleX + ((targetScaleX - dragFxScaleX) * response)
        dragFxScaleY = dragFxScaleY + ((targetScaleY - dragFxScaleY) * response)
        dragFxTransX = dragFxTransX + ((targetTransX - dragFxTransX) * response)
        dragFxTransY = dragFxTransY + ((targetTransY - dragFxTransY) * response)
        dragFxRotate = dragFxRotate + ((targetRotate - dragFxRotate) * response)
    }

    function releaseDragFxToSettled() {
        if (!dragVisualFxEnabled) {
            resetDragFxState()
            syncInteractionEnvelopePad()
            return
        }
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop()
        }
        dragFxReleaseAnimation.restart()
        syncInteractionEnvelopePad()
    }

    function resetMaximizeFxState() {
        maximizeFxScaleX = 1.0
        maximizeFxScaleY = 1.0
        maximizeFxTransX = 0.0
        maximizeFxTransY = 0.0
        maximizeFxRotate = 0.0
    }

    function seedMaximizeFxFromSourceRect(sourceX, sourceY, sourceW, sourceH, targetX, targetY, targetW, targetH) {
        var tw = Math.max(1, Math.round(targetW))
        var th = Math.max(1, Math.round(targetH))
        var sx = Math.max(0.10, Math.min(4.0, Math.max(1, Math.round(sourceW)) / tw))
        var sy = Math.max(0.10, Math.min(4.0, Math.max(1, Math.round(sourceH)) / th))

        var sourceLocalX = Math.round(sourceX - targetX)
        var sourceLocalY = Math.round(sourceY - targetY)
        var originX = tw
        var originY = 0
        var tx = sourceLocalX - (((1.0 - sx) * originX))
        var ty = sourceLocalY - (((1.0 - sy) * originY))

        maximizeFxScaleX = sx
        maximizeFxScaleY = sy
        maximizeFxTransX = tx
        maximizeFxTransY = ty
        maximizeFxRotate = 0.0
    }

    function stopMaximizeFxAnimations() {
        if (maximizeFxAnimation.running) maximizeFxAnimation.stop()
        if (maximizeRestoreFxAnimation.running) maximizeRestoreFxAnimation.stop()
        maximizeAnimInProgress = false
        resetMaximizeFxState()
    }

    function resetMinimizeFxState() {
        minimizeFxScaleX = 1.0
        minimizeFxScaleY = 1.0
        minimizeFxTransX = 0.0
        minimizeFxTransY = 0.0
        minimizeFxRotate = 0.0
    }

    function emitDidCloseOnce() {
        if (_didCloseEmitted) return
        _didCloseEmitted = true
        didClose(instanceId)
    }

    function validRectLike(r) {
        return r
            && typeof r.x === "number"
            && typeof r.y === "number"
            && typeof r.width === "number"
            && typeof r.height === "number"
            && isFinite(r.x)
            && isFinite(r.y)
            && isFinite(r.width)
            && isFinite(r.height)
            && r.width > 0
            && r.height > 0
    }

    function fallbackScreensFromApp() {
        var out = []
        if (!appRef || !appRef.getScreenGeometry) return out
        for (var idx = 0; idx < 16; idx++) {
            var info = null
            try {
                info = appRef.getScreenGeometry(idx)
            } catch (e) {
                info = null
            }
            if (!info || typeof info.w !== "number" || typeof info.h !== "number" || info.w <= 0 || info.h <= 0) {
                break
            }
            out.push({
                "virtualX": Math.round(info.x),
                "virtualY": Math.round(info.y),
                "width": Math.max(1, Math.round(info.w)),
                "height": Math.max(1, Math.round(info.h)),
                "availableGeometry": {
                    "x": Math.round((typeof info.availX === "number") ? info.availX : info.x),
                    "y": Math.round((typeof info.availY === "number") ? info.availY : info.y),
                    "width": Math.max(1, Math.round((typeof info.availW === "number") ? info.availW : info.w)),
                    "height": Math.max(1, Math.round((typeof info.availH === "number") ? info.availH : info.h))
                }
            })
        }
        return out
    }

    function allScreensList() {
        var qmlScreens = (Qt.application && Qt.application.screens) ? Qt.application.screens : []
        if (qmlScreens && qmlScreens.length > 0) return qmlScreens
        return fallbackScreensFromApp()
    }

    function screenVirtualX(screenObj) {
        if (!screenObj) return 0
        if (typeof screenObj.virtualX === "number") return screenObj.virtualX
        if (typeof screenObj.x === "number") return screenObj.x
        return 0
    }

    function screenVirtualY(screenObj) {
        if (!screenObj) return 0
        if (typeof screenObj.virtualY === "number") return screenObj.virtualY
        if (typeof screenObj.y === "number") return screenObj.y
        return 0
    }

    function screenPixelW(screenObj) {
        if (!screenObj) return 1
        if (typeof screenObj.width === "number") return Math.max(1, Math.round(screenObj.width))
        if (typeof screenObj.w === "number") return Math.max(1, Math.round(screenObj.w))
        return 1
    }

    function screenPixelH(screenObj) {
        if (!screenObj) return 1
        if (typeof screenObj.height === "number") return Math.max(1, Math.round(screenObj.height))
        if (typeof screenObj.h === "number") return Math.max(1, Math.round(screenObj.h))
        return 1
    }

    function desktopBoundsRect() {
        var screens = allScreensList()
        if (!screens || screens.length === 0) {
            return { "x": 0, "y": 0, "w": Math.max(1, width), "h": Math.max(1, height) }
        }
        var minX = screenVirtualX(screens[0])
        var minY = screenVirtualY(screens[0])
        var maxX = screenVirtualX(screens[0]) + screenPixelW(screens[0])
        var maxY = screenVirtualY(screens[0]) + screenPixelH(screens[0])
        for (var i = 1; i < screens.length; i++) {
            var s = screens[i]
            minX = Math.min(minX, screenVirtualX(s))
            minY = Math.min(minY, screenVirtualY(s))
            maxX = Math.max(maxX, screenVirtualX(s) + screenPixelW(s))
            maxY = Math.max(maxY, screenVirtualY(s) + screenPixelH(s))
        }
        return {
            "x": minX,
            "y": minY,
            "w": Math.max(1, maxX - minX),
            "h": Math.max(1, maxY - minY)
        }
    }

    function screenContainsPoint(screenObj, px, py) {
        if (!screenObj) return false
        var sx = screenVirtualX(screenObj)
        var sy = screenVirtualY(screenObj)
        var sw = screenPixelW(screenObj)
        var sh = screenPixelH(screenObj)
        return px >= sx && px < (sx + sw) && py >= sy && py < (sy + sh)
    }

    function screenForPoint(px, py, fallbackScreen) {
        var screens = allScreensList()
        if (!screens || screens.length === 0) return fallbackScreen ? fallbackScreen : null
        for (var i = 0; i < screens.length; i++) {
            if (screenContainsPoint(screens[i], px, py)) {
                return screens[i]
            }
        }
        if (fallbackScreen) return fallbackScreen
        return screens[0]
    }

    function visibleRectForScreen(screenObj) {
        if (!screenObj) {
            return { "x": 0, "y": 0, "w": Math.max(1, width), "h": Math.max(1, height) }
        }
        if (screenObj.availableGeometry
            && typeof screenObj.availableGeometry.x === "number"
            && typeof screenObj.availableGeometry.y === "number"
            && typeof screenObj.availableGeometry.width === "number"
            && typeof screenObj.availableGeometry.height === "number") {
            return {
                "x": Math.round(screenObj.availableGeometry.x),
                "y": Math.round(screenObj.availableGeometry.y),
                "w": Math.max(1, Math.round(screenObj.availableGeometry.width)),
                "h": Math.max(1, Math.round(screenObj.availableGeometry.height))
            }
        }
        return {
            "x": Math.round(screenVirtualX(screenObj)),
            "y": Math.round(screenVirtualY(screenObj)),
            "w": Math.max(1, Math.round(screenPixelW(screenObj))),
            "h": Math.max(1, Math.round(screenPixelH(screenObj)))
        }
    }

    function sameScreen(a, b) {
        if (!a || !b) return false
        return screenVirtualX(a) === screenVirtualX(b)
            && screenVirtualY(a) === screenVirtualY(b)
            && screenPixelW(a) === screenPixelW(b)
            && screenPixelH(a) === screenPixelH(b)
    }

    function contentOwningScreen() {
        var screens = allScreensList()
        if (!screens || screens.length === 0) return null
        var contentRect = currentContentRect()
        var cx = contentRect.x + (contentRect.w / 2.0)
        var cy = contentRect.y + (contentRect.h / 2.0)
        for (var i = 0; i < screens.length; i++) {
            if (screenContainsPoint(screens[i], cx, cy)) {
                return screens[i]
            }
        }
        if (floatWin.screen) return floatWin.screen
        return screens[0]
    }

    function adjacentScreenForDirection(direction, baseScreen) {
        var dir = (direction < 0) ? -1 : 1
        var screens = allScreensList()
        if (!screens || screens.length < 2) return null
        var current = baseScreen ? baseScreen : contentOwningScreen()
        if (!current) return null

        var currentCx = screenVirtualX(current) + (screenPixelW(current) / 2.0)
        var currentCy = screenVirtualY(current) + (screenPixelH(current) / 2.0)
        var best = null
        var bestScore = 0
        for (var i = 0; i < screens.length; i++) {
            var s = screens[i]
            if (!s || sameScreen(s, current)) continue
            var sx = screenVirtualX(s) + (screenPixelW(s) / 2.0)
            var sy = screenVirtualY(s) + (screenPixelH(s) / 2.0)
            var dx = sx - currentCx
            if ((dir > 0 && dx <= 0) || (dir < 0 && dx >= 0)) continue
            var score = Math.abs(dx) * 10000 + Math.abs(sy - currentCy)
            if (!best || score < bestScore) {
                best = s
                bestScore = score
            }
        }
        if (best) return best

        var sorted = screens.slice(0).sort(function(a, b) {
            if (screenVirtualX(a) === screenVirtualX(b)) {
                return screenVirtualY(a) - screenVirtualY(b)
            }
            return screenVirtualX(a) - screenVirtualX(b)
        })
        var currentSortedIdx = -1
        for (var j = 0; j < sorted.length; j++) {
            if (sameScreen(sorted[j], current)) {
                currentSortedIdx = j
                break
            }
        }
        if (currentSortedIdx < 0) return null
        var nextIdx = currentSortedIdx + dir
        if (nextIdx < 0 || nextIdx >= sorted.length) return null
        return sorted[nextIdx]
    }

    function requestAdjacentScreenMove(direction, sourceTag, sourceSnapshot) {
        var dir = (direction < 0) ? -1 : 1
        return moveWindowToAdjacentScreen(dir, sourceSnapshot)
    }

    onOsWinShiftMoveSeqChanged: {
        var dir = (osWinShiftMoveDirection < 0) ? -1 : ((osWinShiftMoveDirection > 0) ? 1 : 0)
        if (dir === 0) return
        var sourceSnapshot = {
            "finalX": osWinShiftSourceFinalX,
            "finalY": osWinShiftSourceFinalY,
            "finalW": osWinShiftSourceFinalW,
            "finalH": osWinShiftSourceFinalH,
            "rectX": osWinShiftSourceRectX,
            "rectY": osWinShiftSourceRectY,
            "rectW": osWinShiftSourceRectW,
            "rectH": osWinShiftSourceRectH
        }
        requestAdjacentScreenMove(dir, "Win+Shift native override", sourceSnapshot)
    }

    function moveWindowToAdjacentScreen(direction, sourceSnapshot) {
        if (isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false
        if (userMoveInProgress) finishUserDrag()
        if (_interactionEnvelopePadApplied > 0 || _interactionEnvelopeActive || dragFxReleaseAnimation.running) {
            collapseInteractionEnvelopeNow()
        }

        var hasSnapshot = !!(sourceSnapshot
            && typeof sourceSnapshot.finalX === "number"
            && typeof sourceSnapshot.finalY === "number"
            && typeof sourceSnapshot.finalW === "number"
            && typeof sourceSnapshot.finalH === "number"
            && typeof sourceSnapshot.rectX === "number"
            && typeof sourceSnapshot.rectY === "number"
            && typeof sourceSnapshot.rectW === "number"
            && typeof sourceSnapshot.rectH === "number"
            && sourceSnapshot.finalW > 0
            && sourceSnapshot.finalH > 0
            && sourceSnapshot.rectW > 0
            && sourceSnapshot.rectH > 0)

        var srcContentRect = currentContentRect()
        var srcFinalX = srcContentRect.x
        var srcFinalY = srcContentRect.y
        var srcFinalW = srcContentRect.w
        var srcFinalH = srcContentRect.h
        var srcRect = activeVisibleRectForMaximize()
        var sourceScreen = contentOwningScreen()
        if (hasSnapshot) {
            srcFinalX = Math.round(sourceSnapshot.finalX)
            srcFinalY = Math.round(sourceSnapshot.finalY)
            srcFinalW = Math.max(1, Math.round(sourceSnapshot.finalW))
            srcFinalH = Math.max(1, Math.round(sourceSnapshot.finalH))
            srcRect = {
                "x": Math.round(sourceSnapshot.rectX),
                "y": Math.round(sourceSnapshot.rectY),
                "w": Math.max(1, Math.round(sourceSnapshot.rectW)),
                "h": Math.max(1, Math.round(sourceSnapshot.rectH))
            }
            sourceScreen = screenForPoint(srcRect.x + (srcRect.w / 2.0), srcRect.y + (srcRect.h / 2.0), sourceScreen)
        }

        if (!uiMaximized) {
            var srcRectLooksLikeWindow = Math.abs(srcRect.w - srcFinalW) <= 2
                && Math.abs(srcRect.h - srcFinalH) <= 2
            if (srcRectLooksLikeWindow && sourceScreen) {
                var sourceVisible = visibleRectForScreen(sourceScreen)
                if (sourceVisible && sourceVisible.w > 0 && sourceVisible.h > 0) {
                    srcRect = sourceVisible
                }
            }
        }

        var destScreen = adjacentScreenForDirection(direction, sourceScreen)
        if (!destScreen) return false
        var destRect = visibleRectForScreen(destScreen)
        if (!destRect || destRect.w <= 0 || destRect.h <= 0) return false

        if (uiMaximized) {
            x = Math.round(destRect.x)
            y = Math.round(destRect.y)
            width = Math.max(1, Math.round(destRect.w))
            height = Math.max(1, Math.round(destRect.h))
            refreshActiveVisibleRect()
            return true
        }

        var srcW = Math.max(1, srcRect.w)
        var srcH = Math.max(1, srcRect.h)
        var relX = (srcFinalX - srcRect.x) / srcW
        var relY = (srcFinalY - srcRect.y) / srcH
        var relW = srcFinalW / srcW
        var relH = srcFinalH / srcH

        var minW = ratioToPixels(layoutRatios.resizeMinWidthPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1)
        var minH = ratioToPixels(layoutRatios.resizeMinHeightPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1)
        var nextW = clampNumber(Math.round(destRect.w * relW), minW, Math.max(1, destRect.w))
        var nextH = clampNumber(Math.round(destRect.h * relH), minH, Math.max(1, destRect.h))
        var nextX = Math.round(destRect.x + (destRect.w * relX))
        var nextY = Math.round(destRect.y + (destRect.h * relY))
        nextX = Math.round(clampNumber(nextX, destRect.x, destRect.x + destRect.w - nextW))
        nextY = Math.round(clampNumber(nextY, destRect.y, destRect.y + destRect.h - nextH))

        x = nextX
        y = nextY
        width = Math.max(1, Math.round(nextW))
        height = Math.max(1, Math.round(nextH))
        rememberRestoreGeometry()
        refreshActiveVisibleRect()
        return true
    }

    function refreshActiveVisibleRect() {
        var contentRect = currentContentRect()
        var cx = contentRect.x + (Math.max(1, contentRect.w) / 2.0)
        var cy = contentRect.y + (Math.max(1, contentRect.h) / 2.0)
        var sc = screenForPoint(cx, cy, floatWin.screen ? floatWin.screen : null)
        var rect = visibleRectForScreen(sc)
        activeVisibleRect = {
            "x": Math.round(rect.x),
            "y": Math.round(rect.y),
            "w": Math.max(1, Math.round(rect.w)),
            "h": Math.max(1, Math.round(rect.h))
        }
        if (!userMoveInProgress) {
            metricsMonitorW = activeVisibleRect.w
            metricsMonitorH = activeVisibleRect.h
        }
        if (!_interactionEnvelopeMutating) {
            syncInteractionEnvelopePad()
        }
    }

    function activeVisibleRectForMaximize() {
        if (activeVisibleRect && activeVisibleRect.w > 0 && activeVisibleRect.h > 0) {
            return activeVisibleRect
        }
        var contentRect = currentContentRect()
        return {
            "x": Math.round(contentRect.x),
            "y": Math.round(contentRect.y),
            "w": Math.max(1, Math.round(contentRect.w)),
            "h": Math.max(1, Math.round(contentRect.h))
        }
    }

    function readCursorGlobalPos() {
        if (appRef && appRef.getCursorGlobalPos) {
            var pos = appRef.getCursorGlobalPos()
            if (pos
                && typeof pos.x === "number"
                && typeof pos.y === "number"
                && isFinite(pos.x)
                && isFinite(pos.y)) {
                return { "x": pos.x, "y": pos.y }
            }
        }
        return null
    }

    function clampWindowToRect(rectObj) {
        if (!rectObj || rectObj.w <= 0 || rectObj.h <= 0) return false
        var contentRect = currentContentRect()
        var nextX = Math.round(contentRect.x)
        var nextY = Math.round(contentRect.y)
        var winW = Math.max(1, Math.round(contentRect.w))
        var winH = Math.max(1, Math.round(contentRect.h))
        var minX = Math.round(rectObj.x)
        var minY = Math.round(rectObj.y)
        var maxX = Math.round(rectObj.x + rectObj.w - winW)
        var maxY = Math.round(rectObj.y + rectObj.h - winH)
        if (maxX < minX) maxX = minX
        if (maxY < minY) maxY = minY
        nextX = Math.max(minX, Math.min(nextX, maxX))
        nextY = Math.max(minY, Math.min(nextY, maxY))
        if (nextX === contentRect.x && nextY === contentRect.y) return false
        var pad = Math.max(0, Math.round(_interactionEnvelopePadApplied))
        x = Math.round(nextX - pad)
        y = Math.round(nextY - pad)
        return true
    }

    function topEdgeSnapTargetForDragRelease() {
        if (!userMoveInProgress || uiMaximized) return null
        var screens = allScreensList()
        if (!screens || screens.length <= 0) return null

        var contentRect = currentContentRect()
        var winLeft = Math.round(contentRect.x)
        var winTop = Math.round(contentRect.y)
        var winRight = Math.round(contentRect.x + contentRect.w)
        var winBottom = Math.round(contentRect.y + contentRect.h)

        var framePad = Math.max(1, Math.ceil(Math.max(monitorFrameThickness, monitorFrameGlowThickness * 0.50)))
        var best = null
        var bestOverlapW = 0
        for (var i = 0; i < screens.length; i++) {
            var screenObj = screens[i]
            if (!screenObj) continue

            var rectObj = visibleRectForScreen(screenObj)
            if (!rectObj || rectObj.w <= 0 || rectObj.h <= 0) continue

            var rectLeft = Math.round(rectObj.x)
            var rectTop = Math.round(rectObj.y)
            var rectRight = Math.round(rectLeft + rectObj.w)
            var overlapW = Math.min(winRight, rectRight) - Math.max(winLeft, rectLeft)
            if (overlapW <= 0) continue

            var topBandMin = rectTop - framePad
            var topBandMax = rectTop + framePad
            if (winTop > topBandMax || winBottom < topBandMin) continue
            if (!best || overlapW > bestOverlapW) {
                best = { "screen": screenObj, "index": i, "rect": rectObj }
                bestOverlapW = overlapW
            }
        }
        return best
    }

    function shouldSnapMaximizeOnDragRelease() {
        return topEdgeSnapTargetForDragRelease() !== null
    }

    function rememberRestoreGeometry() {
        var contentRect = currentContentRect()
        restoreFinalX = Math.round(contentRect.x)
        restoreFinalY = Math.round(contentRect.y)
        restoreFinalW = Math.max(1, Math.round(contentRect.w))
        restoreFinalH = Math.max(1, Math.round(contentRect.h))
        restoreGeometryValid = true
    }

    function computeStartGeometry() {
        if (!validRectLike(originRect)) {
            var fb = validRectLike(hostWindowRect)
                ? hostWindowRect
                : Qt.rect(0, 0, Math.max(1, width), Math.max(1, height))
            return {
                "x": Math.round(fb.x + (fb.width * 0.35)),
                "y": Math.round(fb.y + (fb.height * 0.32)),
                "w": Math.max(1, Math.round(fb.width * 0.30)),
                "h": Math.max(1, Math.round(fb.height * 0.20))
            }
        }
        return {
            "x": Math.round(originRect.x),
            "y": Math.round(originRect.y),
            "w": Math.max(1, Math.round(originRect.width)),
            "h": Math.max(1, Math.round(originRect.height))
        }
    }

    function computeFinalGeometry() {
        var baseRect = validRectLike(hostWindowRect)
            ? hostWindowRect
            : Qt.rect(0, 0, 1220, 920)

        var cx = baseRect.x + (baseRect.width / 2.0)
        var cy = baseRect.y + (baseRect.height / 2.0)
        var targetScreen = screenForPoint(cx, cy, floatWin.screen ? floatWin.screen : null)
        var visibleRect = visibleRectForScreen(targetScreen)

        var fallbackW = Math.max(1, Math.round(visibleRect.w * layoutRatios.fallbackWidthPct))
        var fallbackH = Math.max(1, Math.round(visibleRect.h * layoutRatios.fallbackHeightPct))
        var targetW = Math.max(1, Math.round(validRectLike(baseRect) ? baseRect.width : fallbackW))
        var targetH = Math.max(1, Math.round(validRectLike(baseRect) ? baseRect.height : fallbackH))

        var dx = Math.max(1, ratioToPixels(layoutRatios.spawnOffsetXPct, targetW, targetH, 1))
        var dy = Math.max(1, ratioToPixels(layoutRatios.spawnOffsetYPct, targetW, targetH, 1))
        var targetX = Math.round(baseRect.x + dx)
        var targetY = Math.round(baseRect.y - dy)

        var minX = visibleRect.x
        var minY = visibleRect.y
        var maxX = visibleRect.x + visibleRect.w - targetW
        var maxY = visibleRect.y + visibleRect.h - targetH
        if (maxX < minX) maxX = minX
        if (maxY < minY) maxY = minY

        targetX = Math.max(minX, Math.min(targetX, maxX))
        targetY = Math.max(minY, Math.min(targetY, maxY))
        return { "x": targetX, "y": targetY, "w": targetW, "h": targetH }
    }

    function resolveRestoreRectFromMaximized(cursorPos, cursorAnchored) {
        var restoreRect = restoreGeometryValid
            ? { "x": restoreFinalX, "y": restoreFinalY, "w": restoreFinalW, "h": restoreFinalH }
            : {
                "x": Math.round(x + (width * 0.09)),
                "y": Math.round(y + (height * 0.08)),
                "w": Math.max(1, Math.round(width * 0.82)),
                "h": Math.max(1, Math.round(height * 0.82))
            }

        var nextX = Math.round(restoreRect.x)
        var nextY = Math.round(restoreRect.y)
        var nextW = Math.max(1, Math.round(restoreRect.w))
        var nextH = Math.max(1, Math.round(restoreRect.h))

        if (cursorAnchored && cursorPos && isFinite(cursorPos.x) && isFinite(cursorPos.y)) {
            var vis = activeVisibleRectForMaximize()
            var ratioX = 0.5
            if (vis && vis.w > 0) {
                ratioX = Math.max(0.10, Math.min(0.90, (cursorPos.x - vis.x) / vis.w))
            }
            nextX = Math.round(cursorPos.x - (nextW * ratioX))
            nextY = Math.round(cursorPos.y - Math.max(1, Math.round(ratioToPixels(0.030, nextW, nextH, 14))))
        }
        return {
            "x": nextX,
            "y": nextY,
            "w": nextW,
            "h": nextH
        }
    }

    function restoreFromMaximizedForDrag(cursorPos) {
        if (!uiMaximized || maximizeAnimInProgress || isMinimizing || isRestoringFromMinimize) return false
        var targetRect = resolveRestoreRectFromMaximized(cursorPos, true)
        uiMaximized = false
        x = targetRect.x
        y = targetRect.y
        width = targetRect.w
        height = targetRect.h
        refreshActiveVisibleRect()
        return true
    }

    function applyFallbackDragFromCursor() {
        if (!userMoveInProgress || dragStrategy !== "fallback") return false
        var pos = readCursorGlobalPos()
        if (!pos) return false
        if (!dragHasCursorAnchor) {
            dragStartCursorX = pos.x
            dragStartCursorY = pos.y
            _dragStartWindowX = x
            _dragStartWindowY = y
            dragHasCursorAnchor = true
            return true
        }

        var dx = pos.x - dragStartCursorX
        var dy = pos.y - dragStartCursorY
        if (!isFinite(dx) || !isFinite(dy)) return false
        if (dx === 0 && dy === 0) return true

        var nextX = Math.round(_dragStartWindowX + dx)
        var nextY = Math.round(_dragStartWindowY + dy)
        if (nextX === x && nextY === y) {
            dragStartCursorX = pos.x
            dragStartCursorY = pos.y
            _dragStartWindowX = x
            _dragStartWindowY = y
            return true
        }

        x = nextX
        y = nextY
        refreshActiveVisibleRect()
        applyDragFxFromDelta(dx, dy)
        syncInteractionEnvelopePad()
        dragStartCursorX = pos.x
        dragStartCursorY = pos.y
        _dragStartWindowX = x
        _dragStartWindowY = y
        return true
    }

    function beginHeaderDrag(translationX, translationY) {
        if (_closeStarted || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false
        if (uiMaximized) {
            if (typeof translationY === "number" && translationY <= 0) {
                return false
            }
            var cursorPos = readCursorGlobalPos()
            if (!restoreFromMaximizedForDrag(cursorPos)) {
                return false
            }
        }
        userMoveInProgress = true
        dragStrategy = "fallback"
        dragHasCursorAnchor = false
        _dragStartWindowX = x
        _dragStartWindowY = y
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop()
        }
        setInteractionEnvelopeActive(true)
        resetDragFxState()
        if (!preferTranslationDrag) {
            applyFallbackDragFromCursor()
        }
        return true
    }

    function updateUserDrag(translationX, translationY) {
        if (isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false
        if (!userMoveInProgress || dragStrategy !== "fallback") return false
        var hasTranslation = isFinite(translationX) && isFinite(translationY)
        var useTranslation = preferTranslationDrag && hasTranslation
        if (!useTranslation) {
            if (applyFallbackDragFromCursor()) return true
        }

        var tx = isFinite(translationX) ? translationX : 0
        var ty = isFinite(translationY) ? translationY : 0
        var nextX = Math.round(_dragStartWindowX + tx)
        var nextY = Math.round(_dragStartWindowY + ty)
        if (nextX !== x || nextY !== y) {
            var dx = nextX - x
            var dy = nextY - y
            x = nextX
            y = nextY
            refreshActiveVisibleRect()
            applyDragFxFromDelta(dx, dy)
            syncInteractionEnvelopePad()
        }
        return true
    }

    function lockDragReleaseCenter(targetCenterX, targetCenterY) {
        if (!isFinite(targetCenterX) || !isFinite(targetCenterY)) return false
        if (!isFinite(width) || !isFinite(height) || width <= 0 || height <= 0) return false

        var nextX = Math.round(targetCenterX - (width / 2.0))
        var nextY = Math.round(targetCenterY - (height / 2.0))
        if (nextX === x && nextY === y) return false

        console.log("[DRAG-TRACE][FLOAT] release-center-lock from="
            + Math.round(x) + "," + Math.round(y)
            + " to=" + nextX + "," + nextY
            + " center=(" + Math.round(targetCenterX) + "," + Math.round(targetCenterY) + ")")
        x = nextX
        y = nextY
        return true
    }

    function finishUserDrag() {
        if (!userMoveInProgress) return true
        var releaseCenterX = Math.round(x + (width / 2.0))
        var releaseCenterY = Math.round(y + (height / 2.0))
        console.log("[DRAG-TRACE][FLOAT] release-start center=(" + releaseCenterX + "," + releaseCenterY + ")")
        if (dragReleaseCursorSampleEnabled) {
            applyFallbackDragFromCursor()
        }
        var snapTarget = dragReleaseSnapEnabled ? topEdgeSnapTargetForDragRelease() : null
        if (snapTarget) {
            rememberRestoreGeometry()
            maximizeWindowToVisibleRect(snapTarget.screen)
            userMoveInProgress = false
            dragStrategy = "none"
            dragHasCursorAnchor = false
            _interactionEnvelopeActive = false
            releaseDragFxToSettled()
            return true
        }
        if (dragReleaseSnapEnabled) {
            clampWindowToRect(activeVisibleRectForMaximize())
        }
        if (dragReleaseCenterLockEnabled && !uiMaximized) {
            lockDragReleaseCenter(releaseCenterX, releaseCenterY)
        }
        userMoveInProgress = false
        dragStrategy = "none"
        dragHasCursorAnchor = false
        _interactionEnvelopeActive = false
        refreshActiveVisibleRect()
        if (!uiMaximized) rememberRestoreGeometry()
        releaseDragFxToSettled()
        console.log("[DRAG-TRACE][FLOAT] release-settled center=("
            + Math.round(x + (width / 2.0)) + "," + Math.round(y + (height / 2.0)) + ")")
        return true
    }

    function syncDragContentPosition() {
        refreshActiveVisibleRect()
    }

    function updateTargetScreenFromFinalCenter() {
        refreshActiveVisibleRect()
        return true
    }

    function updateCanvasGeometry() {
        refreshActiveVisibleRect()
        return true
    }

    function maximizeWindowToVisibleRect(screenOverride) {
        if (maximizeAnimInProgress || isMinimizing || isRestoringFromMinimize) return false
        collapseInteractionEnvelopeNow()
        if (screenOverride) {
            if (!floatWin.screen || !sameScreen(floatWin.screen, screenOverride)) {
                floatWin.screen = screenOverride
            }
            var overrideVis = visibleRectForScreen(screenOverride)
            activeVisibleRect = {
                "x": Math.round(overrideVis.x),
                "y": Math.round(overrideVis.y),
                "w": Math.max(1, Math.round(overrideVis.w)),
                "h": Math.max(1, Math.round(overrideVis.h))
            }
        } else {
            refreshActiveVisibleRect()
        }
        var vis = activeVisibleRectForMaximize()
        if (!vis || vis.w <= 0 || vis.h <= 0) return false

        var sourceRect = currentContentRect()
        var sourceX = sourceRect.x
        var sourceY = sourceRect.y
        var sourceW = sourceRect.w
        var sourceH = sourceRect.h
        if (dragFxReleaseAnimation.running) dragFxReleaseAnimation.stop()
        resetDragFxState()

        maximizeAnimInProgress = true
        uiMaximized = true
        x = Math.round(vis.x)
        y = Math.round(vis.y)
        width = Math.max(1, Math.round(vis.w))
        height = Math.max(1, Math.round(vis.h))
        seedMaximizeFxFromSourceRect(
            sourceX, sourceY, sourceW, sourceH,
            x, y, width, height
        )
        refreshActiveVisibleRect()
        maximizeFxAnimation.restart()
        return true
    }

    function restoreFromMaximized(cursorPos, cursorAnchored) {
        if (!uiMaximized || maximizeAnimInProgress || isMinimizing || isRestoringFromMinimize) return false
        collapseInteractionEnvelopeNow()
        var sourceRect = currentContentRect()
        var sourceX = sourceRect.x
        var sourceY = sourceRect.y
        var sourceW = sourceRect.w
        var sourceH = sourceRect.h

        var targetRect = resolveRestoreRectFromMaximized(cursorPos, cursorAnchored)
        if (dragFxReleaseAnimation.running) dragFxReleaseAnimation.stop()
        resetDragFxState()

        maximizeAnimInProgress = true
        uiMaximized = false
        x = Math.round(targetRect.x)
        y = Math.round(targetRect.y)
        width = Math.max(1, Math.round(targetRect.w))
        height = Math.max(1, Math.round(targetRect.h))
        seedMaximizeFxFromSourceRect(
            sourceX, sourceY, sourceW, sourceH,
            x, y, width, height
        )
        refreshActiveVisibleRect()
        maximizeRestoreFxAnimation.restart()
        return true
    }

    function toggleWindowMaximize() {
        if (userMoveInProgress) finishUserDrag()
        if (_interactionEnvelopePadApplied > 0 || _interactionEnvelopeActive || dragFxReleaseAnimation.running) {
            collapseInteractionEnvelopeNow()
        }
        if (uiMaximized) return restoreFromMaximized(null, false)
        rememberRestoreGeometry()
        return maximizeWindowToVisibleRect()
    }

    function requestMinimizeAnimation() {
        if (isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false
        if (userMoveInProgress) finishUserDrag()
        if (_interactionEnvelopePadApplied > 0 || _interactionEnvelopeActive || dragFxReleaseAnimation.running) {
            collapseInteractionEnvelopeNow()
        }
        stopMaximizeFxAnimations()
        if (!uiMaximized) rememberRestoreGeometry()
        isMinimizing = true
        minimizeRestorePending = true
        minimizeCloseAnim.restart()
        return true
    }

    function requestCloseAnimation() {
        if (isClosing || isMinimizing || isRestoringFromMinimize) return false
        if (userMoveInProgress) finishUserDrag()
        if (_interactionEnvelopePadApplied > 0 || _interactionEnvelopeActive || dragFxReleaseAnimation.running) {
            collapseInteractionEnvelopeNow()
        }
        stopMaximizeFxAnimations()
        isClosing = true
        isMinimizing = false
        isRestoringFromMinimize = false
        wasWindowMinimized = false
        minimizeRestorePending = false
        closeAnim.restart()
        return true
    }

    function openThemePicker() {
        if (!themePicker) return false
        if (settingsMenu && settingsMenu.opened) settingsMenu.close()
        var rightInset = ratioToPixels(layoutRatios.themePickerRightPct, Math.max(1, width), Math.max(1, height), 1)
        var topInset = ratioToPixels(layoutRatios.themePickerTopPct, Math.max(1, width), Math.max(1, height), 1)
        themePicker.x = Math.max(0, Math.round(width - themePicker.width - rightInset))
        themePicker.y = Math.max(0, Math.round(topInset))
        themePicker.open()
        themePicker.forceActiveFocus()
        return true
    }

    function openSettingsMenu() {
        if (!settingsMenu) return false
        if (themePicker && themePicker.opened) themePicker.close()
        floatWin.syncSoundEffectsFromApp()
        var rightInset = ratioToPixels(layoutRatios.themePickerRightPct, Math.max(1, width), Math.max(1, height), 1)
        var topInset = ratioToPixels(layoutRatios.themePickerTopPct, Math.max(1, width), Math.max(1, height), 1)
        settingsMenu.x = Math.max(0, Math.round(width - settingsMenu.width - rightInset))
        settingsMenu.y = Math.max(0, Math.round(topInset))
        settingsMenu.open()
        settingsMenu.forceActiveFocus()
        return true
    }

    function closeForAppExit() {
        if (_exitDestroying) return
        _exitDestroying = true
        _closeStarted = true
        stopMaximizeFxAnimations()
        visible = false
        close()
        Qt.callLater(function() {
            try {
                floatWin.destroy()
            } catch (e) {
            }
        })
    }

    onXChanged: refreshActiveVisibleRect()
    onYChanged: refreshActiveVisibleRect()
    onWidthChanged: refreshActiveVisibleRect()
    onHeightChanged: refreshActiveVisibleRect()
    onScreenChanged: refreshActiveVisibleRect()

    onVisibilityChanged: {
        if (visibility === Window.Minimized) {
            wasWindowMinimized = true
            isMinimizing = false
            isRestoringFromMinimize = false
            return
        }
        if (_closeStarted || _exitDestroying) {
            return
        }
        if (wasWindowMinimized && minimizeRestorePending && !isRestoringFromMinimize) {
            wasWindowMinimized = false
            isRestoringFromMinimize = true
            minimizeRestoreOpenAnim.restart()
            return
        }
    }

    onClosing: function(closeEvent) {
        if (!_closeStarted && !_exitDestroying && !isClosing) {
            closeEvent.accepted = false
            requestCloseAnimation()
            return
        }
        _closeStarted = true
        stopMaximizeFxAnimations()
        isMinimizing = false
        isRestoringFromMinimize = false
        emitDidCloseOnce()
        closeEvent.accepted = true
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            floatWin.closeForAppExit()
        }
    }

    Shortcut {
        sequence: "Ctrl+Shift+Left"
        context: Qt.WindowShortcut
        autoRepeat: false
        onActivated: floatWin.requestAdjacentScreenMove(-1, "Ctrl+Shift+Left")
    }

    Shortcut {
        sequence: "Ctrl+Shift+Right"
        context: Qt.WindowShortcut
        autoRepeat: false
        onActivated: floatWin.requestAdjacentScreenMove(1, "Ctrl+Shift+Right")
    }

    Timer {
        id: fallbackDragTick
        interval: 8
        repeat: true
        running: floatWin.userMoveInProgress
            && floatWin.dragStrategy === "fallback"
            && floatWin.dragPollingEnabled
        onTriggered: {
            floatWin.applyFallbackDragFromCursor()
        }
    }

    ParallelAnimation {
        id: dragFxReleaseAnimation
        running: false

        NumberAnimation {
            target: floatWin
            property: "dragFxScaleX"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.dragFxReleaseDurationPct, 170)
            easing.type: Easing.OutBack
        }
        NumberAnimation {
            target: floatWin
            property: "dragFxScaleY"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.dragFxReleaseDurationPct, 170)
            easing.type: Easing.OutBack
        }
        NumberAnimation {
            target: floatWin
            property: "dragFxTransX"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.dragFxReleaseDurationPct * 0.84, 140)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "dragFxTransY"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.dragFxReleaseDurationPct * 0.84, 140)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "dragFxRotate"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.dragFxReleaseDurationPct * 0.90, 150)
            easing.type: Easing.OutCubic
        }
        onStopped: {
            floatWin.syncInteractionEnvelopePad()
        }
    }

    ParallelAnimation {
        id: maximizeFxAnimation
        running: false

        NumberAnimation {
            target: floatWin
            property: "maximizeFxScaleX"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxScaleY"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxTransX"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxTransY"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxRotate"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        onStopped: {
            floatWin.maximizeAnimInProgress = false
            floatWin.resetMaximizeFxState()
        }
    }

    ParallelAnimation {
        id: maximizeRestoreFxAnimation
        running: false

        NumberAnimation {
            target: floatWin
            property: "maximizeFxScaleX"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxScaleY"
            to: 1.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxTransX"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxTransY"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: floatWin
            property: "maximizeFxRotate"
            to: 0.0
            duration: floatWin.transitionDurationMs(floatWin.layoutRatios.maximizeFxDurationPct, 210)
            easing.type: Easing.OutCubic
        }
        onStopped: {
            floatWin.maximizeAnimInProgress = false
            floatWin.resetMaximizeFxState()
            if (!floatWin.uiMaximized) {
                floatWin.rememberRestoreGeometry()
            }
        }
    }

    SequentialAnimation {
        id: closeAnim
        running: false

        ScriptAction {
            script: {
                floatWin.resetMinimizeFxState()
                contentLayer.opacity = 1.0
            }
        }
        ParallelAnimation {
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleX"
                to: 0.10
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 1.08, 210)
                easing.type: Easing.InBack
                easing.overshoot: 1.20
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleY"
                to: 0.07
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 1.08, 210)
                easing.type: Easing.InBack
                easing.overshoot: 1.20
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxRotate"
                to: 5.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.92, 180)
                easing.type: Easing.InQuad
            }
            NumberAnimation {
                target: contentLayer
                property: "opacity"
                to: 0.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.92, 180)
                easing.type: Easing.InQuad
            }
        }
        ScriptAction {
            script: {
                floatWin._closeStarted = true
                floatWin.close()
            }
        }
    }

    SequentialAnimation {
        id: minimizeCloseAnim
        running: false

        ScriptAction {
            script: {
                floatWin.resetMinimizeFxState()
                contentLayer.opacity = 1.0
            }
        }
        ParallelAnimation {
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleX"
                to: 0.24
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 190)
                easing.type: Easing.InBack
                easing.overshoot: 1.15
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleY"
                to: 0.15
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 190)
                easing.type: Easing.InBack
                easing.overshoot: 1.15
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxTransY"
                to: Math.max(1, Math.round(floatWin.height * 0.34))
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 190)
                easing.type: Easing.InQuad
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxRotate"
                to: 3.5
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.84, 150)
                easing.type: Easing.InQuad
            }
            NumberAnimation {
                target: contentLayer
                property: "opacity"
                to: 0.70
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.84, 150)
                easing.type: Easing.InQuad
            }
        }
        ScriptAction {
            script: {
                floatWin.resetMinimizeFxState()
                contentLayer.opacity = 1.0
                floatWin.showMinimized()
                floatWin.isMinimizing = false
            }
        }
    }

    SequentialAnimation {
        id: minimizeRestoreOpenAnim
        running: false

        ScriptAction {
            script: {
                floatWin.resetMinimizeFxState()
                floatWin.minimizeFxScaleX = 0.24
                floatWin.minimizeFxScaleY = 0.15
                floatWin.minimizeFxTransX = 0.0
                floatWin.minimizeFxTransY = Math.max(1, Math.round(floatWin.height * 0.34))
                floatWin.minimizeFxRotate = 3.5
                contentLayer.opacity = 1.0
            }
        }
        ParallelAnimation {
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleX"
                to: 1.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 200)
                easing.type: Easing.OutBack
                easing.overshoot: 1.0
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxScaleY"
                to: 1.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 200)
                easing.type: Easing.OutBack
                easing.overshoot: 1.0
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxTransY"
                to: 0.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct, 200)
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: floatWin
                property: "minimizeFxRotate"
                to: 0.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.90, 180)
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: contentLayer
                property: "opacity"
                to: 1.0
                duration: floatWin.transitionDurationMs(floatWin.layoutRatios.minimizeFxDurationPct * 0.90, 180)
                easing.type: Easing.OutCubic
            }
        }
        ScriptAction {
            script: {
                floatWin.isRestoringFromMinimize = false
                floatWin.minimizeRestorePending = false
                floatWin.resetMinimizeFxState()
            }
        }
    }

    Item {
        id: contentLayer
        x: floatWin.contentInsetPx
        y: floatWin.contentInsetPx
        width: floatWin.contentAreaW
        height: floatWin.contentAreaH
        transform: [
            Scale {
                id: openScale
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
            },
            Rotation {
                id: openRotation
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                axis.z: 1
            },
            Scale {
                id: dragFxScale
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                xScale: floatWin.dragFxScaleX
                yScale: floatWin.dragFxScaleY
            },
            Translate {
                x: floatWin.dragFxTransX
                y: floatWin.dragFxTransY
            },
            Rotation {
                id: dragFxRotation
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                axis.z: 1
                angle: floatWin.dragFxRotate
            },
            Scale {
                id: maximizeFxScale
                origin.x: contentLayer.width
                origin.y: 0
                xScale: floatWin.maximizeFxScaleX
                yScale: floatWin.maximizeFxScaleY
            },
            Translate {
                x: floatWin.maximizeFxTransX
                y: floatWin.maximizeFxTransY
            },
            Rotation {
                id: maximizeFxRotation
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                axis.z: 1
                angle: floatWin.maximizeFxRotate
            },
            Scale {
                id: minimizeFxScale
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                xScale: floatWin.minimizeFxScaleX
                yScale: floatWin.minimizeFxScaleY
            },
            Translate {
                x: floatWin.minimizeFxTransX
                y: floatWin.minimizeFxTransY
            },
            Rotation {
                id: minimizeFxRotation
                origin.x: contentLayer.width / 2
                origin.y: contentLayer.height / 2
                axis.z: 1
                angle: floatWin.minimizeFxRotate
            }
        ]

        ChromeSurface {
            anchors.fill: parent
            t: floatWin.t
            metrics: floatWin.uiMetrics
            premiumEdgeEnabled: true
            flairEnabled: true
            interactionBoost: floatWin.userMoveInProgress ? 0.14 : 0.05

            MainContent {
                id: mainContent
                anchors.fill: parent
                t: floatWin.t
                metrics: floatWin.uiMetrics
                appRef: floatWin.appRef
                windowRef: floatWin
                isInteractive: true
                initialTileIndex: floatWin.initialTileIndex
                initialPanelState: floatWin.initialPanelState
                detachedWindow: true
                onTearAwayRequested: function(tileIndex, titleText, state, originRect) {
                    floatWin.requestDetach(tileIndex, titleText, state, originRect)
                    if (mainContent.startPortalReverseTransition) {
                        Qt.callLater(function() {
                            try {
                                mainContent.startPortalReverseTransition(tileIndex)
                            } catch (e) {
                            }
                        })
                    }
                }
            }
        }
    }

    Rectangle {
        x: (floatWin.activeVisibleRect.x - floatWin.x) - Math.floor(floatWin.monitorFrameGlowThickness / 2)
        y: (floatWin.activeVisibleRect.y - floatWin.y) - Math.floor(floatWin.monitorFrameGlowThickness / 2)
        width: floatWin.activeVisibleRect.w + floatWin.monitorFrameGlowThickness
        height: floatWin.activeVisibleRect.h + floatWin.monitorFrameGlowThickness
        color: "transparent"
        border.color: floatWin.monitorFrameColor
        border.width: floatWin.monitorFrameGlowThickness
        opacity: 0.22
        z: 1400
        visible: floatWin.debugFrameEnabled
    }

    Rectangle {
        x: floatWin.activeVisibleRect.x - floatWin.x
        y: floatWin.activeVisibleRect.y - floatWin.y
        width: floatWin.activeVisibleRect.w
        height: floatWin.activeVisibleRect.h
        color: "transparent"
        border.color: floatWin.monitorFrameColor
        border.width: floatWin.monitorFrameThickness
        opacity: 1.0
        z: 1401
        visible: floatWin.debugFrameEnabled
    }

    Rectangle {
        x: floatWin.contentInsetPx - Math.floor(floatWin.canvasFrameGlowThickness / 2)
        y: floatWin.contentInsetPx - Math.floor(floatWin.canvasFrameGlowThickness / 2)
        width: floatWin.contentAreaW + floatWin.canvasFrameGlowThickness
        height: floatWin.contentAreaH + floatWin.canvasFrameGlowThickness
        color: "transparent"
        border.color: floatWin.canvasFrameColor
        border.width: floatWin.canvasFrameGlowThickness
        opacity: 0.24
        z: 1500
        visible: floatWin.debugFrameEnabled
    }

    Rectangle {
        x: floatWin.contentInsetPx
        y: floatWin.contentInsetPx
        width: floatWin.contentAreaW
        height: floatWin.contentAreaH
        color: "transparent"
        border.color: floatWin.canvasFrameColor
        border.width: floatWin.canvasFrameThickness
        opacity: 1.0
        z: 1501
        visible: floatWin.debugFrameEnabled
    }

    SettingsMenu {
        id: settingsMenu
        t: floatWin.t
        appRef: appRef
        metrics: floatWin.uiMetrics
        soundEnabled: floatWin.soundEffectsEnabled
        z: 2001
        onThemeRequested: {
            floatWin.openThemePicker()
        }
        onReportBrandingRequested: {
            reportBrandingSettings.openWithProfiles()
        }
        onBackupRecoveryRequested: {
            backupRecoveryDialog.open()
        }
        onSoundChanged: function(enabled) {
            floatWin.applySoundEffectsEnabled(enabled)
        }
    }

    BackupRecoveryDialog {
        id: backupRecoveryDialog
        t: floatWin.t
        appRef: appRef
        metrics: floatWin.uiMetrics
        x: Math.max(0, (floatWin.width - width) / 2)
        y: Math.max(0, (floatWin.height - height) / 2)
    }

    ReportBrandingSettingsDialog {
        id: reportBrandingSettings
        parentWindow: floatWin
        t: floatWin.t
        appRef: floatWin.appRef
        metrics: floatWin.uiMetrics
        onBrandingChanged: {
            if (mainContent) {
                mainContent.reloadAllActiveReportBranding()
            }
        }
    }

    ThemePicker {
        id: themePicker
        t: floatWin.t
        appRef: appRef
        metrics: floatWin.uiMetrics
        names: appRef ? appRef.themeNames : []
        z: 2000
        onPicked: function(name, payload) {
            floatWin.applyThemeSelection(name, payload)
        }
    }

    SequentialAnimation {
        id: openAnim
        running: false

        ScriptAction {
            script: {
                var s = floatWin.computeStartGeometry()
                floatWin.x = s.x
                floatWin.y = s.y
                floatWin.width = s.w
                floatWin.height = s.h
                openScale.xScale = 0.68
                openScale.yScale = 0.86
                openRotation.angle = -7
                contentLayer.opacity = 1.0
            }
        }

        ParallelAnimation {
            NumberAnimation { target: contentLayer; property: "opacity"; to: 1.0; duration: 140; easing.type: Easing.OutQuad }
            NumberAnimation { target: openRotation; property: "angle"; to: 5; duration: 120; easing.type: Easing.OutQuad }
            NumberAnimation { target: openScale; property: "xScale"; to: 1.15; duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { target: openScale; property: "yScale"; to: 0.84; duration: 150; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: openRotation; property: "angle"; to: -3; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: openScale; property: "xScale"; to: 0.94; duration: 140; easing.type: Easing.OutQuad }
            NumberAnimation { target: openScale; property: "yScale"; to: 1.10; duration: 140; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation {
                target: openRotation
                property: "angle"
                to: 0
                duration: transitionDurationMs(layoutRatios.openStageTwoDurationPct, 150)
                easing.type: Easing.OutElastic
                easing.amplitude: 2.2
                easing.period: 0.45
            }
            NumberAnimation {
                target: openScale
                property: "xScale"
                to: 1.0
                duration: transitionDurationMs(layoutRatios.openStageThreeDurationPct, 180)
                easing.type: Easing.OutElastic
                easing.amplitude: 2.6
                easing.period: 0.45
            }
            NumberAnimation {
                target: openScale
                property: "yScale"
                to: 1.0
                duration: transitionDurationMs(layoutRatios.openStageThreeDurationPct, 180)
                easing.type: Easing.OutElastic
                easing.amplitude: 2.6
                easing.period: 0.45
            }
            ScriptAction {
                script: {
                    var f = floatWin.computeFinalGeometry()
                    geoAnimX.to = f.x
                    geoAnimY.to = f.y
                    geoAnimW.to = f.w
                    geoAnimH.to = f.h
                    geoAnimX.restart()
                    geoAnimY.restart()
                    geoAnimW.restart()
                    geoAnimH.restart()
                }
            }
        }
    }

    NumberAnimation {
        id: geoAnimX
        target: floatWin
        property: "x"
        duration: floatWin.transitionDurationMs(floatWin.layoutRatios.openStageThreeDurationPct, 200)
        easing.type: Easing.OutBack
        easing.overshoot: 1.0
    }
    NumberAnimation {
        id: geoAnimY
        target: floatWin
        property: "y"
        duration: floatWin.transitionDurationMs(floatWin.layoutRatios.openStageThreeDurationPct, 200)
        easing.type: Easing.OutBack
        easing.overshoot: 1.0
    }
    NumberAnimation {
        id: geoAnimW
        target: floatWin
        property: "width"
        duration: floatWin.transitionDurationMs(floatWin.layoutRatios.openStageThreeDurationPct, 200)
        easing.type: Easing.OutBack
        easing.overshoot: 1.0
    }
    NumberAnimation {
        id: geoAnimH
        target: floatWin
        property: "height"
        duration: floatWin.transitionDurationMs(floatWin.layoutRatios.openStageThreeDurationPct, 200)
        easing.type: Easing.OutBack
        easing.overshoot: 1.0
    }

    Component.onCompleted: {
        floatWin.syncThemeFromApp()
        floatWin.syncSoundEffectsFromApp()
        var finalGeo = computeFinalGeometry()
        width = finalGeo.w
        height = finalGeo.h
        rememberRestoreGeometry()
        refreshActiveVisibleRect()
        visible = true
        _openedOnce = true
        openAnim.restart()
        raise()
        try {
            if ((floatWin.flags & Qt.WindowDoesNotAcceptFocus) !== Qt.WindowDoesNotAcceptFocus) {
                requestActivate()
            }
        } catch (e) {
        }
    }

    Connections {
        target: floatWin.appRef
        enabled: !!floatWin.appRef
        function onThemeChanged() {
            floatWin.syncThemeFromApp()
        }
        function onSoundEffectsChanged() {
            floatWin.syncSoundEffectsFromApp()
        }
    }

    Component.onDestruction: {
        emitDidCloseOnce()
    }
}
