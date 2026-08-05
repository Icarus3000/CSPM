pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: cal
    screen: (_resolvedHostWindow() && _resolvedHostWindow().screen) ? _resolvedHostWindow().screen : null
    title: "CSPM-JellyCalendar"
    objectName: "CSPMJellyCalendar"
    
    // Standalone tool window
    flags: Qt.Dialog | Qt.FramelessWindowHint
    modality: Qt.ApplicationModal
    color: "transparent"
    
    property var metrics: null
    property var scaleRatios: ({
        "windowWidthPct": 0.304,
        "windowHeightPct": 0.606,
        "windowMinWidthPct": 0.217,
        "windowMinHeightPct": 0.348,
        "innerWidthPct": 0.904,
        "innerHeightPct": 0.914,
        "panelCornerPct": 0.048,
        "panelBorderPct": 0.0034,
        "panelShadowPct": 0.048,
        "panelShadowSamplesPct": 0.097,
        "panelMarginPct": 0.038,
        "panelSpacingPct": 0.021,
        "titleBarHeightPct": 0.087,
        "titleBarCornerPct": 0.021,
        "titleBarBorderPct": 0.0017,
        "titleInsetPct": 0.021,
        "titleSpacingPct": 0.017,
        "titleButtonWidthPct": 0.076,
        "titleButtonHeightPct": 0.062,
        "titleButtonFontPct": 0.038,
        "titleTextPct": 0.041,
        "closeTextPct": 0.048,
        "dowTextPct": 0.034,
        "gridSpacingPct": 0.010,
        "dayCellSizePct": 0.120,
        "dayTextPct": 0.041,
        "todayBorderPct": 0.0034,
        "flashInsetPct": 0.021,
        "flashBorderPct": 0.0034,
        "fontFloorTitlePct": 0.026,
        "fontFloorBodyPct": 0.022,
        "fontFloorLabelPct": 0.019,
        "fontFloorIconPct": 0.022
    })
    function screenW() {
        if (cal.screen && typeof cal.screen.width === "number" && cal.screen.width > 0) return cal.screen.width
        return Math.max(1, Screen.width)
    }
    function screenH() {
        if (cal.screen && typeof cal.screen.height === "number" && cal.screen.height > 0) return cal.screen.height
        return Math.max(1, Screen.height)
    }
    function windowUnit() {
        return Math.min(Math.max(1, cal.width), Math.max(1, cal.height))
    }
    function ratioScreenW(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(screenW() * ratio))
    }
    function ratioScreenH(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(screenH() * ratio))
    }
    function ratioWindow(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(windowUnit() * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    function metricFloorRatio(metricKey, fallbackRatio) {
        return metricFloor(metricKey, ratioWindow(fallbackRatio, 1))
    }

    width: Math.max(
        ratioScreenW(scaleRatios.windowMinWidthPct, 1),
        ratioScreenW(scaleRatios.windowWidthPct, 1)
    )
    height: Math.max(
        ratioScreenH(scaleRatios.windowMinHeightPct, 1),
        ratioScreenH(scaleRatios.windowHeightPct, 1)
    )
    visible: false

    property var t
    property var hostWindow: null
    property bool isExitClosing: false

    property date selectedDate: new Date()
    property date pendingDate: selectedDate
    property int minSelectableYear: (new Date().getFullYear() - 100)
    property int maxSelectableYear: (new Date().getFullYear() + 25)
    property var monthNames: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    signal datePicked(date d)

    function _allScreens() {
        if (Qt.application && Qt.application.screens && Qt.application.screens.length > 0) {
            return Qt.application.screens
        }
        return []
    }

    function _resolvedHostWindow() {
        if (!hostWindow) return null
        if (hostWindow.screen) return hostWindow
        if (hostWindow.Window && hostWindow.Window.window) return hostWindow.Window.window
        if (hostWindow.window && hostWindow.window.screen) return hostWindow.window
        return null
    }

    function _screenRect(screenObj) {
        if (screenObj && screenObj.availableGeometry
            && typeof screenObj.availableGeometry.x === "number"
            && typeof screenObj.availableGeometry.y === "number"
            && typeof screenObj.availableGeometry.width === "number"
            && typeof screenObj.availableGeometry.height === "number") {
            return {
                "x": Math.round(screenObj.availableGeometry.x),
                "y": Math.round(screenObj.availableGeometry.y),
                "w": Math.max(1, Math.round(screenObj.availableGeometry.width)),
                "h": Math.max(1, Math.round(screenObj.availableGeometry.height))
            }
        }
        return {
            "x": screenObj && typeof screenObj.virtualX === "number" ? Math.round(screenObj.virtualX) : 0,
            "y": screenObj && typeof screenObj.virtualY === "number" ? Math.round(screenObj.virtualY) : 0,
            "w": screenObj && typeof screenObj.width === "number" ? Math.max(1, Math.round(screenObj.width)) : Math.max(1, Screen.width),
            "h": screenObj && typeof screenObj.height === "number" ? Math.max(1, Math.round(screenObj.height)) : Math.max(1, Screen.height)
        }
    }

    function _screenContainsPoint(screenObj, px, py) {
        var rect = _screenRect(screenObj)
        return px >= rect.x && px < (rect.x + rect.w) && py >= rect.y && py < (rect.y + rect.h)
    }

    function _screenForPoint(px, py) {
        var screens = _allScreens()
        for (var i = 0; i < screens.length; i++) {
            if (_screenContainsPoint(screens[i], px, py)) return screens[i]
        }
        return null
    }
    function _preferredScreen(px, py) {
        // An explicit opening point always wins. AP supplies the global centre of
        // the date field that received the double-click.
        if (px !== undefined && py !== undefined && px !== -1 && py !== -1) {
            var byPoint = _screenForPoint(px, py)
            if (byPoint) return byPoint
        }

        var owner = _resolvedHostWindow()
        if (owner && typeof owner.x === "number" && typeof owner.y === "number" && owner.width > 0 && owner.height > 0) {
            var cx = Math.round(owner.x + (owner.width / 2))
            var cy = Math.round(owner.y + (owner.height / 2))
            var screenByOwnerCenter = _screenForPoint(cx, cy)
            if (screenByOwnerCenter) return screenByOwnerCenter
        }
        if (owner && owner.screen) return owner.screen

        var screens = _allScreens()
        if (screens.length > 0) return screens[0]
        return null
    }

    // Standard open (centers on primary screen)
    function open() {
        openAt(-1, -1)
    }

    // Open anchored to the initiating app window's monitor.
    function openAt(px, py) {
        var realHost = _resolvedHostWindow()
        if (realHost) {
            transientParent = realHost
            if (realHost.screen) screen = realHost.screen
        }

        pendingDate = selectedDate
        grid.month = pendingDate.getMonth()
        grid.year = pendingDate.getFullYear()
        var hasPoint = (px !== undefined && py !== undefined && px !== -1 && py !== -1)
        var targetScreen = _preferredScreen(px, py)
        if (targetScreen) {
            cal.screen = targetScreen
        }

        // Compute expected popup size from the target screen directly, because
        // the width/height bindings (which call ratioScreenW / ratioScreenH)
        // may not have re-evaluated yet after the screen assignment above.
        var tgtScrW = (targetScreen && typeof targetScreen.width === "number" && targetScreen.width > 0) ? targetScreen.width : Math.max(1, Screen.width)
        var tgtScrH = (targetScreen && typeof targetScreen.height === "number" && targetScreen.height > 0) ? targetScreen.height : Math.max(1, Screen.height)
        var popupW = Math.max(
            Math.max(1, Math.round(tgtScrW * scaleRatios.windowMinWidthPct)),
            Math.max(1, Math.round(tgtScrW * scaleRatios.windowWidthPct))
        )
        var popupH = Math.max(
            Math.max(1, Math.round(tgtScrH * scaleRatios.windowMinHeightPct)),
            Math.max(1, Math.round(tgtScrH * scaleRatios.windowHeightPct))
        )
        // Force the window to these dimensions immediately so sizing and
        // positioning are coherent.
        cal.width = popupW
        cal.height = popupH

        var rect = _screenRect(targetScreen)
        // Centre over the *screen* geometry (matching the working
        // SearchSelector.recenterWindow pattern).  Using the host Window's
        // frame coordinates is unreliable on Windows because maximised
        // windows report negative x/y and inflated width/height due to
        // invisible resize borders.
        var scrHost = {
            x: cal.screen ? cal.screen.virtualX : rect.x,
            y: cal.screen ? cal.screen.virtualY : rect.y,
            width: cal.screen ? cal.screen.width : rect.w,
            height: cal.screen ? cal.screen.height : rect.h
        }
        var destX = Math.round(scrHost.x + ((scrHost.width  - popupW) / 2.0))
        var destY = Math.round(scrHost.y + ((scrHost.height - popupH) / 2.0))

        var maxX = Math.max(rect.x, rect.x + rect.w - popupW)
        var maxY = Math.max(rect.y, rect.y + rect.h - popupH)
        cal.x = Math.min(Math.max(destX, rect.x), maxX)
        cal.y = Math.min(Math.max(destY, rect.y), maxY)
        if (!hasPoint && !targetScreen) {
            centerWindow()
        }

        cal.visible = true
        cal.show()
        cal.requestActivate()
        
        Qt.callLater(function() {
            // Re-centre using screen geometry to guarantee correct placement.
            var liveScrHost = {
                x: cal.screen ? cal.screen.virtualX : 0,
                y: cal.screen ? cal.screen.virtualY : 0,
                width: cal.screen ? cal.screen.width : 1920,
                height: cal.screen ? cal.screen.height : 1080
            }
            var liveDestX = Math.round(liveScrHost.x + ((liveScrHost.width  - popupW) / 2.0))
            var liveDestY = Math.round(liveScrHost.y + ((liveScrHost.height - popupH) / 2.0))
            var liveRect = _screenRect(targetScreen)
            var liveMaxX = Math.max(liveRect.x, liveRect.x + liveRect.w - popupW)
            var liveMaxY = Math.max(liveRect.y, liveRect.y + liveRect.h - popupH)
            cal.x = Math.min(Math.max(liveDestX, liveRect.x), liveMaxX)
            cal.y = Math.min(Math.max(liveDestY, liveRect.y), liveMaxY)
            cal.raise()
            cal.requestActivate()
        })
    }

    function shiftDisplayedMonth(deltaMonths) {
        var base = new Date(grid.year, grid.month, 1)
        var shifted = new Date(base.getFullYear(), base.getMonth() + Number(deltaMonths || 0), 1)
        grid.month = shifted.getMonth()
        grid.year = shifted.getFullYear()
    }

    function jumpToToday() {
        var now = new Date()
        grid.month = now.getMonth()
        grid.year = now.getFullYear()
        cal.pendingDate = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        cal.pulseSelection()
    }

    function refreshYearBounds() {
        var currentYear = (new Date()).getFullYear()
        minSelectableYear = currentYear - 100
        maxSelectableYear = currentYear + 25
    }

    function openMonthPicker() {
        if (yearPickerPopup.visible) yearPickerPopup.close()
        monthPickerPopup.open()
    }

    function openYearPicker() {
        if (monthPickerPopup.visible) monthPickerPopup.close()
        refreshYearBounds()
        yearPickerPopup.open()
        Qt.callLater(function() {
            if (yearList.count <= 0) return
            var idx = Math.max(0, Math.min(yearList.count - 1, grid.year - minSelectableYear))
            yearList.currentIndex = idx
            yearList.positionViewAtIndex(idx, ListView.Center)
        })
    }
    
    function geometryAudit(tag) {
        var host = _resolvedHostWindow()
        var hostScreen = host && host.screen ? host.screen : null
        var calScreen = cal.screen ? cal.screen : null
        var globalCenter = null
        try {
            if (host && host.contentItem && host.contentItem.mapToGlobal) {
                globalCenter = host.contentItem.mapToGlobal(Qt.point(Math.round(host.contentItem.width / 2), Math.round(host.contentItem.height / 2)))
            }
        } catch (auditError) {
            globalCenter = null
        }
        console.log(
            "[APGEOM][CAL]", tag,
            "host=", host ? [host.x, host.y, host.width, host.height].join(",") : "null",
            "content=", host && host.contentItem ? [host.contentItem.width, host.contentItem.height].join(",") : "null",
            "globalCenter=", globalCenter ? [globalCenter.x, globalCenter.y].join(",") : "null",
            "hostScreen=", hostScreen ? [hostScreen.name, hostScreen.geometry.x, hostScreen.geometry.y, hostScreen.geometry.width, hostScreen.geometry.height, hostScreen.devicePixelRatio].join(",") : "null",
            "calScreen=", calScreen ? [calScreen.name, calScreen.geometry.x, calScreen.geometry.y, calScreen.geometry.width, calScreen.geometry.height, calScreen.devicePixelRatio].join(",") : "null",
            "calendar=", [cal.x, cal.y, cal.width, cal.height, cal.visible].join(","),
            "transientMatches=", host ? (cal.transientParent === host) : false
        )
    }

    function openCenteredInHost() {
        var realHost = _resolvedHostWindow()
        if (realHost) {
            transientParent = realHost
        }
        var popupScreen = _preferredScreen(-1, -1)
        if (popupScreen) {
            cal.screen = popupScreen
        }
        var host = popupScreen ? {
            x: popupScreen.virtualX,
            y: popupScreen.virtualY,
            width: popupScreen.width,
            height: popupScreen.height
        } : null
        if (host) {
            if (!cal.width || cal.width < 50) cal.width = 340
            if (!cal.height || cal.height < 50) cal.height = 380
            cal.x = Math.round(host.x + ((host.width - cal.width) / 2))
            cal.y = Math.round(host.y + ((host.height - cal.height) / 2))
        }
visible = true
        show()
        requestActivate()
        Qt.callLater(function() {
            if (host) {
                if (!cal.width || cal.width < 50) cal.width = 340
                if (!cal.height || cal.height < 50) cal.height = 380
                cal.x = Math.round(host.x + ((host.width - cal.width) / 2))
                cal.y = Math.round(host.y + ((host.height - cal.height) / 2))
            }
            cal.raise()
            cal.requestActivate()
            win.forceActiveFocus()
        })
    }





    Shortcut {
        sequences: ["Esc"]
        context: Qt.ApplicationShortcut
        enabled: cal.visible
        onActivated: {
            console.log("[APESC][CAL] Esc activated")
            cal.pendingDate = cal.selectedDate
            cal.hideCalendar()
        }
    }

    function hideCalendar() {
        cal.hide()
    }

    function acceptDateAndClose(dateValue) {
        var picked = new Date(dateValue.getTime())
        selectedDate = picked
        hideCalendar()
        datePicked(picked)
    }

    function closeForAppExit() {
        if (isExitClosing) return
        isExitClosing = true
        cal.visible = false
        cal.close()
        Qt.callLater(function() {
            cal.destroy()
        })
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            cal.closeForAppExit()
        }
    }

    onClosing: function(close) {
        if (isExitClosing) {
            close.accepted = true
            return
        }
        close.accepted = false
        cal.hide()
    }

    property color accentColor: (t && t.accent) ? t.accent : "#4A6DA8"
    property color panelColor:  (t && t.panel)  ? t.panel  : "#0B1324"
    property color textColor:   (t && t.text)   ? t.text   : "#FFFFFF"
    property color glowColor:   (t && t.glow)   ? t.glow   : accentColor

    property real accentLum: (accentColor.r * 0.299 + accentColor.g * 0.587 + accentColor.b * 0.114)
    property real panelLum:  (panelColor.r  * 0.299 + panelColor.g  * 0.587 + panelColor.b  * 0.114)
    property color panelInk: (panelLum > 0.62) ? "#111111" : "#F7F8FA"
    property color selectedInk: (accentLum > 0.62) ? "#111111" : "#FFFFFF"
    property color dangerInk: SemanticTheme.tone(cal.t, "danger")
    property color dowBase: (accentLum > 0.72) ? Qt.darker(accentColor, 1.55) : accentColor
    property color dowColor: cal.panelInk
    property color outMonthBase: (accentLum > 0.72) ? Qt.darker(accentColor, 1.35) : accentColor
    property color outMonthColor: SemanticTheme.inkMuted(cal.t, "Professional")

    property int flashEpoch: 0
    function pulseSelection() {
        flashEpoch = flashEpoch + 1
    }

    function centerWindow() {
        var s = _preferredScreen(-1, -1)
        if (s) cal.screen = s
        var rect = _screenRect(s)
        var popupW = Math.max(1, Math.round(cal.width))
        var popupH = Math.max(1, Math.round(cal.height))
        var destX = Math.round(rect.x + ((rect.w - popupW) / 2.0))
        var destY = Math.round(rect.y + ((rect.h - popupH) / 2.0))
        cal.x = destX
        cal.y = destY
    }

    // VISUAL CONTENT
    Rectangle {
        id: win
        width: Math.max(1, Math.round(cal.width * cal.scaleRatios.innerWidthPct))
        height: Math.max(1, Math.round(cal.height * cal.scaleRatios.innerHeightPct))
        radius: cal.ratioWindow(cal.scaleRatios.panelCornerPct, 1)
        color: panelColor
        border.width: cal.ratioWindow(cal.scaleRatios.panelBorderPct, 1)
        border.color: accentColor
        
        anchors.centerIn: parent

        layer.enabled: true
        layer.effect: DropShadow {
            transparentBorder: true
            horizontalOffset: 0
            verticalOffset: cal.ratioWindow(cal.scaleRatios.panelShadowPct, 1)
            radius: cal.ratioWindow(cal.scaleRatios.panelShadowPct, 1)
            samples: cal.ratioWindow(cal.scaleRatios.panelShadowSamplesPct, 3)
            color: SemanticTheme.overlayScrim(cal.t, "Professional")
        }

        focus: true
        Keys.onShortcutOverride: function(event) {
            if (event.key === Qt.Key_Escape) {
                event.accepted = true
                cal.pendingDate = cal.selectedDate
                cal.hideCalendar()
            }
        }
        Keys.onEscapePressed: {
            cal.pendingDate = cal.selectedDate
            cal.hideCalendar()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: cal.ratioWindow(cal.scaleRatios.panelMarginPct, 1)
            spacing: cal.ratioWindow(cal.scaleRatios.panelSpacingPct, 1)

            // TITLE BAR
            Rectangle {
                id: titleBar
                Layout.fillWidth: true
                Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.titleBarHeightPct, 1)
                radius: cal.ratioWindow(cal.scaleRatios.titleBarCornerPct, 1)
                color: SemanticTheme.borderSubtle(cal.t, "Professional")
                border.width: cal.ratioWindow(cal.scaleRatios.titleBarBorderPct, 1)
                border.color: SemanticTheme.borderSubtle(cal.t, "Professional")

                MouseArea {
                    anchors.fill: parent
                    onPressed: cal.startSystemMove()
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: cal.ratioWindow(cal.scaleRatios.titleInsetPct, 1)
                    anchors.rightMargin: cal.ratioWindow(cal.scaleRatios.titleInsetPct, 1)
                    spacing: cal.ratioWindow(cal.scaleRatios.titleSpacingPct, 1)

                    Button {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: cal.ratioWindow(cal.scaleRatios.titleButtonWidthPct, 1)
                        Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.titleButtonHeightPct, 1)
                        flat: true
                        onClicked: cal.shiftDisplayedMonth(-1)
                        
                        contentItem: Text {
                            text: "<"
                            color: parent.hovered ? cal.accentColor : panelInk
                            font.pixelSize: cal.ratioWindow(
                                cal.scaleRatios.titleButtonFontPct,
                                cal.metricFloorRatio("fontFloorBodyPx", cal.scaleRatios.fontFloorBodyPct)
                            )
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle { color: "transparent" }
                    }

                    Item {
                        id: monthYearHeader
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        implicitHeight: monthText.implicitHeight

                        Row {
                            anchors.centerIn: parent
                            spacing: cal.ratioWindow(cal.scaleRatios.titleSpacingPct * 0.7, 4)

                            Text {
                                id: monthText
                                text: Qt.formatDate(new Date(grid.year, grid.month, 1), "MMMM")
                                color: panelInk
                                font.bold: true
                                font.pixelSize: cal.ratioWindow(
                                    cal.scaleRatios.titleTextPct,
                                    cal.metricFloorRatio("fontFloorTitlePx", cal.scaleRatios.fontFloorTitlePct)
                                )
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: function(mouse) {
                                        cal.openMonthPicker()
                                        mouse.accepted = true
                                    }
                                }
                            }

                            Text {
                                id: yearText
                                text: Qt.formatDate(new Date(grid.year, grid.month, 1), "yyyy")
                                color: panelInk
                                font.bold: true
                                font.pixelSize: cal.ratioWindow(
                                    cal.scaleRatios.titleTextPct,
                                    cal.metricFloorRatio("fontFloorTitlePx", cal.scaleRatios.fontFloorTitlePct)
                                )
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: function(mouse) {
                                        cal.openYearPicker()
                                        mouse.accepted = true
                                    }
                                }
                            }
                        }
                    }

                    Button {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: cal.ratioWindow(cal.scaleRatios.titleButtonWidthPct, 1)
                        Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.titleButtonHeightPct, 1)
                        flat: true
                        onClicked: cal.shiftDisplayedMonth(1)
                        
                        contentItem: Text {
                            text: ">"
                            color: parent.hovered ? cal.accentColor : panelInk
                            font.pixelSize: cal.ratioWindow(
                                cal.scaleRatios.titleButtonFontPct,
                                cal.metricFloorRatio("fontFloorBodyPx", cal.scaleRatios.fontFloorBodyPct)
                            )
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle { color: "transparent" }
                    }

                    Button {
                        id: todayBtn
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: cal.ratioWindow(cal.scaleRatios.titleButtonWidthPct * 1.6, 52)
                        Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.titleButtonHeightPct, 1)
                        flat: true
                        onClicked: cal.jumpToToday()

                        contentItem: Text {
                            text: "Today"
                            color: todayBtn.hovered ? cal.accentColor : panelInk
                            font.pixelSize: cal.ratioWindow(
                                cal.scaleRatios.dowTextPct * 0.92,
                                cal.metricFloorRatio("fontFloorLabelPx", cal.scaleRatios.fontFloorLabelPct)
                            )
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: cal.ratioWindow(cal.scaleRatios.titleBarCornerPct * 0.7, 4)
                            color: todayBtn.hovered
                                ? SemanticTheme.hoverOverlay(cal.t, "Professional")
                                : SemanticTheme.borderSubtle(cal.t, "Professional")
                            border.width: 1
                            border.color: todayBtn.hovered ? SemanticTheme.hoverOverlay(cal.t, "Professional") : "transparent"
                        }
                    }

                    Button {
                        id: closeBtn
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: cal.ratioWindow(cal.scaleRatios.titleButtonWidthPct, 1)
                        Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.titleButtonHeightPct, 1)
                        flat: true
                        onClicked: cal.hideCalendar()
                        
                        contentItem: Text {
                            text: "\u00D7"
                            color: closeBtn.hovered ? cal.dangerInk : panelInk
                            font.pixelSize: cal.ratioWindow(
                                cal.scaleRatios.closeTextPct,
                                cal.metricFloorRatio("fontFloorIconPx", cal.scaleRatios.fontFloorIconPct)
                            )
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle { color: "transparent" }
                    }
                }
            }

            DayOfWeekRow {
                Layout.fillWidth: true
                delegate: Text {
                    required property var model
                    text: model.shortName
                    color: cal.dowColor
                    font.pixelSize: cal.ratioWindow(
                        cal.scaleRatios.dowTextPct,
                        cal.metricFloorRatio("fontFloorLabelPx", cal.scaleRatios.fontFloorLabelPct)
                    )
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MonthGrid {
                id: grid
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: cal.ratioWindow(scaleRatios.gridSpacingPct, 1)

                delegate: Rectangle {
                    required property var model
                    width: cal.ratioWindow(cal.scaleRatios.dayCellSizePct, 1)
                    height: width
                    radius: width / 2

                    property bool inThisMonth: (model.date.getMonth() === grid.month) && (model.date.getFullYear() === grid.year)
                    property bool isPending: model.date.getTime() === cal.pendingDate.getTime()
                    property bool isToday: {
                        var now = new Date()
                        return model.date.getDate() === now.getDate() &&
                               model.date.getMonth() === now.getMonth() &&
                               model.date.getFullYear() === now.getFullYear()
                    }

                    color: isPending ? cal.accentColor : (isToday ? SemanticTheme.hoverOverlay(cal.t, "Professional") : "transparent")
                    border.width: isToday ? cal.ratioWindow(cal.scaleRatios.todayBorderPct, 1) : 0
                    border.color: isToday ? cal.accentColor : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: model.day
                        font.pixelSize: cal.ratioWindow(
                            cal.scaleRatios.dayTextPct,
                            cal.metricFloorRatio("fontFloorBodyPx", cal.scaleRatios.fontFloorBodyPct)
                        )
                        font.bold: isPending || isToday
                        color: isPending ? cal.selectedInk : (inThisMonth ? cal.textColor : cal.outMonthColor)
                    }

                    Rectangle {
                        id: flashRing
                        anchors.centerIn: parent
                        width: parent.width - cal.ratioWindow(cal.scaleRatios.flashInsetPct, 1)
                        height: parent.height - cal.ratioWindow(cal.scaleRatios.flashInsetPct, 1)
                        radius: width / 2
                        color: "transparent"
                        border.width: cal.ratioWindow(cal.scaleRatios.flashBorderPct, 1)
                        border.color: cal.accentColor
                        opacity: 0.0
                    }

                    SequentialAnimation {
                        id: flashAnim
                        running: false
                        NumberAnimation { target: flashRing; property: "opacity"; from: 0.0; to: 0.9; duration: 90; easing.type: Easing.OutQuad }
                        PauseAnimation { duration: 70 }
                        NumberAnimation { target: flashRing; property: "opacity"; to: 0.0; duration: 240; easing.type: Easing.OutQuad }
                    }

                    onIsPendingChanged: {
                        if (isPending) flashAnim.restart()
                    }
                    Connections {
                        target: cal
                        function onFlashEpochChanged() {
                            if (isPending) flashAnim.restart()
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton

                        onClicked: function(mouse) {
                            cal.pendingDate = model.date
                            mouse.accepted = true
                        }

                        onDoubleClicked: function(mouse) {
                            var clicked = new Date(model.date.getTime())

                            if (!inThisMonth) {
                                grid.month = clicked.getMonth()
                                grid.year = clicked.getFullYear()
                                cal.pendingDate = clicked
                                cal.pulseSelection()
                                mouse.accepted = true
                                return
                            }

                            cal.acceptDateAndClose(clicked)
                            mouse.accepted = true
                        }
                    }
                }
            }
        }

        Popup {
            id: monthPickerPopup
            parent: win
            modal: true
            focus: true
            dim: false
            closePolicy: Popup.CloseOnEscape
            padding: cal.ratioWindow(cal.scaleRatios.panelMarginPct * 0.75, 12)
            width: cal.ratioWindow(0.58, 300)
            height: cal.ratioWindow(0.42, 230)
            x: Math.round((win.width - width) / 2)
            y: Math.round(titleBar.y + titleBar.height + cal.ratioWindow(0.016, 6))

            background: Rectangle {
                radius: cal.ratioWindow(cal.scaleRatios.panelCornerPct * 0.7, 10)
                color: SemanticTheme.surfacePanel(cal.t, "Professional")
                border.width: cal.ratioWindow(cal.scaleRatios.panelBorderPct, 1)
                border.color: SemanticTheme.accentPrimary(cal.t, "Professional")
            }

            contentItem: ColumnLayout {
                anchors.fill: parent
                spacing: cal.ratioWindow(cal.scaleRatios.panelSpacingPct * 0.90, 10)

                Text {
                    Layout.fillWidth: true
                    text: "Select Month"
                    color: cal.panelInk
                    horizontalAlignment: Text.AlignHCenter
                    font.bold: true
                    font.pixelSize: cal.ratioWindow(
                        cal.scaleRatios.dowTextPct,
                        cal.metricFloorRatio("fontFloorLabelPx", cal.scaleRatios.fontFloorLabelPct)
                    )
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: cal.ratioWindow(cal.scaleRatios.titleBarCornerPct, 8)
                    color: SemanticTheme.borderSubtle(cal.t, "Professional")
                    border.width: 1
                    border.color: SemanticTheme.borderSubtle(cal.t, "Professional")

                    GridLayout {
                        anchors.fill: parent
                        anchors.margins: cal.ratioWindow(cal.scaleRatios.panelMarginPct * 0.52, 10)
                        columns: 4
                        rowSpacing: cal.ratioWindow(scaleRatios.gridSpacingPct * 1.40, 8)
                        columnSpacing: cal.ratioWindow(scaleRatios.gridSpacingPct * 1.40, 8)

                        Repeater {
                            model: cal.monthNames
                            delegate: Rectangle {
                                id: monthCell
                                required property int index
                                required property string modelData
                                readonly property int monthIndex: index
                                readonly property bool isCurrentMonth: monthIndex === grid.month

                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredHeight: cal.ratioWindow(cal.scaleRatios.dayCellSizePct * 0.42, 30)
                                radius: cal.ratioWindow(cal.scaleRatios.titleBarCornerPct * 0.8, 6)
                                color: isCurrentMonth
                                    ? SemanticTheme.accentPrimary(cal.t, "Professional")
                                    : SemanticTheme.borderSubtle(cal.t, "Professional")
                                border.width: 1
                                border.color: isCurrentMonth
                                    ? SemanticTheme.accentPrimary(cal.t, "Professional")
                                    : SemanticTheme.borderSubtle(cal.t, "Professional")

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.substring(0, 3)
                                    color: isCurrentMonth ? cal.selectedInk : cal.panelInk
                                    font.bold: isCurrentMonth
                                    font.pixelSize: cal.ratioWindow(
                                        cal.scaleRatios.dowTextPct * 0.86,
                                        cal.metricFloorRatio("fontFloorLabelPx", cal.scaleRatios.fontFloorLabelPct)
                                    )
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: function(mouse) {
                                        var selectedMonth = monthCell.monthIndex
                                        if (selectedMonth < 0 || selectedMonth > 11) {
                                            mouse.accepted = true
                                            return
                                        }
                                        grid.month = selectedMonth
                                        cal.pendingDate = new Date(grid.year, selectedMonth, 1)
                                        monthPickerPopup.close()
                                        mouse.accepted = true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Popup {
            id: yearPickerPopup
            parent: win
            modal: false
            focus: true
            dim: false
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
            padding: cal.ratioWindow(cal.scaleRatios.panelMarginPct * 0.55, 8)
            width: cal.ratioWindow(0.30, 150)
            height: cal.ratioWindow(0.52, 270)
            x: Math.round((win.width - width) / 2)
            y: Math.round(titleBar.y + titleBar.height + cal.ratioWindow(0.016, 6))

            background: Rectangle {
                radius: cal.ratioWindow(cal.scaleRatios.panelCornerPct * 0.7, 10)
                color: SemanticTheme.surfacePanel(cal.t, "Professional")
                border.width: cal.ratioWindow(cal.scaleRatios.panelBorderPct, 1)
                border.color: SemanticTheme.accentPrimary(cal.t, "Professional")
            }

            contentItem: ColumnLayout {
                anchors.fill: parent
                spacing: cal.ratioWindow(cal.scaleRatios.panelSpacingPct * 0.66, 6)

                Text {
                    Layout.fillWidth: true
                    text: "Select Year"
                    color: cal.panelInk
                    horizontalAlignment: Text.AlignHCenter
                    font.bold: true
                    font.pixelSize: cal.ratioWindow(
                        cal.scaleRatios.dowTextPct,
                        cal.metricFloorRatio("fontFloorLabelPx", cal.scaleRatios.fontFloorLabelPct)
                    )
                }

                ListView {
                    id: yearList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: Math.max(0, cal.maxSelectableYear - cal.minSelectableYear + 1)
                    currentIndex: Math.max(0, Math.min(count - 1, grid.year - cal.minSelectableYear))
                    spacing: cal.ratioWindow(scaleRatios.gridSpacingPct * 0.6, 3)
                    ScrollBar.vertical: ScrollBar { }

                    delegate: Rectangle {
                        required property int index
                        readonly property int yearValue: cal.minSelectableYear + index
                        readonly property bool isCurrentYear: yearValue === grid.year
                        width: yearList.width
                        height: cal.ratioWindow(cal.scaleRatios.dayCellSizePct * 0.42, 26)
                        radius: cal.ratioWindow(cal.scaleRatios.titleBarCornerPct * 0.7, 6)
                        color: isCurrentYear
                            ? SemanticTheme.accentPrimary(cal.t, "Professional")
                            : SemanticTheme.borderSubtle(cal.t, "Professional")
                        border.width: 1
                        border.color: isCurrentYear
                            ? SemanticTheme.accentPrimary(cal.t, "Professional")
                            : SemanticTheme.borderSubtle(cal.t, "Professional")

                        Text {
                            anchors.centerIn: parent
                            text: String(parent.yearValue)
                            color: parent.isCurrentYear ? cal.selectedInk : cal.panelInk
                            font.bold: parent.isCurrentYear
                            font.pixelSize: cal.ratioWindow(
                                cal.scaleRatios.dayTextPct * 0.84,
                                cal.metricFloorRatio("fontFloorBodyPx", cal.scaleRatios.fontFloorBodyPct)
                            )
                        }

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton
                            cursorShape: Qt.PointingHandCursor
                            onClicked: function(mouse) {
                                grid.year = parent.yearValue
                                yearPickerPopup.close()
                                mouse.accepted = true
                            }
                        }
                    }
                }
            }
        }
    }
}
