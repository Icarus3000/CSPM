// === THEME SAFETY RULES ===
// "If background is light, text MUST be dark."

function enforceContrast(theme) {
    if (!theme) return theme;

    // Calculate perceived brightness of the panel
    // Formula: (R*299 + G*587 + B*114) / 1000
    // We treat hex strings as simple relative luminance checks here for speed.
    
    var bgHex = theme.panel || "#000000";
    var textHex = theme.text || "#FFFFFF";
    
    var bgLum = getLuminance(bgHex);
    var textLum = getLuminance(textHex);

    // SAFETY CHECK:
    // If Background is Bright (> 0.6) AND Text is Bright (> 0.6)...
    // FORCE Text to Black.
    if (bgLum > 0.6 && textLum > 0.6) {
        console.warn("Theme Violation Detected: Light text on Light background. Auto-Correcting to Black.");
        theme.text = "#111111"; // Forced Dark Text
        theme.btn_text = "#FFFFFF"; // Buttons usually have dark bg in light themes, so white is safe
    }

    return theme;
}

function getLuminance(hex) {
    // Strip '#'
    var c = hex.substring(1);
    var rgb = parseInt(c, 16);
    var r = (rgb >> 16) & 0xff;
    var g = (rgb >>  8) & 0xff;
    var b = (rgb >>  0) & 0xff;

    return 0.2126 * r + 0.7152 * g + 0.0722 * b; // Standard luminance formula
}
