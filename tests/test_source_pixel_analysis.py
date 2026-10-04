"""Array/acquisition diagnosis contracts; no Qt, WebEngine or GPU windows."""
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/diagnostics"))
from source_pixel_analysis import array_summary, compare_pixels, grab_observed, physical_regions


def test_exact_arrays_have_empty_bounds_and_histograms_and_unchanged_identity():
    pixels = np.random.default_rng(9).integers(0, 256, (31, 29, 4), dtype=np.uint8)
    saved = pixels.copy()
    result = compare_pixels(pixels, pixels.copy())
    assert result["status"] == "PASS"
    assert result["differentPixels"] == result["rgbDifferentPixels"] == 0
    assert result["mismatchBoundsLTRB"] is None
    assert not any(result["rowMismatchHistogram"] + result["columnMismatchHistogram"])
    assert result["before"]["sha256"] == result["after"]["sha256"]
    np.testing.assert_array_equal(pixels, saved)


def test_spatial_and_named_region_counts_preserve_an_alpha_only_failure():
    before = np.full((18, 21, 4), 255, dtype=np.uint8)
    after = before.copy()
    after[4:7, 8:13, 3] = 0
    result = compare_pixels(before, after, regions={"header": [0, 0, 21, 4], "body": [0, 4, 21, 18]})
    assert result["status"] == "FAIL"
    assert result["differentPixels"] == result["alphaDifferentPixels"] == 15
    assert result["pixels"] == 378
    assert result["differencePercent"] == 100 * 15 / 378
    assert result["rgbDifferentPixels"] == 0
    assert result["mismatchBoundsLTRB"] == [8, 4, 13, 7]
    assert result["rowMismatchHistogram"][4:7] == [5, 5, 5]
    assert result["columnMismatchHistogram"][8:13] == [3] * 5
    assert result["regions"]["header"]["differentPixels"] == 0
    assert result["regions"]["body"]["differentPixels"] == 15
    assert result["regions"]["body"]["differencePercent"] == 100 * 15 / (14 * 21)
    assert result["luminance"]["differentPixels"] == 0


def test_border_region_unions_do_not_double_count_corners():
    before = np.zeros((10, 10, 3), dtype=np.uint8)
    after = np.ones_like(before)
    result = compare_pixels(before, after, regions={"border": [
        [0, 0, 10, 1], [0, 9, 10, 10], [0, 0, 1, 10], [9, 0, 10, 10]]})
    assert result["regions"]["border"]["pixels"] == 36
    assert result["regions"]["border"]["differentPixels"] == 36


def test_observed_physical_regions_partition_crop_once_including_negative_origin():
    # Outer capture 16x14, client 14x12, content 10x8, one physical border.
    regions = physical_regions([-105, 39, 16, 14], [-104, 40, 14, 12],
        [-102, 42, 10, 8], header_height_px=3, border_px=1)
    before = np.zeros((14, 16, 4), dtype=np.uint8)
    after = np.ones_like(before)
    result = compare_pixels(before, after, regions=regions)
    counts = {name: stats["pixels"] for name, stats in result["regions"].items()}
    assert counts == {"header": 16, "clientBody": 32, "border": 32,
                      "shadowAndMargin": 88, "outsideClient": 56}
    assert sum(counts.values()) == 224
    assert all(stats["pixels"] == stats["differentPixels"] for stats in result["regions"].values())


def test_client_only_crop_has_no_outside_pixels_or_uninvented_shadow_counts():
    regions = physical_regions([100, 200, 20, 15], [100, 200, 20, 15],
        [100, 200, 20, 15], header_height_px=4, border_px=0)
    assert regions["outsideClient"] == regions["shadowAndMargin"] == regions["border"] == []
    result = compare_pixels(np.zeros((15, 20, 3), dtype=np.uint8),
        np.ones((15, 20, 3), dtype=np.uint8), regions=regions)
    assert result["regions"]["header"]["pixels"] == 80
    assert result["regions"]["clientBody"]["pixels"] == 220


def test_offset_search_explains_translation_without_turning_failure_into_pass():
    before = np.random.default_rng(11).integers(1, 250, (34, 39, 4), dtype=np.uint8)
    after = np.zeros_like(before)
    after[1:, 2:] = before[:-1, :-2]
    result = compare_pixels(before, after, stale_frames={"previous": after.copy()})
    assert result["status"] == "FAIL"
    assert result["constantOffsetSearch"]["newSampleOffsetXY"] == [2, 1]
    assert result["constantOffsetSearch"]["overlap"]["differentPixels"] == 0
    assert result["staleFrameComparisons"]["previous"]["differentPixels"] == 0
    assert result["differentPixels"] > 1000


def test_centered_scale_probe_separates_rescaling_from_exact_identity():
    before = np.zeros((41, 41, 3), dtype=np.uint8)
    after = before.copy()
    before[22, 22] = 255
    after[24, 24] = 255
    result = compare_pixels(before, after, scales=(1.0, 2.0))
    scores = result["scaleSearch"]["candidates"]
    assert scores[0]["differentPixels"] == 2
    assert scores[1]["differentPixels"] == 0
    assert result["status"] == "FAIL"


def test_luminance_and_geometry_do_not_hide_constant_brightness_change():
    before = np.full((25, 25, 3), 80, dtype=np.uint8)
    after = np.full_like(before, 90)
    result = compare_pixels(before, after)
    assert result["status"] == "FAIL"
    assert result["luminance"]["meanSignedDifference"] == 10
    assert result["colorDifference"]["neutralBrightnessShiftPixels"] == 625
    assert result["colorDifference"]["chromaticChangePixels"] == 0
    assert result["geometryEdges"]["differentEdgePixels"] == 0


def test_extent_mismatch_is_failed_before_search_and_no_image_arrays_escape():
    result = compare_pixels(np.zeros((3, 3, 4), dtype=np.uint8), np.zeros((4, 3, 4), dtype=np.uint8))
    assert result["status"] == "FAIL"
    assert "constantOffsetSearch" not in result
    import json
    json.dumps(result)


@pytest.mark.parametrize("bad", [np.zeros((3, 3), dtype=np.uint8), np.zeros((3, 3, 4)), np.zeros((0, 2, 4), dtype=np.uint8)])
def test_invalid_pixel_inputs_do_not_qualify(bad):
    with pytest.raises(ValueError):
        array_summary(bad)


def test_combined_dxcam_timestamp_cannot_prove_a_desktop_raster_update():
    backing = np.ones((3, 4, 4), dtype=np.uint8)
    calls = []
    def grab(**kwargs):
        calls.append(kwargs)
        return backing
    camera = SimpleNamespace(grab=grab, width=1920, height=1080,
        latest_frame_ticks=999,
        _duplicator=SimpleNamespace(latest_frame_ticks=456, performance_frequency=1000, accumulated_frames=2))
    pixels, observation = grab_observed(camera, [10, 20, 4, 3])
    assert calls == [{"region": (10, 20, 14, 23), "copy": True, "new_frame_only": True}]
    backing[:] = 0
    assert pixels.all()
    assert observation["acquisitionFrameQpcTicks"] == 456
    assert observation["desktopFrameQpcTicks"] is None
    assert observation["desktopFrameSeconds"] is None
    assert observation["desktopPixelsUpdated"] is None
    assert observation["timestampEvidence"] == "unavailable"
    assert observation["cacheFallbackAllowed"] is False


def test_no_new_desktop_frame_is_unmeasured_never_a_cached_success():
    camera = SimpleNamespace(grab=lambda **kwargs: None)
    pixels, observation = grab_observed(camera, [0, 0, 4, 3])
    assert pixels is None
    assert observation["freshAcquisition"] is False


def test_negative_monitor_desktop_crop_is_translated_to_local_output_coordinates():
    calls = []
    camera = SimpleNamespace(grab=lambda **kwargs: calls.append(kwargs), width=1920, height=1080,
        _output=SimpleNamespace(desc=SimpleNamespace(DesktopCoordinates=SimpleNamespace(left=-1920, top=100))))
    _, observed = grab_observed(camera, [-1800, 220, 100, 80])
    assert calls[0]["region"] == (120, 120, 220, 200)
    assert observed["outputDesktopXYWH"] == [-1920, 100, 1920, 1080]
    assert observed["rectangleXYWH"] == [-1800, 220, 100, 80]
    with pytest.raises(ValueError, match="selected DXGI output"):
        grab_observed(camera, [-5, 220, 100, 80])


def test_invalid_regions_and_search_options_reject_before_platform_acquisition():
    pixels = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="region"):
        compare_pixels(pixels, pixels, regions={"bad": [0, 0, 11, 10]})
    with pytest.raises(ValueError, match="radius"):
        compare_pixels(pixels, pixels, offset_radius=-1)
    with pytest.raises(ValueError, match="Scale"):
        compare_pixels(pixels, pixels, scales=(float("nan"),))
    with pytest.raises(ValueError, match="extent"):
        grab_observed(None, [0, 0, 0, 10])


def _observed_fake_camera(deliveries):
    """Model COM's supported frame-info pointer without loading DXGI or Windows."""
    class DuplicateOutput:
        def AcquireNextFrame(self, timeout, frame_info, resource):
            del timeout, resource
            if not deliveries:
                raise TimeoutError("No newly delivered desktop/pointer frame")
            present, mouse = deliveries.pop(0)
            frame_info._obj.LastPresentTime = present
            frame_info._obj.LastMouseUpdateTime = mouse
            frame_info._obj.AccumulatedFrames = 1
        def ReleaseFrame(self):
            return "released"
    duplicator = SimpleNamespace(duplicator=DuplicateOutput(), latest_frame_ticks=0,
        performance_frequency=1000, accumulated_frames=1)
    def grab(**kwargs):
        del kwargs
        info = SimpleNamespace(LastPresentTime=0, LastMouseUpdateTime=0, AccumulatedFrames=0)
        try:
            duplicator.duplicator.AcquireNextFrame(0, SimpleNamespace(_obj=info), None)
        except TimeoutError:
            return None
        duplicator.latest_frame_ticks = info.LastPresentTime or info.LastMouseUpdateTime
        return np.ones((3, 4, 4), dtype=np.uint8)
    return SimpleNamespace(grab=grab, _duplicator=duplicator, width=1920, height=1080)


def test_successful_identical_deliveries_have_distinct_generations_and_raster_times():
    camera = _observed_fake_camera([(100, 0), (200, 0)])
    first, evidence_one = grab_observed(camera, [10, 20, 4, 3])
    second, evidence_two = grab_observed(camera, [10, 20, 4, 3])
    np.testing.assert_array_equal(first, second)
    assert evidence_one["acquisitionSequence"] == 1
    assert evidence_two["acquisitionSequence"] == 2
    assert evidence_two["desktopFrameSeconds"] == .2
    assert evidence_two["desktopPixelsUpdated"] is True
    assert evidence_two["pointerOnlyFrame"] is False
    assert camera._duplicator.duplicator.ReleaseFrame() == "released"


def test_pointer_only_acquisition_never_claims_new_desktop_raster_or_returns_old_metadata():
    camera = _observed_fake_camera([(100, 0), (0, 200)])
    _, first = grab_observed(camera, [10, 20, 4, 3])
    _, pointer = grab_observed(camera, [10, 20, 4, 3])
    assert pointer["freshAcquisition"] is True
    assert pointer["desktopPixelsUpdated"] is False
    assert pointer["pointerOnlyFrame"] is True
    assert pointer["desktopFrameSeconds"] is None
    assert pointer["lastMouseUpdateQpcTicks"] == 200
    pixels, missing = grab_observed(camera, [10, 20, 4, 3])
    assert pixels is None
    assert missing["freshAcquisition"] is False
    assert missing["newDeliveryObserved"] is False
    assert missing["acquisitionSequence"] == pointer["acquisitionSequence"] == 2
    assert missing["desktopFrameQpcTicks"] is None


def test_ring_buffer_mode_is_rejected_before_returning_cached_frames():
    with pytest.raises(ValueError, match="ring-buffer"):
        grab_observed(SimpleNamespace(is_capturing=True), [0, 0, 4, 3])


def test_acquired_wrong_extent_cannot_be_used_for_a_physical_comparison():
    with pytest.raises(ValueError, match="extent"):
        grab_observed(SimpleNamespace(grab=lambda **kwargs: np.zeros((1, 1, 4), np.uint8)), [0, 0, 4, 3])


@pytest.mark.parametrize("rectangle", [(0.2, 0, 4, 3), (0, 0, 4.9, 3), (0, 0, float("inf"), 3)])
def test_fractional_or_nonfinite_physical_rectangle_is_not_silently_truncated(rectangle):
    with pytest.raises(ValueError, match="integral"):
        grab_observed(None, rectangle)


def test_chromatic_change_at_equal_encoded_luminance_is_distinguished_from_brightness():
    before = np.full((4, 6, 3), 80, dtype=np.uint8)
    after = before.copy()
    after[:, :, 0] += 3  # BGR weights 18/183/54: 3*18 - 1*54 == 0.
    after[:, :, 2] -= 1
    result = compare_pixels(before, after)
    assert result["status"] == "FAIL"
    assert result["luminance"]["differentPixels"] == 0
    assert result["colorDifference"]["neutralBrightnessShiftPixels"] == 0
    assert result["colorDifference"]["equalEncodedLuminanceChangedColorPixels"] == 24


def test_srgb_transfer_hypothesis_explains_brightness_without_qualifying_pixels():
    before = np.arange(256, dtype=np.uint8).reshape(16, 16, 1).repeat(3, axis=2)
    values = before.astype(np.float64) / 255
    after = np.rint(np.where(values <= .04045, values / 12.92,
        ((values + .055) / 1.055) ** 2.4) * 255).astype(np.uint8)
    result = compare_pixels(before, after)
    assert result["status"] == "FAIL"
    assert result["colorSpaceHypotheses"]["beforeSRGBDecodedToLinear"]["differentPixels"] == 0
    assert result["colorSpaceHypotheses"]["beforeLinearEncodedToSRGB"]["differentPixels"] > 0


def test_contrast_change_can_reduce_sharpness_proxy_without_changing_edge_occupancy():
    before = np.tile(np.array([20, 180], dtype=np.uint8), 5)[None, :, None].repeat(3, axis=2)
    after = np.tile(np.array([70, 130], dtype=np.uint8), 5)[None, :, None].repeat(3, axis=2)
    result = compare_pixels(before, after)
    assert result["geometryEdges"]["differentEdgePixels"] == 0
    assert result["sharpnessProxy"]["before"]["meanHorizontalNeighborDifference"] == 160
    assert result["sharpnessProxy"]["after"]["meanHorizontalNeighborDifference"] == 60
    assert result["sharpnessProxy"]["after"]["meanVerticalNeighborDifference"] == 0
    assert result["status"] == "FAIL"
