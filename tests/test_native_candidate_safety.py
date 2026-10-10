"""Dataset gate and immutable authority boundary, with synthetic bytes only."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
from backend import native_candidate
from services.paths import AppPaths


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "acceptance"
    (root / "baseline").mkdir(parents=True)
    (root / "working" / "data").mkdir(parents=True)
    hashes = {}
    for name in ("CSPM.xlsm", "Dockets.xlsm"):
        raw = ("SYNTHETIC-"+name).encode()
        (root / "baseline" / name).write_bytes(raw)
        (root / "working" / "data" / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest().upper()
    metadata = dict(schemaVersion=1, source=str(tmp_path / "authority"), integrityPassed=True,
                    cloudWritesEnabled=False, sourceHashes=hashes, snapshotHashes=hashes)
    (root / "snapshot.private.json").write_text(json.dumps(metadata))
    return root


def test_valid_baseline_accepts_independent_working_writes(snapshot):
    (snapshot / "working" / "data" / "CSPM.xlsm").write_bytes(b"SYNTHETIC-EDIT")
    assert native_candidate.validate_profile(snapshot) == snapshot
    assert (snapshot / "baseline" / "CSPM.xlsm").read_bytes() == b"SYNTHETIC-CSPM.xlsm"


@pytest.mark.parametrize("field,value", [("integrityPassed", False), ("cloudWritesEnabled", True), ("schemaVersion", 2)])
def test_failed_dataset_or_cloud_publish_never_opens_acceptance(snapshot, field, value):
    manifest = snapshot / "snapshot.private.json"
    values = json.loads(manifest.read_text())
    values[field] = value
    manifest.write_text(json.dumps(values))
    with pytest.raises(ValueError):
        native_candidate.validate_profile(snapshot)


def test_modified_protected_baseline_is_rejected(snapshot):
    (snapshot / "baseline" / "CSPM.xlsm").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        native_candidate.validate_profile(snapshot)


def test_overlap_with_authority_is_rejected(snapshot):
    manifest = snapshot / "snapshot.private.json"
    values = json.loads(manifest.read_text())
    values["source"] = str(snapshot)
    manifest.write_text(json.dumps(values))
    with pytest.raises(ValueError, match="overlap"):
        native_candidate.validate_profile(snapshot)


def test_candidate_paths_ignore_attempted_production_folder_overrides(snapshot, monkeypatch):
    monkeypatch.setattr(native_candidate, "_profile", snapshot)
    paths = AppPaths(ROOT, override_data_dir=snapshot.parent / "authority",
                     override_master_dir=snapshot.parent / "authority")
    assert paths.data_dir() == snapshot / "working" / "data"
    assert paths.master_data_dir() is None


def test_ordinary_primary_paths_remain_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(native_candidate, "_profile", None)
    paths = AppPaths(ROOT, override_data_dir=tmp_path / "local", override_master_dir=tmp_path / "cloud")
    assert paths.data_dir() == tmp_path / "local"
    assert paths.master_data_dir() == tmp_path / "cloud"
