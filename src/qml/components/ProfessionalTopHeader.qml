pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: topHeaderRoot

    required property var appRoot
    property Item backdropSource: null
    property bool shellEnabled: true
    property bool returnToDockVisible: false
    signal omniSearchRequested(string query)
    signal homeRequested()
    signal returnToDockRequested()
    readonly property var app: topHeaderRoot.appRoot
    readonly property bool headerLight: !topHeaderRoot.app || typeof topHeaderRoot.app.lightTheme !== "boolean" ? true : topHeaderRoot.app.lightTheme
    readonly property int compactHeightPx: 72
    readonly property int horizontalInsetPx: 16
    readonly property int logoSidePx: Math.max(50, Math.min(58, Math.round(topHeaderRoot.height * 0.78)))
    readonly property int titlePixelSize: Math.max(14, Math.min(18, Math.round(topHeaderRoot.height * 0.25)))
    readonly property int controlButtonSizePx: Math.max(30, Math.min(32, Math.round(topHeaderRoot.height * 0.45)))
    readonly property int controlGlyphSizePx: Math.max(11, Math.min(13, Math.round(topHeaderRoot.controlButtonSizePx * 0.39)))
    readonly property color headerInk: SemanticTheme.inkPrimary(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    readonly property color headerMutedInk: SemanticTheme.inkMuted(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    readonly property color headerBorder: SemanticTheme.alpha(SemanticTheme.borderSubtle(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional"), 0.70)
    // Window controls need a clearly perceptible acknowledgement before the
    // longer native transition begins.  The previous semantic hover overlay
    // was too close to the title-bar surface in both themes.
    readonly property color controlHoverFill: topHeaderRoot.headerLight ? "#DCE8F8" : "#2D4361"
    readonly property color controlPressedFill: topHeaderRoot.headerLight ? "#C8DCF5" : "#38557A"
    readonly property color controlHoverBorder: topHeaderRoot.headerLight ? "#8AAED9" : "#6F95C5"
    readonly property color controlHoverInk: SemanticTheme.accentPrimary(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    readonly property color closeHoverFill: SemanticTheme.destructive(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    readonly property color closeHoverInk: SemanticTheme.textOnAccent(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    Layout.fillWidth: true
    implicitHeight: topHeaderRoot.compactHeightPx
    Layout.preferredHeight: topHeaderRoot.shellEnabled ? topHeaderRoot.compactHeightPx : 0
    visible: topHeaderRoot.shellEnabled
    color: "transparent"
    clip: true

    Rectangle {
        id: headerGlassMask
        anchors.fill: parent
        color: "transparent"
    }

    ShaderEffectSource {
        id: headerBlurSource
        anchors.fill: parent
        sourceItem: topHeaderRoot.backdropSource
        sourceRect: (topHeaderRoot.backdropSource && (topHeaderRoot.app ? typeof topHeaderRoot.app.sourceRectFor : "undefined") === "function") ? topHeaderRoot.app.sourceRectFor(headerGlassMask) : Qt.rect(0, 0, 1, 1)
        live: !(topHeaderRoot.app && topHeaderRoot.app.windowRef && (topHeaderRoot.app.windowRef.userResizeInProgress || topHeaderRoot.app.windowRef.userMoveInProgress))
        hideSource: false
        mipmap: true
    }

    MultiEffect {
        anchors.fill: parent
        source: headerBlurSource
        visible: false
        blurEnabled: false
        blur: 0.0
        blurMax: 8
        saturation: 0.0
        brightness: 0.0
    }

    Rectangle {
        anchors.fill: parent
        color: SemanticTheme.titleBarBackground(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 1
        color: SemanticTheme.focusOverlay(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: topHeaderRoot.headerBorder
    }

    Item {
        id: headerDragZone
        x: topHeaderRoot.horizontalInsetPx
        y: 0
        height: parent.height
        width: {
            var available = parent.width - (topHeaderRoot.horizontalInsetPx * 2) - controlsRow.width - 18
            return Math.max(1, Math.round(available))
        }
        TapHandler {
            id: headerDoubleTap
            gesturePolicy: TapHandler.DragThreshold
            onTapped: {
                if (tapCount === 2) {
                    if (topHeaderRoot.app.windowRef && topHeaderRoot.app.windowRef.toggleWindowMaximize) {
                        topHeaderRoot.app.windowRef.toggleWindowMaximize()
                    }
                }
            }
        }

        DragHandler {
            id: headerDrag
            target: null
            dragThreshold: 0
            enabled: topHeaderRoot.app ? !!(topHeaderRoot.app.isInteractive && topHeaderRoot.app.windowRef) : false
            property bool dragSessionStarted: false

            onActiveChanged: {
                if (!topHeaderRoot.app.windowRef) {
                    return
                }
                if (active) {
                    dragSessionStarted = false
                    if (topHeaderRoot.app.windowRef.geometryTransitionSuppressed !== undefined) {
                        topHeaderRoot.app.windowRef.geometryTransitionSuppressed = true
                    }
                } else {
                    if (!dragSessionStarted) {
                        if (topHeaderRoot.app.windowRef.geometryTransitionSuppressed !== undefined
                            && !topHeaderRoot.app.windowRef.userMoveInProgress
                            && !topHeaderRoot.app.windowRef.userResizeInProgress) {
                            topHeaderRoot.app.windowRef.geometryTransitionSuppressed = false
                        }
                        return
                    }
                    if (topHeaderRoot.app.windowRef.finishUserDrag) {
                        try {
                            topHeaderRoot.app.windowRef.finishUserDrag()
                        } catch(e) {
                        }
                    } else if (topHeaderRoot.app.windowRef.userMoveInProgress !== undefined) {
                        topHeaderRoot.app.windowRef.userMoveInProgress = false
                        if (topHeaderRoot.app.windowRef.updateTargetScreenFromFinalCenter) {
                            try {
                                topHeaderRoot.app.windowRef.updateTargetScreenFromFinalCenter()
                            } catch(e) {
                            }
                        }
                        if (topHeaderRoot.app.windowRef.updateCanvasGeometry) {
                            try {
                                topHeaderRoot.app.windowRef.updateCanvasGeometry()
                            } catch(e) {
                            }
                        }
                    } else if (topHeaderRoot.app.windowRef.updateCanvasGeometry) {
                        try {
                            topHeaderRoot.app.windowRef.updateCanvasGeometry()
                        } catch(e) {
                        }
                    }
                    dragSessionStarted = false
                }
            }

            onTranslationChanged: {
                if (!active || !topHeaderRoot.app.windowRef) {
                    return
                }
                if (!dragSessionStarted) {
                    if (Math.abs(translation.x) < 0.5 && Math.abs(translation.y) < 0.5) {
                        return
                    }
                    if (topHeaderRoot.app.windowRef.uiMaximized && translation.y <= 0.5) {
                        return
                    }
                    if (topHeaderRoot.app.windowRef.beginHeaderDrag) {
                        try {
                            var beginHeaderOk = topHeaderRoot.app.windowRef.beginHeaderDrag(translation.x, translation.y)
                            dragSessionStarted = !!topHeaderRoot.app.windowRef.userMoveInProgress
                            if (!dragSessionStarted && typeof beginHeaderOk === "boolean") {
                                dragSessionStarted = beginHeaderOk
                            }
                        } catch(e) {
                        }
                    } else if (topHeaderRoot.app.windowRef.beginUserDrag) {
                        try {
                            var beginDragOk = topHeaderRoot.app.windowRef.beginUserDrag()
                            dragSessionStarted = !!topHeaderRoot.app.windowRef.userMoveInProgress
                            if (!dragSessionStarted && typeof beginDragOk === "boolean") {
                                dragSessionStarted = beginDragOk
                            }
                        } catch(e2) {
                        }
                    }
                    if (!dragSessionStarted) {
                        return
                    }
                }
                if (topHeaderRoot.app.windowRef.updateUserDrag) {
                    try {
                        topHeaderRoot.app.windowRef.updateUserDrag(translation.x, translation.y)
                    } catch(e3) {
                    }
                } else if (topHeaderRoot.app.windowRef.userMoveInProgress
                    && topHeaderRoot.app.windowRef.animationPhase === "settled"
                    && topHeaderRoot.app.windowRef.syncDragContentPosition) {
                    try {
                        topHeaderRoot.app.windowRef.syncDragContentPosition()
                    } catch(e4) {
                    }
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: topHeaderRoot.horizontalInsetPx
        anchors.rightMargin: topHeaderRoot.horizontalInsetPx
        spacing: 12

        Item {
            Layout.preferredHeight: topHeaderRoot.logoSidePx
            Layout.preferredWidth: topHeaderRoot.logoSidePx
            Layout.alignment: Qt.AlignVCenter

            CrispLogo {
                id: headerLogo
                anchors.fill: parent
                metrics: topHeaderRoot.app.metrics
                color: topHeaderRoot.headerInk
                opacity: 0.94
            }

            TapHandler {
                acceptedButtons: Qt.LeftButton
                onTapped: topHeaderRoot.homeRequested()
            }
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.fillWidth: true
            text: "Cory Schneider Law Office Practice Management"
            color: topHeaderRoot.headerInk
            font.family: "Segoe UI"
            font.pixelSize: topHeaderRoot.titlePixelSize
            font.weight: Font.Medium
            elide: Text.ElideRight
            opacity: 1.0
        }

        Rectangle {
            Layout.preferredWidth: 320
            Layout.preferredHeight: topHeaderRoot.controlButtonSizePx + 2
            Layout.alignment: Qt.AlignVCenter
            radius: 4
            color: topHeaderRoot.headerLight 
                ? SemanticTheme.titleBarBackground(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional") 
                : SemanticTheme.titleBarBackground(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
            border.width: 1
            border.color: topHeaderRoot.controlHoverBorder

            RowLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 6

                Text {
                    text: "\uE721" // Search icon
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 13
                    color: topHeaderRoot.headerMutedInk
                    Layout.leftMargin: 4
                }

                TextField {
    background: Item {}
    padding: 0
                    id: headerOmniInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    verticalAlignment: TextInput.AlignVCenter
                    color: topHeaderRoot.headerInk
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    selectByMouse: true
                    clip: true

                    Text {
                        anchors.fill: parent
                        text: "Search clients, matters, reports, functions..."
                        color: topHeaderRoot.headerMutedInk
                        font: parent.font
                        verticalAlignment: TextInput.AlignVCenter
                        visible: !parent.text && !parent.activeFocus
                    }

                    Keys.onEnterPressed: function(event) {
                        if (text.trim().length > 0) {
                            topHeaderRoot.omniSearchRequested(text.trim());
                            text = "";
                            focus = false;
                        }
                        event.accepted = true;
                    }
                    Keys.onReturnPressed: function(event) {
                        if (text.trim().length > 0) {
                            topHeaderRoot.omniSearchRequested(text.trim());
                            text = "";
                            focus = false;
                        }
                        event.accepted = true;
                    }
                }

                Connections {
                    target: topHeaderRoot.appRoot
                    function onUniversalSearchTriggered() {
                        headerOmniInput.forceActiveFocus()
                    }
                }

                Text {
                    id: enterSearchGlyph
                    text: "\uE71B" // Arrow/Enter glyph
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: 13
                    color: enterSearchHover.containsMouse ? topHeaderRoot.headerInk : topHeaderRoot.headerMutedInk
                    Layout.rightMargin: 4

                    MouseArea {
                        id: enterSearchHover
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (headerOmniInput.text.trim().length > 0) {
                                topHeaderRoot.omniSearchRequested(headerOmniInput.text.trim());
                                headerOmniInput.text = "";
                                headerOmniInput.focus = false;
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            id: controlsRow
            spacing: 2
            Layout.alignment: Qt.AlignVCenter
            visible: true
            z: 3

            Button {
                id: returnDockButton
                visible: topHeaderRoot.returnToDockVisible
                Layout.preferredWidth: visible ? 132 : 0
                Layout.preferredHeight: topHeaderRoot.controlButtonSizePx + 2
                padding: 0
                text: "Return to Dock"
                hoverEnabled: true
                background: Rectangle {
                    radius: 3
                    color: returnDockButton.hovered ? topHeaderRoot.controlHoverFill : "transparent"
                    border.width: returnDockButton.hovered ? 1 : 0
                    border.color: topHeaderRoot.controlHoverBorder
                }
                contentItem: RowLayout {
                    spacing: 5
                    Text {
                        text: "\uE72B"
                        font.family: "Segoe MDL2 Assets"
                        font.pixelSize: 13
                        color: returnDockButton.hovered ? topHeaderRoot.headerInk : topHeaderRoot.headerMutedInk
                        Layout.alignment: Qt.AlignVCenter
                    }
                    Text {
                        Layout.fillWidth: true
                        text: returnDockButton.text
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: returnDockButton.hovered ? topHeaderRoot.headerInk : topHeaderRoot.headerMutedInk
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }
                onClicked: {
                    if (topHeaderRoot.app.isInteractive) {
                        topHeaderRoot.returnToDockRequested()
                    }
                }
                opacity: topHeaderRoot.app.isInteractive ? 1.0 : 0.70
            }

            Button {
                id: settingsButton
                Layout.preferredWidth: topHeaderRoot.controlButtonSizePx
                Layout.preferredHeight: topHeaderRoot.controlButtonSizePx
                padding: 0
                text: "\uE713"
                hoverEnabled: true
                background: Rectangle {
                    radius: 3
                    color: settingsButton.hovered ? topHeaderRoot.controlHoverFill : "transparent"
                    border.width: settingsButton.hovered ? 1 : 0
                    border.color: topHeaderRoot.controlHoverBorder
                }
                contentItem: Text {
                    text: settingsButton.text
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: topHeaderRoot.controlGlyphSizePx
                    color: settingsButton.hovered ? topHeaderRoot.headerInk : topHeaderRoot.headerMutedInk
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    if (topHeaderRoot.app.isInteractive && topHeaderRoot.app.windowRef) {
                        try {
                            if (topHeaderRoot.app.windowRef.openSettingsMenu && topHeaderRoot.app.windowRef.openSettingsMenu()) {
                                return
                            }
                            if (!topHeaderRoot.app.windowRef.openThemePicker || !topHeaderRoot.app.windowRef.openThemePicker()) {
                                console.log("[SETTINGS] openSettingsMenu/openThemePicker returned false")
                            }
                        } catch(e) {
                        }
                    }
                }
                opacity: topHeaderRoot.app.isInteractive ? 1.0 : 0.70
            }
            Rectangle {
                id: minimizeButton
                Layout.preferredWidth: topHeaderRoot.controlButtonSizePx
                Layout.preferredHeight: topHeaderRoot.controlButtonSizePx
                radius: 3
                color: minimizeMouseArea.pressed ? topHeaderRoot.controlPressedFill
                    : (minimizeMouseArea.containsMouse ? topHeaderRoot.controlHoverFill : "transparent")
                border.width: (minimizeMouseArea.containsMouse || minimizeMouseArea.pressed) ? 1 : 0
                border.color: topHeaderRoot.controlHoverBorder

                Text {
                    anchors.centerIn: parent
                    text: "\uE921"
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: topHeaderRoot.controlGlyphSizePx
                    color: (minimizeMouseArea.containsMouse || minimizeMouseArea.pressed)
                        ? topHeaderRoot.controlHoverInk : topHeaderRoot.headerMutedInk
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                MouseArea {
                    id: minimizeMouseArea
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: function(mouse) {
                        topHeaderRoot.app.playSfxUiClick("minimize", 0.42)
                        if (!topHeaderRoot.app || !topHeaderRoot.app.windowRef) return;
                        if (mouse.button === Qt.RightButton) {
                            try {
                                if (topHeaderRoot.app.windowRef.requestMinimizeToTrayAnimation) {
                                    topHeaderRoot.app.windowRef.requestMinimizeToTrayAnimation()
                                } else if (!topHeaderRoot.app.windowRef.requestMinimizeAnimation || !topHeaderRoot.app.windowRef.requestMinimizeAnimation()) {
                                    topHeaderRoot.app.windowRef.showMinimized()
                                }
                            } catch(e) {
                                topHeaderRoot.app.windowRef.showMinimized()
                            }
                        } else {
                            try {
                                if (!topHeaderRoot.app.windowRef.requestMinimizeAnimation || !topHeaderRoot.app.windowRef.requestMinimizeAnimation()) {
                                    topHeaderRoot.app.windowRef.showMinimized()
                                }
                            } catch(e) {
                                topHeaderRoot.app.windowRef.showMinimized()
                            }
                        }
                    }
                }
                opacity: (topHeaderRoot.app && topHeaderRoot.app.isInteractive) ? 1.0 : 0.70
            }
            Button {
                id: maximizeButton
                Layout.preferredWidth: topHeaderRoot.controlButtonSizePx
                Layout.preferredHeight: topHeaderRoot.controlButtonSizePx
                padding: 0
                text: (topHeaderRoot.app.windowRef && topHeaderRoot.app.windowRef.uiMaximized) ? "\uE923" : "\uE922"
                hoverEnabled: true
                background: Rectangle {
                    radius: 3
                    color: maximizeButton.down ? topHeaderRoot.controlPressedFill
                        : (maximizeButton.hovered ? topHeaderRoot.controlHoverFill : "transparent")
                    border.width: (maximizeButton.hovered || maximizeButton.down) ? 1 : 0
                    border.color: topHeaderRoot.controlHoverBorder
                }
                contentItem: Text {
                    text: maximizeButton.text
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: topHeaderRoot.controlGlyphSizePx
                    color: (maximizeButton.hovered || maximizeButton.down)
                        ? topHeaderRoot.controlHoverInk : topHeaderRoot.headerMutedInk
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    topHeaderRoot.app.playSfxUiClick("expand", 0.58)
                    if (topHeaderRoot.app.isInteractive && topHeaderRoot.app.windowRef) {
                        if (topHeaderRoot.app.windowRef.toggleWindowMaximize) {
                            try { topHeaderRoot.app.windowRef.toggleWindowMaximize() } catch(e) { }
                        } else {
                            try { (topHeaderRoot.app.windowRef.isMaximized ? topHeaderRoot.app.windowRef.showNormal() : topHeaderRoot.app.windowRef.showMaximized()) } catch(e2) { }
                        }
                    }
                }
                opacity: topHeaderRoot.app.isInteractive ? 1.0 : 0.70
            }
            Button {
                id: closeButton
                Layout.preferredWidth: topHeaderRoot.controlButtonSizePx
                Layout.preferredHeight: topHeaderRoot.controlButtonSizePx
                padding: 0
                text: "\uE8BB"
                hoverEnabled: true
                background: Rectangle {
                    radius: 3
                    color: (closeButton.hovered || closeButton.down) ? topHeaderRoot.closeHoverFill : "transparent"
                    border.width: (closeButton.hovered || closeButton.down) ? 1 : 0
                    border.color: SemanticTheme.destructiveHover(topHeaderRoot.app ? topHeaderRoot.app.t : null, "Professional")
                }
                contentItem: Text {
                    text: closeButton.text
                    font.family: "Segoe MDL2 Assets"
                    font.pixelSize: topHeaderRoot.controlGlyphSizePx
                    color: (closeButton.hovered || closeButton.down)
                        ? topHeaderRoot.closeHoverInk : topHeaderRoot.headerMutedInk
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    if (topHeaderRoot.app.isInteractive && topHeaderRoot.app.windowRef) {
                        topHeaderRoot.app.playSfxUiClick("danger", 0.82)
                        try {
                            if (!topHeaderRoot.app.windowRef.requestCloseAnimation || !topHeaderRoot.app.windowRef.requestCloseAnimation()) {
                                topHeaderRoot.app.windowRef.close()
                            }
                        } catch(e) {
                            topHeaderRoot.app.windowRef.close()
                        }
                    } else if (topHeaderRoot.app.windowRef) {
                        topHeaderRoot.app.playSfxUiClick("danger", 0.70)
                        try {
                            topHeaderRoot.app.windowRef.close()
                        } catch(e2) {
                        }
                    }
                }
                opacity: 1.0
            }
        }
    }
}
