# 20_codegen_qml_ui.ps1
# Generates QML UI + components + themes.json (safe overwrite w/ backups)

$BaseRoot = "C:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House"
$ProjectRoot = Join-Path $BaseRoot "__CSPM"

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot ("archive\codegen_backups\" + $Stamp)

function Ensure-Dir($p) { if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

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
  Set-Content -LiteralPath $full -Value $content -Encoding UTF8
  Write-Host ("WROTE: " + $relPath) -ForegroundColor Green
}

Ensure-Dir (Join-Path $ProjectRoot "src\qml\components")
Ensure-Dir (Join-Path $ProjectRoot "src\qml\themes")

# themes.json
Write-File "src\qml\themes\themes.json" @'
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
    "Standard Dark": {
      "mode": "Dark",
      "bg": "#141414",
      "panel": "#1F1F1F",
      "panel2": "#2A2A2A",
      "accent": "#7A7A7A",
      "hover": "#6A6A6A",
      "text": "#EAEAEA",
      "muted": "#BDBDBD",
      "btn_text": "white"
    }
  }
}
'@

# PillTextField
Write-File "src\qml\components\PillTextField.qml" @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var t
    property string label: ""
    property string text: field.text
    property string placeholderText: ""
    signal edited(string value)

    implicitHeight: 62
    implicitWidth: 320

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        Text {
            text: root.label
            color: root.t ? root.t.text : "white"
            opacity: 0.9
            font.pixelSize: 12
        }

        Rectangle {
            Layout.fillWidth: true
            height: 40
            radius: 16
            color: Qt.rgba(0,0,0,0.22)
            border.width: field.activeFocus ? 3 : 2
            border.color: field.activeFocus ? root.t.hover : Qt.rgba(1,1,1,0.18)

            TextField {
                id: field
                anchors.fill: parent
                anchors.margins: 10
                background: null
                color: root.t ? root.t.text : "white"
                placeholderText: root.placeholderText
                onTextEdited: root.edited(text)
            }
        }
    }
}
'@

# PillCombo (Client/Matter/Parent dropdowns)
Write-File "src\qml\components\PillCombo.qml" @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var t
    property string label: ""
    property var model: []
    property string value: ""
    signal changed(string value)

    implicitHeight: 62
    implicitWidth: 320

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        Text {
            text: root.label
            color: root.t ? root.t.text : "white"
            opacity: 0.9
            font.pixelSize: 12
        }

        Rectangle {
            Layout.fillWidth: true
            height: 40
            radius: 16
            color: Qt.rgba(0,0,0,0.22)
            border.width: combo.activeFocus ? 3 : 2
            border.color: combo.activeFocus ? root.t.hover : Qt.rgba(1,1,1,0.18)

            ComboBox {
                id: combo
                anchors.fill: parent
                anchors.margins: 6
                model: root.model
                editable: true
                background: null

                Component.onCompleted: combo.editText = root.value || ""

                onEditTextChanged: {
                    root.value = combo.editText
                    root.changed(root.value)
                }

                onActivated: {
                    root.value = combo.currentText
                    root.changed(root.value)
                }

                contentItem: TextField {
                    text: combo.editText
                    background: null
                    color: root.t ? root.t.text : "white"
                    onTextEdited: combo.editText = text
                }

                indicator: Text {
                    text: "▾"
                    color: Qt.rgba(1,1,1,0.80)
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 14
                }
            }
        }
    }

    onValueChanged: {
        if (combo && combo.editText !== root.value) {
            combo.editText = root.value || ""
        }
    }
}
'@

# PillButton
Write-File "src\qml\components\PillButton.qml" @'
import QtQuick
import QtQuick.Controls

Button {
    id: b
    property var t
    property bool primary: true

    height: 44
    font.pixelSize: 12
    font.weight: Font.DemiBold

    background: Rectangle {
        radius: 16
        color: b.primary ? b.t.accent : "transparent"
        border.width: b.primary ? 0 : 2
        border.color: b.primary ? "transparent" : b.t.accent
    }

    contentItem: Text {
        text: b.text
        color: b.primary ? b.t.btn_text : b.t.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
'@

# SegmentedTabs
Write-File "src\qml\components\SegmentedTabs.qml" @'
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var t
    property int index: 0
    signal changed(int ix)

    implicitHeight: 42
    implicitWidth: 360

    Rectangle {
        anchors.fill: parent
        radius: 16
        color: root.t.panel2
        border.width: 1
        border.color: Qt.rgba(1,1,1,0.10)

        Row {
            anchors.centerIn: parent
            spacing: 10

            Repeater {
                model: ["Menu", "Time Entry", "Settings"]
                delegate: Button {
                    text: modelData
                    checkable: true
                    checked: root.index === model.index
                    onClicked: {
                        root.index = model.index
                        root.changed(root.index)
                    }

                    background: Rectangle {
                        radius: 12
                        color: checked ? root.t.accent : Qt.rgba(1,1,1,0.03)
                        border.width: 1
                        border.color: Qt.rgba(1,1,1,0.12)
                    }

                    contentItem: Text {
                        text: parent.text
                        color: checked ? root.t.btn_text : Qt.rgba(1,1,1,0.85)
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
            }
        }
    }
}
'@

# ThemePicker
Write-File "src\qml\components\ThemePicker.qml" @'
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: pop
    property var t
    property var names: []
    signal picked(string name)

    modal: false
    focus: true
    width: 260
    height: 320

    background: Rectangle {
        radius: 16
        color: pop.t.panel
        border.width: 2
        border.color: pop.t.accent
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
'@

# Toast
Write-File "src\qml\components\Toast.qml" @'
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var t
    property string message: ""
    property bool visibleToast: false

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 18
    width: parent.width
    height: 40

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width * 0.6, 520)
        height: 36
        radius: 14
        color: Qt.rgba(0,0,0,0.65)
        border.width: 1
        border.color: Qt.rgba(1,1,1,0.12)
        opacity: root.visibleToast ? 1 : 0

        Text {
            anchors.centerIn: parent
            text: root.message
            color: "white"
            font.pixelSize: 12
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

# Main.qml (Main Menu landing + Time Entry screen)
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

                        // tiles
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
                    // local form state
                    property string f_entryId: ""
                    property string f_date: ""
                    property string f_clientId: ""
                    property string f_matterId: ""
                    property string f_parentId: ""
                    property string f_desc: ""
                    property string f_hours: ""
                    property string f_rate: ""
                    property string f_cut: "0"
                    property int f_rawSeconds: 0

                    Component.onCompleted: {
                        // default date
                        var d = new Date()
                        var mm = String(d.getMonth()+1).padStart(2, "0")
                        var dd = String(d.getDate()).padStart(2, "0")
                        f_date = d.getFullYear() + "-" + mm + "-" + dd
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

                            PillTextField { t: win.t; label: "Date"; text: f_date; onEdited: f_date = value }

                            PillCombo {
                                t: win.t
                                label: "Client (ID or Name for now)"
                                model: app.clients
                                value: f_clientId
                                onChanged: { f_clientId = value; app.addClient(value) }
                            }

                            PillCombo {
                                t: win.t
                                label: "Matter (ID or Name for now)"
                                model: app.matters
                                value: f_matterId
                                onChanged: { f_matterId = value; app.addMatter(value) }
                            }

                            PillCombo {
                                t: win.t
                                label: "Parent (Payor/Referrer)"
                                model: app.parents
                                value: f_parentId
                                onChanged: { f_parentId = value; app.addParent(value) }
                            }

                            PillTextField { t: win.t; label: "Hours"; placeholderText: "e.g., 0.5"; text: f_hours; onEdited: f_hours = value }
                            PillTextField { t: win.t; label: "Client Rate"; placeholderText: "e.g., 475"; text: f_rate; onEdited: f_rate = value }

                            PillTextField { t: win.t; label: "Cut % (Parent)"; placeholderText: "e.g., 30"; text: f_cut; onEdited: f_cut = value }
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
                                    text: f_desc
                                    background: null
                                    color: t.text
                                    wrapMode: TextArea.Wrap
                                    onTextChanged: f_desc = text
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
                                        "EntryID": f_entryId,
                                        "Date": f_date,
                                        "ClientID": f_clientId,
                                        "MatterID": f_matterId,
                                        "ParentID": f_parentId,
                                        "Description": f_desc,
                                        "Hours": f_hours,
                                        "ClientRate": f_rate,
                                        "CutPct": f_cut,
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
Write-Host "QML codegen complete." -ForegroundColor Cyan
Write-Host ("Backups (if any overwrites) in: " + $BackupRoot) -ForegroundColor Cyan