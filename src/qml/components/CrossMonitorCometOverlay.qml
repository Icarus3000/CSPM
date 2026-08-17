import QtQuick

// CrossMonitorCometOverlay.qml
// Transparent overlay window spanning the entire virtual desktop.
// Renders a white-hot comet with plasma tail and sparks that flies
// in a straight line between two global desktop coordinates.
// Used for system-tray minimize/restore when the tray is on a
// different monitor than the application window.

Window {
    id: cometOverlay

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
    color: "transparent"
    visible: false

    // ── Flight endpoints (global desktop coordinates) ──
    property real startGlobalX: 0
    property real startGlobalY: 0
    property real endGlobalX: 0
    property real endGlobalY: 0

    // Animation progress  0.0 → 1.0
    property real flightProgress: 0.0

    signal flightFinished()

    // ── Public API ──────────────────────────────────────
    function launchFlight(sx, sy, ex, ey, vdX, vdY, vdW, vdH, durationMs) {
        startGlobalX = sx;
        startGlobalY = sy;
        endGlobalX   = ex;
        endGlobalY   = ey;

        // Position overlay to span the full virtual desktop
        cometOverlay.x      = vdX;
        cometOverlay.y      = vdY;
        cometOverlay.width   = vdW;
        cometOverlay.height  = vdH;

        flightProgress = 0.0;
        cometOverlay.visible = true;
        cometOverlay.raise();

        flightAnim.duration = durationMs || 600;
        flightAnim.restart();
    }

    function abort() {
        flightAnim.stop();
        cometOverlay.visible = false;
    }

    // ── Animation ──────────────────────────────────────
    NumberAnimation {
        id: flightAnim
        target: cometOverlay
        property: "flightProgress"
        from: 0.0;  to: 1.0
        duration: 600
        easing.type: Easing.InOutCubic

        onFinished: {
            cometOverlay.visible = false;
            cometOverlay.flightFinished();
        }
    }

    onFlightProgressChanged: flightCanvas.requestPaint()

    // ── Canvas ─────────────────────────────────────────
    Canvas {
        id: flightCanvas
        anchors.fill: parent
        renderStrategy: Canvas.Threaded

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.clearRect(0, 0, width, height);

            var p = cometOverlay.flightProgress;
            if (p <= 0.0 || p >= 1.0) return;

            // Gravitational-acceleration easing
            var ease = Math.pow(p, 2.2);

            // Convert global coords to canvas-local
            var sx = cometOverlay.startGlobalX - cometOverlay.x;
            var sy = cometOverlay.startGlobalY - cometOverlay.y;
            var ex = cometOverlay.endGlobalX   - cometOverlay.x;
            var ey = cometOverlay.endGlobalY   - cometOverlay.y;

            var headX = sx + (ex - sx) * ease;
            var headY = sy + (ey - sy) * ease;

            // Flight angle
            var angle = Math.atan2(ey - sy, ex - sx);
            var cosA  = Math.cos(angle);
            var sinA  = Math.sin(angle);

            // Adaptive scale by flight distance (keeps proportions on short/long flights)
            var totalDist = Math.sqrt((ex - sx) * (ex - sx) + (ey - sy) * (ey - sy));
            var scale = Math.min(1.0, Math.max(0.5, totalDist / 1200.0));

            // ── Head glow ──
            var headR = 10 * scale;
            var glowR = headR * 4;

            var outerGlow = ctx.createRadialGradient(headX, headY, 0, headX, headY, glowR);
            outerGlow.addColorStop(0.0,  "rgba(255,255,255,0.92)");
            outerGlow.addColorStop(0.15, "rgba(255,250,235,0.65)");
            outerGlow.addColorStop(0.4,  "rgba(255,230,180,0.30)");
            outerGlow.addColorStop(0.7,  "rgba(255,200,130,0.10)");
            outerGlow.addColorStop(1.0,  "rgba(255,180,100,0.0)");
            ctx.fillStyle = outerGlow;
            ctx.beginPath();
            ctx.arc(headX, headY, glowR, 0, Math.PI * 2);
            ctx.fill();

            // ── Tail ribbon ──
            var tailLen  = (90 + 40 * Math.sin(p * Math.PI)) * scale;
            var tailTipX = headX - cosA * tailLen;
            var tailTipY = headY - sinA * tailLen;

            var halfW = headR * 0.85;
            var perpX = -sinA * halfW;
            var perpY =  cosA * halfW;

            var ribbonGrad = ctx.createLinearGradient(headX, headY, tailTipX, tailTipY);
            ribbonGrad.addColorStop(0.0,  "rgba(255,255,255,0.82)");
            ribbonGrad.addColorStop(0.15, "rgba(255,245,215,0.58)");
            ribbonGrad.addColorStop(0.5,  "rgba(255,220,160,0.25)");
            ribbonGrad.addColorStop(1.0,  "rgba(255,195,120,0.0)");
            ctx.fillStyle = ribbonGrad;
            ctx.beginPath();
            ctx.moveTo(headX + perpX, headY + perpY);
            ctx.quadraticCurveTo(
                (headX + tailTipX) / 2 + perpX * 0.4,
                (headY + tailTipY) / 2 + perpY * 0.4,
                tailTipX, tailTipY
            );
            ctx.quadraticCurveTo(
                (headX + tailTipX) / 2 - perpX * 0.4,
                (headY + tailTipY) / 2 - perpY * 0.4,
                headX - perpX, headY - perpY
            );
            ctx.closePath();
            ctx.fill();

            // ── Core dot ──
            ctx.fillStyle = "rgba(255,255,255,0.98)";
            ctx.beginPath();
            ctx.arc(headX, headY, headR * 0.55, 0, Math.PI * 2);
            ctx.fill();

            // ── Plasma sparks ──
            var sparkCount = 8;
            for (var i = 0; i < sparkCount; i++) {
                var sparkPhase  = (p * 3.0 + i * 0.618) % 1.0;
                var sparkDist   = tailLen * (0.15 + sparkPhase * 0.85);
                var sparkSpread = Math.sin(sparkPhase * Math.PI * 5 + i * 2.1) * (14 * scale);
                var spX = headX - cosA * sparkDist + (-sinA * sparkSpread);
                var spY = headY - sinA * sparkDist + ( cosA * sparkSpread);
                var sparkAlpha = Math.max(0, 0.7 - sparkPhase * 0.9);
                var sparkR     = (3.0 - sparkPhase * 1.5) * scale;

                ctx.fillStyle = "rgba(255,235,185," + sparkAlpha.toFixed(3) + ")";
                ctx.beginPath();
                ctx.arc(spX, spY, sparkR, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}
