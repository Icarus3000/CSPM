pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../standards"
import "../components"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var appRef
    property var sfxBus
    property var metrics: null
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    // Qt RichText gives <a> elements its own default link colour, rather than
    // inheriting the label's semantic ink.  That default is too dark on the
    // Professional dark statement rows.  Keep light mode's existing link
    // treatment and only override the dark-mode matter link colour.
    readonly property bool darkTheme: SemanticTheme.isDarkMode(root.t)
    readonly property string darkMatterLinkColor: "#93C5FD"

    // An explicit context route may prefill the bill-to party. Opening this
    // report from Finance must begin with a deliberate client choice, rather
    // than silently reusing a client from another workspace.
    property string selectedClientLabel: ""
    property string selectedClientId: ""
    property bool useContextClient: false
    property string billingClientName: ""
    property string asOfDateText: todayIsoDate()
    property var billingClientRows: []
    property var billingClientNames: []
    property var availableInvoices: []
    property var selectedInvoiceMap: ({})
    property int selectionRevision: 0
    property var reportData: null
    property bool busy: false
    property string statusText: "Choose a billing client to load its unpaid invoices."
    property int requestSequence: 0
    property string billingClientsRequestId: ""
    property string statementRequestId: ""

    signal reportWindowRequested(var reportDocument)
    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function cleanText(value) {
        return value === undefined || value === null ? "" : String(value).trim()
    }

    function todayIsoDate() {
        var now = new Date()
        var year = now.getFullYear()
        var month = String(now.getMonth() + 1).padStart(2, "0")
        var day = String(now.getDate()).padStart(2, "0")
        return year + "-" + month + "-" + day
    }

    function hasBillingClientChoice(value) {
        var candidate = root.cleanText(value)
        for (var i = 0; i < root.billingClientNames.length; ++i) {
            if (root.cleanText(root.billingClientNames[i]) === candidate)
                return true
        }
        return false
    }

    function formatCurrency(value) {
        var amount = Number(value || 0)
        return "$" + amount.toLocaleString(Qt.locale(), "f", 2)
    }

    function escapeHtml(value) {
        return root.cleanText(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;")
    }

    function matterLinkMarkup(row) {
        var links = row && row.matterLinks && row.matterLinks.length !== undefined
            ? row.matterLinks : []
        if (!links || links.length === 0)
            return root.escapeHtml(row && row.serviceFor)

        var parts = []
        for (var i = 0; i < links.length; ++i) {
            var link = links[i] || ({})
            var clientName = root.cleanText(link.clientName)
            var matterName = root.cleanText(link.matterName)
            var matterId = root.cleanText(link.matterId)
            if (matterName.length === 0)
                continue
            var prefix = clientName.length > 0 ? root.escapeHtml(clientName) + " &#8212; " : ""
            var matterMarkup = root.escapeHtml(matterName)
            if (matterId.length > 0) {
                matterMarkup = "<a href=\"matter:" + encodeURIComponent(matterId) + "\">"
                    + (root.darkTheme ? "<font color=\"" + root.darkMatterLinkColor + "\">" : "")
                    + matterMarkup
                    + (root.darkTheme ? "</font>" : "")
                    + "</a>"
            }
            parts.push(prefix + matterMarkup)
        }
        return parts.length > 0 ? parts.join(", ") : root.escapeHtml(row && row.serviceFor)
    }

    function openInvoiceDirectory(row) {
        var invoice = root.cleanText(row && row.invoice)
        if (invoice.length === 0)
            return
        root.workspaceOpenRequested(2, "C04", {
            "focusNodeId": "C04",
            "focusNodeTitle": "Invoice Directory",
            "selectedInvoiceNum": invoice,
            "invoiceNum": invoice,
            "entityType": "invoice",
            "entityId": invoice,
            "entityTitle": "Invoice " + invoice,
            "option3EntityType": "invoice",
            "option3EntityId": invoice,
            "option3EntityTitle": "Invoice " + invoice,
            "tabTitle": "Invoice Directory: " + invoice,
            "forceNewInstance": true,
            "dirty": false
        })
    }

    function openMatterProfile(row, href) {
        var matterId = root.cleanText(href).replace(/^matter:/, "")
        if (matterId.length === 0)
            return
        try {
            matterId = decodeURIComponent(matterId)
        } catch (error) {
            return
        }

        var links = row && row.matterLinks && row.matterLinks.length !== undefined
            ? row.matterLinks : []
        var selected = null
        for (var i = 0; i < links.length; ++i) {
            if (root.cleanText(links[i].matterId) === matterId) {
                selected = links[i]
                break
            }
        }
        if (!selected)
            return

        var matterName = root.cleanText(selected.matterName)
        var clientName = root.cleanText(selected.clientName)
        var title = clientName.length > 0 ? clientName + " \u2014 " + matterName : matterName
        root.workspaceOpenRequested(0, "A11", {
            "focusNodeId": "A11",
            "focusNodeTitle": "Matter Profile 360",
            "selectedMatterId": matterId,
            "selectedMatterName": matterName,
            "matterDirectoryQueryText": matterName,
            "matterDirectoryModeText": "all",
            "entityType": "matter",
            "entityId": matterId,
            "entityTitle": title,
            "option3EntityType": "matter",
            "option3EntityId": matterId,
            "option3EntityTitle": title,
            "tabTitle": "Matter: " + title,
            "dirty": false
        })
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
        root.statusText = root.selectedInvoiceCount() + " invoice" + (root.selectedInvoiceCount() === 1 ? "" : "s")
                + " selected — " + root.formatCurrency(root.selectedBalance()) + ". Click Preview Statement when ready."
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
        if (billingClientCombo.editText !== name)
            billingClientCombo.editText = name
        if (shouldLoad && name.length > 0)
            root.refreshOpenInvoices()
    }

    function nextRequestId(prefix) {
        root.requestSequence += 1
        return String(prefix || "statement") + "-" + String(root.requestSequence)
    }

    function applyBillingClientRows(rows) {
        var sourceRows = rows || []
        var namesOut = []
        for (var j = 0; j < sourceRows.length; ++j) {
            var name = root.cleanText(sourceRows[j].name || sourceRows[j])
            if (name.length > 0 && namesOut.indexOf(name) < 0)
                namesOut.push(name)
        }
        root.billingClientRows = sourceRows
        root.billingClientNames = namesOut
        if (root.billingClientName.length === 0 && root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, false)
    }

    function loadBillingClients() {
        if (!root.appRef)
            return
        if (typeof root.appRef.requestStatementBillingClients === "function") {
            root.billingClientsRequestId = root.nextRequestId("statement-clients")
            root.busy = true
            root.statusText = "Loading billing clients..."
            root.appRef.requestStatementBillingClients(root.billingClientsRequestId)
            return
        }

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
        root.applyBillingClientRows(rows)
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
        if (typeof root.appRef.requestStatementOfAccount === "function") {
            root.statementRequestId = root.nextRequestId("statement-open-invoices")
            root.appRef.requestStatementOfAccount(root.statementRequestId, root.basePayload())
            return
        }
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

    function applyOpenInvoicesResponse(response) {
        root.busy = false
        root.statementRequestId = ""
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
        if (typeof root.appRef.requestStatementOfAccount === "function") {
            root.statementRequestId = root.nextRequestId("statement-preview")
            root.appRef.requestStatementOfAccount(root.statementRequestId, payload)
            return
        }
        var response = root.appRef.getStatementOfAccount(payload)
        root.busy = false
        if (response && response.ok) {
            root.reportData = response
            root.availableInvoices = response.availableInvoices || root.availableInvoices
            root.statusText = "Statement preview opened — " + selected.length + " invoice"
                    + (selected.length === 1 ? "" : "s") + " included, "
                    + root.formatCurrency(root.selectedBalance()) + " due."
            root.reportWindowRequested(response)
        } else {
            root.statusText = "Could not generate statement: " + root.cleanText(response && response.message)
        }
    }

    function applyGeneratedStatementResponse(response, selected) {
        root.busy = false
        root.statementRequestId = ""
        if (response && response.ok) {
            root.reportData = response
            root.availableInvoices = response.availableInvoices || root.availableInvoices
            root.statusText = "Statement preview opened - " + selected.length + " invoice"
                    + (selected.length === 1 ? "" : "s") + " included, "
                    + root.formatCurrency(root.selectedBalance()) + " due."
            root.reportWindowRequested(response)
        } else {
            root.statusText = "Could not generate statement: " + root.cleanText(response && response.message)
        }
    }

    Component.onCompleted: {
        // Allow the tab shell to paint before its workbook-backed request is
        // queued to the controller's background worker.
        Qt.callLater(function() {
            root.loadBillingClients()
            if (root.useContextClient && root.selectedClientLabel.length > 0)
                root.setBillingClient(root.selectedClientLabel, true)
        })
    }

    onAppRefChanged: {
        if (root.appRef)
            root.loadBillingClients()
    }
    onSelectedClientLabelChanged: {
        if (root.useContextClient && root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, root.visible)
    }
    onVisibleChanged: {
        if (visible && root.useContextClient && root.billingClientName.length === 0 && root.selectedClientLabel.length > 0)
            root.setBillingClient(root.selectedClientLabel, true)
    }

    Connections {
        target: root.appRef

        function onStatementBillingClientsReady(requestId, rows) {
            if (root.cleanText(requestId) !== root.billingClientsRequestId)
                return
            root.billingClientsRequestId = ""
            root.busy = false
            root.applyBillingClientRows(rows || [])
            if (root.billingClientNames.length > 0 && root.billingClientName.length === 0)
                root.statusText = "Choose a billing client to load its unpaid invoices."
        }

        function onStatementBillingClientsFailed(requestId, message) {
            if (root.cleanText(requestId) !== root.billingClientsRequestId)
                return
            root.billingClientsRequestId = ""
            root.busy = false
            root.statusText = "Could not load billing clients: " + root.cleanText(message)
        }

        function onStatementOfAccountReady(requestId, response) {
            if (root.cleanText(requestId) !== root.statementRequestId)
                return
            if (String(requestId).indexOf("statement-preview-") === 0)
                root.applyGeneratedStatementResponse(response || {}, root.selectedInvoiceNumbers())
            else
                root.applyOpenInvoicesResponse(response || {})
        }

        function onStatementOfAccountFailed(requestId, message) {
            if (root.cleanText(requestId) !== root.statementRequestId)
                return
            root.statementRequestId = ""
            root.busy = false
            root.statusText = "Could not prepare statement: " + root.cleanText(message)
        }
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
                Layout.preferredHeight: 112
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

                        ModernComboBox {
                            id: billingClientCombo
                            t: root.t
                            metrics: root.metrics
                            appStyle: root.appStyle
                            label: "Billing Client"
                            emptyOptionLabel: "Select a billing client…"
                            fullModel: root.billingClientNames
                            smartFilterEnabled: true
                            preserveEditTextOnModelChanged: true
                            currentIndex: root.billingClientName.length > 0
                                ? root.billingClientNames.indexOf(root.billingClientName)
                                : -1
                            Layout.preferredWidth: 430
                            Layout.minimumWidth: 300
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            onActivated: function(index) { root.setBillingClient(editText, false) }
                            onEditTextChanged: {
                                if (editText === root.billingClientName)
                                    return
                                root.setBillingClient(editText, false)
                            }
                        }

                        ModernTextField {
                            id: asOfDateInput
                            t: root.t
                            metrics: root.metrics
                            appStyle: root.appStyle
                            label: "Statement Date"
                            datePickerEnabled: true
                            Layout.preferredWidth: 180
                            Layout.preferredHeight: 48
                            text: root.asOfDateText
                            onTextChanged: root.asOfDateText = text
                        }

                        PillButton {
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            text: root.busy ? "Loading…" : "Load Open Invoices"
                            enabled: !root.busy && root.hasBillingClientChoice(root.billingClientName)
                            primary: true
                            Layout.preferredWidth: 160
                            Layout.preferredHeight: 48
                            Layout.alignment: Qt.AlignBottom
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
                        PillButton {
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            text: "Select All"
                            enabled: root.availableInvoices.length > 0 && !root.busy
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 34
                            onClicked: root.selectAllInvoices(true)
                        }
                        PillButton {
                            t: root.t
                            metrics: root.metrics
                            sfxBus: root.sfxBus
                            text: "Clear"
                            enabled: root.availableInvoices.length > 0 && !root.busy
                            Layout.preferredWidth: 82
                            Layout.preferredHeight: 34
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
                        Text { text: "Client & Matter"; Layout.fillWidth: true; font.pixelSize: visualRules.proCaptionFontPx; font.family: visualRules.textFontFamily; font.weight: Font.DemiBold; color: SemanticTheme.inkMuted(root.t, root.appStyle) }
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
                                Text {
                                    id: invoiceNumberLink
                                    text: invoiceRow.modelData.invoice || ""
                                    Layout.preferredWidth: 90
                                    elide: Text.ElideRight
                                    font.pixelSize: visualRules.proBodyFontPx
                                    font.family: visualRules.textFontFamily
                                    font.weight: Font.DemiBold
                                    font.underline: true
                                    color: SemanticTheme.accentPrimary(root.t, root.appStyle)
                                    MouseArea {
                                        id: invoiceNumberMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.openInvoiceDirectory(invoiceRow.modelData)
                                    }
                                    ToolTip.visible: invoiceNumberMouse.containsMouse
                                    ToolTip.text: "Open this invoice in Invoice Directory"
                                }
                                Text {
                                    id: matterLinksText
                                    text: root.matterLinkMarkup(invoiceRow.modelData)
                                    textFormat: Text.RichText
                                    Layout.fillWidth: true
                                    clip: true
                                    wrapMode: Text.NoWrap
                                    font.pixelSize: visualRules.proBodyFontPx
                                    font.family: visualRules.textFontFamily
                                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                    MouseArea {
                                        id: matterLinksMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        property string hoveredLink: ""
                                        onPositionChanged: function(mouse) {
                                            hoveredLink = matterLinksText.linkAt(mouse.x, mouse.y)
                                        }
                                        onExited: hoveredLink = ""
                                        cursorShape: hoveredLink.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: function(mouse) {
                                            var link = matterLinksText.linkAt(mouse.x, mouse.y)
                                            if (link.length > 0)
                                                root.openMatterProfile(invoiceRow.modelData, link)
                                        }
                                    }
                                    ToolTip.visible: matterLinksMouse.containsMouse && matterLinksMouse.hoveredLink.length > 0
                                    ToolTip.text: "Open this matter in Matter Profile 360"
                                }
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
                    PillButton {
                        t: root.t
                        metrics: root.metrics
                        sfxBus: root.sfxBus
                        text: "Preview Statement"
                        enabled: !root.busy && root.selectedInvoiceCount() > 0
                        primary: true
                        Layout.preferredWidth: 164
                        Layout.preferredHeight: 40
                        onClicked: root.generateStatement()
                    }
                }
            }
        }
    }
}
