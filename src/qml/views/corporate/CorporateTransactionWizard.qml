import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../standards"

Item {
    id: root
    property var activeWorkspace: null
    property int currentStep: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Typography.spacingL

        Label {
            text: "Corporate Transaction Wizard"
            font.pixelSize: Typography.fontSizeH2
            font.weight: Typography.fontWeightBold
            color: Typography.textStrong
        }
        
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Typography.bgLighter
            border.color: Typography.borderLight
            radius: Typography.radiusM
            
            ColumnLayout {
                anchors.centerIn: parent
                spacing: Typography.spacingL
                
                Label {
                    text: "Wizard Step: " + currentStep
                    font.pixelSize: Typography.fontSizeH2
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
                
                StackLayout {
                    currentIndex: currentStep - 1
                    Layout.fillWidth: true
                    Layout.preferredHeight: 300
                    
                    // Step 1: Select Transaction Type
                    ColumnLayout {
                        spacing: Typography.spacingM
                        Label { text: "Select transaction type to apply to the corporate entity:" }
                        ComboBox {
                            id: txnTypeCombo
                            model: ["Share Issuance", "Dividend Declaration", "Stock Split", "Amalgamation", "Dissolution"]
                            Layout.fillWidth: true
                        }
                    }
                    
                    // Step 2: Select Entities
                    ColumnLayout {
                        spacing: Typography.spacingM
                        Label { text: "Select Target Entity:" }
                        ComboBox {
                            model: ["Beta Client", "TestCo", "Holdco"]
                            Layout.fillWidth: true
                        }
                        Label { text: "Select Counterparty (if applicable):" }
                        ComboBox {
                            model: ["None", "Beta Client", "TestCo", "Holdco"]
                            Layout.fillWidth: true
                        }
                    }
                    
                    // Step 3: Enter Details
                    ColumnLayout {
                        spacing: Typography.spacingM
                        Label { text: "Amount / Share Count:" }
                        TextField { Layout.fillWidth: true }
                        Label { text: "Effective Date:" }
                        TextField { Layout.fillWidth: true; placeholderText: "YYYY-MM-DD" }
                    }
                    
                    // Step 4: Confirm
                    ColumnLayout {
                        spacing: Typography.spacingM
                        Label { text: "Review the transaction details before applying." }
                        Label { 
                            text: "Type: " + txnTypeCombo.currentText + "\n" +
                                  "This will create a new corporate transaction record and a corresponding Tapestry layout step."
                        }
                    }
                }
                
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Button {
                        text: "Back"
                        enabled: currentStep > 1
                        onClicked: currentStep--
                    }
                    Button {
                        text: currentStep < 4 ? "Next" : "Apply Transaction"
                        onClicked: {
                            if (currentStep < 4) {
                                currentStep++
                            } else {
                                if (app && app.toast) {
                                    app.toast.showSuccess("Transaction Applied. Tapestry step generated.")
                                }
                                if (activeWorkspace) {
                                    activeWorkspace.closeCurrentTab()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
