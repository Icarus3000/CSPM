import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../standards"

Item {
    id: root
    property var activeWorkspace: null
    property string searchFilter: ""

    ListModel {
        id: entitiesModel
    }

    Component.onCompleted: {
        loadData()
    }

    function loadData() {
        entitiesModel.clear()
        if (app && app.corporateController) {
            var raw = app.corporateController.listCorporateEntities()
            for (var i = 0; i < raw.length; i++) {
                entitiesModel.append(raw[i])
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Typography.spacingL

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Corporate Entities"
                font.pixelSize: Typography.fontSizeH2
                font.weight: Typography.fontWeightBold
                color: Typography.textStrong
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "New Entity"
                onClicked: {
                    if (activeWorkspace) {
                        activeWorkspace.openTabByRoute("/corporate/profile", { "EntityID": "" })
                    }
                }
            }
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: entitiesModel
            clip: true
            spacing: Typography.spacingS

            delegate: Rectangle {
                width: ListView.view.width
                height: 60
                color: "white"
                border.color: Typography.borderLight
                radius: Typography.radiusM

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Typography.spacingM
                    
                    ColumnLayout {
                        spacing: 2
                        Label {
                            text: model.LegalName || "Unnamed Entity"
                            font.pixelSize: Typography.fontSizeUI
                            font.weight: Typography.fontWeightBold
                        }
                        Label {
                            text: (model.Jurisdiction || "Unknown") + " | " + (model.Status || "Active")
                            font.pixelSize: Typography.fontSizeCaption
                            color: Typography.textMuted
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "View Profile"
                        onClicked: {
                            if (activeWorkspace) {
                                activeWorkspace.openTabByRoute("/corporate/profile", {
                                    "EntityID": model.EntityID,
                                    "LegalName": model.LegalName
                                })
                            }
                        }
                    }
                }
            }
        }
    }
}
