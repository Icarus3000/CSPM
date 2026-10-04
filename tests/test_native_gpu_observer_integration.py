"""Run real spike methods with synthetic arrays, fake COM and an inert timer.

The diagnostic's main(), disposable data copying and GUI imports are never
executed. Methods are extracted from the current NativeSpike AST so these
checks cover callback/crop/cleanup integration without creating any window.
"""
import ast
import copy
import ctypes
import hashlib
import os
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "scripts/diagnostics"
sys.path.insert(0, str(DIAGNOSTICS))
import native_presentation_observer as observer_module
from source_pixel_analysis import compare_pixels, physical_regions


class InertTimer:
    def __init__(self):
        self.calls = []

    def singleShot(self, delay, callback):
        self.calls.append((delay, callback))


class FakeFunction:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *arguments):
        return self.callback(*arguments)


@pytest.fixture
def harness():
    timer = InertTimer()
    context = {"failures": []}
    actions = []
    native = SimpleNamespace(
        cspm_comp_hwnd=lambda host: 456,
        cspm_comp_destroy=lambda host: actions.append(("destroy-host", host)),
        cspm_gpu_release=lambda frame: actions.append(("release-frame", frame)),
        cspm_comp_set_observer_witness=FakeFunction(lambda *args: actions.append(("witness", args)) or 1))
    options = SimpleNamespace(physical_diagnostics=True, source_observation_only=False,
                              endpoint_pixels=True)
    source = ast.parse((DIAGNOSTICS / "native_gpu_transition_spike.py").read_text(encoding="utf-8"))
    classes = [node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "NativeSpike"]
    assert len(classes) == 1
    names = {"configure_witness", "refresh_witness", "observe_desktop", "poll_desktop_observation",
             "record_pixel_regions", "compare_pixels", "complete"}
    methods = [copy.deepcopy(node) for node in classes[0].body
               if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {method.name for method in methods} == names
    for method in methods:
        method.decorator_list = []
    namespace = {"args": options, "dll": native, "QTimer": timer, "context": context,
        "ctypes": ctypes, "os": os, "hashlib": hashlib,
        "time": SimpleNamespace(perf_counter=lambda: 10.25), "isValid": lambda window: True,
        "native_error": lambda host: "synthetic native rejection",
        "native_present_trace": lambda dll, host: {"scope": "synthetic no-runtime trace"},
        "FreshPresentationGate": observer_module.FreshPresentationGate}
    exec(compile(ast.Module(body=methods, type_ignores=[]), "<real spike methods, no GUI>", "exec"), namespace)
    records = []
    window = SimpleNamespace(winId=lambda: 123, devicePixelRatio=lambda: 1,
        setOpacity=lambda opacity: actions.append(("opacity", opacity)))
    app = SimpleNamespace(finished=False, completed=0, capture_in_progress=False,
        completion_pending=False, live_handoff_connected=False, capture_connected=False,
        profile_armed=False, qt_target_capture_pending=False, capture_request=None,
        observation_pending=None, host=101, frames=[201, 202], window=window,
        pixel_pairs=[], pixel_regions={}, target_pixel_regions={}, source_desktop=None,
        target_desktop=None, snapshot_observations={}, desktop_camera=SimpleNamespace(
            release=lambda: actions.append(("release-camera",))),
        analyze_pixels=compare_pixels, physical_regions=physical_regions,
        unlock_input=lambda: actions.append(("unlock-input",)),
        quit=lambda: actions.append(("quit",)),
        evaluate=lambda command: actions.append(("evaluate", command)),
        record=lambda event, **values: records.append({"event": event, **values}),
        fail=lambda category, error: context["failures"].append(category + ": " + error))
    for name in names:
        setattr(app, name, MethodType(namespace[name], app))
    return SimpleNamespace(app=app, timer=timer, context=context, actions=actions,
                           records=records, dll=native, args=options)


@pytest.mark.parametrize("source_size,target_size", [((16, 12), (6, 4)), ((6, 4), (16, 12))])
def test_source_and_target_analyses_use_their_own_physical_partition(harness, source_size, target_size):
    app = harness.app
    for kind, (width, height) in (("source", source_size), ("target", target_size)):
        app.evaluate = lambda command, w=width, h=height: SimpleNamespace(toVariant=lambda:
            SimpleNamespace(x=lambda: 2) if "HeaderMetrics" in command else [0, 0, w, h])
        app.record_pixel_regions([50, 60, width, height], kind)
    source = np.zeros((source_size[1], source_size[0], 4), dtype=np.uint8)
    target = np.zeros((target_size[1], target_size[0], 4), dtype=np.uint8)
    app.compare_pixels("source-live-to-gpu-pixels", source, source.copy())
    app.compare_pixels("gpu-to-live-target-pixels", target, target.copy())
    app.evaluate = lambda command: harness.actions.append(("evaluate", command))
    app.complete()
    analyses = [record for record in harness.records if record["event"] == "physical-pixel-analysis"]
    assert [(record["comparison"], record["pixels"]) for record in analyses] == [
        ("source-live-to-gpu-pixels", source_size[0] * source_size[1]),
        ("gpu-to-live-target-pixels", target_size[0] * target_size[1])]
    assert all(record["status"] == "PASS" for record in analyses)
    assert harness.context["failures"] == []
    assert app.pixel_pairs == [] and app.frames == []
    assert app.host is None and app.desktop_camera is None
    assert any(delay == 2000 for delay, _ in harness.timer.calls)


def test_spatial_analysis_exception_is_retained_and_does_not_abandon_cleanup(harness):
    app = harness.app
    pixels = np.zeros((4, 6, 4), dtype=np.uint8)
    app.pixel_pairs = [(0, "gpu-to-live-target-pixels", pixels, pixels),
                       (0, "source-live-to-gpu-pixels", pixels, pixels)]
    attempts = []

    def analysis(old, new, *, regions):
        attempts.append(regions)
        if len(attempts) == 1:
            raise ValueError("synthetic old source bounds exceed restored target")
        return compare_pixels(old, new, regions=regions)

    app.analyze_pixels = analysis
    app.complete()
    assert harness.context["failures"] == [
        "gpu-to-live-target-pixels: spatial analysis failed: synthetic old source bounds exceed restored target"]
    assert len(attempts) == 2
    assert any(record["event"] == "physical-pixel-analysis-failure" for record in harness.records)
    assert any(record["event"] == "spike-finished" for record in harness.records)
    assert ("unlock-input",) in harness.actions
    assert ("destroy-host", 101) in harness.actions
    assert ("release-frame", 201) in harness.actions and ("release-frame", 202) in harness.actions
    assert ("release-camera",) in harness.actions
    assert any("requestCloseAnimation" in str(action) for action in harness.actions)
    assert harness.timer.calls[-1][0] == 2000
    actions = list(harness.actions)
    app.complete()
    assert harness.actions == actions


def test_target_partition_at_fractional_dpi_keeps_prior_source_coordinates(harness):
    app = harness.app
    app.window.devicePixelRatio = lambda: 1.25
    app.evaluate = lambda command: SimpleNamespace(toVariant=lambda:
        SimpleNamespace(x=lambda: 2) if "HeaderMetrics" in command else [1, 1, 12, 8])
    app.record_pixel_regions([50, 60, 20, 15], "source")
    saved_source = copy.deepcopy(app.pixel_regions[0])
    app.evaluate = lambda command: SimpleNamespace(toVariant=lambda:
        SimpleNamespace(x=lambda: 2) if "HeaderMetrics" in command else [1, 1, 6, 4])
    app.record_pixel_regions([0, 0, 10, 8], "target")
    assert app.pixel_regions[0] == saved_source
    assert app.target_pixel_regions[0] != saved_source
    assert app.target_pixel_regions[0]["clientBody"] == [[1, 3, 9, 6]]
    assert harness.records[-1]["contentXYWH"] == [1, 1, 8, 5]


def test_cleanup_waits_for_owned_capture_then_runs_without_destroying_an_active_frame(harness):
    app = harness.app
    app.capture_in_progress = True
    app.complete()
    assert app.completion_pending and not app.finished
    assert harness.actions == []
    assert harness.timer.calls[0][0] == 10
    app.capture_in_progress = False
    harness.timer.calls[0][1]()
    assert app.finished and app.host is None and app.frames == []
    assert ("destroy-host", 101) in harness.actions
    assert harness.timer.calls[-1][0] == 2000


@pytest.mark.parametrize("source_only", [False, True])
def test_visual_witness_is_visible_on_output_and_outside_both_actual_clients(harness, source_only):
    app = harness.app
    harness.args.source_observation_only = source_only
    app.envelope = [-32, -32, 1984, 1104]
    physical, target = [100, 100, 500, 400], [0, 0, 1920, 1040]
    app.configure_witness(physical, target)
    x, y, width, height = app.witness_rect
    assert 0 <= x < x + width <= 1920 and 0 <= y < y + height <= 1080
    for client in (physical, target):
        cx, cy, cw, ch = client
        assert x + width <= cx or cx + cw <= x or y + height <= cy or cy + ch <= y
    submitted = [action for action in harness.actions if action[0] == "witness"]
    assert submitted == [("witness", (101, x + 32, y + 32, app.witness_revision))]


@pytest.mark.parametrize("failure", ["no-space", "missing-native-export"])
def test_unavailable_witness_fails_instead_of_weakening_the_freshness_gate(harness, failure):
    app = harness.app
    app.envelope = [-32, -32, 1984, 1144]
    physical = [100, 100, 500, 400]
    target = [0, 0, 1920, 1080] if failure == "no-space" else [0, 0, 1920, 1040]
    if failure == "missing-native-export":
        del harness.dll.cspm_comp_set_observer_witness
    with pytest.raises(RuntimeError, match="witness outside both clients"):
        app.configure_witness(physical, target)
    assert not any(action[0] == "witness" for action in harness.actions)


def observation_fixture(harness, monkeypatch, phase, *, broken_witness=False):
    app = harness.app
    app.desktop_observer = observer_module.DesktopFrameObserver(now=9)
    app.window_state = "normal"
    app.witness_rect = [2, 42, 8, 8]
    app.witness_revision = 0x2345
    rectangle, bounds = [20, 30, 12, 8], [2, 30, 30, 20]
    capture = np.zeros((20, 30, 4), dtype=np.uint8)
    client = np.arange(8 * 12 * 4, dtype=np.uint8).reshape(8, 12, 4)
    capture[:8, 18:30] = client
    capture[12:20, :8] = [phase, 0x23, 0x45, 0]
    if broken_witness:
        capture[12, 0, 2] ^= 1
    app.observation_state = lambda: {"live": {"hwnd": 123, "visible": True,
        "iconic": False, "cloaked": 0, "clientXYWH": rectangle},
        "transition": {"hwnd": 456, "visible": True}, "windowState": "normal",
        "transitionGeneration": 1, "presentationRevision": 0x2345}
    acquisitions = []

    def grab(camera, actual_bounds):
        assert actual_bounds == bounds
        acquisitions.append(actual_bounds)
        sequence = len(acquisitions)
        started, finished, ticks = (10.1, 10.2, 10150) if sequence == 1 else (10.8, 10.85, 10840)
        return capture, {"callStarted": started, "callFinished": finished,
            "rectangleXYWH": actual_bounds, "freshAcquisition": True,
            "cacheFallbackAllowed": False, "newDeliveryObserved": True,
            "acquisitionSequence": sequence, "acquisitionSessionGeneration": 1,
            "desktopPixelsUpdated": True, "desktopFrameQpcTicks": ticks, "qpcFrequency": 1000}

    app.grab_observed = grab
    clocks = iter((10.05, 10.25, 10.90))
    monkeypatch.setattr(observer_module.time, "perf_counter", lambda: next(clocks))
    returned = []
    app.observe_desktop(rectangle, "source-hidden", 10,
                        {"transition.visible": True, "live.clientXYWH": rectangle}, returned.append, phase=phase)
    return SimpleNamespace(capture=capture, client=client, returned=returned, bounds=bounds)


@pytest.mark.parametrize("phase", [1, 3])
def test_same_swapchain_union_is_verified_before_extracting_an_owned_client_only_array(harness, monkeypatch, phase):
    data = observation_fixture(harness, monkeypatch, phase)
    assert len(data.returned) == 1
    np.testing.assert_array_equal(data.returned[0], data.client)
    assert not np.shares_memory(data.returned[0], data.capture)
    proof = harness.app.snapshot_observations["source-hidden"]
    assert proof["status"] == "PASS"
    assert proof["expectedRectangleXYWH"] == data.bounds
    assert proof["frame"]["visualWitness"] == {"revision": 0x2345, "phase": phase, "exact": True}
    assert proof["frame"]["witnessMatchedPixels"] == 64
    assert harness.context["failures"] == [] and harness.timer.calls == []


def test_one_wrong_witness_pixel_requires_retry_and_bounded_reported_failure(harness, monkeypatch):
    data = observation_fixture(harness, monkeypatch, 1, broken_witness=True)
    assert data.returned == []
    assert len(harness.timer.calls) == 1 and harness.timer.calls[0][0] == 8
    assert harness.context["failures"] == []
    harness.timer.calls[0][1]()
    assert data.returned == [] and harness.app.observation_pending is None
    proof = harness.app.snapshot_observations["source-hidden"]
    assert proof["status"] == "FAIL"
    assert proof["reason"] == "intended presentation visual witness unavailable"
    assert proof["frame"]["witnessMatchedPixels"] == 63
    assert len(harness.context["failures"]) == 1
