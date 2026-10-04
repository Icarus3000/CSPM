"""Pure JSON timing/report contracts; no GUI, Qt or private data."""
import importlib.util
import json
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "scripts/diagnostics/target_readiness_report.py"
SPEC = importlib.util.spec_from_file_location("target_readiness_report", PATH)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def fixture():
    return {"events": [
        {"event": "command", "cycle": 0, "t": 1.0, "kind": "maximize"},
        {"event": "native-clock-start", "cycle": 0, "t": 1.1},
        {"event": "layout-begin", "cycle": 0, "t": 1.11},
        {"event": "layout-committed", "cycle": 0, "t": 1.2},
        {"event": "gpu-capture", "kind": "target", "cycle": 0, "t": 1.5,
         "requested": 1.21, "renderCallback": 1.4, "captureFinished": 1.42,
         "client": [0, 0, 1920, 1040], "size": [1920, 1040], "frame": 938438},
    ], "completedCycles": 0, "failures": ["Private Name and path C:/Private"],
       "configuration": {"audit_label": "Private", "layout_repair": True}}


def test_api_chain_is_additive_and_relative_to_both_clocks():
    cycle = report.summarize(fixture())["cycles"][0]
    assert cycle["chainTotalMs"] == 400
    assert cycle["targetGuiArrivalMs"] == 400
    assert cycle["apiBoundaryChain"][1]["durationMs"] == 90
    assert cycle["apiBoundaryChain"][1]["startAfterCommandMs"] == 110
    assert cycle["apiBoundaryChain"][1]["startAfterClockMs"] == 10


def test_report_does_not_export_private_errors_paths_pointers_or_absolute_clocks():
    source = fixture()
    source["qtStageTimings"] = [
        {"cycle": 0, "t": 1.3, "category": "qt.scenegraph.time.renderloop", "message": "[window 0x1234][render thread 0xbeef] syncAndRender: start, elapsed since last call: 17 ms"},
        {"cycle": 0, "t": 1.4, "category": "qt.scenegraph.time.renderloop", "message": "[window 0x1234][render thread 0xbeef] syncAndRender: frame rendered in 100ms, sync=20, render=70, swap=10"},
    ]
    text = json.dumps(report.summarize(source))
    for secret in ("Private", "C:/Private", "0x1234", "0xbeef", "938438", '"t":'):
        assert secret not in text
    assert "syncCompositeMs" in text


def test_nested_polish_uses_own_cost_and_repeated_call_counts():
    rows = [
        {"cycle": 0, "t": 1.0, "message": "updatePolish() ENTERING QQuickRowLayout(0x111, parent=0x222)"},
        {"cycle": 0, "t": 1.01, "message": "updatePolish() ENTERING QQuickColumnLayout(0x222, parent=0x111)"},
        {"cycle": 0, "t": 1.03, "message": "updatePolish() LEAVING QQuickColumnLayout(0x222, parent=0x111)"},
        {"cycle": 0, "t": 1.1, "message": "updatePolish() LEAVING QQuickRowLayout(0x111, parent=0x222)"},
        {"cycle": 0, "t": 1.11, "message": "updatePolish() ENTERING QQuickRowLayout(0x111, parent=0x222)"},
        {"cycle": 0, "t": 1.12, "message": "updatePolish() LEAVING QQuickRowLayout(0x111, parent=0x222)"},
    ]
    result = report.layout_summary(rows, {"0x111": {"visible": False, "ancestors": [{"class": "HomeGrid_QMLTYPE_44", "id": "home"}]}}, 1, 1)
    assert result["pairedCalls"] == 3
    assert result["distinctObjects"] == 2
    assert result["repeatedObjectCalls"] == 1
    assert result["observedOwnTotalMs"] == 110
    assert result["groups"][0]["inclusiveMs"] == 110
    assert result["groups"][0]["ownMs"] == 90
    assert result["groups"][0]["visibleAtInitialMetadataCollection"] is False


@pytest.mark.parametrize("change", ["callback_before_request", "different_extent", "duplicate_capture", "different_cycle", "nan", "reversed_geometry"])
def test_inconsistent_capture_is_rejected(change):
    source = fixture()
    capture = source["events"][-1]
    if change == "callback_before_request":
        capture["renderCallback"] = 1.19
    elif change == "different_extent":
        capture["size"] = [100, 100]
    elif change == "duplicate_capture":
        source["events"].append(dict(capture))
    elif change == "different_cycle":
        capture["cycle"] = 1
    elif change == "nan":
        capture["captureFinished"] = float("nan")
    else:
        source["events"][3]["t"] = 1.09
    with pytest.raises(ValueError):
        report.summarize(source)


def test_uncaptured_qt_frame_boundary_does_not_invent_a_frame():
    source = fixture()
    source["qtStageTimings"] = [{"cycle": 0, "t": 1.2,
        "category": "qt.scenegraph.time.renderloop",
        "message": "[window 0x1234][render thread 0xbeef] syncAndRender: frame rendered in 100ms, sync=20, render=70, swap=10"}]
    result = report.summarize(source)["cycles"][0]["qt"]
    assert result["frames"] == []
    assert result["unpairedBoundaryCounts"] == {"renderSummary": 1}


def test_crossing_polish_boundaries_are_rejected():
    rows = [{"cycle": 0, "t": 1, "message": "updatePolish() ENTERING QQuickRowLayout(0x111)"},
            {"cycle": 0, "t": 2, "message": "updatePolish() LEAVING QQuickRowLayout(0x222)"}]
    with pytest.raises(ValueError):
        report.layout_summary(rows, {}, 0, 0)


def test_layout_only_clock_and_final_cleanup_are_supported():
    source = fixture()
    source["events"][1]["event"] = "layout-profile-start"
    source["events"].append({"event": "spike-finished", "cycle": 1, "t": 2})
    assert report.summarize(source)["cycles"][0]["clock"] == "layout isolation"


def test_prepared_target_arrives_before_native_clock_without_claiming_cold_speed():
    source = fixture()
    source["events"][1]["t"] = 1.6
    source["configuration"]["prepared_target"] = True
    result = report.summarize(source)
    assert result["cycles"][0]["targetGuiArrivalMs"] == -100
    assert result["configuration"]["prepared_target"] is True


def test_duplicate_statement_boundary_is_rejected():
    source = fixture()
    source["profileBoundaries"] = [{"cycle": 0, "t": 1.15, "boundary": "before:finalW"}] * 2
    with pytest.raises(ValueError):
        report.summarize(source)
