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

    property string selectedEntity: "PC"
    property string startDate: "2026-10-17"
    property string endDate: "2026-12-31"
    property string pcHstNumberInput: "Pending CRA BN (Effective Nov 1, 2026)"
    property string confirmationNumber: ""
    property string statusMessage: ""
    property bool statusOk: true
    property var returnData: ({})
    property var salesModel: []
    property var itcModel: []

    function money(val) {
        var n = Number(val || 0)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function selectEntityAndPreset(entityCode, pStart, pEnd) {
        root.selectedEntity = entityCode
        root.startDate = pStart
        root.endDate = pEnd
        root.recalculateReturn()
    }

    function recalculateReturn() {
        if (!root.appRef || !root.appRef.calculateHstReturn) return
        var res = root.appRef.calculateHstReturn(root.selectedEntity, root.startDate, root.endDate, "accrual")
        if (res && res.ok) {
            root.returnData = res
            root.salesModel = res.salesItems || []
            root.itcModel = res.itcItems || []
            if (root.selectedEntity === "PC" && res.hstAccountNumber) {
                root.pcHstNumberInput = String(res.hstAccountNumber)
            }
        }
    }

    function savePcHstNumber() {
        if (!root.appRef || !root.appRef.saveBillingEntity) return
        var res = root.appRef.saveBillingEntity({
            "entityCode": "PC",
            "hstNumber": root.pcHstNumberInput
        })
        if (res && res.ok) {
            root.statusOk = true
            root.statusMessage = "Saved PC CRA RT0001 Account Number: " + root.pcHstNumberInput
            root.recalculateReturn()
        } else {
            root.statusOk = false
            root.statusMessage = "Failed to save PC HST number."
        }
    }

    function saveSnapshot() {
        if (!root.appRef || !root.appRef.saveHstReturnSnapshot) return
        var res = root.appRef.saveHstReturnSnapshot({
            "billerEntity": root.selectedEntity,
            "periodStart": root.startDate,
            "periodEnd": root.endDate,
            "confirmationNum": root.confirmationNumber,
            "status": root.confirmationNumber.length > 0 ? "Filed" : "Draft"
        })
        if (res && res.ok) {
            root.statusOk = true
            root.statusMessage = "Saved HST Return Snapshot for " + root.selectedEntity + " (" + root.startDate + " to " + root.endDate + ")."
            root.recalculateReturn()
        } else {
            root.statusOk = false
            root.statusMessage = (res && res.message) ? String(res.message) : "Failed to save HST snapshot."
        }
    }

    Component.onCompleted: {
        root.recalculateReturn()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // Top Control Bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 108
            radius: 8
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.92)
            border.width: 1
            border.color: root._border

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "Dual HST Return Helper (CRA GST34 / RT0001 Line Worksheet)"
                            color: root._text
                            font.pixelSize: 16
                            font.weight: Font.Bold
                        }

                        Text {
                            text: root.selectedEntity === "PC"
                                ? ("Active Entity: CORY SCHNEIDER LAW PROFESSIONAL CORPORATION (OCN: 1001781977) · RT0001: " + String(root.returnData.hstAccountNumber || root.pcHstNumberInput))
                                : "Active Entity: CORY SCHNEIDER (Sole Proprietorship) · CRA HST: 78621 8222 RT0001"
                            color: root._muted
                            font.pixelSize: 12
                        }
                    }

                    Button {
                        text: "PC Stub (Oct 17 – Dec 31, 2026)"
                        highlighted: root.selectedEntity === "PC"
                        onClicked: root.selectEntityAndPreset("PC", "2026-10-17", "2026-12-31")
                    }

                    Button {
                        text: "Sole Prop 2026 (Jan 1 – Dec 31, 2026)"
                        highlighted: root.selectedEntity === "SOLE_PROP"
                        onClicked: root.selectEntityAndPreset("SOLE_PROP", "2026-01-01", "2026-12-31")
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text { text: "Period Start:"; color: root._muted; font.pixelSize: 12 }
                    TextField {
                        text: root.startDate
                        onTextChanged: root.startDate = text
                        Layout.preferredWidth: 115
                    }

                    Text { text: "Period End:"; color: root._muted; font.pixelSize: 12 }
                    TextField {
                        text: root.endDate
                        onTextChanged: root.endDate = text
                        Layout.preferredWidth: 115
                    }

                    Button {
                        text: "Recalculate Lines"
                        onClicked: root.recalculateReturn()
                    }

                    Item { Layout.preferredWidth: 16 }

                    Text {
                        visible: root.selectedEntity === "PC"
                        text: "PC RT0001 #:"
                        color: root._muted
                        font.pixelSize: 12
                    }
                    TextField {
                        visible: root.selectedEntity === "PC"
                        text: root.pcHstNumberInput
                        onTextChanged: root.pcHstNumberInput = text
                        placeholderText: "Enter PC RT0001 once issued by CRA"
                        Layout.preferredWidth: 230
                    }
                    Button {
                        visible: root.selectedEntity === "PC"
                        text: "Save RT0001"
                        onClicked: root.savePcHstNumber()
                    }

                    Item { Layout.fillWidth: true }

                    TextField {
                        placeholderText: "CRA Conf # (optional)"
                        text: root.confirmationNumber
                        onTextChanged: root.confirmationNumber = text
                        Layout.preferredWidth: 150
                    }
                    Button {
                        text: "Save Filing Snapshot"
                        onClicked: root.saveSnapshot()
                    }
                }
            }
        }

        // Status Banner
        Rectangle {
            visible: root.statusMessage.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            radius: 6
            color: root.statusOk ? Qt.rgba(0.16, 0.65, 0.35, 0.22) : Qt.rgba(0.85, 0.22, 0.22, 0.22)
            border.width: 1
            border.color: root.statusOk ? "#2ea043" : "#f85149"

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.margins: 10
                text: root.statusMessage
                color: root._text
                font.pixelSize: 12
            }
        }

        // CRA Line Cards
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: [
                    {
                        "line": "Line 101",
                        "title": "Sales & Other Revenue",
                        "amount": root.money(root.returnData.line101SalesRevenue || 0),
                        "note": "Pre-tax fees + billed disbursements (" + String((root.salesModel || []).length) + " invoices)",
                        "highlight": false
                    },
                    {
                        "line": "Line 105 (Line 103 + 104)",
                        "title": "Total HST Collected",
                        "amount": root.money(root.returnData.line105TotalHst || 0),
                        "note": "13% Ontario HST collectible on invoices",
                        "highlight": false
                    },
                    {
                        "line": "Line 108 (Line 106 + 107)",
                        "title": "Total Eligible ITCs",
                        "amount": root.money(root.returnData.line108TotalItcs || 0),
                        "note": "Claimable HST paid on expenses & SHL outlays",
                        "highlight": false
                    },
                    {
                        "line": "Line 109 · " + String(root.returnData.positionLabel || "Net Tax"),
                        "title": (root.returnData.isRefund ? "Line 111 Refund Claimed" : "Line 113 Balance Owing"),
                        "amount": root.money(root.returnData.line109NetTax || 0),
                        "note": root.returnData.isRefund ? "CRA refund receivable (GIFI 1300)" : "Net HST remittance payable (GIFI 2680)",
                        "highlight": true
                    }
                ]

                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 86
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
                            text: String(modelData.line || "")
                            color: root._accent
                            font.pixelSize: 11
                            font.weight: Font.Bold
                        }
                        Text {
                            text: String(modelData.title || "")
                            color: root._muted
                            font.pixelSize: 11
                        }
                        Text {
                            text: String(modelData.amount || "$0.00")
                            color: root._text
                            font.pixelSize: 19
                            font.weight: Font.Bold
                        }
                        Text {
                            text: String(modelData.note || "")
                            color: root._muted
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // Side-by-Side Drill-Down Tables (ITCs & Sales)
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Left: Eligible ITCs (Line 106/108)
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

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.08)

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 6

                            Text {
                                text: "Eligible Input Tax Credits — Line 106 / 108 (" + String((root.itcModel || []).length) + " items)"
                                color: root._text
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                Layout.fillWidth: true
                            }
                            Text {
                                text: "Total ITCs: " + root.money(root.returnData.line108TotalItcs || 0)
                                color: "#3fb950"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                            }
                        }
                    }

                    ListView {
                        id: itcListView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.itcModel

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: itcListView.width
                            height: 48
                            color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8

                                Text {
                                    text: String(modelData.date || "")
                                    color: root._text
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 80
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        text: String(modelData.vendor || "") + " — " + String(modelData.description || "")
                                        color: root._text
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: String(modelData.source || "") + " · Pre-Tax: " + root.money(modelData.preTaxAmount || 0) + " · ITC Rate: " + String(modelData.itcClaimablePct || 100) + "%"
                                        color: root._muted
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }
                                Text {
                                    text: root.money(modelData.itcClaimed || 0)
                                    color: "#3fb950"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignRight
                                    Layout.preferredWidth: 85
                                }
                            }
                        }
                    }
                }
            }

            // Right: Sales & Invoices (Line 101/103)
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

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.08)

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 6

                            Text {
                                text: "Billed Invoices — Line 101 Sales & Line 103 HST (" + String((root.salesModel || []).length) + " invoices)"
                                color: root._text
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                Layout.fillWidth: true
                            }
                            Text {
                                text: "HST Collected: " + root.money(root.returnData.line105TotalHst || 0)
                                color: root._accent
                                font.pixelSize: 12
                                font.weight: Font.Bold
                            }
                        }
                    }

                    ListView {
                        id: salesListView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.salesModel

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: salesListView.width
                            height: 46
                            color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8

                                Text {
                                    text: String(modelData.invoiceNum || "")
                                    color: root._accent
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    Layout.preferredWidth: 92
                                }
                                Text {
                                    text: String(modelData.invoiceDate || "")
                                    color: root._text
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 80
                                }
                                Text {
                                    text: String(modelData.clientName || "")
                                    color: root._text
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: "Sales: " + root.money(modelData.preTaxRevenue || 0)
                                    color: root._muted
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 110
                                }
                                Text {
                                    text: "HST: " + root.money(modelData.hstCollected || 0)
                                    color: root._text
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignRight
                                    Layout.preferredWidth: 95
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
