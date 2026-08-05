# scripts\63_ui_titlebar_tiles_anim.ps1
# Forward-only (PySide6/QML): faux titlebar (no borders), larger tiles, open/close animations,
# always-on-top + focused, and Qt6 signal param deprecation fix.

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

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing required file: $Path"
    }

    Backup-File -Path $Path -BackupRoot $BackupRoot
    $txt = Get-Content -LiteralPath $Path -Raw -Encoding UTF8

    # 1) Ensure QCursor import
    if ($txt -notmatch '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+QCursor\s*$') {
        # Insert after existing QtCore import line if present, else after other imports
        $rx = [regex]'(?m)^\s*from\s+PySide6\.QtCore\s+import\s+.*$'
        $m = $rx.Match($txt)
        if ($m.Success) {
            $insertPos = $m.Index + $m.Length
            $txt = $txt.Insert($insertPos, "`nfrom PySide6.QtGui import QCursor")
        } else {
            $txt = "from PySide6.QtGui import QCursor`n" + $txt
        }
    }

    # 2) Capture launch point once in __init__
    if ($txt -notmatch '(?m)self\._launch_point\s*=') {
        $rxInit = [regex]'(?ms)def\s+__init__\s*\(self,\s*paths:\s*AppPaths\s*\)\s*:\s*\n'
        $m2 = $rxInit.Match($txt)
        if (-not $m2.Success) {
            throw "Could not locate AppController.__init__ signature for patching."
        }

        $insertPos2 = $m2.Index + $m2.Length
        $inject = "        self._launch_point = QCursor.pos()`n"
        $txt = $txt.Insert($insertPos2, $inject)
    }

    # 3) Add a QML-visible property: launchPoint (as QVariantMap: {x:int, y:int})
    if ($txt -notmatch '(?m)def\s+launchPoint\s*\(') {
        # Insert near other @Property blocks: after themeNames or near top of properties section.
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
            # Fallback: append near top of class after __init__ block (best-effort)
            $txt += "`n" + $propBlock
        }
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $txt, $utf8NoBom)

    Write-Host "PATCHED: src\python\backend\app_controller.py (launchPoint)" -ForegroundColor Green
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
Write-Host "ProjectRoot: $root" -ForegroundColor Cyan

$backupRoot = Join-Path $root "scripts\_patch_backups\titlebar_tiles_anim"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
$chromeSurfacePath = Join-Path $root "src\qml\components\ChromeSurface.qml"
$titleBarBtnPath = Join-Path $root "src\qml\components\TitleBarButton.qml"
$tileButtonPath = Join-Path $root "src\qml\components\TileButton.qml"
$themePickerPath = Join-Path $root "src\qml\components\ThemePicker.qml"
$appControllerPath = Join-Path $root "src\python\backend\app_controller.py"

# ---- Ensure required forward-stack files exist ----
if (-not (Test-Path -LiteralPath $mainQmlPath)) { throw "Missing required file: $mainQmlPath" }
if (-not (Test-Path -LiteralPath $themePickerPath)) { throw "Missing required file: $themePickerPath" }
if (-not (Test-Path -LiteralPath $appControllerPath)) { throw "Missing required file: $appControllerPath" }

# -------------------------------------------------------------------
# 1) ChromeSurface: clip children so faux titlebar respects rounded corners
# -------------------------------------------------------------------
Ensure-Dir -Path (Split-Path -Parent $chromeSurfacePath)
Backup-File -Path $chromeSurfacePath -BackupRoot $backupRoot

$chromeSurface = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root

    property var t

    property real cornerRadius: 26
    property real padding: 14

    property real glowBlurRadius: 30
    property real glowSpread: 0.18
    property real glowOpacity: 0.32

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
        z: 1
    }

    DropShadow {
        anchors.fill: panel
        source: panel
        horizontalOffset: 0
        verticalOffset: 0
        radius: root.glowBlurRadius
        samples: 25
        spread: root.glowSpread
        color: root.glowColor
        transparentBorder: true
        z: 0
    }

    Item {
        id: contentHost
        anchors.fill: panel
        z: 2
    }
}
"@

Write-Utf8NoBom -Path $chromeSurfacePath -Content $chromeSurface
Write-Host "WROTE: src\qml\components\ChromeSurface.qml" -ForegroundColor Green

# -------------------------------------------------------------------
# 2) TitleBarButton: borderless hoverable glyph/text button (– / ✕)
# -------------------------------------------------------------------
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
    height: 28

    Text {
        id: glyph
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

# -------------------------------------------------------------------
# 3) TileButton: bigger tiles
# -------------------------------------------------------------------
Ensure-Dir -Path (Split-Path -Parent $tileButtonPath)
Backup-File -Path $tileButtonPath -BackupRoot $backupRoot

$tileButton = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property bool primary: false

    height: 130
    font.pixelSize: 16
    font.weight: Font.DemiBold

    background: Rectangle {
        id: bg
        radius: 22
        color: b.primary ? b.t.accent : Qt.rgba(0,0,0,0.18)
        border.width: b.primary ? 0 : 2
        border.color: b.primary ? "transparent" : b.t.accent
    }

    // subtle inner glow for non-primary tiles (optional but nice)
    DropShadow {
        anchors.fill: bg
        source: bg
        horizontalOffset: 0
        verticalOffset: 0
        radius: 18
        samples: 25
        spread: 0.12
        color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.primary ? 0.0 : 0.18)
        transparentBorder: true
        visible: !b.primary
    }

    contentItem: Text {
        text: b.text
        color: b.primary ? b.t.btn_text : b.t.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        width: b.width - 18
    }
}
"@

Write-Utf8NoBom -Path $tileButtonPath -Content $tileButton
Write-Host "WROTE: src\qml\components\TileButton.qml" -ForegroundColor Green

# -------------------------------------------------------------------
# 4) ThemePicker: keep glow background (overwrite stable version)
# -------------------------------------------------------------------
Backup-File -Path $themePickerPath -BackupRoot $backupRoot

$themePicker = @"
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

Popup {
    id: pop
    property var t
    property var names: []
    signal picked(string name)

    modal: false
    focus: true
    width: 260
    height: 320

    background: Item {
        Rectangle {
            id: bg
            anchors.fill: parent
            radius: 16
            color: pop.t.panel
            border.width: 2
            border.color: pop.t.accent
            z: 1
        }

        DropShadow {
            anchors.fill: bg
            source: bg
            horizontalOffset: 0
            verticalOffset: 0
            radius: 22
            samples: 25
            spread: 0.18
            color: Qt.rgba(bg.border.color.r, bg.border.color.g, bg.border.color.b, 0.30)
            transparentBorder: true
            z: 0
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Text {
            text: "Themes"
            color: pop.t.text
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: pop.names
            clip: true

            delegate: Rectangle {
                width: parent.width
                height: 36
                radius: 12
                color: Qt.rgba(1,1,1,0.04)
                border.width: 1
                border.color: Qt.rgba(1,1,1,0.10)

                Text {
                    anchors.centerIn: parent
                    text: modelData
                    color: pop.t.text
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        pop.picked(modelData)
                        pop.close()
                    }
                }
            }
        }

        Button {
            text: "Close"
            onClicked: pop.close()
            background: Rectangle { radius: 14; color: pop.t.accent }
            contentItem: Text {
                text: parent.text
                color: pop.t.btn_text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
"@

Write-Utf8NoBom -Path $themePickerPath -Content $themePicker
Write-Host "WROTE: src\qml\components\ThemePicker.qml" -ForegroundColor Green

# -------------------------------------------------------------------
# 5) Patch Python AppController to expose launchPoint (cursor at startup)
# -------------------------------------------------------------------
Patch-AppControllerForLaunchPoint -Path $appControllerPath -BackupRoot $backupRoot

# -------------------------------------------------------------------
# 6) Main.qml: faux titlebar + larger tiles + open/close animation + always-on-top/focus
# -------------------------------------------------------------------
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
    width: 1000
    height: 740
    title: "CSPM - Practice Management"

    // Frameless + always-on-top
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    // Guard: app may be temporarily null if context injection fails.
    property var appRef: (typeof app !== "undefined" && app !== null) ? app : null

    // Default theme fallback (used only if appRef is null)
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

    // Cursor launch point -> window local coords (bubble origin)
    property point launchLocal: {
        if (!appRef || !appRef.launchPoint) {
            return Qt.point(win.width / 2, win.height / 2)
        }
        var gp = Qt.point(appRef.launchPoint.x, appRef.launchPoint.y)
        return win.mapFromGlobal(gp)
    }

    // Animation state
    property bool closing: false

    function openAnimStart() {
        // bring to front and focus
        win.raise()
        win.requestActivate()

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
        // Always on top + focus at open
        win.raise()
        win.requestActivate()
        // Start bubble open animation from cursor position
        openAnimStart()
    }

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

        // Everything visible animates together (bubble / balloon feel)
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

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                // ------------------------------------------------------------
                // Faux Windows titlebar row (standalone, no borders on glyphs)
                // ------------------------------------------------------------
                Rectangle {
                    id: fauxTitlebar
                    Layout.fillWidth: true
                    height: 32
                    color: Qt.rgba(0,0,0,0.0)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 8

                        // Drag area: title region
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

                // ------------------------------------------------------------
                // Toolbar row (Theme / Backup / Dump) below faux titlebar
                // ------------------------------------------------------------
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 6
                    Layout.rightMargin: 6
                    Layout.topMargin: 6
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    PillButton {
                        t: win.t
                        primary: false
                        text: "Theme"
                        onClicked: {
                            themePicker.x = win.width - themePicker.width - 26
                            themePicker.y = 52
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

                // ------------------------------------------------------------
                // Main content
                // ------------------------------------------------------------
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
                                    spacing: 16

                                    Text {
                                        text: "Main Menu"
                                        color: t.text
                                        font.pixelSize: 18
                                        font.weight: Font.DemiBold
                                    }

                                    // BIGGER TILES
                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 3
                                        columnSpacing: 16
                                        rowSpacing: 16

                                        TileButton {
                                            t: win.t
                                            primary: true
                                            text: "Enter Time"
                                            Layout.fillWidth: true
                                            onClicked: chrome.pageIndex = 1
                                        }

                                        TileButton { t: win.t; primary: false; text: "Clients (Soon)"; Layout.fillWidth: true }
                                        TileButton { t: win.t; primary: false; text: "Reports (Soon)"; Layout.fillWidth: true }
                                        TileButton { t: win.t; primary: false; text: "Invoices (Soon)"; Layout.fillWidth: true }
                                        TileButton { t: win.t; primary: false; text: "Ticklers (Soon)"; Layout.fillWidth: true }
                                        TileButton { t: win.t; primary: false; text: "HST/Tax (Soon)"; Layout.fillWidth: true }
                                    }

                                    // Status is informational placeholder (can remove anytime)
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

                            // PAGE 1: TIME ENTRY (unchanged handlers; no deprecated implicit params)
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

                                        PillTextField {
                                            t: win.t
                                            label: "Date"
                                            text: timePage.f_date
                                            onEdited: function(value) { timePage.f_date = value }
                                        }

                                        PillCombo {
                                            t: win.t
                                            label: "Client (ID or Name for now)"
                                            model: appRef ? appRef.clients : []
                                            value: timePage.f_clientId
                                            onChanged: function(value) {
                                                timePage.f_clientId = value
                                                if (appRef) appRef.addClient(value)
                                            }
                                        }

                                        PillCombo {
                                            t: win.t
                                            label: "Matter (ID or Name for now)"
                                            model: appRef ? appRef.matters : []
                                            value: timePage.f_matterId
                                            onChanged: function(value) {
                                                timePage.f_matterId = value
                                                if (appRef) appRef.addMatter(value)
                                            }
                                        }

                                        PillCombo {
                                            t: win.t
                                            label: "Parent (Payor/Referrer)"
                                            model: appRef ? appRef.parents : []
                                            value: timePage.f_parentId
                                            onChanged: function(value) {
                                                timePage.f_parentId = value
                                                if (appRef) appRef.addParent(value)
                                            }
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

                                        PillButton {
                                            t: win.t
                                            primary: false
                                            text: "Back to Menu"
                                            Layout.fillWidth: true
                                            onClicked: chrome.pageIndex = 0
                                        }
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

        // -------------------------
        // OPEN ANIMATION (bubble)
        // -------------------------
        SequentialAnimation {
            id: openAnim

            PropertyAnimation { target: bubble; property: "opacity"; from: 0.0; to: 1.0; duration: 160; easing.type: Easing.OutCubic }
            ParallelAnimation {
                PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.0; duration: 360; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
                PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 1.0; duration: 360; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
            }
        }

        // -------------------------
        // CLOSE ANIMATION (deflate + blow off screen)
        // -------------------------
        ParallelAnimation {
            id: closeAnim

            PropertyAnimation { target: bubble; property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.InCubic }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 0.06; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.1 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 0.06; duration: 260; easing.type: Easing.InBack; easing.overshoot: 1.1 }
            PropertyAnimation { target: bubbleTranslate; property: "x"; to: win.width * 0.55; duration: 260; easing.type: Easing.InCubic }
            PropertyAnimation { target: bubbleTranslate; property: "y"; to: -win.height * 0.35; duration: 260; easing.type: Easing.InCubic }

            onStopped: {
                win.close()
            }
        }
    }
}
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (faux titlebar + larger tiles + open/close animation)" -ForegroundColor Green

Write-Host "`nDONE. Re-run your app." -ForegroundColor Cyan
Write-Host "Backups saved in: $backupRoot" -ForegroundColor DarkGray