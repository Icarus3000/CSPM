"""Real two-window GPU comparison on actual screen DPIs; images stay in RAM."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRectF, QSize, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/python'))
from backend.window_frame_capture import WindowFrameCapture
app = QGuiApplication([])
engine = QQmlEngine()
capture_service = WindowFrameCapture(engine)
engine.rootContext().setContextProperty('windowFrameCapture', capture_service)
fixture = QQmlComponent(engine)
fixture.setData(b'''
import QtQuick
import QtQuick.Window
Window {
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
    color: "transparent"
    Rectangle {
        x: 14; y: 14; width: parent.width-28; height: parent.height-28
        radius: 12; color: "#faf8f3"; border.color: "#244667"; border.width: 1
        Text { x: 50; y: 24; text: "CSPM title"; font.family: "Segoe UI"; font.pixelSize: 18 }
        Text { x: parent.width-90; y: 26; text: "\\uE922"; font.family: "Segoe MDL2 Assets"; font.pixelSize: 13 }
        Rectangle { x: 24; y: 28; width: 12; height: 13; color: "magenta" }
        Rectangle { x: parent.width-46; y: 28; width: 12; height: 13; color: "magenta" }
        Rectangle { x: 30; y: 110; width: parent.width-60; height: parent.height-140; color: "#4477aa" }
    }
}
''', QUrl.fromLocalFile(str(ROOT/'tests/window_handoff_fixture.qml')))
assert not fixture.isError(), [e.toString() for e in fixture.errors()]
window = fixture.create()
component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT/'src/qml/WindowTransitionSurface.qml')))
assert not component.isError(), [e.toString() for e in component.errors()]
cases = [(screen, size, offset) for screen in app.screens()
         for size in ((668,428), (988,678)) for offset in (0,45,-86)]
index = 0
surfaces, results, failures = [], [], []

def guard(fn):
    def call(*args):
        try:
            fn(*args)
        except Exception as exc:
            failures.append(repr(exc))
            app.exit(1)
    return call

def begin():
    screen, size, offset = cases[index]
    window.setScreen(screen)
    area = screen.availableGeometry()
    window.setGeometry(area.x()+80+offset, area.y()+70+offset//2, *size)
    window.show()
    QTimer.singleShot(150, guard(capture))

def capture():
    global live_image
    live_image = window.grabWindow()
    frame = capture_service.capture(window)
    assert frame
    QTimer.singleShot(0, guard(lambda: ready(frame)))

def ready(result):
    global surface, frame, live_image
    # A screen-DPI change can invalidate nodes after the preceding grab; compare
    # the captured frame with the live scene after the same synchronization.
    live_image = window.grabWindow()
    screen, size, offset = cases[index]
    frame = dict(result, contentUv=QRectF(14/size[0],14/size[1],(size[0]-28)/size[0],(size[1]-28)/size[1]))
    area = screen.availableGeometry()
    surface = component.createWithInitialProperties(dict(
        mainWindow=window, sourceGrab=frame, targetGrab=frame,
        headerMetrics=QRectF(72,120,120,0), screen=screen,
        overlayX=area.x()-58, overlayY=area.y()-38,
        overlayWidth=1280, overlayHeight=900, stage='probe', visible=False))
    assert surface, [e.toString() for e in component.errors()]
    surfaces.append(surface)
    engine.globalObject().setProperty('_s', engine.newQObject(surface))
    value = engine.evaluate('_s.prepareNativeGeometry(); _s.visible=true;')
    assert not value.isError(), value.toString()
    renderer = surface.findChild(QObject, 'CSPMWindowTransitionRenderer')
    renderer.setProperty('progress', 1.0)
    surface.update()
    QTimer.singleShot(150, guard(compare))

def compare():
    global index
    image = surface.grabWindow()
    dpr = surface.devicePixelRatio()
    native = capture_service.geometry(surface)['origin']
    x = round(frame['nativeOrigin'].x()-native.x())
    y = round(frame['nativeOrigin'].y()-native.y())
    actual = image.copy(x,y,live_image.width(),live_image.height()).convertToFormat(QImage.Format_RGBA8888)
    expected = live_image.convertToFormat(QImage.Format_RGBA8888)
    assert actual.size() == expected.size()
    error = max(abs(a-b) for a,b in zip(actual.constBits(), expected.constBits()))
    captured = capture_service.provider.requestImage(frame['url'].split('/')[-1], QSize(), QSize()).convertToFormat(QImage.Format_RGBA8888)
    assert captured.size() == expected.size(), (captured.size().toTuple(),expected.size().toTuple())
    capture_error = max(abs(a-b) for a,b in zip(captured.constBits(), expected.constBits()))
    screen, size, offset = cases[index]
    results.append(dict(screen=screen.name(), dpr=dpr, size=size, offset=offset,
                        max_channel_error=error, capture_error=capture_error, pixels=expected.width()*expected.height()))
    assert error == 0 and capture_error == 0, results[-1]
    surface.closeOverlay('probe-complete')
    assert not capture_service.provider._frames, 'Transition frame retained after release'
    index += 1
    if index < len(cases):
        QTimer.singleShot(0, guard(begin))
    else:
        app.exit(0)

QTimer.singleShot(90000, lambda: (failures.append('GPU probe timeout'), app.exit(2)))
QTimer.singleShot(0, guard(begin))
code = app.exec()
print(json.dumps(dict(samples=results, failures=failures)), flush=True)
raise SystemExit(code)
