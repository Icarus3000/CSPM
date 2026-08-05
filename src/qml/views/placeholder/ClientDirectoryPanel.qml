pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"
import "../../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    property var root

    visible: root.activeIsClientDirectory()
    radius: root.sectionRadiusPx
    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

    onVisibleChanged: {
        if (visible && root && root.refreshClientDirectory) {
            root.refreshClientDirectory(root.clientDirectoryMode === "active")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
        spacing: root.ratioPx(root.scaleRatios.pageSpacingPct * 0.55, 5)

        RowLayout {
            Layout.fillWidth: true
            spacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct * 0.6, 6)

            ModernTextField {
                id: directorySearchInput
                t: root.t
                metrics: root.responsiveMetrics
                label: "Search Client Directory"
                text: root.clientDirectoryQuery
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                onTextChanged: {
                    root.clientDirectoryQuery = text
                    root.rebuildClientDirectoryFilteredRows()
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "All"
                primary: root.clientDirectoryMode !== "active"
                Layout.preferredWidth: root.ratioPxW(0.070, 64)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.clientDirectoryMode = "all"
                    root.rebuildClientDirectoryFilteredRows()
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Active"
                primary: root.clientDirectoryMode === "active"
                Layout.preferredWidth: root.ratioPxW(0.084, 78)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.clientDirectoryMode = "active"
                    root.rebuildClientDirectoryFilteredRows()
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
                    var rows = root.clientDirectoryFilteredRows || []
                    for (var i = 0; i < rows.length; i++) {
                        var row = rows[i] || {}
                        detailRows.push({
                            "clientId": String(row.clientId || ""),
                            "clientName": String(row.clientName || ""),
                            "displayName": String(row.displayName || ""),
                            "status": String(row.status || ""),
                            "entityType": String(row.entityType || ""),
                            "principalName": String(row.principalName || ""),
                            "primaryEmail": String(row.primaryEmail || ""),
                            "primaryPhone": String(row.primaryPhone || ""),
                            "onboardingStatus": String(row.onboardingStatus || ""),
                            "activeMattersCount": String(row.activeMattersCount !== undefined ? row.activeMattersCount : "0")
                        })
                    }

                    var doc = {
                        "reportId": "client_directory",
                        "title": "Client Directory Report",
                        "generatedAt": Qt.formatDateTime(new Date(), "yyyy-MM-dd hh:mm"),
                        "orientation": "landscape",
                        "branding": {
                            "firmName": "Cory Schneider Law Office",
                            "firmContact": "Cory Schneider Law Office Practice Management",
                            "logoUrl": "../assets/CS.svg"
                        },
                        "filterSummary": "Search: " + (root.clientDirectoryQuery || "(none)") + " | Mode: " + root.clientDirectoryMode,
                        "sections": [
                            {
                                "sectionId": "detail",
                                "type": "table",
                                "title": "Detail",
                                "columns": [
                                    { "key": "clientId", "label": "Client ID", "width": 0.10 },
                                    { "key": "displayName", "label": "Client Name", "width": 0.24 },
                                    { "key": "entityType", "label": "Entity Type", "width": 0.14 },
                                    { "key": "principalName", "label": "Principal", "width": 0.16 },
                                    { "key": "primaryEmail", "label": "Email", "width": 0.18 },
                                    { "key": "status", "label": "Status", "width": 0.08 },
                                    { "key": "activeMattersCount", "label": "Matters", "width": 0.10, "align": "right" }
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
                text: "+ New Client"
                primary: true
                Layout.preferredWidth: root.ratioPxW(0.120, 110)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    root.workspaceOpenRequested(0, "A02", {})
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Clients found: " + String(root.clientDirectoryFilteredRows.length)
                + (root.clientDirectoryMode === "active" ? " (active only)" : "")
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
                id: clientDirectoryList
                anchors.fill: parent
                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct, 8)
                model: root.clientDirectoryFilteredRows
                spacing: root.ratioPx(0.0035, 3)

                delegate: Rectangle {
                    id: directoryRow
                    required property var modelData
                    width: clientDirectoryList.width
                    height: root.fieldHeightPx
                    radius: Math.max(5, root.sectionRadiusPx - 3)
                    readonly property string rowClientId: String(modelData.clientId || "")
                    readonly property string rowClientName: String(modelData.clientName || modelData.displayName || "")
                    readonly property bool selected: (root.selectedClientId.length > 0 && root.selectedClientId === rowClientId)
                        || (root.selectedClientId.length <= 0 && root.selectedClientName.length > 0 && root.selectedClientName === rowClientName)
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
                            Layout.fillWidth: true
                            text: String(modelData.displayName || modelData.clientName || "")
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                            elide: Text.ElideRight
                            font.pixelSize: root.ratioPx(0.0115, root.metricFloor("fontFloorBodyPx", 9))
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.preferredWidth: root.ratioPxW(0.090, 80)
                            horizontalAlignment: Text.AlignRight
                            text: String(modelData.status || "")
                            color: root.clientRowIsActive(modelData)
                                ? SemanticTheme.accentPrimary(root.t, root.appStyle)
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.66)
                            elide: Text.ElideRight
                            font.pixelSize: root.ratioPx(0.0102, root.metricFloor("fontFloorLabelPx", 8))
                        }
                    }

                    TapHandler {
                        onTapped: root.setDirectorySelection(directoryRow.modelData)
                        onDoubleTapped: root.openClientProfileFromDirectory(directoryRow.modelData)
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Tip: double-click a client to open Client Profile 360."
            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.66)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }
    }
}
