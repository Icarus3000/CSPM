import sys
import os
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer, QObject, Signal, Slot

class Runner(QObject):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        QTimer.singleShot(1000, self.click_button)
        QTimer.singleShot(2000, QGuiApplication.instance().quit)

    def click_button(self):
        print("--- CLICKING BUTTON ---")
        root = self.engine.rootObjects()[0]
        button = root.findChild(QObject, "myButton")
        if button:
            button.clicked.emit()
        else:
            # just execute a script on the root
            pass

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.load(os.path.abspath('src/qml/test_drag.qml'))

runner = Runner(engine)

sys.exit(app.exec())
