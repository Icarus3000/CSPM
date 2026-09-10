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
    property var invoiceRow: ({})
    property bool postInProgress: false
    property bool resultOk: true
    property string resultMessage: ""
    property var modeOptions: ["Payment", "Write-off / Adjustment"]
    property var methodOptions: ["e-Transfer", "EFT", "Cheque", "Credit Card", "Cash", "Wire", "Other"]
    property var depositAccountOptions: host ? host.depositAccountOptions : []

    signal postRequested(var payload)

    modal: true
    focus: true
    dim: true
    closePolicy: postInProgress ? Popup.NoAutoClose : Popup.CloseOnEscape
    anchors.centerIn: parent
    padding: 0
    width: Math.max(680, Math.min(920, (parent ? parent.width : 960) - 32))
    height: Math.max(560, Math.min(760, (parent ? parent.height : 800) - 32))

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

    function money(value) {
        var n = Number(value || 0)
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function invoiceValue(key, fallback) {
        var value = invoiceRow ? invoiceRow[key] : undefined
        return value === undefined || value === null ? (fallback || "") : value
    }

    function projectedBalance() {
        return Math.max(0, Number(invoiceValue("balance", 0) || 0)
            - _num(amountInput.text, 0)
            - _num(adjustmentAmountInput.text, 0))
    }

    function openForInvoice(row) {
        invoiceRow = row || ({})
        postInProgress = false
        resultOk = true
        resultMessage = ""
        dateInput.text = host ? host._todayIso() : Qt.formatDate(new Date(), "yyyy-MM-dd")
        amountInput.text = Number(invoiceValue("balance", 0) || 0).toFixed(2)
        adjustmentAmountInput.text = ""
        adjustmentReasonInput.text = ""
        modeCombo.editText = "Payment"
        methodCombo.editText = "EFT"
        var accountValue = host ? host._displayForDepositAccount(host.depositAccountCode) : ""
        depositAccountCombo.editText = accountValue
        referenceInput.text = ""
        notesInput.text = ""
        open()
        Qt.callLater(function() {
            if (dialog.visible) amountInput.forceActiveFocus()
        })
    }

    function buildPayload() {
        var depositValue = _clean(depositAccountCombo.editText)
        return {
            "invoice": _clean(invoiceValue("invoice", "")),
            "date": _clean(dateInput.text),
            "mode": _clean(modeCombo.editText),
            "method": _clean(methodCombo.editText),
            "depositAccount": host ? host._depositAccountCodeForDisplay(depositValue) : depositValue,
            "reference": _clean(referenceInput.text),
            "amount": _num(amountInput.text, 0.0),
            "adjustmentAmount": _num(adjustmentAmountInput.text, 0.0),
            "adjustmentReason": _clean(adjustmentReasonInput.text),
            "notes": _clean(notesInput.text)
        }
    }

    function requestPost() {
        if (postInProgress) return
        resultMessage = ""
        postRequested(buildPayload())
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

    function finishPost(ok, message) {
        postInProgress = false
        resultOk = !!ok
        resultMessage = _clean(message) || (resultOk ? "Payment posted." : "Payment posting failed.")
        if (resultOk) close()
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
            Layout.preferredHeight: 62
            color: dialog._panel
            radius: dialog.isProMode ? visualRules.radiusPopup : 12
            border.width: 0

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
                        text: "Record Payment"
                        color: dialog._text
                        font.family: "Segoe UI"
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Invoice " + dialog._clean(dialog.invoiceValue("invoice", ""))
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

        ScrollView {
            id: formScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                width: formScroll.availableWidth
                spacing: 12

                Item { Layout.preferredHeight: 4 }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    columns: dialog.width >= 820 ? 4 : 2
                    columnSpacing: 8
                    rowSpacing: 8

                    Repeater {
                        model: [
                            { "label": "Invoice", "value": dialog.invoiceValue("invoice", "") },
                            { "label": "Client", "value": dialog.invoiceValue("client", dialog.invoiceValue("workClient", "")) },
                            { "label": "Billing client", "value": dialog.invoiceValue("billingClient", "") },
                            { "label": "Matter", "value": dialog.invoiceValue("matter", dialog.invoiceValue("matterDescription", "")) },
                            { "label": "Invoice total", "value": dialog.money(dialog.invoiceValue("invoiceTotal", 0)) },
                            { "label": "Paid / credits", "value": dialog.money(Number(dialog.invoiceValue("paid", 0) || 0) + Number(dialog.invoiceValue("credits", 0) || 0)) },
                            { "label": "Balance due", "value": dialog.money(dialog.invoiceValue("balance", 0)) },
                            { "label": "Status", "value": dialog.invoiceValue("status", "") }
                        ]

                        delegate: Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            color: dialog._input
                            border.width: 1
                            border.color: dialog._border
                            radius: dialog.isProMode ? 4 : 9

                            Column {
                                anchors.fill: parent
                                anchors.margins: 6
                                spacing: 2
                                Text {
                                    width: parent.width
                                    text: modelData.label
                                    color: dialog._mutedText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: dialog._clean(modelData.value)
                                    color: dialog._text
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    columns: dialog.width >= 760 ? 2 : 1
                    columnSpacing: 10
                    rowSpacing: 8

                    ModernTextField {
                        id: dateInput
                        t: dialog.t
                        metrics: dialog.metrics
                        appStyle: dialog.appStyle
                        label: "Date"
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
                        label: "Payment ($)"
                        enabled: !dialog.postInProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: dialog.fieldHeightPx
                    }
                    ModernTextField {
                        id: adjustmentAmountInput
                        t: dialog.t
                        metrics: dialog.metrics
                        appStyle: dialog.appStyle
                        label: "Adjustment ($)"
                        enabled: !dialog.postInProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: dialog.fieldHeightPx
                    }
                    ModernTextField {
                        id: adjustmentReasonInput
                        t: dialog.t
                        metrics: dialog.metrics
                        appStyle: dialog.appStyle
                        label: "Adjustment reason"
                        enabled: !dialog.postInProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: dialog.fieldHeightPx
                    }
                    ModernComboBox {
                        id: modeCombo
                        t: dialog.t
                        metrics: dialog.metrics
                        appStyle: dialog.appStyle
                        label: "Mode"
                        fullModel: dialog.modeOptions
                        enabled: !dialog.postInProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: dialog.fieldHeightPx
                    }
                    ModernComboBox {
                        id: methodCombo
                        t: dialog.t
                        metrics: dialog.metrics
                        appStyle: dialog.appStyle
                        label: "Method"
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
                        label: "Deposit account"
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
                }

                TextArea {
                    id: notesInput
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.preferredHeight: 76
                    enabled: !dialog.postInProgress
                    color: dialog._text
                    placeholderText: "Notes"
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

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.preferredHeight: 44
                    radius: dialog.isProMode ? 4 : 9
                    color: SemanticTheme.hoverOverlay(dialog.t, dialog.appStyle)
                    border.width: 1
                    border.color: dialog._border

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Text {
                            Layout.fillWidth: true
                            text: "Projected balance after posting"
                            color: dialog._text
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                        Text {
                            text: dialog.money(dialog.projectedBalance())
                            color: dialog._accent
                            font.family: "Segoe UI"
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                    }
                }

                Rectangle {
                    visible: dialog.resultMessage.length > 0
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.preferredHeight: resultText.implicitHeight + 18
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
                        anchors.margins: 9
                        text: dialog.resultMessage
                        color: SemanticTheme.tone(dialog.t, dialog.resultOk ? "success" : "error", dialog.appStyle)
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                    }
                }

                Item { Layout.preferredHeight: 6 }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 66
            color: dialog._panel
            border.width: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                spacing: 10

                Text {
                    Layout.fillWidth: true
                    text: dialog.projectedBalance() <= 0.005 ? "This payment will settle the invoice in full." : "A partial balance will remain open."
                    color: dialog._mutedText
                    font.family: "Segoe UI"
                    font.pixelSize: 12
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
                    text: dialog.postInProgress ? "Posting..." : "Post Payment"
                    t: dialog.t
                    metrics: dialog.metrics
                    appStyle: dialog.appStyle
                    primary: true
                    enabled: !dialog.postInProgress
                    Layout.preferredWidth: 150
                    Layout.preferredHeight: 40
                    onClicked: dialog.requestPost()
                }
            }
        }
    }
}
