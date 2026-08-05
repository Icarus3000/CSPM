# scripts\60_frameless_round_glow_v2.ps1
# Forward-only: PySide6/QML stack. Frameless window + rounded corners + accent glow.
# Fixes prior patch issues by overwriting QML files with clean canonical content.

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
        $p = (Resolve-Path -LiteralPath $MaybeRoot).Path
        return $p
    }

    # If run from scripts\, default to parent of script directory
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) {
        $scriptDir = (Get-Location).Path
    }

    $candidate = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path

    # Validate candidate has src\qml\Main.qml
    $check = Join-Path $candidate "src\qml\Main.qml"
    if (Test-Path -LiteralPath $check) {
        return $candidate
    }

    # Fallback: current directory
    $cwd = (Get-Location).Path
    $check2 = Join-Path $cwd "src\qml\Main.qml"
    if (Test-Path -LiteralPath $check2) {
        return $cwd
    }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM (must contain src\qml\Main.qml)."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
Write-Host "ProjectRoot: $root" -ForegroundColor Cyan

$backupRoot = Join-Path $root "scripts\_patch_backups\frameless_round_glow"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
$themePickerPath = Join-Path $root "src\qml\components\ThemePicker.qml"
$chromeSurfacePath = Join-Path $root "src\qml\components\ChromeSurface.qml"

if (-not (Test-Path -LiteralPath $mainQmlPath)) {
    throw "Missing required file: $mainQmlPath"
}
if (-not (Test-Path -LiteralPath $themePickerPath)) {
    throw "Missing required file: $themePickerPath"
}

# -------------------------------------------------------------------
# 1) Create/overwrite ChromeSurface.qml (rounded + glow wrapper)
# -------------------------------------------------------------------
Ensure-Dir -Path (Split-Path -Parent $chromeSurfacePath)
Backup-File -Path $chromeSurfacePath -BackupRoot $backupRoot

$chromeSurface = @"
import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root

    // Theme object (expects accent, panel2, etc.)
    property var t

    // Visual tuning
    property real cornerRadius: 24
    property real padding: 14

    // Glow tuning (subtle)
    property real glowBlurRadius: 28
    property real glowSpread: 0.18
    property real glowOpacity: 0.32

    property color accentColor: root.t ? root.t.accent : "#D500F9"
    property color glowColor: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, glowOpacity)

    // Slot for user content
    default property alias content: contentHost.data

    anchors.fill: parent

    // Main rounded surface
    Rectangle {
        id: panel
        anchors.fill: parent
        anchors.margins: root.padding
        radius: root.cornerRadius
        color: root.t ? root.t.panel2 : "#1A1024"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.10)
        z: 1
    }

    // Accent glow around the perimeter
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
# 2) Overwrite Main.qml with clean frameless + ChromeSurface + drag
#    This eliminates duplicate property assignments that are breaking QML load.
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

    // Frameless + transparent outer window
    flags: Qt.Window | Qt.FramelessWindowHint
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

    ChromeSurface {
        id: chrome
        anchors.fill: parent
        t: win.t
        cornerRadius: 24
        padding: 14
        glowBlurRadius: 28
        glowSpread: 0.18
        glowOpacity: 0.32

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

        // app-level navigation
        property int pageIndex: 0

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10

            // Top bar (drag anywhere on this row)
            RowLayout {
                id: topBar
                Layout.fillWidth: true

                DragHandler {
                    target: null
                    onActiveChanged: if (active) win.startSystemMove()
                }

                Text {
                    text: "Practice Console"
                    color: t.text
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

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
                            spacing: 14

                            Text {
                                text: "Main Menu"
                                color: t.text
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 14

                                PillButton {
                                    t: win.t
                                    primary: true
                                    text: "Enter Time"
                                    Layout.fillWidth: true
                                    onClicked: chrome.pageIndex = 1
                                }

                                PillButton {
                                    t: win.t
                                    primary: false
                                    text: "Clients (Soon)"
                                    Layout.fillWidth: true
                                }

                                PillButton {
                                    t: win.t
                                    primary: false
                                    text: "Reports (Soon)"
                                    Layout.fillWidth: true
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 14

                                PillButton {
                                    t: win.t
                                    primary: false
                                    text: "Invoices (Soon)"
                                    Layout.fillWidth: true
                                }

                                PillButton {
                                    t: win.t
                                    primary: false
                                    text: "Ticklers (Soon)"
                                    Layout.fillWidth: true
                                }

                                PillButton {
                                    t: win.t
                                    primary: false
                                    text: "HST/Tax (Soon)"
                                    Layout.fillWidth: true
                                }
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

                            Text {
                                text: "Time Entry"
                                color: t.text
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 18
                                rowSpacing: 10

                                PillTextField { t: win.t; label: "Date"; text: timePage.f_date; onEdited: timePage.f_date = value }

                                PillCombo {
                                    t: win.t
                                    label: "Client (ID or Name for now)"
                                    model: appRef ? appRef.clients : []
                                    value: timePage.f_clientId
                                    onChanged: { timePage.f_clientId = value; if (appRef) appRef.addClient(value) }
                                }

                                PillCombo {
                                    t: win.t
                                    label: "Matter (ID or Name for now)"
                                    model: appRef ? appRef.matters : []
                                    value: timePage.f_matterId
                                    onChanged: { timePage.f_matterId = value; if (appRef) appRef.addMatter(value) }
                                }

                                PillCombo {
                                    t: win.t
                                    label: "Parent (Payor/Referrer)"
                                    model: appRef ? appRef.parents : []
                                    value: timePage.f_parentId
                                    onChanged: { timePage.f_parentId = value; if (appRef) appRef.addParent(value) }
                                }

                                PillTextField { t: win.t; label: "Hours"; placeholderText: "e.g., 0.5"; text: timePage.f_hours; onEdited: timePage.f_hours = value }
                                PillTextField { t: win.t; label: "Client Rate"; placeholderText: "e.g., 475"; text: timePage.f_rate; onEdited: timePage.f_rate = value }
                                PillTextField { t: win.t; label: "Cut % (Parent)"; placeholderText: "e.g., 30"; text: timePage.f_cut; onEdited: timePage.f_cut = value }
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

                    // PAGE 2: SETTINGS (placeholder)
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
"@

Write-Utf8NoBom -Path $mainQmlPath -Content $mainQml
Write-Host "WROTE: src\qml\Main.qml (clean frameless + rounded glow + drag)" -ForegroundColor Green

# -------------------------------------------------------------------
# 3) Overwrite ThemePicker.qml with glow background
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
                    onClicked: {
                        pop.picked(modelData)
                        pop.close()
                    }
                    cursorShape: Qt.PointingHandCursor
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
Write-Host "WROTE: src\qml\components\ThemePicker.qml (glow background)" -ForegroundColor Green

Write-Host "`nDONE. Re-run your app." -ForegroundColor Cyan
Write-Host "Backups saved in: $backupRoot" -ForegroundColor DarkGray