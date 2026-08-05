pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme
import QtWebEngine
import QtCore
import QtQuick.Dialogs

Item {
    id: root
    property var t
    property var windowRef
    property var sfxBus
    property var appRef
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property bool isDark: SemanticTheme.isDarkMode(root.t)

    // Backend reference
    property var billingBackend: (root.appRef && root.appRef.billing) ? root.appRef.billing : null

    property bool zenModeOpen: false
    
    property string draftNum: ""
    onDraftNumChanged: {
        if (draftNum) {
            _loadDrafts()
            _selectDraft(draftNum)
        }
    }

    // Core Layout Metrics
    property real basePadding: 24

    // Design System Colors
    property color bgSurface: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color textColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color mutedColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color comboSurface: root.isDark ? "#333333" : "#ffffff"
    property color comboHoverSurface: root.isDark ? "#4a4a4a" : "#e8eef6"
    property color comboBorderColor: root.isDark ? "#666d78" : "#aeb9c7"

    // State
    property var draftsList: []
    property string selectedDraftNum: ""
    property var selectedDraftData: null
    property var draftLineItems: []
    property string previewHtml: ""
    property bool isLoading: false
    property string selectedConcept: "Concept_A2"
    property real docketedTimeTotal: {
        var total = 0
        for (var i = 0; i < root.draftLineItems.length; ++i) {
            var item = root.draftLineItems[i]
            if (!root._isCustomFeeItem(item)) total += Number(item.amount || 0)
        }
        return total
    }
    property real customFeeTotal: {
        var total = 0
        for (var i = 0; i < root.draftLineItems.length; ++i) {
            var item = root.draftLineItems[i]
            if (root._isCustomFeeItem(item)) total += Number(item.amount || 0)
        }
        return total
    }
    property bool hasCustomFees: root.customFeeTotal > 0
    property bool reconciliationRequired: root.hasCustomFees
                                        && root.customFeeTotal < root.docketedTimeTotal

    // Finalize state
    property bool isFinalizingExport: false
    property string pendingFinalizeInvoiceNum: ""
    property string pendingFinalizePath: ""
    property bool isFinalized: false

    Timer {
        id: autoCloseTimer
        interval: 2500
        repeat: false
        onTriggered: {
            var navTarget = null;
            if (root.windowRef && typeof root.windowRef.option3OpenWorkspaceForTile === 'function') {
                navTarget = root.windowRef;
            } else if (root.windowRef && root.windowRef.mainContentRef && typeof root.windowRef.mainContentRef.option3OpenWorkspaceForTile === 'function') {
                navTarget = root.windowRef.mainContentRef;
            }
            if (navTarget) {
                navTarget.option3OpenWorkspaceForTile(2, "C01", {});
            }
        }
    }

    property string finalInvoiceNum: ""

    property var _activeDateField: null
    function _isCustomFeeItem(item) {
        if (!item) return false
        return Number(item.hours || 0) === 0
                && Number(item.rate || 0) === 0
                && Number(item.amount || 0) > 0
    }

    function _reconciliationMode() {
        var value = root.selectedDraftData
                ? String(root.selectedDraftData.ReconciliationMode || "")
                : ""
        value = value.toLowerCase().replace(/[ _-]/g, "")
        return value === "discount" || value === "discountline"
                ? "discount_line" : "hidden_adjustment"
    }

    function _docketDisplayIndex() {
        var value = root.selectedDraftData
                ? String(root.selectedDraftData.DocketDisplayMode || "show").toLowerCase()
                : "show"
        if (value === "hide") return 1
        if (value === "tasks") return 2
        return 0
    }

    function _clearSelection() {
        root.selectedDraftNum = ""
        root.selectedDraftData = null
        root.draftLineItems = []
        root.previewHtml = ""
    }

    function openAddFeeDialog() {
        addFeeDialog.open()
    }
    function openDatePickerFor(field, px, py) {
        _activeDateField = field
        datePickerLoader.active = true
        Qt.callLater(function() {
            var cal = datePickerLoader.item
            if (!cal) return
            if (typeof cal["openAt"] === "function") cal["openAt"](px, py)
            else if (typeof cal["open"] === "function") cal["open"]()
            else cal.visible = true
        })
    }

    Loader {
        id: datePickerLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                metrics: root.appRef ? root.appRef.metrics : null
                hostWindow: root.Window.window
                onDatePicked: function(d) {
                    var iso = Qt.formatDate(d, "yyyy-MM-dd")
                    if (root._activeDateField) {
                        root._activeDateField.text = iso
                        if (root.billingBackend && root.selectedDraftNum) {
                            root.billingBackend.updateDraftDate(root.selectedDraftNum, iso)
                        }
                    }
                    datePickerLoader.active = false
                }
            }
        }
    }

    Component.onCompleted: {
        _loadDrafts()
        if (draftNum) {
            _selectDraft(draftNum)
        }
    }

    function _loadDrafts() {
        if (!billingBackend) return
        isLoading = true
        var result = billingBackend.listDrafts()
        draftsList = result || []
        isLoading = false
    }

    function _selectDraft(draftNum) {
        root.isFinalized = false
        root.finalInvoiceNum = ""
        if (!billingBackend) return
        selectedDraftNum = draftNum
        selectedDraftData = billingBackend.getDraft(draftNum)
        draftLineItems = billingBackend.getDraftLineItems(draftNum) || []
        billingBackend.previewInvoiceHtml(draftNum, root.selectedConcept)
    }

    function _finalizeDraft() {
        if (!billingBackend || !selectedDraftNum) return
        finalizeInvoiceDialog.inputInvoiceNum = billingBackend.nextInvoiceNumber()
        finalizeInvoiceDialog.validationError = ""
        finalizeInvoiceDialog.visible = true
    }

    function _deleteDraft() {
        _deleteDraftNumber(selectedDraftNum)
    }

    function _deleteDraftNumber(draftNumber) {
        var num = String(draftNumber || "").trim()
        if (!billingBackend || num.length <= 0) return false

        var res = null
        try {
            res = billingBackend.deleteDraft(num)
        } catch (e) {
            appToast("Failed to delete draft: " + e)
            return false
        }

        if (res && res.ok === false) {
            appToast("Failed to delete draft: " + (res.message ? String(res.message) : "Unknown error"))
            return false
        }

        if (root.selectedDraftNum === num) {
            root.selectedDraftNum = ""
            root.selectedDraftData = null
            root.draftLineItems = []
            root.previewHtml = ""
        }
        root._loadDrafts()
        return true
    }

    function _confirmFinalizeDraft() {
        if (!billingBackend || !selectedDraftNum) return
        var requestedNum = finalizeInvoiceDialog.inputInvoiceNum.trim()
        if (requestedNum === "") {
            finalizeInvoiceDialog.validationError = "Invoice number cannot be empty."
            return
        }
        
        var isUsed = billingBackend.isInvoiceNumberUsed(requestedNum)
        if (isUsed) {
            finalizeInvoiceDialog.validationError = "This invoice number has already been used!"
            return
        }
        
        finalizeInvoiceDialog.visible = false
        
        // Construct descriptive filename
        var safeClientName = ""
        var formattedDate = ""
        if (root.selectedDraftData) {
            var rawClient = root.selectedDraftData.ClientName || ""
            safeClientName = rawClient.replace(/[^a-zA-Z0-9\s-]/g, "").trim().replace(/\s+/g, " ")
            
            var rawDate = root.selectedDraftData.Date || ""
            if (rawDate.length >= 10) {
                var d = new Date(rawDate)
                if (!isNaN(d.getTime())) {
                    formattedDate = d.toLocaleDateString(Qt.locale(), "ddMMMyyyy").toUpperCase()
                }
            }
        }
        
        var fileName = "INV " + requestedNum
        if (safeClientName !== "") fileName += " - " + safeClientName
        if (formattedDate !== "") fileName += " - " + formattedDate
        fileName += ".pdf"
        
        // Open the save dialog for the finalize PDF
        finalizePdfFileDialog.currentFile = "file:///" + fileName
        root.pendingFinalizeInvoiceNum = requestedNum
        finalizePdfFileDialog.open()
    }

    Connections {
        target: root.billingBackend
        function onInvoiceHtmlReady(html) {
            root.previewHtml = html
        }
        function onDraftFinalized(result) {
            root.isFinalized = true
            root.finalInvoiceNum = result
            root._loadDrafts()
            
            // Fetch clean finalized HTML directly from backend to clear draft watermarks and update numbers
            var cleanHtml = root.billingBackend.getFinalizedHtml(root.selectedDraftNum, root.finalInvoiceNum);
            if (cleanHtml) {
                root.previewHtml = cleanHtml;
            }
            
            appToast("Invoice Finalized! Returning to WIP...")
            if (typeof autoCloseTimer !== 'undefined') {
                autoCloseTimer.start();
            }
        }
        function onDraftUpdated(draft) {
            if (!root.selectedDraftNum || !root.billingBackend) return
            var updatedDraftNum = draft ? (draft.InvoiceNum || draft.draftNum) : ""
            if (updatedDraftNum && String(updatedDraftNum) !== root.selectedDraftNum) return
            root.selectedDraftData = root.billingBackend.getDraft(root.selectedDraftNum) || draft || null
            root.draftLineItems = root.billingBackend.getDraftLineItems(root.selectedDraftNum) || []
            root.billingBackend.previewInvoiceHtml(root.selectedDraftNum, root.selectedConcept)
        }
        function onPdfExportFinished(path, success) {
            if (root.isFinalizingExport && success && path === root.pendingFinalizePath) {
                // PDF is saved successfully, now finalize in database
                root.billingBackend.finalizeDraft(root.selectedDraftNum, root.pendingFinalizeInvoiceNum, root.pendingFinalizePath)
                root.isFinalizingExport = false
                root.pendingFinalizeInvoiceNum = ""
                root.pendingFinalizePath = ""
            } else if (root.isFinalizingExport && !success) {
                // Reset state on failure
                root.isFinalizingExport = false
                root.pendingFinalizeInvoiceNum = ""
                root.pendingFinalizePath = ""
            }
        }
    }

    Rectangle {
        id: bgRect
        anchors.fill: parent
        color: bgSurface

        ColumnLayout {
            // Kept only as a source-safe fallback while the restored workspace below is active.
            // It is deliberately hidden so it cannot participate in sizing or render duplicate views.
            visible: false
            anchors.fill: parent
            anchors.margins: root.basePadding
            spacing: 20

            // ── Header ──────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Invoice Builder"
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                    font.family: "Inter"
                    color: textColor
                }
                Text {
                    text: "Review draft invoices, apply discounts, and generate final PDFs."
                    font.pixelSize: 14
                    font.family: "Inter"
                    color: mutedColor
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }

            // ── Main Content Area ───────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 20

                // ── Left Panel: Draft List ──────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 300
                    Layout.fillHeight: true
                    color: panelColor
                    radius: 10
                    border.color: borderColor
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            height: 40
                            color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                            radius: 10
                            Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 10; color: parent.color }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 16
                                text: "Draft Invoices"
                                color: textColor
                                font.pixelSize: 14
                                font.weight: Font.Medium
                            }
                            Rectangle { width: 30; height: 30; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; color: "transparent"; Text { anchors.centerIn: parent; text: "↻"; color: textColor; font.pixelSize: 16 } MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root._loadDrafts() } }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: borderColor }

                        ListView {
                            id: draftListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: root.draftsList
                            delegate: Rectangle {
                                required property var modelData
                                width: draftListView.width
                                height: 50
                                color: root.selectedDraftNum === (modelData.InvoiceNum || modelData.draftNum) ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.12) : "transparent"
                                border.color: root.borderColor
                                border.width: 1

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root._selectDraft((modelData.InvoiceNum || modelData.draftNum))
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 8
                                    
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            text: (modelData.InvoiceNum || modelData.draftNum)
                                            color: root.textColor
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: (modelData.ClientName || modelData.clientName) || "Unknown Client"
                                            color: root.mutedColor
                                            font.pixelSize: 11
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                    
                                    Rectangle {
                                        width: 24
                                        height: 24
                                        radius: 4
                                        color: delHover.containsMouse ? Qt.rgba(229/255, 115/255, 115/255, 0.15) : "transparent"
                                        Layout.alignment: Qt.AlignVCenter
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: "✕"
                                            color: "#E57373"
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                        }
                                        
                                        MouseArea {
                                            id: delHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var num = (modelData.InvoiceNum || modelData.draftNum)
                                                root._deleteDraftNumber(num)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Right Panel: Draft Details & Preview ────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: panelColor
                    radius: 10
                    border.color: borderColor
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 20

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: !root.selectedDraftNum

                            Text {
                                anchors.centerIn: parent
                                text: "Select a draft from the list to review."
                                color: mutedColor
                                font.pixelSize: 14
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: !!root.selectedDraftNum
                            spacing: 16

                            // Top action bar
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 16

                                Text {
                                    text: "Reviewing " + root.selectedDraftNum
                                    color: textColor
                                    font.pixelSize: 20
                                    font.weight: Font.DemiBold
                                }
                                Item { Layout.fillWidth: true }
                                
                                
                                // Editable Issue Date
                                Rectangle {
                                    id: dateOverrideRect
                                    width: 140
                                    height: 36
                                    color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                                    border.color: borderColor
                                    radius: 6
                                    TextInput {
                                        id: dateOverrideField
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: textColor
                                        text: (root.selectedDraftData && root.selectedDraftData.Date) ? root.selectedDraftData.Date.substring(0,10) : "2026-06-30"
                                        font.pixelSize: 13
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onDoubleClicked: root.openDatePickerFor(dateOverrideField, 0, 0)
                                    }
                                }
                            }

                            // --- DISCOUNT & AGENCY SPLIT CONTROLS ---
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: controlsCol.implicitHeight + 20
                                radius: 6
                                color: "transparent"
                                border.color: borderColor
                                
                                ColumnLayout {
                                    id: controlsCol
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.margins: 10
                                    spacing: 12
                                    
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 12

                                        ColumnLayout {
                                            spacing: 12
                                            
                                            // Top Row: Status
                                            RowLayout {
                                                spacing: 8
                                                Text {
                                                    text: "Applied Adjustment: "
                                                    color: textColor
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                    text: {
                                                        if (!root.selectedDraftData) return "None";
                                                        var t = String(root.selectedDraftData.DiscountType || "None");
                                                        var v = parseFloat(root.selectedDraftData.DiscountValue || 0);
                                                        var split = parseFloat(root.selectedDraftData.AgencySplitPercent || 0);
                                                        
                                                        var parts = [];
                                                        if (t === "Percentage" && v > 0) parts.push(v + "% Discount");
                                                        else if (t === "Flat" && v > 0) parts.push("$" + v.toFixed(2) + " Discount");
                                                        
                                                        if (split > 0) parts.push(split + "% Agency Split");
                                                        
                                                        return parts.length > 0 ? parts.join(" & ") : "None";
                                                    }
                                                    color: (text === "None") ? "#888888" : accentColor
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                }
                                                Rectangle {
                                                    width: 80
                                                    height: 24
                                                    radius: 4
                                                    color: "#FFF0F0"
                                                    border.color: "#FFCCCC"
                                                    visible: (root.selectedDraftData && ((root.selectedDraftData.DiscountType && root.selectedDraftData.DiscountType !== "None") || (parseFloat(root.selectedDraftData.AgencySplitPercent || 0) > 0)))
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "Clear"
                                                        color: "#CC0000"
                                                        font.pixelSize: 11
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: {
                                                            root.billingBackend.applyDiscount(root.selectedDraftNum, "None", 0)
                                                            root.billingBackend.applyAgencySplit(root.selectedDraftNum, 0)
                                                        }
                                                    }
                                                }
                                            }
                                            // Bottom Controls
                                            ColumnLayout {
                                                spacing: 12
                                                Layout.fillWidth: true

                                                // Row 1: Settings
                                                RowLayout {
                                                    spacing: 12

                                                    Text {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        text: "Grouping:"
                                                        color: textColor
                                                        font.pixelSize: 12
                                                    }
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 100
                                                        height: 30
                                                        border.color: borderColor
                                                        radius: 4
                                                        color: "transparent"
                                                        ComboBox {
                                                            id: groupingTypeCombo
                                                            anchors.fill: parent
                                                            model: ["Matter", "Client", "Combined"]
                                                            currentIndex: (root.selectedDraftData && root.selectedDraftData.GroupingPref) ? Math.max(0, ["matter", "client", "combined"].indexOf(root.selectedDraftData.GroupingPref.toLowerCase())) : 0
                                                            font.pixelSize: 12
                                                            contentItem: Text { leftPadding: 8; rightPadding: 24; text: groupingTypeCombo.displayText; color: root.textColor; font: groupingTypeCombo.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                                            indicator: Text { x: groupingTypeCombo.width - width - 8; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.mutedColor; font.pixelSize: 16 }
                                                            background: Rectangle { color: root.comboSurface; border.color: root.comboBorderColor; radius: 4 }
                                                            delegate: ItemDelegate {
                                                                width: groupingTypeCombo.width
                                                                contentItem: Text { text: modelData; color: root.textColor; font: groupingTypeCombo.font; verticalAlignment: Text.AlignVCenter }
                                                                background: Rectangle { color: groupingTypeCombo.highlightedIndex === index ? (root.isDark ? "#444" : "#e0e0e0") : (root.isDark ? "#333" : "#fff") }
                                                            }
                                                            popup: Popup {
                                                                y: groupingTypeCombo.height - 1
                                                                width: groupingTypeCombo.width
                                                                implicitHeight: contentItem.implicitHeight
                                                                padding: 1
                                                                contentItem: ListView { clip: true; implicitHeight: contentHeight; model: groupingTypeCombo.popup.visible ? groupingTypeCombo.delegateModel : null; currentIndex: groupingTypeCombo.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator { } }
                                                                background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: root.borderColor; radius: 4 }
                                                            }
                                                            onActivated: {
                                                                if (root.billingBackend) root.billingBackend.updateDraftGrouping(root.selectedDraftNum, currentText.toLowerCase())
                                                            }
                                                        }
                                                    }

                                                    Text {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        text: "Courtesy Discount:"
                                                        color: textColor
                                                        font.pixelSize: 12
                                                        Layout.leftMargin: 10
                                                    }
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 100
                                                        height: 30
                                                        border.color: borderColor
                                                        radius: 4
                                                        color: "transparent"
                                                        ComboBox {
                                                            id: discountTypeCombo
                                                            anchors.fill: parent
                                                            model: ["Percentage", "Fixed Amount"]
                                                            currentIndex: (root.selectedDraftData && root.selectedDraftData.DiscountType === "fixed") ? 1 : 0
                                                            font.pixelSize: 12
                                                            contentItem: Text { leftPadding: 8; rightPadding: 24; text: discountTypeCombo.displayText; color: root.textColor; font: discountTypeCombo.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                                            indicator: Text { x: discountTypeCombo.width - width - 8; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.mutedColor; font.pixelSize: 16 }
                                                            background: Rectangle { color: root.comboSurface; border.color: root.comboBorderColor; radius: 4 }
                                                            delegate: ItemDelegate {
                                                                width: discountTypeCombo.width
                                                                contentItem: Text { text: modelData; color: root.textColor; font: discountTypeCombo.font; verticalAlignment: Text.AlignVCenter }
                                                                background: Rectangle { color: discountTypeCombo.highlightedIndex === index ? (root.isDark ? "#444" : "#e0e0e0") : (root.isDark ? "#333" : "#fff") }
                                                            }
                                                            popup: Popup {
                                                                y: discountTypeCombo.height - 1
                                                                width: discountTypeCombo.width
                                                                implicitHeight: contentItem.implicitHeight
                                                                padding: 1
                                                                contentItem: ListView { clip: true; implicitHeight: contentHeight; model: discountTypeCombo.popup.visible ? discountTypeCombo.delegateModel : null; currentIndex: discountTypeCombo.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator { } }
                                                                background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: root.borderColor; radius: 4 }
                                                            }
                                                        }
                                                    }
                                                    TextField {
                                                        id: discountValInput
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 60
                                                        height: 30
                                                        font.pixelSize: 12
                                                        color: textColor
                                                        background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: borderColor; radius: 4 }
                                                        text: root.selectedDraftData ? (root.selectedDraftData.DiscountValue || "0.0") : "0.0"
                                                    }
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 60
                                                        height: 30
                                                        radius: 15
                                                        color: "transparent"
                                                        border.color: root.borderColor
                                                        border.width: 1
                                                        Text { anchors.centerIn: parent; text: "Apply"; color: root.textColor; font.pixelSize: 12 }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: root.billingBackend.applyDiscount(root.selectedDraftNum, discountTypeCombo.currentIndex === 0 ? "percentage" : "fixed", parseFloat(discountValInput.text) || 0)
                                                        }
                                                    }

                                                    Text {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        text: "Agency Split %:"
                                                        color: textColor
                                                        font.pixelSize: 12
                                                        Layout.leftMargin: 10
                                                    }
                                                    TextField {
                                                        id: agencySplitValInput
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 60
                                                        height: 30
                                                        font.pixelSize: 12
                                                        color: textColor
                                                        background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: borderColor; radius: 4 }
                                                        text: root.selectedDraftData ? (root.selectedDraftData.AgencySplitPercent || "0.0") : "0.0"
                                                    }
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 60
                                                        height: 30
                                                        radius: 15
                                                        color: "transparent"
                                                        border.color: root.borderColor
                                                        border.width: 1
                                                        Text { anchors.centerIn: parent; text: "Apply"; color: root.textColor; font.pixelSize: 12 }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: root.billingBackend.applyAgencySplit(root.selectedDraftNum, parseFloat(agencySplitValInput.text) || 0)
                                                        }
                                                    }
                                                    Item { Layout.fillWidth: true }
                                                }

                                                // Row 2: Action Buttons
                                                RowLayout {
                                                    spacing: 12
                                                    Layout.alignment: Qt.AlignRight

                                                    // Reconciliation Mode (Only visible if Custom Fee)
                                                    Text {
                                                        visible: root.hasCustomFees
                                                        Layout.alignment: Qt.AlignVCenter
                                                        text: "Reconciliation:"
                                                        color: root.textColor
                                                        font.pixelSize: 14
                                                    }
                                                    Rectangle {
                                                        visible: root.hasCustomFees
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 160
                                                        height: 36
                                                        border.color: root.borderColor
                                                        radius: 4
                                                        color: "transparent"
                                                        ComboBox {
                                                            id: reconciliationCombo
                                                            anchors.fill: parent
                                                            model: ["Discount Line", "Hidden Adjustment"]
                                                            currentIndex: (root.selectedDraftData && root.selectedDraftData.ReconciliationMode === "hidden") ? 1 : 0
                                                            font.pixelSize: 13
                                                            contentItem: Text { leftPadding: 8; rightPadding: 24; text: reconciliationCombo.displayText; color: root.textColor; font: reconciliationCombo.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                                            indicator: Text { x: reconciliationCombo.width - width - 8; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.mutedColor; font.pixelSize: 16 }
                                                            background: Rectangle { color: root.comboSurface; border.color: root.comboBorderColor; radius: 4 }
                                                            delegate: ItemDelegate {
                                                                width: reconciliationCombo.width
                                                                contentItem: Text { text: modelData; color: root.textColor; font: reconciliationCombo.font; verticalAlignment: Text.AlignVCenter }
                                                                background: Rectangle { color: reconciliationCombo.highlightedIndex === index ? (root.isDark ? "#444" : "#e0e0e0") : (root.isDark ? "#333" : "#fff") }
                                                            }
                                                            popup: Popup {
                                                                y: reconciliationCombo.height - 1
                                                                width: reconciliationCombo.width
                                                                implicitHeight: contentItem.implicitHeight
                                                                padding: 1
                                                                contentItem: ListView { clip: true; implicitHeight: contentHeight; model: reconciliationCombo.popup.visible ? reconciliationCombo.delegateModel : null; currentIndex: reconciliationCombo.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator { } }
                                                                background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: root.borderColor; radius: 4 }
                                                            }
                                                            onActivated: {
                                                                if (root.billingBackend) root.billingBackend.updateDraftReconciliationMode(root.selectedDraftNum, currentText === "Discount Line" ? "discount" : "hidden")
                                                            }
                                                        }
                                                    }

                                                    // Docket Display Combo (Only visible if Custom Fee)
                                                    Text {
                                                        visible: root.hasCustomFees
                                                        Layout.alignment: Qt.AlignVCenter
                                                        text: "Time Dockets:"
                                                        color: root.textColor
                                                        font.pixelSize: 14
                                                    }
                                                    Rectangle {
                                                        visible: root.hasCustomFees
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 150
                                                        height: 36
                                                        border.color: root.borderColor
                                                        radius: 4
                                                        color: "transparent"
                                                        ComboBox {
                                                            id: docketDisplayCombo
                                                            anchors.fill: parent
                                                            model: ["Show all", "Hide all", "Combine as tasks"]
                                                            currentIndex: 0
                                                            font.pixelSize: 13
                                                            contentItem: Text { leftPadding: 8; rightPadding: 24; text: docketDisplayCombo.displayText; color: root.textColor; font: docketDisplayCombo.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                                            indicator: Text { x: docketDisplayCombo.width - width - 8; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.mutedColor; font.pixelSize: 16 }
                                                            background: Rectangle { color: root.comboSurface; border.color: root.comboBorderColor; radius: 4 }
                                                            delegate: ItemDelegate {
                                                                width: docketDisplayCombo.width
                                                                contentItem: Text { text: modelData; color: root.textColor; font: docketDisplayCombo.font; verticalAlignment: Text.AlignVCenter }
                                                                background: Rectangle { color: docketDisplayCombo.highlightedIndex === index ? (root.isDark ? "#444" : "#e0e0e0") : (root.isDark ? "#333" : "#fff") }
                                                            }
                                                            popup: Popup {
                                                                y: docketDisplayCombo.height - 1
                                                                width: docketDisplayCombo.width
                                                                implicitHeight: contentItem.implicitHeight
                                                                padding: 1
                                                                contentItem: ListView { clip: true; implicitHeight: contentHeight; model: docketDisplayCombo.popup.visible ? docketDisplayCombo.delegateModel : null; currentIndex: docketDisplayCombo.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator { } }
                                                                background: Rectangle { color: root.isDark ? "#333" : "#fff"; border.color: root.borderColor; radius: 4 }
                                                            }
                                                        }
                                                    }

                                                    // Add Custom Fee
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 140
                                                        height: 36
                                                        radius: 18
                                                        color: "transparent"
                                                        border.color: root.accentColor
                                                        border.width: 1
                                                        Text { anchors.centerIn: parent; text: "Add Custom Fee"; color: root.accentColor; font.pixelSize: 14 }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: {
                                                                addFeeDialog.open()
                                                            }
                                                        }
                                                    }

                                                    // Cancel
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 100
                                                        height: 36
                                                        radius: 18
                                                        color: "transparent"
                                                        border.color: root.borderColor
                                                        border.width: 1
                                                        Text { anchors.centerIn: parent; text: "Cancel"; color: root.textColor; font.pixelSize: 14 }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: {
                                                                // Cancel logic
                                                            }
                                                        }
                                                    }

                                                    // Delete Draft
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 120
                                                        height: 36
                                                        radius: 18
                                                        color: "transparent"
                                                        border.color: "#ef4444"
                                                        border.width: 1
                                                        Text { anchors.centerIn: parent; text: "Delete Draft"; color: "#ef4444"; font.pixelSize: 14 }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: {
                                                                if (root.billingBackend) {
                                                                    root.billingBackend.deleteDraft(root.selectedDraftNum)
                                                                    root.draftNum = ""
                                                                    root.selectedDraftNum = ""
                                                                }
                                                            }
                                                        }
                                                    }

                                                    // Finalize Invoice
                                                    Rectangle {
                                                        Layout.alignment: Qt.AlignVCenter
                                                        width: 140
                                                        height: 36
                                                        radius: 18
                                                        color: root.isFinalized ? "#cccccc" : root.accentColor
                                                        Text { anchors.centerIn: parent; text: root.isFinalized ? "Finalized" : "Finalize Invoice"; color: SemanticTheme.surfacePanel(root.t, root.appStyle); font.weight: Font.Medium; font.pixelSize: 14 }
                                                        MouseArea {
                                                            anchors.fill: parent;
                                                            cursorShape: root.isFinalized ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                            onClicked: {
                                                                if (!root.isFinalized) {
                                                                    var dMode = "show"
                                                                    if (root.hasCustomFees) {
                                                                        if (docketDisplayCombo.currentIndex === 1) dMode = "hide";
                                                                        else if (docketDisplayCombo.currentIndex === 2) dMode = "tasks";
                                                                    }
                                                                    root._finalizeDraft(dMode)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                    }
                                }
                            }

                                // Left: Line items list
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 400
                                    color: "transparent"
                                    border.color: root.borderColor
                                    radius: 8

                                    ListView {
                                        id: docketsListView
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        model: root.draftLineItems
                                        clip: true
                                        delegate: Rectangle {
                                            id: itemDelegate
                                            required property var modelData
                                            width: docketsListView.width
                                            height: isEditing ? 80 : 50
                                            border.color: root.borderColor
                                            border.width: 1
                                            color: "transparent"
                                            property bool isEditing: false

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                visible: !itemDelegate.isEditing
                                                Text { text: modelData.date || ""; Layout.preferredWidth: 80; color: root.textColor; font.pixelSize: 12 }
                                                Text { text: modelData.description || ""; Layout.fillWidth: true; color: root.textColor; font.pixelSize: 12; elide: Text.ElideRight }
                                                Text { text: modelData.hours || "-"; Layout.preferredWidth: 40; color: root.textColor; font.pixelSize: 12; horizontalAlignment: Text.AlignRight }
                                                Text { text: "$" + Number(modelData.rate || 0).toFixed(2); Layout.preferredWidth: 60; color: root.textColor; font.pixelSize: 12; horizontalAlignment: Text.AlignRight }
                                                Text { text: "$" + Number(modelData.amount || 0).toFixed(2); Layout.preferredWidth: 80; color: root.textColor; font.pixelSize: 12; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight }
                                                PillButton {
                                                    t: root.t
                                                    text: "Edit"
                                                    primary: false
                                                    Layout.preferredWidth: 60
                                                    Layout.preferredHeight: 28
                                                    onClicked: itemDelegate.isEditing = true
                                                }
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                visible: itemDelegate.isEditing
                                                
                                                Rectangle {
                                                    Layout.preferredWidth: 90
                                                    Layout.preferredHeight: 32
                                                    color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                                    border.color: editDate.activeFocus ? root.accentColor : SemanticTheme.borderSubtle(root.t, root.appStyle)
                                                    border.width: editDate.activeFocus ? 2 : 1
                                                    radius: 4
                                                    TextInput {
                                                        id: editDate
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        verticalAlignment: TextInput.AlignVCenter
                                                        color: root.textColor
                                                        font.pixelSize: 13
                                                        text: modelData.date || ""
                                                        clip: true
                                                        TapHandler {
                                                            acceptedButtons: Qt.LeftButton
                                                            onDoubleTapped: function(eventPoint) {
                                                                var p = editDate.mapToGlobal(eventPoint.position.x, eventPoint.position.y)
                                                                root.openDatePickerFor(editDate, p.x, p.y)
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 32
                                                    color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                                    border.color: editDesc.activeFocus ? root.accentColor : SemanticTheme.borderSubtle(root.t, root.appStyle)
                                                    border.width: editDesc.activeFocus ? 2 : 1
                                                    radius: 4
                                                    TextInput {
                                                        id: editDesc
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        verticalAlignment: TextInput.AlignVCenter
                                                        color: root.textColor
                                                        font.pixelSize: 13
                                                        text: modelData.description || ""
                                                        clip: true
                                                    }
                                                }
                                                
                                                Rectangle {
                                                    Layout.preferredWidth: 40
                                                    Layout.preferredHeight: 32
                                                    color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                                    border.color: editHrs.activeFocus ? root.accentColor : SemanticTheme.borderSubtle(root.t, root.appStyle)
                                                    border.width: editHrs.activeFocus ? 2 : 1
                                                    radius: 4
                                                    TextInput {
                                                        id: editHrs
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        verticalAlignment: TextInput.AlignVCenter
                                                        color: root.textColor
                                                        font.pixelSize: 13
                                                        text: modelData.hours || "0"
                                                        clip: true
                                                    }
                                                }
                                                
                                                Rectangle {
                                                    Layout.preferredWidth: 60
                                                    Layout.preferredHeight: 32
                                                    color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                                    border.color: editRate.activeFocus ? root.accentColor : SemanticTheme.borderSubtle(root.t, root.appStyle)
                                                    border.width: editRate.activeFocus ? 2 : 1
                                                    radius: 4
                                                    TextInput {
                                                        id: editRate
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        verticalAlignment: TextInput.AlignVCenter
                                                        color: root.textColor
                                                        font.pixelSize: 13
                                                        text: modelData.rate || "0.00"
                                                        clip: true
                                                    }
                                                }
                                                
                                                Rectangle {
                                                    Layout.preferredWidth: 80
                                                    Layout.preferredHeight: 32
                                                    color: SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                                    border.color: editAmount.activeFocus ? root.accentColor : SemanticTheme.borderSubtle(root.t, root.appStyle)
                                                    border.width: editAmount.activeFocus ? 2 : 1
                                                    radius: 4
                                                    TextInput {
                                                        id: editAmount
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        verticalAlignment: TextInput.AlignVCenter
                                                        color: root.textColor
                                                        font.pixelSize: 13
                                                        text: modelData.amount || "0.00"
                                                        clip: true
                                                    }
                                                }
                                                PillButton {
                                                    text: "Save"
                                                    t: root.t
                                                    primary: true
                                                    Layout.preferredWidth: 60
                                                    Layout.preferredHeight: 32
                                                    onClicked: {
                                                        var data = {
                                                            "date": editDate.text,
                                                            "description": editDesc.text,
                                                            "hours": parseFloat(editHrs.text) || 0,
                                                            "rate": parseFloat(editRate.text) || 0,
                                                            "amount": parseFloat(editAmount.text) || 0
                                                        }
                                                        root.billingBackend.updateDraftLineItem(root.selectedDraftNum, itemDelegate.modelData.entryId, data)
                                                        itemDelegate.isEditing = false
                                                    }
                                                }
                                                PillButton {
                                                    text: "Remove"
                                                    t: root.t
                                                    primary: false
                                                    Layout.preferredWidth: 75
                                                    Layout.preferredHeight: 32
                                                    onClicked: root.billingBackend.removeDraftLineItem(root.selectedDraftNum, itemDelegate.modelData.entryId, false)
                                                }
                                                PillButton {
                                                    text: "Delete"
                                                    t: root.t
                                                    primary: false
                                                    Layout.preferredWidth: 70
                                                    Layout.preferredHeight: 32
                                                    onClicked: root.billingBackend.removeDraftLineItem(root.selectedDraftNum, itemDelegate.modelData.entryId, true)
                                                }
                                                PillButton {
                                                    text: "Cancel"
                                                    t: root.t
                                                    primary: false
                                                    Layout.preferredWidth: 70
                                                    Layout.preferredHeight: 32
                                                    onClicked: itemDelegate.isEditing = false
                                                }
                                            }
                                        }
                                        
                                        Item {
                                            width: docketsListView.width
                                            height: 60
                                            PillButton {
                                                anchors.centerIn: parent
                                                text: "+ Add New Docket"
                                                t: root.t
                                                primary: false
                                                Layout.preferredWidth: 150
                                                Layout.preferredHeight: 32
                                                onClicked: {
                                                    root.billingBackend.addDraftLineItem(root.selectedDraftNum, {
                                                        "date": Qt.formatDate(new Date(), "yyyy-MM-dd"),
                                                        "description": "New Time Entry",
                                                        "hours": 0.0,
                                                        "rate": 0.0,
                                                        "matterId": "General"
                                                    })
                                                }
                                            }
                                        }
                                    }
                                }

                                // Right: Small Preview
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                                    border.color: root.borderColor
                                    border.width: 1
                                    radius: 8
                                    clip: true

                                    WebEngineView {
                                        id: webView
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        backgroundColor: "transparent"
                                        
                                        Connections {
                                            target: root
                                            function onPreviewHtmlChanged() {
                                                if (root.previewHtml) webView.loadHtml(root.previewHtml, "http://localhost")
                                            }
                                        }
                                        Component.onCompleted: {
                                            if (root.previewHtml) webView.loadHtml(root.previewHtml, "http://localhost")
                                        }
                                    }
                                    
                                    // Overlay clickable to open Zen Mode
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.zenModeOpen = true
                                        
                                        Rectangle {
                                            anchors.fill: parent
                                            color: SemanticTheme.overlayScrim(root.t, root.appStyle)
                                            opacity: parent.containsMouse ? 1.0 : 0.0
                                            Behavior on opacity { NumberAnimation { duration: 150 } }
                                            Text {
                                                anchors.centerIn: parent
                                                text: "Click for Zen Preview"
                                                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                                                font.pixelSize: 18
                                                font.weight: Font.DemiBold
                                            }
                                        }
                                        hoverEnabled: true
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

    // ── Zen Mode Window ──────────────────────────────────────────────────
    InvoiceBuilderWorkspace {
        anchors.fill: parent
        host: root
    }

    Window {
        id: zenPopup
        visible: root.zenModeOpen
        onClosing: root.zenModeOpen = false
        title: root.isFinalized ? ("Finalized: " + root.finalInvoiceNum) : ("Zen Preview — " + root.selectedDraftNum)
        width: 1024
        height: 768
        visibility: root.zenModeOpen ? Window.Maximized : Window.Hidden
        color: "#E5E7EB"
            
        Rectangle {
            id: zenToolbar
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 56
            color: root.bgSurface
            border.color: root.borderColor
            border.width: 1
            
            RowLayout {
                anchors.fill: parent
                anchors.margins: 16
                Text {
                    text: root.isFinalized ? ("Finalized: " + root.finalInvoiceNum) : ("Zen Preview — " + root.selectedDraftNum)
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: root.textColor
                    Layout.fillWidth: true
                }
                


                
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: root.borderColor
                    Layout.margins: 4
                }
    
                PillButton {
                    t: root.t
                    text: "Export Word"
                    primary: false
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 32
                    onClicked: {
                        wordFileDialog.currentFile = "file:///Draft_" + root.selectedDraftNum + ".docx"
                        wordFileDialog.open()
                    }
                }
                
                PillButton {
                    t: root.t
                    text: "Export PDF"
                    primary: false
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 32
                    onClicked: {
                        pdfFileDialog.currentFile = "file:///Draft_" + root.selectedDraftNum + ".pdf"
                        pdfFileDialog.open()
                    }
                }
                
                PillButton {
                    t: root.t
                    text: "Edit Dockets"
                    primary: false
                    enabled: !root.isFinalized
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 32
                    onClicked: {
                        root.zenModeOpen = false
                    }
                }
                
                PillButton {
                    t: root.t
                    text: root.isFinalized ? "Finalized" : "Finalize Invoice"
                    primary: !root.isFinalized
                    enabled: !root.isFinalized
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 32
                    onClicked: {
                        root._finalizeDraft()
                    }
                }
                
                Rectangle {
                    width: 32; height: 32; radius: 16
                    color: "transparent"
                    Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 18; color: root.textColor }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.zenModeOpen = false }
                }
            }
        }
        
        FileDialog {
            id: pdfFileDialog
            title: "Save Draft PDF"
            nameFilters: ["PDF Files (*.pdf)"]
            fileMode: FileDialog.SaveFile
            defaultSuffix: "pdf"
            onAccepted: {
                var path = pdfFileDialog.selectedFile.toString().replace("file:///", "")
                if (root.billingBackend) {
                    root.billingBackend.exportHtmlToPdf(root.previewHtml, path)
                }
            }
        }
        
        FileDialog {
            id: finalizePdfFileDialog
            title: "Save Finalized Invoice PDF"
            nameFilters: ["PDF Files (*.pdf)"]
            fileMode: FileDialog.SaveFile
            defaultSuffix: "pdf"
            onAccepted: {
                var path = finalizePdfFileDialog.selectedFile.toString().replace("file:///", "")
                if (root.billingBackend) {
                    var finalHtml = root.billingBackend.getFinalizedHtml(root.selectedDraftNum, root.pendingFinalizeInvoiceNum)
                    root.isFinalizingExport = true
                    root.pendingFinalizePath = path
                    root.billingBackend.exportHtmlToPdf(finalHtml, path)
                }
            }
            onRejected: {
                root.pendingFinalizeInvoiceNum = ""
            }
        }
        
        FileDialog {
            id: wordFileDialog
            title: "Save Word Document"
            nameFilters: ["Word Documents (*.docx)"]
            fileMode: FileDialog.SaveFile
            defaultSuffix: "docx"
            onAccepted: {
                var path = wordFileDialog.selectedFile.toString().replace("file:///", "")
                root.billingBackend.exportDraftToWord(root.selectedDraftNum, root.selectedConcept, path)
            }
        }
            
        // Paper Area
        Rectangle {
            anchors.top: zenToolbar.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 24
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.color: root.borderColor
            border.width: 1
            
            WebEngineView {
                id: zenWebView
                anchors.fill: parent
                anchors.margins: 24
                backgroundColor: "transparent"
                
                Connections {
                    target: root
                    function onPreviewHtmlChanged() {
                        if (root.previewHtml) zenWebView.loadHtml(root.previewHtml, "http://localhost")
                    }
                }
                Component.onCompleted: {
                    if (root.previewHtml) zenWebView.loadHtml(root.previewHtml, "http://localhost")
                }
                
                Connections {
                    target: zenWebView
                    function onPdfPrintingFinished(filePath, success) {
                        if (success) {
                            if (appRef && appRef.stampPdfPageNumbers) {
                                appRef.stampPdfPageNumbers(filePath)
                            }
                            Qt.openUrlExternally("file:///" + filePath)
                        }
                    }
                }
            }
        }
    }

    // Finalize Invoice Dialog
    Window {
        id: finalizeInvoiceDialog
        property string inputInvoiceNum: ""
        property string validationError: ""
        
        width: 400
        height: 240
        flags: Qt.Dialog | Qt.FramelessWindowHint
        modality: Qt.ApplicationModal
        color: "transparent"
        
        Rectangle {
            anchors.fill: parent
            radius: 8
            color: root.panelColor
            border.color: root.borderColor
            border.width: 1
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16
                Text {
                    text: "Finalize Invoice"
                    font.family: "Inter"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: root.textColor
                }
                Text {
                    text: "Enter the final invoice number to issue. The next standard number is suggested below."
                    font.family: "Inter"
                    font.pixelSize: 14
                    color: root.mutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                TextField {
                    id: invNumInput
                    Layout.fillWidth: true
                    text: finalizeInvoiceDialog.inputInvoiceNum
                    font.family: "Inter"
                    font.pixelSize: 14
                    onTextChanged: finalizeInvoiceDialog.inputInvoiceNum = text
                }
                Text {
                    text: finalizeInvoiceDialog.validationError
                    color: "red"
                    font.pixelSize: 12
                    font.family: "Inter"
                    visible: finalizeInvoiceDialog.validationError !== ""
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    spacing: 12
                    Layout.alignment: Qt.AlignRight
                    Button {
                        text: "Cancel"
                        onClicked: finalizeInvoiceDialog.visible = false
                    }
                    Rectangle {
                        width: 100
                        height: 36
                        radius: 6
                        color: root.accentColor
                        Text {
                            anchors.centerIn: parent
                            text: "Confirm"
                            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.family: "Inter"
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root._confirmFinalizeDraft()
                        }
                    }
                }
            }
        }
    }

    Window {
        id: addFeeDialog
        title: "Add Custom Fee"
        width: 400
        height: 250
        flags: Qt.Dialog | Qt.WindowStaysOnTopHint
        modality: Qt.ApplicationModal
        color: root.backgroundColor

        function open() {
            x = (Screen.desktopAvailableWidth - width) / 2
            y = (Screen.desktopAvailableHeight - height) / 2
            show()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            TextField {
                id: newFeeDate
                placeholderText: "Date (YYYY-MM-DD)"
                placeholderTextColor: root.isDark ? "#888" : "#666"
                text: Qt.formatDate(new Date(), "yyyy-MM-dd")
                Layout.fillWidth: true
                color: root.textColor
                background: Rectangle { color: root.isDark ? "#333" : "#f0f0f0"; radius: 4; border.color: root.borderColor }
            }
            TextField {
                id: newFeeDesc
                placeholderText: "Fee Description"
                placeholderTextColor: root.isDark ? "#888" : "#666"
                Layout.fillWidth: true
                color: root.textColor
                background: Rectangle { color: root.isDark ? "#333" : "#f0f0f0"; radius: 4; border.color: root.borderColor }
            }
            TextField {
                id: newFeeAmount
                placeholderText: "Amount (e.g. 500.00)"
                placeholderTextColor: root.isDark ? "#888" : "#666"
                Layout.fillWidth: true
                color: root.textColor
                background: Rectangle { color: root.isDark ? "#333" : "#f0f0f0"; radius: 4; border.color: root.borderColor }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 10
                Button {
                    text: "Cancel"
                    onClicked: addFeeDialog.close()
                }
                Button {
                    text: "OK"
                    onClicked: {
                        var amount = parseFloat(newFeeAmount.text) || 0;
                        if (amount !== 0 || newFeeDesc.text.trim() !== "") {
                            root.billingBackend.addDraftLineItem(root.selectedDraftNum, {
                                "date": newFeeDate.text,
                                "description": newFeeDesc.text,
                                "isFee": true,
                                "amount": amount,
                                "hours": 0.0,
                                "rate": 0.0,
                                "matterId": "Custom Fee"
                            })
                        }
                        newFeeDesc.text = "";
                        newFeeAmount.text = "";
                        addFeeDialog.close()
                    }
                }
            }
        }
    }
}
}
