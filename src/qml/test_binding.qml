import QtQuick 2.15

Item {
    property var myFavs: []
    property var testProp: myFavs

    Component.onCompleted: {
        var a = []
        a.push({ id: 1 })
        myFavs = a
        console.log("Length:", testProp.length)
    }
}
