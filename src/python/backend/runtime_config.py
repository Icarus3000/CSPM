from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Property


class RuntimeConfig(QObject):
    """Typed runtime config surface consumed by QML via app.runtimeConfig."""

    def __init__(
        self,
        *,
        startup_splash_logo_url: str = "",
        startup_splash_static_logo_url: str = "",
        startup_splash_webengine_enabled: bool = True,
        startup_splash_force_webengine: bool = False,
        startup_splash_webview_enabled: bool = False,
        startup_splash_logo_supersample: float = 1.15,
        startup_splash_logo_web_oversample: float = 1.0,
        startup_splash_logo_layer_samples: int = 1,
        startup_splash_logo_max_texture: int = 4096,
        startup_splash_logo_layer_enabled: bool = False,
        startup_splash_logo_burn_quality: float = 1.0,
        startup_splash_logo_load_wait_ms: int = 350,
        startup_splash_logo_open_lead_ms: int = 1000,
        startup_splash_speed_factor: float = 0.405,
        startup_splash_total_ms: int = 9600,
        startup_splash_audio_url: str = "",
        startup_splash_audio_duration_ms: int = 0,
        startup_splash_white_fade_start_ms: int = 0,
        startup_splash_white_solid_ms: int = 820,
        startup_splash_logo_start_ms: int = 820,
        startup_splash_svg_fire_ash_end_ms: int = 5500,
        startup_splash_svg_light_start_ms: int = 5500,
        startup_splash_svg_light_sweep_ms: int = 2600,
        startup_splash_svg_end_ms: int = 8000,
        startup_splash_svg_solid_hold_ms: int = 210,
        startup_splash_fade_out_start_ms: int = 7200,
        startup_splash_gone_ms: int = 9600,
        startup_splash_fall_start_ms: int = 9600,
        startup_splash_sound_start_ms: int = 290,
        search_bar_debug_enabled: bool = False,
        debug_frames_enabled: bool = False,
        verbose_logging_enabled: bool = False,
        startup_deferred_queue_mode: str = "off",
        startup_deferred_queue_internal_enabled: bool = False,
        startup_deferred_queue_tick_ms: int = 180,
        startup_main_object_prewarm_enabled: bool = False,
        startup_main_object_prewarm_lead_ms: int = 4200,
        startup_fast_launch_focus_enabled: bool = True,
        startup_queue_wait_for_first_input: bool = False,
        startup_queue_input_fallback_ms: int = 0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._startup_splash_logo_url = str(startup_splash_logo_url or "")
        self._startup_splash_static_logo_url = str(startup_splash_static_logo_url or "")
        self._startup_splash_webengine_enabled = bool(startup_splash_webengine_enabled)
        self._startup_splash_force_webengine = bool(startup_splash_force_webengine)
        self._startup_splash_webview_enabled = bool(startup_splash_webview_enabled)
        self._startup_splash_logo_supersample = float(startup_splash_logo_supersample)
        self._startup_splash_logo_web_oversample = float(startup_splash_logo_web_oversample)
        self._startup_splash_logo_layer_samples = int(startup_splash_logo_layer_samples)
        self._startup_splash_logo_max_texture = int(startup_splash_logo_max_texture)
        self._startup_splash_logo_layer_enabled = bool(startup_splash_logo_layer_enabled)
        self._startup_splash_logo_burn_quality = float(startup_splash_logo_burn_quality)
        self._startup_splash_logo_load_wait_ms = int(startup_splash_logo_load_wait_ms)
        self._startup_splash_logo_open_lead_ms = int(startup_splash_logo_open_lead_ms)
        self._startup_splash_speed_factor = float(startup_splash_speed_factor)
        self._startup_splash_total_ms = int(startup_splash_total_ms)
        self._startup_splash_audio_url = str(startup_splash_audio_url or "")
        self._startup_splash_audio_duration_ms = int(startup_splash_audio_duration_ms)
        self._startup_splash_white_fade_start_ms = int(startup_splash_white_fade_start_ms)
        self._startup_splash_white_solid_ms = int(startup_splash_white_solid_ms)
        self._startup_splash_logo_start_ms = int(startup_splash_logo_start_ms)
        self._startup_splash_svg_fire_ash_end_ms = int(startup_splash_svg_fire_ash_end_ms)
        self._startup_splash_svg_light_start_ms = int(startup_splash_svg_light_start_ms)
        self._startup_splash_svg_light_sweep_ms = int(startup_splash_svg_light_sweep_ms)
        self._startup_splash_svg_end_ms = int(startup_splash_svg_end_ms)
        self._startup_splash_svg_solid_hold_ms = int(startup_splash_svg_solid_hold_ms)
        self._startup_splash_fade_out_start_ms = int(startup_splash_fade_out_start_ms)
        self._startup_splash_gone_ms = int(startup_splash_gone_ms)
        self._startup_splash_fall_start_ms = int(startup_splash_fall_start_ms)
        self._startup_splash_sound_start_ms = int(startup_splash_sound_start_ms)
        self._search_bar_debug_enabled = bool(search_bar_debug_enabled)
        self._debug_frames_enabled = bool(debug_frames_enabled)
        self._verbose_logging_enabled = bool(verbose_logging_enabled)
        mode_text = str(startup_deferred_queue_mode or "").strip().lower()
        if mode_text not in {"off", "internal", "on"}:
            mode_text = "internal"
        self._startup_deferred_queue_mode = mode_text
        self._startup_deferred_queue_internal_enabled = bool(startup_deferred_queue_internal_enabled)
        self._startup_deferred_queue_tick_ms = max(24, int(startup_deferred_queue_tick_ms))
        self._startup_main_object_prewarm_enabled = bool(startup_main_object_prewarm_enabled)
        self._startup_main_object_prewarm_lead_ms = max(600, int(startup_main_object_prewarm_lead_ms))
        self._startup_fast_launch_focus_enabled = bool(startup_fast_launch_focus_enabled)
        self._startup_queue_wait_for_first_input = bool(startup_queue_wait_for_first_input)
        self._startup_queue_input_fallback_ms = max(0, int(startup_queue_input_fallback_ms))

    @Property(str, constant=True)
    def startupSplashLogoUrl(self) -> str:
        return self._startup_splash_logo_url

    @Property(str, constant=True)
    def startupSplashStaticLogoUrl(self) -> str:
        return self._startup_splash_static_logo_url

    @Property(bool, constant=True)
    def startupSplashWebEngineEnabled(self) -> bool:
        return self._startup_splash_webengine_enabled

    @Property(bool, constant=True)
    def startupSplashForceWebEngine(self) -> bool:
        return self._startup_splash_force_webengine

    @Property(bool, constant=True)
    def startupSplashWebViewEnabled(self) -> bool:
        return self._startup_splash_webview_enabled

    @Property(float, constant=True)
    def startupSplashLogoSupersample(self) -> float:
        return self._startup_splash_logo_supersample

    @Property(float, constant=True)
    def startupSplashLogoWebOversample(self) -> float:
        return self._startup_splash_logo_web_oversample

    @Property(int, constant=True)
    def startupSplashLogoLayerSamples(self) -> int:
        return self._startup_splash_logo_layer_samples

    @Property(int, constant=True)
    def startupSplashLogoMaxTexture(self) -> int:
        return self._startup_splash_logo_max_texture

    @Property(bool, constant=True)
    def startupSplashLogoLayerEnabled(self) -> bool:
        return self._startup_splash_logo_layer_enabled

    @Property(float, constant=True)
    def startupSplashLogoBurnQuality(self) -> float:
        return self._startup_splash_logo_burn_quality

    @Property(int, constant=True)
    def startupSplashLogoLoadWaitMs(self) -> int:
        return self._startup_splash_logo_load_wait_ms

    @Property(int, constant=True)
    def startupSplashLogoOpenLeadMs(self) -> int:
        return self._startup_splash_logo_open_lead_ms

    @Property(float, constant=True)
    def startupSplashSpeedFactor(self) -> float:
        return self._startup_splash_speed_factor

    @Property(int, constant=True)
    def startupSplashTotalMs(self) -> int:
        return self._startup_splash_total_ms

    @Property(str, constant=True)
    def startupSplashAudioUrl(self) -> str:
        return self._startup_splash_audio_url

    @Property(int, constant=True)
    def startupSplashAudioDurationMs(self) -> int:
        return self._startup_splash_audio_duration_ms

    @Property(int, constant=True)
    def startupSplashWhiteFadeStartMs(self) -> int:
        return self._startup_splash_white_fade_start_ms

    @Property(int, constant=True)
    def startupSplashWhiteSolidMs(self) -> int:
        return self._startup_splash_white_solid_ms

    @Property(int, constant=True)
    def startupSplashLogoStartMs(self) -> int:
        return self._startup_splash_logo_start_ms

    @Property(int, constant=True)
    def startupSplashSvgFireAshEndMs(self) -> int:
        return self._startup_splash_svg_fire_ash_end_ms

    @Property(int, constant=True)
    def startupSplashSvgLightStartMs(self) -> int:
        return self._startup_splash_svg_light_start_ms

    @Property(int, constant=True)
    def startupSplashSvgLightSweepMs(self) -> int:
        return self._startup_splash_svg_light_sweep_ms

    @Property(int, constant=True)
    def startupSplashSvgEndMs(self) -> int:
        return self._startup_splash_svg_end_ms

    @Property(int, constant=True)
    def startupSplashSvgSolidHoldMs(self) -> int:
        return self._startup_splash_svg_solid_hold_ms

    @Property(int, constant=True)
    def startupSplashFadeOutStartMs(self) -> int:
        return self._startup_splash_fade_out_start_ms

    @Property(int, constant=True)
    def startupSplashGoneMs(self) -> int:
        return self._startup_splash_gone_ms

    @Property(int, constant=True)
    def startupSplashFallStartMs(self) -> int:
        return self._startup_splash_fall_start_ms

    @Property(int, constant=True)
    def startupSplashSoundStartMs(self) -> int:
        return self._startup_splash_sound_start_ms

    @Property(bool, constant=True)
    def searchBarDebugEnabled(self) -> bool:
        return self._search_bar_debug_enabled

    @Property(bool, constant=True)
    def debugFramesEnabled(self) -> bool:
        return self._debug_frames_enabled

    @Property(bool, constant=True)
    def verboseLoggingEnabled(self) -> bool:
        return self._verbose_logging_enabled

    @Property(str, constant=True)
    def startupDeferredQueueMode(self) -> str:
        return self._startup_deferred_queue_mode

    @Property(bool, constant=True)
    def startupDeferredQueueInternalEnabled(self) -> bool:
        return self._startup_deferred_queue_internal_enabled

    @Property(int, constant=True)
    def startupDeferredQueueTickMs(self) -> int:
        return self._startup_deferred_queue_tick_ms

    @Property(bool, constant=True)
    def startupMainObjectPrewarmEnabled(self) -> bool:
        return self._startup_main_object_prewarm_enabled

    @Property(int, constant=True)
    def startupMainObjectPrewarmLeadMs(self) -> int:
        return self._startup_main_object_prewarm_lead_ms

    @Property(bool, constant=True)
    def startupFastLaunchFocusEnabled(self) -> bool:
        return self._startup_fast_launch_focus_enabled

    @Property(bool, constant=True)
    def startupQueueWaitForFirstInput(self) -> bool:
        return self._startup_queue_wait_for_first_input

    @Property(int, constant=True)
    def startupQueueInputFallbackMs(self) -> int:
        return self._startup_queue_input_fallback_ms
