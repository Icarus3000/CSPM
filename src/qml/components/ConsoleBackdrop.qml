import QtQuick

Item {
    id: root
    property var t
    anchors.fill: parent

    property bool isLight: root.t && root.t.mode === "Light"

    // CRITICAL: Use panel2 as the silhouette base to avoid a dark rim at the outer edge.
    property color baseColor: root.t ? root.t.panel2 : (isLight ? "#F7F7F7" : "#121F38")
    property color accentColor: root.t ? root.t.accent : "#2979FF"

    Rectangle {
        anchors.fill: parent
        color: root.baseColor
    }

    // Accent wash only.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0;  color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.isLight ? 0.05 : 0.10) }
            GradientStop { position: 0.55; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.isLight ? 0.02 : 0.05) }
            GradientStop { position: 1.0;  color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.00) }
        }
        opacity: 1.0
    }
}
