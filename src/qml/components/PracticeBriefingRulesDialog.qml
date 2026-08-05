pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Dialog {
    id: root

    property var t
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"

    signal filtersSaved()

    title: "Practice Briefing Rules"
    modal: true
    standardButtons: Dialog.Save | Dialog.Cancel
    width: 480

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)

    function loadFilters() {
        if (!root.appRef || !root.appRef.getPracticeBriefingFilters) return
        try {
            var payload = root.appRef.getPracticeBriefingFilters()
            if (!payload) return
            upcomingDaysField.text = String(payload.upcomingDeadlineDays || 14)
            includeOverdueTodaySwitch.checked = payload.includeOverdueDeadlinesInToday !== false
            overdueGraceField.text = String(payload.overdueBillGraceDays || 30)
            readyModeField.currentIndex = (String(payload.readyToBillMode || "") === "ready_only") ? 1 : 0
            minEntriesField.text = String(payload.readyToBillMinEntries || 1)
            minAgeField.text = String(payload.readyToBillMinAgeDays || 28)
            wipThresholdField.text = String(payload.considerBillingWipThreshold || 5000)
        } catch (e) {
        }
    }

    function saveFilters() {
        if (!root.appRef || !root.appRef.savePracticeBriefingFilters) return false
        var payload = {
            "upcomingDeadlineDays": Number(upcomingDaysField.text || 14),
            "includeOverdueDeadlinesInToday": includeOverdueTodaySwitch.checked,
            "overdueBillGraceDays": Number(overdueGraceField.text || 30),
            "readyToBillMode": readyModeField.currentIndex === 1 ? "ready_only" : "wip_and_ready",
            "readyToBillMinEntries": Number(minEntriesField.text || 1),
            "readyToBillMinAgeDays": Number(minAgeField.text || 28),
            "considerBillingWipThreshold": Number(wipThresholdField.text || 5000)
        }
        try {
            return !!root.appRef.savePracticeBriefingFilters(payload)
        } catch (e2) {
            return false
        }
    }

    onOpened: loadFilters()
    onAccepted: {
        if (saveFilters()) {
            root.filtersSaved()
        }
    }

    background: Rectangle {
        radius: visualRules.radiusPopup
        color: panelColor
        border.width: 1
        border.color: borderColor
    }

    contentItem: ColumnLayout {
        spacing: 10

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: mutedInkColor
            font.family: "Segoe UI"
            font.pixelSize: 12
            text: "Controls what Practice Briefing shows. Saved in your application settings."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 12
            rowSpacing: 10

            Text { text: "Upcoming deadline window (days)"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: upcomingDaysField; text: "14"; Layout.preferredWidth: 120 }

            Text { text: "Include overdue deadlines in Today"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Switch { id: includeOverdueTodaySwitch; checked: true }

            Text { text: "Overdue bill age (days)"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: overdueGraceField; text: "30"; Layout.preferredWidth: 120 }

            Text { text: "Consider billing mode"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            ComboBox {
                id: readyModeField
                Layout.preferredWidth: 220
                model: ["Any open WIP", "Ready for billing only"]
            }

            Text { text: "Minimum open WIP entries per matter"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: minEntriesField; text: "1"; Layout.preferredWidth: 120 }

            Text { text: "Minimum age since last billing (days)"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: minAgeField; text: "28"; Layout.preferredWidth: 120 }

            Text { text: "WIP threshold for consideration (CAD)"; color: inkColor; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: wipThresholdField; text: "5000"; Layout.preferredWidth: 120 }
        }
    }
}
