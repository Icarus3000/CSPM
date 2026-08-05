pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "components"
import "views"

ApplicationWindow {
    id: overlayWin
    title: "CSPM-OpeningOverlay"
    objectName: "CSPMOpeningOverlay"
    
 // Pin overlay to the same monitor as the main window (prevents primary-monitor splash).
 // If targetScreen is set in Main.qml, use it. Otherwise fall back to mainWindow.screen.
 screen: (overlayWin.mainWindow && overlayWin.mainWindow.targetScreen)
     ? overlayWin.mainWindow.targetScreen
     : (overlayWin.mainWindow ? overlayWin.mainWindow.screen : null)
    // Reference to main window for state synchronization
    property var mainWindow: null
    property var jellyController: null
    
    // Position and size: Dynamically calculated to match main window with 500px padding
    // These will be set by createAnimationOverlay() in Main.qml
    property int overlayX: 0
    property int overlayY: 0
    property int overlayWidth: 2220
    property int overlayHeight: 1920
    property int contentX: 0  // Position of animation canvas within overlay
    property int contentY: 0
    
    x: overlayX
    y: overlayY
    width: overlayWidth
    height: overlayHeight
    
    visible: true
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
    opacity: 1.0
    property bool isDestroying: false
    property bool isAnimationComplete: false

    function requestActivateIfFocusable(windowRef) {
        if (!windowRef || !windowRef.requestActivate) return false
        try {
            var flags = windowRef.flags
            if ((flags & Qt.WindowDoesNotAcceptFocus) === Qt.WindowDoesNotAcceptFocus) {
                return false
            }
            if ((flags & Qt.Tool) === Qt.Tool || (flags & Qt.Popup) === Qt.Popup || (flags & Qt.ToolTip) === Qt.ToolTip) {
                return false
            }
            windowRef.requestActivate()
            return true
        } catch (e) {
        }
        return false
    }
    
    // For compatibility with MainContent windowRef interface
    readonly property bool isMaximized: (visibility === Window.Maximized)

    onIsAnimationCompleteChanged: {
        if (isAnimationComplete) {
            // Make absolutely sure overlay is on top and focused when it becomes interactive
            try {
                overlayWin.raise();
                overlayWin.requestActivateIfFocusable(overlayWin);
                if (overlayWin.contentItem && overlayWin.contentItem.forceActiveFocus) {
                    overlayWin.contentItem.forceActiveFocus();
                }
            } catch (e) {
            }
        }
    }
    
    function closeOverlay(reason) {
        if (isDestroying) {
            return;
        }
        isDestroying = true;
        overlayWin.visible = false;
        overlayWin.close();
        Qt.callLater(function() {
            overlayWin.destroy();
        });
    }
    
    function requestCloseAnimation() {
        if (overlayWin.mainWindow) {
            overlayWin.mainWindow.beginCloseSequence();
        }
    }
    
    function openThemePicker() {
        if (overlayWin.mainWindow && overlayWin.mainWindow.openThemePicker) {
            return overlayWin.mainWindow.openThemePicker();
        }
        return false;
    }

    
    // ANIMATION CANVAS: Positioned to extend 500px beyond settled window edges
    Item {
        id: animationCanvas
        x: overlayWin.contentX
        y: overlayWin.contentY
        width: (overlayWin.mainWindow && overlayWin.mainWindow.finalW) ? overlayWin.mainWindow.finalW : 1220
        height: (overlayWin.mainWindow && overlayWin.mainWindow.finalH) ? overlayWin.mainWindow.finalH : 920
        z: 100
        
        // Jelly transform applied here - animation has full freedom
        transform: [
            Scale {
                origin.x: animationCanvas.width / 2
                origin.y: animationCanvas.height / 2
                xScale: overlayWin.jellyController ? overlayWin.jellyController.scaleX : 1.0
                yScale: overlayWin.jellyController ? overlayWin.jellyController.scaleY : 1.0
            },
            Translate {
                x: overlayWin.jellyController ? overlayWin.jellyController.transX : 0
                y: overlayWin.jellyController ? overlayWin.jellyController.transY : 0
            }
        ]
        
        // ACTUAL CONTENT: ChromeSurface with MainContent for animation
        Item {
            id: contentWrapper
            anchors.fill: parent
            
            ChromeSurface {
                id: unifiedChrome
                anchors.fill: parent
                farGlowEnabled: !(overlayWin.mainWindow && overlayWin.mainWindow.lowPerformanceMode)
                glowRadiusNear: (overlayWin.mainWindow && overlayWin.mainWindow.lowPerformanceMode) ? 10 : 18
                glowRadiusFar: (overlayWin.mainWindow && overlayWin.mainWindow.lowPerformanceMode) ? 20 : 36
                plasmaOpacity: (overlayWin.mainWindow && overlayWin.mainWindow.lowPerformanceMode) ? 0.72 : 1.0
                lowFxMode: !!(overlayWin.mainWindow && overlayWin.mainWindow.lowPerformanceMode)
                interactionBoost: 0.14
                flairEnabled: false
                t: (overlayWin.mainWindow && overlayWin.mainWindow.t) ? overlayWin.mainWindow.t : ({
                    "bg": "#000000", "accent": "#2979FF", "text": "#FFFFFF", "glow": "#FF1744"
                })
                cornerRadius: 16

                MainContent {
                    anchors.fill: parent
                    t: (overlayWin.mainWindow && overlayWin.mainWindow.t) ? overlayWin.mainWindow.t : ({})
                    appRef: (overlayWin.mainWindow && overlayWin.mainWindow.appRef) ? overlayWin.mainWindow.appRef : null
                    isInteractive: overlayWin.isAnimationComplete  // Content becomes interactive when animation stops
                    windowRef: overlayWin
                }
            }
        }
    }
    
    Component.onCompleted: {
    }

    Connections {
        target: overlayWin.mainWindow
        function onIsClosingChanged() {
            if (overlayWin.mainWindow && overlayWin.mainWindow.isClosing) {
                overlayWin.closeOverlay("main-closing");
            }
        }
        function onForceCloseChanged() {
            if (overlayWin.mainWindow && overlayWin.mainWindow.forceClose) {
                overlayWin.closeOverlay("main-force-close");
            }
        }
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            overlayWin.closeOverlay("aboutToQuit");
        }
    }
    
    onClosing: (close) => {
        if (!isDestroying) {
            overlayWin.closeOverlay("overlay-onClosing");
        }
        close.accepted = true;
    }
}
