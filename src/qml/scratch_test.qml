import QtQuick 2.15
import QtQml.Models 2.15

Item {
    id: root
    property var myModel: [{id: 1, name: "A"}, {id: 2, name: "B"}, {id: 3, name: "C"}]

    DelegateModel {
        id: dm
        model: root.myModel
        delegate: Item {}
    }

    Component.onCompleted: {
        dm.items.move(0, 2)
        var out = []
        for (var i = 0; i < dm.items.count; i++) {
            var item = dm.items.get(i)
            out.push(item.model.modelData ? item.model.modelData.name : "FAIL")
        }
        console.log("Reordered: " + out.join(", "))
        Qt.quit()
    }
}
