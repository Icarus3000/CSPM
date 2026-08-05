pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

ComboBox {
    id: control
    property var t;
    property var metrics
    property color _accent: (t && t.accent) ? t.accent : "#FF1744";
    property color _text: (t && t.text) ? t.text : "#FFFFFF";
    property color _panel: (t && t.panel2) ? t.panel2 : "#1A1A1A";
    property string appStyle: ((typeof app !== "undefined") && app !== null && app.appStyle)
        ? String(app.appStyle)
        : "Professional"
    readonly property bool isProMode: visualRules.isPro
    property color tokenAccent: SemanticTheme.accentPrimary(control.t, control.appStyle)
    property color tokenInk: SemanticTheme.inkPrimary(control.t, control.appStyle)
    property color tokenInput: SemanticTheme.surfaceInput(control.t, control.appStyle)
    property color tokenBorder: SemanticTheme.borderSubtle(control.t, control.appStyle)

    VisualRules {
        id: visualRules
        appStyle: control.appStyle
    }

    signal labelDoubleClicked()

    property string label: ""
    readonly property bool hasLabel: String(control.label || "").length > 0
    property int minimumUsableWidthPx: ratioPx(0.180, 176)
    property var fullModel: []
    property bool smartFilterEnabled: true
    property bool sortSmartFilterResults: true
    property bool preserveEditTextOnModelChanged: true
    property string emptyOptionLabel: "(none)"
    property var displayModel: []
    property bool _searchTypingActive: false
    property var scaleRatios: ({
        "textSizePct": 0.0168,
        "padLeftPct": 0.012,
        "padRightPct": 0.034,
        "padTopPct": 0.024,
        "padBottomPct": 0.006,
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

    function ratioPx(ratio, minPx) {
        // Avoid binding loops: ComboBox implicit size/font/padding can depend on
        // each other; this helper must stay independent of control width/height.
        var rw = (metrics && typeof metrics.contentW === "number") ? metrics.contentW : 1220
        var rh = (metrics && typeof metrics.contentH === "number") ? metrics.contentH : 920
        var unit = Math.min(Math.max(1, rw), Math.max(1, rh))
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(unit * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    function _optionText(optionValue) {
        return String(optionValue === undefined || optionValue === null ? "" : optionValue)
    }

    function optionDisplayText(optionValue) {
        var text = _optionText(optionValue)
        return text.length > 0 ? text : control.emptyOptionLabel
    }

    function _searchableOptionText(optionValue) {
        var text = _optionText(optionValue)
        return text.length > 0 ? text : control.emptyOptionLabel
    }

    function _sourceItems() {
        var out = []
        var source = control.fullModel
        if (!source) return out
        if (source.length !== undefined) {
            for (var i = 0; i < source.length; i++) out.push(source[i])
            return out
        }
        if (source.count !== undefined && source.get) {
            for (var j = 0; j < source.count; j++) out.push(source.get(j))
        }
        return out
    }

    function _searchTokens(value) {
        var raw = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
        if (raw.length <= 0) return []
        var parts = raw.split(/\s+/)
        var tokens = []
        for (var i = 0; i < parts.length; i++) {
            var token = String(parts[i] || "").trim()
            if (token.length > 0) tokens.push(token)
        }
        return tokens
    }

    function _matchesSearch(optionValue, tokens) {
        if (!tokens || tokens.length <= 0) return true
        var haystack = _searchableOptionText(optionValue).toLowerCase()
        for (var i = 0; i < tokens.length; i++) {
            if (haystack.indexOf(String(tokens[i] || "")) < 0) return false
        }
        return true
    }

    function refreshDisplayModel() {
        var source = _sourceItems()
        if (control.sortSmartFilterResults) {
            source.sort(function(a, b) {
                return _searchableOptionText(a).localeCompare(_searchableOptionText(b))
            })
        }
        
        var query = control._searchTypingActive ? String(control.editText || "") : ""
        var tokens = _searchTokens(query)
        if (tokens.length <= 0) {
            control.displayModel = source
            return
        }

        var filtered = []
        for (var i = 0; i < source.length; i++) {
            if (_matchesSearch(source[i], tokens)) filtered.push(source[i])
        }
        control.displayModel = filtered
    }

    implicitWidth: control.minimumUsableWidthPx
    Layout.minimumWidth: control.minimumUsableWidthPx
    editable: true
    // Lock native model to fullModel to preserve strict index mapping
    model: fullModel
    displayText: control.editText.length > 0 ? control.editText : control.emptyOptionLabel
    inputMethodHints: Qt.ImhNoPredictiveText

    property string _lastValidSelectedText: ""

    Component.onCompleted: {
        refreshDisplayModel()
        _lastValidSelectedText = control.editText
    }

    onFullModelChanged: {
        var preTxt = control ? String(control.editText || "") : ""
        refreshDisplayModel()

        if (!control || control.preserveEditTextOnModelChanged !== true) {
            return
        }

        if (preTxt && preTxt.length > 0 && !control._searchTypingActive) {
            Qt.callLater(function() {
                // The combo may have been destroyed/recycled, or the owner may
                // have intentionally changed editText while the model refreshed.
                if (!control || control.preserveEditTextOnModelChanged !== true) return

                var items = control._sourceItems()
                var stillAvailable = false
                for (var i = 0; i < items.length; i++) {
                    var itemText = control.optionDisplayText(items[i])
                    if (itemText === preTxt || String(items[i] || "") === preTxt) {
                        stillAvailable = true
                        break
                    }
                }
                if (!stillAvailable) return

                if (control.editText !== preTxt) {
                    control.editText = preTxt
                }
            })
        }
    }
    onEditTextChanged: if (control.smartFilterEnabled && control._searchTypingActive) refreshDisplayModel()

    onActiveFocusChanged: {
        if (control.activeFocus && comboInput) {
            _lastValidSelectedText = control.editText
            comboInput.forceActiveFocus()
            comboInput.selectAll()
        } else {
            control._searchTypingActive = false
            if (control.smartFilterEnabled) {
                // Revert invalid text to the last known valid text if it doesn't match any option
                var currentTxt = control.editText;
                var found = false;
                var fm = control.fullModel || [];
                var len = fm.length !== undefined ? fm.length : (fm.count !== undefined ? fm.count : 0);
                for (var i = 0; i < len; i++) {
                    var opt = fm.length !== undefined ? fm[i] : fm.get(i);
                    if (control._optionText(opt) === currentTxt) {
                        found = true;
                        break;
                    }
                }
                if (!found && currentTxt !== control.emptyOptionLabel && currentTxt.length > 0) {
                    control.editText = control._lastValidSelectedText;
                } else {
                    control._lastValidSelectedText = control.editText;
                }
                refreshDisplayModel()
            }
        }
    }

    Connections {
        target: control
        function onActivated(index) {
            control._searchTypingActive = false
            control._lastValidSelectedText = control.editText
            if (control.smartFilterEnabled) control.refreshDisplayModel()
        }
    }

    font.pixelSize: ratioPx(scaleRatios.textSizePct, metricFloor("fontFloorBodyPx", 9))
    leftPadding: ratioPx(scaleRatios.padLeftPct, 4)
    rightPadding: ratioPx(scaleRatios.padRightPct, 8)
    
    topPadding: control.hasLabel
        ? Math.max(
            ratioPx(scaleRatios.padTopPct, 4),
            comboLabel.font.pixelSize + ratioPx(0.0040, 2)
        )
        : ratioPx(scaleRatios.padTopPct, 4)
    bottomPadding: ratioPx(scaleRatios.padBottomPct, 2)

    TextMetrics {
        id: displayMetrics
        font: control.font
        text: control.displayText
    }

    TextMetrics {
        id: popupItemMetrics
        font.family: control.font.family
        font.weight: control.font.weight
        font.pixelSize: control.ratioPx(control.scaleRatios.delegateTextPct, control.metricFloor("fontFloorBodyPx", 9))
    }

    property real _maxPopupItemWidth: control.width

    contentItem: Item {
        implicitWidth: comboInput.implicitWidth
        implicitHeight: comboInput.implicitHeight
        clip: true

        property alias text: comboInput.text

        TextInput {
            id: comboInput
            visible: control.editable && control.activeFocus
            text: control.editText
            color: control.isProMode ? control.tokenInk : control._text
            font: control.font
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: TextInput.AlignLeft
            readOnly: !control.editable
            selectByMouse: true
            anchors.fill: parent
            anchors.rightMargin: arrowCanvas.width + control.ratioPx(control.scaleRatios.indicatorRightMarginPct, 3) + 4
            
            Keys.onEscapePressed: function(event) {
                if (control._searchTypingActive) {
                    control.editText = control._lastValidSelectedText;
                    control._searchTypingActive = false;
                    control.refreshDisplayModel();
                    event.accepted = true;
                } else {
                    event.accepted = false;
                }
            }
            clip: true

            onTextChanged: {
                if (control.editText !== text) {
                    control.editText = text
                }
            }

            onTextEdited: {
                control._searchTypingActive = true
                control.refreshDisplayModel()
                if (!control.popup.visible) {
                    control.popup.open()
                }
            }

            onAccepted: {
                if (control.smartFilterEnabled && control.displayModel && control.displayModel.length > 0) {
                    var topMatch = control._optionText(control.displayModel[0])
                    control.editText = topMatch
                    control._lastValidSelectedText = topMatch
                }
                control.popup.close()
                comboInput.focus = false
            }
        }

        Text {
            id: displayText
            visible: !comboInput.visible
            text: control.displayText
            color: control.isProMode ? control.tokenInk : control._text
            font.family: control.font.family
            font.weight: control.font.weight
            font.pixelSize: {
                var basePx = control.font.pixelSize;
                var minPx = 4;
                var cw = displayMetrics.boundingRect.width;
                var aw = parent.width - (arrowCanvas.width + control.ratioPx(control.scaleRatios.indicatorRightMarginPct, 3) + 4);
                if (cw > aw && aw > 0) {
                    var scale = aw / cw;
                    var adjustedPx = basePx * scale * 0.98;
                    if (adjustedPx < minPx) return minPx;
                    return adjustedPx;
                }
                return basePx;
            }
            elide: Text.ElideRight
            clip: true
            maximumLineCount: 1
            wrapMode: Text.NoWrap
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignLeft
            anchors.fill: parent
            anchors.rightMargin: arrowCanvas.width + control.ratioPx(control.scaleRatios.indicatorRightMarginPct, 3) + 4
        }
    }

    background: Item {
        readonly property bool activeGlow: control.activeFocus || control.popup.visible

        DropShadow {
            visible: visualRules.shadowOpacity > 0
            anchors.fill: comboBg
            source: comboBg
            horizontalOffset: 0
            verticalOffset: 0
            radius: control.isProMode ? visualRules.radiusControl : control.ratioPx(control.scaleRatios.radiusPct * 1.8, 4)
            samples: control.ratioPx(control.scaleRatios.radiusPct * 4.0, 10)
            color: Qt.rgba(control._accent.r, control._accent.g, control._accent.b, parent.activeGlow ? 0.20 : 0.0)
            transparentBorder: true
        }

        Rectangle {
            id: comboBg
            anchors.fill: parent
            color: control.isProMode
                ? control.tokenInput
                : Qt.rgba(
                    (control._panel.r * 0.78) + (control._accent.r * 0.22),
                    (control._panel.g * 0.78) + (control._accent.g * 0.22),
                    (control._panel.b * 0.78) + (control._accent.b * 0.22),
                    parent.activeGlow ? 0.95 : 0.91
                )
            radius: control.isProMode ? visualRules.radiusControl : control.ratioPx(control.scaleRatios.radiusPct, 2)
            border.width: parent.activeGlow
                ? Math.max(2, control.ratioPx(control.scaleRatios.focusBorderPct, 1))
                : control.ratioPx(control.scaleRatios.idleBorderPct, 1)
            border.color: parent.activeGlow
                ? Qt.rgba(control.tokenAccent.r, control.tokenAccent.g, control.tokenAccent.b, 0.84)
                : (control.isProMode ? control.tokenBorder : Qt.rgba(control._text.r, control._text.g, control._text.b, 0.40))
        }
    }

    indicator: Canvas {
        id: arrowCanvas
        x: control.width - width - control.ratioPx(control.scaleRatios.indicatorRightMarginPct, 3)
        y: control.height / 2
        width: control.ratioPx(control.scaleRatios.indicatorWidthPct, 6)
        height: control.ratioPx(control.scaleRatios.indicatorHeightPct, 4)
        contextType: "2d"

        property color arrowColor: control.isProMode ? control.tokenInk : (control.t ? control._accent : "#888888")
        onArrowColorChanged: arrowCanvas.requestPaint()
        onWidthChanged: arrowCanvas.requestPaint()
        onHeightChanged: arrowCanvas.requestPaint()

        Connections {
            target: control
            function onPressedChanged() { arrowCanvas.requestPaint() }
        }

        Component.onCompleted: arrowCanvas.requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.beginPath()
            ctx.moveTo(0, 0)
            ctx.lineTo(width / 2, height)
            ctx.lineTo(width, 0)
            ctx.strokeStyle = arrowCanvas.arrowColor
            ctx.lineWidth = control.ratioPx(control.scaleRatios.idleBorderPct, 1)
            ctx.stroke()
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: !control.editable
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            control.forceActiveFocus()
            if (control.popup.visible) {
                control.popup.close()
            } else {
                control.popup.open()
            }
        }
    }

    onModelChanged: {
        Qt.callLater(function() {
            if (!control) return;
            var mw = control.width;
            var c = control.count;
            for (var i = 0; i < c; i++) {
                popupItemMetrics.text = control.optionDisplayText(control.textAt(i));
                var w = popupItemMetrics.boundingRect.width;
                if (w > mw) mw = w;
            }
            control._maxPopupItemWidth = Math.max(control.width, mw + 32);
        });
    }

    popup: Popup {
        y: control.height + control.ratioPx(control.scaleRatios.popupYOffsetPct, 1)
        width: Math.max(control.width, control._maxPopupItemWidth)
        implicitHeight: contentItem.implicitHeight > control.ratioPx(control.scaleRatios.popupMaxHeightPct, 80)
            ? control.ratioPx(control.scaleRatios.popupMaxHeightPct, 80)
            : contentItem.implicitHeight
        padding: 1

        onOpened: {
            var mw = control.width;
            var c = control.count;
            for (var i = 0; i < c; i++) {
                popupItemMetrics.text = control.optionDisplayText(control.textAt(i));
                var w = popupItemMetrics.boundingRect.width;
                if (w > mw) mw = w;
            }
            control._maxPopupItemWidth = Math.max(control.width, mw + 32);
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            // Bypass native delegateModel to bind directly to our JS array,
            // so we don't corrupt the native ComboBox index when filtering.
            model: control.popup.visible ? (control.smartFilterEnabled ? control.displayModel : control.fullModel) : null
            currentIndex: -1
            ScrollIndicator.vertical: ScrollIndicator { }

            delegate: ItemDelegate {
                id: rowDelegate
                required property var modelData
                width: control.popup.width
                height: rowDelegate.modelData === "---" ? 12 : control.ratioPx(control.scaleRatios.delegateHeightPct, 18)
                hoverEnabled: rowDelegate.modelData !== "---"
                enabled: rowDelegate.modelData !== "---"

                contentItem: Item {
                    anchors.fill: parent
                    
                    Text {
                        visible: rowDelegate.modelData !== "---"
                        text: control.optionDisplayText(rowDelegate.modelData)
                        color: control.isProMode ? control.tokenInk : control._text
                        font.pixelSize: control.ratioPx(control.scaleRatios.delegateTextPct, control.metricFloor("fontFloorBodyPx", 9))
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignLeft
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                    }
                    
                    Rectangle {
                        visible: rowDelegate.modelData === "---"
                        width: parent.width - 16
                        height: 1
                        color: control.isProMode ? SemanticTheme.borderSubtle(control.t, control.appStyle) : SemanticTheme.borderSubtle(control.t, control.appStyle)
                        anchors.centerIn: parent
                    }
                }

                background: Rectangle {
                    readonly property bool activeRow: rowDelegate.hovered || rowDelegate.highlighted
                    color: activeRow
                        ? (control.isProMode
                            ? SemanticTheme.surfaceInput(control.t, control.appStyle)
                            : Qt.rgba(
                                (control._accent ? control._accent.r : 1.0),
                                (control._accent ? control._accent.g : 0.0),
                                (control._accent ? control._accent.b : 0.26),
                                rowDelegate.highlighted ? 0.24 : 0.16
                            ))
                        : "transparent"
                    border.width: rowDelegate.hovered ? control.ratioPx(control.scaleRatios.idleBorderPct, 1) : 0
                    border.color: control.isProMode
                        ? SemanticTheme.borderSubtle(control.t, control.appStyle)
                        : Qt.rgba(
                            (control._accent ? control._accent.r : 1.0),
                            (control._accent ? control._accent.g : 0.0),
                            (control._accent ? control._accent.b : 0.26),
                            rowDelegate.hovered ? 0.48 : 0.0
                        )
                }

                onClicked: {
                    var chosen = control._optionText(rowDelegate.modelData)
                    control.editText = chosen
                    control._lastValidSelectedText = chosen
                    control._searchTypingActive = false
                    control.popup.close()
                    
                    // Attempt to sync the native ComboBox currentIndex if possible
                    var nativeIdx = control.find(chosen)
                    if (nativeIdx >= 0) {
                        control.currentIndex = nativeIdx
                        control.activated(nativeIdx)
                    }
                }
            }
        }

        background: SemanticPanel {
            t: control.t
            role: "popup"
            tone: "neutral"
            appStyle: control.appStyle
            borderWidth: control.ratioPx(control.scaleRatios.idleBorderPct, 1)
            radius: control.isProMode ? visualRules.radiusPopup : control.ratioPx(control.scaleRatios.popupRadiusPct, 2)
            shadowEnabled: visualRules.shadowOpacity > 0
            shadowRadius: control.isProMode ? 0 : control.ratioPx(control.scaleRatios.popupRadiusPct * 1.5, 3)
            shadowSamples: control.isProMode ? 0 : control.ratioPx(control.scaleRatios.popupRadiusPct * 3.0, 6)
        }
    }

    Text {
        id: comboLabel
        text: control.label
        visible: control.hasLabel
        color: control.isProMode ? control.tokenInk : control._text
        font.pixelSize: control.ratioPx(control.scaleRatios.labelTextPct, control.metricFloor("fontFloorLabelPx", 8))
        font.weight: Font.DemiBold
        anchors.left: parent.left
        anchors.leftMargin: control.ratioPx(control.scaleRatios.labelLeftPct, 4)
        anchors.right: parent.right
        anchors.rightMargin: control.rightPadding + control.ratioPx(0.0040, 4)
        anchors.top: parent.top
        anchors.topMargin: control.ratioPx(control.scaleRatios.labelTopPct, 2)
        clip: true
        maximumLineCount: 1
        wrapMode: Text.NoWrap
        elide: Text.ElideRight
        font.underline: labelMouseArea.containsMouse
        opacity: labelMouseArea.containsMouse ? 1.0 : 0.94

        MouseArea {
            id: labelMouseArea
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.PointingHandCursor
            onClicked: control.labelDoubleClicked()
            onDoubleClicked: control.labelDoubleClicked()
        }
    }
}
