import QtQuick

Item {
    id: focusLockManager

    property var mainWindow: null
    property bool openingAnimRunning: false
    property var savedFlags: null
    property int focusPulseCount: 0

    function beginFocusLock() {
        if (!mainWindow || mainWindow.detachedMode) return;
        openingAnimRunning = true;
        focusPulseCount = 0;
        // A startup animation must not turn the application into a topmost
        // window or repeatedly take focus from other programs.
        if (mainWindow._requestActivateIfFocusable) {
            mainWindow._requestActivateIfFocusable(mainWindow);
        }
    }

    function endFocusLock() {
        if (!mainWindow || !openingAnimRunning) return;
        openingAnimRunning = false;
        focusTimer.stop();
    }

    Timer {
        id: focusTimer
        interval: 50
        repeat: true
        running: false
        onTriggered: {
            if (!focusLockManager.openingAnimRunning || !focusLockManager.mainWindow) {
                stop();
                return;
            }
            // This component is retained for compatibility only.  It does
            // not reassert activation after the initial launch request.
            focusLockManager.endFocusLock();
        }
    }

    Component.onCompleted: {
        beginFocusLock();
    }

    Connections {
        target: focusLockManager.mainWindow
        function onIsSettledChanged() {
            if (!focusLockManager.mainWindow || !focusLockManager.mainWindow.isSettled) return;
            focusLockManager.endFocusLock();
            if (focusLockManager.mainWindow.triggerDeferredBackendBoot) {
                focusLockManager.mainWindow.triggerDeferredBackendBoot();
            }
        }
    }
}
