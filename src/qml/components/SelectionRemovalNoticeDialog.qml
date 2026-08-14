import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root

    property var t
    property string appStyle: "Professional"
    property int removedCount: 0
    property string scopeLabel: "record"
    property string reason: ""
    property string primaryColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property string panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property string textColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property string mutedColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    property string borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)

    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 520
    height: 272
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose

    function showRemoval(count, scope, explanation) {
        removedCount = Math.max(0, Number(count || 0))
        scopeLabel = String(scope || "record")
        reason = String(explanation || "The underlying records are no longer available in this list.")
        open()
    }

    background: Rectangle {
        color: root.panelColor
        border.color: root.borderColor
        border.width: 1
        radius: 8
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            text: "Selection changed"
            color: root.textColor
            font.pixelSize: 18
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: root.textColor
            font.pixelSize: 13
            text: "CSPM removed " + root.removedCount + " selected " + root.scopeLabel
                + (root.removedCount === 1 ? " because it" : "s because they")
                + " no longer appear in the current worklist."
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: root.mutedColor
            font.pixelSize: 13
            text: "Reason: " + root.reason
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: root.mutedColor
            font.pixelSize: 12
            text: "Selections remain fixed through filtering, sorting, and ordinary refreshes. Only records that actually leave this worklist are removed."
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: 110
                Layout.preferredHeight: 38
                radius: 6
                color: "transparent"
                border.color: root.borderColor
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "OK"
                    color: root.textColor
                    font.pixelSize: 13
                    font.weight: Font.Medium
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                }
            }
        }
    }
}
