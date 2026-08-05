pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var t
    property string appStyle: "Professional"
    property var metrics
    property color panelColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color textColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property string label: ""
    property string text: field.text
    property string placeholderText: ""
    signal edited(string value)
    property var scaleRatios: ({
        "implicitHeightPct": 0.067,
        "implicitWidthPct": 0.262,
        "sectionSpacingPct": 0.0043,
        "labelFontPct": 0.013,
        "fieldHeightPct": 0.043,
        "fieldRadiusPct": 0.017,
        "fieldMarginPct": 0.011
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

    implicitHeight: ratioPx(scaleRatios.implicitHeightPct, 26)
    implicitWidth: ratioPx(scaleRatios.implicitWidthPct, 140)

    ColumnLayout {
        anchors.fill: parent
        spacing: root.ratioPx(root.scaleRatios.sectionSpacingPct, 2)

        Text {
            text: root.label
            color: root.textColor
            opacity: 1.0
            font.pixelSize: root.ratioPx(root.scaleRatios.labelFontPct, root.metricFloor("fontFloorLabelPx", 8))
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.ratioPx(root.scaleRatios.fieldHeightPct, 18)
            radius: root.ratioPx(root.scaleRatios.fieldRadiusPct, 4)
            color: Qt.rgba(
                (root.panelColor.r * 0.82) + (root.accentColor.r * 0.18),
                (root.panelColor.g * 0.82) + (root.accentColor.g * 0.18),
                (root.panelColor.b * 0.82) + (root.accentColor.b * 0.18),
                field.activeFocus ? 0.96 : 0.90
            )
            border.width: field.activeFocus ? root.ratioPx(0.0033, 1) : root.ratioPx(0.0022, 1)
            border.color: field.activeFocus
                ? (root.t && root.t.hover ? root.t.hover : root.accentColor)
                : SemanticTheme.borderSubtle(root.t, root.appStyle)

            TextField {
                id: field
                anchors.fill: parent
                anchors.margins: root.ratioPx(root.scaleRatios.fieldMarginPct, 3)
                background: null
                color: root.textColor
                placeholderText: root.placeholderText
                onTextEdited: root.edited(text)
            }
        }
    }
}
