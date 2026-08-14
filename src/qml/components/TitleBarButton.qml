import QtQuick
import QtQuick.Controls
import "../standards/SemanticTheme.js" as SemanticTheme

Button {
    id: control
    property var t
    property string appStyle: "Professional"
    property var metrics
    property int fontSize: -1
    property real sizeScale: 1.0
    property bool danger: false
    property color baseTextColor: (control.t && control.t.text) ? control.t.text : "#FFFFFF"
    property color accentColor: (control.t && control.t.accent) ? control.t.accent : "#4FC3F7"
    property color dangerColor: SemanticTheme.tone(control.t, "danger")
    property color dangerFill: SemanticTheme.surface(control.t, "tooltip", "danger")
    property color dangerBorder: SemanticTheme.border(control.t, "tooltip", "danger")
    property color dangerInk: SemanticTheme.ink(control.t, "tooltip", "danger")
    property var scaleRatios: ({
        "buttonSizePct": 0.061,
        "fontSizePct": 0.030
    })

    function ratioPx(ratio, minPx) {
        // Avoid binding loops: implicit size uses buttonSizePx, so this helper
        // must not depend on control.width/control.height.
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

    function luma(c) {
        return ((0.299 * c.r) + (0.587 * c.g) + (0.114 * c.b))
    }

    function nonDangerHoverColor() {
        var acc = accentColor
        var base = baseTextColor
        if (Math.abs(luma(acc) - luma(base)) < 0.18) {
            return (luma(base) > 0.5) ? Qt.darker(base, 1.8) : Qt.lighter(base, 1.8)
        }
        return acc
    }

    property color hoverIconColor: danger ? dangerColor : nonDangerHoverColor()

    property real dpiScaleFactor: (metrics && typeof metrics.scalePercent === "number")
        ? Math.max(1.0, metrics.scalePercent / 100.0)
        : 1.0
    property real dpiCompFactor: 1.0
    property int buttonSizePx: Math.max(20, Math.round(ratioPx(scaleRatios.buttonSizePct, 24) * Math.max(0.75, sizeScale)))
    property int autoFontSizePx: Math.max(9, Math.round(ratioPx(scaleRatios.fontSizePct, metricFloor("fontFloorIconPx", 12)) * Math.max(0.75, sizeScale)))

    implicitWidth: buttonSizePx
    implicitHeight: buttonSizePx
    padding: 0
    hoverEnabled: true

    background: Rectangle {
        radius: Math.max(1, Math.round(control.buttonSizePx * 0.28))
        color: control.down
            ? (control.danger
                ? SemanticTheme.alpha(control.dangerFill, 0.90)
                : SemanticTheme.alpha(control.accentColor, 0.30))
            : (control.hovered
            ? (control.danger
                ? control.dangerFill
                : SemanticTheme.hoverOverlay(control.t, control.appStyle))
            : "transparent")
        border.width: (control.hovered || control.down) ? Math.max(1, Math.round(control.buttonSizePx * 0.03)) : 0
        border.color: control.danger
            ? control.dangerBorder
            : SemanticTheme.border(control.t, "tooltip", "neutral")
        Behavior on color { ColorAnimation { duration: 45 } }
    }

    contentItem: Item {
        implicitWidth: control.buttonSizePx
        implicitHeight: control.buttonSizePx
        
        Text {
            anchors.centerIn: parent
            text: control.text
            font.pixelSize: control.fontSize > 0 ? control.fontSize : control.autoFontSizePx
            color: (control.hovered || control.down)
                ? (control.danger ? control.dangerInk : control.hoverIconColor)
                : control.baseTextColor
            opacity: control.down ? 0.7 : 1.0
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Behavior on color { ColorAnimation { duration: 100 } }
        }
    }
}
