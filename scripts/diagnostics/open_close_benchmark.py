"""Observe unchanged Professional opening/closing on isolated copied data.

Records GUI-delivered submitted-frame notifications, not physical scanout.
No QML source changes, captures, financial commands, or maximize commands.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--audit-label", default="open_close_benchmark_" + time.strftime("%Y%m%d_%H%M%S"))
args = parser.parse_args()
if not args.audit_label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.audit_label):
    parser.error("audit label must contain letters, digits, underscores or hyphens")
ROOT = args.source_root.resolve()
AUDIT = Path(__file__).resolve().parents[2] / "logs" / args.audit_label
AUDIT.mkdir(parents=True, exist_ok=False)
PROFILE = AUDIT / "disposable_profile"
original = Path(os.environ["LOCALAPPDATA"]) / "CSPM"
protected = [original / "user_settings.json", *(original / "data" / n for n in ("CSPM.xlsm", "Dockets.xlsm"))]
def hashes():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before_hashes = hashes()
for directory in ("local", "master"):
    target = PROFILE / directory
    target.mkdir(parents=True)
    for name in ("CSPM.xlsm", "Dockets.xlsm"):
        shutil.copy2(original / "data" / name, target / name)
settings = json.loads(protected[0].read_text(encoding="utf-8"))
settings.update(appStyle="Professional", masterDataDir=str(PROFILE / "master"), localDataDir=str(PROFILE / "local"),
                keepTrayAlive=False, runAtStartup=False, soundEffectsEnabled=False,
                mainWindowLayout={"maximized": False, "hasExactRect": True, "x": 320, "y": 140,
                                  "width": 1100, "height": 760, "workAreaX": 0, "workAreaY": 0,
                                  "workAreaWidth": 1920, "workAreaHeight": 1040})
(PROFILE / "user_settings.json").write_text(json.dumps(settings), encoding="utf-8")
for key, value in {"CSPM_RUNTIME_DIR": PROFILE, "CSPM_DATA_DIR": PROFILE, "CSPM_LOG_DIR": AUDIT / "runtime",
                   "CSPM_MACHINE_ID_FILE": PROFILE / "machine_id.json"}.items():
    os.environ[key] = str(value)
sys.path.insert(0, str(ROOT / "src/python"))
import platform as diagnostic_platform
diagnostic_platform.__path__ = [str(ROOT / "src/python/platform")]
import main as entry
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
from PySide6.QtWidgets import QApplication

rows, events, failures = [], [], []
user32 = ctypes.windll.user32
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

class BenchmarkApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.started = time.perf_counter()
        self.window = self.jelly = None
        self.close_sent = False
        self.finished = False
        self.scan = QTimer(self)
        self.scan.setInterval(10)
        self.scan.timeout.connect(self.discover)
        self.scan.start()
        QTimer.singleShot(120000, self.timeout)

    def record_event(self, name):
        events.append({"t": time.perf_counter(), "name": name})

    def discover(self):
        if self.window is None:
            windows = [w for w in self.topLevelWindows() if w.objectName() == "CSPMMainWindow"]
            if not windows:
                return
            self.window = windows[0]
            self.engine = QQmlEngine.contextForObject(self.window).engine()
            self.engine.globalObject().setProperty("_benchmarkWindow", self.engine.newQObject(self.window))
            self.jelly = next((o for o in self.window.findChildren(QObject) if o.metaObject().indexOfProperty("closeProgress") >= 0), None)
            if self.jelly is None:
                failures.append("Jelly controller not discovered")
            self.window.frameSwapped.connect(self.frame, Qt.QueuedConnection)
            for prop in ("startupCinematicBloomReleaseStarted", "startupCinematicBloomActive", "startupCinematicSnapshotActive", "startupPhase", "isClosing", "visible"):
                getattr(self.window, prop + "Changed").connect(lambda *_, p=prop: self.record_event(p + "=" + str(self.window.property(p))))
            if self.jelly:
                self.jelly.closeFinished.connect(lambda: self.record_event("closeFinished"))
            self.record_event("window-discovered")
        if not self.close_sent and self.window.property("startupPhase") == "post-settle-ready" and not self.window.property("startupCinematicBloomActive"):
            self.close_sent = True
            QTimer.singleShot(2000, self.close_window)

    def frame(self):
        w = self.window
        rect = wintypes.RECT()
        user32.GetWindowRect(int(w.winId()), ctypes.byref(rect))
        row = {"t": time.perf_counter(), "visible": w.isVisible(), "bloom": w.property("startupCinematicBloomActive"),
               "bloomScale": w.property("startupCinematicBloomScale"), "snapshot": w.property("startupCinematicSnapshotActive"),
               "phase": w.property("startupPhase"), "closing": w.property("isClosing"),
               "nativeRect": [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top],
               "finalRect": [w.property(p) for p in ("finalX", "finalY", "finalW", "finalH")], "dpr": w.devicePixelRatio()}
        if self.jelly:
            row.update({p: self.jelly.property(p) for p in ("closeProgress", "scaleX", "scaleY", "transX", "transY", "opacityVal")})
        rows.append(row)

    def close_window(self):
        self.record_event("close-command")
        self.window.close()
        QTimer.singleShot(2500, self.finish)

    def timeout(self):
        failures.append("overall timeout")
        self.finish()

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.scan.stop()
        if self.window and self.window.isVisible():
            failures.append("window remained visible after normal close")
        (AUDIT / "benchmark.json").write_text(json.dumps({"clock": "perf_counter GUI delivery", "events": events, "frames": rows, "failures": failures}, indent=2), encoding="utf-8")
        self.quit()

def launch_context():
    primary = QGuiApplication.primaryScreen()
    return {"screenIndex": list(QGuiApplication.screens()).index(primary),
            "cursorX": primary.geometry().center().x(), "cursorY": primary.geometry().center().y()}

entry._capture_startup_launch_context = launch_context
entry.QApplication = BenchmarkApplication
try:
    entry.main()
except SystemExit as exc:
    if exc.code not in (None, 0):
        failures.append("entry exit=" + str(exc.code))
# Normal application shutdown may finish before the diagnostic finish timer.
# Persist the retained plain Python samples after Qt has exited in either case.
(AUDIT / "benchmark.json").write_text(json.dumps({"clock": "perf_counter GUI delivery", "events": events, "frames": rows, "failures": failures}, indent=2), encoding="utf-8")
after_hashes = hashes()
(AUDIT / "protected_hashes.json").write_text(json.dumps({"before": before_hashes, "after": after_hashes, "unchanged": before_hashes == after_hashes}, indent=2), encoding="utf-8")
assert before_hashes == after_hashes
print(json.dumps({"result": str(AUDIT / "benchmark.json"), "frames": len(rows), "failures": failures}), flush=True)
raise SystemExit(1 if failures else 0)
