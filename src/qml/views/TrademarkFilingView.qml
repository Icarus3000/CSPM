import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
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
    property color proControl: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proSurface: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color proActiveBorder: SemanticTheme.borderStrong(root.t, root.appStyle)
    property color proInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color proMutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color proBackground: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color proCanvas: SemanticTheme.surfacePanel(root.t, root.appStyle)

    property bool dirty: false
    property bool saveInProgress: false
    property bool lastSaveOk: true
    property string saveMessage: ""
    property string lastSavedTrademarkId: ""
    property bool _hydrating: false

    function saveStatusTone() {
        if (saveInProgress) return "info"
        if (dirty) return "warning"
        if (saveMessage.length > 0) return lastSaveOk ? "success" : "error"
        return "success"
    }

    property var jurisdictionOptions: ["CIPO", "USPTO", "Other"]
    property var markTypeOptions: ["Standard Character", "Design", "3D", "Sound", "Color", "Other"]
    property var yesNoOptions: ["No", "Yes"]
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

    function _clean(v) {
        return String(v === undefined || v === null ? "" : v).trim()
    }

    function _digits(v) {
        return _clean(v).replace(/[^0-9]/g, "")
    }

    function areaUnit() {
        var w = (metrics && typeof metrics.contentW === "number" && metrics.contentW > 0) ? metrics.contentW : width
        var h = (metrics && typeof metrics.contentH === "number" && metrics.contentH > 0) ? metrics.contentH : height
        return Math.sqrt(Math.max(1, w) * Math.max(1, h))
    }

    function ratioPx(ratio, minPx) {
        return Math.max(minPx || 1, Math.round(areaUnit() * ratio))
    }

    property int fieldHeightPx: ratioPx(0.031, 38)
    property int sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : ratioPx(0.010, 10)
    property var formTextScaleRatios: ({
        "textSizePct": 0.0170,
        "padSidePct": 0.013,
        "padTopPct": 0.012,
        "padBottomPct": 0.010,
        "radiusPct": 0.011,
        "focusBorderPct": 0.0022,
        "idleBorderPct": 0.0011,
        "labelFontPct": 0.0138,
        "labelLeftMarginPct": 0.012,
        "labelTopMarginPct": 0.0048
    })
    property var formComboScaleRatios: ({
        "textSizePct": 0.0170,
        "padLeftPct": 0.012,
        "padRightPct": 0.034,
        "padTopPct": 0.012,
        "padBottomPct": 0.010,
        "radiusPct": 0.011,
        "focusBorderPct": 0.0022,
        "idleBorderPct": 0.0011,
        "indicatorRightMarginPct": 0.012,
        "indicatorWidthPct": 0.013,
        "indicatorHeightPct": 0.010,
        "popupYOffsetPct": 0.0022,
        "popupMaxHeightPct": 0.260,
        "popupRadiusPct": 0.0087,
        "delegateHeightPct": 0.037,
        "delegateTextPct": 0.0165,
        "labelTextPct": 0.0138,
        "labelLeftPct": 0.012,
        "labelTopPct": 0.0048
    })
    property var formFieldMetrics: ({
        "contentW": (metrics && typeof metrics.contentW === "number" && metrics.contentW > 0) ? metrics.contentW : width,
        "contentH": (metrics && typeof metrics.contentH === "number" && metrics.contentH > 0) ? metrics.contentH : height,
        "fontFloorBodyPx": 13,
        "fontFloorLabelPx": 12,
        "fontFloorTitlePx": 15
    })
    property var matterDirectoryRows: []
    property var matterNumberOptions: []
    property string activeDateFieldKey: ""

    function emptyForm() {
        return {
            trademarkId: "",
            jurisdiction: "CIPO",
            jurisdictionOther: "",
            clientName: "",
            matterNumber: "",
            internalNotes: "",
            trademarkText: "",
            markType: "Standard Character",
            designRepresentation: "",
            designImagePaste: "",
            colorClaimed: "No",
            colorDescription: "",
            niceClasses: "",
            goodsServices: "",
            foreignPriorityClaim: "",
            registryLink: "",
            applicationNumber: "",
            registrationNumber: "",
            currentStatus: "",
            filingDate: "",
            registrationDate: "",
            renewalDeadline: "",
            cipoStatus: "",
            tm5Status: "",
            applicantNameAddress: "",
            examinersReportDate: "",
            officeActionResponseDeadline: "",
            approvalDate: "",
            advertisementDate: "",
            advertisementVolIssue: "",
            oppositionDeadline: "",
            allowanceDate: "",
            registerType: "Principal",
            usptoStatusIndicator: "Live",
            ownerNameAddress: "",
            attorneyOfRecord: "",
            publicationDate: "",
            noticeOfAllowanceDate: "",
            souDeadline: "",
            souExtensionTracking: "",
            section8Deadline: "",
            section15Deadline: "",
            section9Deadline: "",
            localForeignAssociate: "",
            applicationReferenceNumber: "",
            publicationAdvertisementDate: "",
            oppositionPeriodEndDate: "",
            upcomingLocalDeadlineOfficeActionDate: ""
        }
    }

    property var form: emptyForm()

    property var cipoFieldDefs: [
        ["applicationNumber", "Application Number"],
        ["registrationNumber", "Registration Number"],
        ["cipoStatus", "CIPO Status"],
        ["tm5Status", "TM5 Status"],
        ["filingDate", "Filing Date (YYYY-MM-DD)"],
        ["examinersReportDate", "Examiner's Report Date"],
        ["officeActionResponseDeadline", "Office Action Response Deadline"],
        ["approvalDate", "Approval Date"],
        ["advertisementDate", "Advertisement Date"],
        ["advertisementVolIssue", "Advertisement Vol/Issue"],
        ["oppositionDeadline", "Opposition Deadline"],
        ["allowanceDate", "Allowance Date"],
        ["registrationDate", "Registration Date"],
        ["renewalDeadline", "Renewal Deadline"]
    ]

    property var usptoFieldDefs: [
        ["applicationNumber", "Serial Number"],
        ["registrationNumber", "Registration Number"],
        ["filingDate", "Filing Date (YYYY-MM-DD)"],
        ["publicationDate", "Publication Date"],
        ["noticeOfAllowanceDate", "Notice of Allowance Date"],
        ["souDeadline", "SOU Deadline"],
        ["souExtensionTracking", "SOU Extension Tracking"],
        ["registrationDate", "Registration Date"],
        ["section8Deadline", "Section 8 Deadline"],
        ["section15Deadline", "Section 15 Deadline"],
        ["section9Deadline", "Section 9 Deadline"],
        ["renewalDeadline", "Renewal Deadline"],
        ["attorneyOfRecord", "Attorney of Record"]
    ]

    property var otherFieldDefs: [
        ["jurisdictionOther", "Jurisdiction / Country Office"],
        ["localForeignAssociate", "Local Foreign Associate / Counsel"],
        ["applicationReferenceNumber", "Application / Reference Number"],
        ["registrationNumber", "Registration Number"],
        ["currentStatus", "Current Status"],
        ["filingDate", "Filing Date"],
        ["publicationAdvertisementDate", "Publication / Advertisement Date"],
        ["oppositionPeriodEndDate", "Opposition Period End Date"],
        ["registrationDate", "Registration Date"],
        ["upcomingLocalDeadlineOfficeActionDate", "Upcoming Local Deadline / Office Action Date"],
        ["renewalDeadline", "Renewal Date"]
    ]

    function value(key) {
        return _clean(form[key])
    }

    function setValue(key, val, markDirty) {
        if (form && form[key] === val) return
        var next = Object.assign({}, form)
        next[key] = val
        form = next
        if (markDirty === undefined || markDirty) _markDirty()
    }

    function _parseIsoDateOrToday(textValue) {
        var text = _clean(textValue)
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year && candidate.getMonth() === monthIndex && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function _isDateLikeField(fieldKey, fieldLabel) {
        var key = _clean(fieldKey).toLowerCase()
        var label = _clean(fieldLabel).toLowerCase()
        return key.indexOf("date") >= 0
            || key.indexOf("deadline") >= 0
            || label.indexOf("date") >= 0
            || label.indexOf("deadline") >= 0
    }

    function openFormDatePicker(fieldKey, existingText, px, py) {
        activeDateFieldKey = _clean(fieldKey)
        if (activeDateFieldKey.length <= 0) return
        trademarkDateCalendarLoader.active = true
        Qt.callLater(function() {
            var cal = trademarkDateCalendarLoader.item
            if (!cal) return
            cal.selectedDate = _parseIsoDateOrToday(existingText)
            if (typeof cal.openAt === "function") cal.openAt(px, py)
            else if (typeof cal.open === "function") cal.open()
            else cal.visible = true
        })
    }

    function refreshMatterLookupOptions() {
        var rows = []
        try {
            rows = (appRef && appRef.listMatterDirectory) ? appRef.listMatterDirectory() : []
        } catch (e0) {
            rows = []
        }
        matterDirectoryRows = rows && rows.length !== undefined ? rows : []
        var seenNumbers = ({})
        var numbers = []
        for (var i = 0; i < matterDirectoryRows.length; i++) {
            var row = matterDirectoryRows[i]
            if (!row) continue
            var numberText = _clean(row.matterNumber)
            if (numberText.length <= 0) continue
            var key = numberText.toLowerCase()
            if (seenNumbers[key]) continue
            seenNumbers[key] = true
            numbers.push(numberText)
        }
        numbers.sort(function(a, b) { return String(a).localeCompare(String(b)) })
        matterNumberOptions = numbers
    }

    function mergeWithDefaults(data) {
        var next = emptyForm()
        if (data) {
            for (var k in data) {
                if (next.hasOwnProperty(k)) next[k] = data[k]
            }
        }
        return next
    }

    function _markDirty() {
        if (!_hydrating) dirty = true
    }

    function isDesignMark() {
        return value("markType").toLowerCase().indexOf("design") >= 0
    }

    function previewSource() {
        var raw = value("designRepresentation")
        if (raw.length <= 0) raw = value("designImagePaste")
        if (raw.indexOf("data:image") === 0 || raw.indexOf("http://") === 0 || raw.indexOf("https://") === 0 || raw.indexOf("file:") === 0) {
            return raw
        }
        var normalized = raw.replace(/\\/g, "/")
        if (/^[A-Za-z]:\//.test(normalized)) return "file:///" + normalized
        return normalized
    }

    function buildRegistryLink() {
        return ExternalLinks.buildTrademarkRegistryUrl(
            value("jurisdiction"),
            value("applicationNumber"),
            value("registrationNumber"),
            value("trademarkText"),
            value("registryLink")
        )
    }

    function ensureRegistryLink(forceOverwrite) {
        if (!forceOverwrite && value("registryLink").length > 0) return
        setValue("registryLink", buildRegistryLink(), forceOverwrite)
    }

    function openExternalUrl(url) {
        var target = _clean(url)
        if (target.length <= 0) return
        if (ExternalLinks.shouldOpenInEdge(target) && root.appRef && root.appRef.openUrlInEdge) {
            if (root.appRef.openUrlInEdge(target)) return
        }
        Qt.openUrlExternally(target)
    }

    function openRegistryLink() {
        if (value("registryLink").length <= 0) ensureRegistryLink(false)
        var url = ExternalLinks.openableTrademarkRegistryUrl(
            value("jurisdiction"),
            value("applicationNumber"),
            value("registrationNumber"),
            value("trademarkText"),
            value("registryLink")
        )
        openExternalUrl(url)
    }

    function snapshotState() {
        return {
            form: form,
            dirty: dirty,
            saveMessage: saveMessage,
            lastSavedTrademarkId: lastSavedTrademarkId
        }
    }

    function applyInitialState(state) {
        if (!state) return
        _hydrating = true
        if (state.form) form = mergeWithDefaults(state.form)
        else form = mergeWithDefaults(state)
        // Restored state should not be treated as unsaved until user edits.
        dirty = false
        saveMessage = _clean(state.saveMessage)
        lastSavedTrademarkId = _clean(state.lastSavedTrademarkId)
        _hydrating = false
        ensureRegistryLink(false)
    }

    function resetForm() {
        _hydrating = true
        form = mergeWithDefaults({ jurisdiction: value("jurisdiction") || "CIPO" })
        _hydrating = false
        ensureRegistryLink(false)
        dirty = false
        saveMessage = ""
        lastSavedTrademarkId = ""
    }

    function saveRecord() {
        if (saveInProgress) return
        var backend = (typeof docketApp !== "undefined") ? docketApp : null
        if (!backend || !backend.saveTrademarkFiling) {
            lastSaveOk = false
            saveMessage = "Trademark save backend is unavailable."
            return
        }
        ensureRegistryLink(false)
        saveInProgress = true
        try {
            backend.saveTrademarkFiling(Object.assign({}, form))
        } catch (e) {
            saveInProgress = false
            lastSaveOk = false
            saveMessage = String(e)
            dirty = true
        }
        // Result arrives via Connections.onTrademarkSaveFinished below
    }

    Connections {
        target: (typeof docketApp !== "undefined") ? docketApp : null
        function onTrademarkSaveFinished(result) {
            if (!root.saveInProgress) return
            saveInProgress = false
            lastSaveOk = !!(result && result.ok)
            lastSavedTrademarkId = _clean(result && result.trademarkId !== undefined ? result.trademarkId : "")
            saveMessage = _clean(result && result.message !== undefined ? result.message : "")
            if (saveMessage.length <= 0) saveMessage = lastSaveOk ? "Trademark filing saved." : "Trademark filing save failed."
            if (lastSaveOk) {
                setValue("trademarkId", lastSavedTrademarkId, false)
                dirty = false
            } else {
                dirty = true
            }
        }
    }

    Connections {
        target: root.appRef
        function onClientDataChanged() {
            root.refreshMatterLookupOptions()
        }
    }

    Component.onCompleted: {
        ensureRegistryLink(false)
        refreshMatterLookupOptions()
    }


    FileDialog {
        id: designFileDialog
        title: "Select Design Mark Image"
        nameFilters: ["Image files (*.png *.jpg *.jpeg *.svg *.bmp *.gif)", "All files (*)"]
        onAccepted: {
            var p = selectedFile ? selectedFile.toString() : ""
            if (_clean(p).length > 0) setValue("designRepresentation", p, true)
        }
    }

    component FormTextField: ColumnLayout {
        id: formTextField
        property string fieldKey: ""
        property string fieldLabel: ""
        property bool dateLike: root._isDateLikeField(fieldKey, fieldLabel)
        Layout.fillWidth: true
        spacing: root.ratioPx(0.0015, 2)

        Text {
            Layout.fillWidth: true
            text: formTextField.fieldLabel
            color: root.isProMode ? root.proMutedInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(0.0118, 11)
            font.weight: Font.DemiBold
            clip: true
            maximumLineCount: 1
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
        }

        ModernTextField {
            id: formTextInput
            t: root.t
            metrics: root.formFieldMetrics
            scaleRatios: root.formTextScaleRatios
            label: ""
            Layout.fillWidth: true
            Layout.preferredHeight: root.fieldHeightPx
            Component.onCompleted: {
                text = root.value(formTextField.fieldKey)
            }
            onTextChanged: {
                if (root._clean(root.value(formTextField.fieldKey)) !== root._clean(text)) {
                    root.setValue(formTextField.fieldKey, text, true)
                }
            }
            MouseArea {
                anchors.fill: parent
                visible: formTextField.dateLike
                enabled: visible
                acceptedButtons: Qt.LeftButton
                propagateComposedEvents: true
                onDoubleClicked: function(mouse) {
                    var p = mapToGlobal(mouse.x, mouse.y)
                    root.openFormDatePicker(formTextField.fieldKey, formTextInput.text, p.x, p.y)
                }
                onPressed: function(mouse) { mouse.accepted = false }
            }
        }

        onFieldKeyChanged: {
            var next = root.value(fieldKey)
            if (formTextInput.text !== next) formTextInput.text = next
        }

        Connections {
            target: root
            function onFormChanged() {
                var next = root.value(formTextField.fieldKey)
                if (formTextInput.text !== next) formTextInput.text = next
            }
        }
    }

    component FormComboField: ColumnLayout {
        id: formComboField
        property string fieldKey: ""
        property string fieldLabel: ""
        property var optionsModel: []
        Layout.fillWidth: true
        spacing: root.ratioPx(0.0015, 2)

        Text {
            Layout.fillWidth: true
            text: formComboField.fieldLabel
            color: root.isProMode ? root.proMutedInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(0.0118, 11)
            font.weight: Font.DemiBold
            clip: true
            maximumLineCount: 1
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
        }

        ModernComboBox {
            id: formComboInput
            t: root.t
            metrics: root.formFieldMetrics
            scaleRatios: root.formComboScaleRatios
            label: ""
            fullModel: formComboField.optionsModel
            Layout.fillWidth: true
            Layout.preferredHeight: root.fieldHeightPx
            Component.onCompleted: {
                editText = root.value(formComboField.fieldKey)
            }
            onEditTextChanged: {
                if (root._clean(root.value(formComboField.fieldKey)) !== root._clean(editText)) {
                    root.setValue(formComboField.fieldKey, editText, true)
                }
            }
            onActivated: {
                if (root._clean(root.value(formComboField.fieldKey)) !== root._clean(editText)) {
                    root.setValue(formComboField.fieldKey, editText, true)
                }
            }
        }

        onFieldKeyChanged: {
            var next = root.value(fieldKey)
            if (formComboInput.editText !== next) formComboInput.editText = next
        }

        Connections {
            target: root
            function onFormChanged() {
                var next = root.value(formComboField.fieldKey)
                if (formComboInput.editText !== next) formComboInput.editText = next
            }
        }
    }

    component FormAreaField: ColumnLayout {
        id: formAreaField
        property string fieldKey: ""
        property string fieldLabel: ""
        property int prefHeight: root.ratioPx(0.085, 115)
        Layout.fillWidth: true
        spacing: root.ratioPx(0.0015, 2)

        Text {
            Layout.fillWidth: true
            text: formAreaField.fieldLabel
            color: root.isProMode ? root.proMutedInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
            font.pixelSize: root.ratioPx(0.0118, 11)
            font.weight: Font.DemiBold
            clip: true
            maximumLineCount: 1
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: formAreaField.prefHeight
            radius: root.isProMode ? visualRules.radiusControl : root.ratioPx(0.006, 6)
            color: root.isProMode ? root.proControl : SemanticTheme.alpha(root._bg, 0.36)
            border.width: 1
            border.color: root.isProMode ? root.proBorder : SemanticTheme.borderSubtle(root.t, root.appStyle)

            TextArea {
                id: areaInput
                anchors.fill: parent
                anchors.margins: root.ratioPx(0.0042, 5)
                text: root.value(formAreaField.fieldKey)
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                color: root.isProMode ? root.proInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
                background: null
                onTextChanged: {
                    if (root._clean(root.value(formAreaField.fieldKey)) !== root._clean(text)) {
                        root.setValue(formAreaField.fieldKey, text, true)
                    }
                }
                Connections {
                    target: root
                    function onFormChanged() {
                        var next = root.value(formAreaField.fieldKey)
                        if (areaInput.text !== next) areaInput.text = next
                    }
                }
            }
        }
    }

    Loader {
        id: trademarkDateCalendarLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: root.t
                metrics: root.formFieldMetrics
                hostWindow: root.Window.window
                onDatePicked: function(d) {
                    var iso = Qt.formatDate(d, "yyyy-MM-dd")
                    if (root.activeDateFieldKey.length > 0) {
                        root.setValue(root.activeDateFieldKey, iso, true)
                    }
                    root.activeDateFieldKey = ""
                    trademarkDateCalendarLoader.active = false
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: !root.isProMode
        gradient: Gradient {
            GradientStop { position: 0.0; color: SemanticTheme.surfaceApp(root.t, root.appStyle) }
            GradientStop { position: 1.0; color: SemanticTheme.surfacePanel(root.t, root.appStyle) }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.isProMode
        color: root.proBackground
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: root.ratioPx(0.0055, 6)

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.sectionRadiusPx
            color: root.isProMode ? root.proCanvas : SemanticTheme.alpha(root._panel, 0.78)
            border.width: 1
            border.color: root.isProMode ? root.proBorder : SemanticTheme.borderSubtle(root.t, root.appStyle)

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
                        text: "Trademark Entry Form"
                        color: root.isProMode ? root.proInk : SemanticTheme.inkPrimary(root.t, root.appStyle)
                        font.pixelSize: 18
                        font.family: "Segoe UI"
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: root.saveMessage.length > 0 ? root.saveMessage : (root.dirty ? "Unsaved" : "Ready")
                        color: SemanticTheme.tone(root.t, root.saveStatusTone())
                        font.pixelSize: root.ratioPx(0.0120, 11)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Repeater {
                        model: root.jurisdictionOptions
                        delegate: Rectangle {
                            property string officeName: String(modelData || "")
                            property bool active: root.value("jurisdiction") === officeName
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.fieldHeightPx * 0.95
                            radius: root.isProMode ? visualRules.radiusControl : height / 2
                            color: root.isProMode
                                ? (active ? root.proControl : root.proSurface)
                                : (active ? SemanticTheme.hoverOverlay(root.t, root.appStyle)
                                          : SemanticTheme.alpha(root._panel, 0.66))
                            border.width: 1
                            border.color: root.isProMode
                                ? (active ? root.proActiveBorder : root.proBorder)
                                : (active ? SemanticTheme.alpha(root._accent, 0.62)
                                          : SemanticTheme.borderSubtle(root.t, root.appStyle))
                            Behavior on color { ColorAnimation { duration: 130 } }
                            Text {
                                anchors.centerIn: parent
                                text: parent.officeName
                                color: root.isProMode
                                    ? (parent.active ? root.proInk : root.proMutedInk)
                                    : SemanticTheme.inkPrimary(root.t, root.appStyle)
                                font.pixelSize: root.ratioPx(0.0155, 14)
                                font.weight: parent.active ? Font.DemiBold : Font.Normal
                            }
                            TapHandler {
                                onTapped: {
                                    root.setValue("jurisdiction", parent.officeName, true)
                                    if (parent.officeName !== "Other") root.setValue("jurisdictionOther", "", false)
                                    root.ensureRegistryLink(false)
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.ratioPx(0.004, 4)
                    PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "New"; primary: false; Layout.preferredWidth: 100; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.resetForm() }
                    PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: root.saveInProgress ? "Saving..." : "Save"; primary: true; enabled: !root.saveInProgress && root.dirty; Layout.preferredWidth: 110; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.saveRecord() }
                    PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Auto Link"; primary: false; Layout.preferredWidth: 116; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.ensureRegistryLink(true) }
                    PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Open Link"; primary: false; Layout.preferredWidth: 116; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: root.openRegistryLink() }
                }

                ScrollView {
                    id: formScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: Math.max(1, formScroll.availableWidth)
                        spacing: root.ratioPx(0.005, 6)

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: universalSectionBody.implicitHeight + (root.ratioPx(0.006, 7) * 2)
                            radius: root.sectionRadiusPx
                            color: root.isProMode ? root.proSurface : SemanticTheme.alpha(root._panel, 0.62)
                            border.width: 1
                            border.color: root.isProMode ? root.proBorder : SemanticTheme.borderSubtle(root.t, root.appStyle)

                            ColumnLayout {
                                id: universalSectionBody
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: root.ratioPx(0.006, 7)
                                spacing: root.ratioPx(0.004, 5)
                                Text { text: "Universal Fields"; color: root.isProMode ? root.proInk : SemanticTheme.inkPrimary(root.t, root.appStyle); font.pixelSize: root.ratioPx(0.0132, 12); font.weight: Font.DemiBold }

                                FormTextField { fieldKey: "clientName"; fieldLabel: "Client Name" }
                                FormComboField { fieldKey: "matterNumber"; fieldLabel: "Matter Number"; optionsModel: root.matterNumberOptions }
                                FormTextField { fieldKey: "trademarkText"; fieldLabel: "Trademark Text" }
                                FormComboField { fieldKey: "markType"; fieldLabel: "Mark Type"; optionsModel: root.markTypeOptions }
                                FormTextField { fieldKey: "designRepresentation"; fieldLabel: "Design Representation (file path/link)" }
                                RowLayout { Layout.fillWidth: true; visible: root.isDesignMark(); PillButton { t: root.t; metrics: root.formFieldMetrics; scaleRatios: root.pillScaleRatios; text: "Browse Design Image"; primary: false; Layout.preferredWidth: 190; Layout.preferredHeight: root.fieldHeightPx * 1.04; onClicked: designFileDialog.open() } }
                                FormComboField { fieldKey: "colorClaimed"; fieldLabel: "Color As Feature"; optionsModel: root.yesNoOptions }
                                FormTextField { visible: root.value("colorClaimed").toLowerCase() === "yes"; fieldKey: "colorDescription"; fieldLabel: "Color Description" }
                                FormTextField { fieldKey: "niceClasses"; fieldLabel: "Nice Classification(s)" }
                                FormTextField { fieldKey: "foreignPriorityClaim"; fieldLabel: "Foreign Priority Claim" }
                                FormTextField { fieldKey: "registryLink"; fieldLabel: "Registry / Application Link" }
                                FormAreaField { fieldKey: "goodsServices"; fieldLabel: "Goods and Services Description" }
                                FormAreaField { fieldKey: "internalNotes"; fieldLabel: "Internal Notes / Next Strategy" }
                                FormAreaField { visible: root.isDesignMark(); fieldKey: "designImagePaste"; fieldLabel: "Design Image URL or data:image paste"; prefHeight: root.ratioPx(0.062, 90) }

                                Rectangle {
                                    visible: root.isDesignMark()
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.ratioPx(0.15, 165)
                                    radius: root.isProMode ? visualRules.radiusControl : root.ratioPx(0.006, 6)
                                    color: root.isProMode ? root.proControl : SemanticTheme.alpha(root._bg, 0.42)
                                    border.width: 1
                                    border.color: root.isProMode ? root.proBorder : SemanticTheme.alpha(root._accent, 0.33)
                                    Image { id: designPreview; anchors.fill: parent; anchors.margins: root.ratioPx(0.004, 5); source: root.previewSource(); fillMode: Image.PreserveAspectFit; asynchronous: true; visible: String(source || "").length > 0 }
                                    Text { anchors.centerIn: parent; visible: !designPreview.visible; text: "No design image selected"; color: root.isProMode ? root.proMutedInk : SemanticTheme.inkMuted(root.t, root.appStyle); font.pixelSize: root.ratioPx(0.0130, 12) }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: jurisdictionSectionBody.implicitHeight + (root.ratioPx(0.006, 7) * 2)
                            radius: root.sectionRadiusPx
                            color: root.isProMode ? root.proSurface : SemanticTheme.alpha(root._panel, 0.62)
                            border.width: 1
                            border.color: root.isProMode ? root.proBorder : SemanticTheme.borderSubtle(root.t, root.appStyle)

                            ColumnLayout {
                                id: jurisdictionSectionBody
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: root.ratioPx(0.006, 7)
                                spacing: root.ratioPx(0.004, 5)

                                Text { text: "Jurisdiction Specific: " + root.value("jurisdiction"); color: root.isProMode ? root.proInk : SemanticTheme.inkPrimary(root.t, root.appStyle); font.pixelSize: root.ratioPx(0.0132, 12); font.weight: Font.DemiBold }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    visible: root.value("jurisdiction") === "CIPO"
                                    Repeater { model: root.cipoFieldDefs; delegate: FormTextField { fieldKey: modelData[0]; fieldLabel: modelData[1] } }
                                    FormAreaField { fieldKey: "applicantNameAddress"; fieldLabel: "Applicant Name and Address"; prefHeight: root.ratioPx(0.070, 95) }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    visible: root.value("jurisdiction") === "USPTO"
                                    FormComboField { fieldKey: "registerType"; fieldLabel: "Register Type"; optionsModel: ["Principal", "Supplemental"] }
                                    FormComboField { fieldKey: "usptoStatusIndicator"; fieldLabel: "Status (Live/Dead)"; optionsModel: ["Live", "Dead"] }
                                    Repeater { model: root.usptoFieldDefs; delegate: FormTextField { fieldKey: modelData[0]; fieldLabel: modelData[1] } }
                                    FormAreaField { fieldKey: "ownerNameAddress"; fieldLabel: "Owner Name and Address"; prefHeight: root.ratioPx(0.070, 95) }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    visible: root.value("jurisdiction") === "Other"
                                    Repeater { model: root.otherFieldDefs; delegate: FormTextField { fieldKey: modelData[0]; fieldLabel: modelData[1] } }
                                }
                            }
                        }
                    }
                }
            }
        }

    }
}
