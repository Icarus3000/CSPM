import QtQuick
import QtQuick.Window
import Qt.labs.platform

Item {
    id: root
    
    property real lastHideTime: 0

    Window {
        id: flyoutWindow
        flags: Qt.Popup | Qt.FramelessWindowHint
        color: "transparent"
        
        Shortcut {
            sequence: "Esc"
            onActivated: flyoutWindow.hide()
        }
        
        Connections {
            target: flyoutWindow
            function onActiveChanged() {
                if (!flyoutWindow.active && flyoutWindow.visible) {
                    root.lastHideTime = Date.now()
                    flyoutWindow.hide()
                }
            }
        }

        TrayTimekeepingFlyout {
            anchors.fill: parent
        }
    }

    Window {
        id: trayToastWindow
        flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
        color: "transparent"
        width: 350
        height: 58
        visible: false

        property string toastMessage: "CSPM is running in the background"

        Rectangle {
            id: toastBubble
            anchors.fill: parent
            anchors.margins: 4
            radius: 12
            color: "#0F172A"
            border.color: "#334155"
            border.width: 1
            opacity: 0.0

            SequentialAnimation {
                id: toastAnim
                running: false

                NumberAnimation {
                    target: toastBubble
                    property: "opacity"
                    from: 0.0
                    to: 0.96
                    duration: 220
                    easing.type: Easing.OutQuad
                }

                PauseAnimation {
                    duration: 3200
                }

                NumberAnimation {
                    target: toastBubble
                    property: "opacity"
                    from: 0.96
                    to: 0.0
                    duration: 650
                    easing.type: Easing.InQuad
                }

                onFinished: {
                    trayToastWindow.hide();
                }
            }

            Row {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12
                layoutDirection: Qt.LeftToRight

                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#2638BDF8"
                    border.color: "#6638BDF8"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "▲"
                        font.pixelSize: 11
                        color: "#38BDF8"
                    }
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    width: parent.width - 48

                    Text {
                        text: trayToastWindow.toastMessage
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        width: parent.width
                    }

                    Text {
                        text: "Click the system tray icon to restore"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        elide: Text.ElideRight
                        width: parent.width
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    toastAnim.stop();
                    toastBubble.opacity = 0.0;
                    trayToastWindow.hide();
                }
            }
        }
    }

    Connections {
        target: trayController
        function onFlyoutGeometryCalculated(x, y, w, h) {
            // If the window just hid due to losing focus from the user clicking the tray icon,
            // we ignore this re-open request so it acts like a true toggle.
            if (Date.now() - root.lastHideTime < 250) {
                return;
            }
            if (flyoutWindow.visible) {
                flyoutWindow.hide()
            } else {
                flyoutWindow.width = w
                flyoutWindow.height = h
                flyoutWindow.x = x
                flyoutWindow.y = y
                flyoutWindow.show()
                flyoutWindow.requestActivate()
            }
        }
        
        function onPromptMissingDescriptions() {
            if (!flyoutWindow.visible) {
                trayController.calculate_flyout_geometry()
            } else {
                flyoutWindow.requestActivate()
            }
        }

        function onShowTrayToast(msg) {
            if (msg && msg.length > 0) {
                trayToastWindow.toastMessage = msg;
            }
            // Position toast comfortably in the bottom-right above the system tray
            var screen = Qt.application.screens ? Qt.application.screens[0] : null;
            var sw = (screen && screen.width > 0) ? screen.width : 1920;
            var sh = (screen && screen.height > 0) ? screen.height : 1080;
            var sx = (screen && typeof screen.x === "number") ? screen.x : 0;
            var sy = (screen && typeof screen.y === "number") ? screen.y : 0;
            var usableH = (screen && screen.virtualGeometry && screen.virtualGeometry.height > 0) ? screen.virtualGeometry.height : (sh - 48);

            trayToastWindow.x = sx + sw - trayToastWindow.width - 20;
            trayToastWindow.y = sy + sh - trayToastWindow.height - 54;
            trayToastWindow.show();
            toastAnim.restart();
        }
    }
}
