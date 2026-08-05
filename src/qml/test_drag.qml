import QtQuick
import QtQuick.Controls
import QtQml.Models

ApplicationWindow {
    width: 400
    height: 400
    visible: true
    title: "Test"

    property var myItems: [
        { name: "A", id: 1 },
        { name: "B", id: 2 },
        { name: "C", id: 3 }
    ]

    Column {
        anchors.fill: parent
        Button {
            objectName: "myButton"
            text: "Reorder"
            onClicked: {
                var arr = myItems.slice()
                var item = arr.splice(0, 1)[0]
                arr.splice(1, 0, item)
                myItems = Array.from(arr)
            }
        }
        
        ListView {
            width: 200
            height: 200
            model: DelegateModel {
                id: visualModel
                model: myItems
                delegate: Rectangle {
                    width: 100
                    height: 30
                    color: "lightblue"
                    border.color: "black"
                    Text { text: modelData.name }
                    Component.onCompleted: console.log("Created: " + modelData.name)
                    Component.onDestruction: console.log("Destroyed: " + modelData.name)
                }
            }
        }
    }
}
