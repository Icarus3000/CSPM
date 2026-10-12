"""Launcher verification scope, data identity and inherited read-only behavior."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("governed_readonly_launcher", ROOT / "scripts/launch_governed_readonly.py")
LAUNCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCHER)


@pytest.fixture
def configuration(tmp_path, monkeypatch):
    package, profile, local, master = [tmp_path / name for name in ("package", "profile", "local", "governed")]
    for folder in (package, profile, local, master):
        folder.mkdir()
    (package / "_internal/native").mkdir(parents=True)
    (package / "CSPM.exe").write_bytes(b"synthetic executable")
    (package / "_internal/native/cspm_native_motion.dll").write_bytes(b"synthetic native")
    (package / "_internal/other-runtime.qml").write_bytes(b"synthetic runtime asset")
    pair = {}
    for name in LAUNCHER.PAIR_NAMES:
        contents = ("synthetic " + name).encode()
        for folder in (local, master):
            (folder / name).write_bytes(contents)
        pair[name] = hashlib.sha256(contents).hexdigest().upper()
    release = dict(schemaVersion=2, sourceSha="a" * 40, sourceStatus="clean", sourceDirty=False,
                   buildTimestampUtc="2026-10-12T16:00:00+00:00", version="2.4.0",
                   candidateProfileRequired=False, defaultMotionEngine="native",
                   nativeDllSha256=LAUNCHER.sha(package / "_internal/native/cspm_native_motion.dll"))
    (package / "_internal/release-provenance.json").write_text(json.dumps(release))
    manifest = master / ".cspm_releases/synthetic/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(dict(releaseId="synthetic", files=pair)))
    settings = dict(readOnlyVerification=True, localDataDir=str(local), masterDataDir=str(master))
    (profile / "user_settings.json").write_text(json.dumps(settings))
    payload = dict(schemaVersion=1, package=str(package), profile=str(profile), readOnlyVerification=True,
                   sourceSha=release["sourceSha"], releaseProvenance=release,
                   executableSha256=LAUNCHER.sha(package / "CSPM.exe"), nativeDllSha256=release["nativeDllSha256"],
                   runtime=LAUNCHER.runtime_manifest(package), localReplica=str(local), governedSource=str(master),
                   pairHashes=pair, datasetIdentity=hashlib.sha256("|".join(pair[name] for name in LAUNCHER.PAIR_NAMES).encode("ascii")).hexdigest()[:12].upper(),
                   releaseManifest=str(manifest), releaseManifestSha256=LAUNCHER.sha(manifest), releaseId="synthetic")
    path = profile / "deployment.private.json"
    path.write_text(json.dumps(payload))
    locked = []
    @contextmanager
    def protection(path):
        locked.append(path)
        try:
            yield
        finally:
            locked.remove(path)
    monkeypatch.setattr(LAUNCHER, "protected_read", protection)
    return path, payload, locked


def test_ordinary_verification_reads_only_critical_runtime_files_and_all_pair_hashes(configuration, monkeypatch):
    path, payload, locked = configuration
    touched = []
    original = LAUNCHER.sha
    def sha(path):
        touched.append(path)
        return original(path)
    monkeypatch.setattr(LAUNCHER, "sha", sha)
    monkeypatch.setattr(LAUNCHER, "runtime_manifest", lambda *_: pytest.fail("Normal launch performed a full runtime scan"))
    timing = {}
    LAUNCHER.verified_configuration(path, timings=timing)
    runtime_paths = [item for item in touched if item.is_relative_to(Path(payload["package"]))]
    assert {item.name for item in runtime_paths} == {"CSPM.exe", "cspm_native_motion.dll"}
    for folder in ("localReplica", "governedSource"):
        assert all(Path(payload[folder]) / name in touched for name in LAUNCHER.PAIR_NAMES)
    assert not locked, "Shared protection handles must be released before the manual session"
    assert set(timing) == {"runtimeIdentitySeconds", "governedDataSeconds", "configurationVerificationSeconds"}
    assert all(value >= 0 for value in timing.values())


def test_explicit_audit_checks_every_resource_and_reports_its_separate_cost(configuration):
    path, payload, _ = configuration
    timing = {}
    LAUNCHER.verified_configuration(path, audit_runtime=True, timings=timing)
    assert timing["runtimeAuditSeconds"] >= 0
    (Path(payload["package"]) / "_internal/other-runtime.qml").write_bytes(b"changed other resource")
    with pytest.raises(ValueError, match="runtime resources differ"):
        LAUNCHER.verified_configuration(path, audit_runtime=True)


@pytest.mark.parametrize("relative, message", [
    ("CSPM.exe", "executable changed"),
    ("_internal/native/cspm_native_motion.dll", "native bridge changed"),
    ("_internal/release-provenance.json", "release provenance differs"),
])
def test_changed_launch_identity_is_refused(configuration, relative, message):
    path, payload, _ = configuration
    item = Path(payload["package"]) / relative
    if item.suffix == ".json":
        identity = json.loads(item.read_text())
        identity["sourceSha"] = "b" * 40
        item.write_text(json.dumps(identity))
    else:
        item.write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match=message):
        LAUNCHER.verified_configuration(path)


@pytest.mark.parametrize("folder", ["localReplica", "governedSource"])
def test_workbook_hash_is_never_replaced_by_a_timestamp_or_cache(configuration, folder):
    path, payload, _ = configuration
    item = Path(payload[folder]) / "CSPM.xlsm"
    before = item.stat()
    changed = bytearray(item.read_bytes())
    changed[0] ^= 1
    item.write_bytes(changed)
    import os
    os.utime(item, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(ValueError, match="local or shared pair changed"):
        LAUNCHER.verified_configuration(path)


@pytest.mark.parametrize("marker", [".cspm_checkout.json", ".cspm_checkout_recovering_synthetic", "~$CSPM.xlsm"])
def test_writer_or_recovery_markers_require_review(configuration, marker):
    path, payload, _ = configuration
    (Path(payload["governedSource"]) / marker).write_bytes(b"synthetic marker")
    with pytest.raises(ValueError, match="checkout requires review|Excel writer"):
        LAUNCHER.verified_configuration(path)


@pytest.mark.parametrize("change", ["deployment-readonly", "profile-readonly", "selectors", "modified-source", "release-manifest"])
def test_configuration_data_or_build_policy_changes_are_refused(configuration, change):
    path, payload, _ = configuration
    if change == "deployment-readonly":
        payload["readOnlyVerification"] = False
        path.write_text(json.dumps(payload))
    elif change in {"profile-readonly", "selectors"}:
        settings_file = Path(payload["profile"]) / "user_settings.json"
        settings = json.loads(settings_file.read_text())
        settings["readOnlyVerification" if change == "profile-readonly" else "localDataDir"] = False if change == "profile-readonly" else payload["governedSource"]
        settings_file.write_text(json.dumps(settings))
    elif change == "modified-source":
        payload["releaseProvenance"]["sourceStatus"] = "modified"
        payload["releaseProvenance"]["sourceDirty"] = True
        (Path(payload["package"]) / "_internal/release-provenance.json").write_text(json.dumps(payload["releaseProvenance"]))
        path.write_text(json.dumps(payload))
    else:
        Path(payload["releaseManifest"]).write_text("{}")
    with pytest.raises(ValueError):
        LAUNCHER.verified_configuration(path)


def test_normal_environment_preserves_motion_profile_and_enforces_inherited_readonly(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ordinary-appdata"))
    monkeypatch.setenv("CSPM_VERIFY_DATA_READ_ONLY", "0")
    monkeypatch.setenv("CSPM_LOW_PERF", "1")
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "synthetic override")
    monkeypatch.setenv("PYTHONPATH", "synthetic override")
    environment = LAUNCHER.normal_environment(tmp_path / "profile")
    assert environment["CSPM_VERIFY_DATA_READ_ONLY"] == "1"
    assert environment["LOCALAPPDATA"] == str(tmp_path / "ordinary-appdata")
    assert environment["CSPM_RUNTIME_DIR"] == str(tmp_path / "profile")
    assert "CSPM_LOW_PERF" not in environment and "QTWEBENGINE_CHROMIUM_FLAGS" not in environment
    assert "PYTHONPATH" not in environment


def test_active_session_is_refused_before_verification_or_launch(configuration, monkeypatch):
    path, _, _ = configuration
    @contextmanager
    def mutex():
        yield
    monkeypatch.setattr(LAUNCHER, "exclusive_launcher", mutex)
    monkeypatch.setattr(LAUNCHER, "active_cspm_sessions", lambda: [{"name": "CSPM.exe", "processId": 1}])
    monkeypatch.setattr(LAUNCHER, "verified_configuration", lambda *_a, **_k: pytest.fail("Configuration should not run"))
    monkeypatch.setattr(sys, "argv", ["launcher", "--check-only", "--configuration", str(path)])
    assert LAUNCHER.main() == 1
    report = json.loads(next((path.parent / "launch-reports").glob("*.json")).read_text())
    assert report["ok"] is False and report["publicationAllowed"] is False


def test_check_only_has_truthful_verification_scope_and_timings(configuration, monkeypatch):
    path, _, _ = configuration
    @contextmanager
    def mutex():
        yield
    monkeypatch.setattr(LAUNCHER, "exclusive_launcher", mutex)
    monkeypatch.setattr(LAUNCHER, "active_cspm_sessions", lambda: [])
    monkeypatch.setattr(sys, "argv", ["launcher", "--check-only", "--configuration", str(path)])
    assert LAUNCHER.main() == 0
    report = json.loads(next((path.parent / "launch-reports").glob("*.json")).read_text())
    assert report["launched"] is False and report["runtimeVerification"] == "executable-native-provenance"
    assert report["completeRuntimeAuditRequested"] is False
    assert "preflightSeconds" in report["timings"] and "runtimeAuditSeconds" not in report["timings"]
    assert report["workbookWritesAllowed"] is False and report["serverFreshnessVerified"] is False
