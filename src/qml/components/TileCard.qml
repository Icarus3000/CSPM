import QtQuick
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

Rectangle {
    id: root
    property var metrics
    property var scaleRatios: ({
        "implicitWidthPct": 0.196,
        "implicitHeightPct": 0.239,
        "cornerRadiusPct": 0.017,
        "borderWidthPct": 0.0011,
        "contentSpacingPct": 0.022,
        "iconSizePct": 0.091,
        "textSizePct": 0.035,
        "textInsetPct": 0.026
    })
    function ratioPx(ratio, minPx) {
        // Avoid binding loops: implicit tile size must not be derived from tile width/height.
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

    property int baseIconPx: ratioPx(scaleRatios.iconSizePct, metricFloor("fontFloorIconPx", 16))
    property int baseTextPx: ratioPx(scaleRatios.textSizePct, metricFloor("fontFloorBodyPx", 8))
    property int textInsetPx: ratioPx(scaleRatios.textInsetPct, 4)
    property int textMinPx: Math.max(6, metricFloor("fontFloorLabelPx", 7) - 1)
    property int iconPx: Math.max(10, Math.min(baseIconPx, Math.round(Math.min(root.width, root.height) * 0.34)))
    property int contentWidthPx: Math.max(1, root.width - (textInsetPx * 2))
    
    implicitWidth: ratioPx(scaleRatios.implicitWidthPct, 80)
    implicitHeight: ratioPx(scaleRatios.implicitHeightPct, 96)
    
    property var t
    property var sfxBus: null
    property string text: "Module"
    property string iconSource: "" 
    property bool isHovered: ma.containsMouse
    property bool maximized: false 
    property real hoverScaleX: 1.10
    property real hoverScaleY: 0.90
    property int hoverSquashDurationMs: 130
    property int hoverReleaseDurationMs: 210
    
    signal clicked(var globalGeom)

    onIsHoveredChanged: {
        if (!isHovered) return
        if (sfxBus && sfxBus.playUiClick) {
            sfxBus.playUiClick("hover", 0.30)
        }
    }

    // LAYER 3: THE TILES
    // CRITICAL FIX: Uses the Layer 3 'panel2' color from your theme.
    color: isHovered ? ((t && t.hover) ? t.hover : "#444") : ((t && t.panel2) ? t.panel2 : "#222")
    
    border.width: ratioPx(scaleRatios.borderWidthPct, 1)
    border.color: isHovered ? t.accent : Qt.rgba(t.text.r, t.text.g, t.text.b, 0.15)
    radius: ratioPx(scaleRatios.cornerRadiusPct, 2)
    
    transform: Scale { 
        id: tileScale 
        origin.x: root.width / 2 
        origin.y: root.height / 2 
        xScale: root.isHovered ? root.hoverScaleX : 1.0
        yScale: root.isHovered ? root.hoverScaleY : 1.0
        Behavior on xScale {
            NumberAnimation {
                duration: root.isHovered ? root.hoverSquashDurationMs : root.hoverReleaseDurationMs
                easing.type: root.isHovered ? Easing.OutCubic : Easing.OutBack
            }
        }
        Behavior on yScale {
            NumberAnimation {
                duration: root.isHovered ? root.hoverSquashDurationMs : root.hoverReleaseDurationMs
                easing.type: root.isHovered ? Easing.OutCubic : Easing.OutBack
            }
        }
    }

    Item {
        id: centeredContent
        anchors.centerIn: parent
        width: root.contentWidthPx
        height: contentCol.implicitHeight

        Column {
            id: contentCol
            anchors.centerIn: parent
            width: centeredContent.width
            spacing: ratioPx(root.root.scaleRatios.contentSpacingPct, 4)

            Text {
                width: contentCol.width
                text: root.iconSource
                font.family: "Segoe MDL2 Assets"
                font.pixelSize: root.root.maximized ? Math.round(root.iconPx * 1.18) : root.iconPx
                color: root.isHovered ? root.t.accent : t.text
                opacity: root.isHovered ? 1.0 : 0.95
                horizontalAlignment: Text.AlignHCenter
            }

            Text {
                width: contentCol.width
                text: root.text
                color: root.root.t.text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: root.textMinPx
                font.pixelSize: root.root.maximized ? Math.round(root.baseTextPx * 1.125) : root.baseTextPx
                font.weight: Font.DemiBold
                opacity: 0.95
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            var globalPos = root.mapToGlobal(0, 0)
            root.clicked(Qt.rect(globalPos.x, globalPos.y, root.width, root.height))
        }
    }
    
    Behavior on color { ColorAnimation { duration: 150 } }
}
