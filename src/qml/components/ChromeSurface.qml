import QtQuick
import QtQuick.Effects
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    anchors.fill: parent
    property bool roundedSurfaceMaskEnabled: cornerRadius > 0
    layer.enabled: roundedSurfaceMaskEnabled
    layer.smooth: true
    layer.effect: MultiEffect {
        maskEnabled: root.roundedSurfaceMaskEnabled
        maskSource: surfaceMaskRect
        maskThresholdMin: 0.74
        maskSpreadAtMin: 0.10
        autoPaddingEnabled: false
    }

    property var t
    property string appStyle: "Professional"
    property var metrics: null
    property real cornerRadius: 16
    property real contentInset: 0
    property color frameColor: t ? SemanticTheme.windowChrome(t, appStyle) : "#000000"
    property color glowColor: t ? SemanticTheme.accentPrimary(t, appStyle) : "#FF1744"
    property color borderColor: t ? SemanticTheme.borderStrong(t, appStyle) : Qt.rgba(1, 1, 1, 0.1)
    property real borderWidth: _ratioPx(0.0011, 1)
    property real borderOpacity: 1.0

    // Properties requested by Main.qml (Restored to prevent crashes)
    property bool farGlowEnabled: true
    property real glowRadiusFar: _ratioPx(0.039, 1)
    property real glowRadiusNear: _ratioPx(0.019, 1)
    property real glowOpacityFar: 0.8
    property real glowOpacityNear: 1.0
    property real plasmaOpacity: 1.0
    property real plasmaRadius: _ratioPx(0.019, 1)
    property bool cacheEnabled: false
    property bool lowFxMode: false
    property real glowSpreadLowPx: _ratioPx(0.019, 1)
    property real glowSpreadHighPx: _ratioPx(0.049, 1)
    property real glowStrokeLowPx: _ratioPx(0.0087, 1)
    property real glowStrokeHighPx: _ratioPx(0.0196, 1)
    property real innerInsetPx: _ratioPx(0.0011, 1)
    property real innerBorderPx: _ratioPx(0.0011, 1)
    property real hairlineBorderPx: Math.max(0.5, _ratioPx(0.0005, 1))
    property real interactionBoost: 0.05
    property bool premiumEdgeEnabled: true
    property bool flairEnabled: true
    property real flairPhase: 0.0
    // Safety switch retained for compatibility; rounded clipping uses a real alpha mask.
    property bool roundedContentMaskEnabled: true

    default property alias content: contentHost.data

    function forensicCornerSummary() {
        var rootW = Math.max(1, Math.round(root.width))
        var rootH = Math.max(1, Math.round(root.height))
        var baseR = Math.max(0, Math.round(root.cornerRadius))

        function layerBleeds(item, layerRadius) {
            if (!item) return false
            if (!item.visible || item.opacity <= 0.001) return false
            var x = Math.round(item.x)
            var y = Math.round(item.y)
            var w = Math.max(1, Math.round(item.width))
            var h = Math.max(1, Math.round(item.height))
            var extendsBounds = (x < 0) || (y < 0) || ((x + w) > rootW) || ((y + h) > rootH)
            var r = -1
            if (typeof layerRadius === "number" && isFinite(layerRadius)) {
                r = Math.max(0, Math.round(layerRadius))
            }
            var radiusTooSmall = (r >= 0) && (r < baseR)
            return extendsBounds || radiusTooSmall
        }

        var glowMargin = Math.round(glowSource.anchors.margins)
        var glowMasked = glowEffect && glowEffect.maskEnabled
        // Flag only true geometric overspill beyond the shell footprint.
        var glowBleed = glowEffect.visible
            && glowEffect.opacity > 0.001
            && glowMargin < -1
            && !glowMasked
        var mainBleed = layerBleeds(mainPanel, mainPanel.radius)
        var contentBleed = layerBleeds(contentClipper, contentClipper.radius)
        var borderBleed = layerBleeds(outerBorder, outerBorder.radius)

        return "glow=" + (glowBleed ? "1" : "0")
            + "@m" + glowMargin
            + "@k" + (glowMasked ? "1" : "0")
            + "@b" + Math.round(glowEffect.blur * 100)
            + " main=" + (mainBleed ? "1" : "0")
            + " content=" + (contentBleed ? "1" : "0")
            + " border=" + (borderBleed ? "1" : "0")
            + " baseR=" + baseR
    }

    function _toBlur(px) { return Math.min(1.0, px / 64.0); }
    function _clamp01(v) { return Math.max(0.0, Math.min(1.0, v)); }
    function _metricUnit() {
        var cw = root.width
        var ch = root.height
        if (metrics && typeof metrics.contentW === "number" && typeof metrics.contentH === "number") {
            cw = metrics.contentW
            ch = metrics.contentH
        }
        return Math.min(Math.max(1, cw), Math.max(1, ch))
    }
    function _ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(_metricUnit() * ratio))
    }
    function _edgeEnergy() {
        var base = (root.lowFxMode ? 0.58 : 0.72) * root._clamp01(root.plasmaOpacity)
        return root._clamp01(base + root.interactionBoost)
    }

    SequentialAnimation on flairPhase {
        loops: Animation.Infinite
        running: root.flairEnabled && !root.lowFxMode
        NumberAnimation { from: 0.0; to: 1.0; duration: 2600; easing.type: Easing.InOutSine }
        NumberAnimation { from: 1.0; to: 0.0; duration: 3000; easing.type: Easing.InOutSine }
    }

    Rectangle {
        id: surfaceMaskRect
        anchors.fill: parent
        radius: Math.max(0, root.cornerRadius)
        color: "black"
        visible: false
        antialiasing: true
        smooth: true
        layer.enabled: true
    }

    // 1. THE GLOW SOURCE - Primary glow layer
    Rectangle {
        id: glowSource
        anchors.fill: parent
        // Keep glow mostly inside the shell bounds so rounded corner masking stays clean.
        anchors.margins: -Math.max(
            0,
            Math.min(
                root._ratioPx(0.0042, 4),
                root.lowFxMode
                    ? (root.glowSpreadLowPx * 0.62)
                    : (root.glowSpreadHighPx * (0.66 + (0.18 * root._edgeEnergy())))
            )
        )
        radius: root.cornerRadius
        color: "transparent"
        border.width: root.lowFxMode ? root.glowStrokeLowPx * 0.66 : root.glowStrokeHighPx * (0.48 + (0.12 * root._edgeEnergy()))
        border.color: root.glowColor
        visible: false 
    }

    Rectangle {
        id: glowMaskRect
        anchors.fill: parent
        radius: Math.max(0, root.cornerRadius)
        color: "black"
        visible: false
        antialiasing: true
        smooth: true
        layer.enabled: true
    }

    // Core glow pass (single halo)
    MultiEffect {
        id: glowEffect
        anchors.fill: parent
        source: glowSource
        z: -2
        autoPaddingEnabled: false
        maskEnabled: true
        maskSource: glowMaskRect
        maskThresholdMin: 0.74
        maskSpreadAtMin: 0.10
        visible: root.farGlowEnabled && root.plasmaOpacity > 0.001
        opacity: root.farGlowEnabled
            ? (root.lowFxMode
                ? (0.13 + (0.15 * root._edgeEnergy()))
                : (0.22 + (0.28 * root._edgeEnergy())))
            : 0
        blurEnabled: !root.lowFxMode
        blurMax: 64
        blur: _toBlur(root.glowRadiusFar * (1.10 + (0.18 * root._edgeEnergy())))
        colorization: 1.0
        colorizationColor: root.glowColor
        brightness: 0.16 + (0.15 * root._edgeEnergy())
        contrast: 0.03 + (0.06 * root._edgeEnergy())
    }
    // 2. THE WINDOW BODY
    Rectangle {
        id: mainPanel
        anchors.fill: parent
        radius: root.cornerRadius
        color: root.frameColor
        z: -1
        antialiasing: true
        
        // Directional light model: top/left edge highlights + bottom/right shadow.
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root._ratioPx(0.012, 2)
            radius: 0
            color: "transparent"
            visible: root.premiumEdgeEnabled
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop {
                    position: 0.0
                    color: Qt.rgba(1, 1, 1, (root.lowFxMode ? 0.07 : 0.11) + (0.08 * root._edgeEnergy()))
                }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: root._ratioPx(0.010, 2)
            radius: 0
            color: "transparent"
            visible: root.premiumEdgeEnabled
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop {
                    position: 0.0
                    color: Qt.rgba(1, 1, 1, (root.lowFxMode ? 0.06 : 0.09) + (0.06 * root._edgeEnergy()))
                }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: root._ratioPx(0.012, 2)
            radius: 0
            color: "transparent"
            visible: root.premiumEdgeEnabled
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop {
                    position: 1.0
                    color: Qt.rgba(0, 0, 0, (root.lowFxMode ? 0.12 : 0.20) + (0.08 * root._edgeEnergy()))
                }
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: root._ratioPx(0.010, 2)
            radius: 0
            color: "transparent"
            visible: root.premiumEdgeEnabled
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop {
                    position: 1.0
                    color: Qt.rgba(0, 0, 0, (root.lowFxMode ? 0.10 : 0.16) + (0.07 * root._edgeEnergy()))
                }
            }
        }

        // Keep only the primary body contour; inner double rims created a false "inner frame" effect.
    }

    Rectangle {
        id: contentMaskRect
        x: root.contentInset
        y: root.contentInset
        width: Math.max(1, root.width - (root.contentInset * 2))
        height: Math.max(1, root.height - (root.contentInset * 2))
        radius: Math.max(0, root.cornerRadius - root.contentInset)
        color: "black"
        visible: false
        antialiasing: true
        smooth: true
        layer.enabled: true
    }

    // 3. THE UI CONTENT - enforce rounded clip with alpha mask so outer shell corners never render square.
    Rectangle {
        id: contentClipper
        anchors.fill: parent
        anchors.margins: root.contentInset
        radius: Math.max(0, root.cornerRadius - root.contentInset)
        color: "transparent"
        clip: false
        antialiasing: true
        z: 1

        Item {
            id: contentHost
            anchors.fill: parent
            clip: false
            layer.enabled: root.roundedContentMaskEnabled && root.cornerRadius > 0
            layer.smooth: true
            layer.effect: MultiEffect {
                maskEnabled: root.roundedContentMaskEnabled && root.cornerRadius > 0
                maskSource: contentMaskRect
                maskThresholdMin: 0.74
                maskSpreadAtMin: 0.10
            }
        }
    }

    // 4. THE OUTER BORDER (minimal, for definition only)
    Rectangle {
        anchors.fill: parent
        radius: root.cornerRadius
        color: "transparent"
        border.width: root.hairlineBorderPx
        border.color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, 1.0)
        opacity: (root.lowFxMode ? 0.07 : 0.10) + (0.06 * root._edgeEnergy())
        z: 2
        antialiasing: true
        id: outerBorder
    }
}
