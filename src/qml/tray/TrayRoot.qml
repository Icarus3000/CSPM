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
    }
}
