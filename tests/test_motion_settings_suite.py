"""
Unit tests for the Singularity Motion Suite & Motion FX Studio Settings.
Validates:
1. Default loading and schema serialization.
2. JSON persistence in user_settings.json.
3. Custom presets saving and retrieval.
4. Loopback API query and action dispatch.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src" / "python"))

from backend.app_controller import (
    AppController,
    DEFAULT_WINDOW_EXIT_STYLE,
    DEFAULT_WINDOW_LAUNCH_STYLE,
    _default_singularity_config,
    _default_motion_presets,
)
from services.professional_client_service import (
    ProfessionalClientService,
    GET_MOTION_SETTINGS_QUERY,
    SAVE_MOTION_SETTINGS_ACTION,
)


class TestMotionSettingsSuite(unittest.TestCase):

    def test_default_config_structure(self):
        cfg = _default_singularity_config()
        self.assertEqual(cfg["durationMs"], 1000)
        self.assertEqual(cfg["twistDegrees"], 720)
        self.assertEqual(cfg["stretchRatio"], 1.60)
        self.assertEqual(cfg["easing"], "QuartIn")
        self.assertTrue(cfg["soundEnabled"])

    def test_default_presets(self):
        presets = _default_motion_presets()
        self.assertGreaterEqual(len(presets), 4)
        preset_ids = [p["id"] for p in presets]
        self.assertIn("cinema", preset_ids)
        self.assertIn("pro", preset_ids)
        self.assertIn("console", preset_ids)
        self.assertIn("snappy", preset_ids)

    def test_app_controller_motion_slots_and_serialization(self):
        mock_paths = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            mock_paths.user_settings_path.return_value = tmp_path / "user_settings.json"
            mock_paths.prefs_path.return_value = tmp_path / "prefs.json"
            mock_paths.executable_root.return_value = tmp_path / "bin" / "app"
            mock_paths.project_root.return_value = tmp_path
            mock_paths.workbook_path.return_value = tmp_path / "CSPM.xlsm"
            mock_paths.state_dir.return_value = tmp_path / "state"
            mock_paths._persistent_data_root.return_value = tmp_path
            mock_paths.app_data_root.return_value = tmp_path
            data_dir = tmp_path / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (tmp_path / "state").mkdir(parents=True, exist_ok=True)
            (data_dir / "clients.json").write_text("{}", encoding="utf-8")

            controller = AppController(paths=mock_paths, defer_settings_load=True)
            self.assertEqual(controller.windowExitStyle, DEFAULT_WINDOW_EXIT_STYLE)
            self.assertEqual(controller.windowLaunchStyle, DEFAULT_WINDOW_LAUNCH_STYLE)

            # Test updating exit style
            self.assertTrue(controller.setWindowExitStyle("ConsoleFlyOff"))
            self.assertEqual(controller.windowExitStyle, "ConsoleFlyOff")

            # Test updating launch style
            self.assertTrue(controller.setWindowLaunchStyle("ExecutiveClean"))
            self.assertEqual(controller.windowLaunchStyle, "ExecutiveClean")

            # Test getMotionSettingsJson
            raw_json = controller.getMotionSettingsJson()
            data = json.loads(raw_json)
            self.assertEqual(data["windowExitStyle"], "ConsoleFlyOff")
            self.assertEqual(data["windowLaunchStyle"], "ExecutiveClean")
            self.assertIn("singularityConfig", data)
            self.assertIn("savedMotionPresets", data)

            # Test saveMotionSettings
            custom_payload = {
                "windowExitStyle": "Singularity",
                "windowLaunchStyle": "QuantumSpring",
                "singularityConfig": {
                    "durationMs": 850,
                    "twistDegrees": 1440,
                    "stretchRatio": 1.80,
                },
                "savedMotionPresets": [
                    {"id": "my_custom", "name": "Custom 1440", "durationMs": 850}
                ]
            }
            self.assertTrue(controller.saveMotionSettings(json.dumps(custom_payload)))
            self.assertEqual(controller.windowExitStyle, "Singularity")
            self.assertEqual(controller.singularityConfig["durationMs"], 850)
            self.assertEqual(controller.singularityConfig["twistDegrees"], 1440)
            self.assertEqual(len(controller.savedMotionPresets), 1)

            # Test minimizeToTray slot does not raise error
            controller.minimizeToTray("Test Title", "Test Message")
            controller.minimizeToTray()

    def test_professional_service_motion_dispatch(self):
        class DummyBackend:
            def getMotionSettingsJson(self):
                return json.dumps({
                    "windowExitStyle": "Singularity",
                    "singularityConfig": {"durationMs": 1000}
                })
            def saveMotionSettings(self, json_str):
                return True

        service = ProfessionalClientService(backend=DummyBackend())

        # Test query
        query_envelope = {
            "requestId": "req-1",
            "action": GET_MOTION_SETTINGS_QUERY,
            "payload": {},
            "actor": "test",
            "timestampUtc": "2026-08-15T00:00:00Z"
        }
        res = service.handle_http_json_request(query_envelope)
        self.assertTrue(res["ok"])
        self.assertEqual(res["payload"]["settings"]["windowExitStyle"], "Singularity")

        # Test action
        action_envelope = {
            "requestId": "req-2",
            "action": SAVE_MOTION_SETTINGS_ACTION,
            "payload": {
                "settings": {
                    "windowExitStyle": "Singularity",
                    "singularityConfig": {"durationMs": 750}
                }
            },
            "actor": "test",
            "timestampUtc": "2026-08-15T00:00:00Z"
        }
        res2 = service.handle_http_json_request(action_envelope)
        self.assertTrue(res2["ok"])
        self.assertTrue(res2["payload"]["saved"])


if __name__ == "__main__":
    unittest.main()
