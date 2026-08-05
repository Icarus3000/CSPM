pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root

    property var t
    property var metrics
    property var appRef: null
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: visualRules.isPro

    property color menuSurface: SemanticTheme.surface(root.t, "popup", "neutral", root.appStyle)
    property color menuInk: SemanticTheme.ink(root.t, "popup", "neutral", root.appStyle)
    property color menuBorder: SemanticTheme.border(root.t, "popup", "neutral", root.appStyle)
    property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color hoverFill: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.alpha(root.menuInk, 0.08)
    property color inactiveFill: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : SemanticTheme.alpha(root.menuInk, 0.05)
    property color activeFill: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : ((SemanticTheme.luma(root.accent) > 0.70) ? Qt.darker(root.accent, 1.14) : root.accent)
    property color activeInk: SemanticTheme.readableInk(root.activeFill)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    width: 600
    height: 500
    modal: true
    focus: true
    dim: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onOpened: {
        loadBackups()
    }

    ListModel {
        id: backupsModel
    }

    function loadBackups() {
        backupsModel.clear()
        if (!root.appRef) return
        
        var resStr = root.appRef.listManagedBackups()
        try {
            var res = JSON.parse(resStr)
            if (res.ok && res.snapshots) {
                for (var i = 0; i < res.snapshots.length; i++) {
                    var s = res.snapshots[i]
                    backupsModel.append({
                        "pkgName": s.package_name || "",
                        "timestamp": s.timestamp_local || "",
                        "reason": s.reason || "",
                        "protected": !!s.protected
                    })
                }
            }
        } catch(e) {
            console.log("Failed to parse backups:", e)
        }
    }

    function formatTime(ts) {
        if (!ts) return "Unknown"
        var d = new Date(ts)
        if (isNaN(d)) return ts
        return d.toLocaleString()
    }

    background: SemanticPanel {
        t: root.t
        appStyle: root.appStyle
        role: "popup"
        tone: "neutral"
        radius: root.isProMode ? visualRules.radiusPopup : 12
        borderWidth: 1
        shadowEnabled: visualRules.shadowOpacity > 0
        shadowRadius: root.isProMode ? 0 : 12
        shadowSamples: root.isProMode ? 0 : 18
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Data, Backup & Recovery"
                color: root.menuInk
                font.pixelSize: 18
                font.weight: Font.Bold
                Layout.fillWidth: true
            }
            
            PillButton {
                t: root.t
                appStyle: root.appStyle
                text: "Refresh"
                onClicked: root.loadBackups()
            }
            
            PillButton {
                t: root.t
                appStyle: root.appStyle
                text: "Close"
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: SemanticTheme.alpha(root.menuInk, 0.14)
        }
        
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: "Application Version: " + (root.appRef ? root.appRef.appVersion : "Unknown")
                    color: SemanticTheme.alpha(root.menuInk, 0.7)
                    font.pixelSize: 12
                }
            }

            PillButton {
                t: root.t
                appStyle: root.appStyle
                primary: true
                text: "Back Up Now"
                onClicked: {
                    if (root.appRef) {
                        var resStr = root.appRef.createManagedBackup("Manual Backup", true)
                        try {
                            var res = JSON.parse(resStr)
                            if (res.ok) {
                                root.loadBackups()
                            }
                        } catch(e){}
                    }
                }
            }
            
            PillButton {
                t: root.t
                appStyle: root.appStyle
                text: "Open Recovery Utility"
                onClicked: {
                    if (root.appRef) {
                        root.appRef.openRecoveryUtility()
                    }
                }
            }
        }

        Text {
            text: "Recent Snapshots"
            color: root.menuInk
            font.pixelSize: 14
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: SemanticTheme.alpha(root.menuInk, 0.03)
            border.color: SemanticTheme.alpha(root.menuInk, 0.1)
            border.width: 1
            radius: 6

            ListView {
                id: lv
                anchors.fill: parent
                anchors.margins: 8
                model: backupsModel
                clip: true
                spacing: 8
                
                delegate: Rectangle {
                    required property var model
                    width: lv.width
                    height: 60
                    color: root.inactiveFill
                    radius: 4
                    border.width: 1
                    border.color: SemanticTheme.alpha(root.menuInk, 0.1)
                    
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 12
                        
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Text {
                                text: model.pkgName
                                color: root.menuInk
                                font.pixelSize: 13
                                font.weight: Font.Bold
                            }
                            RowLayout {
                                spacing: 8
                                Text {
                                    text: root.formatTime(model.timestamp)
                                    color: SemanticTheme.alpha(root.menuInk, 0.7)
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: model.reason
                                    color: SemanticTheme.alpha(root.menuInk, 0.7)
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: model.protected ? "🛡️ Protected" : "♻️ Rolling"
                                    color: model.protected ? SemanticTheme.accentPositive(root.t, root.appStyle) : SemanticTheme.alpha(root.menuInk, 0.7)
                                    font.pixelSize: 11
                                }
                            }
                        }
                        
                        PillButton {
                            t: root.t
                            appStyle: root.appStyle
                            text: model.protected ? "Unprotect" : "Protect"
                            onClicked: {
                                if (root.appRef) {
                                    root.appRef.protectManagedBackup(model.pkgName, !model.protected)
                                    root.loadBackups()
                                }
                            }
                        }
                        
                        PillButton {
                            t: root.t
                            appStyle: root.appStyle
                            text: "Restore..."
                            onClicked: {
                                confirmRestoreDialog.targetPkg = model.pkgName
                                confirmRestoreDialog.open()
                            }
                        }
                    }
                }
            }
        }
    }
    
    Popup {
        id: confirmRestoreDialog
        property string targetPkg: ""
        width: 400
        height: 250
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        
        background: SemanticPanel {
            t: root.t
            appStyle: root.appStyle
            role: "popup"
            tone: "neutral"
            radius: 8
            borderWidth: 1
            shadowEnabled: true
        }
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12
            
            Text {
                text: "WARNING: Prepare Restore"
                color: SemanticTheme.destructive(root.t, root.appStyle)
                font.pixelSize: 16
                font.weight: Font.Bold
                Layout.fillWidth: true
            }
            
            Text {
                text: "This will prepare to overwrite your active data with the backup:\n\n" + confirmRestoreDialog.targetPkg + "\n\nA pre-restore safety backup will be automatically generated.\n\nAre you absolutely sure?"
                color: root.menuInk
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
            
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 12
                
                PillButton {
                    t: root.t
                    appStyle: root.appStyle
                    text: "Cancel"
                    onClicked: confirmRestoreDialog.close()
                }
                
                PillButton {
                    t: root.t
                    appStyle: root.appStyle
                    text: "Prepare Restore"
                    onClicked: {
                        if (root.appRef) {
                            var resStr = root.appRef.prepareManagedRestore(confirmRestoreDialog.targetPkg)
                            try {
                                var res = JSON.parse(resStr)
                                if (res.ok) {
                                    confirmRestoreDialog.close()
                                    root.appRef.openRecoveryUtility()
                                }
                            } catch(e){}
                        }
                    }
                }
            }
        }
    }
}
