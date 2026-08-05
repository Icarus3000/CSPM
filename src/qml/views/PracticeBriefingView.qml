pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtWebEngine
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme
import "../standards/SubwindowStyle.js" as SubwindowStyle

Rectangle {
    id: root
    color: SemanticTheme.surfaceApp(root.t, root.appStyle)

    property var t
    property var metrics
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : "Professional"

    property var briefing: ({
        "ok": false,
        "asOfDate": "",
        "todaysTasks": [],
        "upcomingDeadlines": [],
        "overdueDeadlines": [],
        "overdueBills": [],
        "readyToBillMatters": [],
        "summary": ({})
    })

    signal openScreenRequested(string moduleId, string nodeId)
    signal navigateRequested(int tileIndex, string nodeId, var state)
    signal reportWindowRequested(var reportDocument)
    property string statusText: ""

    property string briefingJsonStr: ""

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color raisedColor: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color warningColor: SemanticTheme.tone(root.t, "warning", root.appStyle)
    readonly property color errorColor: SemanticTheme.tone(root.t, "error", root.appStyle)

    readonly property var scaleRatios: SubwindowStyle.placeholderRatios()
    function ratioPx(ratio, minPx) {
        var unit = Math.min(Math.max(1, root.width), Math.max(1, root.height))
        return Math.max((typeof minPx === "number") ? minPx : 1, Math.round(unit * ratio))
    }

    function safeHydrate(webView, funcName, dataStr) {
        if (!dataStr || dataStr === "") return;
        var script = "(function() {" +
            "if (typeof window." + funcName + " === 'function') {" +
            "    window." + funcName + "(" + dataStr + ");" +
            "} else {" +
            "    var attempts = 0;" +
            "    var interval = setInterval(function() {" +
            "        attempts++;" +
            "        if (typeof window." + funcName + " === 'function') {" +
            "            clearInterval(interval);" +
            "            window." + funcName + "(" + dataStr + ");" +
            "        } else if (attempts > 100) {" +
            "            clearInterval(interval);" +
            "            console.error('Timed out waiting for ' + '" + funcName + "');" +
            "        }" +
            "    }, 50);" +
            "}" +
            "})();";
        webView.runJavaScript(script);
    }

    function refreshBriefing() {
        if (!root.appRef || !root.appRef.getPracticeBriefing) return
        try {
            var payload = root.appRef.getPracticeBriefing()
            if (payload && typeof payload === "object") {
                root.briefing = payload
                root.briefingJsonStr = JSON.stringify(payload)

            }
        } catch (e) {
            console.error("PracticeBriefingView.refreshBriefing failed:", e)
            root.statusText = "Error refreshing briefing: " + String(e)
        }
    }

    function sectionCount(items) {
        if (!items || items.length === undefined) return 0
        return Math.max(0, items.length)
    }

    function navigateTo(tileIndex, nodeId, state) {
        root.navigateRequested(Math.round(tileIndex), String(nodeId || ""), state || ({}))
    }

    function openDeadlineItem(item) {
        if (!item) return
        navigateTo(1, "B08", {
            "focusNodeId": "B08",
            "briefingDeadlineId": String(item.id || ""),
            "briefingCalendarDate": String(item.date || "")
        })
    }

    function openDeadlineCalendar(dateText) {
        navigateTo(1, "B07", {
            "focusNodeId": "B07",
            "briefingCalendarDate": String(dateText || "")
        })
    }

    function openTodayItem(item) {
        if (!item) return
        if (String(item.kind || "") === "meeting") {
            navigateTo(1, "B01", {
                "focusNodeId": "B01",
                "dateText": String(item.date || ""),
                "matterText": String(item.matterName || ""),
                "forceApplyStateAfterOpen": true
            })
            return
        }
        openDeadlineItem(item)
    }

    function openMatterBillingItem(item) {
        if (!item) return
        var clientName = ""
        if (item.raw && item.raw.clientName) {
            clientName = String(item.raw.clientName)
        } else if (item.clientName) {
            clientName = String(item.clientName)
        }
        navigateTo(2, "C01", {
            "focusNodeId": "C01",
            "selectedClientFilter": clientName
        })
    }

    function openRecentWorkItem(item) {
        if (!item) return
        navigateTo(1, "B01", {
            "focusNodeId": "B01",
            "dateText": String(item.date || ""),
            "matterText": String(item.matterName || ""),
            "forceApplyStateAfterOpen": true
        })
    }


    Menu {
        id: statementMenu
        property var targetItem: null

        MenuItem {
            text: statementMenu.targetItem && statementMenu.targetItem.workClient && statementMenu.targetItem.workClient !== statementMenu.targetItem.client
                  ? "Statement of Account (" + statementMenu.targetItem.workClient + ")"
                  : "Statement of Account (" + (statementMenu.targetItem ? statementMenu.targetItem.client : "") + ")"
            onTriggered: {
                if (statementMenu.targetItem && statementMenu.targetItem.client) {
                    var target = statementMenu.targetItem.workClient || statementMenu.targetItem.client
                    root.navigateTo(3, "D17", { "selectedClientId": "", "selectedClientLabel": target })
                }
            }
        }

        MenuItem {
            text: statementMenu.targetItem ? "Statement of Account (Billing: " + statementMenu.targetItem.client + ")" : ""
            visible: !!(statementMenu.targetItem && statementMenu.targetItem.workClient && statementMenu.targetItem.workClient !== statementMenu.targetItem.client)
            onTriggered: {
                if (statementMenu.targetItem && statementMenu.targetItem.client) {
                    root.navigateTo(3, "D17", { "selectedClientId": "", "selectedClientLabel": statementMenu.targetItem.client })
                }
            }
        }
    }

    function openStatementMenu(item) {
        statementMenu.targetItem = item
        statementMenu.popup()
    }

    function openOverdueBillItem(item) {
        if (!item) return
        var state = { "focusNodeId": "C04" }
        if (item.invoice !== undefined) state.invoiceId = String(item.invoice || "")
        else if (item.invoiceId !== undefined) state.invoiceId = String(item.invoiceId || "")
        
        if (item.client !== undefined) state.clientName = String(item.client || "")
        else if (item.clientName !== undefined) state.clientName = String(item.clientName || "")
        
        navigateTo(2, "C04", state)
    }

    PracticeBriefingRulesDialog {
        id: rulesDialog
        t: root.t
        appRef: root.appRef
        appStyle: root.appStyle
        onFiltersSaved: root.refreshBriefing()
    }

    Component.onCompleted: refreshBriefing()
    onVisibleChanged: {
        if (visible) refreshBriefing()
    }

    ScrollView {

        anchors.fill: parent
        anchors.margins: root.ratioPx(0.022, 16)
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: Math.max(720, root.width - 40)
            spacing: root.ratioPx(0.018, 12)

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "\uE80F"
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: root.ratioPx(0.024, 18)
                    color: root.accentColor
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Practice Briefing"
                        font.family: "Segoe UI"
                        font.pixelSize: root.ratioPx(0.025, 18)
                        font.weight: Font.DemiBold
                        color: root.inkColor
                    }

                    Text {
                        text: briefing.asOfDate
                            ? ("As of " + String(briefing.asOfDate || ""))
                            : "Loading today's priorities..."
                        font.family: "Segoe UI"
                        font.pixelSize: root.ratioPx(0.014, 11)
                        color: root.mutedInkColor
                    }
                }

                Button {
                    text: "Rules"
                    onClicked: rulesDialog.open()
                }

                Button {
                    text: "Refresh"
                    onClicked: root.refreshBriefing()
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 14
                rowSpacing: 14

                BriefingSectionCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    title: "Priorities"
                    count: root.sectionCount(root.briefing.todaysTasks) + root.sectionCount(root.briefing.upcomingDeadlines)
                    emptyText: "No immediate priorities."
                    items: (root.briefing.todaysTasks || []).concat(root.briefing.upcomingDeadlines || [])
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.panelColor
                    raisedColor: root.raisedColor
                    borderColor: root.borderColor
                    accentColor: root.accentColor
                    actionLabel: "Open Calendar"
                    onTitleClicked: navigateTo(1, "B01", { "focusNodeId": "B07" })
                    onActionRequested: navigateTo(1, "B01", { "focusNodeId": "B07" })
                    onItemClicked: function(item) { root.openTodayItem(item) }
                }

                BriefingSectionCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    title: "Recent Work"
                    count: root.sectionCount(root.briefing.recentWork)
                    emptyText: "No work entries recorded recently."
                    items: root.briefing.recentWork || []
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.panelColor
                    raisedColor: root.raisedColor
                    borderColor: root.borderColor
                    accentColor: root.accentColor
                    actionLabel: "Time Docket"
                    onTitleClicked: navigateTo(1, "B01", { "focusNodeId": "B01" })
                    onActionRequested: navigateTo(1, "B01", { "focusNodeId": "B01" })
                    onItemClicked: function(item) { root.openRecentWorkItem(item) }
                    itemTitleRole: "description"
                    itemDetailRole: "productivityDetail"

                    customHeader: Component {
                        Rectangle {
                            width: parent ? parent.width : 0
                            height: 48
                            color: "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 4
                                spacing: 8

                                function formatMetrics(label, obj) {
                                    if (!obj) return label + "\n0.0 hrs | $0"
                                    var h = Number(obj.hours || 0).toFixed(1)
                                    var n = Number(obj.net || 0).toLocaleString(Qt.locale(), 'f', 0)
                                    return label + "\n" + h + " hrs | $" + n
                                }

                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    color: root.mutedInkColor
                                    text: parent.formatMetrics("Today", root.briefing.productivitySummary ? root.briefing.productivitySummary.today : null)
                                }
                                Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: root.borderColor; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    color: root.mutedInkColor
                                    text: parent.formatMetrics("WTD", root.briefing.productivitySummary ? root.briefing.productivitySummary.wtd : null)
                                }
                                Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: root.borderColor; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    color: root.mutedInkColor
                                    text: parent.formatMetrics("7-Day", root.briefing.productivitySummary ? root.briefing.productivitySummary.last7 : null)
                                }
                                Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: root.borderColor; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    color: root.mutedInkColor
                                    text: parent.formatMetrics("90-Day", root.briefing.productivitySummary ? root.briefing.productivitySummary.last90 : null)
                                }
                                Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: root.borderColor; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "Segoe UI"
                                    font.pixelSize: 10
                                    color: root.mutedInkColor
                                    text: parent.formatMetrics("YTD", root.briefing.productivitySummary ? root.briefing.productivitySummary.ytd : null)
                                }
                            }
                        }
                    }
                }

                BriefingSectionCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    title: "Overdue Bills"
                    count: root.sectionCount(root.briefing.overdueBills)
                    emptyText: "No overdue invoices on file."
                    items: root.briefing.overdueBills || []
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.panelColor
                    raisedColor: root.raisedColor
                    borderColor: root.borderColor
                    accentColor: root.errorColor
                    actionLabel: "Collections Queue"
                    onTitleClicked: navigateTo(2, "C10", { "focusNodeId": "C10" })
                    onActionRequested: navigateTo(2, "C10", { "focusNodeId": "C10" })
                    onItemClicked: function(item) { root.openOverdueBillItem(item) }
                    onItemRightClicked: function(item, mouse) {
                        if (item && item.kind === "overdue-bill") {
                            root.openStatementMenu(item)
                        }
                    }
                }

                BriefingSectionCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    title: "Consider Billing"
                    count: root.sectionCount(root.briefing.readyToBillMatters)
                    emptyText: "No matters currently need billing review."
                    items: (root.briefing.readyToBillMatters || []).map(function(m) {
                        var cName = m.clientName ? " - " + m.clientName : ""
                        return {
                            matterId: m.matterId,
                            title: (m.matterNumber || m.matterId) + " - " + m.matterName + cName,
                            details: "$" + Number(m.wipAmount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " | " + m.entryCount + " open entries",
                            raw: m
                        }
                    })
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.panelColor
                    raisedColor: root.raisedColor
                    borderColor: root.borderColor
                    accentColor: root.warningColor
                    actionLabel: "WIP-to-Bill"
                    onTitleClicked: navigateTo(2, "C01", { "focusNodeId": "C01" })
                    onActionRequested: navigateTo(2, "C01", { "focusNodeId": "C01" })
                    onItemClicked: function(item) { root.openMatterBillingItem(item) }
                    itemTitleRole: "title"
                    itemDetailRole: "details"
                    itemDetailSuffix: ""
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: root.borderColor
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 18

                BriefingStatChip {
                    label: "Active clients"
                    value: String((root.briefing.summary && root.briefing.summary.activeClientCount) || 0)
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.raisedColor
                    borderColor: root.borderColor
                    onClicked: navigateTo(0, "A01", { "focusNodeId": "A01" })
                }
                BriefingStatChip {
                    label: "Active matters"
                    value: String((root.briefing.summary && root.briefing.summary.activeMatterCount) || 0)
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.raisedColor
                    borderColor: root.borderColor
                    onClicked: navigateTo(0, "A09", { "focusNodeId": "A09" })
                }
                BriefingStatChip {
                    label: "Open deadlines"
                    value: String((root.briefing.summary && root.briefing.summary.deadlinesCount) || 0)
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.raisedColor
                    borderColor: root.borderColor
                    onClicked: navigateTo(1, "B01", { "focusNodeId": "B07" })
                }
                BriefingStatChip {
                    label: "Unbilled entries"
                    value: String((root.briefing.summary && root.briefing.summary.unbilledDraftCount) || 0)
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.raisedColor
                    borderColor: root.borderColor
                    onClicked: navigateTo(2, "C01", { "focusNodeId": "C01" })
                }
                BriefingStatChip {
                    label: "Recent hours"
                    value: String((root.briefing.summary && root.briefing.summary.recentWorkHours) || 0)
                    inkColor: root.inkColor
                    mutedInkColor: root.mutedInkColor
                    panelColor: root.raisedColor
                    borderColor: root.borderColor
                    onClicked: navigateTo(1, "B04", { "focusNodeId": "B04" })
                }
            }
        }
    }

    component BriefingStatChip: Rectangle {
        property string label: ""
        property string value: "0"
        property color inkColor
        property color mutedInkColor
        property color panelColor
        property color borderColor

        signal clicked()

        radius: visualRules.radiusControl
        color: statHover.containsMouse ? Qt.rgba(inkColor.r, inkColor.g, inkColor.b, 0.06) : panelColor
        border.width: 1
        border.color: statHover.containsMouse ? accentColor : borderColor
        implicitWidth: chipLayout.implicitWidth + 24
        implicitHeight: 54

        readonly property color accentColor: root.accentColor

        MouseArea {
            id: statHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }

        ColumnLayout {
            id: chipLayout
            anchors.centerIn: parent
            spacing: 2

            Text {
                text: value
                font.family: "Segoe UI"
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: inkColor
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                text: label
                font.family: "Segoe UI"
                font.pixelSize: 11
                color: mutedInkColor
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }

    component BriefingSectionCard: Rectangle {
        id: card
        property string title: ""
        property int count: 0
        property string emptyText: ""
        property var items: []
        property color inkColor
        property color mutedInkColor
        property color panelColor
        property color raisedColor
        property color borderColor
        property color accentColor
        property string actionLabel: ""
        property string itemTitleRole: "description"
        property string itemDetailRole: "date"
        property string itemDetailSuffix: ""
        property Component customHeader: null

        signal actionRequested()
        signal titleClicked()
        signal itemClicked(var item)
        signal itemRightClicked(var item, var mouse)

        radius: visualRules.radiusPanel
        color: panelColor
        border.width: 1
        border.color: borderColor

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: titleLabel.implicitHeight

                    Text {
                        id: titleLabel
                        anchors.fill: parent
                        text: card.title
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: titleHover.containsMouse ? card.accentColor : card.inkColor
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                    }

                    MouseArea {
                        id: titleHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: card.titleClicked()
                    }
                }

                Rectangle {
                    Layout.preferredWidth: Math.max(24, countBadge.implicitWidth + 12)
                    Layout.preferredHeight: 22
                    radius: 11
                    color: Qt.rgba(card.accentColor.r, card.accentColor.g, card.accentColor.b, 0.12)
                    border.width: 1
                    border.color: Qt.rgba(card.accentColor.r, card.accentColor.g, card.accentColor.b, 0.28)

                    Text {
                        id: countBadge
                        anchors.centerIn: parent
                        text: String(card.count)
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: card.accentColor
                    }
                }
            }

            Loader {
                Layout.fillWidth: true
                active: card.customHeader !== null
                sourceComponent: card.customHeader
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: card.items
                visible: card.count > 0

                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 42
                    radius: 4
                    color: rowHover.containsMouse
                        ? Qt.rgba(card.accentColor.r, card.accentColor.g, card.accentColor.b, 0.10)
                        : card.raisedColor
                    border.width: 1
                    border.color: rowHover.containsMouse ? card.accentColor : card.borderColor

                    readonly property string itemTitle: {
                        var key = card.itemTitleRole
                        return String(modelData && modelData[key] ? modelData[key] : "")
                    }
                    readonly property string itemDetail: {
                        var key = card.itemDetailRole
                        var raw = String(modelData && modelData[key] ? modelData[key] : "")
                        if (key === "entryCount") {
                            return raw + card.itemDetailSuffix
                        }
                        return raw
                    }

                    MouseArea {
                        id: rowHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: function(mouse) {
                            if (mouse.button === Qt.RightButton) {
                                card.itemRightClicked(modelData, mouse)
                            } else {
                                card.itemClicked(modelData)
                            }
                        }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 1

                        Text {
                            Layout.fillWidth: true
                            text: parent.parent.itemTitle || "Item"
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            color: card.inkColor
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: parent.parent.itemDetail
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                            color: card.mutedInkColor
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: card.count <= 0
                text: card.emptyText
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI"
                font.pixelSize: 12
                color: card.mutedInkColor
            }

            Button {
                Layout.alignment: Qt.AlignRight
                text: card.actionLabel
                flat: true
                onClicked: card.actionRequested()
            }
        }
    }
}
