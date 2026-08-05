import QtQuick
import QtQuick.Layouts
import "../components"
import "../standards"
import "../standards/ExternalLinkRules.js" as ExternalLinks
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property var metrics
    property var t

    property color _accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color _text: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color _panel: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color _bg: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: visualRules.isPro
    property color proBackground: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color proCanvas: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color proSurface: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color proControl: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color proActiveBorder: SemanticTheme.borderStrong(root.t, root.appStyle)
    property color proInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color proMutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)

    property bool dirty: false
    property string directoryQuery: ""
    property var directoryRows: []
    property int selectedDirectoryIndex: -1
    property string selectedTrademarkId: ""

    property var formFieldMetrics: ({
        "contentW": (metrics && typeof metrics.contentW === "number" && metrics.contentW > 0) ? metrics.contentW : width,
        "contentH": (metrics && typeof metrics.contentH === "number" && metrics.contentH > 0) ? metrics.contentH : height,
        "fontFloorBodyPx": 15,
        "fontFloorLabelPx": 14,
        "fontFloorTitlePx": 16
    })
    property var pillScaleRatios: ({
        "contentSpacingPct": 0.012,
        "iconSizePct": 0.020,
        "textSizePct": 0.020,
        "secondaryBorderPct": 0.0022,
        "shadowRadiusPct": 0.0085,
        "shadowSamplesPct": 0.018,
        "shadowYOffsetPct": 0.0022
    })

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    signal moduleJumpRequested(int tileIndex, var state)
    signal editTrademarkRequested(var row)
    signal createTrademarkRequested()
    signal reportWindowRequested(var reportDocument)

    function _clean(v) {
        return String(v === undefined || v === null ? "" : v).trim()
    }

    function areaUnit() {
        var w = (metrics && typeof metrics.contentW === "number" && metrics.contentW > 0) ? metrics.contentW : width
        var h = (metrics && typeof metrics.contentH === "number" && metrics.contentH > 0) ? metrics.contentH : height
        return Math.sqrt(Math.max(1, w) * Math.max(1, h))
    }

    function ratioPx(ratio, minPx) {
        return Math.max(minPx || 1, Math.round(areaUnit() * ratio))
    }

    property int fieldHeightPx: ratioPx(0.032, 40)
    property int sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : ratioPx(0.010, 10)

    function selectedRow() {
        if (!directoryRows || directoryRows.length === undefined) return null
        if (selectedDirectoryIndex < 0 || selectedDirectoryIndex >= directoryRows.length) return null
        return directoryRows[selectedDirectoryIndex]
    }

    function refreshDirectory() {
        if (!appRef || !appRef.listTrademarkDirectory) {
            directoryRows = []
            selectedDirectoryIndex = -1
            selectedTrademarkId = ""
            return
        }
        var rows = []
        try {
            rows = appRef.listTrademarkDirectory(directoryQuery)
        } catch (e) {
            rows = []
        }
        if (!rows || rows.length === undefined) rows = []
        directoryRows = rows

        var wantedId = _clean(selectedTrademarkId)
        var nextIndex = -1
        if (wantedId.length > 0) {
            for (var i = 0; i < directoryRows.length; i++) {
                if (_clean(directoryRows[i].trademarkId).toLowerCase() === wantedId.toLowerCase()) {
                    nextIndex = i
                    break
                }
            }
        }
        if (nextIndex < 0 && directoryRows.length > 0) nextIndex = Math.min(selectedDirectoryIndex, directoryRows.length - 1)
        if (nextIndex < 0 && directoryRows.length > 0) nextIndex = 0

        selectedDirectoryIndex = nextIndex
        var selected = selectedRow()
        selectedTrademarkId = selected ? _clean(selected.trademarkId) : ""
    }

    function selectIndex(index) {
        if (!directoryRows || directoryRows.length === undefined) return
        if (index < 0 || index >= directoryRows.length) return
        selectedDirectoryIndex = index
        selectedTrademarkId = _clean(directoryRows[index].trademarkId)
    }

    function openExternalUrl(url) {
        var target = _clean(url)
        if (target.length <= 0) return
        if (ExternalLinks.shouldOpenInEdge(target) && root.appRef && root.appRef.openUrlInEdge) {
            if (root.appRef.openUrlInEdge(target)) return
        }
        Qt.openUrlExternally(target)
    }

    function openSelectedRegistryLink() {
        var row = selectedRow()
        if (!row) return
        var url = ExternalLinks.openableTrademarkRegistryUrl(
            row.jurisdiction,
            row.applicationNumber,
            row.registrationNumber,
            row.trademarkText || row.title,
            row.registryLink
        )
        if (_clean(url).length <= 0) return
        openExternalUrl(url)
    }

    function openSelectedForEdit() {
        var row = selectedRow()
        if (!row) return
        editTrademarkRequested(row)
    }

    function snapshotState() {
        return {
            "directoryQuery": directoryQuery,
            "selectedDirectoryIndex": selectedDirectoryIndex,
            "selectedTrademarkId": selectedTrademarkId,
            "dirty": false
        }
    }

    function applyInitialState(state) {
        if (!state) return
        directoryQuery = _clean(state.directoryQuery)
        selectedDirectoryIndex = Math.max(-1, Math.floor(state.selectedDirectoryIndex || -1))
        selectedTrademarkId = _clean(state.selectedTrademarkId)
        refreshDirectory()
        dirty = false
    }

    Timer {
        id: searchDebounce
        interval: 220
        repeat: false
        onTriggered: root.refreshDirectory()
    }

    Component.onCompleted: refreshDirectory()

    Rectangle {
        anchors.fill: parent
        visible: !root.isProMode
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(root._bg.r, root._bg.g, root._bg.b, 0.95) }
            GradientStop { position: 1.0; color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.82) }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.isProMode
        color: SemanticTheme.surfaceApp(root.t, root.appStyle)
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 14
        radius: root.sectionRadiusPx
        color: root.isProMode ? root.proCanvas : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.78)
        border.width: 1
        border.color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    text: "\uEA18"
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 18
                    color: root.isProMode ? SemanticTheme.accentPrimary(root.t, root.appStyle) : root._accent
                }
                Text {
                    Layout.fillWidth: true
                    text: "Trademark Directory"
                    color: root.isProMode ? root.proInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.95)
                    font.pixelSize: 18
                    font.family: "Segoe UI"
                    font.weight: Font.DemiBold
                }
                Text {
                    text: String(root.directoryRows.length) + " results"
                    color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.78)
                    font.pixelSize: 11
                    font.family: "Segoe UI"
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                ModernTextField {
                    id: searchInput
                    t: root.t
                    metrics: root.formFieldMetrics
                    label: "Search trademarks"
                    text: root.directoryQuery
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.fieldHeightPx
                    onTextChanged: {
                        root.directoryQuery = text
                        searchDebounce.restart()
                    }
                    onAccepted: root.refreshDirectory()
                }
                PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Search"; primary: true; Layout.preferredWidth: 110; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.refreshDirectory() }
                PillButton {
                    t: root.t
                    metrics: root.formFieldMetrics
                    scaleRatios: root.pillScaleRatios
                    text: "Clear"
                    primary: false
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: root.fieldHeightPx * 1.04
                    onClicked: {
                        root.directoryQuery = ""
                        searchInput.text = ""
                        root.refreshDirectory()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "New Entry"; primary: true; Layout.preferredWidth: 130; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.createTrademarkRequested() }
                PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Edit"; primary: false; enabled: root.selectedRow() !== null; Layout.preferredWidth: 96; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.openSelectedForEdit() }
                PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Open Link"; primary: false; enabled: root.selectedRow() !== null && root._clean(root.selectedRow().registryLink).length > 0; Layout.preferredWidth: 122; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.openSelectedRegistryLink() }
                PillButton {
                    t: root.t
                    metrics: root.formFieldMetrics
                    scaleRatios: root.pillScaleRatios
                    text: "Report"
                    primary: false
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: root.fieldHeightPx * 1.04
                    onClicked: {
                        var detailRows = []
                        var rows = root.directoryRows || []
                        for (var i = 0; i < rows.length; i++) {
                            var row = rows[i] || {}
                            detailRows.push({
                                "trademarkId": String(row.trademarkId || ""),
                                "title": String(row.title || row.trademarkText || ""),
                                "jurisdiction": String(row.jurisdiction || ""),
                                "applicationNumber": String(row.applicationNumber || ""),
                                "registrationNumber": String(row.registrationNumber || ""),
                                "status": String(row.currentStatus || row.cipoStatus || row.usptoStatusIndicator || ""),
                                "clientName": String(row.clientName || ""),
                                "filingDate": String(row.filingDate || "")
                            })
                        }

                        var doc = {
                            "reportId": "trademark_directory",
                            "title": "Trademark Directory Report",
                            "generatedAt": Qt.formatDateTime(new Date(), "yyyy-MM-dd hh:mm"),
                            "orientation": "landscape",
                            "branding": {
                                "firmName": "Cory Schneider Law Office",
                                "firmContact": "Cory Schneider Law Office Practice Management",
                                "logoUrl": "../assets/CS.svg"
                            },
                            "filterSummary": "Search: " + (root.directoryQuery || "(none)"),
                            "sections": [
                                {
                                    "sectionId": "detail",
                                    "type": "table",
                                    "title": "Detail",
                                    "columns": [
                                        { "key": "applicationNumber", "label": "App #", "width": 0.12 },
                                        { "key": "title", "label": "Trademark Name", "width": 0.26 },
                                        { "key": "jurisdiction", "label": "Jurisdiction", "width": 0.12 },
                                        { "key": "registrationNumber", "label": "Reg #", "width": 0.12 },
                                        { "key": "status", "label": "Status", "width": 0.14 },
                                        { "key": "clientName", "label": "Client", "width": 0.14 },
                                        { "key": "filingDate", "label": "Filing Date", "width": 0.10 }
                                    ],
                                    "rows": detailRows
                                }
                            ]
                        }
                        root.reportWindowRequested(doc)
                    }
                }
                Item { Layout.fillWidth: true }
            }

            Text {
                Layout.fillWidth: true
                text: "Directory is read-only. Select a record, then click Edit to modify it in Trademark Entry."
                color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.72)
                wrapMode: Text.Wrap
                font.pixelSize: root.ratioPx(0.0126, 12)
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: root.isProMode ? visualRules.radiusControl : root.ratioPx(0.006, 6)
                color: root.isProMode ? root.proSurface : Qt.rgba(root._bg.r, root._bg.g, root._bg.b, 0.28)
                border.width: 1
                border.color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                ListView {
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true
                    spacing: root.ratioPx(0.003, 4)
                    model: root.directoryRows

                    delegate: Rectangle {
                        id: listRow
                        required property var modelData
                        required property int index
                        readonly property bool active: listRow.index === root.selectedDirectoryIndex
                        width: ListView.view.width
                        height: root.ratioPx(0.072, 86)
                        radius: root.isProMode ? visualRules.radiusControl : root.ratioPx(0.0052, 5)
                        color: root.isProMode
                            ? (active ? root.proControl : root.proCanvas)
                            : (active ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.22)
                                      : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72))
                        border.width: 1
                        border.color: root.isProMode
                            ? (active ? root.proActiveBorder : root.proBorder)
                            : (active ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.64)
                                      : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16))

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: root.ratioPx(0.002, 2)
                            Text {
                                Layout.fillWidth: true
                                text: root._clean(listRow.modelData.title || listRow.modelData.trademarkText || listRow.modelData.applicationNumber || listRow.modelData.trademarkId)
                                color: root.isProMode ? root.proInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                elide: Text.ElideRight
                                font.weight: Font.DemiBold
                                font.pixelSize: root.ratioPx(0.0130, 12)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root._clean(listRow.modelData.jurisdiction) + (root._clean(listRow.modelData.applicationNumber).length > 0 ? (" | App: " + root._clean(listRow.modelData.applicationNumber)) : "")
                                color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.78)
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0118, 11)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root._clean(listRow.modelData.currentStatus || listRow.modelData.cipoStatus || listRow.modelData.usptoStatusIndicator) + (root._clean(listRow.modelData.clientName).length > 0 ? (" | " + root._clean(listRow.modelData.clientName)) : "")
                                color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.72)
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0112, 10)
                            }
                        }

                        TapHandler {
                            onTapped: root.selectIndex(listRow.index)
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: root.directoryRows.length <= 0
                        text: "No trademark records found."
                        color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.62)
                        font.pixelSize: root.ratioPx(0.0120, 11)
                    }
                }
            }
        }
    }
}
