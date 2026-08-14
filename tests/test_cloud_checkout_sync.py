from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from services.paths import AppPaths
from services.sync_service import SyncService


def _write_package(folder: Path, label: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    # CSPM's generated blank seed is below 50 KB.  A larger synthetic package
    # lets the service exercise the normal checked-out replica path.
    (folder / "CSPM.xlsm").write_bytes((f"CSPM-{label}|".encode("utf-8")) * 7000)
    (folder / "Dockets.xlsm").write_bytes((f"DOCKETS-{label}|".encode("utf-8")) * 1200)


def _service(tmp_path: Path, name: str, cloud: Path, local: Path) -> SyncService:
    return SyncService(
        AppPaths(
            root=tmp_path / f"runtime-{name}",
            override_data_dir=local,
            override_master_dir=cloud,
        )
    )


def test_checkout_blocks_second_machine_then_publishes_verified_release(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local_a = tmp_path / "local-a"
    local_b = tmp_path / "local-b"
    _write_package(cloud, "initial")

    first = _service(tmp_path, "a", cloud, local_a)
    checked_out = first.checkout_from_cloud()
    assert checked_out["ok"]
    assert (cloud / first.LEASE_FILE_NAME).is_file()
    assert (local_a / "CSPM.xlsm").read_bytes() == (cloud / "CSPM.xlsm").read_bytes()

    second = _service(tmp_path, "b", cloud, local_b)
    blocked = second.checkout_from_cloud()
    assert not blocked["ok"]
    assert blocked["status"] == "checkout-held"
    with pytest.raises(PermissionError):
        second.assert_write_lease()

    _write_package(local_a, "published")
    published = first.publish_and_release()
    assert published["ok"]
    assert published["status"] == "push"
    release = published["release"]
    release_dir = Path(release["releasePath"])
    assert (release_dir / "release.json").is_file()
    assert (release_dir / "CSPM.xlsm").read_bytes() == (local_a / "CSPM.xlsm").read_bytes()
    assert not (cloud / first.LEASE_FILE_NAME).exists()
    assert (cloud / "CSPM.xlsm").read_bytes() == (local_a / "CSPM.xlsm").read_bytes()

    checked_out_second = second.checkout_from_cloud()
    assert checked_out_second["ok"]
    assert (local_b / "CSPM.xlsm").read_bytes() == (cloud / "CSPM.xlsm").read_bytes()
    assert second.publish_and_release()["ok"]


def test_publish_refuses_cloud_change_after_checkout_and_preserves_both_copies(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "base")
    service = _service(tmp_path, "a", cloud, local)
    assert service.checkout_from_cloud()["ok"]

    _write_package(local, "local-change")
    _write_package(cloud, "cloud-change")  # Simulates an out-of-band cloud edit.
    cloud_before_publish = (cloud / "CSPM.xlsm").read_bytes()
    local_before_publish = (local / "CSPM.xlsm").read_bytes()

    result = service.publish_and_release()
    assert not result["ok"]
    assert result["status"] == "conflict"
    assert (cloud / "CSPM.xlsm").read_bytes() == cloud_before_publish
    assert (local / "CSPM.xlsm").read_bytes() == local_before_publish
    assert not (cloud / service.LEASE_FILE_NAME).exists()


def test_unknown_existing_difference_is_a_conflict_not_an_automatic_copy(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "cloud")
    _write_package(local, "local")
    service = _service(tmp_path, "a", cloud, local)

    result = service.checkout_from_cloud()
    assert not result["ok"]
    assert result["status"] == "conflict"
    assert (cloud / "CSPM.xlsm").read_bytes() != (local / "CSPM.xlsm").read_bytes()
    assert not (cloud / service.LEASE_FILE_NAME).exists()


def test_fresh_blank_seed_package_pulls_the_complete_cloud_pair(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "cloud")
    local.mkdir()
    # The local Dockets template need not match the cloud.  A small generated
    # CSPM seed marks the complete pair as a fresh replica.
    (local / "CSPM.xlsm").write_bytes(b"new practice seed")
    (local / "Dockets.xlsm").write_bytes(b"template" * 9000)
    service = _service(tmp_path, "a", cloud, local)

    result = service.checkout_from_cloud()
    assert result["ok"]
    assert result["status"] == "pull"
    assert (local / "CSPM.xlsm").read_bytes() == (cloud / "CSPM.xlsm").read_bytes()
    assert (local / "Dockets.xlsm").read_bytes() == (cloud / "Dockets.xlsm").read_bytes()
    assert service.publish_and_release()["ok"]


def test_existing_cloud_setup_never_overwrites_a_different_local_package(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "cloud")
    _write_package(local, "local")
    service = _service(tmp_path, "a", cloud, local)

    result = service.initialize_shared_source(local)
    assert not result["ok"]
    assert result["status"] == "conflict"
    assert (cloud / "CSPM.xlsm").read_bytes() != (local / "CSPM.xlsm").read_bytes()


def test_repository_write_guard_is_available_only_during_checkout(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "base")
    service = _service(tmp_path, "a", cloud, local)

    with pytest.raises(PermissionError):
        service.assert_write_lease()
    assert service.checkout_from_cloud()["ok"]
    service.assert_write_lease()
    assert service.publish_and_release()["ok"]
    with pytest.raises(PermissionError):
        service.assert_write_lease()


def test_same_installation_dead_process_checkout_is_recovered_automatically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "base")
    first = _service(tmp_path, "a", cloud, local)
    stale_lease = {
        "schemaVersion": 1,
        "machineId": first._machine_identity(),
        "checkoutId": "dead-checkout",
        "processId": 424242,
        "computerName": socket.gethostname(),
        "checkedOutAtUtc": "2026-08-14T00:00:00+00:00",
        "purpose": "CSPM exclusive workbook write checkout",
    }
    (cloud / first.LEASE_FILE_NAME).write_text(json.dumps(stale_lease), encoding="utf-8")

    restarted = _service(tmp_path, "a", cloud, local)
    monkeypatch.setattr(restarted, "_local_process_is_running", lambda _pid: False)

    acquired = restarted._acquire_checkout_lease()

    assert acquired["ok"]
    assert acquired["status"] == "checked-out"
    recovery = acquired["recovery"]
    assert recovery["status"] == "recovered-abandoned-checkout"
    audit_path = Path(recovery["recoveryAuditPath"])
    assert audit_path.is_file()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["abandonedLease"] == stale_lease
    assert json.loads((cloud / first.LEASE_FILE_NAME).read_text(encoding="utf-8"))["checkoutId"] == restarted._checkout_id
    assert restarted._release_checkout_lease()["ok"]


def test_auto_recovery_never_removes_another_installations_dead_process_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "base")
    owner = _service(tmp_path, "owner", cloud, local)
    other = _service(tmp_path, "other", cloud, tmp_path / "other-local")
    foreign_lease = {
        "schemaVersion": 1,
        "machineId": owner._machine_identity(),
        "checkoutId": "foreign-dead-checkout",
        "processId": 424242,
        "computerName": socket.gethostname(),
        "checkedOutAtUtc": "2026-08-14T00:00:00+00:00",
        "purpose": "CSPM exclusive workbook write checkout",
    }
    (cloud / owner.LEASE_FILE_NAME).write_text(json.dumps(foreign_lease), encoding="utf-8")
    monkeypatch.setattr(other, "_local_process_is_running", lambda _pid: False)

    blocked = other._acquire_checkout_lease()

    assert not blocked["ok"]
    assert blocked["status"] == "checkout-held"
    assert json.loads((cloud / owner.LEASE_FILE_NAME).read_text(encoding="utf-8")) == foreign_lease


def test_auto_recovery_does_not_reclaim_a_same_installation_live_process_checkout(tmp_path: Path) -> None:
    cloud = tmp_path / "cloud"
    local = tmp_path / "local"
    _write_package(cloud, "base")
    owner = _service(tmp_path, "a", cloud, local)
    live_lease = {
        "schemaVersion": 1,
        "machineId": owner._machine_identity(),
        "checkoutId": "live-checkout",
        "processId": os.getpid(),
        "computerName": socket.gethostname(),
        "checkedOutAtUtc": "2026-08-14T00:00:00+00:00",
        "purpose": "CSPM exclusive workbook write checkout",
    }
    (cloud / owner.LEASE_FILE_NAME).write_text(json.dumps(live_lease), encoding="utf-8")
    restarted = _service(tmp_path, "a", cloud, local)

    blocked = restarted._acquire_checkout_lease()

    assert not blocked["ok"]
    assert blocked["status"] == "checkout-held"
    assert json.loads((cloud / owner.LEASE_FILE_NAME).read_text(encoding="utf-8")) == live_lease
