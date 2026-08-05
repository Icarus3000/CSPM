pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property string appStyle: "Professional"
    property var tabs: []
    property var favorites: []
    property string activeTabId: ""
    property bool interactive: true

    signal tabActivated(string tabId)
    signal tabCloseRequested(string tabId)
    signal tabOpenInNewWindowRequested(string tabId)
    signal tabPinRequested(string tabId)
    signal tabReordered(int fromIndex, int toIndex)
    signal tabDuplicateRequested(string tabId)
    signal tabFavoriteRequested(string tabId)

    color: SemanticTheme.tabStripBackground(root.t, root.appStyle)
    border.width: 0
    clip: true

    DelegateModel {
        id: visualModel
        model: root.tabs || []
        delegate: DropArea {
            id: delegateRoot
            required property var modelData
            width: tabButtonContainer.width
            height: tabButtonContainer.height
            keys: ["tab"]

            onEntered: function(drag) {
                var fromIdx = drag.source.visualIndex
                var toIdx = delegateRoot.visualIndex
                if (fromIdx !== toIdx) {
                    visualModel.items.move(fromIdx, toIdx)
                    root.tabReordered(fromIdx, toIdx)
                }
            }

            property int visualIndex: DelegateModel.itemsIndex

            Rectangle {
                id: tabButtonContainer
                width: tabButton.width
                height: tabButton.height
                color: "transparent"

                Rectangle {
                    id: tabButton
                    readonly property string tabId: String(modelData.id || "")
                    readonly property bool active: tabId === root.activeTabId
                    readonly property bool hovered: tabHover.containsMouse
                    readonly property bool dirty: !!modelData.dirty

                    width: Math.max(116, Math.min(216, tabLabel.implicitWidth + closeGlyph.width + 36))
                    height: 28
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 3
                    color: active
                        ? SemanticTheme.tabSelectedBackground(root.t, root.appStyle)
                        : (hovered ? SemanticTheme.tabHoverBackground(root.t, root.appStyle) : "transparent")
                    border.width: 1
                    border.color: active
                        ? SemanticTheme.borderStrong(root.t, root.appStyle)
                        : (hovered ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "transparent")

                    Rectangle {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 2
                        height: parent.height - 12
                        radius: 1
                        color: tabButton.active ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "transparent"
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 7
                        spacing: 5
                        z: 2

                        Text {
                            id: dirtyDot
                            text: tabButton.dirty ? "\u2022" : ""
                            visible: tabButton.dirty
                            font.family: "Segoe UI"
                            font.pixelSize: 9
                            font.weight: Font.Medium
                            color: SemanticTheme.accentPrimary(root.t, root.appStyle)
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            id: pinGlyph
                            text: modelData.pinned ? "\uE840" : ""
                            visible: modelData.pinned
                            font.family: "Segoe MDL2 Assets"
                            font.pixelSize: 10
                            color: SemanticTheme.inkSubtle(root.t, root.appStyle)
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            id: tabLabel
                            Layout.fillWidth: true
                            text: String(modelData.title || "Workspace")
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: tabButton.active || tabButton.hovered
                                ? SemanticTheme.inkPrimary(root.t, root.appStyle)
                                : SemanticTheme.inkMuted(root.t, root.appStyle)
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                        }

                        Text {
                            id: closeGlyph
                            text: "\uE8BB"
                            font.family: "Segoe MDL2 Assets"
                            font.pixelSize: 9
                            font.weight: Font.Normal
                            color: closeHover.containsMouse
                                ? SemanticTheme.inkPrimary(root.t, root.appStyle)
                                : SemanticTheme.inkMuted(root.t, root.appStyle)
                            Layout.alignment: Qt.AlignVCenter

                            MouseArea {
                                id: closeHover
                                anchors.fill: parent
                                anchors.margins: -7
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.interactive) root.tabCloseRequested(tabButton.tabId)
                                }
                            }
                        }
                    }

                    DragHandler {
                        id: tabDrag
                        target: tabButtonContainer
                        xAxis.enabled: true
                        yAxis.enabled: false
                    }

                    MouseArea {
                        id: tabHover
                        anchors.fill: parent
                        z: 1
                        hoverEnabled: root.interactive
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
                        drag.target: tabDrag.active ? tabButtonContainer : null

                        property bool dragActive: tabDrag.active

                        onReleased: {
                            tabButtonContainer.x = 0
                            tabButtonContainer.y = 0
                        }

                        onClicked: function(mouse) {
                            if (!root.interactive) return
                            if (mouse.button === Qt.LeftButton) {
                                root.tabActivated(tabButton.tabId)
                            } else if (mouse.button === Qt.RightButton) {
                                globalTabContextMenu.targetTabId = tabButton.tabId
                                globalTabContextMenu.targetPinned = modelData.pinned
                                
                                var isFav = false
                                var checkId = String(modelData.nodeId || modelData.id || "")
                                var favs = root.favorites || []
                                for (var i = 0; i < favs.length; i++) {
                                    var favId = String(favs[i].nodeId || favs[i].id || "")
                                    if (favId === checkId && favs[i].moduleId === modelData.moduleId) {
                                        isFav = true
                                        break
                                    }
                                }
                                globalTabContextMenu.isFavorite = isFav
                                
                                globalTabContextMenu.popup()
                            }
                        }

                        Drag.active: tabDrag.active
                        Drag.source: delegateRoot
                        Drag.hotSpot.x: tabButtonContainer.width / 2
                        Drag.hotSpot.y: tabButtonContainer.height / 2
                        Drag.keys: ["tab"]

                        states: [
                            State {
                                when: tabHover.dragActive
                                ParentChange {
                                    target: tabButtonContainer
                                    parent: tabList
                                }
                                PropertyChanges {
                                    target: tabButtonContainer
                                    opacity: 0.8
                                    scale: 1.05
                                }
                            }
                        ]
                        transitions: [
                            Transition {
                                NumberAnimation { properties: "scale,opacity,x,y"; duration: 150 }
                            }
                        ]
                }
                }
            }
        }
    }
    
    ListView {
        id: tabList
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        orientation: ListView.Horizontal
        spacing: 4
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        model: visualModel

        move: Transition { NumberAnimation { properties: "x,y"; duration: 200 } }
        moveDisplaced: Transition { NumberAnimation { properties: "x,y"; duration: 200 } }
    }

    Menu {
        id: globalTabContextMenu
        property string targetTabId: ""
        property bool targetPinned: false
        property bool isFavorite: false

        MenuItem {
            text: "Open in new window"
            onTriggered: root.tabOpenInNewWindowRequested(globalTabContextMenu.targetTabId)
        }

        MenuItem {
            text: "Duplicate"
            onTriggered: root.tabDuplicateRequested(globalTabContextMenu.targetTabId)
        }

        MenuSeparator {}

        MenuItem {
            text: globalTabContextMenu.isFavorite ? "Remove from Favorites" : "Add to Favorites"
            onTriggered: root.tabFavoriteRequested(globalTabContextMenu.targetTabId)
        }

        MenuItem {
            text: globalTabContextMenu.targetPinned ? "Unpin tab" : "Pin tab"
            onTriggered: root.tabPinRequested(globalTabContextMenu.targetTabId)
        }

        MenuSeparator {}

        MenuItem {
            text: "Close"
            onTriggered: root.tabCloseRequested(globalTabContextMenu.targetTabId)
        }
    }
}
