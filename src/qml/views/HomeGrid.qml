import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Shapes
import Qt5Compat.GraphicalEffects
import "../components"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    property var t: ({})
    property var sfxBus: null
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property bool searchBarDebugEnabled: !!(
        appRef
        && appRef.runtimeConfig
        && appRef.runtimeConfig.searchBarDebugEnabled === true
    )
    property var metrics
    property var windowRef: null
    property bool maximized: false
    property color bgColor: SemanticTheme.surfaceApp(root.t, "Professional")
    property color panelColor: SemanticTheme.surfacePanel(root.t, "Professional")
    property color panel2Color: SemanticTheme.surfaceRaised(root.t, "Professional")
    property color accentColor: SemanticTheme.accentPrimary(root.t, "Professional")
    property color textColor: SemanticTheme.inkPrimary(root.t, "Professional")
    property real bgLuma: (root.bgColor.r * 0.299) + (root.bgColor.g * 0.587) + (root.bgColor.b * 0.114)
    property bool lightTheme: root.bgLuma >= 0.58
    property bool searchBarDebug: !!searchBarDebugEnabled

    Connections {
        target: root.windowRef
        ignoreUnknownSignals: true
        function onUniversalSearchTriggered() {
            omniInput.forceActiveFocus()
        }
    }
    signal tileClicked(int index, rect geometry)
    signal hubClicked(int hubIndex, var moduleIndexes, rect geometry)
    signal omniSearchRequested(string query)

    property var scaleRatios: ({
        "outerMarginPct": 0.022,
        "headerGapPct": 0.016,
        "greetingFontPct": 0.074,
        "summaryFontPct": 0.024,
        "omniWidthPct": 0.62,
        "omniHeightPct": 0.062,
        "omniRadiusPct": 0.020,
        "hubPanelRadiusPct": 0.036,
        "hubPanelBorderPct": 0.0013,
        "hubGridGapPct": 0.014,
        "hubCardRadiusPct": 0.022,
        "hubCardBorderPct": 0.0016,
        "hubIconPct": 0.102,
        "hubTitlePct": 0.0252,
        "hubSubtitlePct": 0.0148,
        "quickButtonHeightPct": 0.076,
        "quickButtonGapPct": 0.021
    })

    readonly property var quickActionModel: [
        { "tileIndex": 0, "title": "Add New Client", "icon": "\uE77B", "query": "new client wizard" },
        { "tileIndex": 0, "title": "Add New Matter", "icon": "\uE7C3", "query": "new matter wizard" },
        { "tileIndex": 1, "title": "New Time Docket", "icon": "\uE823", "query": "time docket entry" },
        { "tileIndex": 1, "title": "Docket Activity Report", "icon": "\uE9D9", "query": "docket activity report" },
        { "tileIndex": 1, "title": "Capture Fee Docket", "icon": "\uE8A5", "query": "fee docket entry" },
        { "tileIndex": 1, "title": "New Trademark Filing", "icon": "\uE8A0", "query": "trademark filing" },
        { "tileIndex": 1, "title": "Open Deadline Calendar", "icon": "\uE787", "query": "deadline master calendar" },
        { "tileIndex": 2, "title": "Create Invoice", "icon": "\uE90E", "query": "invoice builder" },
        { "tileIndex": 2, "title": "Record Payment", "icon": "\uE8C7", "query": "payment entry" },
        { "tileIndex": 2, "title": "Log Expense", "icon": "\uE825", "query": "expense entry" },
        { "tileIndex": 2, "title": "Post HST/GST", "icon": "\uE8D2", "query": "hst remittance center" },
        { "tileIndex": 3, "title": "Executive Dashboard", "icon": "\uE9D2", "query": "executive dashboard" },
        { "tileIndex": 3, "title": "A/R Aging Report", "icon": "\uE9D9", "query": "a/r aging detail" },
        { "tileIndex": 3, "title": "Productivity Report", "icon": "\uE9F9", "query": "productivity report" }
    ]

    property var hubModel: [
        {
            "title": "Clients & Matters",
            "subtitle": "Active Matters: " + String(Math.max(0, Number(root.dashboardSummary.activeMatterCount || 0)))
                        + "  (Clients: " + String(Math.max(0, Number(root.dashboardSummary.activeClientCount || 0))) + ")",
            "detail": "Profiles, contacts, hierarchy, conflicts",
            "iconSource": Qt.resolvedUrl("../../../assets/folder_icon_detail.svg"),
            "moduleIndexes": [0]
        },
        {
            "title": "Docketing & Deadlines",
            "subtitle": "Deadlines: " + String(Math.max(0, Number(root.dashboardSummary.deadlinesCount || 0))),
            "detail": "Time/fee dockets, ticklers, filing calendar",
            "iconSource": Qt.resolvedUrl("../assets/icons/hub_critical_dates_docketing.svg"),
            "iconFrameSource": Qt.resolvedUrl("../assets/icons/hub_critical_dates_docketing_triangle_frame.svg"),
            "moduleIndexes": [1]
        },
        {
            "title": "Billing, Payments & Tax",
            "subtitle": "Unbilled Drafts: " + String(Math.max(0, Number(root.dashboardSummary.unbilledDraftCount || 0))),
            "detail": "Invoices, payments, expenses, HST/GST",
            "iconSource": Qt.resolvedUrl("../assets/icons/hub_financial_forecaster.svg"),
            "moduleIndexes": [2]
        },
        {
            "title": "Finance, Reports & Operations",
            "subtitle": "Queue Items: " + String(Math.max(0, Number(root.dashboardSummary.queueCount || 0))),
            "detail": "Dashboards, ledgers, A/R, WIP, forecasting",
            "iconSource": Qt.resolvedUrl("../../../assets/ui_layout_icon_detail.svg"),
            "moduleIndexes": [3]
        }
    ]

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

    function contentUnit() {
        var rw = root.width
        var rh = root.height
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            rw = metrics.contentW
            rh = metrics.contentH
        }
        return Math.min(Math.max(1, rw), Math.max(1, rh))
    }

    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentUnit() * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    function alphaText(a) {
        return Qt.rgba(root.textColor.r, root.textColor.g, root.textColor.b, a)
    }

    function alphaInk(a) {
        return Qt.rgba(0, 0, 0, a)
    }

    function alphaAccent(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    function panelAlpha(a) {
        return Qt.rgba(root.panelColor.r, root.panelColor.g, root.panelColor.b, a)
    }

    function colorLuma(c) {
        return (c.r * 0.299) + (c.g * 0.587) + (c.b * 0.114)
    }

    function readableInk(fillColor, alpha) {
        var a = (typeof alpha === "number") ? alpha : 0.96
        if (root.colorLuma(fillColor) >= 0.60) {
            return Qt.rgba(0.07, 0.09, 0.13, a)
        }
        return Qt.rgba(0.96, 0.98, 1.00, a)
    }

    function currentGreeting() {
        var hour = (new Date()).getHours()
        if (hour < 12) return "Good morning, Cory."
        if (hour < 18) return "Good afternoon, Cory."
        return "Good evening, Cory."
    }

    function pluralize(count, singular, plural) {
        return count === 1 ? singular : (plural || (singular + "s"))
    }

    function dailySummary() {
        var hour = (new Date()).getHours()
        if (!root.dashboardSummary || !root.dashboardSummary.ok) {
            return (hour < 18)
                ? "Review pending queue items and priorities for today."
                : "Daily review is available. Validate timers and finalize pending entries."
        }

        var deadlines = Math.max(0, Number(root.dashboardSummary.deadlinesCount || 0))
        var unbilled = Math.max(0, Number(root.dashboardSummary.unbilledDraftCount || 0))
        var meetings = Math.max(0, Number(root.dashboardSummary.clientMeetingCount || 0))
        var queue = Math.max(0, Number(root.dashboardSummary.queueCount || (deadlines + unbilled + meetings)))

        if (queue <= 0) {
            return "Queue is clear. No deadlines, drafts, or meetings pending."
        }
        return deadlines + " " + root.pluralize(deadlines, "deadline")
            + ", " + unbilled + " unbilled " + root.pluralize(unbilled, "draft")
            + ", and " + meetings + " client " + root.pluralize(meetings, "meeting") + "."
    }

    function refreshDashboardSummary() {
        if (!root.appRef || !root.appRef.getHomeDashboardSummary) return
        try {
            var payload = root.appRef.getHomeDashboardSummary()
            if (payload && typeof payload === "object" && payload.ok !== undefined) {
                root.dashboardSummary = payload
            }
        } catch (e) {
        }
    }

    Connections {
        target: root.appRef
        function onHomeDashboardSummaryUpdated(payload) {
            if (payload && typeof payload === "object" && payload.ok !== undefined) {
                root.dashboardSummary = payload
            }
        }
        function onBackendBootChanged() {
            if (root.appRef && root.appRef.backendBooted) {
                root.refreshDashboardSummary()
            }
        }
        function onClientDataChanged() {
            if (root.appRef && root.appRef.backendBooted) {
                root.refreshDashboardSummary()
            }
        }
    }

    function themeBucket() {
        var accent = root.accentColor
        if (accent.g >= accent.r && accent.g >= accent.b) return "emerald"
        if (accent.b >= accent.r && accent.b >= accent.g) return "sapphire"
        return "crimson"
    }

    function themeBackgroundSource() {
        return Qt.resolvedUrl("../../../assets/home_skyline_bw.png")
    }

    function backgroundColorizationStrength() {
        if (root.lightTheme) return 0.06
        var bucket = themeBucket()
        if (bucket === "sapphire") return 0.18
        if (bucket === "emerald") return 0.17
        return 0.20
    }

    function sourceRectFor(itemRef) {
        if (!itemRef || !backdropScene) {
            return Qt.rect(0, 0, Math.max(1, root.width), Math.max(1, root.height))
        }
        var p = itemRef.mapToItem(backdropScene, 0, 0)
        return Qt.rect(
            Math.round(p.x),
            Math.round(p.y),
            Math.max(1, Math.round(itemRef.width)),
            Math.max(1, Math.round(itemRef.height))
        )
    }

    function logSearchBarLayer(tag, itemRef, radiusPx, extra) {
        if (!root.searchBarDebug || !itemRef) return
        var p = itemRef.mapToItem(root, 0, 0)
        var msg = "[SEARCHBAR] " + tag
            + " rootXY=" + Math.round(p.x) + "," + Math.round(p.y)
            + " wh=" + Math.round(itemRef.width) + "x" + Math.round(itemRef.height)
            + " r=" + Math.round((typeof radiusPx === "number") ? radiusPx : 0)
        if (extra && String(extra).length > 0) {
            msg += " " + extra
        }
        console.log(msg)
    }

    function playHoverSfx(strengthNorm) {
        if (root.sfxBus && root.sfxBus.playUiClick) {
            root.sfxBus.playUiClick("tile-hover", Math.max(0.18, Math.min(0.60, strengthNorm)))
        }
    }

    function emitTile(index, itemRef) {
        if (!itemRef) return
        var globalPos = itemRef.mapToGlobal(0, 0)
        root.tileClicked(index, Qt.rect(globalPos.x, globalPos.y, itemRef.width, itemRef.height))
    }

    function emitHub(index, moduleIndexes, itemRef) {
        if (!itemRef) return
        var globalPos = itemRef.mapToGlobal(0, 0)
        root.hubClicked(index, moduleIndexes, Qt.rect(globalPos.x, globalPos.y, itemRef.width, itemRef.height))
    }

    property real dpiScaleFactor: (metrics && typeof metrics.scalePercent === "number")
        ? Math.max(1.0, metrics.scalePercent / 100.0)
        : 1.0
    property int greetingFontPx: {
        var basePx = root.ratioPx(root.scaleRatios.greetingFontPct, root.metricFloor("fontFloorTitlePx", 14))
        return Math.max(24, Math.round(basePx))
    }
    property int summaryFontPx: {
        var basePx = root.ratioPx(root.scaleRatios.summaryFontPct, root.metricFloor("fontFloorLabelPx", 9))
        return Math.max(14, Math.round(basePx))
    }
    readonly property int swipeablePageCount: hubPages ? hubPages.count : 0

    function stepSwipePage(delta) {
        if (!hubPages) return
        var next = hubPages.currentIndex + Math.round(delta)
        if (next < 0) next = 0
        if (next >= hubPages.count) next = hubPages.count - 1
        if (next !== hubPages.currentIndex) {
            hubPages.currentIndex = next
        }
    }

    Component.onCompleted: refreshDashboardSummary()
    onVisibleChanged: {
        if (visible) refreshDashboardSummary()
    }

    Timer {
        id: dashboardRefreshTimer
        interval: 60000
        repeat: true
        running: root.visible
        onTriggered: root.refreshDashboardSummary()
    }

    Rectangle {
        id: homeSceneFrame
        anchors.fill: parent
        radius: 0
        clip: true
        antialiasing: true
        color: "transparent"
        layer.enabled: false
        layer.smooth: true

        Item {
            id: backdropScene
            anchors.fill: parent

            Rectangle {
                anchors.fill: parent
                color: root.bgColor
            }

            Image {
                id: cityImage
                anchors.fill: parent
                source: root.themeBackgroundSource()
                fillMode: Image.PreserveAspectCrop
                smooth: true
                asynchronous: false
                retainWhileLoading: true
                cache: true
                mipmap: true
                opacity: root.lightTheme ? 0.50 : 0.72
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: root.lightTheme ? 0.02 : 0.06
                    blurMax: 44
                    saturation: root.lightTheme ? 0.12 : 0.30
                    brightness: root.lightTheme ? 0.05 : -0.02
                    colorizationColor: root.accentColor
                    colorization: root.backgroundColorizationStrength()
                }
            }

            Rectangle {
                anchors.fill: parent
                color: root.panelAlpha(root.lightTheme ? 0.16 : 0.12)
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.05, 0.11, root.lightTheme ? 0.08 : 0.20) }
                    GradientStop { position: 0.46; color: root.alphaAccent(root.lightTheme ? 0.08 : 0.16) }
                    GradientStop { position: 1.0; color: Qt.rgba(0.01, 0.03, 0.08, root.lightTheme ? 0.12 : 0.26) }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.ratioPx(root.scaleRatios.outerMarginPct, 12)
            spacing: root.ratioPx(root.scaleRatios.headerGapPct, 8)

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: root.ratioPx(0.006, 4)
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.currentGreeting()
                color: root.alphaText(0.998)
                font.pixelSize: root.greetingFontPx
                font.weight: Font.DemiBold
                layer.enabled: true
                layer.effect: DropShadow {
                    horizontalOffset: 0
                    verticalOffset: 1
                    radius: 4
                    samples: 9
                    color: root.alphaInk(0.50)
                    transparentBorder: true
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.dailySummary()
                color: root.alphaText(0.92)
                font.pixelSize: root.summaryFontPx
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                layer.enabled: true
                layer.effect: DropShadow {
                    horizontalOffset: 0
                    verticalOffset: 1
                    radius: 4
                    samples: 9
                    color: root.alphaInk(0.48)
                    transparentBorder: true
                }
            }

            Item {
                id: omniBar
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: root.ratioPx(root.scaleRatios.omniWidthPct, 320)
                Layout.preferredHeight: root.ratioPx(root.scaleRatios.omniHeightPct, 44)
                property real cornerRadius: root.ratioPx(root.scaleRatios.omniRadiusPct, 8)
                property int borderStrokePx: Math.max(1, root.ratioPx(root.scaleRatios.hubCardBorderPct, 1))
                property bool hovered: omniHover.hovered
                property color borderStrokeColor: root.readableInk(
                    root.panel2Color,
                    hovered ? (root.lightTheme ? 0.98 : 0.99) : (root.lightTheme ? 0.94 : 0.96)
                )
                Component.onCompleted: root.logSearchBarLayer("omniBar", omniBar, omniBar.cornerRadius, "borderPx=" + omniBar.borderStrokePx)
                onWidthChanged: root.logSearchBarLayer("omniBar", omniBar, omniBar.cornerRadius, "borderPx=" + omniBar.borderStrokePx)
                onHeightChanged: root.logSearchBarLayer("omniBar", omniBar, omniBar.cornerRadius, "borderPx=" + omniBar.borderStrokePx)

                DropShadow {
                    anchors.fill: omniShape
                    source: omniShape
                    horizontalOffset: 0
                    verticalOffset: root.ratioPx(0.0022, 1)
                    radius: root.ratioPx(0.040, 24)
                    samples: root.ratioPx(0.058, 34)
                    color: root.alphaAccent(omniBar.hovered ? 0.48 : 0.34)
                    transparentBorder: true
                }

                Rectangle {
                    id: omniShape
                    anchors.fill: parent
                    radius: omniBar.cornerRadius
                    color: "transparent"
                    clip: true
                    antialiasing: true
                    Component.onCompleted: root.logSearchBarLayer("omniShape", omniShape, omniBar.cornerRadius, "")
                    onWidthChanged: root.logSearchBarLayer("omniShape", omniShape, omniBar.cornerRadius, "")
                    onHeightChanged: root.logSearchBarLayer("omniShape", omniShape, omniBar.cornerRadius, "")

                    Rectangle {
                        id: omniFrame
                        anchors.fill: parent
                        radius: omniBar.cornerRadius
                        color: "transparent"
                        antialiasing: true
                        Component.onCompleted: root.logSearchBarLayer("omniFrame", omniFrame, omniFrame.radius, "")
                        onWidthChanged: root.logSearchBarLayer("omniFrame", omniFrame, omniFrame.radius, "")
                        onHeightChanged: root.logSearchBarLayer("omniFrame", omniFrame, omniFrame.radius, "")

                        Rectangle {
                            id: omniFill
                            anchors.fill: parent
                            anchors.margins: 0
                            radius: omniBar.cornerRadius
                            antialiasing: true
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: root.alphaAccent(omniBar.hovered ? 0.74 : 0.62) }
                                GradientStop { position: 0.58; color: root.alphaAccent(omniBar.hovered ? 0.56 : 0.46) }
                                GradientStop { position: 1.0; color: root.alphaAccent(omniBar.hovered ? 0.42 : 0.34) }
                            }
                            Component.onCompleted: root.logSearchBarLayer("omniFill", omniFill, omniFill.radius, "margins=" + omniFill.anchors.margins)
                            onWidthChanged: root.logSearchBarLayer("omniFill", omniFill, omniFill.radius, "margins=" + omniFill.anchors.margins)
                            onHeightChanged: root.logSearchBarLayer("omniFill", omniFill, omniFill.radius, "margins=" + omniFill.anchors.margins)
                        }
                    }

                    Rectangle {
                        id: omniGlass
                        anchors.fill: parent
                        anchors.margins: omniBar.borderStrokePx + Math.max(1, root.ratioPx(0.0014, 1))
                        radius: Math.max(1, omniBar.cornerRadius - anchors.margins)
                        clip: true
                        color: "transparent"
                        antialiasing: true
                        Component.onCompleted: root.logSearchBarLayer("omniGlass", omniGlass, omniGlass.radius, "margins=" + omniGlass.anchors.margins)
                        onWidthChanged: root.logSearchBarLayer("omniGlass", omniGlass, omniGlass.radius, "margins=" + omniGlass.anchors.margins)
                        onHeightChanged: root.logSearchBarLayer("omniGlass", omniGlass, omniGlass.radius, "margins=" + omniGlass.anchors.margins)

                        ShaderEffectSource {
                            id: omniBlurSource
                            anchors.fill: parent
                            sourceItem: backdropScene
                            sourceRect: root.sourceRectFor(omniGlass)
                            live: !(root.windowRef && (root.windowRef.userResizeInProgress || root.windowRef.userMoveInProgress))
                            hideSource: false
                            mipmap: true
                        }

                        MultiEffect {
                            anchors.fill: parent
                            source: omniBlurSource
                            blurEnabled: true
                            blur: 1.0
                            blurMax: 36
                            saturation: root.lightTheme ? 0.36 : 0.46
                            brightness: root.lightTheme ? 0.05 : -0.04
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: omniGlass.radius
                            antialiasing: true
                            color: SemanticTheme.alpha(root.panel2Color, 0.24)
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: omniGlass.radius
                            antialiasing: true
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: SemanticTheme.hoverOverlay(root.t, "Professional") }
                                GradientStop { position: 0.26; color: SemanticTheme.alpha(SemanticTheme.inkPrimary(root.t, "Professional"), 0.03) }
                                GradientStop { position: 0.64; color: "transparent" }
                                GradientStop { position: 1.0; color: SemanticTheme.overlayScrim(root.t, "Professional") }
                            }
                        }
                    }

                    Item {
                        anchors.fill: parent
                        anchors.leftMargin: root.ratioPx(0.012, 8)
                        anchors.rightMargin: root.ratioPx(0.010, 8)

                        Text {
                            id: omniIcon
                            text: "\uE721"
                            font.family: "Segoe MDL2 Assets"
                            renderType: Text.NativeRendering
                            color: root.alphaText(0.96)
                            font.pixelSize: Math.max(10, root.summaryFontPx)
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        TextField {
                            id: omniInput
                            anchors.left: omniIcon.right
                            anchors.leftMargin: root.ratioPx(0.009, 6)
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            placeholderText: "Search clients, matters, invoices, deadlines, and reports"
                            color: root.alphaText(0.95)
                            placeholderTextColor: root.alphaText(root.lightTheme ? 0.62 : 0.74)
                            font.pixelSize: {
                                var minPx = root.metricFloor("fontFloorLabelPx", 10)
                                // Use omni-bar width (not this field's width) to avoid self-referential font/layout loops.
                                var available = Math.max(160, omniBar.width - root.ratioPx(0.062, 44))
                                var adaptive = Math.round(available / 27)
                                return Math.max(minPx, Math.min(root.summaryFontPx + 4, adaptive))
                            }
                            background: Rectangle {
                                color: "transparent"
                                border.width: 0
                            }
                            onAccepted: {
                                var query = text ? String(text).trim() : ""
                                if (query.length > 0) {
                                    root.omniSearchRequested(query)
                                }
                            }
                        }
                    }
                }

                Shape {
                    id: omniBorderStroke
                    z: 3
                    anchors.fill: parent
                    antialiasing: true
                    property real strokeInset: Math.max(0.5, omniBar.borderStrokePx * 0.5)
                    property real strokeRadius: Math.max(1, omniBar.cornerRadius - strokeInset)
                    ShapePath {
                        strokeWidth: omniBar.borderStrokePx
                        strokeColor: omniBar.borderStrokeColor
                        fillColor: "transparent"
                        joinStyle: ShapePath.RoundJoin
                        PathRectangle {
                            x: omniBorderStroke.strokeInset
                            y: omniBorderStroke.strokeInset
                            width: Math.max(1, omniBorderStroke.width - (omniBorderStroke.strokeInset * 2))
                            height: Math.max(1, omniBorderStroke.height - (omniBorderStroke.strokeInset * 2))
                            radius: omniBorderStroke.strokeRadius
                        }
                    }
                    Component.onCompleted: root.logSearchBarLayer("omniBorder", omniBorderStroke, omniBorderStroke.strokeRadius, "stroke=" + omniBar.borderStrokePx)
                    onWidthChanged: root.logSearchBarLayer("omniBorder", omniBorderStroke, omniBorderStroke.strokeRadius, "stroke=" + omniBar.borderStrokePx)
                    onHeightChanged: root.logSearchBarLayer("omniBorder", omniBorderStroke, omniBorderStroke.strokeRadius, "stroke=" + omniBar.borderStrokePx)
                }

            HoverHandler {
                id: omniHover
                acceptedDevices: PointerDevice.Mouse
            }
        }

            Rectangle {
                id: hubPanel
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.ratioPx(root.scaleRatios.hubPanelRadiusPct, 12)
                color: "transparent"
                border.width: 0
                border.color: "transparent"
                clip: true

                Rectangle {
                    id: hubPanelSurface
                    anchors.fill: parent
                    radius: hubPanel.radius
                    color: SemanticTheme.alpha(root.panelColor, 0.15)
                    border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubPanelBorderPct, 1))
                    border.color: root.alphaAccent(root.lightTheme ? 0.40 : 0.56)
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: root.alphaAccent(root.lightTheme ? 0.34 : 0.50)
                        shadowBlur: 0.46
                        shadowVerticalOffset: root.ratioPx(0.0040, 2)
                        shadowHorizontalOffset: 0
                    }

                    // Swipe gestures should work anywhere in the framed area,
                    // including empty space below tiles.
                    DragHandler {
                        id: hubPanelSwipeDrag
                        target: null
                        acceptedButtons: Qt.LeftButton
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen | PointerDevice.TouchPad
                        grabPermissions: PointerHandler.CanTakeOverFromAnything | PointerHandler.ApprovesTakeOverByAnything
                        xAxis.enabled: true
                        yAxis.enabled: false
                        dragThreshold: root.ratioPx(0.008, 6)
                        enabled: hubPages && hubPages.count > 1
                        property bool swipeLatched: false
                        onActiveChanged: {
                            if (active) {
                                swipeLatched = false
                            }
                        }
                        onTranslationChanged: {
                            if (!active || swipeLatched) return
                            var dx = translation.x
                            var dy = translation.y
                            var minSwipePx = root.ratioPx(0.036, 24)
                            if (Math.abs(dx) < minSwipePx) return
                            if (Math.abs(dx) < (Math.abs(dy) * 1.16)) return
                            swipeLatched = true
                            root.stepSwipePage(dx > 0 ? -1 : 1)
                        }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: root.ratioPx(0.012, 8)
                    spacing: root.ratioPx(root.scaleRatios.hubGridGapPct, 8)

                SwipeView {
                    id: hubPages
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    interactive: false

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.ratioPx(root.scaleRatios.hubGridGapPct, 8)
                            spacing: root.ratioPx(root.scaleRatios.hubGridGapPct, 8)

                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredHeight: root.ratioPx(0.042, 28)
                            }

                            RowLayout {
                                id: hubCardRow
                                property real cardAspect: 1.08 // still portrait, allows larger card area
                                property int cardWidthPx: {
                                    var availableWidth = Math.max(1, (parent ? parent.width : root.width))
                                    var maxByWidth = Math.floor((availableWidth - (spacing * 3)) / 4)
                                    var idealWidth = root.ratioPx(0.345, 260)

                                    // Cap width by available vertical room to avoid clipping/cutoff.
                                    var availableHeight = Math.max(1, (parent ? parent.height : root.height))
                                    var verticalReserve = root.ratioPx(0.016, 10)
                                    var maxByHeight = Math.floor((availableHeight - verticalReserve) / cardAspect)
                                    var fitCap = Math.max(96, Math.min(maxByWidth, maxByHeight))
                                    var softMin = Math.max(96, Math.min(root.ratioPx(0.248, 188), fitCap))
                                    return Math.max(1, Math.round(Math.max(softMin, Math.min(idealWidth, fitCap))))
                                }
                                property int cardHeightPx: Math.max(1, Math.round(cardWidthPx * cardAspect))
                                Layout.fillWidth: false
                                Layout.preferredWidth: Math.max(1, Math.round((cardWidthPx * 4) + (spacing * 3)))
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredHeight: Math.max(1, Math.round(cardHeightPx))
                                Layout.minimumHeight: Math.max(1, Math.round(cardHeightPx))
                                Layout.maximumHeight: Math.max(1, Math.round(cardHeightPx))
                                // Keep a visible neutral gutter between tile halos.
                                spacing: root.ratioPx(0.030, 22)

                                Repeater {
                                    model: root.hubModel
                                    delegate: Item {
                                        id: hubTile
                                        required property var modelData
                                        required property int index
                                        Layout.fillWidth: false
                                        Layout.preferredWidth: hubCardRow.cardWidthPx
                                        Layout.preferredHeight: hubCardRow.cardHeightPx
                                        Layout.minimumHeight: hubCardRow.cardHeightPx
                                        Layout.maximumHeight: hubCardRow.cardHeightPx

                                        property bool hovered: tileHover.hovered
                                        property bool pressed: hubTap.pressed
                                        property real jellyXScale: pressed ? 1.110 : (hovered ? 1.085 : 1.0)
                                        property real jellyYScale: pressed ? 0.80 : (hovered ? 0.875 : 1.0)
                                        property real jellyTilt: hovered ? 0.55 : 0.0
                                        onHoveredChanged: {
                                            if (hovered) {
                                                root.playHoverSfx(0.30)
                                            }
                                        }

                                        transform: [
                                            Scale {
                                                origin.x: hubTile.width / 2
                                                origin.y: hubTile.height / 2
                                                xScale: hubTile.jellyXScale
                                                yScale: hubTile.jellyYScale
                                            },
                                            Rotation {
                                                origin.x: hubTile.width / 2
                                                origin.y: hubTile.height / 2
                                                axis { x: 0; y: 0; z: 1 }
                                                angle: hubTile.jellyTilt
                                            }
                                        ]

                                        Behavior on jellyXScale {
                                            NumberAnimation {
                                                duration: hubTile.pressed ? 95 : 185
                                                easing.type: hubTile.pressed ? Easing.OutCubic : Easing.OutBack
                                            }
                                        }
                                        Behavior on jellyYScale {
                                            NumberAnimation {
                                                duration: hubTile.pressed ? 95 : 185
                                                easing.type: hubTile.pressed ? Easing.OutCubic : Easing.OutBack
                                            }
                                        }
                                        Behavior on jellyTilt {
                                            NumberAnimation {
                                                duration: 150
                                                easing.type: Easing.InOutQuad
                                            }
                                        }

                                        property int tileW: Math.max(1, Math.round(width))
                                        property int tileH: Math.max(1, Math.round(height))
                                        property int cornerRadiusPx: Math.max(
                                            root.ratioPx(root.scaleRatios.hubCardRadiusPct * 1.25, 16),
                                            Math.round(Math.min(tileW, tileH) * 0.12)
                                        )
                                        property int borderStrokePx: Math.max(1, root.ratioPx(root.scaleRatios.hubCardBorderPct * 1.2, 1))
                                        property color borderStrokeColor: root.readableInk(
                                            root.panel2Color,
                                            hovered ? (root.lightTheme ? 0.98 : 0.99) : (root.lightTheme ? 0.94 : 0.96)
                                        )
                                        property int glassInsetPx: Math.max(borderStrokePx + 1, root.ratioPx(0.0022, 2))
                                        property int glassRadiusPx: Math.max(1, cornerRadiusPx - glassInsetPx)
                                        // Tight per-tile halo so neighboring cards do not visually merge.
                                        property int glowRadiusPx: root.ratioPx(0.016, 10)
                                        property int glowPadPx: Math.max(2, Math.ceil(glowRadiusPx * 0.40))
                                        property real glowSpreadVal: hovered ? 0.10 : 0.07
                                        property real glowAlphaVal: hovered ? 0.46 : 0.32
                                        property int titleFontPx: Math.max(
                                            9,
                                            Math.min(
                                                root.ratioPx(root.scaleRatios.hubTitlePct * 1.42, 12),
                                                Math.min(
                                                    Math.round(width * 0.132),
                                                    Math.round(tileH * 0.108)
                                                )
                                            )
                                        )
                                        property int subtitleFontPx: Math.max(
                                            7,
                                            Math.min(
                                                root.ratioPx(root.scaleRatios.hubSubtitlePct * 1.34, 10),
                                                Math.min(
                                                    Math.round(width * 0.083),
                                                    Math.round(tileH * 0.058)
                                                )
                                            )
                                        )
                                        property int detailFontPx: Math.max(
                                            6,
                                            Math.min(
                                                root.ratioPx(root.scaleRatios.hubSubtitlePct * 1.08, 8),
                                                Math.min(
                                                    Math.round(width * 0.074),
                                                    Math.round(tileH * 0.050)
                                                )
                                            )
                                        )
                                        property int contentMarginPx: Math.max(8, Math.min(root.ratioPx(0.021, 14), Math.round(tileH * 0.056)))
                                        property int contentSpacingPx: Math.max(4, Math.min(root.ratioPx(0.010, 7), Math.round(tileH * 0.030)))
                                        property int iconSizePx: Math.max(
                                            root.ratioPx(root.scaleRatios.hubIconPct * 1.05, 56),
                                            Math.min(Math.round(tileW * 0.42), Math.round(tileH * 0.34))
                                        )
                                        property int bottomPadPx: Math.max(6, Math.min(root.ratioPx(0.020, 12), Math.round(tileH * 0.052)))

                                        Rectangle {
                                            id: tileShape
                                            anchors.fill: parent
                                            radius: hubTile.cornerRadiusPx
                                            color: "transparent"
                                            antialiasing: true
                                            clip: false
                                            layer.enabled: true
                                            layer.smooth: true
                                            layer.effect: OpacityMask {
                                                maskSource: Rectangle {
                                                    width: tileShape.width
                                                    height: tileShape.height
                                                    radius: hubTile.cornerRadiusPx
                                                    color: SemanticTheme.textOnAccent(root.t, "Professional")
                                                }
                                            }

                                            Rectangle {
                                                id: hubFrame
                                                anchors.fill: parent
                                                radius: hubTile.cornerRadiusPx
                                                clip: true
                                                antialiasing: true
                                                border.width: 0
                                                gradient: Gradient {
                                                    GradientStop { position: 0.0; color: root.alphaAccent(hubTile.hovered ? 0.74 : 0.66) }
                                                    GradientStop { position: 0.34; color: root.alphaAccent(hubTile.hovered ? 0.60 : 0.52) }
                                                    GradientStop { position: 1.0; color: root.alphaAccent(hubTile.hovered ? 0.44 : 0.38) }
                                                }
                                            }

                                            Rectangle {
                                                id: hubGlass
                                                z: 2
                                                anchors.fill: parent
                                                anchors.margins: hubTile.glassInsetPx
                                                radius: hubTile.glassRadiusPx
                                                clip: true
                                                antialiasing: true
                                                color: "transparent"

                                                ShaderEffectSource {
                                                    id: hubBlurSource
                                                    anchors.fill: parent
                                                    sourceItem: backdropScene
                                                    sourceRect: root.sourceRectFor(hubGlass)
                                                    live: !(root.windowRef && (root.windowRef.userResizeInProgress || root.windowRef.userMoveInProgress))
                                                    hideSource: false
                                                    mipmap: true
                                                }

                                                MultiEffect {
                                                    anchors.fill: parent
                                                    source: hubBlurSource
                                                    blurEnabled: true
                                                    blur: 1.0
                                                    blurMax: 40
                                                    saturation: root.lightTheme ? 0.44 : 0.58
                                                    brightness: root.lightTheme ? 0.04 : -0.04
                                                }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    radius: hubGlass.radius
                                                    color: Qt.rgba(
                                                        root.panel2Color.r,
                                                        root.panel2Color.g,
                                                        root.panel2Color.b,
                                                        hubTile.hovered ? (root.lightTheme ? 0.34 : 0.64) : (root.lightTheme ? 0.29 : 0.56)
                                                    )
                                                }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    radius: hubGlass.radius
                                                    gradient: Gradient {
                                                        GradientStop { position: 0.0; color: SemanticTheme.alpha(SemanticTheme.inkPrimary(root.t, "Professional"), 0.03) }
                                                        GradientStop { position: 0.36; color: "transparent" }
                                                        GradientStop { position: 1.0; color: SemanticTheme.overlayScrim(root.t, "Professional") }
                                                    }
                                                }
                                            }

                                            Shape {
                                                id: hubBorderStroke
                                                z: 3
                                                anchors.fill: parent
                                                antialiasing: true
                                                property real strokeInset: Math.max(0.5, hubTile.borderStrokePx * 0.5)
                                                property real strokeRadius: Math.max(1, hubTile.cornerRadiusPx - strokeInset)
                                                ShapePath {
                                                    strokeWidth: hubTile.borderStrokePx
                                                    strokeColor: hubTile.borderStrokeColor
                                                    fillColor: "transparent"
                                                    joinStyle: ShapePath.RoundJoin
                                                    PathRectangle {
                                                        x: hubBorderStroke.strokeInset
                                                        y: hubBorderStroke.strokeInset
                                                        width: Math.max(1, hubBorderStroke.width - (hubBorderStroke.strokeInset * 2))
                                                        height: Math.max(1, hubBorderStroke.height - (hubBorderStroke.strokeInset * 2))
                                                        radius: hubBorderStroke.strokeRadius
                                                    }
                                                }
                                            }

                                            ColumnLayout {
                                                z: 4
                                                anchors.fill: parent
                                                anchors.margins: hubTile.contentMarginPx
                                                spacing: hubTile.contentSpacingPx

                                                Item {
                                                    Layout.alignment: Qt.AlignHCenter
                                                    Layout.preferredWidth: hubTile.iconSizePx
                                                    Layout.preferredHeight: hubTile.iconSizePx

                                                    Image {
                                                        id: hubIconSource
                                                        anchors.fill: parent
                                                        source: hubTile.modelData.iconSource
                                                        fillMode: Image.PreserveAspectFit
                                                        sourceSize.width: Math.max(1, Math.round(width * 2))
                                                        sourceSize.height: Math.max(1, Math.round(height * 2))
                                                        smooth: true
                                                        mipmap: true
                                                        visible: false
                                                    }

                                                    ColorOverlay {
                                                        id: hubIcon
                                                        anchors.fill: parent
                                                        source: hubIconSource
                                                        color: root.alphaText(hubTile.hovered ? 0.998 : 0.96)
                                                    }

                                                    Image {
                                                        id: hubIconFrameSource
                                                        anchors.fill: parent
                                                        source: (hubTile.modelData.iconFrameSource
                                                            && String(hubTile.modelData.iconFrameSource).length > 0)
                                                            ? hubTile.modelData.iconFrameSource : ""
                                                        fillMode: Image.PreserveAspectFit
                                                        sourceSize.width: Math.max(1, Math.round(width * 2))
                                                        sourceSize.height: Math.max(1, Math.round(height * 2))
                                                        smooth: true
                                                        mipmap: true
                                                        visible: false
                                                    }

                                                    ColorOverlay {
                                                        id: hubIconFrame
                                                        anchors.fill: parent
                                                        source: hubIconFrameSource
                                                        visible: hubIconFrameSource.source.toString().length > 0
                                                        color: Qt.rgba(
                                                            root.panel2Color.r,
                                                            root.panel2Color.g,
                                                            root.panel2Color.b,
                                                            hubTile.hovered ? (root.lightTheme ? 0.98 : 0.94)
                                                                            : (root.lightTheme ? 0.94 : 0.88)
                                                        )
                                                    }

                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: hubTile.modelData.title
                                                    color: root.alphaText(0.992)
                                                    horizontalAlignment: Text.AlignHCenter
                                                    wrapMode: Text.WordWrap
                                                    maximumLineCount: 2
                                                    font.pixelSize: hubTile.titleFontPx
                                                    fontSizeMode: Text.Fit
                                                    minimumPixelSize: 8
                                                    font.weight: Font.DemiBold
                                                    Layout.preferredHeight: Math.round(hubTile.titleFontPx * 2.65)
                                                    Layout.maximumHeight: Math.round(hubTile.titleFontPx * 2.65)
                                                    clip: false
                                                    layer.enabled: true
                                                    layer.effect: DropShadow {
                                                        horizontalOffset: 0
                                                        verticalOffset: 1
                                                        radius: 4
                                                        samples: 9
                                                        color: root.alphaInk(0.50)
                                                        transparentBorder: true
                                                    }
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: hubTile.modelData.subtitle
                                                    color: root.alphaText(0.91)
                                                    horizontalAlignment: Text.AlignHCenter
                                                    wrapMode: Text.WordWrap
                                                    maximumLineCount: 2
                                                    elide: Text.ElideNone
                                                    font.pixelSize: hubTile.subtitleFontPx
                                                    fontSizeMode: Text.Fit
                                                    minimumPixelSize: 7
                                                    font.weight: Font.Medium
                                                    Layout.preferredHeight: Math.round(hubTile.subtitleFontPx * 2.40)
                                                    Layout.maximumHeight: Math.round(hubTile.subtitleFontPx * 2.40)
                                                    clip: false
                                                    layer.enabled: true
                                                    layer.effect: DropShadow {
                                                        horizontalOffset: 0
                                                        verticalOffset: 1
                                                        radius: 3
                                                        samples: 7
                                                        color: root.alphaInk(0.44)
                                                        transparentBorder: true
                                                    }
                                                }

                                                Text {
                                                    visible: hubTile.modelData.detail && String(hubTile.modelData.detail).length > 0
                                                    Layout.fillWidth: true
                                                    text: hubTile.modelData.detail
                                                    color: root.alphaText(0.86)
                                                    horizontalAlignment: Text.AlignHCenter
                                                    wrapMode: Text.WordWrap
                                                    maximumLineCount: 2
                                                    elide: Text.ElideNone
                                                    font.pixelSize: hubTile.detailFontPx
                                                    fontSizeMode: Text.Fit
                                                    minimumPixelSize: 6
                                                    font.weight: Font.Medium
                                                    Layout.preferredHeight: visible ? Math.round(hubTile.detailFontPx * 2.20) : 0
                                                    Layout.maximumHeight: visible ? Math.round(hubTile.detailFontPx * 2.20) : 0
                                                    Layout.minimumHeight: 0
                                                    clip: false
                                                }

                                                Item {
                                                    Layout.minimumHeight: hubTile.bottomPadPx
                                                    Layout.preferredHeight: hubTile.bottomPadPx
                                                }

                                                Item { Layout.fillHeight: true }
                                            }
                                        }

                                        Rectangle {
                                            id: hubOuterStroke
                                            z: 4
                                            anchors.fill: parent
                                            radius: hubTile.cornerRadiusPx
                                            color: "transparent"
                                            antialiasing: true
                                            layer.enabled: true
                                            layer.smooth: true
                                            layer.samples: 4
                                            layer.effect: OpacityMask {
                                                maskSource: Rectangle {
                                                    width: hubOuterStroke.width
                                                    height: hubOuterStroke.height
                                                    radius: hubTile.cornerRadiusPx
                                                    color: SemanticTheme.textOnAccent(root.t, "Professional")
                                                }
                                            }
                                            border.width: hubTile.borderStrokePx
                                            border.color: hubTile.borderStrokeColor
                                        }

                                        RectangularGlow {
                                            anchors.fill: tileShape
                                            anchors.margins: -hubTile.glowPadPx
                                            z: -1
                                            glowRadius: hubTile.glowRadiusPx
                                            spread: hubTile.glowSpreadVal
                                            color: root.alphaAccent(hubTile.glowAlphaVal)
                                            cornerRadius: hubTile.cornerRadiusPx + Math.max(1, Math.ceil(hubTile.glowPadPx * 0.5))
                                            cached: true
                                        }

                                        HoverHandler {
                                            id: tileHover
                                            acceptedDevices: PointerDevice.Mouse
                                        }

                                        TapHandler {
                                            id: hubTap
                                            acceptedButtons: Qt.LeftButton
                                            gesturePolicy: TapHandler.DragThreshold
                                            onTapped: {
                                                if (root.sfxBus && root.sfxBus.playUiClick) {
                                                    root.sfxBus.playUiClick("tile", 0.46)
                                                }
                                                root.emitHub(hubTile.index, hubTile.modelData.moduleIndexes, hubTile)
                                            }
                                        }
                                    }
                                }
                            }

                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredHeight: root.ratioPx(0.042, 28)
                            }
                        }
                    }

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.ratioPx(root.scaleRatios.hubGridGapPct, 8)
                            spacing: root.ratioPx(root.scaleRatios.quickButtonGapPct, 6)

                            // ── Title row: label left, Edit icon right ────────
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: root.ratioPx(0.008, 6)

                                Text {
                                    Layout.fillWidth: true
                                    text: "Quick Actions"
                                    color: root.alphaText(0.97)
                                    font.pixelSize: root.ratioPx(root.scaleRatios.hubTitlePct * 1.06, root.metricFloor("fontFloorBodyPx", 11))
                                    renderType: Text.QtRendering
                                    font.hintingPreference: Font.PreferFullHinting
                                    layer.enabled: true
                                    layer.smooth: false
                                    font.weight: Font.DemiBold
                                }

                                // Edit Quick Actions — future customization placeholder
                                Rectangle {
                                    id: editQuickActionsBtn
                                    width: root.ratioPx(0.030, 28)
                                    height: width
                                    radius: width / 2
                                    property bool hovered: editQAHover.hovered
                                    property bool pressed: editQATap.pressed
                                    color: hovered
                                        ? SemanticTheme.hoverOverlay(root.t, "Professional")
                                        : "transparent"
                                    border.width: 1
                                    border.color: hovered ? root.alphaAccent(0.70) : root.alphaText(0.22)
                                    Layout.alignment: Qt.AlignVCenter

                                    Text {
                                        anchors.centerIn: parent
                                        // Pencil icon — Segoe MDL2 Assets U+E70F
                                        text: "\uE70F"
                                        font.family: "Segoe MDL2 Assets"
                                        color: root.alphaText(editQuickActionsBtn.hovered ? 0.90 : 0.40)
                                        font.pixelSize: Math.round(editQuickActionsBtn.width * 0.50)
                                        renderType: Text.NativeRendering
                                    }

                                    HoverHandler {
                                        id: editQAHover
                                        acceptedDevices: PointerDevice.Mouse
                                        onHoveredChanged: {
                                            if (hovered && root.sfxBus && root.sfxBus.playUiClick) {
                                                root.sfxBus.playUiClick("hover", 0.16)
                                            }
                                        }
                                    }
                                    TapHandler {
                                        id: editQATap
                                        acceptedButtons: Qt.LeftButton
                                        gesturePolicy: TapHandler.DragThreshold
                                        onTapped: {
                                            // Placeholder — Quick Actions customization is a future phase feature.
                                            if (root.sfxBus && root.sfxBus.playUiClick) {
                                                root.sfxBus.playUiClick("affirm", 0.26)
                                            }
                                        }
                                    }

                                    ToolTip {
                                        id: quickActionsTip
                                        visible: editQuickActionsBtn.hovered
                                        padding: root.ratioPx(0.008, 8)
                                        property color inkColor: SemanticTheme.ink(root.t, "tooltip", "neutral")
                                        // Right-align tooltip to button so it extends leftward,
                                        // keeping it fully within the window.
                                        x: -(implicitWidth - parent.width)
                                        y: parent.height + 4
                                        text: "Quick Actions Editor"
                                        delay: 600
                                        timeout: 3000
                                        background: SemanticPanel {
                                            t: root.t
                                            role: "tooltip"
                                            tone: "neutral"
                                            radius: root.ratioPx(0.010, 8)
                                            borderWidth: 1
                                        }
                                        contentItem: Text {
                                            text: quickActionsTip.text
                                            color: quickActionsTip.inkColor
                                            font.pixelSize: root.ratioPx(root.scaleRatios.hubSubtitlePct * 0.94, root.metricFloor("fontFloorLabelPx", 8))
                                            font.weight: Font.Medium
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Direct open links into pathway windows."
                                color: root.alphaText(0.84)
                                font.pixelSize: root.ratioPx(root.scaleRatios.hubSubtitlePct * 1.05, root.metricFloor("fontFloorLabelPx", 9))
                                renderType: Text.QtRendering
                                font.hintingPreference: Font.PreferFullHinting
                                layer.enabled: true
                                layer.smooth: false
                                font.weight: Font.Medium
                            }

                            // ── Scrollable 3-column button grid ─────────────
                            ScrollView {
                                id: quickActionsScroll
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                                Flow {
                                    // availableWidth is ScrollView's viewport width minus any
                                    // scrollbar. This is reliably defined, unlike parent.width
                                    // inside a Flickable which resolves to 0 during layout.
                                    width: quickActionsScroll.availableWidth
                                    spacing: root.ratioPx(root.scaleRatios.quickButtonGapPct, 8)

                                Repeater {
                                    model: root.quickActionModel
                                    delegate: Rectangle {
                                        id: quickTile
                                        required property var modelData
                                        property bool hovered: quickHover.hovered
                                        property bool pressed: quickTap.pressed
                                        property real jellyXScale: pressed ? 1.02 : (hovered ? 1.012 : 1.0)
                                        property real jellyYScale: pressed ? 0.94 : (hovered ? 0.985 : 1.0)
                                        // 3 equal columns: (viewportWidth - 2 gaps) / 3
                                        width: Math.max(60, Math.floor(
                                            (quickActionsScroll.availableWidth - root.ratioPx(root.scaleRatios.quickButtonGapPct, 8) * 2) / 3
                                        ))
                                        height: root.ratioPx(root.scaleRatios.quickButtonHeightPct, 46)
                                        radius: height / 2
                                        property color fillColor: quickTile.hovered
                                            ? SemanticTheme.alpha(root.accentColor, 0.5)
                                            : SemanticTheme.alpha(root.panel2Color, 0.9)
                                        color: quickTile.hovered
                                            ? SemanticTheme.alpha(root.accentColor, 0.5)
                                            : SemanticTheme.alpha(root.panel2Color, 0.9)
                                        border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubCardBorderPct, 1))
                                        border.color: quickTile.hovered
                                            ? root.alphaAccent(root.lightTheme ? 0.94 : 0.82)
                                            : root.alphaText(root.lightTheme ? 0.44 : 0.36)
                                        onHoveredChanged: {
                                            if (hovered) {
                                                root.playHoverSfx(0.28)
                                            }
                                        }
                                        transform: Scale {
                                            origin.x: quickTile.width / 2
                                            origin.y: quickTile.height / 2
                                            xScale: quickTile.jellyXScale
                                            yScale: quickTile.jellyYScale
                                        }
                                        Behavior on jellyXScale {
                                            NumberAnimation {
                                                duration: quickTile.pressed ? 95 : 165
                                                easing.type: quickTile.pressed ? Easing.OutCubic : Easing.OutBack
                                            }
                                        }
                                        Behavior on jellyYScale {
                                            NumberAnimation {
                                                duration: quickTile.pressed ? 95 : 165
                                                easing.type: quickTile.pressed ? Easing.OutCubic : Easing.OutBack
                                            }
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: root.ratioPx(0.012, 8)
                                            anchors.rightMargin: root.ratioPx(0.012, 8)
                                            spacing: root.ratioPx(0.006, 5)

                                            Text {
                                                text: quickTile.modelData.icon
                                                font.family: "Segoe MDL2 Assets"
                                                color: root.readableInk(quickTile.fillColor, 0.96)
                                                font.pixelSize: root.ratioPx(0.0175, 13)
                                                renderType: Text.NativeRendering
                                                Layout.alignment: Qt.AlignVCenter
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: quickTile.modelData.title
                                                color: root.readableInk(quickTile.fillColor, 0.98)
                                                font.pixelSize: root.ratioPx(0.0170, 11)
                                                minimumPixelSize: root.metricFloor("fontFloorLabelPx", 9)
                                                fontSizeMode: Text.Fit
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                                renderType: Text.QtRendering
                                                Layout.alignment: Qt.AlignVCenter
                                            }
                                        }

                                        HoverHandler {
                                            id: quickHover
                                            acceptedDevices: PointerDevice.Mouse
                                        }

                                        TapHandler {
                                            id: quickTap
                                            acceptedButtons: Qt.LeftButton
                                            gesturePolicy: TapHandler.DragThreshold
                                            onTapped: {
                                                if (root.sfxBus && root.sfxBus.playUiClick) {
                                                    root.sfxBus.playUiClick("affirm", 0.40)
                                                }
                                                var commandQuery = quickTile.modelData.query ? String(quickTile.modelData.query).trim() : ""
                                                if (commandQuery.length > 0) {
                                                    root.omniSearchRequested(commandQuery)
                                                } else {
                                                    root.emitTile(quickTile.modelData.tileIndex, quickTile)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            } // ScrollView
                        }
                    }

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: root.ratioPx(root.scaleRatios.hubGridGapPct, 8)
                            spacing: root.ratioPx(root.scaleRatios.quickButtonGapPct, 6)

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: root.ratioPx(root.scaleRatios.hubCardRadiusPct, 10)
                                color: root.panelAlpha(0.34)
                                border.width: root.ratioPx(root.scaleRatios.hubPanelBorderPct, 1)
                                border.color: root.alphaText(0.20)

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: root.ratioPx(0.020, 12)
                                    spacing: root.ratioPx(0.010, 6)

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Pipeline Modules"
                                        color: root.alphaText(0.96)
                                        font.pixelSize: root.ratioPx(root.scaleRatios.hubTitlePct, root.metricFloor("fontFloorBodyPx", 10))
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Regulatory docket intelligence and document operations are staged for upcoming phases."
                                        color: root.alphaText(0.82)
                                        wrapMode: Text.WordWrap
                                        horizontalAlignment: Text.AlignHCenter
                                        font.pixelSize: root.ratioPx(root.scaleRatios.summaryFontPct, root.metricFloor("fontFloorLabelPx", 9))
                                    }

                                    Item { Layout.fillHeight: true }

                                    RowLayout {
                                        Layout.alignment: Qt.AlignHCenter
                                        spacing: root.ratioPx(root.scaleRatios.quickButtonGapPct, 12)

                                        Rectangle {
                                            id: openDeadlinesBtn
                                            Layout.preferredWidth: root.ratioPx(0.155, 128)
                                            Layout.preferredHeight: root.ratioPx(root.scaleRatios.quickButtonHeightPct, 46)
                                            property bool hovered: deadlinesHover.hovered
                                            property bool pressed: deadlinesTap.pressed
                                            property real jellyXScale: pressed ? 1.02 : (hovered ? 1.012 : 1.0)
                                            property real jellyYScale: pressed ? 0.94 : (hovered ? 0.985 : 1.0)
                                            radius: height / 2
                                            color: hovered
                                                ? SemanticTheme.alpha(root.accentColor, 0.5)
                                                : SemanticTheme.alpha(root.panel2Color, 0.9)
                                            border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubCardBorderPct, 1))
                                            border.color: hovered ? root.alphaAccent(0.90) : root.alphaText(root.lightTheme ? 0.44 : 0.36)
                                            onHoveredChanged: {
                                                if (hovered) {
                                                    root.playHoverSfx(0.24)
                                                }
                                            }
                                            transform: Scale {
                                                origin.x: openDeadlinesBtn.width / 2
                                                origin.y: openDeadlinesBtn.height / 2
                                                xScale: openDeadlinesBtn.jellyXScale
                                                yScale: openDeadlinesBtn.jellyYScale
                                            }
                                            Behavior on jellyXScale {
                                                NumberAnimation {
                                                    duration: openDeadlinesBtn.pressed ? 95 : 160
                                                    easing.type: openDeadlinesBtn.pressed ? Easing.OutCubic : Easing.OutBack
                                                }
                                            }
                                            Behavior on jellyYScale {
                                                NumberAnimation {
                                                    duration: openDeadlinesBtn.pressed ? 95 : 160
                                                    easing.type: openDeadlinesBtn.pressed ? Easing.OutCubic : Easing.OutBack
                                                }
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "Open Deadlines"
                                                color: root.readableInk(openDeadlinesBtn.color, 0.98)
                                                font.pixelSize: root.ratioPx(0.0188, 12)
                                                minimumPixelSize: root.metricFloor("fontFloorLabelPx", 9)
                                                fontSizeMode: Text.Fit
                                                renderType: Text.QtRendering
                                                font.weight: Font.DemiBold
                                            }

                                            HoverHandler {
                                                id: deadlinesHover
                                                acceptedDevices: PointerDevice.Mouse
                                            }

                                            TapHandler {
                                                id: deadlinesTap
                                                acceptedButtons: Qt.LeftButton
                                                gesturePolicy: TapHandler.DragThreshold
                                                onTapped: {
                                                    if (root.sfxBus && root.sfxBus.playUiClick) {
                                                        root.sfxBus.playUiClick("affirm", 0.38)
                                                    }
                                                    root.omniSearchRequested("deadline master calendar")
                                                }
                                            }
                                        }

                                        Rectangle {
                                            id: openReportsBtn
                                            Layout.preferredWidth: root.ratioPx(0.170, 138)
                                            Layout.preferredHeight: root.ratioPx(root.scaleRatios.quickButtonHeightPct, 46)
                                            property bool hovered: reportsHover.hovered
                                            property bool pressed: reportsTap.pressed
                                            property real jellyXScale: pressed ? 1.02 : (hovered ? 1.012 : 1.0)
                                            property real jellyYScale: pressed ? 0.94 : (hovered ? 0.985 : 1.0)
                                            radius: height / 2
                                            color: hovered
                                                ? SemanticTheme.alpha(root.accentColor, 0.5)
                                                : SemanticTheme.alpha(root.panel2Color, 0.9)
                                            border.width: Math.max(1, root.ratioPx(root.scaleRatios.hubCardBorderPct, 1))
                                            border.color: hovered ? root.alphaAccent(0.90) : root.alphaText(root.lightTheme ? 0.44 : 0.36)
                                            onHoveredChanged: {
                                                if (hovered) {
                                                    root.playHoverSfx(0.24)
                                                }
                                            }
                                            transform: Scale {
                                                origin.x: openReportsBtn.width / 2
                                                origin.y: openReportsBtn.height / 2
                                                xScale: openReportsBtn.jellyXScale
                                                yScale: openReportsBtn.jellyYScale
                                            }
                                            Behavior on jellyXScale {
                                                NumberAnimation {
                                                    duration: openReportsBtn.pressed ? 95 : 160
                                                    easing.type: openReportsBtn.pressed ? Easing.OutCubic : Easing.OutBack
                                                }
                                            }
                                            Behavior on jellyYScale {
                                                NumberAnimation {
                                                    duration: openReportsBtn.pressed ? 95 : 160
                                                    easing.type: openReportsBtn.pressed ? Easing.OutCubic : Easing.OutBack
                                                }
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "Open Reports"
                                                color: root.readableInk(openReportsBtn.color, 0.98)
                                                font.pixelSize: root.ratioPx(0.0188, 12)
                                                minimumPixelSize: root.metricFloor("fontFloorLabelPx", 9)
                                                fontSizeMode: Text.Fit
                                                renderType: Text.QtRendering
                                                font.weight: Font.DemiBold
                                            }

                                            HoverHandler {
                                                id: reportsHover
                                                acceptedDevices: PointerDevice.Mouse
                                            }

                                            TapHandler {
                                                id: reportsTap
                                                acceptedButtons: Qt.LeftButton
                                                gesturePolicy: TapHandler.DragThreshold
                                                onTapped: {
                                                    if (root.sfxBus && root.sfxBus.playUiClick) {
                                                        root.sfxBus.playUiClick("affirm", 0.38)
                                                    }
                                                    root.omniSearchRequested("executive dashboard")
                                                }
                                            }
                                        }
                                    }

                                    Item { Layout.fillHeight: true }
                                }
                            }
                        }
                    }

                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignRight
                    spacing: root.ratioPx(0.007, 5)

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        Layout.preferredWidth: root.ratioPx(0.022, 18)
                        Layout.preferredHeight: width
                        radius: width / 2
                        color: SemanticTheme.borderSubtle(root.t, "Professional")
                        border.width: 1
                        border.color: SemanticTheme.borderStrong(root.t, "Professional")
                        visible: hubPages.currentIndex > 0
                        opacity: visible ? 1.0 : 0.0

                        Text {
                            anchors.centerIn: parent
                            text: "\u2039"
                            color: root.alphaText(0.95)
                            font.pixelSize: root.ratioPx(0.016, 10)
                            font.weight: Font.Bold
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.stepSwipePage(-1)
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: root.ratioPx(0.022, 18)
                        Layout.preferredHeight: width
                        radius: width / 2
                        color: SemanticTheme.borderSubtle(root.t, "Professional")
                        border.width: 1
                        border.color: SemanticTheme.borderStrong(root.t, "Professional")
                        visible: hubPages.currentIndex < (hubPages.count - 1)
                        opacity: visible ? 1.0 : 0.0

                        Text {
                            anchors.centerIn: parent
                            text: "\u203A"
                            color: root.alphaText(0.95)
                            font.pixelSize: root.ratioPx(0.016, 10)
                            font.weight: Font.Bold
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.stepSwipePage(1)
                        }
                    }
                }

                PageIndicator {
                    id: pageIndicator
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: root.ratioPx(0.008, 6)
                    count: root.swipeablePageCount
                    currentIndex: hubPages.currentIndex
                    interactive: true
                    onCurrentIndexChanged: {
                        if (hubPages.currentIndex !== currentIndex) {
                            hubPages.currentIndex = currentIndex
                        }
                    }
                    delegate: Rectangle {
                        implicitWidth: root.ratioPx(0.010, 8)
                        implicitHeight: implicitWidth
                        radius: width / 2
                        color: index === pageIndicator.currentIndex ? root.alphaAccent(0.96) : root.alphaText(0.36)
                    }
                }
            }
        }
    }

    }

}
