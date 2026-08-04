import sys
import os
import time
import json

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "python")))

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer, Property

# Mock app controller
class MockAppController(QGuiApplication):
    def __init__(self, args):
        super().__init__(args)
        self._option3Favorites = ""

    def get_favs(self):
        return self._option3Favorites

    def set_favs(self, v):
        self._option3Favorites = v

    option3Favorites = Property(str, get_favs, set_favs)


app = MockAppController(sys.argv)
engine = QQmlApplicationEngine()

engine.rootContext().setContextProperty("app", app)
engine.addImportPath(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "qml")))

qml_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "qml", "views", "MainContent.qml"))
engine.load(qml_file)

if not engine.rootObjects():
    sys.exit(-1)

root = engine.rootObjects()[0]
root.setProperty("appRef", app)

def test_fav():
    print("Testing favorite...")
    # Add a tab
    root.option3CreateTab("dashboard", {}, False, False)
    
    tabs = root.property("option3OpenTabs")
    if not tabs:
        print("No tabs created!")
    else:
        # We need to get the tabId from the QJSValue
        tab_js = tabs.property(0)
        tab_id = tab_js.property("id").toString()
        print(f"Tab ID: {tab_id}")
        
        # Favorite the tab
        res = root.option3FavoriteTab(tab_id)
        print(f"option3FavoriteTab result: {res}")
        
        # Check favs
        favs = root.property("option3Favorites")
        print(f"QML option3Favorites property length: {favs.property('length').toInt() if favs else 'null'}")
        
        # Print AppController favs
        print(f"app.option3Favorites: {app._option3Favorites}")

    app.quit()
    
QTimer.singleShot(1000, test_fav)
app.exec()
