"""Run the QML endpoint contract in a JS engine without desktop/GPU creation."""
from pathlib import Path
import re

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine


QML = Path(__file__).resolve().parents[1] / "src/qml/CleanRoomTransitionSurface.qml"
FUNCTIONS = (
    "elapsed", "record", "reject", "prepareNativeGeometry", "nearestNativePixel",
    "near", "targetMatchesPlan", "capturedContentBounds", "nextFrame", "setTargetGrab",
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
    var screen = {}, stopCount = 0, released = [];
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
    evaluate(engine, "surface.screen={}")
    assert not evaluate(engine, "prepareNativeGeometry()").toBool()
    assert evaluate(engine, "qualificationReason").toString() == "cross-monitor-endpoint-plan-unavailable"


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
