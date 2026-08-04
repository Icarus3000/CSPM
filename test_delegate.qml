import QtQuick
import QtQuick.Window
import QtQml.Models

Window {
    visible: true
    width: 200
    height: 200
    DelegateModel {
        id: dm
        model: [{title: "Hello"}, {title: "World"}]
        delegate: Text {
            required property var modelData
            text: modelData.title
        }
    }
    ListView { anchors.fill: parent; model: dm }
}
