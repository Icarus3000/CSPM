import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: tunerRoot
    property var scaleRatios: ({
        "windowWidthPct": 0.25,
        "windowHeightPct": 0.30,
        "titleBarHeightPct": 0.10,
        "titleTextPct": 0.038,
        "closeSizePct": 0.10,
        "topMarginPct": 0.063,
        "sectionSpacingPct": 0.063,
        "rowSpacingPct": 0.016,
        "labelTextPct": 0.044,
        "actionSpacingPct": 0.047
    })
    function screenW() {
        var s = Screen.primaryScreen
        if (!s && Qt.application && Qt.application.screens && Qt.application.screens.length > 0) s = Qt.application.screens[0]
        return (s && s.width > 0) ? s.width : Math.max(1, Screen.width)
    }
    function screenH() {
        var s = Screen.primaryScreen
        if (!s && Qt.application && Qt.application.screens && Qt.application.screens.length > 0) s = Qt.application.screens[0]
        return (s && s.height > 0) ? s.height : Math.max(1, Screen.height)
    }
    function unitPx() {
        return Math.min(Math.max(1, tunerRoot.width), Math.max(1, tunerRoot.height))
    }
    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(unitPx() * ratio))
    }
    width: Math.max(220, Math.round(screenW() * scaleRatios.windowWidthPct))
    height: Math.max(220, Math.round(screenH() * scaleRatios.windowHeightPct))
    visible: true
    title: "Animation Launchpad"
    
    // REFERENCES TO MAIN APP
    property var targetMainWin
    property var targetSplashWin
    property var targetJelly
    property var themeRef: (targetMainWin && targetMainWin.t) ? targetMainWin.t : null
    property color toneBg: (themeRef && themeRef.bg) ? themeRef.bg : "#1e1e1e"
    property color tonePanel: (themeRef && themeRef.panel2) ? themeRef.panel2 : "#333333"
    property color toneText: (themeRef && themeRef.text) ? themeRef.text : "#cccccc"
    property color toneAccent: (themeRef && themeRef.accent) ? themeRef.accent : "#ff1744"
    property color tonePanelInk: readableInk(tonePanel)
    property color toneAccentInk: readableInk(toneAccent)
    property color toneMetricPrimary: Qt.rgba(
        (toneAccent.r * 0.78) + (toneText.r * 0.22),
        (toneAccent.g * 0.78) + (toneText.g * 0.22),
        (toneAccent.b * 0.78) + (toneText.b * 0.22),
        0.98
    )
    property color toneMetricSecondary: Qt.rgba(
        (toneAccent.r * 0.38) + (toneText.r * 0.62),
        (toneAccent.g * 0.38) + (toneText.g * 0.62),
        (toneAccent.b * 0.38) + (toneText.b * 0.62),
        0.98
    )
    function luma(colorValue) {
        if (!colorValue || typeof colorValue.r !== "number") return 0.0
        return (colorValue.r * 0.299) + (colorValue.g * 0.587) + (colorValue.b * 0.114)
    }
    function readableInk(fillColor) {
        return luma(fillColor) >= 0.60
            ? Qt.rgba(0.07, 0.09, 0.13, 0.98)
            : Qt.rgba(0.98, 0.99, 1.0, 0.98)
    }
    
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: toneBg
    
    // DRAG HANDLER
    MouseArea {
        anchors.fill: parent
        onPressed: tunerRoot.startSystemMove()
    }
    
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: Qt.rgba(toneAccent.r, toneAccent.g, toneAccent.b, 0.45)
        border.width: tunerRoot.ratioPx(0.003, 1)
    }

    // --- TITLE BAR ---
    Rectangle {
        id: titleBar
        height: tunerRoot.ratioPx(tunerRoot.scaleRatios.titleBarHeightPct, 24)
        width: parent.width
        color: Qt.rgba(tonePanel.r, tonePanel.g, tonePanel.b, 0.94)
        anchors.top: parent.top
        
        Text {
            text: "ANIMATION TUNER"
            color: toneText
            font.bold: true
            font.pixelSize: tunerRoot.ratioPx(tunerRoot.scaleRatios.titleTextPct, 9)
            anchors.centerIn: parent
        }

        Rectangle {
            width: tunerRoot.ratioPx(tunerRoot.scaleRatios.closeSizePct, 18)
            height: width
            color: closeMouse.containsMouse
                ? Qt.rgba(toneAccent.r, toneAccent.g, toneAccent.b, 0.9)
                : "transparent"
            anchors.right: parent.right
            z: 100
            Text {
                text: "X"
                color: closeMouse.containsMouse ? tunerRoot.toneAccentInk : tunerRoot.tonePanelInk
                anchors.centerIn: parent
            }
            MouseArea {
                id: closeMouse
                anchors.fill: parent
                hoverEnabled: true
                onClicked: tunerRoot.visible = false 
            }
        }
    }

    // --- CONTROLS ---
    ColumnLayout {
        anchors.top: titleBar.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: tunerRoot.ratioPx(tunerRoot.scaleRatios.topMarginPct, 8)
        spacing: tunerRoot.ratioPx(tunerRoot.scaleRatios.sectionSpacingPct, 8)
        
        // TIME
        ColumnLayout {
            spacing: tunerRoot.ratioPx(tunerRoot.scaleRatios.rowSpacingPct, 2)
            Layout.alignment: Qt.AlignHCenter 
            Text {
                text: "TIME SCALE: " + targetMainWin.tuneTime.toFixed(2) + "x"
                color: tunerRoot.toneMetricPrimary
                font.pixelSize: tunerRoot.ratioPx(tunerRoot.scaleRatios.labelTextPct, 10)
                Layout.alignment: Qt.AlignHCenter
            }
            RowLayout {
                Button { text: "FASTER (-.1)"; onClicked: targetMainWin.tuneTime = Math.max(0.1, targetMainWin.tuneTime - 0.1) }
                Button { text: "SLOWER (+.1)"; onClicked: targetMainWin.tuneTime += 0.1 }
            }
        }

        // DAMPING
        ColumnLayout {
            spacing: tunerRoot.ratioPx(tunerRoot.scaleRatios.rowSpacingPct, 2)
            Layout.alignment: Qt.AlignHCenter 
            Text {
                text: "DAMPING: " + targetMainWin.tuneDamping.toFixed(2) + "x"
                color: tunerRoot.toneMetricSecondary
                font.pixelSize: tunerRoot.ratioPx(tunerRoot.scaleRatios.labelTextPct, 10)
                Layout.alignment: Qt.AlignHCenter
            }
            RowLayout {
                Button { text: "LOOSER (-.1)"; onClicked: targetMainWin.tuneDamping = Math.max(0.1, targetMainWin.tuneDamping - 0.1) }
                Button { text: "TIGHTER (+.1)"; onClicked: targetMainWin.tuneDamping += 0.1 }
            }
        }

        // ACTIONS
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: tunerRoot.ratioPx(tunerRoot.scaleRatios.actionSpacingPct, 6)
            
            Button { 
                text: "RESET APP"; 
                palette.buttonText: Qt.rgba(tunerRoot.toneAccent.r, tunerRoot.toneAccent.g, tunerRoot.toneAccent.b, 0.92)
                onClicked: {
                    targetMainWin.opacity = 0.0
                    targetMainWin.width = 0
                    targetMainWin.height = 0
                    targetSplashWin.visible = false
                    if ((tunerRoot.flags & Qt.WindowDoesNotAcceptFocus) !== Qt.WindowDoesNotAcceptFocus) {
                        tunerRoot.requestActivate()
                    }
                }
            }
            
            Button { 
                text: "LAUNCH >"; 
                palette.buttonText: tunerRoot.tonePanelInk
                font.bold: true
                onClicked: {
                    if (targetMainWin.width === 0) {
                        if (targetJelly) targetJelly.prepareLaunch()
                    }
                }
            }
        }
    }
}
