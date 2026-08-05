# scripts\69_ui_polish_round_glow_hover_themes.ps1
# Forward-only UI polish:
# - Rounded glow corners (avoid clipped square glow) by increasing chrome padding and radii
# - Full-window unified open/close animation (bubble wrapper contains everything)
# - Title inset + moved down; X/- moved left
# - Even tile sizing + icon tiles
# - Hover lift + glow for tiles and pill buttons
# - Restore 7 themes in src/qml/themes/themes.json

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
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\Main.qml")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\Main.qml")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM (must contain src\qml\Main.qml)."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\69_ui_polish"
Ensure-Dir -Path $backupRoot

$mainQml = Join-Path $root "src\qml\Main.qml"
$chromeSurface = Join-Path $root "src\qml\components\ChromeSurface.qml"
$pillButton = Join-Path $root "src\qml\components\PillButton.qml"
$tileCard = Join-Path $root "src\qml\components\TileCard.qml"
$titleBarButton = Join-Path $root "src\qml\components\TitleBarButton.qml"
$themesJson = Join-Path $root "src\qml\themes\themes.json"

if (-not (Test-Path -LiteralPath $mainQml)) { throw "Missing: $mainQml" }
Ensure-Dir -Path (Split-Path -Parent $chromeSurface)
Ensure-Dir -Path (Split-Path -Parent $pillButton)
Ensure-Dir -Path (Split-Path -Parent $tileCard)
Ensure-Dir -Path (Split-Path -Parent $titleBarButton)
Ensure-Dir -Path (Split-Path -Parent $themesJson)

Backup-File -Path $mainQml -BackupRoot $backupRoot
Backup-File -Path $chromeSurface -BackupRoot $backupRoot
Backup-File -Path $pillButton -BackupRoot $backupRoot
Backup-File -Path $tileCard -BackupRoot $backupRoot
Backup-File -Path $titleBarButton -BackupRoot $backupRoot
Backup-File -Path $themesJson -BackupRoot $backupRoot

# 1) ChromeSurface.qml - stronger rounding + keep glow inside window bounds by increasing padding
$chromeSurfaceContent = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property var t

    // KEY: padding must be >= glowRadius + ~8 to avoid glow clipping at window edges.
    property real padding: 44
    property real cornerRadius: 44

    property real glowRadius: 28
    property real glowOpacity: 0.42

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
        antialiasing: true
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
Write-Utf8NoBom -Path $chromeSurface -Content $chromeSurfaceContent

# 2) TitleBarButton.qml - hover glow effect (no border), smaller width, easier to move left
$titleBarButtonContent = @"
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

    width: 40
    height: 30

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
Write-Utf8NoBom -Path $titleBarButton -Content $titleBarButtonContent

# 3) PillButton.qml - add hover lift + accent glow
$pillButtonContent = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property bool primary: true

    height: 46
    font.pixelSize: 12
    font.weight: Font.DemiBold
    hoverEnabled: true

    property bool hovered: false

    background: Item {
        id: bgHost

        Rectangle {
            id: bg
            anchors.fill: parent
            radius: 18
            color: b.primary ? b.t.accent : Qt.rgba(0,0,0,0.18)
            border.width: b.primary ? 0 : 2
            border.color: b.primary ? "transparent" : b.t.accent
            antialiasing: true
        }

        RectangularGlow {
            anchors.fill: bg
            glowRadius: 16
            spread: 0.22
            color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.hovered ? 0.35 : 0.15)
            cornerRadius: bg.radius + glowRadius
        }

        Behavior on y { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        y: b.hovered ? -2 : 0
    }

    contentItem: Text {
        text: b.text
        color: b.primary ? b.t.btn_text : b.t.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    onHoveredChanged: b.hovered = b.hovered
    onEntered: b.hovered = true
    onExited: b.hovered = false
}
"@
Write-Utf8NoBom -Path $pillButton -Content $pillButtonContent

# 4) TileCard.qml - enforce even sizing + hover lift + glow + subtle scale
$tileCardContent = @"
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property url iconSource: ""
    property bool primary: false

    // Even size for all tiles
    implicitHeight: 240
    hoverEnabled: true

    property bool hovered: false

    background: Item {
        id: host
        anchors.fill: parent

        Rectangle {
            id: bg
            anchors.fill: parent
            radius: 34
            color: Qt.rgba(0,0,0,0.18)
            border.width: 2
            border.color: b.primary ? "transparent" : b.t.accent
            antialiasing: true
        }

        RectangularGlow {
            anchors.fill: bg
            glowRadius: 20
            spread: 0.22
            color: Qt.rgba(b.t.accent.r, b.t.accent.g, b.t.accent.b, b.hovered ? 0.45 : 0.22)
            cornerRadius: bg.radius + glowRadius
        }

        // Hover lift
        Behavior on y { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        y: b.hovered ? -4 : 0

        // Hover micro-scale
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
        }
    }

    onEntered: b.hovered = true
    onExited: b.hovered = false
}
"@
Write-Utf8NoBom -Path $tileCard -Content $tileCardContent

# 5) Restore 7 themes in themes.json (forward theme source)
$themesJsonContent = @"
{
  "themes": {
    "Neon Purple": {
      "mode": "Dark",
      "bg": "#000000",
      "panel": "#120A18",
      "panel2": "#1A1024",
      "accent": "#D500F9",
      "hover": "#E040FB",
      "text": "#FFFFFF",
      "muted": "#C9B6D6",
      "btn_text": "black"
    },
    "Neon Green": {
      "mode": "Dark",
      "bg": "#000000",
      "panel": "#0A160C",
      "panel2": "#102214",
      "accent": "#00E676",
      "hover": "#69F0AE",
      "text": "#FFFFFF",
      "muted": "#B6D6BE",
      "btn_text": "black"
    },
    "Neon Blue": {
      "mode": "Dark",
      "bg": "#000000",
      "panel": "#0B1324",
      "panel2": "#121F38",
      "accent": "#2979FF",
      "hover": "#448AFF",
      "text": "#FFFFFF",
      "muted": "#B9C9FF",
      "btn_text": "white"
    },
    "Glowing Red": {
      "mode": "Dark",
      "bg": "#000000",
      "panel": "#1A0B0C",
      "panel2": "#2A0F12",
      "accent": "#FF1744",
      "hover": "#FF5252",
      "text": "#FFFFFF",
      "muted": "#F4B7C2",
      "btn_text": "white"
    },
    "Glossy White": {
      "mode": "Light",
      "bg": "#EDEDED",
      "panel": "#FFFFFF",
      "panel2": "#F7F7F7",
      "accent": "#D8D8D8",
      "hover": "#CFCFCF",
      "text": "#111111",
      "muted": "#333333",
      "btn_text": "black"
    },
    "Grayscale": {
      "mode": "Light",
      "bg": "#6E6E6E",
      "panel": "#8A8A8A",
      "panel2": "#9B9B9B",
      "accent": "#3A3A3A",
      "hover": "#5A5A5A",
      "text": "#FFFFFF",
      "muted": "#F0F0F0",
      "btn_text": "white"
    },
    "Standard Dark": {
      "mode": "Dark",
      "bg": "#141414",
      "panel": "#1F1F1F",
      "panel2": "#2A2A2A",
      "accent": "#5A5A5A",
      "hover": "#6A6A6A",
      "text": "#EAEAEA",
      "muted": "#BDBDBD",
      "btn_text": "white"
    }
  }
}
"@
Write-Utf8NoBom -Path $themesJson -Content $themesJsonContent

Write-Host "PATCHED: ChromeSurface.qml, PillButton.qml, TileCard.qml, TitleBarButton.qml, themes.json" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray
Write-Host "Done." -ForegroundColor Cyan