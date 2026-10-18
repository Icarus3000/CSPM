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

    property int selectedTaxYear: 2026
    property int activeTabIndex: 1 // Default to Professional Corp (T2)
    property var t2125Data: ({})
    property var t2Data: ({})
    property var t2125ExpenseModel: []
    property var sch125Model: []
    property var sch100Model: []
    property var sch50Model: []
    property var t2057PropertiesModel: []
    property var t2057RulesModel: []

    function money(val) {
        var n = Number(val || 0)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        return sign + "$" + Math.abs(n).toFixed(2)
    }

    function refreshAll() {
        if (!root.appRef) return
        if (root.appRef.calculateT2125Summary) {
            var res1 = root.appRef.calculateT2125Summary(root.selectedTaxYear)
            if (res1 && res1.ok) {
                root.t2125Data = res1
                root.t2125ExpenseModel = res1.expenseLines || []
            }
        }
        if (root.appRef.calculateT2Summary) {
            var res2 = root.appRef.calculateT2Summary(root.selectedTaxYear)
            if (res2 && res2.ok) {
                root.t2Data = res2
                root.sch125Model = res2.schedule125Lines || []
                root.sch100Model = res2.schedule100Lines || []
                root.sch50Model = res2.schedule50Shareholders || []
                var helper = res2.formT2057Helper || {}
                root.t2057PropertiesModel = helper.electedProperties || []
                root.t2057RulesModel = helper.nonT2057CutoverRules || []
            }
        }
    }

    Component.onCompleted: {
        root.refreshAll()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // Top Bar
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
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Dual Income Tax & Section 85 Rollover Helper (T2125 · T2 GIFI · Form T2057)"
                        color: root._text
                        font.pixelSize: 16
                        font.weight: Font.Bold
                    }

                    Text {
                        text: "2026 Practice Transition: Sole Proprietorship (14 Parsons Court) -> Cory Schneider Law Professional Corporation (OCN: 1001781977)"
                        color: root._muted
                        font.pixelSize: 12
                    }
                }

                Button {
                    text: "1. Sole Prop (T2125 + Sch 3)"
                    highlighted: root.activeTabIndex === 0
                    onClicked: root.activeTabIndex = 0
                }

                Button {
                    text: "2. Professional Corp (T2 Sch 100 / 125 / 50)"
                    highlighted: root.activeTabIndex === 1
                    onClicked: root.activeTabIndex = 1
                }

                Button {
                    text: "3. Section 85 (Form T2057 Helper)"
                    highlighted: root.activeTabIndex === 2
                    onClicked: root.activeTabIndex = 2
                }

                Button {
                    text: "Refresh"
                    onClicked: root.refreshAll()
                }
            }
        }

        // =====================================================================
        // TAB 0: SOLE PROPRIETORSHIP (T2125 + SCHEDULE 3)
        // =====================================================================
        ColumnLayout {
            visible: root.activeTabIndex === 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Repeater {
                    model: [
                        {
                            "title": "Line 8299 Gross Professional Income",
                            "value": root.money(root.t2125Data.line8299GrossProfessionalIncome || 0),
                            "sub": "SOLE_PROP invoices (14 Parsons Court)"
                        },
                        {
                            "title": "Total Deductible Expenses + CCA",
                            "value": root.money(root.t2125Data.totalDeductibleExpenses || 0),
                            "sub": "Operating expenses + Line 9936 CCA"
                        },
                        {
                            "title": "Line 9946 Net Professional Income",
                            "value": root.money(root.t2125Data.line9946NetProfessionalIncome || 0),
                            "sub": "Reportable on T1 Line 13500"
                        },
                        {
                            "title": "Schedule 3 Goodwill Rollover Gain",
                            "value": root.money((root.t2125Data.schedule3CapitalGains || {}).capitalGain || 1.00),
                            "sub": "Elected POD $1.00 · Taxable Capital Gain $0.50"
                        }
                    ]

                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 76
                        radius: 8
                        color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.85)
                        border.width: 1
                        border.color: root._border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2
                            Text { text: String(modelData.title || ""); color: root._muted; font.pixelSize: 11 }
                            Text { text: String(modelData.value || "$0.00"); color: root._text; font.pixelSize: 18; font.weight: Font.Bold }
                            Text { text: String(modelData.sub || ""); color: root._muted; font.pixelSize: 10 }
                        }
                    }
                }
            }

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
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            Text { text: "T2125 Line"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 100 }
                            Text { text: "CRA T2125 Expense Category"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; Layout.fillWidth: true }
                            Text { text: "Gross Pre-Tax"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 120 }
                            Text { text: "Deductible Amount"; color: root._muted; font.pixelSize: 11; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 130 }
                        }
                    }

                    ListView {
                        id: t2125ListView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.t2125ExpenseModel

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: t2125ListView.width
                            height: 38
                            color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                Text { text: "Line " + String(modelData.line || ""); color: root._accent; font.pixelSize: 12; font.weight: Font.Bold; Layout.preferredWidth: 100 }
                                Text { text: String(modelData.label || ""); color: root._text; font.pixelSize: 12; Layout.fillWidth: true }
                                Text { text: root.money(modelData.grossPreTax || 0); color: root._muted; font.pixelSize: 12; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 120 }
                                Text { text: root.money(modelData.deductibleAmount || 0); color: root._text; font.pixelSize: 12; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 130 }
                            }
                        }
                    }
                }
            }
        }

        // =====================================================================
        // TAB 1: PROFESSIONAL CORPORATION (T2 SCH 100 / 125 / 50)
        // =====================================================================
        ColumnLayout {
            visible: root.activeTabIndex === 1
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Top KPI Strip for T2 Stub Year (Oct 17 – Dec 31, 2026)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Repeater {
                    model: [
                        {
                            "title": "GIFI 8299 Total PC Revenue",
                            "value": root.money(root.t2Data.gifi8299TotalRevenue || 0),
                            "sub": "Stub Period: 2026-10-17 to 2026-12-31"
                        },
                        {
                            "title": "GIFI 9367 Operating Expenses",
                            "value": root.money(root.t2Data.gifi9367TotalOperatingExpenses || 0),
                            "sub": "Includes $749.95 Oct 17 SHL start-up outlays"
                        },
                        {
                            "title": "GIFI 9999 Net Income / (Loss)",
                            "value": root.money(root.t2Data.gifi9999NetIncomeBeforeTax || 0),
                            "sub": "T2 Filing Deadline: " + String(root.t2Data.t2FilingDeadline || "2027-06-30")
                        },
                        {
                            "title": "GIFI 2781 Due to Shareholder",
                            "value": root.money(root.t2Data.gifi2781ShareholderLoanBalance || 0),
                            "sub": "GIFI 3500 Common: $1.00 · GIFI 3520 Special: $1.00"
                        }
                    ]

                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 76
                        radius: 8
                        color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.85)
                        border.width: 1
                        border.color: root._border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2
                            Text { text: String(modelData.title || ""); color: root._muted; font.pixelSize: 11 }
                            Text { text: String(modelData.value || "$0.00"); color: root._text; font.pixelSize: 18; font.weight: Font.Bold }
                            Text { text: String(modelData.sub || ""); color: root._muted; font.pixelSize: 10 }
                        }
                    }
                }
            }

            // Side-by-Side Schedule 125 & Schedule 100
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                // Schedule 125 Income Statement GIFI
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
                                Text {
                                    text: "T2 Schedule 125 — Income Statement GIFI (2026-10-17 to 2026-12-31)"
                                    color: root._text
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        ListView {
                            id: sch125ListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: root.sch125Model

                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: sch125ListView.width
                                height: 36
                                color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    Text { text: "GIFI " + String(modelData.gifiCode || ""); color: root._accent; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 76 }
                                    Text { text: String(modelData.label || ""); color: root._text; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: root.money(modelData.amount || 0); color: root._text; font.pixelSize: 12; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 95 }
                                }
                            }
                        }
                    }
                }

                // Schedule 100 Balance Sheet GIFI
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
                                Text {
                                    text: "T2 Schedule 100 — Balance Sheet GIFI & Schedule 50 Share Capital"
                                    color: root._text
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        ListView {
                            id: sch100ListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: root.sch100Model

                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: sch100ListView.width
                                height: 36
                                color: (index % 2 === 0) ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.03)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    Text { text: "GIFI " + String(modelData.gifiCode || ""); color: root._accent; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 76 }
                                    Text { text: String(modelData.label || ""); color: root._text; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: root.money(modelData.amount || 0); color: root._text; font.pixelSize: 12; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 95 }
                                }
                            }
                        }
                    }
                }
            }
        }

        // =====================================================================
        // TAB 2: SECTION 85 ROLLOVER (FORM T2057 HELPER)
        // =====================================================================
        ColumnLayout {
            visible: root.activeTabIndex === 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 165
                radius: 8
                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.90)
                border.width: 1
                border.color: root._accent

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6

                    Text {
                        text: "CRA Form T2057 — Election on Disposition of Property to a Taxable Canadian Corporation (ITA s. 85(1))"
                        color: root._text
                        font.pixelSize: 14
                        font.weight: Font.Bold
                    }

                    Text {
                        text: "Transferor: Cory Adam Schneider · Transferee: Cory Schneider Law Professional Corporation (OCN: 1001781977) · Effective Rollover Date: 2026-11-01 · Filing Deadline: 2027-06-15"
                        color: root._muted
                        font.pixelSize: 12
                    }

                    Repeater {
                        model: root.t2057PropertiesModel

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 68
                            radius: 6
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.14)
                            border.width: 1
                            border.color: root._accent

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 14

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: "Elected Property: " + String(modelData.propertyDescription || "")
                                        color: root._text
                                        font.pixelSize: 13
                                        font.weight: Font.Bold
                                    }
                                    Text {
                                        text: "Share Consideration: " + String(modelData.shareConsiderationDescription || "") + " · Non-Share Boot: " + String(modelData.nonShareBootDescription || "None ($0.00)")
                                        color: root._muted
                                        font.pixelSize: 11
                                    }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Text { text: "Fair Market Value: " + root.money(modelData.fairMarketValue || 100); color: root._text; font.pixelSize: 12; font.weight: Font.Bold }
                                    Text { text: "Elected Amount (POD): " + root.money(modelData.electedAmount || 1); color: "#3fb950"; font.pixelSize: 12; font.weight: Font.Bold }
                                    Text { text: "OBCA s. 24(3) Stated Capital: " + root.money(modelData.statedCapitalAdditionObca24_3 || 1); color: root._accent; font.pixelSize: 11 }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.88)
                border.width: 1
                border.color: root._border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    Text {
                        text: "Governing Minute Book & Cutover Rules (Schedules 50, 8 & Non-T2057 Transfers)"
                        color: root._text
                        font.pixelSize: 13
                        font.weight: Font.Bold
                    }

                    Repeater {
                        model: root.t2057RulesModel

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 42
                            radius: 6
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.04)
                            border.width: 1
                            border.color: root._border

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 10
                                text: "• " + String(modelData || "")
                                color: root._text
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
