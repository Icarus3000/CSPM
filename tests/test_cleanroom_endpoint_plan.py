"""Run the QML endpoint contract in a JS engine without desktop/GPU creation."""
from pathlib import Path
import os
import re
import subprocess
import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine


QML = Path(__file__).resolve().parents[1] / "src/qml/CleanRoomTransitionSurface.qml"
FUNCTIONS = (
    "elapsed", "record", "reject", "prepareNativeGeometry", "nearestNativePixel",
    "near", "samePhysicalScreen", "targetMatchesPlan", "capturedContentBounds", "nextFrame", "setTargetGrab",
)


def qml_function(source, name):
    match = re.search(r"function " + name + r"\([^)]*\)\s*\{", source)
    assert match
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


@pytest.fixture
def engine():
    app = QCoreApplication.instance() or QCoreApplication([])
    js = QJSEngine()
    setup = r"""
    var Qt = {
        rect: function(x,y,w,h) { return {x:x,y:y,width:w,height:h}; },
        point: function(x,y) { return {x:x,y:y}; },
        size: function(w,h) { return {width:w,height:h}; },
        callLater: function(callback) { callback(); }
    };
    var console = {warn:function() {}};
    var screen = {name:'primary', virtualX:0, virtualY:0,
        width:1920, height:1080, devicePixelRatio:1}, stopCount = 0, released = [];
    var surface = {screen:screen, update:function(){}};
    var mainWindow = {screen:screen, professionalWindowTransitionKind:'maximize',
        usableW:1920, usableH:1040, glowPadding:12,
        stopMaximizeFxAnimations:function(){stopCount++;}};
    var windowFrameCapture = {
        geometry:function(){return {origin:Qt.point(0,0),size:Qt.size(1920,1080)};},
        release:function(url){released.push(url);}
    };
    var transitionExperiment = {monotonicMs:function(){return 100;}};
    var width=1920,height=1080,overlayX=0,overlayY=0;
    var sourceBounds=Qt.rect(208,138,880,680),targetBounds=Qt.rect(0,0,1920,1040);
    var sourceGrab={url:'source',nativeFrame:true,nativeOrigin:Qt.point(196,126),
        physicalSize:Qt.size(904,704),logicalSize:Qt.size(904,704),
        globalOrigin:Qt.point(196,126),dpr:1,
        contentUv:Qt.rect(12/904,12/704,880/904,680/704)};
    var headerMetrics=Qt.rect(72,500,0,0),nativeGeometry=null;
    var endpointPlanReady=false,plannedTargetCapture=null;
    var sourceCaptureUv=Qt.rect(0,0,1,1),targetCaptureUv=Qt.rect(0,0,1,1);
    var targetGrab=null,closingSurface=false,motionMs=0,commandMs=0;
    var durationMs=350,transferStart=.55,qualificationFailure=false,qualificationReason='';
    var traceEvents=[],stage='moving',targetReady=false;
    function snapshot(){return JSON.stringify([sourceBounds,targetBounds,
        sourceCaptureUv,targetCaptureUv,headerMetrics]);}
    function resultFromPlan(){return {
        url:'target',nativeFrame:true,
        nativeOrigin:Qt.point(plannedTargetCapture.nativeOrigin.x,plannedTargetCapture.nativeOrigin.y),
        physicalSize:Qt.size(plannedTargetCapture.physicalSize.width,plannedTargetCapture.physicalSize.height),
        logicalSize:Qt.size(plannedTargetCapture.logicalSize.width,plannedTargetCapture.logicalSize.height),
        contentUv:Qt.rect(targetCaptureUv.x,targetCaptureUv.y,targetCaptureUv.width,targetCaptureUv.height)
    };}
    """
    result = js.evaluate(setup + "\n" + "\n".join(qml_function(QML.read_text(encoding="utf-8"), name) for name in FUNCTIONS))
    assert not result.isError(), result.toString()
    yield js
    del js
    assert app is not None


def evaluate(js, code):
    result = js.evaluate(code)
    assert not result.isError(), result.toString()
    return result


def test_ready_target_preserves_frozen_trajectory_and_independent_uvs(engine):
    assert evaluate(engine, "prepareNativeGeometry()").toBool()
    assert evaluate(engine, "sourceCaptureUv.x !== targetCaptureUv.x").toBool()
    before = evaluate(engine, "snapshot()").toString()
    evaluate(engine, "setTargetGrab(resultFromPlan(),500)")
    assert evaluate(engine, "snapshot()").toString() == before
    assert evaluate(engine, "targetGrab.url").toString() == "target"
    assert not evaluate(engine, "qualificationFailure").toBool()


def test_restore_plan_preserves_normal_host_padding(engine):
    evaluate(engine, """
        mainWindow.professionalWindowTransitionKind='restore';
        sourceGrab={url:'source',nativeFrame:true,nativeOrigin:Qt.point(0,0),
            physicalSize:Qt.size(1920,1040),logicalSize:Qt.size(1920,1040),
            globalOrigin:Qt.point(0,0),dpr:1,contentUv:Qt.rect(0,0,1,1)};
        targetBounds=Qt.rect(208,138,880,680);
    """)
    assert evaluate(engine, "prepareNativeGeometry()").toBool()
    assert evaluate(engine, "plannedTargetCapture.nativeOrigin.x").toInt() == 196
    assert evaluate(engine, "plannedTargetCapture.physicalSize.width").toInt() == 904
    assert evaluate(engine, "targetBounds.x").toInt() == 208
    assert evaluate(engine, "targetMatchesPlan(resultFromPlan(),500)").toBool()


@pytest.mark.parametrize("mutation", [
    "result.nativeOrigin.x+=1", "result.physicalSize.width+=1",
    "result.contentUv.x+=1/result.physicalSize.width",
])
def test_target_pixel_mapping_mismatch_rejects_without_retargeting(engine, mutation):
    assert evaluate(engine, "prepareNativeGeometry()").toBool()
    before = evaluate(engine, "snapshot()").toString()
    evaluate(engine, "var result=resultFromPlan();" + mutation + ";setTargetGrab(result,500)")
    assert evaluate(engine, "snapshot()").toString() == before
    assert evaluate(engine, "qualificationFailure").toBool()
    assert evaluate(engine, "targetGrab===null").toBool()
    assert evaluate(engine, "released.length").toInt() == 1
    assert evaluate(engine, "stopCount").toInt() == 1


def test_cross_monitor_source_transform_is_rejected_before_motion(engine):
    evaluate(engine, "surface.screen={name:'secondary', virtualX:1920, virtualY:0, width:1920, height:1080, devicePixelRatio:1}")
    assert not evaluate(engine, "prepareNativeGeometry()").toBool()
    assert evaluate(engine, "qualificationReason").toString() == "cross-monitor-endpoint-plan-unavailable"


def test_distinct_same_monitor_screen_wrappers_are_accepted(engine):
    evaluate(engine, "surface.screen=JSON.parse(JSON.stringify(mainWindow.screen))")
    assert not evaluate(engine, "mainWindow.screen === surface.screen").toBool()
    assert evaluate(engine, "prepareNativeGeometry()").toBool()


@pytest.mark.parametrize("mutation", [
    "surface.screen.name='secondary'", "surface.screen.virtualX+=1",
    "surface.screen.virtualY+=1", "surface.screen.width+=1",
    "surface.screen.height+=1", "surface.screen.devicePixelRatio=1.25",
    "delete surface.screen.name", "delete surface.screen.width",
    "surface.screen.devicePixelRatio=0",
])
def test_screen_descriptor_or_pixel_transform_difference_is_rejected(engine, mutation):
    evaluate(engine, "surface.screen=JSON.parse(JSON.stringify(mainWindow.screen));" + mutation)
    assert not evaluate(engine, "prepareNativeGeometry()").toBool()
    assert not evaluate(engine, "endpointPlanReady").toBool()
    assert evaluate(engine, "qualificationReason").toString() == "cross-monitor-endpoint-plan-unavailable"


def test_real_hidden_qml_windows_share_qscreen_but_have_distinct_wrappers():
    # A separate process permits QGuiApplication while the JS tests use a
    # QCoreApplication. The offscreen windows remain hidden and start no GPU
    # scene or WebEngine process.
    helpers = "\n".join(qml_function(QML.read_text(encoding="utf-8"), name)
                        for name in ("near", "samePhysicalScreen"))
    qml = """import QtQuick
import QtQuick.Window
Window {
    id: first; visible: false
    property Window peer: Window { id: second; objectName: "screenWrapperPeer"; visible: false }
    property bool wrappersMatch: first.screen === second.screen
    property bool descriptorsMatch: samePhysicalScreen(first.screen, second.screen)
""" + helpers + "\n}"
    script = """
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtQuick import QQuickWindow
from shiboken6 import getCppPointer
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(QML_SOURCE.encode('utf-8'), QUrl('file:///hidden_screen_wrapper_test.qml'))
first = component.create()
assert first is not None, [error.toString() for error in component.errors()]
second = first.findChild(QQuickWindow, 'screenWrapperPeer')
assert second is not None
assert not first.isVisible() and not second.isVisible()
assert getCppPointer(first.screen())[0] == getCppPointer(second.screen())[0]
assert first.property('wrappersMatch') is False
assert first.property('descriptorsMatch') is True
first.deleteLater()
app.processEvents()
"""
    result = subprocess.run(
        [sys.executable, "-c", "QML_SOURCE=" + repr(qml) + "\n" + script],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fractional_dpi_negative_origin_uses_native_source_anchor(engine):
    evaluate(engine, """
        overlayX=-960;
        windowFrameCapture.geometry=function(){
            return {origin:Qt.point(-1200,0),size:Qt.size(2400,1350)};
        };
        sourceGrab.nativeOrigin=Qt.point(-1180,158);
        sourceGrab.globalOrigin=Qt.point(-944,126);
        sourceGrab.physicalSize=Qt.size(1130,880);
        sourceGrab.dpr=1.25;
    """)
    assert evaluate(engine, "prepareNativeGeometry()").toBool()
    assert evaluate(engine, "plannedTargetCapture.nativeOrigin.x").toInt() == -1200
    assert evaluate(engine, "plannedTargetCapture.physicalSize.width").toInt() == 2400
    assert evaluate(engine, "targetBounds.x").toInt() == 0
    assert evaluate(engine, "targetMatchesPlan(resultFromPlan(),500)").toBool()
