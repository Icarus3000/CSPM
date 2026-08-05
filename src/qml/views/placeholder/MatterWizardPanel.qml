pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../../components"

TextArea {
    property var root

    id: matterDescriptionInput
    visible: root.activeIsNewMatterWizard()
    Layout.fillWidth: true
    Layout.fillHeight: false
    Layout.preferredHeight: root.ratioPxH(0.084, 64)
    color: root._text
    font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
    wrapMode: Text.Wrap
    placeholderText: "Matter description"
    placeholderTextColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    leftPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
    topPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
    onTextChanged: if (!root._hydrating) root.dirty = true
    background: Rectangle {
        color: SemanticTheme.alpha(root._panel, 0.72)
        radius: root.sectionRadiusPx
        border.width: matterDescriptionInput.activeFocus ? 2 : 1
        border.color: matterDescriptionInput.activeFocus
            ? SemanticTheme.alpha(root._accent, 0.62)
            : SemanticTheme.borderSubtle(root.t, root.appStyle)
    }
}
