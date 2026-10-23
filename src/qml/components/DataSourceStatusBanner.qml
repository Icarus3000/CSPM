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
    readonly property bool isReadOnlyBlock: root.sourceNeedsReview && String(root.statusLabel || "").indexOf("READ-ONLY") === 0
    readonly property bool canRetryCheckout: root.status === "unverified-local" && root.appRef !== null
    readonly property bool canForceClearCheckout: root.canRetryCheckout
        && Boolean(root.appRef && String(root.appRef.checkoutBlockStatus || "") === "checkout-held")
    readonly property color statusInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color warningToneColor: SemanticTheme.tone(root.t, "warning", root.appStyle)

    implicitHeight: Math.max(38, statusText.implicitHeight + 16)
    color: root.isReadOnlyBlock
        ? SemanticTheme.alpha(root.warningToneColor, 0.14)
        : SemanticTheme.surfaceRaised(root.t, root.appStyle)
    border.width: 1
    border.color: root.isReadOnlyBlock
        ? SemanticTheme.alpha(root.warningToneColor, 0.55)
        : SemanticTheme.borderSubtle(root.t, root.appStyle)

    Rectangle {
        width: 4
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: root.sourceNeedsReview
            ? root.warningToneColor
            : SemanticTheme.accentPrimary(root.t, root.appStyle)
    }

    Text {
        id: statusText
        objectName: "CSPMDataSourceStatusText"
        anchors.left: parent.left
        anchors.right: root.canForceClearCheckout
            ? forceClearBtn.left
            : (root.canRetryCheckout ? retryBtn.left : parent.right)
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
        id: forceClearBtn
        objectName: "CSPMDataSourceForceClearButton"
        visible: root.canForceClearCheckout
        anchors.right: retryBtn.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        width: forceClearBtnLabel.implicitWidth + 20
        height: 24
        radius: 6
        color: forceClearMouse.containsMouse
            ? SemanticTheme.alpha(root.warningToneColor, 0.28)
            : SemanticTheme.alpha(root.warningToneColor, 0.16)
        border.width: 1
        border.color: SemanticTheme.alpha(root.warningToneColor, 0.65)

        Text {
            id: forceClearBtnLabel
            anchors.centerIn: parent
            text: "Clear Stale Lock"
            color: root.statusInk
            font.family: AppTypography.textFamily()
            font.pixelSize: 11
            font.weight: Font.DemiBold
        }

        MouseArea {
            id: forceClearMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (root.appRef && typeof root.appRef.forceClearSharedDataCheckout === "function") {
                    root.appRef.forceClearSharedDataCheckout()
                }
            }
        }
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
