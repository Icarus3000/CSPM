pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property string appStyle: "Professional"
    property var drawerState: ({})
    property bool interactive: true
    readonly property bool drawerOpen: {
        if (!root.drawerState) return false
        if (root.drawerState.open !== undefined) return !!root.drawerState.open
        if (root.drawerState.visible !== undefined) return !!root.drawerState.visible
        return false
    }
    readonly property string titleText: {
        if (!root.drawerState) return "Details"
        return String(root.drawerState.title || root.drawerState.recordTitle || root.drawerState.label || "Details")
    }
    readonly property string subtitleText: {
        if (!root.drawerState) return ""
        return String(root.drawerState.subtitle || root.drawerState.status || "")
    }

    signal dismissed()

    width: 360
    visible: drawerOpen
    enabled: visible && interactive
    color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    border.width: 1
    border.color: SemanticTheme.borderStrong(root.t, root.appStyle)
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    text: root.titleText
                    font.family: "Segoe UI"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.subtitleText.length > 0
                    text: root.subtitleText
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                radius: 4
                color: closeHover.containsMouse ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "transparent"
                border.width: 1
                border.color: closeHover.containsMouse ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "x"
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                }

                MouseArea {
                    id: closeHover
                    anchors.fill: parent
                    hoverEnabled: root.interactive
                    cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (root.interactive) root.dismissed()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: SemanticTheme.borderSubtle(root.t, root.appStyle)
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Repeater {
                model: root.drawerState && root.drawerState.fields ? root.drawerState.fields : []

                delegate: RowLayout {
                    id: fieldRow
                    required property var modelData

                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        Layout.preferredWidth: 112
                        text: String(fieldRow.modelData.label || "")
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: String(fieldRow.modelData.value || "")
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        elide: Text.ElideRight
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
