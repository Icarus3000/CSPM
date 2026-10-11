"""Deployment safety checks use synthetic files and never launch an application."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy_native_motion_release.py"
SPEC = importlib.util.spec_from_file_location("native_motion_deployment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "assert_idle", lambda *roots: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("CSPM_RUNTIME_DIR", raising=False)
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "CSPM.exe").write_bytes(b"OLD-SYNTHETIC-RUNTIME")
    (installed / "data").mkdir()
    (installed / "data" / "CSPM.xlsm").write_bytes(b"PRIVATE-SYNTHETIC-DATA")
    (installed / "user_settings.json").write_text('{"existing": true}')
    package = tmp_path / "package"
    package.mkdir()
    (package / "CSPM.exe").write_bytes(b"NEW-SYNTHETIC-RUNTIME")
    return installed, package, tmp_path / "rollback"


def test_snapshot_omits_datasets_and_never_overwrites_a_rollback(deployment):
    installed, _, rollback = deployment
    MODULE.snapshot(installed, rollback)
    assert not (rollback / "package" / "data").exists()
    assert not (rollback / "package" / "user_settings.json").exists()
    assert (rollback / "configuration" / "installation" / "user_settings.json").is_file()
    assert MODULE.verify_snapshot(rollback)["datasetsCopied"] is False
    with pytest.raises(FileExistsError):
        MODULE.snapshot(installed, rollback)


def test_install_refuses_missing_tampered_or_wrong_rollback(deployment):
    installed, package, rollback = deployment
    with pytest.raises(FileNotFoundError):
        MODULE.install(package, installed, rollback)
    MODULE.snapshot(installed, rollback)
    (rollback / "package" / "CSPM.exe").write_bytes(b"TAMPERED")
    with pytest.raises(ValueError, match="hash verification"):
        MODULE.install(package, installed, rollback)
    assert (installed / "CSPM.exe").read_bytes() == b"OLD-SYNTHETIC-RUNTIME"


def test_install_and_restore_preserve_data_settings_and_both_runtime_generations(deployment):
    installed, package, rollback = deployment
    MODULE.snapshot(installed, rollback)
    MODULE.install(package, installed, rollback)
    assert (installed / "CSPM.exe").read_bytes() == b"NEW-SYNTHETIC-RUNTIME"
    assert (installed / "data" / "CSPM.xlsm").read_bytes() == b"PRIVATE-SYNTHETIC-DATA"
    assert (installed / "user_settings.json").read_text() == '{"existing": true}'
    result = MODULE.restore(rollback, installed)
    assert (installed / "CSPM.exe").read_bytes() == b"OLD-SYNTHETIC-RUNTIME"
    assert (Path(result["preservedNewerRuntime"]) / "package" / "CSPM.exe").read_bytes() == b"NEW-SYNTHETIC-RUNTIME"
    assert MODULE.verify_snapshot(rollback)["datasetsCopied"] is False
    assert json.loads(MODULE._motion_path().read_text())["engine"] == "legacy"


def test_unapproved_dataset_is_rejected_even_inside_template_directory(deployment):
    _, package, _ = deployment
    templates = package / "_internal" / "src" / "templates"
    templates.mkdir(parents=True)
    (templates / "CSPM.xlsm").write_bytes(b"UNAPPROVED")
    with pytest.raises(ValueError, match="unapproved"):
        MODULE.validate_package(package)


def test_approved_seed_templates_are_allowed_but_existing_data_is_unchanged(deployment):
    installed, package, rollback = deployment
    templates = package / "_internal" / "src" / "templates"
    templates.mkdir(parents=True)
    template = templates / "CSPM.xlsm"
    template.write_bytes(b"GOVERNED-SYNTHETIC-TEMPLATE")
    (templates / "template_approval.json").write_text(json.dumps(dict(templates=[
        dict(approved_filename="CSPM.xlsm", human_approval_status="APPROVED", sha256=MODULE.sha256(template))])))
    (package / "data").mkdir()
    (package / "data" / "CSPM.xlsm").write_bytes(template.read_bytes())
    MODULE.validate_package(package)
    MODULE.snapshot(installed, rollback)
    MODULE.install(package, installed, rollback)
    assert (installed / "data" / "CSPM.xlsm").read_bytes() == b"PRIVATE-SYNTHETIC-DATA"
    assert not (rollback / "package" / "data").exists()


def test_process_guard_rejects_only_matching_package_process(monkeypatch, tmp_path):
    package = tmp_path / "package"
    monkeypatch.setattr(MODULE.sys, "platform", "win32")
    class Result:
        stdout = json.dumps([dict(Name="CSPM.exe", ProcessId=123,
                                  ExecutablePath=str(package / "CSPM.exe"))])
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(RuntimeError, match="PID 123"):
        MODULE.assert_idle(package)
    MODULE.assert_idle(tmp_path / "other-package")


def test_package_and_rollback_must_not_overlap(deployment):
    installed, _, _ = deployment
    with pytest.raises(ValueError, match="overlap"):
        MODULE.snapshot(installed, installed / "rollback")


def test_candidate_marker_cannot_enter_normal_installation(deployment):
    _, package, _ = deployment
    (package / "native-motion-candidate.json").write_text('{}')
    with pytest.raises(ValueError, match="candidate configuration"):
        MODULE.validate_package(package)


def test_snapshot_rejects_unexpected_dataset_without_creating_rollback(deployment):
    installed, _, rollback = deployment
    (installed / "private.sqlite").write_bytes(b"PRIVATE-SYNTHETIC-DATA")
    with pytest.raises(ValueError, match="Unexpected dataset"):
        MODULE.snapshot(installed, rollback)
    assert not rollback.exists()


def test_empty_process_result_is_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE.sys, "platform", "win32")
    class Result:
        stdout = "\r\n"
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: Result())
    MODULE.assert_idle(tmp_path)
