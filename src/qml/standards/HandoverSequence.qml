import QtQuick

ParallelAnimation {
    id: root

    // FIX: Use 'var' so we can accept Windows or Items
    property var splashWindow
    property var mainWindow
    
    property int durationMs: 200

    // === RULE 1: SEAMLESS TRANSITION ===
    // 1. Splash fades OUT (Linear)
    // 2. Main Glow fades IN (Linear)
    
    NumberAnimation {
        target: root.splashWindow
        property: "opacity"
        from: 1.0
        to: 0.0
        duration: root.durationMs
        easing.type: Easing.Linear
    }

    NumberAnimation {
        target: root.mainWindow
        property: "fadeProgress" // Drives Glow AND Border Opacity
        from: 0.0
        to: 1.0
        duration: root.durationMs
        easing.type: Easing.Linear
    }

    onFinished: {
        // Cleanup state
        if (root.splashWindow) {
            root.splashWindow.visible = false
            root.splashWindow.opacity = 1.0
        }
        if (root.mainWindow) {
            // Ensure the border and glow stick to 100% after anim
            root.mainWindow.fadeProgress = 1.0
        }
    }
}
