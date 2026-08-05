pragma ComponentBehavior: Bound
import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root
    color: visualRules.isPro ? SemanticTheme.surfaceApp(root.t, root.appStyle) : "transparent"

    property var t
    property var metrics
    property var appRef
    property var sfxBus

    property string importMode: "all"
    property string startDate: ""
    property string endDate: ""
    property var availableDataTypes: ["Clients", "Matters", "Dockets", "Disbursements", "Billings", "Payments", "Expenses", "Write-offs", "Receivables", "Invoice Log"]
    property var selectedDataTypes: ["Clients", "Matters", "Dockets", "Disbursements", "Billings", "Payments", "Expenses", "Write-offs", "Receivables", "Invoice Log"]
    property string clientFilter: ""
    property var sourceClients: []
    property string statusMessage: ""
    property string filePath: ""
    property var recentFilePaths: []
    property bool importInProgress: false
    property bool importCompleted: false
    property bool lastImportSucceeded: false
    property bool lastImportCancelled: false
    property bool cancelRequested: false
    property string currentPhase: ""
    property bool analysisStarted: false
    property bool isExpanded: false
    property var activeHoverButton: null
    property bool analysisCompleted: false
    property int analysisCurrent: 0
    property int analysisTotal: 0
    property string analysisMessage: "Securing isolated import workspace"
    property bool sourceAnalysisInProgress: false
    property bool sourceAnalysisComplete: false
    property var analysisResult: null
    property int totalRows: 0
    property int overallRowsDone: 0
    property var rowCounts: ({})
    property var sheetProgress: ({})
    property var lastImportResult: ({})
    property var duplicatePromptPayload: ({})
    property bool duplicateApplyAll: false
    property var importSheetNames: ["Clients", "Matters", "Dockets", "Disbursements", "Ledger", "Receivables", "Invoice Log"]
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"

    readonly property color surfaceColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color raisedColor: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color inputColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color inputInkColor: SemanticTheme.readableInk(root.inputColor)
    readonly property color inputHintInkColor: SemanticTheme.alpha(root.inputInkColor, 0.84)
    readonly property color inputBorderColor: SemanticTheme.mix(root.borderColor, root.inputInkColor, visualRules.isPro ? 0.38 : 0.52)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property color accentColor: SemanticTheme.accentPrimary(root.t, root.appStyle)
    readonly property color successColor: SemanticTheme.tone(root.t, "success", root.appStyle)
    readonly property color warningColor: SemanticTheme.tone(root.t, "warning", root.appStyle)
    readonly property color errorColor: SemanticTheme.tone(root.t, "error", root.appStyle)

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function coerceInt(value) {
        var n = Number(value)
        if (isNaN(n)) return 0
        return Math.max(0, Math.round(n))
    }

    function resetProgressState() {
        root.importInProgress = false
        root.importCompleted = false
        root.lastImportSucceeded = false
        root.lastImportCancelled = false
        root.cancelRequested = false
        root.currentPhase = ""
        root.analysisStarted = false
        root.analysisCompleted = false
        root.analysisCurrent = 0
        root.analysisTotal = 0
        root.analysisMessage = "Securing isolated import workspace"
        root.totalRows = 0
        root.overallRowsDone = 0
        root.rowCounts = ({})
        root.sheetProgress = ({})
        root.lastImportResult = ({})
        root.duplicatePromptPayload = ({})
        root.duplicateApplyAll = false
    }

    function applyRecentFiles(result, autoSelectLast) {
        var files = []
        if (result && result.files && result.files.length !== undefined) {
            for (var i = 0; i < result.files.length; i++) {
                files.push(String(result.files[i] || ""))
            }
        }
        root.recentFilePaths = files
        var lastUsed = result ? String(result.lastUsedPath || "") : ""
        if (lastUsed.length <= 0 && files.length > 0) {
            lastUsed = files[0]
        }
        if (autoSelectLast && lastUsed.length > 0) {
            root.filePath = lastUsed
            root.statusMessage = "Ready to import the last used workbook."
            root.fetchSourceClients()
        }
    }

    function refreshRecentFiles(autoSelectLast) {
        if (!root.appRef || !root.appRef.getLegacyDocketsRecentFiles) return
        try {
            root.applyRecentFiles(root.appRef.getLegacyDocketsRecentFiles(), autoSelectLast)
        } catch(e) {
            // The Browse action remains available if recent-file settings cannot load.
        }
    }

    function selectImportFile(pathText, rememberSelection) {
        var selectedPath = String(pathText || "")
        if (selectedPath.length <= 0) return
        root.filePath = selectedPath
        root.statusMessage = "Ready to import selected workbook."
        root.fetchSourceClients()
        if (!rememberSelection || !root.appRef || !root.appRef.rememberLegacyDocketsImportFile) return
        try {
            var result = root.appRef.rememberLegacyDocketsImportFile(selectedPath)
            if (result && result.ok) {
                root.applyRecentFiles(result, true)
            } else if (result && result.message) {
                root.statusMessage = String(result.message)
            }
        } catch(e) {
            root.statusMessage = "Could not remember the selected workbook."
        }
    }

    function applyRowCounts(counts) {
        var normalized = ({})
        var progress = ({})
        var total = 0
        for (var i = 0; i < root.importSheetNames.length; i++) {
            var sheetName = root.importSheetNames[i]
            var count = root.coerceInt(counts ? counts[sheetName] : 0)
            normalized[sheetName] = count
            progress[sheetName] = ({ "current": 0, "total": count })
            total += count
        }
        if (counts && counts.total !== undefined) {
            total = root.coerceInt(counts.total)
        }
        root.rowCounts = normalized
        root.sheetProgress = progress
        root.totalRows = total
        root.overallRowsDone = 0
    }

    function sheetTotal(sheetName) {
        var item = root.sheetProgress ? root.sheetProgress[sheetName] : null
        if (item && item.total !== undefined) return root.coerceInt(item.total)
        return root.coerceInt(root.rowCounts ? root.rowCounts[sheetName] : 0)
    }

    function sheetCurrent(sheetName) {
        var item = root.sheetProgress ? root.sheetProgress[sheetName] : null
        if (item && item.current !== undefined) return root.coerceInt(item.current)
        return 0
    }

    function sheetFraction(sheetName) {
        var total = root.sheetTotal(sheetName)
        if (total <= 0) return root.importCompleted ? 1.0 : 0.0
        return Math.max(0.0, Math.min(1.0, root.sheetCurrent(sheetName) / total))
    }

    function refreshOverallProgress() {
        var done = 0
        for (var i = 0; i < root.importSheetNames.length; i++) {
            done += root.sheetCurrent(root.importSheetNames[i])
        }
        root.overallRowsDone = Math.max(0, done)
    }

    function overallFraction() {
        if (root.totalRows <= 0) return root.importCompleted ? 1.0 : 0.0
        return Math.max(0.0, Math.min(1.0, root.overallRowsDone / root.totalRows))
    }

    function analysisFraction() {
        if (root.analysisTotal <= 0) return root.analysisCompleted ? 1.0 : 0.0
        return Math.max(0.0, Math.min(1.0, root.analysisCurrent / root.analysisTotal))
    }

    function recordSheetPlan(sheetName, total) {
        if (root.importSheetNames.indexOf(sheetName) === -1) return
        var normalizedCounts = ({})
        var updatedProgress = ({})
        var plannedTotal = 0
        for (var i = 0; i < root.importSheetNames.length; i++) {
            var name = root.importSheetNames[i]
            var oldItem = root.sheetProgress ? root.sheetProgress[name] : null
            var count = name === sheetName
                        ? root.coerceInt(total)
                        : root.coerceInt(root.rowCounts ? root.rowCounts[name] : 0)
            normalizedCounts[name] = count
            updatedProgress[name] = ({
                "current": oldItem && oldItem.current !== undefined ? root.coerceInt(oldItem.current) : 0,
                "total": count
            })
            plannedTotal += count
        }
        root.rowCounts = normalizedCounts
        root.sheetProgress = updatedProgress
        root.totalRows = plannedTotal
    }

    function recordImportProgress(phase, current, total) {
        var phaseName = String(phase || "")
        if (phaseName.indexOf("Cancellation:") === 0) {
            root.cancelRequested = true
            root.currentPhase = phaseName.substring("Cancellation:".length).trim()
            root.statusMessage = "Cancelling import and verifying the pre-import workbook..."
            return
        }
        if (phaseName.indexOf("Analysis:") === 0) {
            root.analysisStarted = true
            root.analysisCurrent = root.coerceInt(current)
            root.analysisTotal = root.coerceInt(total)
            root.analysisMessage = phaseName.substring("Analysis:".length).trim()
            root.currentPhase = root.analysisMessage
            root.analysisCompleted = root.analysisTotal > 0 && root.analysisCurrent >= root.analysisTotal
            return
        }
        if (phaseName.indexOf("Plan:") === 0) {
            root.recordSheetPlan(phaseName.substring("Plan:".length).trim(), total)
            return
        }

        root.analysisStarted = true
        root.analysisCompleted = true
        root.currentPhase = phaseName
        if (root.importSheetNames.indexOf(phaseName) === -1) {
            return
        }

        var updated = ({})
        for (var i = 0; i < root.importSheetNames.length; i++) {
            var sheetName = root.importSheetNames[i]
            var oldItem = root.sheetProgress ? root.sheetProgress[sheetName] : null
            updated[sheetName] = ({
                "current": oldItem && oldItem.current !== undefined ? root.coerceInt(oldItem.current) : 0,
                "total": oldItem && oldItem.total !== undefined ? root.coerceInt(oldItem.total) : root.sheetTotal(sheetName)
            })
        }
        updated[phaseName] = ({
            "current": root.coerceInt(current),
            "total": root.coerceInt(total) > 0 ? root.coerceInt(total) : root.sheetTotal(phaseName)
        })
        root.sheetProgress = updated
        root.refreshOverallProgress()
    }

    function markProgressComplete() {
        var updated = ({})
        for (var i = 0; i < root.importSheetNames.length; i++) {
            var sheetName = root.importSheetNames[i]
            var total = root.sheetTotal(sheetName)
            updated[sheetName] = ({ "current": total, "total": total })
        }
        root.sheetProgress = updated
        root.overallRowsDone = root.totalRows
    }

    function resultSummary(result) {
        if (!result) return "Import failed: no result returned."
        if (result.cancelled) {
            return result.rollbackVerified
                    ? "Import cancelled.\nThe active workbook was restored to its exact pre-import state."
                    : "Import cancellation requires attention.\n" + (result.errors ? result.errors.join(", ") : "Rollback could not be verified.")
        }
        if (result.success) {
            var totalAdded = 0
            if (result.clientsAdded) totalAdded += root.coerceInt(result.clientsAdded)
            if (result.mattersAdded) totalAdded += root.coerceInt(result.mattersAdded)
            if (result.docketsAdded) totalAdded += root.coerceInt(result.docketsAdded)
            if (result.disbursementsAdded) totalAdded += root.coerceInt(result.disbursementsAdded)
            if (result.ledgerAdded) totalAdded += root.coerceInt(result.ledgerAdded)
            if (result.receivablesAdded) totalAdded += root.coerceInt(result.receivablesAdded)
            if (result.invoiceLogAdded) totalAdded += root.coerceInt(result.invoiceLogAdded)
            
            var totalUpdated = 0
            if (result.duplicatesOverwritten) totalUpdated += root.coerceInt(result.duplicatesOverwritten)

            var warnings = result.warnings ? result.warnings.length : 0
            var textParts = []
            if (totalAdded > 0 || totalUpdated === 0) textParts.push(totalAdded + " new records added")
            if (totalUpdated > 0) textParts.push(totalUpdated + " existing records updated")
            
            var text = "Successfully imported: " + textParts.join(", ") + "."
            return "Import completed.\n" + text + (warnings > 0 ? ("\n" + warnings + " warnings") : "")
        }
        return "Import failed: " + (result.errors ? result.errors.join(", ") : "Unknown error")
    }

    function duplicateText(key, fallbackText) {
        var payload = root.duplicatePromptPayload || ({})
        var value = payload[key]
        if (value === undefined || value === null || String(value).length === 0) {
            return fallbackText
        }
        return String(value)
    }

    function showDuplicatePrompt(payload) {
        root.duplicatePromptPayload = payload || ({})
        root.duplicateApplyAll = false
        duplicatePromptPopup.open()
    }

    function resolveDuplicatePrompt(action) {
        var payload = root.duplicatePromptPayload || ({})
        if (root.appRef && root.appRef.resolveLegacyDocketsDuplicate) {
            root.appRef.resolveLegacyDocketsDuplicate({
                "requestId": String(payload.requestId || ""),
                "action": action,
                "scope": root.duplicateApplyAll ? "all" : "one"
            })
        }
        duplicatePromptPopup.close()
    }

    function finishImport(result) {
        root.lastImportResult = result || ({})
        root.importInProgress = false
        root.importCompleted = true
        root.lastImportSucceeded = !!(result && result.success)
        root.lastImportCancelled = !!(result && result.cancelled)
        root.cancelRequested = false
        root.currentPhase = ""
        if (root.lastImportSucceeded) {
            root.markProgressComplete()
        } else {
            root.refreshOverallProgress()
        }
        root.statusMessage = root.resultSummary(result)
        duplicatePromptPopup.close()
        cancelImportPopup.close()
        if (!progressPopup.opened) {
            progressPopup.open()
        }
        Qt.callLater(function() {
            closeProgressButton.forceActiveFocus()
        })
    }

    function minimizeHostWindow() {
        var hostWindow = root.Window.window
        if (!hostWindow || !hostWindow.showMinimized) return
        hostWindow.showMinimized()
    }

    function requestCancelImport() {
        if (!root.importInProgress || root.cancelRequested) return
        cancelImportPopup.open()
    }

    function confirmCancelImport() {
        cancelImportPopup.close()
        if (!root.appRef || !root.appRef.cancelLegacyDocketsImport) {
            root.statusMessage = "Cancellation is unavailable because the backend bridge is not connected."
            return
        }
        try {
            if (root.appRef.cancelLegacyDocketsImport()) {
                root.cancelRequested = true
                root.statusMessage = "Cancelling import and verifying the pre-import workbook..."
                duplicatePromptPopup.close()
            } else {
                root.statusMessage = "The import is already finalizing and can no longer be cancelled."
            }
        } catch(e) {
            root.statusMessage = "Could not request import cancellation: " + String(e)
        }
    }
    function resetAnalysisReview() {
        root.sourceAnalysisInProgress = false
        root.sourceAnalysisComplete = false
        root.analysisResult = ({})
    }

    function applyAnalysisResult(result) {
        root.sourceAnalysisInProgress = false
        root.sourceAnalysisComplete = true
        root.analysisResult = result || ({})
        root.statusMessage = "Analysis complete. " + (result && result.rows ? result.rows.length + " rows analyzed." : "")
    }

    function fetchSourceClients() {
        if (!root.filePath || root.filePath.length <= 0) return
        if (root.appRef && root.appRef.listLegacySourceClients) {
            root.sourceClients = root.appRef.listLegacySourceClients(root.filePath) || []
        }
    }

    function startAnalysis() {
        if (!root.filePath || root.filePath.length <= 0) return
        if (!root.appRef || !root.appRef.analyzeLegacyDockets) {
            root.statusMessage = "Analysis not supported by backend."
            return
        }

        root.resetAnalysisReview()
        root.sourceAnalysisInProgress = true
        root.statusMessage = "Analyzing source workbook against current CSPM data..."

        try {
            var dataTypesJson = JSON.stringify(root.selectedDataTypes)
            var result = root.appRef.analyzeLegacyDockets(root.filePath, root.importMode, root.startDate, root.endDate, dataTypesJson, root.clientFilter)
            if (result && result.success) {
                root.applyAnalysisResult(result)
                root.refreshRecentFiles(false)
                reviewButton.clicked()
            } else {
                root.sourceAnalysisInProgress = false
                root.sourceAnalysisComplete = false
                root.analysisResult = result || ({})
                root.statusMessage = result && result.message ? String(result.message) : "Analysis failed."
            }
        } catch(e) {
            root.sourceAnalysisInProgress = false
            root.sourceAnalysisComplete = false
            root.statusMessage = "Analysis error: " + String(e)
        }
    }

    function startImport() {
        if (!root.filePath || root.filePath.length <= 0) return
        if (!root.appRef || !root.appRef.startLegacyDocketsImport) {
            root.statusMessage = "Backend bridge not wired up yet. Service logic exists in python."
            return
        }

        root.resetProgressState()
        root.importInProgress = true
        root.analysisStarted = true
        root.statusMessage = "Analyzing source and existing CSPM records..."
        progressPopup.resetPosition()
        progressPopup.open()

        try {
            var started = root.appRef.startLegacyDocketsImport(root.filePath, root.importMode, root.startDate, root.endDate)
            if (started === false) {
                root.importInProgress = false
                root.importCompleted = true
                root.lastImportSucceeded = false
                root.statusMessage = "Import failed to start."
            } else {
                root.refreshRecentFiles(false)
            }
        } catch(e) {
            root.importInProgress = false
            root.importCompleted = true
            root.lastImportSucceeded = false
            root.statusMessage = "Error: " + String(e)
        }
    }

    function startFilteredImport(allowedRows) {
        if (!root.filePath || root.filePath.length <= 0) return
        if (!root.appRef || !root.appRef.startLegacyDocketsFilteredImport) {
            root.statusMessage = "Backend bridge not wired up yet."
            return
        }

        var payload = {
            "filePath": root.filePath,
            "mode": root.importMode,
            "startDate": root.startDate,
            "endDate": root.endDate,
            "dataTypes": JSON.stringify(root.selectedDataTypes),
            "clientFilter": root.clientFilter,
            "allowedRows": allowedRows
        }

        root.resetProgressState()
        root.importInProgress = true
        root.analysisStarted = true
        root.statusMessage = "Starting filtered import..."
        progressPopup.resetPosition()
        progressPopup.open()

        try {
            var started = root.appRef.startLegacyDocketsFilteredImport(payload)
            if (started === false) {
                root.importInProgress = false
                root.importCompleted = true
                root.lastImportSucceeded = false
                root.statusMessage = "Import failed to start."
            } else {
                root.refreshRecentFiles(false)
            }
        } catch(e) {
            root.importInProgress = false
            root.importCompleted = true
            root.lastImportSucceeded = false
            root.statusMessage = "Error: " + String(e)
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true

        function onImportProgress(phase, current, total) {
            root.recordImportProgress(phase, current, total)
        }

        function onImportFinished(result) {
            root.finishImport(result)
        }

        function onImportDuplicateFound(payload) {
            if (!root.cancelRequested) {
                root.showDuplicatePrompt(payload)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: visualRules.isPro ? 16 : 0
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "\uE8B7"
                font.family: "Segoe MDL2 Assets"
                font.pixelSize: 18
                color: visualRules.isPro ? root.accentColor : root.accentColor
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "Legacy Dockets Import"
                    font.family: "Segoe UI"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: root.inkColor
                }

                Text {
                    text: "Select an import mode to ingest legacy Dockets.xlsm records. Fuzzy matching is automatically applied."
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    color: root.mutedInkColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: visualRules.isPro ? SemanticTheme.surfacePanel(root.t, root.appStyle) : "transparent"
            border.width: visualRules.isPro ? 1 : 0
            border.color: visualRules.isPro ? SemanticTheme.borderSubtle(root.t, root.appStyle) : "transparent"
            radius: visualRules.isPro ? visualRules.radiusPanel : 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: visualRules.isPro ? 24 : 12
                spacing: 24

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Text {
                text: "Source File:"
                color: root.inkColor
                Layout.preferredWidth: 90
            }

            ComboBox {
                id: fileInput
                model: root.recentFilePaths
                currentIndex: -1
                displayText: root.filePath.length > 0 ? root.filePath : "Select Dockets.xlsm..."
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                enabled: !root.importInProgress
                onActivated: function(index) {
                    root.selectImportFile(root.recentFilePaths[index], true)
                }

                contentItem: Text {
                    leftPadding: 8
                    rightPadding: 8
                    text: fileInput.displayText
                    color: root.filePath.length > 0 ? root.inputInkColor : root.inputHintInkColor
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideMiddle
                }

                delegate: ItemDelegate {
                    id: recentFileDelegate
                    required property var modelData
                    width: fileInput.popup.width

                    contentItem: Text {
                        text: String(recentFileDelegate.modelData || "")
                        color: SemanticTheme.readableInk(root.raisedColor)
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideMiddle
                    }

                    background: Rectangle {
                        color: recentFileDelegate.hovered
                               ? SemanticTheme.mix(root.raisedColor, root.accentColor, visualRules.isPro ? 0.08 : 0.18)
                               : root.raisedColor
                    }

                    ToolTip.visible: hovered
                    ToolTip.text: String(recentFileDelegate.modelData || "")
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: fileInput.activeFocus ? 2 : 1
                    border.color: fileInput.activeFocus ? root.accentColor : root.inputBorderColor
                }

                ToolTip.visible: hovered && root.filePath.length > 0
                ToolTip.text: root.filePath
            }

            Button {
                id: browseButton
                text: "Browse..."
                enabled: !root.importInProgress
                Layout.preferredHeight: 36
                onClicked: importFileDialog.open()

                contentItem: Text {
                    text: browseButton.text
                    color: browseButton.enabled ? root.inputInkColor : root.inputHintInkColor
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: 1
                    border.color: browseButton.hovered && browseButton.enabled
                                  ? root.accentColor
                                  : root.inputBorderColor
                }
            }
        }

        RowLayout {
            spacing: 12

            Text {
                text: "Import Mode:"
                color: root.inkColor
                Layout.preferredWidth: 90
            }

            ComboBox {
                id: modeCombo
                model: ["All Data", "New Data", "Date Range"]
                enabled: !root.importInProgress
                onCurrentTextChanged: {
                    if (currentText === "All Data") root.importMode = "all"
                    else if (currentText === "New Data") root.importMode = "new"
                    else root.importMode = "date_range"
                }

                contentItem: Text {
                    leftPadding: 8
                    rightPadding: 8
                    text: modeCombo.displayText
                    color: modeCombo.enabled ? root.inputInkColor : root.inputHintInkColor
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                delegate: ItemDelegate {
                    id: modeDelegate
                    required property var modelData
                    width: modeCombo.popup.width

                    contentItem: Text {
                        text: String(modeDelegate.modelData || "")
                        color: SemanticTheme.readableInk(root.raisedColor)
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    background: Rectangle {
                        color: modeDelegate.hovered
                               ? SemanticTheme.mix(root.raisedColor, root.accentColor, visualRules.isPro ? 0.08 : 0.18)
                               : root.raisedColor
                    }
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: modeCombo.activeFocus ? 2 : 1
                    border.color: modeCombo.activeFocus ? root.accentColor : root.inputBorderColor
                }
            }
        }

        RowLayout {
            spacing: 12
            visible: root.importMode === "date_range"
            Layout.fillWidth: true

            Text {
                text: "Start Date (YYYY-MM-DD):"
                color: root.inkColor
            }
            TextField {
                id: startInput
                placeholderText: "e.g. 2025-01-01"
                enabled: !root.importInProgress
                Layout.preferredHeight: 36
                Layout.fillWidth: true
                color: root.inputInkColor
                placeholderTextColor: root.inputHintInkColor
                selectByMouse: true
                onTextChanged: root.startDate = text

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: startInput.activeFocus ? 2 : 1
                    border.color: startInput.activeFocus ? root.accentColor : root.inputBorderColor
                }
            }

            Text {
                text: "End Date:"
                color: root.inkColor
            }
            TextField {
                id: endInput
                placeholderText: "e.g. 2025-12-31"
                enabled: !root.importInProgress
                Layout.preferredHeight: 36
                Layout.fillWidth: true
                color: root.inputInkColor
                placeholderTextColor: root.inputHintInkColor
                selectByMouse: true
                onTextChanged: root.endDate = text

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: endInput.activeFocus ? 2 : 1
                    border.color: endInput.activeFocus ? root.accentColor : root.inputBorderColor
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "Client Filter (Fuzzy):"
                color: root.inkColor
            }
            TextField {
                id: clientFilterInput
                placeholderText: "e.g. Kingdon Green (Optional)"
                enabled: !root.importInProgress
                Layout.preferredHeight: 36
                Layout.fillWidth: true
                color: root.inputInkColor
                placeholderTextColor: root.inputHintInkColor
                selectByMouse: true
                onTextChanged: root.clientFilter = text

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: clientFilterInput.activeFocus ? 2 : 1
                    border.color: clientFilterInput.activeFocus ? root.accentColor : root.inputBorderColor
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "Data Types to Import:"
                color: root.inkColor
            }
            
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: root.availableDataTypes
                    delegate: CheckBox {
                        id: typeCheck
                        required property string modelData
                        text: typeCheck.modelData
                        checked: root.selectedDataTypes.indexOf(typeCheck.modelData) !== -1
                        onToggled: {
                            var current = root.selectedDataTypes.slice()
                            var idx = current.indexOf(typeCheck.modelData)
                            if (checked && idx === -1) {
                                current.push(typeCheck.modelData)
                            } else if (!checked && idx !== -1) {
                                current.splice(idx, 1)
                            }
                            root.selectedDataTypes = current
                        }
                        contentItem: Text {
                            text: typeCheck.text
                            color: root.inkColor
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: typeCheck.indicator.width + typeCheck.spacing
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Button {
                id: analyzeButton
                text: root.sourceAnalysisInProgress ? "Analyzing..." : "Analyze Source"
                enabled: root.filePath.length > 0 && !root.importInProgress && !root.sourceAnalysisInProgress
                Layout.preferredWidth: 160
                Layout.preferredHeight: 40
                onClicked: root.startAnalysis()

                contentItem: Text {
                    text: analyzeButton.text
                    color: analyzeButton.enabled ? root.inputInkColor : root.inputHintInkColor
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: analyzeButton.enabled ? SemanticTheme.alpha(root.inkColor, 0.05) : root.inputColor
                    border.width: 1
                    border.color: analyzeButton.enabled ? root.inkColor : root.borderColor
                }
            }

            Button {
                id: reviewButton
                text: "Review Rows"
                visible: root.sourceAnalysisComplete
                enabled: !root.importInProgress
                Layout.preferredWidth: 140
                Layout.preferredHeight: 40
                onClicked: {
                    var component = Qt.createComponent("AnalysisReviewGridWindow.qml")
                    if (component.status === Component.Ready) {
                        var gridWindow = component.createObject(root, {
                            "appRef": root.appRef,
                            "visualRules": visualRules,
                            "analysisResult": root.analysisResult,
                            "importView": root
                        })
                        gridWindow.showMaximized()
                    } else {
                        console.error("Error loading AnalysisReviewGridWindow.qml: " + component.errorString())
                    }
                }

                contentItem: Text {
                    text: reviewButton.text
                    color: reviewButton.enabled ? root.inputInkColor : root.inputHintInkColor
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: 1
                    border.color: reviewButton.enabled ? root.accentColor : root.borderColor
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                id: importButton
                text: root.importInProgress ? "Importing..." : "Run Full Import"
                enabled: root.filePath.length > 0 && !root.importInProgress && !root.sourceAnalysisInProgress
                Layout.preferredWidth: 180
                Layout.preferredHeight: 40
                onClicked: root.startImport()

                contentItem: Text {
                    text: importButton.text
                    color: importButton.enabled ? SemanticTheme.readableInk(root.accentColor) : root.mutedInkColor
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: importButton.enabled ? root.accentColor : root.inputColor
                    border.width: importButton.enabled ? 0 : 1
                    border.color: root.borderColor
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: root.sourceAnalysisComplete && root.analysisResult
            spacing: 24

            RowLayout {
                Layout.fillWidth: true
                spacing: 32

                ColumnLayout {
                    spacing: 4
                    Text { text: "Total Rows Parsed"; font.pixelSize: 12; color: root.mutedInkColor }
                    Text { 
                        text: root.analysisResult && root.analysisResult.rows ? root.analysisResult.rows.length : "0"
                        font.pixelSize: 24; font.weight: Font.DemiBold; color: root.inkColor 
                    }
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "New Additions"; font.pixelSize: 12; color: root.mutedInkColor }
                    Text { 
                        text: root.analysisResult && root.analysisResult.summary ? String(root.analysisResult.summary.newRows) : "0"
                        font.pixelSize: 24; font.weight: Font.DemiBold; color: root.inkColor 
                    }
                }

                ColumnLayout {
                    spacing: 4
                    Text { text: "Skipped (Duplicates)"; font.pixelSize: 12; color: root.mutedInkColor }
                    Text { 
                        text: root.analysisResult && root.analysisResult.summary ? String(root.analysisResult.summary.alreadyImportedRows) : "0"
                        font.pixelSize: 24; font.weight: Font.DemiBold; color: root.inkColor 
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: root.borderColor
                visible: root.analysisResult && root.analysisResult.summary && root.analysisResult.summary.newRows > 0
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.analysisResult && root.analysisResult.summary && root.analysisResult.summary.newRows > 0

                Text {
                    text: "Breakdown of New Additions"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: root.inkColor
                }

                RowLayout {
                    spacing: 24
                    Repeater {
                        model: root.analysisResult && root.analysisResult.summary && root.analysisResult.summary.breakdown
                               ? Object.keys(root.analysisResult.summary.breakdown)
                               : []
                        delegate: RowLayout {
                            spacing: 6
                            visible: root.analysisResult.summary.breakdown[modelData] > 0
                            Text {
                                text: modelData + ":"
                                font.pixelSize: 12
                                color: root.mutedInkColor
                            }
                            Text {
                                text: String(root.analysisResult.summary.breakdown[modelData])
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                color: root.inkColor
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: root.statusMessage
                font.pixelSize: 14
                color: (root.statusMessage.indexOf("Error") !== -1 || root.statusMessage.indexOf("failed") !== -1)
                       ? root.errorColor
                       : root.inkColor
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                verticalAlignment: Text.AlignTop
            }

            Button {
                id: viewWarningsBtn
                text: "View Warnings"
                visible: !!(root.lastImportResult && root.lastImportResult.warnings && root.lastImportResult.warnings.length > 0)
                Layout.preferredHeight: 34
                onClicked: warningsPopup.open()

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: 1
                    border.color: root.borderColor
                }
                contentItem: Text {
                    text: viewWarningsBtn.text
                    color: root.inkColor
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                id: viewAddedRecordsBtn
                text: "View Added Records"
                visible: !!(root.lastImportResult && root.lastImportResult.addedRecords && root.lastImportResult.addedRecords.length > 0)
                Layout.preferredHeight: 34
                onClicked: addedRecordsPopup.open()

                background: Rectangle {
                    radius: visualRules.radiusControl
                    color: root.inputColor
                    border.width: 1
                    border.color: root.borderColor
                }
                contentItem: Text {
                    text: viewAddedRecordsBtn.text
                    color: root.inkColor
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Popup {
            id: addedRecordsPopup
            width: 600
            height: 400
            x: (root.width - width) / 2
            y: (root.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: root.surfaceColor
                radius: 8
                border.color: root.borderColor
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Records Added"
                    font.pixelSize: 18
                    font.weight: Font.Bold
                    color: root.inkColor
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    TextArea {
                        text: (root.lastImportResult && root.lastImportResult.addedRecords) ? root.lastImportResult.addedRecords.join("\n") : ""
                        readOnly: true
                        font.pixelSize: 12
                        color: root.inkColor
                        background: null
                        wrapMode: Text.NoWrap
                    }
                }

                Button {
                    text: "Close"
                    Layout.alignment: Qt.AlignRight
                    onClicked: addedRecordsPopup.close()
                }
            }
        }

        Popup {
            id: warningsPopup
            width: 600
            height: 400
            x: (root.width - width) / 2
            y: (root.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: root.surfaceColor
                radius: 8
                border.color: root.borderColor
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Import Warnings"
                    font.pixelSize: 18
                    font.weight: Font.Bold
                    color: root.inkColor
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    
                    TextArea {
                        text: (root.lastImportResult && root.lastImportResult.warnings) ? root.lastImportResult.warnings.join("\n") : ""
                        readOnly: true
                        font.pixelSize: 13
                        color: root.inkColor
                        wrapMode: Text.Wrap
                        background: null
                    }
                }

                Button {
                    text: "Close"
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredHeight: 34
                    onClicked: warningsPopup.close()
                }
            }
        }

        Item { Layout.fillHeight: true; Layout.fillWidth: true }
            }
        }
    }

    Popup {
        id: progressPopup
        parent: Overlay.overlay
        modal: true
        dim: true
        padding: 0
        property real dragOffsetX: 0
        property real dragOffsetY: 0
        readonly property real overlayWidth: parent ? parent.width : root.width
        readonly property real overlayHeight: parent ? parent.height : root.height
        readonly property real centeredX: Math.round((overlayWidth - width) / 2)
        readonly property real raisedCenterY: Math.max(16, Math.round((overlayHeight - height) / 2) - 48)

        function resetPosition() {
            dragOffsetX = 0
            dragOffsetY = 0
        }

        function moveBy(deltaX, deltaY) {
            var margin = 16
            var maximumX = Math.max(margin, overlayWidth - width - margin)
            var maximumY = Math.max(margin, overlayHeight - height - margin)
            var nextX = Math.max(margin, Math.min(x + deltaX, maximumX))
            var nextY = Math.max(margin, Math.min(y + deltaY, maximumY))
            dragOffsetX = nextX - centeredX
            dragOffsetY = nextY - raisedCenterY
        }

        width: Math.max(320, Math.min(680, (parent ? parent.width : root.width) - 64))
        x: Math.max(16, Math.min(centeredX + dragOffsetX, Math.max(16, overlayWidth - width - 16)))
        y: Math.max(16, Math.min(raisedCenterY + dragOffsetY, Math.max(16, overlayHeight - height - 16)))
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            radius: visualRules.radiusPopup
            color: root.surfaceColor
            border.width: 1
            border.color: root.borderColor
        }

        contentItem: Item {
            implicitWidth: 620
            implicitHeight: progressColumn.implicitHeight + 44

            ColumnLayout {
                id: progressColumn
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                Item {
                    id: progressHeader
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(progressHeaderRow.implicitHeight, 42)

                    RowLayout {
                        id: progressHeaderRow
                        anchors.fill: parent
                        spacing: 12
                        z: 1

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: root.importCompleted
                                      ? (root.lastImportCancelled
                                         ? "Import Cancelled"
                                         : (root.lastImportSucceeded ? "Import Complete" : "Import Failed"))
                                      : (root.analysisCompleted
                                         ? "Importing Legacy Dockets"
                                         : "Analyzing Legacy Dockets")
                                color: root.inkColor
                                font.pixelSize: 20
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Text {
                                text: root.importCompleted
                                      ? (root.lastImportCancelled
                                         ? "The pre-import workbook was preserved."
                                         : (root.lastImportSucceeded
                                            ? "The import finished successfully."
                                            : "The import finished with errors."))
                                      : (!root.analysisCompleted
                                         ? root.analysisMessage
                                         : root.totalRows > 0
                                         ? (root.overallRowsDone + " of " + root.totalRows + " rows processed")
                                         : "Preparing validated records...")
                                color: root.mutedInkColor
                                font.pixelSize: 13
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        Button {
                            id: progressMinimizeButton
                            text: "\uE921"
                            padding: 0
                            hoverEnabled: true
                            Layout.preferredWidth: 34
                            Layout.preferredHeight: 34
                            ToolTip.visible: hovered
                            ToolTip.delay: 350
                            ToolTip.text: "Minimize CSPM"
                            onClicked: root.minimizeHostWindow()

                            contentItem: Text {
                                text: progressMinimizeButton.text
                                font.family: "Segoe MDL2 Assets"
                                font.pixelSize: 13
                                color: progressMinimizeButton.hovered ? root.inkColor : root.mutedInkColor
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }

                            background: Rectangle {
                                radius: visualRules.radiusControl
                                color: progressMinimizeButton.hovered ? root.inputColor : "transparent"
                                border.width: progressMinimizeButton.hovered ? 1 : 0
                                border.color: root.borderColor
                            }
                        }
                    }

                    MouseArea {
                        id: progressDragArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        property point lastOverlayPoint: Qt.point(0, 0)
                        z: 0

                        onPressed: function(mouse) {
                            lastOverlayPoint = mapToItem(progressPopup.parent, mouse.x, mouse.y)
                        }

                        onPositionChanged: function(mouse) {
                            if (!pressed) return
                            var overlayPoint = mapToItem(progressPopup.parent, mouse.x, mouse.y)
                            progressPopup.moveBy(
                                overlayPoint.x - lastOverlayPoint.x,
                                overlayPoint.y - lastOverlayPoint.y
                            )
                            lastOverlayPoint = overlayPoint
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                text: "ANALYZE"
                                color: root.analysisCompleted
                                       ? root.successColor
                                       : (root.importCompleted
                                          ? (root.lastImportCancelled ? root.warningColor : root.errorColor)
                                          : root.accentColor)
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }

                            Item {
                                Layout.fillWidth: true
                            }

                            Text {
                                text: root.analysisCompleted ? "Complete" : (root.importCompleted ? "Stopped" : "Active")
                                color: root.analysisCompleted
                                       ? root.successColor
                                       : (root.importCompleted
                                          ? (root.lastImportCancelled ? root.warningColor : root.errorColor)
                                          : root.mutedInkColor)
                                font.pixelSize: 11
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: visualRules.isPro ? 3 : 5
                            radius: visualRules.isPro ? 1 : visualRules.radiusControl
                            color: root.inputColor
                            clip: true

                            Rectangle {
                                height: parent.height
                                width: parent.width * root.analysisFraction()
                                radius: parent.radius
                                color: root.analysisCompleted
                                       ? root.successColor
                                       : (root.importCompleted
                                          ? (root.lastImportCancelled ? root.warningColor : root.errorColor)
                                          : root.accentColor)

                                Behavior on width {
                                    NumberAnimation {
                                        duration: visualRules.motionNormal
                                        easing.type: Easing.OutCubic
                                    }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                text: "IMPORT"
                                color: root.importCompleted && root.lastImportCancelled
                                       ? root.warningColor
                                       : (root.analysisCompleted ? root.accentColor : root.mutedInkColor)
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }

                            Item {
                                Layout.fillWidth: true
                            }

                            Text {
                                text: root.importCompleted
                                      ? (root.lastImportCancelled
                                         ? "Cancelled"
                                         : (root.lastImportSucceeded ? "Complete" : "Stopped"))
                                      : (root.cancelRequested
                                         ? "Cancelling"
                                         : (root.analysisCompleted ? "Active" : "Queued"))
                                color: root.importCompleted
                                       ? (root.lastImportCancelled
                                          ? root.warningColor
                                          : (root.lastImportSucceeded ? root.successColor : root.errorColor))
                                       : root.mutedInkColor
                                font.pixelSize: 11
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: visualRules.isPro ? 3 : 5
                            radius: visualRules.isPro ? 1 : visualRules.radiusControl
                            color: root.inputColor
                            clip: true

                            Rectangle {
                                height: parent.height
                                width: parent.width * root.overallFraction()
                                radius: parent.radius
                                color: root.importCompleted
                                       ? (root.lastImportCancelled
                                          ? root.warningColor
                                          : (root.lastImportSucceeded ? root.successColor : root.errorColor))
                                       : root.accentColor

                                Behavior on width {
                                    NumberAnimation {
                                        duration: visualRules.motionNormal
                                        easing.type: Easing.OutCubic
                                    }
                                }
                            }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 7
                    visible: !root.analysisCompleted && !root.importCompleted

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Analyzing source against current CSPM data"
                            color: root.inkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Text {
                            text: root.analysisTotal > 0
                                  ? (root.analysisCurrent + " / " + root.analysisTotal)
                                  : ""
                            color: root.mutedInkColor
                            font.pixelSize: 12
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: visualRules.isPro ? 8 : 12
                        radius: visualRules.isPro ? 2 : visualRules.radiusControl
                        color: root.inputColor
                        border.width: 1
                        border.color: root.borderColor
                        clip: true

                        Rectangle {
                            id: analysisProgressFill
                            height: parent.height
                            width: parent.width * root.analysisFraction()
                            radius: parent.radius
                            color: root.accentColor

                            Behavior on width {
                                NumberAnimation {
                                    duration: visualRules.motionNormal
                                    easing.type: Easing.OutCubic
                                }
                            }

                            SequentialAnimation on opacity {
                                running: root.importInProgress && !root.analysisCompleted && visualRules.glowEnabled
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.68; duration: visualRules.motionSlow }
                                NumberAnimation { to: 1.0; duration: visualRules.motionSlow }
                            }
                        }
                    }

                    Text {
                        text: root.analysisMessage
                        color: root.mutedInkColor
                        font.pixelSize: 12
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    visible: root.analysisCompleted || root.importCompleted

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Validated record import"
                            color: root.inkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.overallRowsDone + " / " + root.totalRows
                            color: root.mutedInkColor
                            font.pixelSize: 12
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: visualRules.isPro ? 8 : 12
                        radius: visualRules.isPro ? 2 : visualRules.radiusControl
                        color: root.inputColor
                        border.width: 1
                        border.color: root.borderColor
                        clip: true

                        Rectangle {
                            height: parent.height
                            width: parent.width * root.overallFraction()
                            radius: parent.radius
                            color: root.importCompleted
                                   ? (root.lastImportSucceeded ? root.successColor : root.errorColor)
                                   : root.accentColor

                            Behavior on width {
                                NumberAnimation {
                                    duration: visualRules.motionNormal
                                    easing.type: Easing.OutCubic
                                }
                            }
                        }
                    }

                    Text {
                        text: root.currentPhase.length > 0 ? ("Current: " + root.currentPhase) : "Current: preparing validated records"
                        visible: !root.importCompleted
                        color: root.mutedInkColor
                        font.pixelSize: 12
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: root.importSheetNames

                            delegate: ColumnLayout {
                                id: sheetDelegate
                                required property string modelData

                                Layout.fillWidth: true
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: sheetDelegate.modelData
                                        color: root.inkColor
                                        font.pixelSize: 12
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        text: root.sheetCurrent(sheetDelegate.modelData) + " / " + root.sheetTotal(sheetDelegate.modelData)
                                        color: root.mutedInkColor
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignRight
                                        Layout.preferredWidth: 82
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 7
                                    radius: visualRules.radiusControl
                                    color: root.inputColor
                                    border.width: 1
                                    border.color: root.borderColor
                                    clip: true

                                    Rectangle {
                                        height: parent.height
                                        width: parent.width * root.sheetFraction(sheetDelegate.modelData)
                                        radius: parent.radius
                                        color: root.sheetTotal(sheetDelegate.modelData) > 0 ? root.accentColor : root.borderColor

                                        Behavior on width {
                                            NumberAnimation {
                                                duration: visualRules.motionFast
                                                easing.type: Easing.OutCubic
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Text {
                    visible: root.importCompleted
                    text: root.statusMessage
                    color: root.lastImportCancelled
                           ? (root.lastImportResult.rollbackVerified ? root.warningColor : root.errorColor)
                           : (root.lastImportSucceeded ? root.successColor : root.errorColor)
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.maximumHeight: 92
                    clip: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        id: cancelProgressButton
                        text: root.cancelRequested ? "Cancelling..." : "Cancel Import"
                        visible: root.importInProgress
                        enabled: root.importInProgress && !root.cancelRequested
                        Layout.preferredWidth: 130
                        Layout.preferredHeight: 34
                        onClicked: root.requestCancelImport()

                        contentItem: Text {
                            text: cancelProgressButton.text
                            color: cancelProgressButton.enabled ? root.errorColor : root.mutedInkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: cancelProgressButton.hovered && cancelProgressButton.enabled
                                   ? SemanticTheme.alpha(root.errorColor, visualRules.isPro ? 0.08 : 0.18)
                                   : root.inputColor
                            border.width: 1
                            border.color: cancelProgressButton.enabled ? root.errorColor : root.borderColor
                        }
                    }

                    Button {
                        id: closeProgressButton
                        text: root.importCompleted
                              ? "Done"
                              : (root.cancelRequested
                                 ? "Cancelling..."
                                 : (root.analysisCompleted ? "Importing..." : "Analyzing..."))
                        enabled: root.importCompleted
                        Layout.preferredWidth: 110
                        Layout.preferredHeight: 34
                        onClicked: progressPopup.close()

                        contentItem: Text {
                            text: closeProgressButton.text
                            color: closeProgressButton.enabled ? SemanticTheme.readableInk(root.accentColor) : root.mutedInkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: closeProgressButton.enabled ? root.accentColor : root.inputColor
                            border.width: closeProgressButton.enabled ? 0 : 1
                            border.color: root.borderColor
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: duplicatePromptPopup
        parent: Overlay.overlay
        modal: true
        dim: true
        padding: 0
        width: Math.max(320, Math.min(620, (parent ? parent.width : root.width) - 64))
        x: Math.round(((parent ? parent.width : root.width) - width) / 2)
        y: Math.max(16, Math.round(((parent ? parent.height : root.height) - height) / 2))
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            radius: visualRules.radiusPopup
            color: root.surfaceColor
            border.width: 1
            border.color: root.warningColor
        }

        contentItem: Item {
            implicitWidth: 580
            implicitHeight: duplicateColumn.implicitHeight + 44

            ColumnLayout {
                id: duplicateColumn
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: visualRules.radiusControl
                        color: Qt.rgba(root.warningColor.r, root.warningColor.g, root.warningColor.b, 0.16)
                        border.width: 1
                        border.color: root.warningColor

                        Text {
                            anchors.centerIn: parent
                            text: "!"
                            color: root.warningColor
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "Duplicate Found"
                            color: root.inkColor
                            font.pixelSize: 20
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Text {
                            text: root.duplicateText("sheet", "Import") + " row " + root.duplicateText("rowNumber", "?")
                            color: root.mutedInkColor
                            font.pixelSize: 12
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }

                    Button {
                        id: duplicateMinimizeButton
                        text: "\uE921"
                        padding: 0
                        hoverEnabled: true
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Minimize CSPM"
                        onClicked: root.minimizeHostWindow()

                        contentItem: Text {
                            text: duplicateMinimizeButton.text
                            font.family: "Segoe MDL2 Assets"
                            font.pixelSize: 13
                            color: duplicateMinimizeButton.hovered ? root.inkColor : root.mutedInkColor
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: duplicateMinimizeButton.hovered ? root.inputColor : "transparent"
                            border.width: duplicateMinimizeButton.hovered ? 1 : 0
                            border.color: root.borderColor
                        }
                    }
                }

                Text {
                    text: root.duplicateText("recordLabel", "Record")
                    color: root.inkColor
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: duplicateDetails.implicitHeight + 18
                    radius: visualRules.radiusControl
                    color: root.raisedColor
                    border.width: 1
                    border.color: root.borderColor

                    ColumnLayout {
                        id: duplicateDetails
                        anchors.fill: parent
                        anchors.margins: 9
                        spacing: 8

                        Text {
                            text: "Existing: " + root.duplicateText("existingSummary", "matching record")
                            color: root.mutedInkColor
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "Incoming: " + root.duplicateText("incomingSummary", "incoming row")
                            color: root.inkColor
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                CheckBox {
                    id: duplicateApplyAllCheck
                    checked: root.duplicateApplyAll
                    text: "Use this choice for all duplicates in this import"
                    Layout.fillWidth: true
                    onToggled: root.duplicateApplyAll = checked

                    indicator: Rectangle {
                        implicitWidth: 18
                        implicitHeight: 18
                        x: duplicateApplyAllCheck.leftPadding
                        y: parent.height / 2 - height / 2
                        radius: 3
                        color: duplicateApplyAllCheck.checked ? root.accentColor : root.inputColor
                        border.width: 1
                        border.color: duplicateApplyAllCheck.checked ? root.accentColor : root.borderColor

                        Text {
                            anchors.centerIn: parent
                            text: duplicateApplyAllCheck.checked ? "\u2713" : ""
                            color: SemanticTheme.readableInk(root.accentColor)
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    contentItem: Text {
                        text: duplicateApplyAllCheck.text
                        color: root.inkColor
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: duplicateApplyAllCheck.indicator.width + duplicateApplyAllCheck.spacing
                    }
                }

                GridLayout {
                    columns: duplicatePromptPopup.width < 540 ? 1 : 3
                    columnSpacing: 10
                    rowSpacing: 8
                    Layout.fillWidth: true

                    Button {
                        id: skipDuplicateButton
                        text: "Skip"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        onClicked: root.resolveDuplicatePrompt("skip")

                        contentItem: Text {
                            text: skipDuplicateButton.text
                            color: root.inkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: root.inputColor
                            border.width: 1
                            border.color: root.borderColor
                        }
                    }

                    Button {
                        id: addDuplicateButton
                        text: "Add Duplicate"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        onClicked: root.resolveDuplicatePrompt("add")

                        contentItem: Text {
                            text: addDuplicateButton.text
                            color: SemanticTheme.readableInk(root.accentColor)
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: root.accentColor
                            border.width: 0
                            border.color: root.accentColor
                        }
                    }

                    Button {
                        id: overwriteDuplicateButton
                        text: "Overwrite"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        onClicked: root.resolveDuplicatePrompt("overwrite")

                        contentItem: Text {
                            text: overwriteDuplicateButton.text
                            color: SemanticTheme.readableInk(root.warningColor)
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: root.warningColor
                            border.width: 0
                            border.color: root.warningColor
                            }
                        }
                    }

                }

                Button {
                    id: cancelFromDuplicateButton
                    text: "Cancel Entire Import"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    onClicked: root.requestCancelImport()

                    contentItem: Text {
                        text: cancelFromDuplicateButton.text
                        color: root.errorColor
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    background: Rectangle {
                        radius: visualRules.radiusControl
                        color: cancelFromDuplicateButton.hovered
                               ? SemanticTheme.alpha(root.errorColor, visualRules.isPro ? 0.08 : 0.18)
                               : root.inputColor
                        border.width: 1
                        border.color: root.errorColor
                    }
                }
        }
    }

    Popup {
        id: cancelImportPopup
        parent: Overlay.overlay
        modal: true
        dim: true
        padding: 0
        width: Math.max(320, Math.min(540, (parent ? parent.width : root.width) - 64))
        x: Math.round(((parent ? parent.width : root.width) - width) / 2)
        y: Math.max(16, Math.round(((parent ? parent.height : root.height) - height) / 2) - 24)
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            radius: visualRules.radiusPopup
            color: root.surfaceColor
            border.width: 1
            border.color: root.errorColor
        }

        contentItem: Item {
            implicitWidth: 500
            implicitHeight: cancelImportColumn.implicitHeight + 44

            ColumnLayout {
                id: cancelImportColumn
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                Text {
                    text: "Cancel Legacy Dockets Import?"
                    color: root.inkColor
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "All staged import work will be discarded. CSPM will verify that the active workbook exactly matches its pre-import snapshot before reporting cancellation complete."
                    color: root.mutedInkColor
                    font.pixelSize: 13
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: cancellationGuarantee.implicitHeight + 20
                    radius: visualRules.radiusControl
                    color: root.raisedColor
                    border.width: 1
                    border.color: root.borderColor

                    Text {
                        id: cancellationGuarantee
                        anchors.fill: parent
                        anchors.margins: 10
                        text: "The active CSPM workbook will contain no changes from this import."
                        color: root.inkColor
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        id: keepImportingButton
                        text: "Keep Importing"
                        Layout.preferredWidth: 130
                        Layout.preferredHeight: 36
                        onClicked: cancelImportPopup.close()

                        contentItem: Text {
                            text: keepImportingButton.text
                            color: root.inkColor
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: root.inputColor
                            border.width: 1
                            border.color: root.borderColor
                        }
                    }

                    Button {
                        id: confirmCancelImportButton
                        text: "Cancel Import"
                        Layout.preferredWidth: 130
                        Layout.preferredHeight: 36
                        onClicked: root.confirmCancelImport()

                        contentItem: Text {
                            text: confirmCancelImportButton.text
                            color: SemanticTheme.readableInk(root.errorColor)
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            radius: visualRules.radiusControl
                            color: root.errorColor
                            border.width: 0
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: importFileDialog
        title: "Select Legacy Dockets File"
        nameFilters: ["Excel files (*.xlsm *.xlsx)", "All files (*)"]
        onAccepted: {
            var p = selectedFile ? selectedFile.toString() : ""
            root.selectImportFile(p, true)
        }
    }

    Component.onCompleted: root.refreshRecentFiles(true)
}
