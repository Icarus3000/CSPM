pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"

Rectangle {
    property var root

    visible: root.activeIsGlobalSearch()


    radius: root.sectionRadiusPx
    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
    border.width: 1
    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
        spacing: root.ratioPx(root.scaleRatios.pageSpacingPct * 0.55, 5)

        RowLayout {

            spacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct * 0.6, 6)

            Text {
                text: "Search Mode"
                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.76)
                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                verticalAlignment: Text.AlignVCenter
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Any"
                primary: root.globalSearchMode !== "boolean"
                Layout.preferredWidth: root.ratioPxW(0.070, 64)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.setGlobalSearchMode("any")
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Boolean"
                primary: root.globalSearchMode === "boolean"
                Layout.preferredWidth: root.ratioPxW(0.096, 88)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.setGlobalSearchMode("boolean")
            }

            Item { Layout.fillWidth: true }
        }

        Flickable {
            id: searchFlickable
            Layout.fillWidth: true
            Layout.preferredHeight: root.fieldHeightPx
            contentWidth: filterRow.implicitWidth
            contentHeight: root.fieldHeightPx
            clip: true
            interactive: contentWidth > width

            ScrollBar.horizontal: ScrollBar {
                active: true
                policy: searchFlickable.contentWidth > searchFlickable.width ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
            }

            RowLayout {
                id: filterRow
                spacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct * 0.45, 5)

                Repeater {
                    model: root.globalSearchTypeOptions()
                    delegate: PillButton {
                        required property var modelData
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: String(modelData.label || "")
                            + " (" + String(root.globalSearchFacetCount(modelData.id)) + ")"
                        primary: root._cleanLowerText(modelData.id) === root._cleanLowerText(root.globalSearchEntityFilter)
                        Layout.preferredWidth: Math.max(
                            root.ratioPxW(0.078, 74),
                            (String(text || "").length * root.ratioPx(0.0062, 5)) + root.ratioPx(0.026, 20)
                        )
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.setGlobalSearchEntityFilter(String(modelData.id || "all"))
                    }
                }
            }
        }

        Text {
            text: String(root.globalSearchMessage || "")
            color: root.globalSearchLastOk
                ? Qt.rgba(root._text.r, root._text.g, root._text.b, 0.78)
                : Qt.rgba(0.98, 0.42, 0.42, 0.96)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.sectionRadiusPx
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.64)
            border.width: 1
            border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.14)
            clip: true

            ListView {
                id: globalSearchList
                anchors.fill: parent
                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct, 8)
                model: root.globalSearchFilteredRows
                spacing: root.ratioPx(0.0040, 4)

                delegate: Rectangle {
                    id: globalRow
                    required property var modelData
                    property bool hovered: false
                    width: globalSearchList.width
                    implicitHeight: rowBody.implicitHeight + root.ratioPx(0.010, 8)
                    radius: Math.max(5, root.sectionRadiusPx - 3)
                    color: hovered
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.12)
                        : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.70)
                    border.width: 1
                    border.color: hovered
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.46)
                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.14)

                    RowLayout {
                        id: rowBody
                        anchors.fill: parent
                        anchors.leftMargin: root.ratioPx(0.008, 6)
                        anchors.rightMargin: root.ratioPx(0.008, 6)
                        anchors.topMargin: root.ratioPx(0.0045, 3)
                        anchors.bottomMargin: root.ratioPx(0.0045, 3)
                        spacing: root.ratioPx(0.006, 4)

                        Rectangle {
                            Layout.alignment: Qt.AlignTop
                            Layout.preferredWidth: root.ratioPxW(0.084, 78)
                            Layout.preferredHeight: root.ratioPxH(0.045, 32)
                            radius: Math.max(4, root.sectionRadiusPx - 5)
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.22)
                            border.width: 1
                            border.color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.52)

                            Text {
                                anchors.centerIn: parent
                                text: String(globalRow.modelData.entityTypeLabel || globalRow.modelData.entityType || "Item")
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.92)
                                font.pixelSize: root.ratioPx(0.0098, root.metricFloor("fontFloorLabelPx", 8))
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }

                        ColumnLayout {

                            Layout.fillWidth: true
                            spacing: root.ratioPx(0.0028, 2)

                            Text {
                                Layout.fillWidth: true
                                text: root._cleanLowerText(globalRow.modelData.entityType) === "client"
                                    ? root.globalResultClientHeadline(globalRow.modelData)
                                    : String(globalRow.modelData.title || "")
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.96)
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0116, root.metricFloor("fontFloorBodyPx", 9))
                                font.weight: Font.DemiBold
                            }

                            Text {
                                Layout.fillWidth: true
                                text: root._cleanLowerText(globalRow.modelData.entityType) === "client"
                                    ? root.globalResultClientSecondary(globalRow.modelData)
                                    : String(globalRow.modelData.subtitle || "")
                                visible: text.length > 0
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.76)
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0100, root.metricFloor("fontFloorLabelPx", 8))
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Matched: " + String((globalRow.modelData.matchedFields || []).join(", "))
                                visible: text.length > 9
                                color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.92)
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0096, root.metricFloor("fontFloorLabelPx", 8))
                            }
                        }

                        Text {
                            Layout.alignment: Qt.AlignVCenter
                            text: "Open"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.96)
                            font.pixelSize: root.ratioPx(0.0102, root.metricFloor("fontFloorLabelPx", 8))
                            font.weight: Font.DemiBold
                            font.underline: true
                        }
                    }

                    HoverHandler {
                        cursorShape: Qt.PointingHandCursor
                        onHoveredChanged: globalRow.hovered = hovered
                    }

                    TapHandler {
                        acceptedButtons: Qt.LeftButton
                        onTapped: root.openGlobalSearchResult(globalRow.modelData)
                    }
                }
            }
        }
    }
}
