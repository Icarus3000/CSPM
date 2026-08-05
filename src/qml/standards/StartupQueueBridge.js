.pragma library

function evaluatePauseState(state) {
    var result = {
        "reason": "",
        "startupPostSettleReadyEpochMs": Number(state && state.startupPostSettleReadyEpochMs || 0),
        "startupQueueInputTimeoutReleased": !!(state && state.startupQueueInputTimeoutReleased === true),
        "inputGateElapsedMs": -1
    }

    if (!(state && state.startupDeferredQueueEnabled === true)) {
        result.reason = "queue-disabled"
        return result
    }
    if (!(state.isSettled === true) || String(state.animationPhase || "") !== "settled") {
        result.reason = "window-not-settled"
        return result
    }
    if (!(state.startupHeavyWorkAllowed === true)) {
        result.reason = "startup-heavy-guard"
        return result
    }

    var nowEpochMs = Number(state.nowEpochMs || Date.now())
    var firstInputGateEnabled = (state.startupQueueWaitForFirstInput === true)
        && !(state.detachedMode === true)
        && !(state.startupFirstInputSeen === true)
        && !result.startupQueueInputTimeoutReleased
    if (firstInputGateEnabled) {
        var readyEpoch = result.startupPostSettleReadyEpochMs
        if (readyEpoch <= 0) {
            readyEpoch = nowEpochMs
            result.startupPostSettleReadyEpochMs = readyEpoch
        }
        var inputGateElapsed = Math.max(0, nowEpochMs - readyEpoch)
        result.inputGateElapsedMs = inputGateElapsed
        var fallbackMs = Math.max(0, Number(state.startupQueueInputFallbackMs || 0))
        if (inputGateElapsed < fallbackMs) {
            result.reason = "await-first-input"
            return result
        }
        result.startupQueueInputTimeoutReleased = true
    }

    if (
        state.isClosing === true
        || state.isMinimizing === true
        || state.isRestoringFromMinimize === true
        || state.maximizeAnimInProgress === true
    ) {
        result.reason = "window-transition"
        return result
    }
    if (state.canvasTransitionRunning === true) {
        result.reason = "canvas-transition"
        return result
    }
    if (
        state.userMoveInProgress === true
        || state.userResizeInProgress === true
        || state.systemMoveInProgress === true
        || state.adjacentMoveInProgress === true
        || state.dragFinalizePending === true
        || String(state.dragStrategy || "none") !== "none"
    ) {
        result.reason = "drag-resize"
        return result
    }
    if (state.dragFxReleaseAnimationRunning === true) {
        result.reason = "drag-release"
        return result
    }
    if (state.portalTransitionActive === true) {
        result.reason = "portal-transition"
        return result
    }

    return result
}

