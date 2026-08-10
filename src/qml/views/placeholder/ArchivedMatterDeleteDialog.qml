pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"
import "../../standards/SemanticTheme.js" as SemanticTheme

Dialog {
    id: rootDialog
    title: "Permanently Delete Archived Matter"
    modal: true
    width: 550
    height: 294
    anchors.centerIn: parent
    standardButtons: Dialog.NoButton

    property var host: null
    property string matterId: ""
    property string matterLabel: ""
    property bool checking: false
    property bool canDelete: false
    property bool deleting: false
    property string statusMessage: "Checking linked records..."
    readonly property color destructiveTone: host
        ? SemanticTheme.destructive(host.t, host.appStyle)
        : "#b91c1c"

    function openFor(row) {
        var source = row || ({})
        rootDialog.matterId = String(source.matterId || "").trim()
        var number = String(source.matterNumber || "").trim()
        var name = String(source.displayName || source.matterName || "").trim()
        rootDialog.matterLabel = number.length > 0 && name.length > 0 ? number + " — " + name : (name || number || rootDialog.matterId)
        rootDialog.open()
    }

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

    function resetDeletedMatterSelection() {
        if (!rootDialog.host) return
        rootDialog.host.selectedMatterProfile = ({})
        rootDialog.host.selectedMatterId = ""
        rootDialog.host.selectedMatterName = ""
        rootDialog.host.matterProfileLookupMessage = "Archived matter permanently deleted."
    }

    function permanentlyDeleteArchivedMatter() {
        if (rootDialog.checking || rootDialog.deleting || !rootDialog.canDelete) return

        rootDialog.deleting = true
        var controller = rootDialog.host && rootDialog.host.appRef ? rootDialog.host.appRef : null
        var result = controller ? controller.deleteArchivedMatterProfile(rootDialog.matterId) : null
        if (result && result.ok) {
            rootDialog.resetDeletedMatterSelection()
            if (rootDialog.host && rootDialog.host.refreshMatterDirectory) {
                rootDialog.host.refreshMatterDirectory(false)
            }
            rootDialog.close()
            Qt.callLater(function() {
                rootDialog.showToast("Archived matter permanently deleted.", "success")
            })
            return
        }

        rootDialog.deleting = false
        rootDialog.statusMessage = "Deletion failed: "
            + (result && result.message ? String(result.message) : "Unknown error")
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
        rootDialog.checking = true
        rootDialog.canDelete = false
        rootDialog.deleting = false
        rootDialog.statusMessage = "Checking linked records..."

        var controller = rootDialog.host && rootDialog.host.appRef ? rootDialog.host.appRef : null
        var result = controller ? controller.checkMatterDependencies(rootDialog.matterId) : null
        rootDialog.checking = false

        if (result && result.ok && result.canDelete) {
            rootDialog.canDelete = true
            rootDialog.statusMessage = "No linked invoices, dockets, transactions, or trademarks remain.\nSelect Delete permanently to remove this archived matter. This cannot be undone."
        } else if (result && result.ok) {
            rootDialog.statusMessage = "Deletion is blocked because this archived matter still has "
                + String(result.totalDependencies || 0) + " linked record(s)."
        } else {
            rootDialog.statusMessage = result && result.message
                ? "Could not verify linked records: " + String(result.message)
                : "Could not verify linked records. Deletion is disabled for safety."
        }

        Qt.callLater(function() {
            cancelButton.forceActiveFocus()
        })
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Delete “" + rootDialog.matterLabel + "”?"
            color: rootDialog.host
                ? SemanticTheme.tone(rootDialog.host.t, "warning", rootDialog.host.appStyle)
                : "#b45309"
            font.pixelSize: 15
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            text: rootDialog.statusMessage
            color: rootDialog.host
                ? SemanticTheme.inkPrimary(rootDialog.host.t, rootDialog.host.appStyle)
                : "white"
            font.pixelSize: 13
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Item { Layout.fillWidth: true }

            PillButton {
                id: cancelButton
                t: rootDialog.host ? rootDialog.host.t : ({})
                metrics: rootDialog.host ? rootDialog.host.responsiveMetrics : ({})
                text: "Cancel"
                enabled: !rootDialog.deleting
                Layout.minimumWidth: 112
                Layout.preferredWidth: 120
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40
                focus: true
                onClicked: rootDialog.close()
            }

            Button {
                id: permanentDeleteButton
                text: rootDialog.deleting ? "Deleting…" : "Delete permanently"
                hoverEnabled: true
                enabled: rootDialog.canDelete && !rootDialog.checking && !rootDialog.deleting
                Layout.minimumWidth: 164
                Layout.preferredWidth: 172
                Layout.minimumHeight: 38
                Layout.preferredHeight: 40

                contentItem: Text {
                    text: permanentDeleteButton.text
                    color: SemanticTheme.readableInk(rootDialog.destructiveTone)
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: 4
                    color: !permanentDeleteButton.enabled
                        ? Qt.rgba(rootDialog.destructiveTone.r, rootDialog.destructiveTone.g, rootDialog.destructiveTone.b, 0.48)
                        : (permanentDeleteButton.down
                            ? Qt.darker(rootDialog.destructiveTone, 1.16)
                            : (permanentDeleteButton.hovered
                                ? SemanticTheme.destructiveHover(rootDialog.host ? rootDialog.host.t : ({}), rootDialog.host ? rootDialog.host.appStyle : "Professional")
                                : rootDialog.destructiveTone))
                    Behavior on color { ColorAnimation { duration: 120 } }
                }

                ToolTip.visible: hovered
                ToolTip.delay: 260
                ToolTip.text: "This action cannot be undone"
                onClicked: rootDialog.permanentlyDeleteArchivedMatter()
            }
        }
    }
}
