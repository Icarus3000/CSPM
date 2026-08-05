import QtQuick
import QtQuick.Window

Window {
    width: 480
    height: 800
    visible: true
    title: "CSPM System Tray Prototype"
    color: "#2C2C2C"

    TrayTimekeepingFlyout {
        anchors.centerIn: parent
    }
}
