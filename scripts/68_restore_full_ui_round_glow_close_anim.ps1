# scripts\68_restore_full_ui_round_glow_close_anim.ps1
# Forward-only fix:
# - Restore full Main.qml UI (tabs + tiles + pages)
# - Improve rounded corners + glow (no square glow corners)
# - Inset title text
# - Add proper close animation (intercept onClosing)
# - Keep bubble-gum open animation (window + chrome + glow move together)

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Backup-File {
    param([string]$Path, [string]$BackupRoot)
    if (Test-Path -LiteralPath $Path) {
        Ensure-Dir -Path $BackupRoot
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $name = Split-Path -Leaf $Path
        $dest = Join-Path $BackupRoot ($stamp + "_" + $name)
        Copy-Item -LiteralPath $Path -Destination $dest -Force
        Write-Host "BACKUP: $Path -> $dest" -ForegroundColor DarkGray
    }
}

function Resolve-ProjectRoot {
    param([string]$MaybeRoot)

    if ($MaybeRoot -and $MaybeRoot.Trim() -ne "") {
        return (Resolve-Path -LiteralPath $MaybeRoot).Path
    }

    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

    $candidate = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\Main.qml")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\Main.qml")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM (must contain src\qml\Main.qml)."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
Write-Host "ProjectRoot: $root" -ForegroundColor Cyan

$backupRoot = Join-Path $root "scripts\_patch_backups\68_restore_full_ui"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
$chromeSurfacePath = Join-Path $root "src\qml\components\ChromeSurface.qml"

if (-not (Test-Path -LiteralPath $mainQmlPath)) { throw "Missing: $mainQmlPath" }

# -----------------------------
# 1) Update ChromeSurface.qml (better rounding + glow)
# -----------------------------
Ensure-Dir -Path (Split-Path -Parent $chromeSurfacePath)
Backup-File -Path $chromeSurfacePath -BackupRoot $backupRoot

$chromeSurface = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property var t

    // Bigger rounding so it reads as truly rounded
    property real cornerRadius: 36
    property real padding: 14

    // Glow tuning
    property real glowRadius: 30
    property real glowOpacity: 0.40

    property color accentColor: root.t ? root.t.accent : "#D500F9"
    property color glowColor: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, glowOpacity)

    default property alias content: contentHost.data
    anchors.fill: parent

    Rectangle {
        id: panel
        anchors.fill: parent
        anchors.margins: root.padding
        radius: root.cornerRadius
        color: root.t ? root.t.panel2 : "#1A1024"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.10)
        clip: true
        z: 2
    }

    // Rounded glow that follows the rounded rectangle (no “square” corner feel)
    RectangularGlow {
        anchors.fill: panel
        glowRadius: root.glowRadius
        spread: 0.20
        color: root.glowColor
        cornerRadius: panel.radius + glowRadius
        z: 1
    }

    Item {
        id: contentHost
        anchors.fill: panel
        z: 3
    }
}
"@

Write-Utf8NoBom -Path $chromeSurfacePath -Content $chromeSurface
Write-Host "WROTE: src\qml\components\ChromeSurface.qml" -ForegroundColor Green

# -----------------------------
# 2) Restore Main.qml full UI + close animation intercept
# -----------------------------
Backup-File -Path $mainQmlPath -BackupRoot $backupRoot

$mainQml = @"
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "components"

ApplicationWindow {
    id: win

    // Prevent top-left flash: show only after positioning in open routine
    visible: false

    width: 1080
    height: 800
    title: "CSPM - Practice Management"

    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    property var appRef: (typeof app !== "undefined" && app !== null) ? app : null
    property var fallbackTheme: ({
        "bg": "#000000",
        "panel": "#120A18",
        "panel2": "#1A1024",
        "accent": "#D500F9",
        "hover": "#E040FB",
        "text": "#FFFFFF",
        "muted": "#C9B6D6",
        "btn_text": "black"
    })
    property var t: appRef ? appRef.theme : fallbackTheme

    // Center target on “monitor 0” (last click monitor) if available
    property rect workArea: win.screen ? win.screen.availableGeometry : Qt.rect(0, 0, Screen.width, Screen.height)

    property bool animating: false
    property bool closing: false
    property bool forceClose: false

    // Open origin point inside the window (bubble origin)
    property point originPt: Qt.point(width/2, height/2)

    // Dest position for landing (center of monitor0)
    property int targetX: 0
    property int targetY: 0

    function focusTop() {
        win.raise()
        win.requestActivate()
    }

    function computeMonitor0Target() {
        var a = (appRef && appRef.monitor0) ? appRef.monitor0.available : null
        if (!a) {
            a = { "x": workArea.x, "y": workArea.y, "w": workArea.width, "h": workArea.height }
        }
        targetX = Math.round(a.x + (a.w - win.width) / 2)
        targetY = Math.round(a.y + (a.h - win.height) / 2)
    }

    function openFromLastClick() {
        if (animating) {
            return
        }
        animating = true
        closing = false
        forceClose = false

        // get last click global (fallback to cursor via backend getter)
        var lc = (appRef && appRef.lastClick) ? appRef.lastClick : { "x": targetX, "y": targetY }
        computeMonitor0Target()

        // Start window centered on click point (so bubble originates from click)
        win.x = Math.round(lc.x - win.width / 2)
        win.y = Math.round(lc.y - win.height / 2)

        win.visible = true
        focusTop()

        // Bubble origin in window coords
        originPt = Qt.point(lc.x - win.x, lc.y - win.y)
        bubbleScale.origin.x = originPt.x
        bubbleScale.origin.y = originPt.y
        bubbleRot.origin.x = originPt.x
        bubbleRot.origin.y = originPt.y

        // Reset bubble transforms
        bubble.opacity = 0.0
        bubbleTranslate.x = 0
        bubbleTranslate.y = 0
        bubbleRot.angle = 0
        bubbleScale.xScale = 0.06
        bubbleScale.yScale = 0.06

        openAnim.restart()
    }

    function requestCloseAnimated() {
        if (closing) {
            return
        }
        closing = true
        animating = true

        // Use center for close “wobble/deflate”
        bubbleScale.origin.x = win.width / 2
        bubbleScale.origin.y = win.height / 2
        bubbleRot.origin.x = win.width / 2
        bubbleRot.origin.y = win.height / 2

        closeAnim.restart()
    }

    // Intercept OS/window close (Alt+F4 etc.)
    onClosing: function(close) {
        if (forceClose) {
            close.accepted = true
            return
        }
        close.accepted = false
        requestCloseAnimated()
    }

    Component.onCompleted: {
        focusTop()
        openFromLastClick()
    }

    // Click catcher: update monitor0 dynamically for later opens
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        propagateComposedEvents: true

        onPressed: function(mouse) {
            var gp = win.contentItem.mapToGlobal(mouse.x, mouse.y)
            if (appRef) {
                appRef.setLastClick(Math.round(gp.x), Math.round(gp.y))
            }
            mouse.accepted = false
        }
    }

    // Whole “bubble” contains ChromeSurface + everything, so it animates together.
    Item {
        id: bubble
        anchors.fill: parent
        opacity: 1.0

        transform: [
            Translate { id: bubbleTranslate; x: 0; y: 0 },
            Rotation { id: bubbleRot; origin.x: win.width/2; origin.y: win.height/2; angle: 0 },
            Scale { id: bubbleScale; origin.x: win.width/2; origin.y: win.height/2; xScale: 1.0; yScale: 1.0 }
        ]

        ChromeSurface {
            id: chrome
            anchors.fill: parent
            t: win.t

            property int pageIndex: 0

            ThemePicker {
                id: themePicker
                t: win.t
                names: appRef ? appRef.themeNames : []
                onPicked: { if (appRef) appRef.setTheme(name) }
            }

            Toast {
                id: toast
                t: win.t
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 10
            }

            Connections {
                target: appRef
                ignoreUnknownSignals: true
                function onToast(msg) { toast.show(msg) }
                function onError(msg) { toast.show(msg) }
                function onThemeChanged() { win.t = appRef ? appRef.theme : fallbackTheme }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                // Faux Windows titlebar row (standalone)
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    color: Qt.rgba(0,0,0,0.0)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 36    // << moved inward more
                        anchors.rightMargin: 10
                        spacing: 8

                        Item {
                            Layout.fillWidth: true
                            height: parent.height

                            DragHandler {
                                target: null
                                onActiveChanged: if (active) win.startSystemMove()
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Practice Console"
                                color: t.text
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                            }
                        }

                        TitleBarButton {
                            t: win.t
                            text: "–"
                            fontSize: 18
                            onClicked: win.showMinimized()
                        }

                        TitleBarButton {
                            t: win.t
                            text: "✕"
                            fontSize: 16
                            hoverColor: "#FF5252"
                            onClicked: win.requestCloseAnimated()
                        }
                    }
                }

                // Toolbar row (Theme/Backup/Dump)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 12
                    Layout.rightMargin: 12
                    Layout.topMargin: 6
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    PillButton {
                        t: win.t
                        primary: false
                        text: "Theme"
                        onClicked: {
                            themePicker.x = win.width - themePicker.width - 26
                            themePicker.y = 60
                            themePicker.open()
                        }
                    }

                    PillButton {
                        t: win.t
                        primary: false
                        text: "Backup"
                        onClicked: { if (appRef) appRef.backupWorkbook() }
                    }

                    PillButton {
                        t: win.t
                        primary: false
                        text: "Dump Workspace"
                        onClicked: { if (appRef) appRef.dumpWorkspace() }
                    }
                }

                // Main content
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 12
                    spacing: 10

                    SegmentedTabs {
                        t: win.t
                        index: chrome.pageIndex
                        onChanged: chrome.pageIndex = ix
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 18
                        color: t.panel2
                        border.width: 1
                        border.color: Qt.rgba(1,1,1,0.10)

                        StackLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            currentIndex: chrome.pageIndex

                            // PAGE 0: MENU (tiles)
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 18

                                    Text { text: "Main Menu"; color: t.text; font.pixelSize: 18; font.weight: Font.DemiBold }

                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 3
                                        columnSpacing: 20
                                        rowSpacing: 20

                                        TileCard {
                                            t: win.t
                                            primary: true
                                            text: "Enter Time"
                                            iconSource: "assets/icons/time.svg"
                                            Layout.fillWidth: true
                                            onClicked: chrome.pageIndex = 1
                                        }

                                        TileCard { t: win.t; text: "Clients (Soon)"; iconSource: "assets/icons/clients.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Reports (Soon)"; iconSource: "assets/icons/reports.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Invoices (Soon)"; iconSource: "assets/icons/invoices.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Ticklers (Soon)"; iconSource: "assets/icons/ticklers.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "HST/Tax (Soon)"; iconSource: "assets/icons/tax.svg"; Layout.fillWidth: true }
                                    }
                                }
                            }

                            // PAGE 1: TIME ENTRY
                            Item {
                                id: timePage

                                property string f_entryId: ""
                                property string f_date: ""
                                property string f_clientId: ""
                                property string f_matterId: ""
                                property string f_parentId: ""
                                property string f_desc: ""
                                property string f_hours: ""
                                property string f_rate: ""
                                property string f_cut: "0"

                                Component.onCompleted: {
                                    var d = new Date()
                                    var mm = String(d.getMonth()+1).padStart(2, "0")
                                    var dd = String(d.getDate()).padStart(2, "0")
                                    timePage.f_date = d.getFullYear() + "-" + mm + "-" + dd
                                }

                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 10

                                    Text { text: "Time Entry"; color: t.text; font.pixelSize: 18; font.weight: Font.DemiBold }

                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 2
                                        columnSpacing: 18
                                        rowSpacing: 10

                                        PillTextField { t: win.t; label: "Date"; text: timePage.f_date; onEdited: function(value) { timePage.f_date = value } }

                                        PillCombo {
                                            t: win.t
                                            label: "Client (ID or Name for now)"
                                            model: appRef ? appRef.clients : []
                                            value: timePage.f_clientId
                                            onChanged: function(value) { timePage.f_clientId = value; if (appRef) appRef.addClient(value) }
                                        }

                                        PillCombo {
                                            t: win.t
                                            label: "Matter (ID or Name for now)"
                                            model: appRef ? appRef.matters : []
                                            value: timePage.f_matterId
                                            onChanged: function(value) { timePage.f_matterId = value; if (appRef) appRef.addMatter(value) }
                                        }

                                        PillCombo {
                                            t: win.t
                                            label: "Parent (Payor/Referrer)"
                                            model: appRef ? appRef.parents : []
                                            value: timePage.f_parentId
                                            onChanged: function(value) { timePage.f_parentId = value; if (appRef) appRef.addParent(value) }
                                        }

                                        PillTextField { t: win.t; label: "Hours"; placeholderText: "e.g., 0.5"; text: timePage.f_hours; onEdited: function(value) { timePage.f_hours = value } }
                                        PillTextField { t: win.t; label: "Client Rate"; placeholderText: "e.g., 475"; text: timePage.f_rate; onEdited: function(value) { timePage.f_rate = value } }
                                        PillTextField { t: win.t; label: "Cut % (Parent)"; placeholderText: "e.g., 30"; text: timePage.f_cut; onEdited: function(value) { timePage.f_cut = value } }
                                        Item { }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        spacing: 4

                                        Text { text: "Description"; color: t.text; opacity: 0.9; font.pixelSize: 12 }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            radius: 16
                                            color: Qt.rgba(0,0,0,0.22)
                                            border.width: 2
                                            border.color: Qt.rgba(1,1,1,0.18)

                                            TextArea {
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                text: timePage.f_desc
                                                background: null
                                                color: t.text
                                                wrapMode: TextArea.Wrap
                                                onTextChanged: timePage.f_desc = text
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 14

                                        PillButton {
                                            t: win.t
                                            primary: true
                                            text: "SAVE TIME ENTRY"
                                            Layout.fillWidth: true
                                            onClicked: {
                                                var payload = {
                                                    "EntryID": timePage.f_entryId,
                                                    "Date": timePage.f_date,
                                                    "ClientID": timePage.f_clientId,
                                                    "MatterID": timePage.f_matterId,
                                                    "ParentID": timePage.f_parentId,
                                                    "Description": timePage.f_desc,
                                                    "Hours": timePage.f_hours,
                                                    "ClientRate": timePage.f_rate,
                                                    "CutPct": timePage.f_cut,
                                                    "RawSeconds": appRef && appRef.elapsedSeconds ? Math.floor(appRef.elapsedSeconds) : 0,
                                                    "Status": "WIP"
                                                }
                                                if (appRef) appRef.saveTimeEntry(payload)
                                            }
                                        }

                                        PillButton { t: win.t; primary: false; text: "Back to Menu"; Layout.fillWidth: true; onClicked: chrome.pageIndex = 0 }
                                    }
                                }
                            }

                            // PAGE 2: SETTINGS
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 10
                                    Text { text: "Settings (coming soon)"; color: t.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                                    Text { text: "• animation styles\n• fade-in/out presets\n• global UI preferences"; color: t.muted }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // OPEN animation: bubble inflate + move window to monitor0 center
    ParallelAnimation {
        id: openAnim

        // Bubble inflate + wobble
        SequentialAnimation { PropertyAnimation { target: bubble; property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic } }

        SequentialAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.10; duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 1.0; duration: 140; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
        }

        SequentialAnimation {
            PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 0.92; duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 1.0; duration: 140; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
        }

        SequentialAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; from: 0; to: -6; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 5; duration: 170; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: -3; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 140; easing.type: Easing.OutCubic }
        }

        // Land centered on monitor0
        PropertyAnimation { target: win; property: "x"; to: targetX; duration: 640; easing.type: Easing.OutBack; easing.overshoot: 1.20 }
        PropertyAnimation { target: win; property: "y"; to: targetY; duration: 640; easing.type: Easing.OutBack; easing.overshoot: 1.20 }

        onStopped: {
            animating = false
            focusTop()
        }
    }

    // CLOSE animation: bounce -> deflate -> shoot off-screen -> force-close
    SequentialAnimation {
        id: closeAnim

        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 7; duration: 130; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: 14; duration: 130; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: -10; duration: 130; easing.type: Easing.OutCubic }
        }

        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: -6; duration: 130; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: -10; duration: 130; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 8; duration: 130; easing.type: Easing.OutCubic }
        }

        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 110; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: 0; duration: 110; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 0; duration: 110; easing.type: Easing.OutCubic }
        }

        ParallelAnimation {
            PropertyAnimation { target: bubble; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.InCubic }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.08; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.06; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
        }

        ScriptAction {
            script: {
                // allow closing now
                win.forceClose = true
                win.close()
            }
        }

        onStopped: {
            animating = false
        }
    }
}
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (full UI restored + close animation + inset title)" -ForegroundColor Green

Write-Host "`nDONE. Backups in: $backupRoot" -ForegroundColor Cyan