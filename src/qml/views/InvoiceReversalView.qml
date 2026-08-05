import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import Qt.labs.platform 1.1
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    anchors.fill: parent

    property QtObject appController
    property QtObject windowRef
    property QtObject billingBackend: appController ? appController.billing : null

    property var t
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : (root.appController && root.appController.appStyle) ? String(root.appController.appStyle) : "Professional"
    property bool isProMode: root.appStyle === "Professional"

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    property color _bg: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _border: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color _primary: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _danger: SemanticTheme.tone(root.t, "error", root.appStyle)

    property var invoicesModel: []
    property string selectedInvoiceNum: ""
    property var selectedInvoiceData: null
    property var selectedInvoiceSummary: null
    property var _calInstance: null
    property bool _isEditingFinancials: false

    Component.onCompleted: {
        _loadInvoices()
    }

    function _loadInvoices() {
        if (!billingBackend) return
        var rawInvoices = billingBackend.listFinalizedInvoices()
        var filtered = []
        var query = (typeof searchInput !== "undefined" && searchInput) ? searchInput.text.toLowerCase() : ""

        // CSPM invoices match YY-NNNN pattern (e.g. 26-0070)
        var cspmRegex = /^\d{2}-\d{4}$/

        for (var i = 0; i < rawInvoices.length; i++) {
            var inv = rawInvoices[i]
            var num = String(inv.InvoiceNum || "")
            
            // Only include CSPM generated invoices (filter out vendor AP bills)
            if (!cspmRegex.test(num)) continue
            
            // Apply text search
            if (query !== "") {
                var cName = String(inv.ClientName || "").toLowerCase()
                var scName = String(inv.SubClient || "").toLowerCase()
                if (num.toLowerCase().indexOf(query) === -1 && 
                    cName.indexOf(query) === -1 && 
                    scName.indexOf(query) === -1) {
                    continue
                }
            }
            filtered.push(inv)
        }

        // Sort descending by invoice number
        filtered.sort(function(a, b) {
            var nA = String(a.InvoiceNum || "")
            var nB = String(b.InvoiceNum || "")
            return nA > nB ? -1 : (nA < nB ? 1 : 0)
        })
        invoicesModel = filtered
        
        if (selectedInvoiceNum) {
            var found = false
            for (var j = 0; j < invoicesModel.length; j++) {
                if (String(invoicesModel[j].InvoiceNum) === selectedInvoiceNum) {
                    selectedInvoiceData = invoicesModel[j]
                    found = true
                    break
                }
            }
            if (!found) {
                selectedInvoiceNum = ""
                selectedInvoiceData = null
            }
        }
    }

    function _selectInvoice(invNum) {
        if (selectedInvoiceNum === invNum) {
            selectedInvoiceNum = ""
            selectedInvoiceData = null
            selectedInvoiceSummary = null
            return
        }
        selectedInvoiceNum = invNum
        for (var i = 0; i < invoicesModel.length; i++) {
            if (String(invoicesModel[i].InvoiceNum) === invNum) {
                selectedInvoiceData = invoicesModel[i]
                if (root.billingBackend) {
                    selectedInvoiceSummary = root.billingBackend.getInvoiceSummary(invNum)
                }
                break
            }
        }
    }

    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)

    function applyJumpState(state) {
        if (!state) return
        var inv = String(state.selectedInvoiceNum || state.invoiceNum || state.entityId || state.invoiceId || "")
        if (inv.length > 0 && selectedInvoiceNum !== inv) {
            _selectInvoice(inv)
        }
    }

    // Connect to billingBackend signals if it exists
    Connections {
        target: root.billingBackend
        function onDraftReversed(result) {
            if (result.ok) {
                reverseDialog.visible = false
                selectedInvoiceNum = ""
                selectedInvoiceData = null
                _loadInvoices()
                
                if (result.newDraftNum) {
                    if (root.appRef && root.appRef.handleWorkspaceOpenRequested) {
                        root.appRef.handleWorkspaceOpenRequested(2, "C06", {
                            "draftNum": result.newDraftNum,
                            "selectedInvoiceNum": result.newDraftNum
                        })
                    }
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Left Pane: Invoice List
        Rectangle {
            Layout.preferredWidth: 350
            Layout.fillHeight: true
            color: root._bg
            border.color: root._border
            border.width: 1
            radius: visualRules.isPro ? visualRules.radiusPanel : 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "Finalized Invoices"
                    color: root._text
                    font.pixelSize: 16
                    font.bold: true
                }
                
                TextField {
                    id: searchInput
                    Layout.fillWidth: true
                    placeholderText: "Search invoice or client..."
                    color: root._text
                    placeholderTextColor: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    background: Rectangle {
                        color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._bg
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                    }
                    onTextChanged: root._loadInvoices()
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: root._border
                }

                ListView {
                    id: invoiceListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root.invoicesModel

                    delegate: Rectangle {
                        width: invoiceListView.width
                        height: 60
                        color: root.selectedInvoiceNum === (modelData.InvoiceNum || "") ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.16) : SemanticTheme.hoverOverlay(root.t, root.appStyle)) : "transparent"
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root._selectInvoice(modelData.InvoiceNum || "")
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 4
                            
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "Invoice " + (modelData.InvoiceNum || "Unknown")
                                    font.pixelSize: 14
                                    font.weight: Font.Medium
                                    color: root._text
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: (modelData.InvoiceDate || "").substring(0, 10)
                                    font.pixelSize: 12
                                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                                }
                            }

                            Text {
                                text: modelData.ClientName || "Unknown Client"
                                font.pixelSize: 13
                                color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                    
                    ScrollBar.vertical: ScrollBar { }
                }
            }
        }

        // Right Pane: Detail & Action
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.isProMode ? SemanticTheme.surfaceApp(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle) // soft premium background
            border.color: root._border
            border.width: 1
            radius: visualRules.isPro ? visualRules.radiusPanel : 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 24
                visible: !!root.selectedInvoiceData

                // Header Area
                RowLayout {
                    Layout.fillWidth: true
                    
                    ColumnLayout {
                        spacing: 4
                        Text {
                            text: "Invoice " + (root.selectedInvoiceData ? root.selectedInvoiceData.InvoiceNum : "")
                            font.pixelSize: 28
                            font.weight: Font.Bold
                            color: root._text
                        }
                        
                        RowLayout {
                            spacing: 8
                            Text { text: "Invoice Date:"; font.pixelSize: 14; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            property string displayDate: root.selectedInvoiceData ? (root.selectedInvoiceData.InvoiceDate || "").substring(0, 10) : ""
                            Text {
                                text: parent.displayDate === "" ? "Double-click to set" : parent.displayDate
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                color: parent.displayDate === "" ? root._primary : root._text
                                
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: {
                                        if (!root._calInstance) {
                                            var comp = Qt.createComponent("../components/JellyCalendar.qml")
                                            if (comp.status === Component.Ready) {
                                                root._calInstance = comp.createObject(root)
                                                root._calInstance.datePicked.connect(function(d) {
                                                    var tzOffset = (new Date()).getTimezoneOffset() * 60000;
                                                    var localISOTime = (new Date(d.getTime() - tzOffset)).toISOString().slice(0, -1);
                                                    var dateStr = localISOTime.substring(0, 10);
                                                    
                                                    if (root.appController && root.appController.docketing) {
                                                        root.appController.docketing.updateInvoiceLogEntry({
                                                            "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                                            "invoiceDate": dateStr
                                                        })
                                                        // Clone the object to trigger QML property bindings
                                                        var clone = Object.assign({}, root.selectedInvoiceData)
                                                        clone.InvoiceDate = dateStr
                                                        root.selectedInvoiceData = clone
                                                    }
                                                })
                                            }
                                        }
                                        if (root._calInstance) {
                                            var pt = mapToGlobal(width / 2, height / 2)
                                            if (parent.parent.displayDate !== "") {
                                                root._calInstance.selectedDate = new Date(parent.parent.displayDate + "T12:00:00")
                                            } else {
                                                root._calInstance.selectedDate = new Date()
                                            }
                                            root._calInstance.openAt(pt.x, pt.y)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.fillWidth: true } // spacer

                    // Status Badge
                    Rectangle {
                        property string st: root.selectedInvoiceSummary ? (root.selectedInvoiceSummary.Status || "Unknown") : ""
                        width: 100
                        height: 32
                        radius: visualRules.isPro ? 16 : 16
                        color: st === "Closed" || st === "Paid" ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "success", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "success", "Professional")) : (st === "Partial" ? (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "warning", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.alpha(SemanticTheme.tone(root.t, "error", root.appStyle), 0.16) : SemanticTheme.surface(root.t, "error", "Professional")))
                        border.color: st === "Closed" || st === "Paid" ? (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.border(root.t, "success", "Professional")) : (st === "Partial" ? (root.isProMode ? SemanticTheme.tone(root.t, "warning", root.appStyle) : SemanticTheme.border(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.border(root.t, "error", "Professional")))
                        border.width: 1
                        Layout.alignment: Qt.AlignTop | Qt.AlignRight
                        Text {
                            anchors.centerIn: parent
                            text: parent.st
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: parent.st === "Closed" || parent.st === "Paid" ? (root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.ink(root.t, "success", "Professional")) : (parent.st === "Partial" ? (root.isProMode ? SemanticTheme.tone(root.t, "warning", root.appStyle) : SemanticTheme.ink(root.t, "warning", "Professional")) : (root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.ink(root.t, "error", "Professional")))
                        }
                    }
                }

                // 3 Cards Layout
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 24

                    // Card 1: Client & Matters
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8
                            Text { text: "Client Details"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            Text {
                                text: root.selectedInvoiceSummary ? (root.selectedInvoiceSummary.ClientName || "") : ""
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                                color: root._text
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Item { height: 4 }
                            Text { text: "Matters:"; font.pixelSize: 12; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); visible: (root.selectedInvoiceSummary && root.selectedInvoiceSummary.Matters && root.selectedInvoiceSummary.Matters.length > 0) }
                            ListView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: root.selectedInvoiceSummary ? (root.selectedInvoiceSummary.Matters || []) : []
                                delegate: Text {
                                    text: "• " + modelData
                                    font.pixelSize: 13
                                    color: root._text
                                    elide: Text.ElideRight
                                    width: ListView.view.width
                                }
                            }
                            Item { Layout.fillHeight: true; visible: (!root.selectedInvoiceSummary || !root.selectedInvoiceSummary.Matters || root.selectedInvoiceSummary.Matters.length === 0) }
                        }
                    }

                    // Card 2: Financial Breakdown
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Financial Breakdown"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.fillWidth: true }
                                Text {
                                    text: root._isEditingFinancials ? "Cancel" : "Edit"
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: root._primary
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (root._isEditingFinancials) {
                                                root._isEditingFinancials = false
                                            } else {
                                                editFeesField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalFees || 0).toFixed(2) : "0.00"
                                                editDisbField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalDisbursements || 0).toFixed(2) : "0.00"
                                                editTaxField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.TotalTax || 0).toFixed(2) : "0.00"
                                                editBilledField.text = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.AggregateBilled || 0).toFixed(2) : "0.00"
                                                root._isEditingFinancials = true
                                            }
                                        }
                                    }
                                }
                            }
                            
                            GridLayout {
                                columns: 2
                                Layout.fillWidth: true
                                rowSpacing: root._isEditingFinancials ? 4 : 8
                                Text { text: "Fees:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalFees || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editFeesField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Text { text: "Disbursements:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalDisbursements || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editDisbField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Text { text: "Taxes:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle); Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.TotalTax || 0).toFixed(2) : "$0.00"; font.pixelSize: 13; font.weight: Font.Medium; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { 
                                        id: editTaxField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 13; horizontalAlignment: TextInput.AlignRight 
                                        color: root._text
                                        onTextChanged: {
                                            if (!root._isEditingFinancials) return
                                            var f = parseFloat(editFeesField.text) || 0
                                            var d = parseFloat(editDisbField.text) || 0
                                            var t = parseFloat(editTaxField.text) || 0
                                            editBilledField.text = (f + d + t).toFixed(2)
                                        }
                                    }
                                }
                                
                                Rectangle { Layout.columnSpan: 2; Layout.fillWidth: true; height: 1; color: root._border }
                                
                                Text { text: "Total Billed:"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; Layout.alignment: Qt.AlignVCenter }
                                Item {
                                    Layout.fillWidth: true; Layout.preferredHeight: root._isEditingFinancials ? 30 : 20
                                    Text { visible: !root._isEditingFinancials; text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.AggregateBilled || 0).toFixed(2) : "$0.00"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                                    TextField { id: editBilledField; visible: root._isEditingFinancials; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 100; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; horizontalAlignment: TextInput.AlignRight }
                                }
                                
                                Button {
                                    Layout.columnSpan: 2
                                    Layout.alignment: Qt.AlignRight
                                    visible: root._isEditingFinancials
                                    text: "Save Adjustments"
                                    onClicked: {
                                        if (root.appController && root.appController.docketing) {
                                            var newFees = parseFloat(editFeesField.text) || 0
                                            var newDisb = parseFloat(editDisbField.text) || 0
                                            var newTax = parseFloat(editTaxField.text) || 0
                                            var newBilled = parseFloat(editBilledField.text) || 0
                                            
                                            root.appController.docketing.updateInvoiceLogEntry({
                                                "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                                "totalFees": newFees,
                                                "totalDisbursements": newDisb,
                                                "totalTax": newTax,
                                                "aggregateBilled": newBilled
                                            })
                                            
                                            var clone = Object.assign({}, root.selectedInvoiceSummary)
                                            clone.TotalFees = newFees
                                            clone.TotalDisbursements = newDisb
                                            clone.TotalTax = newTax
                                            clone.AggregateBilled = newBilled
                                            
                                            var amtPaid = parseFloat(clone.AmountPaid || 0)
                                            var bal = newBilled - amtPaid
                                            if (bal <= 0.01 && bal >= -0.01) bal = 0
                                            clone.BalanceDue = bal
                                            
                                            root.selectedInvoiceSummary = clone
                                            
                                            root._isEditingFinancials = false
                                        }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    // Card 3: Ledger Status
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        radius: visualRules.isPro ? visualRules.radiusPanel : 8
                        border.color: root._border
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8
                            Text { text: "Ledger Status"; font.pixelSize: 12; font.weight: Font.Bold; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                            GridLayout {
                                columns: 2
                                Layout.fillWidth: true
                                rowSpacing: 16
                                
                                property int daysUnpaid: {
                                    if (!root.selectedInvoiceData || !root.selectedInvoiceSummary) return -1;
                                    var st = root.selectedInvoiceSummary.Status || "";
                                    if (st === "Closed" || st === "Paid") return -1;
                                    var dateStr = root.selectedInvoiceData.InvoiceDate;
                                    if (!dateStr) return -1;
                                    var d1 = new Date(dateStr.substring(0, 10));
                                    var d2 = new Date();
                                    var diffTime = d2.getTime() - d1.getTime();
                                    var diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
                                    return diffDays;
                                }

                                Text { text: "Amount Paid:"; font.pixelSize: 13; color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle) }
                                Text { 
                                    text: root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.AmountPaid || 0).toFixed(2) : "$0.00"
                                    font.pixelSize: 16; font.weight: Font.DemiBold; color: root.isProMode ? SemanticTheme.tone(root.t, "success", root.appStyle) : SemanticTheme.tone(root.t, "success", root.appStyle)
                                    Layout.alignment: Qt.AlignRight
                                }
                                
                                Rectangle { Layout.columnSpan: 2; Layout.fillWidth: true; height: 1; color: root._border }
                                
                                Text { text: "Balance Owing:"; font.pixelSize: 14; font.weight: Font.Bold; color: root._text; Layout.alignment: Qt.AlignTop }
                                ColumnLayout {
                                    Layout.alignment: Qt.AlignRight | Qt.AlignTop
                                    spacing: 2
                                    Text { 
                                        text: {
                                            if (root._isEditingFinancials) {
                                                var b = parseFloat(editBilledField.text) || 0
                                                var paid = root.selectedInvoiceSummary ? parseFloat(root.selectedInvoiceSummary.AmountPaid || 0) : 0
                                                var owing = b - paid
                                                if (owing <= 0.01 && owing >= -0.01) owing = 0
                                                return "$" + owing.toFixed(2)
                                            } else {
                                                return root.selectedInvoiceSummary ? "$" + parseFloat(root.selectedInvoiceSummary.BalanceDue || 0).toFixed(2) : "$0.00"
                                            }
                                        }
                                        font.pixelSize: 18; font.weight: Font.Bold; color: root._danger
                                        Layout.alignment: Qt.AlignRight
                                    }
                                    Text {
                                        text: parent.parent.daysUnpaid >= 0 ? "(" + parent.parent.daysUnpaid + " days outstanding)" : ""
                                        font.pixelSize: 12
                                        color: root.isProMode ? SemanticTheme.tone(root.t, "error", root.appStyle) : SemanticTheme.tone(root.t, "error", root.appStyle)
                                        font.italic: true
                                        visible: parent.parent.daysUnpaid >= 0
                                        Layout.alignment: Qt.AlignRight
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                Item { Layout.fillHeight: true } // push buttons to bottom

                // Bottom Action Buttons
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    spacing: 16

                    Rectangle {
                        width: 150
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Payment Entry"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.selectedInvoiceData) {
                                    root.workspaceOpenRequested(2, "C07", {
                                        "focusNodeId": "C07",
                                        "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                        "clientName": root.selectedInvoiceData.ClientName
                                    })
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: 180
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Write-off / Adj"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.selectedInvoiceData) {
                                    root.workspaceOpenRequested(2, "C09", {
                                        "focusNodeId": "C09",
                                        "invoiceNum": root.selectedInvoiceData.InvoiceNum,
                                        "clientName": root.selectedInvoiceData.ClientName
                                    })
                                }
                            }
                        }
                    }


                    Rectangle {
                        width: 150
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                        border.color: root._primary
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Open PDF"
                            color: root._primary
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.billingBackend && root.selectedInvoiceData) {
                                    root.billingBackend.openInvoicePdf(root.selectedInvoiceData.InvoiceNum)
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: 150
                        height: 44
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        color: root._danger
                        Text {
                            anchors.centerIn: parent
                            text: "Reverse Invoice"
                            color: root.isProMode ? SemanticTheme.readableInk(root._danger) : SemanticTheme.surfacePanel(root.t, root.appStyle)
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                reverseDialog.visible = true
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                anchors.centerIn: parent
                visible: !root.selectedInvoiceData
                spacing: 12
                
                Text {
                    text: "No Invoice Selected"
                    font.pixelSize: 20
                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: "Select a finalized invoice from the left to view details and reverse it."
                    font.pixelSize: 14
                    color: root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

    // Dialog for Reversal Options
    Rectangle {
        id: reverseDialog
        anchors.fill: parent
        color: "transparent"
        visible: false

        property string pdfAction: "move"
        property string targetDir: ""
        property string sourcePdfPath: ""

        MouseArea {
            anchors.fill: parent
            // block clicks behind
        }

        Rectangle {
            anchors.fill: parent
            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
            opacity: 0.4
        }

        Rectangle {
            width: 480
            height: 380
            anchors.centerIn: parent
            color: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : root._bg
            radius: visualRules.isPro ? visualRules.radiusPopup : 8
            border.color: root._border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16

                Text {
                    text: "Reverse Invoice " + (root.selectedInvoiceNum || "")
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                    color: root._text
                }

                Text {
                    text: "This will revert all associated time and disbursement entries back to unbilled, and remove the invoice from receivables and logs."
                    font.pixelSize: 14
                    color: root.isProMode ? SemanticTheme.inkMuted(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle)
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "What would you like to do with the generated PDF file?"
                    font.pixelSize: 14
                    font.weight: Font.Medium
                    color: root._text
                    Layout.topMargin: 8
                }

                ColumnLayout {
                    spacing: 8
                    Layout.fillWidth: true

                    RowLayout {
                        Layout.fillWidth: true
                        visible: reverseDialog.pdfAction !== "keep"
                        
                        Text { text: "Source PDF:"; font.pixelSize: 13; color: root._text; Layout.alignment: Qt.AlignVCenter }
                        
                        Rectangle {
                            Layout.fillWidth: true
                            height: 36
                            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
                            border.color: root._border
                            border.width: 1
                            radius: visualRules.isPro ? visualRules.radiusControl : 4
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: reverseDialog.sourcePdfPath !== "" ? reverseDialog.sourcePdfPath : "Select PDF file..."
                                color: reverseDialog.sourcePdfPath !== "" ? root._text : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle))
                                font.pixelSize: 13
                                elide: Text.ElideMiddle
                                width: parent.width - 16
                            }
                        }
                        
                        Rectangle {
                            width: 80
                            height: 36
                            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._border
                            radius: visualRules.isPro ? visualRules.radiusControl : 4
                            Text { anchors.centerIn: parent; text: "Browse"; font.pixelSize: 13; color: root._text }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: sourcePdfDialog.open()
                            }
                        }
                    }

                    RowLayout {
                        spacing: 8
                        RadioButton {
                            id: moveRadio
                            checked: true
                            onCheckedChanged: if (checked) reverseDialog.pdfAction = "move"
                        }
                        Text { text: "Move to folder (default: archive/REVERSED)"; font.pixelSize: 14; color: root._text }
                    }

                    RowLayout {
                        spacing: 8
                        visible: moveRadio.checked
                        Layout.leftMargin: 32
                        Layout.fillWidth: true
                        
                        Rectangle {
                            Layout.fillWidth: true
                            height: 36
                            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
                            border.color: root._border
                            border.width: 1
                            radius: visualRules.isPro ? visualRules.radiusControl : 4
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: reverseDialog.targetDir !== "" ? reverseDialog.targetDir : "Default REVERSED folder"
                                color: reverseDialog.targetDir !== "" ? root._text : (root.isProMode ? SemanticTheme.inkSubtle(root.t, root.appStyle) : SemanticTheme.inkMuted(root.t, root.appStyle))
                                font.pixelSize: 13
                                elide: Text.ElideMiddle
                                width: parent.width - 16
                            }
                        }

                        Rectangle {
                            width: 80
                            height: 36
                            color: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root._border
                            radius: visualRules.isPro ? visualRules.radiusControl : 4
                            Text { anchors.centerIn: parent; text: "Browse"; font.pixelSize: 13; color: root._text }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: targetFolderDialog.open()
                            }
                        }
                    }

                    RowLayout {
                        spacing: 8
                        RadioButton {
                            id: deleteRadio
                            onCheckedChanged: if (checked) reverseDialog.pdfAction = "delete"
                        }
                        Text { text: "Delete PDF permanently"; font.pixelSize: 14; color: root._text }
                    }

                    RowLayout {
                        spacing: 8
                        RadioButton {
                            id: keepRadio
                            onCheckedChanged: if (checked) reverseDialog.pdfAction = "keep"
                        }
                        Text { text: "Keep PDF in current folder"; font.pixelSize: 14; color: root._text }
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Layout.alignment: Qt.AlignRight

                    Rectangle {
                        width: 100
                        height: 36
                        color: "transparent"
                        border.color: root._border
                        border.width: 1
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Cancel"; color: root._text; font.pixelSize: 14 }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: reverseDialog.visible = false
                        }
                    }

                    Rectangle {
                        width: 140
                        height: 36
                        color: root._primary
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Reverse & Edit"; color: root.isProMode ? SemanticTheme.readableInk(root._primary) : SemanticTheme.surfacePanel(root.t, root.appStyle); font.pixelSize: 14; font.weight: Font.Medium }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.billingBackend) {
                                    root.billingBackend.reverseAndEditInvoice(root.selectedInvoiceNum, reverseDialog.sourcePdfPath, reverseDialog.pdfAction, reverseDialog.targetDir)
                                }
                            }
                        }
                    }
                    Rectangle {
                        width: 120
                        height: 36
                        color: root._danger
                        radius: visualRules.isPro ? visualRules.radiusControl : 4
                        Text { anchors.centerIn: parent; text: "Reverse Only"; color: root.isProMode ? SemanticTheme.readableInk(root._danger) : SemanticTheme.surfacePanel(root.t, root.appStyle); font.pixelSize: 14; font.weight: Font.Medium }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.billingBackend) {
                                    root.billingBackend.reverseInvoice(root.selectedInvoiceNum, reverseDialog.sourcePdfPath, reverseDialog.pdfAction, reverseDialog.targetDir)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    FolderDialog {
        id: targetFolderDialog
        title: "Select Archive Folder"
        onAccepted: {
            var p = targetFolderDialog.folder.toString()
            if (p.indexOf("file:///") === 0) {
                p = p.substring(8)
            }
            reverseDialog.targetDir = decodeURIComponent(p)
        }
    }
    
    FileDialog {
        id: sourcePdfDialog
        title: "Select Finalized Invoice PDF"
        nameFilters: ["PDF Files (*.pdf)", "All Files (*)"]
        onAccepted: {
            var p = sourcePdfDialog.file.toString()
            if (p.indexOf("file:///") === 0) {
                p = p.substring(8)
            }
            reverseDialog.sourcePdfPath = decodeURIComponent(p)
        }
    }
}
