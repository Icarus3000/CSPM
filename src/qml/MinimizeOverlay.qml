import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window

ApplicationWindow {
    id: minimizeOverlayWin
    title: "CSPM-MinimizeOverlay"
    objectName: "CSPMMinimizeOverlay"

    property var mainWindow: null
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
    property bool restoreReplay: false
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
    signal minimizeFinished()
    signal restoreFinished()

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
        phaseLog("MINIMIZE", "Overlay handoffReady reason=" + reason);
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

    function startMinimize() {
        if (isDestroying) return;
        monitorFrame = 0;
        phaseLog("MINIMIZE", "Overlay start minimize: content="
            + Math.round(contentX) + "," + Math.round(contentY) + " "
            + Math.max(1, Math.round(contentWidth)) + "x" + Math.max(1, Math.round(contentHeight))
            + " target=" + Math.round(targetX) + "," + Math.round(targetY));
        resetIdentityState();
        if (!minimizeSeq.running) {
            minimizeSeq.restart();
        }
    }

    function resetIdentityState() {
        animCenterX = contentX + (contentWidth / 2.0)
        animCenterY = contentY + (contentHeight / 2.0)
        animScaleX = 1.0
        animScaleY = 1.0
        animRotate = 0.0
        animOpacity = 1.0
    }

    function resetMinimizedState() {
        animCenterX = targetX
        animCenterY = targetY
        animScaleX = minScaleX
        animScaleY = minScaleY
        animRotate = 0.0
        animOpacity = 0.0
    }

    function startRestore() {
        if (isDestroying) return;
        monitorFrame = 0;
        phaseLog("RESTORE", "Overlay start restore: target="
            + Math.round(targetX) + "," + Math.round(targetY)
            + " content=" + Math.round(contentX) + "," + Math.round(contentY) + " "
            + Math.max(1, Math.round(contentWidth)) + "x" + Math.max(1, Math.round(contentHeight)));
        if (minimizeSeq.running) {
            minimizeSeq.stop();
        }
        resetMinimizedState();
        if (!restoreSeq.running) {
            restoreSeq.restart();
        }
    }

    function closeOverlay(reason) {
        if (isDestroying) return;
        isDestroying = true;
        phaseLog("MINIMIZE", "Overlay close reason=" + reason);
        minimizeOverlayWin.visible = false;
        minimizeOverlayWin.close();
        Qt.callLater(function() {
            minimizeOverlayWin.destroy();
        });
    }

    function closeForAppExit() {
        closeOverlay("closeForAppExit");
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            minimizeOverlayWin.closeOverlay("aboutToQuit");
        }
    }

    Connections {
        target: minimizeOverlayWin.mainWindow
        function onForceCloseChanged() {
            if (minimizeOverlayWin.mainWindow && minimizeOverlayWin.mainWindow.forceClose) {
                minimizeOverlayWin.closeOverlay("main-force-close");
            }
        }
        function onIsClosingChanged() {
            if (minimizeOverlayWin.mainWindow && minimizeOverlayWin.mainWindow.isClosing) {
                minimizeOverlayWin.closeOverlay("main-closing");
            }
        }
    }

    Item {
        id: sprite
        x: minimizeOverlayWin.animCenterX - (width / 2.0)
        y: minimizeOverlayWin.animCenterY - (height / 2.0)
        width: Math.max(1, minimizeOverlayWin.contentWidth)
        height: Math.max(1, minimizeOverlayWin.contentHeight)
        opacity: minimizeOverlayWin.animOpacity

        transform: [
            Scale {
                origin.x: sprite.width / 2.0
                origin.y: sprite.height / 2.0
                xScale: minimizeOverlayWin.animScaleX
                yScale: minimizeOverlayWin.animScaleY
            },
            Rotation {
                origin.x: sprite.width / 2.0
                origin.y: sprite.height / 2.0
                angle: minimizeOverlayWin.animRotate
            }
        ]

        Image {
            anchors.fill: parent
            source: minimizeOverlayWin.snapshotUrl
            fillMode: Image.Stretch
            asynchronous: false
            smooth: true
            cache: false
        }
    }

    Component.onCompleted: {
        if (restoreReplay) {
            resetMinimizedState();
        } else {
            resetIdentityState();
        }
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
                var img = sprite.children.length > 0 ? sprite.children[0] : null;
                if (img && img.status !== undefined && img.status !== Image.Ready) {
                    handoffDelay.restart();
                    return;
                }
            }
            minimizeOverlayWin.markHandoffReady("delay");
        }
    }

    Timer {
        id: minimizeMonitorTick
        interval: 16
        repeat: true
        running: minimizeSeq.running || restoreSeq.running
        onTriggered: {
            monitorFrame = monitorFrame + 1
            if (minimizeSeq.running) {
                phaseMonitorLog("MINIMIZE", monitorFrame,
                    "center=" + animCenterX.toFixed(1) + "," + animCenterY.toFixed(1)
                    + " scale=" + animScaleX.toFixed(3) + "x" + animScaleY.toFixed(3)
                    + " rot=" + animRotate.toFixed(2)
                    + " opacity=" + animOpacity.toFixed(3))
            } else if (restoreSeq.running) {
                phaseMonitorLog("RESTORE", monitorFrame,
                    "center=" + animCenterX.toFixed(1) + "," + animCenterY.toFixed(1)
                    + " scale=" + animScaleX.toFixed(3) + "x" + animScaleY.toFixed(3)
                    + " rot=" + animRotate.toFixed(2)
                    + " opacity=" + animOpacity.toFixed(3))
            }
        }
    }

    SequentialAnimation {
        id: minimizeSeq
        running: false

        ScriptAction { script: minimizeOverlayWin.phaseLog("MINIMIZE ANIMATION", "=== PHASE 1: PRE-SQUASH ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 1.16; duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 0.84; duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: minimizeOverlayWin.animCenterY + Math.max(4, contentHeight * 0.06); duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 6.0; duration: 160; easing.type: Easing.OutQuad }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("MINIMIZE ANIMATION", "=== PHASE 2: COUNTER-SQUASH ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 0.86; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 1.14; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) - Math.max(3, contentHeight * 0.05); duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: -5.0; duration: 170; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("MINIMIZE ANIMATION", "=== PHASE 3: COMPACTING ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 0.10; duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 0.10; duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) + Math.max(3, contentHeight * 0.03); duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 2.0; duration: 190; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("MINIMIZE ANIMATION", "=== PHASE 4: TASKBAR TRANSIT ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterX"; to: targetX; duration: 380; easing.type: Easing.InBack }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: targetY; duration: 380; easing.type: Easing.InCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: minScaleX; duration: 380; easing.type: Easing.InCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: minScaleY; duration: 380; easing.type: Easing.InCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animOpacity"; to: 0.0; duration: 380; easing.type: Easing.InQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 0.0; duration: 380; easing.type: Easing.InOutSine }
        }

        onFinished: {
            minimizeOverlayWin.phaseLog("MINIMIZE", "Overlay minimize sequence finished");
            minimizeOverlayWin.minimizeFinished();
            minimizeOverlayWin.closeOverlay("finished");
        }
    }

    SequentialAnimation {
        id: restoreSeq
        running: false

        ScriptAction { script: minimizeOverlayWin.phaseLog("RESTORE ANIMATION", "=== PHASE 1: EMERGE FROM TASKBAR ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterX"; to: contentX + (contentWidth / 2.0); duration: 380; easing.type: Easing.OutBack }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) + Math.max(3, contentHeight * 0.03); duration: 380; easing.type: Easing.OutCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 0.10; duration: 380; easing.type: Easing.OutCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 0.10; duration: 380; easing.type: Easing.OutCubic }
            NumberAnimation { target: minimizeOverlayWin; property: "animOpacity"; to: 1.0; duration: 380; easing.type: Easing.OutQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 2.0; duration: 380; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("RESTORE ANIMATION", "=== PHASE 2: COUNTER-SQUASH ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 0.86; duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 1.14; duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) - Math.max(3, contentHeight * 0.05); duration: 190; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: -5.0; duration: 190; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("RESTORE ANIMATION", "=== PHASE 3: PRE-SETTLE ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 1.16; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 0.84; duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: (contentY + (contentHeight / 2.0)) + Math.max(4, contentHeight * 0.06); duration: 170; easing.type: Easing.InOutSine }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 6.0; duration: 170; easing.type: Easing.InOutSine }
        }

        ScriptAction { script: minimizeOverlayWin.phaseLog("RESTORE ANIMATION", "=== PHASE 4: SETTLE ===") }
        ParallelAnimation {
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleX"; to: 1.0; duration: 160; easing.type: Easing.InQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animScaleY"; to: 1.0; duration: 160; easing.type: Easing.InQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animCenterY"; to: contentY + (contentHeight / 2.0); duration: 160; easing.type: Easing.InQuad }
            NumberAnimation { target: minimizeOverlayWin; property: "animRotate"; to: 0.0; duration: 160; easing.type: Easing.InQuad }
        }

        onFinished: {
            minimizeOverlayWin.phaseLog("RESTORE", "Overlay restore sequence finished");
            minimizeOverlayWin.restoreFinished();
            minimizeOverlayWin.closeOverlay("restore-finished");
        }
    }

    onClosing: (close) => {
        close.accepted = true;
    }
}
