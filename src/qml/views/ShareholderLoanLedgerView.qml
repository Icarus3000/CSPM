import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards"

Item {
    id: root

    property var t
    property var metrics
    property var appRef
    property var windowRef
    property var sfxBus

    readonly property color _bg: (t && t.bg) ? t.bg : "#0d111a"
    readonly property color _panel: (t && t.panel) ? t.panel : "#161d2a"
    readonly property color _text: (t && t.text) ? t.text : "#e6edf6"
    readonly property color _accent: (t && t.accent) ? t.accent : "#3b82f6"
    readonly property color _border: Qt.rgba(_text.r, _text.g, _text.b, 0.16)
    readonly property color _muted: Qt.rgba(_text.r, _text.g, _text.b, 0.68)

    property var ledgerData: ({})
    property var entriesModel: []
    property string statusMessage: ""
    property bool statusOk: true
    property string activeFormMode: "" // "", "expense", "repayment", "ucc"

    // Expense form fields
    property string expDate: "2026-10-17"
    property string expVendor: ""
    property string expReceiptRef: ""
    property string expCategory: "EXP_OFFICE_SUPPLIES"
    property string expGifiCode: "8810"
    property string expPreTax: "0.00"
    property string expHstItc: "0.00"
    property string expDescription: ""
    property string expNotes: ""

    // Repayment form fields
    property string repDate: "2026-11-15"
    property string repAmount: "0.00"
    property string repBankAccount: "TD_PC_CHQ"
    property string repReference: "E-TRANSFER"
    property string repNotes: "Tax-free return of shareholder advances under ITA s. 15(2)"

    // UCC Rollover form fields
    property string uccDate: "2026-11-01"
    property string uccClassCode: "Class 50"
    property string uccDescription: "Computer Hardware & Practice Peripherals (Nov 1, 2026 Cutover at UCC)"
    property string uccAmount: "0.00"
    property string uccNotes: "Non-T2057 transfer at tax cost (UCC) credited to Shareholder Loan (GIFI 2781)"

    function money(val) {
        var n = Number(val || 0)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function refreshLedger() {
        if (!root.appRef || !root.appRef.getShareholderLoanLedger) return
        var res = root.appRef.getShareholderLoanLedger("PC")
        if (res && res.ok) {
            root.ledgerData = res
            root.entriesModel = res.entries || []
        }
    }

    function submitExpenseForm() {
        if (!root.appRef || !root.appRef.recordPersonalPaidCorporateExpense) return
        var pre = Number(root.expPreTax || 0)
        var hst = Number(root.expHstItc || 0)
        var res = root.appRef.recordPersonalPaidCorporateExpense({
            "entryDate": root.expDate,
            "vendor": root.expVendor,
            "receiptRef": root.expReceiptRef,
            "categoryCode": root.expCategory,
            "gifiCode": root.expGifiCode,
            "preTaxAmount": pre,
            "hstAmount": hst,
            "grossAmount": Number((pre + hst).toFixed(2)),
            "description": root.expDescription,
            "notes": root.expNotes
        })
        if (res && res.ok) {
            root.statusOk = true
            root.statusMessage = "Recorded personal-paid corporate expense. Updated GIFI 2781 balance: " + root.money(res.closingBalance)
            root.activeFormMode = ""
            root.expVendor = ""
            root.expReceiptRef = ""
            root.expPreTax = "0.00"
            root.expHstItc = "0.00"
            root.expDescription = ""
            root.expNotes = ""
            root.refreshLedger()
        } else {
            root.statusOk = false
            root.statusMessage = (res && res.message) ? String(res.message) : "Failed to record expense."
        }
    }

    function submitRepaymentForm() {
        if (!root.appRef || !root.appRef.recordShareholderLoanRepayment) return
        var res = root.appRef.recordShareholderLoanRepayment({
            "entryDate": root.repDate,
            "amount": Number(root.repAmount || 0),
            "bankAccountCode": root.repBankAccount,
            "receiptRef": root.repReference,
            "notes": root.repNotes
        })
        if (res && res.ok) {
            root.statusOk = true
            root.statusMessage = "Recorded tax-free shareholder loan repayment. Updated GIFI 2781 balance: " + root.money(res.closingBalance)
            root.activeFormMode = ""
            root.repAmount = "0.00"
            root.refreshLedger()
        } else {
            root.statusOk = false
            root.statusMessage = (res && res.message) ? String(res.message) : "Failed to record repayment."
        }
    }

    function submitUccForm() {
        if (!root.appRef || !root.appRef.recordEquipmentUccRollover) return
        var res = root.appRef.recordEquipmentUccRollover({
            "transferDate": root.uccDate,
            "classCode": root.uccClassCode,
            "description": root.uccDescription,
            "uccAmount": Number(root.uccAmount || 0),
            "notes": root.uccNotes
        })
        if (res && res.ok) {
            root.statusOk = true
            root.statusMessage = "Recorded Nov 1, 2026 equipment UCC rollover. Updated GIFI 2781 balance: " + root.money(res.closingBalance)
            root.activeFormMode = ""
            root.uccAmount = "0.00"
            root.refreshLedger()
        } else {
            root.statusOk = false
            root.statusMessage = (res && res.message) ? String(res.message) : "Failed to record UCC rollover."
        }
    }

    Component.onCompleted: {
        root.refreshLedger()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // Header Bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 68
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.92)
            border.width: 1
            border.color: root._border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Shareholder Loan Ledger — Due to Shareholder (GIFI 2781)"
                        color: root._text
                        font.pixelSize: 16
                        font.weight: Font.Bold
                    }

                    Text {
                        text: "CORY SCHNEIDER LAW PROFESSIONAL CORPORATION (OCN: 1001781977) · Shareholder: Cory Adam Schneider · Tax-Free Repayment Pool"
                        color: root._muted
                        font.pixelSize: 12
                    }
                }

                Button {
                    text: "+ Personal-Paid Corp Expense"
                    onClicked: root.activeFormMode = (root.activeFormMode === "expense" ? "" : "expense")
                }

                Button {
                    text: "Record Tax-Free Repayment"
                    onClicked: root.activeFormMode = (root.activeFormMode === "repayment" ? "" : "repayment")
                }

                Button {
                    text: "Nov 1 UCC Equipment Rollover"
                    onClicked: root.activeFormMode = (root.activeFormMode === "ucc" ? "" : "ucc")
                }

                Button {
                    text: "Refresh"
                    onClicked: root.refreshLedger()
                }
            }
        }

        // KPI Summary Strip
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: [
                    {
                        "label": "Pre-Tax Corporate Outlays (Sch 125)",
                        "value": root.money(root.ledgerData.totalPreTaxExpenses || 0),
                        "sub": "Deductible on T2 Schedule 125",
                        "highlight": false
                    },
                    {
                        "label": "Claimable PC HST ITCs (Line 106)",
                        "value": root.money(root.ledgerData.totalClaimableHstItc || 0),
                        "sub": "LSO & eligible HST inputs",
                        "highlight": false
                    },
                    {
                        "label": "Share Subscription Set-Off (GIFI 3500)",
                        "value": "-" + root.money(root.ledgerData.totalShareSubscriptionSetoffs || 0),
                        "sub": "100 Class 1 Common Shares (OBCA s. 23(3))",
                        "highlight": false
                    },
                    {
                        "label": "Tax-Free Repayments to Shareholder",
                        "value": "-" + root.money(root.ledgerData.totalRepayments || 0),
                        "sub": "Corporate bank -> Personal",
                        "highlight": false
                    },
                    {
                        "label": "Net GIFI 2781 Balance (Due to Cory)",
                        "value": root.money(root.ledgerData.closingBalance || 0),
                        "sub": "Available for tax-free withdrawal",
                        "highlight": true
                    }
                ]

                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 78
                    radius: 8
                    color: modelData.highlight
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.18)
                        : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.85)
                    border.width: modelData.highlight ? 2 : 1
                    border.color: modelData.highlight ? root._accent : root._border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 2

                        Text {
                            text: String(modelData.label || "")
                            color: root._muted
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: String(modelData.value || "$0.00")
                            color: root._text
                            font.pixelSize: 18
                            font.weight: Font.Bold
                        }

                        Text {
                            text: String(modelData.sub || "")
                            color: root._muted
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // Status Banner
        Rectangle {
            visible: root.statusMessage.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            radius: 6
            color: root.statusOk ? Qt.rgba(0.16, 0.65, 0.35, 0.22) : Qt.rgba(0.85, 0.22, 0.22, 0.22)
            border.width: 1
            border.color: root.statusOk ? "#2ea043" : "#f85149"

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 10
                text: root.statusMessage
                color: root._text
                font.pixelSize: 12
                elide: Text.ElideRight
            }
        }

        // Quick-Entry Drawer (Personal-Paid Corporate Expense)
        Rectangle {
            visible: root.activeFormMode === "expense"
            Layout.fillWidth: true
            Layout.preferredHeight: 165
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: root._accent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "Record Personal-Paid Corporate Expense (Credits GIFI 2781 + Posts T2 Sch 125 Expense)"
                    color: root._text
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 6
                    columnSpacing: 8
                    rowSpacing: 8

                    TextField {
                        placeholderText: "Date (YYYY-MM-DD)"
                        text: root.expDate
                        onTextChanged: root.expDate = text
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "Vendor / Payee"
                        text: root.expVendor
                        onTextChanged: root.expVendor = text
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "Receipt / Order #"
                        text: root.expReceiptRef
                        onTextChanged: root.expReceiptRef = text
                        Layout.fillWidth: true
                    }
                    ComboBox {
                        model: ["EXP_OFFICE_SUPPLIES", "EXP_LSO_FEES", "EXP_SOFTWARE_SUBSCRIPTIONS", "EXP_ACCOUNTING_LEGAL", "GOV_INCORPORATION_FILING", "CORP_ORG_EXPENSE"]
                        onCurrentTextChanged: root.expCategory = currentText
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "Pre-Tax ($)"
                        text: root.expPreTax
                        onTextChanged: root.expPreTax = text
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "HST ITC ($)"
                        text: root.expHstItc
                        onTextChanged: root.expHstItc = text
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    TextField {
                        placeholderText: "Corporate Expense Description"
                        text: root.expDescription
                        onTextChanged: root.expDescription = text
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "Notes"
                        text: root.expNotes
                        onTextChanged: root.expNotes = text
                        Layout.fillWidth: true
                    }
                    Button {
                        text: "Save Expense to Loan"
                        onClicked: root.submitExpenseForm()
                    }
                    Button {
                        text: "Cancel"
                        onClicked: root.activeFormMode = ""
                    }
                }
            }
        }

        // Quick-Entry Drawer (Tax-Free Corporate Repayment)
        Rectangle {
            visible: root.activeFormMode === "repayment"
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: root._accent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "Record Tax-Free Corporate Repayment to Shareholder (Debits GIFI 2781)"
                    color: root._text
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    TextField {
                        placeholderText: "Date (YYYY-MM-DD)"
                        text: root.repDate
                        onTextChanged: root.repDate = text
                        Layout.preferredWidth: 140
                    }
                    TextField {
                        placeholderText: "Repayment Amount ($)"
                        text: root.repAmount
                        onTextChanged: root.repAmount = text
                        Layout.preferredWidth: 150
                    }
                    TextField {
                        placeholderText: "Corporate Bank (TD_PC_CHQ)"
                        text: root.repBankAccount
                        onTextChanged: root.repBankAccount = text
                        Layout.preferredWidth: 160
                    }
                    TextField {
                        placeholderText: "Transfer Ref"
                        text: root.repReference
                        onTextChanged: root.repReference = text
                        Layout.preferredWidth: 150
                    }
                    TextField {
                        placeholderText: "Notes"
                        text: root.repNotes
                        onTextChanged: root.repNotes = text
                        Layout.fillWidth: true
                    }
                    Button {
                        text: "Record Repayment"
                        onClicked: root.submitRepaymentForm()
                    }
                    Button {
                        text: "Cancel"
                        onClicked: root.activeFormMode = ""
                    }
                }
            }
        }

        // Quick-Entry Drawer (Nov 1 Equipment UCC Rollover)
        Rectangle {
            visible: root.activeFormMode === "ucc"
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: root._accent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "Record Nov 1, 2026 Equipment Transfer at Tax Cost (UCC) — Outside Form T2057, Credited to GIFI 2781"
                    color: root._text
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    ComboBox {
                        model: ["Class 50", "Class 8", "Class 10", "Class 12"]
                        onCurrentTextChanged: root.uccClassCode = currentText
                        Layout.preferredWidth: 130
                    }
                    TextField {
                        placeholderText: "Asset Description"
                        text: root.uccDescription
                        onTextChanged: root.uccDescription = text
                        Layout.fillWidth: true
                    }
                    TextField {
                        placeholderText: "Transferred UCC ($)"
                        text: root.uccAmount
                        onTextChanged: root.uccAmount = text
                        Layout.preferredWidth: 150
                    }
                    Button {
                        text: "Record UCC Rollover"
                        onClicked: root.submitUccForm()
                    }
                    Button {
                        text: "Cancel"
                        onClicked: root.activeFormMode = ""
                    }
                }
            }
        }

        // Ledger Table
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.88)
            border.width: 1
            border.color: root._border
            clip: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Table Header
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.08)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8

                        Text { text: "Date"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 86 }
                        Text { text: "Entry ID"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 120 }
                        Text { text: "Vendor / Counterparty"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 170 }
                        Text { text: "Description & Reference"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.fillWidth: true }
                        Text { text: "Pre-Tax"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 85 }
                        Text { text: "HST ITC"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 80 }
                        Text { text: "Loan Delta"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 95 }
                        Text { text: "GIFI 2781 Balance"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 120 }
                    }
                }

                ListView {
                    id: ledgerListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root.entriesModel

                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: ledgerListView.width
                        height: 46
                        color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8

                            Text {
                                text: String(modelData.entryDate || "")
                                color: root._text
                                font.pixelSize: 12
                                Layout.preferredWidth: 86
                            }
                            Text {
                                text: String(modelData.shlEntryId || "")
                                color: root._muted
                                font.pixelSize: 11
                                elide: Text.ElideRight
                                Layout.preferredWidth: 120
                            }
                            Text {
                                text: String(modelData.vendor || "")
                                color: root._text
                                font.pixelSize: 12
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                                Layout.preferredWidth: 170
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    text: String(modelData.description || "")
                                    color: root._text
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: "Ref: " + String(modelData.receiptRef || "—") + " · Category: " + String(modelData.categoryCode || "—")
                                    color: root._muted
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                            Text {
                                text: root.money(modelData.preTaxAmount || 0)
                                color: root._text
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignRight
                                Layout.preferredWidth: 85
                            }
                            Text {
                                text: root.money(modelData.hstAmount || 0)
                                color: Number(modelData.hstAmount || 0) > 0 ? "#3fb950" : root._muted
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignRight
                                Layout.preferredWidth: 80
                            }
                            Text {
                                property real deltaVal: Number(modelData.signedDelta || 0)
                                text: (deltaVal >= 0 ? "+" : "") + root.money(deltaVal)
                                color: deltaVal >= 0 ? "#58a6ff" : "#d29922"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignRight
                                Layout.preferredWidth: 95
                            }
                            Text {
                                text: root.money(modelData.runningLoanBalance || 0)
                                color: root._text
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                horizontalAlignment: Text.AlignRight
                                Layout.preferredWidth: 120
                            }
                        }
                    }
                }
            }
        }
    }
}
