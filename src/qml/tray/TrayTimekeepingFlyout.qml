import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Rectangle {
    id: flyout
    objectName: "minimalistTrayPopup"
    width: 380
    height: 280
    radius: 12
    color: theme.background
    border.width: 1
    border.color: isRunningNow ? theme.timerGreen : theme.border

    signal minimizeRequested()

    SemanticTheme { id: theme }

    readonly property var todayTabsModel: {
        if (typeof trayController !== "undefined" && trayController && trayController.todayDocketTabs !== undefined) {
            return trayController.todayDocketTabs || []
        }
        return []
    }

    readonly property string activeTabId: {
        if (typeof trayController !== "undefined" && trayController && trayController.selectedTabId !== undefined) {
            return String(trayController.selectedTabId || "")
        }
        return ""
    }

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
            return Boolean(trayController.hasRunningTimer) && statusBadgeText === "RUNNING"
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
            return c.length > 0 ? c : (hasEntryToDisplay ? "No client selected (Click to choose)" : "No active or recent timer")
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

    readonly property bool simTimerWarningOpen: {
        if (typeof trayController !== "undefined" && trayController && trayController.simultaneousTimerWarningVisible !== undefined) {
            return Boolean(trayController.simultaneousTimerWarningVisible)
        }
        return false
    }

    readonly property string simTimerWarningMsg: {
        if (typeof trayController !== "undefined" && trayController && trayController.simultaneousTimerWarningMessage !== undefined) {
            var m = String(trayController.simultaneousTimerWarningMessage || "").trim()
            if (m.length > 0) return m
        }
        return "Another timer is already running. What would you like to do?"
    }

    readonly property bool legacyConflictOpen: {
        if (typeof trayController !== "undefined" && trayController && trayController.hasLegacySyncConflict !== undefined) {
            return Boolean(trayController.hasLegacySyncConflict)
        }
        return false
    }

    readonly property var legacyConflictData: {
        if (typeof trayController !== "undefined" && trayController && trayController.legacySyncConflict !== undefined) {
            return trayController.legacySyncConflict || ({})
        }
        return ({})
    }

    property int selectedConflictRowNumber: 0
    property bool confirmBilledOverwriteArmed: false

    onLegacyConflictDataChanged: {
        confirmBilledOverwriteArmed = false
        if (legacyConflictData && legacyConflictData.selectedTargetRow) {
            selectedConflictRowNumber = Number(legacyConflictData.selectedTargetRow || 0)
        } else if (legacyConflictData && legacyConflictData.existingRows && legacyConflictData.existingRows.length > 0) {
            selectedConflictRowNumber = Number(legacyConflictData.existingRows[0].rowNumber || 0)
        } else {
            selectedConflictRowNumber = 0
        }
    }

    readonly property var selectedExistingRowObj: {
        var rows = (legacyConflictData && legacyConflictData.existingRows) ? legacyConflictData.existingRows : []
        for (var i = 0; i < rows.length; i++) {
            if (Number(rows[i].rowNumber || 0) === flyout.selectedConflictRowNumber) {
                return rows[i]
            }
        }
        return rows.length > 0 ? rows[0] : ({})
    }

    readonly property bool selectedRowIsBilled: {
        var rowObj = flyout.selectedExistingRowObj || ({})
        return Boolean(rowObj.isBilled) || String(rowObj.invoice || "").trim().length > 0
    }

    readonly property bool crashRecoveryOpen: {
        if (typeof trayController !== "undefined" && trayController && trayController.hasCrashRecoveryPrompt !== undefined) {
            return Boolean(trayController.hasCrashRecoveryPrompt)
        }
        return false
    }

    readonly property var crashRecoveryData: {
        if (typeof trayController !== "undefined" && trayController && trayController.currentCrashRecoveryDocket !== undefined) {
            return trayController.currentCrashRecoveryDocket || ({})
        }
        return ({})
    }

    property string crashRecoveryTimeOption: "heartbeat"
    property bool crashRecoveryDiscardArmed: false

    onCrashRecoveryDataChanged: {
        crashRecoveryTimeOption = "heartbeat"
        crashRecoveryDiscardArmed = false
    }

    readonly property bool closeSafeguardOpen: {
        if (typeof trayController !== "undefined" && trayController && trayController.closeSafeguardVisible !== undefined) {
            return Boolean(trayController.closeSafeguardVisible)
        }
        return false
    }

    readonly property string closeSafeguardMsg: {
        if (typeof trayController !== "undefined" && trayController && trayController.closeSafeguardMessage !== undefined) {
            var m = String(trayController.closeSafeguardMessage || "").trim()
            if (m.length > 0) return m
        }
        return "You have active or paused dockets with unsaved time. How would you like to proceed before closing CSPM?"
    }

    onDescriptionRawTextChanged: {
        if (!descField.activeFocus && descField.text !== descriptionRawText) {
            descField.text = descriptionRawText
        }
    }

    property bool newTimerPickerOpen: false
    property bool pickerAssignsCurrentTab: false
    property bool editingElapsedInline: false
    property string activeDropdownTarget: ""
    property var clientSuggestions: []
    property var matterSuggestions: []

    property bool deleteConfirmOpen: false
    property string pendingDeleteTabId: ""
    property string pendingDeleteSummaryLabel: ""
    property string pendingDeleteElapsedFormatted: "00:00:00"
    property string pendingDeleteDescription: ""
    property string pendingCancelKind: ""
    property bool pendingCancelRunning: false
    property bool pendingCancelHasTime: false
    property string pendingCancelSavedFormatted: "00:00:00"
    property string pendingCancelUnsavedFormatted: "00:00:00"

    readonly property var activeTabObject: {
        var tabs = flyout.todayTabsModel || []
        for (var i = 0; i < tabs.length; i++) {
            if (String(tabs[i].tabId || "") === flyout.activeTabId) {
                return tabs[i]
            }
        }
        return tabs.length > 0 ? tabs[0] : null
    }

    // A tab is a SAVED docket only when the backend reports it as SAVED. Resumed saved
    // dockets (RUNNING/PAUSED) and unsaved drafts can be cancelled; saved ones cannot.
    readonly property bool isCurrentTabSavedDocket: {
        var t = flyout.activeTabObject
        if (t) {
            return String(t.status || "") === "SAVED"
        }
        return flyout.statusBadgeText === "LATEST" || flyout.statusBadgeText === "SAVED"
    }

    Shortcut {
        sequence: "Ctrl+Delete"
        context: Qt.WindowShortcut
        onActivated: {
            flyout.requestCancelOrDeleteTab(flyout.activeTabId, false)
        }
    }

    function findTabObjectById(tabId) {
        var cleanId = String(tabId || flyout.activeTabId || "").trim()
        var tabs = flyout.todayTabsModel || []
        for (var i = 0; i < tabs.length; i++) {
            if (String(tabs[i].tabId || "") === cleanId) {
                return tabs[i]
            }
        }
        return cleanId === flyout.activeTabId ? flyout.activeTabObject : null
    }

    // Tray Cancel: unsaved timers/drafts only. Always asks what to do (never deletes saved dockets).
    function requestCancelOrDeleteTab(tabId, fromTabClose) {
        if (flyout.editingElapsedInline) {
            flyout.commitInlineManualTime()
        }
        if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
            trayController.updatePrimaryDescription(descField.text)
        }
        if (typeof trayController === "undefined" || !trayController || !trayController.describeDocketTabForCancel) {
            return
        }
        var cleanId = String(tabId || flyout.activeTabId || "").trim()
        var info = trayController.describeDocketTabForCancel(cleanId)
        if (!info || !info.ok) {
            return
        }
        if (String(info.kind || "") === "saved") {
            if (fromTabClose && trayController.closeOrHideDocketTab) {
                // Closing a saved tab only hides it from the strip (reload brings it back).
                trayController.closeOrHideDocketTab(cleanId)
            } else if (trayController.show_tray_toast) {
                trayController.show_tray_toast(String(info.message || "Saved dockets can only be deleted in CSPM."))
            }
            return
        }
        var cName = String(info.clientName || "").trim()
        var mName = String(info.matterName || "").trim()
        var dText = String(info.description || "").trim()
        if (fromTabClose && String(info.kind || "") === "draft" && !info.hasTime
                && cName.length <= 0 && mName.length <= 0 && dText.length <= 0) {
            // Completely blank draft tab: closing it loses nothing.
            trayController.cancelUnsavedDocketTab(cleanId, "discard")
            return
        }
        var summary = mName.length > 0 ? (cName.length > 0 ? (cName + " \u2022 " + mName) : mName) : (cName.length > 0 ? cName : "Unassigned docket")
        flyout.pendingDeleteTabId = cleanId
        flyout.pendingDeleteSummaryLabel = summary
        flyout.pendingDeleteElapsedFormatted = String(info.elapsedFormatted || "00:00:00")
        flyout.pendingDeleteDescription = dText
        flyout.pendingCancelKind = String(info.kind || "")
        flyout.pendingCancelRunning = Boolean(info.isRunning)
        flyout.pendingCancelHasTime = Boolean(info.hasTime)
        flyout.pendingCancelSavedFormatted = String(info.savedFormatted || "00:00:00")
        flyout.pendingCancelUnsavedFormatted = String(info.unsavedFormatted || "00:00:00")
        flyout.deleteConfirmOpen = true
    }

    function runCancelAction(action) {
        var tabId = String(flyout.pendingDeleteTabId || flyout.activeTabId || "").trim()
        flyout.deleteConfirmOpen = false
        flyout.pendingDeleteTabId = ""
        if (typeof trayController === "undefined" || !trayController) {
            return
        }
        if (action === "save") {
            if (trayController.selectDocketTab) {
                trayController.selectDocketTab(tabId)
            }
            if (trayController.stopAndSavePrimaryTimer) {
                trayController.stopAndSavePrimaryTimer()
            }
            return
        }
        if (trayController.cancelUnsavedDocketTab) {
            trayController.cancelUnsavedDocketTab(tabId, action)
        }
    }

    function openInlineTimeEditor() {
        editingElapsedInline = true
        manualTimeEditField.text = flyout.elapsedText === "00:00:00" ? "" : flyout.elapsedText
        manualTimeEditField.forceActiveFocus()
        manualTimeEditField.selectAll()
    }

    function commitInlineManualTime() {
        if (!editingElapsedInline) return
        var rawVal = String(manualTimeEditField.text || "").trim()
        editingElapsedInline = false
        if (rawVal.length <= 0) return
        if (typeof trayController !== "undefined" && trayController && trayController.setPrimaryManualTime) {
            trayController.setPrimaryManualTime(rawVal)
        }
    }

    function openNewTimerPicker(assignCurrentTab) {
        editingElapsedInline = false
        pickerAssignsCurrentTab = Boolean(assignCurrentTab)
        var curClient = (typeof trayController !== "undefined" && trayController && trayController.displayClientName)
            ? String(trayController.displayClientName || "").trim() : ""
        var curMatter = (typeof trayController !== "undefined" && trayController && trayController.displayMatterName)
            ? String(trayController.displayMatterName || "").trim() : ""
        var curDesc = (typeof trayController !== "undefined" && trayController && trayController.displayDescription)
            ? String(trayController.displayDescription || "").trim() : ""
        newClientInput.text = pickerAssignsCurrentTab ? curClient : ""
        newMatterInput.text = pickerAssignsCurrentTab ? curMatter : ""
        newDescInput.text = pickerAssignsCurrentTab ? curDesc : ""
        if (typeof newTimeInput !== "undefined" && newTimeInput) {
            newTimeInput.text = ""
        }
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

    function commitAssignCurrentTabFromPicker() {
        var cVal = String(newClientInput.text || "").trim()
        var mVal = String(newMatterInput.text || "").trim()
        var dVal = String(newDescInput.text || "").trim()
        var tVal = String((typeof newTimeInput !== "undefined" && newTimeInput) ? newTimeInput.text : "").trim()
        if (typeof trayController !== "undefined" && trayController) {
            if (cVal.length <= 0 && mVal.length > 0 && trayController.getClientForMatter) {
                cVal = String(trayController.getClientForMatter(mVal) || "").trim()
            }
            if (trayController.setSelectedTabClientAndMatter) {
                trayController.setSelectedTabClientAndMatter(cVal, mVal, dVal)
            }
            if (tVal.length > 0 && trayController.setPrimaryManualTime) {
                trayController.setPrimaryManualTime(tVal)
            }
        }
        activeDropdownTarget = ""
        newTimerPickerOpen = false
    }

    function commitNewTimerFromPicker() {
        var cVal = String(newClientInput.text || "").trim()
        var mVal = String(newMatterInput.text || "").trim()
        var dVal = String(newDescInput.text || "").trim()
        var tVal = String((typeof newTimeInput !== "undefined" && newTimeInput) ? newTimeInput.text : "").trim()
        if (typeof trayController !== "undefined" && trayController) {
            if (cVal.length <= 0 && mVal.length > 0 && trayController.getClientForMatter) {
                cVal = String(trayController.getClientForMatter(mVal) || "").trim()
            }
            if (pickerAssignsCurrentTab && trayController.setSelectedTabClientAndMatter) {
                trayController.setSelectedTabClientAndMatter(cVal, mVal, dVal)
                if (tVal.length > 0 && trayController.setPrimaryManualTime) {
                    trayController.setPrimaryManualTime(tVal)
                }
                if (!flyout.isRunningNow && trayController.togglePrimaryTimer) {
                    trayController.togglePrimaryTimer()
                }
            } else if (tVal.length > 0 && trayController.startNewTimerWithManualTime) {
                trayController.startNewTimerWithManualTime(cVal, mVal, dVal, tVal)
            } else if (trayController.startNewTimerWithDescription) {
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

    function commitManualSaveFromPicker() {
        var cVal = String(newClientInput.text || "").trim()
        var mVal = String(newMatterInput.text || "").trim()
        var dVal = String(newDescInput.text || "").trim()
        var tVal = String((typeof newTimeInput !== "undefined" && newTimeInput) ? newTimeInput.text : "").trim()
        if (tVal.length <= 0) {
            commitNewTimerFromPicker()
            return
        }
        if (typeof trayController !== "undefined" && trayController) {
            if (cVal.length <= 0 && mVal.length > 0 && trayController.getClientForMatter) {
                cVal = String(trayController.getClientForMatter(mVal) || "").trim()
            }
            if (trayController.saveManualTimeEntry) {
                trayController.saveManualTimeEntry(cVal, mVal, dVal, tVal)
            }
        }
        activeDropdownTarget = ""
        newTimerPickerOpen = false
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6
        visible: !flyout.newTimerPickerOpen

        // 0. Top Header Bar: Draggable Title/Tab Strip + Today's Dockets Tabs + '+' New Tab + '—' Minimize Button
        Rectangle {
            id: topHeaderStrip
            objectName: "trayHeaderBar"
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            radius: 7
            color: theme.surface
            border.width: 1
            border.color: theme.border

            // Background drag region for moving across monitors
            MouseArea {
                id: windowDragArea
                objectName: "trayWindowDragArea"
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                property point pressLocalPos: Qt.point(0, 0)
                onPressed: function(mouse) {
                    pressLocalPos = Qt.point(mouse.x, mouse.y)
                    if (Window.window && Window.window.startSystemMove) {
                        Window.window.startSystemMove()
                    }
                }
                onPositionChanged: function(mouse) {
                    if (pressed && Window.window && !Window.window.startSystemMove) {
                        Window.window.x += (mouse.x - pressLocalPos.x)
                        Window.window.y += (mouse.y - pressLocalPos.y)
                    }
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 4
                spacing: 4

                // Grip indicator for dragging
                Text {
                    text: "⋮⋮"
                    font.pixelSize: 11
                    font.bold: true
                    color: theme.textSecondary
                    Layout.alignment: Qt.AlignVCenter
                }

                // Today's Dockets Horizontal Tab Strip
                ListView {
                    id: todayTabListView
                    objectName: "trayTodayDocketTabStrip"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    orientation: ListView.Horizontal
                    spacing: 4
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: flyout.todayTabsModel

                    delegate: Rectangle {
                        id: tabPill
                        objectName: "trayDocketTabPill"
                        readonly property bool isSelected: String(modelData.tabId || "") === flyout.activeTabId
                        readonly property string tabStatus: String(modelData.status || "IDLE")
                        height: 22
                        width: Math.min(165, Math.max(78, tabRow.implicitWidth + 12))
                        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                        radius: 5
                        color: isSelected ? "#1E293B" : (tabPillMouse.containsMouse ? "#172033" : "transparent")
                        border.width: 1
                        border.color: isSelected
                            ? (tabStatus === "RUNNING" ? theme.timerGreen : theme.accentBlue)
                            : theme.border

                        MouseArea {
                            id: tabPillMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (flyout.editingElapsedInline) {
                                    flyout.commitInlineManualTime()
                                }
                                if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                                    trayController.updatePrimaryDescription(descField.text)
                                }
                                if (typeof trayController !== "undefined" && trayController && trayController.selectDocketTab) {
                                    trayController.selectDocketTab(String(modelData.tabId || ""))
                                }
                            }
                        }

                        RowLayout {
                            id: tabRow
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 4
                            spacing: 4

                            // Status Dot (green pulsing if RUNNING, amber if PAUSED, muted if SAVED/IDLE)
                            Rectangle {
                                id: tabStatusDot
                                objectName: "trayDocketTabStatusDot"
                                width: 6
                                height: 6
                                radius: 3
                                color: {
                                    if (tabPill.tabStatus === "RUNNING") return theme.timerGreen
                                    if (tabPill.tabStatus === "PAUSED") return "#D97706"
                                    return "#64748B"
                                }

                                SequentialAnimation on opacity {
                                    running: tabPill.tabStatus === "RUNNING"
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.35; duration: 550; easing.type: Easing.InOutQuad }
                                    NumberAnimation { from: 0.35; to: 1.0; duration: 550; easing.type: Easing.InOutQuad }
                                }
                            }

                            // Short Label (MatterNumber prefix or Client short name or Draft #N)
                            Text {
                                id: tabShortLabelText
                                objectName: "trayDocketTabLabel"
                                Layout.fillWidth: true
                                text: String(modelData.shortLabel || "Draft")
                                font.pixelSize: 10
                                font.bold: tabPill.isSelected
                                color: tabPill.isSelected ? "#F8FAFC" : theme.textPrimary
                                elide: Text.ElideRight
                            }

                            // Live Elapsed Time on Tab
                            Text {
                                id: tabElapsedLabelText
                                objectName: "trayDocketTabElapsed"
                                text: String(modelData.elapsedCompact || modelData.elapsedFormatted || "00:00")
                                font.pixelSize: 9
                                font.bold: tabPill.tabStatus === "RUNNING"
                                color: tabPill.tabStatus === "RUNNING" ? theme.timerGreen : theme.textSecondary
                            }

                            // Close / Delete ('×') button on every tab pill
                            Rectangle {
                                id: tabCloseBtn
                                objectName: "trayDocketTabCloseButton"
                                visible: true
                                width: 14
                                height: 14
                                radius: 3
                                color: tabCloseMouse.containsMouse ? "#451A1A" : "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: "×"
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: tabCloseMouse.containsMouse ? "#F87171" : theme.textSecondary
                                }

                                MouseArea {
                                    id: tabCloseMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: function(mouse) {
                                        mouse.accepted = true
                                        flyout.requestCancelOrDeleteTab(String(modelData.tabId || ""), true)
                                    }
                                }
                            }
                        }
                    }
                }

                // Compact '+' Button to open a new blank docket tab for today
                ToolButton {
                    id: addBlankTabBtn
                    objectName: "trayAddBlankDocketTabButton"
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 0
                    ToolTip.visible: hovered
                    ToolTip.text: "New blank docket tab for today"
                    contentItem: Text {
                        text: "+"
                        font.pixelSize: 13
                        font.bold: true
                        color: theme.accentBlue
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 4
                        color: addBlankTabBtn.hovered ? "#1E293B" : "transparent"
                        border.width: 1
                        border.color: theme.border
                    }
                    onClicked: {
                        if (flyout.editingElapsedInline) {
                            flyout.commitInlineManualTime()
                        }
                        if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                            trayController.updatePrimaryDescription(descField.text)
                        }
                        if (typeof trayController !== "undefined" && trayController && trayController.createNewDraftTab) {
                            trayController.createNewDraftTab()
                        }
                    }
                }

                // Reload every docket tab for today (saved today + unsaved timers/drafts)
                ToolButton {
                    id: reloadTodayTabsBtn
                    objectName: "trayReloadTodayDocketsButton"
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 0
                    ToolTip.visible: hovered
                    ToolTip.text: "Reload all of today's dockets"
                    contentItem: Text {
                        text: "\u21bb"
                        font.pixelSize: 12
                        font.bold: true
                        color: theme.accentBlue
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 4
                        color: reloadTodayTabsBtn.hovered ? "#1E293B" : "transparent"
                        border.width: 1
                        border.color: theme.border
                    }
                    onClicked: {
                        if (typeof trayController !== "undefined" && trayController && trayController.reloadTodayDockets) {
                            trayController.reloadTodayDockets()
                        }
                    }
                }

                // Explicit Minimize Button ('—' glyph) in top-right header bar
                ToolButton {
                    id: minimizeTrayBtn
                    objectName: "trayMinimizeButton"
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 0
                    ToolTip.visible: hovered
                    ToolTip.text: "Minimize to system tray (Esc)"
                    contentItem: Text {
                        text: "—"
                        font.pixelSize: 11
                        font.bold: true
                        color: minimizeTrayBtn.hovered ? "#F8FAFC" : theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 4
                        color: minimizeTrayBtn.hovered ? "#334155" : "transparent"
                        border.width: 1
                        border.color: minimizeTrayBtn.hovered ? "#475569" : theme.border
                    }
                    onClicked: {
                        flyout.minimizeRequested()
                    }
                }
            }
        }

        // 1. Status Badge + Live Elapsed Time + Compact Action Controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Rectangle {
                id: statusBadge
                objectName: "trayStatusBadge"
                radius: 5
                height: 22
                implicitWidth: statusLabel.implicitWidth + 10
                color: {
                    if (flyout.statusBadgeText === "RUNNING") return theme.timerGreen
                    if (flyout.statusBadgeText === "PAUSED") return "#D97706"
                    if (flyout.statusBadgeText === "SAVED" || flyout.statusBadgeText === "LATEST") return theme.accentBlue
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

            Rectangle {
                id: elapsedTimeContainer
                visible: !flyout.editingElapsedInline
                radius: 4
                color: elapsedMouse.containsMouse ? theme.surface : "transparent"
                implicitWidth: elapsedTimeText.implicitWidth + 6
                implicitHeight: 24
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: elapsedTimeText
                    objectName: "trayElapsedText"
                    anchors.centerIn: parent
                    text: flyout.elapsedText
                    font.pixelSize: 16
                    font.bold: true
                    color: flyout.isRunningNow ? theme.timerGreen : theme.textPrimary
                }

                MouseArea {
                    id: elapsedMouse
                    objectName: "trayElapsedClickArea"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: flyout.openInlineTimeEditor()
                }
            }

            Rectangle {
                id: manualTimeEditBox
                visible: flyout.editingElapsedInline
                Layout.preferredWidth: 88
                Layout.preferredHeight: 24
                radius: 5
                color: theme.surface
                border.width: 1
                border.color: theme.accentBlue
                Layout.alignment: Qt.AlignVCenter

                TextField {
                    id: manualTimeEditField
                    objectName: "trayManualTimeInput"
                    anchors.fill: parent
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    placeholderText: "e.g. 1.5h / 45m"
                    placeholderTextColor: theme.textSecondary
                    color: theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    selectByMouse: true
                    verticalAlignment: TextInput.AlignVCenter
                    background: Item {}
                    onAccepted: flyout.commitInlineManualTime()
                    onEditingFinished: flyout.commitInlineManualTime()
                    Keys.onEscapePressed: {
                        flyout.editingElapsedInline = false
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Start / Pause / Resume toggle
            Button {
                id: toggleTimerBtn
                objectName: "trayToggleTimerButton"
                visible: true
                implicitWidth: 50
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
                    if (flyout.editingElapsedInline) {
                        flyout.commitInlineManualTime()
                    }
                    if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(descField.text)
                    }
                    if (typeof trayController !== "undefined" && trayController && trayController.togglePrimaryTimer) {
                        trayController.togglePrimaryTimer()
                    }
                }
            }

            // Stop & Save button
            Button {
                id: stopSaveBtn
                objectName: "trayStopSaveButton"
                visible: flyout.hasActiveOrPaused || flyout.hasEntryToDisplay
                implicitWidth: 42
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
                    if (flyout.editingElapsedInline) {
                        flyout.commitInlineManualTime()
                    }
                    if (descField.activeFocus && typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(descField.text)
                    }
                    if (typeof trayController !== "undefined" && trayController && trayController.stopAndSavePrimaryTimer) {
                        trayController.stopAndSavePrimaryTimer()
                    }
                }
            }

            // Cancel: unsaved timers/drafts only. Saved dockets are deleted only in the main app.
            Button {
                id: cancelOrDeleteBtn
                objectName: "trayCancelOrDeleteButton"
                visible: true
                enabled: !flyout.isCurrentTabSavedDocket
                opacity: enabled ? 1.0 : 0.4
                hoverEnabled: true
                implicitWidth: 48
                implicitHeight: 24
                text: "Cancel"
                font.pixelSize: 11
                font.bold: true
                ToolTip.visible: hovered
                ToolTip.text: flyout.isCurrentTabSavedDocket
                    ? "Saved dockets can only be deleted in CSPM \u203a Time Dockets"
                    : "Cancel unsaved timer / draft (Ctrl+Del)"
                contentItem: Text {
                    text: cancelOrDeleteBtn.text
                    font: cancelOrDeleteBtn.font
                    color: cancelOrDeleteBtn.hovered ? "#F87171" : "#EF4444"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: cancelOrDeleteBtn.hovered ? "#2A1215" : theme.surface
                    border.width: 1
                    border.color: cancelOrDeleteBtn.hovered ? "#F87171" : "#EF4444"
                }
                onClicked: {
                    flyout.requestCancelOrDeleteTab(flyout.activeTabId, false)
                }
            }

            // + New Timer for a different Client / Matter
            Button {
                id: newTimerBtn
                objectName: "trayNewTimerButton"
                implicitWidth: 44
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
                    flyout.openNewTimerPicker(false)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: theme.border
        }

        // 2 & 3. Client Name + Matter Name/Number (clickable to assign/switch matter for current tab)
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
                        font.pixelSize: 13
                        font.bold: true
                        color: theme.textPrimary
                        elide: Text.ElideRight
                    }

                    Text {
                        text: "Select Matter ▾"
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
                    font.pixelSize: 11
                    color: theme.textSecondary
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                id: switchMatterMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: flyout.openNewTimerPicker(true)
            }
        }

        // 4. Current Docket Description (editable inline, expands when window is resized taller)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 34
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
                onTextEdited: {
                    if (typeof trayController !== "undefined" && trayController && trayController.updatePrimaryDescription) {
                        trayController.updatePrimaryDescription(text)
                    }
                }
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

        // Compact Footer: Date / Sync Status + Open CSPM & Quit
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                id: footerStatusText
                objectName: "trayFooterStatusText"
                text: {
                    if (typeof trayController !== "undefined" && trayController && trayController.lastSyncStatusMessage) {
                        var msg = String(trayController.lastSyncStatusMessage || "").trim()
                        if (msg.length > 0) return msg
                    }
                    return (typeof trayController !== "undefined" && trayController && trayController.currentDate)
                        ? String(trayController.currentDate)
                        : ""
                }
                font.pixelSize: 10
                color: (typeof trayController !== "undefined" && trayController && String(trayController.lastSyncStatusMessage || "").length > 0)
                    ? theme.timerGreen
                    : theme.textSecondary
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Button {
                id: openAppBtn
                objectName: "trayOpenCspmButton"
                implicitHeight: 22
                implicitWidth: 82
                text: "Open CSPM"
                font.pixelSize: 10
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
                    flyout.minimizeRequested()
                    if (typeof trayController !== "undefined" && trayController && trayController.open_cspm) {
                        trayController.open_cspm()
                    }
                }
            }

            Button {
                id: quitAppBtn
                objectName: "trayQuitButton"
                implicitHeight: 22
                implicitWidth: 44
                text: "Quit"
                font.pixelSize: 10
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
                    flyout.minimizeRequested()
                    if (typeof trayController !== "undefined" && trayController && trayController.exit_cspm) {
                        trayController.exit_cspm()
                    }
                }
            }
        }
    }

    // Inline New Timer / Matter Switcher View
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
                spacing: 4

                Text {
                    text: flyout.pickerAssignsCurrentTab ? "Select Matter" : "New / Manual"
                    font.pixelSize: 11
                    font.bold: true
                    color: theme.textPrimary
                }

                Rectangle {
                    id: newTimeInputBox
                    Layout.fillWidth: true
                    Layout.preferredHeight: 22
                    radius: 4
                    color: theme.surface
                    border.width: 1
                    border.color: newTimeInput.activeFocus ? theme.accentBlue : theme.border

                    TextField {
                        id: newTimeInput
                        objectName: "trayNewTimeInput"
                        anchors.fill: parent
                        anchors.leftMargin: 5
                        anchors.rightMargin: 5
                        placeholderText: "00:00:00 or 1.5h / 45m"
                        placeholderTextColor: theme.textSecondary
                        color: theme.textPrimary
                        font.pixelSize: 11
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Item {}
                        onAccepted: {
                            if (String(newTimeInput.text || "").trim().length > 0) {
                                flyout.commitManualSaveFromPicker()
                            } else {
                                flyout.commitNewTimerFromPicker()
                            }
                        }
                    }
                }

                Button {
                    id: cancelNewTimerBtn
                    objectName: "trayCancelNewTimerButton"
                    implicitWidth: 46
                    implicitHeight: 22
                    text: "Cancel"
                    font.pixelSize: 10
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
                    id: applyTabMatterBtn
                    objectName: "trayApplyTabMatterButton"
                    visible: flyout.pickerAssignsCurrentTab
                    implicitWidth: 44
                    implicitHeight: 22
                    text: "Apply"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: applyTabMatterBtn.text
                        font: applyTabMatterBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.accentBlue
                    }
                    onClicked: flyout.commitAssignCurrentTabFromPicker()
                }

                Button {
                    id: confirmSaveManualTimerBtn
                    objectName: "trayConfirmSaveManualTimerButton"
                    visible: String(newTimeInput.text || "").trim().length > 0
                    implicitWidth: 42
                    implicitHeight: 22
                    text: "Save"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: confirmSaveManualTimerBtn.text
                        font: confirmSaveManualTimerBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.accentBlue
                    }
                    onClicked: flyout.commitManualSaveFromPicker()
                }

                Button {
                    id: confirmStartNewTimerBtn
                    objectName: "trayConfirmStartNewTimerButton"
                    implicitWidth: 44
                    implicitHeight: 22
                    text: "Start"
                    font.pixelSize: 10
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

    // =========================================================================
    // OVERLAY 1: Simultaneous / Multiple Running Timers Warning Dialog (1a)
    // =========================================================================
    Rectangle {
        id: simultaneousTimerWarningOverlay
        objectName: "traySimultaneousTimerWarningModal"
        anchors.fill: parent
        radius: flyout.radius
        color: "#E60F172A"
        visible: flyout.simTimerWarningOpen
        z: 100

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#F59E0B"
                }

                Text {
                    text: "Simultaneous Timer Warning"
                    font.pixelSize: 13
                    font.bold: true
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                }
            }

            Text {
                id: simWarningMessageText
                objectName: "traySimTimerWarningMessage"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: flyout.simTimerWarningMsg
                font.pixelSize: 11
                color: "#E2E8F0"
            }

            Item { Layout.fillHeight: true }

            // 1. Pause Other & Start This One (Default/Primary)
            Button {
                id: simPauseOtherBtn
                objectName: "traySimTimerPauseOtherButton"
                Layout.fillWidth: true
                implicitHeight: 28
                text: "Pause Other & Start This One"
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: simPauseOtherBtn.text
                    font: simPauseOtherBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: theme.timerGreen
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveSimultaneousTimerPauseOther) {
                        trayController.resolveSimultaneousTimerPauseOther()
                    }
                }
            }

            // 2. Run Both Simultaneously
            Button {
                id: simRunBothBtn
                objectName: "traySimTimerRunBothButton"
                Layout.fillWidth: true
                implicitHeight: 26
                text: "Run Both Simultaneously"
                font.pixelSize: 11
                font.bold: true
                contentItem: Text {
                    text: simRunBothBtn.text
                    font: simRunBothBtn.font
                    color: "#38BDF8"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: "#1E293B"
                    border.width: 1
                    border.color: "#38BDF8"
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveSimultaneousTimerRunBoth) {
                        trayController.resolveSimultaneousTimerRunBoth()
                    }
                }
            }

            // 3. Cancel
            Button {
                id: simCancelBtn
                objectName: "traySimTimerCancelButton"
                Layout.fillWidth: true
                implicitHeight: 24
                text: "Cancel"
                font.pixelSize: 11
                contentItem: Text {
                    text: simCancelBtn.text
                    font: simCancelBtn.font
                    color: theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: "transparent"
                    border.width: 1
                    border.color: theme.border
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveSimultaneousTimerCancel) {
                        trayController.resolveSimultaneousTimerCancel()
                    }
                }
            }
        }
    }

    // =========================================================================
    // OVERLAY 2: Legacy Dockets.xlsm Sync Conflict Dialog (Part 2.2)
    // =========================================================================
    Rectangle {
        id: legacyConflictOverlay
        objectName: "trayLegacySyncConflictModal"
        anchors.fill: parent
        radius: flyout.radius
        color: "#F20F172A"
        visible: flyout.legacyConflictOpen
        z: 110

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#F59E0B"
                }

                Text {
                    text: "Legacy Dockets.xlsm Sync Conflict"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            // Incoming CSPM Entry Summary
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: incomingCol.implicitHeight + 8
                radius: 5
                color: "#1E293B"
                border.width: 1
                border.color: "#334155"

                ColumnLayout {
                    id: incomingCol
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 2

                    Text {
                        text: {
                            var inc = (flyout.legacyConflictData && flyout.legacyConflictData.incomingEntry)
                                ? flyout.legacyConflictData.incomingEntry : ({})
                            return "Incoming CSPM: " + String(inc.date || "") + " | "
                                + String(inc.matterId || inc.client || "") + " | "
                                + Number(inc.hours || 0).toFixed(2) + "h (" + Number(inc.rawSeconds || 0) + "s)"
                        }
                        font.pixelSize: 10
                        font.bold: true
                        color: "#38BDF8"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: {
                            var inc = (flyout.legacyConflictData && flyout.legacyConflictData.incomingEntry)
                                ? flyout.legacyConflictData.incomingEntry : ({})
                            return "Desc: " + String(inc.description || "(none)")
                        }
                        font.pixelSize: 10
                        color: "#CBD5E1"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            // Existing Table1_1 Row(s) Selector / Details
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: existingCol.implicitHeight + 8
                radius: 5
                color: "#1E293B"
                border.width: 1
                border.color: flyout.selectedRowIsBilled ? "#EF4444" : "#475569"

                ColumnLayout {
                    id: existingCol
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: {
                                var ex = flyout.selectedExistingRowObj || ({})
                                return "Table1_1 Row #" + String(ex.rowNumber || "?") + ": "
                                    + Number(ex.hours || 0).toFixed(2) + "h (" + Number(ex.rawSeconds || 0) + "s)"
                            }
                            font.pixelSize: 10
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        // Billed warning badge if Invoice is populated
                        Rectangle {
                            visible: flyout.selectedRowIsBilled
                            radius: 3
                            color: "#7F1D1D"
                            border.width: 1
                            border.color: "#EF4444"
                            implicitWidth: billedBadgeLbl.implicitWidth + 8
                            implicitHeight: 16

                            Text {
                                id: billedBadgeLbl
                                anchors.centerIn: parent
                                text: "BILLED: " + String((flyout.selectedExistingRowObj || ({})).invoice || "YES")
                                font.pixelSize: 9
                                font.bold: true
                                color: "#FCA5A5"
                            }
                        }
                    }

                    Text {
                        text: {
                            var ex = flyout.selectedExistingRowObj || ({})
                            return "Existing Desc: " + String(ex.description || "(none)")
                        }
                        font.pixelSize: 10
                        color: "#CBD5E1"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // Row selector pills when multiple rows match (Date, Matter_ID)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        visible: Boolean(flyout.legacyConflictData && flyout.legacyConflictData.existingRows && flyout.legacyConflictData.existingRows.length > 1)

                        Text {
                            text: "Target Row:"
                            font.pixelSize: 9
                            color: theme.textSecondary
                        }

                        Repeater {
                            model: (flyout.legacyConflictData && flyout.legacyConflictData.existingRows) ? flyout.legacyConflictData.existingRows : []
                            delegate: Rectangle {
                                radius: 3
                                height: 16
                                width: rowNumText.implicitWidth + 8
                                color: Number(modelData.rowNumber || 0) === flyout.selectedConflictRowNumber ? theme.accentBlue : "#0F172A"
                                border.width: 1
                                border.color: theme.border

                                Text {
                                    id: rowNumText
                                    anchors.centerIn: parent
                                    text: "#" + String(modelData.rowNumber || "")
                                    font.pixelSize: 9
                                    color: "#FFFFFF"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        flyout.selectedConflictRowNumber = Number(modelData.rowNumber || 0)
                                        flyout.confirmBilledOverwriteArmed = false
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // 4 Explicit User Resolution Buttons (2x2 compact grid so all 4 fit cleanly)
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 4
                columnSpacing: 4

                // 1. Overwrite Existing Row
                Button {
                    id: conflictOverwriteBtn
                    objectName: "trayConflictOverwriteButton"
                    Layout.fillWidth: true
                    implicitHeight: 26
                    text: (flyout.selectedRowIsBilled && !flyout.confirmBilledOverwriteArmed)
                        ? "⚠ Confirm Billed Overwrite?"
                        : "1. Overwrite Existing Row"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: conflictOverwriteBtn.text
                        font: conflictOverwriteBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: flyout.selectedRowIsBilled ? "#DC2626" : "#D97706"
                    }
                    onClicked: {
                        if (flyout.selectedRowIsBilled && !flyout.confirmBilledOverwriteArmed) {
                            flyout.confirmBilledOverwriteArmed = true
                            return
                        }
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveLegacyDocketsConflict) {
                            trayController.resolveLegacyDocketsConflict("overwrite", flyout.selectedConflictRowNumber, true)
                        }
                    }
                }

                // 2. Append as Separate New Row
                Button {
                    id: conflictAppendBtn
                    objectName: "trayConflictAppendButton"
                    Layout.fillWidth: true
                    implicitHeight: 26
                    text: "2. Append Separate Row"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: conflictAppendBtn.text
                        font: conflictAppendBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.accentBlue
                    }
                    onClicked: {
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveLegacyDocketsConflict) {
                            trayController.resolveLegacyDocketsConflict("append", flyout.selectedConflictRowNumber, false)
                        }
                    }
                }

                // 3. Combine / Add Time into Existing Row
                Button {
                    id: conflictCombineBtn
                    objectName: "trayConflictCombineButton"
                    Layout.fillWidth: true
                    implicitHeight: 26
                    text: "3. Combine / Add Time"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: conflictCombineBtn.text
                        font: conflictCombineBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.timerGreen
                    }
                    onClicked: {
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveLegacyDocketsConflict) {
                            trayController.resolveLegacyDocketsConflict("combine", flyout.selectedConflictRowNumber, true)
                        }
                    }
                }

                // 4. Skip Dockets.xlsm (Save in CSPM Only)
                Button {
                    id: conflictSkipBtn
                    objectName: "trayConflictSkipButton"
                    Layout.fillWidth: true
                    implicitHeight: 26
                    text: "4. Skip Dockets.xlsm"
                    font.pixelSize: 10
                    contentItem: Text {
                        text: conflictSkipBtn.text
                        font: conflictSkipBtn.font
                        color: "#CBD5E1"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: "#1E293B"
                        border.width: 1
                        border.color: "#475569"
                    }
                    onClicked: {
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveLegacyDocketsConflict) {
                            trayController.resolveLegacyDocketsConflict("skip", flyout.selectedConflictRowNumber, false)
                        }
                    }
                }
            }
        }
    }

    // =========================================================================
    // OVERLAY 3: Post-Crash Startup Recovery & Dockets.xlsm Sync Modal
    // =========================================================================
    Rectangle {
        id: crashRecoveryOverlay
        objectName: "trayCrashRecoveryModal"
        anchors.fill: parent
        radius: flyout.radius
        color: "#F20F172A"
        visible: flyout.crashRecoveryOpen
        z: 120

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#38BDF8"
                }

                Text {
                    text: "Crash Recovery & Dockets.xlsm Sync"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: crashDetailsCol.implicitHeight + 8
                radius: 5
                color: "#1E293B"
                border.width: 1
                border.color: "#334155"

                ColumnLayout {
                    id: crashDetailsCol
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 2

                    Text {
                        text: {
                            var cr = flyout.crashRecoveryData || ({})
                            return String(cr.clientName || "Ad Hoc Client") + " — " + String(cr.matterNumber || cr.matterId || "General Consultation")
                        }
                        font.pixelSize: 11
                        font.bold: true
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: {
                            var cr = flyout.crashRecoveryData || ({})
                            return "Date: " + String(cr.date || "") + " | Desc: " + String(cr.description || "(no description)")
                        }
                        font.pixelSize: 10
                        color: "#CBD5E1"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            // Time Selector when timer was RUNNING at the moment of the crash
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                visible: Boolean((flyout.crashRecoveryData || ({})).wasRunning)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    // Option A: Heartbeat Time
                    Rectangle {
                        id: optHeartbeatBox
                        objectName: "trayCrashOptionHeartbeat"
                        Layout.fillWidth: true
                        height: 24
                        radius: 4
                        color: flyout.crashRecoveryTimeOption === "heartbeat" ? "#1E3A8A" : "#1E293B"
                        border.width: 1
                        border.color: flyout.crashRecoveryTimeOption === "heartbeat" ? "#38BDF8" : "#475569"

                        Text {
                            anchors.centerIn: parent
                            text: "A: Heartbeat (" + String((flyout.crashRecoveryData || ({})).heartbeatFormatted || "00:00:00") + ")"
                            font.pixelSize: 9
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: flyout.crashRecoveryTimeOption = "heartbeat"
                        }
                    }

                    // Option B: Wall-Clock Time since started_at_utc
                    Rectangle {
                        id: optWallClockBox
                        objectName: "trayCrashOptionWallClock"
                        Layout.fillWidth: true
                        height: 24
                        radius: 4
                        color: flyout.crashRecoveryTimeOption === "wall_clock" ? "#1E3A8A" : "#1E293B"
                        border.width: 1
                        border.color: flyout.crashRecoveryTimeOption === "wall_clock" ? "#38BDF8" : "#475569"

                        Text {
                            anchors.centerIn: parent
                            text: "B: +Wall Gap (" + String((flyout.crashRecoveryData || ({})).wallClockFormatted || "00:00:00") + ")"
                            font.pixelSize: 9
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: flyout.crashRecoveryTimeOption = "wall_clock"
                        }
                    }
                }
            }

            // When timer was PAUSED at crash, show recorded time
            Text {
                visible: !Boolean((flyout.crashRecoveryData || ({})).wasRunning)
                text: "Recovered Paused Time: " + String((flyout.crashRecoveryData || ({})).heartbeatFormatted || "00:00:00")
                font.pixelSize: 10
                font.bold: true
                color: "#F59E0B"
                Layout.fillWidth: true
            }

            Item { Layout.fillHeight: true }

            // 1. Save & Enter into Dockets.xlsm Now
            Button {
                id: crashSaveAndSyncBtn
                objectName: "trayCrashSaveAndSyncButton"
                Layout.fillWidth: true
                implicitHeight: 26
                text: "1. Save & Enter into Dockets.xlsm Now"
                font.pixelSize: 10
                font.bold: true
                contentItem: Text {
                    text: crashSaveAndSyncBtn.text
                    font: crashSaveAndSyncBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 5
                    color: theme.timerGreen
                }
                onClicked: {
                    var eid = String((flyout.crashRecoveryData || ({})).entryId || "")
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveCrashRecoveryDocket) {
                        trayController.resolveCrashRecoveryDocket(eid, "save_and_sync", flyout.crashRecoveryTimeOption)
                    }
                }
            }

            // 2. Enter Current Time into Dockets.xlsm Now & Keep Tab Open (Paused)
            Button {
                id: crashSyncKeepPausedBtn
                objectName: "trayCrashSyncAndKeepPausedButton"
                Layout.fillWidth: true
                implicitHeight: 26
                text: "2. Enter into Dockets.xlsm & Keep Tab Open (Paused)"
                font.pixelSize: 10
                font.bold: true
                contentItem: Text {
                    text: crashSyncKeepPausedBtn.text
                    font: crashSyncKeepPausedBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 5
                    color: theme.accentBlue
                }
                onClicked: {
                    var eid = String((flyout.crashRecoveryData || ({})).entryId || "")
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveCrashRecoveryDocket) {
                        trayController.resolveCrashRecoveryDocket(eid, "sync_and_keep_paused", flyout.crashRecoveryTimeOption)
                    }
                }
            }

            // 3. Discard Recovered Draft (with confirmation)
            Button {
                id: crashDiscardBtn
                objectName: "trayCrashDiscardButton"
                Layout.fillWidth: true
                implicitHeight: 24
                text: flyout.crashRecoveryDiscardArmed
                    ? "⚠ Confirm Discard Recovered Draft?"
                    : "3. Discard Recovered Draft"
                font.pixelSize: 10
                font.bold: flyout.crashRecoveryDiscardArmed
                contentItem: Text {
                    text: crashDiscardBtn.text
                    font: crashDiscardBtn.font
                    color: flyout.crashRecoveryDiscardArmed ? "#FFFFFF" : "#FCA5A5"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 5
                    color: flyout.crashRecoveryDiscardArmed ? "#DC2626" : "transparent"
                    border.width: 1
                    border.color: "#EF4444"
                }
                onClicked: {
                    if (!flyout.crashRecoveryDiscardArmed) {
                        flyout.crashRecoveryDiscardArmed = true
                        return
                    }
                    var eid = String((flyout.crashRecoveryData || ({})).entryId || "")
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveCrashRecoveryDocket) {
                        trayController.resolveCrashRecoveryDocket(eid, "discard", flyout.crashRecoveryTimeOption)
                    }
                }
            }
        }
    }

    // =========================================================================
    // OVERLAY 4: Unsaved / Active Docket Safeguard Dialog on Close/Quit
    // =========================================================================
    Rectangle {
        id: closeSafeguardOverlay
        objectName: "trayCloseSafeguardModal"
        anchors.fill: parent
        radius: flyout.radius
        color: "#F20F172A"
        visible: flyout.closeSafeguardOpen
        z: 130

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#F59E0B"
                }

                Text {
                    text: "Unsaved / Active Docket Safeguard"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            Text {
                id: closeSafeguardMessageText
                objectName: "trayCloseSafeguardMessage"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: flyout.closeSafeguardMsg
                font.pixelSize: 10
                color: "#E2E8F0"
            }

            Item { Layout.fillHeight: true }

            // 1. Save & Sync All to Dockets.xlsm, Then Quit (Primary)
            Button {
                id: safeguardSaveAndQuitBtn
                objectName: "traySafeguardSaveSyncQuitButton"
                Layout.fillWidth: true
                implicitHeight: 26
                text: "1. Save & Sync All to Dockets.xlsm, Then Quit"
                font.pixelSize: 10
                font.bold: true
                contentItem: Text {
                    text: safeguardSaveAndQuitBtn.text
                    font: safeguardSaveAndQuitBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 5
                    color: theme.timerGreen
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveCloseSafeguard) {
                        trayController.resolveCloseSafeguard("save_sync_and_quit")
                    }
                }
            }

            // 2. Pause, Sync Current Time to Dockets.xlsm & Quit (Resume Next Launch)
            Button {
                id: safeguardPauseSyncQuitBtn
                objectName: "traySafeguardPauseSyncQuitButton"
                Layout.fillWidth: true
                implicitHeight: 26
                text: "2. Pause & Keep as Drafts, Then Quit (Reopen Next Launch)"
                font.pixelSize: 10
                font.bold: true
                contentItem: Text {
                    text: safeguardPauseSyncQuitBtn.text
                    font: safeguardPauseSyncQuitBtn.font
                    color: "#FFFFFF"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 5
                    color: theme.accentBlue
                }
                onClicked: {
                    if (typeof trayController !== "undefined" && trayController && trayController.resolveCloseSafeguard) {
                        trayController.resolveCloseSafeguard("pause_keep_drafts_and_quit")
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                // 3. Minimize to System Tray Instead
                Button {
                    id: safeguardMinimizeBtn
                    objectName: "traySafeguardMinimizeTrayButton"
                    Layout.fillWidth: true
                    implicitHeight: 24
                    text: "3. Minimize to System Tray"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: safeguardMinimizeBtn.text
                        font: safeguardMinimizeBtn.font
                        color: "#38BDF8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: "#1E293B"
                        border.width: 1
                        border.color: "#38BDF8"
                    }
                    onClicked: {
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveCloseSafeguard) {
                            trayController.resolveCloseSafeguard("minimize_to_tray")
                        }
                        flyout.minimizeRequested()
                    }
                }

                // Discard unsaved timer time (two clicks) and quit
                Button {
                    id: safeguardDiscardBtn
                    objectName: "traySafeguardDiscardQuitButton"
                    property bool armed: false
                    Layout.fillWidth: true
                    implicitHeight: 24
                    text: armed ? "Click again: discard" : "Discard & Quit"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: safeguardDiscardBtn.text
                        font: safeguardDiscardBtn.font
                        color: safeguardDiscardBtn.armed ? "#FFFFFF" : "#FCA5A5"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: safeguardDiscardBtn.armed ? "#DC2626" : "transparent"
                        border.width: 1
                        border.color: "#EF4444"
                    }
                    onClicked: {
                        if (!armed) {
                            armed = true
                            return
                        }
                        armed = false
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveCloseSafeguard) {
                            trayController.resolveCloseSafeguard("discard_and_quit")
                        }
                    }
                }

                // 4. Cancel
                Button {
                    id: safeguardCancelBtn
                    objectName: "traySafeguardCancelButton"
                    Layout.preferredWidth: 74
                    implicitHeight: 24
                    text: "4. Cancel"
                    font.pixelSize: 10
                    contentItem: Text {
                        text: safeguardCancelBtn.text
                        font: safeguardCancelBtn.font
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
                        if (typeof trayController !== "undefined" && trayController && trayController.resolveCloseSafeguard) {
                            trayController.resolveCloseSafeguard("cancel")
                        }
                    }
                }
            }
        }
    }

    // =========================================================================
    // OVERLAY 5: Compact "Cancel unsaved docket" options (never deletes saved dockets)
    // =========================================================================
    Rectangle {
        id: deleteConfirmOverlay
        objectName: "trayCancelUnsavedOverlay"
        anchors.fill: parent
        radius: flyout.radius
        color: "#F20F172A"
        visible: flyout.deleteConfirmOpen
        z: 140

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#F59E0B"
                }

                Text {
                    text: flyout.pendingCancelKind === "resumed_saved"
                        ? "Cancel the time added to this saved docket?"
                        : "Cancel this unsaved docket?"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: cancelInfoCol.implicitHeight + 8
                radius: 6
                color: "#1E293B"
                border.width: 1
                border.color: "#334155"

                ColumnLayout {
                    id: cancelInfoCol
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 1

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: flyout.pendingDeleteSummaryLabel
                            font.pixelSize: 11
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: flyout.pendingDeleteElapsedFormatted
                            font.pixelSize: 11
                            font.bold: true
                            color: "#FCD34D"
                        }
                    }

                    Text {
                        text: flyout.pendingCancelKind === "resumed_saved"
                            ? ("Saved docket stays at " + flyout.pendingCancelSavedFormatted + " \u2022 unsaved added time " + flyout.pendingCancelUnsavedFormatted)
                            : "Not saved yet. Saved dockets can only be deleted in CSPM \u203a Time Dockets."
                        font.pixelSize: 9
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                // Save (explicit user choice)
                Button {
                    id: cancelOptSaveBtn
                    objectName: "trayCancelOptionSaveButton"
                    visible: flyout.pendingCancelKind === "timer"
                        || flyout.pendingCancelKind === "resumed_saved"
                        || (flyout.pendingCancelKind === "draft" && flyout.pendingCancelHasTime)
                    Layout.fillWidth: true
                    implicitHeight: 24
                    hoverEnabled: true
                    text: flyout.pendingCancelKind === "resumed_saved" ? "Save added time" : "Save docket now"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: cancelOptSaveBtn.text
                        font: cancelOptSaveBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.timerGreen
                        opacity: cancelOptSaveBtn.hovered ? 0.85 : 1.0
                    }
                    onClicked: flyout.runCancelAction("save")
                }

                // Pause & keep as an unsaved draft tab
                Button {
                    id: cancelOptPauseBtn
                    objectName: "trayCancelOptionPauseButton"
                    visible: flyout.pendingCancelRunning
                    Layout.fillWidth: true
                    implicitHeight: 24
                    hoverEnabled: true
                    text: "Pause & keep as draft"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: cancelOptPauseBtn.text
                        font: cancelOptPauseBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: theme.accentBlue
                        opacity: cancelOptPauseBtn.hovered ? 0.85 : 1.0
                    }
                    onClicked: flyout.runCancelAction("pause")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                // Reset the unsaved clock to 00:00:00 but keep the tab
                Button {
                    id: cancelOptResetBtn
                    objectName: "trayCancelOptionResetButton"
                    visible: (flyout.pendingCancelKind === "timer" || flyout.pendingCancelKind === "draft") && flyout.pendingCancelHasTime
                    Layout.fillWidth: true
                    implicitHeight: 24
                    hoverEnabled: true
                    text: "Reset to 00:00:00"
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: cancelOptResetBtn.text
                        font: cancelOptResetBtn.font
                        color: cancelOptResetBtn.hovered ? "#F8FAFC" : "#38BDF8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: cancelOptResetBtn.hovered ? "#1E3A8A" : "#1E293B"
                        border.width: 1
                        border.color: "#38BDF8"
                    }
                    onClicked: flyout.runCancelAction("reset_zero")
                }

                // Discard unsaved time (a saved docket is never changed)
                Button {
                    id: cancelOptDiscardBtn
                    objectName: "trayCancelOptionDiscardButton"
                    Layout.fillWidth: true
                    implicitHeight: 24
                    hoverEnabled: true
                    text: flyout.pendingCancelKind === "resumed_saved"
                        ? ("Discard added " + flyout.pendingCancelUnsavedFormatted)
                        : (flyout.pendingCancelKind === "draft" && !flyout.pendingCancelHasTime
                            ? "Close blank draft"
                            : ("Discard (lose " + flyout.pendingDeleteElapsedFormatted + ")"))
                    font.pixelSize: 10
                    font.bold: true
                    contentItem: Text {
                        text: cancelOptDiscardBtn.text
                        font: cancelOptDiscardBtn.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        radius: 5
                        color: cancelOptDiscardBtn.hovered ? "#F87171" : "#EF4444"
                        border.width: 1
                        border.color: "#FCA5A5"
                    }
                    onClicked: flyout.runCancelAction("discard")
                }
            }

            // Go back (nothing changes)
            Button {
                id: confirmKeepDocketBtn
                objectName: "trayCancelOptionGoBackButton"
                Layout.fillWidth: true
                implicitHeight: 22
                hoverEnabled: true
                text: "Go back \u2014 keep everything as is"
                font.pixelSize: 10
                font.bold: true
                contentItem: Text {
                    text: confirmKeepDocketBtn.text
                    font: confirmKeepDocketBtn.font
                    color: confirmKeepDocketBtn.hovered ? "#F8FAFC" : theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 5
                    color: confirmKeepDocketBtn.hovered ? "#334155" : "transparent"
                    border.width: 1
                    border.color: theme.border
                }
                onClicked: {
                    flyout.deleteConfirmOpen = false
                    flyout.pendingDeleteTabId = ""
                }
            }
        }
    }
}
