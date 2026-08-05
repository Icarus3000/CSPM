pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: root
    width: 1460
    height: 860
    minimumWidth: 1320
    minimumHeight: 520
    visible: false
    color: SemanticTheme.surfaceApp(root.t, root.appStyle)
    title: _safeText(reportDocument.title).length > 0
        ? ("CSPM Report - " + _safeText(reportDocument.title))
        : "CSPM Report"

    property var appRef
    property var managerRef
    property var t
    property var sfxBus
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    property var reportDocument: ({})
    property real zoomScale: 1.0
    property string orientationMode: "portrait"
    property int currentPageIndex: 0
    property string findText: ""
    property string statusText: "Ready"
    property bool busy: false
    property var brandingProfiles: []
    property var brandingProfileNames: []
    property string selectedBrandingProfileId: ""
    property bool _loadingBrandingProfiles: false

    readonly property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color ruleColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property int portraitPageW: 816
    readonly property int portraitPageH: 1056
    readonly property int landscapePageW: 1056
    readonly property int landscapePageH: 816
    readonly property int pageW: orientationMode === "portrait" ? portraitPageW : landscapePageW
    readonly property int pageH: orientationMode === "portrait" ? portraitPageH : landscapePageH
    readonly property int detailRowsPerPage: orientationMode === "portrait" ? 15 : 10
    readonly property int summaryRowsPerPage: orientationMode === "portrait" ? 19 : 11
    readonly property int pageMargin: 42
    readonly property int footerHeight: 28
    property bool _hasUserOrientationChoice: false
    property var parentWindow: null
    property string reportId: _safeText(reportDocument && reportDocument.reportId).trim()
    readonly property bool isStatementReport: reportId === "statement_of_account"
    readonly property int reportTableTitleHeight: isStatementReport ? 22 : 24
    readonly property int reportTableHeaderHeight: isStatementReport ? 23 : 26
    readonly property int reportTableRowHeight: isStatementReport ? 24 : 30
    readonly property int reportTableTopMargin: isStatementReport ? 10 : 18

    onXChanged: {
        if (visible && reportId.length > 0 && appRef && appRef.saveReportWindowGeometry) {
            appRef.saveReportWindowGeometry(reportId, x, y, width, height)
        }
    }
    onYChanged: {
        if (visible && reportId.length > 0 && appRef && appRef.saveReportWindowGeometry) {
            appRef.saveReportWindowGeometry(reportId, x, y, width, height)
        }
    }
    onWidthChanged: {
        if (visible && reportId.length > 0 && appRef && appRef.saveReportWindowGeometry) {
            appRef.saveReportWindowGeometry(reportId, x, y, width, height)
        }
    }
    onHeightChanged: {
        if (visible && reportId.length > 0 && appRef && appRef.saveReportWindowGeometry) {
            appRef.saveReportWindowGeometry(reportId, x, y, width, height)
        }
    }

    onVisibleChanged: {
        if (visible) {
            root.applyDefaultGeometry()
            Qt.callLater(function() {
                root.showMaximized()
                root.fitWidth()
            })
        }
    }

    function applyDefaultGeometry() {
        var p = root.parentWindow
        if (p) {
            var sWidth = (p.screen && p.screen.width > 0) ? p.screen.width : 1600
            var sHeight = (p.screen && p.screen.height > 0) ? p.screen.height : 900
            root.width = Math.min(sWidth, Math.max(root.minimumWidth, p.width))
            root.height = Math.min(sHeight, Math.max(root.minimumHeight, p.height))
            root.x = p.x
            root.y = p.y
        }
    }

    signal recordActionRequested(var action)

    onClosing: function(close) {
        close.accepted = false
        root.hide()
    }

    Connections {
        target: root.appRef ? root.appRef : null
        ignoreUnknownSignals: true
        function onTransactionDataChanged() {
            root.requestRefresh()
        }
        function onClientDataChanged() {
            root.requestRefresh()
        }
    }

    function _safeText(value) {
        return String(value === undefined || value === null ? "" : value)
    }

    function _money(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        return "$" + n.toFixed(2)
    }

    function _hours(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        return n.toFixed(2)
    }

    function _fileUrl(pathText) {
        var normalized = _safeText(pathText).trim()
        if (normalized.length <= 0) return ""
        return "file:///" + encodeURI(normalized.replace(/\\/g, "/"))
    }

    function _logoSource() {
        var branding = reportDocument && reportDocument.branding ? reportDocument.branding : ({})
        var source = _safeText(branding.logoUrl || branding.logoSource || branding.logoPath).trim()
        return source.length > 0 ? source : ""
    }

    function _profileId(profile) {
        return _safeText(profile && (profile.id || profile.profileId)).trim()
    }

    function _profileIndexById(profileId) {
        var target = _safeText(profileId).trim()
        for (var i = 0; i < brandingProfiles.length; i++) {
            if (_profileId(brandingProfiles[i]) === target) return i
        }
        return -1
    }

    function _profileIdAt(index) {
        if (index < 0 || index >= brandingProfiles.length) return ""
        return _profileId(brandingProfiles[index])
    }

    function _selectedProfile() {
        var index = _profileIndexById(selectedBrandingProfileId)
        if (index >= 0) return brandingProfiles[index]
        return null
    }

    function _profileContact(profile) {
        if (!profile) return ""
        var lines = []
        var subtitle = _safeText(profile.subtitle || profile.firmSubtitle).trim()
        if (subtitle.length > 0) lines.push(subtitle)
        var address = profile.addressLines || []
        for (var i = 0; i < address.length; i++) {
            var line = _safeText(address[i]).trim()
            if (line.length > 0) lines.push(line)
        }
        var phone = _safeText(profile.phone).trim()
        var email = _safeText(profile.email).trim()
        if (phone.length > 0 && email.length > 0) {
            lines.push(phone + "  |  " + email)
        } else if (phone.length > 0) {
            lines.push(phone)
        } else if (email.length > 0) {
            lines.push(email)
        }
        return lines.join("\n")
    }

    function _profileBranding(profile) {
        var sourceProfile = profile || ({})
        return {
            "id": _profileId(sourceProfile),
            "profileId": _profileId(sourceProfile),
            "name": _safeText(sourceProfile.name),
            "firmName": _safeText(sourceProfile.firmName),
            "subtitle": _safeText(sourceProfile.subtitle || sourceProfile.firmSubtitle),
            "addressLines": sourceProfile.addressLines || [],
            "phone": _safeText(sourceProfile.phone),
            "email": _safeText(sourceProfile.email),
            "firmContact": _profileContact(sourceProfile),
            "logoPath": _safeText(sourceProfile.logoPath),
            "logoUrl": _safeText(sourceProfile.logoUrl || sourceProfile.logoSource),
            "logoSource": _safeText(sourceProfile.logoUrl || sourceProfile.logoSource)
        }
    }

    function _brandingProfileNames(profiles) {
        var names = []
        for (var i = 0; i < profiles.length; i++) {
            names.push(_safeText(profiles[i].name || profiles[i].firmName || ("Profile " + String(i + 1))))
        }
        return names
    }

    function _applySelectedBrandingProfile(persist) {
        var profile = _selectedProfile()
        if (!profile) return
        var doc = {}
        var current = reportDocument || ({})
        for (var key in current) {
            if (current.hasOwnProperty(key)) doc[key] = current[key]
        }
        doc.branding = _profileBranding(profile)
        reportDocument = doc
        if (persist && appRef && appRef.setLastReportBrandingProfile) {
            try {
                appRef.setLastReportBrandingProfile(selectedBrandingProfileId)
            } catch (e) {
                console.log("[REPORT] setLastReportBrandingProfile failed err=" + e)
            }
        }
    }

    function selectBrandingProfile(profileId, persist) {
        var target = _safeText(profileId).trim()
        if (target.length <= 0) return
        selectedBrandingProfileId = target
        _applySelectedBrandingProfile(persist === true)
    }

    function loadBrandingProfiles() {
        if (_loadingBrandingProfiles) return
        _loadingBrandingProfiles = true
        var selected = _safeText(reportDocument.branding && (reportDocument.branding.profileId || reportDocument.branding.id)).trim()
        try {
            if (appRef && appRef.getReportBrandingProfiles) {
                var result = appRef.getReportBrandingProfiles()
                var profiles = result && result.profiles ? result.profiles : []
                brandingProfiles = profiles
                brandingProfileNames = _brandingProfileNames(profiles)
                if (selected.length <= 0) selected = _safeText(result && result.lastProfileId).trim()
                if (selected.length <= 0 && profiles.length > 0) selected = _profileId(profiles[0])
                if (_profileIndexById(selected) < 0 && profiles.length > 0) selected = _profileId(profiles[0])
                selectedBrandingProfileId = selected
                _applySelectedBrandingProfile(false)
            } else {
                brandingProfiles = []
                brandingProfileNames = []
            }
        } catch (e) {
            console.log("[REPORT] getReportBrandingProfiles failed err=" + e)
        }
        _loadingBrandingProfiles = false
    }

    function _sectionById(sectionId) {
        var sections = reportDocument && reportDocument.sections ? reportDocument.sections : []
        for (var i = 0; i < sections.length; i++) {
            if (_safeText(sections[i].sectionId) === _safeText(sectionId)) return sections[i]
        }
        return ({ "columns": [], "rows": [] })
    }

    function _sectionTitle(sectionId, fallback) {
        var section = _sectionById(sectionId)
        var title = _safeText(section.title || section.label).trim()
        return title.length > 0 ? title : fallback
    }

    function _hasSection(sectionId) {
        var sections = reportDocument && reportDocument.sections ? reportDocument.sections : []
        for (var i = 0; i < sections.length; i++) {
            if (_safeText(sections[i].sectionId) === _safeText(sectionId)) return true
        }
        return false
    }

    function _rowMatches(row) {
        var needle = _safeText(findText).trim().toLowerCase()
        if (needle.length <= 0) return true
        var haystack = JSON.stringify(row || ({})).toLowerCase()
        return haystack.indexOf(needle) >= 0
    }

    function _detailRows() {
        var rows = _sectionById("detail").rows || []
        var out = []
        for (var i = 0; i < rows.length; i++) {
            if (_rowMatches(rows[i])) out.push(rows[i])
        }
        return out
    }

    function _headerRows() {
        return _sectionById("header").rows || []
    }

    function _summaryRows() {
        return _sectionById("summary").rows || []
    }

    function _aggregateRows() {
        return _sectionById("aggregate").rows || []
    }

    function pageDocuments() {
        var rows = _detailRows()
        var summaryRows = _summaryRows()
        var perPage = Math.max(1, detailRowsPerPage)
        var summaryPerPage = Math.max(1, summaryRowsPerPage)
        var hasSummarySection = _hasSection("summary")
        var hasAggregateSection = _hasSection("aggregate")
        var hasHeaderSection = _hasSection("header")
        var pages = []
        if (rows.length > 0 || (!hasSummarySection && !hasAggregateSection)) {
            for (var i = 0; i < Math.max(1, rows.length); i += perPage) {
                pages.push({
                    "pageIndex": pages.length,
                    "rows": rows.slice(i, Math.min(i + perPage, rows.length)),
                    "includeDetail": true,
                    "summaryRows": [],
                    "includeSummary": false,
                    "includeAggregate": false
                })
            }
        }
        if (hasSummarySection && summaryRows.length > 0) {
            for (var s = 0; s < summaryRows.length; s += summaryPerPage) {
                pages.push({
                    "pageIndex": pages.length,
                    "rows": [],
                    "includeDetail": false,
                    "summaryRows": summaryRows.slice(s, Math.min(s + summaryPerPage, summaryRows.length)),
                    "includeSummary": true,
                    "includeAggregate": false
                })
            }
            if (hasAggregateSection) {
                pages[pages.length - 1].includeAggregate = true
            }
        } else if (hasSummarySection || hasAggregateSection) {
            pages.push({
                "pageIndex": pages.length,
                "rows": [],
                "includeDetail": false,
                "summaryRows": [],
                "includeSummary": hasSummarySection,
                "includeAggregate": hasAggregateSection
            })
        }
        for (var p = 0; p < pages.length; p++) {
            pages[p].pageIndex = p
            pages[p].pageCount = pages.length
            if (p === 0 && hasHeaderSection) pages[p].includeHeader = true
            else pages[p].includeHeader = false
            if (pages[p].includeAggregate === undefined) pages[p].includeAggregate = false
        }
        return pages
    }

    function setReportDocument(nextDocument) {
        var previousReportId = _safeText(reportDocument && reportDocument.reportId)
        reportDocument = nextDocument || ({})
        var nextOrientation = _safeText(reportDocument.orientation).toLowerCase()
        var nextReportId = _safeText(reportDocument && reportDocument.reportId)
        if (!_hasUserOrientationChoice || previousReportId !== nextReportId) {
            orientationMode = "portrait"
        }
        currentPageIndex = 0
        loadBrandingProfiles()
        statusText = "Loaded " + _safeText(reportDocument.title || "report")
    }

    function setOrientation(mode, userSelected) {
        var normalized = _safeText(mode).toLowerCase() === "portrait" ? "portrait" : "landscape"
        orientationMode = normalized
        if (userSelected) _hasUserOrientationChoice = true
        if (reportDocument) reportDocument.orientation = normalized
        root.gotoPage(0)
    }

    function focusAndRaise() {
        applyDefaultGeometry()
        showMaximized()
        raise()
        requestActivate()
        Qt.callLater(function() {
            root.fitWidth()
        })
    }

    function clampZoom(value) {
        return Math.max(0.35, Math.min(2.6, Number(value)))
    }

    function setZoom(value) {
        zoomScale = clampZoom(value)
    }

    function resetZoom() {
        setZoom(1.0)
    }

    function applyWheelZoom(wheel) {
        if (wheel.modifiers & Qt.ControlModifier) {
            if (wheel.angleDelta.y > 0) {
                setZoom(zoomScale + 0.05)
            } else {
                setZoom(zoomScale - 0.05)
            }
            return true
        }
        return false
    }

    function fitWidth() {
        var available = Math.max(1, pageList.width - 48)
        setZoom(available / pageW)
    }

    function gotoPage(index) {
        var pages = pageDocuments()
        if (pages.length <= 0) return
        currentPageIndex = Math.max(0, Math.min(pages.length - 1, Math.round(index)))
        pageList.positionViewAtIndex(currentPageIndex, ListView.Beginning)
    }

    function _exportPayload() {
        var basePayload = reportDocument.exportPayload || ({})
        var exportPayload = {}
        for (var key in basePayload) {
            if (basePayload.hasOwnProperty(key)) exportPayload[key] = basePayload[key]
        }
        var config = {}
        var baseConfig = basePayload.config || ({})
        for (var configKey in baseConfig) {
            if (baseConfig.hasOwnProperty(configKey)) config[configKey] = baseConfig[configKey]
        }
        config.orientation = orientationMode
        var profile = _selectedProfile()
        if (profile) {
            var branding = _profileBranding(profile)
            config.brandingProfileId = branding.id
            config.brandingProfile = branding
            config.firmName = branding.firmName
            config.firmContact = branding.firmContact
            config.logoPath = branding.logoPath
            exportPayload.brandingProfileId = branding.id
        }
        exportPayload.title = _safeText(reportDocument.title)
        exportPayload.filterSummary = _safeText(reportDocument.filterSummary)
        config.title = _safeText(reportDocument.title)
        config.filterSummary = _safeText(reportDocument.filterSummary)
        exportPayload.sections = reportDocument.sections
        exportPayload.config = config
        return {
            "reportId": _safeText(reportDocument.reportId),
            "brandingProfileId": profile ? _profileId(profile) : "",
            "exportPayload": exportPayload
        }
    }

    function savePdf(openAfterSave) {
        if (!appRef) {
            statusText = "Report backend unavailable."
            return
        }
        busy = true
        var result = null
        try {
            if (appRef.saveReportPdf) result = appRef.saveReportPdf(_exportPayload())
            else if (appRef.exportDocketActivityPdf) result = appRef.exportDocketActivityPdf(reportDocument.exportPayload || ({}))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        busy = false
        if (result && result.ok) {
            statusText = result.message ? String(result.message) : "PDF saved."
            if (openAfterSave) Qt.openUrlExternally(_fileUrl(result.path))
        } else {
            statusText = "PDF failed: " + (result && result.message ? String(result.message) : "Unknown error")
        }
    }

    function exportCsv() {
        if (!appRef) {
            statusText = "Report backend unavailable."
            return
        }
        busy = true
        var result = null
        try {
            if (appRef.exportReportCsv) result = appRef.exportReportCsv(_exportPayload())
            else if (appRef.exportDocketActivityCsv) result = appRef.exportDocketActivityCsv(reportDocument.exportPayload || ({}))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        busy = false
        statusText = (result && result.ok)
            ? (result.message ? String(result.message) : "CSV exported.")
            : ("CSV failed: " + (result && result.message ? String(result.message) : "Unknown error"))
    }

    function printReport() {
        savePdf(true)
        if (statusText.indexOf("PDF failed:") < 0) {
            statusText = "Print-ready PDF opened."
        }
    }

    function copyReportText() {
        var text = []
        text.push(_safeText(reportDocument.title))
        text.push("Generated\t" + _safeText(reportDocument.generatedAt))
        var profile = _selectedProfile()
        if (profile) text.push("Profile\t" + _safeText(profile.name))
        var detail = _sectionById("detail")
        var columns = detail.columns || []
        var rows = _detailRows()
        var headings = []
        for (var h = 0; h < columns.length; h++) headings.push(_safeText(columns[h].label))
        text.push(headings.join("\t"))
        for (var r = 0; r < rows.length; r++) {
            var cells = []
            for (var c = 0; c < columns.length; c++) {
                cells.push(_safeText(rows[r][columns[c].key]))
            }
            text.push(cells.join("\t"))
        }
        if (appRef && appRef.copyTextToClipboard && appRef.copyTextToClipboard(text.join("\n"))) {
            statusText = "Report copied."
        } else {
            statusText = "Copy unavailable."
        }
    }

    function requestRefresh() {
        statusText = "Refresh requested."
        if (managerRef && managerRef.requestReportRefresh) {
            managerRef.requestReportRefresh(_safeText(reportDocument.reportId), reportDocument.sourceState || ({}))
        }
    }

    function openRow(row) {
        var action = row && row.openAction ? row.openAction : null
        if (!action) return
        root.recordActionRequested(action)
        if (managerRef && managerRef.routeReportRecordAction) {
            managerRef.routeReportRecordAction(action)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
            border.width: 1
            border.color: root.ruleColor

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 6

                Button { text: "-"; Layout.preferredWidth: 34; onClicked: root.setZoom(root.zoomScale - 0.1) }
                Text { text: Math.round(root.zoomScale * 100) + "%"; color: root.ink; Layout.preferredWidth: 46; horizontalAlignment: Text.AlignHCenter }
                Button { text: "+"; Layout.preferredWidth: 34; onClicked: root.setZoom(root.zoomScale + 0.1) }
                Button { text: "100%"; Layout.preferredWidth: 54; onClicked: root.resetZoom() }
                Button { text: "Fit"; Layout.preferredWidth: 46; onClicked: root.fitWidth() }
                Button { text: "<"; Layout.preferredWidth: 34; onClicked: root.gotoPage(root.currentPageIndex - 1) }
                Text {
                    text: String(root.currentPageIndex + 1) + " / " + String(Math.max(1, root.pageDocuments().length))
                    color: root.ink
                    Layout.preferredWidth: 56
                    horizontalAlignment: Text.AlignHCenter
                }
                Button { text: ">"; Layout.preferredWidth: 34; onClicked: root.gotoPage(root.currentPageIndex + 1) }
                Text {
                    text: "Format"
                    color: root.ink
                    Layout.preferredWidth: 48
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 11
                }
                ComboBox {
                    id: orientationCombo
                    Layout.preferredWidth: 112
                    model: ["Landscape", "Portrait"]
                    currentIndex: root.orientationMode === "portrait" ? 1 : 0
                    onActivated: {
                        root.setOrientation(currentIndex === 1 ? "portrait" : "landscape", true)
                    }
                }
                Text {
                    text: "Profile"
                    color: root.ink
                    Layout.preferredWidth: 46
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 11
                    visible: root.brandingProfileNames.length > 0
                }
                ComboBox {
                    id: profileCombo
                    Layout.preferredWidth: 180
                    model: root.brandingProfileNames
                    currentIndex: root._profileIndexById(root.selectedBrandingProfileId)
                    visible: root.brandingProfileNames.length > 0
                    onActivated: function(index) {
                        root.selectBrandingProfile(root._profileIdAt(index), true)
                    }
                }
                TextField {
                    id: findField
                    Layout.preferredWidth: 136
                    placeholderText: "Find"
                    text: root.findText
                    onTextChanged: {
                        root.findText = text
                        root.gotoPage(0)
                    }
                }
                Button { text: "Copy"; Layout.preferredWidth: 58; onClicked: root.copyReportText() }
                Button { text: "Refresh"; Layout.preferredWidth: 76; onClicked: root.requestRefresh() }
                Button { text: "Save"; Layout.preferredWidth: 58; onClicked: root.savePdf(false) }
                Button { text: "CSV"; Layout.preferredWidth: 52; onClicked: root.exportCsv() }
                Button { text: "Print"; Layout.preferredWidth: 58; onClicked: root.printReport() }
                Item { Layout.fillWidth: true }
                Button { text: "Close"; Layout.preferredWidth: 64; onClicked: root.close() }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            Text {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: Text.AlignVCenter
                text: root.statusText
                color: root.mutedInk
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }

        ListView {
            id: pageList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 18
            model: root.pageDocuments()
            onCurrentIndexChanged: root.currentPageIndex = currentIndex

            WheelHandler {
                acceptedModifiers: Qt.ControlModifier
                onWheel: function(wheel) {
                    wheel.accepted = root.applyWheelZoom(wheel)
                }
            }

            delegate: Item {
                id: pageDelegate
                required property var modelData
                property var pageData: modelData
                width: pageList.width
                height: (root.pageH * root.zoomScale) + 22

                Rectangle {
                    id: pageSurface
                    width: root.pageW * root.zoomScale
                    height: root.pageH * root.zoomScale
                    x: Math.max(8, (parent.width - width) / 2)
                    y: 10
                    color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                    border.width: 1
                    border.color: SemanticTheme.borderStrong(root.t, root.appStyle)

                    Item {
                        id: pageContent
                        width: root.pageW
                        height: root.pageH
                        scale: root.zoomScale
                        transformOrigin: Item.TopLeft

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: root.pageMargin
                            color: "transparent"

                            Item {
                                id: brandBlock
                                anchors.left: parent.left
                                anchors.right: generatedStamp.left
                                anchors.top: parent.top
                                anchors.rightMargin: 16
                                height: (firmContact.text && firmContact.text.trim().length > 0) ? (firmContact.y + firmContact.height) : (firmName.y + firmName.height)

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.managerRef && root.managerRef.requestReportBranding) {
                                            root.managerRef.requestReportBranding(root);
                                        }
                                    }
                                }

                                Image {
                                    id: reportLogo
                                    anchors.left: parent.left
                                    anchors.top: firmContact.top
                                    anchors.topMargin: -4
                                    anchors.bottom: firmContact.bottom
                                    anchors.bottomMargin: -4
                                    width: height
                                    source: root._logoSource()
                                    visible: root._logoSource().length > 0
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                    mipmap: true
                                }

                                Text {
                                    id: firmName
                                    text: root._safeText(root.reportDocument.branding && root.reportDocument.branding.firmName)
                                        || "Cory Schneider Law Office"
                                    anchors.left: reportLogo.visible ? reportLogo.right : parent.left
                                    anchors.leftMargin: reportLogo.visible ? 16 : 0
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.topMargin: 0
                                    color: root.ink
                                    font.pixelSize: 20
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: firmContact
                                    text: root._safeText(root.reportDocument.branding && root.reportDocument.branding.firmContact)
                                    anchors.left: reportLogo.visible ? reportLogo.right : parent.left
                                    anchors.leftMargin: reportLogo.visible ? 16 : 0
                                    anchors.right: parent.right
                                    anchors.top: firmName.bottom
                                    anchors.topMargin: 6
                                    color: root.mutedInk
                                    font.pixelSize: 10
                                    lineHeight: 1.15
                                    maximumLineCount: 6
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                    clip: true
                                }
                            }

                            Text {
                                id: generatedStamp
                                text: "Generated: " + root._safeText(root.reportDocument.generatedAt)
                                anchors.right: parent.right
                                anchors.top: parent.top
                                color: root.mutedInk
                                font.pixelSize: 10
                            }
                            Text {
                                text: "Page " + String(pageDelegate.pageData.pageIndex + 1) + " of " + String(pageDelegate.pageData.pageCount)
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.topMargin: 16
                                color: root.mutedInk
                                font.pixelSize: 10
                            }
                            Rectangle {
                                id: headerRule
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: brandBlock.bottom
                                anchors.topMargin: 12
                                height: 1
                                color: root.ruleColor
                            }
                            Text {
                                id: reportTitle
                                text: root._safeText(root.reportDocument.title)
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: headerRule.bottom
                                anchors.topMargin: 12
                                horizontalAlignment: Text.AlignHCenter
                                color: root.ink
                                font.pixelSize: 21
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                id: filterLine
                                text: root._safeText(root.reportDocument.filterSummary)
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: reportTitle.bottom
                                anchors.topMargin: 7
                                horizontalAlignment: Text.AlignHCenter
                                color: root.mutedInk
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }

                            Item {
                                id: footerBlock
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: root.footerHeight

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    height: 1
                                    color: root.ruleColor
                                }

                                Text {
                                    text: "Confidential - For client use only"
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 2
                                    horizontalAlignment: Text.AlignHCenter
                                    color: root.mutedInk
                                    font.pixelSize: 9
                                    elide: Text.ElideRight
                                }
                            }

                            ReportPageTable {
                                id: headerTable
                                t: root.t
                                appStyle: root.appStyle
                                ink: root.ink
                                mutedInk: root.mutedInk
                                ruleColor: root.ruleColor
                                visible: !!pageDelegate.pageData.includeHeader
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: filterLine.bottom
                                anchors.topMargin: root.reportTableTopMargin
                                title: root._sectionTitle("header", "")
                                titleHeight: root.reportTableTitleHeight
                                headerHeight: root.reportTableHeaderHeight
                                rowHeight: root.reportTableRowHeight
                                columns: root._sectionById("header").columns || []
                                rows: root._headerRows()
                                emptyText: ""
                            }

                            ReportPageTable {
                                id: detailTable
                                t: root.t
                                appStyle: root.appStyle
                                ink: root.ink
                                mutedInk: root.mutedInk
                                ruleColor: root.ruleColor
                                visible: pageDelegate.pageData.includeDetail !== false
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: headerTable.visible ? headerTable.bottom : filterLine.bottom
                                anchors.topMargin: root.reportTableTopMargin
                                title: root._sectionTitle("detail", "Detail")
                                titleHeight: root.reportTableTitleHeight
                                headerHeight: root.reportTableHeaderHeight
                                rowHeight: root.reportTableRowHeight
                                columns: root._sectionById("detail").columns || []
                                rows: pageDelegate.pageData.rows || []
                                emptyText: "No detail rows returned."
                                onRowClicked: function(row) { root.openRow(row) }
                                onRowDoubleClicked: function(row) { root.openRow(row) }
                            }

                            ReportPageTable {
                                id: summaryTable
                                t: root.t
                                appStyle: root.appStyle
                                ink: root.ink
                                mutedInk: root.mutedInk
                                ruleColor: root.ruleColor
                                visible: !!pageDelegate.pageData.includeSummary
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: detailTable.visible ? detailTable.bottom : filterLine.bottom
                                anchors.topMargin: root.reportTableTopMargin
                                title: root._sectionTitle("summary", "Summary")
                                titleHeight: root.reportTableTitleHeight
                                headerHeight: root.reportTableHeaderHeight
                                rowHeight: root.reportTableRowHeight
                                columns: root._sectionById("summary").columns || []
                                rows: pageDelegate.pageData.summaryRows || []
                                emptyText: "No summary rows returned."
                            }

                            ReportPageTable {
                                id: aggregateTable
                                t: root.t
                                appStyle: root.appStyle
                                ink: root.ink
                                mutedInk: root.mutedInk
                                ruleColor: root.ruleColor
                                visible: !!pageDelegate.pageData.includeAggregate
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: summaryTable.visible ? summaryTable.bottom : (detailTable.visible ? detailTable.bottom : filterLine.bottom)
                                anchors.topMargin: root.isStatementReport ? 10 : 14
                                title: root._sectionTitle("aggregate", "Aggregate")
                                titleHeight: root.reportTableTitleHeight
                                headerHeight: root.reportTableHeaderHeight
                                rowHeight: root.reportTableRowHeight
                                columns: root._sectionById("aggregate").columns || []
                                rows: root._aggregateRows()
                                emptyText: "No aggregate rows returned."
                            }
                        }
                    }
                }
            }
        }
    }
}
