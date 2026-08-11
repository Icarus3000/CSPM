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

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property bool dirty: false
    property bool saveInProgress: false
    property bool lastSaveOk: true
    property string saveMessage: ""
    property string lastSavedTransactionId: ""
    property bool _hydrating: false
    // An existing transaction must retain its stored combo values even if the
    // related account/client/matter was later retired from current lookups.
    property bool editingStoredTransaction: false
    // Async save callback target — resolved at runtime
    property var docketAppRef: (typeof docketApp !== "undefined") ? docketApp : null

    property var classOptions: ["Family", "Business"]
    property var typeOptions: ["Income", "Expense", "Debt Repayment", "Transfer"]
    property var memberOptions: ["Joint", "Deborah", "Cory", "Alexa", "Emma", "Maya"]
    property var taxFlagOptions: ["None", "HST - Biz", "Business Deductible", "Medical", "Deductible"]
    property var statusOptions: ["Pending", "Cleared", "Reconciled", "Void"]
    property var currencyOptions: ["CAD", "USD"]
    property var yesNoOptions: ["No", "Yes"]
    property var accountNames: []
    property var businessUnits: []
    property var payees: []
    property var categoryRows: []
    property var categoryDisplay: []
    property var parentNames: []
    property var clientNames: []
    property var matterNames: []
    property var matterDirectoryRows: []
    property var matterDisplayOptions: []
    property var recentRows: []

    property color _accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _mutedText: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color _panel: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color _raisedPanel: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color _border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color _appBg: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property int fieldHeightPx: root.isProMode
        ? Math.max(46, Math.round(((metrics && metrics.contentH) ? metrics.contentH : height) * 0.060))
        : Math.max(40, Math.round(((metrics && metrics.contentH) ? metrics.contentH : height) * 0.06))
    property int sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : Math.max(9, Math.round(Math.sqrt(Math.max(1, width) * Math.max(1, height)) * 0.011))
    property int formFieldMinimumWidthPx: Math.max(176, Math.round(Math.min(Math.max(1, width), Math.max(1, height)) * 0.180))

    signal formDirtyChanged(bool dirty)
    signal saveFinished(bool ok, string message, string transactionId)

    onDirtyChanged: formDirtyChanged(dirty)

    function _clean(v) { return String(v === undefined || v === null ? "" : v).trim() }
    function _lower(v) { return _clean(v).toLowerCase() }
    function formGridColumns(preferredColumns, availableWidth) {
        var desired = Math.max(1, Math.round(Number(preferredColumns || 1)))
        var usableWidth = Math.max(1, Math.round(Number(availableWidth || root.width || 1)))
        var gap = 6
        var maxByWidth = Math.max(1, Math.floor((usableWidth + gap) / (root.formFieldMinimumWidthPx + gap)))
        return Math.max(1, Math.min(desired, maxByWidth))
    }
    function formGridSpan(columnCount, desiredSpan) {
        return Math.max(1, Math.min(Math.max(1, Number(columnCount || 1)), Math.max(1, Number(desiredSpan || 1))))
    }
    function _num(v, fallback) {
        var n = parseFloat(_clean(v))
        return isFinite(n) ? n : fallback
    }
    function _todayIso() { return Qt.formatDate(new Date(), "yyyy-MM-dd") }
    function _yesNoToInt(v) { return _lower(v) === "yes" ? 1 : 0 }
    function _needsToAccount() { var t = _lower(typeCombo.editText); return t === "transfer" || t === "debt repayment" }
    function _isExpense() { return _lower(typeCombo.editText) === "expense" }
    function _isBusiness() { return _lower(classCombo.editText) === "business" }
    function _markDirty() { if (!_hydrating) dirty = true }

    function _resolveCategory() {
        var raw = _clean(categoryCombo.editText)
        if (raw.length <= 0) return { "code": "", "name": "" }
        var rawLower = raw.toLowerCase()
        for (var i = 0; i < categoryRows.length; i++) {
            var row = categoryRows[i]
            var code = _clean(row.categoryCode)
            var name = _clean(row.categoryName)
            var display = code.length > 0 && name.length > 0 ? (code + " - " + name) : (code + name)
            if (rawLower === _lower(code) || rawLower === _lower(name) || rawLower === _lower(display)) {
                return { "code": code, "name": name }
            }
        }
        var dash = raw.indexOf(" - ")
        if (dash > 0) return { "code": _clean(raw.slice(0, dash)), "name": _clean(raw.slice(dash + 3)) }
        return { "code": raw, "name": raw }
    }

    function _recalcClaim() {
        var amount = _num(amountInput.text, 0.0)
        var tax = _num(taxAmountInput.text, 0.0)
        var pct = _num(billClaimPctInput.text, 0.0)
        if (!_isExpense() || _yesNoToInt(generalOfficeCombo.editText) === 1) pct = 0.0
        totalClaimAmountInput.text = ((amount + tax) * (pct / 100.0)).toFixed(2)
    }

    function _matterDisplayLabel(row) {
        if (!row) return ""
        var clientName = _clean(row.clientName || "")
        var matterName = _clean(row.matterName || row.displayName || "")
        if (matterName.length <= 0) return ""
        var matterNumber = _clean(row.matterNumber || "")
        if (clientName.length > 0 && matterNumber.length > 0) return clientName + " | " + matterName + " | " + matterNumber
        if (clientName.length > 0) return clientName + " | " + matterName
        if (matterNumber.length > 0) return matterName + " | " + matterNumber
        return matterName
    }

    function _matterNameFromSelection(selectionText) {
        var typed = _clean(selectionText)
        if (typed.length <= 0) return ""
        var typedLower = typed.toLowerCase()
        for (var i = 0; i < matterDirectoryRows.length; i++) {
            var row = matterDirectoryRows[i]
            var matterName = _clean(row.matterName || row.displayName || "")
            var displayLabel = _matterDisplayLabel(row)
            if (typedLower === matterName.toLowerCase() || typedLower === displayLabel.toLowerCase()) {
                return matterName
            }
        }
        var parts = typed.split("|")
        if (parts.length >= 3) {
            var canonicalMatter = _clean(parts[1])
            if (canonicalMatter.length > 0) return canonicalMatter
        }
        if (parts.length === 2) {
            var firstToken = _clean(parts[0])
            var secondToken = _clean(parts[1])
            var firstLower = firstToken.toLowerCase()
            var secondLower = secondToken.toLowerCase()
            var firstIsMatterNumber = false
            var secondIsMatterNumber = false
            for (var m = 0; m < matterDirectoryRows.length; m++) {
                var probeNumber = _clean((matterDirectoryRows[m] || {}).matterNumber).toLowerCase()
                if (probeNumber.length <= 0) continue
                if (probeNumber === firstLower) firstIsMatterNumber = true
                if (probeNumber === secondLower) secondIsMatterNumber = true
            }
            if (secondIsMatterNumber && firstToken.length > 0) return firstToken
            if (firstIsMatterNumber && secondToken.length > 0) return secondToken
            if (secondToken.length > 0) return secondToken
            if (firstToken.length > 0) return firstToken
        }
        return typed
    }

    function _matterDisplayTextForMatterName(matterName) {
        var target = _clean(matterName)
        if (target.length <= 0) return ""
        var targetLower = target.toLowerCase()
        for (var i = 0; i < matterDirectoryRows.length; i++) {
            var row = matterDirectoryRows[i]
            var rowName = _clean(row.matterName || row.displayName || "")
            if (rowName.toLowerCase() === targetLower) return _matterDisplayLabel(row)
        }
        return target
    }

    function _parseIsoOrToday(textValue) {
        var text = _clean(textValue)
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year && candidate.getMonth() === monthIndex && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function backendReady() {
        return !!(root.appRef && root.appRef.backendBooted)
    }

    function canRunLookupRefresh() {
        return root.visible && root.backendReady()
    }

    function scheduleLookupRefresh() {
        lookupRefreshTimer.restart()
    }

    function scheduleCategoryLookupRefresh() {
        categoryLookupTimer.restart()
    }

    function openTxnDatePicker(px, py) {
        txnDateCalendarLoader.active = true
        Qt.callLater(function() {
            var cal = txnDateCalendarLoader.item
            if (!cal) return
            cal.selectedDate = _parseIsoOrToday(txnDateInput.text)
            if (typeof cal.openAt === "function") cal.openAt(px, py)
            else if (typeof cal.open === "function") cal.open()
            else cal.visible = true
        })
    }

    function _applyRules() {
        if (_hydrating) return
        _hydrating = true
        // Draft-entry rules must never erase the stored context of an
        // existing transaction.  Historic transfer rows can legitimately
        // retain a client/matter even though those fields are not normally
        // collected for a brand-new transfer.
        if (!editingStoredTransaction) {
            if (!_needsToAccount()) toAccountCombo.editText = ""
            if (!_isExpense()) {
                generalOfficeCombo.editText = "No"
                parentCombo.editText = ""
                clientCombo.editText = ""
                matterCombo.editText = ""
                billClaimPctInput.text = "0.00"
            }
            if (_yesNoToInt(generalOfficeCombo.editText) === 1) {
                parentCombo.editText = ""
                clientCombo.editText = ""
                matterCombo.editText = ""
                billClaimPctInput.text = "0.00"
            }
        }
        if (_yesNoToInt(hstExemptCombo.editText) === 1) {
            taxAmountInput.text = "0.00"
        }
        if (_lower(statusCombo.editText) !== "void") {
            voidReasonInput.text = ""
        }
        _hydrating = false
        scheduleCategoryLookupRefresh()
        _recalcClaim()
    }

    function _buildPayload() {
        var cat = _resolveCategory()
        return {
            "transactionId": _clean(transactionIdInput.text),
            "txnDate": _clean(txnDateInput.text),
            "class": _clean(classCombo.editText),
            "businessUnit": _clean(businessUnitCombo.editText),
            "type": _clean(typeCombo.editText),
            "fromAccount": _clean(fromAccountCombo.editText),
            "toAccount": _clean(toAccountCombo.editText),
            "payee": _clean(payeeCombo.editText),
            "parent": _clean(parentCombo.editText),
            "client": _clean(clientCombo.editText),
            "matter": _matterNameFromSelection(matterCombo.editText),
            "categoryCode": _clean(cat.code),
            "categoryName": _clean(cat.name),
            "member": _clean(memberCombo.editText),
            "amount": _num(amountInput.text, 0.0),
            "taxAmount": _num(taxAmountInput.text, 0.0),
            "taxFlag": _clean(taxFlagCombo.editText),
            "hstExempt": _yesNoToInt(hstExemptCombo.editText),
            "generalOfficeExpense": _yesNoToInt(generalOfficeCombo.editText),
            "shadow": _yesNoToInt(shadowCombo.editText),
            "invoiceRef": _clean(invoiceRefInput.text),
            "billClaimPct": _num(billClaimPctInput.text, 0.0),
            "totalClaimAmount": _num(totalClaimAmountInput.text, 0.0),
            "expenseDetails": _clean(expenseDetailsInput.text),
            "notes": _clean(notesInput.text),
            "status": _clean(statusCombo.editText),
            "currency": _clean(currencyCombo.editText),
            "voidReason": _clean(voidReasonInput.text)
        }
    }

    function refreshCategoryLookups() {
        if (!root.backendReady()) {
            categoryRows = []
            categoryDisplay = []
            categoryCombo.fullModel = []
            return
        }
        if (!appRef || !appRef.listTransactionCategories) {
            categoryRows = []
            categoryDisplay = []
            categoryCombo.fullModel = []
            return
        }
        var rows = []
        try {
            rows = appRef.listTransactionCategories(_clean(typeCombo.editText), _clean(classCombo.editText), false)
        } catch (e) {
            rows = []
        }
        categoryRows = rows && rows.length !== undefined ? rows : []
        var out = []
        for (var i = 0; i < categoryRows.length; i++) {
            var row = categoryRows[i]
            var code = _clean(row.categoryCode)
            var name = _clean(row.categoryName)
            if (code.length <= 0 && name.length <= 0) continue
            out.push(code.length > 0 && name.length > 0 ? (code + " - " + name) : (code + name))
        }
        categoryDisplay = out
        categoryCombo.fullModel = categoryDisplay
    }

    function loadRecentTransactions() {
        if (!root.backendReady()) {
            recentRows = []
            return
        }
        if (!appRef || !appRef.listTransactions) {
            recentRows = []
            return
        }
        var rows = []
        try {
            rows = appRef.listTransactions({})
        } catch (e) {
            rows = []
        }
        if (!rows || rows.length === undefined) rows = []
        var clipped = []
        for (var i = 0; i < Math.min(rows.length, 12); i++) clipped.push(rows[i])
        recentRows = clipped
    }

    function refreshLookupData() {
        if (!root.backendReady()) {
            accountNames = []
            businessUnits = []
            payees = []
            categoryRows = []
            categoryDisplay = []
            parentNames = []
            clientNames = []
            matterNames = []
            matterDirectoryRows = []
            matterDisplayOptions = []
            recentRows = []
            fromAccountCombo.fullModel = []
            toAccountCombo.fullModel = []
            businessUnitCombo.fullModel = []
            payeeCombo.fullModel = []
            parentCombo.fullModel = []
            clientCombo.fullModel = []
            matterCombo.fullModel = []
            categoryCombo.fullModel = []
            return
        }
        function asTextList(values, key) {
            var out = []
            if (!values || values.length === undefined) return out
            for (var i = 0; i < values.length; i++) {
                var row = values[i]
                var value = key.length > 0 ? _clean(row[key]) : _clean(row)
                if (value.length > 0) out.push(value)
            }
            return out
        }
        try { accountNames = asTextList((appRef && appRef.listTransactionAccounts) ? appRef.listTransactionAccounts() : [], "accountName") } catch (e0) { accountNames = [] }
        try { businessUnits = asTextList((appRef && appRef.listTransactionBusinessUnits) ? appRef.listTransactionBusinessUnits() : [], "businessUnit") } catch (e1) { businessUnits = [] }
        try { payees = asTextList((appRef && appRef.listTransactionPayees) ? appRef.listTransactionPayees() : [], "payeeName") } catch (e2) { payees = [] }
        try { parentNames = asTextList((appRef && appRef.listParentNames) ? appRef.listParentNames() : [], "") } catch (e3) { parentNames = [] }
        try { clientNames = asTextList((appRef && appRef.listClientNames) ? appRef.listClientNames() : [], "") } catch (e4) { clientNames = [] }
        matterDirectoryRows = []
        matterDisplayOptions = []
        try {
            var directoryRows = (appRef && appRef.listMatterDirectory) ? appRef.listMatterDirectory() : []
            if (directoryRows && directoryRows.length !== undefined) {
                var seenMatterLabels = ({})
                for (var m = 0; m < directoryRows.length; m++) {
                    var row = directoryRows[m]
                    if (!row) continue
                    var matterName = _clean(row.matterName || row.displayName || "")
                    if (matterName.length <= 0) continue
                    matterDirectoryRows.push(row)
                    var label = _matterDisplayLabel(row)
                    var labelKey = label.toLowerCase()
                    if (label.length > 0 && !seenMatterLabels[labelKey]) {
                        seenMatterLabels[labelKey] = true
                        matterDisplayOptions.push(label)
                    }
                }
            }
        } catch (e5) {
            matterDirectoryRows = []
            matterDisplayOptions = []
        }
        if (matterDisplayOptions.length <= 0) {
            try { matterNames = asTextList((appRef && appRef.listMatterNames) ? appRef.listMatterNames() : [], "") } catch (e6) { matterNames = [] }
            matterDisplayOptions = matterNames
        }
        fromAccountCombo.fullModel = accountNames
        toAccountCombo.fullModel = accountNames
        businessUnitCombo.fullModel = businessUnits
        payeeCombo.fullModel = payees
        parentCombo.fullModel = parentNames
        clientCombo.fullModel = clientNames
        matterCombo.fullModel = matterDisplayOptions
        refreshCategoryLookups()
        loadRecentTransactions()
    }

    function resetDraft() {
        editingStoredTransaction = false
        _hydrating = true
        transactionIdInput.text = ""
        txnDateInput.text = _todayIso()
        classCombo.editText = "Family"
        typeCombo.editText = "Expense"
        businessUnitCombo.editText = ""
        fromAccountCombo.editText = ""
        toAccountCombo.editText = ""
        payeeCombo.editText = ""
        categoryCombo.editText = ""
        memberCombo.editText = "Joint"
        amountInput.text = ""
        taxAmountInput.text = "0.00"
        taxFlagCombo.editText = "None"
        hstExemptCombo.editText = "No"
        generalOfficeCombo.editText = "No"
        shadowCombo.editText = "No"
        parentCombo.editText = ""
        clientCombo.editText = ""
        matterCombo.editText = ""
        billClaimPctInput.text = "0.00"
        totalClaimAmountInput.text = "0.00"
        invoiceRefInput.text = ""
        statusCombo.editText = "Pending"
        currencyCombo.editText = "CAD"
        voidReasonInput.text = ""
        expenseDetailsInput.text = ""
        notesInput.text = ""
        _hydrating = false
        _applyRules()
        dirty = false
    }

    function snapshotState() {
        return {
            "payload": _buildPayload(),
            "categoryText": _clean(categoryCombo.editText),
            "saveMessage": saveMessage,
            "lastSavedTransactionId": lastSavedTransactionId,
            "dirty": dirty
        }
    }

    function applyState(state) {
        if (!state || !state.payload) return
        var payload = state.payload
        var categoryText = _clean(state.categoryText)
        if (!categoryText) {
            categoryText = _clean(payload.categoryCode)
            if (categoryText && _clean(payload.categoryName)) categoryText += " - "
            categoryText += _clean(payload.categoryName)
        }
        editingStoredTransaction = true
        _hydrating = true
        transactionIdInput.text = _clean(payload.transactionId)
        txnDateInput.text = _clean(payload.txnDate)
        classCombo.editText = _clean(payload.class)
        typeCombo.editText = _clean(payload.type)
        businessUnitCombo.editText = _clean(payload.businessUnit)
        fromAccountCombo.editText = _clean(payload.fromAccount)
        toAccountCombo.editText = _clean(payload.toAccount)
        payeeCombo.editText = _clean(payload.payee)
        categoryCombo.editText = categoryText
        memberCombo.editText = _clean(payload.member)
        amountInput.text = String(payload.amount || "")
        taxAmountInput.text = String(payload.taxAmount || "")
        taxFlagCombo.editText = _clean(payload.taxFlag)
        hstExemptCombo.editText = _yesNoToInt(payload.hstExempt) === 1 ? "Yes" : "No"
        generalOfficeCombo.editText = _yesNoToInt(payload.generalOfficeExpense) === 1 ? "Yes" : "No"
        shadowCombo.editText = _yesNoToInt(payload.shadow) === 1 ? "Yes" : "No"
        parentCombo.editText = _clean(payload.parent)
        clientCombo.editText = _clean(payload.client)
        matterCombo.editText = _matterDisplayTextForMatterName(payload.matter)
        billClaimPctInput.text = String(payload.billClaimPct || "0.00")
        totalClaimAmountInput.text = String(payload.totalClaimAmount || "0.00")
        invoiceRefInput.text = _clean(payload.invoiceRef)
        statusCombo.editText = _clean(payload.status)
        currencyCombo.editText = _clean(payload.currency)
        voidReasonInput.text = _clean(payload.voidReason)
        expenseDetailsInput.text = _clean(payload.expenseDetails)
        notesInput.text = _clean(payload.notes)
        saveMessage = _clean(state.saveMessage)
        lastSavedTransactionId = _clean(state.lastSavedTransactionId)
        _hydrating = false
        _applyRules()
        dirty = !!state.dirty
    }

    function runPrimaryAction() {
        if (saveInProgress) return
        var backend = (typeof docketApp !== "undefined") ? docketApp : null
        if (!backend || !backend.saveTransaction) {
            lastSaveOk = false
            saveMessage = "Transaction save backend is unavailable."
            saveFinished(false, saveMessage, "")
            return
        }
        saveInProgress = true
        try {
            backend.saveTransaction(_buildPayload())
        } catch (e) {
            saveInProgress = false
            lastSaveOk = false
            saveMessage = String(e)
            dirty = true
            saveFinished(false, saveMessage, "")
        }
        // Result arrives via Connections.onTransactionSaveFinished below
    }

    Connections {
        target: (typeof docketApp !== "undefined") ? docketApp : null
        function onTransactionSaveFinished(result) {
            if (!root.saveInProgress) return
            saveInProgress = false
            lastSaveOk = !!(result && result.ok)
            lastSavedTransactionId = String((result && result.transactionId !== undefined) ? result.transactionId : "")
            saveMessage = String((result && result.message !== undefined) ? result.message : "")
            if (saveMessage.length <= 0) saveMessage = lastSaveOk ? "Transaction saved." : "Transaction save failed."
            if (lastSaveOk) {
                transactionIdInput.text = lastSavedTransactionId
                dirty = false
                loadRecentTransactions()
            } else {
                dirty = true
            }
            saveFinished(lastSaveOk, saveMessage, lastSavedTransactionId)
        }
    }

    Loader {
        id: txnDateCalendarLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                metrics: root.metrics
                hostWindow: root.Window.window
                onDatePicked: function(d) {
                    txnDateInput.text = Qt.formatDate(d, "yyyy-MM-dd")
                    txnDateCalendarLoader.active = false
                    if (!root._hydrating) root.dirty = true
                }
            }
        }
    }

    Timer {
        id: lookupRefreshTimer
        interval: 140
        repeat: false
        onTriggered: {
            if (!root.canRunLookupRefresh()) return
            root.refreshLookupData()
        }
    }

    Timer {
        id: categoryLookupTimer
        interval: 120
        repeat: false
        onTriggered: {
            if (!root.canRunLookupRefresh()) return
            root.refreshCategoryLookups()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root._appBg

        ScrollView {
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth
            contentHeight: mainColumn.implicitHeight + 28
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                id: mainColumn
                width: parent.width - 28
                x: 14
                y: 14
                spacing: 14

            // Page title — was completely missing before
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "\uE912"
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 18
                    color: root._text
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Transaction Entry"
                        font.family: "Segoe UI"
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        color: root._text
                    }

                    Text {
                        text: "Enter and review financial transactions"
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                        color: root._mutedText
                    }
                }

                Item { Layout.fillWidth: true }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: root._border
            }

            GridLayout {
                id: transactionFormGrid
                Layout.fillWidth: true
                columns: root.formGridColumns(4, mainColumn.width)
                columnSpacing: 14
                rowSpacing: 14

                ModernTextField {
                    id: txnDateInput
                    t: root.t
                    metrics: root.metrics
                    label: "Txn Date *"
                    text: root._todayIso()
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onTextChanged: root._markDirty()
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        propagateComposedEvents: true
                        onDoubleClicked: function(mouse) {
                            var p = mapToGlobal(mouse.x, mouse.y)
                            root.openTxnDatePicker(p.x, p.y)
                        }
                        onPressed: function(mouse) { mouse.accepted = false }
                    }
                }
                ModernComboBox {
                    id: classCombo
                    t: root.t
                    metrics: root.metrics
                    label: "Class *"
                    fullModel: root.classOptions
                    editText: "Family"
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onEditTextChanged: { root._markDirty(); root._applyRules() }
                    onActivated: { root._markDirty(); root._applyRules() }
                }
                ModernComboBox {
                    id: typeCombo
                    t: root.t
                    metrics: root.metrics
                    label: "Type *"
                    fullModel: root.typeOptions
                    editText: "Expense"
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onEditTextChanged: { root._markDirty(); root._applyRules() }
                    onActivated: { root._markDirty(); root._applyRules() }
                }
                ModernTextField { id: transactionIdInput; t: root.t; metrics: root.metrics; label: "Transaction ID"; enabled: false; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx }

                ModernComboBox { id: businessUnitCombo; t: root.t; metrics: root.metrics; label: "Business Unit"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; enabled: root._isBusiness(); Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: memberCombo; t: root.t; metrics: root.metrics; label: "Member"; fullModel: root.memberOptions; editText: "Joint"; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox {
                    id: statusCombo
                    t: root.t
                    metrics: root.metrics
                    label: "Status"
                    fullModel: root.statusOptions
                    editText: "Pending"
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onEditTextChanged: { root._markDirty(); root._applyRules() }
                    onActivated: { root._markDirty(); root._applyRules() }
                }

                ModernComboBox { id: fromAccountCombo; t: root.t; metrics: root.metrics; label: "From Account *"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: toAccountCombo; t: root.t; metrics: root.metrics; label: root._needsToAccount() ? "To Account *" : "To Account"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; enabled: root._needsToAccount(); Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }

                ModernComboBox { id: payeeCombo; t: root.t; metrics: root.metrics; label: root._lower(typeCombo.editText) === "transfer" ? "Payee (Optional)" : "Payee *"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: categoryCombo; t: root.t; metrics: root.metrics; label: "Category *"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }

                ModernTextField { id: amountInput; t: root.t; metrics: root.metrics; label: "Amount *"; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onTextChanged: { root._markDirty(); root._recalcClaim() } }
                ModernTextField { id: taxAmountInput; t: root.t; metrics: root.metrics; label: "Tax Amount"; text: "0.00"; enabled: root._yesNoToInt(hstExemptCombo.editText) !== 1; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onTextChanged: { root._markDirty(); root._recalcClaim() } }
                ModernComboBox { id: taxFlagCombo; t: root.t; metrics: root.metrics; label: "Tax Flag"; fullModel: root.taxFlagOptions; editText: "None"; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox {
                    id: hstExemptCombo
                    t: root.t
                    metrics: root.metrics
                    label: "HST Exempt"
                    fullModel: root.yesNoOptions
                    editable: false
                    editText: "No"
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onEditTextChanged: { root._markDirty(); root._applyRules() }
                    onActivated: { root._markDirty(); root._applyRules() }
                }

                ModernComboBox {
                    id: generalOfficeCombo
                    t: root.t
                    metrics: root.metrics
                    label: "General Office Expense"
                    fullModel: root.yesNoOptions
                    editable: false
                    editText: "No"
                    visible: root._isExpense()
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldHeightPx
                    onEditTextChanged: { root._markDirty(); root._applyRules() }
                    onActivated: { root._markDirty(); root._applyRules() }
                }
                ModernComboBox { id: shadowCombo; t: root.t; metrics: root.metrics; label: "Shadow"; fullModel: root.yesNoOptions; editable: false; editText: "No"; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: currencyCombo; t: root.t; metrics: root.metrics; label: "Currency"; fullModel: root.currencyOptions; editText: "CAD"; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }

                ModernComboBox { id: parentCombo; t: root.t; metrics: root.metrics; label: "Parent"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; enabled: root._isExpense() && root._yesNoToInt(generalOfficeCombo.editText) !== 1; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: clientCombo; t: root.t; metrics: root.metrics; label: "Client"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; enabled: root._isExpense() && root._yesNoToInt(generalOfficeCombo.editText) !== 1; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernComboBox { id: matterCombo; t: root.t; metrics: root.metrics; label: "Matter"; fullModel: []; preserveUnknownEditTextOnModelChanged: root.editingStoredTransaction; enabled: root._isExpense() && root._yesNoToInt(generalOfficeCombo.editText) !== 1; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onEditTextChanged: root._markDirty(); onActivated: root._markDirty() }
                ModernTextField { id: billClaimPctInput; t: root.t; metrics: root.metrics; label: "Bill Claim %"; text: "0.00"; visible: root._isExpense(); enabled: root._isExpense() && root._yesNoToInt(generalOfficeCombo.editText) !== 1; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx; onTextChanged: { root._markDirty(); root._recalcClaim() } }
                ModernTextField { id: totalClaimAmountInput; t: root.t; metrics: root.metrics; label: "Total Claim Amount"; text: "0.00"; visible: root._isExpense(); enabled: false; Layout.fillWidth: true; Layout.preferredHeight: fieldHeightPx }

                ModernTextField { id: invoiceRefInput; t: root.t; metrics: root.metrics; label: "Invoice Ref"; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onTextChanged: root._markDirty() }
                ModernTextField { id: voidReasonInput; t: root.t; metrics: root.metrics; label: "Void Reason"; visible: root._lower(statusCombo.editText) === "void"; Layout.fillWidth: true; Layout.columnSpan: root.formGridSpan(transactionFormGrid.columns, 2); Layout.preferredHeight: fieldHeightPx; onTextChanged: root._markDirty() }
            }

            TextArea {
                id: expenseDetailsInput
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(64, Math.round(root.fieldHeightPx * 1.5))
                color: root._text
                font.family: "Segoe UI"
                wrapMode: Text.Wrap
                placeholderText: "Expense details"
                onTextChanged: root._markDirty()
                background: Rectangle { color: root.isProMode ? root._raisedPanel : SemanticTheme.alpha(root._panel, 0.72); radius: root.sectionRadiusPx; border.width: 1; border.color: root._border }
            }
            TextArea {
                id: notesInput
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(64, Math.round(root.fieldHeightPx * 1.5))
                color: root._text
                font.family: "Segoe UI"
                wrapMode: Text.Wrap
                placeholderText: "Notes"
                onTextChanged: root._markDirty()
                background: Rectangle { color: root.isProMode ? root._raisedPanel : SemanticTheme.alpha(root._panel, 0.72); radius: root.sectionRadiusPx; border.width: 1; border.color: root._border }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                PillButton { t: root.t; metrics: root.metrics; sfxBus: root.sfxBus; text: "Reset Draft"; primary: false; Layout.preferredWidth: 118; Layout.preferredHeight: fieldHeightPx; onClicked: root.resetDraft() }
                PillButton { t: root.t; metrics: root.metrics; sfxBus: root.sfxBus; text: "Refresh"; primary: false; Layout.preferredWidth: 108; Layout.preferredHeight: fieldHeightPx; onClicked: root.scheduleLookupRefresh() }
                Item { Layout.fillWidth: true }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: sectionRadiusPx
                color: root.isProMode ? root._raisedPanel : SemanticTheme.alpha(root._panel, 0.64)
                border.width: 1
                border.color: root._border
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 4

                    Text {
                        text: "Recent Transactions"
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: root._text
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: recentRows
                        spacing: 6
                        delegate: Rectangle {
                            required property var modelData
                            width: ListView.view.width
                            height: 42
                            radius: 4
                            color: rowMouse.containsMouse ? SemanticTheme.hoverOverlay(root.t, root.appStyle) : root.isProMode ? root._raisedPanel : SemanticTheme.overlayScrim(root.t, root.appStyle)
                            border.width: 1
                            border.color: rowMouse.containsMouse ? root._accent : root._border

                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8
                                Text { Layout.preferredWidth: 95; text: _clean(modelData.txnDate); font.family: "Segoe UI"; font.pixelSize: 12; color: root._mutedText; elide: Text.ElideRight }
                                Text { Layout.preferredWidth: 115; text: _clean(modelData.type); font.family: "Segoe UI"; font.pixelSize: 12; color: root._text; elide: Text.ElideRight }
                                Text { Layout.fillWidth: true; text: _clean(modelData.payee); font.family: "Segoe UI"; font.pixelSize: 12; color: root._text; elide: Text.ElideRight }
                                Text { Layout.preferredWidth: 84; horizontalAlignment: Text.AlignRight; text: Number(modelData.amount || 0).toFixed(2); font.family: "Segoe UI"; font.pixelSize: 12; color: root._accent }
                                Text { Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight; text: _clean(modelData.status); font.family: "Segoe UI"; font.pixelSize: 12; color: root._mutedText; elide: Text.ElideRight }
                                Rectangle {
                                    Layout.preferredWidth: 28
                                    Layout.preferredHeight: 28
                                    color: "transparent"
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uE74D"  // Trash icon
                                        font.family: "Segoe Fluent Icons"
                                        font.pixelSize: 16
                                        color: delMouse.containsMouse ? "#FF5252" : SemanticTheme.inkMuted(root.t, root.appStyle)
                                    }
                                    
                                    MouseArea {
                                        id: delMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: {
                                            let result = root.billingBackend.deleteLedgerEntry(modelData.transactionId)
                                            if (result.ok) {
                                                root.scheduleLookupRefresh()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                }
            }
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onBackendBootChanged() {
            if (!root.visible || !root.backendReady()) return
            root.scheduleLookupRefresh()
        }
        function onClientDataChanged() {
            if (!root.visible || !root.backendReady()) return
            root.scheduleLookupRefresh()
        }
    }

    onVisibleChanged: {
        if (!visible) return
        if (!root.backendReady()) return
        root.scheduleLookupRefresh()
    }

    Component.onCompleted: {
        resetDraft()
        if (root.canRunLookupRefresh()) {
            root.scheduleLookupRefresh()
        }
        dirty = false
    }
}
