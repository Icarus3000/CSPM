"""Short-lived, in-memory native Quick window frames for transition endpoints."""
from threading import Lock
import logging
import sys

from PySide6.QtCore import QObject, QPointF, QSize, QSizeF, Slot
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow


class WindowFrameProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self._frames = {}
        self._serial = 0
        self._lock = Lock()

    def publish(self, image):
        with self._lock:
            self._serial += 1
            key = str(self._serial)
            self._frames[key] = QImage(image)
        return "image://windowframes/" + key

    def release(self, url):
        key = url.removeprefix("image://windowframes/")
        with self._lock:
            self._frames.pop(key, None)

    def requestImage(self, image_id, size, requested_size):
        # Keep the physical framebuffer intact; never resize it to requestedSize.
        with self._lock:
            image = QImage(self._frames.get(image_id, QImage()))
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image


class WindowFrameCapture(QObject):
    def __init__(self, engine):
        super().__init__(engine)
        self.provider = WindowFrameProvider()
        engine.addImageProvider("windowframes", self.provider)

    @Slot(QObject, result="QVariantMap")
    def geometry(self, window):
        if not isinstance(window, QQuickWindow):
            return {}
        # Creating the hidden native surface first resolves Windows' actual
        # monitor/DPI placement before any transition pixels become visible.
        hwnd = int(window.winId())
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            rect, origin = wintypes.RECT(), wintypes.POINT()
            if not user.GetClientRect(hwnd, ctypes.byref(rect)) or not user.ClientToScreen(hwnd, ctypes.byref(origin)):
                return {}
            return dict(origin=QPointF(origin.x, origin.y), size=QSize(rect.right, rect.bottom))
        dpr = window.devicePixelRatio()
        origin = window.contentItem().mapToGlobal(QPointF(0, 0))
        screen = window.screen().geometry()
        return dict(origin=QPointF(screen.x()+(origin.x()-screen.x())*dpr,
                                  screen.y()+(origin.y()-screen.y())*dpr),
                    size=QSize(round(window.width()*dpr), round(window.height()*dpr)))

    @Slot(QObject, result="QVariantMap")
    def capture(self, window):
        # Invoked by QML on the GUI thread, only at the two endpoint gates.
        if not isinstance(window, QQuickWindow) or not window.isVisible():
            return {}
        try:
            image = window.grabWindow()
        except RuntimeError:
            logging.getLogger(__name__).exception("Window frame capture failed")
            return {}
        if image.isNull():
            return {}
        dpr = window.devicePixelRatio()
        screen = window.screen()
        if screen is None:
            return {}
        screen = screen.geometry()
        image.setDevicePixelRatio(1.0)
        geometry = self.geometry(window)
        if not geometry:
            return {}
        return dict(url=self.provider.publish(image), nativeFrame=True,
                    nativeOrigin=geometry['origin'],
                    physicalSize=QSize(image.width(), image.height()),
                    logicalSize=QSizeF(window.width(), window.height()), dpr=dpr,
                    globalOrigin=window.contentItem().mapToGlobal(QPointF(0, 0)),
                    screenOrigin=QPointF(screen.x(), screen.y()))

    @Slot(str)
    def release(self, url):
        self.provider.release(url)
