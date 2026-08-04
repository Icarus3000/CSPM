                font.pixelSize: 11
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Text {
                text: root.cardDisplay(metricCard.card)
                color: root.inkColor
                font.family: visualRules.textFontFamily
                font.pixelSize: 22
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

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

        function horizontalWidth() {
            return Math.max(tableBody.width, root.tableTotalColumnWidth(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending))
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
                contentWidth: table.horizontalWidth()
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
                            anchors.fill: parent
                            Repeater {
                                model: table.allColumns
                                delegate: Rectangle {
                                    id: headerCell
                                    required property var modelData
                                    property string columnKey: String(modelData.key || "")
                                    property real pressRootX: 0
                                    property bool manualDragging: false
                                    visible: root.tableColumnVisible(modelData)
                                    width: visible ? root.tableColumnWidth(modelData) : 0
                                    height: headerRow.height
                                    color: root.activeHeaderDragTableId === table.tableId && root.activeHeaderDropColumnKey === columnKey
                                        ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.18)
                                        : "transparent"

                                    MouseArea {
                                        id: titleDragArea
                                        anchors.fill: parent
                                        anchors.rightMargin: headerCell.modelData.resizable === false ? 0 : root.tableResizeHandleWidthPx
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
                                            if (!pressed)
                                                return
                                            var mapped = titleDragArea.mapToItem(root, mouse.x, mouse.y)
                                            if (Math.abs(mapped.x - headerCell.pressRootX) >= 10)
                                                headerCell.manualDragging = true
                                            if (headerCell.manualDragging) {
                                                var inRow = titleDragArea.mapToItem(headerRow, mouse.x, mouse.y)
                                                root.activeHeaderDropColumnKey = root.tableColumnKeyAtX(
                                                    table.tableId,
                                                    inRow.x,
                                                    table.defaultColumns,
                                                    table.defaultSortKey,
                                                    table.defaultSortAscending
                                                )
                                                mouse.accepted = true
                                            }
                                        }
                                        onReleased: function(mouse) {
                                            if (headerCell.manualDragging) {
                                                var releasedInRow = titleDragArea.mapToItem(headerRow, mouse.x, mouse.y)
                                                var targetColumnKey = root.tableColumnKeyAtX(
                                                    table.tableId,
                                                    releasedInRow.x,
                                                    table.defaultColumns,
                                                    table.defaultSortKey,
                                                    table.defaultSortAscending
                                                )
                                                root.moveTableColumnByKey(
                                                    table.tableId,
                                                    root.activeHeaderDragColumnKey,
                                                    targetColumnKey,
                                                    table.defaultColumns,
                                                    table.defaultSortKey,
                                                    table.defaultSortAscending
                                                )
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
                                        anchors.rightMargin: root.tableHeaderRightPadding(headerCell.modelData)
                                        text: root.tableHeaderText(table.tableId, headerCell.modelData, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                                        color: root.mutedInkColor
                                        font.family: visualRules.textFontFamily
                                        font.pixelSize: 11
                                        font.bold: true
                                        verticalAlignment: Text.AlignVCenter
                                        horizontalAlignment: table.isRight(headerCell.modelData) ? Text.AlignRight : Text.AlignLeft
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
                                        visible: headerCell.modelData.resizable !== false
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
                                        enabled: headerCell.modelData.resizable !== false
                                        property real startRootX: 0
                                        property real startWidth: 0
                                        onPressed: function(mouse) {
                                            root.tableResizeActive = true
                                            mouse.accepted = true
                                            var mapped = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                            startRootX = mapped.x
                                            startWidth = root.tableColumnWidth(headerCell.modelData)
                                        }
                                        onPositionChanged: function(mouse) {
                                            var mapped = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                            root.setTableColumnWidth(
                                                table.tableId,
                                                headerCell.columnKey,
                                                startWidth + (mapped.x - startRootX),
                                                table.defaultColumns,
                                                table.defaultSortKey,
                                                table.defaultSortAscending,
                                                false
                                            )
                                        }
                                        onReleased: {
                                            root.saveTablePreferencesNow(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
                                            root.resetResizeState()
                                        }
                                        onCanceled: {
                                            root.saveTablePreferencesNow(table.tableId, table.defaultColumns, table.defaultSortKey, table.defaultSortAscending)
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
                                anchors.fill: parent
                                Repeater {
                                    model: table.allColumns
                                    delegate: Rectangle {
                                        id: bodyCell
                                        required property var modelData
                                        visible: root.tableColumnVisible(modelData)
                                        width: visible ? root.tableColumnWidth(modelData) : 0
                                        height: cellRow.height
                                        color: "transparent"

                                        Text {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            text: table.cellText(rowDelegate.rowData, bodyCell.modelData)
                                            color: root.inkColor
                                            opacity: 0.92
                                            font.family: visualRules.textFontFamily
                                            font.pixelSize: 12
                                            verticalAlignment: Text.AlignVCenter
                                            horizontalAlignment: table.isRight(bodyCell.modelData) ? Text.AlignRight : Text.AlignLeft
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

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        ScrollView {
            id: reportScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: reportScroll.availableWidth
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    spacing: 8

                    Text {
                        text: "A/R Aging & Detail"
                        color: root.inkColor
                        font.family: visualRules.textFontFamily
                        font.pixelSize: root.isProMode ? 18 : root.ratioPx(0.019, 15)
                        font.bold: true
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    TextField {
                        id: asOfField
                        text: root.asOfDateText
                        placeholderText: "yyyy-mm-dd"
                        enabled: !root.busy
                        selectByMouse: true
                        Layout.preferredWidth: 128
                        Layout.preferredHeight: 34
                        color: root.inkColor
                        placeholderTextColor: root.subtleInkColor
                        font.pixelSize: 12
                        onTextChanged: root.asOfDateText = text
                        background: Rectangle {
                            color: root.inputColor
                            radius: root.isProMode ? 4 : root.sectionRadiusPx
                            border.width: asOfField.activeFocus ? 2 : 1
                            border.color: asOfField.activeFocus ? root.accentColor : root.borderColor
                        }
                    }

                    TextField {
                        id: searchField
                        text: root.queryText
                        placeholderText: "Search invoice, client..."
                        enabled: !root.busy
                        selectByMouse: true
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 34
                        color: root.inkColor
                        placeholderTextColor: root.subtleInkColor
                        font.pixelSize: 12
                        onTextChanged: root.queryText = text
                        onAccepted: root.refreshReport()
                        background: Rectangle {
                            color: root.inputColor
                            radius: root.isProMode ? 4 : root.sectionRadiusPx
                            border.width: searchField.activeFocus ? 2 : 1
                            border.color: searchField.activeFocus ? root.accentColor : root.borderColor
