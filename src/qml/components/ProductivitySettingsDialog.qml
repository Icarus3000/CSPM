pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: root

    title: "Productivity Settings"
    visible: false
    modality: Qt.NonModal
    width: 660
    height: 640
    minimumWidth: 600
    minimumHeight: 590

    property var parentWindow: null
    property var t
    property var appRef: null
    property var metrics
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property string statusText: ""
    property int weeksPerYear: 52
    property int savedBasisDays: 336

    readonly property color menuSurface: SemanticTheme.surface(root.t, "popup", "neutral", root.appStyle)
    readonly property color menuInk: SemanticTheme.ink(root.t, "popup", "neutral", root.appStyle)
    readonly property color menuBorder: SemanticTheme.border(root.t, "popup", "neutral", root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.alpha(root.menuInk, 0.72)
    readonly property int calculatedBasisDays: root.weeksPerYear * root.fieldNumber(workDaysField.text, 0)
        - root.fieldNumber(vacationField.text, 0)
        - root.fieldNumber(holidayField.text, 0)
        - root.fieldNumber(unavailableField.text, 0)
    readonly property bool calculatedBasisValid: root.calculatedBasisDays >= 1 && root.calculatedBasisDays <= 366
    readonly property int effectiveBasisDays: manualOverrideBox.checked
        ? root.fieldNumber(manualBasisField.text, 0) : root.calculatedBasisDays

    function fieldNumber(value, fallback) {
        var text = String(value || "").trim()
        return /^\d+$/.test(text) ? Number(text) : fallback
    }

    function validWholeNumber(value, minimum, maximum) {
        var text = String(value || "").trim()
        if (!/^\d+$/.test(text)) return false
        var number = Number(text)
        return number >= minimum && number <= maximum
    }

    function open() {
        loadSettings()
        visible = true
    }

    function close() {
        visible = false
    }

    function loadSettings() {
        statusText = ""
        var settings = null
        try {
            if (root.appRef && root.appRef.getProductivityForecastSettings) {
                settings = root.appRef.getProductivityForecastSettings()
            }
        } catch (e) {
            statusText = "Could not load Productivity settings."
        }
        if (!settings || !settings.ok) {
            settings = {
                "weeksPerYear": 52,
                "workDaysPerWeek": 5,
                "vacationDays": 0,
                "holidayDays": 0,
                "otherUnavailableDays": 0,
                "manualOverrideEnabled": true,
                "manualBasisDays": 336,
                "effectiveBasisDays": 336
            }
        }
        weeksPerYear = Number(settings.weeksPerYear || 52)
        workDaysField.text = String(settings.workDaysPerWeek)
        vacationField.text = String(settings.vacationDays)
        holidayField.text = String(settings.holidayDays)
        unavailableField.text = String(settings.otherUnavailableDays)
        manualOverrideBox.checked = settings.manualOverrideEnabled !== false
        manualBasisField.text = String(settings.manualBasisDays || settings.effectiveBasisDays || 336)
        savedBasisDays = Number(settings.effectiveBasisDays || 336)
        if (!statusText.length) {
            statusText = manualOverrideBox.checked
                ? "Your existing manual basis is retained until you choose the calculated schedule."
                : "Changes apply when you generate the next Productivity Report."
        }
    }

    function saveSettings() {
        if (!root.appRef || !root.appRef.setProductivityForecastSettings) {
            statusText = "Productivity settings backend unavailable."
            return false
        }
        if (!validWholeNumber(workDaysField.text, 1, 7)) {
            statusText = "Scheduled workdays per week must be between 1 and 7."
            return false
        }
        if (!validWholeNumber(vacationField.text, 0, 366)
                || !validWholeNumber(holidayField.text, 0, 366)
                || !validWholeNumber(unavailableField.text, 0, 366)) {
            statusText = "Vacation, holidays, and unavailable time must be whole scheduled workdays."
            return false
        }
        if (!calculatedBasisValid) {
            statusText = "Your schedule must leave between 1 and 366 planning days."
            return false
        }
        if (manualOverrideBox.checked && !validWholeNumber(manualBasisField.text, 1, 366)) {
            statusText = "Manual forecast basis must be between 1 and 366 days."
            return false
        }
        var result = root.appRef.setProductivityForecastSettings({
            "workDaysPerWeek": fieldNumber(workDaysField.text, 0),
            "vacationDays": fieldNumber(vacationField.text, 0),
            "holidayDays": fieldNumber(holidayField.text, 0),
            "otherUnavailableDays": fieldNumber(unavailableField.text, 0),
            "manualOverrideEnabled": manualOverrideBox.checked,
            "manualBasisDays": fieldNumber(manualBasisField.text, 0)
        })
        if (result && result.ok) {
            savedBasisDays = Number(result.effectiveBasisDays || result.basisDays || effectiveBasisDays)
            manualBasisField.text = String(result.manualBasisDays || manualBasisField.text)
            statusText = String(result.message || "Productivity settings saved.")
            return true
        }
        statusText = (result && result.message) ? String(result.message) : "Could not save Productivity settings."
        return false
    }

    Shortcut {
        sequence: "Escape"
        onActivated: root.close()
    }

    onVisibleChanged: {
        var window = root.parentWindow
        if (visible && window) {
            root.x = window.x + Math.max(0, Math.round((window.width - root.width) / 2))
            root.y = window.y + Math.max(0, Math.round((window.height - root.height) * 0.18))
        }
    }

    onClosing: function(closeEvent) {
        closeEvent.accepted = true
    }

    SemanticPanel {
        anchors.fill: parent
        t: root.t
        appStyle: root.appStyle
        role: "popup"
        tone: "neutral"
        radius: 0
        borderWidth: 0
        shadowRadius: 0
        shadowSamples: 0

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 11

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Productivity Settings"
                    color: root.menuInk
                    font.pixelSize: 21
                    font.bold: true
                    Layout.fillWidth: true
                }
                Button {
                    text: "Close"
                    Layout.preferredWidth: 84
                    onClicked: root.close()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: SemanticTheme.alpha(root.menuInk, 0.14)
            }

            Text {
                Layout.fillWidth: true
                text: "Forecast planning schedule"
                color: root.menuInk
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                text: "CSPM annualizes production from your scheduled working days, not calendar days. A vacation day means a day you normally would have worked."
                color: SemanticTheme.alpha(root.menuInk, 0.72)
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                rowSpacing: 8

                Text { text: "Scheduled workdays per week"; color: root.menuInk; font.pixelSize: 12; Layout.fillWidth: true }
                TextField {
                    id: workDaysField
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 34
                    inputMethodHints: Qt.ImhDigitsOnly
                    selectByMouse: true
                    validator: IntValidator { bottom: 1; top: 7 }
                }

                Text { text: "Vacation (scheduled workdays / year)"; color: root.menuInk; font.pixelSize: 12; Layout.fillWidth: true }
                TextField {
                    id: vacationField
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 34
                    inputMethodHints: Qt.ImhDigitsOnly
                    selectByMouse: true
                    validator: IntValidator { bottom: 0; top: 366 }
                }

                Text { text: "Public holidays (scheduled workdays / year)"; color: root.menuInk; font.pixelSize: 12; Layout.fillWidth: true }
                TextField {
                    id: holidayField
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 34
                    inputMethodHints: Qt.ImhDigitsOnly
                    selectByMouse: true
                    validator: IntValidator { bottom: 0; top: 366 }
                }

                Text { text: "Other unavailable scheduled workdays"; color: root.menuInk; font.pixelSize: 12; Layout.fillWidth: true }
                TextField {
                    id: unavailableField
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 34
                    inputMethodHints: Qt.ImhDigitsOnly
                    selectByMouse: true
                    validator: IntValidator { bottom: 0; top: 366 }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                radius: 5
                color: SemanticTheme.alpha(root.accent, 0.10)
                border.width: 1
                border.color: SemanticTheme.alpha(root.accent, 0.28)
                Column {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 2
                    Text {
                        text: "Calculated planning basis  ·  " + root.calculatedBasisDays + " days"
                        color: root.menuInk
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: root.weeksPerYear + " weeks × " + root.fieldNumber(workDaysField.text, 0)
                            + " scheduled days − vacation − holidays − other unavailable time"
                        color: SemanticTheme.alpha(root.menuInk, 0.72)
                        font.pixelSize: 10
                    }
                }
            }

            CheckBox {
                id: manualOverrideBox
                Layout.fillWidth: true
                text: "Override the calculated basis for forecasts"
                onToggled: {
                    root.statusText = checked
                        ? "Manual basis will be used until you turn this override off."
                        : "The calculated scheduled-workday basis will be used for new reports."
                }
            }

            RowLayout {
                Layout.fillWidth: true
                enabled: manualOverrideBox.checked
                opacity: enabled ? 1.0 : 0.55
                Text {
                    text: "Manual forecast basis"
                    color: root.menuInk
                    font.pixelSize: 12
                    Layout.fillWidth: true
                }
                TextField {
                    id: manualBasisField
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 34
                    inputMethodHints: Qt.ImhDigitsOnly
                    selectByMouse: true
                    validator: IntValidator { bottom: 1; top: 366 }
                }
                Text { text: "days"; color: root.mutedInk; font.pixelSize: 12 }
            }

            Text {
                Layout.fillWidth: true
                text: "Example: with a 6-day workweek, one full week of vacation is 6 vacation days. Your usual seventh day off is already excluded, so it is not deducted again."
                color: SemanticTheme.alpha(root.menuInk, 0.70)
                font.pixelSize: 10
                wrapMode: Text.Wrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 6
                    color: SemanticTheme.alpha(root.accent, 0.10)
                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.statusText
                        color: root.menuInk
                        font.pixelSize: 11
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }
                Button {
                    text: "Save"
                    highlighted: true
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: 36
                    onClicked: root.saveSettings()
                }
            }
        }
    }
}
