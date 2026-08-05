# scripts\70_fix_final_hovered.ps1
# Fix QML component crash: remove overriding FINAL 'hovered' property in Button-derived components.
# Overwrites PillButton.qml and TileCard.qml with safe hover/glow implementations.

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
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot ($stamp + "_" + $name)) -Force
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
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\components\PillButton.qml")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\components\PillButton.qml")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\70_fix_final_hovered"
Ensure-Dir -Path $backupRoot

$pillPath = Join-Path $root "src\qml\components\PillButton.qml"
$tilePath = Join-Path $root "src\qml\components\TileCard.qml"

if (-not (Test-Path -LiteralPath $pillPath)) { throw "Missing: $pillPath" }
if (-not (Test-Path -LiteralPath $tilePath)) { throw "Missing: $tilePath" }

Backup-File -Path $pillPath -BackupRoot $backupRoot
Backup-File -Path $tilePath -BackupRoot $backupRoot

# --- PillButton.qml (SAFE: uses built-in Button.hovered) ---
$pill = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property bool primary: true

    hoverEnabled: true
    height: 46
    font.pixelSize: 12
    font.weight: Font.DemiBold

    background: Item {
        id: bgHost

        Rectangle {
            id: bg
            anchors.fill: parent
            radius: 18
            color: b.primary ? b.t.accent : Qt.rgba(0, 0, 0, 0.18)
            border.width: b.primary ? 0 : 2
            border.color: b.primary ? "transparent" : b.t.accent
            antialiasing: true
        }

        RectangularGlow {
            anchors.fill: bg
            glowRadius: 16
            spread: 0.22
            color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.hovered ? 0.38 : 0.16)
            cornerRadius: bg.radius + glowRadius
        }

        // Lift on hover (no custom 'hovered' property!)
        y: b.hovered ? -2 : 0
        Behavior on y { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }

    contentItem: Text {
        text: b.text
        color: b.primary ? b.t.btn_text : b.t.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
"@

# --- TileCard.qml (SAFE: uses built-in Button.hovered) ---
$tile = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property url iconSource: ""
    property bool primary: false

    hoverEnabled: true

    // even size via implicitHeight; layout can override if needed
    implicitHeight: 240
    implicitWidth: 300

    background: Item {
        id: host
        anchors.fill: parent

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

        // Lift + micro-scale on hover
        y: b.hovered ? -4 : 0
        Behavior on y { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }

        transform: Scale {
            origin.x: host.width / 2
            origin.y: host.height / 2
            xScale: b.hovered ? 1.02 : 1.0
            yScale: b.hovered ? 1.02 : 1.0
        }
        Behavior on transform.xScale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        Behavior on transform.yScale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
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

Write-Utf8NoBom -Path $pillPath -Content $pill
Write-Utf8NoBom -Path $tilePath -Content $tile

Write-Host "PATCHED: PillButton.qml and TileCard.qml (no FINAL override)" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray