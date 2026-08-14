pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Button {
    id: control
    property var t
    property var metrics
    property var sfxBus: null
    property bool primary: false
    // Opt-in scale for dense action strips.  Views use this together with a
    // smaller control footprint so the label remains proportionate.
    property real textScale: 1.0
    property string iconSource: ""
    property string tooltipText: ""
    text: "Button"
    hoverEnabled: true
    property string appStyle: ((typeof app !== "undefined") && app !== null && app.appStyle)
        ? String(app.appStyle)
        : "Professional"
    property var scaleRatios: ({
        "contentSpacingPct": 0.010,
        "iconSizePct": 0.020,
        "textSizePct": 0.016,
        "secondaryBorderPct": 0.0022,
        "shadowRadiusPct": 0.0085,
        "shadowSamplesPct": 0.018,
        "shadowYOffsetPct": 0.0022
    })

    // Coerce theme strings to real QML colors so .r/.g/.b works reliably.
    property color accentColor: (t && t.accent) ? t.accent : "#4A6DA8"
    property color panelColor: (t && t.panel) ? t.panel : "#0B1324"
    property color textColor: (t && t.text) ? t.text : "#FFFFFF"
    property color proAccent: SemanticTheme.accentPrimary(control.t, control.appStyle)
    property color proInk: SemanticTheme.inkPrimary(control.t, control.appStyle)
    property color proSecondaryFill: SemanticTheme.surfaceRaised(control.t, control.appStyle)
    property color proSecondaryHoverFill: SemanticTheme.surfaceInput(control.t, control.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(control.t, control.appStyle)

    VisualRules {
        id: visualRules
        appStyle: control.appStyle
    }

    // If accent is too light (e.g., Slate Gray), soften/darken the PRIMARY fill slightly
    // to reduce glare and avoid "white-on-light-grey" jarring look.
    property real accentLum: (accentColor.r * 0.299 + accentColor.g * 0.587 + accentColor.b * 0.114)
    property color primaryFill: (accentLum > 0.72) ? Qt.darker(accentColor, 1.18) : accentColor

    // Pick ink based on the actual fill color (post-soften)
    property real fillLum: (primaryFill.r * 0.299 + primaryFill.g * 0.587 + primaryFill.b * 0.114)
    property color primaryInk: (fillLum > 0.62) ? "#111111" : "#FFFFFF"
    property color primaryHoverFill: (fillLum > 0.62)
        ? Qt.darker(primaryFill, 1.04)
        : Qt.lighter(primaryFill, 1.06)
    property bool jellyHover: hovered && enabled && !down
    readonly property bool isProMode: visualRules.isPro
    property real jellyXScale: (!visualRules.hoverScaleEnabled || !enabled) ? 1.0 : (down ? 1.01 : (jellyHover ? 1.03 : 1.0))
    property real jellyYScale: (!visualRules.hoverScaleEnabled || !enabled) ? 1.0 : (down ? 0.96 : (jellyHover ? 0.98 : 1.0))

    onHoveredChanged: {
        if (!hovered) return
        if (sfxBus && sfxBus.playUiClick) {
            sfxBus.playUiClick("tile-hover", 0.24)
        }
    }

    transform: Scale {
        origin.x: control.width / 2
        origin.y: control.height / 2
        xScale: control.jellyXScale
        yScale: control.jellyYScale
    }
    Behavior on jellyXScale {
        NumberAnimation {
            duration: control.down ? visualRules.motionFast : visualRules.motionNormal
            easing.type: control.down ? Easing.OutCubic : Easing.OutBack
        }
    }
    Behavior on jellyYScale {
        NumberAnimation {
            duration: control.down ? visualRules.motionFast : visualRules.motionNormal
            easing.type: control.down ? Easing.OutCubic : Easing.OutBack
        }
    }

    function ratioPx(ratio, minPx) {
        var rw = control.width
        var rh = control.height
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

    // CONTENT
    contentItem: Item {
        id: contentHost
        anchors.fill: parent
        readonly property int iconSpace: (control.iconSource !== "") ? (iconGlyph.width + control.ratioPx(control.scaleRatios.contentSpacingPct, 2)) : 0
        Row {
            anchors.centerIn: parent
            spacing: control.ratioPx(control.scaleRatios.contentSpacingPct, 2)

            // ICON
            Image {
                id: iconGlyph
                source: control.iconSource
                width: control.ratioPx(control.scaleRatios.iconSizePct, 8)
                height: width
                visible: control.iconSource !== ""
                sourceSize: Qt.size(width * 2, height * 2)
                anchors.verticalCenter: parent.verticalCenter

                ColorOverlay {
                    anchors.fill: parent
                    source: parent
                    color: control.isProMode
                        ? (control.primary ? SemanticTheme.readableInk(control.proAccent) : control.proInk)
                        : (control.primary ? control.primaryInk : control.accentColor)
                }
            }

            // TEXT
            Text {
                text: control.text
                font.pixelSize: Math.max(
                    control.metricFloor("fontFloorLabelPx", 8),
                    Math.round(control.ratioPx(control.scaleRatios.textSizePct, control.metricFloor("fontFloorBodyPx", 9)) * control.textScale)
                )
                font.weight: Font.Bold
                color: control.isProMode
                    ? (control.primary ? SemanticTheme.readableInk(control.proAccent) : control.proInk)
                    : (control.primary ? control.primaryInk : control.textColor)
                width: Math.max(1, control.width - control.ratioPx(0.022, 16) - contentHost.iconSpace)
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                fontSizeMode: Text.Fit
                minimumPixelSize: Math.max(7, control.metricFloor("fontFloorLabelPx", 8) - 1)
            }
        }
    }

    // BACKGROUND
    background: Rectangle {
        radius: control.isProMode ? visualRules.radiusControl : height / 2

        // Primary: softened accent fill. Secondary: transparent.
        color: control.isProMode
               ? (control.primary
                   ? (control.down ? Qt.darker(control.proAccent, 1.16) : (control.hovered ? Qt.lighter(control.proAccent, 1.08) : control.proAccent))
                   : (control.hovered ? control.proSecondaryHoverFill : control.proSecondaryFill))
               : (control.primary
                   ? (control.down
                       ? Qt.darker(control.primaryFill, 1.06)
                       : (control.hovered ? control.primaryHoverFill : control.primaryFill))
                   : control.hovered ? SemanticTheme.buttonHover(control.t, control.appStyle) : control.panelColor)

        border.width: control.primary ? 0 : control.ratioPx(control.scaleRatios.secondaryBorderPct, 1)
        border.color: control.primary
                      ? "transparent"
                      : (control.isProMode
                         ? control.proBorder
                         : (control.hovered
                            ? SemanticTheme.buttonBackground(control.t, control.appStyle)
                            : SemanticTheme.inkMuted(control.t, control.appStyle)))

        // Neutral shadow only (no neon glow on buttons)
        layer.enabled: !control.down && visualRules.shadowOpacity > 0
        layer.effect: DropShadow {
            transparentBorder: true
            color: control.hovered
                ? SemanticTheme.borderSubtle(control.t, control.appStyle)
                : SemanticTheme.borderSubtle(control.t, control.appStyle)
            radius: control.ratioPx(control.scaleRatios.shadowRadiusPct, 1)
            samples: control.ratioPx(control.scaleRatios.shadowSamplesPct, 5)
            horizontalOffset: 0
            verticalOffset: control.ratioPx(control.scaleRatios.shadowYOffsetPct, 1)
        }
    }

    ToolTip.visible: control.hovered && String(control.tooltipText || "").length > 0
    ToolTip.delay: 260
    ToolTip.text: String(control.tooltipText || "")
}
