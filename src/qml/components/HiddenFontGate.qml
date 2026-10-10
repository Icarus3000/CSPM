import QtQml

// Item-owned scalar publication. The font binding only reads pixelSize;
// it never mutates its own dependency or retains QObject wrappers in JS maps.
QtObject {
    id: gate
    property real inputPixelSize: 12
    property bool active: true
    property real snapshot: 12
    property bool initialized: false
    readonly property real pixelSize: snapshot

    function publish() {
        if (initialized && active && snapshot !== inputPixelSize)
            snapshot = inputPixelSize
    }
    onInputPixelSizeChanged: publish()
    onActiveChanged: publish()
    Component.onCompleted: {
        snapshot = inputPixelSize
        initialized = true
    }
}
