import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtMultimedia

// Runtime startup keys are provided through app.runtimeConfig and screen objects
// are resolved dynamically, which qmllint cannot fully infer statically.
// qmllint disable unqualified
// qmllint disable missing-property

ApplicationWindow {
    id: splashWin
    title: "CSPM-StartupSplash"
    objectName: "CSPMStartupSplash"

    property var mainWindow: null
    function _runtimeConfigSafe() {
        try {
            if (mainWindow && mainWindow.appRef && mainWindow.appRef.runtimeConfig) {
                return mainWindow.appRef.runtimeConfig
            }
            if (typeof app !== "undefined" && app && app.runtimeConfig) {
                return app.runtimeConfig
            }
        } catch (e0) {
        }
        return null
    }

    function _runtimeBoolSafe(key, fallbackValue) {
        var fallback = !!fallbackValue
        var cfg = _runtimeConfigSafe()
        if (!cfg || typeof cfg[key] !== "boolean") return fallback
        return cfg[key]
    }

    function _runtimeNumberSafe(key, fallbackValue) {
        var fallback = Number(fallbackValue)
        if (!isFinite(fallback)) fallback = 0
        var cfg = _runtimeConfigSafe()
        if (!cfg || typeof cfg[key] !== "number" || !isFinite(cfg[key])) {
            return fallback
        }
        return Number(cfg[key])
    }

    function _runtimeStringSafe(key, fallbackValue) {
        var fallback = (fallbackValue === undefined || fallbackValue === null) ? "" : String(fallbackValue)
        var cfg = _runtimeConfigSafe()
        if (!cfg || cfg[key] === undefined || cfg[key] === null) return fallback
        return String(cfg[key])
    }

    property string appStyle: {
        try {
            if (mainWindow && mainWindow.appRef && mainWindow.appRef.appStyle) return String(mainWindow.appRef.appStyle);
            if (typeof app !== "undefined" && app && app.appStyle) return String(app.appStyle);
        } catch(e) {}
        return "Professional"
    }
    property bool isPro: appStyle === "Professional"

    readonly property string startupSplashStaticLogoUrl: _runtimeStringSafe("startupSplashStaticLogoUrl", "")
    readonly property bool startupSplashWebViewEnabled: _runtimeBoolSafe("startupSplashWebViewEnabled", false)
    readonly property bool startupSplashWebEngineEnabled: _runtimeBoolSafe("startupSplashWebEngineEnabled", true)
    readonly property bool startupSplashForceWebEngine: _runtimeBoolSafe("startupSplashForceWebEngine", true)
    readonly property real startupSplashLogoSupersample: _runtimeNumberSafe("startupSplashLogoSupersample", 1.15)
    readonly property real startupSplashLogoWebOversample: _runtimeNumberSafe("startupSplashLogoWebOversample", 1.0)
    readonly property int startupSplashLogoMaxTexture: Math.round(_runtimeNumberSafe("startupSplashLogoMaxTexture", 4096))
    readonly property int startupSplashLogoLayerSamples: Math.round(_runtimeNumberSafe("startupSplashLogoLayerSamples", 1))
    readonly property real startupSplashLogoBurnQuality: _runtimeNumberSafe("startupSplashLogoBurnQuality", 1.0)
    readonly property bool startupSplashLogoLayerEnabled: _runtimeBoolSafe("startupSplashLogoLayerEnabled", false)
    readonly property real startupSplashSpeedFactor: _runtimeNumberSafe("startupSplashSpeedFactor", 0.405)
    readonly property int startupSplashLogoLoadWaitMs: Math.round(_runtimeNumberSafe("startupSplashLogoLoadWaitMs", 3000))
    readonly property int startupSplashTotalMs: Math.round(_runtimeNumberSafe("startupSplashTotalMs", 20000))
    readonly property int startupSplashLogoOpenLeadMs: Math.round(_runtimeNumberSafe("startupSplashLogoOpenLeadMs", 1000))
    readonly property int startupSplashWhiteFadeStartMs: Math.round(_runtimeNumberSafe("startupSplashWhiteFadeStartMs", 0))
    readonly property int startupSplashWhiteSolidMs: Math.round(_runtimeNumberSafe("startupSplashWhiteSolidMs", 0))
    readonly property int startupSplashLogoStartMs: Math.round(_runtimeNumberSafe("startupSplashLogoStartMs", 0))
    readonly property int startupSplashSvgFireAshEndMs: Math.round(_runtimeNumberSafe("startupSplashSvgFireAshEndMs", 5500))
    readonly property int startupSplashSvgLightStartMs: Math.round(_runtimeNumberSafe("startupSplashSvgLightStartMs", 5500))
    readonly property int startupSplashSvgLightSweepMs: Math.round(_runtimeNumberSafe("startupSplashSvgLightSweepMs", 0))
    readonly property int startupSplashSvgEndMs: Math.round(_runtimeNumberSafe("startupSplashSvgEndMs", 8000))
    readonly property int startupSplashSvgSolidHoldMs: Math.round(_runtimeNumberSafe("startupSplashSvgSolidHoldMs", 0))
    readonly property int startupSplashFadeOutStartMs: Math.round(_runtimeNumberSafe("startupSplashFadeOutStartMs", 6800))
    readonly property int startupSplashGoneMs: Math.round(_runtimeNumberSafe("startupSplashGoneMs", 20000))
    readonly property int startupSplashFallStartMs: Math.round(_runtimeNumberSafe("startupSplashFallStartMs", 20000))
    readonly property int startupSplashSoundStartMs: Math.round(_runtimeNumberSafe("startupSplashSoundStartMs", 290))
    readonly property int startupSplashAudioDurationMs: Math.round(_runtimeNumberSafe("startupSplashAudioDurationMs", 0))

    property int splashX: 0
    property int splashY: 0
    property int splashW: 1
    property int splashH: 1
    property var launchScreen: null
    property bool inputCaptureEnabled: false
    property string logoSource: ""
    property string staticLogoSource: ((typeof startupSplashStaticLogoUrl !== "undefined")
        && startupSplashStaticLogoUrl) ? String(startupSplashStaticLogoUrl) : ""
    property string logoPlaybackUrl: ""
    property int logoPlaybackReloadToken: 0
    property string audioSource: ""
    property bool audioEnabled: true
    property bool webViewEnabled: ((typeof startupSplashWebViewEnabled !== "undefined")
        && (startupSplashWebViewEnabled === true))
    property bool webViewLoadFailed: false
    property bool webEngineEnabled: ((typeof startupSplashWebEngineEnabled !== "undefined")
        && (startupSplashWebEngineEnabled === true))
    property bool forceWebEngine: ((typeof startupSplashForceWebEngine !== "undefined")
        && (startupSplashForceWebEngine === true))
    property bool webEngineLoadFailed: false
    property string logoRendererKind: "none" // "webengine" | "webview" | "none"
    property bool logoWebReady: false
    property bool webRendererUsingWebEngine: false
    property bool webRendererUsingWebView: false
    property bool webRendererEnabled: false

    property bool sequenceRunning: false
    property bool isDestroying: false
    property bool sequenceFinishedDispatched: false
    property bool splashGoneLogged: false
    property bool waitingForLogoLoad: false
    property bool logoWebLoaderArmed: false
    property bool logoRenderGateOpen: false
    property int logoLoadRetryCount: 0
    property int logoLoadMaxRetries: 2
    property int focusReassertRemaining: 0
    property double sequenceStartEpochMs: 0
    property double sharedStartEpochMs: 0
    property bool sequenceStartQueued: false
    property real lightSweepVisibleOpacityThreshold: 0.08
    property real bgOpacity: 0.0
    property real logoOpacity: 0.0
    property real logoScale: 0.82
    // Larger canvas avoids edge clipping during the splash logo's squash/stretch phases.
    property real logoCanvasPct: 0.90
    property real logoRenderScale: 1.0
    property real logoLayerOversample: ((typeof startupSplashLogoSupersample !== "undefined")
        && (typeof startupSplashLogoSupersample === "number")
        && isFinite(startupSplashLogoSupersample))
        ? Math.max(1.0, startupSplashLogoSupersample) : 1.15
    property real logoWebOversample: ((typeof startupSplashLogoWebOversample !== "undefined")
        && (typeof startupSplashLogoWebOversample === "number")
        && isFinite(startupSplashLogoWebOversample))
        ? Math.max(1.0, startupSplashLogoWebOversample) : 1.0
    property int logoLayerMaxTexturePx: ((typeof startupSplashLogoMaxTexture !== "undefined")
        && (typeof startupSplashLogoMaxTexture === "number")
        && isFinite(startupSplashLogoMaxTexture))
        ? Math.max(1024, Math.round(startupSplashLogoMaxTexture)) : 4096
    property int logoLayerSamples: ((typeof startupSplashLogoLayerSamples !== "undefined")
        && (typeof startupSplashLogoLayerSamples === "number")
        && isFinite(startupSplashLogoLayerSamples))
        ? Math.max(1, Math.round(startupSplashLogoLayerSamples)) : 1
    property real logoDpr: (splashWin.screen && splashWin.screen.devicePixelRatio && isFinite(splashWin.screen.devicePixelRatio))
        ? Math.max(1.0, splashWin.screen.devicePixelRatio) : 1.0
    // Burn/ash stage can run slightly lower quality for faster startup; geometry stays fixed.
    property real logoBurnQualityFactor: ((typeof startupSplashLogoBurnQuality !== "undefined")
        && (typeof startupSplashLogoBurnQuality === "number")
        && isFinite(startupSplashLogoBurnQuality))
        ? Math.max(0.35, Math.min(1.0, startupSplashLogoBurnQuality)) : 1.0
    property bool logoBurnPhaseActive: true
    property real logoMonitorQualityFactor: splashWin.audioEnabled ? 1.0 : 0.55
    property real logoEffectiveLayerOversample: Math.max(1.0, splashWin.logoLayerOversample * splashWin.logoMonitorQualityFactor)
    property real logoEffectiveWebOversample: Math.max(1.0, splashWin.logoWebOversample * splashWin.logoMonitorQualityFactor)
    property int logoEffectiveLayerSamples: Math.max(
        1,
        Math.round(
            splashWin.logoLayerSamples
            * splashWin.logoMonitorQualityFactor
        )
    )
    // Keep layer settings stable for the full splash run to avoid frame stalls
    // when changing texture sampling state mid-animation.
    property bool logoEffectiveMipmap: false
    property int logoEffectiveMaxTexturePx: splashWin.audioEnabled
        ? splashWin.logoLayerMaxTexturePx
        : Math.max(1024, Math.round(splashWin.logoLayerMaxTexturePx * 0.75))
    property bool logoLayerEnabled: ((typeof startupSplashLogoLayerEnabled !== "undefined")
        && (typeof startupSplashLogoLayerEnabled === "boolean"))
        ? startupSplashLogoLayerEnabled : false
    property real sequenceSpeedFactor: ((typeof startupSplashSpeedFactor !== "undefined")
        && (typeof startupSplashSpeedFactor === "number")
        && isFinite(startupSplashSpeedFactor))
        ? Math.max(0.405, Math.min(1.5, startupSplashSpeedFactor)) : 0.405
    property int logoLoadWaitMs: ((typeof startupSplashLogoLoadWaitMs !== "undefined")
        && (typeof startupSplashLogoLoadWaitMs === "number")
        && isFinite(startupSplashLogoLoadWaitMs))
        ? Math.max(250, Math.round(startupSplashLogoLoadWaitMs)) : 3000
    // Legacy total (still used as fallback for timeline end marker).
    property int splashTotalMs: ((typeof startupSplashTotalMs !== "undefined")
        && (typeof startupSplashTotalMs === "number")
        && isFinite(startupSplashTotalMs))
        ? Math.max(7000, Math.round(startupSplashTotalMs)) : 20000
    // Legacy lead control retained for backward compatibility.
    property int logoOpenAdvanceMs: ((typeof startupSplashLogoOpenLeadMs !== "undefined")
        && (typeof startupSplashLogoOpenLeadMs === "number")
        && isFinite(startupSplashLogoOpenLeadMs))
        ? Math.max(0, Math.round(startupSplashLogoOpenLeadMs)) : 1000

    // Legacy-derived defaults (used only when explicit milestone properties are not provided).
    property int splashAudioDelayDefaultMs: Math.max(90, Math.round(170 * splashWin.sequenceSpeedFactor))
    // Keep a clearly visible white fade-in by default.
    property int phase1FadeInDefaultMs: Math.max(480, Math.round(820 * splashWin.sequenceSpeedFactor))
    property int logoFadeInMs: Math.max(58, Math.round(96 * splashWin.sequenceSpeedFactor))
    property int logoOvershootMs: Math.max(88, Math.round(176 * splashWin.sequenceSpeedFactor))
    property int logoSettleMs: Math.max(68, Math.round(122 * splashWin.sequenceSpeedFactor))
    property int logoSnapMs: Math.max(50, Math.round(90 * splashWin.sequenceSpeedFactor))
    property int logoIntroMs: splashWin.logoOvershootMs + splashWin.logoSettleMs + splashWin.logoSnapMs
    // Smooth SVG fade-out before white fade begins
    property int logoQuickFadeOutMs: 680
    // Keep logo fade-out locked to the full phase-4 window.
    property int logoFadeOutMs: Math.max(1, splashWin.phase4FadeOutMs)
    // Keep a smoother white fade-out by default.
    property int phase4FadeOutDefaultMs: Math.max(1250, Math.round(1380 * splashWin.sequenceSpeedFactor))
    property int logoHoldDefaultMs: Math.max(
        0,
        splashWin.splashTotalMs
        - splashWin.phase1FadeInDefaultMs
        - splashWin.logoIntroMs
        - splashWin.phase4FadeOutDefaultMs
    )

    // Explicit timeline milestones (ms from splash sequence start).
    property int timelineWhiteFadeStartMs: ((typeof startupSplashWhiteFadeStartMs !== "undefined")
        && (typeof startupSplashWhiteFadeStartMs === "number")
        && isFinite(startupSplashWhiteFadeStartMs))
        ? Math.max(0, Math.round(startupSplashWhiteFadeStartMs)) : 0
    property int timelineWhiteSolidMs: ((typeof startupSplashWhiteSolidMs !== "undefined")
        && (typeof startupSplashWhiteSolidMs === "number")
        && isFinite(startupSplashWhiteSolidMs))
        ? Math.max(0, Math.round(startupSplashWhiteSolidMs)) : splashWin.phase1FadeInDefaultMs
    property int timelineLogoStartMs: ((typeof startupSplashLogoStartMs !== "undefined")
        && (typeof startupSplashLogoStartMs === "number")
        && isFinite(startupSplashLogoStartMs))
        ? Math.max(0, Math.round(startupSplashLogoStartMs)) : splashWin.phase1FadeInDefaultMs
    property int timelineSvgFireAshEndMs: ((typeof startupSplashSvgFireAshEndMs !== "undefined")
        && (typeof startupSplashSvgFireAshEndMs === "number")
        && isFinite(startupSplashSvgFireAshEndMs))
        ? Math.max(0, Math.round(startupSplashSvgFireAshEndMs)) : 5500
    property int timelineSvgLightStartMs: ((typeof startupSplashSvgLightStartMs !== "undefined")
        && (typeof startupSplashSvgLightStartMs === "number")
        && isFinite(startupSplashSvgLightStartMs))
        ? Math.max(0, Math.round(startupSplashSvgLightStartMs)) : 5500
    property int timelineSvgLightSweepMs: ((typeof startupSplashSvgLightSweepMs !== "undefined")
        && (typeof startupSplashSvgLightSweepMs === "number")
        && isFinite(startupSplashSvgLightSweepMs)
        && startupSplashSvgLightSweepMs > 0)
        ? Math.max(0, Math.round(startupSplashSvgLightSweepMs))
        : Math.max(0, Math.round(2600 * Math.max(1.0, splashWin.sequenceSpeedFactor)))
    property int timelineSvgEndMs: ((typeof startupSplashSvgEndMs !== "undefined")
        && (typeof startupSplashSvgEndMs === "number")
        && isFinite(startupSplashSvgEndMs))
        ? Math.max(0, Math.round(startupSplashSvgEndMs))
        : 8000
    property int timelineSvgEndResolvedMs: Math.max(
        splashWin.timelineSvgEndMs,
        splashWin.timelineSvgLightStartMs + splashWin.timelineSvgLightSweepMs
    )
    property int timelineSvgSolidHoldMs: ((typeof startupSplashSvgSolidHoldMs !== "undefined")
        && (typeof startupSplashSvgSolidHoldMs === "number")
        && isFinite(startupSplashSvgSolidHoldMs)
        && startupSplashSvgSolidHoldMs > 0)
        ? Math.max(0, Math.round(startupSplashSvgSolidHoldMs))
        : Math.max(0, Math.round(520 * splashWin.sequenceSpeedFactor))
    property int timelineFadeOutStartMs: ((typeof startupSplashFadeOutStartMs !== "undefined")
        && (typeof startupSplashFadeOutStartMs === "number")
        && isFinite(startupSplashFadeOutStartMs))
        ? Math.max(0, Math.round(startupSplashFadeOutStartMs))
        : (splashWin.phase1FadeInDefaultMs + splashWin.logoIntroMs + splashWin.logoHoldDefaultMs)
    property int timelineSplashGoneMs: ((typeof startupSplashGoneMs !== "undefined")
        && (typeof startupSplashGoneMs === "number")
        && isFinite(startupSplashGoneMs))
        ? Math.max(0, Math.round(startupSplashGoneMs)) : splashWin.splashTotalMs
    property int timelineFallStartMs: ((typeof startupSplashFallStartMs !== "undefined")
        && (typeof startupSplashFallStartMs === "number")
        && isFinite(startupSplashFallStartMs))
        ? Math.max(0, Math.round(startupSplashFallStartMs)) : splashWin.timelineSplashGoneMs
    property int timelineSoundStartMs: ((typeof startupSplashSoundStartMs !== "undefined")
        && (typeof startupSplashSoundStartMs === "number")
        && isFinite(startupSplashSoundStartMs))
        ? Math.max(0, Math.round(startupSplashSoundStartMs)) : splashWin.splashAudioDelayDefaultMs
    property int timelineAudioDurationMs: ((typeof startupSplashAudioDurationMs !== "undefined")
        && (typeof startupSplashAudioDurationMs === "number")
        && isFinite(startupSplashAudioDurationMs))
        ? Math.max(0, Math.round(startupSplashAudioDurationMs)) : 0

    // Normalized timeline values used by the animation channels.
    property int whiteFadeStartMs: Math.max(0, splashWin.timelineWhiteFadeStartMs)
    property int whiteSolidMs: Math.max(splashWin.whiteFadeStartMs, splashWin.timelineWhiteSolidMs)
    property int logoStartMs: Math.max(0, splashWin.timelineLogoStartMs)
    property int logoIntroEndMs: splashWin.logoStartMs + splashWin.logoIntroMs
    property int svgSolidHoldEndMs: Math.max(splashWin.timelineSvgEndResolvedMs,
        splashWin.timelineSvgEndResolvedMs + splashWin.timelineSvgSolidHoldMs)
    // Fade-out already waits for svgSolidHoldEnd; keep only a tiny guard so
    // the handoff does not linger after the title/audio moment has finished.
    property int fadeOutExtraDelayMs: 120
    property int fadeOutStartMs: Math.max(splashWin.logoIntroEndMs,
        splashWin.timelineFadeOutStartMs,
        splashWin.svgSolidHoldEndMs) + splashWin.fadeOutExtraDelayMs
    property int splashGoneMs: Math.max(splashWin.fadeOutStartMs, splashWin.timelineSplashGoneMs)
    property int phase1FadeInMs: Math.max(0, splashWin.whiteSolidMs - splashWin.whiteFadeStartMs)
    property int phase4FadeOutMs: Math.max(0, splashWin.splashGoneMs - splashWin.fadeOutStartMs)
    property int logoHoldMs: Math.max(0, splashWin.fadeOutStartMs - splashWin.logoIntroEndMs)
    property int splashAudioDelayMs: Math.max(0, splashWin.timelineSoundStartMs)
    property int timelineSoundEndMs: splashWin.splashAudioDelayMs + splashWin.timelineAudioDurationMs
    property int fallStartMs: Math.max(splashWin.splashGoneMs, splashWin.timelineFallStartMs)
    property int postFadeCloseDelayMs: 140
    property string pendingFinishReason: ""
    property bool holdForLaunchHandoff: false
    property bool waitingForLaunchHandoffRelease: false
    property real handoffHoldOpacity: 0.08
    property int handoffReleaseFadeMs: 360
    property string handoffReleaseReason: "launch-ready"

    property bool isSvgAnimationComplete: !splashWin.webRendererEnabled
    property bool hasAppReleasedHandoff: false
    property bool lightSweepTriggered: false

    Timer {
        id: svgAnimationTimer
        interval: splashWin.timelineSvgEndResolvedMs
        repeat: false
        onTriggered: {
            splashWin.phaseLog("SVG animation sequence reached timeline endpoint.");
            splashWin.isSvgAnimationComplete = true;
            if (splashWin.hasAppReleasedHandoff && !handoffReleaseAnim.running) {
                if (splashWin.fadeOutWindowReady()) {
                    splashWin.forceFadeOut();
                } else {
                    splashWin.phaseLog("SVG complete; holding until solid logo window ends.");
                }
            }
        }
    }

    function forceFadeOut() {
        if (handoffReleaseAnim.running) return;
        splashWin.phaseLog("Fading out overlay now.");
        splashSequence.stop();
        splashWin.holdForLaunchHandoff = false;
        handoffReleaseAnim.start();
    }

    function requestGlobalSkip(reason) {
        if (splashWin.isDestroying) return false;
        try {
            if (splashWin.mainWindow && splashWin.mainWindow.requestStartupSplashSkip) {
                splashWin.mainWindow.requestStartupSplashSkip(reason);
                return true;
            }
        } catch (e) {
        }
        return false;
    }

    function triggerSkip(sourceTag) {
        if (splashWin.isDestroying || splashWin.sequenceFinishedDispatched) return;
        var source = sourceTag ? String(sourceTag) : "key";
        if (splashWin.requestGlobalSkip("hotkey-" + source)) return;
        splashWin.finishSequence("user-skipped-overlay-" + source);
    }

    function handleSkipKey(keyValue, sourceTag) {
        if (keyValue !== Qt.Key_Space
                && keyValue !== Qt.Key_Return
                && keyValue !== Qt.Key_Enter
                && keyValue !== Qt.Key_X) {
            return false;
        }
        splashWin.triggerSkip(sourceTag);
        return true;
    }

    function fadeOutWindowReady() {
        if (splashWin.sequenceStartEpochMs <= 0) return true;
        var elapsed = Math.max(0, Math.round(Date.now() - splashWin.sequenceStartEpochMs));
        return elapsed >= splashWin.fadeOutStartMs;
    }

    signal finished(string reason)
    signal splashGone(string reason)

    function targetSplashWidth() {
        return isPro ? 400 : Math.max(1, Math.round(splashW));
    }

    function targetSplashHeight() {
        return isPro ? 250 : Math.max(1, Math.round(splashH));
    }

    function targetSplashX() {
        if (!isPro) return Math.round(splashX);
        return Math.round(splashX + Math.max(0, (Math.max(1, splashW) - targetSplashWidth()) / 2.0));
    }

    function targetSplashY() {
        if (!isPro) return Math.round(splashY);
        return Math.round(splashY + Math.max(0, (Math.max(1, splashH) - targetSplashHeight()) / 2.0));
    }

    function applyStartupScreenGeometry(reasonTag) {
        var desiredScreen = launchScreen ? launchScreen : null;
        try {
            if (desiredScreen) {
                splashWin.screen = desiredScreen;
            }
        } catch (eScreen) {
        }
        splashWin.width = targetSplashWidth();
        splashWin.height = targetSplashHeight();
        splashWin.x = targetSplashX();
        splashWin.y = targetSplashY();
        phaseLog("Pinned startup splash geometry reason=" + (reasonTag ? reasonTag : "unknown")
            + " rect=" + Math.round(splashWin.x) + "," + Math.round(splashWin.y)
            + " " + Math.max(1, Math.round(splashWin.width)) + "x" + Math.max(1, Math.round(splashWin.height)));
    }

    x: targetSplashX()
    y: targetSplashY()
    width: targetSplashWidth()
    height: targetSplashHeight()
    visible: false
    color: isPro ? "transparent" : "transparent"
    flags: isPro ? (Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint) : ((inputCaptureEnabled ? Qt.Window : Qt.Tool)
        | Qt.FramelessWindowHint
        | Qt.NoDropShadowWindowHint
        | Qt.WindowStaysOnTopHint)
    opacity: 1.0

    function phaseLog(msg) {
        var timedMsg = msg;
        try {
            if (splashWin.sequenceStartEpochMs > 0) {
                var elapsed = Math.max(0, Math.round(Date.now() - splashWin.sequenceStartEpochMs));
                timedMsg += " t+" + elapsed + "ms";
            }
        } catch (e) {
        }
        try {
            if (mainWindow && mainWindow.phaseLog) {
                mainWindow.phaseLog("SPLASH", timedMsg);
                return;
            }
        } catch (e) {
        }
        console.log("[SPLASH] " + timedMsg);
    }

    function msToSecText(msValue) {
        var safeMs = 0;
        if (typeof msValue === "number" && isFinite(msValue)) {
            safeMs = Math.max(0, msValue);
        }
        return (safeMs / 1000.0).toFixed(2);
    }

    function pickLogoRendererKind() {
        if (forceWebEngine) {
            if (webEngineEnabled && !webEngineLoadFailed) return "webengine";
            return "none";
        }
        if (webEngineEnabled && !webEngineLoadFailed) return "webengine";
        if (webViewEnabled && !webViewLoadFailed) return "webview";
        return "none";
    }

    function syncLogoRendererFlags() {
        webRendererUsingWebEngine = (logoRendererKind === "webengine");
        webRendererUsingWebView = (logoRendererKind === "webview");
        webRendererEnabled = webRendererUsingWebEngine || webRendererUsingWebView;
    }

    function resetLogoRendererState() {
        webViewLoadFailed = false;
        webEngineLoadFailed = false;
        logoRendererKind = pickLogoRendererKind();
        syncLogoRendererFlags();
    }

    function selectNextLogoRenderer(reasonText) {
        var previous = String(logoRendererKind || "none");
        logoRendererKind = pickLogoRendererKind();
        syncLogoRendererFlags();
        if (logoRendererKind !== previous) {
            phaseLog("Logo renderer switched " + previous + " -> " + logoRendererKind
                + (reasonText ? (" reason=" + reasonText) : ""));
        }
        return logoRendererKind !== "none";
    }

    function refreshLogoPlaybackUrl(forceReload) {
        if (!forceReload && logoPlaybackUrl && logoPlaybackUrl.length > 0) return;
        logoWebReady = false;
        if (forceReload === true) {
            logoPlaybackReloadToken += 1;
        }
        logoPlaybackUrl = "";
        if (logoSource && logoSource.length > 0) {
            var src = String(logoSource);
            if (src.indexOf("file:") === 0 || src.indexOf("qrc:") === 0) {
                logoPlaybackUrl = src;
            } else {
                var sep = (src.indexOf("?") >= 0) ? "&" : "?";
                logoPlaybackUrl = src + sep + "_splashRun=" + String(Date.now());
            }
        }
    }

    function armLogoRendererEarly(forceReload) {
        refreshLogoPlaybackUrl(forceReload === true);
        logoWebLoaderArmed = webRendererEnabled
            && !!(logoSource && logoSource.length > 0)
            && !!(logoPlaybackUrl && logoPlaybackUrl.length > 0);
        return logoWebLoaderArmed;
    }

    function shouldShowStaticLogoFallback() {
        var hasStaticAsset = !!(
            (logoSource && logoSource.length > 0)
            || (staticLogoSource && staticLogoSource.length > 0)
        );
        if (!hasStaticAsset) return false;
        if (!webRendererEnabled) return true;
        // Always keep the native logo visible until the animated WebEngine
        // document has rendered.  This prevents a blank Professional splash
        // during WebEngine warm-up or fallback and lets the in/out dissolve
        // remain visible on every launch path.
        return !logoWebReady;
    }

    function startSplashTimeline(reasonTag) {
        if (sequenceRunning || isDestroying) return;
        waitingForLogoLoad = false;
        logoLoadWaitTimer.stop();
        sequenceRunning = true;
        if (!svgAnimationTimer.running) {
            svgAnimationTimer.start();
        }
        phaseLog("Splash timeline start reason=" + (reasonTag ? reasonTag : "unknown"));
        splashSequence.restart();
    }

    function restartLogoAnimation(reasonTag) {
        try {
            if (logoWebLoader && logoWebLoader.item && logoWebLoader.item.restartAnimation) {
                logoWebLoader.item.restartAnimation();
                phaseLog("SVG animation restart reason=" + (reasonTag ? reasonTag : "unknown"));
            }
        } catch (e) {
            phaseLog("SVG animation restart failed: " + String(e));
        }
    }

    function startSequenceNow() {
        if (sequenceRunning || isDestroying) return;
        applyStartupScreenGeometry("startSequenceNow");
        sequenceStartQueued = false;
        waitingForLogoLoad = false;
        logoLoadRetryCount = 0;
        logoRenderGateOpen = false;
        hasAppReleasedHandoff = false;
        resetLogoRendererState();
        isSvgAnimationComplete = !webRendererEnabled;
        armLogoRendererEarly(false);
        var targetEpochMs = (sharedStartEpochMs > 0) ? sharedStartEpochMs : Date.now();
        sequenceStartEpochMs = targetEpochMs;
        var skewMs = Math.max(0, Math.round(Date.now() - targetEpochMs));
        phaseLog("Sequence start rect=" + Math.round(splashX) + "," + Math.round(splashY)
            + " " + Math.max(1, Math.round(splashW)) + "x" + Math.max(1, Math.round(splashH))
            + " skewMs=" + skewMs);
        phaseLog("Logo source=" + splashWin.logoSource);

        if (splashWin.isPro) {
            splashWin.phaseLog("Professional splash uses the full logo dissolve timeline");
        }

        splashWin.visible = true;
        splashWin.raise();
        if (splashWin.inputCaptureEnabled) {
            try {
                splashWin.requestActivate();
                if (keyCapture && keyCapture.forceActiveFocus) {
                    keyCapture.forceActiveFocus();
                } else if (splashWin.contentItem && splashWin.contentItem.forceActiveFocus) {
                    splashWin.contentItem.forceActiveFocus();
                }
            } catch (e) {
            }
        }
        focusReassertRemaining = 4;
        splashFocusReassertTimer.stop();
        splashFocusReassertTimer.start();
        var hasStaticFallback = !!(staticLogoSource && staticLogoSource.length > 0);
        var shouldTrackWebWarmup = webRendererEnabled
            && logoPlaybackUrl
            && logoPlaybackUrl.length > 0
            && (forceWebEngine || !hasStaticFallback);

        if (shouldTrackWebWarmup) {
            waitingForLogoLoad = true;
            phaseLog("Logo renderer warmup continues asynchronously after first splash frame");
            logoLoadWaitTimer.stop();
            logoLoadWaitTimer.start();
            return;
        }
        startSplashTimeline(webRendererEnabled
            ? (forceWebEngine ? "webengine-async-start" : "web-renderer-async-start")
            : "web-renderer-disabled");
    }

    function startSequence() {
        if (sequenceRunning || isDestroying || sequenceStartQueued) return;
        armLogoRendererEarly(false);
        var targetEpochMs = (sharedStartEpochMs > 0) ? sharedStartEpochMs : Date.now();
        var waitMs = Math.max(0, Math.round(targetEpochMs - Date.now()));
        if (waitMs > 0) {
            sequenceStartQueued = true;
            syncStartTimer.stop();
            syncStartTimer.interval = waitMs;
            syncStartTimer.start();
            return;
        }
        startSequenceNow();
    }

    function finishSequence(reason) {
        if (isDestroying || sequenceFinishedDispatched) return;
        sequenceFinishedDispatched = true;
        phaseLog("Sequence finished reason=" + reason);
        finished(reason);
        pendingFinishReason = reason ? String(reason) : "unknown";
        if (reason === "user-skipped" || (reason && reason.indexOf("skip") >= 0)) {
            holdForLaunchHandoff = false;
        }
        if (holdForLaunchHandoff && !hasAppReleasedHandoff) {
            waitingForLaunchHandoffRelease = true;
            splashWin.opacity = Math.max(splashWin.handoffHoldOpacity, splashWin.opacity);
            splashWin.bgOpacity = Math.max(splashWin.handoffHoldOpacity, splashWin.bgOpacity);
            phaseLog("Holding splash for launch handoff");
            return;
        }
        postFadeCloseTimer.stop();
        postFadeCloseTimer.start();
    }

    function logSplashGoneOnce(reason) {
        if (splashGoneLogged) return;
        splashGoneLogged = true;
        try {
            var goneMs = Math.max(0, Math.round(Date.now() - sequenceStartEpochMs));
            console.warn("[SPLASH-GONE] Splash completely gone t+" + goneMs + "ms reason=" + String(reason || "unknown"));
        } catch (eGone) {
        }
    }

    function releaseForLaunchHandoff(reason) {
        if (isDestroying) return;
        
        splashWin.hasAppReleasedHandoff = true;
        splashWin.holdForLaunchHandoff = false;
        splashWin.handoffReleaseReason = reason ? String(reason) : "launch-ready";
        
        if (!splashWin.isSvgAnimationComplete) {
            splashWin.phaseLog("App is ready, but delaying handoff until SVG completes... (" + splashWin.handoffReleaseReason + ")");
            return;
        }
        if (!splashWin.fadeOutWindowReady()) {
            splashWin.phaseLog("App is ready, but delaying handoff until fade window opens... (" + splashWin.handoffReleaseReason + ")");
            return;
        }

        splashWin.forceFadeOut();
    }

    function closeOverlay(reason) {
        if (isDestroying) return;
        var closeReason = reason ? String(reason) : "unknown";
        isDestroying = true;
        sequenceStartQueued = false;
        waitingForLogoLoad = false;
        logoWebLoaderArmed = false;
        focusReassertRemaining = 0;
        phaseLog("Close reason=" + closeReason);
        logSplashGoneOnce(closeReason);
        try {
            syncStartTimer.stop();
            splashFocusReassertTimer.stop();
            delayedAudioStart.stop();
            if (typeof burnPhaseTimer !== "undefined" && burnPhaseTimer) burnPhaseTimer.stop();
            logoLoadWaitTimer.stop();
            handoffReleaseAnim.stop();
            if (splashAudio.playbackState === MediaPlayer.PlayingState) {
                splashAudio.stop();
            }
        } catch (e) {
        }
        splashWin.visible = false;
        splashWin.close();
        Qt.callLater(function() {
            splashWin.splashGone(closeReason);
            splashWin.destroy();
        });
    }

    function closeForAppExit() {
        closeOverlay("closeForAppExit");
    }

    Shortcut {
        sequence: "Space"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: splashWin.inputCaptureEnabled && splashWin.visible
            && !splashWin.isDestroying && !splashWin.sequenceFinishedDispatched
        onActivated: splashWin.triggerSkip("shortcut-space")
    }

    Shortcut {
        sequence: "Return"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: splashWin.inputCaptureEnabled && splashWin.visible
            && !splashWin.isDestroying && !splashWin.sequenceFinishedDispatched
        onActivated: splashWin.triggerSkip("shortcut-return")
    }

    Shortcut {
        sequence: "Enter"
        context: Qt.ApplicationShortcut
        autoRepeat: false
        enabled: splashWin.inputCaptureEnabled && splashWin.visible
            && !splashWin.isDestroying && !splashWin.sequenceFinishedDispatched
        onActivated: splashWin.triggerSkip("shortcut-enter")
    }

    Rectangle {
        anchors.fill: parent
        color: splashWin.isPro ? "#F8FAFC" : "#FFFFFF"
        opacity: splashWin.bgOpacity
        radius: splashWin.isPro ? 8 : 0
        border.width: splashWin.isPro ? 1 : 0
        border.color: splashWin.isPro ? "#e2e8f0" : "transparent"

        Text {
            visible: splashWin.isPro && !splashWin.logoRenderGateOpen
            anchors.centerIn: parent
            text: "CSPM"
            font.family: "Segoe UI"
            font.pixelSize: 42
            font.letterSpacing: 6
            font.weight: Font.Light
            color: "#0f172a"
        }
    }

    Item {
        id: keyCapture
        anchors.fill: parent
        focus: splashWin.inputCaptureEnabled
        enabled: splashWin.inputCaptureEnabled
        Keys.onPressed: function(event) {
            if (splashWin.handleSkipKey(event.key, "keys")) {
                event.accepted = true;
            }
        }
    }

    Item {
        id: logoWrap
        x: Math.round((parent.width - width) * 0.5)
        y: Math.round((parent.height - height) * 0.5)
        width: Math.max(1, Math.round(Math.min(splashWin.width, splashWin.height) * splashWin.logoCanvasPct))
        height: Math.max(1, Math.round(Math.min(splashWin.width, splashWin.height) * splashWin.logoCanvasPct))
        visible: splashWin.logoRenderGateOpen
        clip: false
        opacity: splashWin.logoOpacity
        layer.enabled: splashWin.logoLayerEnabled
        layer.smooth: true
        layer.mipmap: splashWin.logoEffectiveMipmap
        layer.samples: splashWin.logoEffectiveLayerSamples
        layer.textureSize: Qt.size(
            Math.max(1, Math.min(splashWin.logoEffectiveMaxTexturePx, Math.round(width * splashWin.logoEffectiveLayerOversample * splashWin.logoDpr))),
            Math.max(1, Math.min(splashWin.logoEffectiveMaxTexturePx, Math.round(height * splashWin.logoEffectiveLayerOversample * splashWin.logoDpr)))
        )

        transform: Scale {
            origin.x: Math.round(logoWrap.width / 2.0)
            origin.y: Math.round(logoWrap.height / 2.0)
            xScale: splashWin.logoScale * splashWin.logoRenderScale
            yScale: splashWin.logoScale * splashWin.logoRenderScale
        }

        Item {
            id: logoWebViewport
            anchors.fill: parent
            clip: true
            Image {
                id: logoStatic
                anchors.fill: parent
                source: (splashWin.staticLogoSource && splashWin.staticLogoSource.length > 0)
                    ? splashWin.staticLogoSource
                    : splashWin.logoSource
                fillMode: Image.PreserveAspectFit
                mipmap: true
                smooth: true
                asynchronous: false
                visible: splashWin.shouldShowStaticLogoFallback()
            }

            Loader {
                id: logoWebLoader
                anchors.fill: parent
                active: splashWin.webRendererEnabled
                    && splashWin.logoWebLoaderArmed
                    && splashWin.logoSource
                    && splashWin.logoSource.length > 0
                source: splashWin.webRendererUsingWebView
                    ? "components/SplashLogoWebViewLocal.qml"
                    : (splashWin.webRendererUsingWebEngine
                        ? "components/SplashLogoWebEngineLocal.qml"
                        : "")
                onStatusChanged: {
                    if (status === Loader.Error) {
                        var attempted = splashWin.logoRendererKind;
                        if (attempted === "webview") {
                            splashWin.webViewLoadFailed = true;
                            splashWin.phaseLog("WebView logo loader failed; falling back");
                        } else if (attempted === "webengine") {
                            splashWin.webEngineLoadFailed = true;
                            splashWin.phaseLog(splashWin.forceWebEngine
                                ? "WebEngine logo loader failed; WebEngine-only mode active"
                                : "WebEngine logo loader failed; continuing with static splash");
                        }
                        if (splashWin.selectNextLogoRenderer("loader-error")) {
                            splashWin.refreshLogoPlaybackUrl(true);
                            if (splashWin.waitingForLogoLoad) {
                                logoLoadWaitTimer.stop();
                                logoLoadWaitTimer.start();
                            }
                            return;
                        }
                        if (splashWin.waitingForLogoLoad) {
                            if (!splashWin.sequenceRunning) {
                                splashWin.startSplashTimeline("logo-loader-error");
                            } else {
                                splashWin.waitingForLogoLoad = false;
                                logoLoadWaitTimer.stop();
                            }
                        }
                    } else if (status === Loader.Ready) {
                        splashWin.logoWebReady = false;
                    }
                }
                onLoaded: {
                    if (!item) return;
                    splashWin.logoWebReady = false;
                    item.logoPlaybackUrl = Qt.binding(function() { return splashWin.logoPlaybackUrl; });
                    item.reloadToken = Qt.binding(function() { return splashWin.logoPlaybackReloadToken; });
                    item.logoOversample = Qt.binding(function() { return splashWin.logoEffectiveWebOversample; });
                    item.logoVisible = Qt.binding(function() {
                        return splashWin.logoWebReady
                            && !!(splashWin.logoSource && splashWin.logoSource.length > 0);
                    });
                }
            }

            Connections {
                target: logoWebLoader.item
                ignoreUnknownSignals: true
                function onLoadingChanged(status, errorCode, errorString) {
                    splashWin.phaseLog(
                        "Logo load status="
                        + status
                        + " error=" + errorCode
                        + " " + errorString
                    );
                    if (status === 2) { // WebEngineView.LoadSucceededStatus
                        splashWin.logoWebReady = true;
                        if (splashWin.waitingForLogoLoad) {
                            splashWin.waitingForLogoLoad = false;
                            logoLoadWaitTimer.stop();
                        }
                        if (!svgAnimationTimer.running) {
                            svgAnimationTimer.start();
                        }
                        if (!splashWin.sequenceRunning) {
                            splashWin.startSplashTimeline("logo-loaded");
                        }
                        return;
                    }
                    if (status === 3) { // WebEngineView.LoadFailedStatus
                        splashWin.logoWebReady = false;
                        var attemptedRenderer = splashWin.logoRendererKind;
                        if (attemptedRenderer === "webview") {
                            splashWin.webViewLoadFailed = true;
                            splashWin.phaseLog("WebView logo load failed");
                        } else if (attemptedRenderer === "webengine") {
                            splashWin.webEngineLoadFailed = true;
                            splashWin.phaseLog(splashWin.forceWebEngine
                                ? "WebEngine logo load failed (WebEngine-only mode)"
                                : "WebEngine logo load failed");
                        }
                        if (splashWin.selectNextLogoRenderer("load-failed")) {
                            splashWin.refreshLogoPlaybackUrl(true);
                            logoLoadWaitTimer.stop();
                            logoLoadWaitTimer.start();
                            return;
                        }
                        if (!splashWin.waitingForLogoLoad) {
                            return;
                        }
                        if (splashWin.logoLoadRetryCount < splashWin.logoLoadMaxRetries) {
                            splashWin.logoLoadRetryCount += 1;
                            splashWin.phaseLog("Logo load failed; retry " + splashWin.logoLoadRetryCount
                                + "/" + splashWin.logoLoadMaxRetries);
                            splashWin.refreshLogoPlaybackUrl(true);
                            logoLoadWaitTimer.stop();
                            logoLoadWaitTimer.start();
                            return;
                        }
                        splashWin.phaseLog("Logo load failed after retries; forcing timeline");
                        splashWin.isSvgAnimationComplete = true; // Failsafe
                        if (!splashWin.sequenceRunning) {
                            splashWin.startSplashTimeline("logo-failed-retries-exhausted");
                        }
                        splashWin.waitingForLogoLoad = false;
                        logoLoadWaitTimer.stop();
                    }
                }
            }
        }

    }

    AudioOutput {
        id: splashAudioOutput
        volume: 1.0
    }

    MediaPlayer {
        id: splashAudio
        source: splashWin.audioEnabled ? splashWin.audioSource : ""
        audioOutput: splashAudioOutput
        loops: 1

        onPlaybackStateChanged: {
            if (splashWin.audioEnabled && splashWin.audioSource && splashWin.audioSource.length > 0) {
                splashWin.phaseLog("Splash audio state=" + playbackState);
            }
        }

        onErrorOccurred: function(error, errorString) {
            if (splashWin.audioEnabled && splashWin.audioSource && splashWin.audioSource.length > 0) {
                splashWin.phaseLog("Splash audio error=" + error + " " + String(errorString || ""));
            }
        }
    }

    Timer {
        id: syncStartTimer
        interval: 1
        repeat: false
        onTriggered: splashWin.startSequenceNow()
    }

    Timer {
        id: splashFocusReassertTimer
        interval: 90
        repeat: false
        onTriggered: {
            if (splashWin.isDestroying || !splashWin.visible || !splashWin.sequenceRunning) return
            if (splashWin.focusReassertRemaining <= 0) return
            splashWin.raise()
            if (splashWin.inputCaptureEnabled) {
                try {
                    if (keyCapture && keyCapture.forceActiveFocus) {
                        keyCapture.forceActiveFocus();
                    } else if (splashWin.contentItem && splashWin.contentItem.forceActiveFocus) {
                        splashWin.contentItem.forceActiveFocus();
                    }
                } catch (e) {
                }
            }
            splashWin.focusReassertRemaining = Math.max(0, splashWin.focusReassertRemaining - 1)
            if (splashWin.focusReassertRemaining > 0) {
                splashFocusReassertTimer.start()
            }
        }
    }

    Timer {
        id: delayedAudioStart
        interval: splashWin.splashAudioDelayMs
        repeat: false
        onTriggered: {
            if (splashWin.isDestroying) return;
            if (splashWin.audioEnabled && splashWin.audioSource && splashWin.audioSource.length > 0) {
                splashWin.phaseLog("Splash audio play requested: " + splashWin.audioSource);
                splashAudio.stop();
                splashAudio.play();
            }
        }
    }

    Timer {
        id: logoLoadWaitTimer
        interval: splashWin.logoLoadWaitMs
        repeat: false
        onTriggered: {
            if (splashWin.isDestroying || !splashWin.waitingForLogoLoad) return;
            if (splashWin.logoWebReady || !splashWin.webRendererEnabled) {
                splashWin.waitingForLogoLoad = false;
                return;
            }
            if (splashWin.logoLoadRetryCount < splashWin.logoLoadMaxRetries) {
                splashWin.logoLoadRetryCount += 1;
                splashWin.phaseLog("Logo load wait timeout; retry " + splashWin.logoLoadRetryCount
                    + "/" + splashWin.logoLoadMaxRetries);
                splashWin.refreshLogoPlaybackUrl(true);
                logoLoadWaitTimer.stop();
                logoLoadWaitTimer.start();
                return;
            }
            splashWin.phaseLog("Logo load timeout after retries; forcing timeline");
            if (!splashWin.sequenceRunning) {
                splashWin.startSplashTimeline("logo-timeout-retries-exhausted");
            }
            splashWin.waitingForLogoLoad = false;
        }
    }

    Component.onCompleted: {
        applyStartupScreenGeometry("Component.onCompleted");
        // Prewarm renderer source early so phase-2 animation is visible on time on all monitors.
        resetLogoRendererState();
        armLogoRendererEarly(false);
        if (keyCapture && keyCapture.forceActiveFocus) {
            keyCapture.forceActiveFocus();
        }
    }

    Timer {
        id: lightSweepStartTimer
        interval: splashWin.timelineSvgLightStartMs
        repeat: false
        onTriggered: {
            if (splashWin.isDestroying) return;
            if (!splashWin.logoRenderGateOpen || splashWin.logoOpacity < splashWin.lightSweepVisibleOpacityThreshold) {
                splashWin.forensicLog("lightSweep hard-gated gateOpen=" + splashWin.logoRenderGateOpen
                    + " logoOpacity=" + Number(splashWin.logoOpacity).toFixed(3));
                lightSweepStartTimer.interval = 16;
                lightSweepStartTimer.restart();
                return;
            }
            if (!splashWin.lightSweepTriggered) {
                splashWin.lightSweepTriggered = true;
                splashWin.phaseLog("Light sweep animation triggered at " + splashWin.msToSecText(splashWin.timelineSvgLightStartMs) + "s");
            }
        }
    }

    Timer {
        id: burnPhaseTimer
        interval: Math.max(250, splashWin.timelineSvgFireAshEndMs - splashWin.logoStartMs)
        repeat: false
        onTriggered: {
            if (splashWin.isDestroying) return;
            if (splashWin.logoBurnPhaseActive) {
                splashWin.logoBurnPhaseActive = false;
                splashWin.phaseLog("SVG fire/ash phase ended at " + splashWin.msToSecText(splashWin.timelineSvgFireAshEndMs) + "s");
            }
        }
    }

    Timer {
        id: postFadeCloseTimer
        interval: splashWin.postFadeCloseDelayMs
        repeat: false
        onTriggered: {
            var reason = (splashWin.pendingFinishReason && splashWin.pendingFinishReason.length > 0)
                ? splashWin.pendingFinishReason : "sequence-complete";
            splashWin.closeOverlay("finished-" + reason);
        }
    }

    ParallelAnimation {
        id: handoffReleaseAnim
        running: false
        NumberAnimation {
            target: splashWin
            property: "opacity"
            to: 0.0
            duration: splashWin.handoffReleaseFadeMs
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: splashWin
            property: "bgOpacity"
            to: 0.0
            duration: splashWin.handoffReleaseFadeMs
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: splashWin
            property: "logoOpacity"
            to: 0.0
            duration: Math.round(splashWin.handoffReleaseFadeMs * 0.5)
            easing.type: Easing.OutQuad
        }
        onStopped: {
            if (!splashWin.isDestroying) {
                splashWin.closeOverlay("handoff-release-" + splashWin.handoffReleaseReason);
            }
        }
    }

    SequentialAnimation {
        id: splashSequence
        running: false

        ScriptAction {
            script: {
                splashWin.bgOpacity = 0.0;
                splashWin.logoOpacity = 0.0;
                splashWin.logoScale = 0.82;
                splashWin.opacity = 1.0;
                splashWin.logoRenderGateOpen = false;
                splashWin.sequenceFinishedDispatched = false;
                splashWin.splashGoneLogged = false;
                splashWin.waitingForLaunchHandoffRelease = false;
                splashWin.logoBurnPhaseActive = true;
                splashWin.lightSweepTriggered = false;
                lightSweepStartTimer.stop();
                lightSweepStartTimer.interval = splashWin.timelineSvgLightStartMs;
                lightSweepStartTimer.start();
                splashWin.phaseLog("Timing config speed=" + splashWin.sequenceSpeedFactor
                    + " totalMs=" + splashWin.splashTotalMs
                    + " phase1DefaultMs=" + splashWin.phase1FadeInDefaultMs
                    + " logoLeadMs=" + splashWin.logoOpenAdvanceMs
                    + " holdDefaultMs=" + splashWin.logoHoldDefaultMs
                    + " audioDelayDefaultMs=" + splashWin.splashAudioDelayDefaultMs);
                splashWin.phaseLog("Timeline markers (sec)"
                    + " whiteFadeStart=" + splashWin.msToSecText(splashWin.whiteFadeStartMs)
                    + " whiteSolid=" + splashWin.msToSecText(splashWin.whiteSolidMs)
                    + " logoStart=" + splashWin.msToSecText(splashWin.logoStartMs)
                    + " fireAshEnd=" + splashWin.msToSecText(splashWin.timelineSvgFireAshEndMs)
                    + " lightStart=" + splashWin.msToSecText(splashWin.timelineSvgLightStartMs)
                    + " svgEnd=" + splashWin.msToSecText(splashWin.timelineSvgEndResolvedMs)
                    + " solidHoldEnd=" + splashWin.msToSecText(splashWin.svgSolidHoldEndMs)
                    + " fadeStart=" + splashWin.msToSecText(splashWin.fadeOutStartMs)
                    + " splashGone=" + splashWin.msToSecText(splashWin.splashGoneMs)
                    + " fallStart=" + splashWin.msToSecText(splashWin.fallStartMs)
                    + " soundStart=" + splashWin.msToSecText(splashWin.splashAudioDelayMs)
                    + " soundEnd=" + splashWin.msToSecText(splashWin.timelineSoundEndMs));
                if (splashWin.audioEnabled) {
                    splashWin.phaseLog("Exact current timeline (defaults, to .01s):");
                    splashWin.phaseLog("White fade begins: " + splashWin.msToSecText(splashWin.whiteFadeStartMs) + "s");
                    splashWin.phaseLog("White fully solid: " + splashWin.msToSecText(splashWin.whiteSolidMs) + "s");
                    splashWin.phaseLog("SVG animation begins: " + splashWin.msToSecText(splashWin.logoStartMs) + "s");
                    splashWin.phaseLog("SVG fire/ash phase ends (marker): " + splashWin.msToSecText(splashWin.timelineSvgFireAshEndMs) + "s");
                    splashWin.phaseLog("SVG light sweep begins (marker): " + splashWin.msToSecText(splashWin.timelineSvgLightStartMs) + "s");
                    splashWin.phaseLog("SVG animation ends: " + splashWin.msToSecText(splashWin.timelineSvgEndResolvedMs) + "s");
                    splashWin.phaseLog("Solid logo hold ends: " + splashWin.msToSecText(splashWin.svgSolidHoldEndMs) + "s");
                    splashWin.phaseLog("Splash fade-out begins: " + splashWin.msToSecText(splashWin.fadeOutStartMs) + "s");
                    splashWin.phaseLog("Splash completely gone: " + splashWin.msToSecText(splashWin.splashGoneMs) + "s");
                    splashWin.phaseLog("Falling window begins: " + splashWin.msToSecText(splashWin.fallStartMs) + "s");
                    splashWin.phaseLog("Sound begins: " + splashWin.msToSecText(splashWin.splashAudioDelayMs) + "s");
                    splashWin.phaseLog("Sound ends: " + splashWin.msToSecText(splashWin.timelineSoundEndMs) + "s");
                }
                if (splashWin.audioEnabled && splashWin.audioSource && splashWin.audioSource.length > 0) {
                    delayedAudioStart.stop();
                    delayedAudioStart.start();
                }
                burnPhaseTimer.stop();
                burnPhaseTimer.interval = Math.max(
                    250,
                    splashWin.timelineSvgFireAshEndMs - splashWin.logoStartMs
                );
                burnPhaseTimer.start();
            }
        }
        ParallelAnimation {
            // Channel A: white fade-in (independent absolute timeline marker).
            SequentialAnimation {
                PauseAnimation {
                    duration: splashWin.whiteFadeStartMs
                }
                ScriptAction {
                    script: splashWin.phaseLog("Phase 1: white fade-in");
                }
                NumberAnimation {
                    target: splashWin
                    property: "bgOpacity"
                    from: 0.0
                    to: 1.0
                    duration: splashWin.phase1FadeInMs
                    easing.type: Easing.InOutSine
                }
            }

            // Channel B: logo open + hold.
            SequentialAnimation {
                PauseAnimation {
                    duration: splashWin.logoStartMs
                }
                ScriptAction {
                    script: {
                        splashWin.logoRenderGateOpen = true;
                        splashWin.restartLogoAnimation("logo-open");
                        splashWin.phaseLog("Phase 2: logo-open");
                    }
                }
                ParallelAnimation {
                    NumberAnimation {
                        target: splashWin
                        property: "logoOpacity"
                        from: 0.0
                        to: 1.0
                        duration: splashWin.logoFadeInMs
                        easing.type: Easing.OutQuad
                    }
                    SequentialAnimation {
                        NumberAnimation {
                            target: splashWin
                            property: "logoScale"
                            from: 0.82
                            to: 1.08
                            duration: splashWin.logoOvershootMs
                            easing.type: Easing.OutBack
                        }
                        NumberAnimation {
                            target: splashWin
                            property: "logoScale"
                            to: 0.98
                            duration: splashWin.logoSettleMs
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            target: splashWin
                            property: "logoScale"
                            to: 1.0
                            duration: splashWin.logoSnapMs
                            easing.type: Easing.OutQuad
                        }
                    }
                }
                ScriptAction {
                    script: {
                        splashWin.phaseLog("Phase 3: hold");
                    }
                }
                SequentialAnimation {
                    PauseAnimation {
                        duration: Math.max(0, splashWin.logoHoldMs - splashWin.logoQuickFadeOutMs)
                    }
                    ScriptAction {
                        script: splashWin.phaseLog("SVG quick fade-out begins");
                    }
                    NumberAnimation {
                        target: splashWin
                        property: "logoOpacity"
                        to: 0.0
                        duration: splashWin.logoQuickFadeOutMs
                        easing.type: Easing.OutQuad
                    }
                }
            }

            // Channel C: global fade-out.
            SequentialAnimation {
                PauseAnimation {
                    duration: splashWin.fadeOutStartMs
                }
                ScriptAction {
                    script: splashWin.phaseLog("Phase 4: slow white fade-out");
                }
                ParallelAnimation {
                    NumberAnimation {
                        target: splashWin
                        property: "opacity"
                        to: splashWin.holdForLaunchHandoff ? splashWin.handoffHoldOpacity : 0.0
                        duration: splashWin.phase4FadeOutMs
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: splashWin
                        property: "bgOpacity"
                        to: splashWin.holdForLaunchHandoff ? splashWin.handoffHoldOpacity : 0.0
                        duration: splashWin.phase4FadeOutMs
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        ScriptAction {
            script: splashWin.finishSequence("sequence-complete")
        }
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            splashWin.closeOverlay("aboutToQuit");
        }
    }

    Connections {
        target: splashWin.mainWindow
        function onForceCloseChanged() {
            if (splashWin.mainWindow && splashWin.mainWindow.forceClose) {
                splashWin.closeOverlay("main-force-close");
            }
        }
    }


}
