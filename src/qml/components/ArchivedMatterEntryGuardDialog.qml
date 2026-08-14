pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root

    property var t
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property string entryKind: "time"
    property string matterId: ""
    property string matterNumber: ""
    property string matterName: ""
    property string expectedConfirmation: ""
    property int stage: 0
    property bool reopening: false
    property string errorText: ""

    signal entryConfirmed()

    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 560
    height: 390
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose

    readonly property color surface: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color inputSurface: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color muted: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)

    function entryLabel() {
        if (entryKind === "fee") return "fee"
        if (entryKind === "disbursement") return "client disbursement"
        return "time"
    }

    function matterLabel() {
        return matterNumber.length > 0 && matterName.length > 0
            ? matterNumber + " — " + matterName
            : (matterNumber || matterName || matterId)
    }

    function openFor(matter) {
        var row = matter || ({})
        matterId = String(row.matterId || row.MatterID || "").trim()
        matterNumber = String(row.matterNumber || row.MatterNumber || "").trim()
        matterName = String(row.matterName || row.MatterName || row.displayName || "").trim()
        expectedConfirmation = "REOPEN " + (matterNumber || matterId)
        stage = 0
        reopening = false
        errorText = ""
        confirmationInput.text = ""
        open()
    }

    function beginReopen() {
        if (reopening) return
        var phrase = String(confirmationInput.text || "").trim()
        if (phrase.toUpperCase() !== expectedConfirmation.toUpperCase()) {
            errorText = "Type exactly " + expectedConfirmation + " to continue."
            return
        }
        if (!appRef || !appRef.reopenMatterForDocketing) {
            errorText = "The protected matter re-open service is unavailable. Restart CSPM after installing the update."
            return
        }
        reopening = true
        errorText = ""
        var result = appRef.reopenMatterForDocketing(matterId, entryKind, phrase)
        reopening = false
        if (result && result.ok) {
            stage = 2
            return
        }
        errorText = String((result && result.message) || "The matter was not re-opened.")
    }

    background: Rectangle {
        color: root.surface
        border.color: root.border
        border.width: 1
        radius: 10
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            Layout.fillWidth: true
            text: root.stage === 0 ? "Archived matter" : (root.stage === 1 ? "Confirm re-open" : "Matter re-opened")
            color: root.ink
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: root.ink
            font.pixelSize: 14
            text: root.stage === 0
                ? root.matterLabel() + " is archived. No " + root.entryLabel() + " entry has been saved."
                : (root.stage === 1
                    ? "Re-opening the file makes it operational again. The re-open is saved in the matter audit notes; your " + root.entryLabel() + " entry still requires its own final confirmation."
                    : root.matterLabel() + " is now open. Review the retained " + root.entryLabel() + " entry and explicitly save it when ready.")
        }

        Text {
            Layout.fillWidth: true
            visible: root.stage === 0
            wrapMode: Text.WordWrap
            color: root.muted
            font.pixelSize: 13
            text: "This safeguard prevents new time, fee, and client-disbursement work from being posted accidentally to an archived matter."
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: root.stage === 1
            spacing: 8

            Text {
                text: "Type exactly " + root.expectedConfirmation
                color: root.ink
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            TextField {
                id: confirmationInput
                Layout.fillWidth: true
                Layout.preferredHeight: 42
                color: root.ink
                placeholderText: root.expectedConfirmation
                placeholderTextColor: root.muted
                background: Rectangle {
                    color: root.inputSurface
                    border.color: confirmationInput.activeFocus ? root.accent : root.border
                    radius: 6
                }
                onTextChanged: root.errorText = ""
            }
        }

        Text {
            Layout.fillWidth: true
            visible: root.errorText.length > 0
            wrapMode: Text.WordWrap
            color: "#C0392B"
            font.pixelSize: 12
            text: root.errorText
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 100
                Layout.preferredHeight: 38
                radius: 6
                color: "transparent"
                border.color: root.border
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: root.stage === 2 ? "Close" : "Cancel"
                    color: root.ink
                    font.pixelSize: 13
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: root.stage === 0 ? 178 : (root.stage === 1 ? 178 : 194)
                Layout.preferredHeight: 38
                radius: 6
                color: (!root.reopening && (root.stage !== 1 || String(confirmationInput.text || "").trim().length > 0))
                    ? SemanticTheme.buttonPrimary(root.t, root.appStyle)
                    : SemanticTheme.borderSubtle(root.t, root.appStyle)
                Text {
                    anchors.centerIn: parent
                    text: root.stage === 0
                        ? "Review re-open"
                        : (root.stage === 1
                            ? (root.reopening ? "Re-opening…" : "Re-open matter")
                            : "Confirm and save " + root.entryLabel())
                    color: (!root.reopening && (root.stage !== 1 || String(confirmationInput.text || "").trim().length > 0))
                        ? SemanticTheme.textOnPrimary(root.t, root.appStyle)
                        : root.muted
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: (!root.reopening && (root.stage !== 1 || String(confirmationInput.text || "").trim().length > 0))
                        ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (root.stage === 0) root.stage = 1
                        else if (root.stage === 1) root.beginReopen()
                        else {
                            root.close()
                            root.entryConfirmed()
                        }
                    }
                }
            }
        }
    }
}
