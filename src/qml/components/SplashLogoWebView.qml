import QtQuick
import QtWebView

Item {
    id: root

    property url logoPlaybackUrl: ""
    property int reloadToken: 0
    property real logoOversample: 1.0
    property bool logoVisible: true

    signal loadingChanged(int status, int errorCode, string errorString)

    function restartAnimation() {
        if (!logoPlaybackUrl || String(logoPlaybackUrl).length <= 0) return
        webView.url = logoPlaybackUrl
    }

    onReloadTokenChanged: restartAnimation()

    WebView {
        id: webView
        anchors.fill: parent
        visible: root.logoVisible
        url: root.logoPlaybackUrl

        onLoadingChanged: function(loadRequest) {
            var req = loadRequest || null
            var status = req && typeof req.status === "number" ? req.status : 0
            var errorCode = req && typeof req.errorCode === "number" ? req.errorCode : 0
            var errorText = req && req.errorString ? String(req.errorString) : ""
            root.loadingChanged(status, errorCode, errorText)
        }
    }
}
