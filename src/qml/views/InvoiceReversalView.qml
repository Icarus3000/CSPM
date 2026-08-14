import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import Qt.labs.platform 1.1
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    anchors.fill: parent

    property QtObject appController
    property QtObject windowRef
    property QtObject billingBackend: appController ? appController.billing : null

    property var t
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : (root.appController && root.appController.appStyle) ? String(root.appController.appStyle) : "Professional"
    property bool isProMode: root.appStyle === "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property color _bg: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color _primary: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _danger: SemanticTheme.tone(root.t, "error", root.appStyle)

    property var invoicesModel: []
    property string selectedInvoiceNum: ""
    property var selectedInvoiceData: null
    property var selectedInvoiceSummary: null
    property var selectedPaymentHistory: []
    property bool invoiceListLoading: false
    property bool invoiceDetailsLoading: false
    property var _calInstance: null
    property bool _isEditingFinancials: false
    // Normal lookup/posting lives in the invoice directory; reversal stays a
    // separate, intentionally destructive workflow.
    property bool directoryMode: false
    property bool compactLayout: width < 1320
    property int outerMargin: root.compactLayout ? 12 : 16
    property int detailMargin: root.compactLayout ? 18 : 28
    property int actionWidth: root.compactLayout ? 132 : 150
    // Keep the three summary cards deliberately substantial.  Their paired
    // expanding spacers preserve equal breathing room above and below content.
    property int invoiceCardHeight: root.compactLayout ? 232 : 255
    property int ledgerAmountColumnWidth: root.compactLayout ? 82 : 96
    property int ledgerDateColumnWidth: root.compactLayout ? 70 : 82

    Component.onCompleted: {
        _loadInvoices()
    }

    function _loadInvoices() {
        if (!billingBackend) return
        invoiceListLoading = true
        billingBackend.loadFinalizedInvoices()
    }

    function _applyInvoices(rawInvoices) {
        rawInvoices = rawInvoices || []
        var filtered = []
        var query = (typeof searchInput !== "undefined" && searchInput) ? searchInput.text.toLowerCase() : ""

        // CSPM invoices match YY-NNNN pattern (e.g. 26-0070)
        var cspmRegex = /^\d{2}-\d{4}$/

        for (var i = 0; i < rawInvoices.length; i++) {
            var inv = rawInvoices[i]
            var num = String(inv.InvoiceNum || "")
            
            // Only include CSPM generated invoices (filter out vendor AP bills)
            if (!cspmRegex.test(num)) continue
            
            // Apply text search
            if (query !== "") {
                var cName = String(inv.ClientName || "").toLowerCase()
                var scName = String(inv.SubClient || "").toLowerCase()
                if (num.toLowerCase().indexOf(query) === -1 && 
                    cName.indexOf(query) === -1 && 
                    scName.indexOf(query) === -1) {
                    continue
                }
            }
            filtered.push(inv)
        }

        // Sort descending by invoice number
        filtered.sort(function(a, b) {
            var nA = String(a.InvoiceNum || "")
            var nB = String(b.InvoiceNum || "")
            return nA > nB ? -1 : (nA < nB ? 1 : 0)
        })
        invoicesModel = filtered
        
        if (selectedInvoiceNum) {
            var found = false
            for (var j = 0; j < invoicesModel.length; j++) {
                if (String(invoicesModel[j].InvoiceNum) === selectedInvoiceNum) {
                    selectedInvoiceData = invoicesModel[j]
                    found = true
                    root._refreshSelectedInvoiceDetails()
                    break
                }
            }
            if (!found) {
                selectedInvoiceNum = ""
                selectedInvoiceData = null
            }
        }
        invoiceListLoading = false
    }

    function _selectInvoice(invNum) {
        if (selectedInvoiceNum === invNum && selectedInvoiceData) {
            selectedInvoiceNum = ""
            selectedInvoiceData = null
            selectedInvoiceSummary = null
            selectedPaymentHistory = []
            invoiceDetailsLoading = false
            return
        }
        selectedInvoiceNum = invNum
        selectedInvoiceSummary = null
        selectedPaymentHistory = []
        invoiceDetailsLoading = true
        for (var i = 0; i < invoicesModel.length; i++) {
            if (String(invoicesModel[i].InvoiceNum) === invNum) {
                selectedInvoiceData = invoicesModel[i]
                root._refreshSelectedInvoiceDetails()
                break
            }
        }
    }

    function _refreshSelectedInvoiceDetails() {
        if (!root.selectedInvoiceNum) return
        root.invoiceDetailsLoading = true
        if (root.billingBackend) root.billingBackend.loadInvoiceDirectoryDetails(root.selectedInvoiceNum)
    }

    onBillingBackendChanged: {
        if (billingBackend && invoicesModel.length === 0) _loadInvoices()
    }

    function _paymentDateLabel(value) {
        var dateText = String(value || "").substring(0, 10)
        if (!dateText) return "Date not recorded"
        var dateValue = new Date(dateText + "T12:00:00")
        if (isNaN(dateValue.getTime())) return dateText
        return Qt.locale().toString(dateValue, "MMM d, yyyy")
    }

    function _displayInvoiceStatus(summary) {
        if (!summary) return "Unavailable"
        var raw = String(summary.Status || "").trim().toLowerCase()
        var hasBalance = Object.prototype.hasOwnProperty.call(summary, "BalanceDue")
        var balance = Number(summary.BalanceDue)
        var paid = Number(summary.AmountPaid || 0)

        // The legacy receivables sheet calls an outstanding invoice "PENDING".
        // That describes neither the invoice state nor the next action.  In
        // CSPM an issued invoice with a positive balance is plainly Unpaid;
        // partial payment is shown separately and a settled invoice is Paid.
        if (hasBalance && isFinite(balance)) {
            if (Math.abs(balance) <= 0.005) return "Paid"
            if (paid > 0.005) return "Partially Paid"
            if (balance > 0.005) return "Unpaid"
        }
        if (raw === "pending" || raw === "unpaid") return "Unpaid"
        if (raw === "partial") return "Partially Paid"
        if (raw === "closed") return "Closed"
        if (raw === "paid") return "Paid"
        return raw ? String(summary.Status) : "Unavailable"
    }

    function _isSettledInvoiceStatus(status) {
        return status === "Paid" || status === "Closed"
    }

    function _isPartialInvoiceStatus(status) {
        return status === "Partially Paid"
    }

    function _paymentWorkspaceState(invoiceNumber, paymentId, clientName) {
        var invoice = String(invoiceNumber || root.selectedInvoiceNum || "")
        if (!invoice) return null
        var payment = String(paymentId || "")
        var contextId = payment.length > 0 ? "edit:" + payment : "new:" + invoice
        var title = payment.length > 0 ? "Payment: " + payment : "Payment Entry: " + invoice
        var state = {
            "focusNodeId": "C07",
            "invoiceNum": invoice,
            "entityType": "payment",
            "entityId": contextId,
            "entityTitle": title,
            "tabTitle": title,
            // Do not write the C07 state into the currently active Invoice
            // Directory panel before its own payment tab is activated.
            "deferTabStateUntilActivated": true
        }
        if (payment.length > 0) state.paymentId = payment
        if (clientName) state.clientName = String(clientName)
        return state
    }

    function _openPaymentEntry(invoiceNumber, paymentId, clientName) {
        var state = _paymentWorkspaceState(invoiceNumber, paymentId, clientName)
        if (!state) return
        root.workspaceOpenRequested(2, "C07", state)
    }

    function _transactionWorkspaceState(invoiceNumber, historyRow, clientName) {
        if (!historyRow) return null
        var transaction = String(historyRow.transactionId || historyRow.paymentId || "")
        if (!transaction) return null
        var payload = historyRow.transactionPayload
        if (!payload || typeof payload !== "object") return null
        var title = "Transaction: " + transaction
        var state = {
            "focusNodeId": "C11",
            "invoiceNum": String(invoiceNumber || root.selectedInvoiceNum || ""),
            "entityType": "transaction",
            "entityId": transaction,
            "entityTitle": title,
            "tabTitle": title,
            "payload": payload,
            "categoryText": String(payload.categoryCode || "")
                + (payload.categoryCode && payload.categoryName ? " - " : "")
                + String(payload.categoryName || ""),
            // Just like a payment tab, do not apply this new tab's state to
            // the still-visible Invoice Directory before activation.
            "deferTabStateUntilActivated": true
        }
        if (clientName) state.clientName = String(clientName)
        return state
    }

    function _setoffWorkspaceState(invoiceNumber, historyRow, clientName) {
        if (!historyRow) return null
        var billId = String(historyRow.apBillId || "")
        var paymentId = String(historyRow.apPaymentId || historyRow.paymentId || "")
        if (!billId || !paymentId) return null
        var title = "Settlement Set-off: " + paymentId
        var state = {
            "focusNodeId": "C18",
            "invoiceNum": String(invoiceNumber || root.selectedInvoiceNum || ""),
            "entityType": "ap_setoff",
            "entityId": paymentId,
            "entityTitle": title,
            "tabTitle": title,
            "apBillId": billId,
            "apPaymentId": paymentId,
            "deferTabStateUntilActivated": true
        }
        if (clientName) state.clientName = String(clientName)
        return state
    }

    function _openPaymentHistoryRecord(historyRow) {
        if (!historyRow) return
        var clientName = root.selectedInvoiceData ? root.selectedInvoiceData.ClientName : ""
        if (String(historyRow.openTarget || "") === "ap_setoff") {
            var setoffState = root._setoffWorkspaceState(root.selectedInvoiceNum, historyRow, clientName)
            if (setoffState) root.workspaceOpenRequested(2, "C18", setoffState)
            return
        }
        if (String(historyRow.openTarget || "") === "transaction") {
            var transactionState = root._transactionWorkspaceState(root.selectedInvoiceNum, historyRow, clientName)
            if (transactionState) root.workspaceOpenRequested(2, "C11", transactionState)
            return
        }
        root._openPaymentEntry(root.selectedInvoiceNum, historyRow.paymentId, clientName)
    }

    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)

    function applyJumpState(state) {
        if (!state) return
        var inv = String(state.selectedInvoiceNum || state.invoiceNum || state.entityId || state.invoiceId || "")
        if (inv.length > 0 && selectedInvoiceNum !== inv) {
            _selectInvoice(inv)
        }
    }

    // Connect to billingBackend signals if it exists
    Connections {
        target: root.billingBackend
        function onFinalizedInvoicesLoaded(invoices) {
            root._applyInvoices(invoices || [])
        }
        function onInvoiceDirectoryDetailsLoaded(payload) {
            if (!payload || String(payload.invoiceNum || "") !== root.selectedInvoiceNum) return
            root.selectedInvoiceSummary = payload.summary || {}
            root.selectedPaymentHistory = payload.paymentHistory || []
            root.invoiceDetailsLoading = false
        }
        function onInvoiceDirectoryDetailsFailed(invoiceNum, _message) {
            if (String(invoiceNum || "") === root.selectedInvoiceNum) {
                root.invoiceDetailsLoading = false
                root.selectedInvoiceSummary = {}
                root.selectedPaymentHistory = []
            }
        }
        function onInvoiceReversalProgress(payload) {
            if (!payload || String(payload.invoiceNum || "") !== root.selectedInvoiceNum) return
            reverseDialog.operationInProgress = payload.active === true
        }
        function onDraftReversed(result) {
            if (result.ok) {
                reverseDialog.operationInProgress = false
                reverseDialog.visible = false
                root.selectedInvoiceNum = ""
                root.selectedInvoiceData = null
                root.selectedInvoiceSummary = null
                root.selectedPaymentHistory = []
                root.invoiceDetailsLoading = false
                root._loadInvoices()

                if (result.action === "correct_reissue" && result.invoiceNum) {
                    root.workspaceOpenRequested(2, "C01", {
                        "focusNodeId": "C01",
                        "correctionInvoiceNum": String(result.invoiceNum)
                    })
                    return
                }
                
                if (result.newDraftNum) {
                    if (root.appRef && root.appRef.handleWorkspaceOpenRequested) {
                        root.appRef.handleWorkspaceOpenRequested(2, "C06", {
                            "draftNum": result.newDraftNum,
                            "selectedInvoiceNum": result.newDraftNum
                        })
                    }
                }
            }
        }
    }

    Connections {
        target: root.appController ? root.appController.docketing : null
        function onPaymentSaveFinished(result) {
            if (result && result.ok && String(result.invoice || "") === root.selectedInvoiceNum) {
                root._refreshSelectedInvoiceDetails()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: root.outerMargin
        spacing: root.compactLayout ? 12 : 16

        // Left Pane: Invoice List
        Rectangle {
            Layout.preferredWidth: root.compactLayout ? 280 : 340
            Layout.fillHeight: true
            color: root._bg
            border.color: root._border
            border.width: 1
            radius: visualRules.isPro ? visualRules.radiusPanel : 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: root.directoryMode ? "Invoice Directory" : "Finalized Invoices"
                    color: root._text
                    font.pixelSize: 16
                    font.bold: true
                }

                Text {
                    visible: root.invoiceListLoading
                    text: "Loading invoices…"
                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    font.pixelSize: 12
                }
                
                TextField {
                    id: searchInput
                    Layout.fillWidth: true
                    placeholderText: "Search invoice or client..."
                    color: root._text
                    placeholderTextColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    background: Rectangle {
                        color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._bg
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                    }
                    onTextChanged: root._loadInvoices()
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: root._border
                }

                ListView {
                    id: invoiceListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root.invoicesModel

                    delegate: Rectangle {
                        id: invoiceDirectoryRow
                        property string matterDescription: String(modelData.MatterDescription || "").trim()

                        width: invoiceListView.width
                        // Keep the familiar two-line row for historic entries
                        // with no resolved matter, and give a third line just
                        // enough room to identify the plain-English matter.
                        height: matterDescription.length > 0 ? 76 : 60
                        color: root.selectedInvoiceNum === (modelData.InvoiceNum || "") ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : SemanticTheme.hoverOverlay(root.t, root.appStyle)) : "transparent"
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4

                        MouseArea {
                            id: invoiceRowMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root._selectInvoice(modelData.InvoiceNum || "")
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 4
                            
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "Invoice " + (modelData.InvoiceNum || "Unknown")
                                    font.pixelSize: 14
                                    font.weight: Font.Medium
                                    color: root._text
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: (modelData.InvoiceDate || "").substring(0, 10)
                                    font.pixelSize: 12
                                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                                }
                            }

                            Text {
                                text: modelData.ClientName || "Unknown Client"
                                font.pixelSize: 13
                                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Text {
                                visible: invoiceDirectoryRow.matterDescription.length > 0
                                text: "Matter · " + invoiceDirectoryRow.matterDescription
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                color: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        ToolTip.visible: invoiceRowMouseArea.containsMouse && matterDescription.length > 0
                        ToolTip.text: matterDescription
                        ToolTip.delay: 500
                    }
                    
                    ScrollBar.vertical: ScrollBar { }
                }
            }
        }

        // Right Pane: Detail & Action
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.isProMode ? SemanticTheme.surfaceApp(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle) // soft premium background
            border.color: root._border
            border.width: 1
            radius: visualRules.isPro ? visualRules.radiusPanel : 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.detailMargin
                spacing: root.compactLayout ? 16 : 22
                visible: !!root.selectedInvoiceData

                // Header Area
                RowLayout {
                    Layout.fillWidth: true
                    
                    ColumnLayout {
                        spacing: 4
                        Text {
                            text: "Invoice " + (root.selectedInvoiceData ? root.selectedInvoiceData.InvoiceNum : "")
                            font.pixelSize: root.compactLayout ? 24 : 28
                            font.weight: Font.Bold
                            color: root._text
                        }
                        
                        RowLayout {
                            spacing: 8
                            Text { text: "Invoice Date:"; font.pixelSize: 14; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            property string displayDate: root.selectedInvoiceData ? (root.selectedInvoiceData.InvoiceDate || "").substring(0, 10) : ""
                            Text {
                                text: parent.displayDate === "" ? "Double-click to set" : parent.displayDate
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                color: parent.displayDate === "" ? root._primary : root._text
                                
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: {
                                        if (!root._calInstance) {
                                            var comp = Qt.createComponent("../components/JellyCalendar.qml")
                                            if (comp.status === Component.Ready) {
                                                root._calInstance = comp.createObject(root)
                                                root._calInstance.datePicked.connect(function(d) {
                                                    var tzOffset = (new Date()).getTimezoneOffset() * 60000;
                                                    var localISOTime = (new Date(d.getTime() - tzOffset)).toISOString().slice(0, -1);
                                                    var dateStr = localISOTime.substring(0, 10);
                                                    
                                                    if (root.appController && root.appController.docketing) {
                                                        root.appController.docketing.updateInvoiceLogEntry({
                                                            "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                                            "invoiceDate": dateStr
                                                        })
                                                        // Clone the object to trigger QML property bindings
                                                        var clone = Object.assign({}, root.selectedInvoiceData)
                                                        clone.InvoiceDate = dateStr
                                                        root.selectedInvoiceData = clone
                                                    }
                                                })
                                            }
                                        }
                                        if (root._calInstance) {
                                            var pt = mapToGlobal(width / 2, height / 2)
                                            if (parent.parent.displayDate !== "") {
                                                root._calInstance.selectedDate = new Date(parent.parent.displayDate + "T12:00:00")
                                            } else {
                                                root._calInstance.selectedDate = new Date()
                                            }
                                            root._calInstance.openAt(pt.x, pt.y)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        visible: root.invoiceDetailsLoading
                        text: "Loading invoice details..."
                        font.pixelSize: 13
                        color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    }

                    Item { Layout.fillWidth: true } // spacer

                    // Status Badge
                    Rectangle {
                        property bool loading: root.invoiceDetailsLoading
                        property string st: loading ? "Loading..." : root._displayInvoiceStatus(root.selectedInvoiceSummary)
                        property bool canRecordPayment: !loading && (st === "Unpaid" || st === "Partially Paid")
                        width: 144
                        height: 46
                        radius: visualRules.isPro ? 23 : 23
                        color: loading ? SemanticTheme.alpha(root._primary, 0.12) : (root._isSettledInvoiceStatus(st) ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "success", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "success", "Professional")) : (root._isPartialInvoiceStatus(st) ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "warning", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "error", "Professional"))))
                        border.color: loading ? root._primary : (root._isSettledInvoiceStatus(st) ? (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.border(root.t, "success", "Professional")) : (root._isPartialInvoiceStatus(st) ? (root.isProMode ? SemanticTheme.tone(root.t, "warning", root.appStyle) : SemanticTheme.border(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.border(root.t, "error", "Professional"))))
                        border.width: 1
                        Layout.alignment: Qt.AlignTop | Qt.AlignRight
                        Text {
                            anchors.centerIn: parent
                            text: parent.st
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                            color: parent.loading ? root._primary : (root._isSettledInvoiceStatus(parent.st) ? (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.ink(root.t, "success", "Professional")) : (root._isPartialInvoiceStatus(parent.st) ? (root.isProMode ? SemanticTheme.tone(root.t, "warning", root.appStyle) : SemanticTheme.ink(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.ink(root.t, "error", "Professional"))))
                        }
                        MouseArea {
                            id: statusPillMouse
                            anchors.fill: parent
                            enabled: parent.canRecordPayment
                            hoverEnabled: parent.canRecordPayment
                            cursorShape: parent.canRecordPayment ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: root._openPaymentEntry(root.selectedInvoiceNum, "", root.selectedInvoiceData ? root.selectedInvoiceData.ClientName : "")
                        }
                        ToolTip.visible: statusPillMouse.containsMouse && statusPillMouse.enabled
                        ToolTip.text: "Record a payment for this invoice"
                    }
                }

                // 3 Cards Layout
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.invoiceCardHeight
                    Layout.minimumHeight: root.invoiceCardHeight
                    Layout.maximumHeight: root.invoiceCardHeight
                    spacing: root.compactLayout ? 14 : 22

                    // Card 1: Client & Matters
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.compactLayout ? 16 : 20
                            spacing: 8
                            Item { Layout.fillHeight: true }
                            Text { text: "Client & Matter Details"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            Text {
                                text: root.selectedInvoiceSummary ? (root.selectedInvoiceSummary.ClientName || "") : ""
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                                color: root._text
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Item { height: 4 }
                            Text { text: "Matter:"; font.pixelSize: 12; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            ListView {
                                Layout.fillWidth: true
                                Layout.preferredHeight: visible ? (root.compactLayout ? 44 : 56) : 0
                                clip: true
                                visible: root.selectedInvoiceSummary && root.selectedInvoiceSummary.MatterDetails && root.selectedInvoiceSummary.MatterDetails.length > 0
                                model: root.selectedInvoiceSummary ? (root.selectedInvoiceSummary.MatterDetails || []) : []
                                delegate: Text {
                                    text: modelData.description || ""
                                    font.pixelSize: 13
                                    color: root._text
                                    elide: Text.ElideRight
                                    width: ListView.view.width
                                }
                                ScrollBar.vertical: ScrollBar { }
                            }
                            Text {
                                visible: !root.selectedInvoiceSummary || !root.selectedInvoiceSummary.MatterDetails || root.selectedInvoiceSummary.MatterDetails.length === 0
                                text: "No matter is linked to this historic invoice."
                                font.pixelSize: 12
                                font.italic: true
                                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    // Card 2: Financial Breakdown
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.compactLayout ? 16 : 20
                            spacing: 8
                            Item { Layout.fillHeight: true }
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Financial Breakdown"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.fillWidth: true }
                                Text {
                                    visible: !root.directoryMode
                                    text: root._isEditingFinancials ? "Cancel" : "Edit"
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: root._primary
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (root._isEditingFinancials) {
                                                root._isEditingFinancials = false
                                            } else {
                                                editFeesField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalFees || 0).toFixed(2) : "0.00"
                                                editDisbField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalDisbursements || 0).toFixed(2) : "0.00"
                                                editTaxField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalTax || 0).toFixed(2) : "0.00"
                                                editBilledField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.AggregateBilled || 0).toFixed(2) : "0.00"
                                                root._isEditingFinancials = true
                                            }
                                        }
                                    }
                                }
                            }
                            
                            GridLayout {
                                columns: 2
                                Layout.fillWidth: true
                                rowSpacing: root._isEditingFinancials ? 4 : 8
                                Text { text: "Fees:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalFees || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editFeesField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Text { text: "Disbursements:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalDisbursements || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editDisbField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Text { text: "Taxes:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalTax || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editTaxField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Rectangle { Layout.columnSpan: 2; Layout.fillWidth: true; height: 1; color: root._border }
                                
                                Text { text: "Total Billed:"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.AggregateBilled || 0).toFixed(2) : "$0.00"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { id: editBilledField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; horizontalAlignment: TextInput.AlignRight }
                                }
                                
                                Button {
                                    Layout.columnSpan: 2
                                    Layout.alignment: Qt.AlignRight
                                    visible: root._isEditingFinancials
                                    text: "Save Adjustments"
                                    onClicked: {
                                        if (root.appController && root.appController.docketing) {
                                            var newFees = parseFloat(editFeesField.text) || 0
                                            var newDisb = parseFloat(editDisbField.text) || 0
                                            var newTax = parseFloat(editTaxField.text) || 0
                                            var newBilled = parseFloat(editBilledField.text) || 0
                                            
                                            root.appController.docketing.updateInvoiceLogEntry({
                                                "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                                "totalFees": newFees,
                                                "totalDisbursements": newDisb,
                                                "totalTax": newTax,
                                                "aggregateBilled": newBilled
                                            })
                                            
                                            var clone = Object.assign({}, root.selectedInvoiceSummary)
                                            clone.TotalFees = newFees
                                            clone.TotalDisbursements = newDisb
                                            clone.TotalTax = newTax
                                            clone.AggregateBilled = newBilled
                                            
                                            var amtPaid = parseFloat(clone.AmountPaid || 0)
                                            var bal = newBilled - amtPaid
                                            if (bal <= 0.01 && bal >= -0.01) bal = 0
                                            clone.BalanceDue = bal
                                            
                                            root.selectedInvoiceSummary = clone
                                            
                                            root._isEditingFinancials = false
                                        }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    // Card 3: Ledger Status
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.compactLayout ? 16 : 20
                            spacing: 8
                            Item { Layout.fillHeight: true }
                            Text { text: "Payment & Ledger"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            ListView {
                                Layout.fillWidth: true
                                // Reserve only the rows that actually exist;
                                // a one-payment history must not create a blank
                                // 62 px canyon above the balance summary.
                                Layout.preferredHeight: visible
                                    ? Math.min(root.compactLayout ? 52 : 56,
                                        Math.max(24, root.selectedPaymentHistory.length * 24))
                                    : 0
                                clip: true
                                visible: root.selectedPaymentHistory.length > 0
                                model: root.selectedPaymentHistory
                                delegate: RowLayout {
                                    width: ListView.view.width
                                    height: 24
                                    spacing: 6
                                    Text {
                                        text: modelData.displayLabel
                                            ? modelData.displayLabel
                                            : modelData.paymentId
                                            ? (modelData.type || "Payment") + " " + modelData.paymentId
                                            : (modelData.type || "Payment")
                                        font.pixelSize: 12
                                        font.weight: modelData.paymentId ? Font.DemiBold : Font.Normal
                                        color: paymentLinkMouse.enabled ? root._primary : root._text
                                        font.underline: paymentLinkMouse.containsMouse
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        MouseArea {
                                            id: paymentLinkMouse
                                            anchors.fill: parent
                                            enabled: modelData.editable !== false && !!modelData.paymentId
                                            hoverEnabled: enabled
                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: root._openPaymentHistoryRecord(modelData)
                                        }
                                    }
                                    Text {
                                        text: "$" + parseFloat(modelData.amount || 0).toFixed(2)
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: modelData.type === "Write-off/Adjustment" ? root._text : SemanticTheme.tone(root.t, "success", root.appStyle)
                                        Layout.preferredWidth: root.ledgerAmountColumnWidth
                                        horizontalAlignment: Text.AlignRight
                                        elide: Text.ElideRight
                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: modelData.editable !== false && !!modelData.paymentId
                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: root._openPaymentHistoryRecord(modelData)
                                        }
                                    }
                                    Text {
                                        text: root._paymentDateLabel(modelData.date)
                                        font.pixelSize: 11
                                        color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                                        Layout.preferredWidth: root.ledgerDateColumnWidth
                                        horizontalAlignment: Text.AlignRight
                                        elide: Text.ElideRight
                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: modelData.editable !== false && !!modelData.paymentId
                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: root._openPaymentHistoryRecord(modelData)
                                        }
                                    }
                                }
                                ScrollBar.vertical: ScrollBar { }
                            }
                            Text {
                                visible: root.selectedPaymentHistory.length === 0
                                text: "No payments recorded"
                                font.pixelSize: 12
                                font.italic: true
                                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                            }
                            Item {
                                id: ledgerStatusMetrics
                                visible: false
                                Layout.preferredHeight: 0
                                property int daysUnpaid: {
                                    if (!root.selectedInvoiceData || !root.selectedInvoiceSummary) return -1;
                                    var st = root.selectedInvoiceSummary.Status || "";
                                    if (st === "Closed" || st === "Paid") return -1;
                                    var dateStr = root.selectedInvoiceData.InvoiceDate;
                                    if (!dateStr) return -1;
                                    var d1 = new Date(dateStr.substring(0, 10));
                                    var d2 = new Date();
                                    var diffTime = d2.getTime() - d1.getTime();
                                    var diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
                                    return diffDays;
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text { text: "Amount Paid:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.fillWidth: true }
                                Text {
                                    text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.AmountPaid || 0).toFixed(2) : "$0.00"
                                    font.pixelSize: 16; font.weight: Font.DemiBold; color: root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.tone(root.t, "success", root.appStyle)
                                    Layout.preferredWidth: root.ledgerAmountColumnWidth
                                    horizontalAlignment: Text.AlignRight
                                }
                                Item { Layout.preferredWidth: root.ledgerDateColumnWidth }
                            }
                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root._border }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text { text: "Balance Owing:"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop }
                                ColumnLayout {
                                    Layout.preferredWidth: root.ledgerAmountColumnWidth
                                    Layout.alignment: Qt.AlignRight | Qt.AlignTop
                                    spacing: 2
                                    Text {
                                        text: {
                                            if (root._isEditingFinancials) {
                                                var b = parseFloat(editBilledField.text) || 0
                                                var paid = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.AmountPaid || 0) : 0
                                                var owing = b - paid
                                                if (owing <= 0.01 && owing >= -0.01) owing = 0
                                                return "$" + owing.toFixed(2)
                                            }
                                            return root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.BalanceDue || 0).toFixed(2) : "$0.00"
                                        }
                                        font.pixelSize: 18; font.weight: Font.Bold; color: root._danger
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignRight
                                    }
                                    Text {
                                        text: ledgerStatusMetrics.daysUnpaid >= 0 ? "(" + ledgerStatusMetrics.daysUnpaid + " days outstanding)" : ""
                                        font.pixelSize: 12
                                        color: root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.tone(root.t, "error", root.appStyle)
                                        font.italic: true
                                        visible: ledgerStatusMetrics.daysUnpaid >= 0
                                        Layout.alignment: Qt.AlignRight
                                    }
                                }
                                Item { Layout.preferredWidth: root.ledgerDateColumnWidth }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                // Keep actions directly below the details on short/high-DPI
                // logical canvases instead of pushing them to the pane bottom.
                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignLeft
                    spacing: root.compactLayout ? 10 : 14

                    Rectangle {
                        width: root.actionWidth
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Payment Entry"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.selectedInvoiceData) {
                                    root._openPaymentEntry(
                                        root.selectedInvoiceData.InvoiceNum,
                                        "",
                                        root.selectedInvoiceData.ClientName
                                    )
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: root.compactLayout ? 154 : 176
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Write-off / Adj"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.selectedInvoiceData) {
                                    root.workspaceOpenRequested(2, "C09", {
                                        "focusNodeId": "C09",
                                        "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                        "clientName": root.selectedInvoiceData.ClientName
                                    })
                                }
                            }
                        }
                    }


                    Rectangle {
                        width: root.actionWidth
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Open PDF"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.billingBackend && root.selectedInvoiceData) {
                                    root.billingBackend.openInvoicePdf(root.selectedInvoiceData.InvoiceNum)
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: root.actionWidth
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root._danger
                        Text {
                            anchors.centerIn: parent
                            text: root.directoryMode ? "Reverse..." : "Reverse Invoice"
                            color: root.isProMode ? SemanticTheme.readableInk(root._danger) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.directoryMode) {
                                    root.workspaceOpenRequested(2, "C08", {
                                        "focusNodeId": "C08",
                                        "selectedInvoiceNum": root.selectedInvoiceData.InvoiceNum
                                    })
                                } else {
                                    reverseDialog.operationInProgress = false
                                    reverseDialog.pdfAction = "keep"
                                    reverseDialog.visible = true
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                anchors.centerIn: parent
                visible: !root.selectedInvoiceData
                spacing: 12
                
                Text {
                    text: "No Invoice Selected"
                    font.pixelSize: 20
                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.directoryMode
                        ? "Select a finalized invoice from the left to view its details."
                        : "Select a finalized invoice from the left to view details and reverse it."
                    font.pixelSize: 14
                    color: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

    // Dialog for Reversal Options
    Rectangle {
        id: reverseDialog
        anchors.fill: parent
        color: "transparent"
        visible: false

        // An invoice can be corrected even when no PDF was generated or the
        // original file is unavailable.  Keep is therefore the safe default.
        property string pdfAction: "keep"
        property string targetDir: ""
        property string sourcePdfPath: ""
        property bool operationInProgress: false

        MouseArea {
            anchors.fill: parent
            // block clicks behind
        }

        Rectangle {
            anchors.fill: parent
            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
            opacity: 0.4
        }

        Rectangle {
            id: reverseDialogCard
            width: Math.min(620, Math.max(360, parent.width - 32))
            height: Math.min(parent.height - 24, 560)
            anchors.centerIn: parent
            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : root._bg
            radius: visualRules.isPro ? visualRules.radiusPopup : 8
            border.color: root._border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: "Correct or Reverse Invoice " + (root.selectedInvoiceNum || "")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: root._text
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        color: "transparent"
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text {
                            anchors.centerIn: parent
                            text: "\u00d7"
                            color: root._text
                            font.pixelSize: 20
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !reverseDialog.operationInProgress
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: reverseDialog.visible = false
                        }
                    }
                }

                Text {
                    text: "Correct & Reissue returns only this invoice's WIP to unbilled work and reserves the same invoice number for its replacement. Reassign the returned WIP if needed, then build a fresh draft. The original and reversal remain internal audit evidence and do not appear on the client statement."
                    font.pixelSize: 13
                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                ScrollView {
                    id: reversalOptionsScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        width: reversalOptionsScroll.availableWidth
                        spacing: 10

                        Text {
                            text: "Invoice PDF (optional)"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: root._text
                        }

                        Text {
                            text: "No PDF available? Leave \"Keep PDF\" selected and continue."
                            font.pixelSize: 13
                            color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            color: reverseDialog.pdfAction === "keep" ? SemanticTheme.alpha(root._primary, 0.10) : "transparent"
                            border.color: reverseDialog.pdfAction === "keep" ? root._primary : root._border
                            border.width: 1
                            radius: visualRules.isPro ? visualRules.radiusControl : 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    Layout.preferredWidth: 15
                                    Layout.preferredHeight: 15
                                    radius: 8
                                    color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : root._bg
                                    border.color: reverseDialog.pdfAction === "keep" ? root._primary : root._border
                                    border.width: 1
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 7
                                        height: 7
                                        radius: 4
                                        color: root._primary
                                        visible: reverseDialog.pdfAction === "keep"
                                    }
                                }
                                Text {
                                    text: "Keep PDF in its current folder"
                                    font.pixelSize: 14
                                    color: root._text
                                    Layout.fillWidth: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !reverseDialog.operationInProgress
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: reverseDialog.pdfAction = "keep"
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            color: reverseDialog.pdfAction === "move" ? SemanticTheme.alpha(root._primary, 0.10) : "transparent"
                            border.color: reverseDialog.pdfAction === "move" ? root._primary : root._border
                            border.width: 1
                            radius: visualRules.isPro ? visualRules.radiusControl : 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    Layout.preferredWidth: 15
                                    Layout.preferredHeight: 15
                                    radius: 8
                                    color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : root._bg
                                    border.color: reverseDialog.pdfAction === "move" ? root._primary : root._border
                                    border.width: 1
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 7
                                        height: 7
                                        radius: 4
                                        color: root._primary
                                        visible: reverseDialog.pdfAction === "move"
                                    }
                                }
                                Text {
                                    text: "Move selected PDF to a REVERSED folder"
                                    font.pixelSize: 14
                                    color: root._text
                                    Layout.fillWidth: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !reverseDialog.operationInProgress
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: reverseDialog.pdfAction = "move"
                            }
                        }

                        RowLayout {
                            spacing: 8
                            Layout.leftMargin: 36
                            Layout.fillWidth: true
                            visible: reverseDialog.pdfAction === "move"

                            Text { text: "PDF:"; font.pixelSize: 13; color: root._text; Layout.alignment: Qt.AlignVCenter }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
                                border.color: root._border
                                border.width: 1
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    text: reverseDialog.sourcePdfPath !== "" ? reverseDialog.sourcePdfPath : "Select PDF file..."
                                    color: reverseDialog.sourcePdfPath !== "" ? root._text : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle))
                                    font.pixelSize: 13
                                    elide: Text.ElideMiddle
                                    width: parent.width - 16
                                }
                            }
                            Rectangle {
                                Layout.preferredWidth: 80
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._border
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text { anchors.centerIn: parent; text: "Browse"; font.pixelSize: 13; color: root._text }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sourcePdfDialog.open() }
                            }
                        }

                        RowLayout {
                            spacing: 8
                            visible: reverseDialog.pdfAction === "move"
                            Layout.leftMargin: 36
                            Layout.fillWidth: true

                            Text { text: "Folder:"; font.pixelSize: 13; color: root._text; Layout.alignment: Qt.AlignVCenter }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
                                border.color: root._border
                                border.width: 1
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    text: reverseDialog.targetDir !== "" ? reverseDialog.targetDir : "Default: REVERSED next to the PDF"
                                    color: reverseDialog.targetDir !== "" ? root._text : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle))
                                    font.pixelSize: 13
                                    elide: Text.ElideMiddle
                                    width: parent.width - 16
                                }
                            }
                            Rectangle {
                                Layout.preferredWidth: 80
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._border
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text { anchors.centerIn: parent; text: "Browse"; font.pixelSize: 13; color: root._text }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: targetFolderDialog.open() }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            color: reverseDialog.pdfAction === "delete" ? SemanticTheme.alpha(root._danger, 0.10) : "transparent"
                            border.color: reverseDialog.pdfAction === "delete" ? root._danger : root._border
                            border.width: 1
                            radius: visualRules.isPro ? visualRules.radiusControl : 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    Layout.preferredWidth: 15
                                    Layout.preferredHeight: 15
                                    radius: 8
                                    color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : root._bg
                                    border.color: reverseDialog.pdfAction === "delete" ? root._danger : root._border
                                    border.width: 1
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 7
                                        height: 7
                                        radius: 4
                                        color: root._danger
                                        visible: reverseDialog.pdfAction === "delete"
                                    }
                                }
                                Text {
                                    text: "Delete selected PDF permanently"
                                    font.pixelSize: 14
                                    color: root._text
                                    Layout.fillWidth: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !reverseDialog.operationInProgress
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: reverseDialog.pdfAction = "delete"
                            }
                        }

                        RowLayout {
                            spacing: 8
                            Layout.leftMargin: 36
                            Layout.fillWidth: true
                            visible: reverseDialog.pdfAction === "delete"

                            Text { text: "PDF:"; font.pixelSize: 13; color: root._text; Layout.alignment: Qt.AlignVCenter }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
                                border.color: root._border
                                border.width: 1
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    text: reverseDialog.sourcePdfPath !== "" ? reverseDialog.sourcePdfPath : "Select PDF file..."
                                    color: reverseDialog.sourcePdfPath !== "" ? root._text : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle))
                                    font.pixelSize: 13
                                    elide: Text.ElideMiddle
                                    width: parent.width - 16
                                }
                            }
                            Rectangle {
                                Layout.preferredWidth: 80
                                Layout.preferredHeight: 36
                                color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._border
                                radius: visualRules.isPro ? visualRules.radiusControl : 4
                                Text { anchors.centerIn: parent; text: "Browse"; font.pixelSize: 13; color: root._text }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sourcePdfDialog.open() }
                            }
                        }

                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: root._border
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: reverseDialog.operationInProgress
                    spacing: 8

                    BusyIndicator {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        running: reverseDialog.operationInProgress
                    }
                    Text {
                        text: "Working safely... CSPM is preparing the correction. This can take a moment; keep this window open."
                        color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                        font.pixelSize: 13
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        Layout.preferredWidth: 96
                        Layout.minimumWidth: 84
                        Layout.preferredHeight: 36
                        color: "transparent"
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Cancel"; color: root._text; font.pixelSize: 14 }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !reverseDialog.operationInProgress
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: reverseDialog.visible = false
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 154
                        Layout.minimumWidth: 126
                        Layout.preferredHeight: 36
                        color: root._primary
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Correct & Reissue"; color: root.isProMode ? SemanticTheme.readableInk(root._primary) : SemanticTheme.surfacePanel(root.t, root.appStyle); font.pixelSize: 14; font.weight: Font.Medium }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !reverseDialog.operationInProgress
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (root.billingBackend) {
                                    reverseDialog.operationInProgress = true
                                    root.billingBackend.correctAndReissueInvoice(root.selectedInvoiceNum, reverseDialog.sourcePdfPath, reverseDialog.pdfAction, reverseDialog.targetDir)
                                }
                            }
                        }
                    }
                    Rectangle {
                        Layout.preferredWidth: 116
                        Layout.minimumWidth: 96
                        Layout.preferredHeight: 36
                        color: root._danger
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Reverse Only"; color: root.isProMode ? SemanticTheme.readableInk(root._danger) : SemanticTheme.surfacePanel(root.t, root.appStyle); font.pixelSize: 14; font.weight: Font.Medium }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !reverseDialog.operationInProgress
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (root.billingBackend) {
                                    reverseDialog.operationInProgress = true
                                    root.billingBackend.reverseInvoice(root.selectedInvoiceNum, reverseDialog.sourcePdfPath, reverseDialog.pdfAction, reverseDialog.targetDir)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    FolderDialog {
        id: targetFolderDialog
        title: "Select Archive Folder"
        onAccepted: {
            var p = targetFolderDialog.folder.toString()
            if (p.indexOf("file:///") === 0) {
                p = p.substring(8)
            }
            reverseDialog.targetDir = decodeURIComponent(p)
        }
    }
    
    FileDialog {
        id: sourcePdfDialog
        title: "Select Finalized Invoice PDF"
        nameFilters: ["PDF Files (*.pdf)", "All Files (*)"]
        onAccepted: {
            var p = sourcePdfDialog.file.toString()
            if (p.indexOf("file:///") === 0) {
                p = p.substring(8)
            }
            reverseDialog.sourcePdfPath = decodeURIComponent(p)
        }
    }
}
