pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../standards"
import "../standards/SemanticTheme.js" as SemanticTheme
import QtWebEngine

Item {
    id: root
    property var t
    property var windowRef
    property var sfxBus
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property string appStyle: (root.appRef && root.appRef.appStyle) ? String(root.appRef.appStyle) : "Professional"
    property bool isZenMode: false
    property string dashboardData: ""
    property bool isZenWebViewLoaded: false
    property bool isDashboardWebViewLoaded: false

    VisualRules { id: visualRules }

    onAppRefChanged: refreshDashboardData()

    Component.onCompleted: refreshDashboardData()

    function refreshDashboardData() {
        if (root.appRef && root.appRef.fetchProductivityDashboard && root.dashboardData === "") {
            root.dashboardData = root.appRef.fetchProductivityDashboard()
        }
    }

    function safeHydrate(webView, funcName, dataStr) {
        if (!dataStr || dataStr === "") return;
        var script = "(function() {" +
            "if (typeof window." + funcName + " === 'function') {" +
            "    window." + funcName + "(" + dataStr + ");" +
            "} else {" +
            "    var attempts = 0;" +
            "    var interval = setInterval(function() {" +
            "        attempts++;" +
            "        if (typeof window." + funcName + " === 'function') {" +
            "            clearInterval(interval);" +
            "            window." + funcName + "(" + dataStr + ");" +
            "        } else if (attempts > 100) {" +
            "            clearInterval(interval);" +
            "            console.error('Timed out waiting for ' + '" + funcName + "');" +
            "        }" +
            "    }, 50);" +
            "}" +
            "})();";
        webView.runJavaScript(script);
    }

    onDashboardDataChanged: {
        if (root.dashboardData !== "") {
            if (root.isDashboardWebViewLoaded) safeHydrate(dashboardWebView, "hydrateDashboard", root.dashboardData)
            if (root.isZenWebViewLoaded) safeHydrate(zenWebView, "hydrateDashboard", root.dashboardData)
        }
    }


    // Zen Mode Dedicated Window
    Window {
        id: zenPopup
        onClosing: root.isZenMode = false
        title: "Zen Mode - Productivity & Utilization"
        width: 1024
        height: 768
        visibility: root.isZenMode ? Window.Maximized : Window.Hidden
        color: SemanticTheme.surfaceApp(root.t, root.appStyle)
        
        WebEngineView {
            id: zenWebView
            anchors.fill: parent
            anchors.margins: 12
            backgroundColor: "transparent"
            url: Qt.resolvedUrl("../../web/productivity_dashboard/dist/index.html")
            onLoadingChanged: function(loadRequest) {
                if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                    root.isZenWebViewLoaded = true
                    if (root.dashboardData !== "") {
                        root.safeHydrate(zenWebView, "hydrateDashboard", root.dashboardData)
                    }
                }
            }
        }
    }

    // Inline Dashboard
    Rectangle {
        id: bgRect
        anchors.fill: parent
        color: SemanticTheme.surfaceApp(root.t, root.appStyle)
        
        WebEngineView {
            id: dashboardWebView
            anchors.fill: parent
            anchors.margins: 12
            backgroundColor: "transparent"
            visible: !root.isZenMode // Hide inline when Zen is active
            url: Qt.resolvedUrl("../../web/productivity_dashboard/dist/index.html")
            onLoadingChanged: function(loadRequest) {
                if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                    root.isDashboardWebViewLoaded = true
                    if (root.dashboardData !== "") {
                        root.safeHydrate(dashboardWebView, "hydrateDashboard", root.dashboardData)
                    }
                }
            }
            onPdfPrintingFinished: function(filePath, success) {
                if (success) {
                    Qt.openUrlExternally("file:///" + filePath)
                }
            }
        }

        FileDialog {
            id: pdfFileDialog
            fileMode: FileDialog.SaveFile
            nameFilters: ["PDF Files (*.pdf)"]
            onAccepted: {
                var path = pdfFileDialog.selectedFile.toString().replace("file:///", "")
                if (path.length > 0) {
                    dashboardWebView.printToPdf(path)
                    if (root.sfxBus && root.sfxBus.playUiClick) root.sfxBus.playUiClick("save", 0.4)
                }
            }
        }

        // Export PDF Button
        Rectangle {
            id: exportPdfBtn
            anchors.top: parent.top
            anchors.right: zenModeBtn.left
            anchors.margins: 20
            width: 140
            height: 36
            radius: 4
            color: SemanticTheme.buttonPrimary(root.t, root.appStyle)
            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
            border.width: 1
            visible: !root.isZenMode

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                
                Text {
                    text: "\uE8A6" // Save/Export icon
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 14
                    color: SemanticTheme.textOnPrimary(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignVCenter
                }
                
                Text {
                    text: "EXPORT PDF"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: SemanticTheme.textOnPrimary(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.sfxBus && root.sfxBus.playUiClick) root.sfxBus.playUiClick("affirm", 0.38)
                    var defaultName = dashboardWebView.title !== "" ? dashboardWebView.title : "Productivity_Report"
                    pdfFileDialog.currentFile = "file:///" + defaultName + ".pdf"
                    pdfFileDialog.open()
                }
            }
        }

        // Zen Mode Toggle Button (Inline)
        Rectangle {
            id: zenModeBtn
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 20
            width: 140
            height: 36
            radius: 18
            color: SemanticTheme.surfaceInput(root.t, root.appStyle)
            border.color: SemanticTheme.borderSubtle(root.t, root.appStyle)
            border.width: 1
            visible: !root.isZenMode

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                
                Text {
                    text: "\uE740" // Expand icon
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 14
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignVCenter
                }
                
                Text {
                    text: "Zen Mode"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: SemanticTheme.inkPrimary(root.t, root.appStyle)
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.sfxBus && root.sfxBus.playUiClick) root.sfxBus.playUiClick("affirm", 0.38)
                    root.isZenMode = true
                }
            }
        }
    }
}
