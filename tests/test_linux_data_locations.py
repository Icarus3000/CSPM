from __future__ import annotations

from pathlib import Path
import json

import pytest

from backend import data_verification, native_candidate
from services import data_locations
from services.data_locations import (
    apply_environment_data_settings,
    discover_onedrive_data_dirs,
    environment_data_path,
    fresh_replica_can_checkout,
)
from services.paths import AppPaths
from services.sync_service import SyncService


@pytest.fixture(autouse=True)
def isolated_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ["CSPM_LOCAL_DATA_DIR", "CSPM_MASTER_DATA_DIR", "CSPM_MACHINE_ID_FILE", "LOCALAPPDATA", "XDG_CONFIG_HOME", data_verification.ENVIRONMENT_KEY]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CSPM_DATA_DIR", str(tmp_path / "profile"))
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(tmp_path / "profile"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))
    monkeypatch.setattr(native_candidate, "_profile", None)


def write_pair(folder: Path) -> None:
    folder.mkdir(parents=True)
    for name in SyncService._FILES:
        (folder / name).write_bytes(f"synthetic-{name}".encode())


def test_launcher_selectors_override_saved_paths_and_survive_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", str(tmp_path / "local replica"))
    monkeypatch.setenv("CSPM_MASTER_DATA_DIR", str(tmp_path / "OneDrive/CSPM_Shared_Data"))
    saved = {"localDataDir": "C:/Old/Local", "masterDataDir": "C:/Old/OneDrive", "readOnlyVerification": True, "theme": "Dark"}
    resolved = apply_environment_data_settings(saved)
    assert resolved["localDataDir"] == str(tmp_path / "local replica")
    assert resolved["masterDataDir"] == str(tmp_path / "OneDrive/CSPM_Shared_Data")
    assert resolved["readOnlyVerification"] is True
    assert resolved["theme"] == "Dark"
    assert saved["localDataDir"] == "C:/Old/Local"
    assert apply_environment_data_settings(resolved) == resolved
    paths = AppPaths(tmp_path / "code")
    assert paths.data_dir() == Path(resolved["localDataDir"])
    assert paths.master_data_dir() == Path(resolved["masterDataDir"])


def test_candidate_policy_stays_cloud_disabled_with_launcher_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", str(tmp_path / "production"))
    monkeypatch.setenv("CSPM_MASTER_DATA_DIR", str(tmp_path / "cloud"))
    monkeypatch.setattr(native_candidate, "_profile", tmp_path / "candidate")
    resolved = apply_environment_data_settings({})
    resolved.update(native_candidate.settings_override())
    assert resolved["masterDataDir"] == ""
    assert resolved["localDataDir"] == str(tmp_path / "candidate/working/data")
    paths = AppPaths(tmp_path / "code")
    assert paths.master_data_dir() is None
    assert paths.data_dir() == tmp_path / "candidate/working/data"


@pytest.mark.skipif(data_locations.os.name == "nt", reason="Linux selector validation")
@pytest.mark.parametrize("value", ["C:/Windows/Data", "C:\\Windows\\Data", "\\\\server\\share", "relative/data"])
def test_linux_launcher_rejects_incompatible_or_relative_paths(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", value)
    with pytest.raises(ValueError):
        environment_data_path("CSPM_LOCAL_DATA_DIR")


def test_native_onedrive_discovery_honors_sync_root_and_preserves_ambiguity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    first = home / "OneDrive/CSPM_Shared_Data"
    second = home / "Business Drive/CSPM_Shared_Data"
    write_pair(first)
    write_pair(second)
    config = home / ".config/onedrive/config"
    config.parent.mkdir(parents=True)
    config.write_text('sync_dir = "~/Business Drive"\nthreads = "4"\n')
    assert discover_onedrive_data_dirs(home) == [first, second]
    monkeypatch.setattr(data_locations, "_is_fuse_mount", lambda folder: "Business Drive" in str(folder))
    assert discover_onedrive_data_dirs(home) == [first]
    (first / "Dockets.xlsm").write_bytes(b"")
    assert discover_onedrive_data_dirs(home) == []


def test_discovery_deduplicates_sync_root_without_reading_other_config_fields(tmp_path: Path) -> None:
    home = tmp_path / "home"
    folder = home / "OneDrive/CSPM_Shared_Data"
    write_pair(folder)
    config = home / ".config/onedrive/config"
    config.parent.mkdir(parents=True)
    config.write_text('sync_dir = "~/OneDrive" # local synced data\nunused = "not a path"\n')
    assert discover_onedrive_data_dirs(home) == [folder]


def test_fresh_replica_bootstrap_never_accepts_partial_or_same_folder(tmp_path: Path) -> None:
    cloud, local = tmp_path / "cloud", tmp_path / "local"
    write_pair(cloud)
    assert fresh_replica_can_checkout(local, cloud)
    assert not fresh_replica_can_checkout(cloud, cloud)
    assert not fresh_replica_can_checkout(local, None)
    local.mkdir()
    (local / "CSPM.xlsm").write_bytes(b"preserve this existing partial package")
    assert not fresh_replica_can_checkout(local, cloud)
    (local / "CSPM.xlsm").unlink()
    (local / "Dockets.xlsm").symlink_to(tmp_path / "unavailable workbook")
    assert not fresh_replica_can_checkout(local, cloud)


def test_linux_source_and_bundle_share_identity_with_distinct_runtime_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = SyncService(AppPaths(tmp_path / "source"))
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(tmp_path / "package-runtime"))
    packaged = SyncService(AppPaths(tmp_path / "bundle"))
    assert source._machine_identity_file == packaged._machine_identity_file
    assert source._machine_identity() == packaged._machine_identity()
    assert source._machine_identity_file.parent == tmp_path / "home/.cspm_data"


def test_fresh_linux_replica_checkout_blocks_second_session_and_publishes_pair(tmp_path: Path) -> None:
    cloud, local, other = tmp_path / "cloud", tmp_path / "local", tmp_path / "other"
    write_pair(cloud)
    first = SyncService(AppPaths(tmp_path / "source", local, cloud), machine_identity_file=tmp_path / "first.json")
    assert fresh_replica_can_checkout(local, cloud)
    assert first.checkout_from_cloud()["ok"]
    second = SyncService(AppPaths(tmp_path / "source", other, cloud), machine_identity_file=tmp_path / "second.json")
    assert second.checkout_from_cloud()["status"] == "checkout-held"
    with pytest.raises(PermissionError):
        second.assert_write_lease()
    (local / "CSPM.xlsm").write_bytes(b"synthetic new workstation save")
    assert first.publish_and_release()["ok"]
    assert second.checkout_from_cloud()["ok"]
    assert (other / "CSPM.xlsm").read_bytes() == (local / "CSPM.xlsm").read_bytes()
    assert second.publish_and_release()["ok"]


def test_controller_bootstraps_fresh_replica_before_ap_repository_and_keeps_environment_on_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import QCoreApplication
    from backend.app_controller import AppController

    application = QCoreApplication.instance() or QCoreApplication([])
    cloud, local = tmp_path / "cloud", tmp_path / "local"
    write_pair(cloud)
    runtime = tmp_path / "profile"
    runtime.mkdir()
    saved = dict(localDataDir="C:/previous-machine/data", masterDataDir="C:/previous-machine/OneDrive",
                 autoBackupMinutes=0, runAtStartup=False, keepTrayAlive=False, theme="Dark")
    settings = runtime / "user_settings.json"
    settings.write_text(json.dumps(saved))
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", str(local))
    monkeypatch.setenv("CSPM_MASTER_DATA_DIR", str(cloud))
    controller = AppController(paths=AppPaths(Path(__file__).resolve().parents[1]))
    try:
        assert controller._paths.data_dir() == local
        assert controller._paths.master_data_dir() == cloud
        assert controller._ap_repository is not None
        assert all((local / name).read_bytes() == (cloud / name).read_bytes() for name in SyncService._FILES)
        controller._prime_deferred_theme_preference()
        controller._apply_settings_payload({"loaded": saved}, emit_theme_signal=False)
        assert controller._paths.data_dir() == local
        assert controller._paths.master_data_dir() == cloud
        controller._sync_service.assert_write_lease()
    finally:
        controller._auto_backup_timer.stop()
        assert controller._sync_service._release_checkout_lease()["ok"]
        application.processEvents()


def test_controller_fresh_replica_cannot_bootstrap_over_another_session_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import QCoreApplication
    from backend.app_controller import AppController

    application = QCoreApplication.instance() or QCoreApplication([])
    cloud, local, other = tmp_path / "cloud", tmp_path / "local", tmp_path / "other"
    write_pair(cloud)
    owner = SyncService(AppPaths(tmp_path / "code", local, cloud), machine_identity_file=tmp_path / "owner.json")
    assert owner.checkout_from_cloud()["ok"]
    marker_before = (cloud / SyncService.LEASE_FILE_NAME).read_bytes()
    runtime = tmp_path / "profile"
    runtime.mkdir(exist_ok=True)
    (runtime / "user_settings.json").write_text(json.dumps(dict(autoBackupMinutes=0, runAtStartup=False)))
    monkeypatch.setenv("CSPM_LOCAL_DATA_DIR", str(other))
    monkeypatch.setenv("CSPM_MASTER_DATA_DIR", str(cloud))
    try:
        with pytest.raises(PermissionError, match="checked out"):
            AppController(paths=AppPaths(Path(__file__).resolve().parents[1]))
        assert not other.exists()
        assert (cloud / SyncService.LEASE_FILE_NAME).read_bytes() == marker_before
    finally:
        assert owner._release_checkout_lease()["ok"]
        application.processEvents()
