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
                              input_witness=False, single_owner_source=False, source_unlocked=False)
    source = ast.parse((DIAGNOSTICS / "native_gpu_transition_spike.py").read_text(encoding="utf-8"))
    classes = [node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "NativeSpike"]
    assert len(classes) == 1
    names = {"configure_witness", "refresh_witness", "observe_desktop", "poll_desktop_observation",
             "record_pixel_regions", "compare_pixels", "source_removal_observation", "complete",
             "begin_input_witness", "input_witness_finished", "defer_source_visibility",
             "resume_live_host_hidden", "transfer_source_visibility", "after_source_coverage",
             "restore_source_activation", "source_reference_observed", "after_source_transfer_observed",
             "raise_source_visibility"}
    methods = [copy.deepcopy(node) for node in classes[0].body
               if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {method.name for method in methods} == names
    for method in methods:
        method.decorator_list = []
    namespace = {"args": options, "dll": native, "QTimer": timer, "context": context,
        "ctypes": ctypes, "wintypes": wintypes, "os": os, "hashlib": hashlib,
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
        composition_probe=None, controlled_backdrop=None,
        input_witness=None, input_release_seconds=None,
        live_visibility_transferred=False,
        source_foreground_before_transfer=False, source_active_before_transfer=False,
        source_before_resume=None,
        analyze_pixels=compare_pixels, physical_regions=physical_regions,
        lock_input=lambda: actions.append(("lock-input",)),
        unlock_input=lambda: actions.append(("unlock-input",)),
        quit=lambda: actions.append(("quit",)),
        evaluate=lambda command: actions.append(("evaluate", command)),
        record=lambda event, **values: records.append({"event": event, **values}),
        fail=lambda category, error: context["failures"].append(category + ": " + error))
    for name in names:
        setattr(app, name, MethodType(namespace[name], app))
    return SimpleNamespace(app=app, timer=timer, context=context, actions=actions,
                           records=records, dll=native, args=options, namespace=namespace)


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
    app.window_observation = lambda hwnd: {"foreground": True}
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
    assert before_proof[1][1] == "source-transfer-before-resume"
    assert before_proof[1][3]["live.visible"] is False and before_proof[1][3]["qtOpacity"] == 1
    app.raise_source_visibility = lambda: setattr(app, "source_reorder_return_seconds", 10.28)
    app.after_source_transfer_observed(app.source_desktop.copy())
    assert visible["live"] and not app.live_visibility_transferred
    assert ("opacity", 0) in harness.actions and ("native-show", 123, 4) in harness.actions
    assert app.witness_revision == 11
    proof = [action for action in harness.actions if action[0] == "observe"][-1]
    assert proof[1][:3] == (physical, "source-transfer", 10.3)
    assert proof[1][3]["qtOpacity"] == 0 and "live.foregroundHwnd" not in proof[1][3]
    assert proof[2] == {"phase": 1}


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
def test_activation_restoration_is_conditional_and_api_success_is_separate_from_observed_state(harness, was_foreground):
    app = harness.app
    app.source_foreground_before_transfer = was_foreground
    app.window.requestActivate = lambda: harness.actions.append(("request-activate",))
    app.window.isActive = lambda: False
    app.window_observation = lambda hwnd: {"foreground": False, "foregroundHwnd": 999}
    harness.namespace["user"] = SimpleNamespace(SetForegroundWindow=lambda hwnd: harness.actions.append(("activate", hwnd)) or 1)
    app.restore_source_activation("live-host-revealed")
    if was_foreground:
        assert harness.actions == [("request-activate",), ("activate", 123)]
        assert harness.records[-1]["apiAccepted"] is True
        assert harness.records[-1]["observedForeground"] is False
    else:
        assert harness.actions == [] and harness.records[-1]["event"] == "source-activation-not-requested"


@pytest.mark.parametrize("rejection", ["never-foreground", "other-foreground", "changed-foreground",
    "foreign-process", "foreign-thread", "unknown-thread", "disabled", "still-locked", "invalid", None])
def test_unlock_focus_restores_only_still_foreground_owned_enabled_gui_thread(harness, monkeypatch, rejection):
    app = harness.app
    app.source_foreground_before_transfer = rejection != "never-foreground"
    app.input_was_enabled = True if rejection == "still-locked" else None
    app.window.isActive = lambda: False
    app.window.requestActivate = lambda: pytest.fail("Unlock must not retry desktop activation")
    app.window_observation = lambda hwnd: {"foregroundHwnd": 999 if rejection == "other-foreground" else hwnd}
    focus = {"hwnd": 0}
    posts = []

    def identify(hwnd, pointer):
        pointer._obj.value = os.getpid() + int(rejection == "foreign-process")
        return 0 if rejection == "unknown-thread" else (99 if rejection == "foreign-thread" else 77)

    def set_focus(hwnd):
        previous = focus["hwnd"]
        focus["hwnd"] = hwnd
        posts.append(hwnd)
        return previous

    user = SimpleNamespace(
        GetForegroundWindow=FakeFunction(lambda: 999 if rejection == "changed-foreground" else 123),
        GetWindowThreadProcessId=FakeFunction(identify),
        IsWindowEnabled=FakeFunction(lambda hwnd: rejection != "disabled"),
        GetFocus=FakeFunction(lambda: focus["hwnd"]), SetFocus=FakeFunction(set_focus),
        SetForegroundWindow=FakeFunction(lambda hwnd: pytest.fail("Unlock must not change desktop foreground")))
    kernel = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: 77))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    harness.namespace.update(user=user, isValid=lambda window: rejection != "invalid")
    app.restore_source_activation("input-restored")
    if rejection:
        assert posts == []
        assert harness.records[-1]["event"] in ("source-focus-not-requested", "source-activation-not-requested")
    else:
        assert posts == [123] and focus["hwnd"] == 123
        assert harness.records[-1]["event"] == "source-focus-restoration"
        assert harness.records[-1]["focusBeforeHwnd"] == 0
        assert harness.records[-1]["apiPreviousFocusHwnd"] == 0
        assert harness.records[-1]["focusAfterHwnd"] == 123
        assert harness.records[-1]["nativeFocusOwned"] is True
        assert harness.records[-1]["qtActive"] is False
    assert harness.timer.calls == []


def test_focus_api_outcome_does_not_qualify_the_independent_input_witness(harness, monkeypatch):
    app = harness.app
    app.source_foreground_before_transfer = True
    app.input_was_enabled = None
    app.window.isActive = lambda: False
    app.window_observation = lambda hwnd: {"foregroundHwnd": hwnd}
    def identify(hwnd, pointer):
        pointer._obj.value = os.getpid()
        return 77
    user = SimpleNamespace(GetForegroundWindow=FakeFunction(lambda: 123),
        GetWindowThreadProcessId=FakeFunction(identify), IsWindowEnabled=lambda hwnd: True,
        GetFocus=FakeFunction(lambda: 999), SetFocus=FakeFunction(lambda hwnd: 0))
    kernel = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: 77))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    harness.namespace["user"] = user
    app.restore_source_activation("input-restored")
    assert harness.records[-1]["nativeFocusOwned"] is False
    assert app.completed == 0 and harness.timer.calls == []


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
        assert harness.records[-1]["api"] == "native owner-thread HWND_TOP source ordering"
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
