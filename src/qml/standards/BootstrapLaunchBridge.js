.pragma library

function resetCreateRetryState(bootstrap, gateCreateRetryTimer) {
    if (!bootstrap) return

    bootstrap._createRetryAttempts = 0
    bootstrap._createRetryReason = ""
    bootstrap._createRetryAllowPrewarm = false
    bootstrap._createRetryExhaustedLogged = false
    if (gateCreateRetryTimer) {
        gateCreateRetryTimer.stop()
    }
}

function scheduleCreateRetry(bootstrap, gateCreateRetryTimer, reason, allowPrewarm) {
    if (!bootstrap) return

    if (bootstrap.mainWindowRef) {
        resetCreateRetryState(bootstrap, gateCreateRetryTimer)
        return
    }
    if (!bootstrap._launchGateOpen && allowPrewarm !== true) return

    if (bootstrap._createRetryAttempts >= bootstrap._createRetryMaxAttempts) {
        if (!bootstrap._createRetryExhaustedLogged) {
            bootstrap._createRetryExhaustedLogged = true
            console.warn("[BOOT] Main window create retries exhausted; reason=" + reason)
            if (bootstrap._lagLog) {
                bootstrap._lagLog("_scheduleCreateRetry exhausted reason=" + reason
                    + " attempts=" + bootstrap._createRetryAttempts)
            }
        }
        return
    }

    if (reason && String(reason).length > 0) {
        bootstrap._createRetryReason = String(reason)
    } else if (bootstrap._createRetryReason.length <= 0) {
        bootstrap._createRetryReason = "unspecified"
    }
    bootstrap._createRetryAllowPrewarm = bootstrap._createRetryAllowPrewarm || (allowPrewarm === true)
    if (gateCreateRetryTimer && gateCreateRetryTimer.running) return

    var intervalMs = Math.min(420, 33 + (bootstrap._createRetryAttempts * 9))
    if (gateCreateRetryTimer) {
        gateCreateRetryTimer.interval = intervalMs
        gateCreateRetryTimer.start()
    }
    if (bootstrap._lagLog) {
        bootstrap._lagLog("_scheduleCreateRetry queued reason=" + bootstrap._createRetryReason
            + " nextAttempt=" + (bootstrap._createRetryAttempts + 1)
            + " inMs=" + intervalMs)
    }
}

function splashGoneMs(bootstrap) {
    if (!bootstrap) return 9600

    if (typeof bootstrap.startupSplashGoneMs === "number" && isFinite(bootstrap.startupSplashGoneMs)) {
        return Math.max(0, Math.round(bootstrap.startupSplashGoneMs))
    }
    return 9600
}

function splashFadeOutStartMs(bootstrap) {
    if (!bootstrap) return Math.max(0, 9600 - 1200)

    if (typeof bootstrap.startupSplashFadeOutStartMs === "number" && isFinite(bootstrap.startupSplashFadeOutStartMs)) {
        return Math.max(0, Math.round(bootstrap.startupSplashFadeOutStartMs))
    }
    return Math.max(0, splashGoneMs(bootstrap) - 1200)
}

function scheduleMainWindowPrewarm(bootstrap, prewarmLoadTimer, prewarmCreateTimer) {
    if (!bootstrap) return
    if (bootstrap._disableSplashPrewarm) return
    if (bootstrap.mainWindowRef || bootstrap._launchGateOpen) return

    bootstrap._prewarmRequested = true
    var goneMs = splashGoneMs(bootstrap)
    var fadeOutStartMs = splashFadeOutStartMs(bootstrap)
    var preloadMs = Math.max(
        350,
        Math.min(
            Math.max(350, fadeOutStartMs),
            Math.max(350, goneMs - 180)
        )
    )

    if (prewarmLoadTimer) {
        prewarmLoadTimer.stop()
        prewarmLoadTimer.interval = preloadMs
        prewarmLoadTimer.start()
    }

    var objectPrewarmEnabled = (bootstrap.startupMainObjectPrewarmEnabled === true)
    if (prewarmCreateTimer) {
        prewarmCreateTimer.stop()
    }
    if (objectPrewarmEnabled) {
        var leadMs = Math.max(600, Math.round(bootstrap.startupMainObjectPrewarmLeadMs))
        var createMs = Math.max(preloadMs + 120, goneMs - leadMs)
        if (prewarmCreateTimer) {
            prewarmCreateTimer.interval = createMs
            prewarmCreateTimer.start()
        }
        if (bootstrap._lagLog) {
            bootstrap._lagLog("_scheduleMainWindowPrewarm preloadMs=" + preloadMs
                + " createMs=" + createMs
                + " leadMs=" + leadMs)
        }
    } else if (bootstrap._lagLog) {
        bootstrap._lagLog("_scheduleMainWindowPrewarm preloadMs=" + preloadMs + " createDisabled=true")
    }
}
