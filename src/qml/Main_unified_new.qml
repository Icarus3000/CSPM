import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtCore
import "components"
import "views"
import "standards"

ApplicationWindow {
    id: mainWin
    title: "CSPM-MainWindow"
    objectName: "CSPMMainWindow"
    
    // ============================================================
    // STATE MANAGEMENT
    // ============================================================
    property bool isSettled: false
    property bool isClosing: false
    property bool forceClose: false
    property bool launchConfigured: false
    property int targetScreenIndex: -1
    property bool closeMotionStarted: false
    property bool geometryTransitionSuppressed: false
    property bool userMoveInProgress: false
    
    // --- PHASE TRACKING ---
    /// OPENING: jelly animates freely, canvas = full monitor
    /// SETTLED: jelly frozen, canvas shrinks to window+padding, window interactive
    /// CLOSING: jelly animates out, canvas expands to full monitor
    property string animationPhase: "opening"  // "opening" | "settled" | "closing"
    
    // --- GEOMETRY TRACKING ---
    property int finalX: 0
    property int finalY: 0
    property int finalW: 1220
    property int finalH: 920
    property int glowPadding: 500
    
    // --- SCREEN & SPACING ---
    property var targetScreen: null
    property var targetScreenInfo: null
    
    // --- CANVAS SIZING (Dynamic) ---
    property int canvasX: 0
    property int canvasY: 0
    property int canvasW: 1920
    property int canvasH: 1080
    
    // ============================================================
    // WINDOW SETUP
    // ============================================================
    visible: true
    color: "transparent"  // Only opaque content is the canvas children
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
    opacity: 1.0
    
    // Window geometry animates smoothly as canvas size/position changes
    Behavior on width {
        enabled: mainWin.animationPhase === "settled"
            && !mainWin.geometryTransitionSuppressed
            && !mainWin.userMoveInProgress
        NumberAnimation {
            duration: 200
            easing.type: Easing.InOutQuad
        }
    }
    Behavior on height {
        enabled: mainWin.animationPhase === "settled"
            && !mainWin.geometryTransitionSuppressed
            && !mainWin.userMoveInProgress
        NumberAnimation {
            duration: 200
            easing.type: Easing.InOutQuad
        }
    }
    Behavior on x {
        enabled: mainWin.animationPhase === "settled"
            && !mainWin.geometryTransitionSuppressed
            && !mainWin.userMoveInProgress
        NumberAnimation {
            duration: 200
            easing.type: Easing.InOutQuad
        }
    }
    Behavior on y {
        enabled: mainWin.animationPhase === "settled"
            && !mainWin.geometryTransitionSuppressed
            && !mainWin.userMoveInProgress
        NumberAnimation {
            duration: 200
            easing.type: Easing.InOutQuad
        }
    }
    
    // Window size/position follow canvas geometry
    width: canvasW
    height: canvasH
    x: canvasX
    y: canvasY
    
    // === WINDOW MOVEMENT TRACKING ===
    // When user drags the settled window, update finalX/Y and recalculate canvas
    onXChanged: {
        if (isSettled && !isClosing && animationPhase === "settled") {
            // During settled, window drag updates the settled position
            finalX = Math.round(x + (canvasW - finalW) / 2);
            console.log("[MOVE] Window dragged -> x=" + x + " finalX=" + finalX);
            updateCanvasGeometry();
        }
    }
    onYChanged: {
        if (isSettled && !isClosing && animationPhase === "settled") {
            // During settled, window drag updates the settled position
            finalY = Math.round(y + (canvasH - finalH) / 2);
            console.log("[MOVE] Window dragged -> y=" + y + " finalY=" + finalY);
            updateCanvasGeometry();
        }
    }
    
    // Shortcut { sequence: "Esc"; onActivated: Qt.quit() }
    VisualRules { id: style; appStyle: mainWin.appStyle }
    
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property string appStyle: (appRef && appRef.appStyle) ? String(appRef.appStyle) : "Professional"
    property var t: {
        try {
            if (appRef && appRef.theme && appRef.theme.bg) {
                return appRef.theme;
            }
        } catch(e) { }
        return {
            "bg": "#000000", "accent": "#2979FF", "text": "#FFFFFF", "glow": "#FF1744"
        };
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
    
    function currentCursorScreenIndex() {
        var idx = 0;
        if (appRef && appRef.getCursorScreenIndex) {
            idx = appRef.getCursorScreenIndex();
        }
        var screens = Qt.application.screens;
        if (!screens || screens.length === 0) return 0;
        if (idx < 0 || idx >= screens.length) idx = 0;
        return idx;
    }
    
    function resolveTargetScreen() {
        var screens = Qt.application.screens;
        if (!screens || screens.length === 0) {
            console.error("[MAIN] No screens available");
            return null;
        }
        var idx = currentCursorScreenIndex();
        targetScreenIndex = idx;
        targetScreen = screens[idx];
        targetScreenInfo = null;
        if (appRef && appRef.getScreenGeometry) {
            targetScreenInfo = appRef.getScreenGeometry(idx);
        }
        console.log("[MAIN] Selected cursor screen index=" + idx + " " + describeScreen(targetScreen));
        return targetScreen;
    }
    
    function applyGeometryToTargetScreen() {
        var selected = targetScreen ? targetScreen : resolveTargetScreen();
        if (!selected) return false;
        
        try {
            mainWin.screen = selected;
        } catch (e) {
            console.log("[MAIN] Failed to assign main window screen:", e);
        }
        
        var ux = selected.virtualX;
        var uy = selected.virtualY;
        var uw = selected.width;
        var uh = selected.height;
        
        if (targetScreenInfo) {
            if (typeof targetScreenInfo.availX === "number") ux = targetScreenInfo.availX;
            if (typeof targetScreenInfo.availY === "number") uy = targetScreenInfo.availY;
            if (typeof targetScreenInfo.availW === "number" && targetScreenInfo.availW > 0) uw = targetScreenInfo.availW;
            if (typeof targetScreenInfo.availH === "number" && targetScreenInfo.availH > 0) uh = targetScreenInfo.availH;
        }
        
        var taskbarSafety = 16;
        var safeH = Math.max(200, uh - taskbarSafety);
        var fitW = uw - 50;
        var fitH = safeH - 50;
        var fit = Math.min(1.0, Math.min(fitW / 1220.0, fitH / 920.0));
        var scaleFactor = fit * 0.95;
        
        finalW = Math.round((1220 * scaleFactor) + 50);
        finalH = Math.round((920 * scaleFactor) + 50);
        finalX = Math.round((ux + (uw / 2.0)) - (finalW / 2.0));
        finalY = Math.round((uy + (safeH / 2.0)) - (finalH / 2.0));
        
        if (!launchConfigured) {
            launchConfigured = true;
            try {
                mainWin.x = finalX - 34;
                mainWin.y = finalY - 34;
            } catch (e) {
                console.log("[MAIN] Failed to position main window:", e);
            }
            mainWin.show();
        }
        mainWin.raise();
        if ((mainWin.flags & Qt.WindowDoesNotAcceptFocus) !== Qt.WindowDoesNotAcceptFocus) {
            mainWin.requestActivate();
        }
        
        console.log("[MAIN] Launch geometry x=" + finalX + " y=" + finalY
            + " w=" + finalW + " h=" + finalH);
        return true;
    }
    
    function logTopLevelWindows(tag) {
        var windows = (Qt.application && Qt.application.topLevelWindows) ? Qt.application.topLevelWindows : [];
        console.log("[MAIN] [" + tag + "] topLevelWindows=" + windows.length);
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (!w) continue;
            var title = w.title ? w.title : "";
            console.log("[MAIN] [" + tag + "] window[" + i + "] '" + title + "' vis=" + w.visible
                + " pos=" + w.x + "," + w.y + " size=" + w.width + "x" + w.height);
        }
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
    
    function updateCanvasGeometry() {
        var windowCenterX = finalX + (finalW / 2);
        var windowCenterY = finalY + (finalH / 2);
        var padding = glowPadding;
        
        if (animationPhase === "opening" || animationPhase === "closing") {
            // OPENING/CLOSING: Full monitor canvas
            if (!targetScreen) {
                console.log("[CANVAS] Cannot update - no targetScreen");
                return;
            }
            canvasW = targetScreen.width;
            canvasH = targetScreen.height;
            canvasX = targetScreen.virtualX;
            canvasY = targetScreen.virtualY;
            
            // Content position within canvas: globalX - canvasX
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
            
        } else if (animationPhase === "settled") {
            // SETTLED: Window + padding, centered on window center point
            canvasW = finalW + (padding * 2);
            canvasH = finalH + (padding * 2);
            canvasX = windowCenterX - (canvasW / 2);
            canvasY = windowCenterY - (canvasH / 2);
            
            // Content position within canvas: globalX - canvasX
            contentLocalX = finalX - canvasX;
            contentLocalY = finalY - canvasY;
        }
        
        console.log("[CANVAS] Phase=" + animationPhase 
            + " canvasGeom=(" + canvasX + "," + canvasY + ") " + canvasW + "x" + canvasH
            + " contentLocalPos=(" + contentLocalX + "," + contentLocalY + ")"
            + " globalContentPos=(" + (canvasX + contentLocalX) + "," + (canvasY + contentLocalY) + ")"
            + " expectedGlobalPos=(" + finalX + "," + finalY + ")");
    }
    
    // ============================================================
    // PHASE TRANSITIONS
    // ============================================================
    
    function transitionToSettled() {
        console.log("[PHASE] Transitioning OPENING → SETTLED");
        animationPhase = "settled";
        isSettled = true;
        updateCanvasGeometry();
        canvasTransition.start();
        performGlowShrinkage();
    }
    
    function transitionToClosing() {
        console.log("[PHASE] Transitioning SETTLED → CLOSING");
        if (isClosing) return;  // Already in closing
        
        isClosing = true;
        closeMotionStarted = false;
        animationPhase = "closing";
        
        // Capture current window position for close animation origin
        try {
            finalX = Math.round(mainWin.x + 34);
            finalY = Math.round(mainWin.y + 34);
            if (mainWin.screen) {
                targetScreen = mainWin.screen;
            }
        } catch (e) {
            console.log("[CLOSE] Failed to capture window geometry:", e);
        }
        
        updateCanvasGeometry();
        canvasTransition.start();
        
        // Freeze jelly at identity before expanding canvas
        jelly.freezeToIdentity();
        
        // Start close motion after canvas transition
        Qt.callLater(function() {
            mainWin.startCloseMotion("phase-transition");
        });
    }
    
    // ============================================================
    // CANVAS TRANSITION ANIMATION
    // ============================================================
    
    SequentialAnimation {
        id: canvasTransition
        
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
    
    // ============================================================
    // GLOW SHRINKAGE (VISUAL EFFECT ONLY)
    // ============================================================
    
    function performGlowShrinkage() {
        glowShrinkAnimation.start();
    }
    
    ParallelAnimation {
        id: glowShrinkAnimation
        property int targetPadding: 45
        
        PropertyAnimation {
            target: mainWin
            property: "glowPadding"
            duration: 180
            easing.type: Easing.InOutQuad
            from: 500
            to: glowShrinkAnimation.targetPadding
        }
        
        NumberAnimation {
            duration: 180
        }
    }
    
    // ============================================================
    // ANIMATION CANVAS (Unified, Three-Phase)
    // ============================================================
    
    Item {
        id: animationCanvasLayer
        // Canvas fills the window (which is sized based on phase)
        anchors.fill: parent
        
        // Apply jelly transforms during animation phases only (not during settled)
        transform: [
            Scale {
                origin.x: animationCanvasLayer.width / 2
                origin.y: animationCanvasLayer.height / 2
                xScale: (mainWin.mainWin.animationPhase !== "settled") ? jelly.scaleX : 1.0
                yScale: (mainWin.mainWin.animationPhase !== "settled") ? jelly.scaleY : 1.0
            },
            Translate {
                x: (mainWin.mainWin.animationPhase !== "settled") ? jelly.transX : 0
                y: (mainWin.mainWin.animationPhase !== "settled") ? jelly.transY : 0
            },
            Rotation {
                origin.x: animationCanvasLayer.width / 2
                origin.y: animationCanvasLayer.height / 2
                angle: (mainWin.mainWin.animationPhase !== "settled") ? jelly.rotationVal : 0.0
            }
        ]
        
        opacity: (mainWin.mainWin.animationPhase !== "settled") ? jelly.opacityVal : 1.0
        
        // CONTENT LAYER - Position within canvas keeps window pixels fixed
        Item {
            id: contentLayer
            x: mainWin.mainWin.contentLocalX
            y: mainWin.mainWin.contentLocalY
            width: mainWin.mainWin.finalW
            height: mainWin.mainWin.finalH
            
            Item {
                id: masterBody
                anchors.fill: parent
                
                ChromeSurface {
                    id: unifiedChrome
                    anchors.fill: parent
                    glowRadiusNear: 18
                    glowRadiusFar: 54
                    plasmaOpacity: 1.0
                    t: mainWin.t
                    cornerRadius: 16
                    MainContent {
                        anchors.fill: parent
                        t: mainWin.t
                        appRef: mainWin.appRef
                        isInteractive: mainWin.isSettled && !mainWin.isClosing
                        windowRef: mainWin
                    }
                }
                
                // TITLEBAR FOR DRAGGING (only interactive when settled)
                Rectangle {
                    id: titleBar
                    width: parent.width
                    height: Math.max(1, Math.round(mainWin.finalH * 0.061))
                    color: "transparent"
                    visible: mainWin.isSettled && !mainWin.isClosing
                    z: 1
                    
                    DragHandler {
                        target: null
                        enabled: mainWin.isSettled && !mainWin.isClosing
                        onActiveChanged: {
                            if (active) {
                                mainWin.geometryTransitionSuppressed = true;
                                mainWin.userMoveInProgress = true;
                                mainWin.startSystemMove();
                            } else {
                                mainWin.userMoveInProgress = false;
                                mainWin.geometryTransitionSuppressed = false;
                            }
                        }
                    }
                }
            }
        }
    }
    
    // ============================================================
    // WINDOW CONTROLS
    // ============================================================
    
    function openThemePicker() {
        if (!themePicker) {
            console.log("[THEME] ThemePicker missing");
            return false;
        }
        var gx = mainWin.width - themePicker.width - 40;
        var gy = 80;
        themePicker.x = gx;
        themePicker.y = gy;
        themePicker.open();
        return true;
    }
    
    function requestCloseAnimation() {
        if (mainWin.forceClose || mainWin.isClosing) return false;
        mainWin.transitionToClosing();
        return true;
    }
    
    function startCloseMotion(reason) {
        if (!mainWin.isClosing || mainWin.closeMotionStarted) return;
        mainWin.closeMotionStarted = true;
        console.log("[CLOSE] Starting close motion (" + reason + ")");
        Qt.callLater(function() {
            jelly.startClose();
        });
    }
    
    // ============================================================
    // JELLY CONTROLLER (Embedded, No Overlays)
    // ============================================================
    
    JellyController {
        id: jelly
        appRef: mainWin.appRef
        
        onGeometryCalculated: (vx, vy, vw, vh) => {
            console.log("[JELLY] Geometry calculated: " + vw + "x" + vh);
            var selected = mainWin.resolveTargetScreen();
            if (!selected) return;
            if (!mainWin.applyGeometryToTargetScreen()) return;
            
            mainWin.animationPhase = "opening";
            mainWin.updateCanvasGeometry();
            console.log("[INIT] Starting open animation");
            jelly.fireOpen();
        }
        
        onReadyForHandoff: {
            console.log("[JELLY] Ready for handoff - transitioning to settled");
            mainWin.transitionToSettled();
        }
        
        onCloseFinished: {
            console.log("[CLOSE] Jelly close finished.");
            if (mainWin.appRef && !mainWin.appRef.keepTrayAlive) {
                console.log("[CLOSE] keepTrayAlive is false - shutting down");
                mainWin.forceClose = true;
                if (mainWin.appRef.trayController) {
                    mainWin.appRef.trayController.exit_cspm();
                } else {
                    Qt.quit();
                }
            } else {
                console.log("[CLOSE] hiding to tray");
                mainWin.visible = false;
                mainWin.forceClose = false;
                mainWin.isClosing = false;
                mainWin.closeMotionStarted = false;
                mainWin.isSettled = false;
                mainWin.animationPhase = "hidden";
                if (jelly && jelly.resetState) jelly.resetState();
            }
        }
    }
    
    // ============================================================
    // CLEANUP & LIFECYCLE
    // ============================================================
    
    function closeAllTopLevelWindows(reason) {
        var windows = (Qt.application && Qt.application.topLevelWindows) ? Qt.application.topLevelWindows : [];
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];
            if (!w || w === mainWin) continue;
            try {
                var title = w.title ? w.title : "";
                if (w.closeForAppExit) {
                    w.closeForAppExit();
                } else {
                    w.close();
                }
                console.log("[MAIN] Closed window '" + title + "' (" + reason + ")");
            } catch (e) {
                console.log("[MAIN] Failed to close window (" + reason + "):", e);
            }
        }
    }
    
    Component.onCompleted: {
        mainWin.resolveTargetScreen();
        mainWin.logTopLevelWindows("startup");
        jelly.prepareLaunch();
    }
    
    Connections {
        target: Qt.application
        function onAboutToQuit() {
            mainWin.closeAllTopLevelWindows("aboutToQuit");
        }
    }
    
    Connections {
        target: mainWin
        function onScreenChanged() {
            try {
                targetScreen = mainWin.screen;
                console.log("[MAIN] Window moved to screen: " + describeScreen(mainWin.screen));
                if (jelly && mainWin.isSettled) {
                    jelly.screenWidth = mainWin.screen ? mainWin.screen.width : jelly.screenWidth;
                    jelly.screenHeight = mainWin.screen ? mainWin.screen.height : jelly.screenHeight;
                }
            } catch (e) {
                console.log('[MAIN] onScreenChanged error:', e);
            }
        }
    }
    
    onVisibleChanged: {
        if (visible && animationPhase === "hidden" && !isSettled) {
            console.log("[MAIN] Window became visible again, starting open animation");
            mainWin.animationPhase = "opening";
            jelly.fireOpen();
        }
    }
    
    onClosing: (close) => {
        console.log("[MAIN] onClosing - forceClose=" + forceClose + " isClosing=" + isClosing);
        if (forceClose) {
            close.accepted = true;
            return;
        }
        close.accepted = false;
        if (!isClosing) {
            mainWin.transitionToClosing();
        }
    }
    
    // ============================================================
    // THEME PICKER
    // ============================================================
    
    ThemePicker {
        id: themePicker
        t: mainWin.t
        names: appRef ? appRef.themeNames : []
        onPicked: function(name) {
            if (appRef) appRef.setTheme(name);
        }
        z: 999
    }
}
