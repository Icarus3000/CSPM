"""Focused Windows desktop lifecycle checks with an externally prepared read-only profile.

Uses the real source entry point and QML, approved data supplied by the caller,
and no cursor movement. It never copies, migrates, or saves a workbook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--engine", choices=("native", "legacy", "reduced"), default="native")
    parser.add_argument("--exit", choices=("x", "tray"), default="x")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--baseline", action="store_true")
    return parser.parse_args()


options = arguments()
repo = options.repo.resolve()
profile = options.profile.resolve()
settings = json.loads((profile / "user_settings.json").read_text(encoding="utf-8"))
assert settings.get("readOnlyVerification") is True
settings["mainWindowLayout"] = dict(maximized=False, hasExactRect=True,
                                  x=120, y=85, width=1200, height=706)
(profile / "user_settings.json").write_text(json.dumps(settings), encoding="utf-8")
data = Path(settings["localDataDir"]).resolve()
before = {name: hashlib.sha256((data / name).read_bytes()).hexdigest().upper()
          for name in ("CSPM.xlsm", "Dockets.xlsm")}
for name in ("local", "roaming", "temp", "logs", "exports"):
    (profile / name).mkdir(exist_ok=True)
previous_log = profile / "logs" / "cspm.log"
if previous_log.exists():
    previous_log.rename(previous_log.with_name("cspm.previous-" + uuid.uuid4().hex + ".log"))
for key in list(os.environ):
    if key.startswith(("CSPM_", "QT_", "QSG_", "QML_", "QTWEBENGINE")):
        os.environ.pop(key, None)
os.environ.update(CSPM_RUNTIME_DIR=str(profile), CSPM_DATA_DIR=str(profile),
                  CSPM_EXECUTABLE_ROOT=str(profile), CSPM_LOG_DIR=str(profile / "logs"),
                  CSPM_EXPORT_DIR=str(profile / "exports"),
                  CSPM_MACHINE_ID_FILE=str(profile / "machine.json"),
                  LOCALAPPDATA=str(profile / "local"), APPDATA=str(profile / "roaming"),
                  TEMP=str(profile / "temp"), TMP=str(profile / "temp"),
                  CSPM_VERIFY_DATA_READ_ONLY="1", PYTHONDONTWRITEBYTECODE="1")
if options.engine == "reduced":
    os.environ["CSPM_LOW_PERF"] = "1"
(profile / "local" / "CSPM-Motion").mkdir(exist_ok=True)
(profile / "local" / "CSPM-Motion" / "motion.json").write_text(
    json.dumps({"engine": options.engine}), encoding="utf-8")
sys.path.insert(0, str(repo / "src" / "python"))
import platform
platform.__path__ = [str(repo / "src" / "python" / "platform")]
sys.argv = [str(repo / "src" / "python" / "main.py"), "--verify-data-read-only"]
import main as entry
from PySide6.QtCore import QObject, QTimer
from PySide6.QtQml import QQmlEngine
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

# Baseline-only observation must also have a fail-closed write boundary, even
# when the old executable predates the supported verification option.
if options.baseline:
    from services.sync_service import SyncService
    from repositories.excel_repo import ExcelRepo
    def deny(*_):
        raise PermissionError("Lifecycle baseline is read-only")
    SyncService.assert_write_lease = deny
    SyncService.pull_from_master = lambda self: {"ok": True, "status": "verification-read-only"}
    SyncService.publish_and_release = lambda self: {"ok": True, "status": "verification-read-only"}
    ExcelRepo._assert_write_permitted = deny

report = {"checks": [], "failures": [], "engine": options.engine,
          "exit": options.exit, "baseline": options.baseline, "beforeHashes": before,
          "restoreCompletions": 0, "closeCompletions": 0, "exitCompletions": 0,
          "restoresWhileHidden": 0, "sourceQtDesktop": True}


class LifecycleApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.started = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.stage = "startup"
        self.deadline = self.started + 120
        self.window = None
        self.cycle = 0
        self.tray_cycle = 0
        self.aboutToQuit.connect(self.completed)

    def js(self, code):
        result = self.engine.evaluate(code)
        if result.isError():
            raise RuntimeError(result.toString())
        return result

    def snapshot(self):
        return json.loads(self.js("JSON.stringify({visible:_p.visible, minimized:_p.visibility===3, "
            "restoring:_p.isRestoringFromMinimize,minimizing:_p.isMinimizing,"
            "maximizing:_p.maximizeAnimInProgress||_p.professionalWindowTransitionActive||_p.nativeMotionPreparing,maximized:_p.uiMaximized,"
            "startupBloom:_p.startupCinematicBloomActive,"
            "rect:[_p.finalX,_p.finalY,_p.finalW,_p.finalH],"
            "revision:_p.trayRestoreRevision === undefined ? 0 : _p.trayRestoreRevision})").toString())

    def advance(self, stage, deadline=20):
        self.stage = stage
        self.deadline = time.monotonic() + deadline
        print("LIFECYCLE STAGE " + stage, flush=True)

    def restore_finished(self):
        report["restoreCompletions"] += 1
        if not self.window.isVisible():
            report["restoresWhileHidden"] += 1

    def tray_restore(self):
        self.restore_before = report["restoreCompletions"]
        self.tray = self._tray_controller
        self._tray_icon.activated.emit(QSystemTrayIcon.Trigger)
        self._tray_icon.activated.emit(QSystemTrayIcon.DoubleClick)
        self.tray.open_cspm()
        self.tray.open_cspm()
        self.advance("tray-return")

    def tick(self):
        try:
            if time.monotonic() > self.deadline:
                raise TimeoutError("Lifecycle stage timeout: " + self.stage)
            if self.stage == "startup":
                found = [w for w in self.topLevelWindows() if w.objectName() == "CSPMMainWindow"]
                if not found or found[0].property("startupPhase") != "post-settle-ready":
                    return
                self.window = found[0]
                self.engine = QQmlEngine.contextForObject(self.window).engine()
                self.engine.globalObject().setProperty("_p", self.engine.newQObject(self.window))
                self.jelly = next(obj for obj in self.window.findChildren(QObject)
                                  if obj.property("closeProgress") is not None
                                  and obj.property("minimizeProgress") is not None)
                self.jelly.restoreFinished.connect(self.restore_finished)
                self.jelly.closeFinished.connect(lambda: report.__setitem__("closeCompletions", report["closeCompletions"] + 1))
                self.jelly.exitFromTrayFinished.connect(lambda: report.__setitem__("exitCompletions", report["exitCompletions"] + 1))
                self.initial = self.snapshot()["rect"]
                self.advance("opening-settled")
                return
            state = self.snapshot()
            if self.stage == "opening-settled":
                if state["startupBloom"] or not state["visible"] or not hasattr(self, "_tray_controller"):
                    return
                report["checks"].append("startup, opening and native tray ready")
                controller = self.window.property("appRef")
                from repositories.excel_repo import TBL_CLIENTS, TBL_MATTERS, TBL_TIME, TBL_INVOICE_LOG, TBL_RECEIVABLES
                refs = [TBL_CLIENTS, TBL_MATTERS, TBL_TIME, TBL_INVOICE_LOG, TBL_RECEIVABLES]
                tables = controller._excel_repo._read_table_rows_bulk(refs)
                report["datasetPopulation"] = {ref.table: len(tables.get(ref.table, [])) for ref in refs}
                if options.cycles:
                    self.js("_p.toggleWindowMaximize()")
                    self.advance("maximize")
                else:
                    self.js("_p.requestMinimizeToTrayAnimation()")
                    self.advance("tray-hidden")
            elif self.stage == "maximize":
                if state["maximizing"] or not state["maximized"]:
                    return
                self.js("_p.toggleWindowMaximize()")
                self.advance("restore-maximize")
            elif self.stage == "restore-maximize":
                if state["maximizing"] or state["maximized"]:
                    return
                assert state["rect"] == self.initial, "Restored geometry changed"
                self.cycle += 1
                if self.cycle < options.cycles:
                    self.js("_p.toggleWindowMaximize()")
                    self.advance("maximize")
                else:
                    report["checks"].append(f"{self.cycle} maximize/restore pairs; exact restored geometry")
                    self.js("_p.requestMinimizeAnimation()")
                    self.advance("taskbar-hidden")
            elif self.stage == "taskbar-hidden":
                if not state["minimized"]:
                    return
                self.window.showNormal()
                self.advance("taskbar-return")
            elif self.stage == "taskbar-return":
                if state["restoring"] or not state["visible"] or state["minimized"]:
                    return
                report["checks"].append("taskbar minimize/return")
                self.hide_restore_before = report["restoreCompletions"]
                self.js("_p.requestMinimizeToTrayAnimation()")
                self.advance("tray-hidden")
            elif self.stage == "tray-hidden":
                if state["visible"] or state["minimizing"]:
                    return
                assert self._tray_icon.isVisible(), "Explicit tray minimize removed icon"
                # Observe hidden visibility churn before sending a new command.
                self.hidden_at = time.monotonic()
                self.advance("hidden-stable")
            elif self.stage == "hidden-stable":
                if time.monotonic() - self.hidden_at < 1.2:
                    return
                if not options.baseline:
                    assert report["restoresWhileHidden"] == 0, "Tray hide incorrectly restored"
                report["checks"].append("explicit tray minimize retains process/icon")
                self.tray_restore()
            elif self.stage == "tray-return":
                if state["restoring"] or not state["visible"]:
                    return
                assert report["restoreCompletions"] - self.restore_before == 1, "Duplicate tray restore completion"
                assert self.window.isVisible()
                assert self.js("_p.contentLayerRef.enabled").toBool(), "Live input disabled"
                self.window.requestActivate()
                self.tray_cycle += 1
                report["checks"].append("tray return once with repeated requests and Trigger/DoubleClick")
                if self.tray_cycle < 3:
                    self.js("_p.requestMinimizeToTrayAnimation()")
                    self.advance("tray-hidden")
                else:
                    report["dataStatus"] = self.js("_p.appRef.dataSourceStatusLabel").toString()
                    report["checks"].append("input enabled after tray return")
                    if options.exit == "tray":
                        self.js("_p.requestMinimizeToTrayAnimation()")
                        self.advance("exit-tray-hidden")
                    else:
                        self.advance("closing")
                        self.window.close()
                        self.window.close()
            elif self.stage == "exit-tray-hidden":
                if state["visible"] or state["minimizing"]:
                    return
                self.advance("closing")
                self._tray_controller.exit_cspm()
            elif self.stage == "closing":
                if options.baseline and not state["visible"]:
                    report["closeRetainedTray"] = self._tray_icon.isVisible()
                    self.quit()
        except Exception as exc:
            report["failures"].append(repr(exc))
            self.quit()

    def completed(self):
        report["finalStage"] = self.stage
        self.timer.stop()
        report["trayVisibleAtShutdown"] = bool(getattr(self, "_tray_icon", None) and self._tray_icon.isVisible())
        report["elapsedSeconds"] = round(time.monotonic() - self.started, 3)


entry.QApplication = LifecycleApplication
try:
    entry.main()
except SystemExit as exc:
    report["processExitCode"] = exc.code
    if exc.code not in (0, None):
        report["failures"].append("Application event loop returned " + str(exc.code))
runtime_app = QApplication.instance()
tray_icon = getattr(runtime_app, "_tray_icon", None)
report["trayVisibleAtShutdown"] = bool(tray_icon and tray_icon.isVisible())
report["afterHashes"] = {name: hashlib.sha256((data / name).read_bytes()).hexdigest().upper() for name in before}
runtime_log = (profile / "logs" / "cspm.log").read_text(encoding="utf-8", errors="replace")
report["motionOutcomes"] = [line.split("motion direction=", 1)[1] for line in runtime_log.splitlines()
                            if "motion direction=" in line]
report["trayTransactions"] = [line.split("[TRAY-TRANSACTION]", 1)[1].strip() for line in runtime_log.splitlines()
                              if "[TRAY-TRANSACTION]" in line]
if report["afterHashes"] != before:
    report["failures"].append("Workbook hash changed")
if not options.baseline:
    if report.get("finalStage") != "closing":
        report["failures"].append("Normal exit sequence incomplete")
    if report.get("trayVisibleAtShutdown"):
        report["failures"].append("Tray icon retained at shutdown")
    expected = "closeCompletions" if options.exit == "x" else "exitCompletions"
    if report[expected] != 1:
        report["failures"].append("Expected exactly one exit animation completion")
report["ok"] = not report["failures"]
(profile / "lifecycle-result.private.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({key: report.get(key) for key in ("ok", "checks", "failures", "restoreCompletions", "closeCompletions", "restoresWhileHidden", "trayVisibleAtShutdown", "elapsedSeconds")}))
raise SystemExit(not report["ok"])
