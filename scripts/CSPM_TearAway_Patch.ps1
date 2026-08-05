<#
CSPM_TearAway_Patch.ps1
Single-run patch script:
- Creates timestamped backups of modified files
- Overwrites QML files deterministically
- Runs the app via the repo .venv python

Run from repo root in PowerShell:
  .\CSPM_TearAway_Patch.ps1
#>

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    $here = Get-Location
    if (Test-Path (Join-Path $here 'src\qml\Main.qml')) { return $here.Path }

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (Test-Path (Join-Path $scriptDir 'src\qml\Main.qml')) { return $scriptDir }

    throw "Repo root not found. Run this script from the CSPM repo root (where src\qml\Main.qml exists)."
}

function New-BackupFolder([string]$root) {
    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    $b = Join-Path $root (Join-Path 'backups' (Join-Path 'patches' $ts))
    New-Item -ItemType Directory -Force -Path $b | Out-Null
    return $b
}

function Backup-File([string]$root, [string]$backupRoot, [string]$relPath) {
    $src = Join-Path $root $relPath
    if (!(Test-Path $src)) {
        throw "Expected file missing: $relPath"
    }
    $dst = Join-Path $backupRoot $relPath
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    Copy-Item -Force $src $dst
}

function Write-Utf8NoBom([string]$path, [string]$content) {
    $dir = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
}

function Get-PythonExe([string]$root) {
    $winPy = Join-Path $root '.venv\Scripts\python.exe'
    $nixPy = Join-Path $root '.venv\bin\python'
    if (Test-Path $winPy) { return $winPy }
    if (Test-Path $nixPy) { return $nixPy }
    throw "Python not found in .venv. Ensure the repo has an activated/created .venv."
}

$root = Resolve-RepoRoot
$backup = New-BackupFolder $root

$targets = @(
    'src\qml\Main.qml',
    'src\qml\views\TimeDocketView.qml',
    'src\qml\windows\FloatingDocketWindow.qml'
)

Write-Host "[PATCH] Repo root: $root"
Write-Host "[PATCH] Backup dir: $backup"

foreach ($t in $targets) {
    Backup-File $root $backup $t
    Write-Host "[PATCH] Backed up: $t"
}

# Overwrite files
$mainQml = @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import "components"

ApplicationWindow {
    id: win
    visible: false
    width: 1220
    height: 920
    minimumWidth: 920
    minimumHeight: 720
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.NoDropShadowWindowHint
    color: "transparent"

    // Theme
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property var t: (appRef && appRef.theme && appRef.theme.bg) ? appRef.theme : ({
        "bg": "#000000",
        "panel": "#0B1324",
        "panel2": "#121F38",
        "accent": "#2979FF",
        "hover": "#448AFF",
        "text": "#FFFFFF",
        "muted": "#B9C9FF",
        "btn_text": "white",
        "glow": "#2979FF"
    })

    readonly property bool isMaximized: win.visibility === Window.Maximized

    // Window animation state
    property bool animating: false
    property bool closing: false
    property bool forceClose: false
    property bool wasMinimized: false

    // Navigation
    property int currentPage: 0
    property bool transitionRunning: false

    // Tile geometry tracking (global + local)
    property rect lastTileGeom: Qt.rect(win.width/2, win.height/2, 100, 100)         // local to pageContainer parent
    property rect lastTileGlobalRect: Qt.rect(win.x + win.width/2, win.y + win.height/2, 100, 100) // global screen coords

    // Multi-window registry
    property var floatingWindows: []  // [{id, moduleKey, windowRef, originRect, createdAt}]
    property int floatSeq: 0
    property bool pendingExitAfterFloaters: false

    // State handoff for module restore
    property var pendingModuleState: null

    function focusTop() {
        win.raise()
        win.requestActivate()
    }

    function bringAllFloatersToFront() {
        for (var i = 0; i < floatingWindows.length; i++) {
            var fw = floatingWindows[i]
            if (fw && fw.windowRef) {
                try { fw.windowRef.raise() } catch(e) {}
                try { fw.windowRef.requestActivate() } catch(e) {}
            }
        }
    }

    function _removeFloaterById(fid) {
        var next = []
        for (var i = 0; i < floatingWindows.length; i++) {
            var fw = floatingWindows[i]
            if (!fw || fw.id !== fid) next.push(fw)
        }
        floatingWindows = next
    }

    function toggleMaximize() {
        if (isMaximized) win.showNormal(); else win.showMaximized()
    }

    function startMinimize() {
        if (!animating) {
            animating = true
            minimizeAnim.restart()
        }
    }

    function requestCloseAnimated() {
        if (!closing) {
            closing = true
            animating = true
            closeAnim.restart()
        }
    }

    function _beginAppCloseFlow() {
        if (floatingWindows.length > 0) {
            bringAllFloatersToFront()
            appCloseWarning.open()
            return
        }
        requestCloseAnimated()
    }

    onClosing: function(close) {
        if (forceClose) {
            close.accepted = true
            return
        }
        close.accepted = false
        _beginAppCloseFlow()
    }

    onVisibilityChanged: {
        if (win.visibility === Window.Minimized) {
            wasMinimized = true
            animating = false
        } else if (win.visibility === Window.Windowed || win.visibility === Window.Maximized) {
            if (wasMinimized) {
                wasMinimized = false
                restoreAnim.restart()
            } else if (!animating && !openAnim.running && !minimizeAnim.running) {
                mainContainer.opacity = 1.0
                bubbleScale.xScale = 1.0
                bubbleScale.yScale = 1.0
                bubbleTranslate.y = 0
            }
        }
    }

    function detectMonitorAndOpen() {
        if (animating) return
        animating = true
        closing = false
        forceClose = false

        var cx = (appRef && appRef.lastClick) ? appRef.lastClick.x : 0
        var cy = (appRef && appRef.lastClick) ? appRef.lastClick.y : 0

        var targetScreen = null
        for (var i = 0; i < Qt.application.screens.length; i++) {
            var s = Qt.application.screens[i]
            if (cx >= s.virtualX && cx < (s.virtualX + s.width) && cy >= s.virtualY && cy < (s.virtualY + s.height)) {
                targetScreen = s
                break
            }
        }
        if (!targetScreen) targetScreen = Screen.primaryScreen

        var finalX = targetScreen.virtualX + (targetScreen.width - win.width) / 2
        var finalY = targetScreen.virtualY + (targetScreen.height - win.height) / 2
        win.x = finalX
        win.y = finalY
        win.visible = true
        focusTop()

        var localPt = mainContainer.mapFromGlobal(cx, cy)
        bubbleScale.origin.x = localPt.x
        bubbleScale.origin.y = localPt.y
        bubbleScale.xScale = 0.06
        bubbleScale.yScale = 0.06
        mainContainer.opacity = 0.0
        openAnim.restart()
    }

    Component.onCompleted: detectMonitorAndOpen()

    // ------------------------
    // Module + Floater Factory
    // ------------------------

    function openModule(index, geom, state) {
        if (transitionRunning) return
        pendingModuleState = (state !== undefined) ? state : null

        currentPage = index
        lastTileGlobalRect = geom

        var globalGeom = consoleView.mapToGlobal(geom.x, geom.y)
        var localGeom = pageContainer.parent.mapFromGlobal(globalGeom.x, globalGeom.y)
        lastTileGeom = Qt.rect(localGeom.x, localGeom.y, geom.width, geom.height)

        // Existing elastic open
        var tx = lastTileGeom.x + (lastTileGeom.width / 2)
        var ty = lastTileGeom.y + (lastTileGeom.height / 2)
        var containerW = pageContainer.parent.width
        var containerH = pageContainer.parent.height
        var throwDist = 250
        var startX = (tx < containerW / 2) ? (-(containerW / 2) - throwDist) : ((containerW / 2) + throwDist)
        var startY = (ty < containerH / 2) ? (-(containerH / 2) - throwDist) : ((containerH / 2) + throwDist)

        pageContainer.visible = true
        pageContainer.opacity = 0
        pageScale.xScale = 0.05
        pageScale.yScale = 0.05
        pageTrans.x = startX
        pageTrans.y = startY
        pageRot.angle = 0
        pageScale.origin.x = pageContainer.width / 2
        pageScale.origin.y = pageContainer.height / 2

        openSequence.restart()
    }

    function closeModule() {
        if (!transitionRunning) {
            closeSequence.restart()
        }
    }

    function _createFloater(moduleKey, originRect, stateSnapshot) {
        var component = Qt.createComponent("windows/FloatingDocketWindow.qml")
        if (component.status !== Component.Ready) {
            console.warn("Floating window component not ready:", component.errorString())
            return
        }

        floatSeq += 1
        var fid = moduleKey + "_" + Date.now().toString() + "_" + floatSeq.toString()

        var fw = component.createObject(null, {
            "t": win.t,
            "moduleKey": moduleKey,
            "instanceId": fid,
            "originRect": originRect,
            "initialState": stateSnapshot
        })

        if (!fw) {
            console.warn("Failed to create floating window")
            return
        }

        floatingWindows = floatingWindows.concat([{ "id": fid, "moduleKey": moduleKey, "windowRef": fw, "originRect": originRect, "createdAt": Date.now() }])

        fw.didClose.connect(function(id) {
            _removeFloaterById(id)
            if (pendingExitAfterFloaters && floatingWindows.length === 0) {
                pendingExitAfterFloaters = false
                requestCloseAnimated()
            }
        })

        fw.requestDocking.connect(function(state, origin, id) {
            _removeFloaterById(id)
            // Restore into console with state
            openModule(1, origin, state)
        })

        fw.show()
        fw.raise()
        fw.requestActivate()
    }

    // Tear-away sequence: the view emits detachRequested(state)
    property var _pendingDetachState: null
    property rect _pendingDetachOrigin: Qt.rect(0,0,80,80)

    function beginDetach(stateSnapshot) {
        if (transitionRunning) return
        _pendingDetachState = stateSnapshot
        _pendingDetachOrigin = lastTileGlobalRect
        detachSequence.restart()
    }

    SequentialAnimation {
        id: detachSequence
        onStarted: win.transitionRunning = true
        onFinished: win.transitionRunning = false

        ScriptAction {
            script: {
                // Origin for the "egg" deformation
                var ox = lastTileGeom.x + lastTileGeom.width / 2
                var oy = lastTileGeom.y + lastTileGeom.height / 2
                pageScale.origin.x = ox
                pageScale.origin.y = oy
                pageRot.origin.x = ox
                pageRot.origin.y = oy
                pageTrans.x = 0
                pageTrans.y = 0
            }
        }

        // Shake + wobble like jelly trying to escape
        ParallelAnimation {
            NumberAnimation { target: pageRot; property: "angle"; from: 0; to: 6; duration: 80; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "xScale"; from: 1.0; to: 1.08; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "yScale"; from: 1.0; to: 0.92; duration: 110; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: pageRot; property: "angle"; from: 6; to: -5; duration: 90; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "xScale"; from: 1.08; to: 0.94; duration: 120; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "yScale"; from: 0.92; to: 1.10; duration: 120; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: pageRot; property: "angle"; from: -5; to: 3; duration: 80; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "xScale"; from: 0.94; to: 1.04; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: pageScale; property: "yScale"; from: 1.10; to: 0.96; duration: 110; easing.type: Easing.OutQuad }
        }

        // Collapse into the origin point (implied "egg" deformation)
        ParallelAnimation {
            NumberAnimation { target: pageScale; property: "xScale"; to: 0.03; duration: 320; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            NumberAnimation { target: pageScale; property: "yScale"; to: 0.03; duration: 320; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            NumberAnimation { target: pageRot; property: "angle"; to: 0; duration: 220; easing.type: Easing.InQuad }
            NumberAnimation { target: pageContainer; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.OutQuad }
            NumberAnimation { target: consoleScale; property: "xScale"; to: 1.0; duration: 420; easing.type: Easing.OutElastic; easing.amplitude: 2.6; easing.period: 0.45 }
            NumberAnimation { target: consoleScale; property: "yScale"; to: 1.0; duration: 420; easing.type: Easing.OutElastic; easing.amplitude: 2.6; easing.period: 0.45 }
            NumberAnimation { target: consoleView; property: "opacity"; to: 1.0; duration: 240; easing.type: Easing.OutQuad }
        }

        ScriptAction {
            script: {
                // Destroy docked instance and return to console
                currentPage = 0
                pageContainer.visible = false
                pageContainer.opacity = 0

                // Spawn floater
                _createFloater("time_dockets", _pendingDetachOrigin, _pendingDetachState)
                _pendingDetachState = null
            }
        }
    }

    // ------------------------
    // Layout
    // ------------------------

    Item {
        id: mainContainer
        anchors.fill: parent
        anchors.margins: isMaximized ? 0 : 20

        transform: [
            Scale { id: bubbleScale; origin.x: width / 2; origin.y: height },
            Translate { id: bubbleTranslate },
            Rotation { id: bubbleRot }
        ]

        DropShadow {
            anchors.fill: bgFrame
            horizontalOffset: 0
            verticalOffset: 0
            radius: 32.0
            samples: 65
            color: t.glow
            source: bgFrame
            opacity: 0.9
            visible: !isMaximized
            cached: true
        }

        Rectangle {
            id: bgFrame
            anchors.fill: parent
            color: t.panel
            radius: isMaximized ? 0 : 16
            border.width: 1
            border.color: Qt.rgba(Qt.colorEqual(t.text, "transparent") ? 1 : Qt.rgba(t.text.r, t.text.g, t.text.b, 0.2).r, Qt.rgba(t.text.r, t.text.g, t.text.b, 0.2).g, Qt.rgba(t.text.r, t.text.g, t.text.b, 0.2).b, 0.2)
        }

        Rectangle { id: contentMask; anchors.fill: bgFrame; radius: bgFrame.radius; visible: false }

        Item {
            id: maskedArea
            anchors.fill: bgFrame
            anchors.margins: 1
            layer.enabled: true
            layer.effect: OpacityMask { maskSource: contentMask }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Title bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 60
                    color: "transparent"

                    Item {
                        anchors.fill: parent
                        DragHandler {
                            target: null
                            onActiveChanged: if (active && !win.isMaximized) win.startSystemMove()
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.topMargin: 14
                        anchors.leftMargin: 48
                        anchors.rightMargin: 40
                        spacing: 10
                        z: 999

                        Item {
                            Layout.fillWidth: true
                            height: parent.height
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Cory Schneider Law Office Practice Management"
                                color: t.text
                                opacity: 0.92
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                            }
                        }

                        TitleBarButton {
                            t: win.t
                            text: "\u2699"
                            fontSize: 18
                            onClicked: {
                                themePicker.x = parent.width - 280
                                themePicker.y = 60
                                themePicker.open()
                            }
                        }

                        TitleBarButton {
                            t: win.t
                            text: "\u2013"
                            fontSize: 22
                            onClicked: win.startMinimize()
                        }

                        TitleBarButton {
                            t: win.t
                            text: win.isMaximized ? "\u2750" : "\u2610"
                            fontSize: 16
                            onClicked: win.toggleMaximize()
                        }

                        TitleBarButton {
                            t: win.t
                            text: "\u2715"
                            fontSize: 16
                            danger: true
                            onClicked: win._beginAppCloseFlow()
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(t.text.r, t.text.g, t.text.b, 0.1) }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    // Console grid
                    Item {
                        id: consoleView
                        enabled: !pageContainer.visible
                        anchors.fill: parent
                        opacity: 1.0
                        transform: Scale { id: consoleScale; origin.x: width / 2; origin.y: height / 2 }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 14

                            Text {
                                text: "Practice Console"
                                color: t.text
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                                opacity: 0.95
                                Layout.leftMargin: 54
                                Layout.topMargin: 24
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(t.text.r, t.text.g, t.text.b, 0.1) }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: Qt.rgba(0, 0, 0, 0.10)
                                border.width: 1
                                border.color: Qt.rgba(1, 1, 1, 0.08)
                                radius: 12
                                Layout.margins: 30

                                GridLayout {
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    columns: 4
                                    columnSpacing: 20
                                    rowSpacing: 20

                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Time &\nDockets"; iconSource: Qt.resolvedUrl("assets/icons/time.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Fee\nEntries"; iconSource: Qt.resolvedUrl("assets/icons/fee.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Billing &\nInvoices"; iconSource: Qt.resolvedUrl("assets/icons/invoices.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Disbursements\n& Expenses"; iconSource: Qt.resolvedUrl("assets/icons/expenses.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Clients &\nMatters"; iconSource: Qt.resolvedUrl("assets/icons/clients.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Deadlines\n& Ticklers"; iconSource: Qt.resolvedUrl("assets/icons/ticklers.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Payments &\nA/R"; iconSource: Qt.resolvedUrl("assets/icons/payments.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                    TileCard { maximized: win.isMaximized; t: win.t; text: "Reports &\nProductivity"; iconSource: Qt.resolvedUrl("assets/icons/reports.svg"); Layout.fillWidth: true; Layout.fillHeight: true;
                                        onClicked: function(g) { win.openModule(1, g) }
                                    }
                                }
                            }
                        }
                    }

                    // Module container
                    Item {
                        id: pageContainer
                        anchors.fill: parent
                        visible: false
                        opacity: 0
                        transform: [
                            Translate { id: pageTrans },
                            Scale { id: pageScale; xScale: 1; yScale: 1 },
                            Rotation { id: pageRot; angle: 0; axis.z: 1 }
                        ]

                        Rectangle { anchors.fill: parent; color: t.panel; radius: isMaximized ? 0 : 16 }

                        Loader {
                            id: moduleLoader
                            anchors.fill: parent
                            anchors.margins: 40
                            source: win.currentPage === 1 ? "views/TimeDocketView.qml" : ""

                            onLoaded: {
                                if (!item) return
                                item.t = Qt.binding(function() { return win.t })

                                // Inject initial state for restore (if supported)
                                if (win.pendingModuleState !== null && item.hasOwnProperty("initialState")) {
                                    item.initialState = win.pendingModuleState
                                }

                                if (item.hasOwnProperty("detachRequested")) {
                                    item.detachRequested.connect(function(state) {
                                        win.beginDetach(state)
                                    })
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ------------------------
    // Close warning when floaters exist
    // ------------------------

    Popup {
        id: appCloseWarning
        anchors.centerIn: parent
        width: 520
        height: 240
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.NoAutoClose

        property color accentColor: (win.t && win.t.accent) ? win.t.accent : "#2979FF"
        property color panel2Color: (win.t && win.t.panel2) ? win.t.panel2 : "#121F38"
        property color textColor: (win.t && win.t.text) ? win.t.text : "#FFFFFF"

        background: Rectangle {
            color: panel2Color
            radius: 16
            border.width: 2
            border.color: accentColor
            layer.enabled: true
            layer.effect: DropShadow {
                transparentBorder: true
                color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.35)
                radius: 22
                samples: 44
                opacity: 0.8
            }
        }

        onOpened: {
            bringAllFloatersToFront()
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            Text {
                text: "FLOATING WINDOWS OPEN"
                color: textColor
                font.pixelSize: 18
                font.weight: Font.Bold
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: "You have one or more floating modules open.\nCancel to keep working, or close all windows."
                color: textColor
                opacity: 0.92
                font.pixelSize: 14
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                PillButton {
                    t: win.t
                    text: "Cancel"
                    primary: false
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 44
                    onClicked: appCloseWarning.close()
                }

                PillButton {
                    t: win.t
                    text: "Close all"
                    primary: true
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 44
                    onClicked: {
                        appCloseWarning.close()
                        pendingExitAfterFloaters = true
                        bringAllFloatersToFront()
                        for (var i = 0; i < floatingWindows.length; i++) {
                            var fw = floatingWindows[i]
                            if (fw && fw.windowRef && fw.windowRef.closeForAppExit) {
                                fw.windowRef.closeForAppExit()
                            } else if (fw && fw.windowRef) {
                                try { fw.windowRef.close() } catch(e) {}
                            }
                        }
                        // If none existed (race), just close main.
                        if (floatingWindows.length === 0) {
                            pendingExitAfterFloaters = false
                            requestCloseAnimated()
                        }
                    }
                }
            }
        }
    }

    ThemePicker {
        id: themePicker
        t: win.t
        names: appRef ? appRef.themeNames : []
        onPicked: function(name) {
            if (appRef) appRef.setTheme(name)
        }
        z: 999
    }

    Toast {
        id: toast
        t: win.t
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        z: 1000
    }

    Connections {
        target: appRef
        ignoreUnknownSignals: true
        function onToast(msg) { toast.show(msg) }
        function onError(msg) { toast.show(msg) }
        function onThemeChanged() {
            win.t = (appRef && appRef.theme && appRef.theme.bg) ? appRef.theme : ({})
        }
    }

    // Resize handles
    Item {
        id: resizeHandles
        anchors.fill: parent
        z: 99999
        visible: !win.isMaximized

        MouseArea { anchors { left: parent.left; right: parent.right; top: parent.top } height: 8; cursorShape: Qt.SizeVerCursor; onPressed: win.startSystemResize(Qt.TopEdge) }
        MouseArea { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 8; cursorShape: Qt.SizeVerCursor; onPressed: win.startSystemResize(Qt.BottomEdge) }
        MouseArea { anchors { top: parent.top; bottom: parent.bottom; left: parent.left } width: 8; cursorShape: Qt.SizeHorCursor; onPressed: win.startSystemResize(Qt.LeftEdge) }
        MouseArea { anchors { top: parent.top; bottom: parent.bottom; right: parent.right } width: 8; cursorShape: Qt.SizeHorCursor; onPressed: win.startSystemResize(Qt.RightEdge) }
        MouseArea { anchors { top: parent.top; left: parent.left } width: 16; height: 16; cursorShape: Qt.SizeFDiagCursor; onPressed: win.startSystemResize(Qt.TopEdge | Qt.LeftEdge) }
        MouseArea { anchors { top: parent.top; right: parent.right } width: 16; height: 16; cursorShape: Qt.SizeBDiagCursor; onPressed: win.startSystemResize(Qt.TopEdge | Qt.RightEdge) }
        MouseArea { anchors { bottom: parent.bottom; left: parent.left } width: 16; height: 16; cursorShape: Qt.SizeBDiagCursor; onPressed: win.startSystemResize(Qt.BottomEdge | Qt.LeftEdge) }
        MouseArea { anchors { bottom: parent.bottom; right: parent.right } width: 16; height: 16; cursorShape: Qt.SizeFDiagCursor; onPressed: win.startSystemResize(Qt.BottomEdge | Qt.RightEdge) }
    }

    // Open/minimize/close animations (existing)
    SequentialAnimation {
        id: openAnim
        onFinished: win.animating = false
        SequentialAnimation { PropertyAnimation { target: mainContainer; property: "opacity"; from: 0.0; to: 1.0; duration: 100 } }
        SequentialAnimation { PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.0; duration: 800; easing.type: Easing.OutElastic; easing.amplitude: 3.5; easing.period: 0.6 } }
        SequentialAnimation { PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 1.0; duration: 800; easing.type: Easing.OutElastic; easing.amplitude: 3.5; easing.period: 0.6 } }
    }

    SequentialAnimation {
        id: closeAnim
        ParallelAnimation {
            PropertyAnimation { target: mainContainer; property: "opacity"; to: 0.0; duration: 180 }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.08; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.06; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
        }
        ScriptAction {
            script: {
                win.forceClose = true
                win.close()
            }
        }
    }

    SequentialAnimation {
        id: minimizeAnim
        ParallelAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.2; duration: 400; easing.type: Easing.InBack; easing.overshoot: 1.0 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 1.5; duration: 400; easing.type: Easing.InBack; easing.overshoot: 1.0 }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 1500; duration: 400; easing.type: Easing.InBack; easing.overshoot: 1.0 }
            SequentialAnimation {
                PauseAnimation { duration: 300 }
                PropertyAnimation { target: mainContainer; property: "opacity"; to: 0; duration: 150 }
            }
        }
        ScriptAction {
            script: {
                win.showMinimized()
                animating = false
            }
        }
    }

    SequentialAnimation {
        id: restoreAnim
        ScriptAction {
            script: {
                bubbleScale.xScale = 0.2
                bubbleScale.yScale = 1.5
                bubbleTranslate.y = 1500
                mainContainer.opacity = 1.0
            }
        }
        ParallelAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 1.0; duration: 500; easing.type: Easing.OutBack }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 1.0; duration: 500; easing.type: Easing.OutBack }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 0; duration: 500; easing.type: Easing.OutBack }
        }
    }

    SequentialAnimation {
        id: openSequence
        onStarted: win.transitionRunning = true
        onFinished: win.transitionRunning = false
        ParallelAnimation {
            NumberAnimation { target: pageContainer; property: "opacity"; from: 0; to: 1; duration: 200 }
            NumberAnimation { target: pageTrans; property: "x"; to: 0; duration: 1100; easing.type: Easing.OutElastic; easing.amplitude: 2.0; easing.period: 0.6 }
            NumberAnimation { target: pageTrans; property: "y"; to: 0; duration: 1100; easing.type: Easing.OutElastic; easing.amplitude: 2.0; easing.period: 0.6 }
            NumberAnimation { target: pageScale; property: "xScale"; from: 0.05; to: 1.0; duration: 1000; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
            NumberAnimation { target: pageScale; property: "yScale"; from: 0.05; to: 1.0; duration: 1000; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
            NumberAnimation { target: consoleScale; property: "xScale"; to: 0.9; duration: 400; easing.type: Easing.OutQuad }
            NumberAnimation { target: consoleScale; property: "yScale"; to: 0.9; duration: 400; easing.type: Easing.OutQuad }
            NumberAnimation { target: consoleView; property: "opacity"; to: 0.4; duration: 400 }
        }
    }

    SequentialAnimation {
        id: closeSequence
        onStarted: {
            win.transitionRunning = true
            consoleScale.xScale = 0.5
            consoleScale.yScale = 0.5
            consoleView.opacity = 0
        }
        onFinished: {
            win.transitionRunning = false
            pageContainer.visible = false
            consoleView.opacity = 1.0
            currentPage = 0
        }

        ParallelAnimation {
            NumberAnimation { target: pageContainer; property: "opacity"; to: 0; duration: 250 }
            NumberAnimation { target: pageScale; property: "xScale"; to: 0.4; duration: 300; easing.type: Easing.InBack; easing.overshoot: 1.7 }
            NumberAnimation { target: pageScale; property: "yScale"; to: 0.4; duration: 300; easing.type: Easing.InBack; easing.overshoot: 1.7 }
            NumberAnimation { target: pageRot; property: "angle"; to: 6; duration: 300; easing.type: Easing.InCubic }

            SequentialAnimation {
                PauseAnimation { duration: 50 }
                ParallelAnimation {
                    NumberAnimation { target: consoleView; property: "opacity"; to: 1.0; duration: 100 }
                    NumberAnimation { target: consoleScale; property: "xScale"; to: 1.0; duration: 700; easing.type: Easing.OutElastic; easing.amplitude: 3.0; easing.period: 0.4 }
                    NumberAnimation { target: consoleScale; property: "yScale"; to: 1.0; duration: 700; easing.type: Easing.OutElastic; easing.amplitude: 3.0; easing.period: 0.4 }
                }
            }
        }
    }
}

'@

$timeViewQml = @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root
    property var t

    // Mode
    property bool isFloating: false

    // Transferable state
    property var initialState: null
    property int elapsedSeconds: 0
    property bool isRunning: false

    // Dirty tracking
    property bool dirty: false
    property bool _hydrating: false

    signal detachRequested(var state)
    signal returnRequested(var state)

    // click shield (prevents fall-through)
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onPressed: mouse.accepted = true
        onClicked: mouse.accepted = true
        z: 0
    }

    function formatTimer(totalSeconds) {
        var tsec = Math.max(0, Math.floor(totalSeconds || 0))
        var h = Math.floor(tsec / 3600)
        var m = Math.floor((tsec % 3600) / 60)
        var s = tsec % 60
        return (h < 10 ? "0" + h : "" + h) + ":" + (m < 10 ? "0" + m : "" + m) + ":" + (s < 10 ? "0" + s : "" + s)
    }

    function syncTimeFieldFromElapsed() {
        var hours = root.elapsedSeconds / 3600.0
        var rounded = Math.ceil(hours * 10) / 10
        timeInput.text = rounded.toFixed(1)
        calculateFees()
    }

    function setElapsedSecondsSafe(sec) {
        root.elapsedSeconds = Math.max(0, Math.floor(sec || 0))
        syncTimeFieldFromElapsed()
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

    function toggleTimer() {
        if (isRunning) {
            docketTimer.stop()
            isRunning = false
        } else {
            docketTimer.start()
            isRunning = true
        }
    }

    function calculateFees() {
        var hours = parseFloat(timeInput.text) || 0.0
        var r = parseFloat(rateInput.text) || 0.0
        var b = parseFloat(billInput.text) || 0.0
        feesInput.text = "$" + (hours * r * (b / 100.0)).toFixed(2)
    }

    function snapshotState() {
        return {
            "elapsedSeconds": root.elapsedSeconds,
            "isRunning": root.isRunning,
            "dirty": root.dirty,
            "dateText": dateInput.text,
            "timeText": timeInput.text,
            "rateText": rateInput.text,
            "billText": billInput.text,
            "feesText": feesInput.text,
            "matterText": matterCombo.editText,
            "clientText": clientCombo.editText,
            "taskText": taskCombo.editText,
            "descriptionText": descInput.text
        }
    }

    function applyInitialState(state) {
        if (!state) return
        _hydrating = true

        if (state.dateText !== undefined) dateInput.text = state.dateText
        if (state.timeText !== undefined) timeInput.text = state.timeText
        if (state.rateText !== undefined) rateInput.text = state.rateText
        if (state.billText !== undefined) billInput.text = state.billText

        if (state.matterText !== undefined) {
            matterCombo.editText = state.matterText
            var mi = matterCombo.find(state.matterText)
            if (mi >= 0) matterCombo.currentIndex = mi
        }
        if (state.clientText !== undefined) {
            clientCombo.editText = state.clientText
            var ci = clientCombo.find(state.clientText)
            if (ci >= 0) clientCombo.currentIndex = ci
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

        root.dirty = !!state.dirty

        // Timer
        root.isRunning = !!state.isRunning
        if (root.isRunning) {
            docketTimer.start()
        } else {
            docketTimer.stop()
        }

        calculateFees()
        _hydrating = false
    }

    Timer {
        id: docketTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.elapsedSeconds += 1
            syncTimeFieldFromElapsed()
        }
    }

    JellyCalendar {
        id: calendar
        t: root.t
        onDatePicked: function(d) {
            dateInput.text = Qt.formatDate(d, "yyyy-MM-dd")
            if (!root._hydrating) root.dirty = true
        }
    }

    // ===== TIMER POPUP (edit) =====
    Popup {
        id: timerEditPopup
        modal: true
        focus: true
        width: 380
        height: 210
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        property bool hasError: false

        background: Rectangle {
            color: t.panel2
            radius: 16
            border.width: 2
            border.color: timerEditPopup.hasError ? Qt.darker(t.accent, 1.2) : t.accent
        }

        onOpened: {
            hasError = false
            timerHms.text = root.formatTimer(root.elapsedSeconds)
            timerHms.forceActiveFocus()
            timerHms.selectAll()
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            Text {
                text: "Edit Timer (HH:MM:SS)"
                color: t.text
                font.pixelSize: 22
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }

            TextField {
                id: timerHms
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 300
                Layout.preferredHeight: 56
                font.pixelSize: 28
                font.weight: Font.DemiBold
                color: t.text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                placeholderText: "HH:MM:SS"

                background: Rectangle {
                    radius: 12
                    color: Qt.rgba(0, 0, 0, 0.18)
                    border.width: 1
                    border.color: timerEditPopup.hasError ? Qt.darker(t.accent, 1.2) : Qt.rgba(1, 1, 1, 0.12)
                }

                onAccepted: applyBtn.clicked()
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                spacing: 6

                Text {
                    text: "Tip:"
                    color: t.accent
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "Only available when paused/stopped."
                    color: t.text
                    opacity: 0.88
                    font.pixelSize: 14
                    font.weight: Font.Medium
                    wrapMode: Text.WordWrap
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                PillButton {
                    t: root.t
                    text: "Cancel"
                    primary: false
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 40
                    onClicked: timerEditPopup.close()
                }

                PillButton {
                    id: applyBtn
                    t: root.t
                    text: "Apply"
                    primary: true
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 40
                    onClicked: {
                        var sec = root.parseHmsToSeconds(timerHms.text)
                        if (sec === null) {
                            timerEditPopup.hasError = true
                            return
                        }
                        root.setElapsedSecondsSafe(sec)
                        if (!root._hydrating) root.dirty = true
                        timerEditPopup.close()
                    }
                }
            }
        }
    }

    // ===== MAIN LAYOUT =====
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 10
        z: 1

        RowLayout {
            Layout.fillWidth: true
            height: 50
            spacing: 20

            Text {
                text: "Time & Dockets"
                color: t.accent
                font.pixelSize: 32
                font.weight: Font.Bold
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: 180
                Layout.preferredHeight: 50
                color: Qt.rgba(0, 0, 0, 0.3)
                radius: 12
                border.width: 2
                border.color: root.isRunning ? t.accent : Qt.rgba(1, 1, 1, 0.20)

                Text {
                    anchors.centerIn: parent
                    text: root.formatTimer(root.elapsedSeconds)
                    color: root.isRunning ? t.accent : t.text
                    font.pixelSize: 26
                    font.family: "Courier New"
                    font.weight: Font.Bold
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !root.isRunning
                    hoverEnabled: true
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: timerEditPopup.open()
                }
            }

            PillButton {
                t: root.t
                text: root.isRunning ? "Pause" : "Start"
                primary: true
                Layout.preferredWidth: 120
                Layout.preferredHeight: 50
                onClicked: root.toggleTimer()
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 4
            columnSpacing: 30
            rowSpacing: 25

            ModernTextField {
                id: dateInput
                t: root.t
                label: "Date"
                text: Qt.formatDate(new Date(), "yyyy-MM-dd")
                Layout.fillWidth: true
                Layout.columnSpan: 2
                onTextChanged: if (!root._hydrating) root.dirty = true

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    onDoubleClicked: {
                        calendar.selectedDate = new Date(dateInput.text)
                        calendar.open()
                    }
                    onClicked: {
                        dateInput.forceActiveFocus()
                        mouse.accepted = false
                    }
                }
            }

            ModernTextField {
                id: timeInput
                t: root.t
                label: "Time (Hrs)"
                text: "0.0"
                Layout.fillWidth: true
                Layout.columnSpan: 2
                readOnly: root.isRunning
                onTextEdited: {
                    if (root.isRunning) return
                    var val = parseFloat(text) || 0.0
                    root.setElapsedSecondsSafe(Math.floor(val * 3600))
                    if (!root._hydrating) root.dirty = true
                }
                onTextChanged: root.calculateFees()
            }

            ModernComboBox {
                id: matterCombo
                t: root.t
                label: "Matter"
                Layout.fillWidth: true
                Layout.columnSpan: 2
                z: 3
                fullModel: ["M-2025-001 Incorporation", "M-2025-002 Trademark", "M-2025-003 General"]
                onEditTextChanged: if (!root._hydrating) root.dirty = true
                onActivated: if (!root._hydrating) root.dirty = true
            }

            ModernComboBox {
                id: clientCombo
                t: root.t
                label: "Client"
                Layout.fillWidth: true
                Layout.columnSpan: 2
                z: 2
                fullModel: ["Google Inc", "Stark Industries", "Wayne Enterprises"]
                onEditTextChanged: if (!root._hydrating) root.dirty = true
                onActivated: if (!root._hydrating) root.dirty = true
            }

            ModernComboBox {
                id: taskCombo
                t: root.t
                label: "Task / Activity"
                Layout.fillWidth: true
                Layout.columnSpan: 4
                z: 1
                fullModel: ["Drafting", "Meeting", "Research", "Telephone Call"]
                onEditTextChanged: if (!root._hydrating) root.dirty = true
                onActivated: if (!root._hydrating) root.dirty = true
            }

            TextArea {
                id: descInput
                Layout.fillWidth: true
                Layout.columnSpan: 4
                Layout.fillHeight: true
                Layout.minimumHeight: 80
                color: t.text
                font.pixelSize: 20
                wrapMode: Text.Wrap
                placeholderText: "Enter detailed description..."
                leftPadding: 16
                topPadding: 16
                onTextChanged: if (!root._hydrating) root.dirty = true

                background: Rectangle {
                    color: Qt.rgba(0, 0, 0, 0.2)
                    radius: 12
                    border.width: parent.activeFocus ? 3 : 1
                    border.color: parent.activeFocus ? t.accent : Qt.rgba(1, 1, 1, 0.15)
                }
            }

            ModernTextField {
                id: rateInput
                t: root.t
                label: "Rate ($)"
                text: "450.00"
                Layout.fillWidth: true
                onTextChanged: {
                    root.calculateFees()
                    if (!root._hydrating) root.dirty = true
                }
            }

            ModernTextField {
                id: billInput
                t: root.t
                label: "Bill %"
                text: "100"
                Layout.fillWidth: true
                onTextChanged: {
                    root.calculateFees()
                    if (!root._hydrating) root.dirty = true
                }
            }

            ModernTextField {
                id: feesInput
                t: root.t
                label: "Total Fees"
                text: ".00"
                readOnly: true
                Layout.fillWidth: true
                Layout.columnSpan: 2
            }
        }

        RowLayout {
            Layout.fillWidth: true
            height: 60
            spacing: 20

            PillButton {
                t: root.t
                text: "Save Docket"
                primary: true
                Layout.preferredWidth: 200
                Layout.preferredHeight: 60
                onClicked: {
                    // UX-only save flag for now
                    root.dirty = false
                }
            }

            PillButton {
                t: root.t
                text: root.isFloating ? "Close" : "Cancel"
                primary: false
                Layout.preferredWidth: 140
                Layout.preferredHeight: 60
                onClicked: {
                    if (root.isFloating) {
                        root.returnRequested(root.snapshotState())
                    } else {
                        // Main window owns closeModule()
                        try { win.closeModule() } catch(e) {}
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Tear away button only when docked
            PillButton {
                visible: !root.isFloating
                t: root.t
                text: "Tear Away"
                primary: true
                Layout.preferredWidth: 180
                Layout.preferredHeight: 60
                onClicked: {
                    root.detachRequested(root.snapshotState())
                }
            }
        }
    }

    Component.onCompleted: {
        syncTimeFieldFromElapsed()
        if (initialState) {
            applyInitialState(initialState)
        }
    }

    onInitialStateChanged: {
        if (initialState) applyInitialState(initialState)
    }
}

'@

$floatingQml = @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import "../components"
import "../views"

Window {
    id: floatWin
    width: 920
    height: 740
    visible: true
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint
    color: "transparent"

    property var t: ({})
    property string moduleKey: "time_dockets"
    property string instanceId: ""
    property rect originRect: Qt.rect(0, 0, 120, 120)
    property var initialState: null

    property bool _bypassCloseWarn: false
    property bool _closingAnimRunning: false

    signal requestDocking(var state, rect originRect, string instanceId)
    signal didClose(string instanceId)

    property color accentColor: (t && t.accent) ? t.accent : "#2979FF"
    property color panelColor: (t && t.panel) ? t.panel : "#0B1324"
    property color panel2Color: (t && t.panel2) ? t.panel2 : "#121F38"
    property color textColor: (t && t.text) ? t.text : "#FFFFFF"

    function _screenForPoint(px, py) {
        var s = null
        for (var i = 0; i < Qt.application.screens.length; i++) {
            var sc = Qt.application.screens[i]
            if (px >= sc.virtualX && px < (sc.virtualX + sc.width) && py >= sc.virtualY && py < (sc.virtualY + sc.height)) {
                s = sc
                break
            }
        }
        if (!s) s = Screen.primaryScreen
        return s
    }

    function _computeFinalGeometry() {
        var cx = originRect.x + originRect.width / 2
        var cy = originRect.y + originRect.height / 2
        var sc = _screenForPoint(cx, cy)

        var targetW = Math.min(920, Math.max(720, Math.round(sc.width * 0.62)))
        var targetH = Math.min(740, Math.max(560, Math.round(sc.height * 0.70)))

        var fx = sc.virtualX + Math.round((sc.width - targetW) / 2)
        var fy = sc.virtualY + Math.round((sc.height - targetH) / 2)
        return { x: fx, y: fy, w: targetW, h: targetH }
    }

    function _computeStartGeometry() {
        var cx = originRect.x + originRect.width / 2
        var cy = originRect.y + originRect.height / 2
        var sw = Math.max(140, Math.round(originRect.width))
        var sh = Math.max(140, Math.round(originRect.height))
        return { x: Math.round(cx - sw / 2), y: Math.round(cy - sh / 2), w: sw, h: sh }
    }

    function _snapshotState() {
        if (timeView && timeView.snapshotState) return timeView.snapshotState()
        return initialState
    }

    function closeForAppExit() {
        _bypassCloseWarn = true
        _startExitCloseAnimation()
    }

    function _startExitCloseAnimation() {
        if (_closingAnimRunning) return
        _closingAnimRunning = true
        exitCloseAnim.restart()
    }

    function _startDockReturn() {
        if (_closingAnimRunning) return
        _closingAnimRunning = true
        dockReturnAnim.restart()
    }

    onClosing: function(close) {
        if (_bypassCloseWarn) {
            close.accepted = true
            return
        }
        if (_closingAnimRunning) {
            close.accepted = true
            return
        }
        if (timeView && (timeView.isRunning || timeView.dirty)) {
            close.accepted = false
            closeWarn.open()
            return
        }
        close.accepted = true
    }

    onVisibleChanged: {
        if (!visible) {
            didClose(instanceId)
        }
    }

    // Layout shell
    ChromeSurface {
        id: chrome
        anchors.fill: parent
        t: floatWin.t

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Title bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 60
                    color: "transparent"

                    Item {
                        anchors.fill: parent
                        DragHandler { target: floatWin }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 26
                        anchors.rightMargin: 22
                        anchors.topMargin: 14
                        spacing: 10

                        Text {
                            text: "Time & Dockets"
                            color: accentColor
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Item { Layout.fillWidth: true }

                        PillButton {
                            t: floatWin.t
                            text: "Return to dock"
                            primary: true
                            Layout.preferredWidth: 170
                            Layout.preferredHeight: 40
                            onClicked: _startDockReturn()
                        }

                        TitleBarButton {
                            t: floatWin.t
                            text: "\u2715"
                            fontSize: 16
                            danger: true
                            onClicked: floatWin.close()
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.10) }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TimeDocketView {
                        id: timeView
                        anchors.fill: parent
                        anchors.margins: 28
                        t: floatWin.t
                        isFloating: true
                        initialState: floatWin.initialState
                        onReturnRequested: function(state) { _startDockReturn() }
                    }
                }
            }
        }
    }

    // Open from tile origin with jelly wobble
    SequentialAnimation {
        id: openAnim
        running: false

        ScriptAction {
            script: {
                var s = _computeStartGeometry()
                floatWin.x = s.x
                floatWin.y = s.y
                floatWin.width = s.w
                floatWin.height = s.h
                containerScale.xScale = 0.65
                containerScale.yScale = 0.85
                containerRot.angle = -7
                chrome.opacity = 0.0
            }
        }

        ParallelAnimation {
            NumberAnimation { target: chrome; property: "opacity"; to: 1.0; duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerRot; property: "angle"; to: 5; duration: 120; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 1.18; duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "yScale"; to: 0.82; duration: 160; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: -3; duration: 120; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 0.92; duration: 160; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "yScale"; to: 1.12; duration: 160; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: 0; duration: 140; easing.type: Easing.OutElastic; easing.amplitude: 2.2; easing.period: 0.45 }
            NumberAnimation { target: containerScale; property: "xScale"; to: 1.0; duration: 520; easing.type: Easing.OutElastic; easing.amplitude: 2.6; easing.period: 0.45 }
            NumberAnimation { target: containerScale; property: "yScale"; to: 1.0; duration: 520; easing.type: Easing.OutElastic; easing.amplitude: 2.6; easing.period: 0.45 }

            ScriptAction {
                script: {
                    var f = _computeFinalGeometry()
                    geoAnimX.to = f.x
                    geoAnimY.to = f.y
                    geoAnimW.to = f.w
                    geoAnimH.to = f.h
                    geoAnimX.restart(); geoAnimY.restart(); geoAnimW.restart(); geoAnimH.restart()
                }
            }
        }
    }

    // Geometry anims
    NumberAnimation { id: geoAnimX; target: floatWin; property: "x"; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 1.0 }
    NumberAnimation { id: geoAnimY; target: floatWin; property: "y"; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 1.0 }
    NumberAnimation { id: geoAnimW; target: floatWin; property: "width"; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 1.0 }
    NumberAnimation { id: geoAnimH; target: floatWin; property: "height"; duration: 560; easing.type: Easing.OutBack; easing.overshoot: 1.0 }

    // Reverse to dock
    SequentialAnimation {
        id: dockReturnAnim

        ScriptAction {
            script: {
                var s = _computeStartGeometry()
                backAnimX.to = s.x
                backAnimY.to = s.y
                backAnimW.to = s.w
                backAnimH.to = s.h
                _bypassCloseWarn = true
            }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: 7; duration: 90; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 1.10; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "yScale"; to: 0.90; duration: 110; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: -5; duration: 90; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 0.92; duration: 120; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "yScale"; to: 1.12; duration: 120; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: 0; duration: 120; easing.type: Easing.InQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 0.20; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.1 }
            NumberAnimation { target: containerScale; property: "yScale"; to: 0.16; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.1 }
            NumberAnimation { target: chrome; property: "opacity"; to: 0.0; duration: 160; easing.type: Easing.OutQuad }
            ScriptAction {
                script: {
                    backAnimX.restart(); backAnimY.restart(); backAnimW.restart(); backAnimH.restart()
                }
            }
        }

        PauseAnimation { duration: 120 }

        ScriptAction {
            script: {
                var st = _snapshotState()
                requestDocking(st, originRect, instanceId)
                floatWin.close()
            }
        }
    }

    NumberAnimation { id: backAnimX; target: floatWin; property: "x"; duration: 340; easing.type: Easing.InBack; easing.overshoot: 1.0 }
    NumberAnimation { id: backAnimY; target: floatWin; property: "y"; duration: 340; easing.type: Easing.InBack; easing.overshoot: 1.0 }
    NumberAnimation { id: backAnimW; target: floatWin; property: "width"; duration: 340; easing.type: Easing.InBack; easing.overshoot: 1.0 }
    NumberAnimation { id: backAnimH; target: floatWin; property: "height"; duration: 340; easing.type: Easing.InBack; easing.overshoot: 1.0 }

    // Exit close for app close-all (jelly collapse)
    SequentialAnimation {
        id: exitCloseAnim

        ScriptAction {
            script: {
                _bypassCloseWarn = true
            }
        }

        ParallelAnimation {
            NumberAnimation { target: containerRot; property: "angle"; to: 6; duration: 110; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "xScale"; to: 1.08; duration: 150; easing.type: Easing.OutQuad }
            NumberAnimation { target: containerScale; property: "yScale"; to: 0.90; duration: 150; easing.type: Easing.OutQuad }
        }

        ParallelAnimation {
            NumberAnimation { target: containerScale; property: "xScale"; to: 0.08; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            NumberAnimation { target: containerScale; property: "yScale"; to: 0.05; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            NumberAnimation { target: chrome; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.OutQuad }
        }

        ScriptAction {
            script: {
                floatWin.close()
            }
        }
    }

    // Container transforms (wobble without hardcoding colors)
    transform: [
        Scale { id: containerScale; origin.x: width/2; origin.y: height/2 },
        Rotation { id: containerRot; origin.x: width/2; origin.y: height/2; axis.z: 1 }
    ]

    Component.onCompleted: {
        // Start open animation and focus
        openAnim.restart()
        raise()
        requestActivate()
    }

    // Close warning (timer running or unsaved changes)
    Popup {
        id: closeWarn
        anchors.centerIn: parent
        width: 520
        height: 260
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.NoAutoClose

        background: Rectangle {
            color: panel2Color
            radius: 16
            border.width: 2
            border.color: accentColor
            layer.enabled: true
            layer.effect: DropShadow {
                transparentBorder: true
                color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.35)
                radius: 22
                samples: 44
                opacity: 0.8
            }
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Text {
                text: "UNSAVED OR RUNNING"
                color: textColor
                font.pixelSize: 18
                font.weight: Font.Bold
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: "This window has a running timer or unsaved changes.\nWhat do you want to do?"
                color: textColor
                opacity: 0.92
                font.pixelSize: 14
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                PillButton {
                    t: floatWin.t
                    text: "Cancel"
                    primary: false
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 44
                    onClicked: closeWarn.close()
                }

                PillButton {
                    t: floatWin.t
                    text: "Close anyway"
                    primary: true
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 44
                    onClicked: {
                        closeWarn.close()
                        _bypassCloseWarn = true
                        _startExitCloseAnimation()
                    }
                }

                PillButton {
                    t: floatWin.t
                    text: "Return to dock"
                    primary: true
                    Layout.preferredWidth: 170
                    Layout.preferredHeight: 44
                    onClicked: {
                        closeWarn.close()
                        _startDockReturn()
                    }
                }
            }
        }
    }
}

'@

Write-Utf8NoBom (Join-Path $root 'src\qml\Main.qml') $mainQml
Write-Utf8NoBom (Join-Path $root 'src\qml\views\TimeDocketView.qml') $timeViewQml
Write-Utf8NoBom (Join-Path $root 'src\qml\windows\FloatingDocketWindow.qml') $floatingQml

Write-Host "[PATCH] Wrote updated QML files." -ForegroundColor Green

# Quick sanity check: ensure key tokens exist
$mainText = Get-Content -Raw (Join-Path $root 'src\qml\Main.qml')
if ($mainText -notmatch 'floatingWindows') { throw "Sanity check failed: Main.qml missing floatingWindows" }
if ($mainText -notmatch 'detachSequence') { throw "Sanity check failed: Main.qml missing detachSequence" }

Write-Host "[PATCH] Sanity checks OK." -ForegroundColor Green

# Run the app
$py = Get-PythonExe $root
Write-Host "[RUN] Using python: $py" -ForegroundColor Cyan
Write-Host "[RUN] Starting app... QML warnings will be prefixed (QTWARN/QTCRIT) by the existing message handler." -ForegroundColor Cyan

Push-Location $root
try {
    & $py 'src\python\main.py'
} finally {
    Pop-Location
}
