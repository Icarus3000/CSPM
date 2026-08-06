import QtQuick
import "."
import "tray"

Item {
    id: bootstrap

    property var mainWindowRef: null
    property var splashRef: null
    property var splashRefs: []
    property bool _splashFinishedHandled: false
    property int _splashSyncLeadMs: 96
    property var _mainComponent: null
    property bool _launchGateOpen: false
    property bool _componentConnected: false
    property bool _prewarmRequested: false
    property bool _createDispatchQueued: false
    property string _pendingCreateReason: ""
    property bool _pendingCreateAllowPrewarm: false
    property double _componentLoadStartedAtMs: 0
    property double _componentReadyAtMs: 0
    // Preload main-window component during splash so launch-gate handoff is faster.
    // Avoid object creation during splash to keep SVG animation smooth.
    property bool _disableSplashPrewarm: startupMainObjectPrewarmEnabled !== true
    property bool _splashHandoffActive: false
    property bool _firstPixelHandoffSeen: false
    property bool _splashReleasedAfterMainVisible: false
    property bool _launchAfterSplashGonePending: false
    property string _launchAfterSplashGoneReason: ""
    property var _splashGonePendingRefs: []
    property int _splashHandoffTimeoutMs: 2800
    property bool _coreLaunchDispatched: false
    property string _startupState: "init"
    property string _launchGateReason: ""
    property int _startupLaunchScreenIndex: -1
    property int _createRetryAttempts: 0
    property int _createRetryMaxAttempts: 180
    property string _createRetryReason: ""
    property bool _createRetryAllowPrewarm: false
    property bool _createRetryExhaustedLogged: false
    property int _handoffTimeoutRetryCount: 0
    property int _handoffTimeoutRetryMax: 12
    property bool forensicBootEnabled: false
    property int forensicPulseMs: 200

    function forensicLog(msg) {
        if (!forensicBootEnabled) return
        console.warn("[BOOT-FORENSIC] [BOOTSTRAP] " + String(msg || ""))
    }

    function _runtimeConfigSafe() {
        try {
            if (typeof app !== "undefined" && app && app.runtimeConfig) {
                return app.runtimeConfig
            }
        } catch (e0) {
        }
        return null
    }

    function _runtimeStringSafe(key, fallbackValue) {
        var fallback = (fallbackValue === undefined || fallbackValue === null) ? "" : String(fallbackValue)
        var cfg = _runtimeConfigSafe()
        if (!cfg || cfg[key] === undefined || cfg[key] === null) return fallback
        return String(cfg[key])
    }

    function _runtimeIntSafe(key, fallbackValue) {
        var fallback = Number(fallbackValue)
        if (!isFinite(fallback)) fallback = 0
        var cfg = _runtimeConfigSafe()
        if (!cfg || typeof cfg[key] !== "number" || !isFinite(cfg[key])) {
            return Math.round(fallback)
        }
        return Math.round(cfg[key])
    }

    function _runtimeBoolSafe(key, fallbackValue) {
        var fallback = !!fallbackValue
        var cfg = _runtimeConfigSafe()
        if (!cfg || typeof cfg[key] !== "boolean") return fallback
        return cfg[key]
    }

    readonly property string startupSplashLogoUrl: _runtimeStringSafe("startupSplashLogoUrl", "")
    readonly property string startupSplashAudioUrl: _runtimeStringSafe("startupSplashAudioUrl", "")
    readonly property int startupSplashGoneMs: _runtimeIntSafe("startupSplashGoneMs", 9600)
    readonly property int startupSplashFadeOutStartMs: _runtimeIntSafe("startupSplashFadeOutStartMs", 8400)
    readonly property bool startupMainObjectPrewarmEnabled: _runtimeBoolSafe("startupMainObjectPrewarmEnabled", true)
    readonly property int startupMainObjectPrewarmLeadMs: _runtimeIntSafe("startupMainObjectPrewarmLeadMs", 4200)

    signal mainWindowReady(var windowRef)

    Timer {
        id: forensicPulseTimer
        interval: forensicPulseMs
        repeat: true
        running: forensicBootEnabled
        onTriggered: {
            forensicLog("pulse state=" + _startupState
                + " gateOpen=" + _launchGateOpen
                + " splashActive=" + _splashHandoffActive
                + " mainReady=" + (!!mainWindowRef)
                + " component=" + (_mainComponent ? _componentStatusLabel(_mainComponent.status) : "null")
                + " createQueued=" + _createDispatchQueued
                + " retries=" + _createRetryAttempts)
        }
    }

    function _componentStatusLabel(statusValue) {
        if (statusValue === Component.Null) return "Null"
        if (statusValue === Component.Ready) return "Ready"
        if (statusValue === Component.Loading) return "Loading"
        if (statusValue === Component.Error) return "Error"
        return String(statusValue)
    }

    function _lagLog(msg) {
        console.warn("[SPLASH-LAG] [BOOTSTRAP] " + msg)
    }

    function _startupStateRank(state) {
        switch (String(state || "")) {
        case "init": return 0
        case "splash-starting": return 1
        case "splash-running": return 2
        case "gate-open": return 3
        case "main-created": return 4
        case "splash-released": return 5
        case "splash-gone": return 6
        case "core-launch-dispatched": return 7
        default: return 0
        }
    }

    function _setStartupState(nextState, reason) {
        var next = String(nextState || "").trim()
        if (next.length <= 0) return false
        var prev = String(_startupState || "init")
        if (next === prev) return false
        var prevRank = _startupStateRank(prev)
        var nextRank = _startupStateRank(next)
        if (nextRank < prevRank) {
            _lagLog("_setStartupState ignored regression prev=" + prev + " next=" + next + " reason=" + reason)
            return false
        }
        _startupState = next
        _lagLog("_startupState " + prev + " -> " + next + " reason=" + reason)
        return true
    }

    function _safeString(value) {
        if (value === undefined || value === null) return ""
        return String(value)
    }

    function _logoSource() {
        return _safeString((typeof startupSplashLogoUrl !== "undefined") ? startupSplashLogoUrl : "")
    }

    function _audioSource() {
        return _safeString((typeof startupSplashAudioUrl !== "undefined") ? startupSplashAudioUrl : "")
    }

    function _soundEffectsEnabled() {
        try {
            return !((typeof app !== "undefined") && app && app.soundEffectsEnabled === false)
        } catch (e0) {
            return true
        }
    }

    function _indexSafe(value, fallbackValue) {
        if (typeof value !== "number" || !isFinite(value)) return fallbackValue
        var rounded = Math.round(value)
        return rounded >= 0 ? rounded : fallbackValue
    }

    function _resolveStartupLaunchScreenIndex(fallbackValue) {
        var screens = (Qt.application && Qt.application.screens) ? Qt.application.screens : []
        var fallback = _indexSafe(fallbackValue, 0)
        if (!screens || screens.length <= 0) return fallback
        if (_startupLaunchScreenIndex >= 0 && _startupLaunchScreenIndex < screens.length) {
            return _startupLaunchScreenIndex
        }

        var idx = -1
        try {
            if (typeof app !== "undefined" && app && app.getStartupLaunchScreenIndex) {
                idx = _indexSafe(app.getStartupLaunchScreenIndex(), -1)
            }
        } catch (e0) {
        }
        if (idx < 0 || idx >= screens.length) {
            try {
                if (typeof app !== "undefined" && app && app.getCursorScreenIndex) {
                    idx = _indexSafe(app.getCursorScreenIndex(), fallback)
                }
            } catch (e1) {
            }
        }
        if (idx < 0 || idx >= screens.length) idx = fallback
        if (idx < 0 || idx >= screens.length) idx = 0
        _startupLaunchScreenIndex = idx
        return idx
    }

    function _pickStartupScreen() {
        var screens = (Qt.application && Qt.application.screens) ? Qt.application.screens : []
        if (!screens || screens.length <= 0) return null

        var idx = _resolveStartupLaunchScreenIndex(0)
        if (idx < 0 || idx >= screens.length) idx = 0
        return screens[idx]
    }

    function _screenRect(screenObj) {
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

    function _collectSplashRefs() {
        var refs = []
        if (splashRefs && splashRefs.length > 0) {
            refs = splashRefs.slice(0)
        }
        if (splashRef && refs.indexOf(splashRef) < 0) {
            refs.push(splashRef)
        }
        return refs
    }

    function _trackSplashGoneRefs(refs) {
        var pending = []
        if (refs && refs.length > 0) {
            for (var i = 0; i < refs.length; i++) {
                var ref = refs[i]
                if (ref && pending.indexOf(ref) < 0) {
                    pending.push(ref)
                }
            }
        }
        _splashGonePendingRefs = pending
        return pending.length
    }

    function _pruneSplashGonePendingRefs() {
        var refs = _splashGonePendingRefs ? _splashGonePendingRefs.slice(0) : []
        var remaining = []
        for (var i = 0; i < refs.length; i++) {
            var ref = refs[i]
            if (!ref) continue
            var isGone = false
            try {
                isGone = (ref.visible === false)
            } catch (e0) {
                isGone = true
            }
            if (!isGone && remaining.indexOf(ref) < 0) {
                remaining.push(ref)
            }
        }
        _splashGonePendingRefs = remaining
        return remaining.length
    }

    function _destroySplash() {
        var refs = _collectSplashRefs()
        _splashHandoffActive = false
        _firstPixelHandoffSeen = false
        _launchAfterSplashGonePending = false
        _launchAfterSplashGoneReason = ""
        _splashGonePendingRefs = []
        _handoffTimeoutRetryCount = 0
        splashHandoffTimeoutTimer.stop()
        splashGoneLaunchTimer.stop()
        if (refs.length <= 0) return
        _setStartupState("splash-released", "destroy")
        _lagLog("_destroySplash begin count=" + refs.length)
        splashRefs = []
        splashRef = null
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
        _lagLog("_destroySplash complete count=" + refs.length)
    }

    function requestGlobalSplashSkip(reason) {
        var hasSplash = ((splashRefs && splashRefs.length > 0) || !!splashRef)
        if (!hasSplash || _splashFinishedHandled) return
        var reasonText = (reason === undefined || reason === null) ? "" : String(reason)
        if (reasonText.length <= 0) {
            reasonText = "user-skipped-global"
        } else if (reasonText.indexOf("user-skipped") < 0) {
            reasonText = "user-skipped-" + reasonText
        }
        _lagLog("requestGlobalSplashSkip reason=" + reasonText)
        _onSplashFinished(reasonText)
    }

    function _releaseSplashForLaunch(reason) {
        var refs = _collectSplashRefs()
        _splashHandoffActive = false
        _handoffTimeoutRetryCount = 0
        splashHandoffTimeoutTimer.stop()
        if (refs.length <= 0) {
            splashRefs = []
            splashRef = null
            return
        }
        _setStartupState("splash-released", "release:" + reason)
        _lagLog("_releaseSplashForLaunch begin reason=" + reason + " count=" + refs.length)
        splashRefs = []
        splashRef = null
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
    }

    function _queueLaunchAfterSplashGone(reason) {
        _launchAfterSplashGonePending = true
        var reasonText = String(reason || "unknown")
        if (_launchAfterSplashGoneReason.length <= 0) {
            _launchAfterSplashGoneReason = reasonText
        }
    }

    function _maybeLaunchAfterSplashGone(reason) {
        if (!_launchAfterSplashGonePending) return
        if (!mainWindowRef) {
            _requestMainWindowCreate("wait-splash-gone-main:" + String(reason || "unknown"), false)
            splashGoneLaunchTimer.stop()
            splashGoneLaunchTimer.interval = 80
            splashGoneLaunchTimer.start()
            return
        }
        var pendingCount = _pruneSplashGonePendingRefs()
        if (pendingCount > 0) {
            _lagLog("waiting for splash windows to disappear before main launch remaining=" + pendingCount
                + " reason=" + String(reason || "unknown"))
            splashGoneLaunchTimer.stop()
            splashGoneLaunchTimer.interval = 80
            splashGoneLaunchTimer.start()
            return
        }

        var launchReason = _launchAfterSplashGoneReason.length > 0
            ? _launchAfterSplashGoneReason : String(reason || "unknown")
        _launchAfterSplashGonePending = false
        _launchAfterSplashGoneReason = ""
        _splashGonePendingRefs = []
        _splashHandoffActive = false
        splashGoneLaunchTimer.stop()
        if (_coreLaunchDispatched) {
            _lagLog("all splash windows gone after first main pixel; restoring main-window focus reason=" + launchReason)
            Qt.callLater(function() {
                if (!bootstrap.mainWindowRef) return
                try {
                    if (bootstrap.mainWindowRef.forceLaunchFocus) {
                        bootstrap.mainWindowRef.forceLaunchFocus()
                    }
                } catch (e0) {
                }
            })
            return
        }
        _setStartupState("splash-gone", launchReason)
        _lagLog("all splash windows gone; dispatching main launch reason=" + launchReason)
        Qt.callLater(function() {
            bootstrap._beginCoreLaunchOnce("splash-gone:" + launchReason)
        })
    }

    function _releaseSplashAndLaunchAfterGone(reason) {
        if (!mainWindowRef) {
            _queueLaunchAfterSplashGone(reason)
            _requestMainWindowCreate("release-wait-main:" + String(reason || "unknown"), false)
            return
        }
        if (_launchAfterSplashGonePending && _splashGonePendingRefs && _splashGonePendingRefs.length > 0) {
            _maybeLaunchAfterSplashGone("pending-release:" + String(reason || "unknown"))
            return
        }

        var refs = _collectSplashRefs()
        _queueLaunchAfterSplashGone(reason)
        if (_trackSplashGoneRefs(refs) <= 0) {
            _maybeLaunchAfterSplashGone("no-splash:" + String(reason || "unknown"))
            return
        }

        _releaseSplashForLaunch(reason)
        splashGoneLaunchTimer.stop()
        splashGoneLaunchTimer.interval = 80
        splashGoneLaunchTimer.start()
    }

    function _resetCreateRetryState() {
        _createRetryAttempts = 0
        _createRetryReason = ""
        _createRetryAllowPrewarm = false
        _createRetryExhaustedLogged = false
        gateCreateRetryTimer.stop()
    }

    function _scheduleCreateRetry(reason, allowPrewarm) {
        if (mainWindowRef) {
            _resetCreateRetryState()
            return
        }
        if (!_launchGateOpen && allowPrewarm !== true) return
        if (_createRetryAttempts >= _createRetryMaxAttempts) {
            if (!_createRetryExhaustedLogged) {
                _createRetryExhaustedLogged = true
                console.warn("[BOOT] Main window create retries exhausted; reason=" + reason)
                _lagLog("_scheduleCreateRetry exhausted reason=" + reason
                    + " attempts=" + _createRetryAttempts)
            }
            return
        }
        if (reason && String(reason).length > 0) {
            _createRetryReason = String(reason)
        } else if (_createRetryReason.length <= 0) {
            _createRetryReason = "unspecified"
        }
        _createRetryAllowPrewarm = _createRetryAllowPrewarm || (allowPrewarm === true)
        if (gateCreateRetryTimer.running) return
        var intervalMs = Math.min(420, 33 + (_createRetryAttempts * 9))
        gateCreateRetryTimer.interval = intervalMs
        gateCreateRetryTimer.start()
        _lagLog("_scheduleCreateRetry queued reason=" + _createRetryReason
            + " nextAttempt=" + (_createRetryAttempts + 1)
            + " inMs=" + intervalMs)
    }

    function _bindMainWindowStartupSignals(windowRef) {
        if (!windowRef) return
        try {
            if (windowRef.startupFirstPixelVisible) {
                windowRef.startupFirstPixelVisible.connect(function() {
                    if (_firstPixelHandoffSeen) return
                    _firstPixelHandoffSeen = true
                    _lagLog("startupFirstPixelVisible received; releasing splash only now")
                    try {
                        if (windowRef.forceLaunchFocus) {
                            windowRef.forceLaunchFocus()
                        }
                    } catch (e0) {
                    }
                    if (_splashHandoffActive && !_splashReleasedAfterMainVisible) {
                        _splashReleasedAfterMainVisible = true
                        _releaseSplashAndLaunchAfterGone("main-first-pixel")
                    }
                })
            }
        } catch (e) {
        }
    }

    function _bindSplashGone(splashObj) {
        if (!splashObj || !splashObj.splashGone) return
        try {
            splashObj.splashGone.connect(function(reason) {
                bootstrap._onSplashGone(splashObj, reason)
            })
        } catch (e) {
        }
    }

    function _bindSplashFinished(splashObj) {
        if (!splashObj || !splashObj.finished) return
        splashObj.finished.connect(function(reason) {
            var reasonText = (reason === undefined || reason === null) ? "" : String(reason)
            if (reasonText.indexOf("user-skipped") >= 0) {
                bootstrap._lagLog("_bindSplashFinished user-skipped from any monitor")
                bootstrap._onSplashFinished(reasonText)
                return
            }
            if (bootstrap.splashRef === splashObj) {
                bootstrap._onSplashFinished(reasonText)
            }
        })
    }

    function _onSplashGone(splashObj, reason) {
        var refs = _splashGonePendingRefs ? _splashGonePendingRefs.slice(0) : []
        var remaining = []
        for (var i = 0; i < refs.length; i++) {
            var ref = refs[i]
            if (!ref || ref === splashObj) continue
            if (remaining.indexOf(ref) < 0) remaining.push(ref)
        }
        _splashGonePendingRefs = remaining
        _lagLog("_onSplashGone reason=" + String(reason || "unknown")
            + " remaining=" + remaining.length)
        _maybeLaunchAfterSplashGone("splash-gone:" + String(reason || "unknown"))
    }

    function _tryCreateMainWindow(reason, allowPrewarm) {
        if (mainWindowRef) return true
        if (!_mainComponent) {
            _lagLog("_tryCreateMainWindow skipped: no component reason=" + reason)
            _scheduleCreateRetry("no-component:" + reason, allowPrewarm)
            return false
        }
        var prewarm = (allowPrewarm === true)
        if (!_launchGateOpen && !prewarm) {
            _lagLog("_tryCreateMainWindow skipped: gate closed reason=" + reason)
            return false
        }

        if (_mainComponent.status === Component.Loading) {
            _lagLog("_tryCreateMainWindow waiting: component Loading reason=" + reason)
            if (prewarm) {
                if (reason && String(reason).length > 0) {
                    _pendingCreateReason = String(reason)
                }
                _pendingCreateAllowPrewarm = true
                _lagLog("_tryCreateMainWindow prewarm deferred until component Ready")
            }
            return false
        }
        if (_mainComponent.status === Component.Error) {
            _lagLog("_tryCreateMainWindow failed: component Error reason=" + reason)
            console.warn("[BOOT] Main window component failed: " + _mainComponent.errorString())
            _scheduleCreateRetry("component-error:" + reason, prewarm)
            return false
        }
        if (_mainComponent.status !== Component.Ready) {
            _lagLog("_tryCreateMainWindow skipped: component status="
                + _componentStatusLabel(_mainComponent.status)
                + " reason=" + reason)
            _scheduleCreateRetry("component-status-" + _componentStatusLabel(_mainComponent.status) + ":" + reason, prewarm)
            return false
        }

        _lagLog("_tryCreateMainWindow createObject begin reason=" + reason
            + " allowPrewarm=" + prewarm
            + " gateOpen=" + _launchGateOpen)
        var createStartMs = Date.now()
        var created = _mainComponent.createObject(null, {
            "appRef": (typeof app !== "undefined" && app) ? app : null,
            "startupSplashEnabled": false,
            "startupLaunchScreenIndex": _resolveStartupLaunchScreenIndex(0),
            "deferStartupLaunch": true,
            "startupSplashRef": splashRef,
            "startupSplashRefs": (splashRefs && splashRefs.length > 0) ? splashRefs.slice(0) : []
        })
        var createElapsedMs = Math.max(0, Date.now() - createStartMs)
        if (!created) {
            _lagLog("_tryCreateMainWindow createObject returned null reason=" + reason
                + " createElapsedMs=" + createElapsedMs)
            console.warn("[BOOT] Unable to create main window. reason=" + reason)
            _scheduleCreateRetry("create-null:" + reason, prewarm)
            return false
        }
        try {
            if (typeof app !== "undefined" && app) {
                created.appRef = app
            }
        } catch (e0) {
        }
        _resetCreateRetryState()
        _prewarmRequested = false
        mainWindowRef = created
        if (_launchGateOpen) {
            _setStartupState("main-created", reason)
        } else {
            _lagLog("_tryCreateMainWindow prewarmed before gate reason=" + reason)
        }
        _bindMainWindowStartupSignals(created)
        _lagLog("_tryCreateMainWindow createObject success reason=" + reason
            + " createElapsedMs=" + createElapsedMs)
        mainWindowReady(created)
        if (_launchGateOpen) {
            _beginCoreLaunchOnce("main-created:" + reason)
        }
        return true
    }

    function _beginCoreLaunchOnce(reason) {
        if (!mainWindowRef || !mainWindowRef.beginCoreLaunchSequence) return
        if (_coreLaunchDispatched) {
            _lagLog("_beginCoreLaunchOnce ignored duplicate reason=" + reason)
            return
        }
        _coreLaunchDispatched = true
        _setStartupState("core-launch-dispatched", reason)
        try {
            mainWindowRef.deferStartupLaunch = false
        } catch (e1) {
        }
        _lagLog("_beginCoreLaunchOnce dispatch reason=" + reason)
        mainWindowRef.beginCoreLaunchSequence()
    }

    function _requestMainWindowCreate(reason, allowPrewarm) {
        _lagLog("_requestMainWindowCreate reason=" + reason
            + " allowPrewarm=" + (allowPrewarm === true)
            + " queued=" + _createDispatchQueued)
        _pendingCreateReason = (reason && reason.length > 0) ? reason : "unspecified"
        _pendingCreateAllowPrewarm = _pendingCreateAllowPrewarm || (allowPrewarm === true)
        if (_createDispatchQueued) return
        _createDispatchQueued = true
        Qt.callLater(function() {
            _createDispatchQueued = false
            var requestReason = _pendingCreateReason
            var requestAllowPrewarm = _pendingCreateAllowPrewarm
            _pendingCreateReason = ""
            _pendingCreateAllowPrewarm = false
            _lagLog("_requestMainWindowCreate dispatch reason=" + requestReason
                + " allowPrewarm=" + requestAllowPrewarm)
            _tryCreateMainWindow(requestReason, requestAllowPrewarm)
        })
    }

    function _splashGoneMs() {
        if (typeof startupSplashGoneMs === "number" && isFinite(startupSplashGoneMs)) {
            return Math.max(0, Math.round(startupSplashGoneMs))
        }
        return 9600
    }

    function _splashFadeOutStartMs() {
        if (typeof startupSplashFadeOutStartMs === "number" && isFinite(startupSplashFadeOutStartMs)) {
            return Math.max(0, Math.round(startupSplashFadeOutStartMs))
        }
        return Math.max(0, _splashGoneMs() - 1200)
    }

    function _scheduleMainWindowPrewarm() {
        if (_disableSplashPrewarm) return
        if (mainWindowRef || _launchGateOpen) return
        _prewarmRequested = true
        var splashGoneMs = _splashGoneMs()
        // Start component preload earlier so Component.Ready is usually reached
        // before splash end.
        var preloadMs = Math.max(350, Math.round(splashGoneMs * 0.28))
        prewarmLoadTimer.stop()
        prewarmLoadTimer.interval = preloadMs
        prewarmLoadTimer.start()
        var objectPrewarmEnabled = (startupMainObjectPrewarmEnabled === true)
        prewarmCreateTimer.stop()
        if (objectPrewarmEnabled) {
            var leadMs = Math.max(600, Math.round(startupMainObjectPrewarmLeadMs))
            var createMs = Math.max(preloadMs + 120, splashGoneMs - leadMs)
            prewarmCreateTimer.interval = createMs
            prewarmCreateTimer.start()
            _lagLog("_scheduleMainWindowPrewarm preloadMs=" + preloadMs
                + " createMs=" + createMs
                + " leadMs=" + leadMs)
        } else {
            _lagLog("_scheduleMainWindowPrewarm preloadMs=" + preloadMs + " createDisabled=true")
        }
    }

    function _onMainComponentStatusChanged() {
        if (!_mainComponent) return
        _lagLog("_onMainComponentStatusChanged status=" + _componentStatusLabel(_mainComponent.status))
        if (_mainComponent.status === Component.Error) {
            console.warn("[BOOT] Main component error: " + _mainComponent.errorString())
            _scheduleCreateRetry("component-status-error", false)
            return
        }
        if (_mainComponent.status === Component.Loading && _componentLoadStartedAtMs <= 0) {
            _componentLoadStartedAtMs = Date.now()
        }
        if (_mainComponent.status === Component.Ready) {
            _componentReadyAtMs = Date.now()
            if (_componentLoadStartedAtMs > 0) {
                _lagLog("_onMainComponentStatusChanged component Ready loadElapsedMs="
                    + Math.max(0, _componentReadyAtMs - _componentLoadStartedAtMs))
            }
            if (_launchGateOpen) {
                _requestMainWindowCreate("component-ready", false)
            } else if (_pendingCreateAllowPrewarm || _prewarmRequested) {
                _lagLog("_onMainComponentStatusChanged component Ready prewarm create requested")
                _requestMainWindowCreate("component-ready-prewarm", true)
            } else {
                _lagLog("_onMainComponentStatusChanged component Ready cached; waiting launch gate")
            }
        }
    }

    function _preloadMainWindow() {
        if (_mainComponent) {
            _lagLog("_preloadMainWindow skipped: already exists status=" + _componentStatusLabel(_mainComponent.status))
            return
        }
        _componentLoadStartedAtMs = Date.now()
        _componentReadyAtMs = 0
        _lagLog("_preloadMainWindow createComponent begin")
        _mainComponent = Qt.createComponent("DetachedShellWindow.qml", Component.Asynchronous)
        if (!_mainComponent) {
            console.warn("[BOOT] Failed to allocate main component")
            return
        }
        _lagLog("_preloadMainWindow createComponent status=" + _componentStatusLabel(_mainComponent.status))
        if (!_componentConnected) {
            _mainComponent.statusChanged.connect(_onMainComponentStatusChanged)
            _componentConnected = true
        }
        _onMainComponentStatusChanged()
    }

    function _openLaunchGate(reason) {
        if (_launchGateOpen) {
            _lagLog("_openLaunchGate ignored duplicate reason=" + reason + " firstReason=" + _launchGateReason)
            return
        }
        _lagLog("_openLaunchGate begin reason=" + reason)
        _launchGateOpen = true
        _launchGateReason = String(reason || "")
        _setStartupState("gate-open", reason)
        _createRetryExhaustedLogged = false
        _handoffTimeoutRetryCount = 0
        prewarmLoadTimer.stop()
        prewarmCreateTimer.stop()
        _preloadMainWindow()
        var hasSplash = ((splashRefs && splashRefs.length > 0) || !!splashRef)
        if (hasSplash) {
            _splashHandoffActive = true
            _firstPixelHandoffSeen = false
            _splashReleasedAfterMainVisible = false
            splashHandoffTimeoutTimer.stop()
            splashHandoffTimeoutTimer.interval = _splashHandoffTimeoutMs
            splashHandoffTimeoutTimer.start()
            _lagLog("_openLaunchGate splash handoff armed timeoutMs=" + _splashHandoffTimeoutMs)
        } else {
            _destroySplash()
        }
        _requestMainWindowCreate(reason, false)
        if (mainWindowRef) {
            _setStartupState("main-created", "open-launch-gate:" + reason)
            _bindMainWindowStartupSignals(mainWindowRef)
            _beginCoreLaunchOnce("open-launch-gate:" + reason)
        }
        _lagLog("_openLaunchGate end reason=" + reason + " hasMainWindow=" + !!mainWindowRef)
    }

    function _onSplashFinished(reason) {
        if (_splashFinishedHandled) return
        _splashFinishedHandled = true
        _lagLog("_onSplashFinished reason=" + reason)
        _openLaunchGate("splash-finished:" + reason)
    }

    function _startSplash() {
        _setStartupState("splash-starting", "start")
        var logo = _logoSource()
        if (!logo || logo.length <= 0) {
            _openLaunchGate("logo-missing")
            return
        }

        var screens = (Qt.application && Qt.application.screens) ? Qt.application.screens : []
        if (!screens || screens.length <= 0) {
            _openLaunchGate("no-screens")
            return
        }

        var activeIdx = _resolveStartupLaunchScreenIndex(0)
        if (activeIdx < 0 || activeIdx >= screens.length) activeIdx = 0

        var audio = _audioSource()
        var sharedEpochMs = Date.now() + _splashSyncLeadMs
        var createdRefs = []
        var isPro = false
        try {
            if (typeof app !== "undefined" && app && app.appStyle) {
                isPro = String(app.appStyle) === "Professional"
            }
        } catch(e) {}

        for (var i = 0; i < screens.length; i++) {
            var monitor = screens[i]
            if (!monitor) continue
            if (isPro && i !== activeIdx) continue
            var rect = _screenRect(monitor)
            var splashObj = splashComponent.createObject(null, {
                "mainWindow": null,
                "splashX": Math.round(rect.x),
                "splashY": Math.round(rect.y),
                "splashW": Math.max(1, Math.round(rect.w)),
                "splashH": Math.max(1, Math.round(rect.h)),
                "logoSource": logo,
                "audioSource": audio,
                "audioEnabled": (audio.length > 0) && (i === activeIdx) && _soundEffectsEnabled(),
                "inputCaptureEnabled": (i === activeIdx),
                "sharedStartEpochMs": sharedEpochMs,
                "launchScreen": monitor,
                "screen": monitor,
                "holdForLaunchHandoff": true,
                "visible": false,
                "appStyle": isPro ? "Professional" : "Professional"
            })
            if (!splashObj) continue
            createdRefs.push(splashObj)
            if (i === activeIdx) {
                splashRef = splashObj
            }
        }
        if (createdRefs.length <= 0) {
            _openLaunchGate("splash-create-failed")
            return
        }

        if (!splashRef) {
            splashRef = createdRefs[0]
        }
        splashRefs = createdRefs
        _splashFinishedHandled = false
        _setStartupState("splash-running", "splash-created")
        _lagLog("_startSplash multi-monitor count=" + createdRefs.length
            + " activeIdx=" + activeIdx
            + " sharedEpochMs=" + Math.round(sharedEpochMs))
        for (var j = 0; j < createdRefs.length; j++) {
            _bindSplashFinished(createdRefs[j])
            _bindSplashGone(createdRefs[j])
        }
        _scheduleMainWindowPrewarm()
        var startedAny = false
        var startedPrimary = false
        for (var k = 0; k < createdRefs.length; k++) {
            var entry = createdRefs[k]
            if (!entry) continue
            if (entry.startSequence) {
                entry.startSequence()
                startedAny = true
                if (entry === splashRef) startedPrimary = true
            }
        }
        if (!startedAny) {
            _openLaunchGate("splash-no-start")
            return
        }
        if (!startedPrimary) {
            _openLaunchGate("splash-primary-no-start")
        }
    }

    Component {
        id: splashComponent
        SplashOverlay {}
    }

    Timer {
        id: prewarmLoadTimer
        interval: 1
        repeat: false
        onTriggered: {
            bootstrap._preloadMainWindow()
        }
    }

    Timer {
        id: prewarmCreateTimer
        interval: 1
        repeat: false
        onTriggered: {
            if (bootstrap.mainWindowRef || bootstrap._launchGateOpen) return
            bootstrap._lagLog("prewarmCreateTimer triggered; requesting splash object prewarm")
            bootstrap._requestMainWindowCreate("splash-object-prewarm", true)
        }
    }
    Timer {
        id: gateCreateRetryTimer
        interval: 33
        repeat: false
        onTriggered: {
            if (bootstrap.mainWindowRef) {
                bootstrap._resetCreateRetryState()
                return
            }
            if (bootstrap._createRetryAttempts >= bootstrap._createRetryMaxAttempts) {
                bootstrap._scheduleCreateRetry("retry-limit-check", false)
                return
            }
            bootstrap._createRetryAttempts += 1
            var retryReason = bootstrap._createRetryReason
            var retryAllowPrewarm = bootstrap._createRetryAllowPrewarm
            bootstrap._createRetryAllowPrewarm = false
            bootstrap._lagLog("gateCreateRetryTimer fire attempt="
                + bootstrap._createRetryAttempts + "/" + bootstrap._createRetryMaxAttempts
                + " reason=" + retryReason)
            bootstrap._requestMainWindowCreate("retry#" + bootstrap._createRetryAttempts + ":" + retryReason,
                retryAllowPrewarm)
        }
    }
    Timer {
        id: splashHandoffTimeoutTimer
        interval: bootstrap._splashHandoffTimeoutMs
        repeat: false
        onTriggered: {
            if (!bootstrap._splashHandoffActive) return
            if (!bootstrap.mainWindowRef) {
                bootstrap._handoffTimeoutRetryCount += 1
                bootstrap._requestMainWindowCreate("handoff-timeout-retry#" + bootstrap._handoffTimeoutRetryCount, false)
                if (bootstrap._handoffTimeoutRetryCount < bootstrap._handoffTimeoutRetryMax) {
                    bootstrap._lagLog("splash handoff timeout: main window not ready; extending hold retry="
                        + bootstrap._handoffTimeoutRetryCount + "/" + bootstrap._handoffTimeoutRetryMax)
                    splashHandoffTimeoutTimer.start()
                    return
                }
                bootstrap._lagLog("splash handoff retries exhausted; retaining splash until the main window can paint")
                return
            }
            if (!bootstrap._coreLaunchDispatched) {
                bootstrap._lagLog("splash handoff timeout: dispatching main launch while splash remains visible")
                bootstrap._beginCoreLaunchOnce("handoff-timeout-main-create")
            }
            if (!bootstrap._firstPixelHandoffSeen) {
                bootstrap._handoffTimeoutRetryCount += 1
                if (bootstrap._handoffTimeoutRetryCount < bootstrap._handoffTimeoutRetryMax) {
                    bootstrap._lagLog("splash handoff timeout: waiting for main first pixel retry="
                        + bootstrap._handoffTimeoutRetryCount + "/" + bootstrap._handoffTimeoutRetryMax)
                    splashHandoffTimeoutTimer.start()
                } else {
                    bootstrap._lagLog("main first pixel was not observed; retaining splash rather than fading before the app is visible")
                }
            }
        }
    }

    Timer {
        id: splashGoneLaunchTimer
        interval: 80
        repeat: false
        onTriggered: {
            bootstrap._maybeLaunchAfterSplashGone("splash-gone-timer")
        }
    }



    Component.onCompleted: {
        // Do not instantiate SplashOverlay.qml here. Startup uses only the
        // native PNG splash created in main.py; the main shell opens behind it
        // and the PNG fades only after the shell reports its first pixel.
        _openLaunchGate("native-png-splash-only")
    }
}
