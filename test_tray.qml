import QtQuick; import Qt.labs.platform; SystemTrayIcon { visible: true; icon.source: "file:///c:/Projects/__CSPM/src/assets/app_icon.ico"; tooltip: "Test"; onActivated: console.log("Activated") }
