import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards/AppTypography.js" as AppTypography

Item {
    id: root

    property var appRef
    property var backend
    property var t
    property color surfaceColor: "#ffffff"
    property color canvasColor: "#f7f9fc"
    property color inputColor: "#ffffff"
    property color textColor: "#17243a"
    property color mutedColor: "#65758a"
    property color borderColor: "#cbd6e3"
    property color accentColor: "#30445f"
    property bool isDark: false

    property bool busy: false
    property string statusMessage: "Select a period preset or date range and click 'Run 4-Way Reconciliation'."
    property bool statusIsError: false
    property bool isReconciled: true
    property int activeTabIndex: 0

    property string startDateText: ""
    property string endDateText: ""
    property string periodLabel: ""

    property real dbHours: 0.0
    property int dbCount: 0
    property real cspmXlHours: 0.0
    property int cspmXlCount: 0
    property real docketsXlHours: 0.0
    property int docketsXlCount: 0
    property real xeroHours: 0.0
    property int xeroCount: 0
    property real diffHours: 0.0
    property int diffMinutes: 0

    property var clientRollup: []
    property var matchedEntries: []
    property var missingEntries: []
    property var xeroOnlyEntries: []
    property var auditWarnings: []
    property string reportText: ""
    property bool initialAutoRunDone: false

    function pad2(n) {
        return n < 10 ? ("0" + n) : String(n)
    }

    function applyCurrentMtdPreset(autoRun) {
        var now = new Date()
        var y = now.getFullYear()
        var m = now.getMonth() + 1
        var d = now.getDate()
        startDateText = y + "-" + pad2(m) + "-01"
        endDateText = y + "-" + pad2(m) + "-" + pad2(d)
        periodLabel = y + "-" + pad2(m) + " (MTD through " + endDateText + ")"
        if (fromDateInput) fromDateInput.text = startDateText
        if (toDateInput) toDateInput.text = endDateText
        if (autoRun) runReconciliation(false, false)
    }

    function applyPreviousMonthPreset(autoRun) {
        var now = new Date()
        var prevEnd = new Date(now.getFullYear(), now.getMonth(), 0)
        var y = prevEnd.getFullYear()
        var m = prevEnd.getMonth() + 1
        var lastDay = prevEnd.getDate()
        startDateText = y + "-" + pad2(m) + "-01"
        endDateText = y + "-" + pad2(m) + "-" + pad2(lastDay)
        periodLabel = y + "-" + pad2(m) + " (Full Month)"
        if (fromDateInput) fromDateInput.text = startDateText
        if (toDateInput) toDateInput.text = endDateText
        if (autoRun) runReconciliation(false, false)
    }

    function runReconciliation(doSync, updateMismatches) {
        if (!backend || !backend.runXeroReconciliation) {
            statusMessage = "Xero reconciliation backend service is not available."
            statusIsError = true
            return
        }
        var sDate = String(fromDateInput ? fromDateInput.text : startDateText).trim()
        var eDate = String(toDateInput ? toDateInput.text : endDateText).trim()
        if (!sDate.length || !eDate.length) {
            statusMessage = "Enter valid YYYY-MM-DD start and end dates."
            statusIsError = true
            return
        }
        startDateText = sDate
        endDateText = eDate
        busy = true
        statusIsError = false
        statusMessage = doSync
            ? ("Syncing missing LIH dockets to Xero Projects (!6x!pP) and verifying " + sDate + " to " + eDate + "...")
            : ("Running live 4-way reconciliation (" + sDate + " to " + eDate + ")...")
        backend.runXeroReconciliation({
            "startDate": sDate,
            "endDate": eDate,
            "periodLabel": periodLabel || (sDate + " to " + eDate),
            "doSync": !!doSync,
            "updateMismatches": !!updateMismatches,
            "exportReport": false
        })
    }

    function exportMarkdownReport() {
        if (!backend || !backend.runXeroReconciliation) return
        var sDate = String(fromDateInput ? fromDateInput.text : startDateText).trim()
        var eDate = String(toDateInput ? toDateInput.text : endDateText).trim()
        busy = true
        statusIsError = false
        statusMessage = "Exporting Markdown reconciliation report to CSPM_Shared_Data..."
        backend.runXeroReconciliation({
            "startDate": sDate,
            "endDate": eDate,
            "periodLabel": periodLabel || (sDate + " to " + eDate),
            "doSync": false,
            "updateMismatches": false,
            "exportReport": true
        })
    }

    Component.onCompleted: {
        applyCurrentMtdPreset(false)
    }

    onVisibleChanged: {
        if (visible && !initialAutoRunDone) {
            initialAutoRunDone = true
            applyCurrentMtdPreset(true)
        }
    }

    Connections {
        target: root.backend
        ignoreUnknownSignals: true

        function onXeroReconciliationFinished(result) {
            root.busy = false
            var resp = result || ({})
            if (!resp.ok) {
                root.statusIsError = true
                root.statusMessage = String(resp.message || "Xero reconciliation failed.")
                return
            }
            root.statusIsError = false
            root.isReconciled = !!resp.is_reconciled
            var tots = resp.totals || ({})
            root.dbHours = Number(tots.db_hours || 0.0)
            root.dbCount = Number(tots.db_count || 0)
            root.cspmXlHours = Number(tots.cspm_xl_hours || 0.0)
            root.cspmXlCount = Number(tots.cspm_xl_count || 0)
            root.docketsXlHours = Number(tots.dockets_xl_hours || 0.0)
            root.docketsXlCount = Number(tots.dockets_xl_count || 0)
            root.xeroHours = Number(tots.xero_hours || 0.0)
            root.xeroCount = Number(tots.xero_count || 0)
            root.diffHours = Number(tots.diff_hours || 0.0)
            root.diffMinutes = Number(tots.diff_minutes || 0)

            root.clientRollup = resp.client_rollup || []
            root.matchedEntries = resp.matched_entries || []
            root.missingEntries = resp.missing_in_xero || []
            root.xeroOnlyEntries = resp.xero_only || []
            root.auditWarnings = resp.warnings || []
            root.reportText = String(resp.report_text || "")

            var syncedCnt = Number(resp.synced_count || 0)
            var updatedCnt = Number(resp.updated_count || 0)
            var savedPath = String(resp.saved_report_path || "")
            if (savedPath.length > 0) {
                root.statusMessage = "Saved reconciliation report to: " + savedPath
            } else if (syncedCnt > 0 || updatedCnt > 0) {
                root.statusMessage = "Synced " + syncedCnt + " new and " + updatedCnt + " updated entries to Xero Projects. 100% verified."
            } else if (root.isReconciled) {
                root.statusMessage = "100% 4-Way Match across cspm.db, CSPM.xlsm, Dockets.xlsm, and Xero Projects (" + root.dbHours.toFixed(2) + "h / " + root.dbCount + " entries)."
            } else {
                root.statusMessage = "Action Needed: " + root.missingEntries.length + " entry(s) missing in Xero, " + root.xeroOnlyEntries.length + " Xero-only entry(s)."
            }
        }
    }

    TextEdit {
        id: hiddenClipboardHelper
        visible: false
    }

    Rectangle {
        anchors.fill: parent
        color: root.canvasColor

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 14

            // 1. Header & Controls Bar
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: headerCol.implicitHeight + 28
                radius: 8
                color: root.surfaceColor
                border.color: root.borderColor
                border.width: 1

                ColumnLayout {
                    id: headerCol
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: "Lawyers In-House (LIH) - 4-Way Xero Projects Reconciliation"
                                color: root.textColor
                                font.family: AppTypography.sans
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                            }

                            Text {
                                text: "Live reconciliation and 1-click docket sync across cspm.db, CSPM.xlsm, Dockets.xlsm, and Xero Projects (!6x!pP). New LIH dockets auto-sync on save."
                                color: root.mutedColor
                                font.family: AppTypography.sans
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }

                        // Status Pill
                        Rectangle {
                            height: 30
                            implicitWidth: statusPillText.implicitWidth + 24
                            radius: 15
                            color: root.isReconciled
                                ? (root.isDark ? "#133929" : "#e6f6ee")
                                : (root.isDark ? "#422c12" : "#fef4e6")
                            border.width: 1
                            border.color: root.isReconciled ? "#22a06b" : "#d97706"

                            Text {
                                id: statusPillText
                                anchors.centerIn: parent
                                text: root.busy
                                    ? "SYNCING / CHECKING..."
                                    : (root.isReconciled ? "100% 4-WAY RECONCILED" : ("VARIANCE: " + (root.diffHours >= 0 ? "+" : "") + root.diffHours.toFixed(2) + "h"))
                                color: root.isReconciled ? (root.isDark ? "#6ee7b7" : "#15803d") : (root.isDark ? "#fcd34d" : "#b45309")
                                font.family: AppTypography.sans
                                font.pixelSize: 11
                                font.weight: Font.Bold
                            }
                        }
                    }

                    // Filter & Action Row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Button {
                            text: "Current Month (MTD)"
                            enabled: !root.busy
                            onClicked: root.applyCurrentMtdPreset(true)
                        }

                        Button {
                            text: "Previous Month"
                            enabled: !root.busy
                            onClicked: root.applyPreviousMonthPreset(true)
                        }

                        Rectangle {
                            width: 1
                            height: 24
                            color: root.borderColor
                        }

                        Text {
                            text: "From:"
                            color: root.mutedColor
                            font.family: AppTypography.sans
                            font.pixelSize: 12
                        }

                        TextField {
                            id: fromDateInput
                            Layout.preferredWidth: 110
                            placeholderText: "YYYY-MM-DD"
                            text: root.startDateText
                            enabled: !root.busy
                            font.family: AppTypography.mono
                            font.pixelSize: 12
                            onTextEdited: {
                                root.periodLabel = fromDateInput.text + " to " + toDateInput.text
                            }
                        }

                        Text {
                            text: "To:"
                            color: root.mutedColor
                            font.family: AppTypography.sans
                            font.pixelSize: 12
                        }

                        TextField {
                            id: toDateInput
                            Layout.preferredWidth: 110
                            placeholderText: "YYYY-MM-DD"
                            text: root.endDateText
                            enabled: !root.busy
                            font.family: AppTypography.mono
                            font.pixelSize: 12
                            onTextEdited: {
                                root.periodLabel = fromDateInput.text + " to " + toDateInput.text
                            }
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: root.busy ? "Running..." : "Run 4-Way Reconciliation"
                            enabled: !root.busy
                            onClicked: root.runReconciliation(false, false)
                        }

                        Button {
                            text: "Sync Missing to Xero (" + root.missingEntries.length + ")"
                            enabled: !root.busy && (root.missingEntries.length > 0 || !root.isReconciled)
                            onClicked: root.runReconciliation(true, true)
                        }

                        Button {
                            text: "Export .MD Report"
                            enabled: !root.busy
                            onClicked: root.exportMarkdownReport()
                        }

                        Button {
                            text: "Re-Auth Xero"
                            enabled: !root.busy
                            onClicked: {
                                if (root.backend && root.backend.openXeroLoginWindow) {
                                    root.statusMessage = "Opening Edge Xero login window..."
                                    root.backend.openXeroLoginWindow()
                                }
                            }
                        }
                    }

                    // Status Message Banner
                    Rectangle {
                        Layout.fillWidth: true
                        height: 30
                        radius: 6
                        color: root.statusIsError
                            ? (root.isDark ? "#3b181c" : "#fde8e8")
                            : (root.isDark ? "#172334" : "#f1f5f9")
                        border.width: 1
                        border.color: root.statusIsError ? "#ef4444" : root.borderColor

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: 10
                            text: root.statusMessage
                            color: root.statusIsError ? "#ef4444" : root.textColor
                            font.family: AppTypography.sans
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            // 2. KPI Summary Cards (4 Systems + Variance)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Repeater {
                    model: [
                        { "title": "1. SQLite (cspm.db)", "hours": root.dbHours.toFixed(2) + " h", "sub": root.dbCount + " LIH entries" },
                        { "title": "2. CSPM Workbook (CSPM.xlsm)", "hours": root.cspmXlHours.toFixed(2) + " h", "sub": root.cspmXlCount + " LIH entries" },
                        { "title": "3. Legacy Dockets (Dockets.xlsm)", "hours": root.docketsXlHours.toFixed(2) + " h", "sub": root.docketsXlCount + " LIH entries" },
                        { "title": "4. Xero Projects (!6x!pP)", "hours": root.xeroHours.toFixed(2) + " h", "sub": root.xeroCount + " Xero entries" },
                        { "title": "Net Variance (CSPM - Xero)", "hours": (root.diffHours >= 0 ? "+" : "") + root.diffHours.toFixed(2) + " h", "sub": (root.diffMinutes >= 0 ? "+" : "") + root.diffMinutes + " mins | " + root.missingEntries.length + " missing" }
                    ]

                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        height: 76
                        radius: 8
                        color: root.surfaceColor
                        border.color: root.borderColor
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 4

                            Text {
                                text: modelData.title
                                color: root.mutedColor
                                font.family: AppTypography.sans
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }

                            Text {
                                text: modelData.hours
                                color: root.textColor
                                font.family: AppTypography.mono
                                font.pixelSize: 19
                                font.weight: Font.Bold
                            }

                            Text {
                                text: modelData.sub
                                color: root.mutedColor
                                font.family: AppTypography.sans
                                font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            // 3. Sub-Navigation Tabs (Client Rollup | Entry Breakdown | Full Text Report)
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "Client Rollup (" + root.clientRollup.length + " Clients)"
                    highlighted: root.activeTabIndex === 0
                    onClicked: root.activeTabIndex = 0
                }

                Button {
                    text: "Entry Breakdown (" + root.matchedEntries.length + " Matched, " + root.missingEntries.length + " Missing)"
                    highlighted: root.activeTabIndex === 1
                    onClicked: root.activeTabIndex = 1
                }

                Button {
                    text: "Formatted Audit Report & Warnings (" + root.auditWarnings.length + ")"
                    highlighted: root.activeTabIndex === 2
                    onClicked: root.activeTabIndex = 2
                }

                Item { Layout.fillWidth: true }

                Button {
                    visible: root.activeTabIndex === 2
                    text: "Copy Report to Clipboard"
                    onClicked: {
                        hiddenClipboardHelper.text = root.reportText
                        hiddenClipboardHelper.selectAll()
                        hiddenClipboardHelper.copy()
                        root.statusMessage = "Copied full 4-way reconciliation report to clipboard."
                    }
                }
            }

            // 4. Main Content Area
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: root.surfaceColor
                border.color: root.borderColor
                border.width: 1
                clip: true

                // TAB 0: Client Rollup Table
                ColumnLayout {
                    anchors.fill: parent
                    visible: root.activeTabIndex === 0
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        color: root.isDark ? "#1e293b" : "#f1f5f9"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            spacing: 8

                            Text { text: "Client"; Layout.preferredWidth: 220; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Xero Project / Task"; Layout.preferredWidth: 220; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "cspm.db"; Layout.preferredWidth: 95; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "CSPM.xlsm"; Layout.preferredWidth: 95; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Dockets.xlsm"; Layout.preferredWidth: 95; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Xero Proj"; Layout.preferredWidth: 95; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Diff"; Layout.preferredWidth: 80; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Status"; Layout.fillWidth: true; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.clientRollup
                        ScrollBar.vertical: ScrollBar {}

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            height: 40
                            color: (index % 2 === 1) ? (root.isDark ? "#151f2e" : "#f8fafc") : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 8

                                Text {
                                    text: String(modelData.client_label || modelData.client_code || "")
                                    Layout.preferredWidth: 220
                                    elide: Text.ElideRight
                                    color: root.textColor
                                    font.family: AppTypography.sans
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                }

                                Text {
                                    text: String(modelData.task_name || modelData.project_name || "Auto-Discover")
                                    Layout.preferredWidth: 220
                                    elide: Text.ElideRight
                                    color: root.mutedColor
                                    font.family: AppTypography.sans
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: Number(modelData.db_hours || 0).toFixed(2) + "h (" + Number(modelData.db_count || 0) + ")"
                                    Layout.preferredWidth: 95
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: Number(modelData.cspm_xl_hours || 0).toFixed(2) + "h (" + Number(modelData.cspm_xl_count || 0) + ")"
                                    Layout.preferredWidth: 95
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: Number(modelData.dockets_xl_hours || 0).toFixed(2) + "h (" + Number(modelData.dockets_xl_count || 0) + ")"
                                    Layout.preferredWidth: 95
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: Number(modelData.xero_hours || 0).toFixed(2) + "h (" + Number(modelData.xero_count || 0) + ")"
                                    Layout.preferredWidth: 95
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    property real var_diff: Number(modelData.diff_hours || 0)
                                    text: (var_diff >= 0 ? "+" : "") + var_diff.toFixed(2) + "h"
                                    Layout.preferredWidth: 80
                                    color: Math.abs(var_diff) < 0.005 ? root.mutedColor : "#d97706"
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                    font.weight: Math.abs(var_diff) < 0.005 ? Font.Normal : Font.Bold
                                }

                                Text {
                                    text: String(modelData.status || "")
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    color: String(modelData.status || "").indexOf("OK") === 0 ? "#16a34a" : "#d97706"
                                    font.family: AppTypography.sans
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                }

                // TAB 1: Entry-by-Entry Breakdown
                ColumnLayout {
                    anchors.fill: parent
                    visible: root.activeTabIndex === 1
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        color: root.isDark ? "#1e293b" : "#f1f5f9"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            spacing: 8

                            Text { text: "Status"; Layout.preferredWidth: 120; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Date"; Layout.preferredWidth: 95; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Client"; Layout.preferredWidth: 200; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "CSPM Hrs"; Layout.preferredWidth: 80; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Xero Hrs"; Layout.preferredWidth: 80; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Split %"; Layout.preferredWidth: 70; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Xero State"; Layout.preferredWidth: 90; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                            Text { text: "Description"; Layout.fillWidth: true; font.weight: Font.Bold; font.pixelSize: 12; color: root.textColor }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        ScrollBar.vertical: ScrollBar {}
                        model: {
                            var combined = []
                            for (var i = 0; i < root.missingEntries.length; i++) {
                                var m = root.missingEntries[i]
                                combined.push({
                                    "badge": "MISSING IN XERO",
                                    "isOk": false,
                                    "date": m.date,
                                    "client_label": m.client_label,
                                    "db_hours": Number(m.hours || 0).toFixed(2) + "h",
                                    "xero_hours": "0.00h",
                                    "share_pct": Number(m.share_pct || 70).toFixed(0) + "%",
                                    "xero_status": "UNSYNCED",
                                    "description": m.description
                                })
                            }
                            for (var j = 0; j < root.xeroOnlyEntries.length; j++) {
                                var x = root.xeroOnlyEntries[j]
                                combined.push({
                                    "badge": "XERO ONLY",
                                    "isOk": false,
                                    "date": x.date,
                                    "client_label": x.client_label,
                                    "db_hours": "0.00h",
                                    "xero_hours": Number(x.xero_hours || 0).toFixed(2) + "h",
                                    "share_pct": "-",
                                    "xero_status": x.xero_status,
                                    "description": x.description
                                })
                            }
                            for (var k = 0; k < root.matchedEntries.length; k++) {
                                var e = root.matchedEntries[k]
                                combined.push({
                                    "badge": e.match_type === "EXACT" ? "MATCHED" : e.match_type,
                                    "isOk": e.match_type === "EXACT",
                                    "date": e.date,
                                    "client_label": e.client_label,
                                    "db_hours": Number(e.db_hours || 0).toFixed(2) + "h",
                                    "xero_hours": Number(e.xero_hours || 0).toFixed(2) + "h",
                                    "share_pct": Number(e.share_pct || 70).toFixed(0) + "%",
                                    "xero_status": e.xero_status,
                                    "description": e.description
                                })
                            }
                            return combined
                        }

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            height: 38
                            color: (index % 2 === 1) ? (root.isDark ? "#151f2e" : "#f8fafc") : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 8

                                Text {
                                    text: String(modelData.badge || "")
                                    Layout.preferredWidth: 120
                                    color: modelData.isOk ? "#16a34a" : "#d97706"
                                    font.family: AppTypography.mono
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                }

                                Text {
                                    text: String(modelData.date || "")
                                    Layout.preferredWidth: 95
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: String(modelData.client_label || "")
                                    Layout.preferredWidth: 200
                                    elide: Text.ElideRight
                                    color: root.textColor
                                    font.family: AppTypography.sans
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: String(modelData.db_hours || "")
                                    Layout.preferredWidth: 80
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: String(modelData.xero_hours || "")
                                    Layout.preferredWidth: 80
                                    color: root.textColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: String(modelData.share_pct || "")
                                    Layout.preferredWidth: 70
                                    color: root.mutedColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: String(modelData.xero_status || "")
                                    Layout.preferredWidth: 90
                                    color: root.mutedColor
                                    font.family: AppTypography.mono
                                    font.pixelSize: 11
                                }

                                Text {
                                    text: String(modelData.description || "")
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    color: root.textColor
                                    font.family: AppTypography.sans
                                    font.pixelSize: 12
                                }
                            }
                        }
                    }
                }

                // TAB 2: Monospace Report Text
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 12
                    visible: root.activeTabIndex === 2
                    clip: true

                    TextArea {
                        text: root.reportText
                        readOnly: true
                        selectByMouse: true
                        color: root.textColor
                        font.family: AppTypography.mono
                        font.pixelSize: 12
                        background: null
                    }
                }
            }
        }
    }
}
