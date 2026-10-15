"""Linux recovery probes and refusal paths never modify workbook fixtures."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from backend import data_verification, native_candidate


ROOT = Path(__file__).resolve().parents[1]


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for key in ["CSPM_LOCAL_DATA_DIR", "CSPM_MASTER_DATA_DIR", "LOCALAPPDATA"]:
        monkeypatch.delenv(key, raising=False)
    profile = tmp_path / "profile"
    data, cloud = tmp_path / "replica", tmp_path / "cloud"
    profile.mkdir()
    data.mkdir()
    cloud.mkdir()
    for folder in [data, cloud]:
        for name in ["CSPM.xlsm", "Dockets.xlsm"]:
            (folder / name).write_bytes(b"synthetic fixture; must remain byte identical")
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(profile))
    monkeypatch.setenv("CSPM_DATA_DIR", str(profile))
    monkeypatch.setenv(data_verification.ENVIRONMENT_KEY, "0")
    monkeypatch.setattr(native_candidate, "_profile", None)
    (profile / "user_settings.json").write_text(json.dumps(dict(localDataDir=str(data), masterDataDir=str(cloud))))
    spec = importlib.util.spec_from_file_location("cspm_recovery_safety_fixture", ROOT / "scripts/cspm_recovery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.original_process_probe = module._is_cspm_running
    monkeypatch.setattr(module, "_is_cspm_running", lambda: False)
    return module


def test_source_recovery_uses_saved_replica_cloud_and_durable_profile(recovery, tmp_path: Path):
    assert recovery.PATHS.data_dir() == tmp_path / "replica"
    assert recovery.PATHS.master_data_dir() == tmp_path / "cloud"
    assert recovery.PATHS.backups_snapshots_dir() == tmp_path / "profile/backups/CSPM/snapshots"


def test_frozen_recovery_does_not_use_extraction_folder_for_live_data(recovery, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "temporary-bundle"), raising=False)
    paths = recovery._load_paths(tmp_path / "temporary-bundle")
    assert paths.data_dir() == tmp_path / "replica"
    assert paths.master_data_dir() == tmp_path / "cloud"
    assert paths.backups_snapshots_dir() == tmp_path / "profile/backups/CSPM/snapshots"


def test_linux_source_backup_default_tracks_settings_profile(recovery, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CSPM_DATA_DIR")
    paths = recovery._load_paths(tmp_path / "source")
    assert paths.backups_snapshots_dir() == tmp_path / "profile/backups/CSPM/snapshots"


def test_unreadable_settings_never_fall_back_to_a_different_data_folder(recovery, tmp_path: Path):
    (tmp_path / "profile/user_settings.json").write_text("broken json")
    with pytest.raises(RuntimeError, match="settings are unreadable"):
        recovery._load_paths(ROOT)


def test_path_approval_rejects_a_sibling_with_the_same_prefix(recovery, tmp_path: Path):
    assert recovery._is_path_approved(tmp_path / "replica/state/restore_journal.json")
    assert not recovery._is_path_approved(tmp_path / "replica-other/CSPM.xlsm")


@pytest.mark.skipif(os.name == "nt", reason="POSIX advisory lock")
def test_posix_advisory_lock_probe_is_read_only(recovery, tmp_path: Path):
    import fcntl

    target = tmp_path / "lock-probe.dat"
    target.write_bytes(b"non-workbook probe")
    before = target.read_bytes()
    with target.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert recovery._is_file_exclusively_locked(target)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    assert not recovery._is_file_exclusively_locked(target)
    assert target.read_bytes() == before


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux open descriptor ownership")
def test_linux_probe_detects_an_ordinary_open_without_advisory_lock(recovery, tmp_path: Path):
    target = tmp_path / "open-probe.dat"
    target.write_bytes(b"non-workbook probe")
    child = subprocess.Popen([sys.executable, "-u", "-c",
                              "import sys; handle=open(sys.argv[1], 'rb'); print('ready', flush=True); sys.stdin.read()",
                              str(target)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        assert recovery._is_file_exclusively_locked(target)
        assert target.read_bytes() == b"non-workbook probe"
    finally:
        child.communicate("", timeout=5)
    assert not recovery._is_file_exclusively_locked(target)


def test_libreoffice_marker_blocks_recovery(recovery, tmp_path: Path):
    marker = tmp_path / "replica/.~lock.CSPM.xlsm#"
    marker.write_text("synthetic office lock")
    assert any("LibreOffice" in reason for reason in recovery.check_locks())


@pytest.mark.parametrize("marker_payload", ['{"machineId":"another-pc"}', "unreadable marker"])
def test_restore_cannot_skip_active_or_unreadable_cloud_checkout(recovery, tmp_path: Path, marker_payload: str):
    marker = tmp_path / "cloud/.cspm_checkout.json"
    marker.write_text(marker_payload)
    before = tree_bytes(tmp_path)
    engine = recovery.RecoveryEngine()
    result = engine.perform_restore(tmp_path / "not-a-package", {}, skip_locks=True)
    assert result["status"] == "failed_safe"
    assert "checkout" in result["message"]
    assert tree_bytes(tmp_path) == before


def test_interrupted_rollback_refuses_active_checkout_before_any_write(recovery, tmp_path: Path):
    (tmp_path / "cloud/.cspm_checkout.json").write_text('{"machineId":"another-pc"}')
    before = tree_bytes(tmp_path)
    engine = recovery.RecoveryEngine()
    journal = dict(current_phase="CSPM_REPLACED", destinations={
        "CSPM.xlsm": dict(target_path=str(tmp_path / "replica/CSPM.xlsm"))})
    result = engine.resume_interrupted_transaction(journal)
    assert result["status"] == "failed_safe"
    assert tree_bytes(tmp_path) == before


def test_inherited_read_only_policy_blocks_restore_without_checkout_or_journal(recovery, tmp_path: Path):
    data_verification.configure(settings={"readOnlyVerification": True})
    before = tree_bytes(tmp_path)
    result = recovery.RecoveryEngine().perform_restore(tmp_path / "not-a-package", {})
    assert result["status"] == "failed_safe"
    assert "read-only" in result["message"]
    assert tree_bytes(tmp_path) == before


def test_recovery_checkout_is_exclusive_and_released_without_workbook_changes(recovery, tmp_path: Path):
    before = tree_bytes(tmp_path)
    marker = tmp_path / "cloud/.cspm_checkout.json"
    with recovery._exclusive_recovery_checkout(tmp_path / "replica"):
        assert marker.is_file()
        assert recovery._shared_checkout_locks() == []
        payload = json.loads(marker.read_text())
        assert payload["purpose"] == "CSPM external recovery exclusive checkout"
    assert not marker.exists()
    assert tree_bytes(tmp_path) == before


def test_recovery_never_removes_an_ownership_changed_marker(recovery, tmp_path: Path):
    marker = tmp_path / "cloud/.cspm_checkout.json"
    with recovery._exclusive_recovery_checkout(tmp_path / "replica"):
        marker.write_text('{"machineId":"another-pc","checkoutId":"foreign"}')
        assert recovery._shared_checkout_locks()
    assert json.loads(marker.read_text())["checkoutId"] == "foreign"


@pytest.mark.parametrize("foreign", ["ordinary-writer", "another-computer", "another-replica"])
def test_abandoned_recovery_never_reclaims_a_foreign_checkout(recovery, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: str):
    payload = dict(purpose="CSPM external recovery exclusive checkout", computerName=socket.gethostname(),
                   recoveryReplica=str(tmp_path / "replica"), checkoutId="a" * 32, processId=424242)
    if foreign == "ordinary-writer": payload["purpose"] = "CSPM exclusive workbook write checkout"
    if foreign == "another-computer": payload["computerName"] = "another-computer"
    if foreign == "another-replica": payload["recoveryReplica"] = str(tmp_path / "other")
    marker = tmp_path / "cloud/.cspm_checkout.json"
    marker.write_text(json.dumps(payload))
    monkeypatch.setattr(recovery.SyncService, "_local_process_is_running", lambda _pid: False)
    before = tree_bytes(tmp_path)
    recovery._recover_abandoned_recovery_checkout(tmp_path / "replica")
    assert tree_bytes(tmp_path) == before


def test_dead_same_workstation_recovery_checkout_is_audited_without_workbook_writes(recovery, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    marker = tmp_path / "cloud/.cspm_checkout.json"
    payload = dict(purpose="CSPM external recovery exclusive checkout", computerName=socket.gethostname(),
                   recoveryReplica=str(tmp_path / "replica"), checkoutId="a" * 32, processId=424242)
    marker.write_text(json.dumps(payload))
    originals = {name: (tmp_path / "replica" / name).read_bytes() for name in ["CSPM.xlsm", "Dockets.xlsm"]}
    monkeypatch.setattr(recovery.SyncService, "_local_process_is_running", lambda _pid: False)
    recovery._recover_abandoned_recovery_checkout(tmp_path / "replica")
    assert not marker.exists()
    audits = list((tmp_path / "replica/state").glob("abandoned_recovery_checkout_*.json"))
    assert len(audits) == 1
    assert json.loads(audits[0].read_text())["abandonedCheckout"] == payload
    assert all((tmp_path / "replica" / name).read_bytes() == data for name, data in originals.items())


def test_interrupted_transaction_cannot_target_a_different_replica(recovery, tmp_path: Path):
    before = tree_bytes(tmp_path)
    result = recovery.RecoveryEngine().resume_interrupted_transaction(dict(current_phase="CSPM_REPLACED", destinations={
        "CSPM.xlsm": dict(target_path=str(tmp_path / "cloud/CSPM.xlsm"))}))
    assert result["status"] == "failed_safe"
    assert tree_bytes(tmp_path) == before


def test_status_does_not_prompt_or_modify_checkout_journal_or_workbooks(recovery, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(sys, "argv", ["CSPM_Recovery", "--status"])
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("Status must not ask for input"))
    before = tree_bytes(tmp_path)
    recovery.cli_main()
    output = capsys.readouterr().out
    status = json.loads(output[output.index("{"):])
    assert status["data_dir"] == str(tmp_path / "replica")
    assert isinstance(status["locks"], list)
    assert tree_bytes(tmp_path) == before
