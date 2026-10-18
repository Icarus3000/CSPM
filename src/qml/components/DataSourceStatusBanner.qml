pragma ComponentBehavior: Bound
import "../standards/AppTypography.js" as AppTypography
import QtQuick
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root
    objectName: "CSPMDataSourceStatusBanner"

    property var t
    property var appRef: null
    property string appStyle: "Professional"
    property string status: "setup"
    property string statusLabel: "Data source: setup required"
    readonly property bool sourceNeedsReview: root.status !== "governed-source"
    readonly property bool canRetryCheckout: root.status === "unverified-local" && root.appRef !== null
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
        anchors.right: root.canRetryCheckout ? retryBtn.left : parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        text: root.statusLabel
        Accessible.role: Accessible.StaticText
        Accessible.name: root.statusLabel
        textFormat: Text.PlainText
        color: root.statusInk
        font.family: AppTypography.textFamily()
        font.pixelSize: 12
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
    }

    Rectangle {
        id: retryBtn
        objectName: "CSPMDataSourceRetryButton"
        visible: root.canRetryCheckout
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        width: retryBtnLabel.implicitWidth + 20
        height: 24
        radius: 6
        color: retryMouse.containsMouse
            ? SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.22)
            : SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.12)
        border.width: 1
        border.color: SemanticTheme.alpha(SemanticTheme.accentPrimary(root.t, root.appStyle), 0.45)

        Text {
            id: retryBtnLabel
            anchors.centerIn: parent
            text: "Retry Checkout"
            color: root.statusInk
            font.family: AppTypography.textFamily()
            font.pixelSize: 11
            font.weight: Font.DemiBold
        }

        MouseArea {
            id: retryMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (root.appRef && typeof root.appRef.retrySharedDataCheckout === "function") {
                    root.appRef.retrySharedDataCheckout()
                }
            }
        }
    }
}
