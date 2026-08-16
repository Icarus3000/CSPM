pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root

    property var t
    property var metrics
    property var appRef: null
    property var sfxBus: null
    property bool soundEnabled: true
    property bool keepTrayAlive: true
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: visualRules.isPro

    signal themeRequested()
    signal soundChanged(bool enabled)
    signal reportBrandingRequested()
    signal productivitySettingsRequested()
    signal backupRecoveryRequested()

    property color menuSurface: SemanticTheme.surface(root.t, "popup", "neutral", root.appStyle)
    property color menuInk: SemanticTheme.ink(root.t, "popup", "neutral", root.appStyle)
    property color menuBorder: SemanticTheme.border(root.t, "popup", "neutral", root.appStyle)
    property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color hoverFill: root.isProMode
        ? SemanticTheme.surfaceInput(root.t, root.appStyle)
        : SemanticTheme.alpha(root.menuInk, 0.08)
    property color inactiveFill: root.isProMode
        ? SemanticTheme.surfaceRaised(root.t, root.appStyle)
        : SemanticTheme.alpha(root.menuInk, 0.05)
    property color activeFill: root.isProMode
        ? SemanticTheme.accentPrimary(root.t, root.appStyle)
        : ((SemanticTheme.luma(root.accent) > 0.70)
            ? Qt.darker(root.accent, 1.14)
            : root.accent)
    property color activeInk: SemanticTheme.readableInk(root.activeFill)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function radiusFor(heightValue) {
        return root.isProMode ? visualRules.radiusControl : Math.max(1, Math.round(heightValue / 2))
    }

    function syncSoundFromApp() {
        var nextEnabled = true
        try {
            nextEnabled = !(root.appRef && root.appRef.soundEffectsEnabled === false)
        } catch (e) {
            nextEnabled = true
        }
        root.soundEnabled = nextEnabled
        if (root.sfxBus) {
            root.sfxBus.enabled = nextEnabled
        }
    }

    function setSoundEnabled(nextEnabled) {
        var enabled = !!nextEnabled
        var saved = true
        try {
            if (root.appRef && root.appRef.setSoundEffectsEnabled) {
                saved = root.appRef.setSoundEffectsEnabled(enabled)
            }
        } catch (e) {
            console.log("[SETTINGS] setSoundEffectsEnabled failed err=" + e)
            saved = false
        }
        root.soundEnabled = enabled
        if (root.sfxBus) {
            root.sfxBus.enabled = enabled
            if (enabled && root.sfxBus.playUiClick) {
                root.sfxBus.playUiClick("affirm", 0.36)
            }
        }
        root.soundChanged(enabled)
        return saved
    }

    function syncTrayPreferenceFromApp() {
        try {
            root.keepTrayAlive = !(root.appRef && root.appRef.keepTrayAlive === false)
        } catch (e) {
            root.keepTrayAlive = true
        }
    }

    function setKeepTrayAlive(nextEnabled) {
        var enabled = !!nextEnabled
        try {
            if (root.appRef) root.appRef.keepTrayAlive = enabled
        } catch (e) {
            console.log("[SETTINGS] keepTrayAlive update failed err=" + e)
            return false
        }
        root.keepTrayAlive = enabled
        return true
    }

    function openExpertPreview() {
        var opened = false
        try {
            if (root.appRef && root.appRef.openExpertPreview) {
                opened = root.appRef.openExpertPreview()
            }
        } catch (e) {
            console.log("[SETTINGS] openExpertPreview failed err=" + e)
            opened = false
        }
        return opened
    }

    function openExpertFlutterPreview() {
        var opened = false
        try {
            if (root.appRef && root.appRef.openExpertFlutterPreview) {
                opened = root.appRef.openExpertFlutterPreview()
            }
        } catch (e) {
            console.log("[SETTINGS] openExpertFlutterPreview failed err=" + e)
            opened = false
        }
        return opened
    }

    width: 320
    height: 780

    modal: true
    focus: true
    dim: false
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: {
        syncSoundFromApp()
        syncTrayPreferenceFromApp()
    }

    background: SemanticPanel {
        t: root.t
        appStyle: root.appStyle
        role: "popup"
        tone: "neutral"
        radius: root.isProMode ? visualRules.radiusPopup : 12
        borderWidth: 1
        shadowEnabled: visualRules.shadowOpacity > 0
        shadowRadius: root.isProMode ? 0 : 12
        shadowSamples: root.isProMode ? 0 : 18
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Settings"
            color: root.menuInk
            font.pixelSize: 16
            font.weight: Font.Bold
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignLeft
            elide: Text.ElideRight
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: SemanticTheme.alpha(root.menuInk, 0.14)
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            spacing: 12

            Text {
                text: "Sound"
                color: root.menuInk
                font.pixelSize: 14
                font.weight: Font.DemiBold
                Layout.preferredWidth: 68
                Layout.fillHeight: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }

            Rectangle {
                id: soundSwitch
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.radiusFor(height)
                color: root.inactiveFill
                border.width: 1
                border.color: SemanticTheme.alpha(root.menuInk, 0.22)

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 2
                    spacing: 2

                    Rectangle {
                        id: offOption
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: root.radiusFor(height)
                        color: !root.soundEnabled
                            ? root.activeFill
                            : (offMouse.containsMouse ? root.hoverFill : "transparent")

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 8
                            text: "Off"
                            color: !root.soundEnabled ? root.activeInk : root.menuInk
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            fontSizeMode: Text.Fit
                            minimumPixelSize: 7
                        }

                        MouseArea {
                            id: offMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.setSoundEnabled(false)
                        }
                    }

                    Rectangle {
                        id: onOption
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: root.radiusFor(height)
                        color: root.soundEnabled
                            ? root.activeFill
                            : (onMouse.containsMouse ? root.hoverFill : "transparent")

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 8
                            text: "On"
                            color: root.soundEnabled ? root.activeInk : root.menuInk
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            fontSizeMode: Text.Fit
                            minimumPixelSize: 7
                        }

                        MouseArea {
                            id: onMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.setSoundEnabled(true)
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            spacing: 12

            Text {
                text: "Close to tray"
                color: root.menuInk
                font.pixelSize: 14
                font.weight: Font.DemiBold
                Layout.preferredWidth: 116
                Layout.fillHeight: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }

            Rectangle {
                id: traySwitch
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.radiusFor(height)
                color: root.inactiveFill
                border.width: 1
                border.color: SemanticTheme.alpha(root.menuInk, 0.22)

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 2
                    spacing: 2

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: root.radiusFor(height)
                        color: !root.keepTrayAlive
                            ? root.activeFill
                            : (trayOffMouse.containsMouse ? root.hoverFill : "transparent")

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 8
                            text: "Off"
                            color: !root.keepTrayAlive ? root.activeInk : root.menuInk
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            id: trayOffMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.setKeepTrayAlive(false)
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: root.radiusFor(height)
                        color: root.keepTrayAlive
                            ? root.activeFill
                            : (trayOnMouse.containsMouse ? root.hoverFill : "transparent")

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 8
                            text: "On"
                            color: root.keepTrayAlive ? root.activeInk : root.menuInk
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            id: trayOnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.setKeepTrayAlive(true)
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: expertMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: expertMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Expert Web Preview"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: "Open"
                    color: root.menuInk
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    Layout.preferredWidth: 42
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: expertMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.openExpertPreview()) {
                        root.close()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: productivitySettingsMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: productivitySettingsMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Productivity Forecast"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: ">"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    Layout.preferredWidth: 12
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: productivitySettingsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.close()
                    root.productivitySettingsRequested()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: expertFlutterMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: expertFlutterMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Expert Flutter"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: "Launch"
                    color: root.menuInk
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    Layout.preferredWidth: 52
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: expertFlutterMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.openExpertFlutterPreview()) {
                        root.close()
                    }
                }
            }
        }


        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            radius: root.radiusFor(height)
            color: dataFolderSetupMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: dataFolderSetupMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "Data Folder Setup"
                        color: root.menuInk
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Text {
                        text: "Configure Shared and Local working folders"
                        color: SemanticTheme.alpha(root.menuInk, 0.6)
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                }

                Text {
                    text: "Configure"
                    color: root.menuInk
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    Layout.preferredWidth: 60
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: dataFolderSetupMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.appRef) {
                        root.appRef.promptDataFolderSetup()
                    }
                }
            }
        }
        
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            radius: root.radiusFor(height)
            color: backupMinsMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: backupMinsMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "Auto-Backup Interval (Minutes)"
                        color: root.menuInk
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Text {
                        text: (root.appRef && root.appRef.autoBackupMinutes) ? root.appRef.autoBackupMinutes + " mins" : "Disabled"
                        color: SemanticTheme.alpha(root.menuInk, 0.6)
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                }

                Text {
                    text: "Toggle"
                    color: root.menuInk
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    Layout.preferredWidth: 42
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: backupMinsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.appRef) {
                        if (root.appRef.autoBackupMinutes === 0) root.appRef.autoBackupMinutes = 15;
                        else if (root.appRef.autoBackupMinutes === 15) root.appRef.autoBackupMinutes = 60;
                        else if (root.appRef.autoBackupMinutes === 60) root.appRef.autoBackupMinutes = 240;
                        else root.appRef.autoBackupMinutes = 0;
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            radius: root.radiusFor(height)
            color: invDirMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: invDirMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "Invoice Root Folder"
                        color: root.menuInk
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Text {
                        text: (root.appRef && root.appRef.billing && root.appRef.billing.customInvoiceDir) ? root.appRef.billing.customInvoiceDir : "Not set (Smart Fallback)"
                        color: SemanticTheme.alpha(root.menuInk, 0.6)
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                }

                Text {
                    text: "Select"
                    color: root.menuInk
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    Layout.preferredWidth: 42
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: invDirMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.appRef && root.appRef.billing) {
                        root.appRef.billing.promptCustomInvoiceDir()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: themeMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: themeMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Theme"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: ">"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    Layout.preferredWidth: 12
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: themeMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.close()
                    root.themeRequested()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: reportBrandingMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: reportBrandingMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Report Branding"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: ">"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    Layout.preferredWidth: 12
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: reportBrandingMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.close()
                    root.reportBrandingRequested()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: motionFxMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: motionFxMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Motion FX Studio"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: ">"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    Layout.preferredWidth: 12
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: motionFxMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.close()
                    if (root.appRef && root.appRef.openMotionFxStudio) {
                        root.appRef.openMotionFxStudio()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: root.radiusFor(height)
            color: backupMouse.containsMouse ? root.hoverFill : root.inactiveFill
            border.width: 1
            border.color: backupMouse.containsMouse ? root.menuBorder : SemanticTheme.alpha(root.menuInk, 0.18)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: "Data, Backup & Recovery"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                Text {
                    text: ">"
                    color: root.menuInk
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    Layout.preferredWidth: 12
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: backupMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.close()
                    root.backupRecoveryRequested()
                }
            }
        }

        Item {
            Layout.fillHeight: true
        }
    }
}
