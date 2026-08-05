pragma ComponentBehavior: Bound
import QtQuick
import Qt5Compat.GraphicalEffects
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property string appStyle: "Professional"
    
    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }
    
    property string role: "panel"
    property string tone: "neutral"
    property real radius: visualRules.radiusPanel
    property real borderWidth: 1
    property real padding: 0
    property bool shadowEnabled: role === "tooltip" || role === "toast" || role === "popup" || role === "dialog"
    property real shadowRadius: visualRules.shadowPanel
    property int shadowSamples: 24
    property real shadowVerticalOffset: 0

    readonly property color surfaceColor: SemanticTheme.surface(root.t, root.role, root.tone, root.appStyle)
    readonly property color borderColor: SemanticTheme.border(root.t, root.role, root.tone, root.appStyle)
    readonly property color inkColor: SemanticTheme.ink(root.t, root.role, root.tone, root.appStyle)
    readonly property color accentColor: SemanticTheme.tone(root.t, root.tone === "neutral" ? "info" : root.tone, root.appStyle)
    readonly property color shadowColor: SemanticTheme.shadow(root.t, root.role, root.tone, root.appStyle)

    default property alias contentData: contentHost.data
    property alias contentItem: contentHost

    implicitWidth: Math.max(1, contentHost.implicitWidth + (root.padding * 2))
    implicitHeight: Math.max(1, contentHost.implicitHeight + (root.padding * 2))

    Rectangle {
        id: backdrop
        anchors.fill: parent
        radius: root.radius
        color: root.surfaceColor
        border.width: root.borderWidth
        border.color: root.borderColor

        layer.enabled: root.shadowEnabled
        layer.effect: DropShadow {
            transparentBorder: true
            color: root.shadowColor
            radius: root.shadowRadius
            samples: root.shadowSamples
            horizontalOffset: 0
            verticalOffset: root.shadowVerticalOffset
        }
    }

    Item {
        id: contentHost
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
