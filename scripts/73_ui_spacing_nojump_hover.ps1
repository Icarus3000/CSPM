# scripts\73_ui_spacing_nojump_hover.ps1
# Fixes:
# 1) Move "Practice Console" title down slightly
# 2) Add right padding after ✕ and after Dump Workspace
# 3) Stop tile hover "jump" by removing layout-moving y-shift on the Button itself
#    and moving lift into the background Item.

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

function Backup-File {
    param([string]$Path, [string]$BackupRoot)
    if (Test-Path -LiteralPath $Path) {
        Ensure-Dir -Path $BackupRoot
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $name = Split-Path -Leaf $Path
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot ($stamp + "_" + $name)) -Force
    }
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
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

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\73_ui_spacing_nojump_hover"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
$tileCardPath = Join-Path $root "src\qml\components\TileCard.qml"

if (-not (Test-Path -LiteralPath $mainQmlPath)) { throw "Missing: $mainQmlPath" }
if (-not (Test-Path -LiteralPath $tileCardPath)) { throw "Missing: $tileCardPath" }

Backup-File -Path $mainQmlPath -BackupRoot $backupRoot
Backup-File -Path $tileCardPath -BackupRoot $backupRoot

# -------------------------
# 1) Overwrite TileCard.qml with "no layout jump" hover
#    (hover lift happens inside background item; Button y never changes)
# -------------------------
$tileCard = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property url iconSource: ""
    property bool primary: false

    hoverEnabled: true

    // Even sizing baseline (GridLayout can still control width)
    implicitWidth: 300
    implicitHeight: 240

    // Micro-scale on hover (transform is visual only; does not re-layout)
    transform: Scale {
        id: hoverScale
        origin.x: b.width / 2
        origin.y: b.height / 2
        xScale: b.hovered ? 1.02 : 1.0
        yScale: b.hovered ? 1.02 : 1.0
        Behavior on xScale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        Behavior on yScale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
    }

    background: Item {
        id: bgHost
        anchors.fill: parent

        // Lift happens HERE (inside background), so layout never reflows/jumps
        y: b.hovered ? -4 : 0
        Behavior on y { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }

        Rectangle {
            id: bg
            anchors.fill: parent
            radius: 34
            color: Qt.rgba(0, 0, 0, 0.18)
            border.width: 2
            border.color: b.primary ? "transparent" : b.t.accent
            antialiasing: true
        }

        RectangularGlow {
            anchors.fill: bg
            glowRadius: 20
            spread: 0.22
            color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.hovered ? 0.50 : 0.24)
            cornerRadius: bg.radius + glowRadius
        }
    }

    contentItem: Column {
        anchors.centerIn: parent
        spacing: 12

        Image {
            width: 76
            height: 76
            source: b.iconSource
            fillMode: Image.PreserveAspectFit
            smooth: true
            opacity: 0.98
        }

        Text {
            text: b.text
            color: b.t.text
            font.pixelSize: 17
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            width: b.width - 28
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
        }
    }
}
"@
Write-Utf8NoBom -Path $tileCardPath -Content $tileCard

# -------------------------
# 2) Patch Main.qml: move title down slightly and add right padding.
#    We do minimal string-based edits.
# -------------------------
$main = Get-Content -LiteralPath $mainQmlPath -Raw -Encoding UTF8

# A) Move title down: after the line containing text: "Practice Console" add a small vertical offset.
# We insert only if not already present.
if ($main -match 'text:\s*"Practice Console"' -and $main -notmatch 'anchors\.verticalCenterOffset') {
    $main = [regex]::Replace(
        $main,
        '(?m)^(\\s*text:\\s*"Practice Console"\\s*)$',
        '$1' + "`n" + '                                anchors.verticalCenterOffset: 2',
        1
    )
}

# B) Add more right padding to the titlebar row by bumping anchors.rightMargin if present.
# If rightMargin exists, increase it (simple replace from 10/12/14 to 26). If absent, add it.
if ($main -match 'anchors\.rightMargin:\s*\d+') {
    $main = [regex]::Replace($main, '(?m)anchors\.rightMargin:\s*\d+', 'anchors.rightMargin: 26', 1)
} else {
    # Insert rightMargin after leftMargin in the titlebar RowLayout if possible
    $main = [regex]::Replace(
        $main,
        '(?m)(anchors\.leftMargin:\s*\d+\s*)$',
        '$1' + "`n" + '                        anchors.rightMargin: 26',
        1
    )
}

# C) Add right padding after "Dump Workspace" row: increase Layout.rightMargin on that toolbar row.
# We set the first toolbar row right margin to 24 if it exists; else insert it.
if ($main -match 'Layout\.rightMargin:\s*\d+') {
    $main = [regex]::Replace($main, '(?m)Layout\.rightMargin:\s*\d+', 'Layout.rightMargin: 24', 1)
} else {
    $main = [regex]::Replace(
        $main,
        '(?m)(Layout\.leftMargin:\s*\d+\s*)$',
        '$1' + "`n" + '                    Layout.rightMargin: 24',
        1
    )
}

Write-Utf8NoBom -Path $mainQmlPath -Content $main

Write-Host "PATCHED: TileCard hover no-jump + Main.qml spacing tweaks" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray