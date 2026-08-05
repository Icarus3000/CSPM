pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var metrics
    property var appRef
    property var windowRef
    property var sfxBus
    property int fieldHeightPx: 36
    property bool autoLoadOnVisible: true
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    property real sectionRadiusPx: visualRules.radiusPanel
    property int selectedYear: (new Date()).getFullYear()
    property bool busy: false
    property bool loadedOnce: false
    property bool hasError: false
    property string statusText: "Ready."
    property var reportData: ({})

    readonly property color surfaceColor: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color inputColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color subtleInkColor: SemanticTheme.inkSubtle(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function ratioPx(ratio, minPx) {
        var baseWidth = (metrics && typeof metrics.contentW === "number")
            ? Math.max(1, Number(metrics.contentW))
            : Math.max(1, root.width > 0 ? root.width : 1280)
        var baseHeight = (metrics && typeof metrics.contentH === "number")
            ? Math.max(1, Number(metrics.contentH))
            : Math.max(1, root.height > 0 ? root.height : 720)
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(Math.min(baseWidth, baseHeight) * ratio))
    }

    function dataList(key) {
        if (!root.reportData || root.reportData[key] === undefined || root.reportData[key] === null)
            return []
        return root.reportData[key]
    }

    function summaryValue(key) {
        var summary = root.reportData && root.reportData.summary ? root.reportData.summary : ({})
        var value = summary[key]
        var n = Number(value)
        return isFinite(n) ? n : 0
    }

    function money(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        n = Math.abs(n)
        var parts = n.toFixed(2).split(".")
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
        return sign + "$" + parts.join(".")
    }

    function wholeMoney(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        n = Math.abs(n)
        return sign + "$" + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    function decimalText(value, digits) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        return n.toFixed(digits)
    }

    function toneColor(kind) {
        var tone = String(kind || "primary")
        if (tone === "success") return SemanticTheme.tone(root.t, "success", root.appStyle)
        if (tone === "warning") return SemanticTheme.tone(root.t, "warning", root.appStyle)
        if (tone === "info") return SemanticTheme.tone(root.t, "info", root.appStyle)
        if (tone === "error") return SemanticTheme.tone(root.t, "error", root.appStyle)
        return root.accentColor
    }

    function refreshDashboard() {
        if (root.busy)
            return
        root.busy = true
        root.hasError = false
        root.statusText = "Refreshing dashboard..."
        try {
            if (!root.appRef || typeof root.appRef.getFinancialDashboardReport !== "function") {
                root.reportData = {
                    "ok": false,
                    "message": "Financial dashboard backend is unavailable."
                }
            } else {
                root.reportData = root.appRef.getFinancialDashboardReport(root.selectedYear)
            }
            root.hasError = !(root.reportData && root.reportData.ok)
            root.statusText = root.hasError
                ? String(root.reportData && root.reportData.message ? root.reportData.message : "Dashboard refresh failed.")
                : ("Updated " + String(root.reportData.asOfDate || ""))
            root.loadedOnce = true
        } catch (e) {
            root.hasError = true
            root.statusText = String(e)
            root.reportData = {
                "ok": false,
                "message": String(e)
            }
        }
        root.busy = false
    }

    Component.onCompleted: {
        if (root.autoLoadOnVisible && root.visible)
            root.refreshDashboard()
    }

    onVisibleChanged: {
        if (visible && root.autoLoadOnVisible && !root.loadedOnce)
            root.refreshDashboard()
    }

    Connections {
        target: root.appRef ? root.appRef : null
        ignoreUnknownSignals: true
        function onTransactionDataChanged() {
            if (root.visible)
                root.refreshDashboard()
        }
        function onClientDataChanged() {
            if (root.visible)
                root.refreshDashboard()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        ScrollView {
            id: dashboardScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: dashboardScroll.availableWidth
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    spacing: 8

                    Text {
                        text: "Financial Dashboard"
                        color: root.inkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: root.isProMode ? 18 : root.ratioPx(0.019, 15)
                        font.bold: true
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Button {
                        text: "<"
                        enabled: !root.busy
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 34
                        onClicked: {
                            root.selectedYear -= 1
                            root.refreshDashboard()
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 82
                        Layout.preferredHeight: 34
                        radius: visualRules.radiusControl
                        color: root.inputColor
                        border.width: 1
                        border.color: root.borderColor

                        Text {
                            anchors.centerIn: parent
                            text: String(root.selectedYear)
                            color: root.inkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }

                    Button {
                        text: ">"
                        enabled: !root.busy
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 34
                        onClicked: {
                            root.selectedYear += 1
                            root.refreshDashboard()
                        }
                    }

                    Button {
                        text: root.busy ? "Refreshing" : "Refresh"
                        enabled: !root.busy
                        Layout.preferredWidth: 104
                        Layout.preferredHeight: 34
                        onClicked: root.refreshDashboard()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: visualRules.radiusPanel
                    color: root.hasError
                        ? Qt.rgba(SemanticTheme.tone(root.t, "error", root.appStyle).r, SemanticTheme.tone(root.t, "error", root.appStyle).g, SemanticTheme.tone(root.t, "error", root.appStyle).b, 0.12)
                        : root.inputColor
                    border.width: 1
                    border.color: root.hasError ? SemanticTheme.tone(root.t, "error", root.appStyle) : root.borderColor

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: Text.AlignVCenter
                        text: root.statusText
                        color: root.hasError ? SemanticTheme.tone(root.t, "error", root.appStyle) : root.mutedInkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: root.width < 900 ? 2 : 3
                    columnSpacing: 8
                    rowSpacing: 8

                    Repeater {
                        model: root.dataList("cards")

                        delegate: Rectangle {
                            id: kpiCard
                            required property var modelData

                            Layout.fillWidth: true
                            Layout.preferredHeight: 82
                            radius: visualRules.radiusPanel
                            color: root.panelColor
                            border.width: 1
                            border.color: root.borderColor

                            Rectangle {
                                width: 4
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                radius: 2
                                color: root.toneColor(kpiCard.modelData.tone)
                            }

                            Column {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 12
                                anchors.topMargin: 10
                                anchors.bottomMargin: 10
                                spacing: 3

                                Text {
                                    width: parent.width
                                    text: String(kpiCard.modelData.label || "")
                                    color: root.mutedInkColor
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: root.money(kpiCard.modelData.value)
                                    color: root.inkColor
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: 21
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: String(kpiCard.modelData.subvalue || "")
                                    color: root.subtleInkColor
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 92
                        radius: visualRules.radiusPanel
                        color: root.panelColor
                        border.width: 1
                        border.color: root.borderColor

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Docketed Time & Fees"
                                    color: root.mutedInkColor
                                    font.pixelSize: 12
                                    font.family: visualRules.textFontFamily
                                }
                                Text {
                                    text: root.money(root.summaryValue("docketedAmount"))
                                    color: root.inkColor
                                    font.pixelSize: 20
                                    font.bold: true
                                    font.family: visualRules.textFontFamily
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Billed From Time"
                                    color: root.mutedInkColor
                                    font.pixelSize: 12
                                    font.family: visualRules.textFontFamily
                                }
                                Text {
                                    text: root.money(root.summaryValue("billedTimeAmount"))
                                    color: root.inkColor
                                    font.pixelSize: 20
                                    font.bold: true
                                    font.family: visualRules.textFontFamily
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "WIP Hours"
                                    color: root.mutedInkColor
                                    font.pixelSize: 12
                                    font.family: visualRules.textFontFamily
                                }
                                Text {
                                    text: root.decimalText(root.summaryValue("wipHours"), 1)
                                    color: root.inkColor
                                    font.pixelSize: 20
                                    font.bold: true
                                    font.family: visualRules.textFontFamily
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumHeight: 310
                    spacing: 10

                    DashboardTable {
                        title: "Quarterly Performance"
                        headers: ["Quarter", "Revenue", "Expenses", "HST Coll", "HST Paid", "Net HST"]
                        rows: root.dataList("quarters")
                        rowKind: "quarters"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        t: root.t
                        appStyle: root.appStyle
                    }

                    DashboardTable {
                        title: "A/R Details"
                        headers: ["Client", "Amount"]
                        rows: root.dataList("arDetails")
                        rowKind: "ar"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        t: root.t
                        appStyle: root.appStyle
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumHeight: 270
                    spacing: 10

                    DashboardTable {
                        title: "Top Billing Clients"
                        headers: ["Client", "Value", "Share"]
                        rows: root.dataList("topBillingClients")
                        rowKind: "top"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        t: root.t
                        appStyle: root.appStyle
                    }

                    DashboardTable {
                        title: "Top Work Clients"
                        headers: ["Client", "Value", "Share"]
                        rows: root.dataList("topWorkClients")
                        rowKind: "top"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        t: root.t
                        appStyle: root.appStyle
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(92, 34 + (root.dataList("notes").length * 22))
                    radius: visualRules.radiusPanel
                    color: root.panelColor
                    border.width: 1
                    border.color: root.borderColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 6

                        Text {
                            text: "Methodology & Data Checks"
                            color: root.inkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }

                        Repeater {
                            model: root.dataList("notes")
                            delegate: Text {
                                required property string modelData
                                Layout.fillWidth: true
                                text: "- " + modelData
                                color: root.mutedInkColor
                                font.family: visualRules.textFontFamily
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
        }
    }
}
