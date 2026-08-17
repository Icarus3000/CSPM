pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property var appRef
    property var dashboardSummary: ({})
    property string appStyle: "Professional"
    property bool interactive: true
    property bool loadingBriefing: false
    property var briefing: defaultBriefing()
    // This is the actual first Professional landing surface.  It must consume
    // the same prepared briefing snapshot as PracticeBriefingView before the
    // hidden startup window can be revealed; otherwise its WIP card briefly
    // paints the zero-valued fallback model.
    property bool startupSnapshotApplied: false

    readonly property bool tight: width < 760 || height < 540
    readonly property int queueRowLimit: height < 560 ? 2 : (height < 760 ? 3 : 4)
    readonly property color backgroundColor: SemanticTheme.surfaceApp(root.t, root.appStyle)
    readonly property color surfaceColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color hoverColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color activeBorderColor: SemanticTheme.borderStrong(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color urgentColor: "#B42318"
    readonly property color positiveColor: "#0F766E"
    readonly property var productivity: (root.briefing && root.briefing.productivitySummary)
        ? root.briefing.productivitySummary : ({})

    signal openScreenRequested(string moduleId, string nodeId)
    signal openWorkspaceRequested(string moduleId, string nodeId, var state)

    clip: true

    function defaultBriefing() {
        return {
            "ok": false,
            "todaysTasks": [],
            "upcomingDeadlines": [],
            "recentWork": [],
            "overdueDeadlines": [],
            "overdueBills": [],
            "readyToBillMatters": [],
            "arSummary": {
                "totalAr": 0.0,
                "openInvoiceCount": 0,
                "overdueAr": 0.0,
                "overdueInvoiceCount": 0,
                "overdueGraceDays": 30
            },
            "summary": {},
            "productivitySummary": {
                "today": { "hours": 0.0, "gross": 0.0, "net": 0.0 },
                "wtd": { "hours": 0.0, "gross": 0.0, "net": 0.0 },
                "ytd": { "hours": 0.0, "gross": 0.0, "net": 0.0 }
            }
        }
    }

    function localTodayIso() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function number(value) {
        var parsed = Number(value || 0)
        return isFinite(parsed) ? parsed : 0
    }

    function whole(value) {
        return Math.max(0, Math.round(number(value)))
    }

    function formatHours(value) {
        var hours = number(value)
        return (Math.round(hours * 10) / 10).toFixed(hours % 1 === 0 ? 0 : 1) + " h"
    }

    function formatMoney(value) {
        var amount = number(value)
        var prefix = amount < 0 ? "-$" : "$"
        var absolute = Math.abs(amount)
        if (absolute >= 1000000)
            return prefix + (absolute / 1000000).toFixed(1).replace(".0", "") + "M"
        if (absolute >= 1000)
            return prefix + (absolute / 1000).toFixed(1).replace(".0", "") + "K"
        return prefix + Math.round(absolute)
    }

    function todayLabel() {
        return Qt.formatDate(new Date(), "dddd, MMMM d")
    }

    function entryCount(list) {
        return list && list.length ? list.length : 0
    }

    function currentDayItems() {
        var items = root.briefing && root.briefing.todaysTasks ? root.briefing.todaysTasks : []
        var today = Qt.formatDate(new Date(), "yyyy-MM-dd")
        var result = []
        for (var i = 0; i < items.length; ++i) {
            // The briefing can deliberately prepend overdue deadlines to this
            // list. They have their own risk category here, so do not count or
            // display them twice on the home page.
            if (String(items[i].date || "") === today)
                result.push(items[i])
        }
        return result
    }

    function sumAmount(list, key) {
        var total = 0
        var rows = list || []
        for (var i = 0; i < rows.length; ++i)
            total += number(rows[i][key])
        return total
    }

    function arSummaryValue(key) {
        var summary = root.briefing && root.briefing.arSummary ? root.briefing.arSummary : ({})
        return number(summary[key])
    }

    function priorityItems() {
        var items = []
        var overdue = root.briefing && root.briefing.overdueDeadlines ? root.briefing.overdueDeadlines : []
        var today = root.currentDayItems()
        var upcoming = root.briefing && root.briefing.upcomingDeadlines ? root.briefing.upcomingDeadlines : []
        for (var i = 0; i < overdue.length; ++i) {
            items.push({
                "title": String(overdue[i].description || "Overdue deadline"),
                "detail": "Overdue · " + String(overdue[i].date || ""),
                "tone": "urgent"
            })
        }
        for (var j = 0; j < today.length; ++j) {
            items.push({
                "title": String(today[j].description || "Today’s item"),
                "detail": String(today[j].kind || "today").replace("-", " ") + " · today",
                "tone": "today"
            })
        }
        for (var k = 0; k < upcoming.length; ++k) {
            items.push({
                "title": String(upcoming[k].description || "Upcoming deadline"),
                "detail": "Due " + String(upcoming[k].date || "soon"),
                "tone": "upcoming"
            })
        }
        if (items.length === 0) {
            items.push({
                "title": "No urgent items in the current queue",
                "detail": "Open Practice Briefing to review the full horizon",
                "tone": "clear"
            })
        }
        return items
    }

    function limitedItems(items, maximum) {
        var limited = []
        var source = items || []
        for (var i = 0; i < source.length && i < maximum; ++i)
            limited.push(source[i])
        return limited
    }

    function refreshBriefing() {
        if (root.loadingBriefing || !root.appRef || !root.appRef.getPracticeBriefing)
            return
        if (root.appRef.backendBooted !== undefined && !root.appRef.backendBooted)
            return
        root.loadingBriefing = true
        try {
            var payload = root.appRef.getPracticeBriefing()
            if (payload && typeof payload === "object" && payload.ok !== undefined)
                root.briefing = payload
        } catch (e) {
        }
        root.loadingBriefing = false
    }

    function startupReadinessBlocksDirectLoad() {
        if (!root.appRef || root.startupSnapshotApplied) return false
        var state = String(root.appRef.startupReadinessState || "idle")
        return state !== "idle" && state !== "ready-to-reveal"
    }

    function applyPreparedStartupBriefing() {
        if (!root.appRef || root.startupSnapshotApplied) return root.startupSnapshotApplied
        if (root.appRef.startupBriefingSnapshotReady !== true) return false
        var payload = root.appRef.startupBriefingSnapshot
        if (!payload || typeof payload !== "object" || payload.ok !== true) return false
        root.briefing = payload
        root.startupSnapshotApplied = true
        return true
    }

    property var quickActions: [
        { "label": "Today", "icon": "\uE80F", "moduleId": "home", "nodeId": "H01" },
        { "label": "Time docket", "icon": "\uE823", "moduleId": "docketing", "nodeId": "B01" },
        { "label": "Clients & matters", "icon": "\uE77B", "moduleId": "clients", "nodeId": "A01" },
        { "label": "WIP to bill", "icon": "\uE8C7", "moduleId": "billing", "nodeId": "C01" }
    ]

    property var dailyMetrics: [
        {
            "label": "Deadline risk",
            "value": String(entryCount(briefing.overdueDeadlines) + entryCount(currentDayItems())),
            "detail": String(entryCount(briefing.overdueDeadlines)) + " overdue · " + String(entryCount(currentDayItems())) + " today",
            "icon": "\uE9D9",
            "tone": entryCount(briefing.overdueDeadlines) > 0 ? "urgent" : "accent",
            "moduleId": "home", "nodeId": "H01"
        },
        {
            "label": "Time today",
            "value": formatHours(productivity.today ? productivity.today.hours : 0),
            "detail": formatMoney(productivity.today ? productivity.today.gross : 0) + " recorded",
            "icon": "\uE823",
            "tone": "accent",
            "moduleId": "finance", "nodeId": "D18",
            "workspaceState": {
                "focusNodeId": "D18",
                "tabTitle": "Today's Time Ledger",
                "singleInstanceKey": "report:D18:today",
                "startDate": root.localTodayIso(),
                "endDate": root.localTodayIso(),
                "showTimeOnly": true
            }
        },
        {
            "label": "WIP to review",
            "value": formatMoney(sumAmount(briefing.readyToBillMatters, "wipAmount")),
            "detail": String(entryCount(briefing.readyToBillMatters)) + " matters ready",
            "icon": "\uE8C7",
            "tone": "positive",
            "moduleId": "billing", "nodeId": "C01"
        },
        {
            "label": "Total A/R",
            "value": formatMoney(arSummaryValue("totalAr")),
            "detail": "Overdue: " + formatMoney(arSummaryValue("overdueAr"))
                + " \u00b7 " + String(whole(arSummaryValue("overdueInvoiceCount")))
                + (whole(arSummaryValue("overdueInvoiceCount")) === 1 ? " invoice" : " invoices"),
            "icon": "\uE9D9",
            "tone": arSummaryValue("overdueInvoiceCount") > 0 ? "urgent" : "accent",
            "moduleId": "finance", "nodeId": "D06"
        }
    ]

    Timer {
        id: initialBriefingTimer
        interval: 1200
        repeat: false
        onTriggered: root.refreshBriefing()
    }

    Component.onCompleted: {
        if (root.applyPreparedStartupBriefing()) return
        if (!root.startupReadinessBlocksDirectLoad()) initialBriefingTimer.start()
    }
    onVisibleChanged: {
        if (!visible) return
        if (root.applyPreparedStartupBriefing()) return
        if (!root.startupReadinessBlocksDirectLoad()) initialBriefingTimer.restart()
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onBackendBootChanged() {
            if (root.appRef && root.appRef.backendBooted
                    && !root.applyPreparedStartupBriefing()
                    && !root.startupReadinessBlocksDirectLoad())
                initialBriefingTimer.restart()
        }
        function onStartupBriefingSnapshotChanged() {
            root.applyPreparedStartupBriefing()
        }
        function onHomeDashboardSummaryUpdated(payload) {
            if (payload && typeof payload === "object")
                root.dashboardSummary = payload
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.backgroundColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.tight ? 10 : 20
        spacing: root.tight ? 8 : 12

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.tight ? 34 : 42
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Text {
                    Layout.fillWidth: true
                    text: "Daily operations"
                    color: root.inkColor
                    font.family: "Segoe UI"
                    font.pixelSize: root.tight ? 17 : 21
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    visible: !root.tight
                    text: root.todayLabel() + " · Focus on risk, time, and active work"
                    color: root.mutedInkColor
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            Text {
                visible: root.loadingBriefing && !root.tight
                text: "Refreshing…"
                color: root.mutedInkColor
                font.family: "Segoe UI"
                font.pixelSize: 11
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.tight ? 36 : 42
            spacing: root.tight ? 5 : 8

            Repeater {
                model: root.quickActions

                delegate: Rectangle {
                    id: quickAction
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: parent.height
                    radius: 4
                    color: quickActionHover.hovered ? root.hoverColor : root.surfaceColor
                    border.width: 1
                    border.color: quickActionHover.hovered ? root.activeBorderColor : root.borderColor

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: root.tight ? 6 : 10
                        anchors.rightMargin: root.tight ? 6 : 10
                        spacing: root.tight ? 3 : 6

                        Text {
                            text: quickAction.modelData.icon
                            font.family: "Segoe MDL2 Assets"
                            font.pixelSize: root.tight ? 14 : 16
                            color: root.accentColor
                        }

                        Text {
                            Layout.fillWidth: true
                            text: quickAction.modelData.label
                            color: root.inkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 10 : 11
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                    }

                    HoverHandler { id: quickActionHover }
                    TapHandler {
                        enabled: root.interactive
                        onTapped: root.openScreenRequested(String(quickAction.modelData.moduleId), String(quickAction.modelData.nodeId))
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.width >= 1060 ? (root.tight ? 64 : 82) : (root.tight ? 136 : 176)
            columns: root.width >= 1060 ? 4 : 2
            columnSpacing: root.tight ? 6 : 10
            rowSpacing: root.tight ? 6 : 10

            Repeater {
                model: root.dailyMetrics

                delegate: Rectangle {
                    id: metricCard
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 5
                    color: metricHover.hovered ? root.hoverColor : root.surfaceColor
                    border.width: 1
                    border.color: metricHover.hovered ? root.activeBorderColor : root.borderColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.tight ? 8 : 12
                        spacing: root.tight ? 1 : 3

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                text: metricCard.modelData.icon
                                font.family: "Segoe MDL2 Assets"
                                font.pixelSize: root.tight ? 13 : 16
                                color: metricCard.modelData.tone === "urgent" ? root.urgentColor
                                    : (metricCard.modelData.tone === "positive" ? root.positiveColor : root.accentColor)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: metricCard.modelData.label
                                color: root.mutedInkColor
                                font.family: "Segoe UI"
                                font.pixelSize: root.tight ? 10 : 11
                                elide: Text.ElideRight
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: metricCard.modelData.value
                            color: root.inkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 17 : 23
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: metricCard.modelData.detail
                            color: root.mutedInkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 9 : 10
                            elide: Text.ElideRight
                        }
                    }

                    HoverHandler { id: metricHover }
                    TapHandler {
                        enabled: root.interactive
                        onTapped: {
                            var state = metricCard.modelData.workspaceState
                            if (state && typeof state === "object") {
                                root.openWorkspaceRequested(
                                    String(metricCard.modelData.moduleId),
                                    String(metricCard.modelData.nodeId),
                                    state
                                )
                            } else {
                                root.openScreenRequested(String(metricCard.modelData.moduleId), String(metricCard.modelData.nodeId))
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: root.tight ? 130 : 190
            spacing: root.tight ? 8 : 12

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                radius: 5
                color: root.surfaceColor
                border.width: 1
                border.color: root.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: root.tight ? 10 : 14
                    spacing: root.tight ? 5 : 8

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            Layout.fillWidth: true
                            text: "Today’s queue"
                            color: root.inkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 13 : 15
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        Text {
                            visible: !root.tight
                            text: "Practice Briefing ›"
                            color: root.accentColor
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                        }
                    }

                    Repeater {
                        model: root.limitedItems(root.priorityItems(), root.queueRowLimit)

                        delegate: Item {
                            id: queueRow
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.tight ? 28 : 34

                            Rectangle {
                                width: 3
                                height: parent.height - 4
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                radius: 2
                                color: queueRow.modelData.tone === "urgent" ? root.urgentColor
                                    : (queueRow.modelData.tone === "clear" ? root.positiveColor : root.accentColor)
                            }

                            ColumnLayout {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 0

                                Text {
                                    Layout.fillWidth: true
                                    text: queueRow.modelData.title
                                    color: root.inkColor
                                    font.family: "Segoe UI"
                                    font.pixelSize: root.tight ? 10 : 11
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: !root.tight
                                    text: queueRow.modelData.detail
                                    color: root.mutedInkColor
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                            }

                            TapHandler {
                                enabled: root.interactive
                                onTapped: root.openScreenRequested("home", "H01")
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                spacing: root.tight ? 8 : 12

                Rectangle {
                    id: productivityCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 5
                    color: root.interactive && productivityClickArea.containsMouse
                        ? root.hoverColor : root.surfaceColor
                    border.width: 1
                    border.color: root.interactive && productivityClickArea.containsMouse
                        ? root.activeBorderColor : root.borderColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.tight ? 9 : 12
                        spacing: root.tight ? 4 : 7

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                Layout.fillWidth: true
                                text: "My productivity"
                                color: root.inkColor
                                font.family: "Segoe UI"
                                font.pixelSize: root.tight ? 12 : 14
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                visible: !root.tight
                                text: "Open report ›"
                                color: root.accentColor
                                font.family: "Segoe UI"
                                font.pixelSize: 10
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: root.tight ? 2 : 5

                            Repeater {
                                model: [
                                    { "label": "WTD billable", "value": root.formatHours(root.productivity.wtd ? root.productivity.wtd.hours : 0) },
                                    { "label": "WTD fees", "value": root.formatMoney(root.productivity.wtd ? root.productivity.wtd.gross : 0) },
                                    { "label": "YTD billable", "value": root.formatHours(root.productivity.ytd ? root.productivity.ytd.hours : 0) },
                                    { "label": "YTD fees", "value": root.formatMoney(root.productivity.ytd ? root.productivity.ytd.gross : 0) }
                                ]

                                delegate: ColumnLayout {
                                    id: productivityMetricDelegate
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Text {
                                        Layout.fillWidth: true
                                        text: productivityMetricDelegate.modelData.label
                                        color: root.mutedInkColor
                                        font.family: "Segoe UI"
                                        font.pixelSize: root.tight ? 8 : 9
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: productivityMetricDelegate.modelData.value
                                        color: root.inkColor
                                        font.family: "Segoe UI"
                                        font.pixelSize: root.tight ? 12 : 15
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }

                    MouseArea {
                        id: productivityClickArea
                        anchors.fill: parent
                        enabled: root.interactive
                        hoverEnabled: true
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: root.openScreenRequested("finance", "D10")
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 5
                    color: root.surfaceColor
                    border.width: 1
                    border.color: root.borderColor

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.tight ? 9 : 12
                        spacing: root.tight ? 3 : 5

                        Text {
                            Layout.fillWidth: true
                            text: "Resume work"
                            color: root.inkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 12 : 14
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        Repeater {
                            model: root.limitedItems(root.briefing.recentWork || [], root.tight ? 2 : 3)

                            delegate: Text {
                                required property var modelData
                                Layout.fillWidth: true
                                text: String(modelData.matterName || modelData.description || "Recent work")
                                color: root.mutedInkColor
                                font.family: "Segoe UI"
                                font.pixelSize: root.tight ? 9 : 10
                                elide: Text.ElideRight
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.entryCount(root.briefing.recentWork) === 0
                            text: "Your recent docket work will appear here."
                            color: root.mutedInkColor
                            font.family: "Segoe UI"
                            font.pixelSize: root.tight ? 9 : 10
                            elide: Text.ElideRight
                        }
                    }

                    TapHandler {
                        enabled: root.interactive
                        onTapped: root.openScreenRequested("clients", "A01")
                    }
                }
            }
        }
    }
}
