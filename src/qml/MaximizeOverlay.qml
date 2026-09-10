import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "components"
import "views"

ApplicationWindow {
    id: maximizeOverlayWin
    title: "CSPM-MaximizeOverlay"
    objectName: "CSPMMaximizeOverlay"

    property var mainWindow: null
    property int overlayX: 0
    property int overlayY: 0
    property int overlayWidth: 1
    property int overlayHeight: 1
    property real sourceX: 0
    property real sourceY: 0
    property real sourceWidth: 1
    property real sourceHeight: 1
    property real targetX: 0
    property real targetY: 0
    property real targetWidth: 1
    property real targetHeight: 1
    property string transitionKind: "maximize"
    property string snapshotUrl: ""
    property real transitionProgress: 0.0
    property bool isDestroying: false
    property bool handoffReadySignaled: false

    readonly property real easedProgress: {
        var p = Math.max(0.0, Math.min(1.0, transitionProgress))
        // Smoothstep has zero velocity at both handoff boundaries, so the
        // frozen surface meets the stationary live shell without a kick.
        return p * p * (3.0 - (2.0 * p))
    }
    readonly property real renderX: sourceX + ((targetX - sourceX) * easedProgress)
    readonly property real renderY: sourceY + ((targetY - sourceY) * easedProgress)
    readonly property real renderWidth: sourceWidth
        + ((targetWidth - sourceWidth) * easedProgress)
    readonly property real renderHeight: sourceHeight
        + ((targetHeight - sourceHeight) * easedProgress)

    signal handoffReady()
    signal transitionFinished()

    x: overlayX
    y: overlayY
    width: Math.max(1, overlayWidth)
    height: Math.max(1, overlayHeight)
    visible: false
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
    opacity: 1.0

    function markHandoffReady() {
        if (handoffReadySignaled || isDestroying) return
        handoffReadySignaled = true
        handoffReady()
    }

    function startTransition() {
        if (isDestroying || transitionAnimation.running) return
        transitionProgress = 0.0
        transitionAnimation.restart()
    }

    function closeOverlay(reason) {
        if (isDestroying) return
        isDestroying = true
        visible = false
        close()
        Qt.callLater(function() {
            maximizeOverlayWin.destroy()
        })
    }

    function closeForAppExit() {
        closeOverlay("closeForAppExit")
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            maximizeOverlayWin.closeOverlay("aboutToQuit")
        }
    }

    Connections {
        target: maximizeOverlayWin.mainWindow
        function onForceCloseChanged() {
            if (maximizeOverlayWin.mainWindow
                    && maximizeOverlayWin.mainWindow.forceClose) {
                maximizeOverlayWin.closeOverlay("main-force-close")
            }
        }
        function onIsClosingChanged() {
            if (maximizeOverlayWin.mainWindow
                    && maximizeOverlayWin.mainWindow.isClosing) {
                maximizeOverlayWin.closeOverlay("main-closing")
            }
        }
    }

    Item {
        id: surfaceSprite
        x: maximizeOverlayWin.renderX
        y: maximizeOverlayWin.renderY
        width: Math.max(1, maximizeOverlayWin.sourceWidth)
        height: Math.max(1, maximizeOverlayWin.sourceHeight)
        layer.enabled: true
        layer.smooth: true
        layer.mipmap: maximizeOverlayWin.transitionKind === "restore"
        transform: Scale {
            origin.x: 0
            origin.y: 0
            xScale: maximizeOverlayWin.renderWidth
                / Math.max(1, maximizeOverlayWin.sourceWidth)
            yScale: maximizeOverlayWin.renderHeight
                / Math.max(1, maximizeOverlayWin.sourceHeight)
        }

        ChromeSurface {
            anchors.fill: parent
            roundedSurfaceMaskEnabled: false
            farGlowEnabled: false
            plasmaOpacity: 0.0
            lowFxMode: true
            flairEnabled: false
            t: (maximizeOverlayWin.mainWindow && maximizeOverlayWin.mainWindow.t)
                ? maximizeOverlayWin.mainWindow.t : ({})
            cornerRadius: 0

            MainContent {
                anchors.fill: parent
                t: (maximizeOverlayWin.mainWindow && maximizeOverlayWin.mainWindow.t)
                    ? maximizeOverlayWin.mainWindow.t : ({})
                metrics: (maximizeOverlayWin.mainWindow
                    && maximizeOverlayWin.mainWindow.uiMetrics)
                    ? maximizeOverlayWin.mainWindow.uiMetrics : ({})
                appRef: (maximizeOverlayWin.mainWindow
                    && maximizeOverlayWin.mainWindow.appRef)
                    ? maximizeOverlayWin.mainWindow.appRef : null
                isInteractive: false
                windowRef: maximizeOverlayWin.mainWindow
            }
        }
    }

    NumberAnimation {
        id: transitionAnimation
        target: maximizeOverlayWin
        property: "transitionProgress"
        from: 0.0
        to: 1.0
        duration: (maximizeOverlayWin.mainWindow
            && maximizeOverlayWin.mainWindow.lowPerformanceMode) ? 190 : 280
        easing.type: Easing.Linear
        onFinished: maximizeOverlayWin.transitionFinished()
    }

    Timer {
        id: handoffDelay
        interval: 16
        repeat: false
        onTriggered: maximizeOverlayWin.markHandoffReady()
    }

    Component.onCompleted: handoffDelay.start()

    onVisibleChanged: {
        if (visible && !handoffReadySignaled) handoffDelay.restart()
    }

    onClosing: (closeEvent) => {
        closeEvent.accepted = true
    }
}
