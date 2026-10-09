"""Safety contracts for the opt-in manual adapter; no real application window."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/diagnostics"))
from manual_native_fixture import (bridge_path, checked_child, fixture_source,
                                   prepare_profile, shell_source, validate_manual_options,
                                   permitted_briefing_worker)


def options(**changes):
    values = dict(duration_ms=350, blend_start_ms=240, gui_delay_ms=0, endpoint_hold_ms=0,
                  intrinsic_only=True, single_owner_source=True, native_created_source_band=True,
                  render_target_import=True, layout_repair=True, activation_repair=True,
                  workspace="time-entry", first_direction="maximize")
    return SimpleNamespace(**(values | changes))


def test_only_current_collector_free_configuration_is_accepted(monkeypatch):
    monkeypatch.delenv("CSPM_EXPERIMENTAL_REDUCED_MOTION", raising=False)
    validate_manual_options(options())


@pytest.mark.parametrize("change", [dict(pixels=True), dict(endpoint_pixels=True),
    dict(prepared_target=True), dict(native_call_trace=True), dict(gui_delay_ms=80),
    dict(duration_ms=351), dict(blend_start_ms=241), dict(single_owner_source=False),
    dict(native_created_source_band=False), dict(render_target_import=False), dict(workspace="home")])
def test_manual_selector_rejects_bypass_or_collector_options(change):
    with pytest.raises(ValueError):
        validate_manual_options(options(**change))


def test_reduced_motion_is_not_weakened(monkeypatch):
    monkeypatch.setenv("CSPM_EXPERIMENTAL_REDUCED_MOTION", "1")
    with pytest.raises(ValueError, match="Reduced motion"):
        validate_manual_options(options())


def test_missing_or_escaped_bridge_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="no fallback"):
        bridge_path(tmp_path, "missing.dll")
    with pytest.raises(ValueError):
        bridge_path(tmp_path, "../../outside.dll")


def test_valid_bridge_must_be_in_governed_outputs(tmp_path):
    directory = tmp_path / "outputs/native_cleanroom"
    directory.mkdir(parents=True)
    dll = directory / "example.dll"
    dll.write_bytes(b"test-only")
    assert bridge_path(tmp_path, dll.name) == dll.resolve()


def test_disposable_paths_reject_siblings_and_root(tmp_path):
    assert checked_child(tmp_path, tmp_path / "profile") == tmp_path / "profile"
    for path in (tmp_path, tmp_path.parent / "other", tmp_path / ".." / "outside"):
        with pytest.raises(ValueError):
            checked_child(tmp_path, path)


def test_disposable_bootstrap_has_no_user_profile_or_automatic_cycles():
    source = (ROOT / "scripts/diagnostics/window_transition_probe.py").read_text(encoding="utf-8")
    result = fixture_source(source, ROOT, ROOT / "logs/test", ROOT / "logs/test/disposable_profile")
    assert "LOCALAPPDATA" not in result
    assert "shutil.copy2" not in result
    assert "QTimer.singleShot(120000, self.timeout)" not in result


def test_ordinary_controls_retain_guards_and_never_reach_production():
    original = (ROOT / "src/qml/DetachedShellWindow.qml").read_text(encoding="utf-8")
    patched = shell_source(original)
    start = patched.index("    function toggleWindowMaximize()")
    end = patched.index("    function beginHeaderDrag", start)
    toggle = patched[start:end]
    assert toggle.index('animationPhase !== "settled"') < toggle.index("manualNativeFixture.requestToggle()")
    assert toggle.index("userMoveInProgress") < toggle.index("manualNativeFixture.requestToggle()")
    assert toggle.index("return manualNativeFixture.requestToggle()") < toggle.index("restoreFromMaximized")
    assert "manualNativeFixture.rejectAlternateCommand(); return false;" in patched
    assert "CSPM NATIVE MOTION VISUAL TEST — DISPOSABLE" in patched
    assert "manualNativeFixture" not in original


def test_mirror_patch_fails_closed_when_architecture_changes():
    with pytest.raises(ValueError):
        shell_source("Window {}")


def test_profile_seeds_synthetic_population_and_all_state_paths(tmp_path, monkeypatch):
    # Changes to environment must not leak out of this focused unit test.
    for name in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOME", "TEMP", "TMP",
                 "CSPM_RUNTIME_DIR", "CSPM_DATA_DIR", "CSPM_LOG_DIR", "CSPM_EXPORT_DIR",
                 "CSPM_MACHINE_ID_FILE", "CSPM_EXECUTABLE_ROOT", "PYTHONPYCACHEPREFIX",
                 "QTWEBENGINE_DICTIONARIES_PATH", "OneDrive", "OneDriveConsumer",
                 "OneDriveCommercial", "CSPM_PIXEL_DEPENDENCIES", "CSPM_WRITE_BYTECODE"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    monkeypatch.setattr(sys, "pycache_prefix", sys.pycache_prefix)
    profile, environment = prepare_profile(ROOT, tmp_path, (960, 650))
    assert all(Path(path).is_relative_to(tmp_path) for path in environment.values())
    settings = json.loads((profile / "user_settings.json").read_text())
    assert settings["appStyle"] == "Professional"
    assert settings["masterDataDir"] == ""
    assert settings["keepTrayAlive"] is False
    from openpyxl import load_workbook
    workbook = load_workbook(profile / "local/CSPM.xlsm", read_only=True)
    for sheet in ("Clients", "Matters", "TimeEntries"):
        rows = list(workbook[sheet].values)
        assert sum(str(row[0]).startswith("VISUAL-") for row in rows) == 3
    workbook.close()


def test_io_guard_denies_external_reads_writes_registry_and_actions(tmp_path):
    # Audit hooks cannot be removed: run this contract in its own process.
    audit = tmp_path / "owned"
    audit.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic forbidden path")
    code = '''import sys,pathlib
sys.path.insert(0, sys.argv[1])
from manual_native_fixture import install_io_guard
owned=pathlib.Path(sys.argv[2]); outside=pathlib.Path(sys.argv[3])
install_io_guard(owned, owned)
(owned / "allowed.txt").write_text("owned")
denied=0
for action in (lambda: outside.read_text(), lambda: outside.write_text("no"),
               lambda: sys.audit("winreg.SetValue", 0, "test", 0, "test"),
               lambda: sys.audit("subprocess.Popen", "test", [], None, None)):
    try: action()
    except PermissionError: denied+=1
assert denied==4
'''
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts/diagnostics"),
                             str(audit), str(outside)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert outside.read_text() == "synthetic forbidden path"


def test_only_owned_synthetic_briefing_child_is_allowed(tmp_path):
    root = tmp_path / "source"
    audit = root / "logs/owned"
    data = audit / "startup/data"
    data.mkdir(parents=True)
    (data / "CSPM.xlsm").write_bytes(b"synthetic")
    request, result = data.parent / "request.json", data.parent / "result.json"
    request.write_text(json.dumps({"root": str(root), "dataDir": str(data)}))
    command = [sys.executable, str(root / "src/python/main.py"), "--startup-briefing-worker",
               str(request), str(result)]
    assert permitted_briefing_worker(root, audit, sys.executable, command)
    if sys.platform == "win32":
        assert permitted_briefing_worker(root, audit, None, subprocess.list2cmdline(command))
    assert not permitted_briefing_worker(root, audit, sys.executable, command + ["extra"])
    assert not permitted_briefing_worker(root, audit, sys.executable, command[:2] + ["--other"] + command[3:])
    request.write_text(json.dumps({"root": str(root), "dataDir": str(tmp_path / "outside")}))
    assert not permitted_briefing_worker(root, audit, sys.executable, command)
