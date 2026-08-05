pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: root

    property var appRef
    property var t
    property var sfxBus
    property var reportWindows: ({})
    property var windowRef: null

    signal recordActionRouted(var action)
    signal reportRefreshRequested(string reportId, var sourceState)
    signal reportBrandingRequested(var initiatingWindow)

    function _safeText(value) {
        return String(value === undefined || value === null ? "" : value)
    }

    function _reportId(reportDocument) {
        var reportId = _safeText(reportDocument && reportDocument.reportId).trim()
        return reportId.length > 0 ? reportId : "report"
    }

    function activeReportWindow(reportId) {
        var key = _safeText(reportId).trim()
        if (key.length <= 0) return null
        return reportWindows && reportWindows[key] ? reportWindows[key] : null
    }

    function openReportWindow(reportDocument) {
        var doc = reportDocument || ({})
        var reportId = _reportId(doc)
        var win = activeReportWindow(reportId)
        if (!win) {
            win = reportWindowComponent.createObject(root, {
                "appRef": root.appRef,
                "t": root.t,
                "sfxBus": root.sfxBus,
                "managerRef": root,
                "parentWindow": root.windowRef
            })
            if (!win) return false
            var next = {}
            for (var key in reportWindows) {
                if (reportWindows.hasOwnProperty(key)) next[key] = reportWindows[key]
            }
            next[reportId] = win
            reportWindows = next
        }
        win.setReportDocument(doc)
        win.focusAndRaise()
        return true
    }

    function refreshReportWindow(reportId, reportDocument) {
        var key = _safeText(reportId).trim()
        var win = activeReportWindow(key)
        if (!win) return openReportWindow(reportDocument || ({ "reportId": key }))
        if (reportDocument) win.setReportDocument(reportDocument)
        win.focusAndRaise()
        return true
    }

    function routeReportRecordAction(action) {
        recordActionRouted(action || ({}))
    }

    function requestReportRefresh(reportId, sourceState) {
        reportRefreshRequested(_safeText(reportId), sourceState || ({}))
    }

    function requestReportBranding(initiatingWindow) {
        reportBrandingRequested(initiatingWindow)
    }

    function reloadAllActiveReportBranding() {
        for (var key in reportWindows) {
            if (reportWindows.hasOwnProperty(key) && reportWindows[key]) {
                try {
                    reportWindows[key].loadBrandingProfiles()
                } catch (e) {
                    console.log("[REPORT-MANAGER] reload branding failed for win=" + key + " err=" + e)
                }
            }
        }
    }

    Component {
        id: reportWindowComponent
        ReportWindow { }
    }
}
