import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    Layout.fillWidth: true
    height: 80
    color: theme.surface
    border.color: theme.border
    border.width: 1
    
    SemanticTheme { id: theme }
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            RowLayout {
                Text { text: "🕒"; font.pixelSize: 16; color: theme.accentBlue }
                Text { text: "Recorded Today"; color: theme.textSecondary; font.pixelSize: 12 }
            }
            Text { text: trayController.recordedTodayFormatted; color: theme.accentBlue; font.bold: true; font.pixelSize: 18 }
        }
        
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            RowLayout {
                Text { text: "⏱"; font.pixelSize: 16; color: theme.timerGreen }
                Text { text: "Active Now"; color: theme.textSecondary; font.pixelSize: 12 }
            }
            Text { text: trayController.activeNowFormatted; color: theme.timerGreen; font.bold: true; font.pixelSize: 18; font.family: "Consolas" }
        }
        
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            RowLayout {
                Text { text: "🕔"; font.pixelSize: 16; color: "#6A1B9A" }
                Text { text: "Total Today"; color: theme.textSecondary; font.pixelSize: 12 }
            }
            Text { text: trayController.totalTodayFormatted; color: "#6A1B9A"; font.bold: true; font.pixelSize: 18 }
        }
    }
}
