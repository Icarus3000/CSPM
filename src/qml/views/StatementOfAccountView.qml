pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var appRef
    property var sfxBus
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"

    // Context routes from a profile/A-R report still prefill the bill-to party.
    property string selectedClientLabel: ""
    property string selectedClientId: ""
    property string billingClientName: ""
    property string asOfDateText: ""
    property var billingClientRows: []
    property var billingClientNames: []
    property var availableInvoices: []
    property var selectedInvoiceMap: ({})
    property int selectionRevision: 0
    property var reportData: null
    property bool busy: false
    property bool statementReady: false
    property string statusText: "Choose a billing client to load its unpaid invoices."

    signal reportWindowRequested(var reportDocument)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function cleanText(value) {
        return value === undefined || value === null ? "" : String(value).trim()
    }

    function formatCurrency(value) {
        var amount = Number(value || 0)
        return "$" + amount.toLocaleString(Qt.locale(), "f", 2)
    }

    function selectedInvoiceNumbers() {
        var selected = []
        for (var i = 0; i < root.availableInvoices.length; ++i) {
            var invoice = root.cleanText(root.availableInvoices[i].invoice)
            if (invoice.length > 0 && root.selectedInvoiceMap[invoice])
                selected.push(invoice)
        }
        return selected
    }

    function selectedInvoiceCount() {
        return root.selectedInvoiceNumbers().length
    }

    function selectedBalance() {
        var amount = 0
        for (var i = 0; i < root.availableInvoices.length; ++i) {
            var row = root.availableInvoices[i]
            var invoice = root.cleanText(row.invoice)
            if (invoice.length > 0 && root.selectedInvoiceMap[invoice])
                amount += Number(row.balanceDue || 0)
        }
        return amount
    }

    function isInvoiceSelected(invoice) {
        return !!root.selectedInvoiceMap[root.cleanText(invoice)]
    }

    function setInvoiceSelected(invoice, selected) {
        var key = root.cleanText(invoice)
        if (key.length === 0)
            return
        var next = {}
        for (var existing in root.selectedInvoiceMap)
            next[existing] = root.selectedInvoiceMap[existing]
        next[key] = !!selected
        root.selectedInvoiceMap = next
        root.selectionRevision += 1
        root.statementReady = false
        root.statusText = root.selectedInvoiceCount() + " invoice" + (root.selectedInvoiceCount() === 1 ? "" : "s")
                + " selected — " + root.formatCurrency(root.selectedBalance()) + ". Click Generate Statement when ready."
    }

    function selectAllInvoices(selected) {
        var next = {}
        for (var i = 0; i < root.availableInvoices.length; ++i) {
            var invoice = root.cleanText(root.availableInvoices[i].invoice)
            if (invoice.length > 0)
                next[invoice] = !!selected
        }
        root.selectedInvoiceMap = next
        root.selectionRevision += 1
        root.statementReady = false
        root.statusText = selected
                ? root.availableInvoices.length + " open invoices selected."
                : "No invoices selected."
    }

    function setBillingClient(value, shouldLoad) {
        var name = root.cleanText(value)
        if (name === root.billingClientName && !shouldLoad)
            return
        root.billingClientName = name
        root.availableInvoices = []
        root.selectedInvoiceMap = ({})
        root.selectionRevision += 1
        root.reportData = null
        root.statementReady = false
        if (billingClientCombo.editText !== name)
            billingClientCombo.editText = name
        if (shouldLoad && name.length > 0)
            root.refreshOpenInvoices()
    }

    function loadBillingClients() {
        if (!root.appRef)
            return
        var rows = []
        try {
            if (typeof root.appRef.listStatementBillingClients === "function")
                rows = root.appRef.listStatementBillingClients() || []
            if ((!rows || rows.length === 0) && typeof root.appRef.listClientNames === "function") {
                var names = root.appRef.listClientNames() || []
                for (var i = 0; i < names.length; ++i)
                    rows.push({ "name": String(names[i]) })
            }
        } catch (e) {
            rows = []
        }
        var namesOut = []
        for (var j = 0; j < rows.length; ++j) {
            var name = root.cleanText(rows[j].name || rows[j])
            if (name.length > 0 && namesOut.indexOf(name) < 0)
                namesOut.push(name)
        }
        root.billingClientRows = rows
        root.billingClientNames = namesOut
        if (root.billingClientName.length === 0 && root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, false)
    }

    function basePayload() {
        return {
            "billingClient": root.billingClientName,
            "client": root.billingClientName,
            "clientId": root.selectedClientId,
            "client_level": "billing",
            "asOfDate": root.asOfDateText,
            "openItemsOnly": true
        }
    }

    function refreshOpenInvoices() {
        if (root.billingClientName.length === 0) {
            root.statusText = "Choose a billing client before loading invoices."
            return
        }
        if (!root.appRef || typeof root.appRef.getStatementOfAccount !== "function") {
            root.statusText = "Statement backend not available."
            return
        }
        root.busy = true
        root.statusText = "Loading open invoices…"
        var response = root.appRef.getStatementOfAccount(root.basePayload())
        root.busy = false
        if (response && response.ok) {
            root.availableInvoices = response.availableInvoices || []
            root.reportData = null
            root.selectAllInvoices(true)
            if (root.availableInvoices.length === 0)
                root.statusText = "No unpaid invoices found for " + root.billingClientName + "."
        } else {
            root.availableInvoices = []
            root.selectedInvoiceMap = ({})
            root.selectionRevision += 1
            root.statusText = "Could not load invoices: " + root.cleanText(response && response.message)
        }
    }

    function generateStatement() {
        var selected = root.selectedInvoiceNumbers()
        if (selected.length === 0) {
            root.statusText = "Select at least one unpaid invoice for this statement."
            return
        }
        if (!root.appRef || typeof root.appRef.getStatementOfAccount !== "function") {
            root.statusText = "Statement backend not available."
            return
        }
        var payload = root.basePayload()
        payload.selectedInvoiceNumbers = selected
        root.busy = true
        root.statusText = "Preparing selected statement…"
        var response = root.appRef.getStatementOfAccount(payload)
        root.busy = false
        if (response && response.ok) {
            root.reportData = response
            root.availableInvoices = response.availableInvoices || root.availableInvoices
            root.statementReady = true
            root.statusText = selected.length + " invoice" + (selected.length === 1 ? "" : "s")
                    + " included — " + root.formatCurrency(root.selectedBalance()) + " due."
        } else {
            root.statementReady = false
            root.statusText = "Could not generate statement: " + root.cleanText(response && response.message)
        }
    }

    function printStatement() {
        if (!root.statementReady || !root.reportData || !root.reportData.ok) {
            root.statusText = "Generate the selected statement before printing or exporting."
            return
        }
        root.reportWindowRequested(root.reportData)
    }

    Component.onCompleted: {
        root.loadBillingClients()
        if (root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, true)
    }

    onAppRefChanged: root.loadBillingClients()
    onSelectedClientLabelChanged: {
        if (root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, root.visible)
    }
    onVisibleChanged: {
        if (visible && root.billingClientName.length === 0 && root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, true)
    }

    Rectangle {
        anchors.fill: parent
        color: SemanticTheme.surfaceApp(root.t, root.appStyle)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.isProMode ? 16 : 12
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 138
                color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                radius: root.isProMode ? visualRules.radiusPanel : 6
                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Statement of Account"
                            font.pixelSize: visualRules.proWorkspaceTitleFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.DemiBold
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "Open invoices only"
                            font.pixelSize: visualRules.proCaptionFontPx
                            font.family: visualRules.textFontFamily
                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        ColumnLayout {
                            Layout.preferredWidth: 360
                            Layout.maximumWidth: 430
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                text: "Billing Client"
                                font.pixelSize: visualRules.proCaptionFontPx
                                font.family: visualRules.textFontFamily
                                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                            }
                            ComboBox {
                                id: billingClientCombo
                                Layout.fillWidth: true
                                editable: true
                                model: root.billingClientNames
                                font.pixelSize: visualRules.proBodyFontPx
                                font.family: visualRules.textFontFamily
                                onActivated: function(index) { root.setBillingClient(String(model[index]), false) }
                                onAccepted: root.setBillingClient(editText, false)
                            }
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 180
                            spacing: 3
                            Text {
                                text: "Statement Date"
                                font.pixelSize: visualRules.proCaptionFontPx
                                font.family: visualRules.textFontFamily
                                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                            }
                            TextField {
                                id: asOfDateInput
                                Layout.fillWidth: true
                                text: root.asOfDateText
                                placeholderText: "YYYY-MM-DD"
                                font.pixelSize: visualRules.proBodyFontPx
                                font.family: visualRules.textFontFamily
                                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                onTextChanged: root.asOfDateText = text
                            }
                        }

                        Button {
                            text: root.busy ? "Loading…" : "Load Open Invoices"
                            enabled: !root.busy && root.billingClientName.length > 0
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            onClicked: root.refreshOpenInvoices()
                        }

                        Item { Layout.fillWidth: true }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                radius: root.isProMode ? visualRules.radiusPanel : 6
                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Select invoices to include"
                            font.pixelSize: visualRules.proSectionTitleFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.DemiBold
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        }
                        Text {
                            text: root.availableInvoices.length + " unpaid invoice" + (root.availableInvoices.length === 1 ? "" : "s")
                            font.pixelSize: visualRules.proCaptionFontPx
                            font.family: visualRules.textFontFamily
                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: "Select All"
                            enabled: root.availableInvoices.length > 0 && !root.busy
                            onClicked: root.selectAllInvoices(true)
                        }
                        Button {
                            text: "Clear"
                            enabled: root.availableInvoices.length > 0 && !root.busy
                            onClicked: root.selectAllInvoices(false)
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: "Include"; Layout.preferredWidth: 68; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Date"; Layout.preferredWidth: 92; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Invoice"; Layout.preferredWidth: 90; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Legal Services For"; Layout.fillWidth: true; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Invoice Total"; Layout.preferredWidth: 105; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Paid / Credits"; Layout.preferredWidth: 110; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                        Text { text: "Amount Due"; Layout.preferredWidth: 105; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
                    }

                    ListView {
                        id: invoiceList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        model: root.availableInvoices

                        delegate: Rectangle {
                            id: invoiceRow
                            required property var modelData
                            required property int index
                            width: invoiceList.width
                            height: 42
                            color: index % 2 === 0 ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : "transparent"
                            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 4
                                anchors.rightMargin: 8
                                spacing: 8
                                CheckBox {
                                    Layout.preferredWidth: 68
                                    checked: root.selectionRevision >= 0 && root.isInvoiceSelected(invoiceRow.modelData.invoice)
                                    onClicked: root.setInvoiceSelected(invoiceRow.modelData.invoice, checked)
                                }
                                Text { text: invoiceRow.modelData.date || ""; Layout.preferredWidth: 92; elide: Text.ElideRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                                Text { text: invoiceRow.modelData.invoice || ""; Layout.preferredWidth: 90; elide: Text.ElideRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                                Text { text: invoiceRow.modelData.serviceFor || ""; Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                                Text { text: invoiceRow.modelData.invoiceTotalFormatted || ""; Layout.preferredWidth: 105; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                                Text { text: invoiceRow.modelData.paidCreditsFormatted || ""; Layout.preferredWidth: 110; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                                Text { text: invoiceRow.modelData.balanceDueFormatted || ""; Layout.preferredWidth: 105; horizontalAlignment: Text.AlignRight; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkPrimary(root.t, root.appStyle) }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: invoiceList.count === 0 && !root.busy
                            text: root.billingClientName.length > 0
                                ? "No unpaid invoices are available for this billing client."
                                : "Choose a billing client, then load its open invoices."
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 82
                color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                radius: root.isProMode ? visualRules.radiusPanel : 6
                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 16

                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: root.selectedInvoiceCount() + " invoice" + (root.selectedInvoiceCount() === 1 ? "" : "s") + " selected"
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        }
                        Text {
                            text: root.formatCurrency(root.selectedBalance())
                            font.pixelSize: visualRules.proWorkspaceTitleFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.DemiBold
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        }
                    }
                    Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: SemanticTheme.borderSubtle(root.t, root.appStyle) }
                    Text {
                        Layout.fillWidth: true
                        text: root.statusText
                        wrapMode: Text.WordWrap
                        font.pixelSize: visualRules.proCaptionFontPx
                        font.family: visualRules.textFontFamily
                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    }
                    Button {
                        text: "Generate Statement"
                        enabled: !root.busy && root.selectedInvoiceCount() > 0
                        font.pixelSize: visualRules.proBodyFontPx
                        font.family: visualRules.textFontFamily
                        font.weight: Font.Medium
                        onClicked: root.generateStatement()
                    }
                    Button {
                        text: "Print / Export"
                        enabled: !root.busy && root.statementReady
                        font.pixelSize: visualRules.proBodyFontPx
                        font.family: visualRules.textFontFamily
                        font.weight: Font.Medium
                        onClicked: root.printStatement()
                    }
                }
            }
        }
    }
}
