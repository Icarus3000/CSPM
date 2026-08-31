import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtWebEngine
import "../components"

Item {
    id: workspace
    property var host

    component ThemedComboBox: ComboBox {
        id: control
        property var host
        font.pixelSize: 12
        contentItem: Text {
            leftPadding: 8
            rightPadding: 24
            text: control.displayText
            color: control.enabled ? control.host.textColor : control.host.mutedColor
            font: control.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            x: control.width - width - 8
            anchors.verticalCenter: parent.verticalCenter
            text: "⌄"
            color: control.host.mutedColor
            font.pixelSize: 16
        }
        background: Rectangle {
            color: control.enabled ? control.host.comboSurface
                                   : (control.host.isDark ? "#292d33" : "#edf0f4")
            border.color: control.host.comboBorderColor
            border.width: 1
            radius: 4
        }
        delegate: ItemDelegate {
            width: control.popup.width
            height: 32
            highlighted: control.highlightedIndex === index
            contentItem: Text {
                leftPadding: 8
                text: modelData
                color: control.host.textColor
                font: control.font
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            background: Rectangle {
                color: parent.highlighted ? control.host.comboHoverSurface
                                          : control.host.comboSurface
                radius: 3
            }
        }
        popup: Popup {
            y: control.height - 1
            width: control.width
            implicitHeight: Math.min(contentItem.implicitHeight, 194)
            padding: 1
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator {}
            }
            background: Rectangle {
                color: control.host.comboSurface
                border.color: control.host.comboBorderColor
                border.width: 1
                radius: 4
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: host.basePadding
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                text: "Invoice Builder"
                color: host.textColor
                font.family: "Inter"
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "Review draft invoices, reconcile flat fees, and generate final PDFs."
                color: host.mutedColor
                font.family: "Inter"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            Rectangle {
                Layout.preferredWidth: 450
                Layout.minimumWidth: 350
                Layout.fillHeight: true
                color: host.panelColor
                border.color: host.borderColor
                border.width: 1
                radius: 10

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: "Draft Invoices"
                            color: host.textColor
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        PillButton {
                            t: host.t
                            text: "Refresh"
                            primary: false
                            Layout.preferredWidth: 76
                            Layout.preferredHeight: 30
                            onClicked: host._loadDrafts()
                        }
                    }

                    ListView {
                        id: draftList
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(contentHeight, 140)
                        Layout.minimumHeight: 48
                        clip: true
                        model: host.draftsList
                        spacing: 4
                        delegate: Rectangle {
                            required property var modelData
                            width: draftList.width
                            height: 46
                            radius: 5
                            color: host.selectedDraftNum === String(modelData.InvoiceNum || modelData.draftNum)
                                   ? Qt.rgba(host.accentColor.r, host.accentColor.g, host.accentColor.b, 0.16)
                                   : (draftMouse.containsMouse
                                      ? (host.isDark ? "#303844" : "#f2f6fb") : "transparent")
                            border.color: host.borderColor
                            border.width: 1
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        Layout.fillWidth: true
                                        text: String(modelData.InvoiceNum || modelData.draftNum)
                                        color: host.textColor
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: String(modelData.ClientName || modelData.clientName || "Unknown client")
                                        color: host.mutedColor
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }
                                Text { text: "›"; color: host.mutedColor; font.pixelSize: 18 }
                            }
                            MouseArea {
                                id: draftMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: host._selectDraft(String(modelData.InvoiceNum || modelData.draftNum))
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: host.borderColor }

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: host.selectedDraftNum ? "Line Items · " + host.selectedDraftNum : "Line Items"
                            color: host.textColor
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: host.selectedDraftNum ? host.draftLineItems.length + " entries" : ""
                            color: host.mutedColor
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: host.isDark ? "#262b33" : "#fbfcfe"
                        border.color: host.borderColor
                        border.width: 1
                        radius: 7

                        ListView {
                            id: lineItems
                            anchors.fill: parent
                            anchors.margins: 1
                            clip: true
                            model: host.selectedDraftNum ? host.draftLineItems : []
                            spacing: 1
                            delegate: Rectangle {
                                id: lineDelegate
                                required property var modelData
                                width: lineItems.width
                                height: editing ? 93 : 54
                                property bool editing: false
                                property bool isFee: Boolean(modelData.isFee)
                                color: editing ? (host.isDark ? "#303844" : "#f4f8fc") : "transparent"
                                border.color: host.borderColor
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 9
                                    spacing: 7
                                    visible: !lineDelegate.editing
                                    Text { Layout.preferredWidth: 72; text: modelData.date || ""; color: host.mutedColor; font.pixelSize: 11; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: modelData.description || ""; color: host.textColor; font.pixelSize: 12; elide: Text.ElideRight }
                                    Text { Layout.preferredWidth: 36; text: Number(modelData.hours || 0) > 0 ? Number(modelData.hours).toFixed(1) : ""; color: host.mutedColor; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                                    Text { Layout.preferredWidth: 72; text: "$" + Number(modelData.amount || 0).toFixed(2); color: host.textColor; font.pixelSize: 12; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignRight }
                                    PillButton {
                                        t: host.t
                                        text: "Edit"
                                        primary: false
                                        Layout.preferredWidth: 54
                                        Layout.preferredHeight: 28
                                        onClicked: lineDelegate.editing = true
                                    }
                                }

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 6
                                    visible: lineDelegate.editing
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 5
                                        TextField {
                                            id: lineDate
                                            Layout.preferredWidth: 90
                                            Layout.preferredHeight: 31
                                            text: modelData.date || ""
                                            placeholderText: "Date"
                                            placeholderTextColor: host.isDark ? "#8d99a7" : "#8a96a5"
                                            color: host.textColor
                                            font.pixelSize: 12
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                        }
                                        TextField {
                                            id: lineDescription
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 31
                                            text: modelData.description || ""
                                            placeholderText: "Description of work performed"
                                            placeholderTextColor: host.isDark ? "#8d99a7" : "#8a96a5"
                                            color: host.textColor
                                            font.pixelSize: 12
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                        }
                                        TextField {
                                            id: lineHours
                                            visible: !lineDelegate.isFee
                                            Layout.preferredWidth: 48
                                            Layout.preferredHeight: 31
                                            text: Number(modelData.hours || 0) > 0 ? String(modelData.hours) : ""
                                            placeholderText: "Hours"
                                            placeholderTextColor: host.isDark ? "#8d99a7" : "#8a96a5"
                                            color: host.textColor
                                            font.pixelSize: 12
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                        }
                                        TextField {
                                            id: lineRate
                                            visible: !lineDelegate.isFee
                                            Layout.preferredWidth: 62
                                            Layout.preferredHeight: 31
                                            text: Number(modelData.rate || 0) > 0 ? String(modelData.rate) : ""
                                            placeholderText: "Rate ($)"
                                            placeholderTextColor: host.isDark ? "#8d99a7" : "#8a96a5"
                                            color: host.textColor
                                            font.pixelSize: 12
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                        }
                                        TextField {
                                            id: lineFeeAmount
                                            visible: lineDelegate.isFee
                                            Layout.preferredWidth: 116
                                            Layout.preferredHeight: 31
                                            text: Number(modelData.amount || 0) > 0 ? String(modelData.amount) : ""
                                            placeholderText: "Fee amount ($)"
                                            placeholderTextColor: host.isDark ? "#8d99a7" : "#8a96a5"
                                            color: host.textColor
                                            font.pixelSize: 12
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Item { Layout.fillWidth: true }
                                        PillButton { t: host.t; text: "Cancel"; primary: false; Layout.preferredWidth: 66; Layout.preferredHeight: 28; onClicked: lineDelegate.editing = false }
                                        PillButton { t: host.t; text: "Remove"; primary: false; Layout.preferredWidth: 70; Layout.preferredHeight: 28; onClicked: host.billingBackend.removeDraftLineItem(host.selectedDraftNum, modelData.entryId, false) }
                                        PillButton {
                                            t: host.t
                                            text: "Save"
                                            primary: true
                                            Layout.preferredWidth: 58
                                            Layout.preferredHeight: 28
                                            onClicked: {
                                                var changes = {
                                                    "date": lineDate.text,
                                                    "description": lineDescription.text
                                                }
                                                if (lineDelegate.isFee)
                                                    changes.amount = parseFloat(lineFeeAmount.text) || 0
                                                else {
                                                    changes.hours = parseFloat(lineHours.text) || 0
                                                    changes.rate = parseFloat(lineRate.text) || 0
                                                }
                                                host.billingBackend.updateDraftLineItem(host.selectedDraftNum, modelData.entryId, changes)
                                                lineDelegate.editing = false
                                            }
                                        }
                                    }
                                }
                            }
                            footer: Item {
                                width: lineItems.width
                                height: 56
                                PillButton {
                                    anchors.centerIn: parent
                                    t: host.t
                                    text: "+ Add New Docket"
                                    primary: false
                                    Layout.preferredWidth: 156
                                    Layout.preferredHeight: 30
                                    onClicked: host.billingBackend.addDraftLineItem(host.selectedDraftNum, {
                                        "date": Qt.formatDate(new Date(), "yyyy-MM-dd"),
                                        "description": "New Time Entry",
                                        "hours": 0.0,
                                        "rate": 0.0,
                                        "matterId": "General"
                                    })
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !host.selectedDraftNum
                            text: "Select a draft to review its line items."
                            color: host.mutedColor
                            font.pixelSize: 13
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: host.panelColor
                border.color: host.borderColor
                border.width: 1
                radius: 10

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12
                    visible: !!host.selectedDraftNum

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: "HTML Preview · " + host.selectedDraftNum
                            color: host.textColor
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }
                        PillButton {
                            t: host.t
                            text: "Zen Preview"
                            primary: false
                            Layout.preferredWidth: 108
                            Layout.preferredHeight: 32
                            onClicked: host.zenModeOpen = true
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: host.isDark ? "#20242b" : "#f6f7f9"
                        border.color: host.borderColor
                        border.width: 1
                        radius: 7
                        clip: true
                        WebEngineView {
                            id: htmlPreview
                            anchors.fill: parent
                            anchors.margins: 6
                            backgroundColor: "transparent"
                            visible: !host.isPreviewLoading
                            Component.onCompleted: {
                                if (host.previewHtml) htmlPreview.loadHtml(host.previewHtml, "http://localhost")
                            }
                            Connections {
                                target: host
                                function onPreviewHtmlChanged() {
                                    if (host.previewHtml) htmlPreview.loadHtml(host.previewHtml, "http://localhost")
                                }
                            }
                        }
                        
                        BusyIndicator {
                            anchors.centerIn: parent
                            width: 32
                            height: 32
                            visible: host.isPreviewLoading
                        }
                    }

                    Rectangle {
                        id: controls
                        Layout.fillWidth: true
                        Layout.preferredHeight: controlsContent.implicitHeight + 22
                        color: host.isDark ? "#252a31" : "#f8fafc"
                        border.color: host.borderColor
                        border.width: 1
                        radius: 7
                        ColumnLayout {
                            id: controlsContent
                            anchors.fill: parent
                            anchors.margins: 11
                            spacing: 10

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 58
                                color: host.isDark ? "#2c3643" : "#edf5ff"
                                border.color: host.accentColor
                                border.width: 1
                                radius: 6

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 9
                                    spacing: 10

                                    ColumnLayout {
                                        Layout.preferredWidth: 180
                                        spacing: 1

                                        Text {
                                            text: "Invoice date"
                                            color: host.textColor
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: "Date shown on the invoice"
                                            color: host.mutedColor
                                            font.pixelSize: 11
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    TextField {
                                        id: invoiceDateField
                                        Layout.preferredWidth: 128
                                        Layout.preferredHeight: 32
                                        text: (host.selectedDraftData && host.selectedDraftData.Date)
                                            ? String(host.selectedDraftData.Date).substring(0, 10)
                                            : Qt.formatDate(new Date(), "yyyy-MM-dd")
                                        color: host.textColor
                                        font.pixelSize: 12
                                        selectByMouse: true
                                        onEditingFinished: host._saveInvoiceDate(text, invoiceDateField)
                                        background: Rectangle {
                                            color: host.comboSurface
                                            border.color: host.comboBorderColor
                                            border.width: 1
                                            radius: 4
                                        }
                                    }

                                    PillButton {
                                        t: host.t
                                        text: "Choose date"
                                        primary: true
                                        Layout.preferredWidth: 108
                                        Layout.preferredHeight: 32
                                        onClicked: {
                                            var point = invoiceDateField.mapToGlobal(
                                                invoiceDateField.width / 2,
                                                invoiceDateField.height / 2
                                            )
                                            host.openDatePickerFor(invoiceDateField, point.x, point.y)
                                        }
                                    }
                                }
                            }

                            // Settings row
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 9
                                ColumnLayout {
                                    Layout.preferredWidth: 88
                                    spacing: 3
                                    Text { text: "Grouping"; color: host.mutedColor; font.pixelSize: 11 }
                                    ThemedComboBox {
                                        id: groupingCombo
                                        host: workspace.host
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 31
                                        model: ["Matter", "Client", "Combined"]
                                        currentIndex: host.selectedDraftData ? Math.max(0, ["matter", "client", "combined"].indexOf(String(host.selectedDraftData.GroupingPref || "matter").toLowerCase())) : 0
                                        onActivated: host.billingBackend.updateDraftGrouping(host.selectedDraftNum, currentText.toLowerCase())
                                    }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth: 182
                                    spacing: 3
                                    Text { text: "Courtesy Discount"; color: host.mutedColor; font.pixelSize: 11 }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        ThemedComboBox {
                                            id: discountTypeCombo
                                            host: workspace.host
                                            Layout.preferredWidth: 101
                                            Layout.preferredHeight: 31
                                            model: ["Percentage", "Flat Amount"]
                                            currentIndex: host.selectedDraftData && ["flat", "fixed", "flat amount"].indexOf(String(host.selectedDraftData.DiscountType || "").toLowerCase()) >= 0 ? 1 : 0
                                            onActivated: {
                                                if (parseFloat(discountValue.text) > 0) {
                                                    host.billingBackend.applyDiscount(host.selectedDraftNum, currentIndex === 0 ? "Percentage" : "Flat", parseFloat(discountValue.text) || 0)
                                                }
                                            }
                                        }
                                        TextField {
                                            id: discountValue
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 31
                                            text: host.selectedDraftData ? String(host.selectedDraftData.DiscountValue || "0.0") : "0.0"
                                            color: host.textColor
                                            font.pixelSize: 11
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                            onEditingFinished: host.billingBackend.applyDiscount(host.selectedDraftNum, discountTypeCombo.currentIndex === 0 ? "Percentage" : "Flat", parseFloat(discountValue.text) || 0)
                                            onAccepted: host.billingBackend.applyDiscount(host.selectedDraftNum, discountTypeCombo.currentIndex === 0 ? "Percentage" : "Flat", parseFloat(discountValue.text) || 0)
                                        }
                                        PillButton { t: host.t; text: "Apply"; primary: false; Layout.preferredWidth: 50; Layout.preferredHeight: 31; onClicked: host.billingBackend.applyDiscount(host.selectedDraftNum, discountTypeCombo.currentIndex === 0 ? "Percentage" : "Flat", parseFloat(discountValue.text) || 0) }
                                    }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth: 108
                                    spacing: 3
                                    Text { text: "Agency Split %"; color: host.mutedColor; font.pixelSize: 11 }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        TextField {
                                            id: agencySplit
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 31
                                            text: host.selectedDraftData ? String(host.selectedDraftData.AgencySplitPercent || "0.0") : "0.0"
                                            color: host.textColor
                                            font.pixelSize: 11
                                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                                            background: Rectangle { color: host.comboSurface; border.color: host.comboBorderColor; radius: 4 }
                                            onEditingFinished: host.billingBackend.applyAgencySplit(host.selectedDraftNum, parseFloat(agencySplit.text) || 0)
                                            onAccepted: host.billingBackend.applyAgencySplit(host.selectedDraftNum, parseFloat(agencySplit.text) || 0)
                                        }
                                        PillButton { t: host.t; text: "Set"; primary: false; Layout.preferredWidth: 42; Layout.preferredHeight: 31; onClicked: host.billingBackend.applyAgencySplit(host.selectedDraftNum, parseFloat(agencySplit.text) || 0) }
                                    }
                                }
                                ColumnLayout {
                                    visible: host.reconciliationRequired
                                    Layout.preferredWidth: 138
                                    spacing: 3
                                    Text { text: "Reconciliation"; color: host.mutedColor; font.pixelSize: 11 }
                                    ThemedComboBox {
                                        id: reconciliationCombo
                                        host: workspace.host
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 31
                                        model: ["Discount Line", "Hidden Adjustment"]
                                        currentIndex: host._reconciliationMode() === "discount_line" ? 0 : 1
                                        onActivated: host.billingBackend.updateDraftReconciliationMode(host.selectedDraftNum, currentText)
                                    }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth: 116
                                    spacing: 3
                                    Text { text: "Time Dockets"; color: host.mutedColor; font.pixelSize: 11 }
                                    ThemedComboBox {
                                        id: docketDisplayCombo
                                        host: workspace.host
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 31
                                        enabled: host.hasCustomFees
                                        model: ["Show all", "Hide all", "Combine as tasks"]
                                        currentIndex: host._docketDisplayIndex()
                                        onActivated: host.billingBackend.updateDraftDocketDisplayMode(host.selectedDraftNum, currentIndex === 1 ? "hide" : (currentIndex === 2 ? "tasks" : "show"))
                                    }
                                }
                                Item { Layout.fillWidth: true }
                            }

                            // Actions row
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Item { Layout.fillWidth: true }
                                PillButton { t: host.t; text: "Add Custom Fee"; primary: false; Layout.preferredWidth: 132; Layout.preferredHeight: 34; onClicked: host.openAddFeeDialog() }
                                PillButton { t: host.t; text: "Cancel"; primary: false; Layout.preferredWidth: 82; Layout.preferredHeight: 34; onClicked: host._clearSelection() }
                                PillButton { t: host.t; text: "Delete Draft"; primary: false; Layout.preferredWidth: 104; Layout.preferredHeight: 34; onClicked: host._deleteDraft() }
                                PillButton { t: host.t; text: host.isFinalized ? "Finalized" : "Finalize Invoice"; primary: true; enabled: !host.isFinalized; Layout.preferredWidth: 132; Layout.preferredHeight: 34; onClicked: host._finalizeDraft() }
                            }
                        }
                    }
                }
                
                // --- Finalized Success Overlay ---
                Rectangle {
                    anchors.fill: parent
                    visible: host.isFinalized
                    color: host.isDark ? "#20242b" : "#ffffff"
                    radius: 10
                    border.color: host.borderColor
                    border.width: 1
                    
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 24
                        
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            width: 80; height: 80; radius: 40
                            color: "#10b981" // Emerald 500
                            Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.pixelSize: 48; font.weight: Font.DemiBold }
                        }
                        
                        ColumnLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 8
                            Text {
                                text: "Invoice Finalized Successfully"
                                color: host.textColor
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                font.family: "Inter"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "Invoice " + host.finalInvoiceNum + " has been recorded."
                                color: host.mutedColor
                                font.pixelSize: 15
                                font.family: "Inter"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                        
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 16
                            Layout.topMargin: 16
                            
                            PillButton { 
                                t: host.t
                                text: "Open Final PDF"
                                primary: false
                                Layout.preferredWidth: 160
                                Layout.preferredHeight: 40
                                onClicked: Qt.openUrlExternally("file:///" + host.finalPdfPath)
                            }
                            
                            PillButton { 
                                t: host.t
                                text: "Return to WIP"
                                primary: true
                                Layout.preferredWidth: 160
                                Layout.preferredHeight: 40
                                onClicked: {
                                    host.isFinalized = false
                                    if (typeof host.autoCloseTimer !== 'undefined') {
                                        host.autoCloseTimer.start()
                                    }
                                }
                            }
                        }
                    }
                }
                
                Text {
                    anchors.centerIn: parent
                    visible: !host.selectedDraftNum && !host.isFinalized
                    text: "Select a draft invoice to show its preview and billing controls."
                    color: host.mutedColor
                    font.pixelSize: 14
                }
            }
        }
    }
}
