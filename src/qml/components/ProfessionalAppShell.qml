pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme

Item {
    id: root

    default property alias workspaceContent: workspaceHost.data
    readonly property alias workspaceHostItem: workspaceHost

    property var t
    property var metrics
    property var sfxBus
    required property var appRoot
    property Item backdropSource: null
    property string appStyle: "Professional"
    property bool shellEnabled: false
    property bool interactive: true
    property bool detachedWindow: false
    readonly property bool _topBarVisible: shellEnabled || detachedWindow
    property var modules: []
    property var favorites: []
    property var tabs: []
    property var flyoutModuleData: null
    property var rightDrawerState: ({})
    property string activeModuleId: ""
    property string flyoutModuleId: ""
    property string activeItemId: ""
    property string activeTabId: ""
    property string moduleTitle: ""
    property string itemTitle: ""
    property string subtitle: ""
    property string closeGuardTabId: ""
    property string closeGuardMessage: ""
    property bool activeDirty: false
    readonly property bool rightDrawerOpen: {
        if (!root.rightDrawerState) return false
        if (root.rightDrawerState.open !== undefined) return !!root.rightDrawerState.open
        if (root.rightDrawerState.visible !== undefined) return !!root.rightDrawerState.visible
        return false
    }
    readonly property int professionalHeaderHeightPx: 72
    readonly property int professionalRailWidthPx: 56
    readonly property int professionalTabBarHeightPx: 38
    readonly property int professionalBreadcrumbHeightPx: 44

    signal moduleRequested(var moduleData)
    signal homeRequested()
    signal moduleFavoriteRequested(var moduleData, bool remove)
    signal flyoutItemRequested(var moduleData, var itemData)
    signal flyoutDismissed()
    signal omniSearchRequested(string query)
    signal tabActivated(string tabId)
    signal tabCloseRequested(string tabId)
    signal tabOpenInNewWindowRequested(string tabId)
    signal tabPinRequested(string tabId)
    signal tabReordered(int fromIndex, int toIndex)
    signal tabDuplicateRequested(string tabId)
    signal tabFavoriteRequested(string tabId)
    signal favoriteRequested(var favData)
    signal favoriteRemoveRequested(var favData)
    signal favoriteReordered(int fromIndex, int toIndex)
    signal itemFavoriteRequested(var moduleData, var itemData, bool remove)
    signal closeGuardSaveRequested()
    signal closeGuardDiscardRequested(string tabId)
    signal closeGuardCancelRequested()
    signal rightDrawerDismissed()
    signal detachedReturnToDockRequested()

    clip: false

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }

    ProfessionalTopHeader {
        id: proTopHeader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root._topBarVisible ? root.professionalHeaderHeightPx : 0
        z: 55
        appRoot: root.appRoot
        backdropSource: root.backdropSource
        shellEnabled: root._topBarVisible
        returnToDockVisible: root.detachedWindow
        visible: root._topBarVisible
        onOmniSearchRequested: function(query) {
            root.omniSearchRequested(query)
        }
        onHomeRequested: {
            root.homeRequested()
        }
        onReturnToDockRequested: {
            root.detachedReturnToDockRequested()
        }
    }

    ProfessionalModuleRail {
        id: proModuleRail
        anchors.left: parent.left
        anchors.top: root.shellEnabled ? proTopHeader.bottom : parent.top
        anchors.bottom: parent.bottom
        visible: root.shellEnabled
        width: root.shellEnabled ? root.professionalRailWidthPx : 0
        z: 40
        t: root.t
        appStyle: root.appStyle
        modules: root.modules
        favorites: root.favorites
        activeModuleId: root.activeModuleId
        flyoutModuleId: root.flyoutModuleId
        interactive: root.interactive
        onModuleRequested: function(moduleData) {
            root.moduleRequested(moduleData)
        }
        onModuleFavoriteRequested: function(moduleData, remove) {
            root.moduleFavoriteRequested(moduleData, remove)
        }
        onFavoriteRequested: function(favData) {
            root.favoriteRequested(favData)
        }
        onFavoriteRemoveRequested: function(favData) {
            root.favoriteRemoveRequested(favData)
        }
        onFavoriteReordered: function(fromIndex, toIndex) {
            root.favoriteReordered(fromIndex, toIndex)
        }
    }

    ProfessionalWorkTabBar {
        id: proWorkTabBar
        anchors.left: root.shellEnabled ? proModuleRail.right : parent.left
        anchors.right: parent.right
        anchors.top: root.shellEnabled ? proTopHeader.bottom : parent.top
        height: root.shellEnabled ? root.professionalTabBarHeightPx : 0
        visible: root.shellEnabled
        z: 35
        t: root.t
        appStyle: root.appStyle
        tabs: root.tabs
        favorites: root.favorites
        activeTabId: root.activeTabId
        interactive: root.interactive
        onTabActivated: function(tabId) {
            root.tabActivated(tabId)
        }
        onTabCloseRequested: function(tabId) {
            root.tabCloseRequested(tabId)
        }
        onTabOpenInNewWindowRequested: function(tabId) {
            root.tabOpenInNewWindowRequested(tabId)
        }
        onTabPinRequested: function(tabId) {
            root.tabPinRequested(tabId)
        }
        onTabReordered: function(fromIndex, toIndex) {
            root.tabReordered(fromIndex, toIndex)
        }
        onTabDuplicateRequested: function(tabId) {
            root.tabDuplicateRequested(tabId)
        }
        onTabFavoriteRequested: function(tabId) {
            root.tabFavoriteRequested(tabId)
        }
    }

    ProfessionalBreadcrumbBar {
        id: proBreadcrumbBar
        anchors.left: root.shellEnabled ? proModuleRail.right : parent.left
        anchors.right: parent.right
        anchors.top: root.shellEnabled ? proWorkTabBar.bottom : parent.top
        height: root.shellEnabled ? root.professionalBreadcrumbHeightPx : 0
        visible: root.shellEnabled
        z: 35
        t: root.t
        appStyle: root.appStyle
        moduleTitle: root.moduleTitle
        itemTitle: root.itemTitle
        subtitle: root.subtitle
        dirty: root.activeDirty
    }

    Item {
        id: workspaceHost
        anchors.top: root.shellEnabled ? proBreadcrumbBar.bottom : (root._topBarVisible ? proTopHeader.bottom : parent.top)
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.left: root.shellEnabled ? proModuleRail.right : parent.left
        z: 10
        clip: false
    }

    ProfessionalModuleFlyout {
        id: proModuleFlyout
        anchors.left: root.shellEnabled ? proModuleRail.right : parent.left
        anchors.top: root.shellEnabled ? proTopHeader.bottom : parent.top
        anchors.bottom: parent.bottom
        visible: root.shellEnabled && String(root.flyoutModuleId || "").length > 0
        z: 120
        t: root.t
        appStyle: root.appStyle
        moduleData: root.flyoutModuleData
        activeItemId: root.activeItemId
        interactive: root.interactive
        favorites: root.favorites
        onItemRequested: function(moduleData, itemData) {
            root.flyoutItemRequested(moduleData, itemData)
        }
        onItemFavoriteRequested: function(moduleData, itemData, remove) {
            root.itemFavoriteRequested(moduleData, itemData, remove)
        }
        onDismissed: root.flyoutDismissed()
    }

    ProfessionalRightDrawer {
        id: proRightDrawer
        anchors.top: root.shellEnabled ? proWorkTabBar.bottom : parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        visible: root.shellEnabled && root.rightDrawerOpen
        z: 130
        t: root.t
        appStyle: root.appStyle
        drawerState: root.rightDrawerState
        interactive: root.interactive
        onDismissed: root.rightDrawerDismissed()
    }

    Item {
        id: option3CloseGuardOverlay
        anchors.fill: parent
        visible: root.shellEnabled && String(root.closeGuardTabId || "").length > 0
        enabled: visible
        z: 170

        Rectangle {
            anchors.fill: parent
            color: SemanticTheme.overlayScrim(root.t, root.appStyle)
        }

        Rectangle {
            id: option3CloseGuardCard
            width: Math.min(440, Math.max(320, parent.width - 80))
            height: 178
            anchors.centerIn: parent
            radius: visualRules.radiusPanel
            color: SemanticTheme.surfacePanel(root.t, root.appStyle)
            border.width: 1
            border.color: SemanticTheme.borderStrong(root.t, root.appStyle)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    Layout.fillWidth: true
                    text: "Unsaved changes"
                    font.family: "Segoe UI"
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: root.closeGuardMessage
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    color: SemanticTheme.inkMuted(root.t, root.appStyle)
                    wrapMode: Text.WordWrap
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Item { Layout.fillWidth: true }

                    PillButton {
                        t: root.t
                        metrics: root.metrics
                        sfxBus: root.sfxBus
                        appStyle: root.appStyle
                        text: "Save"
                        primary: false
                        Layout.preferredWidth: 86
                        Layout.preferredHeight: 34
                        onClicked: root.closeGuardSaveRequested()
                    }

                    PillButton {
                        t: root.t
                        metrics: root.metrics
                        sfxBus: root.sfxBus
                        appStyle: root.appStyle
                        text: "Discard"
                        primary: true
                        Layout.preferredWidth: 92
                        Layout.preferredHeight: 34
                        onClicked: root.closeGuardDiscardRequested(root.closeGuardTabId)
                    }

                    PillButton {
                        t: root.t
                        metrics: root.metrics
                        sfxBus: root.sfxBus
                        appStyle: root.appStyle
                        text: "Cancel"
                        primary: false
                        Layout.preferredWidth: 86
                        Layout.preferredHeight: 34
                        onClicked: root.closeGuardCancelRequested()
                    }
                }
            }
        }
    }
}
