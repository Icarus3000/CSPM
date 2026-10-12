pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root
    objectName: "CSPMAboutDialog"
    property var t
    property string appStyle: "Professional"
    property var informationProvider: null
    property bool reducedMotion: false
    property var details: ({})
    property string copyStatus: ""
    readonly property color ink: SemanticTheme.ink(root.t, "popup", "neutral", root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property string versionText: [
        "Product: CSPM",
        "Version: " + (details.version || "Unavailable") + " (" + (details.codename || "Unavailable")
            + ", build " + (details.versionBuild || "Unavailable") + ")",
        "Source Git SHA: " + (details.sourceSha || "Unavailable"),
        "Source status: " + (details.sourceStatus || "Unavailable"),
        "Build UTC: " + (details.buildUtc || "Unavailable"),
        "Build local: " + (details.buildLocal || "Unavailable"),
        "Executable SHA-256: " + (details.executableSha256 || "Unavailable"),
        "Motion preference: " + (details.motionPreference || "Unavailable")
    ].join("\n\n")

    width: Math.min(720, parent ? Math.max(240, parent.width - 32) : 720)
    height: Math.min(580, parent ? Math.max(220, parent.height - 32) : 580)
    modal: true
    focus: true
    dim: true
    padding: 20
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: {
        copyStatus = ""
        details = informationProvider ? informationProvider.information(reducedMotion) : ({})
        copyButton.forceActiveFocus()
    }

    background: SemanticPanel {
        t: root.t
        appStyle: root.appStyle
        role: "popup"
        tone: "neutral"
        radius: 12
        borderWidth: 1
    }

    ColumnLayout {
        Accessible.name: "About CSPM"
        Accessible.role: Accessible.Dialog
        anchors.fill: parent
        spacing: 12
        Label {
            text: "About CSPM"
            color: root.ink
            font.pixelSize: 20
            font.bold: true
            Layout.fillWidth: true
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            TextArea {
                objectName: "CSPMAboutVersionText"
                text: root.versionText
                readOnly: true
                selectByMouse: true
                activeFocusOnTab: true
                wrapMode: TextEdit.WrapAnywhere
                color: root.ink
                selectionColor: root.accent
                selectedTextColor: SemanticTheme.readableInk(root.accent)
                font.pixelSize: 14
                background: null
                Accessible.name: "CSPM version information"
            }
        }
        Label {
            text: root.copyStatus
            color: root.ink
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            Accessible.name: root.copyStatus
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                id: copyButton
                objectName: "CSPMAboutCopyButton"
                text: "Copy version information"
                activeFocusOnTab: true
                Accessible.name: text
                onClicked: root.copyStatus = root.informationProvider
                    && root.informationProvider.copyVersionInformation(root.reducedMotion)
                    ? "Version information copied." : "Clipboard unavailable."
                contentItem: Text {
                    text: copyButton.text
                    color: root.ink
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.width: copyButton.activeFocus ? 2 : 1
                    border.color: copyButton.activeFocus ? root.accent : SemanticTheme.border(root.t, "popup", "neutral", root.appStyle)
                }
                padding: 12
            }
            Item { Layout.fillWidth: true }
            Button {
                id: closeButton
                text: "Close"
                activeFocusOnTab: true
                Accessible.name: "Close About CSPM"
                onClicked: root.close()
                contentItem: Text {
                    text: closeButton.text
                    color: root.ink
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.width: closeButton.activeFocus ? 2 : 1
                    border.color: closeButton.activeFocus ? root.accent : SemanticTheme.border(root.t, "popup", "neutral", root.appStyle)
                }
                padding: 12
            }
        }
    }
}
