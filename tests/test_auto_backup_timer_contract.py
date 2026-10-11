"""Disabled backup settings must never start an idle-loop snapshot timer."""
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.app_controller import AppController
from backend import native_candidate


@pytest.fixture
def controller_factory(tmp_path, monkeypatch):
    application = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setenv("CSPM_AUTOBACKUP_MINUTES", "15")
    controllers = []

    def create(*, saved_minutes=0, candidate=False, deferred=False):
        root = tmp_path / str(len(controllers))
        data = root / "working/data"
        data.mkdir(parents=True)
        (root / "state").mkdir()
        # No workbook is opened: these markers satisfy the isolated folder
        # boundary, while the repository path remains deliberately absent.
        (data / "CSPM.xlsm").write_bytes(b"")
        (data / "Dockets.xlsm").write_bytes(b"")
        settings = root / "user_settings.json"
        settings.write_text(json.dumps(dict(localDataDir=str(data), masterDataDir="",
            autoBackupMinutes=saved_minutes, autoBackupIntervalMins=0,
            runAtStartup=False, keepTrayAlive=False)))
        paths = MagicMock()
        paths.root = root
        paths.user_settings_path.return_value = settings
        paths.prefs_path.return_value = root / "prefs.json"
        paths.executable_root.return_value = root / "bin/app"
        paths.project_root.return_value = root
        paths.workbook_path.return_value = root / "missing-workbook.xlsm"
        paths.state_dir.return_value = root / "state"
        paths.runtime_dir.return_value = root / "working"
        paths._persistent_data_root.return_value = root
        paths.app_data_root.return_value = root
        paths.data_dir.return_value = data
        paths.master_data_dir.return_value = root
        monkeypatch.setattr(native_candidate, "_profile", root if candidate else None)
        controller = AppController(paths=paths, defer_settings_load=deferred)
        controller._create_project_snapshot = MagicMock(return_value=True)
        controllers.append(controller)
        return controller

    yield create
    for controller in controllers:
        controller._auto_backup_timer.stop()
    application.processEvents()


@pytest.mark.parametrize("candidate", [False, True])
@pytest.mark.parametrize("deferred", [False, True])
def test_saved_or_candidate_disabled_backup_never_starts_zero_timer(
        controller_factory, candidate, deferred):
    # The candidate overrides a persisted positive interval with zero.
    controller = controller_factory(saved_minutes=15 if candidate else 0,
                                    candidate=candidate, deferred=deferred)
    assert controller.autoBackupMinutes == 0
    assert controller.autoBackupEnabled is False
    assert not controller._auto_backup_timer.isActive()
    controller._auto_backup_timer.timeout.emit()  # A stale queued timeout.
    controller._run_startup_snapshot()           # A stale startup single-shot.
    controller._create_project_snapshot.assert_not_called()


@pytest.mark.parametrize("minutes", [5, 15])
def test_positive_saved_interval_keeps_one_connected_backup_callback(controller_factory, minutes):
    controller = controller_factory(saved_minutes=minutes)
    assert controller.autoBackupEnabled is True
    assert controller._auto_backup_timer.isActive()
    assert controller._auto_backup_timer.interval() == minutes * 60 * 1000
    controller._auto_backup_timer.timeout.emit()
    controller._create_project_snapshot.assert_called_once_with(
        "scheduled-auto-backup", emit_toast=False)


def test_initially_disabled_backup_can_be_reenabled_then_disabled(controller_factory, monkeypatch):
    monkeypatch.setenv("CSPM_AUTOBACKUP_MINUTES", "0")
    controller = controller_factory(saved_minutes=0)
    controller.autoBackupMinutes = 5
    assert controller.autoBackupEnabled is True
    assert controller._auto_backup_timer.isActive()
    assert controller._auto_backup_timer.interval() == 300000
    controller._auto_backup_timer.timeout.emit()
    controller._create_project_snapshot.assert_called_once_with(
        "scheduled-auto-backup", emit_toast=False)
    controller.autoBackupMinutes = 0
    assert controller.autoBackupEnabled is False
    assert not controller._auto_backup_timer.isActive()
    controller._auto_backup_timer.timeout.emit()
    controller._run_startup_snapshot()
    assert controller._create_project_snapshot.call_count == 1
