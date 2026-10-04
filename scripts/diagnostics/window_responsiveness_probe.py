"""Profile click-to-motion and handoff on a disposable full-source desktop app.

No per-frame Python callbacks run in the render thread. Click timings start at
the real QML handler invoked programmatically, and frame timings describe GUI
notification handling rather than physical monitor scanout. --pixels optionally
collects compositor coordinates in another process. Requires Windows and the
project venv; run outside a WebEngine-restricting sandbox.
"""
import json
import os
from pathlib import Path
import shutil
import sys

import argparse
import time
from target_layout_fanout import _body_bounds
parser = argparse.ArgumentParser(description="Outside-sandbox desktop timing fixture on disposable data; no screenshots are saved.")
parser.add_argument('--audit-label', default='window_responsiveness_' + time.strftime('%Y%m%d_%H%M%S'))
parser.add_argument('--compare', action='store_true', help='Alternate the earlier preparation order and the early-motion path for 20 toggles.')
parser.add_argument('--compare-capture', action='store_true', help='Alternate content-only and native-frame capture for matched timing pairs.')
parser.add_argument('--pixels', action='store_true', help='Collect actual desktop marker coordinates in a separate process; requires desktop duplication access.')
parser.add_argument('--geometry', action='store_true', help='Record content-to-desktop coordinates at transition stages and late live frames.')
parser.add_argument('--cycles', type=int, default=10, help='Even number of primary toggles (default: 10; --compare defaults to 20).')
parser.add_argument('--screen-index', type=int, help='Place the disposable app on this Qt screen index; defaults to the primary screen.')
parser.add_argument('--keep-visible', action='store_true', help='Keep the disposable window above other windows so desktop pixel measurements are unoccluded.')
parser.add_argument('--endpoint-hold-ms', type=int, default=0, help='Diagnostic-only endpoint hold for stable pixel sampling; excluded from normal timing claims.')
args = parser.parse_args()
if args.cycles < 2 or args.cycles % 2:
    parser.error('--cycles must be an even number of at least two')
if args.screen_index is not None and args.screen_index < 0:
    parser.error('--screen-index must be nonnegative')
if args.compare and args.compare_capture:
    parser.error('--compare and --compare-capture are mutually exclusive')
if args.endpoint_hold_ms < 0 or args.endpoint_hold_ms > 1000:
    parser.error('--endpoint-hold-ms must be between zero and 1000')
cycle_count = 20 if (args.compare or args.compare_capture) and args.cycles == 10 else args.cycles
if not args.audit_label or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for ch in args.audit_label):
    parser.error('--audit-label must contain only letters, digits, underscores or hyphens')
ROOT = Path(__file__).resolve().parents[2]
AUDIT_NAME = args.audit_label
AUDIT = ROOT/'logs'/AUDIT_NAME
MIRROR = AUDIT/'tree'
MIRROR.mkdir(parents=True, exist_ok=True)
for source, destination in ((ROOT/'src/qml', MIRROR/'src/qml'),
                            (ROOT/'src/assets', MIRROR/'src/assets'),
                            (ROOT/'assets', MIRROR/'assets')):
    shutil.copytree(source, destination, dirs_exist_ok=True)

def replace_once(text, before, after):
    assert text.count(before) == 1, (before[:100], text.count(before))
    return text.replace(before, after, 1)

shell_path = MIRROR/'src/qml/DetachedShellWindow.qml'
shell = shell_path.read_text(encoding='utf-8')
# Keep the experimental capture function byte-for-byte intact while the
# production-only observer adds its strict one-match hooks below.
experimental_start = shell.index('    function captureCleanRoomTransitionSurface(')
_, experimental_end = _body_bounds(shell, 'DetachedShellWindow', 'captureCleanRoomTransitionSurface')
experimental_capture = shell[experimental_start:experimental_end + 1]
experimental_marker = '    // CSPM_DIAGNOSTIC_EXPERIMENTAL_CAPTURE_BOUNDARY'
shell = replace_once(shell, experimental_capture, experimental_marker)
shell = replace_once(shell, '    function toggleWindowMaximize() {', '''
    property var responsivenessProbeEvents: []
    property var responsivenessProbeRuns: []
    property bool responsivenessProbeActive: false
    function beginResponsivenessProbe(label) {
        responsivenessProbeEvents = [];
        responsivenessProbeActive = true;
        recordResponsivenessStage(label);
    }
    function recordResponsivenessStage(label) {
        if (responsivenessProbeActive) responsivenessProbeEvents.push([label, Date.now()]);
    }
    function toggleWindowMaximize() {
        if (!responsivenessProbeActive) beginResponsivenessProbe("direct-command");
        recordResponsivenessStage("toggle-entry");''')
if args.geometry:
    shell = replace_once(shell,
        '    property var responsivenessProbeEvents: []', '''
    property var responsivenessProbeGeometry: []
    property int responsivenessProbeGeometrySequence: 0
    property string responsivenessProbeGeometryKind: ""
    property double responsivenessProbeGeometryUntil: 0
    function recordResponsivenessGeometry(label) {
        var p = contentLayer.mapToGlobal(0, 0);
        responsivenessProbeGeometry.push({label:label, time:Date.now(),
            sequence:responsivenessProbeGeometrySequence,
            kind:responsivenessProbeGeometryKind,
            window:[x,y,width,height], host:[hostX,hostY,hostW,hostH],
            finalRect:[finalX,finalY,finalW,finalH],
            canvas:[canvasX,canvasY,canvasW,canvasH],
            local:[canvasLocalX,canvasLocalY,contentLocalX,contentLocalY],
            content:[p.x,p.y,contentLayer.width,contentLayer.height],
            dpr:Screen.devicePixelRatio, opacity:mainWin.opacity,
            phase:animationPhase,
            otherMotion:isMinimizing || isRestoringFromMinimize || wasWindowMinimized || isClosing,
            transforms:[settledScaleX(),settledScaleY(),settledTransX(),settledTransY(),settledRotate()],
            surfaceStage:maximizeOverlayRef ? maximizeOverlayRef.stage : "none"});
    }
    Connections {
        target: mainWin
        function onFrameSwapped() {
            if (Date.now() < mainWin.responsivenessProbeGeometryUntil)
                mainWin.recordResponsivenessGeometry("live-frame");
        }
    }
    property var responsivenessProbeEvents: []''')
    shell = replace_once(shell, '        responsivenessProbeEvents = [];', '''
        responsivenessProbeGeometrySequence++;
        responsivenessProbeGeometryKind = uiMaximized ? "restore" : "maximize";
        responsivenessProbeEvents = [];''')
    shell = replace_once(shell,
        '        if (responsivenessProbeActive) responsivenessProbeEvents.push([label, Date.now()]);', '''
        if (responsivenessProbeActive) {
            responsivenessProbeEvents.push([label, Date.now()]);
            recordResponsivenessGeometry(label);
            if (label === "motion-finished") responsivenessProbeGeometryUntil = Date.now()+1500;
        }''')
shell = replace_once(shell,
    '                console.warn("Professional window surface handoff timed out");',
    '''                recordResponsivenessStage("watchdog-" + (maximizeOverlayRef ? maximizeOverlayRef.stage : "no-surface"));
                responsivenessProbeRuns.push({kind: professionalWindowTransitionKind,
                    optimized: professionalEarlyWindowMotionEnabled,
                    timedOut: true, events: responsivenessProbeEvents});
                responsivenessProbeActive = false;
                console.warn("Professional window surface handoff timed out");''')
shell = replace_once(shell, '            return restored;\n        }\n        phaseLog("MAXIMIZE"',
    '            recordResponsivenessStage("toggle-return");\n            return restored;\n        }\n        phaseLog("MAXIMIZE"')
shell = replace_once(shell, '        return maximized;\n    }\n\n    function beginHeaderDrag',
    '        recordResponsivenessStage("toggle-return");\n        return maximized;\n    }\n\n    function beginHeaderDrag')
shell = replace_once(shell,
    '        professionalSurfaceWatchdog.restart();\n        var sourceHeaderMetrics',
    '        recordResponsivenessStage("source-grab-request");\n        professionalSurfaceWatchdog.restart();\n        var sourceHeaderMetrics')
source_grab_line = '        var accepted = grabProfessionalWindowFrame(function(result) {'
# Both experimental and production paths capture a source. Instrument only
# the production transaction, retaining the strict one-match guard within it.
source_grab_context = '        var sourceHeaderMetrics = mainContent.professionalTransitionHeaderMetrics();\n' + source_grab_line
shell = replace_once(shell, source_grab_context,
    source_grab_context+'\n            mainWin.recordResponsivenessStage("source-grab-ready");')
create_line = '            var surface = professionalSurfaceComponent.createObject(null, {'
shell = replace_once(shell, create_line,
    '            mainWin.recordResponsivenessStage("surface-create-start");\n'+create_line)
surface_create_guard = '            if (!surface) {\n                windowFrameCapture.release(result.url);'
shell = replace_once(shell, surface_create_guard,
    '            mainWin.recordResponsivenessStage("surface-create-end");\n'+surface_create_guard)
source_connect = '            surface.sourcePresented.connect(function() {'
shell = replace_once(shell, source_connect,
    source_connect+'\n                mainWin.recordResponsivenessStage("source-presented");')
target_connect = '            surface.targetCaptureRequested.connect(function() {'
shell = replace_once(shell, target_connect,
    target_connect+'\n                mainWin.recordResponsivenessStage("target-grab-request");')
target_grab_line = '                var targetAccepted = mainWin.grabProfessionalWindowFrame(function(targetResult) {'
shell = replace_once(shell, target_grab_line,
    target_grab_line+'\n                    mainWin.recordResponsivenessStage("target-grab-ready");')
present_connect = '            surface.targetPresented.connect(function() {'
shell = replace_once(shell, present_connect,
    present_connect+'\n                mainWin.recordResponsivenessStage("live-target-reveal");')
shell = replace_once(shell, '            surface.visible = true;\n        });',
    '            mainWin.recordResponsivenessStage("surface-show-request");\n            surface.visible = true;\n            mainWin.recordResponsivenessStage("source-callback-end");\n        });')

start = shell.index('    function commitProfessionalWindowTransitionTarget(')
end = shell.index('    function finishProfessionalWindowTransition(', start)
commit = shell[start:end]
commit = commit.replace('        geometryTransitionSuppressed = true;',
    '        recordResponsivenessStage("commit-start");\n        geometryTransitionSuppressed = true;', 1)
for line, label in [('        finalX = Math.round(targetRect.x);', 'commit-x'),
                    ('        finalY = Math.round(targetRect.y);', 'commit-y'),
                    ('        finalW = Math.max(1, Math.round(targetRect.w));', 'commit-width'),
                    ('        finalH = Math.max(1, Math.round(targetRect.h));', 'commit-height')]:
    commit = replace_once(commit, line, line+'\n        recordResponsivenessStage("'+label+'");')
for line, label in [('        uiMaximized = kind === "maximize";', 'commit-size'),
                    ('        refreshActiveVisibleRect();', 'commit-screen'),
                    ('        applyHostEnvelopeForTarget();', 'commit-visible-rect'),
                    ('        updateCanvasGeometry();', 'commit-native-envelope')]:
    commit = replace_once(commit, line, '        recordResponsivenessStage("'+label+'");\n'+line)
commit = commit.replace('        if (!uiMaximized) {', '        recordResponsivenessStage("commit-end");\n        if (!uiMaximized) {',1)
shell = shell[:start]+commit+shell[end:]
start = shell.index('    function finishProfessionalWindowTransition(')
end = shell.index('    function completeProfessionalWindowTransitionDirect(', start)
finish = shell[start:end]
finish = replace_once(finish, '        professionalSurfaceWatchdog.stop();',
    '        recordResponsivenessStage("finish-start");\n        professionalSurfaceWatchdog.stop();')
finish = replace_once(finish, '            persistMainWindowLayout();',
    '            recordResponsivenessStage("save-layout-start");\n            persistMainWindowLayout();\n            recordResponsivenessStage("save-layout-end");')
finish = finish.rstrip()[:-1]+'''
        recordResponsivenessStage("finish-end");
        responsivenessProbeRuns.push({kind: kind, events: responsivenessProbeEvents});
        responsivenessProbeActive = false;
    }

'''
shell = shell[:start]+finish+shell[end:]
shell = shell.replace('responsivenessProbeRuns.push({kind: kind, events: responsivenessProbeEvents});',
    'responsivenessProbeRuns.push({kind: kind, optimized: professionalEarlyWindowMotionEnabled, events: responsivenessProbeEvents});')
shell = shell.replace('optimized: professionalEarlyWindowMotionEnabled,',
    'optimized: professionalEarlyWindowMotionEnabled, nativeFrames: professionalPixelAlignedWindowCaptureEnabled,')
if args.endpoint_hold_ms:
    shell = replace_once(shell, '    function toggleWindowMaximize() {', '''
    Timer {
        id: responsivenessEndpointHoldTimer
        interval: '''+str(args.endpoint_hold_ms)+'''
        property var revealAction
        onTriggered: revealAction()
    }
    function toggleWindowMaximize() {''')
    shell = replace_once(shell, present_connect,
        present_connect+'\n                responsivenessEndpointHoldTimer.revealAction = function() {')
    shell = replace_once(shell, '                surface.expectLiveHandoff();\n            });',
        '                surface.expectLiveHandoff();\n                };\n                responsivenessEndpointHoldTimer.restart();\n            });')
shell = replace_once(shell, experimental_marker, experimental_capture)
shell_path.write_text(shell, encoding='utf-8')

surface_path = MIRROR/'src/qml/WindowTransitionSurface.qml'
surface = surface_path.read_text(encoding='utf-8')
surface = replace_once(surface, '    function startMotion() {',
    '    function startMotion() {\n        mainWindow.recordResponsivenessStage("motion-start-request");')
assert surface.count('            surface.motionComplete = true') in (1, 2)
surface = surface.replace('            surface.motionComplete = true',
    '            surface.mainWindow.recordResponsivenessStage("motion-finished");\n            surface.motionComplete = true')
surface = replace_once(surface, '        targetGrab = result',
    '        mainWindow.recordResponsivenessStage("target-image-assigned");\n        targetGrab = result')
surface = replace_once(surface, '        if (closingSurface) return\n        if (stage === "source"',
    '        if (closingSurface) return\n        mainWindow.recordResponsivenessStage("surface-frame-" + stage + "-" + presentedFrames);\n        if (stage === "source"')
surface = replace_once(surface, '            motionStarted()',
    '            mainWindow.recordResponsivenessStage("motion-first-submitted-frame");\n            motionStarted()')
surface = replace_once(surface, '            if (surface.closingSurface) return\n            if (surface.awaitingLiveHandoff)',
    '            if (surface.closingSurface) return\n            if (surface.awaitingLiveTarget || surface.awaitingLiveHandoff)\n                surface.mainWindow.recordResponsivenessStage("original-frame-" + surface.stage + "-" + surface.liveTargetFrames);\n            if (surface.awaitingLiveHandoff)')
surface = replace_once(surface, '    function startPreparationMotion() {',
    '    function startPreparationMotion() {\n        mainWindow.recordResponsivenessStage("preparation-start-request");')
surface_path.write_text(surface, encoding='utf-8')

header_path = MIRROR/'src/qml/components/ProfessionalTopHeader.qml'
header = header_path.read_text(encoding='utf-8')
header = replace_once(header, '                id: maximizeButton',
    '                id: maximizeButton\n                objectName: "ResponsivenessMaximizeButton"')
offset = header.index('                id: maximizeButton')
clicked = header.index('                onClicked: {', offset)+len('                onClicked: {')
header = header[:clicked]+'\n                    topHeaderRoot.app.windowRef.beginResponsivenessProbe("click-handler");'+header[clicked:]
header_path.write_text(header, encoding='utf-8')

# Reuse the previous completion-gated, no-per-frame-Python functional fixture.
wrapper = (
    '"""Use the portable real-app fixture without the unrelated DXGI collector."""\n'
    'from pathlib import Path\n'
    'import sys\n'
    '\n'
    'root = Path(__file__).resolve().parents[1]\n'
    "probe = root / 'scripts/diagnostics/window_transition_probe.py'\n"
    'sys.path.insert(0, str(probe.parent))\n'
    "code = probe.read_text(encoding='utf-8')\n"
    'if not args.pixels:\n'
    "    code = code.replace('from pixel_tracker_process import PixelTracker, SENSORS', '''\n"
    'from pixel_tracker_process import SENSORS\n'
    'class PixelTracker:\n'
    '    def __init__(self, *_): pass\n'
    '    def start(self): pass\n'
    '    def stop(self): pass\n'
    "    def command(self, name): print('FUNCTIONAL COMMAND', name, flush=True)\n"
    "''')\n"
    "code = code.replace('logs/window_transition_diagnostic', 'logs/titlebar_settlement_source_fixture_20261002')\n"
    "code = code.replace('120000', '180000')\n"
    "code = code.replace('        self.surface_timer.start()', '        # Functional fixture has no per-frame Python polling.')\n"
    'code = code.replace("for name in (\'xChanged\',\'yChanged\',\'widthChanged\',\'heightChanged\',\'finalXChanged\',\'finalYChanged\',\'finalWChanged\',\'finalHChanged\'):", "for name in ():")\n'
    '# A Python DirectConnection on every render-stage signal stalls the render\n'
    "# thread behind the GUI's GIL. Functional checks need completion events only.\n"
    'code = code.replace("for name in (\'beforeFrameBegin\',\'beforeSynchronizing\',\'afterSynchronizing\',\'beforeRendering\',\'afterRendering\',\'afterFrameEnd\',\'frameSwapped\'):", "for name in ():")\n'
    'code = code.replace("w.frameSwapped.connect(lambda: qt_events.append([time.perf_counter(),\'surfaceFrameSwapped\']),Qt.DirectConnection)", "w.frameSwapped.connect(lambda: qt_events.append([time.perf_counter(),\'surfaceFrameSwapped\']))")\n'
    "code = code.replace('QTimer.singleShot(1400, self.check_cycle)', 'QTimer.singleShot(50, self.wait_cycle_settlement)')\n"
    "code = code.replace('    def check_cycle(self):', '''    def wait_cycle_settlement(self):\n"
    "        if self.window.property('professionalWindowTransitionActive'):\n"
    '            QTimer.singleShot(50, self.wait_cycle_settlement)\n'
    '        else:\n'
    '            self.check_cycle()\n'
    '\n'
    "    def check_cycle(self):''')\n"
    'code = code.replace(\'accepted = self.evaluate("_probeWindow.toggleWindowMaximize()")\', \'self.cycle_started = time.monotonic(); accepted = self.evaluate("_probeWindow.toggleWindowMaximize()")\')\n'
    'code = code.replace(\'        self.index += 1\', "        print(\'CYCLE LATENCY\', round(time.monotonic()-self.cycle_started,3), flush=True)\\n        self.index += 1")\n'
    "for callback in ('self.minimize_maximized', 'self.check_after_taskbar', 'self.close_maximized'):\n"
    "    code = code.replace('QTimer.singleShot(1400, '+callback+')',\n"
    "                        'QTimer.singleShot(50, lambda: self.wait_until_window_settles('+callback+'))')\n"
    "code = code.replace('    def check_resumed(self):', '''    def wait_until_window_settles(self, callback):\n"
    "        if (self.window.property('professionalWindowTransitionActive')\n"
    "                or self.window.property('isRestoringFromMinimize')\n"
    "                or self.window.property('isMinimizing')):\n"
    '            QTimer.singleShot(50, lambda: self.wait_until_window_settles(callback))\n'
    '        else:\n'
    '            callback()\n'
    '\n'
    '    def check_resumed(self):\n'
    "        if self.window.property('isRestoringFromMinimize'):\n"
    '            QTimer.singleShot(50, self.check_resumed)\n'
    "            return''')\n"
    'code = code.replace("w.targetPresented.connect(lambda: qt_events.append([time.perf_counter(),\'targetPresented\']))", """\n'
    "                w.targetPresented.connect(lambda: qt_events.append([time.perf_counter(),'targetPresented']))\n"
    "                w.motionStarted.connect(lambda: qt_events.append([time.perf_counter(),'motionStarted']))\n"
    "                w.transitionFinished.connect(lambda: qt_events.append([time.perf_counter(),'transitionFinished']))\n"
    '""")\n'
    "code = code.replace('raise SystemExit(1 if failures else 0)', '')\n"
    "runtime_path = root/'logs/titlebar_settlement_source_fixture_20261002/runtime/cspm.log'\n"
    'initial_log_bytes = runtime_path.stat().st_size if runtime_path.exists() else 0\n'
    "exec(compile(code, str(probe), 'exec'), {'__file__':str(probe), '__name__':'__main__'})\n"
    'import json\n'
    "report = json.loads((root/'logs/titlebar_settlement_source_fixture_20261002/window_transition_results.json').read_text())\n"
    "assert not report['failures'], report['failures']\n"
    "runtime = runtime_path.read_bytes()[initial_log_bytes:].decode('utf-8', errors='replace')\n"
    "assert 'Professional window surface handoff timed out' not in runtime\n"
)
wrapper = wrapper.replace("root = Path(__file__).resolve().parents[1]", "root = Path("+repr(str(ROOT))+")")
wrapper = wrapper.replace('titlebar_settlement_source_fixture_20261002', AUDIT_NAME)
insertion = '''
code = code.replace('import main as entry', '''+repr('''import main as entry
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QObject
class ProfileEngine(QQmlApplicationEngine):
    def load(self, url):
        local = url.toLocalFile() if isinstance(url, QUrl) else str(url)
        if Path(local).name == 'Main.qml':
            url = QUrl.fromLocalFile('''+repr(str(MIRROR/'src/qml/Main.qml'))+''')
        return super().load(url)
entry.QQmlApplicationEngine = ProfileEngine
_probe_mask_times = []
''')+''')
code = code.replace('        self.original_flags = int(self.window.flags())', '''+repr('''        self.original_flags = int(self.window.flags())
        self.button = self.window.findChild(QObject, 'ResponsivenessMaximizeButton')
        assert self.button is not None
        self.engine.globalObject().setProperty('_probeMaximizeButton', self.engine.newQObject(self.button))''')+''')
code = code.replace('self.evaluate("_probeWindow.toggleWindowMaximize()")',
                    'self.evaluate("_probeMaximizeButton.clicked(); true")')
code = code.replace('    def write_results(self):', '''+repr('''    def write_results(self):
        if hasattr(self, 'engine'):
            payload = self.evaluate("JSON.stringify(_probeWindow.responsivenessProbeRuns)").toString()
            (AUDIT/'latency_events.json').write_text(payload, encoding='utf-8')
            geometry = self.evaluate("JSON.stringify(_probeWindow.responsivenessProbeGeometry || [])").toString()
            (AUDIT/'geometry_events.json').write_text(geometry, encoding='utf-8')
            (AUDIT/'mask_times.json').write_text(json.dumps(_probe_mask_times), encoding='utf-8')
            (AUDIT/'display_probe.json').write_text(json.dumps({'dpr':self.window.devicePixelRatio(), 'visible':self.window.isVisible()}), encoding='utf-8')''')+''')
'''
wrapper = replace_once(wrapper, "code = code.replace('raise SystemExit(1 if failures else 0)', '')",
    insertion+"\ncode = code.replace('raise SystemExit(1 if failures else 0)', '')")
wrapper = replace_once(wrapper, "code = code.replace('raise SystemExit(1 if failures else 0)', '')",
    f"code = code.replace('if self.index < 10:', 'if self.index < {cycle_count}:')\n"
    + ("code = code.replace('            self.check_cycle()', '            QTimer.singleShot(300, self.check_cycle)')\n" if args.geometry else "")
    + "code = code.replace('raise SystemExit(1 if failures else 0)', '')")
if args.compare:
    wrapper = wrapper.replace("code = code.replace('raise SystemExit(1 if failures else 0)', '')", '''
code = code.replace('    def step(self):', '    def step(self):\\n        self.evaluate("_probeWindow.professionalEarlyWindowMotionEnabled = " + ("true" if (self.index // 2) % 2 else "false"))\\n        QTimer.singleShot(100, self.command_step)\\n\\n    def command_step(self):')
code = code.replace('raise SystemExit(1 if failures else 0)', '')''')
if args.compare_capture:
    wrapper = wrapper.replace("code = code.replace('raise SystemExit(1 if failures else 0)', '')", '''
code = code.replace('    def step(self):', '    def step(self):\\n        self.evaluate("_probeWindow.professionalPixelAlignedWindowCaptureEnabled = " + ("true" if (self.index // 2) % 2 else "false"))\\n        QTimer.singleShot(100, self.command_step)\\n\\n    def command_step(self):')
code = code.replace('raise SystemExit(1 if failures else 0)', '')''')
if args.screen_index is not None:
    wrapper = replace_once(wrapper, "code = code.replace('raise SystemExit(1 if failures else 0)', '')",
        "code = code.replace('primary=QGuiApplication.primaryScreen()', "
        + repr(f'primary=QGuiApplication.screens()[{args.screen_index}]') + ")\n"
        + "code = code.replace('raise SystemExit(1 if failures else 0)', '')")
if args.keep_visible:
    wrapper = replace_once(wrapper, "code = code.replace('raise SystemExit(1 if failures else 0)', '')",
        "code = code.replace('    def begin_cycles(self):', " + repr('''    def begin_cycles(self):
        # Diagnostic-only HWND z-order; released when this disposable app exits.
        u.SetWindowPos.argtypes = [ctypes.wintypes.HWND,ctypes.wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
        assert u.SetWindowPos(int(self.window.winId()), -1, 0, 0, 0, 0, 0x13)
        self.window.update()''') + ")\n"
        + "code = code.replace('raise SystemExit(1 if failures else 0)', '')")
try:
    exec(compile(wrapper, str(ROOT/'logs/run_settlement_fixture_20261002.py'), 'exec'),
         {'__file__':str(ROOT/'logs/run_settlement_fixture_20261002.py'), '__name__':'__main__', 'args': args})
except SystemExit as exc:
    assert exc.code in (None, 0), exc.code

runtime = (AUDIT/'runtime/cspm.log').read_text(encoding='utf-8', errors='replace')
runs = json.loads((AUDIT/'latency_events.json').read_text())
report = json.loads((AUDIT/'window_transition_results.json').read_text(encoding='utf-8'))
assert not report['failures'], report['failures']
assert 'Professional window surface handoff timed out' not in runtime
expected = cycle_count + 3
assert len(runs) == expected, (len(runs), expected)
assert len([row for row in report['results'] if row['label'].startswith('cycle ')]) == cycle_count
(AUDIT/'latency_events.json').write_text(json.dumps(runs, indent=2), encoding='utf-8')
print(json.dumps({'timed_runs':len(runs), 'result':str(AUDIT/'latency_events.json')}), flush=True)
