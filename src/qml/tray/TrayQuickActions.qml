import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    Layout.fillWidth: true
    height: 80
    color: theme.background
    
    SemanticTheme { id: theme }
    
    signal startNewTimerRequested()
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 0
        
        ActionItem { text: "New Timer"; icon: "⊕"; onClicked: startNewTimerRequested() }
        ActionItem { text: "Time & Dockets"; icon: "📄"; onClicked: trayController.open_time_dockets() }
        ActionItem { text: "Reports"; icon: "📈"; onClicked: trayController.open_reports() }
        ActionItem { text: "Settings"; icon: "⚙"; onClicked: trayController.open_settings() }
        ActionItem { text: "Exit CSPM"; icon: "⏻"; textColor: theme.timerRed; onClicked: trayController.exit_cspm() }
    }
    
    component ActionItem: Item {
        id: actionItemRoot
        property string text: ""
        property string icon: ""
        property color textColor: theme.textSecondary
        signal clicked()
        
        Layout.fillWidth: true
        Layout.fillHeight: true
        
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 4
            Text { text: actionItemRoot.icon; font.pixelSize: 22; color: actionItemRoot.textColor; Layout.alignment: Qt.AlignHCenter }
            Text { text: actionItemRoot.text; font.pixelSize: 11; color: actionItemRoot.textColor; Layout.alignment: Qt.AlignHCenter }
        }
        
        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (actionItemRoot.text !== "New Timer" && Window.window) {
                    Window.window.hide()
                }
                actionItemRoot.clicked()
            }
        }
    }
}
