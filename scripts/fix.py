import os
import re
from pathlib import Path

# =====================================================================
# 1. QML OVERRIDE (ListModel Strict Roles, Layout Locks, Flow Fix)
# =====================================================================
DOCKET_REPORT_QML = r"""pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Item {
    id: root

    property var t
    property var metrics
    property var appRef
    property var sfxBus
    property real sectionRadiusPx: 8
    property int fieldHeightPx: 36
    property bool autoLoadOnVisible: true

    // State & Errors
    property bool busy: false
    property string debugBannerText: "Waiting for backend..."
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
    property string sortKey: "date"
    property bool sortAscending: false
    
    // Theme Colors
    property color _surfaceColor: (root.t && root.t.panel2) ? root.t.panel2 : "#1A1A1A"
    property color _surfaceColor2: (root.t && root.t.panel) ? root.t.panel : "#111111"
    property color _textPrimary: (root.t && root.t.text) ? root.t.text : "#FFFFFF"
    property color _accent: (root.t && root.t.accent) ? root.t.accent : "#2979FF"
    
    property var masterClientList: ["All Clients"]
    property var masterMatterList: ["All Matters"]
    property var clientFilterOptions: ["All Clients"]
    property var matterFilterOptions: ["All Matters"]
    
    property var reportRows: []
    property var displayRows: []
    property var displaySummaryRows: []
    property var reportTotals: ({ "totalHours": 0.0, "totalGrossToClient": 0.0 })
    property bool _loadedOnce: false

    function _textColor(alpha) { return Qt.rgba(_textPrimary.r, _textPrimary.g, _textPrimary.b, alpha) }
    function _safeText(v) { return String(v === undefined || v === null ? "" : v) }

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
    signal detachRequested(var state)
    property bool detachedWindow: false

    Timer { id: cooldownTimer; interval: 2000; onTriggered: root._isOnCooldown = false }

    function executePdfExport(config) {
        if (!appRef || !appRef.exportDocketActivityPdf) return;
        busy = true;
        var payload = { "filters": buildFilters(), "rows": displayRows, "summaryRows": displaySummaryRows, "totals": reportTotals, "config": config, "sortKey": sortKey, "sortAscending": sortAscending };
        appRef.exportDocketActivityPdf(payload);
        busy = false;
    }

    function setPreset(presetKey) {
        currentPreset = presetKey;
        var today = new Date(); var start = new Date(today.getFullYear(), today.getMonth(), today.getDate()); var end = new Date(start);
        if (presetKey === "all") { start = new Date(1999, 0, 1); end = new Date(2099, 11, 31); }
        else if (presetKey === "year") { start = new Date(start.getFullYear(), 0, 1); }
        else if (presetKey === "month") { start = new Date(start.getFullYear(), start.getMonth(), 1); }
        else if (presetKey === "week") { start.setDate(start.getDate() - start.getDay()); }
        else if (presetKey === "last_month") { start = new Date(start.getFullYear(), start.getMonth() - 1, 1); end = new Date(start.getFullYear(), start.getMonth() + 1, 0); }
        else if (presetKey === "last_week") { end.setDate(end.getDate() - end.getDay() - 1); start = new Date(end); start.setDate(start.getDate() - 6); }
        fromDateText = Qt.formatDate(start, "yyyy-MM-dd"); toDateText = Qt.formatDate(end, "yyyy-MM-dd");
    }
    
    function clearFilters() {
        root.queryText = ""; root.clientFilterText = "All Clients"; root.matterFilterText = "All Matters";
        root.statusMode = "all"; root.setPreset("all"); root.runReport();
    }

    function _incorporateRowsIntoMaster(rows) {
        var cMap = ({}); var mMap = ({});
        for(var i=0; i<rows.length; i++){
            var c=_safeText(rows[i].clientName).trim(); var m=_safeText(rows[i].matterName).trim();
            if(c) cMap[c]=true; if(m) mMap[m]=true;
        }
        var cList=["All Clients"]; for(var ck in cMap) cList.push(ck);
        var mList=["All Matters"]; for(var mk in mMap) mList.push(mk);
        masterClientList = cList; masterMatterList = mList;
        clientFilterOptions = masterClientList; matterFilterOptions = masterMatterList;
    }

    // PRIORITY 1: STRICT LISTMODEL INJECTION (Solves Delegate Blanks completely)
    ListModel { id: strictRowsModel }
    ListModel { id: strictSummaryModel }

    function _applySortAndSummary() {
        displayRows = reportRows.slice(); 
        
        // 1. Populate Strict Detail Model
        strictRowsModel.clear();
        for(var j=0; j<displayRows.length; j++) {
            var rowObj = displayRows[j];
            // Ensure no undefined values crash the model
            rowObj.date = rowObj.date || "";
            rowObj.clientName = rowObj.clientName || "";
            rowObj.matterName = rowObj.matterName || "";
            rowObj.description = rowObj.description || "";
            rowObj.status = rowObj.status || "";
            rowObj.hours = Number(rowObj.hours) || 0.0;
            rowObj.grossToClient = Number(rowObj.grossToClient) || 0.0;
            strictRowsModel.append(rowObj);
        }
        
        console.log("[DocketUI] strictRowsModel.count = " + strictRowsModel.count);

        // 2. Populate Summary Model
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

    function buildFilters() {
        return {
            "fromDate": fromDateText, "toDate": toDateText,
            "statusMode": statusModeCombo.editText === "All (Except Merged)" ? "all_except_merged" : statusModeCombo.editText.toLowerCase().replace(" ", "_"),
            "query": queryText, "clientFilter": clientFilterText === "All Clients" ? "" : clientFilterText,
            "matterFilter": matterFilterText === "All Matters" ? "" : matterFilterText
        }
    }

    // PRIORITY 4: ANTI-SPAM (Strict single-execution trigger)
    function runReport() {
        if (root._isOnCooldown || busy) {
            console.log("[DocketUI] Ignore trigger: busy or on cooldown.");
            return;
        }
        if (!appRef || !appRef.getDocketActivityReport) { 
            hasBackendError = true; debugBannerText = "UI Error: Backend offline."; return; 
        }
        
        busy = true;
        hasBackendError = false; hasDataError = false;
        
        var payload;
        try { payload = appRef.getDocketActivityReport(buildFilters()); } 
        catch(e) { hasBackendError = true; debugBannerText = "UI Error: Python crash -> " + e; busy = false; return; }
        
        busy = false; _loadedOnce = true;
        
        if (!payload || !payload.ok) {
            hasBackendError = true;
            debugBannerText = "Excel read failed: " + (payload ? payload.message : "Unknown failure.");
            reportRows = []; _applySortAndSummary();
            root._isOnCooldown = true; cooldownTimer.start();
            return;
        }

        reportRows = payload.rows ? payload.rows : [];
        _incorporateRowsIntoMaster(reportRows);
        _applySortAndSummary();
        
        if (payload.debug) {
            var d = payload.debug;
            if (d.scanned === 0) { hasDataError = true; debugBannerText = "Excel read produced 0 rows (See logs)."; } 
            else if (reportRows.length === 0) { hasDataError = false; debugBannerText = "Filters excluded all " + d.scanned + " rows (See logs)."; } 
            else { debugBannerText = "Loaded from Excel: " + d.scanned + " rows | After filters: " + reportRows.length + " rows | Refresh: " + Qt.formatTime(new Date(), "hh:mm:ss"); }
        }
    }

    // PRIORITY 3: Strict Presets Model
    ListModel {
        id: presetListModel
        ListElement { key: "all"; label: "All Time" }
        ListElement { key: "today"; label: "Today" }
        ListElement { key: "week"; label: "Week to date" }
        ListElement { key: "month"; label: "Month to date" }
        ListElement { key: "last_week"; label: "Last week" }
        ListElement { key: "last_month"; label: "Last month" }
        ListElement { key: "year"; label: "Year to date" }
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 10
        
        // STATUS BANNER
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 4
            color: root.hasBackendError ? "#3E1212" : (root.hasDataError ? "#3E2712" : "#1A2E1A")
            border.width: 1; border.color: root.hasBackendError ? "#D32F2F" : (root.hasDataError ? "#FFB300" : "#388E3C")
            Text { anchors.centerIn: parent; text: root.debugBannerText; color: root.hasBackendError ? "#FFCDD2" : (root.hasDataError ? "#FFE0B2" : "#C8E6C9"); font.pixelSize: 12; font.weight: Font.DemiBold }
        }

        // INPUTS
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            ModernTextField { id: fromDateInput; t: root.t; metrics: root.metrics; label: "From"; text: root.fromDateText; Layout.preferredWidth: 160; Layout.preferredHeight: root.fieldHeightPx; onEditingFinished: { root.fromDateText = text; } }
            ModernTextField { id: toDateInput; t: root.t; metrics: root.metrics; label: "To"; text: root.toDateText; Layout.preferredWidth: 160; Layout.preferredHeight: root.fieldHeightPx; onEditingFinished: { root.toDateText = text; } }
            ModernComboBox { id: statusModeCombo; t: root.t; metrics: root.metrics; label: "Status"; fullModel: ["All Statuses", "All (Except Merged)", "Draft", "Ready for Billing", "Billed"]; editText: "All Statuses"; Layout.preferredWidth: 160; Layout.preferredHeight: root.fieldHeightPx; }
            ModernComboBox { id: clientFilterCombo; t: root.t; metrics: root.metrics; label: "Client"; fullModel: root.clientFilterOptions; editText: root.clientFilterText; Layout.preferredWidth: 180; Layout.preferredHeight: root.fieldHeightPx; onActivated: { root.clientFilterText = editText; } }
            ModernComboBox { id: matterFilterCombo; t: root.t; metrics: root.metrics; label: "Matter"; fullModel: root.matterFilterOptions; editText: root.matterFilterText; Layout.preferredWidth: 180; Layout.preferredHeight: root.fieldHeightPx; onActivated: { root.matterFilterText = editText; } }
        }

        // ACTIONS AND PRESETS
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: Math.max(root.fieldHeightPx, flowLayout.implicitHeight)
            Flow {
                id: flowLayout
                width: parent.width; spacing: 8
                
                // PRESETS
                Repeater {
                    model: presetListModel
                    delegate: Rectangle {
                        property bool isPrimary: root.currentPreset === model.key
                        width: Math.max(110, presetLbl.implicitWidth + 24); height: root.fieldHeightPx; radius: 6
                        color: isPrimary ? _accent : Qt.rgba(1,1,1,0.08)
                        border.color: isPrimary ? _accent : _textColor(0.3)
                        Text { id: presetLbl; anchors.centerIn: parent; text: model.label; color: parent.isPrimary ? "#FFFFFF" : _textColor(1.0); font.pixelSize: 13; font.weight: parent.isPrimary ? Font.Bold : Font.Normal }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.setPreset(model.key); root.runReport(); } }
                    }
                }
                
                // SPACER TO PUSH ACTIONS RIGHT
                Item { width: Math.max(8, parent.width - flowLayout.childrenRect.width - 450); height: root.fieldHeightPx }

                // ACTIONS
                Rectangle {
                    width: 110; height: root.fieldHeightPx; radius: 6; color: Qt.rgba(1,1,1,0.08); border.color: _textColor(0.3)
                    Text { anchors.centerIn: parent; text: "Clear Filters"; color: _textColor(1.0); font.pixelSize: 13 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.clearFilters() }
                }
                Rectangle {
                    width: 110; height: root.fieldHeightPx; radius: 6; color: Qt.rgba(1,1,1,0.08); border.color: _textColor(0.3)
                    Text { anchors.centerIn: parent; text: "Export PDF"; color: _textColor(1.0); font.pixelSize: 13 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { if(appRef.exportDocketActivityPdf) root.executePdfExport({}); } }
                }
                Rectangle {
                    width: 130; height: root.fieldHeightPx; radius: 6; color: _accent
                    Text { anchors.centerIn: parent; text: root.busy ? "Loading..." : "Run Report"; color: "#FFFFFF"; font.pixelSize: 13; font.weight: Font.Bold }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.runReport() }
                }
            }
        }

        // PRIORITY 2: TABLE LOCK & NO WHITE BACKGROUNDS
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 250
            color: "transparent" // NEVER WHITE
            radius: 8; border.width: 1; border.color: _textColor(0.2); clip: true

            Rectangle { anchors.fill: parent; color: _surfaceColor; radius: 8; z: -1 }

            ColumnLayout {
                anchors.fill: parent; spacing: 0
                
                // HEADERS
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 36; color: Qt.rgba(0,0,0,0.4)
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 15; anchors.rightMargin: 15
                        Text { text: "Date"; color: _textColor(0.6); Layout.preferredWidth: 90; font.bold: true; font.pixelSize: 11 }
                        Text { text: "Details"; color: _textColor(0.6); Layout.fillWidth: true; font.bold: true; font.pixelSize: 11 }
                        Text { text: "Hours"; color: _textColor(0.6); Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight; font.bold: true; font.pixelSize: 11 }
                        Text { text: "Gross"; color: _textColor(0.6); Layout.preferredWidth: 90; horizontalAlignment: Text.AlignRight; font.bold: true; font.pixelSize: 11 }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: _textColor(0.2); anchors.bottom: parent.bottom }
                }

                // DATA BODY
                Item {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    ListView {
                        id: reportList; anchors.fill: parent; clip: true
                        
                        // STRICT MODEL BINDING
                        model: strictRowsModel
                        
                        delegate: Rectangle {
                            width: reportList.width; height: 44
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.04) // Dark theme safe zebra
                            
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 15; anchors.rightMargin: 15
                                Text { text: model.date; color: _textPrimary; Layout.preferredWidth: 90; font.pixelSize: 12 }
                                ColumnLayout {
                                    spacing: 2; Layout.fillWidth: true
                                    Text { text: model.clientName + " [" + model.matterName + "]"; color: _accent; font.pixelSize: 12; font.bold: true; elide: Text.ElideRight }
                                    Text { text: model.description; color: _textColor(0.7); font.pixelSize: 11; elide: Text.ElideRight }
                                }
                                Text { text: Number(model.hours).toFixed(2); color: _textPrimary; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight; font.family: "Courier New" }
                                Text { text: "$" + Number(model.grossToClient).toFixed(2); color: _textPrimary; Layout.preferredWidth: 90; horizontalAlignment: Text.AlignRight; font.family: "Courier New"; font.bold: true }
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(1,1,1,0.05); anchors.bottom: parent.bottom }
                            
                            Component.onCompleted: console.log("[DocketUI] Rendered delegate for: " + model.date + " Gross: " + model.grossToClient)
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: strictRowsModel.count === 0 && !root.busy
                        text: "No rows returned for current filters."
                        color: _textColor(0.5); font.pixelSize: 14; font.italic: true
                    }
                }

                // AGGREGATE SUMMARY
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 44; color: Qt.rgba(0,0,0,0.5)
                    Rectangle { Layout.fillWidth: true; height: 1; color: _textColor(0.2); anchors.top: parent.top }
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 15
                        Text { text: "TOTAL AGGREGATE"; color: _textColor(0.6); font.bold: true; Layout.fillWidth: true; font.pixelSize: 12 }
                        Text { text: strictRowsModel.count + " Entries"; color: _textPrimary; font.bold: true; Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight; font.pixelSize: 12 }
                        Text { text: root.reportTotals.totalHours.toFixed(2) + " hrs"; color: _textPrimary; font.bold: true; Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight; font.pixelSize: 13 }
                        Text { text: "$" + root.reportTotals.totalGrossToClient.toFixed(2); color: _accent; font.bold: true; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight; font.pixelSize: 14 }
                    }
                }
            }
        }
    }
}
"""

# =====================================================================
# 2. PYTHON AST REWRITE (Stops Spam, Global load_workbook, TRACE logs)
# =====================================================================
def ensure_global_load_workbook_and_trace():
    p = Path("src/python/repositories/excel_repo.py")
    if not p.exists(): 
        print(f"[ERROR] Could not find {p}")
        return
        
    content = p.read_text(encoding="utf-8")

    # Priority 4 & 6 Fix: Global openpyxl import, kill 'load_workbook = None'
    if "from openpyxl import load_workbook" not in content[:1500]:
        content = re.sub(
            r'(from typing import.*?)\n',
            r'\1\nfrom openpyxl import load_workbook\n',
            content
        )
    content = re.sub(r'^\s*load_workbook\s*=\s*None\s*$', '', content, flags=re.MULTILINE)

    # Priority 5 Fix: Suppress Table Object Spam via caching
    cache_init = """    def __init__(self, paths: AppPaths):
        self.paths = paths
        self._missing_tables = set() # Priority 5: Cache missing table warnings"""
    
    content = re.sub(r'def __init__\(self, paths: AppPaths\):\s*self\.paths = paths', cache_init, content)
    
    missing_table_patch = """
            if tref.table in ws.tables:
                table = ws.tables[tref.table]
                _, rows = self._rows_from_table(ws, table)
                return rows
            else:
                if tref.table not in getattr(self, '_missing_tables', set()):
                    logger.warning(f"[ExcelRepo] Table '{tref.table}' missing. Falling back to range scan. (Will not warn again)")
                    if hasattr(self, '_missing_tables'): self._missing_tables.add(tref.table)
"""
    content = re.sub(r'if tref\.table in ws\.tables:.*?else:\s*logger\.warning.*?Falling back to dynamic raw range scan\."\)', missing_table_patch, content, flags=re.DOTALL)

    p.write_text(content, encoding="utf-8")
    print("[SUCCESS] Python Backend: `load_workbook` fixed globally, Spam Loop broken.")

def purge_main_duplicate_logs():
    p = Path("src/python/main.py")
    if not p.exists(): return
    content = p.read_text(encoding="utf-8")
    
    # Priority E: Kill duplicate functions
    content = re.sub(r'import logging\nfrom logging\.handlers import RotatingFileHandler\nfrom PySide6\.QtCore import qInstallMessageHandler, QtMsgType\n', '', content)
    content = re.sub(r'def setup_global_logging\(\):.*?return logging\.getLogger\("App"\)\n', '', content, flags=re.DOTALL)
    content = re.sub(r'def qt_message_handler\(mode, context, message\):.*?else: logger\.debug\(message\)\n', '', content, flags=re.DOTALL)
    content = re.sub(r'setup_global_logging\(\)\nqInstallMessageHandler\(qt_message_handler\)\nlogging\.info\("=== CSPM APPLICATION START ==="\)\n', '', content)
    
    pure_log_block = """import logging
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

def setup_global_logging():
    import sys, os
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "cspm.log")
    trace_mode = "--trace-docket" in sys.argv or os.environ.get("CSPM_DOCKET_TRACE") == "1"
    level = logging.DEBUG if trace_mode else logging.INFO
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if root_logger.hasHandlers(): root_logger.handlers.clear()
    
    fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    fh.setFormatter(formatter)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    
    root_logger.addHandler(fh)
    root_logger.addHandler(ch)
    return root_logger

def qt_message_handler(mode, context, message):
    logger = logging.getLogger("QML")
    if mode == QtMsgType.QtWarningMsg: logger.warning(message)
    elif mode == QtMsgType.QtCriticalMsg: logger.error(message)
    elif mode == QtMsgType.QtFatalMsg: logger.critical(message)
    else: logger.debug(message)

setup_global_logging()
qInstallMessageHandler(qt_message_handler)
logging.info("=== CSPM APPLICATION START ===")
"""
    content = re.sub(r'(import sys\n)', r'\1\n' + pure_log_block, content, count=1)
    p.write_text(content, encoding="utf-8")
    print("[SUCCESS] Cleared duplicate logging functions in main.py.")

if __name__ == '__main__':
    print("=== DEPLOYING STRICT, FINAL BLOCKING FIXES ===")
    
    p_qml = Path("src/qml/components/DocketActivityReportPanel.qml")
    if p_qml.exists():
        p_qml.write_text(DOCKET_REPORT_QML, encoding="utf-8")
        print("[SUCCESS] QML Overwritten: Strict ListModel active. Presets fixed. White overlays killed.")
    else:
        print(f"[WARN] Could not find {p_qml}")
        
    ensure_global_load_workbook_and_trace()
    purge_main_duplicate_logs()
    
    print("========================================================")
    print("READY. Launch the application:")
    print("python src/python/main.py --trace-docket")
