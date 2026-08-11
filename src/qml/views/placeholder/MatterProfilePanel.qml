pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"
import "../../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    property var root

    visible: root.activeIsMatterProfile360()


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

            ModernComboBox {
                id: profileMatterCombo
                t: root.t
                metrics: root.responsiveMetrics
                label: "Select Matter"
                fullModel: root.matterDirectoryNameOptions
                editText: root.selectedMatterName

                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                onEditTextChanged: {
                    if (profileMatterCombo.activeFocus) {
                        root.selectedMatterName = editText
                    }
                    if (editText.length <= 0) {
                        root.selectedMatterId = ""
                    }
                }
                onActivated: root.selectedMatterName = editText

                Connections {
                    target: root
                    function onSelectedMatterNameChanged() {
                        if (!profileMatterCombo.activeFocus && profileMatterCombo.editText !== root.selectedMatterName) {
                            profileMatterCombo.editText = root.selectedMatterName
                        }
                    }
                }

                onFullModelChanged: {
                    if (root.selectedMatterName.length > 0) {
                        Qt.callLater(function() {
                            if (profileMatterCombo.editText !== root.selectedMatterName) {
                                profileMatterCombo.editText = root.selectedMatterName
                            }
                        })
                    }
                }

                Connections {
                    target: profileMatterCombo
                    function onModelChanged() {
                        if (root.selectedMatterName.length > 0) {
                            Qt.callLater(function() {
                                if (profileMatterCombo.editText !== root.selectedMatterName) {
                                    profileMatterCombo.editText = root.selectedMatterName
                                }
                            })
                        }
                    }
                }
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Load Profile"
                primary: true
                Layout.preferredWidth: root.ratioPxW(0.108, 98)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.loadSelectedMatterProfile(profileMatterCombo.editText)
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Edit Matter"
                primary: true
                Layout.preferredWidth: root.ratioPxW(0.108, 98)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.editSelectedMatterInWizard()
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Directory"
                primary: false
                Layout.preferredWidth: root.ratioPxW(0.088, 80)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.gotoNode("A09")
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Ledger Report"
                primary: false
                visible: root.selectedClientId.length > 0
                Layout.preferredWidth: root.ratioPxW(0.12, 110)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.gotoNode("D07")
            }
            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Merge Matter"
                primary: false
                visible: root.selectedMatterId.length > 0
                Layout.preferredWidth: root.ratioPxW(0.12, 110)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: mergeMatterDialog.open()
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Delete Archived"
                primary: false
                visible: root.selectedMatterId.length > 0
                    && String(root.selectedMatterProfile && root.selectedMatterProfile.status ? root.selectedMatterProfile.status : "").trim().toLowerCase() === "archived"
                Layout.preferredWidth: root.ratioPxW(0.132, 124)
                Layout.preferredHeight: root.fieldHeightPx
                ToolTip.text: "Permanently delete this archived matter"
                onClicked: {
                    archivedMatterDeleteDialogProfile.openFor({
                        "matterId": root.selectedMatterId,
                        "matterNumber": root.selectedMatterProfile && root.selectedMatterProfile.matterNumber ? root.selectedMatterProfile.matterNumber : "",
                        "matterName": root.selectedMatterProfile && root.selectedMatterProfile.matterName ? root.selectedMatterProfile.matterName : root.selectedMatterName,
                        "displayName": root.selectedMatterProfile && root.selectedMatterProfile.displayName ? root.selectedMatterProfile.displayName : ""
                    })
                }
            }
        }

Rectangle {
    id: matterCommandCenterBar
    Layout.fillWidth: true
    Layout.preferredHeight: 60
    Layout.minimumHeight: 60
    Layout.maximumHeight: 60
    radius: Math.max(5, root.sectionRadiusPx - 3)
    color: SemanticTheme.alpha(root._panel, 0.66)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 0
        anchors.bottomMargin: 0
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 2

            Text {
                text: "Matter Command Center"
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.92, root.metricFloor("fontFloorBodyPx", 10))
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            Text {
                text: "Premium quick action: open a clean Time Docket Entry prefilled for this matter."
                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Item {
            Layout.preferredWidth: 180
            Layout.fillHeight: true

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Docket Time"
                primary: true
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 180
                height: 44
                onClicked: {
                root.openTimeDocketForSelectedMatter(profileMatterCombo.editText)
                }
            }
        }

        Item {
            Layout.preferredWidth: 150
            Layout.fillHeight: true

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Statement of Account"
                primary: false
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 150
                height: 44
                onClicked: root.gotoNode("D17")
            }
        }
    }
}

        Rectangle {
            id: matterFinancialProfileCard
            visible: root.selectedMatterId.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(92, matterFinancialProfileContent.implicitHeight + 16)
            radius: Math.max(5, root.sectionRadiusPx - 3)
            color: SemanticTheme.alpha(root._panel, 0.66)
            border.width: 1
            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

            ColumnLayout {
                id: matterFinancialProfileContent
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: "WIP & unpaid invoices"
                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.92, root.metricFloor("fontFloorBodyPx", 10))
                        font.weight: Font.DemiBold
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Open WIP Ledger"
                        primary: false
                        Layout.preferredWidth: root.ratioPxW(0.128, 126)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.openMatterWipLedger()
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.matterFinancialSummaryLoading
                    text: "Loading unbilled WIP and unpaid invoices…"
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                }

                Text {
                    Layout.fillWidth: true
                    visible: !root.matterFinancialSummaryLoading
                        && (!root.matterFinancialSummary || !root.matterFinancialSummary.ok)
                    text: root.matterFinancialSummary && root.matterFinancialSummary.message
                        ? String(root.matterFinancialSummary.message)
                        : "Load a matter to see WIP and unpaid invoices."
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.matterFinancialSummaryLoading
                        && root.matterFinancialSummary && root.matterFinancialSummary.ok
                    spacing: 14

                    Text {
                        text: "Unbilled WIP: " + Number(root.matterFinancialSummary.unbilledWipCount || 0)
                            + " item(s) · " + root.matterFinancialMoney(root.matterFinancialSummary.unbilledWipAmount)
                        color: Number(root.matterFinancialSummary.unbilledWipCount || 0) > 0
                            ? "#b36a1d" : SemanticTheme.inkMuted(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.98, root.metricFloor("fontFloorLabelPx", 8))
                        font.weight: Font.DemiBold
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "Unpaid invoices: " + Number(root.matterFinancialSummary.unpaidInvoiceCount || 0)
                            + " · " + root.matterFinancialMoney(root.matterFinancialSummary.unpaidInvoiceAmount)
                        color: Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) > 0
                            ? "#bd312c" : SemanticTheme.inkMuted(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.98, root.metricFloor("fontFloorLabelPx", 8))
                        font.weight: Font.DemiBold
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.matterFinancialSummary && root.matterFinancialSummary.ok
                        && Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) === 0
                    text: "No unpaid invoices are linked to this matter."
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                }

                Column {
                    Layout.fillWidth: true
                    visible: root.matterFinancialSummary && root.matterFinancialSummary.ok
                        && Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) > 0
                    spacing: 2

                    Repeater {
                        model: root.matterFinancialSummary && root.matterFinancialSummary.unpaidInvoices
                            ? root.matterFinancialSummary.unpaidInvoices : []
                        delegate: Rectangle {
                            required property var modelData
                            width: parent ? parent.width : 0
                            height: Math.max(24, unpaidInvoiceLink.implicitHeight + 6)
                            radius: 3
                            color: unpaidInvoiceMouse.containsMouse
                                ? SemanticTheme.alpha(root._accent, 0.12)
                                : SemanticTheme.alpha(root._bg, 0.20)
                            border.width: 1
                            border.color: SemanticTheme.alpha(root._accent, 0.24)

                            Text {
                                id: unpaidInvoiceLink
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 6
                                text: "Invoice " + String(modelData.invoiceNum || "")
                                    + " · Amount due " + root.matterFinancialMoney(modelData.balanceDue)
                                    + " — open in Invoice Directory"
                                color: SemanticTheme.accentPrimary(root.t, root.appStyle)
                                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                                font.underline: unpaidInvoiceMouse.containsMouse
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                id: unpaidInvoiceMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.openMatterInvoice(String(modelData.invoiceNum || ""))
                            }
                        }
                    }
                }
            }
        }


        Text {

            text: String(root.matterProfileLookupMessage || "Select and load a matter profile.")
            color: SemanticTheme.inkMuted(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }

        ScrollView {
            id: matterProfileDetailsScroll
            Layout.fillWidth: true
            Layout.fillHeight: true


            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                width: Math.max(1, matterProfileDetailsScroll.availableWidth)
                spacing: root.ratioPx(0.0035, 2)

                Repeater {
                    model: root.matterProfileRowModel()
                    delegate: RowLayout {
                        required property var modelData

                        Layout.alignment: Qt.AlignTop
                        spacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct * 0.60, 7)

                        readonly property real cardWidth: Math.max(
                            1,
                            (matterProfileDetailsScroll.availableWidth - spacing) / 2
                        )

                        Rectangle {
                            id: matterLeftCard
                            Layout.fillHeight: true
                            property var entry: modelData.left

                            Layout.preferredWidth: parent.cardWidth
                            Layout.alignment: Qt.AlignTop
                            implicitHeight: entry
                                ? matterLeftValueText.implicitHeight
                                    + matterLeftLabelText.implicitHeight
                                    + (entry.multiline ? root.ratioPx(0.012, 10) : root.ratioPx(0.009, 7))
                                : 1
                            Layout.minimumHeight: entry
                                ? (entry.multiline ? root.ratioPxH(0.084, 66) : root.ratioPxH(0.062, 48))
                                : 1
                            radius: Math.max(5, root.sectionRadiusPx - 3)
                            color: entry
                                ? SemanticTheme.alpha(root._panel, 0.66)
                                : "transparent"
                            border.width: entry ? 1 : 0
                            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                            ColumnLayout {
                                visible: !!matterLeftCard.entry
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(0.0045, 4)
                                spacing: 1

                                Text {
                                    id: matterLeftLabelText

                                    text: String(matterLeftCard.entry && matterLeftCard.entry.label ? matterLeftCard.entry.label : "")
                                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: matterLeftValueText
                                    maximumLineCount: 3
                                    clip: false
                                    elide: Text.ElideNone
                                    width: Math.max(1, parent ? parent.width : 1)
                                    Layout.fillWidth: true

                                    text: String(matterLeftCard.entry && matterLeftCard.entry.value ? matterLeftCard.entry.value : "[blank]")
                                    color: (matterLeftCard.entry && matterLeftCard.entry.label === "Client" && text !== "[blank]") ? SemanticTheme.accentPrimary(root.t, root.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                    font.underline: (matterLeftCard.entry && matterLeftCard.entry.label === "Client" && text !== "[blank]")
                                    wrapMode: Text.WordWrap
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !!matterLeftCard.entry && matterLeftCard.entry.label === "Client" && matterLeftCard.entry.value !== "[blank]"
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.selectedClientName = matterLeftCard.entry.value
                                    root.gotoNode("A10")
                                    root.loadSelectedClientProfile(matterLeftCard.entry.value)
                                }
                            }
                        }

                        Rectangle {
                            id: matterRightCard
                            Layout.fillHeight: true
                            property var entry: modelData.right

                            Layout.preferredWidth: parent.cardWidth
                            Layout.alignment: Qt.AlignTop
                            implicitHeight: entry
                                ? matterRightValueText.implicitHeight
                                    + matterRightLabelText.implicitHeight
                                    + (entry.multiline ? root.ratioPx(0.012, 10) : root.ratioPx(0.009, 7))
                                : 1
                            Layout.minimumHeight: entry
                                ? (entry.multiline ? root.ratioPxH(0.084, 66) : root.ratioPxH(0.062, 48))
                                : 1
                            radius: Math.max(5, root.sectionRadiusPx - 3)
                            color: entry
                                ? SemanticTheme.alpha(root._panel, 0.66)
                                : "transparent"
                            border.width: entry ? 1 : 0
                            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                            ColumnLayout {
                                visible: !!matterRightCard.entry
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(0.0045, 4)
                                spacing: 1

                                Text {
                                    id: matterRightLabelText

                                    text: String(matterRightCard.entry && matterRightCard.entry.label ? matterRightCard.entry.label : "")
                                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: matterRightValueText
                                    maximumLineCount: 3
                                    clip: false
                                    elide: Text.ElideNone
                                    width: Math.max(1, parent ? parent.width : 1)
                                    Layout.fillWidth: true

                                    text: String(matterRightCard.entry && matterRightCard.entry.value ? matterRightCard.entry.value : "[blank]")
                                    color: (matterRightCard.entry && matterRightCard.entry.label === "Client" && text !== "[blank]") ? SemanticTheme.accentPrimary(root.t, root.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                    font.underline: (matterRightCard.entry && matterRightCard.entry.label === "Client" && text !== "[blank]")
                                    wrapMode: Text.WordWrap
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !!matterRightCard.entry && matterRightCard.entry.label === "Client" && matterRightCard.entry.value !== "[blank]"
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.selectedClientName = matterRightCard.entry.value
                                    root.gotoNode("A10")
                                    root.loadSelectedClientProfile(matterRightCard.entry.value)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: mergeMatterDialog
        title: "Merge Matter"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: 500
        height: 250
        anchors.centerIn: parent

        onAccepted: {
            var targetRow = root.resolveMatterDirectoryRowByKey(targetMatterCombo.editText)
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
                mergeSuccessDialogProfile.sourceMatterId = root.selectedMatterId
                mergeSuccessDialogProfile.targetMatterId = targetMatterId
                mergeSuccessDialogProfile.open()
                root.refreshMatterDirectory(true)
            } else {
                root.saveMessage = res && res.message ? res.message : "Matter merge failed."
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 15

            Text {
                text: "Select the authoritative matter to merge this one into. All dockets and transactions will be moved to the target matter. The current matter will be deleted. This cannot be undone."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: 13
            }

            ModernComboBox {
                id: targetMatterCombo
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
        id: mergeSuccessDialogProfile
        host: root
    }

    ArchivedMatterDeleteDialog {
        id: archivedMatterDeleteDialogProfile
        host: root
    }
}
