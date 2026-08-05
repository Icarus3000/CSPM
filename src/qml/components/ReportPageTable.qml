pragma ComponentBehavior: Bound
import QtQuick
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    property var t
    property string appStyle: "Professional"
    property string title: ""
    property var columns: []
    property var rows: []
    property string emptyText: "No rows."
    property int titleHeight: 24
    property int headerHeight: 26
    property int rowHeight: 30
    property color ink: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color mutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color ruleColor: SemanticTheme.borderSubtle(root.t, root.appStyle)
    readonly property bool isProMode: appStyle === "Professional"
    readonly property color titleFill: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    readonly property color headerFill: SemanticTheme.tableHeaderBackground(root.t, root.appStyle)
    readonly property color rowFill: SemanticTheme.tableRowBackground(root.t, root.appStyle)
    readonly property color alternateRowFill: SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)
    readonly property color rowRuleColor: SemanticTheme.borderSubtle(root.t, root.appStyle)

    signal rowClicked(var row)
    signal rowDoubleClicked(var row)

    height: tableColumn.implicitHeight + 2

    function _safeText(value) {
        return String(value === undefined || value === null ? "" : value)
    }

    function _columnWeight(column) {
        var value = Number(column && column.width !== undefined ? column.width : 1)
        if (!isFinite(value) || value <= 0) value = 1
        return value
    }

    function _totalWeight() {
        var total = 0
        var list = columns || []
        for (var i = 0; i < list.length; i++) total += _columnWeight(list[i])
        return total > 0 ? total : 1
    }

    function _columnWidth(column) {
        return Math.max(26, Math.floor(width * (_columnWeight(column) / _totalWeight())))
    }

    Column {
        id: tableColumn
        width: parent.width
        spacing: 0

        Rectangle {
            width: root.width
            height: root.titleHeight
            color: root.titleFill
            border.width: 1
            border.color: root.ruleColor
            Text {
                anchors.fill: parent
                anchors.leftMargin: 8
                verticalAlignment: Text.AlignVCenter
                text: root.title
                color: root.ink
                font.pixelSize: 11
                font.bold: true
                elide: Text.ElideRight
            }
        }

        Rectangle {
            width: root.width
            height: root.headerHeight
            color: root.headerFill
            border.width: 1
            border.color: root.ruleColor
            Row {
                anchors.fill: parent
                Repeater {
                    model: root.columns || []
                    delegate: Text {
                        required property var modelData
                        property var columnData: modelData
                        width: root._columnWidth(columnData)
                        height: root.headerHeight
                        leftPadding: 6
                        rightPadding: 6
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root._safeText(columnData.align) === "right"
                            ? Text.AlignRight
                            : Text.AlignLeft
                        text: root._safeText(columnData.label)
                        color: root.ink
                        font.pixelSize: 9
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }
            }
        }

        Repeater {
            model: Math.max(1, root.rows.length)
            delegate: Rectangle {
                id: rowDelegate
                required property int index
                property int rowIndex: rowDelegate.index
                property var rowData: root.rows.length > 0 ? root.rows[rowDelegate.index] : ({})
                width: root.width
                height: Math.max(root.rowHeight, rowCells.implicitHeight + 12)
                color: root.rows.length <= 0
                    ? root.rowFill
                    : (rowDelegate.index % 2 === 0 ? root.rowFill : root.alternateRowFill)
                border.width: 1
                border.color: root.rowRuleColor

                Row {
                    id: rowCells
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.rows.length > 0
                    Repeater {
                        model: root.columns || []
                        delegate: Text {
                            required property var modelData
                            property var columnData: modelData
                            width: root._columnWidth(columnData)
                            leftPadding: 6
                            rightPadding: 6
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: root._safeText(columnData.align) === "right"
                                ? Text.AlignRight
                                : Text.AlignLeft
                            text: root._safeText(rowDelegate.rowData[root._safeText(columnData.key)])
                            color: root.ink
                            font.pixelSize: 9
                            wrapMode: (columnData.key === "description" || columnData.key === "matterName") ? Text.Wrap : Text.NoWrap
                            elide: (columnData.key === "description" || columnData.key === "matterName") ? Text.ElideNone : Text.ElideRight
                        }
                    }
                }

                Text {
                    anchors.fill: parent
                    visible: root.rows.length <= 0
                    leftPadding: 8
                    verticalAlignment: Text.AlignVCenter
                    text: root.emptyText
                    color: root.mutedInk
                    font.pixelSize: 9
                    font.italic: true
                    elide: Text.ElideRight
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: root.rows.length > 0 && !!rowDelegate.rowData.openAction
                    hoverEnabled: enabled
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: root.rowClicked(rowDelegate.rowData)
                    onDoubleClicked: root.rowDoubleClicked(rowDelegate.rowData)
                }
            }
        }
    }
}
