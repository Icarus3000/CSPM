import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    property var t
    property var metrics
    property string icon: ""
    property string label: ""
    signal clicked()
    property string appStyle: "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property var scaleRatios: ({
        "cornerRadiusPct": 0.013,
        "borderWidthPct": 0.0011,
        "hoverBlurPct": 0.017,
        "contentSpacingPct": 0.017,
        "iconFontPct": 0.059,
        "labelFontPct": 0.020
    })
    function ratioPx(ratio, minPx) {
        var rw = width
        var rh = height
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            rw = metrics.contentW
            rh = metrics.contentH
        }
        var unit = Math.min(Math.max(1, rw), Math.max(1, rh))
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(unit * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    property bool hovered: hoverHandler.hovered
    HoverHandler { id: hoverHandler }
    TapHandler { onTapped: root.clicked() }

    Rectangle {
        anchors.fill: parent
        color: root.hovered ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : SemanticTheme.surfaceInput(root.t, root.appStyle)
        radius: visualRules.radiusPanel
        border.color: root.hovered ? SemanticTheme.accentPrimary(root.t, root.appStyle) : SemanticTheme.borderSubtle(root.t, root.appStyle)
        border.width: root.ratioPx(root.scaleRatios.borderWidthPct, 1)
        
        layer.enabled: root.hovered
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: SemanticTheme.shadow(root.t, "panel", "neutral", root.appStyle)
            shadowOpacity: visualRules.shadowOpacity
            shadowBlur: root.ratioPx(root.scaleRatios.hoverBlurPct, 2)
        }

        // CENTERED CONTENT
        ColumnLayout {
            anchors.centerIn: parent
            spacing: root.ratioPx(root.scaleRatios.contentSpacingPct, 4)

            // ICON
            Text {
                text: root.icon
                font.family: visualRules.iconFontFamily
                font.pixelSize: root.ratioPx(root.scaleRatios.iconFontPct, root.metricFloor("fontFloorIconPx", 12))
                color: root.hovered ? SemanticTheme.accentPrimary(root.t, root.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
                Layout.alignment: Qt.AlignHCenter
            }

            // LABEL
            Text {
                text: root.label
                font.pixelSize: root.ratioPx(root.scaleRatios.labelFontPct, root.metricFloor("fontFloorLabelPx", 8))
                font.family: visualRules.textFontFamily
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }
}
