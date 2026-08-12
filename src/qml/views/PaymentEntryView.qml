import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property var metrics
    property var appRef
    property var sfxBus
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : "Professional"
    property bool isProMode: root.appStyle === "Professional"
    property bool dirty: false
    property bool saveInProgress: false
    property bool lastSaveOk: true
    property string saveMessage: ""
    property string lastSavedPaymentId: ""
    property string editingPaymentId: ""
    property real editingOriginalPaymentAmount: 0
    property real editingOriginalAdjustmentAmount: 0
    property string currentNodeId: ""
    property bool _hydrating: false
    property var invoiceRows: []
    property string invoiceSortKey: "client"
    property bool invoiceSortAscending: true
    property var invoiceColumns: [
        { "key": "invoice", "label": "Invoice", "width": 76, "fill": false, "align": "left", "sortKey": "invoice" },
        { "key": "client", "label": "Client", "width": 0, "fill": true, "align": "left", "sortKey": "client" },
        { "key": "ageDays", "label": "Age", "width": 78, "fill": false, "align": "right", "sortKey": "ageDays" },
        { "key": "balance", "label": "Balance", "width": 92, "fill": false, "align": "right", "sortKey": "balance" }
    ]
    property var sortedInvoiceRows: root._sortedInvoiceRows()
    property var historyRows: []
    property var selectedInvoice: ({})
    // Keep the selection separate from the row object.  A table refresh
    // replaces row objects, but must never make the user lose the invoice
    // they are actively posting against.
    property string selectedInvoiceKey: ""
    property int selectedInvoiceIndex: -1
    property var modeOptions: ["Payment", "Write-off / Adjustment"]
    property var methodOptions: ["e-Transfer", "EFT", "Cheque", "Credit Card", "Cash", "Wire", "Other"]
    // The payment method describes how the client paid; this is the actual
    // business account receiving the money and is posted as FromAccount.
    property var depositAccountRows: []
    property var depositAccountOptions: []
    property string depositAccountCode: ""
    // A routed Invoice Directory -> Payment Entry tab begins with only an
    // invoice number. Wait until its live invoice row resolves, then apply
    // the balance once. Later refreshes must preserve a user's partial amount.
    property string _pendingFullAmountInvoiceKey: ""

    signal formDirtyChanged(bool dirty)
    signal saveFinished(bool ok, string message, string paymentId)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property color _accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _mutedText: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color _panel: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color _raisedPanel: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color _input: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color _border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property int fieldHeightPx: root.isProMode
        ? Math.max(38, Math.round(((metrics && metrics.contentH) ? metrics.contentH : height) * 0.048))
        : Math.max(40, Math.round(((metrics && metrics.contentH) ? metrics.contentH : height) * 0.056))
    property int panelRadiusPx: root.isProMode ? visualRules.radiusPanel : 12

    onDirtyChanged: formDirtyChanged(dirty)

    function _clean(value) {
        return String(value === undefined || value === null ? "" : value).trim()
    }

    function _num(value, fallback) {
        var n = parseFloat(_clean(value).replace(/[$,]/g, ""))
        return isFinite(n) ? n : fallback
    }

    function _todayIso() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function money(value) {
        var n = Number(value || 0)
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function _invoiceSortGlyph(column) {
        var key = _clean(column && column.sortKey !== undefined ? column.sortKey : (column && column.key))
        if (key !== _clean(invoiceSortKey)) return ""
        return invoiceSortAscending ? " ^" : " v"
    }

    function invoiceHeaderText(column) {
        return _clean(column && column.label) + _invoiceSortGlyph(column)
    }

    function invoiceHeaderColor(column) {
        var key = _clean(column && column.sortKey !== undefined ? column.sortKey : (column && column.key))
        return key === _clean(invoiceSortKey) ? root._accent : root._mutedText
    }

    function invoiceColumnAlignment(column) {
        return _clean(column && column.align).toLowerCase() === "right" ? Text.AlignRight : Text.AlignLeft
    }

    function invoiceCellText(row, column) {
        var key = _clean(column && column.key)
        if (key === "client") return _clean(row && (row.client || row.billingClient))
        if (key === "ageDays") return _clean(row && row.ageDays) + " days"
        if (key === "balance") return money(row && row.balance)
        return _clean(row && row[key])
    }

    function invoiceCellColor(column) {
        return _clean(column && column.key) === "balance" ? root._accent : root._text
    }

    function _invoiceSortValue(row, key) {
        var sortKey = _clean(key)
        if (sortKey === "client")
            return _clean(row && (row.client || row.billingClient)).toLowerCase()
        if (sortKey === "ageDays" || sortKey === "balance" || sortKey === "invoiceTotal" || sortKey === "paid" || sortKey === "credits")
            return Number(row && row[sortKey] !== undefined ? row[sortKey] : 0)
        return _clean(row && row[sortKey]).toLowerCase()
    }

    function _compareInvoiceRows(a, b, key, ascending) {
        var valA = _invoiceSortValue(a, key)
        var valB = _invoiceSortValue(b, key)
        if (valA < valB) return ascending ? -1 : 1
        if (valA > valB) return ascending ? 1 : -1

        var clientA = _invoiceSortValue(a, "client")
        var clientB = _invoiceSortValue(b, "client")
        if (clientA < clientB) return -1
        if (clientA > clientB) return 1

        var invoiceA = _invoiceSortValue(a, "invoice")
        var invoiceB = _invoiceSortValue(b, "invoice")
        if (invoiceA < invoiceB) return -1
        if (invoiceA > invoiceB) return 1
        return 0
    }

    function _sortedInvoiceRows() {
        var rows = []
        var source = invoiceRows || []
        for (var i = 0; i < source.length; i++) rows.push(source[i])
        var key = _clean(invoiceSortKey)
        if (key.length <= 0) return rows
        var asc = invoiceSortAscending !== false
        rows.sort(function(a, b) { return root._compareInvoiceRows(a, b, key, asc) })
        return rows
    }

    function selectedInvoiceNumber() {
        var retained = _clean(selectedInvoiceKey)
        return retained.length > 0 ? retained : _clean(selectedValue("invoice", ""))
    }

    function isSelectedInvoice(row) {
        var current = selectedInvoiceNumber()
        return current.length > 0 && _clean(row && row.invoice).toLowerCase() === current.toLowerCase()
    }

    function sortedInvoiceIndex(invoiceNumber) {
        var needle = _clean(invoiceNumber).toLowerCase()
        var rows = sortedInvoiceRows || []
        for (var i = 0; i < rows.length; i++) {
            if (_clean(rows[i] && rows[i].invoice).toLowerCase() === needle) return i
        }
        return -1
    }

    function toggleInvoiceSort(column) {
        var key = _clean(column && column.sortKey !== undefined ? column.sortKey : (column && column.key))
        if (key.length <= 0) return
        if (invoiceSortKey === key) {
            invoiceSortAscending = !invoiceSortAscending
        } else {
            invoiceSortKey = key
            invoiceSortAscending = true
        }
        selectedInvoiceIndex = sortedInvoiceIndex(selectedInvoiceNumber())
    }

    function selectedValue(key, fallback) {
        if (!selectedInvoice) return fallback || ""
        var value = selectedInvoice[key]
        return value === undefined || value === null ? (fallback || "") : value
    }

    function _markDirty() {
        if (!_hydrating) dirty = true
    }

    function backendReady() {
        return !!(root.appRef && root.appRef.backendBooted)
    }

    function _paymentBackend() {
        if (typeof docketApp !== "undefined" && docketApp) return docketApp
        if (root.appRef && root.appRef.docketing) return root.appRef.docketing
        return null
    }

    function _accountDisplay(row) {
        var account = row || ({})
        var code = _clean(account.accountCode)
        var name = _clean(account.accountName)
        if (code.length > 0 && name.length > 0 && code.toLowerCase() !== name.toLowerCase())
            return name + " (" + code + ")"
        return name || code
    }

    function _accountRowForStoredValue(value) {
        var needle = _clean(value).toLowerCase()
        if (needle.length <= 0) return null
        var rows = depositAccountRows || []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i] || ({})
            if (_clean(row.accountCode).toLowerCase() === needle
                    || _clean(row.accountName).toLowerCase() === needle
                    || _accountDisplay(row).toLowerCase() === needle) {
                return row
            }
        }
        return null
    }

    function _depositAccountCodeForDisplay(value) {
        var row = _accountRowForStoredValue(value)
        return row ? _clean(row.accountCode || row.accountName) : _clean(value)
    }

    function _displayForDepositAccount(value) {
        var row = _accountRowForStoredValue(value)
        return row ? _accountDisplay(row) : _clean(value)
    }

    function _defaultDepositAccountRow() {
        var rows = depositAccountRows || []
        var preferredCodes = ["CIBC_CHEQUING", "SIMPLII_CHEQUING", "OPERATING"]
        for (var p = 0; p < preferredCodes.length; p++) {
            for (var i = 0; i < rows.length; i++) {
                if (_clean(rows[i] && rows[i].accountCode).toUpperCase() === preferredCodes[p])
                    return rows[i]
            }
        }
        return rows.length > 0 ? rows[0] : null
    }

    function _setDepositAccount(value) {
        var stored = _clean(value)
        depositAccountCode = _depositAccountCodeForDisplay(stored)
        if (depositAccountCombo)
            depositAccountCombo.editText = _displayForDepositAccount(stored)
    }

    function loadDepositAccounts() {
        if (!backendReady() || !root.appRef || !root.appRef.listTransactionAccounts) return
        var rows = []
        try {
            rows = root.appRef.listTransactionAccounts()
        } catch (e) {
            rows = []
        }
        if (!rows || rows.length === undefined) rows = []

        var normalized = []
        var options = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i] || ({})
            if (_clean(row.accountCode).length <= 0 && _clean(row.accountName).length <= 0) continue
            normalized.push(row)
            options.push(_accountDisplay(row))
        }

        _hydrating = true
        depositAccountRows = normalized
        depositAccountOptions = options
        if (_clean(depositAccountCode).length > 0) {
            _setDepositAccount(depositAccountCode)
        } else {
            var fallback = _defaultDepositAccountRow()
            if (fallback) _setDepositAccount(_clean(fallback.accountCode || fallback.accountName))
        }
        _hydrating = false
    }

    function _applyPendingFullAmountIfResolved() {
        var pending = _clean(_pendingFullAmountInvoiceKey)
        if (pending.length <= 0 || selectedInvoiceNumber().toLowerCase() !== pending.toLowerCase()) return
        if (!selectedInvoice || selectedInvoice.balance === undefined) return
        _hydrating = true
        amountInput.text = Number(selectedInvoice.balance || 0).toFixed(2)
        _hydrating = false
        _pendingFullAmountInvoiceKey = ""
    }

    function refreshInvoices() {
        if (!backendReady() || !root.appRef || !root.appRef.listOpenPaymentInvoices) {
            invoiceRows = []
            return
        }
        var rows = []
        try {
            rows = root.appRef.listOpenPaymentInvoices({ "query": _clean(searchInput.text) })
        } catch (e) {
            rows = []
        }
        if (!rows || rows.length === undefined) rows = []
        // Capture the scalar key before replacing the list/model.  In
        // particular, do not reset amountInput here: a refresh can arrive
        // while the user is changing a partial-payment amount.
        var selectedNumber = selectedInvoiceNumber()
        invoiceRows = rows
        if (selectedNumber.length > 0) {
            var nextSelectedIndex = sortedInvoiceIndex(selectedNumber)
            if (nextSelectedIndex >= 0) {
                selectedInvoiceIndex = nextSelectedIndex
                var rowsProxy = sortedInvoiceRows || []
                if (nextSelectedIndex < rowsProxy.length) {
                    selectedInvoice = rowsProxy[nextSelectedIndex]
                    selectedInvoiceKey = _clean(selectedInvoice.invoice)
                    _applyPendingFullAmountIfResolved()
                }
            } else {
                // A search or a background refresh may temporarily omit the
                // selected invoice.  Preserve its last known details and the
                // user's in-progress payment rather than clearing the form.
                selectedInvoiceIndex = -1
            }
        }
    }

    function loadPaymentForEdit(paymentId) {
        var backend = _paymentBackend()
        if (!backend || !backend.getPaymentEntry) {
            lastSaveOk = false
            saveMessage = "Payment editing is unavailable."
            return
        }
        var result = {}
        try {
            result = backend.getPaymentEntry(paymentId)
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (!result || !result.ok) {
            lastSaveOk = false
            saveMessage = _clean(result && result.message) || "The selected payment could not be loaded."
            return
        }

        _hydrating = true
        editingPaymentId = _clean(result.paymentId || paymentId)
        editingOriginalPaymentAmount = Number(result.amount || 0)
        editingOriginalAdjustmentAmount = Number(result.adjustmentAmount || 0)
        selectedInvoice = result.invoiceRow || { "invoice": _clean(result.invoice) }
        selectedInvoiceKey = _clean(result.invoice || selectedInvoice.invoice)
        selectedInvoiceIndex = sortedInvoiceIndex(_clean(result.invoice))
        searchInput.text = _clean(result.invoice)
        dateInput.text = _clean(result.date)
        modeCombo.editText = _clean(result.mode) || "Payment"
        methodCombo.editText = _clean(result.method) || "EFT"
        _setDepositAccount(_clean(result.depositAccount))
        referenceInput.text = _clean(result.reference)
        amountInput.text = Number(result.amount || 0).toFixed(2)
        adjustmentAmountInput.text = Number(result.adjustmentAmount || 0).toFixed(2)
        adjustmentReasonInput.text = _clean(result.adjustmentReason)
        notesInput.text = _clean(result.notes)
        lastSavedPaymentId = editingPaymentId
        saveMessage = "Editing saved payment " + editingPaymentId + "."
        lastSaveOk = true
        _hydrating = false
        dirty = false
        refreshHistory()
    }

    function refreshHistory() {
        var invoice = _clean(selectedValue("invoice", ""))
        if (!invoice || !root.appRef || !root.appRef.listInvoicePaymentHistory) {
            historyRows = []
            return
        }
        var rows = []
        try {
            rows = root.appRef.listInvoicePaymentHistory(invoice)
        } catch (e) {
            rows = []
        }
        historyRows = rows && rows.length !== undefined ? rows : []
    }

    function selectInvoice(row, index) {
        _hydrating = true
        editingPaymentId = ""
        editingOriginalPaymentAmount = 0
        editingOriginalAdjustmentAmount = 0
        selectedInvoice = row || ({})
        selectedInvoiceKey = _clean(selectedInvoice.invoice)
        selectedInvoiceIndex = index
        _pendingFullAmountInvoiceKey = ""
        amountInput.text = selectedInvoice && selectedInvoice.balance !== undefined
            ? Number(selectedInvoice.balance || 0).toFixed(2)
            : ""
        dateInput.text = _todayIso()
        modeCombo.editText = "Payment"
        methodCombo.editText = "EFT"
        referenceInput.text = ""
        notesInput.text = ""
        adjustmentAmountInput.text = ""
        adjustmentReasonInput.text = ""
        saveMessage = ""
        lastSavedPaymentId = ""
        editingPaymentId = ""
        editingOriginalPaymentAmount = 0
        editingOriginalAdjustmentAmount = 0
        _hydrating = false
        dirty = false
        
        if (root.currentNodeId === "C09") {
            adjustmentAmountInput.forceActiveFocus()
        } else {
            amountInput.forceActiveFocus()
        }
        
        refreshHistory()
    }

    function resetDraft() {
        if (editingPaymentId) {
            loadPaymentForEdit(editingPaymentId)
            return
        }
        _hydrating = true
        dateInput.text = _todayIso()
        modeCombo.editText = "Payment"
        methodCombo.editText = "EFT"
        amountInput.text = selectedInvoice && selectedInvoice.balance !== undefined
            ? Number(selectedInvoice.balance || 0).toFixed(2)
            : ""
        referenceInput.text = ""
        notesInput.text = ""
        adjustmentAmountInput.text = ""
        adjustmentReasonInput.text = ""
        saveMessage = ""
        lastSavedPaymentId = ""
        _hydrating = false
        dirty = false
        
        if (root.currentNodeId === "C09") {
            adjustmentAmountInput.forceActiveFocus()
        } else {
            amountInput.forceActiveFocus()
        }
    }

    function _buildPayload() {
        return {
            "invoice": _clean(selectedValue("invoice", "")),
            "date": _clean(dateInput.text),
            "mode": _clean(modeCombo.editText),
            "method": _clean(methodCombo.editText),
            "depositAccount": _clean(depositAccountCode) || _depositAccountCodeForDisplay(depositAccountCombo.editText),
            "reference": _clean(referenceInput.text),
            "paymentId": editingPaymentId,
            "amount": _num(amountInput.text, 0.0),
            "adjustmentAmount": _num(adjustmentAmountInput.text, 0.0),
            "adjustmentReason": _clean(adjustmentReasonInput.text),
            "notes": _clean(notesInput.text)
        }
    }

    function _validatePayload(payload) {
        if (!_clean(payload.invoice)) return "Select an open invoice first."
        if (!_clean(payload.date).match(/^\d{4}-\d{2}-\d{2}$/)) return "Date must be in YYYY-MM-DD format."
        var paymentAmt = Number(payload.amount || 0)
        var adjAmt = Number(payload.adjustmentAmount || 0)
        if (paymentAmt <= 0 && adjAmt <= 0) return "You must enter a payment or adjustment amount greater than 0."
        var totalApplied = paymentAmt + adjAmt
        var balance = Number(selectedValue("balance", 0) || 0)
        if (!editingPaymentId && totalApplied - balance > 0.01) return "Total amount exceeds the selected invoice balance."
        if (paymentAmt > 0 && _clean(payload.mode).toLowerCase().indexOf("payment") >= 0 && !_clean(payload.method)) return "Payment method is required."
        if (paymentAmt > 0 && _clean(payload.mode).toLowerCase().indexOf("payment") >= 0 && !_clean(payload.depositAccount)) return "Select the account receiving this payment."
        if (adjAmt > 0 && !_clean(payload.adjustmentReason)) return "Adjustment reason is required if an adjustment amount is entered."
        return ""
    }

    function runPrimaryAction() {
        if (saveInProgress) return
        var payload = _buildPayload()
        var validation = _validatePayload(payload)
        if (validation.length > 0) {
            lastSaveOk = false
            saveMessage = validation
            dirty = true
            saveFinished(false, saveMessage, "")
            return
        }
        var backend = _paymentBackend()
        if (!backend || (editingPaymentId ? !backend.updatePayment : !backend.postPayment)) {
            lastSaveOk = false
            saveMessage = editingPaymentId ? "Payment editing backend is unavailable." : "Payment backend is unavailable."
            dirty = true
            saveFinished(false, saveMessage, "")
            return
        }
        saveInProgress = true
        try {
            if (editingPaymentId) backend.updatePayment(payload)
            else backend.postPayment(payload)
        } catch (e) {
            saveInProgress = false
            lastSaveOk = false
            saveMessage = String(e)
            dirty = true
            saveFinished(false, saveMessage, "")
        }
    }

    function snapshotState() {
        return {
            "searchText": _clean(searchInput.text),
            "selectedInvoice": selectedInvoice,
            "selectedInvoiceNum": selectedInvoiceNumber(),
            "selectedInvoiceIndex": selectedInvoiceIndex,
            "invoiceSortKey": invoiceSortKey,
            "invoiceSortAscending": invoiceSortAscending,
            "payload": _buildPayload(),
            "saveMessage": saveMessage,
            "lastSavedPaymentId": lastSavedPaymentId,
            "paymentId": editingPaymentId,
            "dirty": dirty
        }
    }

    function applyState(state) {
        if (!state) return
        var paymentId = _clean(state.paymentId || state.editPaymentId)
        _hydrating = true
        var searchVal = String(state.invoiceNum || state.searchText || "")
        searchInput.text = _clean(searchVal)
        selectedInvoice = state.selectedInvoice || ({})
        var restoredInvoice = _clean(state.invoiceNum || state.selectedInvoiceNum || selectedInvoice.invoice)
        if (restoredInvoice.length > 0 && (!selectedInvoice || _clean(selectedInvoice.invoice).length <= 0)) {
            selectedInvoice = { "invoice": restoredInvoice }
        }
        selectedInvoiceKey = restoredInvoice
        selectedInvoiceIndex = state.selectedInvoiceIndex !== undefined
            ? Number(state.selectedInvoiceIndex)
            : -1
        invoiceSortKey = _clean(state.invoiceSortKey) || "client"
        invoiceSortAscending = state.invoiceSortAscending !== undefined ? !!state.invoiceSortAscending : true
        var payload = state.payload || ({})
        dateInput.text = _clean(payload.date) || _todayIso()
        var defaultMode = "Payment"
        if (state.focusNodeId === "C09") {
            defaultMode = "Write-Off"
        }
        modeCombo.editText = _clean(payload.mode) || defaultMode
        methodCombo.editText = _clean(payload.method) || "EFT"
        if (_clean(payload.depositAccount).length > 0)
            _setDepositAccount(_clean(payload.depositAccount))
        referenceInput.text = _clean(payload.reference)
        amountInput.text = payload.amount !== undefined ? String(payload.amount) : ""
        adjustmentAmountInput.text = payload.adjustmentAmount !== undefined ? String(payload.adjustmentAmount) : ""
        adjustmentReasonInput.text = _clean(payload.adjustmentReason)
        notesInput.text = _clean(payload.notes)
        saveMessage = _clean(state.saveMessage)
        lastSavedPaymentId = _clean(state.lastSavedPaymentId)
        _pendingFullAmountInvoiceKey = (!paymentId && restoredInvoice.length > 0 && payload.amount === undefined)
            ? restoredInvoice
            : ""
        if (!paymentId) {
            editingPaymentId = ""
            editingOriginalPaymentAmount = 0
            editingOriginalAdjustmentAmount = 0
        }
        _hydrating = false
        dirty = !!state.dirty
        if (paymentId) {
            loadPaymentForEdit(paymentId)
            return
        }
        refreshInvoices()
        refreshHistory()
    }

    Connections {
        target: root._paymentBackend()
        ignoreUnknownSignals: true
        function onPaymentSaveFinished(result) {
            if (!root.saveInProgress) return
            root.saveInProgress = false
            root.lastSaveOk = !!(result && result.ok)
            var paymentId = (result && result.paymentId !== undefined && result.paymentId !== null) ? result.paymentId : ""
            root.lastSavedPaymentId = root._clean(paymentId)
            root.saveMessage = root._clean(result && result.message)
            if (root.saveMessage.length <= 0) {
                root.saveMessage = root.lastSaveOk
                    ? (root.editingPaymentId ? "Payment updated." : "Payment posted.")
                    : (root.editingPaymentId ? "Payment update failed." : "Payment posting failed.")
            }
            if (root.lastSaveOk) {
                if (typeof app !== "undefined" && app && app.recordTelemetry) {
                    app.recordTelemetry("Action_Save", "Payment Entry saved: " + root.lastSavedPaymentId)
                }
                root.dirty = false
                if (result && result.invoiceRow) {
                    root.selectedInvoice = result.invoiceRow
                    root.selectedInvoiceKey = root._clean(result.invoiceRow.invoice)
                }
                if (root.editingPaymentId) {
                    root.editingPaymentId = root._clean((result && result.paymentId) || root.editingPaymentId)
                    root.editingOriginalPaymentAmount = Number(result && result.paymentAmount !== undefined ? result.paymentAmount : amountInput.text)
                    root.editingOriginalAdjustmentAmount = Number(result && result.adjustmentAmount !== undefined ? result.adjustmentAmount : adjustmentAmountInput.text)
                } else {
                    amountInput.text = root.selectedInvoice && root.selectedInvoice.balance !== undefined ? Number(root.selectedInvoice.balance || 0).toFixed(2) : ""
                    adjustmentAmountInput.text = ""
                    adjustmentReasonInput.text = ""
                    referenceInput.text = ""
                    notesInput.text = ""
                }
                
                root.refreshInvoices()
                root.refreshHistory()
            } else {
                root.dirty = true
            }
            root.saveFinished(root.lastSaveOk, root.saveMessage, root.lastSavedPaymentId)
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onBackendBootChanged() {
            if (root.visible && root.backendReady()) {
                root.loadDepositAccounts()
                root.refreshInvoices()
            }
        }
        function onTransactionDataChanged() {
            if (root.visible && root.backendReady() && !root.saveInProgress) root.refreshInvoices()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.isProMode ? 14 : 10
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.fieldHeightPx
            spacing: 8

            ModernTextField {
                id: searchInput
                t: root.t
                metrics: root.metrics
                appStyle: root.appStyle
                label: "Search unpaid invoices"
                Layout.fillWidth: true
                Layout.preferredHeight: root.fieldHeightPx
                onAccepted: root.refreshInvoices()
                onTextEdited: root.refreshInvoices()
            }

            PillButton {
                text: "Find"
                t: root.t
                metrics: root.metrics
                appStyle: root.appStyle
                primary: true
                Layout.preferredWidth: 92
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: root.refreshInvoices()
            }

            PillButton {
                text: "Reset"
                t: root.t
                metrics: root.metrics
                appStyle: root.appStyle
                Layout.preferredWidth: 92
                Layout.preferredHeight: root.fieldHeightPx
                onClicked: {
                    searchInput.text = ""
                    root.refreshInvoices()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Rectangle {
                Layout.preferredWidth: Math.max(420, Math.round(root.width * 0.46))
                Layout.fillHeight: true
                radius: root.panelRadiusPx
                color: root._raisedPanel
                border.width: 1
                border.color: root._border
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        Text {
                            Layout.fillWidth: true
                            text: "Open invoices"
                            color: root._text
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: String(root.invoiceRows.length || 0)
                            color: root._mutedText
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        color: root._input
                        border.width: 1
                        border.color: root._border
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 8
                            Repeater {
                                model: root.invoiceColumns
                                Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: modelData.fill === true
                                    Layout.preferredWidth: modelData.fill === true ? 1 : Number(modelData.width || 80)
                                    Layout.fillHeight: true
                                    color: headerHover.containsMouse ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, root.isProMode ? 0.07 : 0.14) : "transparent"
                                    radius: root.isProMode ? 3 : 7

                                    Text {
                                        anchors.fill: parent
                                        anchors.leftMargin: 0
                                        anchors.rightMargin: 0
                                        verticalAlignment: Text.AlignVCenter
                                        horizontalAlignment: root.invoiceColumnAlignment(parent.modelData)
                                        text: root.invoiceHeaderText(parent.modelData)
                                        color: root.invoiceHeaderColor(parent.modelData)
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    MouseArea {
                                        id: headerHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.toggleInvoiceSort(parent.modelData)
                                    }
                                }
                            }
                        }
                    }

                    ListView {
                        id: invoiceList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.sortedInvoiceRows
                        spacing: 5
                        delegate: Rectangle {
                            property var rowData: modelData
                            width: ListView.view.width
                            height: 50
                            radius: root.isProMode ? 4 : 9
                            color: root.isSelectedInvoice(rowData)
                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, root.isProMode ? 0.13 : 0.22)
                                : root._input
                            border.width: 1
                            border.color: root.isSelectedInvoice(rowData) ? root._accent : root._border

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8
                                Repeater {
                                    model: root.invoiceColumns
                                    Text {
                                        required property var modelData
                                        Layout.fillWidth: modelData.fill === true
                                        Layout.preferredWidth: modelData.fill === true ? 1 : Number(modelData.width || 80)
                                        text: root.invoiceCellText(rowData, modelData)
                                        color: root.invoiceCellColor(modelData)
                                        font.family: "Segoe UI"
                                        font.pixelSize: 12
                                        font.weight: root._clean(modelData.key) === "balance" ? Font.DemiBold : Font.Normal
                                        horizontalAlignment: root.invoiceColumnAlignment(modelData)
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.selectInvoice(parent.rowData, index)
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.panelRadiusPx
                color: root._raisedPanel
                border.width: 1
                border.color: root._border
                clip: true

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 10
                    contentWidth: width
                    contentHeight: detailColumn.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    clip: true

                    ColumnLayout {
                        id: detailColumn
                        width: parent.width
                        spacing: 7

                        Text {
                            Layout.fillWidth: true
                            text: root._clean(root.selectedValue("invoice", "")).length > 0
                                ? ((root.editingPaymentId ? "Edit payment — Invoice " : "Invoice ") + root.selectedValue("invoice", ""))
                                : "Select an open invoice"
                            color: root._text
                            font.family: "Segoe UI"
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 5

                            Repeater {
                                model: [
                                    { "label": "Client", "value": root.selectedValue("client", "") },
                                    { "label": "Billing client", "value": root.selectedValue("billingClient", "") },
                                    { "label": "Invoice total", "value": root.money(root.selectedValue("invoiceTotal", 0)) },
                                    { "label": "Paid/Credits", "value": root.money(root.selectedValue("paid", 0)) },
                                    { "label": "Balance due", "value": root.money(root.selectedValue("balance", 0)) },
                                    { "label": "Status", "value": root.selectedValue("status", "") }
                                ]
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 39
                                    radius: root.isProMode ? 4 : 9
                                    color: root._input
                                    border.width: 1
                                    border.color: root._border
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 5
                                        spacing: 1
                                        Text { width: parent.width; text: modelData.label; color: root._mutedText; font.family: "Segoe UI"; font.pixelSize: 10; elide: Text.ElideRight }
                                        Text { width: parent.width; text: root._clean(modelData.value); color: root._text; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                    }
                                }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.width > 980 ? 2 : 1
                            columnSpacing: 8
                            rowSpacing: 6

                            ModernTextField {
                                id: dateInput
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Date"
                                datePickerEnabled: true
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onTextEdited: root._markDirty()
                            }
                            ModernTextField {
                                id: amountInput
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Payment ($)"
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onTextEdited: root._markDirty()
                            }
                            ModernTextField {
                                id: adjustmentAmountInput
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Adjustment ($)"
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onTextEdited: root._markDirty()
                            }
                            ModernTextField {
                                id: adjustmentReasonInput
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Adj Reason"
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onTextEdited: root._markDirty()
                            }
                            ModernComboBox {
                                id: modeCombo
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Mode"
                                fullModel: root.modeOptions
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onEditTextChanged: root._markDirty()
                            }
                            ModernComboBox {
                                id: methodCombo
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Method"
                                fullModel: root.methodOptions
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onEditTextChanged: root._markDirty()
                            }
                            ModernComboBox {
                                id: depositAccountCombo
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Deposit account"
                                fullModel: root.depositAccountOptions
                                preserveUnknownEditTextOnModelChanged: true
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onActivated: {
                                    root.depositAccountCode = root._depositAccountCodeForDisplay(editText)
                                    root._markDirty()
                                }
                                onEditTextChanged: {
                                    root.depositAccountCode = root._depositAccountCodeForDisplay(editText)
                                    root._markDirty()
                                }
                            }
                            ModernTextField {
                                id: referenceInput
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                label: "Reference / Cheque #"
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onTextEdited: root._markDirty()
                            }
                        }

                        TextArea {
                            id: notesInput
                            Layout.fillWidth: true
                            Layout.preferredHeight: 76
                            color: root._text
                            placeholderText: "Notes"
                            placeholderTextColor: root._mutedText
                            wrapMode: Text.Wrap
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            onTextChanged: root._markDirty()
                            background: Rectangle {
                                color: root._input
                                radius: root.isProMode ? 4 : 9
                                border.width: notesInput.activeFocus ? 2 : 1
                                border.color: notesInput.activeFocus ? root._accent : root._border
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 42
                            radius: root.isProMode ? 4 : 9
                            color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                            border.width: 1
                            border.color: SemanticTheme.destructiveHover(root.t, root.appStyle)
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8
                                Text {
                                    Layout.fillWidth: true
                                    text: root.editingPaymentId ? "Projected balance after update" : "Projected balance after posting"
                                    color: root._text
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: root.money(Math.max(0, Number(root.selectedValue("balance", 0) || 0) + root.editingOriginalPaymentAmount + root.editingOriginalAdjustmentAmount - root._num(amountInput.text, 0) - root._num(adjustmentAmountInput.text, 0)))
                                    color: root._accent
                                    font.family: "Segoe UI"
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.fieldHeightPx
                            spacing: 8
                            PillButton {
                                text: root.saveInProgress ? (root.editingPaymentId ? "Updating..." : "Posting...") : (root.editingPaymentId ? "Update Payment" : "Post Transaction")
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                primary: true
                                enabled: !root.saveInProgress
                                    && root._clean(root.selectedValue("invoice", "")).length > 0
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.runPrimaryAction()
                            }
                            PillButton {
                                text: root.editingPaymentId ? "Reset" : "Clear"
                                t: root.t
                                metrics: root.metrics
                                appStyle: root.appStyle
                                Layout.preferredWidth: 100
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.resetDraft()
                            }
                        }

                        Rectangle {
                            visible: root.saveMessage.length > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: saveMessageText.implicitHeight + 16
                            color: root.lastSaveOk
                                ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "success", root.appStyle), 0.12)
                                : SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.12)
                            border.color: root.lastSaveOk
                                ? SemanticTheme.tone(root.t, "success", root.appStyle)
                                : SemanticTheme.tone(root.t, "error", root.appStyle)
                            border.width: 1
                            radius: 4
                            Text {
                                id: saveMessageText
                                anchors.fill: parent
                                anchors.margins: 8
                                text: root.saveMessage
                                color: root.lastSaveOk
                                    ? SemanticTheme.tone(root.t, "success", root.appStyle)
                                    : SemanticTheme.tone(root.t, "error", root.appStyle)
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                wrapMode: Text.WordWrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Recent payment evidence"
                            color: root._text
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Repeater {
                            model: root.historyRows
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                radius: root.isProMode ? 4 : 8
                                color: root._input
                                border.width: 1
                                border.color: root._border
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8
                                    Text { Layout.preferredWidth: 82; text: root._clean(modelData.date); color: root._mutedText; font.pixelSize: 11; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: root._clean(modelData.type) + " " + root._clean(modelData.reference); color: root._text; font.pixelSize: 11; elide: Text.ElideRight }
                                    Text { Layout.preferredWidth: 82; horizontalAlignment: Text.AlignRight; text: root.money(modelData.amount); color: root._accent; font.pixelSize: 11; font.weight: Font.DemiBold }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    onVisibleChanged: {
        if (visible && backendReady()) {
            loadDepositAccounts()
            refreshInvoices()
        }
    }

    Component.onCompleted: {
        resetDraft()
        if (backendReady()) {
            loadDepositAccounts()
            refreshInvoices()
        }
    }
}
