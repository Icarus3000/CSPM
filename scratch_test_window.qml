import QtQuick
import "src/qml/views" as Views

Window {
    id: win
    width: 1400
    height: 900
    visible: true
    title: "Matter Wizard Test Layout"

    Views.PlaceholderSubmenuView {
        id: view
        anchors.fill: parent
        titleText: "Clients & Matters"
        appRef: app
        t: app.theme
        
        Component.onCompleted: {
            view.selectedMatterProfile = ({
                "matterId": "M-2025-001",
                "matterNumber": "M-2025-001",
                "matterName": "HKH Exit Planning",
                "displayName": "HKH Exit Planning",
                "clientName": "Litera Group",
                "parentName": "",
                "matterType": "General Consultation",
                "status": "Open",
                "practiceArea": "General",
                "responsibleLawyer": "Cory Schneider",
                "billingArrangement": "Hourly",
                "billingContact": "Cory Schneider",
                "billingEmail": "cory@litera.com",
                "defaultRate": "475",
                "defaultSharePct": "100.00",
                "rateHistory": "[]",
                "dateOfEngagement": "2026-06-08",
                "dateOpened": "2026-06-08",
                "dateClosed": "",
                "courtFileNumber": "Court File #12345",
                "opposingParty": "Opposing Party Inc.",
                "referralFrom": "Internal Referral",
                "description": "General description",
                "notes": "Matter notes"
            })
            view.editSelectedMatterInWizard()
        }
    }

    Timer {
        interval: 2500
        running: true
        repeat: false
        onTriggered: {
            console.log("Grabbing image...")
            win.contentItem.grabToImage(function(result) {
                console.log("Saving to logs/matter_wizard_repaired_layout.png")
                result.saveToFile("logs/matter_wizard_repaired_layout.png");
                Qt.quit();
            });
        }
    }
}
