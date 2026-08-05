pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
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
    property int fieldHeightPx: 36
    property bool autoLoadOnVisible: true
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    property real sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : 8
    property bool busy: false
    property bool loadedOnce: false
    property bool hasError: false
    property string statusText: "Ready."
    property string asOfDateText: Qt.formatDate(new Date(), "yyyy-MM-dd")
    property string queryText: ""
    property string groupByMode: "client"
    property var excludedInvoices: []

    function fetchExcludedInvoices() {
        if (root.appRef && typeof root.appRef.getExcludedARInvoices === "function") {
            var ex = root.appRef.getExcludedARInvoices()
            if (ex && ex.length !== undefined) {
                root.excludedInvoices = root.sanitizedExcludedInvoices(ex)
            }
        }
    }

    function sanitizedExcludedInvoices(source) {
        var out = []
        var rows = source && source.length !== undefined ? source : []
        var seen = ({})
        for (var i = 0; i < rows.length; i++) {
            var raw = rows[i]
            var invoice = ""
            var client = ""
            if (raw && typeof raw === "object") {
                invoice = String(raw.invoice || raw.invoiceNumber || raw.reference || raw.id || "").trim()
                client = String(raw.client || raw.clientName || "").trim()
            } else {
                invoice = String(raw || "").trim()
            }
            if (invoice.length <= 0 || seen[invoice])
                continue
            seen[invoice] = true
            out.push({ "invoice": invoice, "client": client })
        }
        return out
    }

    function _buildExcludedSummaryText() {
        if (!root.excludedInvoices || root.excludedInvoices.length === 0) return ""
        var names = []
        for (var i = 0; i < root.excludedInvoices.length; i++) {
            var inv = root.excludedInvoices[i]
            names.push(String(inv.invoice || inv))
        }
        return "Excluded Invoices: " + names.join(", ")
    }

    function hideInvoice(invoice, clientName) {
        if (!invoice) return
        var newList = root.sanitizedExcludedInvoices(root.excludedInvoices)
        // Check if already in list
        var found = false
        for (var i = 0; i < newList.length; i++) {
            if ((newList[i].invoice || newList[i]) === invoice) {
                found = true; break;
            }
        }
        if (!found) {
            newList.push({ "invoice": invoice, "client": clientName || "" })
            root.excludedInvoices = newList
            if (root.appRef && typeof root.appRef.setExcludedARInvoices === "function") {
                root.appRef.setExcludedARInvoices(newList)
            }
            root.refreshReport()
        }
    }

    function unhideInvoice(invoice) {
        if (!invoice) return
        var newList = []
        var current = root.sanitizedExcludedInvoices(root.excludedInvoices)
        for (var i = 0; i < current.length; i++) {
            var inv = current[i]
            if ((inv.invoice || inv) !== invoice) {
                newList.push(inv)
            }
        }
        root.excludedInvoices = newList
        if (root.appRef && typeof root.appRef.setExcludedARInvoices === "function") {
            root.appRef.setExcludedARInvoices(newList)
        }
        root.refreshReport()
    }
    property var reportData: ({})

    property string tablePreferencesBaseId: "arAgingReport_v2"
    property var tableStates: ({})
    property int tableStateRevision: 0
    property string activeHeaderDragTableId: ""
    property string activeHeaderDragColumnKey: ""
    property string activeHeaderDropColumnKey: ""
    property bool tableResizeActive: false
    property string expandedTableId: ""
    readonly property int tableResizeHandleWidthPx: 16
    readonly property int tableCellPadXPx: 8

    readonly property color surfaceColor: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : ((root.t && root.t.panel2) ? root.t.panel2 : "#1A1A1A")
    readonly property color panelColor: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : ((root.t && root.t.panel) ? root.t.panel : "#111111")
    readonly property color inputColor: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : Qt.rgba(1, 1, 1, 0.06)
    readonly property color inkColor: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : ((root.t && root.t.text) ? root.t.text : "#FFFFFF")
    readonly property color mutedInkColor: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : Qt.rgba(root.inkColor.r, root.inkColor.g, root.inkColor.b, 0.72)
    readonly property color subtleInkColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : Qt.rgba(root.inkColor.r, root.inkColor.g, root.inkColor.b, 0.54)
    readonly property color borderColor: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : Qt.rgba(root.inkColor.r, root.inkColor.g, root.inkColor.b, 0.18)
    readonly property color accentColor: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : ((root.t && root.t.accent) ? root.t.accent : "#2979FF")

    signal reportWindowRequested(var reportDocument)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function ratioPx(ratio, minPx) {
        var baseWidth = (metrics && typeof metrics.contentW === "number")
            ? Math.max(1, Number(metrics.contentW))
            : Math.max(1, root.width > 0 ? root.width : 1280)
        var baseHeight = (metrics && typeof metrics.contentH === "number")
            ? Math.max(1, Number(metrics.contentH))
            : Math.max(1, root.height > 0 ? root.height : 720)
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(Math.min(baseWidth, baseHeight) * ratio))
    }

    function safeList(key) {
        if (!root.reportData || root.reportData[key] === undefined || root.reportData[key] === null)
            return []
        return root.reportData[key]
    }

    function summaryValue(key) {
        var summary = root.reportData && root.reportData.summary ? root.reportData.summary : ({})
        var n = Number(summary[key])
        return isFinite(n) ? n : 0
    }

    function money(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        n = Math.abs(n)
        var parts = n.toFixed(2).split(".")
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
        return sign + "$" + parts.join(".")
    }

    function toneColor(kind) {
        var tone = String(kind || "primary")
        if (tone === "success") return SemanticTheme.tone(root.t, "success", root.appStyle)
        if (tone === "warning") return SemanticTheme.tone(root.t, "warning", root.appStyle)
        if (tone === "info") return SemanticTheme.tone(root.t, "info", root.appStyle)
        if (tone === "error") return SemanticTheme.tone(root.t, "error", root.appStyle)
        return root.accentColor
    }

    function cardDisplay(card) {
        if (!card)
            return ""
        var display = String(card.displayValue || "")
        if (display.length > 0)
            return display
        return money(card.value)
    }

    function groupByLabel() {
        return root.groupByMode === "billingClient" ? "Billing Client" : "Client"
    }

    function resetTableState(tableId) {
        var id = String(tableId || "")
        if (id.length <= 0)
            return
        var states = root.tableStates || ({})
        if (states[id] !== undefined) {
            delete states[id]
            root.tableStates = states
            root._bumpTableStateRevision()
        }
    }

    function setGroupByMode(mode) {
        var next = String(mode || "") === "billingClient" ? "billingClient" : "client"
        if (next === root.groupByMode)
            return
        root.groupByMode = next
        root.resetTableState("summary")
        if (root.loadedOnce && !root.busy)
            root.refreshReport()
    }

    function openCardAction(card) {
        var tableId = String(card && card.actionTable ? card.actionTable : "")
        if (tableId.length > 0)
            root.expandTable(tableId)
    }

    function refreshReport() {
        if (root.busy)
            return
        root.busy = true
        root.hasError = false
        root.statusText = "Refreshing A/R aging..."
        try {
            if (!root.appRef || typeof root.appRef.getARAgingReport !== "function") {
                root.reportData = {
                    "ok": false,
                    "message": "A/R aging backend is unavailable."
                }
            } else {
                root.reportData = root.appRef.getARAgingReport({
                    "asOfDate": root.asOfDateText,
                    "query": root.queryText,
                    "groupBy": root.groupByMode,
                    "excludedInvoices": root.sanitizedExcludedInvoices(root.excludedInvoices)
                })
            }
            root.hasError = !(root.reportData && root.reportData.ok)
            root.statusText = root.hasError
                ? String(root.reportData && root.reportData.message ? root.reportData.message : "A/R aging refresh failed.")
                : ("Updated " + String(root.reportData.asOfDate || "") + " | " + String(root.summaryValue("invoiceCount")) + " open invoices")
            root.loadedOnce = true
        } catch (e) {
            root.hasError = true
            root.statusText = String(e)
            root.reportData = {
                "ok": false,
                "message": String(e)
            }
        }
        root.busy = false
    }

    function detailColumns() {
        return [
            { "key": "invoice", "label": "Invoice", "width": 82, "minWidth": 68 },
            { "key": "date", "label": "Date", "width": 110, "minWidth": 90 },
            { "key": "billingClient", "label": "Billing Client", "width": 170, "minWidth": 130 },
            { "key": "client", "label": "Client", "width": 170, "minWidth": 130 },
            { "key": "matter", "label": "Matter", "width": 140, "minWidth": 110 },
            { "key": "status", "label": "Status", "width": 120, "minWidth": 78 },
            { "key": "ageDays", "label": "Age", "width": 54, "minWidth": 48, "align": "right" },
            { "key": "bucketLabel", "label": "Bucket", "width": 74, "minWidth": 62 },
            { "key": "invoiceTotalDisplay", "label": "Invoice", "width": 95, "minWidth": 82, "align": "right", "sortKey": "invoiceTotal" },
            { "key": "paidDisplay", "label": "Paid", "width": 92, "minWidth": 78, "align": "right", "sortKey": "paid" },
            { "key": "balanceDisplay", "label": "Balance", "width": 98, "minWidth": 86, "align": "right", "sortKey": "balance" }
        ]
    }

    function closedVoidColumns() {
        return [
            { "key": "invoice", "label": "Invoice", "width": 86, "minWidth": 68 },
            { "key": "date", "label": "Date", "width": 108, "minWidth": 90 },
            { "key": "client", "label": "Client", "width": 240, "minWidth": 140 },
            { "key": "billingClient", "label": "Billing Client", "width": 220, "minWidth": 130 },
            { "key": "workClient", "label": "Work Client", "width": 220, "minWidth": 130 },
            { "key": "status", "label": "Status", "width": 88, "minWidth": 70 },
            { "key": "invoiceTotalDisplay", "label": "Invoice", "width": 104, "minWidth": 88, "align": "right", "sortKey": "invoiceTotal" },
            { "key": "paidDisplay", "label": "Paid/Credits", "width": 112, "minWidth": 94, "align": "right", "sortKey": "paid" },
            { "key": "balanceDisplay", "label": "Balance", "width": 108, "minWidth": 90, "align": "right", "sortKey": "balance" },
            { "key": "reason", "label": "Reason", "width": 360, "minWidth": 220 }
        ]
    }

    function summaryColumns() {
        var columns = [
            { "key": "client", "label": root.groupByLabel(), "width": 210, "minWidth": 150 },
            { "key": "invoiceCount", "label": "Inv", "width": 48, "minWidth": 42, "align": "right" },
            { "key": "oldestAgeDays", "label": "Oldest", "width": 64, "minWidth": 54, "align": "right" },
            { "key": "currentDisplay", "label": "0-30", "width": 86, "minWidth": 76, "align": "right", "sortKey": "current" },
            { "key": "days31To60Display", "label": "31-60", "width": 86, "minWidth": 76, "align": "right", "sortKey": "days31To60" },
            { "key": "days61To90Display", "label": "61-90", "width": 86, "minWidth": 76, "align": "right", "sortKey": "days61To90" },
            { "key": "days90PlusDisplay", "label": "90+", "width": 86, "minWidth": 76, "align": "right", "sortKey": "days90Plus" },
            { "key": "balanceDisplay", "label": "Balance", "width": 104, "minWidth": 88, "align": "right", "sortKey": "balance" }
        ]
        if (root.groupByMode === "billingClient")
            columns.splice(1, 0, { "key": "childClients", "label": "Clients", "width": 210, "minWidth": 150 })
        return columns
    }

    function bucketColumns() {
        return [
            { "key": "title", "label": "Bucket", "width": 190, "minWidth": 130 },
            { "key": "invoiceCount", "label": "Invoices", "width": 76, "minWidth": 64, "align": "right" },
            { "key": "amountDisplay", "label": "Amount", "width": 118, "minWidth": 92, "align": "right", "sortKey": "amount" }
        ]
    }

    function issueColumns() {
        return [
            { "key": "type", "label": "Issue", "width": 170, "minWidth": 150 },
            { "key": "reference", "label": "Ref", "width": 88, "minWidth": 74 },
            { "key": "client", "label": "Client", "width": 170, "minWidth": 130 },
            { "key": "status", "label": "Status", "width": 130, "minWidth": 78 },
            { "key": "amountDisplay", "label": "Amount", "width": 102, "minWidth": 86, "align": "right", "sortKey": "amount" },
            { "key": "note", "label": "Note", "width": 280, "minWidth": 190 }
        ]
    }

    function _aggregateRows() {
        return [
            { "metric": "Total A/R (Gross)", "value": money(root.summaryValue("totalAr")) },
            { "metric": "Total A/R (net of HST)", "value": money(root.summaryValue("totalArNet")) },
            { "metric": "Open invoices", "value": String(root.summaryValue("invoiceCount")) },
            { "metric": root.groupByMode === "billingClient" ? "Open billing clients" : "Open clients", "value": String(root.summaryValue("clientCount")) },
            { "metric": "Dashboard A/R authority", "value": money(root.summaryValue("ledgerAr")) },
            { "metric": "Open Receivables balance", "value": money(root.summaryValue("openReceivablesBalance")) },
            { "metric": "Dashboard delta", "value": money(root.summaryValue("ledgerDifference")) },
            { "metric": "Legacy ledger audit A/R", "value": money(root.summaryValue("legacyLedgerAr")) },
            { "metric": "Legacy ledger variance", "value": money(root.summaryValue("legacyLedgerDifference")) },
            { "metric": "Non-invoice legacy ledger A/R accounted", "value": money(root.summaryValue("nonInvoiceLedgerAr")) },
            { "metric": "Closed/void balances excluded", "value": money(root.summaryValue("staleClosedBalance")) }
        ]
    }

    function tableDefinition(tableId) {
        var id = String(tableId || "")
        if (id === "buckets") {
            return {
                "tableId": "buckets",
                "title": "Aging Buckets",
                "columns": root.bucketColumns(),
                "rows": root.safeList("bucketRows"),
                "visibleRows": 4,
                "emptyText": "No aging buckets returned.",
                "defaultSortKey": "",
                "defaultSortAscending": true
            }
        }
        if (id === "summary") {
            return {
                "tableId": "summary",
                "title": root.groupByMode === "billingClient" ? "Billing Client Summary" : "Client Summary",
                "columns": root.summaryColumns(),
                "rows": root.safeList("summaryRows"),
                "visibleRows": 7,
                "emptyText": root.groupByMode === "billingClient"
                    ? "No billing clients currently have open A/R."
                    : "No clients currently have open A/R.",
                "defaultSortKey": "balanceDisplay",
                "defaultSortAscending": false
            }
        }
        if (id === "issues") {
            return {
                "tableId": "issues",
                "title": "Reconciliation / Data Quality Issues",
                "columns": root.issueColumns(),
                "rows": root.safeList("issueRows"),
                "visibleRows": 6,
                "emptyText": "No reconciliation issues found.",
                "defaultSortKey": "type",
                "defaultSortAscending": true
            }
        }
        if (id === "closedVoid") {
            return {
                "tableId": "closedVoid",
                "title": "Excluded Closed/Void Detail",
                "columns": root.closedVoidColumns(),
                "rows": root.safeList("closedVoidRows"),
                "visibleRows": 10,
                "emptyText": "No closed, paid, or void balances are excluded.",
                "defaultSortKey": "balanceDisplay",
                "defaultSortAscending": false
            }
        }
        return {
            "tableId": "detail",
            "title": "Accounts Receivable",
            "columns": root.detailColumns(),
            "rows": root.safeList("rows"),
            "visibleRows": 10,
            "emptyText": "No open invoices found.",
            "defaultSortKey": "ageDays",
            "defaultSortAscending": false
        }
    }

    function tablePreferenceKey(tableId) {
        return root.tablePreferencesBaseId + "." + String(tableId || "table")
    }

    function _columnMinWidth(column) {
        var value = Number(column && column.minWidth !== undefined ? column.minWidth : 48)
        return isFinite(value) && value > 0 ? value : 48
    }

    function _columnWidth(column) {
        var value = Number(column && column.width !== undefined ? column.width : 100)
        if (!isFinite(value) || value <= 0) value = 100
        return Math.max(root._columnMinWidth(column), Math.round(value))
    }

    function _cloneColumnDefinition(column) {
        return {
            "key": String(column && column.key !== undefined ? column.key : ""),
            "label": String(column && column.label !== undefined ? column.label : ""),
            "width": root._columnWidth(column),
            "minWidth": root._columnMinWidth(column),
            "align": String(column && column.align !== undefined ? column.align : "left").toLowerCase() === "right" ? "right" : "left",
            "sortKey": String(column && column.sortKey !== undefined ? column.sortKey : (column && column.key !== undefined ? column.key : "")),
            "visible": !(column && column.visible === false),
            "resizable": !(column && column.resizable === false)
        }
    }

    function _firstVisibleColumnKey(columns) {
        for (var i = 0; i < columns.length; i++) {
            if (columns[i] && columns[i].visible !== false)
                return String(columns[i].key || "")
        }
        return columns.length > 0 ? String(columns[0].key || "") : ""
    }

    function _ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        var id = String(tableId || "table")
        var states = root.tableStates || ({})
        var existing = states[id]
        if (existing && existing.columns && existing.columns.length !== undefined)
            return existing

        var columns = []
        var defaults = defaultColumns && defaultColumns.length !== undefined ? defaultColumns : []
        for (var i = 0; i < defaults.length; i++) {
            var next = root._cloneColumnDefinition(defaults[i])
            if (next.key.length > 0)
                columns.push(next)
        }
        var sortKey = String(defaultSortKey || "")
        if (sortKey.length <= 0)
            sortKey = ""
        var state = {
            "columns": columns,
            "sortKey": sortKey,
            "sortAscending": defaultSortAscending !== false,
            "preferencesLoaded": false
        }

        if (root.appRef && typeof root.appRef.getTablePreferences === "function") {
            try {
                var preferences = root.appRef.getTablePreferences(root.tablePreferenceKey(id))
                root._applyTablePreferencesToState(state, preferences)
            } catch (e) {
            }
        }
        state.preferencesLoaded = true
        states[id] = state
        root.tableStates = states
        return state
    }

    function _applyTablePreferencesToState(state, preferences) {
        if (!state || !preferences || !preferences.columns || !state.columns)
            return
        var defaults = []
        var byKey = ({})
        for (var i = 0; i < state.columns.length; i++) {
            var cloned = root._cloneColumnDefinition(state.columns[i])
            defaults.push(cloned)
            byKey[cloned.key] = cloned
        }
        var nextColumns = []
        var used = ({})
        for (var p = 0; p < preferences.columns.length; p++) {
            var pref = preferences.columns[p]
            var key = String(pref && pref.key !== undefined ? pref.key : "")
            if (!key || used[key] || !byKey[key])
                continue
            var merged = root._cloneColumnDefinition(byKey[key])
            if (pref.width !== undefined) {
                var prefWidth = Math.round(Number(pref.width))
                if (isFinite(prefWidth) && prefWidth > 0)
                    merged.width = Math.max(merged.minWidth, prefWidth)
            }
            if (pref.visible !== undefined)
                merged.visible = !!pref.visible
            nextColumns.push(merged)
            used[key] = true
        }
        for (var d = 0; d < defaults.length; d++) {
            if (!used[defaults[d].key])
                nextColumns.push(defaults[d])
        }
        var visibleCount = 0
        for (var v = 0; v < nextColumns.length; v++) {
            if (nextColumns[v].visible !== false)
                visibleCount += 1
        }
        if (visibleCount <= 0 && nextColumns.length > 0)
            nextColumns[0].visible = true
        if (nextColumns.length > 0)
            state.columns = nextColumns

        var sortKey = String(preferences.sortKey || "")
        if (sortKey.length > 0 && root._tableColumnByKeyInState(state, sortKey))
            state.sortKey = sortKey
        if (preferences.sortAscending !== undefined)
            state.sortAscending = !!preferences.sortAscending
    }

    function _tableColumnByKeyInState(state, key) {
        if (!state || !state.columns)
            return null
        var wanted = String(key || "")
        for (var i = 0; i < state.columns.length; i++) {
            if (String(state.columns[i].key || "") === wanted)
                return state.columns[i]
        }
        return null
    }

    function _bumpTableStateRevision() {
        root.tableStateRevision += 1
    }

    function tableColumns(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        var revision = root.tableStateRevision
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var out = []
        for (var i = 0; i < state.columns.length; i++) {
            var col = state.columns[i]
            if (col && col.visible !== false) {
                var colCopy = {}
                for (var k in col) colCopy[k] = col[k]
                
                var defW = col.width
                for (var j = 0; j < defaultColumns.length; j++) {
                    if (defaultColumns[j].key === col.key) {
                        defW = defaultColumns[j].width
                        colCopy.label = defaultColumns[j].label
                        colCopy.sortKey = String(defaultColumns[j].sortKey !== undefined ? defaultColumns[j].sortKey : defaultColumns[j].key)
                        break
                    }
                }
                colCopy.width = defW
                out.push(colCopy)
            }
        }
        return out
    }

    function allTableColumns(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        var revision = root.tableStateRevision
        return root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending).columns
    }

    function tableColumnByKey(tableId, columnKey, defaultColumns, defaultSortKey, defaultSortAscending) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        return root._tableColumnByKeyInState(state, columnKey)
    }

    function tableColumnWidth(column) {
        var revision = root.tableStateRevision
        return root._columnWidth(column)
    }

    function tableColumnVisible(column) {
        var revision = root.tableStateRevision
        return !!(column && column.visible !== false)
    }

    function tableTotalColumnWidth(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        var cols = root.tableColumns(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var total = 0
        for (var i = 0; i < cols.length; i++)
            total += root.tableColumnWidth(cols[i])
        return total
    }

    function _tableColumnIndexByKey(state, key) {
        if (!state || !state.columns)
            return -1
        var wanted = String(key || "")
        for (var i = 0; i < state.columns.length; i++) {
            if (String(state.columns[i].key || "") === wanted)
                return i
        }
        return -1
    }

    function _nextVisibleColumnIndexInState(state, idx) {
        if (!state || !state.columns)
            return -1
        for (var i = idx + 1; i < state.columns.length; i++) {
            var column = state.columns[i]
            if (column && column.visible !== false)
                return i
        }
        return -1
    }

    function tableHeaderRightPadding(column) {
        return root.tableCellPadXPx + (column && column.resizable !== false ? root.tableResizeHandleWidthPx : 0)
    }

    function tableColumnKeyAtX(tableId, localX, defaultColumns, defaultSortKey, defaultSortAscending) {
        var cols = root.tableColumns(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var x = Math.max(0, Number(localX))
        var cursor = 0
        var lastKey = ""
        for (var i = 0; i < cols.length; i++) {
            var width = root.tableColumnWidth(cols[i])
            if (x <= cursor + width)
                return String(cols[i].key || "")
            lastKey = String(cols[i].key || "")
            cursor += width
        }
        return lastKey
    }

    function tableHeaderText(tableId, column, defaultColumns, defaultSortKey, defaultSortAscending) {
        var revision = root.tableStateRevision
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var key = String(column && column.key !== undefined ? column.key : "")
        var label = String(column && column.label !== undefined ? column.label : "")
        if (state.sortKey === key)
            return label + (state.sortAscending ? " ^" : " v")
        return label
    }

    function _sortValue(row, column) {
        if (!row || !column)
            return ""
        var key = String(column.sortKey || column.key || "")
        var value = row[key]
        if (value === undefined || value === null)
            value = row[String(column.key || "")]
        if (value === undefined || value === null)
            return ""
        if (typeof value === "number")
            return value
        var text = String(value)
        var numeric = Number(text.replace(/[$,%\s,]/g, ""))
        if (isFinite(numeric) && text.match(/[0-9]/))
            return numeric
        var time = Date.parse(text)
        if (isFinite(time) && text.match(/^\d{4}-\d{2}-\d{2}/))
            return time
        return text.toLowerCase()
    }

    function tableSortedRows(tableId, rows, defaultColumns, defaultSortKey, defaultSortAscending) {
        var revision = root.tableStateRevision
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var src = rows && rows.length !== undefined ? rows : []
        var out = []
        for (var i = 0; i < src.length; i++)
            out.push(src[i])
        if (!state.sortKey)
            return out
        var column = root._tableColumnByKeyInState(state, state.sortKey)
        if (!column)
            return out
        var asc = state.sortAscending !== false
        out.sort(function(a, b) {
            var av = root._sortValue(a, column)
            var bv = root._sortValue(b, column)
            if (typeof av === "number" && typeof bv === "number")
                return asc ? av - bv : bv - av
            var as = String(av)
            var bs = String(bv)
            if (as < bs)
                return asc ? -1 : 1
            if (as > bs)
                return asc ? 1 : -1
            return 0
        })
        return out
    }

    function tablePreferencesSnapshot(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var columns = []
        for (var i = 0; i < state.columns.length; i++) {
            var col = state.columns[i]
            columns.push({
                "key": String(col.key || ""),
                "width": root.tableColumnWidth(col),
                "visible": col.visible !== false
            })
        }
        return {
            "version": 1,
            "columns": columns,
            "sortKey": String(state.sortKey || ""),
            "sortAscending": state.sortAscending !== false
        }
    }

    function saveTablePreferencesNow(tableId, defaultColumns, defaultSortKey, defaultSortAscending) {
        if (!root.appRef || typeof root.appRef.saveTablePreferences !== "function")
            return false
        var id = String(tableId || "")
        if (!id)
            return false
        return root.appRef.saveTablePreferences(
            root.tablePreferenceKey(id),
            root.tablePreferencesSnapshot(id, defaultColumns, defaultSortKey, defaultSortAscending)
        )
    }

    function setTableSort(tableId, columnKey, defaultColumns, defaultSortKey, defaultSortAscending) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var key = String(columnKey || "")
        if (!root._tableColumnByKeyInState(state, key))
            return
        if (state.sortKey === key) {
            state.sortAscending = !state.sortAscending
        } else {
            state.sortKey = key
            state.sortAscending = true
        }
        root._bumpTableStateRevision()
        root.saveTablePreferencesNow(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
    }

    function moveTableColumnByKey(tableId, fromKey, toKey, defaultColumns, defaultSortKey, defaultSortAscending) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var fromIdx = root._tableColumnIndexByKey(state, fromKey)
        var toIdx = root._tableColumnIndexByKey(state, toKey)
        if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx)
            return
        var moved = state.columns.splice(fromIdx, 1)[0]
        state.columns.splice(toIdx, 0, moved)
        root._bumpTableStateRevision()
        root.saveTablePreferencesNow(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
    }

    function setTableColumnWidth(tableId, columnKey, width, defaultColumns, defaultSortKey, defaultSortAscending, persist) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var columnIdx = root._tableColumnIndexByKey(state, columnKey)
        var column = columnIdx >= 0 ? state.columns[columnIdx] : null
        if (!column || column.resizable === false)
            return
        var requested = Math.round(Number(width))
        if (!isFinite(requested) || requested <= 0)
            return
        var currentWidth = root._columnWidth(column)
        var minWidth = root._columnMinWidth(column)
        var nextWidth = Math.max(minWidth, requested)
        var delta = nextWidth - currentWidth
        var nextIdx = root._nextVisibleColumnIndexInState(state, columnIdx)
        var nextColumn = nextIdx >= 0 ? state.columns[nextIdx] : null
        if (nextColumn) {
            var neighborWidth = root._columnWidth(nextColumn)
            var neighborMin = root._columnMinWidth(nextColumn)
            var maxGrow = Math.max(0, neighborWidth - neighborMin)
            var maxShrink = Math.max(0, currentWidth - minWidth)
            delta = Math.max(-maxShrink, Math.min(delta, maxGrow))
            if (delta === 0)
                return
            column.width = currentWidth + delta
            nextColumn.width = neighborWidth - delta
        } else {
            column.width = nextWidth
        }
        root._bumpTableStateRevision()
        if (persist !== false)
            root.saveTablePreferencesNow(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
    }

    function setTableColumnVisible(tableId, columnKey, visible, defaultColumns, defaultSortKey, defaultSortAscending) {
        var state = root._ensureTableState(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
        var column = root._tableColumnByKeyInState(state, columnKey)
        if (!column)
            return
        var visibleCount = 0
        for (var i = 0; i < state.columns.length; i++) {
            if (state.columns[i].visible !== false)
                visibleCount += 1
        }
        if (visible === false && visibleCount <= 1)
            return
        column.visible = visible !== false
        if (column.visible === false && state.sortKey === String(column.key || ""))
            state.sortKey = root._firstVisibleColumnKey(state.columns)
        root._bumpTableStateRevision()
        root.saveTablePreferencesNow(tableId, defaultColumns, defaultSortKey, defaultSortAscending)
    }

    function expandTable(tableId) {
        root.expandedTableId = String(tableId || "")
    }

    function restoreExpandedTable() {
        root.expandedTableId = ""
    }

    function resetHeaderDrag() {
        root.activeHeaderDragTableId = ""
        root.activeHeaderDragColumnKey = ""
        root.activeHeaderDropColumnKey = ""
    }

    function resetResizeState() {
        root.tableResizeActive = false
    }

    function expandedDefinition() {
        return root.tableDefinition(root.expandedTableId)
    }

    function _buildReportDocument() {
        var detailDef = root.tableDefinition("detail")
        var summaryDef = root.tableDefinition("summary")
        var bucketDef = root.tableDefinition("buckets")
        var issueDef = root.tableDefinition("issues")
        var closedVoidDef = root.tableDefinition("closedVoid")
        var aggregateRows = root._aggregateRows()
        var detailRows = root.tableSortedRows("detail", detailDef.rows, detailDef.columns, detailDef.defaultSortKey, detailDef.defaultSortAscending)
        var summaryRows = root.tableSortedRows("summary", summaryDef.rows, summaryDef.columns, summaryDef.defaultSortKey, summaryDef.defaultSortAscending)
        var bucketRows = root.tableSortedRows("buckets", bucketDef.rows, bucketDef.columns, bucketDef.defaultSortKey, bucketDef.defaultSortAscending)
        var issueRows = root.tableSortedRows("issues", issueDef.rows, issueDef.columns, issueDef.defaultSortKey, issueDef.defaultSortAscending)
        var closedVoidRows = root.tableSortedRows("closedVoid", closedVoidDef.rows, closedVoidDef.columns, closedVoidDef.defaultSortKey, closedVoidDef.defaultSortAscending)
        return {
            "reportId": "ar_aging",
            "title": "A/R Aging & Detail",
            "filterSummary": "As of: " + String(root.reportData.asOfDate || root.asOfDateText)
                + " | Search: " + (root.queryText.length > 0 ? root.queryText : "All open invoices")
                + " | Group: " + root.groupByLabel()
                + " | Source: tblReceivables"
                ,
            "exportPayload": {
                "reportId": "ar_aging",
                "filters": { "asOfDate": root.asOfDateText, "query": root.queryText, "groupBy": root.groupByMode },
                "summary": root.reportData.summary || ({}),
                "rows": detailRows,
                "summaryRows": summaryRows,
                "bucketRows": bucketRows,
                "issueRows": issueRows,
                "closedVoidRows": closedVoidRows
            },
            "sections": [
                {
                    "sectionId": "detail",
                    "title": "A/R Invoice Detail",
                    "columns": root.tableColumns("detail", detailDef.columns, detailDef.defaultSortKey, detailDef.defaultSortAscending),
                    "rows": detailRows
                },
                {
                    "sectionId": "summary",
                    "title": "Client Summary",
                    "columns": root.tableColumns("summary", summaryDef.columns, summaryDef.defaultSortKey, summaryDef.defaultSortAscending),
                    "rows": summaryRows
                },
                {
                    "sectionId": "aggregate",
                    "title": "Aging Buckets",
                    "columns": root.tableColumns("buckets", bucketDef.columns, bucketDef.defaultSortKey, bucketDef.defaultSortAscending),
                    "rows": bucketRows
                },
                {
                    "sectionId": "issues",
                    "title": "Reconciliation / Data Quality Issues",
                    "columns": root.tableColumns("issues", issueDef.columns, issueDef.defaultSortKey, issueDef.defaultSortAscending),
                    "rows": issueRows
                },
                {
                    "sectionId": "closedVoid",
                    "title": "Excluded Closed/Void Detail",
                    "columns": root.tableColumns("closedVoid", closedVoidDef.columns, closedVoidDef.defaultSortKey, closedVoidDef.defaultSortAscending),
                    "rows": closedVoidRows
                },
                {
                    "sectionId": "totals",
                    "title": "A/R Totals",
                    "columns": [
                        { "key": "metric", "label": "Metric", "width": 240 },
                        { "key": "value", "label": "Value", "width": 160, "align": "right" }
                    ],
                    "rows": aggregateRows
                }
            ]
        }
    }

    function openReportWindow() {
        if (!root.loadedOnce)
            root.refreshReport()
        root.reportWindowRequested(root._buildReportDocument())
    }

    function printExpandedTable(tableId) {
        if (!root.loadedOnce)
            root.refreshReport()
        var def = root.tableDefinition(tableId)
        var sortedRows = root.tableSortedRows(tableId, def.rows, def.columns, def.defaultSortKey, def.defaultSortAscending)
        var sectionId = "detail"
        if (tableId === "summary")
            sectionId = "summary"
        else if (tableId === "buckets")
            sectionId = "aggregate"
        else if (tableId === "closedVoid")
            sectionId = "closedVoid"
        
        var headerColumns = []
        var headerRow = {}
        var cards = root.safeList("cards")
        for (var i = 0; i < cards.length; i++) {
            var cKey = "c" + i
            headerColumns.push({ "key": cKey, "label": String(cards[i].label) })
            headerRow[cKey] = root.cardDisplay(cards[i])
        }

        var doc = {
            "reportId": "ar_aging_" + tableId,
            "title": def.title,
            "filterSummary": "As of: " + String(root.reportData.asOfDate || root.asOfDateText)
                + " | Search: " + (root.queryText.length > 0 ? root.queryText : "All open invoices")
                + " | Group: " + root.groupByLabel()
                + " | Source: tblReceivables"
                ,
            "exportPayload": {
                "reportId": "ar_aging_" + tableId,
                "filters": { "asOfDate": root.asOfDateText, "query": root.queryText, "groupBy": root.groupByMode },
                "summary": root.reportData.summary || ({}),
                "rows": sortedRows
            },
            "sections": [
                {
                    "sectionId": "header",
                    "title": "",
                    "columns": headerColumns,
                    "rows": [ headerRow ]
                },
                {
                    "sectionId": sectionId,
                    "title": def.title,
                    "columns": root.tableColumns(tableId, def.columns, def.defaultSortKey, def.defaultSortAscending),
                    "rows": sortedRows
                }
            ]
        }
        root.reportWindowRequested(doc)
    }


    Component.onCompleted: {
        root.fetchExcludedInvoices()
        if (root.autoLoadOnVisible && root.visible)
            root.refreshReport()
    }

    onVisibleChanged: {
        if (visible && root.autoLoadOnVisible && !root.loadedOnce)
            root.refreshReport()
    }

    Connections {
        target: root.appRef ? root.appRef : null
        ignoreUnknownSignals: true
        function onTransactionDataChanged() {
            if (root.visible)
                root.refreshReport()
        }
        function onClientDataChanged() {
            if (root.visible)
                root.refreshReport()
        }
    }

    component MetricCard: Rectangle {
        id: metricCard
        required property var card
        property color cardAccent: root.toneColor(metricCard.card ? metricCard.card.tone : "primary")
        property string actionTable: String(metricCard.card && metricCard.card.actionTable ? metricCard.card.actionTable : "")
        radius: root.isProMode ? 5 : root.sectionRadiusPx
        color: root.panelColor
        border.width: 1
        border.color: Qt.rgba(cardAccent.r, cardAccent.g, cardAccent.b, 0.32)

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 3
            radius: 2
            color: parent.cardAccent
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 3

            Text {
                text: String(metricCard.card ? metricCard.card.label : "")
                color: root.mutedInkColor
                font.family: visualRules.textFontFamily
                font.pixelSize: 11
                fontSizeMode: Text.Fit
                minimumPixelSize: 9
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Text {
                text: root.cardDisplay(metricCard.card)
                color: root.inkColor
                font.family: visualRules.textFontFamily
                font.pixelSize: 22
                font.bold: true
                fontSizeMode: Text.Fit
                minimumPixelSize: 14
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        MouseArea {
            id: metricCardMouse
            anchors.fill: parent
            enabled: metricCard.actionTable.length > 0
            hoverEnabled: enabled
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.openCardAction(metricCard.card)
        }

        ToolTip.visible: metricCardMouse.enabled && metricCardMouse.containsMouse
        ToolTip.text: metricCard.actionTable.length > 0 ? "Open detail" : ""
    }

    component DataTable: Rectangle {
        id: table
        property string tableId: ""
        property string title: ""
        property var defaultColumns: []
        property var rows: []
        property int visibleRows: 6
        property string emptyText: "No rows returned."
        property string defaultSortKey: ""
        property bool defaultSortAscending: true
        property bool expandedMode: false
        property bool fillAvailableHeight: false
        property int fillColIdx: -1

        readonly property var effectiveColumns: root.tableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
        readonly property var allColumns: root.allTableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
        readonly property var effectiveRows: root.tableSortedRows(table.tableId, table.rows, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)

        implicitHeight: table.fillAvailableHeight
            ? 420
            : (titleRow.implicitHeight + 38 + Math.max(38, Math.min(Math.max(1, table.effectiveRows.length), table.visibleRows) * 38) + 18)
        radius: root.isProMode ? 5 : root.sectionRadiusPx
        color: root.panelColor
        border.width: 1
        border.color: root.borderColor
        clip: true

        Shortcut {
            sequence: "Esc"
            enabled: table.expandedMode
            onActivated: root.restoreExpandedTable()
        }

        property var columns: root.tableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)

        Popup {
            id: columnPopup
            x: Math.max(0, table.width - width - 10)
            y: Math.max(34, titleRow.height + 4)
            width: 250
            modal: false
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: root.surfaceColor
                radius: root.isProMode ? 5 : root.sectionRadiusPx
                border.width: 1
                border.color: root.borderColor
            }

            contentItem: ColumnLayout {
                spacing: 4
                Repeater {
                    model: root.allTableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                    delegate: CheckBox {
                        id: columnCheck
                        required property var modelData
                        text: String(modelData.label || modelData.key || "")
                        checked: modelData.visible !== false
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        indicator: Rectangle {
                            implicitWidth: 15
                            implicitHeight: 15
                            x: 8
                            y: (columnCheck.height - height) / 2
                            radius: 2
                            color: columnCheck.checked ? root.accentColor : root.inputColor
                            border.width: 1
                            border.color: columnCheck.checked ? root.accentColor : root.borderColor

                            Text {
                                anchors.centerIn: parent
                                text: columnCheck.checked ? "X" : ""
                                color: "#ffffff"
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                        contentItem: Text {
                            text: columnCheck.text
                            color: root.inkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 12
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            leftPadding: 30
                            rightPadding: 8
                        }
                        onToggled: {
                            root.setTableColumnVisible(
                                table.tableId,
                                String(modelData.key || ""),
                                checked,
                                table.defaultColumns,
                                table.defaultSortKey,
                                table.defaultSortAscending
                            )
                        }
                    }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            RowLayout {
                id: titleRow
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                spacing: 6

                Text {
                    text: table.title
                    color: root.inkColor
                    font.family: visualRules.textFontFamily
                    font.pixelSize: table.expandedMode ? 15 : 13
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                }

                Text {
                    text: String(table.effectiveRows.length) + " rows"
                    color: root.subtleInkColor
                    font.family: visualRules.textFontFamily
                    font.pixelSize: 11
                    Layout.preferredWidth: 72
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }


                Button {
                    id: settingsButton
                    text: "⚙" // Gear icon
                    visible: table.tableId === "detail"
                    Layout.preferredWidth: 40
                    font.pixelSize: 16
                    onClicked: excludedInvoicesPopup.open()
                }

                Button {
                    id: columnButton

                    text: "Columns"
                    Layout.preferredWidth: 86
                    Layout.preferredHeight: 28
                    onClicked: columnPopup.open()
                }

                Button {
                    text: "Print"
                    Layout.preferredWidth: 82
                    Layout.preferredHeight: 28
                    visible: table.expandedMode
                    onClicked: root.printExpandedTable(table.tableId)
                }

                Button {
                    text: table.expandedMode ? "Restore" : "Expand"
                    Layout.preferredWidth: 82
                    Layout.preferredHeight: 28
                    onClicked: table.expandedMode ? root.restoreExpandedTable() : root.expandTable(table.tableId)
                }
            }

            Flickable {
                id: tableBody
                pressDelay: 0
                Layout.fillWidth: true
                Layout.fillHeight: table.fillAvailableHeight
                Layout.preferredHeight: table.fillAvailableHeight
                    ? 320
                    : (30 + Math.max(38, Math.min(Math.max(1, table.effectiveRows.length), table.visibleRows) * 38))
                clip: true
                contentWidth: Math.max(width, tableHeader.totalColumnWidth)
                contentHeight: height
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                interactive: !root.tableResizeActive

                Column {
                    id: tableContent
                    width: tableBody.contentWidth
                    height: tableBody.height

                    StandardTableHeader {
                        id: tableHeader
                        width: parent.width
                        columns: table.columns
                        sortColumn: root.tableStates[table.tableId] ? root.tableStates[table.tableId].sortKey : ""
                        sortAscending: root.tableStates[table.tableId] ? root.tableStates[table.tableId].sortAscending : true

                        onSortRequested: function(key) {
                            root.setTableSort(table.tableId, key, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                        }

                        onConfigChanged: function(newCols) {
                            if (!newCols) return
                            for (var i = 0; i < newCols.length; i++) {
                                root.setTableColumnWidth(table.tableId, newCols[i].key, newCols[i].width, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending, false)
                            }
                            var state = root._ensureTableState(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                            var newColumns = []
                            for (var i = 0; i < newCols.length; i++) {
                                var idx = root._tableColumnIndexByKey(state, newCols[i].key)
                                if (idx >= 0) newColumns.push(state.columns[idx])
                            }
                            for (var i = 0; i < state.columns.length; i++) {
                                var found = false
                                for (var j = 0; j < newCols.length; j++) {
                                    if (newCols[j].key === state.columns[i].key) { found = true; break; }
                                }
                                if (!found) newColumns.push(state.columns[i])
                            }
                            state.columns = newColumns
                            root._bumpTableStateRevision()
                            root.saveTablePreferencesNow(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                        }
                    }

                    ListView {
                        id: rowList
                        width: parent.width
                        height: Math.max(38, parent.height - tableHeader.height)
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: table.effectiveRows
                        delegate: Rectangle {
                            id: rowDelegate
                            required property int index
                            required property var modelData
                            property var rowData: modelData
                            width: rowList.width
                            height: 38
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(root.inkColor.r, root.inkColor.g, root.inkColor.b, 0.035)

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: root.borderColor
                            }

                            MouseArea {
                                anchors.fill: parent
                                z: 10
                                acceptedButtons: Qt.RightButton
                                onClicked: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        var inv = rowDelegate.rowData ? rowDelegate.rowData.invoice : ""
                                        if (inv) {
                                            rowContextPopup.openForRow(rowDelegate.rowData, mouse.x, mouse.y, rowDelegate)
                                        }
                                    }
                                }
                            }

                            Row {

                                id: cellRow
                                height: parent.height

                                Repeater {
                                    model: table.columns
                                    delegate: Rectangle {
                                        id: bodyCell
                                        required property int index
                                        required property var modelData
                                        property string colKey: modelData.key || ""
                                        property string colAlign: modelData.align || "left"

                                        visible: modelData.visible !== false
                                        width: visible ? tableHeader.columnWidthFor(colKey) : 0
                                        height: cellRow.height
                                        color: "transparent"

                                        Text {
                                            id: cellTextObj
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            color: root.inkColor
                                            opacity: 0.92
                                            font.family: visualRules.textFontFamily
                                            font.pixelSize: Math.max(9, Math.round(12 * tableHeader.tableScale))
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight

                                            Component.onCompleted: updateContent()

                                            Connections {
                                                target: rowDelegate
                                                function onRowDataChanged() { cellTextObj.updateContent() }
                                            }

                                            Connections {
                                                target: bodyCell
                                                function onColKeyChanged() { cellTextObj.updateContent() }
                                                function onColAlignChanged() { cellTextObj.updateContent() }
                                            }

                                            function updateContent() {
                                                var val = rowDelegate.rowData ? rowDelegate.rowData[bodyCell.colKey] : undefined
                                                cellTextObj.text = (val !== undefined && val !== null) ? String(val) : ""
                                                cellTextObj.horizontalAlignment = bodyCell.colAlign === "right" ? Text.AlignRight : Text.AlignLeft
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: table.effectiveRows.length <= 0
                            text: table.emptyText
                            color: root.subtleInkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        ScrollView {
            id: reportScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: reportScroll.availableWidth
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    spacing: 8

                    Text {
                        text: "A/R Aging & Detail"
                        color: root.inkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: root.isProMode ? 18 : root.ratioPx(0.019, 15)
                        font.bold: true
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    TextField {
                        id: asOfField
                        text: root.asOfDateText
                        placeholderText: "yyyy-mm-dd"
                        enabled: !root.busy
                        selectByMouse: true
                        Layout.preferredWidth: 128
                        Layout.preferredHeight: 34
                        color: root.inkColor
                        placeholderTextColor: root.subtleInkColor
                        font.pixelSize: 12
                        onTextChanged: root.asOfDateText = text
                        background: Rectangle {
                            color: root.inputColor
                            radius: root.isProMode ? 4 : root.sectionRadiusPx
                            border.width: asOfField.activeFocus ? 2 : 1
                            border.color: asOfField.activeFocus ? root.accentColor : root.borderColor
                        }
                    }

                    TextField {
                        id: searchField
                        text: root.queryText
                        placeholderText: "Search invoice, client..."
                        enabled: !root.busy
                        selectByMouse: true
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 34
                        color: root.inkColor
                        placeholderTextColor: root.subtleInkColor
                        font.pixelSize: 12
                        onTextChanged: root.queryText = text
                        onAccepted: root.refreshReport()
                        background: Rectangle {
                            color: root.inputColor
                            radius: root.isProMode ? 4 : root.sectionRadiusPx
                            border.width: searchField.activeFocus ? 2 : 1
                            border.color: searchField.activeFocus ? root.accentColor : root.borderColor
                        }
                    }

                    RowLayout {
                        Layout.preferredWidth: 260
                        Layout.preferredHeight: 34
                        spacing: 6

                        Text {
                            text: "Group"
                            color: root.mutedInkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 11
                            Layout.preferredWidth: 42
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            id: groupSegment
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            radius: root.isProMode ? 4 : root.sectionRadiusPx
                            color: root.inputColor
                            border.width: 1
                            border.color: root.borderColor
                            clip: true

                            Row {
                                anchors.fill: parent
                                anchors.margins: 2

                                Repeater {
                                    model: [
                                        { "mode": "client", "label": "Client" },
                                        { "mode": "billingClient", "label": "Billing Client" }
                                    ]

                                    delegate: Rectangle {
                                        id: groupSegmentOption
                                        required property var modelData
                                        property bool selected: root.groupByMode === String(groupSegmentOption.modelData.mode || "")

                                        width: Math.max(0, (groupSegment.width - 4) / 2)
                                        height: parent.height
                                        radius: root.isProMode ? 3 : root.sectionRadiusPx
                                        color: selected
                                            ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.isProMode ? 0.18 : 0.30)
                                            : "transparent"
                                        border.width: selected ? 1 : 0
                                        border.color: selected ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.55) : "transparent"

                                        Text {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            text: String(groupSegmentOption.modelData.label || "")
                                            color: parent.selected ? root.inkColor : root.mutedInkColor
                                            font.family: visualRules.textFontFamily
                                            font.pixelSize: 11
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: !root.busy
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.setGroupByMode(String(groupSegmentOption.modelData.mode || "client"))
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Button {
                        text: root.busy ? "Refreshing..." : "Refresh"
                        enabled: !root.busy
                        Layout.preferredWidth: 96
                        Layout.preferredHeight: 34
                        onClicked: root.refreshReport()
                    }

                    Button {
                        text: "Open Report"
                        enabled: !root.busy && root.loadedOnce
                        Layout.preferredWidth: 112
                        Layout.preferredHeight: 34
                        onClicked: root.openReportWindow()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: root.isProMode ? 4 : root.sectionRadiusPx
                    color: root.hasError
                        ? Qt.rgba(root.toneColor("error").r, root.toneColor("error").g, root.toneColor("error").b, 0.12)
                        : Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.08)
                    border.width: 1
                    border.color: root.hasError ? root.toneColor("error") : root.borderColor

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.statusText
                        color: root.hasError ? root.toneColor("error") : root.mutedInkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: root.safeList("cards")
                        delegate: MetricCard {
                            required property var modelData
                            card: modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 112
                            Layout.preferredHeight: 76
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: reportScroll.availableWidth > 1180 ? 2 : 1
                    columnSpacing: 12
                    rowSpacing: 12

                    DataTable {
                        tableId: "buckets"
                        title: root.tableDefinition("buckets").title
                        defaultColumns: root.bucketColumns()
                        rows: root.safeList("bucketRows")
                        visibleRows: 4
                        emptyText: root.tableDefinition("buckets").emptyText
                        defaultSortKey: ""
                        defaultSortAscending: true
                        Layout.fillWidth: true
                    }

                    DataTable {
                        tableId: "summary"
                        title: root.tableDefinition("summary").title
                        defaultColumns: root.summaryColumns()
                        rows: root.safeList("summaryRows")
                        visibleRows: 7
                        emptyText: root.tableDefinition("summary").emptyText
                        defaultSortKey: "balanceDisplay"
                        defaultSortAscending: false
                        Layout.fillWidth: true
                    }
                }

                DataTable {
                    tableId: "detail"
                    title: root.tableDefinition("detail").title
                    defaultColumns: root.detailColumns()
                    rows: root.safeList("rows")
                    visibleRows: 10
                    emptyText: root.tableDefinition("detail").emptyText
                    defaultSortKey: "ageDays"
                    defaultSortAscending: false
                    Layout.fillWidth: true
                }

                DataTable {
                    tableId: "issues"
                    title: root.tableDefinition("issues").title
                    defaultColumns: root.issueColumns()
                    rows: root.safeList("issueRows")
                    visibleRows: 6
                    emptyText: root.tableDefinition("issues").emptyText
                    defaultSortKey: "type"
                    defaultSortAscending: true
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(42, notesColumn.implicitHeight + 20)
                    radius: root.isProMode ? 5 : root.sectionRadiusPx
                    color: root.panelColor
                    border.width: 1
                    border.color: root.borderColor

                    ColumnLayout {
                        id: notesColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 10
                        spacing: 3

                        Repeater {
                            model: root.safeList("notes")
                            delegate: Text {
                                required property string modelData
                                text: modelData
                                color: root.subtleInkColor
                                font.family: visualRules.textFontFamily
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: expandedOverlay
        anchors.fill: parent
        z: 1000
        visible: root.expandedTableId.length > 0
        color: Qt.rgba(15 / 255, 23 / 255, 42 / 255, root.isProMode ? 0.18 : 0.42)

        MouseArea {
            anchors.fill: parent
            onClicked: {
            }
        }

    Popup {
        id: rowContextPopup
        property string targetInvoice: ""
        property string targetClient: ""
        property string targetWorkClient: ""
        property string targetBillingClient: ""
        property var actionItems: []
        readonly property int rowHeight: 34

        function clean(value) {
            if (value === undefined || value === null)
                return ""
            return String(value).trim()
        }

        function sameName(left, right) {
            var a = rowContextPopup.clean(left).toLowerCase()
            var b = rowContextPopup.clean(right).toLowerCase()
            return a.length > 0 && b.length > 0 && a === b
        }

        function addStatementAction(actions, label, client, clientLevel) {
            var target = rowContextPopup.clean(client)
            if (target.length <= 0)
                return
            for (var i = 0; i < actions.length; i++) {
                var existing = actions[i]
                if (existing
                        && existing.kind === "statement"
                        && rowContextPopup.sameName(existing.client, target)
                        && String(existing.clientLevel || "") === String(clientLevel || "")) {
                    return
                }
            }
            actions.push({
                "kind": "statement",
                "label": label,
                "client": target,
                "clientLevel": clientLevel
            })
        }

        function rebuildActions(row) {
            var displayClient = rowContextPopup.clean(row && row.client)
            var legacyParentClient = (
                rowContextPopup.clean(row && row.billingParentName)
                || rowContextPopup.clean(row && row.billingParentId)
            )
            var billingClient = (
                legacyParentClient
                || rowContextPopup.clean(row && row.billingClient)
                || displayClient
            )
            var workClient = rowContextPopup.clean(row && row.workClient) || displayClient || billingClient

            rowContextPopup.targetInvoice = rowContextPopup.clean(row && row.invoice)
            rowContextPopup.targetClient = displayClient || billingClient
            rowContextPopup.targetWorkClient = workClient
            rowContextPopup.targetBillingClient = billingClient

            var actions = [{
                "kind": "exclude",
                "label": "Exclude Invoice from Reports"
            }]

            var primaryClient = workClient || displayClient || billingClient
            rowContextPopup.addStatementAction(
                actions,
                "Statement of Account (" + primaryClient + ")",
                primaryClient,
                "work"
            )

            if (billingClient.length > 0 && !rowContextPopup.sameName(billingClient, primaryClient)) {
                rowContextPopup.addStatementAction(
                    actions,
                    "Statement of Account (Billing: " + billingClient + ")",
                    billingClient,
                    "billing"
                )
            }

            rowContextPopup.actionItems = actions
        }

        function longestLabelLength() {
            var longest = 0
            for (var i = 0; i < rowContextPopup.actionItems.length; i++) {
                var text = rowContextPopup.clean(rowContextPopup.actionItems[i] && rowContextPopup.actionItems[i].label)
                longest = Math.max(longest, text.length)
            }
            return longest
        }

        function preferredMenuWidth() {
            var byText = Math.round(rowContextPopup.longestLabelLength() * 7.6) + 44
            return Math.min(Math.max(360, byText), Math.max(360, root.width - 24))
        }

        function preferredMenuHeight() {
            return Math.max(rowContextPopup.rowHeight, rowContextPopup.actionItems.length * rowContextPopup.rowHeight)
        }

        function openForRow(row, localX, localY, sourceItem) {
            rowContextPopup.rebuildActions(row || ({}))
            rowContextPopup.width = rowContextPopup.preferredMenuWidth()
            rowContextPopup.height = rowContextPopup.preferredMenuHeight()

            var point = sourceItem ? sourceItem.mapToItem(root, localX, localY) : Qt.point(8, 8)
            rowContextPopup.x = Math.max(8, Math.min(root.width - rowContextPopup.width - 8, Math.round(point.x)))
            rowContextPopup.y = Math.max(8, Math.min(root.height - rowContextPopup.height - 8, Math.round(point.y)))
            rowContextPopup.open()
        }

        function activateAction(action) {
            if (!action)
                return
            rowContextPopup.close()
            if (action.kind === "exclude") {
                if (rowContextPopup.targetInvoice) {
                    root.hideInvoice(rowContextPopup.targetInvoice, rowContextPopup.targetClient)
                }
                return
            }

            if (action.kind === "statement") {
                if (!root.appRef || typeof root.appRef.getStatementOfAccount !== "function") {
                    root.statusText = "Failed to generate statement: reporting backend is unavailable."
                    return
                }
                var payload = {
                    "client": action.client,
                    "client_level": action.clientLevel || "work"
                }
                var result = root.appRef.getStatementOfAccount(payload)
                if (result && result.ok) {
                    root.reportWindowRequested(result)
                } else {
                    root.statusText = "Failed to generate statement: " + (result ? result.message : "Unknown error")
                }
            }
        }

        padding: 0
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: root.panelColor
            radius: root.isProMode ? visualRules.radiusPopup : root.sectionRadiusPx
            border.width: 1
            border.color: root.borderColor
        }

        contentItem: Column {
            id: rowContextColumn
            spacing: 0

            Repeater {
                model: rowContextPopup.actionItems
                delegate: Rectangle {
                    id: rowContextAction
                    required property int index
                    required property var modelData

                    width: rowContextPopup.width
                    height: rowContextPopup.rowHeight
                    color: rowContextMouse.containsMouse
                        ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.isProMode ? 0.10 : 0.22)
                        : "transparent"

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 1
                        visible: rowContextAction.index === 1
                        color: root.borderColor
                    }

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        anchors.topMargin: rowContextAction.index === 1 ? 1 : 0
                        text: rowContextPopup.clean(rowContextAction.modelData && rowContextAction.modelData.label)
                        color: root.inkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    MouseArea {
                        id: rowContextMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton
                        onClicked: rowContextPopup.activateAction(rowContextAction.modelData)
                    }
                }
            }
        }
    }

    Popup {
        id: excludedInvoicesPopup
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: Math.min(Math.max(760, root.width * 0.58), Math.max(360, root.width - 48))
        height: Math.min(420, Math.max(260, root.height - 96))
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        
        background: Rectangle {
            color: root.panelColor
            radius: root.sectionRadiusPx
            border.width: 1
            border.color: root.borderColor
        }
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            
            Text {
                text: "Manually Excluded Invoices"
                color: root.inkColor
                font.bold: true
                font.pixelSize: 16
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            
            ListView {
                id: manualExcludedList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.sanitizedExcludedInvoices(root.excludedInvoices)
                delegate: RowLayout {
                    id: manualExcludedRow
                    required property var modelData
                    width: ListView.view.width
                    height: 32
                    
                    Text {
                        text: (manualExcludedRow.modelData.invoice || manualExcludedRow.modelData)
                            + (manualExcludedRow.modelData.client ? " (" + manualExcludedRow.modelData.client + ")" : "")
                        color: root.inkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        wrapMode: Text.NoWrap
                        Layout.fillWidth: true
                    }
                    
                    Button {
                        text: "Unhide"
                        onClicked: root.unhideInvoice(manualExcludedRow.modelData.invoice || manualExcludedRow.modelData)
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: manualExcludedList.count <= 0
                    text: "No manually excluded invoices."
                    color: root.subtleInkColor
                    font.family: visualRules.textFontFamily
                    font.pixelSize: 12
                }
            }
            
            Button {
                text: "Close"
                Layout.alignment: Qt.AlignRight
                onClicked: excludedInvoicesPopup.close()
            }
        }
    }

        Rectangle {
            anchors.fill: parent
            anchors.margins: root.isProMode ? 12 : 8
            radius: root.isProMode ? 6 : root.sectionRadiusPx
            color: root.surfaceColor
            border.width: 1
            border.color: root.borderColor

            DataTable {
                id: expandedTable
                anchors.fill: parent
                anchors.margins: 10
                tableId: root.expandedTableId
                title: root.expandedDefinition().title
                defaultColumns: root.expandedDefinition().columns
                rows: root.expandedDefinition().rows
                visibleRows: 999
                emptyText: root.expandedDefinition().emptyText
                defaultSortKey: root.expandedDefinition().defaultSortKey
                defaultSortAscending: root.expandedDefinition().defaultSortAscending
                expandedMode: true
                fillAvailableHeight: true
            }
        }
    }
}
