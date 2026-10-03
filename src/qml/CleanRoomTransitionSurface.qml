import QtQuick
import QtQuick.Window

// A competing fixed-clock compositor. No production preparation/settlement
// progress, no capped position and no readiness-driven easing switch.
Window {
    id: surface
    objectName: "CSPMCleanRoomTransitionSurface"
    title: "CSPM experimental single-clock transition"
    property var mainWindow
    property var sourceGrab
    property var targetGrab
    property rect headerMetrics
    property rect sourceBounds
    property rect targetBounds
    property var nativeGeometry: null
    property int overlayX
    property int overlayY
    property int overlayWidth
    property int overlayHeight
    property real commandMs: 0
    property real motionMs: 0
    property int durationMs: 350
    property real transferStart: 0.55
    property bool closingSurface: false
    property bool motionComplete: false
    property bool targetReady: false
    property bool awaitingTarget: false
    property bool awaitingHandoff: false
    property bool qualificationFailure: false
    property string qualificationReason: ""
    property string stage: "source"
    property var traceEvents: []
    property bool endpointPlanReady: false
    property var plannedTargetCapture: null
    property rect sourceCaptureUv: Qt.rect(0, 0, 1, 1)
    property rect targetCaptureUv: Qt.rect(0, 0, 1, 1)
    signal sourcePresented()
    signal motionStarted()
    signal targetCaptureRequested()
    signal targetPresented()
    signal transitionFinished()

    x: overlayX
    y: overlayY
    width: overlayWidth
    height: overlayHeight
    visible: false
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus

    function elapsed() { return transitionExperiment.monotonicMs() - commandMs }
    function record(event) {
        var row = {event: event, elapsedMs: elapsed(), stage: stage,
            targetReady: targetReady, qualificationFailure: qualificationFailure}
        // This timestamp is a GUI-delivered observation, not physical scanout.
        var rows = traceEvents.slice(); rows.push(row); traceEvents = rows;
    }
    function reject(reason) {
        if (!qualificationFailure) {
            qualificationFailure = true; qualificationReason = reason;
            console.warn("Clean-room objective gate failed: " + reason);
            record("qualification-failure:" + reason);
        }
    }
    function prepareNativeGeometry() {
        if (endpointPlanReady) return true;
        nativeGeometry = windowFrameCapture.geometry(surface);
        if (!nativeGeometry || !nativeGeometry.origin || !nativeGeometry.size
                || nativeGeometry.size.width <= 0 || nativeGeometry.size.height <= 0 || !sourceGrab
                || !sourceGrab.nativeFrame || !sourceGrab.contentUv
                || !sourceGrab.nativeOrigin || !sourceGrab.physicalSize
                || !sourceGrab.logicalSize || !sourceGrab.globalOrigin
                || sourceGrab.logicalSize.width <= 0 || sourceGrab.logicalSize.height <= 0
                || sourceGrab.contentUv.width <= 0 || sourceGrab.contentUv.height <= 0
                || !isFinite(sourceGrab.dpr) || sourceGrab.dpr <= 0) return false;
        // Future cross-monitor native placement cannot be inferred from the
        // source monitor's pixel transform. Reject that premise before motion.
        if (!samePhysicalScreen(mainWindow.screen, surface.screen)) {
            reject("cross-monitor-endpoint-plan-unavailable"); return false;
        }
        var requestedTarget = Qt.rect(targetBounds.x, targetBounds.y,
            targetBounds.width, targetBounds.height);
        var padding = 0;
        if (mainWindow.professionalWindowTransitionKind === "restore") {
            var refW = Math.max(1, mainWindow.usableW);
            var refH = Math.max(1, mainWindow.usableH);
            var maxPadX = Math.max(0, Math.floor((refW - requestedTarget.width) / 2));
            var maxPadY = Math.max(0, Math.floor((refH - requestedTarget.height) / 2));
            if (!isFinite(mainWindow.glowPadding) || mainWindow.glowPadding < 0) {
                reject("target-host-padding-unavailable"); return false;
            }
            padding = Math.max(0, Math.min(Math.round(mainWindow.glowPadding),
                Math.min(maxPadX, maxPadY)));
        }
        var logicalW = Math.max(1, Math.round(requestedTarget.width + 2 * padding));
        var logicalH = Math.max(1, Math.round(requestedTarget.height + 2 * padding));
        var logicalX = Math.round(overlayX + requestedTarget.x - padding);
        var logicalY = Math.round(overlayY + requestedTarget.y - padding);
        var dpr = sourceGrab.dpr;
        plannedTargetCapture = {
            nativeOrigin: Qt.point(sourceGrab.nativeOrigin.x
                + nearestNativePixel(logicalX * dpr)
                - nearestNativePixel(sourceGrab.globalOrigin.x * dpr),
                sourceGrab.nativeOrigin.y + nearestNativePixel(logicalY * dpr)
                - nearestNativePixel(sourceGrab.globalOrigin.y * dpr)),
            physicalSize: Qt.size(nearestNativePixel(logicalW * dpr),
                nearestNativePixel(logicalH * dpr)),
            logicalSize: Qt.size(logicalW, logicalH),
            contentUv: Qt.rect(padding / logicalW, padding / logicalH,
                requestedTarget.width / logicalW, requestedTarget.height / logicalH)
        };
        // These shader inputs affect both vertex geometry and endpoint sampling.
        // Capture readiness must never replace them while the clock is running.
        sourceCaptureUv = sourceGrab.contentUv;
        targetCaptureUv = plannedTargetCapture.contentUv;
        sourceBounds = capturedContentBounds(sourceGrab);
        targetBounds = capturedContentBounds(plannedTargetCapture);
        var sx = nativeGeometry.size.width / width;
        var sy = nativeGeometry.size.height / height;
        var sourceScaleX = sourceGrab.physicalSize.width / sourceGrab.logicalSize.width / sx;
        var sourceScaleY = sourceGrab.physicalSize.height / sourceGrab.logicalSize.height / sy;
        var targetScaleX = plannedTargetCapture.physicalSize.width / logicalW / sx;
        headerMetrics = Qt.rect(headerMetrics.x * sourceScaleY,
            headerMetrics.y * sourceScaleX, headerMetrics.y * targetScaleX, 0);
        endpointPlanReady = true;
        record("endpoints-pinned");
        return true;
    }
    function nearestNativePixel(value) {
        return value < 0 ? -Math.round(-value) : Math.round(value);
    }
    function near(a, b) { return Math.abs(a - b) <= 0.0001; }
    function samePhysicalScreen(left, right) {
        // Window.screen exposes a separate QQuickScreenInfo wrapper for each
        // window, even when both wrappers refer to the same native QScreen.
        // Match the screen descriptor and pixel transform, not wrapper identity.
        if (!left || !right || typeof left.name !== "string"
                || typeof right.name !== "string" || left.name !== right.name)
            return false;
        var keys = ["virtualX", "virtualY", "width", "height", "devicePixelRatio"];
        for (var i = 0; i < keys.length; ++i) {
            var key = keys[i];
            if (!isFinite(left[key]) || !isFinite(right[key])
                    || !near(left[key], right[key])) return false;
        }
        return left.width > 0 && left.height > 0 && left.devicePixelRatio > 0;
    }
    function targetMatchesPlan(result, rightWidth) {
        if (!endpointPlanReady || !result || !result.nativeFrame
                || !result.nativeOrigin || !result.physicalSize
                || !result.logicalSize || !result.contentUv) return false;
        var plan = plannedTargetCapture;
        var uv = result.contentUv;
        var sx = nativeGeometry.size.width / width;
        var actualCap = rightWidth * result.physicalSize.width / result.logicalSize.width / sx;
        return near(result.nativeOrigin.x, plan.nativeOrigin.x)
            && near(result.nativeOrigin.y, plan.nativeOrigin.y)
            && near(result.physicalSize.width, plan.physicalSize.width)
            && near(result.physicalSize.height, plan.physicalSize.height)
            && near(result.logicalSize.width, plan.logicalSize.width)
            && near(result.logicalSize.height, plan.logicalSize.height)
            && near((uv.x - plan.contentUv.x) * result.physicalSize.width, 0)
            && near((uv.y - plan.contentUv.y) * result.physicalSize.height, 0)
            && near((uv.width - plan.contentUv.width) * result.physicalSize.width, 0)
            && near((uv.height - plan.contentUv.height) * result.physicalSize.height, 0)
            && near(actualCap, headerMetrics.width);
    }
    function capturedContentBounds(grab) {
        if (!grab || !nativeGeometry || !nativeGeometry.size) return sourceBounds;
        var sx = nativeGeometry.size.width / width, sy = nativeGeometry.size.height / height;
        var uv = grab.contentUv;
        return Qt.rect((grab.nativeOrigin.x - nativeGeometry.origin.x) / sx + uv.x * grab.physicalSize.width / sx,
            (grab.nativeOrigin.y - nativeGeometry.origin.y) / sy + uv.y * grab.physicalSize.height / sy,
            uv.width * grab.physicalSize.width / sx, uv.height * grab.physicalSize.height / sy);
    }
    function nextFrame() { Qt.callLater(function() { if (!closingSurface) surface.update() }); }
    function expectLiveTarget() {
        awaitingTarget = true;
        Qt.callLater(function() { if (!closingSurface) mainWindow.update() });
    }
    function setTargetGrab(result, rightWidth) {
        if (!targetMatchesPlan(result, rightWidth)) {
            if (result && result.url) windowFrameCapture.release(result.url);
            reject("target-native-endpoint-plan-mismatch");
            Qt.callLater(function() {
                if (!closingSurface) mainWindow.stopMaximizeFxAnimations();
            });
            return;
        }
        targetGrab = result;
        record("target-captured");
        if (transitionExperiment.monotonicMs() - motionMs > durationMs * transferStart)
            reject("target-missed-fixed-transfer-deadline");
        nextFrame();
    }
    function expectLiveHandoff() {
        awaitingHandoff = true; record("live-host-revealed");
        Qt.callLater(function() { if (!closingSurface) mainWindow.update() });
    }
    function tryHandoff() {
        if (!motionComplete || !targetReady || stage === "handoff" || stage === "release") return;
        stage = "handoff"; record("handoff-frame"); targetPresented();
    }
    function closeOverlay(reason) {
        if (closingSurface) return;
        closingSurface = true; clock.stop(); visible = false;
        if (sourceGrab && sourceGrab.nativeFrame) windowFrameCapture.release(sourceGrab.url);
        if (targetGrab && targetGrab.nativeFrame) windowFrameCapture.release(targetGrab.url);
        Qt.callLater(function() { surface.destroy() });
    }
    Image { id: sourceImage; source: sourceGrab ? sourceGrab.url : ""; visible: false; cache: false; smooth: true }
    Image { id: targetImage; source: targetGrab ? targetGrab.url : (sourceGrab ? sourceGrab.url : ""); visible: false; cache: false; smooth: true }
    ShaderEffect {
        id: renderer
        objectName: "CSPMCleanRoomTransitionRenderer"
        anchors.fill: parent
        property var source: sourceImage
        property var targetSource: targetImage
        property real clock: 0
        property real transferStart: surface.transferStart
        property rect sourceRect: surface.sourceBounds
        property rect targetRect: surface.targetBounds
        property rect headerMetrics: surface.headerMetrics
        property rect sourceCaptureUv: surface.sourceCaptureUv
        property rect targetCaptureUv: surface.targetCaptureUv
        vertexShader: "shaders/cleanroom_transition.vert.qsb"
        fragmentShader: "shaders/cleanroom_transition.frag.qsb"
    }
    UniformAnimator {
        id: clock
        target: renderer
        uniform: "clock"
        from: 0
        to: 1
        duration: surface.durationMs
        easing.type: Easing.Linear
        onFinished: {
            surface.motionComplete = true; surface.record("motion-end");
            if (!surface.targetReady) surface.reject("target-not-presented-at-clock-end");
            surface.tryHandoff();
        }
    }
    onFrameSwapped: {
        if (closingSurface) return;
        record("surface-frame");
        if (stage === "source" && sourceImage.status === Image.Ready && renderer.status !== ShaderEffect.Error) {
            stage = "clock-start"; sourcePresented();
            motionMs = transitionExperiment.monotonicMs(); record("clock-start");
            clock.start(); nextFrame();
        } else if (stage === "clock-start") {
            stage = "moving"; record("first-submitted-motion"); motionStarted();
        }
        if (targetGrab && !targetReady && targetImage.status === Image.Ready && renderer.status !== ShaderEffect.Error) {
            targetReady = true; record("target-presented"); tryHandoff();
        }
        if (stage === "release") {
            stage = "finished"; record("surface-retired"); transitionFinished();
        }
    }
    Connections {
        target: surface.mainWindow
        function onFrameSwapped() {
            if (surface.closingSurface) return;
            if (surface.awaitingHandoff) {
                surface.awaitingHandoff = false; surface.record("first-live-frame");
                surface.stage = "release"; surface.nextFrame(); return;
            }
            if (surface.awaitingTarget) {
                surface.awaitingTarget = false; surface.record("target-layout-frame");
                surface.targetCaptureRequested();
            }
        }
    }
}
