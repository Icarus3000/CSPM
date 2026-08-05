.pragma library

function cloneThemeObject(themeObj) {
    if (!themeObj || typeof themeObj !== "object") return null
    var clone = {}
    for (var key in themeObj) {
        clone[key] = themeObj[key]
    }
    return clone
}

function normalizeThemeField(value) {
    return String(value === undefined || value === null ? "" : value).trim().toLowerCase()
}

function themeForName(appRef, themeName) {
    var resolvedName = ""
    if (themeName !== undefined && themeName !== null) {
        resolvedName = String(themeName)
    }
    if (!resolvedName.length || !appRef || !appRef.getThemeByName) return null
    try {
        var payload = appRef.getThemeByName(resolvedName)
        if (payload && payload.bg) {
            return cloneThemeObject(payload)
        }
    } catch (e) {
    }
    return null
}

function syncThemeFromApp(appRef) {
    if (!(appRef && appRef.theme && appRef.theme.bg)) return null
    var payload = cloneThemeObject(appRef.theme)
    if (!payload || !payload.bg) return null
    return payload
}

function resolveThemeNameForPayload(appRef, payload) {
    if (!appRef || !appRef.themeNames || !appRef.getThemeByName) return ""
    if (!payload || typeof payload !== "object") return ""
    var targetBg = normalizeThemeField(payload.bg)
    var targetAccent = normalizeThemeField(payload.accent)
    var targetPanel = normalizeThemeField(payload.panel)
    var names = appRef.themeNames
    for (var i = 0; i < names.length; i++) {
        var name = String(names[i] === undefined || names[i] === null ? "" : names[i]).trim()
        if (!name.length) continue
        var candidate = appRef.getThemeByName(name)
        if (!candidate || typeof candidate !== "object") continue
        var cBg = normalizeThemeField(candidate.bg)
        var cAccent = normalizeThemeField(candidate.accent)
        var cPanel = normalizeThemeField(candidate.panel)
        if (cBg === targetBg && cAccent === targetAccent) return name
        if (cBg === targetBg && cPanel === targetPanel) return name
    }
    return ""
}

function applyThemeSelection(appRef, themeName, pickedPayload) {
    var resolvedName = ""
    if (themeName !== undefined && themeName !== null) {
        resolvedName = String(themeName)
    }
    if (!resolvedName.length) return null
    try {
        if (appRef && appRef.setTheme) {
            appRef.setTheme(resolvedName)
        }
    } catch (e) {
    }
    var localTheme = themeForName(appRef, resolvedName)
    if (localTheme && localTheme.bg) {
        return localTheme
    }
    if (pickedPayload && pickedPayload.bg) {
        return cloneThemeObject(pickedPayload)
    }
    return null
}
