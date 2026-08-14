pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property var metrics
    property var appRef: null
    property var windowRef: null
    property var sfxBus: null
    property var reportData: ({})
    property bool isLoading: false
    property bool initialRequestMade: false
    property bool zenAvailable: true
    property bool zenPresentation: false
    property bool autoGenerate: true
    property var zenPanel: null
    property string statusText: "Choose a period, then generate an executive productivity report."

    readonly property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle) : "Professional"
    readonly property color pageColor: SemanticTheme.surfaceApp(root.t, root.appStyle)
    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color raisedColor: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color inputColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color strongBorderColor: SemanticTheme.borderStrong(root.t, root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color navy: SemanticTheme.isDarkMode(root.t) ? "#17243a" : "#1d2b44"
    readonly property color chartNavy: SemanticTheme.isDarkMode(root.t) ? "#6282ae" : "#24334d"
    readonly property bool hasReport: !!(root.reportData && root.reportData.ok)
    readonly property bool shortCanvas: root.height < 650
    readonly property int outerMargin: root.zenPresentation ? 18 : 10
    readonly property int sectionGap: root.shortCanvas ? 7 : 10
    readonly property int railWidth: root.zenPresentation ? 310 : Math.max(250, Math.min(296, Math.round(root.width * 0.23)))

    function isoDate(value) {
        return Qt.formatDate(value, "yyyy-MM-dd")
    }

    function daysFromToday(days) {
        var value = new Date()
        value.setHours(12, 0, 0, 0)
        value.setDate(value.getDate() + days)
        return value
    }

    function money(value, decimals) {
        var places = decimals === undefined ? 0 : decimals
        var number = Number(value || 0)
        var sign = number < 0 ? "-" : ""
        number = Math.abs(number)
        var fixed = number.toFixed(places)
        var pieces = fixed.split(".")
        pieces[0] = pieces[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
        return sign + "$" + pieces.join(places > 0 ? "." : "")
    }

    function percent(value) {
        var number = Number(value || 0)
        return (number >= 0 ? "+" : "") + number.toFixed(1) + "%"
    }

    function numberValue(value, decimals) {
        var places = decimals === undefined ? 1 : decimals
        return Number(value || 0).toFixed(places).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    function summary() { return root.hasReport && root.reportData.summary ? root.reportData.summary : ({}) }
    function forecast() { return root.hasReport && root.reportData.forecast ? root.reportData.forecast : ({}) }
    function topClients() { return root.hasReport && root.reportData.topClients ? root.reportData.topClients : [] }
    function monthlyRows() { return root.hasReport && root.reportData.monthlyProduction ? root.reportData.monthlyProduction : [] }
    function dailyRows() { return root.hasReport && root.reportData.dailyProduction ? root.reportData.dailyProduction : [] }

    function maximum(rows) {
        var greatest = 0
        for (var index = 0; index < rows.length; ++index)
            greatest = Math.max(greatest, Number(rows[index].amount || 0))
        return greatest
    }

    function applyRange(start, end) {
        startField.text = isoDate(start)
        endField.text = isoDate(end)
        generateReport()
    }

    function applyPreset(key) {
        var today = daysFromToday(0)
        if (key === "today") {
            applyRange(today, today)
        } else if (key === "last7") {
            applyRange(daysFromToday(-6), today)
        } else if (key === "lastWeek") {
            var end = daysFromToday(0)
            if (end.getDay() !== 6) end.setDate(end.getDate() - end.getDay() - 1)
            applyRange(daysFromToday((end.getTime() - today.getTime()) / 86400000 - 6), end)
        } else if (key === "rolling30") {
            applyRange(daysFromToday(-30), today)
        } else if (key === "rolling90") {
            applyRange(daysFromToday(-90), today)
        } else if (key === "lastMonth") {
            applyRange(new Date(today.getFullYear(), today.getMonth() - 1, 1), new Date(today.getFullYear(), today.getMonth(), 0))
        } else if (key === "ytd") {
            applyRange(new Date(today.getFullYear(), 0, 1), today)
        } else if (key === "rollingYear") {
            applyRange(daysFromToday(-365), today)
        }
    }

    function generateReport() {
        if (!root.appRef || !root.appRef.getProductivityReport) {
            root.statusText = "Productivity reporting is still connecting to CSPM data."
            return
        }
        root.isLoading = true
        root.statusText = "Calculating realized production…"
        var result = root.appRef.getProductivityReport({
            "startDate": String(startField.text || "").trim(),
            "endDate": String(endField.text || "").trim(),
            "annualTarget": String(targetField.text || "").trim()
        })
        root.isLoading = false
        if (result && result.ok) {
            root.reportData = result
            root.statusText = "Report updated " + String(result.generatedAt || "") + "."
        } else {
            root.reportData = ({})
            root.statusText = (result && result.message) ? String(result.message) : "CSPM could not generate this report."
        }
    }

    function exportPdf() {
        if (!root.hasReport) {
            root.statusText = "Generate a valid report before exporting it."
            return
        }
        if (!root.appRef || !root.appRef.saveReportPdf) {
            root.statusText = "PDF export is not available yet."
            return
        }
        var result = root.appRef.saveReportPdf({
            "reportId": "productivity_report",
            "exportPayload": root.reportData
        })
        if (result && result.ok) {
            root.statusText = String(result.message || "PDF exported.")
            if (result.path) Qt.openUrlExternally("file:///" + String(result.path).replace(/\\/g, "/"))
        } else {
            root.statusText = (result && result.message) ? String(result.message) : "CSPM could not export the PDF."
        }
    }

    function requestInitialReport() {
        if (!root.autoGenerate || root.initialRequestMade || !root.appRef || !root.appRef.getProductivityReport) return
        root.initialRequestMade = true
        Qt.callLater(generateReport)
    }

    function reportSnapshot() {
        return {
            "startDate": String(startField.text || ""),
            "endDate": String(endField.text || ""),
            "annualTarget": String(targetField.text || ""),
            "reportData": root.reportData,
            "statusText": root.statusText
        }
    }

    function applyReportSnapshot(snapshot) {
        if (!snapshot) return
        startField.text = String(snapshot.startDate || "")
        endField.text = String(snapshot.endDate || "")
        targetField.text = String(snapshot.annualTarget || "")
        root.reportData = snapshot.reportData || ({})
        root.statusText = String(snapshot.statusText || "Choose a period, then generate an executive productivity report.")
        root.initialRequestMade = true
    }

    function syncZenPanel() {
        if (root.zenPanel && root.zenPanel.applyReportSnapshot) {
            root.zenPanel.applyReportSnapshot(root.reportSnapshot())
        }
    }

    function openZenView() {
        if (!root.zenAvailable) return
        var appWindow = root.Window.window
        if (appWindow) zenWindow.transientParent = appWindow
        zenWindow.showMaximized()
        zenWindow.requestActivate()
        Qt.callLater(root.syncZenPanel)
    }

    onAppRefChanged: requestInitialReport()
    Component.onCompleted: {
        startField.text = isoDate(daysFromToday(-30))
        endField.text = isoDate(daysFromToday(0))
        targetField.text = "350000"
        requestInitialReport()
    }

    Item {
        id: inlineHost
        anchors.fill: parent
    }

    Window {
        id: zenWindow
        title: "Productivity Report — Zen View"
        color: root.pageColor
        flags: Qt.Window
        minimumWidth: 1100
        minimumHeight: 720
        visible: false

        onVisibleChanged: {
            if (visible) Qt.callLater(root.syncZenPanel)
        }

        Loader {
            id: zenPanelLoader
            anchors.fill: parent
            active: zenWindow.visible && root.zenAvailable
            sourceComponent: zenPanelComponent
            onLoaded: {
                root.zenPanel = item
                Qt.callLater(root.syncZenPanel)
            }
        }
    }

    Component {
        id: zenPanelComponent
        ProductivityZenView {
            anchors.fill: parent
            t: root.t
        }
    }

    Item {
        id: reportSurface
        parent: inlineHost
        width: parent ? parent.width : 0
        height: parent ? parent.height : 0
        clip: true

        Rectangle {
            anchors.fill: parent
            color: root.pageColor
        }

        RowLayout {
            anchors.fill: parent
            anchors.margins: root.outerMargin
            spacing: root.sectionGap

            Rectangle {
                id: parameterRail
                Layout.fillHeight: true
                Layout.preferredWidth: root.railWidth
                Layout.minimumWidth: 236
                radius: 8
                color: root.panelColor
                border.width: 1
                border.color: root.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: root.shortCanvas ? 11 : 14
                    spacing: root.shortCanvas ? 6 : 8

                    Text {
                        text: "REPORT PARAMETERS"
                        color: root.ink
                        font.pixelSize: 12
                        font.weight: Font.Bold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Choose a period and target. Double-click a date for the calendar."
                        color: root.mutedInk
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }

                    ModernTextField {
                        id: startField
                        t: root.t
                        metrics: root.metrics
                        label: "Start Date"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        selectByMouse: true
                        onEditingFinished: root.generateReport()
                        onDatePickerDatePicked: function(_pickedDate, _isoText) {
                            root.generateReport()
                        }
                    }

                    ModernTextField {
                        id: endField
                        t: root.t
                        metrics: root.metrics
                        label: "End Date"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        selectByMouse: true
                        onEditingFinished: root.generateReport()
                        onDatePickerDatePicked: function(_pickedDate, _isoText) {
                            root.generateReport()
                        }
                    }

                    ModernTextField {
                        id: targetField
                        t: root.t
                        metrics: root.metrics
                        label: "Annual Target ($)"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        selectByMouse: true
                        inputMethodHints: Qt.ImhFormattedNumbersOnly
                        onEditingFinished: root.generateReport()
                    }

                    Text {
                        text: "QUICK RANGES"
                        color: root.accent
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        Layout.topMargin: 2
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 6
                        rowSpacing: 6

                        Repeater {
                            model: [
                                { "key": "today", "label": "Today" },
                                { "key": "last7", "label": "Last 7 Days" },
                                { "key": "lastWeek", "label": "Last Week" },
                                { "key": "rolling30", "label": "30 Days" },
                                { "key": "rolling90", "label": "90 Days" },
                                { "key": "lastMonth", "label": "Last Month" },
                                { "key": "ytd", "label": "YTD" },
                                { "key": "rollingYear", "label": "365 Days" }
                            ]

                            delegate: PillButton {
                                required property var modelData
                                t: root.t
                                metrics: root.metrics
                                sfxBus: root.sfxBus
                                text: modelData.label
                                primary: false
                                Layout.fillWidth: true
                                Layout.preferredHeight: 30
                                onClicked: root.applyPreset(String(modelData.key))
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: railStatusText.implicitHeight + 16
                        radius: 5
                        color: root.hasReport
                            ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.08)
                            : Qt.rgba(root.mutedInk.r, root.mutedInk.g, root.mutedInk.b, 0.08)
                        Text {
                            id: railStatusText
                            anchors.fill: parent
                            anchors.margins: 8
                            text: root.statusText
                            color: root.mutedInk
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Forecast basis: " + String(root.forecast().annualBasisDays || 336)
                            + " days. Change it in Settings → Productivity Forecast."
                        color: root.mutedInk
                        font.pixelSize: 9
                        wrapMode: Text.WordWrap
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: root.sectionGap

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.shortCanvas ? 58 : 68
                    radius: 8
                    color: root.navy

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: root.shortCanvas ? 14 : 18
                        anchors.rightMargin: root.shortCanvas ? 12 : 14
                        spacing: root.shortCanvas ? 8 : 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                text: "PRODUCTIVITY REPORT"
                                color: "white"
                                font.pixelSize: root.shortCanvas ? 13 : 15
                                font.weight: Font.Bold
                            }
                            Text {
                                text: root.hasReport
                                    ? String(root.reportData.startDate || "") + "  —  " + String(root.reportData.endDate || "")
                                    : "Select report parameters to begin"
                                color: Qt.rgba(1, 1, 1, 0.76)
                                font.pixelSize: 10
                            }
                        }

                        Rectangle {
                            id: liveReadOnlyPill
                            Layout.preferredWidth: root.shortCanvas ? 132 : 156
                            Layout.preferredHeight: 28
                            radius: 14
                            color: Qt.rgba(1, 1, 1, 0.12)
                            Text {
                                anchors.centerIn: parent
                                text: "LIVE DATA · READ ONLY"
                                color: "white"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }
                            MouseArea {
                                id: liveReadOnlyHover
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.WhatsThisCursor
                            }
                            ToolTip.visible: liveReadOnlyHover.containsMouse
                            ToolTip.text: "Uses your current CSPM records for calculations. This report never edits invoices, time entries, or financial data."
                            ToolTip.delay: 250
                        }

                        PillButton {
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            text: "Zen View"
                            primary: false
                            visible: root.zenAvailable
                            Layout.preferredWidth: root.shortCanvas ? 88 : 104
                            Layout.preferredHeight: 34
                            onClicked: root.openZenView()
                        }

                        PillButton {
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            text: "Export PDF"
                            primary: true
                            Layout.preferredWidth: root.shortCanvas ? 96 : 112
                            Layout.preferredHeight: 34
                            enabled: root.hasReport
                            onClicked: root.exportPdf()
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.shortCanvas ? 62 : 72
                    visible: root.hasReport
                    columns: 3
                    columnSpacing: root.sectionGap

                    Repeater {
                        model: [
                            { "label": "TOTAL PRODUCTION", "value": root.money(root.summary().totalProduction, 0) },
                            { "label": "BILLABLE HOURS", "value": root.numberValue(root.summary().billableHours, 1) },
                            { "label": "REALIZED RATE", "value": root.money(root.summary().realizedRate, 2) }
                        ]

                        delegate: Rectangle {
                            id: metricCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 7
                            color: root.panelColor
                            border.width: 1
                            border.color: root.borderColor
                            Column {
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 3
                                Text {
                                    text: metricCard.modelData.label
                                    color: root.mutedInk
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                }
                                Text {
                                    text: metricCard.modelData.value
                                    color: root.ink
                                    font.pixelSize: root.shortCanvas ? 18 : 22
                                    font.weight: Font.Light
                                }
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.shortCanvas ? 144 : 162
                    visible: root.hasReport
                    columns: 2
                    columnSpacing: root.sectionGap

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: root.panelColor
                        border.width: 1
                        border.color: root.borderColor
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.shortCanvas ? 11 : 14
                            spacing: root.shortCanvas ? 4 : 6
                            Text { text: "ANNUAL FORECAST"; color: root.accent; font.pixelSize: 10; font.weight: Font.Bold }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 12
                                rowSpacing: 3
                                Text { text: "Current pace"; color: root.mutedInk; font.pixelSize: 10 }
                                Text { text: root.money(root.forecast().dailyPace, 0) + " / day"; color: root.ink; font.pixelSize: 10; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                                Text { text: "Basis"; color: root.mutedInk; font.pixelSize: 10 }
                                Text { text: String(root.forecast().annualBasisDays || 336) + " days"; color: root.ink; font.pixelSize: 10; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                                Text { text: "Target"; color: root.mutedInk; font.pixelSize: 10 }
                                Text { text: root.money(root.forecast().annualTarget, 0); color: root.ink; font.pixelSize: 10; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                            }
                            Item { Layout.fillHeight: true }
                            Text { text: root.money(root.forecast().annualProjection, 0); color: root.ink; font.pixelSize: root.shortCanvas ? 22 : 26; font.weight: Font.Light }
                            Text { text: root.percent(root.forecast().percentToTarget) + " vs target"; color: Number(root.forecast().percentToTarget || 0) < 0 ? "#C23B3B" : "#278A58"; font.pixelSize: 10; font.weight: Font.Bold }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: root.panelColor
                        border.width: 1
                        border.color: root.borderColor
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.shortCanvas ? 11 : 14
                            spacing: root.shortCanvas ? 4 : 6
                            Text { text: "TOP CLIENTS"; color: root.accent; font.pixelSize: 10; font.weight: Font.Bold }
                            Text {
                                visible: root.topClients().length === 0
                                text: "No production in the selected period."
                                color: root.mutedInk
                                font.pixelSize: 10
                                font.italic: true
                            }
                            Repeater {
                                model: root.topClients()
                                delegate: Item {
                                    id: clientRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.shortCanvas ? 16 : 19
                                    Text {
                                        id: clientName
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.max(80, parent.width * 0.40)
                                        text: clientRow.modelData.name
                                        color: root.ink
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        id: clientValue
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: root.money(clientRow.modelData.amount, 0)
                                        color: root.ink
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                    }
                                    Rectangle {
                                        anchors.left: clientName.right
                                        anchors.leftMargin: 8
                                        anchors.right: clientValue.left
                                        anchors.rightMargin: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                        height: 6
                                        radius: 3
                                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                                        Rectangle {
                                            width: parent.width * (Number(clientRow.modelData.amount || 0) / Math.max(1, root.maximum(root.topClients())))
                                            height: parent.height
                                            radius: 3
                                            color: root.accent
                                        }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: root.shortCanvas ? 174 : 208
                    visible: root.hasReport
                    columns: 2
                    columnSpacing: root.sectionGap

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: root.panelColor
                        border.width: 1
                        border.color: root.borderColor
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.shortCanvas ? 11 : 14
                            spacing: 4
                            Text { text: "MONTHLY PRODUCTION TREND"; color: root.ink; font.pixelSize: 10; font.weight: Font.Bold }
                            Text { text: "Last 4 months, ending " + String(root.reportData.endDate || ""); color: root.mutedInk; font.pixelSize: 9 }
                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Row {
                                    id: monthlyChartRow
                                    anchors.fill: parent
                                    spacing: 5
                                    Repeater {
                                        model: root.monthlyRows()
                                        delegate: Item {
                                            id: monthlyDelegate
                                            required property var modelData
                                            width: Math.max(1, (monthlyChartRow.width - monthlyChartRow.spacing * Math.max(0, root.monthlyRows().length - 1)) / Math.max(1, root.monthlyRows().length))
                                            height: parent.height
                                            Item {
                                                id: monthlyPlot
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.top: parent.top
                                                anchors.bottom: monthlyLabel.top
                                                anchors.bottomMargin: 4
                                                Rectangle {
                                                    id: monthlyBar
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.bottom: parent.bottom
                                                    width: Math.min(44, parent.width * 0.52)
                                                    height: Math.max(3, parent.height * (Number(monthlyDelegate.modelData.amount || 0) / Math.max(1, root.maximum(root.monthlyRows()))))
                                                    radius: 3
                                                    color: root.chartNavy
                                                }
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.bottom: monthlyBar.top
                                                    anchors.bottomMargin: 2
                                                    text: Number(monthlyDelegate.modelData.amount || 0) > 0 ? root.money(monthlyDelegate.modelData.amount, 0) : ""
                                                    color: root.ink
                                                    font.pixelSize: 8
                                                }
                                            }
                                            Text {
                                                id: monthlyLabel
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                anchors.bottom: parent.bottom
                                                width: parent.width
                                                text: monthlyDelegate.modelData.label
                                                color: root.mutedInk
                                                horizontalAlignment: Text.AlignHCenter
                                                font.pixelSize: 9
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: root.panelColor
                        border.width: 1
                        border.color: root.borderColor
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.shortCanvas ? 11 : 14
                            spacing: 4
                            Text { text: "DAILY PRODUCTION"; color: root.ink; font.pixelSize: 10; font.weight: Font.Bold }
                            Text { text: "Last 7 days, ending " + String(root.reportData.endDate || ""); color: root.mutedInk; font.pixelSize: 9 }
                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Row {
                                    id: dailyChartRow
                                    anchors.fill: parent
                                    spacing: 3
                                    Repeater {
                                        model: root.dailyRows()
                                        delegate: Item {
                                            id: dailyDelegate
                                            required property var modelData
                                            width: Math.max(1, (dailyChartRow.width - dailyChartRow.spacing * Math.max(0, root.dailyRows().length - 1)) / Math.max(1, root.dailyRows().length))
                                            height: parent.height
                                            Item {
                                                id: dailyPlot
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.top: parent.top
                                                anchors.bottom: dailyLabel.top
                                                anchors.bottomMargin: 4
                                                Rectangle {
                                                    id: dailyBar
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.bottom: parent.bottom
                                                    width: Math.min(31, parent.width * 0.56)
                                                    height: Math.max(3, parent.height * (Number(dailyDelegate.modelData.amount || 0) / Math.max(1, root.maximum(root.dailyRows()))))
                                                    radius: 3
                                                    color: root.accent
                                                }
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    anchors.bottom: dailyBar.top
                                                    anchors.bottomMargin: 2
                                                    text: Number(dailyDelegate.modelData.amount || 0) > 0 ? root.money(dailyDelegate.modelData.amount, 0) : ""
                                                    color: root.ink
                                                    font.pixelSize: 8
                                                }
                                            }
                                            Text {
                                                id: dailyLabel
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                anchors.bottom: parent.bottom
                                                width: parent.width
                                                text: dailyDelegate.modelData.label
                                                color: root.mutedInk
                                                horizontalAlignment: Text.AlignHCenter
                                                font.pixelSize: 8
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.shortCanvas ? 24 : 30
                    visible: root.hasReport
                    Text {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: String(root.reportData.methodology || "") + " Forecast uses the saved "
                            + String(root.forecast().annualBasisDays || 336) + "-day planning basis."
                        color: root.mutedInk
                        font.pixelSize: 9
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !root.hasReport
                    Text {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 48, 520)
                        text: root.isLoading ? "Calculating realized production…" : "Generate a report to view realized production, forecast, clients, and trends."
                        color: root.mutedInk
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
