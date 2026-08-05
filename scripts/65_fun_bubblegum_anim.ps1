# scripts\65_fun_bubblegum_anim.ps1
# Forward-only (PySide6/QML):
# - Rounded corners + rounded glow (no pointy taper) using RectangularGlow
# - Faux titlebar: inset title text; borderless – and ✕
# - Real large tiles with icons
# - Fun “bubblegum” open/close + minimize-to-taskbar-edge animation
# - Entire window animates as one object (chrome+glow+content together)
# - Exposes app.launchPoint from backend for bubble origin at cursor

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

function Patch-AppControllerForLaunchPoint {
    param([string]$Path, [string]$BackupRoot)

    Backup-File -Path $Path -BackupRoot $BackupRoot
    $txt = Get-Content -LiteralPath $Path -Raw -Encoding UTF8

    if ($txt -notmatch '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+QCursor\s*$') {
        $rx = [regex]'(?m)^\s*from\s+PySide6\.QtCore\s+import\s+.*$'
        $m = $rx.Match($txt)
        if ($m.Success) {
            $txt = $txt.Insert($m.Index + $m.Length, "`nfrom PySide6.QtGui import QCursor")
        } else {
            $txt = "from PySide6.QtGui import QCursor`n" + $txt
        }
    }

    if ($txt -notmatch '(?m)self\._launch_point\s*=') {
        $rxInit = [regex]'(?ms)def\s+__init__\s*\(self,\s*paths:\s*AppPaths\s*\)\s*:\s*\n'
        $m2 = $rxInit.Match($txt)
        if (-not $m2.Success) { throw "Could not locate AppController.__init__ signature." }
        $txt = $txt.Insert($m2.Index + $m2.Length, "        self._launch_point = QCursor.pos()`n")
    }

    if ($txt -notmatch '(?m)def\s+launchPoint\s*\(') {
        $rxAnchor = [regex]'(?ms)@Property\("QStringList",\s*constant=True\)\s*\n\s*def\s+themeNames\s*\(self\)\s*:\s*\n\s*return\s+.*?\n'
        $m3 = $rxAnchor.Match($txt)

        $propBlock = @"
    @Property("QVariantMap", constant=True)
    def launchPoint(self):
        p = self._launch_point
        return {"x": int(p.x()), "y": int(p.y())}

"@
        if ($m3.Success) {
            $txt = $txt.Insert($m3.Index + $m3.Length, "`n" + $propBlock)
        } else {
            $txt += "`n" + $propBlock
        }
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $txt, $utf8NoBom)

    Write-Host "PATCHED: src\python\backend\app_controller.py (launchPoint)" -ForegroundColor Green
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
Write-Host "ProjectRoot: $root" -ForegroundColor Cyan

$backupRoot = Join-Path $root "scripts\_patch_backups\65_fun_bubblegum_anim"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
$chromeSurfacePath = Join-Path $root "src\qml\components\ChromeSurface.qml"
$titleBarBtnPath = Join-Path $root "src\qml\components\TitleBarButton.qml"
$tileCardPath = Join-Path $root "src\qml\components\TileCard.qml"
$themePickerPath = Join-Path $root "src\qml\components\ThemePicker.qml"
$iconsDir = Join-Path $root "src\qml\assets\icons"
$appControllerPath = Join-Path $root "src\python\backend\app_controller.py"

if (-not (Test-Path -LiteralPath $mainQmlPath)) { throw "Missing: $mainQmlPath" }
if (-not (Test-Path -LiteralPath $themePickerPath)) { throw "Missing: $themePickerPath" }
if (-not (Test-Path -LiteralPath $appControllerPath)) { throw "Missing: $appControllerPath" }

# 1) ChromeSurface: rounded panel + rounded glow (RectangularGlow) + clip
Ensure-Dir -Path (Split-Path -Parent $chromeSurfacePath)
Backup-File -Path $chromeSurfacePath -BackupRoot $backupRoot

$chromeSurface = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property var t

    property real cornerRadius: 30
    property real padding: 14

    property real glowRadius: 26
    property real glowOpacity: 0.38

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

# 2) TitleBarButton: borderless glyph button
Ensure-Dir -Path (Split-Path -Parent $titleBarBtnPath)
Backup-File -Path $titleBarBtnPath -BackupRoot $backupRoot

$titleBarBtn = @"
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var t
    property string text: ""
    property int fontSize: 16
    property color hoverColor: root.t ? root.t.hover : "#E040FB"
    property color normalColor: root.t ? root.t.text : "white"
    signal clicked()

    width: 46
    height: 30

    Text {
        anchors.centerIn: parent
        text: root.text
        color: area.containsMouse ? root.hoverColor : root.normalColor
        font.pixelSize: root.fontSize
        font.weight: Font.DemiBold
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
"@

Write-Utf8NoBom -Path $titleBarBtnPath -Content $titleBarBtn
Write-Host "WROTE: src\qml\components\TitleBarButton.qml" -ForegroundColor Green

# 3) Icons (SVG) – create if absent
Ensure-Dir -Path $iconsDir

function Write-IconSvg {
    param([string]$Name, [string]$Svg)
    $p = Join-Path $iconsDir $Name
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Utf8NoBom -Path $p -Content $Svg
        Write-Host "WROTE: src\qml\assets\icons\$Name" -ForegroundColor Green
    }
}

$svgHeader = '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
$svgFooter = '</svg>'

Write-IconSvg "time.svg" @"
$svgHeader
<circle cx="64" cy="64" r="44" fill="none" stroke="#D500F9" stroke-width="8"/>
<path d="M64 36v32l20 12" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
$svgFooter
"@

Write-IconSvg "clients.svg" @"
$svgHeader
<circle cx="50" cy="54" r="16" fill="none" stroke="#D500F9" stroke-width="8"/>
<circle cx="84" cy="62" r="12" fill="none" stroke="#D500F9" stroke-width="8"/>
<path d="M24 98c6-16 20-26 36-26s30 10 36 26" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

Write-IconSvg "reports.svg" @"
$svgHeader
<path d="M28 92V36" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M28 92h72" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M40 82l16-18 14 10 22-28" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
$svgFooter
"@

Write-IconSvg "invoices.svg" @"
$svgHeader
<path d="M40 24h40l12 12v68H40z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M80 24v16h16" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M52 62h36M52 76h28" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

Write-IconSvg "ticklers.svg" @"
$svgHeader
<path d="M64 28c20 0 36 16 36 36 0 22-18 30-36 48-18-18-36-26-36-48 0-20 16-36 36-36z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M64 54v18" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M64 84h.01" stroke="#D500F9" stroke-width="10" stroke-linecap="round"/>
$svgFooter
"@

Write-IconSvg "tax.svg" @"
$svgHeader
<path d="M36 44h56v60H36z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M48 44V28h32v16" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M48 72h32M48 86h26" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

# 4) TileCard: BIG tile w/ icon + label
Ensure-Dir -Path (Split-Path -Parent $tileCardPath)
Backup-File -Path $tileCardPath -BackupRoot $backupRoot

$tileCard = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property url iconSource: ""
    property bool primary: false

    height: 220
    font.pixelSize: 17
    font.weight: Font.DemiBold

    background: Rectangle {
        id: bg
        radius: 30
        color: Qt.rgba(0,0,0,0.18)
        border.width: 2
        border.color: b.primary ? "transparent" : b.t.accent
    }

    RectangularGlow {
        anchors.fill: bg
        glowRadius: 20
        spread: 0.22
        color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.primary ? 0.45 : 0.24)
        cornerRadius: bg.radius + glowRadius
    }

    contentItem: Column {
        anchors.centerIn: parent
        spacing: 12

        Image {
            width: 74
            height: 74
            source: b.iconSource
            fillMode: Image.PreserveAspectFit
            smooth: true
            opacity: 0.98
        }

        Text {
            text: b.text
            color: b.t.text
            horizontalAlignment: Text.AlignHCenter
            width: b.width - 28
            wrapMode: Text.WordWrap
        }
    }
}
"@

Write-Utf8NoBom -Path $tileCardPath -Content $tileCard
Write-Host "WROTE: src\qml\components\TileCard.qml" -ForegroundColor Green

# 5) Patch backend for app.launchPoint (cursor at launch)
Patch-AppControllerForLaunchPoint -Path $appControllerPath -BackupRoot $backupRoot

# 6) Main.qml: unified fun animations + minimize-to-taskbar-edge
Backup-File -Path $mainQmlPath -BackupRoot $backupRoot

$mainQml = @"
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "components"

ApplicationWindow {
    id: win
    visible: true
    width: 1080
    height: 800
    title: "CSPM - Practice Management"

    // Frameless + always on top
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

    // State
    property bool animating: false
    property bool closing: false

    // Store “restored” position so minimize animation can return you to center
    property real restoreX: 0
    property real restoreY: 0

    // Bubble origin (in window coords)
    property point originPt: Qt.point(width/2, height/2)

    // Screen work area (above taskbar)
    property rect workArea: win.screen ? win.screen.availableGeometry : Qt.rect(0,0,Screen.width,Screen.height)

    function centerWindow() {
        var ax = workArea.x + (workArea.width - win.width) / 2
        var ay = workArea.y + (workArea.height - win.height) / 2
        win.x = Math.round(ax)
        win.y = Math.round(ay)
    }

    function computeOriginFromCursor() {
        if (!appRef || !appRef.launchPoint) {
            return Qt.point(win.width/2, win.height/2)
        }
        // Use contentItem mapping to avoid mapFromGlobal errors
        return win.contentItem.mapFromGlobal(appRef.launchPoint.x, appRef.launchPoint.y)
    }

    function focusTop() {
        win.raise()
        win.requestActivate()
    }

    function openBubblegum() {
        if (animating) {
            return
        }
        animating = true
        focusTop()
        centerWindow()

        originPt = computeOriginFromCursor()
        bubbleScale.origin.x = originPt.x
        bubbleScale.origin.y = originPt.y
        bubbleRot.origin.x = originPt.x
        bubbleRot.origin.y = originPt.y

        bubble.opacity = 0.0
        bubbleScale.xScale = 0.06
        bubbleScale.yScale = 0.06
        bubbleRot.angle = 0
        bubbleTranslate.x = 0
        bubbleTranslate.y = 0

        winBumpX.from = win.x
        winBumpY.from = win.y
        openAnim.restart()
    }

    function closeBubblegum() {
        if (closing || animating) {
            return
        }
        closing = true
        animating = true
        focusTop()

        originPt = Qt.point(win.width/2, win.height/2)
        bubbleScale.origin.x = originPt.x
        bubbleScale.origin.y = originPt.y
        bubbleRot.origin.x = originPt.x
        bubbleRot.origin.y = originPt.y

        closeAnim.restart()
    }

    function minimizeBubblegum() {
        if (animating) {
            return
        }
        animating = true
        focusTop()

        restoreX = win.x
        restoreY = win.y

        // Target: bottom-center of work area (simulates “to taskbar”)
        var targetCenterX = workArea.x + workArea.width / 2
        var targetBottomY = workArea.y + workArea.height - 8

        minWinX.to = Math.round(targetCenterX - win.width / 2)
        minWinY.to = Math.round(targetBottomY - win.height)

        // Shrink toward bottom center
        bubbleScale.origin.x = win.width / 2
        bubbleScale.origin.y = win.height
        bubbleRot.origin.x = win.width / 2
        bubbleRot.origin.y = win.height

        minimizeAnim.restart()
    }

    // Restore from taskbar: run open from cursor (cursor likely on taskbar icon)
    onVisibilityChanged: {
        if (win.visibility === Window.Windowed && !closing) {
            focusTop()
        }
    }

    Component.onCompleted: {
        focusTop()
        centerWindow()
        openBubblegum()
    }

    // Animate EVERYTHING as one object
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

                // Faux Windows titlebar (standalone; inset title)
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    color: Qt.rgba(0,0,0,0.0)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 22
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

                        TitleBarButton { t: win.t; text: "–"; fontSize: 18; onClicked: win.minimizeBubblegum() }
                        TitleBarButton { t: win.t; text: "✕"; fontSize: 16; hoverColor: "#FF5252"; onClicked: win.closeBubblegum() }
                    }
                }

                // Toolbar row
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

                    PillButton { t: win.t; primary: false; text: "Backup"; onClicked: { if (appRef) appRef.backupWorkbook() } }
                    PillButton { t: win.t; primary: false; text: "Dump Workspace"; onClicked: { if (appRef) appRef.dumpWorkspace() } }
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

                            // MENU
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

                                        TileCard { t: win.t; primary: true; text: "Enter Time"; iconSource: "assets/icons/time.svg"; Layout.fillWidth: true; onClicked: chrome.pageIndex = 1 }
                                        TileCard { t: win.t; text: "Clients (Soon)"; iconSource: "assets/icons/clients.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Reports (Soon)"; iconSource: "assets/icons/reports.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Invoices (Soon)"; iconSource: "assets/icons/invoices.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "Ticklers (Soon)"; iconSource: "assets/icons/ticklers.svg"; Layout.fillWidth: true }
                                        TileCard { t: win.t; text: "HST/Tax (Soon)"; iconSource: "assets/icons/tax.svg"; Layout.fillWidth: true }
                                    }
                                }
                            }

                            // TIME ENTRY (handlers use formal params)
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
                        }
                    }
                }
            }
        }
    }

    // ---- OPEN: bubble-gum blow + wobble + settle ----
    SequentialAnimation {
        id: openAnim
        running: false

        ScriptAction { script: {} }

        ParallelAnimation {
            PropertyAnimation { target: bubble; property: "opacity"; from: 0.0; to: 1.0; duration: 150; easing.type: Easing.OutCubic }

            // Big bouncy inflate
            PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.05; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 0.95; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.35 }

            // Wobble rotation
            SequentialAnimation {
                PropertyAnimation { target: bubbleRot; property: "angle"; from: 0; to: -4; duration: 140; easing.type: Easing.OutCubic }
                PropertyAnimation { target: bubbleRot; property: "angle"; to: 3; duration: 160; easing.type: Easing.OutCubic }
                PropertyAnimation { target: bubbleRot; property: "angle"; to: -2; duration: 120; easing.type: Easing.OutCubic }
                PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 120; easing.type: Easing.OutCubic }
            }

            // Window “bounce settle” (small position wiggle)
            SequentialAnimation {
                PropertyAnimation { id: winBumpX; target: win; property: "x"; to: win.x + 10; duration: 120; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "x"; to: win.x - 6; duration: 120; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "x"; to: win.x + 3; duration: 100; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "x"; to: win.x; duration: 80; easing.type: Easing.OutCubic }
            }
            SequentialAnimation {
                PropertyAnimation { id: winBumpY; target: win; property: "y"; to: win.y + 8; duration: 120; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "y"; to: win.y - 6; duration: 120; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "y"; to: win.y + 2; duration: 100; easing.type: Easing.OutCubic }
                PropertyAnimation { target: win; property: "y"; to: win.y; duration: 80; easing.type: Easing.OutCubic }
            }
        }

        // Snap to perfect scale at end
        ParallelAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 1.0; duration: 140; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 1.0; duration: 140; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
        }

        onStopped: {
            animating = false
        }
    }

    // ---- MINIMIZE: bounce down + shrink to taskbar edge, then minimize ----
    SequentialAnimation {
        id: minimizeAnim
        running: false

        ParallelAnimation {
            PropertyAnimation { target: win; property: "y"; to: win.y + 14; duration: 120; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: -2; duration: 120; easing.type: Easing.OutCubic }
        }

        ParallelAnimation {
            PropertyAnimation { target: win; property: "y"; to: win.y; duration: 120; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 120; easing.type: Easing.OutCubic }
        }

        ParallelAnimation {
            PropertyAnimation { id: minWinX; target: win; property: "x"; duration: 260; easing.type: Easing.InCubic }
            PropertyAnimation { id: minWinY; target: win; property: "y"; duration: 260; easing.type: Easing.InCubic }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.06; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.06; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.2 }
            PropertyAnimation { target: bubble; property: "opacity"; to: 0.0; duration: 220; easing.type: Easing.InCubic }
        }

        ScriptAction {
            script: {
                win.showMinimized()
                // restore location so when user restores it's centered again
                win.x = restoreX
                win.y = restoreY
                bubbleScale.xScale = 1.0
                bubbleScale.yScale = 1.0
                bubble.opacity = 1.0
                animating = false
            }
        }
    }

    // ---- CLOSE: bounce, deflate, then shoot off-screen ----
    SequentialAnimation {
        id: closeAnim
        running: false

        // A couple playful bounces
        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 6; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: 14; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: -10; duration: 140; easing.type: Easing.OutCubic }
        }
        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: -5; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: -10; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 8; duration: 140; easing.type: Easing.OutCubic }
        }
        ParallelAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 120; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: 0; duration: 120; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: 0; duration: 120; easing.type: Easing.OutCubic }
        }

        // Deflate
        ParallelAnimation {
            PropertyAnimation { target: bubble; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.InCubic }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.10; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.08; duration: 220; easing.type: Easing.InBack; easing.overshoot: 1.15 }
        }

        // Shoot off-screen (window moves so whole object flies away)
        ScriptAction {
            script: {
                // choose up-right off screen
                var ax = workArea.x + workArea.width + 400
                var ay = workArea.y - 400
                win.x = Math.round(ax)
                win.y = Math.round(ay)
            }
        }

        ScriptAction { script: win.close() }
    }
}
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (fun open/close/minimize animations + true tiles)" -ForegroundColor Green

Write-Host "`nDONE. Re-run your app." -ForegroundColor Cyan
Write-Host "Backups saved in: $backupRoot" -ForegroundColor DarkGray