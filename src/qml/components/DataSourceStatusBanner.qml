pragma ComponentBehavior: Bound
import QtQuick
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root
    objectName: "CSPMDataSourceStatusBanner"

    property var t
    property string appStyle: "Professional"
    property string status: "setup"
    property string statusLabel: "Data source: setup required"
    readonly property bool sourceNeedsReview: root.status !== "governed-source"
    readonly property color statusInk: SemanticTheme.inkPrimary(root.t, root.appStyle)

    implicitHeight: Math.max(38, statusText.implicitHeight + 16)
    color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    border.width: 1
    border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)

    Rectangle {
        width: 4
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: root.sourceNeedsReview
            ? SemanticTheme.tone(root.t, "warning", root.appStyle)
            : SemanticTheme.accentPrimary(root.t, root.appStyle)
    }

    Text {
        id: statusText
        objectName: "CSPMDataSourceStatusText"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        text: root.statusLabel
        textFormat: Text.PlainText
        color: root.statusInk
        font.family: "Segoe UI"
        font.pixelSize: 12
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
    }
}
