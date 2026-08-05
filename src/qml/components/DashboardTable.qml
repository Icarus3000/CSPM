pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property string title: "Table"
    property var headers: []
    property var rows: []
    property string rowKind: "top"
    property var t
    property string appStyle: "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    readonly property color panelColor: SemanticTheme.surfacePanel(root.t, root.appStyle)
    readonly property color inputColor: SemanticTheme.surfaceInput(root.t, root.appStyle)
    readonly property color inkColor: SemanticTheme.inkPrimary(root.t, root.appStyle)
    readonly property color mutedInkColor: SemanticTheme.inkMuted(root.t, root.appStyle)
    readonly property color borderColor: SemanticTheme.borderSubtle(root.t, root.appStyle)

    radius: visualRules.radiusPanel
    color: root.panelColor
    border.width: 1
    border.color: root.borderColor
    clip: true

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    function safeRows() {
        return root.rows && root.rows.length !== undefined ? root.rows : []
    }

    function money(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        var sign = n < 0 ? "-" : ""
        n = Math.abs(n)
        var parts = n.toFixed(2).split(".")
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
        return sign + "$" + parts.join(".")
    }

    function pct(value) {
        var n = Number(value)
        if (!isFinite(n)) n = 0
        return n.toFixed(1) + "%"
    }

    function cellText(row, columnIndex) {
        if (!row) return ""
        if (root.rowKind === "quarters") {
            if (columnIndex === 0) return String(row.quarter || "")
            if (columnIndex === 1) return money(row.revenue)
            if (columnIndex === 2) return money(row.expenses)
            if (columnIndex === 3) return money(row.hstCollected)
            if (columnIndex === 4) return money(row.hstPaid)
            if (columnIndex === 5) return money(row.netHst)
        }
        if (root.rowKind === "ar") {
            if (columnIndex === 0) return String(row.client || "")
            if (columnIndex === 1) return money(row.amount)
        }
        if (columnIndex === 0) return String(row.client || "")
        if (columnIndex === 1) return money(row.amount)
        if (columnIndex === 2) return pct(row.sharePct)
        return ""
    }

    function columnWidth(columnIndex) {
        if (root.rowKind === "quarters") {
            return columnIndex === 0 ? 78 : 102
        }
        if (columnIndex === 0) return 260
        if (columnIndex === 1) return 112
        return 70
    }

    function columnAlignment(columnIndex) {
        if (root.rowKind === "quarters")
            return columnIndex === 0 ? Text.AlignLeft : Text.AlignRight
        return columnIndex === 0 ? Text.AlignLeft : Text.AlignRight
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        Text {
            Layout.fillWidth: true
            text: root.title
            color: root.inkColor
            font.family: visualRules.textFontFamily
            font.pixelSize: 13
            font.bold: true
            elide: Text.ElideRight
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            radius: visualRules.radiusPanel
            color: root.inputColor
            border.width: 1
            border.color: root.borderColor

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                Repeater {
                    model: root.headers
                    delegate: Text {
                        required property int index
                        required property string modelData
                        Layout.preferredWidth: root.columnWidth(index)
                        Layout.fillWidth: index === 0
                        text: modelData
                        color: root.mutedInkColor
                        horizontalAlignment: root.columnAlignment(index)
                        verticalAlignment: Text.AlignVCenter
                        font.family: visualRules.textFontFamily
                        font.pixelSize: 11
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }
            }
        }

        ScrollView {
            id: tableScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            Column {
                width: tableScroll.availableWidth
                spacing: 0

                Repeater {
                    model: root.safeRows()

                    delegate: Rectangle {
                        id: rowDelegate
                        required property int index
                        required property var modelData
                        property var rowData: modelData

                        width: parent ? parent.width : 0
                        height: 32
                        color: index % 2 === 0 ? SemanticTheme.tableRowBackground(root.t, root.appStyle) : SemanticTheme.tableAlternateRowBackground(root.t, root.appStyle)

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8

                            Repeater {
                                model: root.headers
                                delegate: Text {
                                    required property int index
                                    Layout.preferredWidth: root.columnWidth(index)
                                    Layout.fillWidth: index === 0
                                    text: root.cellText(rowDelegate.rowData, index)
                                    color: root.inkColor
                                    horizontalAlignment: root.columnAlignment(index)
                                    verticalAlignment: Text.AlignVCenter
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
