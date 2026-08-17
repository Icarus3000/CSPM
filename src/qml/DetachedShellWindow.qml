pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Window
import "components"
import "views"
import "standards"
import "standards/ThemeBridge.js" as ThemeBridge
import "standards/StartupQueueBridge.js" as StartupQueueBridge
import "standards/PerfTrace.js" as PerfTrace

Window {
    id: mainWin
    title: mainWin.detachedMode
        ? ((mainWin.panelTaskbarTitle && mainWin.panelTaskbarTitle.length > 0)
            ? mainWin.panelTaskbarTitle
            : ("CSPM - " + ((mainWin.detachedPanelTitle && mainWin.detachedPanelTitle.length > 0)
                ? mainWin.detachedPanelTitle : "Module")))
        : "CSPM - Main Menu"
    objectName: mainWin.detachedMode ? "CSPMFloatingDocketWindow" : "CSPMMainWindow"
    property alias mainContentRef: mainContent
    property alias sfxBusRef: sfxBus
    property bool detachedMode: false
    // Bootstrap supplies the one native PNG splash. Never create a second QML
    // splash from the main window, including when the Console style is active.
    property bool startupSplashEnabled: false
    property bool deferStartupLaunch: false

    // Startup may request regular activation once, but CSPM must never set
    // itself topmost or reassert focus after the user changes applications.
    property string instanceId: ""
    property rect detachedOriginRect: Qt.rect(0, 0, 120, 90)
    property rect detachedHostWindowRect: Qt.rect(0, 0, 1220, 920)
    property int detachedInitialTileIndex: -1
    property var detachedInitialPanelState: null
    property string detachedPanelTitle: "Module"

    // --- DEFERRED BACKEND BOOT ---
    Timer {
        id: deferredBackendBootTimer
        interval: 20
        running: false
        repeat: false
        onTriggered: {
            var completed = mainWin.runDeferredBackendBootTask({"source": "deferredBackendBootTimer"});
            if (completed === false) {
                deferredBackendBootTimer.interval = Math.max(24, mainWin.startupHeavyWorkDelayMs());
                deferredBackendBootTimer.start();
                mainWin.lagLog("deferredBackendBootTimer delayed by startup guard intervalMs=" + deferredBackendBootTimer.interval);
            }
        }
    }
    // --------------------------------
    property string panelTaskbarTitle: ""
    property var dockHostWindowRef: null
    property bool _detachedDidCloseEmitted: false
    signal didClose(string instanceId)
    signal requestDetach(int tileIndex, string titleText, var state, rect originRect)
    signal startupFirstPixelVisible()
    signal hiddenStartupBriefingPrepared()
    signal startupCinematicBloomStaged()

    Shortcut {
        sequence: "Space"
        context: Qt.ApplicationShortcut
        enabled: mainWin.startupCinematicBloomActive
        onActivated: mainWin.skipStartupCinematicBloom("space")
    }
    Shortcut {
        sequence: "Return"
        context: Qt.ApplicationShortcut
        enabled: mainWin.startupCinematicBloomActive
        onActivated: mainWin.skipStartupCinematicBloom("return")
    }
    Shortcut {
        sequence: "Enter"
        context: Qt.ApplicationShortcut
        enabled: mainWin.startupCinematicBloomActive
        onActivated: mainWin.skipStartupCinematicBloom("enter")
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        enabled: mainWin.startupCinematicBloomActive
        onActivated: mainWin.skipStartupCinematicBloom("escape")
    }


    
    // ============================================================
    // STATE MANAGEMENT
    // ============================================================
    property bool isSettled: false
    property bool isClosing: false
    property bool isMinimizing: false
    property bool isRestoringFromMinimize: false
    property bool maximizeAnimInProgress: false
    property bool wasWindowMinimized: false
    property bool isMinimizingToTray: false
    property bool isExitingFromTray: false
    property real lastMinimizeTargetDistX: 0.0
    property real lastMinimizeTargetDistY: 0.0
    // Cross-monitor tray flight state
    property bool _crossMonitorTrayFlight: false
    property real _trayTargetGlobalX: 0
    property real _trayTargetGlobalY: 0
    property real _windowCenterGlobalX: 0
    property real _windowCenterGlobalY: 0
    property real _vdX: 0
    property real _vdY: 0
    property real _vdW: 0
    property real _vdH: 0
    property var  _crossMonitorOverlay: null
    // Pending action after overlay flight completes: "restore" | "exit" | ""
    property string _pendingTrayAction: ""
    property bool forceClose: false
    property bool launchConfigured: false
    property bool startupLaunchStarted: false
    property bool startupSplashSkipInvoked: false
    property bool startupFirstPixelLogged: false
    property bool startupDataBootStarted: false
    property bool startupDataBootComplete: false
    property bool startupDataBootFailed: false
    property bool startupHiddenBriefingPrepared: false
    // The expensive final-window geometry pass is prepared while the native
    // splash is still on-screen.  Act III can then begin at its pinpoint on
    // the very next handoff frame instead of pausing between acts.
    property bool startupCinematicGeometryPrepared: false
    // True only while the native splash is still covering the QML pinpoint.
    // The visual scale stays at 0.2% until main.py releases Act III.
    property bool startupCinematicBloomPrestageOnly: false
    // Some Qt paths emit NumberAnimation.finished when a staging animation is
    // stopped. Keep staging distinct from a real, released bloom.
    property bool startupCinematicBloomReleaseStarted: false
    // The launch bloom uses a frozen GPU-ready canvas instead of exposing the
    // live host while Windows is creating/activating it. This gives Act III a
    // single visual surface that can unambiguously grow from the screen centre.
    property bool startupCinematicSnapshotActive: false
    property string startupCinematicSnapshotUrl: ""
    property int startupCinematicSnapshotSequence: 0
    // A GPU readback is normally returned quickly.  Keep a bounded fallback
    // so a platform that loses the grab callback can never leave the opening
    // sequence frozen behind the native splash.
    property int startupCinematicSnapshotFallbackMs: 6000
    // Act III of the Phase 2 launch sequence.  The native window is already
    // positioned at its final geometry; only the fully composed visual layer
    // scales from its exact centre point.
    property bool startupCinematicBloomActive: false
    property real startupCinematicBloomScale: 1.0
    // Temporarily muted per UX request.
    // property string startupDataBootMessage: "Loading Data - Please Wait"
    property string startupDataBootMessage: ""
    property string startupPhase: "init"
    property int startupHeavyWorkGraceMs: 340
    property bool startupHeavyWorkAllowed: false
    property int startupHeavyWorkBlockedCount: 0
    property double startupSettledEpochMs: 0
    property double startupPostSettleReadyEpochMs: 0
    property bool startupCheckpointPending: false
    property bool startupQueueInputTimeoutReleased: false
    property bool startupLaunchScreenLocked: false
    property bool startupDeferredQueueEnabled: (!mainWin.detachedMode)
        && (mainWin.startupDeferredQueueMode === "on"
            || (mainWin.startupDeferredQueueMode === "internal"
                && mainWin.startupDeferredQueueInternalEnabled))
    property bool startupDeferredQueueEnabledForClients: startupDeferredQueueEnabled
    property var startupDeferredTaskQueue: []
    property int startupDeferredTaskSeq: 0
    property int startupDeferredTaskPauseLogCount: 0
    property var _perfMarks: ({})
    property bool forensicBootEnabled: false
    property int forensicBootPulseMs: 200
    property bool hoverActivateEnabled: true
    property int hoverActivateDelayMs: 1
    property int targetScreenIndex: -1
    // Native Win+Shift+Arrow override requests from Python event filter.
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
    property bool closeMotionStarted: false
    property bool uiMaximized: false
    property bool restoreGeometryValid: false
    property bool startupRestoreMaximized: false
    property int restoreFinalX: 0
    property int restoreFinalY: 0
    property int restoreFinalW: 1
    property int restoreFinalH: 1
    property bool geometryTransitionSuppressed: false
    property bool userMoveInProgress: false
    property bool userResizeInProgress: false
    property bool systemMoveInProgress: false
    property bool adjacentMoveInProgress: false
    property int hostReassertAttemptsRemaining: 0
    property string hostReassertReason: ""
    property string dragStrategy: "none"  // "none" | "native" | "fallback"
    property bool recoveryBandEnabled: true
    property int recoveryBandHeight: ratioToPixels(0.008, Math.max(1, usableW), Math.max(1, usableH), 10)
    property bool recoveryBandMaskActive: recoveryBandEnabled
        && animationPhase === "settled"
        && titlebarOutsideVisibleRect(activeVisibleRectSafe())
    property bool recoveryAutoClampEnabled: false
    property int recoveryAutoClampDelayMs: 300
    property real titlebarOutSinceMs: 0
    property real dragReleaseSettlingUntilMs: 0
    property bool dragReleaseSnapEnabled: true
    property bool dragReleaseCenterLockEnabled: true
    property bool dragReleaseCursorSampleEnabled: false
    property bool classicMoveMenuArmed: false
    property bool classicMoveModeActive: false
    property int classicMoveStartX: 0
    property int classicMoveStartY: 0
    property int forceNudgeStepPx: 48
    property int classicMoveStepPx: 24
    property string resizeHandle: "none"  // "none" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw"
    // One-line rollback switch for the new edge/corner resize pipeline.
    property bool strictResizePipelineEnabled: true
    // Safe-test toggle: flip to false to immediately restore legacy settled padding behavior.
    property bool useExactSettledCanvasPadding: true
    // Keep launch sizing ratio-consistent across mixed-DPI monitors.
    property bool useDpiLaunchBoost: false
    // Controlled from Python runtime config object.
    property bool phaseLoggingEnabled: verboseLoggingEnabled
    property bool interactionTraceEnabled: true
    property int interactionTraceWindowMs: 520
    property real interactionTraceStartedMs: 0
    property real interactionTraceUntilMs: 0
    property int interactionTraceSeq: 0
    property int interactionTraceEventSeq: 0
    property string interactionTraceMode: ""
    property string interactionTraceOrigin: ""
    property bool allowNativeSystemDrag: false
    // Cursor-anchored drag is the stable path across mixed-DPI/multi-monitor setups.
    property bool preferTranslationDrag: false
    // Keep a single drag driver active to avoid pointer-fighting jitter.
    property bool dragPollingEnabled: true
    property bool dragTraceEnabled: true
    // Disable drag deformation FX while stabilizing drag smoothness.
    property bool dragVisualFxEnabled: true
    property real dragStartHostX: 0
    property real dragStartHostY: 0
    property real dragStartFinalX: 0
    property real dragStartFinalY: 0
    property real dragStartCursorX: 0
    property real dragStartCursorY: 0
    property bool dragHasCursorAnchor: false
    property bool dragHasRealDelta: false
    property real dragLastTranslationX: 0
    property real dragLastTranslationY: 0
    property real dragAccumHostX: 0
    property real dragAccumHostY: 0
    property real dragAccumFinalX: 0
    property real dragAccumFinalY: 0
    property bool dragFinalizePending: false
    property real resizeStartFinalX: 0
    property real resizeStartFinalY: 0
    property real resizeStartFinalW: 1
    property real resizeStartFinalH: 1
    property real resizeStartCursorX: 0
    property real resizeStartCursorY: 0
    property bool resizeHasCursorAnchor: false
    property bool resizeHasRealDelta: false
    property real resizeLiveCursorX: 0
    property real resizeLiveCursorY: 0
    property bool resizeLiveCursorValid: false
    property double resizeLiveCursorSampleMs: 0
    property int resizeLiveCursorFreshMs: 2
    property int resizeMonitorFrame: 0
    property int maximizeMonitorFrame: 0
    property int restoreMaxMonitorFrame: 0
    property int dragForensicFrame: 0
    
    // --- PHASE TRACKING ---
    /// OPENING: jelly animates freely, canvas = full monitor
    /// SETTLED: jelly frozen, canvas shrinks to window+padding, window interactive
    /// CLOSING: jelly animates out, canvas expands to full monitor
    property string animationPhase: "opening"  // "opening" | "settled" | "closing"
    
    // --- GEOMETRY TRACKING ---
    property int finalX: 0
    property int finalY: 0
    property int finalW: 1
    property int finalH: 1
    property real maximizeFxScaleX: 1.0
    property real maximizeFxScaleY: 1.0
    property real maximizeFxTransX: 0.0
    property real maximizeFxTransY: 0.0
    property real maximizeFxRotate: 0.0
    property real dragFxScaleX: 1.0
    property real dragFxScaleY: 1.0
    property real dragFxTransX: 0.0
    property real dragFxTransY: 0.0
    property real dragFxRotate: 0.0
    property real dragFxCornerBoost: 0.0
    property real dragFxVelX: 0.0
    property real dragFxVelY: 0.0
    property real dragReleaseVelocityNorm: 0.0
    property int dragFxStartScreenIndex: -1
    property bool dragFxCrossMonitorLockout: false
    property int glowPadding: 0
    onGlowPaddingChanged: {
        // Keep settled canvas geometry in sync with glow padding shrink/expand.
        if (mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.isMinimizing
            && !mainWin.isRestoringFromMinimize
            && !mainWin.userMoveInProgress
            && !mainWin.userResizeInProgress) {
            mainWin.updateCanvasGeometry();
        }
    }
    
    // --- SCREEN & SPACING ---
    property int startupLaunchScreenIndex: -1
    property var targetScreen: null
    property var targetScreenInfo: null
    property int usableX: 0
    property int usableY: 0
    property int usableW: 0
    property int usableH: 0
    property int monitorScalePercent: 100
    property string taskbarEdge: "none"
    property int taskbarSize: 0
    
    // --- CANVAS SIZING (Dynamic) ---
    property int canvasX: 0
    property int canvasY: 0
    property int canvasW: 1
    property int canvasH: 1
    property int hostX: 0
    property int hostY: 0
    property int hostW: 1
    property int hostH: 1
    property int debugBoundsX: 0
    property int debugBoundsY: 0
    property int debugBoundsW: 1
    property int debugBoundsH: 1
    // Toggle expertDebugMode to true to re-enable the neon monitor/geometry boundary overlays
    property bool expertDebugMode: false
    property bool debugFrameEnabled: expertDebugMode
    property color monitorFrameColor: "#39FF14"
    property int monitorFrameThickness: ratioToPixels(layoutRatios.monitorFrameCorePct, Math.max(1, usableW), Math.max(1, usableH), 1)
    property int monitorFrameGlowThickness: ratioToPixels(layoutRatios.monitorFrameGlowPct, Math.max(1, usableW), Math.max(1, usableH), monitorFrameThickness + 1)
    property color canvasFrameColor: "#FF8C00"
    property int canvasFrameThickness: ratioToPixels(layoutRatios.canvasFrameCorePct, Math.max(1, usableW), Math.max(1, usableH), 1)
    property int canvasFrameGlowThickness: ratioToPixels(layoutRatios.canvasFrameGlowPct, Math.max(1, usableW), Math.max(1, usableH), canvasFrameThickness + 1)
    property bool outerRoundedShellMaskEnabled: true
    property bool cornerForensicLoggingEnabled: phaseLoggingEnabled
    property bool cornerForensicBurstEnabled: phaseLoggingEnabled
    property int cornerForensicBurstFrames: 72
    property int cornerForensicBurstRemaining: 0
    property string cornerForensicBurstReason: ""
    // Delay rounded-mask activation briefly after settle transition completes
    // to avoid perceived corner flash during handoff.
    property bool shellMaskSettleDelayReady: false
    // Immediate rounded-mask activation at settle to avoid a one-frame handoff flash.
    property int shellMaskSettleDelayMs: 0
    // Exposed for Python mask sync so native window rounding only engages
    // when the QML shell layer mask is actually active.
    property bool shellMaskLayerActive: (typeof animationCanvasLayer !== "undefined")
        && animationCanvasLayer.roundedClipActive
    property bool mainContentRoundedMaskActive: false
    property string lastCornerForensicSignature: ""
    property string lastCornerLayerSummary: ""
    property var dragMonitorVisibleRect: ({ "x": 0, "y": 0, "w": 1, "h": 1 })
    property var activeVisibleRect: ({ "x": 0, "y": 0, "w": 1, "h": 1 })
    property var closingOverlayRef: null
    // Freeze the visible content, monitor, and motion geometry at the instant
    // close is initiated.  The host envelope may span monitors, so its own
    // Window.screen is not a reliable proxy for the monitor containing the
    // visible CSPM surface.
    property var closingOverlayGeometry: null
    property int closingOverlayHandoffSeq: 0
    property var startupSplashRef: null
    property var startupSplashRefs: []
    property int startupSplashPendingCount: 0
    property double startupSplashSequenceEpochMs: 0
    // Small lead lets all monitor splash overlays align to one shared start timestamp.
    property int startupSplashSyncLeadMs: 96
    property int startupFocusReassertRemaining: 0
    property int startupFallStartTimelineMs: ((typeof startupSplashFallStartMs === "number")
        && isFinite(startupSplashFallStartMs))
        ? Math.max(0, Math.round(startupSplashFallStartMs)) : 0
    property var minimizeOverlayRef: null
    property int minimizeOverlayHandoffSeq: 0
    property var detachedWindows: []
    property int detachedWindowSeq: 0
    property var detachedFramePalette: ([
        { "monitor": "#00E5FF", "canvas": "#FF8C00" },
        { "monitor": "#FF4D4D", "canvas": "#7C4DFF" },
        { "monitor": "#00E676", "canvas": "#FFD740" },
        { "monitor": "#40C4FF", "canvas": "#FF6D00" },
        { "monitor": "#69F0AE", "canvas": "#FF4081" },
        { "monitor": "#FFFF00", "canvas": "#18FFFF" },
        { "monitor": "#FF9100", "canvas": "#64FFDA" },
        { "monitor": "#B388FF", "canvas": "#FF5252" }
    ])
    property bool minimizeRestorePending: false
    property string minimizeRestoreSnapshotUrl: ""
    property int minimizeRestoreFinalX: 0
    property int minimizeRestoreFinalY: 0
    property int minimizeRestoreFinalW: 1
    property int minimizeRestoreFinalH: 1
    property int minimizeRestoreTargetX: 0
    property int minimizeRestoreTargetY: 0
    property bool closeTargetOverrideActive: false
    property int closeTargetOverrideX: 0
    property int closeTargetOverrideY: 0
    property var pendingDockCommitRequest: null
    property var pendingRedockRequest: null
    property bool closeGuardVisible: false
    property string closeGuardTitle: ""
    property string closeGuardMessage: ""
    property var closeGuardWindowRows: []
    property int closeGuardDetachedCount: 0
    property int closeGuardUnsavedCount: 0
    property int closeGuardRunningTimerCount: 0
    property bool recoveryPromptVisible: false
    property string recoveryPromptTitle: ""
    property string recoveryPromptMessage: ""
    property var recoveryPromptRows: []
    property var pendingRecoveryPayload: null
    property bool recoveryPromptHandled: false
    property bool closeCheckpointHadRisk: false
    property string closeCheckpointSignature: ""
    property bool redockPromptVisible: false
    property bool redockPromptAllowAuto: false
    property bool redockPromptAllowFocus: false
    property string redockPromptTitle: ""
    property string redockPromptMessage: ""
    property var layoutRatios: ({
        "contentAspect": 1.70,
        // +10% area default (sqrt(1.10) ~= 1.0488) at fixed content aspect.
        "contentHeightPct": 0.806,
        "contentMinHeightPct": 0.50,
        "contentMaxHeightPct": 0.92,
        "contentMinWidthPct": 0.35,
        "contentMaxWidthPct": 0.84,
        "contentCenterXPct": 0.50,
        "contentCenterYPct": 0.50,
        "openPaddingPct": 0.245,
        "openPaddingLowPerfPct": 0.205,
        "settledCanvasAreaScale": 1.05,
        "settledPaddingPct": 0.085,
        "settledPaddingLowPerfPct": 0.055,
        "closePadPct": 0.020,
        "dragPadPct": 0.030,
        "hostMarginPct": 0.085,
        "hostMarginLowPerfPct": 0.065,
        "hostMarginMinPct": 0.045,
        "hostMarginContentPct": 0.120,
        "monitorFrameCorePct": 0.0024,
        "monitorFrameGlowPct": 0.0068,
        "canvasFrameCorePct": 0.0030,
        "canvasFrameGlowPct": 0.0080,
        "themePickerRightPct": 0.020,
        "themePickerTopPct": 0.040,
        "resizeHandleThicknessPct": 0.0088,
        "resizeCornerSizePct": 0.036,
        "resizeMinWidthPct": 0.240,
        "resizeMinHeightPct": 0.260,
        "titleBarHeightPct": 0.061,
        "chromeCornerRadiusPct": 0.052,
        "chromeGlowNearPct": 0.010,
        "chromeGlowFarPct": 0.030,
        "chromeGlowNearLowPerfPct": 0.006,
        "chromeGlowFarLowPerfPct": 0.016,
        "openDropOvershootPct": 0.0015,
        "openingMaxSquashScaleX": 1.38,
        "openingMaxReboundScaleY": 1.12,
        "openingFloorGuardMinPx": 58,
        "openingFrameInsetMinPx": 18
    })

    property int frozenContentW: 0
    property int frozenContentH: 0

    // Unified metrics payload for downstream components.
    // All responsive sizing should trace back to monitor usable geometry + settled content geometry.
    property var uiMetrics: (function() {
        var activeW = Math.max(1, finalW)
        var activeH = Math.max(1, finalH)
        if (mainWin.userResizeInProgress || mainWin.userMoveInProgress) {
            if (mainWin.frozenContentW > 0 && mainWin.frozenContentH > 0) {
                activeW = mainWin.frozenContentW
                activeH = mainWin.frozenContentH
            }
        } else {
            mainWin.frozenContentW = activeW
            mainWin.frozenContentH = activeH
        }
        return {
            "monitorW": Math.max(1, (usableW > 0) ? usableW : ((targetScreen && targetScreen.width > 0) ? targetScreen.width : width)),
            "monitorH": Math.max(1, (usableH > 0) ? usableH : ((targetScreen && targetScreen.height > 0) ? targetScreen.height : height)),
            "contentW": activeW,
            "contentH": activeH,
            "scalePercent": Math.max(1, monitorScalePercent),
            "fontFloorTitlePx": metricFloorPx(0.0130, 12),
            "fontFloorIconPx": metricFloorPx(0.0120, 12),
            "fontFloorBodyPx": metricFloorPx(0.0109, 8),
            "fontFloorLabelPx": metricFloorPx(0.0098, 7)
        }
    })()
    
    // ============================================================
    // WINDOW SETUP
    // ============================================================
    visible: false
    color: "transparent"  // Only opaque content is the canvas children
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowMinimizeButtonHint
    opacity: 1.0
    
    // Native OS window geometry must snap atomically without continuous Behavior animation
    Behavior on width { enabled: false }
    Behavior on height { enabled: false }
    Behavior on x { enabled: false }
    Behavior on y { enabled: false }

    // During a normal settled state, the native window is only as large as the
    // visible canvas.  A monitor-sized transparent host blocks every other
    // application on that monitor even when CSPM itself looks small.
    width: hostW
    height: hostH
    x: hostX
    y: hostY
    onHostXChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("HOST-X", "hostX=" + Math.round(hostX), false);
        }
    }
    onHostYChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("HOST-Y", "hostY=" + Math.round(hostY), false);
        }
    }
    onHostWChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("HOST-W", "hostW=" + Math.round(hostW), false);
        }
    }
    onHostHChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("HOST-H", "hostH=" + Math.round(hostH), false);
        }
    }
    onXChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("WIN-X", "x=" + Math.round(x), false);
        }
        if (mainWin.animationPhase === "closing") {
            canvasLocalX = canvasX - x;
            return;
        }
        if (mainWin.systemMoveInProgress && mainWin.dragStrategy === "native"
            && mainWin.animationPhase === "settled" && !mainWin.isClosing) {
            mainWin.syncSettledGeometryFromWindowMove();
        }
    }
    onYChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("WIN-Y", "y=" + Math.round(y), false);
        }
        if (mainWin.animationPhase === "closing") {
            canvasLocalY = canvasY - y;
            return;
        }
        if (mainWin.systemMoveInProgress && mainWin.dragStrategy === "native"
            && mainWin.animationPhase === "settled" && !mainWin.isClosing) {
            mainWin.syncSettledGeometryFromWindowMove();
        }
    }
    onWidthChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("WIN-W", "width=" + Math.round(width), false);
        }
    }
    onHeightChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("WIN-H", "height=" + Math.round(height), false);
        }
    }
    onUserMoveInProgressChanged: {
        if (mainWin.interactionTraceActive() || userMoveInProgress) {
            if (userMoveInProgress && !mainWin.interactionTraceActive()) {
                mainWin.beginInteractionTrace("drag", "userMoveInProgressChanged");
            } else {
                mainWin.extendInteractionTrace(120);
            }
            mainWin.logInteractionTrace("STATE-MOVE", "userMoveInProgress=" + (userMoveInProgress ? "1" : "0"), true);
        }
    }
    onUserResizeInProgressChanged: {
        if (mainWin.interactionTraceActive() || userResizeInProgress) {
            if (userResizeInProgress && !mainWin.interactionTraceActive()) {
                mainWin.beginInteractionTrace("resize", "userResizeInProgressChanged");
            } else {
                mainWin.extendInteractionTrace(120);
            }
            mainWin.logInteractionTrace("STATE-RESIZE", "userResizeInProgress=" + (userResizeInProgress ? "1" : "0"), true);
        }
    }
    onSystemMoveInProgressChanged: {
        if (mainWin.interactionTraceActive() || systemMoveInProgress) {
            if (systemMoveInProgress && !mainWin.interactionTraceActive()) {
                mainWin.beginInteractionTrace("system-move", "systemMoveInProgressChanged");
            } else {
                mainWin.extendInteractionTrace(120);
            }
            mainWin.logInteractionTrace("STATE-SYSTEM", "systemMoveInProgress=" + (systemMoveInProgress ? "1" : "0"), true);
        }
    }
    onGeometryTransitionSuppressedChanged: {
        if (mainWin.interactionTraceActive()) {
            mainWin.extendInteractionTrace(120);
            mainWin.logInteractionTrace("STATE-GEOM", "geometryTransitionSuppressed=" + (geometryTransitionSuppressed ? "1" : "0"), false);
        }
    }

/*
    Shortcut {
        sequence: "Esc"
        onActivated: {
            if (mainWin.classicMoveModeActive) {
                mainWin.stopClassicMoveMode(false, "Esc")
                return
            }
            if (!mainWin.requestCloseAnimation()) {
                try {
                    mainWin.close()
                } catch (e) {
                    Qt.quit()
                }
            }
        }
    }
*/
    Shortcut {
        sequence: "Meta+Shift+Left"
        enabled: Qt.platform.os !== "windows"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.requestAdjacentScreenMove(-1, "Meta+Shift+Left")
    }
    Shortcut {
        sequence: "Meta+Shift+Right"
        enabled: Qt.platform.os !== "windows"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.requestAdjacentScreenMove(1, "Meta+Shift+Right")
    }
    Shortcut {
        sequence: "Ctrl+Shift+Left"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.requestAdjacentScreenMove(-1, "Ctrl+Shift+Left")
    }
    Shortcut {
        sequence: "Ctrl+Shift+Right"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.requestAdjacentScreenMove(1, "Ctrl+Shift+Right")
    }
    Shortcut {
        sequence: "Ctrl+Alt+Home"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.hardRecenterToActiveMonitor("Ctrl+Alt+Home")
    }
    Shortcut {
        sequence: "Ctrl+Alt+Shift+Left"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        onActivated: mainWin.forceNudgeWindow(-mainWin.forceNudgeStepPx, 0, "Ctrl+Alt+Shift+Left")
    }
    Shortcut {
        sequence: "Ctrl+Alt+Shift+Right"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        onActivated: mainWin.forceNudgeWindow(mainWin.forceNudgeStepPx, 0, "Ctrl+Alt+Shift+Right")
    }
    Shortcut {
        sequence: "Ctrl+Alt+Shift+Up"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        onActivated: mainWin.forceNudgeWindow(0, -mainWin.forceNudgeStepPx, "Ctrl+Alt+Shift+Up")
    }
    Shortcut {
        sequence: "Ctrl+Alt+Shift+Down"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        onActivated: mainWin.forceNudgeWindow(0, mainWin.forceNudgeStepPx, "Ctrl+Alt+Shift+Down")
    }
    Shortcut {
        sequence: "Alt+Space"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        onActivated: mainWin.armClassicMoveMenu("Alt+Space")
    }
    Shortcut {
        sequence: "M"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: mainWin.classicMoveMenuArmed
        onActivated: mainWin.startClassicMoveMode("Alt+Space,M")
    }
    Shortcut {
        sequence: "Left"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.nudgeClassicMove(-mainWin.classicMoveStepPx, 0, "ClassicMove-Left")
    }
    Shortcut {
        sequence: "Right"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.nudgeClassicMove(mainWin.classicMoveStepPx, 0, "ClassicMove-Right")
    }
    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.nudgeClassicMove(0, -mainWin.classicMoveStepPx, "ClassicMove-Up")
    }
    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        autoRepeat: true
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.nudgeClassicMove(0, mainWin.classicMoveStepPx, "ClassicMove-Down")
    }
    Shortcut {
        sequence: "Return"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.stopClassicMoveMode(true, "ClassicMove-Enter")
    }
    Shortcut {
        sequence: "Enter"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: mainWin.classicMoveModeActive
        onActivated: mainWin.stopClassicMoveMode(true, "ClassicMove-Enter")
    }
    Shortcut {
        sequence: "Ctrl+Shift+L"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: mainWin.liveLogConsoleVisible && mainWin.liveLogBuffer.length > 0
        onActivated: mainWin.copyLiveLogBufferToClipboard()
    }
    VisualRules { id: style; appStyle: mainWin.appStyle }
    
    property var appRef: null
    property var runtimeConfigRef: (appRef && appRef.runtimeConfig) ? appRef.runtimeConfig : null
    property bool verboseLoggingEnabled: !!(runtimeConfigRef && runtimeConfigRef.verboseLoggingEnabled === true)
    property bool debugFramesEnabled: !!(runtimeConfigRef && runtimeConfigRef.debugFramesEnabled === true)
    property string startupDeferredQueueMode: (runtimeConfigRef && runtimeConfigRef.startupDeferredQueueMode)
        ? String(runtimeConfigRef.startupDeferredQueueMode).toLowerCase() : "internal"
    property bool startupDeferredQueueInternalEnabled: !!(runtimeConfigRef && runtimeConfigRef.startupDeferredQueueInternalEnabled === true)
    property int startupDeferredQueueTickMs: ((runtimeConfigRef && typeof runtimeConfigRef.startupDeferredQueueTickMs === "number")
        && isFinite(runtimeConfigRef.startupDeferredQueueTickMs))
        ? Math.max(24, Math.round(runtimeConfigRef.startupDeferredQueueTickMs)) : 180
    property bool startupFastLaunchFocusEnabled: !(runtimeConfigRef && runtimeConfigRef.startupFastLaunchFocusEnabled === false)
    property bool startupQueueWaitForFirstInput: !(runtimeConfigRef && runtimeConfigRef.startupQueueWaitForFirstInput === false)
    property int startupQueueInputFallbackMs: ((runtimeConfigRef && typeof runtimeConfigRef.startupQueueInputFallbackMs === "number")
        && isFinite(runtimeConfigRef.startupQueueInputFallbackMs))
        ? Math.max(0, Math.round(runtimeConfigRef.startupQueueInputFallbackMs)) : 1400
    property bool startupFirstInputSeen: !!(appRef && appRef.startupFirstInputSeen === true)
    property int startupSplashFallStartMs: ((runtimeConfigRef && typeof runtimeConfigRef.startupSplashFallStartMs === "number")
        && isFinite(runtimeConfigRef.startupSplashFallStartMs))
        ? Math.max(0, Math.round(runtimeConfigRef.startupSplashFallStartMs)) : 0
    property string startupSplashLogoUrl: (runtimeConfigRef && runtimeConfigRef.startupSplashLogoUrl)
        ? String(runtimeConfigRef.startupSplashLogoUrl) : ""
    property string startupSplashAudioUrl: (runtimeConfigRef && runtimeConfigRef.startupSplashAudioUrl)
        ? String(runtimeConfigRef.startupSplashAudioUrl) : ""
    property bool lowPerformanceMode: !!(appRef && appRef.lowPerformanceMode)
    property bool soundEffectsEnabled: !(appRef && appRef.soundEffectsEnabled === false)
    property string appStyle: (appRef && appRef.appStyle) ? String(appRef.appStyle) : "Professional"
    property string appNotificationMessage: ""
    property string appNotificationTone: "info"
    property bool appNotificationActive: false
    property bool liveLogConsoleVisible: false
    property string liveLogBuffer: ""
    property int liveLogMaxLines: 100
    property int liveLogMaxChars: 5000
    property var t: {
        try {
            if (appRef && appRef.theme && appRef.theme.bg) {
                return appRef.theme;
            }
        } catch(e) {
            mainWin.reportUiSilentFailure("DetachedShellWindow.theme.resolve", String(e));
        }
        return {
            "bg": "#040405",
            "panel": "#0E0F11",
            "panel2": "#181A1E",
            "accent": "#F8FAFC",
            "hover": "#2A2D33",
            "text": "#F5F7FA",
            "muted": "#A4AAB4",
            "btn_text": "#050506",
            "glow": "#FFFFFF"
        };
    }

    function cloneThemeObject(themeObj) {
        return ThemeBridge.cloneThemeObject(themeObj);
    }

    function themeForName(themeName) {
        var resolvedAppRef = resolveAppRef();
        return ThemeBridge.themeForName(resolvedAppRef, themeName);
    }

    function resolveAppRef() {
        if (appRef) return appRef;
        var candidate = contextMemberSafe("app");
        if (candidate) {
            appRef = candidate;
        }
        return appRef;
    }

    function applyThemeSelection(themeName, pickedPayload) {
        var resolvedAppRef = resolveAppRef();
        var localTheme = ThemeBridge.applyThemeSelection(resolvedAppRef, themeName, pickedPayload);
        if (localTheme && localTheme.bg) {
            mainWin.t = localTheme;
            return;
        }
        var resolvedName = String(themeName === undefined || themeName === null ? "" : themeName);
        phaseLog("THEME", "Detached local theme lookup failed name=" + resolvedName);
    }

    function syncThemeFromApp() {
        var resolvedAppRef = resolveAppRef();
        var payload = ThemeBridge.syncThemeFromApp(resolvedAppRef);
        if (!payload || !payload.bg) return false;
        mainWin.t = payload;
        return true;
    }

    function syncSoundEffectsFromApp() {
        var resolvedAppRef = resolveAppRef();
        var nextEnabled = true;
        try {
            nextEnabled = !(resolvedAppRef && resolvedAppRef.soundEffectsEnabled === false);
        } catch (e) {
            nextEnabled = true;
        }
        mainWin.soundEffectsEnabled = nextEnabled;
        if (sfxBus) {
            sfxBus.enabled = nextEnabled;
        }
        if (settingsMenu) {
            settingsMenu.soundEnabled = nextEnabled;
        }
        return nextEnabled;
    }

    function applySoundEffectsEnabled(enabled) {
        var nextEnabled = !!enabled;
        mainWin.soundEffectsEnabled = nextEnabled;
        if (sfxBus) {
            sfxBus.enabled = nextEnabled;
        }
        if (settingsMenu) {
            settingsMenu.soundEnabled = nextEnabled;
        }
        return true;
    }

    function normalizeThemeField(value) {
        return ThemeBridge.normalizeThemeField(value);
    }

    function resolveThemeNameForPayload(payload) {
        var resolvedAppRef = resolveAppRef();
        return ThemeBridge.resolveThemeNameForPayload(resolvedAppRef, payload);
    }

    function persistCurrentThemeSelection(sourceTag) {
        var resolvedAppRef = resolveAppRef();
        if (!(resolvedAppRef && resolvedAppRef.setTheme)) return false;
        var resolvedName = resolveThemeNameForPayload(mainWin.t);
        if (!resolvedName.length) return false;
        try {
            resolvedAppRef.setTheme(resolvedName);
            phaseLog("THEME", "Persist from " + String(sourceTag || "unknown") + " name=" + resolvedName);
            return true;
        } catch (e) {
            phaseLog("THEME", "Persist failed from " + String(sourceTag || "unknown") + " err=" + e);
            return false;
        }
    }

    function showAppNotification(message, tone) {
        var text = String(message === undefined || message === null ? "" : message).trim();
        if (!text.length) return;
        appNotificationMessage = text;
        appNotificationTone = String(tone || "info");
        appNotificationActive = true;
        appNotificationTimer.restart();
    }

    function appendLiveLog(msg) {
        var text = String(msg === undefined || msg === null ? "" : msg);
        if (!text.length) return;

        text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

        var nextBuffer = liveLogBuffer.length ? (liveLogBuffer + "\n" + text) : text;
        var lines = nextBuffer.split("\n");
        if (lines.length > liveLogMaxLines) {
            lines = lines.slice(lines.length - liveLogMaxLines);
        }
        nextBuffer = lines.join("\n");

        if (nextBuffer.length > liveLogMaxChars) {
            nextBuffer = nextBuffer.slice(nextBuffer.length - liveLogMaxChars);
            var firstBreak = nextBuffer.indexOf("\n");
            if (firstBreak >= 0 && firstBreak < nextBuffer.length - 1) {
                nextBuffer = nextBuffer.slice(firstBreak + 1);
            }
        }

        liveLogBuffer = nextBuffer;
        if (liveLogConsoleVisible) {
            Qt.callLater(function() {
                mainWin.scrollLiveLogConsoleToEnd()
            })
        }
    }

    function resetLiveLogBuffer(reason) {
        liveLogBuffer = "";
        if (liveLogViewport) {
            liveLogViewport.contentY = 0;
        }
        var stamp = new Date();
        appendLiveLog("[LIVE-LOG] reset=" + String(reason || "unspecified")
            + " ts=" + stamp.toISOString());
    }

    function scrollLiveLogConsoleToEnd() {
        if (!liveLogViewport) return;
        liveLogViewport.contentY = Math.max(0, liveLogViewport.contentHeight - liveLogViewport.height);
    }

    function copyLiveLogBufferToClipboard() {
        if (!liveLogBuffer.length) {
            mainWin.showAppNotification("No logs to copy", "info");
            return;
        }
        liveLogClipboardProxy.text = liveLogBuffer;
        liveLogClipboardProxy.forceActiveFocus();
        liveLogClipboardProxy.selectAll();
        liveLogClipboardProxy.copy();
        liveLogClipboardProxy.focus = false;
        mainWin.showAppNotification("Logs copied to clipboard", "info");
    }

    function reportUiFailure(context, detail, userMessage) {
        var safeContext = String(context === undefined || context === null ? "qml" : context);
        var safeDetail = String(detail === undefined || detail === null ? "" : detail).trim();
        var safeMessage = String(userMessage === undefined || userMessage === null ? "Operation failed." : userMessage).trim();
        if (mainWin.appRef && mainWin.appRef.reportUiFailure) {
            mainWin.appRef.reportUiFailure(safeContext, safeDetail.length ? safeDetail : safeMessage, safeMessage);
            return;
        }
        mainWin.showAppNotification(safeMessage + (safeDetail.length ? ": " + safeDetail : ""), "error");
    }

    function reportUiSilentFailure(context, detail) {
        var safeContext = String(context === undefined || context === null ? "qml.silent" : context);
        var safeDetail = String(detail === undefined || detail === null ? "" : detail).trim();
        if (mainWin.appRef && mainWin.appRef.reportUiSilentFailure) {
            mainWin.appRef.reportUiSilentFailure(safeContext, safeDetail);
            return;
        }
        if (safeDetail.length) {
            console.warn("[UI-SILENT] " + safeContext + ": " + safeDetail);
        } else {
            console.warn("[UI-SILENT] " + safeContext);
        }
    }

    function dragTrace(stage, detail) {
        if (!dragTraceEnabled) return;
        var centerX = Math.round(finalX + (finalW / 2.0));
        var centerY = Math.round(finalY + (finalH / 2.0));
        var msg = "[DRAG-TRACE] " + stage
            + " center=(" + centerX + "," + centerY + ")"
            + " final=" + fmtRect(finalX, finalY, finalW, finalH)
            + " host=" + fmtRect(hostX, hostY, hostW, hostH)
            + " strategy=" + dragStrategy;
        if (detail && detail.length) {
            msg += " " + detail;
        }
        console.log(msg);
    }

    function lockDragReleaseCenter(targetCenterX, targetCenterY) {
        if (!isFinite(targetCenterX) || !isFinite(targetCenterY)) return false;
        if (!isFinite(finalW) || !isFinite(finalH) || finalW <= 0 || finalH <= 0) return false;

        var pinnedScreen = screenForPoint(targetCenterX, targetCenterY, targetScreen);
        if (pinnedScreen) {
            adoptTargetScreen(pinnedScreen, true);
        }

        var nextX = Math.round(targetCenterX - (finalW / 2.0));
        var nextY = Math.round(targetCenterY - (finalH / 2.0));
        if (nextX === finalX && nextY === finalY) return false;

        var prevRect = fmtRect(finalX, finalY, finalW, finalH);
        finalX = nextX;
        finalY = nextY;
        dragTrace("release-center-lock", "from=" + prevRect + " to=" + fmtRect(finalX, finalY, finalW, finalH));
        return true;
    }

    onAppRefChanged: {
        Qt.callLater(function() {
            mainWin.syncThemeFromApp();
        });
    }

    onTChanged: {
        var list = detachedWindows ? detachedWindows : [];
        var outboundTheme = cloneThemeObject(mainWin.t);
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry || !entry.windowRef) continue;
            try {
                entry.windowRef.t = cloneThemeObject(outboundTheme ? outboundTheme : mainWin.t);
            } catch (e) {
            }
        }
    }
    
    // ============================================================
    // UTILITY FUNCTIONS
    // ============================================================
    
    function describeScreen(screenObj) {
        if (!screenObj) return "<none>";
        var dpr = (typeof screenObj.devicePixelRatio === "number")
            ? screenObj.devicePixelRatio.toFixed(2) : "n/a";
        var name = screenObj.name ? screenObj.name : "<unnamed>";
        return name + " geom=" + screenObj.virtualX + "," + screenObj.virtualY + " "
            + screenObj.width + "x" + screenObj.height + " dpr=" + dpr;
    }

    function fmtRect(x, y, w, h) {
        return Math.round(x) + "," + Math.round(y) + " "
            + Math.max(1, Math.round(w)) + "x" + Math.max(1, Math.round(h));
    }

    function safeColor(inputColor, fallbackColor) {
        if (inputColor
                && typeof inputColor.r === "number"
                && typeof inputColor.g === "number"
                && typeof inputColor.b === "number") {
            return inputColor;
        }
        return fallbackColor;
    }

    function relativeLuminance(inputColor) {
        var c = safeColor(inputColor, Qt.rgba(0, 0, 0, 1));
        function toLinear(chan) {
            var v = Math.max(0.0, Math.min(1.0, chan));
            if (v <= 0.03928) return v / 12.92;
            return Math.pow((v + 0.055) / 1.055, 2.4);
        }
        var r = toLinear(c.r);
        var g = toLinear(c.g);
        var b = toLinear(c.b);
        return (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
    }

    function contrastRatio(a, b) {
        var lA = relativeLuminance(a);
        var lB = relativeLuminance(b);
        var hi = Math.max(lA, lB);
        var lo = Math.min(lA, lB);
        return (hi + 0.05) / (lo + 0.05);
    }

    function readableTextOn(bgColor, preferredTextColor) {
        var bg = safeColor(bgColor, Qt.rgba(0, 0, 0, 1));
        var preferred = safeColor(preferredTextColor, Qt.rgba(1, 1, 1, 1));
        if (contrastRatio(preferred, bg) >= 4.5) {
            return preferred;
        }
        var white = Qt.rgba(1, 1, 1, 1);
        var black = Qt.rgba(0, 0, 0, 1);
        return contrastRatio(white, bg) >= contrastRatio(black, bg) ? white : black;
    }

    function readableAccentOn(bgColor, accentColor, fallbackTextColor) {
        var bg = safeColor(bgColor, Qt.rgba(0, 0, 0, 1));
        var accent = safeColor(accentColor, safeColor(fallbackTextColor, Qt.rgba(1, 1, 1, 1)));
        if (contrastRatio(accent, bg) >= 4.5) {
            return accent;
        }
        var textColor = safeColor(fallbackTextColor, Qt.rgba(1, 1, 1, 1));
        return Qt.rgba(textColor.r, textColor.g, textColor.b, 1.0);
    }

    function isFiniteRectLike(r) {
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
            && r.height > 0;
    }

    function normalizeDetachedOriginRect(originRect, fallbackRect) {
        if (isFiniteRectLike(originRect)) {
            return Qt.rect(
                Math.round(originRect.x),
                Math.round(originRect.y),
                Math.max(1, Math.round(originRect.width)),
                Math.max(1, Math.round(originRect.height))
            );
        }
        var fb = isFiniteRectLike(fallbackRect) ? fallbackRect : detachedHostRect();
        return Qt.rect(
            Math.round(fb.x + (fb.width * 0.35)),
            Math.round(fb.y + (fb.height * 0.30)),
            Math.max(1, Math.round(fb.width * 0.30)),
            Math.max(1, Math.round(fb.height * 0.20))
        );
    }

    function detachedHostRect() {
        var hostW = Math.max(1, Math.round(finalW));
        var hostH = Math.max(1, Math.round(finalH));
        var hostXv = Math.round(finalX);
        var hostYv = Math.round(finalY);
        if (!isFinite(hostXv) || !isFinite(hostYv)) {
            hostXv = Math.round(mainWin.x);
            hostYv = Math.round(mainWin.y);
        }
        if (!isFinite(hostW) || hostW <= 0) {
            hostW = Math.max(1, Math.round(mainWin.width));
        }
        if (!isFinite(hostH) || hostH <= 0) {
            hostH = Math.max(1, Math.round(mainWin.height));
        }
        return Qt.rect(hostXv, hostYv, hostW, hostH);
    }

    function detachedFrameColorsForSequence(sequence) {
        var palette = detachedFramePalette || [];
        if (!palette.length) {
            return { "monitor": "#00E5FF", "canvas": "#FF8C00" };
        }
        var idx = Math.max(0, Math.round(sequence - 1)) % palette.length;
        var pair = palette[idx];
        var mon = (pair && pair.monitor) ? pair.monitor : "#00E5FF";
        var can = (pair && pair.canvas) ? pair.canvas : "#FF8C00";
        return { "monitor": mon, "canvas": can };
    }

    function detachedPanelTitleText(rawTitle) {
        var text = (rawTitle !== undefined && rawTitle !== null) ? String(rawTitle) : "";
        if (!text || text.length <= 0) {
            return "Module";
        }
        return text;
    }

    function setPanelTaskbarTitle(nextTitle) {
        if (nextTitle === undefined || nextTitle === null) {
            panelTaskbarTitle = "";
            return;
        }
        panelTaskbarTitle = String(nextTitle);
    }

// === DETACHED PANEL TITLE SYNC (fix.py) ===
function syncDetachedPanelTitleFromTileIndex(tileIndex) {
    var idx = Math.round(tileIndex)
    if (!isFinite(idx) || idx < 0) idx = 0
    var titleText = "Module"
    try {
        if (mainContent && mainContent.tileTitleForIndex) {
            titleText = String(mainContent.tileTitleForIndex(idx) || "Module")
        }
    } catch (e0) {
    }
    detachedInitialTileIndex = idx
    detachedPanelTitle = titleText
    setPanelTaskbarTitle("CSPM - " + titleText)
}

    function emitDetachedDidCloseOnce() {
        if (!mainWin.detachedMode || mainWin._detachedDidCloseEmitted) return;
        mainWin._detachedDidCloseEmitted = true;
        mainWin.didClose(mainWin.instanceId);
    }

    function applyDetachedPanelTaskbarTitles(panelTitle) {
        var titleText = detachedPanelTitleText(panelTitle);
        var list = detachedWindows ? detachedWindows : [];
        var matches = [];
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry || !entry.windowRef) continue;
            if (detachedPanelTitleText(entry.panelTitle) !== titleText) continue;
            matches.push(entry);
        }

        var total = matches.length;
        for (var j = 0; j < total; j++) {
            var win = matches[j].windowRef;
            if (!win) continue;
            var taskbarLabel = "CSPM - " + titleText;
            if (total > 1) {
                taskbarLabel += " (" + (j + 1) + ")";
            }
            try {
                if (win.setPanelTaskbarTitle) {
                    win.setPanelTaskbarTitle(taskbarLabel);
                } else {
                    win.title = taskbarLabel;
                }
            } catch (e) {
            }
        }
    }

    function unregisterDetachedWindow(instanceId, windowRef) {
        var list = detachedWindows ? detachedWindows : [];
        var next = [];
        var removedTitles = ({});
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry) continue;
            var sameInstance = (instanceId && entry.instanceId === instanceId);
            var sameRef = (windowRef && entry.windowRef === windowRef);
            if (!(sameInstance || sameRef)) {
                next.push(entry);
            } else {
                var removedTitle = detachedPanelTitleText(entry.panelTitle);
                removedTitles[removedTitle] = true;
            }
        }
        detachedWindows = next;
        for (var key in removedTitles) {
            if (removedTitles[key]) {
                applyDetachedPanelTaskbarTitles(key);
            }
        }
    }

    function launchDetachedPanel(tileIndex, titleText, state, originRect, sourceContentRef) {
        var detachedComponent = Qt.createComponent(Qt.resolvedUrl("DetachedShellWindow.qml"));
        if (!detachedComponent) {
            phaseLog("DETACH", "Floating component unavailable");
            return false;
        }
        if (detachedComponent.status === Component.Error) {
            var err = detachedComponent.errorString ? detachedComponent.errorString() : "<unknown>";
            phaseLog("DETACH", "Floating component load failed: " + err);
            return false;
        }
        if (detachedComponent.status !== Component.Ready) {
            phaseLog("DETACH", "Floating component not ready status=" + detachedComponent.status);
            return false;
        }

        var seq = detachedWindowSeq + 1;
        detachedWindowSeq = seq;
        var colors = detachedFrameColorsForSequence(seq);
        var hostRect = detachedHostRect();
        var launchRect = normalizeDetachedOriginRect(originRect, hostRect);
        var idx = Math.round(tileIndex);
        if (!isFinite(idx) || idx < -1) idx = 0;
        var panelTitle = detachedPanelTitleText(titleText);
        var dockHostRef = mainWin.detachedMode && mainWin.dockHostWindowRef
            ? mainWin.dockHostWindowRef
            : mainWin;
        if (sfxBus && sfxBus.playLaunchBurst) {
            sfxBus.playLaunchBurst(0.90);
        }

        var instanceId = "detached-" + seq;
        var detachedWin = detachedComponent.createObject(null, {
            "detachedMode": true,
            "instanceId": instanceId,
            "appRef": mainWin.appRef,
            "dockHostWindowRef": dockHostRef,
            "t": mainWin.cloneThemeObject(mainWin.t),
            "detachedPanelTitle": panelTitle,
            "detachedOriginRect": launchRect,
            "detachedHostWindowRect": hostRect,
            "detachedInitialTileIndex": idx,
            "detachedInitialPanelState": state,
            "monitorFrameColor": colors.monitor,
            "canvasFrameColor": colors.canvas,
            "debugFrameEnabled": mainWin.debugFrameEnabled
        });
        if (!detachedWin) {
            phaseLog("DETACH", "Failed to create detached window for tile=" + idx);
            return false;
        }

        var list = detachedWindows ? detachedWindows : [];
        list.push({
            "instanceId": instanceId,
            "windowRef": detachedWin,
            "panelTitle": panelTitle
        });
        detachedWindows = list;
        applyDetachedPanelTaskbarTitles(panelTitle);

        detachedWin.didClose.connect(function(closedInstanceId) {
            mainWin.unregisterDetachedWindow(closedInstanceId, detachedWin);
        });
        detachedWin.requestDetach.connect(function(nextTileIndex, nextTitleText, nextState, nextOriginRect) {
            mainWin.launchDetachedPanel(nextTileIndex, nextTitleText, nextState, nextOriginRect, detachedWin.mainContentRef);
        });

        if (sourceContentRef) {
            try {
                if (sourceContentRef.completeTearAwayTransition) {
                    sourceContentRef.completeTearAwayTransition(idx);
                } else if (sourceContentRef.startPortalReverseTransition) {
                    sourceContentRef.startPortalReverseTransition(idx);
                }
            } catch (e) {
            }
        }
        if (detachedWin.forceLaunchFocus) {
            try {
                detachedWin.forceLaunchFocus();
            } catch (e2) {
            }
        }
        return true;
    }

    function currentContentGlobalRect() {
        return Qt.rect(
            Math.round(finalX),
            Math.round(finalY),
            Math.max(1, Math.round(finalW)),
            Math.max(1, Math.round(finalH))
        );
    }

    function topLevelWindowsSafe() {
        try {
            var windows = applicationMemberSafe("topLevelWindows");
            if (windows) {
                return windows;
            }
        } catch (e) {
        }
        return [];
    }

    function applicationScreensSafe() {
        try {
            var screens = applicationMemberSafe("screens");
            if (screens) {
                return screens;
            }
        } catch (e) {
        }
        return [];
    }

    function applicationMemberSafe(memberName) {
        try {
            var application = Qt.application;
            return application ? application[memberName] : null;
        } catch (e) {
        }
        return null;
    }

    function contextMemberSafe(memberName) {
        try {
            return Function("try { return " + memberName + "; } catch (e) { return null; }")();
        } catch (e) {
        }
        return null;
    }

    function resolvePrimaryMainShellWindow() {
        var hostRef = null;
        try {
            hostRef = mainWin.dockHostWindowRef;
        } catch (e0) {
        }
        if (hostRef) {
            var hostDetached = false;
            try {
                hostDetached = !!hostRef.detachedMode;
            } catch (e1) {
            }
            if (!hostDetached) return hostRef;
        }

        var windows = topLevelWindowsSafe();
        var fallback = null;
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (!w || w === mainWin) continue;
            var isDetached = false;
            try {
                isDetached = !!w.detachedMode;
            } catch (e1) {
            }
            if (isDetached) continue;

            var isMainName = false;
            try {
                isMainName = (w.objectName === "CSPMMainWindow");
            } catch (e2) {
            }
            if (isMainName) return w;
            if (!fallback) fallback = w;
        }
        return fallback;
    }

    function isMainShellReadyForDirectDock(mainShell) {
        if (!mainShell) return false;
        try {
            if (mainShell.isClosing || mainShell.forceClose) return false;
        } catch (e) {
        }
        var content = null;
        try {
            content = mainShell.mainContentRef;
        } catch (e2) {
        }
        if (!content) return false;
        if (content.acceptsDirectDockInCurrentPhase) {
            try {
                return !!content.acceptsDirectDockInCurrentPhase();
            } catch (e4) {
            }
        }
        if (!content.isInMainMenuPhase) return false;
        try {
            return !!content.isInMainMenuPhase();
        } catch (e3) {
        }
        return false;
    }

    function shellGeometryRect(shellRef) {
        if (!shellRef) {
            return {
                "x": Math.round(finalX),
                "y": Math.round(finalY),
                "w": Math.max(1, Math.round(finalW)),
                "h": Math.max(1, Math.round(finalH))
            };
        }
        var gx = 0;
        var gy = 0;
        var gw = 1;
        var gh = 1;
        var usedFinal = false;
        try {
            gx = Math.round(shellRef.finalX);
            gy = Math.round(shellRef.finalY);
            gw = Math.max(1, Math.round(shellRef.finalW));
            gh = Math.max(1, Math.round(shellRef.finalH));
            usedFinal = isFinite(gx) && isFinite(gy) && isFinite(gw) && isFinite(gh) && gw > 0 && gh > 0;
        } catch (e1) {
            usedFinal = false;
        }
        if (!usedFinal) {
            try {
                gx = Math.round(shellRef.x);
                gy = Math.round(shellRef.y);
                gw = Math.max(1, Math.round(shellRef.width));
                gh = Math.max(1, Math.round(shellRef.height));
            } catch (e2) {
                gx = Math.round(finalX);
                gy = Math.round(finalY);
                gw = Math.max(1, Math.round(finalW));
                gh = Math.max(1, Math.round(finalH));
            }
        }
        return { "x": gx, "y": gy, "w": Math.max(1, gw), "h": Math.max(1, gh) };
    }

    function rectVisibleOnAnyScreen(rect) {
        if (!rect || rect.w <= 0 || rect.h <= 0) return false;
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return true;
        var minVisibleEdge = 56;
        for (var i = 0; i < screens.length; i++) {
            var s = screens[i];
            if (!s) continue;
            var ix = Math.max(rect.x, s.virtualX);
            var iy = Math.max(rect.y, s.virtualY);
            var ex = Math.min(rect.x + rect.w, s.virtualX + s.width);
            var ey = Math.min(rect.y + rect.h, s.virtualY + s.height);
            var iw = ex - ix;
            var ih = ey - iy;
            if (iw >= minVisibleEdge && ih >= minVisibleEdge) {
                return true;
            }
        }
        return false;
    }

    function mainShellNeedsReveal(mainShell) {
        if (!mainShell) return true;
        try {
            if (mainShell.forceClose || mainShell.isClosing) return true;
        } catch (e1) {
        }
        try {
            if (!mainShell.visible) return true;
        } catch (e2) {
        }
        try {
            if (mainShell.visibility === Window.Minimized) return true;
        } catch (e3) {
        }
        return !rectVisibleOnAnyScreen(shellGeometryRect(mainShell));
    }

    function resolveRevealScreenForDock(mainShell) {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return null;

        var sourceScreen = contentOwningScreen();
        if (!sourceScreen) {
            sourceScreen = screenForPoint(finalX + (finalW / 2.0), finalY + (finalH / 2.0), null);
        }
        if (!sourceScreen) sourceScreen = screens[0];
        if (screens.length <= 1) return sourceScreen;

        var rightScreen = adjacentScreenForDirection(1, sourceScreen);
        if (rightScreen) return rightScreen;
        var leftScreen = adjacentScreenForDirection(-1, sourceScreen);
        if (leftScreen) return leftScreen;
        return sourceScreen;
    }

    function centeredRectInVisibleArea(visibleRect, desiredW, desiredH) {
        var rect = visibleRect && visibleRect.w > 0 && visibleRect.h > 0
            ? visibleRect
            : { "x": Math.round(finalX), "y": Math.round(finalY), "w": Math.max(1, Math.round(finalW)), "h": Math.max(1, Math.round(finalH)) };
        var w = Math.max(1, Math.round(desiredW));
        var h = Math.max(1, Math.round(desiredH));
        if (w > rect.w) w = Math.max(1, Math.round(rect.w));
        if (h > rect.h) h = Math.max(1, Math.round(rect.h));
        return {
            "x": Math.round(rect.x + ((rect.w - w) * 0.5)),
            "y": Math.round(rect.y + ((rect.h - h) * 0.5)),
            "w": Math.max(1, w),
            "h": Math.max(1, h)
        };
    }

    function revealMainShellForDock(mainShell, activateNow) {
        if (!mainShell) return false;
        var shouldActivate = !!activateNow;
        var needsReveal = mainShellNeedsReveal(mainShell);

        if (needsReveal) {
            var revealScreen = resolveRevealScreenForDock(mainShell);
            var revealIdx = indexOfScreen(revealScreen);
            var revealInfo = null;
            if (revealIdx >= 0 && appRef && appRef.getScreenGeometry) {
                revealInfo = appRef.getScreenGeometry(revealIdx);
            }
            var vis = visibleRectForScreen(revealScreen, revealInfo);

            var desiredW = Math.max(1, Math.round(finalW));
            var desiredH = Math.max(1, Math.round(finalH));
            try {
                if (mainShell.restoreGeometryValid) {
                    desiredW = Math.max(1, Math.round(mainShell.restoreFinalW));
                    desiredH = Math.max(1, Math.round(mainShell.restoreFinalH));
                } else {
                    desiredW = Math.max(1, Math.round(mainShell.finalW));
                    desiredH = Math.max(1, Math.round(mainShell.finalH));
                }
            } catch (e1) {
            }
            if (!isFinite(desiredW) || desiredW <= 0) desiredW = Math.max(1, Math.round(vis.w * 0.72));
            if (!isFinite(desiredH) || desiredH <= 0) desiredH = Math.max(1, Math.round(vis.h * 0.72));
            var targetRect = centeredRectInVisibleArea(vis, desiredW, desiredH);

            var priorSuppressed = false;
            var hasSuppressed = false;
            try {
                priorSuppressed = !!mainShell.geometryTransitionSuppressed;
                hasSuppressed = true;
                mainShell.geometryTransitionSuppressed = true;
            } catch (e2) {
            }

            try {
                if (mainShell.clearMinimizeRestoreState) mainShell.clearMinimizeRestoreState();
            } catch (e3) {
            }
            try {
                mainShell.isMinimizing = false;
                mainShell.isRestoringFromMinimize = false;
                mainShell.wasWindowMinimized = false;
            } catch (e4) {
            }
            try {
                if (mainShell.stopMaximizeFxAnimations) mainShell.stopMaximizeFxAnimations();
                mainShell.maximizeAnimInProgress = false;
            } catch (e5) {
            }
            try {
                mainShell.uiMaximized = false;
            } catch (e6) {
            }
            try {
                if (mainShell.visibility === Window.Minimized && mainShell.showNormal) {
                    mainShell.showNormal();
                } else if (mainShell.show) {
                    mainShell.show();
                }
            } catch (e7) {
                try {
                    if (mainShell.show) mainShell.show();
                } catch (e8) {
                }
            }
            try {
                mainShell.opacity = 1.0;
            } catch (e9) {
            }

            try {
                if (mainShell.adoptTargetScreen) {
                    mainShell.adoptTargetScreen(revealScreen);
                } else {
                    mainShell.targetScreen = revealScreen;
                    if (revealIdx >= 0) mainShell.targetScreenIndex = revealIdx;
                }
            } catch (e10) {
            }

            try {
                mainShell.finalX = Math.round(targetRect.x);
                mainShell.finalY = Math.round(targetRect.y);
                mainShell.finalW = Math.max(1, Math.round(targetRect.w));
                mainShell.finalH = Math.max(1, Math.round(targetRect.h));
            } catch (e11) {
            }
            try {
                if (mainShell.updateTargetScreenFromFinalCenter) mainShell.updateTargetScreenFromFinalCenter();
                if (mainShell.refreshActiveVisibleRect) mainShell.refreshActiveVisibleRect();
                if (mainShell.applyHostEnvelopeForTarget) mainShell.applyHostEnvelopeForTarget();
                if (mainShell.updateCanvasGeometry) mainShell.updateCanvasGeometry();
                if (mainShell.rememberRestoreGeometry) mainShell.rememberRestoreGeometry();
            } catch (e12) {
            }

            if (hasSuppressed) {
                try {
                    mainShell.geometryTransitionSuppressed = priorSuppressed;
                } catch (e13) {
                }
            }
        }

        if (shouldActivate) {
            try {
                if (mainShell.raise) mainShell.raise();
                mainWin._requestActivateIfFocusable(mainShell);
            } catch (e14) {
            }
        }
        return true;
    }

    function focusMainShell(mainShell) {
        if (!mainShell) return false;
        return revealMainShellForDock(mainShell, true);
    }

    function resolveDockLandingPoint(mainShell, tileIndex) {
        if (!mainShell) {
            return { "x": Math.round(finalX + (finalW / 2.0)), "y": Math.round(finalY + (finalH / 2.0)) };
        }

        var rect = null;
        try {
            if (mainShell.mainContentRef && mainShell.mainContentRef.resolveDockLandingRect) {
                rect = mainShell.mainContentRef.resolveDockLandingRect(tileIndex);
            }
        } catch (e) {
        }

        if (rect
            && typeof rect.x === "number"
            && typeof rect.y === "number"
            && typeof rect.width === "number"
            && typeof rect.height === "number"
            && isFinite(rect.x)
            && isFinite(rect.y)
            && isFinite(rect.width)
            && isFinite(rect.height)
            && rect.width > 0
            && rect.height > 0) {
            return {
                "x": Math.round(rect.x + (rect.width / 2.0)),
                "y": Math.round(rect.y + (rect.height / 2.0))
            };
        }

        try {
            return {
                "x": Math.round(mainShell.x + (mainShell.width / 2.0)),
                "y": Math.round(mainShell.y + (mainShell.height / 2.0))
            };
        } catch (e2) {
        }
        return { "x": Math.round(finalX + (finalW / 2.0)), "y": Math.round(finalY + (finalH / 2.0)) };
    }

    function setCloseTargetOverride(point) {
        if (!point
            || typeof point.x !== "number"
            || typeof point.y !== "number"
            || !isFinite(point.x)
            || !isFinite(point.y)) {
            closeTargetOverrideActive = false;
            return;
        }
        closeTargetOverrideX = Math.round(point.x);
        closeTargetOverrideY = Math.round(point.y);
        closeTargetOverrideActive = true;
    }

    function clearCloseTargetOverride() {
        closeTargetOverrideActive = false;
        closeTargetOverrideX = 0;
        closeTargetOverrideY = 0;
    }

    function clearPendingDockCommit() {
        pendingDockCommitRequest = null;
    }

    function queuePendingDockCommit(requestInfo, autoReturnToMenu) {
        if (!requestInfo || !requestInfo.mainShell) {
            pendingDockCommitRequest = null;
            return false;
        }
        var idx = Math.round(requestInfo.tileIndex);
        if (!isFinite(idx) || idx < -1) idx = -1;
        var origin = isFiniteRectLike(requestInfo.originRect)
            ? requestInfo.originRect
            : currentContentGlobalRect();
        pendingDockCommitRequest = {
            "tileIndex": idx,
            "state": requestInfo.state,
            "originRect": Qt.rect(
                Math.round(origin.x),
                Math.round(origin.y),
                Math.max(1, Math.round(origin.width)),
                Math.max(1, Math.round(origin.height))
            ),
            "mainShell": requestInfo.mainShell,
            "autoReturnToMenu": !!autoReturnToMenu
        };
        return true;
    }

    function commitPendingDockAfterClose() {
        var req = pendingDockCommitRequest;
        pendingDockCommitRequest = null;
        if (!req || !req.mainShell) return false;

        var content = null;
        try {
            content = req.mainShell.mainContentRef;
        } catch (e) {
        }
        if (!content) return false;

        var accepted = false;
        try {
            if (req.autoReturnToMenu && content.autoReturnToMenuThenDock) {
                accepted = !!content.autoReturnToMenuThenDock(
                    req.tileIndex,
                    req.state,
                    req.originRect
                );
            } else if (!req.autoReturnToMenu && content.requestDockIngest) {
                accepted = !!content.requestDockIngest(
                    req.tileIndex,
                    req.state,
                    req.originRect
                );
            }
        } catch (e2) {
            accepted = false;
        }
        if (accepted) {
            try {
                if (req.mainShell.sfxBusRef && req.mainShell.sfxBusRef.playDockSettle) {
                    req.mainShell.sfxBusRef.playDockSettle(0.72);
                }
            } catch (dockSfxError) {
            }
            focusMainShell(req.mainShell);
        }
        return accepted;
    }

    function closeRedockPrompt() {
        redockPromptVisible = false;
        redockPromptTitle = "";
        redockPromptMessage = "";
        redockPromptAllowAuto = false;
        redockPromptAllowFocus = false;
        pendingRedockRequest = null;
    }

    function presentRedockPrompt(requestInfo, titleText, messageText, allowAuto, allowFocus) {
        pendingRedockRequest = requestInfo;
        redockPromptTitle = titleText ? String(titleText) : "Docking Needs Main Menu";
        redockPromptMessage = messageText
            ? String(messageText)
            : "This panel can dock only when the main window is showing Main Menu.";
        redockPromptAllowAuto = !!allowAuto;
        redockPromptAllowFocus = !!allowFocus;
        redockPromptVisible = true;
    }

    function executeDockBackRequest(requestInfo, autoReturnToMenu) {
        if (!requestInfo || !requestInfo.mainShell) return false;
        var mainShell = requestInfo.mainShell;
        var content = null;
        try {
            content = mainShell.mainContentRef;
        } catch (e) {
        }
        if (!content) return false;
        if (autoReturnToMenu) {
            if (!content.autoReturnToMenuThenDock) return false;
        } else {
            if (!content.requestDockIngest) return false;
            if (!isMainShellReadyForDirectDock(mainShell)) return false;
        }
        if (!queuePendingDockCommit(requestInfo, autoReturnToMenu)) {
            return false;
        }
        if (!revealMainShellForDock(mainShell, false)) {
            clearPendingDockCommit();
            return false;
        }
        setCloseTargetOverride(resolveDockLandingPoint(mainShell, requestInfo.tileIndex));
        if (!requestCloseAnimation()) {
            clearCloseTargetOverride();
            clearPendingDockCommit();
            return false;
        }
        return true;
    }

    function handleReturnToDock(tileIndex, titleText, state, originRect) {
        if (!mainWin.detachedMode) return false;
        var idx = Math.round(tileIndex);
        if (!isFinite(idx) || idx < -1) idx = -1;

        var dockOrigin = isFiniteRectLike(originRect) ? originRect : currentContentGlobalRect();
        var mainShell = resolvePrimaryMainShellWindow();
        if (!mainShell) {
            presentRedockPrompt(
                null,
                "Main Window Not Found",
                "No main CSPM window is available to receive this panel right now.",
                false,
                false
            );
            return false;
        }

        var requestInfo = {
            "tileIndex": idx,
            "titleText": titleText ? String(titleText) : detachedPanelTitleText(detachedPanelTitle),
            "state": state,
            "originRect": Qt.rect(
                Math.round(dockOrigin.x),
                Math.round(dockOrigin.y),
                Math.max(1, Math.round(dockOrigin.width)),
                Math.max(1, Math.round(dockOrigin.height))
            ),
            "mainShell": mainShell
        };

        if (isMainShellReadyForDirectDock(mainShell)) {
            if (executeDockBackRequest(requestInfo, false)) {
                return true;
            }
        }

        presentRedockPrompt(
            requestInfo,
            "Docking Needs Main Menu",
            "This panel can dock only when Main Menu is active in the main window.",
            true,
            true
        );
        return false;
    }

    function redockPromptAutoReturnAndDock() {
        if (!pendingRedockRequest) {
            closeRedockPrompt();
            return;
        }
        var req = pendingRedockRequest;
        closeRedockPrompt();
        if (!executeDockBackRequest(req, true)) {
            presentRedockPrompt(
                req,
                "Auto Dock Could Not Start",
                "The main window could not switch to Main Menu for docking. Focus it and try again.",
                true,
                true
            );
        }
    }

    function redockPromptFocusMain() {
        if (!pendingRedockRequest || !pendingRedockRequest.mainShell) {
            closeRedockPrompt();
            return;
        }
        focusMainShell(pendingRedockRequest.mainShell);
        closeRedockPrompt();
    }

    function closeGuardWindowVisibility(windowRef) {
        var minimized = false;
        var hidden = false;
        if (!windowRef) {
            return { "minimized": false, "hidden": true };
        }
        try {
            minimized = (windowRef.visibility === Window.Minimized);
        } catch (e1) {
        }
        try {
            hidden = !windowRef.visible;
        } catch (e2) {
            hidden = false;
        }
        return {
            "minimized": !!minimized,
            "hidden": !!hidden
        };
    }

    function closeGuardRiskSnapshot(windowRef) {
        var summary = {
            "hasUnsavedWork": false,
            "hasRunningTimer": false,
            "activeDescriptor": "Main Menu",
            "activeTileIndex": -1,
            "inMainMenu": true,
            "panels": [],
            "stateByTile": ({})
        };
        if (!windowRef) return summary;
        var content = null;
        try {
            content = windowRef.mainContentRef;
        } catch (e1) {
        }
        if (!content) return summary;
        try {
            if (content.closeRiskSnapshot) {
                var raw = content.closeRiskSnapshot();
                if (raw && typeof raw === "object") {
                    summary.hasUnsavedWork = !!raw.hasUnsavedWork;
                    summary.hasRunningTimer = !!raw.hasRunningTimer;
                    summary.activeDescriptor = raw.activeDescriptor
                        ? String(raw.activeDescriptor)
                        : "Main Menu";
                    summary.activeTileIndex = (typeof raw.activeTileIndex === "number")
                        ? raw.activeTileIndex
                        : -1;
                    summary.inMainMenu = !!raw.inMainMenu;
                    summary.panels = raw.panels ? raw.panels : [];
                    summary.stateByTile = raw.stateByTile ? raw.stateByTile : ({});
                }
            }
        } catch (e2) {
        }
        return summary;
    }

    function checkpointCloseSessionForWindow(windowRef) {
        var snapshot = closeGuardRiskSnapshot(windowRef);
        if (!windowRef) return snapshot;
        var content = null;
        try {
            content = windowRef.mainContentRef;
        } catch (e1) {
        }
        if (!content) return snapshot;
        try {
            if (content.checkpointCloseSessionState) {
                var raw = content.checkpointCloseSessionState();
                if (raw && typeof raw === "object") {
                    snapshot.hasUnsavedWork = !!raw.hasUnsavedWork;
                    snapshot.hasRunningTimer = !!raw.hasRunningTimer;
                    snapshot.activeDescriptor = raw.activeDescriptor
                        ? String(raw.activeDescriptor)
                        : "Main Menu";
                    snapshot.activeTileIndex = (typeof raw.activeTileIndex === "number")
                        ? raw.activeTileIndex
                        : -1;
                    snapshot.inMainMenu = !!raw.inMainMenu;
                    snapshot.panels = raw.panels ? raw.panels : [];
                    snapshot.stateByTile = raw.stateByTile ? raw.stateByTile : ({});
                }
            }
        } catch (e2) {
        }
        return snapshot;
    }

    function closeGuardStatusText(hasUnsavedWork, hasRunningTimer, visibilityInfo) {
        var tags = [];
        if (hasUnsavedWork) tags.push("Unsaved work");
        if (hasRunningTimer) tags.push("Running timer");
        if (visibilityInfo && visibilityInfo.minimized) tags.push("Minimized");
        if (visibilityInfo && visibilityInfo.hidden) tags.push("Hidden");
        if (!tags.length) tags.push("No pending changes");
        return tags.join(" | ");
    }

    function closeGuardDescriptorLooksReporting(textValue) {
        var text = String(textValue || "").trim().toLowerCase();
        if (text.length <= 0) return false;
        return (
            text.indexOf("report") >= 0
            || text.indexOf("dashboard") >= 0
            || text.indexOf("analytics") >= 0
            || text.indexOf("summary") >= 0
        );
    }

    function normalizeCloseGuardRisk(risk) {
        if (!risk || typeof risk !== "object") return risk;

        var isReportLike = closeGuardDescriptorLooksReporting(risk.activeDescriptor);
        if (!isReportLike && risk.panels && risk.panels.length > 0) {
            for (var i = 0; i < risk.panels.length; i++) {
                var panel = risk.panels[i];
                if (!panel || typeof panel !== "object") continue;
                if (closeGuardDescriptorLooksReporting(panel.titleText)) {
                    isReportLike = true;
                    break;
                }
                var panelState = panel.state;
                if (panelState && typeof panelState === "object") {
                    if (closeGuardDescriptorLooksReporting(panelState.focusNodeTitle)) {
                        isReportLike = true;
                        break;
                    }
                }
            }
        }

        if (isReportLike) {
            risk.hasUnsavedWork = false;
            risk.hasRunningTimer = false;
        }
        return risk;
    }

    function collectCloseGuardRows() {
        var rows = [];
        var detachedCount = 0;
        var unsavedCount = 0;
        var runningTimerCount = 0;

        var mainRisk = normalizeCloseGuardRisk(closeGuardRiskSnapshot(mainWin));
        var mainVisibility = closeGuardWindowVisibility(mainWin);
        var mainPanelActive = !mainRisk.inMainMenu;
        var mainHasUnsavedRisk = mainPanelActive && !!mainRisk.hasUnsavedWork;
        var mainHasTimerRisk = mainPanelActive && !!mainRisk.hasRunningTimer;
        rows.push({
            "windowId": "main-shell",
            "windowLabel": "Main Window",
            "detailText": "Current view: " + (mainRisk.activeDescriptor ? String(mainRisk.activeDescriptor) : "Main Menu"),
            "statusText": closeGuardStatusText(mainHasUnsavedRisk, mainHasTimerRisk, mainVisibility),
            "hasUnsavedWork": mainHasUnsavedRisk,
            "hasRunningTimer": mainHasTimerRisk,
            "inMainMenu": !!mainRisk.inMainMenu,
            "detached": false,
            "windowRef": mainWin
        });
        if (mainHasUnsavedRisk) unsavedCount += 1;
        if (mainHasTimerRisk) runningTimerCount += 1;

        var list = detachedWindows ? detachedWindows : [];
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry || !entry.windowRef) continue;
            var detachedRef = entry.windowRef;
            var skip = false;
            try {
                skip = !!detachedRef.forceClose || !!detachedRef.isClosing;
            } catch (e1) {
            }
            if (skip) continue;

            detachedCount += 1;
            var detachedRisk = normalizeCloseGuardRisk(closeGuardRiskSnapshot(detachedRef));
            var detachedVisibility = closeGuardWindowVisibility(detachedRef);
            if (detachedRisk.hasUnsavedWork) unsavedCount += 1;
            if (detachedRisk.hasRunningTimer) runningTimerCount += 1;

            var panelTitle = detachedPanelTitleText(entry.panelTitle);
            var rowId = entry.instanceId ? String(entry.instanceId) : ("detached-row-" + i);
            rows.push({
                "windowId": rowId,
                "windowLabel": panelTitle,
                "detailText": "Detached window | Current view: "
                    + (detachedRisk.activeDescriptor ? String(detachedRisk.activeDescriptor) : "Main Menu"),
                "statusText": closeGuardStatusText(detachedRisk.hasUnsavedWork, detachedRisk.hasRunningTimer, detachedVisibility),
                "hasUnsavedWork": !!detachedRisk.hasUnsavedWork,
                "hasRunningTimer": !!detachedRisk.hasRunningTimer,
                "detached": true,
                "windowRef": detachedRef
            });
        }

        return {
            "rows": rows,
            "detachedCount": detachedCount,
            "unsavedCount": unsavedCount,
            "runningTimerCount": runningTimerCount
        };
    }

    function closeCloseGuard() {
        closeGuardVisible = false;
        closeGuardTitle = "";
        closeGuardMessage = "";
        closeGuardDetachedCount = 0;
        closeGuardUnsavedCount = 0;
        closeGuardRunningTimerCount = 0;
        closeGuardWindowRows = [];
    }

    function presentMainCloseGuard(reason) {
        if (mainWin.detachedMode || mainWin.forceClose || mainWin.isClosing) return false;
        var details = collectCloseGuardRows();
        if (!details || !details.rows || details.rows.length <= 0) {
            closeCloseGuard();
            return false;
        }
        var mainRow = details.rows[0];
        var mainHasRisk = !!(mainRow && (mainRow.hasUnsavedWork || mainRow.hasRunningTimer));
        var hasDetached = details.detachedCount > 0;
        if (!hasDetached && !mainHasRisk) {
            closeCloseGuard();
            return false;
        }
        closeGuardWindowRows = details.rows;
        closeGuardDetachedCount = details.detachedCount;
        closeGuardUnsavedCount = details.unsavedCount;
        closeGuardRunningTimerCount = details.runningTimerCount;
        if (hasDetached && mainHasRisk) {
            closeGuardTitle = "Unsaved Work Across Open Windows";
            closeGuardMessage = "You still have " + details.detachedCount
                + " detached windows and active unsaved work in main ("
                + details.unsavedCount + " windows with unsaved work, "
                + details.runningTimerCount + " running timers).";
        } else if (hasDetached) {
            closeGuardTitle = "Detached Windows Still Open";
            closeGuardMessage = "You still have " + details.detachedCount
                + " detached windows (" + details.unsavedCount
                + " with unsaved work, " + details.runningTimerCount + " running timers).";
        } else {
            closeGuardTitle = "Unsaved Work in Main Window";
            closeGuardMessage = "The active main window panel has unsaved data or a running timer that is not yet"
                + " committed to the database exactly as entered. Save and verify before exiting to avoid data loss.";
        }
        closeGuardVisible = true;
        autoCheckpointCloseSession("close-guard-presented");
        phaseLog("CLOSING", "Close guard presented reason=" + reason
            + " detached=" + details.detachedCount
            + " unsaved=" + details.unsavedCount
            + " timers=" + details.runningTimerCount);
        return true;
    }

    function closeGuardRowForId(windowId) {
        if (!windowId) return null;
        var rows = closeGuardWindowRows ? closeGuardWindowRows : [];
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            if (!row) continue;
            if (String(row.windowId) === String(windowId)) {
                return row;
            }
        }
        return null;
    }

    function focusAnyWindow(windowRef) {
        if (!windowRef) return false;
        try {
            if (windowRef.visibility === Window.Minimized && windowRef.showNormal) {
                windowRef.showNormal();
            }
        } catch (e1) {
        }
        try {
            if (!windowRef.visible) {
                if (windowRef.show) {
                    windowRef.show();
                } else {
                    windowRef.visible = true;
                }
            }
        } catch (e2) {
        }
        try {
            if (windowRef.raise) windowRef.raise();
            mainWin._requestActivateIfFocusable(windowRef);
        } catch (e3) {
        }
        return true;
    }

    function focusWindowFromCloseGuard(windowId) {
        var row = closeGuardRowForId(windowId);
        if (!row || !row.windowRef) return false;
        return focusAnyWindow(row.windowRef);
    }

    function closeGuardReviewWindows() {
        var rows = closeGuardWindowRows ? closeGuardWindowRows : [];
        var targetRef = null;
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            if (!row || !row.detached || !row.windowRef) continue;
            if (row.hasUnsavedWork || row.hasRunningTimer) {
                targetRef = row.windowRef;
                break;
            }
        }
        if (!targetRef) {
            for (var j = 0; j < rows.length; j++) {
                var fallbackRow = rows[j];
                if (!fallbackRow || !fallbackRow.detached || !fallbackRow.windowRef) continue;
                targetRef = fallbackRow.windowRef;
                break;
            }
        }
        closeCloseGuard();
        if (targetRef) {
            focusAnyWindow(targetRef);
        } else {
            focusAnyWindow(mainWin);
        }
    }

    function collectCloseCheckpointPayload() {
        var payload = {
            "savedAtMs": Date.now(),
            "source": "main-close-guard",
            "windows": []
        };

        var mainSnapshot = checkpointCloseSessionForWindow(mainWin);
        var mainPanelActive = !mainSnapshot.inMainMenu;
        var mainGeom = shellGeometryRect(mainWin);
        payload.windows.push({
            "windowId": "main-shell",
            "windowLabel": "Main Window",
            "detachedWindow": false,
            "activeDescriptor": mainSnapshot.activeDescriptor,
            "activeTileIndex": (typeof mainSnapshot.activeTileIndex === "number") ? mainSnapshot.activeTileIndex : -1,
            "inMainMenu": !!mainSnapshot.inMainMenu,
            "hasUnsavedWork": mainPanelActive && !!mainSnapshot.hasUnsavedWork,
            "hasRunningTimer": mainPanelActive && !!mainSnapshot.hasRunningTimer,
            "panels": mainSnapshot.panels ? mainSnapshot.panels : [],
            "stateByTile": mainSnapshot.stateByTile ? mainSnapshot.stateByTile : ({}),
            "geometry": {
                "x": mainGeom.x,
                "y": mainGeom.y,
                "w": mainGeom.w,
                "h": mainGeom.h
            }
        });

        var list = detachedWindows ? detachedWindows : [];
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry || !entry.windowRef) continue;
            var detachedRef = entry.windowRef;
            var skip = false;
            try {
                skip = !!detachedRef.forceClose || !!detachedRef.isClosing;
            } catch (e1) {
            }
            if (skip) continue;

            var detachedSnapshot = checkpointCloseSessionForWindow(detachedRef);
            var geom = shellGeometryRect(detachedRef);
            payload.windows.push({
                "windowId": entry.instanceId ? String(entry.instanceId) : ("detached-row-" + i),
                "windowLabel": detachedPanelTitleText(entry.panelTitle),
                "detachedWindow": true,
                "activeDescriptor": detachedSnapshot.activeDescriptor,
                "activeTileIndex": (typeof detachedSnapshot.activeTileIndex === "number") ? detachedSnapshot.activeTileIndex : -1,
                "inMainMenu": !!detachedSnapshot.inMainMenu,
                "hasUnsavedWork": !!detachedSnapshot.hasUnsavedWork,
                "hasRunningTimer": !!detachedSnapshot.hasRunningTimer,
                "panels": detachedSnapshot.panels ? detachedSnapshot.panels : [],
                "stateByTile": detachedSnapshot.stateByTile ? detachedSnapshot.stateByTile : ({}),
                "geometry": {
                    "x": geom.x,
                    "y": geom.y,
                    "w": geom.w,
                    "h": geom.h
                }
            });
        }

        return payload;
    }

    function persistCloseCheckpointPayload(payload) {
        if (!payload) return false;
        try {
            if (appRef && appRef.saveCloseSessionSnapshot) {
                return !!appRef.saveCloseSessionSnapshot(payload);
            }
        } catch (e1) {
        }
        return false;
    }

    function payloadHasCloseRisk(payload) {
        if (!payload || !payload.windows) return false;
        var windows = payload.windows;
        for (var i = 0; i < windows.length; i++) {
            var row = windows[i];
            if (!row) continue;
            if (row.hasUnsavedWork || row.hasRunningTimer) return true;
        }
        return false;
    }

    function checkpointPayloadSignature(payload) {
        if (!payload || !payload.windows) return "";
        try {
            return JSON.stringify(payload.windows);
        } catch (e1) {
        }
        return "";
    }

    function autoCheckpointCloseSession(reason) {
        if (mainWin.detachedMode || mainWin.forceClose || mainWin.isClosing) return false;
        var payload = collectCloseCheckpointPayload();
        var hasRisk = payloadHasCloseRisk(payload);
        payload.source = reason ? String(reason) : "periodic-risk-checkpoint";
        var signature = checkpointPayloadSignature(payload);
        if (signature && signature === mainWin.closeCheckpointSignature && hasRisk === mainWin.closeCheckpointHadRisk) {
            return false;
        }
        var saved = persistCloseCheckpointPayload(payload);
        if (saved) {
            mainWin.closeCheckpointSignature = signature;
            mainWin.closeCheckpointHadRisk = hasRisk;
        }
        return saved;
    }

    function closeRecoveryPrompt() {
        recoveryPromptVisible = false;
        recoveryPromptTitle = "";
        recoveryPromptMessage = "";
        recoveryPromptRows = [];
        pendingRecoveryPayload = null;
    }

    function buildRecoveryPromptRows(payload) {
        var rows = [];
        if (!payload || !payload.windows) return rows;
        var windows = payload.windows;
        for (var i = 0; i < windows.length; i++) {
            var row = windows[i];
            if (!row) continue;
            var label = row.windowLabel ? String(row.windowLabel) : (row.detachedWindow ? "Detached Window" : "Main Window");
            var activeDesc = row.activeDescriptor ? String(row.activeDescriptor) : "Main Menu";
            rows.push({
                "windowId": row.windowId ? String(row.windowId) : ("recover-row-" + i),
                "windowLabel": label,
                "detailText": "Current view: " + activeDesc,
                "statusText": closeGuardStatusText(!!row.hasUnsavedWork, !!row.hasRunningTimer, null),
                "hasUnsavedWork": !!row.hasUnsavedWork,
                "hasRunningTimer": !!row.hasRunningTimer,
                "detached": !!row.detachedWindow
            });
        }
        return rows;
    }

    function normalizeRecoveryRect(rawRect) {
        var fallback = currentContentGlobalRect();
        if (!rawRect) {
            return {
                "x": fallback.x,
                "y": fallback.y,
                "w": fallback.width,
                "h": fallback.height
            };
        }
        var x = Math.round(rawRect.x);
        var y = Math.round(rawRect.y);
        var w = Math.max(1, Math.round(rawRect.w));
        var h = Math.max(1, Math.round(rawRect.h));
        if (!isFinite(x) || !isFinite(y) || !isFinite(w) || !isFinite(h)) {
            return {
                "x": fallback.x,
                "y": fallback.y,
                "w": fallback.width,
                "h": fallback.height
            };
        }
        return { "x": x, "y": y, "w": w, "h": h };
    }

    function applyRecoveryPayload(payload) {
        if (!payload || !payload.windows) return false;
        var windows = payload.windows;
        var mainRow = null;
        var detachedRows = [];
        for (var i = 0; i < windows.length; i++) {
            var row = windows[i];
            if (!row) continue;
            if (row.detachedWindow) {
                detachedRows.push(row);
            } else if (!mainRow) {
                mainRow = row;
            }
        }

        if (mainRow && mainWin.mainContentRef && mainWin.mainContentRef.applyRecoveredSessionRow) {
            try {
                mainWin.mainContentRef.applyRecoveredSessionRow(mainRow);
            } catch (e1) {
            }
        }

        for (var j = 0; j < detachedRows.length; j++) {
            var detachedRow = detachedRows[j];
            if (!detachedRow) continue;
            var stateByTile = (detachedRow.stateByTile && typeof detachedRow.stateByTile === "object")
                ? detachedRow.stateByTile
                : ({});
            var activeIdx = (typeof detachedRow.activeTileIndex === "number")
                ? Math.round(detachedRow.activeTileIndex)
                : -1;
            if (activeIdx < 0 || activeIdx >= 8) {
                activeIdx = 0;
            }
            var initialState = null;
            if (stateByTile[activeIdx] !== undefined) {
                initialState = stateByTile[activeIdx];
            }
            var geom = normalizeRecoveryRect(detachedRow.geometry);
            var panelTitle = detachedRow.windowLabel ? String(detachedRow.windowLabel) : "Recovered Window";
            var launched = launchDetachedPanel(
                activeIdx,
                panelTitle,
                initialState,
                Qt.rect(geom.x, geom.y, geom.w, geom.h),
                null
            );
            if (!launched) continue;
            var list = detachedWindows ? detachedWindows : [];
            if (!list.length) continue;
            var detachedRef = list[list.length - 1].windowRef;
            if (detachedRef && detachedRef.mainContentRef && detachedRef.mainContentRef.applyRecoveredSessionRow) {
                try {
                    detachedRef.mainContentRef.applyRecoveredSessionRow(detachedRow);
                } catch (e2) {
                }
            }
        }
        focusAnyWindow(mainWin);
        return true;
    }

    function maybePresentPendingRecoveryPrompt() {
        if (mainWin.detachedMode || recoveryPromptHandled) return false;
        recoveryPromptHandled = true;
        if (!appRef || !appRef.getPendingCloseRecovery) return false;
        var payload = null;
        try {
            payload = appRef.getPendingCloseRecovery();
        } catch (e1) {
            payload = null;
        }
        if (!payload || !payload.available || !payload.payload) return false;

        pendingRecoveryPayload = payload.payload;
        recoveryPromptRows = buildRecoveryPromptRows(payload.payload);
        var summary = payload.summary ? payload.summary : ({});
        var unsavedCount = summary.unsavedCount ? summary.unsavedCount : 0;
        var runningCount = summary.runningTimerCount ? summary.runningTimerCount : 0;
        recoveryPromptTitle = "Recover Unsaved Windows?";
        recoveryPromptMessage = "Practice Console closed unexpectedly with unsaved work ("
            + unsavedCount + " windows with unsaved data, "
            + runningCount + " running timers)."
            + " Reopen previous windows or reset to default state.";
        recoveryPromptVisible = true;
        phaseLog("RECOVERY", "Pending recovery prompt shown unsaved=" + unsavedCount + " timers=" + runningCount);
        return true;
    }

    function recoverUnsavedWindows() {
        var payload = pendingRecoveryPayload;
        closeRecoveryPrompt();
        if (payload) {
            applyRecoveryPayload(payload);
        }
        try {
            if (appRef && appRef.resolvePendingCloseRecovery) {
                appRef.resolvePendingCloseRecovery("restore");
            }
        } catch (e1) {
        }
    }

    function resetRecoveredWindows() {
        closeRecoveryPrompt();
        try {
            if (appRef && appRef.resolvePendingCloseRecovery) {
                appRef.resolvePendingCloseRecovery("reset");
            }
        } catch (e1) {
        }
    }

    function beginCloseFromGuard(reason) {
        if (mainWin.forceClose || mainWin.isClosing) return;
        closeCloseGuard();
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        resetDragFxState();
        phaseLog("CLOSING", "Close confirmed via guard reason=" + reason);
        mainWin.transitionToClosing();
    }

    function closeGuardSaveAllAndExit() {
        var payload = collectCloseCheckpointPayload();
        var saved = persistCloseCheckpointPayload(payload);
        phaseLog("CLOSING", "Save-all checkpoint before exit saved=" + saved);
        beginCloseFromGuard(saved ? "save-all-exit" : "save-all-exit-unsaved");
    }

    function closeGuardExitWithoutSaving() {
        beginCloseFromGuard("exit-without-saving");
    }

    function phaseLog(tag, message) {
        if (!phaseLoggingEnabled) return;
        var line = "[" + tag + "] " + message;
        console.log(line);
        appendLiveLog(line);
    }

    function phaseMonitorLog(tag, frameIndex, message) {
        if (!phaseLoggingEnabled) return;
        if (!isFinite(frameIndex) || frameIndex <= 0) return;
        if ((frameIndex % 10) !== 0) return;
        var line = "[" + tag + " MONITOR] Frame " + frameIndex + ": " + message;
        console.log(line);
        appendLiveLog(line);
    }

    function interactionTraceActive() {
        return interactionTraceEnabled
            && isFinite(interactionTraceUntilMs)
            && interactionTraceUntilMs > 0
            && Date.now() <= interactionTraceUntilMs;
    }

    function interactionTraceAgeMs() {
        if (!isFinite(interactionTraceStartedMs) || interactionTraceStartedMs <= 0) {
            return 0;
        }
        return Math.max(0, Math.round(Date.now() - interactionTraceStartedMs));
    }

    function interactionTraceSnapshot() {
        return " hostWin=" + fmtRect(mainWin.x, mainWin.y, mainWin.width, mainWin.height)
            + " hostEnv=" + fmtRect(hostX, hostY, hostW, hostH)
            + " canvasGlobal=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " canvasLocal=" + fmtRect(canvasLocalX, canvasLocalY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " move=" + (userMoveInProgress ? "1" : "0")
            + " resize=" + (userResizeInProgress ? "1" : "0")
            + " systemMove=" + (systemMoveInProgress ? "1" : "0")
            + " dragStrategy=" + dragStrategy
            + " geomSupp=" + (geometryTransitionSuppressed ? "1" : "0");
    }

    function logInteractionTrace(tag, message, forceLog) {
        if (!interactionTraceEnabled) return;
        if (!forceLog && !interactionTraceActive()) return;
        interactionTraceEventSeq = interactionTraceEventSeq + 1;
        var line = "[CLICKTRACE #" + interactionTraceSeq
            + " +" + interactionTraceAgeMs() + "ms"
            + " e" + interactionTraceEventSeq
            + " " + interactionTraceMode + "] "
            + tag
            + (message && message.length > 0 ? (" " + message) : "")
            + interactionTraceSnapshot();
        console.log(line);
        appendLiveLog(line);
    }

    function beginInteractionTrace(mode, origin) {
        if (!interactionTraceEnabled) return;
        interactionTraceSeq = interactionTraceSeq + 1;
        interactionTraceEventSeq = 0;
        interactionTraceMode = String(mode || "");
        interactionTraceOrigin = String(origin || "");
        interactionTraceStartedMs = Date.now();
        interactionTraceUntilMs = interactionTraceStartedMs + interactionTraceWindowMs;
        logInteractionTrace("START", "origin=" + interactionTraceOrigin, true);
    }

    function extendInteractionTrace(extraMs) {
        if (!interactionTraceEnabled || !interactionTraceActive()) return;
        var bumpMs = isFinite(extraMs) ? Math.max(0, Math.round(extraMs)) : 120;
        interactionTraceUntilMs = Math.max(interactionTraceUntilMs, Date.now() + bumpMs);
    }

    function greenFrameLocalRect() {
        return {
            "x": Math.round(activeVisibleRect.x - mainWin.x),
            "y": Math.round(activeVisibleRect.y - mainWin.y),
            "w": Math.max(1, Math.round(activeVisibleRect.w)),
            "h": Math.max(1, Math.round(activeVisibleRect.h))
        };
    }

    function logGreenFrameGeometry(tag, stage) {
        if (!phaseLoggingEnabled) return;
        var greenLocal = greenFrameLocalRect();
        phaseLog(tag, stage
            + " hostWin=" + fmtRect(mainWin.x, mainWin.y, mainWin.width, mainWin.height)
            + " hostEnv=" + fmtRect(hostX, hostY, hostW, hostH)
            + " activeVisible=" + fmtRect(activeVisibleRect.x, activeVisibleRect.y, activeVisibleRect.w, activeVisibleRect.h)
            + " greenLocal=" + fmtRect(greenLocal.x, greenLocal.y, greenLocal.w, greenLocal.h)
            + " canvasGlobal=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " canvasLocal=" + fmtRect(canvasLocalX, canvasLocalY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " uiMax=" + (uiMaximized ? "1" : "0")
            + " fx=" + maximizeFxScaleX.toFixed(3) + "x" + maximizeFxScaleY.toFixed(3)
            + "@" + maximizeFxTransX.toFixed(1) + "," + maximizeFxTransY.toFixed(1));
    }

    function logDragForensic(stage, cursorPos) {
        if (!phaseLoggingEnabled) return;
        var greenLocal = greenFrameLocalRect();
        var cursorStr = "n/a";
        if (cursorPos
            && typeof cursorPos.x === "number"
            && typeof cursorPos.y === "number"
            && isFinite(cursorPos.x)
            && isFinite(cursorPos.y)) {
            cursorStr = Math.round(cursorPos.x) + "," + Math.round(cursorPos.y);
        }
        phaseLog("DRAG", stage
            + " cursor=" + cursorStr
            + " targetIdx=" + targetScreenIndex
            + " scale=" + monitorScalePercent + "%"
            + " usable=" + fmtRect(usableX, usableY, usableW, usableH)
            + " activeVisible=" + fmtRect(activeVisibleRect.x, activeVisibleRect.y, activeVisibleRect.w, activeVisibleRect.h)
            + " greenLocal=" + fmtRect(greenLocal.x, greenLocal.y, greenLocal.w, greenLocal.h)
            + " hostWin=" + fmtRect(mainWin.x, mainWin.y, mainWin.width, mainWin.height)
            + " hostEnv=" + fmtRect(hostX, hostY, hostW, hostH)
            + " canvasGlobal=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " canvasLocal=" + fmtRect(canvasLocalX, canvasLocalY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH));
    }

    function logCornerForensics(stage) {
        if (!phaseLoggingEnabled || !cornerForensicLoggingEnabled) return;
        var resolvedChromeRadius = -1;
        var layerSummary = "";
        if (typeof unifiedChrome !== "undefined" && unifiedChrome !== null
            && typeof unifiedChrome.cornerRadius === "number" && isFinite(unifiedChrome.cornerRadius)) {
            resolvedChromeRadius = Math.round(unifiedChrome.cornerRadius);
            if (typeof unifiedChrome.forensicCornerSummary === "function") {
                layerSummary = String(unifiedChrome.forensicCornerSummary());
            }
        }
        var resolvedMainContentMask = -1;
        var resolvedMainContentRadius = -1;
        var activeMainContent = mainWin.mainContentRef;
        if (activeMainContent) {
            if (typeof activeMainContent.roundedRootMaskEnabled === "boolean") {
                resolvedMainContentMask = activeMainContent.roundedRootMaskEnabled ? 1 : 0;
            }
            if (typeof activeMainContent.chromeCornerRadius === "number" && isFinite(activeMainContent.chromeCornerRadius)) {
                resolvedMainContentRadius = Math.round(activeMainContent.chromeCornerRadius);
            }
        }
        var signature = animationPhase
            + "|" + fmtRect(mainWin.x, mainWin.y, mainWin.width, mainWin.height)
            + "|" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + "|" + fmtRect(finalX, finalY, finalW, finalH)
            + "|" + chromeCornerRadiusPx()
            + "|" + canvasFrameCornerRadiusPx()
            + "|" + shellVisualCornerRadiusPx()
            + "|" + resolvedChromeRadius
            + "|" + resolvedMainContentMask
            + "|" + resolvedMainContentRadius
            + "|" + (shellRoundedMaskActive() ? "1" : "0")
            + "|" + ((typeof animationCanvasLayer !== "undefined" && animationCanvasLayer.roundedClipActive) ? "1" : "0")
            + "|" + (recoveryBandMaskActive ? "1" : "0")
            + "|" + layerSummary;
        if (stage === "timer" && signature === lastCornerForensicSignature) {
            return;
        }
        lastCornerForensicSignature = signature;
        lastCornerLayerSummary = layerSummary;
        phaseLog("ROUND", stage
            + " phase=" + animationPhase
            + " hostWin=" + fmtRect(mainWin.x, mainWin.y, mainWin.width, mainWin.height)
            + " hostEnv=" + fmtRect(hostX, hostY, hostW, hostH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " canvasLocal=" + fmtRect(canvasLocalX, canvasLocalY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " radiusChrome=" + chromeCornerRadiusPx()
            + " radiusCanvas=" + canvasFrameCornerRadiusPx()
            + " radiusShell=" + shellVisualCornerRadiusPx()
            + " radiusUnified=" + resolvedChromeRadius
            + " mainMask=" + resolvedMainContentMask
            + " mainRadius=" + resolvedMainContentRadius
            + " shellMaskActive=" + (shellRoundedMaskActive() ? "1" : "0")
            + " shellMaskLayer=" + ((typeof animationCanvasLayer !== "undefined" && animationCanvasLayer.roundedClipActive) ? "1" : "0")
            + " bandMask=" + (recoveryBandMaskActive ? "1" : "0")
            + " layerBleed=" + (layerSummary && layerSummary.length > 0 ? layerSummary : "n/a"));
    }

    function startCornerForensicBurst(reason, frames) {
        if (!phaseLoggingEnabled || !cornerForensicLoggingEnabled || !cornerForensicBurstEnabled) return;
        var burstFrames = cornerForensicBurstFrames;
        if (typeof frames === "number" && isFinite(frames)) {
            burstFrames = Math.round(frames);
        }
        burstFrames = Math.max(6, Math.min(240, burstFrames));
        cornerForensicBurstReason = reason ? String(reason) : "unspecified";
        cornerForensicBurstRemaining = burstFrames;
        logCornerForensics("burst-start-" + cornerForensicBurstReason + "-n" + burstFrames);
        cornerForensicBurstTimer.restart();
    }

    function activeVisibleRectSafe() {
        var rect = activeVisibleRect;
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = activeVisibleRectForMaximize();
        }
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = {
                "x": Math.round(finalX),
                "y": Math.round(finalY),
                "w": Math.max(1, Math.round(finalW)),
                "h": Math.max(1, Math.round(finalH))
            };
        }
        return {
            "x": Math.round(rect.x),
            "y": Math.round(rect.y),
            "w": Math.max(1, Math.round(rect.w)),
            "h": Math.max(1, Math.round(rect.h))
        };
    }

    function abortActiveInteractionsForRecovery() {
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        if (userResizeInProgress) {
            userResizeInProgress = false;
            resizeHandle = "none";
            resizeHasCursorAnchor = false;
        }
        if (userMoveInProgress || systemMoveInProgress || dragFinalizePending || dragStrategy !== "none") {
            userMoveInProgress = false;
            systemMoveInProgress = false;
            dragFinalizePending = false;
            dragStrategy = "none";
            resetDragFxState();
        }
    }

    function applySettledGeometryAtomically(reason, rememberRestore) {
        var prevGeomSuppressed = geometryTransitionSuppressed;
        geometryTransitionSuppressed = true;
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        geometryTransitionSuppressed = prevGeomSuppressed;
        if (rememberRestore !== false && !uiMaximized) {
            rememberRestoreGeometry();
        }
        if (reason && reason.length > 0) {
            phaseLog("RECOVER", reason
                + " content=" + fmtRect(finalX, finalY, finalW, finalH)
                + " activeVisible=" + fmtRect(activeVisibleRect.x, activeVisibleRect.y, activeVisibleRect.w, activeVisibleRect.h));
        }
    }

    function titlebarOutsideVisibleRect(rect) {
        if (!rect || rect.w <= 0 || rect.h <= 0) return false;
        var titleH = Math.max(1, Math.round(titleBarHeightPx()));
        var top = Math.round(finalY);
        var bottom = Math.round(top + titleH);
        var minY = Math.round(rect.y);
        var maxY = Math.round(rect.y + rect.h);
        return top < minY || bottom > maxY;
    }

    function clampTitlebarYToVisibleRect(rect) {
        if (!rect || rect.w <= 0 || rect.h <= 0) return false;
        var titleH = Math.max(1, Math.round(titleBarHeightPx()));
        var minY = Math.round(rect.y);
        var maxY = Math.round(rect.y + rect.h - titleH);
        if (maxY < minY) maxY = minY;
        var nextY = Math.round(clampNumber(finalY, minY, maxY));
        if (nextY === finalY) return false;
        finalY = nextY;
        return true;
    }

    function clampTitlebarToVisible(sourceTag) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize) return false;
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        var rect = activeVisibleRectSafe();
        if (!clampTitlebarYToVisibleRect(rect)) return false;
        var source = sourceTag ? sourceTag : "clamp-titlebar";
        applySettledGeometryAtomically("Titlebar clamp (" + source + ")", true);
        return true;
    }

    function hardRecenterToActiveMonitor(sourceTag) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize) return false;
        abortActiveInteractionsForRecovery();
        observeContentGlobalPosition();
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        var rect = activeVisibleRectSafe();
        if (!rect || rect.w <= 0 || rect.h <= 0) return false;

        if (uiMaximized) {
            finalX = Math.round(rect.x);
            finalY = Math.round(rect.y);
            finalW = Math.max(1, Math.round(rect.w));
            finalH = Math.max(1, Math.round(rect.h));
        } else {
            var nextW = Math.max(1, Math.round(finalW));
            var nextH = Math.max(1, Math.round(finalH));
            var minW = Math.min(rect.w, ratioToPixels(layoutRatios.resizeMinWidthPct, rect.w, rect.h, 1));
            var minH = Math.min(rect.h, ratioToPixels(layoutRatios.resizeMinHeightPct, rect.w, rect.h, 1));
            nextW = Math.max(minW, Math.min(nextW, rect.w));
            nextH = Math.max(minH, Math.min(nextH, rect.h));
            if (nextW > rect.w) nextW = rect.w;
            if (nextH > rect.h) nextH = rect.h;
            finalW = Math.max(1, Math.round(nextW));
            finalH = Math.max(1, Math.round(nextH));
            finalX = Math.round(rect.x + ((rect.w - finalW) * 0.5));
            finalY = Math.round(rect.y + ((rect.h - finalH) * 0.5));
            clampTitlebarYToVisibleRect(rect);
        }

        var source = sourceTag ? sourceTag : "hard-recenter";
        applySettledGeometryAtomically("Hard recenter (" + source + ")", true);
        return true;
    }

    function forceNudgeWindow(dx, dy, sourceTag) {
        var deltaX = isFinite(dx) ? Math.round(dx) : 0;
        var deltaY = isFinite(dy) ? Math.round(dy) : 0;
        if (deltaX === 0 && deltaY === 0) return false;
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;

        if (classicMoveModeActive) {
            return nudgeClassicMove(deltaX, deltaY, sourceTag);
        }

        abortActiveInteractionsForRecovery();
        observeContentGlobalPosition();
        finalX = Math.round(finalX + deltaX);
        finalY = Math.round(finalY + deltaY);
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        clampTitlebarYToVisibleRect(activeVisibleRectSafe());
        var source = sourceTag ? sourceTag : "force-nudge";
        applySettledGeometryAtomically("Force nudge (" + source + ")", true);
        return true;
    }

    function armClassicMoveMenu(sourceTag) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize) return false;
        classicMoveMenuArmed = true;
        if (classicMoveArmTimer.running) {
            classicMoveArmTimer.stop();
        }
        classicMoveArmTimer.start();
        phaseLog("MOVE", "Classic move menu armed source=" + (sourceTag ? sourceTag : "Alt+Space"));
        return true;
    }

    function startClassicMoveMode(sourceTag) {
        if (classicMoveModeActive) return true;
        if (!classicMoveMenuArmed) return false;
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) {
            classicMoveMenuArmed = false;
            return false;
        }
        abortActiveInteractionsForRecovery();
        observeContentGlobalPosition();
        classicMoveStartX = Math.round(finalX);
        classicMoveStartY = Math.round(finalY);
        classicMoveModeActive = true;
        classicMoveMenuArmed = false;
        if (classicMoveArmTimer.running) {
            classicMoveArmTimer.stop();
        }
        phaseLog("MOVE", "Classic move mode start source=" + (sourceTag ? sourceTag : "Alt+Space,M")
            + " content=" + fmtRect(finalX, finalY, finalW, finalH));
        return true;
    }

    function stopClassicMoveMode(commit, sourceTag) {
        classicMoveMenuArmed = false;
        if (classicMoveArmTimer.running) {
            classicMoveArmTimer.stop();
        }
        if (!classicMoveModeActive) return false;
        classicMoveModeActive = false;
        if (!commit) {
            finalX = Math.round(classicMoveStartX);
            finalY = Math.round(classicMoveStartY);
        }
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        clampTitlebarYToVisibleRect(activeVisibleRectSafe());
        applySettledGeometryAtomically(
            (commit ? "Classic move commit" : "Classic move cancel") + " (" + (sourceTag ? sourceTag : "classic-move") + ")",
            true
        );
        return true;
    }

    function nudgeClassicMove(dx, dy, sourceTag) {
        if (!classicMoveModeActive) return false;
        var deltaX = isFinite(dx) ? Math.round(dx) : 0;
        var deltaY = isFinite(dy) ? Math.round(dy) : 0;
        if (deltaX === 0 && deltaY === 0) return false;
        observeContentGlobalPosition();
        finalX = Math.round(finalX + deltaX);
        finalY = Math.round(finalY + deltaY);
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        clampTitlebarYToVisibleRect(activeVisibleRectSafe());
        applySettledGeometryAtomically("", false);
        return true;
    }

    function requestAdjacentScreenMove(direction, sourceTag, sourceSnapshot) {
        if (classicMoveModeActive) {
            stopClassicMoveMode(true, "adjacent-screen-move")
        }
        classicMoveMenuArmed = false;
        if (classicMoveArmTimer.running) {
            classicMoveArmTimer.stop();
        }
        var dir = (direction < 0) ? -1 : 1;
        var source = sourceTag ? sourceTag : "adjacent-screen-move";
        phaseLog("MOVE", "Shortcut " + source);
        return moveWindowToAdjacentScreen(dir, sourceSnapshot);
    }

    onOsWinShiftMoveSeqChanged: {
        var dir = (osWinShiftMoveDirection < 0) ? -1 : ((osWinShiftMoveDirection > 0) ? 1 : 0);
        if (dir === 0) {
            return;
        }
        var sourceSnapshot = {
            "finalX": osWinShiftSourceFinalX,
            "finalY": osWinShiftSourceFinalY,
            "finalW": osWinShiftSourceFinalW,
            "finalH": osWinShiftSourceFinalH,
            "rectX": osWinShiftSourceRectX,
            "rectY": osWinShiftSourceRectY,
            "rectW": osWinShiftSourceRectW,
            "rectH": osWinShiftSourceRectH
        };
        requestAdjacentScreenMove(dir, "Win+Shift native override", sourceSnapshot);
    }

    function clampNumber(value, minValue, maxValue) {
        var v = value;
        if (v < minValue) v = minValue;
        if (v > maxValue) v = maxValue;
        return v;
    }

    function ratioToPixels(ratio, refW, refH, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1;
        var safeW = Math.max(1, refW);
        var safeH = Math.max(1, refH);
        if (mainWin.userResizeInProgress) {
            var startW = Math.max(1, Math.round(mainWin.resizeStartFinalW));
            var startH = Math.max(1, Math.round(mainWin.resizeStartFinalH));
            var liveFinalW = Math.max(1, Math.round(mainWin.finalW));
            var liveFinalH = Math.max(1, Math.round(mainWin.finalH));
            var liveHostW = Math.max(1, Math.round(mainWin.width));
            var liveHostH = Math.max(1, Math.round(mainWin.height));
            var matchesFinalRef = Math.abs(safeW - liveFinalW) <= 1
                && Math.abs(safeH - liveFinalH) <= 1;
            var matchesHostRef = Math.abs(safeW - liveHostW) <= 1
                && Math.abs(safeH - liveHostH) <= 1;
            if (matchesFinalRef || matchesHostRef) {
                safeW = startW;
                safeH = startH;
            }
        }
        var unit = Math.min(safeW, safeH);
        var px = Math.round(unit * ratio);
        return Math.max(floorPx, px);
    }

    function remapWindowGeometryAcrossVisibleRects(srcRect, srcVisibleRect, destVisibleRect, minW, minH) {
        if (!srcRect || !srcVisibleRect || !destVisibleRect) return null;
        if (srcVisibleRect.w <= 0 || srcVisibleRect.h <= 0 || destVisibleRect.w <= 0 || destVisibleRect.h <= 0) return null;

        var safeMinW = Math.max(1, Math.round(minW));
        var safeMinH = Math.max(1, Math.round(minH));
        var srcW = Math.max(1, Math.round(srcRect.w));
        var srcH = Math.max(1, Math.round(srcRect.h));
        var srcAspect = clampNumber(srcW / srcH, 0.35, 3.50);

        var srcArea = Math.max(1.0, srcW * srcH);
        var srcVisibleArea = Math.max(1.0, srcVisibleRect.w * srcVisibleRect.h);
        var relArea = clampNumber(srcArea / srcVisibleArea, 0.02, 1.0);

        var srcCenterX = srcRect.x + (srcW / 2.0);
        var srcCenterY = srcRect.y + (srcH / 2.0);
        var relCenterX = clampNumber((srcCenterX - srcVisibleRect.x) / Math.max(1, srcVisibleRect.w), 0.0, 1.0);
        var relCenterY = clampNumber((srcCenterY - srcVisibleRect.y) / Math.max(1, srcVisibleRect.h), 0.0, 1.0);

        var destArea = Math.max(1.0, destVisibleRect.w * destVisibleRect.h);
        var targetArea = Math.max(1.0, destArea * relArea);
        var nextW = Math.max(1, Math.round(Math.sqrt(targetArea * srcAspect)));
        var nextH = Math.max(1, Math.round(nextW / srcAspect));

        if (nextW > destVisibleRect.w) {
            nextW = Math.max(1, Math.round(destVisibleRect.w));
            nextH = Math.max(1, Math.round(nextW / srcAspect));
        }
        if (nextH > destVisibleRect.h) {
            nextH = Math.max(1, Math.round(destVisibleRect.h));
            nextW = Math.max(1, Math.round(nextH * srcAspect));
        }

        if (nextW < safeMinW) {
            nextW = Math.min(destVisibleRect.w, safeMinW);
            nextH = Math.max(1, Math.round(nextW / srcAspect));
        }
        if (nextH < safeMinH) {
            nextH = Math.min(destVisibleRect.h, safeMinH);
            nextW = Math.max(1, Math.round(nextH * srcAspect));
        }

        if (nextW > destVisibleRect.w) {
            nextW = Math.max(1, Math.round(destVisibleRect.w));
            nextH = Math.max(1, Math.round(nextW / srcAspect));
        }
        if (nextH > destVisibleRect.h) {
            nextH = Math.max(1, Math.round(destVisibleRect.h));
            nextW = Math.max(1, Math.round(nextH * srcAspect));
        }

        var destCenterX = destVisibleRect.x + (destVisibleRect.w * relCenterX);
        var destCenterY = destVisibleRect.y + (destVisibleRect.h * relCenterY);
        var nextX = Math.round(destCenterX - (nextW / 2.0));
        var nextY = Math.round(destCenterY - (nextH / 2.0));
        nextX = Math.round(clampNumber(nextX, destVisibleRect.x, destVisibleRect.x + destVisibleRect.w - nextW));
        nextY = Math.round(clampNumber(nextY, destVisibleRect.y, destVisibleRect.y + destVisibleRect.h - nextH));

        return {
            "x": nextX,
            "y": nextY,
            "w": Math.max(1, Math.round(nextW)),
            "h": Math.max(1, Math.round(nextH)),
            "relArea": relArea,
            "relCenterX": relCenterX,
            "relCenterY": relCenterY,
            "aspect": srcAspect
        };
    }

    function metricFloorPx(ratio, minPx) {
        var safeMin = (typeof minPx === "number") ? minPx : 1;
        var scaleFactor = Math.max(1, monitorScalePercent) / 100.0;
        var scaledMin = Math.max(1, Math.round(safeMin * scaleFactor));
        var contentFloor = ratioToPixels(ratio, Math.max(1, finalW), Math.max(1, finalH), 1);
        return Math.max(scaledMin, contentFloor);
    }

    function settledWindowBehaviorDuration() {
        if (maximizeAnimInProgress) {
            return mainWin.lowPerformanceMode ? 220 : 300;
        }
        return mainWin.lowPerformanceMode ? 150 : 200;
    }

    function resetMaximizeFxState() {
        maximizeFxScaleX = 1.0;
        maximizeFxScaleY = 1.0;
        maximizeFxTransX = 0.0;
        maximizeFxTransY = 0.0;
        maximizeFxRotate = 0.0;
    }

    function stopMaximizeFxAnimations() {
        if (maximizeFxAnimation.running) {
            maximizeFxAnimation.stop();
        }
        if (maximizeRestoreFxAnimation.running) {
            maximizeRestoreFxAnimation.stop();
        }
        maximizeAnimInProgress = false;
        resetMaximizeFxState();
    }

    function resetDragFxState() {
        dragFxScaleX = 1.0;
        dragFxScaleY = 1.0;
        dragFxTransX = 0.0;
        dragFxTransY = 0.0;
        dragFxRotate = 0.0;
        dragFxCornerBoost = 0.0;
        dragFxVelX = 0.0;
        dragFxVelY = 0.0;
        dragReleaseVelocityNorm = 0.0;
    }

    function dragFxVisible() {
        if (!dragVisualFxEnabled) return false;
        return userMoveInProgress
            || (dragFxReleaseAnimation && dragFxReleaseAnimation.running)
            || Math.abs(dragFxScaleX - 1.0) > 0.001
            || Math.abs(dragFxScaleY - 1.0) > 0.001
            || Math.abs(dragFxTransX) > 0.01
            || Math.abs(dragFxTransY) > 0.01
            || Math.abs(dragFxRotate) > 0.01
            || Math.abs(dragFxCornerBoost) > 0.01;
    }

    function beginDragFxTracking() {
        if (!dragVisualFxEnabled) {
            resetDragFxState();
            return;
        }
        if (dragFxReleaseAnimation && dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        resetDragFxState();
        dragFxStartScreenIndex = -1;
        dragFxCrossMonitorLockout = false;
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.34);
        }
    }

    function applyDragFxFromDelta(dx, dy) {
        if (!dragVisualFxEnabled) return;
        if (!userMoveInProgress || animationPhase !== "settled" || isClosing || maximizeAnimInProgress) return;
        if (!isFinite(dx) || !isFinite(dy)) return;
        if (dx === 0 && dy === 0) return;

        // Ignore sub-pixel jitter from mixed DPI drag sampling.
        if (Math.abs(dx) < 0.45 && Math.abs(dy) < 0.45) return;

        var speed = Math.sqrt((dx * dx) + (dy * dy));
        if (!isFinite(speed) || speed <= 0.0001) return;

        // Smooth velocity to prevent noisy oscillation at monitor boundaries.
        dragFxVelX = (dragFxVelX * 0.70) + (dx * 0.30);
        dragFxVelY = (dragFxVelY * 0.70) + (dy * 0.30);
        var vdx = dragFxVelX;
        var vdy = dragFxVelY;
        var vSpeed = Math.sqrt((vdx * vdx) + (vdy * vdy));
        if (!isFinite(vSpeed) || vSpeed <= 0.0001) return;

        var refUnit = Math.max(1, Math.min(Math.max(1, usableW), Math.max(1, usableH)));
        var speedRef = clampNumber(Math.round(refUnit * 0.040), 18, 64);
        var speedNorm = clampNumber(vSpeed / speedRef, 0.0, 1.0);
        dragReleaseVelocityNorm = clampNumber((dragReleaseVelocityNorm * 0.65) + (speedNorm * 0.35), 0.0, 1.0);

        var invSpeed = 1.0 / vSpeed;
        var dirX = vdx * invSpeed;
        var dirY = vdy * invSpeed;
        var absDirX = Math.abs(dirX);
        var absDirY = Math.abs(dirY);

        var stretch = 0.020 + (0.110 * speedNorm);
        var targetScaleX = 1.0 + (stretch * (absDirX - absDirY));
        var targetScaleY = 1.0 + (stretch * (absDirY - absDirX));
        targetScaleX = clampNumber(targetScaleX, 0.88, 1.15);
        targetScaleY = clampNumber(targetScaleY, 0.88, 1.15);

        // Keep translation neutral to avoid cross-monitor frame drift and clipping artifacts.
        var targetTransX = 0.0;
        var targetTransY = 0.0;
        var targetRotate = clampNumber((vdx * 0.120) + (vdy * 0.028), -6.2, 6.2);

        // Pseudo soft-body corners: increase curvature with drag energy.
        var baseCorner = chromeCornerRadiusPx();
        var targetCornerBoost = clampNumber(baseCorner * (0.04 + (0.30 * speedNorm)), 0, baseCorner * 0.38);

        var response = lowPerformanceMode ? 0.28 : 0.36;
        dragFxScaleX = dragFxScaleX + ((targetScaleX - dragFxScaleX) * response);
        dragFxScaleY = dragFxScaleY + ((targetScaleY - dragFxScaleY) * response);
        dragFxTransX = dragFxTransX + ((targetTransX - dragFxTransX) * response);
        dragFxTransY = dragFxTransY + ((targetTransY - dragFxTransY) * response);
        dragFxRotate = dragFxRotate + ((targetRotate - dragFxRotate) * response);
        dragFxCornerBoost = dragFxCornerBoost + ((targetCornerBoost - dragFxCornerBoost) * response);
    }

    function currentDragVelocityNorm() {
        var vSpeed = Math.sqrt((dragFxVelX * dragFxVelX) + (dragFxVelY * dragFxVelY));
        if (!isFinite(vSpeed) || vSpeed <= 0.0001) {
            return clampNumber(dragReleaseVelocityNorm, 0.0, 1.0);
        }
        var refUnit = Math.max(1, Math.min(Math.max(1, usableW), Math.max(1, usableH)));
        var speedRef = clampNumber(Math.round(refUnit * 0.040), 18, 64);
        return clampNumber(vSpeed / speedRef, 0.0, 1.0);
    }

    function releaseDragFxToSettled() {
        if (!dragVisualFxEnabled) {
            resetDragFxState();
            return;
        }
        if (dragFxReleaseAnimation && dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        dragFxStartScreenIndex = -1;
        dragFxCrossMonitorLockout = false;
        if (animationPhase !== "settled" || isClosing || maximizeAnimInProgress) {
            resetDragFxState();
            return;
        }
        var releaseNorm = currentDragVelocityNorm();
        if (sfxBus && sfxBus.playBounceFromVelocity && releaseNorm > 0.04) {
            sfxBus.playBounceFromVelocity(releaseNorm);
        }
        dragReleaseVelocityNorm = 0.0;
        dragFxReleaseAnimation.restart();
    }

    function settledScaleX() {
        if (maximizeAnimInProgress) return maximizeFxScaleX;
        if (dragFxVisible()) return dragFxScaleX;
        return 1.0;
    }

    function settledScaleY() {
        if (maximizeAnimInProgress) return maximizeFxScaleY;
        if (dragFxVisible()) return dragFxScaleY;
        return 1.0;
    }

    function settledTransX() {
        if (maximizeAnimInProgress) return maximizeFxTransX;
        if (dragFxVisible()) return dragFxTransX;
        return 0.0;
    }

    function settledTransY() {
        if (maximizeAnimInProgress) return maximizeFxTransY;
        if (dragFxVisible()) return dragFxTransY;
        return 0.0;
    }

    function settledRotate() {
        if (maximizeAnimInProgress) return maximizeFxRotate;
        if (dragFxVisible()) return dragFxRotate;
        return 0.0;
    }

    function settledScaleOriginX() {
        if (maximizeAnimInProgress) return contentLocalX + finalW;
        return animationCanvasLayer.width / 2;
    }

    function settledScaleOriginY() {
        if (maximizeAnimInProgress) return contentLocalY;
        return animationCanvasLayer.height / 2;
    }

    function screenAvailableRect(screenObj) {
        if (!screenObj) return null;
        if (screenObj.availableGeometry
            && typeof screenObj.availableGeometry.x === "number"
            && typeof screenObj.availableGeometry.y === "number"
            && typeof screenObj.availableGeometry.width === "number"
            && typeof screenObj.availableGeometry.height === "number"
            && isFinite(screenObj.availableGeometry.x)
            && isFinite(screenObj.availableGeometry.y)
            && isFinite(screenObj.availableGeometry.width)
            && isFinite(screenObj.availableGeometry.height)
            && screenObj.availableGeometry.width > 0
            && screenObj.availableGeometry.height > 0) {
            return {
                "x": Math.round(screenObj.availableGeometry.x),
                "y": Math.round(screenObj.availableGeometry.y),
                "w": Math.max(1, Math.round(screenObj.availableGeometry.width)),
                "h": Math.max(1, Math.round(screenObj.availableGeometry.height))
            };
        }
        return null;
    }

    function visibleRectForScreen(screenObj, infoObj) {
        if (!screenObj) {
            return { "x": 0, "y": 0, "w": 1, "h": 1 };
        }

        var availableRect = screenAvailableRect(screenObj);
        if (availableRect) {
            return availableRect;
        }

        var baseX = screenObj.virtualX;
        var baseY = screenObj.virtualY;
        var baseW = Math.max(1, screenObj.width);
        var baseH = Math.max(1, screenObj.height);
        var rectX = baseX;
        var rectY = baseY;
        var rectW = baseW;
        var rectH = baseH;

        if (infoObj
            && typeof infoObj.x === "number"
            && typeof infoObj.y === "number"
            && typeof infoObj.w === "number"
            && typeof infoObj.h === "number"
            && typeof infoObj.availX === "number"
            && typeof infoObj.availY === "number"
            && typeof infoObj.availW === "number"
            && typeof infoObj.availH === "number"
            && isFinite(infoObj.x)
            && isFinite(infoObj.y)
            && isFinite(infoObj.w)
            && isFinite(infoObj.h)
            && isFinite(infoObj.availX)
            && isFinite(infoObj.availY)
            && isFinite(infoObj.availW)
            && isFinite(infoObj.availH)
            && infoObj.w > 0
            && infoObj.h > 0) {
            // Map Python-provided taskbar insets into QML screen space. This avoids
            // mixed-DPI coordinate space mismatches when absolute geometry units differ.
            var leftInset = Math.max(0, infoObj.availX - infoObj.x);
            var topInset = Math.max(0, infoObj.availY - infoObj.y);
            var rightInset = Math.max(0, (infoObj.x + infoObj.w) - (infoObj.availX + infoObj.availW));
            var bottomInset = Math.max(0, (infoObj.y + infoObj.h) - (infoObj.availY + infoObj.availH));

            var scaleX = baseW / infoObj.w;
            var scaleY = baseH / infoObj.h;
            if (!isFinite(scaleX) || scaleX <= 0) scaleX = 1;
            if (!isFinite(scaleY) || scaleY <= 0) scaleY = 1;

            var leftAdj = Math.max(0, Math.round(leftInset * scaleX));
            var topAdj = Math.max(0, Math.round(topInset * scaleY));
            var rightAdj = Math.max(0, Math.round(rightInset * scaleX));
            var bottomAdj = Math.max(0, Math.round(bottomInset * scaleY));

            rectX = Math.round(baseX + leftAdj);
            rectY = Math.round(baseY + topAdj);
            rectW = Math.max(1, Math.round(baseW - leftAdj - rightAdj));
            rectH = Math.max(1, Math.round(baseH - topAdj - bottomAdj));
        }

        return {
            "x": Math.round(rectX),
            "y": Math.round(rectY),
            "w": Math.max(1, Math.round(rectW)),
            "h": Math.max(1, Math.round(rectH))
        };
    }

    function fullRectForScreen(screenObj, infoObj) {
        if (!screenObj) {
            return { "x": 0, "y": 0, "w": 1, "h": 1 };
        }

        var rectX = 0;
        var rectY = 0;
        var rectW = 1;
        var rectH = 1;

        if (typeof screenObj.virtualX === "number" && isFinite(screenObj.virtualX)) {
            rectX = screenObj.virtualX;
        } else if (infoObj && typeof infoObj.x === "number" && isFinite(infoObj.x)) {
            rectX = infoObj.x;
        }

        if (typeof screenObj.virtualY === "number" && isFinite(screenObj.virtualY)) {
            rectY = screenObj.virtualY;
        } else if (infoObj && typeof infoObj.y === "number" && isFinite(infoObj.y)) {
            rectY = infoObj.y;
        }

        if (typeof screenObj.width === "number" && isFinite(screenObj.width) && screenObj.width > 0) {
            rectW = screenObj.width;
        } else if (infoObj && typeof infoObj.w === "number" && isFinite(infoObj.w) && infoObj.w > 0) {
            rectW = infoObj.w;
        }

        if (typeof screenObj.height === "number" && isFinite(screenObj.height) && screenObj.height > 0) {
            rectH = screenObj.height;
        } else if (infoObj && typeof infoObj.h === "number" && isFinite(infoObj.h) && infoObj.h > 0) {
            rectH = infoObj.h;
        }

        return {
            "x": Math.round(rectX),
            "y": Math.round(rectY),
            "w": Math.max(1, Math.round(rectW)),
            "h": Math.max(1, Math.round(rectH))
        };
    }

    function openingPaddingPx() {
        var ratio = mainWin.lowPerformanceMode
            ? layoutRatios.openPaddingLowPerfPct
            : layoutRatios.openPaddingPct;
        return ratioToPixels(ratio, Math.max(1, usableW), Math.max(1, usableH), 0);
    }

    function resizeVisualWidthPx() {
        if (mainWin.userResizeInProgress) {
            return Math.max(1, Math.round(mainWin.resizeStartFinalW));
        }
        return Math.max(1, finalW);
    }

    function resizeVisualHeightPx() {
        if (mainWin.userResizeInProgress) {
            return Math.max(1, Math.round(mainWin.resizeStartFinalH));
        }
        return Math.max(1, finalH);
    }

    function settledPaddingPx(contentW, contentH) {
        if (useExactSettledCanvasPadding) {
            var targetScale = (typeof layoutRatios.settledCanvasAreaScale === "number")
                ? layoutRatios.settledCanvasAreaScale : 1.05;
            if (targetScale > 1.0) {
                var safeW = Math.max(1, (typeof contentW === "number") ? contentW : finalW);
                var safeH = Math.max(1, (typeof contentH === "number") ? contentH : finalH);
                // Solve (w + 2p)(h + 2p) = scale * (w * h) for p.
                var a = safeW + safeH;
                var disc = (a * a) + (4 * safeW * safeH * (targetScale - 1.0));
                if (isFinite(disc) && disc >= 0) {
                    var solvedPad = (Math.sqrt(disc) - a) / 4.0;
                    if (isFinite(solvedPad) && solvedPad >= 0) {
                        return Math.max(0, Math.round(solvedPad));
                    }
                }
            }
        }

        var ratio = mainWin.lowPerformanceMode
            ? layoutRatios.settledPaddingLowPerfPct
            : layoutRatios.settledPaddingPct;
        return ratioToPixels(ratio, Math.max(1, usableW), Math.max(1, usableH), 0);
    }

    function launchSizeBoostForScalePercent(scalePercent) {
        if (!mainWin.useDpiLaunchBoost) return 1.0;
        var sp = Math.max(100, Math.round(scalePercent));
        if (sp <= 125) return 1.0;
        // Smoothly increase launch coverage for very high DPI displays where
        // logical desktop size is much smaller than native resolution.
        var t = clampNumber((sp - 125) / 125.0, 0.0, 1.0);
        return 1.0 + (0.42 * t); // max +42% at 250%
    }

    function closePadPx(refW, refH) {
        return ratioToPixels(layoutRatios.closePadPct, refW, refH, 1);
    }

    function closingOverlayMotionRect(contentGX, contentGY, contentW, contentH, targetGX, targetGY) {
        var cw = Math.max(1, Math.round(contentW));
        var ch = Math.max(1, Math.round(contentH));
        var cx = Math.round(contentGX);
        var cy = Math.round(contentGY);
        var tx = Math.round(targetGX);
        var ty = Math.round(targetGY);

        // Keep close overlays local to the actual motion path to avoid mixed-DPI remap jumps.
        var baseW = (usableW > 0) ? usableW : cw;
        var baseH = (usableH > 0) ? usableH : ch;
        var pathSpan = Math.max(cw, ch, Math.abs(tx - cx), Math.abs(ty - cy));
        var pad = Math.max(closePadPx(Math.max(1, baseW), Math.max(1, baseH)), Math.round(pathSpan * 0.20), 96);

        var minX = Math.min(cx, tx) - pad;
        var minY = Math.min(cy, ty) - pad;
        var maxX = Math.max(cx + cw, tx) + pad;
        var maxY = Math.max(cy + ch, ty) + pad;

        return {
            "x": Math.round(minX),
            "y": Math.round(minY),
            "w": Math.max(1, Math.round(maxX - minX)),
            "h": Math.max(1, Math.round(maxY - minY))
        };
    }

    function clearClosingOverlayGeometry() {
        closingOverlayGeometry = null;
    }

    function captureClosingOverlayGeometry() {
        // Read the native window geometry at click time, not the previous
        // modelled host envelope.  Windows can commit an OS monitor move one
        // event after QML's hostX/hostY model was updated.
        var actualHostX = Math.round(mainWin.x);
        var actualHostY = Math.round(mainWin.y);
        var localContentX = Math.round(canvasLocalX + contentLocalX);
        var localContentY = Math.round(canvasLocalY + contentLocalY);
        var actualContentX = Math.round(actualHostX + localContentX);
        var actualContentY = Math.round(actualHostY + localContentY);

        if (!isFinite(actualContentX) || !isFinite(actualContentY)) {
            actualContentX = Math.round(finalX);
            actualContentY = Math.round(finalY);
        }

        var previousX = Math.round(finalX);
        var previousY = Math.round(finalY);
        finalX = actualContentX;
        finalY = actualContentY;

        var centerX = finalX + (finalW / 2.0);
        var centerY = finalY + (finalH / 2.0);
        var sourceScreen = screenForPoint(centerX, centerY,
            mainWin.screen ? mainWin.screen : targetScreen);
        if (sourceScreen) {
            // Preserve the actual source monitor without pinning/moving the
            // host window during the close handoff.
            adoptTargetScreen(sourceScreen, true);
        } else {
            updateTargetScreenFromFinalCenter();
            sourceScreen = targetScreen;
        }
        refreshActiveVisibleRect();

        var target = closeTargetGlobalPoint();
        var rect = closingOverlayMotionRect(finalX, finalY, finalW, finalH, target.x, target.y);
        closingOverlayGeometry = {
            "sourceScreen": sourceScreen,
            "contentX": Math.round(finalX),
            "contentY": Math.round(finalY),
            "contentW": Math.max(1, Math.round(finalW)),
            "contentH": Math.max(1, Math.round(finalH)),
            "targetX": Math.round(target.x),
            "targetY": Math.round(target.y),
            "rect": {
                "x": Math.round(rect.x),
                "y": Math.round(rect.y),
                "w": Math.max(1, Math.round(rect.w)),
                "h": Math.max(1, Math.round(rect.h))
            }
        };
        phaseLog("CLOSING", "Frozen close monitor=" + describeScreen(sourceScreen)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " previous=" + previousX + "," + previousY
            + " target=" + Math.round(target.x) + "," + Math.round(target.y));
        return true;
    }

    function closingCanvasRect() {
        if (closingOverlayGeometry && closingOverlayGeometry.rect) {
            return closingOverlayGeometry.rect;
        }
        var target = closeTargetGlobalPoint();
        return closingOverlayMotionRect(finalX, finalY, finalW, finalH, target.x, target.y);
    }

    function applyHostEnvelopeForClosing() {
        var rect = closingCanvasRect();
        var hostPad = closePadPx(rect.w, rect.h);
        hostX = Math.round(rect.x - hostPad);
        hostY = Math.round(rect.y - hostPad);
        hostW = Math.max(1, Math.round(rect.w + (hostPad * 2)));
        hostH = Math.max(1, Math.round(rect.h + (hostPad * 2)));
    }

    function destroyClosingOverlay() {
        if (!closingOverlayRef) return;
        try {
            closingOverlayRef.closeOverlay("replace");
        } catch (e) {
            try {
                closingOverlayRef.destroy();
            } catch (e2) {
            }
        }
        closingOverlayRef = null;
    }

    function startupSplashLogoSourceUrl() {
        try {
            if (startupSplashLogoUrl && startupSplashLogoUrl.length > 0) {
                return String(startupSplashLogoUrl);
            }
        } catch (e) {
        }
        return "";
    }

    function startupSplashAudioSourceUrl() {
        try {
            if (startupSplashAudioUrl && startupSplashAudioUrl.length > 0) {
                return String(startupSplashAudioUrl);
            }
        } catch (e) {
        }
        return "";
    }

    function removeStartupSplashRef(splashObj) {
        if (!startupSplashRefs || startupSplashRefs.length === 0) {
            if (startupSplashRef === splashObj) {
                startupSplashRef = null;
            }
            startupSplashPendingCount = 0;
            return 0;
        }

        var remaining = [];
        for (var i = 0; i < startupSplashRefs.length; i++) {
            var entry = startupSplashRefs[i];
            if (!entry || entry === splashObj) {
                continue;
            }
            remaining.push(entry);
        }
        startupSplashRefs = remaining;
        if (startupSplashRef === splashObj) {
            startupSplashRef = (remaining.length > 0) ? remaining[0] : null;
        }
        startupSplashPendingCount = remaining.length;
        return startupSplashPendingCount;
    }

    function destroyStartupSplash() {
        var refs = [];
        if (startupSplashRefs && startupSplashRefs.length > 0) {
            refs = startupSplashRefs.slice(0);
        }
        if (startupSplashRef && refs.indexOf(startupSplashRef) < 0) {
            refs.push(startupSplashRef);
        }

        startupSplashRefs = [];
        startupSplashRef = null;
        startupSplashPendingCount = 0;

        for (var i = 0; i < refs.length; i++) {
            var splashObj = refs[i];
            if (!splashObj) continue;
            try {
                splashObj.closeOverlay("replace");
            } catch (e) {
                try {
                    splashObj.destroy();
                } catch (e2) {
                }
            }
        }
    }

    function requestStartupSplashSkip(reason) {
        if (startupSplashSkipInvoked) return;
        startupSplashSkipInvoked = true;
        var reasonText = String(reason || "user-skip");
        lagLog("startup splash skip requested reason=" + reasonText);

        startupSplashEnabled = false;
        startupSplashSequenceEpochMs = 0;
        startupSplashPendingCount = 0;
        destroyStartupSplash();
        startupLaunchDelayTimer.stop();

        if (!startupLaunchStarted) {
            beginCoreLaunchSequence();
            return;
        }

        if (startupPhase !== "falling-window") {
            primeStartupLaunchScreen("splash-skip");
            setStartupPhase("splash-skipped", reasonText);
            startOpeningLaunchNow();
        }
    }

    function splashElapsedMs() {
        if (startupSplashSequenceEpochMs <= 0) return 0;
        return Math.max(0, Math.round(Date.now() - startupSplashSequenceEpochMs));
    }

    function lagLog(msg) {
        var line = "[SPLASH-LAG] [MAINWIN] " + msg + " t+" + splashElapsedMs() + "ms";
        console.warn(line);
        appendLiveLog(line);
    }

    Timer {
        id: forensicBootPulseTimer
        interval: forensicBootPulseMs
        repeat: true
        running: forensicBootEnabled
        onTriggered: {
            lagLog("[FORENSIC-PULSE] phase=" + startupPhase
                + " settled=" + isSettled
                + " opening=" + (!isSettled && !isClosing)
                + " heavyAllowed=" + startupHeavyWorkAllowed
                + " heavyDelayMs=" + startupHeavyWorkDelayMs()
                + " deferredQueueEnabled=" + startupDeferredQueueEnabled
                + " deferredQueueSize=" + (startupDeferredTaskQueue ? startupDeferredTaskQueue.length : 0)
                + " startupDataBootStarted=" + startupDataBootStarted
                + " startupDataBootComplete=" + startupDataBootComplete
                + " startupLaunchStarted=" + startupLaunchStarted
                + " startupFirstPixelLogged=" + startupFirstPixelLogged
                + " visible=" + visible
                + " animationPhase=" + animationPhase
                + " startupSplashPendingCount=" + startupSplashPendingCount)
        }
    }

    function perfLog(message) {
        lagLog("[PERF] " + String(message || ""));
    }

    function perfStart(key, detail) {
        _perfMarks = PerfTrace.markStart(_perfMarks, key);
        perfLog("start key=" + String(key || "") + " " + String(detail || ""));
    }

    function perfEnd(key, detail) {
        var result = PerfTrace.markFinish(_perfMarks, key);
        _perfMarks = result.marks;
        if (result.elapsedMs < 0) return;
        perfLog("end key=" + String(key || "")
            + " elapsedMs=" + String(result.elapsedMs)
            + " " + String(detail || ""));
    }

    function setStartupPhase(nextPhase, reason) {
        lagLog("[FORENSIC] setStartupPhase request next=" + String(nextPhase || "") + " reason=" + String(reason || ""))
        var phaseText = String(nextPhase || "").trim();
        if (phaseText.length <= 0) phaseText = "unknown";
        if (startupPhase === phaseText) return;
        startupPhase = phaseText;
        var reasonText = (reason === undefined || reason === null) ? "" : String(reason);
        console.warn("[STARTUP-PHASE] [MAINWIN] phase=" + startupPhase
            + " reason=" + reasonText
            + " heavyAllowed=" + startupHeavyWorkAllowed
            + " settled=" + isSettled
            + " t+" + splashElapsedMs() + "ms");
    }

    function startupHeavyWorkDelayMs() {
        if (startupHeavyWorkAllowed) return 0;
        if (!isSettled || startupSettledEpochMs <= 0) {
            return Math.max(80, startupHeavyWorkGraceMs);
        }
        var elapsed = Math.max(0, Math.round(Date.now() - startupSettledEpochMs));
        return Math.max(24, startupHeavyWorkGraceMs - elapsed);
    }

    function startupAllowsHeavyWork(reason) {
        if (startupHeavyWorkAllowed) return true;
        var reasonText = (reason === undefined || reason === null) ? "unspecified" : String(reason);
        if (isSettled && startupSettledEpochMs > 0
            && (Date.now() - startupSettledEpochMs) >= startupHeavyWorkGraceMs) {
            startupHeavyWorkAllowed = true;
            startupHeavyWorkBlockedCount = 0;
            startupPostSettleReadyEpochMs = Date.now();
            setStartupPhase("post-settle-ready", "guard-auto-release:" + reasonText);
            lagLog("startup heavy-work guard auto-released reason=" + reasonText);
            requestDeferredSettingsLoadIfNeeded("guard-auto-release:" + reasonText);
            requestStartupDeferredQueuePump("guard-auto-release:" + reasonText);
            return true;
        }
        startupHeavyWorkBlockedCount += 1;
        if (startupHeavyWorkBlockedCount <= 12 || (startupHeavyWorkBlockedCount % 25) === 0) {
            lagLog("startup heavy-work guard blocked reason=" + reasonText
                + " phase=" + startupPhase
                + " settled=" + isSettled
                + " waitMs=" + startupHeavyWorkDelayMs());
        }
        return false;
    }

    function requestDeferredSettingsLoadIfNeeded(reason) {
        if (!mainWin.appRef || typeof mainWin.appRef.requestDeferredSettingsLoad !== "function") {
            return;
        }
        try {
            mainWin.appRef.requestDeferredSettingsLoad(reason);
        } catch (e) {
            lagLog("requestDeferredSettingsLoadIfNeeded failed reason="
                + String(reason)
                + " error=" + e);
        }
    }

    function startupDeferredQueuePauseReason() {
        var pauseState = StartupQueueBridge.evaluatePauseState({
            "startupDeferredQueueEnabled": startupDeferredQueueEnabled,
            "isSettled": isSettled,
            "animationPhase": animationPhase,
            "startupHeavyWorkAllowed": startupHeavyWorkAllowed,
            "startupQueueWaitForFirstInput": startupQueueWaitForFirstInput,
            "detachedMode": mainWin.detachedMode,
            "startupFirstInputSeen": startupFirstInputSeen,
            "startupQueueInputTimeoutReleased": startupQueueInputTimeoutReleased,
            "startupPostSettleReadyEpochMs": startupPostSettleReadyEpochMs,
            "startupQueueInputFallbackMs": startupQueueInputFallbackMs,
            "isClosing": isClosing,
            "isMinimizing": isMinimizing,
            "isRestoringFromMinimize": isRestoringFromMinimize,
            "maximizeAnimInProgress": maximizeAnimInProgress,
            "canvasTransitionRunning": !!(canvasTransition && canvasTransition.running),
            "userMoveInProgress": userMoveInProgress,
            "userResizeInProgress": userResizeInProgress,
            "systemMoveInProgress": systemMoveInProgress,
            "adjacentMoveInProgress": adjacentMoveInProgress,
            "dragFinalizePending": dragFinalizePending,
            "dragStrategy": dragStrategy,
            "dragFxReleaseAnimationRunning": !!(dragFxReleaseAnimation && dragFxReleaseAnimation.running),
            "portalTransitionActive": !!(mainContent && mainContent.portalTransitionActive),
            "nowEpochMs": Date.now()
        });
        var hadTimeoutRelease = startupQueueInputTimeoutReleased;
        startupPostSettleReadyEpochMs = pauseState.startupPostSettleReadyEpochMs;
        startupQueueInputTimeoutReleased = pauseState.startupQueueInputTimeoutReleased === true;
        if (!hadTimeoutRelease && startupQueueInputTimeoutReleased) {
            lagLog("startup queue first-input gate released by timeout elapsedMs="
                + pauseState.inputGateElapsedMs
                + " fallbackMs=" + startupQueueInputFallbackMs);
        }
        return String(pauseState.reason || "");
    }

    function clearStartupDeferredQueue(reason) {
        startupDeferredQueueTimer.stop();
        var count = startupDeferredTaskQueue ? startupDeferredTaskQueue.length : 0;
        if (count > 0) {
            lagLog("startup queue cleared reason=" + String(reason || "unspecified")
                + " count=" + count);
        }
        startupDeferredTaskQueue = [];
        startupDeferredTaskPauseLogCount = 0;
    }

    function requestStartupDeferredQueuePump(reason) {
        if (!startupDeferredQueueEnabled) return;
        var queueCount = startupDeferredTaskQueue ? startupDeferredTaskQueue.length : 0;
        if (queueCount <= 0) return;
        if (startupDeferredQueueTimer.running) return;
        startupDeferredQueueTimer.interval = Math.max(24, startupDeferredQueueTickMs);
        startupDeferredQueueTimer.start();
    }

    function enqueuePostSettleTask(taskKey, targetObj, methodName, payload, retryable) {
        if (!startupDeferredQueueEnabled) return false;
        var keyText = String(taskKey || "").trim();
        var methodText = String(methodName || "").trim();
        if (keyText.length <= 0 || methodText.length <= 0 || !targetObj) return false;

        var queue = startupDeferredTaskQueue ? startupDeferredTaskQueue.slice(0) : [];
        for (var i = 0; i < queue.length; i++) {
            var existing = queue[i];
            if (!existing) continue;
            if (String(existing.key || "") === keyText) {
                return false;
            }
        }

        startupDeferredTaskSeq += 1;
        queue.push({
            "key": keyText,
            "target": targetObj,
            "methodName": methodText,
            "payload": payload,
            "retryable": (retryable !== false),
            "attempts": 0,
            "seq": startupDeferredTaskSeq
        });
        startupDeferredTaskQueue = queue;
        lagLog("startup queue enqueue key=" + keyText + " size=" + queue.length);
        requestStartupDeferredQueuePump("enqueue:" + keyText);
        return true;
    }

    function processStartupDeferredQueueTick() {
        if (!startupDeferredQueueEnabled) {
            clearStartupDeferredQueue("queue-disabled");
            return;
        }

        var queue = startupDeferredTaskQueue ? startupDeferredTaskQueue.slice(0) : [];
        if (queue.length <= 0) return;

        var pauseReason = startupDeferredQueuePauseReason();
        if (pauseReason.length > 0) {
            startupDeferredTaskPauseLogCount += 1;
            if (startupDeferredTaskPauseLogCount <= 12 || (startupDeferredTaskPauseLogCount % 25) === 0) {
                lagLog("startup queue paused reason=" + pauseReason
                    + " size=" + queue.length
                    + " phase=" + startupPhase);
            }
            startupDeferredQueueTimer.interval = Math.max(
                24,
                Math.max(startupDeferredQueueTickMs, startupHeavyWorkDelayMs())
            );
            startupDeferredQueueTimer.start();
            return;
        }

        startupDeferredTaskPauseLogCount = 0;
        var task = queue.shift();
        startupDeferredTaskQueue = queue;
        if (!task) {
            requestStartupDeferredQueuePump("null-task");
            return;
        }

        var shouldRetry = false;
        var taskKey = String(task.key || "unknown");
        try {
            if (task.target && task.methodName && typeof task.target[task.methodName] === "function") {
                var result = task.target[task.methodName](task.payload);
                if (result === false) {
                    shouldRetry = true;
                }
            }
        } catch (e) {
            shouldRetry = false;
            lagLog("startup queue task error key=" + taskKey + " error=" + e);
            reportUiSilentFailure("DetachedShellWindow.startupDeferredQueueTask", String(e));
        }

        if (shouldRetry && task.retryable === true) {
            task.attempts = Math.max(0, Number(task.attempts || 0)) + 1;
            if (task.attempts <= 500) {
                var retryQueue = startupDeferredTaskQueue ? startupDeferredTaskQueue.slice(0) : [];
                retryQueue.push(task);
                startupDeferredTaskQueue = retryQueue;
            }
        }

        if (startupDeferredTaskQueue && startupDeferredTaskQueue.length > 0) {
            startupDeferredQueueTimer.interval = Math.max(24, startupDeferredQueueTickMs);
            startupDeferredQueueTimer.start();
        }
    }

    function _windowAcceptsFocus(windowRef) {
        if (!windowRef) return false;
        try {
            var flags = windowRef.flags;
            if ((flags & Qt.WindowDoesNotAcceptFocus) === Qt.WindowDoesNotAcceptFocus) {
                return false;
            }
            // Tool/popup windows are frequently non-focusable on Windows even when the
            // explicit no-focus flag is not reflected yet; skip activation attempts.
            if ((flags & Qt.Tool) === Qt.Tool || (flags & Qt.Popup) === Qt.Popup || (flags & Qt.ToolTip) === Qt.ToolTip) {
                return false;
            }
            return true;
        } catch (e) {
            return false;
        }
        return false;
    }

    function _requestActivateIfFocusable(windowRef) {
        if (!windowRef) return false;
        if (!_windowAcceptsFocus(windowRef)) return false;
        try {
            if (windowRef.requestActivate) {
                windowRef.requestActivate();
                return true;
            }
        } catch (e) {
        }
        return false;
    }

    function forceLaunchFocusLight() {
        focusAnyWindow(mainWin);
        mainWin._requestActivateIfFocusable(mainWin);
    }

    function forceLaunchFocus() {
        forceLaunchFocusLight();
    }

    function markStartupFirstPixelVisible(sourceTag) {
        if (mainWin.detachedMode || mainWin.startupFirstPixelLogged) return;
        mainWin.startupFirstPixelLogged = true;
        mainWin.startupFirstPixelVisible();
        if (!mainWin.isSettled) {
            mainWin.setStartupPhase("first-pixel-visible", sourceTag);
        }
        var fpClock = Qt.formatDateTime(new Date(), "yyyy-MM-dd HH:mm:ss.zzz");
        var fpMsg = "[SPLASH-FIRST-PIXEL] Main window first pixel at " + fpClock
            + " (t+" + mainWin.splashElapsedMs() + "ms)"
            + " source=" + String(sourceTag || "unknown");
        console.warn(fpMsg);
        try {
            if (mainWin.appRef && mainWin.appRef.markStartupFirstPixelSeen) {
                mainWin.appRef.markStartupFirstPixelSeen();
            }
        } catch (eFp) {
        }
        mainWin.phaseLog("SPLASH", fpMsg);
    }

    function prepareStartupBriefingForReveal() {
        if (mainWin.detachedMode || mainWin.startupHiddenBriefingPrepared) return mainWin.startupHiddenBriefingPrepared
        if (!(mainWin.appRef && mainWin.appRef.startupBriefingSnapshotReady === true)) return false
        if (!mainContent || !mainContent.applyPreparedStartupBriefing) return false
        if (mainContent.applyPreparedStartupBriefing() !== true) return false
        if (!mainWin.prepareStartupCinematicGeometry()) return false

        // Let bindings consume the supplied payload before the backend's
        // ready-to-reveal state is emitted.  The window remains visible:false
        // throughout this acknowledgement.
        Qt.callLater(function() {
            if (mainWin.startupHiddenBriefingPrepared) return
            mainWin.startupHiddenBriefingPrepared = true
            mainWin.lagLog("hidden Practice Briefing prepared before first pixel")
            try {
                if (mainWin.appRef && mainWin.appRef.markStartupBriefingFrameReady) {
                    mainWin.appRef.markStartupBriefingFrameReady()
                }
            } catch (e0) {
                mainWin.lagLog("hidden Practice Briefing acknowledgement failed=" + e0)
                return
            }
            mainWin.hiddenStartupBriefingPrepared()
        })
        return true
    }

    function prepareStartupCinematicGeometry() {
        if (mainWin.detachedMode) return true
        if (mainWin.startupCinematicGeometryPrepared && mainWin.launchConfigured) return true

        var selected = mainWin.resolveTargetScreen()
        if (!selected) {
            lagLog("hidden cinematic geometry preparation failed: resolveTargetScreen")
            return false
        }
        if (!mainWin.applyGeometryToTargetScreen(false)) {
            lagLog("hidden cinematic geometry preparation failed: applyGeometryToTargetScreen")
            return false
        }
        mainWin.startupCinematicGeometryPrepared = true
        mainWin.lagLog("hidden final window geometry prepared during native splash")
        return true
    }

    function completeStartupCinematicBloom(reason) {
        if (startupCinematicBloomAnimation.running) {
            startupCinematicBloomAnimation.stop()
        }
        startupCinematicBloomScale = 1.0
        if (!startupCinematicBloomActive) return
        startupCinematicBloomActive = false
        startupCinematicBloomReleaseStarted = false
        startupCinematicSnapshotActive = false
        startupCinematicSnapshotUrl = ""
        phaseLog("SPLASH", "Act III bloom complete reason=" + String(reason || "finished"))
        if (sfxBus && sfxBus.playWindowSettle) {
            // SfxBus already owns the app's sound-effects enabled flag and
            // master-volume scaling, so a muted launch remains silent.
            sfxBus.playWindowSettle("launch", 0.42)
        }
    }

    function releaseStartupCinematicBloom() {
        if (!startupCinematicBloomActive) return false
        startupCinematicBloomPrestageOnly = false
        // Reassert the pinpoint in case a platform staging frame was committed
        // immediately before the native splash disappeared.
        startupCinematicBloomScale = 0.002
        startupCinematicBloomReleaseStarted = true
        phaseLog("SPLASH", "Act III main window bloom begins t+" + splashElapsedMs() + "ms")
        startupCinematicBloomAnimation.restart()
        return true
    }

    function startupCinematicBloomCanvasOriginX() {
        return (mainWin.activeVisibleRect.x + (mainWin.activeVisibleRect.w / 2.0))
            - mainWin.x - mainWin.canvasLocalX
    }

    function startupCinematicBloomCanvasOriginY() {
        return (mainWin.activeVisibleRect.y + (mainWin.activeVisibleRect.h / 2.0))
            - mainWin.y - mainWin.canvasLocalY
    }

    function _finishStartupCinematicPrestage(snapshotUrl, sequence) {
        if (sequence !== mainWin.startupCinematicSnapshotSequence) return
        if (!mainWin.startupCinematicBloomPrestageOnly) return

        startupCinematicSnapshotFallbackTimer.stop()
        mainWin.startupCinematicSnapshotUrl = snapshotUrl || ""
        mainWin.startupCinematicSnapshotActive = mainWin.startupCinematicSnapshotUrl.length > 0
        mainWin.startupCinematicBloomScale = 0.002
        mainWin.startupCinematicBloomActive = true
        // The live host has now been replaced by either its frozen canvas or
        // the in-place fallback. Make the native window compositable only once
        // it cannot expose a full-size frame above the native splash.
        mainWin.opacity = 1.0
        mainWin.lagLog("Act III prestage ready snapshot="
            + (mainWin.startupCinematicSnapshotActive ? "yes" : "fallback-live"))
        mainWin.startupCinematicBloomStaged()
    }

    function prestageStartupCinematicBloom() {
        var sequence = mainWin.startupCinematicSnapshotSequence + 1
        mainWin.startupCinematicSnapshotSequence = sequence
        if (!animationCanvasLayer || !animationCanvasLayer.grabToImage) {
            mainWin._finishStartupCinematicPrestage("", sequence)
            return false
        }
        var captureSize = Qt.size(Math.max(1, Math.round(mainWin.canvasW)),
            Math.max(1, Math.round(mainWin.canvasH)))
        var requested = false
        try {
            startupCinematicSnapshotFallbackTimer.sequence = sequence
            startupCinematicSnapshotFallbackTimer.restart()
            requested = animationCanvasLayer.grabToImage(function(result) {
                var snapshotUrl = (result && result.url) ? String(result.url) : ""
                mainWin._finishStartupCinematicPrestage(snapshotUrl, sequence)
            }, captureSize)
        } catch (eCapture) {
            mainWin.lagLog("Act III snapshot capture failed=" + eCapture)
            requested = false
        }
        if (!requested) {
            mainWin._finishStartupCinematicPrestage("", sequence)
        }
        return requested
    }

    Timer {
        id: startupCinematicSnapshotFallbackTimer
        property int sequence: -1
        interval: mainWin.startupCinematicSnapshotFallbackMs
        repeat: false
        onTriggered: {
            if (mainWin.startupCinematicBloomPrestageOnly
                    && sequence === mainWin.startupCinematicSnapshotSequence) {
                mainWin.lagLog("Act III snapshot capture timed out; using live bloom fallback")
                mainWin._finishStartupCinematicPrestage("", sequence)
            }
        }
    }

    function skipStartupCinematicBloom(reason) {
        if (!startupCinematicBloomActive) return false
        completeStartupCinematicBloom("user-skipped:" + String(reason || "input"))
        forceLaunchFocusLight()
        return true
    }

    function startupCinematicBloomOriginX() {
        return (mainWin.activeVisibleRect.x + (mainWin.activeVisibleRect.w / 2.0)) - mainWin.finalX
    }

    function startupCinematicBloomOriginY() {
        return (mainWin.activeVisibleRect.y + (mainWin.activeVisibleRect.h / 2.0)) - mainWin.finalY
    }

    function startProfessionalLaunchNow() {
        perfStart("window.transition.open", "detached=" + detachedMode + " phase=" + animationPhase + " style=Professional");
        setStartupPhase("professional-open", "startProfessionalLaunchNow");
        lagLog("startProfessionalLaunchNow begin"
            + " startupLaunchStarted=" + startupLaunchStarted
            + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"));

        startupFocusReassertRemaining = 0;
        startupFocusReassertTimer.stop();

        if (!mainWin.startupCinematicGeometryPrepared) {
            // Safe fallback for detached/diagnostic routes which do not use
            // the hidden readiness gate.
            var selected = mainWin.resolveTargetScreen();
            if (!selected) {
                lagLog("startProfessionalLaunchNow abort: resolveTargetScreen failed");
                return;
            }
            if (!mainWin.applyGeometryToTargetScreen(false)) {
                lagLog("startProfessionalLaunchNow abort: applyGeometryToTargetScreen failed");
                return;
            }
        }

        jelly.freezeToIdentity();
        jelly.opacityVal = 1.0;
        jelly.scaleX = 1.0;
        jelly.scaleY = 1.0;
        jelly.transX = 0.0;
        jelly.transY = 0.0;
        jelly.rotationVal = 0.0;
        startupCinematicBloomAnimation.stop();
        startupCinematicBloomReleaseStarted = false;
        startupCinematicSnapshotActive = false;
        startupCinematicSnapshotUrl = "";
        startupCinematicBloomScale = 1.0;
        startupCinematicBloomActive = false;
        var previousGeometryTransitionSuppressed = mainWin.geometryTransitionSuppressed;
        mainWin.geometryTransitionSuppressed = true;
        try {
            mainWin.transitionToSettled();
        } finally {
            mainWin.geometryTransitionSuppressed = previousGeometryTransitionSuppressed;
        }

        // During native prestage, keep the Windows host effectively invisible
        // until a frozen canvas has replaced its live full-size contents.
        mainWin.opacity = mainWin.startupCinematicBloomPrestageOnly ? 0.001 : 1.0;
        if (!mainWin.visible) {
            mainWin.show();
        }
        if (!mainWin.startupCinematicBloomPrestageOnly) {
            mainWin.forceLaunchFocus();
        }
        if (mainWin.detachedMode) {
            startupFocusReassertRemaining = 3;
            startupFocusReassertTimer.stop();
            startupFocusReassertTimer.start();
        }
        mainWin.markStartupFirstPixelVisible("professional-cinematic-bloom");
        if (mainWin.startupCinematicBloomPrestageOnly) {
            phaseLog("SPLASH", "Act III frozen canvas staging behind native splash t+" + splashElapsedMs() + "ms")
            mainWin.prestageStartupCinematicBloom()
            return
        }
        mainWin.startupCinematicBloomScale = 0.002
        mainWin.startupCinematicBloomActive = true
        mainWin.releaseStartupCinematicBloom()
    }

    NumberAnimation {
        id: startupCinematicBloomAnimation
        target: mainWin
        property: "startupCinematicBloomScale"
        from: 0.002
        to: 1.0
        duration: 400
        easing.type: Easing.OutCubic
        onFinished: {
            if (mainWin.startupCinematicBloomReleaseStarted) {
                mainWin.completeStartupCinematicBloom("animation-finished")
            }
        }
    }

    function startOpeningLaunchNow() {
        if (mainWin.appStyle === "Professional") {
            startProfessionalLaunchNow();
            return;
        }
        perfStart("window.transition.open", "detached=" + detachedMode + " phase=" + animationPhase);
        setStartupPhase("falling-window", "startOpeningLaunchNow");
        lagLog("startOpeningLaunchNow begin"
            + " startupLaunchStarted=" + startupLaunchStarted
            + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"));
        if (startupFastLaunchFocusEnabled && !mainWin.detachedMode) {
            forceLaunchFocusLight();
            startupFocusReassertRemaining = 0;
            startupFocusReassertTimer.stop();
        } else {
            forceLaunchFocus();
            startupFocusReassertRemaining = 3;
            startupFocusReassertTimer.stop();
            startupFocusReassertTimer.start();
            Qt.callLater(function() {
                forceLaunchFocus();
                Qt.callLater(function() {
                    forceLaunchFocus();
                });
            });
        }
        lagLog("startOpeningLaunchNow before jelly.prepareLaunch");
        phaseLog("SPLASH", "Falling window begins t+" + splashElapsedMs() + "ms");
        jelly.prepareLaunch();
        if (startupFastLaunchFocusEnabled && !mainWin.detachedMode) {
            Qt.callLater(function() {
                forceLaunchFocus();
                startupFocusReassertRemaining = 2;
                startupFocusReassertTimer.stop();
                startupFocusReassertTimer.start();
            });
        }
        lagLog("startOpeningLaunchNow after jelly.prepareLaunch");
    }

    function beginCoreLaunchSequence() {
        if (startupLaunchStarted) return;
        startupLaunchStarted = true;
        startupLaunchScreenLocked = false;
        primeStartupLaunchScreen("beginCoreLaunchSequence");
        setStartupPhase("core-launch", "beginCoreLaunchSequence");
        var elapsedMs = splashElapsedMs();
        var fallDelayMs = 0;
        var skipReasonText = "normal";
        if (startupSplashSequenceEpochMs > 0 && !startupSplashSkipInvoked) {
            fallDelayMs = Math.max(0, startupFallStartTimelineMs - elapsedMs);
            skipReasonText = "timeline";
        } else if (startupSplashSkipInvoked) {
            fallDelayMs = 0;
            skipReasonText = "user-skipped (no timeline wait)";
        }
        lagLog("beginCoreLaunchSequence"
            + " elapsedMs=" + elapsedMs
            + " fallTargetMs=" + startupFallStartTimelineMs
            + " fallDelayMs=" + fallDelayMs
            + " skipReason=" + skipReasonText
            + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"));
        phaseLog("SPLASH", "Splash complete -> prepare opening animation"
            + " t+" + elapsedMs + "ms"
            + " fallTargetMs=" + startupFallStartTimelineMs
            + " fallDelayMs=" + fallDelayMs
            + " skipReason=" + skipReasonText);
        if (fallDelayMs > 0) {
            startupLaunchDelayTimer.stop();
            startupLaunchDelayTimer.interval = fallDelayMs;
            startupLaunchDelayTimer.start();
            lagLog("beginCoreLaunchSequence waiting for delay timer intervalMs=" + fallDelayMs);
            return;
        }
        startOpeningLaunchNow();
    }

    function runDeferredBackendBootTask(taskPayload) {
        lagLog("deferred backend task triggered"
            + " startupDataBootStarted=" + mainWin.startupDataBootStarted
            + " startupDataBootComplete=" + mainWin.startupDataBootComplete
            + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"));
        if (!mainWin.startupAllowsHeavyWork("deferredBackendBootTask")) {
            return false;
        }
        if (!mainWin.startupDataBootStarted || mainWin.startupDataBootComplete) return true;
        if (!(mainWin.appRef && typeof mainWin.appRef.boot_backend === "function")) {
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootMessage = "";
            return true;
        }
        try {
            mainWin.lagLog("deferred backend task calling appRef.boot_backend()");
            mainWin.appRef.boot_backend();
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootMessage = "";
            mainWin.lagLog("deferred backend task boot_backend complete");
        } catch (e) {
            mainWin.startupDataBootFailed = true;
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootMessage = "Data load failed. Please restart.";
            mainWin.lagLog("deferred backend task boot_backend error=" + e);
            mainWin.reportUiFailure(
                "DetachedShellWindow.deferredBackendBoot",
                String(e),
                "Data load failed. Please restart."
            );
        }
        return true;
    }

    function triggerDeferredBackendBoot() {
        lagLog("[FORENSIC] triggerDeferredBackendBoot called")
        lagLog("triggerDeferredBackendBoot invoked"
            + " isSettled=" + mainWin.isSettled
            + " startupDataBootStarted=" + mainWin.startupDataBootStarted
            + " startupDataBootComplete=" + mainWin.startupDataBootComplete
            + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"));
        if (mainWin.detachedMode) {
            mainWin.startupDataBootStarted = true;
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootMessage = "";
            return;
        }
        if (!mainWin.isSettled) return;
        if (mainWin.startupDataBootStarted || mainWin.startupDataBootComplete) return;
        if (mainWin.appRef && mainWin.appRef.backendBooted) {
            mainWin.startupDataBootStarted = true;
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootMessage = "";
            return;
        }
        mainWin.startupDataBootStarted = true;
        mainWin.startupDataBootFailed = false;
        // Temporarily muted per UX request.
        // mainWin.startupDataBootMessage = "Loading Data - Please Wait";
        mainWin.startupDataBootMessage = "";
        if (mainWin.enqueuePostSettleTask(
            "DetachedShellWindow.deferredBackendBoot",
            mainWin,
            "runDeferredBackendBootTask",
            { "source": "triggerDeferredBackendBoot" },
            true
        )) {
            mainWin.lagLog("triggerDeferredBackendBoot queued deferred backend task");
            return;
        }
        lagLog("triggerDeferredBackendBoot restarting deferredBackendBootTimer");
        deferredBackendBootTimer.restart();
    }

    function beginStartupSplashSequence() {
        if (startupLaunchStarted) return false;
        if (!startupSplashComponent) return false;
        if (!startupSplashEnabled) return false;
        if (appStyle === "Professional") return false;
        startupHeavyWorkAllowed = false;
        startupHeavyWorkBlockedCount = 0;
        startupSettledEpochMs = 0;
        startupCheckpointPending = false;
        startupHeavyWorkGraceTimer.stop();
        setStartupPhase("splash-running", "beginStartupSplashSequence");

        var logoUrl = startupSplashLogoSourceUrl();
        var audioUrl = startupSplashAudioSourceUrl();
        if (logoUrl.length <= 0 || audioUrl.length <= 0) {
            phaseLog("SPLASH", "Skipping startup splash (logo=" + ((logoUrl.length > 0) ? "yes" : "no")
                + " audio=" + ((audioUrl.length > 0) ? "yes" : "no") + ")");
            return false;
        }

        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            phaseLog("SPLASH", "Skipping startup splash (no screen)");
            return false;
        }

        var splashScreen = targetScreen ? targetScreen : resolveTargetScreen();
        if (!splashScreen && mainWin.screen) {
            splashScreen = mainWin.screen;
        }
        if (!splashScreen) {
            splashScreen = screens[0];
        }
        var primaryIdx = indexOfScreen(splashScreen);
        if (primaryIdx < 0 || primaryIdx >= screens.length) {
            primaryIdx = 0;
        }

        destroyStartupSplash();
        startupSplashSequenceEpochMs = Date.now() + startupSplashSyncLeadMs;
        phaseLog("SPLASH", "Create startup splash windows across " + screens.length + " monitor(s)"
            + " syncLeadMs=" + startupSplashSyncLeadMs);

        var created = [];
        var screenInfos = [];
        if (appRef && appRef.getScreenGeometry) {
            for (var infoIdx = 0; infoIdx < screens.length; infoIdx++) {
                screenInfos[infoIdx] = appRef.getScreenGeometry(infoIdx);
            }
        }
        for (var i = 0; i < screens.length; i++) {
            var monitor = screens[i];
            if (!monitor) continue;
            var monitorInfo = (i < screenInfos.length) ? screenInfos[i] : null;
            // Splash should cover each full monitor, including taskbars.
            var splashRect = fullRectForScreen(monitor, monitorInfo);
            var sx = Math.round(splashRect.x);
            var sy = Math.round(splashRect.y);
            var sw = Math.max(1, Math.round(splashRect.w));
            var sh = Math.max(1, Math.round(splashRect.h));
            var splashObj = startupSplashComponent.createObject(null, {
                "mainWindow": mainWin,
                "splashX": sx,
                "splashY": sy,
                "splashW": sw,
                "splashH": sh,
                "logoSource": logoUrl,
                "audioSource": audioUrl,
                "audioEnabled": (i === primaryIdx) && (mainWin.soundEffectsEnabled !== false),
                "inputCaptureEnabled": (i === primaryIdx),
                "sharedStartEpochMs": startupSplashSequenceEpochMs,
                "launchScreen": monitor,
                "screen": monitor,
                "visible": false
            });
            if (!splashObj) {
                phaseLog("SPLASH", "Startup splash create failed monitor idx=" + i
                    + " rect=" + fmtRect(sx, sy, sw, sh));
                continue;
            }
            splashObj.splashX = sx;
            splashObj.splashY = sy;
            splashObj.splashW = sw;
            splashObj.splashH = sh;
            created.push({
                "obj": splashObj,
                "idx": i,
                "rect": fmtRect(sx, sy, sw, sh)
            });
        }

        if (created.length <= 0) {
            phaseLog("SPLASH", "Startup splash create failed on all monitors -> fallback to opening animation");
            return false;
        }

        startupSplashRefs = [];
        startupSplashRef = null;
        for (var j = 0; j < created.length; j++) {
            startupSplashRefs.push(created[j].obj);
            if (!startupSplashRef && created[j].idx === primaryIdx) {
                startupSplashRef = created[j].obj;
            }
        }
        if (!startupSplashRef && startupSplashRefs.length > 0) {
            startupSplashRef = startupSplashRefs[0];
        }
        startupSplashPendingCount = startupSplashRefs.length;

        for (var k = 0; k < created.length; k++) {
            var entry = created[k];
            var splashObjEntry = entry.obj;
            var monitorIdx = entry.idx;
            var rectLabel = entry.rect;
            (function(splashRefObj, idx) {
                splashRefObj.finished.connect(function(reason) {
                    mainWin.phaseLog("SPLASH", "Startup splash monitor idx=" + idx + " finished reason=" + reason);
                    var remaining = mainWin.removeStartupSplashRef(splashRefObj);
                    if (remaining <= 0) {
                        mainWin.phaseLog("SPLASH", "All startup splash monitors finished");
                        mainWin.beginCoreLaunchSequence();
                    }
                });
            })(splashObjEntry, monitorIdx);

            if (splashObjEntry.startSequence) {
                phaseLog("SPLASH", "Start startup splash monitor idx=" + monitorIdx
                    + ((monitorIdx === primaryIdx) ? " [audio]" : " [visual-only]")
                    + " rect=" + rectLabel);
                splashObjEntry.startSequence();
            } else {
                phaseLog("SPLASH", "Startup splash missing startSequence monitor idx=" + monitorIdx);
                removeStartupSplashRef(splashObjEntry);
                try {
                    splashObjEntry.closeOverlay("missing-startSequence");
                } catch (e) {
                    try {
                        splashObjEntry.destroy();
                    } catch (e2) {
                    }
                }
            }
        }

        if (startupSplashPendingCount <= 0) {
            phaseLog("SPLASH", "Startup splash could not start -> fallback");
            destroyStartupSplash();
            return false;
        }
        return true;
    }

    function createClosingOverlayWithSnapshot(snapshotUrl) {
        if (!closingOverlayComponent) return false;
        var frozen = closingOverlayGeometry;
        var rect = (frozen && frozen.rect) ? frozen.rect : closingCanvasRect();
        var target = (frozen && isFinite(frozen.targetX) && isFinite(frozen.targetY))
            ? { "x": frozen.targetX, "y": frozen.targetY }
            : closeTargetGlobalPoint();
        var contentX = (frozen && isFinite(frozen.contentX)) ? frozen.contentX : finalX;
        var contentY = (frozen && isFinite(frozen.contentY)) ? frozen.contentY : finalY;
        var contentW = (frozen && isFinite(frozen.contentW)) ? frozen.contentW : finalW;
        var contentH = (frozen && isFinite(frozen.contentH)) ? frozen.contentH : finalH;
        var sourceScreen = (frozen && frozen.sourceScreen) ? frozen.sourceScreen : targetScreen;
        phaseLog("CLOSING", "Overlay create requested rect=" + fmtRect(rect.x, rect.y, rect.w, rect.h)
            + " content=" + fmtRect(contentX, contentY, contentW, contentH)
            + " target=" + Math.round(target.x) + "," + Math.round(target.y)
            + " snapshot=" + ((snapshotUrl && snapshotUrl.length > 0) ? "yes" : "no"));
        var overlayProps = {
            "mainWindow": mainWin,
            "jellyController": jelly,
            "overlayX": rect.x,
            "overlayY": rect.y,
            "overlayWidth": rect.w,
            "overlayHeight": rect.h,
            "contentX": Math.round(contentX - rect.x),
            "contentY": Math.round(contentY - rect.y),
            "contentWidth": Math.max(1, Math.round(contentW)),
            "contentHeight": Math.max(1, Math.round(contentH)),
            "targetX": Math.round(target.x - rect.x),
            "targetY": Math.round(target.y - rect.y),
            "snapshotUrl": snapshotUrl ? snapshotUrl : "",
            // Do not permit a first frame on the default monitor.  Pin the
            // window to the monitor containing the closing surface, then
            // reveal it only after all geometry has been applied.
            "visible": false
        };
        if (sourceScreen) {
            overlayProps["screen"] = sourceScreen;
        }
        var overlayObj = closingOverlayComponent.createObject(null, overlayProps);
        if (!overlayObj) {
            return false;
        }

        closingOverlayRef = overlayObj;
        overlayObj.handoffReady.connect(function() {
            if (!mainWin.isClosing) return;
            if (mainWin.closeMotionStarted) return;
            mainWin.closeMotionStarted = true;
            mainWin.phaseLog("CLOSING", "Overlay handoff ready -> starting close sequence");
            // Hide main window content only after overlay has first painted.
            // This prevents any visible host relocation/teleport frame.
            mainWin.opacity = 0.0;
            if (overlayObj.startClose) {
                overlayObj.startClose();
                return;
            }
            mainWin.startCloseMotion("overlay-handoff-fallback");
        });
        if (overlayObj.closeFinished) {
            overlayObj.closeFinished.connect(function() {
                if (!mainWin.isClosing) return;
                mainWin.phaseLog("CLOSING", "Overlay close finished -> finalize");
                mainWin.finalizeCloseSequence("overlay-close-finished");
            });
        }
        try {
            if (sourceScreen) {
                overlayObj.screen = sourceScreen;
            }
            overlayObj.x = Math.round(rect.x);
            overlayObj.y = Math.round(rect.y);
            overlayObj.width = Math.max(1, Math.round(rect.w));
            overlayObj.height = Math.max(1, Math.round(rect.h));
            overlayObj.visible = true;
        } catch (e) {
            phaseLog("CLOSING", "Overlay monitor pin failed; using frozen global geometry err=" + e);
            overlayObj.visible = true;
        }
        return true;
    }

    function closeTargetGlobalPoint() {
        if (closeTargetOverrideActive
            && isFinite(closeTargetOverrideX)
            && isFinite(closeTargetOverrideY)) {
            return {
                "x": Math.round(closeTargetOverrideX),
                "y": Math.round(closeTargetOverrideY)
            };
        }
        var rect = activeVisibleRectForMaximize();
        var centerX = finalX + (finalW / 2.0);
        var targetX = Math.round(clampNumber(centerX, rect.x + 1, rect.x + rect.w - 1));
        var topInset = Math.max(1, Math.floor(Math.max(1, monitorFrameThickness) / 2));
        var targetY = Math.round(rect.y + topInset);
        return {
            "x": targetX,
            "y": targetY
        };
    }

    function beginClosingOverlayHandoff() {
        if (!closingOverlayComponent || !contentLayer || !contentLayer.grabToImage) return false;

        destroyClosingOverlay();
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        var handoffSeq = closingOverlayHandoffSeq + 1;
        closingOverlayHandoffSeq = handoffSeq;
        var requested = false;
        phaseLog("CLOSING", "Overlay handoff capture requested seq=" + handoffSeq
            + " grabSize=" + Math.max(1, finalW) + "x" + Math.max(1, finalH));
        try {
            requested = contentLayer.grabToImage(function(result) {
                if (handoffSeq !== closingOverlayHandoffSeq) return;
                if (!mainWin.isClosing || mainWin.closeMotionStarted) return;

                var snapUrl = "";
                if (result && result.url) {
                    snapUrl = result.url;
                }
                mainWin.phaseLog("CLOSING", "Overlay handoff capture complete seq=" + handoffSeq
                    + " snapshot=" + ((snapUrl && snapUrl.length > 0) ? "yes" : "no"));

                if (createClosingOverlayWithSnapshot(snapUrl)) {
                    return;
                }

                mainWin.phaseLog("CLOSING", "Overlay handoff fallback -> in-place close motion");
                applyClosingGeometryAtomically();
                mainWin.startCloseMotion("phase-transition-fallback");
            }, Qt.size(Math.max(1, finalW), Math.max(1, finalH)));
        } catch (e) {
            requested = false;
            phaseLog("CLOSING", "Overlay handoff capture exception: " + e);
        }
        if (!requested) {
            phaseLog("CLOSING", "Overlay handoff capture request was not accepted");
        }
        return requested;
    }

    function destroyMinimizeOverlay() {
        if (!minimizeOverlayRef) return;
        try {
            minimizeOverlayRef.closeOverlay("replace");
        } catch (e) {
            try {
                minimizeOverlayRef.destroy();
            } catch (e2) {
            }
        }
        minimizeOverlayRef = null;
    }

    function clearMinimizeRestoreState() {
        minimizeRestorePending = false;
        minimizeRestoreSnapshotUrl = "";
        minimizeRestoreFinalX = 0;
        minimizeRestoreFinalY = 0;
        minimizeRestoreFinalW = 1;
        minimizeRestoreFinalH = 1;
        minimizeRestoreTargetX = 0;
        minimizeRestoreTargetY = 0;
    }

    function minimizeTargetGlobalPoint() {
        var rect = activeVisibleRectForMaximize();
        var centerX = finalX + (finalW / 2.0);
        var centerY = finalY + (finalH / 2.0);
        var targetX = Math.round(clampNumber(centerX, rect.x + 1, rect.x + rect.w - 1));
        var targetY = Math.round(rect.y + rect.h + Math.max(8, Math.round(Math.max(1, taskbarSize) * 0.5)));

        if (taskbarEdge === "top") {
            targetY = Math.round(rect.y - Math.max(8, Math.round(Math.max(1, taskbarSize) * 0.5)));
        } else if (taskbarEdge === "left") {
            targetX = Math.round(rect.x - Math.max(8, Math.round(Math.max(1, taskbarSize) * 0.5)));
            targetY = Math.round(clampNumber(centerY, rect.y + 1, rect.y + rect.h - 1));
        } else if (taskbarEdge === "right") {
            targetX = Math.round(rect.x + rect.w + Math.max(8, Math.round(Math.max(1, taskbarSize) * 0.5)));
            targetY = Math.round(clampNumber(centerY, rect.y + 1, rect.y + rect.h - 1));
        }

        return {
            "x": targetX,
            "y": targetY
        };
    }

    function minimizeOverlayMotionRect(contentGX, contentGY, contentW, contentH, targetGX, targetGY) {
        var cw = Math.max(1, Math.round(contentW));
        var ch = Math.max(1, Math.round(contentH));
        var cx = Math.round(contentGX);
        var cy = Math.round(contentGY);
        var tx = Math.round(targetGX);
        var ty = Math.round(targetGY);

        // Keep the overlay local to the actual motion path. Full-desktop overlays can drift on mixed-DPI setups.
        var swing = Math.max(cw, ch);
        var pad = Math.max(96, Math.round(swing * 0.25));

        var minX = Math.min(cx, tx) - pad;
        var minY = Math.min(cy, ty) - pad;
        var maxX = Math.max(cx + cw, tx) + pad;
        var maxY = Math.max(cy + ch, ty) + pad;

        return {
            "x": Math.round(minX),
            "y": Math.round(minY),
            "w": Math.max(1, Math.round(maxX - minX)),
            "h": Math.max(1, Math.round(maxY - minY))
        };
    }

    function createMinimizeOverlayWithSnapshot(snapshotUrl) {
        if (!minimizeOverlayComponent) return false;
        var target = minimizeTargetGlobalPoint();
        var rect = minimizeOverlayMotionRect(finalX, finalY, finalW, finalH, target.x, target.y);

        minimizeRestoreFinalX = Math.round(finalX);
        minimizeRestoreFinalY = Math.round(finalY);
        minimizeRestoreFinalW = Math.max(1, Math.round(finalW));
        minimizeRestoreFinalH = Math.max(1, Math.round(finalH));
        minimizeRestoreTargetX = Math.round(target.x);
        minimizeRestoreTargetY = Math.round(target.y);
        minimizeRestoreSnapshotUrl = snapshotUrl ? snapshotUrl : "";
        minimizeRestorePending = (minimizeRestoreSnapshotUrl.length > 0);
        phaseLog("MINIMIZE", "Overlay create requested rect=" + fmtRect(rect.x, rect.y, rect.w, rect.h)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " target=" + Math.round(target.x) + "," + Math.round(target.y)
            + " snapshot=" + ((minimizeRestorePending) ? "yes" : "no"));

        var overlayProps = {
            "mainWindow": mainWin,
            "overlayX": rect.x,
            "overlayY": rect.y,
            "overlayWidth": rect.w,
            "overlayHeight": rect.h,
            "contentX": Math.round(finalX - rect.x),
            "contentY": Math.round(finalY - rect.y),
            "contentWidth": Math.max(1, Math.round(finalW)),
            "contentHeight": Math.max(1, Math.round(finalH)),
            "targetX": Math.round(target.x - rect.x),
            "targetY": Math.round(target.y - rect.y),
            "restoreReplay": false,
            "snapshotUrl": snapshotUrl ? snapshotUrl : "",
            "visible": true
        };
        if (targetScreen) {
            overlayProps["screen"] = targetScreen;
        }
        var overlayObj = minimizeOverlayComponent.createObject(null, overlayProps);
        if (!overlayObj) {
            return false;
        }

        minimizeOverlayRef = overlayObj;
        overlayObj.handoffReady.connect(function() {
            if (!mainWin.isMinimizing) return;
            mainWin.phaseLog("MINIMIZE", "Overlay handoff ready -> start minimize sequence");
            mainWin.opacity = 0.0;
            overlayObj.startMinimize();
        });
        overlayObj.minimizeFinished.connect(function() {
            if (!mainWin.isMinimizing) return;
            mainWin.phaseLog("MINIMIZE", "Overlay minimize finished -> showMinimized");
            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                mainWin.sfxBusRef.playWindowSettle("minimize", 0.60);
            }
            mainWin.isMinimizing = false;
            mainWin.showMinimized();
            // Keep host fully hidden while minimized so taskbar restore has no ghost frame.
            mainWin.opacity = mainWin.minimizeRestorePending ? 0.0 : 1.0;
            mainWin.destroyMinimizeOverlay();
        });
        return true;
    }

    function beginMinimizeOverlayHandoff() {
        if (!minimizeOverlayComponent || !contentLayer || !contentLayer.grabToImage) return false;

        destroyMinimizeOverlay();
        var handoffSeq = minimizeOverlayHandoffSeq + 1;
        minimizeOverlayHandoffSeq = handoffSeq;
        var requested = false;
        phaseLog("MINIMIZE", "Overlay handoff capture requested seq=" + handoffSeq
            + " grabSize=" + Math.max(1, finalW) + "x" + Math.max(1, finalH));
        try {
            requested = contentLayer.grabToImage(function(result) {
                if (handoffSeq !== minimizeOverlayHandoffSeq) return;
                if (!mainWin.isMinimizing) return;

                var snapUrl = "";
                if (result && result.url) {
                    snapUrl = result.url;
                }
                mainWin.phaseLog("MINIMIZE", "Overlay handoff capture complete seq=" + handoffSeq
                    + " snapshot=" + ((snapUrl && snapUrl.length > 0) ? "yes" : "no"));

                if (createMinimizeOverlayWithSnapshot(snapUrl)) {
                    return;
                }

                mainWin.phaseLog("MINIMIZE", "Overlay handoff fallback -> direct minimize");
                mainWin.isMinimizing = false;
                mainWin.clearMinimizeRestoreState();
                mainWin.opacity = 1.0;
                mainWin.showMinimized();
            }, Qt.size(Math.max(1, finalW), Math.max(1, finalH)));
        } catch (e) {
            requested = false;
            phaseLog("MINIMIZE", "Overlay handoff capture exception: " + e);
        }
        if (!requested) {
            phaseLog("MINIMIZE", "Overlay handoff capture request was not accepted");
        }
        return requested;
    }

    function restoreOverlayRectForMinimizeReplay() {
        return minimizeOverlayMotionRect(
            minimizeRestoreFinalX,
            minimizeRestoreFinalY,
            minimizeRestoreFinalW,
            minimizeRestoreFinalH,
            minimizeRestoreTargetX,
            minimizeRestoreTargetY
        );
    }

    function createRestoreOverlayFromMinimize() {
        if (!minimizeOverlayComponent) return false;
        if (!minimizeRestoreSnapshotUrl || minimizeRestoreSnapshotUrl.length <= 0) return false;

        var rect = restoreOverlayRectForMinimizeReplay();
        phaseLog("RESTORE", "Replay overlay create rect=" + fmtRect(rect.x, rect.y, rect.w, rect.h)
            + " restoreFinal=" + fmtRect(minimizeRestoreFinalX, minimizeRestoreFinalY, minimizeRestoreFinalW, minimizeRestoreFinalH)
            + " restoreTarget=" + Math.round(minimizeRestoreTargetX) + "," + Math.round(minimizeRestoreTargetY));
        var overlayProps = {
            "mainWindow": mainWin,
            "overlayX": rect.x,
            "overlayY": rect.y,
            "overlayWidth": rect.w,
            "overlayHeight": rect.h,
            "contentX": Math.round(minimizeRestoreFinalX - rect.x),
            "contentY": Math.round(minimizeRestoreFinalY - rect.y),
            "contentWidth": Math.max(1, Math.round(minimizeRestoreFinalW)),
            "contentHeight": Math.max(1, Math.round(minimizeRestoreFinalH)),
            "targetX": Math.round(minimizeRestoreTargetX - rect.x),
            "targetY": Math.round(minimizeRestoreTargetY - rect.y),
            "restoreReplay": true,
            "snapshotUrl": minimizeRestoreSnapshotUrl,
            "visible": true
        };
        if (targetScreen) {
            overlayProps["screen"] = targetScreen;
        }
        var overlayObj = minimizeOverlayComponent.createObject(null, overlayProps);
        if (!overlayObj) {
            return false;
        }

        minimizeOverlayRef = overlayObj;
        overlayObj.handoffReady.connect(function() {
            if (!mainWin.isRestoringFromMinimize) return;
            mainWin.phaseLog("RESTORE", "Replay overlay handoff ready -> start restore sequence");
            mainWin.opacity = 0.0;
            overlayObj.startRestore();
        });
        overlayObj.restoreFinished.connect(function() {
            if (!mainWin.isRestoringFromMinimize) return;
            mainWin.phaseLog("RESTORE", "Replay restore finished -> host visible");
            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                mainWin.sfxBusRef.playWindowSettle("restore", 0.60);
            }
            mainWin.isRestoringFromMinimize = false;
            mainWin.clearMinimizeRestoreState();
            mainWin.opacity = 1.0;
            mainWin.destroyMinimizeOverlay();
            mainWin.raise();
            mainWin._requestActivateIfFocusable(mainWin);
        });
        return true;
    }

    function beginRestoreFromMinimize() {
        if (isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        if (!minimizeRestorePending || !minimizeRestoreSnapshotUrl || minimizeRestoreSnapshotUrl.length <= 0) {
            phaseLog("RESTORE", "Skipped: no pending minimize snapshot");
            clearMinimizeRestoreState();
            return false;
        }
        if (animationPhase !== "settled") {
            phaseLog("RESTORE", "Skipped: animationPhase=" + animationPhase);
            clearMinimizeRestoreState();
            return false;
        }

        if (userMoveInProgress) {
            finishUserDrag();
        }
        if (userResizeInProgress) {
            finishUserResize();
        }

        isRestoringFromMinimize = true;
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.52);
        }
        phaseLog("RESTORE", "Begin restore from minimize final="
            + fmtRect(minimizeRestoreFinalX, minimizeRestoreFinalY, minimizeRestoreFinalW, minimizeRestoreFinalH));
        geometryTransitionSuppressed = true;
        finalX = Math.round(minimizeRestoreFinalX);
        finalY = Math.round(minimizeRestoreFinalY);
        finalW = Math.max(1, Math.round(minimizeRestoreFinalW));
        finalH = Math.max(1, Math.round(minimizeRestoreFinalH));
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        geometryTransitionSuppressed = false;

        if (createRestoreOverlayFromMinimize()) {
            return true;
        }

        phaseLog("RESTORE", "Replay overlay fallback -> direct visible restore");
        if (sfxBus && sfxBus.playWindowSettle) {
            sfxBus.playWindowSettle("restore", 0.50);
        }
        isRestoringFromMinimize = false;
        clearMinimizeRestoreState();
        opacity = 1.0;
        try {
            if (showNormal) showNormal();
        } catch (e) {
        }
        try {
            if (show) show();
        } catch (e) {
        }
        try {
            raise();
        } catch (e) {
        }
        try {
            _requestActivateIfFocusable(mainWin);
        } catch (e) {
        }
        return false;
    }

    function applyClosingGeometryAtomically() {
        var rect = closingCanvasRect();
        var hostPad = closePadPx(rect.w, rect.h);

        var nextHostX = Math.round(rect.x - hostPad);
        var nextHostY = Math.round(rect.y - hostPad);
        var nextHostW = Math.max(1, Math.round(rect.w + (hostPad * 2)));
        var nextHostH = Math.max(1, Math.round(rect.h + (hostPad * 2)));

        canvasX = rect.x;
        canvasY = rect.y;
        canvasW = rect.w;
        canvasH = rect.h;
        contentLocalX = finalX - canvasX;
        contentLocalY = finalY - canvasY;
        canvasLocalX = canvasX - nextHostX;
        canvasLocalY = canvasY - nextHostY;

        hostX = nextHostX;
        hostY = nextHostY;
        hostW = nextHostW;
        hostH = nextHostH;
    }

    function dragPadPx(refW, refH) {
        // Frame-0 fix: during settled phase, lock to glowPadding to prevent
        // host envelope expansion flash on the press frame.
        if (mainWin.animationPhase === "settled") {
            return Math.max(0, Math.round(mainWin.glowPadding));
        }
        var ratioPad = ratioToPixels(layoutRatios.dragPadPct, refW, refH, 1);
        return Math.max(ratioPad, settledPaddingPx());
    }

    function resizeHandleThicknessPx() {
        return ratioToPixels(layoutRatios.resizeHandleThicknessPct, Math.max(1, finalW), Math.max(1, finalH), 8);
    }

    function resizeCornerSizePx() {
        var base = ratioToPixels(layoutRatios.resizeCornerSizePct, Math.max(1, finalW), Math.max(1, finalH), 28);
        return Math.max(base, resizeHandleThicknessPx() * 3);
    }

    function resizeLiveCursorIsFresh() {
        return resizeLiveCursorValid
            && isFinite(resizeLiveCursorSampleMs)
            && resizeLiveCursorSampleMs > 0
            && (Date.now() - resizeLiveCursorSampleMs) <= Math.max(1, resizeLiveCursorFreshMs);
    }

    function resizeMinWidthPx() {
        var rect = activeVisibleRect;
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = { "x": usableX, "y": usableY, "w": Math.max(1, usableW), "h": Math.max(1, usableH) };
        }
        return ratioToPixels(layoutRatios.resizeMinWidthPct, Math.max(1, rect.w), Math.max(1, rect.h), 1);
    }

    function resizeMinHeightPx() {
        var rect = activeVisibleRect;
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = { "x": usableX, "y": usableY, "w": Math.max(1, usableW), "h": Math.max(1, usableH) };
        }
        return ratioToPixels(layoutRatios.resizeMinHeightPct, Math.max(1, rect.w), Math.max(1, rect.h), 1);
    }

    function isResizeHandleValid(handle) {
        return handle === "n" || handle === "s" || handle === "e" || handle === "w"
            || handle === "ne" || handle === "nw" || handle === "se" || handle === "sw";
    }

    function hostMarginPx(refW, refH, contentW, contentH) {
        var ratio = mainWin.lowPerformanceMode
            ? layoutRatios.hostMarginLowPerfPct
            : layoutRatios.hostMarginPct;
        var byMonitor = ratioToPixels(ratio, refW, refH, 1);
        var byMin = ratioToPixels(layoutRatios.hostMarginMinPct, refW, refH, 1);
        var safeCW = Math.max(1, contentW);
        var safeCH = Math.max(1, contentH);
        var byContent = Math.round(Math.max(safeCW, safeCH) * layoutRatios.hostMarginContentPct);
        return Math.max(byMin, Math.max(byMonitor, byContent));
    }

    function settledHostPaddingPx(refW, refH) {
        // Keep the native host exactly aligned with the settled canvas.  This
        // preserves the visible glow/resize perimeter without leaving a large
        // invisible, click-blocking rectangle across the monitor.
        var desiredPadding = glowPadding;
        if (!isFinite(desiredPadding) || desiredPadding < 0) {
            desiredPadding = settledPaddingPx(Math.max(1, finalW), Math.max(1, finalH));
        }
        var maxPadX = Math.max(0, Math.floor((Math.max(1, refW) - Math.max(1, finalW)) / 2));
        var maxPadY = Math.max(0, Math.floor((Math.max(1, refH) - Math.max(1, finalH)) / 2));
        return Math.max(0, Math.min(Math.round(desiredPadding), Math.min(maxPadX, maxPadY)));
    }

    function titleBarHeightPx() {
        return ratioToPixels(layoutRatios.titleBarHeightPct, resizeVisualWidthPx(), resizeVisualHeightPx(), 1);
    }

    function chromeCornerRadiusPx() {
        if (mainWin.appRef && mainWin.appRef.appStyle === "Professional") return 0;
        return ratioToPixels(layoutRatios.chromeCornerRadiusPct, resizeVisualWidthPx(), resizeVisualHeightPx(), 1);
    }

    function canvasFrameCornerRadiusPx() {
        var base = chromeCornerRadiusPx();
        if (mainWin.animationPhase !== "settled" || mainWin.userResizeInProgress) {
            return Math.max(0, base);
        }
        var safeFinalW = resizeVisualWidthPx();
        var safeFinalH = resizeVisualHeightPx();
        var desiredSettledPad = Math.max(0, settledPaddingPx(safeFinalW, safeFinalH));
        var monitorW = (mainWin.usableW > 0) ? mainWin.usableW : safeFinalW;
        var monitorH = (mainWin.usableH > 0) ? mainWin.usableH : safeFinalH;
        var maxSettledPadX = Math.max(0, Math.floor((monitorW - safeFinalW) * 0.5));
        var maxSettledPadY = Math.max(0, Math.floor((monitorH - safeFinalH) * 0.5));
        var settledPad = Math.max(0, Math.min(desiredSettledPad, Math.min(maxSettledPadX, maxSettledPadY)));

        // Keep corner radius stable during opening->settled handoff so shell geometry
        // cannot overshoot to very large radii while glow/canvas padding collapses.
        var lockToSettledPad = !mainWin.shellMaskSettleDelayReady
            || canvasTransition.running
            || canvasGeometryAdjust.transitionProgress < 0.995
            || mainWin.maximizeAnimInProgress;
        if (lockToSettledPad) {
            return Math.max(0, base + settledPad);
        }

        var safeCanvasW = Math.max(1, canvasW);
        var safeCanvasH = Math.max(1, canvasH);
        var padX = Math.max(0, Math.round((safeCanvasW - safeFinalW) * 0.5));
        var padY = Math.max(0, Math.round((safeCanvasH - safeFinalH) * 0.5));
        return Math.max(0, base + Math.max(settledPad, Math.max(padX, padY)));
    }

    function shellVisualCornerRadiusPx() {
        var base = canvasFrameCornerRadiusPx();
        if (mainWin.animationPhase !== "settled" || mainWin.userResizeInProgress) {
            return Math.max(0, base);
        }
        // Keep only a tiny settled inset to avoid a visible crescent line at corners.
        var subtleInsetPx = 1;
        return Math.max(0, base + subtleInsetPx);
    }

    function shellRoundedMaskActive() {
        return mainWin.outerRoundedShellMaskEnabled
            && (mainWin.animationPhase === "settled" || mainWin.animationPhase === "closing")
            && !canvasTransition.running
            && canvasGeometryAdjust.transitionProgress >= 0.995
            && mainWin.shellMaskSettleDelayReady
            && !mainWin.isMinimizing
            && !mainWin.isRestoringFromMinimize
            && !mainWin.maximizeAnimInProgress
            && !mainWin.userMoveInProgress
            && !mainWin.userResizeInProgress
            && !mainWin.systemMoveInProgress
            && !mainWin.dragFxVisible()
            && mainWin.canvasFrameCornerRadiusPx() > 0;
    }

    function chromeGlowNearPx() {
        var ratio = mainWin.lowPerformanceMode
            ? layoutRatios.chromeGlowNearLowPerfPct
            : layoutRatios.chromeGlowNearPct;
        return ratioToPixels(ratio, resizeVisualWidthPx(), resizeVisualHeightPx(), 1);
    }

    function chromeGlowFarPx() {
        var ratio = mainWin.lowPerformanceMode
            ? layoutRatios.chromeGlowFarLowPerfPct
            : layoutRatios.chromeGlowFarPct;
        return ratioToPixels(ratio, resizeVisualWidthPx(), resizeVisualHeightPx(), 1);
    }

    function themePickerRightOffsetPx() {
        return ratioToPixels(layoutRatios.themePickerRightPct, Math.max(1, usableW), Math.max(1, usableH), 1);
    }

    function themePickerTopOffsetPx() {
        return ratioToPixels(layoutRatios.themePickerTopPct, Math.max(1, usableW), Math.max(1, usableH), 1);
    }

    function openDropOvershootPx() {
        return ratioToPixels(layoutRatios.openDropOvershootPct, Math.max(1, usableW), Math.max(1, usableH), 1);
    }

    function openingMaxSquashScaleX() {
        var value = layoutRatios.openingMaxSquashScaleX;
        return (typeof value === "number" && isFinite(value) && value > 1.0) ? value : 1.40;
    }

    function openingMaxReboundScaleY() {
        var value = layoutRatios.openingMaxReboundScaleY;
        return (typeof value === "number" && isFinite(value) && value > 1.0) ? value : 1.12;
    }

    function openingVisualBleedPx(contentW, contentH) {
        var safeW = Math.max(1, (typeof contentW === "number") ? contentW : finalW);
        var safeH = Math.max(1, (typeof contentH === "number") ? contentH : finalH);
        var glowRatio = mainWin.lowPerformanceMode
            ? layoutRatios.chromeGlowFarLowPerfPct
            : layoutRatios.chromeGlowFarPct;
        var glowFar = ratioToPixels(glowRatio, safeW, safeH, 1);
        var corner = ratioToPixels(layoutRatios.chromeCornerRadiusPct, safeW, safeH, 1);
        return Math.max(10, Math.round(glowFar * 0.85), Math.round(corner * 0.22));
    }

    function openingFloorGuardPx(contentW, contentH) {
        var minGuard = layoutRatios.openingFloorGuardMinPx;
        if (typeof minGuard !== "number" || !isFinite(minGuard) || minGuard < 0) {
            minGuard = 58;
        }
        return Math.max(Math.round(minGuard), openingVisualBleedPx(contentW, contentH) + openingFrameInsetPx(contentW, contentH));
    }

    function openingFrameInsetPx(contentW, contentH) {
        var minInset = layoutRatios.openingFrameInsetMinPx;
        if (typeof minInset !== "number" || !isFinite(minInset) || minInset < 0) {
            minInset = 18;
        }
        var framePx = Math.max(
            0,
            Math.round((typeof monitorFrameGlowThickness === "number") ? monitorFrameGlowThickness : 0),
            Math.round((typeof monitorFrameThickness === "number") ? monitorFrameThickness : 0)
        );
        return Math.max(Math.round(minInset), framePx + 10, Math.round(openingVisualBleedPx(contentW, contentH) * 0.35));
    }

    function insetRect(rect, insetPx) {
        var r = (rect && rect.w > 0 && rect.h > 0) ? rect : { "x": 0, "y": 0, "w": 1, "h": 1 };
        var inset = Math.max(0, Math.round(insetPx));
        var maxInset = Math.max(0, Math.floor((Math.min(r.w, r.h) - 1) / 2));
        inset = Math.min(inset, maxInset);
        return {
            "x": Math.round(r.x + inset),
            "y": Math.round(r.y + inset),
            "w": Math.max(1, Math.round(r.w - (inset * 2))),
            "h": Math.max(1, Math.round(r.h - (inset * 2)))
        };
    }

    function unionRects(a, b) {
        if (!a || a.w <= 0 || a.h <= 0) return b;
        if (!b || b.w <= 0 || b.h <= 0) return a;
        var x1 = Math.min(a.x, b.x);
        var y1 = Math.min(a.y, b.y);
        var x2 = Math.max(a.x + a.w, b.x + b.w);
        var y2 = Math.max(a.y + a.h, b.y + b.h);
        return {
            "x": Math.round(x1),
            "y": Math.round(y1),
            "w": Math.max(1, Math.round(x2 - x1)),
            "h": Math.max(1, Math.round(y2 - y1))
        };
    }

    function openingVisibleRect() {
        var rect = activeVisibleRect;
        if (rect && rect.w > 0 && rect.h > 0) {
            return rect;
        }
        if (usableW > 0 && usableH > 0) {
            return { "x": usableX, "y": usableY, "w": usableW, "h": usableH };
        }
        return { "x": 0, "y": 0, "w": Math.max(1, width), "h": Math.max(1, height) };
    }

    function openingHostBaseRect(visibleRect) {
        var safeVisible = (visibleRect && visibleRect.w > 0 && visibleRect.h > 0)
            ? visibleRect
            : openingVisibleRect();
        var fullRect = null;
        if (targetScreen) {
            fullRect = fullRectForScreen(targetScreen, targetScreenInfo);
        }
        return unionRects(safeVisible, fullRect ? fullRect : safeVisible);
    }

    function openingMotionSafeRect(contentW, contentH) {
        return insetRect(openingVisibleRect(), openingFrameInsetPx(contentW, contentH));
    }

    function openingConstrainedSize(contentW, contentH, aspect, availW, availH) {
        var safeAspect = (typeof aspect === "number" && isFinite(aspect) && aspect > 0.01) ? aspect : 1.70;
        var w = Math.max(1, Math.round(contentW));
        var h = Math.max(1, Math.round(contentH));
        var aw = Math.max(1, Math.round(availW));
        var ah = Math.max(1, Math.round(availH));
        for (var i = 0; i < 3; i++) {
            var bleed = openingVisualBleedPx(w, h);
            var inset = openingFrameInsetPx(w, h);
            var maxW = Math.max(1, Math.floor(aw - ((bleed + inset) * 2)));
            var maxH = Math.max(1, Math.floor(ah - ((bleed + inset) * 2)));
            if (w > maxW) {
                w = maxW;
                h = Math.max(1, Math.round(w / safeAspect));
            }
            if (h > maxH) {
                h = maxH;
                w = Math.max(1, Math.round(h * safeAspect));
            }
        }

        return { "w": Math.max(1, Math.round(w)), "h": Math.max(1, Math.round(h)) };
    }

    function openingTransformOriginX() {
        return Math.max(1, finalW) / 2.0;
    }

    function openingTransformOriginY() {
        return Math.max(1, finalH);
    }

    function openingVisualBoundsForTransform(transX, transY, scaleX, scaleY) {
        var tx = (typeof transX === "number" && isFinite(transX)) ? transX : 0.0;
        var ty = (typeof transY === "number" && isFinite(transY)) ? transY : 0.0;
        var sx = (typeof scaleX === "number" && isFinite(scaleX) && scaleX > 0.01) ? scaleX : 1.0;
        var sy = (typeof scaleY === "number" && isFinite(scaleY) && scaleY > 0.01) ? scaleY : 1.0;
        var bleed = openingVisualBleedPx();
        var left = -bleed;
        var right = finalW + bleed;
        var top = -bleed;
        var bottom = finalH + bleed;
        var ox = openingTransformOriginX();
        var oy = openingTransformOriginY();
        var baseX = canvasX + contentLocalX;
        var baseY = canvasY + contentLocalY;

        var x1 = ox + ((left - ox) * sx) + tx;
        var x2 = ox + ((right - ox) * sx) + tx;
        var y1 = oy + ((top - oy) * sy) + ty;
        var y2 = oy + ((bottom - oy) * sy) + ty;

        var minX = baseX + Math.min(x1, x2);
        var maxX = baseX + Math.max(x1, x2);
        var minY = baseY + Math.min(y1, y2);
        var maxY = baseY + Math.max(y1, y2);
        return {
            "x": minX,
            "y": minY,
            "w": Math.max(1, maxX - minX),
            "h": Math.max(1, maxY - minY)
        };
    }

    function openingSafeScaleX(requestedScaleX, requestedTransX) {
        if (mainWin.detachedMode || mainWin.animationPhase !== "opening") return requestedScaleX;
        var sx = (typeof requestedScaleX === "number" && isFinite(requestedScaleX) && requestedScaleX > 0.01)
            ? requestedScaleX : 1.0;
        var tx = (typeof requestedTransX === "number" && isFinite(requestedTransX)) ? requestedTransX : 0.0;
        var safe = openingMotionSafeRect();
        var bleed = openingVisualBleedPx();
        var left = -bleed;
        var right = finalW + bleed;
        var ox = openingTransformOriginX();
        var originGlobal = canvasX + contentLocalX + ox + tx;
        var leftSpan = Math.max(1, ox - left);
        var rightSpan = Math.max(1, right - ox);
        var maxLeftScale = (originGlobal - safe.x) / leftSpan;
        var maxRightScale = ((safe.x + safe.w) - originGlobal) / rightSpan;
        var maxScale = Math.max(0.20, Math.min(maxLeftScale, maxRightScale, openingMaxSquashScaleX()));
        return Math.min(sx, maxScale);
    }

    function openingSafeScaleY(requestedScaleY) {
        if (mainWin.detachedMode || mainWin.animationPhase !== "opening") return requestedScaleY;
        var sy = (typeof requestedScaleY === "number" && isFinite(requestedScaleY) && requestedScaleY > 0.01)
            ? requestedScaleY : 1.0;
        if (sy <= 1.0) return sy;
        var safe = openingMotionSafeRect();
        var bleed = openingVisualBleedPx();
        var maxScale = Math.max(0.20, Math.min(openingMaxReboundScaleY(), safe.h / Math.max(1, finalH + (bleed * 2))));
        return Math.min(sy, maxScale);
    }

    function openingSafeTransX(requestedTransX, renderScaleX) {
        if (mainWin.detachedMode || mainWin.animationPhase !== "opening") return requestedTransX;
        var tx = (typeof requestedTransX === "number" && isFinite(requestedTransX)) ? requestedTransX : 0.0;
        var sx = (typeof renderScaleX === "number" && isFinite(renderScaleX) && renderScaleX > 0.01)
            ? renderScaleX : 1.0;
        var safe = openingMotionSafeRect();
        var bounds = openingVisualBoundsForTransform(tx, 0.0, sx, 1.0);
        if (bounds.x < safe.x) {
            tx += safe.x - bounds.x;
            bounds = openingVisualBoundsForTransform(tx, 0.0, sx, 1.0);
        }
        var overflowRight = (bounds.x + bounds.w) - (safe.x + safe.w);
        if (overflowRight > 0) {
            tx -= overflowRight;
        }
        return tx;
    }

    function openingSafeTransY(requestedTransY, renderScaleY) {
        if (mainWin.detachedMode || mainWin.animationPhase !== "opening") return requestedTransY;
        var ty = (typeof requestedTransY === "number" && isFinite(requestedTransY)) ? requestedTransY : 0.0;
        var sy = (typeof renderScaleY === "number" && isFinite(renderScaleY) && renderScaleY > 0.01)
            ? renderScaleY : 1.0;
        var safe = openingMotionSafeRect();
        var bounds = openingVisualBoundsForTransform(0.0, ty, 1.0, sy);

        if (ty >= 0.0 && bounds.y < safe.y) {
            ty += safe.y - bounds.y;
            bounds = openingVisualBoundsForTransform(0.0, ty, 1.0, sy);
        }

        var overflowBottom = (bounds.y + bounds.h) - (safe.y + safe.h);
        if (overflowBottom > 0) {
            ty -= overflowBottom;
        }
        return ty;
    }

    function openingStartTransY() {
        var safe = openingVisibleRect();
        var topInCanvasY = safe.y - canvasY;
        var bleed = openingVisualBleedPx();
        return Math.round(topInCanvasY - (contentLocalY + finalH + bleed) - Math.max(1, openDropOvershootPx()));
    }

    function openingImpactTransY() {
        var safe = openingMotionSafeRect();
        var floorInCanvasY = (safe.y - canvasY) + safe.h;
        var bleed = openingVisualBleedPx();
        var target = Math.round((floorInCanvasY - openingFloorGuardPx()) - (contentLocalY + finalH + bleed));
        return Math.round(openingSafeTransY(target, 1.0));
    }

    function openingImpactScaleXTarget() {
        return openingSafeScaleX(openingMaxSquashScaleX(), 0.0);
    }

    function openingImpactScaleYTarget() {
        return Math.min(0.62, openingSafeScaleY(0.62));
    }

    function interactionDesktopRect() {
        updateDebugOverlayBounds();
        return {
            "x": Math.round(debugBoundsX),
            "y": Math.round(debugBoundsY),
            "w": Math.max(1, Math.round(debugBoundsW)),
            "h": Math.max(1, Math.round(debugBoundsH))
        };
    }

    function pinInteractionHostEnvelope() {
        var desktopRect = interactionDesktopRect();
        var refW = Math.max(1, desktopRect.w);
        var refH = Math.max(1, desktopRect.h);
        var hostPad = hostMarginPx(refW, refH, Math.max(1, finalW), Math.max(1, finalH));
        hostX = Math.round(desktopRect.x - hostPad);
        hostY = Math.round(desktopRect.y - hostPad);
        hostW = Math.max(1, Math.round(desktopRect.w + (hostPad * 2)));
        hostH = Math.max(1, Math.round(desktopRect.h + (hostPad * 2)));
    }

    function dragInteractionCanvasRect() {
        var refRect = activeVisibleRect;
        if (!refRect || refRect.w <= 0 || refRect.h <= 0) {
            refRect = activeVisibleRectForMaximize();
        }
        var refW = Math.max(1, (refRect && refRect.w > 0) ? refRect.w : Math.max(1, usableW));
        var refH = Math.max(1, (refRect && refRect.h > 0) ? refRect.h : Math.max(1, usableH));
        var dragPad = dragPadPx(refW, refH);
        return {
            "x": Math.round(finalX - dragPad),
            "y": Math.round(finalY - dragPad),
            "w": Math.max(1, Math.round(finalW + (dragPad * 2))),
            "h": Math.max(1, Math.round(finalH + (dragPad * 2)))
        };
    }

    function applyDragInteractionGeometry() {
        if (dragGeometryLockedOnPressFrame()) {
            logInteractionTrace("DRAG-GEOM-LOCK", "applyDragInteractionGeometry press-frame lock", false);
            contentLocalX = Math.round(finalX - canvasX);
            contentLocalY = Math.round(finalY - canvasY);
            return;
        }
        var dragRect = dragInteractionCanvasRect();
        canvasX = dragRect.x;
        canvasY = dragRect.y;
        canvasW = dragRect.w;
        canvasH = dragRect.h;

        var hostRect = activeVisibleRect;
        if (!hostRect || hostRect.w <= 0 || hostRect.h <= 0) {
            hostRect = {
                "x": usableX,
                "y": usableY,
                "w": Math.max(1, usableW),
                "h": Math.max(1, usableH)
            };
        }
        if (!hostRect || hostRect.w <= 0 || hostRect.h <= 0) {
            hostRect = {
                "x": dragRect.x,
                "y": dragRect.y,
                "w": dragRect.w,
                "h": dragRect.h
            };
        }

        var hostPad = hostMarginPx(
            Math.max(1, hostRect.w),
            Math.max(1, hostRect.h),
            Math.max(1, finalW),
            Math.max(1, finalH)
        );
        if (hostW <= 1 || hostH <= 1) {
            logInteractionTrace("DRAG-GEOM-SEED", "seed host from activeVisibleRect", false);
            hostX = Math.round(hostRect.x - hostPad);
            hostY = Math.round(hostRect.y - hostPad);
            hostW = Math.max(1, Math.round(hostRect.w + (hostPad * 2)));
            hostH = Math.max(1, Math.round(hostRect.h + (hostPad * 2)));
        }
        // During active fallback drag, treat the existing host shell as a movement
        // buffer instead of recentring it around the canvas every frame. The
        // immediate recenter path moves the native window on the first real drag
        // delta, which is the exact jump reported on first click.
        //
        // We only expand the host once the drag canvas reaches a host edge.
        ensureHostContainsRect(canvasX, canvasY, canvasW, canvasH, 0, false);

        contentLocalX = Math.round(finalX - canvasX);
        contentLocalY = Math.round(finalY - canvasY);
        canvasLocalX = canvasX - hostX;
        canvasLocalY = canvasY - hostY;
    }

    function dragGeometryLockedOnPressFrame() {
        return animationPhase === "settled"
            && userMoveInProgress
            && !dragHasRealDelta;
    }

    function resizeGeometryLockedOnPressFrame() {
        return animationPhase === "settled"
            && userResizeInProgress
            && !resizeHasRealDelta;
    }

    function syncDragContentPosition() {
        // Frame-0 guard: do NOT recalculate canvas/host on the press frame.
        // Wait for the first real mouse delta before allowing rebase.
        if (resizeGeometryLockedOnPressFrame()) {
            logInteractionTrace("SYNC-LOCK", "resize press-frame lock", false);
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
            return;
        }
        if (dragGeometryLockedOnPressFrame()) {
            logInteractionTrace("SYNC-LOCK", "drag press-frame lock", false);
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
            return;
        }
        if (animationPhase === "settled" && userMoveInProgress) {
            logInteractionTrace("SYNC-DRAG", "applyDragInteractionGeometry", false);
            // Keep drag geometry local to the moving content; full-desktop rebases can flash
            // a stale frame on other monitors at drag start.
            applyDragInteractionGeometry();
            return;
        }

        if (animationPhase === "settled" && userResizeInProgress) {
            logInteractionTrace("SYNC-RESIZE", "resize pad=" + Math.max(0, Math.round(glowPadding)), false);
            var dragPad = Math.max(0, Math.round(glowPadding));
            canvasX = Math.round(finalX - dragPad);
            canvasY = Math.round(finalY - dragPad);
            canvasW = Math.max(1, Math.round(finalW + (dragPad * 2)));
            canvasH = Math.max(1, Math.round(finalH + (dragPad * 2)));

            // Active resize should only expand host enough to contain the visible
            // canvas. Adding extra host margin here causes a native-window rebase
            // on the first real resize delta, which reads as a down/up jump.
            ensureHostContainsRect(canvasX, canvasY, canvasW, canvasH, 0, false);

            contentLocalX = Math.round(finalX - canvasX);
            contentLocalY = Math.round(finalY - canvasY);
            canvasLocalX = canvasX - hostX;
            canvasLocalY = canvasY - hostY;
            return;
        }
        contentLocalX = finalX - canvasX;
        contentLocalY = finalY - canvasY;
    }

    function updateDebugOverlayBounds() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            debugBoundsX = usableX;
            debugBoundsY = usableY;
            debugBoundsW = Math.max(1, usableW);
            debugBoundsH = Math.max(1, usableH);
            return;
        }

        var minX = screens[0].virtualX;
        var minY = screens[0].virtualY;
        var maxX = screens[0].virtualX + screens[0].width;
        var maxY = screens[0].virtualY + screens[0].height;
        for (var i = 1; i < screens.length; i++) {
            var s = screens[i];
            minX = Math.min(minX, s.virtualX);
            minY = Math.min(minY, s.virtualY);
            maxX = Math.max(maxX, s.virtualX + s.width);
            maxY = Math.max(maxY, s.virtualY + s.height);
        }

        debugBoundsX = minX;
        debugBoundsY = minY;
        debugBoundsW = Math.max(1, maxX - minX);
        debugBoundsH = Math.max(1, maxY - minY);
    }

    function currentCursorScreenIndex() {
        var idx = 0;
        if (!mainWin.isSettled && mainWin.startupLaunchScreenLocked && mainWin.targetScreenIndex >= 0) {
            idx = mainWin.targetScreenIndex;
        } else if (appRef && appRef.getCursorScreenIndex) {
            idx = appRef.getCursorScreenIndex();
        }
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return 0;
        if (idx < 0 || idx >= screens.length) idx = 0;
        return idx;
    }

    function startupLaunchScreenIndexSafe(fallbackIndex) {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return 0;
        var fallback = (typeof fallbackIndex === "number" && isFinite(fallbackIndex)) ? Math.round(fallbackIndex) : 0;
        if (fallback < 0 || fallback >= screens.length) fallback = 0;

        var idx = mainWin.startupLaunchScreenIndex;
        if (idx < 0 && appRef && appRef.getStartupLaunchScreenIndex) {
            try {
                idx = appRef.getStartupLaunchScreenIndex();
            } catch (e0) {
                idx = -1;
            }
        }
        if (idx < 0 && appRef && appRef.getCursorScreenIndex) {
            try {
                idx = appRef.getCursorScreenIndex();
            } catch (e1) {
                idx = fallback;
            }
        }
        if (idx < 0 || idx >= screens.length) idx = fallback;
        if (idx < 0 || idx >= screens.length) idx = 0;
        mainWin.startupLaunchScreenIndex = idx;
        return idx;
    }

    function primeStartupLaunchScreen(reason) {
        if (mainWin.detachedMode) return false;
        var screens = applicationScreensSafe();
        if (!screens || screens.length <= 0) return false;

        var idx = startupLaunchScreenIndexSafe(0);
        if (idx < 0 || idx >= screens.length) idx = 0;
        mainWin.targetScreenIndex = idx;
        mainWin.targetScreen = screens[idx];
        if (appRef && appRef.getScreenGeometry) {
            mainWin.targetScreenInfo = appRef.getScreenGeometry(idx);
        } else {
            mainWin.targetScreenInfo = null;
        }
        mainWin.startupLaunchScreenLocked = true;
        mainWin.lagLog("primeStartupLaunchScreen reason=" + String(reason || "unspecified")
            + " index=" + idx);
        return true;
    }

    function screenContainsPoint(screenObj, px, py) {
        if (!screenObj) return false;
        var sx = screenObj.virtualX;
        var sy = screenObj.virtualY;
        var sw = screenObj.width;
        var sh = screenObj.height;
        return px >= sx && px < (sx + sw) && py >= sy && py < (sy + sh);
    }

    function screenForPoint(px, py, fallbackScreen) {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return null;
        for (var i = 0; i < screens.length; i++) {
            if (screenContainsPoint(screens[i], px, py)) {
                return screens[i];
            }
        }
        if (fallbackScreen) return fallbackScreen;
        return screens[0];
    }

    function selectScreenFromPythonInfo(screens, info, fallbackIndex) {
        if (!screens || screens.length === 0) {
            return { "screen": null, "index": -1, "reason": "no-screens" };
        }

        if (info && typeof info.x === "number" && typeof info.y === "number"
            && typeof info.w === "number" && typeof info.h === "number") {
            for (var i = 0; i < screens.length; i++) {
                var sExact = screens[i];
                if (!sExact) continue;
                if (sExact.virtualX === info.x && sExact.virtualY === info.y
                    && sExact.width === info.w && sExact.height === info.h) {
                    return { "screen": sExact, "index": i, "reason": "exact-geometry" };
                }
            }

            var cx = info.x + (info.w / 2.0);
            var cy = info.y + (info.h / 2.0);
            for (var j = 0; j < screens.length; j++) {
                var sCenter = screens[j];
                if (screenContainsPoint(sCenter, cx, cy)) {
                    return { "screen": sCenter, "index": j, "reason": "center-point" };
                }
            }

            if (info.name && info.name.length > 0) {
                for (var k = 0; k < screens.length; k++) {
                    var sName = screens[k];
                    if (sName && sName.name === info.name) {
                        return { "screen": sName, "index": k, "reason": "name-match" };
                    }
                }
            }
        }

        var idx = fallbackIndex;
        if (idx < 0 || idx >= screens.length) idx = 0;
        return { "screen": screens[idx], "index": idx, "reason": "fallback-index" };
    }

    function indexOfScreen(screenObj) {
        if (!screenObj) return -1;
        var screens = applicationScreensSafe();
        for (var i = 0; i < screens.length; i++) {
            var s = screens[i];
            if (!s) continue;
            if (s === screenObj) return i;
            if (s.virtualX === screenObj.virtualX && s.virtualY === screenObj.virtualY
                && s.width === screenObj.width && s.height === screenObj.height) {
                return i;
            }
            if (s.name && screenObj.name && s.name === screenObj.name
                && s.virtualX === screenObj.virtualX && s.virtualY === screenObj.virtualY) {
                return i;
            }
        }
        return -1;
    }

    function sameScreen(a, b) {
        if (!a || !b) return false;
        return a.virtualX === b.virtualX && a.virtualY === b.virtualY
            && a.width === b.width && a.height === b.height;
    }

    function enforceWindowScreen(screenObj, reasonTag) {
        if (!screenObj) return false;
        try {
            var before = mainWin.screen;
            if (!mainWin.screen || !sameScreen(mainWin.screen, screenObj)) {
                mainWin.screen = screenObj;
            }
            var pinned = !!(mainWin.screen && sameScreen(mainWin.screen, screenObj));
            if (pinned && (!before || !sameScreen(before, mainWin.screen))) {
                phaseLog("MAIN", "Screen pin reason=" + reasonTag
                    + " target=" + describeScreen(screenObj)
                    + " actual=" + describeScreen(mainWin.screen));
            }
            if (pinned) {
                return true;
            }
            phaseLog("MAIN", "Screen pin mismatch reason=" + reasonTag
                + " target=" + describeScreen(screenObj)
                + " actual=" + describeScreen(mainWin.screen));
        } catch (e) {
            phaseLog("MAIN", "Screen pin failed reason=" + reasonTag + " err=" + e);
            return false;
        }
        return false;
    }

    function contentOwningScreen() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) return null;

        var cx = finalX + (finalW / 2.0);
        var cy = finalY + (finalH / 2.0);
        for (var i = 0; i < screens.length; i++) {
            if (screenContainsPoint(screens[i], cx, cy)) {
                return screens[i];
            }
        }
        if (targetScreen) return targetScreen;
        if (mainWin.screen) return mainWin.screen;
        return screens[0];
    }

    function adjacentScreenForDirection(direction, baseScreen) {
        var dir = (direction < 0) ? -1 : 1;
        var screens = applicationScreensSafe();
        if (!screens || screens.length < 2) return null;

        var current = baseScreen ? baseScreen : contentOwningScreen();
        if (!current) return null;

        var currentCx = current.virtualX + (current.width / 2.0);
        var currentCy = current.virtualY + (current.height / 2.0);
        var best = null;
        var bestScore = 0;
        for (var i = 0; i < screens.length; i++) {
            var s = screens[i];
            if (!s || sameScreen(s, current)) continue;
            var sx = s.virtualX + (s.width / 2.0);
            var sy = s.virtualY + (s.height / 2.0);
            var dx = sx - currentCx;
            if ((dir > 0 && dx <= 0) || (dir < 0 && dx >= 0)) continue;
            var score = Math.abs(dx) * 10000 + Math.abs(sy - currentCy);
            if (!best || score < bestScore) {
                best = s;
                bestScore = score;
            }
        }
        if (best) return best;

        // Fallback ordering when monitors are vertically stacked or share center-X.
        var sorted = screens.slice(0).sort(function(a, b) {
            if (a.virtualX === b.virtualX) {
                return a.virtualY - b.virtualY;
            }
            return a.virtualX - b.virtualX;
        });
        var currentSortedIdx = -1;
        for (var j = 0; j < sorted.length; j++) {
            if (sameScreen(sorted[j], current)) {
                currentSortedIdx = j;
                break;
            }
        }
        if (currentSortedIdx < 0) return null;
        var nextIdx = currentSortedIdx + dir;
        if (nextIdx < 0 || nextIdx >= sorted.length) return null;
        return sorted[nextIdx];
    }

    function adoptTargetScreen(screenObj, skipScreenPin) {
        if (!screenObj) return false;
        var idx = indexOfScreen(screenObj);
        var info = null;
        if (idx >= 0 && appRef && appRef.getScreenGeometry) {
            info = appRef.getScreenGeometry(idx);
        }

        targetScreen = screenObj;
        targetScreenIndex = idx;
        targetScreenInfo = info;

        var vis = visibleRectForScreen(screenObj, info);
        usableX = vis.x;
        usableY = vis.y;
        usableW = vis.w;
        usableH = vis.h;
        if (info) {
            monitorScalePercent = (typeof info.scalePercent === "number")
                ? info.scalePercent
                : ((typeof info.dpr === "number") ? Math.round(info.dpr * 100) : 100);
            taskbarEdge = (typeof info.taskbarEdge === "string") ? info.taskbarEdge : "none";
            taskbarSize = (typeof info.taskbarSize === "number") ? info.taskbarSize : 0;
        } else {
            monitorScalePercent = 100;
            taskbarEdge = "none";
            taskbarSize = 0;
        }
        if (!skipScreenPin) {
            enforceWindowScreen(screenObj, userMoveInProgress ? "drag-monitor-switch" : "adoptTargetScreen");
        }
        refreshActiveVisibleRect();
        return true;
    }

    function hostWindowGeometryDrift() {
        return {
            "dx": Math.round(mainWin.x - hostX),
            "dy": Math.round(mainWin.y - hostY),
            "dw": Math.round(mainWin.width - hostW),
            "dh": Math.round(mainWin.height - hostH)
        };
    }

    function hostWindowOutOfSync(tolerance) {
        var tol = (typeof tolerance === "number") ? Math.max(0, Math.round(tolerance)) : 1;
        var drift = hostWindowGeometryDrift();
        return Math.abs(drift.dx) > tol
            || Math.abs(drift.dy) > tol
            || Math.abs(drift.dw) > tol
            || Math.abs(drift.dh) > tol;
    }

    function reassertHostWindowGeometry(reasonTag) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize) return false;
        if (userMoveInProgress || userResizeInProgress || systemMoveInProgress || dragFinalizePending || dragStrategy !== "none") return false;
        if (!hostWindowOutOfSync(1)) return false;

        var driftBefore = hostWindowGeometryDrift();
        var prevGeomSuppressed = geometryTransitionSuppressed;
        geometryTransitionSuppressed = true;

        // Re-pulse host model properties so QML reapplies host bindings even when
        // the platform asynchronously remapped the window after screen migration.
        var oldHostX = hostX;
        var oldHostY = hostY;
        var oldHostW = hostW;
        var oldHostH = hostH;
        hostX = oldHostX + ((driftBefore.dx !== 0) ? 1 : 0);
        hostY = oldHostY + ((driftBefore.dy !== 0) ? 1 : 0);
        hostW = oldHostW + ((driftBefore.dw !== 0) ? 1 : 0);
        hostH = oldHostH + ((driftBefore.dh !== 0) ? 1 : 0);
        hostX = oldHostX;
        hostY = oldHostY;
        hostW = oldHostW;
        hostH = oldHostH;

        // Re-install explicit bindings in case platform-side geometry writes detached
        // x/y/width/height from their host model expressions.
        mainWin.x = Qt.binding(function() { return mainWin.hostX; });
        mainWin.y = Qt.binding(function() { return mainWin.hostY; });
        mainWin.width = Qt.binding(function() { return mainWin.hostW; });
        mainWin.height = Qt.binding(function() { return mainWin.hostH; });

        geometryTransitionSuppressed = prevGeomSuppressed;
        var driftAfter = hostWindowGeometryDrift();
        phaseLog("MOVE", "Host reassert reason=" + (reasonTag ? reasonTag : "reassert")
            + " driftBefore=" + Math.round(driftBefore.dx) + "," + Math.round(driftBefore.dy)
            + "," + Math.round(driftBefore.dw) + "," + Math.round(driftBefore.dh)
            + " driftAfter=" + Math.round(driftAfter.dx) + "," + Math.round(driftAfter.dy)
            + "," + Math.round(driftAfter.dw) + "," + Math.round(driftAfter.dh)
            + " host=" + fmtRect(hostX, hostY, hostW, hostH)
            + " win=" + fmtRect(Math.round(mainWin.x), Math.round(mainWin.y), Math.round(mainWin.width), Math.round(mainWin.height)));
        return true;
    }

    function scheduleHostReassert(reasonTag) {
        hostReassertReason = reasonTag ? reasonTag : "host-reassert";
        hostReassertAttemptsRemaining = 8;
        if (!hostReassertTimer.running) {
            hostReassertTimer.start();
        }
        reassertHostWindowGeometry(hostReassertReason + "-immediate");
    }

    function moveWindowToAdjacentScreen(direction, sourceSnapshot) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) {
            return false;
        }
        if (adjacentMoveInProgress) {
            return false;
        }
        adjacentMoveInProgress = true;
        var done = function(result) {
            adjacentMoveInProgress = false;
            return !!result;
        };
        if (userMoveInProgress) {
            finishUserDrag();
        }
        if (userResizeInProgress) {
            finishUserResize();
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
            && sourceSnapshot.rectH > 0);

        var srcFinalX = finalX;
        var srcFinalY = finalY;
        var srcFinalW = Math.max(1, finalW);
        var srcFinalH = Math.max(1, finalH);
        var srcRect = activeVisibleRectForMaximize();
        var sourceScreen = contentOwningScreen();

        if (hasSnapshot) {
            srcFinalX = Math.round(sourceSnapshot.finalX);
            srcFinalY = Math.round(sourceSnapshot.finalY);
            srcFinalW = Math.max(1, Math.round(sourceSnapshot.finalW));
            srcFinalH = Math.max(1, Math.round(sourceSnapshot.finalH));
            var hintedRect = {
                "x": Math.round(sourceSnapshot.rectX),
                "y": Math.round(sourceSnapshot.rectY),
                "w": Math.max(1, Math.round(sourceSnapshot.rectW)),
                "h": Math.max(1, Math.round(sourceSnapshot.rectH))
            };
            var hintedScreen = screenForPoint(
                hintedRect.x + (hintedRect.w / 2.0),
                hintedRect.y + (hintedRect.h / 2.0),
                sourceScreen
            );
            sourceScreen = screenForPoint(
                srcFinalX + (srcFinalW / 2.0),
                srcFinalY + (srcFinalH / 2.0),
                hintedScreen
            );
            var sourceIdxFromSnapshot = indexOfScreen(sourceScreen);
            var sourceInfoFromSnapshot = null;
            if (sourceIdxFromSnapshot >= 0 && appRef && appRef.getScreenGeometry) {
                sourceInfoFromSnapshot = appRef.getScreenGeometry(sourceIdxFromSnapshot);
            }
            srcRect = visibleRectForScreen(sourceScreen, sourceInfoFromSnapshot);
            if (!srcRect || srcRect.w <= 0 || srcRect.h <= 0) {
                srcRect = hintedRect;
            }
            phaseLog("MOVE", "Win source snapshot " + fmtRect(srcFinalX, srcFinalY, srcFinalW, srcFinalH)
                + " in " + fmtRect(hintedRect.x, hintedRect.y, hintedRect.w, hintedRect.h)
                + " resolved=" + fmtRect(srcRect.x, srcRect.y, srcRect.w, srcRect.h));
        } else {
            observeContentGlobalPosition();
            updateTargetScreenFromFinalCenter();
            refreshActiveVisibleRect();
            srcFinalX = finalX;
            srcFinalY = finalY;
            srcFinalW = Math.max(1, finalW);
            srcFinalH = Math.max(1, finalH);
            sourceScreen = contentOwningScreen();
            var sourceIdx = indexOfScreen(sourceScreen);
            var sourceInfo = null;
            if (sourceIdx >= 0 && appRef && appRef.getScreenGeometry) {
                sourceInfo = appRef.getScreenGeometry(sourceIdx);
            }
            srcRect = visibleRectForScreen(sourceScreen, sourceInfo);
            if (!srcRect || srcRect.w <= 0 || srcRect.h <= 0) {
                srcRect = activeVisibleRectForMaximize();
            }
        }

        var destScreen = adjacentScreenForDirection(direction, sourceScreen);
        if (!destScreen) {
            phaseLog("MOVE", "No adjacent screen available for direction=" + ((direction < 0) ? "left" : "right"));
            return done(false);
        }

        var destIdx = indexOfScreen(destScreen);
        var destInfo = null;
        if (destIdx >= 0 && appRef && appRef.getScreenGeometry) {
            destInfo = appRef.getScreenGeometry(destIdx);
        }
        var computedDestRect = visibleRectForScreen(destScreen, destInfo);

        if (!adoptTargetScreen(destScreen, true)) {
            return done(false);
        }
        var destRect = computedDestRect;
        if (!destRect || destRect.w <= 0 || destRect.h <= 0) {
            destRect = activeVisibleRectForMaximize();
        }
        if (!destRect || destRect.w <= 0 || destRect.h <= 0) {
            return done(false);
        }

        if (uiMaximized) {
            finalX = Math.round(destRect.x);
            finalY = Math.round(destRect.y);
            finalW = Math.max(1, Math.round(destRect.w));
            finalH = Math.max(1, Math.round(destRect.h));
            phaseLog("MOVE", "Maximized monitor move -> " + fmtRect(finalX, finalY, finalW, finalH));
        } else {
            var minW = ratioToPixels(layoutRatios.resizeMinWidthPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1);
            var minH = ratioToPixels(layoutRatios.resizeMinHeightPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1);
            var remapped = remapWindowGeometryAcrossVisibleRects(
                {
                    "x": srcFinalX,
                    "y": srcFinalY,
                    "w": srcFinalW,
                    "h": srcFinalH
                },
                srcRect,
                destRect,
                minW,
                minH
            );
            if (!remapped) return done(false);

            finalX = remapped.x;
            finalY = remapped.y;
            finalW = remapped.w;
            finalH = remapped.h;
            rememberRestoreGeometry();
            phaseLog("MOVE", "Relative monitor move -> " + fmtRect(finalX, finalY, finalW, finalH)
                + " src=" + fmtRect(srcRect.x, srcRect.y, srcRect.w, srcRect.h)
                + " dst=" + fmtRect(destRect.x, destRect.y, destRect.w, destRect.h)
                + " relCenter=" + remapped.relCenterX.toFixed(3) + "," + remapped.relCenterY.toFixed(3)
                + " relArea=" + remapped.relArea.toFixed(3)
                + " aspect=" + remapped.aspect.toFixed(3));
        }

        // Keep shortcut move behavior aligned with drag cross-monitor behavior:
        // after remap, ensure target screen stays pinned to destination before host/canvas apply.
        updateTargetScreenFromFinalCenter();
        if (!targetScreen || !sameScreen(targetScreen, destScreen)) {
            phaseLog("MOVE", "Post-remap screen drift -> repin destination " + describeScreen(destScreen));
            adoptTargetScreen(destScreen, true);
        }
        resetDragFxState();
        var prevGeomSuppressed = geometryTransitionSuppressed;
        geometryTransitionSuppressed = true;
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        geometryTransitionSuppressed = prevGeomSuppressed;
        enforceWindowScreen(destScreen, "adjacent-move-finalize");
        refreshActiveVisibleRect();
        scheduleHostReassert("adjacent-move-finalize");
        phaseLog("MOVE", "Post-move host=" + fmtRect(hostX, hostY, hostW, hostH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " screen=" + describeScreen(targetScreen ? targetScreen : contentOwningScreen()));
        logCornerForensics("post-move");
        return done(true);
    }

    function updateTargetScreenFromFinalCenter() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            return false;
        }

        var rectX = finalX;
        var rectY = finalY;
        var rectW = finalW;
        var rectH = finalH;
        var chosen = null;
        var chosenIdx = -1;
        var chosenInfo = null;
        var bestArea = -1;

        for (var i = 0; i < screens.length; i++) {
            var s = screens[i];
            if (!s) continue;

            var info = null;
            if (appRef && appRef.getScreenGeometry) {
                info = appRef.getScreenGeometry(i);
            }
            var vis = visibleRectForScreen(s, info);
            var sx = vis.x;
            var sy = vis.y;
            var sw = vis.w;
            var sh = vis.h;

            var ix = Math.max(rectX, sx);
            var iy = Math.max(rectY, sy);
            var ex = Math.min(rectX + rectW, sx + sw);
            var ey = Math.min(rectY + rectH, sy + sh);
            var iw = ex - ix;
            var ih = ey - iy;
            var area = (iw > 0 && ih > 0) ? (iw * ih) : 0;
            if (area > bestArea) {
                bestArea = area;
                chosen = s;
                chosenIdx = i;
                chosenInfo = info;
            }
        }

        if (!chosen || bestArea <= 0) {
            var centerX = rectX + (rectW / 2.0);
            var centerY = rectY + (rectH / 2.0);
            for (var j = 0; j < screens.length; j++) {
                if (screenContainsPoint(screens[j], centerX, centerY)) {
                    chosen = screens[j];
                    chosenIdx = j;
                    break;
                }
            }
        }

        if (!chosen) {
            chosen = targetScreen ? targetScreen : (mainWin.screen ? mainWin.screen : screens[0]);
            chosenIdx = indexOfScreen(chosen);
        }

        if (chosenInfo === null && chosenIdx >= 0 && appRef && appRef.getScreenGeometry) {
            chosenInfo = appRef.getScreenGeometry(chosenIdx);
        }

        if (!chosen) {
            return false;
        }

        var changed = !targetScreen || !sameScreen(targetScreen, chosen);
        targetScreen = chosen;
        if (chosenIdx < 0) {
            chosenIdx = indexOfScreen(chosen);
        }
        if (chosenIdx >= 0) {
            targetScreenIndex = chosenIdx;
            targetScreenInfo = chosenInfo;
        } else {
            targetScreenInfo = null;
        }

        // Keep usable monitor bounds in sync with the active screen selection.
        var chosenRect = visibleRectForScreen(chosen, targetScreenInfo);
        usableX = chosenRect.x;
        usableY = chosenRect.y;
        usableW = chosenRect.w;
        usableH = chosenRect.h;

        if (targetScreenInfo) {
            monitorScalePercent = (typeof targetScreenInfo.scalePercent === "number")
                ? targetScreenInfo.scalePercent
                : ((typeof targetScreenInfo.dpr === "number") ? Math.round(targetScreenInfo.dpr * 100) : 100);
            taskbarEdge = (typeof targetScreenInfo.taskbarEdge === "string")
                ? targetScreenInfo.taskbarEdge : "none";
            taskbarSize = (typeof targetScreenInfo.taskbarSize === "number")
                ? targetScreenInfo.taskbarSize : 0;
        } else {
            monitorScalePercent = 100;
            taskbarEdge = "none";
            taskbarSize = 0;
        }

        if (jelly && mainWin.isSettled) {
            jelly.screenWidth = chosen.width;
            jelly.screenHeight = chosen.height;
        }
        if (changed && userMoveInProgress) {
            phaseLog("DRAG", "Cursor screen -> " + describeScreen(chosen)
                + " usable=" + fmtRect(usableX, usableY, usableW, usableH)
                + " content=" + fmtRect(finalX, finalY, finalW, finalH));
        }
        mainWin.refreshActiveVisibleRect();
        return changed;
    }

    function updateTargetScreenFromHorizontalCenter() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            return false;
        }

        var centerX = finalX + (finalW / 2.0);
        var centerY = finalY + (finalH / 2.0);
        var candidateIndexes = [];
        for (var i = 0; i < screens.length; i++) {
            var screenObj = screens[i];
            if (!screenObj) continue;
            var sx = screenObj.virtualX;
            var sw = screenObj.width;
            if (centerX >= sx && centerX < (sx + sw)) {
                candidateIndexes.push(i);
            }
        }

        var chosen = null;
        if (candidateIndexes.length === 1) {
            chosen = screens[candidateIndexes[0]];
        } else if (candidateIndexes.length > 1) {
            for (var j = 0; j < candidateIndexes.length; j++) {
                var candidate = screens[candidateIndexes[j]];
                if (screenContainsPoint(candidate, centerX, centerY)) {
                    chosen = candidate;
                    break;
                }
            }
            if (!chosen) {
                var bestArea = -1;
                for (var k = 0; k < candidateIndexes.length; k++) {
                    var areaScreen = screens[candidateIndexes[k]];
                    if (!areaScreen) continue;
                    var ix = Math.max(finalX, areaScreen.virtualX);
                    var iy = Math.max(finalY, areaScreen.virtualY);
                    var ex = Math.min(finalX + finalW, areaScreen.virtualX + areaScreen.width);
                    var ey = Math.min(finalY + finalH, areaScreen.virtualY + areaScreen.height);
                    var iw = ex - ix;
                    var ih = ey - iy;
                    var area = (iw > 0 && ih > 0) ? (iw * ih) : 0;
                    if (area > bestArea) {
                        bestArea = area;
                        chosen = areaScreen;
                    }
                }
            }
        }

        if (!chosen) {
            // Gap/stack fallback: keep existing full-center behavior when horizontal-only lookup is ambiguous.
            return updateTargetScreenFromFinalCenter();
        }

        var changed = !targetScreen || !sameScreen(targetScreen, chosen);
        if (!adoptTargetScreen(chosen)) {
            return false;
        }
        if (jelly && mainWin.isSettled) {
            jelly.screenWidth = chosen.width;
            jelly.screenHeight = chosen.height;
        }
        if (changed && userMoveInProgress) {
            phaseLog("DRAG", "Window center-X screen -> " + describeScreen(chosen)
                + " usable=" + fmtRect(usableX, usableY, usableW, usableH)
                + " content=" + fmtRect(finalX, finalY, finalW, finalH));
        }
        return changed;
    }

    function updateTargetScreenFromCursor() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            return false;
        }
        var cursorIdx = currentCursorScreenIndex();
        var cursorInfo = null;
        if (appRef && appRef.getScreenGeometry) {
            cursorInfo = appRef.getScreenGeometry(cursorIdx);
        }
        var picked = selectScreenFromPythonInfo(screens, cursorInfo, cursorIdx);
        var chosen = picked.screen;
        var chosenIdx = picked.index;
        if (!chosen) {
            if (cursorIdx >= 0 && cursorIdx < screens.length) {
                chosen = screens[cursorIdx];
                chosenIdx = cursorIdx;
            } else {
                chosen = screens[0];
                chosenIdx = 0;
            }
        }

        var changed = !targetScreen || !sameScreen(targetScreen, chosen);
        targetScreen = chosen;
        if (chosenIdx < 0) {
            chosenIdx = indexOfScreen(chosen);
        }
        targetScreenIndex = chosenIdx;

        var chosenInfo = null;
        if (chosenIdx >= 0 && appRef && appRef.getScreenGeometry) {
            chosenInfo = appRef.getScreenGeometry(chosenIdx);
        }
        targetScreenInfo = chosenInfo;

        var chosenRect = visibleRectForScreen(chosen, targetScreenInfo);
        usableX = chosenRect.x;
        usableY = chosenRect.y;
        usableW = chosenRect.w;
        usableH = chosenRect.h;

        if (targetScreenInfo) {
            monitorScalePercent = (typeof targetScreenInfo.scalePercent === "number")
                ? targetScreenInfo.scalePercent
                : ((typeof targetScreenInfo.dpr === "number") ? Math.round(targetScreenInfo.dpr * 100) : 100);
            taskbarEdge = (typeof targetScreenInfo.taskbarEdge === "string")
                ? targetScreenInfo.taskbarEdge : "none";
            taskbarSize = (typeof targetScreenInfo.taskbarSize === "number")
                ? targetScreenInfo.taskbarSize : 0;
        } else {
            monitorScalePercent = 100;
            taskbarEdge = "none";
            taskbarSize = 0;
        }

        if (jelly && mainWin.isSettled) {
            jelly.screenWidth = chosen.width;
            jelly.screenHeight = chosen.height;
        }
        if (changed && userMoveInProgress) {
            phaseLog("DRAG", "Cursor screen idx=" + chosenIdx
                + " " + describeScreen(chosen)
                + " usable=" + fmtRect(usableX, usableY, usableW, usableH));
        }
        mainWin.refreshActiveVisibleRect();
        return changed;
    }

    function refreshActiveVisibleRect() {
        activeVisibleRect = activeMonitorVisibleRect();
    }

    function activeMonitorVisibleRect() {
        if (userResizeInProgress
            && dragMonitorVisibleRect
            && dragMonitorVisibleRect.w > 0
            && dragMonitorVisibleRect.h > 0) {
            return dragMonitorVisibleRect;
        }

        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            return { "x": 0, "y": 0, "w": 1, "h": 1 };
        }

        var screenObj = targetScreen;
        if (!screenObj) {
            var centerX = finalX + (finalW / 2.0);
            var centerY = finalY + (finalH / 2.0);
            for (var i = 0; i < screens.length; i++) {
                var s = screens[i];
                if (screenContainsPoint(s, centerX, centerY)) {
                    screenObj = s;
                    break;
                }
            }
            if (!screenObj && mainWin.screen) {
                screenObj = mainWin.screen;
            }
            if (!screenObj) {
                screenObj = screens[0];
            }
        }

        var infoObj = (targetScreen && sameScreen(screenObj, targetScreen)) ? targetScreenInfo : null;
        var rect = visibleRectForScreen(screenObj, infoObj);
        var rectX = rect.x;
        var rectY = rect.y;
        var rectW = rect.w;
        var rectH = rect.h;

        if (usableW > 0 && usableH > 0 && targetScreen && sameScreen(screenObj, targetScreen)) {
            rectX = usableX;
            rectY = usableY;
            rectW = usableW;
            rectH = usableH;
        }

        return {
            "x": Math.round(rectX),
            "y": Math.round(rectY),
            "w": Math.max(1, Math.round(rectW)),
            "h": Math.max(1, Math.round(rectH))
        };
    }

    function remapDragGeometryForMonitorSwitch(sourceRect) {
        if (!sourceRect || sourceRect.w <= 0 || sourceRect.h <= 0) {
            return false;
        }

        var destRect = activeVisibleRect;
        if (!destRect || destRect.w <= 0 || destRect.h <= 0) {
            destRect = activeVisibleRectForMaximize();
        }
        if (!destRect || destRect.w <= 0 || destRect.h <= 0) {
            return false;
        }

        if (uiMaximized) {
            finalX = Math.round(destRect.x);
            finalY = Math.round(destRect.y);
            finalW = Math.max(1, Math.round(destRect.w));
            finalH = Math.max(1, Math.round(destRect.h));
            return true;
        }

        var minW = ratioToPixels(layoutRatios.resizeMinWidthPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1);
        var minH = ratioToPixels(layoutRatios.resizeMinHeightPct, Math.max(1, destRect.w), Math.max(1, destRect.h), 1);
        var remapped = remapWindowGeometryAcrossVisibleRects(
            {
                "x": finalX,
                "y": finalY,
                "w": finalW,
                "h": finalH
            },
            sourceRect,
            destRect,
            minW,
            minH
        );
        if (!remapped) return false;

        finalX = remapped.x;
        finalY = remapped.y;
        finalW = remapped.w;
        finalH = remapped.h;
        phaseLog("DRAG", "Relative monitor remap -> " + fmtRect(finalX, finalY, finalW, finalH)
            + " from " + fmtRect(sourceRect.x, sourceRect.y, sourceRect.w, sourceRect.h)
            + " to " + fmtRect(destRect.x, destRect.y, destRect.w, destRect.h)
            + " relCenter=" + remapped.relCenterX.toFixed(3) + "," + remapped.relCenterY.toFixed(3)
            + " relArea=" + remapped.relArea.toFixed(3)
            + " aspect=" + remapped.aspect.toFixed(3));
        return true;
    }

    function clampFinalGeometryToRect(rect) {
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            return false;
        }

        var rectX = Math.round(rect.x);
        var rectY = Math.round(rect.y);
        var rectW = Math.max(1, Math.round(rect.w));
        var rectH = Math.max(1, Math.round(rect.h));

        var nextW = Math.max(1, Math.min(Math.round(finalW), rectW));
        var nextH = Math.max(1, Math.min(Math.round(finalH), rectH));

        var minX = rectX;
        var maxX = rectX + rectW - nextW;
        var minY = rectY;
        var maxY = rectY + rectH - nextH;

        var nextX = Math.round(clampNumber(finalX, Math.min(minX, maxX), Math.max(minX, maxX)));
        var nextY = Math.round(clampNumber(finalY, Math.min(minY, maxY), Math.max(minY, maxY)));
        if (nextX === finalX && nextY === finalY && nextW === finalW && nextH === finalH) {
            return false;
        }

        finalX = nextX;
        finalY = nextY;
        finalW = Math.max(1, Math.round(nextW));
        finalH = Math.max(1, Math.round(nextH));
        return true;
    }

    function enforceNoClipWithinActiveMonitor() {
        var rect = activeVisibleRect;
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = activeVisibleRectForMaximize();
        }
        return clampFinalGeometryToRect(rect);
    }

    function observedContentGlobalPosition() {
        // During live/just-finished native drag, trust actual window coordinates first.
        // hostX/hostY can lag one tick and cause release-time misprojection.
        var preferAnimatedHost = userMoveInProgress || systemMoveInProgress || dragFinalizePending;
        var stableHostX = preferAnimatedHost
            ? Math.round(mainWin.x)
            : (isFinite(hostX) ? Math.round(hostX) : Math.round(mainWin.x));
        var stableHostY = preferAnimatedHost
            ? Math.round(mainWin.y)
            : (isFinite(hostY) ? Math.round(hostY) : Math.round(mainWin.y));
        var observedFinalX = Math.round(stableHostX + canvasLocalX + contentLocalX);
        var observedFinalY = Math.round(stableHostY + canvasLocalY + contentLocalY);
        var animatedObservedX = Math.round(mainWin.x + canvasLocalX + contentLocalX);
        var animatedObservedY = Math.round(mainWin.y + canvasLocalY + contentLocalY);
        return {
            "valid": isFinite(observedFinalX) && isFinite(observedFinalY),
            "x": observedFinalX,
            "y": observedFinalY,
            "animatedX": animatedObservedX,
            "animatedY": animatedObservedY
        };
    }

    function observeContentGlobalPosition() {
        var observed = observedContentGlobalPosition();
        if (!observed.valid) {
            return false;
        }
        finalX = observed.x;
        finalY = observed.y;
        return true;
    }

    function readCursorGlobalPos() {
        if (appRef && appRef.getCursorGlobalPos) {
            var pos = appRef.getCursorGlobalPos();
            if (pos
                && typeof pos.x === "number"
                && typeof pos.y === "number"
                && isFinite(pos.x)
                && isFinite(pos.y)) {
                return {
                    "x": pos.x,
                    "y": pos.y
                };
            }
        }
        return null;
    }

    function applyFallbackDragFromCursor() {
        if (!userMoveInProgress || dragStrategy !== "fallback") return false;
        var pos = readCursorGlobalPos();
        if (!pos) return false;
        if (!dragHasCursorAnchor) {
            dragStartCursorX = pos.x;
            dragStartCursorY = pos.y;
            dragStartFinalX = finalX;
            dragStartFinalY = finalY;
            dragHasCursorAnchor = true;
            return true;
        }

        var dx = pos.x - dragStartCursorX;
        var dy = pos.y - dragStartCursorY;
        if (!isFinite(dx) || !isFinite(dy)) return false;

        var nextFinalX = Math.round(dragStartFinalX + dx);
        var nextFinalY = Math.round(dragStartFinalY + dy);
        if (nextFinalX === finalX && nextFinalY === finalY) {
            dragStartCursorX = pos.x;
            dragStartCursorY = pos.y;
            dragStartFinalX = finalX;
            dragStartFinalY = finalY;
            return true;
        }

        dragHasRealDelta = true;
        var sourceRect = activeVisibleRect;
        if (!sourceRect || sourceRect.w <= 0 || sourceRect.h <= 0) {
            sourceRect = activeVisibleRectForMaximize();
        }
        if (sourceRect && sourceRect.w > 0 && sourceRect.h > 0) {
            sourceRect = {
                "x": Math.round(sourceRect.x),
                "y": Math.round(sourceRect.y),
                "w": Math.max(1, Math.round(sourceRect.w)),
                "h": Math.max(1, Math.round(sourceRect.h))
            };
        } else {
            sourceRect = null;
        }

        finalX = nextFinalX;
        finalY = nextFinalY;
        var screenChanged = updateTargetScreenFromHorizontalCenter();
        refreshActiveVisibleRect();
        if (screenChanged) {
            if (sourceRect) {
                remapDragGeometryForMonitorSwitch(sourceRect);
            }
            // Keep drag anchored to absolute cursor movement; do not side-shift on monitor hop.
            geometryTransitionSuppressed = true;
            updateCanvasGeometry();
            geometryTransitionSuppressed = false;
        }
        applyDragFxFromDelta(dx, dy);
        syncDragContentPosition();

        dragAccumFinalX = finalX;
        dragAccumFinalY = finalY;
        dragStartCursorX = pos.x;
        dragStartCursorY = pos.y;
        dragStartFinalX = finalX;
        dragStartFinalY = finalY;
        dragForensicFrame = dragForensicFrame + 1;
        if (screenChanged) {
            logDragForensic("Switch anchor", pos);
            dragTrace("screen-switch", "cursor=" + Math.round(pos.x) + "," + Math.round(pos.y));
        }
        phaseMonitorLog("DRAG", dragForensicFrame,
            "cursor=" + Math.round(pos.x) + "," + Math.round(pos.y)
            + " green=" + fmtRect(activeVisibleRect.x, activeVisibleRect.y, activeVisibleRect.w, activeVisibleRect.h)
            + " orange=" + fmtRect(canvasX, canvasY, canvasW, canvasH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH));

        return true;
    }

    function applyHostEnvelopeForTarget() {
        var rect = activeVisibleRect;
        if (usableW > 0 && usableH > 0) {
            rect = {
                "x": usableX,
                "y": usableY,
                "w": usableW,
                "h": usableH
            };
        }
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            return;
        }

        var refW = Math.max(1, rect.w);
        var refH = Math.max(1, rect.h);
        var safeFinalW = Math.max(1, finalW);
        var safeFinalH = Math.max(1, finalH);

        // Opening uses a screen-sized host. The drop may begin offscreen, but the
        // visible part should never depend on a giant negative-Y native window.
        if (!mainWin.detachedMode && (mainWin.animationPhase === "opening" || mainWin.startupPhase === "falling-window")) {
            var openingHost = openingHostBaseRect(rect);
            hostX = Math.round(openingHost.x);
            hostY = Math.round(openingHost.y);
            hostW = Math.max(1, Math.round(openingHost.w));
            hostH = Math.max(1, Math.round(openingHost.h));
            return;
        }

        if (mainWin.animationPhase === "closing") {
            applyHostEnvelopeForClosing();
            return;
        }

        // Maximize uses monitor-sized envelope
        if (mainWin.maximizeAnimInProgress || uiMaximized) {
            hostX = Math.round(rect.x);
            hostY = Math.round(rect.y);
            hostW = Math.max(1, Math.round(rect.w));
            hostH = Math.max(1, Math.round(rect.h));
            return;
        }

        // Normal and detached settled windows must be no larger than their
        // visible canvas. This is an input boundary, not just a rendering one.
        var canvasPad = settledHostPaddingPx(refW, refH);
        hostX = Math.round(finalX - canvasPad);
        hostY = Math.round(finalY - canvasPad);
        hostW = Math.max(1, Math.round(safeFinalW + (canvasPad * 2)));
        hostH = Math.max(1, Math.round(safeFinalH + (canvasPad * 2)));
    }


    function ensureHostContainsRect(rectX, rectY, rectW, rectH, padPx, allowShrink) {
        // Frame-0 guard: do NOT rebase host on the exact press frame.
        // The OS window must stay put until real mouse movement occurs.
        if (mainWin.resizeGeometryLockedOnPressFrame()) {
            logInteractionTrace("ENSURE-HOST-LOCK", "resize press-frame rect=" + fmtRect(rectX, rectY, rectW, rectH), false);
            return false;
        }
        if (mainWin.dragGeometryLockedOnPressFrame()) {
            logInteractionTrace("ENSURE-HOST-LOCK", "drag press-frame rect=" + fmtRect(rectX, rectY, rectW, rectH), false);
            return false;
        }
        var safePad = Math.max(0, Math.round(padPx));
        var neededX = Math.round(rectX - safePad);
        var neededY = Math.round(rectY - safePad);
        var neededR = Math.round(rectX + rectW + safePad);
        var neededB = Math.round(rectY + rectH + safePad);

        var curX = Math.round(hostX);
        var curY = Math.round(hostY);
        var curR = Math.round(hostX + hostW);
        var curB = Math.round(hostY + hostH);

        var shrink = !!allowShrink;
        var nextX = shrink ? neededX : Math.min(curX, neededX);
        var nextY = shrink ? neededY : Math.min(curY, neededY);
        var nextR = shrink ? neededR : Math.max(curR, neededR);
        var nextB = shrink ? neededB : Math.max(curB, neededB);

        var nextW = Math.max(1, Math.round(nextR - nextX));
        var nextH = Math.max(1, Math.round(nextB - nextY));
        if (nextX === hostX && nextY === hostY && nextW === hostW && nextH === hostH) {
            logInteractionTrace("ENSURE-HOST-NOOP",
                "rect=" + fmtRect(rectX, rectY, rectW, rectH)
                + " pad=" + safePad
                + " shrink=" + (shrink ? "1" : "0"),
                false);
            return false;
        }

        logInteractionTrace("ENSURE-HOST-APPLY",
            "rect=" + fmtRect(rectX, rectY, rectW, rectH)
            + " pad=" + safePad
            + " shrink=" + (shrink ? "1" : "0")
            + " next=" + fmtRect(nextX, nextY, nextW, nextH),
            false);
        hostX = nextX;
        hostY = nextY;
        hostW = nextW;
        hostH = nextH;
        return true;
    }

    function rememberRestoreGeometry() {
        if (animationPhase !== "settled" || isClosing || uiMaximized) return;
        if (!isFinite(finalX) || !isFinite(finalY) || !isFinite(finalW) || !isFinite(finalH)) return;
        if (finalW < 2 || finalH < 2) return;
        restoreFinalX = Math.round(finalX);
        restoreFinalY = Math.round(finalY);
        restoreFinalW = Math.max(1, Math.round(finalW));
        restoreFinalH = Math.max(1, Math.round(finalH));
        restoreGeometryValid = true;
    }

    function activeVisibleRectForMaximize() {
        if (usableW > 0 && usableH > 0) {
            return {
                "x": usableX,
                "y": usableY,
                "w": usableW,
                "h": usableH
            };
        }
        var rect = activeMonitorVisibleRect();
        if (!rect || rect.w <= 0 || rect.h <= 0) {
            rect = {
                "x": finalX,
                "y": finalY,
                "w": Math.max(1, finalW),
                "h": Math.max(1, finalH)
            };
        }
        return rect;
    }

    function topEdgeSnapTargetForDragRelease() {
        if (!userMoveInProgress || uiMaximized) return null;
        var screens = applicationScreensSafe();
        if (!screens || screens.length <= 0) return null;

        var winLeft = Math.round(finalX);
        var winTop = Math.round(finalY);
        var winRight = Math.round(finalX + finalW);
        var winBottom = Math.round(finalY + finalH);

        var framePad = Math.max(1, Math.ceil(Math.max(monitorFrameThickness, monitorFrameGlowThickness * 0.50)));
        var best = null;
        var bestOverlapW = 0;
        for (var i = 0; i < screens.length; i++) {
            var screenObj = screens[i];
            if (!screenObj) continue;

            var infoObj = null;
            if (appRef && appRef.getScreenGeometry) {
                infoObj = appRef.getScreenGeometry(i);
            }
            var rect = visibleRectForScreen(screenObj, infoObj);
            if (!rect || rect.w <= 0 || rect.h <= 0) continue;

            var rectLeft = Math.round(rect.x);
            var rectTop = Math.round(rect.y);
            var rectRight = Math.round(rectLeft + rect.w);
            var topBandMin = rectTop - framePad;
            var topBandMax = rectTop + framePad;
            var overlapW = Math.min(winRight, rectRight) - Math.max(winLeft, rectLeft);
            if (overlapW <= 0) continue;
            if (winTop > topBandMax || winBottom < topBandMin) continue;
            if (!best || overlapW > bestOverlapW) {
                best = { "screen": screenObj, "index": i, "info": infoObj, "rect": rect };
                bestOverlapW = overlapW;
            }
        }
        return best;
    }

    function shouldSnapMaximizeOnDragRelease() {
        return topEdgeSnapTargetForDragRelease() !== null;
    }

    function maximizeWindowToVisibleRect(screenOverride) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        logGreenFrameGeometry("MAXIMIZE", "Pre-maximize snapshot");
        var sourceX = Math.round(finalX);
        var sourceY = Math.round(finalY);
        var sourceW = Math.max(1, Math.round(finalW));
        var sourceH = Math.max(1, Math.round(finalH));
        if (screenOverride) {
            adoptTargetScreen(screenOverride);
        } else {
            updateTargetScreenFromFinalCenter();
        }
        refreshActiveVisibleRect();
        logGreenFrameGeometry("MAXIMIZE", "Post-screen-refresh snapshot");
        var rect = activeVisibleRectForMaximize();
        if (!rect || rect.w <= 0 || rect.h <= 0) return false;

        phaseLog("MAXIMIZE", "Start maximize from " + fmtRect(finalX, finalY, finalW, finalH)
            + " -> " + fmtRect(rect.x, rect.y, rect.w, rect.h));
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.74);
        }
        uiMaximized = true;
        resetMaximizeFxState();
        geometryTransitionSuppressed = true;
        finalX = Math.round(rect.x);
        finalY = Math.round(rect.y);
        finalW = Math.max(1, Math.round(rect.w));
        finalH = Math.max(1, Math.round(rect.h));
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();

        if (appStyle !== "Professional") {
            maximizeAnimInProgress = true;
            maximizeMonitorFrame = 0;
            seedMaximizeFxFromSourceRect(sourceX, sourceY, sourceW, sourceH);
            maximizeFxAnimation.restart();
        } else {
            maximizeAnimInProgress = false;
        }

        Qt.callLater(function() {
            mainWin.geometryTransitionSuppressed = false;
        });
        return true;
    }

    function defaultRestoreRect() {
        var rect = activeVisibleRectForMaximize();
        var aspect = (typeof layoutRatios.contentAspect === "number" && layoutRatios.contentAspect > 0.01)
            ? layoutRatios.contentAspect : (1220.0 / 920.0);
        var h = Math.max(1, Math.round(rect.h * layoutRatios.contentHeightPct));
        var w = Math.max(1, Math.round(h * aspect));
        if (w > rect.w) {
            w = rect.w;
            h = Math.max(1, Math.round(w / aspect));
        }
        if (h > rect.h) {
            h = rect.h;
            w = Math.max(1, Math.round(h * aspect));
        }
        return {
            "x": Math.round(rect.x + ((rect.w - w) / 2)),
            "y": Math.round(rect.y + ((rect.h - h) / 2)),
            "w": Math.max(1, Math.round(w)),
            "h": Math.max(1, Math.round(h))
        };
    }

    function resolveRestoreRectFromMaximized(cursorPos, cursorAnchored) {
        var restoreRect = restoreGeometryValid
            ? { "x": restoreFinalX, "y": restoreFinalY, "w": restoreFinalW, "h": restoreFinalH }
            : defaultRestoreRect();

        var nextX = restoreRect.x;
        var nextY = restoreRect.y;
        var nextW = restoreRect.w;
        var nextH = restoreRect.h;

        if (cursorAnchored && cursorPos && isFinite(cursorPos.x) && isFinite(cursorPos.y)) {
            var vis = activeVisibleRectForMaximize();
            var ratioX = 0.5;
            if (vis && vis.w > 0) {
                ratioX = clampNumber((cursorPos.x - vis.x) / vis.w, 0.10, 0.90);
            }
            nextX = Math.round(cursorPos.x - (nextW * ratioX));
            nextY = Math.round(cursorPos.y - Math.max(1, Math.round(titleBarHeightPx() * 0.50)));
        }

        return {
            "x": Math.round(nextX),
            "y": Math.round(nextY),
            "w": Math.max(1, Math.round(nextW)),
            "h": Math.max(1, Math.round(nextH))
        };
    }

    function restoreFromMaximized(cursorPos, cursorAnchored) {
        if (!uiMaximized || maximizeAnimInProgress) return false;
        var sourceX = Math.round(finalX);
        var sourceY = Math.round(finalY);
        var sourceW = Math.max(1, Math.round(finalW));
        var sourceH = Math.max(1, Math.round(finalH));

        var targetRect = resolveRestoreRectFromMaximized(cursorPos, cursorAnchored);
        var nextX = targetRect.x;
        var nextY = targetRect.y;
        var nextW = targetRect.w;
        var nextH = targetRect.h;

        phaseLog("RESTORE-MAX", "Start restore from maximized to " + fmtRect(nextX, nextY, nextW, nextH)
            + " cursorAnchored=" + (cursorAnchored ? "yes" : "no"));
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.62);
        }
        uiMaximized = false;
        resetMaximizeFxState();
        geometryTransitionSuppressed = true;
        finalX = Math.round(nextX);
        finalY = Math.round(nextY);
        finalW = Math.max(1, Math.round(nextW));
        finalH = Math.max(1, Math.round(nextH));
        updateTargetScreenFromFinalCenter();
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();

        if (appStyle !== "Professional") {
            maximizeAnimInProgress = true;
            restoreMaxMonitorFrame = 0;
            seedMaximizeFxFromSourceRect(sourceX, sourceY, sourceW, sourceH);
            maximizeRestoreFxAnimation.restart();
        } else {
            maximizeAnimInProgress = false;
        }

        Qt.callLater(function() {
            mainWin.geometryTransitionSuppressed = false;
        });
        return true;
    }

    function restoreFromMaximizedForDrag(cursorPos) {
        if (!uiMaximized || maximizeAnimInProgress) return false;
        var targetRect = resolveRestoreRectFromMaximized(cursorPos, true);
        phaseLog("RESTORE-MAX", "Drag restore from maximized to "
            + fmtRect(targetRect.x, targetRect.y, targetRect.w, targetRect.h));
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.58);
        }

        stopMaximizeFxAnimations();
        uiMaximized = false;
        geometryTransitionSuppressed = true;
        finalX = targetRect.x;
        finalY = targetRect.y;
        finalW = targetRect.w;
        finalH = targetRect.h;
        updateTargetScreenFromFinalCenter();
        refreshActiveVisibleRect();
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        geometryTransitionSuppressed = false;
        return true;
    }

    function seedMaximizeFxFromSourceRect(sourceX, sourceY, sourceW, sourceH) {
        var targetW = Math.max(1, Math.round(finalW));
        var targetH = Math.max(1, Math.round(finalH));
        var targetX = Math.round(contentLocalX);
        var targetY = Math.round(contentLocalY);
        var sourceLocalX = Math.round(sourceX - canvasX);
        var sourceLocalY = Math.round(sourceY - canvasY);
        var sourceLocalW = Math.max(1, Math.round(sourceW));
        var sourceLocalH = Math.max(1, Math.round(sourceH));

        var sx = sourceLocalW / targetW;
        var sy = sourceLocalH / targetH;

        // Maximize pivot is top-right so growth reads as expanding toward the monitor's top-right corner.
        var ox = targetX + targetW;
        var oy = targetY;
        var tx = sourceLocalX - ((sx * targetX) + ((1.0 - sx) * ox));
        var ty = sourceLocalY - ((sy * targetY) + ((1.0 - sy) * oy));

        maximizeFxScaleX = sx;
        maximizeFxScaleY = sy;
        maximizeFxTransX = tx;
        maximizeFxTransY = ty;
        maximizeFxRotate = 0.0;
        phaseLog("MAXIMIZE", "FX seeded from source="
            + fmtRect(sourceX, sourceY, sourceW, sourceH)
            + " target=" + fmtRect(finalX, finalY, finalW, finalH)
            + " fx=" + sx.toFixed(3) + "x" + sy.toFixed(3)
            + "@" + tx.toFixed(1) + "," + ty.toFixed(1));
    }

    function toggleWindowMaximize() {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        if (userMoveInProgress || userResizeInProgress || systemMoveInProgress) return false;
        if (uiMaximized) {
            phaseLog("RESTORE-MAX", "Toggle requested -> restore from maximized");
            var restored = restoreFromMaximized(null, false);
            if (restored && !mainWin.detachedMode) {
                persistMainWindowLayout();
            }
            return restored;
        }
        phaseLog("MAXIMIZE", "Toggle requested -> maximize");
        rememberRestoreGeometry();
        var maximized = maximizeWindowToVisibleRect();
        if (maximized && !mainWin.detachedMode) {
            persistMainWindowLayout();
        }
        return maximized;
    }

    function beginHeaderDrag(preDragX, preDragY) {
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        if (uiMaximized) {
            // Windows-style behavior: only trigger restore-on-drag when movement is downward.
            if (typeof preDragY === "number" && preDragY <= 0) {
                return false;
            }
            var cursorPos = readCursorGlobalPos();
            if (!restoreFromMaximizedForDrag(cursorPos)) {
                return false;
            }
        }
        var beginOk = beginUserDrag();
        // Fallback drag path returns false by contract even when drag state is active.
        return beginOk || userMoveInProgress;
    }

    function beginUserDrag() {
        // Drag pipeline contract anchor for Option 3:
        // docs/DECISIONS/DRAG_PIPELINE_OPTION3.md
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        if (userResizeInProgress) return false;
        beginInteractionTrace("drag", "beginUserDrag");
        logInteractionTrace("BEGIN-DRAG", "entry", true);

        // Suppress geometry Behavior animations before any state change
        // to prevent Frame-0 easing slide on the press event.
        geometryTransitionSuppressed = true;
        userMoveInProgress = true;
        systemMoveInProgress = false;
        dragStrategy = "none";
        dragStartHostX = x;
        dragStartHostY = y;

        observeContentGlobalPosition();
        dragStartFinalX = finalX;
        dragStartFinalY = finalY;
        dragStartCursorX = 0;
        dragStartCursorY = 0;
        dragHasCursorAnchor = false;
        dragHasRealDelta = false;
        dragLastTranslationX = 0;
        dragLastTranslationY = 0;
        dragAccumHostX = x;
        dragAccumHostY = y;
        dragAccumFinalX = finalX;
        dragAccumFinalY = finalY;
        dragForensicFrame = 0;
        beginDragFxTracking();
        var cursorPos = readCursorGlobalPos();
        if (cursorPos) {
            dragStartCursorX = cursorPos.x;
            dragStartCursorY = cursorPos.y;
            dragHasCursorAnchor = true;
        }

        if (activeVisibleRect && activeVisibleRect.w > 0 && activeVisibleRect.h > 0) {
            dragMonitorVisibleRect = {
                "x": activeVisibleRect.x,
                "y": activeVisibleRect.y,
                "w": activeVisibleRect.w,
                "h": activeVisibleRect.h
            };
        }
        updateDebugOverlayBounds();
        logDragForensic("Begin drag", cursorPos);
        dragTrace("begin", "cursor=" + (cursorPos ? (Math.round(cursorPos.x) + "," + Math.round(cursorPos.y)) : "<none>"));

        if (allowNativeSystemDrag) {
            var nativeStarted = true;
            try {
                var moveResult = startSystemMove();
                if (typeof moveResult === "boolean") {
                    nativeStarted = moveResult;
                }
            } catch (e) {
                nativeStarted = false;
            }

            if (nativeStarted) {
                systemMoveInProgress = true;
                dragStrategy = "native";
                return true;
            }
        }

        // Controlled drag path: no OS clamp, so user can place the window anywhere.
        systemMoveInProgress = false;
        dragStrategy = "fallback";
        // Do not rebase host/canvas to full-desktop until the first real move delta.
        // Immediate rebase on press can cause a one-frame stale-window flash on another monitor.
        dragTrace("fallback-start", "polling=" + (dragPollingEnabled ? "on" : "off"));
        return false;
    }

    function updateUserDrag(translationX, translationY) {
        if (!userMoveInProgress || dragStrategy !== "fallback") return;
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return;
        var hasTranslation = isFinite(translationX) && isFinite(translationY);
        if (preferTranslationDrag && !hasTranslation) return;
        var useTranslation = preferTranslationDrag && hasTranslation;
        if (!useTranslation) {
            if (applyFallbackDragFromCursor()) {
                dragLastTranslationX = isFinite(translationX) ? translationX : dragLastTranslationX;
                dragLastTranslationY = isFinite(translationY) ? translationY : dragLastTranslationY;
                return;
            }
        }

        var tx = isFinite(translationX) ? translationX : dragLastTranslationX;
        var ty = isFinite(translationY) ? translationY : dragLastTranslationY;
        var dx = tx - dragLastTranslationX;
        var dy = ty - dragLastTranslationY;
        dragLastTranslationX = tx;
        dragLastTranslationY = ty;
        if (!isFinite(dx) || !isFinite(dy)) return;
        if (dx === 0 && dy === 0) return;

        dragHasRealDelta = true;
        var sourceRect = activeVisibleRect;
        if (!sourceRect || sourceRect.w <= 0 || sourceRect.h <= 0) {
            sourceRect = activeVisibleRectForMaximize();
        }
        if (sourceRect && sourceRect.w > 0 && sourceRect.h > 0) {
            sourceRect = {
                "x": Math.round(sourceRect.x),
                "y": Math.round(sourceRect.y),
                "w": Math.max(1, Math.round(sourceRect.w)),
                "h": Math.max(1, Math.round(sourceRect.h))
            };
        } else {
            sourceRect = null;
        }

        finalX = Math.round(finalX + dx);
        finalY = Math.round(finalY + dy);
        var screenChanged = updateTargetScreenFromHorizontalCenter();
        refreshActiveVisibleRect();
        if (screenChanged) {
            if (sourceRect) {
                remapDragGeometryForMonitorSwitch(sourceRect);
            }
            geometryTransitionSuppressed = true;
            updateCanvasGeometry();
            geometryTransitionSuppressed = false;
            dragTrace("screen-switch", "translation-fallback");
        }
        applyDragFxFromDelta(dx, dy);
        syncDragContentPosition();
    }

    function beginUserResize(handle) {
        if (!strictResizePipelineEnabled) return false;
        if (animationPhase !== "settled" || isClosing || isMinimizing || isRestoringFromMinimize || maximizeAnimInProgress) return false;
        if (uiMaximized) return false;
        if (userMoveInProgress || systemMoveInProgress) return false;
        if (!isResizeHandleValid(handle)) return false;
        beginInteractionTrace("resize:" + handle, "beginUserResize");
        logInteractionTrace("BEGIN-RESIZE", "handle=" + handle, true);

        observeContentGlobalPosition();

        // Suppress geometry Behavior animations before any state change
        // to prevent Frame-0 easing slide on the press event.
        geometryTransitionSuppressed = true;
        resizeMonitorFrame = 0;
        resizeHandle = handle;
        resizeStartFinalX = finalX;
        resizeStartFinalY = finalY;
        resizeStartFinalW = finalW;
        resizeStartFinalH = finalH;
        resizeStartCursorX = 0;
        resizeStartCursorY = 0;
        resizeHasCursorAnchor = false;
        resizeHasRealDelta = false;
        userResizeInProgress = true;

        var cursorPos = resizeLiveCursorIsFresh()
            ? { "x": resizeLiveCursorX, "y": resizeLiveCursorY }
            : readCursorGlobalPos();
        if (cursorPos) {
            resizeStartCursorX = cursorPos.x;
            resizeStartCursorY = cursorPos.y;
            resizeHasCursorAnchor = true;
        }

        if (activeVisibleRect && activeVisibleRect.w > 0 && activeVisibleRect.h > 0) {
            dragMonitorVisibleRect = {
                "x": activeVisibleRect.x,
                "y": activeVisibleRect.y,
                "w": activeVisibleRect.w,
                "h": activeVisibleRect.h
            };
        }

        // Keep the host anchored during resize-start.
        // Re-basing host to a desktop envelope here can produce visible teleport on multi-monitor setups.
        syncDragContentPosition();
        phaseLog("RESIZE", "Begin handle=" + handle + " start=" + fmtRect(resizeStartFinalX, resizeStartFinalY, resizeStartFinalW, resizeStartFinalH));
        return true;
    }

    function updateUserResize(translationX, translationY) {
        if (!strictResizePipelineEnabled) return;
        if (!userResizeInProgress || animationPhase !== "settled" || isClosing) return;

        var dx = 0;
        var dy = 0;
        var fromCursor = false;
        if (resizeHasCursorAnchor) {
            var cursorPos = resizeLiveCursorIsFresh()
                ? { "x": resizeLiveCursorX, "y": resizeLiveCursorY }
                : readCursorGlobalPos();
            if (cursorPos) {
                dx = cursorPos.x - resizeStartCursorX;
                dy = cursorPos.y - resizeStartCursorY;
                fromCursor = true;
            }
        }
        if (!fromCursor) {
            dx = isFinite(translationX) ? translationX : 0;
            dy = isFinite(translationY) ? translationY : 0;
        }
        if (!isFinite(dx) || !isFinite(dy)) return;
        if (dx === 0 && dy === 0) return;

        resizeHasRealDelta = true;

        var left = resizeStartFinalX;
        var top = resizeStartFinalY;
        var right = resizeStartFinalX + resizeStartFinalW;
        var bottom = resizeStartFinalY + resizeStartFinalH;

        if (resizeHandle.indexOf("w") >= 0) {
            left = resizeStartFinalX + dx;
        }
        if (resizeHandle.indexOf("e") >= 0) {
            right = resizeStartFinalX + resizeStartFinalW + dx;
        }
        if (resizeHandle.indexOf("n") >= 0) {
            top = resizeStartFinalY + dy;
        }
        if (resizeHandle.indexOf("s") >= 0) {
            bottom = resizeStartFinalY + resizeStartFinalH + dy;
        }

        var minW = Math.max(1, resizeMinWidthPx());
        var minH = Math.max(1, resizeMinHeightPx());

        if ((right - left) < minW) {
            if (resizeHandle.indexOf("w") >= 0 && resizeHandle.indexOf("e") < 0) {
                left = right - minW;
            } else {
                right = left + minW;
            }
        }

        if ((bottom - top) < minH) {
            if (resizeHandle.indexOf("n") >= 0 && resizeHandle.indexOf("s") < 0) {
                top = bottom - minH;
            } else {
                bottom = top + minH;
            }
        }

        var nextX = Math.round(left);
        var nextY = Math.round(top);
        var nextW = Math.max(1, Math.round(right - left));
        var nextH = Math.max(1, Math.round(bottom - top));

        if (nextX === finalX && nextY === finalY && nextW === finalW && nextH === finalH) {
            return;
        }

        finalX = nextX;
        finalY = nextY;
        finalW = nextW;
        finalH = nextH;
        syncDragContentPosition();
        resizeMonitorFrame = resizeMonitorFrame + 1;
        phaseMonitorLog("RESIZE", resizeMonitorFrame,
            "handle=" + resizeHandle
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH));
    }

    function finishUserResize() {
        if (!userResizeInProgress) return;

        updateUserResize(0, 0);
        updateTargetScreenFromFinalCenter();

        userResizeInProgress = false;
        resizeHandle = "none";
        resizeHasCursorAnchor = false;
        resizeHasRealDelta = false;
        resizeLiveCursorValid = false;
        resizeLiveCursorSampleMs = 0;
        refreshActiveVisibleRect();
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        geometryTransitionSuppressed = false;
        rememberRestoreGeometry();
        if (!mainWin.detachedMode) {
            persistMainWindowLayout();
        }
        phaseLog("RESIZE", "Finish final=" + fmtRect(finalX, finalY, finalW, finalH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH));
    }

    function finishUserDrag() {
        // Drag lifecycle finalization point used by both Option 2 and future Option 3.
        if (!userMoveInProgress && dragStrategy === "none" && !systemMoveInProgress) return;
        if (dragFinalizePending) return;

        var wasNative = (dragStrategy === "native" || systemMoveInProgress);
        var releaseCenterX = Math.round(finalX + (finalW / 2.0));
        var releaseCenterY = Math.round(finalY + (finalH / 2.0));
        dragTrace("release-start", "native=" + (wasNative ? "yes" : "no")
            + " releaseCenter=(" + releaseCenterX + "," + releaseCenterY + ")");

        var finalizeDrop = function(nativeDrag, targetCenterX, targetCenterY) {
            // Native drag can emit release before final OS position commit; sample on finalize.
            if (nativeDrag) {
                var liveHostX = Math.round(mainWin.x);
                var liveHostY = Math.round(mainWin.y);
                if (isFinite(liveHostX) && isFinite(liveHostY)) {
                    var observedDeltaX = Math.round(liveHostX - dragStartHostX);
                    var observedDeltaY = Math.round(liveHostY - dragStartHostY);
                    var droppedFinalX = Math.round(dragStartFinalX + observedDeltaX);
                    var droppedFinalY = Math.round(dragStartFinalY + observedDeltaY);
                    if (isFinite(droppedFinalX) && isFinite(droppedFinalY)) {
                        finalX = droppedFinalX;
                        finalY = droppedFinalY;
                    }
                    hostX = liveHostX;
                    hostY = liveHostY;
                } else if (!observeContentGlobalPosition()) {
                    var fallbackDeltaX = Math.round(hostX - dragStartHostX);
                    var fallbackDeltaY = Math.round(hostY - dragStartHostY);
                    var fallbackFinalX = Math.round(dragStartFinalX + fallbackDeltaX);
                    var fallbackFinalY = Math.round(dragStartFinalY + fallbackDeltaY);
                    if (isFinite(fallbackFinalX) && isFinite(fallbackFinalY)) {
                        finalX = fallbackFinalX;
                        finalY = fallbackFinalY;
                    }
                }
            }

            dragReleaseSettlingUntilMs = Date.now() + Math.max(260, recoveryAutoClampDelayMs + 120);
            updateTargetScreenFromFinalCenter();
            refreshActiveVisibleRect();
            var snapTarget = dragReleaseSnapEnabled ? topEdgeSnapTargetForDragRelease() : null;
            if (snapTarget) {
                phaseLog("MAXIMIZE", "Top-edge drag release -> snap maximize");
                geometryTransitionSuppressed = true;
                userMoveInProgress = false;
                systemMoveInProgress = false;
                dragStrategy = "none";
                dragFinalizePending = false;
                updateCanvasGeometry();
                geometryTransitionSuppressed = false;
                if (dragFxReleaseAnimation.running) {
                    dragFxReleaseAnimation.stop();
                }
                resetDragFxState();
                rememberRestoreGeometry();
                if (maximizeWindowToVisibleRect(snapTarget.screen)) {
                    return;
                }
                phaseLog("MAXIMIZE", "Top-edge snap maximize fallback -> settle");
            }
            if (dragReleaseSnapEnabled && !nativeDrag && enforceNoClipWithinActiveMonitor()) {
                updateTargetScreenFromFinalCenter();
                refreshActiveVisibleRect();
                phaseLog("DRAG", "No-clip settle clamp -> " + fmtRect(finalX, finalY, finalW, finalH));
            }
            if (dragReleaseCenterLockEnabled && !uiMaximized) {
                if (lockDragReleaseCenter(targetCenterX, targetCenterY)) {
                    updateTargetScreenFromFinalCenter();
                    refreshActiveVisibleRect();
                }
            }

            geometryTransitionSuppressed = true;
            userMoveInProgress = false;
            systemMoveInProgress = false;
            dragStrategy = "none";
            dragFinalizePending = false;
            dragHasRealDelta = false;
            updateCanvasGeometry();
            // Drag release should settle into the existing host shell without
            // reintroducing the oversized host margin. That release-time margin
            // was the last remaining source of a one-shot flash after the first drag.
            if (ensureHostContainsRect(canvasX, canvasY, canvasW, canvasH, 0, false)) {
                updateCanvasGeometry();
            }
            geometryTransitionSuppressed = false;
            if (!uiMaximized) {
                rememberRestoreGeometry();
            }
            if (!mainWin.detachedMode) {
                persistMainWindowLayout();
            }
            releaseDragFxToSettled();
            var settledCenterX = Math.round(finalX + (finalW / 2.0));
            var settledCenterY = Math.round(finalY + (finalH / 2.0));
            dragTrace("release-settled",
                "releaseCenter=(" + targetCenterX + "," + targetCenterY + ")"
                + " settledCenter=(" + settledCenterX + "," + settledCenterY + ")");
        };

        if (wasNative) {
            dragFinalizePending = true;
            Qt.callLater(function() {
                finalizeDrop(true, releaseCenterX, releaseCenterY);
            });
            return;
        }

        if (dragReleaseCursorSampleEnabled) {
            applyFallbackDragFromCursor();
        }
        finalizeDrop(false, releaseCenterX, releaseCenterY);
    }

    // Backward-compatible alias.
    function beginSystemWindowMove() {
        return beginUserDrag();
    }

    function syncSettledGeometryFromWindowMove() {
        if (animationPhase !== "settled" || isClosing || !systemMoveInProgress || dragStrategy !== "native") return;
        logInteractionTrace("SYNC-NATIVE", "syncSettledGeometryFromWindowMove", false);

        var wx = Math.round(x);
        var wy = Math.round(y);
        if (!isFinite(wx) || !isFinite(wy)) {
            return;
        }

        // During native drag we only mirror host position.
        // finalX/finalY, screen target, and green frame are recomputed on drag release.
        var fxDx = wx - hostX;
        var fxDy = wy - hostY;
        if (hostX !== wx) hostX = wx;
        if (hostY !== wy) hostY = wy;
        applyDragFxFromDelta(fxDx, fxDy);
    }

    function detachedLaunchRectOrNull() {
        if (!mainWin.detachedMode) return null;
        if (isFiniteRectLike(mainWin.detachedHostWindowRect)) {
            return {
                "x": Math.round(mainWin.detachedHostWindowRect.x),
                "y": Math.round(mainWin.detachedHostWindowRect.y),
                "w": Math.max(1, Math.round(mainWin.detachedHostWindowRect.width)),
                "h": Math.max(1, Math.round(mainWin.detachedHostWindowRect.height))
            };
        }
        if (isFiniteRectLike(mainWin.detachedOriginRect)) {
            return {
                "x": Math.round(mainWin.detachedOriginRect.x),
                "y": Math.round(mainWin.detachedOriginRect.y),
                "w": Math.max(1, Math.round(mainWin.detachedOriginRect.width)),
                "h": Math.max(1, Math.round(mainWin.detachedOriginRect.height))
            };
        }
        return null;
    }
    
    function resolveTargetScreen() {
        var screens = applicationScreensSafe();
        if (!screens || screens.length === 0) {
            return null;
        }

        if (!mainWin.isSettled && mainWin.startupLaunchScreenLocked && mainWin.targetScreen) {
            return mainWin.targetScreen;
        }

        if (mainWin.detachedMode) {
            var detachedRect = detachedLaunchRectOrNull();
            if (detachedRect) {
                var cx = detachedRect.x + (detachedRect.w / 2.0);
                var cy = detachedRect.y + (detachedRect.h / 2.0);
                var pickedScreen = screenForPoint(cx, cy, mainWin.screen ? mainWin.screen : null);
                if (pickedScreen) {
                    targetScreen = pickedScreen;
                    targetScreenIndex = indexOfScreen(pickedScreen);
                    if (targetScreenIndex < 0) targetScreenIndex = 0;
                    targetScreenInfo = null;
                    if (appRef && appRef.getScreenGeometry && targetScreenIndex >= 0) {
                        targetScreenInfo = appRef.getScreenGeometry(targetScreenIndex);
                    }
                    return targetScreen;
                }
            }
        }

        var idx = currentCursorScreenIndex();
        targetScreenInfo = null;
        if (!mainWin.isSettled && mainWin.startupLaunchScreenLocked
            && idx === mainWin.targetScreenIndex
            && mainWin.targetScreenInfo) {
            targetScreenInfo = mainWin.targetScreenInfo;
        } else if (appRef && appRef.getScreenGeometry) {
            targetScreenInfo = appRef.getScreenGeometry(idx);
        }

        var picked = selectScreenFromPythonInfo(screens, targetScreenInfo, idx);
        targetScreen = picked.screen;
        targetScreenIndex = picked.index;
        if (!targetScreen) {
            targetScreen = screens[0];
            targetScreenIndex = 0;
        }
        if (!mainWin.isSettled && mainWin.startupLaunchScreenLocked
            && targetScreenIndex === mainWin.targetScreenIndex
            && mainWin.targetScreenInfo) {
            targetScreenInfo = mainWin.targetScreenInfo;
        } else if (appRef && appRef.getScreenGeometry && targetScreenIndex >= 0) {
            targetScreenInfo = appRef.getScreenGeometry(targetScreenIndex);
        }
        
        return targetScreen;
    }
    
    function persistMainWindowLayout() {
        if (mainWin.detachedMode || !mainWin.appRef || !mainWin.appRef.saveMainWindowLayout) return false;
        var payload = { "maximized": !!mainWin.uiMaximized };
        if (!mainWin.uiMaximized) {
            var uw = Math.max(1, Math.round(mainWin.usableW));
            var uh = Math.max(1, Math.round(mainWin.usableH));
            var ux = Math.round(mainWin.usableX);
            var uy = Math.round(mainWin.usableY);
            payload.widthPct = Math.max(0, Math.min(1, mainWin.finalW / uw));
            payload.heightPct = Math.max(0, Math.min(1, mainWin.finalH / uh));
            payload.centerXPct = Math.max(0, Math.min(1, ((mainWin.finalX + (mainWin.finalW / 2.0)) - ux) / uw));
            payload.centerYPct = Math.max(0, Math.min(1, ((mainWin.finalY + (mainWin.finalH / 2.0)) - uy) / uh));
        }
        try {
            return !!mainWin.appRef.saveMainWindowLayout(payload);
        } catch (e0) {
            return false;
        }
    }

    function resolvePersistedMainWindowRect(ux, uy, uw, uh, minW, maxW, minH, maxH) {
        if (!mainWin.appRef || !mainWin.appRef.getMainWindowLayout) return null;
        var saved = null;
        try {
            saved = mainWin.appRef.getMainWindowLayout();
        } catch (e0) {
            return null;
        }
        if (!saved || !saved.ok) return null;
        if (saved.maximized) {
            return { "maximized": true };
        }
        var widthPct = Number(saved.widthPct || 0);
        var heightPct = Number(saved.heightPct || 0);
        if (!(widthPct > 0.05 && heightPct > 0.05)) return null;

        var w = Math.round(clampNumber(uw * widthPct, minW, Math.min(maxW, uw)));
        var h = Math.round(clampNumber(uh * heightPct, minH, Math.min(maxH, uh)));
        var cx = ux + (clampNumber(Number(saved.centerXPct || 0.5), 0.0, 1.0) * uw);
        var cy = uy + (clampNumber(Number(saved.centerYPct || 0.5), 0.0, 1.0) * uh);
        var x = Math.round(cx - (w / 2.0));
        var y = Math.round(cy - (h / 2.0));
        x = Math.round(clampNumber(x, ux, ux + uw - w));
        y = Math.round(clampNumber(y, uy, uy + uh - h));
        return { "maximized": false, "x": x, "y": y, "w": w, "h": h };
    }

    function applyGeometryToTargetScreen(showWhenConfigured) {
        var shouldShowWindow = showWhenConfigured !== false;
        var selected = targetScreen ? targetScreen : resolveTargetScreen();
        if (!selected) return false;
        enforceWindowScreen(selected, "applyGeometryToTargetScreen");
        
        // Canonical geometry basis: monitor visible/usable area.
        var visibleRect = visibleRectForScreen(selected, targetScreenInfo);
        var ux = visibleRect.x;
        var uy = visibleRect.y;
        var uw = visibleRect.w;
        var uh = visibleRect.h;

        usableX = ux;
        usableY = uy;
        usableW = uw;
        usableH = uh;
        mainWin.refreshActiveVisibleRect();
        updateDebugOverlayBounds();
        if (targetScreenInfo) {
            monitorScalePercent = (typeof targetScreenInfo.scalePercent === "number")
                ? targetScreenInfo.scalePercent
                : ((typeof targetScreenInfo.dpr === "number") ? Math.round(targetScreenInfo.dpr * 100) : 100);
            taskbarEdge = (typeof targetScreenInfo.taskbarEdge === "string")
                ? targetScreenInfo.taskbarEdge : "none";
            taskbarSize = (typeof targetScreenInfo.taskbarSize === "number")
                ? targetScreenInfo.taskbarSize : 0;
        } else {
            monitorScalePercent = 100;
            taskbarEdge = "none";
            taskbarSize = 0;
        }

        // Initialize settled-glow animation from a percentage of visible area.
        glowPadding = openingPaddingPx();

        var detachedLaunchRect = detachedLaunchRectOrNull();
        if (detachedLaunchRect) {
            var detachedW = Math.max(1, Math.round(detachedLaunchRect.w));
            var detachedH = Math.max(1, Math.round(detachedLaunchRect.h));
            if (detachedW > uw) detachedW = uw;
            if (detachedH > uh) detachedH = uh;

            var detachedX = Math.round(detachedLaunchRect.x);
            var detachedY = Math.round(detachedLaunchRect.y);
            detachedX = Math.round(clampNumber(detachedX, ux, ux + uw - detachedW));
            detachedY = Math.round(clampNumber(detachedY, uy, uy + uh - detachedH));

            finalW = Math.max(1, detachedW);
            finalH = Math.max(1, detachedH);
            finalX = detachedX;
            finalY = detachedY;
            uiMaximized = false;
            rememberRestoreGeometry();
            applyHostEnvelopeForTarget();

            if (!launchConfigured) {
                launchConfigured = true;
                updateCanvasGeometry();
                if (shouldShowWindow) {
                    mainWin.show();
                }
            }
            phaseLog("MAIN", "Detached launch geometry: usable=" + fmtRect(usableX, usableY, usableW, usableH)
                + " content=" + fmtRect(finalX, finalY, finalW, finalH)
                + " host=" + fmtRect(hostX, hostY, hostW, hostH));
            if (shouldShowWindow) {
                mainWin.raise();
                mainWin._requestActivateIfFocusable(mainWin);
            }
            return true;
        }

        var aspect = (typeof layoutRatios.contentAspect === "number" && layoutRatios.contentAspect > 0.01)
            ? layoutRatios.contentAspect
            : (1220.0 / 920.0);
        var launchBoost = launchSizeBoostForScalePercent(monitorScalePercent);
        var targetHeightRatio = clampNumber(layoutRatios.contentHeightPct * launchBoost, layoutRatios.contentHeightPct, 0.94);
        var minHeightRatio = clampNumber(layoutRatios.contentMinHeightPct * (1.0 + ((launchBoost - 1.0) * 0.65)), layoutRatios.contentMinHeightPct, 0.72);
        var maxHeightRatio = clampNumber(layoutRatios.contentMaxHeightPct * (1.0 + ((launchBoost - 1.0) * 0.55)), layoutRatios.contentMaxHeightPct, 0.995);
        var targetH = Math.round(uh * targetHeightRatio);
        var minH = Math.max(1, Math.round(uh * minHeightRatio));
        var maxH = Math.max(minH, Math.round(uh * maxHeightRatio));
        var computedH = clampNumber(targetH, minH, maxH);
        var computedW = Math.round(computedH * aspect);

        var minWidthRatio = clampNumber(layoutRatios.contentMinWidthPct * (1.0 + ((launchBoost - 1.0) * 0.75)), layoutRatios.contentMinWidthPct, 0.58);
        var maxWidthRatio = clampNumber(layoutRatios.contentMaxWidthPct * (1.0 + ((launchBoost - 1.0) * 0.50)), layoutRatios.contentMaxWidthPct, 0.985);
        var minW = Math.max(1, Math.round(uw * minWidthRatio));
        var maxW = Math.max(minW, Math.round(uw * maxWidthRatio));
        computedW = clampNumber(computedW, minW, maxW);

        var persistedRect = null;
        var usePersistedWindowSize = false;
        if (!mainWin.detachedMode) {
            persistedRect = resolvePersistedMainWindowRect(ux, uy, uw, uh, minW, maxW, minH, maxH);
            if (persistedRect && persistedRect.maximized) {
                uiMaximized = true;
                finalX = Math.round(ux);
                finalY = Math.round(uy);
                finalW = Math.max(1, Math.round(uw));
                finalH = Math.max(1, Math.round(uh));
                applyHostEnvelopeForTarget();

                if (!launchConfigured) {
                    launchConfigured = true;
                    updateCanvasGeometry();
                    enforceWindowScreen(selected, "launch-before-show-persisted-max");
                    if (shouldShowWindow) {
                        mainWin.show();
                    }
                }
                phaseLog("MAIN", "Launch geometry (persisted maximized): usable=" + fmtRect(usableX, usableY, usableW, usableH)
                    + " content=" + fmtRect(finalX, finalY, finalW, finalH)
                    + " host=" + fmtRect(hostX, hostY, hostW, hostH));
                if (shouldShowWindow) {
                    mainWin.raise();
                    mainWin._requestActivateIfFocusable(mainWin);
                }
                return true;
            }
            if (persistedRect) {
                computedW = Math.max(1, Math.round(persistedRect.w));
                computedH = Math.max(1, Math.round(persistedRect.h));
                usePersistedWindowSize = true;
            }
        }

        if (!usePersistedWindowSize) {
            // Reserve settled-effect padding so the window/glow cannot be cropped while moving.
            var reservePad = settledPaddingPx(computedW, computedH);
            var maxWWithPad = Math.max(1, uw - (reservePad * 2));
            var maxHWithPad = Math.max(1, uh - (reservePad * 2));
            if (computedW > maxWWithPad) {
                computedW = maxWWithPad;
                computedH = Math.max(1, Math.round(computedW / aspect));
            }
            if (computedH > maxHWithPad) {
                computedH = maxHWithPad;
                computedW = Math.max(1, Math.round(computedH * aspect));
            }

            // Reserve the normal opening visual bleed up front. The squash/stretch
            // deformation itself is render-clamped below so the final app size stays stable.
            var openingSize = openingConstrainedSize(computedW, computedH, aspect, uw, uh);
            computedW = openingSize.w;
            computedH = openingSize.h;

            if (computedW > uw) {
                computedW = uw;
                computedH = Math.max(1, Math.round(computedW / aspect));
            }
            if (computedH > uh) {
                computedH = uh;
                computedW = Math.max(1, Math.round(computedH * aspect));
            }
        }

        finalW = Math.max(1, Math.round(computedW));
        finalH = Math.max(1, Math.round(computedH));

        if (usePersistedWindowSize && persistedRect
                && typeof persistedRect.x === "number" && typeof persistedRect.y === "number") {
            finalX = Math.round(persistedRect.x);
            finalY = Math.round(persistedRect.y);
        } else {
            var monitorCenterX = ux + (uw * layoutRatios.contentCenterXPct);
            var monitorCenterY = uy + (uh * layoutRatios.contentCenterYPct);
            finalX = Math.round(monitorCenterX - (finalW / 2.0));
            finalY = Math.round(monitorCenterY - (finalH / 2.0));
        }
        uiMaximized = false;
        rememberRestoreGeometry();

        applyHostEnvelopeForTarget();
        
                
        if (!launchConfigured) {
            launchConfigured = true;
            updateCanvasGeometry();
            enforceWindowScreen(selected, "launch-before-show");
            if (shouldShowWindow) {
                mainWin.show();
            }
        }
        phaseLog("MAIN", "Launch geometry: usable=" + fmtRect(usableX, usableY, usableW, usableH)
            + " content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " host=" + fmtRect(hostX, hostY, hostW, hostH)
            + " scale=" + monitorScalePercent + "% boost=" + launchBoost.toFixed(3)
            + " taskbar=" + taskbarEdge + "@" + taskbarSize);
        logCornerForensics("launch");
        if (shouldShowWindow) {
            mainWin.raise();
            mainWin._requestActivateIfFocusable(mainWin);
        }
        return true;
    }
    
    // ============================================================
    // CANVAS SIZING: PIXEL-PERFECT TRANSITIONS
    // ============================================================
    
    /// CRITICAL CONSTRAINT: Window content's global pixel position NEVER changes
    /// Window global position: (finalX, finalY, finalW, finalH)  
    /// Canvas position & size changes based on phase
    /// Content's LOCAL position within canvas adjusts to compensate
    /// Invariant: globalContentX = canvasX + contentLocalX = finalX always
    
    property int contentLocalX: 0
    property int contentLocalY: 0
    property int canvasLocalX: 0
    property int canvasLocalY: 0
    
    // Keep content locked to finalX/finalY during canvas reflow.
    // Animating contentLocal* causes visible side-shifts during opening->settled handoff.
    
    function updateCanvasGeometry() {
        if (animationPhase === "settled" && userMoveInProgress && dragStrategy === "native") {
            // Keep canvas fixed during native drag; host window movement carries content smoothly.
            canvasLocalX = canvasX - hostX;
            canvasLocalY = canvasY - hostY;
            return;
        }

        var windowCenterX = finalX + (finalW / 2);
        var windowCenterY = finalY + (finalH / 2);
        var padding = glowPadding;
        
        // CRITICAL: Always use the ACTIVE monitor (where content currently is or where cursor is)
        var activeScreen = targetScreen;
        if (!activeScreen) {
            // If target screen lost, redetect based on window center position
            var screens = applicationScreensSafe();
            for (var i = 0; i < screens.length; i++) {
                var s = screens[i];
                var sx = s.virtualX;
                var sy = s.virtualY;
                var sw = s.width;
                var sh = s.height;
                // Check if window center is on this screen
                if (windowCenterX >= sx && windowCenterX < (sx + sw) &&
                    windowCenterY >= sy && windowCenterY < (sy + sh)) {
                    activeScreen = s;
                    targetScreen = s;
                    break;
                }
            }
            if (!activeScreen) {
                return;
            }
        }
        
        // Get ONLY this monitor's bounds (single screen, not virtual combined space)
        var monitorX = activeScreen.virtualX;
        var monitorY = activeScreen.virtualY;
        var monitorW = activeScreen.width;
        var monitorH = activeScreen.height;

        // Keep opening/closing strictly within usable area when known.
        if (mainWin.usableW > 0 && mainWin.usableH > 0) {
            monitorX = mainWin.usableX;
            monitorY = mainWin.usableY;
            monitorW = mainWin.usableW;
            monitorH = mainWin.usableH;
        }

        if (!isFinite(padding) || padding < 0) {
            padding = settledPaddingPx();
        }
        
        if (animationPhase === "opening") {
            if (mainWin.detachedMode) {
                // Detached opening should not own full-monitor input bounds.
                var openPad = Math.max(
                    settledPaddingPx(Math.max(1, finalW), Math.max(1, finalH)),
                    dragPadPx(monitorW, monitorH)
                );
                canvasX = Math.round(finalX - openPad);
                canvasY = Math.round(finalY - openPad);
                canvasW = Math.max(1, Math.round(finalW + (openPad * 2)));
                canvasH = Math.max(1, Math.round(finalH + (openPad * 2)));
            } else {
                // OPENING (main): use the full launch host/full-screen envelope,
                // not the usable rect, so the animated layer never has the
                // taskbar-aware green rectangle as an implicit viewport.
                var openingCanvas = openingHostBaseRect({
                    "x": monitorX,
                    "y": monitorY,
                    "w": monitorW,
                    "h": monitorH
                });
                canvasX = Math.round(openingCanvas.x);
                canvasY = Math.round(openingCanvas.y);
                canvasW = Math.max(1, Math.round(openingCanvas.w));
                canvasH = Math.max(1, Math.round(openingCanvas.h));
            }
            
            // Content position within canvas
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
            
        } else if (animationPhase === "closing") {
            // CLOSING: use a tight motion envelope around content and its close target.
            var closeRect = closingCanvasRect();
            canvasX = closeRect.x;
            canvasY = closeRect.y;
            canvasW = closeRect.w;
            canvasH = closeRect.h;

            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
            
        } else if (animationPhase === "settled" && maximizeAnimInProgress && !uiMaximized) {
            // RESTORE-FROM-MAX: keep canvas pinned to full visible monitor during FX to prevent crop/clipping.
            // Shrink back to settled window bounds only after maximize FX fully settles.
            canvasX = monitorX;
            canvasY = monitorY;
            canvasW = monitorW;
            canvasH = monitorH;

            contentLocalX = Math.round(finalX - canvasX);
            contentLocalY = Math.round(finalY - canvasY);

        } else if (animationPhase === "settled" && userResizeInProgress) {
            // RESIZING: keep a fixed interaction pad and avoid settled clamping during live deformation.
            var resizePad = Math.max(0, Math.round(glowPadding));
            canvasX = Math.round(finalX - resizePad);
            canvasY = Math.round(finalY - resizePad);
            canvasW = Math.max(1, Math.round(finalW + (resizePad * 2)));
            canvasH = Math.max(1, Math.round(finalH + (resizePad * 2)));

            contentLocalX = Math.round(finalX - canvasX);
            contentLocalY = Math.round(finalY - canvasY);

        } else if (animationPhase === "settled" && userMoveInProgress && dragStrategy === "fallback") {
            // DRAGGING (SETTLED): keep no-clip geometry local to movement.
            applyDragInteractionGeometry();
            return;

        } else if (animationPhase === "settled") {
            // SETTLED: Window + padding, but never allow canvas to exceed usable monitor bounds.
            var maxPadX = Math.max(0, Math.floor((monitorW - finalW) / 2));
            var maxPadY = Math.max(0, Math.floor((monitorH - finalH) / 2));
            var maxPad = Math.min(maxPadX, maxPadY);
            var boundedPadding = Math.max(0, Math.min(padding, maxPad));

            canvasW = finalW + (boundedPadding * 2);
            canvasH = finalH + (boundedPadding * 2);
            canvasX = windowCenterX - (canvasW / 2);
            canvasY = windowCenterY - (canvasH / 2);
            
            // Content position within canvas
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
        }
        
        // Host follows the active monitor envelope; canvas/content remain monitor-relative inside host.
        canvasLocalX = canvasX - hostX;
        canvasLocalY = canvasY - hostY;
    }
    
    // ============================================================
    // PHASE TRANSITIONS
    // ============================================================
    
    function transitionToSettled() {
        lagLog("[FORENSIC] transitionToSettled entered")
        phaseLog("PHASE", "OPENING -> SETTLED");
        shellMaskSettleDelayReady = false;
        shellMaskSettleTimer.stop();
        logCornerForensics("transition-to-settled-pre");
        animationPhase = "settled";
        isSettled = true;
        // Backend boot is a data-lifecycle requirement, not a focus side
        // effect. Keep it explicit so removing startup focus code can never
        // leave the live workbook unread and the dashboard at zero.
        if (!mainWin.detachedMode) {
            mainWin.triggerDeferredBackendBoot();
        }
        startupLaunchScreenLocked = false;
        startupHeavyWorkAllowed = false;
        startupHeavyWorkBlockedCount = 0;
        startupSettledEpochMs = Date.now();
        startupPostSettleReadyEpochMs = 0;
        startupQueueInputTimeoutReleased = false;
        startupHeavyWorkGraceTimer.stop();
        startupHeavyWorkGraceTimer.interval = Math.max(120, startupHeavyWorkGraceMs);
        startupHeavyWorkGraceTimer.start();
        setStartupPhase("settled-grace", "transitionToSettled");
        perfEnd("window.transition.open", "phase=" + animationPhase + " settled=" + isSettled);
        startupCheckpointPending = false;
        // Snap canvas envelope to final settled padding at handoff so there is
        // no residual settle-time host/canvas geometry morph.
        glowPadding = settledPaddingPx(Math.max(1, finalW), Math.max(1, finalH));
        mainWin.geometryTransitionSuppressed = true;
        applyHostEnvelopeForTarget();
        updateCanvasGeometry();
        Qt.callLater(function() {
            mainWin.geometryTransitionSuppressed = false;
        });
        phaseLog("SETTLED", "content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH));
        logCornerForensics("transition-to-settled");
        startCornerForensicBurst("transition-to-settled", 96);
        if (mainWin.appStyle === "Professional") {
            canvasTransition.stop();
            canvasGeometryAdjust.transitionProgress = 1.0;
            shellMaskSettleDelayReady = true;
        } else {
            canvasTransition.start();
            performGlowShrinkage();
        }
        if (!mainWin.detachedMode) {
            if (mainWin.startupAllowsHeavyWork("transitionToSettled.autoCheckpoint")) {
                autoCheckpointCloseSession("startup-settled");
            } else {
                startupCheckpointPending = true;
            }
            if (!mainWin.recoveryPromptHandled && !recoveryPromptStartupTimer.running) {
                recoveryPromptStartupTimer.start();
            }
        }
    }
    
    function transitionToClosing() {
        if (isClosing) return;
        if (!mainWin.detachedMode) {
            persistMainWindowLayout();
        }
        perfStart("window.transition.close", "phase=" + animationPhase + " detached=" + detachedMode);
        closeFinalizeFailsafeTimer.restart();
        shellMaskSettleDelayReady = false;
        shellMaskSettleTimer.stop();
        phaseLog("PHASE", "SETTLED -> CLOSING");
        clearStartupDeferredQueue("transition-to-closing");
        try {
            if (mainContent && mainContent.cancelAsyncStartupWork) {
                mainContent.cancelAsyncStartupWork("window-transition-to-closing");
            }
        } catch (eCancelStartupLoaders) {
            lagLog("MainContent async-loader cancellation failed=" + eCancelStartupLoaders);
        }
        phaseLog("CLOSING", "Transition requested content=" + fmtRect(finalX, finalY, finalW, finalH)
            + " canvas=" + fmtRect(canvasX, canvasY, canvasW, canvasH));
        if (sfxBus && sfxBus.playWindowCloseFly) {
            sfxBus.playWindowCloseFly(mainWin.detachedMode ? 0.56 : 0.68);
        }
        logCornerForensics("transition-to-closing");
        if (!mainWin.detachedMode) {
            autoCheckpointCloseSession("transition-to-closing");
        }
        if (maximizeAnimInProgress) {
            stopMaximizeFxAnimations();
        }
        if (isMinimizing) {
            isMinimizing = false;
            destroyMinimizeOverlay();
            opacity = 1.0;
            clearMinimizeRestoreState();
        }
        if (isRestoringFromMinimize) {
            isRestoringFromMinimize = false;
            destroyMinimizeOverlay();
            opacity = 1.0;
            clearMinimizeRestoreState();
        }
        if (userResizeInProgress) {
            finishUserResize();
        }
        if (userMoveInProgress) {
            finishUserDrag();
        }

        // Lock the exact settled host and content geometry in-place.
        // Zero window repositioning or host envelope resizing avoids DWM/FBO repaints.
        animationPhase = "closing";
        isClosing = true;
        closeMotionStarted = false;
        jelly.freezeToIdentity();

        phaseLog("CLOSING", "Starting direct in-place Singularity close motion");
        mainWin.startCloseMotion("singularity-inplace");
    }
    
    // ============================================================
    // CANVAS TRANSITION ANIMATION
    // ============================================================
    
    SequentialAnimation {
        id: canvasTransition
        onRunningChanged: {
            if (running) {
                mainWin.shellMaskSettleDelayReady = false;
                shellMaskSettleTimer.stop();
                return;
            }
            if (mainWin.animationPhase === "settled"
                && !mainWin.isClosing
                && !mainWin.isMinimizing
                && !mainWin.isRestoringFromMinimize) {
                if (mainWin.shellMaskSettleDelayMs <= 0) {
                    mainWin.shellMaskSettleDelayReady = true;
                } else {
                    shellMaskSettleTimer.restart();
                }
            } else {
                mainWin.shellMaskSettleDelayReady = false;
                shellMaskSettleTimer.stop();
            }
        }
        
        ParallelAnimation {
            NumberAnimation {
                target: canvasGeometryAdjust
                property: "transitionProgress"
                from: 0.0
                to: 1.0
                duration: 200
                easing.type: Easing.InOutQuad
            }
        }
    }
    
    Item {
        id: canvasGeometryAdjust
        property real transitionProgress: 0.0
    }

    Timer {
        id: shellMaskSettleTimer
        interval: Math.max(0, mainWin.shellMaskSettleDelayMs)
        repeat: false
        onTriggered: {
            if (mainWin.animationPhase === "settled"
                && !mainWin.isClosing
                && !mainWin.isMinimizing
                && !mainWin.isRestoringFromMinimize) {
                mainWin.shellMaskSettleDelayReady = true;
            }
        }
    }

    Timer {
        id: startupLaunchDelayTimer
        interval: 0
        repeat: false
        onTriggered: {
            mainWin.lagLog("startupLaunchDelayTimer triggered intervalMs=" + startupLaunchDelayTimer.interval);
            mainWin.startOpeningLaunchNow();
        }
    }

    Timer {
        id: startupDeferredQueueTimer
        interval: Math.max(24, mainWin.startupDeferredQueueTickMs)
        repeat: false
        onTriggered: {
            mainWin.processStartupDeferredQueueTick();
        }
    }

    Timer {
        id: startupHeavyWorkGraceTimer
        interval: mainWin.startupHeavyWorkGraceMs
        repeat: false
        onTriggered: {
            if (!mainWin.isSettled) return;
            mainWin.startupHeavyWorkAllowed = true;
            mainWin.startupHeavyWorkBlockedCount = 0;
            mainWin.startupPostSettleReadyEpochMs = Date.now();
            mainWin.setStartupPhase("post-settle-ready", "settle-grace-elapsed");
            mainWin.lagLog("startup heavy-work guard released graceMs=" + mainWin.startupHeavyWorkGraceMs);
            console.warn("[STARTUP-FIRST-INPUT-READY] [MAINWIN] t+" + mainWin.splashElapsedMs() + "ms");
            mainWin.requestDeferredSettingsLoadIfNeeded("settle-grace-elapsed");
            if (mainWin.startupCheckpointPending && !mainWin.detachedMode) {
                mainWin.startupCheckpointPending = false;
                mainWin.autoCheckpointCloseSession("startup-settled");
            }
            mainWin.requestStartupDeferredQueuePump("startupHeavyWorkGraceTimer");
        }
    }

    Timer {
        id: startupFocusReassertTimer
        interval: 120
        repeat: false
        onTriggered: {
            // Never reclaim focus after startup.  A user may already have
            // moved to another application by the time this timer fires.
            mainWin.startupFocusReassertRemaining = 0;
        }
    }

    Connections {
        target: mainWin.appRef
        ignoreUnknownSignals: true
        function onStartupBriefingSnapshotChanged() {
            mainWin.prepareStartupBriefingForReveal()
        }
        function onBackendBootChanged() {
            if (!(mainWin.appRef && mainWin.appRef.backendBooted)) return;
            mainWin.startupDataBootStarted = true;
            mainWin.startupDataBootComplete = true;
            mainWin.startupDataBootFailed = false;
            mainWin.startupDataBootMessage = "";
        }
        function onStartupFirstInputSeenChanged() {
            mainWin.requestStartupDeferredQueuePump("startup-first-input-seen");
        }
        function onToast(message) {
            if (!mainWin.visible) return;
            mainWin.showAppNotification(String(message || ""), "info");
        }
        function onError(message) {
            if (!mainWin.visible) return;
            mainWin.showAppNotification(String(message || ""), "error");
        }
    }

    SequentialAnimation {
        id: maximizeFxAnimation
        running: false

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.12; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 0.88; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 14; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: -12; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 1.9; duration: 110; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 0.93; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 1.08; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: -9; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: 7; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: -1.5; duration: 130; easing.type: Easing.InOutSine }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.02; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 0.99; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 3; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: -2; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 0.45; duration: 110; easing.type: Easing.InOutSine }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.0; duration: 95; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 1.0; duration: 95; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 0.0; duration: 95; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: 0.0; duration: 95; easing.type: Easing.OutQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 0.0; duration: 95; easing.type: Easing.OutQuad }
        }

        onRunningChanged: {
            if (running) {
                mainWin.phaseLog("MAXIMIZE", "FX animation start");
                mainWin.logGreenFrameGeometry("MAXIMIZE", "FX start geometry");
            }
            if (!running && mainWin.maximizeAnimInProgress && !maximizeRestoreFxAnimation.running) {
                mainWin.resetMaximizeFxState();
                mainWin.maximizeAnimInProgress = false;
                mainWin.updateCanvasGeometry();
                mainWin.phaseLog("MAXIMIZE", "FX animation settled");
                mainWin.logGreenFrameGeometry("MAXIMIZE", "FX settled geometry");
                if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                    mainWin.sfxBusRef.playWindowSettle("maximize", 0.70);
                }
            }
        }
    }

    SequentialAnimation {
        id: maximizeRestoreFxAnimation
        running: false

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.02; duration: 95; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 0.99; duration: 95; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 3; duration: 95; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: -2; duration: 95; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 0.45; duration: 95; easing.type: Easing.InQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 0.93; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 1.08; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: -9; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: 7; duration: 110; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: -1.5; duration: 110; easing.type: Easing.InOutSine }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.12; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 0.88; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 14; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: -12; duration: 130; easing.type: Easing.InOutSine }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 1.9; duration: 130; easing.type: Easing.InOutSine }
        }

        ParallelAnimation {
            NumberAnimation { target: mainWin; property: "maximizeFxScaleX"; to: 1.0; duration: 110; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxScaleY"; to: 1.0; duration: 110; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransX"; to: 0.0; duration: 110; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxTransY"; to: 0.0; duration: 110; easing.type: Easing.InQuad }
            NumberAnimation { target: mainWin; property: "maximizeFxRotate"; to: 0.0; duration: 110; easing.type: Easing.InQuad }
        }

        onRunningChanged: {
            if (running) {
                mainWin.phaseLog("RESTORE-MAX", "FX animation start");
                mainWin.logGreenFrameGeometry("RESTORE-MAX", "FX start geometry");
            }
            if (!running && mainWin.maximizeAnimInProgress && !maximizeFxAnimation.running) {
                mainWin.resetMaximizeFxState();
                mainWin.maximizeAnimInProgress = false;
                mainWin.updateCanvasGeometry();
                mainWin.phaseLog("RESTORE-MAX", "FX animation settled");
                mainWin.logGreenFrameGeometry("RESTORE-MAX", "FX settled geometry");
                if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                    mainWin.sfxBusRef.playWindowSettle("restore", 0.66);
                }
            }
        }
    }

    Timer {
        id: maximizeFxMonitor
        interval: 16
        repeat: true
        running: mainWin.maximizeAnimInProgress && (maximizeFxAnimation.running || maximizeRestoreFxAnimation.running)
        onTriggered: {
            var gLocal = mainWin.greenFrameLocalRect();
            if (maximizeFxAnimation.running) {
                mainWin.maximizeMonitorFrame = mainWin.maximizeMonitorFrame + 1
                mainWin.phaseMonitorLog("MAXIMIZE", mainWin.maximizeMonitorFrame,
                    "fxScale=" + mainWin.maximizeFxScaleX.toFixed(3) + "x" + mainWin.maximizeFxScaleY.toFixed(3)
                    + " transX=" + mainWin.maximizeFxTransX.toFixed(2)
                    + " transY=" + mainWin.maximizeFxTransY.toFixed(2)
                    + " rotate=" + mainWin.maximizeFxRotate.toFixed(2)
                    + " greenLocal=" + Math.round(gLocal.x) + "," + Math.round(gLocal.y)
                    + " host=" + Math.round(mainWin.x) + "," + Math.round(mainWin.y))
            } else if (maximizeRestoreFxAnimation.running) {
                mainWin.restoreMaxMonitorFrame = mainWin.restoreMaxMonitorFrame + 1
                mainWin.phaseMonitorLog("RESTORE-MAX", mainWin.restoreMaxMonitorFrame,
                    "fxScale=" + mainWin.maximizeFxScaleX.toFixed(3) + "x" + mainWin.maximizeFxScaleY.toFixed(3)
                    + " transX=" + mainWin.maximizeFxTransX.toFixed(2)
                    + " transY=" + mainWin.maximizeFxTransY.toFixed(2)
                    + " rotate=" + mainWin.maximizeFxRotate.toFixed(2)
                    + " greenLocal=" + Math.round(gLocal.x) + "," + Math.round(gLocal.y)
                    + " host=" + Math.round(mainWin.x) + "," + Math.round(mainWin.y))
            }
        }
    }

    ParallelAnimation {
        id: dragFxReleaseAnimation
        running: false

        NumberAnimation {
            target: mainWin
            property: "dragFxScaleX"
            to: 1.0
            duration: mainWin.lowPerformanceMode ? 170 : 300
            easing.type: mainWin.lowPerformanceMode ? Easing.OutQuad : Easing.OutBack
        }
        NumberAnimation {
            target: mainWin
            property: "dragFxScaleY"
            to: 1.0
            duration: mainWin.lowPerformanceMode ? 170 : 300
            easing.type: mainWin.lowPerformanceMode ? Easing.OutQuad : Easing.OutBack
        }
        NumberAnimation {
            target: mainWin
            property: "dragFxTransX"
            to: 0.0
            duration: mainWin.lowPerformanceMode ? 140 : 240
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: mainWin
            property: "dragFxTransY"
            to: 0.0
            duration: mainWin.lowPerformanceMode ? 140 : 240
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: mainWin
            property: "dragFxRotate"
            to: 0.0
            duration: mainWin.lowPerformanceMode ? 150 : 260
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: mainWin
            property: "dragFxCornerBoost"
            to: 0.0
            duration: mainWin.lowPerformanceMode ? 170 : 300
            easing.type: Easing.OutQuad
        }
    }

    Timer {
        id: fallbackDragTick
        interval: 8
        repeat: true
        running: mainWin.userMoveInProgress
            && mainWin.dragStrategy === "fallback"
            && mainWin.dragPollingEnabled
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
        onTriggered: {
            mainWin.applyFallbackDragFromCursor()
        }
    }

    Timer {
        id: resizeTick
        interval: 4
        repeat: true
        running: mainWin.userResizeInProgress
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
        onTriggered: {
            mainWin.updateUserResize(0, 0)
        }
    }

    Timer {
        id: hoverActivateTimer
        interval: Math.max(1, mainWin.hoverActivateDelayMs)
        repeat: false
        onTriggered: {
            if (!mainWin.hoverActivateEnabled) return;
            if (mainWin.active) return;
            if (mainWin.animationPhase !== "settled") return;
            if (mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize) return;
            try {
                mainWin.raise();
                mainWin._requestActivateIfFocusable(mainWin);
            } catch (e) {
            }
        }
    }

    Timer {
        id: recoveryPromptStartupTimer
        interval: 240
        repeat: false
        onTriggered: {
            if (mainWin.detachedMode) return
            mainWin.maybePresentPendingRecoveryPrompt()
        }
    }

    Timer {
        id: closeRiskCheckpointTimer
        interval: 12000
        repeat: true
        running: !mainWin.detachedMode
            && mainWin.launchConfigured
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.forceClose
            && !mainWin.isMinimizing
            && !mainWin.isRestoringFromMinimize
        onTriggered: {
            mainWin.autoCheckpointCloseSession("periodic-risk-checkpoint")
        }
    }

    Timer {
        id: classicMoveArmTimer
        interval: 1200
        repeat: false
        onTriggered: {
            mainWin.classicMoveMenuArmed = false
        }
    }

    Timer {
        id: titlebarAutoClampTimer
        interval: 60
        repeat: true
        running: mainWin.recoveryAutoClampEnabled
            && mainWin.launchConfigured
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.forceClose
        onTriggered: {
            var nowMs = Date.now()
            if (nowMs < mainWin.dragReleaseSettlingUntilMs) {
                mainWin.titlebarOutSinceMs = 0
                return
            }
            if (mainWin.classicMoveModeActive
                || mainWin.userMoveInProgress
                || mainWin.userResizeInProgress
                || mainWin.systemMoveInProgress
                || mainWin.dragFinalizePending
                || mainWin.isMinimizing
                || mainWin.isRestoringFromMinimize
                || mainWin.maximizeAnimInProgress) {
                mainWin.titlebarOutSinceMs = 0
                return
            }
            var activeRect = mainWin.activeVisibleRectSafe()
            if (!mainWin.titlebarOutsideVisibleRect(activeRect)) {
                mainWin.titlebarOutSinceMs = 0
                return
            }
            if (mainWin.titlebarOutSinceMs <= 0) {
                mainWin.titlebarOutSinceMs = nowMs
                return
            }
            if ((nowMs - mainWin.titlebarOutSinceMs) < Math.max(1, mainWin.recoveryAutoClampDelayMs)) {
                return
            }
            mainWin.titlebarOutSinceMs = 0
            mainWin.clampTitlebarToVisible("auto-clamp")
        }
    }

    Timer {
        id: hostReassertTimer
        interval: 30
        repeat: true
        running: false
        onTriggered: {
            if (mainWin.hostReassertAttemptsRemaining <= 0) {
                stop()
                return
            }
            mainWin.hostReassertAttemptsRemaining = mainWin.hostReassertAttemptsRemaining - 1
            mainWin.reassertHostWindowGeometry(mainWin.hostReassertReason + "-tick" + (8 - mainWin.hostReassertAttemptsRemaining))
            if (!mainWin.hostWindowOutOfSync(1)) {
                stop()
            }
        }
    }

    Timer {
        id: cornerForensicBurstTimer
        interval: 16
        repeat: true
        running: false
        onTriggered: {
            if (!mainWin.phaseLoggingEnabled
                || !mainWin.cornerForensicLoggingEnabled
                || !mainWin.cornerForensicBurstEnabled
                || mainWin.forceClose
                || mainWin.cornerForensicBurstRemaining <= 0) {
                stop();
                return;
            }
            var remaining = mainWin.cornerForensicBurstRemaining;
            mainWin.logCornerForensics("burst-" + mainWin.cornerForensicBurstReason + "-t" + remaining);
            mainWin.cornerForensicBurstRemaining = remaining - 1;
            if (mainWin.cornerForensicBurstRemaining <= 0) {
                mainWin.logCornerForensics("burst-end-" + mainWin.cornerForensicBurstReason);
                stop();
            }
        }
    }

    Timer {
        id: cornerForensicTimer
        interval: 450
        repeat: true
        running: mainWin.phaseLoggingEnabled
            && mainWin.cornerForensicLoggingEnabled
            && mainWin.launchConfigured
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.forceClose
        onTriggered: {
            mainWin.logCornerForensics("timer");
        }
    }
    
    // ============================================================
    // GLOW SHRINKAGE (VISUAL EFFECT ONLY)
    // ============================================================
    
    function performGlowShrinkage() {
        glowShrinkAnimation.start();
    }
    
    ParallelAnimation {
        id: glowShrinkAnimation
        property int targetPadding: mainWin.settledPaddingPx()
        
        PropertyAnimation {
            target: mainWin
            property: "glowPadding"
            duration: mainWin.lowPerformanceMode ? 120 : 180
            easing.type: Easing.InOutQuad
            from: mainWin.glowPadding
            to: glowShrinkAnimation.targetPadding
        }
        
        NumberAnimation {
            duration: mainWin.lowPerformanceMode ? 120 : 180
        }
    }
    
    // ============================================================
    // JELLY CONTROLLER (Embedded, No Overlays)
    // ============================================================
    
    JellyController {
        id: jelly
        appRef: mainWin.appRef
        lowPerformanceMode: mainWin.lowPerformanceMode
        openStyle: mainWin.detachedMode ? "blobPop" : "drop"
        
        onGeometryCalculated: (vx, vy, vw, vh) => {
            var calcStartMs = Date.now();
            mainWin.lagLog("jelly.onGeometryCalculated start vx=" + Math.round(vx)
                + " vy=" + Math.round(vy)
                + " vw=" + Math.round(vw)
                + " vh=" + Math.round(vh));

            var tResolveStart = Date.now();
            var selected = mainWin.resolveTargetScreen();
            var resolveMs = Date.now() - tResolveStart;
            if (!selected) {
                mainWin.lagLog("jelly.onGeometryCalculated abort: resolveTargetScreen failed resolveMs=" + resolveMs);
                return;
            }

            var tApplyStart = Date.now();
            var applied = mainWin.applyGeometryToTargetScreen();
            var applyMs = Date.now() - tApplyStart;
            if (!applied) {
                mainWin.lagLog("jelly.onGeometryCalculated abort: applyGeometryToTargetScreen failed"
                    + " resolveMs=" + resolveMs
                    + " applyMs=" + applyMs);
                return;
            }
            if (mainWin.startupFastLaunchFocusEnabled && !mainWin.detachedMode) {
                Qt.callLater(function() {
                    mainWin.forceLaunchFocus();
                });
            } else {
                mainWin.forceLaunchFocus();
            }
            
            var tCanvasStart = Date.now();
            mainWin.animationPhase = "opening";
            mainWin.updateCanvasGeometry();
            var canvasMs = Date.now() - tCanvasStart;

            // Ensure opening animation uses the opening canvas (visible monitor area) as the floor basis.
            jelly.screenWidth = Math.max(1, mainWin.activeVisibleRect.w);
            jelly.screenHeight = Math.max(1, mainWin.activeVisibleRect.h);
            if (mainWin.detachedMode) {
                jelly.openStartTransY = 0;
                jelly.openImpactTransY = 0;
                jelly.openImpactScaleX = 1.0;
                jelly.openImpactScaleY = 1.0;
                jelly.transY = 0;
            } else {
                // Main-shell open: motion targets are derived from the visual bounds,
                // including rounded-corner/effect bleed, not just the content rect.
                jelly.openStartTransY = mainWin.openingStartTransY();
                jelly.transY = jelly.openStartTransY;
                jelly.openImpactTransY = mainWin.openingImpactTransY();
                jelly.openImpactScaleX = mainWin.openingImpactScaleXTarget();
                jelly.openImpactScaleY = mainWin.openingImpactScaleYTarget();
            }

            mainWin.lagLog("jelly.onGeometryCalculated prepared"
                + " resolveMs=" + resolveMs
                + " applyMs=" + applyMs
                + " canvasMs=" + canvasMs
                + " totalMs=" + (Date.now() - calcStartMs)
                + " finalRect=" + Math.round(mainWin.finalX) + "," + Math.round(mainWin.finalY)
                + " " + Math.round(mainWin.finalW) + "x" + Math.round(mainWin.finalH)
                + " openStartY=" + Math.round(jelly.openStartTransY)
                + " openImpactY=" + Math.round(jelly.openImpactTransY)
                + " impactScale=" + jelly.openImpactScaleX.toFixed(3) + "," + jelly.openImpactScaleY.toFixed(3)
                + " bleed=" + Math.round(mainWin.openingVisualBleedPx())
                + " frameInset=" + Math.round(mainWin.openingFrameInsetPx()));

            mainWin.markStartupFirstPixelVisible("jelly.onGeometryCalculated");
            mainWin.lagLog("jelly.fireOpen dispatch totalMs=" + (Date.now() - calcStartMs));
            if (mainWin.appStyle === "Professional") {
                jelly.opacityVal = 1.0;
                jelly.scaleX = 1.0;
                jelly.scaleY = 1.0;
                jelly.transX = 0.0;
                jelly.transY = 0.0;
                jelly.rotationVal = 0.0;
                mainWin.transitionToSettled();
            } else {
                jelly.fireOpen();
            }
        }
        
        onReadyForHandoff: {
            mainWin.transitionToSettled();
        }

        onOpenFloorImpact: (strengthNorm) => {
            if (mainWin.detachedMode) return;
            var s = isFinite(strengthNorm) ? Math.max(0.0, Math.min(1.0, strengthNorm)) : 0.92;
            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                mainWin.sfxBusRef.playWindowSettle("launch", s);
            }
        }
        
        onCloseFinished: {
            mainWin.finalizeCloseSequence("jelly-close-finished");
        }

        onExitFromTrayFinished: {
            mainWin.phaseLog("EXIT", "jelly-exit-from-tray-finished -> finalizeCloseSequence");
            mainWin.isExitingFromTray = false;
            mainWin.finalizeCloseSequence("tray-exit-finished");
        }

        onMinimizeFinished: {
            mainWin.phaseLog("MINIMIZE", "jelly-minimize-finished -> " + (mainWin.isMinimizingToTray ? "hide to tray" : "showMinimized"));
            mainWin.isMinimizing = false;
            mainWin.wasWindowMinimized = true;
            if (mainWin.isMinimizingToTray) {
                // Show keep-alive window BEFORE hiding — prevents lastWindowClosed
                trayKeepAlive.visible = true;
                mainWin.hide();
                // Cross-monitor: launch overlay comet from window center to tray
                if (mainWin._crossMonitorTrayFlight) {
                    mainWin._pendingTrayAction = "";
                    var overlay = mainWin._ensureCrossMonitorOverlay();
                    if (overlay) {
                        var dist = Math.sqrt(
                            Math.pow(mainWin._trayTargetGlobalX - mainWin._windowCenterGlobalX, 2) +
                            Math.pow(mainWin._trayTargetGlobalY - mainWin._windowCenterGlobalY, 2)
                        );
                        var durationMs = Math.round(Math.min(800, Math.max(400, dist * 0.3)));
                        overlay.launchFlight(
                            mainWin._windowCenterGlobalX, mainWin._windowCenterGlobalY,
                            mainWin._trayTargetGlobalX,   mainWin._trayTargetGlobalY,
                            mainWin._vdX, mainWin._vdY, mainWin._vdW, mainWin._vdH,
                            durationMs
                        );
                    }
                    mainWin._crossMonitorTrayFlight = false;
                }
                try {
                    systemTrayToastWindow.showToast("CSPM is running in the system tray");
                } catch(e) {
                }
                if (typeof trayController !== "undefined" && trayController.show_tray_toast) {
                    trayController.show_tray_toast("CSPM is running in the system tray");
                }
            } else {
                mainWin.showMinimized();
            }
        }

        onRestoreFinished: {
            mainWin.phaseLog("RESTORE", "jelly-restore-finished -> settled");
            mainWin.isRestoringFromMinimize = false;
            mainWin.wasWindowMinimized = false;
            mainWin.minimizeRestorePending = false;
            mainWin.geometryTransitionSuppressed = true;
            mainWin.applyHostEnvelopeForTarget();
            mainWin.updateCanvasGeometry();
            Qt.callLater(function() {
                mainWin.geometryTransitionSuppressed = false;
            });
            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playWindowSettle) {
                mainWin.sfxBusRef.playWindowSettle("restore", 0.45);
            }
        }
    }
    
    // ============================================================
    // ANIMATION CANVAS (Unified, Three-Phase)
    // ============================================================
    
    Item {
        id: animationCanvasLayer
        visible: !mainWin.isExitingFromTray && !mainWin.startupCinematicSnapshotActive
        // Canvas is a dynamic rectangle inside a fixed host window.
        x: mainWin.canvasLocalX
        y: mainWin.canvasLocalY
        width: mainWin.canvasW
        height: mainWin.canvasH
        property bool roundedClipActive: mainWin.shellRoundedMaskActive()
        property real openingRenderScaleX: mainWin.openingSafeScaleX(jelly.scaleX, jelly.transX)
        property real openingRenderScaleY: mainWin.openingSafeScaleY(jelly.scaleY)
        property real openingRenderTransX: mainWin.openingSafeTransX(jelly.transX, openingRenderScaleX)
        property real openingRenderTransY: mainWin.openingSafeTransY(jelly.transY, openingRenderScaleY)
        onRoundedClipActiveChanged: {
            mainWin.mainContentRoundedMaskActive = roundedClipActive;
            mainWin.logCornerForensics("shell-mask-state");
            if (mainWin.animationPhase === "opening" || mainWin.animationPhase === "settled") {
                mainWin.startCornerForensicBurst("shell-mask-state", 40);
            }
        }
        Component.onCompleted: {
            mainWin.mainContentRoundedMaskActive = roundedClipActive;
        }
        // Disable clip for opening/closing/minimizing/restoring/fallback-drag/maximize-fx to avoid edge crop artifacts.
        clip: !(mainWin.animationPhase === "opening"
            || mainWin.animationPhase === "closing"
            || mainWin.isMinimizing
            || mainWin.isRestoringFromMinimize
            || mainWin.isExitingFromTray
            || (mainWin.animationPhase === "settled"
                && (mainWin.userMoveInProgress || mainWin.userResizeInProgress))
            || (mainWin.animationPhase === "settled"
                && mainWin.dragFxVisible())
            || (mainWin.animationPhase === "settled"
                && mainWin.maximizeAnimInProgress))
        layer.enabled: roundedClipActive && !mainWin.isMinimizing && !mainWin.isRestoringFromMinimize && !mainWin.isClosing && !mainWin.isExitingFromTray
        layer.smooth: true
        layer.effect: MultiEffect {
            maskEnabled: animationCanvasLayer.roundedClipActive && !mainWin.isMinimizing && !mainWin.isRestoringFromMinimize && !mainWin.isClosing && !mainWin.isExitingFromTray
            maskSource: animationCanvasMaskSource
            maskThresholdMin: 0.74
            maskSpreadAtMin: 0.10
            autoPaddingEnabled: false
        }

        Rectangle {
            id: animationCanvasMaskSource
            anchors.fill: parent
            radius: mainWin.shellVisualCornerRadiusPx()
            color: "black"
            visible: false
            antialiasing: true
            smooth: true
            layer.enabled: true
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.NoButton
            hoverEnabled: true
            enabled: mainWin.hoverActivateEnabled
                && mainWin.animationPhase === "settled"
                && !mainWin.isClosing
                && !mainWin.isMinimizing
                && !mainWin.isRestoringFromMinimize
            onEntered: mainWin.requestHoverActivation()
        }
         
        // Keep the canvas stable during launch. Opening deformation is applied to
        // contentLayer so the canvas cannot become a clipped viewport.
        transform: [
            Scale {
                origin.x: mainWin.contentLocalX + (mainWin.finalW / 2)
                origin.y: mainWin.contentLocalY + (mainWin.finalH / 2)
                xScale: (mainWin.animationPhase === "opening")
                    ? 1.0
                    : ((mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized)
                        ? jelly.scaleX
                        : ((mainWin.animationPhase !== "settled") ? jelly.scaleX : mainWin.settledScaleX()))
                yScale: (mainWin.animationPhase === "opening")
                    ? 1.0
                    : ((mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized)
                        ? jelly.scaleY
                        : ((mainWin.animationPhase !== "settled") ? jelly.scaleY : mainWin.settledScaleY()))
            },
            Translate {
                x: (mainWin.animationPhase === "opening")
                    ? 0.0
                    : ((mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized)
                        ? jelly.transX
                        : ((mainWin.animationPhase !== "settled") ? jelly.transX : mainWin.settledTransX()))
                y: (mainWin.animationPhase === "opening")
                    ? 0.0
                    : ((mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized)
                        ? jelly.transY
                        : ((mainWin.animationPhase !== "settled") ? jelly.transY : mainWin.settledTransY()))
            },
            Rotation {
                origin.x: mainWin.contentLocalX + (mainWin.finalW / 2)
                origin.y: mainWin.contentLocalY + (mainWin.finalH / 2)
                angle: (mainWin.animationPhase === "opening")
                    ? 0.0
                    : ((mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized)
                        ? jelly.rotationVal
                        : ((mainWin.animationPhase !== "settled") ? jelly.rotationVal : mainWin.settledRotate()))
            }
        ]

        opacity: mainWin.isExitingFromTray ? 0.0 : ((mainWin.animationPhase === "closing" || mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.wasWindowMinimized) ? jelly.opacityVal : 1.0)

        // CONTENT LAYER - Position within canvas keeps window pixels fixed
        Item {
            id: contentLayer
            x: mainWin.contentLocalX
            y: mainWin.contentLocalY
            width: mainWin.userResizeInProgress
                ? Math.max(1, Math.round(mainWin.resizeStartFinalW))
                : mainWin.finalW
            height: mainWin.userResizeInProgress
                ? Math.max(1, Math.round(mainWin.resizeStartFinalH))
                : mainWin.finalH
            clip: !(mainWin.animationPhase === "opening"
                || mainWin.startupPhase === "falling-window"
                || mainWin.startupCinematicBloomActive)
            layer.enabled: mainWin.userResizeInProgress
            layer.smooth: !mainWin.userResizeInProgress
            transform: [
                Scale {
                    origin.x: mainWin.startupCinematicBloomActive
                        ? mainWin.startupCinematicBloomOriginX()
                        : ((mainWin.animationPhase === "opening")
                        ? (Math.max(1, mainWin.finalW) / 2.0)
                        : 0)
                    origin.y: mainWin.startupCinematicBloomActive
                        ? mainWin.startupCinematicBloomOriginY()
                        : ((mainWin.animationPhase === "opening")
                        ? Math.max(1, mainWin.finalH)
                        : 0)
                    xScale: mainWin.startupCinematicBloomActive
                        ? mainWin.startupCinematicBloomScale
                        : ((mainWin.animationPhase === "opening")
                        ? animationCanvasLayer.openingRenderScaleX
                        : ((mainWin.userResizeInProgress && contentLayer.width > 0)
                            ? (mainWin.finalW / contentLayer.width)
                            : 1.0))
                    yScale: mainWin.startupCinematicBloomActive
                        ? mainWin.startupCinematicBloomScale
                        : ((mainWin.animationPhase === "opening")
                        ? animationCanvasLayer.openingRenderScaleY
                        : ((mainWin.userResizeInProgress && contentLayer.height > 0)
                            ? (mainWin.finalH / contentLayer.height)
                            : 1.0))
                },
                Translate {
                    x: (mainWin.animationPhase === "opening")
                        ? animationCanvasLayer.openingRenderTransX
                        : 0.0
                    y: (mainWin.animationPhase === "opening")
                        ? animationCanvasLayer.openingRenderTransY
                        : 0.0
                }
            ]

            HoverHandler {
                acceptedDevices: PointerDevice.Mouse
                enabled: mainWin.hoverActivateEnabled
                    && mainWin.animationPhase === "settled"
                    && !mainWin.isClosing
                    && !mainWin.isMinimizing
                    && !mainWin.isRestoringFromMinimize
                onHoveredChanged: {
                    if (hovered) {
                        mainWin.requestHoverActivation();
                    }
                }
            }
             
            Item {
                id: masterBody
                anchors.fill: parent
                
                ChromeSurface {
                    id: unifiedChrome
                    anchors.fill: parent
                    metrics: mainWin.uiMetrics
                    farGlowEnabled: !(mainWin.lowPerformanceMode || mainWin.userResizeInProgress)
                    glowRadiusNear: mainWin.userResizeInProgress ? 0 : mainWin.chromeGlowNearPx()
                    glowRadiusFar: mainWin.userResizeInProgress ? 0 : mainWin.chromeGlowFarPx()
                    plasmaOpacity: (mainWin.lowPerformanceMode || mainWin.userResizeInProgress) ? 0.0 : 1.0
                    lowFxMode: mainWin.lowPerformanceMode || mainWin.userResizeInProgress
                    interactionBoost: (mainWin.animationPhase !== "settled")
                        ? 0.22
                        : (mainWin.userResizeInProgress ? 0.0 : ((mainWin.userMoveInProgress || mainWin.dragFxVisible()) ? 0.16 : 0.05))
                    premiumEdgeEnabled: !mainWin.userResizeInProgress
                    flairEnabled: !mainWin.userResizeInProgress
                    t: mainWin.t
                    cornerRadius: ((mainWin.animationPhase === "settled")
                            ? mainWin.shellVisualCornerRadiusPx()
                            : mainWin.chromeCornerRadiusPx())
                        + ((mainWin.animationPhase === "settled" && !mainWin.maximizeAnimInProgress)
                            ? mainWin.dragFxCornerBoost : 0)

                    MainContent {
                        id: mainContent
                        anchors.fill: parent
                        t: mainWin.t
                        sfxBus: mainWin.sfxBusRef
                        metrics: mainWin.uiMetrics
                        appRef: mainWin.appRef
                        chromeCornerRadius: unifiedChrome.cornerRadius
                        roundedRootMaskEnabled: mainWin.mainContentRoundedMaskActive
                            && !mainWin.userResizeInProgress
                        initialTileIndex: mainWin.detachedMode ? mainWin.detachedInitialTileIndex : -1
                        initialPanelState: mainWin.detachedMode ? mainWin.detachedInitialPanelState : null
                        detachedWindow: mainWin.detachedMode
                        isInteractive: mainWin.isSettled
                            && !mainWin.isClosing
                            && !mainWin.isMinimizing
                            && !mainWin.isRestoringFromMinimize
                            && !mainWin.maximizeAnimInProgress
                            && !mainWin.userResizeInProgress
                        windowRef: mainWin
                        onTearAwayRequested: function(tileIndex, titleText, state, originRect) {
                            if (mainWin.detachedMode) {
                                mainWin.handleReturnToDock(tileIndex, titleText, state, originRect);
                                return;
                            }
                            mainWin.launchDetachedPanel(tileIndex, titleText, state, originRect, mainContent);
                        }
                        onDockRequested: function(tileIndex, titleText, state, originRect) {
                            mainWin.handleReturnToDock(tileIndex, titleText, state, originRect);
                        }
                        onUndockRequested: function(tileIndex, titleText, state, originRect) {
                            if (mainWin.detachedMode) {
                                mainWin.handleReturnToDock(tileIndex, titleText, state, originRect);
                                return;
                            }
                            mainWin.launchDetachedPanel(tileIndex, titleText, state, originRect, mainContent);
                        }
                    }
                }
                
                // TITLEBAR FOR DRAGGING (only interactive when settled)
                Rectangle {
                    id: titleBar
                    width: parent.width
                    height: mainWin.titleBarHeightPx()
                    color: "transparent"
                    visible: mainWin.isSettled
                        && !mainWin.isClosing
                        && !mainWin.isMinimizing
                        && !mainWin.isRestoringFromMinimize
                        && !mainWin.maximizeAnimInProgress
                    z: 1
                    
                    DragHandler {
                        target: null
                        // Dragging is handled by MainContent header DragHandler.
                        // Keep this disabled to avoid competing drag loops.
                        enabled: false
                        property real startFinalX: 0
                        property real startFinalY: 0
                        property real lastTranslationX: 0
                        property real lastTranslationY: 0
                        onActiveChanged: {
                            mainWin.userMoveInProgress = active;
                            if (active) {
                                startFinalX = mainWin.finalX;
                                startFinalY = mainWin.finalY;
                                lastTranslationX = translation.x;
                                lastTranslationY = translation.y;
                            } else {
                                lastTranslationX = 0;
                                lastTranslationY = 0;
                            }
                        }
                        onTranslationChanged: {
                            if (!active) return;
                            var dx = translation.x - lastTranslationX;
                            var dy = translation.y - lastTranslationY;
                            lastTranslationX = translation.x;
                            lastTranslationY = translation.y;

                            var nx = Math.round(mainWin.finalX + dx);
                            var ny = Math.round(mainWin.finalY + dy);

                            if (mainWin.usableW > 0 && mainWin.usableH > 0) {
                                nx = Math.max(mainWin.usableX, Math.min(nx, mainWin.usableX + mainWin.usableW - mainWin.finalW));
                                ny = Math.max(mainWin.usableY, Math.min(ny, mainWin.usableY + mainWin.usableH - mainWin.finalH));
                            }

                            if (nx !== mainWin.finalX || ny !== mainWin.finalY) {
                                mainWin.finalX = nx;
                                mainWin.finalY = ny;
                                mainWin.updateCanvasGeometry();
                            }
                        }
                    }
                }
            }
        }
    }

    // Act III visual owner. It is a frozen GPU canvas captured while the
    // native splash is still in front, so nothing other than this image can
    // appear between the plasma's centre point and the growing app surface.
    Image {
        id: startupCinematicBloomSnapshot
        x: mainWin.canvasLocalX
        y: mainWin.canvasLocalY
        width: Math.max(1, mainWin.canvasW)
        height: Math.max(1, mainWin.canvasH)
        z: 1750
        visible: mainWin.startupCinematicSnapshotActive
            && mainWin.startupCinematicSnapshotUrl.length > 0
        source: mainWin.startupCinematicSnapshotUrl
        fillMode: Image.Stretch
        smooth: true
        mipmap: true
        asynchronous: false
        transform: Scale {
            origin.x: mainWin.startupCinematicBloomCanvasOriginX()
            origin.y: mainWin.startupCinematicBloomCanvasOriginY()
            xScale: mainWin.startupCinematicBloomActive
                ? mainWin.startupCinematicBloomScale : 1.0
            yScale: mainWin.startupCinematicBloomActive
                ? mainWin.startupCinematicBloomScale : 1.0
        }
    }

    Rectangle {
        id: startupDataLoadingOverlay
        anchors.fill: parent
        z: 1700
        // Temporarily disabled per UX request; keep code for future re-enable.
        visible: false
        // visible: !mainWin.detachedMode
        //     && mainWin.isSettled
        //     && mainWin.startupDataBootStarted
        //     && !mainWin.startupDataBootComplete
        color: Qt.rgba(0.02, 0.03, 0.07, 0.74)

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            preventStealing: true
            onPressed: function(mouse) { mouse.accepted = true; }
            onReleased: function(mouse) { mouse.accepted = true; }
            onWheel: function(wheel) { wheel.accepted = true; }
        }

        Rectangle {
            width: Math.max(320, Math.round(startupDataLoadingOverlay.width * 0.34))
            height: 92
            radius: 14
            x: {
                var canvasLeft = Math.max(0, mainWin.canvasLocalX)
                var canvasWidth = Math.max(1, mainWin.canvasW)
                var leftBound = canvasLeft + 16
                var rightBound = canvasLeft + canvasWidth - width - 16
                if (rightBound < leftBound) {
                    return Math.max(8, startupDataLoadingOverlay.width - width - 8)
                }
                return rightBound
            }
            y: {
                var canvasTop = Math.max(0, mainWin.canvasLocalY)
                var canvasHeight = Math.max(1, mainWin.canvasH)
                var topBound = canvasTop + 16
                var bottomBound = canvasTop + canvasHeight - height - 16
                if (bottomBound < topBound) {
                    return Math.max(8, startupDataLoadingOverlay.height - height - 8)
                }
                return bottomBound
            }
            color: Qt.alpha(mainWin.t.panel, 0.96)
            border.width: 1
            border.color: Qt.alpha(mainWin.t.accent, 0.48)

            Column {
                anchors.centerIn: parent
                spacing: 8

                Text {
                    text: "Loading Data - Please Wait"
                    color: Qt.alpha(mainWin.t.text, 0.98)
                    font.pixelSize: Math.max(14, Math.round(mainWin.ratioToPixels(0.014, mainWin.width, mainWin.height, 14)))
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "Initializing workbook data and indexes..."
                    color: Qt.alpha(mainWin.t.text, 0.72)
                    font.pixelSize: Math.max(11, Math.round(mainWin.ratioToPixels(0.010, mainWin.width, mainWin.height, 11)))
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    // The native splash handles input during Acts I/II.  Once it has vanished,
    // this short-lived shield completes the promised click-to-skip contract
    // while Act III grows the already-hydrated window from its centre point.
    MouseArea {
        anchors.fill: parent
        z: 1801
        visible: mainWin.startupCinematicBloomActive
        enabled: visible
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
        preventStealing: true
        onPressed: function(mouse) {
            mainWin.skipStartupCinematicBloom("pointer")
            mouse.accepted = true
        }
    }

    Item {
        id: resizeHandlesLayer
        x: mainWin.canvasLocalX
        y: mainWin.canvasLocalY
        width: Math.max(1, mainWin.canvasW)
        height: Math.max(1, mainWin.canvasH)
        z: 1520
        visible: mainWin.launchConfigured
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.isMinimizing
            && !mainWin.isRestoringFromMinimize
            && !mainWin.maximizeAnimInProgress
            && !mainWin.uiMaximized
            && mainWin.strictResizePipelineEnabled

        property int edgePx: mainWin.resizeHandleThicknessPx()
        property int cornerPx: Math.min(Math.max(1, width), Math.min(Math.max(1, height), mainWin.resizeCornerSizePx()))

        function sampleHandleCursor(mouseEvent, areaX, areaY) {
            if (!mouseEvent) return false
            if (typeof mouseEvent.x !== "number" || typeof mouseEvent.y !== "number") return false

            var baseX = isFinite(areaX) ? areaX : 0
            var baseY = isFinite(areaY) ? areaY : 0
            var mapped = null
            try {
                mapped = resizeHandlesLayer.mapToGlobal(baseX + mouseEvent.x, baseY + mouseEvent.y)
            } catch (e) {
                mapped = null
            }
            if (mapped && typeof mapped.x === "number" && typeof mapped.y === "number"
                && isFinite(mapped.x) && isFinite(mapped.y)) {
                mainWin.resizeLiveCursorX = Math.round(mapped.x)
                mainWin.resizeLiveCursorY = Math.round(mapped.y)
            } else {
                mainWin.resizeLiveCursorX = Math.round(mainWin.x + resizeHandlesLayer.x + baseX + mouseEvent.x)
                mainWin.resizeLiveCursorY = Math.round(mainWin.y + resizeHandlesLayer.y + baseY + mouseEvent.y)
            }
            mainWin.resizeLiveCursorValid = true
            mainWin.resizeLiveCursorSampleMs = Date.now()
            return true
        }

        function beginHandle(handleName, mouseEvent, areaX, areaY) {
            sampleHandleCursor(mouseEvent, areaX, areaY)
            mainWin.geometryTransitionSuppressed = true
            if (!mainWin.beginUserResize(handleName)) {
                if (!mainWin.userMoveInProgress && !mainWin.userResizeInProgress) {
                    mainWin.geometryTransitionSuppressed = false
                }
                mouseEvent.accepted = false
                return
            }
        }

        function moveHandle(mouseEvent, areaX, areaY) {
            sampleHandleCursor(mouseEvent, areaX, areaY)
            mainWin.updateUserResize(0, 0)
        }

        function endHandle() {
            mainWin.finishUserResize()
        }

        MouseArea {
            x: resizeHandlesLayer.cornerPx
            y: 0
            width: Math.max(1, resizeHandlesLayer.width - (resizeHandlesLayer.cornerPx * 2))
            height: resizeHandlesLayer.edgePx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeVerCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("n", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: resizeHandlesLayer.cornerPx
            y: resizeHandlesLayer.height - resizeHandlesLayer.edgePx
            width: Math.max(1, resizeHandlesLayer.width - (resizeHandlesLayer.cornerPx * 2))
            height: resizeHandlesLayer.edgePx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeVerCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("s", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: 0
            y: resizeHandlesLayer.cornerPx
            width: resizeHandlesLayer.edgePx
            height: Math.max(1, resizeHandlesLayer.height - (resizeHandlesLayer.cornerPx * 2))
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeHorCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("w", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: resizeHandlesLayer.width - resizeHandlesLayer.edgePx
            y: resizeHandlesLayer.cornerPx
            width: resizeHandlesLayer.edgePx
            height: Math.max(1, resizeHandlesLayer.height - (resizeHandlesLayer.cornerPx * 2))
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeHorCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("e", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: 0
            y: 0
            width: resizeHandlesLayer.cornerPx
            height: resizeHandlesLayer.cornerPx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeFDiagCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("nw", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: resizeHandlesLayer.width - resizeHandlesLayer.cornerPx
            y: 0
            width: resizeHandlesLayer.cornerPx
            height: resizeHandlesLayer.cornerPx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeBDiagCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("ne", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: 0
            y: resizeHandlesLayer.height - resizeHandlesLayer.cornerPx
            width: resizeHandlesLayer.cornerPx
            height: resizeHandlesLayer.cornerPx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeBDiagCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("sw", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }

        MouseArea {
            x: resizeHandlesLayer.width - resizeHandlesLayer.cornerPx
            y: resizeHandlesLayer.height - resizeHandlesLayer.cornerPx
            width: resizeHandlesLayer.cornerPx
            height: resizeHandlesLayer.cornerPx
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeFDiagCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) { resizeHandlesLayer.beginHandle("se", mouse, x, y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) resizeHandlesLayer.moveHandle(mouse, x, y) }
            onReleased: resizeHandlesLayer.endHandle()
            onCanceled: resizeHandlesLayer.endHandle()
        }
    }

    Item {
        id: topEdgeRecoveryBand
        x: mainWin.activeVisibleRect.x - mainWin.x
        y: mainWin.activeVisibleRect.y - mainWin.y
        width: Math.max(1, mainWin.activeVisibleRect.w)
        height: Math.max(1, mainWin.recoveryBandHeight)
        z: 1505
        visible: mainWin.launchConfigured
            && mainWin.recoveryBandEnabled
            && mainWin.animationPhase === "settled"
            && !mainWin.isClosing
            && !mainWin.isMinimizing
            && !mainWin.isRestoringFromMinimize
            && !mainWin.maximizeAnimInProgress
        enabled: visible

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            hoverEnabled: true
            cursorShape: Qt.SizeAllCursor
            preventStealing: true
            propagateComposedEvents: false
            onPressed: function(mouse) {
                mainWin.geometryTransitionSuppressed = true
                var started = mainWin.beginHeaderDrag(0, 1)
                mouse.accepted = started || mainWin.userMoveInProgress
                if (!mouse.accepted && !mainWin.userMoveInProgress && !mainWin.userResizeInProgress) {
                    mainWin.geometryTransitionSuppressed = false
                }
            }
            onPositionChanged: function(mouse) {
                if (mouse.buttons & Qt.LeftButton) {
                    mainWin.applyFallbackDragFromCursor()
                }
            }
            onReleased: {
                if (mainWin.userMoveInProgress || mainWin.systemMoveInProgress) {
                    mainWin.finishUserDrag()
                }
            }
            onCanceled: {
                if (mainWin.userMoveInProgress || mainWin.systemMoveInProgress) {
                    mainWin.finishUserDrag()
                }
            }
        }
    }

    Canvas {
        id: closingAccretionCanvas
        x: 0
        y: 0
        width: mainWin.width
        height: mainWin.height
        visible: mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.isExitingFromTray
        z: 999999

        property var particles: []
        property bool initialized: false

        function initParticles() {
            var pts = [];
            for (var i = 0; i < 250; i++) {
                pts.push({
                    "angle": Math.random() * Math.PI * 2,
                    "distRatio": 0.15 + Math.random() * 0.85,
                    "speed": 1.8 + Math.random() * 3.6,
                    "size": 1.2 + Math.random() * 2.8,
                    "alpha": 0.25 + Math.random() * 0.75
                });
            }
            particles = pts;
            initialized = true;
        }

        Connections {
            target: jelly
            function onCloseProgressChanged() {
                closingAccretionCanvas.requestPaint();
            }
            function onMinimizeProgressChanged() {
                closingAccretionCanvas.requestPaint();
            }
            function onExitFromTrayProgressChanged() {
                closingAccretionCanvas.requestPaint();
            }
        }

        onPaint: {
            var ctx = getContext("2d");
            if (!ctx) return;
            var w = width;
            var h = height;
            ctx.clearRect(0, 0, w, h);

            var isExitTray = mainWin.isExitingFromTray;
            var isMin = mainWin.isMinimizing || mainWin.isRestoringFromMinimize;
            var rawP = isExitTray ? jelly.exitFromTrayProgress : (isMin ? jelly.minimizeProgress : jelly.closeProgress);
            var p = Math.max(0.0, Math.min(1.0, rawP));
            if (p <= 0.0001 || p >= 0.9999) return;
            if (!initialized) initParticles();

            var centerSingX = mainWin.width / 2.0;
            var centerSingY = mainWin.height / 2.0;
            var singX = centerSingX;
            var singY = centerSingY;

            if (isExitTray) {
                // ============================================================
                // SYSTEM TRAY EXIT ENGINE (TRAY SHOOT -> CENTER BURST & HANG -> SINGULARITY SUCK -> CLOSE)
                // ============================================================
                var targetDistX = jelly.taskbarTargetDistX;
                var targetDistY = jelly.taskbarTargetDistY;
                var angleTheta = Math.atan2(targetDistY, targetDistX);
                var cosA = Math.cos(angleTheta);
                var sinA = Math.sin(angleTheta);

                if (p < 0.35) {
                    // Stage 1 (0.00 to 0.35): White comet launches from system tray and shoots along straight trajectory to center
                    var upP = p / 0.35; // 0.0 to 1.0
                    var upEase = Math.sin(upP * Math.PI * 0.5); // Smooth deceleration approaching center
                    var curX = (centerSingX + targetDistX) - (upEase * targetDistX);
                    var curY = (centerSingY + targetDistY) - (upEase * targetDistY);
                    var cometRad = 16.0; // 16px comet head

                    // Incandescent comet tail trailing backwards towards tray launch point
                    var tailLen = Math.min(220, 24.0 + ((1.0 - upEase) * 180.0));
                    var tailTipX = curX + (cosA * tailLen);
                    var tailTipY = curY + (sinA * tailLen);

                    var tailGrad = ctx.createLinearGradient(curX, curY, tailTipX, tailTipY);
                    tailGrad.addColorStop(0.00, "rgba(255, 255, 255, 0.90)");
                    tailGrad.addColorStop(0.20, "rgba(254, 240, 138, 0.75)");
                    tailGrad.addColorStop(0.50, "rgba(251, 146, 60, 0.45)");
                    tailGrad.addColorStop(0.80, "rgba(239, 68, 68, 0.15)");
                    tailGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                    ctx.fillStyle = tailGrad;
                    ctx.beginPath();
                    var halfHead = cometRad * 0.90;
                    var perpX = -sinA * halfHead;
                    var perpY = cosA * halfHead;

                    ctx.moveTo(curX + perpX, curY + perpY);
                    ctx.quadraticCurveTo(curX + perpX * 0.4 + cosA * tailLen * 0.6, curY + perpY * 0.4 + sinA * tailLen * 0.6, tailTipX, tailTipY);
                    ctx.quadraticCurveTo(curX - perpX * 0.4 + cosA * tailLen * 0.6, curY - perpY * 0.4 + sinA * tailLen * 0.6, curX - perpX, curY - perpY);
                    ctx.closePath();
                    ctx.fill();

                    // Sparks trailing backwards along launch angle
                    for (var st = 0; st < 14; st++) {
                        var spDist = (st / 14) * tailLen * (0.8 + 0.2 * Math.sin(st * 3.7 + upP * 6.0));
                        var spSpread = Math.sin(st * 5.1 + upP * 8.0) * (halfHead * (1.0 - (spDist / tailLen)));
                        var spX = curX + (cosA * spDist) + (-sinA * spSpread);
                        var spY = curY + (sinA * spDist) + (cosA * spSpread);
                        var spAlpha = Math.max(0.0, 1.0 - (spDist / tailLen));
                        ctx.fillStyle = (st % 2 === 0)
                            ? "rgba(255, 255, 255, " + (spAlpha * 0.9).toFixed(3) + ")"
                            : "rgba(251, 146, 60, " + (spAlpha * 0.8).toFixed(3) + ")";
                        ctx.beginPath();
                        ctx.arc(spX, spY, Math.max(0.5, 1.2 * spAlpha), 0, Math.PI * 2);
                        ctx.fill();
                    }

                    // Hyper-dense white-hot comet head
                    var headGrad = ctx.createRadialGradient(curX, curY, 0.5, curX, curY, cometRad);
                    headGrad.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                    headGrad.addColorStop(0.35, "rgba(255, 255, 255, 0.98)");
                    headGrad.addColorStop(0.60, "rgba(255, 250, 235, 0.80)");
                    headGrad.addColorStop(0.82, "rgba(251, 146, 60, 0.40)");
                    headGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                    ctx.fillStyle = headGrad;
                    ctx.beginPath();
                    ctx.arc(curX, curY, cometRad, 0, Math.PI * 2);
                    ctx.fill();

                } else if (p < 0.58) {
                    // Stage 2 (0.35 to 0.58): Arrives at center, blooms from 16px -> 32px, and HANGS in the middle glowing
                    var midP = (p - 0.35) / 0.23; // 0.0 to 1.0
                    var midEase = Math.sin(midP * Math.PI * 0.5);
                    var midRadius = 16.0 + (midEase * 16.0); // 16px -> 32px

                    // Outer champagne plasma aura
                    var midOuter = ctx.createRadialGradient(centerSingX, centerSingY, midRadius * 0.40, centerSingX, centerSingY, midRadius * 1.22);
                    midOuter.addColorStop(0.00, "rgba(254, 215, 170, 0.28)");
                    midOuter.addColorStop(0.60, "rgba(251, 146, 60, 0.12)");
                    midOuter.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");
                    ctx.fillStyle = midOuter;
                    ctx.beginPath();
                    ctx.arc(centerSingX, centerSingY, midRadius * 1.22, 0, Math.PI * 2);
                    ctx.fill();

                    // Suspended Incandescent Supernova Core (28/72 ratio)
                    var midGrad = ctx.createRadialGradient(centerSingX, centerSingY, 0.5, centerSingX, centerSingY, midRadius);
                    midGrad.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                    midGrad.addColorStop(0.28, "rgba(255, 255, 255, 0.98)");
                    midGrad.addColorStop(0.55, "rgba(255, 250, 235, 0.75)");
                    midGrad.addColorStop(0.78, "rgba(254, 215, 170, 0.35)");
                    midGrad.addColorStop(0.92, "rgba(251, 146, 60, 0.12)");
                    midGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                    ctx.fillStyle = midGrad;
                    ctx.beginPath();
                    ctx.arc(centerSingX, centerSingY, midRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // 16 shimmering ember sparks
                    for (var mk = 0; mk < 16; mk++) {
                        var mkAngle = (mk / 16) * Math.PI * 2 + (midP * 1.6);
                        var mkDist = (midRadius * 0.58) * (0.30 + 0.70 * Math.sin(mk * 5.7 + midP * 4.0));
                        var mkx = centerSingX + Math.cos(mkAngle) * mkDist;
                        var mky = centerSingY + Math.sin(mkAngle) * mkDist;
                        ctx.fillStyle = (mk % 4 === 0)
                            ? "rgba(239, 68, 68, 0.75)"
                            : (mk % 4 === 1)
                                ? "rgba(251, 146, 60, 0.85)"
                                : (mk % 4 === 2)
                                    ? "rgba(254, 240, 138, 0.95)"
                                    : "rgba(255, 255, 255, 0.95)";
                        ctx.beginPath();
                        ctx.arc(mkx, mky, 1.0, 0, Math.PI * 2);
                        ctx.fill();
                    }

                } else if (p < 0.88) {
                    // Stage 3 (0.58 to 0.88): Sucks into itself down to a microscopic center pinpoint (32px -> 0px)
                    var selfSuckP = (p - 0.58) / 0.30; // 0.0 to 1.0
                    var selfShrink = Math.pow(1.0 - selfSuckP, 2.6);
                    var selfRadius = Math.max(0.1, selfShrink * 32.0);
                    var selfAlpha = Math.pow(1.0 - selfSuckP, 2.2);

                    var selfGrad = ctx.createRadialGradient(centerSingX, centerSingY, 0, centerSingX, centerSingY, selfRadius);
                    selfGrad.addColorStop(0.00, "rgba(255, 255, 255, " + selfAlpha.toFixed(3) + ")");
                    selfGrad.addColorStop(0.30, "rgba(255, 255, 255, " + (selfAlpha * 0.90).toFixed(3) + ")");
                    selfGrad.addColorStop(0.65, "rgba(254, 215, 170, " + (selfAlpha * 0.30).toFixed(3) + ")");
                    selfGrad.addColorStop(0.88, "rgba(251, 146, 60, " + (selfAlpha * 0.10).toFixed(3) + ")");
                    selfGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                    ctx.fillStyle = selfGrad;
                    ctx.beginPath();
                    ctx.arc(centerSingX, centerSingY, selfRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // Inward vortex accretion particles
                    for (var vi = 0; vi < particles.length; vi++) {
                        var pt = particles[vi];
                        var pDistRatio = pt.distRatio * (1.0 - selfSuckP);
                        var pDist = pDistRatio * 180.0;
                        if (pDist <= 1.0) continue;
                        var pAng = pt.angle + (selfSuckP * pt.speed * 2.0);
                        var px = centerSingX + Math.cos(pAng) * pDist;
                        var py = centerSingY + Math.sin(pAng) * pDist;
                        var pAlpha = pt.alpha * (1.0 - selfSuckP) * Math.min(1.0, pDist / 30.0);

                        ctx.fillStyle = "rgba(255, 255, 255, " + pAlpha.toFixed(3) + ")";
                        ctx.beginPath();
                        ctx.arc(px, py, pt.size * (1.0 - selfSuckP), 0, Math.PI * 2);
                        ctx.fill();
                    }

                } else {
                    // Stage 4 (0.88 to 1.00): Singular quantum annihilation flash -> pure darkness
                    var finalP = (p - 0.88) / 0.12; // 0.0 to 1.0
                    var finalPulse = Math.max(0.0, (1.0 - finalP) * 1.5);
                    if (finalPulse > 0.01) {
                        ctx.fillStyle = "rgba(255, 255, 255, " + (1.0 - finalP).toFixed(3) + ")";
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, finalPulse, 0, Math.PI * 2);
                        ctx.fill();
                    }
                }
                return;
            }

            if (isMin) {
                var targetDistX = jelly.taskbarTargetDistX;
                var targetDistY = jelly.taskbarTargetDistY;
                var flightDist = Math.sqrt(targetDistX * targetDistX + targetDistY * targetDistY);
                var angleTheta = Math.atan2(targetDistY, targetDistX);
                var cosA = Math.cos(angleTheta);
                var sinA = Math.sin(angleTheta);

                if (mainWin.isRestoringFromMinimize) {
                    // ============================================================
                    // 5-STAGE REVERSE RESTORE ENGINE (2D VECTOR AWARE)
                    // ============================================================
                    // Stage 1 (0.00 to 0.28): Comet shoots UPWARD along straight trajectory vector to center
                    // Stage 2 (0.28 to 0.46): Pauses in the middle, blooms to ~32px, and hangs glowing
                    // Stage 3 (0.46 to 0.62): Disappears into itself down to a center pinpoint (32px -> 0px)
                    // Stage 4 (0.62 to 0.74): Pauses at the microscopic pinpoint
                    // Stage 5 (0.74 to 1.00): Bursts forth from center into final window position

                    if (p < 0.28) {
                        // Stage 1: Comet shoots from destination along trajectory angleTheta up to center
                        var upP = p / 0.28; // 0.0 to 1.0
                        var upEase = Math.sin(upP * Math.PI * 0.5); // Smooth deceleration approaching center
                        var curX = (centerSingX + targetDistX) - (upEase * targetDistX);
                        var curY = (centerSingY + targetDistY) - (upEase * targetDistY);
                        var cometRad = 16.0; // 16px comet head

                        // Incandescent comet tail trailing backwards towards launch point (angleTheta)
                        var tailLen = Math.min(220, 24.0 + ((1.0 - upEase) * 180.0));
                        var tailTipX = curX + (cosA * tailLen);
                        var tailTipY = curY + (sinA * tailLen);

                        var tailGrad = ctx.createLinearGradient(curX, curY, tailTipX, tailTipY);
                        tailGrad.addColorStop(0.00, "rgba(255, 255, 255, 0.90)");
                        tailGrad.addColorStop(0.20, "rgba(254, 240, 138, 0.75)");
                        tailGrad.addColorStop(0.50, "rgba(251, 146, 60, 0.45)");
                        tailGrad.addColorStop(0.80, "rgba(239, 68, 68, 0.15)");
                        tailGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = tailGrad;
                        ctx.beginPath();
                        // Perpendicular vector for the ribbon width
                        var halfHead = cometRad * 0.90;
                        var perpX = -sinA * halfHead;
                        var perpY = cosA * halfHead;

                        ctx.moveTo(curX + perpX, curY + perpY);
                        ctx.quadraticCurveTo(curX + perpX * 0.4 + cosA * tailLen * 0.6, curY + perpY * 0.4 + sinA * tailLen * 0.6, tailTipX, tailTipY);
                        ctx.quadraticCurveTo(curX - perpX * 0.4 + cosA * tailLen * 0.6, curY - perpY * 0.4 + sinA * tailLen * 0.6, curX - perpX, curY - perpY);
                        ctx.closePath();
                        ctx.fill();

                        // Sparks trailing backwards along launch angle
                        for (var st = 0; st < 14; st++) {
                            var spDist = (st / 14) * tailLen * (0.8 + 0.2 * Math.sin(st * 3.7 + upP * 6.0));
                            var spSpread = Math.sin(st * 5.1 + upP * 8.0) * (halfHead * (1.0 - (spDist / tailLen)));
                            var spX = curX + (cosA * spDist) + (-sinA * spSpread);
                            var spY = curY + (sinA * spDist) + (cosA * spSpread);
                            var spAlpha = Math.max(0.0, 1.0 - (spDist / tailLen));
                            ctx.fillStyle = (st % 2 === 0)
                                ? "rgba(255, 255, 255, " + (spAlpha * 0.9).toFixed(3) + ")"
                                : "rgba(251, 146, 60, " + (spAlpha * 0.8).toFixed(3) + ")";
                            ctx.beginPath();
                            ctx.arc(spX, spY, Math.max(0.5, 1.2 * spAlpha), 0, Math.PI * 2);
                            ctx.fill();
                        }

                        // Hyper-dense white-hot comet head
                        var headGrad = ctx.createRadialGradient(curX, curY, 0.5, curX, curY, cometRad);
                        headGrad.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                        headGrad.addColorStop(0.35, "rgba(255, 255, 255, 0.98)");
                        headGrad.addColorStop(0.60, "rgba(255, 250, 235, 0.80)");
                        headGrad.addColorStop(0.82, "rgba(251, 146, 60, 0.40)");
                        headGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = headGrad;
                        ctx.beginPath();
                        ctx.arc(curX, curY, cometRad, 0, Math.PI * 2);
                        ctx.fill();

                    } else if (p < 0.46) {
                        // Stage 2: Arrives at center, blooms from 16px -> 32px, and PAUSES in the middle glowing
                        var midP = (p - 0.28) / 0.18; // 0.0 to 1.0
                        var midEase = Math.sin(midP * Math.PI * 0.5);
                        var midRadius = 16.0 + (midEase * 16.0); // 16px -> 32px

                        // Outer champagne plasma aura
                        var midOuter = ctx.createRadialGradient(centerSingX, centerSingY, midRadius * 0.40, centerSingX, centerSingY, midRadius * 1.22);
                        midOuter.addColorStop(0.00, "rgba(254, 215, 170, 0.28)");
                        midOuter.addColorStop(0.60, "rgba(251, 146, 60, 0.12)");
                        midOuter.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");
                        ctx.fillStyle = midOuter;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, midRadius * 1.22, 0, Math.PI * 2);
                        ctx.fill();

                        // Suspended Incandescent Supernova Core (28/72 ratio)
                        var midGrad = ctx.createRadialGradient(centerSingX, centerSingY, 0.5, centerSingX, centerSingY, midRadius);
                        midGrad.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                        midGrad.addColorStop(0.28, "rgba(255, 255, 255, 0.98)");
                        midGrad.addColorStop(0.55, "rgba(255, 250, 235, 0.75)");
                        midGrad.addColorStop(0.78, "rgba(254, 215, 170, 0.35)");
                        midGrad.addColorStop(0.92, "rgba(251, 146, 60, 0.12)");
                        midGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = midGrad;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, midRadius, 0, Math.PI * 2);
                        ctx.fill();

                        // 16 shimmering ember sparks
                        for (var mk = 0; mk < 16; mk++) {
                            var mkAngle = (mk / 16) * Math.PI * 2 + (midP * 1.6);
                            var mkDist = (midRadius * 0.58) * (0.30 + 0.70 * Math.sin(mk * 5.7 + midP * 4.0));
                            var mkx = centerSingX + Math.cos(mkAngle) * mkDist;
                            var mky = centerSingY + Math.sin(mkAngle) * mkDist;
                            ctx.fillStyle = (mk % 4 === 0)
                                ? "rgba(239, 68, 68, 0.75)"
                                : (mk % 4 === 1)
                                    ? "rgba(251, 146, 60, 0.85)"
                                    : (mk % 4 === 2)
                                        ? "rgba(254, 240, 138, 0.95)"
                                        : "rgba(255, 255, 255, 0.95)";
                            ctx.beginPath();
                            ctx.arc(mkx, mky, 1.0, 0, Math.PI * 2);
                            ctx.fill();
                        }

                    } else if (p < 0.62) {
                        // Stage 3: Disappears into itself down to a center pinpoint (32px -> 0px)
                        var selfSuckP = (p - 0.46) / 0.16; // 0.0 to 1.0
                        var selfShrink = Math.pow(1.0 - selfSuckP, 2.6);
                        var selfRadius = Math.max(0.1, selfShrink * 32.0);
                        var selfAlpha = Math.pow(1.0 - selfSuckP, 2.2);

                        var selfGrad = ctx.createRadialGradient(centerSingX, centerSingY, 0, centerSingX, centerSingY, selfRadius);
                        selfGrad.addColorStop(0.00, "rgba(255, 255, 255, " + selfAlpha.toFixed(3) + ")");
                        selfGrad.addColorStop(0.30, "rgba(255, 255, 255, " + (selfAlpha * 0.90).toFixed(3) + ")");
                        selfGrad.addColorStop(0.65, "rgba(254, 215, 170, " + (selfAlpha * 0.30).toFixed(3) + ")");
                        selfGrad.addColorStop(0.88, "rgba(251, 146, 60, " + (selfAlpha * 0.10).toFixed(3) + ")");
                        selfGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = selfGrad;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, selfRadius, 0, Math.PI * 2);
                        ctx.fill();

                        if (selfRadius > 1.0) {
                            for (var sm = 0; sm < 12; sm++) {
                                var smAngle = (sm / 12) * Math.PI * 2 + (selfSuckP * 2.5);
                                var smDist = selfRadius * 0.45 * (1.0 - selfSuckP * 0.5);
                                var sx = centerSingX + Math.cos(smAngle) * smDist;
                                var sy = centerSingY + Math.sin(smAngle) * smDist;
                                ctx.fillStyle = (sm % 2 === 0)
                                    ? "rgba(255, 255, 255, " + (selfAlpha * 0.95).toFixed(3) + ")"
                                    : "rgba(251, 146, 60, " + (selfAlpha * 0.75).toFixed(3) + ")";
                                ctx.beginPath();
                                ctx.arc(sx, sy, Math.max(0.4, 1.0 * selfShrink), 0, Math.PI * 2);
                                ctx.fill();
                            }
                        }

                    } else if (p < 0.74) {
                        // Stage 4: Pauses again at the microscopic pinpoint (pregnant pause before the bloom)
                        var holdPinP = (p - 0.62) / 0.12; // 0.0 to 1.0
                        var pulseRad = 1.0 + (Math.sin(holdPinP * Math.PI * 2.0) * 0.6); // tiny quantum pulse
                        ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, pulseRad, 0, Math.PI * 2);
                        ctx.fill();

                    } else {
                        // Stage 5: Bursts forth from the center to final position (White-hole outward bloom)
                        var burstP = (p - 0.74) / 0.26; // 0.0 to 1.0
                        var bloomRadius = 2.0 + (Math.sin(burstP * Math.PI * 0.5) * 54.0); // expands 2px -> 56px
                        var bloomAlpha = Math.max(0.0, 1.0 - (burstP * 1.3));

                        if (bloomAlpha > 0.01) {
                            var bloomGrad = ctx.createRadialGradient(centerSingX, centerSingY, 0.5, centerSingX, centerSingY, bloomRadius);
                            bloomGrad.addColorStop(0.00, "rgba(255, 255, 255, " + bloomAlpha.toFixed(3) + ")");
                            bloomGrad.addColorStop(0.35, "rgba(255, 250, 235, " + (bloomAlpha * 0.80).toFixed(3) + ")");
                            bloomGrad.addColorStop(0.70, "rgba(254, 215, 170, " + (bloomAlpha * 0.35).toFixed(3) + ")");
                            bloomGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                            ctx.fillStyle = bloomGrad;
                            ctx.beginPath();
                            ctx.arc(centerSingX, centerSingY, bloomRadius, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }
                } else {
                    // ============================================================
                    // 5-STAGE MINIMIZE TO TASKBAR / SYSTEM TRAY COMET ENGINE (2D VECTOR AWARE)
                    // ============================================================
                    // Stage 1 (0.00 to 0.30): Inward Suction into Center Pinpoint
                    // Stage 2 (0.30 to 0.42): White-Hot Supernova Detonation at Center (~27.5px)
                    // Stage 3 (0.42 to 0.65): Extended Supernova Hang & Gentle Swell (~32px max)
                    // Stage 4 (0.65 to 0.88): Comet Contraction (half radius: 32px -> 16px) & Straight Siphon along angleTheta with Tail
                    // Stage 5 (0.88 to 1.00): Disappears Behind the Taskbar/Tray [ISOLATED MODULAR STAGE]

                    if (p < 0.30) {
                        // Stage 1: Window UI and particle field get sucked straight into the center pinpoint
                        var minSuckP = p / 0.30;
                        var minAuraAlpha = Math.min(1.0, minSuckP * 2.0);
                        var minAuraRadius = Math.max(9, (1.0 - minSuckP * 0.75) * Math.min(mainWin.finalW, mainWin.finalH) * 0.25);

                        var minGrad1 = ctx.createRadialGradient(centerSingX, centerSingY, 2, centerSingX, centerSingY, minAuraRadius);
                        minGrad1.addColorStop(0.00, "rgba(255, 255, 255, " + (minAuraAlpha * 0.95).toFixed(3) + ")");
                        minGrad1.addColorStop(0.35, "rgba(255, 250, 235, " + (minAuraAlpha * 0.70).toFixed(3) + ")");
                        minGrad1.addColorStop(0.70, "rgba(254, 215, 170, " + (minAuraAlpha * 0.25).toFixed(3) + ")");
                        minGrad1.addColorStop(1.00, "rgba(251, 146, 60, 0.0)");

                        ctx.fillStyle = minGrad1;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, minAuraRadius, 0, Math.PI * 2);
                        ctx.fill();

                        for (var mj = 0; mj < particles.length; mj++) {
                            var mpItem = particles[mj];
                            var mcurDist = mpItem.distRatio * (1.0 - Math.pow(minSuckP, 2.0)) * (Math.min(mainWin.finalW, mainWin.finalH) * 0.38);
                            var mpX = centerSingX + Math.cos(mpItem.angle) * mcurDist;
                            var mpY = centerSingY + Math.sin(mpItem.angle) * mcurDist;

                            var mpAlpha = mpItem.alpha * minAuraAlpha;
                            var mpSize = Math.max(0.6, mpItem.size * (1.0 - minSuckP * 0.4));

                            ctx.fillStyle = (mj % 3 === 0)
                                ? "rgba(255, 255, 255, " + mpAlpha.toFixed(3) + ")"
                                : (mj % 3 === 1)
                                    ? "rgba(254, 240, 138, " + mpAlpha.toFixed(3) + ")"
                                    : "rgba(251, 146, 60, " + (mpAlpha * 0.8).toFixed(3) + ")";
                            ctx.beginPath();
                            ctx.arc(mpX, mpY, mpSize, 0, Math.PI * 2);
                            ctx.fill();
                        }

                    } else if (p < 0.42) {
                        // Stage 2: Supernova Detonation (Identical white-hot core & champagne plasma aura)
                        var minBurstP = (p - 0.30) / 0.12;
                        var minBurstEase = Math.sin(minBurstP * Math.PI * 0.5);
                        var minBurstRadius = 2.5 + (minBurstEase * 25.0); // ~27.5px

                        var minGrad2 = ctx.createRadialGradient(centerSingX, centerSingY, 0.5, centerSingX, centerSingY, minBurstRadius);
                        minGrad2.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                        minGrad2.addColorStop(0.28, "rgba(255, 255, 255, 0.98)");
                        minGrad2.addColorStop(0.55, "rgba(255, 250, 235, 0.75)");
                        minGrad2.addColorStop(0.78, "rgba(254, 215, 170, 0.35)");
                        minGrad2.addColorStop(0.92, "rgba(251, 146, 60, 0.14)");
                        minGrad2.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = minGrad2;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, minBurstRadius, 0, Math.PI * 2);
                        ctx.fill();

                        for (var mb = 0; mb < 16; mb++) {
                            var mbAngle = (mb / 16) * Math.PI * 2 + (minBurstP * 1.5);
                            var mbDist = (minBurstRadius * 0.55) * (0.25 + 0.75 * Math.sin(mb * 4.3 + minBurstP * 3.0));
                            var mbx = centerSingX + Math.cos(mbAngle) * mbDist;
                            var mby = centerSingY + Math.sin(mbAngle) * mbDist;
                            ctx.fillStyle = (mb % 4 === 0)
                                ? "rgba(239, 68, 68, 0.75)"
                                : (mb % 4 === 1)
                                    ? "rgba(251, 146, 60, 0.85)"
                                    : (mb % 4 === 2)
                                        ? "rgba(254, 240, 138, 0.95)"
                                        : "rgba(255, 255, 255, 0.95)";
                            ctx.beginPath();
                            ctx.arc(mbx, mby, 0.9 + (minBurstEase * 0.3), 0, Math.PI * 2);
                            ctx.fill();
                        }

                    } else if (p < 0.65) {
                        // Stage 3: Extended Supernova Hang & Gentle Swell
                        var minHangP = (p - 0.42) / 0.23;
                        var minHangEase = Math.sin(minHangP * Math.PI * 0.5);
                        var minHangRadius = 27.5 + (minHangEase * 4.5); // ~32px max

                        var minOuterGrad = ctx.createRadialGradient(centerSingX, centerSingY, minHangRadius * 0.40, centerSingX, centerSingY, minHangRadius * 1.22);
                        minOuterGrad.addColorStop(0.00, "rgba(254, 215, 170, 0.28)");
                        minOuterGrad.addColorStop(0.60, "rgba(251, 146, 60, 0.12)");
                        minOuterGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");
                        ctx.fillStyle = minOuterGrad;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, minHangRadius * 1.22, 0, Math.PI * 2);
                        ctx.fill();

                        var minGrad3 = ctx.createRadialGradient(centerSingX, centerSingY, 0.5, centerSingX, centerSingY, minHangRadius);
                        minGrad3.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                        minGrad3.addColorStop(0.28, "rgba(255, 255, 255, 0.98)");
                        minGrad3.addColorStop(0.55, "rgba(255, 250, 235, 0.75)");
                        minGrad3.addColorStop(0.78, "rgba(254, 215, 170, 0.35)");
                        minGrad3.addColorStop(0.92, "rgba(251, 146, 60, 0.12)");
                        minGrad3.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = minGrad3;
                        ctx.beginPath();
                        ctx.arc(centerSingX, centerSingY, minHangRadius, 0, Math.PI * 2);
                        ctx.fill();

                        for (var mk = 0; mk < 16; mk++) {
                            var mkAngle = (mk / 16) * Math.PI * 2 + (minHangP * 1.6);
                            var mkDist = (minHangRadius * 0.58) * (0.30 + 0.70 * Math.sin(mk * 5.7 + minHangP * 4.0));
                            var mkx = centerSingX + Math.cos(mkAngle) * mkDist;
                            var mky = centerSingY + Math.sin(mkAngle) * mkDist;
                            ctx.fillStyle = (mk % 4 === 0)
                                ? "rgba(239, 68, 68, 0.75)"
                                : (mk % 4 === 1)
                                    ? "rgba(251, 146, 60, 0.85)"
                                    : (mk % 4 === 2)
                                        ? "rgba(254, 240, 138, 0.95)"
                                        : "rgba(255, 255, 255, 0.95)";
                            ctx.beginPath();
                            ctx.arc(mkx, mky, 1.0, 0, Math.PI * 2);
                            ctx.fill();
                        }

                    } else if (p < 0.88) {
                        // Stage 4: Comet Contraction (Radius halved: 32px -> 16px) & Straight Siphon along angleTheta with Glowing Tail
                        var cometP = (p - 0.65) / 0.23; // 0.0 to 1.0
                        var cometContract = 32.0 - (cometP * 16.0); // 32px -> 16px
                        var cometEase = Math.pow(cometP, 2.4); // Gravitational acceleration along straight trajectory line
                        var headX = centerSingX + (cometEase * targetDistX);
                        var headY = centerSingY + (cometEase * targetDistY);

                        // Draw Glowing Incandescent Comet Tail (Trailing backwards from flight angle)
                        var tailLength = Math.min(220, 24.0 + (cometEase * 180.0));
                        var tailTipX = headX - (cosA * tailLength);
                        var tailTipY = headY - (sinA * tailLength);

                        var tailGrad = ctx.createLinearGradient(headX, headY, tailTipX, tailTipY);
                        tailGrad.addColorStop(0.00, "rgba(255, 255, 255, 0.90)");
                        tailGrad.addColorStop(0.20, "rgba(254, 240, 138, 0.75)");
                        tailGrad.addColorStop(0.50, "rgba(251, 146, 60, 0.45)");
                        tailGrad.addColorStop(0.80, "rgba(239, 68, 68, 0.15)");
                        tailGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = tailGrad;
                        ctx.beginPath();
                        // Tapered aerodynamic comet tail ribbon perpendicular to flight path
                        var halfHeadW = cometContract * 0.90;
                        var perpX = -sinA * halfHeadW;
                        var perpY = cosA * halfHeadW;

                        ctx.moveTo(headX + perpX, headY + perpY);
                        ctx.quadraticCurveTo(headX + perpX * 0.4 - cosA * tailLength * 0.6, headY + perpY * 0.4 - sinA * tailLength * 0.6, tailTipX, tailTipY);
                        ctx.quadraticCurveTo(headX - perpX * 0.4 - cosA * tailLength * 0.6, headY - perpY * 0.4 - sinA * tailLength * 0.6, headX - perpX, headY - perpY);
                        ctx.closePath();
                        ctx.fill();

                        // Trailing sparks and plasma embers streaming backwards along flight wake
                        for (var t = 0; t < 16; t++) {
                            var sparkDist = (t / 16) * tailLength * (0.8 + 0.2 * Math.sin(t * 3.7 + cometP * 6.0));
                            var sparkSpread = (Math.sin(t * 5.1 + cometP * 8.0) * (halfHeadW * (1.0 - (sparkDist / tailLength))));
                            var spX = headX - (cosA * sparkDist) + (-sinA * sparkSpread);
                            var spY = headY - (sinA * sparkDist) + (cosA * sparkSpread);
                            var spAlpha = Math.max(0.0, 1.0 - (sparkDist / tailLength));
                            ctx.fillStyle = (t % 2 === 0)
                                ? "rgba(255, 255, 255, " + (spAlpha * 0.9).toFixed(3) + ")"
                                : "rgba(251, 146, 60, " + (spAlpha * 0.8).toFixed(3) + ")";
                            ctx.beginPath();
                            ctx.arc(spX, spY, Math.max(0.5, 1.2 * spAlpha), 0, Math.PI * 2);
                            ctx.fill();
                        }

                        // Hyper-Dense White-Hot Comet Head (16px)
                        var headGrad = ctx.createRadialGradient(headX, headY, 0.5, headX, headY, cometContract);
                        headGrad.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                        headGrad.addColorStop(0.35, "rgba(255, 255, 255, 0.98)");
                        headGrad.addColorStop(0.60, "rgba(255, 250, 235, 0.80)");
                        headGrad.addColorStop(0.82, "rgba(251, 146, 60, 0.40)");
                        headGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = headGrad;
                        ctx.beginPath();
                        ctx.arc(headX, headY, cometContract, 0, Math.PI * 2);
                        ctx.fill();

                    } else {
                        // ============================================================
                        // STAGE 5: DISAPPEARS BEHIND DESTINATION HORIZON (ISOLATED MODULAR STAGE)
                        // ============================================================
                        var stage5P = (p - 0.88) / 0.12; // 0.0 to 1.0
                        var destHorizonX = centerSingX + targetDistX;
                        var destHorizonY = centerSingY + targetDistY;
                        var s5HeadX = destHorizonX + (cosA * stage5P * 24.0);
                        var s5HeadY = destHorizonY + (sinA * stage5P * 24.0);
                        var s5Alpha = Math.max(0.0, 1.0 - Math.pow(stage5P, 1.8)); // Clean disappearance
                        var s5Radius = Math.max(0.5, 16.0 * (1.0 - (stage5P * 0.5)));

                        // Dissipating tail wake above destination horizon
                        var s5TailLen = Math.max(10, 120.0 * (1.0 - stage5P));
                        var s5TipX = destHorizonX - (cosA * s5TailLen);
                        var s5TipY = destHorizonY - (sinA * s5TailLen);
                        var s5TailGrad = ctx.createLinearGradient(destHorizonX, destHorizonY, s5TipX, s5TipY);
                        s5TailGrad.addColorStop(0.00, "rgba(254, 240, 138, " + (s5Alpha * 0.7).toFixed(3) + ")");
                        s5TailGrad.addColorStop(0.50, "rgba(251, 146, 60, " + (s5Alpha * 0.4).toFixed(3) + ")");
                        s5TailGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = s5TailGrad;
                        ctx.beginPath();
                        var s5PerpX = -sinA * 12;
                        var s5PerpY = cosA * 12;
                        ctx.moveTo(destHorizonX + s5PerpX, destHorizonY + s5PerpY);
                        ctx.quadraticCurveTo(destHorizonX + s5PerpX * 0.3 - cosA * s5TailLen * 0.5, destHorizonY + s5PerpY * 0.3 - sinA * s5TailLen * 0.5, s5TipX, s5TipY);
                        ctx.quadraticCurveTo(destHorizonX - s5PerpX * 0.3 - cosA * s5TailLen * 0.5, destHorizonY - s5PerpY * 0.3 - sinA * s5TailLen * 0.5, destHorizonX - s5PerpX, destHorizonY - s5PerpY);
                        ctx.closePath();
                        ctx.fill();

                        // Submerging Comet Head
                        var s5Grad = ctx.createRadialGradient(s5HeadX, s5HeadY, 0.5, s5HeadX, s5HeadY, s5Radius);
                        s5Grad.addColorStop(0.00, "rgba(255, 255, 255, " + s5Alpha.toFixed(3) + ")");
                        s5Grad.addColorStop(0.40, "rgba(255, 250, 235, " + (s5Alpha * 0.85).toFixed(3) + ")");
                        s5Grad.addColorStop(0.80, "rgba(251, 146, 60, " + (s5Alpha * 0.35).toFixed(3) + ")");
                        s5Grad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                        ctx.fillStyle = s5Grad;
                        ctx.beginPath();
                        ctx.arc(s5HeadX, s5HeadY, s5Radius, 0, Math.PI * 2);
                        ctx.fill();
                    }
                }
            } else {
                // CLOSE ANIMATION: White-Hot Supernova Flash with Rapid Prominent Fizzle Out
                // 1. Inward Suction (0.0 to 0.30)
                // 2. Supernova Detonation (0.30 to 0.42) - Scaled down 10% (~27.5px), same 28/72 ratio
                // 3. Extended "Hang & Gentle Swell" (0.42 to 0.76) - Scaled down 10% (~32px max), glowing champagne plasma
                // 4. Rapid Prominent Fizzle Out (0.76 to 1.0) - Fast optical fade-out and crisp suction into center
                if (p < 0.30) {
                    // Stage 1: Window UI and particle field get sucked straight into the center pinpoint
                    var suckP = p / 0.30;
                    var auraAlpha = Math.min(1.0, suckP * 2.0);
                    var auraRadius = Math.max(9, (1.0 - suckP * 0.75) * Math.min(mainWin.finalW, mainWin.finalH) * 0.25);

                    var grad1 = ctx.createRadialGradient(singX, singY, 2, singX, singY, auraRadius);
                    grad1.addColorStop(0.00, "rgba(255, 255, 255, " + (auraAlpha * 0.95).toFixed(3) + ")");
                    grad1.addColorStop(0.35, "rgba(255, 250, 235, " + (auraAlpha * 0.70).toFixed(3) + ")");
                    grad1.addColorStop(0.70, "rgba(254, 215, 170, " + (auraAlpha * 0.25).toFixed(3) + ")");
                    grad1.addColorStop(1.00, "rgba(251, 146, 60, 0.0)");

                    ctx.fillStyle = grad1;
                    ctx.beginPath();
                    ctx.arc(singX, singY, auraRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // Particles stream straight inward towards the center point
                    for (var j = 0; j < particles.length; j++) {
                        var pItem = particles[j];
                        var curDist = pItem.distRatio * (1.0 - Math.pow(suckP, 2.0)) * (Math.min(mainWin.finalW, mainWin.finalH) * 0.38);
                        var pX = singX + Math.cos(pItem.angle) * curDist;
                        var pY = singY + Math.sin(pItem.angle) * curDist;

                        var pAlpha = pItem.alpha * auraAlpha;
                        var pSize = Math.max(0.6, pItem.size * (1.0 - suckP * 0.4));

                        ctx.fillStyle = (j % 3 === 0)
                            ? "rgba(255, 255, 255, " + pAlpha.toFixed(3) + ")"
                            : (j % 3 === 1)
                                ? "rgba(254, 240, 138, " + pAlpha.toFixed(3) + ")"
                                : "rgba(251, 146, 60, " + (pAlpha * 0.8).toFixed(3) + ")";
                        ctx.beginPath();
                        ctx.arc(pX, pY, pSize, 0, Math.PI * 2);
                        ctx.fill();
                    }
                } else if (p < 0.42) {
                    // Stage 2: Supernova Detonation (10% smaller radius, 28/72 ratio)
                    var burstP = (p - 0.30) / 0.12; // 0.0 to 1.0
                    var burstEase = Math.sin(burstP * Math.PI * 0.5); // Explosive OutQuad expansion
                    var burstRadius = 2.5 + (burstEase * 25.0); // ~27.5px total footprint (-10%)

                    // Concentrated core with large soft glowing plasma falloff
                    var grad2 = ctx.createRadialGradient(singX, singY, 0.5, singX, singY, burstRadius);
                    grad2.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                    grad2.addColorStop(0.28, "rgba(255, 255, 255, 0.98)"); // small solid center (~7.5px)
                    grad2.addColorStop(0.55, "rgba(255, 250, 235, 0.75)"); // wide glowing champagne plasma
                    grad2.addColorStop(0.78, "rgba(254, 215, 170, 0.35)"); // delicate warm amber plasma
                    grad2.addColorStop(0.92, "rgba(251, 146, 60, 0.14)"); // faint solar warmth
                    grad2.addColorStop(1.00, "rgba(239, 68, 68, 0.00)"); // outer fade

                    ctx.fillStyle = grad2;
                    ctx.beginPath();
                    ctx.arc(singX, singY, burstRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // Internal delicate ember dots
                    for (var b = 0; b < 16; b++) {
                        var bAngle = (b / 16) * Math.PI * 2 + (burstP * 1.5);
                        var bDist = (burstRadius * 0.55) * (0.25 + 0.75 * Math.sin(b * 4.3 + burstP * 3.0));
                        var bx = singX + Math.cos(bAngle) * bDist;
                        var by = singY + Math.sin(bAngle) * bDist;
                        ctx.fillStyle = (b % 4 === 0)
                            ? "rgba(239, 68, 68, 0.75)"      // subtle crimson accent
                            : (b % 4 === 1)
                                ? "rgba(251, 146, 60, 0.85)"  // soft amber
                                : (b % 4 === 2)
                                    ? "rgba(254, 240, 138, 0.95)" // pale champagne
                                    : "rgba(255, 255, 255, 0.95)"; // white spark
                        ctx.beginPath();
                        ctx.arc(bx, by, 0.9 + (burstEase * 0.3), 0, Math.PI * 2);
                        ctx.fill();
                    }

                } else if (p < 0.76) {
                    // Stage 3: Extended "Hang & Gentle Swell" (10% smaller radius: ~32px max, 28/72 ratio)
                    var hangP = (p - 0.42) / 0.34; // 0.0 to 1.0
                    var hangEase = Math.sin(hangP * Math.PI * 0.5);
                    var hangRadius = 27.5 + (hangEase * 4.5); // ~32px total footprint (-10%)

                    // Wide ethereal plasma aura fading seamlessly towards exterior
                    var outerGrad = ctx.createRadialGradient(singX, singY, hangRadius * 0.40, singX, singY, hangRadius * 1.22);
                    outerGrad.addColorStop(0.00, "rgba(254, 215, 170, 0.28)");
                    outerGrad.addColorStop(0.60, "rgba(251, 146, 60, 0.12)");
                    outerGrad.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");
                    ctx.fillStyle = outerGrad;
                    ctx.beginPath();
                    ctx.arc(singX, singY, hangRadius * 1.22, 0, Math.PI * 2);
                    ctx.fill();

                    // Concentrated Core with dominant glowing champagne plasma aura
                    var grad3 = ctx.createRadialGradient(singX, singY, 0.5, singX, singY, hangRadius);
                    grad3.addColorStop(0.00, "rgba(255, 255, 255, 1.0)");
                    grad3.addColorStop(0.28, "rgba(255, 255, 255, 0.98)"); // solid center (~9px)
                    grad3.addColorStop(0.55, "rgba(255, 250, 235, 0.75)"); // wide glowing champagne plasma (~72% area)
                    grad3.addColorStop(0.78, "rgba(254, 215, 170, 0.35)"); // delicate warm amber plasma
                    grad3.addColorStop(0.92, "rgba(251, 146, 60, 0.12)"); // faint solar warmth
                    grad3.addColorStop(1.00, "rgba(239, 68, 68, 0.00)"); // seamless fade to transparent

                    ctx.fillStyle = grad3;
                    ctx.beginPath();
                    ctx.arc(singX, singY, hangRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // 16 delicate ember dots shimmering inside the core and glowing plasma
                    for (var k = 0; k < 16; k++) {
                        var emberAngle = (k / 16) * Math.PI * 2 + (hangP * 1.6);
                        var emberDist = (hangRadius * 0.58) * (0.30 + 0.70 * Math.sin(k * 5.7 + hangP * 4.0));
                        var epX = singX + Math.cos(emberAngle) * emberDist;
                        var epY = singY + Math.sin(emberAngle) * emberDist;

                        ctx.fillStyle = (k % 4 === 0)
                            ? "rgba(239, 68, 68, 0.75)"      // subtle crimson accent
                            : (k % 4 === 1)
                                ? "rgba(251, 146, 60, 0.85)"  // soft amber
                                : (k % 4 === 2)
                                    ? "rgba(254, 240, 138, 0.95)" // pale champagne
                                    : "rgba(255, 255, 255, 0.95)"; // white spark
                        ctx.beginPath();
                        ctx.arc(epX, epY, 1.0, 0, Math.PI * 2);
                        ctx.fill();
                    }

                } else {
                    // Stage 4: Rapid Prominent Fade-Out & Sucked into Center Pinpoint!
                    var fizzleP = (p - 0.76) / 0.24; // 0.0 to 1.0
                    var shrinkFactor = Math.pow(1.0 - fizzleP, 2.8); // Snappy, crisp gravitational contraction
                    var fizzleAlpha = Math.pow(1.0 - fizzleP, 2.6); // Rapid, prominent optical fade-out
                    var fizzleRadius = Math.max(0.1, shrinkFactor * 32.0);

                    var grad4 = ctx.createRadialGradient(singX, singY, 0, singX, singY, fizzleRadius);
                    grad4.addColorStop(0.00, "rgba(255, 255, 255, " + fizzleAlpha.toFixed(3) + ")");
                    grad4.addColorStop(0.30, "rgba(255, 255, 255, " + (fizzleAlpha * 0.90).toFixed(3) + ")");
                    grad4.addColorStop(0.65, "rgba(254, 215, 170, " + (fizzleAlpha * 0.30).toFixed(3) + ")");
                    grad4.addColorStop(0.88, "rgba(251, 146, 60, " + (fizzleAlpha * 0.10).toFixed(3) + ")");
                    grad4.addColorStop(1.00, "rgba(239, 68, 68, 0.00)");

                    ctx.fillStyle = grad4;
                    ctx.beginPath();
                    ctx.arc(singX, singY, fizzleRadius, 0, Math.PI * 2);
                    ctx.fill();

                    // Embers getting drawn rapidly into the pinpoint hole
                    if (fizzleRadius > 1.0) {
                        for (var m = 0; m < 12; m++) {
                            var retAngle = (m / 12) * Math.PI * 2 + (fizzleP * 2.5);
                            var retDist = fizzleRadius * 0.45 * (1.0 - fizzleP * 0.5);
                            var rx = singX + Math.cos(retAngle) * retDist;
                            var ry = singY + Math.sin(retAngle) * retDist;
                            ctx.fillStyle = (m % 2 === 0)
                                ? "rgba(255, 255, 255, " + (fizzleAlpha * 0.95).toFixed(3) + ")"
                                : "rgba(251, 146, 60, " + (fizzleAlpha * 0.75).toFixed(3) + ")";
                            ctx.beginPath();
                            ctx.arc(rx, ry, Math.max(0.4, 1.0 * shrinkFactor), 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }
                }
            }
        }
    }

    // Permanent neon frame around the active monitor's visible area.
    Rectangle {
        x: (mainWin.activeVisibleRect.x - mainWin.x) - Math.floor(mainWin.monitorFrameGlowThickness / 2)
        y: (mainWin.activeVisibleRect.y - mainWin.y) - Math.floor(mainWin.monitorFrameGlowThickness / 2)
        width: mainWin.activeVisibleRect.w + mainWin.monitorFrameGlowThickness
        height: mainWin.activeVisibleRect.h + mainWin.monitorFrameGlowThickness
        color: "transparent"
        border.color: mainWin.monitorFrameColor
        border.width: mainWin.monitorFrameGlowThickness
        opacity: 0.22
        z: 1400
        visible: mainWin.launchConfigured && mainWin.debugFrameEnabled
            && mainWin.animationPhase === "settled"
    }

    Rectangle {
        x: mainWin.activeVisibleRect.x - mainWin.x
        y: mainWin.activeVisibleRect.y - mainWin.y
        width: mainWin.activeVisibleRect.w
        height: mainWin.activeVisibleRect.h
        color: "transparent"
        border.color: mainWin.monitorFrameColor
        border.width: mainWin.monitorFrameThickness
        opacity: 1.0
        z: 1401
        visible: mainWin.launchConfigured && mainWin.debugFrameEnabled
            && mainWin.animationPhase === "settled"
    }

    // Dynamic orange frame for the current canvas bounds (always top-most in this window).
    Rectangle {
        // Keep debug stroke fully inside the shell mask so corners do not appear clipped.
        property real strokeInset: mainWin.canvasFrameGlowThickness / 2
        x: mainWin.canvasLocalX + strokeInset
        y: mainWin.canvasLocalY + strokeInset
        width: Math.max(1, mainWin.canvasW - (strokeInset * 2))
        height: Math.max(1, mainWin.canvasH - (strokeInset * 2))
        radius: Math.max(0, mainWin.shellVisualCornerRadiusPx() - strokeInset)
        antialiasing: true
        color: "transparent"
        border.color: mainWin.canvasFrameColor
        border.width: mainWin.canvasFrameGlowThickness
        opacity: 0.24
        z: 1500
        visible: mainWin.launchConfigured && mainWin.debugFrameEnabled && mainWin.animationPhase === "settled"
    }

    Rectangle {
        property real strokeInset: mainWin.canvasFrameThickness / 2
        x: mainWin.canvasLocalX + strokeInset
        y: mainWin.canvasLocalY + strokeInset
        width: Math.max(1, mainWin.canvasW - (strokeInset * 2))
        height: Math.max(1, mainWin.canvasH - (strokeInset * 2))
        radius: Math.max(0, mainWin.shellVisualCornerRadiusPx() - strokeInset)
        antialiasing: true
        color: "transparent"
        border.color: mainWin.canvasFrameColor
        border.width: mainWin.canvasFrameThickness
        opacity: 1.0
        z: 1501
        visible: mainWin.launchConfigured && mainWin.debugFrameEnabled && mainWin.animationPhase === "settled"
    }

    // ============================================================
    // WINDOW CONTROLS
    // ============================================================
    
    function openThemePicker() {
        if (!themePicker) {
            return false;
        }
        if (settingsMenu && settingsMenu.opened) {
            settingsMenu.close();
        }
        if (sfxBus && sfxBus.playUiClick) {
            sfxBus.playUiClick("open", 0.54);
        }
        // Place picker relative to visible content (orange area), not host envelope.
        var contentLeft = canvasLocalX + contentLocalX;
        var contentTop = canvasLocalY + contentLocalY;
        var gx = Math.round(contentLeft + finalW - themePicker.width - themePickerRightOffsetPx());
        var gy = Math.round(contentTop + themePickerTopOffsetPx());

        // Clamp inside canvas so mask/input region always contains the popup.
        if (canvasW > 0 && canvasH > 0) {
            var minX = canvasLocalX;
            var minY = canvasLocalY;
            var maxX = canvasLocalX + canvasW - themePicker.width;
            var maxY = canvasLocalY + canvasH - themePicker.height;
            if (maxX < minX) maxX = minX;
            if (maxY < minY) maxY = minY;
            gx = Math.max(minX, Math.min(gx, maxX));
            gy = Math.max(minY, Math.min(gy, maxY));
        }

        themePicker.x = gx;
        themePicker.y = gy;
        themePicker.open();
        themePicker.forceActiveFocus();
        return true;
    }

    function openReportBrandingSettings(initiatingWindow) {
        if (reportBrandingSettings) {
            if (initiatingWindow !== undefined && initiatingWindow !== null) {
                reportBrandingSettings.parentWindow = initiatingWindow;
            } else {
                reportBrandingSettings.parentWindow = mainWin;
            }
            reportBrandingSettings.openWithProfiles();
            return true;
        }
        return false;
    }

    function openSettingsMenu() {
        if (!settingsMenu) {
            return false;
        }
        if (themePicker && themePicker.opened) {
            themePicker.close();
        }
        mainWin.syncSoundEffectsFromApp();
        if (sfxBus && sfxBus.playUiClick) {
            sfxBus.playUiClick("open", 0.48);
        }

        var contentLeft = canvasLocalX + contentLocalX;
        var contentTop = canvasLocalY + contentLocalY;
        var gx = Math.round(contentLeft + finalW - settingsMenu.width - themePickerRightOffsetPx());
        var gy = Math.round(contentTop + themePickerTopOffsetPx());

        if (canvasW > 0 && canvasH > 0) {
            var minX = canvasLocalX;
            var minY = canvasLocalY;
            var maxX = canvasLocalX + canvasW - settingsMenu.width;
            var maxY = canvasLocalY + canvasH - settingsMenu.height;
            if (maxX < minX) maxX = minX;
            if (maxY < minY) maxY = minY;
            gx = Math.max(minX, Math.min(gx, maxX));
            gy = Math.max(minY, Math.min(gy, maxY));
        }

        settingsMenu.x = gx;
        settingsMenu.y = gy;
        settingsMenu.open();
        settingsMenu.forceActiveFocus();
        return true;
    }

    function requestHoverActivation() {
        if (!mainWin.hoverActivateEnabled) return;
        if (mainWin.active) return;
        if (mainWin.animationPhase !== "settled") return;
        if (mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize) return;
        try {
            if (mainWin.raise) mainWin.raise();
            mainWin._requestActivateIfFocusable(mainWin);
        } catch (e) {
        }
        if (mainWin.active) return;
        if (!hoverActivateTimer.running) {
            hoverActivateTimer.start();
        }
    }
    
    function requestCloseAnimation() {
        if (mainWin.forceClose || mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.maximizeAnimInProgress) return false;
        if (mainWin.recoveryPromptVisible) return true;
        if (!mainWin.detachedMode && mainWin.presentMainCloseGuard("window-control")) {
            return true;
        }
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        resetDragFxState();
        mainWin.phaseLog("CLOSING", "Close requested via window control");
        mainWin.transitionToClosing();
        return true;
    }

    function requestMinimizeAnimation() {
        if (mainWin.forceClose || mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.maximizeAnimInProgress) return false;
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        resetDragFxState();
        mainWin.phaseLog("MINIMIZE", "Minimize requested via window control");
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.56);
        }
        mainWin.clearMinimizeRestoreState();
        if (mainWin.animationPhase !== "settled") {
            mainWin.phaseLog("MINIMIZE", "Skipped animation because phase=" + mainWin.animationPhase + "; minimizing directly");
            if (sfxBus && sfxBus.playWindowSettle) {
                sfxBus.playWindowSettle("minimize", 0.44);
            }
            mainWin.showMinimized();
            return true;
        }

        if (mainWin.userMoveInProgress) {
            mainWin.finishUserDrag();
        }
        if (mainWin.userResizeInProgress) {
            mainWin.finishUserResize();
        }

        mainWin.isMinimizing = true;
        mainWin.isMinimizingToTray = false;
        mainWin.minimizeRestorePending = true;
        if (!mainWin.uiMaximized) {
            mainWin.rememberRestoreGeometry();
        }
        var targetDistX = 0.0;
        var targetDistY = (mainWin.finalH / 2.0) + mainWin.glowPadding;

        mainWin.lastMinimizeTargetDistX = targetDistX;
        mainWin.lastMinimizeTargetDistY = targetDistY;

        jelly.startMinimize(targetDistX, targetDistY);
        return true;
    }

    function requestMinimizeToTrayAnimation() {
        if (mainWin.forceClose || mainWin.isClosing || mainWin.isMinimizing || mainWin.isRestoringFromMinimize || mainWin.maximizeAnimInProgress) return false;
        if (dragFxReleaseAnimation.running) {
            dragFxReleaseAnimation.stop();
        }
        resetDragFxState();
        mainWin.phaseLog("MINIMIZE", "Minimize to System Tray requested via right-click");
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(0.56);
        }
        mainWin.clearMinimizeRestoreState();

        if (mainWin.userMoveInProgress) {
            mainWin.finishUserDrag();
        }
        if (mainWin.userResizeInProgress) {
            mainWin.finishUserResize();
        }

        mainWin.isMinimizing = true;
        mainWin.isMinimizingToTray = true;
        mainWin.minimizeRestorePending = true;
        if (!mainWin.uiMaximized) {
            mainWin.rememberRestoreGeometry();
        }

        // Query the actual system tray location for angle-correct comet flight
        var targetDistX, targetDistY;
        mainWin._crossMonitorTrayFlight = false;
        if (typeof trayController !== "undefined" && trayController.getTrayFlightInfo) {
            var winCX = Math.round(mainWin.x + mainWin.width / 2.0);
            var winCY = Math.round(mainWin.y + mainWin.height / 2.0);
            var info = trayController.getTrayFlightInfo(winCX, winCY);
            console.warn("[TRAY-GEOM] getTrayFlightInfo result: available=" + (info ? info.available : "null")
                + " trayCenterX=" + (info ? info.trayCenterX : "?") + " trayCenterY=" + (info ? info.trayCenterY : "?")
                + " sameMonitor=" + (info ? info.sameMonitor : "?") + " winCX=" + winCX + " winCY=" + winCY);
            if (info && info.available) {
                // Store for cross-monitor overlay use
                mainWin._trayTargetGlobalX = info.trayCenterX;
                mainWin._trayTargetGlobalY = info.trayCenterY;
                mainWin._windowCenterGlobalX = winCX;
                mainWin._windowCenterGlobalY = winCY;
                mainWin._vdX = info.vdX;
                mainWin._vdY = info.vdY;
                mainWin._vdW = info.vdW;
                mainWin._vdH = info.vdH;
                mainWin._crossMonitorTrayFlight = !info.sameMonitor;

                // Compute angle-corrected in-window targetDist
                var angle = Math.atan2(info.trayCenterY - winCY, info.trayCenterX - winCX);
                var mag = Math.sqrt(Math.pow(mainWin.finalW / 2.0 + mainWin.glowPadding, 2)
                                  + Math.pow(mainWin.finalH / 2.0 + mainWin.glowPadding, 2));
                targetDistX = Math.cos(angle) * mag;
                targetDistY = Math.sin(angle) * mag;
            } else {
                // Fallback: bottom-right of current monitor
                targetDistX = (mainWin.finalW / 2.0) + mainWin.glowPadding;
                targetDistY = (mainWin.finalH / 2.0) + mainWin.glowPadding;
            }
        } else {
            targetDistX = (mainWin.finalW / 2.0) + mainWin.glowPadding;
            targetDistY = (mainWin.finalH / 2.0) + mainWin.glowPadding;
        }

        mainWin.lastMinimizeTargetDistX = targetDistX;
        mainWin.lastMinimizeTargetDistY = targetDistY;

        jelly.startMinimize(targetDistX, targetDistY);
        return true;
    }

    function requestExitFromTrayAnimation() {
        mainWin.phaseLog("EXIT", "Exit from System Tray animation requested");
        if (mainWin.isClosing && !mainWin.isExitingFromTray) return false;

        // Check if tray is on a different monitor — fly overlay comet first
        if (typeof trayController !== "undefined" && trayController.getTrayFlightInfo) {
            var winCX = Math.round(mainWin.x + mainWin.width / 2.0);
            var winCY = Math.round(mainWin.y + mainWin.height / 2.0);
            var info = trayController.getTrayFlightInfo(winCX, winCY);
            if (info && info.available && !info.sameMonitor) {
                mainWin._pendingTrayAction = "exit";
                var overlay = mainWin._ensureCrossMonitorOverlay();
                if (overlay) {
                    var dist = Math.sqrt(
                        Math.pow(winCX - info.trayCenterX, 2) +
                        Math.pow(winCY - info.trayCenterY, 2)
                    );
                    var durationMs = Math.round(Math.min(800, Math.max(400, dist * 0.3)));
                    overlay.launchFlight(
                        info.trayCenterX, info.trayCenterY,
                        winCX, winCY,
                        info.vdX, info.vdY, info.vdW, info.vdH,
                        durationMs
                    );
                    return true;
                }
            }
        }

        mainWin._startExitFromTrayInWindow();
        return true;
    }

    function _startExitFromTrayInWindow() {
        console.warn("[TRAY-ANIM] _startExitFromTrayInWindow called");
        trayKeepAlive.visible = false;
        mainWin.animationPhase = "closing";
        mainWin.clearMinimizeRestoreState();
        mainWin.isClosing = true;
        mainWin.isExitingFromTray = true;
        mainWin.isMinimizing = false;
        mainWin.isRestoringFromMinimize = false;
        mainWin.wasWindowMinimized = false;

        mainWin.applyHostEnvelopeForTarget();
        mainWin.updateCanvasGeometry();

        mainWin.opacity = 1.0;
        mainWin.showNormal();
        mainWin.requestActivate();

        var targetDistX = (mainWin.finalW / 2.0) + mainWin.glowPadding;
        var targetDistY = (mainWin.finalH / 2.0) + mainWin.glowPadding;

        console.warn("[TRAY-ANIM]   calling jelly.startExitFromTray distX=" + targetDistX + " distY=" + targetDistY);
        jelly.startExitFromTray(targetDistX, targetDistY);
    }

    function requestRestoreFromTrayAnimation() {
        mainWin.phaseLog("RESTORE", "Restore from System Tray animation requested");
        if (mainWin.isClosing) return false;

        // Check if tray is on a different monitor — fly overlay comet first
        if (typeof trayController !== "undefined" && trayController.getTrayFlightInfo) {
            var winCX = Math.round(mainWin.x + mainWin.width / 2.0);
            var winCY = Math.round(mainWin.y + mainWin.height / 2.0);
            var info = trayController.getTrayFlightInfo(winCX, winCY);
            if (info && info.available && !info.sameMonitor) {
                mainWin._pendingTrayAction = "restore";
                var overlay = mainWin._ensureCrossMonitorOverlay();
                if (overlay) {
                    var dist = Math.sqrt(
                        Math.pow(winCX - info.trayCenterX, 2) +
                        Math.pow(winCY - info.trayCenterY, 2)
                    );
                    var durationMs = Math.round(Math.min(800, Math.max(400, dist * 0.3)));
                    overlay.launchFlight(
                        info.trayCenterX, info.trayCenterY,
                        winCX, winCY,
                        info.vdX, info.vdY, info.vdW, info.vdH,
                        durationMs
                    );
                    return true;
                }
            }
        }

        mainWin._startRestoreFromTrayInWindow();
        return true;
    }

    function _startRestoreFromTrayInWindow() {
        console.warn("[TRAY-ANIM] _startRestoreFromTrayInWindow called");
        trayKeepAlive.visible = false;
        console.warn("[TRAY-ANIM]   isClosing=" + mainWin.isClosing + " isMinimizing=" + mainWin.isMinimizing
            + " isRestoringFromMinimize=" + mainWin.isRestoringFromMinimize + " wasWindowMinimized=" + mainWin.wasWindowMinimized
            + " animationPhase=" + mainWin.animationPhase + " isVisible=" + mainWin.visible);
        mainWin.clearMinimizeRestoreState();
        mainWin.isClosing = false;
        mainWin.isExitingFromTray = false;
        mainWin.isMinimizing = false;
        mainWin.isRestoringFromMinimize = true;
        mainWin.wasWindowMinimized = false;

        mainWin.applyHostEnvelopeForTarget();
        mainWin.updateCanvasGeometry();

        mainWin.opacity = 1.0;
        mainWin.showNormal();
        mainWin.requestActivate();

        var targetDistX = (mainWin.lastMinimizeTargetDistX !== 0.0) ? mainWin.lastMinimizeTargetDistX : ((mainWin.finalW / 2.0) + mainWin.glowPadding);
        var targetDistY = (mainWin.lastMinimizeTargetDistY !== 0.0) ? mainWin.lastMinimizeTargetDistY : ((mainWin.finalH / 2.0) + mainWin.glowPadding);

        console.warn("[TRAY-ANIM]   calling jelly.startRestore distX=" + targetDistX + " distY=" + targetDistY);
        jelly.startRestore(targetDistX, targetDistY);
    }

    function _ensureCrossMonitorOverlay() {
        if (mainWin._crossMonitorOverlay) return mainWin._crossMonitorOverlay;
        try {
            var comp = Qt.createComponent("components/CrossMonitorCometOverlay.qml");
            if (comp.status === Component.Ready) {
                mainWin._crossMonitorOverlay = comp.createObject(null);
                mainWin._crossMonitorOverlay.flightFinished.connect(mainWin._onCrossMonitorFlightFinished);
            } else if (comp.status === Component.Error) {
                console.warn("[TRAY] CrossMonitorCometOverlay load error: " + comp.errorString());
            }
        } catch (e) {
            console.warn("[TRAY] Failed to create CrossMonitorCometOverlay: " + e);
        }
        return mainWin._crossMonitorOverlay;
    }

    function _onCrossMonitorFlightFinished() {
        var action = mainWin._pendingTrayAction;
        mainWin._pendingTrayAction = "";
        if (action === "restore") {
            mainWin._startRestoreFromTrayInWindow();
        } else if (action === "exit") {
            mainWin._startExitFromTrayInWindow();
        }
    }

    function finalizeCloseSequence(reason) {
        if (mainWin.forceClose) return;
        closeFinalizeFailsafeTimer.stop();
        perfEnd("window.transition.close", "reason=" + String(reason || ""));
        mainWin.phaseLog("CLOSING", "Finalize close reason=" + reason);
        var dockCommitted = false;
        if (mainWin.detachedMode) {
            dockCommitted = mainWin.commitPendingDockAfterClose();
        } else {
            mainWin.clearPendingDockCommit();
        }
        mainWin.clearCloseTargetOverride();
        mainWin.clearClosingOverlayGeometry();
        mainWin.isClosing = false;
        mainWin.isMinimizing = false;
        mainWin.isRestoringFromMinimize = false;
        mainWin.stopMaximizeFxAnimations();
        mainWin.destroyStartupSplash();
        mainWin.destroyClosingOverlay();
        mainWin.destroyMinimizeOverlay();
        mainWin.clearMinimizeRestoreState();
        if (mainWin.detachedMode) {
            mainWin.forceClose = true;
            if (!dockCommitted) {
                var mainShell = mainWin.resolvePrimaryMainShellWindow();
                if (mainShell) mainWin.focusMainShell(mainShell);
            }
            mainWin.emitDetachedDidCloseOnce();
            mainWin.close();
            return;
        }
        if (mainWin.appRef && mainWin.appRef.keepTrayAlive) {
            mainWin.phaseLog("CLOSING", "Close complete; retaining the application in the system tray");
            mainWin.forceClose = false;
            mainWin.isClosing = false;
            mainWin.isMinimizing = false;
            mainWin.isRestoringFromMinimize = false;
            mainWin.closeMotionStarted = false;
            mainWin.animationPhase = "settled";
            mainWin.isSettled = true;
            mainWin.opacity = 1.0;
            if (jelly && jelly.restore) jelly.restore();
            mainWin.visible = false;
            return;
        }
        mainWin.forceClose = true;
        mainWin.closeAllTopLevelWindows();
        mainWin.close();
        Qt.callLater(function() {
            if (Qt.application) {
                mainWin.phaseLog("CLOSING", "Qt.quit() requested");
                Qt.quit();
            }
        });
    }

    function startCloseMotion(reason) {
        if (!mainWin.isClosing || mainWin.closeMotionStarted) return;
        mainWin.closeMotionStarted = true;
        mainWin.phaseLog("CLOSING", "startCloseMotion reason=" + reason);
        jelly.startClose();
    }

    Timer {
        id: appNotificationTimer
        interval: 3600
        repeat: false
        onTriggered: mainWin.appNotificationActive = false
    }

    Timer {
        id: closeFinalizeFailsafeTimer
        interval: 6000
        repeat: false
        onTriggered: {
            if (!mainWin.forceClose && mainWin.isClosing) {
                mainWin.phaseLog("CLOSING", "Failsafe timeout finalize");
                mainWin.finalizeCloseSequence("failsafe-timeout");
            }
        }
    }

    NotificationToaster {
        id: appNotificationToaster
        anchors.top: parent.top
        anchors.topMargin: mainWin.metricFloorPx(0.012, 12)
        anchors.horizontalCenter: parent.horizontalCenter
        z: 999999
        t: mainWin.t
        metrics: ({
            "contentW": Math.max(1, mainWin.width),
            "contentH": Math.max(1, mainWin.height),
            "fontFloorLabelPx": mainWin.metricFloorPx(0.012, 11)
        })
        message: mainWin.appNotificationMessage
        isActive: mainWin.appNotificationActive
        tone: mainWin.appNotificationTone
    }

    Window {
        id: systemTrayToastWindow
        flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
        color: "transparent"
        width: 350
        height: 60
        visible: false

        property string toastMessage: "CSPM is running in the system tray"

        function showToast(msg) {
            if (msg && msg.length > 0) {
                toastMessage = msg;
            }
            var targetScreenObj = mainWin.targetScreen || (Qt.application.screens ? Qt.application.screens[0] : null);
            var sw = (targetScreenObj && targetScreenObj.width > 0) ? targetScreenObj.width : 1920;
            var sh = (targetScreenObj && targetScreenObj.height > 0) ? targetScreenObj.height : 1080;
            var sx = (targetScreenObj && typeof targetScreenObj.x === "number") ? targetScreenObj.x : 0;
            var sy = (targetScreenObj && typeof targetScreenObj.y === "number") ? targetScreenObj.y : 0;

            systemTrayToastWindow.x = sx + sw - systemTrayToastWindow.width - 20;
            systemTrayToastWindow.y = sy + sh - systemTrayToastWindow.height - 54;
            systemTrayToastWindow.show();
            standaloneToastAnim.restart();
        }

        Rectangle {
            id: standaloneToastBubble
            anchors.fill: parent
            anchors.margins: 4
            radius: 12
            color: "#0F172A"
            border.color: "#334155"
            border.width: 1
            opacity: 0.0

            SequentialAnimation {
                id: standaloneToastAnim
                running: false

                NumberAnimation {
                    target: standaloneToastBubble
                    property: "opacity"
                    from: 0.0
                    to: 0.96
                    duration: 220
                    easing.type: Easing.OutQuad
                }

                PauseAnimation {
                    duration: 3200
                }

                NumberAnimation {
                    target: standaloneToastBubble
                    property: "opacity"
                    from: 0.96
                    to: 0.0
                    duration: 650
                    easing.type: Easing.InQuad
                }

                onFinished: {
                    systemTrayToastWindow.hide();
                }
            }

            Row {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12
                layoutDirection: Qt.LeftToRight

                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#2638BDF8"
                    border.color: "#6638BDF8"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "▲"
                        font.pixelSize: 11
                        color: "#38BDF8"
                    }
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    width: parent.width - 48

                    Text {
                        text: systemTrayToastWindow.toastMessage
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        width: parent.width
                    }

                    Text {
                        text: "Click the system tray icon to restore"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        elide: Text.ElideRight
                        width: parent.width
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    standaloneToastAnim.stop();
                    standaloneToastBubble.opacity = 0.0;
                    systemTrayToastWindow.hide();
                }
            }
        }
    }

    TextEdit {
        id: liveLogClipboardProxy
        x: -4096
        y: -4096
        width: 1
        height: 1
        opacity: 0.0
        wrapMode: TextEdit.NoWrap
    }

    Rectangle {
        id: liveLogConsole
        visible: mainWin.liveLogConsoleVisible
        property int panelInset: mainWin.metricFloorPx(0.010, 12)
        property int contentLeft: Math.round(mainWin.canvasLocalX + mainWin.contentLocalX)
        property int contentTop: Math.round(mainWin.canvasLocalY + mainWin.contentLocalY)
        property int availableContentWidth: Math.max(180, Math.round(mainWin.finalW - (panelInset * 2)))
        property int availableContentHeight: Math.max(140, Math.round(mainWin.finalH - (panelInset * 2)))
        x: contentLeft + panelInset
        y: contentTop + panelInset
        width: Math.min(
            availableContentWidth,
            Math.max(240, Math.min(540, Math.round(mainWin.finalW * 0.42)))
        )
        height: Math.min(
            availableContentHeight,
            Math.max(160, Math.min(320, Math.round(mainWin.finalH * 0.28)))
        )
        radius: mainWin.metricFloorPx(0.012, 12)
        color: Qt.alpha(mainWin.safeColor(mainWin.t.panel2, Qt.rgba(0.06, 0.07, 0.08, 1.0)), 0.94)
        border.width: 1
        border.color: Qt.alpha(mainWin.safeColor(mainWin.t.accent, Qt.rgba(1, 1, 1, 1)), 0.22)
        z: 9999
        clip: true

        Rectangle {
            id: liveLogHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: mainWin.metricFloorPx(0.040, 40)
            color: Qt.alpha(mainWin.safeColor(mainWin.t.panel, Qt.rgba(0.10, 0.11, 0.12, 1.0)), 0.98)

            Text {
                anchors.left: parent.left
                anchors.leftMargin: mainWin.metricFloorPx(0.010, 12)
                anchors.verticalCenter: parent.verticalCenter
                text: "Live Log Console"
                color: mainWin.safeColor(mainWin.t.text, "#F5F7FA")
                font.pixelSize: mainWin.metricFloorPx(0.011, 12)
                font.bold: true
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: mainWin.metricFloorPx(0.010, 10)
                anchors.verticalCenter: parent.verticalCenter
                text: "Double-click panel to copy"
                color: Qt.alpha(mainWin.safeColor(mainWin.t.muted, "#A4AAB4"), 0.94)
                font.pixelSize: mainWin.metricFloorPx(0.0092, 10)
            }
        }

        ScrollView {
            id: liveLogScrollView
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: liveLogHeader.bottom
            anchors.bottom: parent.bottom
            clip: true
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            Flickable {
                id: liveLogViewport
                width: liveLogScrollView.availableWidth
                height: liveLogScrollView.availableHeight
                contentWidth: width
                contentHeight: Math.max(liveLogText.paintedHeight + (liveLogPad * 2), height)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height
                property int liveLogPad: mainWin.metricFloorPx(0.010, 12)

                Text {
                    id: liveLogText
                    x: liveLogViewport.liveLogPad
                    y: liveLogViewport.liveLogPad
                    width: Math.max(1, liveLogViewport.width - (liveLogViewport.liveLogPad * 2))
                    text: mainWin.liveLogBuffer.length ? mainWin.liveLogBuffer : "[live log console ready]"
                    color: mainWin.safeColor(mainWin.t.text, "#F5F7FA")
                    textFormat: Text.PlainText
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.family: "Consolas"
                    font.pixelSize: mainWin.metricFloorPx(0.0098, 11)
                    lineHeight: 1.15
                }
            }
        }

        TapHandler {
            acceptedButtons: Qt.LeftButton
            onDoubleTapped: mainWin.copyLiveLogBufferToClipboard()
        }
    }
    
    // ============================================================
    // CLEANUP & LIFECYCLE
    // ============================================================

    function closeForAppExit() {
        if (mainWin.forceClose) return;
        closeFinalizeFailsafeTimer.stop();
        mainWin.persistCurrentThemeSelection("closeForAppExit");
        mainWin.forceClose = true;
        mainWin.clearStartupDeferredQueue("closeForAppExit");
        mainWin.clearPendingDockCommit();
        mainWin.clearCloseTargetOverride();
        mainWin.isClosing = false;
        mainWin.isMinimizing = false;
        mainWin.isRestoringFromMinimize = false;
        mainWin.stopMaximizeFxAnimations();
        mainWin.destroyStartupSplash();
        mainWin.destroyClosingOverlay();
        mainWin.destroyMinimizeOverlay();
        mainWin.clearMinimizeRestoreState();
        mainWin.emitDetachedDidCloseOnce();
        mainWin.visible = false;
        mainWin.close();
        Qt.quit();
    }
    
    function closeAllTopLevelWindows() {
        var windows = topLevelWindowsSafe();
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (!w || w === mainWin) continue;
            try {
                if (w.closeForAppExit) {
                    w.closeForAppExit();
                } else {
                    w.close();
                }
            } catch (e) {
            }
        }
    }
    
    Component.onCompleted: {
        mainWin.resetLiveLogBuffer("component-ready");
        mainWin.setStartupPhase("component-ready", "Component.onCompleted");
        mainWin.syncThemeFromApp();
        mainWin.syncSoundEffectsFromApp();
        if (!mainWin.detachedMode) {
            mainWin.primeStartupLaunchScreen("Component.onCompleted");
        }
        mainWin.resolveTargetScreen();
        mainWin.refreshActiveVisibleRect();
        mainWin.updateDebugOverlayBounds();
        Qt.callLater(function() {
            mainWin.prepareStartupBriefingForReveal();
        });
        if (mainWin.detachedMode) {
            mainWin.beginCoreLaunchSequence();
            return;
        }
        if (mainWin.deferStartupLaunch) {
            mainWin.phaseLog("SPLASH", "Startup launch deferred by deferStartupLaunch=true");
            return;
        }
        if (!mainWin.startupSplashEnabled) {
            mainWin.phaseLog("SPLASH", "Startup splash bypassed by startupSplashEnabled=false");
            mainWin.beginCoreLaunchSequence();
            return;
        }
        if (!mainWin.beginStartupSplashSequence()) {
            mainWin.beginCoreLaunchSequence();
        }
    }

    Component.onDestruction: {
        mainWin.clearStartupDeferredQueue("Component.onDestruction");
        mainWin.persistCurrentThemeSelection("Component.onDestruction");
        mainWin.emitDetachedDidCloseOnce();
    }
    
    Connections {
        target: Qt.application
        enabled: !mainWin.detachedMode
        function onAboutToQuit() {
            mainWin.closeAllTopLevelWindows();
        }
    }
    
    Connections {
        target: mainWin
        function onScreenChanged() {
            try {
                var newScreen = mainWin.screen;
                if (!newScreen) {
                    return;
                }
                if (mainWin.interactionTraceActive()) {
                    mainWin.extendInteractionTrace(120);
                    mainWin.logInteractionTrace("SCREEN", "onScreenChanged", false);
                }

                if (mainWin.userMoveInProgress
                    || mainWin.userResizeInProgress
                    || mainWin.systemMoveInProgress
                    || mainWin.adjacentMoveInProgress
                    || mainWin.dragFinalizePending
                    || mainWin.dragStrategy !== "none"
                    || mainWin.isMinimizing
                    || mainWin.isRestoringFromMinimize
                    || mainWin.maximizeAnimInProgress) {
                    // Avoid mid-interaction screen re-targeting churn.
                    return;
                }
                mainWin.updateDebugOverlayBounds();

                // Closing owns a fixed, all-monitors envelope; ignore transient screen flips.
                if (mainWin.animationPhase === "closing") {
                    return;
                }

                // During opening/closing we lock to the launch monitor and ignore transient flips.
                if (mainWin.animationPhase !== "settled") {
                    if (mainWin.targetScreen && !mainWin.sameScreen(newScreen, mainWin.targetScreen)) {
                        Qt.callLater(function() {
                            mainWin.enforceWindowScreen(mainWin.targetScreen, "opening-screen-flip");
                            mainWin.updateCanvasGeometry();
                        });
                    }
                    return;
                }

                mainWin.updateTargetScreenFromFinalCenter();
                Qt.callLater(function() {
                    mainWin.updateCanvasGeometry();
                });
            } catch (e) {
            }
        }

        function onVisibilityChanged() {
            if (mainWin.visibility === Window.Minimized) {
                mainWin.phaseLog("MINIMIZE", "Host visibility -> Minimized");
                mainWin.wasWindowMinimized = true;
                if (mainWin.maximizeAnimInProgress) {
                    mainWin.stopMaximizeFxAnimations();
                }
                if (mainWin.isMinimizing) {
                    mainWin.isMinimizing = false;
                }
                return;
            }

            if (mainWin.isClosing || mainWin.forceClose) {
                // Close pipeline owns opacity/visibility while exiting; avoid ghost host flashes.
                return;
            }

            var resumedFromTaskbar = mainWin.wasWindowMinimized;
            if (resumedFromTaskbar && !mainWin.isClosing) {
                mainWin.phaseLog("RESTORE", "Taskbar/Tray restore detected; running Gravitational Siphon restore");
                mainWin.isRestoringFromMinimize = true;
                mainWin.wasWindowMinimized = false;

                var targetDistX = mainWin.lastMinimizeTargetDistX;
                var targetDistY = mainWin.lastMinimizeTargetDistY;
                if (!isFinite(targetDistY) || targetDistY <= 0.0) {
                    targetDistY = (mainWin.finalH / 2.0) + mainWin.glowPadding;
                    targetDistX = 0.0;
                }

                jelly.startRestore(targetDistX, targetDistY);
                return;
            }

            if (mainWin.isRestoringFromMinimize) {
                return;
            }

            if (!mainWin.maximizeAnimInProgress && (mainWin.maximizeFxScaleX !== 1.0
                || mainWin.maximizeFxScaleY !== 1.0
                || mainWin.maximizeFxTransX !== 0.0
                || mainWin.maximizeFxTransY !== 0.0
                || mainWin.maximizeFxRotate !== 0.0)) {
                mainWin.resetMaximizeFxState();
            }

            // The cinematic pre-stage intentionally keeps the native host at
            // near-zero opacity until its frozen launch canvas is ready. Do
            // not let this ordinary visibility-recovery hook reveal one full
            // app frame above the still-loading CS splash.
            if (mainWin.opacity !== 1.0 && !mainWin.startupCinematicBloomPrestageOnly) {
                mainWin.opacity = 1.0;
            }
            mainWin.phaseLog("MAIN", "Host visibility resumed state=" + mainWin.visibility);
        }

        function onStartupDeferredQueueEnabledChanged() {
            if (!mainWin.startupDeferredQueueEnabled) {
                mainWin.clearStartupDeferredQueue("startupDeferredQueueEnabledChanged:false");
                return;
            }
            mainWin.requestStartupDeferredQueuePump("startupDeferredQueueEnabledChanged:true");
        }
    }
    
    onClosing: (close) => {
        mainWin.clearStartupDeferredQueue("onClosing");
        if (forceClose) {
            mainWin.emitDetachedDidCloseOnce();
            close.accepted = true;
            return;
        }
        mainWin.persistCurrentThemeSelection("onClosing");
        if (mainWin.appRef && typeof mainWin.appRef.saveCloseSessionSnapshot === "function") {
            try {
                var dockSnapshot = mainWin.getCurrentDockSnapshot ? mainWin.getCurrentDockSnapshot() : {};
                mainWin.appRef.saveCloseSessionSnapshot(dockSnapshot);
            } catch (e) {
                phaseLog("CLOSE", "Failed to save session snapshot on close: " + String(e));
            }
        }
        if (mainWin.recoveryPromptVisible) {
            close.accepted = false;
            return;
        }
        if (!mainWin.detachedMode && mainWin.presentMainCloseGuard("window-manager")) {
            close.accepted = false;
            return;
        }
        if (maximizeAnimInProgress) {
            stopMaximizeFxAnimations();
        }
        if (isMinimizing) {
            isMinimizing = false;
            destroyMinimizeOverlay();
            opacity = 1.0;
            clearMinimizeRestoreState();
        }
        if (isRestoringFromMinimize) {
            isRestoringFromMinimize = false;
            destroyMinimizeOverlay();
            opacity = 1.0;
            clearMinimizeRestoreState();
        }
        close.accepted = false;
        if (!isClosing) {
            mainWin.transitionToClosing();
        }
    }
    
    // ============================================================
    // THEME PICKER
    // ============================================================

    Component {
        id: closingOverlayComponent
        ClosingOverlay {}
    }

    Component {
        id: startupSplashComponent
        SplashOverlay {}
    }

    Component {
        id: minimizeOverlayComponent
        MinimizeOverlay {}
    }

    SfxBus {
        id: sfxBus
        appStyle: mainWin.appStyle
        enabled: mainWin.soundEffectsEnabled
        lowPerformanceMode: mainWin.lowPerformanceMode
    }

    SettingsMenu {
        id: settingsMenu
        t: mainWin.t
        appRef: mainWin.appRef
        metrics: mainWin.uiMetrics
        sfxBus: mainWin.sfxBusRef
        soundEnabled: mainWin.soundEffectsEnabled
        z: 1000
        onThemeRequested: {
            mainWin.openThemePicker();
        }
        onReportBrandingRequested: {
            reportBrandingSettings.openWithProfiles();
        }
        onProductivitySettingsRequested: {
            productivitySettings.open();
        }
        onBackupRecoveryRequested: {
            backupRecoveryDialog.open();
        }
        onSoundChanged: function(enabled) {
            mainWin.applySoundEffectsEnabled(enabled);
        }
    }

    BackupRecoveryDialog {
        id: backupRecoveryDialog
        t: mainWin.t
        appRef: mainWin.appRef
        metrics: mainWin.uiMetrics
        x: Math.max(0, (mainWin.width - width) / 2)
        y: Math.max(0, (mainWin.height - height) / 2)
    }

    ReportBrandingSettingsDialog {
        id: reportBrandingSettings
        parentWindow: mainWin
        t: mainWin.t
        appRef: mainWin.appRef
        metrics: mainWin.uiMetrics
        sfxBus: mainWin.sfxBusRef
        onBrandingChanged: {
            if (mainContent) {
                mainContent.reloadAllActiveReportBranding()
            }
        }
    }

    ProductivitySettingsDialog {
        id: productivitySettings
        parentWindow: mainWin
        t: mainWin.t
        appRef: mainWin.appRef
        metrics: mainWin.uiMetrics
    }
    
    ThemePicker {
        id: themePicker
        t: mainWin.t
        appRef: mainWin.appRef
        metrics: mainWin.uiMetrics
        sfxBus: mainWin.sfxBusRef
        names: mainWin.appRef ? mainWin.appRef.themeNames : []
        onPicked: function(name, payload) {
            mainWin.applyThemeSelection(name, payload);
        }
        z: 999
    }

    Connections {
        target: mainWin.appRef
        enabled: !!mainWin.appRef
        function onThemeChanged() {
            mainWin.syncThemeFromApp();
        }
        function onSoundEffectsChanged() {
            mainWin.syncSoundEffectsFromApp();
        }
    }

    Connections {
        target: typeof trayController !== "undefined" ? trayController : null
        enabled: !mainWin.detachedMode
        ignoreUnknownSignals: true
        function onRequestRestoreFromTray() {
            console.warn("[TRAY-SIGNAL] onRequestRestoreFromTray received in QML");
            mainWin.requestRestoreFromTrayAnimation();
        }
        function onRequestExitFromTray() {
            console.log("[TRAY-SIGNAL] onRequestExitFromTray received in QML");
            mainWin.requestExitFromTrayAnimation();
        }
        function onNavigateToModule(tileIndex, nodeId, state) {
            mainWin.showNormal();
            mainWin.requestActivate();
            if (mainWin.mainContentRef && typeof mainWin.mainContentRef.handleWorkspaceOpenRequested === "function") {
                mainWin.mainContentRef.handleWorkspaceOpenRequested(tileIndex, nodeId, state || {});
            }
        }
        function onOpenSettingsRequested() {
            mainWin.showNormal();
            mainWin.requestActivate();
            mainWin.openSettingsMenu();
        }
    }

    Item {
        id: closeGuardOverlay
        anchors.fill: parent
        visible: mainWin.closeGuardVisible
        enabled: visible
        z: 2210

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: function(mouse) { mouse.accepted = true; }
            onClicked: function(mouse) { mouse.accepted = true; }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.50)
        }

        SemanticPanel {
            id: closeGuardCard
            t: mainWin.t
            role: "dialog"
            tone: "warning"
            padding: 0
            property int panelPad: mainWin.ratioToPixels(0.016, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
            property int panelSpacing: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 8)
            property int actionHeight: mainWin.ratioToPixels(0.044, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 36)
            property int actionHintGap: mainWin.ratioToPixels(0.0042, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 4)
            property int listPad: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
            property int rowPad: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
            readonly property color promptSurface: closeGuardCard.surfaceColor
            readonly property color promptTextColor: closeGuardCard.inkColor
            readonly property color promptAccentColor: closeGuardCard.accentColor
            readonly property var promptTheme: {
                var patched = mainWin.cloneThemeObject(mainWin.t);
                if (!patched) patched = {};
                patched.text = promptTextColor;
                patched.panel = promptSurface;
                patched.panel2 = promptSurface;
                return patched;
            }
            readonly property real contentCenterXLocal: mainWin.canvasLocalX + mainWin.contentLocalX + (Math.max(1, mainWin.finalW) * 0.5)
            readonly property real contentCenterYLocal: mainWin.canvasLocalY + mainWin.contentLocalY + (Math.max(1, mainWin.finalH) * 0.5)
            width: Math.min(
                Math.max(mainWin.ratioToPixels(0.46, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 520), 460),
                Math.max(360, mainWin.width - (panelPad * 6))
            )
            height: closeGuardBody.implicitHeight + (panelPad * 2)
            x: {
                var centerX = contentCenterXLocal;
                if (!isFinite(centerX)) centerX = closeGuardOverlay.width * 0.5;
                var desired = centerX - (width * 0.5);
                var inset = panelPad * 2;
                var minX = inset;
                var maxX = closeGuardOverlay.width - width - inset;
                if (maxX < minX) return Math.round((closeGuardOverlay.width - width) * 0.5);
                return Math.round(Math.max(minX, Math.min(maxX, desired)));
            }
            y: {
                var centerY = contentCenterYLocal;
                if (!isFinite(centerY)) centerY = closeGuardOverlay.height * 0.5;
                var desired = centerY - (height * 0.5);
                var inset = panelPad * 2;
                var minY = inset;
                var maxY = closeGuardOverlay.height - height - inset;
                if (maxY < minY) return Math.round((closeGuardOverlay.height - height) * 0.5);
                return Math.round(Math.max(minY, Math.min(maxY, desired)));
            }
            radius: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 10)
            borderWidth: mainWin.ratioToPixels(0.0018, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)

            Rectangle {
                anchors.fill: parent
                radius: closeGuardCard.radius
                color: Qt.rgba(mainWin.t.panel2.r, mainWin.t.panel2.g, mainWin.t.panel2.b, 0.28)
                border.width: 0
            }

            Column {
                id: closeGuardBody
                anchors.fill: parent
                anchors.margins: closeGuardCard.panelPad
                spacing: closeGuardCard.panelSpacing

                Text {
                    text: mainWin.closeGuardTitle
                    color: closeGuardCard.promptAccentColor
                    font.pixelSize: mainWin.ratioToPixels(0.020, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 16)
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: mainWin.closeGuardMessage
                    color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.90)
                    font.pixelSize: mainWin.ratioToPixels(0.014, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "Open windows (click to focus):"
                    color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.95)
                    font.pixelSize: mainWin.ratioToPixels(0.0135, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                    font.weight: Font.DemiBold
                    width: parent.width
                    horizontalAlignment: Text.AlignLeft
                }

                Rectangle {
                    id: closeGuardRowsFrame
                    width: parent.width
                    height: Math.min(
                        Math.max(closeGuardRowsColumn.implicitHeight + (closeGuardCard.listPad * 2), mainWin.ratioToPixels(0.12, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 112)),
                        mainWin.ratioToPixels(0.34, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 250)
                    )
                    radius: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
                    color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.08)
                    border.width: 1
                    border.color: Qt.rgba(closeGuardCard.promptAccentColor.r, closeGuardCard.promptAccentColor.g, closeGuardCard.promptAccentColor.b, 0.34)

                    Flickable {
                        id: closeGuardRowsFlick
                        anchors.fill: parent
                        anchors.margins: closeGuardCard.listPad
                        contentWidth: width
                        contentHeight: closeGuardRowsColumn.implicitHeight
                        boundsBehavior: Flickable.StopAtBounds
                        clip: true
                        interactive: contentHeight > height

                        Column {
                            id: closeGuardRowsColumn
                            width: closeGuardRowsFlick.width
                            spacing: closeGuardCard.listPad

                            Repeater {
                                model: mainWin.closeGuardWindowRows
                                delegate: Rectangle {
                                    id: closeGuardRow
                                    required property var modelData
                                    property bool hovered: rowMouse.containsMouse
                                    width: closeGuardRowsColumn.width
                                    height: rowBody.implicitHeight + (closeGuardCard.rowPad * 2)
                                    radius: mainWin.ratioToPixels(0.0058, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 5)
                                    color: hovered
                                        ? Qt.rgba(closeGuardCard.promptAccentColor.r, closeGuardCard.promptAccentColor.g, closeGuardCard.promptAccentColor.b, 0.26)
                                        : Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.10)
                                    border.width: 1
                                    border.color: hovered
                                        ? Qt.rgba(closeGuardCard.promptAccentColor.r, closeGuardCard.promptAccentColor.g, closeGuardCard.promptAccentColor.b, 0.78)
                                        : Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.22)

                                    Column {
                                        id: rowBody
                                        x: closeGuardCard.rowPad
                                        y: closeGuardCard.rowPad
                                        width: parent.width - (closeGuardCard.rowPad * 2)
                                        spacing: mainWin.ratioToPixels(0.0036, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 3)

                                        Text {
                                            width: parent.width
                                            text: closeGuardRow.modelData && closeGuardRow.modelData.windowLabel ? String(closeGuardRow.modelData.windowLabel) : "Window"
                                            color: closeGuardCard.promptAccentColor
                                            font.pixelSize: mainWin.ratioToPixels(0.014, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                                            font.weight: Font.DemiBold
                                            font.underline: true
                                            wrapMode: Text.WordWrap
                                        }

                                        Text {
                                            width: parent.width
                                            text: closeGuardRow.modelData && closeGuardRow.modelData.detailText ? String(closeGuardRow.modelData.detailText) : ""
                                            color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.94)
                                            font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                                            wrapMode: Text.WordWrap
                                        }

                                        Text {
                                            width: parent.width
                                            text: closeGuardRow.modelData && closeGuardRow.modelData.statusText ? String(closeGuardRow.modelData.statusText) : ""
                                            color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.80)
                                            font.pixelSize: mainWin.ratioToPixels(0.0118, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 10)
                                            wrapMode: Text.WordWrap
                                        }
                                    }

                                    MouseArea {
                                        id: rowMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                                mainWin.sfxBusRef.playUiClick("open", 0.52);
                                            }
                                            if (closeGuardRow.modelData && closeGuardRow.modelData.windowId) {
                                                mainWin.focusWindowFromCloseGuard(closeGuardRow.modelData.windowId);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: mainWin.ratioToPixels(0.0012, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)
                    color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.22)
                }

                Item {
                    width: parent.width
                    height: reviewWindowsButton.height + closeGuardCard.actionHintGap + reviewWindowsHint.implicitHeight

                    PillButton {
                        id: reviewWindowsButton
                        t: closeGuardCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Review Windows"
                        primary: false
                        width: parent.width
                        height: closeGuardCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("open", 0.48);
                            }
                            mainWin.closeGuardReviewWindows();
                        }
                    }

                    Text {
                        id: reviewWindowsHint
                        width: parent.width
                        anchors.top: reviewWindowsButton.bottom
                        anchors.topMargin: closeGuardCard.actionHintGap
                        color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Cancel exit and review open windows."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    width: parent.width
                    height: saveAllExitButton.height + closeGuardCard.actionHintGap + saveAllExitHint.implicitHeight

                    PillButton {
                        id: saveAllExitButton
                        t: closeGuardCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Save All and Exit"
                        primary: true
                        width: parent.width
                        height: closeGuardCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("confirm", 0.74);
                            }
                            mainWin.closeGuardSaveAllAndExit();
                        }
                    }

                    Text {
                        id: saveAllExitHint
                        width: parent.width
                        anchors.top: saveAllExitButton.bottom
                        anchors.topMargin: closeGuardCard.actionHintGap
                        color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Checkpoint all open window state, then exit."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    width: parent.width
                    height: exitWithoutSavingButton.height + closeGuardCard.actionHintGap + exitWithoutSavingHint.implicitHeight

                    PillButton {
                        id: exitWithoutSavingButton
                        t: closeGuardCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Exit Without Saving"
                        primary: false
                        width: parent.width
                        height: closeGuardCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("danger", 0.72);
                            }
                            mainWin.closeGuardExitWithoutSaving();
                        }
                    }

                    Text {
                        id: exitWithoutSavingHint
                        width: parent.width
                        anchors.top: exitWithoutSavingButton.bottom
                        anchors.topMargin: closeGuardCard.actionHintGap
                        color: Qt.rgba(closeGuardCard.promptTextColor.r, closeGuardCard.promptTextColor.g, closeGuardCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Close now and discard unsaved changes."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }

    Item {
        id: recoveryPromptOverlay
        anchors.fill: parent
        visible: mainWin.recoveryPromptVisible
        enabled: visible
        z: 2215

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: function(mouse) { mouse.accepted = true; }
            onClicked: function(mouse) { mouse.accepted = true; }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.50)
        }

        SemanticPanel {
            id: recoveryPromptCard
            t: mainWin.t
            role: "dialog"
            tone: "info"
            padding: 0
            property int panelPad: mainWin.ratioToPixels(0.016, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
            property int panelSpacing: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 8)
            property int actionHeight: mainWin.ratioToPixels(0.044, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 36)
            property int actionHintGap: mainWin.ratioToPixels(0.0042, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 4)
            property int listPad: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
            property int rowPad: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
            readonly property color promptSurface: recoveryPromptCard.surfaceColor
            readonly property color promptTextColor: recoveryPromptCard.inkColor
            readonly property color promptAccentColor: recoveryPromptCard.accentColor
            readonly property var promptTheme: {
                var patched = mainWin.cloneThemeObject(mainWin.t);
                if (!patched) patched = {};
                patched.text = promptTextColor;
                patched.panel = promptSurface;
                patched.panel2 = promptSurface;
                return patched;
            }
            readonly property real contentCenterXLocal: mainWin.canvasLocalX + mainWin.contentLocalX + (Math.max(1, mainWin.finalW) * 0.5)
            readonly property real contentCenterYLocal: mainWin.canvasLocalY + mainWin.contentLocalY + (Math.max(1, mainWin.finalH) * 0.5)
            width: Math.min(
                Math.max(mainWin.ratioToPixels(0.42, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 460), 420),
                Math.max(340, mainWin.width - (panelPad * 6))
            )
            height: recoveryPromptBody.implicitHeight + (panelPad * 2)
            x: {
                var centerX = contentCenterXLocal;
                if (!isFinite(centerX)) centerX = recoveryPromptOverlay.width * 0.5;
                var desired = centerX - (width * 0.5);
                var inset = panelPad * 2;
                var minX = inset;
                var maxX = recoveryPromptOverlay.width - width - inset;
                if (maxX < minX) return Math.round((recoveryPromptOverlay.width - width) * 0.5);
                return Math.round(Math.max(minX, Math.min(maxX, desired)));
            }
            y: {
                var centerY = contentCenterYLocal;
                if (!isFinite(centerY)) centerY = recoveryPromptOverlay.height * 0.5;
                var desired = centerY - (height * 0.5);
                var inset = panelPad * 2;
                var minY = inset;
                var maxY = recoveryPromptOverlay.height - height - inset;
                if (maxY < minY) return Math.round((recoveryPromptOverlay.height - height) * 0.5);
                return Math.round(Math.max(minY, Math.min(maxY, desired)));
            }
            radius: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 10)
            borderWidth: mainWin.ratioToPixels(0.0018, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)

            Rectangle {
                anchors.fill: parent
                radius: recoveryPromptCard.radius
                color: Qt.rgba(mainWin.t.panel2.r, mainWin.t.panel2.g, mainWin.t.panel2.b, 0.28)
                border.width: 0
            }

            Column {
                id: recoveryPromptBody
                anchors.fill: parent
                anchors.margins: recoveryPromptCard.panelPad
                spacing: recoveryPromptCard.panelSpacing

                Text {
                    text: mainWin.recoveryPromptTitle
                    color: recoveryPromptCard.promptAccentColor
                    font.pixelSize: mainWin.ratioToPixels(0.020, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 16)
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: mainWin.recoveryPromptMessage
                    color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.90)
                    font.pixelSize: mainWin.ratioToPixels(0.014, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "Recovered window snapshot:"
                    color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.95)
                    font.pixelSize: mainWin.ratioToPixels(0.0135, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                    font.weight: Font.DemiBold
                    width: parent.width
                    horizontalAlignment: Text.AlignLeft
                }

                Rectangle {
                    id: recoveryPromptRowsFrame
                    width: parent.width
                    height: Math.min(
                        Math.max(recoveryPromptRowsColumn.implicitHeight + (recoveryPromptCard.listPad * 2), mainWin.ratioToPixels(0.10, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 92)),
                        mainWin.ratioToPixels(0.28, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 210)
                    )
                    radius: mainWin.ratioToPixels(0.007, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 6)
                    color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.08)
                    border.width: 1
                    border.color: Qt.rgba(recoveryPromptCard.promptAccentColor.r, recoveryPromptCard.promptAccentColor.g, recoveryPromptCard.promptAccentColor.b, 0.34)

                    Flickable {
                        id: recoveryPromptRowsFlick
                        anchors.fill: parent
                        anchors.margins: recoveryPromptCard.listPad
                        contentWidth: width
                        contentHeight: recoveryPromptRowsColumn.implicitHeight
                        boundsBehavior: Flickable.StopAtBounds
                        clip: true
                        interactive: contentHeight > height

                        Column {
                            id: recoveryPromptRowsColumn
                            width: recoveryPromptRowsFlick.width
                            spacing: recoveryPromptCard.listPad

                            Repeater {
                                model: mainWin.recoveryPromptRows
                                delegate: Rectangle {
                                    id: recoveryPromptRow
                                    required property var modelData
                                    width: recoveryPromptRowsColumn.width
                                    height: recoveryRowBody.implicitHeight + (recoveryPromptCard.rowPad * 2)
                                    radius: mainWin.ratioToPixels(0.0058, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 5)
                                    color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.10)
                                    border.width: 1
                                    border.color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.22)

                                    Column {
                                        id: recoveryRowBody
                                        x: recoveryPromptCard.rowPad
                                        y: recoveryPromptCard.rowPad
                                        width: parent.width - (recoveryPromptCard.rowPad * 2)
                                        spacing: mainWin.ratioToPixels(0.0036, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 3)

                                        Text {
                                            width: parent.width
                                            text: recoveryPromptRow.modelData && recoveryPromptRow.modelData.windowLabel ? String(recoveryPromptRow.modelData.windowLabel) : "Window"
                                            color: recoveryPromptCard.promptAccentColor
                                            font.pixelSize: mainWin.ratioToPixels(0.014, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                                            font.weight: Font.DemiBold
                                            wrapMode: Text.WordWrap
                                        }

                                        Text {
                                            width: parent.width
                                            text: recoveryPromptRow.modelData && recoveryPromptRow.modelData.detailText ? String(recoveryPromptRow.modelData.detailText) : ""
                                            color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.94)
                                            font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                                            wrapMode: Text.WordWrap
                                        }

                                        Text {
                                            width: parent.width
                                            text: recoveryPromptRow.modelData && recoveryPromptRow.modelData.statusText ? String(recoveryPromptRow.modelData.statusText) : ""
                                            color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.80)
                                            font.pixelSize: mainWin.ratioToPixels(0.0118, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 10)
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: mainWin.ratioToPixels(0.0012, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)
                    color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.22)
                }

                Item {
                    width: parent.width
                    height: recoverWindowsButton.height + recoveryPromptCard.actionHintGap + recoverWindowsHint.implicitHeight

                    PillButton {
                        id: recoverWindowsButton
                        t: recoveryPromptCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Reopen Windows"
                        primary: true
                        width: parent.width
                        height: recoveryPromptCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("confirm", 0.74);
                            }
                            mainWin.recoverUnsavedWindows();
                        }
                    }

                    Text {
                        id: recoverWindowsHint
                        width: parent.width
                        anchors.top: recoverWindowsButton.bottom
                        anchors.topMargin: recoveryPromptCard.actionHintGap
                        color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Restore unsaved windows and their in-progress data state."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    width: parent.width
                    height: resetRecoveredButton.height + recoveryPromptCard.actionHintGap + resetRecoveredHint.implicitHeight

                    PillButton {
                        id: resetRecoveredButton
                        t: recoveryPromptCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Reset to Default"
                        primary: false
                        width: parent.width
                        height: recoveryPromptCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("danger", 0.72);
                            }
                            mainWin.resetRecoveredWindows();
                        }
                    }

                    Text {
                        id: resetRecoveredHint
                        width: parent.width
                        anchors.top: resetRecoveredButton.bottom
                        anchors.topMargin: recoveryPromptCard.actionHintGap
                        color: Qt.rgba(recoveryPromptCard.promptTextColor.r, recoveryPromptCard.promptTextColor.g, recoveryPromptCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Discard recovered draft windows and continue with a clean workspace."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }

    Item {
        id: redockPromptOverlay
        anchors.fill: parent
        visible: mainWin.redockPromptVisible
        enabled: visible
        z: 2200

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: function(mouse) { mouse.accepted = true; }
            onClicked: function(mouse) { mouse.accepted = true; }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.46)
        }

        SemanticPanel {
            id: redockPromptCard
            t: mainWin.t
            role: "dialog"
            tone: "info"
            padding: 0
            property int panelPad: mainWin.ratioToPixels(0.016, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
            property int panelSpacing: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 8)
            property int actionHeight: mainWin.ratioToPixels(0.044, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 36)
            property int actionHintGap: mainWin.ratioToPixels(0.0042, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 4)
            readonly property color promptSurface: redockPromptCard.surfaceColor
            readonly property color promptTextColor: redockPromptCard.inkColor
            readonly property color promptAccentColor: redockPromptCard.accentColor
            readonly property var promptTheme: {
                var patched = mainWin.cloneThemeObject(mainWin.t);
                if (!patched) patched = {};
                patched.text = promptTextColor;
                patched.panel = promptSurface;
                patched.panel2 = promptSurface;
                return patched;
            }
            readonly property real contentCenterXLocal: mainWin.canvasLocalX + mainWin.contentLocalX + (Math.max(1, mainWin.finalW) * 0.5)
            readonly property real contentCenterYLocal: mainWin.canvasLocalY + mainWin.contentLocalY + (Math.max(1, mainWin.finalH) * 0.5)
            width: Math.min(
                Math.max(mainWin.ratioToPixels(0.34, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 356), 340),
                Math.max(320, mainWin.width - (panelPad * 6))
            )
            height: promptBody.implicitHeight + (panelPad * 2)
            x: {
                var centerX = contentCenterXLocal;
                if (!isFinite(centerX)) centerX = redockPromptOverlay.width * 0.5;
                var desired = centerX - (width * 0.5);
                var inset = panelPad * 2;
                var minX = inset;
                var maxX = redockPromptOverlay.width - width - inset;
                if (maxX < minX) return Math.round((redockPromptOverlay.width - width) * 0.5);
                return Math.round(Math.max(minX, Math.min(maxX, desired)));
            }
            y: {
                var centerY = contentCenterYLocal;
                if (!isFinite(centerY)) centerY = redockPromptOverlay.height * 0.5;
                var desired = centerY - (height * 0.5);
                var inset = panelPad * 2;
                var minY = inset;
                var maxY = redockPromptOverlay.height - height - inset;
                if (maxY < minY) return Math.round((redockPromptOverlay.height - height) * 0.5);
                return Math.round(Math.max(minY, Math.min(maxY, desired)));
            }
            radius: mainWin.ratioToPixels(0.010, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 10)
            borderWidth: mainWin.ratioToPixels(0.0018, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)

            Rectangle {
                anchors.fill: parent
                radius: redockPromptCard.radius
                color: Qt.rgba(mainWin.t.panel2.r, mainWin.t.panel2.g, mainWin.t.panel2.b, 0.28)
                border.width: 0
            }

            Column {
                id: promptBody
                anchors.fill: parent
                anchors.margins: redockPromptCard.panelPad
                spacing: redockPromptCard.panelSpacing

                Text {
                    text: mainWin.redockPromptTitle
                    color: redockPromptCard.promptAccentColor
                    font.pixelSize: mainWin.ratioToPixels(0.020, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 16)
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: mainWin.redockPromptMessage
                    color: Qt.rgba(redockPromptCard.promptTextColor.r, redockPromptCard.promptTextColor.g, redockPromptCard.promptTextColor.b, 0.90)
                    font.pixelSize: mainWin.ratioToPixels(0.014, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 12)
                    wrapMode: Text.WordWrap
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                }

                Rectangle {
                    width: parent.width
                    height: mainWin.ratioToPixels(0.0012, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 1)
                    color: Qt.rgba(redockPromptCard.promptTextColor.r, redockPromptCard.promptTextColor.g, redockPromptCard.promptTextColor.b, 0.22)
                }

                Item {
                    width: parent.width
                    height: cancelButton.height + redockPromptCard.actionHintGap + cancelHint.implicitHeight

                    PillButton {
                        id: cancelButton
                        t: redockPromptCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Cancel"
                        primary: false
                        width: parent.width
                        height: redockPromptCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("dismiss", 0.42);
                            }
                            mainWin.closeRedockPrompt();
                        }
                    }

                    Text {
                        id: cancelHint
                        width: parent.width
                        anchors.top: cancelButton.bottom
                        anchors.topMargin: redockPromptCard.actionHintGap
                        color: Qt.rgba(redockPromptCard.promptTextColor.r, redockPromptCard.promptTextColor.g, redockPromptCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Keep this panel detached for now."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    width: parent.width
                    height: autoButton.height + redockPromptCard.actionHintGap + autoHint.implicitHeight
                    opacity: mainWin.redockPromptAllowAuto ? 1.0 : 0.62

                    PillButton {
                        id: autoButton
                        t: redockPromptCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Auto Dock"
                        primary: true
                        enabled: mainWin.redockPromptAllowAuto
                        width: parent.width
                        height: redockPromptCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("confirm", 0.70);
                            }
                            mainWin.redockPromptAutoReturnAndDock();
                        }
                    }

                    Text {
                        id: autoHint
                        width: parent.width
                        anchors.top: autoButton.bottom
                        anchors.topMargin: redockPromptCard.actionHintGap
                        color: Qt.rgba(redockPromptCard.promptTextColor.r, redockPromptCard.promptTextColor.g, redockPromptCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Return main to Main Menu and dock this panel."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    width: parent.width
                    height: focusButton.height + redockPromptCard.actionHintGap + focusHint.implicitHeight
                    opacity: mainWin.redockPromptAllowFocus ? 1.0 : 0.62

                    PillButton {
                        id: focusButton
                        t: redockPromptCard.promptTheme
                        metrics: mainWin.uiMetrics
                        text: "Focus Main"
                        primary: false
                        enabled: mainWin.redockPromptAllowFocus
                        width: parent.width
                        height: redockPromptCard.actionHeight
                        onClicked: {
                            if (mainWin.sfxBusRef && mainWin.sfxBusRef.playUiClick) {
                                mainWin.sfxBusRef.playUiClick("open", 0.46);
                            }
                            mainWin.redockPromptFocusMain();
                        }
                    }

                    Text {
                        id: focusHint
                        width: parent.width
                        anchors.top: focusButton.bottom
                        anchors.topMargin: redockPromptCard.actionHintGap
                        color: Qt.rgba(redockPromptCard.promptTextColor.r, redockPromptCard.promptTextColor.g, redockPromptCard.promptTextColor.b, 0.90)
                        font.pixelSize: mainWin.ratioToPixels(0.0125, Math.max(1, mainWin.finalW), Math.max(1, mainWin.finalH), 11)
                        text: "Bring main forward without docking yet."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }

    // --- SAFE 1% OPACITY GPU WARMUP ---
    Timer {
        id: gpuWarmupStep1
        interval: 25
        running: mainWin.appStyle !== "Professional"
        repeat: false
        onTriggered: {
            if (mainWin.appStyle === "Professional") {
                return;
            }
            if (mainWin && mainWin.targetScreen && typeof mainWin.applyDragInteractionGeometry === "function") {
                mainWin.opacity = 0.01;
                var prev = mainWin.geometryTransitionSuppressed;
                mainWin.geometryTransitionSuppressed = true;
                mainWin.applyDragInteractionGeometry();
                mainWin.geometryTransitionSuppressed = prev;
                gpuWarmupStep2.start();
            }
        }
    }
    Timer {
        id: gpuWarmupStep2
        interval: 75
        repeat: false
        onTriggered: {
            if (mainWin && typeof mainWin.applyHostEnvelopeForTarget === "function") {
                var prev = mainWin.geometryTransitionSuppressed;
                mainWin.geometryTransitionSuppressed = true;
                mainWin.applyHostEnvelopeForTarget();
                mainWin.geometryTransitionSuppressed = prev;
                mainWin.opacity = 1.0;
            }
        }
    }

    // Invisible keep-alive window — prevents frozen PyInstaller lastWindowClosed
    // from killing the app while the main window is hidden in the system tray.
    Window {
        id: trayKeepAlive
        visible: false
        width: 1; height: 1
        x: -9999; y: -9999
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput
        color: "transparent"
        title: "CSPMTrayKeepAlive"
    }
}
