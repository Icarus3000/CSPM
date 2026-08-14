pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property var reportData: ({})
    property string startDate: ""
    property string endDate: ""
    property string statusText: ""

    readonly property string appStyle: "Professional"
    readonly property color pageColor: SemanticTheme.surfaceApp(root.t, root.appStyle)
    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color inputColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color navy: SemanticTheme.isDarkMode(root.t) ? "#17243a" : "#1d2b44"
    readonly property color chartNavy: SemanticTheme.isDarkMode(root.t) ? "#6282ae" : "#24334d"
    readonly property bool hasReport: !!(root.reportData && root.reportData.ok)

    function applyReportSnapshot(snapshot) {
        if (!snapshot) return
        startDate = String(snapshot.startDate || "")
        endDate = String(snapshot.endDate || "")
        reportData = snapshot.reportData || ({})
        statusText = String(snapshot.statusText || "")
    }

    function money(value, decimals) {
        var places = decimals === undefined ? 0 : decimals
        var number = Math.abs(Number(value || 0))
        var sign = Number(value || 0) < 0 ? "-" : ""
        var fixed = number.toFixed(places)
        var pieces = fixed.split(".")
        pieces[0] = pieces[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
        return sign + "$" + pieces.join(places > 0 ? "." : "")
    }

    function numberValue(value, decimals) {
        return Number(value || 0).toFixed(decimals === undefined ? 1 : decimals)
    }

    function maximum(rows) {
        var result = 1
        for (var index = 0; index < rows.length; ++index)
            result = Math.max(result, Number(rows[index].amount || 0))
        return result
    }

    readonly property var summary: root.hasReport && root.reportData.summary ? root.reportData.summary : ({})
    readonly property var forecast: root.hasReport && root.reportData.forecast ? root.reportData.forecast : ({})
    readonly property var clients: root.hasReport && root.reportData.topClients ? root.reportData.topClients : []
    readonly property var monthly: root.hasReport && root.reportData.monthlyProduction ? root.reportData.monthlyProduction : []
    readonly property var daily: root.hasReport && root.reportData.dailyProduction ? root.reportData.dailyProduction : []

    Rectangle {
        anchors.fill: parent
        color: root.pageColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 12

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 82
            color: root.navy
            radius: 8
            RowLayout {
                anchors.fill: parent
                anchors.margins: 18
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: "PRODUCTIVITY REPORT"; color: "white"; font.pixelSize: 18; font.bold: true }
                    Text { text: root.startDate + "  —  " + root.endDate; color: "#D9E7FA"; font.pixelSize: 11 }
                }
                Text { text: "ZEN VIEW  ·  LIVE DATA · READ ONLY"; color: "#D9E7FA"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            // Do not let the KPI row compete with the insight or chart rows
            // for the entire window height.  Zen is a fixed report canvas,
            // not a vertically growing dashboard.
            Layout.preferredHeight: 104
            Layout.minimumHeight: 104
            Layout.maximumHeight: 104
            spacing: 10
            Repeater {
                model: [
                    { "label": "TOTAL PRODUCTION", "value": root.money(root.summary.totalProduction) },
                    { "label": "BILLABLE HOURS", "value": root.numberValue(root.summary.billableHours, 1) },
                    { "label": "REALIZED RATE", "value": root.money(root.summary.realizedRate, 2) }
                ]
                delegate: Rectangle {
                    id: kpiCard
                    required property var modelData
                    property string labelText: String(modelData.label || "")
                    property string valueText: String(modelData.value || "")
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: root.panelColor
                    border.width: 1
                    border.color: root.borderColor
                    radius: 7
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 7
                        Text { text: kpiCard.labelText; color: root.mutedInk; font.pixelSize: 10; font.weight: Font.Bold }
                        Text { text: kpiCard.valueText; color: root.ink; font.pixelSize: 24; font.weight: Font.Light }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 224
            Layout.minimumHeight: 224
            Layout.maximumHeight: 224
            spacing: 12

            Rectangle {
                // Using parent.width here made the RowLayout calculate its
                // own width from a child that was calculating from the
                // RowLayout.  Qt detected that recursive rearrange at runtime
                // and eventually crushed the charts below the viewport.
                Layout.preferredWidth: Math.max(360, Math.round(root.width * 0.42))
                Layout.minimumWidth: 360
                Layout.fillHeight: true
                color: root.panelColor
                border.width: 1
                border.color: root.borderColor
                radius: 7
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6
                    Text { text: "ANNUAL FORECAST"; color: root.accent; font.pixelSize: 11; font.bold: true }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        rowSpacing: 5
                        Text { text: "Current pace"; color: root.mutedInk; font.pixelSize: 11 }
                        Text { text: root.money(root.forecast.dailyPace, 0) + " / day"; color: root.ink; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                        Text { text: "Planning basis"; color: root.mutedInk; font.pixelSize: 11 }
                        Text { text: String(root.forecast.annualBasisDays || "—") + " days"; color: root.ink; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                        Text { text: "Annual target"; color: root.mutedInk; font.pixelSize: 11 }
                        Text { text: root.money(root.forecast.annualTarget); color: root.ink; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                    }
                    Item { Layout.fillHeight: true }
                    Text { text: root.money(root.forecast.annualProjection); color: root.ink; font.pixelSize: 31; font.weight: Font.Light }
                    Text { text: root.numberValue(root.forecast.percentToTarget, 1) + "% vs target"; color: Number(root.forecast.percentToTarget || 0) >= 0 ? "#0F8A6A" : "#C33A3A"; font.pixelSize: 11; font.bold: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                color: root.panelColor
                border.width: 1
                border.color: root.borderColor
                radius: 7
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8
                    Text { text: "TOP CLIENTS"; color: root.accent; font.pixelSize: 11; font.bold: true }
                    Repeater {
                        model: root.clients
                        delegate: RowLayout {
                            id: clientRow
                            required property var modelData
                            property string clientName: String(modelData.name || "")
                            property real clientAmount: Number(modelData.amount || 0)
                            Layout.fillWidth: true
                            Layout.preferredHeight: 22
                            Text { text: clientRow.clientName; color: root.ink; font.pixelSize: 11; elide: Text.ElideRight; Layout.preferredWidth: Math.max(130, parent.width * 0.34) }
                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 7; radius: 4; color: SemanticTheme.alpha(root.mutedInk, 0.18); Rectangle { width: parent.width * (clientRow.clientAmount / root.maximum(root.clients)); height: parent.height; radius: 4; color: root.chartNavy } }
                            Text { text: root.money(clientRow.clientAmount); color: root.ink; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 78 }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 240
            spacing: 12
            Repeater {
                model: [
                    { "title": "MONTHLY PRODUCTION", "subtitle": "Last 4 months", "rows": root.monthly, "color": root.chartNavy },
                    { "title": "DAILY PRODUCTION", "subtitle": "Last 7 days", "rows": root.daily, "color": root.accent }
                ]
                delegate: Rectangle {
                    id: chartCard
                    required property var modelData
                    property var chartRows: modelData.rows || []
                    property color barColor: modelData.color
                    property string chartTitle: String(modelData.title || "")
                    property string chartSubtitle: String(modelData.subtitle || "")
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    color: root.panelColor
                    border.width: 1
                    border.color: root.borderColor
                    radius: 7
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 5
                        Text { text: chartCard.chartTitle; color: root.ink; font.pixelSize: 11; font.bold: true }
                        Text { text: chartCard.chartSubtitle; color: root.mutedInk; font.pixelSize: 10 }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 170
                            spacing: 8
                            Repeater {
                                model: chartCard.chartRows
                                delegate: Item {
                                    id: chartBar
                                    required property var modelData
                                    property real amount: Number(modelData.amount || 0)
                                    property string labelText: String(modelData.label || "")
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: bar.top; anchors.bottomMargin: 4; text: root.money(chartBar.amount); color: root.ink; font.pixelSize: 9 }
                                    Rectangle { id: bar; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: label.top; width: Math.min(48, Math.max(16, parent.width * 0.55)); height: Math.max(3, (parent.height - 45) * (chartBar.amount / root.maximum(chartCard.chartRows))); color: chartCard.barColor; radius: 2 }
                                    Text { id: label; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; text: chartBar.labelText; color: root.mutedInk; font.pixelSize: 9 }
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.statusText
            color: root.mutedInk
            font.pixelSize: 10
            elide: Text.ElideRight
        }
    }
}
