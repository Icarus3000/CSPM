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
}
