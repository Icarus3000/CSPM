pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var metrics
    property var appRef
    property var windowRef
    property var docketAppRef: (root.appRef && root.appRef.docketing) ? root.appRef.docketing : null
    property var sfxBus
    property int fieldHeightPx: 52
    property bool autoLoadOnVisible: true
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : (((typeof app !== "undefined") && app !== null && app.appStyle) ? String(app.appStyle) : "Professional")
    readonly property bool isProMode: appStyle === "Professional"
    property real sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : 8

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    // State
    signal reportWindowRequested(var reportDocument)
    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)

    function transitionToWipBilling() {
        var draftIds = []
        for (var i = 0; i < root.reportEntries.length; i++) {
            var item = root.reportEntries[i]
            if (item.type === "Time" || item.type === "Fee" || item.type === "Disbursement") {
                var st = String(item.status || "").toLowerCase()
                if (st !== "billed" && st !== "merged") {
                    var id = (item.type === "Time" || item.type === "Fee") ? item.entryId : item.disbursementId
                    if (id) draftIds.push(String(id))
                }
            }
        }
        
        if (draftIds.length <= 0) {
            root.statusText = "No unbilled items to bill."
            root.hasError = true
            if (typeof appToast === 'function') {
                appToast("No unbilled WIP found for this selection.")
            } else if (root.windowRef && typeof root.windowRef.appToast === 'function') {
                root.windowRef.appToast("No unbilled WIP found for this selection.")
            }
            return
        }
        
        var state = {
            "idsToDraft": draftIds,
            "clientIdToDraft": root.selectedClientId,
            "clientNameToDraft": root.selectedClientLabel
        }
        
        root.workspaceOpenRequested(2, "C01", state)
    }

    property bool busy: false
    property string statusText: "Select a client and click Load Report."
    property bool hasError: false

    // Filter state
    property string selectedClientId: "ALL"
    property string selectedClientLabel: ""
    property string fromDateText: ""
    property string toDateText: ""
    property string searchText: ""

    // Entry type filter toggles
    property bool showTime: true
    property bool showFees: true
    property bool showDisbursements: true
    property bool showInvoices: true
    property bool showPayments: true
    property bool showCredits: true
    property bool excludeHst: false
    property bool showUnbilledOnly: false

    // Edit Invoice dialog state
    property bool _editDialogVisible: false
    property string _editInvoiceNum: ""
    property string _editInvoiceClient: ""
    property string _editInvoiceDate: ""
    property real _editFees: 0
    property real _editDisb: 0
    property real _editTax: 0
    property string _editInvoiceError: ""
    property string _editBillTo: ""
    property string _editSubClient: ""
    property bool _editModeIsReissue: false

    function openEditInvoiceDialog(entry, isReissue) {
        root._editModeIsReissue = !!isReissue
        root._editInvoiceNum = String(entry.invoiceRef || "")
        root._editInvoiceClient = String(entry.invoiceClientName || entry.clientName || "")
        root._editInvoiceDate = String(entry.date || "")
        root._editFees = Number(entry.invoiceFees || 0)
        root._editDisb = Number(entry.invoiceDisb || 0)
        root._editTax = Number(entry.invoiceTax || 0)
        root._editBillTo = String(entry.invoiceBillTo || "")
        root._editSubClient = String(entry.invoiceSubClient || "")
        root._editInvoiceError = ""
        root._editDialogVisible = true
    }

    function saveEditInvoice() {
        if (!root.docketAppRef) {
            root._editInvoiceError = "Backend not available."
            return
        }
        var fees = parseFloat(editFeesField.text) || 0
        var disb = parseFloat(editDisbField.text) || 0
        var payload = {
            "invoiceNum": root._editInvoiceNum,
            "invoiceDate": editDateField.text,
            "clientName": root._editInvoiceClient,
            "subClient": root._editSubClient,
            "billToClient": root._editBillTo,
            "totalFees": fees,
            "totalDisbursements": disb,
            "totalTax": tax,
            "aggregateBilled": aggregate
        }
        
        if (root._editModeIsReissue) {
            root.docketAppRef.reverseAndReissueInvoice(payload)
        } else {
            root.docketAppRef.updateInvoiceLogEntry(payload)
        }
    }

    // Data
    property var reportData: null

    property string selectedBillingClientId: "ALL"
    property string selectedBillingClientLabel: "All Billing Clients"
    property string selectedMatterId: "ALL"
    property string selectedMatterLabel: "All Matters"
    
    property var optionBillingClients: []
    property var optionMatters: []
    
    readonly property int tableSideMarginPx: 12
    readonly property int tableColumnSpacingPx: 6
    readonly property int tableCellPadXPx: 8
    readonly property int tableResizeHandleWidthPx: 8
    readonly property int tableResizeHandleGapPx: 4
    property string tablePreferencesId: "clientLedgerReport_v3"
    property bool columnPreferencesLoaded: false
    property bool suppressColumnPreferenceSave: true

    property var columns: [
        { key: "date", label: "Date", width: 96, defaultWidth: 96, minWidth: 64, align: "left", fmt: "text", visible: true, resizable: true },
        { key: "clientName", label: "Client", width: 140, defaultWidth: 140, minWidth: 90, align: "left", fmt: "text", visible: true, resizable: true },
        { key: "billingParentName", label: "Billing Client", width: 130, defaultWidth: 130, minWidth: 110, align: "left", fmt: "text", visible: true, resizable: true },
        { key: "matterName", label: "Matter", width: 140, defaultWidth: 140, minWidth: 90, align: "left", fmt: "text", visible: true, resizable: true },
        { key: "type", label: "Type", width: 90, defaultWidth: 90, minWidth: 70, align: "left", fmt: "type", visible: true, resizable: true },
        { key: "description", label: "Description", width: 210, defaultWidth: 210, minWidth: 150, align: "left", fmt: "text", visible: true, resizable: true },
        { key: "hours", label: "Hours", width: 68, defaultWidth: 68, minWidth: 50, align: "right", fmt: "decimal1", visible: true, resizable: true },
        { key: "debit", label: "Debit", width: 96, defaultWidth: 96, minWidth: 70, align: "right", fmt: "currency", visible: true, resizable: true },
        { key: "credit", label: "Credit", width: 96, defaultWidth: 96, minWidth: 70, align: "right", fmt: "currency", visible: true, resizable: true },
        { key: "balance", label: "Balance", width: 110, defaultWidth: 110, minWidth: 86, align: "right", fmt: "currency", visible: true, resizable: false }
    ]

    Timer {
        id: columnPreferenceSaveTimer
        interval: 300
        repeat: false
        onTriggered: root.saveColumnPreferencesNow()
    }

    function applyColumnPreferences(preferences) {
        if (!preferences || !preferences.columns) return
        var used = {}
        var nextColumns = []
        
        for (var p = 0; p < preferences.columns.length; p++) {
            var pref = preferences.columns[p]
            var key = pref.key
            if (!key || used[key]) continue
            for (var i = 0; i < root.columns.length; i++) {
                if (root.columns[i].key === key) {
                    var merged = Object.assign({}, root.columns[i])
                    if (pref.width !== undefined) merged.width = Math.max(merged.minWidth || 50, Number(pref.width))
                    if (pref.visible !== undefined) merged.visible = !!pref.visible
                    nextColumns.push(merged)
                    used[key] = true
                    break
                }
            }
        }
        for (var d = 0; d < root.columns.length; d++) {
            if (!used[root.columns[d].key]) {
                nextColumns.push(Object.assign({}, root.columns[d]))
            }
        }
        root.suppressColumnPreferenceSave = true
        root.columns = nextColumns
        root.suppressColumnPreferenceSave = false
    }

    function loadColumnPreferences() {
        if (root.columnPreferencesLoaded) return
        if (!root.appRef || typeof root.appRef.getTablePreferences !== "function") return
        root.suppressColumnPreferenceSave = true
        var preferences = root.appRef.getTablePreferences(root.tablePreferencesId)
        if (preferences && preferences.ok && preferences.columns && preferences.columns.length > 0)
            root.applyColumnPreferences(preferences)
        root.columnPreferencesLoaded = true
        root.suppressColumnPreferenceSave = false
    }

    function columnPreferencesSnapshot() {
        var saved = []
        for (var i = 0; i < root.columns.length; i++) {
            var c = root.columns[i]
            saved.push({
                "key": c.key,
                "width": c.width,
                "visible": c.visible !== false
            })
        }
        return {
            "version": 1,
            "columns": saved
        }
    }

    function scheduleColumnPreferenceSave() {
        if (!root.columnPreferencesLoaded || root.suppressColumnPreferenceSave) return
        if (!root.appRef || typeof root.appRef.saveTablePreferences !== "function") return
        columnPreferenceSaveTimer.restart()
    }

    function saveColumnPreferencesNow() {
        if (columnPreferenceSaveTimer.running) columnPreferenceSaveTimer.stop()
        if (!root.columnPreferencesLoaded || root.suppressColumnPreferenceSave) return false
        if (!root.appRef || typeof root.appRef.saveTablePreferences !== "function") return false
        return root.appRef.saveTablePreferences(root.tablePreferencesId, root.columnPreferencesSnapshot())
    }

    function toggleColumnVisibility(idx) {
        if (idx < 0 || idx >= root.columns.length) return
        var cols = root.columns.slice()
        cols[idx].visible = !cols[idx].visible
        
        var visibleCount = 0
        for (var i = 0; i < cols.length; i++) if (cols[i].visible) visibleCount++
        if (visibleCount === 0) cols[idx].visible = true
        
        root.columns = cols
        root.scheduleColumnPreferenceSave()
    }

    function toggleColumnVisibilityByKey(key) {
        for (var i = 0; i < root.columns.length; i++) {
            if (root.columns[i].key === key) {
                toggleColumnVisibility(i)
                return
            }
        }
    }

    function columnsSnapshot(includeHidden) {
        var arr = []
        for (var i = 0; i < root.columns.length; i++) {
            var c = root.columns[i]
            if (!includeHidden && !c.visible) continue
            arr.push({
                "label": c.label || "",
                "key": c.key || "",
                "align": c.align === "right" ? "right" : "left",
                "width": c.width,
                "defaultWidth": c.defaultWidth || c.width,
                "format": c.fmt === "text" ? "" : (c.fmt || "")
            })
        }
        return arr
    }

    property var optionClients: []
    property var allEntries: []
    property bool zenMode: false
    property var reportSummary: {
        var s = {
            wipFees: 0.0,
            wipDisb: 0.0,
            wipTotal: 0.0,
            arBilled: 0.0,
            arPaid: 0.0,
            arOutstanding: 0.0,
            totalHours: 0.0
        }
        var entries = root.reportEntries || []
        
        var grossBilled = 0.0
        var taxBilled = 0.0
        var grossPaid = 0.0
        
        for (var i = 0; i < entries.length; i++) {
            var e = entries[i]
            var type = String(e.type || "")
            var debit = e.debit || 0
            var credit = e.credit || 0
            
            if (type === "Time") {
                s.totalHours += (e.hours || 0)
                if (e.status === "WIP") {
                    s.wipFees += debit
                    s.wipTotal += debit
                }
            } else if (type === "Fee") {
                if (e.status === "WIP") {
                    s.wipFees += debit
                    s.wipTotal += debit
                }
            } else if (type === "Disbursement") {
                if (!e.invoiceRef) {
                    s.wipDisb += debit
                    s.wipTotal += debit
                }
            } else if (type === "Invoice") {
                grossBilled += debit
                taxBilled += (e.tax || 0)
            } else if (type === "Payment" || type === "Credit/Adj") {
                grossPaid += credit
            }
        }
        
        var grossOutstanding = grossBilled - grossPaid
        
        if (root.excludeHst) {
            var netRatio = grossBilled > 0 ? ((grossBilled - taxBilled) / grossBilled) : 1.0
            s.arBilled = grossBilled - taxBilled
            s.arPaid = grossPaid * netRatio
            s.arOutstanding = grossOutstanding * netRatio
        } else {
            s.arBilled = grossBilled
            s.arPaid = grossPaid
            s.arOutstanding = grossOutstanding
        }
        
        s.totalFees = s.arBilled + s.wipTotal
        
        return s
    }
    property var clientInfo: ({})
    property string _requestToken: ""

    // Filtered entries (recomputed when toggles or search change)
    property var reportEntries: {
        var src = root.allEntries || []
        var filtered = []
        var q = String(root.searchText || "").trim().toLowerCase()
        for (var i = 0; i < src.length; i++) {
            var e = src[i]
            var t = String(e.type || "")
            if (t === "Time" && !root.showTime) continue
            if (t === "Fee" && !root.showFees) continue
            if (t === "Disbursement" && !root.showDisbursements) continue
            if (t === "Invoice" && !root.showInvoices) continue
            if (t === "Payment" && !root.showPayments) continue
            if (t === "Credit/Adj" && !root.showCredits) continue
            
            if (root.showUnbilledOnly) {
                if (e.invoiceRef) continue
                if ((t === "Time" || t === "Fee") && e.status !== "WIP") continue
            }
            
            if (q.length > 0) {
                var hay = (String(e.date || "") + " " + t + " " + String(e.description || "") + " " + String(e.matter || "")).toLowerCase()
                if (hay.indexOf(q) < 0) continue
            }
            filtered.push(e)
        }
        
        // Apply Sort
        filtered.sort(function(a, b) {
            var valA = a[root.sortColumn] || ""
            var valB = b[root.sortColumn] || ""
            if (root.sortColumn === "hours" || root.sortColumn === "debit" || root.sortColumn === "credit" || root.sortColumn === "balance") {
                valA = Number(valA)
                valB = Number(valB)
            } else {
                valA = String(valA).toLowerCase()
                valB = String(valB).toLowerCase()
            }
            if (valA < valB) return root.sortAsc ? -1 : 1
            if (valA > valB) return root.sortAsc ? 1 : -1
            
            // Secondary Sort: Chronological order within the same primary column tie
            // Ensure Invoices come before Payments, but after Time
            function getChronologicalWeight(entry) {
                var t = String(entry.type || "")
                if (t === "Time" || t === "Fee" || t === "Disbursement") return 10;
                if (t === "Invoice") {
                    var sub = String(entry.invoiceSubType || "")
                    if (sub === "wipTransfer") return 20;
                    if (sub === "fees") return 21;
                    if (sub === "tax") return 22;
                    return 29;
                }
                if (t === "Payment" || t === "Credit/Adj") return 80;
                return 50; 
            }
            
            var weightA = getChronologicalWeight(a)
            var weightB = getChronologicalWeight(b)
            
            if (weightA !== weightB) {
                return root.sortAsc ? (weightA - weightB) : (weightB - weightA)
            }
            
            return 0
        })

        var out = filtered
        // Recompute running balance on filtered set (only for A/R)
        var running = 0.0
        
        var grossB = 0.0
        var taxB = 0.0
        for (var k = 0; k < out.length; k++) {
            if (out[k].type === "Invoice") {
                grossB += (out[k].debit || 0)
                taxB += (out[k].tax || 0)
            }
        }
        var netRatio = grossB > 0 ? ((grossB - taxB) / grossB) : 1.0

        for (var j = 0; j < out.length; j++) {
            var o = out[j]
            var isAR = (o.type === "Invoice" || o.type === "Payment" || o.type === "Credit/Adj")
            
            var d = o.debit || 0
            var c = o.credit || 0
            
            if (root.excludeHst && isAR) {
                if (o.type === "Invoice") d -= (o.tax || 0)
                if (o.type === "Payment" || o.type === "Credit/Adj") c *= netRatio
            }
            
            running += (d - c)
            
            var mod = { filteredBalance: Math.round(running * 100) / 100 }
            if (root.excludeHst && isAR) {
                mod.debit = d
                mod.credit = c
            }
            
            out[j] = Object.assign({}, o, mod)
        }
        return out
    }

    // Theme
    property color _surfaceColor: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : ((root.t && root.t.panel2) ? root.t.panel2 : "#1A1A1A")
    property color _surfaceColor2: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : ((root.t && root.t.panel) ? root.t.panel : "#111111")
    property color _textPrimary: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : ((root.t && root.t.text) ? root.t.text : "#FFFFFF")
    property color _textMuted: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : Qt.rgba(root._textPrimary.r, root._textPrimary.g, root._textPrimary.b, 0.55)
    property color _accent: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : ((root.t && root.t.accent) ? root.t.accent : "#2979FF")
    property color _borderSubtle: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color _tableHeaderFill: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : Qt.rgba(0, 0, 0, 0.35)
    property color _tableAltFill: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : Qt.rgba(1, 1, 1, 0.04)
    property color _tableRule: root.isProMode ? root._borderSubtle : Qt.rgba(1, 1, 1, 0.05)
    property color _inputBg: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : Qt.rgba(1, 1, 1, 0.06)
    property color _successColor: "#4CAF50"
    property color _warnColor: "#FF9800"
    property color _errorColor: "#F44336"
    property color _paymentColor: "#66BB6A"
    property color _disbColor: "#FF7043"
    property color _invoiceColor: "#42A5F5"

    // ── Connections to backend ──────────────────────────────────────────
    Connections {
        target: root.docketAppRef || null
        function onClientLedgerReportFinished(result) {
            if (root._requestToken && result._requestToken && result._requestToken !== root._requestToken) return
            
            if (result._jsonPayload) {
                result = JSON.parse(result._jsonPayload)
            }
            
            root.busy = false
            root._requestToken = ""
            if (!result.ok) {
                root.hasError = true
                root.statusText = String(result.message || "Error loading report.")
                return
            }
            root.hasError = false

            root.optionBillingClients = result.optionBillingClients || []
            root.optionMatters = result.optionMatters || []
            root.optionClients = result.optionClients || []

            root.allEntries = result.entries || []
            root.clientInfo = result.client || ({})
            root.reportData = result
            var n = root.allEntries.length
            if (n > 0) {
                root.statusText = n + " entries loaded."
            } else if (root.selectedClientId && root.selectedClientId !== "ALL") {
                root.statusText = "No ledger entries found for this client."
            } else {
                root.statusText = String(result.message || "Select a client to load the ledger.")
            }
        }
        function onInvoiceLogEntryUpdated(result) {
            if (!result.ok) {
                root._editInvoiceError = String(result.message || "Failed to save invoice.")
                return
            }
            root._editDialogVisible = false
            root._editInvoiceError = ""
            Qt.callLater(root.runReport)
        }
    }

    
    function openReportWindow() {
        var doc = {
            "title": "Client Ledger Report",
            "filterSummary": "Client: " + selectedClientLabel + 
                             (selectedBillingClientId !== "ALL" ? " | Billing: " + selectedBillingClientLabel : "") +
                             (selectedMatterId !== "ALL" ? " | Matter: " + selectedMatterLabel : "") +
                             (fromDateText ? " | From: " + fromDateText : "") + 
                             (toDateText ? " | To: " + toDateText : "") + 
                             (searchText ? " | Search: '" + searchText + "'" : ""),
            "exportPayload": {
                "source": "ClientLedger",
                "clientId": selectedClientId,
                "billingClientId": selectedBillingClientId,
                "matterId": selectedMatterId,
                "fromDate": fromDateText,
                "toDate": toDateText,
                "searchText": searchText,
                "showTime": root.showTime,
                "showFees": root.showFees,
                "showDisbursements": root.showDisbursements,
                "showInvoices": root.showInvoices,
                "showPayments": root.showPayments,
                "showCredits": root.showCredits,
                "showUnbilledOnly": root.showUnbilledOnly
            },
            "sections": [
                {
                    "sectionId": "detail",
                    "title": "Ledger Entries",
                    "type": "table",
                    "columns": root.columnsSnapshot(false),
                    "rows": root.reportEntries
                }
            ]
        }
        root.reportWindowRequested(doc)
    }

    property string sortColumn: "date"
    property bool sortAsc: true

    function sortEntries(col) {
        if (root.sortColumn === col) {
            root.sortAsc = !root.sortAsc
        } else {
            root.sortColumn = col
            root.sortAsc = true
        }
    }

    function runReport() {
        if (!root.docketAppRef) {
            root.statusText = "Backend not available."
            root.hasError = true
            return
        }
        root.busy = true
        root.hasError = false
        root.statusText = "Loading..."
        root._requestToken = "CLR-" + Date.now()
        var payload = {
            "clientId": root.selectedClientId || "",
            "billingClientId": root.selectedBillingClientId || "",
            "matterId": root.selectedMatterId || "",
            "startDate": root.fromDateText || "",
            "endDate": root.toDateText || "",
            "_requestToken": root._requestToken
        }
        root.docketAppRef.loadClientLedgerReport(payload)
    }

    function loadClientList() {
        if (!root.docketAppRef) return
        root.busy = true
        root._requestToken = "CLR-init-" + Date.now()
        root.docketAppRef.loadClientLedgerReport({
            "clientId": "",
            "_requestToken": root._requestToken
        })
    }

    onAppRefChanged: {
        if (!root.columnPreferencesLoaded)
            Qt.callLater(root.loadColumnPreferences)
    }

    Component.onCompleted: {
        Qt.callLater(root.loadColumnPreferences)
        if (root.autoLoadOnVisible) {
            Qt.callLater(root.loadClientList)
        }
    }

    // ── Layout ─────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 4
        spacing: 10

        ScrollView {
            Layout.fillWidth: true
            Layout.maximumHeight: parent.height * 0.45
            Layout.preferredHeight: topContent.implicitHeight + 16
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            
            ColumnLayout {
                id: topContent
                width: parent.width
                spacing: 10

        // ══════════════════════════════════════════════════════
        // ROW 1 — Client, Dates, Load button
        // ══════════════════════════════════════════════════════
        GridLayout {
            visible: !root.zenMode
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            columns: root.width > 1250 ? 8 : (root.width > 850 ? 4 : (root.width > 550 ? 2 : 1))
            rowSpacing: 10
            columnSpacing: 10

            // Client dropdown
            ModernComboBox {
                id: clientCombo
                t: root.t
                metrics: root.metrics
                label: "Client"
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                sortSmartFilterResults: false
                fullModel: {
                    var labels = ["All Clients", "---"]
                    var opts = root.optionClients || []
                    var sortedOpts = []
                    for (var i = 0; i < opts.length; i++) {
                        var lbl = String(opts[i].label || opts[i].id || "")
                        if (sortedOpts.indexOf(lbl) === -1) {
                            sortedOpts.push(lbl)
                        }
                    }
                    sortedOpts.sort(function(a, b) { return a.localeCompare(b) })
                    for (var j = 0; j < sortedOpts.length; j++) {
                        labels.push(sortedOpts[j])
                    }
                    return labels
                }
                onActivated: function(index) {
                    if (index === 0) {
                        root.selectedClientId = "ALL"
                        root.selectedClientLabel = "All Clients"
                    } else if (index > 1) {
                        var chosenLabel = clientCombo.fullModel[index]
                        root.selectedClientId = chosenLabel
                        root.selectedClientLabel = chosenLabel
                    }
                }
            }

            // Billing Client dropdown
            ModernComboBox {
                id: billingCombo
                t: root.t
                metrics: root.metrics
                label: "Billing Client"
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                sortSmartFilterResults: false
                fullModel: {
                    var labels = ["All Billing Clients", "---"]
                    var opts = root.optionBillingClients || []
                    var sortedOpts = []
                    for (var i = 0; i < opts.length; i++) {
                        var lbl = String(opts[i].label || opts[i].id || "")
                        if (sortedOpts.indexOf(lbl) === -1) {
                            sortedOpts.push(lbl)
                        }
                    }
                    sortedOpts.sort(function(a, b) { return a.localeCompare(b) })
                    for (var j = 0; j < sortedOpts.length; j++) {
                        labels.push(sortedOpts[j])
                    }
                    return labels
                }
                onActivated: function(index) {
                    if (index === 0) {
                        root.selectedBillingClientId = "ALL"
                        root.selectedBillingClientLabel = "All Billing Clients"
                    } else if (index > 1) {
                        var chosenLabel = billingCombo.fullModel[index]
                        root.selectedBillingClientId = chosenLabel
                        root.selectedBillingClientLabel = chosenLabel
                    }
                }
            }

            // Matter dropdown
            ModernComboBox {
                id: matterCombo
                t: root.t
                metrics: root.metrics
                label: "Matter"
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                sortSmartFilterResults: false
                fullModel: {
                    var labels = ["All Matters", "---"]
                    var opts = root.optionMatters || []
                    var sortedOpts = []
                    for (var i = 0; i < opts.length; i++) {
                        var lbl = String(opts[i].label || opts[i].id || "")
                        if (sortedOpts.indexOf(lbl) === -1) {
                            sortedOpts.push(lbl)
                        }
                    }
                    sortedOpts.sort(function(a, b) { return a.localeCompare(b) })
                    for (var j = 0; j < sortedOpts.length; j++) {
                        labels.push(sortedOpts[j])
                    }
                    return labels
                }
                onActivated: function(index) {
                    if (index === 0) {
                        root.selectedMatterId = "ALL"
                        root.selectedMatterLabel = "All Matters"
                    } else if (index > 1) {
                        var chosenLabel = matterCombo.fullModel[index]
                        root.selectedMatterId = chosenLabel
                        root.selectedMatterLabel = chosenLabel
                    }
                }
            }

            // Date from
            ModernTextField {
                id: fromDateField
                t: root.t
                metrics: root.metrics
                label: "From Date"
                placeholderText: "yyyy-mm-dd"
                datePickerEnabled: true
                Layout.preferredWidth: 160
                Layout.preferredHeight: root.fieldHeightPx
                text: root.fromDateText
                onTextChanged: root.fromDateText = text
            }

            // Date to
            ModernTextField {
                id: toDateField
                t: root.t
                metrics: root.metrics
                label: "To Date"
                placeholderText: "yyyy-mm-dd"
                datePickerEnabled: true
                Layout.preferredWidth: 160
                Layout.preferredHeight: root.fieldHeightPx
                text: root.toDateText
                onTextChanged: root.toDateText = text
            }

            // Search
            ModernTextField {
                id: searchField
                t: root.t
                metrics: root.metrics
                label: "Search"
                placeholderText: "Filter entries…"
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                text: root.searchText
                onTextChanged: root.searchText = text
            }

            // Run button
            Rectangle {
                Layout.preferredWidth: 130
                Layout.preferredHeight: root.fieldHeightPx
                radius: root.sectionRadiusPx
                color: runMa.containsMouse
                    ? Qt.lighter(root._accent, 1.15)
                    : root._accent
                opacity: root.busy ? 0.5 : 1.0

                Text {
                    anchors.centerIn: parent
                    text: root.busy ? "Loading…" : "Load Report"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: runMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!root.busy) root.runReport()
                    }
                }
            }

            RowLayout {
                spacing: 8
                Layout.alignment: Qt.AlignVCenter
                // Bill Unbilled WIP button
                Rectangle {
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: root.fieldHeightPx
                    radius: root.sectionRadiusPx
                    color: billWipMa.containsMouse ? Qt.lighter(root._accent, 1.15) : "transparent"
                    border.width: 1
                    border.color: root._accent
                    visible: root.reportEntries.length > 0

                    Text {
                        anchors.centerIn: parent
                        text: "Bill Unbilled WIP"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: root._accent
                    }

                    MouseArea {
                        id: billWipMa
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.transitionToWipBilling()
                    }
                }

                // Print button
                Rectangle {
                    Layout.preferredWidth: 60
                    Layout.preferredHeight: root.fieldHeightPx
                    radius: root.sectionRadiusPx
                    color: printMa.containsMouse ? Qt.lighter(root._accent, 1.15) : "transparent"
                    border.width: 1
                    border.color: root._accent
                    visible: root.reportEntries.length > 0

                    Text {
                        anchors.centerIn: parent
                        text: "Print"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: root._accent
                    }

                    MouseArea {
                        id: printMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.openReportWindow()
                    }
                }
            }

        }

        // ══════════════════════════════════════════════════════
        // ROW 1.5 — Date Presets
        // ══════════════════════════════════════════════════════
        Flow {
            visible: !root.zenMode
            Layout.fillWidth: true
            spacing: 8
            
            Text {
                text: "Presets:"
                font.pixelSize: 13
                color: root._textMuted
                height: 30
                verticalAlignment: Text.AlignVCenter
            }
            
            Repeater {
                model: [
                    { label: "Today", preset: "TODAY" },
                    { label: "All Time", preset: "ALL" },
                    { label: "Last 30 Days", preset: "30" },
                    { label: "Last 90 Days", preset: "90" },
                    { label: "YTD", preset: "YTD" },
                    { label: "WIP", preset: "SLB" }
                ]
                
                Rectangle {
                    required property var modelData
                    required property int index
                    height: 30
                    width: presetLabel.implicitWidth + 24
                    radius: 15
                    color: presetMa.containsMouse ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.2) : Qt.rgba(root._textMuted.r, root._textMuted.g, root._textMuted.b, 0.1)
                    border.width: 1
                    border.color: Qt.rgba(root._textMuted.r, root._textMuted.g, root._textMuted.b, 0.2)
                    
                    Text {
                        id: presetLabel
                        anchors.centerIn: parent
                        text: modelData.label
                        font.pixelSize: 12
                        color: root._textPrimary
                    }
                    MouseArea {
                        id: presetMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var d = new Date()
                            function fmt(dt) {
                                var m = (dt.getMonth() + 1).toString().padStart(2, '0')
                                var day = dt.getDate().toString().padStart(2, '0')
                                return dt.getFullYear() + "-" + m + "-" + day
                            }
                            if (modelData.preset === "TODAY") {
                                root.fromDateText = fmt(d)
                                root.toDateText = fmt(d)
                            } else if (modelData.preset === "ALL") {
                                root.fromDateText = ""
                                root.toDateText = ""
                            } else if (modelData.preset === "30") {
                                root.toDateText = fmt(d)
                                d.setDate(d.getDate() - 30)
                                root.fromDateText = fmt(d)
                            } else if (modelData.preset === "90") {
                                root.toDateText = fmt(d)
                                d.setDate(d.getDate() - 90)
                                root.fromDateText = fmt(d)
                            } else if (modelData.preset === "YTD") {
                                root.toDateText = fmt(d)
                                root.fromDateText = d.getFullYear() + "-01-01"
                            } else if (modelData.preset === "SLB") {
                                root.fromDateText = ""
                                root.toDateText = ""
                                root.showInvoices = false
                                root.showPayments = false
                                root.showCredits = false
                                root.showTime = true
                                root.showFees = true
                                root.showDisbursements = true
                                root.searchText = ""
                                root.showUnbilledOnly = true
                            }
                        }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════
        // ROW 2 — Entry type filter chips
        // ══════════════════════════════════════════════════════
        Flow {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "Show:"
                font.pixelSize: 14
                font.weight: Font.Medium
                color: root._textMuted
                height: 30
                verticalAlignment: Text.AlignVCenter
            }

            Repeater {
                model: [
                    { label: "Time",           prop: "showTime",          color: root._textPrimary },
                    { label: "Fees",           prop: "showFees",          color: root._accent },
                    { label: "Disbursements",  prop: "showDisbursements", color: root._disbColor },
                    { label: "Invoices",       prop: "showInvoices",      color: root._invoiceColor },
                    { label: "Payments",       prop: "showPayments",      color: root._paymentColor },
                    { label: "Credits/Adj",    prop: "showCredits",       color: root._paymentColor }
                ]

                Rectangle {
                    required property var modelData
                    required property int index
                    property bool checked: root[modelData.prop]
                    height: 30
                    width: chipLabel.implicitWidth + 36
                    radius: 15
                    color: checked
                        ? Qt.rgba(modelData.color.r, modelData.color.g, modelData.color.b, 0.18)
                        : Qt.rgba(root._textPrimary.r, root._textPrimary.g, root._textPrimary.b, 0.06)
                    border.width: 1
                    border.color: checked
                        ? Qt.rgba(modelData.color.r, modelData.color.g, modelData.color.b, 0.45)
                        : Qt.rgba(root._textPrimary.r, root._textPrimary.g, root._textPrimary.b, 0.12)

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            width: 12; height: 12; radius: 3
                            color: checked ? modelData.color : Qt.rgba(root._textMuted.r, root._textMuted.g, root._textMuted.b, 0.3)
                            border.width: 1; border.color: checked ? modelData.color : root._textMuted

                            Text {
                                anchors.centerIn: parent
                                text: checked ? "✓" : ""
                                font.pixelSize: 10; font.weight: Font.Bold; color: "#FFF"
                            }
                        }
                        Text {
                            id: chipLabel
                            text: modelData.label
                            font.pixelSize: 13
                            font.weight: checked ? Font.DemiBold : Font.Normal
                            color: checked ? modelData.color : root._textMuted
                        }
                    }

                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root[modelData.prop] = !root[modelData.prop]
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Exclude HST Toggle
            Rectangle {
                height: 30
                width: hstLabel.implicitWidth + 36
                radius: 15
                color: root.excludeHst
                    ? Qt.rgba(root._warnColor.r, root._warnColor.g, root._warnColor.b, 0.18)
                    : Qt.rgba(root._textPrimary.r, root._textPrimary.g, root._textPrimary.b, 0.06)
                border.width: 1
                border.color: root.excludeHst
                    ? Qt.rgba(root._warnColor.r, root._warnColor.g, root._warnColor.b, 0.45)
                    : Qt.rgba(root._textPrimary.r, root._textPrimary.g, root._textPrimary.b, 0.12)

                RowLayout {
                    anchors.centerIn: parent
                    spacing: 6
                    Rectangle {
                        width: 12; height: 12; radius: 3
                        color: root.excludeHst ? root._warnColor : Qt.rgba(root._textMuted.r, root._textMuted.g, root._textMuted.b, 0.3)
                        border.width: 1; border.color: root.excludeHst ? root._warnColor : root._textMuted

                        Text {
                            anchors.centerIn: parent
                            text: root.excludeHst ? "✓" : ""
                            font.pixelSize: 10; font.weight: Font.Bold; color: "#FFF"
                        }
                    }
                    Text {
                        id: hstLabel
                        text: "Exclude HST"
                        font.pixelSize: 13
                        font.weight: root.excludeHst ? Font.DemiBold : Font.Normal
                        color: root.excludeHst ? root._warnColor : root._textMuted
                    }
                }

                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: root.excludeHst = !root.excludeHst
                }
            }

            Item { width: 8 }

            // Entry count badge
            Text {
                visible: root.allEntries.length > 0
                text: root.reportEntries.length + " of " + root.allEntries.length + " entries"
                font.pixelSize: 13
                color: root._textMuted
                height: 30
                verticalAlignment: Text.AlignVCenter
            }
            
            // Zen Mode Button
            Rectangle {
                width: zenLabel.implicitWidth + 24
                height: 30
                radius: 15
                color: zenHover.containsMouse ? root._surfaceColor2 : "transparent"
                border.width: 1
                border.color: root._borderSubtle

                Text {
                    id: zenLabel
                    anchors.centerIn: parent
                    text: root.zenMode ? "Show Filters ▼" : "Zen Mode ▲"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: root._textPrimary
                }
                MouseArea {
                    id: zenHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.zenMode = !root.zenMode
                }
            }
            
            // Gear icon for column settings
            Rectangle {
                width: 32
                height: 32
                radius: 4
                color: gearHover.containsMouse ? root._surfaceColor2 : "transparent"
                border.width: 1
                border.color: gearHover.containsMouse ? root._borderSubtle : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "⚙"
                    font.pixelSize: 16
                    color: root._textMuted
                }
                
                MouseArea {
                    id: gearHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: colSettingsMenu.popup(gearHover, -140, 32)
                }
                Menu {
                    id: colSettingsMenu
                    Instantiator {
                        model: root.columns
                        MenuItem {
                            required property int index
                            required property var modelData
                            text: modelData.label
                            checkable: true
                            checked: modelData.visible !== false
                            onTriggered: root.toggleColumnVisibility(index)
                        }
                        onObjectAdded: function(index, object) { colSettingsMenu.insertItem(index, object) }
                        onObjectRemoved: function(index, object) { colSettingsMenu.removeItem(object) }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════
        // ROW 3 — Summary Cards
        // ══════════════════════════════════════════════════════
        GridLayout {
            Layout.fillWidth: true
            columns: root.width > 1600 ? 7 : (root.width > 1200 ? 4 : (root.width > 800 ? 3 : (root.width > 500 ? 2 : 1)))
            rowSpacing: 8
            columnSpacing: 8
            visible: root.allEntries.length > 0 && !root.zenMode

            Repeater {
                model: [
                    { label: "Total Fees",                  key: "totalFees",       fmt: "$", color: root._textPrimary },
                    { label: "Total Disb (Unbilled)",       key: "wipDisb",         fmt: "$", color: root._disbColor },
                    { label: "Total WIP",                   key: "wipTotal",        fmt: "$", color: root._accent },
                    { label: "Total Hours",                 key: "totalHours",      fmt: "h", color: root._textMuted },
                    
                    { label: root.excludeHst ? "Net Revenue (Billed)" : "Total Invoiced (Billed)", key: "arBilled",    fmt: "$", color: root._invoiceColor },
                    { label: "Total Payments Received",     key: "arPaid",          fmt: "$", color: root._paymentColor },
                    { label: "Total A/R (Outstanding)",     key: "arOutstanding",   fmt: "$", color: root._warnColor }
                ]

                Rectangle {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    radius: root.sectionRadiusPx
                    color: root._surfaceColor2
                    border.width: 1
                    border.color: root._borderSubtle

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        spacing: 2

                        Text {
                            text: modelData.label
                            font.pixelSize: 13
                            font.weight: Font.Medium
                            color: root._textMuted
                            Layout.fillWidth: true
                        }
                        Text {
                            property real val: {
                                var s = root.reportSummary || ({})
                                var v = s[modelData.key]
                                return (v !== undefined && v !== null) ? Number(v) : 0
                            }
                            text: modelData.fmt === "$"
                                ? "$" + val.toLocaleString(Qt.locale(), 'f', 2)
                                : val.toLocaleString(Qt.locale(), 'f', 1)
                            font.pixelSize: 22
                            font.weight: Font.Bold
                            color: modelData.color
                            Layout.fillWidth: true
                        }
                        }
                    }
                }
            }

            // Bottom spacer to prevent wrapping cutoffs
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 16
            }

            } // End topContent ColumnLayout
        } // End top ScrollView

        // ══════════════════════════════════════════════════════
        // Status text (when no data)
        // ══════════════════════════════════════════════════════
        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            visible: root.allEntries.length <= 0 || root.hasError
            text: root.statusText
            font.pixelSize: 15
            font.weight: root.hasError ? Font.DemiBold : Font.Normal
            color: root.hasError ? root._errorColor : root._textMuted
            horizontalAlignment: Text.AlignHCenter
            topPadding: 40
        }

        // ══════════════════════════════════════════════════════
        // Table Header
        // ══════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            Layout.alignment: Qt.AlignTop
            color: root._tableHeaderFill
            radius: root.sectionRadiusPx
            visible: root.reportEntries.length > 0
            clip: true

            StandardTableHeader {
                id: tableHeader
                x: -ledgerListView.contentX
                width: Math.max(parent.width, tableHeader.totalColumnWidth + root.tableSideMarginPx)
                height: parent.height
                color: "transparent"
                
                columns: root.columns
                sortColumn: root.sortColumn
                sortAscending: root.sortAsc
                columnMargin: root.tableSideMarginPx
                columnSpacing: root.tableColumnSpacingPx
                dragDropKey: "clientLedgerColumnReorder"
                
                onSortRequested: function(key) {
                    root.sortEntries(key)
                }
                onConfigChanged: function(newColumns) {
                    root.columns = newColumns
                    root.scheduleColumnPreferenceSave()
                }
            }
        } // <--- CLOSE TABLE HEADER RECTANGLE

        // ══════════════════════════════════════════════════════
        // Table Body
        // ══════════════════════════════════════════════════════
        ListView {
            id: ledgerListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 150
            model: root.reportEntries
            clip: true
            visible: root.reportEntries.length > 0
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: Math.max(width, tableHeader.totalColumnWidth + root.tableSideMarginPx)

            ScrollBar.horizontal: ScrollBar {
                policy: ScrollBar.AsNeeded
            }
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }

            delegate: Rectangle {
                id: rowDelegate
                required property var modelData
                required property int index
                width: Math.max(ledgerListView.width, tableHeader.totalColumnWidth + root.tableSideMarginPx)
                height: 38
                color: {
                    if (rowHover.containsMouse) return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.07)
                    return index % 2 === 0 ? "transparent" : root._tableAltFill
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: root._tableRule
                }

                Row {
                    id: bodyRow
                    anchors.fill: parent
                    anchors.leftMargin: root.tableSideMarginPx
                    anchors.rightMargin: 0
                    spacing: root.tableColumnSpacingPx
                    
                    Repeater {
                        model: root.columns
                        delegate: Item {
                            id: bodyCol
                            required property int index
                            required property var modelData
                            property var colDef: modelData
                            property string columnKey: String(colDef && colDef.key !== undefined ? colDef.key : "")
                            visible: colDef ? (colDef.visible !== false) : false
                            width: tableHeader.columnWidthFor(columnKey)
                            height: parent ? parent.height : 38

                            Text {
                                anchors.fill: parent
                                anchors.margins: 0
                                leftPadding: root.tableCellPadXPx
                                rightPadding: index === root.columns.length - 1 ? 4 : root.tableCellPadXPx
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: colDef.align === "right" ? Text.AlignRight : Text.AlignLeft
                                elide: Text.ElideRight
                                font.pixelSize: Math.max(9, Math.round(14 * tableHeader.tableScale))
                                font.weight: colDef.fmt === "type" ? Font.Medium : (columnKey === "balance" ? Font.DemiBold : Font.Normal)

                                color: {
                                    if (columnKey === "type") {
                                        var et = String(rowDelegate.modelData.type || "")
                                        if (et === "Payment") return root._paymentColor
                                        if (et === "Disbursement") return root._disbColor
                                        if (et === "Invoice") return root._invoiceColor
                                        if (et === "Credit/Adj") return root._paymentColor
                                        if (et === "Fee") return root._accent
                                        return root._textPrimary
                                    }
                                    if (columnKey === "credit") return root._paymentColor
                                    if (columnKey === "balance") {
                                        var balRaw = rowDelegate.modelData.filteredBalance !== undefined ? rowDelegate.modelData.filteredBalance : rowDelegate.modelData.balance
                                        var bal = Number(balRaw !== undefined ? balRaw : 0)
                                        return bal < 0 ? root._paymentColor : (bal > 0 ? root._textPrimary : root._textMuted)
                                    }
                                    if (columnKey === "matterName") return root._textMuted
                                    return root._textPrimary
                                }

                                text: {
                                    if (colDef.fmt === "currency") {
                                        var valRaw = rowDelegate.modelData[columnKey]
                                        if (columnKey === "balance" && rowDelegate.modelData.filteredBalance !== undefined) {
                                            valRaw = rowDelegate.modelData.filteredBalance
                                        }
                                        var v = Number(valRaw !== undefined ? valRaw : 0)
                                        if (columnKey !== "balance" && v <= 0) return ""
                                        return "$" + v.toLocaleString(Qt.locale(), 'f', 2)
                                    }
                                    if (colDef.fmt === "decimal1") {
                                        var hrRaw = rowDelegate.modelData[columnKey]
                                        var hr = Number(hrRaw !== undefined ? hrRaw : 0)
                                        return hr > 0 ? hr.toFixed(1) : ""
                                    }
                                    var val = rowDelegate.modelData[columnKey]
                                    if (val === undefined && columnKey === "matterName") val = rowDelegate.modelData["matter"]
                                    return String(val !== undefined ? val : "")
                                }
                            }
                        }
                    }
                }

                MouseArea {
                    id: rowHover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: function(mouse) {
                        if (mouse.button === Qt.RightButton) {
                            var entry = rowDelegate.modelData
                            if (entry && entry.invoiceEditable) {
                                root._contextMenuEntry = entry
                                rowContextMenu.x = mouse.x
                                rowContextMenu.y = mouse.y
                                rowContextMenu.open()
                            }
                        } else if (mouse.button === Qt.LeftButton) {
                            var et = String(rowDelegate.modelData.type || "")
                            var invRef = rowDelegate.modelData.invoiceRef
                            var eId = rowDelegate.modelData.entryId
                            
                            if (invRef && (et === "Invoice" || et === "Fee" || et === "Disbursement" || et === "Time")) {
                                root.workspaceOpenRequested(2, "C04", {
                                    "selectedInvoiceNum": invRef
                                })
                            } else if (et === "Payment" || et === "Credit/Adj") {
                                root.workspaceOpenRequested(2, "C07", {
                                    "entityId": invRef
                                })
                            } else if (eId && et === "Time") {
                                root.workspaceOpenRequested(1, "B01", {
                                    "lastSavedEntryId": eId,
                                    "editRowData": rowDelegate.modelData,
                                    "returnToTileIndex": 2,
                                    "returnToNodeId": "C01"
                                })
                            } else if (eId && et === "Fee") {
                                root.workspaceOpenRequested(1, "B02", {
                                    "lastSavedEntryId": eId,
                                    "editRowData": rowDelegate.modelData,
                                    "returnToTileIndex": 2,
                                    "returnToNodeId": "C01"
                                })
                            }
                        }
                    }
                    onDoubleClicked: function(mouse) {
                        // Double click can safely trigger the same as single click
                        if (mouse.button === Qt.LeftButton) {
                            var et = String(rowDelegate.modelData.type || "")
                            var invRef = rowDelegate.modelData.invoiceRef
                            var eId = rowDelegate.modelData.entryId
                            
                            if (invRef && (et === "Invoice" || et === "Fee" || et === "Disbursement" || et === "Time")) {
                                root.workspaceOpenRequested(2, "C04", {
                                    "selectedInvoiceNum": invRef
                                })
                            } else if (et === "Payment" || et === "Credit/Adj") {
                                root.workspaceOpenRequested(2, "C07", {
                                    "entityId": invRef
                                })
                            } else if (eId && et === "Time") {
                                root.workspaceOpenRequested(1, "B01", {
                                    "lastSavedEntryId": eId,
                                    "editRowData": rowDelegate.modelData,
                                    "returnToTileIndex": 2,
                                    "returnToNodeId": "C01"
                                })
                            } else if (eId && et === "Fee") {
                                root.workspaceOpenRequested(1, "B02", {
                                    "lastSavedEntryId": eId,
                                    "editRowData": rowDelegate.modelData,
                                    "returnToTileIndex": 2,
                                    "returnToNodeId": "C01"
                                })
                            }
                        }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════
        // Layout Spacer (pushes everything up when list is empty)
        // ══════════════════════════════════════════════════════
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.reportEntries.length <= 0
        }
    }

    // ── Context menu entry holder ────────────────────────────────────
    property var _contextMenuEntry: null

    // ── Right-click context menu for invoice rows ────────────────────
    Popup {
        id: rowContextMenu
        width: editInvoiceLabel.implicitWidth + 40
        height: 36
        padding: 0
        background: Rectangle {
            color: root._surfaceColor2
            border.width: 1
            border.color: root._borderSubtle
            radius: root.isProMode ? 4 : 8
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: root.isProMode ? 3 : 6
            color: contextMa.containsMouse ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.12) : "transparent"

            Text {
                id: editInvoiceLabel
                anchors.centerIn: parent
                text: {
                    if (!root._contextMenuEntry) return ""
                    var fees = Number(root._contextMenuEntry.invoiceFees || 0)
                    var tax = Number(root._contextMenuEntry.invoiceTax || 0)
                    return (fees + tax) === 0 ? "Fill Missing Data" : "Reverse && Re-issue"
                }
                font.pixelSize: 13
                font.weight: Font.Medium
                color: root._textPrimary
            }
            MouseArea {
                id: contextMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    rowContextMenu.close()
                    if (root._contextMenuEntry) {
                        var fees = Number(root._contextMenuEntry.invoiceFees || 0)
                        var tax = Number(root._contextMenuEntry.invoiceTax || 0)
                        root.openEditInvoiceDialog(root._contextMenuEntry, (fees + tax) > 0)
                    }
                }
            }
        }
    }

    // ── Edit Invoice Dialog ──────────────────────────────────────────
    Popup {
        id: editInvoicePopup
        visible: root._editDialogVisible
        modal: true
        anchors.centerIn: parent
        width: 420
        height: editDialogCol.implicitHeight + 48
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onClosed: root._editDialogVisible = false

        background: Rectangle {
            color: root._surfaceColor
            border.width: 1
            border.color: root._borderSubtle
            radius: root.isProMode ? 6 : 12

            // Subtle shadow
            Rectangle {
                anchors.fill: parent
                anchors.margins: -1
                z: -1
                radius: parent.radius + 1
                color: "transparent"
                border.width: 2
                border.color: Qt.rgba(0, 0, 0, 0.15)
            }
        }

        ColumnLayout {
            id: editDialogCol
            anchors.fill: parent
            anchors.margins: 24
            spacing: 14

            // Title
            Text {
                text: root._editModeIsReissue ? "Reverse & Re-issue " + root._editInvoiceNum : "Edit Invoice " + root._editInvoiceNum
                font.pixelSize: 18
                font.weight: Font.Bold
                color: root._textPrimary
                Layout.fillWidth: true
            }

            // Client info (read-only)
            Text {
                text: "Client: " + root._editInvoiceClient
                font.pixelSize: 13
                color: root._textMuted
                Layout.fillWidth: true
                visible: root._editInvoiceClient.length > 0
            }

            // Error message
            Text {
                text: root._editInvoiceError
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: root._errorColor
                Layout.fillWidth: true
                visible: root._editInvoiceError.length > 0
                wrapMode: Text.WordWrap
            }

            // Warning message for Re-issue
            Text {
                text: "WARNING: This will permanently Void the original invoice and issue a new Amended (-A) copy. This action cannot be undone."
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: root._errorColor
                Layout.fillWidth: true
                visible: root._editModeIsReissue
                wrapMode: Text.WordWrap
            }

            // Invoice Date field
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Invoice Date (YYYY-MM-DD)"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: root._textMuted
                }
                TextField {
                    id: editDateField
                    Layout.fillWidth: true
                    font.pixelSize: 14
                    placeholderText: "YYYY-MM-DD"
                    text: root._editInvoiceDate
                }
            }

            // Total Fees field
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Total Fees"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: root._textMuted
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: root.isProMode ? 4 : 8
                    color: root._inputBg
                    border.width: 1
                    border.color: editFeesField.activeFocus ? root._accent : root._borderSubtle
                    TextInput {
                        id: editFeesField
                        anchors.fill: parent
                        anchors.margins: 8
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                        color: root._textPrimary
                        selectByMouse: true
                        text: root._editDialogVisible ? root._editFees.toFixed(2) : ""
                        validator: DoubleValidator { bottom: 0; decimals: 2 }
                    }
                }
            }

            // Total Disbursements field
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Total Disbursements"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: root._textMuted
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: root.isProMode ? 4 : 8
                    color: root._inputBg
                    border.width: 1
                    border.color: editDisbField.activeFocus ? root._accent : root._borderSubtle
                    TextInput {
                        id: editDisbField
                        anchors.fill: parent
                        anchors.margins: 8
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                        color: root._textPrimary
                        selectByMouse: true
                        text: root._editDialogVisible ? root._editDisb.toFixed(2) : ""
                        validator: DoubleValidator { bottom: 0; decimals: 2 }
                    }
                }
            }

            // Total Tax / HST field
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Total Tax (HST)"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: root._textMuted
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: root.isProMode ? 4 : 8
                    color: root._inputBg
                    border.width: 1
                    border.color: editTaxField.activeFocus ? root._accent : root._borderSubtle
                    TextInput {
                        id: editTaxField
                        anchors.fill: parent
                        anchors.margins: 8
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                        color: root._textPrimary
                        selectByMouse: true
                        text: root._editDialogVisible ? root._editTax.toFixed(2) : ""
                        validator: DoubleValidator { bottom: 0; decimals: 2 }
                    }
                }
            }

            // Aggregate (auto-calculated, read-only)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Aggregate Billed (auto-calculated)"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: root._textMuted
                }
                Text {
                    property real calcTotal: {
                        var f = parseFloat(editFeesField.text) || 0
                        var d = parseFloat(editDisbField.text) || 0
                        var t = parseFloat(editTaxField.text) || 0
                        return Math.round((f + d + t) * 100) / 100
                    }
                    text: "$" + calcTotal.toLocaleString(Qt.locale(), 'f', 2)
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: root._accent
                }
            }

            // Buttons
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 6
                spacing: 12

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: cancelLabel.implicitWidth + 32
                    height: 36
                    radius: root.isProMode ? 4 : 8
                    color: cancelMa.containsMouse ? Qt.rgba(root._textMuted.r, root._textMuted.g, root._textMuted.b, 0.12) : "transparent"
                    border.width: 1
                    border.color: root._borderSubtle
                    Text {
                        id: cancelLabel
                        anchors.centerIn: parent
                        text: "Cancel"
                        font.pixelSize: 14
                        font.weight: Font.Medium
                        color: root._textMuted
                    }
                    MouseArea {
                        id: cancelMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._editDialogVisible = false
                    }
                }

                Rectangle {
                    width: saveLabel.implicitWidth + 32
                    height: 36
                    radius: root.isProMode ? 4 : 8
                    color: saveMa.containsMouse ? Qt.lighter(root._accent, 1.15) : root._accent
                    Text {
                        id: saveLabel
                        anchors.centerIn: parent
                        text: root._editModeIsReissue ? "Confirm Re-issue" : "Save"
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: saveMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.saveEditInvoice()
                    }
                }
            }
        }
    }
}

