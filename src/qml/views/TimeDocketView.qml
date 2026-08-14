pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects 
import QtQuick.Window
import "../components"
import "../standards"
import "../standards/SubwindowStyle.js" as SubwindowStyle
import "../standards/SemanticTheme.js" as SemanticTheme
import "../standards/PerfTrace.js" as PerfTrace

Item {
            id: root
    property var deadlineCalendar: typeof deadlineCalendarLoader !== 'undefined' ? deadlineCalendarLoader.item : null
    property var t;
    property var metrics
    property var windowRef
    property var appRef
    readonly property var docketActivityReportPanel: (docketActivityReportPanelLoader && docketActivityReportPanelLoader.item)
        ? docketActivityReportPanelLoader.item : null
    property var sfxBus: (root.windowRef && root.windowRef.sfxBusRef) ? root.windowRef.sfxBusRef : null
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : (((typeof app !== "undefined") && app !== null && app.appStyle) ? String(app.appStyle) : "Professional")
    property color _accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _mutedText: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color _subtleText: SemanticTheme.alpha(SemanticTheme.inkMuted(root.t, root.appStyle), 0.82)
    property color _panel: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color _bg: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color _panelBase: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property real _bgLuma: (_bg.r * 0.299) + (_bg.g * 0.587) + (_bg.b * 0.114)
    property bool lightTheme: _bgLuma >= 0.58
    readonly property bool isProMode: visualRules.isPro
    property color proBackground: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color proSurface: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color proCanvas: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color proControl: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proControlHover: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color proActiveBorder: SemanticTheme.borderStrong(root.t, root.appStyle)
    property color proInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color proMutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color proActiveFill: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color proHoverFill: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property int proControlRadiusPx: visualRules.radiusControl
    property var scaleRatios: SubwindowStyle.timeDocketRatios()

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function themeBucket() {
        if (_accent.g >= _accent.r && _accent.g >= _accent.b) return "emerald"
        if (_accent.b >= _accent.r && _accent.b >= _accent.g) return "sapphire"
        return "crimson"
    }

    function themeBackgroundSource() {
        return Qt.resolvedUrl("../../../assets/home_skyline_bw.png")
    }

    function backgroundColorizationStrength() {
        if (root.isProMode) return 0.0
        if (root.lightTheme) return 0.06
        var bucket = themeBucket()
        if (bucket === "sapphire") return 0.18
        if (bucket === "emerald") return 0.17
        return 0.20
    }

    function contentW() {
        if (metrics && typeof metrics.contentW === "number") return Math.max(1, metrics.contentW)
        return Math.max(1, root.width)
    }
    function contentH() {
        if (metrics && typeof metrics.contentH === "number") return Math.max(1, metrics.contentH)
        return Math.max(1, root.height)
    }
    function contentUnit() {
        return Math.min(contentW(), contentH())
    }
    function areaUnit() {
        return Math.sqrt(contentW() * contentH())
    }
    function areaFloorPx(ratio, fallbackPx) {
        var floorPx = (typeof fallbackPx === "number") ? fallbackPx : 1
        return Math.max(floorPx, Math.round(areaUnit() * ratio))
    }
    // Area-based metrics payload for child controls; independent of OS DPI scaling.
    property var responsiveMetrics: ({
        "contentW": contentW(),
        "contentH": contentH(),
        "scalePercent": (metrics && typeof metrics.scalePercent === "number") ? metrics.scalePercent : 100,
        "fontFloorTitlePx": areaFloorPx(0.0130, 12),
        "fontFloorIconPx": areaFloorPx(0.0120, 11),
        "fontFloorBodyPx": areaFloorPx(0.0109, 9),
        "fontFloorLabelPx": areaFloorPx(0.0098, 8)
    })
    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(areaUnit() * ratio))
    }
    function ratioPxW(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentW() * ratio))
    }
    function ratioPxH(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentH() * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (responsiveMetrics && typeof responsiveMetrics[metricKey] === "number") {
            return Math.max(1, Math.round(responsiveMetrics[metricKey]))
        }
        if (metrics && typeof metrics[metricKey] === "number") return Math.max(1, Math.round(metrics[metricKey]))
        return Math.max(1, Math.round(fallbackPx))
    }
    function readableMinFontPx() {
        return root.metricFloor("fontFloorLabelPx", 8)
    }

// === SIDEBAR HOVER HELPERS (fix.py) ===
function sidebarHoverBlendFactor(hovered) {
    if (root.lightTheme) {
        return hovered ? 0.40 : 0.14
    }
    return hovered ? 0.58 : 0.20
}
function sidebarHoverFill(active, hovered, activeAlpha, hoverAlpha, idleAlpha) {
    if (root.isProMode) {
        return active ? root.proHoverFill : (hovered ? root.proSurface : "transparent")
    }
    if (active) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, activeAlpha)
    }
    var mixFactor = root.sidebarHoverBlendFactor(hovered)
    return Qt.rgba(
        (root._panel.r * (1.0 - mixFactor)) + (root._accent.r * mixFactor),
        (root._panel.g * (1.0 - mixFactor)) + (root._accent.g * mixFactor),
        (root._panel.b * (1.0 - mixFactor)) + (root._accent.b * mixFactor),
        hovered ? hoverAlpha : idleAlpha
    )
}
function sidebarHoverBorder(active, hovered, activeAlpha, hoverAlpha, idleAlpha) {
    if (root.isProMode) {
        return active ? root.proActiveBorder : (hovered ? root.proBorder : "transparent")
    }
    if (active) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, activeAlpha)
    }
    if (hovered) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, hoverAlpha)
    }
    return Qt.rgba(root._text.r, root._text.g, root._text.b, idleAlpha)
}
    property int sectionRadiusPx: root.isProMode
        ? root.proControlRadiusPx
        : root.ratioPx(root.scaleRatios.descCornerPct, 10)
    property int fieldHeightPx: root.isProMode
        ? Math.max(52, root.ratioPxH(0.064, 52))
        : root.ratioPxH(0.060, 44)
    property int liveDocketFieldHeightPx: root.isProMode ? root.fieldHeightPx : 46
    property int professionalHostedOuterMarginPx: (root.isProMode && root.externalNavigationShell) ? 14 : root.ratioPx(root.scaleRatios.pageMarginPct, 6)
    property int professionalLiveCanvasMarginPx: (root.isProMode && root.externalNavigationShell && root.activeIsLiveDocket()) ? 14 : (root.activeIsLiveDocket() ? 10 : root.ratioPx(root.scaleRatios.pageMarginPct * 0.95, 10))
    property int controlGapPx: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.72, 6)

    function colorAlpha(base, alpha) {
        return Qt.rgba(base.r, base.g, base.b, alpha)
    }

    function deadlineTagFill(kind) {
        if (kind === "completed") return SemanticTheme.surface(root.t, "tooltip", "success")
        if (kind === "escalated") return SemanticTheme.surface(root.t, "tooltip", "danger")
        return SemanticTheme.surface(root.t, "tooltip", "info")
    }

    function deadlineTagText(kind) {
        if (kind === "completed") return SemanticTheme.ink(root.t, "tooltip", "success")
        if (kind === "escalated") return SemanticTheme.ink(root.t, "tooltip", "danger")
        return SemanticTheme.ink(root.t, "tooltip", "info")
    }

    function moduleRefWidth() {
        if (moduleCanvas && typeof moduleCanvas.width === "number" && moduleCanvas.width > 1) {
            return moduleCanvas.width
        }
        return contentW()
    }

    function moduleRatioPxW(ratio, minPx, maxPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        var value = Math.max(floorPx, Math.round(moduleRefWidth() * ratio))
        if (typeof maxPx === "number") {
            value = Math.min(value, Math.max(floorPx, Math.round(maxPx)))
        }
        return value
    }

    function startupAllowsHeavyWorkNow(reason) {
        if (root.windowRef && root.windowRef.startupAllowsHeavyWork) {
            return root.windowRef.startupAllowsHeavyWork("TimeDocketView." + String(reason || "unspecified"))
        }
        return true
    }

    function startupQueueEnabled() {
        return !!(root.windowRef
            && root.windowRef.startupDeferredQueueEnabledForClients
            && root.windowRef.enqueuePostSettleTask)
    }

    function startupHeavyWorkDelayMs(defaultMs) {
        var fallback = (typeof defaultMs === "number") ? Math.max(60, Math.round(defaultMs)) : 220
        if (root.windowRef && root.windowRef.startupHeavyWorkDelayMs) {
            var delayMs = Number(root.windowRef.startupHeavyWorkDelayMs())
            if (isFinite(delayMs)) {
                return Math.max(24, Math.round(delayMs))
            }
        }
        return fallback
    }

    function scheduleStartupHydration(reason) {
        root.startupDeferredHydrationPending = true
        startupHydrationRetryTimer.stop()
        if (!root.visible) {
            return
        }
        if (startupQueueEnabled()) {
            if (root.windowRef.enqueuePostSettleTask(
                "TimeDocketView.startupHydration",
                root,
                "_runQueuedStartupHydrationTask",
                { "reason": String(reason || "unspecified") },
                true
            )) {
                return
            }
        }
        startupHydrationRetryTimer.interval = startupHeavyWorkDelayMs(root.startupHydrationRetryMs)
        startupHydrationRetryTimer.start()
    }

    function _runQueuedStartupHydrationTask(payload) {
        if (root.startupHydrationCompleted) {
            root.startupDeferredHydrationPending = false
            return true
        }
        if (!root.visible) return false
        if (!activeNeedsStartupHydration()) return false
        if (!startupAllowsHeavyWorkNow("runStartupHydration.queued")) return false
        root.startupDeferredHydrationPending = false
        root.runStartupHydration("queued:" + String(payload && payload.reason ? payload.reason : "unspecified"))
        return root.startupHydrationCompleted
    }

    function activeNeedsStartupHydration() {
        return root.activeUsesDocketContext()
            || root.activeIsDeadlineCalendar()
            || root.activeIsDeadlineEditor()
            || root.activeIsDocketReport()
    }

    function ensureActivationHydration(reason) {
        if (root.startupHydrationCompleted) {
            return true
        }
        if (!root.visible) {
            root.startupDeferredHydrationPending = true
            startupHydrationRetryTimer.stop()
            return false
        }
        if (!activeNeedsStartupHydration()) {
            root.startupDeferredHydrationPending = true
            return false
        }
        runStartupHydration("activation:" + String(reason || "unspecified"))
        return root.startupHydrationCompleted
    }

    function runStartupHydration(reason) {
        if (root.startupHydrationCompleted) {
            return
        }
        if (!root.visible) {
            scheduleStartupHydration(reason)
            return
        }
        if (!activeNeedsStartupHydration()) {
            root.startupDeferredHydrationPending = true
            return
        }
        if (!startupAllowsHeavyWorkNow("runStartupHydration:" + String(reason || "unspecified"))) {
            scheduleStartupHydration(reason)
            return
        }
        root.startupDeferredHydrationPending = false
        root.startupHydrationCompleted = true
        refreshLookupLists()
        loadDeadlineFilterPreferences()
        if (initialState) {
            applyInitialState(initialState)
        }
        if (root.persistedBucketKey.length <= 0) {
            root.persistedBucketKey = currentBucketKey()
        }
        if (!root.dirty) {
            scheduleBucketRefresh()
        }
        root.setDeadlineRangeDefaultWeek()
        root.refreshDeadlineMatterOptions()
        root.loadDeadlines()
        if (root.activeIsDocketReport() || root.docketReportPanelLoadRequested) {
            requestDocketReportPanelLoad("runStartupHydration", false)
        }
    }

    function applyPendingDocketReportState() {
        if (root.pendingDocketReportState === null || root.pendingDocketReportState === undefined) {
            return false
        }
        var panel = root.docketActivityReportPanel
        if (!panel || !panel.applyState) {
            return false
        }
        panel.applyState(root.pendingDocketReportState, false)
        root.pendingDocketReportState = null
        return true
    }

    function requestDocketReportPanelLoad(reason, runAfterLoad) {
        var shouldRun = runAfterLoad === true
        if (shouldRun) {
            root.docketReportPanelPendingRun = true
        }
        root.docketReportPanelLoadRequested = true

        if (!root.visible || !root.activeIsDocketReport()) {
            return false
        }
        if (!startupAllowsHeavyWorkNow("docketReportPanelLoad:" + String(reason || "unspecified"))) {
            scheduleStartupHydration("docketReportPanelLoad:" + String(reason || "unspecified"))
            return false
        }
        if (docketActivityReportPanelLoader && !docketActivityReportPanelLoader.active) {
            docketActivityReportPanelLoader.active = true
        }

        var panel = root.docketActivityReportPanel
        if (panel) {
            root.docketReportPanelLoadRequested = false
            applyPendingDocketReportState()
            if (root.docketReportPanelPendingRun && panel.runReport) {
                root.docketReportPanelPendingRun = false
                panel.runReport(true)
            }
            return true
        }
        return false
    }


    // Mode
    property bool isFloating: false
    property bool detachedWindow: false
    property int tileIndex: 1
    property string titleText: "Docketing & Deadlines"
    property var navItems: []
    property var laneSummary: ({})
    property bool externalNavigationShell: false

    // buttons that appear at top of every module sidebar
    property var laneSwitchModel: [
        { "tileIndex": 0, "title": "Clients",   "shortTitle": "Clients",   "compactTitle": "C" },
        { "tileIndex": 1, "title": "Docketing", "shortTitle": "Docket",    "compactTitle": "D" },
        { "tileIndex": 2, "title": "Billing",   "shortTitle": "Billing",   "compactTitle": "B" },
        { "tileIndex": 3, "title": "Finance",   "shortTitle": "Finance",   "compactTitle": "F" }
    ]

    // trademark state cache
    // B16 = entry form, B17 = directory/search
    property var tf_state: ({})
    property var td_state: ({})
    property var _perfMarks: ({})

    function perfLog(message) {
        var text = "[PERF] TimeDocketView " + String(message || "")
        if (root.windowRef && root.windowRef.lagLog) {
            root.windowRef.lagLog(text)
        } else {
            console.log(text)
        }
    }

    function perfStart(key, detail) {
        _perfMarks = PerfTrace.markStart(_perfMarks, key)
        perfLog("start key=" + String(key || "") + " " + String(detail || ""))
    }

    function perfEnd(key, detail) {
        var result = PerfTrace.markFinish(_perfMarks, key)
        _perfMarks = result.marks
        if (result.elapsedMs < 0) return
        perfLog("end key=" + String(key || "") + " elapsedMs=" + String(result.elapsedMs)
            + " " + String(detail || ""))
    }
    property string tf_appNo: ""
    property string tf_trademark: ""
    property string tf_office: ""
    property string tf_status: ""
    property string tf_notes: ""
    property bool trademarkFormDirty: false

    function formHasContent() {
        if (activeIsTrademarkEntry()) {
            return !!root.trademarkFormDirty
        }
        if (activeIsTrademarkDirectory()) {
            return !!(root.tf_state && root.tf_state.dirty)
        }
        var secs = Math.max(0, Math.floor(root.elapsedSeconds || 0))
        if (secs > 0) return true
        if (descInput && String(descInput.text || "").trim().length > 0) return true
        return false
    }

    function maybeMarkDirty() {
        if (root._hydrating) return
        root.dirty = formHasContent()
    }

    function currentDirtyState() {
        if (activeSubwindowId === "B04") return false; // DOCKET REPORT IS NEVER DIRTY
        if (root.activeIsFeeDocket()) return !!(feeDocketEntryPanel && feeDocketEntryPanel.dirty);
        if (root.activeIsTrademarkEntry()) return !!root.trademarkFormDirty;
        if (root.activeIsTrademarkDirectory()) return !!(root.tf_state && root.tf_state.dirty);
        if (root.activeIsDeadlineEditor()) return !!root.deadlineFormDirty;
        return !!root.dirty;
    }

    function activeIsTrademarkEntry() {
        return String(activeSubwindowId || "") === "B16"
    }

    function activeIsTrademarkDirectory() {
        return String(activeSubwindowId || "") === "B17"
    }

    function activeIsTrademark() {
        return activeIsTrademarkEntry() || activeIsTrademarkDirectory()
    }
    property string activeSubwindowId: "B01"
    property bool _returnToReportOnCancel: false
    property int _returnToTileIndex: -1
    property string _returnToNodeId: ""

    // deadline/calendar state (NP-10)
    property var deadlines: []             // full list from backend
    property date calendarSelectedDate: new Date()
    property date deadlineRangeStartDate: new Date()
    property date deadlineRangeEndDate: new Date((new Date()).getTime() + (6 * 24 * 60 * 60 * 1000))
    property var calendarEntries: []       // entries for selected date range (+ overdue open)
    property var editingDeadline: ({})      // entry currently in editor
    property string selectedCalendarEntryId: ""
    property string pendingBriefingDeadlineId: ""
    property string pendingBriefingCalendarDate: ""
    property var deadlineMatterDirectory: []
    property var deadlineMatterOptions: ["General"]
    property var deadlineClientOptions: ["All", "Non-client related"]
    property string deadlineFilterMatter: "All"
    property string deadlineFilterClient: "All"
    property bool deadlineFilterShowOpen: true
    property bool deadlineFilterShowCompleted: true
    property bool deadlineFilterShowInformationOnly: true
    property bool deadlineFilterShowTasks: true
    property bool deadlineFilterActionableOnly: false
    property bool deadlineFilterPrefsHydrating: false
    property string deadlineDatePickerTarget: ""

    // Transferable state
    property var initialState: null
    property int elapsedSeconds: 0
    property bool isRunning: false

    // Dirty tracking
    property bool dirty: false
    property bool _hydrating: false
    property bool saveInProgress: false
    property bool lastSaveWasExact: false
    property string lastSavedEntryId: ""
    property int lastPersistedSeconds: 0
    property string persistedBucketKey: ""
    property string _inactiveMatterId: ""
    property var _inactiveMatterRow: ({})
    property var pendingSaveOptions: ({})
    property string pendingSaveReason: ""
    property bool autoPostOnStop: true
    property bool aggregateLoadInProgress: false
    property bool startupDeferredHydrationPending: false
    property bool startupHydrationCompleted: false
    property int startupHydrationRetryMs: 220
    property bool docketReportPanelLoadRequested: false
    property bool docketReportPanelPendingRun: false
    property bool docketReportPanelPendingOpenReportWindow: false
    property var pendingDocketReportState: null
    property var recentDocketsModel: []
    property string docketStatusText: "Draft"

    ArchivedMatterEntryGuardDialog {
        id: inactiveMatterPopup
        t: root.t
        appRef: root.appRef
        entryKind: "time"
        onEntryConfirmed: {
            root.continuePendingSave({ "skipInactivePrompt": true })
        }
    }

    Popup {
        id: recentDocketsPopup
        width: 675
        x: Math.round((root.width - width) / 2)
        y: Math.round(root.height * 0.15)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        
        background: Rectangle {
            color: root._bg
            radius: 8
            border.color: root._accent
            border.width: 1
        }
        
        contentItem: ColumnLayout {
            spacing: 0
            
            Rectangle {
                Layout.fillWidth: true
                height: 40
                color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.1)
                radius: 8
                
                // Keep bottom corners square so it merges with the list
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 8
                    color: parent.color
                }
                
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    text: "Recent Entries (" + dateInput.text + ")"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                }

            }
            
            ListView {
                id: recentDocketsListView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(350, contentHeight)
                clip: true
                model: root.recentDocketsModel
                spacing: 0
                
                delegate: Rectangle {
                    required property var modelData

                    width: ListView.view.width
                    height: 55
                    color: itemMa.containsMouse ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.05) : "transparent"
                    border.color: root._border
                    border.width: 1

                    MouseArea {
                        id: itemMa
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            recentDocketsPopup.close()
                            root.openReportEntryForEdit(modelData)
                        }
                    }
                    
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 2
                        
                        Text {
                            text: {
                                var c = modelData ? modelData.clientName : ""
                                var m = modelData ? modelData.matterName : ""
                                return c + (m ? " — " + m : "")
                            }
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: root._fg
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: {
                                var h = modelData ? modelData.hours : "0"
                                var d = modelData ? modelData.Description : ""
                                return h + "h | " + String(d).replace(/\n/g, ' ')
                            }
                            font.pixelSize: 13
                            color: root._fgLight
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
    property string timerOwnerId: ""
    property string timerLockNotice: ""
    property var timerLockHolder: ({})
    property bool forceCleanDocketTimerContext: false
    property double activeSegmentStartedAtMs: 0
    property string saveFeedbackText: ""
    property bool saveFeedbackIsError: false
    property string originalLoadedTime: ""
    property string originalLoadedRate: ""
    
    property string timeFieldValidationMessage: ""
    property bool _manualTimeCommitBusy: false
    property var _rawClientDirectory: []
    property var _rawMatterDirectory: []

    signal detachRequested(var state)
    signal returnRequested(var state)
    signal moduleJumpRequested(int tileIndex, var state)
    signal reportWindowRequested(var reportDocument)
    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)
    signal workspaceNavChanged(int tileIndex, var state)

    function ensureTrademarkDirectoryNavNode(list) {
        var src = (list && list.length !== undefined) ? list : []
        var out = []
        var hasEntry = false
        var hasDirectory = false
        var insertAt = -1

        for (var i = 0; i < src.length; i++) {
            var row = src[i]
            var rowId = row && row.id !== undefined ? String(row.id || "") : ""
            out.push(row)
            if (rowId === "B16") {
                hasEntry = true
                insertAt = out.length
            } else if (rowId === "B17") {
                hasDirectory = true
            }
        }

        if (hasEntry && !hasDirectory) {
            var directoryNode = { "id": "B17", "title": "Trademark Directory" }
            if (insertAt >= 0 && insertAt <= out.length) {
                out.splice(insertAt, 0, directoryNode)
            } else {
                out.push(directoryNode)
            }
        }
        return out
    }

    function normalizedNavItems() {
        if (navItems && navItems.length !== undefined && navItems.length > 0) {
            return ensureTrademarkDirectoryNavNode(navItems)
        }
        return ensureTrademarkDirectoryNavNode([
            { "id": "B01", "title": "Time Docket Entry" },
            { "id": "B03", "title": "Timer Console" },
            { "id": "B02", "title": "Fee Docket Entry" },
            { "id": "B05", "title": "Move Dockets Between Matters" },
            { "id": "B04", "title": "Docket Activity Report" },
            { "id": "B16", "title": "Trademark Filing" },
            { "id": "B07", "title": "Deadline Master Calendar" },
            { "id": "B08", "title": "Deadline Entry Editor" }
        ])
    }

    function currentNavNode() {
        var list = normalizedNavItems()
        for (var i = 0; i < list.length; i++) {
            if (String(list[i].id || "") === String(activeSubwindowId || "")) {
                return list[i]
            }
        }
        if (list.length > 0) return list[0]
        return { "id": "B01", "title": "Time Docket Entry" }
    }

    function ensureActiveSubwindow() {
        var list = normalizedNavItems()
        if (list.length <= 0) {
            activeSubwindowId = ""
            return
        }
        var wanted = String(activeSubwindowId || "").trim()
        if (wanted.length <= 0) wanted = "B01"
        var found = false
        for (var i = 0; i < list.length; i++) {
            if (String(list[i].id || "") === wanted) {
                found = true
                break
            }
        }
        if (!found) wanted = String(list[0].id || "B01")
        activeSubwindowId = wanted
    }

    function activeIsLiveDocket() {
        return String(activeSubwindowId || "") === "B01"
    }

    function activeIsFeeDocket() {
        return String(activeSubwindowId || "") === "B02"
    }

    function activeIsTimerConsole() {
        return String(activeSubwindowId || "") === "B03"
    }

    function activeIsDocketReport() {
        return String(activeSubwindowId || "") === "B04"
    }

    function activeIsBulkDocketMove() {
        return String(activeSubwindowId || "") === "B05"
    }

    function activeIsDeadlineCalendar() {
        return String(activeSubwindowId || "") === "B07"
    }

    function activeIsDeadlineEditor() {
        return String(activeSubwindowId || "") === "B08"
    }

    function activeUsesDocketContext() {
        return activeIsLiveDocket() || activeIsFeeDocket() || activeIsTimerConsole() || activeIsBulkDocketMove()
    }

    function normalizedDocketStatus(value) {
        var s = String(value || "").trim().toLowerCase()
        if (s === "ready for billing" || s === "ready_for_billing" || s === "ready") return "Ready for Billing"
        if (s === "billed" || s === "posted" || s === "finalized" || s === "locked") return "Billed"
        return "Draft"
    }

    // --- deadline helpers ------------------------------------------------------
    function _formatDate(d) {
        if (!d) return ""
        d = new Date(d)
        return Qt.formatDate(d, "yyyy-MM-dd")
    }

    function _parseDate(txt) {
        var d = new Date(txt)
        return isNaN(d.getTime()) ? new Date() : d
    }

    function _looksIsoDate(txt) {
        return /^\d{4}-\d{2}-\d{2}$/.test(String(txt || "").trim())
    }

    function _startOfDay(d) {
        var out = _parseDate(d)
        out.setHours(0, 0, 0, 0)
        return out
    }

    function _addDays(d, days) {
        var out = _startOfDay(d)
        out.setDate(out.getDate() + Number(days || 0))
        return out
    }

    function setDeadlineRange(startDate, endDate) {
        var start = _startOfDay(startDate)
        var end = _startOfDay(endDate)
        if (end.getTime() < start.getTime()) {
            var swap = start
            start = end
            end = swap
        }
        root.deadlineRangeStartDate = start
        root.deadlineRangeEndDate = end
        root.calendarSelectedDate = start
        root._refreshCalendarEntries()
        if (deadlineRangeFromField && !deadlineRangeFromField.activeFocus) {
            deadlineRangeFromField.text = _formatDate(start)
        }
        if (deadlineRangeToField && !deadlineRangeToField.activeFocus) {
            deadlineRangeToField.text = _formatDate(end)
        }
    }

    function setDeadlineRangeDefaultWeek() {
        var today = _startOfDay(new Date())
        setDeadlineRange(today, _addDays(today, 6))
    }

    function setDeadlineRangeAllTime() {
        setDeadlineRange(new Date(1999, 0, 1), new Date(2199, 11, 31))
    }

    function openDeadlineDatePicker(targetKey, selectedDate, anchorItem) {
        root.deadlineDatePickerTarget = String(targetKey || "")
        deadlineCalendarLoader.active = true
        Qt.callLater(function() {
            var cal = deadlineCalendarLoader.item
            if (!cal) return
            cal.selectedDate = _parseDate(selectedDate)

            var px = -1
            var py = -1
            try {
                if (anchorItem && anchorItem.mapToGlobal) {
                    var anchorW = (typeof anchorItem.width === "number") ? anchorItem.width : 0
                    var anchorH = (typeof anchorItem.height === "number") ? anchorItem.height : 0
                    var p = anchorItem.mapToGlobal(Math.round(anchorW * 0.5), Math.round(anchorH))
                    px = p.x
                    py = p.y
                }
            } catch (e1) {
            }

            if (typeof cal.openAt === "function") cal.openAt(px, py)
            else if (typeof cal.open === "function") cal.open()
            else cal.visible = true
        })
    }

    function _deadlineInRangeOrOverdueOpen(entry, rangeStart, rangeEnd) {
        var due = _startOfDay(entry && entry.date ? entry.date : new Date())
        var inRange = due.getTime() >= rangeStart.getTime() && due.getTime() <= rangeEnd.getTime()
        if (inRange) return true
        var overdueOpen = due.getTime() < rangeStart.getTime() && !Boolean(entry && entry.completed)
        return overdueOpen
    }

    function _normalizeEditingDeadline(entry) {
        var out = JSON.parse(JSON.stringify(entry || {}))
        out.date = _formatDate(out.date || root.calendarSelectedDate)
        out.description = String(out.description || "")
        out.escalated = !!out.escalated
        out.completed = !!out.completed
        out.clientName = String(out.clientName || "")
        out.entryType = _deadlineEntryType(out)
        out.assignmentType = (String(out.assignmentType || "").toLowerCase() === "matter" || String(out.matterName || "").trim().length > 0)
            ? "Matter"
            : "General"
        out.matterId = String(out.matterId || "")
        out.matterName = String(out.matterName || "")
        if (out.assignmentType !== "Matter") {
            out.matterId = ""
            out.matterName = ""
        }
        // Task-specific fields
        out.workDate = String(out.workDate || "")
        out.priority = String(out.priority || "Normal")
        out.reminderNote = String(out.reminderNote || "")
        out.recurrence = String(out.recurrence || "None")
        out.recurrenceInterval = parseInt(out.recurrenceInterval) || 1
        out.recurrenceEndDate = String(out.recurrenceEndDate || "")
        return out
    }

    function _deadlineMatterRecordByName(label) {
        var target = String(label || "").trim().toLowerCase()
        if (!target.length) return null
        for (var i = 0; i < root.deadlineMatterDirectory.length; i++) {
            var row = root.deadlineMatterDirectory[i] || {}
            var display = String(row.displayName || "").trim().toLowerCase()
            var matter = String(row.matterName || "").trim().toLowerCase()
            if (display === target || matter === target) return row
        }
        return null
    }

    function _deadlineMatterDisplayName(row) {
        var src = row || {}
        var client = String(src.clientName || "").trim()
        var matter = String(src.matterName || src.displayName || src.matterNumber || src.matterId || "").trim()
        if (client.length > 0 && matter.length > 0) {
            return client + "|" + matter
        }
        return matter
    }

    function _coerceArray(value) {
        if (Array.isArray(value)) return value.slice(0)
        if (value && typeof value.length === "number") {
            var out = []
            for (var i = 0; i < value.length; i++) out.push(value[i])
            return out
        }
        if (value && Array.isArray(value.items)) return value.items.slice(0)
        if (value && Array.isArray(value.rows)) return value.rows.slice(0)
        if (value && Array.isArray(value.data)) return value.data.slice(0)
        return []
    }

    function _deadlineEntryType(entry) {
        var raw = String((entry && (entry.entryType || entry.category || entry.type)) || "").trim().toLowerCase()
        if (raw === "task" || raw === "reminder" || raw === "tickler" || raw === "todo" || raw === "to-do") {
            return "Task"
        }
        if (raw === "information" || raw === "information only" || raw === "info" || raw === "info-only") {
            return "Information"
        }
        return "Deadline"
    }

    function _deadlineIsTask(entry) {
        return _deadlineEntryType(entry) === "Task"
    }

    function _deadlineIsInformationOnly(entry) {
        return _deadlineEntryType(entry) === "Information"
    }

    function _deadlineEntryMatterLabel(entry) {
        var assignment = String((entry && entry.assignmentType) || "").trim().toLowerCase()
        var matterName = String((entry && entry.matterName) || "").trim()
        return (assignment === "matter" && matterName.length > 0) ? matterName : "General"
    }

    function _deadlineEntryClientName(entry) {
        var direct = String((entry && entry.clientName) || "").trim()
        if (direct.length > 0) return direct
        var matterId = String((entry && entry.matterId) || "").trim()
        var matterName = String((entry && entry.matterName) || "").trim().toLowerCase()
        if (matterId.length <= 0 && matterName.length <= 0) return ""
        for (var i = 0; i < root.deadlineMatterDirectory.length; i++) {
            var row = root.deadlineMatterDirectory[i] || {}
            if (matterId.length > 0 && String(row.matterId || "").trim() === matterId) {
                return String(row.clientName || "").trim()
            }
            if (matterName.length > 0 && String(row.matterName || "").trim().toLowerCase() === matterName) {
                return String(row.clientName || "").trim()
            }
        }
        return ""
    }

    function refreshDeadlineFilterOptions() {
        var matterLabels = ["All", "General"]
        var seenMatter = { "all": true, "general": true }
        var clientLabels = ["All", "Non-client related"]
        var seenClient = { "all": true, "non-client related": true }

        function sameStringArray(lhs, rhs) {
            if (!Array.isArray(lhs) || !Array.isArray(rhs)) return false
            if (lhs.length !== rhs.length) return false
            for (var i = 0; i < lhs.length; i++) {
                if (String(lhs[i]) !== String(rhs[i])) return false
            }
            return true
        }

        function pushMatter(raw) {
            var label = String(raw || "").trim()
            if (!label.length) return
            var key = label.toLowerCase()
            if (seenMatter[key]) return
            seenMatter[key] = true
            matterLabels.push(label)
        }

        function pushClient(raw) {
            var label = String(raw || "").trim()
            if (!label.length) return
            var key = label.toLowerCase()
            if (seenClient[key]) return
            seenClient[key] = true
            clientLabels.push(label)
        }

        for (var i = 0; i < root.deadlineMatterDirectory.length; i++) {
            var row = root.deadlineMatterDirectory[i] || {}
            pushMatter(String(row.matterName || row.displayName || ""))
            pushClient(String(row.clientName || ""))
        }

        for (var j = 0; j < root.deadlines.length; j++) {
            var entry = root.deadlines[j] || {}
            pushMatter(_deadlineEntryMatterLabel(entry))
            pushClient(_deadlineEntryClientName(entry))
        }

        root.deadlineMatterOptions = root.deadlineMatterOptions || ["General"]
        if (matterLabels.length <= 0) matterLabels = ["All", "General"]
        if (clientLabels.length <= 0) clientLabels = ["All", "Non-client related"]

        var selectedMatter = String(root.deadlineFilterMatter || "All").trim()
        var selectedClient = String(root.deadlineFilterClient || "All").trim()
        if (selectedMatter.length > 0 && matterLabels.indexOf(selectedMatter) < 0) {
            matterLabels.push(selectedMatter)
        }
        if (selectedClient.length > 0 && clientLabels.indexOf(selectedClient) < 0) {
            clientLabels.push(selectedClient)
        }

        if (!sameStringArray(root.deadlineClientOptions, clientLabels)) {
            root.deadlineClientOptions = clientLabels
        }
        if (!sameStringArray(root.deadlineMatterFilterOptions, matterLabels)) {
            root.deadlineMatterFilterOptions = matterLabels
        }
    }

    property var deadlineMatterFilterOptions: ["All", "General"]

    function deadlineFilterStatePayload() {
        return {
            "matter": String(root.deadlineFilterMatter || "All"),
            "client": String(root.deadlineFilterClient || "All"),
            "showOpen": !!root.deadlineFilterShowOpen,
            "showCompleted": !!root.deadlineFilterShowCompleted,
            "showInformationOnly": !!root.deadlineFilterShowInformationOnly,
            "showTasks": !!root.deadlineFilterShowTasks,
            "actionableOnly": !!root.deadlineFilterActionableOnly
        }
    }

    function applyDeadlineFilterState(rawState, persistAfter) {
        var state = rawState || {}
        var shouldPersist = (persistAfter === undefined) ? false : !!persistAfter
        root.deadlineFilterPrefsHydrating = true
        root.deadlineFilterMatter = String(state.matter || "All").trim() || "All"
        root.deadlineFilterClient = String(state.client || "All").trim() || "All"
        root.deadlineFilterShowOpen = !!(state.showOpen !== undefined ? state.showOpen : true)
        root.deadlineFilterShowCompleted = !!(state.showCompleted !== undefined ? state.showCompleted : true)
        root.deadlineFilterShowInformationOnly = !!(state.showInformationOnly !== undefined ? state.showInformationOnly : true)
        root.deadlineFilterShowTasks = !!(state.showTasks !== undefined ? state.showTasks : true)
        root.deadlineFilterActionableOnly = !!(state.actionableOnly || false)
        if (root.deadlineFilterActionableOnly) {
            root.deadlineFilterShowInformationOnly = false
        }
        if (!root.deadlineFilterShowOpen && !root.deadlineFilterShowCompleted && !root.deadlineFilterShowInformationOnly && !root.deadlineFilterShowTasks) {
            if (root.deadlineFilterActionableOnly) root.deadlineFilterShowOpen = true
            else root.deadlineFilterShowInformationOnly = true
        }
        root.deadlineFilterPrefsHydrating = false
        refreshDeadlineFilterOptions()
        root._refreshCalendarEntries()
        if (shouldPersist) persistDeadlineFilterPreferences()
    }

    function persistDeadlineFilterPreferences() {
        if (root.deadlineFilterPrefsHydrating) return
        var svc = root.appRef ? root.appRef : (typeof app !== "undefined" ? app : null)
        if (!svc || !svc.saveDeadlineCalendarFilters) return
        svc.saveDeadlineCalendarFilters(deadlineFilterStatePayload())
    }

    function loadDeadlineFilterPreferences() {
        if (!startupAllowsHeavyWorkNow("loadDeadlineFilterPreferences")) {
            scheduleStartupHydration("loadDeadlineFilterPreferences")
            return
        }
        var svc = root.appRef ? root.appRef : (typeof app !== "undefined" ? app : null)
        if (!svc || !svc.getDeadlineCalendarFilters) return
        var state = svc.getDeadlineCalendarFilters()
        if (!state || typeof state !== "object") return
        applyDeadlineFilterState(state, false)
    }

    function setDeadlineMatterFilter(value, shouldPersist) {
        var nextValue = String(value || "").trim()
        if (nextValue.length <= 0) nextValue = "All"
        if (root.deadlineFilterMatter === nextValue) return
        root.deadlineFilterMatter = nextValue
        refreshDeadlineFilterOptions()
        root._refreshCalendarEntries()
        if (shouldPersist !== false) persistDeadlineFilterPreferences()
    }

    function setDeadlineClientFilter(value, shouldPersist) {
        var nextValue = String(value || "").trim()
        if (nextValue.length <= 0) nextValue = "All"
        if (root.deadlineFilterClient === nextValue) return
        root.deadlineFilterClient = nextValue
        refreshDeadlineFilterOptions()
        root._refreshCalendarEntries()
        if (shouldPersist !== false) persistDeadlineFilterPreferences()
    }

    function setDeadlineActionableOnly(enabled, shouldPersist) {
        var nextValue = !!enabled
        if (root.deadlineFilterActionableOnly === nextValue && !(nextValue && root.deadlineFilterShowInformationOnly)) {
            return
        }
        root.deadlineFilterActionableOnly = nextValue
        if (nextValue) {
            root.deadlineFilterShowInformationOnly = false
            if (!root.deadlineFilterShowOpen && !root.deadlineFilterShowCompleted) {
                root.deadlineFilterShowOpen = true
            }
        }
        root._refreshCalendarEntries()
        if (shouldPersist !== false) persistDeadlineFilterPreferences()
    }

    function setDeadlineStatusFilter(kind, checked, shouldPersist) {
        if (kind === "open") root.deadlineFilterShowOpen = !!checked
        else if (kind === "completed") root.deadlineFilterShowCompleted = !!checked
        else if (kind === "information") {
            if (root.deadlineFilterActionableOnly && !!checked) {
                root.deadlineFilterActionableOnly = false
            }
            root.deadlineFilterShowInformationOnly = !!checked
        } else if (kind === "tasks") {
            root.deadlineFilterShowTasks = !!checked
        }
        if (!root.deadlineFilterShowOpen && !root.deadlineFilterShowCompleted
                && !root.deadlineFilterShowInformationOnly && !root.deadlineFilterShowTasks) {
            if (root.deadlineFilterActionableOnly) root.deadlineFilterShowOpen = true
            else if (kind === "completed") root.deadlineFilterShowCompleted = true
            else if (kind === "information") root.deadlineFilterShowInformationOnly = true
            else if (kind === "tasks") root.deadlineFilterShowTasks = true
            else root.deadlineFilterShowOpen = true
        }
        root._refreshCalendarEntries()
        if (shouldPersist !== false) persistDeadlineFilterPreferences()
    }

    function _deadlinePassesFilters(entry) {
        var matterFilter = String(root.deadlineFilterMatter || "All")
        var clientFilter = String(root.deadlineFilterClient || "All")
        var matterLabel = _deadlineEntryMatterLabel(entry)
        var clientLabel = _deadlineEntryClientName(entry)
        var isInfo = _deadlineIsInformationOnly(entry)
        var isTask = _deadlineIsTask(entry)
        var isCompleted = !!(entry && entry.completed)

        if (matterFilter !== "All" && matterLabel !== matterFilter) return false
        if (clientFilter === "Non-client related") {
            if (clientLabel.length > 0) return false
        } else if (clientFilter !== "All" && clientLabel !== clientFilter) {
            return false
        }

        if (isInfo && root.deadlineFilterActionableOnly) return false
        if (isInfo) return root.deadlineFilterShowInformationOnly
        if (isTask) {
            if (!root.deadlineFilterShowTasks) return false
            if (isCompleted) return root.deadlineFilterShowCompleted
            return root.deadlineFilterShowOpen
        }
        if (isCompleted) return root.deadlineFilterShowCompleted
        return root.deadlineFilterShowOpen
    }

    function _deadlineEditingMatterDisplayName() {
        var assignment = String(root.editingDeadline.assignmentType || "").toLowerCase()
        var matterId = String(root.editingDeadline.matterId || "").trim()
        var matterName = String(root.editingDeadline.matterName || "").trim()
        if (assignment !== "matter" || matterName.length <= 0) {
            return "General"
        }
        for (var i = 0; i < root.deadlineMatterDirectory.length; i++) {
            var row = root.deadlineMatterDirectory[i] || {}
            if (matterId.length > 0 && String(row.matterId || "").trim() === matterId) {
                return String(row.displayName || matterName)
            }
            if (String(row.matterName || "").trim().toLowerCase() === matterName.toLowerCase()) {
                return String(row.displayName || matterName)
            }
        }
        return matterName
    }

    function refreshDeadlineMatterOptions() {
        if (!startupAllowsHeavyWorkNow("refreshDeadlineMatterOptions")) {
            scheduleStartupHydration("refreshDeadlineMatterOptions")
            return
        }
        var svc = root.appRef ? root.appRef : (typeof app !== "undefined" ? app : null)
        var directory = []
        var labels = ["General"]
        var seenLabels = { "general": true }
        var seenDirectory = {}

        function pushLabel(raw) {
            var label = String(raw || "").trim()
            if (!label.length) return
            var key = label.toLowerCase()
            if (seenLabels[key]) return
            seenLabels[key] = true
            labels.push(label)
        }

        function pushDirectory(row) {
            var src = row || {}
            var matterName = String(src.matterName || src.displayName || src.matterNumber || src.matterId || "").trim()
            var display = root._deadlineMatterDisplayName(src)
            if (!display.length) return
            var key = display.toLowerCase()
            if (!seenDirectory[key]) {
                directory.push({
                    "matterId": String(src.matterId || ""),
                    "matterName": matterName,
                    "clientName": String(src.clientName || ""),
                    "displayName": display,
                    "matterNumber": String(src.matterNumber || "")
                })
                seenDirectory[key] = true
            }
            pushLabel(display)
        }

        var rows = []
        if (svc && svc.listActiveMatterDirectory) {
            rows = svc.listActiveMatterDirectory()
        }
        if (!Array.isArray(rows) || rows.length <= 0) {
            rows = []
        }
        if (svc && svc.listMatterDirectory) {
            var allRows = svc.listMatterDirectory()
            if ((!Array.isArray(rows) || rows.length <= 0) && Array.isArray(allRows)) {
                rows = allRows
            } else if (Array.isArray(allRows)) {
                for (var ar = 0; ar < allRows.length; ar++) {
                    pushDirectory(allRows[ar])
                }
            }
        }
        if (Array.isArray(rows)) {
            for (var i = 0; i < rows.length; i++) {
                pushDirectory(rows[i])
            }
        }

        if (svc && svc.listActiveMatterNames) {
            var activeNames = svc.listActiveMatterNames()
            if (Array.isArray(activeNames)) {
                for (var an = 0; an < activeNames.length; an++) {
                    var activeLabel = String(activeNames[an] || "").trim()
                    if (!activeLabel.length) continue
                    pushLabel(activeLabel)
                    var activeKey = activeLabel.toLowerCase()
                    if (!seenDirectory[activeKey]) {
                        directory.push({
                            "matterId": "",
                            "matterName": activeLabel,
                            "clientName": "",
                            "displayName": activeLabel,
                            "matterNumber": ""
                        })
                        seenDirectory[activeKey] = true
                    }
                }
            }
        }

        if (svc && svc.listMatterNames) {
            var names = svc.listMatterNames()
            if (Array.isArray(names)) {
                for (var n = 0; n < names.length; n++) {
                    var label = String(names[n] || "").trim()
                    if (!label.length) continue
                    pushLabel(label)
                    var nameKey = label.toLowerCase()
                    if (!seenDirectory[nameKey]) {
                        directory.push({
                            "matterId": "",
                            "matterName": label,
                            "clientName": "",
                            "displayName": label,
                            "matterNumber": ""
                        })
                        seenDirectory[nameKey] = true
                    }
                }
            }
        }

        if (matterCombo && Array.isArray(matterCombo.fullModel)) {
            for (var c = 0; c < matterCombo.fullModel.length; c++) {
                var cached = String(matterCombo.fullModel[c] || "").trim()
                if (!cached.length) continue
                pushLabel(cached)
                var cachedKey = cached.toLowerCase()
                if (!seenDirectory[cachedKey]) {
                    directory.push({
                        "matterId": "",
                        "matterName": cached,
                        "clientName": "",
                        "displayName": cached,
                        "matterNumber": ""
                    })
                    seenDirectory[cachedKey] = true
                }
            }
        }

        root.deadlineMatterDirectory = directory
        root.deadlineMatterOptions = labels
        refreshDeadlineFilterOptions()

        if (labels.length <= 1 && svc && svc.backendBooted === false) {
            deadlineMatterOptionsRetryTimer.restart()
        }
    }

    function loadDeadlines() {
        if (!startupAllowsHeavyWorkNow("loadDeadlines")) {
            scheduleStartupHydration("loadDeadlines")
            return
        }
        perfStart("master.calendar.loadDeadlines", "activeSubwindowId=" + String(root.activeSubwindowId || ""))
        var result = app && app.listDeadlines ? app.listDeadlines() : []
        var rows = _coerceArray(result)
        if (rows.length > 0 || (result && typeof result.length === "number")) {
            root.deadlines = rows
            refreshDeadlineFilterOptions()
            root._refreshCalendarEntries()
            perfEnd("master.calendar.loadDeadlines", "rows=" + rows.length)
            root._resolvePendingBriefingDeadlineNav()
            return
        }
        if (result && result.ok === false) {
            showSaveFeedback(result.message || "Could not load deadlines.", true)
        }
        root.deadlines = []
        refreshDeadlineFilterOptions()
        root._refreshCalendarEntries()
        perfEnd("master.calendar.loadDeadlines", "rows=0")
        root._resolvePendingBriefingDeadlineNav()
    }

    function _resolvePendingBriefingDeadlineNav() {
        var wantedId = String(root.pendingBriefingDeadlineId || "").trim()
        var wantedDate = String(root.pendingBriefingCalendarDate || "").trim()
        if (wantedId.length > 0) {
            root.pendingBriefingDeadlineId = ""
            root.pendingBriefingCalendarDate = ""
            for (var i = 0; i < root.deadlines.length; i++) {
                var entry = root.deadlines[i]
                if (String(entry.id || "") !== wantedId) continue
                if (wantedDate.length > 0) {
                    root.calendarSelectedDate = _parseDate(wantedDate)
                }
                root.startEditing(entry, true)
                return
            }
        }
        if (wantedDate.length > 0) {
            root.pendingBriefingCalendarDate = ""
            root.activeSubwindowId = "B07"
            root.ensureActiveSubwindow()
            root.selectCalendarDate(_parseDate(wantedDate))
        }
    }

    function _refreshCalendarEntries() {
        perfStart("master.calendar.refreshEntries", "deadlines=" + root.deadlines.length)
        var rangeStart = _startOfDay(root.deadlineRangeStartDate || new Date())
        var rangeEnd = _startOfDay(root.deadlineRangeEndDate || rangeStart)
        if (rangeEnd.getTime() < rangeStart.getTime()) {
            var tmp = rangeStart
            rangeStart = rangeEnd
            rangeEnd = tmp
        }
        root.calendarEntries = root.deadlines.filter(function(e) {
            return _deadlineInRangeOrOverdueOpen(e, rangeStart, rangeEnd) && _deadlinePassesFilters(e)
        })
        if (String(root.selectedCalendarEntryId || "").length > 0) {
            var stillExists = root.calendarEntries.some(function(e) {
                return String(e.id || "") === String(root.selectedCalendarEntryId || "")
            })
            if (!stillExists) root.selectedCalendarEntryId = ""
        }
        perfEnd("master.calendar.refreshEntries", "entries=" + root.calendarEntries.length)
    }

    function selectCalendarDate(d) {
        perfStart("master.calendar.selectDate", "date=" + _formatDate(d))
        root.calendarSelectedDate = new Date(d)
        root._refreshCalendarEntries()
        perfEnd("master.calendar.selectDate", "entries=" + root.calendarEntries.length)
    }

    function selectedCalendarEntry() {
        var id = String(root.selectedCalendarEntryId || "")
        if (id.length <= 0) return null
        for (var i = 0; i < root.calendarEntries.length; i++) {
            var entry = root.calendarEntries[i]
            if (String(entry.id || "") === id) return entry
        }
        return null
    }

    function startEditing(entry, switchToEditor) {
        refreshLookupLists()
        refreshDeadlineMatterOptions()
        if (entry) {
            root.editingDeadline = _normalizeEditingDeadline(entry)
            root.selectedCalendarEntryId = String(entry.id || "")
        } else {
            root.editingDeadline = _normalizeEditingDeadline({
                "date": _formatDate(root.calendarSelectedDate),
                "description": "",
                "escalated": false,
                "completed": false,
                "entryType": "Deadline",
                "assignmentType": "General",
                "clientName": "",
                "matterId": "",
                "matterName": ""
            })
        }
        var linkedMatter = String(root.editingDeadline.matterName || "").trim()
        var linkedDisplay = root._deadlineEditingMatterDisplayName()
        if (linkedMatter.length > 0 && linkedDisplay !== "General" && root.deadlineMatterOptions.indexOf(linkedDisplay) < 0) {
            var nextOptions = (root.deadlineMatterOptions || []).slice(0)
            nextOptions.push(linkedDisplay)
            root.deadlineMatterOptions = nextOptions
        }
        if (switchToEditor === undefined) switchToEditor = true
        if (switchToEditor) {
            root.activeSubwindowId = "B08"
            root.ensureActiveSubwindow()
        }
        if (deadlineEditorDateField && !deadlineEditorDateField.activeFocus) {
            deadlineEditorDateField.text = String(root.editingDeadline.date || root._formatDate(new Date()))
        }
    }

    function ensureEditingDeadlineSeeded() {
        var current = root.editingDeadline || ({})
        var hasId = String(current.id || "").length > 0
        var hasDate = String(current.date || "").trim().length > 0
        var hasDescription = String(current.description || "").trim().length > 0
        if (hasId || hasDate || hasDescription) return
        root.editingDeadline = _normalizeEditingDeadline({
            date: _formatDate(root.calendarSelectedDate),
            description: "",
            escalated: false,
            entryType: "Deadline"
        })
        if (deadlineEditorDateField && !deadlineEditorDateField.activeFocus) {
            deadlineEditorDateField.text = String(root.editingDeadline.date || _formatDate(new Date()))
        }
    }

    function editSelectedFromCalendar() {
        var selected = selectedCalendarEntry()
        if (!selected) {
            showSaveFeedback("Select a deadline row first.", true)
            return
        }
        startEditing(selected, true)
    }

    function saveEditing() {
        var payload = _normalizeEditingDeadline(root.editingDeadline || {})
        payload.date = _formatDate(_parseDate(payload.date))
        payload.description = String(payload.description || "").trim()
        if (payload.description.length <= 0) {
            showSaveFeedback("Deadline description is required.", true)
            return
        }
        payload.assignmentType = (String(payload.assignmentType || "").toLowerCase() === "matter") ? "Matter" : "General"
        if (payload.assignmentType === "Matter") {
            payload.matterName = String(payload.matterName || "").trim()
            if (!payload.matterName.length) {
                showSaveFeedback("Select a matter or switch this deadline to General.", true)
                return
            }
            var matterRecord = _deadlineMatterRecordByName(payload.matterName)
            payload.matterId = matterRecord ? String(matterRecord.matterId || "") : String(payload.matterId || "")
            payload.clientName = matterRecord ? String(matterRecord.clientName || "") : String(payload.clientName || "")
        } else {
            payload.matterId = ""
            payload.matterName = ""
            payload.clientName = ""
        }
        payload.entryType = String(payload.entryType || "Deadline")
        payload.completed = !!payload.completed
        payload.escalated = !!payload.escalated
        var res
        if (payload.id) {
            res = app.updateDeadline(payload.id, payload)
            if (res && res.ok === false) {
                showSaveFeedback(res.message || "Could not update deadline.", true)
                return
            }
            if (res && typeof res === "object") {
                root.editingDeadline = _normalizeEditingDeadline(res)
            }
            showSaveFeedback("Deadline updated.", false)
        } else {
            res = app.createDeadline(payload)
            if (res && res.ok === false) {
                showSaveFeedback(res.message || "Could not create deadline.", true)
                return
            }
            if (res && typeof res === "object") {
                root.editingDeadline = _normalizeEditingDeadline(res)
            }
            showSaveFeedback("Deadline created.", false)
        }
        root.calendarSelectedDate = _parseDate(payload.date)
        loadDeadlines()
        root.selectedCalendarEntryId = String((root.editingDeadline && root.editingDeadline.id) || "")
    }

    function deleteEditing() {
        if (root.editingDeadline && root.editingDeadline.id) {
            var ok = app.deleteDeadline(root.editingDeadline.id)
            if (ok) {
                showSaveFeedback("Deadline deleted.", false)
                loadDeadlines()
                root.selectedCalendarEntryId = ""
                root.editingDeadline = _normalizeEditingDeadline({
                    date: _formatDate(root.calendarSelectedDate),
                    description: "",
                    escalated: false,
                    completed: false,
                    assignmentType: "General"
                })
                root.activeSubwindowId = "B07"
                root.ensureActiveSubwindow()
            } else {
                showSaveFeedback("Could not delete deadline.", true)
            }
        }
    }

    function snoozeEditing() {
        if (!root.editingDeadline) return
        var d = _parseDate(root.editingDeadline.date)
        d.setDate(d.getDate() + 1)
        var newDate = _formatDate(d)
        root.editingDeadline.date = newDate
        if (root.editingDeadline.id) {
            var res = app.updateDeadline(root.editingDeadline.id, { "date": newDate })
            if (res && res.ok === false) {
                showSaveFeedback(res.message || "Could not snooze deadline.", true)
                return
            }
            showSaveFeedback("Deadline snoozed to " + newDate + ".", false)
            loadDeadlines()
        }
    }

    function escalateEditing() {
        if (!root.editingDeadline) return
        var nextValue = !Boolean(root.editingDeadline.escalated)
        root.editingDeadline.escalated = nextValue
        if (root.editingDeadline.id) {
            var res = app.updateDeadline(root.editingDeadline.id, { "escalated": nextValue })
            if (res && res.ok === false) {
                showSaveFeedback(res.message || "Could not update escalation.", true)
                return
            }
            showSaveFeedback(nextValue ? "Deadline escalated." : "Deadline de-escalated.", false)
            loadDeadlines()
        }
    }

    function toggleCompletedEditing() {
        if (!root.editingDeadline) return
        var nextValue = !Boolean(root.editingDeadline.completed)
        root.editingDeadline.completed = nextValue
        if (root.editingDeadline.id) {
            var res = app.updateDeadline(root.editingDeadline.id, { "completed": nextValue })
            if (res && res.ok === false) {
                showSaveFeedback(res.message || "Could not update completion state.", true)
                return
            }
            showSaveFeedback(nextValue ? "Deadline marked complete." : "Deadline reopened.", false)
            loadDeadlines()
        }
    }

    // ---------------------------------------------------------------------------

    function isBucketLocked() {
        return normalizedDocketStatus(root.docketStatusText) === "Billed"
    }

    function canMarkReadyForBilling() {
        if (root.isRunning) return false
        if (root.elapsedSeconds <= 0) return false
        if (String(clientCombo ? clientCombo.editText : "").trim().length <= 0) return false
        if (String(matterCombo ? matterCombo.editText : "").trim().length <= 0) return false
        return normalizedDocketStatus(root.docketStatusText) !== "Ready for Billing"
    }

    function canMarkBilled() {
        if (root.isRunning || root.isBucketLocked()) return false
        if (root.elapsedSeconds <= 0) return false
        return normalizedDocketStatus(root.docketStatusText) === "Ready for Billing"
    }

    function canSetDraft() {
        if (root.isRunning) return false
        let status = normalizedDocketStatus(root.docketStatusText)
        return status === "Ready for Billing" || status === "Billed"
    }

    function setDraftStatus() {
        if (!canSetDraft()) return
        requestSaveToDatabaseIfNeeded("set-draft", { "statusText": "Draft", "forceEditBilled": true })
    }

    function markReadyForBilling() {
        if (!canMarkReadyForBilling()) return
        requestSaveToDatabaseIfNeeded("mark-ready", { "statusText": "Ready for Billing", "forceEditBilled": true })
    }

    function markBilled() {
        if (!canMarkBilled()) return
        requestSaveToDatabaseIfNeeded("mark-billed", { "statusText": "Billed" })
    }

    function statusChipColor() {
        var status = normalizedDocketStatus(root.docketStatusText)
        if (status === "Billed") {
            return Qt.rgba(0.86, 0.30, 0.32, 0.92)
        }
        if (status === "Ready for Billing") {
            return Qt.rgba(0.94, 0.66, 0.18, 0.92)
        }
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.86)
    }

    function matterDisplayLabel(row) {
        var src = row || ({})
        var num = String(src.matterNumber || "").trim()
        var name = String(src.matterName || src.displayName || "").trim()
        if (num.length > 0 && name.length > 0) return num + " - " + name
        if (num.length > 0) return num
        return name
    }

    function setComboTextStrict(combo, valueText) {
        if (!combo) return
        var v = String(valueText || "")
        combo.preserveEditTextOnModelChanged = false
        combo.editText = v
        var idx = combo.find(v)
        if (idx >= 0) combo.currentIndex = idx
    }

    function getMatterRecordById(matterId) {
        var target = String(matterId || "").trim().toLowerCase()
        if (target.length <= 0 || !root._rawMatterDirectory) return null
        for (var i = 0; i < root._rawMatterDirectory.length; i++) {
            var row = root._rawMatterDirectory[i]
            if (String(row.matterId || "").trim().toLowerCase() === target) return row
        }
        return null
    }

    function currentMatterId() {
        var explicitId = String(root.selectedMatterId || "").trim()
        if (explicitId.length > 0) return explicitId
        var rec = root.getMatterRecordFromName(matterCombo ? matterCombo.editText : "")
        return rec ? String(rec.matterId || rec.matterNumber || "") : ""
    }

    function currentClientId() {
        var explicitId = String(root.selectedClientId || "").trim()
        if (explicitId.length > 0) return explicitId
        var rec = root.getClientRecordFromName(clientCombo ? clientCombo.editText : "")
        return rec ? String(rec.clientId || "") : ""
    }

    function updateSelectedMatterIdentityFromCombo() {
        var rec = root.getMatterRecordFromName(matterCombo ? matterCombo.editText : "")
        if (!rec) return
        root.selectedMatterId = String(rec.matterId || "")
        if (String(rec.clientId || "").trim().length > 0) root.selectedClientId = String(rec.clientId || "")
        if (String(rec.parentId || "").trim().length > 0) root.selectedParentId = String(rec.parentId || "")
    }

    function accrueRunningSegmentToRawSeconds() {
        if (!root.isRunning || root.activeSegmentStartedAtMs <= 0) return 0
        var elapsed = Math.max(0, Math.floor((Date.now() - root.activeSegmentStartedAtMs) / 1000))
        root.elapsedSeconds = Math.max(0, Math.floor(root.activeSegmentBaseSeconds || 0)) + elapsed
        root.syncTimeFieldFromElapsed()
        return elapsed
    }

    function applyAggregateResult(result) {
        if (root.timerProtectedMode || (root.timerIsRunningNow && root.timerIsRunningNow())) {
            return
        }
        if (root.cspmTimerWatchdogActive || root.isRunning || Number(root.activeSegmentStartedAtMs || 0) > 0) {
            return
        }
        if (root.timerIsActivelyRunning && root.timerIsActivelyRunning()) {
            return
        }
        if (!result || !result.ok || root.matter360QuickActionActiveNow() || root.isRunning) return
        var resultKey = String(result._bucketKey || "")
        if (resultKey.length > 0 && resultKey !== root._aggregateRequestKey) return

        if (result.exists) {
            root._hydrating = true
            var loadedSeconds = parseInt(result.aggregateRawSeconds)
            if (!isFinite(loadedSeconds) || loadedSeconds < 0) loadedSeconds = 0
            root.elapsedSeconds = Math.max(0, Math.floor(loadedSeconds))
            root.lastPersistedSeconds = root.elapsedSeconds
            root.persistedBucketKey = currentBucketKey()
            root.lastSavedEntryId = (result.entryId !== undefined && result.entryId !== null) ? String(result.entryId) : ""
            root.docketStatusText = normalizedDocketStatus(result.status)
            if (String(result.matterId || "").trim().length > 0) root.selectedMatterId = String(result.matterId || "").trim()

            var loadedRate = parseFloat(result.rate)
            if (isFinite(loadedRate) && loadedRate >= 0) rateInput.text = loadedRate.toFixed(2)
            var loadedShare = parseFloat(result.sharePct)
            if (isFinite(loadedShare) && loadedShare >= 0) billInput.text = String(loadedShare)
            if (String(descInput.text || "").trim().length <= 0 && result.description !== undefined) {
                descInput.text = String(result.description || "")
            }
            syncTimeFieldFromElapsed()
            calculateFees()
            root._hydrating = false
            return
        }

        setElapsedSecondsSafe(0)
        lastPersistedSeconds = 0
        lastSavedEntryId = ""
        docketStatusText = "Draft"
        persistedBucketKey = currentBucketKey()
    }

    function applyMatterQuickActionState(state) {
        if (root.timerProtectedMode || (root.timerIsRunningNow && root.timerIsRunningNow())) {
            return
        }
        if (!state || typeof state !== "object") return false

        root.refreshLookupLists()

        var matterId = String(state.matterId || state.selectedMatterId || "").trim()
        var rec = root.getMatterRecordById(matterId)
        var matterText = String(state.matterText !== undefined ? state.matterText : (state.matterName || state.selectedMatterName || "")).trim()
        if (!rec) rec = root.getMatterRecordFromName(matterText)

        var parentText = String(state.parentText !== undefined ? state.parentText : (state.parentName || state.billingClientText || "")).trim()
        var clientText = String(state.clientText !== undefined ? state.clientText : (state.clientName || state.selectedClientName || "")).trim()
        if (rec) {
            matterId = String(rec.matterId || matterId || "")
            matterText = root.matterDisplayLabel(rec)
            clientText = String(rec.clientName || clientText || "")
            parentText = String(rec.parentName || parentText || "")
            root.selectedClientId = String(rec.clientId || root.selectedClientId || "")
            root.selectedParentId = String(rec.parentId || root.selectedParentId || "")
        }

        var rateText = String(state.rateText !== undefined ? state.rateText : "0.00")
        var billText = String(state.billText !== undefined ? state.billText : "100.00")
        var dateText = String(state.dateText !== undefined ? state.dateText : Qt.formatDate(new Date(), "yyyy-MM-dd"))

        root.beginMatter360QuickActionLock(clientText, matterText)
        root.selectedMatterId = matterId

        try { if (bucketLookupDebounce) bucketLookupDebounce.stop() } catch (e0) {}
        docketTimer.stop()
        root.isRunning = false
        root.activeSegmentStartedAtMs = 0
        root.activeSegmentBaseSeconds = 0
        releaseTimerLock()

        root.aggregateLoadInProgress = false
        root.elapsedSeconds = 0
        root.lastPersistedSeconds = 0
        root.lastSavedEntryId = ""
        root.persistedBucketKey = ""
        root.docketStatusText = "Draft"
        root.timerLockNotice = ""
        root.timerLockHolder = ({})

        var wasHydrating = root._hydrating
        root._hydrating = true
        try {
            root.activeSubwindowId = "B01"
            ensureActiveSubwindow()
            if (dateInput) dateInput.text = dateText
            root.setComboTextStrict(parentCombo, parentText.length > 0 ? parentText : "(none)")
            root.setComboTextStrict(clientCombo, clientText)
            root.updateCascadingDropdowns("client")
            root.setComboTextStrict(matterCombo, matterText)
            root.setComboTextStrict(taskCombo, String(state.taskText || ""))
            if (descInput) descInput.text = String(state.descriptionText || "")
            if (timeInput) timeInput.text = "0.00"
            if (rateInput) rateInput.text = rateText
            if (billInput) billInput.text = billText
            syncTimeFieldFromElapsed()
            calculateFees()
        } finally {
            root._hydrating = wasHydrating
        }

        root.dirty = true
        Qt.callLater(function() {
            if (!root.matter360QuickActionActiveNow()) return
            var restoreHydrating = root._hydrating
            root._hydrating = true
            try {
                root.setComboTextStrict(parentCombo, parentText.length > 0 ? parentText : "(none)")
                root.setComboTextStrict(clientCombo, clientText)
                root.updateCascadingDropdowns("client")
                root.setComboTextStrict(matterCombo, matterText)
                root.setComboTextStrict(taskCombo, String(state.taskText || ""))
                if (dateInput) dateInput.text = dateText
                if (timeInput) timeInput.text = "0.00"
                if (rateInput) rateInput.text = rateText
                if (billInput) billInput.text = billText
                root.selectedMatterId = matterId
                root.elapsedSeconds = 0
                root.lastPersistedSeconds = 0
                root.lastSavedEntryId = ""
                root.persistedBucketKey = ""
                root.docketStatusText = "Draft"
                root.activeSegmentBaseSeconds = 0
                syncTimeFieldFromElapsed()
                calculateFees()
            } finally {
                root._hydrating = restoreHydrating
            }
            root.dirty = true
        })
        return true
    }

    function openDocketActivityReportForMatterDay() {
        var workDate = String(dateInput ? dateInput.text : "").trim()
        if (workDate.length <= 0) workDate = Qt.formatDate(new Date(), "yyyy-MM-dd")
        var matterId = root.currentMatterId()
        var matterLabel = String(matterCombo ? matterCombo.editText : "").trim()
        var clientLabel = String(clientCombo ? clientCombo.editText : "").trim()
        if (matterId.length <= 0 && matterLabel.length <= 0) {
            root.showSaveFeedback("Select a matter before opening the activity report.", true)
            return
        }
        if (root.isRunning) {
            root.accrueRunningSegmentToRawSeconds()
            docketTimer.stop()
            root.isRunning = false
            root.activeSegmentStartedAtMs = 0
            requestSaveToDatabaseIfNeeded("pause-open-activity-report", { "forceReplaceRawSeconds": true })
            releaseTimerLock()
        } else if (root.dirty) {
            requestSaveToDatabaseIfNeeded("open-activity-report", { "forceReplaceRawSeconds": true })
        }
        var reportState = {
            "fromDateText": workDate,
            "toDateText": workDate,
            "statusModeText": "All (Except Merged)",
            "queryText": "",
            "clientFilterText": clientLabel.length > 0 ? clientLabel : "All Clients",
            "matterFilterText": matterLabel.length > 0 ? matterLabel : "All Matters",
            "matterIdFilterText": matterId,
            "currentPreset": "today",
            "sortKey": "date",
            "sortAscending": false
        }
        root.pendingDocketReportState = reportState
        root.activeSubwindowId = "B04"
        root.ensureActiveSubwindow()
        requestDocketReportPanelLoad("openDocketActivityReportForMatterDay", true)
        if (docketActivityReportPanel && docketActivityReportPanel.applyState) {
            docketActivityReportPanel.applyState(reportState, true)
            root.pendingDocketReportState = null
        }
    }

    function currentBucketKey() {
        var dateText = String(dateInput ? dateInput.text : "").trim().toLowerCase()
        var matterId = String(root.currentMatterId ? root.currentMatterId() : "").trim().toLowerCase()
        if (matterId.length > 0) return dateText + "|matterid|" + matterId
        var clientText = String(clientCombo ? clientCombo.editText : "").trim().toLowerCase()
        var matterText = String(matterCombo ? matterCombo.editText : "").trim().toLowerCase()
        return dateText + "|" + clientText + "|" + matterText
    }

    function todayIsoLocal() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function handleBucketContextChanged() {
        if (_hydrating || !root.timerMayRefreshBucket()) return
        scheduleBucketRefresh()
    }

    function scheduleBucketRefresh() {
        if (_hydrating || !root.timerMayRefreshBucket()) return
        bucketLookupDebounce.restart()
    }

    function loadAggregateForCurrentBucket() {
        if (root.timerProtectedMode || (root.timerIsRunningNow && root.timerIsRunningNow())) {
            return
        }
        if (root.cspmTimerWatchdogActive || root.isRunning || Number(root.activeSegmentStartedAtMs || 0) > 0) {
            return
        }
        if (root.timerIsActivelyRunning && root.timerIsActivelyRunning()) {
            return
        }
        // CHATGPT-SAFE-TIMER-GUARD
        var __cspmActiveStart = Number(root.activeSegmentStartedAtMs || 0)
        if (root.isRunning || __cspmActiveStart > 0) {
            return
        }

        if (_hydrating || root.isRunning || aggregateLoadInProgress || root.matter360QuickActionActiveNow() || root.lastSavedEntryId) return
        if (!startupAllowsHeavyWorkNow("loadAggregateForCurrentBucket")) {
            scheduleBucketRefresh()
            return
        }
        var dateText = String(dateInput ? dateInput.text : "").trim()
        var clientText = String(clientCombo ? clientCombo.editText : "").trim()
        var matterText = String(matterCombo ? matterCombo.editText : "").trim()
        var matterId = String(root.currentMatterId ? root.currentMatterId() : "").trim()
        var key = currentBucketKey()
        if (dateText.length <= 0 || clientText.length <= 0) {
            setElapsedSecondsSafe(0)
            lastPersistedSeconds = 0
            lastSavedEntryId = ""
            docketStatusText = "Draft"
            persistedBucketKey = key
            return
        }
        var backend = (typeof docketApp !== "undefined") ? docketApp : ((appRef && appRef.docketing) ? appRef.docketing : null)
        if (!backend || !backend.loadTimeDocketAggregate) return
        aggregateLoadInProgress = true
        root._aggregateRequestKey = key
        backend.loadTimeDocketAggregate({
            "dateText": dateText,
            "clientText": clientText,
            "matterText": matterText,
            "matterId": matterId,
            "allowClientOnlyDraft": matterText.length <= 0 ? 1 : 0,
            "_bucketKey": key
        })
    }

    function headerSummaryText() {
        if (timerLockNotice.length > 0) {
            return timerLockNotice
        }
        if (activeIsTrademarkEntry()) {
            return "Simple trademark filing form"
        }
        if (activeIsTrademarkDirectory()) {
            return "Search trademarks and open records for edit"
        }
        if (activeIsLiveDocket()) {
            return "Integrated docket capture with live timer and exact-save tracking"
        }
        if (activeIsFeeDocket()) {
            return "Create a matter-linked fee directly in invoiceable WIP"
        }
        if (activeIsBulkDocketMove()) {
            return "Review and move selected unbilled time and fee dockets to another matter"
        }
        if (activeIsTimerConsole()) {
            return "Central timer controls, checkpoint saves, and lock handoff management"
        }
        if (activeIsDocketReport()) {
            return "Docket activity report with date range, No Matter grouping, and CSV export"
        }
        if (activeIsDeadlineCalendar()) {
            return "Create, edit, snooze, escalate, and delete deadline entries"
        }
        if (activeIsDeadlineEditor()) {
            return "Deadline entry editor for creating and maintaining deadline records"
        }
        return "Pathway placeholder for " + String(currentNavNode().title || "selected sub-window")
    }

    function timerLockHolderDisplayText() {
        var holder = root.timerLockHolder || ({})
        return String(holder.descriptor || holder.ownerLabel || "none")
    }

    function unsavedTimerSeconds() {
        var currentSeconds = Math.max(0, Math.floor(root.elapsedSeconds || 0))
        var persistedSeconds = Math.max(0, Math.floor(root.lastPersistedSeconds || 0))
        return Math.max(0, currentSeconds - persistedSeconds)
    }

    function formatHoursRounded(totalSeconds) {
        var sec = Math.max(0, Math.floor(totalSeconds || 0))
        if (sec <= 0) return "0.0"
        return (Math.ceil(((sec / 3600.0) * 10.0) - 1e-9) / 10.0).toFixed(1)
    }

    function quickAdjustTimerSeconds(deltaSeconds) {
        if (root.isRunning || root.isBucketLocked()) return
        var delta = parseInt(deltaSeconds)
        if (!isFinite(delta)) return
        var nextSeconds = Math.max(0, Math.floor(root.elapsedSeconds || 0) + delta)
        root.setElapsedSecondsSafe(nextSeconds)
        if (!root._hydrating) root.dirty = true
    }

    function restorePersistedTimerSeconds() {
        if (root.isRunning || root.isBucketLocked()) return
        var baseline = Math.max(0, Math.floor(root.lastPersistedSeconds || 0))
        root.setElapsedSecondsSafe(baseline)
        if (!root._hydrating) root.dirty = false
    }

    function resetTimerToZero() {
        if (root.isBucketLocked()) return
        if (root.isRunning) {
            docketTimer.stop()
            root.isRunning = false
            root.activeSegmentStartedAtMs = 0
            releaseTimerLock()
        }
        root.setElapsedSecondsSafe(0)
        root.lastPersistedSeconds = 0
        root.lastSavedEntryId = ""
        root.persistedBucketKey = ""
        root.docketStatusText = "Draft"
        if (!root._hydrating) root.dirty = root.formHasContent()
        if (!root.formHasContent()) root.timerLockNotice = ""
    }

    function openTimerEditPopup() {
        if (root.isBucketLocked()) return
        timerEditPopup.hasError = false
        var localX = Math.round((root.width - timerEditPopup.width) * 0.5)
        var localY = Math.round((root.height - timerEditPopup.height) * 0.5)
        var hostWindow = root.Window.window ? root.Window.window : root.windowRef
        if (hostWindow && hostWindow.screen && hostWindow.screen.availableGeometry) {
            var avail = hostWindow.screen.availableGeometry
            var origin = root.mapToGlobal(0, 0)
            var globalX = origin.x + localX
            var globalY = origin.y + localY
            var minX = Math.round(avail.x)
            var minY = Math.round(avail.y)
            var maxX = Math.round(avail.x + avail.width - timerEditPopup.width)
            var maxY = Math.round(avail.y + avail.height - timerEditPopup.height)
            if (maxX < minX) maxX = minX
            if (maxY < minY) maxY = minY
            globalX = Math.max(minX, Math.min(maxX, globalX))
            globalY = Math.max(minY, Math.min(maxY, globalY))
            localX = Math.round(globalX - origin.x)
            localY = Math.round(globalY - origin.y)
        }
        timerEditPopup.x = localX
        timerEditPopup.y = localY
        timerEditPopup.open()
    }

    function openTimeEntrySubwindow() {
        _hydrating = true
        root.activeSubwindowId = "B01"
        root.ensureActiveSubwindow()
        Qt.callLater(function() { _hydrating = false })
        if (!root.dirty) root.scheduleBucketRefresh()
    }

    function openDocketReportSubwindow() {
        root.activeSubwindowId = "B04"
        root.ensureActiveSubwindow()
        requestDocketReportPanelLoad("openDocketReportSubwindow", true)
    }

    function openDocketReportWindowFromState(reportState) {
        root.activeSubwindowId = "B04"
        root.ensureActiveSubwindow()
        root.pendingDocketReportState = reportState || root.pendingDocketReportState
        root.docketReportPanelPendingOpenReportWindow = true
        requestDocketReportPanelLoad("openDocketReportWindowFromState", true)
        if (docketActivityReportPanel && docketActivityReportPanel.openReportWindow) {
            if (reportState && docketActivityReportPanel.applyState) {
                docketActivityReportPanel.applyState(reportState, false)
            }
            root.pendingDocketReportState = null
            docketActivityReportPanel.openReportWindow(true)
        }
    }

    function showSaveFeedback(message, isError) {
        var text = String(message || "").trim()
        root.saveFeedbackText = text
        root.saveFeedbackIsError = !!isError
        if (text.length > 0) {
            saveFeedbackTimer.restart()
        } else {
            saveFeedbackTimer.stop()
        }
    }

    function refreshDocketReportAfterSave() {
        var savedDateText = String(dateInput ? (dateInput.text || "") : "").trim()
        if (savedDateText.length <= 0) {
            savedDateText = Qt.formatDate(new Date(), "yyyy-MM-dd")
        }
        var nextState = {
            "fromDateText": savedDateText,
            "toDateText": savedDateText,
            "statusModeText": "all_except_merged",
            "queryText": "",
            "clientFilterText": "All Clients",
            "matterFilterText": "All Matters",
            "currentPreset": "today"
        }
        root.pendingDocketReportState = nextState
        if (docketActivityReportPanel && docketActivityReportPanel.applyState) {
            docketActivityReportPanel.applyState(nextState, false)
            root.pendingDocketReportState = null
        }
        if (docketActivityReportPanel) {
            docketActivityReportPanel._loadedOnce = false
        }
        requestDocketReportPanelLoad("refreshDocketReportAfterSave", true)
    }

    function runTimerConsoleCheckpoint(statusText) {
        if (root.isBucketLocked()) {
            root.timerLockNotice = "This docket is billed and locked."
            return { "ok": false, "message": root.timerLockNotice }
        }
        var opts = {}
        if (statusText !== undefined && statusText !== null && String(statusText).trim().length > 0) {
            opts.statusText = String(statusText).trim()
        }
        var result = requestSaveToDatabaseIfNeeded("timer-console-save", opts)
        if (result && result.ok && result.verifiedExact) {
            root.timerLockNotice = "Checkpoint saved (" + root.formatHoursRounded(root.elapsedSeconds) + " hrs)."
        } else if (result && result.message) {
            root.timerLockNotice = String(result.message)
        }
        return result
    }

    function buildTimerLockDescriptor() {
        var clientText = String(clientCombo ? clientCombo.editText : "").trim()
        var matterText = String(matterCombo ? matterCombo.editText : "").trim()
        var suffix = ""
        if (clientText.length > 0 || matterText.length > 0) {
            suffix = " (" + (clientText.length > 0 ? clientText : "No Client")
                + " / " + (matterText.length > 0 ? matterText : "No Matter") + ")"
        }
        return "Time Docket Entry" + suffix
    }

    function ensureTimerOwnerId() {
        if (timerOwnerId.length > 0) return
        timerOwnerId = "TDV_" + String(Date.now()) + "_" + String(Math.floor(Math.random() * 1000000))
    }

    function acquireTimerLock(showPrompt, forceTakeover) {
        if (showPrompt === undefined) showPrompt = true
        if (forceTakeover === undefined) forceTakeover = false
        ensureTimerOwnerId()
        if (!appRef || !appRef.acquireGlobalTimerLock) return true
        var result = {}
        try {
            result = appRef.acquireGlobalTimerLock({
                "ownerId": timerOwnerId,
                "ownerLabel": root.detachedWindow ? "Detached Docket" : "Main Docket",
                "descriptor": buildTimerLockDescriptor(),
                "tileIndex": root.tileIndex,
                "laneKey": "docketing_deadlines",
                "forceTakeover": forceTakeover ? 1 : 0
            })
        } catch (e0) {
            timerLockNotice = "Timer lock error. Try again."
            return false
        }
        if (result && result.ok && result.granted) {
            timerLockNotice = ""
            timerLockHolder = ({})
            return true
        }
        var holder = (result && result.holder) ? result.holder : ({})
        timerLockHolder = holder
        var holderDescriptor = String(holder.descriptor || holder.ownerLabel || "another window")
        timerLockNotice = "Timer already running in " + holderDescriptor + "."
        if (showPrompt && timerLockPopup && !timerLockPopup.visible) {
            timerLockPopup.open()
        }
        return false
    }

    function releaseTimerLock() {
        if (timerOwnerId.length <= 0) return
        if (!appRef || !appRef.releaseGlobalTimerLock) return
        try {
            appRef.releaseGlobalTimerLock({ "ownerId": timerOwnerId })
        } catch (e0) {
        }
    }

    function startTimerAfterLock() {
        if (root.isBucketLocked()) return false

        root.timerBeginProtectedMode()

        if (normalizedDocketStatus(root.docketStatusText) === "Ready for Billing") {
            root.docketStatusText = "Draft"
        }

        var base = Math.max(
            0,
            Math.floor(Number(root.elapsedSeconds || 0)),
            Math.floor(Number(root.pausedRawSeconds || 0)),
            Math.floor(Number(root.activeSegmentBaseSeconds || 0))
        )

        root.timerLockNotice = ""
        root.activeSegmentBaseSeconds = base
        root.pausedRawSeconds = base
        root.activeSegmentStartedAtMs = Date.now()
        root.isRunning = true

        // Display exactly the base at Start; subsequent ticks add current segment.
        root.timerApplyRawSeconds(base)

        docketTimer.restart()
        return true
    }

    function stopTimerFromRemoteTakeover(holder) {
        if (!root.isRunning) return
        docketTimer.stop()
        root.isRunning = false
        root.activeSegmentStartedAtMs = 0
        var h = holder || ({})
        root.timerLockHolder = h
        var holderDescriptor = String(h.descriptor || h.ownerLabel || "another window")
        root.timerLockNotice = "Timer switched to " + holderDescriptor + "."
        var takeoverStamp = Qt.formatDateTime(new Date(), "yyyy-MM-dd HH:mm:ss")
        var takeoverOwnerId = String(h.ownerId || "")
        var auditText = "[LOCK SWITCH @ " + takeoverStamp + "] Taken over by "
            + holderDescriptor + (takeoverOwnerId.length > 0 ? " (" + takeoverOwnerId + ")" : "")
        if (root.autoPostOnStop) {
            requestSaveToDatabaseIfNeeded("auto-stop-lock-takeover", {
                "skipMatterPrompt": true,
                "allowClientOnlyDraft": true,
                "lockAudit": auditText
            })
        }
    }

    function verifyGlobalTimerLockOwner() {
        if (!root.isRunning) return
        if (!appRef || !appRef.getGlobalTimerLock) return
        var result = {}
        try {
            result = appRef.getGlobalTimerLock()
        } catch (e0) {
            return
        }
        if (!result || !result.ok) return
        if (!result.active) {
            // Best-effort self-heal if lock state was cleared.
            acquireTimerLock(false, false)
            return
        }
        var holder = result.holder ? result.holder : ({})
        var holderId = String(holder.ownerId || "")
        if (holderId.length <= 0) return
        if (holderId === root.timerOwnerId) return
        stopTimerFromRemoteTakeover(holder)
    }

    function takeOverTimerHere() {
        if (root.isBucketLocked()) {
            timerLockPopup.close()
            return
        }
        if (!acquireTimerLock(false, true)) {
            return
        }
        timerLockPopup.close()
        startTimerAfterLock()
    }

    function loadAggregateForBucket(dateText, clientText, matterText) {
        if (!appRef || !appRef.getTimeDocketAggregate) return ({ "ok": false, "exists": false })
        var result = {}
        try {
            result = appRef.getTimeDocketAggregate({
                "dateText": String(dateText || ""),
                "clientText": String(clientText || ""),
                "matterText": String(matterText || ""),
                "allowClientOnlyDraft": String(matterText || "").trim().length <= 0 ? 1 : 0
            })
        } catch (e0) {
            result = { "ok": false, "exists": false, "message": String(e0) }
        }
        return result || ({ "ok": false, "exists": false })
    }

    function handleMidnightSplitIfNeeded() {
        if (!root.isRunning) return
        var currentBucketDate = String(dateInput.text || "").trim()
        var localToday = todayIsoLocal()
        if (currentBucketDate.length <= 0) {
            dateInput.text = localToday
            return
        }
        if (currentBucketDate === localToday) return

        var nowMs = Date.now()
        var localNow = new Date()
        var todayStartMs = new Date(
            localNow.getFullYear(),
            localNow.getMonth(),
            localNow.getDate(),
            0, 0, 0, 0
        ).getTime()

        var currentTotalSeconds = Math.max(0, Math.floor(root.elapsedSeconds || 0))
        var persistedSeconds = Math.max(0, Math.floor(root.lastPersistedSeconds || 0))
        var unsavedSeconds = Math.max(0, currentTotalSeconds - persistedSeconds)
        var segStartMs = (root.activeSegmentStartedAtMs > 0) ? root.activeSegmentStartedAtMs : nowMs
        var beforeBoundarySeconds = Math.floor((todayStartMs - segStartMs) / 1000.0)
        if (!isFinite(beforeBoundarySeconds)) beforeBoundarySeconds = unsavedSeconds
        beforeBoundarySeconds = Math.max(0, Math.min(unsavedSeconds, beforeBoundarySeconds))
        var afterBoundarySeconds = Math.max(0, unsavedSeconds - beforeBoundarySeconds)
        var oldDayTotalSeconds = persistedSeconds + beforeBoundarySeconds

        var oldSaveResult = requestSaveToDatabaseIfNeeded("auto-midnight-split-old-day", {
            "skipMatterPrompt": true,
            "allowClientOnlyDraft": true,
            "forceReplaceRawSeconds": true,
            "overrideDateText": currentBucketDate,
            "overrideRawSeconds": oldDayTotalSeconds
        })
        if (!(oldSaveResult && oldSaveResult.ok && oldSaveResult.verifiedExact)) {
            root.timerLockNotice = "Midnight split failed to save prior day. Please save manually."
            return
        }

        var clientText = String(clientCombo.editText || "")
        var matterText = String(matterCombo.editText || "")
        var aggregate = loadAggregateForBucket(localToday, clientText, matterText)
        var existingTodaySeconds = 0
        var existingTodayStatus = "Draft"
        if (aggregate && aggregate.ok && aggregate.exists) {
            var aggSec = parseInt(aggregate.aggregateRawSeconds)
            if (isFinite(aggSec) && aggSec >= 0) {
                existingTodaySeconds = Math.floor(aggSec)
            }
            existingTodayStatus = normalizedDocketStatus(aggregate.status)
        }

        var carriedTodaySeconds = Math.max(0, existingTodaySeconds + afterBoundarySeconds)
        dateInput.text = localToday
        root.docketStatusText = existingTodayStatus
        root.elapsedSeconds = carriedTodaySeconds
        syncTimeFieldFromElapsed()
        root.lastPersistedSeconds = Math.max(0, existingTodaySeconds)
        root.persistedBucketKey = currentBucketKey()
        root.dirty = true
        root.activeSegmentStartedAtMs = nowMs - (afterBoundarySeconds * 1000.0)
        if (root.activeSegmentStartedAtMs < 0 || !isFinite(root.activeSegmentStartedAtMs)) {
            root.activeSegmentStartedAtMs = nowMs
        }
    }

    function jumpToLockHolder() {
        var holder = root.timerLockHolder || ({})
        var holderTile = parseInt(holder.tileIndex)
        var targetTile = 1
        if (isFinite(holderTile) && holderTile >= 0) {
            targetTile = holderTile
        }
        root.moduleJumpRequested(targetTile, { "_targetTileState": { "focusNodeId": "B01" } })
    }

    onNavItemsChanged: ensureActiveSubwindow()

    Rectangle {
        anchors.fill: parent
        color: root.isProMode ? root.proBackground : root._bg
        z: -3
    }

    Image {
        id: docketBackdrop
        anchors.fill: parent
        source: root.themeBackgroundSource()
        fillMode: Image.PreserveAspectCrop
        smooth: true
        asynchronous: false
        retainWhileLoading: true
        cache: true
        mipmap: true
        visible: !root.isProMode
        opacity: root.lightTheme ? 0.50 : 0.72
        z: -2
        layer.enabled: true
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.lightTheme ? 0.02 : 0.06
            blurMax: 44
            saturation: root.lightTheme ? 0.12 : 0.30
            brightness: root.lightTheme ? 0.05 : -0.02
            colorizationColor: root._accent
            colorization: root.backgroundColorizationStrength()
            autoPaddingEnabled: false
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.isProMode
            ? "transparent"
            : Qt.rgba(root._panelBase.r, root._panelBase.g, root._panelBase.b, root.lightTheme ? 0.22 : 0.14)
        z: -1
    }

    // click shield
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        // FIX: Explicitly declare mouse parameter
        onPressed: function(mouse) {
            if (root.windowRef && root.windowRef.requestActivate) {
                try {
                    if ((root.windowRef.flags & Qt.WindowDoesNotAcceptFocus) !== Qt.WindowDoesNotAcceptFocus) {
                        root.windowRef.requestActivate()
                    }
                } catch (e) { }
            }
            mouse.accepted = true
        }
        onClicked: function(mouse) { mouse.accepted = true }
        z: 0
    }

    function formatTimer(totalSeconds) {
        var tsec = Math.max(0, Math.floor(totalSeconds || 0))
        var h = Math.floor(tsec / 3600)
        var m = Math.floor((tsec % 3600) / 60)
        var s = tsec % 60
        return (h < 10 ? "0" + h : "" + h) + ":" + (m < 10 ? "0" + m : "" + m) + ":" + (s < 10 ? "0" + s : "" + s)
    }

    function descriptionMinHeightPx() {
        return root.ratioPxH(root.scaleRatios.descPrefHeightPct, 88)
    }

    function descriptionMaxHeightPx() {
        var minH = descriptionMinHeightPx()
        var hardCap = root.ratioPxH(root.scaleRatios.descMaxHeightPct, 220)
        // Reserve room for rate/bill/fees + feedback + footer action row.
        var reserved = (root.fieldHeightPx * 3) + (root.controlGapPx * 5) + root.ratioPxH(0.12, 110)
        var available = Math.max(minH, Math.round(root.height - reserved))
        return Math.max(minH, Math.min(hardCap, available))
    }

    function descriptionTargetHeightPx() {
        var minH = descriptionMinHeightPx()
        var maxH = descriptionMaxHeightPx()
        var textValue = String((descInput && descInput.text !== undefined) ? descInput.text : "")
        // Keep this independent of the scroll area's live layout geometry to avoid
        // feedback loops while GridLayout is solving dimensions.
        var viewportW = Math.max(260, Math.round(root.moduleRefWidth() * 0.92))
        var sidePad = root.ratioPx(root.scaleRatios.descPadPct, 4) * 3
        var textWidth = Math.max(120, Math.round(viewportW - sidePad))
        var fontPx = root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
        var linePx = Math.max(fontPx + root.ratioPx(0.0032, 4), root.ratioPx(0.017, 16))
        var avgCharPx = Math.max(6, Math.round(fontPx * 0.56))
        var charsPerLine = Math.max(12, Math.floor(textWidth / avgCharPx))
        var lines = 0
        var parts = textValue.split("\n")
        for (var i = 0; i < parts.length; i++) {
            var segLen = String(parts[i] || "").length
            lines += Math.max(1, Math.ceil(segLen / charsPerLine))
        }
        lines = Math.max(3, lines)
        var verticalPad = root.ratioPx(root.scaleRatios.descPadPct, 4) * 2
        var desired = Math.round((lines * linePx) + verticalPad + root.ratioPx(0.007, 6))
        if (!isFinite(desired) || desired <= 0) desired = minH
        return Math.max(minH, Math.min(maxH, desired))
    }

    // CHATGPT-TIMER-WATCHDOG
    function cspmUpdateElapsedFromClock() {
        var startMs = Number(root.activeSegmentStartedAtMs || 0)
        if (startMs <= 0) return 0
        var segmentSeconds = Math.max(0, Math.floor((Date.now() - startMs) / 1000))
        root.elapsedSeconds = Math.max(0, Math.floor(Number(root.activeSegmentBaseSeconds || 0))) + segmentSeconds
        root.pausedRawSeconds = root.elapsedSeconds
        root.syncTimeFieldFromElapsed()
        return segmentSeconds
    }

    function timerBucketKey() {
        try {
            if (root.currentBucketKey) return String(root.currentBucketKey() || "")
        } catch (e0) {
        }
        return ""
    }

    function timerIsRunningNow() {
        return !!root.isRunning && Number(root.activeSegmentStartedAtMs || 0) > 0
    }

    function timerRawSecondsNow() {
        if (root.timerIsRunningNow()) {
            var startMs = Number(root.activeSegmentStartedAtMs || 0)

            // One fixed base captured when Start is pressed.
            // Never update this base during a running tick.
            var base = Math.max(0, Math.floor(Number(root.activeSegmentBaseSeconds || 0)))
            var segment = Math.max(0, Math.floor((Date.now() - startMs) / 1000))
            return base + segment
        }

        return Math.max(
            0,
            Math.floor(Number(root.elapsedSeconds || 0)),
            Math.floor(Number(root.pausedRawSeconds || 0)),
            Math.floor(Number(root.activeSegmentBaseSeconds || 0))
        )
    }

    function timerApplyRawSeconds(rawSeconds) {
        var value = Math.max(0, Math.floor(Number(rawSeconds || 0)))

        root.timerInternalElapsedWrite = true
        root.elapsedSeconds = value

        if (!root.timerIsRunningNow()) {
            root.pausedRawSeconds = value
            root.activeSegmentBaseSeconds = value
        }

        root.syncTimeFieldFromElapsed()
        root.timerInternalElapsedWrite = false
        return value
    }

    function timerBeginProtectedMode() {
        root.timerProtectedMode = true
        root.timerDraftBucketKey = root.timerBucketKey()

        try {
            if (bucketLookupDebounce) bucketLookupDebounce.stop()
        } catch (e0) {
        }
    }

    function timerMayRefreshBucket() {
        if (root.timerIsRunningNow()) return false
        if (root.timerProtectedMode) return false
        if (root.dirty && root.pausedRawSeconds > 0) return false
        return true
    }

    function cspmTimerIsActive() {
        return root.timerIsRunningNow()
    }

    function cspmCurrentRawSeconds() {
        return root.timerApplyRawSeconds(root.timerRawSecondsNow())
    }

    function matter360QuickActionActiveNow() {
        return root.timerProtectedMode || root.timerIsRunningNow()
    }

    function beginMatter360QuickActionLock(clientText, matterText) {
        if (root.timerProtectedMode || root.timerIsRunningNow()) return
    }

    function endMatter360QuickActionLock() {
    }

    function resetDocketTimerToZero() {
        // User-intentional timer reset. This does NOT save the docket.
        // It only clears the in-memory timer state and marks the form dirty.

        try {
            if (docketTimer) docketTimer.stop()
        } catch (e0) {
        }

        try {
            if (bucketLookupDebounce) bucketLookupDebounce.stop()
        } catch (e1) {
        }

        try {
            releaseTimerLock()
        } catch (e2) {
        }

        root.timerInternalElapsedWrite = true

        root.isRunning = false
        root.activeSegmentStartedAtMs = 0
        root.activeSegmentBaseSeconds = 0
        root.pausedRawSeconds = 0
        root.elapsedSeconds = 0

        // Keep protected mode on for the current bucket so a delayed aggregate
        // refresh does not immediately repaint old saved time back into view.
        root.timerProtectedMode = true

        try {
            root.timerDraftBucketKey = root.timerBucketKey ? root.timerBucketKey() : ""
        } catch (e3) {
            root.timerDraftBucketKey = ""
        }

        root.syncTimeFieldFromElapsed()

        try {
            calculateFees()
        } catch (e4) {
        }

        root.dirty = true
        root.timerInternalElapsedWrite = false

        return true
    }

    function cspmParseEditTimerSeconds(textValue) {
        var raw = String(textValue || "").trim()
        if (raw.length <= 0) return 0

        var parts = raw.split(":")
        var h = 0
        var m = 0
        var s = 0

        if (parts.length === 3) {
            h = parseInt(parts[0])
            m = parseInt(parts[1])
            s = parseInt(parts[2])
        } else if (parts.length === 2) {
            m = parseInt(parts[0])
            s = parseInt(parts[1])
        } else {
            s = parseInt(parts[0])
        }

        if (!isFinite(h)) h = 0
        if (!isFinite(m)) m = 0
        if (!isFinite(s)) s = 0

        return Math.max(0, Math.floor(h * 3600 + m * 60 + s))
    }

    function cspmFormatEditTimerSeconds(totalSeconds) {
        var sec = Math.max(0, Math.floor(Number(totalSeconds || 0)))
        var h = Math.floor(sec / 3600)
        var m = Math.floor((sec % 3600) / 60)
        var s = sec % 60

        function pad(n) {
            return n < 10 ? "0" + n : "" + n
        }

        return pad(h) + ":" + pad(m) + ":" + pad(s)
    }

    function cspmFindEditTimerTextItem(obj) {
        if (!obj) return null

        try {
            if (obj.visible === false) {
                // Keep looking through invisible wrappers only if this is the known popup.
                if (obj !== timerEditPopup) return null
            }
        } catch (e0) {
        }

        try {
            if (obj.text !== undefined) {
                var t = String(obj.text || "")
                if (/^\s*\d{1,3}:\d{2}:\d{2}\s*$/.test(t)) {
                    return obj
                }
            }
        } catch (e1) {
        }

        var containers = []

        try {
            if (obj.contentItem) containers.push(obj.contentItem)
        } catch (e2) {
        }

        try {
            if (obj.children) {
                for (var i = 0; i < obj.children.length; ++i) containers.push(obj.children[i])
            }
        } catch (e3) {
        }

        try {
            if (obj.contentChildren) {
                for (var j = 0; j < obj.contentChildren.length; ++j) containers.push(obj.contentChildren[j])
            }
        } catch (e4) {
        }

        for (var k = 0; k < containers.length; ++k) {
            var found = root.cspmFindEditTimerTextItem(containers[k])
            if (found) return found
        }

        return null
    }

    function cspmResetEditTimerDraftOnly() {
        // Dialog-local only. The live timer changes only when Apply is clicked.
        var item = root.cspmFindBestEditTimerTextItem()

        if (item) {
            try {
                item.text = root.cspmFormatEditTimerSeconds(0)
                item.forceActiveFocus()
                if (item.selectAll) item.selectAll()
            } catch (e0) {
            }
        }

        return true
    }

    function cspmCloseEditTimerDialog() {
        // Close only the Edit Timer popup/container. Never touch parent windows.
        try {
            if (timerEditPopup.close) {
                timerEditPopup.close()
                return true
            }
        } catch (e0) {
        }

        try {
            timerEditPopup.visible = false
        } catch (e1) {
        }

        try {
            timerEditPopup.enabled = false
        } catch (e2) {
        }

        return true
    }

    function cspmApplyEditTimerDialog() {
        var value = 0
        var item = root.cspmFindBestEditTimerTextItem()

        try {
            if (item) {
                value = root.cspmParseEditTimerSeconds(root.cspmEditTimerItemText(item))
            }
        } catch (e0) {
            value = 0
        }

        value = Math.max(0, Math.floor(Number(value || 0)))

        try {
            if (docketTimer) docketTimer.stop()
        } catch (e1) {
        }

        try {
            releaseTimerLock()
        } catch (e2) {
        }

        root.isRunning = false
        root.activeSegmentStartedAtMs = 0
        root.activeSegmentBaseSeconds = value
        root.pausedRawSeconds = value
        root.elapsedSeconds = value

        try {
            if (root.timerProtectedMode !== undefined) root.timerProtectedMode = true
        } catch (e3) {
        }

        try {
            if (root.timerApplyRawSeconds) {
                root.timerApplyRawSeconds(value)
            } else {
                root.syncTimeFieldFromElapsed()
            }
        } catch (e4) {
            root.syncTimeFieldFromElapsed()
        }

        try {
            calculateFees()
        } catch (e5) {
        }

        root.dirty = true
        root.cspmCloseEditTimerDialog()
        return value
    }

    function cspmEditTimerItemText(obj) {
        if (!obj) return ""

        try {
            if (obj.text !== undefined) return String(obj.text || "")
        } catch (e0) {
        }

        try {
            if (obj.displayText !== undefined) return String(obj.displayText || "")
        } catch (e1) {
        }

        return ""
    }

    function cspmEditTimerItemScore(obj) {
        if (!obj) return -100000

        var raw = root.cspmEditTimerItemText(obj)
        var score = -100000

        if (/^\s*\d{1,3}:\d{2}:\d{2}\s*$/.test(raw)) {
            score = 100
        } else if (raw.indexOf(":") >= 0) {
            score = 30
        } else {
            return -100000
        }

        try {
            if (obj.activeFocus) score += 10000
        } catch (e0) {
        }

        try {
            if (obj.cursorPosition !== undefined) score += 500
        } catch (e1) {
        }

        try {
            if (obj.selectedText !== undefined) score += 250
        } catch (e2) {
        }

        try {
            if (obj.selectAll) score += 150
        } catch (e3) {
        }

        try {
            if (obj.readOnly === false) score += 250
        } catch (e4) {
        }

        try {
            if (obj.inputMethodHints !== undefined) score += 100
        } catch (e5) {
        }

        try {
            if (obj.enabled === false) score -= 200
        } catch (e6) {
        }

        try {
            if (obj.visible === false) score -= 200
        } catch (e7) {
        }

        return score
    }

    function cspmFindBestEditTimerTextItem() {
        var best = null
        var bestScore = -100000
        var visited = []

        function alreadySeen(o) {
            for (var i = 0; i < visited.length; ++i) {
                if (visited[i] === o) return true
            }
            return false
        }

        function visit(o, depth) {
            if (!o || depth > 14 || alreadySeen(o)) return
            visited.push(o)

            var score = root.cspmEditTimerItemScore(o)
            if (score > bestScore) {
                bestScore = score
                best = o
            }

            try {
                if (o.contentItem) visit(o.contentItem, depth + 1)
            } catch (e0) {
            }

            try {
                if (o.children) {
                    for (var i = 0; i < o.children.length; ++i) visit(o.children[i], depth + 1)
                }
            } catch (e1) {
            }

            try {
                if (o.contentChildren) {
                    for (var j = 0; j < o.contentChildren.length; ++j) visit(o.contentChildren[j], depth + 1)
                }
            } catch (e2) {
            }
        }

        try {
            visit(timerEditPopup, 0)
        } catch (e3) {
        }

        if (!best || bestScore < 0) {
            try {
                visit(root, 0)
            } catch (e4) {
            }
        }

        return best
    }

    function syncTimeFieldFromElapsed() {
        var hours = root.elapsedSeconds / 3600.0
        var rounded = Math.ceil(hours * 10) / 10
        timeInput.text = rounded.toFixed(1)
        calculateFees()
    }

    function setElapsedSecondsSafe(value) {
        var nextValue = Math.max(0, Math.floor(Number(value || 0)))

        if (root.timerProtectedMode && !root.timerInternalElapsedWrite) {
            // Automatic aggregate/state refreshes are not allowed to change the
            // active/paused draft timer. Only timerApplyRawSeconds may write it.
            return
        }

        if (root.timerIsRunningNow() && !root.timerInternalElapsedWrite) {
            return
        }

        if (!root.isRunning && root.dirty && root.pausedRawSeconds > 0 && nextValue === 0) {
            return
        }

        root.timerApplyRawSeconds(nextValue)
    }

    function parseHmsToSeconds(s) {
        var raw = String(s || "").trim()
        if (raw === "") return null
        var parts = raw.split(":")
        if (parts.length > 3) return null
        function toIntSafe(x) {
            var v = parseInt(String(x).trim(), 10)
            if (isNaN(v) || v < 0) return null
            return v
        }
        var h = 0
        var m = 0
        var sec = 0
        if (parts.length === 3) {
            h = toIntSafe(parts[0]); m = toIntSafe(parts[1]); sec = toIntSafe(parts[2])
        } else if (parts.length === 2) {
            m = toIntSafe(parts[0]); sec = toIntSafe(parts[1])
        } else {
            sec = toIntSafe(parts[0])
        }
        if (h === null || m === null || sec === null) return null
        if (m >= 60 || sec >= 60) return null
        return (h * 3600) + (m * 60) + sec
    }

    function parseTimeEntryInputToSeconds(rawInput) {
        var raw = String(rawInput || "").trim()
        if (raw.length <= 0) {
            return { "ok": true, "seconds": 0 }
        }

        var compact = raw.replace(",", ".")
        if (compact.indexOf(":") >= 0) {
            var parts = compact.split(":")
            if (parts.length !== 2 && parts.length !== 3) {
                return { "ok": false, "message": "Use decimal hours or HH:MM[:SS]." }
            }

            function parseWhole(token) {
                var t = String(token || "").trim()
                if (!/^\d+$/.test(t)) return null
                var v = parseInt(t, 10)
                if (!isFinite(v) || v < 0) return null
                return v
            }

            var hh = 0
            var mm = 0
            var ss = 0
            if (parts.length === 2) {
                // Time-entry field uses HH:MM when two groups are supplied.
                hh = parseWhole(parts[0])
                mm = parseWhole(parts[1])
            } else {
                hh = parseWhole(parts[0])
                mm = parseWhole(parts[1])
                ss = parseWhole(parts[2])
            }
            if (hh === null || mm === null || ss === null) {
                return { "ok": false, "message": "Time contains invalid characters." }
            }
            if (mm >= 60 || ss >= 60) {
                return { "ok": false, "message": "Minutes/seconds must be under 60." }
            }
            return { "ok": true, "seconds": (hh * 3600) + (mm * 60) + ss }
        }

        if (!/^([0-9]+(\.[0-9]+)?|\.[0-9]+)$/.test(compact)) {
            return { "ok": false, "message": "Use decimal hours (example: 0.6) or HH:MM[:SS]." }
        }
        var decHours = parseFloat(compact)
        if (!isFinite(decHours) || decHours < 0) {
            return { "ok": false, "message": "Time must be a positive number." }
        }
        return { "ok": true, "seconds": Math.floor(decHours * 3600.0) }
    }

    function showTimeFieldValidationPopup(messageText) {
        root.timeFieldValidationMessage = String(messageText || "Enter decimal hours or HH:MM[:SS].")
        if (!timeFieldValidationPopup) return
        if (timeFieldValidationPopup.centerToRoot) {
            timeFieldValidationPopup.centerToRoot()
        }
        if (!timeFieldValidationPopup.visible) {
            timeFieldValidationPopup.open()
        }
    }

    function commitManualTimeField(normalizeAfterCommit) {
        if (!timeInput) return true
        if (root._manualTimeCommitBusy) return true
        root._manualTimeCommitBusy = true
        var ok = true
        try {
        if (root.isRunning || root.isBucketLocked()) {
            if (normalizeAfterCommit) {
                var lockedHours = root.formatHoursRounded(root.elapsedSeconds)
                if (timeInput.text !== lockedHours) timeInput.text = lockedHours
            }
            return true
        }

        var parsed = root.parseTimeEntryInputToSeconds(timeInput.text)
        if (!parsed.ok) {
            if (!(timeFieldValidationPopup && timeFieldValidationPopup.visible)) {
                root.showTimeFieldValidationPopup(parsed.message)
            } else {
                root.timeFieldValidationMessage = String(parsed.message || "Use decimal hours or HH:MM[:SS].")
            }
            if (normalizeAfterCommit) {
                var normalizedHours = root.formatHoursRounded(root.elapsedSeconds)
                if (timeInput.text !== normalizedHours) timeInput.text = normalizedHours
            }
            ok = false
            return false
        }

        var changed = (parsed.seconds !== Math.floor(root.elapsedSeconds || 0))
        root.setElapsedSecondsSafe(parsed.seconds)
        if (changed && !root._hydrating) {
            root.dirty = true
        }
        return true
        } finally {
            root._manualTimeCommitBusy = false
        }
        return ok
    }

    function toggleTimer() {
        if (root.isBucketLocked()) {
            return
        }

        if (root.isRunning) {
            // Stop means PAUSE ONLY. No save here.
            var paused = root.timerRawSecondsNow()

            docketTimer.stop()

            root.activeSegmentStartedAtMs = 0
            root.isRunning = false
            root.timerApplyRawSeconds(paused)
            root.dirty = true

            // Keep protected mode on while paused/dirty.
            root.timerProtectedMode = true

            releaseTimerLock()
            return
        }

        if (!acquireTimerLock(true)) {
            return
        }

        startTimerAfterLock()
    }

    function feeCalculationHours() {
        // A manually typed value is the active source of truth for the live
        // preview.  The timer remains the fallback for timer-driven dockets.
        // This keeps Total Fees accurate before the user leaves the field or
        // saves the docket.
        if (timeInput) {
            var parsed = root.parseTimeEntryInputToSeconds(timeInput.text)
            if (parsed && parsed.ok) {
                return Math.max(0, Number(parsed.seconds || 0)) / 3600.0
            }
        }
        return Math.max(0, Math.floor(root.elapsedSeconds || 0)) / 3600.0
    }

    function calculateFees() {
        var hours = root.feeCalculationHours()
        var r = parseFloat(rateInput.text) || 0.0
        var b = parseFloat(billInput.text) || 0.0
        feesInput.text = "$" + (hours * r * (b / 100.0)).toFixed(2)
    }

    property bool _updatingDropdowns: false
    property bool timerInternalElapsedWrite: false
    property bool timerProtectedMode: false
    property double matter360QuickActionCompatUntilMs: 0
    property bool matter360QuickActionCompatActive: false
    property string timerDraftBucketKey: ""
    property int pausedRawSeconds: 0
    property bool saveAsDistinctDocket: false
    property string _aggregateRequestKey: ""
    property string _matter360LockedMatterText: ""
    property string _matter360LockedClientText: ""
    property double _matter360QuickActionLockUntilMs: 0
    property bool _matter360QuickActionActive: false
    property int activeSegmentBaseSeconds: 0
    property string selectedParentId: ""
    property string selectedClientId: ""
    property string selectedMatterId: ""

    function updateCascadingDropdowns(source) {
        if (root._updatingDropdowns) return
        root._updatingDropdowns = true

        if (!root._rawClientDirectory || !root._rawMatterDirectory) {
            root._updatingDropdowns = false
            return
        }
        var pSel = parentCombo.editText
        var cSel = clientCombo.editText
        var mSel = matterCombo.editText

        if (source === "matter" && mSel && mSel !== "") {
            var matchMatter = null
            var cleanMSel = mSel.replace(/ - $/, "").replace(/ - undefined$/, "").trim()
            for (var i = 0; i < root._rawMatterDirectory.length; i++) {
                var m = root._rawMatterDirectory[i]
                var mStr = String(m.matterNumber || "") + " - " + String(m.matterName || "")
                var mNum = String(m.matterNumber || "").trim()
                var mName = String(m.matterName || "").trim()
                var dName = String(m.displayName || "").trim()
                
                if (mStr === mSel || 
                    mName === mSel || mName === cleanMSel ||
                    mNum === mSel || mNum === cleanMSel || 
                    dName === mSel || dName === cleanMSel ||
                    (mNum !== "" && mSel.indexOf(mNum) === 0)) {
                    matchMatter = m
                    break
                }
            }
            if (matchMatter) {
                var cName = String(matchMatter.clientName || "")
                if (cName) {
                    clientCombo.editText = cName
                    cSel = cName
                    var pName = ""
                    for (var j = 0; j < root._rawClientDirectory.length; j++) {
                        var c = root._rawClientDirectory[j]
                        if (c.displayName === cName || c.clientName === cName) {
                            pName = String(c.parentClientName || "")
                            break
                        }
                    }
                    if (pName) {
                        parentCombo.editText = pName
                    } else {
                        parentCombo.editText = "(none)"
                    }
                    pSel = parentCombo.editText
                }
            }
        }
        if (source === "client" && cSel && cSel !== "" && cSel !== "(blank)") {
            var matchClient = null
            for (var k = 0; k < root._rawClientDirectory.length; k++) {
                var c2 = root._rawClientDirectory[k]
                if (c2.displayName === cSel || c2.clientName === cSel) {
                    matchClient = c2
                    break
                }
            }
            if (matchClient) {
                var pName2 = String(matchClient.parentClientName || "")
                if (pName2) {
                    parentCombo.editText = pName2
                    pSel = pName2
                } else {
                    parentCombo.editText = "(none)"
                    pSel = "(none)"
                }
            }
        }

        var parents = {"(blank)": true, "(none)": true}
        var filteredClients = ["(blank)"]
        var filteredMatters = []

        var pFilter = (pSel === "(blank)" || pSel === "") ? null : (pSel === "(none)" ? "" : pSel)
        
        for (var idxC = 0; idxC < root._rawClientDirectory.length; idxC++) {
            var rc = root._rawClientDirectory[idxC]
            var rpName = String(rc.parentClientName || "")
            if (rpName) parents[rpName] = true
            
            var rcName = String(rc.displayName || rc.clientName || "")
            if (!rcName) continue
            
            if (pFilter !== null) {
                if (rpName !== pFilter) continue
            }
            filteredClients.push(rcName)
        }

        var cFilter = (cSel === "(blank)" || cSel === "") ? null : cSel
        
        for (var idxM = 0; idxM < root._rawMatterDirectory.length; idxM++) {
            var rm = root._rawMatterDirectory[idxM]
            var rmcName = String(rm.clientName || "")
            if (cFilter !== null) {
                if (rmcName !== cFilter) continue
            } else if (pFilter !== null) {
                var rmParentName = String(rm.parentName || "")
                if (rmParentName !== pFilter) continue
            }
            
            var rmStr = String(rm.matterNumber || "") + " - " + String(rm.matterName || "")
            filteredMatters.push(rmStr)
        }

        var sortedParents = Object.keys(parents)
        sortedParents.sort(function(a, b) {
            if (a === "(blank)") return -1
            if (b === "(blank)") return 1
            if (a === "(none)") return -1
            if (b === "(none)") return 1
            return a.localeCompare(b)
        })
        parentCombo.fullModel = sortedParents
        clientCombo.fullModel = filteredClients.sort()
        matterCombo.fullModel = filteredMatters.sort()

        if (!root._hydrating && source !== "init") {
            root.dirty = true
            root.handleBucketContextChanged()
        }

        root._updatingDropdowns = false
    }

    function refreshLookupLists() {
        if (!startupAllowsHeavyWorkNow("refreshLookupLists")) {
            scheduleStartupHydration("refreshLookupLists")
            return
        }
        if (!appRef) return
        try {
            if (appRef.listClientDirectory) {
                var cDir = appRef.listClientDirectory()
                if (cDir) root._rawClientDirectory = cDir
            }
        } catch (e1) {}
        try {
            if (appRef.listMatterDirectory) {
                var mDir = appRef.listMatterDirectory()
                if (mDir) root._rawMatterDirectory = mDir
            }
        } catch (e2) {}
        
        root.updateCascadingDropdowns("init")
    }

    function buildPersistencePayload(options) {
        options = options || ({})

        var rawSeconds = root.timerRawSecondsNow()
        root.timerApplyRawSeconds(rawSeconds)

        var hours = rawSeconds / 3600.0

        var rate = parseFloat(rateInput.text)
        if (!isFinite(rate)) rate = 0.0

        var sharePct = parseFloat(billInput.text)
        if (!isFinite(sharePct)) sharePct = 100.0

        var payloadDateText = (options.overrideDateText !== undefined && options.overrideDateText !== null)
            ? String(options.overrideDateText)
            : dateInput.text

        return {
            "dateText": payloadDateText,
            "clientId": root.currentClientId(),
            "clientText": clientCombo.editText,
            "matterId": root.currentMatterId(),
            "matterText": matterCombo.editText,
            "parentText": parentCombo ? parentCombo.editText : "",
            "taskText": taskCombo.editText,
            "descriptionText": descInput.text,
            "lockAudit": String(options.lockAudit || ""),
            "timeText": root.formatHoursRounded(rawSeconds),
            "rateText": rateInput.text,
            "billText": billInput.text,
            "elapsedSeconds": rawSeconds,
            "hours": hours,
            "rate": rate,
            "sharePct": sharePct,
            "rawSeconds": rawSeconds,
            "rawSecondsMode": "replace",
            "distinctDocket": root.saveAsDistinctDocket ? 1 : 0,
            "status": String(options.statusText || root.docketStatusText || "Draft"),
            "allowClientOnlyDraft": options.allowClientOnlyDraft ? 1 : 0,
            "entryId": root.lastSavedEntryId
        }
    }

    function cloneOptions(source) {
        var out = ({})
        var src = source || ({})
        for (var key in src) {
            out[key] = src[key]
        }
        return out
    }

    function openMatterRequiredPrompt(reasonTag, options) {
        root.pendingSaveReason = String(reasonTag || "manual-save")
        root.pendingSaveOptions = cloneOptions(options)
        matterRequiredPopup.open()
    }

    function continuePendingSave(extraOptions) {
        var opts = cloneOptions(root.pendingSaveOptions)
        var extras = extraOptions || ({})
        for (var key in extras) {
            opts[key] = extras[key]
        }
        opts.skipMatterPrompt = true
        var reason = String(root.pendingSaveReason || "manual-save")
        root.pendingSaveReason = ""
        root.pendingSaveOptions = ({})
        return requestSaveToDatabaseIfNeeded(reason, opts)
    }

    function requestSaveToDatabaseIfNeeded(reasonTag, options) {
        options = options || ({})
        if (root.isBucketLocked() && !options.forceEditBilled) {
            var origTimeSecs = root.parseTimeEntryInputToSeconds(String(root.originalLoadedTime).trim()).seconds || 0
            var currTimeSecs = root.parseTimeEntryInputToSeconds(String(timeInput.text).trim()).seconds || 0
            var origRate = Number(String(root.originalLoadedRate).trim()) || 0.0
            var currRate = Number(String(rateInput.text).trim()) || 0.0

            var timeChanged = Math.abs(origTimeSecs - currTimeSecs) > 0
            var rateChanged = Math.abs(origRate - currRate) > 0.001
            var financialChanged = timeChanged || rateChanged
            
            if (!financialChanged) {
                // Administrative edit allowed
                options.forceEditBilled = true
                console.log("Administrative edit allowed on billed docket.")
            } else {
                var lockedResult = { "ok": false, "message": "This docket is billed. To change financial values (hours, rate), you must first unlink or reverse the invoice." }
                root.timerLockNotice = String(lockedResult.message)
                root.showSaveFeedback(lockedResult.message, true)
                return lockedResult
            }
        }
        if (!root.commitManualTimeField(true)) {
            var invalidTimeResult = { "ok": false, "message": "Invalid time format." }
            root.timerLockNotice = String(invalidTimeResult.message)
            root.showSaveFeedback("Invalid time value. Use decimal hours or HH:MM[:SS].", true)
            return invalidTimeResult
        }
        var matterText = String(matterCombo.editText || "").trim()
        var clientText = String(clientCombo.editText || "").trim()
        if (!options.skipMatterPrompt && matterText.length <= 0 && clientText.length > 0 && !options.allowClientOnlyDraft) {
            openMatterRequiredPrompt(reasonTag, options)
            var matterPromptResult = { "ok": false, "message": "Matter selection required." }
            root.timerLockNotice = "Select a matter, or use Client-only Draft."
            root.showSaveFeedback("Matter required before saving.", true)
            return matterPromptResult
        }

        var isInactive = false
        var matterIdToReopen = ""
        var inactiveMatterStatus = ""
        var inactiveMatterRow = ({})
        if (!options.skipInactivePrompt && matterText.length > 0) {
            for (var i = 0; i < root._rawMatterDirectory.length; i++) {
                var mrow = root._rawMatterDirectory[i]
                var mname = String(mrow.matterName || mrow.displayName || "")
                if (mname === matterText || String(mrow.matterId || "") === matterText || String(mrow.matterNumber || "") === matterText) {
                    matterIdToReopen = String(mrow.matterId || "")
                    inactiveMatterRow = mrow
                    inactiveMatterStatus = String(mrow.status || "").trim().toLowerCase()
                    if (inactiveMatterStatus === "archived") {
                        isInactive = true
                    }
                    if (mrow.active === 0 || mrow.active === false || mrow.active === "false" || String(mrow.active).toLowerCase() === "inactive") {
                        isInactive = true
                    }
                    if (inactiveMatterStatus === "closed") {
                        isInactive = true
                    }
                    break
                }
            }
        }
        
        if (isInactive) {
            root.pendingSaveReason = String(reasonTag || "manual-save")
            root.pendingSaveOptions = cloneOptions(options)
            root._inactiveMatterId = matterIdToReopen
            root._inactiveMatterRow = inactiveMatterRow
            var inactiveResult = { "ok": false, "message": "Matter is closed or inactive." }
            if (inactiveMatterStatus === "archived") {
                inactiveMatterPopup.openFor(inactiveMatterRow)
                root.timerLockNotice = "Matter is archived. Complete the protected re-open flow before saving."
                root.showSaveFeedback("Matter is archived. No time entry was saved.", true)
            } else {
                root.timerLockNotice = "Matter is closed or inactive. Re-open it in Matter Profile before saving."
                root.showSaveFeedback("Matter is closed or inactive.", true)
            }
            return inactiveResult
        }

        if (saveInProgress) {
            var busyResult = { "ok": false, "message": "Save already in progress." }
            root.timerLockNotice = String(busyResult.message)
            root.showSaveFeedback(busyResult.message, true)
            return busyResult
        }
        saveInProgress = true
        var result = {}
        try {
            if (appRef && appRef.saveTimeDocketEntry) {
                result = appRef.saveTimeDocketEntry(buildPersistencePayload(options))
            } else {
                result = { "ok": false, "verifiedExact": false, "message": "Backend save is unavailable." }
            }
        } catch (e) {
            result = { "ok": false, "verifiedExact": false, "message": String(e) }
        }
        saveInProgress = false

        var exactOk = !!(result && result.ok && result.verifiedExact)
        lastSaveWasExact = exactOk
        if (exactOk) {
            lastSavedEntryId = (result.entryId !== undefined && result.entryId !== null) ? String(result.entryId) : ""
            if (result.savedRow && result.savedRow.Status !== undefined) {
                root.docketStatusText = normalizedDocketStatus(result.savedRow.Status)
            } else if (result.status !== undefined) {
                root.docketStatusText = normalizedDocketStatus(result.status)
            }
            var persistedSeconds = -1
            try {
                if (result.savedRow && result.savedRow.RawSeconds !== undefined) {
                    persistedSeconds = parseInt(result.savedRow.RawSeconds)
                } else if (result.aggregateRawSeconds !== undefined) {
                    persistedSeconds = parseInt(result.aggregateRawSeconds)
                }
            } catch (persistErr) {
                persistedSeconds = -1
            }
            if (isFinite(persistedSeconds) && persistedSeconds >= 0) {
                root._hydrating = true
                root.elapsedSeconds = Math.max(0, Math.floor(persistedSeconds))
                syncTimeFieldFromElapsed()
                root.lastPersistedSeconds = root.elapsedSeconds
                root._hydrating = false
            } else {
                root.lastPersistedSeconds = Math.max(0, Math.floor(root.elapsedSeconds || 0))
            }
            root.persistedBucketKey = currentBucketKey()
            if (root.isRunning) {
                root.activeSegmentStartedAtMs = Date.now()
            }
            if (!root._hydrating) root.dirty = false
            root.timerLockNotice = "Saved " + (lastSavedEntryId.length > 0 ? ("entry " + lastSavedEntryId + " ") : "")
                + "(" + root.formatHoursRounded(root.elapsedSeconds) + " hrs)."
            root.showSaveFeedback(
                "Docket saved"
                + (lastSavedEntryId.length > 0 ? (": " + lastSavedEntryId) : "")
                + " (" + root.formatHoursRounded(root.elapsedSeconds) + " hrs).",
                false
            )
            root.refreshDocketReportAfterSave()
            if (root._returnToTileIndex >= 0 && root.windowRef) {
                var targetIdx = root._returnToTileIndex
                var targetNode = root._returnToNodeId || ""
                root._returnToTileIndex = -1
                root._returnToNodeId = ""
                var navTarget = root.windowRef.mainContentRef || root.windowRef
                if (navTarget && navTarget.option3OpenWorkspaceForTile) {
                    navTarget.option3OpenWorkspaceForTile(targetIdx, targetNode)
                }
            }
        } else {
            if (!root._hydrating) root.dirty = true
            root.timerLockNotice = String((result && result.message) ? result.message : "Save failed.")
            root.showSaveFeedback(root.timerLockNotice, true)
        }
        try {
            if (windowRef && windowRef.autoCheckpointCloseSession) {
                windowRef.autoCheckpointCloseSession("time-docket-save")
            }
        } catch (e2) {
        }
        return result
    }

    function getClientRecordFromName(cName) {
        var cleanName = String(cName || "").trim().toLowerCase()
        if (!cleanName || cleanName === "(none)" || cleanName === "(blank)") return null
        for (var i = 0; i < root._rawClientDirectory.length; i++) {
            var c = root._rawClientDirectory[i]
            var dName = String(c.displayName || "").trim().toLowerCase()
            var clName = String(c.clientName || "").trim().toLowerCase()
            if (dName === cleanName || clName === cleanName) {
                return c
            }
        }
        return null
    }

    function getMatterRecordFromName(mSel) {
        var cleanMSel = String(mSel || "").replace(/ - $/, "").replace(/ - undefined$/, "").trim().toLowerCase()
        if (!cleanMSel || cleanMSel === "(none)" || cleanMSel === "(blank)") return null
        if (!root._rawMatterDirectory) return null
        var best = null
        var bestScore = -1
        for (var i = 0; i < root._rawMatterDirectory.length; i++) {
            var m = root._rawMatterDirectory[i]
            var mId = String(m.matterId || "").trim().toLowerCase()
            var mNum = String(m.matterNumber || "").trim().toLowerCase()
            var mName = String(m.matterName || "").trim().toLowerCase()
            var dName = String(m.displayName || "").trim().toLowerCase()
            var mStr = mNum + (mName ? " - " + mName : "")
            var score = -1
            if (mId && mId === cleanMSel) score = 1000
            else if (mNum && mNum === cleanMSel) score = 900
            else if (mStr && mStr === cleanMSel) score = 850
            else if (dName && dName === cleanMSel) score = 700
            else if (mName && mName === cleanMSel) score = 500
            else if (mNum && cleanMSel.indexOf(mNum) === 0) score = 450
            if (score > bestScore) {
                bestScore = score
                best = m
            }
        }
        return best
    }

    function getClientIdFromName(cName) {
        var c = getClientRecordFromName(cName)
        return c ? String(c.clientId || "") : ""
    }
    
    function getMatterIdFromName(mSel) {
        var m = getMatterRecordFromName(mSel)
        return m ? String(m.matterId || m.matterNumber || "") : ""
    }

    function requestOption3Save(command, tab) {
        var saveCommand = String(command || "").trim()
        if (saveCommand === "time-docket") {
            var docketResult = requestSaveToDatabaseIfNeeded("option3-tab-close")
            return !!(docketResult && docketResult.ok && docketResult.verifiedExact)
        }
        if (saveCommand === "fee-docket") {
            return !!(feeDocketEntryPanel && feeDocketEntryPanel.saveFeeEntry && feeDocketEntryPanel.saveFeeEntry())
        }
        if (saveCommand === "deadline-entry") {
            saveEditing()
            return true
        }
        if (saveCommand === "trademark-filing") {
            var trademarkItem = trademarkLoader ? trademarkLoader.item : null
            var trademarkSaveMethod = "save" + "Record"
            if (activeIsTrademarkEntry() && trademarkItem && typeof trademarkItem[trademarkSaveMethod] === "function") {
                trademarkItem[trademarkSaveMethod]()
                return true
            }
            return false
        }
        return false
    }

    function openReportEntryForEdit(row) {
        if (!row) return
        
        root.refreshLookupLists()
        try { if (bucketLookupDebounce) bucketLookupDebounce.stop() } catch (e0) {}
        
        var nextDate = String(row.Date || row.date || "").trim()
        var nextClient = String(row.clientName || "").trim()
        var nextMatter = String(row.matterName || "").trim()
        if (nextMatter.toLowerCase() === "no matter") nextMatter = ""
        var nextDescription = String(row.Description || row.description || "").trim()
        var nextStatus = normalizedDocketStatus(String(row.Status || row.status || "Draft"))
        var nextTask = String(row.Task || row.activity || "").trim()
        var nextRate = Number(row.ClientRate || row.rate)
        var nextShare = Number(row.SharePct || row.sharePct)
        var nextSeconds = parseInt(row.RawSeconds || row.rawSeconds)
        var nextHours = Number(row.hours)

        if (!isFinite(nextSeconds) || nextSeconds < 0) {
            if (isFinite(nextHours) && nextHours > 0) {
                nextSeconds = Math.max(0, Math.round(nextHours * 3600))
            } else {
                nextSeconds = 0
            }
        }

        _hydrating = true
        _returnToReportOnCancel = true
        activeSubwindowId = "B01"
        ensureActiveSubwindow()

        if (dateInput) dateInput.text = nextDate.length > 0 ? nextDate : Qt.formatDate(new Date(), "yyyy-MM-dd")
        root.setComboTextStrict(clientCombo, nextClient)
        root.updateCascadingDropdowns("client")
        root.setComboTextStrict(matterCombo, nextMatter)
        root.updateCascadingDropdowns("matter")
        root.setComboTextStrict(taskCombo, nextTask)
        
        root.lastSavedEntryId = String(row.EntryID || row.entryId || row.Id || "")
        
        if (descInput) descInput.text = nextDescription
        
        if (isFinite(nextRate) && nextRate >= 0) {
            if (rateInput) rateInput.text = nextRate.toFixed(2)
        } else {
            if (rateInput) rateInput.text = "0.00"
        }
        if (isFinite(nextShare) && nextShare >= 0) {
            if (billInput) billInput.text = String(nextShare.toFixed(2))
        } else {
            if (billInput) billInput.text = "0.00"
        }

        root.docketStatusText = nextStatus
        root.elapsedSeconds = Math.max(0, Math.floor(nextSeconds))
        syncTimeFieldFromElapsed()
        root.lastPersistedSeconds = root.elapsedSeconds
        root.persistedBucketKey = currentBucketKey()
        root.calculateFees()
        root.dirty = true
        _hydrating = false
    }

    function clearDocketForm() {
        _hydrating = true
        root.lastSavedEntryId = ""
        if (timeInput) timeInput.text = ""
        if (descInput) descInput.text = ""
        if (billInput) billInput.text = ""
        
        root.resetDocketTimerToZero()
        root.docketStatusText = "Draft"
        root.calculateFees()
        
        root.dirty = false
        _hydrating = false
    }

    function returnToCallerOrClose() {
        var navTarget = root.windowRef ? (root.windowRef.mainContentRef || root.windowRef) : null
        var currentTabId = ""
        if (navTarget && navTarget.option3ActiveTabId) {
            currentTabId = String(navTarget.option3ActiveTabId)
        }

        if (root._returnToTileIndex >= 0 && root.windowRef) {
            var targetIdx = root._returnToTileIndex
            var targetNode = root._returnToNodeId || ""
            root._returnToTileIndex = -1
            root._returnToNodeId = ""
            if (navTarget && navTarget.option3OpenWorkspaceForTile) {
                navTarget.option3OpenWorkspaceForTile(targetIdx, targetNode)
            }
            if (currentTabId.length > 0 && navTarget.option3CloseTab) {
                navTarget.option3CloseTab(currentTabId, true)
            }
        } else if (currentTabId.length > 0 && navTarget && navTarget.option3CloseTab) {
            navTarget.option3CloseTab(currentTabId, true)
        } else if (root._returnToReportOnCancel) {
            root._returnToReportOnCancel = false;
            root.activeSubwindowId = "B04";
            root.ensureActiveSubwindow();
            root.requestDocketReportPanelLoad("cancel-return-report", true)
        } else {
            root.returnRequested(root.snapshotState());
        }
    }

    function snapshotState() {
        var state = {
            "tileIndex": root.tileIndex,
            "titleText": root.titleText,
            "focusNodeId": root.activeSubwindowId,
            "focusNodeTitle": String(root.currentNavNode().title || ""),
            "elapsedSeconds": root.elapsedSeconds,
            "lastPersistedSeconds": root.lastPersistedSeconds,
            "persistedBucketKey": root.persistedBucketKey,
            "docketStatusText": root.docketStatusText,
            "isRunning": root.isRunning,
            "dirty": root.currentDirtyState(),
            "dateText": dateInput.text,
            "timeText": timeInput.text,
            "rateText": rateInput.text,
            "billText": billInput.text,
            "feesText": feesInput.text,
            "matterText": matterCombo.editText,
            "clientText": clientCombo.editText,
            "taskText": taskCombo.editText,
            "descriptionText": descInput.text,
            "deadlineFilterState": deadlineFilterStatePayload(),
            "docketReportState": (docketActivityReportPanel && docketActivityReportPanel.snapshotState)
                ? docketActivityReportPanel.snapshotState()
                : ({})
        }
        // trademark panel state (entry + directory caches)
        if (activeIsTrademarkEntry() && trademarkLoader && trademarkLoader.item && trademarkLoader.item.snapshotState) {
            state.trademarkState = trademarkLoader.item.snapshotState()
        } else {
            state.trademarkState = root.tf_state || ({})
        }
        if (activeIsTrademarkDirectory() && trademarkLoader && trademarkLoader.item && trademarkLoader.item.snapshotState) {
            state.trademarkDirectoryState = trademarkLoader.item.snapshotState()
        } else {
            state.trademarkDirectoryState = root.td_state || ({})
        }
        return state
    }

    function applyInitialState(state) {
        if (root.timerProtectedMode || (root.timerIsRunningNow && root.timerIsRunningNow())) {
            return
        }
        if (!state) return

        if (state.returnToTileIndex !== undefined) {
            root._returnToTileIndex = state.returnToTileIndex
        } else {
            root._returnToTileIndex = -1
        }
        if (state.returnToNodeId !== undefined) {
            root._returnToNodeId = state.returnToNodeId
        } else {
            root._returnToNodeId = ""
        }

        if (state.editRowData !== undefined) {
            root.openReportEntryForEdit(state.editRowData)
            return
        }

        if (state.briefingDeadlineId !== undefined || state.briefingCalendarDate !== undefined) {
            if (state.focusNodeId !== undefined) {
                root.activeSubwindowId = String(state.focusNodeId || "B07")
            }
            root.pendingBriefingDeadlineId = String(state.briefingDeadlineId || "")
            root.pendingBriefingCalendarDate = String(state.briefingCalendarDate || "")
            root.ensureActiveSubwindow()
            root.loadDeadlines()
            return
        }

        if (state.cspmQuickAction === "matter360Docket" || state.forceNewDocketContext || state.forceApplyStateAfterOpen) {
            applyMatterQuickActionState(state)
            return
        }
        if (state.forceApplyStateAfterOpen || state.suppressBucketRefreshOnce || state.option3EntityType === "matter") {
            applyMatterQuickActionState(state)
            return
        }

        _hydrating = true

        if (state.focusNodeId !== undefined) {
            root.activeSubwindowId = String(state.focusNodeId || "")
        }
        // restore trademark cache if provided
        if (state.trademarkState !== undefined) {
            root.tf_state = state.trademarkState || ({})
            if (root.tf_state && typeof root.tf_state === "object") {
                root.tf_state.dirty = false
            }
            root.trademarkFormDirty = false
            // also prefill the lightweight fields for backwards compatibility
            root.tf_appNo = state.trademarkState.f_appNo || ""
            root.tf_trademark = state.trademarkState.f_trademark || ""
            root.tf_office = state.trademarkState.f_office || ""
            root.tf_status = state.trademarkState.f_status || ""
            root.tf_notes = state.trademarkState.f_notes || ""
        }
        if (state.trademarkDirectoryState !== undefined) {
            root.td_state = state.trademarkDirectoryState || ({})
        }
        ensureActiveSubwindow()
        if (state.deadlineFilterState !== undefined) {
            applyDeadlineFilterState(state.deadlineFilterState, false)
        }

        if (state.dateText !== undefined) dateInput.text = state.dateText
        if (state.timeText !== undefined) {
            timeInput.text = state.timeText
            root.originalLoadedTime = state.timeText
        }
        if (state.rateText !== undefined) {
            rateInput.text = state.rateText
            root.originalLoadedRate = state.rateText
        }
        if (state.billText !== undefined) billInput.text = state.billText

        // Client first, then matter. Matter cascading can infer/change the client;
        // doing this in the opposite order makes cross-screen prefill fragile.
        if (state.clientText !== undefined) {
            clientCombo.editText = state.clientText
            var ci = clientCombo.find(state.clientText)
            if (ci >= 0) clientCombo.currentIndex = ci
        }
        if (state.matterText !== undefined) {
            matterCombo.editText = state.matterText
            var mi = matterCombo.find(state.matterText)
            if (mi >= 0) matterCombo.currentIndex = mi
        }
        if (state.taskText !== undefined) {
            taskCombo.editText = state.taskText
            var ti = taskCombo.find(state.taskText)
            if (ti >= 0) taskCombo.currentIndex = ti
        }
        if (state.descriptionText !== undefined) descInput.text = state.descriptionText

        if (state.elapsedSeconds !== undefined) {
            root.elapsedSeconds = Math.max(0, Math.floor(state.elapsedSeconds || 0))
            syncTimeFieldFromElapsed()
        }
        if (state.lastPersistedSeconds !== undefined) {
            root.lastPersistedSeconds = Math.max(0, Math.floor(state.lastPersistedSeconds || 0))
        }
        if (state.lastSavedEntryId !== undefined) {
            root.lastSavedEntryId = String(state.lastSavedEntryId || "")
        }
        if (state.persistedBucketKey !== undefined) {
            root.persistedBucketKey = String(state.persistedBucketKey || "")
        }
        if (state.docketStatusText !== undefined) {
            root.docketStatusText = normalizedDocketStatus(state.docketStatusText)
        }
        if (state.docketReportState !== undefined) {
            root.pendingDocketReportState = state.docketReportState
            if (docketActivityReportPanel && docketActivityReportPanel.applyState) {
                docketActivityReportPanel.applyState(state.docketReportState, false)
                root.pendingDocketReportState = null
            } else if (root.activeIsDocketReport()) {
                requestDocketReportPanelLoad("applyInitialState", false)
            }
        }

        if (activeIsTrademarkEntry()) {
            root.dirty = !!root.trademarkFormDirty
        } else if (activeIsTrademarkDirectory() || activeIsDocketReport()) {
            root.dirty = false
        } else {
            root.dirty = !!state.dirty
        }

        // Timer
        root.isRunning = !!state.isRunning
        if (root.isRunning) {
            if (acquireTimerLock(false)) {
                root.activeSegmentStartedAtMs = Date.now()
                docketTimer.start()
            } else {
                root.isRunning = false
                docketTimer.stop()
            }
        } else {
            docketTimer.stop()
            root.activeSegmentStartedAtMs = 0
            releaseTimerLock()
        }

        calculateFees()
        _hydrating = false
        if (!root.dirty) {
            scheduleBucketRefresh()
        }
    }


    Connections {
        target: (typeof docketApp !== "undefined") ? docketApp : ((appRef && appRef.docketing) ? appRef.docketing : null)
        function onTimeDocketAggregateFinished(result) {
        if (root.cspmTimerWatchdogActive || root.isRunning || Number(root.activeSegmentStartedAtMs || 0) > 0) {
            return
        }
        if (root.timerIsActivelyRunning && root.timerIsActivelyRunning()) {
            return
        }
            root.aggregateLoadInProgress = false
            root.applyAggregateResult(result || ({}))
        }

        function onUnlinkBilledDocketFinished(result) {
            if (result && result.ok) {
                root.docketStatusText = "Draft"
                root.docketInvoiceRef = ""
                root.timerLockNotice = ""
                root.showSaveFeedback("Unlinked successfully. Docket is now Draft.", false)
                if (!root._hydrating) root.dirty = false
            }
        }
    }

    // CHATGPT-TIMER-WATCHDOG
    // Disabled legacy watchdog. Timing is now controlled only by docketTimer.

    // Keeps a paused unsaved docket from being visually repainted as 0
    // by delayed aggregate/bucket refreshes.





    Timer {
        id: docketTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.handleMidnightSplitIfNeeded()
            if (!root.timerIsRunningNow()) {
                return
            }
            root.timerApplyRawSeconds(root.timerRawSecondsNow())
        }
    }

    Timer {
        id: timerLockWatchdog
        interval: 900
        repeat: true
        running: root.isRunning
        onTriggered: root.verifyGlobalTimerLockOwner()
    }

    Timer {
        id: startupHydrationRetryTimer
        interval: 220
        repeat: false
        onTriggered: {
            root.startupDeferredHydrationPending = false
            root.runStartupHydration("startupHydrationRetryTimer")
        }
    }

    Timer {
        id: bucketLookupDebounce
        interval: 220
        repeat: false
        onTriggered: root.loadAggregateForCurrentBucket()
    }

    Timer {
        id: saveFeedbackTimer
        interval: 7000
        repeat: false
        onTriggered: {
            root.saveFeedbackText = ""
            root.saveFeedbackIsError = false
        }
    }

    Timer {
        id: deadlineMatterOptionsRetryTimer
        interval: 500
        repeat: false
        onTriggered: root.refreshDeadlineMatterOptions()
    }

    // ===== TIMER POPUP (edit) =====
    Popup {
        id: timerEditPopup
        modal: true
        focus: true
        dim: false // Fixes square border artifact

        padding: root.ratioPx(root.scaleRatios.popupMarginPct, 1)
        width: root.ratioPxW(root.scaleRatios.popupWidthPct, 1)
        implicitHeight: Math.max(
            root.ratioPxH(root.scaleRatios.popupHeightPct, 1),
            timerEditContent.implicitHeight + (padding * 2)
        )
        height: implicitHeight
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        property bool hasError: false

        background: Rectangle {
            id: timerPopupBg
            property int shadowOffsetPx: root.ratioPx(root.scaleRatios.popupSpacingPct, 1)
            color: root._panel
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(root.scaleRatios.popupCornerPct, 1)
            border.width: root.ratioPx(root.scaleRatios.popupBorderPct, 1)
            border.color: timerEditPopup.hasError ? Qt.darker(root._accent, 1.2) : root._accent
            
            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Qt.rgba(0,0,0,0.5)
                shadowBlur: 0.4
                shadowVerticalOffset: timerPopupBg.shadowOffsetPx
                shadowHorizontalOffset: 0
            }
        }


        contentItem: ColumnLayout {
            id: timerEditContent









            property int editTimerDraftSeconds: 0

        function formatEditTimerSeconds(totalSeconds) {
            var sec = Math.max(0, Math.floor(Number(totalSeconds || 0)))
            var h = Math.floor(sec / 3600)
            var m = Math.floor((sec % 3600) / 60)
            var s = sec % 60
            function pad(n) { return n < 10 ? "0" + n : "" + n }
            return pad(h) + ":" + pad(m) + ":" + pad(s)
        }

        function parseEditTimerSeconds(textValue) {
            var raw = String(textValue || "").trim()
            if (raw.length <= 0) return 0
            var parts = raw.split(":")
            var h = 0
            var m = 0
            var s = 0
            if (parts.length === 3) {
                h = parseInt(parts[0])
                m = parseInt(parts[1])
                s = parseInt(parts[2])
            } else if (parts.length === 2) {
                m = parseInt(parts[0])
                s = parseInt(parts[1])
            } else {
                s = parseInt(parts[0])
            }
            if (!isFinite(h)) h = 0
            if (!isFinite(m)) m = 0
            if (!isFinite(s)) s = 0
            return Math.max(0, Math.floor(h * 3600 + m * 60 + s))
        }

            function setEditTimerDraftSeconds(totalSeconds) {
                var value = Math.max(0, Math.floor(Number(totalSeconds || 0)))
                editTimerDraftSeconds = value

                try {
                    timerHms.text = formatEditTimerSeconds(value)
                    timerHms.forceActiveFocus()
                    if (timerHms.selectAll) timerHms.selectAll()
                } catch (e0) {
                }

                return value
            }

        function resetEditTimerDraftOnly() {
            try {
                timerEditContent.text = formatEditTimerSeconds(0)
                timerEditContent.forceActiveFocus()
                if (timerEditContent.selectAll) timerEditContent.selectAll()
            } catch (e0) {
            }
            return true
        }

        function closeEditTimerDialog() {
            try {
                if (timerEditPopup.close) timerEditPopup.close()
            } catch (e0) {
            }
            try {
                timerEditPopup.visible = false
            } catch (e1) {
            }
            try {
                timerEditPopup.enabled = false
            } catch (e2) {
            }
            return true
        }

        function applyEditTimerDraftToTimer() {
            var value = 0
            try {
                value = parseEditTimerSeconds(timerEditContent.text)
            } catch (e0) {
                value = 0
            }
            value = Math.max(0, Math.floor(Number(value || 0)))

            try {
                if (docketTimer) docketTimer.stop()
            } catch (e1) {
            }
            try {
                releaseTimerLock()
            } catch (e2) {
            }

            root.isRunning = false
            root.activeSegmentStartedAtMs = 0
            root.activeSegmentBaseSeconds = value
            root.pausedRawSeconds = value
            root.elapsedSeconds = value

            try {
                if (root.timerProtectedMode !== undefined) root.timerProtectedMode = true
            } catch (e3) {
            }
            try {
                if (root.timerApplyRawSeconds) {
                    root.timerApplyRawSeconds(value)
                } else {
                    root.syncTimeFieldFromElapsed()
                }
            } catch (e4) {
                root.syncTimeFieldFromElapsed()
            }
            try {
                calculateFees()
            } catch (e5) {
            }
            root.dirty = true
            root.cspmCloseEditTimerDialog()
            return value
        }
            function loadEditTimerDraftFromCurrentTimer() {
                var value = 0

                try {
                    value = root.timerRawSecondsNow ? root.timerRawSecondsNow() : Number(root.elapsedSeconds || 0)
                } catch (e0) {
                    value = Number(root.elapsedSeconds || 0)
                }

                setEditTimerDraftSeconds(value)
            }





            width: timerEditPopup.availableWidth
            spacing: root.ratioPx(root.scaleRatios.popupSpacingPct, 1)

            Text {
                text: "Edit Timer (HH:MM:SS)"
                color: root._text
                font.pixelSize: root.ratioPx(root.scaleRatios.popupTitleFontPct, root.metricFloor("fontFloorTitlePx", 1))
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }

            TextField {
                id: timerHms
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(
                    timerEditPopup.availableWidth,
                    root.ratioPxW(root.scaleRatios.timerEditFieldWidthPct, 1)
                )
                Layout.preferredHeight: root.ratioPxH(root.scaleRatios.timerEditFieldHeightPct, 1)
                font.pixelSize: root.ratioPx(root.scaleRatios.timerEditFieldFontPct, root.metricFloor("fontFloorBodyPx", 1))
                font.weight: Font.DemiBold
                color: root._text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                placeholderText: "HH:MM:SS"

                background: Rectangle {
                    radius: root.isProMode
                        ? root.proControlRadiusPx
                        : root.ratioPx(root.scaleRatios.timerEditFieldCornerPct, 3)
                    color: Qt.rgba(0, 0, 0, 0.18)
                    border.width: root.ratioPx(root.scaleRatios.timerEditFieldBorderPct, 1)
                    border.color: timerEditPopup.hasError ? Qt.darker(root._accent, 1.2) : Qt.rgba(1, 1, 1, 0.12)
                }

                onAccepted: applyBtn.clicked()
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(root.scaleRatios.tipSpacingPct, 1)

                Text {
                    text: "Tip:"
                    color: root._accent
                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, root.metricFloor("fontFloorLabelPx", 1))
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "Click timer anytime. Apply will pause and set time."
                    color: root._text
                    opacity: 0.88
                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, root.metricFloor("fontFloorLabelPx", 1))
                    font.weight: Font.Medium
                    Layout.fillWidth: true
                    Layout.minimumWidth: 1
                    wrapMode: Text.WordWrap
                }
            }

            Item {
                id: timerPopupActionStrip
                Layout.fillWidth: true
                Layout.preferredHeight: root.ratioPxH(root.scaleRatios.popupActionBtnHeightPct, 1)

                Row {
                    id: timerPopupActionRow
                    anchors.fill: parent
                    spacing: root.ratioPx(root.scaleRatios.popupSpacingPct * 1.2, 6)
                    property real buttonWidth: Math.max(
                        root.ratioPx(0.068, 92),
                        Math.floor((width - (spacing * 2)) / 3)
                    )

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Reset Timer"
                        primary: false
                        width: timerPopupActionRow.buttonWidth
                        height: parent.height
                        onClicked: {
                            root.cspmResetEditTimerDraftOnly()
                        }
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Cancel"
                        primary: false
                        width: timerPopupActionRow.buttonWidth
                        height: parent.height
                        onClicked: {
                            root.cspmCloseEditTimerDialog()
                        }
                    }

                    PillButton {
                        id: applyBtn
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Apply"
                        primary: true
                        width: timerPopupActionRow.buttonWidth
                        height: parent.height
                        onClicked: {
                            root.cspmApplyEditTimerDialog()
                        }
                    }
                }
            }
        }
    }

    // ===== MAIN LAYOUT =====
    RowLayout {
        anchors.fill: parent
        anchors.margins: root.professionalHostedOuterMarginPx
        spacing: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.68, 6)
        z: 1

        Rectangle {
            id: moduleSidebar
            Layout.preferredWidth: (root.externalNavigationShell && root.isProMode)
                ? 0
                : root.ratioPxW(0.228, 224)
            Layout.fillHeight: true
            visible: !(root.externalNavigationShell && root.isProMode)
            enabled: visible
            radius: root.sectionRadiusPx
            color: root.isProMode
                ? root.proSurface
                : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.88)
            border.width: root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
            border.color: root.isProMode
                ? root.proBorder
                : SemanticTheme.borderSubtle(root.t, root.appStyle)

            layer.enabled: !root.isProMode
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Qt.rgba(0, 0, 0, 0.18)
                shadowBlur: 0.16
                shadowVerticalOffset: root.ratioPx(0.0015, 1)
                shadowHorizontalOffset: 0
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                spacing: root.isProMode ? 10 : root.ratioPx(0.006, 4)

                Text {
                    Layout.fillWidth: true
                    text: root.titleText
                    color: root.isProMode
                        ? root.proInk
                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.92)
                    font.family: visualRules.textFontFamily
                    font.pixelSize: root.isProMode
                        ? visualRules.proSectionTitleFontPx
                        : root.ratioPx(root.scaleRatios.headerSubtitleFontPct * 1.03, root.metricFloor("fontFloorLabelPx", 10))
                    elide: Text.ElideRight
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                }

                Text {
                    Layout.fillWidth: true
                    text: "Pathway map"
                    color: root.isProMode
                        ? root.proMutedInk
                        : SemanticTheme.inkMuted(root.t, root.appStyle)
                    font.family: visualRules.textFontFamily
                    font.pixelSize: root.isProMode
                        ? visualRules.proCaptionFontPx
                        : root.ratioPx(root.scaleRatios.hintFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                    elide: Text.ElideRight
                }

                // quick home buttons (same as lane chips in PlaceholderSubmenuView)
                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.isProMode
                    Layout.preferredHeight: visible ? implicitHeight : 0
                    spacing: root.ratioPx(0.0045, 4)
                    Repeater {
                        model: root.laneSwitchModel
                        delegate: Rectangle {
                            id: laneChip
                            required property var modelData
                              Layout.fillWidth: true
                              Layout.preferredHeight: root.ratioPxH(0.033, 24)
                              radius: root.isProMode ? root.proControlRadiusPx : height / 2
                              property bool active: root.tileIndex === laneChip.modelData.tileIndex
                              property bool hovered: laneChipHover.containsMouse
                              color: active
                                  ? root.sidebarHoverFill(active, true, 0.24, 0.98, 0.82)
                                  : root.sidebarHoverFill(active, hovered, 0.24, 0.98, 0.82)
                              border.width: 1
                              border.color: active
                                  ? root.sidebarHoverBorder(active, true, 0.72, 0.98, 0.16)
                                  : root.sidebarHoverBorder(active, hovered, 0.72, 0.98, 0.16)
Behavior on color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}
Behavior on border.color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}

                            Text {
                                anchors.centerIn: parent
                                readonly property real labelWidthPx: Math.max(1, parent.width - root.ratioPx(0.010, 8))
                                width: labelWidthPx
                                text: String(laneChip.modelData.title || "")
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.90)
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0090, root.metricFloor("fontFloorLabelPx", 7))
                                minimumPixelSize: Math.max(6, root.readableMinFontPx() - 2)
                                fontSizeMode: Text.Fit
                                font.weight: Font.DemiBold
                            }

                            MouseArea {
                                id: laneChipHover
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                cursorShape: laneChip.active ? Qt.ArrowCursor : Qt.PointingHandCursor
                                onClicked: function(mouse) {
                                    mouse.accepted = true
                                    if (!laneChip.active) {
                                        root.moduleJumpRequested(laneChip.modelData.tileIndex, root.snapshotState())
                                    }
                                }
                            }
                            ToolTip.visible: laneChipHover.containsMouse
                            ToolTip.delay: 280
                            ToolTip.text: String(laneChip.modelData.title || "")
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth

                    ListView {
                        id: navList
                        width: parent.width
                        model: root.normalizedNavItems()
                        spacing: root.ratioPx(0.0042, 3)

                        delegate: Rectangle {
                            id: navRow
                            required property var modelData
                            width: navList.width
                            height: root.ratioPxH(0.050, 36)
                            radius: root.isProMode ? root.proControlRadiusPx : Math.max(6, root.sectionRadiusPx - 2)
                              property bool isCurrent: String(modelData.id || "") === String(root.activeSubwindowId || "")
                              color: isCurrent
                                  ? (root.isProMode
                                      ? root.proHoverFill
                                      : root.sidebarHoverFill(isCurrent, true, 0.22, 0.96, 0.82))
                                  : (root.isProMode
                                      ? (navHover.containsMouse ? root.proHoverFill : "transparent")
                                      : root.sidebarHoverFill(isCurrent, navHover.containsMouse, 0.22, 0.96, 0.82))
                            border.width: root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
                            border.color: isCurrent
                                ? (root.isProMode
                                    ? root.proActiveBorder
                                    : root.sidebarHoverBorder(isCurrent, true, 0.66, 0.94, 0.16))
                                : (root.isProMode
                                    ? (navHover.containsMouse ? root.proBorder : "transparent")
                                    : root.sidebarHoverBorder(isCurrent, navHover.containsMouse, 0.66, 0.94, 0.16))
Behavior on color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}
Behavior on border.color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: root.ratioPx(0.0085, 7)
                                anchors.rightMargin: root.ratioPx(0.0085, 7)
                                spacing: root.ratioPx(0.0040, 3)

                                Text {
                                    Layout.fillWidth: true
                                    text: navRow.modelData.title
                                    color: root.isProMode
                                        ? (navRow.isCurrent || navHover.containsMouse ? root.proInk : root.proMutedInk)
                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.92)
                                    elide: Text.ElideRight
                                    fontSizeMode: Text.Fit
                                    minimumPixelSize: Math.max(7, root.readableMinFontPx() - 1)
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: root.isProMode
                                        ? visualRules.proLabelFontPx
                                        : root.ratioPx(0.0120, root.metricFloor("fontFloorLabelPx", 9))
                                    font.weight: navRow.isCurrent ? Font.DemiBold : Font.Medium
                                }
                            }

                            MouseArea {
                                id: navHover
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                cursorShape: navRow.current !== undefined ? (navRow.current ? Qt.ArrowCursor : Qt.PointingHandCursor) : (navRow.isCurrent ? Qt.ArrowCursor : Qt.PointingHandCursor)
                                onPressed: function(mouse) { mouse.accepted = false }
                            }

                            TapHandler {
                                enabled: !navRow.isCurrent
                                onTapped: {
                                    var newId = String(navRow.modelData.id || "")
                                    var prevId = String(root.activeSubwindowId || "")
                                    if (prevId === "B16" && trademarkLoader && trademarkLoader.item && trademarkLoader.item.snapshotState) {
                                        root.tf_state = trademarkLoader.item.snapshotState()
                                        root.trademarkFormDirty = !!root.tf_state.dirty
                                    } else if (prevId === "B17" && trademarkLoader && trademarkLoader.item && trademarkLoader.item.snapshotState) {
                                        root.td_state = trademarkLoader.item.snapshotState()
                                    }
                                    root.activeSubwindowId = newId
                                    root.ensureActiveSubwindow()
                                    if (!root._hydrating) {
                                        if (newId === "B16") {
                                            root.dirty = !!root.trademarkFormDirty
                                        } else if (newId === "B17") {
                                            root.dirty = root.formHasContent()
                                        } else if (newId === "B04") {
                                            root.dirty = false
                                        } else if (prevId === "B16") {
                                            root.dirty = !!root.trademarkFormDirty
                                        } else if (prevId === "B17") {
                                            root.dirty = false
                                        } else {
                                            root.dirty = true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: moduleCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.isProMode ? 0 : root.sectionRadiusPx
            color: root.isProMode
                ? "transparent"
                : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.86)
            border.width: root.isProMode ? 0 : root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
            border.color: root.isProMode
                ? "transparent"
                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.10)
            clip: true

            layer.enabled: !root.isProMode
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Qt.rgba(0, 0, 0, 0.20)
                shadowBlur: 0.18
                shadowVerticalOffset: root.ratioPx(0.0015, 1)
                shadowHorizontalOffset: 0
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: root.isProMode ? 0 : (root.activeIsLiveDocket() ? -8 : 0)
                anchors.margins: root.isProMode ? 0 : root.professionalLiveCanvasMarginPx
                spacing: root.isProMode ? 10 : (root.activeIsLiveDocket() ? 4 : root.controlGapPx)

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.isProMode
                        ? (root.activeIsLiveDocket() ? 38 : visualRules.proWorkspaceHeaderHeightPx)
                        : (root.activeIsLiveDocket() ? 38 : root.ratioPxH(root.scaleRatios.headerHeightPct, 42))
                    visible: true
                    spacing: root.isProMode ? 10 : (root.activeIsLiveDocket() ? 6 : root.ratioPx(root.scaleRatios.headerSpacingPct, 6))

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: root.isProMode ? visualRules.proWorkspaceHeaderGapPx : 2

                        Text {
                            Layout.fillWidth: true
                            text: {
                                var nodeTitle = String(root.currentNavNode().title || "Time Docket Entry")
                                return root.isProMode ? nodeTitle : (root.titleText + " - " + nodeTitle)
                            }
                            color: root.isProMode
                                ? root.proInk
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.98)
                            font.family: visualRules.textFontFamily
                            font.pixelSize: root.isProMode
                                ? visualRules.proWorkspaceTitleFontPx
                                : (root.activeIsLiveDocket() ? 18 : root.ratioPx(root.scaleRatios.headerTitleFontPct, root.metricFloor("fontFloorTitlePx", 12)))
                            fontSizeMode: Text.Fit
                            minimumPixelSize: root.isProMode
                                ? 12
                                : (root.activeIsLiveDocket() ? 14 : Math.max(root.readableMinFontPx() + 2, 10))
                            elide: Text.ElideRight
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.headerSummaryText()
                            color: root.isProMode
                                ? root.proMutedInk
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.72)
                            font.family: visualRules.textFontFamily
                            font.pixelSize: root.isProMode
                                ? visualRules.proWorkspaceSubtitleFontPx
                                : (root.activeIsLiveDocket() ? 10 : root.ratioPx(root.scaleRatios.tipFontPct * 0.92, root.metricFloor("fontFloorLabelPx", 8)))
                            fontSizeMode: Text.Fit
                            minimumPixelSize: root.isProMode
                                ? 9
                                : (root.activeIsLiveDocket() ? 8 : root.readableMinFontPx())
                            elide: Text.ElideRight
                            font.weight: Font.Medium
                        }
                    }

                    Item { Layout.fillWidth: true }

                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: 0
                        visible: root.activeIsLiveDocket()
                        enabled: visible
                        spacing: 8

                        Rectangle {
                            Layout.preferredHeight: 40
                            Layout.preferredWidth: 112
                            radius: root.isProMode ? root.proControlRadiusPx : 6
                            color: root.statusChipColor()
                            border.width: 1
                            border.color: root.isProMode
                                ? SemanticTheme.borderStrong(root.t, root.appStyle)
                                : Qt.rgba(1, 1, 1, 0.24)

                            Text {
                                anchors.centerIn: parent
                                text: root.normalizedDocketStatus(root.docketStatusText)
                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                font.family: visualRules.textFontFamily
                                font.pixelSize: root.isProMode
                                    ? visualRules.proCaptionFontPx
                                    : root.ratioPx(root.scaleRatios.tipFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }

                        Rectangle {
                            id: timerPill
                            Layout.preferredWidth: 174
                            Layout.preferredHeight: 40
                            color: root.isProMode
                                ? root.proSurface
                                : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.78)
                            radius: root.isProMode ? root.proControlRadiusPx : 6
                            border.width: root.ratioPx(root.scaleRatios.timerBoxBorderPct, 1)
                            border.color: root.isRunning
                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.54)
                                : (root.isProMode
                                    ? root.proBorder
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16))

                            Text {
                                anchors.centerIn: parent
                                text: root.formatTimer(root.elapsedSeconds)
                                color: root.isRunning
                                    ? root._accent
                                    : (root.isProMode
                                        ? root.proInk
                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.94))
                                font.family: root.isProMode ? visualRules.textFontFamily : "Consolas"
                                font.pixelSize: root.isProMode ? 20 : 22
                                font.weight: Font.Bold
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !root.isBucketLocked()
                                hoverEnabled: true
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.openTimerEditPopup()
                            }
                        }

                        PillButton {
                            t: root.t
                            metrics: root.responsiveMetrics
                            sfxBus: root.sfxBus
                            text: root.isBucketLocked() ? "Locked" : (root.isRunning ? "Stop" : "Start")
                            primary: true
                            enabled: !root.isBucketLocked()
                            Layout.preferredWidth: 120
                            Layout.preferredHeight: 40
                            onClicked: root.toggleTimer()
                        }

                        PillButton {
                            t: root.t
                            metrics: root.responsiveMetrics
                            sfxBus: root.sfxBus
                            text: "Reset"
                            primary: false
                            enabled: !root.isBucketLocked() && (root.isRunning || root.elapsedSeconds > 0)
                            Layout.preferredWidth: 116
                            Layout.preferredHeight: 40
                            onClicked: root.resetDocketTimerToZero()
                        }
                    }
                }

                Rectangle {
                    id: proFormCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.isProMode ? root.sectionRadiusPx : 0
                    color: root.isProMode ? root.proCanvas : "transparent"
                    border.width: root.isProMode ? 1 : 0
                    border.color: root.isProMode ? root.proBorder : "transparent"
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.isProMode ? 14 : 0
                        spacing: root.isProMode ? 14 : (root.activeIsLiveDocket() ? 4 : root.controlGapPx)

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: false
                    Layout.alignment: Qt.AlignTop
                    visible: root.activeIsLiveDocket()
                    enabled: visible
                    Layout.topMargin: 2
                    columns: 12
                    columnSpacing: 14
                    rowSpacing: root.isProMode ? 14 : 6

                    ModernTextField {
                        id: dateInput
                        objectName: "timeDocketDateInput"
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Date"
                        text: Qt.formatDate(new Date(), "yyyy-MM-dd")
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 3
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        onTextChanged: {
                            if (!root._hydrating) {
                                root.handleBucketContextChanged()
                                maybeMarkDirty()
                            }
                        }
                    }

                    ModernComboBox {
                        id: parentCombo
                        enabled: !root.isRunning && !root.isBucketLocked()
                        preserveEditTextOnModelChanged: false
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Client"
                        Layout.fillWidth: true
                        Layout.columnSpan: 5
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        z: 4
                        fullModel: []
                        Component.onCompleted: root.refreshLookupLists()
                        onActiveFocusChanged: if (activeFocus) root.refreshLookupLists()
                        onActivated: root.updateCascadingDropdowns("parent")
                        onEditTextChanged: root.updateCascadingDropdowns("parent")
                        onLabelDoubleClicked: {
                            var cRec = root.getClientRecordFromName(parentCombo.editText)
                            var cId = cRec ? String(cRec.clientId || "") : ""
                            var cName = cRec ? String(cRec.clientName || cRec.displayName || "") : ""
                            console.log("[TimeDocket] Billing Client label clicked. cId:", cId, "text:", parentCombo.editText)
                            if (cId) {
                                root.showSaveFeedback("Opening Billing Client: " + cId, false)
                                root.workspaceOpenRequested(0, "A03", { "focusNodeId": "A03", "selectedClientId": cId, "clientName": cName })
                            } else {
                                root.showSaveFeedback("Could not find ID for Billing Client.", true)
                            }
                        }
                    }

                    ModernComboBox {
                        id: clientCombo
                        enabled: !root.isRunning && !root.isBucketLocked()
                        preserveEditTextOnModelChanged: false
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Client"
                        Layout.fillWidth: true
                        Layout.columnSpan: 4
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        z: 3
                        fullModel: []
                        onActivated: root.updateCascadingDropdowns("client")
                        onEditTextChanged: root.updateCascadingDropdowns("client")
                        onLabelDoubleClicked: {
                            var cRec = root.getClientRecordFromName(clientCombo.editText)
                            var cId = cRec ? String(cRec.clientId || "") : ""
                            var cName = cRec ? String(cRec.clientName || cRec.displayName || "") : ""
                            console.log("[TimeDocket] Client label clicked. cId:", cId, "text:", clientCombo.editText)
                            if (cId) {
                                root.showSaveFeedback("Opening Client: " + cId, false)
                                root.workspaceOpenRequested(0, "A03", { "focusNodeId": "A03", "selectedClientId": cId, "clientName": cName })
                            } else {
                                root.showSaveFeedback("Could not find ID for Client.", true)
                            }
                        }
                    }

                    ModernComboBox {
                        id: matterCombo
                        enabled: !root.isRunning && !root.isBucketLocked()
                        preserveEditTextOnModelChanged: false
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Matter"
                        Layout.fillWidth: true
                        Layout.columnSpan: 8
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        z: 2
                        fullModel: []
                        onActivated: root.updateCascadingDropdowns("matter")
                        onEditTextChanged: root.updateCascadingDropdowns("matter")
                        onLabelDoubleClicked: {
                            var mRec = root.getMatterRecordFromName(matterCombo.editText)
                            var mId = mRec ? String(mRec.matterId || "") : ""
                            var mNum = mRec ? String(mRec.matterNumber || "") : ""
                            var mName = mRec ? String(mRec.matterName || mRec.displayName || "") : ""
                            console.log("[TimeDocket] Matter label clicked. mId:", mId, "text:", matterCombo.editText)
                            if (mId) {
                                root.showSaveFeedback("Opening Matter: " + mId, false)
                                root.workspaceOpenRequested(0, "A11", { "focusNodeId": "A11", "selectedMatterId": mId, "matterNumber": mNum, "matterName": mName })
                            } else {
                                root.showSaveFeedback("Could not find ID for Matter.", true)
                            }
                        }
                    }

                    ModernTextField {
                        id: timeInput
                        enabled: !root.isRunning && !root.isBucketLocked()
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Time (Hrs)"
                        text: root.formatHoursRounded(root.elapsedSeconds)
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        readOnly: root.isRunning || root.isBucketLocked()
                        onTextEdited: if (!root._hydrating && !root.isRunning && !root.isBucketLocked()) root.dirty = true
                        onTextChanged: root.calculateFees()
                        onAccepted: root.commitManualTimeField(true)
                        onActiveFocusChanged: {
                            if (!activeFocus
                                    && !root._manualTimeCommitBusy
                                    && !(timeFieldValidationPopup && timeFieldValidationPopup.visible)) {
                                root.commitManualTimeField(true)
                            }
                        }
                    }
                    
                    Connections {
                        target: root
                        function onElapsedSecondsChanged() {
                            if (!timeInput.activeFocus) {
                                timeInput.text = root.formatHoursRounded(root.elapsedSeconds)
                            }
                        }
                    }
                    
                    ModernTextField {
                        id: rateInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Rate ($)"
                        text: "475.00"
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        onTextChanged: {
                            root.calculateFees()
                            if (!root._hydrating) root.dirty = true
                        }
                    }

                    ModernComboBox {
                        id: taskCombo
                        preserveEditTextOnModelChanged: false
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Task / Activity"
                        Layout.fillWidth: true
                        Layout.columnSpan: 8
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        z: 1
                        fullModel: [
                            "Communication - Client",
                            "Communication - Opposing Counsel",
                            "Communication - Opposing Party",
                            "Communication - CRA",
                            "Communication - Internal",
                            "Drafting - Client Memo",
                            "Drafting - Notes to File",
                            "Drafting - Memo to File",
                            "Drafting - Legal Documents",
                            "Emails - Review and Response",
                            "Meeting - Client",
                            "Meeting - Internal",
                            "Meeting - External",
                            "Planning and Strategy",
                            "Research - Legal",
                            "Research - General",
                            "Telephone Call",
                            "Trademark - Application/Filing",
                            "Trademark - Prosecution",
                            "Trademark - Search/Clearance"
                        ]
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                        onActivated: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: billInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Bill %"
                        text: "100"
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                        onTextChanged: {
                            root.calculateFees()
                            if (!root._hydrating) root.dirty = true
                        }
                    }

                    ModernTextField {
                        id: feesInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Total Fees"
                        text: "$0.00"
                        readOnly: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        Layout.preferredHeight: root.liveDocketFieldHeightPx
                    }

                    ScrollView {
                        id: descScroll
                        Layout.fillWidth: true
                        Layout.columnSpan: 12
                        Layout.minimumHeight: root.descriptionMinHeightPx()
                        Layout.preferredHeight: root.descriptionTargetHeightPx()
                        Layout.maximumHeight: root.descriptionMaxHeightPx()
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded

                        background: Rectangle {
                            color: root.isProMode
                                ? root.proSurface
                                : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72)
                            radius: root.sectionRadiusPx
                            border.width: descInput.activeFocus
                                ? Math.max(1, root.ratioPx(root.scaleRatios.descFocusBorderPct, 1))
                                : root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
                            border.color: descInput.activeFocus
                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.62)
                                : (root.isProMode
                                    ? root.proBorder
                                    : SemanticTheme.borderSubtle(root.t, root.appStyle))
                        }

                        TextArea {
                            id: descInput
                            width: descScroll.availableWidth
                            height: Math.max(descScroll.availableHeight, implicitHeight)
                            color: root.isProMode ? root.proInk : root._text
                            font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                            wrapMode: Text.Wrap
                            placeholderText: "Enter detailed description..."
                            placeholderTextColor: root.isProMode
                                ? root.proMutedInk
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.50)
                            leftPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            topPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            rightPadding: root.ratioPx(root.scaleRatios.descPadPct + 0.002, 10)
                            bottomPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            background: null
                            onTextChanged: if (!root._hydrating) root.dirty = true
                        }
                    }
                }

                FeeDocketEntryPanel {
                    id: feeDocketEntryPanel
                    visible: root.activeIsFeeDocket()
                    enabled: visible
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 16777215 : 0
                    t: root.t
                    metrics: root.responsiveMetrics
                    appRef: root.appRef
                    sfxBus: root.sfxBus
                    onSaved: function(result) {
                        root.dirty = false
                    }
                }

                BulkDocketMovePanel {
                    id: bulkDocketMovePanel
                    visible: root.activeIsBulkDocketMove()
                    enabled: visible
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 16777215 : 0
                    t: root.t
                    appRef: root.appRef
                    backend: (typeof docketApp !== "undefined") ? docketApp : ((root.appRef && root.appRef.docketing) ? root.appRef.docketing : null)
                    surfaceColor: root.isProMode ? root.proSurface : root._panel
                    canvasColor: root.isProMode ? root.proCanvas : root._bg
                    inputColor: root.isProMode ? root.proControl : root._panelBase
                    textColor: root.isProMode ? root.proInk : root._text
                    mutedColor: root.isProMode ? root.proMutedInk : root._mutedText
                    borderColor: root.isProMode ? root.proBorder : SemanticTheme.borderSubtle(root.t, root.appStyle)
                    accentColor: root.isProMode ? root.proActiveFill : root._accent
                    isDark: !root.lightTheme
                }

                Component {
                    id: docketActivityReportPanelComponent
                    DocketActivityReportPanel {
                        anchors.fill: parent
                        t: root.t
                        metrics: root.responsiveMetrics
                        appRef: root.appRef
                        windowRef: root.windowRef
                        sfxBus: root.sfxBus
                        sectionRadiusPx: root.sectionRadiusPx
                        fieldHeightPx: root.fieldHeightPx
                        autoLoadOnVisible: true
                        onEditRequested: function(row) {
                            root.openReportEntryForEdit(row)
                        }
                        onReportWindowRequested: function(reportDocument) {
                            root.reportWindowRequested(reportDocument)
                        }
                    }
                }

                Item {
                    id: docketActivityReportHost
                    visible: root.activeIsDocketReport()
                    enabled: visible
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 16777215 : 0

                    Loader {
                        id: docketActivityReportPanelLoader
                        anchors.fill: parent
                        active: false
                        asynchronous: true
                        sourceComponent: docketActivityReportPanelComponent
                        onStatusChanged: {
                            if (status !== Loader.Ready || !item) {
                                return
                            }
                            root.docketReportPanelLoadRequested = false
                            root.applyPendingDocketReportState()
                            var panel = root.docketActivityReportPanel
                            if (root.docketReportPanelPendingOpenReportWindow && panel && panel.openReportWindow) {
                                root.docketReportPanelPendingOpenReportWindow = false
                                root.docketReportPanelPendingRun = false
                                panel.openReportWindow(true)
                            } else if (root.docketReportPanelPendingRun && panel && panel.runReport) {
                                root.docketReportPanelPendingRun = false
                                panel.runReport(true)
                            }
                        }
                    }
                }

                Rectangle {
                    id: timerConsolePanel
                    visible: root.activeIsTimerConsole()
                    enabled: visible
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumHeight: visible ? 16777215 : 0
                    radius: root.sectionRadiusPx
                    color: root.isProMode
                        ? root.proCanvas
                        : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.78)
                    border.width: root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
                    border.color: root.isProMode
                        ? root.proBorder
                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.10, 10)
                        spacing: root.ratioPx(root.scaleRatios.pageSpacingPct * 0.58, 6)

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: root.ratioPx(0.008, 6)

                            Rectangle {
                                Layout.preferredHeight: root.fieldHeightPx
                                Layout.preferredWidth: root.moduleRatioPxW(0.120, 116, 240)
                                radius: root.isProMode ? root.proControlRadiusPx : height / 2
                                color: root.statusChipColor()
                                border.width: 1
                                border.color: Qt.rgba(1, 1, 1, 0.22)

                                Text {
                                    anchors.centerIn: parent
                                    text: root.normalizedDocketStatus(root.docketStatusText)
                                    color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                            }

                            Rectangle {
                                Layout.preferredHeight: root.fieldHeightPx
                                Layout.preferredWidth: root.moduleRatioPxW(0.120, 116, 240)
                                radius: root.isProMode ? root.proControlRadiusPx : height / 2
                                color: root.isRunning
                                    ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.28)
                                    : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72)
                                border.width: 1
                                border.color: root.isRunning
                                    ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.58)
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.20)

                                Text {
                                    anchors.centerIn: parent
                                    text: root.isRunning ? "Running" : "Paused"
                                    color: root.isRunning
                                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.98)
                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.92)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: root.timerLockNotice.length > 0
                                    ? root.timerLockNotice
                                    : ("Lock Owner: " + root.timerLockHolderDisplayText())
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.80)
                                font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 8))
                                wrapMode: Text.WordWrap
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ratioPxH(0.170, 140)
                            radius: root.sectionRadiusPx
                            color: root.isProMode
                                ? root.proSurface
                                : SemanticTheme.alpha(root._panel, 0.66)
                            border.width: 1
                            border.color: root.isRunning
                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.54)
                                : (root.isProMode
                                    ? root.proBorder
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16))

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(0.010, 10)
                                spacing: root.ratioPx(0.006, 4)

                                Text {
                                    Layout.fillWidth: true
                                    text: "Current Segment Timer"
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    horizontalAlignment: Text.AlignHCenter
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.92, root.metricFloor("fontFloorLabelPx", 8))
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: root.formatTimer(root.elapsedSeconds)
                                    color: root.isRunning
                                        ? root._accent
                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.96)
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: root.isProMode ? visualRules.textFontFamily : "Courier New"
                                    font.pixelSize: root.ratioPx(root.scaleRatios.timerFontPct * 1.55, root.metricFloor("fontFloorBodyPx", 22))
                                    font.weight: Font.Bold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Hours: " + root.formatHoursRounded(root.elapsedSeconds)
                                        + " | Unsaved: " + root.formatHoursRounded(root.unsavedTimerSeconds())
                                        + " | Entry: " + (root.lastSavedEntryId.length > 0 ? root.lastSavedEntryId : "[new]")
                                    color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.74)
                                    horizontalAlignment: Text.AlignHCenter
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.86, root.metricFloor("fontFloorLabelPx", 8))
                                    wrapMode: Text.WordWrap
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !root.isBucketLocked()
                                hoverEnabled: true
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.openTimerEditPopup()
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: root.ratioPx(0.007, 6)

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: root.isBucketLocked() ? "Locked" : (root.isRunning ? "Stop Timer" : "Start Timer")
                                primary: true
                                enabled: !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.122, 110, 240)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.toggleTimer()
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Save Checkpoint"
                                primary: true
                                enabled: !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.142, 126, 260)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.runTimerConsoleCheckpoint("")
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Reset Timer"
                                primary: false
                                enabled: !root.isBucketLocked() && (root.isRunning || root.elapsedSeconds > 0)
                                Layout.preferredWidth: root.moduleRatioPxW(0.132, 118, 250)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.resetDocketTimerToZero()
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Reset to Saved"
                                primary: false
                                enabled: !root.isRunning && !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.120, 112, 240)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.resetDocketTimerToZero()
                            }

                            Item { Layout.fillWidth: true }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Open Entry"
                                primary: false
                                Layout.preferredWidth: root.moduleRatioPxW(0.104, 98, 220)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.openTimeEntrySubwindow()
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: root.ratioPx(0.007, 6)

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "-30s"
                                primary: false
                                enabled: !root.isRunning && !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.072, 70, 160)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.quickAdjustTimerSeconds(-30)
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "+30s"
                                primary: false
                                enabled: !root.isRunning && !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.072, 70, 160)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.quickAdjustTimerSeconds(30)
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "-5m"
                                primary: false
                                enabled: !root.isRunning && !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.072, 70, 160)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.quickAdjustTimerSeconds(-300)
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "+5m"
                                primary: false
                                enabled: !root.isRunning && !root.isBucketLocked()
                                Layout.preferredWidth: root.moduleRatioPxW(0.072, 70, 160)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.quickAdjustTimerSeconds(300)
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "View Activity for This Matter / Day"
                                primary: false
                                Layout.preferredWidth: root.moduleRatioPxW(0.210, 190, 360)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.openDocketActivityReportForMatterDay()
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Open Report"
                                primary: false
                                Layout.preferredWidth: root.moduleRatioPxW(0.104, 98, 220)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.openDocketReportSubwindow()
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Switch Here"
                                primary: true
                                visible: String((root.timerLockHolder || ({})).ownerId || "").length > 0
                                    && String((root.timerLockHolder || ({})).ownerId || "") !== root.timerOwnerId
                                enabled: !root.isBucketLocked()
                                Layout.preferredWidth: visible ? root.moduleRatioPxW(0.108, 104, 220) : 0
                                Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                                onClicked: root.takeOverTimerHere()
                            }

                            Item { Layout.fillWidth: true }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: root.sectionRadiusPx
                            color: root.isProMode
                                ? root.proSurface
                                : SemanticTheme.alpha(root._panel, 0.66)
                            border.width: 1
                            border.color: root.isProMode
                                ? root.proBorder
                                : SemanticTheme.borderSubtle(root.t, root.appStyle)

                            GridLayout {
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(0.009, 8)
                                columns: 2
                                rowSpacing: root.ratioPx(0.004, 3)
                                columnSpacing: root.ratioPx(0.010, 8)

                                Text {
                                    Layout.fillWidth: true
                                    text: "Date: " + String(dateInput.text || "")
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Client: " + (String(clientCombo.editText || "").trim().length > 0 ? String(clientCombo.editText || "") : "[select in entry]")
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Matter: " + (String(matterCombo.editText || "").trim().length > 0 ? String(matterCombo.editText || "") : "[none]")
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Task: " + (String(taskCombo.editText || "").trim().length > 0 ? String(taskCombo.editText || "") : "[none]")
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Rate / Bill: $" + String(rateInput.text || "0.00") + " @ " + String(billInput.text || "100") + "%"
                                    color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.80)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.84, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Total Fees: " + String(feesInput.text || "$0.00")
                                    color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.80)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.84, root.metricFloor("fontFloorLabelPx", 8))
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                // trademark subwindow loader
                Rectangle {
                    id: trademarkPanel
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 16777215 : 0
                    visible: root.activeIsTrademark()
                    enabled: visible
                    radius: root.sectionRadiusPx
                    color: root.isProMode
                        ? root.proCanvas
                        : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.86)
                    border.width: root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
                    border.color: root.isProMode
                        ? root.proBorder
                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.10)

                    Loader {
                        id: trademarkLoader
                        anchors.fill: parent
                        active: trademarkPanel.visible
                        source: root.activeIsTrademarkDirectory()
                            ? Qt.resolvedUrl("TrademarkDirectoryView.qml")
                            : Qt.resolvedUrl("TrademarkFilingView.qml")
                        onStatusChanged: {
                            if (status !== Loader.Ready && root.activeIsTrademarkEntry()) {
                                root.trademarkFormDirty = false
                            }
                            if (status === Loader.Error) {
                                console.error("Failed to load trademark view", source, item, status, trademarkLoader.errorString)
                            }
                        }
                        onLoaded: {
                            if (!item) {
                                console.warn("Trademark loader status Ready but no item created")
                                return
                            }

                            if (root.appRef) item.appRef = root.appRef
                            if (root.metrics) item.metrics = root.metrics
                            if (root.t) item.t = root.t
                            if (item.moduleJumpRequested && item.moduleJumpRequested.connect) {
                                item.moduleJumpRequested.connect(root.moduleJumpRequested)
                            }

                            if (root.activeIsTrademarkDirectory()) {
                                if (root.td_state && item.applyInitialState) {
                                    item.applyInitialState(root.td_state)
                                }
                                root.trademarkFormDirty = false
                            } else {
                                if (root.tf_state && item.applyInitialState) {
                                    item.applyInitialState(root.tf_state)
                                }
                                root.trademarkFormDirty = !!item.dirty
                            }

                            if (root.activeIsTrademark() && !root._hydrating) {
                                root.dirty = root.formHasContent()
                            }
                        }

                        Connections {
                            target: trademarkLoader.item
                            ignoreUnknownSignals: true
                            function onDirtyChanged() {
                                if (root.activeIsTrademarkEntry() && trademarkLoader.item) {
                                    root.trademarkFormDirty = !!trademarkLoader.item.dirty
                                } else {
                                    root.trademarkFormDirty = false
                                }
                                if (root.activeIsTrademark() && !root._hydrating) {
                                    root.dirty = root.formHasContent()
                                }
                            }

                            function onEditTrademarkRequested(row) {
                                var selected = row || ({})
                                if (trademarkLoader.item && trademarkLoader.item.snapshotState) {
                                    root.td_state = trademarkLoader.item.snapshotState()
                                }
                                root.tf_state = {
                                    "form": selected,
                                    "dirty": false,
                                    "saveMessage": "",
                                    "lastSavedTrademarkId": String(selected.trademarkId || "")
                                }
                                root.trademarkFormDirty = false
                                root.activeSubwindowId = "B16"
                                root.ensureActiveSubwindow()
                                if (!root._hydrating) root.dirty = false
                            }

                            function onCreateTrademarkRequested() {
                                if (trademarkLoader.item && trademarkLoader.item.snapshotState) {
                                    root.td_state = trademarkLoader.item.snapshotState()
                                }
                                root.tf_state = {
                                    "form": ({ "jurisdiction": "CIPO" }),
                                    "dirty": false,
                                    "saveMessage": "",
                                    "lastSavedTrademarkId": ""
                                }
                                root.trademarkFormDirty = false
                                root.activeSubwindowId = "B16"
                                root.ensureActiveSubwindow()
                                if (!root._hydrating) root.dirty = false
                            }
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: trademarkLoader.status === Loader.Error
                        color: "red"
                        text: "(Unable to load trademark view)"
                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, 10)
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: trademarkLoader.status === Loader.Ready && !trademarkLoader.item
                        color: "orange"
                        text: "(trademark view not available)"
                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, 10)
                    }

                    Connections {
                        target: trademarkPanel
                        function onVisibleChanged() {
                            if (!visible && trademarkLoader.item && trademarkLoader.item.snapshotState) {
                                var snap = trademarkLoader.item.snapshotState()
                                if (snap && snap.form !== undefined) {
                                    root.tf_state = snap
                                    root.trademarkFormDirty = !!root.tf_state.dirty
                                } else {
                                    root.td_state = snap || ({})
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 16777215 : 0
                    visible: !root.activeIsLiveDocket() && !root.activeIsFeeDocket() && !root.activeIsBulkDocketMove() && !root.activeIsTimerConsole() && !root.activeIsDocketReport() && !root.activeIsTrademark()
                    enabled: visible
                    radius: root.activeIsDeadlineEditor() ? 0 : root.sectionRadiusPx
                    color: root.activeIsDeadlineEditor()
                        ? "transparent"
                        : (root.isProMode
                            ? root.proCanvas
                            : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.80))
                    border.width: root.activeIsDeadlineEditor() ? 0 : root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
                    border.color: root.activeIsDeadlineEditor()
                        ? "transparent"
                        : (root.isProMode
                            ? root.proBorder
                            : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16))

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.2, 10)
                        spacing: root.ratioPx(root.scaleRatios.tipSpacingPct, 4)

                        Text {
                            Layout.fillWidth: true
                            visible: !root.activeIsDeadlineCalendar() && !root.activeIsDeadlineEditor()
                            text: "Placeholder Mode - " + String(root.currentNavNode().title || "")
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.96)
                            font.pixelSize: root.ratioPx(root.scaleRatios.headerSubtitleFontPct * 1.06, root.metricFloor("fontFloorLabelPx", 10))
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: !root.activeIsDeadlineCalendar() && !root.activeIsDeadlineEditor()
                            text: (root.laneSummary && root.laneSummary.lineA)
                                ? String(root.laneSummary.lineA)
                                : "This sub-window is scaffolded for full workflow wiring."
                            color: root._mutedText
                            wrapMode: Text.WordWrap
                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.92, root.metricFloor("fontFloorBodyPx", 10))
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: !root.activeIsDeadlineCalendar() && !root.activeIsDeadlineEditor()
                            text: (root.laneSummary && root.laneSummary.lineB)
                                ? String(root.laneSummary.lineB)
                                : "Use omni-search or quick-actions to route directly to this node."
                            color: root._subtleText
                            wrapMode: Text.WordWrap
                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.88, root.metricFloor("fontFloorBodyPx", 9))
                        }

                        Loader {
                            id: deadlineCalendarLoader
                            active: false
                            sourceComponent: Component {
                                JellyCalendar {
                                    visible: false
                                    id: deadlineCalendar
                                    t: root.t
                                    hostWindow: root.Window.window ? root.Window.window : root.windowRef
                                    onDatePicked: function(date) {
                                        if (root.deadlineDatePickerTarget === "range-start") {
                                            root.setDeadlineRange(date, root.deadlineRangeEndDate)
                                        } else if (root.deadlineDatePickerTarget === "range-end") {
                                            root.setDeadlineRange(root.deadlineRangeStartDate, date)
                                        } else if (root.deadlineDatePickerTarget === "editor-date" || root.activeIsDeadlineEditor()) {
                                            root.editingDeadline.date = root._formatDate(date)
                                            if (deadlineEditorDateField && !deadlineEditorDateField.activeFocus) {
                                                deadlineEditorDateField.text = String(root.editingDeadline.date || "")
                                            }
                                        } else {
                                            root.selectCalendarDate(date)
                                        }
                                        root.deadlineDatePickerTarget = ""
                                    }
                                }
                            }
                        }

                        Item {
                            id: deadlineCalendarPane
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: root.activeIsDeadlineCalendar()

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: root.ratioPx(root.scaleRatios.panelSpacingPct, 6)

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: root.ratioPx(root.scaleRatios.panelSpacingPct, 6)

                                    PillButton {
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        sfxBus: root.sfxBus
                                        text: "Add Deadline"
                                        primary: true
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.12, 132, 240)
                                        onClicked: root.startEditing(null, true)
                                    }

                                    PillButton {
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        sfxBus: root.sfxBus
                                        text: "Edit Selected"
                                        primary: false
                                        enabled: !!root.selectedCalendarEntry()
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.12, 132, 240)
                                        onClicked: root.editSelectedFromCalendar()
                                    }

                                    PillButton {
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        sfxBus: root.sfxBus
                                        text: "This Week"
                                        primary: false
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 220)
                                        onClicked: root.setDeadlineRangeDefaultWeek()
                                    }

                                    PillButton {
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        sfxBus: root.sfxBus
                                        text: "All Time"
                                        primary: false
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 220)
                                        onClicked: root.setDeadlineRangeAllTime()
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: String(root.calendarEntries.length) + " deadlines shown"
                                        color: root._mutedText
                                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 1.02, root.metricFloor("fontFloorBodyPx", 10))
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: root.ratioPx(root.scaleRatios.panelSpacingPct, 6)

                                    ModernTextField {
                                        id: deadlineRangeFromField
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "From"
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 188)
                                        text: ""
                                        Component.onCompleted: text = root._formatDate(root.deadlineRangeStartDate)
                                        onTextEdited: {
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.setDeadlineRange(root._parseDate(entered), root.deadlineRangeEndDate)
                                            }
                                        }
                                        onActiveFocusChanged: {
                                            if (activeFocus) return
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.setDeadlineRange(root._parseDate(entered), root.deadlineRangeEndDate)
                                            } else {
                                                text = root._formatDate(root.deadlineRangeStartDate)
                                            }
                                        }

                                        TapHandler {
                                            acceptedButtons: Qt.LeftButton
                                            onDoubleTapped: {
                                                root.openDeadlineDatePicker("range-start", root.deadlineRangeStartDate, deadlineRangeFromField)
                                            }
                                        }
                                    }

                                    ModernTextField {
                                        id: deadlineRangeToField
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "To"
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 188)
                                        text: ""
                                        Component.onCompleted: text = root._formatDate(root.deadlineRangeEndDate)
                                        onTextEdited: {
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.setDeadlineRange(root.deadlineRangeStartDate, root._parseDate(entered))
                                            }
                                        }
                                        onActiveFocusChanged: {
                                            if (activeFocus) return
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.setDeadlineRange(root.deadlineRangeStartDate, root._parseDate(entered))
                                            } else {
                                                text = root._formatDate(root.deadlineRangeEndDate)
                                            }
                                        }

                                        TapHandler {
                                            acceptedButtons: Qt.LeftButton
                                            onDoubleTapped: {
                                                root.openDeadlineDatePicker("range-end", root.deadlineRangeEndDate, deadlineRangeToField)
                                            }
                                        }
                                    }

                                    ModernComboBox {
                                        id: deadlineMatterFilterCombo
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "Matter"
                                        editable: false
                                        fullModel: root.deadlineMatterFilterOptions
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.15, 170, 320)
                                        editText: root.deadlineFilterMatter
                                        onActivated: {
                                            var picked = String(editText || "").trim()
                                            root.setDeadlineMatterFilter(picked, true)
                                        }
                                    }

                                    ModernComboBox {
                                        id: deadlineClientFilterCombo
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "Client"
                                        editable: false
                                        fullModel: root.deadlineClientOptions
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Layout.preferredWidth: root.moduleRatioPxW(0.15, 170, 320)
                                        editText: root.deadlineFilterClient
                                        onActivated: {
                                            var picked = String(editText || "").trim()
                                            root.setDeadlineClientFilter(picked, true)
                                        }
                                    }

                                    Item { Layout.fillWidth: true }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: root.ratioPx(root.scaleRatios.panelSpacingPct, 8)

                                    Text {
                                        text: "Show:"
                                        color: root._mutedText
                                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.95, root.metricFloor("fontFloorBodyPx", 10))
                                        verticalAlignment: Text.AlignVCenter
                                        Layout.alignment: Qt.AlignVCenter
                                    }

                                    CheckBox {
                                        id: deadlineActionableOnlyCheck
                                        text: "Actionable Only"
                                        checked: root.deadlineFilterActionableOnly
                                        spacing: root.ratioPx(0.004, 4)
                                        Layout.preferredWidth: implicitWidth
                                        onToggled: root.setDeadlineActionableOnly(checked, true)

                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: deadlineActionableOnlyCheck.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: 3
                                            color: deadlineActionableOnlyCheck.checked ? root._accent : root.proControl
                                            border.width: 1
                                            border.color: deadlineActionableOnlyCheck.checked ? root._accent : root.proActiveBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: deadlineActionableOnlyCheck.checked ? "\u2713" : ""
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }

                                        contentItem: Text {
                                            text: deadlineActionableOnlyCheck.text
                                            color: root._text
                                            font: deadlineActionableOnlyCheck.font
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: deadlineActionableOnlyCheck.indicator.width + deadlineActionableOnlyCheck.spacing
                                        }
                                    }

                                    CheckBox {
                                        id: deadlineOpenCheck
                                        text: "Open"
                                        checked: root.deadlineFilterShowOpen
                                        spacing: root.ratioPx(0.004, 4)
                                        Layout.preferredWidth: implicitWidth
                                        onToggled: root.setDeadlineStatusFilter("open", checked, true)

                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: deadlineOpenCheck.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: 3
                                            color: deadlineOpenCheck.checked ? root._accent : root.proControl
                                            border.width: 1
                                            border.color: deadlineOpenCheck.checked ? root._accent : root.proActiveBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: deadlineOpenCheck.checked ? "\u2713" : ""
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }

                                        contentItem: Text {
                                            text: deadlineOpenCheck.text
                                            color: root._text
                                            font: deadlineOpenCheck.font
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: deadlineOpenCheck.indicator.width + deadlineOpenCheck.spacing
                                        }
                                    }

                                    CheckBox {
                                        id: deadlineCompletedCheck
                                        text: "Completed"
                                        checked: root.deadlineFilterShowCompleted
                                        spacing: root.ratioPx(0.004, 4)
                                        Layout.preferredWidth: implicitWidth
                                        onToggled: root.setDeadlineStatusFilter("completed", checked, true)

                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: deadlineCompletedCheck.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: 3
                                            color: deadlineCompletedCheck.checked ? root._accent : root.proControl
                                            border.width: 1
                                            border.color: deadlineCompletedCheck.checked ? root._accent : root.proActiveBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: deadlineCompletedCheck.checked ? "\u2713" : ""
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }

                                        contentItem: Text {
                                            text: deadlineCompletedCheck.text
                                            color: root._text
                                            font: deadlineCompletedCheck.font
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: deadlineCompletedCheck.indicator.width + deadlineCompletedCheck.spacing
                                        }
                                    }

                                    CheckBox {
                                        id: deadlineInformationCheck
                                        text: "Information Only"
                                        checked: root.deadlineFilterShowInformationOnly
                                        enabled: !root.deadlineFilterActionableOnly
                                        spacing: root.ratioPx(0.004, 4)
                                        Layout.preferredWidth: implicitWidth
                                        onToggled: root.setDeadlineStatusFilter("information", checked, true)

                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: deadlineInformationCheck.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: 3
                                            color: deadlineInformationCheck.checked ? root._accent : root.proControl
                                            border.width: 1
                                            border.color: deadlineInformationCheck.checked ? root._accent : root.proActiveBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: deadlineInformationCheck.checked ? "\u2713" : ""
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }

                                        contentItem: Text {
                                            text: deadlineInformationCheck.text
                                            color: root._text
                                            font: deadlineInformationCheck.font
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: deadlineInformationCheck.indicator.width + deadlineInformationCheck.spacing
                                        }
                                    }

                                    CheckBox {
                                        id: deadlineTasksCheck
                                        text: "Tasks"
                                        checked: root.deadlineFilterShowTasks
                                        spacing: root.ratioPx(0.004, 4)
                                        Layout.preferredWidth: implicitWidth
                                        onToggled: root.setDeadlineStatusFilter("tasks", checked, true)

                                        indicator: Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            x: deadlineTasksCheck.leftPadding
                                            y: parent.height / 2 - height / 2
                                            radius: 3
                                            color: deadlineTasksCheck.checked ? root._accent : root.proControl
                                            border.width: 1
                                            border.color: deadlineTasksCheck.checked ? root._accent : root.proActiveBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: deadlineTasksCheck.checked ? "\u2713" : ""
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }

                                        contentItem: Text {
                                            text: deadlineTasksCheck.text
                                            color: root._text
                                            font: deadlineTasksCheck.font
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: deadlineTasksCheck.indicator.width + deadlineTasksCheck.spacing
                                        }
                                    }

                                    Item { Layout.fillWidth: true }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: root.sectionRadiusPx
                                    color: Qt.rgba(root._panelBase.r, root._panelBase.g, root._panelBase.b, root.lightTheme ? 0.94 : 0.88)
                                    border.width: 1
                                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.24)

                                    ListView {
                                        id: deadlineCalendarList
                                        anchors.fill: parent
                                        anchors.margins: root.ratioPx(0.004, 4)
                                        clip: true
                                        spacing: root.ratioPx(0.003, 2)
                                        model: root.calendarEntries

                                        delegate: Rectangle {
                                            id: entryRow
                                            required property int index
                                            readonly property var entryData: (index >= 0 && index < root.calendarEntries.length)
                                                ? root.calendarEntries[index]
                                                : null
                                            property bool selected: String((entryRow.entryData && entryRow.entryData.id) || "") === String(root.selectedCalendarEntryId || "")
                                            property bool hovered: rowHit.containsMouse
                                            width: ListView.view ? ListView.view.width : 0
                                            height: root.ratioPxH(0.088, 72)
                                            radius: root.isProMode
                                                ? root.proControlRadiusPx
                                                : root.ratioPx(0.006, 6)
                                            color: selected
                                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, root.lightTheme ? 0.18 : 0.26)
                                                : (hovered
                                                    ? Qt.rgba(root._panel.r, root._panel.g, root._panel.b, root.lightTheme ? 0.96 : 0.86)
                                                    : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, root.lightTheme ? 0.92 : 0.78))
                                            border.width: 1
                                            border.color: selected
                                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.82)
                                                : Qt.rgba(root._text.r, root._text.g, root._text.b, hovered ? 0.28 : 0.20)

                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: root.ratioPx(0.008, 8)
                                                anchors.rightMargin: root.ratioPx(0.008, 8)
                                                spacing: root.ratioPx(0.003, 2)

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: root.ratioPx(0.008, 8)

                                                    Text {
                                                        text: String((entryRow.entryData && entryRow.entryData.date) || "").trim().length > 0
                                                            ? String(entryRow.entryData.date)
                                                            : "No date"
                                                        color: root._text
                                                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 1.04, root.metricFloor("fontFloorBodyPx", 11))
                                                        font.weight: Font.DemiBold
                                                    }

                                                    Text {
                                                        text: {
                                                            var assignment = String((entryRow.entryData && entryRow.entryData.assignmentType) || "").toLowerCase()
                                                            var matterText = assignment === "matter"
                                                                ? ("Matter: " + String((entryRow.entryData && entryRow.entryData.matterName) || ""))
                                                                : "General"
                                                            var clientText = root._deadlineEntryClientName(entryRow.entryData)
                                                            if (clientText.length > 0) return "Client: " + clientText + " | " + matterText
                                                            return matterText === "General" ? "Non-client related" : matterText
                                                        }
                                                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, root.lightTheme ? 0.82 : 0.92)
                                                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.96, root.metricFloor("fontFloorBodyPx", 10))
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }

                                                    Rectangle {
                                                        visible: root._deadlineIsInformationOnly(entryRow.entryData)
                                                        radius: root.isProMode ? root.proControlRadiusPx : height / 2
                                                        color: root.deadlineTagFill("info")
                                                        implicitHeight: root.ratioPxH(0.030, 22)
                                                        implicitWidth: infoTagText.implicitWidth + root.ratioPx(0.014, 16)

                                                        Text {
                                                            id: infoTagText
                                                            anchors.centerIn: parent
                                                            text: "Information Only"
                                                            color: root.deadlineTagText("info")
                                                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }

                                                    Rectangle {
                                                        visible: Boolean(entryRow.entryData && entryRow.entryData.completed)
                                                        radius: root.isProMode ? root.proControlRadiusPx : height / 2
                                                        color: root.deadlineTagFill("completed")
                                                        implicitHeight: root.ratioPxH(0.030, 22)
                                                        implicitWidth: completedTagText.implicitWidth + root.ratioPx(0.014, 16)

                                                        Text {
                                                            id: completedTagText
                                                            anchors.centerIn: parent
                                                            text: "Completed"
                                                            color: root.deadlineTagText("completed")
                                                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }

                                                    Rectangle {
                                                        visible: Boolean(entryRow.entryData && entryRow.entryData.escalated)
                                                        radius: root.isProMode ? root.proControlRadiusPx : height / 2
                                                        color: root.deadlineTagFill("escalated")
                                                        implicitHeight: root.ratioPxH(0.030, 22)
                                                        implicitWidth: escalatedTagText.implicitWidth + root.ratioPx(0.014, 16)

                                                        Text {
                                                            id: escalatedTagText
                                                            anchors.centerIn: parent
                                                            text: "Escalated"
                                                            color: root.deadlineTagText("escalated")
                                                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.86, root.metricFloor("fontFloorBodyPx", 9))
                                                            font.weight: Font.DemiBold
                                                        }
                                                    }
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: String((entryRow.entryData && entryRow.entryData.description) || "").trim().length > 0
                                                        ? String(entryRow.entryData.description)
                                                        : "No description"
                                                    color: Boolean(entryRow.entryData && entryRow.entryData.completed)
                                                        ? Qt.rgba(root._text.r, root._text.g, root._text.b, root.lightTheme ? 0.70 : 0.80)
                                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.98)
                                                    elide: Text.ElideRight
                                                    font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 1.02, root.metricFloor("fontFloorBodyPx", 11))
                                                }
                                            }

                                            MouseArea {
                                                id: rowHit
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.selectedCalendarEntryId = String((entryRow.entryData && entryRow.entryData.id) || "")
                                                onDoubleClicked: root.startEditing(entryRow.entryData, true)
                                            }
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: root.calendarEntries.length <= 0
                                        text: "No deadlines match the selected range/filters."
                                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.64)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, root.metricFloor("fontFloorLabelPx", 9))
                                    }
                                }
                            }
                        }

                        Item {
                            id: deadlineEditorPane
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: root.activeIsDeadlineEditor()

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 0

                                // ── Header bar ──
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.ratioPxH(0.055, 44)
                                    radius: root.isProMode ? root.proControlRadiusPx : root.ratioPx(0.008, 7)
                                    color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, root.lightTheme ? 0.10 : 0.18)

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: root.ratioPx(0.012, 12)
                                        anchors.rightMargin: root.ratioPx(0.008, 8)
                                        spacing: root.ratioPx(0.008, 8)

                                        Text {
                                            Layout.fillWidth: true
                                            text: (root.editingDeadline && String(root.editingDeadline.id || "").length > 0)
                                                ? "\u270E  Editing Deadline"
                                                : "\u2795  New Deadline"
                                            color: root._text
                                            font.pixelSize: root.ratioPx(root.scaleRatios.headerSubtitleFontPct, root.metricFloor("fontFloorTitlePx", 13))
                                            font.weight: Font.Bold
                                            verticalAlignment: Text.AlignVCenter
                                        }

                                        PillButton {
                                            t: root.t
                                            metrics: root.responsiveMetrics
                                            sfxBus: root.sfxBus
                                            text: "\u2190 Back to Calendar"
                                            primary: false
                                            Layout.preferredHeight: root.ratioPxH(0.038, 30)
                                            Layout.preferredWidth: root.moduleRatioPxW(0.13, 150, 260)
                                            onClicked: {
                                                root.pendingBriefingDeadlineId = ""
                                                root.pendingBriefingCalendarDate = ""
                                                root.activeSubwindowId = "B07"
                                                root.ensureActiveSubwindow()
                                            }
                                        }
                                    }
                                }

                                Item { Layout.preferredHeight: root.ratioPx(0.010, 10) }

                                // ── Form fields ──
                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: false
                                    Layout.alignment: Qt.AlignTop
                                    columns: 12
                                    columnSpacing: 14
                                    rowSpacing: 8

                                    // Date field
                                    ModernTextField {
                                        id: deadlineEditorDateField
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "Deadline Date"
                                        datePickerEnabled: true
                                        Layout.fillWidth: true
                                        Layout.columnSpan: 4
                                        Layout.preferredHeight: root.fieldHeightPx
                                        text: ""
                                        Component.onCompleted: text = String(root.editingDeadline.date || root._formatDate(new Date()))
                                        onTextEdited: {
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.editingDeadline.date = root._formatDate(root._parseDate(entered))
                                            }
                                        }
                                        onActiveFocusChanged: {
                                            if (activeFocus) return
                                            var entered = String(text || "").trim()
                                            if (root._looksIsoDate(entered)) {
                                                root.editingDeadline.date = root._formatDate(root._parseDate(entered))
                                            } else {
                                                text = String(root.editingDeadline.date || root._formatDate(new Date()))
                                            }
                                        }

                                        TapHandler {
                                            acceptedButtons: Qt.LeftButton
                                            onDoubleTapped: {
                                                root.openDeadlineDatePicker("editor-date", root.editingDeadline.date, deadlineEditorDateField)
                                            }
                                        }
                                    }

                                    // Assign To combo
                                    ModernComboBox {
                                        id: deadlineAssignmentCombo
                                        t: root.t
                                        metrics: root.responsiveMetrics
                                        label: "Assign To (Matter or General)"
                                        editable: false
                                        fullModel: root.deadlineMatterOptions
                                        Layout.fillWidth: true
                                        Layout.columnSpan: 8
                                        Layout.preferredHeight: root.fieldHeightPx
                                        Component.onCompleted: root.refreshDeadlineMatterOptions()
                                        onActiveFocusChanged: if (activeFocus) root.refreshDeadlineMatterOptions()
                                        editText: root._deadlineEditingMatterDisplayName()
                                        onEditTextChanged: {
                                            var picked = String(editText || "").trim()
                                            if (picked.toLowerCase() === "general" || picked.length <= 0) {
                                                root.editingDeadline.assignmentType = "General"
                                                root.editingDeadline.matterId = ""
                                                root.editingDeadline.matterName = ""
                                                return
                                            }
                                            root.editingDeadline.assignmentType = "Matter"
                                            var row = root._deadlineMatterRecordByName(picked)
                                            root.editingDeadline.matterId = row ? String(row.matterId || "") : ""
                                            root.editingDeadline.matterName = row ? String(row.matterName || picked) : picked
                                        }
                                        onActivated: {
                                            var picked = String(editText || "").trim()
                                            if (picked.toLowerCase() === "general" || picked.length <= 0) {
                                                root.editingDeadline.assignmentType = "General"
                                                root.editingDeadline.matterId = ""
                                                root.editingDeadline.matterName = ""
                                                return
                                            }
                                            root.editingDeadline.assignmentType = "Matter"
                                            var row = root._deadlineMatterRecordByName(picked)
                                            root.editingDeadline.matterId = row ? String(row.matterId || "") : ""
                                            root.editingDeadline.matterName = row ? String(row.matterName || picked) : picked
                                        }
                                    }
                                }

                                Item { Layout.preferredHeight: root.ratioPx(0.006, 6) }

                                // ── Description area ──
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.minimumHeight: root.ratioPxH(0.18, 140)
                                    radius: root.isProMode ? root.proControlRadiusPx : root.ratioPx(0.008, 7)
                                    color: Qt.rgba(root._panelBase.r, root._panelBase.g, root._panelBase.b, root.lightTheme ? 0.60 : 0.40)
                                    border.width: 1
                                    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: root.ratioPx(0.010, 10)
                                        spacing: root.ratioPx(0.004, 4)

                                        Text {
                                            text: "Description"
                                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.90, root.metricFloor("fontFloorLabelPx", 9))
                                            font.weight: Font.DemiBold
                                            Layout.fillWidth: true
                                        }

                                        TextArea {
                                            id: deadlineEditorDescription
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            wrapMode: Text.WordWrap
                                            selectByMouse: true
                                            text: String(root.editingDeadline.description || "")
                                            color: root._text
                                            font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 1.08, root.metricFloor("fontFloorBodyPx", 12))
                                            placeholderText: "Describe the deadline, required action, and any notes…"
                                            placeholderTextColor: SemanticTheme.alpha(root._text, 0.36)
                                            onTextChanged: root.editingDeadline.description = text
                                            background: Rectangle {
                                                color: "transparent"
                                            }
                                        }
                                    }
                                }

                            }
                        }

                        // placeholder for other nodes
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: !root.activeIsDeadlineCalendar() && !root.activeIsDeadlineEditor()
                            radius: root.sectionRadiusPx
                            color: SemanticTheme.alpha(root._panel, 0.66)
                            border.width: 1
                            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                            Text {
                                anchors.centerIn: parent
                                width: parent.width - root.ratioPx(0.02, 16)
                                text: "Workflow placeholders are active for this Docketing & Deadlines node. Data schema and action handlers can be wired incrementally."
                                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                    Layout.maximumHeight: visible ? root.fieldHeightPx : 0
                    visible: (root.activeIsLiveDocket()
                        || root.activeIsTimerConsole()
                        || root.activeIsDeadlineCalendar()
                        || root.activeIsDeadlineEditor())
                        && String(root.saveFeedbackText || "").length > 0
                    radius: root.sectionRadiusPx
                    color: root.saveFeedbackIsError
                        ? SemanticTheme.tone(root.t, "error", root.appStyle)
                        : SemanticTheme.tone(root.t, "success", root.appStyle)
                    border.width: 1
                    border.color: root.saveFeedbackIsError
                        ? SemanticTheme.border(root.t, "error", "Professional")
                        : SemanticTheme.border(root.t, "success", "Professional")

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: root.ratioPx(0.010, 10)
                        anchors.rightMargin: root.ratioPx(0.010, 10)
                        verticalAlignment: Text.AlignVCenter
                        text: String(root.saveFeedbackText || "")
                        color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct * 0.96, root.metricFloor("fontFloorLabelPx", 9))
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.preferredHeight: 40
                    visible: root.activeIsLiveDocket()
                    enabled: visible
                    spacing: 10

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Set Draft"
                        primary: false
                        enabled: root.canSetDraft()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 72, 200)
                        Layout.preferredHeight: 44
                        onClicked: root.setDraftStatus()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Mark Ready"
                        primary: false
                        enabled: root.canMarkReadyForBilling()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.saveBtnWidthPct, 94, 220)
                        Layout.preferredHeight: 44
                        onClicked: root.markReadyForBilling()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Mark Billed"
                        primary: true
                        enabled: root.canMarkBilled()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.saveBtnWidthPct, 94, 220)
                        Layout.preferredHeight: 44
                        onClicked: root.markBilled()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Unlink Invoice"
                        primary: false
                        visible: root.lastSavedEntryId.length > 0 && root.isBucketLocked()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.saveBtnWidthPct, 94, 220)
                        Layout.preferredHeight: 44
                        onClicked: unlinkInvoiceConfirmationPopup.open()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Delete"
                        primary: false
                        visible: root.lastSavedEntryId.length > 0 && !root.isBucketLocked()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 70, 200)
                        Layout.preferredHeight: 44
                        onClicked: deleteConfirmationPopup.open()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Recent Entries"
                        primary: false
                        Layout.preferredWidth: 120
                        Layout.preferredHeight: 44
                        onClicked: {
                            if (root.appRef && root.appRef.docketing) {
                                var resString = root.appRef.docketing.getDocketEntriesSync({
                                    "fromDate": dateInput.text,
                                    "toDate": dateInput.text,
                                    "statusMode": "all"
                                })
                                
                                var safeModel = []
                                try {
                                    var res = JSON.parse(resString)
                                    if (res && res.length) {
                                        for (var i = 0; i < res.length; i++) {
                                            var it = res[i]
                                            safeModel.push({
                                                clientName: String(it.clientName || it.ClientName || it.ClientID || ""),
                                                matterName: String(it.matterName || it.MatterName || it.MatterID || ""),
                                                hours: String(it.hours || it.Hours || "0"),
                                                Description: String(it.Description || it.description || ""),
                                                description: String(it.description || it.Description || ""),
                                                date: String(it.date || it.Date || ""),
                                                rate: Number(it.rate || it.ClientRate || 0),
                                                sharePct: Number(it.sharePct || it.SharePct || 100),
                                                rawSeconds: Number(it.rawSeconds || it.RawSeconds || 0),
                                                status: String(it.status || it.Status || ""),
                                                entryId: String(it.entryId || it.EntryID || "")
                                            })
                                        }
                                    }
                                } catch (e) {
                                    console.error("Failed to parse recent entries JSON:", e)
                                }
                                
                                root.recentDocketsModel = safeModel
                                if (safeModel.length > 0) {
                                    recentDocketsPopup.open()
                                } else {
                                    if (typeof appToast === 'function') {
                                        appToast("No recent entries found for " + dateInput.text)
                                    } else {
                                        recentDocketsPopup.open()
                                    }
                                }
                            }
                        }
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "+ New Entry"
                        primary: false
                        Layout.preferredWidth: 100
                        Layout.preferredHeight: 44
                        onClicked: root.clearDocketForm()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Save Docket"
                        primary: true
                        enabled: !root.isBucketLocked()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.saveBtnWidthPct, 90, 220)
                        Layout.preferredHeight: 44
                        onClicked: root.requestSaveToDatabaseIfNeeded("manual-save")
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Close" : "Cancel"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 70, 200)
                        Layout.preferredHeight: 44
                        onClicked: root.returnToCallerOrClose()
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.moduleRatioPxW(
                                root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct,
                                138,
                                240
                            )
                            : 0
                        Layout.preferredHeight: 44
                        onClicked: root.detachRequested(root.snapshotState())
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: root.fieldHeightPx
                    visible: root.activeIsTimerConsole()
                    enabled: visible
                    spacing: root.ratioPx(root.scaleRatios.footerSpacingPct, 8)

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.isRunning ? "Stop Timer" : "Start Timer"
                        primary: true
                        enabled: !root.isBucketLocked()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.startBtnWidthPct, 98, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.toggleTimer()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Save Checkpoint"
                        primary: true
                        enabled: !root.isBucketLocked()
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.saveBtnWidthPct, 108, 240)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.runTimerConsoleCheckpoint("")
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Open Entry"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 90, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.openTimeEntrySubwindow()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Open Report"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 94, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.openDocketReportSubwindow()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Close" : "Cancel"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 72, 200)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.returnToCallerOrClose()
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.moduleRatioPxW(
                                root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct,
                                138,
                                240
                            )
                            : 0
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.detachRequested(root.snapshotState())
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: root.fieldHeightPx
                    visible: root.activeIsDocketReport()
                    enabled: visible
                    spacing: root.ratioPx(root.scaleRatios.footerSpacingPct, 8)

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Close" : "Cancel"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 72, 200)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.returnToCallerOrClose()
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.moduleRatioPxW(
                                root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct,
                                138,
                                240
                            )
                            : 0
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.detachRequested(root.snapshotState())
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: root.fieldHeightPx
                    visible: root.activeIsDeadlineCalendar()
                    enabled: visible
                    spacing: root.ratioPx(root.scaleRatios.footerSpacingPct, 8)

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Close" : "Cancel"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 72, 200)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.returnRequested(root.snapshotState())
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.moduleRatioPxW(
                                root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct,
                                138,
                                240
                            )
                            : 0
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.detachRequested(root.snapshotState())
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: root.fieldHeightPx
                    visible: root.activeIsDeadlineEditor()
                    enabled: visible
                    spacing: root.ratioPx(root.scaleRatios.footerSpacingPct, 8)

                    Text {
                        text: "Status: "
                              + (Boolean(root.editingDeadline && root.editingDeadline.completed) ? "Completed" : "Open")
                              + (Boolean(root.editingDeadline && root.editingDeadline.escalated) ? " | Escalated" : "")
                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        font.pixelSize: root.ratioPx(root.scaleRatios.tipFontPct, root.metricFloor("fontFloorLabelPx", 9))
                        font.weight: Font.DemiBold
                        verticalAlignment: Text.AlignVCenter
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Snooze +1 Day"
                        primary: false
                        enabled: (root.editingDeadline && String(root.editingDeadline.id || "").length > 0)
                        Layout.preferredWidth: root.moduleRatioPxW(0.11, 128, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.snoozeEditing()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: Boolean(root.editingDeadline && root.editingDeadline.escalated) ? "Clear Escalate" : "Escalate"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 112, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.escalateEditing()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: Boolean(root.editingDeadline && root.editingDeadline.completed) ? "Reopen" : "Mark Complete"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.toggleCompletedEditing()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Delete"
                        primary: false
                        enabled: (root.editingDeadline && String(root.editingDeadline.id || "").length > 0)
                        Layout.preferredWidth: root.moduleRatioPxW(0.08, 92, 180)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.deleteEditing()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: (root.editingDeadline && String(root.editingDeadline.id || "").length > 0) ? "Save Changes" : "Save Deadline"
                        primary: true
                        Layout.preferredWidth: root.moduleRatioPxW(0.10, 118, 220)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.saveEditing()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Cancel"
                        primary: false
                        Layout.preferredWidth: root.moduleRatioPxW(root.scaleRatios.cancelBtnWidthPct, 72, 200)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: {
                            root.pendingBriefingDeadlineId = ""
                            root.pendingBriefingCalendarDate = ""
                            root.activeSubwindowId = "B07"
                            root.ensureActiveSubwindow()
                        }
                    }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.moduleRatioPxW(
                                root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct,
                                138,
                                240
                            )
                            : 0
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.detachRequested(root.snapshotState())
                    }
                }
                    }
                }
            }
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onClientDataChanged() {
            if (!root.visible) {
                root.startupDeferredHydrationPending = true
                return
            }
            if (!root.startupHydrationCompleted) {
                root.ensureActivationHydration("appRef.onClientDataChanged")
                if (!root.startupHydrationCompleted) return
            }
            root.refreshLookupLists()
            if (root.docketActivityReportPanel) {
                root.docketActivityReportPanel._loadedOnce = false
            }
            if (root.activeIsDocketReport()) {
                root.requestDocketReportPanelLoad("appRef.onClientDataChanged", true)
            }
        }
        function onBackendBootChanged() {
            if (!root.visible) {
                root.startupDeferredHydrationPending = true
                return
            }
            if (!root.startupHydrationCompleted) {
                root.ensureActivationHydration("appRef.onBackendBootChanged")
                if (!root.startupHydrationCompleted) return
            }
            root.refreshLookupLists()
            if (root.activeIsDeadlineCalendar() || root.activeIsDeadlineEditor()) {
                root.refreshDeadlineMatterOptions()
                root.loadDeadlines()
            }
            if (root.activeIsDocketReport()) {
                root.requestDocketReportPanelLoad("appRef.onBackendBootChanged", true)
            }
        }
        function onError(message) {
            if (!root.visible) return
            var lowered = String(message || "").toLowerCase()
            if (lowered.indexOf("deadline") < 0) return
            root.showSaveFeedback(String(message || "Deadline operation failed."), true)
        }
    }

    Connections {
        target: root.windowRef
        function onStartupHeavyWorkAllowedChanged() {
            if (!root.windowRef || !root.windowRef.startupHeavyWorkAllowed) return
            if (root.startupDeferredHydrationPending) {
                root.ensureActivationHydration("window.startupHeavyWorkAllowed")
            }
            if (root.activeIsDocketReport() || root.docketReportPanelLoadRequested) {
                root.requestDocketReportPanelLoad("window.startupHeavyWorkAllowed", false)
            }
        }
    }

    Popup {
        id: timerLockPopup
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        width: root.ratioPxW(0.40, 340)
        padding: root.ratioPx(0.010, 10)

        background: Rectangle {
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(0.012, 10)
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.alpha(root._accent, 0.36)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Timer Already Running"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: {
                    var holder = root.timerLockHolder || ({})
                    var descriptor = String(holder.descriptor || holder.ownerLabel || "another docket window")
                    return "A timer is already running in " + descriptor + ". Stop it there, then start here."
                }
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Switch Here"
                    primary: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        root.takeOverTimerHere()
                    }
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Open Docket"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        timerLockPopup.close()
                        root.jumpToLockHolder()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: timerLockPopup.close()
                }
            }
        }
    }

    Popup {
        id: timeFieldValidationPopup
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        width: root.ratioPxW(0.34, 360)
        padding: root.ratioPx(0.012, 12)

        function centerToRoot() {
            var hostW = Math.max(1, Math.round(root.width || 1))
            var hostH = Math.max(1, Math.round(root.height || 1))
            x = Math.max(0, Math.round((hostW - width) * 0.5))
            y = Math.max(0, Math.round((hostH - height) * 0.5))
        }

        onOpened: centerToRoot()
        onVisibleChanged: if (visible) centerToRoot()
        onWidthChanged: if (visible) centerToRoot()
        onHeightChanged: if (visible) centerToRoot()

        background: Rectangle {
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(0.012, 10)
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.alpha(root._accent, 0.36)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.009, 8)

            Text {
                Layout.fillWidth: true
                text: "Invalid Time Format"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignLeft
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: String(root.timeFieldValidationMessage || "Use decimal hours or HH:MM[:SS].")
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)
                Item { Layout.fillWidth: true }
                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "OK"
                    primary: true
                    Layout.fillWidth: false
                    Layout.preferredWidth: root.moduleRatioPxW(0.085, 110, 170)
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        timeFieldValidationPopup.close()
                        Qt.callLater(function() {
                            if (!timeInput) return
                            timeInput.forceActiveFocus()
                            timeInput.selectAll()
                        })
                    }
                }
                Item { Layout.fillWidth: true }
            }
        }
    }

    Popup {
        id: unlinkInvoiceConfirmationPopup
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        width: root.ratioPxW(0.46, 360)
        padding: root.ratioPx(0.010, 10)

        background: Rectangle {
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(0.012, 10)
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.alpha(root._accent, 0.36)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Reverse / Unlink Invoice"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "This docket is billed. Are you sure you want to reverse the invoice? If the invoice is missing (phantom), this will simply scrub the invoice reference and unlock the docket."
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Unlink / Reverse"
                    primary: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        unlinkInvoiceConfirmationPopup.close()
                        if (root.lastSavedEntryId) {
                            var backend = (typeof docketApp !== "undefined") ? docketApp : ((appRef && appRef.docketing) ? appRef.docketing : null)
                            if (backend && backend.unlinkBilledDocket) {
                                backend.unlinkBilledDocket(root.lastSavedEntryId)
                            }
                        }
                    }
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: unlinkInvoiceConfirmationPopup.close()
                }
            }
        }
    }

    Popup {
        id: deleteConfirmationPopup
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        width: root.ratioPxW(0.46, 360)
        padding: root.ratioPx(0.010, 10)

        background: Rectangle {
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(0.012, 10)
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.alpha(root._accent, 0.36)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Confirm Delete"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Are you sure you want to delete this docket entry? This action cannot be undone."
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Delete"
                    primary: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        deleteConfirmationPopup.close()
                        if (root.lastSavedEntryId) {
                            if (appRef && appRef.deleteTimeEntry) {
                                var result = appRef.deleteTimeEntry(root.lastSavedEntryId)
                                if (result && result.ok) {
                                    root.lastSavedEntryId = ""
                                    root.dirty = false
                                    root.returnToCallerOrClose()
                                }
                            }
                        }
                    }
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: deleteConfirmationPopup.close()
                }

                Item { Layout.fillWidth: true }
            }
        }
    }

    Popup {
        id: matterRequiredPopup
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        width: root.ratioPxW(0.46, 360)
        padding: root.ratioPx(0.010, 10)

        background: Rectangle {
            radius: root.isProMode
                ? root.proControlRadiusPx
                : root.ratioPx(0.012, 10)
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.alpha(root._accent, 0.36)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Matter Required"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "This docket should be tied to a matter. Create/select a matter, or continue with a temporary client-only draft."
                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Create Matter"
                    primary: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                    // Return navigation hook
                    if (root.appRef && root.appRef._returnToReports) {
                        root.appRef._returnToReports = false;
                        if (root.windowRef && typeof root.windowRef.openModule === "function") {
                            root.windowRef.openModule(7, null);
                        } else if (typeof mainWin !== "undefined" && typeof mainWin.setTileIndex === "function") {
                            mainWin.setTileIndex(7);
                        }
                        return;
                    }
                        matterRequiredPopup.close()
                        var state = {
                            "_targetTileState": {
                                "focusNodeId": "A13",
                                "matterClientText": clientCombo.editText,
                                "matterDateOpenedText": dateInput.text
                            }
                        }
                        root.moduleJumpRequested(0, state)
                    }
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Choose Matter"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        matterRequiredPopup.close()
                        matterCombo.forceActiveFocus()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Client-only Draft"
                    primary: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                        matterRequiredPopup.close()
                        root.continuePendingSave({ "allowClientOnlyDraft": true })
                    }
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.fieldHeightPx, root.ratioPx(0.045, 42))
                    onClicked: {
                    // Return navigation hook
                    if (root.appRef && root.appRef._returnToReports) {
                        root.appRef._returnToReports = false;
                        if (root.windowRef && typeof root.windowRef.openModule === "function") {
                            root.windowRef.openModule(7, null);
                        } else if (typeof mainWin !== "undefined" && typeof mainWin.setTileIndex === "function") {
                            mainWin.setTileIndex(7);
                        }
                        return;
                    }
                        matterRequiredPopup.close()
                        root.pendingSaveReason = ""
                        root.pendingSaveOptions = ({})
                    }
                }
            }
        }
    }

    SequentialAnimation {
        id: timerPulseAnimation
        running: root.isRunning
        loops: Animation.Infinite
        NumberAnimation {
            target: timerPill
            property: "opacity"
            to: 0.72
            duration: 420
            easing.type: Easing.InOutQuad
        }
        NumberAnimation {
            target: timerPill
            property: "opacity"
            to: 1.0
            duration: 420
            easing.type: Easing.InOutQuad
        }
    }

    onIsRunningChanged: {
        if (!root.isRunning) {
            timerPill.opacity = 1.0
            root.activeSegmentStartedAtMs = 0
            releaseTimerLock()
        }
    
    }

    Component.onCompleted: {
        ensureTimerOwnerId()
        syncTimeFieldFromElapsed()
        ensureActivationHydration("Component.onCompleted")
        if (root.activeIsDocketReport()) {
            requestDocketReportPanelLoad("Component.onCompleted", false)
        }
    }

    Component.onDestruction: {
        releaseTimerLock()
    }

    onVisibleChanged: {
        if (!visible) return
        ensureActivationHydration("onVisibleChanged")
        if (root.activeIsDocketReport()) {
            requestDocketReportPanelLoad("onVisibleChanged", true)
        }
        if (!root.startupHydrationCompleted) return
        if (root.activeUsesDocketContext()) {
            refreshLookupLists()
            if (!root.dirty) scheduleBucketRefresh()
        }
    }

    onActiveSubwindowIdChanged: {
        if (root.externalNavigationShell && root.tileIndex >= 0) {
            root.workspaceNavChanged(root.tileIndex, root.snapshotState())
        }
        if (root.activeIsDocketReport()) {
            requestDocketReportPanelLoad("onActiveSubwindowIdChanged", true)
        }
        ensureActivationHydration("onActiveSubwindowIdChanged")
        if (!root.startupHydrationCompleted) {
            if (root.activeIsDeadlineEditor()) {
                ensureEditingDeadlineSeeded()
            }
            return
        }
        if (root.activeUsesDocketContext()) {
            refreshLookupLists()
            if (!root.dirty) scheduleBucketRefresh()
        }
        if (root.activeIsDeadlineCalendar() || root.activeIsDeadlineEditor()) {
            root.refreshDeadlineMatterOptions()
            root.loadDeadlines()
        }
        if (root.activeIsDeadlineEditor()) {
            ensureEditingDeadlineSeeded()
        }
    }

    onInitialStateChanged: {
        if (initialState) applyInitialState(initialState)
    }
}
