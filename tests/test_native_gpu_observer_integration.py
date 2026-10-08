"""Run real spike methods with synthetic arrays, fake COM and an inert timer.

The diagnostic's main(), disposable data copying and GUI imports are never
executed. Methods are extracted from the current NativeSpike AST so these
checks cover callback/crop/cleanup integration without creating any window.
"""
import ast
import copy
import ctypes
from ctypes import wintypes
import hashlib
import json
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
                              endpoint_pixels=True, controlled_backdrop=False, probe_composition=False,
                              input_witness=False, single_owner_source=False, source_unlocked=False,
                              intrinsic_only=False, probe_endpoint=False, post_input_pixels=False,
                              endpoint_hold_ms=0)
    source = ast.parse((DIAGNOSTICS / "native_gpu_transition_spike.py").read_text(encoding="utf-8"))
    classes = [node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "NativeSpike"]
    assert len(classes) == 1
    names = {"configure_witness", "refresh_witness", "observe_desktop", "poll_desktop_observation",
             "record_pixel_regions", "compare_pixels", "source_removal_observation", "complete",
             "begin_input_witness", "input_witness_finished", "defer_source_visibility",
             "resume_live_host_hidden", "transfer_source_visibility", "after_source_coverage",
             "restore_source_activation", "source_reference_observed", "after_source_transfer_observed",
             "raise_source_visibility", "endpoint_observed", "live_host_frame", "live_host_deadline",
             "handoff", "handoff_compare", "analyze_endpoint_frame", "finish_handoff",
             "accepted_input_pixels_observed", "poll_native", "record_target_import_rejection"}
    methods = [copy.deepcopy(node) for node in classes[0].body
               if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {method.name for method in methods} == names
    for method in methods:
        method.decorator_list = []
    namespace = {"args": options, "dll": native, "QTimer": timer, "context": context,
        "ctypes": ctypes, "wintypes": wintypes, "os": os, "hashlib": hashlib, "json": json,
        "time": SimpleNamespace(perf_counter=lambda: 10.25), "isValid": lambda window: True,
        "native_error": lambda host: "synthetic native rejection",
        "native_present_trace": lambda dll, host: {"scope": "synthetic no-runtime trace"},
        "native_observation": lambda dll, host: {"hostHideReturnSeconds": 10.2},
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
        composition_probe=None, controlled_backdrop=None,
        input_witness=None, input_release_seconds=None, input_trace=None,
        endpoint_diagnostic_pixels=None, diagnostic_texel_readbacks=0,
        live_visibility_transferred=False,
        source_foreground_before_transfer=False, source_active_before_transfer=False,
        source_before_resume=None,
        analyze_pixels=compare_pixels, physical_regions=physical_regions,
        lock_input=lambda: actions.append(("lock-input",)),
        unlock_input=lambda: actions.append(("unlock-input",)),
        quit=lambda: actions.append(("quit",)),
        evaluate=lambda command: actions.append(("evaluate", command)),
        record=lambda event, **values: records.append({"event": event, "cycle": 0, **values}),
        fail=lambda category, error: context["failures"].append(category + ": " + error))
    for name in names:
        setattr(app, name, MethodType(namespace[name], app))
    return SimpleNamespace(app=app, timer=timer, context=context, actions=actions,
                           records=records, dll=native, args=options, namespace=namespace)


def test_rejected_target_retains_native_worker_entry_and_original_failure(harness):
    observation = {"targetImportBeginSeconds": 10.9, "lastPresentReturnSeconds": 10.4}
    harness.namespace["native_observation"] = lambda dll, host: dict(observation)
    harness.namespace["native_error"] = lambda host: "First presentation slot failure"
    harness.app.record_target_import_rejection({"targetImportStarted": 10.7, "targetImportFinished": 11.0})
    record = harness.records[-1]
    assert record["event"] == "target-render-import-rejected"
    assert (record["started"], record["finished"]) == (10.7, 11.0)
    assert record["native"] == observation
    assert record["nativeError"] == "First presentation slot failure"
    assert harness.context["failures"] == ["target readiness: First presentation slot failure"]


def test_rejected_target_snapshot_failure_does_not_hide_original_failure(harness):
    def unavailable(dll, host):
        raise RuntimeError("Observation unavailable")
    harness.namespace["native_observation"] = unavailable
    harness.namespace["native_error"] = lambda host: "First target failure"
    harness.app.record_target_import_rejection({})
    assert harness.records[-1]["native"] == {"available": False}
    assert harness.context["failures"] == ["target readiness: First target failure"]


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


@pytest.mark.parametrize("bad_backdrop", [False, True])
def test_source_composition_removal_checks_full_backdrop_and_logs_only_aggregate_gpu_data(harness, bad_backdrop):
    app = harness.app
    harness.args.controlled_backdrop = harness.args.probe_composition = True
    color = [83, 61, 37, 255]
    backdrop = np.full((4, 6, 4), color, np.uint8)
    live = backdrop.copy()
    live[1, 1] = [140, 130, 120, 255]
    app.source_desktop = app.source_overlap = app.source_native_desktop = live
    app.composition_probe = ([(1, 1)], ["cornerTL"], np.array([[140, 130, 120, 255]], np.uint8),
        np.array([[140, 130, 120, 255]], np.uint8), {"included": [True]})
    app.controlled_backdrop = SimpleNamespace(bgra=color,
        close=lambda: harness.actions.append(("close-owned-backdrop",)))
    if bad_backdrop:
        backdrop[3, 5, 0] ^= 1  # Outside the tiny sampled probe; full verification must fail.
    app.source_removal_observation(backdrop)
    proofs = [row for row in harness.records if row["event"] == "controlled-backdrop-verification"]
    assert proofs[0]["status"] == ("FAIL" if bad_backdrop else "PASS")
    assert proofs[0]["differentPixels"] == int(bad_backdrop)
    analysis = next(row for row in harness.records if row["event"] == "composition-probe-analysis")
    assert analysis["sourceSubmittedDifferentSamples"] == 0
    assert analysis["models"]["submittedPremultipliedOverBackdropToNative"]["differentSamples"] == 0
    assert ("close-owned-backdrop",) in harness.actions
    assert app.controlled_backdrop is app.composition_probe is None
    assert app.completed == 1 and app.finished
    import json
    assert "[140, 130, 120, 255]" not in json.dumps(harness.records)
    assert any("controlled backdrop was not exact" in failure for failure in harness.context["failures"]) == bad_backdrop


def test_input_witness_waits_for_consumed_pair_and_uses_actual_acceptance_timestamp(harness, monkeypatch):
    app = harness.app
    app.input_release_seconds = 10.1
    app.current = {"command": 9.0}
    app.engine = "owned-engine"
    owner = object()
    app.evaluate = lambda command: SimpleNamespace(toQObject=lambda: owner)
    started = []
    class Witness:
        def __init__(self, window, engine, interaction_owner, **kwargs):
            assert window is app.window and engine == app.engine and interaction_owner is owner
            assert kwargs["disposable"] is True
            self.finished = kwargs["finished"]
        def start(self):
            started.append(self)
    monkeypatch.setitem(sys.modules, "input_restoration_witness", SimpleNamespace(InputRestorationWitness=Witness))
    app.step = lambda: None
    app.begin_input_witness()
    assert app.completed == 0 and harness.timer.calls == []
    assert app.input_witness is started[0]
    started[0].finished({"status": "PASS", "acceptedSeconds": 10.12, "reason": "owned pair consumed"})
    result = next(row for row in harness.records if row["event"] == "input-restoration-acceptance")
    assert result["commandToAcceptedMs"] == pytest.approx(1120)
    assert result["inputReleaseToAcceptedMs"] == pytest.approx(20)
    assert app.completed == 1 and app.input_witness is None
    assert harness.timer.calls[0][0] == 200 and harness.context["failures"] == []


def test_failed_input_witness_does_not_advance_completed_cycle(harness):
    app = harness.app
    app.input_release_seconds = 10.1
    app.current = {"command": 9.0}
    app.input_witness = object()
    app.input_witness_finished({"status": "FAIL", "acceptedSeconds": None, "reason": "bounded timeout"})
    assert app.completed == 0 and app.input_witness is None and harness.timer.calls == []
    assert harness.context["failures"] == ["input restoration: bounded timeout"]


def test_fixture_cleanup_cancels_only_the_pending_owned_input_witness(harness):
    app = harness.app
    app.input_witness = SimpleNamespace(cancel=lambda: harness.actions.append(("cancel-owned-input-witness",)))
    app.complete()
    assert app.input_witness is None
    assert harness.actions[0] == ("cancel-owned-input-witness",)


@pytest.mark.parametrize("api_success", [False, True])
def test_single_owner_transfer_runs_on_caller_then_resumes_same_hidden_opacity_live_host(harness, api_success):
    app = harness.app
    harness.args.single_owner_source = True
    visible = {"live": True}
    physical = [100, 100, 6, 4]
    properties = dict(zip(("finalX", "finalY", "finalW", "finalH"), physical))
    app.window.property = properties.get
    app.window.isActive = lambda: True
    app.window_observation = lambda hwnd: {"foreground": True, "processId": os.getpid(), "visible": True}
    app.window.show = lambda: harness.actions.append(("qt-show",))  # Model Qt's cached-visible no-op.
    app.witness_revision = 10
    app.current = {"sourceClient": physical}
    app.source_desktop = np.zeros((4, 6, 4), np.uint8)
    app.state_observation = lambda label: harness.actions.append(("state", label))
    app.refresh_witness = lambda: harness.actions.append(("refresh-witness", app.witness_revision))
    app.observe_desktop = lambda *args, **kwargs: harness.actions.append(("observe", args, kwargs))
    user = SimpleNamespace(IsWindowVisible=lambda hwnd: visible["live"],
        ShowWindow=lambda hwnd, mode: visible.update(live=True) or harness.actions.append(("native-show", hwnd, mode)))
    harness.namespace.update(user=user, client=lambda window: physical,
        native_observation=lambda dll, host: {"sourceShowReturnSeconds": 10.2, "lastPresentReturnSeconds": 10.3})
    clock = iter((10.1, 10.2, 10.35, 10.4, 10.45, 10.5))
    harness.namespace["time"] = SimpleNamespace(perf_counter=lambda: next(clock))
    harness.dll.cspm_comp_status = lambda host: 1
    harness.dll.cspm_comp_raise_source_visibility = FakeFunction(
        lambda host: harness.actions.append(("owner-thread-raise", host)) or 1)
    def transfer(host, hwnd):
        assert host == 101 and hwnd == 123
        assert harness.actions[-1] == ("lock-input",)
        harness.actions.append(("caller-transfer", host, hwnd))
        visible["live"] = False
        return int(api_success)
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(transfer)
    if not api_success:
        with pytest.raises(RuntimeError, match="transfer rejected"):
            app.transfer_source_visibility(physical)
        assert app.live_visibility_transferred and not visible["live"]
        app.complete()
        assert visible["live"] and not app.live_visibility_transferred
        assert ("opacity", 1) in harness.actions
        return
    app.transfer_source_visibility(physical)
    assert not visible["live"] and app.live_visibility_transferred
    before_proof = next(action for action in harness.actions if action[0] == "observe")
    first_raise = ("owner-thread-raise", 101)
    assert harness.actions.index(("caller-transfer", 101, 123)) < harness.actions.index(first_raise)
    assert harness.actions.index(first_raise) < harness.actions.index(before_proof)
    assert before_proof[1][1] == "source-transfer-before-resume"
    assert before_proof[1][2] == 10.4  # Acquisition must be newer than the successful ordering return.
    assert before_proof[1][3]["live.visible"] is False and before_proof[1][3]["qtOpacity"] == 1
    app.after_source_transfer_observed(app.source_desktop.copy())
    assert visible["live"] and not app.live_visibility_transferred
    assert ("opacity", 0) in harness.actions and ("native-show", 123, 4) in harness.actions
    assert app.witness_revision == 11
    proof = [action for action in harness.actions if action[0] == "observe"][-1]
    assert proof[1][:3] == (physical, "source-transfer", 10.5)
    assert proof[1][3]["qtOpacity"] == 0 and "live.foregroundHwnd" not in proof[1][3]
    assert proof[2] == {"phase": 1}
    raises = [index for index, action in enumerate(harness.actions) if action == first_raise]
    assert len(raises) == 2
    assert harness.actions.index(("native-show", 123, 4)) < raises[1] < harness.actions.index(proof)


@pytest.mark.parametrize("intrinsic", [False, True])
def test_failed_source_ordering_cannot_claim_desktop_proof_or_start_native_clock(harness, intrinsic):
    app = harness.app
    harness.args.single_owner_source = True
    harness.args.intrinsic_only = intrinsic
    physical = [100, 100, 6, 4]
    properties = dict(zip(("finalX", "finalY", "finalW", "finalH"), physical))
    app.window.property = properties.get
    app.window.isActive = lambda: True
    app.window_observation = lambda hwnd: {"foreground": True, "processId": os.getpid(), "visible": True}
    app.state_observation = lambda label: harness.actions.append(("state", label))
    app.resume_live_host_hidden = lambda: harness.actions.append(("resume-hidden-live",))
    app.observe_desktop = lambda *args, **kwargs: pytest.fail("Failed ordering cannot claim desktop proof")
    app.start_native = lambda: pytest.fail("Failed ordering cannot start the fixed native clock")
    harness.namespace["client"] = lambda window: physical
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(lambda *args: 1)
    harness.dll.cspm_comp_status = lambda host: 1
    harness.dll.cspm_comp_raise_source_visibility = FakeFunction(
        lambda host: harness.actions.append(("owner-thread-raise", host)) or 0)
    with pytest.raises(RuntimeError, match="Stopped native source ordering failed"):
        app.transfer_source_visibility(physical)
    assert ("owner-thread-raise", 101) in harness.actions
    assert not any(row["event"] == "source-visibility-reordered" for row in harness.records)
    assert not hasattr(app, "source_reorder_return_seconds")


def test_single_owner_coverage_is_a_required_transfer_comparison_not_an_overlap(harness):
    app = harness.app
    harness.args.single_owner_source = True
    pixels = np.zeros((4, 6, 4), np.uint8)
    app.source_desktop = pixels
    app.current = {"sourceClient": [100, 100, 6, 4]}
    app.witness_revision = 10
    app.refresh_witness = lambda: None
    app.observe_desktop = lambda *args, **kwargs: None
    app.after_source_hidden = lambda *args: None
    harness.namespace["native_observation"] = lambda dll, host: {"lastPresentReturnSeconds": 10.3}
    app.after_source_coverage(pixels)
    assert app.pixel_pairs[0][1] == "source-live-to-transfer-pixels"
    assert app.witness_revision == 11


def test_deferred_source_visibility_requires_all_native_exports_before_preparation(harness):
    with pytest.raises(RuntimeError, match="all native"):
        harness.app.defer_source_visibility()
    calls = []
    harness.dll.cspm_comp_defer_source_visibility = FakeFunction(lambda host: calls.append(host) or 1)
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(lambda *args: 1)
    harness.dll.cspm_comp_raise_source_visibility = FakeFunction(lambda *args: 1)
    harness.app.defer_source_visibility()
    assert calls == [101]
    assert harness.records[-1]["event"] == "source-visibility-deferred"


def test_single_owner_transfer_geometry_change_is_rejected_before_observation(harness):
    app = harness.app
    physical = [100, 100, 6, 4]
    props = dict(zip(("finalX", "finalY", "finalW", "finalH"), physical))
    app.window.property = props.get
    app.window.isActive = lambda: True
    app.window_observation = lambda hwnd: {"foreground": True}
    app.state_observation = lambda label: None
    app.resume_live_host_hidden = lambda: props.update(finalW=7)
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(lambda *args: 1)
    harness.namespace["client"] = lambda window: physical
    app.current = {"sourceClient": physical}
    app.source_desktop = np.zeros((4, 6, 4), np.uint8)
    app.single_owner_source_geometry = list(props.values())
    with pytest.raises(RuntimeError, match="saved source geometry"):
        app.after_source_transfer_observed(app.source_desktop.copy())


@pytest.mark.parametrize("was_foreground", [False, True])
def test_activation_is_never_requested_on_disabled_live_reveal(harness, was_foreground):
    app = harness.app
    app.source_foreground_before_transfer = was_foreground
    app.window.requestActivate = lambda: pytest.fail("Reveal must not request activation while the source is disabled")
    app.window.isActive = lambda: False
    app.window_observation = lambda hwnd: {"foreground": False, "foregroundHwnd": 999}
    harness.namespace["user"] = SimpleNamespace(SetForegroundWindow=lambda hwnd: harness.actions.append(("activate", hwnd)) or 1)
    app.restore_source_activation("live-host-revealed")
    assert harness.actions == [] and harness.records[-1]["event"] == "source-activation-not-requested"


@pytest.mark.parametrize("rejection", ["never-foreground", "other-foreground", "changed-foreground",
    "foreign-process", "foreign-thread", "unknown-thread", "disabled", "still-locked", "invalid", None])
def test_unlock_activation_requests_only_still_foreground_owned_enabled_gui_thread(harness, monkeypatch, rejection):
    app = harness.app
    app.source_foreground_before_transfer = rejection != "never-foreground"
    app.input_was_enabled = True if rejection == "still-locked" else None
    app.window.isActive = lambda: False
    app.window_observation = lambda hwnd: {"foregroundHwnd": 999 if rejection == "other-foreground" else hwnd}
    focus = {"hwnd": 0}
    posts = []

    def identify(hwnd, pointer):
        pointer._obj.value = os.getpid() + int(rejection == "foreign-process")
        return 0 if rejection == "unknown-thread" else (99 if rejection == "foreign-thread" else 77)

    def request_activate():
        focus["hwnd"] = 123  # Model Qt's native focus restoration.
        posts.append("owned-qt-request")

    app.window.requestActivate = request_activate

    user = SimpleNamespace(
        GetForegroundWindow=FakeFunction(lambda: 999 if rejection == "changed-foreground" else 123),
        GetWindowThreadProcessId=FakeFunction(identify),
        IsWindowEnabled=FakeFunction(lambda hwnd: rejection != "disabled"),
        GetFocus=FakeFunction(lambda: focus["hwnd"]),
        GetActiveWindow=FakeFunction(lambda: 123),
        SetFocus=FakeFunction(lambda hwnd: pytest.fail("Qt request must not have duplicate native focus calls")),
        SetForegroundWindow=FakeFunction(lambda hwnd: pytest.fail("Unlock must not change desktop foreground")))
    kernel = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: 77))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    harness.namespace.update(user=user, isValid=lambda window: rejection != "invalid")
    app.restore_source_activation("input-restored")
    if rejection:
        assert posts == []
        assert harness.records[-1]["event"] in ("source-focus-not-requested", "source-activation-not-requested")
    else:
        assert posts == ["owned-qt-request"] and focus["hwnd"] == 123
        assert harness.records[-1]["event"] == "source-activation-restoration"
        assert harness.records[-1]["focusBeforeHwnd"] == 0
        assert harness.records[-1]["focusAfterHwnd"] == 123
        assert harness.records[-1]["nativeFocusOwned"] is True
        assert harness.records[-1]["qtActive"] is False
    assert harness.timer.calls == []


def test_focus_api_outcome_does_not_qualify_the_independent_input_witness(harness, monkeypatch):
    app = harness.app
    app.source_foreground_before_transfer = True
    app.input_was_enabled = None
    app.window.isActive = lambda: False
    app.window.requestActivate = lambda: None
    app.window_observation = lambda hwnd: {"foregroundHwnd": hwnd}
    def identify(hwnd, pointer):
        pointer._obj.value = os.getpid()
        return 77
    user = SimpleNamespace(GetForegroundWindow=FakeFunction(lambda: 123),
        GetWindowThreadProcessId=FakeFunction(identify), IsWindowEnabled=lambda hwnd: True,
        GetFocus=FakeFunction(lambda: 999), GetActiveWindow=FakeFunction(lambda: 123))
    kernel = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: 77))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    harness.namespace["user"] = user
    app.restore_source_activation("input-restored")
    assert harness.records[-1]["nativeFocusOwned"] is False
    assert app.completed == 0 and harness.timer.calls == []


def test_trace_heartbeat_starts_before_post_and_stops_at_witness_terminal(harness, monkeypatch):
    app = harness.app
    app.input_release_seconds = 10.1
    app.current = {"command": 9.0}
    app.engine, app.step = "owned-engine", lambda: None
    app.evaluate = lambda command: SimpleNamespace(toQObject=lambda: object())
    actions = []
    app.input_trace = SimpleNamespace(set_pending=lambda pending, **values: actions.append((pending, values["cycle"])))

    class Witness:
        def __init__(self, *args, **kwargs):
            self.finished = kwargs["finished"]
        def start(self):
            assert actions == [(True, 0)]
            self.finished({"status": "FAIL", "acceptedSeconds": None, "reason": "bounded timeout"})

    monkeypatch.setitem(sys.modules, "input_restoration_witness", SimpleNamespace(InputRestorationWitness=Witness))
    app.begin_input_witness()
    assert actions == [(True, 0), (False, 0)]
    assert app.completed == 0
    assert harness.context["failures"] == ["input restoration: bounded timeout"]


def test_cleanup_stops_trace_heartbeat_before_cancelling_witness(harness):
    app = harness.app
    app.input_trace = SimpleNamespace(set_pending=lambda pending, **values:
        harness.actions.append(("trace-heartbeat", pending)))
    app.input_witness = SimpleNamespace(cancel=lambda: harness.actions.append(("cancel-witness",)))
    app.complete()
    assert harness.actions[:2] == [("trace-heartbeat", False), ("cancel-witness",)]


def test_original_source_foreground_is_saved_before_input_lock_changes_actual_activation(harness):
    app = harness.app
    harness.args.single_owner_source = True
    state = {"foreground": True, "nativeInputEnabled": True}
    app.window_observation = lambda hwnd: dict(state)
    app.window.isActive = lambda: state["foreground"]
    app.evaluate = lambda command: SimpleNamespace(toBool=lambda: True)
    app.lock_input = lambda: state.update(foreground=False, nativeInputEnabled=False)
    app.request_capture = lambda kind: harness.actions.append(("capture", kind))
    app.source_reference_observed(np.zeros((4, 6, 4), np.uint8))
    assert app.source_foreground_before_transfer is True and app.source_active_before_transfer is True
    assert state["foreground"] is True and state["nativeInputEnabled"] is True
    saved = next(row for row in harness.records if row["event"] == "source-activation-before-input-lock")
    assert saved["nativeInputEnabled"] is True
    assert harness.records[-1]["event"] == "source-capture-before-input-lock"
    assert harness.actions == [("capture", "source")]


@pytest.mark.parametrize("single_owner,unlocked", [(False, False), (False, True), (True, True)])
def test_source_capture_guard_retains_ordinary_order_and_unlocked_control(harness, single_owner, unlocked):
    app = harness.app
    harness.args.single_owner_source, harness.args.source_unlocked = single_owner, unlocked
    app.window_observation = lambda hwnd: {"foreground": True, "nativeInputEnabled": True}
    app.window.isActive = lambda: True
    app.evaluate = lambda command: SimpleNamespace(toBool=lambda: True)
    app.request_capture = lambda kind: harness.actions.append(("capture", kind))
    app.source_reference_observed(np.zeros((4, 6, 4), np.uint8))
    expected = [] if unlocked else [("lock-input",)]
    assert harness.actions == expected + [("capture", "source")]


@pytest.mark.parametrize("rejection", ["running", "foreign", "hidden", None])
def test_source_raise_requires_stopped_prepared_owned_visible_host(harness, rejection):
    app = harness.app
    harness.dll.cspm_comp_status = lambda host: 3 if rejection == "running" else 1
    calls = []
    harness.dll.cspm_comp_raise_source_visibility = FakeFunction(lambda host: calls.append(host) or 1)
    app.window_observation = lambda hwnd: {"processId": os.getpid()+int(rejection == "foreign"),
        "visible": rejection != "hidden"}
    app.state_observation = lambda label: harness.actions.append(("state", label))
    if rejection:
        with pytest.raises(RuntimeError, match="Source ordering"):
            app.raise_source_visibility()
        assert calls == []
    else:
        app.raise_source_visibility()
        assert calls == [101]
        assert harness.records[-1]["api"] == "native owner-thread saved source window-band ordering"
        assert harness.actions == [("state", "source-after-visibility-reorder")]


def test_pre_resume_and_resumed_physical_arrays_remain_independent_required_comparisons(harness):
    app = harness.app
    harness.args.single_owner_source = True
    app.source_desktop = np.zeros((4, 6, 4), np.uint8)
    app.source_before_resume = app.source_desktop.copy()
    resumed = app.source_desktop.copy()
    resumed[2, 3, 0] = 1
    app.current = {"sourceClient": [100, 100, 6, 4]}
    app.witness_revision = 10
    app.refresh_witness = lambda: None
    app.observe_desktop = lambda *args, **kwargs: None
    app.after_source_hidden = lambda *args: None
    harness.namespace["native_observation"] = lambda dll, host: {"lastPresentReturnSeconds": 10.3}
    app.after_source_coverage(resumed)
    assert [pair[1] for pair in app.pixel_pairs] == ["source-live-to-transfer-pixels", "source-transfer-to-resumed-pixels"]
    app.complete()
    assert harness.context["failures"] == ["source-live-to-transfer-pixels: physical pixels differ",
        "source-transfer-to-resumed-pixels: physical pixels differ"]


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


def test_intrinsic_transfer_requires_guarded_submission_geometry_and_skips_desktop(harness):
    app = harness.app
    harness.args.single_owner_source = harness.args.intrinsic_only = True
    harness.args.physical_diagnostics = harness.args.endpoint_pixels = False
    physical = [100, 100, 6, 4]
    app.window.property = dict(zip(("finalX", "finalY", "finalW", "finalH"), physical)).get
    app.window.isActive = lambda: True
    app.window_observation = lambda hwnd: {"foreground": True}
    app.state_observation = lambda label: None
    app.resume_live_host_hidden = lambda: harness.actions.append(("resume-hidden",))
    app.raise_source_visibility = lambda: harness.actions.append(("source-reorder",))
    app.start_native = lambda: harness.actions.append(("start-fixed-native-clock",))
    app.observe_desktop = lambda *args, **kwargs: pytest.fail("Intrinsic control cannot sample desktop")
    harness.namespace["client"] = lambda window: physical
    def transfer(host, hwnd):
        assert harness.actions == [("lock-input",)]
        harness.actions.append(("transfer",))
        return 1
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(transfer)
    app.transfer_source_visibility(physical)
    assert harness.actions == [("lock-input",), ("transfer",), ("resume-hidden",),
        ("source-reorder",), ("start-fixed-native-clock",)]
    assert harness.timer.calls == []
    submission = next(row for row in harness.records if row["event"] == "intrinsic-source-submission")
    assert "pixels and visibility continuity unmeasured" in submission["scope"]
    assert app.pixel_pairs == [] and not any(row.get("status") == "PASS" for row in harness.records)


def test_intrinsic_geometry_failure_cannot_start_native_clock(harness):
    app = harness.app
    harness.args.intrinsic_only = True
    physical = [100, 100, 6, 4]
    app.window.property = dict(zip(("finalX", "finalY", "finalW", "finalH"), physical)).get
    app.window.isActive = lambda: True
    app.window_observation = lambda hwnd: {"foreground": True}
    app.state_observation = lambda label: None
    app.resume_live_host_hidden = lambda: None
    harness.namespace["client"] = lambda window: [100, 100, 7, 4]
    harness.dll.cspm_comp_transfer_source_visibility = FakeFunction(lambda *args: 1)
    app.start_native = lambda: pytest.fail("Changed geometry cannot start clock")
    with pytest.raises(RuntimeError, match="changed saved geometry"):
        app.transfer_source_visibility(physical)


def test_intrinsic_live_handoff_uses_first_frame_and_unchanged_deadline_without_fixed_waits(harness):
    app = harness.app
    harness.args.intrinsic_only = True
    harness.args.physical_diagnostics = harness.args.endpoint_pixels = False
    app.current = {"kind": "restore"}
    signal_actions = []
    app.window.frameSwapped = SimpleNamespace(connect=lambda *args: signal_actions.append("connect"),
        disconnect=lambda *args: signal_actions.append("disconnect"))
    app.window.update = lambda: harness.actions.append(("window-update",))
    harness.namespace["Qt"] = SimpleNamespace(QueuedConnection="queued")
    app.handoff_compare = lambda: harness.actions.append(("intrinsic-handoff-compare",))
    app.observe_desktop = lambda *args, **kwargs: pytest.fail("Intrinsic handoff cannot observe desktop")
    harness.dll.cspm_comp_finish = lambda host: harness.actions.append(("finish-host", host)) or 1
    app.endpoint_observed(None)
    assert app.live_handoff_connected and signal_actions == ["connect"]
    assert [delay for delay, _ in harness.timer.calls] == [750]
    app.live_host_frame()
    assert not app.live_handoff_connected and signal_actions == ["connect", "disconnect"]
    assert harness.actions[-2:] == [("finish-host", 101), ("intrinsic-handoff-compare",)]
    assert [delay for delay, _ in harness.timer.calls] == [750]
    app.live_host_deadline()
    assert harness.context["failures"] == []
    assert not any(row.get("status") == "PASS" for row in harness.records)


def test_intrinsic_missing_live_frame_fails_the_same_bounded_gate(harness):
    harness.app.live_handoff_connected = True
    harness.app.live_host_deadline()
    assert harness.context["failures"] == [
        "live-HWND handoff: No submitted live-host frame before bounded observation deadline"]


def test_intrinsic_status_failure_cannot_be_treated_as_a_ready_endpoint(harness):
    app = harness.app
    harness.args.intrinsic_only = True
    harness.args.physical_diagnostics = False
    harness.dll.cspm_comp_status = lambda host: 16
    app.presentation_telemetry = lambda: {}
    app.measure_endpoint = lambda: pytest.fail("Rejected target cannot reveal endpoint")
    app.poll_native()
    assert harness.context["failures"] == ["DirectComposition presentation: synthetic native rejection"]
    assert harness.timer.calls == []


def test_endpoint_probe_preserves_complete_target_comparison_and_native_ownership_until_analysis(harness, monkeypatch, tmp_path):
    app = harness.app
    harness.args.probe_endpoint = True
    app.current, app.target_client = {"command": 9.0, "sourceClient": [100,100,6,4]}, [100, 100, 6, 4]
    app.envelope, app.witness_revision = [90,90,26,24], 7
    app.rows = harness.records
    app.rows.extend([{"event": "gpu-capture", "cycle": 0, "kind": kind,
        "frameIdentity": {"revision": revision}} for kind, revision in (("source",201),("target",202))])
    app.rows.append({"event": "physical-target-regions", "cycle": 0, "contentXYWH": app.target_client})
    app.snapshot_observations["target-live"] = {"frame": {"outputDesktopXYWH": [0,0,1920,1080]}}
    app.window_observation = lambda hwnd: {"windowXYWH": app.target_client}
    harness.namespace["audit"] = tmp_path
    native_pixels = np.zeros((4, 6, 4), np.uint8)
    live_pixels = native_pixels.copy()
    live_pixels[3, 5, 0] = 1
    app.target_desktop = native_pixels
    app.target_pixel_regions[0] = {"clientMargin": [[5, 0, 6, 4]]}
    app.state_observation = lambda label: None
    app.request_capture = lambda kind: harness.actions.append(("capture", kind))
    harness.namespace["client"] = lambda window: app.target_client
    app.handoff_compare(live_pixels)
    assert app.pixel_pairs[0][1] == "gpu-to-live-target-pixels"
    assert app.pixel_pairs[0][2] is native_pixels and app.pixel_pairs[0][3] is live_pixels
    assert app.endpoint_diagnostic_pixels is live_pixels
    assert app.host == 101 and app.frames == [201, 202]
    assert harness.actions == [("capture", "endpoint-live-diagnostic")]
    attempts = []
    def coordinates(target, live, final, regions, radius):
        assert target is native_pixels and live is live_pixels and final is live_pixels
        assert regions == app.target_pixel_regions[0]
        return [(5, 3)], ["clientMargin"], {"scope": "complete-client partition"}
    def native_probe(dll, host, coordinates):
        assert host == 101 and app.host == 101
        attempts.append("native")
        return np.zeros((1, 4), np.uint8), np.zeros((1, 4), np.uint8)
    def live_probe(dll, host, frame, coordinates):
        assert host == 101 and frame in (201,303)
        attempts.append("live")
        return np.array([[1, 0, 0, 0]], np.uint8)
    monkeypatch.setitem(sys.modules, "source_pixel_analysis", SimpleNamespace(
        composition_probe_coordinates=coordinates, probe_gpu_endpoint_composition=native_probe,
        probe_gpu_live_frame=live_probe, endpoint_composition_analysis=lambda *args: {"differentSamples": 1}))
    import submitted_surface_contract
    identity = {"witnessRevision": 7, "sourceFrameRevision": 201, "targetFrameRevision": 202,
        "hostLeft": 90, "hostTop": 90, "hostWidth": 26, "hostHeight": 24,
        "sourceLeft": 10, "sourceTop": 10, "sourceWidth": 6, "sourceHeight": 4,
        "targetLeft": 10, "targetTop": 10, "targetWidth": 6, "targetHeight": 4}
    monkeypatch.setattr(submitted_surface_contract, "probe_identity", lambda *args, **kw: dict(identity))
    monkeypatch.setattr(submitted_surface_contract, "frame_identity", lambda *args: {"revision":303,"width":6,"height":4})
    app.evaluate = lambda command: SimpleNamespace(toNumber=lambda: 3)
    app.finish_handoff = lambda: harness.actions.append(("finish-after-probe",))
    app.analyze_endpoint_frame({"client": app.target_client, "size": [6, 4], "frame": 303})
    assert attempts == ["native", "live", "live"] and app.diagnostic_texel_readbacks == 4
    assert app.endpoint_diagnostic_pixels is None and harness.actions[-1] == ("finish-after-probe",)
    evidence = next(row for row in harness.records if row["event"] == "endpoint-composition-analysis")
    assert evidence["differentSamples"] == 1 and "Diagnostic only" in evidence["timingQualification"]
    assert evidence["submittedIdentity"] == identity
    assert evidence["coordinateContract"]["samples"][0]["submittedSurfaceTexelXY"] == [15,13]
    import json
    private = json.loads((tmp_path/"endpoint_probe_private_cycle0.json").read_text())
    assert private["sourceSampleIndices"] == [0] and private["liveRGBA"] == [[0,0,1,0]]
    app.evaluate = lambda command: harness.actions.append(("evaluate", command))
    app.complete()
    comparison = next(row for row in harness.records if row["event"] == "physical-pixel-analysis")
    assert comparison["pixels"] == 24 and comparison["differentPixels"] == 1
    assert harness.context["failures"] == ["gpu-to-live-target-pixels: physical pixels differ"]


def endpoint_identity_harness(harness, monkeypatch, tmp_path):
    """A stopped synthetic endpoint whose sampling never creates a window."""
    import submitted_surface_contract
    app = harness.app
    app.current = {"command": 9.0, "sourceClient": [100, 100, 6, 4]}
    app.target_client, app.envelope = [100, 100, 6, 4], [90, 90, 26, 24]
    app.witness_revision = 7
    app.rows = harness.records
    app.rows.extend([{"event": "gpu-capture", "cycle": 0, "kind": kind,
        "frameIdentity": {"revision": revision}} for kind, revision in (("source",201), ("target",202))])
    app.rows.append({"event": "physical-target-regions", "cycle": 0, "contentXYWH": app.target_client})
    app.snapshot_observations["target-live"] = {"frame": {"outputDesktopXYWH": [0,0,1920,1080]}}
    app.window_observation = lambda hwnd: {"windowXYWH": app.target_client}
    app.target_desktop = np.zeros((4, 6, 4), np.uint8)
    app.endpoint_diagnostic_pixels = app.target_desktop.copy()
    app.target_pixel_regions[0] = {"clientMargin": [[5, 0, 6, 4]]}
    app.evaluate = lambda command: SimpleNamespace(toNumber=lambda: 3)
    app.finish_handoff = lambda: pytest.fail("Rejected identity cannot finish handoff")
    harness.namespace["audit"] = tmp_path
    attempts = []
    def native_probe(*args):
        attempts.append("submitted-readback")
        return np.zeros((1,4), np.uint8), np.zeros((1,4), np.uint8)
    def frame_probe(*args):
        attempts.append("frame-readback")
        return np.zeros((1,4), np.uint8)
    monkeypatch.setitem(sys.modules, "source_pixel_analysis", SimpleNamespace(
        composition_probe_coordinates=lambda *args: ([(5,3)], ["clientMargin"], {}),
        probe_gpu_endpoint_composition=native_probe, probe_gpu_live_frame=frame_probe,
        endpoint_composition_analysis=lambda *args: pytest.fail("Rejected revision cannot publish analysis")))
    identity = dict(witnessRevision=7, sourceFrameRevision=201, targetFrameRevision=202,
        snapshotRevision=8, hostGeneration=9, snapshotResourceIdentity=10,
        hostLeft=90, hostTop=90, hostWidth=26, hostHeight=24,
        sourceLeft=10, sourceTop=10, sourceWidth=6, sourceHeight=4,
        targetLeft=10, targetTop=10, targetWidth=6, targetHeight=4)
    exported = dict(revision=303, width=6, height=4)
    monkeypatch.setattr(submitted_surface_contract, "probe_identity", lambda *args, **kw: dict(identity))
    monkeypatch.setattr(submitted_surface_contract, "frame_identity", lambda *args: dict(exported))
    return identity, exported, attempts


@pytest.mark.parametrize("changes", [dict(witnessRevision=6), dict(sourceFrameRevision=199),
    dict(targetFrameRevision=200), dict(hostLeft=91), dict(hostTop=91),
    dict(hostWidth=25), dict(hostHeight=23), dict(sourceLeft=11), dict(sourceTop=11),
    dict(sourceWidth=5), dict(sourceHeight=3), dict(targetLeft=11), dict(targetTop=11),
    dict(targetWidth=5), dict(targetHeight=3)])
def test_endpoint_identity_must_match_the_transaction_before_any_pixel_readback(harness, monkeypatch, tmp_path, changes):
    identity, _, attempts = endpoint_identity_harness(harness, monkeypatch, tmp_path)
    identity.update(changes)
    with pytest.raises(RuntimeError, match="transaction"):
        harness.app.analyze_endpoint_frame({"client": harness.app.target_client, "size": [6,4], "frame": 303})
    assert attempts == [] and harness.app.diagnostic_texel_readbacks == 0
    assert not list(tmp_path.iterdir())
    assert harness.app.host == 101 and harness.app.frames == [201,202]


@pytest.mark.parametrize("changes", [dict(revision=201), dict(revision=202), dict(width=5), dict(height=3)])
def test_later_live_identity_cannot_alias_source_target_or_a_different_frame_extent(harness, monkeypatch, tmp_path, changes):
    _, exported, attempts = endpoint_identity_harness(harness, monkeypatch, tmp_path)
    exported.update(changes)
    with pytest.raises(RuntimeError, match="transaction"):
        harness.app.analyze_endpoint_frame({"client": harness.app.target_client, "size": [6,4], "frame": 303})
    assert attempts == [] and not list(tmp_path.iterdir())


@pytest.mark.parametrize("changed_field", ["snapshotRevision", "hostGeneration",
    "sourceFrameRevision", "targetFrameRevision", "witnessRevision", "snapshotResourceIdentity"])
def test_endpoint_revision_is_bracketed_and_changes_during_readback_never_publish_evidence(harness, monkeypatch, tmp_path, changed_field):
    import submitted_surface_contract
    identity, _, attempts = endpoint_identity_harness(harness, monkeypatch, tmp_path)
    calls = []
    def observed_identity(*args, **kwargs):
        calls.append("identity")
        return dict(identity) if len(calls) == 1 else {**identity, changed_field: identity[changed_field]+1}
    monkeypatch.setattr(submitted_surface_contract, "probe_identity", observed_identity)
    with pytest.raises(RuntimeError, match="revision changed"):
        harness.app.analyze_endpoint_frame({"client": harness.app.target_client, "size": [6,4], "frame": 303})
    assert calls == ["identity", "identity"]
    assert attempts == ["submitted-readback", "frame-readback", "frame-readback"]
    assert harness.app.diagnostic_texel_readbacks == 0
    assert not any(row["event"] == "endpoint-composition-analysis" for row in harness.records)
    assert not list(tmp_path.iterdir())
    assert harness.app.host == 101 and harness.app.frames == [201,202]


def test_post_input_observation_starts_after_accepted_pair_without_advancing_cycle(harness):
    app = harness.app
    harness.args.post_input_pixels = True
    app.current, app.target_client = {"command": 9.0}, [100, 100, 6, 4]
    app.input_release_seconds, app.input_witness = 10.1, object()
    app.window.update = lambda: harness.actions.append(("update-after-input",))
    app.observe_desktop = lambda *args, **kwargs: harness.actions.append(("observe-after-input", args, kwargs))
    app.input_witness_finished({"status": "PASS", "acceptedSeconds": 10.12, "reason": "owned pair consumed"})
    assert app.completed == 0 and app.input_witness is None
    assert harness.actions[0] == ("update-after-input",)
    requested = harness.actions[1][1]
    assert requested[0:3] == (app.target_client, "target-after-accepted-input", 10.25)
    assert requested[3]["witnessAbsent"] is True and requested[3]["live.clientXYWH"] == app.target_client
    assert harness.timer.calls == []
    harness.actions.clear()
    app.input_witness_finished({"status": "FAIL", "acceptedSeconds": None, "reason": "bounded timeout"})
    assert harness.actions == [] and app.completed == 0


def test_post_input_margin_difference_is_compared_in_complete_target_partition(harness):
    app = harness.app
    app.current, app.step = {"command": 9.0}, lambda: None
    source = np.zeros((8, 10, 4), np.uint8)
    target = np.zeros((4, 6, 4), np.uint8)
    after_input = target.copy()
    after_input[3, 5, 0] = 1
    app.source_desktop, app.target_desktop = source, target
    app.pixel_regions[0] = {"clientBody": [[0, 0, 10, 8]]}
    app.target_pixel_regions[0] = {"clientMargin": [[5, 0, 6, 4]]}
    app.window.isActive = lambda: True
    app.applicationState = lambda: SimpleNamespace(value=4)
    app.accepted_input_pixels_observed(after_input)
    assert app.completed == 1 and harness.timer.calls[0][0] == 200
    assert app.pixel_pairs[0][1] == "gpu-to-live-target-after-input-pixels"
    app.complete()
    analysis = next(row for row in harness.records if row["event"] == "physical-pixel-analysis")
    assert analysis["pixels"] == 24 and analysis["differentPixels"] == 1
    assert harness.context["failures"] == ["gpu-to-live-target-after-input-pixels: physical pixels differ"]


def test_failure_cleanup_restores_activation_after_reveal_unlock_and_native_host_destruction(harness):
    app = harness.app
    harness.args.single_owner_source = True
    app.input_was_enabled = True
    harness.context["failures"].append("retained fixture failure")
    app.source_foreground_before_transfer = True
    app.live_visibility_transferred = True
    app.window.show = lambda: harness.actions.append(("reveal-owned-live",))
    harness.namespace["user"] = SimpleNamespace(ShowWindow=lambda hwnd, mode:
        harness.actions.append(("native-owned-show", hwnd, mode)))
    def unlock():
        assert ("reveal-owned-live",) in harness.actions
        app.input_was_enabled = None
        harness.actions.append(("release-owned-input",))
    def restore(boundary):
        assert boundary == "input-restored"
        assert app.host is None and app.input_was_enabled is None
        assert harness.actions[-1] == ("release-frame", 202)
        harness.actions.append(("guarded-owned-activation",))
    app.unlock_input, app.restore_source_activation = unlock, restore
    app.complete()
    assert ("guarded-owned-activation",) in harness.actions
    assert harness.actions.index(("release-owned-input",)) < harness.actions.index(("destroy-host", 101))
    assert harness.actions.index(("destroy-host", 101)) < harness.actions.index(("guarded-owned-activation",))
    assert harness.actions.index(("release-frame", 202)) < harness.actions.index(("guarded-owned-activation",))


def test_normal_completed_handoff_cleanup_does_not_request_activation_twice(harness):
    app = harness.app
    harness.args.single_owner_source = True
    app.input_was_enabled = None
    app.host = None
    app.restore_source_activation = lambda boundary: pytest.fail("Released normal handoff must not request activation twice")
    app.complete()
