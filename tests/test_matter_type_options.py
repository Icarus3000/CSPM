import sys
from pathlib import Path

from PySide6.QtCore import QObject


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))

from backend.app_controller import (  # noqa: E402
    AppController,
    CUSTOM_MATTER_TYPES_KEY,
    DEFAULT_MATTER_TYPES_BY_PRACTICE_AREA,
)


class _CrudStub:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def list_matter_directory(self):
        return list(self.rows)


def _controller(settings=None, rows=None, save_ok=True):
    controller = AppController.__new__(AppController)
    QObject.__init__(controller)
    controller._settings_load_complete = True
    controller._settings_data = dict(settings or {})
    controller._is_booted = True
    controller._crud = _CrudStub(rows)
    controller.save_settings = lambda: save_ok
    return controller


def test_default_catalog_has_broad_practice_area_choices() -> None:
    assert len(DEFAULT_MATTER_TYPES_BY_PRACTICE_AREA["General"]) >= 10
    assert "Independent Legal Advice" in DEFAULT_MATTER_TYPES_BY_PRACTICE_AREA["General"]
    assert "Trademark Search / Clearance" in DEFAULT_MATTER_TYPES_BY_PRACTICE_AREA["Intellectual Property"]
    assert "Tax Court Appeal" in DEFAULT_MATTER_TYPES_BY_PRACTICE_AREA["Tax"]


def test_custom_matter_type_is_normalized_persisted_and_deduplicated() -> None:
    controller = _controller()

    added = controller.addMatterTypeOption("Tax", "  Scientific   Research  &  Experimental Development ")

    assert added["ok"] is True
    assert added["created"] is True
    assert added["matterType"] == "Scientific Research & Experimental Development"
    assert controller._settings_data[CUSTOM_MATTER_TYPES_KEY]["Tax"] == [
        "Scientific Research & Experimental Development"
    ]

    reloaded = _controller(controller._settings_data)
    assert "Scientific Research & Experimental Development" in reloaded.getMatterTypeOptions("Tax")

    duplicate = reloaded.addMatterTypeOption("tax", "scientific research & experimental development")
    assert duplicate["ok"] is True
    assert duplicate["created"] is False
    assert duplicate["matterType"] == "Scientific Research & Experimental Development"


def test_workbook_matter_types_remain_available_in_their_practice_area() -> None:
    controller = _controller(
        rows=[
            {"practiceArea": "Tax", "matterType": "Legacy Tax Advisory"},
            {"practiceArea": "Family Law", "matterType": "Legacy Family File"},
        ]
    )

    assert "Legacy Tax Advisory" in controller.getMatterTypeOptions("Tax")
    assert "Legacy Family File" not in controller.getMatterTypeOptions("Tax")
    assert "Other" in controller.getMatterTypeOptions("Family Law")


def test_failed_settings_write_rolls_back_custom_catalog_change() -> None:
    controller = _controller(save_ok=False)

    result = controller.addMatterTypeOption("General", "A Type That Will Not Save")

    assert result == {"ok": False, "message": "The matter type could not be saved."}
    assert CUSTOM_MATTER_TYPES_KEY not in controller._settings_data


def test_new_matter_wizard_exposes_persistent_add_type_workflow() -> None:
    qml = (ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(encoding="utf-8")

    assert "appRef.getMatterTypeOptions(area)" in qml
    assert "appRef.addMatterTypeOption(area, label)" in qml
    assert 'id: addMatterTypePopup' in qml
    assert 'text: "+ Add"' in qml
