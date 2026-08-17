import QtQuick
import QtQuick.Window

Item {
    id: root
    property var appRef
    property bool lowPerformanceMode: false
    property string openStyle: "drop"  // "drop" | "blobPop"
    
    // PROPERTIES
    property real scaleX: 1.0
    property real scaleY: 1.0
    property real transX: 0.0
    property real transY: 0.0
    property real rotationVal: 0.0
    property real opacityVal: 1.0 
    
    property real finalRadius: Math.max(4, Math.round(Math.min(screenWidth, screenHeight) * 0.011))
    property real blobRadius: finalRadius * 2.4
    property real borderFlashOpacity: 1.0 
    
    property real screenHeight: (Qt.application && Qt.application.primaryScreen && Qt.application.primaryScreen.height > 0)
        ? Qt.application.primaryScreen.height : Math.max(1, Screen.height)
    property real screenWidth: (Qt.application && Qt.application.primaryScreen && Qt.application.primaryScreen.width > 0)
        ? Qt.application.primaryScreen.width : Math.max(1, Screen.width)
    property var motionRatios: ({
        "openStartOvershootPct": 0.0022,
        "openBlobStartScale": 0.22,
        "openBlobPressScaleX": 0.74,
        "openBlobPressScaleY": 0.58,
        "openBlobBurstScaleX": 1.32,
        "openBlobBurstScaleY": 0.72,
        "openBlobReboundScaleX": 0.90,
        "openBlobReboundScaleY": 1.12,
        "openBlobPressDownPct": 0.020,
        "openBlobPopLiftPct": -0.062,
        "openBlobReboundDownPct": 0.012,
        "openBlobStartRadiusScale": 3.2,
        "openBlobPressRadiusScale": 2.4,
        "openBlobBurstRadiusScale": 1.5,
        "openRecoveryLiftPct": -0.020,
        "openRecoveryDropPct": 0.0090,
        "openRecoveryLift2Pct": -0.0105,
        "openRecoveryDrop2Pct": 0.0042,
        "openRecoveryLift3Pct": -0.0035,
        "closePhase1TransYPct": 0.084,
        "closePhase1TransXPct": -0.024,
        "closePhase2TransYPct": -0.198,
        "closePhase2TransXPct": 0.063,
        "closePhase3TransYPct": 0.078,
        "closePhase3TransXPct": -0.033
    })
    property real openStartTransY: -(screenHeight * (1.0 + motionRatios.openStartOvershootPct))
    property real openImpactTransY: 0.0
    property real openImpactScaleX: 1.38
    property real openImpactScaleY: 0.62
    property int settleFrames: 0 
    property bool reducedMotion: lowPerformanceMode
    function pxX(ratio) { return screenWidth * ratio }
    function pxY(ratio) { return screenHeight * ratio }

    signal geometryCalculated(real x, real y, real w, real h)
    signal requestPreResize()
    signal requestStandardSize()
    signal readyForHandoff()
    signal openFloorImpact(real strengthNorm)
    signal closeFinished()
    signal minimizeFinished()
    signal restoreFinished()
    signal exitFromTrayFinished()
    
    property bool isFrozenAtIdentity: false
    property real closeProgress: 0.0
    property real minimizeProgress: 0.0
    property real exitFromTrayProgress: 0.0
    property real taskbarTargetDistX: 0.0
    property real taskbarTargetDistY: 0.0
    property bool isExplicitAnimating: closeSeq.running || minimizeSeq.running || restoreSeq.running || exitFromTraySeq.running

    property point launchOrigin: Qt.point(0,0)
    property bool isAnimating: openSeq.running || openBlobSeq.running || closeSeq.running || minimizeSeq.running || restoreSeq.running || exitFromTraySeq.running
    property bool isInSpringPhase: false
    property bool closeFinishEmitted: false
    property int openStabilityIntervalMs: 3
    property int openStableFramesForPreResize: 1
    property int openStableFramesForHandoff: 1
    property int openChecksAfterPreResizeForHandoff: 0
    property bool openHandoffEmitted: false
    property int openRecoveryDurationMs: lowPerformanceMode ? 160 : 380

    // ============================================================
    // PHYSICS ENGINE
    // ============================================================
    Behavior on transY {
        id: physicsY
        enabled: !isExplicitAnimating && root.isInSpringPhase && !root.reducedMotion
        SpringAnimation { spring: 0.3; mass: 2.0; damping: 0.073; epsilon: 0.002 }
    }
    
    Behavior on scaleX {
        id: physicsScale
        enabled: !isExplicitAnimating && root.isInSpringPhase && !root.reducedMotion
        SpringAnimation { spring: 0.6; mass: 1.5; damping: 0.073; epsilon: 0.002 }
    }
    
    Behavior on scaleY {
        enabled: !isExplicitAnimating && root.isInSpringPhase && !root.reducedMotion
        SpringAnimation { spring: 0.6; mass: 1.5; damping: 0.073; epsilon: 0.002 }
    }
    
    Behavior on transX {
        enabled: !isExplicitAnimating && !openSeq.running && !openBlobSeq.running && root.isInSpringPhase && !root.reducedMotion
        SpringAnimation { spring: 0.3; mass: 2.0; damping: 0.077; epsilon: 0.001 }
    }
    
    Behavior on rotationVal { 
        enabled: !isExplicitAnimating && !root.reducedMotion
        NumberAnimation { duration: 1500; easing.type: Easing.InOutBack }
    }
    Behavior on opacityVal { 
        enabled: !isExplicitAnimating && !root.reducedMotion
        NumberAnimation { duration: 600 } 
    }
    Behavior on blobRadius { enabled: !root.reducedMotion; NumberAnimation { duration: 1500; easing.type: Easing.OutQuad } }

    // ============================================================
    // LOGIC
    // ============================================================
    function stopOpenAnimations() {
        if (openSeq.running) {
            openSeq.stop()
        }
        if (openBlobSeq.running) {
            openBlobSeq.stop()
        }
    }

    function beginOpenSpringSettle() {
        isInSpringPhase = true
        openHandoffEmitted = false
        fallMonitor.start()
        stabilityCheck.stableCount = 0
        stabilityCheck.checkCount = 0
        stabilityCheck.checkpointOnePassed = false
        stabilityCheck.checkpointOneCheckCount = 0
        stabilityCheck.start()
        root.transX = 0
        root.transY = 0
        root.scaleX = 1.0
        root.scaleY = 1.0
        root.rotationVal = 0.0
        root.blobRadius = root.finalRadius
        root.borderFlashOpacity = 1.0
    }

    function completeBoundedOpenHandoff() {
        isInSpringPhase = false
        fallMonitor.stop()
        stabilityCheck.stop()
        transX = 0
        transY = 0
        scaleX = 1.0
        scaleY = 1.0
        rotationVal = 0.0
        blobRadius = finalRadius
        borderFlashOpacity = 1.0
        if (!openHandoffEmitted) {
            openHandoffEmitted = true
            root.requestPreResize()
            root.requestStandardSize()
            root.readyForHandoff()
        }
    }

    function prepareLaunch() {
        stopOpenAnimations()
        closeSeq.stop()
        openHandoffEmitted = false
        
        // Get the monitor where the cursor is located
        var cursorScreenIndex = 0;
        if (appRef && appRef.getCursorScreenIndex) {
            cursorScreenIndex = appRef.getCursorScreenIndex();
        }
        
        // Ensure valid screen index
        if (cursorScreenIndex < 0 || cursorScreenIndex >= Qt.application.screens.length) {
            cursorScreenIndex = 0;
        }
        
        var targetScreen = Qt.application.screens[cursorScreenIndex];
        console.log("[JELLY] Using cursor screen index", cursorScreenIndex, "at", targetScreen.virtualX + "," + targetScreen.virtualY);

        var winX = Math.round(targetScreen.virtualX)
        var winY = Math.round(targetScreen.virtualY)
        var winW = Math.round(targetScreen.width)
        var winH = Math.round(targetScreen.height)
        if (winW === 0) winW = Screen.desktopAvailableWidth * 0.8
        if (winH === 0) winH = Screen.desktopAvailableHeight * 0.8
        screenHeight = winH
        screenWidth = winW
        
        // Prime the very first painted frame based on opening style.
        // This avoids one-frame full-size flashes before the opening sequence starts.
        if (openStyle === "blobPop") {
            openStartTransY = 0
            openImpactTransY = 0
            transY = 0
            scaleX = motionRatios.openBlobStartScale
            scaleY = motionRatios.openBlobStartScale
            opacityVal = 0.0
            blobRadius = finalRadius * motionRatios.openBlobStartRadiusScale
        } else {
            // Start fully above the monitor so entry is bottom-edge first.
            openStartTransY = -(screenHeight * (1.0 + motionRatios.openStartOvershootPct))
            openImpactTransY = 0
            transY = openStartTransY
            scaleX = 1.0
            scaleY = 1.0
            opacityVal = 1.0
            blobRadius = finalRadius * 2.4
        }
        transX = 0
        rotationVal = 0.0
        borderFlashOpacity = 1.0
        isInSpringPhase = false
        
        settleFrames = 0 
        geometryCalculated(winX, winY, winW, winH)
    }

    function fireOpen() {
        if (root.reducedMotion) {
            console.log("[JELLY] reducedMotion active - skipping openSeq, snapping to settled state");
            // Immediately settle to identity (no spring) so handover can proceed using simple fades
            isInSpringPhase = false;
            transX = 0;
            transY = 0;
            scaleX = 1.0;
            scaleY = 1.0;
            rotationVal = 0.0;
            opacityVal = 1.0;
            blobRadius = finalRadius;
            borderFlashOpacity = 1.0;

            // Emit handoff-related signals so Main.qml continues the handover/fade path
            if (!openHandoffEmitted) {
                openHandoffEmitted = true;
                root.requestPreResize();
                root.requestStandardSize();
                root.readyForHandoff();
            }
            return;
        }
        stopOpenAnimations()
        if (openStyle === "blobPop") {
            openBlobSeq.restart()
            return
        }
        openSeq.restart();
    }
    function finishCloseIfNeeded(reason) {
        if (closeFinishEmitted) {
            return;
        }
        closeFinishEmitted = true;
        closeTimeout.stop();
        if (closeSeq.running) {
            closeSeq.stop();
        }
        // Snap to terminal state for deterministic shutdown handoff.
        transX = 0.0;
        transY = 0.0;
        rotationVal = 720.0;
        scaleX = 0.0;
        scaleY = 0.0;
        opacityVal = 0.0;
        console.log("[JELLY] finishCloseIfNeeded reason=" + reason + ", emitting closeFinished");
        root.closeFinished();
    }

    function startClose() { 
        console.log("[JELLY] startClose() called");
        if (root.reducedMotion) {
            console.log("[JELLY] reducedMotion active - skipping closeSeq");
            transX = 0.0;
            transY = 0.0;
            scaleX = 1.0;
            scaleY = 1.0;
            rotationVal = 0.0;
            opacityVal = 1.0;
            isInSpringPhase = false;
            closeFinishEmitted = false;
            root.finishCloseIfNeeded("reduced-motion");
            return;
        }
        scaleX = 1.0;
        scaleY = 1.0;
        transX = 0.0;
        transY = 0.0;
        rotationVal = 0.0;
        opacityVal = 1.0;
        isFrozenAtIdentity = false;
        closeProgress = 0.0;
        
        isInSpringPhase = false;
        closeFinishEmitted = false;
        closeTimeout.restart();
        
        if (!closeSeq.running) {
            console.log("[JELLY] Starting closeSeq animation");
            closeSeq.restart();
        } else {
            console.log("[JELLY] closeSeq already running");
        }
    }
    function restore() { scaleX = 1.0; scaleY = 1.0; transX = 0; transY = 0; rotationVal = 0.0; opacityVal = 1.0; borderFlashOpacity = 1.0; }
    
    // SEAMLESS HANDOFF: Freeze all transform properties at identity to prevent any visual discontinuity
    function freezeToIdentity() {
        console.log("[JELLY] Freezing to identity state");
        isFrozenAtIdentity = true;
        isInSpringPhase = false;
        
        // Disable all spring physics - prevents any oscillation or drift
        physicsY.enabled = false;
        physicsScale.enabled = false;
        
        // Set all transform properties to EXACT identity values
        transX = 0.0;
        transY = 0.0;
        scaleX = 1.0;
        scaleY = 1.0;
        rotationVal = 0.0;
        
        console.log("[JELLY] Frozen: transX=" + transX + " transY=" + transY + " scaleX=" + scaleX + " scaleY=" + scaleY);
    }

    Timer {
        id: closeTimeout
        interval: 4200
        repeat: false
        running: false
        onTriggered: {
            root.finishCloseIfNeeded("timeout")
        }
    }
    
    Timer {
        id: fallMonitor
        interval: 8
        repeat: true
        running: false
        property int frameCount: 0
        property int nearStableFrames: 0
        onTriggered: {
            var host = root
            if (!host) {
                fallMonitor.stop()
                return
            }
            var currentTransX = (typeof host.transX === "number") ? host.transX : 0.0
            var currentTransY = (typeof host.transY === "number") ? host.transY : 0.0
            var currentScaleX = (typeof host.scaleX === "number") ? host.scaleX : 1.0
            var currentScaleY = (typeof host.scaleY === "number") ? host.scaleY : 1.0
            frameCount++
            // Log every 10 frames
            if (frameCount % 10 === 0) {
                console.log("[FALL MONITOR] Frame " + frameCount + ": transY=" + currentTransY.toFixed(1) + " scale=" + currentScaleX.toFixed(2) + "x" + currentScaleY.toFixed(2));
            }
            // Keep transX locked at 0 to prevent rightward drift
            if (Math.abs(currentTransX) > 0.1) {
                host.transX = 0
                currentTransX = 0
            }

            var nearStable = Math.abs(currentTransY) < 5.0
                && Math.abs(currentScaleX - 1.0) < 0.04
                && Math.abs(currentScaleY - 1.0) < 0.04
            if (nearStable) {
                nearStableFrames += 1
            } else {
                nearStableFrames = 0
            }

            // Deterministic snap to remove visible end-of-open jitter.
            if (nearStableFrames >= 1) {
                console.log("[FALL MONITOR] Snap criteria met: transY=" + currentTransY.toFixed(2)
                    + " scale=" + currentScaleX.toFixed(3) + "x" + currentScaleY.toFixed(3));
                host.transX = 0
                host.transY = 0
                host.scaleX = 1.0
                host.scaleY = 1.0
                host.rotationVal = 0.0
                host.isInSpringPhase = false
                if (stabilityCheck.running) {
                    stabilityCheck.stop()
                }
                stopOpenAnimations()
                frameCount = 0
                nearStableFrames = 0
                fallMonitor.stop()
                console.log("[FALL MONITOR] Near-stable snap -> handoff")
                if (!host.openHandoffEmitted) {
                    host.openHandoffEmitted = true
                    host.requestStandardSize()
                    host.readyForHandoff()
                }
                return
            }

            // Simple: just check if we're done animating
            if (!physicsY.running && !physicsScale.running && Math.abs(currentTransY) < 1.0 && Math.abs(currentScaleX - 1.0) < 0.01 && Math.abs(currentScaleY - 1.0) < 0.01) {
                console.log("[FALL MONITOR] Done - final transY=" + currentTransY.toFixed(2));
                frameCount = 0;
                nearStableFrames = 0;
                fallMonitor.stop()
            }
        }
    }

    Timer {
        id: stabilityCheck; interval: root.openStabilityIntervalMs; repeat: true; running: false
        property int stableCount: 0
        property int checkCount: 0
        property bool checkpointOnePassed: false
        property int checkpointOneCheckCount: 0
        
        onTriggered: {
            var host = root
            if (!host) {
                stabilityCheck.stop()
                return
            }
            var currentTransX = (typeof host.transX === "number") ? host.transX : 0.0
            var currentTransY = (typeof host.transY === "number") ? host.transY : 0.0
            var currentScaleX = (typeof host.scaleX === "number") ? host.scaleX : 1.0
            var currentScaleY = (typeof host.scaleY === "number") ? host.scaleY : 1.0
            checkCount += 1
            var isStableY = !physicsY.running && Math.abs(currentTransY) < 0.3
            var isStableScaleX = !physicsScale.running && Math.abs(currentScaleX - 1.0) < 0.005
            var isStableScaleY = Math.abs(currentScaleY - 1.0) < 0.005
            var isCentered = Math.abs(currentTransX) < 0.1
            
            if (isStableY && isStableScaleX && isStableScaleY && isCentered) {
                stableCount += 1
            } else {
                stableCount = 0
            }
            
            if (stableCount === host.openStableFramesForPreResize && !checkpointOnePassed) { 
                host.requestPreResize() 
                checkpointOnePassed = true;
                checkpointOneCheckCount = checkCount;
            }
            
            if (stableCount >= host.openStableFramesForHandoff
                && checkCount >= (checkpointOneCheckCount + host.openChecksAfterPreResizeForHandoff)) {
                stabilityCheck.stop()
                host.isInSpringPhase = false
                stopOpenAnimations()
                fallMonitor.stop()
                if (!host.openHandoffEmitted) {
                    host.openHandoffEmitted = true
                    host.requestStandardSize()
                    host.readyForHandoff()
                }
            }
        }
    }

    SequentialAnimation {
        id: openBlobSeq
        running: false

        // Detached-window branch: hatch/pop growth from center with jelly wobble.
        ScriptAction {
            script: {
                console.log("[JELLY ANIMATION] === BLOB OPEN: HATCH START ===");
                root.transX = 0
                root.transY = 0
                root.rotationVal = 0.0
                root.scaleX = root.motionRatios.openBlobStartScale
                root.scaleY = root.motionRatios.openBlobStartScale
                root.blobRadius = root.finalRadius * root.motionRatios.openBlobStartRadiusScale
                root.opacityVal = 1.0
                root.borderFlashOpacity = 1.0
                root.isInSpringPhase = false
            }
        }

        ParallelAnimation {
            NumberAnimation {
                target: root; property: "scaleX"
                to: root.motionRatios.openBlobPressScaleX
                duration: 170
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: root; property: "scaleY"
                to: root.motionRatios.openBlobPressScaleY
                duration: 170
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: root; property: "transY"
                to: root.pxY(root.motionRatios.openBlobPressDownPct)
                duration: 170
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: root; property: "blobRadius"
                to: root.finalRadius * root.motionRatios.openBlobPressRadiusScale
                duration: 170
                easing.type: Easing.OutQuad
            }
        }

        ParallelAnimation {
            NumberAnimation {
                target: root; property: "scaleX"
                to: root.motionRatios.openBlobBurstScaleX
                duration: 185
                easing.type: Easing.OutBack
            }
            NumberAnimation {
                target: root; property: "scaleY"
                to: root.motionRatios.openBlobBurstScaleY
                duration: 185
                easing.type: Easing.OutBack
            }
            NumberAnimation {
                target: root; property: "transY"
                to: root.pxY(root.motionRatios.openBlobPopLiftPct)
                duration: 185
                easing.type: Easing.OutBack
            }
            NumberAnimation {
                target: root; property: "blobRadius"
                to: root.finalRadius * root.motionRatios.openBlobBurstRadiusScale
                duration: 185
                easing.type: Easing.OutQuad
            }
        }

        ParallelAnimation {
            NumberAnimation {
                target: root; property: "scaleX"
                to: root.motionRatios.openBlobReboundScaleX
                duration: 215
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: root; property: "scaleY"
                to: root.motionRatios.openBlobReboundScaleY
                duration: 215
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: root; property: "transY"
                to: root.pxY(root.motionRatios.openBlobReboundDownPct)
                duration: 215
                easing.type: Easing.InOutSine
            }
        }

        ScriptAction {
            script: {
                console.log("[JELLY ANIMATION] === BLOB OPEN: SPRING SETTLE ===");
                beginOpenSpringSettle()
            }
        }

        PauseAnimation { duration: 3150 }
    }

    SequentialAnimation {
        id: openSeq
        running: false
        
        // Phase 1: Free fall - vertical motion only, starting from above
        // transX locked at 0 for symmetric deformation
        ScriptAction {
            script: {
                console.log("[JELLY ANIMATION] === PHASE 1: FREE FALL START ===");
                root.transX = 0
            }
        }
        
        NumberAnimation { 
            target: root; property: "transY"; 
            from: root.openStartTransY
            to: root.openImpactTransY  // Land on opening canvas floor (orange frame bottom)
            duration: 810;
            easing.type: Easing.Linear
        }
        
        // Phase 2: Impact deformation - flatten and spread symmetrically
        ScriptAction {
            script: {
                console.log("[JELLY ANIMATION] === PHASE 2: IMPACT DEFORMATION START ===");
                root.openFloorImpact(0.94);
            }
        }
        
        ParallelAnimation {
            NumberAnimation {
                target: root; property: "scaleY"
                from: 1.0
                to: root.openImpactScaleY
                duration: 243
                easing.type: Easing.OutQuad
            }
            
            NumberAnimation {
                target: root; property: "scaleX"
                from: 1.0
                to: root.openImpactScaleX
                duration: 243
                easing.type: Easing.OutQuad
            }
            
            NumberAnimation{
                target: root; property: "blobRadius"
                from: root.finalRadius
                to: root.finalRadius * 2.3
                duration: 243
                easing.type: Easing.OutQuad
            }
        }
        
        // Phase 3: loose bounded recovery. The fall and impact stay untouched;
        // this only adds a damped post-impact wobble before final handoff.
        SequentialAnimation {
            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: Math.min(-1.0, root.pxY(root.motionRatios.openRecoveryLiftPct))
                    duration: root.lowPerformanceMode ? 145 : 360
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 0.920
                    duration: root.lowPerformanceMode ? 145 : 360
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 1.120
                    duration: root.lowPerformanceMode ? 145 : 360
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius * 1.30
                    duration: root.lowPerformanceMode ? 145 : 360
                    easing.type: Easing.OutCubic
                }
            }

            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: Math.max(1.0, root.pxY(root.motionRatios.openRecoveryDropPct))
                    duration: root.lowPerformanceMode ? 125 : 310
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 1.055
                    duration: root.lowPerformanceMode ? 125 : 310
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 0.955
                    duration: root.lowPerformanceMode ? 125 : 310
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius * 1.16
                    duration: root.lowPerformanceMode ? 125 : 310
                    easing.type: Easing.InOutSine
                }
            }

            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: Math.min(-1.0, root.pxY(root.motionRatios.openRecoveryLift2Pct))
                    duration: root.lowPerformanceMode ? 112 : 270
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 0.975
                    duration: root.lowPerformanceMode ? 112 : 270
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 1.045
                    duration: root.lowPerformanceMode ? 112 : 270
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius * 1.10
                    duration: root.lowPerformanceMode ? 112 : 270
                    easing.type: Easing.InOutSine
                }
            }

            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: Math.max(1.0, root.pxY(root.motionRatios.openRecoveryDrop2Pct))
                    duration: root.lowPerformanceMode ? 96 : 230
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 1.018
                    duration: root.lowPerformanceMode ? 96 : 230
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 0.988
                    duration: root.lowPerformanceMode ? 96 : 230
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius * 1.055
                    duration: root.lowPerformanceMode ? 96 : 230
                    easing.type: Easing.InOutSine
                }
            }

            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: Math.min(-1.0, root.pxY(root.motionRatios.openRecoveryLift3Pct))
                    duration: root.lowPerformanceMode ? 82 : 190
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 0.996
                    duration: root.lowPerformanceMode ? 82 : 190
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 1.010
                    duration: root.lowPerformanceMode ? 82 : 190
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius * 1.025
                    duration: root.lowPerformanceMode ? 82 : 190
                    easing.type: Easing.InOutSine
                }
            }

            ParallelAnimation {
                NumberAnimation {
                    target: root; property: "transY"
                    to: 0
                    duration: root.lowPerformanceMode ? 132 : 380
                    easing.type: Easing.OutSine
                }
                NumberAnimation {
                    target: root; property: "scaleX"
                    to: 1.0
                    duration: root.lowPerformanceMode ? 132 : 380
                    easing.type: Easing.OutSine
                }
                NumberAnimation {
                    target: root; property: "scaleY"
                    to: 1.0
                    duration: root.lowPerformanceMode ? 132 : 380
                    easing.type: Easing.OutSine
                }
                NumberAnimation {
                    target: root; property: "blobRadius"
                    to: root.finalRadius
                    duration: root.lowPerformanceMode ? 132 : 380
                    easing.type: Easing.OutSine
                }
            }

            PauseAnimation { duration: root.lowPerformanceMode ? 35 : 95 }
        }

        ScriptAction {
            script: {
                console.log("[JELLY ANIMATION] === PHASE 3: BOUNDED RECOVERY HANDOFF ===");
                completeBoundedOpenHandoff()
            }
        }
    }

    // ============================================================
    // CLOSING ANIMATION: visible-window shrink -> burst -> hold -> implosion
    // ============================================================
    SequentialAnimation {
        id: closeSeq
        running: false

        NumberAnimation {
            target: root
            property: "closeProgress"
            from: 0.0
            to: 1.0
            duration: 1120
            easing.type: Easing.Linear
        }

        onFinished: {
            root.finishCloseIfNeeded("singularity-finished")
        }
    }

    onCloseProgressChanged: {
        var p = closeProgress;

        // 1. Pure Inward Suction - ZERO SPIN
        rotationVal = 0.0;
        transX = 0.0;
        transY = 0.0;

        // 2. Visible window shrink (0.0 to 0.44). This deliberately owns
        // almost half the motion so the shell is unmistakably seen collapsing
        // into its centre before any burst appears.
        if (p < 0.44) {
            var suckP = p / 0.44;
            if (suckP < 0.08) {
                var breath = Math.sin((suckP / 0.08) * Math.PI) * 0.02;
                scaleX = 1.0 - breath;
                scaleY = 1.0 - breath;
            } else {
                var collapseP = (suckP - 0.08) / 0.92;
                var shrink = Math.pow(1.0 - collapseP, 2.4);
                scaleX = Math.max(0.001, shrink);
                scaleY = Math.max(0.001, shrink);
            }
            opacityVal = 1.0;
        } else {
            // Window UI collapsed into its singular center point while the
            // supernova burst, hold, and implosion acts play.
            scaleX = 0.001;
            scaleY = 0.001;
            opacityVal = 0.0;
        }
    }

    // ============================================================
    // MINIMIZE & RESTORE: Gravitational Siphon Engine
    // ============================================================
    function startMinimize(targetDistX, targetDistY) {
        console.log("[JELLY] startMinimize targetDistX=" + targetDistX + " targetDistY=" + targetDistY);
        taskbarTargetDistX = targetDistX;
        taskbarTargetDistY = targetDistY;
        if (root.reducedMotion) {
            transX = 0.0;
            transY = 0.0;
            scaleX = 1.0;
            scaleY = 1.0;
            rotationVal = 0.0;
            opacityVal = 1.0;
            minimizeProgress = 1.0;
            root.minimizeFinished();
            return;
        }
        scaleX = 1.0;
        scaleY = 1.0;
        transX = 0.0;
        transY = 0.0;
        rotationVal = 0.0;
        opacityVal = 1.0;
        minimizeProgress = 0.0;
        isInSpringPhase = false;

        if (restoreSeq.running) restoreSeq.stop();
        minimizeSeq.restart();
    }

    function startRestore(targetDistX, targetDistY) {
        console.log("[JELLY] startRestore targetDistX=" + targetDistX + " targetDistY=" + targetDistY);
        taskbarTargetDistX = targetDistX;
        taskbarTargetDistY = targetDistY;
        if (root.reducedMotion) {
            transX = 0.0;
            transY = 0.0;
            scaleX = 1.0;
            scaleY = 1.0;
            rotationVal = 0.0;
            opacityVal = 1.0;
            minimizeProgress = 0.0;
            root.restoreFinished();
            return;
        }
        minimizeProgress = 0.0;
        opacityVal = 0.0;
        transX = 0.0;
        transY = 0.0;
        scaleX = 0.001;
        scaleY = 0.001;
        rotationVal = 0.0;
        isInSpringPhase = false;

        if (minimizeSeq.running) minimizeSeq.stop();
        restoreSeq.restart();
    }

    SequentialAnimation {
        id: minimizeSeq
        running: false

        NumberAnimation {
            target: root
            property: "minimizeProgress"
            from: 0.0
            to: 1.0
            duration: 860
            easing.type: Easing.Linear
        }

        onFinished: {
            opacityVal = 0.0;
            minimizeProgress = 1.0;
            root.minimizeFinished();
        }
    }

    SequentialAnimation {
        id: restoreSeq
        running: false

        NumberAnimation {
            target: root
            property: "minimizeProgress"
            from: 0.0
            to: 1.0
            duration: 860
            easing.type: Easing.Linear
        }

        onFinished: {
            // Snap cleanly to identity
            transX = 0.0;
            transY = 0.0;
            scaleX = 1.0;
            scaleY = 1.0;
            rotationVal = 0.0;
            opacityVal = 1.0;
            root.restoreFinished();
        }
    }

    function startExitFromTray(targetDistX, targetDistY) {
        console.log("[JELLY] startExitFromTray targetDistX=" + targetDistX + " targetDistY=" + targetDistY);
        taskbarTargetDistX = targetDistX;
        taskbarTargetDistY = targetDistY;
        if (root.reducedMotion) {
            transX = 0.0;
            transY = 0.0;
            scaleX = 0.001;
            scaleY = 0.001;
            rotationVal = 0.0;
            opacityVal = 0.0;
            exitFromTrayProgress = 1.0;
            root.exitFromTrayFinished();
            return;
        }
        exitFromTrayProgress = 0.0;
        opacityVal = 0.0;
        transX = 0.0;
        transY = 0.0;
        scaleX = 0.001;
        scaleY = 0.001;
        rotationVal = 0.0;
        isInSpringPhase = false;

        if (minimizeSeq.running) minimizeSeq.stop();
        if (restoreSeq.running) restoreSeq.stop();
        if (closeSeq.running) closeSeq.stop();
        exitFromTraySeq.restart();
    }

    SequentialAnimation {
        id: exitFromTraySeq
        running: false

        NumberAnimation {
            target: root
            property: "exitFromTrayProgress"
            from: 0.0
            to: 1.0
            duration: 1100
            easing.type: Easing.Linear
        }

        onFinished: {
            opacityVal = 0.0;
            scaleX = 0.001;
            scaleY = 0.001;
            root.exitFromTrayFinished();
        }
    }

    onExitFromTrayProgressChanged: {
        scaleX = 0.001;
        scaleY = 0.001;
        opacityVal = 0.0;
        rotationVal = 0.0;
        transX = 0.0;
        transY = 0.0;
    }

    onMinimizeProgressChanged: {
        var rawP = minimizeProgress;
        if (!minimizeSeq.running && !restoreSeq.running && rawP === 0.0) return;

        // Clamp p to [0.0, 1.0]
        var p = Math.max(0.0, Math.min(1.0, rawP));

        rotationVal = 0.0;
        transX = 0.0;
        transY = 0.0;

        if (restoreSeq.running) {
            // 5-Stage Reverse Restore:
            // Stages 1-4 (0.0 to 0.74): Comet climbs -> pauses in middle -> disappears into itself -> pauses at pinpoint
            // Stage 5 (0.74 to 1.00): Bursts forth from center into final settled position
            if (p < 0.74) {
                scaleX = 0.001;
                scaleY = 0.001;
                opacityVal = 0.0;
            } else {
                var expandP = (p - 0.74) / 0.26; // 0.0 to 1.0
                var bloom = Math.sin(expandP * Math.PI * 0.5);
                scaleX = Math.max(0.001, Math.min(1.0, bloom));
                scaleY = Math.max(0.001, Math.min(1.0, bloom));
                opacityVal = Math.min(1.0, expandP * 2.5);
            }
        } else {
            // Minimize handling:
            // Stage 1 (0.0 to 0.30): Window UI sucked directly into center pinpoint (zero spin, zero transX/transY)
            if (p < 0.30) {
                var suckP = p / 0.30;
                if (suckP < 0.08) {
                    var breath = Math.sin((suckP / 0.08) * Math.PI) * 0.02;
                    scaleX = 1.0 - breath;
                    scaleY = 1.0 - breath;
                } else {
                    var collapseP = (suckP - 0.08) / 0.92;
                    var shrink = Math.pow(1.0 - collapseP, 2.4);
                    scaleX = Math.max(0.001, shrink);
                    scaleY = Math.max(0.001, shrink);
                }
                opacityVal = 1.0;
            } else {
                // UI collapsed into singular center point while canvas executes burst -> hang -> comet -> taskbar
                scaleX = 0.001;
                scaleY = 0.001;
                opacityVal = 0.0;
            }
        }
    }

    Component.onDestruction: {
        closeTimeout.stop()
        fallMonitor.stop()
        stabilityCheck.stop()
        stopOpenAnimations()
        if (closeSeq.running) {
            closeSeq.stop()
        }
        if (minimizeSeq.running) {
            minimizeSeq.stop()
        }
        if (restoreSeq.running) {
            restoreSeq.stop()
        }
        if (exitFromTraySeq.running) {
            exitFromTraySeq.stop()
        }
    }
}
