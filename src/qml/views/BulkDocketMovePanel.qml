import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../components"

Item {
    id: root

    property var appRef
    property var backend
    property var t
    property color surfaceColor: "#ffffff"
    property color canvasColor: "#f7f9fc"
    property color inputColor: "#ffffff"
    property color textColor: "#17243a"
    property color mutedColor: "#65758a"
    property color borderColor: "#cbd6e3"
    property color accentColor: "#30445f"
    property bool isDark: false

    property var matterOptions: []
    property var matterLabels: []
    property string sourceMatterId: ""
    property string targetMatterId: ""
    property var candidates: []
    property var selectedEntryIds: ({})
    property bool previewBusy: false
    property bool moveBusy: false
    property string statusMessage: "Choose the source matter and date range, then review the dockets before moving them."
    property bool statusIsError: false
    property int blockedCount: 0
    property string datePickerTarget: ""
    property string lastPreviewFromDate: ""
    property string lastPreviewToDate: ""

    SelectionRemovalNoticeDialog {
        id: selectionRemovalNotice
        t: root.t
        appStyle: root.appRef && root.appRef.appStyle ? String(root.appRef.appStyle) : "Professional"
    }

    readonly property int selectedCount: {
        var count = 0
        for (var i = 0; i < candidates.length; ++i) {
            if (selectedEntryIds[String(candidates[i].entryId)]) count++
        }
        return count
    }

    function todayText() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function firstDayOfMonthText() {
        var now = new Date()
        return Qt.formatDate(new Date(now.getFullYear(), now.getMonth(), 1), "yyyy-MM-dd")
    }

    function parseIsoDateOrToday(textValue) {
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(textValue || "").trim())
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year
                    && candidate.getMonth() === monthIndex
                    && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function openDatePicker(targetKey, anchorItem, px, py) {
        datePickerTarget = String(targetKey || "")
        bulkMoveCalendarLoader.active = true
        Qt.callLater(function() {
            var calendar = bulkMoveCalendarLoader.item
            if (!calendar) return
            var field = datePickerTarget === "from" ? fromDateField : toDateField
            calendar.selectedDate = root.parseIsoDateOrToday(field.text)
            // JellyCalendar resolves this global point to its containing
            // monitor and centres its own window on that monitor.
            if (typeof calendar.openAt === "function") calendar.openAt(px, py)
            else if (typeof calendar.open === "function") calendar.open()
            else calendar.visible = true
        })
    }

    function clearPreviewForChangedDateRange() {
        if (root.candidates.length <= 0 && root.selectedCount <= 0) return
        if (root.lastPreviewFromDate === fromDateField.text
                && root.lastPreviewToDate === toDateField.text) return
        root.clearPreview(
            "Choose a date range and find eligible dockets.",
            "You changed the date range, so the previous candidate selection no longer applies."
        )
    }

    function matterLabelForId(matterId) {
        var wanted = String(matterId || "").trim()
        for (var i = 0; i < matterOptions.length; ++i) {
            if (String(matterOptions[i].matterId || "") === wanted)
                return String(matterOptions[i].label || "Select a matter...")
        }
        return "Select a matter..."
    }

    function matterIdForLabel(labelText) {
        var wanted = String(labelText || "").trim()
        for (var i = 0; i < matterOptions.length; ++i) {
            if (String(matterOptions[i].label || "") === wanted)
                return String(matterOptions[i].matterId || "")
        }
        return ""
    }

    function refreshMatterOptions() {
        if (!appRef) return
        var rows = []
        try {
            rows = appRef.listActiveMatterDirectory ? appRef.listActiveMatterDirectory() : []
            if ((!rows || rows.length === 0) && appRef.listMatterDirectory)
                rows = appRef.listMatterDirectory()
        } catch (error) {
            rows = []
        }
        var options = [{ "matterId": "", "label": "Select a matter...", "clientId": "" }]
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i] || ({})
            var matterId = String(row.matterId || row.Matter_ID || "").trim()
            if (!matterId.length) continue
            var clientName = String(row.clientName || row.ClientName || row.Client_Name
                || row.client || row.Client || row.clientId || row.Client_ID || "Unassigned client").trim()
            var matterDescription = String(row.matterName || row.Matter_Name || row.description
                || row.Description || row.displayName || matterId).trim()
            var matterNumber = String(row.matterNumber || row.MatterNumber || row.Matter_Number || matterId).trim()
            var label = clientName + " | " + matterDescription + " | " + matterNumber
            options.push({
                "matterId": matterId,
                "label": label,
                "clientId": String(row.clientId || row.Client_ID || "").trim(),
                "clientName": clientName,
                "matterDescription": matterDescription,
                "matterNumber": matterNumber
            })
        }
        options.sort(function(left, right) {
            if (!left.matterId.length) return -1
            if (!right.matterId.length) return 1
            return String(left.label).localeCompare(String(right.label))
        })
        matterOptions = options
        var labels = []
        for (var j = 0; j < options.length; ++j)
            labels.push(String(options[j].label || ""))
        matterLabels = labels
    }

    function clearPreview(message, selectionReason) {
        var removedCount = 0
        for (var entryId in selectedEntryIds) {
            if (selectedEntryIds[entryId]) removedCount++
        }
        candidates = []
        selectedEntryIds = ({})
        blockedCount = 0
        if (message !== undefined) {
            statusMessage = String(message)
            statusIsError = false
        }
        if (removedCount > 0) {
            selectionRemovalNotice.showRemoval(
                removedCount,
                "docket",
                String(selectionReason || "The candidate worklist was reset, so those dockets no longer belong to the current selection.")
            )
        }
    }

    function selectAll(select) {
        var next = ({})
        if (select) {
            for (var i = 0; i < candidates.length; ++i)
                next[String(candidates[i].entryId)] = true
        }
        selectedEntryIds = next
    }

    function setEntrySelected(entryId, selected) {
        var next = ({})
        for (var key in selectedEntryIds) next[key] = selectedEntryIds[key]
        if (selected) next[String(entryId)] = true
        else delete next[String(entryId)]
        selectedEntryIds = next
    }

    function loadPreview() {
        if (!sourceMatterId.length) {
            statusMessage = "Select the matter that currently owns the dockets."
            statusIsError = true
            return
        }
        if (!backend || !backend.previewBulkDocketMove) {
            statusMessage = "The bulk docket move service is unavailable."
            statusIsError = true
            return
        }
        previewBusy = true
        statusIsError = false
        statusMessage = "Finding eligible dockets…"
        backend.previewBulkDocketMove({
            "sourceMatterId": sourceMatterId,
            "fromDate": fromDateField.text,
            "toDate": toDateField.text
        })
    }

    function requestMove() {
        if (!targetMatterId.length) {
            statusMessage = "Select the destination matter."
            statusIsError = true
            return
        }
        if (selectedCount <= 0) {
            statusMessage = "Select at least one eligible docket to move."
            statusIsError = true
            return
        }
        confirmationPopup.open()
    }

    function moveSelected() {
        if (!backend || !backend.moveDocketsToMatter) {
            statusMessage = "The bulk docket move service is unavailable."
            statusIsError = true
            return
        }
        var ids = []
        for (var i = 0; i < candidates.length; ++i) {
            var entryId = String(candidates[i].entryId)
            if (selectedEntryIds[entryId]) ids.push(entryId)
        }
        moveBusy = true
        statusIsError = false
        statusMessage = "Moving " + ids.length + " docket" + (ids.length === 1 ? "…" : "s…")
        backend.moveDocketsToMatter({
            "sourceMatterId": sourceMatterId,
            "targetMatterId": targetMatterId,
            "fromDate": fromDateField.text,
            "toDate": toDateField.text,
            "entryIds": ids
        })
    }

    Component.onCompleted: refreshMatterOptions()

    Connections {
        target: root.backend
        ignoreUnknownSignals: true

        function onBulkDocketMovePreviewFinished(result) {
            root.previewBusy = false
            var response = result || ({})
            if (!response.ok) {
                root.clearPreview(String(response.message || "Could not find movable dockets."))
                root.statusIsError = true
                return
            }
            var priorSelection = root.selectedEntryIds
            var hadPreviousPreview = root.candidates.length > 0
            root.candidates = response.candidates || []
            root.blockedCount = Number(response.blockedCount || 0)
            root.lastPreviewFromDate = fromDateField.text
            root.lastPreviewToDate = toDateField.text
            if (!hadPreviousPreview) {
                root.selectAll(true)
            } else {
                var available = ({})
                var preserved = ({})
                var removedCount = 0
                for (var candidateIndex = 0; candidateIndex < root.candidates.length; ++candidateIndex)
                    available[String(root.candidates[candidateIndex].entryId)] = true
                for (var selectedId in priorSelection) {
                    if (!priorSelection[selectedId]) continue
                    if (available[selectedId]) preserved[selectedId] = true
                    else removedCount++
                }
                root.selectedEntryIds = preserved
                if (removedCount > 0) {
                    selectionRemovalNotice.showRemoval(
                        removedCount,
                        "docket",
                        "The candidate worklist was refreshed and these dockets are no longer eligible to move."
                    )
                }
            }
            var matched = Number(response.matchedCount || 0)
            root.statusIsError = false
            if (root.candidates.length > 0) {
                root.statusMessage = root.candidates.length + " eligible docket" + (root.candidates.length === 1 ? "" : "s")
                    + " found and selected."
                if (root.blockedCount > 0)
                    root.statusMessage += " " + root.blockedCount + " invoice-linked docket" + (root.blockedCount === 1 ? " was" : "s were") + " excluded."
            } else if (matched > 0) {
                root.statusMessage = "All " + matched + " matching dockets are already invoice-linked and cannot be moved here."
            } else {
                root.statusMessage = "No dockets matched that matter and date range."
            }
        }

        function onBulkDocketMoveFinished(result) {
            root.moveBusy = false
            var response = result || ({})
            if (!response.ok) {
                root.statusMessage = String(response.message || "Could not move the selected dockets.")
                root.statusIsError = true
                return
            }
            root.statusIsError = false
            root.statusMessage = "Moved " + Number(response.movedCount || 0) + " docket"
                + (Number(response.movedCount || 0) === 1 ? "" : "s") + " to the destination matter."
            moveSuccessPopup.movedCount = Number(response.movedCount || 0)
            moveSuccessPopup.destinationLabel = root.matterLabelForId(root.targetMatterId)
            moveSuccessPopup.open()
            root.selectAll(false)
            root.loadPreview()
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onClientDataChanged() { root.refreshMatterOptions() }
        function onBackendBootChanged() { root.refreshMatterOptions() }
    }

    Loader {
        id: bulkMoveCalendarLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                hostWindow: root.Window.window
                onDatePicked: function(dateValue) {
                    var field = root.datePickerTarget === "from" ? fromDateField : toDateField
                    var nextText = Qt.formatDate(dateValue, "yyyy-MM-dd")
                    var changed = field.text !== nextText
                    field.text = nextText
                    root.datePickerTarget = ""
                    bulkMoveCalendarLoader.active = false
                    if (changed) root.clearPreviewForChangedDateRange()
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 74
            color: root.isDark ? "#303a47" : "#edf5ff"
            border.color: root.accentColor
            border.width: 1
            radius: 6

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Text { text: "Move dockets between matters"; color: root.textColor; font.pixelSize: 17; font.weight: Font.DemiBold }
                    Text {
                        Layout.fillWidth: true
                        text: "Moves selected unbilled time and fee dockets only, updating them to the destination matter's client. Invoice-linked dockets remain protected."
                        color: root.mutedColor
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }
                PillButton {
                    t: root.t
                    text: "Refresh matters"
                    primary: false
                    Layout.preferredWidth: 128
                    Layout.preferredHeight: 32
                    onClicked: root.refreshMatterOptions()
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 12
            rowSpacing: 7

            Text { text: "From matter"; color: root.mutedColor; font.pixelSize: 11; font.weight: Font.DemiBold }
            Text { text: "From date"; color: root.mutedColor; font.pixelSize: 11; font.weight: Font.DemiBold }
            Text { text: "To date"; color: root.mutedColor; font.pixelSize: 11; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }

            ModernComboBox {
                id: sourceMatterCombo
                t: root.t
                appStyle: root.appRef && root.appRef.appStyle ? String(root.appRef.appStyle) : "Professional"
                Layout.fillWidth: true
                Layout.minimumWidth: 250
                Layout.preferredHeight: 42
                fullModel: root.matterLabels
                editText: root.matterLabelForId(root.sourceMatterId)
                emptyOptionLabel: "Select a matter..."
                onActivated: {
                    root.sourceMatterId = root.matterIdForLabel(editText)
                    root.clearPreview(
                        "Choose a date range and find eligible dockets.",
                        "You changed the source matter, so the previous candidate selection no longer applies."
                    )
                }
            }

            TextField {
                id: fromDateField
                Layout.preferredWidth: 124
                Layout.preferredHeight: 42
                text: root.firstDayOfMonthText()
                placeholderText: "YYYY-MM-DD"
                placeholderTextColor: root.mutedColor
                color: root.textColor
                font.pixelSize: 12
                verticalAlignment: TextInput.AlignVCenter
                leftPadding: 9
                rightPadding: 9
                background: Rectangle { color: root.inputColor; border.color: root.borderColor; border.width: 1; radius: 4 }
                onEditingFinished: root.clearPreviewForChangedDateRange()
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    propagateComposedEvents: true
                    onDoubleClicked: function(mouse) {
                        var point = mapToGlobal(mouse.x, mouse.y)
                        root.openDatePicker("from", fromDateField, point.x, point.y)
                    }
                    onPressed: function(mouse) { mouse.accepted = false }
                }
            }

            TextField {
                id: toDateField
                Layout.preferredWidth: 124
                Layout.preferredHeight: 42
                text: root.todayText()
                placeholderText: "YYYY-MM-DD"
                placeholderTextColor: root.mutedColor
                color: root.textColor
                font.pixelSize: 12
                verticalAlignment: TextInput.AlignVCenter
                leftPadding: 9
                rightPadding: 9
                background: Rectangle { color: root.inputColor; border.color: root.borderColor; border.width: 1; radius: 4 }
                onEditingFinished: root.clearPreviewForChangedDateRange()
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    propagateComposedEvents: true
                    onDoubleClicked: function(mouse) {
                        var point = mapToGlobal(mouse.x, mouse.y)
                        root.openDatePicker("to", toDateField, point.x, point.y)
                    }
                    onPressed: function(mouse) { mouse.accepted = false }
                }
            }

            PillButton {
                t: root.t
                text: root.previewBusy ? "Finding…" : "Find eligible dockets"
                primary: true
                enabled: !root.previewBusy && !root.moveBusy
                Layout.preferredWidth: 164
                Layout.preferredHeight: 42
                onClicked: root.loadPreview()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: root.borderColor
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                Layout.fillWidth: true
                text: root.statusMessage
                color: root.statusIsError ? "#b42318" : root.mutedColor
                font.pixelSize: 12
                elide: Text.ElideRight
            }
            PillButton { t: root.t; text: "Select all"; primary: false; enabled: root.candidates.length > 0 && !root.moveBusy; Layout.preferredWidth: 88; Layout.preferredHeight: 30; onClicked: root.selectAll(true) }
            PillButton { t: root.t; text: "Clear"; primary: false; enabled: root.selectedCount > 0 && !root.moveBusy; Layout.preferredWidth: 70; Layout.preferredHeight: 30; onClicked: root.selectAll(false) }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 190
            color: root.canvasColor
            border.color: root.borderColor
            border.width: 1
            radius: 6

            ListView {
                id: docketList
                anchors.fill: parent
                anchors.margins: 6
                clip: true
                spacing: 5
                model: root.candidates
                delegate: Rectangle {
                    required property var modelData
                    width: docketList.width
                    height: 48
                    color: root.selectedEntryIds[String(modelData.entryId)]
                        ? (root.isDark ? "#344557" : "#e8f1fc") : root.surfaceColor
                    border.color: root.borderColor
                    border.width: 1
                    radius: 4

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8
                        CheckBox {
                            checked: !!root.selectedEntryIds[String(modelData.entryId)]
                            onToggled: root.setEntrySelected(modelData.entryId, checked)
                        }
                        Text { Layout.preferredWidth: 86; text: modelData.date; color: root.mutedColor; font.pixelSize: 11 }
                        Text { Layout.preferredWidth: 44; text: modelData.isFee ? "Fee" : "Time"; color: root.mutedColor; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Text { Layout.fillWidth: true; text: modelData.description; color: root.textColor; font.pixelSize: 12; elide: Text.ElideRight }
                        Text { Layout.preferredWidth: 56; visible: !modelData.isFee; text: Number(modelData.hours || 0).toFixed(2) + " h"; color: root.mutedColor; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 92; text: "$" + Number(modelData.amount || 0).toFixed(2); color: root.textColor; font.pixelSize: 12; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight }
                    }
                }
                ScrollBar.vertical: ScrollBar { }
            }

            Text {
                anchors.centerIn: parent
                visible: root.candidates.length === 0 && !root.previewBusy
                text: "No eligible dockets loaded."
                color: root.mutedColor
                font.pixelSize: 13
            }
            BusyIndicator { anchors.centerIn: parent; running: root.previewBusy; visible: running }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 82
            color: root.surfaceColor
            border.color: root.borderColor
            border.width: 1
            radius: 6

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12
                ColumnLayout {
                    Layout.preferredWidth: 145
                    spacing: 3
                    Text { text: "Move to matter"; color: root.textColor; font.pixelSize: 13; font.weight: Font.DemiBold }
                    Text { text: root.selectedCount + " docket" + (root.selectedCount === 1 ? " selected" : "s selected"); color: root.mutedColor; font.pixelSize: 11 }
                }
                ModernComboBox {
                    id: targetMatterCombo
                    t: root.t
                    appStyle: root.appRef && root.appRef.appStyle ? String(root.appRef.appStyle) : "Professional"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 280
                    Layout.preferredHeight: 42
                    fullModel: root.matterLabels
                    editText: root.matterLabelForId(root.targetMatterId)
                    emptyOptionLabel: "Select a matter..."
                    onActivated: root.targetMatterId = root.matterIdForLabel(editText)
                }
                PillButton {
                    t: root.t
                    text: root.moveBusy ? "Moving…" : "Move selected"
                    primary: true
                    enabled: root.selectedCount > 0 && root.targetMatterId.length > 0 && !root.previewBusy && !root.moveBusy
                    Layout.preferredWidth: 138
                    Layout.preferredHeight: 42
                    onClicked: root.requestMove()
                }
            }
        }
    }

    Popup {
        id: confirmationPopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(520, root.width - 40)
        padding: 18
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: root.surfaceColor; border.color: root.borderColor; border.width: 1; radius: 6 }
        contentItem: ColumnLayout {
            spacing: 12
            Text { Layout.fillWidth: true; text: "Confirm docket move"; color: root.textColor; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text {
                Layout.fillWidth: true
                text: "Move " + root.selectedCount + " selected unbilled docket" + (root.selectedCount === 1 ? "" : "s")
                    + " to the destination matter? This changes their matter assignment and records an audit note."
                color: root.mutedColor
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                PillButton { t: root.t; text: "Cancel"; primary: false; Layout.preferredWidth: 88; Layout.preferredHeight: 34; onClicked: confirmationPopup.close() }
                PillButton { t: root.t; text: "Move dockets"; primary: true; Layout.preferredWidth: 120; Layout.preferredHeight: 34; onClicked: { confirmationPopup.close(); root.moveSelected() } }
            }
        }
    }

    Popup {
        id: moveSuccessPopup
        property int movedCount: 0
        property string destinationLabel: ""
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(560, root.width - 40)
        padding: 22
        closePolicy: Popup.NoAutoClose
        background: Rectangle {
            color: root.surfaceColor
            border.color: "#16835a"
            border.width: 2
            radius: 8
        }
        contentItem: ColumnLayout {
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Rectangle {
                    Layout.preferredWidth: 38
                    Layout.preferredHeight: 38
                    radius: 19
                    color: "#16835a"
                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        color: "white"
                        font.pixelSize: 23
                        font.weight: Font.DemiBold
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: "Dockets moved successfully"
                    color: root.textColor
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                }
            }
            Text {
                Layout.fillWidth: true
                text: moveSuccessPopup.movedCount + " selected unbilled docket"
                    + (moveSuccessPopup.movedCount === 1 ? " was" : "s were")
                    + " moved to the destination matter."
                color: root.textColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                text: "Destination: " + moveSuccessPopup.destinationLabel
                color: root.mutedColor
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                text: "The source worklist has been refreshed. An audit note was recorded for the move."
                color: root.mutedColor
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                PillButton {
                    t: root.t
                    text: "OK"
                    primary: true
                    Layout.preferredWidth: 104
                    Layout.preferredHeight: 38
                    onClicked: moveSuccessPopup.close()
                }
            }
        }
    }
}
