import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: gridWindow
    width: 1000
    height: 700
    title: "Analysis Review Grid"
    color: gridWindow.isProMode ? SemanticTheme.surfaceApp(gridWindow.t, gridWindow.appStyle) : "#F9F9FB"
    visible: false
    Component.onCompleted: {
        if (gridWindow.importView && gridWindow.importView.Window && gridWindow.importView.Window.window) {
            var targetScreen = gridWindow.importView.Window.window.screen
            gridWindow.screen = targetScreen
            var vx = targetScreen.virtualX !== undefined ? targetScreen.virtualX : 0
            var vy = targetScreen.virtualY !== undefined ? targetScreen.virtualY : 0
            gridWindow.x = vx + 100
            gridWindow.y = vy + 100
            gridWindow.transientParent = gridWindow.importView.Window.window
        }
    }

    property var t: null
    property string appStyle: (gridWindow.appRef && gridWindow.appRef.appStyle) ? String(gridWindow.appRef.appStyle) : "Professional"
    property bool isProMode: gridWindow.appStyle === "Professional"

    VisualRules {
        id: defaultVisualRules
        appStyle: gridWindow.appStyle
    }

    property var appRef: null
    property var visualRules: null
    property var analysisResult: null
    property var rowsData: []
    property var importView: null
    property var selectedMap: ({})
    property string selectionHint: "Review and select rows manually, or use the safe docket update for missing time entries only."
    property var safeSelectionSummary: ({ "applied": false })

    ListModel {
        id: columnsModel
        ListElement { key: "selected"; title: ""; isVisible: true; colWidth: 40; isCheckbox: true }
        ListElement { key: "sheet"; title: "Sheet"; isVisible: true; colWidth: 100 }
        ListElement { key: "row"; title: "Row"; isVisible: true; colWidth: 60 }
        ListElement { key: "action"; title: "Action"; isVisible: true; colWidth: 80 }
        ListElement { key: "title"; title: "Title"; isVisible: true; colWidth: 200 }
        ListElement { key: "details"; title: "Details"; isVisible: true; colWidth: 250 }
        ListElement { key: "payload"; title: "Payload"; isVisible: true; colWidth: 400 }
    }

    property string sortCol: ""
    property bool sortAsc: true

    property string sheetFilter: "All"
    onSheetFilterChanged: refreshRows()

    property int metricNewClients: 0
    property int metricNewMatters: 0
    property int metricNewDockets: 0
    property int metricNewLedger: 0
    property int metricSkipped: 0

    onAnalysisResultChanged: {
        safeSelectionSummary = ({ "applied": false })
        refreshMetrics()
        refreshRows()
    }
    property bool metricHasSelected: false
    property bool metricAllSelected: false

    function sourceText(rowData, key) {
        var payload = rowData && rowData.payload ? rowData.payload : ({})
        var value = payload[key]
        return value === undefined || value === null ? "" : String(value).trim()
    }

    function sourceNumber(rowData, key) {
        var payload = rowData && rowData.payload ? rowData.payload : ({})
        var value = payload[key]
        if (value === undefined || value === null || value === "") return 0
        var parsed = Number(String(value).replace(/[$,]/g, ""))
        return isNaN(parsed) ? 0 : parsed
    }

    function displayMoney(value) {
        var amount = Number(value || 0)
        var fixed = amount.toFixed(2)
        return "$" + fixed.replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    function displayHours(value) {
        var tenths = Math.round(Number(value || 0) * 10)
        var prefix = tenths < 0 ? "-" : ""
        tenths = Math.abs(tenths)
        return prefix + String(Math.floor(tenths / 10)) + "." + String(tenths % 10)
    }

    function selectSafeDocketUpdate() {
        // This deliberately selects only newly identified docket rows and the
        // new client/matter setup they require. It never selects legacy ledger,
        // A/R, invoice-log, disbursement, or unrelated directory rows.
        var rows = analysisResult && analysisResult.rows ? analysisResult.rows : []
        var selected = ({})
        var requiredMatterIds = ({})
        var requiredClientIds = ({})
        var selectedDockets = 0
        var selectedMatters = 0
        var selectedClients = 0
        var selectedHours = 0
        var selectedAmount = 0

        function selectRow(rowData) {
            var sheet = String(rowData.sheet || "")
            var rowNumber = String(rowData.row || "")
            if (!sheet || !rowNumber) return
            if (!selected[sheet]) selected[sheet] = ({})
            selected[sheet][rowNumber] = true
        }

        for (var i = 0; i < rows.length; i++) {
            var docket = rows[i]
            if (String(docket.sheet || "") !== "Dockets"
                    || String(docket.action || "") !== "add"
                    || docket.safeDocketCandidate !== true) continue
            selectRow(docket)
            selectedDockets += 1
            selectedHours += Number(docket.safeDocketHours || sourceNumber(docket, "Time (in hrs)") || 0)
            selectedAmount += Number(docket.safeDocketAmount || sourceNumber(docket, "Amount to CS") || 0)
            var matterId = sourceText(docket, "Matter_ID").toLowerCase()
            if (matterId) requiredMatterIds[matterId] = true
        }

        for (var j = 0; j < rows.length; j++) {
            var matter = rows[j]
            if (String(matter.sheet || "") !== "Matters" || String(matter.action || "") !== "add") continue
            var sourceMatterId = sourceText(matter, "Matter_ID").toLowerCase()
            if (!requiredMatterIds[sourceMatterId]) continue
            selectRow(matter)
            selectedMatters += 1
            var clientId = sourceText(matter, "Client_ID").toLowerCase()
            if (clientId) requiredClientIds[clientId] = true
        }

        for (var k = 0; k < rows.length; k++) {
            var client = rows[k]
            if (String(client.sheet || "") !== "Clients" || String(client.action || "") !== "add") continue
            var sourceClientId = sourceText(client, "Client_ID").toLowerCase()
            if (!requiredClientIds[sourceClientId]) continue
            selectRow(client)
            selectedClients += 1
        }

        selectedMap = selected
        selectedMapChanged()
        refreshRows()
        safeSelectionSummary = {
            "applied": true,
            "dockets": selectedDockets,
            "matters": selectedMatters,
            "clients": selectedClients,
            "hours": selectedHours,
            "amount": selectedAmount
        }
        selectionHint = "Safe selection ready: " + selectedDockets + " new docket(s), "
                + selectedMatters + " required matter(s), and " + selectedClients
                + " required client(s). " + displayHours(selectedHours) + " hours and "
                + displayMoney(selectedAmount) + " of WIP are selected. No financial or unrelated legacy rows are selected."
    }

    function refreshMetrics() {
        if (!analysisResult || !analysisResult.rows) return
        var c = 0, m = 0, d = 0, l = 0, s = 0;
        for (var i=0; i<analysisResult.rows.length; i++) {
            var row = analysisResult.rows[i];
            if (row.action === "add") {
                if (row.sheet === "Clients") c++;
                else if (row.sheet === "Matters") m++;
                else if (row.sheet === "Dockets") d++;
                else if (row.sheet.indexOf("Ledger") === 0) l++;
            } else if (row.action === "skip") {
                s++;
            }
        }
        metricNewClients = c;
        metricNewMatters = m;
        metricNewDockets = d;
        metricNewLedger = l;
        metricSkipped = s;
    }

    function refreshRows() {
        if (analysisResult && analysisResult.rows) {
            var filtered = []
            var allSel = true
            for (var i=0; i<analysisResult.rows.length; i++) {
                var row = analysisResult.rows[i]
                if (sheetFilter !== "All" && row.sheet !== sheetFilter) continue
                if (row.action === "skip") continue
                if (row.selected === undefined) row.selected = false
                if (!row.selected) allSel = false
                filtered.push(row)
            }
            metricAllSelected = (filtered.length > 0 && allSel)
            rowsData = filtered
            applySort()
        } else {
            rowsData = []
            metricAllSelected = false
        }
    }

    function applySort() {
        if (!sortCol) return
        var sorted = rowsData.slice()
        sorted.sort(function(a, b) {
            var valA = a[sortCol] !== undefined ? String(a[sortCol]) : ""
            var valB = b[sortCol] !== undefined ? String(b[sortCol]) : ""
            var res = valA.localeCompare(valB)
            return sortAsc ? res : -res
        })
        rowsData = sorted
    }

    function toggleSort(colKey) {
        if (sortCol === colKey) {
            sortAsc = !sortAsc
        } else {
            sortCol = colKey
            sortAsc = true
        }
        applySort()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "Legacy Import Analysis Review"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#1E1E1E"
                Layout.fillWidth: true
            }

            Button {
                text: "Select Safe Docket Update"
                Layout.preferredHeight: 36
                enabled: gridWindow.analysisResult && gridWindow.analysisResult.rows
                onClicked: gridWindow.selectSafeDocketUpdate()
                ToolTip.visible: hovered
                ToolTip.text: "Select new dockets and only the new client/matter records they require. Ledger, A/R, invoices, disbursements, and unrelated records remain unselected."
            }


            Button {
                text: "Import Selected Data"
                Layout.preferredHeight: 36
                enabled: gridWindow.importView !== undefined
                onClicked: {
                    var allowedRows = {}
                    var sheets = Object.keys(gridWindow.selectedMap || {})
                    for (var i = 0; i < sheets.length; i++) {
                        var sh = sheets[i]
                        var rowsObj = gridWindow.selectedMap[sh]
                        var rowsKeys = Object.keys(rowsObj)
                        for (var j = 0; j < rowsKeys.length; j++) {
                            var rStr = rowsKeys[j]
                            if (rowsObj[rStr] === true) {
                                if (!allowedRows[sh]) allowedRows[sh] = []
                                allowedRows[sh].push(parseInt(rStr))
                            }
                        }
                    }

                    if (gridWindow.importView) {
                        gridWindow.importView.startFilteredImport(allowedRows)
                        gridWindow.close()
                    } else {
                        console.error("Failed to start filtered import")
                    }
                }
            }

            Button {
                text: "Export to Excel"
                Layout.preferredHeight: 36
                onClicked: {
                    if (appRef && appRef.exportLegacyDocketsAnalysisExcel && analysisResult) {
                        var res = appRef.exportLegacyDocketsAnalysisExcel(analysisResult)
                        if (res.ok) {
                            console.log("Exported successfully to: " + res.path)
                        } else {
                            console.error("Export failed: " + res.message)
                        }
                    }
                }
            }

            Button {
                text: "Close"
                Layout.preferredHeight: 36
                onClicked: gridWindow.close()
            }
        }

        Text {
            Layout.fillWidth: true
            text: gridWindow.selectionHint
            wrapMode: Text.WordWrap
            font.pixelSize: 12
            color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A"
        }

        Rectangle {
            visible: Boolean(gridWindow.safeSelectionSummary && gridWindow.safeSelectionSummary.applied)
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 76 : 0
            color: gridWindow.isProMode
                ? SemanticTheme.surfaceRaised(gridWindow.t, gridWindow.appStyle)
                : "#EEF6FF"
            border.color: gridWindow.isProMode
                ? SemanticTheme.accentPrimary(gridWindow.t, gridWindow.appStyle)
                : "#8DB8E8"
            border.width: 1
            radius: gridWindow.isProMode ? (gridWindow.visualRules ? gridWindow.visualRules.radiusPanel : defaultVisualRules.radiusPanel) : 6

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 26

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "SAFE DOCKET UPDATE READY"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#16355D"
                    }
                    Text {
                        text: "Only reconciliation-confirmed missing dockets and their required setup are selected."
                        font.pixelSize: 11
                        color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#46688F"
                    }
                }

                Item { Layout.fillWidth: true }

                ColumnLayout {
                    spacing: 2
                    Text { text: "DOCKETS"; font.pixelSize: 10; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#46688F" }
                    Text { text: String(gridWindow.safeSelectionSummary.dockets || 0); font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.tone(gridWindow.t, "success", gridWindow.appStyle) : "#16764A" }
                }
                ColumnLayout {
                    spacing: 2
                    Text { text: "HOURS"; font.pixelSize: 10; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#46688F" }
                    Text { text: gridWindow.displayHours(gridWindow.safeSelectionSummary.hours); font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#16355D" }
                }
                ColumnLayout {
                    spacing: 2
                    Text { text: "WIP"; font.pixelSize: 10; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#46688F" }
                    Text { text: gridWindow.displayMoney(gridWindow.safeSelectionSummary.amount); font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#16355D" }
                }
                ColumnLayout {
                    spacing: 2
                    Text { text: "SETUP"; font.pixelSize: 10; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#46688F" }
                    Text { text: String(gridWindow.safeSelectionSummary.clients || 0) + " client · " + String(gridWindow.safeSelectionSummary.matters || 0) + " matter"; font.pixelSize: 12; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#16355D" }
                }
            }
        }

        // Summary Metrics
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: gridWindow.isProMode ? SemanticTheme.surfacePanel(gridWindow.t, gridWindow.appStyle) : "#FFFFFF"
            border.color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
            radius: gridWindow.isProMode ? (gridWindow.visualRules ? gridWindow.visualRules.radiusPanel : defaultVisualRules.radiusPanel) : 6

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 24

                ColumnLayout {
                    spacing: 4
                    Text { text: "New Clients"; font.pixelSize: 11; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A" }
                    Text { text: gridWindow.metricNewClients; font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.tone(gridWindow.t, "success", gridWindow.appStyle) : "#2E8B57" }
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "New Matters"; font.pixelSize: 11; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A" }
                    Text { text: gridWindow.metricNewMatters; font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.tone(gridWindow.t, "success", gridWindow.appStyle) : "#2E8B57" }
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "New Dockets"; font.pixelSize: 11; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A" }
                    Text { text: gridWindow.metricNewDockets; font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.tone(gridWindow.t, "success", gridWindow.appStyle) : "#2E8B57" }
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "New Ledger Entries"; font.pixelSize: 11; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A" }
                    Text { text: gridWindow.metricNewLedger; font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.tone(gridWindow.t, "success", gridWindow.appStyle) : "#2E8B57" }
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "Skipped (Duplicates)"; font.pixelSize: 11; font.weight: Font.DemiBold; color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A" }
                    Text { text: gridWindow.metricSkipped; font.pixelSize: 18; font.weight: Font.Bold; color: gridWindow.isProMode ? SemanticTheme.inkSubtle(gridWindow.t, gridWindow.appStyle) : "#555555" }
                }

                Item { Layout.fillWidth: true }
            }
        }

        // Column Configurator
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: gridWindow.isProMode ? SemanticTheme.surfacePanel(gridWindow.t, gridWindow.appStyle) : "#FFFFFF"
            border.color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
            radius: gridWindow.isProMode ? (gridWindow.visualRules ? gridWindow.visualRules.radiusControl : defaultVisualRules.radiusControl) : 6

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 12

                Text {
                    text: "Sheet Filter:"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A"
                }

                ComboBox {
                    id: sheetFilterCombo
                    model: ["All", "Clients", "Matters", "Dockets", "Ledger", "Ledger (A/R Deduced)"]
                    onCurrentTextChanged: {
                        gridWindow.sheetFilter = currentText
                    }
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 28
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
                    Layout.leftMargin: 4
                    Layout.rightMargin: 4
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
                    Layout.leftMargin: 4
                    Layout.rightMargin: 4
                }

                Text {
                    text: "Columns:"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: gridWindow.isProMode ? SemanticTheme.inkMuted(gridWindow.t, gridWindow.appStyle) : "#6E6E7A"
                }

                Repeater {
                    model: columnsModel
                    delegate: RowLayout {
                        spacing: 4
                        CheckBox {
                            checked: model.isVisible
                            onCheckedChanged: {
                                columnsModel.setProperty(index, "isVisible", checked)
                            }
                        }
                        Text {
                            text: model.title
                            font.pixelSize: 12
                            color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#1E1E1E"
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                
                Button {
                    text: "Import Selected Data"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    Layout.preferredHeight: 28
                    Layout.preferredWidth: 160
                    background: Rectangle {
                        color: parent.down ? (gridWindow.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(gridWindow.t, gridWindow.appStyle), 0.25) : "#28354A") : parent.hovered ? (gridWindow.isProMode ? SemanticTheme.alpha(SemanticTheme.accentPrimary(gridWindow.t, gridWindow.appStyle), 0.15) : "#3B4A63") : (gridWindow.isProMode ? SemanticTheme.accentPrimary(gridWindow.t, gridWindow.appStyle) : "#324158")
                        radius: gridWindow.isProMode ? (gridWindow.visualRules ? gridWindow.visualRules.radiusControl : defaultVisualRules.radiusControl) : 4
                    }
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: gridWindow.isProMode ? SemanticTheme.readableInk(SemanticTheme.accentPrimary(gridWindow.t, gridWindow.appStyle)) : "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (gridWindow.importView) {
                            var allowedRows = {}
                            for (var i = 0; i < gridWindow.rowsData.length; i++) {
                                var r = gridWindow.rowsData[i]
                                var isSel = gridWindow.selectedMap[r.sheet] && gridWindow.selectedMap[r.sheet][r.row] === true
                                if (isSel) {
                                    if (!allowedRows[r.sheet]) allowedRows[r.sheet] = []
                                    allowedRows[r.sheet].push(parseInt(r.row))
                                }
                            }
                            
                            gridWindow.importView.startFilteredImport(allowedRows)
                            gridWindow.close()
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: gridWindow.isProMode ? SemanticTheme.surfacePanel(gridWindow.t, gridWindow.appStyle) : "#FFFFFF"
            border.color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
            radius: gridWindow.isProMode ? (gridWindow.visualRules ? gridWindow.visualRules.radiusPanel : defaultVisualRules.radiusPanel) : 8
            clip: true

            ScrollView {
                id: scrollView
                anchors.fill: parent
                contentWidth: headerRow.implicitWidth
                contentHeight: contentCol.implicitHeight + headerRow.implicitHeight

                Column {
                    id: contentCol
                    spacing: 0

                    // Header
                    Row {
                        id: headerRow
                        spacing: 0
                        Repeater {
                            model: columnsModel
                            delegate: Rectangle {
                                visible: model.isVisible
                                width: model.colWidth
                                height: 36
                                color: gridWindow.isProMode ? SemanticTheme.surfaceRaised(gridWindow.t, gridWindow.appStyle) : "#F3F3F6"
                                border.color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    Loader {
                                        active: model.isCheckbox === true
                                        visible: active
                                        sourceComponent: CheckBox {
                                            id: headerCheck
                                            checked: gridWindow.metricAllSelected
                                            onClicked: {
                                                var val = checked
                                                gridWindow.metricAllSelected = val
                                                var sm = gridWindow.selectedMap || {}
                                                for (var i=0; i<gridWindow.rowsData.length; i++) {
                                                    var r = gridWindow.rowsData[i]
                                                    if (!sm[r.sheet]) sm[r.sheet] = {}
                                                    sm[r.sheet][r.row] = val
                                                }
                                                gridWindow.selectedMap = sm
                                                gridWindow.selectedMapChanged()
                                            }
                                        }
                                    }
                                    Text {
                                        visible: model.isCheckbox !== true
                                        text: model.title + (gridWindow.sortCol === model.key ? (gridWindow.sortAsc ? " \u2191" : " \u2193") : "")
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#1E1E1E"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    visible: model.isCheckbox !== true
                                    onClicked: gridWindow.toggleSort(model.key)
                                }
                            }
                        }
                    }

                    // Body
                    Repeater {
                        model: gridWindow.rowsData
                        delegate: Row {
                            id: dataRow
                            property var rowData: modelData
                            property int rowIndex: index
                            spacing: 0
                            Repeater {
                                model: columnsModel
                                delegate: Rectangle {
                                    visible: model.isVisible
                                    width: model.colWidth
                                    height: 48
                                    color: rowIndex % 2 === 0 ? (gridWindow.isProMode ? SemanticTheme.surfacePanel(gridWindow.t, gridWindow.appStyle) : "#FFFFFF") : (gridWindow.isProMode ? SemanticTheme.surfaceRaised(gridWindow.t, gridWindow.appStyle) : "#FAFAFC")
                                    border.color: gridWindow.isProMode ? SemanticTheme.borderSubtle(gridWindow.t, gridWindow.appStyle) : "#E2E2E8"
                                    border.width: 1

                                    Loader {
                                        anchors.centerIn: parent
                                        active: model.isCheckbox === true
                                        visible: active
                                        sourceComponent: CheckBox {
                                            checked: gridWindow.selectedMap[dataRow.rowData.sheet] && gridWindow.selectedMap[dataRow.rowData.sheet][dataRow.rowData.row] === true
                                            onClicked: {
                                                var sm = gridWindow.selectedMap || {}
                                                if (!sm[dataRow.rowData.sheet]) sm[dataRow.rowData.sheet] = {}
                                                sm[dataRow.rowData.sheet][dataRow.rowData.row] = checked
                                                gridWindow.selectedMap = sm
                                                gridWindow.selectedMapChanged()
                                                
                                                var allSel = true
                                                for (var i=0; i<gridWindow.rowsData.length; i++) {
                                                    var r = gridWindow.rowsData[i]
                                                    if (!sm[r.sheet] || sm[r.sheet][r.row] !== true) {
                                                        allSel = false
                                                        break
                                                    }
                                                }
                                                gridWindow.metricAllSelected = allSel
                                            }
                                        }
                                    }
                                    Text {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        visible: model.isCheckbox !== true
                                        text: {
                                            if (model.key === "payload") {
                                                return JSON.stringify(dataRow.rowData[model.key] || {})
                                            }
                                            return String(dataRow.rowData[model.key] || "")
                                        }
                                        font.pixelSize: 12
                                        color: gridWindow.isProMode ? SemanticTheme.inkPrimary(gridWindow.t, gridWindow.appStyle) : "#3A3A40"
                                        elide: Text.ElideRight
                                        verticalAlignment: Text.AlignVCenter
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
