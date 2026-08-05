pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"
import "../../standards"
import "../../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: clientProfilePanel

    property var root

    visible: root.activeIsClientProfile360()


    radius: root.sectionRadiusPx
    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

    property var relatedMatters: []

    function refreshRelatedMatters() {
        var clientId = String(root.selectedClientId || "").trim()
        var clientName = String(root.selectedClientName || "").trim()
        if (clientId.length <= 0 && clientName.length <= 0) {
            relatedMatters = []
            return
        }
        var allMatters = []
        try {
            if (root.appRef && root.appRef.listMatterDirectory) {
                allMatters = root.appRef.listMatterDirectory()
            }
        } catch (e) {
            allMatters = []
        }
        var filtered = []
        for (var i = 0; i < allMatters.length; i++) {
            var m = allMatters[i]
            var mClientId = String(m.clientId || "").trim()
            var mParentId = String(m.parentId || "").trim()
            var mClientName = String(m.clientName || "").trim()
            var mParentName = String(m.parentName || "").trim()

            var isClient = false
            var isBilling = false

            if (clientId.length > 0) {
                if (mClientId === clientId) isClient = true
                if (mParentId === clientId) isBilling = true
            } else if (clientName.length > 0) {
                if (mClientName.toLowerCase() === clientName.toLowerCase()) isClient = true
                if (mParentName.toLowerCase() === clientName.toLowerCase()) isBilling = true
            }

            if (isClient || isBilling) {
                var role = "Client"
                if (isClient && isBilling) role = "Client & Billing"
                else if (isBilling) role = "Billing Client"

                filtered.push({
                    "matterId": m.matterId,
                    "matterNumber": m.matterNumber || "",
                    "matterName": m.matterName || "",
                    "displayName": m.displayName || m.matterName || "",
                    "clientName": m.clientName || "",
                    "parentName": m.parentName || "",
                    "status": m.status || "Open",
                    "billingArrangement": m.billingArrangement || "Hourly",
                    "role": role,
                    "active": m.active
                })
            }
        }
        relatedMatters = filtered
    }

    function requestProfileAutoLoad() {
        if (!visible || !root || !root.autoLoadSelectedClientProfile) return
        root.autoLoadSelectedClientProfile(profileClientCombo ? profileClientCombo.editText : "")
    }

    onVisibleChanged: {
        if (visible) profileAutoLoadTimer.restart()
    }

    Component.onCompleted: {
        profileAutoLoadTimer.restart()
        clientProfilePanel.refreshRelatedMatters()
    }

    Connections {
        target: clientProfilePanel.root
        ignoreUnknownSignals: true
        function onSelectedClientIdChanged() {
            profileAutoLoadTimer.restart()
            clientProfilePanel.refreshRelatedMatters()
        }
        function onSelectedClientNameChanged() {
            profileAutoLoadTimer.restart()
        }
        function onActiveNodeIdChanged() {
            if (clientProfilePanel.visible) {
                profileAutoLoadTimer.restart()
                clientProfilePanel.refreshRelatedMatters()
            }
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onClientDataChanged() {
            clientProfilePanel.refreshRelatedMatters()
        }
    }

    Timer {
        id: profileAutoLoadTimer
        interval: 40
        repeat: false
        onTriggered: clientProfilePanel.requestProfileAutoLoad()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
        spacing: root.ratioPx(root.scaleRatios.pageSpacingPct * 0.55, 5)

        RowLayout {
            Layout.fillWidth: true

            spacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct * 0.6, 6)

            ModernComboBox {
                id: profileClientCombo
                t: root.t
                metrics: root.responsiveMetrics
                label: "Select Client"
                fullModel: root.clientDirectoryNameOptions
                editText: root.selectedClientName

                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                onEditTextChanged: {
                    if (profileClientCombo.activeFocus) {
                        root.selectedClientName = editText
                    }
                    if (editText.length <= 0) {
                        root.selectedClientId = ""
                    }
                }
                onActivated: root.selectedClientName = editText

                Connections {
                    target: root
                    function onSelectedClientNameChanged() {
                        if (!profileClientCombo.activeFocus && profileClientCombo.editText !== root.selectedClientName) {
                            profileClientCombo.editText = root.selectedClientName
                        }
                    }
                }

                onFullModelChanged: {
                    if (root.selectedClientName.length > 0) {
                        Qt.callLater(function() {
                            if (profileClientCombo.editText !== root.selectedClientName) {
                                profileClientCombo.editText = root.selectedClientName
                            }
                        })
                    }
                }

                Connections {
                    target: profileClientCombo
                    function onModelChanged() {
                        if (root.selectedClientName.length > 0) {
                            Qt.callLater(function() {
                                if (profileClientCombo.editText !== root.selectedClientName) {
                                    profileClientCombo.editText = root.selectedClientName
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
                onClicked: root.loadSelectedClientProfile(profileClientCombo.editText)
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Edit Client"
                primary: true
                Layout.preferredWidth: root.ratioPxW(0.102, 94)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.editSelectedClientInWizard()
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Directory"
                primary: false
                Layout.preferredWidth: root.ratioPxW(0.088, 80)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.gotoNode("A01")
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
                text: "Statement of Account"
                primary: false
                visible: root.selectedClientId.length > 0
                Layout.preferredWidth: root.ratioPxW(0.14, 150)
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.gotoNode("D17")
            }
        }

        Text {

            text: String(root.profileLookupMessage || "Select and load a client profile.")
            color: SemanticTheme.inkMuted(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
            elide: Text.ElideRight
        }

        RowLayout {
            id: mainBodyLayout
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: root.ratioPxW(0.015, 12)

            ScrollView {
                id: clientProfileDetailsScroll
                Layout.preferredWidth: clientProfilePanel.width * 0.58
                Layout.fillWidth: true
                Layout.fillHeight: true

                clip: true
                contentWidth: availableWidth
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: Math.max(1, clientProfileDetailsScroll.availableWidth)
                    spacing: root.ratioPx(0.006, 4)

                    Repeater {
                        model: root.clientProfileRowModel()
                        delegate: RowLayout {
                            required property var modelData

                            Layout.alignment: Qt.AlignTop
                            spacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct * 0.72, 8)

                            readonly property real cardWidth: Math.max(
                                1,
                                (clientProfileDetailsScroll.availableWidth - spacing) / 2
                            )

                            Rectangle {
                                id: leftCard
                                property var entry: modelData.left

                                Layout.preferredWidth: parent.cardWidth
                                Layout.alignment: Qt.AlignTop
                                implicitHeight: entry
                                    ? leftValueText.implicitHeight
                                        + leftLabelText.implicitHeight
                                        + (entry.multiline ? root.ratioPx(0.020, 18) : root.ratioPx(0.014, 12))
                                    : 1
                                Layout.minimumHeight: entry
                                    ? (entry.multiline ? root.ratioPxH(0.100, 74) : root.ratioPxH(0.070, 52))
                                    : 1
                                radius: Math.max(5, root.sectionRadiusPx - 3)
                                color: entry
                                    ? SemanticTheme.alpha(root._panel, 0.66)
                                    : "transparent"
                                border.width: entry ? 1 : 0
                                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                                ColumnLayout {
                                    visible: !!leftCard.entry
                                    anchors.fill: parent
                                    anchors.margins: root.ratioPx(0.0065, 6)
                                    spacing: root.ratioPx(0.0028, 2)

                                    Text {
                                        id: leftLabelText

                                        text: String(leftCard.entry && leftCard.entry.label ? leftCard.entry.label : "")
                                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
                                        font.weight: Font.DemiBold
                                        wrapMode: Text.NoWrap
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        id: leftValueText

                                        text: String(leftCard.entry && leftCard.entry.value ? leftCard.entry.value : "[blank]")
                                        elide: Text.ElideNone
                                        Layout.fillWidth: true
                                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }

                            Rectangle {
                                id: rightCard
                                property var entry: modelData.right

                                Layout.preferredWidth: parent.cardWidth
                                Layout.alignment: Qt.AlignTop
                                implicitHeight: entry
                                    ? rightValueText.implicitHeight
                                        + rightLabelText.implicitHeight
                                        + (entry.multiline ? root.ratioPx(0.020, 18) : root.ratioPx(0.014, 12))
                                    : 1
                                Layout.minimumHeight: entry
                                    ? (entry.multiline ? root.ratioPxH(0.100, 74) : root.ratioPxH(0.070, 52))
                                    : 1
                                radius: Math.max(5, root.sectionRadiusPx - 3)
                                color: entry
                                    ? SemanticTheme.alpha(root._panel, 0.66)
                                    : "transparent"
                                border.width: entry ? 1 : 0
                                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                                ColumnLayout {
                                    visible: !!rightCard.entry
                                    anchors.fill: parent
                                    anchors.margins: root.ratioPx(0.0065, 6)
                                    spacing: root.ratioPx(0.0028, 2)

                                    Text {
                                        id: rightLabelText

                                        text: String(rightCard.entry && rightCard.entry.label ? rightCard.entry.label : "")
                                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
                                        font.weight: Font.DemiBold
                                        wrapMode: Text.NoWrap
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        id: rightValueText

                                        text: String(rightCard.entry && rightCard.entry.value ? rightCard.entry.value : "[blank]")
                                        elide: Text.ElideNone
                                        Layout.fillWidth: true
                                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: relatedMattersContainer
                Layout.preferredWidth: clientProfilePanel.width * 0.40
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.sectionRadiusPx
                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.4)
                border.width: 1
                border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.14)
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: root.ratioPx(root.scaleRatios.descPadPct, 8)
                    spacing: root.ratioPx(0.005, 4)

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Related Matters"
                            font.bold: true
                            font.pixelSize: root.ratioPx(0.0125, 12.5)
                            color: root.appStyle === "Professional" ? root.proInk : root._text
                        }
                        Item { Layout.fillWidth: true }
                        PillButton {
                            t: root.t
                            metrics: root.responsiveMetrics
                            sfxBus: root.sfxBus
                            text: "+ New Matter"
                            Layout.preferredHeight: root.fieldHeightPx * 0.8
                            Layout.preferredWidth: root.ratioPxW(0.1, 90)
                            onClicked: {
                                root.initializeNewMatterWithClient(root.selectedClientName)
                            }
                        }
                    }

                    Text {
                        text: "Matters found: " + String(clientProfilePanel.relatedMatters.length)
                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.9, root.metricFloor("fontFloorLabelPx", 8))
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: root.sectionRadiusPx
                        color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.6)
                        border.width: 1
                        border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.12)
                        clip: true

                        ListView {
                            id: relatedMattersList
                            anchors.fill: parent
                            anchors.margins: root.ratioPx(root.scaleRatios.descPadPct, 8)
                            model: clientProfilePanel.relatedMatters
                            spacing: root.ratioPx(0.0035, 3)

                            delegate: Rectangle {
                                id: relatedMatterRow
                                required property var modelData
                                width: relatedMattersList.width
                                height: root.fieldHeightPx * 1.1
                                radius: Math.max(5, root.sectionRadiusPx - 3)
                                color: tapHandler.pressed
                                    ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.25)
                                    : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.70)
                                border.width: 1
                                border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.12)

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: root.ratioPx(0.006, 6)
                                    spacing: root.ratioPx(0.001, 1)

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: String(modelData.matterNumber || "[no number]")
                                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.60)
                                            font.pixelSize: root.ratioPx(0.009, root.metricFloor("fontFloorLabelPx", 8))
                                            font.bold: true
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: String(modelData.role || "Client")
                                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.8)
                                            font.pixelSize: root.ratioPx(0.0085, root.metricFloor("fontFloorLabelPx", 8))
                                            font.bold: true
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            Layout.fillWidth: true
                                            text: String(modelData.displayName || modelData.matterName || "")
                                            color: root.appStyle === "Professional" ? root.proInk : root._text
                                            font.pixelSize: root.ratioPx(0.011, 11)
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: String(modelData.status || "")
                                            color: modelData.status === "Open" || modelData.status === "Active"
                                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.5)
                                            font.pixelSize: root.ratioPx(0.0095, root.metricFloor("fontFloorLabelPx", 8))
                                        }
                                    }
                                }

                                TapHandler {
                                    id: tapHandler
                                    onDoubleTapped: {
                                        root.openMatterProfileFromDirectory(modelData)
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        text: "Tip: Double-click a matter to open its Matter Profile 360."
                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.5)
                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 0.8, root.metricFloor("fontFloorLabelPx", 8))
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
