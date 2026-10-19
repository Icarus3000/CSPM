import QtQuick
import QtQuick.Window
import Qt.labs.platform

Item {
    id: root

    property int resizeEdgeThickness: 6
    property int resizeCornerSize: 12

    function persistMiniPopupGeometry() {
        if (typeof trayController !== "undefined" && trayController && trayController.saveMiniPopupGeometry) {
            if (flyoutWindow.width >= flyoutWindow.minimumWidth && flyoutWindow.height >= flyoutWindow.minimumHeight) {
                trayController.saveMiniPopupGeometry(
                    flyoutWindow.x,
                    flyoutWindow.y,
                    flyoutWindow.width,
                    flyoutWindow.height
                )
            }
        }
    }

    function hideMiniPopup() {
        root.persistMiniPopupGeometry()
        flyoutWindow.hide()
    }

    Timer {
        id: geometrySaveDebounce
        interval: 250
        repeat: false
        onTriggered: root.persistMiniPopupGeometry()
    }

    Window {
        id: flyoutWindow
        objectName: "trayMiniPopupWindow"
        title: "CSPM Today's Dockets"
        flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        color: "transparent"
        width: 380
        height: 280
        minimumWidth: 320
        minimumHeight: 220

        onXChanged: {
            if (visible) geometrySaveDebounce.restart()
        }
        onYChanged: {
            if (visible) geometrySaveDebounce.restart()
        }
        onWidthChanged: {
            if (visible) geometrySaveDebounce.restart()
        }
        onHeightChanged: {
            if (visible) geometrySaveDebounce.restart()
        }

        Shortcut {
            sequences: ["Escape"]
            context: Qt.WindowShortcut
            onActivated: root.hideMiniPopup()
        }

        TrayTimekeepingFlyout {
            id: flyoutContent
            anchors.fill: parent
            onMinimizeRequested: root.hideMiniPopup()
        }

        // 8-Directional Edge & Corner Resize Zones
        // Top Edge
        MouseArea {
            objectName: "resizeTopEdge"
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.resizeCornerSize
            anchors.rightMargin: root.resizeCornerSize
            height: root.resizeEdgeThickness
            cursorShape: Qt.SizeVerCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.TopEdge)
            }
        }

        // Bottom Edge
        MouseArea {
            objectName: "resizeBottomEdge"
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.resizeCornerSize
            anchors.rightMargin: root.resizeCornerSize
            height: root.resizeEdgeThickness
            cursorShape: Qt.SizeVerCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.BottomEdge)
            }
        }

        // Left Edge
        MouseArea {
            objectName: "resizeLeftEdge"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: root.resizeCornerSize
            anchors.bottomMargin: root.resizeCornerSize
            width: root.resizeEdgeThickness
            cursorShape: Qt.SizeHorCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.LeftEdge)
            }
        }

        // Right Edge
        MouseArea {
            objectName: "resizeRightEdge"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: root.resizeCornerSize
            anchors.bottomMargin: root.resizeCornerSize
            width: root.resizeEdgeThickness
            cursorShape: Qt.SizeHorCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.RightEdge)
            }
        }

        // Top-Left Corner
        MouseArea {
            objectName: "resizeTopLeftCorner"
            anchors.top: parent.top
            anchors.left: parent.left
            width: root.resizeCornerSize
            height: root.resizeCornerSize
            cursorShape: Qt.SizeFDiagCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.TopLeftCorner)
            }
        }

        // Top-Right Corner
        MouseArea {
            objectName: "resizeTopRightCorner"
            anchors.top: parent.top
            anchors.right: parent.right
            width: root.resizeCornerSize
            height: root.resizeCornerSize
            cursorShape: Qt.SizeBDiagCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.TopRightCorner)
            }
        }

        // Bottom-Left Corner
        MouseArea {
            objectName: "resizeBottomLeftCorner"
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            width: root.resizeCornerSize
            height: root.resizeCornerSize
            cursorShape: Qt.SizeBDiagCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.BottomLeftCorner)
            }
        }

        // Bottom-Right Corner + Visual Resize Grip (⋱)
        MouseArea {
            objectName: "resizeBottomRightCorner"
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            width: root.resizeCornerSize + 2
            height: root.resizeCornerSize + 2
            cursorShape: Qt.SizeFDiagCursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                mouse.accepted = true
                flyoutWindow.startSystemResize(Qt.BottomRightCorner)
            }

            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 3
                anchors.bottomMargin: 1
                text: "⋱"
                font.pixelSize: 11
                color: "#64748B"
            }
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
            if (flyoutWindow.visible) {
                root.hideMiniPopup()
            } else {
                if (typeof trayController !== "undefined" && trayController && trayController.refreshTodayDockets) {
                    trayController.refreshTodayDockets()
                }
                flyoutWindow.width = Math.max(flyoutWindow.minimumWidth, w)
                flyoutWindow.height = Math.max(flyoutWindow.minimumHeight, h)
                flyoutWindow.x = x
                flyoutWindow.y = y
                flyoutWindow.flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                flyoutWindow.show()
                flyoutWindow.raise()
                flyoutWindow.requestActivate()
            }
        }

        function onPromptMissingDescriptions() {
            if (!flyoutWindow.visible) {
                trayController.calculate_flyout_geometry()
            } else {
                flyoutWindow.raise()
                flyoutWindow.requestActivate()
            }
        }

        function onLegacyDocketsSyncConflictDetected() {
            if (!flyoutWindow.visible) {
                trayController.calculate_flyout_geometry()
            } else {
                flyoutWindow.raise()
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
