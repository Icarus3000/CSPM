import QtQuick
import QtQuick.Window

// Two endpoint images of the same shell; never constructs another workspace.
// Its HWND stays fixed for the complete transaction, including both handoffs.
Window {
    id: surface
    objectName: "CSPMWindowTransitionSurface"
    title: "CSPM window transition"
    property bool earlyMotionEnabled: false
    property var mainWindow
    property var sourceGrab
    property var targetGrab
    property rect headerMetrics
    property rect sourceBounds
    property rect targetBounds
    property var nativeGeometry: null
    readonly property rect sourceCaptureUv: sourceGrab && sourceGrab.contentUv
        ? sourceGrab.contentUv : Qt.rect(0, 0, 1, 1)
    readonly property rect targetCaptureUv: targetGrab && targetGrab.contentUv
        ? targetGrab.contentUv : Qt.rect(0, 0, 1, 1)
    property int overlayX
    property int overlayY
    property int overlayWidth
    property int overlayHeight
    property bool motionComplete: false
    property bool targetReady: false
    property bool awaitingLiveTarget: false
    property bool awaitingLiveHandoff: false
    property int liveTargetFrames: 0
    property bool closingSurface: false
    property string stage: "source"
    property int presentedFrames: 0

    signal sourcePresented()
    signal motionStarted()
    signal targetCaptureRequested()
    signal targetPresented()
    signal transitionFinished()

    x: overlayX
    y: overlayY
    width: overlayWidth
    height: overlayHeight
    color: "transparent"
    visible: false
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput
        | Qt.WindowDoesNotAcceptFocus

    Image {
        id: frozenSource
        source: surface.sourceGrab ? surface.sourceGrab.url : ""
        visible: false
        cache: false
        smooth: true
        mipmap: true
    }
    Image {
        id: frozenTarget
        source: surface.targetGrab ? surface.targetGrab.url
            : (surface.sourceGrab ? surface.sourceGrab.url : "")
        visible: false
        cache: false
        smooth: true
        mipmap: true
    }
    ShaderEffect {
        id: movingSource
        objectName: "CSPMWindowTransitionRenderer"
        anchors.fill: parent
        property var source: frozenSource
        property var targetSource: frozenTarget
        property real progress: 0
        property real preparationProgress: 0
        property real settlementProgress: 0
        property real earlyMotion: surface.earlyMotionEnabled ? 1.0 : 0.0
        property rect sourceRect: surface.sourceGrab && surface.sourceGrab.contentUv
            ? surface.capturedContentBounds(surface.sourceGrab) : surface.sourceBounds
        property rect targetRect: surface.targetGrab && surface.targetGrab.contentUv
            ? surface.capturedContentBounds(surface.targetGrab) : surface.targetBounds
        property rect headerMetrics: surface.headerMetrics
        property rect sourceCaptureUv: surface.sourceCaptureUv
        property rect targetCaptureUv: surface.targetCaptureUv
        vertexShader: "shaders/window_transition.vert.qsb"
        fragmentShader: "shaders/window_transition.frag.qsb"
    }
    UniformAnimator {
        id: motion
        target: movingSource
        uniform: "progress"
        from: 0
        to: 1
        duration: 220
        easing.type: Easing.OutCubic
        onFinished: {
            surface.motionComplete = true
            surface.tryRevealTarget()
        }
    }
    // Begin with exact source pixels. The final-layout capture can be prepared
    // after movement is visible, without changing header pixel dimensions.
    UniformAnimator {
        id: preparationMotion
        target: movingSource
        uniform: "preparationProgress"
        from: 0
        to: 0.85
        duration: 800
        easing.type: Easing.OutCubic
    }
    UniformAnimator {
        id: settlementMotion
        target: movingSource
        uniform: "settlementProgress"
        from: 0
        to: 1
        duration: 220
        easing.type: Easing.InOutCubic
        onFinished: {
            preparationMotion.stop()
            surface.motionComplete = true
            surface.tryRevealTarget()
        }
    }
    function startPreparationMotion() {
        stage = "motion-start"
        presentedFrames = 0
        preparationMotion.start()
        requestNextFrame()
    }
    function startMotion() {
        if (closingSurface) return
        if (earlyMotionEnabled) {
            stage = "moving"
            settlementMotion.start()
            return
        }
        stage = "motion-start"
        presentedFrames = 0
        motion.start()
    }
    function expectLiveTarget() {
        if (closingSurface) return
        stage = "preparing-target"
        awaitingLiveTarget = true
        liveTargetFrames = 0
        Qt.callLater(function() { if (!surface.closingSurface) surface.mainWindow.update() })
    }
    function setTargetGrab(result, rightWidth) {
        if (closingSurface) return
        targetGrab = result
        headerMetrics = Qt.rect(headerMetrics.x, headerMetrics.y, rightWidth, 0)
        stage = "captured-target"
        presentedFrames = 0
        requestNextFrame()
    }
    function prepareNativeGeometry() {
        nativeGeometry = windowFrameCapture.geometry(surface)
        return nativeGeometry && nativeGeometry.size
    }
    function capturedContentBounds(grab) {
        if (!nativeGeometry || !nativeGeometry.size) return Qt.rect(0, 0, 0, 0)
        // Use the actual native client pixels, including placement rounding at
        // monitor boundaries. The host stays fixed for the whole transaction.
        var sx = nativeGeometry.size.width / surface.width
        var sy = nativeGeometry.size.height / surface.height
        var frameX = (grab.nativeOrigin.x - nativeGeometry.origin.x) / sx
        var frameY = (grab.nativeOrigin.y - nativeGeometry.origin.y) / sy
        var frameW = grab.physicalSize.width / sx
        var frameH = grab.physicalSize.height / sy
        var uv = grab.contentUv
        return Qt.rect(frameX + uv.x * frameW, frameY + uv.y * frameH,
            uv.width * frameW, uv.height * frameH)
    }
    function expectLiveHandoff() {
        if (closingSurface) return
        awaitingLiveHandoff = true
        liveTargetFrames = 0
        Qt.callLater(function() { if (!surface.closingSurface) surface.mainWindow.update() })
    }
    function tryRevealTarget() {
        if (!motionComplete || !targetReady || stage === "live-handoff" || closingSurface) return
        // The moving image already contains the final layout at native size.
        stage = "target"
        presentedFrames = 0
        requestNextFrame()
    }
    function requestNextFrame() {
        // A direct update from frameSwapped can be coalesced into the frame
        // that is still ending. Queue the next request after that transaction.
        Qt.callLater(function() { if (!surface.closingSurface) surface.update() })
    }
    function closeOverlay(reason) {
        if (closingSurface) return
        closingSurface = true
        motion.stop()
        preparationMotion.stop()
        settlementMotion.stop()
        visible = false
        if (typeof windowFrameCapture !== "undefined") {
            if (sourceGrab && sourceGrab.nativeFrame) windowFrameCapture.release(sourceGrab.url)
            if (targetGrab && targetGrab.nativeFrame) windowFrameCapture.release(targetGrab.url)
        }
        Qt.callLater(function() { surface.destroy() })
    }

    onFrameSwapped: {
        if (closingSurface) return
        if (stage === "source" && frozenSource.status === Image.Ready
                && movingSource.status !== ShaderEffect.Error) {
            if (++presentedFrames >= 3) {
                stage = "source-presented"
                sourcePresented()
                if (earlyMotionEnabled && !closingSurface) startPreparationMotion()
            } else requestNextFrame()
        } else if (stage === "motion-start") {
            stage = "moving"
            motionStarted()
        } else if (stage === "captured-target" && frozenTarget.status === Image.Ready
                && movingSource.status !== ShaderEffect.Error) {
            if (++presentedFrames >= 2) {
                targetReady = true
                startMotion()
            } else requestNextFrame()
        } else if (stage === "target") {
            if (++presentedFrames >= 2) {
                stage = "live-handoff"
                targetPresented()
            } else requestNextFrame()
        } else if (stage === "release") {
            if (++presentedFrames >= 3) {
                stage = "finished"
                transitionFinished()
            } else requestNextFrame()
        }
    }
    Connections {
        target: surface.mainWindow
        function onFrameSwapped() {
            if (surface.closingSurface) return
            if (surface.awaitingLiveHandoff) {
                if (++surface.liveTargetFrames >= 2) {
                    surface.awaitingLiveHandoff = false
                    surface.stage = "release"
                    surface.presentedFrames = 0
                    surface.requestNextFrame()
                } else Qt.callLater(function() { surface.mainWindow.update() })
                return
            }
            if (!surface.awaitingLiveTarget) return
            if (++surface.liveTargetFrames >= 2) {
                surface.awaitingLiveTarget = false
                surface.targetCaptureRequested()
            } else Qt.callLater(function() { surface.mainWindow.update() })
        }
    }
}
