# scripts\64_ui_round_glow_tiles_anim.ps1
# Forward-only (PySide6/QML): true rounded glow perimeter, inset title text,
# real large icon tiles, and bubble open + balloon close where EVERYTHING moves together.
# Creates backups under scripts\_patch_backups\ui_round_glow_tiles_anim\

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
    if (-not $scriptDir) {
        $scriptDir = (Get-Location).Path
    }

    $candidate = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\Main.qml")) {
        return $candidate
    }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\Main.qml")) {
        return $cwd
    }

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
            $insertPos = $m.Index + $m.Length
            $txt = $txt.Insert($insertPos, "`nfrom PySide6.QtGui import QCursor")
        } else {
            $txt = "from PySide6.QtGui import QCursor`n" + $txt
        }
    }

    if ($txt -notmatch '(?m)self\._launch_point\s*=') {
        $rxInit = [regex]'(?ms)def\s+__init__\s*\(self,\s*paths:\s*AppPaths\s*\)\s*:\s*\n'
        $m2 = $rxInit.Match($txt)
        if (-not $m2.Success) {
            throw "Could not locate AppController.__init__ signature."
        }
        $insertPos2 = $m2.Index + $m2.Length
        $txt = $txt.Insert($insertPos2, "        self._launch_point = QCursor.pos()`n")
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
            $insertPos3 = $m3.Index + $m3.Length
            $txt = $txt.Insert($insertPos3, "`n" + $propBlock)
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

$backupRoot = Join-Path $root "scripts\_patch_backups\ui_round_glow_tiles_anim"
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

# 1) ChromeSurface with RectangularGlow (prevents pointy-taper corner look)
Ensure-Dir -Path (Split-Path -Parent $chromeSurfacePath)
Backup-File -Path $chromeSurfacePath -BackupRoot $backupRoot

$chromeSurface = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property var t

    property real cornerRadius: 28
    property real padding: 14

    // Glow controls
    property real glowRadius: 22
    property real glowOpacity: 0.38

    property color accentColor: root.t ? root.t.accent : "#D500F9"
    property color glowColor: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, glowOpacity)

    default property alias content: contentHost.data
    anchors.fill: parent

    // Rounded panel surface (clips children)
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

    // Rounded glow that follows corners (no pointy taper)
    RectangularGlow {
        anchors.fill: panel
        glowRadius: root.glowRadius
        spread: 0.18
        color: root.glowColor
        cornerRadius: panel.radius + glowRadius
        z: 1
    }

    // Very subtle soft shadow to add depth (optional)
    DropShadow {
        anchors.fill: panel
        source: panel
        radius: 14
        samples: 17
        horizontalOffset: 0
        verticalOffset: 3
        color: Qt.rgba(0, 0, 0, 0.35)
        transparentBorder: true
        z: 0
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

# 2) TitleBarButton (borderless glyph with hover only)
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

    width: 44
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

# 3) Create icons (simple SVGs) for tiles
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

# Clock
Write-IconSvg -Name "time.svg" -Svg @"
$svgHeader
<circle cx="64" cy="64" r="44" fill="none" stroke="#D500F9" stroke-width="8"/>
<path d="M64 36v32l20 12" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
$svgFooter
"@

# Clients
Write-IconSvg -Name "clients.svg" -Svg @"
$svgHeader
<circle cx="50" cy="54" r="16" fill="none" stroke="#D500F9" stroke-width="8"/>
<circle cx="84" cy="62" r="12" fill="none" stroke="#D500F9" stroke-width="8"/>
<path d="M24 98c6-16 20-26 36-26s30 10 36 26" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

# Reports
Write-IconSvg -Name "reports.svg" -Svg @"
$svgHeader
<path d="M28 92V36" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M28 92h72" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M40 82l16-18 14 10 22-28" fill="none" stroke="#D500F9" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
$svgFooter
"@

# Invoices
Write-IconSvg -Name "invoices.svg" -Svg @"
$svgHeader
<path d="M40 24h40l12 12v68H40z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M80 24v16h16" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M52 62h36M52 76h28" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

# Ticklers
Write-IconSvg -Name "ticklers.svg" -Svg @"
$svgHeader
<path d="M64 28c20 0 36 16 36 36 0 22-18 30-36 48-18-18-36-26-36-48 0-20 16-36 36-36z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M64 54v18" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
<path d="M64 84h.01" stroke="#D500F9" stroke-width="10" stroke-linecap="round"/>
$svgFooter
"@

# HST/Tax
Write-IconSvg -Name "tax.svg" -Svg @"
$svgHeader
<path d="M36 44h56v60H36z" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M48 44V28h32v16" fill="none" stroke="#D500F9" stroke-width="8" stroke-linejoin="round"/>
<path d="M48 72h32M48 86h26" stroke="#D500F9" stroke-width="8" stroke-linecap="round"/>
$svgFooter
"@

# 4) TileCard component (image + label, real tile)
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

    height: 180
    font.pixelSize: 16
    font.weight: Font.DemiBold

    background: Rectangle {
        id: bg
        radius: 26
        color: Qt.rgba(0,0,0,0.18)
        border.width: 2
        border.color: b.primary ? "transparent" : b.t.accent
    }

    RectangularGlow {
        anchors.fill: bg
        glowRadius: 18
        spread: 0.20
        color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.primary ? 0.35 : 0.22)
        cornerRadius: bg.radius + glowRadius
    }

    contentItem: Column {
        anchors.centerIn: parent
        spacing: 10

        Image {
            width: 64
            height: 64
            source: b.iconSource
            fillMode: Image.PreserveAspectFit
            smooth: true
            opacity: 0.95
        }

        Text {
            text: b.text
            color: b.t.text
            horizontalAlignment: Text.AlignHCenter
            width: b.width - 24
            wrapMode: Text.WordWrap
        }
    }
}
"@

Write-Utf8NoBom -Path $tileCardPath -Content $tileCard
Write-Host "WROTE: src\qml\components\TileCard.qml" -ForegroundColor Green

# 5) ThemePicker stays as-is, but we keep it stable (no change unless you want it to match RectangularGlow)
# (Optional: you can later ask to glow it with RectangularGlow too.)

# 6) Patch Python backend: provide app.launchPoint (cursor pos at startup)
Patch-AppControllerForLaunchPoint -Path $appControllerPath -BackupRoot $backupRoot

# 7) Overwrite Main.qml: animate EVERYTHING (ChromeSurface included), inset title text, big icon tiles
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
    width: 1040
    height: 760
    title: "CSPM - Practice Management"

    // Frameless + always-on-top
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

    property bool closing: false
    property point launchLocal: Qt.point(width/2, height/2)

    function computeLaunchLocal() {
        if (!appRef || !appRef.launchPoint) {
            return Qt.point(win.width/2, win.height/2)
        }
        // Use contentItem mapping (avoids mapFromGlobal TypeError)
        var gx = appRef.launchPoint.x
        var gy = appRef.launchPoint.y
        return win.contentItem.mapFromGlobal(gx, gy)
    }

    function openAnimStart() {
        win.raise()
        win.requestActivate()

        launchLocal = computeLaunchLocal()

        bubble.opacity = 0.0
        bubbleScale.xScale = 0.06
        bubbleScale.yScale = 0.06
        bubbleTranslate.x = 0
        bubbleTranslate.y = 0
        openAnim.restart()
    }

    function closeAnimated() {
        if (closing) {
            return
        }
        closing = true
        closeAnim.restart()
    }

    Component.onCompleted: {
        openAnimStart()
    }

    // EVERYTHING is under bubble, so it all animates together (chrome + glow + content).
    Item {
        id: bubble
        anchors.fill: parent

        transform: [
            Translate { id: bubbleTranslate; x: 0; y: 0 },
            Scale {
                id: bubbleScale
                origin.x: win.launchLocal.x
                origin.y: win.launchLocal.y
                xScale: 1.0
                yScale: 1.0
            }
        ]

        ChromeSurface {
            id: chrome
            anchors.fill: parent
            t: win.t

            // NAV
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

                // Faux titlebar row (standalone, no borders)
                Rectangle {
                    Layout.fillWidth: true
                    height: 34
                    color: Qt.rgba(0,0,0,0.0)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18      // <-- INSET TITLE TEXT
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
                            onClicked: win.closeAnimated()
                        }
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
                            themePicker.y = 56
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

                            // PAGE 0: MENU
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 18

                                    Text {
                                        text: "Main Menu"
                                        color: t.text
                                        font.pixelSize: 18
                                        font.weight: Font.DemiBold
                                    }

                                    // TRUE LARGE ICON TILES
                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 3
                                        columnSpacing: 18
                                        rowSpacing: 18

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

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 16
                                        color: Qt.rgba(0,0,0,0.18)
                                        border.width: 1
                                        border.color: Qt.rgba(1,1,1,0.10)

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 8
                                            Text { text: "Status"; color: t.text; font.weight: Font.DemiBold }
                                            Text { text: "• Excel store: data/CSPM.xlsm"; color: t.muted }
                                            Text { text: "• Auto-schema bootstrap enabled"; color: t.muted }
                                            Text { text: "• Parent cut model supported in Time Entries (CutPct)"; color: t.muted }
                                        }
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

    // OPEN: bubbly pop-in (whole window)
    SequentialAnimation {
        id: openAnim
        PropertyAnimation { target: bubble; property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
        ParallelAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.0; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 1.0; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
    }

    // CLOSE: deflate + drift off (whole window)
    ParallelAnimation {
        id: closeAnim
        PropertyAnimation { target: bubble; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.InCubic }
        PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.06; duration: 280; easing.type: Easing.InBack; easing.overshoot: 1.15 }
        PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.06; duration: 280; easing.type: Easing.InBack; easing.overshoot: 1.15 }
        PropertyAnimation { target: bubbleTranslate; property: "x"; to: win.width * 0.55; duration: 280; easing.type: Easing.InCubic }
        PropertyAnimation { target: bubbleTranslate; property: "y"; to: -win.height * 0.35; duration: 280; easing.type: Easing.InCubic }
        onStopped: win.close()
    }
}
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (rounded glow + inset title + icon tiles + unified animation)" -ForegroundColor Green

Write-Host "`nDONE. Re-run your app." -ForegroundColor Cyan
Write-Host "Backups saved in: $backupRoot" -ForegroundColor DarkGray