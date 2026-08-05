import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var modelData
    property bool isExpanded: false
    height: isExpanded ? 120 : 72
    
    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
    
    SemanticTheme { id: theme }
    
    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        radius: theme.radiusMedium
        border.color: theme.border
        border.width: 1
        color: "transparent"
        clip: true
        
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                spacing: 16
                
                // Play Icon Circle
                Rectangle {
                    width: 36; height: 36; radius: 18
                    border.color: modelData && modelData.isRunning ? theme.timerGreen : theme.textSecondary
                    border.width: 2
                    color: "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: modelData && modelData.isRunning ? "▶" : "⏸"
                        color: modelData && modelData.isRunning ? theme.timerGreen : theme.textSecondary
                        font.pixelSize: 14
                        anchors.horizontalCenterOffset: modelData && modelData.isRunning ? 2 : 0
                    }
                }
                
                ColumnLayout {
                    spacing: 2
                    Text {
                        text: modelData ? trayController.formatElapsed(modelData.elapsedSeconds) : "00:00:00"
                        color: modelData && modelData.isRunning ? theme.timerGreen : theme.textSecondary
                        font.bold: true
                        font.pixelSize: 18
                        font.family: "Consolas" // fixed width
                    }
                    Text { 
                        text: modelData && modelData.isRunning ? "Running" : "Paused"
                        color: modelData && modelData.isRunning ? theme.timerGreen : theme.textSecondary
                        font.pixelSize: 12 
                    }
                }
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: modelData ? modelData.clientName : ""; font.bold: true; font.pixelSize: 14; color: theme.textPrimary; elide: Text.ElideRight; Layout.fillWidth: true }
                    Text { text: modelData ? modelData.matterName : ""; font.pixelSize: 13; color: theme.textSecondary; elide: Text.ElideRight; Layout.fillWidth: true }
                }
                
                // Pause/Play Button
                Rectangle {
                    width: 32; height: 32; radius: 4; border.color: theme.border; color: "transparent"
                    Text { anchors.centerIn: parent; text: modelData && modelData.isRunning ? "⏸" : "▶"; font.pixelSize: 14; color: theme.textPrimary }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if(modelData) {
                                if(modelData.isRunning) trayController.pause_timer(modelData.id);
                                else trayController.resume_timer(modelData.id);
                            }
                        }
                    }
                }
                
                // Stop Button
                Rectangle {
                    width: 32; height: 32; radius: 4; border.color: theme.border; color: "transparent"
                    Rectangle { anchors.centerIn: parent; width: 12; height: 12; color: theme.timerRed; radius: 2 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: if(modelData) trayController.stop_timer(modelData.id)
                    }
                }
                
                // Chevron
                Text {
                    text: "⌄"
                    font.pixelSize: 20
                    color: theme.textSecondary
                    rotation: isExpanded ? 180 : 0
                    Behavior on rotation { NumberAnimation { duration: 200 } }
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -10
                        onClicked: isExpanded = !isExpanded
                    }
                }
            }
            
            // Expanded Section (Description)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                color: theme.surface
                visible: isExpanded
                
                TextField {
                    id: descField
                    anchors.fill: parent
                    anchors.margins: 8
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    placeholderText: "Add docket description..."
                    
                    font.pixelSize: 13
                    color: theme.textPrimary
                    selectByMouse: true
                    background: Rectangle { color: "transparent"; border.color: "transparent" }
                    
                    Binding {
                        target: descField
                        property: "text"
                        value: modelData ? modelData.description : ""
                        when: !descField.activeFocus
                        restoreMode: Binding.RestoreNone
                    }
                    
                    onTextEdited: {
                        if(modelData) {
                            trayController.update_timer_description(modelData.id, text);
                        }
                    }
                }
            }
        }
    }
}
