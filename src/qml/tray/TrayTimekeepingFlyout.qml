import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: flyout
    width: 420
    height: 740
    radius: theme.radiusLarge
    color: theme.background
    
    SemanticTheme { id: theme }

    // Drop shadow
    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.margins: -10
        color: "#1A000000"
        radius: theme.radiusLarge + 5
        visible: false // Use MultiEffect or DropShadow in Qt6, simple fallback here
    }
    
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        
        // Header
        Rectangle {
            Layout.fillWidth: true
            height: 76
            color: "transparent"
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                
                // Icon
                Rectangle {
                    width: 40; height: 40; radius: theme.radiusMedium; color: theme.accentTeal
                    Text { anchors.centerIn: parent; text: "CS"; color: "white"; font.bold: true; font.pixelSize: 16 }
                }
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: "CSPM"; font.bold: true; font.pixelSize: 18; color: theme.textPrimary }
                    Text { text: trayController.currentDate; font.pixelSize: 13; color: theme.textSecondary }
                }
                
                // Replaced three dots button with spacing since it was redundant
                // (settings and exit are already in the bottom quick actions bar)
                Button {
                    text: "Open CSPM ⍈"
                    font.pixelSize: 13
                    font.bold: true
                    background: Rectangle {
                        color: "transparent"
                        border.color: theme.border
                        radius: theme.radiusMedium
                    }
                    onClicked: {
                        if (Window.window) Window.window.hide();
                        trayController.open_cspm();
                    }
                }
            }
        }
        
        // Custom Scrollable Area
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: contentColumn.height
            contentWidth: width
            clip: true
            ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
            
            Column {
                id: contentColumn
                width: parent.width
                
                // ACTIVE TIMERS HEADER
                Item {
                    width: parent.width; height: 48
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20
                        Text { text: "ACTIVE TIMERS"; font.bold: true; color: theme.accentBlue; font.pixelSize: 13; font.letterSpacing: 1 }
                        Rectangle {
                            width: 20; height: 20; radius: 10; color: theme.accentBlue
                            Text { anchors.centerIn: parent; text: trayController.activeTimers.length; color: "white"; font.pixelSize: 11; font.bold: true }
                        }
                    }
                }
                
                Repeater {
                    model: trayController.activeTimers
                    delegate: ActiveTimerRow { modelData: model.modelData; width: contentColumn.width }
                }
                
                Item {
                    width: parent.width; height: 48
                    Button {
                        anchors.left: parent.left; anchors.leftMargin: 20; anchors.verticalCenter: parent.verticalCenter
                        text: "+  Start New Timer"
                        font.pixelSize: 14; font.bold: true; 
                        contentItem: Text {
                            text: parent.text
                            color: theme.accentBlue
                            font: parent.font
                        }
                        background: Item {}
                        onClicked: timerOverlay.openOverlay()
                    }
                }
                
                Rectangle { width: parent.width; height: 1; color: theme.border }
                
                // RECORDED TODAY HEADER
                Item {
                    width: parent.width; height: 48
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20
                        Text { text: "RECORDED TODAY"; font.bold: true; color: theme.accentBlue; font.pixelSize: 13; font.letterSpacing: 1 }
                        Rectangle {
                            width: 20; height: 20; radius: 10; color: theme.accentBlue
                            Text { anchors.centerIn: parent; text: trayController.recordedEntries.length; color: "white"; font.pixelSize: 11; font.bold: true }
                        }
                        Item { Layout.fillWidth: true }
                        Text { text: "Total: " + trayController.recordedTodayFormatted; color: theme.accentBlue; font.pixelSize: 13; font.bold: true }
                    }
                }
                
                Repeater {
                    model: trayController.recordedEntries
                    delegate: RecordedTimeRow { modelData: model.modelData; width: contentColumn.width }
                }
                
                Item {
                    width: parent.width; height: 48
                    Button {
                        anchors.left: parent.left; anchors.leftMargin: 20; anchors.verticalCenter: parent.verticalCenter
                        text: "▶ View All Time Entries"
                        font.pixelSize: 14; font.bold: true
                        contentItem: Text {
                            text: parent.text
                            color: theme.accentBlue
                            font: parent.font
                        }
                        background: Item {}
                        onClicked: {
                            if (Window.window) Window.window.hide();
                            trayController.open_docket_activity_report();
                        }
                    }
                    Text {
                        anchors.right: parent.right; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter
                        text: ">"
                        font.pixelSize: 24; color: theme.textSecondary
                    }
                }
            }
        }
        
        DailyTimeSummary {}
        
        TrayQuickActions {
            onStartNewTimerRequested: timerOverlay.openOverlay()
        }
    }
    
    TimerCreationOverlay {
        id: timerOverlay
        visible: false
    }
    
    MissingDescriptionsWizard {
        id: missingDescriptionsWizard
        visible: false
    }
}
