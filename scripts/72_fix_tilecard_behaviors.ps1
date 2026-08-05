# scripts\72_fix_tilecard_behaviors.ps1
# Fix TileCard.qml: Behavior must be declared on properties of the SAME object,
# so put Behavior inside Scale object (not "Behavior on hoverScale.xScale" in Button).
# Creates backup under scripts\_patch_backups\72_fix_tilecard_behaviors\

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
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\components\TileCard.qml")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\components\TileCard.qml")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\72_fix_tilecard_behaviors"
Ensure-Dir -Path $backupRoot

$tilePath = Join-Path $root "src\qml\components\TileCard.qml"
if (-not (Test-Path -LiteralPath $tilePath)) { throw "Missing: $tilePath" }

Backup-File -Path $tilePath -BackupRoot $backupRoot

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

    // even sizing baseline
    implicitWidth: 300
    implicitHeight: 240

    // Lift on hover (uses built-in Button.hovered)
    y: b.hovered ? -4 : 0
    Behavior on y { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }

    // Micro-scale on hover (Behavior MUST live inside the Scale object)
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

Write-Utf8NoBom -Path $tilePath -Content $tile

Write-Host "PATCHED: src/qml/components/TileCard.qml (fixed Behavior placement)" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray