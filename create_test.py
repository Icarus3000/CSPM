import sys
import os

# Create a small script that overrides the QML property update and prints the result
script = """
import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    width: 200
    height: 200
    visible: true
    Component.onCompleted: {
        console.log("TESTING FAVS LOGIC!")
        Qt.quit()
    }
}
"""

with open("test_favs2.qml", "w") as f:
    f.write(script)
