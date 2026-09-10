pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: dialog

    property var host
    property var t
    property var metrics
    property var appRef
    property var sfxBus
    property string appStyle: (host && host.appStyle) ? String(host.appStyle) : "Professional"
    property bool isProMode: appStyle === "Professional"
    property bool postInProgress: false
    property bool resultOk: true
    property string resultMessage: ""
    property var billingClientOptions: []
    property var allocationRows: []
    property string invoiceFilterText: ""
    property int allocationRevision: 0
    property var filteredAllocationRows: dialog._filteredAllocationRows()
    property var methodOptions: ["e-Transfer", "EFT", "Cheque", "Credit Card", "Cash", "Wire", "Other"]
    property var depositAccountOptions: host ? host.depositAccountOptions : []
    property string selectedBillingClient: ""

    signal postRequested(var payload)

    modal: true
    focus: true
    dim: true
    closePolicy: postInProgress ? Popup.NoAutoClose : Popup.CloseOnEscape
    anchors.centerIn: parent
    padding: 0
    width: Math.max(860, Math.min(1180, (parent ? parent.width : 1240) - 28))
    height: Math.max(620, Math.min(860, (parent ? parent.height : 900) - 28))

    VisualRules {
        id: visualRules
        appStyle: dialog.appStyle
    }

    property color _accent: SemanticTheme.accentPrimary(dialog.t, dialog.appStyle)
    property color _text: SemanticTheme.inkPrimary(dialog.t, dialog.appStyle)
    property color _mutedText: SemanticTheme.inkMuted(dialog.t, dialog.appStyle)
    property color _panel: SemanticTheme.surfacePanel(dialog.t, dialog.appStyle)
    property color _raisedPanel: SemanticTheme.surfaceRaised(dialog.t, dialog.appStyle)
    property color _input: SemanticTheme.surfaceInput(dialog.t, dialog.appStyle)
    property color _border: SemanticTheme.borderSubtle(dialog.t, dialog.appStyle)
    property int fieldHeightPx: host ? host.fieldHeightPx : 42

    function _clean(value) {
        return String(value === undefined || value === null ? "" : value).trim()
    }

    function _num(value, fallback) {
        var n = parseFloat(_clean(value).replace(/[$,]/g, ""))
        return isFinite(n) ? n : fallback
    }

    function _roundMoney(value) {
        return Math.round((Number(value || 0) + Number.EPSILON) * 100) / 100
    }

    function money(value) {
        var n = Number(value || 0)
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function refreshBillingClientOptions() {
        var source = (host && host.partyUniverseRows) ? host.partyUniverseRows : []
        var seen = ({})
        var options = []
        for (var i = 0; i < source.length; i++) {
            var value = _clean(source[i] && (source[i].billingClient || source[i].client))
            var key = value.toLowerCase()
            if (value.length <= 0 || seen[key]) continue
            seen[key] = true
            options.push(value)
        }
        options.sort(function(a, b) { return String(a).localeCompare(String(b)) })
        billingClientOptions = options
    }

    function loadBillingClient(clientName) {
        var client = _clean(clientName)
        selectedBillingClient = client
        billingClientCombo.editText = client
        resultMessage = ""
        if (!client || !appRef || !appRef.listOpenPaymentInvoices) {
            allocationRows = []
            return
        }
        var raw = []
        try {
            raw = appRef.listOpenPaymentInvoices({
                "partyType": "Billing client",
                "partyValue": client
            })
        } catch (e) {
            resultOk = false
            resultMessage = String(e)
            allocationRows = []
            return
        }
        var rows = []
        for (var i = 0; i < raw.length; i++) {
            var item = raw[i] || ({})
            rows.push({
                "invoice": _clean(item.invoice),
                "date": _clean(item.date),
                "ageDays": Number(item.ageDays || 0),
                "client": _clean(item.client || item.workClient),
                "matter": _clean(item.matter || item.matterDescription),
                "balance": _roundMoney(item.balance),
                "allocation": ""
            })
        }
        rows.sort(function(a, b) {
            if (a.date < b.date) return -1
            if (a.date > b.date) return 1
            return a.invoice.localeCompare(b.invoice)
        })
        for (var j = 0; j < rows.length; j++) rows[j].sourceIndex = j
        allocationRows = rows
        allocationRevision += 1
    }

    function openForBillingClient(clientName) {
        refreshBillingClientOptions()
        postInProgress = false
        resultOk = true
        resultMessage = ""
        dateInput.text = host ? host._todayIso() : Qt.formatDate(new Date(), "yyyy-MM-dd")
        amountInput.text = ""
        methodCombo.editText = "EFT"
        var accountValue = host ? host._displayForDepositAccount(host.depositAccountCode) : ""
        depositAccountCombo.editText = accountValue
        referenceInput.text = ""
        notesInput.text = ""
        invoiceFilterText = ""
        invoiceFilterInput.text = ""
        loadBillingClient(_clean(clientName))
        open()
        Qt.callLater(function() {
            if (!dialog.visible) return
            if (dialog.selectedBillingClient.length > 0) amountInput.forceActiveFocus()
            else billingClientCombo.forceActiveFocus()
        })
    }

    function allocationAmount(index) {
        var revision = allocationRevision
        var row = allocationRows[index] || ({})
        return Math.max(0, _num(row.allocation, 0))
    }

    function setAllocation(index, value) {
        if (index < 0 || index >= allocationRows.length) return
        // Do not replace allocationRows while the user types. Replacing the
        // ListView model destroys its delegates, which used to drop focus
        // after every character and make the row jump out of view.
        allocationRows[index].allocation = _clean(value)
        allocationRevision += 1
        resultMessage = ""
    }

    function _rowMatchesFilter(row) {
        var query = _clean(invoiceFilterText).toLowerCase()
        if (!query) return true
        var haystack = [
            _clean(row && row.invoice),
            _clean(row && row.client),
            _clean(row && row.matter),
            _clean(row && row.date)
        ].join(" | ").toLowerCase()
        return haystack.indexOf(query) >= 0
    }

    function _filteredAllocationRows() {
        var rows = []
        var source = allocationRows || []
        for (var i = 0; i < source.length; i++) {
            if (_rowMatchesFilter(source[i])) rows.push(source[i])
        }
        return rows
    }

    function setInvoiceFilter(value) {
        invoiceFilterText = _clean(value)
    }

    function totalOutstanding() {
        var total = 0
        for (var i = 0; i < allocationRows.length; i++) total += Number(allocationRows[i].balance || 0)
        return _roundMoney(total)
    }

    function totalAllocated() {
        var revision = allocationRevision
        var total = 0
        for (var i = 0; i < allocationRows.length; i++) total += allocationAmount(i)
        return _roundMoney(total)
    }

    function positiveAllocationCount() {
        var revision = allocationRevision
        var count = 0
        for (var i = 0; i < allocationRows.length; i++) {
            if (allocationAmount(i) > 0) count += 1
        }
        return count
    }

    function filteredOutstanding() {
        var total = 0
        var rows = filteredAllocationRows || []
        for (var i = 0; i < rows.length; i++) total += Number(rows[i].balance || 0)
        return _roundMoney(total)
    }

    function amountReceived() {
        return _roundMoney(Math.max(0, _num(amountInput.text, 0)))
    }

    function unallocatedAmount() {
        return _roundMoney(amountReceived() - totalAllocated())
    }

    function allocateOldestFirst() {
        var remaining = amountReceived()
        if (remaining <= 0) {
            showValidationError("Enter the amount received before allocating it.")
            return
        }
        var rows = []
        var shownCount = 0
        for (var i = 0; i < allocationRows.length; i++) {
            var copy = Object.assign({}, allocationRows[i])
            var isShown = _rowMatchesFilter(copy)
            var applied = isShown
                ? Math.min(Number(copy.balance || 0), Math.max(0, remaining))
                : 0
            if (isShown) shownCount += 1
            copy.allocation = applied > 0 ? _roundMoney(applied).toFixed(2) : ""
            remaining = _roundMoney(remaining - applied)
            rows.push(copy)
        }
        if (shownCount <= 0) {
            showValidationError("No invoices match the current filter.")
            return
        }
        allocationRows = rows
        allocationRevision += 1
        resultMessage = remaining > 0.005
            ? "The receipt exceeds this billing client's open A/R by " + money(remaining) + "."
            : ""
        resultOk = remaining <= 0.005
    }

    function clearAllocations() {
        var rows = []
        for (var i = 0; i < allocationRows.length; i++) {
            var copy = Object.assign({}, allocationRows[i])
            copy.allocation = ""
            rows.push(copy)
        }
        allocationRows = rows
        allocationRevision += 1
        resultMessage = ""
    }

    function buildPayload() {
        var allocations = []
        for (var i = 0; i < allocationRows.length; i++) {
            var amount = allocationAmount(i)
            if (amount > 0) allocations.push({
                "invoice": allocationRows[i].invoice,
                "amount": _roundMoney(amount)
            })
        }
        var depositValue = _clean(depositAccountCombo.editText)
        return {
            "billingClient": selectedBillingClient,
            "date": _clean(dateInput.text),
            "totalAmount": amountReceived(),
            "method": _clean(methodCombo.editText),
            "depositAccount": host ? host._depositAccountCodeForDisplay(depositValue) : depositValue,
            "reference": _clean(referenceInput.text),
            "notes": _clean(notesInput.text),
            "allocations": allocations
        }
    }

    function validatePayload(payload) {
        if (!_clean(payload.billingClient)) return "Select a billing client."
        if (!_clean(payload.date).match(/^\d{4}-\d{2}-\d{2}$/)) return "Date must be in YYYY-MM-DD format."
        if (Number(payload.totalAmount || 0) <= 0) return "Amount received must be greater than 0."
        if (!_clean(payload.method)) return "Payment method is required."
        if (!_clean(payload.depositAccount)) return "Select the general account receiving this payment."
        if (!payload.allocations || payload.allocations.length <= 0) return "Allocate the receipt to at least one invoice."
        for (var i = 0; i < allocationRows.length; i++) {
            var allocation = allocationAmount(i)
            var balance = Number(allocationRows[i].balance || 0)
            if (allocation - balance > 0.005)
                return "Allocation for invoice " + allocationRows[i].invoice + " exceeds its open balance."
        }
        if (Math.abs(Number(payload.totalAmount || 0) - totalAllocated()) > 0.005)
            return "Allocated total must exactly equal the amount received."
        return ""
    }

    function requestPost() {
        if (postInProgress) return
        var payload = buildPayload()
        var validation = validatePayload(payload)
        if (validation.length > 0) {
            showValidationError(validation)
            return
        }
        postRequested(payload)
    }

    function showValidationError(message) {
        resultOk = false
        resultMessage = _clean(message)
    }

    function beginPost() {
        resultOk = true
        resultMessage = ""
        postInProgress = true
    }

    function finishPost(ok, message, result) {
        postInProgress = false
        resultOk = !!ok
        resultMessage = _clean(message) || (resultOk ? "Receipt posted." : "Receipt posting failed.")
        if (!resultOk) return
        amountInput.text = ""
        referenceInput.text = ""
        notesInput.text = ""
        loadBillingClient(selectedBillingClient)
        resultOk = true
        resultMessage = _clean(message)
    }

    background: Rectangle {
        color: dialog._raisedPanel
        border.width: 1
        border.color: dialog._border
        radius: dialog.isProMode ? visualRules.radiusPopup : 12
    }

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 66
            color: dialog._panel
            radius: dialog.isProMode ? visualRules.radiusPopup : 12

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 14
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: "Billing Client A/R Collection"
                        color: dialog._text
                        font.family: "Segoe UI"
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Record one received payment and allocate it across the billing client's invoices."
                        color: dialog._mutedText
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }

                PillButton {
                    text: "Close"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    enabled: !dialog.postInProgress
                    Layout.preferredWidth: 84
                    Layout.preferredHeight: 36
                    onClicked: dialog.close()
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.topMargin: 12
            Layout.bottomMargin: 12
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                color: SemanticTheme.alpha(SemanticTheme.tone(dialog.t, "warning", dialog.appStyle), 0.10)
                border.width: 1
                border.color: SemanticTheme.tone(dialog.t, "warning", dialog.appStyle)
                radius: 4
                Text {
                    anchors.fill: parent
                    anchors.margins: 9
                    text: "General account only — trust receipts and trust-to-general transfers are not implemented in this workflow."
                    color: SemanticTheme.tone(dialog.t, "warning", dialog.appStyle)
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: dialog.width >= 1040 ? 4 : 2
                columnSpacing: 9
                rowSpacing: 8

                ModernComboBox {
                    id: billingClientCombo
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Billing client"
                    fullModel: dialog.billingClientOptions
                    preserveUnknownEditTextOnModelChanged: true
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                    onActivated: dialog.loadBillingClient(editText)
                }
                ModernTextField {
                    id: dateInput
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Date received"
                    datePickerEnabled: true
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                }
                ModernTextField {
                    id: amountInput
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Amount received ($)"
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                    onTextEdited: dialog.resultMessage = ""
                }
                ModernComboBox {
                    id: methodCombo
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Payment method"
                    fullModel: dialog.methodOptions
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                }
                ModernComboBox {
                    id: depositAccountCombo
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "General deposit account"
                    fullModel: dialog.depositAccountOptions
                    preserveUnknownEditTextOnModelChanged: true
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                }
                ModernTextField {
                    id: referenceInput
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Reference / Cheque #"
                    enabled: !dialog.postInProgress
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                }
                TextArea {
                    id: notesInput
                    Layout.columnSpan: dialog.width >= 1040 ? 2 : 1
                    Layout.fillWidth: true
                    Layout.preferredHeight: dialog.fieldHeightPx
                    enabled: !dialog.postInProgress
                    color: dialog._text
                    placeholderText: "Receipt notes"
                    placeholderTextColor: dialog._mutedText
                    wrapMode: Text.Wrap
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    background: Rectangle {
                        color: dialog._input
                        radius: dialog.isProMode ? 4 : 9
                        border.width: notesInput.activeFocus ? 2 : 1
                        border.color: notesInput.activeFocus ? dialog._accent : dialog._border
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: dialog.selectedBillingClient
                        ? (dialog.filteredAllocationRows.length + " of " + dialog.allocationRows.length
                            + " open invoices · Shown A/R " + dialog.money(dialog.filteredOutstanding()))
                        : "Select a billing client to load open A/R."
                    color: dialog._text
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                ModernTextField {
                    id: invoiceFilterInput
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    label: "Filter invoice, client or matter"
                    enabled: !dialog.postInProgress && dialog.allocationRows.length > 0
                    Layout.preferredWidth: 260
                    Layout.preferredHeight: 36
                    onTextEdited: dialog.setInvoiceFilter(text)
                }
                PillButton {
                    text: dialog.invoiceFilterText ? "Allocate shown oldest first" : "Allocate oldest first"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    primary: true
                    enabled: !dialog.postInProgress && dialog.filteredAllocationRows.length > 0
                    Layout.preferredWidth: dialog.invoiceFilterText ? 196 : 164
                    Layout.preferredHeight: 34
                    onClicked: dialog.allocateOldestFirst()
                }
                PillButton {
                    text: "Clear allocations"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    enabled: !dialog.postInProgress && dialog.allocationRows.length > 0
                    Layout.preferredWidth: 138
                    Layout.preferredHeight: 34
                    onClicked: dialog.clearAllocations()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: dialog._panel
                border.width: 1
                border.color: dialog._border
                radius: dialog.isProMode ? 4 : 9
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        color: SemanticTheme.hoverOverlay(dialog.t, dialog.appStyle)
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8
                            Text { Layout.preferredWidth: 94; text: "Invoice"; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text { Layout.preferredWidth: 82; text: "Date / Age"; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text { Layout.fillWidth: true; text: "Work client / Matter"; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text { Layout.preferredWidth: 96; text: "Balance"; horizontalAlignment: Text.AlignRight; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text { Layout.preferredWidth: 124; text: "Apply ($)"; horizontalAlignment: Text.AlignRight; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text { Layout.preferredWidth: 104; text: "After"; horizontalAlignment: Text.AlignRight; color: dialog._mutedText; font.pixelSize: 11; font.weight: Font.DemiBold }
                        }
                    }

                    ListView {
                        id: allocationList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: dialog.filteredAllocationRows
                        spacing: 3
                        delegate: Rectangle {
                            id: allocationDelegate
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            height: 48
                            color: index % 2 === 0 ? dialog._input : dialog._panel
                            border.width: 0

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8
                                Text { Layout.preferredWidth: 94; text: dialog._clean(allocationDelegate.modelData.invoice); color: dialog._text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Text { Layout.preferredWidth: 82; text: dialog._clean(allocationDelegate.modelData.date) + "\n" + Number(allocationDelegate.modelData.ageDays || 0) + " days"; color: dialog._mutedText; font.pixelSize: 10; elide: Text.ElideRight }
                                Text { Layout.fillWidth: true; text: dialog._clean(allocationDelegate.modelData.client) + (dialog._clean(allocationDelegate.modelData.matter) ? " · " + dialog._clean(allocationDelegate.modelData.matter) : ""); color: dialog._text; font.pixelSize: 11; elide: Text.ElideRight }
                                Text { Layout.preferredWidth: 96; text: dialog.money(allocationDelegate.modelData.balance); horizontalAlignment: Text.AlignRight; color: dialog._text; font.pixelSize: 12; font.weight: Font.DemiBold }
                                TextField {
                                    id: allocationInput
                                    Layout.preferredWidth: 124
                                    Layout.preferredHeight: 34
                                    text: dialog._clean(allocationDelegate.modelData.allocation)
                                    enabled: !dialog.postInProgress
                                    horizontalAlignment: Text.AlignRight
                                    selectByMouse: true
                                    color: dialog._text
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                    validator: DoubleValidator { bottom: 0; decimals: 2 }
                                    activeFocusOnTab: true
                                    onActiveFocusChanged: {
                                        if (!activeFocus) return
                                        allocationList.currentIndex = allocationDelegate.index
                                        allocationList.positionViewAtIndex(allocationDelegate.index, ListView.Contain)
                                    }
                                    onTextEdited: {
                                        allocationList.currentIndex = allocationDelegate.index
                                        dialog.setAllocation(allocationDelegate.modelData.sourceIndex, text)
                                        allocationList.positionViewAtIndex(allocationDelegate.index, ListView.Contain)
                                    }
                                    background: Rectangle {
                                        color: dialog._raisedPanel
                                        radius: dialog.isProMode ? 3 : 7
                                        border.width: parent.activeFocus ? 2 : 1
                                        border.color: parent.activeFocus ? dialog._accent : dialog._border
                                    }
                                }
                                Text {
                                    Layout.preferredWidth: 104
                                    text: dialog.money(Math.max(0, Number(allocationDelegate.modelData.balance || 0) - dialog.allocationAmount(allocationDelegate.modelData.sourceIndex)))
                                    horizontalAlignment: Text.AlignRight
                                    color: dialog._accent
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: dialog.selectedBillingClient.length > 0 && dialog.filteredAllocationRows.length <= 0
                    text: dialog.invoiceFilterText
                        ? "No open invoices match “" + dialog.invoiceFilterText + "”."
                        : "This billing client has no open invoices."
                    color: dialog._mutedText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                spacing: 10
                Repeater {
                    model: [
                        { "label": "Received", "value": dialog.amountReceived(), "tone": "neutral" },
                        { "label": "Allocated", "value": dialog.totalAllocated(), "tone": "neutral" },
                        { "label": "Unallocated", "value": dialog.unallocatedAmount(), "tone": Math.abs(dialog.unallocatedAmount()) <= 0.005 ? "success" : "warning" }
                    ]
                    delegate: Rectangle {
                        id: summaryDelegate
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        color: SemanticTheme.hoverOverlay(dialog.t, dialog.appStyle)
                        border.width: 1
                        border.color: summaryDelegate.modelData.tone === "neutral" ? dialog._border : SemanticTheme.tone(dialog.t, summaryDelegate.modelData.tone, dialog.appStyle)
                        radius: 4
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 9
                            Text { Layout.fillWidth: true; text: summaryDelegate.modelData.label; color: dialog._mutedText; font.pixelSize: 11 }
                            Text { text: dialog.money(summaryDelegate.modelData.value); color: summaryDelegate.modelData.tone === "neutral" ? dialog._text : SemanticTheme.tone(dialog.t, summaryDelegate.modelData.tone, dialog.appStyle); font.pixelSize: 13; font.weight: Font.DemiBold }
                        }
                    }
                }
            }

            Rectangle {
                visible: dialog.resultMessage.length > 0
                Layout.fillWidth: true
                Layout.preferredHeight: resultText.implicitHeight + 16
                color: SemanticTheme.alpha(
                    SemanticTheme.tone(dialog.t, dialog.resultOk ? "success" : "error", dialog.appStyle),
                    0.12
                )
                border.width: 1
                border.color: SemanticTheme.tone(dialog.t, dialog.resultOk ? "success" : "error", dialog.appStyle)
                radius: 4
                Text {
                    id: resultText
                    anchors.fill: parent
                    anchors.margins: 8
                    text: dialog.resultMessage
                    color: SemanticTheme.tone(dialog.t, dialog.resultOk ? "success" : "error", dialog.appStyle)
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: dialog._panel

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    text: "Posting creates one receipt transaction and " + dialog.positiveAllocationCount() + " invoice allocation record(s)."
                    color: dialog._mutedText
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
                PillButton {
                    text: "Cancel"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    enabled: !dialog.postInProgress
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 40
                    onClicked: dialog.close()
                }
                PillButton {
                    text: dialog.postInProgress ? "Posting..." : "Post Received Payment"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    primary: true
                    enabled: !dialog.postInProgress
                    Layout.preferredWidth: 190
                    Layout.preferredHeight: 40
                    onClicked: dialog.requestPost()
                }
            }
        }
    }
}
