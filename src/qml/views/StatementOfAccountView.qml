pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root
    clip: true

    property var t
    property var appRef
    property var sfxBus
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    readonly property bool isProMode: appStyle === "Professional"
    
    // Core parameters for statement
    property string selectedClientLabel: ""
    property string selectedClientId: ""
    property string asOfDateText: ""
    property bool openItemsOnly: true

    // Report data
    property var reportData: null
    property bool busy: false
    property string statusText: "Select a client and click Generate Statement."

    onVisibleChanged: {
        if (visible && (root.selectedClientId || root.selectedClientLabel)) {
            root.loadStatement()
        }
    }
    onSelectedClientIdChanged: {
        if (visible && root.selectedClientId) {
            root.loadStatement()
        }
    }
    onSelectedClientLabelChanged: {
        if (visible && root.selectedClientLabel) {
            root.loadStatement()
        }
    }

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    signal reportWindowRequested(var reportDocument)

    function loadStatement() {
        if (!root.selectedClientLabel && !root.selectedClientId) {
            root.statusText = "Please specify a client."
            return
        }
        
        if (!root.appRef || typeof root.appRef.getStatementOfAccount !== "function") {
            root.statusText = "Backend not available."
            return
        }

        root.busy = true
        root.statusText = "Generating statement..."
        
        var payload = {
            "client": root.selectedClientLabel || root.selectedClientId,
            "clientId": root.selectedClientId,
            "asOfDate": root.asOfDateText,
            "openItemsOnly": root.openItemsOnly
        }
        
        // This is a synchronous call to the backend
        var res = root.appRef.getStatementOfAccount(payload)
        
        root.busy = false
        if (res && res.ok) {
            root.reportData = res
            root.statusText = "Statement generated."
        } else {
            root.reportData = null
            root.statusText = "Error: " + (res ? res.message : "Failed to load statement.")
        }
    }
    
    function printStatement() {
        if (!root.reportData || !root.reportData.ok) {
            root.statusText = "Please generate a statement first."
            return
        }
        root.reportWindowRequested(root.reportData)
    }

    Rectangle {
        anchors.fill: parent
        color: SemanticTheme.surfaceApp(root.t, root.appStyle)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.isProMode ? 16 : 12
            spacing: 12

            // Header Section
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                radius: root.isProMode ? visualRules.radiusPanel : 6
                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 16
                    
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: "Statement of Account"
                            font.pixelSize: visualRules.proWorkspaceTitleFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.DemiBold
                            color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                        }
                        Text {
                            text: root.selectedClientLabel || root.selectedClientId || "No client selected"
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            color: SemanticTheme.inkMuted(root.t, root.appStyle)
                            elide: Text.ElideRight
                        }
                    }
                    
                    RowLayout {
                        spacing: 12
                        
                        ColumnLayout {
                            spacing: 4
                            Text {
                                text: "As of Date"
                                font.pixelSize: visualRules.proCaptionFontPx
                                font.family: visualRules.textFontFamily
                                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                            }
                            TextField {
                                id: asOfDateInput
                                text: root.asOfDateText
                                placeholderText: "YYYY-MM-DD (or blank for today)"
                                font.pixelSize: visualRules.proBodyFontPx
                                font.family: visualRules.textFontFamily
                                implicitWidth: 150
                                color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                onTextChanged: root.asOfDateText = text
                            }
                        }
                        
                        ColumnLayout {
                            spacing: 4
                            Text {
                                text: "Filter"
                                font.pixelSize: visualRules.proCaptionFontPx
                                font.family: visualRules.textFontFamily
                                color: SemanticTheme.inkMuted(root.t, root.appStyle)
                            }
                            CheckBox {
                                text: "Open Items Only"
                                checked: root.openItemsOnly
                                font.pixelSize: visualRules.proBodyFontPx
                                font.family: visualRules.textFontFamily
                                onCheckedChanged: root.openItemsOnly = checked
                            }
                        }
                        
                        Button {
                            text: "Generate"
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.Medium
                            enabled: !root.busy
                            onClicked: root.loadStatement()
                        }
                        
                        Button {
                            text: "Print / Export"
                            font.pixelSize: visualRules.proBodyFontPx
                            font.family: visualRules.textFontFamily
                            font.weight: Font.Medium
                            enabled: root.reportData !== null
                            onClicked: root.printStatement()
                        }
                    }
                }
            }

            // Body Section
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: SemanticTheme.surfacePanel(root.t, root.appStyle)
                radius: root.isProMode ? visualRules.radiusPanel : 6
                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    
                    // Summary Cards
                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.reportData !== null
                        spacing: 16
                        
                        Repeater {
                            model: (root.reportData && root.reportData.cards) ? root.reportData.cards : []
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 70
                                color: SemanticTheme.surfaceRaised(root.t, root.appStyle)
                                radius: 4
                                border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                                
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 2
                                    Text {
                                        text: modelData.label || ""
                                        font.pixelSize: visualRules.proCaptionFontPx
                                        font.family: visualRules.textFontFamily
                                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                                        Layout.alignment: Qt.AlignHCenter
                                    }
                                    Text {
                                        text: modelData.displayValue || ""
                                        font.pixelSize: visualRules.proWorkspaceTitleFontPx
                                        font.family: visualRules.textFontFamily
                                        font.weight: Font.DemiBold
                                        color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                                        Layout.alignment: Qt.AlignHCenter
                                    }
                                }
                            }
                        }
                    }
                    
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: SemanticTheme.borderSubtle(root.t, root.appStyle)
                        visible: root.reportData !== null
                    }
                    
                    // Table Header
                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.reportData !== null
                        spacing: 8
                        
                        Text { text: "Date"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.preferredWidth: 90 }
                        Text { text: "Ref"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.preferredWidth: 90 }
                        Text { text: "Description"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.fillWidth: true }
                        Text { text: "Charges"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Credits"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Balance"; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkMuted(root.t, root.appStyle); Layout.preferredWidth: 110; horizontalAlignment: Text.AlignRight }
                    }
                    
                    // Table Body
                    ListView {
                        id: eventsList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.reportData !== null
                        clip: true
                        spacing: 2
                        model: (root.reportData && root.reportData.rows) ? root.reportData.rows : []
                        
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 36
                            color: index % 2 === 0 ? SemanticTheme.surfaceApp(root.t, root.appStyle) : "transparent"
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 2
                                anchors.rightMargin: 2
                                spacing: 8
                                
                                Text { text: modelData.date || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.preferredWidth: 90; elide: Text.ElideRight }
                                Text { text: modelData.reference || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.preferredWidth: 90; elide: Text.ElideRight }
                                Text { text: modelData.description || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.fillWidth: true; elide: Text.ElideRight }
                                Text { text: modelData.debitFormatted || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                                Text { text: modelData.creditFormatted || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                                Text { text: modelData.balanceFormatted || ""; font.pixelSize: visualRules.proBodyFontPx; font.family: visualRules.textFontFamily; font.weight: Font.Medium; color: SemanticTheme.inkPrimary(root.t, root.appStyle); Layout.preferredWidth: 110; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                    
                    // Status
                    Text {
                        visible: root.reportData === null
                        text: root.statusText
                        font.pixelSize: visualRules.proBodyFontPx
                        font.family: visualRules.textFontFamily
                        color: SemanticTheme.inkMuted(root.t, root.appStyle)
                        Layout.alignment: Qt.AlignCenter
                        Layout.fillHeight: true
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
}
