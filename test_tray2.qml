import QtQuick; import Qt.labs.platform; Item { Component.onCompleted: { console.log("Tray available:", SystemTrayIcon.isSystemTrayAvailable); Qt.quit() } }
