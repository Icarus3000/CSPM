# 25_fix_style_and_qml_scope.ps1
# Fixes:
# 1) Force Qt Quick Controls 2 non-native style (Basic)
# 2) Toast anchor conflict
# 3) QML ReferenceError on time entry properties (scope via timePage)

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot ("archive\codegen_backups\" + $Stamp)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Ensure-Dir($p) {
  if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

function Backup-IfExists($filePath) {
  if (Test-Path -LiteralPath $filePath) {
    $rel = Resolve-Path -LiteralPath $filePath | ForEach-Object { $_.Path.Substring($ProjectRoot.Length).TrimStart("\") }
    $dest = Join-Path $BackupRoot $rel
    Ensure-Dir (Split-Path -Parent $dest)
    Copy-Item -LiteralPath $filePath -Destination $dest -Force
  }
}

function Write-File($relPath, $content) {
  $full = Join-Path $ProjectRoot $relPath
  Ensure-Dir (Split-Path -Parent $full)
  Backup-IfExists $full
  [System.IO.File]::WriteAllText($full, $content, $utf8NoBom)
  Write-Host ("WROTE: " + $relPath) -ForegroundColor Green
}

# ----------------------------
# src/python/main.py
# Force Qt Quick Controls style to Basic (customizable)
# ----------------------------
Write-File "src\python\main.py" @'
from __future__ import annotations

import os
import sys
from pathlib import Path

# Force a non-native Qt Quick Controls 2 style so we can customize background/contentItem/etc.
# Windows native style blocks many customizations and produces warnings like you saw.
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl

try:
    from PySide6.QtQuickControls2 import QQuickStyle
    QQuickStyle.setStyle("Basic")
except Exception:
    # Environment variable fallback above usually suffices.
    pass

from backend.app_controller import AppController
from services.paths import AppPaths


def main() -> int:
    root = AppPaths.project_root()

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    controller = AppController(paths=AppPaths(root))
    engine.rootContext().setContextProperty("app", controller)

    qml_main = root / "src" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_main)))

    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
'@

# ----------------------------
# src/qml/components/Toast.qml
# Fix anchor conflict by not forcing horizontalCenter while also expecting left/right.
# Toast now fills width and centers its internal bubble.
# ----------------------------
Write-File "src\qml\components\Toast.qml" @'
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var t
    property string message: ""
    property bool visibleToast: false

    // Caller should set left/right OR anchors.fill; we do not set conflicting anchors here.
    height: 44

    Rectangle {
        id: bubble
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6

        width: Math.min(root.width * 0.70, 560)
        height: 36
        radius: 14
        color: Qt.rgba(0,0,0,0.70)
        border.width: 1
        border.color: Qt.rgba(1,1,1,0.12)
        opacity: root.visibleToast ? 1 : 0

        Text {
            anchors.centerIn: parent
            text: root.message
            color: "white"
            font.pixelSize: 12
            elide: Text.ElideRight
            width: parent.width - 24
            horizontalAlignment: Text.AlignHCenter
        }

        Behavior on opacity { NumberAnimation { duration: 140 } }
    }

    Timer {
        id: tmr
        interval: 1700
        repeat: false
        onTriggered: root.visibleToast = false
    }

    function show(msg) {
        root.message = msg
        root.visibleToast = true
        tmr.restart()
    }
}
'@

# ----------------------------
# src/qml/Main.qml
# Fix:
# - Remove conflicting anchors on Toast
# - Add id: timePage and scope all f_* references to timePage.*
# ----------------------------
Write-File "src\qml\Main.qml" @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "components"

ApplicationWindow {
    id: win
    visible: true
    width: 1000
    height: 740
    title: "CSPM - Practice Management"

    property var t: app.theme
    color: t.bg

    ThemePicker {
        id: themePicker
        t: win.t
        names: app.themeNames
        onPicked: app.setTheme(name)
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
        target: app
        function onToast(msg) { toast.show(msg) }
        function onError(msg) { toast.show(msg) }
        function onThemeChanged() { win.t = app.theme }
    }

    // app-level navigation
    property int pageIndex: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        // Top bar
        RowLayout {
            Layout.fillWidth: true

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
                onClicked: app.backupWorkbook()
            }

            PillButton {
                t: win.t
                primary: false
                text: "Dump Workspace"
                onClicked: app.dumpWorkspace()
            }
        }

        SegmentedTabs {
            t: win.t
            index: win.pageIndex
            onChanged: win.pageIndex = ix
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
                currentIndex: win.pageIndex

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
                                onClicked: win.pageIndex = 1
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

                            PillTextField {
                                t: win.t
                                label: "Date"
                                text: timePage.f_date
                                onEdited: timePage.f_date = value
                            }

                            PillCombo {
                                t: win.t
                                label: "Client (ID or Name for now)"
                                model: app.clients
                                value: timePage.f_clientId
                                onChanged: { timePage.f_clientId = value; app.addClient(value) }
                            }

                            PillCombo {
                                t: win.t
                                label: "Matter (ID or Name for now)"
                                model: app.matters
                                value: timePage.f_matterId
                                onChanged: { timePage.f_matterId = value; app.addMatter(value) }
                            }

                            PillCombo {
                                t: win.t
                                label: "Parent (Payor/Referrer)"
                                model: app.parents
                                value: timePage.f_parentId
                                onChanged: { timePage.f_parentId = value; app.addParent(value) }
                            }

                            PillTextField {
                                t: win.t
                                label: "Hours"
                                placeholderText: "e.g., 0.5"
                                text: timePage.f_hours
                                onEdited: timePage.f_hours = value
                            }

                            PillTextField {
                                t: win.t
                                label: "Client Rate"
                                placeholderText: "e.g., 475"
                                text: timePage.f_rate
                                onEdited: timePage.f_rate = value
                            }

                            PillTextField {
                                t: win.t
                                label: "Cut % (Parent)"
                                placeholderText: "e.g., 30"
                                text: timePage.f_cut
                                onEdited: timePage.f_cut = value
                            }

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
                                        "RawSeconds": app.elapsedSeconds ? Math.floor(app.elapsedSeconds) : 0,
                                        "Status": "WIP"
                                    }
                                    app.saveTimeEntry(payload)
                                }
                            }

                            PillButton {
                                t: win.t
                                primary: false
                                text: "Back to Menu"
                                Layout.fillWidth: true
                                onClicked: win.pageIndex = 0
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
'@

Write-Host ""
Write-Host "Patch complete. Backups saved at:" -ForegroundColor Cyan
Write-Host ("  " + $BackupRoot) -ForegroundColor Yellow