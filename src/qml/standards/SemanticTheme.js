.pragma library

function _hexColor(text, fallback) {
    var raw = String(text === undefined || text === null ? "" : text).trim()
    if (!/^#?[0-9a-fA-F]{6}$/.test(raw)) return fallback
    if (raw.charAt(0) !== "#") raw = "#" + raw
    return Qt.rgba(
        parseInt(raw.slice(1, 3), 16) / 255.0,
        parseInt(raw.slice(3, 5), 16) / 255.0,
        parseInt(raw.slice(5, 7), 16) / 255.0,
        1.0
    )
}

function asColor(value, fallback) {
    if (value && typeof value.r === "number") {
        return Qt.rgba(value.r, value.g, value.b, value.a === undefined ? 1.0 : value.a)
    }
    return _hexColor(value, fallback)
}

function alpha(colorValue, amount) {
    var c = asColor(colorValue, Qt.rgba(0.0, 0.0, 0.0, 1.0))
    return Qt.rgba(c.r, c.g, c.b, Math.max(0.0, Math.min(1.0, Number(amount))))
}

function mix(left, right, amount) {
    var a = asColor(left, Qt.rgba(0.0, 0.0, 0.0, 1.0))
    var b = asColor(right, Qt.rgba(1.0, 1.0, 1.0, 1.0))
    var t = Math.max(0.0, Math.min(1.0, Number(amount)))
    return Qt.rgba(
        (a.r * (1.0 - t)) + (b.r * t),
        (a.g * (1.0 - t)) + (b.g * t),
        (a.b * (1.0 - t)) + (b.b * t),
        1.0
    )
}

function luma(colorValue) {
    var c = asColor(colorValue, Qt.rgba(0.0, 0.0, 0.0, 1.0))
    return (c.r * 0.299) + (c.g * 0.587) + (c.b * 0.114)
}

function readableInk(fillColor) {
    return luma(fillColor) >= 0.60
        ? Qt.rgba(0.07, 0.09, 0.13, 0.98)
        : Qt.rgba(0.98, 0.99, 1.0, 0.98)
}

function isProfessional(appStyle) {
    return String(appStyle || "") === "Professional"
}

function isDarkMode(theme) {
    if (!theme) return false
    if (theme.mode) return String(theme.mode).toLowerCase() === "dark"
    return luma(theme.bg) < 0.5
}

function _professionalToken(name, isDark) {
    if (isDark) {
        switch (String(name || "")) {
        case "surfaceApp": return Qt.rgba(0.06, 0.07, 0.09, 1.0)
        case "surfacePanel": return Qt.rgba(0.11, 0.13, 0.17, 1.0)
        case "surfaceInput": return Qt.rgba(0.14, 0.16, 0.20, 1.0)
        case "surfaceRaised": return Qt.rgba(0.14, 0.16, 0.20, 1.0)
        case "inkPrimary": return Qt.rgba(0.95, 0.96, 0.98, 1.0)
        case "inkMuted": return Qt.rgba(0.60, 0.65, 0.72, 1.0)
        case "inkSubtle": return Qt.rgba(0.40, 0.45, 0.52, 1.0)
        case "borderSubtle": return Qt.rgba(0.20, 0.24, 0.30, 1.0)
        case "borderStrong": return Qt.rgba(0.35, 0.40, 0.48, 1.0)
        case "accentPrimary": return Qt.rgba(0.25, 0.50, 0.90, 1.0)
        case "hoverFill": return Qt.rgba(0.17, 0.20, 0.25, 1.0)
        case "success": return Qt.rgba(0.18, 0.71, 0.49, 1.0)
        case "warning": return Qt.rgba(0.91, 0.69, 0.23, 1.0)
        case "error":
        case "danger": return Qt.rgba(0.85, 0.34, 0.39, 1.0)
        case "info": return Qt.rgba(0.25, 0.50, 0.90, 1.0)
        default: return Qt.rgba(0.0, 0.0, 0.0, 1.0)
        }
    }
    switch (String(name || "")) {
    case "surfaceApp":
        return Qt.rgba(0.933, 0.949, 0.965, 1.0) // #EEF2F6
    case "surfacePanel":
        return Qt.rgba(1.0, 1.0, 1.0, 1.0)
    case "surfaceInput":
        return Qt.rgba(0.910, 0.929, 0.953, 1.0) // #E8EDF3
    case "surfaceRaised":
        return Qt.rgba(0.973, 0.980, 0.988, 1.0) // #F8FAFC
    case "inkPrimary":
        return Qt.rgba(0.059, 0.090, 0.165, 1.0) // #0F172A
    case "inkMuted":
        return Qt.rgba(0.322, 0.380, 0.455, 1.0) // #526174
    case "inkSubtle":
        return Qt.rgba(0.392, 0.455, 0.545, 1.0) // #64748B
    case "borderSubtle":
        return Qt.rgba(0.780, 0.820, 0.875, 1.0) // #C7D1DF
    case "borderStrong":
        return Qt.rgba(0.392, 0.455, 0.545, 1.0) // #64748B
    case "accentPrimary":
        return Qt.rgba(0.200, 0.255, 0.333, 1.0) // #334155
    case "hoverFill":
        return Qt.rgba(0.914, 0.933, 0.961, 1.0) // #E9EEF5
    case "success":
        return Qt.rgba(0.086, 0.396, 0.204, 1.0) // #166534
    case "warning":
        return Qt.rgba(0.706, 0.325, 0.035, 1.0) // #B45309
    case "error":
    case "danger":
        return Qt.rgba(0.725, 0.110, 0.110, 1.0) // #B91C1C
    case "info":
        return Qt.rgba(0.118, 0.329, 0.620, 1.0) // #1E549E
    default:
        return Qt.rgba(0.0, 0.0, 0.0, 1.0)
    }
}

function surfaceApp(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("surfaceApp", isDarkMode(theme))
    return asColor(theme && theme.bg, Qt.rgba(0.02, 0.02, 0.024, 1.0))
}

function surfacePanel(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("surfacePanel", isDarkMode(theme))
    return asColor(theme && theme.panel, Qt.rgba(0.08, 0.10, 0.14, 1.0))
}

function surfaceInput(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("surfaceInput", isDarkMode(theme))
    return asColor(theme && theme.panel2, Qt.rgba(0.10, 0.12, 0.16, 1.0))
}

function surfaceRaised(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("surfaceRaised", isDarkMode(theme))
    return asColor(theme && theme.panel2, Qt.rgba(0.10, 0.12, 0.16, 1.0))
}

function inkPrimary(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("inkPrimary", isDarkMode(theme))
    return asColor(theme && theme.text, Qt.rgba(0.98, 0.99, 1.0, 1.0))
}

function inkMuted(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("inkMuted", isDarkMode(theme))
    return asColor(theme && theme.muted, alpha(inkPrimary(theme, appStyle), 0.74))
}

function inkSubtle(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("inkSubtle", isDarkMode(theme))
    return alpha(inkMuted(theme, appStyle), 0.82)
}

function borderSubtle(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("borderSubtle", isDarkMode(theme))
    return alpha(inkPrimary(theme, appStyle), 0.24)
}

function borderStrong(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("borderStrong", isDarkMode(theme))
    return alpha(accentPrimary(theme, appStyle), 0.62)
}

function accentPrimary(theme, appStyle) {
    if (isProfessional(appStyle)) return _professionalToken("accentPrimary", isDarkMode(theme))
    return asColor(theme && theme.accent, Qt.rgba(0.16, 0.47, 1.0, 1.0))
}

function _fallbackAccent(theme, appStyle) {
    if (isProfessional(appStyle)) return accentPrimary(theme, appStyle)
    return asColor(theme && theme.accent, Qt.rgba(0.16, 0.47, 1.0, 1.0))
}

function tone(theme, kind, appStyle) {
    if (isProfessional(appStyle)) {
        var isDark = isDarkMode(theme)
        switch (String(kind || "neutral")) {
        case "success":
            return _professionalToken("success", isDark)
        case "warning":
            return _professionalToken("warning", isDark)
        case "error":
        case "danger":
            return _professionalToken("danger", isDark)
        case "info":
            return _professionalToken("info", isDark)
        default:
            return accentPrimary(theme, appStyle)
        }
    }
    var safeTheme = theme || ({})
    switch (String(kind || "neutral")) {
    case "success":
        return asColor(safeTheme.semanticSuccess, Qt.rgba(0.18, 0.71, 0.49, 1.0))
    case "warning":
        return asColor(safeTheme.semanticWarning, Qt.rgba(0.91, 0.69, 0.23, 1.0))
    case "error":
        return asColor(safeTheme.semanticError, Qt.rgba(0.85, 0.34, 0.39, 1.0))
    case "danger":
        return asColor(safeTheme.semanticDanger, tone(safeTheme, "error", appStyle))
    case "info":
        return asColor(safeTheme.semanticInfo, _fallbackAccent(safeTheme, appStyle))
    default:
        return _fallbackAccent(safeTheme, appStyle)
    }
}

function toneText(theme, kind, appStyle) {
    if (isProfessional(appStyle)) return readableInk(tone(theme, kind, appStyle))
    var safeTheme = theme || ({})
    switch (String(kind || "neutral")) {
    case "success":
        return asColor(safeTheme.semanticSuccessText, readableInk(tone(safeTheme, "success", appStyle)))
    case "warning":
        return asColor(safeTheme.semanticWarningText, readableInk(tone(safeTheme, "warning", appStyle)))
    case "error":
        return asColor(safeTheme.semanticErrorText, readableInk(tone(safeTheme, "error", appStyle)))
    case "danger":
        return asColor(safeTheme.semanticDangerText, readableInk(tone(safeTheme, "danger", appStyle)))
    case "info":
        return asColor(safeTheme.semanticInfoText, readableInk(tone(safeTheme, "info", appStyle)))
    default:
        return asColor(safeTheme.text, readableInk(_fallbackAccent(safeTheme, appStyle)))
    }
}

function _roleBase(theme, role, appStyle) {
    if (isProfessional(appStyle)) {
        switch (String(role || "panel")) {
        case "app":
            return surfaceApp(theme, appStyle)
        case "input":
            return surfaceInput(theme, appStyle)
        case "tooltip":
        case "toast":
        case "popup":
        case "dialog":
        case "raised":
            return surfaceRaised(theme, appStyle)
        default:
            return surfacePanel(theme, appStyle)
        }
    }
    var safeTheme = theme || ({})
    switch (String(role || "panel")) {
    case "tooltip":
    case "toast":
    case "popup":
        return asColor(safeTheme.panel2, Qt.rgba(0.10, 0.12, 0.16, 1.0))
    case "dialog":
        return asColor(safeTheme.panel, Qt.rgba(0.08, 0.10, 0.14, 1.0))
    default:
        return asColor(safeTheme.panel, Qt.rgba(0.08, 0.10, 0.14, 1.0))
    }
}

function _mixAmount(role, kind) {
    var resolvedKind = String(kind || "neutral")
    var resolvedRole = String(role || "panel")
    var base = 0.10
    if (resolvedRole === "tooltip") base = 0.12
    else if (resolvedRole === "popup") base = 0.10
    else if (resolvedRole === "toast") base = 0.18
    else if (resolvedRole === "dialog") base = 0.15
    if (resolvedKind === "neutral") base *= 0.55
    return base
}

function surface(theme, role, kind, appStyle) {
    if (isProfessional(appStyle)) {
        var proBase = _roleBase(theme, role, appStyle)
        var proRole = String(role || "panel")
        if (String(kind || "neutral") === "neutral") return proBase
        var proTone = tone(theme, kind, appStyle)
        var proMix = (proRole === "tooltip" || proRole === "toast" || proRole === "popup") ? 0.08 : 0.05
        return mix(proBase, proTone, proMix)
    }
    var base = _roleBase(theme, role, appStyle)
    var accentTone = tone(theme, kind === "neutral" ? "info" : kind, appStyle)
    var mixed = mix(base, accentTone, _mixAmount(role, kind))
    var opacity = 0.95
    var resolvedRole = String(role || "panel")
    if (resolvedRole === "tooltip") opacity = 0.98
    else if (resolvedRole === "popup") opacity = 0.98
    else if (resolvedRole === "toast") opacity = 0.96
    else if (resolvedRole === "dialog") opacity = 0.975
    return Qt.rgba(mixed.r, mixed.g, mixed.b, opacity)
}

function border(theme, role, kind, appStyle) {
    if (isProfessional(appStyle)) {
        if (String(kind || "neutral") === "neutral") return borderSubtle(theme, appStyle)
        return alpha(tone(theme, kind, appStyle), 0.52)
    }
    var resolvedKind = String(kind || "neutral")
    var accentTone = tone(theme, resolvedKind === "neutral" ? "info" : resolvedKind, appStyle)
    var alphaValue = 0.38
    var resolvedRole = String(role || "panel")
    if (resolvedRole === "tooltip") alphaValue = 0.44
    else if (resolvedRole === "popup") alphaValue = 0.46
    else if (resolvedRole === "toast") alphaValue = 0.48
    else if (resolvedRole === "dialog") alphaValue = 0.58
    if (resolvedKind === "neutral") alphaValue *= 0.88
    return alpha(accentTone, alphaValue)
}

function ink(theme, role, kind, appStyle) {
    if (isProfessional(appStyle)) {
        var resolvedKind = String(kind || "neutral")
        if (resolvedKind === "neutral") {
            var resolvedRole = String(role || "panel")
            if (resolvedRole === "tooltip" || resolvedRole === "toast") return inkPrimary(theme, appStyle)
            return inkPrimary(theme, appStyle)
        }
        return toneText(theme, kind, appStyle)
    }
    return readableInk(surface(theme, role, kind, appStyle))
}

function shadow(theme, role, kind, appStyle) {
    if (isProfessional(appStyle)) return alpha(inkPrimary(theme, appStyle), 0.0)
    var accentTone = tone(theme, String(kind || "neutral") === "neutral" ? "info" : kind, appStyle)
    var alphaValue = String(role || "panel") === "tooltip" ? 0.18 : 0.24
    return alpha(accentTone, alphaValue)
}

// Layout & Overlays
function pageBackground(theme, appStyle) { return surfaceApp(theme, appStyle) }
function overlayScrim(theme, appStyle) { return alpha(Qt.rgba(0,0,0,1), 0.5) }
function windowChrome(theme, appStyle) { return surfacePanel(theme, appStyle) }
function titleBarBackground(theme, appStyle) { return surfacePanel(theme, appStyle) }

// Navigation
function navigationBackground(theme, appStyle) { return surfacePanel(theme, appStyle) }
function navigationSelectedBackground(theme, appStyle) { return alpha(accentPrimary(theme, appStyle), 0.15) }

// Tabs
function tabStripBackground(theme, appStyle) { return surfaceApp(theme, appStyle) }
function tabHoverBackground(theme, appStyle) { return alpha(inkPrimary(theme, appStyle), 0.05) }
function tabSelectedBackground(theme, appStyle) { return surfacePanel(theme, appStyle) }

// Buttons
function buttonPrimary(theme, appStyle) { return accentPrimary(theme, appStyle) }
function buttonBackground(theme, appStyle) { return surfaceInput(theme, appStyle) }
function buttonHover(theme, appStyle) { return alpha(inkPrimary(theme, appStyle), 0.08) }
function destructive(theme, appStyle) { return tone(theme, "danger", appStyle) }
function destructiveHover(theme, appStyle) { return mix(tone(theme, "danger", appStyle), inkPrimary(theme, appStyle), 0.15) }
function textOnPrimary(theme, appStyle) { return readableInk(buttonPrimary(theme, appStyle)) }
function textOnAccent(theme, appStyle) { return readableInk(accentPrimary(theme, appStyle)) }

// Tables
function tableHeaderBackground(theme, appStyle) { return surfaceRaised(theme, appStyle) }
function tableRowBackground(theme, appStyle) { return surfacePanel(theme, appStyle) }
function tableAlternateRowBackground(theme, appStyle) { return surfaceInput(theme, appStyle) }
function tableRowHover(theme, appStyle) { return alpha(inkPrimary(theme, appStyle), 0.04) }

// States
function hoverOverlay(theme, appStyle) { return alpha(inkPrimary(theme, appStyle), 0.06) }
function focusOverlay(theme, appStyle) { return borderStrong(theme, appStyle) }
