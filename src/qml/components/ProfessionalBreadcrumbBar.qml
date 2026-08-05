pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property string appStyle: "Professional"
    property string moduleTitle: ""
    property string itemTitle: ""
    property string subtitle: ""
    property bool dirty: false

    color: SemanticTheme.pageBackground(root.t, root.appStyle)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        spacing: 1

        RowLayout {
            Layout.fillWidth: true
            spacing: 7

            Text {
                Layout.fillWidth: true
                text: {
                    var moduleText = String(root.moduleTitle || "Workspace")
                    var itemText = String(root.itemTitle || "")
                    return itemText.length > 0 ? (moduleText + " > " + itemText) : moduleText
                }
                font.family: "Segoe UI"
                font.pixelSize: 13
                font.weight: Font.Medium
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                elide: Text.ElideRight
            }

            Rectangle {
                visible: root.dirty
                Layout.preferredWidth: dirtyLabel.implicitWidth + 14
                Layout.preferredHeight: 20
                radius: 3
                color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                border.width: 1
                border.color: SemanticTheme.borderStrong(root.t, root.appStyle)

                Text {
                    id: dirtyLabel
                    anchors.centerIn: parent
                    text: "Unsaved"
                    font.family: "Segoe UI"
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: String(root.subtitle || "")
            font.family: "Segoe UI"
            font.pixelSize: 10
            color: SemanticTheme.inkMuted(root.t, root.appStyle)
            elide: Text.ElideRight
        }
    }
}
