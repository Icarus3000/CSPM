"""Qt tray geometry and panel-edge recovery without a GUI or cloud data."""
from pathlib import Path
from types import SimpleNamespace
import sys

from PySide6.QtCore import QRect
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.controllers import tray_controller as module
from backend.controllers.tray_controller import TrayController


def tray_app(monkeypatch, rect, work=None, visible=True):
    monitor = QRect(-1600, 0, 1600, 900)
    screen = SimpleNamespace(geometry=lambda: monitor,
                             availableGeometry=lambda: work or monitor)
    icon = SimpleNamespace(geometry=lambda: rect, isVisible=lambda: visible)
    app = SimpleNamespace(_tray_icon=icon, primaryScreen=lambda: screen)
    monkeypatch.setattr(module, "QApplication", SimpleNamespace(instance=lambda: app))
    return app


def test_linux_uses_real_qt_icon_bounds_before_panel_estimation(monkeypatch):
    tray_app(monkeypatch, QRect(-96, 864, 32, 32))
    geometry = TrayController._qt_system_tray_geometry(SimpleNamespace())
    assert geometry == {"x": -96, "y": 864, "width": 32, "height": 32,
                        "source": "qt-tray-icon"}


@pytest.mark.parametrize("work,expected", [
    (QRect(-1600, 0, 1600, 860), (-40, 860, 40, 40)),
    (QRect(-1600, 40, 1600, 860), (-40, 0, 40, 40)),
    (QRect(-1560, 0, 1560, 900), (-1600, 860, 40, 40)),
    (QRect(-1600, 0, 1560, 900), (-40, 860, 40, 40)),
])
def test_missing_status_notifier_geometry_follows_reserved_panel_edge(monkeypatch, work, expected):
    tray_app(monkeypatch, QRect(), work)
    geometry = TrayController._qt_system_tray_geometry(SimpleNamespace())
    assert tuple(geometry[key] for key in ("x", "y", "width", "height")) == expected
    assert geometry["source"] == "panel-edge-estimate"


@pytest.mark.parametrize("visible", [True, False])
def test_unknown_or_hidden_tray_keeps_the_existing_unavailable_fallback(monkeypatch, visible):
    tray_app(monkeypatch, QRect(), visible=visible)
    assert TrayController._qt_system_tray_geometry(SimpleNamespace()) == {}


def test_non_windows_never_attempts_the_win32_tray_api(monkeypatch):
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="linux"))
    expected = {"x": 12, "y": 15, "width": 32, "height": 32}
    controller = SimpleNamespace(_qt_system_tray_geometry=lambda: expected)
    assert TrayController.getSystemTrayGeometry(controller) == expected


def test_cross_monitor_flight_uses_qt_bounds_and_all_monitor_origins(monkeypatch):
    left = SimpleNamespace(geometry=lambda: QRect(-1600, 0, 1600, 900))
    right = SimpleNamespace(geometry=lambda: QRect(0, -200, 1920, 1080))
    app = SimpleNamespace(screens=lambda: [left, right],
        screenAt=lambda point: left if point.x() < 0 else right)
    monkeypatch.setattr(module, "QGuiApplication", SimpleNamespace(instance=lambda: app))
    controller = SimpleNamespace(getSystemTrayGeometry=lambda: {
        "x": -40, "y": 860, "width": 40, "height": 40, "source": "qt-tray-icon"})
    result = TrayController.getTrayFlightInfo(controller, 960, 400)
    assert result["available"] and not result["sameMonitor"]
    assert (result["trayCenterX"], result["trayCenterY"]) == (-20, 880)
    assert (result["vdX"], result["vdY"], result["vdW"], result["vdH"]) == (-1600, -200, 3520, 1100)
    assert result["source"] == "qt-tray-icon"
