.pragma library

function safeString(value) {
    if (value === undefined || value === null) return ""
    return String(value)
}

function logoSource(bootstrap) {
    if (!bootstrap) return ""
    return safeString((typeof bootstrap.startupSplashLogoUrl !== "undefined") ? bootstrap.startupSplashLogoUrl : "")
}

function audioSource(bootstrap) {
    if (!bootstrap) return ""
    return safeString((typeof bootstrap.startupSplashAudioUrl !== "undefined") ? bootstrap.startupSplashAudioUrl : "")
}

function screenRect(screenObj) {
    if (!screenObj) {
        return { "x": 0, "y": 0, "w": 1280, "h": 720 }
    }
    var sx = (typeof screenObj.virtualX === "number" && isFinite(screenObj.virtualX)) ? Math.round(screenObj.virtualX) : 0
    var sy = (typeof screenObj.virtualY === "number" && isFinite(screenObj.virtualY)) ? Math.round(screenObj.virtualY) : 0
    var sw = (typeof screenObj.width === "number" && isFinite(screenObj.width)) ? Math.round(screenObj.width) : 1280
    var sh = (typeof screenObj.height === "number" && isFinite(screenObj.height)) ? Math.round(screenObj.height) : 720
    sw = Math.max(1, sw)
    sh = Math.max(1, sh)
    return { "x": sx, "y": sy, "w": sw, "h": sh }
}

function collectSplashRefs(bootstrap) {
    if (!bootstrap) return []

    var refs = []
    if (bootstrap.splashRefs && bootstrap.splashRefs.length > 0) {
        refs = bootstrap.splashRefs.slice(0)
    }
    if (bootstrap.splashRef && refs.indexOf(bootstrap.splashRef) < 0) {
        refs.push(bootstrap.splashRef)
    }
    return refs
}

function resetSplashTracking(bootstrap, splashHandoffTimeoutTimer) {
    if (!bootstrap) return
    bootstrap._splashHandoffActive = false
    bootstrap._firstPixelHandoffSeen = false
    bootstrap._handoffTimeoutRetryCount = 0
    if (splashHandoffTimeoutTimer) {
        splashHandoffTimeoutTimer.stop()
    }
}

function destroySplash(bootstrap, splashHandoffTimeoutTimer) {
    if (!bootstrap) return 0

    var refs = collectSplashRefs(bootstrap)
    resetSplashTracking(bootstrap, splashHandoffTimeoutTimer)
    if (refs.length <= 0) return 0

    if (bootstrap._setStartupState) {
        bootstrap._setStartupState("splash-released", "destroy")
    }
    if (bootstrap._lagLog) {
        bootstrap._lagLog("_destroySplash begin count=" + refs.length)
    }

    bootstrap.splashRefs = []
    bootstrap.splashRef = null
    for (var i = 0; i < refs.length; i++) {
        var ref = refs[i]
        if (!ref) continue
        try {
            if (ref.closeForAppExit) {
                ref.closeForAppExit()
            } else if (ref.closeOverlay) {
                ref.closeOverlay("bootstrap-destroy")
            } else {
                ref.close()
            }
        } catch (e1) {
        }
    }

    if (bootstrap._lagLog) {
        bootstrap._lagLog("_destroySplash complete count=" + refs.length)
    }
    return refs.length
}

function releaseSplashForLaunch(bootstrap, splashHandoffTimeoutTimer, reason) {
    if (!bootstrap) return 0

    var refs = collectSplashRefs(bootstrap)
    resetSplashTracking(bootstrap, splashHandoffTimeoutTimer)
    if (refs.length <= 0) {
        bootstrap.splashRefs = []
        bootstrap.splashRef = null
        return 0
    }

    if (bootstrap._setStartupState) {
        bootstrap._setStartupState("splash-released", "release:" + reason)
    }
    if (bootstrap._lagLog) {
        bootstrap._lagLog("_releaseSplashForLaunch begin reason=" + reason + " count=" + refs.length)
    }

    bootstrap.splashRefs = []
    bootstrap.splashRef = null
    for (var i = 0; i < refs.length; i++) {
        var ref = refs[i]
        if (!ref) continue
        try {
            if (ref.releaseForLaunchHandoff) {
                ref.releaseForLaunchHandoff(reason)
            } else if (ref.closeOverlay) {
                ref.closeOverlay("launch-handoff-" + reason)
            } else {
                ref.close()
            }
        } catch (e1) {
            try {
                if (ref.closeForAppExit) {
                    ref.closeForAppExit()
                }
            } catch (e2) {
            }
        }
    }

    return refs.length
}

function createSplashEntries(bootstrap, splashComponent, screens, activeIdx, sharedEpochMs, logo, audio) {
    var result = {
        "createdRefs": [],
        "primaryRef": null
    }

    if (!bootstrap || !splashComponent || !screens || screens.length <= 0) {
        return result
    }

    var soundEnabled = true
    try {
        if (bootstrap._soundEffectsEnabled) {
            soundEnabled = bootstrap._soundEffectsEnabled()
        }
    } catch (e0) {
        soundEnabled = true
    }

    for (var i = 0; i < screens.length; i++) {
        var monitor = screens[i]
        if (!monitor) continue
        var rect = screenRect(monitor)
        var splashObj = splashComponent.createObject(null, {
            "mainWindow": null,
            "splashX": rect.x,
            "splashY": rect.y,
            "splashW": rect.w,
            "splashH": rect.h,
            "logoSource": logo,
            "audioSource": audio,
            "audioEnabled": (audio.length > 0) && (i === activeIdx) && soundEnabled,
            "inputCaptureEnabled": (i === activeIdx),
            "sharedStartEpochMs": sharedEpochMs,
            "screen": monitor,
            "holdForLaunchHandoff": true,
            "visible": false
        })
        if (!splashObj) continue
        result.createdRefs.push(splashObj)
        if (i === activeIdx) {
            result.primaryRef = splashObj
        }
    }

    if (!result.primaryRef && result.createdRefs.length > 0) {
        result.primaryRef = result.createdRefs[0]
    }
    return result
}
