"""Desktop evidence contracts with synthetic metadata only; no Qt/GPU/desktop."""
import ctypes
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/diagnostics/native_presentation_observer.py"
SPEC = importlib.util.spec_from_file_location("native_presentation_observer_tests", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DesktopFrameObserver = MODULE.DesktopFrameObserver
FreshPresentationGate = MODULE.FreshPresentationGate
RECTANGLE = [-80, 120, 300, 200]
STATE = {"live": {"visible": False, "clientXYWH": RECTANGLE},
         "transition": {"visible": True}, "native": {"sequence": 4, "submittedPresentId": 7}}


class Pixels:
    shape = (200, 300, 4)


def metadata(sequence=1, ticks=10150, **changes):
    return {"callStarted": 10.10, "callFinished": 10.20,
            "rectangleXYWH": list(RECTANGLE), "freshAcquisition": True,
            "cacheFallbackAllowed": False, "acquisitionSequence": sequence,
            "acquisitionSessionGeneration": 1, "newDeliveryObserved": True,
            "desktopFrameQpcTicks": ticks, "qpcFrequency": 1000,
            "desktopPixelsUpdated": True, **changes}


def gate(observer=None, **changes):
    return FreshPresentationGate(observer or DesktopFrameObserver(now=9.0), RECTANGLE, 10.0,
        now=10.05, expected_state={"live.visible": False, "transition.visible": True,
            "live.clientXYWH": RECTANGLE, "native.sequence": 4},
        minimum_state={"native.submittedPresentId": 7}, **changes)


def poll(value, frame_metadata=None, *, pixels=None, **changes):
    return value.poll(Pixels() if pixels is None else pixels,
                      metadata() if frame_metadata is None else frame_metadata,
                      state_before=STATE, state_after=STATE, now=10.25, **changes)


def test_new_delivery_of_identical_content_is_fresh_and_can_qualify():
    observer = DesktopFrameObserver(now=9)
    observer.observe(Pixels(), metadata(ticks=9900), content_revision="identical-content")
    value = gate(observer)
    pixels, evidence = poll(value, metadata(sequence=2), content_revision="identical-content")
    assert pixels is not None and evidence["status"] == "PASS"
    assert evidence["frame"]["contentDelivery"] == "new delivery containing unchanged pixels"
    assert evidence["frame"]["observerGeneration"] == 2
    assert observer.last_comparison_generation == 2
    assert evidence["frame"]["desktopFrameSeconds"] == 10.15


def test_new_changed_delivery_and_unchanged_delivery_have_separate_content_classifications():
    observer = DesktopFrameObserver(now=9)
    first = observer.observe(Pixels(), metadata(), content_revision="one")
    second = observer.observe(Pixels(), metadata(sequence=2, ticks=10200), content_revision="two")
    assert first["contentDelivery"] == "first content revision"
    assert second["contentDelivery"] == "new delivery containing changed pixels"
    assert second["usableDesktopDelivery"] is True


@pytest.mark.parametrize("changes,reason", [
    ({"freshAcquisition": False}, "stale cached frame"),
    ({"cacheFallbackAllowed": True}, "stale cached frame"),
    ({"newDeliveryObserved": False}, "successful native acquisition unproved"),
    ({"acquisitionSessionGeneration": None}, "capture session unavailable"),
    ({"acquisitionSequence": None}, "delivery sequence unavailable"),
    ({"desktopPixelsUpdated": False, "desktopFrameQpcTicks": 0}, "pointer-only or unproved raster delivery"),
    ({"desktopFrameQpcTicks": None}, "desktop presentation timestamp unavailable"),
    ({"qpcFrequency": None}, "desktop presentation timestamp unavailable"),
    ({"desktopFrameQpcTicks": 10000}, "desktop frame precedes presentation lower bound"),
    ({"rectangleXYWH": [0, 120, 300, 200]}, "wrong sampled physical rectangle"),
    ({"callStarted": 10.01}, "acquisition timestamps outside observation attempt"),
    ({"callFinished": 10.30}, "acquisition timestamps outside observation attempt"),
    ({"desktopFrameQpcTicks": 10201}, "desktop presentation timestamp follows acquisition return"),
])
def test_unproved_delivery_or_wrong_frame_never_reaches_comparison(changes, reason):
    pixels, evidence = poll(gate(), metadata(**changes))
    assert pixels is None and evidence["status"] == "PENDING"
    assert evidence["reason"] == reason


def test_repeated_acquisition_and_repeated_raster_timestamp_are_rejected_independently():
    observer = DesktopFrameObserver(now=9)
    assert observer.observe(Pixels(), metadata())["usableDesktopDelivery"]
    repeated = observer.observe(Pixels(), metadata())
    assert repeated["delivery"] == "stale cached frame"
    assert repeated["observerGeneration"] == 1
    duplicate_ticks = observer.observe(Pixels(), metadata(sequence=2))
    assert duplicate_ticks["delivery"] == "stale desktop presentation timestamp"
    assert duplicate_ticks["observerGeneration"] == 2


def test_pointer_only_delivery_does_not_consume_a_future_raster_timestamp():
    observer = DesktopFrameObserver(now=9)
    observer.observe(Pixels(), metadata(sequence=1, desktopPixelsUpdated=False))
    valid = observer.observe(Pixels(), metadata(sequence=2))
    assert valid["usableDesktopDelivery"] is True
    assert valid["observerGeneration"] == 2


def test_camera_session_recreation_cannot_reuse_sequence_for_same_gate():
    observer = DesktopFrameObserver(now=9)
    observer.observe(Pixels(), metadata())
    value = gate(observer)
    pixels, evidence = poll(value, metadata(sequence=200, acquisitionSessionGeneration=2))
    assert pixels is None and evidence["reason"] == "capture session changed"
    assert observer.generation == 1


def test_changed_camera_session_requires_explicit_new_observer():
    observer = DesktopFrameObserver(now=9)
    pixels, evidence = poll(gate(observer), metadata(acquisitionSessionGeneration=2))
    assert pixels is not None and evidence["status"] == "PASS"
    assert observer.acquisition_session_generation == 2


def test_stale_cache_times_out_and_terminal_poll_cannot_return_pixels_again():
    value = gate(timeout_ms=250)
    pixels, evidence = value.poll(Pixels(), metadata(freshAcquisition=False),
        state_before=STATE, state_after=STATE, now=10.30)
    assert pixels is None and evidence["status"] == "FAIL"
    assert evidence["reason"] == "stale cached frame"
    repeated_pixels, repeated = value.poll(Pixels(), metadata(sequence=2),
        state_before=STATE, state_after=STATE, now=11)
    assert repeated_pixels is None and repeated == evidence
    assert value.observer.generation == 0


def test_static_desktop_without_new_acquisition_terminates_with_explicit_reason():
    value = gate(timeout_ms=250)
    pixels, evidence = value.poll(None, metadata(freshAcquisition=False),
        state_before=STATE, state_after=STATE, now=10.30)
    assert pixels is None and evidence["status"] == "FAIL"
    assert evidence["reason"] == "no new observable frame"


def test_correct_raster_arriving_at_timeout_does_not_manufacture_a_pass():
    pixels, evidence = poll(gate(timeout_ms=200))
    assert pixels is None and evidence["status"] == "FAIL"
    assert evidence["reason"] == "fresh desktop frame arrived after bounded timeout"


@pytest.mark.parametrize("which", ["before", "after"])
def test_correct_frame_requires_window_state_on_both_sides_of_acquisition(which):
    wrong = {**STATE, "transition": {"visible": False}}
    value = gate()
    pixels, evidence = value.poll(Pixels(), metadata(),
        state_before=wrong if which == "before" else STATE,
        state_after=wrong if which == "after" else STATE, now=10.25)
    assert pixels is None and evidence["reason"] == "wrong visible state"
    assert evidence["stateMismatches" + which.capitalize()][0]["path"] == "transition.visible"


@pytest.mark.parametrize("native", [{"sequence": 3, "submittedPresentId": 7},
                                   {"sequence": 4, "submittedPresentId": 6}, {}])
def test_wrong_transition_generation_or_presentation_revision_never_qualifies(native):
    wrong = {**STATE, "native": native}
    pixels, evidence = gate().poll(Pixels(), metadata(),
        state_before=wrong, state_after=wrong, now=10.25)
    assert pixels is None and evidence["reason"] == "wrong visible state"


@pytest.mark.parametrize("witness", [None, {}, {"generation": 3, "revision": "source"}])
def test_required_visual_witness_cannot_be_inferred_from_timestamps_or_native_state(witness):
    value = gate(expected_witness={"generation": 4, "revision": "source"})
    pixels, evidence = poll(value, metadata(visualWitness=witness))
    assert pixels is None
    assert evidence["reason"] == "intended presentation visual witness unavailable"


def test_fresh_sample_with_matching_visual_witness_and_window_state_can_qualify():
    value = gate(expected_witness={"generation": 4, "revision": "source"})
    pixels, evidence = poll(value, metadata(visualWitness={"generation": 4, "revision": "source"}))
    assert pixels is not None and evidence["status"] == "PASS"


def test_successful_frame_generation_cannot_be_reused_in_later_comparison():
    observer = DesktopFrameObserver(now=9)
    pixels, first = poll(gate(observer))
    assert pixels is not None and first["status"] == "PASS"
    pixels, second = poll(gate(observer))
    assert pixels is None and second["reason"] == "stale cached frame"
    assert observer.last_comparison_generation == 1


def test_evidence_retains_owned_metadata_when_caller_mutates_state():
    state = {**STATE, "transition": {"visible": True}}
    value = gate()
    _, evidence = value.poll(Pixels(), metadata(), state_before=state, state_after=state, now=10.25)
    state["transition"]["visible"] = False
    evidence["stateBefore"]["transition"]["visible"] = False
    _, repeated = value.poll(None, {}, state_before={}, state_after={}, now=20)
    assert repeated["stateBefore"]["transition"]["visible"] is True


def test_gate_rejects_clock_reversal_after_pending_poll():
    value = gate()
    poll(value, metadata(freshAcquisition=False))
    with pytest.raises(ValueError, match="advancing finite"):
        value.poll(None, {}, state_before=STATE, state_after=STATE, now=10.24)


@pytest.mark.parametrize("change", [
    {"after_seconds": 8}, {"timeout_ms": 0}, {"timeout_ms": float("inf")},
    {"rectangle": [0, 0, 300, 0]}, {"rectangle": [0, 0, 300.5, 200]},
    {"expected_state": {}}, {"expected_witness": {}},
    {"minimum_state": {"native.sequence": None}},
])
def test_invalid_gate_inputs_fail_before_any_acquisition(change):
    arguments = {"observer": DesktopFrameObserver(now=9), "rectangle": RECTANGLE,
        "after_seconds": 10.0, "now": 10.05, "expected_state": {"live.visible": False}, **change}
    with pytest.raises(ValueError):
        FreshPresentationGate(**arguments)


def test_native_observation_rejects_changed_returned_abi_instead_of_describing_it_as_evidence():
    class DLL:
        def cspm_comp_observation(self, host, pointer, size):
            ctypes.cast(pointer, ctypes.POINTER(MODULE.NativeObservation)).contents.version = 2
            return 1
    with pytest.raises(RuntimeError, match="incompatible version/size"):
        MODULE.native_observation(DLL(), 1)


def test_native_present_history_rejects_impossible_counts_without_native_runtime():
    class DLL:
        def cspm_comp_present_trace(self, host, pointer, size):
            value = ctypes.cast(pointer, ctypes.POINTER(MODULE.NativePresentTrace)).contents
            value.count, value.totalFrames = 2, 1
            return 1
    with pytest.raises(RuntimeError, match="count is invalid"):
        MODULE.native_present_trace(DLL(), 1)


@pytest.mark.parametrize("kind", ["unchanged-raster", "pointer-only", "cached"])
def test_actual_grab_metadata_pipeline_distinguishes_equal_content_delivery_from_cache(monkeypatch, kind):
    """Run the real metadata adapter and gate together with a fake COM producer.

    Equal image bytes do not decide freshness. Only the supported frame-info
    acquisition and desktop LastPresentTime can authorize this comparison.
    """
    import numpy as np
    sys.path.insert(0, str(SOURCE.parent))
    import source_pixel_analysis

    class FrameInfo(ctypes.Structure):
        _fields_ = [("LastPresentTime", ctypes.c_int64),
                    ("LastMouseUpdateTime", ctypes.c_int64), ("AccumulatedFrames", ctypes.c_uint32)]

    class Delegate:
        def AcquireNextFrame(self, timeout, pointer, resource):
            info = pointer._obj
            info.LastPresentTime = 0 if kind == "pointer-only" else 10150
            info.LastMouseUpdateTime = 10190
            info.AccumulatedFrames = 1

    class Camera:
        width, height, is_capturing = 1920, 1080, False

        def __init__(self):
            self._output = SimpleNamespace(desc=SimpleNamespace(
                DesktopCoordinates=SimpleNamespace(left=-100, top=0)))
            self._duplicator = SimpleNamespace(duplicator=Delegate(),
                performance_frequency=1000, latest_frame_ticks=10190)

        def grab(self, *, region, copy, new_frame_only):
            assert copy and new_frame_only
            if kind != "cached":
                info = FrameInfo()
                self._duplicator.duplicator.AcquireNextFrame(0, ctypes.byref(info), None)
            return np.zeros((200, 300, 4), dtype=np.uint8)

    clocks = iter((10.08, 10.10, 10.20))
    monkeypatch.setattr(source_pixel_analysis.time, "perf_counter", lambda: next(clocks))
    pixels, observed = source_pixel_analysis.grab_observed(Camera(), RECTANGLE)
    value = gate()
    accepted, evidence = value.poll(pixels, observed, state_before=STATE,
                                  state_after=STATE, now=10.25, content_revision="same bytes")
    assert observed["acquisitionFrameQpcTicks"] == 10190
    if kind == "unchanged-raster":
        assert accepted is not None and evidence["status"] == "PASS"
        assert observed["desktopFrameQpcTicks"] == 10150
    else:
        assert accepted is None and evidence["status"] == "PENDING"
        assert evidence["reason"] == ("pointer-only or unproved raster delivery"
            if kind == "pointer-only" else "successful native acquisition unproved")
