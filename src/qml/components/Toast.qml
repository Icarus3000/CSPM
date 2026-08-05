import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var t
    property string message: ""
    property bool visibleToast: false
    property var metrics
    property string tone: "info"
    property var scaleRatios: ({
        "hostHeightPct": 0.048,
        "bottomMarginPct": 0.0065,
        "bubbleWidthPct": 0.70,
        "bubbleWidthMaxPct": 0.459,
        "bubbleHeightPct": 0.039,
        "bubbleRadiusPct": 0.017,
        "bubbleBorderPct": 0.0011,
        "textSizePct": 0.013,
        "textInsetPct": 0.026
    })

    function contentW() {
        if (metrics && typeof metrics.contentW === "number") return Math.max(1, metrics.contentW)
        return Math.max(1, root.width)
    }
    function contentH() {
        if (metrics && typeof metrics.contentH === "number") return Math.max(1, metrics.contentH)
        return Math.max(1, root.height)
    }
    function ratioPx(ratio, minPx) {
        var unit = Math.min(contentW(), contentH())
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(unit * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }
    // Caller should set left/right OR anchors.fill; we do not set conflicting anchors here.
    height: ratioPx(scaleRatios.hostHeightPct, 20)

    SemanticPanel {
        id: bubble
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.ratioPx(root.scaleRatios.bottomMarginPct, 2)
        t: root.t
        role: "toast"
        tone: root.tone

        width: Math.min(contentW() * root.scaleRatios.bubbleWidthPct, Math.round(contentW() * root.scaleRatios.bubbleWidthMaxPct))
        height: root.ratioPx(root.scaleRatios.bubbleHeightPct, 16)
        radius: root.ratioPx(root.scaleRatios.bubbleRadiusPct, 4)
        borderWidth: root.ratioPx(root.scaleRatios.bubbleBorderPct, 1)
        opacity: root.visibleToast ? 1 : 0

        Text {
            anchors.centerIn: parent
            text: root.message
            color: bubble.inkColor
            font.pixelSize: root.ratioPx(root.scaleRatios.textSizePct, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
            width: parent.width - root.ratioPx(root.scaleRatios.textInsetPct, 8)
            horizontalAlignment: Text.AlignHCenter
        }

        Behavior on opacity { NumberAnimation { duration: 140 } }
    }

    Timer {
        id: tmr
        interval: 1700
        repeat: false
        onTriggered: root.visibleToast = false
    }

    function show(msg) {
        root.message = msg
        root.visibleToast = true
        tmr.restart()
    }
}
