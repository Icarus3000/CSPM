pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

TextField {
    id: control
    property var t
    property var metrics
    property string label: ""
    property bool datePickerEnabled: false
    property color accentColor: SemanticTheme.accentPrimary(control.t, control.appStyle)
    property color panelColor: SemanticTheme.surfaceInput(control.t, control.appStyle)
    property color textColor: SemanticTheme.inkPrimary(control.t, control.appStyle)
    property string appStyle: ((typeof app !== "undefined") && app !== null && app.appStyle)
        ? String(app.appStyle)
        : "Professional"
    readonly property bool isProMode: visualRules.isPro
    property color tokenAccent: SemanticTheme.accentPrimary(control.t, control.appStyle)
    property color tokenInk: SemanticTheme.inkPrimary(control.t, control.appStyle)
    property color tokenInput: SemanticTheme.surfaceInput(control.t, control.appStyle)
    property color tokenBorder: SemanticTheme.borderSubtle(control.t, control.appStyle)
    readonly property bool hasLabel: String(control.label || "").length > 0
    property int minimumUsableWidthPx: ratioPx(0.180, 176)
    property var scaleRatios: ({
        "textSizePct": 0.0168,
        "padSidePct": 0.013,
        "padTopPct": 0.024,
        "padBottomPct": 0.006,
        "radiusPct": 0.011,
        "focusBorderPct": 0.0022,
        "idleBorderPct": 0.0011,
        "labelFontPct": 0.0138,
        "labelLeftMarginPct": 0.012,
        "labelTopMarginPct": 0.0048
    })
    // Use stable sizing inputs (app metrics or fixed fallback), not control width/height.
    // This prevents implicitHeight/font/padding feedback loops in Qt Quick TextField.
    property real _baseContentW: (metrics && typeof metrics.contentW === "number" && metrics.contentW > 0)
        ? metrics.contentW
        : 1280
    property real _baseContentH: (metrics && typeof metrics.contentH === "number" && metrics.contentH > 0)
        ? metrics.contentH
        : 800
    VisualRules {
        id: visualRules
        appStyle: control.appStyle
    }
    signal datePickerDatePicked(date pickedDate, string isoText)

    implicitWidth: control.minimumUsableWidthPx
    Layout.minimumWidth: control.minimumUsableWidthPx
    function ratioPx(ratio, minPx) {
        var rw = _baseContentW
        var rh = _baseContentH
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

    function _parseIsoDateOrToday(textValue) {
        var textValueString = String(textValue || "").trim()
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(textValueString)
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year
                && candidate.getMonth() === monthIndex
                && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function openDatePickerAt(px, py) {
        if (!control.datePickerEnabled) return
        datePickerLoader.active = true
        Qt.callLater(function() {
            var cal = datePickerLoader.item
            if (!cal) return
            cal["selectedDate"] = control._parseIsoDateOrToday(control.text)
            if (typeof cal["openAt"] === "function") cal["openAt"](px, py)
            else if (typeof cal["open"] === "function") cal["open"]()
            else cal.visible = true
        })
    }

    placeholderText: ""
    color: control.isProMode ? control.tokenInk : control.textColor
    font.pixelSize: ratioPx(scaleRatios.textSizePct, metricFloor("fontFloorBodyPx", 10))
    
    leftPadding: ratioPx(scaleRatios.padSidePct, 4)
    rightPadding: leftPadding
    topPadding: control.hasLabel
        ? Math.max(
            ratioPx(scaleRatios.padTopPct, 4),
            fieldLabel.font.pixelSize + ratioPx(0.0040, 2)
        )
        : ratioPx(scaleRatios.padTopPct, 4)
    bottomPadding: ratioPx(scaleRatios.padBottomPct, 2)

    background: Item {
        DropShadow {
            visible: visualRules.shadowOpacity > 0
            anchors.fill: fieldBg
            source: fieldBg
            horizontalOffset: 0
            verticalOffset: 0
            radius: control.isProMode ? visualRules.radiusControl : control.ratioPx(control.scaleRatios.radiusPct * 1.8, 4)
            samples: control.ratioPx(control.scaleRatios.radiusPct * 4.0, 10)
            color: Qt.rgba(
                control.accentColor.r,
                control.accentColor.g,
                control.accentColor.b,
                control.activeFocus ? 0.22 : 0.0
            )
            transparentBorder: true
        }

        Rectangle {
            id: fieldBg
            anchors.fill: parent
            color: control.isProMode
                ? control.tokenInput
                : Qt.rgba(
                    (control.panelColor.r * 0.78) + (control.accentColor.r * 0.22),
                    (control.panelColor.g * 0.78) + (control.accentColor.g * 0.22),
                    (control.panelColor.b * 0.78) + (control.accentColor.b * 0.22),
                    control.activeFocus ? 0.95 : 0.91
                )
            radius: control.isProMode ? visualRules.radiusControl : control.ratioPx(control.scaleRatios.radiusPct, 2)
            border.width: control.activeFocus
                ? Math.max(2, control.ratioPx(control.scaleRatios.focusBorderPct, 1))
                : control.ratioPx(control.scaleRatios.idleBorderPct, 1)
            border.color: control.activeFocus
                ? Qt.rgba(
                    control.tokenAccent.r,
                    control.tokenAccent.g,
                    control.tokenAccent.b,
                    0.84
                )
                : (control.isProMode
                    ? control.tokenBorder
                    : Qt.rgba(
                        control.textColor.r,
                        control.textColor.g,
                        control.textColor.b,
                        0.40
                    ))
            Behavior on border.color { ColorAnimation { duration: 150 } }
        }
    }

    Text {
        id: fieldLabel
        text: control.label
        visible: control.hasLabel
        color: control.isProMode
            ? control.tokenInk
            : control.textColor
        font.pixelSize: control.ratioPx(control.scaleRatios.labelFontPct, control.metricFloor("fontFloorLabelPx", 8))
        font.weight: Font.DemiBold
        anchors.left: parent.left
        anchors.leftMargin: control.ratioPx(control.scaleRatios.labelLeftMarginPct, 4)
        anchors.right: parent.right
        anchors.rightMargin: control.rightPadding + control.ratioPx(0.0040, 4)
        anchors.top: parent.top
        anchors.topMargin: control.ratioPx(control.scaleRatios.labelTopMarginPct, 2)
        clip: true
        maximumLineCount: 1
        wrapMode: Text.NoWrap
        elide: Text.ElideRight
        z: 10
        layer.enabled: false
    }

    Loader {
        id: datePickerLoader
        active: false
        sourceComponent: Component {
            JellyCalendar {
                visible: false
                t: control.t
                metrics: control.metrics
                hostWindow: control.Window.window
                onDatePicked: function(d) {
                    var iso = Qt.formatDate(d, "yyyy-MM-dd")
                    control.text = iso
                    control.datePickerDatePicked(d, iso)
                    datePickerLoader.active = false
                }
            }
        }
    }

    TapHandler {
        enabled: control.datePickerEnabled
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: function(eventPoint) {
            var p = control.mapToGlobal(eventPoint.position.x, eventPoint.position.y)
            control.openDatePickerAt(p.x, p.y)
        }
    }
}
