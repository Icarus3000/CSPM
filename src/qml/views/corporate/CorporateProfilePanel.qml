import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../standards"

Item {
    id: root
    property var activeWorkspace: null
    property string activeRecordId: ""
    property var startupParams: null
    property bool isDirty: false
    
    // Extracted from startupParams
    property string entityName: startupParams ? (startupParams.LegalName || "New Entity") : "New Entity"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Typography.spacingL
        spacing: Typography.spacingM

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Corporate Profile: " + root.entityName
                font.pixelSize: Typography.fontSizeH2
                font.weight: Typography.fontWeightBold
                color: Typography.textStrong
            }
            Item { Layout.fillWidth: true }
            
            Button {
                text: "Launch Diagram (Tapestry)"
                icon.name: "diagram" 
                onClicked: {
                    if (app && app.corporateController) {
                        var res = app.corporateController.launchTapestryDiagram(root.entityName)
                        if (app.toast) {
                            if (res.ok) {
                                app.toast.showInfo(res.message)
                            } else {
                                app.toast.showError(res.message)
                            }
                        }
                    }
                }
            }
            
            Button {
                text: "Save"
                onClicked: {
                    if (app && app.corporateController) {
                        var payload = {
                            "EntityID": root.activeRecordId || (root.startupParams && root.startupParams.EntityID ? root.startupParams.EntityID : ""),
                            "LegalName": fldLegalName.text,
                            "Jurisdiction": fldJurisdiction.text,
                            "IncorporationDate": fldIncorpDate.text,
                            "IncorporationNumber": fldIncNumber.text,
                            "FiscalYearEnd": fldFYE.text,
                            "Status": fldStatus.currentText,
                            "Notes": fldNotes.text
                        }
                        var res = app.corporateController.saveCorporateEntity(payload)
                        if (res.ok) {
                            root.activeRecordId = res.entityId
                            root.isDirty = false
                            if (app.toast) app.toast.showSuccess("Corporate entity saved successfully.")
                        } else {
                            if (app.toast) app.toast.showError("Failed to save: " + res.message)
                        }
                    }
                }
            }
        }
        
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Typography.bgLighter
            border.color: Typography.borderLight
            radius: Typography.radiusM
            
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                ColumnLayout {
                    width: parent.width - Typography.spacingL * 2
                    anchors.margins: Typography.spacingL
                    spacing: Typography.spacingL

                    Label {
                        text: "Tapestry integration is wired up. Clicking the button above exports data to CSV and launches the Tapestry application automatically."
                        wrapMode: Text.WordWrap
                        Layout.maximumWidth: 600
                        color: Typography.textMuted
                        font.italic: true
                    }
                    
                    GridLayout {
                        columns: 2
                        rowSpacing: Typography.spacingM
                        columnSpacing: Typography.spacingL
                        Layout.fillWidth: true

                        Label { text: "Legal Name" }
                        TextField { 
                            id: fldLegalName
                            Layout.fillWidth: true
                            text: root.entityName
                            onTextChanged: root.isDirty = true
                        }

                        Label { text: "Jurisdiction" }
                        TextField { 
                            id: fldJurisdiction
                            Layout.fillWidth: true
                            onTextChanged: root.isDirty = true
                        }

                        Label { text: "Incorporation Date" }
                        TextField { 
                            id: fldIncorpDate
                            Layout.fillWidth: true
                            placeholderText: "YYYY-MM-DD"
                            onTextChanged: root.isDirty = true
                        }

                        Label { text: "Incorporation Number" }
                        TextField { 
                            id: fldIncNumber
                            Layout.fillWidth: true
                            onTextChanged: root.isDirty = true
                        }

                        Label { text: "Fiscal Year End" }
                        TextField { 
                            id: fldFYE
                            Layout.fillWidth: true
                            onTextChanged: root.isDirty = true
                        }

                        Label { text: "Status" }
                        ComboBox {
                            id: fldStatus
                            Layout.fillWidth: true
                            model: ["Active", "Inactive", "Dissolved", "Amalgamated"]
                            onCurrentTextChanged: root.isDirty = true
                        }
                    }

                    Label { text: "Notes" }
                    TextArea {
                        id: fldNotes
                        Layout.fillWidth: true
                        Layout.minimumHeight: 100
                        wrapMode: Text.WordWrap
                        onTextChanged: root.isDirty = true
                    }
                    
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
