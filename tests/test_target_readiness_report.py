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


def render_import_fixture(imported=True):
    source = fixture()
    source["events"][-1].update(targetImportStarted=1.421,
        targetImportFinished=1.43, targetImported=imported)
    source["configuration"]["render_target_import"] = True
    if imported:
        source["events"].append({"event": "target-gpu-composition-committed", "cycle": 0,
            "t": 1.501, "importThread": "render", "importStarted": 1.421, "importFinished": 1.43})
    else:
        source["events"][-1]["targetImportError"] = "Private Customer and C:/Private"
    return source


def test_render_import_critical_path_excludes_queued_gui_observation():
    cycle = report.summarize(render_import_fixture())["cycles"][0]
    assert cycle["chainTotalMs"] == 330
    assert cycle["nativeOwnedTargetPublishedMs"] == 330
    assert cycle["targetGuiArrivalMs"] == 400
    assert cycle["apiBoundaryChain"][-1]["durationMs"] == 9
    assert cycle["asynchronousGuiObservations"][0]["durationMs"] == 70
    assert all(row["stage"] != "queuedGuiDelivery" for row in cycle["apiBoundaryChain"])


def test_rejected_render_import_has_no_presentable_target_or_private_error():
    result = report.summarize(render_import_fixture(False))
    assert result["cycles"][0]["nativeOwnedTargetPublishedMs"] is None
    assert result["cycles"][0]["nativeImportStatus"] == "native import rejected"
    assert "Private" not in json.dumps(result)


@pytest.mark.parametrize("mutation", ["before_export", "after_delivery", "mismatched_event", "missing_finish", "wrong_thread"])
def test_inconsistent_render_import_is_rejected(mutation):
    source = render_import_fixture()
    target, event = source["events"][-2:]
    if mutation == "before_export":
        target["targetImportStarted"] = 1.4
    elif mutation == "after_delivery":
        target["targetImportFinished"] = 1.6
    elif mutation == "mismatched_event":
        event["importFinished"] = 1.432
    elif mutation == "missing_finish":
        del target["targetImportFinished"]
    else:
        event["importThread"] = "GUI"
    with pytest.raises(ValueError):
        report.summarize(source)


@pytest.mark.parametrize("client,size", [([0, 0, 10, 0], [10, 0]),
    ([0, 0, 10.5, 10], [10.5, 10]), ([0, 0, 10], [10]), ([0, 0, 10, 10], None)])
def test_malformed_physical_extent_is_rejected(client, size):
    source = fixture()
    source["events"][-1].update(client=client, size=size)
    with pytest.raises(ValueError):
        report.summarize(source)


def test_known_configuration_is_retained_without_private_values():
    source = fixture()
    source["configuration"].update(workspace="invoice-preview", first_direction="restore",
        restored_size=[760, 540], keep_visible=True, pixels=True)
    result = report.summarize(source)["configuration"]
    assert result["workspace"] == "invoice-preview"
    assert result["first_direction"] == "restore"
    assert result["restored_size"] == [760, 540]
    assert result["keep_visible"] is True
    source["configuration"].update(workspace=["Private Client"], first_direction="Private Client",
        restored_size=["C:/Private", 540], keep_visible="Private Client", duration_ms="Private Client")
    assert "Private" not in json.dumps(report.summarize(source))


def test_pixel_failures_and_submission_counts_do_not_certify_presentation():
    source = fixture()
    source["events"].extend([
        {"event": "source-live-to-gpu-pixels", "cycle": 0, "t": 1.51, "status": "FAIL", "differentPixels": 48, "private": "Private Client"},
        {"event": "native-endpoint-submitted", "cycle": 0, "t": 1.52, "presentation": {"submitted": 18, "displayed": 15, "private": "Private Client"}},
        {"event": "live-handoff", "cycle": 0, "t": 1.6},
    ])
    cycle = report.summarize(source)["cycles"][0]
    assert cycle["pixelObservations"] == [{"comparison": "source-live-to-gpu-pixels", "status": "FAIL", "differentPixels": 48}]
    assert cycle["submissionObservations"][0]["displayed"] == 15
    assert all(row["physicalPresentationEstablished"] is False for row in cycle["submissionObservations"])
    assert "Private" not in json.dumps(cycle)


def test_render_notification_deferral_and_unknown_costs_are_explicit():
    cycle = report.summarize(render_import_fixture())["cycles"][0]
    observation = cycle["asynchronousGuiObservations"][0]
    assert observation["requiredForFirstTarget"] is False
    assert observation["safelyDeferrable"] is True
    assert cycle["apiBoundaryChain"][1]["safelyDeferrable"] is None
    assert cycle["apiBoundaryChain"][1]["unnecessarilyRepeated"] is None


def test_fanout_only_exports_recognized_instrumentation_labels():
    source = fixture()
    source["fanoutCounts"] = [{"cycle": 0, "counts": {
        "before:metricsPublication:Shell.uiMetricsCompute:visible": {"count": 1, "helperMs": 2},
        "Private Customer/C:/Private": {"count": 200, "helperMs": 100},
    }}]
    result = report.summarize(source)
    assert len(result["fanoutObservations"][0]["helpers"]) == 1
    assert "Private" not in json.dumps(result)
