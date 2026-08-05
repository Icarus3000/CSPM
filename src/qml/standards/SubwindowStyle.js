.pragma library

function cloneMap(src) {
    var out = {}
    if (!src) return out
    for (var k in src) {
        out[k] = src[k]
    }
    return out
}

function mergeMap(base, overrides) {
    var out = cloneMap(base)
    if (!overrides) return out
    for (var k in overrides) {
        out[k] = overrides[k]
    }
    return out
}

var BASE = {
    "pageMarginPct": 0.024,
    "pageSpacingPct": 0.015,
    "headerHeightPct": 0.060,
    "headerSpacingPct": 0.010,
    "headerTitleFontPct": 0.027,
    "headerSubtitleFontPct": 0.015,
    "gridColumnSpacingPct": 0.014,
    "gridRowSpacingPct": 0.012,
    "panelRadiusPct": 0.013,
    "panelBorderPct": 0.0011,
    "descPrefHeightPct": 0.092,
    "descMaxHeightPct": 0.105,
    "descFontPct": 0.016,
    "descPadPct": 0.011,
    "descCornerPct": 0.013,
    "descFocusBorderPct": 0.0033,
    "descIdleBorderPct": 0.0011,
    "hintFontPct": 0.015,
    "footerHeightPct": 0.058,
    "footerSpacingPct": 0.011,
    "submitBtnWidthPct": 0.138,
    "cancelBtnWidthPct": 0.096,
    "tearBtnWidthPct": 0.148,
    "dockBtnWidthPct": 0.190
}

var TIME_DOCKET_OVERRIDES = {
    "popupWidthPct": 0.311,
    "popupHeightPct": 0.228,
    "popupCornerPct": 0.017,
    "popupBorderPct": 0.0022,
    "popupMarginPct": 0.017,
    "popupSpacingPct": 0.011,
    "popupTitleFontPct": 0.026,
    "timerEditFieldWidthPct": 0.246,
    "timerEditFieldHeightPct": 0.061,
    "timerEditFieldFontPct": 0.030,
    "timerEditFieldCornerPct": 0.013,
    "timerEditFieldBorderPct": 0.0011,
    "tipSpacingPct": 0.0065,
    "tipFontPct": 0.017,
    "popupActionBtnWidthPct": 0.090,
    "popupActionBtnHeightPct": 0.043,
    "timerBoxWidthPct": 0.140,
    "timerBoxHeightPct": 0.056,
    "timerBoxCornerPct": 0.013,
    "timerBoxBorderPct": 0.0022,
    "timerFontPct": 0.024,
    "startBtnWidthPct": 0.096,
    "saveBtnWidthPct": 0.138,
    "cancelBtnWidthPct": 0.096,
    "dockBtnWidthPct": 0.190
}

var PLACEHOLDER_OVERRIDES = {
    "headerSubtitleFontPct": 0.014,
    "hintFontPct": 0.0145,
    "descPrefHeightPct": 0.096,
    "descMaxHeightPct": 0.108
}

function baseRatios() {
    return cloneMap(BASE)
}

function timeDocketRatios() {
    return mergeMap(BASE, TIME_DOCKET_OVERRIDES)
}

function placeholderRatios() {
    return mergeMap(BASE, PLACEHOLDER_OVERRIDES)
}

