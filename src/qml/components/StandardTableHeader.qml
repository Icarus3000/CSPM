pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Rectangle {
    id: root

    property var t
    property string appStyle: "Professional"

    property var columns: []
    property var dynamicColumnWidths: ({})
    property string sortColumn: ""
    property bool sortAscending: true
    property real columnMargin: 12
    property real columnSpacing: 6
    property string dragDropKey: "standardColumnReorder"
    
    property real totalColumnWidth: {
        var w = 0;
        var vis = root.visibleColumns();
        for (var i = 0; i < vis.length; i++) {
            var dynW = root.dynamicColumnWidths[vis[i].key];
            w += (dynW !== undefined) ? dynW : root._baseColumnWidthFor(vis[i].key);
        }
        return w + Math.max(0, (vis.length - 1) * root.columnSpacing) + root.columnMargin;
    }
    
    property real tableScale: {
        if (!root.width) return 1.0;
        var visCols = root.visibleColumns();
        if (visCols.length === 0) return 1.0;
        var totalReq = 0;
        for (var i = 0; i < visCols.length; i++) {
            var dynW = root.dynamicColumnWidths[visCols[i].key];
            totalReq += (dynW !== undefined) ? dynW : root._baseColumnWidthFor(visCols[i].key);
        }
        totalReq += ((visCols.length - 1) * root.columnSpacing) + root.columnMargin;
        if (totalReq > root.width && root.width > 0) {
            return Math.max(0.6, root.width / totalReq);
        }
        return 1.0;
    }

    signal sortRequested(string key)
    signal configChanged(var newColumns)

    function visibleColumns() {
        var cols = []
        for (var i = 0; i < (root.columns || []).length; i++)
            if (root.columns[i].visible) cols.push(root.columns[i])
        return cols
    }

    function _baseColumnWidthFor(key) {
        if (root.dynamicColumnWidths[key] !== undefined)
            return root.dynamicColumnWidths[key]
        for (var i = 0; i < (root.columns || []).length; i++)
            if (root.columns[i].key === key) return root.columns[i].width
        return 100
    }

    function columnWidthFor(key) {
        var visCols = root.visibleColumns()
        if (visCols.length === 0) return 100 * root.tableScale
        
        var isLast = (visCols[visCols.length - 1].key === key)
        var dynamicW = root.dynamicColumnWidths[key]
        var base = (dynamicW !== undefined) ? dynamicW : root._baseColumnWidthFor(key)
        
        if (isLast) {
            var used = 0
            for (var i = 0; i < visCols.length - 1; i++) {
                var cKey = visCols[i].key
                var cDynamic = root.dynamicColumnWidths[cKey]
                var cBase = (cDynamic !== undefined) ? cDynamic : root._baseColumnWidthFor(cKey)
                used += cBase * root.tableScale
            }
            used += ((visCols.length - 1) * root.columnSpacing)
            var available = root.width - root.columnMargin - used
            var minW = (visCols[visCols.length - 1].minWidth || 50) * root.tableScale
            return Math.max(minW, available)
        }
        return base * root.tableScale
    }

    Layout.fillWidth: true
    Layout.preferredHeight: 36
    color: SemanticTheme.tableHeaderBackground(root.t, root.appStyle)
    radius: 5

    Row {
        id: headerRow
        anchors.fill: parent
        anchors.leftMargin: root.columnMargin
        anchors.rightMargin: 0 // Extend last column to far right
        spacing: root.columnSpacing

        Repeater {
            model: root.visibleColumns().length
            delegate: Item {
                id: headerCell
                required property int index
                property var colDef: root.visibleColumns()[index]
                z: headerDragArea.drag.active ? 100 : 1
                width: root.columnWidthFor(headerCell.colDef.key)
                height: headerRow.height

                DropArea {
                    anchors.fill: parent
                    keys: [root.dragDropKey]
                    onDropped: function(drop) {
                        var fromGlobalIdx = drop.source.globalColumnIndex
                        var visCols = root.visibleColumns()
                        var toKey = visCols[headerCell.index].key
                        var toGlobalIdx = -1
                        for (var i = 0; i < root.columns.length; i++) {
                            if (root.columns[i].key === toKey) { toGlobalIdx = i; break }
                        }
                        if (fromGlobalIdx >= 0 && toGlobalIdx >= 0 && fromGlobalIdx !== toGlobalIdx) {
                            var cols = root.columns.slice()
                            var moved = cols.splice(fromGlobalIdx, 1)[0]
                            cols.splice(toGlobalIdx, 0, moved)
                            root.configChanged(cols)
                        }
                    }
                }

                MouseArea {
                    id: resizeHandle
                    z: 20
                    visible: headerCell.index < root.visibleColumns().length - 1
                    width: 14
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.right: parent.right
                    cursorShape: Qt.SplitHCursor
                    hoverEnabled: true
                    preventStealing: true

                    Rectangle {
                        anchors.centerIn: parent
                        width: 2
                        height: parent.height - 10
                        color: (resizeHandle.containsMouse || resizeHandle.pressed) ? SemanticTheme.accentPrimary(root.t, root.appStyle) : SemanticTheme.borderSubtle(root.t, root.appStyle)
                        radius: 1
                    }

                    property real startMouseX: 0
                    property real startLeftWidth: 0
                    property real startRightWidth: 0
                    property real combinedWidth: 0
                    property string leftKey: ""
                    property string rightKey: ""

                    onPressed: function(mouse) {
                        var visCols = root.visibleColumns()
                        var leftCol = visCols[headerCell.index]
                        var rightCol = visCols[headerCell.index + 1]
                        if (!leftCol || !rightCol) return
                        leftKey = leftCol.key
                        rightKey = rightCol.key
                        startLeftWidth = root.columnWidthFor(leftCol.key) / root.tableScale
                        startRightWidth = root.columnWidthFor(rightCol.key) / root.tableScale
                        combinedWidth = startLeftWidth + startRightWidth
                        startMouseX = resizeHandle.mapToItem(root, mouse.x, mouse.y).x
                    }

                    onPositionChanged: function(mouse) {
                        if (!pressed) return
                        var visCols = root.visibleColumns()
                        var leftCol = visCols[headerCell.index]
                        var rightCol = visCols[headerCell.index + 1]
                        if (!leftCol || !rightCol) return

                        var currentMouseX = resizeHandle.mapToItem(root, mouse.x, mouse.y).x
                        var dx = currentMouseX - startMouseX

                        var minLeft = leftCol.minWidth || 50
                        var minRight = rightCol.minWidth || 50
                        var maxLeft = combinedWidth - minRight

                        var newLeftWidth = Math.max(minLeft, Math.min(maxLeft, Math.round(startLeftWidth + dx)))
                        var newRightWidth = combinedWidth - newLeftWidth

                        var newWidths = Object.assign({}, root.dynamicColumnWidths)
                        newWidths[leftKey] = newLeftWidth
                        newWidths[rightKey] = newRightWidth
                        root.dynamicColumnWidths = newWidths
                    }

                    onReleased: function() {
                        var cols = root.columns.slice()
                        for (var i = 0; i < cols.length; i++) {
                            var newWidth = root.dynamicColumnWidths[cols[i].key]
                            if (newWidth !== undefined) cols[i].width = newWidth
                        }
                        root.dynamicColumnWidths = {}
                        root.configChanged(cols)
                    }
                }

                Row {
                    anchors.left: parent.left
                    anchors.right: resizeHandle.visible ? resizeHandle.left : parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.rightMargin: 4
                    spacing: 3

                    Label {
                        width: parent.width - sortIndicator.width - 3
                        height: parent.height
                        text: headerCell.colDef.label
                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        font.weight: Font.DemiBold
                        font.pixelSize: Math.max(9, Math.round(12 * root.tableScale))
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: headerCell.colDef.align === "right" ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                    }

                    Label {
                        id: sortIndicator
                        width: root.sortColumn === headerCell.colDef.key ? implicitWidth : 0
                        height: parent.height
                        text: root.sortAscending ? "\u25B2" : "\u25BC"
                        visible: root.sortColumn === headerCell.colDef.key
                        color: SemanticTheme.accentPrimary(root.t, root.appStyle)
                        font.pixelSize: 9
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                MouseArea {
                    id: headerDragArea
                    anchors.left: parent.left
                    anchors.right: resizeHandle.visible ? resizeHandle.left : parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    cursorShape: Qt.PointingHandCursor
                    property int globalColumnIndex: {
                        var visCols = root.visibleColumns()
                        var key = visCols[headerCell.index].key
                        for (var i = 0; i < root.columns.length; i++)
                            if (root.columns[i].key === key) return i
                        return -1
                    }
                    drag.target: headerDragProxy
                    drag.axis: Drag.XAxis
                    onClicked: root.sortRequested(headerCell.colDef.key)
                    onReleased: {
                        headerDragProxy.Drag.drop()
                        headerDragProxy.x = 0
                        headerDragProxy.y = 0
                    }

                    Rectangle {
                        id: headerDragProxy
                        width: headerCell.width
                        height: headerCell.height
                        color: SemanticTheme.surfaceInput(root.t, root.appStyle)
                        radius: 4
                        opacity: 0.8
                        visible: false
                        Drag.active: headerDragArea.drag.active
                        Drag.keys: [root.dragDropKey]
                        Drag.source: headerDragArea
                        Drag.hotSpot.x: width / 2
                        Drag.hotSpot.y: height / 2
                        states: State {
                            when: headerDragArea.drag.active
                            PropertyChanges { target: headerDragProxy; visible: true }
                        }
                        Label {
                            anchors.centerIn: parent
                            text: headerCell.colDef.label
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                            font.weight: Font.DemiBold
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }
    }
}
