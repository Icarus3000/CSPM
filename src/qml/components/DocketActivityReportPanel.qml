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
    property var metrics
    property var appRef
    property var windowRef
    property var docketAppRef: (root.appRef && root.appRef.docketing) ? root.appRef.docketing : null
    property var sfxBus
    property int fieldHeightPx: 36
    property bool autoLoadOnVisible: true
    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : (((typeof app !== "undefined") && app !== null && app.appStyle) ? String(app.appStyle) : "Professional")
    readonly property bool isProMode: appStyle === "Professional"
    property real sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : 8

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    // State & Errors
    property bool busy: false
    property string debugBannerText: "Ready to run report."
    property bool hasBackendError: false
    property bool hasDataError: false
    property bool _isOnCooldown: false
    
    // Filters
    property string fromDateText: Qt.formatDate(new Date(1999, 0, 1), "yyyy-MM-dd")
    property string toDateText: Qt.formatDate(new Date(2099, 11, 31), "yyyy-MM-dd")
    property string statusMode: "all"
    property string currentPreset: "all" 
    property string queryText: ""
    property string clientFilterText: "All Clients"
    property string matterFilterText: "All Matters"
    property string matterIdFilterText: ""
    property string sortKey: "date"
    property bool sortAscending: false
    
    // Theme Colors
    property color _surfaceColor: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : ((root.t && root.t.panel2) ? root.t.panel2 : "#1A1A1A")
    property color _surfaceColor2: root.isProMode ? SemanticTheme.surfacePanel(root.t, root.appStyle) : ((root.t && root.t.panel) ? root.t.panel : "#111111")
    property color _textPrimary: root.isProMode ? SemanticTheme.inkPrimary(root.t, root.appStyle) : ((root.t && root.t.text) ? root.t.text : "#FFFFFF")
    property color _accent: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : ((root.t && root.t.accent) ? root.t.accent : "#2979FF")
    property color _borderSubtle: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color _tableHeaderFill: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : Qt.rgba(0, 0, 0, 0.35)
    property color _tableAggregateFill: root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : Qt.rgba(0, 0, 0, 0.5)
    property color _tableAltFill: root.isProMode ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : Qt.rgba(1, 1, 1, 0.04)
    property color _tableRule: root.isProMode ? root._borderSubtle : Qt.rgba(1, 1, 1, 0.05)
    property int compactToolbarHeight: 38
    property int compactToolbarGap: 6
    property int compactButtonWidth: 68
    property int compactOpenReportButtonWidth: 96
    property int compactRunButtonWidth: 92
    property int compactDateWidth: 112
    property int compactStatusWidth: 144
    property int compactRangeWidth: 96
    property int compactWideMinWidth: 140
    property int compactWideMaxWidth: 260
    property var compactTextFieldRatios: ({
        "textSizePct": 0.0132,
        "padSidePct": 0.0065,
        "padTopPct": 0.016,
        "padBottomPct": 0.003,
        "radiusPct": 0.0075,
        "focusBorderPct": 0.0017,
        "idleBorderPct": 0.0009,
        "labelFontPct": 0.0105,
        "labelLeftMarginPct": 0.0065,
        "labelTopMarginPct": 0.0020
    })
    property var compactComboRatios: ({
        "textSizePct": 0.0132,
        "padLeftPct": 0.0065,
        "padRightPct": 0.020,
        "padTopPct": 0.016,
        "padBottomPct": 0.003,
        "radiusPct": 0.0075,
        "focusBorderPct": 0.0017,
        "idleBorderPct": 0.0009,
        "indicatorRightMarginPct": 0.007,
        "indicatorWidthPct": 0.010,
        "indicatorHeightPct": 0.008,
        "popupYOffsetPct": 0.0022,
        "popupMaxHeightPct": 0.260,
        "popupRadiusPct": 0.0087,
        "delegateHeightPct": 0.034,
        "delegateTextPct": 0.014,
        "labelTextPct": 0.0105,
        "labelLeftPct": 0.0065,
        "labelTopPct": 0.0020
    })
    property var compactButtonRatios: ({
        "contentSpacingPct": 0.006,
        "iconSizePct": 0.015,
        "textSizePct": 0.013,
        "secondaryBorderPct": 0.0016,
        "shadowRadiusPct": 0.006,
        "shadowSamplesPct": 0.014,
        "shadowYOffsetPct": 0.0018
    })
    property var presetLabelOptions: ["All", "Today", "WTD", "MTD", "L-Week", "L-Month", "YTD"]
    property int tableLeftPadding: 16
    property int tableRightPadding: 18
    property int tableDateWidth: 96
    property int tableEntriesWidth: 96
    property int tableHoursWidth: 96
    property int tableGrossWidth: 108
    property int tableColumnGap: 16
    property int tableRowTopPadding: 10
    property int detailRowMinHeight: 64
    property int groupHeaderHeight: 22
    property int minVisibleDetailRows: 3
    property int summaryRowHeight: 34
    property int summaryMaxVisibleRows: 5
    property int effectiveSummaryMaxVisibleRows: root.height < 760 ? 4 : root.summaryMaxVisibleRows
    property int descriptionMaxLines: 2
    property int tableHeaderHeight: 48
    property int summaryHeaderHeight: 32
    property int aggregateRowHeight: 44
    property int tableHeaderFontPx: 12
    property int tableBodyFontPx: 13
    property int tableDetailFontPx: 12
    property int tableSummaryFontPx: 13
    property int detailPreferredHeight: root.detailRowMinHeight * root.minVisibleDetailRows
    property int reportTableMinimumHeight: root.tableHeaderHeight + root.summaryHeaderHeight + root.summaryRowHeight + root.aggregateRowHeight
    property int reportTablePreferredHeight: root.reportTableMinimumHeight + root.detailPreferredHeight
    property int panelBottomInsetPx: 0
    property string _lastExportPath: ""
    property color _accentInk: _readableInk(_accent)
    
    property var masterClientList: ["All Clients"]
    property var masterMatterList: ["All Matters"]
    property var clientFilterOptions: ["All Clients"]
    property var matterFilterOptions: ["All Matters"]
    
    property var reportRows: []
    property var displayRows: []
    property var displaySummaryRows: []
    property var reportTotals: ({ "totalHours": 0.0, "totalGrossToClient": 0.0 })
    property bool _loadedOnce: false
    property double _lastRunEpochMs: 0
    property double _pendingRunEpochMs: 0
    property string _lastRunSignature: ""
    property string _pendingRunSignature: ""
    property string _pendingRequestToken: ""
    property bool _pendingVisibleAutoload: false
    property bool _openReportAfterLoad: false

    function ratioPx(ratio, minPx) {
        var baseWidth = (metrics && typeof metrics.contentW === "number")
            ? Math.max(1, Number(metrics.contentW))
            : Math.max(1, root.width > 0 ? root.width : ((parent && parent.width > 0) ? parent.width : 1280))
        var baseHeight = (metrics && typeof metrics.contentH === "number")
            ? Math.max(1, Number(metrics.contentH))
            : Math.max(1, root.height > 0 ? root.height : ((parent && parent.height > 0) ? parent.height : 720))
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(Math.min(baseWidth, baseHeight) * ratio))
    }
    function _textColor(alpha) { return Qt.rgba(_textPrimary.r, _textPrimary.g, _textPrimary.b, alpha) }
    function _luma(colorValue) {
        if (!colorValue || typeof colorValue.r !== "number") return 0.0
        return (colorValue.r * 0.299) + (colorValue.g * 0.587) + (colorValue.b * 0.114)
    }
    function _readableInk(fillColor) {
        return _luma(fillColor) >= 0.60
            ? Qt.rgba(0.07, 0.09, 0.13, 0.98)
            : Qt.rgba(0.98, 0.99, 1.00, 0.98)
    }
    function _statusTone(kind) {
        return SemanticTheme.tone(root.t, kind)
    }
    function _statusSurface(kind) {
        return SemanticTheme.surface(root.t, "toast", kind)
    }
    function _statusBorder(kind) {
        return SemanticTheme.border(root.t, "toast", kind)
    }
    function _statusInk(kind) {
        return SemanticTheme.ink(root.t, "toast", kind)
    }
    function _mixWithWhite(colorValue, amount) {
        var ratio = Math.max(0, Math.min(1, Number(amount)))
        return Qt.rgba(
            colorValue.r + (1.0 - colorValue.r) * ratio,
            colorValue.g + (1.0 - colorValue.g) * ratio,
            colorValue.b + (1.0 - colorValue.b) * ratio,
            colorValue.a
        )
    }
    function _safeText(v) { return String(v === undefined || v === null ? "" : v) }
    function _startupAllowsAutoLoad(reason) {
        if (root.windowRef && root.windowRef.startupAllowsHeavyWork) {
            return root.windowRef.startupAllowsHeavyWork("DocketActivityReportPanel." + String(reason || "unspecified"))
        }
        return true
    }
    function _tryAutoLoad(reason) {
        if (!root.visible || !autoLoadOnVisible || _loadedOnce) return false
        if (!_startupAllowsAutoLoad("autoload:" + String(reason || "unspecified"))) {
            root._pendingVisibleAutoload = true
            return false
        }
        root._pendingVisibleAutoload = false
        if (appRef && appRef.backendBooted) {
            runReport(true)
        } else {
            debugBannerText = "Report backend is starting."
        }
        return true
    }
    function _toFileUrl(pathText) {
        var normalized = _safeText(pathText).trim()
        if (normalized.length <= 0) return ""
        return "file:///" + encodeURI(normalized.replace(/\\/g, "/"))
    }
    function _tryOpenBannerPath() {
        if (root.hasBackendError || root.hasDataError) return
        if (_safeText(root._lastExportPath).length <= 0) return
        if (root.debugBannerText.indexOf("Click to open") < 0) return
        if (!Qt.openUrlExternally(_toFileUrl(root._lastExportPath))) {
            root.hasDataError = true
            root.debugBannerText = "Could not open file: " + root._lastExportPath
        }
    }
    function _firstRowValue(row, keys, fallbackValue) {
        if (!row || !keys || keys.length <= 0) return fallbackValue
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i]
            if (row[k] !== undefined && row[k] !== null && row[k] !== "") {
                return row[k]
            }
        }
        return fallbackValue
    }
    function _normalizeDetailRow(sourceRow) {
        var row = sourceRow || ({})
        var normalizedDate = _safeText(_firstRowValue(row, ["date", "Date", "dateText"], "")).trim()
        var normalizedDesc = _safeText(_firstRowValue(row, ["description", "Description", "descriptionText"], "")).trim()
        if (normalizedDesc.length <= 0) normalizedDesc = "(No description)"
        var normalizedClient = _safeText(_firstRowValue(row, ["clientName", "ClientName", "client"], "")).trim()
        var normalizedMatter = _safeText(_firstRowValue(row, ["matterName", "MatterName", "matter"], "")).trim()
        if (normalizedMatter.length <= 0) normalizedMatter = "No Matter"
        var normalizedHours = Number(_firstRowValue(row, ["hours", "Hours"], 0.0))
        if (!isFinite(normalizedHours)) normalizedHours = 0.0
        var normalizedGross = Number(_firstRowValue(row, ["grossToClient", "GrossToClient"], 0.0))
        if (!isFinite(normalizedGross)) normalizedGross = 0.0
        var normalizedRate = Number(_firstRowValue(row, ["rate", "Rate", "clientRate", "ClientRate"], 0.0))
        if (!isFinite(normalizedRate)) normalizedRate = 0.0
        var normalizedShare = Number(_firstRowValue(row, ["sharePct", "SharePct"], 100.0))
        if (!isFinite(normalizedShare)) normalizedShare = 100.0
        var normalizedRawSeconds = parseInt(_firstRowValue(row, ["rawSeconds", "RawSeconds"], 0))
        if (!isFinite(normalizedRawSeconds) || normalizedRawSeconds < 0) normalizedRawSeconds = 0
        return {
            "entryId": _safeText(_firstRowValue(row, ["entryId", "EntryID", "EntryId"], "")),
            "clientId": _safeText(_firstRowValue(row, ["clientId", "ClientID", "ClientId"], "")),
            "matterId": _safeText(_firstRowValue(row, ["matterId", "MatterID", "MatterId"], "")),
            "date": normalizedDate,
            "clientName": normalizedClient,
            "matterName": normalizedMatter,
            "description": normalizedDesc,
            "status": _safeText(_firstRowValue(row, ["status", "Status"], "Draft")),
            "hours": normalizedHours,
            "grossToClient": normalizedGross,
            "rate": normalizedRate,
            "sharePct": normalizedShare,
            "rawSeconds": normalizedRawSeconds
        }
    }

    function _sortGlyph(colKey) {
        if (_safeText(colKey) !== _safeText(sortKey)) return "";
        return sortAscending ? "  ↑" : "  ↓";
    }

    function toggleSort(key) {
        if (sortKey === key) { sortAscending = !sortAscending; } 
        else { sortKey = key; sortAscending = key !== "date"; }
        _applySortAndSummary();
    }

    signal editRequested(var row)
    signal reportWindowRequested(var reportDocument)
    signal detachRequested(var state)
    property bool detachedWindow: false

    Timer { id: cooldownTimer; interval: 550; onTriggered: root._isOnCooldown = false }
    Timer {
        id: reportLoadTimeoutTimer
        interval: 20000
        repeat: false
        onTriggered: {
            if (!root.busy || root._pendingRequestToken.length <= 0) return
            root.busy = false
            root.hasBackendError = false
            root.hasDataError = true
            root._lastExportPath = ""
            root._pendingRunSignature = ""
            root._pendingRunEpochMs = 0
            root._pendingRequestToken = ""
            root.debugBannerText = "Report load timed out. Click Run to try again."
        }
    }

    function _buildExportPayload(configOverrides) {
        var exportConfig = {
            "detail": true,
            "summary": true,
            "aggregate": true,
            "selections": true,
            "hstRate": 13.0
        }
        if (configOverrides) {
            for (var key in configOverrides) {
                exportConfig[key] = configOverrides[key]
            }
        }
        return {
            "filters": buildFilters(),
            "rows": displayRows,
            "summaryRows": displaySummaryRows,
            "totals": reportTotals,
            "config": exportConfig,
            "sortKey": sortKey,
            "sortAscending": sortAscending
        }
    }

    function _reportGeneratedAt() {
        return Qt.formatDateTime(new Date(), "yyyy-MM-dd hh:mm")
    }

    function _reportFilterSummary() {
        var filters = buildFilters()
        var parts = [
            "Date: " + _safeText(filters.fromDate) + " to " + _safeText(filters.toDate),
            "Status: " + _statusModeLabelFromValue(filters.statusMode),
            "Client: " + (_safeText(clientFilterText).length > 0 ? clientFilterText : "All Clients"),
            "Matter: " + (_safeText(matterFilterText).length > 0 ? matterFilterText : "All Matters")
        ]
        if (_safeText(queryText).trim().length > 0) parts.push("Search: " + queryText)
        return parts.join(" | ")
    }

    function _reportOpenActionForRow(row) {
        var normalized = _normalizeDetailRow(row || ({}))
        return {
            "type": "openRecord",
            "reportId": "docket_activity",
            "recordType": "time_entry",
            "recordId": normalized.entryId,
            "row": normalized
        }
    }

    function _buildReportDocument(orientationOverride) {
        var detailRows = []
        for (var i = 0; i < displayRows.length; i++) {
            var detail = _normalizeDetailRow(displayRows[i])
            detail.recordType = "time_entry"
            detail.recordId = detail.entryId
            detail.openAction = _reportOpenActionForRow(detail)
            detail.grossDisplay = "$" + Number(detail.grossToClient).toFixed(2)
            detail.hoursDisplay = Number(detail.hours).toFixed(2)
            detailRows.push(detail)
        }

        var summaryRows = []
        for (var s = 0; s < displaySummaryRows.length; s++) {
            var summary = displaySummaryRows[s] || ({})
            var totalHours = Number(summary.totalHours || 0)
            var totalGross = Number(summary.totalGrossToClient || 0)
            summaryRows.push({
                "matterName": _safeText(summary.matterName),
                "clientName": _safeText(summary.clientName),
                "entryCount": _safeText(summary.entryCount || 0),
                "totalHours": isFinite(totalHours) ? totalHours.toFixed(2) : "0.00",
                "totalGrossToClient": "$" + (isFinite(totalGross) ? totalGross.toFixed(2) : "0.00")
            })
        }

        return {
            "reportId": "docket_activity",
            "title": "Docket Activity Report",
            "generatedAt": _reportGeneratedAt(),
            "orientation": _safeText(orientationOverride).length > 0 ? _safeText(orientationOverride) : "landscape",
            "branding": {
                "firmName": "Cory Schneider Law Office",
                "firmContact": "Cory Schneider Law Office Practice Management",
                "logoUrl": "../assets/CS.svg"
            },
            "filters": buildFilters(),
            "filterSummary": _reportFilterSummary(),
            "totals": reportTotals,
            "sourceState": snapshotState(),
            "exportPayload": _buildExportPayload({}),
            "sections": [
                {
                    "sectionId": "detail",
                    "type": "table",
                    "title": "Detail",
                    "columns": [
                        { "key": "date", "label": "Date", "width": 0.11 },
                        { "key": "clientName", "label": "Client", "width": 0.18 },
                        { "key": "matterName", "label": "Matter", "width": 0.20 },
                        { "key": "description", "label": "Description", "width": 0.32 },
                        { "key": "hoursDisplay", "label": "Hours", "width": 0.08, "align": "right" },
                        { "key": "grossDisplay", "label": "Gross", "width": 0.11, "align": "right" }
                    ],
                    "rows": detailRows
                },
                {
                    "sectionId": "summary",
                    "type": "table",
                    "title": "Summary by Matter",
                    "columns": [
                        { "key": "matterName", "label": "Matter", "width": 0.36 },
                        { "key": "clientName", "label": "Client", "width": 0.30 },
                        { "key": "entryCount", "label": "Entries", "width": 0.10, "align": "right" },
                        { "key": "totalHours", "label": "Hours", "width": 0.11, "align": "right" },
                        { "key": "totalGrossToClient", "label": "Gross", "width": 0.13, "align": "right" }
                    ],
                    "rows": summaryRows
                },
                {
                    "sectionId": "aggregate",
                    "type": "keyValue",
                    "title": "Total Aggregate",
                    "columns": [
                        { "key": "label", "label": "Metric", "width": 0.60 },
                        { "key": "value", "label": "Value", "width": 0.40, "align": "right" }
                    ],
                    "rows": [
                        { "label": "Entries", "value": _safeText(displayRows.length) },
                        { "label": "Hours", "value": Number(reportTotals.totalHours || 0).toFixed(2) },
                        { "label": "Gross", "value": "$" + Number(reportTotals.totalGrossToClient || 0).toFixed(2) }
                    ]
                }
            ]
        }
    }

    function openReportWindow(forceReload) {
        if (forceReload === undefined) forceReload = false
        if (busy) {
            _openReportAfterLoad = true
            debugBannerText = "Opening report after refresh..."
            return
        }
        if (forceReload || !_loadedOnce) {
            _openReportAfterLoad = true
            runReport(true)
            return
        }
        reportWindowRequested(_buildReportDocument("landscape"))
    }

    function executePdfExport(config) {
        if (!appRef || !appRef.exportDocketActivityPdf) return;
        busy = true
        var result = null
        try {
            result = appRef.exportDocketActivityPdf(_buildExportPayload(config || {}))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        busy = false
        if (result && result.ok) {
            hasBackendError = false
            hasDataError = false
            _lastExportPath = _safeText(result.path)
            debugBannerText = result.message ? String(result.message) + " | Click to open" : "PDF export complete. Click to open."
        } else {
            hasDataError = true
            _lastExportPath = ""
            debugBannerText = "PDF export failed: " + (result && result.message ? String(result.message) : "Unknown error")
        }
    }

    function executeCsvExport() {
        if (!appRef || !appRef.exportDocketActivityCsv) return;
        busy = true
        var result = null
        try {
            result = appRef.exportDocketActivityCsv(_buildExportPayload({}))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        busy = false
        if (result && result.ok) {
            hasBackendError = false
            hasDataError = false
            _lastExportPath = _safeText(result.path)
            debugBannerText = result.message ? String(result.message) + " | Click to open" : "CSV export complete. Click to open."
        } else {
            hasDataError = true
            _lastExportPath = ""
            debugBannerText = "CSV export failed: " + (result && result.message ? String(result.message) : "Unknown error")
        }
    }

    function exportCsv() {
        executeCsvExport()
    }

    function exportPdf() {
        openReportWindow(false)
    }

    function _handleReportPayload(payload, signature, nowMs) {
        var effectiveNow = nowMs > 0 ? nowMs : Date.now()
        reportLoadTimeoutTimer.stop()
        busy = false
        _loadedOnce = true

        if (!payload || !payload.ok) {
            _lastExportPath = ""
            _openReportAfterLoad = false
            hasBackendError = true
            hasDataError = false
            debugBannerText = "Excel read failed: " + (payload ? payload.message : "Unknown failure.")
            reportRows = []
            _applySortAndSummary()
            root._isOnCooldown = true
            cooldownTimer.restart()
            return
        }

        hasBackendError = false
        reportRows = payload.rows ? payload.rows : []
        _applyFilterOptionsFromPayload(payload)
        _applySortAndSummary()
        root._lastRunSignature = signature
        root._lastRunEpochMs = effectiveNow
        root._isOnCooldown = true
        cooldownTimer.restart()

        if (payload.debug) {
            var d = payload.debug
            if (d.scanned === 0) {
                _lastExportPath = ""
                hasDataError = true
                debugBannerText = "Excel read produced 0 rows (See logs)."
            } else if (reportRows.length === 0) {
                _lastExportPath = ""
                hasDataError = false
                debugBannerText = "Filters excluded all " + d.scanned + " rows (See logs)."
            } else {
                _lastExportPath = ""
                hasDataError = false
                debugBannerText = "Loaded from Excel: " + d.scanned + " rows | After filters: " + reportRows.length + " rows | Refresh: " + Qt.formatTime(new Date(), "hh:mm:ss")
            }
        } else {
            hasDataError = reportRows.length <= 0
            debugBannerText = reportRows.length > 0
                ? ("Loaded " + reportRows.length + " docket rows.")
                : "No docket rows matched the current filters."
        }
        if (root._openReportAfterLoad) {
            root._openReportAfterLoad = false
            Qt.callLater(function() {
                root.reportWindowRequested(root._buildReportDocument("landscape"))
            })
        }
    }

    function setPreset(presetKey) {
        currentPreset = _presetKeyFromLabel(presetKey);
        var today = new Date(); var start = new Date(today.getFullYear(), today.getMonth(), today.getDate()); var end = new Date(start);
        if (currentPreset === "all") { start = new Date(1999, 0, 1); end = new Date(2099, 11, 31); }
        else if (currentPreset === "year") { start = new Date(start.getFullYear(), 0, 1); }
        else if (currentPreset === "month") { start = new Date(start.getFullYear(), start.getMonth(), 1); }
        else if (currentPreset === "week") { start.setDate(start.getDate() - start.getDay()); }
        else if (currentPreset === "last_month") { start = new Date(start.getFullYear(), start.getMonth() - 1, 1); end = new Date(start.getFullYear(), start.getMonth() + 1, 0); }
        else if (currentPreset === "last_week") { end.setDate(end.getDate() - end.getDay() - 1); start = new Date(end); start.setDate(start.getDate() - 6); }
        fromDateText = Qt.formatDate(start, "yyyy-MM-dd"); toDateText = Qt.formatDate(end, "yyyy-MM-dd");
        if (fromDateInput) fromDateInput.text = fromDateText
        if (toDateInput) toDateInput.text = toDateText
        _syncPresetCombo()
    }
    
    function clearFilters() {
        root.queryText = ""; root.clientFilterText = "All Clients"; root.matterFilterText = "All Matters";
        root.statusMode = "all";
        if (statusModeCombo) statusModeCombo.editText = "All Statuses"
        root.setPreset("all");
        root.runReport(true);
    }

    function _dedupeAndSortOptions(seedLabel, values) {
        var map = ({})
        var ordered = []
        if (!values) values = []
        for (var i = 0; i < values.length; i++) {
            var raw = _safeText(values[i]).trim()
            if (raw.length <= 0) continue
            var key = raw.toLowerCase()
            if (map[key] === true) continue
            map[key] = true
            ordered.push(raw)
        }
        ordered.sort(function(a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()) })
        ordered.unshift(seedLabel)
        return ordered
    }

    function _syncFilterSelection(combo, optionList, selectedText, defaultText) {
        var normalized = _safeText(selectedText).trim()
        if (normalized.length <= 0) normalized = defaultText
        var exists = false
        for (var i = 0; i < optionList.length; i++) {
            if (_safeText(optionList[i]).toLowerCase() === normalized.toLowerCase()) {
                normalized = optionList[i]
                exists = true
                break
            }
        }
        if (!exists) normalized = defaultText
        if (combo && combo.editText !== normalized) {
            combo.editText = normalized
        }
        return normalized
    }

    function _applyFilterOptionsFromPayload(payloadObj) {
        var payloadClients = payloadObj && payloadObj.optionClients ? payloadObj.optionClients : []
        var payloadMatters = payloadObj && payloadObj.optionMatters ? payloadObj.optionMatters : []
        if ((!payloadClients || payloadClients.length <= 0) || (!payloadMatters || payloadMatters.length <= 0)) {
            var fallbackClients = []
            var fallbackMatters = []
            for (var i = 0; i < reportRows.length; i++) {
                var c = _safeText(reportRows[i].clientName).trim()
                var m = _safeText(reportRows[i].matterName).trim()
                if (c.length > 0) fallbackClients.push(c)
                if (m.length > 0) fallbackMatters.push(m)
            }
            payloadClients = fallbackClients
            payloadMatters = fallbackMatters
        }

        masterClientList = _dedupeAndSortOptions("All Clients", payloadClients)
        masterMatterList = _dedupeAndSortOptions("All Matters", payloadMatters)
        clientFilterOptions = masterClientList
        matterFilterOptions = masterMatterList
        clientFilterText = _syncFilterSelection(clientFilterCombo, clientFilterOptions, clientFilterText, "All Clients")
        matterFilterText = _syncFilterSelection(matterFilterCombo, matterFilterOptions, matterFilterText, "All Matters")
    }

    // PRIORITY 1: STRICT LISTMODEL INJECTION (Solves Delegate Blanks completely)
    ListModel { id: strictRowsModel }
    ListModel { id: strictSummaryModel }

    function _applySortAndSummary() {
        var normalizedRows = []
        for (var j = 0; j < reportRows.length; j++) {
            normalizedRows.push(_normalizeDetailRow(reportRows[j]))
        }
        displayRows = normalizedRows

        // 1. Populate strict detail model
        strictRowsModel.clear();
        for (var k = 0; k < displayRows.length; k++) {
            var rowObj = displayRows[k];
            strictRowsModel.append(rowObj);
        }

        // 2. Populate summary model
        var summaryMap = ({}); var th=0.0; var tg=0.0;
        for(var i=0; i<displayRows.length; i++){
            var r=displayRows[i]; th+=r.hours; tg+=r.grossToClient;
            var m=r.matterName||"No Matter"; var c=r.clientName; var k=m+"::"+c;
            if(!summaryMap[k]) summaryMap[k]={matterName:m, clientName:c, entryCount:0, totalHours:0.0, totalGrossToClient:0.0};
            summaryMap[k].entryCount++; summaryMap[k].totalHours+=r.hours; summaryMap[k].totalGrossToClient+=r.grossToClient;
        }
        
        strictSummaryModel.clear();
        var sList=[]; 
        for(var x in summaryMap) {
            var sumObj = summaryMap[x];
            strictSummaryModel.append(sumObj);
            sList.push(sumObj);
        }
        displaySummaryRows = sList; 
        reportTotals = {totalHours: th, totalGrossToClient: tg};
    }

    function _statusModeValueFromLabel(labelText) {
        var label = _safeText(labelText).trim().toLowerCase()
        if (label === "all statuses") return "all"
        if (label === "all (except merged)") return "all_except_merged"
        if (label === "ready for billing") return "ready_for_billing"
        if (label === "draft") return "draft"
        if (label === "billed") return "billed"
        return "all_except_merged"
    }

    function _statusModeLabelFromValue(statusValue) {
        var value = _safeText(statusValue).trim().toLowerCase()
        if (value === "all" || value === "all_statuses") return "All Statuses"
        if (value === "all_except_merged") return "All (Except Merged)"
        if (value === "ready_for_billing" || value === "ready") return "Ready for Billing"
        if (value === "draft" || value === "draft_only" || value === "open" || value === "unbilled") return "Draft"
        if (value === "billed" || value === "billed_only") return "Billed"
        return "All (Except Merged)"
    }

    function _presetLabelFromKey(presetKey) {
        var key = _safeText(presetKey).trim().toLowerCase()
        if (key === "today") return "Today"
        if (key === "week") return "WTD"
        if (key === "month") return "MTD"
        if (key === "last_week") return "L-Week"
        if (key === "last_month") return "L-Month"
        if (key === "year") return "YTD"
        return "All"
    }

    function _presetKeyFromLabel(labelText) {
        var raw = _safeText(labelText).trim()
        var key = raw.toLowerCase()
        if (key === "all" || key === "today" || key === "week" || key === "month"
                || key === "last_week" || key === "last_month" || key === "year") {
            return key
        }
        if (key === "wtd") return "week"
        if (key === "mtd") return "month"
        if (key === "l-week" || key === "last week") return "last_week"
        if (key === "l-month" || key === "last month") return "last_month"
        if (key === "ytd") return "year"
        return "all"
    }

    function _presetIndexFromKey(presetKey) {
        var label = _presetLabelFromKey(presetKey)
        for (var i = 0; i < presetLabelOptions.length; i++) {
            if (_safeText(presetLabelOptions[i]) === label) {
                return i
            }
        }
        return 0
    }

    function _syncPresetCombo() {
        if (rangePresetCombo) {
            rangePresetCombo.currentIndex = _presetIndexFromKey(currentPreset)
            rangePresetCombo.editText = _presetLabelFromKey(currentPreset)
        }
    }

    function _compactWideControlWidth(toolbarWidth) {
        var availableWidth = Math.max(0, Number(toolbarWidth || 0))
        var fixedWidth =
            root.compactDateWidth
            + root.compactDateWidth
            + root.compactStatusWidth
            + root.compactRangeWidth
            + root.compactButtonWidth
            + root.compactOpenReportButtonWidth
            + root.compactButtonWidth
            + root.compactButtonWidth
            + root.compactRunButtonWidth
            + (root.compactToolbarGap * 10)
        var remainingForWideControls = availableWidth - fixedWidth
        var candidateWidth = Math.floor(remainingForWideControls / 2)
        var cappedWidth = Math.max(root.compactWideMinWidth, Math.min(root.compactWideMaxWidth, candidateWidth))
        return Math.max(1, Math.min(availableWidth, cappedWidth))
    }

    function buildFilters() {
        var statusText = statusModeCombo ? statusModeCombo.editText : "All (Except Merged)"
        return {
            "fromDate": fromDateText,
            "toDate": toDateText,
            "statusMode": _statusModeValueFromLabel(statusText),
            "query": queryText,
            "clientFilter": clientFilterText === "All Clients" ? "" : clientFilterText,
            "matterFilter": matterFilterText === "All Matters" ? "" : matterFilterText,
            "matterId": matterIdFilterText
        }
    }

    function snapshotState() {
        return {
            "fromDateText": fromDateText,
            "toDateText": toDateText,
            "statusModeText": statusModeCombo ? statusModeCombo.editText : "All (Except Merged)",
            "queryText": queryText,
            "clientFilterText": clientFilterText,
            "matterFilterText": matterFilterText,
            "matterIdFilterText": matterIdFilterText,
            "currentPreset": currentPreset,
            "sortKey": sortKey,
            "sortAscending": sortAscending
        }
    }

    function applyState(stateObj, triggerRunReport) {
        var state = stateObj || ({})
        fromDateText = _safeText(state.fromDateText).trim().length > 0
            ? _safeText(state.fromDateText).trim()
            : fromDateText
        toDateText = _safeText(state.toDateText).trim().length > 0
            ? _safeText(state.toDateText).trim()
            : toDateText
        queryText = _safeText(state.queryText)
        clientFilterText = _safeText(state.clientFilterText).trim().length > 0
            ? _safeText(state.clientFilterText).trim()
            : "All Clients"
        matterFilterText = _safeText(state.matterFilterText).trim().length > 0
            ? _safeText(state.matterFilterText).trim()
            : "All Matters"
        matterIdFilterText = _safeText(state.matterIdFilterText).trim()
        currentPreset = _safeText(state.currentPreset).trim().length > 0
            ? _presetKeyFromLabel(state.currentPreset)
            : currentPreset
        sortKey = _safeText(state.sortKey).trim().length > 0 ? _safeText(state.sortKey).trim() : sortKey
        if (state.sortAscending !== undefined) sortAscending = !!state.sortAscending

        if (fromDateInput) fromDateInput.text = fromDateText
        if (toDateInput) toDateInput.text = toDateText
        _syncPresetCombo()

        var incomingStatus = _safeText(state.statusModeText).trim()
        if (incomingStatus.length > 0) {
            if (incomingStatus.toLowerCase().indexOf("all") === 0
                || incomingStatus.toLowerCase() === "draft"
                || incomingStatus.toLowerCase() === "ready for billing"
                || incomingStatus.toLowerCase() === "billed") {
                if (statusModeCombo) statusModeCombo.editText = incomingStatus
            } else {
                if (statusModeCombo) statusModeCombo.editText = _statusModeLabelFromValue(incomingStatus)
            }
        } else if (statusModeCombo && _safeText(statusModeCombo.editText).trim().length <= 0) {
            statusModeCombo.editText = "All (Except Merged)"
        }

        clientFilterText = _syncFilterSelection(clientFilterCombo, clientFilterOptions, clientFilterText, "All Clients")
        matterFilterText = _syncFilterSelection(matterFilterCombo, matterFilterOptions, matterFilterText, "All Matters")

        if (triggerRunReport === undefined || triggerRunReport) {
            runReport(true)
        }
    }

    // PRIORITY 4: ANTI-SPAM (Strict single-execution trigger)
    function runReport(forceReload) {
        if (forceReload === undefined) forceReload = false
        // Explicit user actions (preset clicks, post-save refresh) should bypass cooldown.
        if (busy) {
            return;
        }
        if (root._isOnCooldown && !forceReload) {
            return;
        }
        if (!docketAppRef || !docketAppRef.loadDocketActivityReport) {
            _lastExportPath = ""
            hasBackendError = true
            hasDataError = false
            debugBannerText = "Docket report backend is unavailable."
            return
        }
        var filters = buildFilters()
        var signature = JSON.stringify(filters)
        var nowMs = Date.now()
        if (!forceReload && signature === root._lastRunSignature && (nowMs - root._lastRunEpochMs) < 2500) {
            return
        }

        busy = true
        hasBackendError = false
        hasDataError = false
        _lastExportPath = ""
        debugBannerText = "Loading report..."
        _pendingRunSignature = signature
        _pendingRunEpochMs = nowMs
        _pendingRequestToken = signature + "::" + String(nowMs) + "::" + Math.random().toString(36).slice(2)
        reportLoadTimeoutTimer.restart()

        try {
            var requestPayload = Object.assign({}, filters, { "_requestToken": _pendingRequestToken })
            docketAppRef.loadDocketActivityReport(requestPayload)
        } catch (e) {
            _lastExportPath = ""
            hasBackendError = true
            hasDataError = false
            debugBannerText = "UI Error: Python crash -> " + e
            busy = false
            reportLoadTimeoutTimer.stop()
            _pendingRunSignature = ""
            _pendingRunEpochMs = 0
            _pendingRequestToken = ""
        }
    }

    onVisibleChanged: {
        _tryAutoLoad("onVisibleChanged")
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onBackendBootChanged() {
            if (!root.visible || !root.appRef || !root.appRef.backendBooted) return
            if (!root._startupAllowsAutoLoad("onBackendBootChanged")) {
                root._pendingVisibleAutoload = true
                return
            }
            root.runReport(true)
        }
    }

    Connections {
        target: root.windowRef
        function onStartupHeavyWorkAllowedChanged() {
            if (!root.windowRef || !root.windowRef.startupHeavyWorkAllowed) return
            if (!root.visible || !root.autoLoadOnVisible || root._loadedOnce) return
            root._tryAutoLoad("window.startupHeavyWorkAllowed")
        }
    }

    Connections {
        target: root.docketAppRef
        ignoreUnknownSignals: true
        function onDocketActivityReportFinished(result) {
            var requestToken = root._safeText(result && result._requestToken)
            if (requestToken.length <= 0 || requestToken !== root._pendingRequestToken) return
            var pendingSignature = root._pendingRunSignature
            var pendingEpochMs = root._pendingRunEpochMs
            root._pendingRunSignature = ""
            root._pendingRunEpochMs = 0
            root._pendingRequestToken = ""
            root._handleReportPayload(result, pendingSignature, pendingEpochMs)
        }
        function onError(message) {
            if (!root.visible || !root.busy || root._pendingRequestToken.length <= 0) return
            root._lastExportPath = ""
            root.hasBackendError = true
            root.hasDataError = false
            root.debugBannerText = String(message || "Docket report backend error.")
        }
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 8; spacing: 4
        
        // STATUS BANNER
        Rectangle {
            id: reportStatusBanner
            Layout.fillWidth: true; Layout.preferredHeight: 20; radius: 4
            property string bannerTone: root.hasBackendError ? "error" : (root.hasDataError ? "warning" : "success")
            color: root._statusSurface(bannerTone)
            border.width: 1
            border.color: root._statusBorder(bannerTone)
            property bool clickable: !root.hasBackendError && !root.hasDataError && _safeText(root._lastExportPath).length > 0 && root.debugBannerText.indexOf("Click to open") >= 0
            Text {
                anchors.centerIn: parent
                width: parent.width - 16
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: root.debugBannerText
                color: root._statusInk(parent.bannerTone)
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
            MouseArea {
                anchors.fill: parent
                enabled: parent.clickable
                cursorShape: parent.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: root._tryOpenBannerPath()
            }
        }

        // COMPACT FILTER TOOLBAR
        Flow {
            id: compactFilterToolbar
            Layout.fillWidth: true
            Layout.preferredHeight: compactFilterToolbar.implicitHeight
            Layout.minimumHeight: compactFilterToolbar.implicitHeight
            spacing: root.compactToolbarGap

            readonly property int safeControlMaxWidth: Math.max(1, Math.floor(width))
            readonly property int wideControlWidth: root._compactWideControlWidth(width)

            ModernTextField {
                id: fromDateInput
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactTextFieldRatios
                label: "From"
                text: root.fromDateText
                datePickerEnabled: true
                width: Math.min(root.compactDateWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onEditingFinished: { root.fromDateText = text; }
                onDatePickerDatePicked: function(_pickedDate, isoText) { root.fromDateText = isoText }
            }

            ModernTextField {
                id: toDateInput
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactTextFieldRatios
                label: "To"
                text: root.toDateText
                datePickerEnabled: true
                width: Math.min(root.compactDateWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onEditingFinished: { root.toDateText = text; }
                onDatePickerDatePicked: function(_pickedDate, isoText) { root.toDateText = isoText }
            }

            ModernComboBox {
                id: statusModeCombo
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactComboRatios
                label: "Status"
                fullModel: ["All Statuses", "All (Except Merged)", "Draft", "Ready for Billing", "Billed"]
                editText: "All Statuses"
                width: Math.min(root.compactStatusWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onActivated: {
                    root.statusMode = root._statusModeValueFromLabel(editText)
                    root.runReport(true)
                }
            }

            ModernComboBox {
                id: clientFilterCombo
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactComboRatios
                label: "Client"
                fullModel: root.clientFilterOptions
                editText: root.clientFilterText
                width: compactFilterToolbar.wideControlWidth
                height: root.compactToolbarHeight
                onActivated: {
                    root.clientFilterText = editText
                    root.runReport(true)
                }
            }

            ModernComboBox {
                id: matterFilterCombo
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactComboRatios
                label: "Matter"
                fullModel: root.matterFilterOptions
                editText: root.matterFilterText
                width: compactFilterToolbar.wideControlWidth
                height: root.compactToolbarHeight
                onActivated: {
                    root.matterFilterText = editText
                    root.runReport(true)
                }
            }

            ModernComboBox {
                id: rangePresetCombo
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactComboRatios
                label: "Range"
                editable: false
                fullModel: root.presetLabelOptions
                editText: root._presetLabelFromKey(root.currentPreset)
                width: Math.min(root.compactRangeWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onActivated: function(index) {
                    var pickedLabel = (typeof index === "number" && index >= 0)
                        ? rangePresetCombo.textAt(index)
                        : rangePresetCombo.currentText
                    root.setPreset(root._presetKeyFromLabel(pickedLabel))
                    root.runReport(true)
                }
            }

            PillButton {
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactButtonRatios
                sfxBus: root.sfxBus
                text: "Clear"
                primary: false
                width: Math.min(root.compactButtonWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onClicked: root.clearFilters()
            }

            PillButton {
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactButtonRatios
                sfxBus: root.sfxBus
                text: "Open"
                tooltipText: "Open Report"
                primary: false
                width: Math.min(root.compactOpenReportButtonWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onClicked: root.openReportWindow(false)
            }

            PillButton {
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactButtonRatios
                sfxBus: root.sfxBus
                text: "PDF"
                tooltipText: "Open Report to Save PDF"
                primary: false
                width: Math.min(root.compactButtonWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onClicked: root.openReportWindow(false)
            }

            PillButton {
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactButtonRatios
                sfxBus: root.sfxBus
                text: "CSV"
                primary: false
                width: Math.min(root.compactButtonWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onClicked: { if (appRef.exportDocketActivityCsv) root.executeCsvExport(); }
            }

            PillButton {
                t: root.t
                metrics: root.metrics
                scaleRatios: root.compactButtonRatios
                sfxBus: root.sfxBus
                text: root.busy ? "Loading..." : "Run"
                primary: true
                width: Math.min(root.compactRunButtonWidth, compactFilterToolbar.safeControlMaxWidth)
                height: root.compactToolbarHeight
                onClicked: root.runReport(true)
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.bottomMargin: root.panelBottomInsetPx
            Layout.minimumHeight: root.reportTableMinimumHeight
            Layout.preferredHeight: root.reportTablePreferredHeight
            color: "transparent"
            radius: root.sectionRadiusPx
            border.width: 1
            border.color: root.isProMode ? root._borderSubtle : _textColor(0.2)
            clip: true

            Rectangle { anchors.fill: parent; color: _surfaceColor; radius: root.sectionRadiusPx; z: -1 }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.tableHeaderHeight
                    color: root._tableHeaderFill
                    Item {
                        anchors.fill: parent

                        Text {
                            id: reportHeaderGross
                            text: "Gross"
                            anchors.right: parent.right
                            anchors.rightMargin: root.tableRightPadding
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableGrossWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textColor(0.6)
                            font.weight: Font.DemiBold
                            font.pixelSize: root.tableHeaderFontPx
                            font.family: "Courier New"
                        }
                        Text {
                            id: reportHeaderHours
                            text: "Hours"
                            anchors.right: reportHeaderGross.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableHoursWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textColor(0.6)
                            font.weight: Font.DemiBold
                            font.pixelSize: root.tableHeaderFontPx
                            font.family: "Courier New"
                        }
                        Text {
                            id: reportHeaderDate
                            text: "Date"
                            anchors.left: parent.left
                            anchors.leftMargin: root.tableLeftPadding
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableDateWidth
                            color: _textColor(0.6)
                            font.weight: Font.DemiBold
                            font.pixelSize: root.tableHeaderFontPx
                        }
                        Text {
                            id: reportHeaderDetails
                            text: "Details"
                            anchors.left: reportHeaderDate.right
                            anchors.leftMargin: root.tableColumnGap
                            anchors.right: reportHeaderHours.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            color: _textColor(0.65)
                            font.weight: Font.DemiBold
                            font.pixelSize: root.tableHeaderFontPx
                            elide: Text.ElideRight
                        }
                    }
                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: root.isProMode ? root._borderSubtle : _textColor(0.2) }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 0
                    Layout.preferredHeight: root.detailPreferredHeight
                    clip: true
                    ListView {
                        id: reportList
                        anchors.fill: parent
                        clip: true
                        model: strictRowsModel
                        ScrollBar.vertical: ScrollBar {
                            policy: strictRowsModel.count > root.minVisibleDetailRows ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                        }
                        delegate: Rectangle {
                            required property int index
                            required property string entryId
                            required property string clientId
                            required property string matterId
                            required property string date
                            required property string clientName
                            required property string matterName
                            required property string description
                            required property string status
                            required property real hours
                            required property real grossToClient
                            required property real rate
                            required property real sharePct
                            required property int rawSeconds
                            readonly property bool showGroupHeader: {
                                if (index <= 0) return true
                                var prev = strictRowsModel.get(index - 1)
                                if (!prev) return true
                                return String(prev.clientName || "") !== String(clientName || "")
                                    || String(prev.matterName || "") !== String(matterName || "")
                            }
                            readonly property int entryTopMargin: showGroupHeader
                                ? (root.groupHeaderHeight + root.tableRowTopPadding)
                                : root.tableRowTopPadding
                            width: reportList.width
                            height: showGroupHeader ? (root.detailRowMinHeight + root.groupHeaderHeight) : root.detailRowMinHeight
                            color: index % 2 === 0 ? "transparent" : root._tableAltFill

                            Item {
                                anchors.fill: parent

                                Text {
                                    id: rowDate
                                    text: date
                                    anchors.left: parent.left
                                    anchors.leftMargin: root.tableLeftPadding
                                    anchors.top: parent.top
                                    anchors.topMargin: entryTopMargin
                                    width: root.tableDateWidth
                                    color: _textPrimary
                                    font.pixelSize: root.tableBodyFontPx
                                }

                                Text {
                                    id: rowGross
                                    text: "$" + Number(grossToClient).toFixed(2)
                                    anchors.right: parent.right
                                    anchors.rightMargin: root.tableRightPadding
                                    anchors.top: parent.top
                                    anchors.topMargin: entryTopMargin
                                    width: root.tableGrossWidth
                                    horizontalAlignment: Text.AlignLeft
                                    color: _textPrimary
                                    font.family: "Courier New"
                                    font.pixelSize: root.tableBodyFontPx
                                }
                                Text {
                                    id: rowHours
                                    text: Number(hours).toFixed(2)
                                    anchors.right: rowGross.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.top: parent.top
                                    anchors.topMargin: entryTopMargin
                                    width: root.tableHoursWidth
                                    horizontalAlignment: Text.AlignLeft
                                    color: _textPrimary
                                    font.family: "Courier New"
                                    font.pixelSize: root.tableBodyFontPx
                                }

                                Text {
                                    visible: showGroupHeader
                                    text: clientName + " | " + matterName
                                    anchors.left: rowDate.right
                                    anchors.leftMargin: root.tableColumnGap
                                    anchors.right: rowHours.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.top: parent.top
                                    anchors.topMargin: 4
                                    color: _accent
                                    font.pixelSize: root.tableBodyFontPx
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Item {
                                    id: detailBlock
                                    anchors.left: rowDate.right
                                    anchors.leftMargin: root.tableColumnGap
                                    anchors.right: rowHours.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.top: parent.top
                                    anchors.topMargin: entryTopMargin
                                    height: Math.min(parent.height - entryTopMargin - 2, detailDescription.implicitHeight)

                                    Text {
                                        id: detailDescription
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        text: description
                                        color: _textColor(0.72)
                                        font.pixelSize: root.tableDetailFontPx
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        maximumLineCount: root.descriptionMaxLines
                                        elide: Text.ElideRight
                                    }
                                }

                                MouseArea {
                                    anchors.fill: detailBlock
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    acceptedButtons: Qt.LeftButton
                                    preventStealing: true
                                    onDoubleClicked: {
                                        root.editRequested({
                                            "entryId": entryId,
                                            "clientId": clientId,
                                            "matterId": matterId,
                                            "date": date,
                                            "clientName": clientName,
                                            "matterName": matterName,
                                            "description": description,
                                            "status": status,
                                            "hours": hours,
                                            "grossToClient": grossToClient,
                                            "rate": rate,
                                            "sharePct": sharePct,
                                            "rawSeconds": rawSeconds
                                        })
                                    }
                                }
                            }
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: root._tableRule }
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: strictRowsModel.count === 0 && !root.busy
                        text: "No rows returned for current filters."
                        color: _textColor(0.5)
                        font.pixelSize: 13
                        font.italic: true
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.summaryHeaderHeight
                    color: root._tableHeaderFill
                    Item {
                        anchors.fill: parent
                        Text {
                            id: summaryGrossHeader
                            text: "Gross"
                            anchors.right: parent.right
                            anchors.rightMargin: root.tableRightPadding
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableGrossWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textColor(0.6)
                            font.pixelSize: root.tableHeaderFontPx
                            font.weight: Font.DemiBold
                            font.family: "Courier New"
                        }
                        Text {
                            id: summaryHoursHeader
                            text: "Hours"
                            anchors.right: summaryGrossHeader.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableHoursWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textColor(0.6)
                            font.pixelSize: root.tableHeaderFontPx
                            font.weight: Font.DemiBold
                            font.family: "Courier New"
                        }
                        Text {
                            id: summaryEntriesHeader
                            text: "Entries"
                            anchors.right: summaryHoursHeader.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableEntriesWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textColor(0.6)
                            font.pixelSize: root.tableHeaderFontPx
                            font.weight: Font.DemiBold
                            font.family: "Courier New"
                        }
                        Text {
                            text: "Summary by Matter"
                            anchors.left: parent.left
                            anchors.leftMargin: root.tableLeftPadding
                            anchors.right: summaryEntriesHeader.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            color: _textColor(0.9)
                            font.weight: Font.DemiBold
                            font.pixelSize: root.tableHeaderFontPx
                            elide: Text.ElideRight
                        }
                    }
                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: root.isProMode ? root._borderSubtle : _textColor(0.2) }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(root.summaryRowHeight, Math.min(root.effectiveSummaryMaxVisibleRows, Math.max(strictSummaryModel.count, 1)) * root.summaryRowHeight)
                    Layout.maximumHeight: root.effectiveSummaryMaxVisibleRows * root.summaryRowHeight
                    clip: true
                    ListView {
                        anchors.fill: parent
                        model: strictSummaryModel
                        clip: true
                        delegate: Rectangle {
                            required property string matterName
                            required property string clientName
                            required property int entryCount
                            required property real totalHours
                            required property real totalGrossToClient
                            required property int index
                            width: parent ? parent.width : 0
                            height: root.summaryRowHeight
                            color: index % 2 === 0 ? "transparent" : root._tableAltFill
                            Item {
                                anchors.fill: parent
                                Text {
                                    id: summaryRowGross
                                    text: "$" + Number(totalGrossToClient).toFixed(2)
                                    anchors.right: parent.right
                                    anchors.rightMargin: root.tableRightPadding
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: root.tableGrossWidth
                                    horizontalAlignment: Text.AlignLeft
                                    color: _textPrimary
                                    font.pixelSize: root.tableSummaryFontPx
                                    font.family: "Courier New"
                                }
                                Text {
                                    id: summaryRowHours
                                    text: Number(totalHours).toFixed(2)
                                    anchors.right: summaryRowGross.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: root.tableHoursWidth
                                    horizontalAlignment: Text.AlignLeft
                                    color: _textPrimary
                                    font.pixelSize: root.tableSummaryFontPx
                                    font.family: "Courier New"
                                }
                                Text {
                                    id: summaryRowEntries
                                    text: String(entryCount)
                                    anchors.right: summaryRowHours.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: root.tableEntriesWidth
                                    horizontalAlignment: Text.AlignLeft
                                    color: _textPrimary
                                    font.pixelSize: root.tableSummaryFontPx
                                    font.family: "Courier New"
                                }
                                Text {
                                    text: matterName + "  [" + clientName + "]"
                                    anchors.left: parent.left
                                    anchors.leftMargin: root.tableLeftPadding
                                    anchors.right: summaryRowEntries.left
                                    anchors.rightMargin: root.tableColumnGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: _textPrimary
                                    font.pixelSize: root.tableSummaryFontPx
                                    elide: Text.ElideRight
                                }
                            }
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: root._tableRule }
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: strictSummaryModel.count === 0
                        text: "No summary rows yet."
                        color: _textColor(0.5)
                        font.pixelSize: root.tableSummaryFontPx
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.aggregateRowHeight
                    color: root._tableAggregateFill
                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: root.isProMode ? root._borderSubtle : _textColor(0.2) }
                    Item {
                        anchors.fill: parent
                        Text {
                            id: aggregateGross
                            text: "$" + root.reportTotals.totalGrossToClient.toFixed(2)
                            anchors.right: parent.right
                            anchors.rightMargin: root.tableRightPadding
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableGrossWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textPrimary
                            font.pixelSize: root.tableSummaryFontPx
                            font.family: "Courier New"
                        }
                        Text {
                            id: aggregateHours
                            text: root.reportTotals.totalHours.toFixed(2)
                            anchors.right: aggregateGross.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableHoursWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textPrimary
                            font.pixelSize: root.tableSummaryFontPx
                            font.family: "Courier New"
                        }
                        Text {
                            id: aggregateEntries
                            text: String(strictRowsModel.count)
                            anchors.right: aggregateHours.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.tableEntriesWidth
                            horizontalAlignment: Text.AlignLeft
                            color: _textPrimary
                            font.pixelSize: root.tableSummaryFontPx
                            font.family: "Courier New"
                        }
                        Text {
                            text: "TOTAL AGGREGATE"
                            anchors.left: parent.left
                            anchors.leftMargin: root.tableLeftPadding
                            anchors.right: aggregateEntries.left
                            anchors.rightMargin: root.tableColumnGap
                            anchors.verticalCenter: parent.verticalCenter
                            color: _textPrimary
                            font.pixelSize: root.tableSummaryFontPx
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }
}
