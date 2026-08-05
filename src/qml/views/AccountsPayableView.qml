pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    readonly property real apTaxRate: 0.13
    property bool apTaxExempt: false
    property bool apTaxSyncing: false
    property var t
    property var metrics
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property bool isProMode: root.appStyle === "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }
    property var sfxBus
    // Prefer the established app surface (app.apController), with context alias fallback.
    property var apController: {
        if (root.appRef && root.appRef.apController)
            return root.appRef.apController
        if ((typeof app !== "undefined") && app && app.apController)
            return app.apController
        if ((typeof apBackendController !== "undefined") && apBackendController)
            return apBackendController
        return null
    }
    property var billRows: []
    property var selectedBill: null
    property bool entryPanelVisible: true
    property bool paymentMode: false
    property bool busy: false
    property string busyOperation: ""
    property int operationVersion: 0
    property string reloadSuccessMessage: ""
    property bool clearBillFormWhenLoaded: false
    property bool errorState: false
    property string statusMessage: ""
    property string editingBillId: ""
    property var editingBillDetails: null
    property var contextBill: null
    property string detailRequest: ""
    property var activePaymentChoices: []
    property var selectedReversalPayment: null
    readonly property real billColumnMargin: 12
    readonly property real billColumnSpacing: 8
    readonly property real billDueColumnWidth: 96
    readonly property real billStatusColumnWidth: 110
    readonly property real billBalanceColumnWidth: 110
    function billVendorColumnWidth(contentWidth) {
        return Math.max(
            180,
            contentWidth - (3 * billColumnSpacing)
            - billDueColumnWidth - billStatusColumnWidth - billBalanceColumnWidth
        )
    }
    property var expenseTreatments: [
        { "id": "office", "label": "General office expense" },
        { "id": "matter", "label": "Client matter expense" },
        { "id": "personal", "label": "Personal expense" }
    ]
    property var categoryOptions: []
    property var paymentAccountOptions: []
    property var matterOptions: []
    property string selectedTreatmentId: "office"
    property string selectedCategoryId: ""
    property string selectedPaymentAccountId: ""
    property string selectedMatterId: ""
    property string selectedMatterClientId: ""
    property string selectedMatterClientName: ""
    property string selectedMatterName: ""
    property var dateTargetField: null


    Timer {
        id: operationTimeout
        interval: 12000
        repeat: false
        property int operationVersion: -1
        onTriggered: {
            if (!root.busy || operationTimeout.operationVersion !== root.operationVersion)
                return
            operationTimeout.stop()
            root.busy = false
            root.busyOperation = ""
            root.errorState = true
            root.statusMessage = "The Accounts Payable operation took too long. Select Refresh to try again."
            console.warn("[AP] operation timeout", operationTimeout.operationVersion)
        }
    }

    function beginBusy(operationName) {
        root.operationVersion += 1
        root.busyOperation = String(operationName || "")
        root.busy = true
        operationTimeout.operationVersion = root.operationVersion
        operationTimeout.restart()
        console.log("[AP] operation started", root.operationVersion, root.busyOperation)
    }

    function finishBusy() {
        operationTimeout.stop()
        root.busy = false
        root.busyOperation = ""
        console.log("[AP] busy state finished", root.operationVersion)
    }

    function firstValue(row, keys, fallbackValue) {
        if (!row || typeof row !== "object")
            return fallbackValue || ""
        for (var i = 0; i < keys.length; i++) {
            var value = row[keys[i]]
            if (value !== undefined && value !== null && String(value).trim().length > 0)
                return String(value).trim()
        }
        return fallbackValue || ""
    }

    function optionByLabel(options, labelText) {
        var target = String(labelText || "").trim().toLowerCase()
        for (var i = 0; i < options.length; i++) {
            if (String(options[i].label || "").trim().toLowerCase() === target)
                return options[i]
        }
        return null
    }

    function normalizeMatterRows(rows) {
        var output = []
        var source = rows || []
        for (var i = 0; i < source.length; i++) {
            var row = source[i] || {}
            var matterId = root.firstValue(row, ["MatterID", "matterId", "matter_id", "ID", "id"], "")
            var matterName = root.firstValue(row, ["MatterName", "matterName", "matter_name", "Name", "name", "Description", "description"], matterId)
            var clientId = root.firstValue(row, ["ClientID", "clientId", "client_id", "ClientKey", "clientKey"], "")
            var clientName = root.firstValue(row, ["ClientName", "clientName", "client_name", "Client", "client"], "")
            if (!matterId && !matterName)
                continue
            var label = clientName ? clientName + " | " + matterName : matterName
            if (matterId && label.indexOf(matterId) < 0)
                label += " • " + matterId
            output.push({
                "id": matterId || matterName,
                "label": label,
                "matterName": matterName,
                "clientId": clientId,
                "clientName": clientName,
                "search": (clientName + " " + matterName + " " + matterId).toLowerCase()
            })
        }
        output.sort(function(a, b) { return String(a.label).localeCompare(String(b.label)) })
        return output
    }

    function normalizeCategoryRows(rows) {
        var output = []
        var source = rows || []
        for (var i = 0; i < source.length; i++) {
            var row = source[i] || {}
            var id = root.firstValue(row, ["CategoryCode", "categoryCode", "Code", "code", "ID", "id"], "")
            var name = root.firstValue(row, ["CategoryName", "categoryName", "Name", "name", "Description", "description"], id)
            if (!id && !name)
                continue
            var label = id && name !== id ? name + " • " + id : name
            output.push({ "id": id || name, "label": label, "name": name, "search": (name + " " + id).toLowerCase() })
        }
        output.sort(function(a, b) { return String(a.label).localeCompare(String(b.label)) })
        return output
    }

    function normalizeAccountRows(rows) {
        var output = []
        var source = rows || []
        for (var i = 0; i < source.length; i++) {
            var row = source[i] || {}
            var id = root.firstValue(row, ["AccountID", "accountId", "AccountCode", "accountCode", "Code", "code", "ID", "id"], "")
            var name = root.firstValue(row, ["AccountName", "accountName", "DisplayName", "displayName", "Name", "name"], id)
            if (!id && !name)
                continue
            var label = id && name !== id ? name + " • " + id : name
            output.push({ "id": id || name, "label": label, "name": name, "search": (name + " " + id).toLowerCase() })
        }
        output.sort(function(a, b) { return String(a.label).localeCompare(String(b.label)) })
        return output
    }

    function loadSetupLists() {
        if (!root.appRef)
            return
        try {
            if (root.appRef.listActiveMatterDirectory)
                root.matterOptions = root.normalizeMatterRows(root.appRef.listActiveMatterDirectory())
        } catch (matterError) {
            console.warn("AP matter lookup failed", matterError)
        }
        try {
            if (root.appRef.listTransactionCategories)
                root.categoryOptions = root.normalizeCategoryRows(root.appRef.listTransactionCategories("Expense", "", false))
        } catch (categoryError) {
            console.warn("AP category lookup failed", categoryError)
        }
        try {
            if (root.appRef.listTransactionAccounts)
                root.paymentAccountOptions = root.normalizeAccountRows(root.appRef.listTransactionAccounts())
        } catch (accountError) {
            console.warn("AP account lookup failed", accountError)
        }
    }

    function clearMatterSelection() {
        root.selectedMatterId = ""
        root.selectedMatterName = ""
        root.selectedMatterClientId = ""
        root.selectedMatterClientName = ""
        matterField.clearSelection()
    }


    function parseIsoDateOrToday(value) {
        var textValue = String(value || "").trim()
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(textValue)
        if (match) {
            var candidate = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
            if (!isNaN(candidate.getTime())) return candidate
        }
        return new Date()
    }
    function openDatePicker(field) {
        root.dateTargetField = field
        apDateCalendarLoader.active = true
        Qt.callLater(function() {
            var calendar = apDateCalendarLoader.item
            if (!calendar || !field) return
            calendar.selectedDate = root.parseIsoDateOrToday(field.text || "")
            calendar.pendingDate = calendar.selectedDate

            // The initiating field is the sole monitor-selection source.
            // Its global centre is captured before JellyCalendar receives focus.
            var anchorPoint = field.mapToGlobal(
                Qt.point(Math.round(field.width / 2), Math.round(field.height / 2))
            )
            if (typeof calendar.openAt === "function")
                calendar.openAt(anchorPoint.x, anchorPoint.y)
            else if (typeof calendar.openCenteredInHost === "function")
                calendar.openCenteredInHost()
            else
                calendar.visible = true
        })
    }

    Loader {
        id: apDateCalendarLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                metrics: root.metrics
                hostWindow: root.Window.window
                onDatePicked: function(value) {
                    if (root.dateTargetField)
                        root.dateTargetField.text = Qt.formatDate(value, "yyyy-MM-dd")
                    root.dateTargetField = null
                    apDateCalendarLoader.active = false
                }
            }
        }
    }



    function todayText() {
        var d = new Date()
        return d.getFullYear() + "-"
            + String(d.getMonth() + 1).padStart(2, "0") + "-"
            + String(d.getDate()).padStart(2, "0")
    }

    function generatedId(prefix) {
        return prefix + "-" + Date.now().toString()
    }

    function moneyText(value) {
        var number = Number(value || 0)
        return isFinite(number) ? "$" + number.toFixed(2) : "$0.00"
    }

    function loadBills(reason, successMessage, clearFormAfterLoad) {
        if (!root.apController || !root.apController.loadAPInvoices) {
            root.finishBusy()
            root.errorState = true
            root.statusMessage = "Accounts Payable service is unavailable."
            return
        }
        root.reloadSuccessMessage = String(successMessage || "")
        root.clearBillFormWhenLoaded = clearFormAfterLoad === true
        root.beginBusy(String(reason || "load"))
        console.log("[AP] reload requested", root.operationVersion, root.busyOperation)
        root.apController.loadAPInvoices()
    }

    function validateBill() {
        if (!vendorField.text.trim()) {
            root.statusMessage = "Enter a vendor or supplier."
            return false
        }
        if (!invoiceNumberField.text.trim()) {
            root.statusMessage = "Enter the supplier invoice number."
            return false
        }
        if (root.apNumber(subtotalField.text) <= 0) {
            root.statusMessage = "Enter a positive subtotal."
            return false
        }
        if (!root.selectedCategoryId) {
            root.statusMessage = "Select an expense category from the configured list."
            return false
        }
        if (root.selectedTreatmentId === "matter" && !root.selectedMatterId) {
            root.statusMessage = "Select a client matter for a client matter expense."
            return false
        }
        if (root.selectedTreatmentId !== "matter")
            root.clearMatterSelection()
        return true
    }

    function apNumber(textValue) {
        var number = Number(String(textValue || "").replace(/,/g, ""))
        return isFinite(number) ? number : 0
    }

    function apMoney(value) {
        return Math.max(0, Number(value || 0)).toFixed(2)
    }

    function syncAPFromSubtotal() {
        if (root.apTaxSyncing)
            return
        root.apTaxSyncing = true
        var subtotal = root.apNumber(subtotalField.text)
        var tax = root.apTaxExempt ? 0 : subtotal * root.apTaxRate
        taxField.text = root.apMoney(tax)
        totalField.text = root.apMoney(subtotal + tax)
        root.apTaxSyncing = false
    }

    function syncAPFromTax() {
        if (root.apTaxSyncing)
            return
        root.apTaxSyncing = true
        var subtotal = root.apNumber(subtotalField.text)
        var tax = root.apTaxExempt ? 0 : root.apNumber(taxField.text)
        taxField.text = root.apMoney(tax)
        totalField.text = root.apMoney(subtotal + tax)
        root.apTaxSyncing = false
    }

    function syncAPFromTotal() {
        if (root.apTaxSyncing)
            return
        root.apTaxSyncing = true
        var total = root.apNumber(totalField.text)
        var subtotal = root.apTaxExempt ? total : total / (1 + root.apTaxRate)
        var tax = root.apTaxExempt ? 0 : total - subtotal
        subtotalField.text = root.apMoney(subtotal)
        taxField.text = root.apMoney(tax)
        totalField.text = root.apMoney(total)
        root.apTaxSyncing = false
    }

    function applyTaxExempt() {
        root.apTaxSyncing = true
        var subtotal = root.apNumber(subtotalField.text)
        var tax = root.apTaxExempt ? 0 : subtotal * root.apTaxRate
        taxField.text = root.apMoney(tax)
        totalField.text = root.apMoney(subtotal + tax)
        root.apTaxSyncing = false
    }

    function billPayload() {
        return {
            "APBillID": root.editingBillId || root.generatedId("APB"),
            "Vendor": vendorField.text.trim(),
            "VendorInvoiceNumber": invoiceNumberField.text.trim(),
            "InvoiceDate": invoiceDateField.text.trim(),
            "DueDate": dueDateField.text.trim(),
            "Subtotal": root.apNumber(subtotalField.text),
            "TaxAmount": root.apNumber(taxField.text),
            "Total": root.apNumber(totalField.text),
            "TaxExempt": root.apTaxExempt,
            "Currency": currencyField.currentText,
            "SourceAccount": root.selectedPaymentAccountId,
            "CategoryCode": root.selectedCategoryId,
            "CategoryName": categoryField.selectedLabel,
            "Matter": root.selectedMatterId,
            "MatterID": root.selectedMatterId,
            "MatterName": root.selectedMatterName,
            "ClientID": root.selectedMatterClientId,
            "ClientName": root.selectedMatterClientName,
            "ExpenseTreatment": root.selectedTreatmentId,
            "Notes": notesField.text.trim(),
            "Class": "Business"
        }
    }

    function saveBill() {
        if (!root.validateBill()) {
            root.errorState = true
            return
        }
        root.errorState = false
        var update = root.editingBillId.length > 0
        root.beginBusy(update ? "update_bill" : "save_bill")
        root.statusMessage = update ? "Saving bill changes..." : "Saving supplier bill..."
        console.log("[AP] save requested", root.operationVersion, update ? "update" : "create")
        if (update)
            root.apController.updateAPInvoice(root.billPayload())
        else
            root.apController.saveAPInvoice(root.billPayload())
    }

    function savePayment() {
        if (!root.selectedBill) {
            root.errorState = true
            root.statusMessage = "Select a bill before recording a payment."
            return
        }
        if (Number(paymentAmountField.text || 0) <= 0) {
            root.errorState = true
            root.statusMessage = "Enter a positive payment amount."
            return
        }
        if (!root.selectedPaymentAccountId) {
            root.errorState = true
            root.statusMessage = "Select the payment account."
            return
        }
        root.errorState = false
        root.beginBusy("record_payment")
        root.statusMessage = "Recording payment..."
        root.apController.recordAPPayment({
            "APPaymentID": root.generatedId("APP"),
            "APBillID": String(root.selectedBill.APBillID || ""),
            "PaymentDate": paymentDateField.text.trim(),
            "Amount": Number(paymentAmountField.text || 0),
            "FromAccount": root.selectedPaymentAccountId,
            "Method": paymentMethodField.currentText,
            "Reference": paymentReferenceField.text.trim(),
            "Notes": paymentNotesField.text.trim()
        })
    }

    function selectBill(row) {
        root.selectedBill = row
        paymentAmountField.text = Number(row.Balance || 0).toFixed(2)
        root.statusMessage = ""
        root.errorState = false
    }

    function clearBillForm() {
        root.editingBillId = ""
        root.editingBillDetails = null
        root.apTaxExempt = false
        vendorField.text = ""
        invoiceNumberField.text = ""
        invoiceDateField.text = root.todayText()
        dueDateField.text = ""
        subtotalField.text = ""
        taxField.text = "0.00"
        totalField.text = ""
        currencyField.currentIndex = 0
        root.selectedTreatmentId = "office"
        treatmentField.selectedId = "office"
        treatmentField.selectedLabel = "General office expense"
        root.selectedCategoryId = ""
        categoryField.clearSelection()
        root.selectedPaymentAccountId = ""
        accountField.clearSelection()
        paymentAccountField.clearSelection()
        root.clearMatterSelection()
        notesField.text = ""
    }

    function cancelEdit() {
        root.clearBillForm()
        root.statusMessage = "Edit cancelled."
        root.errorState = false
    }

    function canDeleteBill(row) {
        if (!row)
            return false
        var status = String(row.Status || "").toLowerCase()
        return root.apNumber(row.AmountPaid) === 0
            && (status === "unpaid" || status === "draft")
    }

    function requestBillDetails(bill, request) {
        if (!bill || !root.apController || !root.apController.loadAPBillDetails)
            return
        root.detailRequest = request
        root.beginBusy(request === "edit" ? "load_bill_for_edit" : "load_active_payments")
        root.apController.loadAPBillDetails(String(bill.APBillID || ""))
    }

    function beginEditBill(bill) {
        root.contextBill = bill
        root.selectBill(bill)
        root.requestBillDetails(bill, "edit")
    }

    function populateEditForm(details) {
        var bill = details.bill || {}
        var transaction = details.transaction || {}
        root.editingBillId = String(bill.APBillID || "")
        root.editingBillDetails = details
        vendorField.text = String(bill.Vendor || "")
        invoiceNumberField.text = String(bill.VendorInvoiceNumber || "")
        invoiceDateField.text = String(bill.InvoiceDate || root.todayText())
        dueDateField.text = String(bill.DueDate || "")
        subtotalField.text = root.apMoney(bill.Subtotal)
        taxField.text = root.apMoney(bill.TaxAmount)
        totalField.text = root.apMoney(bill.Total)
        root.apTaxExempt = Boolean(transaction.hstExempt || transaction.HSTExempt)
        var currency = String(bill.Currency || transaction.currency || "CAD")
        currencyField.currentIndex = currencyField.find(currency)
        if (currencyField.currentIndex < 0)
            currencyField.currentIndex = 0
        root.selectedCategoryId = String(transaction.categoryCode || transaction.CategoryCode || "")
        categoryField.selectedId = root.selectedCategoryId
        categoryField.selectedLabel = String(transaction.categoryName || transaction.CategoryName || root.selectedCategoryId)
        root.selectedPaymentAccountId = String(transaction.fromAccount || transaction.FromAccount || "")
        accountField.selectedId = root.selectedPaymentAccountId
        accountField.selectedLabel = String(transaction.fromAccount || transaction.FromAccount || "")
        root.selectedMatterId = String(transaction.matter || transaction.Matter || "")
        root.selectedMatterName = root.selectedMatterId
        root.selectedMatterClientId = String(transaction.client || transaction.Client || "")
        root.selectedMatterClientName = root.selectedMatterClientId
        root.selectedTreatmentId = root.selectedMatterId ? "matter" : "office"
        treatmentField.selectedId = root.selectedTreatmentId
        treatmentField.selectedLabel = root.selectedTreatmentId === "matter" ? "Client matter expense" : "General office expense"
        matterField.selectedId = root.selectedMatterId
        matterField.selectedLabel = root.selectedMatterName
        notesField.text = String(bill.Notes || transaction.notes || transaction.Notes || "")
        root.entryPanelVisible = true
        root.paymentMode = false
        root.statusMessage = "Editing supplier bill."
        root.errorState = false
    }

    function requestDeleteBill(bill) {
        root.contextBill = bill
        deleteBillDialog.open()
    }

    function deleteContextBill() {
        if (!root.contextBill || !root.apController || !root.apController.deleteAPInvoice)
            return
        root.errorState = false
        root.beginBusy("delete_bill")
        root.statusMessage = "Deleting supplier bill..."
        root.apController.deleteAPInvoice(String(root.contextBill.APBillID || ""))
    }

    function openPaymentReversal(bill) {
        root.contextBill = bill
        root.requestBillDetails(bill, "reverse_payment")
    }

    function reverseSelectedPayment() {
        if (!root.selectedReversalPayment || !reversalReasonField.text.trim()) {
            root.errorState = true
            root.statusMessage = "Select an active payment and enter a reversal reason."
            return
        }
        root.errorState = false
        root.beginBusy("reverse_payment")
        root.statusMessage = "Reversing payment..."
        root.apController.reverseAPPayment(
            String(root.selectedReversalPayment.APPaymentID || ""),
            root.generatedId("APP-REV"),
            reversalReasonField.text.trim()
        )
    }

    Component.onCompleted: {
        invoiceDateField.text = root.todayText()
        paymentDateField.text = root.todayText()
        root.loadSetupLists()
        root.loadBills()
    }

    Connections {
        target: root.apController
        ignoreUnknownSignals: true

        function onApLoaded(rows) {
            var clearForm = root.clearBillFormWhenLoaded
            root.clearBillFormWhenLoaded = false
            root.billRows = rows || []
            root.finishBusy()
            if (clearForm) {
                try {
                    root.clearBillForm()
                } catch (error) {
                    console.warn("[AP] saved rows reloaded but the form could not be cleared", error)
                }
            }
            if (root.reloadSuccessMessage.length > 0) {
                root.statusMessage = root.reloadSuccessMessage
                root.reloadSuccessMessage = ""
                root.errorState = false
            }
            console.log("[AP] reload completed", root.operationVersion, "rows=", root.billRows.length,
                        "error=", root.errorState, "status=", root.statusMessage)
        }

        function onApSaveFinished(result) {
            if (result && result.ok) {
                root.errorState = false
                console.log("[AP] save backend completed", root.operationVersion, result.operation || "save")
                root.loadBills("save_reload", result.message || "Supplier bill saved.", true)
            } else {
                root.finishBusy()
                root.errorState = true
                root.statusMessage = (result && (result.message || result.error))
                    || "The supplier bill could not be saved."
            }
        }

        function onApPaymentFinished(result) {
            if (result && result.APPaymentID) {
                root.errorState = false
                root.loadBills("payment_reload", "Payment recorded.")
            } else {
                root.finishBusy()
                root.errorState = true
                root.statusMessage = (result && (result.message || result.error))
                    || "The payment could not be recorded."
            }
        }

        function onApBillDetailsLoaded(details) {
            root.finishBusy()
            if (!details || !details.ok) {
                root.errorState = true
                root.statusMessage = (details && (details.message || details.error))
                    || "The supplier bill details could not be loaded."
                return
            }
            if (root.detailRequest === "edit") {
                root.populateEditForm(details)
            } else if (root.detailRequest === "reverse_payment") {
                root.activePaymentChoices = details.activePayments || []
                root.selectedReversalPayment = root.activePaymentChoices.length > 0
                    ? root.activePaymentChoices[0] : null
                reversalReasonField.text = ""
                if (root.activePaymentChoices.length === 0) {
                    root.statusMessage = "There are no active payments to reverse."
                    root.errorState = false
                } else {
                    reversalDialog.open()
                }
            }
            root.detailRequest = ""
        }

        function onApDeleteFinished(result) {
            if (result && result.ok) {
                root.selectedBill = null
                root.contextBill = null
                root.loadBills("delete_reload", result.message || "Supplier bill deleted.", true)
            } else {
                root.finishBusy()
                root.errorState = true
                root.statusMessage = (result && (result.message || result.error))
                    || "The supplier bill could not be deleted."
            }
        }

        function onApPaymentReversed(result) {
            if (result && result.APPaymentID) {
                reversalDialog.close()
                root.selectedReversalPayment = null
                root.loadBills("reversal_reload", "Payment reversed. The bill balance was restored.")
            } else {
                root.finishBusy()
                root.errorState = true
                root.statusMessage = (result && (result.message || result.error))
                    || "The payment could not be reversed."
            }
        }

        function onError(message) {
            root.finishBusy()
            root.errorState = true
            root.statusMessage = String(message || "Accounts Payable operation failed.")
            root.reloadSuccessMessage = ""
            console.warn("[AP] backend error", root.statusMessage)
        }
    }

    component FormLabel: Label {
        color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"
        font.pixelSize: 12
        font.weight: Font.Medium
    }

    component FormField: TextField {
        Layout.fillWidth: true
        implicitHeight: 32
        color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
        selectedTextColor: root.isProMode ? SemanticTheme.readableInk(SemanticTheme.accentPrimary(root.t, root.appStyle)) : "#FFFFFF"
        selectionColor: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F6FA8"
        placeholderTextColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#8291A3"
        leftPadding: 10
        rightPadding: 10
        background: Rectangle {
            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
            radius: visualRules.isPro ? visualRules.radiusControl : 6
            border.width: parent.activeFocus ? 2 : 1
            border.color: parent.activeFocus ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F6FA8") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#C7D3DF")
        }
    }


    component SearchSelector: Item {
        id: selector
        property var allOptions: []
        property var filteredOptions: []
        property string selectedId: ""
        property string selectedLabel: ""
        property bool allowBlank: true
        property string blankLabel: "Clear selection"
        property string searchHint: "Select or type to search"
        property string dialogTitle: "Select an option"
        signal optionChosen(var option)

        Layout.fillWidth: true
        implicitHeight: 32

        function hostWindow() {
            return root.Window.window
        }

        function rebuild(termText) {
            var term = String(termText || "").trim().toLowerCase()
            var rows = []
            for (var i = 0; i < allOptions.length; i++) {
                var option = allOptions[i] || {}
                var haystack = String(option.search || option.label || "").toLowerCase()
                if (!term || haystack.indexOf(term) >= 0)
                    rows.push(option)
            }
            filteredOptions = rows
        }

        function selectorGeometryAudit(tag) {
            var host = hostWindow()
            var globalCenter = null
            try {
                if (host && host.contentItem && host.contentItem.mapToGlobal) {
                    globalCenter = host.contentItem.mapToGlobal(Qt.point(Math.round(host.contentItem.width / 2), Math.round(host.contentItem.height / 2)))
                }
            } catch (auditError) {
                globalCenter = null
            }
            var hostScreen = host && host.screen ? host.screen : null
            var popupScreen = selectorWindow.screen ? selectorWindow.screen : null
            console.log(
                "[APGEOM][SELECTOR]", tag, selector.dialogTitle,
                "host=", host ? [host.x, host.y, host.width, host.height].join(",") : "null",
                "content=", host && host.contentItem ? [host.contentItem.width, host.contentItem.height].join(",") : "null",
                "globalCenter=", globalCenter ? [globalCenter.x, globalCenter.y].join(",") : "null",
                "hostScreen=", hostScreen ? [hostScreen.name, hostScreen.geometry.x, hostScreen.geometry.y, hostScreen.geometry.width, hostScreen.geometry.height, hostScreen.devicePixelRatio].join(",") : "null",
                "popupScreen=", popupScreen ? [popupScreen.name, popupScreen.geometry.x, popupScreen.geometry.y, popupScreen.geometry.width, popupScreen.geometry.height, popupScreen.devicePixelRatio].join(",") : "null",
                "popup=", [selectorWindow.x, selectorWindow.y, selectorWindow.width, selectorWindow.height, selectorWindow.visible].join(","),
                "transientMatches=", host ? (selectorWindow.transientParent === host) : false
            )
        }

        function recenterWindow() {
            var realHost = hostWindow()
            if (!realHost) return
            selectorWindow.transientParent = realHost
            if (realHost.screen) selectorWindow.screen = realHost.screen
            var host = {
                x: selectorWindow.screen ? selectorWindow.screen.virtualX : 0,
                y: selectorWindow.screen ? selectorWindow.screen.virtualY : 0,
                width: selectorWindow.screen ? selectorWindow.screen.width : 1920,
                height: selectorWindow.screen ? selectorWindow.screen.height : 1080
            }
            selectorWindow.x = Math.round(host.x + ((host.width - selectorWindow.width) / 2))
            selectorWindow.y = Math.round(host.y + ((host.height - selectorWindow.height) / 2))
        }

        function openSelector() {
            searchBox.text = ""
            rebuild("")
            var realHost = hostWindow()
            var count = Math.max(1, filteredOptions.length + (allowBlank ? 1 : 0))
            selectorWindow.width = Math.min(720, Math.max(520, realHost ? realHost.width * 0.50 : 620))
            selectorWindow.height = Math.min(560, Math.max(250, 126 + Math.min(count, 8) * 44))
            recenterWindow()
            selectorWindow.show()
            selectorWindow.requestActivate()
            Qt.callLater(function() {
                recenterWindow()
                selectorWindow.requestActivate()
                selectorWindow.raise()
                searchBox.forceActiveFocus()
                selector.selectorGeometryAudit("after-position")
                Qt.callLater(function() { selector.selectorGeometryAudit("settled") })
            })
        }

        function clearSelection() {
            selectedId = ""
            selectedLabel = ""
            displayField.text = ""
            rebuild("")
        }

        function choose(option) {
            selectedId = String(option.id || "")
            selectedLabel = String(option.label || "")
            displayField.text = selectedLabel
            optionChosen(option)
            selectorWindow.hide()
        }

        onSelectedLabelChanged: displayField.text = selectedLabel
        Component.onCompleted: {
            displayField.text = selectedLabel
            rebuild("")
        }

        TextField {
            id: displayField
            anchors.fill: parent
            rightPadding: 10
            readOnly: true
            placeholderText: selector.searchHint
            color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
            placeholderTextColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#8291A3"
            background: Rectangle {
                radius: visualRules.isPro ? visualRules.radiusControl : 5
                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
                border.width: displayField.activeFocus ? 2 : 1
                border.color: displayField.activeFocus ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F70C0") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9CDB")
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: selector.openSelector()
            }
        }



        Window {
            id: selectorWindow
            visible: false
            title: selector.dialogTitle
            flags: Qt.Dialog | Qt.FramelessWindowHint
            modality: Qt.ApplicationModal
            color: "transparent"

            Shortcut {
                sequences: ["Esc"]
                context: Qt.ApplicationShortcut
                enabled: selectorWindow.visible
                onActivated: selectorWindow.hide()
            }



            Rectangle {
                id: popupRect
                anchors.fill: parent
                color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"
                radius: visualRules.isPro ? visualRules.radiusPopup : 10
                border.width: 1
                border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
                focus: true
                Keys.onShortcutOverride: function(event) {
                    if (event.key === Qt.Key_Escape) {
                        event.accepted = true
                        selectorWindow.hide()
                    }
                }
                Keys.onEscapePressed: selectorWindow.hide()

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "#F4F7FB"
                        radius: visualRules.isPro ? visualRules.radiusPopup : 10

                        Label {
                            anchors.left: parent.left
                            anchors.leftMargin: 18
                            anchors.verticalCenter: parent.verticalCenter
                            text: selector.dialogTitle
                            color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }

                        Row {
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            Button {
                                id: clearSelectionButton
                                visible: selector.allowBlank
                                text: "Clear"
                                flat: true
                                implicitWidth: 64
                                onClicked: {
                                    selector.clearSelection()
                                    selectorWindow.hide()
                                }
                                background: Rectangle {
                                    color: clearSelectionButton.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.12) : "#DCEBFA") : (root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "#FFFFFF")
                                    border.width: 1
                                    border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
                                    radius: visualRules.isPro ? visualRules.radiusControl : 5
                                }
                                contentItem: Text {
                                    text: clearSelectionButton.text
                                    color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            Button {
                                id: closeSelectorButton
                                text: "Close"
                                flat: true
                                implicitWidth: 64
                                onClicked: selectorWindow.hide()
                                background: Rectangle {
                                    color: closeSelectorButton.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.inkPrimary(root.t, root.appStyle), 0.08) : "#EEF5FC") : "transparent"
                                    radius: visualRules.isPro ? visualRules.radiusControl : 5
                                }
                                contentItem: Text {
                                    text: closeSelectorButton.text
                                    color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.margins: 16
                        spacing: 10

                        TextField {
                            id: searchBox
                            Layout.fillWidth: true
                            implicitHeight: 38
                            placeholderText: selector.searchHint
                            color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                            placeholderTextColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#8291A3"
                            background: Rectangle {
                                radius: visualRules.isPro ? visualRules.radiusControl : 6
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
                                border.width: searchBox.activeFocus ? 2 : 1
                                border.color: searchBox.activeFocus ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F70C0") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB")
                            }
                            onTextEdited: selector.rebuild(text)
                            Keys.onDownPressed: {
                                resultList.forceActiveFocus()
                                if (resultList.count > 0) resultList.currentIndex = 0
                            }
                        }

                        Label {
                            visible: selector.filteredOptions.length === 0
                            Layout.fillWidth: true
                            text: "No matching options"
                            color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#607287"
                            horizontalAlignment: Text.AlignHCenter
                            padding: 18
                        }

                        ListView {
                            id: resultList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: selector.filteredOptions
                            currentIndex: -1
                            spacing: 2

                            delegate: ItemDelegate {
                                required property var modelData
                                width: resultList.width
                                implicitHeight: 42
                                text: String(modelData.label || "")
                                highlighted: ListView.isCurrentItem
                                onClicked: selector.choose(modelData)
                                ToolTip.visible: hovered && contentText.truncated
                                ToolTip.text: text
                                background: Rectangle {
                                    color: parent.highlighted ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#DCEBFA") : (parent.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.08) : "#EEF5FC") : (root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"))
                                    radius: visualRules.isPro ? visualRules.radiusControl : 5
                                }
                                contentItem: Text {
                                    id: contentText
                                    text: parent.text
                                    color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                    leftPadding: 10
                                    rightPadding: 10
                                }
                            }
                            Keys.onReturnPressed: {
                                if (currentIndex >= 0) selector.choose(selector.filteredOptions[currentIndex])
                            }
                            Keys.onEnterPressed: {
                                if (currentIndex >= 0) selector.choose(selector.filteredOptions[currentIndex])
                            }
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }
            }
        }
    }

    component LightComboBox: ComboBox {
        id: lightCombo
        Layout.fillWidth: true
        implicitHeight: 32
        leftPadding: 10
        rightPadding: 30
        font.pixelSize: 12

        contentItem: Text {
            text: lightCombo.displayText
            color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font: lightCombo.font
        }
        background: Rectangle {
            radius: visualRules.isPro ? visualRules.radiusControl : 5
            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
            border.width: lightCombo.activeFocus ? 2 : 1
            border.color: lightCombo.activeFocus ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F70C0") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB")
        }
        popup: Popup {
            onOpened: console.log("[APCOMBO] opened", lightCombo.objectName, "count=", lightCombo.count, "model=", JSON.stringify(lightCombo.model))
            y: lightCombo.height + 2
            width: lightCombo.width
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 320)
            padding: 6
            background: Rectangle {
                color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"
                radius: visualRules.isPro ? visualRules.radiusPopup : 6
                border.width: 1
                border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
            }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: lightCombo.popup.visible ? lightCombo.delegateModel : null
                currentIndex: lightCombo.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
        }
        delegate: ItemDelegate {
            id: comboDelegate
            required property int index
            required property var modelData
            width: lightCombo.width - 12
            implicitHeight: 34
            text: String(modelData)
            highlighted: lightCombo.highlightedIndex === index
            background: Rectangle {
                color: comboDelegate.highlighted ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#DCEBFA") : (comboDelegate.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.08) : "#EEF5FC") : (root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"))
            }
            contentItem: Text {
                text: comboDelegate.text
                color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                verticalAlignment: Text.AlignVCenter
                leftPadding: 8
            }
        }
    }

    component ToolbarButton: Button {
        implicitHeight: 36
        leftPadding: 14
        rightPadding: 14
        contentItem: Label {
            text: parent.text
            color: parent.enabled ? (root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#20354D") : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#94A0AD")
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 12
            font.weight: Font.Medium
        }
        background: Rectangle {
            color: parent.down ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.20) : "#DCE7F1") : (parent.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.10) : "#EEF4F9") : (root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"))
            radius: visualRules.isPro ? visualRules.radiusControl : 6
            border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#BFCDDA"
        }
    }

    Menu {
        id: billContextMenu
        width: 196
        modal: false
        property var bill: root.contextBill

        background: Rectangle {
            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"
            radius: visualRules.isPro ? visualRules.radiusPopup : 6
            border.width: 1
            border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
        }

        MenuItem {
            id: editBillMenuItem
            text: "Edit Bill"
            enabled: !!billContextMenu.bill
            onTriggered: root.beginEditBill(billContextMenu.bill)
            contentItem: Label {
                text: editBillMenuItem.text
                color: editBillMenuItem.enabled ? (root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40") : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#94A0AD")
                verticalAlignment: Text.AlignVCenter
                leftPadding: 12
            }
            background: Rectangle {
                color: editBillMenuItem.highlighted ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#DCEBFA") : "transparent"
                radius: visualRules.isPro ? visualRules.radiusControl : 4
            }
        }

        MenuItem {
            id: reversePaymentMenuItem
            text: "View / Reverse Payments"
            enabled: !!billContextMenu.bill && root.apNumber(billContextMenu.bill.AmountPaid) > 0
            onTriggered: root.openPaymentReversal(billContextMenu.bill)
            contentItem: Label {
                text: reversePaymentMenuItem.text
                color: reversePaymentMenuItem.enabled ? (root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40") : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#94A0AD")
                verticalAlignment: Text.AlignVCenter
                leftPadding: 12
            }
            background: Rectangle {
                color: reversePaymentMenuItem.highlighted ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#DCEBFA") : "transparent"
                radius: visualRules.isPro ? visualRules.radiusControl : 4
            }
        }

        MenuSeparator { }

        MenuItem {
            id: deleteBillMenuItem
            text: "Delete Bill"
            enabled: root.canDeleteBill(billContextMenu.bill)
            onTriggered: root.requestDeleteBill(billContextMenu.bill)
            contentItem: Label {
                text: deleteBillMenuItem.text
                color: deleteBillMenuItem.enabled ? (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : "#A12E2E") : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#94A0AD")
                verticalAlignment: Text.AlignVCenter
                leftPadding: 12
            }
            background: Rectangle {
                color: deleteBillMenuItem.highlighted ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.12) : "#FCEBEC") : "transparent"
                radius: visualRules.isPro ? visualRules.radiusControl : 4
            }
        }
    }

    Dialog {
        id: deleteBillDialog
        modal: true
        focus: true
        title: "Delete supplier bill"
        standardButtons: Dialog.NoButton
        anchors.centerIn: Overlay.overlay
        width: 430

        background: Rectangle {
            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"
            radius: visualRules.isPro ? visualRules.radiusPopup : 8
            border.width: 1
            border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
        }

        contentItem: ColumnLayout {
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: root.contextBill
                    ? "Permanently delete " + String(root.contextBill.Vendor || "supplier bill")
                      + " • " + String(root.contextBill.VendorInvoiceNumber || "") + "?"
                    : "Permanently delete this supplier bill?"
                color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                wrapMode: Text.Wrap
            }
            Label {
                Layout.fillWidth: true
                text: "Deletion is allowed only for unpaid bills with no active payments. Reverse active payments first."
                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#607287"
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "Cancel"; onClicked: deleteBillDialog.close() }
                Button {
                    id: confirmDeleteButton
                    text: "Delete Bill"
                    enabled: root.canDeleteBill(root.contextBill) && !root.busy
                    onClicked: {
                        deleteBillDialog.close()
                        root.deleteContextBill()
                    }
                    contentItem: Label {
                        text: confirmDeleteButton.text
                        color: root.isProMode ? SemanticTheme.readableInk(SemanticTheme.tone(root.t, "error", root.appStyle)) : "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: confirmDeleteButton.down ? (root.isProMode ? SemanticTheme.mix(SemanticTheme.tone(root.t, "error", root.appStyle), "#000000", 0.2) : "#8E2525") : (confirmDeleteButton.hovered ? (root.isProMode ? SemanticTheme.mix(SemanticTheme.tone(root.t, "error", root.appStyle), "#FFFFFF", 0.15) : "#B94242") : (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : "#A12E2E"))
                        radius: visualRules.isPro ? visualRules.radiusControl : 5
                    }
                }
            }
        }
    }

    Dialog {
        id: reversalDialog
        modal: true
        focus: true
        title: "Reverse active payment"
        standardButtons: Dialog.NoButton
        anchors.centerIn: Overlay.overlay
        width: 470

        background: Rectangle {
            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"
            radius: visualRules.isPro ? visualRules.radiusPopup : 8
            border.width: 1
            border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#B9C9DB"
        }

        contentItem: ColumnLayout {
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: "Select the active payment to reverse. The reversal retains the payment audit history and restores the bill balance."
                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"
                wrapMode: Text.Wrap
            }
            Repeater {
                model: root.activePaymentChoices
                delegate: Button {
                    id: paymentChoiceButton
                    required property var modelData
                    Layout.fillWidth: true
                    checkable: true
                    checked: root.selectedReversalPayment === modelData
                    text: String(modelData.PaymentDate || "") + "  •  "
                        + root.moneyText(modelData.Amount) + "  •  "
                        + String(modelData.Reference || modelData.Method || "Payment")
                    onClicked: root.selectedReversalPayment = modelData
                    contentItem: Label {
                        text: paymentChoiceButton.text
                        color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                        leftPadding: 10
                        rightPadding: 10
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        color: paymentChoiceButton.checked ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#DCEBFA") : (paymentChoiceButton.hovered ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.08) : "#EEF5FC") : (root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FFFFFF"))
                        border.width: 1
                        border.color: paymentChoiceButton.checked ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#3A78AE") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#C7D3DF")
                        radius: visualRules.isPro ? visualRules.radiusControl : 5
                    }
                }
            }
            FormLabel { text: "Reversal reason *" }
            FormField {
                id: reversalReasonField
                Layout.fillWidth: true
                placeholderText: "Why is this payment being reversed?"
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "Cancel"; onClicked: reversalDialog.close() }
                Button {
                    text: "Reverse Payment"
                    enabled: !root.busy && !!root.selectedReversalPayment && reversalReasonField.text.trim().length > 0
                    onClicked: root.reverseSelectedPayment()
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.isProMode ? SemanticTheme.surfaceApp(root.t, root.appStyle) : "#F4F7FA"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Label {
                        text: "Accounts Payable"
                        color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                        font.pixelSize: 22
                        font.weight: Font.DemiBold
                    }

                    Label {
                        text: "Supplier bills, recoverable costs, payments, and outstanding balances"
                        color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#607287"
                        font.pixelSize: 12
                    }
                }

                ToolbarButton {
                    text: root.paymentMode ? "New bill" : "Record payment"
                    onClicked: root.paymentMode = !root.paymentMode
                }

                ToolbarButton {
                    text: root.entryPanelVisible ? "Focus results" : "Show entry"
                    onClicked: root.entryPanelVisible = !root.entryPanelVisible
                }

                ToolbarButton {
                    text: "Refresh"
                    enabled: !root.busy
                    onClicked: root.loadBills()
                }
            }

            Rectangle {
                visible: root.statusMessage.length > 0
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? 36 : 0
                color: root.errorState ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.12) : "#FFF0F0") : (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "success", root.appStyle), 0.12) : "#EDF7F0")
                radius: visualRules.isPro ? visualRules.radiusControl : 6
                border.color: root.errorState ? (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : "#D76A6A") : (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : "#76A987")

                Label {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    text: root.statusMessage
                    color: root.errorState ? (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : "#8B2D2D") : (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : "#285C37")
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Rectangle {
                    visible: root.entryPanelVisible
                    Layout.preferredWidth: visible ? Math.min(380, Math.max(330, root.width * 0.27)) : 0
                    Layout.fillHeight: true
                    color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "#FFFFFF"
                    radius: visualRules.isPro ? visualRules.radiusPanel : 8
                    border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#CDD8E5"
                    clip: true

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 9
                        contentWidth: availableWidth
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded

                        ColumnLayout {
                            width: parent.width
                            spacing: 3

                            Label {
                                text: root.paymentMode ? "Record payment"
                                    : (root.editingBillId.length > 0 ? "Edit supplier bill" : "Add supplier bill")
                                color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                            }

                            Label {
                                visible: root.paymentMode
                                Layout.fillWidth: true
                                text: root.selectedBill
                                    ? String(root.selectedBill.Vendor || "") + "  •  "
                                        + String(root.selectedBill.VendorInvoiceNumber || "")
                                    : "Select a bill from the results panel first."
                                color: root.selectedBill ? (root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D") : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#8291A3")
                                wrapMode: Text.Wrap
                            }

                            ColumnLayout {
                                visible: !root.paymentMode
                                Layout.fillWidth: true
                                spacing: 5

                                FormLabel { text: "Vendor *" }
                                FormField { id: vendorField; placeholderText: "Vendor or supplier" }

                                FormLabel { text: "Invoice number *" }
                                FormField { id: invoiceNumberField; placeholderText: "Supplier invoice number" }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        FormLabel { text: "Invoice date" }
                                        FormField {
                                        id: invoiceDateField
                                        placeholderText: "YYYY-MM-DD"
                                        MouseArea {
                                            anchors.fill: parent
                                            acceptedButtons: Qt.LeftButton
                                            propagateComposedEvents: true
                                            onClicked: function(mouse) { mouse.accepted = false }
                                            onDoubleClicked: root.openDatePicker(parent)
                                        }
                                    }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        FormLabel { text: "Due date" }
                                        FormField {
                                        id: dueDateField
                                        placeholderText: "YYYY-MM-DD"
                                        MouseArea {
                                            anchors.fill: parent
                                            acceptedButtons: Qt.LeftButton
                                            propagateComposedEvents: true
                                            onClicked: function(mouse) { mouse.accepted = false }
                                            onDoubleClicked: root.openDatePicker(parent)
                                        }
                                    }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        FormLabel { text: "Subtotal *" }
                                        FormField {
                                            id: subtotalField
                                            placeholderText: "0.00"
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            onTextEdited: root.syncAPFromSubtotal()
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        FormLabel { text: "Tax" }
                                        FormField {
                                            id: taxField
                                            placeholderText: "0.00"
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            enabled: !root.apTaxExempt
                                            onTextEdited: root.syncAPFromTax()
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        FormLabel { text: "Total" }
                                        FormField {
                                            id: totalField
                                            placeholderText: "0.00"
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            onTextEdited: root.syncAPFromTotal()
                                        }
                                    }
                                }

                                Row {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 32
                                    spacing: 8

                                    FormLabel {
                                        id: currencyLabel
                                        objectName: "apCurrencyLabel"
                                        text: "Currency"
                                        width: 58
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    LightComboBox {
                                        id: currencyField
                                        objectName: "apCurrencyCombo"
                                        width: 86
                                        height: 32
                                        model: ["CAD", "USD"]
                                    }
                                    CheckBox {
                                        id: taxExemptCheckBox
                                        text: ""
                                        checked: root.apTaxExempt
                                        width: 18
                                        height: 32
                                        onToggled: {
                                            root.apTaxExempt = checked
                                            root.applyTaxExempt()
                                        }
                                        contentItem: Item { }
                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: taxExemptCheckBox.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: visualRules.isPro ? visualRules.radiusControl : 3
                                            border.width: 1
                                            border.color: taxExemptCheckBox.checked ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F6FA8") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#8FA4B8")
                                            color: taxExemptCheckBox.checked ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#2F6FA8") : (root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF")
                                            Text {
                                                anchors.centerIn: parent
                                                text: taxExemptCheckBox.checked ? "✓" : ""
                                                color: root.isProMode ? SemanticTheme.readableInk(SemanticTheme.accentPrimary(root.t, root.appStyle)) : "#FFFFFF"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                            }
                                        }
                                    }
                                    Label {
                                        objectName: "apTaxExemptLabel"
                                        text: "Tax Exempt"
                                        width: 86
                                        height: 32
                                        color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }

                                FormLabel { text: "Expense treatment" }
                                SearchSelector {
                                    id: treatmentField
                                    allowBlank: false
                                    allOptions: root.expenseTreatments
                                    selectedId: root.selectedTreatmentId
                                    selectedLabel: "General office expense"
                                    onOptionChosen: function(option) {
                                        root.selectedTreatmentId = String(option.id || "office")
                                        if (root.selectedTreatmentId !== "matter")
                                            root.clearMatterSelection()
                                    }
                                }

                                FormLabel { text: "Expense category *" }
                                SearchSelector {
                                    id: categoryField
                                    allowBlank: false
                                    allOptions: root.categoryOptions
                                    searchHint: "Select or search categories"
                                    dialogTitle: "Select expense category"
                                    onOptionChosen: function(option) {
                                        root.selectedCategoryId = String(option.id || "")
                                    }
                                }

                                FormLabel { text: "Expected payment account (optional)" }
                                SearchSelector {
                                    id: accountField
                                    allowBlank: true
                                    blankLabel: "No expected payment account"
                                    allOptions: root.paymentAccountOptions
                                    searchHint: "Select or search accounts"
                                    dialogTitle: "Select payment account"
                                    onOptionChosen: function(option) {
                                        root.selectedPaymentAccountId = String(option.id || "")
                                    }
                                }

                                FormLabel {
                                    visible: root.selectedTreatmentId === "matter"
                                    text: "Client matter *"
                                }
                                SearchSelector {
                                    id: matterField
                                    visible: root.selectedTreatmentId === "matter"
                                    Layout.preferredHeight: visible ? 32 : 0
                                    allowBlank: false
                                    allOptions: root.matterOptions
                                    searchHint: "Select or search client matters"
                                    dialogTitle: "Select client matter"
                                    onOptionChosen: function(option) {
                                        root.selectedMatterId = String(option.id || "")
                                        root.selectedMatterName = String(option.matterName || "")
                                        root.selectedMatterClientId = String(option.clientId || "")
                                        root.selectedMatterClientName = String(option.clientName || "")
                                    }
                                }

                                FormLabel { text: "Notes" }
                                TextArea {
                                    id: notesField
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 48
                                    color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                    wrapMode: TextEdit.Wrap
                                    padding: 9
                                    background: Rectangle {
                                        color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
                                        radius: visualRules.isPro ? visualRules.radiusControl : 6
                                        border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#C7D3DF"
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.paymentMode
                                Layout.fillWidth: true
                                spacing: 5

                                FormLabel { text: "Payment date" }
                                FormField {
                                        id: paymentDateField
                                        placeholderText: "YYYY-MM-DD"
                                        MouseArea {
                                            anchors.fill: parent
                                            acceptedButtons: Qt.LeftButton
                                            propagateComposedEvents: true
                                            onClicked: function(mouse) { mouse.accepted = false }
                                            onDoubleClicked: root.openDatePicker(parent)
                                        }
                                    }

                                FormLabel { text: "Amount *" }
                                FormField { id: paymentAmountField; placeholderText: "0.00" }

                                FormLabel { text: "From account *" }
                                SearchSelector {
                                    id: paymentAccountField
                                    allowBlank: false
                                    allOptions: root.paymentAccountOptions
                                    searchHint: "Select or search accounts"
                                    dialogTitle: "Select payment account"
                                    onOptionChosen: function(option) {
                                        root.selectedPaymentAccountId = String(option.id || "")
                                    }
                                }

                                FormLabel { text: "Method" }
                                LightComboBox {
                                    id: paymentMethodField
                                    objectName: "apPaymentMethodCombo"
                                    model: ["EFT", "Cheque", "Credit card", "Debit card", "Pre-authorized debit", "Cash", "Wire transfer", "Internal transfer", "Owner-paid", "Other"]
                                }

                                FormLabel { text: "Reference" }
                                FormField { id: paymentReferenceField; placeholderText: "Confirmation or cheque number" }

                                FormLabel { text: "Notes" }
                                TextArea {
                                    id: paymentNotesField
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 72
                                    color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                    wrapMode: TextEdit.Wrap
                                    padding: 9
                                    background: Rectangle {
                                        color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "#FFFFFF"
                                        radius: visualRules.isPro ? visualRules.radiusControl : 6
                                        border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#C7D3DF"
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Button {
                                    visible: !root.paymentMode && root.editingBillId.length > 0
                                    text: "Cancel Edit"
                                    onClicked: root.cancelEdit()
                                }

                                Button {
                                    Layout.fillWidth: true
                                    implicitHeight: 34
                                    enabled: !root.busy && (!root.paymentMode || root.selectedBill)
                                    text: root.busy ? "Working..." : (root.paymentMode
                                        ? "Record payment"
                                        : (root.editingBillId.length > 0 ? "Save changes" : "Save bill"))
                                    onClicked: root.paymentMode ? root.savePayment() : root.saveBill()
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "#FFFFFF"
                    radius: visualRules.isPro ? visualRules.radiusPanel : 8
                    border.color: root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#CDD8E5"
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true

                            Label {
                                Layout.fillWidth: true
                                text: "Bills and balances"
                                color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                            }

                            Label {
                                text: String(root.billRows.length) + " bill" + (root.billRows.length === 1 ? "" : "s")
                                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#607287"
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 36
                            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#F0F4F8"
                            radius: visualRules.isPro ? visualRules.radiusControl : 5

                            Row {
                                anchors.fill: parent
                                anchors.leftMargin: root.billColumnMargin
                                anchors.rightMargin: root.billColumnMargin
                                spacing: root.billColumnSpacing

                                Label { width: root.billVendorColumnWidth(parent.width); height: parent.height; text: "Vendor / invoice"; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                Label { width: root.billDueColumnWidth; height: parent.height; text: "Due"; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                Label { width: root.billStatusColumnWidth; height: parent.height; text: "Status"; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                Label { width: root.billBalanceColumnWidth; height: parent.height; text: "Balance"; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignRight }
                            }
                        }

                        ListView {
                            id: billList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 4
                            model: root.billRows

                            delegate: Rectangle {
                                id: billRow
                                required property var modelData
                                required property int index
                                width: billList.width
                                height: 60
                                radius: visualRules.isPro ? visualRules.radiusControl : 6
                                color: root.selectedBill === billRow.modelData ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : "#E8F1FA") : (root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "#FAFBFC")
                                border.color: root.selectedBill === billRow.modelData ? (root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : "#3A78AE") : (root.isProMode ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "#D7E0E8")

                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: root.billColumnMargin
                                    anchors.rightMargin: root.billColumnMargin
                                    spacing: root.billColumnSpacing

                                    Column {
                                        width: root.billVendorColumnWidth(parent.width)
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 1
                                        Label { width: parent.width; text: String(billRow.modelData.Vendor || ""); color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                        Label { width: parent.width; text: String(billRow.modelData.VendorInvoiceNumber || ""); color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#607287"; elide: Text.ElideRight }
                                    }

                                    Label { width: root.billDueColumnWidth; height: parent.height; text: String(billRow.modelData.DueDate || ""); color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                    Label { width: root.billStatusColumnWidth; height: parent.height; text: String(billRow.modelData.Status || ""); color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                    Label { width: root.billBalanceColumnWidth; height: parent.height; text: root.moneyText(billRow.modelData.Balance); color: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : "#172A40"; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignRight }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onPressed: function(mouse) {
                                        if (mouse.button === Qt.RightButton) {
                                            root.contextBill = billRow.modelData
                                            root.selectBill(billRow.modelData)
                                            billContextMenu.popup(billRow, mouse.x, mouse.y)
                                        }
                                    }
                                    onClicked: function(mouse) {
                                        if (mouse.button !== Qt.LeftButton)
                                            return
                                        root.selectBill(billRow.modelData)
                                    }
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button !== Qt.LeftButton)
                                            return
                                        root.selectBill(billRow.modelData)
                                        root.paymentMode = true
                                        root.entryPanelVisible = true
                                    }
                                }
                            }

                            ColumnLayout {
                                anchors.centerIn: parent
                                visible: !root.busy && root.billRows.length === 0
                                spacing: 6

                                Label {
                                    text: "No supplier bills yet"
                                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : "#42566D"
                                    font.pixelSize: 16
                                    font.weight: Font.DemiBold
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Label {
                                    text: "Add the first bill using the compact entry panel."
                                    color: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : "#8291A3"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        BusyIndicator {
            anchors.centerIn: parent
            visible: root.busy
            running: root.busy
            z: 100
        }
    }
}
