




















































































































































        for (var i = 0; i < root.analysisRows.length; i++) {
            var item = Object.assign({}, root.analysisRows[i])
            if (item.selectable) {
                item.selected = checked
            }
            updated.push(item)
        }
        root.analysisRows = updated
    }

    function applyAnalysisResult(result) {
        var normalizedRows = []
        var incomingRows = (result && result.rows && result.rows.length !== undefined) ? result.rows : []
        for (var i = 0; i < incomingRows.length; i++) {
            var item = Object.assign({}, incomingRows[i])
            item.selected = !!item.defaultSelected
            normalizedRows.push(item)
        }
        root.analysisRows = normalizedRows
        root.analysisSummary = (result && result.summary) ? result.summary : ({})
        root.analysisResult = result || ({})
        root.sourceAnalysisComplete = true
        root.sourceAnalysisInProgress = false
        var newRows = root.analysisCount("newRows")
        var alreadyRows = root.analysisCount("alreadyImportedRows")
        var issueRows = root.analysisCount("conflictRows") + root.analysisCount("skippedRows")
        root.statusMessage = "Analysis complete: " + newRows + " new/different rows, "
                           + alreadyRows + " already in CSPM"
                           + (issueRows > 0 ? (", " + issueRows + " needing attention.") : ".")
    }

    function rese




























        var lastUsed = result ? String(result.lastUsedPath || "") : ""
        if (lastUsed.length <= 0 && files.length > 0) {
            lastUsed = files[0]
        }
        if (autoSelectLast && lastUsed.length > 0) {
            root.filePath = lastUsed
            root.statusMessage = "Ready to import the last used workbook."
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
        root.resetAnalysisReview()
        root.statusMessage = "Ready to import selected workbook."
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

























































































































































































































































        }

        root.resetAnalysisReview()
        root.sourceAnalysisInProgress = true
        root.statusMessage = "Analyzing source workbook against current CSPM data..."

        try {
            var result = root.appRef.analyzeLegacyDockets(root.filePath, root.importMode, root.startDate, root.endDate)
            if (result && result.success) {
                root.applyAnalysisResult(result)
                root.refreshRecentFiles(false)
            } else {
                root.sourceAnalysisInProgress = false
                root.sourceAnalysisComplete = false
                root.analysisResult = result || ({})
                root.statusMessage = result && result.message
                                     ? String(result.message)
                                     : "Analysis failed."
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
        root.analysisSt
 









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
