"""Recovery policy and ABI checks without opening a native window or WebEngine."""
import json
import logging
from pathlib import Path
import sys

import pytest
from PySide6.QtCore import QObject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
from backend import motion_settings
from backend import native_motion


@pytest.fixture
def local_motion(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(native_motion, "system_reduced_motion", lambda: False)
    return motion_settings.preference_path()


@pytest.mark.parametrize("mode", motion_settings.MODES)
def test_local_recovery_round_trip_without_data_or_qt_startup(local_motion, mode):
    motion_settings.write_mode(mode)
    assert motion_settings.read_mode() == mode
    assert list(local_motion.parent.iterdir()) == [local_motion]


@pytest.mark.parametrize("payload", [None, [], {}, {"engine": "single-clock"}, {"engine": "native-composition"}])
def test_diagnostic_engines_never_become_persisted_user_settings(local_motion, payload):
    local_motion.parent.mkdir(parents=True)
    local_motion.write_text(json.dumps(payload))
    assert motion_settings.read_mode() == "native"


def test_missing_and_corrupt_settings_default_to_native(local_motion):
    assert motion_settings.read_mode() == "native"
    local_motion.parent.mkdir(parents=True)
    local_motion.write_text("corrupt")
    assert motion_settings.read_mode() == "native"


def test_invalid_mode_does_not_overwrite_recovery(local_motion):
    motion_settings.write_mode("legacy")
    before = local_motion.read_bytes()
    with pytest.raises(ValueError):
        motion_settings.write_mode("diagnostic")
    assert local_motion.read_bytes() == before


def test_recovery_command_exits_before_any_bridge_load(local_motion):
    with pytest.raises(SystemExit) as exit_info:
        motion_settings.handle_motion_arguments(["CSPM.exe", "--set-motion-engine", "legacy"])
    assert exit_info.value.code == 0
    assert motion_settings.read_mode() == "legacy"


@pytest.mark.parametrize("mode", ["legacy", "reduced"])
def test_recovery_modes_do_not_even_attempt_native_loading(local_motion, mode):
    motion_settings.write_mode(mode)
    def forbidden(_):
        pytest.fail("Legacy/reduced selection attempted native loading")
    runtime = native_motion.NativeMotion(bridge_factory=forbidden)
    assert runtime.engine == mode
    assert not runtime.available
    assert runtime.reducedMotion == (mode == "reduced")


def test_os_reduced_motion_is_authoritative_over_native_default(local_motion, monkeypatch):
    monkeypatch.setattr(native_motion, "system_reduced_motion", lambda: True)
    def forbidden(_):
        pytest.fail("System reduced motion attempted native loading")
    runtime = native_motion.NativeMotion(bridge_factory=forbidden)
    assert runtime.engine == "native"
    assert runtime.reducedMotion and not runtime.layoutRepair


def test_bridge_unavailable_keeps_default_and_observes_legacy_fallback(local_motion, caplog):
    def missing(_):
        raise OSError("missing")
    runtime = native_motion.NativeMotion(bridge_factory=missing)
    window = QObject()
    window.setProperty("professionalWindowTransitionKind", "maximize")
    with caplog.at_level(logging.INFO, logger="motion"):
        assert not runtime.begin(window, 1, {}, {}, 1, 1)
    assert runtime.engine == "native"
    assert "used=legacy-fallback" in caplog.text
    assert "bridge-unavailable" in caplog.text
    assert runtime._transaction is None


def test_native_bridge_no_window_abi_and_null_rejection():
    path = native_motion.bridge_path()
    if not path.exists() or sys.platform != "win32":
        pytest.skip("Native bridge build required")
    bridge = native_motion.NativeBridge(path)
    assert bridge.dll.cspm_comp_abi_version() == 1
    assert bridge.dll.cspm_comp_status(None) & 16
    assert not bridge.dll.cspm_comp_create_from_frame_with_source_band(None, 0, 0, 0, 10, 10)
    assert bridge.error()
