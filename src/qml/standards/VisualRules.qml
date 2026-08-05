import QtQuick

QtObject {
    property string appStyle: "Professional"
    readonly property bool isPro: appStyle === "Professional"
    readonly property bool isConsole: !isPro

    // === CANONICAL BEHAVIOR/METRIC TOKENS ===
    // SemanticTheme.js owns colors; this object owns motion, geometry, shadows,
    // chrome behavior, and audio policy.
    readonly property int radiusPanel: isPro ? 6 : 16
    readonly property int radiusControl: isPro ? 4 : 999
    readonly property int radiusPopup: isPro ? 4 : 12
    readonly property int shadowPanel: isPro ? 0 : 18
    readonly property real shadowOpacity: isPro ? 0.0 : 0.26
    readonly property int motionFast: isPro ? 90 : 160
    readonly property int motionNormal: isPro ? 130 : 260
    readonly property int motionSlow: isPro ? 180 : 420
    readonly property string textFontFamily: "Segoe UI"
    readonly property string iconFontFamily: "Segoe MDL2 Assets"
    readonly property int proWorkspaceHeaderHeightPx: 44
    readonly property int proWorkspaceHeaderGapPx: 2
    readonly property int proWorkspaceTitleFontPx: 17
    readonly property int proWorkspaceSubtitleFontPx: 11
    readonly property int proSectionTitleFontPx: 13
    readonly property int proBodyFontPx: 12
    readonly property int proLabelFontPx: 11
    readonly property int proCaptionFontPx: 10
    readonly property bool jellyEnabled: !isPro
    readonly property bool glowEnabled: !isPro
    readonly property bool hoverScaleEnabled: !isPro
    readonly property bool neonFlickerEnabled: !isPro
    readonly property string soundProfile: isPro ? "muted" : "expressive"
    readonly property real soundVolumeScale: isPro ? 0.35 : 1.0

    // === RULE 1: GEOMETRY ===
    // These values MUST be used by all Windows (Splash, Main, Dialogs)
    readonly property int cornerRadius: isPro ? radiusPanel : 16
    readonly property int glowPad: isPro ? 0 : 60
    readonly property real scaleBias: isPro ? 1.0 : 0.90

    // === RULE 2: PLASMA GLOW (The New Standard) ===
    // These control the "Neon" look. 
    // Tube Width = The thickness of the hollow ring.
    readonly property int plasmaTubeWidth: isPro ? 1 : 10
    
    // Brightness = How "Hot" the core looks (Max 1.0).
    readonly property real plasmaBrightness: isPro ? 0.0 : 1.0

    // === RULE 3: DISSIPATION MATH ===
    // This is the "Magic Number" that converts Pixels to GPU Blur.
    // 128.0 allows for the wide, dissipating gas look.
    readonly property real blurDivisor: isPro ? 1.0 : 128.0

    // Multipliers drive how far the gas spreads from the tube.
    readonly property real spreadNear: isPro ? 1.0 : 3.0  // Dense core
    readonly property real spreadFar: isPro ? 0.0 : 1.0   // Atmosphere
}
