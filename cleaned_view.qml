
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
        if (!root.appRef || !root.appRef.importLegacyDockets) {
            root.statusMessage = "Backend bridge not wired up yet. Service logic exists in python."
            return
        }

        root.resetProgressState()
        root.importInProgress = true
        root.analysisStarted = true
 
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
