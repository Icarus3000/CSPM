.pragma library

function _safeNowMs() {
    var nowMs = Date.now()
    if (!isFinite(nowMs) || nowMs <= 0) return 0
    return Math.round(nowMs)
}

function markStart(markBag, key) {
    var marks = (markBag && typeof markBag === "object") ? markBag : {}
    var resolvedKey = String(key === undefined || key === null ? "" : key).trim()
    if (!resolvedKey.length) {
        return marks
    }
    marks[resolvedKey] = _safeNowMs()
    return marks
}

function markFinish(markBag, key) {
    var marks = (markBag && typeof markBag === "object") ? markBag : {}
    var resolvedKey = String(key === undefined || key === null ? "" : key).trim()
    if (!resolvedKey.length || !marks.hasOwnProperty(resolvedKey)) {
        return {
            "marks": marks,
            "elapsedMs": -1
        }
    }
    var startedMs = Number(marks[resolvedKey] || 0)
    delete marks[resolvedKey]
    var nowMs = _safeNowMs()
    if (!isFinite(startedMs) || startedMs <= 0 || nowMs <= 0) {
        return {
            "marks": marks,
            "elapsedMs": -1
        }
    }
    return {
        "marks": marks,
        "elapsedMs": Math.max(0, Math.round(nowMs - startedMs))
    }
}

