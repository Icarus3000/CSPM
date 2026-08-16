import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "components"
import "views"
import "standards"

ApplicationWindow {
    id: closingOverlayWin
    title: "CSPM-ClosingOverlay"
    objectName: "CSPMClosingOverlay"

    property var mainWindow: null
    property var jellyController: null

    property int overlayX: 0
    property int overlayY: 0
    property int overlayWidth: 1
    property int overlayHeight: 1
    property int contentX: 0
    property int contentY: 0
    property int contentWidth: 1
    property int contentHeight: 1
    property real targetX: 0
    property real targetY: 0
    property string snapshotUrl: ""

    property bool isDestroying: false
    property bool handoffReadySignaled: false
    property bool phaseLoggingEnabled: (mainWindow && mainWindow.phaseLoggingEnabled !== undefined)
        ? !!mainWindow.phaseLoggingEnabled : true

    property real animCenterX: contentX + (contentWidth / 2.0)
    property real animCenterY: contentY + (contentHeight / 2.0)
    property real animScaleX: 1.0
    property real animScaleY: 1.0
    property real animRotate: 0.0
    property real animOpacity: 1.0
    property real animProgress: 0.0

    signal handoffReady()
    signal closeFinished()

    x: overlayX
    y: overlayY
    width: Math.max(1, overlayWidth)
    height: Math.max(1, overlayHeight)
    visible: false
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowTransparentForInput
    opacity: 1.0

    function markHandoffReady(reason) {
        if (handoffReadySignaled || isDestroying) return;
        handoffReadySignaled = true;
        phaseLog("CLOSING", "Overlay handoffReady reason=" + reason);
        handoffReady();
    }

    function phaseLog(tag, message) {
        if (!phaseLoggingEnabled) return;
        console.log("[" + tag + "] " + message);
    }

    function resetIdentityState() {
        animCenterX = contentX + (contentWidth / 2.0);
        animCenterY = contentY + (contentHeight / 2.0);
        animScaleX = 1.0;
        animScaleY = 1.0;
        animRotate = 0.0;
        animOpacity = 1.0;
        animProgress = 0.0;
    }

    // ============================================================
    // CONTINUOUS SINGULARITY COLLAPSE ANIMATION
    // ============================================================
    NumberAnimation {
        id: singularityAnim
        target: closingOverlayWin
        property: "animProgress"
        from: 0.0
        to: 1.0
        duration: 580
        easing.type: Easing.InOutQuad

        onFinished: {
            animOpacity = 0.0;
            visible = false;
            phaseLog("CLOSING", "Singularity close animation finished -> signal host");
            closeFinished();
            closeOverlay("singularity-finished");
        }
    }

    onAnimProgressChanged: {
        var p = animProgress;
        var startCenterX = contentX + (contentWidth / 2.0);
        var startCenterY = contentY + (contentHeight / 2.0);

        // 1. Vortex Movement to Target Destination (p^2.8)
        var moveP = Math.pow(p, 2.8);
        animCenterX = startCenterX + (targetX - startCenterX) * moveP;
        animCenterY = startCenterY + (targetY - startCenterY) * moveP;

        // 2. Continuous Exponential Twist Rotation (720 deg)
        animRotate = Math.pow(p, 3.0) * 720.0;

        // 3. Mathematical Tidal Spaghettification
        if (p < 0.10) {
            var breath = Math.sin((p / 0.10) * Math.PI) * 0.04;
            animScaleX = 1.0 - breath;
            animScaleY = 1.0 - breath;
        } else {
            var collapseP = (p - 0.10) / 0.90;
            var stretchCurve = Math.sin(Math.pow(collapseP, 0.7) * Math.PI);
            var tidalElongation = 1.0 + stretchCurve * 0.95;
            var shrinkFactor = Math.pow(1.0 - collapseP, 2.2);

            animScaleX = Math.max(0.001, shrinkFactor * tidalElongation);
            animScaleY = Math.max(0.001, shrinkFactor * (1.0 - Math.pow(collapseP, 0.6) * 0.82));
        }

        // 4. Smooth Disappearance at final collapse
        if (p < 0.93) {
            animOpacity = 1.0;
        } else {
            animOpacity = Math.max(0.0, 1.0 - ((p - 0.93) / 0.07));
        }

        if (particleCanvas.visible) {
            particleCanvas.requestPaint();
        }
    }

    function startClose() {
        if (isDestroying) return;
        phaseLog("CLOSING", "Overlay start Singularity close: content="
            + Math.round(contentX) + "," + Math.round(contentY) + " "
            + Math.max(1, Math.round(contentWidth)) + "x" + Math.max(1, Math.round(contentHeight))
            + " target=" + Math.round(targetX) + "," + Math.round(targetY));
        resetIdentityState();
        singularityAnim.restart();
    }

    function closeOverlay(reason) {
        if (isDestroying) return;
        isDestroying = true;
        phaseLog("CLOSING", "Overlay close reason=" + reason);
        closingOverlayWin.visible = false;
        closingOverlayWin.close();
        Qt.callLater(function() {
            closingOverlayWin.destroy();
        });
    }

    function closeForAppExit() {
        closeOverlay("closeForAppExit");
    }

    Connections {
        target: Qt.application
        function onAboutToQuit() {
            closingOverlayWin.closeOverlay("aboutToQuit");
        }
    }

    Connections {
        target: mainWindow
        function onForceCloseChanged() {
            if (mainWindow && mainWindow.forceClose) {
                closingOverlayWin.closeOverlay("main-force-close");
            }
        }
    }

    Item {
        id: container
        anchors.fill: parent

        // ============================================================
        // 1. ACCRETION PARTICLE CANVAS (Hardware 2D Context)
        // ============================================================
        Canvas {
            id: particleCanvas
            anchors.fill: parent
            renderTarget: Canvas.FramebufferObject
            renderStrategy: Canvas.Threaded
            visible: true
            z: 10

            property var particles: []
            property bool initialized: false

            function initParticles() {
                var pts = [];
                for (var i = 0; i < 250; i++) {
                    pts.push({
                        "angle": Math.random() * Math.PI * 2,
                        "distRatio": 0.15 + Math.random() * 0.85,
                        "speed": 1.8 + Math.random() * 3.6,
                        "size": 1.2 + Math.random() * 2.8,
                        "alpha": 0.25 + Math.random() * 0.75
                    });
                }
                particles = pts;
                initialized = true;
            }

            onPaint: {
                var ctx = getContext("2d");
                if (!ctx) return;
                var w = width;
                var h = height;
                ctx.clearRect(0, 0, w, h);

                var p = closingOverlayWin.animProgress;
                if (p <= 0.02 || p >= 1.0) return;
                if (!initialized) initParticles();

                var singX = closingOverlayWin.targetX;
                var singY = closingOverlayWin.targetY;

                // 1. Glowing Accretion Disc Radial Gradient (Soft, luminous glow)
                var discAlpha = Math.min(1.0, Math.pow(p * 1.4, 2.0));
                var discRadius = Math.max(14, (1.0 - p * 0.65) * 160);

                var grad = ctx.createRadialGradient(singX, singY, 4, singX, singY, discRadius);
                grad.addColorStop(0.0, "rgba(56, 189, 248, " + (discAlpha * 0.85).toFixed(3) + ")");
                grad.addColorStop(0.35, "rgba(129, 140, 248, " + (discAlpha * 0.50).toFixed(3) + ")");
                grad.addColorStop(0.70, "rgba(244, 114, 182, " + (discAlpha * 0.22).toFixed(3) + ")");
                grad.addColorStop(1.0, "rgba(56, 189, 248, 0.0)");

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(singX, singY, discRadius, 0, Math.PI * 2);
                ctx.fill();

                // 2. Swirling Orbital Accretion Particles (Logarithmic Spiral)
                for (var i = 0; i < particles.length; i++) {
                    var pt = particles[i];
                    pt.angle += (pt.speed * 0.035) / (pt.distRatio + 0.08);
                    var currentDist = pt.distRatio * (1.0 - p * 0.86) * (w * 0.38);
                    var px = singX + Math.cos(pt.angle) * currentDist;
                    var py = singY + Math.sin(pt.angle) * currentDist;

                    var ptAlpha = pt.alpha * discAlpha;
                    var ptSize = Math.max(0.6, pt.size * (1.0 - p * 0.55));

                    ctx.fillStyle = (i % 3 === 0)
                        ? "rgba(56, 189, 248, " + ptAlpha.toFixed(3) + ")"
                        : (i % 3 === 1)
                            ? "rgba(129, 140, 248, " + ptAlpha.toFixed(3) + ")"
                            : "rgba(244, 114, 182, " + ptAlpha.toFixed(3) + ")";
                    ctx.beginPath();
                    ctx.arc(px, py, ptSize, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }

        // ============================================================
        // 2. WINDOW SURFACE COLLAPSING & SPINNING INTO VORTEX
        // ============================================================
        Item {
            id: sprite
            x: closingOverlayWin.animCenterX - (width / 2.0)
            y: closingOverlayWin.animCenterY - (height / 2.0)
            width: Math.max(1, closingOverlayWin.contentWidth)
            height: Math.max(1, closingOverlayWin.contentHeight)
            scale: closingOverlayWin.animScaleX
            rotation: closingOverlayWin.animRotate
            opacity: closingOverlayWin.animOpacity
            transformOrigin: Item.Center
            z: 5

            transform: [
                Scale {
                    origin.x: sprite.width / 2.0
                    origin.y: sprite.height / 2.0
                    xScale: 1.0
                    yScale: closingOverlayWin.animScaleY / Math.max(0.0001, closingOverlayWin.animScaleX)
                }
            ]

            Loader {
                id: contentLoader
                anchors.fill: parent
                sourceComponent: (snapshotUrl && snapshotUrl.length > 0) ? snapshotContent : liveContent
            }
        }
    }

    Component {
        id: snapshotContent
        Image {
            anchors.fill: parent
            fillMode: Image.Stretch
            source: closingOverlayWin.snapshotUrl
            asynchronous: false
            smooth: true
            cache: false
            onStatusChanged: {
                if (status === Image.Ready) {
                    closingOverlayWin.markHandoffReady("snapshot-ready");
                }
            }
        }
    }

    Component {
        id: liveContent
        ChromeSurface {
            anchors.fill: parent
            farGlowEnabled: !(mainWindow && mainWindow.lowPerformanceMode)
            glowRadiusNear: 16
            glowRadiusFar: 32
            plasmaOpacity: closingOverlayWin.animOpacity
            lowFxMode: false
            flairEnabled: false
            t: (mainWindow && mainWindow.t) ? mainWindow.t : ({
                "bg": "#121212", "accent": "#38BDF8", "text": "#FFFFFF", "glow": "#818CF8"
            })
            cornerRadius: (mainWindow && mainWindow.visibility === Window.Maximized)
                ? 0
                : ((mainWindow && mainWindow.chromeCornerRadiusPx) ? mainWindow.chromeCornerRadiusPx() : 16)

            MainContent {
                anchors.fill: parent
                t: (mainWindow && mainWindow.t) ? mainWindow.t : ({})
                metrics: (mainWindow && mainWindow.uiMetrics) ? mainWindow.uiMetrics : ({})
                appRef: (mainWindow && mainWindow.appRef) ? mainWindow.appRef : null
                isInteractive: false
                windowRef: mainWindow
            }
        }
    }

    Component.onCompleted: {
        resetIdentityState();
        handoffDelay.start();
    }

    onVisibleChanged: {
        if (visible && !handoffReadySignaled) {
            handoffDelay.restart();
        }
    }

    Timer {
        id: handoffDelay
        interval: 16
        running: false
        repeat: false
        onTriggered: {
            closingOverlayWin.markHandoffReady("delay");
        }
    }

    onClosing: (close) => {
        if (!isDestroying) closingOverlayWin.closeOverlay("onClosing");
        close.accepted = true;
    }
}
