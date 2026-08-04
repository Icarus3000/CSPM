import codecs

def find_block(text, start_str, end_str):
    start = text.find(start_str)
    if start == -1: return -1, -1
    end = text.find(end_str, start + len(start_str))
    if end == -1: return -1, -1
    return start, end + len(end_str)

with codecs.open(r"src\qml\components\ClientLedgerReportPanel.qml", "r", "utf-8") as f:
    qml = f.read()

# 1. Properties
s_prop = "    property var tableColumns: ["
e_prop = "    function setColumnWidth(idx, width) {\r\n        root.tableColumns[idx].width = Math.max(20, width)\r\n        root.tableColumnsTrigger += 1\r\n    }"
start, end = find_block(qml, s_prop, e_prop)
if start != -1:
    repl = """    ListModel {
        id: columnModel
        Component.onCompleted: {
            append({ key: "date", label: "Date", width: 90, align: Text.AlignLeft, fmt: "text", visible: true, resizable: true });
            append({ key: "clientName", label: "Client", width: 120, align: Text.AlignLeft, fmt: "text", visible: true, resizable: true });
            append({ key: "matterName", label: "Matter", width: 120, align: Text.AlignLeft, fmt: "text", visible: true, resizable: true });
            append({ key: "type", label: "Type", width: 90, align: Text.AlignLeft, fmt: "type", visible: true, resizable: true });
            append({ key: "description", label: "Description", width: 250, align: Text.AlignLeft, fmt: "text", visible: true, resizable: true });
            append({ key: "hours", label: "Hours", width: 50, align: Text.AlignRight, fmt: "decimal1", visible: true, resizable: true });
            append({ key: "debit", label: "Debit", width: 80, align: Text.AlignRight, fmt: "currency", visible: true, resizable: true });
            append({ key: "credit", label: "Credit", width: 80, align: Text.AlignRight, fmt: "currency", visible: true, resizable: true });
            append({ key: "balance", label: "Balance", width: 90, align: Text.AlignRight, fmt: "currency", visible: true, resizable: false });
        }
    }
    
    property int lastVisibleColIndex: {
        for (var i = columnModel.count - 1; i >= 0; i--) {
            if (columnModel.get(i).visible) return i
        }
        return -1
    }
    
    function moveColumn(fromIdx, toIdx) {
        if (fromIdx === toIdx) return
        columnModel.move(fromIdx, toIdx, 1)
    }

    function toggleColumnVisibility(idx) {
        var isVis = columnModel.get(idx).visible
        columnModel.setProperty(idx, "visible", !isVis)
    }

    function setColumnWidth(idx, width) {
        columnModel.setProperty(idx, "width", Math.max(20, width))
    }

    function indexOfColumnKey(key) {
        for (var i = 0; i < columnModel.count; i++) {
            if (columnModel.get(i).key === key) return i
        }
        return -1
    }

    function effectiveColumnWidth(idx, parentWidth) {
        var col = columnModel.get(idx)
        if (!col || !col.visible) return 0
        if (idx !== lastVisibleColIndex) {
            return col.width > 0 ? col.width : 100
        }
        var used = 0
        for (var i = 0; i < columnModel.count; i++) {
            var c = columnModel.get(i)
            if (i !== idx && c.visible) {
                used += c.width > 0 ? c.width : 100
                used += 6
            }
        }
        return Math.max(50, parentWidth - used)
    }"""
    qml = qml[:start] + repl + qml[end:]

# 2. columns JSON mapping
s_json = "                    \"columns\": root.tableColumns.map(function(c) {"
e_json = "                    }),"
start, end = find_block(qml, s_json, e_json)
if start != -1:
    repl = """                    "columns": function() {
                        var arr = []
                        for(var i=0; i<columnModel.count; i++){ 
                            var c = columnModel.get(i); 
                            arr.push({"title": c.label, "key": c.key, "align": c.align === Text.AlignRight ? "right" : "left", "width": c.width > 0 ? c.width : undefined, "format": c.fmt === "text" ? "" : c.fmt})
                        }
                        return arr;
                    }(),"""
    qml = qml[:start] + repl + qml[end:]

# 3. Simple replacements
qml = qml.replace("model: root.tableColumns", "model: columnModel")
qml = qml.replace("root.tableColumns.length", "columnModel.count")
qml = qml.replace("headerCol.colDef", "model")
qml = qml.replace("bodyCol.colDef", "model")

# 4. Header Repeater Delegate
s_head = "                    delegate: Item {\r\n                        id: headerCol\r\n                        required property int index\r\n                        required property var modelData\r\n                        property var colDef: modelData"
e_head = "                                    onTriggered: root.toggleColumnVisibility(index)\r\n                                }\r\n                            }\r\n                        }\r\n                    }"
start, end = find_block(qml, s_head, e_head)
if start != -1:
    repl = """                    delegate: Item {
                        id: headerCol
                        required property int index
                        
                        visible: model.visible
                        width: root.effectiveColumnWidth(index, root.parent ? root.parent.width : 800)
                        height: parent ? parent.height : 34

                        Binding on width {
                            when: index === root.lastVisibleColIndex
                            value: root.effectiveColumnWidth(index, root.parent ? root.parent.width : 800)
                        }

                        // Resize handle (lives on the right edge, z=2)
                        Rectangle {
                            visible: index !== root.lastVisibleColIndex
                            width: 6
                            z: 2
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            height: parent.height * 0.7
                            color: "transparent"
                            border.color: gearHover.hovered ? "#cbd5e1" : "transparent"
                            opacity: 0.8
                            radius: 3
                            MouseArea {
                                anchors.fill: parent
                                anchors.margins: -4
                                cursorShape: Qt.SplitHCursor
                                property real startMouseX: 0
                                property real startW: 0
                                onPressed: function(mouse) {
                                    startMouseX = mouse.x
                                    startW = model.width
                                }
                                onPositionChanged: function(mouse) {
                                    if (pressed) {
                                        root.setColumnWidth(index, startW + (mouse.x - startMouseX))
                                    }
                                }
                            }
                        }

                        // Title content and Drag Zone (z=1)
                        Rectangle {
                            anchors.fill: parent
                            anchors.rightMargin: (index !== root.lastVisibleColIndex) ? 10 : 0
                            color: dropArea.containsDrag ? "#e2e8f0" : "transparent"
                            z: 1

                            Drag.active: titleDragHandler.active
                            Drag.source: { "columnKey": model.key }
                            Drag.hotSpot.x: width / 2
                            Drag.hotSpot.y: height / 2

                            DragHandler {
                                id: titleDragHandler
                                target: parent
                                xAxis.enabled: true
                                yAxis.enabled: false
                                cursorShape: Qt.OpenHandCursor
                            }

                            DropArea {
                                id: dropArea
                                anchors.fill: parent
                                property string targetColumnKey: model.key
                                onDropped: function(drop) {
                                    var sourceKey = drop.source.columnKey
                                    if (sourceKey && sourceKey !== targetColumnKey) {
                                        var sourceIndex = root.indexOfColumnKey(sourceKey)
                                        if (sourceIndex >= 0) {
                                            root.moveColumn(sourceIndex, index)
                                        }
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 4

                                Text {
                                    text: parent.parent.parent.parent.parent.headerText(model.key, model.label)
                                    Layout.fillWidth: true
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: parent.parent.parent.parent.parent.headerColor(model.key)
                                    horizontalAlignment: model.align
                                }
                                Text {
                                    visible: model.key === "balance"
                                    text: "Debits - Credits"
                                    Layout.fillWidth: true
                                    font.pixelSize: 10
                                    color: root._textMuted
                                    horizontalAlignment: model.align
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        colSettingsMenu.popup()
                                    } else {
                                        if (root.sortColumn === model.key) {
                                            root.sortAsc = !root.sortAsc
                                        } else {
                                            root.sortColumn = model.key
                                            root.sortAsc = true
                                        }
                                        root.reportEntries = root.reportEntries // Trigger re-eval
                                    }
                                }
                            }
                        }
                    }"""
    qml = qml[:start] + repl + qml[end:]


# 5. Body Repeater Delegate
s_body = "                    delegate: Item {\r\n                            id: bodyCol\r\n                            required property int index\r\n                            required property var modelData\r\n                            property var colDef: modelData"
e_body = "                                        onClicked: {\r\n                                            console.log(\"Clicked entry:\", e)\r\n                                        }\r\n                                    }\r\n                                ]\r\n                            }\r\n                        }\r\n                    }"
start, end = find_block(qml, s_body, e_body)
if start != -1:
    repl = """                    delegate: Item {
                            id: bodyCol
                            required property int index
                            
                            visible: model.visible
                            width: root.effectiveColumnWidth(index, root.parent ? root.parent.width : 800)
                            height: parent ? parent.height : 38

                            Binding on width {
                                when: index === root.lastVisibleColIndex
                                value: root.effectiveColumnWidth(index, root.parent ? root.parent.width : 800)
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: (index !== root.lastVisibleColIndex) ? 14 : 8 // pad for resize handle alignment
                                spacing: 4

                                Text {
                                    text: {
                                        var v = e[model.key]
                                        if (v === undefined || v === null) return ""
                                        if (model.fmt === "currency") {
                                            if (v === 0) return "-"
                                            return "$" + Number(v).toLocaleString(Qt.locale(), 'f', 2)
                                        } else if (model.fmt === "decimal1") {
                                            return Number(v).toLocaleString(Qt.locale(), 'f', 1)
                                        } else if (model.fmt === "type") {
                                            return String(v)
                                        }
                                        return String(v)
                                    }
                                    Layout.fillWidth: true
                                    font.pixelSize: 13
                                    font.weight: model.key === "balance" ? Font.DemiBold : Font.Normal
                                    color: {
                                        if (model.key === "balance") return root._textStrong
                                        if (model.fmt === "currency") {
                                            return Number(e[model.key]) < 0 ? "#dc2626" : root._textNormal
                                        }
                                        if (model.fmt === "type") {
                                            var t = String(e[model.key])
                                            if (t === "Time") return "#2563eb"
                                            if (t === "Fee") return "#9333ea"
                                            if (t === "Disbursement") return "#ca8a04"
                                            if (t === "Payment") return "#16a34a"
                                            if (t === "Credit/Adj") return "#059669"
                                            if (t === "Invoice") return "#dc2626"
                                        }
                                        return root._textNormal
                                    }
                                    horizontalAlignment: model.align
                                    elide: Text.ElideRight
                                    
                                    components: [
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                console.log("Clicked entry:", e)
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }"""
    qml = qml[:start] + repl + qml[end:]

with codecs.open(r"src\qml\components\ClientLedgerReportPanel.qml", "w", "utf-8") as f:
    f.write(qml)
