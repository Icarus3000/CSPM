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

    function rowIsArchived(row) {
        return String(row && row.status !== undefined ? row.status : "").trim().toLowerCase() === "archived"
    }

    function requestArchivedMatterDeletion(row) {
        if (!row || !rowIsArchived(row)) return
        root.setMatterDirectorySelection(row)
        archivedMatterDeleteDialog.openFor(row)
    }


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
                text: "Merge"
                primary: false
                visible: root.selectedMatterId.length > 0 || root.selectedMatterName.length > 0
                Layout.preferredWidth: root.ratioPxW(0.084, 78)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    mergeMatterDirectoryDialog.open()
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
                    readonly property bool archived: rowIsArchived(modelData)
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
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: function(mouse) {
                            root.setMatterDirectorySelection(matterDirectoryRow.modelData)
                            if (mouse.button === Qt.RightButton && matterDirectoryRow.archived) {
                                archivedMatterContextMenu.x = Math.max(0, Math.min(mouse.x, matterDirectoryRow.width - archivedMatterContextMenu.width))
                                archivedMatterContextMenu.y = Math.max(0, Math.min(mouse.y, matterDirectoryRow.height - archivedMatterContextMenu.height))
                                archivedMatterContextMenu.open()
                            }
                        }
                        onDoubleClicked: function(mouse) {
                            if (mouse.button === Qt.LeftButton) {
                                root.openMatterProfileFromDirectory(matterDirectoryRow.modelData)
                            }
                        }
                    }

                    Menu {
                        id: archivedMatterContextMenu
                        parent: matterDirectoryRow
                        width: 230
                        padding: 4

                        background: Rectangle {
                            radius: 4
                            color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
                            border.width: 1
                            border.color: SemanticTheme.borderStrong(root.t, root.appStyle)
                        }

                        delegate: MenuItem {
                            id: menuDelegate
                            implicitHeight: 38

                            contentItem: Text {
                                text: menuDelegate.text
                                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                                rightPadding: 10
                                elide: Text.ElideRight
                            }

                            background: Rectangle {
                                radius: 3
                                color: menuDelegate.highlighted || menuDelegate.hovered
                                    ? SemanticTheme.surface(root.t, "popup", "danger", root.appStyle)
                                    : "transparent"
                            }
                        }

                        MenuItem {
                            text: "Delete archived matter…"
                            onTriggered: requestArchivedMatterDeletion(matterDirectoryRow.modelData)
                        }
                    }
                }
            }
        }

        Text {

            text: "Tip: double-click a matter to open Matter Profile 360. Right-click an archived matter to delete it."
            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.66)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }
    }

    Dialog {
        id: mergeMatterDirectoryDialog
        title: "Merge Selected Matter"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: 500
        height: 250
        anchors.centerIn: parent

        onAccepted: {
            var targetRow = root.resolveMatterDirectoryRowByKey(targetMatterComboDir.editText)
            var targetMatterId = String(targetRow && targetRow.matterId ? targetRow.matterId : "").trim()
            if (!targetMatterId) {
                root.saveMessage = "Choose a target matter from the directory list."
                return
            }
            if (targetMatterId === root.selectedMatterId) {
                root.saveMessage = "Source and target matters must be different."
                return
            }

            var res = undefined
            if (typeof root.mergeMatters === "function") {
                res = root.mergeMatters(root.selectedMatterId, targetMatterId)
            } else if (root.appRef && root.appRef.mergeMatters) {
                res = root.appRef.mergeMatters(root.selectedMatterId, targetMatterId)
            }

            if (res && res.ok) {
                mergeSuccessDialogDir.sourceMatterId = root.selectedMatterId
                mergeSuccessDialogDir.targetMatterId = targetMatterId
                mergeSuccessDialogDir.open()
                root.refreshMatterDirectory(true)
            } else {
                root.saveMessage = res && res.message ? res.message : "Matter merge failed."
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 15

            Text {
                text: "Select the authoritative matter to merge the currently selected matter into (" + (root.selectedMatterName || root.selectedMatterId || "Unknown") + "). All dockets and transactions will be moved to the target matter. The selected matter will be archived. This cannot be undone."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: 13
            }

            ModernComboBox {
                id: targetMatterComboDir
                t: root.t
                metrics: root.responsiveMetrics
                label: "Target Matter"
                fullModel: root.matterDirectoryNameOptions
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
            }
        }
    }

    MatterMergeSuccessDialog {
        id: mergeSuccessDialogDir
        host: root
    }

    ArchivedMatterDeleteDialog {
        id: archivedMatterDeleteDialog
        host: root
    }
}
