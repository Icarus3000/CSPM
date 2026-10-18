pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../standards/SemanticTheme.js" as SemanticTheme

Dialog {
    id: root

    property var t
    property var controller: null
    property string appStyle: "Professional"
    property string saveError: ""
    property bool signInCodeCopied: false
    readonly property var agenda: root.controller && root.controller.snapshot ? root.controller.snapshot : ({})
    readonly property var configuration: root.controller && root.controller.configuration
        ? root.controller.configuration : ({})
    readonly property bool busy: root.controller ? !!root.controller.busy : false
    readonly property bool hasAccount: !!root.agenda.accountEmail
        && (root.agenda.state === "ready" || root.agenda.state === "partial")
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)

    title: "Microsoft 365 calendars"
    modal: true
    focus: true
    parent: Overlay.overlay
    width: Math.min(620, (root.parent ? root.parent.width : 680) - 32)
    height: Math.min(650, (root.parent ? root.parent.height : 730) - 32)
    x: root.parent ? (root.parent.width - width) / 2 : 0
    y: root.parent ? (root.parent.height - height) / 2 : 0
    padding: 18
    closePolicy: Popup.CloseOnEscape

    function loadConfiguration() {
        root.saveError = ""
        clientIdField.text = String(root.configuration.clientId || "")
        tenantIdField.text = String(root.configuration.tenantId || "organizations")
        accountEmailField.text = String(root.configuration.accountEmail || "")
        timeZoneField.text = String(root.configuration.timeZone || "America/Toronto")
        var sources = root.configuration.holidaySources || ({})
        var disabled = root.configuration.disabledCalendarIds || []
        canadaCheck.checked = sources.CA !== false && disabled.indexOf("holidays:CA") === -1
        unitedStatesCheck.checked = sources.US !== false && disabled.indexOf("holidays:US") === -1
        jewishCheck.checked = sources.JEWISH !== false && disabled.indexOf("holidays:JEWISH") === -1
    }

    function saveSettings() {
        if (!root.controller || !root.controller.saveConfiguration) return false
        var saved = root.controller.saveConfiguration({
            "clientId": clientIdField.text.trim(),
            "tenantId": tenantIdField.text.trim() || "organizations",
            "accountEmail": accountEmailField.text.trim(),
            "timeZone": timeZoneField.text.trim() || "America/Toronto",
            "disabledCalendarIds": (root.configuration.disabledCalendarIds || []).filter(function(value) {
                return String(value).indexOf("holidays:") !== 0
            }),
            "holidaySources": {
                "CA": canadaCheck.checked,
                "US": unitedStatesCheck.checked,
                "JEWISH": jewishCheck.checked
            }
        })
        root.saveError = saved ? "" : "Calendar settings could not be saved. Check the connection status below."
        return !!saved
    }

    function connectCalendarAccount() {
        if (root.controller && !root.busy && root.saveSettings()) root.controller.connectAccount()
    }

    function disconnectCalendarAccount() {
        if (root.controller && !root.busy) root.controller.disconnectAccount()
    }

    function cancelSignIn() {
        if (root.controller && root.controller.cancelConnection) root.controller.cancelConnection()
    }

    function setCalendarSelected(calendarId, enabled) {
        if (root.controller && !root.busy) root.controller.setCalendarEnabled(String(calendarId), enabled)
    }

    function copySignInCode() {
        var code = String(root.agenda.signInCode || "").trim()
        if (!code) {
            root.signInCodeCopied = false
            return false
        }
        var copied = false
        if (root.controller && root.controller.copyToClipboard)
            copied = !!root.controller.copyToClipboard(code)
        if (!copied && signInCodeField) {
            signInCodeField.selectAll()
            signInCodeField.copy()
            signInCodeField.deselect()
            copied = true
        }
        root.signInCodeCopied = copied
        return copied
    }

    function openMicrosoftSignIn() {
        root.copySignInCode()
        if (root.controller && root.agenda.signInUrl)
            root.controller.openEventLink(String(root.agenda.signInUrl))
    }

    onOpened: {
        root.loadConfiguration()
        if (root.agenda.signInCode)
            root.copySignInCode()
    }

    background: Rectangle {
        radius: 5
        color: SemanticTheme.surfacePanel(root.t, root.appStyle)
        border.width: 1
        border.color: root.borderColor
    }
    header: Text {
        text: root.title
        color: root.inkColor
        font.family: "Segoe UI"
        font.pixelSize: 19
        font.weight: Font.DemiBold
        padding: 18
        bottomPadding: 6
    }
    contentItem: ScrollView {
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.width
            spacing: 10

            Text {
                Layout.fillWidth: true
                text: "Read-only meetings across your available Microsoft 365 calendars, plus Canadian, U.S. and Jewish holidays."
                color: root.mutedInkColor
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
            Text {
                objectName: "calendarConnectionStatus"
                Layout.fillWidth: true
                text: String(root.agenda.message || "Set up Microsoft sign-in, then connect your account.")
                color: root.agenda.state === "error" || root.agenda.state === "partial"
                    ? SemanticTheme.tone(root.t, "warning", root.appStyle) : root.inkColor
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                visible: root.hasAccount
                text: "Connected account: " + String(root.agenda.accountEmail || "")
                color: root.mutedInkColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: signInColumn.implicitHeight + 20
                visible: !!root.agenda.signInCode
                color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                radius: 4
                onVisibleChanged: {
                    if (visible && root.agenda.signInCode)
                        root.copySignInCode()
                }
                ColumnLayout {
                    id: signInColumn
                    anchors.fill: parent
                    anchors.margins: 10
                    Text {
                        Layout.fillWidth: true
                        text: "Enter this code on Microsoft’s sign-in page:"
                        color: root.inkColor
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        TextEdit {
                            id: signInCodeField
                            objectName: "calendarSignInCode"
                            text: String(root.agenda.signInCode || "")
                            color: root.accentColor
                            font.pixelSize: 21
                            font.weight: Font.DemiBold
                            readOnly: true
                            selectByMouse: true
                            onTextChanged: {
                                if (text.trim().length > 0)
                                    root.copySignInCode()
                                else
                                    root.signInCodeCopied = false
                            }
                            TapHandler {
                                onTapped: root.copySignInCode()
                            }
                        }
                        Text {
                            objectName: "calendarSignInCodeCopiedLabel"
                            Layout.fillWidth: true
                            visible: !!root.agenda.signInCode && root.signInCodeCopied
                            text: "Copied to clipboard — press Ctrl+V on Microsoft’s page"
                            color: root.mutedInkColor
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }
                    PillButton {
                        objectName: "calendarMicrosoftSignInButton"
                        text: "Open Microsoft sign-in"
                        t: root.t
                        appStyle: root.appStyle
                        primary: true
                        Layout.preferredWidth: 190
                        Layout.preferredHeight: 34
                        onClicked: root.openMicrosoftSignIn()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PillButton {
                    objectName: "calendarConnectAccountButton"
                    text: root.hasAccount ? "Reconnect account" : "Connect account"
                    t: root.t
                    appStyle: root.appStyle
                    primary: true
                    Layout.preferredWidth: 146
                    Layout.preferredHeight: 34
                    enabled: !!root.controller && !root.busy && clientIdField.text.trim().length > 0
                    onClicked: root.connectCalendarAccount()
                }
                PillButton {
                    objectName: "calendarDisconnectAccountButton"
                    text: "Disconnect"
                    t: root.t
                    appStyle: root.appStyle
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 34
                    enabled: !!root.controller && !root.busy
                        && (!!root.configuration.clientId && !!root.configuration.accountEmail)
                    onClicked: root.disconnectCalendarAccount()
                }
                PillButton {
                    objectName: "calendarCancelSignInButton"
                    text: "Cancel sign-in"
                    visible: root.agenda.state === "signing-in"
                    t: root.t
                    appStyle: root.appStyle
                    Layout.preferredWidth: 112
                    Layout.preferredHeight: 34
                    enabled: !!root.controller
                    onClicked: root.cancelSignIn()
                }
                Text {
                    Layout.fillWidth: true
                    text: root.busy ? "Working…" : ""
                    color: root.mutedInkColor
                    font.pixelSize: 11
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Available calendars"
                color: root.inkColor
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Repeater {
                model: root.agenda.calendars || []
                delegate: CheckBox {
                    id: calendarCheck
                    required property var modelData
                    Layout.fillWidth: true
                    visible: String(calendarCheck.modelData.source || "").toLowerCase() !== "holiday"
                        && String(calendarCheck.modelData.id || "").indexOf("holidays:") !== 0
                    checked: calendarCheck.modelData.enabled !== false
                    text: String(calendarCheck.modelData.name || "Calendar")
                        + (calendarCheck.modelData.owner ? " · " + String(calendarCheck.modelData.owner) : "")
                    enabled: !root.busy
                    palette.windowText: root.inkColor
                    palette.text: root.inkColor
                    palette.highlight: root.accentColor
                    onClicked: root.setCalendarSelected(calendarCheck.modelData.id, checked)
                }
            }
            Text {
                Layout.fillWidth: true
                visible: !(root.agenda.calendars || []).length
                text: "Your Microsoft 365 calendars will appear after sign-in."
                color: root.mutedInkColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: "Supplemental holiday calendars"
                color: root.inkColor
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            CheckBox {
                id: canadaCheck
                objectName: "calendarCanadaHolidays"
                text: "Canadian holidays"
                checked: true
                enabled: !root.busy
                palette.windowText: root.inkColor
                palette.text: root.inkColor
                palette.highlight: root.accentColor
            }
            CheckBox {
                id: unitedStatesCheck
                objectName: "calendarUSHolidays"
                text: "U.S. holidays"
                checked: true
                enabled: !root.busy
                palette.windowText: root.inkColor
                palette.text: root.inkColor
                palette.highlight: root.accentColor
            }
            CheckBox {
                id: jewishCheck
                objectName: "calendarJewishHolidays"
                text: "Jewish holidays (diaspora)"
                checked: true
                enabled: !root.busy
                palette.windowText: root.inkColor
                palette.text: root.inkColor
                palette.highlight: root.accentColor
            }
            Text {
                Layout.fillWidth: true
                text: "Holiday changes take effect when you save. You can hide Microsoft holiday calendars above if you prefer these sources."
                color: root.mutedInkColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: root.agenda.calendars || []
                delegate: Text {
                    required property var modelData
                    Layout.fillWidth: true
                    visible: !!modelData.provider
                    text: String(modelData.name || "Calendar") + " · " + String(modelData.provider || "")
                    color: root.mutedInkColor
                    font.pixelSize: 10
                    wrapMode: Text.WordWrap
                }
            }
            Text {
                text: "Jewish holiday dates provided by Hebcal.com ›"
                color: root.accentColor
                font.pixelSize: 11
                TapHandler {
                    enabled: !!root.controller
                    onTapped: root.controller.openEventLink("https://www.hebcal.com/")
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Microsoft connection setup"
                color: root.inkColor
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "Register CSPM as a public desktop application in Microsoft Entra. Enable public client flows and delegated Calendars.Read and Calendars.Read.Shared permissions. Paste its Application (client) ID below. No client secret is needed. Your organization may require administrator consent."
                color: root.mutedInkColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            PillButton {
                text: "Microsoft registration guide"
                t: root.t
                appStyle: root.appStyle
                Layout.preferredWidth: 208
                Layout.preferredHeight: 30
                enabled: !!root.controller
                onClicked: root.controller.openEventLink("https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app")
            }
            ModernTextField {
                id: clientIdField
                objectName: "calendarClientIdField"
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                label: "Application (client) ID"
                placeholderText: "Microsoft Entra app registration ID"
                t: root.t
                appStyle: root.appStyle
                enabled: !root.busy
            }
            ModernTextField {
                id: accountEmailField
                objectName: "calendarAccountEmailField"
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                label: "Microsoft 365 account"
                placeholderText: "name@example.com"
                t: root.t
                appStyle: root.appStyle
                enabled: !root.busy
            }
            ModernTextField {
                id: tenantIdField
                objectName: "calendarTenantIdField"
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                label: "Tenant ID or domain (organizations by default)"
                text: "organizations"
                t: root.t
                appStyle: root.appStyle
                enabled: !root.busy
            }
            ModernTextField {
                id: timeZoneField
                objectName: "calendarTimeZoneField"
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                label: "Calendar timezone"
                text: "America/Toronto"
                t: root.t
                appStyle: root.appStyle
                enabled: !root.busy
            }
            Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.saveError
                color: SemanticTheme.tone(root.t, "error", root.appStyle)
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: root.agenda.errors || []
                delegate: Text {
                    required property var modelData
                    Layout.fillWidth: true
                    text: typeof modelData === "string" ? modelData
                        : String(modelData.message || modelData.calendar || "A calendar could not be refreshed.")
                    color: SemanticTheme.tone(root.t, "warning", root.appStyle)
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
    footer: RowLayout {
        spacing: 8
        Item { Layout.fillWidth: true }
        PillButton {
            objectName: "calendarSaveSettingsButton"
            text: "Save settings"
            t: root.t
            appStyle: root.appStyle
            primary: true
            Layout.preferredWidth: 118
            Layout.preferredHeight: 34
            enabled: !!root.controller && !root.busy
            onClicked: {
                if (root.saveSettings()) root.controller.refresh()
            }
        }
        PillButton {
            text: "Close"
            t: root.t
            appStyle: root.appStyle
            Layout.preferredWidth: 78
            Layout.preferredHeight: 34
            onClicked: root.close()
        }
    }
}
