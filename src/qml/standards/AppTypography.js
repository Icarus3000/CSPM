.pragma library

// Private-use Windows glyphs have no Unicode fallback. CSPM Symbols is a
// bundled, MIT-licensed vector font with the same codepoints used by our UI.
// The Python startup registers it before any QML window is constructed.
function textFamily() {
    return Qt.platform.os === "windows" ? "Segoe UI" : Qt.application.font.family
}

function interFamily() {
    return Qt.platform.os === "windows" ? "Inter" : Qt.application.font.family
}

function iconFamily() {
    return Qt.platform.os === "windows" ? "Segoe MDL2 Assets" : "CSPM Symbols"
}

function fluentIconFamily() {
    return Qt.platform.os === "windows" ? "Segoe Fluent Icons" : "CSPM Symbols"
}

// Use this for icon-only Text items with standard Unicode symbols or emoji.
// The Linux font also maps these symbols to consistent monochrome outlines.
function symbolFamily() {
    return Qt.platform.os === "windows" ? Qt.application.font.family : "CSPM Symbols"
}

function monoFamily(windowsFamily) {
    return Qt.platform.os === "windows" ? (windowsFamily || "Consolas") : "monospace"
}
