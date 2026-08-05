.pragma library

function startupSplashLogoSourceUrl(mainWin) {
    if (!mainWin) return ""
    try {
        if (mainWin.startupSplashLogoUrl && mainWin.startupSplashLogoUrl.length > 0) {
            return String(mainWin.startupSplashLogoUrl)
        }
    } catch (e) {
    }
    return ""
}

function startupSplashAudioSourceUrl(mainWin) {
    if (!mainWin) return ""
    try {
        if (mainWin.startupSplashAudioUrl && mainWin.startupSplashAudioUrl.length > 0) {
            return String(mainWin.startupSplashAudioUrl)
        }
    } catch (e) {
    }
    return ""
}

function removeStartupSplashRef(mainWin, splashObj) {
    if (!mainWin) return 0
    if (!mainWin.startupSplashRefs || mainWin.startupSplashRefs.length === 0) {
        if (mainWin.startupSplashRef === splashObj) {
            mainWin.startupSplashRef = null
        }
        mainWin.startupSplashPendingCount = 0
        return 0
    }

    var remaining = []
    for (var i = 0; i < mainWin.startupSplashRefs.length; i++) {
        var entry = mainWin.startupSplashRefs[i]
        if (!entry || entry === splashObj) {
            continue
        }
        remaining.push(entry)
    }
    mainWin.startupSplashRefs = remaining
    if (mainWin.startupSplashRef === splashObj) {
        mainWin.startupSplashRef = (remaining.length > 0) ? remaining[0] : null
    }
    mainWin.startupSplashPendingCount = remaining.length
    return mainWin.startupSplashPendingCount
}

function destroyStartupSplash(mainWin) {
    if (!mainWin) return

    var refs = []
    if (mainWin.startupSplashRefs && mainWin.startupSplashRefs.length > 0) {
        refs = mainWin.startupSplashRefs.slice(0)
    }
    if (mainWin.startupSplashRef && refs.indexOf(mainWin.startupSplashRef) < 0) {
        refs.push(mainWin.startupSplashRef)
    }

    mainWin.startupSplashRefs = []
    mainWin.startupSplashRef = null
    mainWin.startupSplashPendingCount = 0

    for (var i = 0; i < refs.length; i++) {
        var splashObj = refs[i]
        if (!splashObj) continue
        try {
            splashObj.closeOverlay("replace")
        } catch (e) {
            try {
                splashObj.destroy()
            } catch (e2) {
            }
        }
    }
}

function requestStartupSplashSkip(mainWin, startupLaunchDelayTimer, reason) {
    if (!mainWin || mainWin.startupSplashSkipInvoked) return

    mainWin.startupSplashSkipInvoked = true
    var reasonText = String(reason || "user-skip")
    mainWin.lagLog("startup splash skip requested reason=" + reasonText)

    mainWin.startupSplashEnabled = false
    mainWin.startupSplashSequenceEpochMs = 0
    mainWin.startupSplashPendingCount = 0
    destroyStartupSplash(mainWin)
    if (startupLaunchDelayTimer) {
        startupLaunchDelayTimer.stop()
    }

    if (!mainWin.startupLaunchStarted) {
        mainWin.beginCoreLaunchSequence()
        return
    }

    if (mainWin.startupPhase !== "falling-window") {
        mainWin.primeStartupLaunchScreen("splash-skip")
        mainWin.setStartupPhase("splash-skipped", reasonText)
        mainWin.startOpeningLaunchNow()
    }
}

function beginCoreLaunchSequence(mainWin, startupLaunchDelayTimer) {
    if (!mainWin || mainWin.startupLaunchStarted) return

    mainWin.startupLaunchStarted = true
    mainWin.startupLaunchScreenLocked = false
    mainWin.primeStartupLaunchScreen("beginCoreLaunchSequence")
    mainWin.setStartupPhase("core-launch", "beginCoreLaunchSequence")
    var elapsedMs = mainWin.splashElapsedMs()
    var fallDelayMs = 0
    var skipReasonText = "normal"
    if (mainWin.startupSplashSequenceEpochMs > 0 && !mainWin.startupSplashSkipInvoked) {
        fallDelayMs = Math.max(0, mainWin.startupFallStartTimelineMs - elapsedMs)
        skipReasonText = "timeline"
    } else if (mainWin.startupSplashSkipInvoked) {
        fallDelayMs = 0
        skipReasonText = "user-skipped (no timeline wait)"
    }
    mainWin.lagLog("beginCoreLaunchSequence"
        + " elapsedMs=" + elapsedMs
        + " fallTargetMs=" + mainWin.startupFallStartTimelineMs
        + " fallDelayMs=" + fallDelayMs
        + " skipReason=" + skipReasonText
        + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"))
    mainWin.phaseLog("SPLASH", "Splash complete -> prepare opening animation"
        + " t+" + elapsedMs + "ms"
        + " fallTargetMs=" + mainWin.startupFallStartTimelineMs
        + " fallDelayMs=" + fallDelayMs
        + " skipReason=" + skipReasonText)
    if (fallDelayMs > 0) {
        if (startupLaunchDelayTimer) {
            startupLaunchDelayTimer.stop()
            startupLaunchDelayTimer.interval = fallDelayMs
            startupLaunchDelayTimer.start()
        }
        mainWin.lagLog("beginCoreLaunchSequence waiting for delay timer intervalMs=" + fallDelayMs)
        return
    }
    mainWin.startOpeningLaunchNow()
}

function runDeferredBackendBootTask(mainWin, taskPayload) {
    if (!mainWin) return true

    mainWin.lagLog("deferred backend task triggered"
        + " startupDataBootStarted=" + mainWin.startupDataBootStarted
        + " startupDataBootComplete=" + mainWin.startupDataBootComplete
        + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"))
    if (!mainWin.startupAllowsHeavyWork("deferredBackendBootTask")) {
        return false
    }
    if (!mainWin.startupDataBootStarted || mainWin.startupDataBootComplete) return true
    if (!(mainWin.appRef && typeof mainWin.appRef.boot_backend === "function")) {
        mainWin.startupDataBootComplete = true
        mainWin.startupDataBootMessage = ""
        return true
    }
    try {
        mainWin.lagLog("deferred backend task calling appRef.boot_backend()")
        mainWin.appRef.boot_backend()
        mainWin.startupDataBootComplete = true
        mainWin.startupDataBootMessage = ""
        mainWin.lagLog("deferred backend task boot_backend complete")
    } catch (e) {
        mainWin.startupDataBootFailed = true
        mainWin.startupDataBootComplete = true
        mainWin.startupDataBootMessage = "Data load failed. Please restart."
        mainWin.lagLog("deferred backend task boot_backend error=" + e)
        mainWin.reportUiFailure(
            "DetachedShellWindow.deferredBackendBoot",
            String(e),
            "Data load failed. Please restart."
        )
    }
    return true
}

function triggerDeferredBackendBoot(mainWin, deferredBackendBootTimer) {
    if (!mainWin) return

    mainWin.lagLog("[FORENSIC] triggerDeferredBackendBoot called")
    mainWin.lagLog("triggerDeferredBackendBoot invoked"
        + " isSettled=" + mainWin.isSettled
        + " startupDataBootStarted=" + mainWin.startupDataBootStarted
        + " startupDataBootComplete=" + mainWin.startupDataBootComplete
        + " backendBooted=" + ((mainWin.appRef && mainWin.appRef.backendBooted) ? "true" : "false"))
    if (mainWin.detachedMode) {
        mainWin.startupDataBootStarted = true
        mainWin.startupDataBootComplete = true
        mainWin.startupDataBootMessage = ""
        return
    }
    if (!mainWin.isSettled) return
    if (mainWin.startupDataBootStarted || mainWin.startupDataBootComplete) return
    if (mainWin.appRef && mainWin.appRef.backendBooted) {
        mainWin.startupDataBootStarted = true
        mainWin.startupDataBootComplete = true
        mainWin.startupDataBootMessage = ""
        return
    }
    mainWin.startupDataBootStarted = true
    mainWin.startupDataBootFailed = false
    mainWin.startupDataBootMessage = ""
    if (mainWin.enqueuePostSettleTask(
        "DetachedShellWindow.deferredBackendBoot",
        mainWin,
        "runDeferredBackendBootTask",
        { "source": "triggerDeferredBackendBoot" },
        true
    )) {
        mainWin.lagLog("triggerDeferredBackendBoot queued deferred backend task")
        return
    }
    mainWin.lagLog("triggerDeferredBackendBoot restarting deferredBackendBootTimer")
    if (deferredBackendBootTimer) {
        deferredBackendBootTimer.restart()
    }
}

function buildStartupSplashSetup(mainWin) {
    var result = {
        "ok": false,
        "reason": "",
        "logoUrl": "",
        "audioUrl": "",
        "screens": [],
        "primaryIdx": 0
    }

    if (!mainWin) {
        result.reason = "missing-main-window"
        return result
    }

    result.logoUrl = startupSplashLogoSourceUrl(mainWin)
    result.audioUrl = startupSplashAudioSourceUrl(mainWin)
    if (result.logoUrl.length <= 0 || result.audioUrl.length <= 0) {
        result.reason = "missing-media"
        return result
    }

    result.screens = mainWin.applicationScreensSafe()
    if (!result.screens || result.screens.length <= 0) {
        result.reason = "no-screen"
        result.screens = []
        return result
    }

    var splashScreen = mainWin.targetScreen ? mainWin.targetScreen : mainWin.resolveTargetScreen()
    if (!splashScreen && mainWin.screen) {
        splashScreen = mainWin.screen
    }
    if (!splashScreen) {
        splashScreen = result.screens[0]
    }

    result.primaryIdx = mainWin.indexOfScreen(splashScreen)
    if (result.primaryIdx < 0 || result.primaryIdx >= result.screens.length) {
        result.primaryIdx = 0
    }

    result.ok = true
    return result
}

function createStartupSplashEntries(mainWin, startupSplashComponent, setup) {
    if (!mainWin || !startupSplashComponent || !setup || !setup.screens || setup.screens.length <= 0) {
        return []
    }

    destroyStartupSplash(mainWin)
    mainWin.startupSplashSequenceEpochMs = Date.now() + mainWin.startupSplashSyncLeadMs
    mainWin.phaseLog("SPLASH", "Create startup splash windows across " + setup.screens.length + " monitor(s)"
        + " syncLeadMs=" + mainWin.startupSplashSyncLeadMs)

    var created = []
    var screenInfos = []
    if (mainWin.appRef && mainWin.appRef.getScreenGeometry) {
        for (var infoIdx = 0; infoIdx < setup.screens.length; infoIdx++) {
            screenInfos[infoIdx] = mainWin.appRef.getScreenGeometry(infoIdx)
        }
    }

    for (var i = 0; i < setup.screens.length; i++) {
        var monitor = setup.screens[i]
        if (!monitor) continue
        var monitorInfo = (i < screenInfos.length) ? screenInfos[i] : null
        var splashRect = mainWin.fullRectForScreen(monitor, monitorInfo)
        var sx = Math.round(splashRect.x)
        var sy = Math.round(splashRect.y)
        var sw = Math.max(1, Math.round(splashRect.w))
        var sh = Math.max(1, Math.round(splashRect.h))
        var splashObj = startupSplashComponent.createObject(null, {
            "mainWindow": mainWin,
            "splashX": sx,
            "splashY": sy,
            "splashW": sw,
            "splashH": sh,
            "logoSource": setup.logoUrl,
            "audioSource": setup.audioUrl,
            "audioEnabled": (i === setup.primaryIdx) && (mainWin.soundEffectsEnabled !== false),
            "inputCaptureEnabled": (i === setup.primaryIdx),
            "sharedStartEpochMs": mainWin.startupSplashSequenceEpochMs,
            "launchScreen": monitor,
            "screen": monitor,
            "visible": false
        })
        if (!splashObj) {
            mainWin.phaseLog("SPLASH", "Startup splash create failed monitor idx=" + i
                + " rect=" + mainWin.fmtRect(sx, sy, sw, sh))
            continue
        }
        splashObj.splashX = sx
        splashObj.splashY = sy
        splashObj.splashW = sw
        splashObj.splashH = sh
        created.push({
            "obj": splashObj,
            "idx": i,
            "rect": mainWin.fmtRect(sx, sy, sw, sh)
        })
    }

    return created
}

function assignStartupSplashRefs(mainWin, created, primaryIdx) {
    if (!mainWin) return 0

    mainWin.startupSplashRefs = []
    mainWin.startupSplashRef = null
    for (var i = 0; i < created.length; i++) {
        mainWin.startupSplashRefs.push(created[i].obj)
        if (!mainWin.startupSplashRef && created[i].idx === primaryIdx) {
            mainWin.startupSplashRef = created[i].obj
        }
    }
    if (!mainWin.startupSplashRef && mainWin.startupSplashRefs.length > 0) {
        mainWin.startupSplashRef = mainWin.startupSplashRefs[0]
    }
    mainWin.startupSplashPendingCount = mainWin.startupSplashRefs.length
    return mainWin.startupSplashPendingCount
}
