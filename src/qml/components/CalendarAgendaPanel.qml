pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property var appRef
    property var controller: root.appRef && root.appRef.calendarController
        ? root.appRef.calendarController : null
    property string appStyle: "Professional"
    property bool interactive: true
    property bool compact: false
    property int selectedHorizon: 0
    property bool initialRefreshRequested: false
    readonly property var agenda: root.controller && root.controller.snapshot
        ? root.controller.snapshot : ({ "state": "unconfigured", "today": [], "next7Days": [] })
    readonly property var events: root.selectedHorizon === 0
        ? (root.agenda.today || []) : (root.agenda.next7Days || [])
    readonly property bool busy: root.controller ? !!root.controller.busy : false
    readonly property string state: String(root.agenda.state || "unconfigured")
    readonly property bool hasAccount: !!root.agenda.accountEmail
        && (root.state === "ready" || root.state === "partial")
    readonly property bool hostVisible: root.Window.window !== null && root.Window.window.visible
    readonly property bool refreshAllowed: root.visible && root.interactive && root.hostVisible
        && !!root.controller
        && (!root.appRef || root.appRef.backendBooted !== false)
        && (!root.appRef || !root.appRef.startupReadinessState
            || String(root.appRef.startupReadinessState) === "idle"
            || String(root.appRef.startupReadinessState) === "ready-to-reveal")
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)

    signal practiceBriefingRequested()

    radius: 5
    color: SemanticTheme.surfacePanel(root.t, root.appStyle)
    border.width: 1
    border.color: root.borderColor
    clip: true

    // A hidden Professional home participates in the existing startup snapshot
    // handshake. Calendar network work starts only once its real window is shown.
    function requestInitialRefresh() {
        if (!root.refreshAllowed || root.initialRefreshRequested) return
        root.initialRefreshRequested = true
        root.controller.refresh()
    }

    function refreshAgenda() {
        if (root.refreshAllowed && !root.busy) root.controller.refresh()
    }

    function openConnectionSettings() {
        if (!root.interactive) return
        connectionDialogLoader.active = true
        Qt.callLater(function() {
            var dialog = connectionDialogLoader.item as CalendarConnectionDialog
            if (dialog) dialog.open()
        })
    }

    function dateLabel(isoDate) {
        var parts = String(isoDate || "").split("-")
        if (parts.length !== 3) return String(isoDate || "")
        return Qt.formatDate(new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])), "ddd, MMM d")
    }

    // Controller timestamps are already expressed in the configured calendar
    // timezone. Preserve those wall-clock fields even on a different PC timezone.
    function timeLabel(isoTime) {
        var match = /T(\d{2}):(\d{2})/.exec(String(isoTime || ""))
        if (!match) return ""
        var hour = Number(match[1])
        return String(hour % 12 || 12) + ":" + match[2] + (hour < 12 ? " AM" : " PM")
    }

    function eventTimeLabel(event) {
        if (event.allDay) return "All day"
        var start = root.timeLabel(event.start)
        var end = root.timeLabel(event.end)
        return (event.isCurrent ? "Now · " : "") + start + (end ? " – " + end : "")
    }

    function sourceLabel(event) {
        return (event.sourceCalendars || []).join(" · ")
    }

    function statusLabel() {
        if (!root.controller) return "Calendar connection is unavailable in this session."
        if (root.state === "unconfigured") return "Connect Microsoft 365 to see your meetings and holidays."
        if (root.state === "signing-in") return "Finish Microsoft sign-in in Manage calendars."
        if (root.state === "disconnected") return "Connect your Microsoft 365 account in Manage calendars."
        if (root.busy) return "Refreshing calendars…"
        if (root.agenda.message) return String(root.agenda.message)
        return ""
    }

    onRefreshAllowedChanged: if (root.refreshAllowed) initialRefreshTimer.restart()
    onControllerChanged: {
        root.initialRefreshRequested = false
        if (root.refreshAllowed) initialRefreshTimer.restart()
    }
    Component.onCompleted: if (root.refreshAllowed) initialRefreshTimer.start()

    Timer {
        id: initialRefreshTimer
        interval: 600
        repeat: false
        onTriggered: root.requestInitialRefresh()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compact ? 10 : 14
        spacing: root.compact ? 4 : 7

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "Today’s queue"
                color: root.inkColor
                font.family: "Segoe UI"
                font.pixelSize: root.compact ? 13 : 15
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            PillButton {
                objectName: "calendarManageButton"
                text: root.hasAccount ? "Manage calendars" : "Connect calendar"
                t: root.t
                appStyle: root.appStyle
                Layout.preferredWidth: root.compact ? 116 : 132
                Layout.preferredHeight: 28
                enabled: root.interactive && !!root.controller
                onClicked: root.openConnectionSettings()
            }
            PillButton {
                objectName: "calendarRefreshButton"
                text: "Refresh"
                t: root.t
                appStyle: root.appStyle
                Layout.preferredWidth: 64
                Layout.preferredHeight: 28
                enabled: root.refreshAllowed && !root.busy
                onClicked: root.refreshAgenda()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: ["Today", "Next 7 days"]
                delegate: PillButton {
                    id: horizonButton
                    required property string modelData
                    required property int index
                    objectName: "calendarHorizon" + horizonButton.index
                    text: horizonButton.modelData
                    t: root.t
                    appStyle: root.appStyle
                    primary: root.selectedHorizon === horizonButton.index
                    Layout.preferredWidth: horizonButton.index === 0 ? 66 : 96
                    Layout.preferredHeight: 27
                    enabled: root.interactive
                    onClicked: root.selectedHorizon = horizonButton.index
                }
            }
            Text {
                Layout.fillWidth: true
                text: String(root.events.length) + (root.events.length === 1 ? " event" : " events")
                color: root.mutedInkColor
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }

        Text {
            objectName: "calendarAgendaStatus"
            Layout.fillWidth: true
            visible: text.length > 0
            text: root.statusLabel()
            color: root.state === "error" || root.state === "partial"
                ? SemanticTheme.tone(root.t, "warning", root.appStyle) : root.mutedInkColor
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        ListView {
            id: agendaList
            objectName: "calendarAgendaList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            interactive: root.interactive
            model: root.events
            spacing: 3
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; enabled: root.interactive }
            section.property: "date"
            section.criteria: ViewSection.FullString
            section.delegate: Text {
                required property string section
                objectName: "calendarDateHeader"
                width: agendaList.width
                height: 25
                text: root.dateLabel(section)
                color: root.mutedInkColor
                font.pixelSize: 10
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
            }
            delegate: Rectangle {
                id: eventRow
                required property var modelData
                width: agendaList.width
                height: eventContent.implicitHeight + 14
                radius: 3
                color: eventRow.modelData.isCurrent
                    ? SemanticTheme.surfaceInput(root.t, root.appStyle) : "transparent"

                Rectangle {
                    width: 3
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.topMargin: 5
                    anchors.bottomMargin: 5
                    radius: 1
                    color: eventRow.modelData.kind === "holiday"
                        ? SemanticTheme.tone(root.t, "success", root.appStyle) : root.accentColor
                }
                ColumnLayout {
                    id: eventContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 10
                    anchors.rightMargin: 8
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: root.eventTimeLabel(eventRow.modelData)
                        color: eventRow.modelData.isCurrent ? root.accentColor : root.mutedInkColor
                        font.pixelSize: 10
                        font.weight: eventRow.modelData.isCurrent ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: String(eventRow.modelData.title || "Untitled event")
                        color: root.inkColor
                        font.family: "Segoe UI"
                        font.pixelSize: root.compact ? 11 : 12
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.sourceLabel(eventRow.modelData)
                            + (eventRow.modelData.location ? " · " + String(eventRow.modelData.location) : "")
                        color: root.mutedInkColor
                        font.pixelSize: 10
                        elide: Text.ElideRight
                    }
                }
                HoverHandler { id: eventHover }
                ToolTip.visible: eventHover.hovered
                ToolTip.text: String(eventRow.modelData.title || "") + "\n"
                    + root.eventTimeLabel(eventRow.modelData) + "\n" + root.sourceLabel(eventRow.modelData)
                TapHandler {
                    enabled: root.interactive && !!root.controller && !!eventRow.modelData.webUrl
                    onTapped: root.controller.openEventLink(String(eventRow.modelData.webUrl))
                }
            }

            Text {
                anchors.fill: parent
                anchors.margins: 6
                visible: root.events.length === 0 && !root.busy
                    && (root.state === "ready" || root.state === "partial")
                text: root.selectedHorizon === 0
                    ? "No remaining meetings or holidays today."
                    : "No meetings or holidays in the next seven days."
                color: root.mutedInkColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                objectName: "calendarRefreshTimestamp"
                Layout.fillWidth: true
                text: (root.agenda.stale ? "Last known · " : "")
                    + (root.agenda.asOf ? "Updated " + root.timeLabel(root.agenda.asOf) + " · " : "")
                    + String(root.agenda.timeZone || "America/Toronto")
                color: root.mutedInkColor
                font.pixelSize: 9
                elide: Text.ElideRight
            }
            Text {
                text: "Practice Briefing ›"
                color: root.accentColor
                font.pixelSize: 10
                TapHandler {
                    enabled: root.interactive
                    onTapped: root.practiceBriefingRequested()
                }
            }
        }
    }

    Loader {
        id: connectionDialogLoader
        active: false
        sourceComponent: Component {
            CalendarConnectionDialog {
                objectName: "calendarConnectionDialog"
                t: root.t
                appStyle: root.appStyle
                controller: root.controller
            }
        }
    }
}
