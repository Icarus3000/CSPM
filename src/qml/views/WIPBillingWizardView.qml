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
                            root.isBuildingInvoice = true
                            billingBackend.createDraftWithGrouping(billingGroupingPromptDialog.clientIdToDraft, billingGroupingPromptDialog.clientNameToDraft, billingGroupingPromptDialog.idsToDraft, "matter")
                            if (root.isZenMode) root.isZenMode = false
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
                            root.isBuildingInvoice = true
                            billingBackend.createDraftWithGrouping(billingGroupingPromptDialog.clientIdToDraft, billingGroupingPromptDialog.clientNameToDraft, billingGroupingPromptDialog.idsToDraft, "client")
                            if (root.isZenMode) root.isZenMode = false
                            billingGroupingPromptDialog.close()
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

    // State
    property var wipItems: []
    property var selectedIds: ({})
    property int selectedCount: 0
    property real selectedTotal: 0.0
    property bool isLoading: false
    property bool isBuildingInvoice: false
    property string selectedClientFilter: ""
    property string selectedBillingClientFilter: ""
    property string _pendingClientIdToFilter: ""
    property bool isZenMode: false
    // Computed: unique clients from WIP
    property var clientList: {
        if (!wipItems) return ["All Clients"]
        var seen = {}
        var list = []
        for (var i = 0; i < wipItems.length; i++) {
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
        if (!selectedClientFilter && !selectedBillingClientFilter)
            return wipItems
        var out = []
        for (var i = 0; i < wipItems.length; i++) {
            var cname = wipItems[i].clientName || wipItems[i].clientId || ""
            var bname = wipItems[i].parentName || wipItems[i].parentId || ""
            var matchClient = (!selectedClientFilter || selectedClientFilter === "All Clients" || cname === selectedClientFilter)
            var matchBilling = (!selectedBillingClientFilter || selectedBillingClientFilter === "All Billing Clients" || bname === selectedBillingClientFilter)
            
            if (matchClient && matchBilling) {
                out.push(wipItems[i])
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
        { key: "hours", label: "HOURS", width: 70, minWidth: 50, align: "right", resizable: true, fill: false, visible: true },
        { key: "amount", label: "AMOUNT", width: 100, minWidth: 60, align: "right", resizable: true, fill: false, visible: true }
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
            changed = true
        }
        root.autoCheckFilterMatch();
        if (changed) {
            root._loadWip();
        }
    }

    function autoCheckFilterMatch() { root._clearSelection() }

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

    Timer {
        id: initDelayTimer
        interval: 300
        repeat: false
        running: false
        onTriggered: {
            if (billingBackend) {
                billingBackend.loadUnbilledWip()
            }
        }
    }

    Component.onCompleted: _loadWip()
    function _loadWip(quiet) {
        if (!billingBackend) return
        if (!quiet) {
            isLoading = true
        }
        initDelayTimer.start()
    }
    function _toggleSelection(entryId, net) {
        var copy = {}
        for (var k in selectedIds) copy[k] = selectedIds[k]
        if (copy[entryId] !== undefined) {
            delete copy[entryId]
        } else {
            copy[entryId] = net
        }
        selectedIds = copy
        // Recount
        var count = 0; var total = 0.0
        for (var k2 in selectedIds) {
            count++
            total += selectedIds[k2]
        }
        selectedCount = count
        selectedTotal = total
    }
    function _selectAll() {
        var copy = {}
        for (var i = 0; i < filteredItems.length; i++) {
            var item = filteredItems[i]
            copy[item.entryId] = item.net
        }
        selectedIds = copy
        var count = 0; var total = 0.0
        for (var k in selectedIds) { count++; total += selectedIds[k] }
        selectedCount = count
        selectedTotal = total
    }
    function _clearSelection() {
        selectedIds = ({})
        selectedCount = 0
        selectedTotal = 0.0
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

    function _createDraft() {
        if (selectedCount === 0 || !billingBackend) return
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
        
        if (parentCount > 1) {
            billingGroupingErrorDialog.visible = true
            return
        }
        
        if (clientCount > 1) {
            // Group by client
            root.isBuildingInvoice = true
            billingBackend.createDraftWithGrouping(primaryParentId, primaryParentName, ids, "client")
            if (root.isZenMode) root.isZenMode = false
            return
        }
        
        // If billed to a third-party, default to client grouping
        if (primaryParentId && primaryParentId !== primaryClientId) {
            root.isBuildingInvoice = true
            billingBackend.createDraftWithGrouping(primaryClientId, primaryClientName, ids, "client")
            if (root.isZenMode) root.isZenMode = false
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
        root.isBuildingInvoice = true
        var defaultGrouping = (primaryParentId && primaryParentId !== primaryClientId) ? "client" : "matter"
        billingBackend.createDraftWithGrouping(primaryClientId, primaryClientName, ids, defaultGrouping)
        if (root.isZenMode) root.isZenMode = false
    }
    // Signal connections
    Connections {
        target: root.billingBackend
        function onWipDataLoaded(data) {
            root.wipItems = data
            if (root.sortCol !== "") {
                root.applySort()
            }
            
            // Clean up selection
            var validIds = {}
            for (var i = 0; i < root.wipItems.length; i++) {
                validIds[root.wipItems[i].entryId] = true
            }
            var newSelectedIds = {}
            var count = 0
            var total = 0.0
            
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

            for (var k in root.selectedIds) {
                if (validIds[k]) {
                    newSelectedIds[k] = root.selectedIds[k]
                }
            }
            
            for (var key in newSelectedIds) {
                count++
                total += newSelectedIds[key]
            }
            root.selectedIds = newSelectedIds
            root.selectedCount = count
            root.selectedTotal = total

            root.isLoading = false
        }
        function onDraftCreated(result) {
            if (!root.isBuildingInvoice) return
            root.isBuildingInvoice = false
            if (result && result.ok === false) {
                if (result.message) appToast("Could not create draft: " + String(result.message))
                return
            }
            root._clearSelection()
            root._loadWip()
            var draftNum = result.InvoiceNum || result.draftNum || (result.draft && result.draft.draftNum) || result.id || "";
            if (draftNum) {
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
            // ── Toolbar Row ─────────────────────────────────────────────
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
                        onClicked: root._loadWip()
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
                                text: "Loading unbilled WIP..."
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
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root._toggleSelection(rowDelegate.modelData.entryId, rowDelegate.modelData.net)
                                onDoubleClicked: {
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
                    // Create Draft Button
                    Rectangle {
                        width: 200
                        height: 40
                        radius: 8
                        color: (root.selectedCount > 0 && !root.isBuildingInvoice) ? SemanticTheme.buttonPrimary(root.t, root.appStyle) : SemanticTheme.borderSubtle(root.t, root.appStyle)
                        Text {
                            anchors.centerIn: parent
                            text: root.isBuildingInvoice ? "Building..." : "Create Draft Invoice"
                            color: (root.selectedCount > 0 && !root.isBuildingInvoice) ? SemanticTheme.textOnPrimary(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.family: "Inter"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: (root.selectedCount > 0 && !root.isBuildingInvoice) ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (root.selectedCount > 0 && !root.isBuildingInvoice) {
                                    root._createDraft()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
