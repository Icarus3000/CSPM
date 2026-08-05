import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: rootPopup
    modal: true
    focus: true
    dim: true
    closePolicy: Popup.CloseOnEscape
    anchors.centerIn: parent
    padding: root.ratioPx(0.010, 10)
    width: Math.max(
        root.ratioPxW(0.34, 360),
        Math.min(root.ratioPxW(0.56, 680), (parent ? parent.width : root.width) - root.ratioPx(0.018, 18))
    )

    property var root: null
    property string invoiceNum: ""
    property string appStyle: (rootPopup.root && rootPopup.root.appStyle) ? String(rootPopup.root.appStyle) : "Professional"
    property bool isProMode: rootPopup.appStyle === "Professional"

    VisualRules {
        id: visualRules
        appStyle: rootPopup.appStyle
    }

    onOpened: {
        _loadReceivable()
    }

    function _loadReceivable() {
        if (!invoiceNum) return
        var res = appController.getReceivable(invoiceNum)
        if (res && res.ok && res.receivable) {
            var rec = res.receivable
            _setTextFieldSilently(clientInput, String(rec.Client || ""))
            _setTextFieldSilently(dateInput, String(rec.Date || ""))
            _setTextFieldSilently(invoiceInput, String(rec.InvoiceNum || ""))
            _setTextFieldSilently(totalInput, String(rec.TotalInvoiced || "0.00"))
            _setTextFieldSilently(amountPaidInput, String(rec.AmountPaid || "0.00"))
            _setTextFieldSilently(creditsAdjInput, String(rec.CreditsAdj || "0.00"))
            statusInput.currentText = String(rec.Status || "")
            _setTextFieldSilently(workClientInput, String(rec.WorkClient || ""))
            saveMsg.text = ""
        } else {
            saveMsg.text = "Failed to load invoice details."
            saveMsg.color = rootPopup.isProMode ? SemanticTheme.tone(rootPopup.root ? rootPopup.root.t : null, "error", rootPopup.appStyle) : SemanticTheme.tone(root.t, "danger")
        }
    }

    function _setTextFieldSilently(fieldRef, textValue) {
        if (!fieldRef) return
        var wasTracking = false
        if (fieldRef.tracking !== undefined) {
            wasTracking = fieldRef.tracking
            fieldRef.tracking = false
        }
        var oldCursor = fieldRef.cursorPosition !== undefined ? fieldRef.cursorPosition : 0
        fieldRef.text = textValue
        if (fieldRef.cursorPosition !== undefined) fieldRef.cursorPosition = oldCursor
        if (wasTracking) fieldRef.tracking = true
    }

    function _saveReceivable() {
        var changes = {
            "client": clientInput.text,
            "date": dateInput.text,
            "invoiceNum": invoiceInput.text,
            "totalInvoiced": parseFloat(totalInput.text) || 0.0,
            "amountPaid": parseFloat(amountPaidInput.text) || 0.0,
            "creditsAdj": parseFloat(creditsAdjInput.text) || 0.0,
            "status": statusInput.currentText,
            "workClient": workClientInput.text
        }
        var res = appController.updateReceivable(invoiceNum, changes)
        if (res && res.ok) {
            saveMsg.text = "Receivable updated successfully."
            saveMsg.color = rootPopup.isProMode ? SemanticTheme.inkMuted(rootPopup.root ? rootPopup.root.t : null, rootPopup.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
            root.refreshGlobalSearchSilent() // optional: refresh search if needed
            invoiceNum = invoiceInput.text // Update primary key if it changed
        } else {
            saveMsg.text = res ? (res.message || "Update failed.") : "Update failed."
            saveMsg.color = rootPopup.isProMode ? SemanticTheme.tone(rootPopup.root ? rootPopup.root.t : null, "error", rootPopup.appStyle) : SemanticTheme.tone(root.t, "danger")
        }
    }

    background: Rectangle {
        color: rootPopup.isProMode ? SemanticTheme.surfaceRaised(rootPopup.root ? rootPopup.root.t : null, rootPopup.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
        border.color: rootPopup.isProMode ? SemanticTheme.borderSubtle(rootPopup.root ? rootPopup.root.t : null, rootPopup.appStyle) : SemanticTheme.borderSubtle(root.t, root.appStyle)
        border.width: 1
        radius: visualRules.isPro ? visualRules.radiusPopup : root.sectionRadiusPx
    }

    ColumnLayout {
        width: parent.width
        spacing: root.ratioPx(root.scaleRatios.gridRowSpacingPct, 12)

        Text {
            Layout.fillWidth: true
            text: "Edit Receivable / Invoice (A/R)"
            color: root._text
            font.pixelSize: Math.round(root.ratioPx(root.scaleRatios.h2FontPct, root.metricFloor("fontFloorLabelPx", 14))) | 0
            font.weight: Font.DemiBold
            bottomPadding: root.ratioPx(root.scaleRatios.gridRowSpacingPct, 8)
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: root.ratioPx(root.scaleRatios.gridRowSpacingPct * 0.8, 8)
            columnSpacing: root.ratioPx(root.scaleRatios.gridColumnSpacingPct, 12)

            Text { text: "Invoice Number"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: invoiceInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Client"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: clientInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Work Client"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: workClientInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Date"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: dateInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Total Invoiced"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: totalInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Amount Paid"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: amountPaidInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Credits / Adj"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            TextField {
                id: creditsAdjInput
                Layout.fillWidth: true
                color: root._text
                font.pixelSize: root.labelFontPx || 14
            }

            Text { text: "Status"; color: root._text; font.pixelSize: root.labelFontPx || 14 }
            ComboBox {
                id: statusInput
                Layout.fillWidth: true
                model: ["Draft", "Final", "Paid", "Written Off"]
                contentItem: Text {
                    text: statusInput.displayText
                    color: root._text
                    font.pixelSize: root.labelFontPx || 14
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Text {
            id: saveMsg
            Layout.fillWidth: true
            text: ""
            color: root._text
            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 12))
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignRight
            spacing: root.ratioPx(0.008, 8)

            Item { Layout.fillWidth: true }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Cancel"
                onClicked: rootPopup.close()
            }

            PillButton {
                t: root.t
                metrics: root.responsiveMetrics
                sfxBus: root.sfxBus
                text: "Save Changes"
                primary: true
                onClicked: _saveReceivable()
            }
        }
    }
}
