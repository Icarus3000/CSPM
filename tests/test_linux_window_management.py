"""Run shell window commands in Qt's JS engine without a window or WebEngine."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtQml import QJSEngine
import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = QCoreApplication.instance() or QCoreApplication([])
SHELL = ROOT / "src/qml/DetachedShellWindow.qml"


def function_source(name: str) -> str:
    source = SHELL.read_text(encoding="utf-8")
    start = source.index("function " + name + "(")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def run_shell(functions: list[str], expression: str, **overrides):
    state = dict(
        linuxDesktopWindowManagement=True,
        linuxCompositorGeometryActive=True,
        linuxCompositorGeometrySyncing=False,
        linuxNormalWindowPadding=12,
        linuxNormalWindowRect=None,
        animationPhase="settled", isClosing=False, isMinimizing=False,
        isRestoringFromMinimize=False, maximizeAnimInProgress=False,
        userMoveInProgress=False, userResizeInProgress=False,
        systemMoveInProgress=False, strictResizePipelineEnabled=True,
        uiMaximized=False, visible=True, visibility=2, x=-1600, y=90, width=1000, height=760,
        finalX=-1588, finalY=102, finalW=976, finalH=736,
        hostX=-1600, hostY=90, hostW=1000, hostH=760,
        canvasX=-1600, canvasY=90, canvasW=1000, canvasH=760,
        canvasLocalX=0, canvasLocalY=0, contentLocalX=12, contentLocalY=12,
        maximizedOwnerScreen=None,
        screen={"name": "current-screen"}, targetScreen=None,
        calls=[], geometryTransitionSuppressed=True,
        isExitingFromTray=False, wasWindowMinimized=False, opacity=1, glowPadding=12,
    )
    state.update(overrides)
    engine = QJSEngine()
    setup = "var state=" + json.dumps(state) + ";state.mainWin=state;"
    setup += "var Window={Windowed:2,Minimized:3,Maximized:4};"
    setup += "var Qt=" + json.dumps({
        "LeftEdge": Qt.LeftEdge.value, "RightEdge": Qt.RightEdge.value,
        "TopEdge": Qt.TopEdge.value, "BottomEdge": Qt.BottomEdge.value,
    }) + ";"
    setup += """
        var linuxWindowGeometrySync={restart:function(){state.calls.push('sync');}};
        var linuxWindowLayoutSave={restart:function(){state.calls.push('save');}};
        var console={warn:function(){}};
        var trayKeepAlive={visible:true};
        var jelly={startExitFromTray:function(x,y){state.calls.push(['exit-light',x,y]);}};
        state.showMaximized=function(){state.calls.push('maximize');};
        state.showNormal=function(){state.calls.push('normal');};
        state.setGeometry=function(x,y,w,h){state.calls.push(['geometry',x,y,w,h]);};
        state.startSystemMove=function(){state.calls.push('move');return true;};
        state.startSystemResize=function(edges){state.calls.push(['resize',edges]);return true;};
        state.rememberRestoreGeometry=function(){state.calls.push('remember');};
        state.refreshActiveVisibleRect=function(){state.calls.push('workarea');};
        state.clearMinimizeRestoreState=function(){state.calls.push('clear');};
        state.applyHostEnvelopeForTarget=function(){state.calls.push('host');};
        state.updateCanvasGeometry=function(){state.calls.push('canvas');};
        state.requestActivate=function(){state.calls.push('activate');};
        state.adoptTargetScreen=function(screen){state.targetScreen=screen;};
        state.isResizeHandleValid=function(handle){return /^(n|s|e|w|ne|nw|se|sw)$/.test(handle);};
        // Native geometry is read-only to the shell during a compositor event.
        ['x','y','width','height'].forEach(function(key){
            var value=state[key];
            Object.defineProperty(state,key,{get:function(){return value;},
                set:function(){throw new Error('QML wrote native '+key);}, enumerable:true});
        });
    """
    for name in functions:
        setup += "with(state){state." + name + "=" + function_source(name) + ";}"
    result = engine.evaluate(setup + "var result=" + expression
                             + ";delete state.mainWin;({result:result,state:state});")
    assert not result.isError(), result.toString()
    return result.property("result").toVariant(), result.property("state").toVariant()


@pytest.mark.parametrize("maximized", [False, True])
def test_linux_state_command_has_one_native_owner(maximized):
    accepted, state = run_shell(
        ["adoptLinuxCompositorGeometry", "requestLinuxWindowState"],
        f"state.requestLinuxWindowState({str(maximized).lower()})",
    )
    assert accepted is True
    assert state["calls"] == ["maximize" if maximized else "normal", "sync"]
    assert state["maximizeAnimInProgress"] is False
    assert state["hostW"] == 1000


@pytest.mark.parametrize("visible,pad,expected_maximized", [(2, 12, False), (4, 0, True)])
def test_native_configure_updates_content_without_writing_geometry(visible, pad, expected_maximized):
    _, state = run_shell(["syncLinuxCompositorGeometry"], "state.syncLinuxCompositorGeometry()",
                         visibility=visible, width=1250, height=820)
    assert state["uiMaximized"] is expected_maximized
    assert (state["hostW"], state["hostH"]) == (1250, 820)
    assert (state["canvasLocalX"], state["canvasLocalY"]) == (0, 0)
    assert (state["contentLocalX"], state["contentLocalY"]) == (pad, pad)
    assert (state["finalW"], state["finalH"]) == (1250 - 2 * pad, 820 - 2 * pad)
    assert state["targetScreen"] == state["screen"]
    assert ("remember" in state["calls"]) is not expected_maximized


@pytest.mark.parametrize("override", [
    {"isClosing": True}, {"isMinimizing": True}, {"isRestoringFromMinimize": True},
    {"visibility": 3}, {"animationPhase": "opening"},
    {"visible": False, "visibility": 0, "uiMaximized": True},
])
def test_native_geometry_sync_preserves_lifecycle_light_effects(override):
    _, state = run_shell(["syncLinuxCompositorGeometry"], "state.syncLinuxCompositorGeometry()",
                         **override)
    assert state["calls"] == []
    assert state["finalW"] == 976
    if override.get("uiMaximized"):
        assert state["uiMaximized"] is True


@pytest.mark.parametrize("handle,expected", [
    ("n", Qt.TopEdge), ("s", Qt.BottomEdge), ("w", Qt.LeftEdge), ("e", Qt.RightEdge),
    ("nw", Qt.TopEdge | Qt.LeftEdge), ("ne", Qt.TopEdge | Qt.RightEdge),
    ("sw", Qt.BottomEdge | Qt.LeftEdge), ("se", Qt.BottomEdge | Qt.RightEdge),
])
def test_each_resize_handle_delegates_to_the_compositor(handle, expected):
    accepted, state = run_shell(
        ["adoptLinuxCompositorGeometry", "linuxResizeEdges", "beginUserResize"],
        f"state.beginUserResize({json.dumps(handle)})",
    )
    assert accepted is True
    assert state["calls"] == [["resize", expected.value]]
    # No custom cursor polling or deformation pipeline is enabled.
    assert state["userResizeInProgress"] is False
    assert state["geometryTransitionSuppressed"] is False


@pytest.mark.parametrize("maximized", [False, True])
def test_header_drag_leaves_restore_and_snapping_to_plasma(maximized):
    accepted, state = run_shell(
        ["adoptLinuxCompositorGeometry", "beginUserDrag", "beginHeaderDrag"],
        "state.beginHeaderDrag(10, 20)", uiMaximized=maximized,
    )
    assert accepted is True
    assert state["calls"] == ["move"]
    assert state["userMoveInProgress"] is False
    assert state["uiMaximized"] is maximized


@pytest.mark.parametrize("linux,maximized,expected", [
    (True, True, "maximize"), (True, False, "normal"),
    (False, True, "normal"), (False, False, "normal"),
])
def test_tray_restore_preserves_linux_native_maximized_state(linux, maximized, expected):
    _, state = run_shell(["showForLifecycleRestore"], "state.showForLifecycleRestore()",
                         linuxDesktopWindowManagement=linux, uiMaximized=maximized)
    assert state["calls"] == [expected]


def test_windows_never_enters_linux_window_state_path():
    accepted, state = run_shell(["requestLinuxWindowState"], "state.requestLinuxWindowState(true)",
                               linuxDesktopWindowManagement=False)
    assert accepted is False
    assert state["calls"] == []


def test_maximized_tray_exit_keeps_the_native_canvas_for_its_light_burst():
    _, state = run_shell(["showForLifecycleRestore", "_startExitFromTrayInWindow"],
                         "state._startExitFromTrayInWindow()", uiMaximized=True,
                         visible=False, visibility=0, wasWindowMinimized=True)
    assert state["calls"] == ["clear", "host", "canvas", "maximize", "activate",
                               ["exit-light", 500, 380]]
    assert state["isClosing"] and state["isExitingFromTray"]
    assert state["uiMaximized"]
    assert state["animationPhase"] == "closing"


def test_linux_restore_uses_the_exact_normal_rectangle_after_a_tray_roundtrip():
    _, state = run_shell(["adoptLinuxCompositorGeometry", "requestLinuxWindowState"],
                         "state.requestLinuxWindowState(true);state.uiMaximized=true;"
                         "state.requestLinuxWindowState(false)")
    assert state["linuxNormalWindowRect"] == {"x": -1600, "y": 90, "w": 1000, "h": 760}
    assert state["calls"] == ["maximize", "sync", "normal",
                              ["geometry", -1600, 90, 1000, 760], "sync"]
