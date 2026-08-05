import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: overlay
    anchors.fill: parent
    color: "#B3000000"
    z: 100

    MouseArea { anchors.fill: parent; onClicked: { clientPopup.close(); matterPopup.close() } }

    SemanticTheme { id: theme }

    ListModel { id: clientListModel }
    ListModel { id: matterListModel }

    function openOverlay() {
        var clients = trayController.availableClients()
        var matters = trayController.availableMatters()
        clientListModel.clear()
        for (var i = 0; i < clients.length; i++)
            clientListModel.append({"name": clients[i]})
        matterListModel.clear()
        for (var j = 0; j < matters.length; j++)
            matterListModel.append({"name": matters[j]})
        clientInput.text = ""
        matterInput.text = ""
        overlay.visible = true
        clientInput.forceActiveFocus()
    }

    Rectangle {
        id: dialogBox
        width: 380
        height: 300
        anchors.centerIn: parent
        radius: theme.radiusLarge
        color: theme.background
        border.color: theme.border
        border.width: 1
        clip: false

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            Text {
                text: "Start New Timer"
                font.bold: true; font.pixelSize: 18
                color: theme.textPrimary
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 4
            }

            // ── Client Field ─────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text { text: "Client"; font.pixelSize: 12; font.bold: true; color: theme.textSecondary }

                Item {
                    id: clientFieldWrapper
                    Layout.fillWidth: true
                    height: 36

                    Rectangle {
                        id: clientField
                        anchors.fill: parent
                        color: theme.surface
                        border.color: clientInput.activeFocus ? theme.accentBlue : theme.border
                        border.width: clientInput.activeFocus ? 2 : 1
                        radius: theme.radiusSmall

                        TextInput {
                            id: clientInput
                            anchors.fill: parent
                            anchors.leftMargin: 12; anchors.rightMargin: 32
                            font.pixelSize: 13; color: theme.textPrimary
                            verticalAlignment: Text.AlignVCenter
                            clip: true; selectByMouse: true

                            Text {
                                text: "Type to search clients..."
                                color: theme.textSecondary; font: clientInput.font
                                anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                                visible: !clientInput.text && !clientInput.activeFocus
                            }

                            onTextEdited: {
                                var filtered = trayController.filterClients(text)
                                clientListModel.clear()
                                for (var i = 0; i < filtered.length; i++)
                                    clientListModel.append({"name": filtered[i]})
                                if (filtered.length > 0) clientPopup.open(); else clientPopup.close()
                                var fm = trayController.filterMattersByClientAndText(text, matterInput.text)
                                matterListModel.clear()
                                for (var j = 0; j < fm.length; j++)
                                    matterListModel.append({"name": fm[j]})
                            }
                            onActiveFocusChanged: {
                                if (activeFocus && !text && !clientPopup.visible) {
                                    var all = trayController.availableClients()
                                    clientListModel.clear()
                                    for (var i = 0; i < all.length; i++)
                                        clientListModel.append({"name": all[i]})
                                    clientPopup.open()
                                }
                            }
                            Keys.onPressed: function(event) {
                                if (event.key === Qt.Key_Tab || event.key === Qt.Key_Down) {
                                    if (clientListModel.count > 0 && clientPopup.visible) {
                                        clientListView.forceActiveFocus()
                                        clientListView.currentIndex = 0
                                        event.accepted = true
                                    }
                                }
                            }
                        }

                        Text {
                            text: clientPopup.visible ? "\u25B2" : "\u25BC"
                            font.pixelSize: 10; color: theme.textSecondary
                            anchors.right: parent.right; anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -8
                                onClicked: {
                                    if (clientPopup.visible) { clientPopup.close() }
                                    else {
                                        var all = trayController.filterClients(clientInput.text)
                                        clientListModel.clear()
                                        for (var i = 0; i < all.length; i++)
                                            clientListModel.append({"name": all[i]})
                                        clientPopup.open()
                                        clientInput.forceActiveFocus()
                                    }
                                }
                            }
                        }
                    }

                    Popup {
                        id: clientPopup
                        y: clientFieldWrapper.height
                        width: clientFieldWrapper.width
                        height: Math.min(clientListView.contentHeight + 4, 200)
                        padding: 2
                        closePolicy: Popup.CloseOnPressOutsideParent

                        background: Rectangle {
                            color: theme.background
                            border.color: theme.border; border.width: 1
                            radius: theme.radiusSmall
                        }
                        contentItem: ListView {
                            id: clientListView
                            model: clientListModel
                            clip: true
                            currentIndex: -1
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            
                            Keys.onPressed: function(event) {
                                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    if (currentIndex >= 0 && currentIndex < count) {
                                        clientInput.text = model.get(currentIndex).name
                                        clientPopup.close()
                                        var fm = trayController.filterMattersByClient(clientInput.text)
                                        matterListModel.clear()
                                        for (var i = 0; i < fm.length; i++)
                                            matterListModel.append({"name": fm[i]})
                                        matterInput.forceActiveFocus()
                                        event.accepted = true
                                    }
                                }
                            }
                            
                            delegate: ItemDelegate {
                                width: clientListView.width
                                height: 32
                                highlighted: ListView.isCurrentItem
                                contentItem: Text {
                                    text: model.name
                                    font.pixelSize: 13; color: theme.textPrimary
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 8; elide: Text.ElideRight
                                }
                                background: Rectangle {
                                    color: parent.hovered || parent.highlighted ? theme.surface : "transparent"
                                }
                                onClicked: {
                                    clientInput.text = model.name
                                    clientPopup.close()
                                    var fm = trayController.filterMattersByClient(model.name)
                                    matterListModel.clear()
                                    for (var i = 0; i < fm.length; i++)
                                        matterListModel.append({"name": fm[i]})
                                    matterInput.forceActiveFocus()
                                }
                            }
                        }
                    }
                }
            }

            // ── Matter Field ─────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text { text: "Matter"; font.pixelSize: 12; font.bold: true; color: theme.textSecondary }

                Item {
                    id: matterFieldWrapper
                    Layout.fillWidth: true
                    height: 36

                    Rectangle {
                        id: matterField
                        anchors.fill: parent
                        color: theme.surface
                        border.color: matterInput.activeFocus ? theme.accentBlue : theme.border
                        border.width: matterInput.activeFocus ? 2 : 1
                        radius: theme.radiusSmall

                        TextInput {
                            id: matterInput
                            anchors.fill: parent
                            anchors.leftMargin: 12; anchors.rightMargin: 32
                            font.pixelSize: 13; color: theme.textPrimary
                            verticalAlignment: Text.AlignVCenter
                            clip: true; selectByMouse: true

                            Text {
                                text: "Type to search matters..."
                                color: theme.textSecondary; font: matterInput.font
                                anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                                visible: !matterInput.text && !matterInput.activeFocus
                            }

                            onTextEdited: {
                                var filtered = trayController.filterMattersByClientAndText(clientInput.text, text)
                                matterListModel.clear()
                                for (var i = 0; i < filtered.length; i++)
                                    matterListModel.append({"name": filtered[i]})
                                if (filtered.length > 0) matterPopup.open(); else matterPopup.close()
                            }
                            onActiveFocusChanged: {
                                if (activeFocus && !text && !matterPopup.visible) {
                                    var all = trayController.filterMattersByClient(clientInput.text)
                                    matterListModel.clear()
                                    for (var i = 0; i < all.length; i++)
                                        matterListModel.append({"name": all[i]})
                                    matterPopup.open()
                                }
                            }
                            Keys.onPressed: function(event) {
                                if (event.key === Qt.Key_Tab || event.key === Qt.Key_Down) {
                                    if (matterListModel.count > 0 && matterPopup.visible) {
                                        matterListView.forceActiveFocus()
                                        matterListView.currentIndex = 0
                                        event.accepted = true
                                    }
                                }
                            }
                        }

                        Text {
                            text: matterPopup.visible ? "\u25B2" : "\u25BC"
                            font.pixelSize: 10; color: theme.textSecondary
                            anchors.right: parent.right; anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -8
                                onClicked: {
                                    if (matterPopup.visible) { matterPopup.close() }
                                    else {
                                        var all = trayController.filterMattersByClientAndText(clientInput.text, matterInput.text)
                                        matterListModel.clear()
                                        for (var i = 0; i < all.length; i++)
                                            matterListModel.append({"name": all[i]})
                                        matterPopup.open()
                                        matterInput.forceActiveFocus()
                                    }
                                }
                            }
                        }
                    }

                    Popup {
                        id: matterPopup
                        y: matterFieldWrapper.height
                        width: matterFieldWrapper.width
                        height: Math.min(matterListView.contentHeight + 4, 200)
                        padding: 2
                        closePolicy: Popup.CloseOnPressOutsideParent

                        background: Rectangle {
                            color: theme.background
                            border.color: theme.border; border.width: 1
                            radius: theme.radiusSmall
                        }
                        contentItem: ListView {
                            id: matterListView
                            model: matterListModel
                            clip: true
                            currentIndex: -1
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            
                            Keys.onPressed: function(event) {
                                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    if (currentIndex >= 0 && currentIndex < count) {
                                        matterInput.text = model.get(currentIndex).name
                                        matterPopup.close()
                                        event.accepted = true
                                    }
                                }
                            }
                            
                            delegate: ItemDelegate {
                                width: matterListView.width
                                height: 32
                                highlighted: ListView.isCurrentItem
                                contentItem: Text {
                                    text: model.name
                                    font.pixelSize: 13; color: theme.textPrimary
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 8; elide: Text.ElideRight
                                }
                                background: Rectangle {
                                    color: parent.hovered || parent.highlighted ? theme.surface : "transparent"
                                }
                                onClicked: {
                                    matterInput.text = model.name
                                    matterPopup.close()
                                }
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Button {
                    text: "Cancel"
                    Layout.fillWidth: true
                    font.pixelSize: 14; font.bold: true
                    contentItem: Text { text: parent.text; color: theme.textSecondary; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "transparent"; border.color: theme.border; radius: theme.radiusSmall }
                    onClicked: { clientPopup.close(); matterPopup.close(); overlay.visible = false }
                }

                Button {
                    text: "Start Timer"
                    Layout.fillWidth: true
                    font.pixelSize: 14; font.bold: true
                    contentItem: Text { text: parent.text; color: "white"; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: theme.accentBlue; radius: theme.radiusSmall }
                    onClicked: {
                        trayController.start_new_timer(clientInput.text, matterInput.text)
                        clientPopup.close(); matterPopup.close()
                        overlay.visible = false
                    }
                }
            }
        }
    }
}
