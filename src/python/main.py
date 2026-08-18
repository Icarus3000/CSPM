import os
import sys
import argparse
os.environ["QML_DISABLE_DISK_CACHE"] = "1"
os.environ["QML_FORCE_DISK_CACHE_DISABLE"] = "1"
import re
import atexit
import ctypes

import logging
from bootstrap.runtime_bootstrap import (
    bootstrap_logging_and_qt_bridge,
    install_global_exception_hooks,
    report_nonfatal_startup_failure as _report_nonfatal_startup_failure,
    report_terminal_failure as _report_terminal_failure,
)

# Avoid transient file locks in OneDrive-synced workspaces unless explicitly overridden.
# Set this before local module imports so Python never writes source-tree bytecode.
if os.environ.get("CSPM_WRITE_BYTECODE", "").strip().lower() not in {"1", "true", "yes", "on"}:
    sys.dont_write_bytecode = True

# Force QtWebEngine to use its dedicated GUI subsystem executable.
# If it uses python.exe (which is a Console subsystem app), it will spawn visible
# console windows for every background Chromium helper process it launches!
try:
    if not getattr(sys, 'frozen', False):
        import PySide6
        from pathlib import Path
        _pyside_dir = Path(PySide6.__file__).parent
        _webengine_process = _pyside_dir / "QtWebEngineProcess.exe"
        if _webengine_process.exists():
            os.environ["QTWEBENGINEPROCESS_PATH"] = str(_webengine_process)
except Exception:
    pass

bootstrap_logging_and_qt_bridge()
logging.info("=== CSPM APPLICATION START ===")

install_global_exception_hooks()

import math
import time
t0 = time.perf_counter()
startup_logger = logging.getLogger('startup')
startup_logger.info(f'[{time.perf_counter()-t0:.3f}s] Boot Initiated')
import wave
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PySide6 import QtCore
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    Qt,
    QtMsgType,
    QTimer,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPen
from PySide6.QtCore import Qt, QElapsedTimer, QRectF, QTimer, QVariantAnimation, Property, QEasingCurve, QPropertyAnimation

class CustomSplash(QWidget):
    """Native, readiness-driven splash and the first two opening acts.

    The QML shell is fully hydrated and rendered at a frozen centre pinpoint
    while the native splash remains focused.  The plasma implosion can then
    hand directly to QML's centre-out bloom without a dead frame or host flash.
    """

    cinematicBloomPrestageRequested = QtCore.Signal()
    cinematicRevealReady = QtCore.Signal()

    _ACT_I_VORTEX_MS = 550
    _ACT_II_BURST_MS = 150
    _ACT_II_HOLD_MS = 80
    _ACT_II_IMPLODE_MS = 220
    _BAR_COMPLETION_MS = 180
    _PROGRESS_MAX_RATE_PER_SEC = 0.20

    def __init__(self, pixmap_path):
        # This splash deliberately owns the visual foreground until the plasma
        # implodes.  The pre-hydrated QML host stays hidden until that point,
        # so Windows cannot raise a full application frame over this logo.
        splash_flags = (
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        # QSplashScreen paints its supplied pixmap before a subclass's custom
        # paint path.  Its former empty pixmap produced the observed black
        # square before the CS logo.  A transparent QWidget gives this class
        # sole ownership of every splash pixel.
        super().__init__(None, splash_flags)

        original_pixmap = QPixmap(pixmap_path)
        if original_pixmap.width() > 500 or original_pixmap.height() > 500:
            original_pixmap = original_pixmap.scaled(
                500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        rounded = QPixmap(original_pixmap.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, original_pixmap.width(), original_pixmap.height(), 40, 40)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, original_pixmap)
        painter.end()
        self._logo_pixmap = rounded
        self.setFixedSize(rounded.size())

        self.setWindowFlags(splash_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setWindowOpacity(0.0)

        self.anim_in = QPropertyAnimation(self, b"windowOpacity", self)
        self.anim_in.setDuration(460)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(1.0)
        self.anim_in.setEasingCurve(QEasingCurve.InOutCubic)

        self._progress = 0.0
        self._progress_target = 0.0
        self._progress_started = False
        self._startup_error_message = ""
        self._progress_clock = QElapsedTimer()
        self._cinematic_clock = QElapsedTimer()
        self._last_progress_tick_ms = 0
        self._bar_completion_start = 0.0
        self._cinematic_mode = "loading"  # loading | prestage | completing-bar | vortex | plasma
        self._logo_rotation = 0.0
        self._logo_scale = 1.0
        self._plasma_scale = 0.0
        self._show_progress_bar = True
        self._cinematic_complete = False
        self._fade_in_waiting_for_first_paint = False
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value or 0.0)))

    @staticmethod
    def _ease_in_out(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - (2.0 * value))

    @staticmethod
    def _ease_out_cubic(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return 1.0 - pow(1.0 - value, 3.0)

    def set_readiness_progress(self, progress: float) -> None:
        """Accept only the controller's real startup state as loader progress."""
        if self._startup_error_message or self._cinematic_complete:
            return
        self._progress_target = max(self._progress_target, self._clamp01(progress))
        self.update()

    def begin_cinematic_reveal(self) -> None:
        """Begin native Acts I/II only after the hidden briefing has real data."""
        if self._startup_error_message or self._cinematic_complete:
            return
        if self._cinematic_mode not in {"loading", "completing-bar", "prestage"}:
            return
        if self._cinematic_mode == "prestage":
            return
        # The visible animation must not begin until the QML shell has staged
        # its centre pinpoint without activating its top-level host.  The
        # plasma implosion then releases the prepared bloom directly.
        self._cinematic_mode = "prestage"
        # Keep the native splash visibly above all other windows while it owns
        # the first two opening acts.
        self.raise_()
        self.activateWindow()
        self.cinematicBloomPrestageRequested.emit()

    def confirm_cinematic_bloom_prestaged(self) -> None:
        """Start the native choreography after QML stages its hidden pinpoint."""
        if self._startup_error_message or self._cinematic_complete:
            return
        if self._cinematic_mode != "prestage":
            return
        # The native splash remains focused above the 0.2% QML pinpoint until
        # the exact implosion endpoint; focus returns after the bloom begins.
        self.raise_()
        self.activateWindow()
        self._progress_target = 1.0
        self._bar_completion_start = self._progress
        self._cinematic_mode = "completing-bar"
        self._cinematic_clock.start()
        if not self.progress_timer.isActive():
            self.progress_timer.start(16)
        self.update()

    def _start_vortex(self) -> None:
        self._progress = 1.0
        self._show_progress_bar = False
        self._cinematic_mode = "vortex"
        self._cinematic_clock.restart()
        self.raise_()

    def _finish_cinematic_to_bloom(self) -> None:
        if self._cinematic_complete:
            return
        self._cinematic_complete = True
        self._show_progress_bar = False
        self._logo_scale = 0.0
        self._plasma_scale = 0.0
        self.progress_timer.stop()
        # Hide first, then release the already staged QML bloom in this same
        # turn.  The QML pre-stage intentionally did not request focus, so it
        # never raised a full application frame above this splash.
        self.hide()
        self.cinematicRevealReady.emit()

    def _update_progress(self) -> None:
        if not self._progress_started or self._startup_error_message:
            return
        if not self._progress_clock.isValid():
            return

        now_ms = self._progress_clock.elapsed()
        delta_ms = max(0, now_ms - self._last_progress_tick_ms)
        self._last_progress_tick_ms = now_ms

        if self._cinematic_mode == "loading":
            increment = self._PROGRESS_MAX_RATE_PER_SEC * (delta_ms / 1000.0)
            self._progress = min(self._progress_target, self._progress + increment)
        elif self._cinematic_mode == "completing-bar":
            ratio = self._clamp01(self._cinematic_clock.elapsed() / self._BAR_COMPLETION_MS)
            self._progress = self._bar_completion_start + (
                (1.0 - self._bar_completion_start) * self._ease_in_out(ratio)
            )
            if ratio >= 1.0:
                self._start_vortex()
        elif self._cinematic_mode in {"vortex", "plasma"}:
            elapsed = max(0, self._cinematic_clock.elapsed())
            if elapsed < self._ACT_I_VORTEX_MS:
                ratio = self._clamp01(elapsed / self._ACT_I_VORTEX_MS)
                self._logo_rotation = 1080.0 * ratio * ratio
                self._logo_scale = max(0.0, 1.0 - (ratio * ratio))
                self._plasma_scale = 0.0
            else:
                self._cinematic_mode = "plasma"
                phase_ms = elapsed - self._ACT_I_VORTEX_MS
                burst_end = self._ACT_II_BURST_MS
                hold_end = burst_end + self._ACT_II_HOLD_MS
                implode_end = hold_end + self._ACT_II_IMPLODE_MS
                self._logo_scale = 0.0
                if phase_ms < burst_end:
                    self._plasma_scale = 1.2 * self._ease_out_cubic(phase_ms / burst_end)
                elif phase_ms < hold_end:
                    self._plasma_scale = 1.2
                elif phase_ms < implode_end:
                    ratio = self._clamp01((phase_ms - hold_end) / self._ACT_II_IMPLODE_MS)
                    self._plasma_scale = 1.2 * (1.0 - pow(ratio, 3.0))
                else:
                    self._finish_cinematic_to_bloom()
                    return
        self.update()

    def _start_progress_after_visible_paint(self) -> None:
        if not self._progress_started or self._progress_clock.isValid():
            return
        self._progress_clock.start()
        self._last_progress_tick_ms = 0
        if not self.progress_timer.isActive():
            self.progress_timer.start(16)

    def _draw_logo(self, painter: QPainter, width: int, height: int) -> None:
        if self._logo_scale <= 0.001 or self._logo_pixmap.isNull():
            return
        painter.save()
        painter.translate(width / 2.0, height / 2.0)
        painter.rotate(self._logo_rotation)
        painter.scale(self._logo_scale, self._logo_scale)
        painter.drawPixmap(
            int(-self._logo_pixmap.width() / 2),
            int(-self._logo_pixmap.height() / 2),
            self._logo_pixmap,
        )
        painter.restore()

    def _draw_plasma(self, painter: QPainter, width: int, height: int) -> None:
        if self._plasma_scale <= 0.001:
            return
        cx, cy = width / 2.0, height / 2.0
        # A restrained burst leaves more negative space around the central
        # vortex and aligns better with the pinpoint handoff.
        radius = 76.0 * self._plasma_scale
        outer = QRadialGradient(cx, cy, radius * 1.35)
        outer.setColorAt(0.0, QColor(255, 250, 235, 220))
        outer.setColorAt(0.30, QColor(255, 250, 235, 186))
        outer.setColorAt(0.57, QColor(254, 215, 170, 105))
        outer.setColorAt(0.79, QColor(251, 146, 60, 42))
        outer.setColorAt(1.0, QColor(239, 68, 68, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(outer)
        painter.drawEllipse(QRectF(cx - radius * 1.35, cy - radius * 1.35, radius * 2.7, radius * 2.7))

        core = QRadialGradient(cx, cy, max(1.0, radius))
        core.setColorAt(0.0, QColor(255, 255, 255, 255))
        core.setColorAt(0.22, QColor(255, 255, 255, 250))
        core.setColorAt(0.52, QColor(255, 250, 235, 205))
        core.setColorAt(0.77, QColor(254, 215, 170, 100))
        core.setColorAt(1.0, QColor(251, 146, 60, 0))
        painter.setBrush(core)
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0))

        spark_radius = max(1.0, radius * 0.66)
        for index in range(16):
            angle = (index / 16.0) * 6.28318530718 + (self._cinematic_clock.elapsed() * 0.004)
            distance = spark_radius * (0.32 + (0.34 * ((index % 5) / 4.0)))
            sx = cx + math.cos(angle) * distance
            sy = cy + math.sin(angle) * distance
            painter.setBrush(QColor(255, 255 if index % 4 else 240, 255 if index % 4 else 138, 226))
            dot = max(1.0, 1.1 * self._plasma_scale)
            painter.drawEllipse(QRectF(sx - dot, sy - dot, dot * 2.0, dot * 2.0))

    def _draw_progress_bar(self, painter: QPainter, width: int, height: int) -> None:
        bar_width = min(width - 28.0, max(width * 0.84, 180.0))
        bar_height = 10.0
        x = (width - bar_width) / 2.0
        y = height - 46.0
        track = QRectF(x, y, bar_width, bar_height)
        radius = bar_height / 2.0
        painter.setPen(Qt.NoPen)
        for inset, color in ((8.0, QColor(34, 211, 238, 18)), (5.0, QColor(59, 130, 246, 28)), (2.0, QColor(99, 102, 241, 48))):
            glow_rect = track.adjusted(-inset, -inset / 2.0, inset, inset / 2.0)
            painter.setBrush(color)
            painter.drawRoundedRect(glow_rect, glow_rect.height() / 2.0, glow_rect.height() / 2.0)
        track_gradient = QLinearGradient(track.left(), track.top(), track.left(), track.bottom())
        track_gradient.setColorAt(0.0, QColor(18, 46, 74, 232))
        track_gradient.setColorAt(0.48, QColor(7, 22, 44, 238))
        track_gradient.setColorAt(1.0, QColor(3, 12, 29, 242))
        painter.setPen(QPen(QColor(174, 225, 255, 148), 1.0))
        painter.setBrush(track_gradient)
        painter.drawRoundedRect(track, radius, radius)
        inner = track.adjusted(1.25, 1.25, -1.25, -1.25)
        fill_width = inner.width() * self._clamp01(self._progress)
        if fill_width <= 0.25:
            return
        fill = QRectF(inner.left(), inner.top(), fill_width, inner.height())
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill, min(inner.height() / 2.0, fill.width() / 2.0), inner.height() / 2.0)
        plasma_gradient = QLinearGradient(inner.left(), inner.top(), inner.right(), inner.top())
        plasma_gradient.setColorAt(0.00, QColor(34, 211, 238))
        plasma_gradient.setColorAt(0.30, QColor(56, 189, 248))
        plasma_gradient.setColorAt(0.62, QColor(99, 102, 241))
        plasma_gradient.setColorAt(1.00, QColor(192, 132, 252))
        painter.setPen(Qt.NoPen)
        painter.fillPath(fill_path, plasma_gradient)
        painter.setPen(QPen(QColor(240, 253, 255, 175), 0.85))
        painter.drawLine(inner.left() + 1.0, inner.top() + 1.0, inner.left() + fill_width - 1.0, inner.top() + 1.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._draw_logo(painter, self.width(), self.height())
        self._draw_plasma(painter, self.width(), self.height())
        if self._show_progress_bar:
            self._draw_progress_bar(painter, self.width(), self.height())
        if self._startup_error_message:
            message_rect = QRectF(24.0, max(24.0, self.height() - 138.0), max(1.0, self.width() - 48.0), 68.0)
            painter.setPen(QColor(255, 235, 235, 238))
            painter.drawText(message_rect, Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextWordWrap,
                             "CSPM could not prepare the Practice Briefing.\n" + self._startup_error_message)
        painter.end()
        # The backing surface now holds an actual logo frame while opacity is
        # still zero. Starting the dissolve on the next event turn guarantees
        # that the first visible pixel is the CS logo, never an unpainted
        # native window.
        if self._fade_in_waiting_for_first_paint:
            self._fade_in_waiting_for_first_paint = False
            QTimer.singleShot(0, self._begin_fade_in_after_first_paint)

    def _begin_fade_in_after_first_paint(self) -> None:
        if self._cinematic_complete or self._startup_error_message or not self.isVisible():
            return
        self._start_progress_after_visible_paint()
        self.anim_in.start()

    def start_fade_in(self):
        if self._cinematic_complete:
            return
        self._progress = 0.0
        self._progress_target = 0.0
        self._progress_clock.invalidate()
        self._progress_started = True
        self.update()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self._fade_in_waiting_for_first_paint = True

    def show_first_frame(self) -> None:
        """Present a painted CS frame before synchronous startup work begins.

        The normal Qt event loop starts only after Python has finished loading
        the controller and QML engine.  Calling ``show()`` alone before that
        point leaves a newly-created transparent native surface unpainted,
        which Windows can display as a black square.  Prime that surface at
        zero opacity, then reveal its completed CS/logo/progress frame
        immediately instead of waiting for the main event loop.
        """
        if self._cinematic_complete:
            return
        self._progress = 0.0
        self._progress_target = 0.0
        self._progress_clock.invalidate()
        self._progress_started = True
        self._fade_in_waiting_for_first_paint = False
        self.anim_in.stop()
        self.setWindowOpacity(0.0)
        self.show()
        # ``repaint`` guarantees the backing image exists; processing the
        # expose/paint events while still fully transparent prevents a native
        # default (black) client rectangle from reaching the desktop.
        self.repaint()
        app = QApplication.instance()
        if app is not None:
            app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        self.setWindowOpacity(1.0)
        self._start_progress_after_visible_paint()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self.repaint()
        if app is not None:
            app.processEvents(QtCore.QEventLoop.AllEvents, 50)

    def start_fade_out(self):
        """Compatibility fallback for legacy callers; never overlap the main UI."""
        self._finish_cinematic_to_bloom()

    def show_startup_error(self, message: str) -> None:
        self._startup_error_message = str(message or "Please close CSPM and try again.").strip()
        self._progress_started = False
        self.progress_timer.stop()
        self.anim_in.stop()
        self.setWindowOpacity(1.0)
        self.raise_()
        self.update()

    def _request_skip(self) -> None:
        # Mouse/key input commonly arrives while the user is launching CSPM.
        # It must not be remembered and then erase the visible CS spin/shrink
        # and plasma burst once readiness completes.  Only a deliberate input
        # during a currently visible cinematic act may skip its remainder.
        if self._cinematic_mode not in {"completing-bar", "vortex", "plasma"}:
            return
        self._finish_cinematic_to_bloom()

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape}:
            self._request_skip()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        self._request_skip()
        event.accept()

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

from backend.native_svg import NativeSvgItem

APP_MAINTAINER = "Tim"
APP_TITLE = "Practice Console"
APP_USER_MODEL_ID = "CSPM.PracticeConsole"

from services.paths import AppPaths
PROJECT_ROOT = AppPaths.project_root()
APP_ICON_PATH = PROJECT_ROOT / "src" / "assets" / "app_icon.ico"
SPLASH_LOGO_CLEAN_PATH = PROJECT_ROOT / "assets" / "CS.svg"
SPLASH_LOGO_STATIC_PATH = PROJECT_ROOT / "assets" / "splash_logo.png"






# CSPM_AP_ADAPTIVE_COMPOSITION_V2
def _cspm_find_ap_expense_gateway(root_object):
    """Find the existing expense gateway without assuming its attribute name."""
    queue = [(root_object, 'app', 0)]
    seen = set()
    preferred = ('repo','_repo','repository','_repository','excel_repo','_excel_repo','workbook_repo','data_repo','backend','controller','_controller','billing','finance','transactions','services','app_controller')
    while queue:
        current, path, depth = queue.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if callable(getattr(current, 'save_ap_expense', None)):
            return current, path
        if depth >= 3:
            continue
        for name in preferred:
            try:
                child = getattr(current, name, None)
            except Exception:
                child = None
            if child is not None and id(child) not in seen:
                queue.append((child, path + '.' + name, depth + 1))
        try:
            attributes = vars(current)
        except Exception:
            attributes = {}
        for name, child in attributes.items():
            low = str(name).lower()
            if any(token in low for token in ('repo','excel','workbook','backend','billing','finance','transaction')) and child is not None and id(child) not in seen:
                queue.append((child, path + '.' + str(name), depth + 1))
    return None, ''
def _read_np_step_yaml():
    """Return tuple(current_step_id, last_completed_step_id) or (None,None).
    """
    try:
        import yaml
        path = PROJECT_ROOT / "docs" / "spec" / "no_placeholder_21_step_execution.yaml"
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return data.get("current_step_id"), data.get("last_completed_step_id")
    except Exception:
        return None, None


def _print_np_status_and_exit():
    cur, last = _read_np_step_yaml()
    if cur is None:
        print("Unable to read NP step YAML")
        sys.exit(1)
    print(f"current_step_id: {cur}")
    print(f"last_completed_step_id: {last}")
    sys.exit(0)
SPLASH_LOGO_ANIMATED_PATH = PROJECT_ROOT / "assets" / "splash_logo.svg"
SPLASH_AUDIO_PATHS = [
    PROJECT_ROOT / "assets" / "splash_sound.wav",
    PROJECT_ROOT / "assets" / "splash_sound.mp3",
]
_SINGLE_INSTANCE_MUTEX_NAME = "Local\\CSPM.PracticeConsole.MainInstance"
_single_instance_mutex_handle = None


def _is_chromium_helper_process(argv = None) -> bool:
    args = sys.argv[1:] if argv is None else argv
    return any(str(arg).startswith("--type=") for arg in args)


def _release_single_instance_lock() -> None:
    global _single_instance_mutex_handle
    handle = _single_instance_mutex_handle
    if not handle or not sys.platform.startswith("win"):
        _single_instance_mutex_handle = None
        return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.ReleaseMutex(ctypes.c_void_p(handle))
        kernel32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        pass
    _single_instance_mutex_handle = None


def _acquire_single_instance_lock() -> bool:
    """Return False when another CSPM GUI process already owns the app mutex."""
    global _single_instance_mutex_handle
    if not sys.platform.startswith("win"):
        return True
    if _single_instance_mutex_handle:
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.GetLastError.restype = ctypes.c_ulong
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]

        handle = kernel32.CreateMutexW(None, True, _SINGLE_INSTANCE_MUTEX_NAME)
        if not handle:
            return True
        last_error = int(kernel32.GetLastError())
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        _single_instance_mutex_handle = int(handle)
        atexit.register(_release_single_instance_lock)
        return True
    except Exception as exc:
        logging.getLogger("startup").warning(
            "Unable to create single-instance mutex; continuing without it: %s",
            exc,
        )
        return True


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


# Toggle verbose terminal diagnostics (QML console logs + Python debug prints).
VERBOSE_TERMINAL_LOGGING = _env_flag("CSPM_VERBOSE_LOGGING", False)
# Toggle startup splash timeline summary lines in terminal.
# Kept separate from full verbose logging so timeline diagnostics remain visible by default.
SPLASH_TIMELINE_LOGGING = _env_flag("CSPM_SPLASH_TIMELINE_LOGGING", False)
# Toggle orange/green debug frames in QML.
DEBUG_FRAMES_ENABLED = _env_flag("CSPM_DEBUG_FRAMES", False)


def _vlog(message: str) -> None:
    if VERBOSE_TERMINAL_LOGGING:
        print(message)


def _timeline_log(message: str) -> None:
    if SPLASH_TIMELINE_LOGGING:
        print(message)


def _boot_log(message: str) -> None:
    """Log a boot-time message to the startup logger."""
    t0_boot = time.perf_counter() - t0
    startup_logger.info(f'[{t0_boot:.3f}s] {message}')


_QT_NOISY_PREFIXES = (
    "qml: [ROUND]",
    "qml: [MASK]",
    "qml: [SPLASH]",
    "qml: [CLOSING]",
    "qml: [JELLY]",
    "qml: [FALL MONITOR]",
    "qml: [CLOSING MONITOR]",
    "qml: [DRAG]",
    "qml: [SETTLED]",
    "qml: [MAIN]",
    "qml: [PHASE]",
)
_QT_SUPPRESSED_SUBSTRINGS = (
    # FFmpeg/QtMultimedia startup probe chatter from splash audio.
    "Input #0, wav, from",
    "Stream #0:0: Audio:",
    "Retrying to obtain clipboard.",
    # Qt internal warning during multi-monitor/high-DPI expose; not an app failure.
    "cached device pixel ratio value was stale on window expose",
)
_QT_SUPPRESSED_WARNING_SNIPPETS = (
    # Frequent Qt warning when requestActivate() is called on non-focusable tool windows.
    "requestActivate() called for",
    "Qt::WindowDoesNotAcceptFocus set",
)
_qt_message_filter_installed = False
_previous_qt_message_handler = None
_splash_gone_perf: Optional[float] = None
_splash_first_pixel_perf: Optional[float] = None
_startup_first_input_perf: Optional[float] = None
_startup_first_input_label: str = ""
_splash_lag_events: List[Tuple[float, str]] = []
_startup_input_notify_callback: Optional[Any] = None
_SPLASH_TO_FIRST_PIXEL_BUDGET_S = 0.700


def _qt_message_handler(mode: QtMsgType, context: Any, message: str) -> None:
    global _splash_gone_perf, _splash_first_pixel_perf, _startup_first_input_perf, _splash_lag_events
    text = str(message)

    if (
        mode == QtMsgType.QtWarningMsg
        and _QT_SUPPRESSED_WARNING_SNIPPETS[0] in text
        and _QT_SUPPRESSED_WARNING_SNIPPETS[1] in text
    ):
        return

    # Route QML tray diagnostics to the file logger
    if mode == QtMsgType.QtWarningMsg and "[TRAY" in text:
        logging.getLogger("QML").warning(text)
        return
    if mode == QtMsgType.QtWarningMsg and "[SPLASH-LAG]" in text:
        try:
            now_perf = time.perf_counter()
            elapsed_s = max(0.0, now_perf - t0)
            detail = text.split("[SPLASH-LAG]", 1)[1].strip()
            logging.getLogger("startup").info("splash-lag-step [%.3fs]: %s", elapsed_s, detail)
            _splash_lag_events.append((now_perf, detail))
            if len(_splash_lag_events) > 240:
                _splash_lag_events = _splash_lag_events[-240:]
        except Exception:
            pass
        return

    if mode == QtMsgType.QtWarningMsg and "[STARTUP-PHASE]" in text:
        try:
            now_perf = time.perf_counter()
            elapsed_s = max(0.0, now_perf - t0)
            detail = text.split("[STARTUP-PHASE]", 1)[1].strip()
            logging.getLogger("startup").info("startup-phase [%.3fs]: %s", elapsed_s, detail)
        except Exception:
            pass
        return

    if mode == QtMsgType.QtWarningMsg and "[STARTUP-FIRST-INPUT-READY]" in text:
        try:
            now_perf = time.perf_counter()
            elapsed_s = max(0.0, now_perf - t0)
            detail = text.split("[STARTUP-FIRST-INPUT-READY]", 1)[1].strip()
            logging.getLogger("startup").info("startup-input-ready [%.3fs]: %s", elapsed_s, detail)
        except Exception:
            pass
        return

    if mode == QtMsgType.QtWarningMsg and "[STARTUP-FIRST-INPUT]" in text:
        try:
            now_perf = time.perf_counter()
            elapsed_s = max(0.0, now_perf - t0)
            detail = text.split("[STARTUP-FIRST-INPUT]", 1)[1].strip()
            logging.getLogger("startup").info("startup-first-input-marker [%.3fs]: %s", elapsed_s, detail)
            if _splash_first_pixel_perf is not None:
                logging.getLogger("startup").info(
                    "first-pixel->first-input-marker latency: [%.3fs]",
                    max(0.0, now_perf - _splash_first_pixel_perf),
                )
        except Exception:
            pass
        return

    # Promote splash lifecycle markers to structured INFO logs.
    if mode == QtMsgType.QtWarningMsg and "[SPLASH-GONE]" in text:
        _splash_gone_perf = None
        _splash_first_pixel_perf = None
        _startup_first_input_perf = None
        elapsed_s = None
        try:
            now_perf = time.perf_counter()
            _splash_gone_perf = now_perf
            elapsed_s = max(0.0, now_perf - t0)
        except Exception:
            pass
        if elapsed_s is None:
            ms_match = re.search(r"t\+(\d+)ms", text)
            if ms_match:
                elapsed_s = int(ms_match.group(1)) / 1000.0
        if elapsed_s is not None:
            logging.getLogger("startup").info("splash completely gone: [%.3fs]", elapsed_s)
        else:
            logging.getLogger("startup").info("splash completely gone: [n/a]")
        return

    if mode == QtMsgType.QtWarningMsg and "[SPLASH-FIRST-PIXEL]" in text:
        elapsed_s = None
        now_perf = None
        try:
            now_perf = time.perf_counter()
            _splash_first_pixel_perf = now_perf
            elapsed_s = max(0.0, now_perf - t0)
        except Exception:
            pass
        if elapsed_s is None:
            ms_match = re.search(r"t\+(\d+)ms", text)
            if ms_match:
                elapsed_s = int(ms_match.group(1)) / 1000.0
        if elapsed_s is not None:
            logging.getLogger("startup").info("Falling window first pixel: [%.3fs]", elapsed_s)
        else:
            logging.getLogger("startup").info("Falling window first pixel: [n/a]")
        if _splash_gone_perf is not None and now_perf is not None:
            try:
                lag_s = max(0.0, now_perf - _splash_gone_perf)
                logging.getLogger("startup").info("splash->first-pixel lag window: [%.3fs]", lag_s)
                if lag_s > _SPLASH_TO_FIRST_PIXEL_BUDGET_S:
                    logging.getLogger("startup").warning(
                        "Startup budget exceeded: splash->first-pixel %.3fs (target %.3fs)",
                        lag_s,
                        _SPLASH_TO_FIRST_PIXEL_BUDGET_S,
                    )
                lag_steps = [
                    (ts, step) for (ts, step) in _splash_lag_events
                    if ts >= _splash_gone_perf and ts <= (now_perf + 0.25)
                ]
                if lag_steps:
                    logging.getLogger("startup").info("splash-lag-step-count: %d", len(lag_steps))
                    for ts, step in lag_steps:
                        rel = max(0.0, ts - _splash_gone_perf)
                        logging.getLogger("startup").info("  +%.3fs %s", rel, step)
                else:
                    logging.getLogger("startup").info("splash-lag-step-count: 0 (no instrumented steps captured)")
            except Exception:
                pass
        return

    # Suppress high-volume debug/info chatter unless explicitly enabled.
    if mode in (QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg):
        if VERBOSE_TERMINAL_LOGGING:
            sys.stderr.write(text + os.linesep)
        return

    if (not VERBOSE_TERMINAL_LOGGING) and (text.startswith("Metadata:") or text.startswith("Duration:")):
        return
    if (not VERBOSE_TERMINAL_LOGGING) and any(fragment in text for fragment in _QT_SUPPRESSED_SUBSTRINGS):
        return
    if (not VERBOSE_TERMINAL_LOGGING) and text.startswith(_QT_NOISY_PREFIXES):
        return

    if callable(_previous_qt_message_handler):
        try:
            _previous_qt_message_handler(mode, context, message)
            return
        except Exception:
            pass
    sys.stderr.write(text + os.linesep)


def _install_qt_message_filter() -> None:
    global _qt_message_filter_installed, _previous_qt_message_handler
    if _qt_message_filter_installed:
        return
    _previous_qt_message_handler = qInstallMessageHandler(_qt_message_handler)
    _qt_message_filter_installed = True


class _StartupInputProbe(QObject):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._captured = False

    def eventFilter(self, watched: QObject, event: Any) -> bool:
        del watched
        global _startup_first_input_perf, _startup_first_input_label
        if event is None:
            return False

        try:
            event_type = int(event.type())
        except Exception:
            return False

        label = ""
        if event_type == int(QEvent.Type.MouseButtonPress):
            label = "mouse-press"
        elif event_type == int(QEvent.Type.MouseButtonDblClick):
            label = "mouse-double-click"
        elif event_type == int(QEvent.Type.KeyPress):
            label = "key-press"
        elif event_type == int(QEvent.Type.TouchBegin):
            label = "touch-begin"
        elif event_type == int(QEvent.Type.Wheel):
            label = "wheel"
        else:
            return False

        if not self._captured:
            self._captured = True
            now_perf = None
            elapsed_s = None
            try:
                now_perf = time.perf_counter()
                _startup_first_input_perf = now_perf
                _startup_first_input_label = label
                elapsed_s = max(0.0, now_perf - t0)
            except Exception:
                pass

            startup_log = logging.getLogger("startup")
            if elapsed_s is not None:
                startup_log.info("startup first input: [%.3fs] type=%s", elapsed_s, label)
            else:
                startup_log.info("startup first input: [n/a] type=%s", label)

            if _splash_first_pixel_perf is not None and now_perf is not None:
                startup_log.info(
                    "first-pixel->first-input latency: [%.3fs]",
                    max(0.0, now_perf - _splash_first_pixel_perf),
                )
            elif _splash_gone_perf is not None and now_perf is not None:
                startup_log.info(
                    "splash-gone->first-input latency: [%.3fs]",
                    max(0.0, now_perf - _splash_gone_perf),
                )
            else:
                startup_log.info("first-pixel->first-input latency: [n/a]")
        try:
            callback = _startup_input_notify_callback
            if callable(callback):
                callback(label)
        except Exception as exc:
            _report_nonfatal_startup_failure("startup.inputProbe.notify", exc)
        return False



_APP_ICON_SYNC_EVENT_TYPES = {
    QEvent.Type.PlatformSurface,
    QEvent.Type.Show,
    QEvent.Type.WindowActivate,
}


def _load_app_icon() -> QIcon:
    if not APP_ICON_PATH.exists():
        startup_logger.warning("CSPM app icon not found: %s", APP_ICON_PATH)
        return QIcon()
    icon = QIcon(str(APP_ICON_PATH))
    if icon.isNull():
        startup_logger.warning("CSPM app icon could not be loaded: %s", APP_ICON_PATH)
    return icon


def _apply_app_icon_to_window(window: Any, icon: QIcon) -> bool:
    if window is None or icon.isNull():
        return False
    try:
        if window.metaObject().className() == "QMessageBox":
            return False
        
        if hasattr(window, "setWindowIcon"):
            window.setWindowIcon(icon)
            return True
            
        set_icon = getattr(window, "setIcon", None)
        if callable(set_icon):
            set_icon(icon)
            return True
    except RuntimeError:
        return False
    except Exception as exc:
        _report_nonfatal_startup_failure("icon.applyWindow", exc)
    return False


class _AppIconSync(QObject):
    """Keep the saved CSPM icon on QML windows that are created after app init."""

    def __init__(self, app: QApplication, icon: QIcon) -> None:
        super().__init__(app)
        self._app = app
        self._icon = icon
        self._pending_apply = False

    def apply_all(self) -> None:
        self._pending_apply = False
        if self._icon.isNull():
            return
        try:
            self._app.setWindowIcon(self._icon)
        except Exception as exc:
            _report_nonfatal_startup_failure("icon.applyApp", exc)
        try:
            windows = list(self._app.topLevelWindows())
        except RuntimeError:
            windows = []
        except Exception as exc:
            _report_nonfatal_startup_failure("icon.enumerateWindows", exc)
            windows = []
        for win in windows:
            _apply_app_icon_to_window(win, self._icon)

    def queue_apply_all(self) -> None:
        if self._pending_apply:
            return
        self._pending_apply = True
        QTimer.singleShot(0, self.apply_all)

    def eventFilter(self, watched: QObject, event: Any) -> bool:
        try:
            if event is not None and event.type() in _APP_ICON_SYNC_EVENT_TYPES:
                _apply_app_icon_to_window(watched, self._icon)
                self.queue_apply_all()
        except RuntimeError:
            pass
        except Exception as exc:
            _report_nonfatal_startup_failure("icon.eventFilter", exc)
        return False


def _install_app_icon_sync(app: QApplication) -> None:
    icon = _load_app_icon()
    if icon.isNull():
        return
    icon_sync = _AppIconSync(app, icon)
    app.installEventFilter(icon_sync)
    try:
        app.focusWindowChanged.connect(lambda _window=None: icon_sync.queue_apply_all())
    except Exception as exc:
        _report_nonfatal_startup_failure("icon.focusWindowChanged.connect", exc)
    app._cspm_app_icon = icon  # type: ignore[attr-defined]
    app._cspm_app_icon_sync = icon_sync  # type: ignore[attr-defined]
    icon_sync.apply_all()
    for delay_ms in (0, 120, 500, 1500, 3500):
        QTimer.singleShot(delay_ms, icon_sync.apply_all)


def _capture_startup_launch_context() -> dict:
    result = {
        "cursorX": 0,
        "cursorY": 0,
        "screenIndex": 0,
    }
    try:
        cursor_pos = QCursor.pos()
        result["cursorX"] = int(cursor_pos.x())
        result["cursorY"] = int(cursor_pos.y())
        screens = list(QApplication.screens() or [])
        if not screens:
            return result

        cursor_screen = QApplication.screenAt(cursor_pos)
        if cursor_screen is None:
            for screen in screens:
                try:
                    if screen.geometry().contains(cursor_pos):
                        cursor_screen = screen
                        break
                except Exception:
                    continue
        if cursor_screen is None:
            cursor_screen = screens[0]

        for index, screen in enumerate(screens):
            if screen is cursor_screen:
                result["screenIndex"] = int(index)
                break
            try:
                if (
                    screen.name() == cursor_screen.name()
                    and screen.geometry() == cursor_screen.geometry()
                ):
                    result["screenIndex"] = int(index)
                    break
            except Exception:
                continue
    except Exception as exc:
        _report_nonfatal_startup_failure("startup.captureLaunchContext", exc)
    return result


# ---------------------------------------------------------------------------
# Platform-specific hooks — imported from the platform/ package.
# The classes below are only used on Windows; they are lazily imported
# inside _install_runtime_native_features() and on_about_to_quit() to
# avoid importing win32 ctypes on non-Windows platforms.
# ---------------------------------------------------------------------------


def _maybe_enable_software_renderer() -> None:
    """Optional: set CSPM_SOFTWARE_RENDER=1 to force Qt Quick software backend."""
    if not sys.platform.startswith("win"):
        return
    if os.environ.get("CSPM_SOFTWARE_RENDER", "").strip() != "1":
        return
    os.environ.setdefault("QT_QUICK_BACKEND", "software")


def _ensure_non_native_controls_style() -> None:
    """Use a non-native Controls style so custom control delegates are respected."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")


def _initialize_qt_webengine() -> None:
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick

        QtWebEngineQuick.initialize()
    except Exception as exc:
        _vlog(f"[SPLASH] QtWebEngine init unavailable: {exc}")


def _initialize_qt_webview() -> None:
    try:
        from PySide6.QtWebView import QtWebView

        QtWebView.initialize()
    except Exception as exc:
        _vlog(f"[SPLASH] QtWebView init unavailable: {exc}")


def _configure_qt_webengine_runtime() -> None:
    """Apply minimal runtime settings for WebEngine-backed splash rendering."""
    # NOTE FOR AUTOMATION/AI AGENTS:
    # In sandboxed shells, Qt WebEngine runtime may fail with
    # "channel-pipe ... Access is denied (0x5)" before app logic runs.
    # Treat that as environment restriction. Validate WebEngine splash/e2e
    # startup outside sandbox (or with elevated permission) and keep
    # sandbox runs for static/safe checks only.
    if not sys.platform.startswith("win"):
        return
    force_webengine = _env_flag("CSPM_SPLASH_FORCE_WEBENGINE", True)
    webengine_disabled = os.environ.get("CSPM_SPLASH_WEBENGINE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }
    if webengine_disabled and not force_webengine:
        return

    # Keep sandbox disabled (required on some Windows setups for local splash assets).
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    # Remove legacy splash flags that caused delayed/blank WebEngine render.
    # Keep a targeted compatibility feature-disable for DirectComposition to
    # avoid unsupported IDCompositionDevice4 paths on some Windows/GPU stacks.
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    blocked_exact = {
        "--single-process",
        "--no-zygote",
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--use-angle=swiftshader",
    }
    blocked_features = {"RendererCodeIntegrity", "VizDisplayCompositor"}
    required_disable_features = {"DirectComposition"}
    required_exact_flags = {
        "--disable-direct-composition",
        "--disable-logging",
        "--log-level=3",
    }
    saw_disable_features = False
    cleaned_parts: list[str] = []
    preserved_disable_features: list[str] = []
    for raw_part in existing_flags.split():
        part = raw_part.strip()
        if not part:
            continue
        if part in blocked_exact:
            continue
        if part.startswith("--disable-features="):
            saw_disable_features = True
            raw_features = part.split("=", 1)[1]
            kept_features = []
            for item in raw_features.split(","):
                feature_name = item.strip()
                if not feature_name:
                    continue
                if feature_name in blocked_features:
                    continue
                if feature_name not in kept_features:
                    kept_features.append(feature_name)
            preserved_disable_features = kept_features
            continue
        cleaned_parts.append(part)

    merged_disable_features = preserved_disable_features[:]
    for feature_name in sorted(required_disable_features):
        if feature_name not in merged_disable_features:
            merged_disable_features.append(feature_name)
    if merged_disable_features:
        cleaned_parts.append("--disable-features=" + ",".join(merged_disable_features))
    elif saw_disable_features:
        # If all features were stripped, omit empty disable-features entry.
        pass

    for required_flag in sorted(required_exact_flags):
        if required_flag not in cleaned_parts:
            cleaned_parts.append(required_flag)

    if cleaned_parts:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(cleaned_parts)
    else:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--disable-features=DirectComposition "
            "--disable-direct-composition --disable-logging --log-level=3"
        )


def _configure_qt_logging_rules() -> None:
    desired_rules = [
        "qt.multimedia.ffmpeg=false",
        "qt.svg=false",
        "qt.svg.draw=false",
    ]
    existing_raw = os.environ.get("QT_LOGGING_RULES", "").strip()
    entries = [part.strip() for part in existing_raw.split(";") if part.strip()]
    keys = set()
    for entry in entries:
        if "=" in entry:
            keys.add(entry.split("=", 1)[0].strip())
    for rule in desired_rules:
        key = rule.split("=", 1)[0].strip()
        if key not in keys:
            entries.append(rule)
            keys.add(key)
    if entries:
        os.environ["QT_LOGGING_RULES"] = ";".join(entries)


def _configure_qt_multimedia_runtime() -> None:
    # Keep splash audio playback quiet unless verbose diagnostics are explicitly enabled.
    os.environ.setdefault("QT_FFMPEG_DEBUG", "0")
    os.environ.setdefault("QT_FFMPEG_LOGLEVEL", "quiet")


def _existing_file_url(path: Path, label: str) -> str:
    try:
        if path.exists():
            return QUrl.fromLocalFile(str(path)).toString()
        _vlog(f"[SPLASH] Missing {label}: {path}")
    except Exception as exc:
        _vlog(f"[SPLASH] Failed to prepare {label}: {exc}")
    return ""


def _first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _first_existing_file_url(paths: list[Path], label: str) -> str:
    for path in paths:
        url = _existing_file_url(path, label)
        if url:
            return url
    return ""


def _probe_audio_duration_ms(paths: list[Path]) -> int:
    """Best-effort audio duration probe used for splash timeline diagnostics."""
    audio_path = _first_existing_path(paths)
    if audio_path is None:
        return 0
    try:
        if audio_path.suffix.lower() == ".wav":
            with wave.open(str(audio_path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                if frame_rate > 0 and frame_count > 0:
                    return int(round((frame_count / float(frame_rate)) * 1000.0))
    except Exception:
        return 0
    return 0


def _splash_logo_paths() -> list[Path]:
    """Use animated splash logo by default; allow env override for clean/static variant."""
    variant = os.environ.get("CSPM_SPLASH_LOGO_VARIANT", "animated").strip().lower()
    if variant in ("clean", "static"):
        return [SPLASH_LOGO_CLEAN_PATH, SPLASH_LOGO_ANIMATED_PATH, SPLASH_LOGO_STATIC_PATH]
    return [SPLASH_LOGO_ANIMATED_PATH, SPLASH_LOGO_CLEAN_PATH, SPLASH_LOGO_STATIC_PATH]


def _env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except Exception:
        return default
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except Exception:
        return default
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def _call_if_present(obj: Any, method: str, *args: Any) -> bool:
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args)
            return True
        except Exception:
            return False
    return False


def _request_window_teardown(win: Any) -> None:
    """Best-effort close + native teardown for helper windows that are hidden but still alive."""
    _call_if_present(win, "close")
    _call_if_present(win, "hide")
    _call_if_present(win, "destroy")
    _call_if_present(win, "deleteLater")


def _drain_all_windows(max_passes: int = 8) -> int:
    """Try to reduce QApplication.allWindows() to zero during shutdown."""
    remaining = 0
    for pass_idx in range(max_passes):
        try:
            windows = list(QApplication.allWindows())
        except Exception:
            windows = []
        remaining = len(windows)
        for win in windows:
            _request_window_teardown(win)
        try:
            QCoreApplication.processEvents()
            QCoreApplication.sendPostedEvents(None, 0)
        except Exception:
            pass
        if remaining == 0:
            break
    try:
        remaining = len(list(QApplication.allWindows()))
    except Exception:
        remaining = -1
    return remaining


def main() -> None:
    if _is_chromium_helper_process():
        startup_logger.warning(
            "QtWebEngine helper-style argv detected before GUI startup; skipping CSPM QML initialization: %s",
            sys.argv[1:],
        )
        return
    if not _acquire_single_instance_lock():
        startup_logger.warning("Duplicate CSPM GUI launch blocked by single-instance mutex. Sending WAKEUP signal.")
        # Connect to existing instance
        socket = QLocalSocket()
        socket.connectToServer("CSPM_IPC_SERVER")
        if socket.waitForConnected(1000):
            socket.write(b"WAKEUP")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        return

    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass

    _maybe_enable_software_renderer()
    _ensure_non_native_controls_style()
    _configure_qt_logging_rules()
    _configure_qt_multimedia_runtime()
    _install_qt_message_filter()
    splash_force_webengine = _env_flag("CSPM_SPLASH_FORCE_WEBENGINE", True)
    # The startup experience is a native PNG splash, not a WebEngine/QML
    # overlay. Avoid adding renderer startup work before the main window unless
    # a diagnostic environment explicitly asks for it.
    splash_preinit_webengine = _env_flag("CSPM_PREINIT_WEBENGINE", False)
    splash_preinit_webview = _env_flag("CSPM_PREINIT_WEBVIEW", False)
    _configure_qt_webengine_runtime()

    if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    parser = argparse.ArgumentParser(description="CSPM Application")
    parser.add_argument("--tray-only", action="store_true", help="Start the application minimized in the system tray")
    # We parse known args so Qt can still parse its own args if any
    args, _ = parser.parse_known_args()
    is_tray_only = args.tray_only
    
    app = QApplication(sys.argv)

    _boot_log("QApplication.created")
    startup_launch_context = _capture_startup_launch_context()
    _boot_log(
        "Startup launch screen captured index="
        + str(startup_launch_context.get("screenIndex", 0))
        + " cursor=("
        + str(startup_launch_context.get("cursorX", 0))
        + ","
        + str(startup_launch_context.get("cursorY", 0))
        + ")"
    )

    custom_splash: Optional[CustomSplash] = None
    if not is_tray_only:
        splash_png_path = str(PROJECT_ROOT / "src" / "assets" / "app_icon_preview.png")
        custom_splash = CustomSplash(splash_png_path)
        try:
            screens = list(QApplication.screens() or [])
            screen_index = int(startup_launch_context.get("screenIndex", 0))
            if screens:
                screen_index = max(0, min(screen_index, len(screens) - 1))
                target_geometry = screens[screen_index].geometry()
                custom_splash.move(
                    target_geometry.x() + max(0, (target_geometry.width() - custom_splash.width()) // 2),
                    target_geometry.y() + max(0, (target_geometry.height() - custom_splash.height()) // 2),
                )
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.positionTargetScreen", exc)
        # The process continues with synchronous engine/controller setup next.
        # Prime and reveal a completed native CS frame now, so Windows never
        # shows an unpainted black splash rectangle during that work.
        custom_splash.show_first_frame()
        _boot_log("Native CS splash first frame primed")

    # Expose to QML Engine

    # Keep app alive during splash -> main shell handoff. Re-enabled once main window exists.
    app.setQuitOnLastWindowClosed(False)
    # Optional pre-initialization can reduce first-use renderer spikes but may
    # increase time-to-first-frame. Keep disabled by default.
    if splash_preinit_webengine:
        _initialize_qt_webengine()
    if splash_preinit_webview:
        _initialize_qt_webview()
    try:
        startup_input_probe = _StartupInputProbe(app)
        app.installEventFilter(startup_input_probe)
        app._startup_input_probe = startup_input_probe  # type: ignore[attr-defined]
    except Exception as exc:
        _report_nonfatal_startup_failure("startup.installInputProbe", exc)

    _install_app_icon_sync(app)

    app.setOrganizationName(APP_MAINTAINER)
    app.setApplicationName(APP_TITLE)

    engine = QQmlApplicationEngine()
    _boot_log("QQmlApplicationEngine.created")

    native_splash_signal_bound = False
    native_splash_main_window = None
    native_splash_bootstrap_root = None

    def _restore_main_foreground_after_native_splash() -> None:
        """Politely request activation after the native splash has closed.

        Startup must not claim the foreground with Win32 calls: CSPM should
        open focused, but it must remain an ordinary peer of the user's other
        applications immediately afterwards.
        """
        main_window = native_splash_main_window
        if main_window is None:
            return
        try:
            force_launch_focus = getattr(main_window, "forceLaunchFocusLight", None)
            if callable(force_launch_focus):
                force_launch_focus()
                return
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.restoreQmlFocus", exc)

        # This fallback deliberately uses only Qt's regular activation request.
        # It must never alter the topmost state or take Windows focus directly.
        try:
            show_fn = getattr(main_window, "show", None)
            if callable(show_fn):
                show_fn()
            raise_fn = getattr(main_window, "raise_", None)
            if callable(raise_fn):
                raise_fn()
            activate_fn = getattr(main_window, "requestActivate", None)
            if callable(activate_fn):
                activate_fn()
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.restoreNativeFocus", exc)

    def _bind_native_splash_to_main_window(main_window) -> None:
        nonlocal native_splash_main_window
        if main_window is None:
            return
        native_splash_main_window = main_window

    def _prestage_cinematic_bloom() -> None:
        """Ask QML to stage Act III's pinpoint without taking native focus."""
        root_obj = native_splash_bootstrap_root
        if root_obj is None:
            _report_nonfatal_startup_failure(
                "nativeSplash.prestageCinematicBloom",
                RuntimeError("Bootstrap root was not available for cinematic prestage."),
            )
            return
        try:
            prestage_bloom = getattr(root_obj, "prestageCinematicBloom", None)
            if callable(prestage_bloom):
                prestage_bloom()
            else:
                raise RuntimeError("BootstrapRoot.prestageCinematicBloom is unavailable.")
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.prestageCinematicBloom", exc)

    def _release_cinematic_launch_gate() -> None:
        """Release QML's staged bloom after the native plasma reaches zero."""
        root_obj = native_splash_bootstrap_root
        if root_obj is None:
            _report_nonfatal_startup_failure(
                "nativeSplash.releaseCinematicGate",
                RuntimeError("Bootstrap root was not available at cinematic handoff."),
            )
            return
        try:
            release_gate = getattr(root_obj, "releaseCinematicLaunchGate", None)
            if callable(release_gate):
                release_gate()
            else:
                raise RuntimeError("BootstrapRoot.releaseCinematicLaunchGate is unavailable.")
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.releaseCinematicGate", exc)
            return
        # The shell receives one normal Qt activation request after the bloom
        # is dispatched.  It never uses topmost or Win32 foreground forcing.
        QTimer.singleShot(460, _restore_main_foreground_after_native_splash)

    if custom_splash is not None:
        custom_splash.cinematicBloomPrestageRequested.connect(_prestage_cinematic_bloom)
        custom_splash.cinematicRevealReady.connect(_release_cinematic_launch_gate)

    def on_object_created(obj, obj_url):
        nonlocal native_splash_signal_bound, native_splash_bootstrap_root
        if obj is None or native_splash_signal_bound:
            return
        # BootstrapRoot owns the hidden, data-backed QML shell.  It asks the
        # native splash to start Acts I/II only once the hidden frame says it
        # is ready; the native splash calls back to open Act III at its exact
        # implosion endpoint.
        try:
            obj.setProperty("nativeStartupCinematicActive", custom_splash is not None)
            main_window_ready = getattr(obj, "mainWindowReady", None)
            if main_window_ready is None:
                return
            main_window_ready.connect(_bind_native_splash_to_main_window)
            native_splash_bootstrap_root = obj
            if custom_splash is not None:
                cinematic_reveal = getattr(obj, "cinematicRevealRequested", None)
                if cinematic_reveal is None:
                    raise RuntimeError("BootstrapRoot.cinematicRevealRequested is unavailable.")
                cinematic_reveal.connect(custom_splash.begin_cinematic_reveal)
                cinematic_prestage_complete = getattr(obj, "cinematicBloomPrestageComplete", None)
                if cinematic_prestage_complete is None:
                    raise RuntimeError("BootstrapRoot.cinematicBloomPrestageComplete is unavailable.")
                cinematic_prestage_complete.connect(custom_splash.confirm_cinematic_bloom_prestaged)
                # The controller runs its hidden read in a worker and can be
                # unusually fast on a warm cache.  If readiness was emitted
                # during root construction, honour the already-recorded QML
                # request instead of waiting for a signal that has passed.
                if bool(obj.property("_phaseTwoCinematicRequested")):
                    QTimer.singleShot(0, custom_splash.begin_cinematic_reveal)
            native_splash_signal_bound = True
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.bindBootstrap", exc)

    engine.objectCreated.connect(on_object_created)


    _boot_log("BEGIN: importing AppController and RuntimeConfig")
    from backend.app_controller import AppController
    from backend.runtime_config import RuntimeConfig
    _boot_log("END: imported AppController and RuntimeConfig")
    
    _boot_log("BEGIN: resolving splash asset paths")
    splash_logo_url = _first_existing_file_url(_splash_logo_paths(), "logo")
    splash_static_logo_url = _first_existing_file_url(
        # splash_logo.png is intentionally transparent in the current asset
        # set.  Never select it as the native splash fallback, or the splash
        # can be visible while the actual logo is not.
        [SPLASH_LOGO_CLEAN_PATH, SPLASH_LOGO_ANIMATED_PATH],
        "static-logo",
    )
    splash_audio_url = _first_existing_file_url(SPLASH_AUDIO_PATHS, "audio")
    _boot_log("BEGIN: probing audio duration")
    splash_audio_duration_ms = _probe_audio_duration_ms(SPLASH_AUDIO_PATHS)
    _boot_log(f"END: probed audio duration ({splash_audio_duration_ms}ms)")
    splash_webengine_enabled = True if splash_force_webengine else _env_flag("CSPM_SPLASH_WEBENGINE", True)
    splash_webview_enabled = _env_flag("CSPM_SPLASH_WEBVIEW", not splash_force_webengine)
    if splash_force_webengine:
        splash_webview_enabled = False
    splash_logo_supersample = _env_float("CSPM_SPLASH_LOGO_SUPERSAMPLE", 1.15, 1.0, 3.0)
    splash_logo_web_oversample = _env_float("CSPM_SPLASH_LOGO_WEB_OVERSAMPLE", 1.0, 1.0, 3.0)
    splash_logo_layer_samples = _env_int("CSPM_SPLASH_LOGO_LAYER_SAMPLES", 1, 1, 16)
    splash_logo_max_texture = _env_int("CSPM_SPLASH_LOGO_MAX_TEXTURE", 4096, 1024, 16384)
    splash_logo_layer_enabled = _env_flag("CSPM_SPLASH_LOGO_LAYER_ENABLED", False)
    splash_logo_burn_quality = _env_float("CSPM_SPLASH_LOGO_BURN_QUALITY", 1.0, 0.35, 1.0)
    splash_logo_load_wait_ms = _env_int("CSPM_SPLASH_LOGO_LOAD_WAIT_MS", 250, 0, 8000)
    # Explicit lead control for when Phase 2 (logo-open) starts relative to the white fade-in.
    splash_logo_open_lead_ms = _env_int("CSPM_SPLASH_LOGO_OPEN_LEAD_MS", 1000, 0, 3000)
    searchbar_debug = _env_flag("CSPM_SEARCHBAR_DEBUG", False)
    splash_speed_factor = _env_float("CSPM_SPLASH_SPEED_FACTOR", 0.405, 0.405, 1.5)
    splash_total_ms = _env_int("CSPM_SPLASH_TOTAL_MS", 2000, 500, 18000)
    # Legacy-derived defaults.
    # Keep a clearly visible white fade-in by default.
    phase1_fade_default_ms = max(480, round(820 * splash_speed_factor))
    logo_overshoot_default_ms = max(88, round(176 * splash_speed_factor))
    logo_settle_default_ms = max(68, round(122 * splash_speed_factor))
    logo_snap_default_ms = max(50, round(90 * splash_speed_factor))
    logo_intro_default_ms = logo_overshoot_default_ms + logo_settle_default_ms + logo_snap_default_ms
    # Keep a smoother white fade-out by default.
    phase4_fade_default_ms = max(1250, round(1380 * splash_speed_factor))
    logo_hold_default_ms = max(0, splash_total_ms - phase1_fade_default_ms - logo_intro_default_ms - phase4_fade_default_ms)
    splash_sound_start_default_ms = 290

    # Explicit per-milestone controls for splash timeline tuning.
    splash_white_fade_start_ms = _env_int("CSPM_SPLASH_WHITE_FADE_START_MS", 0, 0, 30000)
    splash_white_solid_ms = _env_int("CSPM_SPLASH_WHITE_SOLID_MS", phase1_fade_default_ms, 0, 30000)
    splash_logo_start_ms = _env_int("CSPM_SPLASH_LOGO_START_MS", phase1_fade_default_ms, 0, 30000)
    splash_svg_fire_ash_end_ms = _env_int("CSPM_SPLASH_SVG_FIRE_ASH_END_MS", 5500, 0, 30000)
    splash_svg_light_start_ms = _env_int("CSPM_SPLASH_SVG_LIGHT_START_MS", 5500, 0, 30000)
    splash_svg_light_sweep_ms = _env_int(
        "CSPM_SPLASH_SVG_LIGHT_SWEEP_MS",
        max(0, round(2600 * max(1.0, splash_speed_factor))),
        0,
        30000,
    )
    splash_svg_end_ms = _env_int("CSPM_SPLASH_SVG_END_MS", 1500, 0, 30000)
    splash_svg_solid_hold_ms = _env_int(
        "CSPM_SPLASH_SVG_SOLID_HOLD_MS",
        max(0, round(520 * splash_speed_factor)),
        0,
        30000,
    )
    splash_fade_out_start_ms = _env_int(
        "CSPM_SPLASH_FADE_OUT_START_MS",
        phase1_fade_default_ms + logo_intro_default_ms + logo_hold_default_ms,
        0,
        30000,
    )
    splash_gone_ms = _env_int("CSPM_SPLASH_GONE_MS", splash_total_ms, 0, 30000)
    splash_fall_start_ms = _env_int("CSPM_SPLASH_FALL_START_MS", splash_total_ms, 0, 30000)
    splash_sound_start_ms = _env_int("CSPM_SPLASH_SOUND_START_MS", splash_sound_start_default_ms, 0, 30000)
    startup_deferred_queue_mode = os.environ.get(
        "CSPM_STARTUP_DEFERRED_QUEUE_MODE", "on"
    ).strip().lower()
    if startup_deferred_queue_mode not in {"off", "internal", "on"}:
        startup_deferred_queue_mode = "internal"
    startup_deferred_queue_internal_enabled = _env_flag(
        "CSPM_STARTUP_DEFERRED_QUEUE_INTERNAL",
        _env_flag("CSPM_DOCKET_TRACE", False) or VERBOSE_TERMINAL_LOGGING,
    )
    startup_deferred_queue_tick_ms = _env_int(
        "CSPM_STARTUP_DEFERRED_QUEUE_TICK_MS", 180, 24, 2000
    )
    startup_main_object_prewarm_enabled = _env_flag(
        "CSPM_STARTUP_MAIN_OBJECT_PREWARM", False
    )
    startup_main_object_prewarm_lead_ms = _env_int(
        "CSPM_STARTUP_MAIN_OBJECT_PREWARM_LEAD_MS", 4200, 600, 12000
    )
    startup_fast_launch_focus_enabled = _env_flag(
        "CSPM_STARTUP_FAST_LAUNCH_FOCUS", True
    )
    startup_queue_wait_for_first_input = _env_flag(
        "CSPM_STARTUP_QUEUE_WAIT_FOR_FIRST_INPUT", False
    )
    startup_queue_input_fallback_ms = _env_int(
        "CSPM_STARTUP_QUEUE_INPUT_FALLBACK_MS", 0, 0, 10000
    )
    startup_background_idle_ms = _env_int(
        "CSPM_STARTUP_BACKGROUND_IDLE_MS", 900, 250, 10000
    )
    startup_defer_settings_load = _env_flag(
        "CSPM_STARTUP_DEFER_SETTINGS_LOAD", True
    )

    # Keep milestone relationships sane if user-provided values overlap.
    # Enforce visible fades even if env overrides collapse markers.
    splash_white_solid_ms = max(splash_white_fade_start_ms + 420, splash_white_solid_ms)
    splash_logo_start_ms = max(splash_white_solid_ms, splash_logo_start_ms)
    splash_svg_light_start_ms = max(0, splash_svg_light_start_ms)
    splash_svg_fire_ash_end_ms = max(0, splash_svg_fire_ash_end_ms)
    splash_svg_end_ms = max(splash_svg_light_start_ms, splash_svg_end_ms)
    splash_logo_intro_end_ms = splash_logo_start_ms + logo_intro_default_ms
    splash_fade_out_start_ms = max(splash_logo_intro_end_ms, splash_fade_out_start_ms)
    splash_gone_ms = max(splash_fade_out_start_ms + 1200, splash_gone_ms)
    splash_fall_start_ms = max(splash_gone_ms, splash_fall_start_ms)
    _boot_log("END: resolved splash asset paths")

    def _fmt_sec(ms_value: int) -> str:
        return f"{(max(0, int(ms_value)) / 1000.0):.2f}s"

    if SPLASH_TIMELINE_LOGGING or VERBOSE_TERMINAL_LOGGING:
        _timeline_log("[SPLASH TIMELINE] Exact current timeline (defaults, to .01s):")
        _timeline_log(f"[SPLASH TIMELINE] White fade begins: {_fmt_sec(splash_white_fade_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] White fully solid: {_fmt_sec(splash_white_solid_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] SVG animation begins: {_fmt_sec(splash_logo_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] SVG fire/ash phase ends (marker): {_fmt_sec(splash_svg_fire_ash_end_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] SVG light sweep begins (marker): {_fmt_sec(splash_svg_light_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] SVG animation ends: {_fmt_sec(splash_svg_end_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] Splash fade-out begins: {_fmt_sec(splash_fade_out_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] Splash completely gone: {_fmt_sec(splash_gone_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] Falling window begins: {_fmt_sec(splash_fall_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] Sound begins: {_fmt_sec(splash_sound_start_ms)}")
        _timeline_log(f"[SPLASH TIMELINE] Sound ends: {_fmt_sec(splash_sound_start_ms + splash_audio_duration_ms)}")

    _boot_log("BEGIN: creating RuntimeConfig")
    runtime_config = RuntimeConfig(
        startup_splash_logo_url=splash_logo_url,
        startup_splash_static_logo_url=splash_static_logo_url,
        startup_splash_webengine_enabled=splash_webengine_enabled,
        startup_splash_force_webengine=splash_force_webengine,
        startup_splash_webview_enabled=splash_webview_enabled,
        startup_splash_logo_supersample=splash_logo_supersample,
        startup_splash_logo_web_oversample=splash_logo_web_oversample,
        startup_splash_logo_layer_samples=splash_logo_layer_samples,
        startup_splash_logo_max_texture=splash_logo_max_texture,
        startup_splash_logo_layer_enabled=splash_logo_layer_enabled,
        startup_splash_logo_burn_quality=splash_logo_burn_quality,
        startup_splash_logo_load_wait_ms=splash_logo_load_wait_ms,
        startup_splash_logo_open_lead_ms=splash_logo_open_lead_ms,
        startup_splash_speed_factor=splash_speed_factor,
        startup_splash_total_ms=splash_total_ms,
        startup_splash_audio_url=splash_audio_url,
        startup_splash_audio_duration_ms=splash_audio_duration_ms,
        startup_splash_white_fade_start_ms=splash_white_fade_start_ms,
        startup_splash_white_solid_ms=splash_white_solid_ms,
        startup_splash_logo_start_ms=splash_logo_start_ms,
        startup_splash_svg_fire_ash_end_ms=splash_svg_fire_ash_end_ms,
        startup_splash_svg_light_start_ms=splash_svg_light_start_ms,
        startup_splash_svg_light_sweep_ms=splash_svg_light_sweep_ms,
        startup_splash_svg_end_ms=splash_svg_end_ms,
        startup_splash_svg_solid_hold_ms=splash_svg_solid_hold_ms,
        startup_splash_fade_out_start_ms=splash_fade_out_start_ms,
        startup_splash_gone_ms=splash_gone_ms,
        startup_splash_fall_start_ms=splash_fall_start_ms,
        startup_splash_sound_start_ms=splash_sound_start_ms,
        search_bar_debug_enabled=searchbar_debug,
        debug_frames_enabled=DEBUG_FRAMES_ENABLED,
        verbose_logging_enabled=VERBOSE_TERMINAL_LOGGING,
        startup_deferred_queue_mode=startup_deferred_queue_mode,
        startup_deferred_queue_internal_enabled=startup_deferred_queue_internal_enabled,
        startup_deferred_queue_tick_ms=startup_deferred_queue_tick_ms,
        startup_main_object_prewarm_enabled=startup_main_object_prewarm_enabled,
        startup_main_object_prewarm_lead_ms=startup_main_object_prewarm_lead_ms,
        startup_fast_launch_focus_enabled=startup_fast_launch_focus_enabled,
        startup_queue_wait_for_first_input=startup_queue_wait_for_first_input,
        startup_queue_input_fallback_ms=startup_queue_input_fallback_ms,
        startup_background_idle_ms=startup_background_idle_ms,
    )
    _boot_log("END: created RuntimeConfig")
    
    _boot_log("BEGIN: creating AppController")
    controller = AppController(
        runtime_config=runtime_config,
        defer_settings_load=startup_defer_settings_load,
        startup_launch_context=startup_launch_context,
    )
    _boot_log("END: created AppController")
    if custom_splash is not None:
        try:
            controller.startupReadinessFailed.connect(custom_splash.show_startup_error)
            def _sync_native_splash_readiness_progress() -> None:
                try:
                    custom_splash.set_readiness_progress(
                        float(getattr(controller, "startupReadinessProgress", 0.0) or 0.0)
                    )
                except Exception as exc:
                    _report_nonfatal_startup_failure(
                        "nativeSplash.syncStartupReadinessProgress", exc
                    )

            controller.startupReadinessChanged.connect(_sync_native_splash_readiness_progress)
            _sync_native_splash_readiness_progress()
        except Exception as exc:
            _report_nonfatal_startup_failure("nativeSplash.bindStartupReadinessFailure", exc)
    global _startup_input_notify_callback
    _startup_input_notify_callback = controller.markStartupUserActivity

    # AP is composed on AppController (app.apController), matching docketing/billing.
    # Keep a context-property alias for older QML resolution paths during transition.
    engine.rootContext().setContextProperty("app", controller)
    engine.rootContext().setContextProperty("apBackendController", controller.apController)
    _boot_log("context.app.injected")
    engine.rootContext().setContextProperty("docketApp", controller.docketing)
    logging.getLogger("startup").info(
        "AP controller exposed via app.apController and apBackendController (workbook=%s)",
        getattr(getattr(controller, "_ap_repository", None), "path", None),
    )

    qmlRegisterType(NativeSvgItem, "com.cspm.components", 1, 0, "NativeSvgItem")  # type: ignore

    engine.quit.connect(app.quit)
    runtime_hook_state = {
        "installed": False,
        "retry_count": 0,
        "startup_close_rechecks": 0,
    }

    def _top_level_windows_safe() -> list:
        try:
            return list(app.topLevelWindows())
        except Exception:
            return []

    def _has_visible_top_level_window() -> bool:
        windows = _top_level_windows_safe()
        logging.getLogger("startup").info("Checking %d top level windows", len(windows))
        for win in windows:
            try:
                if win is not None:
                    vis = win.isVisible()
                    obj_name = str(win.objectName() or "")
                    logging.getLogger("startup").info("Window %s isVisible=%s", obj_name, vis)
                    if vis:
                        return True
            except Exception as e:
                logging.getLogger("startup").info("Exception checking window: %s", e)
                continue
        return False

    def _qml_property_safe(obj, name: str, fallback=None):
        try:
            if obj is None:
                return fallback
            prop_fn = getattr(obj, "property", None)
            if callable(prop_fn):
                return prop_fn(name)
        except Exception:
            return fallback
        return fallback

    def _bootstrap_startup_pending() -> bool:
        try:
            root_obj = root
        except NameError:
            return True
        if root_obj is None:
            return False
        if _qml_property_safe(root_obj, "mainWindowRef") is not None:
            return True
        if _qml_property_safe(root_obj, "splashRef") is not None:
            return True
        splash_refs = _qml_property_safe(root_obj, "splashRefs", [])
        try:
            if isinstance(splash_refs, list) and len(splash_refs) > 0:
                return True
        except Exception:
            pass
        state = str(_qml_property_safe(root_obj, "_startupState", "") or "")
        if state in {
            "init",
            "splash-starting",
            "splash-running",
            "gate-open",
            "main-created",
            "core-launch-dispatched",
        }:
            return True
        launch_gate_open = bool(_qml_property_safe(root_obj, "_launchGateOpen", False))
        try:
            val_count = _qml_property_safe(root_obj, "_createRetryAttempts", 0)
            retry_count = int(str(val_count)) if val_count is not None else 0
            val_max = _qml_property_safe(root_obj, "_createRetryMaxAttempts", 0)
            retry_max = int(str(val_max)) if val_max is not None else 0
        except Exception:
            retry_count = 0
            retry_max = 0
        return launch_gate_open and (retry_max <= 0 or retry_count < retry_max)

    def on_about_to_quit() -> None:
        global _startup_input_notify_callback
        # Do NOT delete the engine here and do NOT call os._exit().
        try:
            if controller is not None and hasattr(controller, "shutdown"):
                # A checked-out CSPM session publishes a verified cloud release
                # (or reports a safe conflict) before its normal exit releases
                # the exclusive write lease.
                controller.shutdown()
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.publishSharedData", exc)
        try:
            if controller is not None and hasattr(controller, "markExpectedShutdown"):
                controller.markExpectedShutdown(True)
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.markExpectedShutdown", exc)
        try:
            mask_sync_manager = getattr(app, "_orange_input_mask_sync_manager", None)
            if mask_sync_manager is not None and hasattr(mask_sync_manager, "clear"):
                mask_sync_manager.clear()
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.clearMaskSync", exc)
        try:
            low_level_hook = getattr(app, "_win_shift_low_level_hook", None)
            if low_level_hook is not None and hasattr(low_level_hook, "uninstall"):
                low_level_hook.uninstall()
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.uninstallLowLevelHook", exc)
        try:
            click_through_filter = getattr(app, "_click_through_filter", None)
            if click_through_filter is not None:
                shutdown_fn = getattr(click_through_filter, "shutdown", None)
                if callable(shutdown_fn):
                    shutdown_fn()
                app.removeNativeEventFilter(click_through_filter)
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.removeClickThroughFilter", exc)
        try:
            win_shift_override_filter = getattr(app, "_win_shift_arrow_override_filter", None)
            if win_shift_override_filter is not None:
                app.removeNativeEventFilter(win_shift_override_filter)
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.removeWinShiftOverrideFilter", exc)
        try:
            startup_input_probe = getattr(app, "_startup_input_probe", None)
            if startup_input_probe is not None:
                app.removeEventFilter(startup_input_probe)
        except Exception as exc:
            _report_nonfatal_startup_failure("aboutToQuit.removeStartupInputProbe", exc)
        _startup_input_notify_callback = None
        _drain_all_windows()

    def on_last_window_closed() -> None:
        # If the app is living in the system tray, don't quit.
        tray_icon = getattr(app, '_tray_icon', None)
        tray_exit = getattr(app, '_tray_exit_requested', False)
        # A main-shell close can legitimately pass through this Qt signal
        # while CSPM is still tray-resident.  Record it for diagnostics without
        # presenting a normal lifecycle path as a startup warning.
        logging.getLogger("startup").info(
            "lastWindowClosed observed: tray_icon=%s tray_exit=%s isVisible=%s",
            tray_icon is not None, tray_exit,
            tray_icon.isVisible() if tray_icon else "N/A"
        )
        if tray_icon is not None and not tray_exit:
            logging.getLogger("startup").info(
                "lastWindowClosed ignored: app is tray-resident"
            )
            return
        # Ignore transient startup window churn until the real runtime window hooks
        # are installed; otherwise releasing temporary bootstrap windows can tear
        # down splash/main windows before launch.
        if not runtime_hook_state.get("installed", False):
            logging.getLogger("startup").info(
                "Ignoring lastWindowClosed before runtime hooks install"
            )

            def _recheck_startup_window_closure() -> None:
                # If app became tray-resident, stop the watchdog.
                tray_icon = getattr(app, '_tray_icon', None)
                tray_exit = getattr(app, '_tray_exit_requested', False)
                if tray_icon is not None and not tray_exit:
                    logging.getLogger("startup").info("Recheck aborted: tray-resident")
                    return
                if runtime_hook_state.get("installed", False):
                    return
                try:
                    _install_runtime_native_features()
                except Exception as exc:
                    _report_nonfatal_startup_failure("lastWindowClosed.installRuntimeHooksRetry", exc)
                if runtime_hook_state.get("installed", False) or _has_visible_top_level_window():
                    return
                if _bootstrap_startup_pending():
                    runtime_hook_state["startup_close_rechecks"] += 1
                    if runtime_hook_state["startup_close_rechecks"] <= 48:
                        logging.getLogger("startup").info(
                            "Startup window closure recheck deferred: bootstrap still pending"
                        )
                        QTimer.singleShot(2500, _recheck_startup_window_closure)
                        return
                logging.getLogger("startup").error(
                    "Startup stall detected: no visible windows before runtime hooks install"
                )
                _report_terminal_failure(
                    "Startup stalled before a visible window was established. See logs/cspm.log."
                )
                app.quit()

            QTimer.singleShot(2500, _recheck_startup_window_closure)
            return
        try:
            booted = bool(getattr(controller, "backendBooted", False))
        except Exception as exc:
            _report_nonfatal_startup_failure("lastWindowClosed.backendBootedProbe", exc)
            booted = True
        _drain_all_windows()
        if booted:
            QTimer.singleShot(0, app.quit)

    app.aboutToQuit.connect(on_about_to_quit)
    app.lastWindowClosed.connect(on_last_window_closed)
    if startup_defer_settings_load:
        # Keep the safety fallback well after the splash + settle path so it does
        # not compete with first paint or the opening motion.
        startup_deferred_settings_fallback_ms = max(12000, splash_total_ms + 2500)
        QTimer.singleShot(
            startup_deferred_settings_fallback_ms,
            lambda: controller.requestDeferredSettingsLoad("startup-fallback-timer"),
        )

    qml_path = PROJECT_ROOT / "src" / "qml" / "Main.qml"
    qml_url = QUrl.fromLocalFile(str(qml_path))

    # Add QML import paths before loading
    qml_dir = PROJECT_ROOT / "src" / "qml"
    src_dir = PROJECT_ROOT / "src"
    engine.addImportPath(str(src_dir))
    engine.addImportPath(str(qml_dir))

    _boot_log("BEGIN: loading Main.qml")

    tray_controller = None
    try:
        from backend.controllers.tray_controller import TrayController
        _boot_log("BEGIN: init TrayController")
        tray_controller = TrayController(controller)
        engine.rootContext().setContextProperty("trayController", tray_controller)
        app._tray_controller = tray_controller # keep a reference
        _boot_log("END: init TrayController")
    except Exception as exc:
        logging.getLogger("startup").exception("Failed to initialize TrayController")

    qml_url = QUrl.fromLocalFile(str(PROJECT_ROOT / "src" / "qml" / "Main.qml"))
    
    main_window_load_requested = False

    def load_main_window():
        nonlocal main_window_load_requested
        if main_window_load_requested:
            return
        main_window_load_requested = True
        root_count_before_load = len(engine.rootObjects())
        _boot_log("BEGIN: loading Main.qml dynamically")
        engine.load(qml_url)
        if len(engine.rootObjects()) <= root_count_before_load:
            main_window_load_requested = False
            logging.getLogger("startup").error("Main QML component failed to load: %s", qml_url.toString())
            _report_terminal_failure("Startup failed: main QML component did not load. See logs/cspm.log.")
            sys.exit(1)

    controller.requestMainWindowLoad.connect(load_main_window)

    def _handle_existing_instance_wakeup(socket) -> None:
        try:
            payload = bytes(socket.readAll()).decode("utf-8", errors="ignore")
            if "WAKEUP" not in payload:
                return
            logging.getLogger("startup").info(
                "Existing CSPM instance received WAKEUP; opening the current tray-only/main instance without splash."
            )
            if tray_controller is not None:
                QTimer.singleShot(0, tray_controller.open_cspm)
            else:
                QTimer.singleShot(0, load_main_window)
        finally:
            try:
                socket.disconnectFromServer()
            except Exception:
                pass

    def _accept_existing_instance_wakeup() -> None:
        while ipc_server.hasPendingConnections():
            socket = ipc_server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda sock=socket: _handle_existing_instance_wakeup(sock))
            if socket.bytesAvailable() > 0:
                _handle_existing_instance_wakeup(socket)

    ipc_server = QLocalServer(app)
    try:
        # The mutex above proves no live CSPM instance owns this endpoint, so
        # removing a stale endpoint after a crash is safe.
        QLocalServer.removeServer("CSPM_IPC_SERVER")
        if not ipc_server.listen("CSPM_IPC_SERVER"):
            logging.getLogger("startup").warning(
                "Unable to listen for duplicate-launch wakeups: %s",
                ipc_server.errorString(),
            )
        else:
            ipc_server.newConnection.connect(_accept_existing_instance_wakeup)
            app._cspm_ipc_server = ipc_server  # type: ignore[attr-defined]
    except Exception as exc:
        _report_nonfatal_startup_failure("singleInstance.listen", exc)

    if not is_tray_only:
        if custom_splash is not None:
            # ``show_first_frame`` intentionally stops the legacy fade-in
            # animation after it has painted a complete native CS frame. Do
            # not wait on that animation's ``finished`` signal here: it will
            # never fire after ``stop()``, leaving the splash at 0% forever.
            # Run the QML load on the first event-loop turn.  Calling it
            # synchronously here starts Qt Quick while QApplication is still
            # completing its setup; that is capable of crashing the source
            # process with an access violation.  This introduces no timed
            # delay: the native CS frame has already been painted and the
            # queued callback runs as soon as app.exec() begins.  The existing
            # objectCreated handler binds BootstrapRoot even though TrayRoot
            # has been created first.
            QTimer.singleShot(0, load_main_window)
        else:
            load_main_window()

    try:
        tray_url = QUrl.fromLocalFile(str(PROJECT_ROOT / "src" / "qml" / "tray" / "TrayRoot.qml"))
        engine.load(tray_url)
        
        # Native QSystemTrayIcon
        app._tray_icon = QSystemTrayIcon(QIcon(str(PROJECT_ROOT / "src" / "assets" / "app_icon.ico")), app)
        tray_menu = QMenu()
        open_action = tray_menu.addAction("Open CSPM")
        open_action.triggered.connect(tray_controller.open_cspm)
        exit_action = tray_menu.addAction("Exit CSPM")
        exit_action.triggered.connect(tray_controller.exit_cspm)
        app._tray_icon.setContextMenu(tray_menu)
        
        def _on_tray_activated(reason):
            if reason == QSystemTrayIcon.Trigger:
                tray_controller.calculate_flyout_geometry()
            elif reason == QSystemTrayIcon.DoubleClick:
                tray_controller.open_cspm()
        app._tray_icon.activated.connect(_on_tray_activated)
        app._tray_icon.show()
    except Exception as exc:
        logging.getLogger("startup").exception("Failed to load TrayRoot.qml")

    try:
        root = engine.rootObjects()[0]
    except Exception as exc:
        _report_nonfatal_startup_failure("engine.rootObjects.first", exc)
        root = None

    if root is not None:
        if not native_splash_signal_bound:
            try:
                root.setProperty("nativeStartupCinematicActive", custom_splash is not None)
                main_window_ready = getattr(root, "mainWindowReady", None)
                if main_window_ready is not None:
                    main_window_ready.connect(_bind_native_splash_to_main_window)
                    native_splash_bootstrap_root = root
                    if custom_splash is not None:
                        cinematic_reveal = getattr(root, "cinematicRevealRequested", None)
                        if cinematic_reveal is None:
                            raise RuntimeError("BootstrapRoot.cinematicRevealRequested is unavailable.")
                        cinematic_reveal.connect(custom_splash.begin_cinematic_reveal)
                        cinematic_prestage_complete = getattr(root, "cinematicBloomPrestageComplete", None)
                        if cinematic_prestage_complete is None:
                            raise RuntimeError("BootstrapRoot.cinematicBloomPrestageComplete is unavailable.")
                        cinematic_prestage_complete.connect(custom_splash.confirm_cinematic_bloom_prestaged)
                        if bool(root.property("_phaseTwoCinematicRequested")):
                            QTimer.singleShot(0, custom_splash.begin_cinematic_reveal)
                    native_splash_signal_bound = True
            except Exception as exc:
                _report_nonfatal_startup_failure("nativeSplash.bindBootstrapFallback", exc)
        from PySide6.QtGui import QKeyEvent
        class GlobalSplashSkipFilter(QObject):
            def eventFilter(self, watched: QObject, event: Any) -> bool:
                return False

        _splash_skip_filter = GlobalSplashSkipFilter(app)
        app.installEventFilter(_splash_skip_filter)
        app._splash_skip_filter = _splash_skip_filter # type: ignore[attr-defined]

    def _resolve_hook_target_window():
        if root is None:
            return None
        candidate = root
        try:
            win_id_fn = getattr(candidate, "winId", None)
            if callable(win_id_fn):
                win_id = win_id_fn()
                if win_id is not None:
                    return candidate
        except Exception:
            pass
        try:
            candidate = root.property("mainWindowRef")
        except Exception:
            candidate = None
        if candidate is None:
            return None
        try:
            win_id_fn = getattr(candidate, "winId", None)
            if callable(win_id_fn):
                win_id = win_id_fn()
                if win_id is not None:
                    return candidate
        except Exception:
            pass
        for candidate in _top_level_windows_safe():
            try:
                obj_name = str(candidate.objectName() or "")
            except Exception:
                obj_name = ""
            if obj_name not in ("CSPMMainWindow", "CSPMFloatingDocketWindow"):
                continue
            try:
                win_id_fn = getattr(candidate, "winId", None)
                if callable(win_id_fn):
                    win_id = win_id_fn()
                    if win_id is not None:
                        return candidate
            except Exception:
                continue
        return None

    def _install_runtime_native_features() -> None:
        if runtime_hook_state["installed"]:
            return
        hook_target = _resolve_hook_target_window()
        if hook_target is None:
            runtime_hook_state["retry_count"] += 1
            if runtime_hook_state["retry_count"] <= 2400:
                QTimer.singleShot(50, _install_runtime_native_features)
            return
        runtime_hook_state["installed"] = True
        runtime_hook_state["startup_close_rechecks"] = 0
        # app.setQuitOnLastWindowClosed(True) # Disabled to keep tray app alive
        try:
            icon_sync = getattr(app, "_cspm_app_icon_sync", None)
            if icon_sync is not None and hasattr(icon_sync, "apply_all"):
                icon_sync.apply_all()
        except Exception as exc:
            _report_nonfatal_startup_failure("icon.applyAfterHookTarget", exc)
        try:
            from platform.orange_mask_sync import _AllWindowMaskSyncManager
            mask_sync_manager = _AllWindowMaskSyncManager(app)
            app._orange_input_mask_sync_manager = mask_sync_manager  # type: ignore[attr-defined]
            _vlog("[MASK] Orange input/window mask sync manager installed")
        except Exception as exc:
            _vlog(f"[MASK] Failed to initialize mask sync manager: {exc}")
        if not sys.platform.startswith("win"):
            return
        if _env_flag("CSPM_ENABLE_LOW_LEVEL_WIN_HOOK", True):
            try:
                from platform.win_shift_arrow import _WinShiftArrowLowLevelHook
                win_shift_low_level_hook = _WinShiftArrowLowLevelHook(hook_target)
                app._win_shift_low_level_hook = win_shift_low_level_hook  # type: ignore[attr-defined]
            except Exception as exc:
                _vlog(f"[WINHOOK] Failed to init low-level Win+Shift hook: {exc}")
        try:
            from platform.win_shift_arrow import _WinShiftArrowOverrideFilter
            win_shift_override_filter = _WinShiftArrowOverrideFilter(hook_target)
            app.installNativeEventFilter(win_shift_override_filter)
            # Keep a strong reference for the app lifetime.
            app._win_shift_arrow_override_filter = win_shift_override_filter  # type: ignore[attr-defined]
        except Exception as exc:
            _vlog(f"[WINHOOK] Failed to install native Win+Shift override filter: {exc}")
        try:
            from platform.orange_pass_through import _OutsideOrangePassThroughFilter
            click_through_filter = _OutsideOrangePassThroughFilter(hook_target)
            app.installNativeEventFilter(click_through_filter)
            app._click_through_filter = click_through_filter  # type: ignore[attr-defined]
        except Exception as exc:
            _vlog(f"[WINHOOK] Failed to install click-through filter: {exc}")


    # Install native hooks/filters after the event loop starts, not on the pre-handoff path.
    try:
        ready_signal = getattr(root, "mainWindowReady", None)
        if ready_signal is not None:
            ready_signal.connect(lambda _window=None: QTimer.singleShot(0, _install_runtime_native_features))
    except Exception as exc:
        _report_nonfatal_startup_failure("root.mainWindowReady.connectRuntimeHooks", exc)
    QTimer.singleShot(0, _install_runtime_native_features)

    
    # Keep splash overlays visually above other windows during early startup
    # without repeatedly forcing focus (which can spam requestActivate warnings
    # on non-focusable tool windows).
    def _reassert_startup_visibility() -> None:
        try:
            import shiboken6
        except ImportError:
            shiboken6 = None
        for win in app.topLevelWindows():
            try:
                if shiboken6 is not None and not shiboken6.isValid(win):
                    continue
                if str(win.objectName() or "") != "CSPMStartupSplash":
                    continue
                if not win.isVisible():
                    continue
                win.raise_()
            except Exception:
                continue

    startup_focus_timer = QTimer()
    startup_focus_timer.timeout.connect(_reassert_startup_visibility)
    startup_focus_timer.start(90)

    def _finish_startup_visibility_period() -> None:
        """End the visual-splash period without changing foreground focus."""
        startup_focus_timer.stop()

    # The startup splash interval has ended; do not reclaim the foreground.
    QTimer.singleShot(3500, _finish_startup_visibility_period)
    pass # Removed hardcoded splash timer

    code = startup_logger.info(f'[{time.perf_counter()-t0:.3f}s] Handing off to Qt Engine Event Loop')
    code = app.exec()
    sys.exit(code)


if __name__ == "__main__":
    # allow simple inspection of roadmap
    if "--print-np" in sys.argv:
        _print_np_status_and_exit()
    try:
        main()
    except Exception as exc:
        logging.getLogger("startup").exception("Fatal startup failure")
        _report_terminal_failure(f"Fatal startup failure: {exc}. See logs/cspm.log.")
        raise
