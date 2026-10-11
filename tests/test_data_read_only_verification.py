"""Verification never acquires a writer lease or mutates workbook packages."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import os
import sys

import pytest
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))

from backend import data_verification
from backend.app_controller import AppController
from repositories.excel_repo import ExcelRepo
from repositories.ap_workbook_repository import APWorkbookRepository
from services.paths import AppPaths
from services.sync_service import SyncService


@pytest.fixture(autouse=True)
def isolated_policy(monkeypatch):
    monkeypatch.setenv(data_verification.ENVIRONMENT_KEY, "0")


def package(directory, payload=b"verified data"):
    directory.mkdir(parents=True)
    for name in SyncService._FILES:
        (directory / name).write_bytes(payload + name.encode())


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("matching", [True, False])
def test_verification_observes_hashes_without_checkout_copy_or_state(tmp_path, matching):
    cloud, local = tmp_path / "cloud", tmp_path / "local"
    package(cloud)
    package(local, b"verified data" if matching else b"different data")
    marker = cloud / SyncService.LEASE_FILE_NAME
    marker.write_text('{"machineId":"another-machine","checkoutId":"owned-elsewhere"}')
    before = tree_bytes(tmp_path)
    service = SyncService(AppPaths(tmp_path / "runtime", local, cloud),
                          machine_identity_file=tmp_path / "machine.json", read_only_verification=True)
    result = service.checkout_from_cloud()
    assert result["ok"] is matching
    assert result["readOnly"]
    assert result["sourceVerified"] is matching
    assert bool(result["sourceIdentity"]) is matching
    assert not service._lease_owned
    assert service.publish_and_release()["status"] == "read-only-verification"
    assert not service.initialize_shared_source()["ok"]
    with pytest.raises(PermissionError, match="verification is read-only"):
        service.assert_write_lease()
    assert tree_bytes(tmp_path) == before


def test_verification_does_not_release_even_an_existing_owned_lease(tmp_path):
    cloud, local = tmp_path / "cloud", tmp_path / "local"
    package(cloud)
    package(local)
    service = SyncService(AppPaths(tmp_path / "runtime", local, cloud),
                          machine_identity_file=tmp_path / "machine.json")
    assert service.checkout_from_cloud()["ok"]
    before = tree_bytes(tmp_path)
    data_verification.configure(["CSPM.exe", "--verify-data-read-only"])
    assert service.publish_and_release()["readOnly"]
    assert tree_bytes(tmp_path) == before


def test_local_only_cannot_bypass_verification_and_policy_is_inherited(tmp_path):
    data_verification.configure(settings={"readOnlyVerification": True})
    data_verification.configure(settings={"readOnlyVerification": False})
    assert os.environ[data_verification.ENVIRONMENT_KEY] == "1"
    service = SyncService(AppPaths(tmp_path))
    assert service.checkout_from_cloud()["readOnly"]
    with pytest.raises(PermissionError):
        service.assert_write_lease()
    # The startup child constructs its own repository with no SyncService.
    repo = ExcelRepo(AppPaths(tmp_path))
    with pytest.raises(PermissionError):
        repo._safe_save(MagicMock(), tmp_path / "CSPM.xlsm")
    assert not (tmp_path / "CSPM.xlsm").exists()


@pytest.mark.parametrize("method,args", [
    ("create_bill", ({},)), ("update_bill", ({},)),
    ("delete_bill", ("bill",)), ("post_payment", ({},)),
    ("reverse_payment", ("payment", "reversal", "reason")),
    ("update_payment_metadata", ("payment", {})),
])
def test_accounts_payable_write_paths_cannot_bypass_policy(tmp_path, method, args):
    workbook = tmp_path / "CSPM.xlsm"
    workbook.write_bytes(b"must not be opened or changed")
    repo = APWorkbookRepository(workbook)
    data_verification.configure(settings={"readOnlyVerification": True})
    with pytest.raises(PermissionError):
        getattr(repo, method)(*args)
    assert workbook.read_bytes() == b"must not be opened or changed"


@pytest.mark.parametrize("migration", [True, False])
def test_startup_schema_probe_never_saves_and_required_migration_fails(tmp_path, migration):
    data_verification.configure(settings={"readOnlyVerification": True})
    workbook = tmp_path / "CSPM.xlsm"
    workbook.write_bytes(b"current workbook")
    repo = SimpleNamespace(schema_requires_migration=MagicMock(return_value=migration),
                           ensure_schema=MagicMock())
    controller = SimpleNamespace(_paths=AppPaths(tmp_path.parent, tmp_path), _excel_repo=repo,
                                 _report_failure=MagicMock(), _create_project_snapshot=MagicMock())
    if migration:
        with pytest.raises(PermissionError, match="no migration"):
            AppController._bootstrap_workbook_schema(controller)
    else:
        AppController._bootstrap_workbook_schema(controller)
    repo.ensure_schema.assert_not_called()
    controller._create_project_snapshot.assert_not_called()


def test_setting_is_latched_before_controller_checkout_and_labels_source(tmp_path, monkeypatch):
    application = QCoreApplication.instance() or QCoreApplication([])
    runtime = tmp_path / "runtime"
    data, cloud = tmp_path / "data", tmp_path / "cloud"
    package(data)
    package(cloud)
    runtime.mkdir()
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("CSPM_DATA_DIR", str(runtime))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-profile"))
    import json
    (runtime / "user_settings.json").write_text(json.dumps(dict(
        localDataDir=str(data), masterDataDir=str(cloud), readOnlyVerification=True,
        autoBackupMinutes=0, runAtStartup=False)))
    controller = AppController(paths=AppPaths(ROOT))
    try:
        assert controller.dataSourceStatus == "governed-source"
        assert "read-only verification" in controller.dataSourceStatusLabel
        assert not (cloud / SyncService.LEASE_FILE_NAME).exists()
        assert not controller._sync_service.state_file.exists()
        assert controller._sync_service.push_to_master()["readOnly"]
    finally:
        controller._auto_backup_timer.stop()
        application.processEvents()


def test_real_schema_and_metadata_reads_do_not_write_replica_state(tmp_path):
    import shutil
    data = tmp_path / "data"
    data.mkdir()
    for name in SyncService._FILES:
        shutil.copyfile(ROOT / "src/templates" / name, data / name)
    before = tree_bytes(data)
    data_verification.configure(settings={"readOnlyVerification": True})
    repo = ExcelRepo(AppPaths(ROOT, data))
    assert repo.schema_requires_migration() is False
    assert repo.ensure_schema()["readOnly"]
    repo.warm_startup_metadata_cache()
    assert tree_bytes(data) == before


def test_reloading_settings_updates_paths_before_checkout_and_invalidates_source(tmp_path, monkeypatch):
    application = QCoreApplication.instance() or QCoreApplication([])
    runtime = tmp_path / "runtime"
    old_data, new_data, cloud = tmp_path / "old", tmp_path / "new", tmp_path / "cloud"
    for directory in (old_data, new_data, cloud):
        package(directory)
    runtime.mkdir()
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("CSPM_DATA_DIR", str(runtime))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-profile"))
    import json
    settings = dict(localDataDir=str(old_data), masterDataDir=str(cloud),
                    readOnlyVerification=True, autoBackupMinutes=0, runAtStartup=False)
    (runtime / "user_settings.json").write_text(json.dumps(settings))
    controller = AppController(paths=AppPaths(ROOT))
    try:
        assert controller.dataSourceStatus == "governed-source"
        settings["localDataDir"] = str(new_data)
        settings["masterDataDir"] = ""
        controller._apply_settings_payload({"loaded": settings}, emit_theme_signal=False)
        assert controller._paths.data_dir() == new_data
        assert controller._paths.master_data_dir() is None
        assert controller.dataSourceStatus == "unverified-local"
        assert "cloud freshness unverified" not in controller.dataSourceStatusLabel
        controller.save_settings()
        assert json.loads((runtime / "user_settings.json").read_text())["readOnlyVerification"]
        controller._governed_source_verified = True
        controller._governed_source_identity = "test"
        controller.masterDataDir = str(cloud)
        assert controller.dataSourceStatus == "unverified-local"
        assert controller._governed_source_identity == ""
        controller._governed_source_verified = True
        controller._governed_source_identity = "test"
        controller.localDataDir = str(old_data)
        assert controller.dataSourceStatus == "unverified-local"
        assert controller._governed_source_identity == ""
        with pytest.raises(PermissionError, match="separate local replica"):
            controller.localDataDir = str(cloud)
    finally:
        controller._auto_backup_timer.stop()
        application.processEvents()


def test_verification_rejects_authority_as_runtime_folder_before_services_exist(tmp_path, monkeypatch):
    import json
    data = tmp_path / "governed"
    package(data)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("CSPM_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("CSPM_DATA_DIR", str(runtime))
    (runtime / "user_settings.json").write_text(json.dumps(dict(
        localDataDir=str(data), masterDataDir=str(data), readOnlyVerification=True)))
    before = tree_bytes(data)
    with pytest.raises(PermissionError, match="separate local replica"):
        AppController(paths=AppPaths(ROOT))
    assert tree_bytes(data) == before


def test_failed_replica_verification_clears_stale_identity_and_blocks_readiness(tmp_path):
    data_verification.configure(settings={"readOnlyVerification": True})
    controller = SimpleNamespace(
        _governed_source_verified=True, _governed_source_identity="stale",
        _paths=AppPaths(ROOT, tmp_path / "local", tmp_path / "governed"),
        _sync_service=SimpleNamespace(pull_from_master=lambda: {"ok": False, "sourceVerified": False}),
        dataSourceStatusChanged=MagicMock(), toast=MagicMock(),
    )
    with pytest.raises(PermissionError, match="could not match"):
        AppController._checkout_shared_data(controller, "test")
    assert controller._governed_source_verified is False
    assert controller._governed_source_identity == ""
    controller.dataSourceStatusChanged.emit.assert_called_once()
