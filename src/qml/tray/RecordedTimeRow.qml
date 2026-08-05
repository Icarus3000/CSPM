import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var modelData
    property bool isExpanded: false
    height: isExpanded ? 112 : 64
    
    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
    
    SemanticTheme { id: theme }
    
    clip: true
    
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            Layout.leftMargin: 20
            Layout.rightMargin: 16
            spacing: 16
            
            Text {
                text: modelData ? modelData.decimalHours.toFixed(1) + " h" : "0.0 h"
                font.bold: true
                font.pixelSize: 16
                color: theme.textPrimary
                Layout.preferredWidth: 64
            }
            
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: modelData ? modelData.clientName : ""; font.bold: true; font.pixelSize: 14; color: theme.textPrimary; elide: Text.ElideRight; Layout.fillWidth: true }
                Text { text: modelData ? modelData.matterName : ""; font.pixelSize: 13; color: theme.textSecondary; elide: Text.ElideRight; Layout.fillWidth: true }
            }
            
            Text {
                text: modelData ? modelData.timeStr : ""
                font.pixelSize: 13
                color: theme.textSecondary
            }
            
            // Restart Button
            Rectangle {
                width: 32; height: 32; radius: 4; border.color: theme.border; color: "transparent"
                Text { anchors.centerIn: parent; text: "▶"; font.pixelSize: 14; color: theme.timerGreen }
                MouseArea {
                    anchors.fill: parent
                    onClicked: if(modelData) trayController.restart_recorded_timer(modelData.id)
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
            color: "transparent"
            visible: isExpanded
            
            TextField {
                id: descField
                anchors.fill: parent
                anchors.margins: 4
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                placeholderText: "Add docket description..."
                
                font.pixelSize: 13
                color: theme.textPrimary
                selectByMouse: true
                background: Rectangle { color: theme.surface; border.color: theme.border; radius: theme.radiusSmall }
                
                Binding {
                    target: descField
                    property: "text"
                    value: modelData ? modelData.description : ""
                    when: !descField.activeFocus
                    restoreMode: Binding.RestoreNone
                }
                
                onTextEdited: {
                    if(modelData) {
                        trayController.update_recorded_description(modelData.entry_id, text);
                    }
                }
            }
        }
    }
    
    Rectangle { width: parent.width; height: 1; color: theme.border; anchors.bottom: parent.bottom }
}
