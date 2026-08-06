pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"
import "../../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    property var root

    visible: root.activeIsMatterDirectory()


    radius: root.sectionRadiusPx
    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
        spacing: root.ratioPx(root.scaleRatios.pageSpacingPct * 0.55, 5)

        RowLayout {
            Layout.fillWidth: true
            spacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct * 0.6, 6)

            ModernTextField {
                id: matterDirectorySearchInput
                t: root.t
                metrics: root.responsiveMetrics
                label: "Search Matter Directory"
                text: root.matterDirectoryQuery
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                onTextChanged: {
                    root.matterDirectoryQuery = text
                    root.rebuildMatterDirectoryFilteredRows()
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "All"
                primary: root.matterDirectoryMode !== "active"
                Layout.preferredWidth: root.ratioPxW(0.070, 64)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.matterDirectoryMode = "all"
                    root.rebuildMatterDirectoryFilteredRows()
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Active"
                primary: root.matterDirectoryMode === "active"
                Layout.preferredWidth: root.ratioPxW(0.084, 78)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.matterDirectoryMode = "active"
                    root.rebuildMatterDirectoryFilteredRows()
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Report"
                Layout.preferredWidth: root.ratioPxW(0.084, 78)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    var detailRows = []
                    var rows = root.matterDirectoryFilteredRows || []
                    for (var i = 0; i < rows.length; i++) {
                        var row = rows[i] || {}
                        detailRows.push({
                            "matterId": String(row.matterId || ""),
                            "matterNumber": String(row.matterNumber || ""),
                            "displayName": String(row.displayName || ""),
                            "clientName": String(row.clientName || ""),
                            "matterType": String(row.matterType || ""),
                            "practiceArea": String(row.practiceArea || ""),
                            "responsibleLawyer": String(row.responsibleLawyer || ""),
                            "status": String(row.status || ""),
                            "billingArrangement": String(row.billingArrangement || "")
                        })
                    }

                    var doc = {
                        "reportId": "matter_directory",
                        "title": "Matter Directory Report",
                        "generatedAt": Qt.formatDateTime(new Date(), "yyyy-MM-dd hh:mm"),
                        "orientation": "landscape",
                        "branding": {
                            "firmName": "Cory Schneider Law Office",
                            "firmContact": "Cory Schneider Law Office Practice Management",
                            "logoUrl": "../assets/CS.svg"
                        },
                        "filterSummary": "Search: " + (root.matterDirectoryQuery || "(none)") + " | Mode: " + root.matterDirectoryMode,
                        "sections": [
                            {
                                "sectionId": "detail",
                                "type": "table",
                                "title": "Detail",
                                "columns": [
                                    { "key": "matterNumber", "label": "Matter #", "width": 0.12 },
                                    { "key": "clientName", "label": "Client", "width": 0.24 },
                                    { "key": "displayName", "label": "Matter Name", "width": 0.24 , "multiline": true, "wrap": true },
                                    { "key": "practiceArea", "label": "Practice Area", "width": 0.10 },
                                    { "key": "responsibleLawyer", "label": "Lawyer", "width": 0.12 },
                                    { "key": "billingArrangement", "label": "Billing", "width": 0.10 },
                                    { "key": "status", "label": "Status", "width": 0.08 }
                                ],
                                "rows": detailRows
                            }
                        ]
                    }
                    root.reportWindowRequested(doc)
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "+ New Matter"
                primary: true
                Layout.preferredWidth: root.ratioPxW(0.120, 110)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.workspaceOpenRequested(0, "A10", {})
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Matters found: " + String(root.matterDirectoryFilteredRows.length)
                + (root.matterDirectoryMode === "active" ? " (active only)" : "")
            color: SemanticTheme.inkMuted(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
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
                id: matterDirectoryList
                anchors.fill: parent
                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct, 8)
                model: root.matterDirectoryFilteredRows
                spacing: root.ratioPx(0.0035, 3)

                delegate: Rectangle {
                    id: matterDirectoryRow
                    required property var modelData
                    width: matterDirectoryList.width
                    height: root.fieldHeightPx
                    radius: Math.max(5, root.sectionRadiusPx - 3)
                    readonly property string rowMatterId: String(modelData.matterId || "")
                    readonly property string rowMatterName: String(modelData.matterName || modelData.displayName || "")
                    readonly property bool selected: (root.selectedMatterId.length > 0 && root.selectedMatterId === rowMatterId)
                        || (root.selectedMatterId.length <= 0 && root.selectedMatterName.length > 0 && root.selectedMatterName === rowMatterName)
                    color: selected
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.20)
                        : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.70)
                    border.width: 1
                    border.color: selected
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.58)
                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.12)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: root.ratioPx(0.007, 6)
                        anchors.rightMargin: root.ratioPx(0.007, 6)
                        spacing: root.ratioPx(0.005, 4)

                        Text {
                            Layout.preferredWidth: root.ratioPxW(0.130, 110)
                            text: String(modelData.matterNumber || "")
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.74)
                            elide: Text.ElideRight
                            font.pixelSize: root.ratioPx(0.010, root.metricFloor("fontFloorLabelPx", 8))
                            font.weight: Font.Medium
                        }

                        Text {
                            Layout.preferredWidth: root.ratioPxW(0.200, 180)
                            text: String(modelData.clientName || "")
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, root.matterRowIsActive(modelData) ? 0.9 : 0.4)
                            font.pixelSize: root.ratioPx(0.0125, 12.5)
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: String(modelData.displayName || modelData.matterName || "")
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, root.matterRowIsActive(modelData) ? 0.9 : 0.4)
                            font.pixelSize: root.ratioPx(0.0125, 12.5)
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.preferredWidth: root.ratioPxW(0.090, 80)
                            horizontalAlignment: Text.AlignRight
                            text: String(modelData.status || "")
                            color: root.matterRowIsActive(modelData)
                                ? SemanticTheme.accentPrimary(root.t, root.appStyle)
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.66)
                            elide: Text.ElideRight
                            font.pixelSize: root.ratioPx(0.0102, root.metricFloor("fontFloorLabelPx", 8))
                            font.weight: root.matterRowIsActive(modelData) ? Font.Bold : Font.Medium
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.setMatterDirectorySelection(matterDirectoryRow.modelData)
                        onDoubleClicked: root.openMatterProfileFromDirectory(matterDirectoryRow.modelData)
                    }
                }
            }
        }

        Text {

            text: "Tip: double-click a matter to open Matter Profile 360."
            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.66)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }
    }
}
