import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: flyout
    objectName: "minimalistTrayPopup"
    width: 340
    height: 218
    radius: 12
    color: theme.background
    border.width: 1
    border.color: isRunningNow ? theme.timerGreen : theme.border

    SemanticTheme { id: theme }

    readonly property var fallbackEntry: {
        if (typeof trayController === "undefined" || !trayController) return null
        if (trayController.activeTimers && trayController.activeTimers.length > 0) {
            return trayController.activeTimers[0]
        }
        if (trayController.recordedEntries && trayController.recordedEntries.length > 0) {
            return trayController.recordedEntries[0]
        }
        return null
    }

    readonly property string statusBadgeText: {
        if (typeof trayController !== "undefined" && trayController && trayController.displayStatus !== undefined) {
            return String(trayController.displayStatus || "IDLE")
        }
        if (fallbackEntry) {
            if (fallbackEntry.isRunning !== undefined) {
                return fallbackEntry.isRunning ? "RUNNING" : "PAUSED"
            }
            return "LATEST"
        }
        return "IDLE"
    }

    readonly property bool isRunningNow: {
        if (typeof trayController !== "undefined" && trayController && trayController.hasRunningTimer !== undefined) {
            return Boolean(trayController.hasRunningTimer)
        }
        return statusBadgeText === "RUNNING"
    }

    readonly property bool hasActiveOrPaused: {
        if (typeof trayController !== "undefined" && trayController && trayController.hasActiveOrPausedTimer !== undefined) {
            return Boolean(trayController.hasActiveOrPausedTimer)
        }
        return statusBadgeText === "RUNNING" || statusBadgeText === "PAUSED"
    }

    readonly property bool hasEntryToDisplay: {
        if (typeof trayController !== "undefined" && trayController && trayController.hasDisplayEntry !== undefined) {
            return Boolean(trayController.hasDisplayEntry)
        }
        return fallbackEntry !== null
    }

    readonly property string elapsedText: {
        if (typeof trayController !== "undefined" && trayController && trayController.displayElapsedFormatted !== undefined) {
            return String(trayController.displayElapsedFormatted || "00:00:00")
        }
        if (fallbackEntry && typeof trayController !== "undefined" && trayController && trayController.formatElapsed) {
            return String(trayController.formatElapsed(fallbackEntry.elapsed || 0))
        }
        return "00:00:00"
    }

    readonly property string clientNameText: {
        if (typeof trayController !== "undefined" && trayController && trayController.displayClientName !== undefined) {
            var c = String(trayController.displayClientName || "").trim()
            return c.length > 0 ? c : (hasEntryToDisplay ? "No client selected" : "No active or recent timer")
        }
        if (fallbackEntry && fallbackEntry.client) {
            return String(fallbackEntry.client)
        }
        return "No active or recent timer"
    }

    readonly property string matterNameText: {
        if (typeof trayController !== "undefined" && trayController && trayController.displayMatterName !== undefined) {
            var m = String(trayController.displayMatterName || "").trim()
            return m.length > 0 ? m : "No matter selected"
        }
        if (fallbackEntry && fallbackEntry.matter) {
            return String(fallbackEntry.matter)
        }
        return "No matter selected"
    }

    readonly property string descriptionRawText: {
        if (typeof trayController !== "undefined" && trayController && trayController.displayDescription !== undefined) {
            return String(trayController.displayDescription || "")
        }
        if (fallbackEntry && fallbackEntry.description) {
            return String(fallbackEntry.description)
        }
        return ""
    }

    onDescriptionRawTextChanged: {
        if (!descField.activeFocus && descField.text !== descriptionRawText) {
            descField.text = descriptionRawText
        }
    }

    property bool newTimerPickerOpen: false
    property string activeDropdownTarget: ""
    property var clientSuggestions: []
    property var matterSuggestions: []

    function openNewTimerPicker() {
        newClientInput.text = ""
        newMatterInput.text = ""
        newDescInput.text = ""
        activeDropdownTarget = ""
        refreshNewTimerSuggestions()
        newTimerPickerOpen = true
        newClientInput.forceActiveFocus()
    }

    function refreshNewTimerSuggestions() {
        if (typeof trayController === "undefined" || !trayController) {
            clientSuggestions = []
            matterSuggestions = []
            return
        }
        var cQuery = String(newClientInput ? newClientInput.text : "").trim()
        var mQuery = String(newMatterInput ? newMatterInput.text : "").trim()
        try {
            clientSuggestions = trayController.filterClients ? (trayController.filterClients(cQuery) || []) : []
        } catch (e0) {
            clientSuggestions = []
        }
        try {
            matterSuggestions = trayController.filterMattersByClientAndText
                ? (trayController.filterMattersByClientAndText(cQuery, mQuery) || [])
                : []
        } catch (e1) {
            matterSuggestions = []
        }
    }

    function commitNewTimerFromPicker() {
        var cVal = String(newClientInput.text || "").trim()
        var mVal = String(newMatterInput.text || "").trim()
        var dVal = String(newDescInput.text || "").trim()
        if (typeof trayController !== "undefined" && trayController) {
            if (cVal.length <= 0 && mVal.length > 0 && trayController.getClientForMatter) {
                cVal = String(trayController.getClientForMatter(mVal) || "").trim()
            }
            if (trayController.startNewTimerWithDescription) {
                trayController.startNewTimerWithDescription(cVal, mVal, dVal)
            } else if (trayController.start_new_timer) {
                trayController.start_new_timer(cVal, mVal)
                if (dVal.length > 0 && trayController.updatePrimaryDescription) {
                    trayController.updatePrimaryDescription(dVal)
                }
            }
        }
        activeDropdownTarget = ""
        newTimerPickerOpen = false
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8
        visible: !flyout.newTimerPickerOpen

        // 1. Top Row: Status Badge + Live Elapsed Time + Compact Action Controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Rectangle {
                id: statusBadge
                objectName: "trayStatusBadge"
                radius: 5
                height: 22
                implicitWidth: statusLabel.implicitWidth + 12
                color: {
                    if (flyout.statusBadgeText === "RUNNING") return theme.timerGreen
                    if (flyout.statusBadgeText === "PAUSED") return "#D97706"
                    if (flyout.statusBadgeText === "LATEST") return theme.accentBlue
                    return theme.surface
                }
                border.width: flyout.statusBadgeText === "IDLE" ? 1 : 0
                border.color: theme.border

                RowLayout {
                    anchors.centerIn: parent
                    spacing: 4

                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        visible: flyout.isRunningNow
                        color: "#FFFFFF"
                    }

                    Text {
                        id: statusLabel
                        objectName: "trayStatusText"
                        text: flyout.statusBadgeText
                        font.pixelSize: 10
                        font.bold: true
                        font.letterSpacing: 0.5
                        color: flyout.statusBadgeText === "IDLE" ? theme.textSecondary : "#FFFFFF"
                    }
                }
            }

            Text {
                id: elapsedTimeText
                objectName: "trayElapsedText"
                text: flyout.elapsedText
                font.pixelSize: 18
                font.bold: true
                color: flyout.isRunningNow ? theme.timerGreen : theme.textPrimary
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            // Start / Pause / Resume toggle
            Button {
                id: toggleTimerBtn
                objectName: "trayToggleTimerButton"
                visible: flyout.hasEntryToDisplay || flyout.hasActiveOrPaused
                implicitWidth: 52
                implicitHeight: 24
                text: flyout.isRunningNow ? "Pause" : (flyout.statusBadgeText === "PAUSED" ? "Resume" : "Start")
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: toggleTimerBtn.text
                    font: toggleTimerBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: flyout.isRunningNow ? "#D97706" : theme.timerGreen
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.togglePrimaryTimer) {
                        trayController.togglePrimaryTimer()
                    }
                }
            }

            // Stop & Save button (when running or paused)
            Button {
                id: stopSaveBtn
                objectName: "trayStopSaveButton"
                visible: flyout.hasActiveOrPaused
                implicitWidth: 44
                implicitHeight: 24
                text: "Save"
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: stopSaveBtn.text
                    font: stopSaveBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: theme.accentBlue
                }
                onClicked: {
                    if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(descField.text)
                    }
                    if (typeof trayController !== "undefined" && trayController && trayController.stopAndSavePrimaryTimer) {
                        trayController.stopAndSavePrimaryTimer()
                    }
                }
            }

            // + New Timer for a different Client / Matter
            Button {
                id: newTimerBtn
                objectName: "trayNewTimerButton"
                implicitWidth: 46
                implicitHeight: 24
                text: "+ New"
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: newTimerBtn.text
                    font: newTimerBtn.font
                    color: theme.accentBlue
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: theme.surface
                    border.width: 1
                    border.color: theme.accentBlue
                }
                onClicked: {
                    if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(descField.text)
                    }
                    flyout.openNewTimerPicker()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: theme.border
        }

        // 2 & 3. Client Name + Matter Name/Number (clickable to switch matter/start new timer)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: clientMatterCol.implicitHeight + 4
            radius: 5
            color: switchMatterMouse.containsMouse ? theme.surface : "transparent"

            ColumnLayout {
                id: clientMatterCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        id: clientLabel
                        objectName: "trayClientNameText"
                        Layout.fillWidth: true
                        text: flyout.clientNameText
                        font.pixelSize: 14
                        font.bold: true
                        color: theme.textPrimary
                        elide: Text.ElideRight
                    }

                    Text {
                        text: "Switch ▾"
                        font.pixelSize: 10
                        color: theme.accentBlue
                        visible: switchMatterMouse.containsMouse
                    }
                }

                Text {
                    id: matterLabel
                    objectName: "trayMatterNameText"
                    Layout.fillWidth: true
                    text: flyout.matterNameText
                    font.pixelSize: 12
                    color: theme.textSecondary
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: switchMatterMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: flyout.openNewTimerPicker()
            }
        }

        // 4. Current Docket Description (editable inline with muted "No description" placeholder)
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            radius: 6
            color: theme.surface
            border.width: descField.activeFocus ? 1 : 0
            border.color: theme.accentBlue

            TextField {
                id: descField
                objectName: "trayDescriptionInput"
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                text: flyout.descriptionRawText
                placeholderText: "No description"
                placeholderTextColor: theme.textSecondary
                color: theme.textPrimary
                font.pixelSize: 12
                selectByMouse: true
                verticalAlignment: TextInput.AlignVCenter
                background: Item {}
                onEditingFinished: {
                    if (typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(text)
                    }
                }
                onAccepted: {
                    if (typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(text)
                    }
                    focus = false
                }
            }
        }

        // Compact Footer: Open CSPM & Quit
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: (typeof trayController !== "undefined" && trayController && trayController.currentDate) ? String(trayController.currentDate) : ""
                font.pixelSize: 11
                color: theme.textSecondary
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Button {
                id: openAppBtn
                objectName: "trayOpenCspmButton"
                implicitHeight: 24
                implicitWidth: 86
                text: "Open CSPM"
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: openAppBtn.text
                    font: openAppBtn.font
                    color: theme.accentBlue
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: "transparent"
                    border.width: 1
                    border.color: theme.border
                }
                onClicked: {
                    if (Window.window) Window.window.hide()
                    if (typeof trayController !== "undefined" && trayController && trayController.open_cspm) {
                        trayController.open_cspm()
                    }
                }
            }

            Button {
                id: quitAppBtn
                objectName: "trayQuitButton"
                implicitHeight: 24
                implicitWidth: 48
                text: "Quit"
                font.pixelSize: 11
                contentItem: Text {
                    text: quitAppBtn.text
                    font: quitAppBtn.font
                    color: theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: "transparent"
                    border.width: 1
                    border.color: theme.border
                }
                onClicked: {
                    if (Window.window) Window.window.hide()
                    if (typeof trayController !== "undefined" && trayController && trayController.exit_cspm) {
                        trayController.exit_cspm()
                    }
                }
            }
        }
    }

    // Inline New Timer / Matter Switcher View (fits inside the 340x218 flyout)
    Item {
        id: newTimerOverlay
        objectName: "trayNewTimerPicker"
        anchors.fill: parent
        anchors.margins: 10
        visible: flyout.newTimerPickerOpen

        ColumnLayout {
            anchors.fill: parent
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "New Timer (00:00:00)"
                    font.pixelSize: 12
                    font.bold: true
                    color: theme.textPrimary
                    Layout.fillWidth: true
                }

                Button {
                    id: cancelNewTimerBtn
                    objectName: "trayCancelNewTimerButton"
                    implicitWidth: 52
                    implicitHeight: 22
                    text: "Cancel"
                    font.pixelSize: 11
                    contentItem: Text {
                        text: cancelNewTimerBtn.text
                        font: cancelNewTimerBtn.font
                        color: theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 5
                        color: "transparent"
                        border.width: 1
                        border.color: theme.border
                    }
                    onClicked: {
                        flyout.activeDropdownTarget = ""
                        flyout.newTimerPickerOpen = false
                    }
                }

                Button {
                    id: confirmStartNewTimerBtn
                    objectName: "trayConfirmStartNewTimerButton"
                    implicitWidth: 54
                    implicitHeight: 22
                    text: "Start"
                    font.pixelSize: 11
                    font.bold: true
                    contentItem: Text {
                        text: confirmStartNewTimerBtn.text
                        font: confirmStartNewTimerBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.timerGreen
                    }
                    onClicked: flyout.commitNewTimerFromPicker()
                }
            }

            // Client selector row
            Rectangle {
                id: clientInputBox
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                radius: 5
                color: theme.surface
                border.width: 1
                border.color: newClientInput.activeFocus || flyout.activeDropdownTarget === "client" ? theme.accentBlue : theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 4

                    TextField {
                        id: newClientInput
                        objectName: "trayNewClientInput"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "Select or search Client..."
                        placeholderTextColor: theme.textSecondary
                        color: theme.textPrimary
                        font.pixelSize: 12
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Item {}
                        onActiveFocusChanged: {
                            if (activeFocus) {
                                flyout.refreshNewTimerSuggestions()
                                flyout.activeDropdownTarget = "client"
                            }
                        }
                        onTextEdited: {
                            flyout.refreshNewTimerSuggestions()
                            flyout.activeDropdownTarget = "client"
                        }
                        onAccepted: flyout.commitNewTimerFromPicker()
                    }

                    Text {
                        text: flyout.activeDropdownTarget === "client" ? "▴" : "▾"
                        font.pixelSize: 11
                        color: theme.textSecondary
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                flyout.refreshNewTimerSuggestions()
                                flyout.activeDropdownTarget = (flyout.activeDropdownTarget === "client" ? "" : "client")
                            }
                        }
                    }
                }
            }

            // Matter selector row
            Rectangle {
                id: matterInputBox
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                radius: 5
                color: theme.surface
                border.width: 1
                border.color: newMatterInput.activeFocus || flyout.activeDropdownTarget === "matter" ? theme.accentBlue : theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 4

                    TextField {
                        id: newMatterInput
                        objectName: "trayNewMatterInput"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "Select or search Matter..."
                        placeholderTextColor: theme.textSecondary
                        color: theme.textPrimary
                        font.pixelSize: 12
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Item {}
                        onActiveFocusChanged: {
                            if (activeFocus) {
                                flyout.refreshNewTimerSuggestions()
                                flyout.activeDropdownTarget = "matter"
                            }
                        }
                        onTextEdited: {
                            flyout.refreshNewTimerSuggestions()
                            flyout.activeDropdownTarget = "matter"
                        }
                        onAccepted: flyout.commitNewTimerFromPicker()
                    }

                    Text {
                        text: flyout.activeDropdownTarget === "matter" ? "▴" : "▾"
                        font.pixelSize: 11
                        color: theme.textSecondary
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                flyout.refreshNewTimerSuggestions()
                                flyout.activeDropdownTarget = (flyout.activeDropdownTarget === "matter" ? "" : "matter")
                            }
                        }
                    }
                }
            }

            // Description input row (hidden while dropdown list is open so dropdown list has room)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                visible: flyout.activeDropdownTarget === ""
                radius: 5
                color: theme.surface
                border.width: newDescInput.activeFocus ? 1 : 0
                border.color: theme.accentBlue

                TextField {
                    id: newDescInput
                    objectName: "trayNewDescriptionInput"
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    placeholderText: "Description (optional)..."
                    placeholderTextColor: theme.textSecondary
                    color: theme.textPrimary
                    font.pixelSize: 12
                    selectByMouse: true
                    verticalAlignment: TextInput.AlignVCenter
                    background: Item {}
                    onAccepted: flyout.commitNewTimerFromPicker()
                }
            }

            // Inline dropdown suggestion list (when selecting Client or Matter)
            Rectangle {
                id: suggestionListBox
                objectName: "traySuggestionListBox"
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: flyout.activeDropdownTarget !== ""
                radius: 5
                color: theme.surface
                border.width: 1
                border.color: theme.border
                clip: true

                ListView {
                    id: suggestionListView
                    anchors.fill: parent
                    anchors.margins: 2
                    model: flyout.activeDropdownTarget === "client" ? flyout.clientSuggestions : flyout.matterSuggestions
                    delegate: Rectangle {
                        width: suggestionListView.width
                        height: 24
                        radius: 4
                        color: itemMouse.containsMouse ? theme.accentBlue : "transparent"

                        Text {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: String(modelData || "")
                            font.pixelSize: 11
                            color: itemMouse.containsMouse ? "#FFFFFF" : theme.textPrimary
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var chosen = String(modelData || "")
                                if (flyout.activeDropdownTarget === "client") {
                                    newClientInput.text = chosen
                                    flyout.refreshNewTimerSuggestions()
                                    if (flyout.matterSuggestions.length === 1) {
                                        newMatterInput.text = String(flyout.matterSuggestions[0] || "")
                                        flyout.activeDropdownTarget = ""
                                    } else {
                                        newMatterInput.text = ""
                                        flyout.refreshNewTimerSuggestions()
                                        flyout.activeDropdownTarget = "matter"
                                    }
                                } else {
                                    newMatterInput.text = chosen
                                    if (typeof trayController !== "undefined" && trayController && trayController.getClientForMatter) {
                                        var resolvedC = String(trayController.getClientForMatter(chosen) || "").trim()
                                        if (resolvedC.length > 0) {
                                            newClientInput.text = resolvedC
                                        }
                                    }
                                    flyout.activeDropdownTarget = ""
                                }
                            }
                        }
                    }
                }
            }

            Item {
                Layout.fillHeight: true
                visible: flyout.activeDropdownTarget === ""
            }
        }
    }
}

