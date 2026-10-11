"""Command identity and orderly service teardown without opening a GUI."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import sys
import threading
import subprocess

import pytest
from PySide6.QtCore import QCoreApplication, QThreadPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.app_controller import AppController
from backend.controllers import tray_controller as tray_module
from backend.controllers.tray_controller import TrayController
from backend.workers import Worker


@pytest.fixture
def tray(monkeypatch):
    qt = QCoreApplication.instance() or QCoreApplication([])
    window = MagicMock()
    window.objectName.return_value = "CSPMMainWindow"
    window.isVisible.return_value = False
    app = SimpleNamespace(topLevelWindows=lambda: [window], _tray_icon=MagicMock(),
                          _tray_menu=MagicMock())
    backend = SimpleNamespace(_theme_name="Light", forceWindowForeground=MagicMock())
    monkeypatch.setattr(tray_module, "QApplication", SimpleNamespace(instance=lambda: app))
    controller = TrayController(backend)
    yield controller, app, window, backend
    controller._timer.stop()
    controller._exit_failsafe_timer.stop()
    qt.processEvents()


def test_pending_restore_is_one_transaction_and_later_hidden_restore_is_distinct(tray):
    controller, app, window, backend = tray
    revisions = []
    controller.requestRestoreFromTray.connect(revisions.append)
    controller.open_cspm()
    controller.open_cspm()  # Double-click/menu command while native host still hidden.
    assert revisions == [1]
    controller.completeRestoreFromTray(999)  # A stale acknowledgment cannot unlock it.
    controller.open_cspm()
    assert revisions == [1]
    window.isVisible.return_value = True
    controller.completeRestoreFromTray(1)
    controller.open_cspm()
    backend.forceWindowForeground.assert_called_once_with(window)
    assert revisions == [1]
    window.isVisible.return_value = False  # A later explicit minimize-to-tray.
    controller.open_cspm()
    controller.open_cspm()
    assert revisions == [1, 2]
    controller.completeRestoreFromTray(1)
    assert controller._pending_restore_revision == 2
    controller.completeRestoreFromTray(2)
    assert controller._pending_restore_revision == 0
    assert controller._timer.isActive()
    app._tray_icon.hide.assert_not_called()


def test_full_exit_intent_does_not_interrupt_close_animation_and_shutdown_releases_once(tray):
    controller, app, window, backend = tray
    icon, menu = app._tray_icon, app._tray_menu
    save = MagicMock()
    controller.force_shutdown_save = save
    controller.open_cspm()
    controller.requestApplicationExit("title-bar-close")
    assert app._tray_exit_requested
    assert controller._pending_restore_revision == 0
    assert controller._timer.isActive()  # Animation still owns its normal completion.
    icon.hide.assert_not_called()
    controller.shutdown()
    controller.shutdown()
    assert not controller._timer.isActive()
    assert not controller._exit_failsafe_timer.isActive()
    save.assert_called_once()
    icon.hide.assert_called_once()
    icon.setContextMenu.assert_called_once_with(None)
    icon.deleteLater.assert_called_once()
    menu.close.assert_called_once()
    assert app._tray_icon is None and app._tray_menu is None
    revision = controller._restore_revision
    controller.open_cspm()
    assert controller._restore_revision == revision


def test_tray_exit_emits_once_and_owned_failsafe_stops_on_shutdown(tray):
    controller, app, window, backend = tray
    requests = []
    controller.requestExitFromTray.connect(lambda: requests.append("exit"))
    controller.exit_cspm()
    controller.exit_cspm()
    assert requests == ["exit"]
    assert app._tray_exit_requested
    assert controller._exit_failsafe_timer.isActive()
    controller.shutdown()
    assert not controller._exit_failsafe_timer.isActive()


def test_backend_shutdown_finishes_accepted_writes_before_publish_and_blocks_stale_work(monkeypatch):
    QCoreApplication.instance() or QCoreApplication([])
    events = []
    private_pool = MagicMock()
    private_pool.clear.side_effect = lambda: events.append("private-queued-cleared")
    private_pool.waitForDone.side_effect = lambda: events.append("private-active-finished")
    global_pool = QThreadPool()
    saved = threading.Event()
    def write():
        events.append("accepted-write-finished")
        saved.set()
    global_pool.start(Worker(write))
    monkeypatch.setattr(QThreadPool, "globalInstance", lambda: global_pool)
    service = MagicMock()
    def publish():
        assert saved.is_set()
        events.append("publish")
        return {"ok": True}
    service.push_to_master.side_effect = publish
    controller = SimpleNamespace(
        _shutdown_sync_complete=False, _shutting_down=False,
        _auto_backup_timer=MagicMock(), _startup_briefing_process_poll_timer=MagicMock(),
        cancelStartupPracticeBriefingProcess=MagicMock(), cancelLegacyDocketsImport=MagicMock(),
        _background_pool=private_pool, _background_workers={1: object()}, _sync_service=service,
        _auto_backup_enabled=True, _create_project_snapshot=MagicMock(),
    )
    AppController.shutdown(controller)
    AppController.shutdown(controller)
    assert controller._shutting_down
    assert controller._background_workers == {}
    assert events.index("private-active-finished") < events.index("publish")
    assert events.index("accepted-write-finished") < events.index("publish")
    service.push_to_master.assert_called_once()
    controller._auto_backup_timer.stop.assert_called_once()
    controller.cancelStartupPracticeBriefingProcess.assert_called_once()
    controller.cancelLegacyDocketsImport.assert_called_once()
    AppController._run_auto_backup_tick(controller)
    AppController._run_startup_snapshot(controller)
    AppController._start_background_worker(controller, MagicMock(), name="stale")
    controller._create_project_snapshot.assert_not_called()
    private_pool.start.assert_not_called()


def test_startup_helper_is_reaped_before_removing_its_workspace():
    process = MagicMock()
    process.poll.return_value = None
    state = {"process": process}
    controller = SimpleNamespace(_startup_briefing_process_state=state,
                                 _finish_startup_briefing_process=MagicMock())
    AppController.cancelStartupPracticeBriefingProcess(controller)
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=2)
    process.kill.assert_not_called()
    controller._finish_startup_briefing_process.assert_called_once_with(state)


def test_unresponsive_startup_helper_has_bounded_task_owned_termination():
    process = MagicMock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("briefing", 2), 0]
    state = {"process": process}
    controller = SimpleNamespace(_startup_briefing_process_state=state,
                                 _finish_startup_briefing_process=MagicMock())
    AppController.cancelStartupPracticeBriefingProcess(controller)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    controller._finish_startup_briefing_process.assert_called_once_with(state)
