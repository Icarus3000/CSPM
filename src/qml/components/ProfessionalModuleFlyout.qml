pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property string appStyle: "Professional"
    property var moduleData: null
    property string activeItemId: ""
    property bool interactive: true
    property var favorites: []

    signal itemRequested(var moduleData, var itemData)
    signal itemFavoriteRequested(var moduleData, var itemData, bool remove)
    signal dismissed()

    Menu {
        id: flyoutItemContextMenu
        property var targetModuleData: null
        property var targetItemData: null
        property bool isFavorite: {
            if (!targetItemData || !root.favorites) return false
            var checkId = targetItemData.nodeId || targetItemData.id || ""
            for (var i = 0; i < root.favorites.length; i++) {
                var favNodeId = root.favorites[i].nodeId || root.favorites[i].id || ""
                if (favNodeId === checkId && root.favorites[i].moduleId === targetModuleData.moduleId) {
                    return true
                }
            }
            return false
        }

        MenuItem {
            text: flyoutItemContextMenu.isFavorite ? "Remove from Favorites" : "Add to Favorites"
            onTriggered: {
                if (flyoutItemContextMenu.targetModuleData && flyoutItemContextMenu.targetItemData) {
                    root.itemFavoriteRequested(flyoutItemContextMenu.targetModuleData, flyoutItemContextMenu.targetItemData, flyoutItemContextMenu.isFavorite)
                }
            }
        }
    }

    width: 340
    height: parent ? parent.height : 640
    visible: !!moduleData
    enabled: visible && interactive

    Rectangle {
        anchors.fill: parent
        anchors.margins: 8
        radius: 6
        color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
        border.width: 1
        border.color: SemanticTheme.borderStrong(root.t, root.appStyle)
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: String(root.moduleData && root.moduleData.icon ? root.moduleData.icon : "")
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 22
                    color: SemanticTheme.accentPrimary(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        Layout.fillWidth: true
                        text: String(root.moduleData && root.moduleData.title ? root.moduleData.title : "Module")
                        font.family: "Segoe UI"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: String(root.moduleData && root.moduleData.subtitle ? root.moduleData.subtitle : "")
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
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.dismissed()
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: SemanticTheme.borderSubtle(root.t, root.appStyle)
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth

                ColumnLayout {
                    width: Math.max(1, parent.width)
                    spacing: 14

                    Repeater {
                        model: root.moduleData && root.moduleData.sections ? root.moduleData.sections : []

                        delegate: ColumnLayout {
                            id: sectionBlock
                            required property var modelData

                            width: parent ? parent.width : 1
                            spacing: 5

                            Text {
                                Layout.fillWidth: true
                                text: String(sectionBlock.modelData.title || "")
                                font.family: "Segoe UI"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                elide: Text.ElideRight
                            }

                            Repeater {
                                model: sectionBlock.modelData.displayItems || []

                                delegate: Rectangle {
                                    id: flyoutRow
                                    required property var modelData
                                    readonly property bool active: String(modelData.nodeId || modelData.id || "") === root.activeItemId
                                    readonly property bool hovered: flyoutHover.containsMouse

                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 34
                                    radius: 4
                                    color: active
                                        ? SemanticTheme.surfaceInput(root.t, root.appStyle)
                                        : (hovered ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "transparent")
                                    border.width: 1
                                    border.color: active
                                        ? SemanticTheme.borderStrong(root.t, root.appStyle)
                                        : (hovered ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "transparent")

                                    Text {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        verticalAlignment: Text.AlignVCenter
                                        text: String(flyoutRow.modelData.label || flyoutRow.modelData.title || "")
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                        font.weight: flyoutRow.active ? Font.DemiBold : Font.Medium
                                        color: flyoutRow.active || flyoutRow.hovered
                                            ? SemanticTheme.inkPrimary(root.t, root.appStyle)
                                            : SemanticTheme.inkMuted(root.t, root.appStyle)
                                        elide: Text.ElideRight
                                    }

                                    MouseArea {
                                        id: flyoutHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        onClicked: function(mouse) {
                                            if (mouse.button === Qt.RightButton) {
                                                flyoutItemContextMenu.targetModuleData = root.moduleData
                                                flyoutItemContextMenu.targetItemData = flyoutRow.modelData
                                                flyoutItemContextMenu.popup()
                                            } else {
                                                root.itemRequested(root.moduleData, flyoutRow.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
