pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var metrics
    property var appRef
    property var windowRef
    property var sfxBus
    property var startupState: null
    property var docketAppRef: (root.appRef && root.appRef.docketing) ? root.appRef.docketing : null
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    readonly property color appSurface: SemanticTheme.surfaceApp(root.t, root.appStyle)
    readonly property color panelSurface: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color inputSurface: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color positive: SemanticTheme.tone(root.t, "success")
    readonly property color warning: SemanticTheme.tone(root.t, "warning")
    // Keep status and Zen controls visibly intentional in either Professional
    // theme.  Using the accent rather than a translucent copy of the text
    // colour avoids the washed-out grey pill seen in light mode.
    readonly property color accentSurface: SemanticTheme.surface(root.t, "panel", "info", root.appStyle)
    readonly property color accentBorder: SemanticTheme.border(root.t, "panel", "info", root.appStyle)
    readonly property color accentInk: SemanticTheme.ink(root.t, "panel", "info", root.appStyle)
    readonly property real panelRadius: visualRules.radiusPanel
    // Labelled Modern fields need enough vertical space for both the floating
    // label and a full-height value/edit cursor at normal desktop scaling.
    readonly property int fieldHeight: 56

    property bool busy: false
    property bool hasError: false
    property string statusText: "Loading today's docketed time…"
    property string requestToken: ""
    property bool stateApplied: false
    property bool stateRunQueued: false

    property string selectedClientId: "ALL"
    property string selectedClientLabel: "All Clients"
    property string selectedBillingClientId: "ALL"
    property string selectedBillingClientLabel: "All Billing Clients"
    property string selectedMatterId: "ALL"
    property string selectedMatterLabel: "All Matters"
    property string fromDateText: root.localTodayIso()
    property string toDateText: root.localTodayIso()
    property string searchText: ""

    property var optionClients: []
    property var optionBillingClients: []
    property var optionMatters: []
    property var matterGroups: []
    property var matterTotals: ({ "entryCount": 0, "totalHours": 0, "totalGrossFee": 0, "totalNetFee": 0 })
    property bool hasDistinctBillingClient: false
    property var ledgerRows: []
    property string lastExportPath: ""

    function localTodayIso() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function cleanText(value) {
        return String(value === undefined || value === null ? "" : value).trim()
    }

    function formatMoney(value) {
        var amount = Number(value || 0)
        if (!isFinite(amount)) amount = 0
        return "$" + amount.toLocaleString(Qt.locale("en_CA"), "f", 2)
    }

    function formatHours(value) {
        var hours = Number(value || 0)
        if (!isFinite(hours)) hours = 0
        return hours.toLocaleString(Qt.locale("en_CA"), "f", 2)
    }

    function optionLabels(allLabel, options) {
        var labels = [allLabel, "---"]
        var seen = ({})
        var values = options || []
        for (var i = 0; i < values.length; i++) {
            var label = cleanText(values[i].label || values[i].id)
            var key = label.toLowerCase()
            if (!label || seen[key]) continue
            seen[key] = true
            labels.push(label)
        }
        return labels
    }

    function optionForLabel(options, label, allLabel) {
        var wanted = cleanText(label)
        if (!wanted || wanted === allLabel) return ({ "id": "ALL", "label": allLabel })
        var values = options || []
        for (var i = 0; i < values.length; i++) {
            if (cleanText(values[i].label || values[i].id) === wanted) return values[i]
        }
        return ({ "id": wanted, "label": wanted })
    }

    function selectedOptionLabel(options, selectedId, fallback) {
        var wanted = cleanText(selectedId)
        var values = options || []
        for (var i = 0; i < values.length; i++) {
            var optionId = cleanText(values[i].id)
            if (optionId && optionId === wanted) return cleanText(values[i].label || optionId)
        }
        return fallback
    }

    function filterSummary() {
        var parts = []
        parts.push("Period: " + (fromDateText || "Earliest") + " to " + (toDateText || "Today"))
        if (selectedClientId !== "ALL") parts.push("Client: " + selectedClientLabel)
        if (selectedBillingClientId !== "ALL") parts.push("Billing client: " + selectedBillingClientLabel)
        if (selectedMatterId !== "ALL") parts.push("Matter: " + selectedMatterLabel)
        if (cleanText(searchText)) parts.push("Search: “" + cleanText(searchText) + "”")
        return parts.join("  ·  ")
    }

    function setRange(preset) {
        var today = new Date()
        function iso(value) { return Qt.formatDate(value, "yyyy-MM-dd") }
        if (preset === "today") {
            fromDateText = iso(today)
            toDateText = iso(today)
        } else if (preset === "week") {
            var day = today.getDay()
            var mondayOffset = day === 0 ? -6 : 1 - day
            var weekStart = new Date(today)
            weekStart.setDate(today.getDate() + mondayOffset)
            fromDateText = iso(weekStart)
            toDateText = iso(today)
        } else if (preset === "seven") {
            var sevenStart = new Date(today)
            sevenStart.setDate(today.getDate() - 6)
            fromDateText = iso(sevenStart)
            toDateText = iso(today)
        } else if (preset === "month") {
            fromDateText = Qt.formatDate(new Date(today.getFullYear(), today.getMonth(), 1), "yyyy-MM-dd")
            toDateText = iso(today)
        } else if (preset === "ytd") {
            fromDateText = Qt.formatDate(new Date(today.getFullYear(), 0, 1), "yyyy-MM-dd")
            toDateText = iso(today)
        } else if (preset === "all") {
            fromDateText = ""
            toDateText = ""
        }
        root.queueRunReport()
    }

    function queueRunReport() {
        if (stateRunQueued) return
        stateRunQueued = true
        Qt.callLater(function() {
            stateRunQueued = false
            root.runReport()
        })
    }

    function applyState(state) {
        var supplied = state || ({})
        if (supplied.startDate !== undefined) fromDateText = cleanText(supplied.startDate)
        if (supplied.endDate !== undefined) toDateText = cleanText(supplied.endDate)
        if (supplied.fromDate !== undefined) fromDateText = cleanText(supplied.fromDate)
        if (supplied.toDate !== undefined) toDateText = cleanText(supplied.toDate)
        if (supplied.clientId !== undefined) selectedClientId = cleanText(supplied.clientId) || "ALL"
        if (supplied.billingClientId !== undefined) selectedBillingClientId = cleanText(supplied.billingClientId) || "ALL"
        if (supplied.matterId !== undefined) selectedMatterId = cleanText(supplied.matterId) || "ALL"
        if (supplied.searchText !== undefined) searchText = cleanText(supplied.searchText)
        stateApplied = true
        root.queueRunReport()
    }

    function rebuildLedgerRows() {
        var rows = []
        var groups = matterGroups || []
        for (var i = 0; i < groups.length; i++) {
            var group = groups[i] || ({})
            rows.push({ "kind": "group", "group": group })
            var entries = group.entries || []
            for (var j = 0; j < entries.length; j++) {
                rows.push({ "kind": "entry", "entry": entries[j], "group": group })
            }
            rows.push({ "kind": "subtotal", "group": group })
        }
        ledgerRows = rows
    }

    function runReport() {
        if (!docketAppRef) {
            hasError = true
            statusText = "The reporting service is not available."
            return
        }
        busy = true
        hasError = false
        lastExportPath = ""
        statusText = "Refreshing docketed time…"
        requestToken = "MTL-" + Date.now()
        docketAppRef.loadClientLedgerReport({
            "clientId": selectedClientId === "ALL" ? "" : selectedClientId,
            "billingClientId": selectedBillingClientId === "ALL" ? "" : selectedBillingClientId,
            "matterId": selectedMatterId === "ALL" ? "" : selectedMatterId,
            "startDate": fromDateText,
            "endDate": toDateText,
            "searchText": searchText,
            "showTime": true,
            "showFees": false,
            "showDisbursements": false,
            "showInvoices": false,
            "showPayments": false,
            "showCredits": false,
            "_requestToken": requestToken
        })
    }

    function showToast(message) {
        if (root.windowRef && typeof root.windowRef.appToast === "function") {
            root.windowRef.appToast(message)
        }
    }

    function exportPdf() {
        if (busy || !appRef || !appRef.saveReportPdf) return
        var result = appRef.saveReportPdf({
            "reportId": "matter_time_ledger",
            "exportPayload": {
                "title": "Matter Time Ledger",
                "filterSummary": filterSummary(),
                "filters": {
                    "fromDate": fromDateText,
                    "toDate": toDateText,
                    "client": selectedClientId === "ALL" ? "All Clients" : selectedClientLabel,
                    "billingClient": selectedBillingClientId === "ALL" ? "All Billing Clients" : selectedBillingClientLabel,
                    "matter": selectedMatterId === "ALL" ? "All Matters" : selectedMatterLabel,
                    "search": searchText
                },
                "matterGroups": matterGroups,
                "totals": matterTotals,
                "hasDistinctBillingClient": hasDistinctBillingClient,
                "config": { "title": "Matter Time Ledger", "orientation": "landscape" }
            }
        })
        if (result && result.ok) {
            lastExportPath = cleanText(result.path)
            statusText = cleanText(result.message || "PDF exported.")
            hasError = false
            showToast(statusText)
            if (lastExportPath) {
                // A completed export should feel complete: open the file the
                // user just requested rather than silently placing it in a
                // background folder.
                Qt.openUrlExternally("file:///" + lastExportPath.replace(/\\/g, "/"))
            }
        } else {
            hasError = true
            statusText = cleanText(result && result.message) || "The PDF could not be exported."
        }
    }

    function openZenWindow() {
        zenWindow.showCenteredOnInitiatingMonitor()
    }

    Connections {
        target: root.docketAppRef || null

        function onClientLedgerReportFinished(result) {
            if (root.requestToken && result._requestToken && result._requestToken !== root.requestToken) return
            if (result._jsonPayload) result = JSON.parse(result._jsonPayload)
            root.busy = false
            root.requestToken = ""
            if (!result.ok) {
                root.hasError = true
                root.statusText = root.cleanText(result.message) || "The time ledger could not be loaded."
                return
            }
            root.optionClients = result.optionClients || []
            root.optionBillingClients = result.optionBillingClients || []
            root.optionMatters = result.optionMatters || []
            if (root.selectedClientId !== "ALL") {
                root.selectedClientLabel = root.selectedOptionLabel(root.optionClients, root.selectedClientId, root.selectedClientLabel)
            }
            if (root.selectedBillingClientId !== "ALL") {
                root.selectedBillingClientLabel = root.selectedOptionLabel(root.optionBillingClients, root.selectedBillingClientId, root.selectedBillingClientLabel)
            }
            if (root.selectedMatterId !== "ALL") {
                root.selectedMatterLabel = root.selectedOptionLabel(root.optionMatters, root.selectedMatterId, root.selectedMatterLabel)
            }
            root.matterGroups = result.matterTimeGroups || []
            root.matterTotals = result.matterTimeTotals || ({ "entryCount": 0, "totalHours": 0, "totalGrossFee": 0, "totalNetFee": 0 })
            root.hasDistinctBillingClient = !!result.hasDistinctBillingClient
            root.rebuildLedgerRows()
            root.hasError = false
            var count = Number(root.matterTotals.entryCount || 0)
            root.statusText = count > 0
                ? count + " docket" + (count === 1 ? "" : "s") + " across " + root.matterGroups.length + " matter" + (root.matterGroups.length === 1 ? "." : "s.")
                : "No docketed time matches these filters."
        }
    }

    onStartupStateChanged: {
        if (startupState) applyState(startupState)
    }

    Component.onCompleted: {
        Qt.callLater(function() { root.applyState(root.startupState || ({})) })
    }

    Component {
        id: ledgerRowDelegate

        Rectangle {
            id: ledgerRow
            required property var modelData
            width: ListView.view ? ListView.view.width : 1200
            readonly property string kind: String(modelData.kind || "")
            readonly property var group: modelData.group || ({})
            readonly property var entry: modelData.entry || ({})
            height: kind === "group" ? 56 : (kind === "subtotal" ? 35 : 40)
            radius: kind === "entry" ? 0 : root.panelRadius
            color: kind === "group"
                ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                : (kind === "subtotal" ? Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.055) : "transparent")
            border.width: kind === "group" ? 1 : 0
            border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.34)

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 1
                visible: ledgerRow.kind === "group"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        text: ledgerRow.group.matterDisplay || ledgerRow.group.matterName || "Unassigned matter"
                        color: root.ink
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: root.formatMoney(ledgerRow.group.totalGrossFee)
                        color: root.accent
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: "Client: " + (ledgerRow.group.clientName || "—")
                        + (root.cleanText(ledgerRow.group.billingClientName) ? "  ·  Billing client: " + ledgerRow.group.billingClientName : "")
                    color: root.mutedInk
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10
                visible: ledgerRow.kind === "entry"

                Text { Layout.preferredWidth: 91; text: ledgerRow.entry.date || ""; color: root.ink; font.pixelSize: 12; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; text: ledgerRow.entry.description || "(No description)"; color: root.ink; font.pixelSize: 12; elide: Text.ElideRight }
                Text { Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight; text: root.formatHours(ledgerRow.entry.hours); color: root.ink; font.pixelSize: 12 }
                Text { Layout.preferredWidth: 93; horizontalAlignment: Text.AlignRight; text: root.formatMoney(ledgerRow.entry.rate); color: root.ink; font.pixelSize: 12 }
                Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: root.formatMoney(ledgerRow.entry.grossFee); color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                Text { Layout.preferredWidth: 96; text: ledgerRow.entry.invoiceRef || ledgerRow.entry.docketStatus || ledgerRow.entry.status || "WIP"; color: root.mutedInk; font.pixelSize: 11; elide: Text.ElideRight }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12
                visible: ledgerRow.kind === "subtotal"
                Text { Layout.fillWidth: true; text: "Matter subtotal · " + Number(ledgerRow.group.entryCount || 0) + " docket" + (Number(ledgerRow.group.entryCount || 0) === 1 ? "" : "s"); color: root.mutedInk; font.pixelSize: 11; font.weight: Font.DemiBold }
                Text { Layout.preferredWidth: 82; horizontalAlignment: Text.AlignRight; text: root.formatHours(ledgerRow.group.totalHours) + " h"; color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: root.formatMoney(ledgerRow.group.totalGrossFee); color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 68
            radius: root.panelRadius
            color: root.accentSurface
            border.width: 1
            border.color: root.accentBorder

            RowLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: "Matter Time Ledger"; color: root.ink; font.pixelSize: 20; font.weight: Font.Bold }
                    Text { text: "Docketed time grouped by matter · live data, read only"; color: root.mutedInk; font.pixelSize: 12 }
                }
                Rectangle {
                    Layout.preferredWidth: 126; Layout.preferredHeight: 32; radius: 16
                    color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.14)
                    border.width: 1
                    border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.42)
                    Text { anchors.centerIn: parent; text: "LIVE · READ ONLY"; color: root.accent; font.pixelSize: 10; font.weight: Font.DemiBold }
                    ToolTip.visible: livePillHover.hovered
                    ToolTip.text: "This ledger reads current docket records. It never edits time, WIP, invoices, or financial data."
                    HoverHandler { id: livePillHover }
                }
                // Every report action uses the same shared control.  The
                // prior raw Rectangles mixed custom colours with semantic
                // tokens, so light-mode Zen and the detached Export action
                // looked unrelated to the primary action.
                PillButton {
                    Layout.preferredWidth: 108
                    Layout.preferredHeight: 38
                    t: root.t
                    metrics: root.metrics
                    sfxBus: root.sfxBus
                    appStyle: root.appStyle
                    primary: false
                    text: "Zen View"
                    tooltipText: "Open this report in a dedicated presentation window"
                    onClicked: root.openZenWindow()
                }
                PillButton {
                    Layout.preferredWidth: 118
                    Layout.preferredHeight: 38
                    t: root.t
                    metrics: root.metrics
                    sfxBus: root.sfxBus
                    appStyle: root.appStyle
                    primary: true
                    enabled: !root.busy
                    text: root.busy ? "Exporting…" : "Export PDF"
                    tooltipText: "Save and open a branded PDF of this report"
                    onClicked: root.exportPdf()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: filtersLayout.implicitHeight + 20
            radius: root.panelRadius
            color: root.panelSurface
            border.width: 1
            border.color: root.border

            GridLayout {
                id: filtersLayout
                anchors.fill: parent
                anchors.margins: 10
                columns: root.width >= 1370 ? 7 : (root.width >= 960 ? 4 : 2)
                columnSpacing: 8
                rowSpacing: 8

                ModernComboBox {
                    id: clientFilter
                    t: root.t; metrics: root.metrics; label: "Client"; Layout.fillWidth: true; Layout.preferredHeight: root.fieldHeight
                    fullModel: root.optionLabels("All Clients", root.optionClients)
                    onActivated: function(index) {
                        if (index === 1) return
                        var option = root.optionForLabel(root.optionClients, fullModel[index], "All Clients")
                        root.selectedClientId = root.cleanText(option.id) || "ALL"
                        root.selectedClientLabel = root.cleanText(option.label) || "All Clients"
                        root.queueRunReport()
                    }
                }
                ModernComboBox {
                    id: billingFilter
                    t: root.t; metrics: root.metrics; label: "Billing Client"; Layout.fillWidth: true; Layout.preferredHeight: root.fieldHeight
                    fullModel: root.optionLabels("All Billing Clients", root.optionBillingClients)
                    onActivated: function(index) {
                        if (index === 1) return
                        var option = root.optionForLabel(root.optionBillingClients, fullModel[index], "All Billing Clients")
                        root.selectedBillingClientId = root.cleanText(option.id) || "ALL"
                        root.selectedBillingClientLabel = root.cleanText(option.label) || "All Billing Clients"
                        root.queueRunReport()
                    }
                }
                ModernComboBox {
                    id: matterFilter
                    t: root.t; metrics: root.metrics; label: "Matter"; Layout.fillWidth: true; Layout.preferredHeight: root.fieldHeight
                    fullModel: root.optionLabels("All Matters", root.optionMatters)
                    onActivated: function(index) {
                        if (index === 1) return
                        var option = root.optionForLabel(root.optionMatters, fullModel[index], "All Matters")
                        root.selectedMatterId = root.cleanText(option.id) || "ALL"
                        root.selectedMatterLabel = root.cleanText(option.label) || "All Matters"
                        root.queueRunReport()
                    }
                }
                ModernTextField {
                    id: fromDateField
                    t: root.t; metrics: root.metrics; label: "From"; datePickerEnabled: true; placeholderText: "YYYY-MM-DD"
                    Layout.preferredWidth: 136; Layout.preferredHeight: root.fieldHeight
                    text: root.fromDateText
                    onEditingFinished: { root.fromDateText = text; root.queueRunReport() }
                    onDatePickerDatePicked: function(date, isoText) { root.fromDateText = isoText; root.queueRunReport() }
                }
                ModernTextField {
                    id: toDateField
                    t: root.t; metrics: root.metrics; label: "To"; datePickerEnabled: true; placeholderText: "YYYY-MM-DD"
                    Layout.preferredWidth: 136; Layout.preferredHeight: root.fieldHeight
                    text: root.toDateText
                    onEditingFinished: { root.toDateText = text; root.queueRunReport() }
                    onDatePickerDatePicked: function(date, isoText) { root.toDateText = isoText; root.queueRunReport() }
                }
                ModernTextField {
                    id: searchFilter
                    t: root.t; metrics: root.metrics; label: "Search dockets"; placeholderText: "Description, reference…"
                    Layout.fillWidth: true; Layout.preferredHeight: root.fieldHeight
                    text: root.searchText
                    onEditingFinished: { root.searchText = text; root.queueRunReport() }
                }
                Rectangle {
                    Layout.preferredWidth: 108; Layout.preferredHeight: root.fieldHeight; radius: root.panelRadius
                    color: root.busy ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.42) : root.accent
                    Text { anchors.centerIn: parent; text: root.busy ? "Loading…" : "Refresh"; color: "white"; font.pixelSize: 13; font.weight: Font.DemiBold }
                    TapHandler { enabled: !root.busy; onTapped: root.runReport() }
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 7
            Repeater {
                model: [
                    { "label": "Today", "preset": "today" }, { "label": "This Week", "preset": "week" },
                    { "label": "Last 7 Days", "preset": "seven" }, { "label": "This Month", "preset": "month" },
                    { "label": "YTD", "preset": "ytd" }, { "label": "All Time", "preset": "all" }
                ]
                delegate: Rectangle {
                    id: quickRange
                    required property var modelData
                    height: 28; width: quickRangeText.implicitWidth + 26; radius: 14
                    color: rangeHover.hovered ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16) : Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.055)
                    border.width: 1; border.color: root.border
                    Text { id: quickRangeText; anchors.centerIn: parent; text: quickRange.modelData.label; color: root.ink; font.pixelSize: 11; font.weight: Font.DemiBold }
                    HoverHandler { id: rangeHover }
                    TapHandler { onTapped: root.setRange(quickRange.modelData.preset) }
                }
            }
            Text { width: 16; height: 1 }
            Text { text: root.filterSummary(); color: root.mutedInk; font.pixelSize: 11; height: 28; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Repeater {
                model: [
                    { "label": "Docketed time", "value": Number(root.matterTotals.entryCount || 0) },
                    { "label": "Billable hours", "value": root.formatHours(root.matterTotals.totalHours) + " h" },
                    { "label": "Gross fees", "value": root.formatMoney(root.matterTotals.totalGrossFee) }
                ]
                delegate: Rectangle {
                    id: summaryKpi
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 62; radius: root.panelRadius
                    color: root.panelSurface; border.width: 1; border.color: root.border
                    ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 2
                        Text { text: summaryKpi.modelData.label; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { text: summaryKpi.modelData.value; color: root.ink; font.pixelSize: 19; font.weight: Font.DemiBold }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.panelRadius
            color: root.panelSurface
            border.width: 1
            border.color: root.hasError ? SemanticTheme.tone(root.t, "danger") : root.border

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 0
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    Text {
                        Layout.fillWidth: true
                        text: root.statusText
                        color: root.hasError
                            ? SemanticTheme.tone(root.t, "danger")
                            : (root.lastExportPath ? root.positive : root.mutedInk)
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text { text: root.busy ? "Updating…" : Number(root.matterTotals.entryCount || 0) + " records"; color: root.mutedInk; font.pixelSize: 11 }
                }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 31; color: root.inputSurface; radius: root.panelRadius; border.width: 1; border.color: root.border
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 10
                        Text { Layout.preferredWidth: 91; text: "DATE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { Layout.fillWidth: true; text: "DESCRIPTION"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight; text: "HOURS"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 93; horizontalAlignment: Text.AlignRight; text: "RATE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: "GROSS FEES"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 96; text: "REFERENCE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                    }
                }
                ListView {
                    id: inlineLedgerList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.topMargin: 6
                    clip: true
                    spacing: 4
                    model: root.ledgerRows
                    delegate: ledgerRowDelegate
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    Text { anchors.centerIn: parent; visible: !root.busy && root.ledgerRows.length === 0; text: root.hasError ? "" : "No docketed time matches the chosen filters."; color: root.mutedInk; font.pixelSize: 13 }
                }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 43; Layout.topMargin: 7; radius: root.panelRadius; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12); border.width: 1; border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.30)
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                        Text { Layout.fillWidth: true; text: "Final summary · " + Number(root.matterTotals.entryCount || 0) + " docket" + (Number(root.matterTotals.entryCount || 0) === 1 ? "" : "s") + " across " + root.matterGroups.length + " matter" + (root.matterGroups.length === 1 ? "" : "s"); color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight; text: root.formatHours(root.matterTotals.totalHours) + " h"; color: root.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: root.formatMoney(root.matterTotals.totalGrossFee); color: root.accent; font.pixelSize: 14; font.weight: Font.Bold }
                    }
                }
            }
        }
    }

    Window {
        id: zenWindow
        visible: false
        width: 1360
        height: 820
        minimumWidth: 1040
        minimumHeight: 620
        title: "Matter Time Ledger — Zen View"
        color: root.appSurface
        transientParent: root.windowRef || null

        function showCenteredOnInitiatingMonitor() {
            var sourceWindow = root.windowRef
            var sourceScreen = sourceWindow && sourceWindow.screen ? sourceWindow.screen : null
            if (sourceScreen) {
                var screenX = Number(sourceScreen.virtualX || 0)
                var screenY = Number(sourceScreen.virtualY || 0)
                var screenW = Number(sourceScreen.width || zenWindow.width)
                var screenH = Number(sourceScreen.height || zenWindow.height)
                zenWindow.width = Math.max(zenWindow.minimumWidth, Math.min(Math.round(screenW * 0.96), screenW))
                zenWindow.height = Math.max(zenWindow.minimumHeight, Math.min(Math.round(screenH * 0.92), screenH))
                zenWindow.x = Math.round(screenX + (screenW - zenWindow.width) / 2)
                zenWindow.y = Math.round(screenY + (screenH - zenWindow.height) / 2)
            }
            zenWindow.show()
            zenWindow.raise()
            zenWindow.requestActivate()
        }

        onClosing: function(closeEvent) {
            closeEvent.accepted = false
            zenWindow.hide()
        }

        Rectangle {
            anchors.fill: parent
            color: root.appSurface
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 60; radius: root.panelRadius; color: root.accentSurface; border.width: 1; border.color: root.accentBorder
                    RowLayout { anchors.fill: parent; anchors.margins: 14
                        ColumnLayout { Layout.fillWidth: true; spacing: 1
                            Text { text: "Matter Time Ledger"; color: root.ink; font.pixelSize: 20; font.weight: Font.Bold }
                            Text { text: root.filterSummary(); color: root.mutedInk; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        PillButton {
                            id: zenExportButton
                            Layout.preferredWidth: 118
                            Layout.preferredHeight: 36
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            appStyle: root.appStyle
                            primary: true
                            enabled: !root.busy
                            text: root.busy ? "Exporting…" : "Export PDF"
                            tooltipText: "Save and open a branded PDF of this report"
                            onClicked: root.exportPdf()
                        }
                        PillButton {
                            Layout.preferredWidth: 76
                            Layout.preferredHeight: 36
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            appStyle: root.appStyle
                            primary: false
                            text: "Close"
                            onClicked: zenWindow.hide()
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Repeater {
                        model: [
                            { "label": "Docketed time", "value": Number(root.matterTotals.entryCount || 0) },
                            { "label": "Billable hours", "value": root.formatHours(root.matterTotals.totalHours) + " h" },
                            { "label": "Gross fees", "value": root.formatMoney(root.matterTotals.totalGrossFee) }
                        ]
                        delegate: Rectangle {
                            id: zenKpi
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 54
                            radius: root.panelRadius
                            color: root.panelSurface
                            border.width: 1
                            border.color: root.border
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 9
                                spacing: 1
                                Text { text: zenKpi.modelData.label; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { text: zenKpi.modelData.value; color: root.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                            }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: root.panelRadius; color: root.panelSurface; border.width: 1; border.color: root.border
                    ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 0
                        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 31; color: root.inputSurface; radius: root.panelRadius; border.width: 1; border.color: root.border
                            RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 10
                                Text { Layout.preferredWidth: 91; text: "DATE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { Layout.fillWidth: true; text: "DESCRIPTION"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight; text: "HOURS"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 93; horizontalAlignment: Text.AlignRight; text: "RATE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: "GROSS FEES"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 96; text: "REFERENCE"; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.DemiBold }
                            }
                        }
                        ListView { Layout.fillWidth: true; Layout.fillHeight: true; Layout.topMargin: 6; clip: true; spacing: 4; model: root.ledgerRows; delegate: ledgerRowDelegate; ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded } }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 43
                            Layout.topMargin: 7
                            radius: root.panelRadius
                            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                            border.width: 1
                            border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.30)
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                Text { Layout.fillWidth: true; text: "Final summary"; color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight; text: root.formatHours(root.matterTotals.totalHours) + " h"; color: root.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                Text { Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight; text: root.formatMoney(root.matterTotals.totalGrossFee); color: root.accent; font.pixelSize: 14; font.weight: Font.Bold }
                            }
                        }
                    }
                }
            }
        }
    }
}
