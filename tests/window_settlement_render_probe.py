"""Real Qt GPU pixel checks; run outside sandbox, never persist screenshots."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow

ROOT = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlEngine()
fixture = QQmlComponent(engine)
fixture.setData(b'''
import QtQuick
import QtQuick.Window
Window {
    width: 640; height: 400; x: 50; y: 50; visible: true; color: "white"
    property alias scene: scene
    Rectangle {
        id: scene; objectName: "fixtureScene"; anchors.fill: parent; color: width > 700 ? "#e0ecfa" : "#faf0e0"
        Rectangle { width: parent.width; height: 72; color: "white" }
        Text { x: 50; y: 24; text: "CSPM title"; font.family: "Segoe UI"; font.pixelSize: 18 }
        Text { x: parent.width - 90; y: 26; text: "\\uE922"; font.family: "Segoe MDL2 Assets"; font.pixelSize: 13 }
        Rectangle { x: 24; y: 28; width: 12; height: 13; color: "magenta" }
        Rectangle { x: parent.width-46; y: 28; width: 12; height: 13; color: "magenta" }
        Rectangle { x: 30; y: 110; width: parent.width-60; height: parent.height-140; color: "#4477aa" }
    }
}
''', QUrl.fromLocalFile(str(ROOT/'tests/window_settlement_fixture.qml')))
assert not fixture.isError(), [e.toString() for e in fixture.errors()]
window = fixture.create()
scene = window.findChild(QQuickItem, 'fixtureScene')
component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT/'src/qml/WindowTransitionSurface.qml')))
assert not component.isError(), [e.toString() for e in component.errors()]
grabs = []
surfaces = []
failures = []
results = []
source_sizes = [(640, 400), (960, 650)]
pair = 0
sample_states = [(False, p, 0.0, 0.0) for p in (0.0, 0.5, 0.85, 1.0)] + [
    (True, 0.0, 0.0, 0.0),
    (True, 0.0, 0.5, 0.0),
    (True, 0.0, 0.5, 0.5),
    (True, 0.0, 0.0, 0.85),
    (True, 0.0, 0.85, 1.0),
]

def guard(fn):
    def call(*args):
        try:
            fn(*args)
        except Exception as exc:
            failures.append(repr(exc))
            app.exit(1)
    return call

def grab(item, callback):
    result = item.grabToImage()
    assert result is not None
    grabs.append(result)
    result.ready.connect(guard(lambda: callback(result)))

def begin_pair():
    w, h = source_sizes[pair]
    window.setWidth(w)
    window.setHeight(h)
    QTimer.singleShot(100, guard(lambda: grab(scene, source_ready)))

def source_ready(result):
    global source_grab
    source_grab = result
    w, h = source_sizes[1-pair]
    window.setWidth(w)
    window.setHeight(h)
    QTimer.singleShot(100, guard(lambda: grab(scene, target_ready)))

def target_ready(result):
    global surface, renderer, target_grab, sample_index
    target_grab = result
    sw, sh = source_sizes[pair]
    tw, th = source_sizes[1-pair]
    from PySide6.QtCore import QRectF
    surface = component.createWithInitialProperties(dict(
        mainWindow=window, sourceGrab={'url':source_grab.url()}, targetGrab={'url':target_grab.url()},
        sourceBounds=QRectF(0, 0, sw, sh), targetBounds=QRectF(0, 0, tw, th),
        headerMetrics=QRectF(72, 120, 120, 0), overlayX=50, overlayY=50,
        overlayWidth=960, overlayHeight=650, stage='probe', visible=True))
    assert surface, [e.toString() for e in component.errors()]
    surfaces.append(surface)
    renderer = surface.findChild(QObject, 'CSPMWindowTransitionRenderer')
    assert renderer
    engine.globalObject().setProperty('_renderSurface', engine.newQObject(surface))
    sample_index = 0
    sample()

def sample():
    early, legacy, preparation, settlement = sample_states[sample_index]
    surface.setProperty('earlyMotionEnabled', early)
    renderer.setProperty('progress', legacy)
    renderer.setProperty('preparationProgress', preparation)
    renderer.setProperty('settlementProgress', settlement)
    # Before capture readiness the target texture is the source fallback.
    surface.setProperty('targetGrab', None if early and settlement == 0.0 else {'url':target_grab.url()})
    surface.update()
    QTimer.singleShot(100, guard(lambda: grab(surface.contentItem(), sampled)))

def sampled(result):
    global sample_index, pair
    early, legacy, preparation, settlement = sample_states[sample_index]
    p = preparation + (1.0-preparation)*settlement if early else legacy
    sw, sh = source_sizes[pair]
    tw, th = source_sizes[1-pair]
    w, h = round(sw+(tw-sw)*p), round(sh+(th-sh)*p)
    image = result.image()
    # Only coordinate/count measurements leave RAM.
    xs, ys = [], []
    for y in range(20, 50):
        for x in range(w):
            c = image.pixelColor(x, y)
            if c.red() > 245 and c.green() < 10 and c.blue() > 245:
                xs.append(x)
                ys.append(y)
    assert len(xs) == 2*12*13, (pair, p, len(xs), image.size().toTuple(),
        image.pixelColor(30,34).getRgb(), source_grab.image().pixelColor(30,34).getRgb(),
        renderer.property('log'), engine.evaluate('JSON.stringify(_renderSurface.contentItem.children.map(function(c) { return {source:String(c.source), status:c.status, width:c.width, height:c.height}; }))').toString())
    assert min(ys) == 28 and max(ys) == 40, (pair, p, min(ys), max(ys))
    assert min(xs) == 24 and max(xs) == w-35, (pair, p, min(xs), max(xs), w)
    endpoint_error = None
    if p in (0.0, 1.0):
        expected = source_grab.image() if p == 0 else target_grab.image()
        # Compare every channel in RAM without millions of QColor allocations.
        actual_rgba = image.copy(0, 0, w, h).convertToFormat(QImage.Format_RGBA8888)
        expected_rgba = expected.convertToFormat(QImage.Format_RGBA8888)
        assert actual_rgba.size() == expected_rgba.size()
        endpoint_error = max(abs(a-b) for a,b in zip(actual_rgba.constBits(), expected_rgba.constBits()))
        assert endpoint_error <= 1, (pair, p, endpoint_error)
    results.append(dict(direction='maximize' if pair == 0 else 'restore', progress=p,
                        early_motion=early, preparation=preparation, settlement=settlement,
                        marker_count=len(xs), marker_height=13, endpoint_max_channel_error=endpoint_error))
    sample_index += 1
    if sample_index < len(sample_states):
        QTimer.singleShot(0, guard(sample))
    else:
        surface.close()
        pair += 1
        if pair < 2:
            QTimer.singleShot(0, guard(begin_pair))
        else:
            app.exit(0)

QTimer.singleShot(45000, lambda: (failures.append('GPU probe timeout'), app.exit(2)))
QTimer.singleShot(100, guard(begin_pair))
code = app.exec()
print(json.dumps({'samples':results, 'failures':failures}), flush=True)
raise SystemExit(code)
