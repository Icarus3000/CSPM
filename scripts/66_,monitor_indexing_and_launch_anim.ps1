# scripts\66_monitor_indexing_and_launch_anim.ps1
# Forward-only: implement monitor indexing in backend, expose monitor0 + click point to QML,
# and update Main.qml to position on monitor0 and animate from last click to center.

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

$backupRoot = Join-Path $root "scripts\_patch_backups\66_monitor_indexing_and_launch_anim"
Ensure-Dir -Path $backupRoot

$appControllerPath = Join-Path $root "src\python\backend\app_controller.py"
$mainQmlPath = Join-Path $root "src\qml\Main.qml"

if (-not (Test-Path -LiteralPath $appControllerPath)) { throw "Missing: $appControllerPath" }
if (-not (Test-Path -LiteralPath $mainQmlPath)) { throw "Missing: $mainQmlPath" }

# -------------------------------
# 1) Patch backend/app_controller.py
# -------------------------------
Backup-File -Path $appControllerPath -BackupRoot $backupRoot
$py = Get-Content -LiteralPath $appControllerPath -Raw -Encoding UTF8

# Ensure imports
if ($py -notmatch '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+QCursor,\s*QGuiApplication\s*$') {
    # Add a combined import line; if QCursor import exists, extend it; else insert new line.
    if ($py -match '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+QCursor\s*$') {
        $py = [regex]::Replace($py, '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+QCursor\s*$', 'from PySide6.QtGui import QCursor, QGuiApplication')
    } elseif ($py -match '(?m)^\s*from\s+PySide6\.QtGui\s+import\s+') {
        # If some QtGui import exists but not QCursor, add new line near the Qt imports
        $py = "from PySide6.QtGui import QCursor, QGuiApplication`n" + $py
    } else {
        $py = "from PySide6.QtGui import QCursor, QGuiApplication`n" + $py
    }
}

# Ensure QPoint import (we’ll accept QtCore already imported with QObject/Signal/Slot/Property/QTimer)
if ($py -notmatch '(?m)QPoint') {
    # If QtCore import line exists, append QPoint
    $py = [regex]::Replace(
        $py,
        '(?m)^from\s+PySide6\.QtCore\s+import\s+(.+)$',
        { param($m) 
            $line = $m.Groups[0].Value
            if ($line -match '\bQPoint\b') { return $line }
            return $line.TrimEnd() + ", QPoint"
        },
        1
    )
}

# Add signal + storage + helpers + properties + slot if not present
if ($py -notmatch '(?m)monitorChanged\s*=\s*Signal') {
    $py = [regex]::Replace(
        $py,
        '(?m)^\s*listsChanged\s*=\s*Signal\(\s*\)\s*$',
        '$0' + "`n    monitorChanged = Signal()`n",
        1
    )
}

# Inject into __init__: last click + monitor cache
if ($py -notmatch '(?m)self\._last_click\s*=') {
    $py = [regex]::Replace(
        $py,
        '(?ms)def\s+__init__\s*\(self,\s*paths:\s*AppPaths\s*\)\s*:\s*\n\s*super\(\)\.__init__\(\)\s*\n',
        { param($m)
            $m.Value + "        self._last_click = QCursor.pos()`n"
        },
        1
    )
}

# Add helper methods inside class (only once)
if ($py -notmatch '(?m)def\s+_screens_ltr') {
$helpers = @"
    def _screens_ltr(self):
        screens = list(QGuiApplication.screens() or [])
        # Left-most monitor = smallest geometry().x(); then next to the right.
        screens.sort(key=lambda s: int(s.geometry().x()))
        return screens

    def _screen_index_1_based(self, screen):
        screens = self._screens_ltr()
        try:
            return screens.index(screen) + 1
        except ValueError:
            return 1

    def _screen_for_point(self, pt):
        # Prefer Qt API if available.
        try:
            s = QGuiApplication.screenAt(pt)
            if s is not None:
                return s
        except Exception:
            pass
        # Fallback: manual contains check.
        for s in self._screens_ltr():
            try:
                if s.geometry().contains(pt):
                    return s
            except Exception:
                continue
        try:
            return QGuiApplication.primaryScreen()
        except Exception:
            return None

    def _rect_to_map(self, r):
        return {"x": int(r.x()), "y": int(r.y()), "w": int(r.width()), "h": int(r.height())}

"@

    # Insert helpers near top of class after __init__ block (best effort: after __init__ definition ends is hard),
    # so insert after existing _tick method if present else near end.
    if ($py -match '(?ms)\n\s*def\s+_tick\s*\(self\).*?\n') {
        $py = $py + "`n" + $helpers
    } else {
        $py = $py + "`n" + $helpers
    }
}

# Add properties + slot
if ($py -notmatch '(?m)def\s+monitorsOrdered') {
$props = @"
    @Property("QVariantList", notify=monitorChanged)
    def monitorsOrdered(self):
        out = []
        for ix, s in enumerate(self._screens_ltr(), start=1):
            g = s.geometry()
            a = s.availableGeometry()
            out.append({
                "index": int(ix),
                "name": str(s.name() or f"Screen {ix}"),
                "geometry": self._rect_to_map(g),
                "available": self._rect_to_map(a),
            })
        return out

    @Property("QVariantMap", notify=monitorChanged)
    def lastClick(self):
        p = self._last_click
        return {"x": int(p.x()), "y": int(p.y())}

    @Property("QVariantMap", notify=monitorChanged)
    def monitor0(self):
        s = self._screen_for_point(self._last_click)
        if s is None:
            return {"index": 1, "name": "Screen 1", "geometry": {"x":0,"y":0,"w":0,"h":0}, "available": {"x":0,"y":0,"w":0,"h":0}}
        ix = self._screen_index_1_based(s)
        return {
            "index": int(ix),
            "name": str(s.name() or f"Screen {ix}"),
            "geometry": self._rect_to_map(s.geometry()),
            "available": self._rect_to_map(s.availableGeometry()),
        }

    @Slot(int, int)
    def setLastClick(self, x, y):
        try:
            self._last_click = QPoint(int(x), int(y))
        except Exception:
            self._last_click = QCursor.pos()
        self.monitorChanged.emit()

"@
    $py = $py + "`n" + $props
}

# Write back
Write-Utf8NoBom -Path $appControllerPath -Content $py
Write-Host "PATCHED: src\python\backend\app_controller.py (monitor indexing + monitor0 + last click)" -ForegroundColor Green

# -------------------------------
# 2) Overwrite Main.qml with correct positioning + “center on monitor0” bounce
# -------------------------------
Backup-File -Path $mainQmlPath -BackupRoot $backupRoot

$mainQml = @"
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: win

    // Critical: do not show until positioned, to avoid top-left flashes.
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

    // Animation state
    property bool animating: false
    property bool closing: false

    // Global click point (monitor0 anchor)
    property int clickGX: 0
    property int clickGY: 0

    // Target center on monitor0 available rect
    property int targetX: 0
    property int targetY: 0

    // Update click + monitor0 in backend
    function noteClickGlobal(gx, gy) {
        if (appRef) {
            appRef.setLastClick(gx, gy)
        }
    }

    function computeMonitor0Target() {
        var a = (appRef && appRef.monitor0) ? appRef.monitor0.available : null
        if (!a) {
            // fallback: current screen
            var ax = win.screen ? win.screen.availableGeometry.x : 0
            var ay = win.screen ? win.screen.availableGeometry.y : 0
            var aw = win.screen ? win.screen.availableGeometry.width : Screen.width
            var ah = win.screen ? win.screen.availableGeometry.height : Screen.height
            a = { "x": ax, "y": ay, "w": aw, "h": ah }
        }
        targetX = Math.round(a.x + (a.w - win.width) / 2)
        targetY = Math.round(a.y + (a.h - win.height) / 2)
    }

    function focusTop() {
        win.raise()
        win.requestActivate()
    }

    // Bubble origin in window coords
    property point originPt: Qt.point(width/2, height/2)

    function openBubbleFromClickToMonitor0Center() {
        if (animating) {
            return
        }
        animating = true
        closing = false

        // Read last click from backend (initially cursor at startup)
        var lc = (appRef && appRef.lastClick) ? appRef.lastClick : { "x": 0, "y": 0 }
        clickGX = lc.x
        clickGY = lc.y

        // Compute destination: center of monitor0
        computeMonitor0Target()

        // Start position: center window on click point (so bubble is born at click)
        win.x = Math.round(clickGX - win.width / 2)
        win.y = Math.round(clickGY - win.height / 2)

        // Show now (position already set; no top-left flash)
        win.visible = true
        focusTop()

        // Bubble origin relative to current window position (click inside window)
        originPt = Qt.point(clickGX - win.x, clickGY - win.y)
        bubbleScale.origin.x = originPt.x
        bubbleScale.origin.y = originPt.y
        bubbleRot.origin.x = originPt.x
        bubbleRot.origin.y = originPt.y

        // Reset transforms
        bubble.opacity = 0.0
        bubbleTranslate.x = 0
        bubbleTranslate.y = 0
        bubbleRot.angle = 0
        bubbleScale.xScale = 0.06
        bubbleScale.yScale = 0.06

        // Animate window movement to center of monitor0 while inflating bubble
        openAnim.restart()
    }

    // Global click catcher (updates monitor0 definition while app runs)
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: true

        onPressed: function(mouse) {
            // Map the click to global coordinates and tell backend
            var gp = win.contentItem.mapToGlobal(mouse.x, mouse.y)
            noteClickGlobal(Math.round(gp.x), Math.round(gp.y))
            // Let underlying controls still receive click
            mouse.accepted = false
        }
    }

    Component.onCompleted: {
        // Make sure backend has a last-click (it will default to cursor at startup)
        // Then run the open animation: from click point -> center of monitor0
        openBubbleFromClickToMonitor0Center()
    }

    // Whole app (chrome + glow + content) animates together
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
            anchors.fill: parent
            t: win.t

            // Faux titlebar: monitor0 index available if you want to display it later
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
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
                        onClicked: win.close()
                    }
                }
            }

            // TODO: your existing toolbar + tiles/pages remain; keep your current UI below
            // (We are focusing on monitor positioning + launch animation here.)
        }
    }

    // OPEN: bubblegum inflate + window move to monitor0 center + settle bounce
    ParallelAnimation {
        id: openAnim

        // Bubble inflation + wobble
        SequentialAnimation {
            PropertyAnimation { target: bubble; property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
        }

        SequentialAnimation {
            PropertyAnimation { target: bubbleScale; property: "xScale"; from: 0.06; to: 1.08; duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
            PropertyAnimation { target: bubbleScale; property: "xScale"; to: 1.0; duration: 160; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
        }

        SequentialAnimation {
            PropertyAnimation { target: bubbleScale; property: "yScale"; from: 0.06; to: 0.92; duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
            PropertyAnimation { target: bubbleScale; property: "yScale"; to: 1.0; duration: 160; easing.type: Easing.OutElastic; easing.amplitude: 1.0; easing.period: 0.5 }
        }

        SequentialAnimation {
            PropertyAnimation { target: bubbleRot; property: "angle"; from: 0; to: -6; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 5; duration: 170; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: -3; duration: 140; easing.type: Easing.OutCubic }
            PropertyAnimation { target: bubbleRot; property: "angle"; to: 0; duration: 140; easing.type: Easing.OutCubic }
        }

        // Window movement from click position -> monitor0 center with bounce settle
        SequentialAnimation {
            PropertyAnimation { target: win; property: "x"; to: targetX; duration: 640; easing.type: Easing.OutBack; easing.overshoot: 1.20 }
            PropertyAnimation { target: win; property: "x"; to: targetX; duration: 60; easing.type: Easing.OutCubic }
        }

        SequentialAnimation {
            PropertyAnimation { target: win; property: "y"; to: targetY; duration: 640; easing.type: Easing.OutBack; easing.overshoot: 1.20 }
            PropertyAnimation { target: win; property: "y"; to: targetY; duration: 60; easing.type: Easing.OutCubic }
        }

        onStopped: {
            animating = false
            focusTop()
        }
    }
}
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (monitor0 centering + correct launch placement)" -ForegroundColor Green

Write-Host "`nDONE. Backups in: $backupRoot" -ForegroundColor Cyan
