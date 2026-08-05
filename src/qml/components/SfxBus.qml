import QtQuick
import QtMultimedia

Item {
    id: bus
    visible: false
    width: 0
    height: 0

    property string appStyle: "Professional"
    readonly property bool isPro: appStyle === "Professional"

    property bool enabled: true
    property bool lowPerformanceMode: false
    property real masterVolume: lowPerformanceMode ? 0.62 : 0.80
    property real uiVolumeScale: 1.0
    property int defaultCooldownMs: lowPerformanceMode ? 120 : 85
    property var _lastPlayMsByKey: ({})
    property real _queuedLaunchHeavyVolume: 0.62
    property real _queuedCloseImpactStrength: 0.62

    function clamp01(v) {
        if (!isFinite(v)) return 0.0
        if (v < 0.0) return 0.0
        if (v > 1.0) return 1.0
        return v
    }

    function _nowMs() {
        return Date.now()
    }

    function _jitter(multiplier, span) {
        var base = isFinite(multiplier) ? multiplier : 1.0
        var spread = Math.max(0.0, isFinite(span) ? span : 0.0)
        return base + ((Math.random() * 2.0 - 1.0) * spread)
    }

    function _canPlay(cooldownKey, cooldownMs) {
        if (!enabled) return false
        var key = (cooldownKey && String(cooldownKey).length > 0) ? String(cooldownKey) : "global"
        var waitMs = Math.max(0, Math.round(isFinite(cooldownMs) ? cooldownMs : defaultCooldownMs))
        var now = _nowMs()
        var prev = _lastPlayMsByKey[key]
        if (typeof prev === "number" && (now - prev) < waitMs) {
            return false
        }
        _lastPlayMsByKey[key] = now
        return true
    }

    function _play(effectRef, baseVolume, cooldownKey, cooldownMs) {
        if (!effectRef || !enabled) return false
        if (!_canPlay(cooldownKey, cooldownMs)) return false

        var finalVolume = baseVolume
        var finalEffect = effectRef

        if (isPro) {
            finalVolume = baseVolume * 0.35
            if (effectRef === sfxImpactHeavy || effectRef === sfxImpactMid) {
                finalEffect = sfxImpactLight
            }
        }

        var rawVolume = clamp01((isFinite(finalVolume) ? finalVolume : 0.5) * masterVolume * uiVolumeScale)
        var randomizedVolume = clamp01(rawVolume * _jitter(1.0, 0.08))
        finalEffect.volume = randomizedVolume
        if (finalEffect.playing) {
            finalEffect.stop()
        }
        finalEffect.play()
        return true
    }

    function _tierFromStrength(strengthNorm) {
        var s = clamp01(strengthNorm)
        if (s >= 0.80) return "heavy"
        if (s >= 0.45) return "mid"
        return "light"
    }

    function _impactEffectForTier(tier) {
        var key = tier ? String(tier) : "light"
        if (key === "heavy") return sfxImpactHeavy
        if (key === "mid") return sfxImpactMid
        return sfxImpactLight
    }

    function playUiClick(kind, strengthNorm) {
        var mode = kind ? String(kind) : "default"
        var s = clamp01(isFinite(strengthNorm) ? strengthNorm : 0.46)
        if (mode === "danger") {
            _play(sfxImpactHeavy, 0.34 + (s * 0.20), "ui-danger", 95)
            return
        }
        if (mode === "affirm" || mode === "apply" || mode === "confirm") {
            _play(sfxImpactMid, 0.34 + (s * 0.16), "ui-affirm", 85)
            return
        }
        if (mode === "open" || mode === "expand") {
            _play(sfxDeformPop, 0.20 + (s * 0.12), "ui-open-pop", 80)
            _play(sfxImpactLight, 0.25 + (s * 0.12), "ui-open", 72)
            return
        }
        if (mode === "dismiss" || mode === "cancel" || mode === "minimize") {
            _play(sfxImpactLight, 0.24 + (s * 0.10), "ui-dismiss", 78)
            return
        }
        if (mode === "tile") {
            _play(sfxImpactLight, 0.30 + (s * 0.14), "ui-tile", 65)
            return
        }
        if (mode === "hover" || mode === "tile-hover") {
            _play(sfxImpactLight, 0.18 + (s * 0.10), "ui-hover", 52)
            return
        }

        if (s >= 0.72) {
            _play(sfxImpactMid, 0.36 + (s * 0.16), "ui-default-strong", 82)
            return
        }
        _play(sfxImpactLight, 0.28 + (s * 0.12), "ui-default", 72)
    }

    function playTilePress() {
        playUiClick("tile", 0.42)
    }

    function playWindowDeform(strengthNorm) {
        var s = clamp01(strengthNorm)
        _play(sfxDeformPop, 0.34 + (s * 0.20), "window-deform", lowPerformanceMode ? 120 : 90)
    }

    function playBounceFromVelocity(speedNorm) {
        var s = clamp01(speedNorm)
        var tier = _tierFromStrength(s)
        var impact = _impactEffectForTier(tier)
        if (tier === "heavy") {
            _play(impact, 0.54 + (s * 0.22), "bounce-heavy", 90)
        } else if (tier === "mid") {
            _play(impact, 0.46 + (s * 0.18), "bounce-mid", 80)
        } else {
            _play(impact, 0.34 + (s * 0.14), "bounce-light", 75)
        }
    }

    function playLaunchBurst(strengthNorm) {
        var s = clamp01(strengthNorm)
        playWindowDeform(Math.max(0.45, s))
        _queuedLaunchHeavyVolume = clamp01(0.56 + (s * 0.24))
        if (launchHeavyTimer.running) {
            launchHeavyTimer.stop()
        }
        launchHeavyTimer.start()
    }

    function playWindowSettle(kind, strengthNorm) {
        var mode = kind ? String(kind) : "settle"
        var s = clamp01(strengthNorm)
        if (mode === "minimize") {
            _play(sfxImpactLight, 0.30 + (s * 0.14), "settle-min", 90)
            return
        }
        if (mode === "restore") {
            _play(sfxImpactMid, 0.44 + (s * 0.18), "settle-restore", 95)
            return
        }
        if (mode === "dock") {
            _play(sfxImpactMid, 0.50 + (s * 0.16), "settle-dock", 95)
            return
        }
        if (mode === "launch") {
            _play(sfxImpactHeavy, 0.54 + (s * 0.18), "settle-launch", 100)
            return
        }
        _play(sfxImpactMid, 0.46 + (s * 0.16), "settle-default", 90)
    }

    function playWindowCloseFly(strengthNorm) {
        var s = clamp01(isFinite(strengthNorm) ? strengthNorm : 0.62)
        _play(sfxDeformPop, 0.30 + (s * 0.18), "close-fly-deform", lowPerformanceMode ? 135 : 100)
        _queuedCloseImpactStrength = s
        if (closeImpactTimer.running) {
            closeImpactTimer.stop()
        }
        closeImpactTimer.start()
    }

    function playDockSettle(strengthNorm) {
        playWindowSettle("dock", strengthNorm)
    }

    Timer {
        id: launchHeavyTimer
        interval: bus.lowPerformanceMode ? 32 : 24
        repeat: false
        onTriggered: {
            bus._play(sfxImpactHeavy, bus._queuedLaunchHeavyVolume, "launch-heavy", bus.lowPerformanceMode ? 125 : 95)
        }
    }

    Timer {
        id: closeImpactTimer
        interval: bus.lowPerformanceMode ? 88 : 68
        repeat: false
        onTriggered: {
            var s = bus.clamp01(bus._queuedCloseImpactStrength)
            var tier = bus._tierFromStrength(s)
            if (tier === "heavy") {
                bus._play(sfxImpactHeavy, 0.52 + (s * 0.20), "close-fly-impact-heavy", bus.lowPerformanceMode ? 170 : 125)
                return
            }
            bus._play(sfxImpactMid, 0.44 + (s * 0.18), "close-fly-impact-mid", bus.lowPerformanceMode ? 150 : 110)
        }
    }

    SoundEffect {
        id: sfxDeformPop
        source: Qt.resolvedUrl("../../../assets/audio/sfx_splat_deform.wav")
    }

    SoundEffect {
        id: sfxImpactLight
        source: Qt.resolvedUrl("../../../assets/audio/sfx_splat_light.wav")
    }

    SoundEffect {
        id: sfxImpactMid
        source: Qt.resolvedUrl("../../../assets/audio/sfx_splat_mid.wav")
    }

    SoundEffect {
        id: sfxImpactHeavy
        source: Qt.resolvedUrl("../../../assets/audio/sfx_splat_heavy.wav")
    }
}
