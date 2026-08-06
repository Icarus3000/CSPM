pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import "../components"
import "../views"
import "../standards"
import "../standards/ModulePathways.js" as ModulePathways
import "../standards/PerfTrace.js" as PerfTrace
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    layer.enabled: roundedRootMaskEnabled
    layer.smooth: true
    layer.effect: MultiEffect {
        maskEnabled: root.roundedRootMaskEnabled
        maskSource: rootRoundedMask
        maskThresholdMin: 0.74
        maskSpreadAtMin: 0.10
        autoPaddingEnabled: false
    }
    property var t
    property var metrics
    property var windowRef
    property var sfxBus
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property bool isProMode: appStyle === "Professional"
    property bool isInteractive: true
    // Keep fallback renderer available for emergency diagnostics, but disabled by default
    // because translucent overlays can visually double-expose the HomeGrid.
    property bool enableHomeGridFallback: false
    property int initialTileIndex: -1
    property var initialPanelState: null
    property bool detachedWindow: false
    property real chromeCornerRadius: 0
    property bool roundedRootMaskEnabled: chromeCornerRadius > 0
    property var pendingDockRequest: null
    property var dockedStateByTile: ({})
    property bool hubModuleChooserVisible: false
    property var hubModuleChooserRows: []
    property int hubModuleChooserHubIndex: -1
    property rect hubModuleChooserOriginRect: Qt.rect(0, 0, 0, 0)
    signal tearAwayRequested(int tileIndex, string titleText, var state, rect originRect)
    signal dockRequested(int tileIndex, string titleText, var state, rect originRect)
    signal undockRequested(int tileIndex, string titleText, var state, rect originRect)
    property var tileTitles: ModulePathways.laneTitles()
    property var laneConfigs: ModulePathways.laneConfigs()
    property bool option3ShellEnabled: root.isProMode && !root.detachedWindow
    property var option3NavigationModules: ModulePathways.navigationModules()
    property string option3FlyoutModuleId: ""
    property var option3OpenTabs: []
    property var option3Favorites: []
    property bool option3SuspendTabMutation: false
    property string option3ActiveTabId: ""
    property string option3CloseGuardTabId: ""
    property string option3CloseGuardMessage: ""

    onOption3OpenTabsChanged: {
        // console.warn("[TABS_CHANGED] stack:", new Error().stack)
    }

    property bool isMac: Qt.platform.os === "osx"
    property string option3PendingCloseAfterSaveTabId: ""
    property var option3RightDrawerState: ({ "open": false })
    property bool option3AutoEnsurePaused: false
    property var dashboardSummary: ({
        "ok": false,
        "asOfDate": "",
        "deadlinesCount": 0,
        "unbilledDraftCount": 0,
        "clientMeetingCount": 0,
        "queueCount": 0,
        "activeClientCount": 0,
        "activeMatterCount": 0
    })
    property bool _startupDashboardRefreshPending: false
    property int _startupDashboardRetryMs: 180
    property var _stackPageLoadRequested: ({ "1": false, "2": false, "3": false, "4": false })
    property var _startupPrewarmStackOrder: [2, 1, 3, 4]
    property int _startupPrewarmStackCursor: 0
    property bool _startupPrewarmComplete: false
    property bool _startupPrewarmQueuedToWindow: false
    property int _startupPrewarmStepMs: 220
    property var _perfMarks: ({})
    property color bgColor: (root && root.t && root.t.bg) ? root.t.bg : "#090E18"
    property color panelColor: (root && root.t && root.t.panel) ? root.t.panel : "#131C2B"
    property color panel2Color: (root && root.t && root.t.panel2) ? root.t.panel2 : ((root && root.panelColor) ? root.panelColor : "#131C2B")
    property color accentColor: (root && root.t && root.t.accent) ? root.t.accent : "#4DA3FF"
    property color textColor: (root && root.t && root.t.text) ? root.t.text : "#F5F8FF"
    property color proBackground: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color proSurface: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color proRaised: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color proHoverFill: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color proMutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color proActiveBorder: SemanticTheme.borderStrong(root.t, root.appStyle)
    property color proAccent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property real bgLuma: {
        if (!root) return 0.2;
        var c = root.bgColor;
        if (!c || typeof c.r !== "number") return 0.2;
        return (c.r * 0.299) + (c.g * 0.587) + (c.b * 0.114);
    }
    property bool lightTheme: (!root || (root ? typeof root.bgLuma : "undefined") !== "number") ? false : (root.bgLuma >= 0.58)
    property color portalAccentColor: (root && root.t && root.t.accent) ? root.t.accent : "#00E5FF"
    property color portalPanelColor: (root && root.t && root.t.panel) ? root.t.panel : "#0B1324"
    property var tileLaunchGeometryByIndex: ({})
    property int activeTileIndex: -1
    property double telemetryScreenOpenTime: 0
    property int telemetryLastTileIndex: -1

    signal universalSearchTriggered()
    
    Shortcut {
        sequence: "Ctrl+K"
        context: Qt.ApplicationShortcut
        enabled: !root.isProMode
        onActivated: {
            root.universalSearchTriggered()
            if (!root.isProMode) {
                // Return to home briefing to show the omni search bar
                root.option3OpenHomeBriefing()
            }
        }
    }
    onActiveTileIndexChanged: {
        if (typeof app !== "undefined" && app && app.recordTelemetryDuration) {
            var now = Date.now()
            if (telemetryScreenOpenTime > 0 && telemetryLastTileIndex >= 0) {
                var durationMs = now - telemetryScreenOpenTime
                var prevTitle = (telemetryLastTileIndex >= 0 && telemetryLastTileIndex < root.tileTitles.length) 
                    ? root.tileTitles[telemetryLastTileIndex] 
                    : ("Unknown_" + telemetryLastTileIndex)
                if (durationMs > 1000) {
                    app.recordTelemetryDuration("Screen_Time", durationMs, prevTitle)
                }
            }
            telemetryScreenOpenTime = now
            telemetryLastTileIndex = activeTileIndex
            
            if (activeTileIndex >= 0) {
                var currTitle = (activeTileIndex >= 0 && activeTileIndex < root.tileTitles.length) 
                    ? root.tileTitles[activeTileIndex] 
                    : ("Unknown_" + activeTileIndex)
                app.recordTelemetry("Screen_Opened", currTitle)
            } else {
                app.recordTelemetry("Screen_Opened", "Dashboard")
            }
        }
    }
    property bool portalReverse: false
    property string transitionTitle: "Module"
    property bool portalTransitionActive: false
    property real portalProgress: 0.0
    property real portalSwitchProgressForward: 0.66
    property real portalSwitchProgressReverse: 0.24
    property int portalTargetIndex: -1
    property real portalOriginX: 0.0
    property real portalOriginY: 0.0
    property real launchStartX: 0.0
    property real launchStartY: 0.0
    property real launchStartW: 1.0
    property real launchStartH: 1.0
    property real launchEndX: 0.0
    property real launchEndY: 0.0
    property real launchEndW: 1.0
    property real launchEndH: 1.0
    property real launchStartRadius: 1.0
    property real launchEndRadius: 1.0
    // Keep the floating undock tab implementation available, but disabled by default.
    property bool floatingUndockTabEnabled: false
    property var scaleRatios: ({
        "headerHeightPct": 0.114,
        "headerMarginPct": 0.014,
        "headerSpacingPct": 0.014,
        "titleSpacingPct": 0.0044,
        "titleFontPct": 0.0265,
        "logoSizePct": 0.106,
        "controlsSpacingPct": 0.0087,
        "dividerThicknessPct": 0.0011,
        "bodyMarginPct": 0.013,
        "portalBaseDiameterPct": 0.116,
        "portalRingBorderPct": 0.0019,
        "jellyCoreDiameterPct": 0.57,
        "jellySquishStrength": 0.23,
        "jellyStageOneDurationPct": 0.087,
        "jellyStageTwoDurationPct": 0.154,
        "jellyStageThreeDurationPct": 0.173,
        "jellyLaunchCornerStartPct": 0.018,
        "jellyLaunchCornerEndPct": 0.011,
        "jellyLaunchTopBarPct": 0.116,
        "jellyLaunchPreviewPaddingPct": 0.018,
        "jellyLaunchPreviewGapPct": 0.010,
        "jellyLaunchPreviewRowPct": 0.101,
        "hubChooserWidthPct": 0.30,
        "hubChooserPadPct": 0.014,
        "hubChooserGapPct": 0.009,
        "hubPanelBorderPct": 0.0011,
        "undockTabWidthPct": 0.21,
        "undockTabHeightPct": 0.045,
        "undockTabRadiusPct": 0.012,
        "undockTabDragThresholdPct": 0.080
    })
    property real portalSwitchProgress: portalSwitchProgressForward

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    Rectangle {
        id: rootRoundedMask
        anchors.fill: parent
        radius: Math.max(0, root.chromeCornerRadius)
        color: "black"
        visible: false
        antialiasing: true
        smooth: true
        layer.enabled: true
    }

    function ratioPx(ratio, minPx) {
        var rw = root.width
        var rh = root.height
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            rw = metrics.contentW
            rh = metrics.contentH
        }
        var unit = Math.min(Math.max(1, rw), Math.max(1, rh))
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(unit * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    function alphaAccent(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    function alphaText(a) {
        return Qt.rgba(root.textColor.r, root.textColor.g, root.textColor.b, a)
    }

    function colorLuma(c) {
        return (c.r * 0.299) + (c.g * 0.587) + (c.b * 0.114)
    }

    function readableInk(fillColor) {
        return colorLuma(fillColor) >= 0.58
            ? Qt.rgba(0.07, 0.09, 0.12, 0.99)
            : Qt.rgba(0.98, 0.99, 1.0, 0.99)
    }

    function transitionDurationMs(ratio, minMs) {
        var unit = Math.min(Math.max(1, root.width), Math.max(1, root.height))
        return Math.max(Math.max(1, Math.round(minMs || 1)), Math.round(unit * ratio))
    }

    function perfLog(message) {
        var text = "[PERF] MainContent " + String(message || "")
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

    function clamp01(v) {
        if (!isFinite(v)) return 0.0
        if (v < 0.0) return 0.0
        if (v > 1.0) return 1.0
        return v
    }

    function clampNumber(v, minVal, maxVal) {
        var n = Number(v)
        if (!isFinite(n)) n = Number(minVal)
        var lo = Number(minVal)
        var hi = Number(maxVal)
        if (!isFinite(lo)) lo = n
        if (!isFinite(hi)) hi = n
        if (lo > hi) {
            var tmp = lo
            lo = hi
            hi = tmp
        }
        return Math.max(lo, Math.min(hi, n))
    }

    function playSfxTilePress() {
        if (sfxBus && sfxBus.playTilePress) {
            sfxBus.playTilePress()
        }
    }

    function playSfxUiClick(kind, strengthNorm) {
        if (sfxBus && sfxBus.playUiClick) {
            sfxBus.playUiClick(kind, clamp01(strengthNorm))
        } else {
            playSfxTilePress()
        }
    }

    function playSfxTransitionDeform(strengthNorm) {
        if (sfxBus && sfxBus.playWindowDeform) {
            sfxBus.playWindowDeform(clamp01(strengthNorm))
        }
    }

    function playSfxLaunchBurst(strengthNorm) {
        if (sfxBus && sfxBus.playLaunchBurst) {
            sfxBus.playLaunchBurst(clamp01(strengthNorm))
        }
    }

    function playSfxTransitionSettle(strengthNorm) {
        if (sfxBus && sfxBus.playWindowSettle) {
            sfxBus.playWindowSettle("dock", clamp01(strengthNorm))
        }
    }

    function portalEaseOutCubic(v) {
        var t = clamp01(v)
        var inv = 1.0 - t
        return 1.0 - (inv * inv * inv)
    }

    function mix(a, b, t) {
        var p = clamp01(t)
        return a + ((b - a) * p)
    }

    function jellyEaseOutBack(v) {
        var t = clamp01(v) - 1.0
        var s = 1.525
        return 1.0 + ((s + 1.0) * t * t * t) + (s * t * t)
    }

    function sourceRectFor(itemRef) {
        if (!itemRef || !skylineBackdrop) {
            return Qt.rect(0, 0, Math.max(1, root.width), Math.max(1, root.height))
        }
        var p = itemRef.mapToItem(skylineBackdrop, 0, 0)
        return Qt.rect(
            Math.round(p.x),
            Math.round(p.y),
            Math.max(1, Math.round(itemRef.width)),
            Math.max(1, Math.round(itemRef.height))
        )
    }

    function jellyLaunchProgress(v) {
        var t = clamp01(v)
        if (t <= 0.18) {
            return 0.04 * (t / 0.18)
        }
        var stage = (t - 0.18) / 0.82
        return 0.04 + (0.96 * jellyEaseOutBack(stage))
    }

    function tileTitleForIndex(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return "Module"
        return tileTitles[idx]
    }

    function dockTitleForIndex(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx === -1) return "Practice Briefing"
        return tileTitleForIndex(idx)
    }

    function laneConfigForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return null
        if (!laneConfigs || laneConfigs.length === undefined) return null
        if (idx >= laneConfigs.length) return null
        return laneConfigs[idx]
    }

    function laneNavItemsForTile(tileIndex) {
        var cfg = laneConfigForTile(tileIndex)
        if (!cfg || !cfg.displayNavItems || cfg.displayNavItems.length === undefined) return []
        return cfg.displayNavItems
    }

    function option3ModuleForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        var modules = option3NavigationModules || []
        for (var i = 0; i < modules.length; i++) {
            if (Math.round(modules[i].tileIndex) === idx) return modules[i]
        }
        return ModulePathways.moduleForTile(idx)
    }

    function option3ModuleForId(moduleId) {
        var wanted = String(moduleId || "").trim()
        var modules = option3NavigationModules || []
        for (var i = 0; i < modules.length; i++) {
            if (String(modules[i].moduleId || "") === wanted) return modules[i]
        }
        return ModulePathways.moduleForId(wanted)
    }

    function option3CurrentTileIndex() {
        if (stack && stack.currentIndex > 0) {
            var fromStack = tileIndexForStack(stack.currentIndex)
            if (fromStack >= 0) return fromStack
        }
        if (activeTileIndex >= 0 && activeTileIndex < tileTitles.length) return activeTileIndex
        return 0
    }

    function option3StateForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        var livePanel = panelRefForTile(idx)
        if (livePanel && livePanel.snapshotState) {
            try {
                var liveState = livePanel.snapshotState()
                if (liveState && typeof liveState === "object") return liveState
            } catch (e0) {
            }
        }
        if (dockedStateByTile && dockedStateByTile[idx] !== undefined) return dockedStateByTile[idx]
        return {}
    }

    function option3NodeIdForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        var state = option3StateForTile(idx)
        if (state && typeof state === "object" && state.focusNodeId !== undefined) {
            var nodeId = String(state.focusNodeId || "").trim()
            if (nodeId.length > 0) return nodeId
        }
        var module = option3ModuleForTile(idx)
        return module ? String(module.defaultNodeId || "") : ""
    }

    function option3ItemForTile(tileIndex, nodeId) {
        var idx = Math.round(tileIndex)
        var wanted = String(nodeId || option3NodeIdForTile(idx) || "").trim()
        var module = option3ModuleForTile(idx)
        if (module && module.navItems) {
            var navItems = module.navItems
            for (var i = 0; i < navItems.length; i++) {
                if (String(navItems[i].nodeId || navItems[i].id || "") === wanted) {
                    return navItems[i]
                }
            }
            if (wanted.length <= 0 && navItems.length > 0) return navItems[0]
        }
        var item = ModulePathways.findNavigationItem(idx, wanted)
        if (item) return item
        return ModulePathways.defaultNavigationItem(idx)
    }

    function option3ItemForModuleNode(moduleId, nodeId) {
        var module = option3ModuleForId(moduleId)
        if (!module || !module.navItems) return null
        var wanted = String(nodeId || module.defaultNodeId || "").trim()
        var items = module.navItems
        for (var i = 0; i < items.length; i++) {
            if (String(items[i].nodeId || items[i].id || "") === wanted) return items[i]
        }
        return items.length > 0 ? items[0] : null
    }

    function option3OpenScreenByModuleNode(moduleId, nodeId) {
        var module = option3ModuleForId(moduleId)
        var item = option3ItemForModuleNode(moduleId, nodeId)
        if (!module || !item) return false
        return option3OpenWorkspace(module, item, {})
    }

    function option3OpenHomeBriefing() {
        return option3OpenScreenByModuleNode("home", "H01")
    }

    function ensureStartupProfessionalHome() {
        // The first Professional-window surface is its native no-open-tabs
        // home, not a pre-opened Practice Briefing tab. Preserve explicit
        // routed starts and existing workspaces.
        if (!option3ShellEnabled || !stack) return
        if (Math.round(initialTileIndex) >= 0) return
        if (stack.currentIndex !== 0 || option3HasCurrentWorkspace()) return
        activeTileIndex = -1
        transitionTitle = "Home"
    }

    function option3ActiveModuleId() {
        var tab = option3ActiveTab()
        if (tab && tab.moduleId) return String(tab.moduleId || "")
        var module = option3ModuleForTile(option3CurrentTileIndex())
        return module ? String(module.moduleId || "") : ""
    }

    function option3ActiveItemId() {
        var item = option3ItemForTile(option3CurrentTileIndex(), "")
        return item ? String(item.nodeId || item.id || "") : ""
    }

    function option3ActiveTab() {
        var wanted = String(option3ActiveTabId || "")
        var tabs = option3OpenTabs || []
        for (var i = 0; i < tabs.length; i++) {
            if (String(tabs[i].id || "") === wanted) return tabs[i]
        }
        return null
    }

    function option3ActiveModuleTitle() {
        if (option3ShellEnabled && !option3HasCurrentWorkspace()) return "Workspace"
        var tab = option3ActiveTab()
        if (tab && tab.moduleTitle) return String(tab.moduleTitle || "")
        var module = option3ModuleForTile(option3CurrentTileIndex())
        return module ? String(module.title || "") : "Workspace"
    }

    function option3ActiveItemTitle() {
        if (option3ShellEnabled && !option3HasCurrentWorkspace()) return ""
        var tab = option3ActiveTab()
        if (tab && tab.title) return String(tab.title || "")
        var item = option3ItemForTile(option3CurrentTileIndex(), "")
        return item ? String(item.label || item.title || "") : ""
    }

    function option3ActiveSubtitle() {
        if (option3ShellEnabled && !option3HasCurrentWorkspace()) return "No docked workspace tabs"
        var module = option3ModuleForTile(option3CurrentTileIndex())
        var item = option3ItemForTile(option3CurrentTileIndex(), "")
        var section = item && item.sectionTitle ? String(item.sectionTitle || "") : ""
        var subtitle = module && module.subtitle ? String(module.subtitle || "") : ""
        return section.length > 0 ? (section + " - " + subtitle) : subtitle
    }

    function option3ActiveDirty() {
        var tab = option3ActiveTab()
        return tab ? !!tab.dirty : false
    }

    function option3OpenFlyout(moduleId) {
        var wanted = String(moduleId || "").trim()
        if (wanted.length <= 0) return false
        option3FlyoutModuleId = (option3FlyoutModuleId === wanted) ? "" : wanted
        return true
    }

    function option3FlyoutModuleData() {
        if (String(option3FlyoutModuleId || "").length <= 0) return null
        return option3ModuleForId(option3FlyoutModuleId)
    }

    function option3FirstStringValue(source, keys) {
        if (!source || typeof source !== "object") return ""
        for (var i = 0; i < keys.length; i++) {
            var key = String(keys[i] || "")
            if (key.length <= 0 || source[key] === undefined || source[key] === null) continue
            var value = String(source[key] || "").trim()
            if (value.length > 0) return value
        }
        return ""
    }

    function option3ParamValue(params, keys) {
        var sources = []
        if (params && typeof params === "object") {
            sources.push(params)
            if (params.state && typeof params.state === "object") sources.push(params.state)
            if (params.record && typeof params.record === "object") sources.push(params.record)
            if (params.entity && typeof params.entity === "object") sources.push(params.entity)
            if (params.reportDocument && typeof params.reportDocument === "object") sources.push(params.reportDocument)
            if (params.reportState && typeof params.reportState === "object") sources.push(params.reportState)
        }
        for (var i = 0; i < sources.length; i++) {
            var value = option3FirstStringValue(sources[i], keys)
            if (value.length > 0) return value
        }
        return ""
    }

    function option3ParamsWithState(params, state) {
        var out = root.shallowCloneObject(params || ({}))
        if (state && typeof state === "object" && out.state === undefined) {
            out.state = state
        }
        return out
    }

    function option3EffectiveNodeId(nodeId, state) {
        var routeNode = String(nodeId || "").trim()
        if (state && typeof state === "object" && state.focusNodeId !== undefined) {
            var stateNode = String(state.focusNodeId || "").trim()
            if (stateNode.length > 0) return stateNode
        }
        return routeNode
    }

    function option3PersistableTileState(state) {
        if (!state || typeof state !== "object") return state
        var next = root.shallowCloneObject(state)
        delete next.briefingDeadlineId
        delete next.briefingCalendarDate
        return next
    }

    function option3EntityTypeForItem(item, params) {
        var explicitType = option3ParamValue(params, [
            "entityType", "recordType", "tabEntityType", "option3EntityType"
        ]).toLowerCase()
        if (explicitType.length > 0) return explicitType

        var tabType = String(item && item.tabType ? item.tabType : "screen").trim().toLowerCase()
        if (tabType === "client" || tabType === "matter" || tabType === "invoice"
                || tabType === "report" || tabType === "dashboard" || tabType === "calendar") {
            return tabType
        }
        return "record"
    }

    function option3EntityIdForItem(item, params) {
        var explicitId = option3ParamValue(params, [
            "entityId", "recordId", "tabEntityId", "option3EntityId"
        ])
        if (explicitId.length > 0) return explicitId

        var entityType = option3EntityTypeForItem(item, params)
        if (entityType === "client") {
            return option3ParamValue(params, [
                "clientId", "selectedClientId", "clientProfileAutoLoadKey", "clientName", "selectedClientName"
            ])
        }
        if (entityType === "matter") {
            return option3ParamValue(params, [
                "matterId", "selectedMatterId", "matterNumber", "matterName", "selectedMatterName"
            ])
        }
        if (entityType === "invoice") {
            return option3ParamValue(params, [
                "invoiceId", "invoiceNumber", "invoiceDraftId", "draftId"
            ])
        }
        if (entityType === "report" || entityType === "dashboard") {
            return option3ParamValue(params, [
                "reportId", "reportKey", "reportName", "title"
            ])
        }
        return option3ParamValue(params, [
            "id", "key", "recordKey", "transactionId", "accountId", "categoryId"
        ])
    }

    function option3EntityTitleForItem(item, params) {
        var explicitTitle = option3ParamValue(params, [
            "entityTitle", "recordTitle", "tabEntityTitle", "option3EntityTitle", "displayName", "title"
        ])
        if (explicitTitle.length > 0) return explicitTitle

        var entityType = option3EntityTypeForItem(item, params)
        if (entityType === "client") {
            return option3ParamValue(params, ["clientName", "selectedClientName", "legalName"])
        }
        if (entityType === "matter") {
            return option3ParamValue(params, ["matterName", "selectedMatterName", "matterNumber"])
        }
        if (entityType === "invoice") {
            return option3ParamValue(params, ["invoiceNumber", "invoiceTitle", "draftId"])
        }
        if (entityType === "report" || entityType === "dashboard") {
            return option3ParamValue(params, ["reportTitle", "reportName", "title"])
        }
        return option3ParamValue(params, ["name", "label"])
    }

    function option3EntityIdentityForItem(item, params) {
        var entityType = option3EntityTypeForItem(item, params)
        var entityId = option3EntityIdForItem(item, params)
        var entityTitle = option3EntityTitleForItem(item, params)
        return {
            "entityType": entityType,
            "entityId": entityId,
            "entityTitle": entityTitle
        }
    }

    function option3TabTitleForItem(moduleData, itemData, params) {
        var explicitTitle = option3ParamValue(params || ({}), ["tabTitle", "workspaceTitle"])
        if (explicitTitle.length > 0) return explicitTitle

        var identity = option3EntityIdentityForItem(itemData, params || ({}))
        var entityTitle = String(identity.entityTitle || identity.entityId || "").trim()
        var entityType = String(identity.entityType || "").toLowerCase()
        if (itemData && itemData.singleInstance === false && entityTitle.length > 0) {
            if (entityType === "client") return "Client: " + entityTitle
            if (entityType === "matter") return "Matter: " + entityTitle
            if (entityType === "invoice") return "Invoice: " + entityTitle
            if (entityType === "report") return "Report: " + entityTitle
            return String(itemData.label || itemData.title || "Record") + ": " + entityTitle
        }
        return String(itemData.label || itemData.title || moduleData.title || "Workspace")
    }

    function option3ApplyEntityIdentityToState(identity, state) {
        var next = state && typeof state === "object" ? state : ({})
        var entityType = String(identity && identity.entityType ? identity.entityType : "").toLowerCase()
        var entityId = String(identity && identity.entityId ? identity.entityId : "").trim()
        var entityTitle = String(identity && identity.entityTitle ? identity.entityTitle : "").trim()
        if (entityId.length <= 0 && entityTitle.length <= 0) return next

        next.option3EntityType = entityType
        next.option3EntityId = entityId
        next.option3EntityTitle = entityTitle

        if (entityType === "client") {
            if (entityId.length > 0) {
                next.selectedClientId = entityId
                next.clientProfileAutoLoadKey = entityId
                next.autoLoadClientProfile = true
            }
            if (entityTitle.length > 0) next.selectedClientName = entityTitle
        } else if (entityType === "matter") {
            if (entityId.length > 0) next.selectedMatterId = entityId
            if (entityTitle.length > 0) next.selectedMatterName = entityTitle
        } else if (entityType === "invoice") {
            if (entityId.length > 0) next.invoiceId = entityId
            if (entityTitle.length > 0) next.invoiceTitle = entityTitle
        } else if (entityType === "report" || entityType === "dashboard") {
            if (entityId.length > 0) next.reportId = entityId
            if (entityTitle.length > 0) next.reportTitle = entityTitle
        }
        return next
    }

    function option3ApplyTabEntityToState(tab, state) {
        return option3ApplyEntityIdentityToState({
            "entityType": String(tab && tab.entityType ? tab.entityType : ""),
            "entityId": String(tab && tab.entityId ? tab.entityId : ""),
            "entityTitle": String(tab && tab.entityTitle ? tab.entityTitle : "")
        }, state)
    }

    function option3TabKeyForItem(item, params) {
        if (!item) return ""
        var explicitKey = option3ParamValue(params || ({}), ["singleInstanceKey", "tabSingleInstanceKey"])
        if (explicitKey.length > 0) return explicitKey

        var base = String(item.singleInstanceKey || item.itemId || item.nodeId || item.id || "")
        var identity = option3EntityIdentityForItem(item, params || ({}))
        if (item.singleInstance === false && identity.entityId.length > 0) {
            return base + ":" + identity.entityType + ":" + identity.entityId
        }
        return base
    }

    function option3TabIdForKey(key) {
        var raw = String(key || "workspace").toLowerCase()
        raw = raw.replace(/[^a-z0-9]+/g, "-")
        raw = raw.replace(/^-+|-+$/g, "")
        if (raw.length <= 0) raw = "workspace"
        return "tab-" + raw
    }

    function option3FindTabIndexById(tabId) {
        var wanted = String(tabId || "")
        var tabs = option3OpenTabs || []
        for (var i = 0; i < tabs.length; i++) {
            if (String(tabs[i].id || "") === wanted) return i
        }
        return -1
    }

    function option3UniqueTabId(baseId) {
        var base = String(baseId || "tab-workspace").trim()
        if (base.length <= 0) base = "tab-workspace"
        if (option3FindTabIndexById(base) < 0) return base
        for (var i = 2; i < 1000; i++) {
            var candidate = base + "-" + i
            if (option3FindTabIndexById(candidate) < 0) return candidate
        }
        return base + "-" + Date.now()
    }

    function option3SetEmptyWorkspace(reason) {
        option3ActiveTabId = ""
        option3FlyoutModuleId = ""
        activeTileIndex = -1
        transitionTitle = "Workspace"
        if (!stack) return true

        var wasPaused = option3AutoEnsurePaused
        option3AutoEnsurePaused = true
        stack.currentIndex = 0
        option3AutoEnsurePaused = wasPaused
        return true
    }

    function option3HasCurrentWorkspace() {
        if (!option3ShellEnabled) return false
        if (option3ActiveTab()) return true
        return !!stack && stack.currentIndex > 0 && activeTileIndex >= 0
    }

    function option3FindTabIndexForItem(itemData, params) {
        if (!itemData) return -1
        var key = option3TabKeyForItem(itemData, params || ({}))
        var singleInstance = itemData.singleInstance !== false
        var wantedTile = Math.round(itemData.tileIndex)
        var wantedNode = String(itemData.nodeId || itemData.id || "")
        var wantedRoute = String(itemData.route || "")
        var tabs = option3OpenTabs || []
        for (var i = 0; i < tabs.length; i++) {
            if (String(tabs[i].singleInstanceKey || "") === String(key || "")) {
                return i
            }
            if (singleInstance && Math.round(tabs[i].tileIndex) === wantedTile) {
                if (wantedNode.length > 0 && String(tabs[i].nodeId || "") === wantedNode) {
                    return i
                }
                if (wantedRoute.length > 0 && String(tabs[i].route || "") === wantedRoute) {
                    return i
                }
            }
        }
        return -1
    }

    function option3CopyOpenTabs() {
        var out = []
        var tabs = option3OpenTabs || []
        for (var i = 0; i < tabs.length; i++) out.push(root.shallowCloneObject(tabs[i]))
        return out
    }

    function option3CreateTab(moduleData, itemData, params, dirty) {
        var key = option3TabKeyForItem(itemData, params || ({}))
        var tabId = params && params.tabId !== undefined
            ? String(params.tabId || "")
            : option3TabIdForKey(key)
        tabId = option3UniqueTabId(tabId)
        var identity = option3EntityIdentityForItem(itemData, params || ({}))
        return {
            "id": tabId,
            "title": option3TabTitleForItem(moduleData, itemData, params || ({})),
            "moduleId": String(moduleData.moduleId || ""),
            "moduleTitle": String(moduleData.title || ""),
            "tileIndex": Math.round(itemData.tileIndex),
            "nodeId": String(itemData.nodeId || itemData.id || ""),
            "route": String(itemData.route || ""),
            "tabType": String(itemData.tabType || "screen"),
            "saveCommand": String(itemData.saveCommand || ""),
            "entityType": String(identity.entityType || ""),
            "entityId": String(identity.entityId || ""),
            "entityTitle": String(identity.entityTitle || ""),
            "singleInstanceKey": key,
            "dirty": !!dirty,
            "pinned": false
        }
    }
    function option3DuplicateTab(tabId) {
        var idx = option3FindTabIndexById(tabId)
        if (idx < 0) return false
        var src = root.shallowCloneObject(option3OpenTabs[idx])
        src.id = option3UniqueTabId(src.id)
        src.pinned = false
        var tabs = option3CopyOpenTabs()
        tabs.push(src)
        option3OpenTabs = tabs
        if (typeof proAppShell !== "undefined" && typeof proAppShell.saveState === "function") {
            proAppShell.saveState()
        }
        return true
    }

    function option3FavoriteTab(tabId) {
        var idx = option3FindTabIndexById(tabId)
        if (idx < 0) return false
        var src = option3OpenTabs[idx]
        var favs = []
        try {
            favs = JSON.parse(root.appRef.option3Favorites || "[]")
        } catch (e) {
            favs = []
        }
        
        var existingIndex = -1
        var checkId = src.nodeId || src.id || tabId
        for (var i = 0; i < favs.length; i++) {
            var favNodeId = favs[i].nodeId || favs[i].id || ""
            if (favNodeId === checkId && favs[i].moduleId === src.moduleId) {
                existingIndex = i
                break
            }
        }

        if (existingIndex >= 0) {
            favs.splice(existingIndex, 1)
        } else {
            var module = option3ModuleForId(src.moduleId)
            var moduleIcon = module && module.icon ? module.icon : "\uE82D"
            var favItem = {
                "id": src.id || tabId,
                "title": src.title,
                "shortTitle": src.moduleTitle || src.title,
                "moduleId": src.moduleId,
                "tileIndex": src.tileIndex,
                "nodeId": src.nodeId,
                "route": src.route,
                "tabType": src.tabType,
                "saveCommand": src.saveCommand,
                "entityType": src.entityType,
                "entityId": src.entityId,
                "entityTitle": src.entityTitle,
                "singleInstance": src.singleInstance,
                "singleInstanceKey": src.singleInstanceKey,
                "icon": src.icon || moduleIcon
            }
            favs.push(favItem)
        }

        if (typeof root.appRef !== "undefined" && root.appRef) {
            try {
                root.appRef.option3Favorites = JSON.stringify(favs)
            } catch (e) {
                console.warn("Failed to set appRef.option3Favorites: " + e)
            }
        }
        root.option3Favorites = [] // Force QML property binding re-evaluation
        Qt.callLater(function() {
            root.option3Favorites = favs
            if (typeof proAppShell !== "undefined" && typeof proAppShell.saveState === "function") {
                proAppShell.saveState()
            }
        })
        return true
    }

    function option3FavoriteModule(moduleData) {
        var favs = []
        try {
            favs = JSON.parse(root.appRef.option3Favorites || "[]")
        } catch (e) {
            favs = []
        }
        var favItem = {
            "id": moduleData.moduleId,
            "title": moduleData.title,
            "shortTitle": moduleData.shortTitle || moduleData.title,
            "moduleId": moduleData.moduleId,
            "tileIndex": moduleData.tileIndex,
            "nodeId": moduleData.moduleId,
            "route": "module",
            "tabType": "module",
            "saveCommand": "",
            "entityType": "",
            "entityId": "",
            "entityTitle": "",
            "singleInstance": true,
            "singleInstanceKey": moduleData.moduleId,
            "icon": moduleData.icon || "\uE82D"
        }
        favs.push(favItem)
        if (typeof root.appRef !== "undefined" && root.appRef) {
            try {
                root.appRef.option3Favorites = JSON.stringify(favs)
            } catch (e) {
                console.warn("Failed to set appRef.option3Favorites: " + e)
            }
        }
        root.option3Favorites = []
        Qt.callLater(function() {
            root.option3Favorites = favs
        })
        return true
    }

    function option3FavoriteItem(moduleData, itemData) {
        var favs = []
        try {
            favs = JSON.parse(root.appRef.option3Favorites || "[]")
        } catch (e) {
            favs = []
        }
        var moduleIcon = moduleData && moduleData.icon ? moduleData.icon : "\uE82D"
        var favItem = {
            "id": itemData.id || itemData.nodeId,
            "title": itemData.title || itemData.label || "Workspace",
            "shortTitle": itemData.shortTitle || itemData.title || itemData.label,
            "moduleId": moduleData.moduleId,
            "tileIndex": moduleData.tileIndex,
            "nodeId": itemData.nodeId || itemData.id,
            "route": itemData.route || "item",
            "tabType": itemData.tabType || "default",
            "saveCommand": itemData.saveCommand || "",
            "entityType": itemData.entityType || "",
            "entityId": itemData.entityId || "",
            "entityTitle": itemData.entityTitle || "",
            "singleInstance": itemData.singleInstance !== false,
            "singleInstanceKey": itemData.singleInstanceKey || (moduleData.moduleId + "/" + (itemData.nodeId || itemData.id)),
            "icon": itemData.icon || moduleIcon
        }
        favs.push(favItem)
        if (typeof root.appRef !== "undefined" && root.appRef) {
            try {
                root.appRef.option3Favorites = JSON.stringify(favs)
            } catch (e) {
                console.warn("Failed to set appRef.option3Favorites: " + e)
            }
        }
        root.option3Favorites = []
        Qt.callLater(function() {
            root.option3Favorites = favs
        })
        return true
    }

    function option3ActivateTab(tabId, focusAfter) {
        var index = option3FindTabIndexById(tabId)
        if (index < 0) return false
        var tab = option3OpenTabs[index]
        var idx = Math.round(tab.tileIndex)
        if (idx === -1) {
            if (stack) {
                root.requestStackPageLoad(0, "option3-activate-tab-home")
                stack.currentIndex = 0
            }
            activeTileIndex = -1
            transitionTitle = "Practice Briefing"
            option3ActiveTabId = String(tab.id || "")
            option3FlyoutModuleId = ""
            if (focusAfter === undefined || focusAfter) root.focusShellWindow()
            return true
        }
        var nodeId = String(tab.nodeId || "")
        var state = root.shallowCloneObject(option3StateForTile(idx))
        state.focusNodeId = nodeId
        state.focusNodeTitle = String(tab.title || "")
        state = option3ApplyTabEntityToState(tab, state)
        
        option3ActiveTabId = String(tab.id || "")
        
        root.applyStateToTile(idx, state)
        var targetStackIndex = stackIndexForTile(idx)
        if (targetStackIndex > 0 && stack) {
            root.requestStackPageLoad(targetStackIndex, "option3-activate-tab")
            stack.currentIndex = targetStackIndex
        }
        activeTileIndex = idx
        transitionTitle = tileTitleForIndex(idx)
        option3FlyoutModuleId = ""
        if (focusAfter === undefined || focusAfter) root.focusShellWindow()
        return true
    }

    function option3OpenWorkspace(moduleData, item, params) {
        if (!moduleData || !item) return false

        var wasSuspended = root.option3SuspendTabMutation
        root.option3SuspendTabMutation = true
        try {
            var tabParams = params || ({})
            var idx = Math.round(item.tileIndex)
    
            var incomingState = null
            if (tabParams && typeof tabParams === "object") {
                if (tabParams.state && typeof tabParams.state === "object") {
                    incomingState = root.shallowCloneObject(tabParams.state)
                } else if (tabParams.focusNodeId !== undefined
                        || tabParams.clientText !== undefined
                        || tabParams.matterText !== undefined
                        || tabParams.cspmQuickAction !== undefined
                        || tabParams.forceNewDocketContext !== undefined) {
                    incomingState = root.shallowCloneObject(tabParams)
                }
            }
    
            if (incomingState) {
                var requestedFocus = incomingState.focusNodeId !== undefined
                    ? String(incomingState.focusNodeId || "").trim()
                    : ""
                if (requestedFocus.length <= 0) {
                    incomingState.focusNodeId = String(item.nodeId || item.id || "")
                }
                if (!incomingState.focusNodeTitle) {
                    incomingState.focusNodeTitle = String(item.label || item.title || "")
                }
    
                if (tabParams.activate !== false) {
                    // This must happen BEFORE tab activation, otherwise the old B01/Yoo state
                    // can be snapshotted and re-applied during activation.
                    root.applyStateToTile(idx, incomingState)
                }
            }
    
            if (!tabParams.forceNewInstance) {
                var tabIndex = option3FindTabIndexForItem(item, tabParams)
                if (tabIndex >= 0) {
                    var existingId = option3OpenTabs[tabIndex].id
                    option3ActivateTab(existingId, false)
    
                    if (incomingState) {
                        root.applyStateToTile(idx, incomingState)
                        root.option3UpdateTabForState(idx, incomingState)
                        Qt.callLater(function() {
                            root.option3UpdateTabForState(idx, incomingState)
                            root.focusShellWindow()
                        })
                    } else {
                        root.focusShellWindow()
                    }
    
                    return existingId
                }
            }
    
            var state = incomingState || option3StateForTile(idx)
            var tabs = option3CopyOpenTabs()
            var tab = option3CreateTab(moduleData, item, tabParams, !!state.dirty)
            tabs.push(tab)
            option3OpenTabs = tabs
    
            // Pause auto-ensure so the stack.currentIndex change inside
            // option3ActivateTab does NOT trigger EnsureTabForCurrentWorkspace
            // (which would create a duplicate tab using the stale defaultNodeId).
            var wasPaused = option3AutoEnsurePaused
            option3AutoEnsurePaused = true
            if (tabParams.activate !== false) {
                option3ActivateTab(String(tab.id || ""), false)
            }
            option3AutoEnsurePaused = wasPaused
    
            if (incomingState) {
                if (tabParams.activate !== false) {
                    root.applyStateToTile(idx, incomingState)
                    root.option3UpdateTabForState(idx, incomingState)
                    Qt.callLater(function() {
                        root.option3UpdateTabForState(idx, incomingState)
                        root.focusShellWindow()
                    })
                }
            } else {
                if (tabParams.activate !== false) {
                    root.focusShellWindow()
                }
            }
    
            return true
        } finally {
            root.option3SuspendTabMutation = wasSuspended
        }
    }

    function option3OpenWorkspaceForTile(tileIndex, nodeId, params) {
        var idx = Math.round(tileIndex)
        var module = option3ModuleForTile(idx)
        var effectiveNodeId = option3EffectiveNodeId(nodeId, params || ({}))
        var item = option3ItemForTile(idx, effectiveNodeId || nodeId || "")
        return option3OpenWorkspace(module, item, params || ({}))
    }

    function option3OpenWorkspaceForTileState(idx, nodeId, state) {
        return option3OpenWorkspaceForTile(idx, nodeId || "", state || ({}))
    }

    function handleWorkspaceOpenRequested(tileIndex, nodeId, state) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return false

        var targetState = (state && typeof state === "object")
            ? root.shallowCloneObject(state)
            : ({})

        var effectiveNodeId = option3EffectiveNodeId(nodeId, targetState)
        if (effectiveNodeId.length > 0) {
            targetState.focusNodeId = effectiveNodeId
        }

        if (targetState && typeof targetState === "object") {
            root.applyStateToTile(idx, targetState)
        }

        var result = false
        if (root.option3ShellEnabled) {
            result = option3OpenWorkspaceForTileState(idx, effectiveNodeId || nodeId || "", targetState)
        } else if (root.detachedWindow) {
            var targetStackIndex = root.stackIndexForTile(idx)
            if (targetStackIndex <= 0) return false
            root.requestStackPageLoad(targetStackIndex, "workspace-open-request")
            if (stack) stack.currentIndex = targetStackIndex
            root.activeTileIndex = idx
            root.transitionTitle = root.tileTitleForIndex(idx)
            root.clearHubModuleChooser()
            result = true
        } else {
            result = root.launchTileFromHome(idx, null)
        }

        if (targetState && typeof targetState === "object") {
            Qt.callLater(function() {
                root.applyStateToTile(idx, targetState)
                root.focusShellWindow()
            })
        }

        return result
    }

    function option3EnsureTabForCurrentWorkspace(reason) {
        if (!option3ShellEnabled) return false
        if (option3AutoEnsurePaused) return false
        if (!stack || stack.currentIndex <= 0) return false
        var idx = option3CurrentTileIndex()

        // Guard: if the active tab already belongs to this tile, do nothing.
        // This prevents a race where option3OpenWorkspace just created a tab
        // but the tile state hasn't synced yet, causing a duplicate with the
        // module's defaultNodeId.
        if (String(option3ActiveTabId || "").length > 0) {
            var activeIdx = option3FindTabIndexById(option3ActiveTabId)
            if (activeIdx >= 0) {
                var activeTab = option3OpenTabs[activeIdx]
                if (Math.round(activeTab.tileIndex) === idx) {
                    option3SyncOpenTabsFromPanels()
                    return true
                }
            }
        }

        var module = option3ModuleForTile(idx)
        var item = option3ItemForTile(idx, "")
        if (!module || !item) return false
        var state = option3StateForTile(idx)
        var tabParams = option3ParamsWithState({}, state)
        var existingIndex = option3FindTabIndexForItem(item, tabParams)
        if (existingIndex >= 0) {
            option3ActiveTabId = String(option3OpenTabs[existingIndex].id || "")
            option3SyncOpenTabsFromPanels()
            return true
        }
        var tabs = option3CopyOpenTabs()
        var tab = option3CreateTab(module, item, tabParams, !!(state && state.dirty))
        tabs.push(tab)
        option3OpenTabs = tabs
        option3ActiveTabId = String(tab.id || "")
        return true
    }


    function option3UpdateTabForState(tileIndex, state) {
        if (root.option3SuspendTabMutation) return false
        var idx = Math.round(tileIndex)
        var nodeId = state && state.focusNodeId !== undefined
            ? String(state.focusNodeId || "")
            : option3NodeIdForTile(idx)
        var module = option3ModuleForTile(idx)
        var item = option3ItemForTile(idx, nodeId)
        if (!module || !item) return false
        var tabParams = option3ParamsWithState({}, state || ({}))
        var identity = option3EntityIdentityForItem(item, tabParams)
        var tabIndex = option3FindTabIndexForItem(item, tabParams)
        var activeIndex = option3FindTabIndexById(option3ActiveTabId)
        if (activeIndex >= 0) {
            var activeTab = option3OpenTabs[activeIndex]
            if (Math.round(activeTab.tileIndex) === idx) {
                tabIndex = activeIndex
            }
        }
        if (tabIndex < 0) return false
        var tabs = option3CopyOpenTabs()
        tabs[tabIndex].title = option3TabTitleForItem(module, item, tabParams)
        tabs[tabIndex].nodeId = String(item.nodeId || item.id || "")
        tabs[tabIndex].saveCommand = String(item.saveCommand || "")
        tabs[tabIndex].entityType = String(identity.entityType || "")
        tabs[tabIndex].entityId = String(identity.entityId || "")
        tabs[tabIndex].entityTitle = String(identity.entityTitle || "")
        tabs[tabIndex].singleInstanceKey = option3TabKeyForItem(item, tabParams)
        tabs[tabIndex].dirty = !!(state && state.dirty)
        option3OpenTabs = tabs
        return true
    }

    function option3SyncOpenTabsFromPanels() {
        if (!option3ShellEnabled) return false
        var tabs = option3CopyOpenTabs()
        var changed = false
        for (var i = 0; i < tabs.length; i++) {
            var idx = Math.round(tabs[i].tileIndex)
            if (idx < 0) continue
            var snapshot = panelSnapshotForClose(idx)
            if (!snapshot || !snapshot.state) continue
            var snapshotNodeId = String(snapshot.state.focusNodeId || "")
            var isActiveTab = String(tabs[i].id || "") === String(option3ActiveTabId || "")
            var isActiveNode = snapshotNodeId === String(tabs[i].nodeId || "")
            if (!isActiveNode && !(isActiveTab && snapshotNodeId.length > 0)) continue

            if (tabs[i].dirty !== !!snapshot.state.dirty) {
                tabs[i].dirty = !!snapshot.state.dirty
                changed = true
            }
            var module = option3ModuleForTile(idx)
            var syncNodeId = snapshotNodeId.length > 0 ? snapshotNodeId : String(tabs[i].nodeId || "")
            var item = option3ItemForTile(idx, syncNodeId)
            if (module && item) {
                var tabParams = option3ParamsWithState({}, snapshot.state)
                var identity = option3EntityIdentityForItem(item, tabParams)
                var nextKey = option3TabKeyForItem(item, tabParams)
                var nextTitle = option3TabTitleForItem(module, item, tabParams)
                var nextSaveCommand = String(item.saveCommand || "")
                var nextNodeId = String(item.nodeId || item.id || syncNodeId || "")
                if (String(tabs[i].nodeId || "") !== nextNodeId
                        || String(tabs[i].entityType || "") !== String(identity.entityType || "")
                        || String(tabs[i].entityId || "") !== String(identity.entityId || "")
                        || String(tabs[i].entityTitle || "") !== String(identity.entityTitle || "")
                        || String(tabs[i].saveCommand || "") !== nextSaveCommand
                        || String(tabs[i].singleInstanceKey || "") !== String(nextKey || "")
                        || String(tabs[i].title || "") !== String(nextTitle || "")) {
                    console.warn("[SYNC_DEBUG] Tab changed! Index:", i,
                                 "nodeId:", tabs[i].nodeId, "->", nextNodeId,
                                 "title:", tabs[i].title, "->", nextTitle,
                                 "entityId:", tabs[i].entityId, "->", identity.entityId)
                    tabs[i].nodeId = nextNodeId
                    tabs[i].entityType = String(identity.entityType || "")
                    tabs[i].entityId = String(identity.entityId || "")
                    tabs[i].entityTitle = String(identity.entityTitle || "")
                    tabs[i].saveCommand = nextSaveCommand
                    tabs[i].singleInstanceKey = String(nextKey || "")
                    tabs[i].title = String(nextTitle || "")
                    changed = true
                }
            }
        }
        if (changed) option3OpenTabs = tabs
        return changed
    }

    function option3CloseWorkspaceTabForTile(tileIndex, nodeId, forceDiscard) {
        var idx = Math.round(tileIndex)
        var wantedNode = String(nodeId || "").trim()
        var tabs = option3OpenTabs || []
        for (var i = tabs.length - 1; i >= 0; i--) {
            if (Math.round(tabs[i].tileIndex) !== idx) continue
            if (wantedNode.length > 0 && String(tabs[i].nodeId || "") !== wantedNode) continue
            return option3CloseTab(String(tabs[i].id || ""), !!forceDiscard)
        }
        return false
    }

    function option3CloseTab(tabId, forceDiscard) {
        var index = option3FindTabIndexById(tabId)
        if (index < 0) return false
        var tab = option3OpenTabs[index]
        if (tab && tab.dirty && !forceDiscard) {
            if (String(tab.saveCommand || "").length > 0) {
                option3CloseGuardTabId = String(tab.id || "")
                option3CloseGuardMessage = "Unsaved changes in " + String(tab.title || "this workspace")
                return false
            }
        }
        var tabs = option3CopyOpenTabs()
        tabs.splice(index, 1)
        option3OpenTabs = tabs
        if (String(option3ActiveTabId || "") === String(tabId || "")) {
            if (tabs.length > 0) {
                var nextIndex = Math.max(0, Math.min(index, tabs.length - 1))
                option3ActiveTabId = String(tabs[nextIndex].id || "")
                option3ActivateTab(option3ActiveTabId)
            } else {
                option3ActiveTabId = ""
                option3EnsureTabForCurrentWorkspace("close-last-tab")
            }
        }
        if (typeof proAppShell !== "undefined" && typeof proAppShell.saveState === "function") {
            proAppShell.saveState()
        }
        return true
    }

    function option3RemoveTabForDetachedWindow(tabId) {
        var index = option3FindTabIndexById(tabId)
        if (index < 0) return false

        var removedWasActive = String(option3ActiveTabId || "") === String(tabId || "")
        var tabs = option3CopyOpenTabs()
        tabs.splice(index, 1)
        option3OpenTabs = tabs
        option3CloseGuardTabId = ""
        option3CloseGuardMessage = ""
        
        if (typeof proAppShell !== "undefined" && typeof proAppShell.saveState === "function") {
            proAppShell.saveState()
        }

        if (!removedWasActive) return true
        if (tabs.length > 0) {
            var nextIndex = Math.max(0, Math.min(index, tabs.length - 1))
            option3ActiveTabId = String(tabs[nextIndex].id || "")
            option3ActivateTab(option3ActiveTabId, false)
        } else {
            option3SetEmptyWorkspace("detach-last-tab")
        }
        return true
    }

    function option3StateWithoutDetachedTabMetadata(state) {
        var clean = root.shallowCloneObject(state || ({}))
        if (clean._option3DetachedTab !== undefined) delete clean._option3DetachedTab
        return clean
    }

    function option3DetachedTabMetadataFromState(state) {
        if (state && typeof state === "object" && state._option3DetachedTab && typeof state._option3DetachedTab === "object") {
            return root.shallowCloneObject(state._option3DetachedTab)
        }
        if (root.detachedWindow
            && root.initialPanelState
            && typeof root.initialPanelState === "object"
            && root.initialPanelState._option3DetachedTab
            && typeof root.initialPanelState._option3DetachedTab === "object") {
            return root.shallowCloneObject(root.initialPanelState._option3DetachedTab)
        }
        return null
    }

    function option3CreateReturnedDockTab(tileIndex, state) {
        if (!option3ShellEnabled) return ""
        var idx = Math.round(tileIndex)
        if (idx < -1 || idx >= tileTitles.length) return ""

        var panelState = option3StateWithoutDetachedTabMetadata(state || ({}))
        var nodeId = panelState && panelState.focusNodeId !== undefined
            ? String(panelState.focusNodeId || "")
            : option3NodeIdForTile(idx)
        var module = option3ModuleForTile(idx)
        var item = option3ItemForTile(idx, nodeId)
        if (!module || !item) return ""

        var tabParams = option3ParamsWithState({}, panelState)
        var identity = option3EntityIdentityForItem(item, tabParams)
        var detachedTab = option3DetachedTabMetadataFromState(state || ({}))
        var nextTab = detachedTab ? root.shallowCloneObject(detachedTab) : option3CreateTab(module, item, tabParams, !!panelState.dirty)
        var baseId = String(nextTab.id || option3TabIdForKey(nextTab.singleInstanceKey || option3TabKeyForItem(item, tabParams)))
        nextTab.id = option3UniqueTabId(baseId)
        nextTab.title = option3TabTitleForItem(module, item, tabParams)
        nextTab.moduleId = String(module.moduleId || nextTab.moduleId || "")
        nextTab.moduleTitle = String(module.title || nextTab.moduleTitle || "")
        nextTab.tileIndex = idx
        nextTab.nodeId = String(item.nodeId || item.id || nodeId || "")
        nextTab.route = String(item.route || nextTab.route || "")
        nextTab.tabType = String(item.tabType || nextTab.tabType || "screen")
        nextTab.saveCommand = String(item.saveCommand || nextTab.saveCommand || "")
        nextTab.entityType = String(identity.entityType || "")
        nextTab.entityId = String(identity.entityId || "")
        nextTab.entityTitle = String(identity.entityTitle || "")
        nextTab.singleInstanceKey = String(option3TabKeyForItem(item, tabParams))
        nextTab.dirty = !!panelState.dirty
        nextTab.pinned = !!nextTab.pinned

        var tabs = option3CopyOpenTabs()
        tabs.push(nextTab)
        option3OpenTabs = tabs
        option3ActiveTabId = String(nextTab.id || "")
        return option3ActiveTabId
    }

    function option3OpenTabInNewWindow(tabId) {
        if (root.detachedWindow) return false
        var index = option3FindTabIndexById(tabId)
        if (index < 0) return false
        var tab = option3OpenTabs[index]
        var idx = Math.round(tab.tileIndex)
        if (idx < -1 || idx >= tileTitles.length) return false

        var state = root.shallowCloneObject(option3StateForTile(idx))
        state.tileIndex = idx
        state.titleText = String(tab.title || tileTitleForIndex(idx))
        state.focusNodeId = String(tab.nodeId || "")
        state.focusNodeTitle = String(tab.title || "")
        state = option3ApplyTabEntityToState(tab, state)
        state._option3DetachedTab = root.shallowCloneObject(tab)

        var originRect = fallbackGlobalLaunchRectForTile(idx)
        option3RemoveTabForDetachedWindow(tabId)
        option3FlyoutModuleId = ""
        tearAwayRequested(idx, String(tab.title || tileTitleForIndex(idx)), state, originRect)
        return true
    }

    function option3ItemForTab(tab) {
        if (!tab) return null
        return option3ItemForTile(Math.round(tab.tileIndex), String(tab.nodeId || ""))
    }

    function option3SaveCommandForTab(tab) {
        var explicitCommand = String(tab && tab.saveCommand ? tab.saveCommand : "").trim()
        if (explicitCommand.length > 0) return explicitCommand

        var item = option3ItemForTab(tab)
        var itemCommand = String(item && item.saveCommand ? item.saveCommand : "").trim()
        if (itemCommand.length > 0) return itemCommand

        var nodeId = String(tab && tab.nodeId ? tab.nodeId : "").trim()
        if (nodeId === "B01" || nodeId === "B03") return "time-docket"
        if (nodeId === "B02") return "fee-docket"
        if (nodeId === "B08") return "deadline-entry"
        if (nodeId === "B16") return "trademark-filing"
        if (nodeId === "A02" || nodeId === "A03") return "client-profile"
        if (nodeId === "A10" || nodeId === "A11") return "matter-profile"
        if (nodeId === "C11") return "transaction"
        return "primary-action"
    }

    function option3ActivateGuardedTabForSave(tab) {
        if (!tab) return false
        var tabId = String(tab.id || "")
        if (tabId.length <= 0) return false
        var currentState = option3StateForTile(Math.round(tab.tileIndex))
        if (String(option3ActiveTabId || "") !== tabId
                || String(currentState.focusNodeId || "") !== String(tab.nodeId || "")) {
            return option3ActivateTab(tabId)
        }
        return true
    }

    function option3DispatchSaveCommand(panel, command, tab) {
        var saveCommand = String(command || "").trim()
        if (!panel || saveCommand.length <= 0) return false

        if (panel.requestOption3Save) {
            return !!panel.requestOption3Save(saveCommand, tab || ({}))
        }

        if (saveCommand === "time-docket" && panel.requestSaveToDatabaseIfNeeded) {
            var docketResult = panel.requestSaveToDatabaseIfNeeded("option3-tab-close")
            return !!(docketResult && docketResult.ok && docketResult.verifiedExact)
        }
        if (saveCommand === "deadline-entry" && panel.saveEditing) {
            panel.saveEditing()
            return true
        }
        if (saveCommand === "client-profile" && panel.trySaveClientProfile) {
            panel.trySaveClientProfile(false)
            return true
        }
        if (saveCommand === "matter-profile" && panel.trySaveMatterProfile) {
            panel.trySaveMatterProfile()
            return true
        }
        if (saveCommand === "primary-action" && panel.requestPrimaryAction) {
            panel.requestPrimaryAction()
            return true
        }
        return false
    }

    function option3AttemptSaveGuardedTab() {
        var index = option3FindTabIndexById(option3CloseGuardTabId)
        if (index < 0) return false
        var tab = option3OpenTabs[index]
        if (!option3ActivateGuardedTabForSave(tab)) return false
        var panel = panelRefForTile(Math.round(tab.tileIndex))
        if (!panel) return false
        var ok = false
        try {
            ok = option3DispatchSaveCommand(panel, option3SaveCommandForTab(tab), tab)
        } catch (e0) {
            ok = false
        }
        option3SyncOpenTabsFromPanels()
        return ok
    }

    function option3TryCompletePendingCloseAfterSave() {
        var tabId = String(option3PendingCloseAfterSaveTabId || "")
        if (tabId.length <= 0) return false

        option3SyncOpenTabsFromPanels()
        var index = option3FindTabIndexById(tabId)
        if (index < 0) {
            option3PendingCloseAfterSaveTabId = ""
            option3CloseGuardTabId = ""
            option3CloseGuardMessage = ""
            return false
        }

        var tab = option3OpenTabs[index]
        var panel = panelRefForTile(Math.round(tab.tileIndex))
        var isDirty = panel ? !!panel.dirty : !!(tab && tab.dirty)
        if (isDirty) return false

        option3PendingCloseAfterSaveTabId = ""
        option3CloseGuardTabId = ""
        option3CloseGuardMessage = ""
        return option3CloseTab(tabId, true)
    }

    function option3SaveGuardedTabAndCloseIfClean() {
        var tabId = String(option3CloseGuardTabId || "")
        if (tabId.length <= 0) return false
        if (!option3AttemptSaveGuardedTab()) return false

        option3PendingCloseAfterSaveTabId = tabId
        return option3TryCompletePendingCloseAfterSave()
    }

    function laneSummaryForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        var s = dashboardSummary || ({})
        var activeClients = Math.max(0, Number(s.activeClientCount || 0))
        var activeMatters = Math.max(0, Number(s.activeMatterCount || 0))
        var deadlines = Math.max(0, Number(s.deadlinesCount || 0))
        var drafts = Math.max(0, Number(s.unbilledDraftCount || 0))
        var queue = Math.max(0, Number(s.queueCount || (deadlines + drafts)))
        if (idx === 0) {
            return {
                "headline": "Active Matters: " + String(activeMatters) +
                            " (Clients: " + String(activeClients) + ")",
                "lineA": "Manage your firm's clients and matters",
                "lineB": "Entity search enabled for clients, matters, parents"
            }
        }
        if (idx === 1) {
            return {
                "headline": "Deadlines: " + String(deadlines),
                "lineA": "Time Docket Entry is live",
                "lineB": "Deadline/tickler pathway scaffolded"
            }
        }
        if (idx === 2) {
            return {
                "headline": "Unbilled Drafts: " + String(drafts),
                "lineA": "Invoices/payments/expenses/HST lanes staged",
                "lineB": "Invoice-number lookup routing enabled"
            }
        }
        return {
            "headline": "Queue Items: " + String(queue),
            "lineA": "Dashboards, ledgers, A/R, WIP, forecasting",
            "lineB": "Cross-cutting ops/tools included"
        }
    }

    function startupAllowsHeavyWork(reason) {
        if (root.windowRef && root.windowRef.startupAllowsHeavyWork) {
            return root.windowRef.startupAllowsHeavyWork("MainContent." + String(reason || "unspecified"))
        }
        return true
    }

    function startupQueueEnabled() {
        return !!(root.windowRef
            && root.windowRef.startupDeferredQueueEnabledForClients
            && root.windowRef.enqueuePostSettleTask)
    }

    function startupHeavyWorkDelayMs(defaultMs) {
        var fallback = (typeof defaultMs === "number") ? Math.max(40, Math.round(defaultMs)) : 180
        if (root.windowRef && root.windowRef.startupHeavyWorkDelayMs) {
            var delayMs = Number(root.windowRef.startupHeavyWorkDelayMs())
            if (isFinite(delayMs)) {
                return Math.max(20, Math.round(delayMs))
            }
        }
        return fallback
    }

    function scheduleDashboardSummaryRefresh(reason) {
        if (root._startupDashboardRefreshPending) return
        root._startupDashboardRefreshPending = true
        if (startupQueueEnabled()) {
            if (root.windowRef.enqueuePostSettleTask(
                "MainContent.refreshDashboardSummary",
                root,
                "_runQueuedDashboardSummaryRefreshTask",
                { "reason": String(reason || "unspecified") },
                true
            )) {
                return
            }
        }
        startupDashboardRetryTimer.stop()
        startupDashboardRetryTimer.interval = startupHeavyWorkDelayMs(root._startupDashboardRetryMs)
        startupDashboardRetryTimer.start()
    }

    function _runQueuedDashboardSummaryRefreshTask(payload) {
        if (!root.visible) return false
        if (!startupAllowsHeavyWork("refreshDashboardSummary.queued")) {
            return false
        }
        root._startupDashboardRefreshPending = false
        root.refreshDashboardSummaryNow()
        return true
    }

    function refreshDashboardSummaryNow() {
        if (!appRef || !appRef.getHomeDashboardSummary) return
        try {
            var payload = appRef.getHomeDashboardSummary()
            if (payload && typeof payload === "object" && payload.ok !== undefined) {
                dashboardSummary = payload
            }
        } catch (e0) {
        }
    }

    function refreshDashboardSummary() {
        if (!startupAllowsHeavyWork("refreshDashboardSummary")) {
            scheduleDashboardSummaryRefresh("guard-blocked")
            return
        }
        root._startupDashboardRefreshPending = false
        refreshDashboardSummaryNow()
    }

    function isStackPageLoadRequested(stackIndex) {
        var idx = Math.round(stackIndex)
        if (idx <= 0) return true
        if (stack && stack.currentIndex === idx) return true
        var key = String(idx)
        return !!(_stackPageLoadRequested && _stackPageLoadRequested[key] === true)
    }

    function requestStackPageLoad(stackIndex, reason) {
        var idx = Math.round(stackIndex)
        if (idx <= 0) return false
        if (idx > tileTitles.length) return false
        if (isStackPageLoadRequested(idx)) return false

        var nextFlags = {}
        if (_stackPageLoadRequested) {
            for (var k in _stackPageLoadRequested) {
                if (_stackPageLoadRequested.hasOwnProperty(k)) {
                    nextFlags[k] = _stackPageLoadRequested[k]
                }
            }
        }
        nextFlags[String(idx)] = true
        _stackPageLoadRequested = nextFlags
        if (root.windowRef && root.windowRef.lagLog) {
            root.windowRef.lagLog("MainContent stack page load requested index="
                + idx + " reason=" + String(reason || "unspecified"))
        }
        return true
    }

    function scheduleStartupStackPrewarm(reason) {
        if (root.detachedWindow || _startupPrewarmComplete) return
        if (startupQueueEnabled()) {
            queueStartupStackPrewarm(reason)
            return
        }
        if (startupStackPrewarmTimer.running) return
        startupStackPrewarmTimer.interval = Math.max(100, _startupPrewarmStepMs)
        startupStackPrewarmTimer.start()
    }

    function queueStartupStackPrewarm(reason) {
        if (!startupQueueEnabled()) return
        if (root.detachedWindow || _startupPrewarmComplete) return
        if (_startupPrewarmQueuedToWindow) return

        var order = _startupPrewarmStackOrder
        var queuedAny = false
        while (_startupPrewarmStackCursor < order.length) {
            var nextStackIdx = Math.round(order[_startupPrewarmStackCursor])
            _startupPrewarmStackCursor += 1
            if (nextStackIdx <= 0 || nextStackIdx > tileTitles.length) continue
            if (isStackPageLoadRequested(nextStackIdx)) continue
            if (root.windowRef.enqueuePostSettleTask(
                "MainContent.stackPrewarm." + String(nextStackIdx),
                root,
                "_runQueuedStartupStackPrewarmTask",
                { "stackIndex": nextStackIdx, "reason": String(reason || "startup-prewarm") },
                true
            )) {
                queuedAny = true
            }
        }
        _startupPrewarmQueuedToWindow = queuedAny
        _startupPrewarmComplete = (_startupPrewarmStackCursor >= order.length)
    }

    function _runQueuedStartupStackPrewarmTask(payload) {
        if (root.detachedWindow) return true
        if (!root.visible || !stack) return false
        if (!startupAllowsHeavyWork("startupStackPrewarm.queued")) return false
        var idx = Math.round(payload && payload.stackIndex !== undefined ? payload.stackIndex : -1)
        if (idx <= 0 || idx > tileTitles.length) return true
        requestStackPageLoad(idx, "startup-prewarm")
        return true
    }

    function runStartupStackPrewarmTick() {
        if (root.detachedWindow || _startupPrewarmComplete) return
        if (startupQueueEnabled()) {
            queueStartupStackPrewarm("runStartupStackPrewarmTick")
            return
        }
        if (!root.visible || !stack) {
            scheduleStartupStackPrewarm("not-visible")
            return
        }
        if (root.windowRef && root.windowRef.startupHeavyWorkAllowed === false) {
            startupStackPrewarmTimer.interval = startupHeavyWorkDelayMs(_startupPrewarmStepMs)
            startupStackPrewarmTimer.start()
            return
        }
        if (!startupAllowsHeavyWork("startupStackPrewarm")) {
            startupStackPrewarmTimer.interval = startupHeavyWorkDelayMs(_startupPrewarmStepMs)
            startupStackPrewarmTimer.start()
            return
        }

        var order = _startupPrewarmStackOrder
        while (_startupPrewarmStackCursor < order.length) {
            var nextStackIdx = Math.round(order[_startupPrewarmStackCursor])
            _startupPrewarmStackCursor += 1
            if (requestStackPageLoad(nextStackIdx, "startup-prewarm")) {
                startupStackPrewarmTimer.interval = Math.max(120, _startupPrewarmStepMs)
                startupStackPrewarmTimer.start()
                return
            }
        }
        _startupPrewarmComplete = true
    }

    function stackIndexForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return 0
        return idx + 1
    }

    function tileIndexForStack(stackIndex) {
        var idx = Math.round(stackIndex) - 1
        if (idx < 0 || idx >= tileTitles.length) return -1
        return idx
    }

    function isValidGlobalRect(r) {
        return r
            && typeof r.x === "number"
            && typeof r.y === "number"
            && typeof r.width === "number"
            && typeof r.height === "number"
            && isFinite(r.x)
            && isFinite(r.y)
            && isFinite(r.width)
            && isFinite(r.height)
            && r.width > 0
            && r.height > 0
    }

    function rememberTileGeometry(tileIndex, tileGlobalGeom) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return
        if (!isValidGlobalRect(tileGlobalGeom)) return
        var nextMap = tileLaunchGeometryByIndex ? tileLaunchGeometryByIndex : ({})
        nextMap[idx] = Qt.rect(tileGlobalGeom.x, tileGlobalGeom.y, tileGlobalGeom.width, tileGlobalGeom.height)
        tileLaunchGeometryByIndex = nextMap
    }

    function resolveTileLocalRect(tileGlobalGeom, tileIndex) {
        var bodyW = Math.max(1, bodyHost.width)
        var bodyH = Math.max(1, bodyHost.height)
        var solved = {
            "x": Math.round(bodyW * 0.32),
            "y": Math.round(bodyH * 0.30),
            "w": Math.max(1, ratioPx(scaleRatios.portalBaseDiameterPct * 1.72, 64)),
            "h": Math.max(1, ratioPx(scaleRatios.portalBaseDiameterPct * 0.94, 42))
        }
        var idx = Math.round(tileIndex)
        var sourceRect = tileGlobalGeom
        if (!isValidGlobalRect(sourceRect)
            && tileLaunchGeometryByIndex
            && idx >= 0
            && idx < tileTitles.length
            && tileLaunchGeometryByIndex[idx]
            && isValidGlobalRect(tileLaunchGeometryByIndex[idx])) {
            sourceRect = tileLaunchGeometryByIndex[idx]
        }

        if (isValidGlobalRect(sourceRect)) {
            var mapped = false
            if (bodyHost.mapFromGlobal) {
                try {
                    var localTopLeft = bodyHost.mapFromGlobal(sourceRect.x, sourceRect.y)
                    var localBottomRight = bodyHost.mapFromGlobal(sourceRect.x + sourceRect.width, sourceRect.y + sourceRect.height)
                    if (localTopLeft
                        && localBottomRight
                        && isFinite(localTopLeft.x)
                        && isFinite(localTopLeft.y)
                        && isFinite(localBottomRight.x)
                        && isFinite(localBottomRight.y)) {
                        solved.x = Math.min(localTopLeft.x, localBottomRight.x)
                        solved.y = Math.min(localTopLeft.y, localBottomRight.y)
                        solved.w = Math.max(1, Math.abs(localBottomRight.x - localTopLeft.x))
                        solved.h = Math.max(1, Math.abs(localBottomRight.y - localTopLeft.y))
                        mapped = true
                    }
                } catch (e) {
                }
            }
            if (!mapped) {
                solved.w = Math.max(solved.w, Math.round(sourceRect.width))
                solved.h = Math.max(solved.h, Math.round(sourceRect.height))
            }
        }

        solved.w = Math.max(ratioPx(scaleRatios.portalBaseDiameterPct * 1.72, 64), solved.w)
        solved.h = Math.max(ratioPx(scaleRatios.portalBaseDiameterPct * 0.94, 42), solved.h)
        solved.x = Math.max((-0.3 * solved.w), Math.min(bodyW - (0.7 * solved.w), solved.x))
        solved.y = Math.max((-0.3 * solved.h), Math.min(bodyH - (0.7 * solved.h), solved.y))
        return solved
    }

    function fallbackGlobalLaunchRectForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        var baseW = Math.max(1, ratioPx(scaleRatios.portalBaseDiameterPct * 1.72, 64))
        var baseH = Math.max(1, ratioPx(scaleRatios.portalBaseDiameterPct * 0.94, 42))
        var bodyW = Math.max(1, bodyHost ? bodyHost.width : root.width)
        var bodyH = Math.max(1, bodyHost ? bodyHost.height : root.height)
        var localRect = resolveTileLocalRect(null, idx)
        var localCenterX = localRect.x + (localRect.w * 0.5)
        var localCenterY = localRect.y + (localRect.h * 0.5)

        if (bodyHost && bodyHost.mapToGlobal) {
            try {
                var gp = bodyHost.mapToGlobal(localCenterX, localCenterY)
                if (gp && isFinite(gp.x) && isFinite(gp.y)) {
                    return Qt.rect(
                        Math.round(gp.x - (Math.max(baseW, localRect.w) * 0.5)),
                        Math.round(gp.y - (Math.max(baseH, localRect.h) * 0.5)),
                        Math.max(1, Math.round(Math.max(baseW, localRect.w))),
                        Math.max(1, Math.round(Math.max(baseH, localRect.h)))
                    )
                }
            } catch (e) {
            }
        }

        var fallbackX = (root.windowRef && typeof root.windowRef.x === "number") ? root.windowRef.x : 0
        var fallbackY = (root.windowRef && typeof root.windowRef.y === "number") ? root.windowRef.y : 0
        return Qt.rect(
            Math.round(fallbackX + ((bodyW - baseW) * 0.5)),
            Math.round(fallbackY + ((bodyH - baseH) * 0.5)),
            baseW,
            baseH
        )
    }

    function launchTileFromHome(tileIndex, tileGlobalGeom) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return false
        if (root.option3ShellEnabled) {
            return option3OpenWorkspaceForTile(idx, "")
        }
        var targetIndex = stackIndexForTile(idx)
        if (targetIndex <= 0) return false
        if (!startPortalBlobTransition(targetIndex, tileGlobalGeom, idx)) {
            stack.currentIndex = targetIndex
            activeTileIndex = idx
            transitionTitle = tileTitleForIndex(idx)
        }
        return true
    }

    function normalizedHubModules(moduleIndexes) {
        var resolved = []
        if (!moduleIndexes || moduleIndexes.length === undefined) return resolved
        for (var i = 0; i < moduleIndexes.length; i++) {
            var idx = Math.round(moduleIndexes[i])
            if (idx < 0 || idx >= tileTitles.length) continue
            var duplicate = false
            for (var j = 0; j < resolved.length; j++) {
                if (resolved[j] === idx) {
                    duplicate = true
                    break
                }
            }
            if (!duplicate) {
                resolved.push(idx)
            }
        }
        return resolved
    }

    function clearHubModuleChooser() {
        hubModuleChooserVisible = false
        hubModuleChooserRows = []
        hubModuleChooserHubIndex = -1
        hubModuleChooserOriginRect = Qt.rect(0, 0, 0, 0)
    }

    function openHubSelection(hubIndex, moduleIndexes, tileGlobalGeom) {
        var hubIdx = Math.round(hubIndex)
        var rows = normalizedHubModules(moduleIndexes)
        if (rows.length <= 0) return false
        if (rows.length === 1) {
            clearHubModuleChooser()
            return launchTileFromHome(rows[0], tileGlobalGeom)
        }

        var chooserRows = []
        for (var i = 0; i < rows.length; i++) {
            var tileIdx = rows[i]
            chooserRows.push({
                "tileIndex": tileIdx,
                "titleText": tileTitleForIndex(tileIdx)
            })
        }
        hubModuleChooserRows = chooserRows
        hubModuleChooserHubIndex = hubIdx
        if (isValidGlobalRect(tileGlobalGeom)) {
            hubModuleChooserOriginRect = Qt.rect(
                tileGlobalGeom.x,
                tileGlobalGeom.y,
                tileGlobalGeom.width,
                tileGlobalGeom.height
            )
        } else {
            hubModuleChooserOriginRect = fallbackGlobalLaunchRectForTile(chooserRows[0].tileIndex)
        }
        hubModuleChooserVisible = true
        return true
    }

    function launchHubChooserRow(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return false
        var geom = hubModuleChooserOriginRect
        clearHubModuleChooser()
        return launchTileFromHome(idx, geom)
    }

    function handleOmniSearch(queryText) {
        var query = String(queryText || "").trim()
        if (query.length <= 0) return false

        if (appRef && appRef.handleOmniSearchCommand) {
            try {
                var routed = appRef.handleOmniSearchCommand(query)
                if (routed && routed.ok && typeof routed.tileIndex === "number") {
                    var idx = Math.round(routed.tileIndex)
                    if (idx >= 0 && idx < tileTitles.length) {
                        var routeState = snapshotStateForTile(idx)
                        if (!routeState || typeof routeState !== "object") {
                            routeState = {}
                        }
                        var routedQuery = (routed.queryText !== undefined)
                            ? String(routed.queryText || "").trim()
                            : String(query || "").trim()
                        routeState.omniQuery = routedQuery
                        if (routed.queryType !== undefined) {
                            routeState.omniQueryType = String(routed.queryType)
                        }
                        if (String(routed.queryType || "") === "client_lookup") {
                            routeState.clientDirectoryQueryText = routeState.omniQuery
                            routeState.clientDirectoryModeText = "all"
                        }
                        if (String(routed.queryType || "") === "matter_lookup") {
                            routeState.selectedMatterName = routeState.omniQuery
                            routeState.selectedMatterId = ""
                            routeState.matterDirectoryQueryText = routeState.omniQuery
                            routeState.matterDirectoryModeText = "all"
                        }
                        if (String(routed.queryType || "") === "top_result") {
                            var entityType = String(routed.entityType || "").trim().toLowerCase()
                            routeState.topSearchResultEntityType = entityType
                            routeState.topSearchResultTitle = String(routed.title || "")
                            routeState.topSearchResultId = String(routed.entityId || "")
                            if (entityType === "client") {
                                routeState.selectedClientId = String(routed.clientId || routed.entityId || "")
                                routeState.selectedClientName = String(routed.clientName || routed.title || "")
                                routeState.clientProfileAutoLoadKey = routeState.selectedClientId.length > 0
                                    ? routeState.selectedClientId
                                    : routeState.selectedClientName
                                routeState.autoLoadClientProfile = true
                                routeState.clientDirectoryQueryText = String(routed.clientName || routed.title || routeState.omniQuery)
                                routeState.clientDirectoryModeText = "all"
                            } else if (entityType === "matter") {
                                routeState.selectedMatterId = String(routed.matterId || routed.entityId || "")
                                routeState.selectedMatterName = String(routed.matterName || routed.displayName || routed.title || "")
                                routeState.matterDirectoryQueryText = String(routed.title || routed.matterName || routeState.omniQuery)
                                routeState.matterDirectoryModeText = "all"
                            } else if (entityType === "transaction"
                                || entityType === "account"
                                || entityType === "category"
                                || entityType === "business_unit"
                                || entityType === "payee") {
                                routeState.transactionSearchQueryText = String(routed.title || routed.entityId || routeState.omniQuery)
                                routeState.transactionSearchEntityType = entityType
                                routeState.transactionSearchEntityId = String(routed.entityId || "")
                            }
                        }
                        if (String(routed.queryType || "") === "global_lookup") {
                            routeState.globalSearchModeText = "any"
                            routeState.globalSearchFilterText = "all"
                        }
                        if (routed.subwindowId !== undefined && String(routed.subwindowId).trim().length > 0) {
                            routeState.focusNodeId = String(routed.subwindowId).trim()
                        }
                        if (routed.subwindowTitle !== undefined && String(routed.subwindowTitle).trim().length > 0) {
                            routeState.focusNodeTitle = String(routed.subwindowTitle).trim()
                        }
                        applyStateToTile(idx, routeState)
                        if (root.option3ShellEnabled) {
                            var focusNode = String(routeState.focusNodeId || "").trim()
                            var searchParams = root.shallowCloneObject(routeState)
                            option3OpenWorkspaceForTile(idx, focusNode, searchParams)
                            return true
                        }
                    }
                    return launchTileFromHome(routed.tileIndex, null)
                }
            } catch (e0) {
            }
        }

        var q = query.toLowerCase()
        for (var i = 0; i < tileTitles.length; i++) {
            var title = String(tileTitles[i] || "").toLowerCase()
            if (title.indexOf(q) >= 0) {
                applyStateToTile(i, { "omniQuery": query, "omniQueryType": "lane" })
                return launchTileFromHome(i, null)
            }
        }
        return false
    }

    function requestTearAwayForTile(tileIndex, state) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) {
            idx = activeTileIndex
        }
        if (idx < 0 || idx >= tileTitles.length) {
            idx = 0
        }
        var globalRect = null
        if (tileLaunchGeometryByIndex && tileLaunchGeometryByIndex[idx] && isValidGlobalRect(tileLaunchGeometryByIndex[idx])) {
            var knownRect = tileLaunchGeometryByIndex[idx]
            globalRect = Qt.rect(knownRect.x, knownRect.y, knownRect.width, knownRect.height)
        } else {
            globalRect = fallbackGlobalLaunchRectForTile(idx)
        }
        tearAwayRequested(idx, tileTitleForIndex(idx), state, globalRect)
    }

    function windowContentGlobalRect() {
        if (root.windowRef
            && typeof root.windowRef.finalX === "number"
            && typeof root.windowRef.finalY === "number"
            && typeof root.windowRef.finalW === "number"
            && typeof root.windowRef.finalH === "number"
            && isFinite(root.windowRef.finalX)
            && isFinite(root.windowRef.finalY)
            && isFinite(root.windowRef.finalW)
            && isFinite(root.windowRef.finalH)
            && root.windowRef.finalW > 0
            && root.windowRef.finalH > 0) {
            return Qt.rect(
                Math.round(root.windowRef.finalX),
                Math.round(root.windowRef.finalY),
                Math.round(root.windowRef.finalW),
                Math.round(root.windowRef.finalH)
            )
        }
        return null
    }

    function shallowCloneObject(sourceObj) {
        var clone = {}
        if (!sourceObj || typeof sourceObj !== "object") return clone
        for (var key in sourceObj) {
            if (sourceObj.hasOwnProperty(key)) {
                clone[key] = sourceObj[key]
            }
        }
        return clone
    }

    function panelRefForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx === 0) {
            return clientsLanePanelLoader.item
        }
        if (idx === 1) {
            return docketLanePanelLoader.item
        }
        if (idx === 2) {
            return billingLanePanelLoader.item
        }
        if (idx === 3) {
            return financeLanePanelLoader.item
        }
        return null
    }

    function snapshotStateForTile(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return {}
        var snapshot = panelSnapshotForClose(idx)
        if (snapshot && snapshot.state && typeof snapshot.state === "object") {
            return snapshot.state
        }
        return {}
    }

    function requestUndockFromActiveModule(sourceRect) {
        if (detachedWindow || !stack || stack.currentIndex <= 0) return false
        var idx = tileIndexForStack(stack.currentIndex)
        if (idx < 0 || idx >= tileTitles.length) return false

        var originRect = sourceRect
        if (!isValidGlobalRect(originRect)) {
            originRect = fallbackGlobalLaunchRectForTile(idx)
        }
        var state = snapshotStateForTile(idx)

        if (appRef && appRef.recordUndockRequest) {
            try {
                appRef.recordUndockRequest({
                    "tileIndex": idx,
                    "titleText": tileTitleForIndex(idx),
                    "originX": originRect.x,
                    "originY": originRect.y,
                    "originW": originRect.width,
                    "originH": originRect.height
                })
            } catch (e0) {
            }
        }

        undockRequested(idx, tileTitleForIndex(idx), state, originRect)
        return true
    }

    function panelSnapshotForClose(tileIndex) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return null

        var livePanel = panelRefForTile(idx)
        var liveState = null
        if (livePanel) {
            try {
                if (livePanel.snapshotState) {
                    liveState = livePanel.snapshotState()
                }
            } catch (e0) {
            }
        }

        var cachedState = null
        if (dockedStateByTile && dockedStateByTile[idx] !== undefined) {
            cachedState = dockedStateByTile[idx]
        }

        function stateIsReportingView(state) {
            if (!state || typeof state !== "object") return false
            var focusTitle = String(state.focusNodeTitle || "").trim().toLowerCase()
            if (focusTitle.length <= 0) return false
            return (
                focusTitle.indexOf("report") >= 0
                || focusTitle.indexOf("dashboard") >= 0
                || focusTitle.indexOf("analytics") >= 0
                || focusTitle.indexOf("summary") >= 0
            )
        }

        // Helper: inspect a snapshot object for any non-default user-entered data
        function stateHasUserData(state) {
            if (!state || typeof state !== "object") return false
            // Reporting screens are read-only analysis surfaces and should never trip close guards.
            if (stateIsReportingView(state)) {
                return false
            }
            // Close guard should trust each panel's explicit dirty signal only.
            return state.dirty !== undefined ? !!state.dirty : false
        }

        // Prefer live panel state; only fall back to cached state when no live snapshot exists.
        var effectiveState = null
        if (liveState && typeof liveState === "object") {
            effectiveState = liveState
        } else if (cachedState && typeof cachedState === "object") {
            effectiveState = cachedState
        }

        var hasUnsaved = stateHasUserData(effectiveState)
        var hasRunningTimer = false
        if (livePanel) {
            try { hasRunningTimer = !!livePanel.isRunning } catch (e1) { }
        }
        if (!hasRunningTimer && effectiveState && typeof effectiveState === "object") {
            hasRunningTimer = !!effectiveState.isRunning
        }
        // Report/dashboard surfaces should never trigger close guard risk.
        if (stateIsReportingView(effectiveState)) {
            hasRunningTimer = false
        }

        var mergedState = shallowCloneObject(cachedState)
        if (liveState && typeof liveState === "object") {
            for (var key in liveState) {
                if (liveState.hasOwnProperty(key)) {
                    mergedState[key] = liveState[key]
                }
            }
        }
        // indicate panel should be considered "dirty" only if there is actual data
        mergedState.dirty = !!hasUnsaved
        if (idx === 0 || mergedState.isRunning !== undefined || hasRunningTimer) {
            mergedState.isRunning = !!hasRunningTimer
        }

        return {
            "tileIndex": idx,
            "titleText": tileTitleForIndex(idx),
            "hasUnsavedWork": !!hasUnsaved,
            "hasRunningTimer": !!hasRunningTimer,
            "state": mergedState
        }
    }

    // Collect a cross-panel snapshot for close guards and save-on-exit.
    function gatherCloseSessionSnapshot(updateCache) {
        var snapshots = []
        var nextStateMap = {}
        if (dockedStateByTile) {
            for (var key in dockedStateByTile) {
                if (dockedStateByTile.hasOwnProperty(key)) {
                    nextStateMap[key] = dockedStateByTile[key]
                }
            }
        }

        var hasUnsaved = false
        var hasRunningTimer = false
        for (var idx = 0; idx < tileTitles.length; idx++) {
            var panelSnapshot = panelSnapshotForClose(idx)
            if (!panelSnapshot) continue
            snapshots.push(panelSnapshot)
            nextStateMap[idx] = panelSnapshot.state
            if (panelSnapshot.hasUnsavedWork) hasUnsaved = true
            if (panelSnapshot.hasRunningTimer) hasRunningTimer = true
        }

        if (updateCache) {
            dockedStateByTile = nextStateMap
        }

        var resolvedActiveIdx = -1
        if (stack && stack.currentIndex > 0) {
            resolvedActiveIdx = tileIndexForStack(stack.currentIndex)
        } else if (activeTileIndex >= 0 && activeTileIndex < tileTitles.length) {
            resolvedActiveIdx = activeTileIndex
        }
        if (resolvedActiveIdx < 0 || resolvedActiveIdx >= tileTitles.length) {
            resolvedActiveIdx = -1
        }

        var activeDescriptor = "Main Menu"
        if (resolvedActiveIdx >= 0) {
            var activeState = nextStateMap[resolvedActiveIdx]
            var activeNodeTitle = ""
            if (activeState && typeof activeState === "object" && activeState.focusNodeTitle) {
                activeNodeTitle = String(activeState.focusNodeTitle || "").trim()
            }
            activeDescriptor = activeNodeTitle.length > 0 ? activeNodeTitle : tileTitleForIndex(resolvedActiveIdx)
        }

        return {
            "windowKind": detachedWindow ? "detached" : "main",
            "windowLabel": detachedWindow ? "Detached Window" : "Main Window",
            "activeTileIndex": resolvedActiveIdx,
            "activeDescriptor": activeDescriptor,
            "inMainMenu": isInMainMenuPhase(),
            "hasUnsavedWork": !!hasUnsaved,
            "hasRunningTimer": !!hasRunningTimer,
            "stateByTile": nextStateMap,
            "panels": snapshots
        }
    }

    function closeRiskSnapshot() {
        return gatherCloseSessionSnapshot(false)
    }

    function checkpointCloseSessionState() {
        return gatherCloseSessionSnapshot(true)
    }

    function requestReturnToDockForTile(tileIndex, state) {
        var idx = Math.round(tileIndex)
        if (idx < -1 || idx >= tileTitles.length) {
            idx = activeTileIndex
        }
        if (idx < -1 || idx >= tileTitles.length) {
            idx = -1
        }
        var originRect = windowContentGlobalRect()
        if (!isValidGlobalRect(originRect)) {
            originRect = fallbackGlobalLaunchRectForTile(idx)
        }
        var dockState = root.shallowCloneObject(state || ({}))
        dockState.tileIndex = idx
        if (idx === -1) {
            if (!dockState.focusNodeId) dockState.focusNodeId = "H01"
            if (!dockState.focusNodeTitle) dockState.focusNodeTitle = "Practice Briefing"
            if (!dockState.titleText) dockState.titleText = "Practice Briefing"
        }
        var detachedTab = option3DetachedTabMetadataFromState(dockState)
        if (!detachedTab && idx === -1) {
            var homeModule = option3ModuleForTile(-1)
            var homeItem = option3ItemForTile(-1, "H01")
            if (homeModule && homeItem) {
                detachedTab = option3CreateTab(homeModule, homeItem, option3ParamsWithState({}, dockState), !!dockState.dirty)
            }
        }
        if (detachedTab) dockState._option3DetachedTab = detachedTab
        dockRequested(idx, dockTitleForIndex(idx), dockState, originRect)
        return true
    }

    function requestReturnToDockFromDetachedShell() {
        if (!root.detachedWindow) return false
        var idx = Math.round(root.initialTileIndex)
        if (idx < -1 || idx >= tileTitles.length) {
            idx = (stack && stack.currentIndex > 0) ? tileIndexForStack(stack.currentIndex) : activeTileIndex
        }
        if (idx < -1 || idx >= tileTitles.length) idx = -1

        var dockState = {}
        if (idx >= 0) {
            dockState = snapshotStateForTile(idx)
        }
        if ((!dockState || Object.keys(dockState).length <= 0)
            && root.initialPanelState
            && typeof root.initialPanelState === "object") {
            dockState = root.shallowCloneObject(root.initialPanelState)
        }
        return requestReturnToDockForTile(idx, dockState)
    }

    function isInMainMenuPhase() {
        return !!stack && !portalTransitionActive && stack.currentIndex === 0
    }

    function acceptsDirectDockInCurrentPhase() {
        if (root.option3ShellEnabled) return !!stack && !portalTransitionActive
        return isInMainMenuPhase()
    }

    function focusShellWindow() {
        if (!root.windowRef) return false
        try {
            if (root.windowRef.raise) root.windowRef.raise()
            if (root.windowRef.requestActivate) {
                if ((root.windowRef.flags & Qt.WindowDoesNotAcceptFocus) !== Qt.WindowDoesNotAcceptFocus) {
                    root.windowRef.requestActivate()
                }
            }
            return true
        } catch (e) {
        }
        return false
    }

    function openReportWindow(reportDocument) {
        if (!reportWindowManager) return false
        return reportWindowManager.openReportWindow(reportDocument || ({}))
    }

    function _docketStateFromReportRow(row) {
        var nextMatter = String(row && row.matterName !== undefined ? row.matterName : "").trim()
        if (nextMatter.toLowerCase() === "no matter") nextMatter = ""
        var hours = Number(row && row.hours !== undefined ? row.hours : 0)
        if (!isFinite(hours) || hours < 0) hours = 0
        var rawSeconds = parseInt(row && row.rawSeconds !== undefined ? row.rawSeconds : 0)
        if (!isFinite(rawSeconds) || rawSeconds < 0) {
            rawSeconds = Math.max(0, Math.round(hours * 3600))
        }
        return {
            "focusNodeId": "B01",
            "focusNodeTitle": "Time Docket Entry",
            "dateText": String(row && row.date !== undefined ? row.date : ""),
            "clientText": String(row && row.clientName !== undefined ? row.clientName : ""),
            "matterText": nextMatter,
            "descriptionText": String(row && row.description !== undefined ? row.description : ""),
            "timeText": String(hours.toFixed(2)),
            "rateText": String(Number(row && row.rate !== undefined ? row.rate : 0).toFixed(2)),
            "billText": String(Number(row && row.sharePct !== undefined ? row.sharePct : 0).toFixed(2)),
            "docketStatusText": String(row && row.status !== undefined ? row.status : "Draft"),
            "elapsedSeconds": rawSeconds,
            "lastPersistedSeconds": rawSeconds,
            "lastSavedEntryId": String(row && row.entryId !== undefined ? row.entryId : "")
        }
    }

    function _reportRecordEntityTitle(row) {
        var dateText = String(row && row.date !== undefined ? row.date : "").trim()
        var clientText = String(row && row.clientName !== undefined ? row.clientName : "").trim()
        var matterText = String(row && row.matterName !== undefined ? row.matterName : "").trim()
        var parts = []
        if (dateText.length > 0) parts.push(dateText)
        if (clientText.length > 0) parts.push(clientText)
        if (matterText.length > 0 && matterText.toLowerCase() !== "no matter") parts.push(matterText)
        return parts.join(" - ")
    }

    function _applyReportRecordIdentityToState(action, row, state) {
        var next = state && typeof state === "object" ? state : ({})
        var recordType = String(action && action.recordType !== undefined ? action.recordType : "").trim()
        var recordId = String(action && action.recordId !== undefined ? action.recordId : "").trim()
        if (recordId.length <= 0) {
            recordId = String(row && row.entryId !== undefined ? row.entryId : "").trim()
        }
        var recordTitle = String(action && action.recordTitle !== undefined ? action.recordTitle : "").trim()
        if (recordTitle.length <= 0) recordTitle = _reportRecordEntityTitle(row)

        next.recordType = recordType
        next.recordId = recordId
        next.recordTitle = recordTitle
        next.option3EntityType = recordType
        next.option3EntityId = recordId
        next.option3EntityTitle = recordTitle
        next.reportId = String(action && action.reportId !== undefined ? action.reportId : "")

        var module = option3ModuleForTile(1)
        var item = option3ItemForTile(1, "B01")
        if (root.option3ShellEnabled && module && item) {
            next._option3DetachedTab = root.option3CreateTab(module, item, option3ParamsWithState({}, next), !!next.dirty)
        }
        return next
    }

    function routeReportRecordAction(action) {
        var row = action && action.row ? action.row : ({})
        var recordType = String(action && action.recordType !== undefined ? action.recordType : "").trim()
        if (recordType !== "time_entry") return false

        var targetState = _applyReportRecordIdentityToState(action, row, _docketStateFromReportRow(row))

        // Symmetrically open editing inside a new focused, undocked sub-window (detached window)
        var targetWin = root.windowRef
        if (targetWin && targetWin.detachedMode && targetWin.dockHostWindowRef) {
            targetWin = targetWin.dockHostWindowRef
        }

        if (targetWin && targetWin.launchDetachedPanel) {
            targetWin.launchDetachedPanel(1, root.tileTitleForIndex(1), targetState, root.resolveDockLandingRect(1), null)
        }
        return true
    }

    function refreshReportFromWindow(reportId, sourceState) {
        if (String(reportId || "") !== "docket_activity") return false
        var targetStackIndex = stackIndexForTile(1)
        requestStackPageLoad(targetStackIndex, "report-window-refresh")
        if (stack) stack.currentIndex = targetStackIndex
        activeTileIndex = 1
        transitionTitle = tileTitleForIndex(1)
        clearHubModuleChooser()
        focusShellWindow()
        Qt.callLater(function() {
            var panel = panelRefForTile(1)
            if (panel && panel.openDocketReportWindowFromState) {
                panel.openDocketReportWindowFromState(sourceState || ({}))
            }
        })
        return true
    }

    function reloadAllActiveReportBranding() {
        if (reportWindowManager) {
            reportWindowManager.reloadAllActiveReportBranding()
        }
    }

    function resolveDockLandingRect(tileIndex) {
        return fallbackGlobalLaunchRectForTile(tileIndex)
    }

    function applyStateToTile(tileIndex, state) {
        var idx = Math.round(tileIndex)
        if (idx < 0 || idx >= tileTitles.length) return false
        if (!state) return true
        var nextStateMap = {}
        if (dockedStateByTile) {
            for (var key in dockedStateByTile) {
                if (dockedStateByTile.hasOwnProperty(key)) {
                    nextStateMap[key] = dockedStateByTile[key]
                }
            }
        }
        var persistedState = root.option3PersistableTileState(state)
        nextStateMap[idx] = persistedState
        dockedStateByTile = nextStateMap
        var livePanel = panelRefForTile(idx)
        if (livePanel && livePanel.applyInitialState) {
            try {
                livePanel.applyInitialState(state)
            } catch (e0) {
            }
        }
        if (root.option3ShellEnabled) {
            root.option3UpdateTabForState(idx, state)
        }
        return true
    }

    function requestDockIngest(tileIndex, state, originRect) {
        var idx = Math.round(tileIndex)
        if (idx < -1 || idx >= tileTitles.length) return false

        var sourceRect = originRect
        if (!isValidGlobalRect(sourceRect)) {
            sourceRect = fallbackGlobalLaunchRectForTile(idx)
        }

        if (root.option3ShellEnabled) {
            if (!stack || portalTransitionActive) return false
            var panelState = option3StateWithoutDetachedTabMetadata(state || ({}))
            var wasPaused = option3AutoEnsurePaused
            option3AutoEnsurePaused = true
            if (idx >= 0) {
                applyStateToTile(idx, panelState)
            }
            var dockedTabId = option3CreateReturnedDockTab(idx, state || ({}))
            var option3TargetIndex = stackIndexForTile(idx)
            if (option3TargetIndex > 0) {
                requestStackPageLoad(option3TargetIndex, "option3-dock-ingest")
                stack.currentIndex = option3TargetIndex
            } else {
                stack.currentIndex = 0
            }
            activeTileIndex = idx
            transitionTitle = dockTitleForIndex(idx)
            option3FlyoutModuleId = ""
            if (dockedTabId.length > 0) option3ActiveTabId = dockedTabId
            option3AutoEnsurePaused = wasPaused
            focusShellWindow()
            return true
        }

        if (idx < 0) return false
        if (!stack || portalTransitionActive || stack.currentIndex !== 0) return false

        applyStateToTile(idx, state)
        var targetIndex = stackIndexForTile(idx)
        var started = startPortalBlobTransition(targetIndex, sourceRect, idx)
        if (!started) {
            stack.currentIndex = targetIndex
            activeTileIndex = idx
            transitionTitle = tileTitleForIndex(idx)
        }
        applyStateToTile(idx, state)
        return true
    }

    function tryConsumePendingDockRequest() {
        if (!pendingDockRequest) return false
        if (portalTransitionActive || !stack || stack.currentIndex !== 0) return false
        var req = pendingDockRequest
        pendingDockRequest = null
        return requestDockIngest(req.tileIndex, req.state, req.originRect)
    }

    function autoReturnToMenuThenDock(tileIndex, state, originRect) {
        var idx = Math.round(tileIndex)
        if (idx < -1 || idx >= tileTitles.length) return false
        if (idx < 0 && !root.option3ShellEnabled) return false

        var sourceRect = originRect
        if (!isValidGlobalRect(sourceRect)) {
            sourceRect = fallbackGlobalLaunchRectForTile(idx)
        }

        pendingDockRequest = {
            "tileIndex": idx,
            "state": state,
            "originRect": Qt.rect(sourceRect.x, sourceRect.y, sourceRect.width, sourceRect.height)
        }

        if (!stack) return false
        if (portalTransitionActive) return true

        if (stack.currentIndex > 0) {
            var currentTile = tileIndexForStack(stack.currentIndex)
            if (currentTile < 0 || currentTile >= tileTitles.length) {
                currentTile = idx
            }
            if (!startPortalReverseTransition(currentTile)) {
                stack.currentIndex = 0
            }
        }
        return tryConsumePendingDockRequest()
    }

    function startPortalBlobTransition(targetIndex, tileGlobalGeom, tileIndex) {
        if (typeof targetIndex !== "number" || targetIndex < 0) return false
        if (portalTransitionActive) return false
        if (!stack || targetIndex === stack.currentIndex) return false
        clearHubModuleChooser()

        if (root.isProMode) {
            stack.currentIndex = targetIndex
            return true
        }

        playSfxTransitionDeform(0.58)
        if (!bodyHost || bodyHost.width <= 0 || bodyHost.height <= 0) {
            stack.currentIndex = targetIndex
            return true
        }

        var bodyW = Math.max(1, bodyHost.width)
        var bodyH = Math.max(1, bodyHost.height)
        var tileIdx = Math.round(tileIndex)
        if (tileIdx >= 0 && tileIdx < tileTitles.length) {
            activeTileIndex = tileIdx
            transitionTitle = tileTitleForIndex(tileIdx)
            rememberTileGeometry(tileIdx, tileGlobalGeom)
        } else {
            transitionTitle = "Module"
        }

        var solvedStart = resolveTileLocalRect(tileGlobalGeom, tileIdx)
        var startX = solvedStart.x
        var startY = solvedStart.y
        var startW = solvedStart.w
        var startH = solvedStart.h

        var endX = 0
        var endY = 0
        var endW = bodyW
        var endH = bodyH
        var startCornerPx = Math.max(
            ratioPx(scaleRatios.jellyLaunchCornerStartPct, 4),
            Math.round(Math.min(startW, startH) * 0.14)
        )
        var endCornerPx = ratioPx(scaleRatios.jellyLaunchCornerEndPct, 2)
        var originX = startX + (startW * 0.5)
        var originY = startY + (startH * 0.5)

        portalReverse = false
        portalSwitchProgress = portalSwitchProgressForward
        portalTargetIndex = targetIndex
        portalOriginX = originX
        portalOriginY = originY
        launchStartX = startX
        launchStartY = startY
        launchStartW = startW
        launchStartH = startH
        launchEndX = endX
        launchEndY = endY
        launchEndW = endW
        launchEndH = endH
        launchStartRadius = startCornerPx
        launchEndRadius = endCornerPx
        portalProgress = 0.0
        portalTransitionActive = true
        perfStart("sidebar.nav.open", "tileIndex=" + tileIdx + " targetStack=" + targetIndex)
        // make sure our window is active when the portal animation starts
        focusShellWindow()
        root.isInteractive = false

        if (portalBlobTransition.running) {
            portalBlobTransition.stop()
        }
        portalBlobTransition.restart()
        return true
    }

    function startPortalReverseTransition(tileIndex) {
        if (portalTransitionActive) return false
        clearHubModuleChooser()
        if (!stack || stack.currentIndex <= 0) {
            if (stack) stack.currentIndex = 0
            return true
        }

        if (root.isProMode) {
            stack.currentIndex = 0
            return true
        }

        playSfxTransitionDeform(0.48)
        if (!bodyHost || bodyHost.width <= 0 || bodyHost.height <= 0) {
            stack.currentIndex = 0
            return true
        }

        var bodyW = Math.max(1, bodyHost.width)
        var bodyH = Math.max(1, bodyHost.height)
        var tileIdx = Math.round(tileIndex)
        if (tileIdx < 0 || tileIdx >= tileTitles.length) {
            tileIdx = tileIndexForStack(stack.currentIndex)
        }
        if (tileIdx < 0 || tileIdx >= tileTitles.length) {
            tileIdx = activeTileIndex
        }
        if (tileIdx < 0 || tileIdx >= tileTitles.length) {
            tileIdx = 0
        }
        activeTileIndex = tileIdx
        transitionTitle = tileTitleForIndex(tileIdx)

        var solvedEnd = resolveTileLocalRect(null, tileIdx)
        var startX = 0
        var startY = 0
        var startW = bodyW
        var startH = bodyH
        var endX = solvedEnd.x
        var endY = solvedEnd.y
        var endW = solvedEnd.w
        var endH = solvedEnd.h
        var startCornerPx = ratioPx(scaleRatios.jellyLaunchCornerEndPct, 2)
        var endCornerPx = Math.max(
            ratioPx(scaleRatios.jellyLaunchCornerStartPct, 4),
            Math.round(Math.min(endW, endH) * 0.14)
        )
        var originX = startX + (startW * 0.5)
        var originY = startY + (startH * 0.5)

        portalReverse = true
        portalSwitchProgress = portalSwitchProgressReverse
        portalTargetIndex = 0
        portalOriginX = originX
        portalOriginY = originY
        launchStartX = startX
        launchStartY = startY
        launchStartW = startW
        launchStartH = startH
        launchEndX = endX
        launchEndY = endY
        launchEndW = endW
        launchEndH = endH
        launchStartRadius = startCornerPx
        launchEndRadius = endCornerPx
        portalProgress = 0.0
        portalTransitionActive = true
        perfStart("sidebar.nav.back", "tileIndex=" + tileIdx + " fromStack=" + stack.currentIndex)
        root.isInteractive = false

        if (portalBlobTransition.running) {
            portalBlobTransition.stop()
        }
        portalBlobTransition.restart()
        return true
    }

    // Tear-away handoff path: return source shell to main menu without reverse shrink.
    // This keeps the detached-window burst as one continuous visual event.
    function completeTearAwayTransition(tileIndex) {
        if (portalBlobTransition.running) {
            portalBlobTransition.stop()
        }
        portalTransitionActive = false
        portalProgress = 0.0
        portalTargetIndex = -1
        portalReverse = false
        portalSwitchProgress = portalSwitchProgressForward

        if (root.option3ShellEnabled) {
            if ((option3OpenTabs || []).length > 0) {
                if (option3FindTabIndexById(option3ActiveTabId) < 0) {
                    option3ActiveTabId = String(option3OpenTabs[0].id || "")
                }
                option3ActivateTab(option3ActiveTabId, false)
            } else {
                option3SetEmptyWorkspace("tear-away-complete")
            }
            root.isInteractive = true
            return
        }

        if (stack) {
            stack.currentIndex = 0
        }
        activeTileIndex = -1
        transitionTitle = "Module"
        root.isInteractive = true
        if (pendingDockRequest) {
            Qt.callLater(function() {
                root.tryConsumePendingDockRequest()
            })
        }
    }

    function finishPortalBlobTransition() {
        var completedTarget = portalTargetIndex
        var wasReverse = portalReverse
        if (portalTargetIndex >= 0 && stack && stack.currentIndex !== portalTargetIndex) {
            stack.currentIndex = portalTargetIndex
        }
        portalTransitionActive = false
        portalProgress = 0.0
        portalTargetIndex = -1
        portalReverse = false
        portalSwitchProgress = portalSwitchProgressForward
        if (stack) {
            var resolvedTileIdx = tileIndexForStack(stack.currentIndex)
            if (resolvedTileIdx >= 0) {
                activeTileIndex = resolvedTileIdx
                transitionTitle = tileTitleForIndex(resolvedTileIdx)
            }
        }
        root.isInteractive = true
        if (wasReverse) {
            perfEnd("sidebar.nav.back", "targetStack=" + completedTarget + " currentStack=" + (stack ? stack.currentIndex : -1))
        } else {
            perfEnd("sidebar.nav.open", "targetStack=" + completedTarget + " currentStack=" + (stack ? stack.currentIndex : -1))
        }
    }

    function applyInitialSelection() {
        if (!stack) return
        var idx = Math.round(initialTileIndex)
        if (idx >= 0 && idx < tileTitles.length) {
            activeTileIndex = idx
            transitionTitle = tileTitleForIndex(idx)
            stack.currentIndex = stackIndexForTile(idx)
        } else if (stack.currentIndex <= 0) {
            activeTileIndex = -1
            transitionTitle = "Module"
            stack.currentIndex = 0
        } else {
            var resolvedIdx = tileIndexForStack(stack.currentIndex)
            if (resolvedIdx >= 0) {
                activeTileIndex = resolvedIdx
                transitionTitle = tileTitleForIndex(resolvedIdx)
            }
        }
        requestStackPageLoad(stack.currentIndex, "applyInitialSelection")
    }

    function applyRecoveredStateBundle(stateByTile, recoveredActiveTileIndex, recoveredInMainMenu) {
        var nextStateMap = {}
        if (stateByTile && typeof stateByTile === "object") {
            for (var key in stateByTile) {
                if (stateByTile.hasOwnProperty(key)) {
                    nextStateMap[key] = stateByTile[key]
                }
            }
        }
        dockedStateByTile = nextStateMap

        if (!stack) return true
        if (recoveredInMainMenu) {
            stack.currentIndex = 0
            activeTileIndex = -1
            transitionTitle = "Module"
            return true
        }

        var idx = Math.round(recoveredActiveTileIndex)
        if (idx >= 0 && idx < tileTitles.length) {
            activeTileIndex = idx
            transitionTitle = tileTitleForIndex(idx)
            stack.currentIndex = stackIndexForTile(idx)
            return true
        }
        return true
    }

    function applyRecoveredSessionRow(row) {
        if (!row || typeof row !== "object") return false
        var stateMap = row.stateByTile && typeof row.stateByTile === "object" ? row.stateByTile : {}
        var activeIdx = (typeof row.activeTileIndex === "number") ? row.activeTileIndex : -1
        var inMain = !!row.inMainMenu
        return applyRecoveredStateBundle(stateMap, activeIdx, inMain)
    }

    property int headerHeightPx: ratioPx(scaleRatios.headerHeightPct, 1)
    property int headerMarginPx: ratioPx(scaleRatios.headerMarginPct, 1)
    property int headerCornerInsetPx: Math.max(
        4,
        Math.min(ratioPx(0.010, 7), Math.round(Math.max(0, root.chromeCornerRadius) * 0.32))
    )
    property int headerSpacingPx: ratioPx(scaleRatios.headerSpacingPct, 1)
    property int titleBarControlsExtraInsetPx: Math.max(2, ratioPx(0.0036, 3))
    property int titleBarControlsInsetPx: headerCornerInsetPx + titleBarControlsExtraInsetPx
    property real titleBarControlScale: 0.90
    property int titleSpacingPx: ratioPx(scaleRatios.titleSpacingPct, 1)
    property real dpiScaleFactor: (metrics && typeof metrics.scalePercent === "number")
        ? Math.max(1.0, metrics.scalePercent / 100.0)
        : 1.0
    property int titleFontPx: {
        var basePx = ratioPx(scaleRatios.titleFontPct, metricFloor("fontFloorTitlePx", 12))
        return Math.max(14, basePx)
    }
    property int logoSizePx: ratioPx(scaleRatios.logoSizePct, 1)
    property int controlsSpacingPx: ratioPx(scaleRatios.controlsSpacingPct, 1)
    property int dividerThicknessPx: ratioPx(scaleRatios.dividerThicknessPct, 1)
    property int bodyMarginPx: ratioPx(scaleRatios.bodyMarginPct, 1)

    SequentialAnimation {
        id: portalBlobTransition
        running: false
        NumberAnimation {
            target: root
            property: "portalProgress"
            from: 0.0
            to: 0.18
            duration: root.transitionDurationMs(root.scaleRatios.jellyStageOneDurationPct, 90)
            easing.type: Easing.InOutQuad
        }
        NumberAnimation {
            target: root
            property: "portalProgress"
            to: root.portalSwitchProgress
            duration: root.transitionDurationMs(root.scaleRatios.jellyStageTwoDurationPct, 150)
            easing.type: Easing.OutBack
            easing.overshoot: 1.36
        }
        ScriptAction {
            script: {
                root.playSfxLaunchBurst(root.portalReverse ? 0.50 : 0.86)
                if (root.portalTargetIndex >= 0) {
                    stack.currentIndex = root.portalTargetIndex
                }
            }
        }
        NumberAnimation {
            target: root
            property: "portalProgress"
            to: 1.0
            duration: root.transitionDurationMs(root.scaleRatios.jellyStageThreeDurationPct, 180)
            easing.type: Easing.OutCubic
        }
        ScriptAction {
            script: {
                root.playSfxTransitionSettle(root.portalReverse ? 0.52 : 0.60)
                root.finishPortalBlobTransition()
            }
        }
        onStopped: {
            if (root.portalTransitionActive && !running) {
                root.finishPortalBlobTransition()
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.isProMode ? root.proBackground : root.bgColor
        antialiasing: true
    }

    Image {
        id: skylineBackdrop
        visible: !root.isProMode
        anchors.fill: parent
        source: Qt.resolvedUrl("../../../assets/home_skyline_bw.png")
        fillMode: Image.PreserveAspectCrop
        smooth: true
        asynchronous: false
        retainWhileLoading: true
        cache: true
        mipmap: true
        opacity: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.22 : 0.34) : 0.34
        layer.enabled: true
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.02 : 0.04) : 0.04
            blurMax: 28
            saturation: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.06 : 0.18) : 0.18
            brightness: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.04 : -0.04) : -0.04
            colorizationColor: root.accentColor
            colorization: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.06 : 0.14) : 0.14
            autoPaddingEnabled: false
        }
    }

    Rectangle {
        anchors.fill: parent
        color: {
            if (root && root.isProMode) return "transparent";
            var isLight = ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? (root ? root.lightTheme : false) : false;
            var p = root ? root.panelColor : null;
            if (p && typeof p.r === "number") {
                return Qt.rgba(p.r, p.g, p.b, isLight ? 0.28 : 0.16);
            }
            return isLight ? "#F9FAFB" : "#0E0F11";
        }
        antialiasing: true
    }

    Rectangle {
        anchors.fill: parent
        visible: !root.isProMode
        gradient: Gradient {
            GradientStop { 
                position: 0.0; 
                color: ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean" && (root ? typeof root.alphaAccent : "undefined") === "function") 
                    ? root.alphaAccent((root ? (root ? root.lightTheme : false) : false) ? 0.04 : 0.10) 
                    : Qt.rgba(0.2, 0.5, 1.0, 0.10)
            }
            GradientStop { 
                position: 0.52; 
                color: {
                    var isLight = ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? (root ? root.lightTheme : false) : false;
                    var p = root ? root.panelColor : null;
                    if (p && typeof p.r === "number") {
                        return Qt.rgba(p.r, p.g, p.b, isLight ? 0.06 : 0.04);
                    }
                    return isLight ? "rgba(249, 250, 251, 0.06)" : "rgba(14, 15, 17, 0.04)";
                }
            }
            GradientStop { 
                position: 1.0; 
                color: {
                    var isLight = ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? (root ? root.lightTheme : false) : false;
                    var p2 = root ? root.panel2Color : null;
                    if (p2 && typeof p2.r === "number") {
                        return Qt.rgba(p2.r, p2.g, p2.b, isLight ? 0.10 : 0.08);
                    }
                    return isLight ? "rgba(241, 243, 245, 0.10)" : "rgba(24, 26, 30, 0.08)";
                }
            }
        }
        antialiasing: true
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: root.ratioPx(0.0, 0)

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.isProMode ? 0 : (root ? root.headerHeightPx : 0)
            visible: !root.isProMode
            color: "transparent"
            clip: true

            Rectangle {
                id: headerGlassMask
                anchors.fill: parent
                color: "transparent"
            }

            ShaderEffectSource {
                id: headerBlurSource
                anchors.fill: parent
                sourceItem: skylineBackdrop
                sourceRect: (skylineBackdrop && (root ? typeof root.sourceRectFor : "undefined") === "function") ? root.sourceRectFor(headerGlassMask) : Qt.rect(0, 0, 1, 1)
                live: !(root.windowRef && (root.windowRef.userResizeInProgress || root.windowRef.userMoveInProgress))
                hideSource: false
                mipmap: true
            }

            MultiEffect {
                anchors.fill: parent
                source: headerBlurSource
                blurEnabled: true
                blur: 1.0
                blurMax: 30
                saturation: (root ? (root ? root.lightTheme : false) : false) ? 0.26 : 0.38
                brightness: (root ? (root ? root.lightTheme : false) : false) ? 0.06 : -0.03
            }

            Rectangle {
                anchors.fill: parent
                color: {
                    var isLight = ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? (root ? root.lightTheme : false) : true;
                    if (isLight) {
                        var p2 = root ? root.panel2Color : null;
                        return (p2 && typeof p2.r === "number") 
                            ? Qt.rgba(p2.r, p2.g, p2.b, 0.62) 
                            : "#F1F3F5";
                    } else {
                        var p = root ? root.panelColor : null;
                        return (p && typeof p.r === "number")
                            ? Qt.rgba(p.r, p.g, p.b, 0.54)
                            : "#0E0F11";
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: Math.max(1, ((root ? typeof root.ratioPx : "undefined") === "function") ? root.ratioPx(0.012, 3) : 3)
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, ((root ? typeof (root ? root.lightTheme : false) : "undefined") === "boolean") ? ((root ? (root ? root.lightTheme : false) : false) ? 0.28 : 0.20) : 0.20) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Math.max(1, root.ratioPx(root.scaleRatios.dividerThicknessPct, 1))
                color: Qt.rgba(root.textColor.r, root.textColor.g, root.textColor.b, (root ? (root ? root.lightTheme : false) : false) ? 0.14 : 0.10)
            }

            Item {
                id: headerDragZone
                x: ((root ? typeof (root ? root.headerMarginPx : 0) : "undefined") === "number") ? ((root ? root.headerMarginPx : 0) + (root ? root.headerCornerInsetPx : 0)) : 4
                y: 0
                height: parent.height
                width: {
                    if ((root ? typeof (root ? root.headerMarginPx : 0) : "undefined") !== "number" || (root ? typeof (root ? root.headerCornerInsetPx : 0) : "undefined") !== "number") return Math.max(1, parent.width - 100);
                    var available = parent.width
                        - (((root ? root.headerMarginPx : 0) + (root ? root.headerCornerInsetPx : 0)) * 2)
                        - controlsRow.width
                        - (root ? root.titleBarControlsInsetPx : 0)
                        - (root ? root.headerSpacingPx : 0)
                    return Math.max(1, Math.round(available))
                }
                TapHandler {
                    id: headerDoubleTap
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: {
                        if (tapCount === 2) {
                            if (root.windowRef && root.windowRef.toggleWindowMaximize) {
                                root.windowRef.toggleWindowMaximize()
                            }
                        }
                    }
                }

                DragHandler {
                    id: headerDrag
                    target: null
                    dragThreshold: 0
                    // Start drag session only after real translation begins.
                    // Press-time start can trigger one-frame geometry/mask churn on multi-monitor setups.
                    enabled: root ? !!(root.isInteractive && root.windowRef) : false
                    property bool dragSessionStarted: false

                    onActiveChanged: {
                        if (!root.windowRef) {
                            return
                        }
                        if (active) {
                            dragSessionStarted = false
                            if (root.windowRef.geometryTransitionSuppressed !== undefined) {
                                root.windowRef.geometryTransitionSuppressed = true
                            }
                        } else {
                            if (!dragSessionStarted) {
                                if (root.windowRef.geometryTransitionSuppressed !== undefined
                                    && !root.windowRef.userMoveInProgress
                                    && !root.windowRef.userResizeInProgress) {
                                    root.windowRef.geometryTransitionSuppressed = false
                                }
                                return
                            }
                            if (root.windowRef.finishUserDrag) {
                                try {
                                    root.windowRef.finishUserDrag()
                                } catch(e) {
                                }
                            } else if (root.windowRef.userMoveInProgress !== undefined) {
                                root.windowRef.userMoveInProgress = false
                                if (root.windowRef.updateTargetScreenFromFinalCenter) {
                                    try {
                                        root.windowRef.updateTargetScreenFromFinalCenter()
                                    } catch(e) {
                                    }
                                }
                                if (root.windowRef.updateCanvasGeometry) {
                                    try {
                                        root.windowRef.updateCanvasGeometry()
                                    } catch(e) {
                                    }
                                }
                            } else if (root.windowRef.updateCanvasGeometry) {
                                try {
                                    root.windowRef.updateCanvasGeometry()
                                } catch(e) {
                                }
                            }
                            dragSessionStarted = false
                        }
                    }

                    onTranslationChanged: {
                        if (!active || !root.windowRef) {
                            return
                        }
                        if (!dragSessionStarted) {
                            if (Math.abs(translation.x) < 0.5 && Math.abs(translation.y) < 0.5) {
                                return
                            }
                            if (root.windowRef.uiMaximized && translation.y <= 0.5) {
                                return
                            }
                            if (root.windowRef.beginHeaderDrag) {
                                try {
                                    var beginHeaderOk = root.windowRef.beginHeaderDrag(translation.x, translation.y)
                                    dragSessionStarted = !!root.windowRef.userMoveInProgress
                                    if (!dragSessionStarted && typeof beginHeaderOk === "boolean") {
                                        dragSessionStarted = beginHeaderOk
                                    }
                                } catch(e) {
                                }
                            } else if (root.windowRef.beginUserDrag) {
                                try {
                                    var beginDragOk = root.windowRef.beginUserDrag()
                                    dragSessionStarted = !!root.windowRef.userMoveInProgress
                                    if (!dragSessionStarted && typeof beginDragOk === "boolean") {
                                        dragSessionStarted = beginDragOk
                                    }
                                } catch(e2) {
                                }
                            }
                            if (!dragSessionStarted) {
                                return
                            }
                        }
                        if (root.windowRef.updateUserDrag) {
                            try {
                                root.windowRef.updateUserDrag(translation.x, translation.y)
                            } catch(e3) {
                            }
                        } else if (root.windowRef.userMoveInProgress
                            && root.windowRef.animationPhase === "settled"
                            && root.windowRef.syncDragContentPosition) {
                            try {
                                root.windowRef.syncDragContentPosition()
                            } catch(e4) {
                            }
                        }
                    }
                }
            }

            RowLayout {
                anchors.fill: parent
                // TIGHT V1 MARGINS
                anchors.leftMargin: (root ? root.headerMarginPx : 0) + (root ? root.headerCornerInsetPx : 0)
                anchors.rightMargin: (root ? root.headerMarginPx : 0) + (root ? root.headerCornerInsetPx : 0)
                spacing: (root ? root.headerSpacingPx : 0)

                // 1. LOGO (ratio-scaled)
                CrispLogo {
                    id: headerLogo
                    Layout.preferredHeight: (root ? root.logoSizePx : 0)
                    Layout.preferredWidth: (root ? root.logoSizePx : 0)
                    metrics: root.metrics
                    color: (root && root.t && root.t.text) ? root.t.text : "#FFFFFF"
                }

                // 2. TITLES
                ColumnLayout {
                    spacing: (root ? root.titleSpacingPx : 0)
                    Layout.alignment: Qt.AlignVCenter
                     
                    Text {
                        text: "Cory Schneider Law Office Practice Management"
                        color: (root && root.t && root.t.text) ? root.t.text : "#FFFFFF"
                        font.pixelSize: (root ? root.titleFontPx : 14)
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Item { Layout.fillWidth: true }

                // 3. CONTROLS
                RowLayout {
                    id: controlsRow
                    spacing: Math.max(1, (root ? root.controlsSpacingPx : 0) - Math.max(1, root.ratioPx(0.003, 2)))
                    Layout.rightMargin: (root ? root.titleBarControlsInsetPx : 0)
                    visible: true 
                    z: 3
                    
                    TitleBarButton { 
                        t: root.t; text: "\u2699"; 
                        metrics: root.metrics
                        sizeScale: (root ? root.titleBarControlScale : 1.0)
                        onClicked: {
                            if (root.isInteractive && root.windowRef) {
                                try {
                                    if (root.windowRef.openSettingsMenu && root.windowRef.openSettingsMenu()) {
                                        return
                                    }
                                    if (!root.windowRef.openThemePicker || !root.windowRef.openThemePicker()) {
                                        console.log("[SETTINGS] openSettingsMenu/openThemePicker returned false")
                                    }
                                } catch(e) {
                                }
                            }
                        }
                        opacity: root.isInteractive ? 1.0 : 1.05
                    }
                    TitleBarButton { 
                        t: root.t; text: "\u2013"; 
                        metrics: root.metrics
                        sizeScale: (root ? root.titleBarControlScale : 1.0)
                        onClicked: {
                            root.playSfxUiClick("minimize", 0.42)
                            if (root.isInteractive && root.windowRef) {
                                try {
                                    if (!root.windowRef.requestMinimizeAnimation || !root.windowRef.requestMinimizeAnimation()) {
                                        root.windowRef.showMinimized()
                                    }
                                } catch(e) {
                                    root.windowRef.showMinimized()
                                }
                            }
                        } 
                        opacity: root.isInteractive ? 1.0 : 1.05
                    }
                    TitleBarButton { 
                        t: root.t; text: (root.windowRef && root.windowRef.uiMaximized) ? "\u2750" : "\u2610"; 
                        metrics: root.metrics
                        sizeScale: (root ? root.titleBarControlScale : 1.0)
                        onClicked: {
                            root.playSfxUiClick("expand", 0.58)
                            if (root.isInteractive && root.windowRef) {
                                if (root.windowRef.toggleWindowMaximize) {
                                    try { root.windowRef.toggleWindowMaximize() } catch(e) { }
                                } else {
                                    try { (root.windowRef.isMaximized ? root.windowRef.showNormal() : root.windowRef.showMaximized()) } catch(e2) { }
                                }
                            }
                        }
                        opacity: root.isInteractive ? 1.0 : 1.05
                    }
                    TitleBarButton { 
                        id: closeButton
                        t: root.t; text: "\u2715"; danger: true; 
                        metrics: root.metrics
                        sizeScale: (root ? root.titleBarControlScale : 1.0)
                        
                        TapHandler {
                            onTapped: {
                                if (closeButton.hovered && root.isInteractive && root.windowRef) {
                                    root.playSfxUiClick("danger", 0.82)
                                    try {
                                        if (!root.windowRef.requestCloseAnimation || !root.windowRef.requestCloseAnimation()) {
                                            root.windowRef.close()
                                        }
                                    } catch(e) { root.windowRef.close() }
                                } else if (closeButton.hovered && root.windowRef) {
                                    root.playSfxUiClick("danger", 0.70)
                                    // Allow close even if not marked as interactive - fallback
                                    try {
                                        root.windowRef.close();
                                    } catch(e) { }
                                }
                            }
                        }
                        opacity: 1.0  // Always fully visible
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.isProMode ? 0 : (root ? root.dividerThicknessPx : 1)
            visible: !root.isProMode
            color: Qt.rgba((root && root.textColor ? root.textColor.r : 255), (root && root.textColor ? root.textColor.g : 255), (root && root.textColor ? root.textColor.b : 255), 0.15)
        }

        // === BODY ===
        Item {
            id: bodyHost
            Layout.fillWidth: true
            Layout.fillHeight: true

            function activeStackPage() {
                if (!stack) return null
                if (stack.count <= 0) return null
                var idx = Math.max(0, Math.min(stack.currentIndex, stack.count - 1))
                if (typeof stack.itemAt === "function") {
                    var item = stack.itemAt(idx)
                    if (item) return item
                }
                if (stack.children && idx >= 0 && idx < stack.children.length) {
                    return stack.children[idx]
                }
                return null
            }

            function stackPageLooksRenderable() {
                var page = activeStackPage()
                if (!page) return false
                if (page.visible === false) return false
                var w = (typeof page.width === "number") ? page.width : 0
                var h = (typeof page.height === "number") ? page.height : 0
                var a = (typeof page.opacity === "number") ? page.opacity : 1.0
                return w > 1 && h > 1 && a > 0.001
            }

            HomeGrid {
                id: homeGridFallback
                anchors.fill: parent
                z: 5
                t: root.t
                sfxBus: root.sfxBus
                metrics: root.metrics
                windowRef: root.windowRef
                dashboardSummary: root.dashboardSummary
                maximized: (root.windowRef && root.windowRef.uiMaximized) ? true : false
                enabled: false
                // Safety fallback when stack is momentarily invalid so the body never renders blank.
                // Keep this component in-place for quick rollback, but force-disabled to avoid
                // translucent double-render artifacts (duplicate search icon/text/bar).
                visible: false
                onTileClicked: function(idx, geom) {
                    root.playSfxTilePress()
                    root.launchTileFromHome(idx, geom)
                }
                onHubClicked: function(hubIndex, moduleIndexes, geom) {
                    root.playSfxTilePress()
                    var modules = root.normalizedHubModules(moduleIndexes)
                    if (modules.length <= 0) {
                        return
                    }
                    if (modules.length === 1) {
                        root.launchTileFromHome(modules[0], geom)
                        return
                    }
                    if (!root.openHubSelection(hubIndex, modules, geom)) {
                        root.launchTileFromHome(modules[0], geom)
                    }
                }
                onOmniSearchRequested: function(query) {
                    root.handleOmniSearch(query)
                }
            }

            Component {
                id: clientsLanePanelComponent
                PlaceholderSubmenuView {
                    anchors.fill: parent
                    t: root.t
                    metrics: root.metrics
                    appRef: root.appRef
                    windowRef: root.windowRef
                    detachedWindow: root.detachedWindow
                    externalNavigationShell: root.option3ShellEnabled
                    laneKey: "clients_matters"
                    laneSummary: root.laneSummaryForTile(0)
                    navItems: root.laneNavItemsForTile(0)
                    defaultNodeId: "A01"
                    tileIndex: 0
                    titleText: root.tileTitleForIndex(0)
                    initialState: (root.dockedStateByTile[0] !== undefined)
                        ? root.dockedStateByTile[0]
                        : ((root.initialTileIndex === 0) ? root.initialPanelState : null)
                    enabled: root.isInteractive
                    onSubmitRequested: function(state) {
                    }
                    onCancelRequested: function(state) {
                        if (root.detachedWindow && root.windowRef) {
                            try {
                                if (!root.windowRef.requestCloseAnimation || !root.windowRef.requestCloseAnimation()) {
                                    root.windowRef.close()
                                }
                            } catch (e) {
                                try { root.windowRef.close() } catch (e2) { }
                            }
                            return
                        }
                        if (!root.startPortalReverseTransition(0)) {
                            stack.currentIndex = 0
                        }
                    }
                    onTearAwayRequested: function(state) {
                        if (root.detachedWindow) {
                            root.requestReturnToDockForTile(0, state)
                        } else {
                            root.requestTearAwayForTile(0, state)
                        }
                    }
                    onModuleJumpRequested: function(nextTileIndex, state) {
            var nextIdx = Math.round(nextTileIndex)
            if (nextIdx < 0 || nextIdx >= root.tileTitles.length) return
            var sourceState = root.shallowCloneObject(state)
            var targetState = null
            if (sourceState && sourceState._targetTileState && typeof sourceState._targetTileState === "object") {
                targetState = root.shallowCloneObject(sourceState._targetTileState)
                delete sourceState._targetTileState
            }
            root.applyStateToTile(0, sourceState)
            if (targetState && typeof targetState === "object") {
                root.applyStateToTile(nextIdx, targetState)
            }
            if (root.detachedWindow) {
                var targetStackIndex = root.stackIndexForTile(nextIdx)
                if (targetStackIndex <= 0) return
                root.requestStackPageLoad(targetStackIndex, "module-jump-detached")
                if (stack) {
                    stack.currentIndex = targetStackIndex
                }
                root.activeTileIndex = nextIdx
                root.transitionTitle = root.tileTitleForIndex(nextIdx)
                root.clearHubModuleChooser()
                root.focusShellWindow()
                if (root.windowRef) {
                    try {
                        root.windowRef.detachedInitialTileIndex = nextIdx
                        root.windowRef.detachedPanelTitle = root.tileTitleForIndex(nextIdx)
                        if (root.windowRef.setPanelTaskbarTitle) {
                            root.windowRef.setPanelTaskbarTitle("CSPM - " + root.tileTitleForIndex(nextIdx))
                        }
                    } catch (e0) {
                    }
                }
                return
            }
            root.launchTileFromHome(nextIdx, null)
        }
                    onWorkspaceOpenRequested: function(targetTileIndex, nodeId, state) {
                        root.handleWorkspaceOpenRequested(targetTileIndex, nodeId, state)
                    }
                    onReportWindowRequested: function(reportDocument) {
                        root.openReportWindow(reportDocument)
                    }
                }
            }

            Component {
                id: docketLanePanelComponent
                TimeDocketView {
                    anchors.fill: parent
                    t: root.t
                    metrics: root.metrics
                    appRef: root.appRef
                    windowRef: root.windowRef
                    detachedWindow: root.detachedWindow
                    externalNavigationShell: root.option3ShellEnabled
                    laneSummary: root.laneSummaryForTile(1)
                    navItems: root.laneNavItemsForTile(1)
                    tileIndex: 1
                    titleText: root.tileTitleForIndex(1)
                    initialState: (root.dockedStateByTile[1] !== undefined)
                        ? root.dockedStateByTile[1]
                        : ((root.initialTileIndex === 1) ? root.initialPanelState : null)
                    enabled: root.isInteractive
                    onWorkspaceNavChanged: function(tileIndex, state) {
                        if (root.option3ShellEnabled) {
                            root.option3UpdateTabForState(tileIndex, state)
                        }
                    }
                    onReturnRequested: function(state) {
                        if (root.detachedWindow && root.windowRef) {
                            try {
                                if (!root.windowRef.requestCloseAnimation || !root.windowRef.requestCloseAnimation()) {
                                    root.windowRef.close()
                                }
                            } catch (e) {
                                try { root.windowRef.close() } catch (e2) { }
                            }
                            return
                        }
                        if (root.option3ShellEnabled) {
                            var closingTabId = String(root.option3ActiveTabId || "")
                            if (!root.startPortalReverseTransition(1)) {
                                stack.currentIndex = 0
                            }
                            activeTileIndex = -1
                            root.option3OpenHomeBriefing()
                            if (closingTabId.length > 0) {
                                root.option3CloseTab(closingTabId, true)
                            }
                            return
                        }
                        if (!root.startPortalReverseTransition(1)) {
                            stack.currentIndex = 0
                        }
                    }
                    onDetachRequested: function(state) {
                        if (root.detachedWindow) {
                            root.requestReturnToDockForTile(1, state)
                        } else {
                            root.requestTearAwayForTile(1, state)
                        }
                    }
                    onModuleJumpRequested: function(nextTileIndex, state) {
            var nextIdx = Math.round(nextTileIndex)
            if (nextIdx < 0 || nextIdx >= root.tileTitles.length) return
            var sourceState = root.shallowCloneObject(state)
            var targetState = null
            if (sourceState && sourceState._targetTileState && typeof sourceState._targetTileState === "object") {
                targetState = root.shallowCloneObject(sourceState._targetTileState)
                delete sourceState._targetTileState
            }
            root.applyStateToTile(1, sourceState)
            if (targetState && typeof targetState === "object") {
                root.applyStateToTile(nextIdx, targetState)
            }
            if (root.detachedWindow) {
                var targetStackIndex = root.stackIndexForTile(nextIdx)
                if (targetStackIndex <= 0) return
                root.requestStackPageLoad(targetStackIndex, "module-jump-detached")
                if (stack) {
                    stack.currentIndex = targetStackIndex
                }
                root.activeTileIndex = nextIdx
                root.transitionTitle = root.tileTitleForIndex(nextIdx)
                root.clearHubModuleChooser()
                root.focusShellWindow()
                if (root.windowRef) {
                    try {
                        root.windowRef.detachedInitialTileIndex = nextIdx
                        root.windowRef.detachedPanelTitle = root.tileTitleForIndex(nextIdx)
                        if (root.windowRef.setPanelTaskbarTitle) {
                            root.windowRef.setPanelTaskbarTitle("CSPM - " + root.tileTitleForIndex(nextIdx))
                        }
                    } catch (e0) {
                    }
                }
                return
            }
            root.launchTileFromHome(nextIdx, null)
        }
                    onReportWindowRequested: function(reportDocument) {
                        root.openReportWindow(reportDocument)
                    }
                    onWorkspaceOpenRequested: function(targetTileIndex, nodeId, state) {
                        root.handleWorkspaceOpenRequested(targetTileIndex, nodeId, state)
                    }
                }
            }

            Component {
                id: billingLanePanelComponent
                PlaceholderSubmenuView {
                    anchors.fill: parent
                    t: root.t
                    metrics: root.metrics
                    appRef: root.appRef
                    windowRef: root.windowRef
                    detachedWindow: root.detachedWindow
                    externalNavigationShell: root.option3ShellEnabled
                    laneKey: "billing_tax"
                    laneSummary: root.laneSummaryForTile(2)
                    navItems: root.laneNavItemsForTile(2)
                    defaultNodeId: "C01"
                    tileIndex: 2
                    titleText: root.tileTitleForIndex(2)
                    initialState: (root.dockedStateByTile[2] !== undefined)
                        ? root.dockedStateByTile[2]
                        : ((root.initialTileIndex === 2) ? root.initialPanelState : null)
                    enabled: root.isInteractive
                    onSubmitRequested: function(state) {
                    }
                    onCancelRequested: function(state) {
                        if (root.detachedWindow && root.windowRef) {
                            try {
                                if (!root.windowRef.requestCloseAnimation || !root.windowRef.requestCloseAnimation()) {
                                    root.windowRef.close()
                                }
                            } catch (e) {
                                try { root.windowRef.close() } catch (e2) { }
                            }
                            return
                        }
                        if (root.option3ShellEnabled && root.option3ActiveTabId) {
                            var tabId = root.option3ActiveTabId
                            Qt.callLater(function() {
                                root.option3CloseTab(tabId, true)
                            })
                            return
                        }
                        if (!root.startPortalReverseTransition(2)) {
                            stack.currentIndex = 0
                        }
                    }
                    onTearAwayRequested: function(state) {
                        if (root.detachedWindow) {
                            root.requestReturnToDockForTile(2, state)
                        } else {
                            root.requestTearAwayForTile(2, state)
                        }
                    }
                    onModuleJumpRequested: function(nextTileIndex, state) {
            var nextIdx = Math.round(nextTileIndex)
            if (nextIdx < 0 || nextIdx >= root.tileTitles.length) return
            var sourceState = root.shallowCloneObject(state)
            var targetState = null
            if (sourceState && sourceState._targetTileState && typeof sourceState._targetTileState === "object") {
                targetState = root.shallowCloneObject(sourceState._targetTileState)
                delete sourceState._targetTileState
            }
            root.applyStateToTile(2, sourceState)
            if (targetState && typeof targetState === "object") {
                root.applyStateToTile(nextIdx, targetState)
            }
            if (root.detachedWindow) {
                var targetStackIndex = root.stackIndexForTile(nextIdx)
                if (targetStackIndex <= 0) return
                root.requestStackPageLoad(targetStackIndex, "module-jump-detached")
                if (stack) {
                    stack.currentIndex = targetStackIndex
                }
                root.activeTileIndex = nextIdx
                root.transitionTitle = root.tileTitleForIndex(nextIdx)
                root.clearHubModuleChooser()
                root.focusShellWindow()
                if (root.windowRef) {
                    try {
                        root.windowRef.detachedInitialTileIndex = nextIdx
                        root.windowRef.detachedPanelTitle = root.tileTitleForIndex(nextIdx)
                        if (root.windowRef.setPanelTaskbarTitle) {
                            root.windowRef.setPanelTaskbarTitle("CSPM - " + root.tileTitleForIndex(nextIdx))
                        }
                    } catch (e0) {
                    }
                }
                return
            }
            root.launchTileFromHome(nextIdx, null)
        }
                    onWorkspaceOpenRequested: function(targetTileIndex, nodeId, state) {
                        root.handleWorkspaceOpenRequested(targetTileIndex, nodeId, state)
                    }
                    onReportWindowRequested: function(reportDocument) {
                        root.openReportWindow(reportDocument)
                    }
                }
            }

            Component {
                id: financeLanePanelComponent
                PlaceholderSubmenuView {
                    anchors.fill: parent
                    t: root.t
                    metrics: root.metrics
                    appRef: root.appRef
                    windowRef: root.windowRef
                    detachedWindow: root.detachedWindow
                    externalNavigationShell: root.option3ShellEnabled
                    laneKey: "finance_ops"
                    laneSummary: root.laneSummaryForTile(3)
                    navItems: root.laneNavItemsForTile(3)
                    defaultNodeId: "D01"
                    tileIndex: 3
                    titleText: root.tileTitleForIndex(3)
                    initialState: (root.dockedStateByTile[3] !== undefined)
                        ? root.dockedStateByTile[3]
                        : ((root.initialTileIndex === 3) ? root.initialPanelState : null)
                    enabled: root.isInteractive
                    onSubmitRequested: function(state) {
                    }
                    onCancelRequested: function(state) {
                        if (root.detachedWindow && root.windowRef) {
                            try {
                                if (!root.windowRef.requestCloseAnimation || !root.windowRef.requestCloseAnimation()) {
                                    root.windowRef.close()
                                }
                            } catch (e) {
                                try { root.windowRef.close() } catch (e2) { }
                            }
                            return
                        }
                        if (!root.startPortalReverseTransition(3)) {
                            stack.currentIndex = 0
                        }
                    }
                    onTearAwayRequested: function(state) {
                        if (root.detachedWindow) {
                            root.requestReturnToDockForTile(3, state)
                        } else {
                            root.requestTearAwayForTile(3, state)
                        }
                    }
                    onModuleJumpRequested: function(nextTileIndex, state) {
            var nextIdx = Math.round(nextTileIndex)
            if (nextIdx < 0 || nextIdx >= root.tileTitles.length) return
            var sourceState = root.shallowCloneObject(state)
            var targetState = null
            if (sourceState && sourceState._targetTileState && typeof sourceState._targetTileState === "object") {
                targetState = root.shallowCloneObject(sourceState._targetTileState)
                delete sourceState._targetTileState
            }
            root.applyStateToTile(3, sourceState)
            if (targetState && typeof targetState === "object") {
                root.applyStateToTile(nextIdx, targetState)
            }
            if (root.detachedWindow) {
                var targetStackIndex = root.stackIndexForTile(nextIdx)
                if (targetStackIndex <= 0) return
                root.requestStackPageLoad(targetStackIndex, "module-jump-detached")
                if (stack) {
                    stack.currentIndex = targetStackIndex
                }
                root.activeTileIndex = nextIdx
                root.transitionTitle = root.tileTitleForIndex(nextIdx)
                root.clearHubModuleChooser()
                root.focusShellWindow()
                if (root.windowRef) {
                    try {
                        root.windowRef.detachedInitialTileIndex = nextIdx
                        root.windowRef.detachedPanelTitle = root.tileTitleForIndex(nextIdx)
                        if (root.windowRef.setPanelTaskbarTitle) {
                            root.windowRef.setPanelTaskbarTitle("CSPM - " + root.tileTitleForIndex(nextIdx))
                        }
                    } catch (e0) {
                    }
                }
                return
            }
            root.launchTileFromHome(nextIdx, null)
        }
                    onWorkspaceOpenRequested: function(targetTileIndex, nodeId, state) {
                        root.handleWorkspaceOpenRequested(targetTileIndex, nodeId, state)
                    }
                    onReportWindowRequested: function(reportDocument) {
                        root.openReportWindow(reportDocument)
                    }
                }
            }

            ReportWindowManager {
                id: reportWindowManager
                appRef: root.appRef
                t: root.t
                sfxBus: root.sfxBus
                windowRef: root.windowRef
                onRecordActionRouted: function(action) {
                    root.routeReportRecordAction(action)
                }
                onReportRefreshRequested: function(reportId, sourceState) {
                    root.refreshReportFromWindow(reportId, sourceState)
                }
                onReportBrandingRequested: function(initiatingWindow) {
                    if (root.windowRef && root.windowRef.openReportBrandingSettings) {
                        root.windowRef.openReportBrandingSettings(initiatingWindow)
                    }
                }
            }

            ProfessionalAppShell {
                id: proAppShell
                anchors.fill: parent
                shellEnabled: root.option3ShellEnabled
                detachedWindow: root.detachedWindow
                t: root.t
                metrics: root.metrics
                sfxBus: root.sfxBus
                appRoot: root
                backdropSource: skylineBackdrop
                appStyle: root.appStyle
                interactive: root.isInteractive
                modules: root.option3NavigationModules
                tabs: root.option3OpenTabs
                favorites: root.option3Favorites
                
                Component.onCompleted: {
                    if (root.appRef) {
                        try {
                            if (root.appRef.option3Favorites) {
                                root.option3Favorites = JSON.parse(root.appRef.option3Favorites)
                            }
                            if (root.appRef.option3PinnedTabs) {
                                var pinned = JSON.parse(root.appRef.option3PinnedTabs)
                                var tabs = root.option3OpenTabs || []
                                for (var i = 0; i < pinned.length; i++) {
                                    var exists = false;
                                    for(var j=0; j < tabs.length; j++) {
                                        if (tabs[j].id === pinned[i].id) exists = true;
                                    }
                                    if (!exists) tabs.push(pinned[i])
                                }
                                root.option3OpenTabs = tabs
                            }
                        } catch(e) {}
                    }
                }

                function saveState() {
                    if (!root.appRef) return
                    var pinned = []
                    var tabs = root.option3OpenTabs || []
                    for (var i = 0; i < tabs.length; i++) {
                        if (tabs[i].pinned) pinned.push(tabs[i])
                    }
                    root.appRef.option3PinnedTabs = JSON.stringify(pinned)
                    root.appRef.option3Favorites = JSON.stringify(root.option3Favorites || [])
                }

                activeModuleId: root.option3ActiveModuleId()
                flyoutModuleId: root.option3FlyoutModuleId
                activeItemId: root.option3ActiveItemId()
                activeTabId: root.option3ActiveTabId
                moduleTitle: root.option3ActiveModuleTitle()
                itemTitle: root.option3ActiveItemTitle()
                subtitle: root.option3ActiveSubtitle()
                activeDirty: root.option3ActiveDirty()
                flyoutModuleData: root.option3FlyoutModuleData()
                closeGuardTabId: root.option3CloseGuardTabId
                closeGuardMessage: root.option3CloseGuardMessage
                rightDrawerState: root.option3RightDrawerState
                onModuleRequested: function(moduleData) {
                    if (String(moduleData.moduleId || "") === "home") {
                        root.option3OpenHomeBriefing()
                        return
                    }
                    root.option3OpenFlyout(moduleData.moduleId)
                }
                onHomeRequested: {
                    root.option3OpenHomeBriefing()
                }
                onDetachedReturnToDockRequested: {
                    root.requestReturnToDockFromDetachedShell()
                }
                onModuleFavoriteRequested: function(moduleData, remove) {
                    if (remove) {
                        var checkId = moduleData.moduleId
                        var favs = root.option3Favorites || []
                        var nextFavs = []
                        for (var i = 0; i < favs.length; i++) {
                            if (favs[i].moduleId !== checkId || favs[i].tabType !== "module") {
                                nextFavs.push(favs[i])
                            }
                        }
                        root.option3Favorites = []
                        Qt.callLater(function() {
                            root.option3Favorites = nextFavs
                            proAppShell.saveState()
                        })
                    } else {
                        root.option3FavoriteModule(moduleData)
                    }
                }
                onItemFavoriteRequested: function(moduleData, itemData, remove) {
                    if (remove) {
                        var checkId = itemData.nodeId || itemData.id || ""
                        var favs = root.option3Favorites || []
                        var nextFavs = []
                        for (var j = 0; j < favs.length; j++) {
                            var favNodeId = favs[j].nodeId || favs[j].id || ""
                            if (favNodeId !== checkId || favs[j].moduleId !== moduleData.moduleId) {
                                nextFavs.push(favs[j])
                            }
                        }
                        root.option3Favorites = []
                        Qt.callLater(function() {
                            root.option3Favorites = nextFavs
                            proAppShell.saveState()
                        })
                    } else {
                        root.option3FavoriteItem(moduleData, itemData)
                    }
                }
                onTabDuplicateRequested: function(tabId) {
                    root.option3DuplicateTab(tabId)
                }
                onTabFavoriteRequested: function(tabId) {
                    root.option3FavoriteTab(tabId)
                }
                onFavoriteRequested: function(favData) {
                    root.option3OpenWorkspace(favData, favData, {})
                }
                onFavoriteRemoveRequested: function(favData) {
                    var favs = root.option3Favorites || []
                    var filtered = []
                    for (var i = 0; i < favs.length; i++) {
                        if (favs[i].id !== favData.id && favs[i].title !== favData.title) {
                            filtered.push(favs[i])
                        }
                    }
                    root.option3Favorites = []
                    Qt.callLater(function() {
                        root.option3Favorites = filtered
                        proAppShell.saveState()
                    })
                }
                onFavoriteReordered: function(fromIndex, toIndex) {
                    var favs = root.option3Favorites || []
                    if (fromIndex >= 0 && fromIndex < favs.length && toIndex >= 0 && toIndex < favs.length) {
                        var item = favs.splice(fromIndex, 1)[0]
                        favs.splice(toIndex, 0, item)
                        root.option3Favorites = Array.from(favs)
                        if (typeof proAppShell !== "undefined" && typeof proAppShell.saveState === "function") {
                            proAppShell.saveState()
                        }
                    }
                }
                onOmniSearchRequested: function(query) {
                    root.handleOmniSearch(query)
                }
                onFlyoutItemRequested: function(moduleData, itemData) {
                    root.option3OpenWorkspace(moduleData, itemData, {})
                }
                onFlyoutDismissed: {
                    root.option3FlyoutModuleId = ""
                }
                onTabActivated: function(tabId) {
                    root.option3ActivateTab(tabId)
                }
                onTabCloseRequested: function(tabId) {
                    root.option3CloseTab(tabId, false)
                }
                onTabOpenInNewWindowRequested: function(tabId) {
                    root.option3OpenTabInNewWindow(tabId)
                }
                onTabPinRequested: function(tabId) {
                    var tabs = root.option3OpenTabs || []
                    for (var i = 0; i < tabs.length; i++) {
                        if (tabs[i].id === tabId) {
                            tabs[i].pinned = !tabs[i].pinned
                            break
                        }
                    }
                    root.option3OpenTabs = Array.from(tabs)
                    proAppShell.saveState()
                }
                onTabReordered: function(fromIndex, toIndex) {
                    var tabs = root.option3OpenTabs || []
                    if (fromIndex >= 0 && fromIndex < tabs.length && toIndex >= 0 && toIndex < tabs.length) {
                        var item = tabs.splice(fromIndex, 1)[0]
                        tabs.splice(toIndex, 0, item)
                        root.option3OpenTabs = Array.from(tabs)
                        proAppShell.saveState()
                    }
                }
                onCloseGuardSaveRequested: {
                    root.option3SaveGuardedTabAndCloseIfClean()
                }
                onCloseGuardDiscardRequested: function(tabId) {
                    root.option3PendingCloseAfterSaveTabId = ""
                    root.option3CloseGuardTabId = ""
                    root.option3CloseGuardMessage = ""
                    root.option3CloseTab(tabId, true)
                }
                onCloseGuardCancelRequested: {
                    root.option3PendingCloseAfterSaveTabId = ""
                    root.option3CloseGuardTabId = ""
                    root.option3CloseGuardMessage = ""
                }
                onRightDrawerDismissed: {
                    root.option3RightDrawerState = ({ "open": false })
                }

                StackLayout {
                    id: stack
                    anchors.fill: parent
                    currentIndex: 0
                    onCurrentIndexChanged: {
                        if (count <= 0) return
                        if (currentIndex < 0) {
                            currentIndex = 0
                            return
                        }
                        if (currentIndex >= count) {
                            currentIndex = count - 1
                            return
                        }
                        if (currentIndex > 0 && root.hubModuleChooserVisible) {
                            root.clearHubModuleChooser()
                        }
                        root.requestStackPageLoad(currentIndex, "stack.currentIndexChanged")
                        if (root.option3ShellEnabled && currentIndex > 0 && !root.option3AutoEnsurePaused) {
                            root.option3EnsureTabForCurrentWorkspace("stack.currentIndexChanged")
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        PracticeBriefingView {
                            id: practiceBriefingView
                            anchors.fill: parent
                            visible: root.isProMode && (!root.option3ShellEnabled || root.option3HasCurrentWorkspace())
                            t: root.t
                            metrics: root.metrics
                            appRef: root.appRef
                            enabled: root.isInteractive && root.isProMode && visible
                            onOpenScreenRequested: function(moduleId, nodeId) {
                                root.option3OpenScreenByModuleNode(moduleId, nodeId)
                            }
                            onNavigateRequested: function(tileIndex, nodeId, state) {
                                root.handleWorkspaceOpenRequested(tileIndex, nodeId, state)
                            }
                            onReportWindowRequested: function(reportDocument) {
                                root.openReportWindow(reportDocument)
                            }
                        }

                        HomeGrid {
                            anchors.fill: parent
                            visible: !root.isProMode
                            t: root.t
                            sfxBus: root.sfxBus
                            metrics: root.metrics
                            windowRef: root.windowRef
                            dashboardSummary: root.dashboardSummary
                            maximized: (root.windowRef && root.windowRef.uiMaximized) ? true : false
                            enabled: root.isInteractive && !root.isProMode
                            onTileClicked: function(idx, geom) {
                                root.playSfxTilePress()
                                root.launchTileFromHome(idx, geom)
                            }
                            onHubClicked: function(hubIndex, moduleIndexes, geom) {
                                root.playSfxTilePress()
                                var modules = root.normalizedHubModules(moduleIndexes)
                                if (modules.length <= 0) {
                                    return
                                }
                                if (modules.length === 1) {
                                    root.launchTileFromHome(modules[0], geom)
                                    return
                                }
                                if (!root.openHubSelection(hubIndex, modules, geom)) {
                                    root.launchTileFromHome(modules[0], geom)
                                }
                            }
                            onOmniSearchRequested: function(query) {
                                root.handleOmniSearch(query)
                            }
                        }

                        Rectangle {
                            id: proEmptyWorkspace
                            anchors.fill: parent
                            // This is the native Professional background and
                            // quick-tile home shown whenever all tabs close.
                            visible: root.option3ShellEnabled && !root.option3HasCurrentWorkspace()
                            color: root.proBackground
                            property var quickTiles: [
                                { "title": "Practice Briefing", "subtitle": "Today", "icon": "\uE80F", "moduleId": "home", "nodeId": "H01" },
                                { "title": "Client Directory", "subtitle": "Clients", "icon": "\uE77B", "moduleId": "clients", "nodeId": "A01" },
                                { "title": "Time Docket Entry", "subtitle": "Docketing", "icon": "\uE823", "moduleId": "docketing", "nodeId": "B01" },
                                { "title": "Docket Activity Report", "subtitle": "Reports", "icon": "\uE9D9", "moduleId": "docketing", "nodeId": "B04" }
                            ]

                            ColumnLayout {
                                id: emptyWorkspaceLayout
                                width: Math.min(760, Math.max(320, proEmptyWorkspace.width - 80))
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 16

                                Text {
                                    Layout.fillWidth: true
                                    text: "Workspace Home"
                                    font.family: "Segoe UI"
                                    font.pixelSize: 22
                                    font.weight: Font.DemiBold
                                    color: root.proInk
                                    horizontalAlignment: Text.AlignHCenter
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "No open tabs"
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                    color: root.proMutedInk
                                    horizontalAlignment: Text.AlignHCenter
                                    elide: Text.ElideRight
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: Math.max(1, Math.min(4, Math.floor((emptyWorkspaceLayout.width + 12) / 170)))
                                    columnSpacing: 12
                                    rowSpacing: 12

                                    Repeater {
                                        model: proEmptyWorkspace.quickTiles
                                        delegate: Rectangle {
                                            id: emptyTile
                                            required property var modelData
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 86
                                            radius: 5
                                            color: emptyTileHover.hovered ? root.proHoverFill : root.proSurface
                                            border.width: 1
                                            border.color: emptyTileHover.hovered ? root.proActiveBorder : root.proBorder

                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 5

                                                Text {
                                                    text: emptyTile.modelData.icon
                                                    font.family: "Segoe MDL2 Assets"
                                                    font.pixelSize: 20
                                                    color: root.proAccent
                                                    Layout.alignment: Qt.AlignHCenter
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: emptyTile.modelData.title
                                                    font.family: "Segoe UI"
                                                    font.pixelSize: 12
                                                    font.weight: Font.DemiBold
                                                    color: root.proInk
                                                    horizontalAlignment: Text.AlignHCenter
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: emptyTile.modelData.subtitle
                                                    font.family: "Segoe UI"
                                                    font.pixelSize: 11
                                                    color: root.proMutedInk
                                                    horizontalAlignment: Text.AlignHCenter
                                                    elide: Text.ElideRight
                                                }
                                            }

                                            HoverHandler {
                                                id: emptyTileHover
                                            }

                                            TapHandler {
                                                onTapped: {
                                                    root.option3OpenScreenByModuleNode(
                                                        String(emptyTile.modelData.moduleId || ""),
                                                        String(emptyTile.modelData.nodeId || "")
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Loader {
                        id: clientsLanePanelLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: root.isStackPageLoadRequested(1)
                        asynchronous: stack.currentIndex !== 1
                        sourceComponent: clientsLanePanelComponent
                    }
                    Loader {
                        id: docketLanePanelLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.margins: root.bodyMarginPx
                        active: root.isStackPageLoadRequested(2)
                        asynchronous: stack.currentIndex !== 2
                        sourceComponent: docketLanePanelComponent
                    }
                    Loader {
                        id: billingLanePanelLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: root.isStackPageLoadRequested(3)
                        asynchronous: stack.currentIndex !== 3
                        sourceComponent: billingLanePanelComponent
                    }
                    Loader {
                        id: financeLanePanelLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: root.isStackPageLoadRequested(4)
                        asynchronous: stack.currentIndex !== 4
                        sourceComponent: financeLanePanelComponent
                    }
                }
            }

            Item {
                id: hubChooserOverlay
                anchors.fill: parent
                z: 180
                visible: root.hubModuleChooserVisible && stack.currentIndex === 0 && !root.portalTransitionActive
                enabled: visible

                Rectangle {
                    anchors.fill: parent
                    color: Qt.rgba(root.panelColor.r, root.panelColor.g, root.panelColor.b, 0.62)
                }

                Rectangle {
                    id: hubChooserCard
                    property color baseColor: root.lightTheme
                        ? Qt.rgba(root.panel2Color.r, root.panel2Color.g, root.panel2Color.b, 0.975)
                        : Qt.rgba(root.panelColor.r, root.panelColor.g, root.panelColor.b, 0.96)
                    property color inkColor: root.readableInk(baseColor)
                    property color subInkColor: Qt.rgba(inkColor.r, inkColor.g, inkColor.b, 0.84)
                    property int cardPadPx: root.ratioPx(root.scaleRatios.hubChooserPadPct * 1.04, 10)
                    property int actionHeightPx: root.ratioPx(0.043, 34)
                    property int maxCardWidthPx: Math.max(
                        320,
                        Math.min(
                            Math.round(bodyHost.width - root.ratioPx(0.08, 56)),
                            root.ratioPx(0.44, 560)
                        )
                    )
                    property int minCardWidthPx: Math.max(
                        300,
                        Math.min(maxCardWidthPx, root.ratioPx(0.28, 380))
                    )
                    width: root.clampNumber(
                        root.ratioPx(0.36, 440),
                        minCardWidthPx,
                        maxCardWidthPx
                    )
                    height: {
                        var maxCardHeight = Math.max(140, Math.round(bodyHost.height - root.ratioPx(0.10, 72)));
                        var minCardHeight = root.ratioPx(0.17, 170);
                        var idealHeight = hubChooserColumn.implicitHeight + (cardPadPx * 2);
                        return Math.max(minCardHeight, Math.min(maxCardHeight, idealHeight));
                    }
                    x: Math.round((bodyHost.width - width) * 0.5)
                    y: Math.round((bodyHost.height - height) * 0.5)
                    radius: root.ratioPx(root.scaleRatios.undockTabRadiusPct * 1.20, 12)
                    color: baseColor
                    border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubPanelBorderPct * 1.45, 1))
                    border.color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, (root ? (root ? root.lightTheme : false) : false) ? 0.52 : 0.68)
                    clip: true
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: Qt.rgba(0, 0, 0, (root ? (root ? root.lightTheme : false) : false) ? 0.24 : 0.52)
                        shadowBlur: (root ? (root ? root.lightTheme : false) : false) ? 0.28 : 0.48
                        shadowVerticalOffset: root.ratioPx(0.0027, 2)
                        shadowHorizontalOffset: 0
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: root.ratioPx(0.052, 22)
                        color: "transparent"
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, (root ? (root ? root.lightTheme : false) : false) ? 0.14 : 0.11) }
                            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
                        }
                    }

                    ColumnLayout {
                        id: hubChooserColumn
                        anchors.fill: parent
                        anchors.margins: hubChooserCard.cardPadPx
                        spacing: root.ratioPx(root.scaleRatios.hubChooserGapPct * 1.24, 8)

                        Text {
                            Layout.fillWidth: true
                            text: "Choose module"
                            color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.98)
                            font.pixelSize: root.ratioPx(0.021, root.metricFloor("fontFloorTitlePx", 13))
                            font.weight: Font.DemiBold
                            layer.enabled: true
                            layer.effect: MultiEffect {
                                shadowEnabled: true
                                shadowColor: Qt.rgba(0, 0, 0, 0.46)
                                shadowBlur: 0.22
                                shadowVerticalOffset: 1
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Hub routes multiple workflows. Select the module to open."
                            color: hubChooserCard.subInkColor
                            wrapMode: Text.WordWrap
                            font.pixelSize: root.ratioPx(0.014, root.metricFloor("fontFloorLabelPx", 10))
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(1, root.ratioPx(root.scaleRatios.hubPanelBorderPct, 1))
                            color: Qt.rgba(hubChooserCard.inkColor.r, hubChooserCard.inkColor.g, hubChooserCard.inkColor.b, 0.14)
                        }

                        Repeater {
                            model: root.hubModuleChooserRows
                            delegate: PillButton {
                                required property var modelData
                                t: root.t
                                metrics: root.metrics
                                sfxBus: root.sfxBus
                                text: modelData.titleText
                                primary: false
                                Layout.fillWidth: true
                                Layout.preferredHeight: hubChooserCard.actionHeightPx
                                onClicked: {
                                    root.playSfxUiClick("tile", 0.42)
                                    root.launchHubChooserRow(modelData.tileIndex)
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: root.ratioPx(0.004, 3)

                            Item { Layout.fillWidth: true }

                            PillButton {
                                t: root.t
                                metrics: root.metrics
                                sfxBus: root.sfxBus
                                text: "Cancel"
                                primary: false
                                Layout.preferredWidth: root.ratioPx(0.120, 96)
                                Layout.preferredHeight: hubChooserCard.actionHeightPx
                                onClicked: root.clearHubModuleChooser()
                            }
                        }
                    }
                }

                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    onTapped: function(eventPoint) {
                        var local = hubChooserCard.mapFromItem(hubChooserOverlay, eventPoint.position.x, eventPoint.position.y)
                        var inside = local.x >= 0
                            && local.y >= 0
                            && local.x <= hubChooserCard.width
                            && local.y <= hubChooserCard.height
                        if (!inside) {
                            root.clearHubModuleChooser()
                        }
                    }
                }
            }

            Item {
                id: undockTab
                z: 190
                visible: root.floatingUndockTabEnabled
                    && !root.detachedWindow
                    && stack.currentIndex > 0
                    && stack.currentIndex !== 1
                    && !root.portalTransitionActive
                    && root.isInteractive
                width: root.ratioPx(root.scaleRatios.undockTabWidthPct, 220)
                height: root.ratioPx(root.scaleRatios.undockTabHeightPct, 38)
                property color baseColor: root.lightTheme
                    ? Qt.rgba(root.panel2Color.r, root.panel2Color.g, root.panel2Color.b, 0.96)
                    : Qt.rgba(root.panelColor.r, root.panelColor.g, root.panelColor.b, 0.94)
                property real homeX: Math.round(bodyHost.width - width - root.ratioPx(0.014, 10))
                property real homeY: root.ratioPx(0.014, 10)
                x: homeX
                y: homeY

                onVisibleChanged: {
                    if (visible) {
                        x = homeX
                        y = homeY
                    }
                }
                onHomeXChanged: {
                    if (!undockDrag.active && !undockReturn.running) {
                        x = homeX
                    }
                }
                onHomeYChanged: {
                    if (!undockDrag.active && !undockReturn.running) {
                        y = homeY
                    }
                }

                Rectangle {
                    id: undockTabGlass
                    anchors.fill: parent
                    radius: root.ratioPx(root.scaleRatios.undockTabRadiusPct, 10)
                    color: undockHover.hovered
                        ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, (root ? (root ? root.lightTheme : false) : false) ? 0.26 : 0.32)
                        : undockTab.baseColor
                    border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubPanelBorderPct, 1))
                    border.color: undockHover.hovered
                        ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, undockDrag.active ? 0.98 : 0.74)
                        : Qt.rgba(root.textColor.r, root.textColor.g, root.textColor.b, 0.28)
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: Qt.rgba(0, 0, 0, undockHover.hovered ? 0.30 : 0.22)
                        shadowBlur: undockHover.hovered ? 0.26 : 0.18
                        shadowVerticalOffset: root.ratioPx(0.0023, 1)
                        shadowHorizontalOffset: 0
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: root.ratioPx(0.010, 8)
                    anchors.rightMargin: root.ratioPx(0.010, 8)
                    spacing: root.ratioPx(0.006, 5)

                    Text {
                        text: "\uE7C3"
                        font.family: "Segoe MDL2 Assets"
                        color: root.readableInk(undockTabGlass.color)
                        font.pixelSize: root.ratioPx(0.016, 10)
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Undock " + root.tileTitleForIndex(root.tileIndexForStack(stack.currentIndex))
                        color: root.readableInk(undockTabGlass.color)
                        font.pixelSize: root.ratioPx(0.013, root.metricFloor("fontFloorLabelPx", 9))
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.alignment: Qt.AlignVCenter
                    }
                }

                HoverHandler {
                    id: undockHover
                    acceptedDevices: PointerDevice.Mouse
                }

                DragHandler {
                    id: undockDrag
                    target: undockTab
                    dragThreshold: 0
                    xAxis.enabled: true
                    yAxis.enabled: true

                    onActiveChanged: {
                        if (active) {
                            root.playSfxUiClick("hover", 0.28)
                            return
                        }

                        var threshold = root.ratioPx(root.scaleRatios.undockTabDragThresholdPct, 44)
                        var center = bodyHost.mapFromItem(undockTab, undockTab.width * 0.5, undockTab.height * 0.5)
                        var outside = center.x < -threshold
                            || center.y < -threshold
                            || center.x > bodyHost.width + threshold
                            || center.y > bodyHost.height + threshold

                        if (outside) {
                            var gp = undockTab.mapToGlobal(0, 0)
                            var sourceRect = Qt.rect(
                                Math.round(gp.x),
                                Math.round(gp.y),
                                Math.round(undockTab.width),
                                Math.round(undockTab.height)
                            )
                            root.requestUndockFromActiveModule(sourceRect)
                        }

                        undockReturnX.to = undockTab.homeX
                        undockReturnY.to = undockTab.homeY
                        undockReturn.start()
                    }
                }

                ParallelAnimation {
                    id: undockReturn
                    running: false
                    NumberAnimation {
                        id: undockReturnX
                        target: undockTab
                        property: "x"
                        duration: 170
                        easing.type: Easing.InOutQuad
                    }
                    NumberAnimation {
                        id: undockReturnY
                        target: undockTab
                        property: "y"
                        duration: 170
                        easing.type: Easing.InOutQuad
                    }
                }
            }

            Item {
                id: portalLayer
                anchors.fill: parent
                z: 200
                enabled: false
                visible: root.portalTransitionActive
                clip: false

                Rectangle {
                    id: jellyLaunchWindow
                    readonly property real p: root.clamp01(root.portalProgress)
                    readonly property real launch: root.jellyLaunchProgress(p)
                    readonly property real wobble: Math.sin((p * Math.PI * 5.0) + 0.35) * (1.0 - p) * root.scaleRatios.jellySquishStrength
                    readonly property real baseX: root.mix(root.launchStartX, root.launchEndX, launch)
                    readonly property real baseY: root.mix(root.launchStartY, root.launchEndY, launch)
                    readonly property real baseW: Math.max(1, root.mix(root.launchStartW, root.launchEndW, launch))
                    readonly property real baseH: Math.max(1, root.mix(root.launchStartH, root.launchEndH, launch))
                    readonly property real stretchX: Math.max(0.72, 1.0 + (wobble * 0.56))
                    readonly property real stretchY: Math.max(0.72, 1.0 - (wobble * 0.46))
                    readonly property real launchRadiusPx: root.mix(root.launchStartRadius, root.launchEndRadius, launch)
                    readonly property real cornerCapPx: Math.max(2, Math.round(Math.min(width, height) * 0.20))
                    width: Math.max(1, Math.round(baseW * stretchX))
                    height: Math.max(1, Math.round(baseH * stretchY))
                    x: Math.round(baseX - ((width - baseW) * 0.5))
                    y: Math.round(baseY - ((height - baseH) * 0.5))
                    radius: Math.max(1, Math.min(cornerCapPx, Math.round(launchRadiusPx * (1.0 + (Math.abs(wobble) * 0.22)))))
                    rotation: Math.sin(p * Math.PI * 3.4) * (1.0 - p) * 4.4
                    clip: true
                    color: Qt.rgba(root.portalPanelColor.r, root.portalPanelColor.g, root.portalPanelColor.b, 0.96)
                    border.width: root.ratioPx(root.scaleRatios.portalRingBorderPct * 0.94, 1)
                    border.color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.66)
                    opacity: {
                        var p = root.clamp01(root.portalProgress)
                        if (p < root.portalSwitchProgress) return 1.0
                        var post = (p - root.portalSwitchProgress) / Math.max(0.001, 1.0 - root.portalSwitchProgress)
                        return Math.max(0.0, 1.0 - post)
                    }

                    Rectangle {
                        id: launchTopBar
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: Math.max(1, Math.round(parent.height * root.scaleRatios.jellyLaunchTopBarPct))
                        color: Qt.rgba(root.portalPanelColor.r, root.portalPanelColor.g, root.portalPanelColor.b, 0.88)
                        border.width: 0
                    }

                    Rectangle {
                        anchors.left: launchTopBar.left
                        anchors.right: launchTopBar.right
                        anchors.bottom: launchTopBar.bottom
                        height: root.ratioPx(root.scaleRatios.portalRingBorderPct * 0.82, 1)
                        color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.38)
                    }

                    Row {
                        anchors.left: launchTopBar.left
                        anchors.leftMargin: Math.max(1, Math.round(Math.min(jellyLaunchWindow.width, jellyLaunchWindow.height) * root.scaleRatios.jellyLaunchPreviewPaddingPct))
                        anchors.verticalCenter: launchTopBar.verticalCenter
                        spacing: Math.max(1, Math.round(Math.min(jellyLaunchWindow.width, jellyLaunchWindow.height) * root.scaleRatios.jellyLaunchPreviewGapPct))
                        Rectangle {
                            width: Math.max(1, Math.round(launchTopBar.height * 0.22))
                            height: width
                            radius: width / 2
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.40)
                        }
                        Rectangle {
                            width: Math.max(1, Math.round(launchTopBar.height * 0.22))
                            height: width
                            radius: width / 2
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.24)
                        }
                        Rectangle {
                            width: Math.max(1, Math.round(launchTopBar.height * 0.22))
                            height: width
                            radius: width / 2
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.24)
                        }
                    }

                    Text {
                        anchors.centerIn: launchTopBar
                        text: (root.transitionTitle && root.transitionTitle.length > 0) ? root.transitionTitle : "Module"
                        color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.86)
                        font.pixelSize: Math.max(10, Math.round(Math.min(jellyLaunchWindow.width, jellyLaunchWindow.height) * 0.036))
                        font.weight: Font.DemiBold
                    }

                    Item {
                        id: launchPreview
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: launchTopBar.bottom
                        anchors.bottom: parent.bottom
                        anchors.margins: Math.max(1, Math.round(Math.min(jellyLaunchWindow.width, jellyLaunchWindow.height) * root.scaleRatios.jellyLaunchPreviewPaddingPct))

                        property int gapPx: Math.max(1, Math.round(Math.min(width, height) * root.scaleRatios.jellyLaunchPreviewGapPct))
                        property int rowHeightPx: Math.max(1, Math.round(height * root.scaleRatios.jellyLaunchPreviewRowPct))

                        Rectangle {
                            id: previewCardLeft
                            x: 0
                            y: 0
                            width: Math.max(1, Math.round((launchPreview.width - launchPreview.gapPx) * 0.56))
                            height: Math.max(1, Math.round(launchPreview.height * 0.55))
                            radius: Math.max(1, Math.round(Math.min(width, height) * 0.08))
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.13)
                            border.width: root.ratioPx(root.scaleRatios.portalRingBorderPct * 0.68, 1)
                            border.color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.34)
                        }

                        Rectangle {
                            x: previewCardLeft.x + previewCardLeft.width + launchPreview.gapPx
                            y: 0
                            width: Math.max(1, launchPreview.width - x)
                            height: previewCardLeft.height
                            radius: previewCardLeft.radius
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.10)
                            border.width: root.ratioPx(root.scaleRatios.portalRingBorderPct * 0.62, 1)
                            border.color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.28)
                        }

                        Rectangle {
                            x: 0
                            y: previewCardLeft.height + launchPreview.gapPx
                            width: launchPreview.width
                            height: Math.max(1, launchPreview.rowHeightPx)
                            radius: Math.max(1, Math.round(height * 0.45))
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.17)
                        }

                        Rectangle {
                            x: 0
                            y: previewCardLeft.height + launchPreview.gapPx + height + launchPreview.gapPx
                            width: Math.max(1, Math.round(launchPreview.width * 0.78))
                            height: Math.max(1, launchPreview.rowHeightPx)
                            radius: Math.max(1, Math.round(height * 0.45))
                            color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.14)
                        }
                    }
                }

                Rectangle {
                    anchors.centerIn: jellyLaunchWindow
                    width: Math.max(1, Math.round(jellyLaunchWindow.width * (1.05 + (root.portalProgress * 0.28))))
                    height: Math.max(1, Math.round(jellyLaunchWindow.height * (1.08 + (root.portalProgress * 0.34))))
                    radius: Math.max(1, Math.round(jellyLaunchWindow.radius * 1.18))
                    color: "transparent"
                    border.width: root.ratioPx(root.scaleRatios.portalRingBorderPct * 0.78, 1)
                    border.color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.46)
                    opacity: Math.max(0.0, jellyLaunchWindow.opacity * (1.0 - root.portalProgress))
                }

                Rectangle {
                    anchors.centerIn: jellyLaunchWindow
                    width: Math.max(1, Math.round(jellyLaunchWindow.width * (1.10 + ((1.0 - root.portalProgress) * 0.13))))
                    height: Math.max(1, Math.round(jellyLaunchWindow.height * (1.12 + ((1.0 - root.portalProgress) * 0.15))))
                    radius: Math.max(1, Math.round(jellyLaunchWindow.radius * 1.28))
                    color: Qt.rgba(root.portalAccentColor.r, root.portalAccentColor.g, root.portalAccentColor.b, 0.14)
                    opacity: Math.max(0.0, jellyLaunchWindow.opacity * (1.0 - (root.portalProgress * 0.52)))
                    z: -1
                }
            }
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onHomeDashboardSummaryUpdated(payload) {
            if (payload && typeof payload === "object" && payload.ok !== undefined) {
                root.dashboardSummary = payload
            }
        }
        function onClientDataChanged() {
            root.refreshDashboardSummary()
        }
        function onBackendBootChanged() {
            if (root.appRef && root.appRef.backendBooted) {
                Qt.callLater(function() {
                    root.refreshDashboardSummaryNow()
                })
            }
        }
    }

    Connections {
        target: root.windowRef
        function onStartupHeavyWorkAllowedChanged() {
            if (root.windowRef && root.windowRef.startupHeavyWorkAllowed) {
                root.scheduleStartupStackPrewarm("window.startupHeavyWorkAllowed")
            }
        }
    }

    Timer {
        id: dashboardRefreshTimer
        interval: 60000
        repeat: true
        running: root.visible
        onTriggered: root.refreshDashboardSummary()
    }

    Timer {
        id: startupDashboardRetryTimer
        interval: 180
        repeat: false
        onTriggered: {
            root._startupDashboardRefreshPending = false
            root.refreshDashboardSummary()
        }
    }

    Timer {
        id: startupStackPrewarmTimer
        interval: 220
        repeat: false
        onTriggered: {
            root.runStartupStackPrewarmTick()
        }
    }

    Timer {
        id: option3TabStateRefreshTimer
        interval: 800
        repeat: true
        running: root.option3ShellEnabled
        onTriggered: {
            root.option3SyncOpenTabsFromPanels()
            root.option3TryCompletePendingCloseAfterSave()
        }
    }

    Component.onCompleted: {
        refreshDashboardSummary()
        applyInitialSelection()
        ensureStartupProfessionalHome()
        option3EnsureTabForCurrentWorkspace("Component.onCompleted")
        scheduleStartupStackPrewarm("Component.onCompleted")
    }

    onInitialTileIndexChanged: {
        applyInitialSelection()
        option3EnsureTabForCurrentWorkspace("initialTileIndexChanged")
    }

    onOption3ShellEnabledChanged: {
        if (option3ShellEnabled) {
            ensureStartupProfessionalHome()
            option3EnsureTabForCurrentWorkspace("option3ShellEnabled")
        } else {
            option3FlyoutModuleId = ""
            option3PendingCloseAfterSaveTabId = ""
            option3CloseGuardTabId = ""
            option3CloseGuardMessage = ""
            option3RightDrawerState = ({ "open": false })
        }
    }

    onAppRefChanged: {
        if (appRef) {
            refreshDashboardSummary()
        }
    }

    onVisibleChanged: {
        if (visible) {
            refreshDashboardSummary()
            scheduleStartupStackPrewarm("onVisibleChanged")
        }
    }
}
