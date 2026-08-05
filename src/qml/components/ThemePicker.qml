pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Popup {
    id: root
    property real uiScaleBoost: 1.08
    property var metrics
    property var t
    property var appRef: null
    property var names: []
    property var sfxBus: null
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: visualRules.isPro
    property color popupSurface: SemanticTheme.surface(root.t, "dialog", "neutral", root.appStyle)
    property color closeFill: SemanticTheme.surface(root.t, "tooltip", "neutral", root.appStyle)
    property color popupInk: SemanticTheme.ink(root.t, "dialog", "neutral", root.appStyle)
    property color closeInk: SemanticTheme.ink(root.t, "tooltip", "neutral", root.appStyle)
    property var scaleRatios: ({
        "popupWidthPct": 0.213,
        "popupHeightPct": 0.478,
        "popupMinWidthPct": 0.148,
        "popupMinHeightPct": 0.261,
        "cornerRadiusPct": 0.017,
        "layoutMarginPct": 0.022,
        "layoutSpacingPct": 0.016,
        "titleFontPct": 0.020,
        "titleFontFloorPct": 0.015,
        "dividerHeightPct": 0.0011,
        "rowSpacingPct": 0.0087,
        "rowHeightPct": 0.048,
        "rowRadiusPct": 0.0087,
        "dotSizePct": 0.017,
        "dotRadiusPct": 0.0087,
        "rowInsetPct": 0.017,
        "labelFontPct": 0.016,
        "labelFontFloorPct": 0.012,
        "closeHeightPct": 0.043,
        "closeFontPct": 0.015,
        "closeFontFloorPct": 0.012
    })

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function contentW() {
        if (metrics && typeof metrics.contentW === "number") {
            return Math.max(1, Math.round(metrics.contentW))
        }
        if (root.parent && typeof root.parent.width === "number") {
            return Math.max(1, Math.round(root.parent.width))
        }
        return Math.max(1, Math.round(root.width))
    }

    function contentH() {
        if (metrics && typeof metrics.contentH === "number") {
            return Math.max(1, Math.round(metrics.contentH))
        }
        if (root.parent && typeof root.parent.height === "number") {
            return Math.max(1, Math.round(root.parent.height))
        }
        return Math.max(1, Math.round(root.height))
    }

    function contentUnit() {
        return Math.min(contentW(), contentH())
    }

    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentUnit() * ratio * uiScaleBoost))
    }

    function ratioPxW(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentW() * ratio * uiScaleBoost))
    }

    function ratioPxH(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentH() * ratio * uiScaleBoost))
    }

    function metricFloor(metricKey, fallbackPx) {
        var baseFloor = Math.max(1, Math.round(fallbackPx))
        if (metrics && typeof metrics[metricKey] === "number") {
            baseFloor = Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(baseFloor * uiScaleBoost))
    }

    function playUiClick(kind, strengthNorm) {
        if (!sfxBus || !sfxBus.playUiClick) return
        var s = isFinite(strengthNorm) ? strengthNorm : 0.46
        sfxBus.playUiClick(kind, Math.max(0.0, Math.min(1.0, s)))
    }
    function luma(colorValue) {
        if (!colorValue || typeof colorValue.r !== "number") return 0.0
        return (colorValue.r * 0.299) + (colorValue.g * 0.587) + (colorValue.b * 0.114)
    }
    function readableInk(fillColor) {
        return luma(fillColor) >= 0.60
            ? Qt.rgba(0.07, 0.09, 0.13, 0.98)
            : Qt.rgba(0.98, 0.99, 1.0, 0.98)
    }

    width: {
        var idealW = Math.max(
            ratioPxW(scaleRatios.popupMinWidthPct, 1),
            ratioPxW(scaleRatios.popupWidthPct, 1)
        )
        var maxW = (root.parent && typeof root.parent.width === "number") ? Math.max(200, root.parent.width - 40) : 400
        return Math.min(idealW, maxW)
    }
    height: Math.max(
        ratioPxH(scaleRatios.popupMinHeightPct, 1),
        ratioPxH(scaleRatios.popupHeightPct, 1)
    )
    
    modal: true
    focus: true
    dim: false
    
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    
    signal picked(string name, var payload)

    property var themeColors: {
        "Light": "#FFFFFF",
        "Dark": "#202124"
    }
    property var fallbackThemePayloads: ({
        "Light": { "bg": "#FFFFFF", "panel": "#F9FAFB", "panel2": "#F1F3F5", "accent": "#0E1116", "hover": "#E1E5EA", "text": "#0B0D10", "muted": "#5A626F", "btn_text": "#FFFFFF", "glow": "#1D2128" },
        "Dark": { "bg": "#040405", "panel": "#0E0F11", "panel2": "#181A1E", "accent": "#F8FAFC", "hover": "#2A2D33", "text": "#F5F7FA", "muted": "#A4AAB4", "btn_text": "#050506", "glow": "#FFFFFF" }
    })
    readonly property var fallbackThemeNames: [
        "Light",
        "Dark"
    ]
    readonly property var resolvedThemeNames: {
        var source = root.names;
        if (!source || typeof source.length !== "number" || source.length === 0) {
            source = root.fallbackThemeNames;
        }
        var result = [];
        for (var i = 0; i < source.length; i++) {
            var name = String(source[i] !== undefined && source[i] !== null ? source[i] : "").trim();
            if (!name.length) continue;
            if (result.indexOf(name) >= 0) continue;
            result.push(name);
        }
        if (result.length === 0) {
            return root.fallbackThemeNames;
        }
        return result;
    }
    function swatchColorForName(themeName, payload) {
        var resolvedName = String(themeName === undefined || themeName === null ? "" : themeName).trim()
        if (resolvedName.length) {
            if (root.themeColors[resolvedName]) {
                return root.themeColors[resolvedName]
            }
            var lowered = resolvedName.toLowerCase()
            var keys = Object.keys(root.themeColors)
            for (var i = 0; i < keys.length; i++) {
                var keyName = String(keys[i]).trim()
                if (keyName.toLowerCase() === lowered) {
                    return root.themeColors[keyName]
                }
            }
        }
        if (payload && payload.bg) {
            return payload.bg
        }
        if (payload && payload.accent) {
            return payload.accent
        }
        return "#888"
    }
    function themePayloadForName(themeName) {
        var resolvedName = String(themeName === undefined || themeName === null ? "" : themeName).trim()
        if (!resolvedName.length) return ({})
        try {
            if (root.appRef && root.appRef.getThemeByName) {
                var livePayload = root.appRef.getThemeByName(resolvedName)
                if (livePayload && livePayload.bg) return livePayload
            }
        } catch (e) {
        }
        var fallback = root.fallbackThemePayloads[resolvedName]
        if (fallback && fallback.bg) return fallback
        return ({})
    }

    background: SemanticPanel {
        t: root.t
        appStyle: root.appStyle
        role: "dialog"
        tone: "neutral"
        radius: root.isProMode ? visualRules.radiusPopup : root.ratioPx(root.scaleRatios.cornerRadiusPct, 1)
        borderWidth: root.ratioPx(root.scaleRatios.dividerHeightPct, 1)
        shadowEnabled: !root.isProMode
        shadowRadius: root.isProMode ? 0 : root.ratioPx(root.scaleRatios.popupHeightPct * 0.073, 1)
        shadowSamples: root.isProMode ? 1 : root.ratioPx(root.scaleRatios.popupWidthPct * 0.092, 1)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.ratioPx(root.scaleRatios.layoutMarginPct, 1)
        spacing: root.ratioPx(root.scaleRatios.layoutSpacingPct, 1)

        Text {
            text: "Select Theme"
            color: root.popupInk
            font.pixelSize: root.ratioPx(
                root.scaleRatios.titleFontPct,
                root.metricFloor("fontFloorTitlePx", root.ratioPx(root.scaleRatios.titleFontFloorPct, 1))
            )
            font.weight: Font.Bold
            Layout.alignment: Qt.AlignHCenter
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.ratioPx(root.scaleRatios.dividerHeightPct, 1)
            color: Qt.rgba(root.popupInk.r, root.popupInk.g, root.popupInk.b, 0.12)
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.resolvedThemeNames
            spacing: root.ratioPx(root.scaleRatios.rowSpacingPct, 1)

            delegate: Rectangle {
                id: themeRow
                required property string modelData
                width: ListView.view ? ListView.view.width : 0
                height: root.ratioPx(root.scaleRatios.rowHeightPct, 1)
                radius: root.isProMode ? visualRules.radiusControl : root.ratioPx(root.scaleRatios.rowRadiusPct, 1)
                color: ma.containsMouse
                    ? (root.isProMode ? SemanticTheme.surfaceInput(root.t, root.appStyle) : root.t.hover)
                    : "transparent"
                border.width: root.ratioPx(root.scaleRatios.dividerHeightPct, 1)
                border.color: ma.containsMouse
                    ? (root.isProMode ? SemanticTheme.borderStrong(root.t, root.appStyle) : root.t.accent)
                    : "transparent"

                // Strict Anchors for perfect alignment
                Rectangle {
                    id: dot
                    width: root.ratioPx(root.scaleRatios.dotSizePct, 1)
                    height: width
                    radius: root.ratioPx(root.scaleRatios.dotRadiusPct, 1)
                    property var _payload: root.themePayloadForName(themeRow.modelData)
                    // Use explicit swatch colors so the dot matches the theme name
                    // (e.g., White stays white instead of using accent ink).
                    color: root.swatchColorForName(themeRow.modelData, _payload)
                    border.width: root.ratioPx(root.scaleRatios.dividerHeightPct, 1)
                    border.color: Qt.rgba(root.popupInk.r, root.popupInk.g, root.popupInk.b, 0.3)
                    
                    anchors.left: parent.left
                    anchors.leftMargin: root.ratioPx(root.scaleRatios.rowInsetPct, 1)
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: themeRow.modelData
                    color: root.popupInk
                    font.pixelSize: root.ratioPx(
                        root.scaleRatios.labelFontPct,
                        root.metricFloor("fontFloorLabelPx", root.ratioPx(root.scaleRatios.labelFontFloorPct, 1))
                    )
                    font.weight: Font.Medium
                    
                    anchors.left: dot.right
                    anchors.leftMargin: root.ratioPx(root.scaleRatios.rowInsetPct, 1)
                    anchors.verticalCenter: parent.verticalCenter
                }

                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var chosenName = String(themeRow.modelData)
                        var chosenPayload = root.themePayloadForName(chosenName)
                        try {
                            if (root.appRef && root.appRef.setTheme) {
                                root.appRef.setTheme(chosenName)
                            }
                        } catch (e0) {
                            console.log("[THEME] setTheme failed in ThemePicker name=" + chosenName + " err=" + e0)
                        }
                        root.playUiClick("affirm", 0.58)
                        root.picked(chosenName, chosenPayload)
                        root.close()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.ratioPx(root.scaleRatios.closeHeightPct * 0.85, 1)
            radius: root.isProMode ? visualRules.radiusControl : height / 2
            color: root.closeFill

            Text {
                anchors.centerIn: parent
                text: "Close"
                color: root.closeInk
                font.pixelSize: root.ratioPx(
                    root.scaleRatios.closeFontPct,
                    root.metricFloor("fontFloorLabelPx", root.ratioPx(root.scaleRatios.closeFontFloorPct, 1))
                )
                font.weight: Font.Bold
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.playUiClick("dismiss", 0.36)
                    root.close()
                }
            }
        }
    }
}
