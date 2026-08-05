import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: wizardOverlay
    anchors.fill: parent
    color: "#E6000000" // 90% opacity black
    z: 200
    
    // Prevent clicks from passing through
    MouseArea { anchors.fill: parent }
    
    SemanticTheme { id: theme }
    
    property var missingList: trayController.missingDescriptionEntries
    property int currentIndex: 0
    property var currentEntry: missingList && missingList.length > 0 && currentIndex < missingList.length ? missingList[currentIndex] : null
    
    // Auto-show when we have entries
    Connections {
        target: trayController
        function onPromptMissingDescriptions() {
            currentIndex = 0
            wizardOverlay.visible = true
            descInput.forceActiveFocus()
        }
    }
    
    Rectangle {
        width: 380
        height: 380
        anchors.centerIn: parent
        radius: theme.radiusLarge
        color: theme.background
        border.color: theme.border
        border.width: 1
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16
            
            Text {
                text: "Missing Descriptions (" + (currentIndex + 1) + " of " + (missingList ? missingList.length : 0) + ")"
                font.bold: true
                font.pixelSize: 18
                color: theme.textPrimary
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 8
            }
            
            Text {
                text: "Please provide a docket description before closing the application."
                font.pixelSize: 13
                color: theme.textSecondary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                Layout.bottomMargin: 8
            }
            
            // Context Box
            Rectangle {
                Layout.fillWidth: true
                height: 70
                color: theme.surface
                border.color: theme.border
                radius: theme.radiusSmall
                
                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: currentEntry ? currentEntry.client : ""; font.bold: true; font.pixelSize: 14; color: theme.textPrimary }
                    Text { text: currentEntry ? currentEntry.matter : ""; font.pixelSize: 13; color: theme.textSecondary }
                    Text { text: "Time: " + (currentEntry ? currentEntry.time : ""); font.pixelSize: 12; color: theme.accentBlue; font.bold: true }
                }
            }
            
            // Input
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                TextArea {
                    id: descInput
                    placeholderText: "Enter description..."
                    color: theme.textPrimary
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    background: Rectangle {
                        color: "transparent"
                        border.color: theme.border
                        radius: theme.radiusSmall
                    }
                    // Reset text when entry changes
                    onActiveFocusChanged: {
                        if (activeFocus && text === "") {
                            // Hack to force UI update if needed
                        }
                    }
                }
            }
            
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                
                Button {
                    text: "Cancel"
                    Layout.fillWidth: true
                    font.pixelSize: 14
                    font.bold: true
                    contentItem: Text { text: parent.text; color: theme.textSecondary; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "transparent"; border.color: theme.border; radius: theme.radiusSmall }
                    onClicked: {
                        wizardOverlay.visible = false
                    }
                }
                
                Button {
                    text: currentIndex === (missingList ? missingList.length - 1 : 0) ? "Save & Exit" : "Next"
                    Layout.fillWidth: true
                    font.pixelSize: 14
                    font.bold: true
                    enabled: descInput.text.trim().length > 0
                    opacity: enabled ? 1.0 : 0.5
                    contentItem: Text { text: parent.text; color: "white"; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: theme.accentBlue; radius: theme.radiusSmall }
                    onClicked: {
                        // Save the description
                        if (currentEntry) {
                            trayController.update_recorded_description(currentEntry.id, descInput.text)
                        }
                        
                        descInput.text = "" // clear for next
                        
                        if (currentIndex < missingList.length - 1) {
                            currentIndex++
                            descInput.forceActiveFocus()
                        } else {
                            // Done
                            wizardOverlay.visible = false
                            trayController.force_exit()
                        }
                    }
                }
            }
            
            Button {
                text: "Exit without saving descriptions"
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 12
                font.underline: true
                contentItem: Text { text: parent.text; color: theme.timerRed; font: parent.font; horizontalAlignment: Text.AlignHCenter }
                background: Item {}
                onClicked: {
                    wizardOverlay.visible = false
                    trayController.force_exit()
                }
            }
        }
    }
}
