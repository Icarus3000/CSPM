"""Regression coverage for the hidden first-workspace startup gate."""

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QCoreApplication


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src" / "python"))

from backend.app_controller import AppController


class TestStartupBriefingReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QCoreApplication.instance() or QCoreApplication([])

    def _controller(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (root / "state").mkdir(parents=True, exist_ok=True)

        paths = MagicMock()
        paths.user_settings_path.return_value = root / "user_settings.json"
        paths.prefs_path.return_value = root / "prefs.json"
        paths.executable_root.return_value = root / "bin" / "app"
        paths.project_root.return_value = root
        paths.root = root
        paths.workbook_path.return_value = root / "missing-workbook.xlsm"
        paths.state_dir.return_value = root / "state"
        paths._persistent_data_root.return_value = root
        paths.app_data_root.return_value = root
        paths.data_dir.return_value = data_dir
        paths.master_data_dir.return_value = root

        controller = AppController(paths=paths, defer_settings_load=True)
        controller._settings_load_complete = True
        controller._is_booted = True
        controller._excel_repo = MagicMock()

        def run_inline(fn, *, on_result=None, on_error=None, **_kwargs):
            try:
                result = fn()
            except Exception as exc:  # mirrors Worker.error's error tuple shape
                if on_error:
                    on_error((type(exc), exc, None))
                return
            if on_result:
                on_result(result)

        controller._start_background_worker = run_inline
        return controller

    def test_snapshot_must_be_bound_before_ready_to_reveal(self):
        controller = self._controller()
        payload = {
            "ok": True,
            "asOfDate": "2026-08-17",
            "todaysTasks": [{"id": "task-1"}],
            "summary": {"activeClientCount": 1},
        }
        controller._excel_repo.practice_briefing.return_value = payload

        controller.prepareStartupPracticeBriefing()

        self.assertEqual(controller.startupReadinessState, "briefing-snapshot-ready")
        self.assertTrue(controller.startupBriefingSnapshotReady)
        self.assertEqual(controller.startupBriefingSnapshot, payload)
        self.assertFalse(controller.startupReadyToReveal)

        controller.markStartupBriefingFrameReady()

        self.assertTrue(controller.startupReadyToReveal)
        self.assertEqual(controller.startupReadinessProgress, 1.0)

    def test_invalid_snapshot_holds_startup_in_failed_state(self):
        controller = self._controller()
        controller._excel_repo.practice_briefing.return_value = {"ok": False}
        failures = []
        controller.startupReadinessFailed.connect(failures.append)

        controller.prepareStartupPracticeBriefing()

        self.assertEqual(controller.startupReadinessState, "failed")
        self.assertFalse(controller.startupReadyToReveal)
        self.assertTrue(failures)

    def test_professional_landing_home_consumes_the_prepared_snapshot(self):
        """The visible Daily Operations home must not reintroduce zero cards."""
        home_qml = (ROOT_DIR / "src" / "qml" / "components" / "DailyOperationsHome.qml").read_text(
            encoding="utf-8"
        )
        main_content_qml = (ROOT_DIR / "src" / "qml" / "views" / "MainContent.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("function applyPreparedStartupBriefing()", home_qml)
        self.assertIn("function onStartupBriefingSnapshotChanged()", home_qml)
        self.assertIn("if (!root.startupReadinessBlocksDirectLoad()) initialBriefingTimer.start()", home_qml)
        self.assertIn("id: dailyOperationsHome", main_content_qml)
        self.assertIn("var homePrepared = dailyOperationsHome.applyPreparedStartupBriefing() === true", main_content_qml)
        self.assertIn("return briefingPrepared && homePrepared", main_content_qml)

    def test_metadata_warm_waits_for_the_hidden_snapshot_handoff(self):
        controller = self._controller()
        controller._startup_briefing_preparation_started = True
        controller._startup_readiness_state = "workbook-booting"
        controller._on_boot_complete(time.perf_counter())

        self.assertTrue(controller._startup_metadata_warm_deferred_for_reveal)
        self.assertFalse(controller._startup_metadata_warm_scheduled)

        controller._startup_readiness_state = "briefing-snapshot-ready"
        controller._startup_briefing_snapshot = {"ok": True}
        controller._startup_metadata_warm_deferred_for_reveal = True
        controller._queue_startup_metadata_warm = MagicMock()
        controller.markStartupBriefingFrameReady()

        self.assertTrue(controller.startupReadyToReveal)
        controller._queue_startup_metadata_warm.assert_called_once_with()

    def test_all_user_input_refreshes_the_background_idle_deadline(self):
        controller = self._controller()
        controller.markStartupUserActivity("mouse-press")
        first_activity = controller.startupUserActivityEpochMs

        time.sleep(0.002)
        controller.markStartupUserActivity("key-press")

        self.assertTrue(controller.startupFirstInputSeen)
        self.assertGreater(controller.startupUserActivityEpochMs, first_activity)

    def test_startup_queue_defers_unopened_workspaces_and_honors_user_idle(self):
        main_py = (ROOT_DIR / "src" / "python" / "main.py").read_text(encoding="utf-8")
        config_py = (ROOT_DIR / "src" / "python" / "backend" / "runtime_config.py").read_text(
            encoding="utf-8"
        )
        shell_qml = (ROOT_DIR / "src" / "qml" / "DetachedShellWindow.qml").read_text(
            encoding="utf-8"
        )
        bridge_js = (ROOT_DIR / "src" / "qml" / "standards" / "StartupQueueBridge.js").read_text(
            encoding="utf-8"
        )
        main_content_qml = (ROOT_DIR / "src" / "qml" / "views" / "MainContent.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn('"CSPM_STARTUP_DEFERRED_QUEUE_MODE", "on"', main_py)
        self.assertIn("startup_background_idle_ms", main_py)
        self.assertIn("_startup_input_notify_callback = controller.markStartupUserActivity", main_py)
        self.assertIn("def markStartupUserActivity", (ROOT_DIR / "src" / "python" / "backend" / "app_controller.py").read_text(encoding="utf-8"))
        self.assertIn("def startupBackgroundIdleMs", config_py)
        self.assertIn("property bool startupWorkspacePrewarmEnabled: false", main_content_qml)
        self.assertIn("if (!startupWorkspacePrewarmEnabled) return", main_content_qml)
        self.assertIn("property double startupLastUserActivityEpochMs", shell_qml)
        self.assertIn("function onStartupUserActivityChanged()", shell_qml)
        self.assertIn('"recent-user-input"', bridge_js)
        self.assertIn("startupBackgroundIdleMs", bridge_js)
        self.assertIn("pauseDelayMs", bridge_js)

    def test_phase_two_keeps_the_native_acts_ahead_of_the_qml_bloom(self):
        """The 100% handoff must never let the main window overlap the splash."""
        main_py = (ROOT_DIR / "src" / "python" / "main.py").read_text(encoding="utf-8")
        bootstrap_qml = (ROOT_DIR / "src" / "qml" / "BootstrapRoot.qml").read_text(
            encoding="utf-8"
        )
        shell_qml = (ROOT_DIR / "src" / "qml" / "DetachedShellWindow.qml").read_text(
            encoding="utf-8"
        )
        main_content_qml = (ROOT_DIR / "src" / "qml" / "views" / "MainContent.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("controller.startupReadinessChanged.connect(_sync_native_splash_readiness_progress)", main_py)
        self.assertIn("cinematicBloomPrestageRequested = QtCore.Signal()", main_py)
        self.assertIn("def confirm_cinematic_bloom_prestaged", main_py)
        self.assertIn("Qt.WindowStaysOnTopHint", main_py)
        self.assertIn("class CustomSplash(QWidget)", main_py)
        self.assertIn("self.setAttribute(Qt.WA_NoSystemBackground)", main_py)
        self.assertIn("_begin_fade_in_after_first_paint", main_py)
        self.assertIn("radius = 76.0 * self._plasma_scale", main_py)
        self.assertIn("_ACT_I_VORTEX_MS = 550", main_py)
        self.assertIn("_ACT_II_HOLD_MS = 80", main_py)
        self.assertIn("_ACT_II_IMPLODE_MS = 220", main_py)
        self.assertIn("self.hide()", main_py)
        self.assertIn("self.cinematicRevealReady.emit", main_py)
        self.assertIn("def show_first_frame(self) -> None:", main_py)
        self.assertIn("Native CS splash first frame primed", main_py)
        self.assertIn("custom_splash.show_first_frame()", main_py)
        self.assertIn("leaving the splash at 0% forever", main_py)
        self.assertNotIn("custom_splash.anim_in.finished.connect", main_py)
        launch_block_start = main_py.index("if not is_tray_only:")
        tray_load_start = main_py.index("tray_url = QUrl.fromLocalFile", launch_block_start)
        launch_block = main_py[launch_block_start:tray_load_start]
        self.assertIn("load_main_window()", launch_block)
        self.assertLess(
            launch_block.index("load_main_window()"),
            main_py.index("tray_url = QUrl.fromLocalFile", launch_block_start),
        )
        self.assertIn("def _request_skip(self) -> None:", main_py)
        self.assertIn(
            'if self._cinematic_mode not in {"completing-bar", "vortex", "plasma"}:',
            main_py,
        )
        self.assertIn(
            "It must not be remembered and then erase the visible CS spin/shrink",
            main_py,
        )
        self.assertNotIn("self._skip_requested", main_py)
        self.assertIn("signal cinematicRevealRequested()", bootstrap_qml)
        self.assertIn("signal cinematicBloomPrestageComplete()", bootstrap_qml)
        self.assertIn("function prestageCinematicBloom()", bootstrap_qml)
        self.assertIn("function releaseCinematicLaunchGate()", bootstrap_qml)
        prestage_start = bootstrap_qml.index("function prestageCinematicBloom()")
        handoff_start = bootstrap_qml.index("function releaseCinematicLaunchGate()")
        prestage_function = bootstrap_qml[prestage_start:handoff_start]
        self.assertIn(
            "Phase 2 prestaging QML pinpoint while native splash retains focus",
            prestage_function,
        )
        self.assertIn("startupCinematicBloomPrestageOnly = true", prestage_function)
        self.assertIn('_openLaunchGate("phase2-native-prestage")', prestage_function)
        self.assertIn(
            "Phase 2 QML pinpoint ready; holding native splash focus until plasma handoff",
            bootstrap_qml,
        )
        focus_hold_index = bootstrap_qml.index(
            "Phase 2 QML pinpoint ready; holding native splash focus until plasma handoff"
        )
        focus_request_index = bootstrap_qml.index("windowRef.forceLaunchFocus()")
        self.assertLess(focus_hold_index, focus_request_index)
        self.assertIn("function _scheduleHiddenWindowPreloadAfterSnapshot(reason)", bootstrap_qml)
        self.assertIn("function _beginHiddenWindowPreloadAfterSnapshot()", bootstrap_qml)
        self.assertIn(
            "Phase 1 snapshot complete; serializing hidden shell preload",
            bootstrap_qml,
        )
        self.assertIn(
            "_scheduleHiddenWindowPreloadAfterSnapshot(\"controller-readiness-changed\")",
            bootstrap_qml,
        )
        self.assertIn("property bool startupCinematicBloomActive", shell_qml)
        self.assertIn("function prepareStartupCinematicGeometry()", shell_qml)
        self.assertIn("signal startupCinematicBloomStaged()", shell_qml)
        self.assertIn("function releaseStartupCinematicBloom()", shell_qml)
        self.assertIn("property bool startupCinematicBloomReleaseStarted", shell_qml)
        self.assertIn("property bool startupCinematicSnapshotActive", shell_qml)
        self.assertIn("property int startupCinematicSnapshotFallbackMs: 6000", shell_qml)
        self.assertIn("id: startupCinematicSnapshotFallbackTimer", shell_qml)
        self.assertIn("Act III snapshot capture timed out; using live bloom fallback", shell_qml)
        self.assertIn("function prestageStartupCinematicBloom()", shell_qml)
        self.assertIn("id: startupCinematicBloomSnapshot", shell_qml)
        self.assertIn("!mainWin.startupCinematicBloomPrestageOnly", shell_qml)
        self.assertIn("hidden final window geometry prepared during native splash", shell_qml)
        self.assertIn("duration: 400", shell_qml)
        self.assertIn("function cancelAsyncStartupWork(reason)", main_content_qml)
        self.assertIn("active: !root.shutdownRequested", main_content_qml)


if __name__ == "__main__":
    unittest.main()
