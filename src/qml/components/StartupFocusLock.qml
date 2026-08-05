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
        savedFlags = mainWindow.flags;
        mainWindow.flags = mainWindow.flags | Qt.WindowStaysOnTopHint;
        focusTimer.start();
        if (mainWindow._requestActivateIfFocusable) {
            mainWindow._requestActivateIfFocusable(mainWindow);
        }
    }

    function endFocusLock() {
        if (!mainWindow || !openingAnimRunning) return;
        openingAnimRunning = false;
        focusTimer.stop();
        if (savedFlags !== null) {
            mainWindow.flags = savedFlags;
        }
        if (mainWindow._requestActivateIfFocusable) {
            mainWindow._requestActivateIfFocusable(mainWindow);
        }
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
            // Avoid repeated requestActivate() storms during splash handoff.
            if (focusLockManager.focusPulseCount < 2) {
                if (focusLockManager.mainWindow._requestActivateIfFocusable) {
                    focusLockManager.mainWindow._requestActivateIfFocusable(focusLockManager.mainWindow);
                }
            } else if (focusLockManager.mainWindow.raise) {
                focusLockManager.mainWindow.raise();
            }
            focusLockManager.focusPulseCount += 1;
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
