pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property var metrics
    property var appRef
    property var sfxBus
    property bool dirty: false
    property bool _hydrating: false
    property bool _updatingLookups: false
    property var _clients: []
    property var _matters: []
    property string feedbackText: ""
    property bool feedbackIsError: false

    signal saved(var result)

    ArchivedMatterEntryGuardDialog {
        id: archivedMatterFeeGuard
        t: root.t
        appRef: root.appRef
        entryKind: "fee"
        onEntryConfirmed: root.saveFeeEntry(true)
    }

    readonly property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : "Professional"
    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color surface: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color inputSurface: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color outlineColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)

    radius: 8
    color: root.surface
    border.width: 1
    border.color: root.outlineColor

    function normalized(value) {
        return String(value === undefined || value === null ? "" : value).trim().toLowerCase()
    }

    function matterLabel(row) {
        var number = String(row && row.matterNumber ? row.matterNumber : "").trim()
        var name = String(row && (row.matterName || row.displayName) ? (row.matterName || row.displayName) : "").trim()
        return number.length > 0 && name.length > 0 ? number + " - " + name : (name || number)
    }

    function findMatter(value) {
        var lookup = normalized(value)
        if (!lookup.length) return null
        var best = null
        var bestScore = -1
        for (var i = 0; i < root._matters.length; i++) {
            var row = root._matters[i] || ({})
            var matterId = normalized(row.matterId)
            var number = normalized(row.matterNumber)
            var name = normalized(row.matterName)
            var display = normalized(row.displayName)
            var label = normalized(matterLabel(row))
            var score = -1
            if (matterId && lookup === matterId) score = 1000
            else if (number && lookup === number) score = 900
            else if (label && lookup === label) score = 850
            else if (display && lookup === display) score = 700
            else if (name && lookup === name) score = 500
            else if (number && lookup.indexOf(number) === 0) score = 450
            if (score > bestScore) {
                best = row
                bestScore = score
            }
        }
        return best
    }

    function setFeedback(message, isError) {
        root.feedbackText = String(message || "").trim()
        root.feedbackIsError = !!isError
        if (root.feedbackText.length > 0) feedbackTimer.restart()
    }

    function refreshLookupLists() {
        if (!root.appRef) return
        try {
            if (root.appRef.listClientDirectory) {
                var clients = root.appRef.listClientDirectory()
                if (clients) root._clients = clients
            }
        } catch (clientError) {
        }
        try {
            if (root.appRef.listMatterDirectory) {
                var matters = root.appRef.listMatterDirectory()
                if (matters) root._matters = matters
            }
        } catch (matterError) {
        }
        rebuildLookupOptions("refresh")
    }

    function rebuildLookupOptions(source) {
        if (root._updatingLookups) return
        root._updatingLookups = true

        var selectedMatter = findMatter(matterCombo.editText)
        if (source === "matter" && selectedMatter) {
            var linkedClient = String(selectedMatter.clientName || "").trim()
            if (linkedClient.length > 0) clientCombo.editText = linkedClient
        }

        var clientOptions = []
        var seenClients = ({})
        for (var i = 0; i < root._clients.length; i++) {
            var client = root._clients[i] || ({})
            var clientName = String(client.clientName || client.displayName || "").trim()
            if (!clientName.length) continue
            var clientKey = clientName.toLowerCase()
            if (seenClients[clientKey]) continue
            seenClients[clientKey] = true
            clientOptions.push(clientName)
        }
        clientOptions.sort()
        clientCombo.fullModel = clientOptions

        var selectedClient = normalized(clientCombo.editText)
        var matterOptions = []
        for (var j = 0; j < root._matters.length; j++) {
            var matter = root._matters[j] || ({})
            var matterClient = normalized(matter.clientName)
            if (selectedClient.length > 0 && matterClient !== selectedClient) continue
            var label = matterLabel(matter)
            if (label.length > 0) matterOptions.push(label)
        }
        matterOptions.sort()
        matterCombo.fullModel = matterOptions

        root._updatingLookups = false
    }

    function parseFeeAmount(text) {
        var parsed = Number(String(text || "").replace(/[$,\s]/g, ""))
        return isFinite(parsed) ? parsed : NaN
    }

    function clearFeeForm() {
        root._hydrating = true
        feeAmountInput.text = ""
        descriptionInput.text = ""
        statusCombo.editText = "Ready for Billing"
        root._hydrating = false
        root.dirty = false
        root.feedbackText = ""
    }

    function saveFeeEntry(skipArchivedGuard) {
        var selectedMatter = findMatter(matterCombo.editText)
        if (!selectedMatter || !String(selectedMatter.matterId || "").trim().length) {
            setFeedback("Select an existing matter before saving a fee entry.", true)
            return false
        }
        var matterStatus = normalized(selectedMatter.status)
        if (selectedMatter.active === 0 || selectedMatter.active === false
                || matterStatus === "closed" || matterStatus === "archived") {
            if (matterStatus === "archived" && !skipArchivedGuard) {
                archivedMatterFeeGuard.openFor(selectedMatter)
                setFeedback("Matter is archived. No fee entry was saved.", true)
            } else {
                setFeedback("The selected matter is closed or inactive.", true)
            }
            return false
        }

        var amount = parseFeeAmount(feeAmountInput.text)
        if (!isFinite(amount) || amount <= 0) {
            setFeedback("Enter a fee amount greater than zero.", true)
            return false
        }

        if (!root.appRef || !root.appRef.saveFeeDocketEntry) {
            setFeedback("Fee entry saving is unavailable.", true)
            return false
        }

        var result = ({})
        try {
            result = root.appRef.saveFeeDocketEntry({
                "dateText": String(dateInput.text || "").trim(),
                "clientText": String(selectedMatter.clientName || clientCombo.editText || "").trim(),
                "matterText": String(selectedMatter.matterName || matterCombo.editText || "").trim(),
                "matterId": String(selectedMatter.matterId || "").trim(),
                "amount": amount,
                "descriptionText": String(descriptionInput.text || "").trim(),
                "status": String(statusCombo.editText || "Ready for Billing").trim()
            })
        } catch (saveError) {
            result = { "ok": false, "message": String(saveError) }
        }

        if (result && result.ok && result.verifiedExact) {
            var entryId = String(result.entryId || "").trim()
            setFeedback("Fee entry saved" + (entryId.length ? ": " + entryId : "") + ".", false)
            root._hydrating = true
            feeAmountInput.text = ""
            descriptionInput.text = ""
            root._hydrating = false
            root.dirty = false
            root.saved(result)
            return true
        }

        setFeedback(String((result && result.message) || "Fee entry could not be saved."), true)
        return false
    }

    Timer {
        id: feedbackTimer
        interval: 5500
        repeat: false
        onTriggered: root.feedbackText = ""
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        Text {
            Layout.fillWidth: true
            text: "Enter a matter-linked fee directly into invoiceable WIP. When the matter has only fee entries, its invoice is rendered as a flat-fee invoice."
            color: root.mutedInk
            font.pixelSize: 13
            wrapMode: Text.WordWrap
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 12
            columnSpacing: 14
            rowSpacing: 14

            ModernTextField {
                id: dateInput
                t: root.t
                metrics: root.metrics
                label: "Fee Date"
                text: Qt.formatDate(new Date(), "yyyy-MM-dd")
                datePickerEnabled: true
                Layout.fillWidth: true
                Layout.columnSpan: 3
                Layout.preferredHeight: 52
                onTextChanged: if (!root._hydrating) root.dirty = true
            }

            ModernComboBox {
                id: clientCombo
                t: root.t
                metrics: root.metrics
                label: "Client"
                fullModel: []
                Layout.fillWidth: true
                Layout.columnSpan: 4
                Layout.preferredHeight: 52
                z: 2
                onActivated: {
                    root.rebuildLookupOptions("client")
                    if (!root._hydrating) root.dirty = true
                }
                onEditTextChanged: {
                    root.rebuildLookupOptions("client")
                    if (!root._hydrating && !root._updatingLookups) root.dirty = true
                }
                onActiveFocusChanged: if (activeFocus) root.refreshLookupLists()
            }

            ModernComboBox {
                id: matterCombo
                t: root.t
                metrics: root.metrics
                label: "Matter"
                fullModel: []
                Layout.fillWidth: true
                Layout.columnSpan: 5
                Layout.preferredHeight: 52
                z: 1
                onActivated: {
                    root.rebuildLookupOptions("matter")
                    if (!root._hydrating) root.dirty = true
                }
                onEditTextChanged: {
                    root.rebuildLookupOptions("matter")
                    if (!root._hydrating && !root._updatingLookups) root.dirty = true
                }
                onActiveFocusChanged: if (activeFocus) root.refreshLookupLists()
            }

            ModernTextField {
                id: feeAmountInput
                t: root.t
                metrics: root.metrics
                label: "Fee Amount ($)"
                placeholderText: "0.00"
                inputMethodHints: Qt.ImhFormattedNumbersOnly
                Layout.fillWidth: true
                Layout.columnSpan: 3
                Layout.preferredHeight: 52
                onTextChanged: if (!root._hydrating) root.dirty = true
            }

            ModernComboBox {
                id: statusCombo
                t: root.t
                metrics: root.metrics
                label: "WIP Status"
                fullModel: ["Draft", "Ready for Billing"]
                editText: "Ready for Billing"
                Layout.fillWidth: true
                Layout.columnSpan: 3
                Layout.preferredHeight: 52
                z: 1
                onActivated: if (!root._hydrating) root.dirty = true
                onEditTextChanged: if (!root._hydrating) root.dirty = true
            }

            Text {
                Layout.fillWidth: true
                Layout.columnSpan: 6
                Layout.alignment: Qt.AlignVCenter
                text: "HST is calculated automatically when the fee is invoiced."
                color: root.mutedInk
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.columnSpan: 12
                Layout.preferredHeight: 172
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                background: Rectangle {
                    radius: 6
                    color: root.inputSurface
                    border.width: 1
                    border.color: descriptionInput.activeFocus ? root.accent : root.outlineColor
                }

                TextArea {
                    id: descriptionInput
                    width: parent.width
                    height: Math.max(parent.height, implicitHeight)
                    leftPadding: 12
                    rightPadding: 12
                    topPadding: 10
                    bottomPadding: 10
                    color: root.ink
                    placeholderText: "Fee description for the invoice (for example, Flat fee for incorporation filing)"
                    placeholderTextColor: root.mutedInk
                    wrapMode: Text.Wrap
                    background: null
                    onTextChanged: if (!root._hydrating) root.dirty = true
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 42 : 0
            visible: root.feedbackText.length > 0
            radius: 6
            color: root.feedbackIsError
                ? SemanticTheme.tone(root.t, "error", root.appStyle)
                : SemanticTheme.tone(root.t, "success", root.appStyle)

            Text {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: Text.AlignVCenter
                text: root.feedbackText
                color: SemanticTheme.textOnAccent(root.t, root.appStyle)
                font.pixelSize: 13
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            PillButton {
                t: root.t
                metrics: root.metrics
                sfxBus: root.sfxBus
                text: "Clear Fee"
                primary: false
                Layout.preferredWidth: 150
                Layout.preferredHeight: 44
                onClicked: root.clearFeeForm()
            }

            Item { Layout.fillWidth: true }

            PillButton {
                t: root.t
                metrics: root.metrics
                sfxBus: root.sfxBus
                text: "Save Fee Entry"
                primary: true
                Layout.preferredWidth: 184
                Layout.preferredHeight: 44
                onClicked: root.saveFeeEntry()
            }
        }
    }

    Connections {
        target: root.appRef
        function onClientDataChanged() {
            root.refreshLookupLists()
        }
    }

    Component.onCompleted: root.refreshLookupLists()
    onVisibleChanged: if (visible) root.refreshLookupLists()
}
