"""Exercise the actual Jelly component without visible windows or workbook access."""
from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_tray_return_has_one_growth_and_taskbar_choreography_is_preserved():
    script = r'''
import math
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine, QUrl.fromLocalFile(str(
    Path("src/qml/components/JellyController.qml").resolve())))
assert component.status() == QQmlComponent.Ready, [e.toString() for e in component.errors()]
jelly = component.create()
assert jelly is not None
engine.globalObject().setProperty("jelly", engine.newQObject(jelly))

def invoke(expression):
    result = engine.evaluate(expression)
    assert not result.isError(), result.toString()
    return result

# Drive the real animation's progress deterministically; no timer or frame wait.
for arrived in (False, True):
    invoke("jelly.startRestore(100, 100, true, %s)" % str(arrived).lower())
    scales = []
    opacities = []
    blooms = []
    for index in range(1, 100):
        progress = index / 100
        jelly.setProperty("minimizeProgress", progress)
        scales.append(jelly.property("scaleX"))
        opacities.append(jelly.property("opacityVal"))
        blooms.append(invoke("jelly.restoreBloomProgress(%s)" % progress).toNumber())
    assert all(b >= a for a, b in zip(scales, scales[1:])), scales
    assert all(b >= a for a, b in zip(opacities, opacities[1:])), opacities
    assert all(b >= a for a, b in zip(blooms, blooms[1:])), blooms
    assert scales[-1] > 0.99
    # A finished desktop comet enters the bloom; it never repeats incoming flight.
    initial = invoke("jelly.trayRestoreVisualProgress(0)").toNumber()
    assert initial == (0.28 if arrived else 0.0)
    invoke("jelly.cancelMinimizeRestore()")

# Omitting tray mode retains the accepted taskbar pinpoint and final reveal.
invoke("jelly.startRestore(0, 100)")
for progress in (0.10, 0.28, 0.46, 0.62, 0.73):
    jelly.setProperty("minimizeProgress", progress)
    assert jelly.property("scaleX") == 0.001
    assert jelly.property("opacityVal") == 0.0
jelly.setProperty("minimizeProgress", 0.87)
assert math.isclose(jelly.property("scaleX"), math.sin(math.pi / 4), abs_tol=1e-12)
invoke("jelly.cancelMinimizeRestore()")

# Reduced motion bypasses animation and completes each accepted command once.
completed = []
jelly.restoreFinished.connect(lambda: completed.append(True))
jelly.setProperty("lowPerformanceMode", True)
for arrived in (False, True):
    invoke("jelly.startRestore(100, 100, true, %s)" % str(arrived).lower())
    assert jelly.property("scaleX") == 1.0
    assert jelly.property("scaleY") == 1.0
    assert jelly.property("opacityVal") == 1.0
    assert jelly.property("isAnimating") is False
assert len(completed) == 2

# Execute the actual shell transaction methods with the visual host replaced
# by a counter. This covers duplicate requests before reveal and after cleanup.
shell = Path("src/qml/DetachedShellWindow.qml").read_text(encoding="utf-8")
def shell_function(name):
    start = shell.index("    function " + name + "(")
    opening = shell.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if shell[end] == "{": depth += 1
        elif shell[end] == "}": depth -= 1
        end += 1
    return shell[start:end].strip()

invoke("""
var restoreStarts = 0;
var acknowledgments = [];
var navigations = [];
var settingsOpens = 0;
var mainWin = {
    forceClose: false, isClosing: false, trayRestoreActive: false,
    trayRestoreRevision: 0, _pendingTrayAction: '', _crossMonitorOverlay: null,
    _startRestoreFromTrayInWindow: function() { restoreStarts++; },
    mainContentRef: { handleWorkspaceOpenRequested: function(tileIndex, nodeId, state) {
        navigations.push([tileIndex, nodeId, state]);
    } },
    openSettingsMenu: function() { settingsOpens++; },
    phaseLog: function() {}
};
var trayController = { completeRestoreFromTray: function(revision) { acknowledgments.push(revision); } };
""")
for name in ("requestRestoreFromTrayAnimation", "finishTrayRestoreTransaction"):
    invoke(shell_function(name))
assert invoke("requestRestoreFromTrayAnimation(1)").toBool()
assert not invoke("requestRestoreFromTrayAnimation(1)").toBool()
assert not invoke("requestRestoreFromTrayAnimation(2)").toBool()
assert invoke("restoreStarts").toInt() == 1
invoke("mainWin._pendingTrayNavigation = {tileIndex: 1, nodeId: 'B01', state: {test: true}}; mainWin._pendingTraySettings = true")
assert invoke("navigations.length").toInt() == 0
invoke("finishTrayRestoreTransaction('restore-finished')")
assert invoke("navigations.length").toInt() == 1
assert invoke("navigations[0][1]").toString() == "B01"
assert invoke("settingsOpens").toInt() == 1
invoke("finishTrayRestoreTransaction('restore-finished')")
assert invoke("navigations.length").toInt() == 1
assert invoke("settingsOpens").toInt() == 1
assert invoke("acknowledgments.join(',')").toString() == "1"
assert not invoke("requestRestoreFromTrayAnimation(1)").toBool()
assert invoke("requestRestoreFromTrayAnimation(2)").toBool()
assert invoke("restoreStarts").toInt() == 2
invoke("mainWin._pendingTrayNavigation = {tileIndex: 3, nodeId: 'D01'}; mainWin._pendingTraySettings = true")
invoke("finishTrayRestoreTransaction('close-preempted'); mainWin.isClosing = true")
assert not invoke("requestRestoreFromTrayAnimation(3)").toBool()
assert invoke("acknowledgments.join(',')").toString() == "1,2"
assert invoke("navigations.length").toInt() == 1
assert invoke("settingsOpens").toInt() == 1
assert invoke("mainWin._pendingTrayNavigation === null && !mainWin._pendingTraySettings").toBool()
jelly.deleteLater()
app.processEvents()
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
