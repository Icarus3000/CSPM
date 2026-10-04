"""Stopped-clock corner/margin diagnosis contracts; no desktop or Qt runtime."""
import ctypes
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
import source_pixel_analysis as module


def controls():
    backdrop = np.full((40, 50, 4), [83, 61, 37, 255], dtype=np.uint8)
    live = backdrop.copy()
    live[4:36, 4:46] = [150, 140, 130, 255]
    regions = module.physical_regions([0, 0, 50, 40], [0, 0, 50, 40],
        [4, 4, 42, 32], header_height_px=7, border_px=0)
    return live, backdrop, regions


def test_coordinates_remain_in_measured_corner_or_margin_regions_with_bounded_coverage():
    live, _, regions = controls()
    overlap, native = live.copy(), live.copy()
    overlap[4, 4, 0] ^= 1
    native[12:25, 46:50, 1] ^= 1
    coordinates, labels, summaries = module.composition_probe_coordinates(live, overlap, native, regions, 6)
    assert 1 <= len(coordinates) <= 64
    assert len(set(coordinates)) == len(coordinates) == len(labels)
    assert summaries["cornerTL"]["differentPixels"] == 1
    assert summaries["cornerTL"]["sampledChangedPixels"] == 1
    assert summaries["clientMargin"]["differentPixels"] == 52
    assert summaries["clientMargin"]["unsampledChangedPixels"] == 28
    assert all(any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1
                   in summaries[label]["rectanglesLTRB"]) for (x, y), label in zip(coordinates, labels))
    assert (24, 24) not in coordinates


def test_matching_arrays_still_sample_corner_and_margin_controls_without_interior_content():
    live, _, regions = controls()
    coordinates, labels, summaries = module.composition_probe_coordinates(live, live, live, regions, 6)
    assert len(coordinates) == 40
    assert all(summary["differentPixels"] == 0 for summary in summaries.values())
    assert labels.count("clientMargin") == 8


def test_matching_clients_keep_radius_relative_fringe_samples_at_all_four_corners():
    live, _, regions = controls()
    coordinates, labels, summaries = module.composition_probe_coordinates(live, live, live, regions, 9)
    expected = [(0, 7), (7, 0), (2, 3), (3, 2)]
    for label in ("cornerTL", "cornerTR", "cornerBL", "cornerBR"):
        actual = {xy for xy, zone in zip(coordinates, labels) if zone == label}
        reflected = {(4+dx if label.endswith("L") else 45-dx,
            4+dy if label.startswith("cornerT") else 35-dy) for dx, dy in expected}
        assert reflected <= actual
        assert summaries[label]["differentPixels"] == 0
    assert len(coordinates) <= 64


@pytest.mark.parametrize("change", ["extent", "radius", "regions"])
def test_invalid_coordinate_selection_rejects_without_readback(change):
    live, _, regions = controls()
    with pytest.raises(ValueError):
        module.composition_probe_coordinates(live, live[:-1] if change == "extent" else live,
            live, {} if change == "regions" else regions, -1 if change == "radius" else 6)


def test_composition_math_distinguishes_single_and_double_partial_alpha_without_raw_samples():
    bg = np.array([83, 61, 37], dtype=np.float64)
    sample = np.array([[60, 50, 40, 128], [140, 130, 120, 255], [0, 0, 0, 0]], dtype=np.uint8)
    alpha = sample[:, 3:4]/255
    one = np.clip(np.rint(sample[:, :3]+(1-alpha)*bg), 0, 255).astype(np.uint8)
    two = np.clip(np.rint(sample[:, :3]+(1-alpha)*one), 0, 255).astype(np.uint8)
    def array(rgb):
        return np.concatenate([rgb[None], np.full((1, 3, 1), 255, np.uint8)], axis=2)
    result = module.composition_analysis(array(one), array(two), array(one),
        array(np.tile(bg.astype(np.uint8), (3, 1))), [(0, 0), (1, 0), (2, 0)],
        ["cornerTL"]*3, sample, sample.copy(), {"included": [True]*3})
    assert result["sourceSubmittedDifferentSamples"] == 0
    assert result["sourceAlphaHistogram"][128] == 1
    assert result["sourcePremultipliedViolations"] == 0
    for name in ("sourcePremultipliedOverBackdropToLive", "submittedPremultipliedOverBackdropToNative",
                 "submittedPremultipliedOverLiveToOverlap"):
        assert result["models"][name]["differentSamples"] == 0
    assert result["models"]["submittedStraightAlphaOverBackdropToNative"]["differentSamples"] == 1
    assert result["regions"]["cornerTL"]["liveOverlapDifferentSamples"] == 1
    encoded = json.dumps(result)
    assert "raw" in result["scope"]
    assert "coordinates" not in result and "samples" not in result
    assert "[60, 50, 40, 128]" not in encoded
    assert module.compare_pixels(array(one), array(two))["status"] == "FAIL"


def test_native_region_can_explain_a_live_clipped_pixel_without_altering_native_model():
    backdrop = np.full((1, 1, 4), [83, 61, 37, 255], np.uint8)
    native = np.full_like(backdrop, [140, 130, 120, 255])
    samples = np.array([[140, 130, 120, 255]], np.uint8)
    result = module.composition_analysis(backdrop, native, native, backdrop,
        [(0, 0)], ["cornerTL"], samples, samples, {"included": [False]})
    assert result["models"]["sourcePremultipliedOverBackdropToLive"]["differentSamples"] == 1
    assert result["models"]["sourcePremultipliedWithNativeRegionToLive"]["differentSamples"] == 0
    assert result["models"]["submittedPremultipliedOverBackdropToNative"]["differentSamples"] == 0


def test_source_submitted_byte_change_remains_a_separate_failed_identity():
    array = np.full((1, 1, 4), 255, np.uint8)
    source, submitted = np.full((1, 4), 255, np.uint8), np.full((1, 4), 255, np.uint8)
    submitted[0, 0] -= 1
    result = module.composition_analysis(array, array, array, array, [(0, 0)],
        ["clientMargin"], source, submitted)
    assert result["sourceSubmittedDifferentSamples"] == 1
    assert result["regions"]["clientMargin"]["sourceSubmittedDifferentSamples"] == 1


class FakeFunction:
    def __init__(self, callback):
        self.callback = callback
    def __call__(self, *args):
        return self.callback(*args)


def test_probe_adapter_owns_tiny_bgra_arrays_and_rejects_native_failure():
    calls = []
    buffers = []
    def native(host, coordinates, count, source, submitted):
        calls.append((host, list(coordinates), count))
        buffers.extend((source, submitted))
        for i in range(count*4):
            source[i], submitted[i] = i, i+1
        return 1
    dll = SimpleNamespace(cspm_comp_probe_pixels=FakeFunction(native))
    source, submitted = module.probe_gpu_composition(dll, 101, [(3, 4), (5, 6)])
    assert calls == [(101, [3, 4, 5, 6], 2)]
    buffers[0][0] = 99
    assert source[0, 0] == 0 and submitted[0, 0] == 1
    dll.cspm_comp_probe_pixels.callback = lambda *args: 0
    with pytest.raises(RuntimeError, match="rejected"):
        module.probe_gpu_composition(dll, 101, [(3, 4)])


@pytest.mark.parametrize("points", [[], [(0, 0)]*65, [(-1, 0)], [(0.5, 0)], [(True, 0)]])
def test_probe_rejects_invalid_coordinate_arguments_before_native_call(points):
    dll = SimpleNamespace(cspm_comp_probe_pixels=FakeFunction(lambda *args: pytest.fail("native called")))
    with pytest.raises(ValueError):
        module.probe_gpu_composition(dll, 101, points)


def test_region_membership_translates_client_origin_and_releases_only_owned_region(monkeypatch):
    calls = []
    gdi = SimpleNamespace(CreateRectRgn=FakeFunction(lambda *args: 902),
        PtInRegion=FakeFunction(lambda region, x, y: calls.append((region, x, y)) or x < 10),
        DeleteObject=FakeFunction(lambda region: calls.append(("release", region))))
    user = SimpleNamespace(GetWindowRgn=FakeFunction(lambda hwnd, region: 3))
    monkeypatch.setattr(module, "window_observation", lambda hwnd: {"clientOffsetInWindowXY": [2, 3]})
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kwargs: user if name == "user32" else gdi)
    result = module.window_region_membership(101, [(1, 2), (10, 20)])
    assert result["included"] == [True, False]
    assert calls == [(902, 3, 5), (902, 12, 23), ("release", 902)]


def test_backdrop_cleanup_destroys_only_its_owned_window_class_and_brush():
    calls = []
    backdrop = object.__new__(module.ControlledBackdrop)
    backdrop.hwnd, backdrop.registered, backdrop.brush = 101, True, 202
    backdrop.class_name, backdrop.instance = "owned", 303
    backdrop.user = SimpleNamespace(DestroyWindow=lambda hwnd: calls.append(("window", hwnd)) or 1,
        UnregisterClassW=lambda name, instance: calls.append(("class", name, instance)) or 1)
    backdrop.gdi = SimpleNamespace(DeleteObject=lambda brush: calls.append(("brush", brush)))
    backdrop.close()
    backdrop.close()
    assert calls == [("window", 101), ("class", "owned", 303), ("brush", 202)]
