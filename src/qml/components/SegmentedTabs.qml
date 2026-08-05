pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    property var t
    property var metrics
    property int index: 0
    signal changed(int ix)
    property string appStyle: "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property var scaleRatios: ({
        "implicitHeightPct": 0.046,
        "implicitWidthPct": 0.295,
        "outerRadiusPct": 0.017,
        "outerBorderPct": 0.0011,
        "tabsSpacingPct": 0.011,
        "tabRadiusPct": 0.013,
        "tabBorderPct": 0.0011,
        "tabTextPct": 0.013
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

    implicitHeight: ratioPx(scaleRatios.implicitHeightPct, 20)
    implicitWidth: ratioPx(scaleRatios.implicitWidthPct, 160)

    Rectangle {
        anchors.fill: parent
        radius: visualRules.radiusControl
        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
        border.width: root.ratioPx(root.scaleRatios.outerBorderPct, 1)
        border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

        Row {
            anchors.centerIn: parent
            spacing: root.ratioPx(root.scaleRatios.tabsSpacingPct, 2)

            Repeater {
                model: ["Menu", "Time Entry", "Settings"]
                delegate: Button {
                    id: tabButton
                    required property string modelData
                    required property int index
                    text: modelData
                    checkable: true
                    checked: root.index === tabButton.index
                    onClicked: {
                        root.index = tabButton.index
                        root.changed(root.index)
                    }

                    background: Rectangle {
                        radius: visualRules.radiusControl
                        color: tabButton.checked
                            ? SemanticTheme.accentPrimary(root.t, root.appStyle)
                            : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.width: root.ratioPx(root.scaleRatios.tabBorderPct, 1)
                        border.color: tabButton.checked
                            ? SemanticTheme.borderStrong(root.t, root.appStyle)
                            : SemanticTheme.borderSubtle(root.t, root.appStyle)
                    }

                    contentItem: Text {
                        text: tabButton.text
                        color: tabButton.checked ? root.t.btn_text : root.t.text
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: visualRules.textFontFamily
                        font.pixelSize: root.ratioPx(root.scaleRatios.tabTextPct, root.metricFloor("fontFloorLabelPx", 8))
                        font.weight: Font.DemiBold
                    }
                }
            }
        }
    }
}
