"""Safe QtQml-only checks; no QQuickWindow or WebEngine is constructed."""
from pathlib import Path
import sys

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/python"))


@pytest.fixture
def gate():
    application = QCoreApplication.instance() or QCoreApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(
        Path(__file__).resolve().parents[1] / "src/qml/components/LayoutMetricsGate.qml")))
    assert component.isReady(), component.errorString()
    item = component.create()
    assert item is not None, component.errorString()
    yield item
    item.deleteLater()
    application.processEvents()


def snapshot(gate):
    value = gate.property("snapshot")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_hidden_controls_publish_latest_complete_geometry_once_on_reactivation(gate):
    gate.setProperty("active", True)
    gate.setProperty("inputMetrics", {"contentW": 1100, "contentH": 760})
    gate.setProperty("active", False)
    seen = []
    gate.snapshotChanged.connect(lambda: seen.append(snapshot(gate)))
    gate.setProperty("inputMetrics", {"contentW": 1920, "contentH": 760})
    gate.setProperty("inputMetrics", {"contentW": 1920, "contentH": 1040})
    assert snapshot(gate) == {"contentW": 1100, "contentH": 760}
    assert seen == []
    gate.setProperty("active", True)
    assert seen == [{"contentW": 1920, "contentH": 1040}]
    assert gate.property("revision") == 2


def test_duplicate_metrics_and_visibility_do_not_publish_again(gate):
    metrics = {"contentW": 1280, "contentH": 800, "fontFloorBodyPx": 10}
    gate.setProperty("active", True)
    gate.setProperty("inputMetrics", metrics)
    gate.setProperty("inputMetrics", dict(metrics))
    gate.setProperty("active", False)
    gate.setProperty("active", True)
    assert gate.property("revision") == 1
    gate.setProperty("inputMetrics", {**metrics, "fontFloorBodyPx": 11})
    assert gate.property("revision") == 2


def test_active_null_input_clears_cached_metrics_and_allows_a_fresh_layout(gate):
    gate.setProperty("active", True)
    gate.setProperty("inputMetrics", {"contentW": 1920, "contentH": 1040})
    seen = []
    gate.snapshotChanged.connect(lambda: seen.append(snapshot(gate)))
    gate.setProperty("inputMetrics", None)
    assert snapshot(gate) is None
    assert seen == [None]
    assert gate.property("revision") == 2
    gate.setProperty("inputMetrics", {"contentW": 1100, "contentH": 760})
    assert snapshot(gate) == {"contentW": 1100, "contentH": 760}
    assert seen == [None, {"contentW": 1100, "contentH": 760}]
    assert gate.property("revision") == 3


def test_hidden_null_input_keeps_last_layout_until_reactivation(gate):
    previous = {"contentW": 1100, "contentH": 760}
    gate.setProperty("active", True)
    gate.setProperty("inputMetrics", previous)
    gate.setProperty("active", False)
    seen = []
    gate.snapshotChanged.connect(lambda: seen.append(snapshot(gate)))
    gate.setProperty("inputMetrics", None)
    assert snapshot(gate) == previous
    assert seen == []
    assert gate.property("revision") == 1
    gate.setProperty("active", True)
    assert snapshot(gate) is None
    assert seen == [None]
    assert gate.property("revision") == 2


def test_duplicate_null_input_and_visibility_do_not_publish_again(gate):
    gate.setProperty("active", True)
    gate.setProperty("inputMetrics", None)
    assert gate.property("revision") == 0
    gate.setProperty("inputMetrics", {"contentW": 1100, "contentH": 760})
    gate.setProperty("inputMetrics", None)
    assert gate.property("revision") == 2
    seen = []
    gate.snapshotChanged.connect(lambda: seen.append(snapshot(gate)))
    gate.setProperty("inputMetrics", None)
    gate.setProperty("active", False)
    gate.setProperty("active", True)
    assert snapshot(gate) is None
    assert gate.property("revision") == 2
    assert seen == []


@pytest.mark.parametrize("width,height,scale", [
    (480, 320, 100), (1600, 1000, 100), (1920, 1040, 225), (1100, 760, 125),
])
def test_restored_maximized_and_fractional_dpi_metrics_are_forwarded(gate, width, height, scale):
    metrics = {"contentW": width, "contentH": height, "scalePercent": scale,
               "monitorX": -1920, "monitorY": -1080}
    gate.setProperty("inputMetrics", metrics)
    gate.setProperty("active", True)
    assert snapshot(gate) == metrics


def test_irrelevant_hidden_updates_leave_visible_layout_revision_stable(gate):
    gate.setProperty("inputMetrics", {"contentW": 1100, "contentH": 760})
    assert gate.property("revision") == 0
    assert snapshot(gate) is None
    gate.setProperty("active", True)
    assert gate.property("revision") == 1
