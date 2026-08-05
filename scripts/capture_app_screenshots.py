import sys
import os
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtQml import QQmlApplicationEngine

os.environ["QT_QPA_PLATFORM"] = "offscreen"

def capture_and_exit(app, engine):
    output_dir = Path(r"C:\CSPM_EVIDENCE\screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    root_objects = engine.rootObjects()
    if not root_objects:
        print("No root objects to capture.")
        sys.exit(1)
        
    main_window = root_objects[0]
    
    # Grab the window image
    image = main_window.grabToImage()
    
    def save_image(result):
        filepath = output_dir / "app_shell_automated.png"
        result.save(str(filepath))
        print(f"Captured: {filepath}")
        sys.exit(0)
        
    image.connect("ready", lambda: save_image(image))
    
    # Failsafe
    QTimer.singleShot(2000, lambda: sys.exit(2))

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    
    engine = QQmlApplicationEngine()
    
    # Load test window
    test_qml = Path(__file__).resolve().parent.parent / "src" / "qml" / "scratch_test.qml"
    engine.load(str(test_qml))
    
    # Set a timer to capture after 2 seconds
    QTimer.singleShot(2000, lambda: capture_and_exit(app, engine))
    
    sys.exit(app.exec())
