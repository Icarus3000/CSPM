"""Real Qt activation tree scope contracts without a native window."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from synthetic_activation_fanout import run_controls, VARIANTS


def test_same_native_item_tree_retains_all_activation_dispatch_with_exact_filter_counts():
    result = run_controls(child_count=31, samples=3)
    assert result["status"] == "PASS" and result["nodeCount"] == 32
    assert result["sameTreeAcrossVariants"]
    rows = result["variants"]
    assert tuple(row["variant"] for row in rows) == VARIANTS
    assert [row["observedFilterCalls"] for row in rows] == [0, 192, 192, 576, 6]
    assert [row["observedTypedActivationCalls"] for row in rows] == [0, 0, 192, 576, 6]
    assert all(len(row["pairWallMs"]) == 3 and row["medianPairWallMs"] >= 0 for row in rows)
    assert all(row["allDispatchReturnedTrue"] for row in rows)


@pytest.mark.parametrize("argument,value", [("child_count",0), ("child_count",20001),
    ("child_count",True), ("child_count",1.5), ("samples",0), ("samples",31), ("samples",False)])
def test_bounded_configuration_rejects_before_qt_object_creation(argument, value):
    with pytest.raises(ValueError):
        run_controls(**{argument:value})


def test_global_and_root_scope_do_not_consume_recursive_events_or_palette_inheritance():
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
    from PySide6.QtGui import QColor
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from shiboken6 import delete

    app = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
Item {
    palette.button: "#123456"
    property color observed: palette.button
    property color childObserved: leaf.palette.button
    Item { id: leaf; objectName: "syntheticLeaf" }
}''', QUrl("file:///SyntheticActivationPalette.qml"))
    assert component.isReady(), component.errorString()
    root = component.create()
    leaf = root.findChild(QQuickItem, "syntheticLeaf")
    engine.globalObject().setProperty("syntheticRoot", engine.newQObject(root))

    class Observer(QObject):
        def __init__(self):
            super().__init__()
            self.deliveries = []
        def eventFilter(self, watched, event):
            if event.type() in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                self.deliveries.append((watched, event.type()))
            return False

    sentinel = Observer()
    leaf.installEventFilter(sentinel)
    global_filter, root_filter = Observer(), Observer()
    try:
        for target, observer in ((app, global_filter), (root, root_filter)):
            target.installEventFilter(observer)
            for kind in (QEvent.WindowActivate, QEvent.WindowDeactivate):
                assert QCoreApplication.sendEvent(root, QEvent(kind))
            target.removeEventFilter(observer)
        assert [kind for _,kind in sentinel.deliveries] == [QEvent.WindowActivate,
            QEvent.WindowDeactivate, QEvent.WindowActivate, QEvent.WindowDeactivate]
        assert [watched for watched,_ in root_filter.deliveries] == [root,root]
        assert len(global_filter.deliveries) == 4
        assert root.property("observed") == QColor("#123456")
        assert root.property("childObserved") == QColor("#123456")
        assert not engine.evaluate('syntheticRoot.palette.button = "#abcdef"; true').isError()
        assert root.property("observed") == QColor("#abcdef")
        assert root.property("childObserved") == QColor("#abcdef")
    finally:
        leaf.removeEventFilter(sentinel)
        for observer in (sentinel, global_filter, root_filter):
            delete(observer)
        root.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
