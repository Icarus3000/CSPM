import QtQml

// Hidden controls retain their last scalar layout inputs. Data and model state
// remain live. Reactivation publishes current inputs synchronously before paint.
QtObject {
    id: gate
    property var inputMetrics: null
    property bool active: false
    property var snapshot: null
    property int revision: 0

    function publish() {
        if (!active) return
        if (!inputMetrics) {
            if (snapshot !== null) {
                snapshot = null
                revision += 1
            }
            return
        }
        var next = {}
        var keys = Object.keys(inputMetrics)
        var changed = !snapshot || Object.keys(snapshot).length !== keys.length
        for (var index = 0; index < keys.length; ++index) {
            var key = keys[index]
            next[key] = inputMetrics[key]
            if (!snapshot || snapshot[key] !== next[key]) changed = true
        }
        if (!changed) return
        snapshot = next
        revision += 1
    }

    onInputMetricsChanged: publish()
    onActiveChanged: publish()
    Component.onCompleted: publish()
}
