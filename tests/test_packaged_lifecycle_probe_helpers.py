"""Safe checks for the frozen smoke's preparation boundary; never launch CSPM."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packaged_lifecycle_probe", ROOT / "scripts/diagnostics/packaged_lifecycle_repair_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def prepared(tmp_path):
    package, profile, master = (tmp_path / name for name in ("package", "profile", "governed"))
    local = profile / "data"
    for directory in (package, profile, master, local):
        directory.mkdir(exist_ok=True)
    for name in probe.WORKBOOKS:
        (local / name).write_bytes(name.encode() + b" governed content")
        (master / name).write_bytes((local / name).read_bytes())
    settings = dict(localDataDir=str(local), masterDataDir=str(master), readOnlyVerification=True)
    (profile / "user_settings.json").write_text(json.dumps(settings))
    return package, profile, local, master, settings


def test_preparation_reads_exact_pair_and_never_modifies_profile_or_workbooks(tmp_path):
    package, profile, local, master, _ = prepared(tmp_path)
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    _, selected, governed, observation = probe.prepared_profile(profile, package)
    assert selected == local and governed == master
    assert observation["datasetIdentity"] == probe.pair_identity(observation["localHashes"])
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
    (local / "CSPM.xlsm").write_bytes(b"unverified change")
    with pytest.raises(ValueError, match="does not match"):
        probe.prepared_profile(profile, package)


def test_unprotected_or_package_local_profiles_are_rejected_before_launch(tmp_path):
    package, profile, _, _, settings = prepared(tmp_path)
    settings["readOnlyVerification"] = False
    (profile / "user_settings.json").write_text(json.dumps(settings))
    with pytest.raises(ValueError, match="readOnlyVerification"):
        probe.prepared_profile(profile, package)
    with pytest.raises(ValueError, match="outside the package"):
        probe.prepared_profile(package / "profile", package)


def test_launch_environment_drops_inherited_runtime_and_qt_overrides(tmp_path, monkeypatch):
    _, profile, _, _, _ = prepared(tmp_path)
    monkeypatch.setenv("CSPM_NATIVE_CANDIDATE", "unexpected")
    monkeypatch.setenv("CSPM_LOG_DIR", "unrelated")
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "unexpected")
    monkeypatch.setenv("PYTHONPATH", "unrelated")
    environment = probe.isolated_environment(profile)
    assert "CSPM_NATIVE_CANDIDATE" not in environment
    assert "QTWEBENGINE_CHROMIUM_FLAGS" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["CSPM_LOG_DIR"] == str(profile / "logs")
    assert environment["CSPM_VERIFY_DATA_READ_ONLY"] == "1"
    assert environment["LOCALAPPDATA"] == str(profile / "local")
