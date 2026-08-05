pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    property var t
    property var windowRef
    property var sfxBus
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    
    property real basePadding: 24
    property color bgSurface: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color textColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color mutedColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    
    Rectangle {
        id: bgRect
        anchors.fill: parent
        color: bgSurface
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.basePadding
            spacing: 24
            
            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: "Draft Review Workspace"
                        font.pixelSize: 28
                        font.weight: Font.DemiBold
                        font.family: "Inter"
                        color: textColor
                    }
                    Text {
                        text: "Edit invoice details, apply courtesy discounts, and preview before finalizing."
                        font.pixelSize: 14
                        font.family: "Inter"
                        color: mutedColor
                    }
                }
                
                // Actions
                Rectangle {
                    width: 140
                    height: 40
                    radius: 8
                    color: "transparent"
                    border.color: borderColor
                    Text {
                        anchors.centerIn: parent
                        text: "Export to DOCX"
                        color: textColor
                        font.weight: Font.Medium
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                    }
                }
                
                Rectangle {
                    width: 140
                    height: 40
                    radius: 8
                    color: accentColor
                    Text {
                        anchors.centerIn: parent
                        text: "Finalize Invoice"
                        color: "#FFFFFF"
                        font.weight: Font.DemiBold
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                    }
                }
            }
            
            // Split Workspace
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 24
                
                // Left Panel: Interactive Editor
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 400
                    color: panelColor
                    radius: 12
                    border.color: borderColor
                    border.width: 1
                    
                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 20
                        contentWidth: availableWidth
                        
                        ColumnLayout {
                            width: parent.width
                            spacing: 24
                            
                            // Editor Header
                            Text {
                                text: "Invoice Editor"
                                font.pixelSize: 18
                                font.weight: Font.Medium
                                color: textColor
                            }
                            
                            // Editable Invoice Number
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { text: "Invoice Number (Override)"; color: mutedColor; font.pixelSize: 14 }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 44
                                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                    border.color: borderColor
                                    radius: 6
                                    TextInput {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: textColor
                                        text: "INV 26-0001"
                                        font.pixelSize: 14
                                    }
                                }
                            }
                            
                            // Editable Issue Date
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { text: "Issue Date (Override)"; color: mutedColor; font.pixelSize: 14 }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 44
                                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                    border.color: borderColor
                                    radius: 6
                                    TextInput {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: textColor
                                        text: "2026-06-30" // Placeholder for today's date
                                        font.pixelSize: 14
                                    }
                                }
                            }
                            
                            // Courtesy Discount
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { text: "Courtesy Discount"; color: mutedColor; font.pixelSize: 14 }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12
                                    Rectangle {
                                        Layout.preferredWidth: 100
                                        height: 44
                                        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                        border.color: borderColor
                                        radius: 6
                                        Text { anchors.centerIn: parent; text: "Percentage"; color: textColor }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 44
                                        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                        border.color: borderColor
                                        radius: 6
                                        TextInput {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            color: textColor
                                            text: "0.00"
                                            font.pixelSize: 14
                                        }
                                    }
                                }
                            }
                            
                            // Summary
                            Rectangle {
                                Layout.fillWidth: true
                                height: 120
                                color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                border.color: borderColor
                                radius: 8
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 8
                                    RowLayout { Layout.fillWidth: true; Text { text: "Subtotal:"; color: mutedColor; Layout.fillWidth: true }; Text { text: "$0.00"; color: textColor; font.weight: Font.Medium } }
                                    RowLayout { Layout.fillWidth: true; Text { text: "Discount:"; color: mutedColor; Layout.fillWidth: true }; Text { text: "$0.00"; color: textColor; font.weight: Font.Medium } }
                                    RowLayout { Layout.fillWidth: true; Text { text: "Tax:"; color: mutedColor; Layout.fillWidth: true }; Text { text: "$0.00"; color: textColor; font.weight: Font.Medium } }
                                    Rectangle { Layout.fillWidth: true; height: 1; color: borderColor }
                                    RowLayout { Layout.fillWidth: true; Text { text: "Total Due:"; color: textColor; font.weight: Font.Bold; Layout.fillWidth: true }; Text { text: "$0.00"; color: accentColor; font.weight: Font.Bold; font.pixelSize: 16 } }
                                }
                            }
                        }
                    }
                }
                
                // Right Panel: Live PDF Preview
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 600
                    color: SemanticTheme.surfaceApp(root.t, root.appStyle)
                    radius: 12
                    border.color: borderColor
                    border.width: 1
                    
                    Text {
                        anchors.centerIn: parent
                        text: "PDF Preview rendering..."
                        color: mutedColor
                        font.pixelSize: 14
                    }
                }
            }
        }
    }
}
