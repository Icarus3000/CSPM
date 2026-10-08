from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from startup_input_classification_control import load_classifiers, run_control


def test_counterbalanced_actual_qt_tree_has_equal_calls_and_complete_event_delivery():
    result = run_control(child_count=63, samples=4)
    assert result["status"] == "PASS" and result["nodeCount"] == 64
    assert result["sampleOrders"] == [["source", "map-prototype"], ["map-prototype", "source"]] * 2
    assert len(result["sourceSha256"]) == 64
    assert [row["observedFilterCalls"] for row in result["variants"]] == [512,512]
    assert all(row["medianPairWallMs"] >= 0 and len(row["observations"]) == 4
               for row in result["variants"])


@pytest.mark.parametrize("variant", ["source", "map-prototype"])
def test_classifier_preserves_first_capture_and_every_later_callback_label(variant):
    from PySide6.QtCore import QCoreApplication, QEvent
    app = QCoreApplication.instance() or QCoreApplication([])
    now, calls = [10.0], []
    definitions, _ = load_classifiers(clock=lambda: now[0], callback=calls.append)
    definition = definitions[variant]
    probe = definition["class"](app)
    for index, kind in enumerate((QEvent.MouseButtonPress, QEvent.MouseButtonDblClick,
                                 QEvent.KeyPress, QEvent.TouchBegin, QEvent.Wheel, QEvent.KeyPress)):
        now[0] = 11.0 + index
        assert probe.eventFilter(None, QEvent(kind)) is False
    assert calls == ["mouse-press", "mouse-double-click", "key-press", "touch-begin", "wheel", "key-press"]
    assert definition["namespace"]["_startup_first_input_perf"] == 11.0
    assert definition["namespace"]["_startup_first_input_label"] == "mouse-press"
    assert probe._captured
    assert probe.eventFilter(None, QEvent(QEvent.WindowActivate)) is False
    assert probe.eventFilter(None, None) is False
    assert len(calls) == 6
    probe.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("argument,value", [("child_count",0), ("child_count",20001),
    ("samples",1), ("samples",3), ("samples",32), ("samples",True)])
def test_bad_config_rejects_before_importing_qt(argument, value):
    with pytest.raises(ValueError):
        run_control(**{argument:value})
