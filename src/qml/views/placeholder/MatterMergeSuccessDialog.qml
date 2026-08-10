pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"
import "../../standards/SemanticTheme.js" as SemanticTheme

Dialog {
    id: rootDialog
    title: "Merge Successful"
    modal: true
    width: 540
    height: rootDialog.deleteConfirmationVisible ? 316 : (rootDialog.actionFeedback.length > 0 ? 306 : 286)
    anchors.centerIn: parent
    standardButtons: Dialog.NoButton

    property var host: null
    property string sourceMatterId: ""
    property string targetMatterId: ""
    property bool checkComplete: false
    property bool canDelete: false
    property int totalDependencies: 0
    property bool deleteConfirmationVisible: false
    property bool actionInProgress: false
    property string dependencyStatusMessage: "Checking remaining records..."
    property string statusMessage: dependencyStatusMessage
    property string actionFeedback: ""
    property string actionFeedbackTone: "success"
    readonly property color destructiveTone: host
        ? SemanticTheme.destructive(host.t, host.appStyle)
        : "#b91c1c"

    function hostWindow() {
        try {
            return rootDialog.host ? rootDialog.host.Window.window : null
        } catch (e) {
            return null
        }
    }

    function showToast(message, tone) {
        var windowRef = rootDialog.hostWindow()
        if (windowRef && windowRef.showAppNotification) {
            windowRef.showAppNotification(String(message || ""), String(tone || "info"))
        }
    }

    function finishAction(message, tone) {
        rootDialog.actionInProgress = true
        rootDialog.actionFeedback = String(message || "")
        rootDialog.actionFeedbackTone = String(tone || "success")
        feedbackCloseTimer.restart()
    }

    function requestPermanentDelete() {
        rootDialog.deleteConfirmationVisible = true
        rootDialog.statusMessage = "Permanent deletion cannot be undone. Select Delete permanently to continue."
        Qt.callLater(function() {
            confirmDeleteButton.forceActiveFocus()
        })
    }

    function cancelPermanentDelete() {
        rootDialog.deleteConfirmationVisible = false
        rootDialog.statusMessage = rootDialog.dependencyStatusMessage
        Qt.callLater(function() {
            keepArchivedButton.forceActiveFocus()
        })
    }

    function permanentlyDeleteMatter() {
        if (rootDialog.actionInProgress) return

        rootDialog.actionInProgress = true
        var controller = rootDialog.host && rootDialog.host.appRef ? rootDialog.host.appRef : null
        var deleteResult = controller ? controller.deleteArchivedMatterProfile(rootDialog.sourceMatterId) : null
        if (deleteResult && deleteResult.ok) {
            rootDialog.finishAction("Old matter permanently deleted.", "success")
            return
        }

        rootDialog.actionInProgress = false
        rootDialog.statusMessage = "Error deleting matter: "
            + (deleteResult && deleteResult.message ? deleteResult.message : "Unknown error")
    }

    background: Rectangle {
        color: rootDialog.host
            ? SemanticTheme.surfacePanel(rootDialog.host.t, rootDialog.host.appStyle)
            : "#202020"
        border.width: 1
        border.color: rootDialog.host
            ? SemanticTheme.borderStrong(rootDialog.host.t, rootDialog.host.appStyle)
            : "#5d6b80"
        radius: 4
    }

    header: Label {
        text: rootDialog.title
        color: rootDialog.host
            ? SemanticTheme.inkPrimary(rootDialog.host.t, rootDialog.host.appStyle)
            : "white"
        font.bold: true
        font.pixelSize: 14
        padding: 14
        background: Rectangle {
            color: rootDialog.host
                ? SemanticTheme.surfaceRaised(rootDialog.host.t, rootDialog.host.appStyle)
                : "#282828"
        }
    }

    onOpened: {
        rootDialog.checkComplete = false
        rootDialog.canDelete = false
        rootDialog.deleteConfirmationVisible = false
        rootDialog.actionInProgress = false
        rootDialog.actionFeedback = ""
        rootDialog.dependencyStatusMessage = "Checking remaining records..."
        rootDialog.statusMessage = rootDialog.dependencyStatusMessage

        var controller = rootDialog.host && rootDialog.host.appRef ? rootDialog.host.appRef : null
        var result = controller ? controller.checkMatterDependencies(rootDialog.sourceMatterId) : null
        if (result && result.ok) {
            rootDialog.checkComplete = true
            rootDialog.canDelete = result.canDelete
            rootDialog.totalDependencies = result.totalDependencies
            rootDialog.dependencyStatusMessage = rootDialog.canDelete
                ? "This archived matter has no remaining invoices or dockets.\nWould you like to permanently delete it to keep your directory clean?"
                : "This matter cannot be permanently deleted because it still has "
                    + result.invoiceCount + " invoices and "
                    + (result.timeCount + result.disbursementCount) + " dockets attached."
        } else {
            rootDialog.checkComplete = true
            rootDialog.canDelete = false
            rootDialog.dependencyStatusMessage = result && result.message
                ? "Could not verify matter dependencies: " + result.message
                : "Could not verify matter dependencies. Deletion is disabled for safety."
        }
        rootDialog.statusMessage = rootDialog.dependencyStatusMessage
        Qt.callLater(function() {
            keepArchivedButton.forceActiveFocus()
        })
    }

    Timer {
        id: feedbackCloseTimer
        interval: 500
        repeat: false
        onTriggered: {
            var message = rootDialog.actionFeedback
            var tone = rootDialog.actionFeedbackTone
            rootDialog.close()
            Qt.callLater(function() {
                rootDialog.showToast(message, tone)
            })
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Matter successfully merged! The old matter has been archived."
            color: rootDialog.host
                ? SemanticTheme.tone(rootDialog.host.t, "success", rootDialog.host.appStyle)
                : "#2e7d32"
            font.pixelSize: 15
            font.bold: true
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Text {
            text: rootDialog.statusMessage
            color: rootDialog.host
                ? SemanticTheme.inkPrimary(rootDialog.host.t, rootDialog.host.appStyle)
                : "white"
            font.pixelSize: 13
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Rectangle {
            visible: rootDialog.actionFeedback.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 30 : 0
            radius: 3
            color: rootDialog.host
                ? SemanticTheme.surface(rootDialog.host.t, "dialog", rootDialog.actionFeedbackTone, rootDialog.host.appStyle)
                : "#203525"
            border.width: 1
            border.color: rootDialog.host
                ? SemanticTheme.border(rootDialog.host.t, "dialog", rootDialog.actionFeedbackTone, rootDialog.host.appStyle)
                : "#2e7d32"

            Text {
                anchors.fill: parent
                anchors.leftMargin: 9
                anchors.rightMargin: 9
                verticalAlignment: Text.AlignVCenter
                text: "✓  " + rootDialog.actionFeedback
                color: rootDialog.host
                    ? SemanticTheme.tone(rootDialog.host.t, rootDialog.actionFeedbackTone, rootDialog.host.appStyle)
                    : "#2e7d32"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            visible: !rootDialog.deleteConfirmationVisible
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 40 : 0
            spacing: 10

            Item { Layout.fillWidth: true }

            PillButton {
                id: keepArchivedButton
                t: rootDialog.host ? rootDialog.host.t : ({})
                metrics: rootDialog.host ? rootDialog.host.responsiveMetrics : ({})
                text: rootDialog.actionInProgress ? "Keeping archived…" : "Keep Archived"
                primary: true
                enabled: !rootDialog.actionInProgress
                Layout.minimumWidth: 144
                Layout.preferredWidth: 150
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40
                focus: true
                ToolTip.text: "Keep the source matter in the archived directory"
                onClicked: rootDialog.finishAction("Matter kept archived.", "success")
            }

            PillButton {
                t: rootDialog.host ? rootDialog.host.t : ({})
                metrics: rootDialog.host ? rootDialog.host.responsiveMetrics : ({})
                text: "Delete permanently…"
                visible: rootDialog.checkComplete && rootDialog.canDelete
                enabled: !rootDialog.actionInProgress
                Layout.minimumWidth: 156
                Layout.preferredWidth: 164
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40
                ToolTip.text: "Requires one more confirmation"
                onClicked: rootDialog.requestPermanentDelete()
            }
        }

        RowLayout {
            visible: rootDialog.deleteConfirmationVisible
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 40 : 0
            spacing: 10

            Item { Layout.fillWidth: true }

            PillButton {
                t: rootDialog.host ? rootDialog.host.t : ({})
                metrics: rootDialog.host ? rootDialog.host.responsiveMetrics : ({})
                text: "Cancel"
                enabled: !rootDialog.actionInProgress
                Layout.minimumWidth: 112
                Layout.preferredWidth: 120
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40
                onClicked: rootDialog.cancelPermanentDelete()
            }

            Button {
                id: confirmDeleteButton
                text: rootDialog.actionInProgress ? "Deleting…" : "Delete permanently"
                hoverEnabled: true
                enabled: !rootDialog.actionInProgress
                Layout.minimumWidth: 164
                Layout.preferredWidth: 172
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40

                contentItem: Text {
                    text: confirmDeleteButton.text
                    color: SemanticTheme.readableInk(rootDialog.destructiveTone)
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: 4
                    color: !confirmDeleteButton.enabled
                        ? Qt.rgba(rootDialog.destructiveTone.r, rootDialog.destructiveTone.g, rootDialog.destructiveTone.b, 0.48)
                        : (confirmDeleteButton.down
                            ? Qt.darker(rootDialog.destructiveTone, 1.16)
                            : (confirmDeleteButton.hovered
                                ? SemanticTheme.destructiveHover(rootDialog.host ? rootDialog.host.t : ({}), rootDialog.host ? rootDialog.host.appStyle : "Professional")
                                : rootDialog.destructiveTone))
                    Behavior on color { ColorAnimation { duration: 120 } }
                }

                ToolTip.visible: hovered
                ToolTip.delay: 260
                ToolTip.text: "This cannot be undone"
                onClicked: rootDialog.permanentlyDeleteMatter()
            }
        }
    }
}
