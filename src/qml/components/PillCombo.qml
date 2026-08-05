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
    property var model: []
    property string value: ""
    signal changed(string value)
    property var scaleRatios: ({
        "implicitHeightPct": 0.067,
        "implicitWidthPct": 0.262,
        "sectionSpacingPct": 0.0043,
        "labelFontPct": 0.013,
        "fieldHeightPct": 0.043,
        "fieldRadiusPct": 0.017,
        "comboMarginPct": 0.0065,
        "indicatorMarginPct": 0.011,
        "indicatorFontPct": 0.015
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
                combo.activeFocus ? 0.96 : 0.90
            )
            border.width: combo.activeFocus ? root.ratioPx(0.0033, 1) : root.ratioPx(0.0022, 1)
            border.color: combo.activeFocus
                ? (root.t && root.t.hover ? root.t.hover : root.accentColor)
                : SemanticTheme.borderSubtle(root.t, root.appStyle)

            ComboBox {
                id: combo
                anchors.fill: parent
                anchors.margins: root.ratioPx(root.scaleRatios.comboMarginPct, 2)
                model: root.model
                editable: true
                background: null

                Component.onCompleted: combo.editText = root.value || ""

                onEditTextChanged: {
                    root.value = combo.editText
                    root.changed(root.value)
                }

                onActivated: {
                    root.value = combo.currentText
                    root.changed(root.value)
                }

                contentItem: TextField {
                    text: combo.editText
                    background: null
                    color: root.textColor
                    onTextEdited: combo.editText = text
                }

                indicator: Text {
                    text: "\u25BE"
                    color: root.textColor
                    anchors.right: parent.right
                    anchors.rightMargin: root.ratioPx(root.scaleRatios.indicatorMarginPct, 3)
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: root.ratioPx(root.scaleRatios.indicatorFontPct, root.metricFloor("fontFloorLabelPx", 8))
                }

                popup: Popup {
                    y: combo.height + root.ratioPx(0.0018, 1)
                    width: combo.width
                    padding: root.ratioPx(0.0011, 1)
                    implicitHeight: Math.min(contentItem.implicitHeight, root.ratioPx(0.220, 180))

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: combo.popup.visible ? combo.delegateModel : null
                        currentIndex: combo.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator { }
                    }

                    background: SemanticPanel {
                        t: root.t
                        role: "popup"
                        tone: "neutral"
                        radius: root.ratioPx(0.0098, 4)
                        borderWidth: root.ratioPx(0.0011, 1)
                    }
                }

                delegate: ItemDelegate {
                    id: rowDelegate
                    required property string modelData
                    required property int index
                    width: combo.width
                    height: root.ratioPx(0.034, 20)
                    hoverEnabled: true
                    text: rowDelegate.modelData
                    highlighted: combo.highlightedIndex === index
                    font.pixelSize: root.ratioPx(0.0135, root.metricFloor("fontFloorBodyPx", 9))
                    contentItem: Text {
                        text: rowDelegate.text
                        color: root.textColor
                        font: rowDelegate.font
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    background: Rectangle {
                        color: (rowDelegate.hovered || rowDelegate.highlighted)
                            ? rowDelegate.highlighted ? SemanticTheme.hoverOverlay(root.t, root.appStyle) : "transparent"
                            : "transparent"
                    }
                }
            }
        }
    }

    onValueChanged: {
        if (combo && combo.editText !== root.value) {
            combo.editText = root.value || ""
        }
    }
}
