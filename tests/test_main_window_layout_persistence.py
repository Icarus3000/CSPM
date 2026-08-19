import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))

from backend.app_controller import AppController


def _layout_controller() -> AppController:
    controller = AppController.__new__(AppController)
    controller._settings_data = {}
    controller.save_settings = lambda: True
    return controller


def test_exact_main_window_rectangle_round_trips_through_app_settings() -> None:
    controller = _layout_controller()

    assert controller.saveMainWindowLayout(
        {
            "maximized": False,
            "hasExactRect": True,
            "x": -1600,
            "y": 32,
            "width": 1200,
            "height": 900,
            "workAreaX": -1920,
            "workAreaY": 0,
            "workAreaWidth": 1920,
            "workAreaHeight": 1040,
            "widthPct": 0.625,
            "heightPct": 0.865,
            "centerXPct": 0.4,
            "centerYPct": 0.5,
        }
    )

    saved = controller.getMainWindowLayout()
    assert saved["ok"] is True
    assert saved["hasExactRect"] is True
    assert (saved["x"], saved["y"], saved["width"], saved["height"]) == (-1600, 32, 1200, 900)
    assert (
        saved["workAreaX"],
        saved["workAreaY"],
        saved["workAreaWidth"],
        saved["workAreaHeight"],
    ) == (-1920, 0, 1920, 1040)


def test_invalid_exact_main_window_rectangle_falls_back_to_proportional_restore() -> None:
    controller = _layout_controller()

    assert controller.saveMainWindowLayout(
        {
            "maximized": False,
            "hasExactRect": True,
            "x": "not-a-coordinate",
            "y": 0,
            "width": 1200,
            "height": 900,
            "workAreaX": 0,
            "workAreaY": 0,
            "workAreaWidth": 1920,
            "workAreaHeight": 1040,
            "widthPct": 0.625,
            "heightPct": 0.865,
            "centerXPct": 0.4,
            "centerYPct": 0.5,
        }
    )

    saved = controller.getMainWindowLayout()
    assert saved["hasExactRect"] is False
    assert saved["widthPct"] == 0.625
    assert saved["heightPct"] == 0.865


def test_qml_restores_exact_layout_only_when_the_saved_work_area_matches() -> None:
    shell = (ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(encoding="utf-8")

    assert "payload.hasExactRect = true;" in shell
    assert "payload.workAreaWidth = uw;" in shell
    assert "var exactWorkAreaMatches = saved.hasExactRect === true" in shell
    assert "if (exactFitsWorkArea) {" in shell
    assert 'return { "maximized": false, "x": exactX, "y": exactY, "w": exactW, "h": exactH };' in shell
