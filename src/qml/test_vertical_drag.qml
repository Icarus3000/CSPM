import QtQuick
import QtQuick.Controls
import QtQml.Models

ApplicationWindow {
    width: 300
    height: 400
    visible: true
    title: "Vertical Drag Test"

    property var myItems: [
        { id: "1", title: "Block 1" },
        { id: "2", title: "Block 2" },
        { id: "3", title: "Block 3" },
        { id: "4", title: "Block 4" }
    ]

    DelegateModel {
        id: visualModel
        model: myItems
        delegate: DropArea {
            id: delegateRoot
            required property var modelData
            width: 200
            height: 50
            keys: ["block"]

            property int visualIndex: DelegateModel.itemsIndex

            onEntered: function(drag) {
                console.log("[DRAG] onEntered fired. fromIdx:", drag.source.visualIndex, "toIdx:", delegateRoot.visualIndex)
                var fromIdx = drag.source.visualIndex
                var toIdx = delegateRoot.visualIndex
                if (fromIdx !== toIdx) {
                    console.log("[DRAG] Calling visualModel.items.move(" + fromIdx + ", " + toIdx + ")")
                    visualModel.items.move(fromIdx, toIdx)
                    
                    var arr = myItems || []
                    var item = arr.splice(fromIdx, 1)[0]
                    arr.splice(toIdx, 0, item)
                    console.log("[DRAG] Reassigning myItems array. Old reference: " + (myItems ? "exists" : "null"))
                    myItems = Array.from(arr)
                    console.log("[DRAG] Reassigned myItems array.")
                }
            }

            Rectangle {
                id: blockContainer
                width: 200
                height: 40
                y: 5

                Rectangle {
                    id: block
                    anchors.fill: parent
                    color: blockHover.containsMouse ? "lightblue" : "lightgray"
                    border.color: "black"

                    Text {
                        anchors.centerIn: parent
                        text: modelData.title
                    }
                    Component.onCompleted: console.log("[DELEGATE] Created: " + modelData.title + " at index: " + delegateRoot.visualIndex)
                    Component.onDestruction: console.log("[DELEGATE] Destroyed: " + modelData.title)

                    MouseArea {
                        id: blockHover
                        anchors.fill: parent
                        hoverEnabled: true

                        property bool dragActive: blockDrag.active

                        onReleased: {
                            console.log("[DRAG] onReleased fired for: " + modelData.title + ". Snapping back to 0, 5.")
                            blockContainer.x = 0
                            blockContainer.y = 5
                        }

                        states: [
                            State {
                                when: blockHover.dragActive
                                ParentChange {
                                    target: blockContainer
                                    parent: blockList
                                }
                                PropertyChanges {
                                    target: blockContainer
                                    opacity: 0.8
                                    scale: 1.05
                                }
                            }
                        ]
                    }
                }

                Drag.active: blockDrag.active
                Drag.source: delegateRoot
                Drag.hotSpot.x: blockContainer.width / 2
                Drag.hotSpot.y: blockContainer.height / 2
                Drag.keys: ["block"]

                DragHandler {
                    id: blockDrag
                    target: blockContainer
                    xAxis.enabled: false
                    yAxis.enabled: true
                }
            }
        }
    }

    ListView {
        id: blockList
        anchors.centerIn: parent
        width: 200
        height: 200
        interactive: false
        model: visualModel
        spacing: 0
        move: Transition { NumberAnimation { properties: "x,y"; duration: 150 } }
        displaced: Transition { NumberAnimation { properties: "x,y"; duration: 150 } }
    }
}
