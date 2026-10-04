"""Pure diagnostics-helper contracts; no fixture launch, Qt window or GPU.

Read and compile the inherited runner as text. Its private-data copying and
application startup are never executed by these checks.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "scripts/diagnostics"
sys.path.insert(0, str(DIAGNOSTICS))
SPEC = importlib.util.spec_from_file_location(
    "native_readiness_helpers_under_test", DIAGNOSTICS / "native_gpu_transition_spike.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
configure_fixture_source = MODULE.configure_fixture_source
import_render_target = MODULE.import_render_target
WORKSPACES = MODULE.WORKSPACES


def valid_result():
    return {"client": [0, 0, 1920, 1040], "size": [1920, 1040], "frame": object()}


@pytest.mark.parametrize("change,host", [
    ({"client": [1, 0, 1920, 1040]}, object()),
    ({"client": [0, 0, 1920, 1039]}, object()),
    ({"size": [1920, 1039]}, object()),
    ({"size": None}, object()),
    ({"frame": None}, object()),
    ({}, None),
])
def test_import_rejects_extent_or_missing_ownership_before_clock_or_native_call(change, host):
    result = {**valid_result(), **change}
    before = dict(result)
    calls = []
    with pytest.raises(RuntimeError, match="predetermined physical endpoint|owned host and GPU frame"):
        import_render_target(result, host, [0, 0, 1920, 1040],
                             lambda *args: calls.append(args),
                             lambda *args: calls.append(args),
                             clock=lambda: calls.append("clock"))
    assert calls == []
    assert result == before


def test_import_success_preserves_owned_handles_and_records_the_native_call_interval():
    result = valid_result()
    frame, host = result["frame"], object()
    observations = []
    ticks = iter((17.5, 17.507))

    def set_target(actual_host, actual_frame):
        observations.append((actual_host, actual_frame, result["targetImportStarted"]))
        assert "targetImportFinished" not in result
        return 1

    import_render_target(result, host, [0, 0, 1920, 1040], set_target,
                         lambda unused: pytest.fail("A successful import must not query an error"),
                         clock=lambda: next(ticks))
    assert observations == [(host, frame, 17.5)]
    assert result["frame"] is frame
    assert result["targetImported"] is True
    assert result["targetImportStarted"] == 17.5
    assert result["targetImportFinished"] == 17.507
    assert "targetImportError" not in result


def test_import_native_rejection_keeps_frame_owned_and_retains_failure_timing():
    result = valid_result()
    frame, host = result["frame"], object()
    calls = []
    ticks = iter((20.0, 20.020))

    def failure(actual_host):
        calls.append(actual_host)
        assert result["targetImported"] is False
        assert result["targetImportFinished"] == 20.020
        return "fixed content-transfer deadline exceeded"

    import_render_target(result, host, [0, 0, 1920, 1040], lambda *unused: 0,
                         failure, clock=lambda: next(ticks))
    assert calls == [host]
    assert result["frame"] is frame
    assert result["targetImportError"] == "fixed content-transfer deadline exceeded"
    assert result["targetImportStarted"] == 20.0


def test_import_exception_propagates_without_claiming_a_completed_native_import():
    result = valid_result()
    frame = result["frame"]

    def broken_setter(*unused):
        raise RuntimeError("native callback failed")

    with pytest.raises(RuntimeError, match="native callback failed"):
        import_render_target(result, object(), [0, 0, 1920, 1040], broken_setter,
                             lambda unused: pytest.fail("Failed call must propagate"), clock=lambda: 22.0)
    assert result["frame"] is frame
    assert result["targetImportStarted"] == 22.0
    assert "targetImported" not in result
    assert "targetImportFinished" not in result


def inherited_source():
    return (DIAGNOSTICS / "window_transition_probe.py").read_text(encoding="utf-8")


def startup_layout(source):
    tree = ast.parse(source)
    matches = [keyword.value for node in ast.walk(tree) if isinstance(node, ast.Call)
               for keyword in node.keywords if keyword.arg == "mainWindowLayout"]
    assert len(matches) == 1
    return ast.literal_eval(matches[0])


@pytest.mark.parametrize("direction", ["maximize", "restore"])
@pytest.mark.parametrize("workspace", sorted(WORKSPACES))
@pytest.mark.parametrize("size", [(700, 540), (1100, 760), (1550, 900)])
def test_actual_inherited_source_only_changes_disposable_startup_and_navigation(direction, workspace, size):
    source = inherited_source()
    configured = configure_fixture_source(source, direction, workspace, size)
    compile(configured, "<inherited diagnostic text only>", "exec")
    original_layout = startup_layout(source)
    layout = startup_layout(configured)
    assert layout == {**original_layout, "maximized": direction == "restore",
                      "width": size[0], "height": size[1]}
    route = WORKSPACES[workspace]
    if route:
        expected = f"option3OpenWorkspaceForTile({route[0]}, '{route[1]}', {{}})"
        assert configured.count(expected) == 1
        assert 'if not self.expected_tab:' in configured
    else:
        assert 'self.evaluate("true")' in configured
        assert 'if False:  # Home has no work tab.' in configured
        assert 'option3OpenWorkspaceForTile' not in configured
    # No target preparation, private-data source, or preservation guard changes.
    assert configured.count('shutil.copy2(') == source.count('shutil.copy2(')
    assert configured.count('requestCloseAnimation()') == source.count('requestCloseAnimation()')
    assert configured.count('workspace changed') == source.count('workspace changed')
    assert inherited_source() == source


@pytest.mark.parametrize("anchor", [
    'mainWindowLayout={"maximized": False, "hasExactRect": True,',
    '"width": 1100, "height": 760,',
    'self.evaluate("_probeWindow.mainContentRef.option3OpenWorkspaceForTile(3, \'D10\', {})")',
    'if not self.expected_tab:',
])
@pytest.mark.parametrize("problem", ["missing", "ambiguous"])
def test_fixture_transform_refuses_missing_or_ambiguous_anchors_without_writing(anchor, problem):
    source = inherited_source()
    assert source.count(anchor) == 1
    broken = source.replace(anchor, "# unavailable anchor", 1) if problem == "missing" else source + "\n" + anchor
    with pytest.raises(ValueError, match="unavailable or ambiguous"):
        configure_fixture_source(broken, "restore", "home", (1100, 760))
    assert inherited_source() == source


def test_workspace_choices_match_canonical_shell_routes_without_production_changes():
    pathways = (ROOT / "src/qml/standards/ModulePathways.js").read_text(encoding="utf-8")
    for node, label in (("A01", "Client Directory"), ("B01", "Time Docket Entry"),
                        ("D10", "Productivity & Utilization")):
        assert f'"id": "{node}", "label": "{label}"' in pathways
    assert WORKSPACES == {"productivity": (3, "D10"), "time-entry": (1, "B01"),
                          "client-directory": (0, "A01"), "invoice-preview": (2, "C03"), "home": None}
