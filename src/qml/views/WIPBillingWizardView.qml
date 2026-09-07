pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import QtQuick.Window
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme
Item {
    id: root
    property var t
    property var windowRef
    property var sfxBus
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    // Backend reference
    property var billingBackend: (root.appRef && root.appRef.billing) ? root.appRef.billing : null

    // State
    property var idsToDraft: []
    property bool isReconcilingWip: false

    // Core Layout Metrics
    property real basePadding: 24
    // Design System Colors
    property color bgSurface: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color textColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color mutedColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    
    // Global Wait Cursor during operations
    MouseArea {
        anchors.fill: parent
        z: 9999
        acceptedButtons: Qt.NoButton
        hoverEnabled: true
        cursorShape: (root.isLoading || root.isBuildingInvoice) ? Qt.WaitCursor : Qt.ArrowCursor
        visible: root.isLoading || root.isBuildingInvoice
    }

    // Centered Animated Loading Indicator
    BusyIndicator {
        anchors.centerIn: parent
        z: 10000
        running: root.isLoading || root.isBuildingInvoice
        visible: running
        width: 64
        height: 64
    }

    SelectionRemovalNoticeDialog {
        id: selectionRemovalNotice
        t: root.t
        appStyle: root.appStyle
    }

    Popup {
        id: reconcileWipDialog
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 600
        height: 492
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose

        property int entryCount: 0
        property real selectedTotal: 0.0
        readonly property bool hasNonZeroTotal: Math.abs(selectedTotal) >= 0.005
        readonly property bool confirmationReady: reconciliationAcknowledgement.checked
            && (!hasNonZeroTotal || nonZeroReconciliationAcknowledgement.checked)

        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 10
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12

            Text {
                text: "Reconcile selected WIP"
                color: root.textColor
                font.pixelSize: 20
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "This records that " + reconcileWipDialog.entryCount
                    + " selected time or fee entr" + (reconcileWipDialog.entryCount === 1 ? "y has" : "ies have")
                    + " already been settled or billed elsewhere. It removes only those entries from WIP; it does not create, alter, reverse, or pay an invoice."
                color: root.mutedColor
                font.pixelSize: 13
            }

            Text {
                Layout.fillWidth: true
                text: "Selected WIP total: $" + reconcileWipDialog.selectedTotal.toLocaleString(Qt.locale("en_CA"), "f", 2)
                color: reconcileWipDialog.hasNonZeroTotal
                    ? SemanticTheme.tone(root.t, "warning", root.appStyle)
                    : root.mutedColor
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }

            Text {
                visible: reconcileWipDialog.hasNonZeroTotal
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "This selection does not net to $0.00. Reconciling it will remove this non-zero amount from unbilled WIP without creating or changing an invoice."
                color: SemanticTheme.tone(root.t, "warning", root.appStyle)
                font.pixelSize: 12
            }

            Text {
                text: "Destination invoice / reconciliation reference"
                color: root.textColor
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }

            TextField {
                id: reconciliationReferenceField
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                color: root.textColor
                placeholderText: "e.g., SEE SUFFOLK 26-0080"
                placeholderTextColor: root.mutedColor
                background: Rectangle {
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.color: reconciliationReferenceField.activeFocus ? root.accentColor : root.borderColor
                    radius: 6
                }
            }

            Text {
                text: "Reason (kept in the docket audit trail)"
                color: root.textColor
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }

            TextArea {
                id: reconciliationReasonField
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                color: root.textColor
                wrapMode: TextEdit.Wrap
                placeholderText: "Explain why this work is no longer billable from this matter."
                placeholderTextColor: root.mutedColor
                background: Rectangle {
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.color: reconciliationReasonField.activeFocus ? root.accentColor : root.borderColor
                    radius: 6
                }
            }

            CheckBox {
                id: reconciliationAcknowledgement
                Layout.fillWidth: true
                text: "I verified the destination invoice or reconciliation evidence."
                contentItem: Text {
                    text: reconciliationAcknowledgement.text
                    color: root.textColor
                    font.pixelSize: 13
                    leftPadding: reconciliationAcknowledgement.indicator.width + 8
                    verticalAlignment: Text.AlignVCenter
                }
            }

            CheckBox {
                id: nonZeroReconciliationAcknowledgement
                visible: reconcileWipDialog.hasNonZeroTotal
                Layout.fillWidth: true
                text: "I intentionally approve reconciling the non-zero total shown above."
                contentItem: Text {
                    text: nonZeroReconciliationAcknowledgement.text
                    color: root.textColor
                    font.pixelSize: 13
                    leftPadding: nonZeroReconciliationAcknowledgement.indicator.width + 8
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 38
                    radius: 6
                    color: "transparent"
                    border.color: root.borderColor
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Cancel"; color: root.textColor; font.pixelSize: 13 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: reconcileWipDialog.close()
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: 190
                    Layout.preferredHeight: 38
                    radius: 6
                    color: reconcileWipDialog.confirmationReady && !root.isReconcilingWip
                        ? SemanticTheme.buttonPrimary(root.t, root.appStyle)
                        : SemanticTheme.borderSubtle(root.t, root.appStyle)
                    Text {
                        anchors.centerIn: parent
                        text: root.isReconcilingWip ? "Reconciling…" : "Confirm Reconciliation"
                        color: reconcileWipDialog.confirmationReady && !root.isReconcilingWip
                            ? SemanticTheme.textOnPrimary(root.t, root.appStyle)
                            : root.mutedColor
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: reconcileWipDialog.confirmationReady && !root.isReconcilingWip
                            ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: root._confirmWipReconciliation()
                    }
                }
            }
        }
    }


    Popup {
        id: billingGroupingPromptDialog
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 520
        height: 240
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        
        property var idsToDraft: []
        property string clientIdToDraft: ""
        property string clientNameToDraft: ""
        
        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 8
        }
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            
            Text {
                text: "Multiple Matters Selected"
                color: root.textColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            
            Text {
                text: "You have selected time entries across multiple matters for the same client. How would you like to group these on the invoice?"
                color: root.textColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            
            Item { Layout.fillHeight: true }
            
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                
                // Cancel
                Rectangle {
                    Layout.preferredWidth: 100; Layout.preferredHeight: 36; radius: 4; border.color: root.borderColor; color: "transparent"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Cancel"; color: root.textColor; font.pixelSize: 14 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: billingGroupingPromptDialog.close() }
                }
                
                Item { Layout.fillWidth: true }
                
                // Separate by Matter
                Rectangle {
                    Layout.preferredWidth: 160; Layout.preferredHeight: 36; radius: 4; border.color: root.borderColor; color: "transparent"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Separate by Matter"; color: root.textColor; font.pixelSize: 14 }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root._beginDraft(
                                billingGroupingPromptDialog.clientIdToDraft,
                                billingGroupingPromptDialog.clientNameToDraft,
                                billingGroupingPromptDialog.idsToDraft,
                                "matter"
                            )
                            billingGroupingPromptDialog.close()
                        }
                    }
                }
                
                // Group into One
                Rectangle {
                    Layout.preferredWidth: 140; Layout.preferredHeight: 36; radius: 4; color: root.accentColor
                    Text { anchors.centerIn: parent; text: "Group into One"; color: SemanticTheme.textOnAccent(root.t, root.appStyle); font.weight: Font.Medium; font.pixelSize: 14 }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root._beginDraft(
                                billingGroupingPromptDialog.clientIdToDraft,
                                billingGroupingPromptDialog.clientNameToDraft,
                                billingGroupingPromptDialog.idsToDraft,
                                "client"
                            )
                            billingGroupingPromptDialog.close()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: jointBillToPromptDialog
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 560
        height: 330
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose

        property var idsToDraft: []
        property string clientIdToDraft: ""
        property string clientNameToDraft: ""
        property string groupingToDraft: "matter"
        property var recipientOptions: []
        property var selectedRecipient: ({})

        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12

            Text {
                text: "Select Invoice Recipient"
                color: root.textColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }

            Text {
                text: "This work is on a matter with multiple designated invoice recipients. Choose the client and address for this invoice."
                color: root.textColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            ComboBox {
                id: jointBillToRecipientCombo
                Layout.fillWidth: true
                model: jointBillToPromptDialog.recipientOptions
                textRole: "clientName"
                onActivated: {
                    jointBillToPromptDialog.selectedRecipient = jointBillToPromptDialog.recipientOptions[currentIndex] || ({})
                }
            }

            Text {
                Layout.fillWidth: true
                text: String(jointBillToPromptDialog.selectedRecipient.fullAddress || "")
                color: root.mutedColor
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    Layout.preferredWidth: 100; Layout.preferredHeight: 36; radius: 4; border.color: root.borderColor; color: "transparent"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Cancel"; color: root.textColor; font.pixelSize: 14 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: jointBillToPromptDialog.close() }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: 150; Layout.preferredHeight: 36; radius: 4; color: root.accentColor
                    Text { anchors.centerIn: parent; text: "Create Draft"; color: SemanticTheme.textOnAccent(root.t, root.appStyle); font.weight: Font.Medium; font.pixelSize: 14 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var recipient = jointBillToPromptDialog.selectedRecipient || ({})
                            if (!recipient.clientId) return
                            root.isBuildingInvoice = true
                            root.billingBackend.createDraftWithGroupingAndBillTo(
                                jointBillToPromptDialog.clientIdToDraft,
                                jointBillToPromptDialog.clientNameToDraft,
                                jointBillToPromptDialog.idsToDraft,
                                jointBillToPromptDialog.groupingToDraft,
                                recipient
                            )
                            if (root.isZenMode) root.isZenMode = false
                            jointBillToPromptDialog.close()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: billingGroupingErrorDialog
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 440
        height: 200
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        
        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 8
        }
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            
            Text {
                text: "Invalid Selection"
                color: root.textColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            
            Text {
                text: "You have selected entries belonging to multiple distinct clients. You can only create an invoice for one client at a time. Please adjust your selection."
                color: root.textColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            
            Item { Layout.fillHeight: true }
            
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                
                Item { Layout.fillWidth: true }
                
                Rectangle {
                    Layout.preferredWidth: 100; Layout.preferredHeight: 36; radius: 4; color: root.accentColor
                    Text { anchors.centerIn: parent; text: "OK"; color: SemanticTheme.textOnAccent(root.t, root.appStyle); font.weight: Font.Medium; font.pixelSize: 14 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: billingGroupingErrorDialog.close() }
                }
            }
        }
    }

    Popup {
        id: emptyWipSelectionDialog
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 460
        height: 210
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16

            Text {
                text: "No entries selected"
                color: root.textColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }

            Text {
                text: "Select at least one time docket or fee entry before creating a draft invoice."
                color: root.textColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 36
                    radius: 4
                    color: root.accentColor
                    Text {
                        anchors.centerIn: parent
                        text: "OK"
                        color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                        font.weight: Font.Medium
                        font.pixelSize: 14
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: emptyWipSelectionDialog.close()
                    }
                }
            }
        }
    }

    Menu {
        id: docketContextMenu
        width: 190
        modal: false
        property var docket: root.contextDocket

        background: Rectangle {
            color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
            border.color: root.borderColor
            border.width: 1
            radius: 6
        }

        MenuItem {
            id: deleteDocketMenuItem
            text: "Delete Docket"
            enabled: !!docketContextMenu.docket && !root.isLoading && !root.isBuildingInvoice
            onTriggered: root._requestContextDocketDeletion()

            contentItem: Label {
                text: deleteDocketMenuItem.text
                color: deleteDocketMenuItem.enabled
                    ? SemanticTheme.tone(root.t, "error", root.appStyle)
                    : root.mutedColor
                verticalAlignment: Text.AlignVCenter
                leftPadding: 12
            }
            background: Rectangle {
                color: deleteDocketMenuItem.highlighted
                    ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.12)
                    : "transparent"
                radius: 4
            }
        }
    }

    Popup {
        id: deleteDocketConfirmation
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 460
        height: 210
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 14

            Text {
                text: "Delete docket?"
                color: root.textColor
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }

            Text {
                text: {
                    var docket = root.contextDocket
                    if (!docket) return "This action cannot be undone."
                    var date = String(docket.date || "")
                    var description = String(docket.description || "this docket entry")
                    return "Permanently delete " + (date ? date + " — " : "") + description + "? This action cannot be undone."
                }
                color: root.mutedColor
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.fillHeight: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: 36
                    radius: 4
                    color: "transparent"
                    border.color: root.borderColor
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Cancel"
                        color: root.textColor
                        font.pixelSize: 14
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: deleteDocketConfirmation.close()
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 118
                    Layout.preferredHeight: 36
                    radius: 4
                    color: SemanticTheme.tone(root.t, "error", root.appStyle)
                    Text {
                        anchors.centerIn: parent
                        text: "Delete Docket"
                        color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                        font.pixelSize: 14
                        font.weight: Font.Medium
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            deleteDocketConfirmation.close()
                            root._deleteContextDocket()
                        }
                    }
                }
            }
        }
    }

    // State
    property var wipItems: []
    property var selectedIds: ({})
    // When a user-initiated operation removes records from WIP, the refresh
    // handler uses this explanation rather than silently discarding selection.
    property string pendingSelectionRemovalReason: ""
    // The row currently targeted by the right-click docket menu.  Keep this
    // separate from invoice selection so the menu always acts on one docket.
    property var contextDocket: null
    property int selectedCount: 0
    property real selectedTotal: 0.0
    property bool isLoading: false
    property bool isBuildingInvoice: false
    property string wipStatusText: "Preparing WIP workbench…"
    property string selectedClientFilter: ""
    property string selectedBillingClientFilter: ""
    property string _pendingClientIdToFilter: ""
    property bool isZenMode: false

    // Date Filtering State
    readonly property string beginningOfTime: "2025-01-01"
    property string fromDateFilter: ""
    property string toDateFilter: ""
    property string activeDatePreset: "all"
    property string datePickerTarget: "from"

    function todayIso() {
        return Qt.formatDate(new Date(), "yyyy-MM-dd")
    }

    function getLastDayOfPreviousMonth() {
        var now = new Date()
        var lastDay = new Date(now.getFullYear(), now.getMonth(), 0)
        return Qt.formatDate(lastDay, "yyyy-MM-dd")
    }

    function applyDatePreset(preset) {
        if (preset === "toDate") {
            root.fromDateFilter = root.beginningOfTime
            root.toDateFilter = root.todayIso()
            root.activeDatePreset = "toDate"
        } else if (preset === "lastMonth") {
            root.fromDateFilter = root.beginningOfTime
            root.toDateFilter = root.getLastDayOfPreviousMonth()
            root.activeDatePreset = "lastMonth"
        } else if (preset === "all") {
            root.fromDateFilter = ""
            root.toDateFilter = ""
            root.activeDatePreset = "all"
        }
        root.autoCheckFilterMatch()
    }

    function _syncDatePreset() {
        if (!root.fromDateFilter && !root.toDateFilter) {
            root.activeDatePreset = "all"
        } else if (root.fromDateFilter === root.beginningOfTime && root.toDateFilter === root.todayIso()) {
            root.activeDatePreset = "toDate"
        } else if (root.fromDateFilter === root.beginningOfTime && root.toDateFilter === root.getLastDayOfPreviousMonth()) {
            root.activeDatePreset = "lastMonth"
        } else {
            root.activeDatePreset = "custom"
        }
        root.autoCheckFilterMatch()
    }

    function parseIsoDateOrToday(textValue) {
        var textValueString = String(textValue || "").trim()
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(textValueString)
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year
                && candidate.getMonth() === monthIndex
                && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function openDatePicker(target, px, py) {
        root.datePickerTarget = target
        wipCalendarLoader.active = true
        Qt.callLater(function() {
            var calendar = wipCalendarLoader.item
            if (!calendar) return
            var val = target === "from" ? root.fromDateFilter : root.toDateFilter
            calendar.selectedDate = root.parseIsoDateOrToday(val)
            if (typeof calendar.openAt === "function") calendar.openAt(px, py)
            else if (typeof calendar.open === "function") calendar.open()
            else calendar.visible = true
        })
    }

    Loader {
        id: wipCalendarLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                metrics: null
                hostWindow: root.Window.window
                onDatePicked: function(d) {
                    var iso = Qt.formatDate(d, "yyyy-MM-dd")
                    if (root.datePickerTarget === "from") {
                        root.fromDateFilter = iso
                    } else {
                        root.toDateFilter = iso
                    }
                    root._syncDatePreset()
                    wipCalendarLoader.active = false
                }
                onVisibleChanged: {
                    if (!visible) {
                        wipCalendarLoader.active = false
                    }
                }
                onClosing: function(close_event) {
                    wipCalendarLoader.active = false
                }
            }
        }
    }

    // Computed: unique clients from WIP
    property var clientList: {
        if (!wipItems) return ["All Clients"]
        var seen = {}
        var list = []
        for (var i = 0; i < wipItems.length; i++) {
            var itemDate = String(wipItems[i].date || "").substring(0, 10)
            if (root.fromDateFilter && itemDate.length >= 10 && itemDate < root.fromDateFilter) continue
            if (root.toDateFilter && itemDate.length >= 10 && itemDate > root.toDateFilter) continue
            var bname = wipItems[i].parentName || wipItems[i].parentId || ""
            if (selectedBillingClientFilter && selectedBillingClientFilter !== "All Billing Clients" && bname !== selectedBillingClientFilter) {
                continue
            }
            var cname = wipItems[i].clientName || wipItems[i].clientId || ""
            if (cname && !seen[cname]) {
                seen[cname] = true
                list.push(cname)
            }
        }
        list.sort()
        return ["All Clients"].concat(list)
    }

    // Computed: unique billing clients from WIP
    property var billingClientList: {
        if (!wipItems) return ["All Billing Clients"]
        var seen = {}
        var list = []
        for (var i = 0; i < wipItems.length; i++) {
            var itemDate = String(wipItems[i].date || "").substring(0, 10)
            if (root.fromDateFilter && itemDate.length >= 10 && itemDate < root.fromDateFilter) continue
            if (root.toDateFilter && itemDate.length >= 10 && itemDate > root.toDateFilter) continue
            var cname = wipItems[i].clientName || wipItems[i].clientId || ""
            if (selectedClientFilter && selectedClientFilter !== "All Clients" && cname !== selectedClientFilter) {
                continue
            }
            var bname = wipItems[i].parentName || wipItems[i].parentId || ""
            if (bname && !seen[bname]) {
                seen[bname] = true
                list.push(bname)
            }
        }
        list.sort()
        return ["All Billing Clients"].concat(list)
    }

    // Computed: filtered items
    property var filteredItems: {
        if (!selectedClientFilter && !selectedBillingClientFilter && !root.fromDateFilter && !root.toDateFilter)
            return wipItems
        var out = []
        for (var i = 0; i < wipItems.length; i++) {
            var item = wipItems[i]
            var itemDate = String(item.date || "").substring(0, 10)
            if (root.fromDateFilter && itemDate.length >= 10 && itemDate < root.fromDateFilter) {
                continue
            }
            if (root.toDateFilter && itemDate.length >= 10 && itemDate > root.toDateFilter) {
                continue
            }
            var cname = item.clientName || item.clientId || ""
            var bname = item.parentName || item.parentId || ""
            var matchClient = (!selectedClientFilter || selectedClientFilter === "All Clients" || cname === selectedClientFilter)
            var matchBilling = (!selectedBillingClientFilter || selectedBillingClientFilter === "All Billing Clients" || bname === selectedBillingClientFilter)
            
            if (matchClient && matchBilling) {
                out.push(item)
            }
        }
        return out
    }

    // Column Management State
    property int columnRevision: 0
    property string sortCol: ""
    property bool sortAsc: true

    readonly property int tableColumnSpacingPx: 0
    readonly property int tableCellPadXPx: 16
    readonly property int tableResizeHandleWidthPx: 8

    property var columnModel: [
        { key: "selection", label: "✓", width: 40, minWidth: 40, align: "center", resizable: false, fill: false, visible: true },
        { key: "date", label: "DATE", width: 100, minWidth: 60, align: "left", resizable: true, fill: false, visible: true },
        { key: "client", label: "CLIENT", width: 180, minWidth: 100, align: "left", resizable: true, fill: false, visible: true },
        { key: "billing_client", label: "BILLING CLIENT", width: 180, minWidth: 100, align: "left", resizable: true, fill: false, visible: true },
        { key: "matter", label: "MATTER", width: 180, minWidth: 100, align: "left", resizable: true, fill: false, visible: true },
        { key: "description", label: "DESCRIPTION", width: 350, minWidth: 100, align: "left", resizable: true, fill: true, visible: true },
        { key: "hours", label: "HOURS", width: 70, minWidth: 70, align: "right", resizable: true, fill: false, visible: true },
        { key: "amount", label: "AMOUNT", width: 100, minWidth: 70, align: "right", resizable: true, fill: false, visible: true }
    ]
    
    function applyInitialState(state) {
        console.log("WIPBillingWizardView.applyInitialState called with state:", JSON.stringify(state));
        if (!state) return;
        var changed = false;
        if (state.selectedClientFilter !== undefined) {
            root.selectedClientFilter = String(state.selectedClientFilter || "");
        }
        if (state.selectedBillingClientFilter !== undefined) {
            root.selectedBillingClientFilter = String(state.selectedBillingClientFilter || "");
        }
        if (state.clientIdToDraft !== undefined && state.clientIdToDraft !== "ALL") {
            root._pendingClientIdToFilter = String(state.clientIdToDraft);
        }
        if (state.matterId) {
            root.selectedMatterId = state.matterId
        }
        if (state.fromDate !== undefined) {
            root.fromDateFilter = String(state.fromDate || "");
        }
        if (state.toDate !== undefined) {
            root.toDateFilter = String(state.toDate || "");
        }
        if (state.datePreset !== undefined) {
            root.activeDatePreset = String(state.datePreset || "");
        } else if (state.fromDate !== undefined || state.toDate !== undefined) {
            root._syncDatePreset();
        }
        root.autoCheckFilterMatch();
        
        // Component creation loads WIP once.  Returning to this tab uses the
        // controller's signature-checked cache instead of forcing an Excel
        // scan every time the user navigates here.
    }

    function snapshotState() {
        return {
            "selectedClientFilter": root.selectedClientFilter,
            "selectedBillingClientFilter": root.selectedBillingClientFilter,
            "clientIdToDraft": root._pendingClientIdToFilter || "ALL",
            "matterId": root.selectedMatterId,
            "fromDate": root.fromDateFilter,
            "toDate": root.toDateFilter,
            "datePreset": root.activeDatePreset
        }
    }

    // A route/state restore is not permission to discard a user's worklist.
    // Filters can hide selected rows, but they must not unselect them.
    function autoCheckFilterMatch() { }

    function applySort() {
        if (!sortCol) return
        var copy = wipItems.slice()
        copy.sort(function(a, b) {
            var valA = ""; var valB = "";
            if (sortCol === "date") { valA = a.date || ""; valB = b.date || ""; }
            else if (sortCol === "client") { valA = (a.clientName || a.clientId || "").toLowerCase(); valB = (b.clientName || b.clientId || "").toLowerCase(); }
            else if (sortCol === "billing_client") { valA = (a.parentName || a.parentId || "").toLowerCase(); valB = (b.parentName || b.parentId || "").toLowerCase(); }
            else if (sortCol === "matter") { valA = (a.matterName || a.matterId || "").toLowerCase(); valB = (b.matterName || b.matterId || "").toLowerCase(); }
            else if (sortCol === "description") { valA = (a.description || "").toLowerCase(); valB = (b.description || "").toLowerCase(); }
            else if (sortCol === "hours") { valA = a.hours || 0; valB = b.hours || 0; }
            else if (sortCol === "amount") { valA = a.net || 0; valB = b.net || 0; }
            
            var res = 0;
            if (valA < valB) res = -1;
            else if (valA > valB) res = 1;
            return sortAsc ? res : -res;
        })
        wipItems = copy
    }

    function toggleSort(colKey) {
        if (colKey === "selection") return
        if (sortCol === colKey) {
            sortAsc = !sortAsc
        } else {
            sortCol = colKey
            sortAsc = true
        }
        applySort()
    }

    Component.onCompleted: _loadWip(false)
    function _loadWip(forceRefresh) {
        if (!billingBackend) return
        isLoading = true
        billingBackend.loadUnbilledWip(!!forceRefresh)
    }
    function _setSelectedIds(nextIds) {
        var copy = ({})
        var count = 0
        var total = 0.0
        for (var key in nextIds) {
            if (nextIds[key] === undefined) continue
            copy[String(key)] = Number(nextIds[key] || 0.0)
            count++
            total += copy[String(key)]
        }
        selectedIds = copy
        selectedCount = count
        selectedTotal = total
    }

    function _toggleSelection(entryId, net) {
        var copy = {}
        for (var k in selectedIds) copy[k] = selectedIds[k]
        var key = String(entryId || "")
        if (copy[key] !== undefined) {
            delete copy[key]
        } else {
            copy[key] = Number(net || 0.0)
        }
        _setSelectedIds(copy)
    }
    function _selectAll() {
        var copy = {}
        // Select All adds the visible rows; it must not silently unselect
        // records that happen to be hidden by the current filters.
        for (var key in selectedIds) copy[key] = selectedIds[key]
        for (var i = 0; i < filteredItems.length; i++) {
            var item = filteredItems[i]
            copy[String(item.entryId)] = Number(item.net || 0.0)
        }
        _setSelectedIds(copy)
    }
    function _clearSelection() {
        _setSelectedIds(({}))
    }

    function _selectedWipRows() {
        var selected = []
        for (var i = 0; i < wipItems.length; i++) {
            var row = wipItems[i] || ({})
            if (selectedIds[String(row.entryId || "")] !== undefined) selected.push(row)
        }
        return selected
    }

    function _openWipReconciliation() {
        if (root.isReconcilingWip) return
        var selected = root._selectedWipRows()
        if (selected.length === 0) {
            emptyWipSelectionDialog.open()
            return
        }
        var references = ({})
        var onlyReference = ""
        for (var i = 0; i < selected.length; i++) {
            var reference = String(selected[i].invoiceRef || "").trim()
            if (reference.length > 0) references[reference] = true
        }
        var values = Object.keys(references)
        if (values.length === 1) onlyReference = values[0]
        reconcileWipDialog.entryCount = selected.length
        reconcileWipDialog.selectedTotal = root.selectedTotal
        reconciliationReferenceField.text = onlyReference
        reconciliationReasonField.text = ""
        reconciliationAcknowledgement.checked = false
        nonZeroReconciliationAcknowledgement.checked = false
        reconcileWipDialog.open()
    }

    function _confirmWipReconciliation() {
        if (root.isReconcilingWip || !reconciliationAcknowledgement.checked) return
        if (reconcileWipDialog.hasNonZeroTotal && !nonZeroReconciliationAcknowledgement.checked) return
        var reference = String(reconciliationReferenceField.text || "").trim()
        var reason = String(reconciliationReasonField.text || "").trim()
        if (reference.length === 0 || reason.length === 0) {
            appToast("Enter both the destination reference and a reconciliation reason.")
            return
        }
        if (!billingBackend || !billingBackend.reconcileWipEntries) {
            appToast("WIP reconciliation is unavailable. Please restart CSPM after installing the update.")
            return
        }
        var ids = []
        var selected = root._selectedWipRows()
        for (var i = 0; i < selected.length; i++) {
            var entryId = String(selected[i].entryId || "").trim()
            if (entryId.length > 0) ids.push(entryId)
        }
        root.isReconcilingWip = true
        var result = billingBackend.reconcileWipEntries(
            ids, reference, reason, !reconcileWipDialog.hasNonZeroTotal || nonZeroReconciliationAcknowledgement.checked
        )
        root.isReconcilingWip = false
        if (result && result.ok) {
            reconcileWipDialog.close()
            root.pendingSelectionRemovalReason = "You confirmed a WIP reconciliation, so these records are no longer eligible for billing."
            root._loadWip(true)
            appToast(String(result.message || "WIP reconciliation recorded."))
            return
        }
        appToast(String((result && result.message) || "WIP reconciliation could not be saved."))
    }

    function _openDocketContextMenu(entry, sourceItem, localX, localY) {
        if (!entry || !entry.entryId) return
        contextDocket = entry
        docketContextMenu.popup(sourceItem, localX, localY)
    }

    function _requestContextDocketDeletion() {
        if (!contextDocket || !contextDocket.entryId) return
        deleteDocketConfirmation.open()
    }

    function _deleteContextDocket() {
        if (!contextDocket || !contextDocket.entryId) return
        if (!appRef || !appRef.deleteTimeEntry) {
            return
        }

        var entryId = String(contextDocket.entryId)
        var result = appRef.deleteTimeEntry(entryId)
        if (result && result.ok) {
            contextDocket = null
            root.pendingSelectionRemovalReason = "You deleted a selected docket, so it is no longer eligible WIP."
            root._loadWip(true)
            return
        }

    }

    // Helper to force QML binding dependency on selectedIds dictionary
    function isRowSelected(id) {
        var dummy = root.selectedIds; // Force dependency tracking
        return dummy[String(id)] !== undefined;
    }

    function _selectClientFilter(value) {
        var nextValue = String(value || "")
        selectedClientFilter = (nextValue === "All Clients") ? "" : nextValue
        clientFilterPopup.close()
        autoCheckFilterMatch()
    }

    function _selectBillingClientFilter(value) {
        var nextValue = String(value || "")
        selectedBillingClientFilter = (nextValue === "All Billing Clients") ? "" : nextValue
        billingClientFilterPopup.close()
        autoCheckFilterMatch()
    }

    function _beginDraft(clientId, clientName, ids, grouping) {
        var recipients = []
        try {
            recipients = billingBackend && billingBackend.invoiceBillToOptions
                ? billingBackend.invoiceBillToOptions(ids) : []
        } catch (e) {
            appToast("Could not load the invoice recipient choices: " + String(e))
            return
        }
        if (recipients && recipients.length > 1) {
            jointBillToPromptDialog.idsToDraft = ids
            jointBillToPromptDialog.clientIdToDraft = String(clientId || "")
            jointBillToPromptDialog.clientNameToDraft = String(clientName || "")
            jointBillToPromptDialog.groupingToDraft = String(grouping || "matter")
            jointBillToPromptDialog.recipientOptions = recipients
            jointBillToPromptDialog.selectedRecipient = recipients[0] || ({})
            jointBillToRecipientCombo.currentIndex = 0
            jointBillToPromptDialog.open()
            return
        }
        root.isBuildingInvoice = true
        billingBackend.createDraftWithGrouping(clientId, clientName, ids, grouping)
        if (root.isZenMode) root.isZenMode = false
    }

    function _createDraft() {
        if (isBuildingInvoice) return
        if (!billingBackend) {
            appToast("Billing is not ready yet. Please try again in a moment.")
            return
        }
        if (selectedCount === 0) {
            emptyWipSelectionDialog.open()
            return
        }
        var ids = []
        var uniqueParents = {}
        var uniqueClients = {}
        var uniqueMatters = {}
        var parentCount = 0
        var clientCount = 0
        var matterCount = 0
        
        var primaryParentId = ""
        var primaryParentName = ""
        var primaryClientId = ""
        var primaryClientName = ""
        
        for (var i = 0; i < wipItems.length; i++) {
            var item = wipItems[i]
            if (selectedIds[item.entryId] !== undefined) {
                ids.push(item.entryId)
                
                if (!uniqueParents[item.parentId]) {
                    uniqueParents[item.parentId] = true
                    parentCount++
                    if (parentCount === 1) {
                        primaryParentId = item.parentId
                        primaryParentName = item.parentName || item.parentId
                    }
                }
                if (!uniqueClients[item.clientId]) {
                    uniqueClients[item.clientId] = true
                    clientCount++
                    if (clientCount === 1) {
                        primaryClientId = item.clientId
                        primaryClientName = item.clientName || item.clientId
                    }
                }
                if (!uniqueMatters[item.matterId]) {
                    uniqueMatters[item.matterId] = true
                    matterCount++
                }
            }
        }

        // The WIP list may have refreshed after a row was selected.  Treat a
        // stale selection exactly like an empty selection, without starting a
        // draft request or showing the blocking progress overlay.
        if (ids.length === 0) {
            root._clearSelection()
            emptyWipSelectionDialog.open()
            return
        }
        
        if (parentCount > 1) {
            billingGroupingErrorDialog.visible = true
            return
        }
        
        if (clientCount > 1) {
            // Group by client
            root._beginDraft(primaryParentId, primaryParentName, ids, "client")
            return
        }
        
        // If billed to a third-party, default to client grouping
        if (primaryParentId && primaryParentId !== primaryClientId) {
            root._beginDraft(primaryClientId, primaryClientName, ids, "client")
            return
        }
        
        if (matterCount > 1) {
            // Prompt for matter grouping
            billingGroupingPromptDialog.idsToDraft = ids
            billingGroupingPromptDialog.clientIdToDraft = primaryClientId
            billingGroupingPromptDialog.clientNameToDraft = primaryClientName
            billingGroupingPromptDialog.visible = true
            return
        }
        
        // Single matter, default behavior
        var defaultGrouping = (primaryParentId && primaryParentId !== primaryClientId) ? "client" : "matter"
        root._beginDraft(primaryClientId, primaryClientName, ids, defaultGrouping)
    }
    // Signal connections
    Connections {
        target: root.billingBackend
        function onWipLoadStatusChanged(message) {
            root.wipStatusText = String(message || "")
        }
        function onWipDataLoaded(data) {
            var priorSelection = root.selectedIds
            root.wipItems = data
            if (root.sortCol !== "") {
                root.applySort()
            }
            
            // Clean up selection
            var validIds = {}
            for (var i = 0; i < root.wipItems.length; i++) {
                validIds[String(root.wipItems[i].entryId)] = true
            }
            var newSelectedIds = {}
            var removedSelectionIds = []
            
            // Handle pending client filter
            if (root._pendingClientIdToFilter) {
                var foundName = "";
                for (var i = 0; i < root.wipItems.length; i++) {
                    if (String(root.wipItems[i].clientId) === root._pendingClientIdToFilter) {
                        foundName = root.wipItems[i].clientName;
                        break;
                    }
                }
                if (foundName) {
                    root.selectedClientFilter = foundName;
                }
                root._pendingClientIdToFilter = "";
            }

            // Handle pre-selections from idsToDraft
            if (root.idsToDraft && root.idsToDraft.length > 0) {
                for (var i = 0; i < root.idsToDraft.length; i++) {
                    var did = String(root.idsToDraft[i])
                    if (validIds[did]) {
                        // Find the net amount to store
                        for (var j = 0; j < root.wipItems.length; j++) {
                            if (String(root.wipItems[j].entryId) === did) {
                                newSelectedIds[did] = root.wipItems[j].net
                                break
                            }
                        }
                    }
                }
                root.idsToDraft = [] // Clear after applying
            }

            for (var k in priorSelection) {
                if (validIds[k]) {
                    // Recalculate with the refreshed amount, without losing
                    // the selection merely because the list was reloaded.
                    for (var refreshedIndex = 0; refreshedIndex < root.wipItems.length; refreshedIndex++) {
                        var refreshed = root.wipItems[refreshedIndex] || ({})
                        if (String(refreshed.entryId || "") === String(k)) {
                            newSelectedIds[k] = Number(refreshed.net || 0.0)
                            break
                        }
                    }
                } else {
                    removedSelectionIds.push(k)
                }
            }

            root._setSelectedIds(newSelectedIds)

            if (removedSelectionIds.length > 0) {
                var explanation = root.pendingSelectionRemovalReason
                if (!explanation.length) {
                    explanation = "The WIP worklist was refreshed and these dockets are no longer eligible. They may have been billed, reconciled, deleted, or changed in another screen."
                }
                selectionRemovalNotice.showRemoval(removedSelectionIds.length, "WIP docket", explanation)
            }
            root.pendingSelectionRemovalReason = ""

            root.isLoading = false
        }
        property string pendingDraftNumForPreview: ""

        function onDraftCreated(result) {
            if (!root.isBuildingInvoice) return
            
            if (result && result.ok === false) {
                root.isBuildingInvoice = false
                if (result.message) appToast("Could not create draft: " + String(result.message))
                return
            }
            root.pendingSelectionRemovalReason = "You created a draft invoice, so the selected dockets are now attached to that draft and are no longer unbilled WIP."
            root._loadWip(true)
            var draftNum = result.InvoiceNum || result.draftNum || (result.draft && result.draft.draftNum) || result.id || "";
            if (draftNum) {
                // Instead of navigating immediately, ask for the preview HTML and wait for it.
                // This keeps the "building invoice" animation running on this screen.
                pendingDraftNumForPreview = draftNum
                root.billingBackend.previewInvoiceHtml(draftNum, "Concept_A2")
            } else {
                root.isBuildingInvoice = false
            }
        }
        
        function onInvoiceHtmlReady(html) {
            if (pendingDraftNumForPreview) {
                var draftNum = pendingDraftNumForPreview
                pendingDraftNumForPreview = ""
                root.isBuildingInvoice = false
                
                var navTarget = null;
                if (root.windowRef && typeof root.windowRef.option3OpenWorkspaceForTile === 'function') {
                    navTarget = root.windowRef;
                } else if (root.windowRef && root.windowRef.mainContentRef && typeof root.windowRef.mainContentRef.option3OpenWorkspaceForTile === 'function') {
                    navTarget = root.windowRef.mainContentRef;
                }
                
                if (navTarget) {
                    Qt.callLater(function() {
                        navTarget.option3OpenWorkspaceForTile(2, "C03", {
                            draftNum: draftNum,
                            draftId: draftNum,
                            invoiceDraftId: draftNum,
                            focusNodeId: "C03",
                            option3EntityType: "invoice"
                        });
                    });
                } else {
                    appToast("Navigation failed: Unable to find MainContent reference.");
                }
            }
        }
        
        function onError(err) {
            root.isBuildingInvoice = false
            pendingDraftNumForPreview = ""
        }
    }
    
    Rectangle {
        id: buildingOverlay
        anchors.fill: parent
        color: SemanticTheme.overlayScrim(root.t, root.appStyle)
        visible: root.isBuildingInvoice
        z: 9999

        MouseArea {
            anchors.fill: parent
            // block clicks while building
        }

        Rectangle {
            anchors.centerIn: parent
            width: 300
            height: 120
            radius: 8
            color: root.panelColor
            border.color: root.accentColor
            border.width: 2
            
            Text {
                id: buildingText
                anchors.centerIn: parent
                property int dotCount: 0
                text: {
                    var dots = ""
                    for(var i=0; i<dotCount; i++) dots += " ."
                    return "Building invoice" + dots
                }
                color: root.textColor
                font.pixelSize: 16
                font.weight: Font.DemiBold
                Timer {
                    interval: 400
                    running: root.isBuildingInvoice
                    repeat: true
                    onTriggered: buildingText.dotCount = (buildingText.dotCount + 1) % 4
                }
            }
        }
    }

    Window {
        id: zenWindow
        title: "Zen Mode - WIP-to-Bill Workbench"
        color: root.bgSurface
        
        flags: Qt.Window

        onClosing: function(close_event) {
            root.isZenMode = false
            close_event.accepted = true
        }

        Item {
            id: popupContainer
            anchors.fill: parent
            anchors.margins: 24
        }
    }
    onIsZenModeChanged: {
        if (isZenMode) {
            var appWindow = root.Window.window
            if (appWindow) {
                zenWindow.transientParent = appWindow
                zenWindow.screen = appWindow.screen
            }
            zenWindow.showMaximized()
            zenWindow.requestActivate()
        } else {
            zenWindow.hide()
        }
    }
    Rectangle {
        id: bgRect
        anchors.fill: parent
        color: bgSurface
        Item {
            id: inlineContainer
            anchors.fill: parent
            anchors.margins: root.basePadding
        }
    }
    ColumnLayout {
        id: mainLayout
        parent: root.isZenMode ? popupContainer : inlineContainer
        width: parent.width
        height: parent.height
        spacing: 20
            // ── Toolbar Section ─────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                // Row 1: Entity Filters & Global Actions
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    // Client filter combo
                Rectangle {
                    id: clientFilterRect
                    width: 220
                    height: 36
                    radius: 6
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.color: borderColor
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 6
                        Text {
                            text: "▼"
                            color: mutedColor
                            font.pixelSize: 11
                        }
                        Text {
                            text: selectedClientFilter || "All Clients"
                            color: textColor
                            font.pixelSize: 13
                            font.family: "Inter"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !root.isBuildingInvoice
                        cursorShape: root.isBuildingInvoice ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: {
                            billingClientFilterPopup.close()
                            if (clientFilterPopup.visible) clientFilterPopup.close()
                            else clientFilterPopup.open()
                        }
                    }
                    Popup {
                        id: clientFilterPopup
                        x: 0
                        y: clientFilterRect.height + 4
                        width: Math.max(clientFilterRect.width, 260)
                        height: Math.min(clientFilterList.contentHeight + 38, 280)
                        padding: 1
                        modal: false
                        focus: true
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                        background: Rectangle {
                            color: root.panelColor
                            border.color: root.borderColor
                            border.width: 1
                            radius: 4
                        }
                        contentItem: ColumnLayout {
                            spacing: 0
                            Rectangle {
                                Layout.fillWidth: true
                                height: 36
                                color: root.panelColor
                                TextField {
                                    id: clientSearchField
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    placeholderText: "Search..."
                                    font.pixelSize: 13
                                    font.family: "Inter"
                                    color: root.textColor
                                    background: Rectangle { color: SemanticTheme.surfaceInput(root.t, root.appStyle); border.color: root.borderColor; radius: 4 }
                                    onVisibleChanged: {
                                        if (visible) {
                                            text = ""
                                            forceActiveFocus()
                                        }
                                    }
                                }
                            }
                            ListView {
                                id: clientFilterList
                                Layout.fillWidth: true
                                Layout.preferredHeight: Math.min(contentHeight, 240)
                                clip: true
                                model: {
                                    var txt = clientSearchField.text.toLowerCase()
                                    if (!txt) return root.clientList
                                    var res = []
                                    for (var i=0; i<root.clientList.length; i++) {
                                        if (String(root.clientList[i]).toLowerCase().indexOf(txt) !== -1) {
                                            res.push(root.clientList[i])
                                        }
                                    }
                                    return res
                                }
                                delegate: ItemDelegate {
                                    id: clientFilterDelegate
                                    required property var modelData
                                    readonly property string optionText: String(modelData || "")
                                    readonly property bool selectedRow: root.selectedClientFilter.length <= 0
                                        ? optionText === "All Clients"
                                        : root.selectedClientFilter === optionText
                                    width: clientFilterList.width
                                    height: 32
                                    hoverEnabled: true
                                    contentItem: RowLayout {
                                        spacing: 8
                                        Text {
                                            text: clientFilterDelegate.selectedRow ? "\uE73E" : ""
                                            color: root.accentColor
                                            font.family: "Segoe MDL2 Assets"
                                            font.pixelSize: 12
                                            Layout.preferredWidth: 16
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        Text {
                                            text: clientFilterDelegate.optionText
                                            color: root.textColor
                                            font.pixelSize: 13
                                            font.family: "Inter"
                                            elide: Text.ElideRight
                                            verticalAlignment: Text.AlignVCenter
                                            Layout.fillWidth: true
                                        }
                                    }
                                    background: Rectangle {
                                        color: clientFilterDelegate.hovered || clientFilterDelegate.selectedRow
                                            ? SemanticTheme.surfaceInput(root.t, root.appStyle)
                                            : "transparent"
                                    }
                                    onClicked: {
                                        root._selectClientFilter(optionText)
                                        clientFilterPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
                // Billing Client filter combo
                Rectangle {
                    id: billingClientFilterRect
                    width: 220
                    height: 36
                    radius: 6
                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                    border.color: borderColor
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 6
                        Text {
                            text: "▼"
                            color: mutedColor
                            font.pixelSize: 11
                        }
                        Text {
                            text: selectedBillingClientFilter || "All Billing Clients"
                            color: textColor
                            font.pixelSize: 13
                            font.family: "Inter"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !root.isBuildingInvoice
                        cursorShape: root.isBuildingInvoice ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: {
                            clientFilterPopup.close()
                            if (billingClientFilterPopup.visible) billingClientFilterPopup.close()
                            else billingClientFilterPopup.open()
                        }
                    }
                    Popup {
                        id: billingClientFilterPopup
                        x: 0
                        y: billingClientFilterRect.height + 4
                        width: Math.max(billingClientFilterRect.width, 280)
                        height: Math.min(billingClientFilterList.contentHeight + 38, 280)
                        padding: 1
                        modal: false
                        focus: true
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                        background: Rectangle {
                            color: root.panelColor
                            border.color: root.borderColor
                            border.width: 1
                            radius: 4
                        }
                        contentItem: ColumnLayout {
                            spacing: 0
                            Rectangle {
                                Layout.fillWidth: true
                                height: 36
                                color: root.panelColor
                                TextField {
                                    id: billingSearchField
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    placeholderText: "Search..."
                                    font.pixelSize: 13
                                    font.family: "Inter"
                                    color: root.textColor
                                    background: Rectangle { color: SemanticTheme.surfaceInput(root.t, root.appStyle); border.color: root.borderColor; radius: 4 }
                                    onVisibleChanged: {
                                        if (visible) {
                                            text = ""
                                            forceActiveFocus()
                                        }
                                    }
                                }
                            }
                            ListView {
                                id: billingClientFilterList
                                Layout.fillWidth: true
                                Layout.preferredHeight: Math.min(contentHeight, 240)
                                clip: true
                                model: {
                                    var txt = billingSearchField.text.toLowerCase()
                                    if (!txt) return root.billingClientList
                                    var res = []
                                    for (var i=0; i<root.billingClientList.length; i++) {
                                        if (String(root.billingClientList[i]).toLowerCase().indexOf(txt) !== -1) {
                                            res.push(root.billingClientList[i])
                                        }
                                    }
                                    return res
                                }
                                delegate: ItemDelegate {
                                    id: billingClientFilterDelegate
                                    required property var modelData
                                    readonly property string optionText: String(modelData || "")
                                    readonly property bool selectedRow: root.selectedBillingClientFilter.length <= 0
                                        ? optionText === "All Billing Clients"
                                        : root.selectedBillingClientFilter === optionText
                                    width: billingClientFilterList.width
                                    height: 32
                                    hoverEnabled: true
                                    contentItem: RowLayout {
                                        spacing: 8
                                        Text {
                                            text: billingClientFilterDelegate.selectedRow ? "\uE73E" : ""
                                            color: root.accentColor
                                            font.family: "Segoe MDL2 Assets"
                                            font.pixelSize: 12
                                            Layout.preferredWidth: 16
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        Text {
                                            text: billingClientFilterDelegate.optionText
                                            color: root.textColor
                                            font.pixelSize: 13
                                            font.family: "Inter"
                                            elide: Text.ElideRight
                                            verticalAlignment: Text.AlignVCenter
                                            Layout.fillWidth: true
                                        }
                                    }
                                    background: Rectangle {
                                        color: billingClientFilterDelegate.hovered || billingClientFilterDelegate.selectedRow
                                            ? SemanticTheme.surfaceInput(root.t, root.appStyle)
                                            : "transparent"
                                    }
                                    onClicked: {
                                        root._selectBillingClientFilter(optionText)
                                        billingClientFilterPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
                // Select All / Clear
                Rectangle {
                    width: 90
                    height: 36
                    radius: 6
                    color: "transparent"
                    border.color: borderColor
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Select All"
                        color: accentColor
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        font.family: "Inter"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._selectAll()
                    }
                }
                Rectangle {
                    width: 70
                    height: 36
                    radius: 6
                    color: "transparent"
                    border.color: borderColor
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Clear"
                        color: mutedColor
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        font.family: "Inter"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._clearSelection()
                    }
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: root.wipStatusText
                    color: root.mutedColor
                    font.pixelSize: 12
                    font.family: "Inter"
                    elide: Text.ElideRight
                    Layout.maximumWidth: 300
                    verticalAlignment: Text.AlignVCenter
                }
                // Refresh button
                Rectangle {
                    width: 36
                    height: 36
                    radius: 6
                    color: "transparent"
                    border.color: borderColor
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "↻"
                        color: textColor
                        font.pixelSize: 16
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._loadWip(true)
                    }
                }
                // Zen Mode Expand Button
                Rectangle {
                    visible: !root.isZenMode
                    width: 36
                    height: 36
                    radius: 6
                    color: "transparent"
                    border.color: root.borderColor
                    border.width: 1
                    
                    Text {
                        anchors.centerIn: parent
                        text: "⛶"
                        color: root.textColor
                        font.pixelSize: 18
                        font.weight: Font.Medium
                    }

                    MouseArea {
                        id: expandMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.isZenMode = true
                    }
                    ToolTip.visible: expandMouseArea.containsMouse
                    ToolTip.text: "Expand to Zen Mode Window"
                }
                }

                // Row 2: Date Filtering & Quick Presets
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "Period:"
                        color: root.mutedColor
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        font.family: "Inter"
                        verticalAlignment: Text.AlignVCenter
                    }

                    // From Date Input Box
                    Rectangle {
                        id: fromDateBox
                        width: 145
                        height: 34
                        radius: 6
                        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                        border.color: fromDateInput.activeFocus ? root.accentColor : root.borderColor
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 8
                            spacing: 4

                            TextField {
                                id: fromDateInput
                                text: root.fromDateFilter
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                font.pixelSize: 12
                                font.family: "Inter"
                                color: root.textColor
                                placeholderText: "From (YYYY-MM-DD)"
                                placeholderTextColor: root.mutedColor
                                verticalAlignment: TextInput.AlignVCenter
                                background: Item {}
                                padding: 0
                                leftPadding: 0
                                rightPadding: 0
                                topPadding: 0
                                bottomPadding: 0

                                onEditingFinished: {
                                    var val = text.trim()
                                    if (val === "" || /^\d{4}-\d{2}-\d{2}$/.test(val)) {
                                        root.fromDateFilter = val
                                        root._syncDatePreset()
                                    } else {
                                        text = root.fromDateFilter
                                    }
                                }
                                onAccepted: {
                                    focus = false
                                }
                            }

                            Text {
                                visible: root.fromDateFilter.length > 0
                                text: "✕"
                                color: fromClearMouseArea.containsMouse ? root.textColor : root.mutedColor
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                Layout.preferredWidth: 14
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    id: fromClearMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.fromDateFilter = ""
                                        root._syncDatePreset()
                                    }
                                }
                            }

                            Text {
                                text: "📅"
                                font.pixelSize: 13
                                Layout.preferredWidth: 20
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    id: fromCalMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var pt = typeof fromDateBox.mapToGlobal === "function"
                                            ? fromDateBox.mapToGlobal(0, fromDateBox.height)
                                            : fromDateBox.mapToItem(null, 0, fromDateBox.height)
                                        root.openDatePicker("from", pt.x, pt.y)
                                    }
                                }
                                ToolTip.visible: fromCalMouseArea.containsMouse
                                ToolTip.text: "Pick 'From' date"
                            }
                        }
                    }

                    Text {
                        text: "→"
                        color: root.mutedColor
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        verticalAlignment: Text.AlignVCenter
                    }

                    // To Date Input Box
                    Rectangle {
                        id: toDateBox
                        width: 145
                        height: 34
                        radius: 6
                        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                        border.color: toDateInput.activeFocus ? root.accentColor : root.borderColor
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 8
                            spacing: 4

                            TextField {
                                id: toDateInput
                                text: root.toDateFilter
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                font.pixelSize: 12
                                font.family: "Inter"
                                color: root.textColor
                                placeholderText: "To (YYYY-MM-DD)"
                                placeholderTextColor: root.mutedColor
                                verticalAlignment: TextInput.AlignVCenter
                                background: Item {}
                                padding: 0
                                leftPadding: 0
                                rightPadding: 0
                                topPadding: 0
                                bottomPadding: 0

                                onEditingFinished: {
                                    var val = text.trim()
                                    if (val === "" || /^\d{4}-\d{2}-\d{2}$/.test(val)) {
                                        root.toDateFilter = val
                                        root._syncDatePreset()
                                    } else {
                                        text = root.toDateFilter
                                    }
                                }
                                onAccepted: {
                                    focus = false
                                }
                            }

                            Text {
                                visible: root.toDateFilter.length > 0
                                text: "✕"
                                color: toClearMouseArea.containsMouse ? root.textColor : root.mutedColor
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                Layout.preferredWidth: 14
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    id: toClearMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.toDateFilter = ""
                                        root._syncDatePreset()
                                    }
                                }
                            }

                            Text {
                                text: "📅"
                                font.pixelSize: 13
                                Layout.preferredWidth: 20
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter

                                MouseArea {
                                    id: toCalMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var pt = typeof toDateBox.mapToGlobal === "function"
                                            ? toDateBox.mapToGlobal(0, toDateBox.height)
                                            : toDateBox.mapToItem(null, 0, toDateBox.height)
                                        root.openDatePicker("to", pt.x, pt.y)
                                    }
                                }
                                ToolTip.visible: toCalMouseArea.containsMouse
                                ToolTip.text: "Pick 'To' date"
                            }
                        }
                    }

                    // Divider
                    Rectangle {
                        width: 1
                        height: 20
                        color: root.borderColor
                        Layout.leftMargin: 4
                        Layout.rightMargin: 4
                    }

                    // Preset: To-Date
                    Rectangle {
                        id: toDateBtn
                        height: 34
                        width: toDateText.implicitWidth + 24
                        radius: 6
                        color: root.activeDatePreset === "toDate"
                            ? SemanticTheme.alpha(root.accentColor, 0.15)
                            : (toDateMouse.containsMouse ? SemanticTheme.buttonHover(root.t, root.appStyle) : "transparent")
                        border.color: root.activeDatePreset === "toDate" ? root.accentColor : root.borderColor
                        border.width: root.activeDatePreset === "toDate" ? 1.5 : 1

                        Text {
                            id: toDateText
                            anchors.centerIn: parent
                            text: "To-Date"
                            color: root.activeDatePreset === "toDate"
                                ? root.accentColor
                                : (toDateMouse.containsMouse ? root.textColor : root.mutedColor)
                            font.pixelSize: 12
                            font.weight: root.activeDatePreset === "toDate" ? Font.DemiBold : Font.Normal
                            font.family: "Inter"
                        }

                        MouseArea {
                            id: toDateMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.applyDatePreset("toDate")
                        }
                        ToolTip.visible: toDateMouse.containsMouse
                        ToolTip.text: "From 2025-01-01 through today (" + root.todayIso() + ")"
                    }

                    // Preset: Through Last Month
                    Rectangle {
                        id: lastMonthBtn
                        height: 34
                        width: lastMonthText.implicitWidth + 24
                        radius: 6
                        color: root.activeDatePreset === "lastMonth"
                            ? SemanticTheme.alpha(root.accentColor, 0.15)
                            : (lastMonthMouse.containsMouse ? SemanticTheme.buttonHover(root.t, root.appStyle) : "transparent")
                        border.color: root.activeDatePreset === "lastMonth" ? root.accentColor : root.borderColor
                        border.width: root.activeDatePreset === "lastMonth" ? 1.5 : 1

                        Text {
                            id: lastMonthText
                            anchors.centerIn: parent
                            text: "Through Last Month"
                            color: root.activeDatePreset === "lastMonth"
                                ? root.accentColor
                                : (lastMonthMouse.containsMouse ? root.textColor : root.mutedColor)
                            font.pixelSize: 12
                            font.weight: root.activeDatePreset === "lastMonth" ? Font.DemiBold : Font.Normal
                            font.family: "Inter"
                        }

                        MouseArea {
                            id: lastMonthMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.applyDatePreset("lastMonth")
                        }
                        ToolTip.visible: lastMonthMouse.containsMouse
                        ToolTip.text: "From 2025-01-01 through " + root.getLastDayOfPreviousMonth()
                    }

                    // Preset: All Dates
                    Rectangle {
                        id: allDatesBtn
                        height: 34
                        width: allDatesText.implicitWidth + 24
                        radius: 6
                        color: root.activeDatePreset === "all"
                            ? SemanticTheme.alpha(root.accentColor, 0.15)
                            : (allDatesMouse.containsMouse ? SemanticTheme.buttonHover(root.t, root.appStyle) : "transparent")
                        border.color: root.activeDatePreset === "all" ? root.accentColor : root.borderColor
                        border.width: root.activeDatePreset === "all" ? 1.5 : 1

                        Text {
                            id: allDatesText
                            anchors.centerIn: parent
                            text: "All Dates"
                            color: root.activeDatePreset === "all"
                                ? root.accentColor
                                : (allDatesMouse.containsMouse ? root.textColor : root.mutedColor)
                            font.pixelSize: 12
                            font.weight: root.activeDatePreset === "all" ? Font.DemiBold : Font.Normal
                            font.family: "Inter"
                        }

                        MouseArea {
                            id: allDatesMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.applyDatePreset("all")
                        }
                        ToolTip.visible: allDatesMouse.containsMouse
                        ToolTip.text: "Show entries across all dates without date restrictions"
                    }

                    Item { Layout.fillWidth: true }

                    // Counter of filtered entries
                    Text {
                        text: "Showing " + root.filteredItems.length + " of " + (root.wipItems ? root.wipItems.length : 0) + " entries"
                        color: root.mutedColor
                        font.pixelSize: 12
                        font.family: "Inter"
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Connections {
                    target: root
                    function onFromDateFilterChanged() {
                        if (fromDateInput.text !== root.fromDateFilter) {
                            fromDateInput.text = root.fromDateFilter
                        }
                    }
                    function onToDateFilterChanged() {
                        if (toDateInput.text !== root.toDateFilter) {
                            toDateInput.text = root.toDateFilter
                        }
                    }
                }
            }

            // ── WIP Table ───────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: SemanticTheme.tableRowBackground(root.t, root.appStyle)
                radius: 8
                border.color: SemanticTheme.tableRowHover(root.t, root.appStyle)
                border.width: 1
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6
                    // Table header
                    StandardTableHeader {
                        id: tableHeader
                        Layout.fillWidth: true
                            t: root.t
                            appStyle: root.appStyle
                            columns: root.columnModel
                            sortColumn: root.sortCol
                            sortAscending: root.sortAsc
                            columnMargin: 20
                            columnSpacing: 6
                            dragDropKey: "wipColumnReorder"
                            onSortRequested: function(key) { root.toggleSort(key) }
                            onConfigChanged: function(newCols) {
                                root.columnModel = newCols
                            }
                        }
                    // Loading state
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.isLoading
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 12
                            BusyIndicator {
                                Layout.alignment: Qt.AlignHCenter
                                running: root.isLoading
                            }
                            Text {
                                text: root.wipStatusText || "Loading unbilled WIP..."
                                color: root.mutedColor
                                font.pixelSize: 14
                                font.family: "Inter"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                    // Empty state
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !root.isLoading && root.filteredItems.length === 0
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 8
                            Text {
                                text: "No unbilled WIP found"
                                color: mutedColor
                                font.pixelSize: 16
                                font.family: "Inter"
                                font.weight: Font.Medium
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "All time entries are either billed or have an invoice reference."
                                color: mutedColor
                                font.pixelSize: 13
                                font.family: "Inter"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                    // Data rows
                    ListView {
                        id: wipList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !root.isLoading && root.filteredItems.length > 0
                        model: root.filteredItems
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        spacing: 4
                        delegate: Rectangle {
                            id: rowDelegate
                            required property var modelData
                            required property int index
                            width: wipList.width
                            height: 42
                            radius: 6
                            color: {
                                var isSelected = root.isRowSelected(modelData.entryId)
                                if (isSelected) return SemanticTheme.tableSelectedBackground(root.t, root.appStyle)
                                if (rowMouseArea.containsMouse) return SemanticTheme.tableRowHover(root.t, root.appStyle)
                                return index % 2 === 1 ? SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle) : SemanticTheme.tableRowBackground(root.t, root.appStyle)
                            }
                            border.color: {
                                var isSelected = root.isRowSelected(modelData.entryId)
                                if (isSelected) return SemanticTheme.borderStrong(root.t, root.appStyle)
                                return "transparent"
                            }
                            MouseArea {
                                id: rowMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                cursorShape: Qt.PointingHandCursor
                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        root._openDocketContextMenu(rowDelegate.modelData, rowDelegate, mouse.x, mouse.y)
                                    }
                                }
                                onClicked: function(mouse) {
                                    if (mouse.button === Qt.LeftButton) {
                                        root._toggleSelection(rowDelegate.modelData.entryId, rowDelegate.modelData.net)
                                    }
                                }
                                onDoubleClicked: function(mouse) {
                                    if (mouse.button !== Qt.LeftButton) return
                                    root._toggleSelection(rowDelegate.modelData.entryId, rowDelegate.modelData.net)
                                    var navTarget = null;
                                    if (root.windowRef && typeof root.windowRef.option3OpenWorkspaceForTile === "function") {
                                        navTarget = root.windowRef;
                                    } else if (root.windowRef && root.windowRef.mainContentRef) {
                                        navTarget = root.windowRef.mainContentRef;
                                    }
                                    if (navTarget) {
                                        navTarget.option3OpenWorkspaceForTile(1, "A02", {
                                            state: {
                                                editRowData: rowDelegate.modelData,
                                                returnToTileIndex: 2,
                                                returnToNodeId: "C01"
                                            }
                                        });
                                    }
                                }
                            }
                                Item {
                                    id: bodyRowContainer
                                    anchors.fill: parent
                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 20
                                        anchors.rightMargin: 0
                                        spacing: 6
                                        Repeater {
                                            model: columnModel
                                            delegate: Item {
                                                id: bodyCell
                                                required property var modelData
                                                required property int index
                                                visible: bodyCell.modelData.visible
                                                width: tableHeader.columnWidthFor(bodyCell.modelData.key)
                                                height: bodyRowContainer.height

                                                Item {
                                                    anchors.fill: parent
                                                    
                                                    // 1. Selection
                                                Rectangle {
                                                    visible: bodyCell.modelData.key === "selection"
                                                    anchors.centerIn: parent
                                                    width: 18; height: 18
                                                    radius: 4
                                                    color: root.isRowSelected(rowDelegate.modelData.entryId) ? root.accentColor : "transparent"
                                                    border.color: root.isRowSelected(rowDelegate.modelData.entryId) ? root.accentColor : root.borderColor
                                                    border.width: 1.5
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✓"
                                                        color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                        font.pixelSize: 12
                                                        font.weight: Font.Bold
                                                        visible: root.isRowSelected(rowDelegate.modelData.entryId)
                                                    }
                                                }

                                                // Draft Badge
                                                Rectangle {
                                                    id: draftBadge
                                                    visible: bodyCell.modelData.key === "description" && !!rowDelegate.modelData.invoiceRef
                                                    width: badgeText.width + 12
                                                    height: 20
                                                    radius: 4
                                                    color: SemanticTheme.tableRowHover(root.t, root.appStyle)
                                                    border.color: root.accentColor
                                                    border.width: 1
                                                    anchors.left: parent.left
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    Text {
                                                        id: badgeText
                                                        anchors.centerIn: parent
                                                        text: "DRAFT"
                                                        color: root.accentColor
                                                        font.pixelSize: 10
                                                        font.weight: Font.Bold
                                                    }
                                                    ToolTip.visible: badgeMouseArea.containsMouse
                                                    ToolTip.text: "Currently in " + (rowDelegate.modelData.invoiceRef || "")
                                                    MouseArea {
                                                        id: badgeMouseArea
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                    }
                                                }

                                                // 2. Text data
                                                Text {
                                                    visible: bodyCell.modelData.key !== "selection"
                                                    anchors.fill: parent
                                                    anchors.leftMargin: (bodyCell.modelData.key === "description" && !!rowDelegate.modelData.invoiceRef) ? (draftBadge.width + 6) : 0
                                                    anchors.rightMargin: (bodyCell.modelData.align === "right") ? ((bodyCell.modelData.resizable !== false && bodyCell.index < root.columnModel.length - 1) ? 21 : 7) : 0
                                                    verticalAlignment: Text.AlignVCenter
                                                    horizontalAlignment: bodyCell.modelData.align === "right" ? Text.AlignRight : (bodyCell.modelData.align === "center" ? Text.AlignHCenter : Text.AlignLeft)
                                                    elide: Text.ElideRight
                                                    font.pixelSize: Math.max(9, Math.round(13 * tableHeader.tableScale))
                                                    font.family: "Inter"
                                                    color: bodyCell.modelData.key === "matter" ? root.mutedColor : root.textColor
                                                    font.weight: bodyCell.modelData.key === "amount" ? Font.Medium : Font.Normal
                                                    
                                                    text: {
                                                        var item = rowDelegate.modelData
                                                        if (bodyCell.modelData.key === "date") return item.date || "";
                                                        if (bodyCell.modelData.key === "client") return item.clientName || item.clientId || "";
                                                        if (bodyCell.modelData.key === "billing_client") return item.parentName || item.parentId || "";
                                                        if (bodyCell.modelData.key === "matter") return item.matterName || item.matterId || "";
                                                        if (bodyCell.modelData.key === "description") return item.description || "";
                                                        if (bodyCell.modelData.key === "hours") return (item.hours || 0).toFixed(1);
                                                        if (bodyCell.modelData.key === "amount") return "$" + (item.net || 0).toLocaleString(Qt.locale("en_CA"), 'f', 2);
                                                        return ""
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            // ── Footer / Summary Bar ────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 56
                radius: 10
                color: panelColor
                border.color: borderColor
                border.width: 1
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 16
                    Text {
                        text: root.selectedCount + " entries selected"
                        color: textColor
                        font.pixelSize: 14
                        font.family: "Inter"
                        font.weight: Font.Medium
                    }
                    Rectangle {
                        width: 1; height: 24; color: borderColor
                    }
                    Text {
                        text: "Total: $" + root.selectedTotal.toLocaleString(Qt.locale("en_CA"), 'f', 2)
                        color: accentColor
                        font.pixelSize: 16
                        font.family: "Inter"
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        Layout.preferredWidth: 174
                        Layout.preferredHeight: 40
                        radius: 8
                        color: root.selectedCount > 0 && !root.isReconcilingWip
                            ? "transparent" : SemanticTheme.borderSubtle(root.t, root.appStyle)
                        border.color: root.borderColor
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Reconcile Selected"
                            color: root.selectedCount > 0 && !root.isReconcilingWip ? root.textColor : root.mutedColor
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.family: "Inter"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: root.selectedCount > 0 && !root.isReconcilingWip
                                ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: root._openWipReconciliation()
                        }
                    }
                    // Create Draft Button
                    Rectangle {
                        width: 200
                        height: 40
                        radius: 8
                        color: !root.isBuildingInvoice ? SemanticTheme.buttonPrimary(root.t, root.appStyle) : SemanticTheme.borderSubtle(root.t, root.appStyle)
                        Text {
                            anchors.centerIn: parent
                            text: root.isBuildingInvoice ? "Building..." : "Create Draft Invoice"
                            color: !root.isBuildingInvoice ? SemanticTheme.textOnPrimary(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.family: "Inter"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: !root.isBuildingInvoice ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (!root.isBuildingInvoice) {
                                    root._createDraft()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
