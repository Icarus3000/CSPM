    component DataTable: Rectangle {
        id: table
        property string tableId: ""
        property string title: ""
        property var defaultColumns: []
        property var rows: []
        property int visibleRows: 6
        property string emptyText: "No rows returned."
        property string defaultSortKey: ""
        property bool defaultSortAscending: true
        property bool expandedMode: false
        property bool fillAvailableHeight: false
        readonly property var effectiveColumns: root.tableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
        readonly property var allColumns: root.allTableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
        readonly property var effectiveRows: root.tableSortedRows(table.tableId, table.rows, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)

        implicitHeight: table.fillAvailableHeight
            ? 420
            : (titleRow.implicitHeight + 38 + Math.max(38, Math.min(Math.max(1, table.effectiveRows.length), table.visibleRows) * 38) + 18)
        radius: root.isProMode ? 5 : root.sectionRadiusPx
        color: root.panelColor
        border.width: 1
        border.color: root.borderColor
        clip: true

        ListModel {
            id: columnModel
        }

        onAllColumnsChanged: {
            var cols = table.allColumns
            if (!cols || cols.length === 0) return
            
            if (columnModel.count === 0) {
                for (var i = 0; i < cols.length; i++) {
                    var c = cols[i]
                    columnModel.append({
                        key: c.key || "",
                        label: c.label || "",
                        width: root.tableColumnWidth(c),
                        align: c.align || "left",
                        visible: root.tableColumnVisible(c),
                        resizable: c.resizable !== false,
                        sortKey: c.sortKey || "",
                        fmt: c.fmt || "",
                        minWidth: c.minWidth || 50
                    })
                }
            } else {
                for (var i = 0; i < cols.length; i++) {
                    var tc = cols[i]
                    for (var j = 0; j < columnModel.count; j++) {
                        var mc = columnModel.get(j)
                        if (mc.key === tc.key) {
                            var newVisible = root.tableColumnVisible(tc)
                            if (mc.visible !== newVisible) {
                                columnModel.setProperty(j, "visible", newVisible)
                            }
                            break
                        }
                    }
                }
            }
        }

        function isRight(column) {
            return String(column && column.align ? column.align : "").toLowerCase() === "right"
        }

        function cellText(row, column) {
            if (!row || !column)
                return ""
            var key = String(column.key || "")
            var value = row[key]
            if (value === undefined || value === null)
                return ""
            return String(value)
        }

        Popup {
            id: columnPopup
            x: Math.max(0, table.width - width - 10)
            y: Math.max(34, titleRow.height + 4)
            width: 250
            modal: false
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: root.surfaceColor
                radius: root.isProMode ? 5 : root.sectionRadiusPx
                border.width: 1
                border.color: root.borderColor
            }

            contentItem: ColumnLayout {
                spacing: 4
                Repeater {
                    model: root.allTableColumns(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                    delegate: CheckBox {
                        id: columnCheck
                        required property var modelData
                        text: String(modelData.label || modelData.key || "")
                        checked: modelData.visible !== false
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        indicator: Rectangle {
                            implicitWidth: 15
                            implicitHeight: 15
                            x: 8
                            y: (columnCheck.height - height) / 2
                            radius: 2
                            color: columnCheck.checked ? root.accentColor : root.inputColor
                            border.width: 1
                            border.color: columnCheck.checked ? root.accentColor : root.borderColor

                            Text {
                                anchors.centerIn: parent
                                text: columnCheck.checked ? "X" : ""
                                color: "#ffffff"
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                        contentItem: Text {
                            text: columnCheck.text
                            color: root.inkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 12
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            leftPadding: 30
                            rightPadding: 8
                        }
                        onToggled: root.setTableColumnVisible(
                            table.tableId,
                            String(modelData.key || ""),
                            checked,
                            table.defaultColumns,
                            table.defaultSortKey,
                            table.defaultSortAscending
                        )
                    }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            RowLayout {
                id: titleRow
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                spacing: 6

                Text {
                    text: table.title
                    color: root.inkColor
                    font.family: visualRules.textFontFamily
                    font.pixelSize: table.expandedMode ? 15 : 13
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    verticalAlignment: Text.AlignVCenter
                }

                Text {
                    text: String(table.effectiveRows.length) + " rows"
                    color: root.subtleInkColor
                    font.family: visualRules.textFontFamily
                    font.pixelSize: 11
                    Layout.preferredWidth: 72
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }

                Button {
                    id: columnButton
                    text: "Columns"
                    Layout.preferredWidth: 86
                    Layout.preferredHeight: 28
                    onClicked: columnPopup.open()
                }

                Button {
                    text: table.expandedMode ? "Restore" : "Expand"
                    Layout.preferredWidth: 82
                    Layout.preferredHeight: 28
                    onClicked: table.expandedMode ? root.restoreExpandedTable() : root.expandTable(table.tableId)
                }
            }

            Flickable {
                id: tableBody
                Layout.fillWidth: true
                Layout.fillHeight: table.fillAvailableHeight
                Layout.preferredHeight: table.fillAvailableHeight
                    ? 320
                    : (30 + Math.max(38, Math.min(Math.max(1, table.effectiveRows.length), table.visibleRows) * 38))
                clip: true
                contentWidth: Math.max(width, headerRow.width)
                contentHeight: height
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                interactive: !root.tableResizeActive

                Column {
                    id: tableContent
                    width: tableBody.contentWidth
                    height: tableBody.height

                    Rectangle {
                        id: headerBand
                        width: parent.width
                        height: 30
                        radius: root.isProMode ? 4 : root.sectionRadiusPx
                        color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.isProMode ? 0.07 : 0.12)
                        clip: true

                        Row {
                            id: headerRow
                            height: parent.height
                            Repeater {
                                model: columnModel
                                delegate: Rectangle {
                                    id: headerCell
                                    required property int index
                                    required property var model
                                    property string columnKey: headerCell.model.key
                                    property real pressRootX: 0
                                    property bool manualDragging: false
                                    visible: headerCell.model.visible
                                    width: visible ? headerCell.model.width : 0
                                    height: headerRow.height
                                    color: root.activeHeaderDragTableId === table.tableId && root.activeHeaderDropColumnKey === columnKey
                                        ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.18)
                                        : "transparent"

                                    MouseArea {
                                        id: titleDragArea
                                        anchors.fill: parent
                                        anchors.rightMargin: headerCell.model.resizable ? root.tableResizeHandleWidthPx : 0
                                        hoverEnabled: true
                                        preventStealing: true
                                        cursorShape: Qt.PointingHandCursor
                                        onPressed: function(mouse) {
                                            var mapped = titleDragArea.mapToItem(root, mouse.x, mouse.y)
                                            headerCell.pressRootX = mapped.x
                                            headerCell.manualDragging = false
                                            root.activeHeaderDragTableId = table.tableId
                                            root.activeHeaderDragColumnKey = headerCell.columnKey
                                            root.activeHeaderDropColumnKey = headerCell.columnKey
                                            mouse.accepted = true
                                        }
                                        onPositionChanged: function(mouse) {
                                            if (!pressed) return
                                            var mapped = titleDragArea.mapToItem(root, mouse.x, mouse.y)
                                            if (Math.abs(mapped.x - headerCell.pressRootX) >= 10)
                                                headerCell.manualDragging = true
                                            if (headerCell.manualDragging) {
                                                var inRow = titleDragArea.mapToItem(headerRow, mouse.x, mouse.y)
                                                
                                                var hoverCursor = 0
                                                var targetKey = headerCell.columnKey
                                                for (var i = 0; i < columnModel.count; i++) {
                                                    var c = columnModel.get(i)
                                                    if (!c.visible) continue
                                                    if (inRow.x >= hoverCursor && inRow.x < hoverCursor + c.width) {
                                                        targetKey = c.key
                                                        break
                                                    }
                                                    hoverCursor += c.width
                                                }
                                                root.activeHeaderDropColumnKey = targetKey
                                                mouse.accepted = true
                                            }
                                        }
                                        onReleased: function(mouse) {
                                            if (headerCell.manualDragging) {
                                                var targetKey = root.activeHeaderDropColumnKey
                                                if (targetKey && targetKey !== headerCell.columnKey) {
                                                    var toIdx = -1
                                                    for (var i = 0; i < columnModel.count; i++) {
                                                        if (columnModel.get(i).key === targetKey) {
                                                            toIdx = i
                                                            break
                                                        }
                                                    }
                                                    if (toIdx >= 0) {
                                                        columnModel.move(headerCell.index, toIdx, 1)
                                                    }
                                                    root.moveTableColumnByKey(
                                                        table.tableId,
                                                        headerCell.columnKey,
                                                        targetKey,
                                                        table.defaultColumns,
                                                        table.defaultSortKey,
                                                        table.defaultSortAscending
                                                    )
                                                }
                                            } else {
                                                root.setTableSort(
                                                    table.tableId,
                                                    headerCell.columnKey,
                                                    table.defaultColumns,
                                                    table.defaultSortKey,
                                                    table.defaultSortAscending
                                                )
                                            }
                                            root.resetHeaderDrag()
                                            headerCell.manualDragging = false
                                            mouse.accepted = true
                                        }
                                        onCanceled: {
                                            root.resetHeaderDrag()
                                            headerCell.manualDragging = false
                                        }
                                    }

                                    Text {
                                        anchors.fill: parent
                                        anchors.leftMargin: root.tableCellPadXPx
                                        anchors.rightMargin: headerCell.model.resizable ? root.tableResizeHandleWidthPx : 8
                                        text: headerCell.model.label || headerCell.model.key || ""
                                        color: root.mutedInkColor
                                        font.family: visualRules.textFontFamily
                                        font.pixelSize: 11
                                        font.bold: true
                                        verticalAlignment: Text.AlignVCenter
                                        horizontalAlignment: headerCell.model.align === "right" ? Text.AlignRight : Text.AlignLeft
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        id: resizeLine
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        width: 3
                                        color: resizeHandle.containsMouse
                                            ? root.accentColor
                                            : Qt.rgba(root.mutedInkColor.r, root.mutedInkColor.g, root.mutedInkColor.b, 0.22)
                                        visible: headerCell.model.resizable
                                    }

                                    MouseArea {
                                        id: resizeHandle
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        width: root.tableResizeHandleWidthPx
                                        z: 10
                                        hoverEnabled: true
                                        preventStealing: true
                                        cursorShape: Qt.SplitHCursor
                                        enabled: headerCell.model.resizable
                                        property real startRootX: 0
                                        property real startWidth: 0
                                        onPressed: function(mouse) {
                                            root.tableResizeActive = true
                                            mouse.accepted = true
                                            var mapped = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                            startRootX = mapped.x
                                            startWidth = headerCell.model.width
                                        }
                                        onPositionChanged: function(mouse) {
                                            var mapped = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                            var newWidth = Math.max(headerCell.model.minWidth, startWidth + (mapped.x - startRootX))
                                            columnModel.setProperty(headerCell.index, "width", newWidth)
                                        }
                                        onReleased: {
                                            root.setTableColumnWidth(
                                                table.tableId,
                                                headerCell.columnKey,
                                                headerCell.model.width,
                                                table.defaultColumns,
                                                table.defaultSortKey,
                                                table.defaultSortAscending,
                                                true
                                            )
                                            root.resetResizeState()
                                        }
                                        onCanceled: {
                                            root.setTableColumnWidth(
                                                table.tableId,
                                                headerCell.columnKey,
                                                headerCell.model.width,
                                                table.defaultColumns,
                                                table.defaultSortKey,
                                                table.defaultSortAscending,
                                                true
                                            )
                                            root.resetResizeState()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ListView {
                        id: rowList
                        width: parent.width
                        height: Math.max(38, parent.height - headerBand.height)
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: table.effectiveRows
                        delegate: Rectangle {
                            id: rowDelegate
                            required property int index
                            required property var modelData
                            property var rowData: modelData
                            width: rowList.width
                            height: 38
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(root.inkColor.r, root.inkColor.g, root.inkColor.b, 0.035)

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: root.borderColor
                            }

                            Row {
                                id: cellRow
                                height: parent.height
                                Repeater {
                                    model: columnModel
                                    delegate: Rectangle {
                                        id: bodyCell
                                        required property int index
                                        required property var model
                                        visible: bodyCell.model.visible
                                        width: visible ? bodyCell.model.width : 0
                                        height: cellRow.height
                                        color: "transparent"

                                        Text {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: bodyCell.model.resizable ? root.tableResizeHandleWidthPx : 8
                                            text: table.cellText(rowDelegate.rowData, bodyCell.model)
                                            color: root.inkColor
                                            opacity: 0.92
                                            font.family: visualRules.textFontFamily
                                            font.pixelSize: 12
                                            verticalAlignment: Text.AlignVCenter
                                            horizontalAlignment: bodyCell.model.align === "right" ? Text.AlignRight : Text.AlignLeft
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: table.effectiveRows.length <= 0
                            text: table.emptyText
                            color: root.subtleInkColor
                            font.family: visualRules.textFontFamily
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }
    }
