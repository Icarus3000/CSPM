import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Button {
    id: b
    property var t
    property string appStyle: "Professional"
    property var metrics
    property bool primary: false
    property var scaleRatios: ({
        "heightPct": 0.141,
        "fontPct": 0.017,
        "cornerPct": 0.024,
        "borderPct": 0.0022,
        "shadowRadiusPct": 0.020,
        "shadowSamplesPct": 0.027,
        "contentInsetPct": 0.020
    })

    function ratioPx(ratio, minPx) {
        var rw = width
        var rh = height
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            rw = metrics.contentW
            rh = metrics.contentH
        }
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

    height: ratioPx(scaleRatios.heightPct, 48)
    font.pixelSize: ratioPx(scaleRatios.fontPct, metricFloor("fontFloorLabelPx", 8))
    font.weight: Font.DemiBold

    background: Rectangle {
        id: bg
        radius: b.ratioPx(b.scaleRatios.cornerPct, 4)
        color: b.primary ? b.t.accent : SemanticTheme.borderSubtle(b.t, "Professional")
        border.width: b.primary ? 0 : b.ratioPx(b.scaleRatios.borderPct, 1)
        border.color: b.primary ? "transparent" : b.t.accent
    }

    // subtle inner glow for non-primary tiles (optional but nice)
    DropShadow {
        anchors.fill: bg
        source: bg
        horizontalOffset: 0
        verticalOffset: 0
        radius: b.ratioPx(b.scaleRatios.shadowRadiusPct, 3)
        samples: b.ratioPx(b.scaleRatios.shadowSamplesPct, 8)
        spread: 0.12
        color: SemanticTheme.borderSubtle(b.t, "Professional")
        transparentBorder: true
        visible: !b.primary
    }

    contentItem: Text {
        text: b.text
        color: b.primary ? b.t.btn_text : b.t.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        width: b.width - b.ratioPx(b.scaleRatios.contentInsetPct, 6)
    }
}
