import QtQuick
import QtWebEngine

Item {
    id: root

    property url logoPlaybackUrl: ""
    property int reloadToken: 0
    property real logoOversample: 1.0
    property bool logoVisible: true
    property string playerUrl: ""

    signal loadingChanged(int status, int errorCode, string errorString)

    function buildPlayerUrl(restartToken) {
        if (!logoPlaybackUrl || String(logoPlaybackUrl).length <= 0) return "about:blank"
        var base = String(Qt.resolvedUrl("SplashLogoWebEnginePlayer.html"))
        var sep = (base.indexOf("?") >= 0) ? "&" : "?"
        return base + sep
            + "logo=" + encodeURIComponent(String(logoPlaybackUrl))
            + "&run=" + encodeURIComponent(String(restartToken))
    }

    function loadPlayer(restartToken) {
        playerUrl = buildPlayerUrl(restartToken)
    }

    function restartAnimation() {
        if (!logoPlaybackUrl || String(logoPlaybackUrl).length <= 0) return
        try {
            engineView.runJavaScript(
                "try { window.restartSplash && window.restartSplash(); } catch (e) {}"
            )
        } catch (e) {
            loadPlayer(Date.now())
        }
    }

    onLogoPlaybackUrlChanged: loadPlayer(reloadToken)

    onReloadTokenChanged: {
        if (logoPlaybackUrl && String(logoPlaybackUrl).length > 0
                && String(engineView.url) !== "about:blank") restartAnimation()
    }

    Component.onCompleted: loadPlayer(reloadToken)

    WebEngineView {
        id: engineView
        anchors.fill: parent
        visible: root.logoVisible
        url: root.playerUrl
        backgroundColor: "transparent"
        settings.localContentCanAccessFileUrls: true
        settings.localContentCanAccessRemoteUrls: false
        settings.javascriptCanOpenWindows: false

        onLoadingChanged: function(loadRequest) {
            var req = loadRequest || null
            var status = req && typeof req.status === "number" ? req.status : 0
            var errorCode = req && typeof req.errorCode === "number" ? req.errorCode : 0
            var errorText = req && req.errorString ? String(req.errorString) : ""
            root.loadingChanged(status, errorCode, errorText)
        }
    }
}
