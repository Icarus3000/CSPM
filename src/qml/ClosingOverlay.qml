import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "components"
import "views"
import "standards"

ApplicationWindow {
    id: closingOverlayWin
    title: "CSPM-ClosingOverlay"
    objectName: "CSPMClosingOverlay"

    // Main creates this overlay with an explicit screen when available to stabilize mixed-DPI mapping.
    property var mainWindow: null
    property var jellyController: null

    property int overlayX: 0
    property int overlayY: 0
    property int overlayWidth: 1
    property int overlayHeight: 1
    property int contentX: 0
    property int contentY: 0
    property int contentWidth: 1
    property int contentHeight: 1
    property real targetX: 0
    property real targetY: 0
    property string snapshotUrl: ""

    property bool isDestroying: false
    property bool handoffReadySignaled: false
    property bool phaseLoggingEnabled: (mainWindow && mainWindow.phaseLoggingEnabled !== undefined)
        ? !!mainWindow.phaseLoggingEnabled : true
    property int monitorFrame: 0

    property real animCenterX: contentX + (contentWidth / 2.0)
    property real animCenterY: contentY + (contentHeight / 2.0)
    property real animScaleX: 1.0
    property real animScaleY: 1.0
    property real animRotate: 0.0
    property real animOpacity: 1.0
    readonly property real minScaleX: 1.0 / Math.max(1, contentWidth)
    readonly property real minScaleY: 1.0 / Math.max(1, contentHeight)

    signal handoffReady()
    signal closeFinished()

    x: overlayX
    y: overlayY
    width: Math.max(1, overlayWidth)
    height: Math.max(1, overlayHeight)
    visible: false
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowTransparentForInput
    opacity: 1.0

    function markHandoffReady(reason) {
        if (handoffReadySignaled || isDestroying) return;
        handoffReadySignaled = true;
        phaseLog("CLOSING", "Overlay handoffReady reason=" + reason);
        handoffReady();
    }

    function phaseLog(tag, message) {
        if (!phaseLoggingEnabled) return;
        console.log("[" + tag + "] " + message);
    }

    function phaseMonitorLog(tag, frameIndex, message) {
        if (!phaseLoggingEnabled) return;
        if (!isFinite(frameIndex) || frameIndex <= 0) return;
        if ((frameIndex % 10) !== 0) return;
        console.log("[" + tag + " MONITOR] Frame " + frameIndex + ": " + message);
    }

    function resetIdentityState() {
        animCenterX = contentX + (contentWidth / 2.0)
        animCenterY = contentY + (contentHeight / 2.0)
        animScaleX = 1.0
        animScaleY = 1.0
        animRotate = 0.0
        animOpacity = 1.0
    }

    function startClose() {
        if (isDestroying) return;
        monitorFrame = 0;
        phaseLog("CLOSING", "Overlay start close: content="
            + Math.round(contentX) + "," + Math.round(contentY) + " "
            + Math.max(1, Math.round(contentWidth)) + "x" + Math.max(1, Math.round(contentHeight))
            + " target=" + Math.round(targetX) + "," + Math.round(targetY));
        resetIdentityState();
        if (!closeSeq.running) {
            closeSeq.restart();
        }
    }

    function closeOverlay(reason) {
        if (isDestroying) return;
        isDestroying = true;
        phaseLog("CLOSING", "Overlay close reason=" + reason);
        closingOverlayWin.visible = false;
        closingOverlayWin.close();
        Qt.callLater(function() {
            closingOverlayWin.destroy();
        });
    }

    function closeForAppExit() {
        closeOverlay("closeForAppExit");
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            closingOverlayWin.closeOverlay("aboutToQuit");
        }
    }

    Connections {
        target: mainWindow
        function onForceCloseChanged() {
            if (mainWindow && mainWindow.forceClose) {
                closingOverlayWin.closeOverlay("main-force-close");
            }
        }
    }

    Item {
        id: sprite
        x: closingOverlayWin.animCenterX - (width / 2.0)
        y: closingOverlayWin.animCenterY - (height / 2.0)
        width: Math.max(1, closingOverlayWin.contentWidth)
        height: Math.max(1, closingOverlayWin.contentHeight)
        opacity: closingOverlayWin.animOpacity

        transform: [
            Scale {
                origin.x: sprite.width / 2.0
                origin.y: sprite.height / 2.0
                xScale: closingOverlayWin.animScaleX
                yScale: closingOverlayWin.animScaleY
            },
            Rotation {
                origin.x: sprite.width / 2.0
                origin.y: sprite.height / 2.0
                angle: closingOverlayWin.animRotate
            }
        ]

        Loader {
            id: contentLoader
            anchors.fill: parent
            sourceComponent: (snapshotUrl && snapshotUrl.length > 0) ? snapshotContent : liveContent
        }
    }

    Component {
        id: snapshotContent
        Image {
            anchors.fill: parent
            fillMode: Image.Stretch
            source: closingOverlayWin.snapshotUrl
            asynchronous: false
            smooth: true
            cache: false
        }
    }

    Component {
        id: liveContent
        ChromeSurface {
            anchors.fill: parent
            farGlowEnabled: !(mainWindow && mainWindow.lowPerformanceMode)
            glowRadiusNear: (mainWindow && mainWindow.lowPerformanceMode) ? 10 : 18
            glowRadiusFar: (mainWindow && mainWindow.lowPerformanceMode) ? 20 : 36
            plasmaOpacity: (mainWindow && mainWindow.lowPerformanceMode)
                ? (closingOverlayWin.animOpacity * 0.72)
                : closingOverlayWin.animOpacity
            lowFxMode: !!(mainWindow && mainWindow.lowPerformanceMode)
            interactionBoost: 0.16
            flairEnabled: false
            t: (mainWindow && mainWindow.t) ? mainWindow.t : ({
                "bg": "#000000", "accent": "#2979FF", "text": "#FFFFFF", "glow": "#FF1744"
            })
            cornerRadius: (mainWindow && mainWindow.visibility === Window.Maximized)
                ? 0
                : ((mainWindow && mainWindow.chromeCornerRadiusPx) ? mainWindow.chromeCornerRadiusPx() : 16)

            MainContent {
                anchors.fill: parent
                t: (mainWindow && mainWindow.t) ? mainWindow.t : ({})
                metrics: (mainWindow && mainWindow.uiMetrics) ? mainWindow.uiMetrics : ({})
                appRef: (mainWindow && mainWindow.appRef) ? mainWindow.appRef : null
                isInteractive: false
                windowRef: mainWindow
            }
        }
    }

    Component.onCompleted: {
        resetIdentityState();
        handoffDelay.start();
    }

    onVisibleChanged: {
        if (visible && !handoffReadySignaled) {
            handoffDelay.restart();
        }
    }

    Timer {
        id: handoffDelay
        interval: 24
        running: false
        repeat: false
        onTriggered: {
            if (snapshotUrl && snapshotUrl.length > 0) {
                if (contentLoader.status !== Loader.Ready) {
                    handoffDelay.restart();
                    return;
                }
                var loaded = contentLoader.item;
                if (loaded && loaded.status !== undefined && loaded.status !== Image.Ready) {
                    handoffDelay.restart();
                    return;
                }
            }
            closingOverlayWin.markHandoffReady("delay");
        }
    }

    Timer {
        id: closeMonitorTick
        interval: 16
        repeat: true
        running: closeSeq.running
        onTriggered: {
            monitorFrame = monitorFrame + 1
            phaseMonitorLog("CLOSING", monitorFrame,
                "center=" + animCenterX.toFixed(1) + "," + animCenterY.toFixed(1)
                + " scale=" + animScaleX.toFixed(3) + "x" + animScaleY.toFixed(3)
                + " rot=" + animRotate.toFixed(2)
                + " opacity=" + animOpacity.toFixed(3))
        }
    }

    SequentialAnimation {
        id: closeSeq
        running: false

        ScriptAction { script: closingOverlayWin.phaseLog("CLOSING ANIMATION", "=== PHASE 1: PRE-SQUASH ===") }
        ParallelAnimation {
            NumberAnimation { target: closingOverlayWin; property: "animScaleX"; to: 1.14; duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { target: closingOverlayWin; property: "animScaleY"; to: 0.86; duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { target: closingOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) + Math.max(4, contentHeight * 0.05); duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { target: closingOverlayWin; property: "animRotate"; to: 5.0; duration: 150; easing.type: Easing.OutQuad }
        }

        ScriptAction { script: closingOverlayWin.phaseLog("CLOSING ANIMATION", "=== PHASE 2: COUNTER-SQUASH ===") }
        ParallelAnimation {
            NumberAnimation { target: closingOverlayWin; property: "animScaleX"; to: 0.88; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animScaleY"; to: 1.12; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) - Math.max(3, contentHeight * 0.04); duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animRotate"; to: -4.0; duration: 170; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: closingOverlayWin.phaseLog("CLOSING ANIMATION", "=== PHASE 3: COMPACTING ===") }
        ParallelAnimation {
            NumberAnimation { target: closingOverlayWin; property: "animScaleX"; to: 0.10; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animScaleY"; to: 0.10; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) + Math.max(3, contentHeight * 0.03); duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: closingOverlayWin; property: "animRotate"; to: 2.0; duration: 170; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: closingOverlayWin.phaseLog("CLOSING ANIMATION", "=== PHASE 4: TOP-EDGE TRANSIT ===") }
        ParallelAnimation {
            NumberAnimation { target: closingOverlayWin; property: "animCenterX"; to: targetX; duration: 420; easing.type: Easing.InBack }
            NumberAnimation { target: closingOverlayWin; property: "animCenterY"; to: targetY; duration: 420; easing.type: Easing.InCubic }
            NumberAnimation { target: closingOverlayWin; property: "animScaleX"; to: minScaleX; duration: 420; easing.type: Easing.InCubic }
            NumberAnimation { target: closingOverlayWin; property: "animScaleY"; to: minScaleY; duration: 420; easing.type: Easing.InCubic }
            NumberAnimation { target: closingOverlayWin; property: "animOpacity"; to: 0.0; duration: 420; easing.type: Easing.InQuad }
            NumberAnimation { target: closingOverlayWin; property: "animRotate"; to: 0.0; duration: 420; easing.type: Easing.InOutSine }
        }

        onFinished: {
            closingOverlayWin.phaseLog("CLOSING", "Overlay close sequence finished");
            closingOverlayWin.closeFinished();
            closingOverlayWin.closeOverlay("close-seq-finished");
        }
    }

    onClosing: (close) => {
        if (!isDestroying) closingOverlayWin.closeOverlay("onClosing");
        close.accepted = true;
    }
}
