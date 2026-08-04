import sys
import os
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from PySide6.QtCore import qInstallMessageHandler

def qt_message_handler(mode, context, message):
    print(message, flush=True)

qInstallMessageHandler(qt_message_handler)

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.load(os.path.abspath('src/qml/test_vertical_drag.qml'))

if not engine.rootObjects():
    sys.exit(-1)

sys.exit(app.exec())
