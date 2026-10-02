"""External real-source regression runner; disposable workbook/settings copies."""
import os
import sys
import json
import shutil
import ctypes
import ctypes.wintypes
import time
from pathlib import Path
from pixel_tracker_process import PixelTracker, SENSORS

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "logs/window_transition_diagnostic"
AUDIT.mkdir(parents=True, exist_ok=True)
PROFILE = AUDIT / "disposable_profile"
PROFILE.mkdir(exist_ok=True)
for directory in ("local", "master"):
    target = PROFILE / directory
    target.mkdir(exist_ok=True)
    for name in ("CSPM.xlsm", "Dockets.xlsm"):
        shutil.copy2(Path(os.environ["LOCALAPPDATA"]) / "CSPM/data" / name, target / name)
settings = json.loads((Path(os.environ["LOCALAPPDATA"]) / "CSPM/user_settings.json").read_text())
settings.update(masterDataDir=str(PROFILE / "master"), localDataDir=str(PROFILE / "local"),
                keepTrayAlive=False, runAtStartup=False,
                mainWindowLayout={"maximized": False, "hasExactRect": True,
                                  "x": 320, "y": 140, "width": 1100, "height": 760,
                                  "workAreaX": 0, "workAreaY": 0,
                                  "workAreaWidth": 1920, "workAreaHeight": 1040})
(PROFILE / "user_settings.json").write_text(json.dumps(settings), encoding="utf-8")
os.environ["CSPM_RUNTIME_DIR"] = str(PROFILE)
os.environ["CSPM_DATA_DIR"] = str(PROFILE)
os.environ["CSPM_LOG_DIR"] = str(AUDIT / "runtime")
sys.path.insert(0, str(ROOT / "src/python"))
import platform as diagnostic_platform
diagnostic_platform.__path__ = [str(ROOT / 'src/python/platform')]
import main as entry
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine

qt_events=[]
results = []
failures = []
u = ctypes.windll.user32
u.IsZoomed.argtypes = [ctypes.c_void_p]
u.GetWindowLongPtrW.argtypes = [ctypes.c_void_p,ctypes.c_int]
u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u.GetWindowRect.argtypes = [ctypes.c_void_p,ctypes.POINTER(ctypes.wintypes.RECT)]
u.GetClientRect.argtypes = [ctypes.c_void_p,ctypes.POINTER(ctypes.wintypes.RECT)]
u.ClientToScreen.argtypes = [ctypes.c_void_p,ctypes.POINTER(ctypes.wintypes.POINT)]

class ProbeApplication(QApplication):
    def __init__(self, args):
        super().__init__(args)
        self.aboutToQuit.connect(self.write_results)
        self.started = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.wait_ready)
        self.timer.start()
        self.traced_surfaces = set()
        self.surface_timer = QTimer(self)
        self.surface_timer.setInterval(5)
        self.surface_timer.timeout.connect(self.trace_surfaces)
        self.surface_timer.start()
        self.window = None
        self.index = 0
        self.expected_tab = None
        QTimer.singleShot(120000, self.timeout)

    def trace_surfaces(self):
        for w in self.topLevelWindows():
            if w.objectName() == 'CSPMWindowTransitionSurface' and id(w) not in self.traced_surfaces:
                self.traced_surfaces.add(id(w))
                w.frameSwapped.connect(lambda: qt_events.append([time.perf_counter(),'surfaceFrameSwapped']),Qt.DirectConnection)
                self.engine.globalObject().setProperty('_surfaceProbe',self.engine.newQObject(w))
                for n in ('stageChanged','targetReadyChanged','motionCompleteChanged'):
                    getattr(w,n).connect(lambda *_, win=w: print('SURFACE STATE',round(time.perf_counter(),4),win.property('stage'),win.property('presentedFrames'),win.property('targetReady'),win.property('motionComplete'),flush=True))
                w.sourcePresented.connect(lambda: qt_events.append([time.perf_counter(),'sourcePresented']))
                w.targetPresented.connect(lambda: qt_events.append([time.perf_counter(),'targetPresented']))

    def snapshot(self, label):
        w = self.window
        m=w.frameMargins()
        frame=ctypes.wintypes.RECT(); client=ctypes.wintypes.RECT(); origin=ctypes.wintypes.POINT()
        u.GetWindowRect(int(w.winId()),ctypes.byref(frame)); u.GetClientRect(int(w.winId()),ctypes.byref(client)); u.ClientToScreen(int(w.winId()),ctypes.byref(origin))
        content_state = json.loads(self.evaluate("JSON.stringify({radius: _probeWindow.shellVisualCornerRadiusPx(), activeTab: _probeWindow.mainContentRef.option3ActiveTabId, tabs: _probeWindow.mainContentRef.option3OpenTabs})").toString())
        data = {"label": label, "hwnd":int(w.winId()), "style":hex(u.GetWindowLongPtrW(int(w.winId()),-16)), "margins":[m.left(),m.top(),m.right(),m.bottom()], "frame":[frame.left,frame.top,frame.right-frame.left,frame.bottom-frame.top], "nativeClient":[origin.x,origin.y,client.right,client.bottom], "zoomed": bool(u.IsZoomed(int(w.winId()))),
                "qtGeometry": [w.x(), w.y(), w.width(), w.height()],
                "flags": hex(int(w.flags())), "nativeOwner": bool(w.property("professionalNativeWindowState")),
                "uiMaximized": bool(w.property("uiMaximized")),
                "final": [w.property(k) for k in ("finalX", "finalY", "finalW", "finalH")],
                "canvas": [w.property(k) for k in ("canvasX", "canvasY", "canvasW", "canvasH")],
                "radius": content_state["radius"],
                "activeTab": content_state["activeTab"],
                "tabs": content_state["tabs"],
                "overlay": any(x.objectName() == "CSPMMaximizeOverlay" for x in self.topLevelWindows())}
        results.append(data)
        print(json.dumps({k:v for k,v in data.items() if k != "tabs"}), flush=True)
        if data["overlay"]:
            failures.append(label + ": created maximize replica")
        if self.expected_tab and data["activeTab"] != self.expected_tab:
            failures.append(label + ": workspace changed")
        return data

    def evaluate(self, source):
        value = self.engine.evaluate(source)
        if value.isError(): raise RuntimeError(value.toString())
        return value

    def wait_ready(self):
        matches = [w for w in self.topLevelWindows() if w.objectName() == "CSPMMainWindow"]
        if not matches or str(matches[0].property("startupPhase")) != "post-settle-ready":
            return
        self.timer.stop()
        self.window = matches[0]
        self.engine = QQmlEngine.contextForObject(self.window).engine()
        self.engine.globalObject().setProperty("_probeWindow", self.engine.newQObject(self.window))
        self.original_flags = int(self.window.flags())
        self.before = self.snapshot("startup")
        for name in ('beforeFrameBegin','beforeSynchronizing','afterSynchronizing','beforeRendering','afterRendering','afterFrameEnd','frameSwapped'):
            getattr(self.window,name).connect(lambda *_, n=name: qt_events.append([time.perf_counter(),n]),Qt.DirectConnection)
        for name in ('xChanged','yChanged','widthChanged','heightChanged','finalXChanged','finalYChanged','finalWChanged','finalHChanged'):
            getattr(self.window,name).connect(lambda *_, n=name: qt_events.append([time.perf_counter(),n,[self.window.x(),self.window.y(),self.window.width(),self.window.height()],[self.window.property(k) for k in ('finalX','finalY','finalW','finalH')]]))
        self.evaluate("_probeWindow.mainContentRef.option3OpenWorkspaceForTile(3, 'D10', {})")
        QTimer.singleShot(1500, self.begin_cycles)

    def begin_cycles(self):
        self.expected_tab = self.evaluate("_probeWindow.mainContentRef.option3ActiveTabId").toString()
        if not self.expected_tab:
            failures.append("Report workspace did not open")
        positions = [("18", "18"), ("parent.width/2-9", "18"), ("parent.width-36", "18"),
                     ("parent.width-36", "parent.height/2-9"), ("parent.width-36", "parent.height-36"),
                     ("parent.width/2-9", "parent.height-36"), ("18", "parent.height-36"), ("18", "parent.height/2-9")]
        for (name, rgb), (px,py) in zip(SENSORS, positions):
            color = '#' + ''.join(f'{v:02x}' for v in rgb)
            code = 'import QtQuick; Rectangle { width:18; height:18; color:"'+color+'"; x:'+px+'; y:'+py+'; z:100000 }'
            self.evaluate('Qt.createQmlObject('+json.dumps(code)+',_probeWindow.contentLayerRef,'+json.dumps('ReviewPixel_'+name)+'); true')
        self.tracker=PixelTracker(int(self.window.winId()), AUDIT / 'window_transition_pixel8.csv')
        self.tracker.start()
        QTimer.singleShot(7000,self.step)

    def step(self):
        try:
            if self.index < 10:
                self.tracker.command("maximize" if self.index % 2 == 0 else "restore")
                accepted = self.evaluate("_probeWindow.toggleWindowMaximize()").toBool()
                if not accepted:
                    failures.append("command rejected at step " + str(self.index))
                QTimer.singleShot(1400, self.check_cycle)
            else:
                self.tracker.command("minimize")
                self.evaluate("_probeWindow.requestMinimizeAnimation()")
                QTimer.singleShot(1800, self.check_minimized)
        except Exception as exc:
            failures.append(repr(exc))
            self.finish()

    def check_cycle(self):
        data = self.snapshot("cycle " + str(self.index))
        expected_max = self.index % 2 == 0
        if (data["zoomed"] != expected_max if data["nativeOwner"] else False) or data["uiMaximized"] != expected_max:
            failures.append("wrong native/UI state at " + str(self.index))
        if not expected_max and data["final"] != self.before["final"]:
            failures.append("restore rectangle changed at " + str(self.index))
        if data["radius"] > 30:
            failures.append("oversized corner at " + str(self.index))
        self.index += 1
        if self.index in (4,8,12,16):
            self.evaluate("_probeWindow.releaseNativeStateForRestoredInteraction(); _probeWindow.finalX += 45; _probeWindow.finalY += 20; _probeWindow.applyHostEnvelopeForTarget(); _probeWindow.updateCanvasGeometry(); _probeWindow.rememberRestoreGeometry()")
            self.before=self.snapshot("moved " + str(self.index))
        self.step()

    def check_minimized(self):
        data = self.snapshot("minimized")
        if data["nativeOwner"] or int(self.window.flags()) != self.original_flags:
            failures.append("custom minimize did not recover original frame contract")
        self.tracker.command("taskbar-return")
        self.window.showNormal()
        QTimer.singleShot(1800, self.check_resumed)

    def check_resumed(self):
        data = self.snapshot("taskbar resumed")
        if self.window.property("isRestoringFromMinimize") or self.window.property("wasWindowMinimized"):
            failures.append("taskbar restore did not settle")
        if data["final"] != self.before["final"]:
            failures.append("taskbar restore moved content")
        self.evaluate("_probeWindow.toggleWindowMaximize()").toBool()
        QTimer.singleShot(1400, self.minimize_maximized)

    def minimize_maximized(self):
        self.snapshot("before maximized minimize")
        self.evaluate("_probeWindow.requestMinimizeAnimation()")
        QTimer.singleShot(1800, self.resume_maximized)

    def resume_maximized(self):
        data = self.snapshot("maximized minimized")
        if data["nativeOwner"] or int(self.window.flags()) != self.original_flags:
            failures.append("maximized minimize did not recover original frame")
        self.tracker.command("taskbar-return")
        self.window.showNormal()
        QTimer.singleShot(1800, self.restore_after_taskbar)

    def restore_after_taskbar(self):
        data = self.snapshot("maximized taskbar resumed")
        if not data["uiMaximized"]:
            failures.append("maximized taskbar return lost maximized UI")
        self.evaluate("_probeWindow.toggleWindowMaximize()")
        QTimer.singleShot(1400, self.check_after_taskbar)

    def check_after_taskbar(self):
        data = self.snapshot("restored after maximized taskbar cycle")
        if data["final"] != self.before["final"] or data["zoomed"]:
            failures.append("restore after maximized taskbar cycle changed rectangle")
        self.evaluate("_probeWindow.toggleWindowMaximize()")
        QTimer.singleShot(1400, self.close_maximized)

    def close_maximized(self):
        self.snapshot("before maximized close")
        self.evaluate("_probeWindow.requestCloseAnimation()")
        if self.window.property("professionalNativeWindowState"):
            failures.append("custom close retained native owner")
        QTimer.singleShot(2400, self.finish)

    def write_results(self):
        if hasattr(self,"tracker"):
            try: self.tracker.stop()
            except Exception as exc:
                if str(exc) not in failures: failures.append(str(exc))
        (AUDIT / "window_transition_results.json").write_text(json.dumps({"results":results,"failures":failures},indent=2),encoding="utf-8")
        (AUDIT / 'window_transition_frame_trace.json').write_text(json.dumps(qt_events),encoding='utf-8')
        print("REGRESSION FAILURES " + json.dumps(failures), flush=True)

    def finish(self):
        if hasattr(self,"tracker"):
            try: self.tracker.stop()
            except Exception as exc:
                if str(exc) not in failures: failures.append(str(exc))
        self.write_results()
        self.quit()

    def timeout(self):
        failures.append("regression timeout")
        self.finish()

def diagnostic_launch_context():
    primary=QGuiApplication.primaryScreen()
    rectangle=primary.geometry()
    return {'screenIndex':list(QGuiApplication.screens()).index(primary), 'cursorX':rectangle.center().x(),'cursorY':rectangle.center().y()}

entry._capture_startup_launch_context = diagnostic_launch_context
entry.QApplication = ProbeApplication
entry.main()

raise SystemExit(1 if failures else 0)
