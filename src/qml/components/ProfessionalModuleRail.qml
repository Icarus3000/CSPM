pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property string appStyle: "Professional"
    property var modules: []
    property var favorites: []
    property string activeModuleId: ""
    property string flyoutModuleId: ""
    property bool interactive: true

    signal moduleRequested(var moduleData)
    signal favoriteRequested(var favData)
    signal favoriteRemoveRequested(var favData)
    signal favoriteReordered(int fromIndex, int toIndex)
    signal moduleFavoriteRequested(var moduleData, bool remove)

    width: 56
    color: SemanticTheme.navigationBackground(root.t, root.appStyle)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 6

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 36
            Layout.preferredHeight: 34
            radius: 4
            color: "transparent"
            border.width: 1
            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

            Text {
                anchors.centerIn: parent
                text: "CS"
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.weight: Font.Medium
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: SemanticTheme.borderSubtle(root.t, root.appStyle)
        }

        Repeater {
            model: root.modules || []

            delegate: Rectangle {
                id: railButton
                required property var modelData
                readonly property string moduleId: String(modelData.moduleId || "")
                readonly property bool active: moduleId === root.activeModuleId
                readonly property bool flyoutActive: moduleId === root.flyoutModuleId
                readonly property bool hovered: railHover.containsMouse

                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 40
                Layout.preferredHeight: 38
                radius: 3
                color: active || flyoutActive
                    ? SemanticTheme.navigationSelectedBackground(root.t, root.appStyle)
                    : (hovered ? SemanticTheme.hoverOverlay(root.t, root.appStyle) : "transparent")
                border.width: 1
                border.color: active || flyoutActive
                    ? SemanticTheme.borderSubtle(root.t, root.appStyle)
                    : "transparent"

                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 2
                    height: parent.height - 16
                    radius: 1
                    color: railButton.active || railButton.flyoutActive
                        ? SemanticTheme.accentPrimary(root.t, root.appStyle)
                        : "transparent"
                }

                Text {
                    anchors.centerIn: parent
                    text: String(railButton.modelData.icon || "")
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 16
                    color: railButton.active || railButton.hovered || railButton.flyoutActive
                        ? SemanticTheme.inkPrimary(root.t, root.appStyle)
                        : SemanticTheme.inkMuted(root.t, root.appStyle)
                }

                MouseArea {
                    id: railHover
                    anchors.fill: parent
                    hoverEnabled: root.interactive
                    cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: function(mouse) {
                        if (!root.interactive) return
                        if (mouse.button !== Qt.RightButton) {
                            root.moduleRequested(railButton.modelData)
                        }
                    }
                }

                ToolTip {
                    visible: railHover.containsMouse
                    delay: 260
                    text: String(railButton.modelData.title || railButton.modelData.label || "")
                    x: railButton.width + 8
                    y: (railButton.height - 24) / 2
                }
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.topMargin: 4
            Layout.bottomMargin: 4
            color: SemanticTheme.borderSubtle(root.t, root.appStyle)
            visible: root.favorites && root.favorites.length > 0
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 16
            visible: root.favorites && root.favorites.length > 0
            Text {
                anchors.centerIn: parent
                text: "FAVS"
                font.family: "Segoe UI"
                font.pixelSize: 9
                font.weight: Font.Bold
                color: SemanticTheme.inkMuted(root.t, root.appStyle)
            }
        }

        DelegateModel {
            id: favVisualModel
            model: root.favorites || []
            delegate: DropArea {
                id: favDelegateRoot
                required property var modelData
                width: 40
                height: 44
                keys: ["fav"]

                property int visualIndex: DelegateModel.itemsIndex
                property int dragStartIndex: -1

                onEntered: function(drag) {
                    var fromIdx = drag.source.visualIndex
                    var toIdx = favDelegateRoot.visualIndex
                    if (fromIdx !== toIdx) {
                        if (drag.source.dragStartIndex === -1) {
                            drag.source.dragStartIndex = fromIdx
                        }
                        favVisualModel.items.move(fromIdx, toIdx)
                    }
                }

                Rectangle {
                    id: favButtonContainer
                    width: 40
                    height: 38
                    x: 0
                    y: Math.round((favDelegateRoot.height - 38) / 2)
                    color: "transparent"

                    Rectangle {
                        id: favButton
                        anchors.fill: parent
                        radius: 3
                        color: favHover.containsMouse ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "transparent"
                        border.width: 1
                        border.color: "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: String(favDelegateRoot.modelData.icon || "\uE82D") // Use document if no icon
                            font.family: "Segoe MDL2 Assets"
                            font.pixelSize: 16
                            color: favHover.containsMouse
                                ? SemanticTheme.inkPrimary(root.t, root.appStyle)
                                : SemanticTheme.inkMuted(root.t, root.appStyle)
                        }

                        MouseArea {
                            id: favHover
                            anchors.fill: parent
                            hoverEnabled: root.interactive
                            cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: function(mouse) {
                                if (!root.interactive) return
                                if (mouse.button === Qt.RightButton) {
                                    favContextMenu.targetFavData = favDelegateRoot.modelData
                                    favContextMenu.popup()
                                } else {
                                    root.favoriteRequested(favDelegateRoot.modelData)
                                }
                            }



                            property bool dragActive: favDrag.active

                            states: [
                                State {
                                    when: favHover.dragActive
                                    ParentChange {
                                        target: favButtonContainer
                                        parent: favList
                                    }
                                    PropertyChanges {
                                        target: favButtonContainer
                                        opacity: 0.8
                                        scale: 1.05
                                    }
                                }
                            ]
                            transitions: [
                                Transition {
                                    NumberAnimation { properties: "scale,opacity"; duration: 150 }
                                }
                            ]
                        }

                        ToolTip {
                            visible: favHover.containsMouse
                            delay: 260
                            text: String(favDelegateRoot.modelData.title || favDelegateRoot.modelData.label || "")
                            x: favButton.width + 8
                            y: (favButton.height - 24) / 2
                        }
                    }

                    Drag.active: favDrag.active
                    Drag.source: favDelegateRoot
                    Drag.hotSpot.x: favButtonContainer.width / 2
                    Drag.hotSpot.y: favButtonContainer.height / 2
                    Drag.keys: ["fav"]

                    DragHandler {
                        id: favDrag
                        target: favButtonContainer
                        xAxis.enabled: false
                        yAxis.enabled: true

                        onActiveChanged: {
                            if (!active) {
                                favButtonContainer.x = 0
                                favButtonContainer.y = Math.round((favDelegateRoot.height - favButtonContainer.height) / 2)
                                
                                if (favDelegateRoot.dragStartIndex !== -1 && favDelegateRoot.dragStartIndex !== favDelegateRoot.visualIndex) {
                                    root.favoriteReordered(favDelegateRoot.dragStartIndex, favDelegateRoot.visualIndex)
                                }
                                favDelegateRoot.dragStartIndex = -1
                            }
                        }
                    }
                }
            }
        }

        Menu {
            id: moduleContextMenu
            property var targetModuleData: null
            property bool isFavorite: {
                if (!targetModuleData || !root.favorites) return false
                for (var i = 0; i < root.favorites.length; i++) {
                    if (root.favorites[i].moduleId === targetModuleData.moduleId && root.favorites[i].tabType === "module") return true
                }
                return false
            }

            MenuItem {
                text: moduleContextMenu.isFavorite ? "Remove from Favorites" : "Add to Favorites"
                onTriggered: {
                    if (moduleContextMenu.targetModuleData) {
                        root.moduleFavoriteRequested(moduleContextMenu.targetModuleData, moduleContextMenu.isFavorite)
                    }
                }
            }
        }

        Menu {
            id: favContextMenu
            property var targetFavData: null

            MenuItem {
                text: "Remove from Favorites"
                onTriggered: {
                    if (favContextMenu.targetFavData) {
                        root.favoriteRemoveRequested(favContextMenu.targetFavData)
                    }
                }
            }
        }

        ListView {
            id: favList
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 40
            Layout.preferredHeight: (root.favorites ? root.favorites.length : 0) * 44
            interactive: false
            model: favVisualModel
            spacing: 0
            move: Transition {
                NumberAnimation { properties: "x,y"; duration: 150; easing.type: Easing.OutCubic }
            }
            displaced: Transition {
                NumberAnimation { properties: "x,y"; duration: 150; easing.type: Easing.OutCubic }
            }
        }

        Item { Layout.preferredHeight: 8 }
    }
}
