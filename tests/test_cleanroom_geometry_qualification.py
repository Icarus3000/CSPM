"""Guard against diagnostic false passes when motion is paused or unmeasured."""
import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "scripts/diagnostics/cleanroom_transition_probe.py"
spec = importlib.util.spec_from_file_location("cleanroom_transition_probe", module_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def samples(progress):
    return [{"t": i / 60, "rect": [round(p * 1000), 0, 100, 100]} for i, p in enumerate(progress)]


def test_continuous_marker_geometry_has_scoped_pass():
    result = probe.analyze_geometry(samples([i / 30 for i in range(31)]), [0, 0, 100, 100], [1000, 0, 100, 100])
    assert result["status"] == "PASS"
    assert result["scope"] == "tested marker geometry only"
    assert len(result["jerk"]) == 28


def test_interior_pause_fails():
    values = [i / 30 for i in range(15)] + [.5] * 6 + [.5 + i / 30 for i in range(1, 16)]
    result = probe.analyze_geometry(samples(values), [0, 0, 100, 100], [1000, 0, 100, 100])
    assert result["status"] == "FAIL"
    assert any("stationary" in message for message in result["failures"])


def test_large_single_frame_jump_fails():
    values = [0, .03, .06, .1, .15, .2, .5, .55, .6, .7, .8, .9, 1]
    result = probe.analyze_geometry(samples(values), [0, 0, 100, 100], [1000, 0, 100, 100])
    assert result["status"] == "FAIL"
    assert any("22%" in message for message in result["failures"])


def test_missing_or_gapped_measurement_is_unmeasured():
    assert probe.analyze_geometry([], [0, 0, 100, 100], [1000, 0, 100, 100])["status"] == "UNMEASURED"
    rows = samples([i / 30 for i in range(31)])
    for row in rows[10:]:
        row["t"] += .1
    result = probe.analyze_geometry(rows, [0, 0, 100, 100], [1000, 0, 100, 100])
    assert result["status"] == "UNMEASURED"


def test_physical_failure_prevents_successful_process_result():
    failures = []
    result = probe.finalize_physical_geometry([{"status": "PASS"}, {"status": "FAIL"}], failures)
    assert result["status"] == "FAIL"
    assert failures == ["independent compositor marker geometry failed"]


def test_unmeasured_physical_samples_are_not_promoted_to_pass():
    for observations in ([], [{"status": "PASS"}, {"status": "UNMEASURED"}]):
        failures = ["earlier unrelated failure"]
        result = probe.finalize_physical_geometry(observations, failures)
        assert result["status"] == "UNMEASURED"
        assert failures == ["earlier unrelated failure"]


def test_all_measured_geometry_passes_preserve_narrow_scope():
    failures = []
    result = probe.finalize_physical_geometry([{"status": "PASS"}], failures)
    assert result["status"] == "PASS"
    assert "whole texture/luminance/sharpness handoff remains unmeasured" in result["scope"]
    assert failures == []
