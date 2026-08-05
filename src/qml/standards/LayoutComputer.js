// === RULE 3: CONTENT SCALING ===
// Calculates the exact X, Y, W, H to fit content centered on a screen
// while respecting the invisible "Glow Padding" so borders are never clipped.

function computeLaunchGeometry(screen, contentW, contentH, glowPad, scaleBias) {
    // 1. Determine the "Usable" area of the screen (excluding taskbars)
    var rx = screen.virtualX
    var ry = screen.virtualY
    var rw = screen.width
    var rh = screen.desktopAvailableHeight > 0 ? screen.desktopAvailableHeight : screen.height
    
    // Safety buffer for Windows taskbar quirks
    var taskbarSafety = 16
    rh = Math.max(200, rh - taskbarSafety)

    // 2. Calculate the "Fit" scale
    var fitW = rw - glowPad
    var fitH = rh - glowPad
    var fit = Math.min(1.0, Math.min(fitW / contentW, fitH / contentH))
    var scaleFactor = fit * scaleBias

    // 3. Calculate Final Dimensions (Content + Glow Padding)
    var w = Math.round((contentW * scaleFactor) + glowPad)
    var h = Math.round((contentH * scaleFactor) + glowPad)

    // 4. Center it
    var cx = rx + (rw / 2)
    var cy = ry + (rh / 2)

    var x = Math.round(cx - (w / 2))
    var y = Math.round(cy - (h / 2))

    return {
        scale: scaleFactor,
        x: x, y: y,
        w: w, h: h,
        // Pass through usable rect for debug/splash positioning
        ux: rx, uy: ry, uw: rw, uh: rh
    }
}

function pickScreen(vx, vy, vw, vh) {
    var screens = Qt.application.screens
    for (var i = 0; i < screens.length; i++) {
        var s = screens[i]
        if (s.virtualX === vx && s.virtualY === vy && s.width === vw && s.height === vh) return s
    }
    return screens[0]
}
