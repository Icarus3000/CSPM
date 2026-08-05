import QtQuick
import QtQuick.Layouts

Item {
    id: root
    
    // Properties injected from parent
    property var t
    property var metrics
    property string message: "Loading Data... Please Wait"
    property bool isActive: false
    property string tone: "info"
    
    // Geometry scale helpers
    function contentUnit() {
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            return Math.min(Math.max(1, metrics.contentW), Math.max(1, metrics.contentH))
        }
        return 800 // Safe fallback to avoid cyclic loops
    }

    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentUnit() * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    // Dynamic sizing constants
    property int heightPx: ratioPx(0.045, 36)
    property int padPx: ratioPx(0.018, 14)
    property int radiusPx: ratioPx(0.010, 8)
    property int iconSizePx: ratioPx(0.022, 16)
    
    // Hard lock implicit width to prevent infinite binding loops
    width: padPx * 2 + iconSizePx + padPx * 0.5 + Math.max(1, msgText.implicitWidth)
    height: heightPx
    
    opacity: isActive ? 1.0 : 0.0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

    SemanticPanel {
        id: bubble
        anchors.fill: parent
        radius: root.radiusPx
        borderWidth: 1
        t: root.t
        role: "toast"
        tone: root.tone

        // Removed ShaderEffect drop shadow in Qt6 since qsb preprocessing is required
        // and we don't have a build pipeline.

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: root.padPx
            anchors.rightMargin: root.padPx
            spacing: root.padPx * 0.5

            // Simple pulsing icon indicator
            Rectangle {
                Layout.preferredWidth: root.iconSizePx
                Layout.preferredHeight: root.iconSizePx
                radius: root.iconSizePx / 2
                color: bubble.accentColor
                
                SequentialAnimation on opacity {
                    running: root.isActive
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.3; duration: 600; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.3; to: 1.0; duration: 600; easing.type: Easing.InOutSine }
                }
            }

            Text {
                id: msgText
                text: root.message
                color: bubble.inkColor
                font.pixelSize: root.metricFloor("fontFloorLabelPx", 11)
                font.weight: Font.Medium
                Layout.alignment: Qt.AlignVCenter
            }
        }
    }
}
