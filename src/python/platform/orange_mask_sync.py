"""
_OrangeInputMaskSync — Synchronizes the Qt window input mask to the orange canvas
rectangle so only the canvas area receives mouse/touch events.

_AllWindowMaskSyncManager — Attaches an _OrangeInputMaskSync to every CSPM shell
window (main + detached) and keeps the set updated as windows appear/disappear.

Extracted from main.py. Only active on Windows.
"""
import time
from typing import Any

from PySide6.QtCore import QObject, QRect, QRectF, QTimer
from PySide6.QtGui import QGuiApplication, QPainterPath, QRegion


class _OrangeInputMaskSync(QObject):
    """Restrict window hit-testing to the orange canvas rectangle only."""

    def __init__(self, main_window: Any) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._last_mask_key: tuple[object, ...] | None = None
        # Move interaction freezes mask churn for smooth drag.
        # Resize interaction keeps mask live so deformation remains visible.
        self._drag_active = self._is_drag_active()
        self._force_update_pending = False
        self._last_forensic_log_ms = 0.0

        # Poll slowly for safety; geometry signal hooks handle immediate refreshes.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)
        self._poll_timer.timeout.connect(self._schedule_soft_update)
        if not self._drag_active:
            self._poll_timer.start()

        # Coalesce bursty signal updates into one mask recompute per event-loop turn.
        self._coalesce_timer = QTimer(self)
        self._coalesce_timer.setSingleShot(True)
        self._coalesce_timer.setInterval(0)
        self._coalesce_timer.timeout.connect(self._flush_scheduled_update)

        # Fast-path signals that should force mask recomputation.
        for signal_name in (
            "canvasLocalXChanged",
            "canvasLocalYChanged",
            "canvasWChanged",
            "canvasHChanged",
            "activeVisibleRectChanged",
            "canvasFrameGlowThicknessChanged",
            "monitorFrameGlowThicknessChanged",
            "monitorFrameThicknessChanged",
            "visibleChanged",
            "launchConfiguredChanged",
            "isClosingChanged",
            "animationPhaseChanged",
            "startupPhaseChanged",
            "recoveryBandEnabledChanged",
            "recoveryBandHeightChanged",
        ):
            self._connect_signal(signal_name, self._schedule_force_update)

        # Slow-path geometry signals can be coalesced without forcing.
        for signal_name in (
            "widthChanged",
            "heightChanged",
            "xChanged",
            "yChanged",
        ):
            self._connect_signal(signal_name, self._schedule_soft_update)

        self._connect_signal("userMoveInProgressChanged", self._on_drag_state_changed)
        self._connect_signal("userResizeInProgressChanged", self._on_drag_state_changed)
        self._connect_signal("systemMoveInProgressChanged", self._on_drag_state_changed)
        self._connect_signal("dragStrategyChanged", self._on_drag_state_changed)
        QTimer.singleShot(0, self._schedule_force_update)

    def _connect_signal(self, signal_name: str, handler: Any) -> None:
        sig = getattr(self._main_window, signal_name, None)
        if sig is None:
            return
        connect_fn = getattr(sig, "connect", None)
        if not callable(connect_fn):
            return
        try:
            connect_fn(handler)
        except Exception:
            pass

    def _schedule_soft_update(self, *_args: Any) -> None:
        self._schedule_update(force=False)

    def _schedule_force_update(self, *_args: Any) -> None:
        try:
            if bool(self._main_window.property("isClosing")):
                self.update_mask(force=True)
                return
        except Exception:
            pass
        # During move we coalesce updates without forcing to avoid drag jitter.
        if self._drag_active:
            self._schedule_update(force=False)
            return
        self._schedule_update(force=True)

    def _schedule_update(self, force: bool) -> None:
        if force:
            self._force_update_pending = True
        if not self._coalesce_timer.isActive():
            self._coalesce_timer.start()

    def _flush_scheduled_update(self) -> None:
        force = self._force_update_pending
        self._force_update_pending = False
        self.update_mask(force=force)

    def _is_drag_active(self) -> bool:
        win = self._main_window
        if win is None:
            return False
        try:
            if bool(win.property("userMoveInProgress")) or bool(win.property("userResizeInProgress")):
                return True
            if bool(win.property("systemMoveInProgress")):
                return True
            strategy_raw = win.property("dragStrategy")
            strategy = str(strategy_raw) if strategy_raw is not None else ""
            return strategy in ("fallback", "native")
        except Exception:
            return False

    def _on_drag_state_changed(self, *_args: Any) -> None:
        win = self._main_window
        if win is None:
            return

        move_active = self._is_drag_active()
        if move_active == self._drag_active:
            # Resize toggles still require immediate mask refresh.
            self._last_mask_key = None
            if not move_active and not self._poll_timer.isActive():
                self._poll_timer.start()
            self._schedule_force_update()
            return

        self._drag_active = move_active
        self._last_mask_key = None
        if self._drag_active:
            if self._poll_timer.isActive():
                self._poll_timer.stop()
        else:
            if not self._poll_timer.isActive():
                self._poll_timer.start()
        # Entering drag: force immediately to avoid stale mask on press.
        # Exiting drag: defer one event-loop turn so QML settle geometry applies first.
        if self._drag_active:
            try:
                self.update_mask(force=True)
            except Exception:
                pass
        self._schedule_force_update()

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    @staticmethod
    def _as_map(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        to_variant = getattr(value, "toVariant", None)
        if callable(to_variant):
            try:
                maybe = to_variant()
                if isinstance(maybe, dict):
                    return maybe
            except Exception:
                pass
        return {}

    def _mask_forensics_enabled(self) -> bool:
        win = self._main_window
        if win is None:
            return False
        try:
            return bool(win.property("phaseLoggingEnabled"))
        except Exception:
            return False

    def _log_mask_forensics(
        self,
        mode: str,
        mask_region: QRegion,
        corner_radius: int,
        bounded_corner_radius: int,
        bounded: QRect,
        canvas_x: int,
        canvas_y: int,
        canvas_w: int,
        canvas_h: int,
        recovery_band_enabled: bool,
    ) -> None:
        if not self._mask_forensics_enabled():
            return

        now_ms = time.monotonic() * 1000.0
        if (now_ms - self._last_forensic_log_ms) < 120.0:
            return
        self._last_forensic_log_ms = now_ms

        win = self._main_window
        if win is None:
            return

        phase = ""
        try:
            phase_raw = win.property("animationPhase")
            phase = str(phase_raw) if phase_raw is not None else ""
        except Exception:
            phase = ""

        bounds = mask_region.boundingRect()
        from main import _vlog  # avoids circular import at module load time
        _vlog(
            "[MASK] mode="
            + mode
            + " phase="
            + phase
            + " host="
            + str(self._as_int(win.x(), 0))
            + ","
            + str(self._as_int(win.y(), 0))
            + " "
            + str(self._as_int(win.width(), 1))
            + "x"
            + str(self._as_int(win.height(), 1))
            + " canvasLocal="
            + str(canvas_x)
            + ","
            + str(canvas_y)
            + " "
            + str(canvas_w)
            + "x"
            + str(canvas_h)
            + " bounded="
            + str(bounded.x())
            + ","
            + str(bounded.y())
            + " "
            + str(bounded.width())
            + "x"
            + str(bounded.height())
            + " corner="
            + str(corner_radius)
            + "/"
            + str(bounded_corner_radius)
            + " band="
            + ("1" if recovery_band_enabled else "0")
            + " maskBounds="
            + str(bounds.x())
            + ","
            + str(bounds.y())
            + " "
            + str(bounds.width())
            + "x"
            + str(bounds.height())
        )

    def _window_corner_radius_px(self) -> int:
        win = self._main_window
        if win is None:
            return 0

        corner_fn = getattr(win, "shellVisualCornerRadiusPx", None)
        if callable(corner_fn):
            try:
                return max(0, self._as_int(corner_fn(), 0))
            except Exception:
                pass

        corner_fn = getattr(win, "canvasFrameCornerRadiusPx", None)
        if callable(corner_fn):
            try:
                return max(0, self._as_int(corner_fn(), 0))
            except Exception:
                pass

        corner_fn = getattr(win, "chromeCornerRadiusPx", None)
        if callable(corner_fn):
            try:
                return max(0, self._as_int(corner_fn(), 0))
            except Exception:
                pass

        ratios = self._as_map(win.property("layoutRatios"))
        try:
            pct = float(ratios.get("chromeCornerRadiusPct", 0.052))
        except Exception:
            pct = 0.052
        final_w = max(1, self._as_int(win.property("finalW"), self._as_int(win.width(), 1)))
        final_h = max(1, self._as_int(win.property("finalH"), self._as_int(win.height(), 1)))
        return max(0, int(round(min(final_w, final_h) * pct)))

    @staticmethod
    def _rounded_region(rect: QRect, radius_px: int) -> QRegion:
        if rect.width() <= 0 or rect.height() <= 0:
            return QRegion()

        max_radius = max(0, min(rect.width() // 2, rect.height() // 2))
        r = max(0, min(radius_px, max_radius))
        if r <= 0:
            return QRegion(rect)

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), float(r), float(r))
        return QRegion(path.toFillPolygon().toPolygon())

    def _green_frame_region(self, win_w: int, win_h: int) -> QRegion:
        """Return a thin ring where the green debug frame is drawn."""
        win = self._main_window
        active = self._as_map(win.property("activeVisibleRect"))
        if not active:
            return QRegion()

        ax = self._as_int(active.get("x", 0))
        ay = self._as_int(active.get("y", 0))
        aw = max(1, self._as_int(active.get("w", 1), 1))
        ah = max(1, self._as_int(active.get("h", 1), 1))

        win_x = self._as_int(win.x(), 0)
        win_y = self._as_int(win.y(), 0)

        glow = max(1, self._as_int(win.property("monitorFrameGlowThickness"), 1))
        core = max(1, self._as_int(win.property("monitorFrameThickness"), 1))
        band = max(glow, core) + 2

        outer_x = (ax - win_x) - (glow // 2)
        outer_y = (ay - win_y) - (glow // 2)
        outer_w = aw + glow
        outer_h = ah + glow

        outer = QRect(outer_x, outer_y, outer_w, outer_h).intersected(QRect(0, 0, win_w, win_h))
        if outer.width() <= 0 or outer.height() <= 0:
            return QRegion()

        top = QRect(outer.x(), outer.y(), outer.width(), min(band, outer.height()))
        bottom = QRect(outer.x(), max(outer.y(), outer.y() + outer.height() - band), outer.width(), min(band, outer.height()))
        left = QRect(outer.x(), outer.y(), min(band, outer.width()), outer.height())
        right = QRect(max(outer.x(), outer.x() + outer.width() - band), outer.y(), min(band, outer.width()), outer.height())

        region = QRegion(top)
        region = region.united(QRegion(bottom))
        region = region.united(QRegion(left))
        region = region.united(QRegion(right))
        return region

    def _recovery_band_region(self, win_w: int, win_h: int) -> QRegion:
        win = self._main_window
        if win is None:
            return QRegion()
        try:
            if not bool(win.property("recoveryBandEnabled")):
                return QRegion()
        except Exception:
            return QRegion()

        active = self._as_map(win.property("activeVisibleRect"))
        if not active:
            return QRegion()

        ax = self._as_int(active.get("x", 0))
        ay = self._as_int(active.get("y", 0))
        aw = max(1, self._as_int(active.get("w", 1), 1))
        ah = max(1, self._as_int(active.get("h", 1), 1))
        if aw <= 0 or ah <= 0:
            return QRegion()

        band_h = max(1, self._as_int(win.property("recoveryBandHeight"), 1))
        win_x = self._as_int(win.x(), 0)
        win_y = self._as_int(win.y(), 0)

        local = QRect(ax - win_x, ay - win_y, aw, band_h).intersected(QRect(0, 0, win_w, win_h))
        if local.width() <= 0 or local.height() <= 0:
            return QRegion()
        return QRegion(local)

    def update_mask(self, force: bool = False) -> None:
        win = self._main_window
        if win is None:
            return

        win_w = max(1, self._as_int(win.width(), 1))
        win_h = max(1, self._as_int(win.height(), 1))
        corner_radius = self._window_corner_radius_px()
        animation_phase = ""
        try:
            phase_raw = win.property("animationPhase")
            animation_phase = str(phase_raw) if phase_raw is not None else ""
        except Exception:
            animation_phase = ""
        startup_phase = ""
        try:
            startup_phase_raw = win.property("startupPhase")
            startup_phase = str(startup_phase_raw) if startup_phase_raw is not None else ""
        except Exception:
            startup_phase = ""
        is_settled_phase = animation_phase == "settled"
        shell_mask_layer_active = False
        try:
            shell_mask_layer_active = bool(win.property("shellMaskLayerActive"))
        except Exception:
            shell_mask_layer_active = False
        is_true_settled = is_settled_phase and shell_mask_layer_active
        is_closing = False
        try:
            is_closing = bool(win.property("isClosing"))
        except Exception:
            is_closing = False

        # Closing must never use a stale cropped mask while the host envelope jumps.
        if is_closing:
            closing_key = ("closing", win_w, win_h)
            if force or closing_key != self._last_mask_key:
                self._last_mask_key = closing_key
                full_mask = self._rounded_region(QRect(0, 0, win_w, win_h), corner_radius)
                win.setMask(full_mask)
                self._log_mask_forensics(
                    mode="closing",
                    mask_region=full_mask,
                    corner_radius=corner_radius,
                    bounded_corner_radius=corner_radius,
                    bounded=QRect(0, 0, win_w, win_h),
                    canvas_x=self._as_int(win.property("canvasLocalX")),
                    canvas_y=self._as_int(win.property("canvasLocalY")),
                    canvas_w=max(1, self._as_int(win.property("canvasW"), win_w)),
                    canvas_h=max(1, self._as_int(win.property("canvasH"), win_h)),
                    recovery_band_enabled=False,
                )
            return

        # While QML is animating the shell, the native mask must not be tied to
        # the orange canvas. QWindow.setMask affects rendered pixels, not only
        # hit-testing, so a canvas-sized mask becomes an invisible crop frame.
        if not is_settled_phase or startup_phase == "falling-window":
            transition_key = ("transition-full", animation_phase, startup_phase, win_w, win_h)
            if force or transition_key != self._last_mask_key:
                self._last_mask_key = transition_key
                full_mask = QRegion(QRect(0, 0, win_w, win_h))
                win.setMask(full_mask)
                self._log_mask_forensics(
                    mode="transition-full",
                    mask_region=full_mask,
                    corner_radius=0,
                    bounded_corner_radius=0,
                    bounded=QRect(0, 0, win_w, win_h),
                    canvas_x=self._as_int(win.property("canvasLocalX")),
                    canvas_y=self._as_int(win.property("canvasLocalY")),
                    canvas_w=max(1, self._as_int(win.property("canvasW"), win_w)),
                    canvas_h=max(1, self._as_int(win.property("canvasH"), win_h)),
                    recovery_band_enabled=False,
                )
            return

        # During live move/resize, keep mask unconstrained.
        is_interacting = False
        try:
            is_interacting = self._is_drag_active()
        except Exception:
            is_interacting = self._drag_active
        if is_interacting:
            drag_key = ("drag", win_w, win_h)
            if force or drag_key != self._last_mask_key:
                self._last_mask_key = drag_key
                drag_mask = self._rounded_region(QRect(0, 0, win_w, win_h), corner_radius)
                win.setMask(drag_mask)
                self._log_mask_forensics(
                    mode="drag",
                    mask_region=drag_mask,
                    corner_radius=corner_radius,
                    bounded_corner_radius=corner_radius,
                    bounded=QRect(0, 0, win_w, win_h),
                    canvas_x=self._as_int(win.property("canvasLocalX")),
                    canvas_y=self._as_int(win.property("canvasLocalY")),
                    canvas_w=max(1, self._as_int(win.property("canvasW"), win_w)),
                    canvas_h=max(1, self._as_int(win.property("canvasH"), win_h)),
                    recovery_band_enabled=False,
                )
            return

        canvas_x = self._as_int(win.property("canvasLocalX"))
        canvas_y = self._as_int(win.property("canvasLocalY"))
        canvas_w = max(1, self._as_int(win.property("canvasW"), 1))
        canvas_h = max(1, self._as_int(win.property("canvasH"), 1))
        active = self._as_map(win.property("activeVisibleRect"))
        active_x = self._as_int(active.get("x", 0))
        active_y = self._as_int(active.get("y", 0))
        active_w = self._as_int(active.get("w", 0))
        active_h = self._as_int(active.get("h", 0))
        monitor_glow = self._as_int(win.property("monitorFrameGlowThickness"), 0)
        monitor_core = self._as_int(win.property("monitorFrameThickness"), 0)
        canvas_glow = self._as_int(win.property("canvasFrameGlowThickness"), 0)
        win_x = self._as_int(win.x(), 0)
        win_y = self._as_int(win.y(), 0)
        recovery_band_h = max(1, self._as_int(win.property("recoveryBandHeight"), 1))
        effective_corner_radius = corner_radius if is_true_settled else 0
        recovery_band_enabled = False
        try:
            recovery_band_enabled = bool(win.property("recoveryBandEnabled"))
        except Exception:
            recovery_band_enabled = False
        recovery_band_mask_active = False
        try:
            recovery_band_mask_active = bool(win.property("recoveryBandMaskActive"))
        except Exception:
            recovery_band_mask_active = False
        recovery_band_enabled = recovery_band_enabled and recovery_band_mask_active

        raw_rect = QRect(canvas_x, canvas_y, canvas_w, canvas_h)
        bounded = raw_rect.intersected(QRect(0, 0, win_w, win_h))
        bounded_corner_radius = effective_corner_radius
        if bounded.width() > 0 and bounded.height() > 0:
            max_bounded_radius = max(0, min(bounded.width() // 2, bounded.height() // 2))
            bounded_corner_radius = max(0, min(effective_corner_radius, max_bounded_radius))
        key = (
            animation_phase,
            shell_mask_layer_active,
            bounded.x(),
            bounded.y(),
            bounded.width(),
            bounded.height(),
            win_w,
            win_h,
            active_x,
            active_y,
            active_w,
            active_h,
            monitor_glow,
            monitor_core,
            canvas_glow,
            win_x,
            win_y,
            effective_corner_radius,
            bounded_corner_radius,
            recovery_band_h,
            recovery_band_enabled,
        )

        if key == self._last_mask_key:
            return
        self._last_mask_key = key

        mask_region = self._rounded_region(QRect(0, 0, win_w, win_h), effective_corner_radius)
        if bounded.width() > 0 and bounded.height() > 0:
            mask_region = self._rounded_region(bounded, bounded_corner_radius)

        if recovery_band_enabled:
            band_region = self._recovery_band_region(win_w, win_h)
            if not band_region.isEmpty():
                mask_region = mask_region.united(band_region)

        # Keep outer host corners rounded even when extra regions are united into the mask.
        full_window_rounded = self._rounded_region(QRect(0, 0, win_w, win_h), effective_corner_radius)
        if not full_window_rounded.isEmpty():
            mask_region = mask_region.intersected(full_window_rounded)

        if mask_region.isEmpty():
            mask_region = self._rounded_region(QRect(0, 0, win_w, win_h), effective_corner_radius)

        win.setMask(mask_region)
        self._log_mask_forensics(
            mode="settled" if is_true_settled else "transitional",
            mask_region=mask_region,
            corner_radius=effective_corner_radius,
            bounded_corner_radius=bounded_corner_radius,
            bounded=bounded,
            canvas_x=canvas_x,
            canvas_y=canvas_y,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            recovery_band_enabled=recovery_band_enabled,
        )


class _AllWindowMaskSyncManager(QObject):
    """Attach orange-canvas input masks to every CSPM shell window (main + detached)."""

    _TARGET_OBJECT_NAMES = {"CSPMMainWindow", "CSPMFloatingDocketWindow"}

    def __init__(self, app: QGuiApplication) -> None:
        super().__init__(app)
        self._app = app
        self._entries: dict[int, tuple[Any, _OrangeInputMaskSync]] = {}

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

        focus_changed = getattr(app, "focusWindowChanged", None)
        if focus_changed is not None:
            try:
                focus_changed.connect(self.refresh)
            except Exception:
                pass

        QTimer.singleShot(0, self.refresh)

    @classmethod
    def _is_target_window(cls, window_obj: Any) -> bool:
        if window_obj is None:
            return False
        try:
            name = window_obj.objectName()
            if name is None:
                return False
            return str(name) in cls._TARGET_OBJECT_NAMES
        except Exception:
            return False

    def refresh(self, *_args: Any) -> None:
        try:
            windows = list(QGuiApplication.topLevelWindows())
        except Exception:
            windows = []

        seen_ids: set[int] = set()
        for window_obj in windows:
            if not self._is_target_window(window_obj):
                continue
            key = id(window_obj)
            seen_ids.add(key)
            if key in self._entries:
                continue
            try:
                self._entries[key] = (window_obj, _OrangeInputMaskSync(window_obj))
            except Exception:
                pass

        stale_ids = [key for key in self._entries.keys() if key not in seen_ids]
        for key in stale_ids:
            _, sync_obj = self._entries.pop(key)
            try:
                sync_obj.deleteLater()
            except Exception:
                pass

    def clear(self) -> None:
        for _, sync_obj in self._entries.values():
            try:
                sync_obj.deleteLater()
            except Exception:
                pass
        self._entries.clear()
