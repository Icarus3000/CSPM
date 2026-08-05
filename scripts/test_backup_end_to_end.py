import os
import sys
import shutil
import zipfile
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "src" / "python"))

from services.paths import AppPaths
from services.backup_service import BackupService

# Need to import recovery module for testing
sys.path.append(str(ROOT_DIR / "scripts"))
import cspm_recovery

class TestPaths(AppPaths):
    def __init__(self, root: Path):
        super().__init__(root)
        self._test_root = root
    def _persistent_data_root(self) -> Path:
        return self._test_root
    def runtime_dir(self) -> Path:
        return self._test_root
    def exports_dir(self) -> Path:
        return self._test_root / "exports"

@pytest.fixture
def temp_env(tmp_path):
    root = Path(__file__).resolve().parent.parent
    if (tmp_path / "data").resolve() == (root / "data").resolve():
        pytest.exit("ABORT: Writable test fixture resolves to exact live workbook path.")
        
    paths = TestPaths(tmp_path)
    paths.data_dir().mkdir(parents=True)
    paths.state_dir().mkdir(parents=True)
    paths.backups_snapshots_dir().mkdir(parents=True)
    
    # Create valid mock xlsm files
    for wb in ["CSPM.xlsm", "Dockets.xlsm"]:
        wb_path = paths.data_dir() / wb
        with zipfile.ZipFile(wb_path, "w") as zf:
            zf.writestr("xl/vbaProject.bin", b"VBA_MACRO_CONTENT")
            zf.writestr("docProps/core.xml", b"XML")
            zf.writestr("[Content_Types].xml", b"XML")
    
    yield paths

def test_01_backup_coordinated(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    assert res["ok"]
    assert "package_name" in res
    
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    assert (pkg_dir / "CSPM.xlsm").exists()
    assert (pkg_dir / "Dockets.xlsm").exists()

def test_02_valid_manifest_creation(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    man_path = pkg_dir / "manifest.json"
    assert man_path.exists()
    with open(man_path) as f:
        man = json.load(f)
    assert len(man["files"]) == 2
    filenames = sorted([f["filename"] for f in man["files"]])
    assert filenames == ["CSPM.xlsm", "Dockets.xlsm"]

def test_04_macro_preservation(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    for wb in ["CSPM.xlsm", "Dockets.xlsm"]:
        with zipfile.ZipFile(pkg_dir / wb, "r") as zf:
            assert "xl/vbaProject.bin" in zf.namelist()

def test_07_source_to_backup_equality(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    for wb in ["CSPM.xlsm", "Dockets.xlsm"]:
        src = temp_env.data_dir() / wb
        dest = pkg_dir / wb
        with open(src, "rb") as f1, open(dest, "rb") as f2:
            assert f1.read() == f2.read()

def test_13_missing_workbook_rejection(temp_env):
    svc = BackupService(paths=temp_env)
    (temp_env.data_dir() / "CSPM.xlsm").unlink()
    res = svc.create_snapshot(reason="Test", force=True)
    assert not res["ok"]
    assert "missing" in res["message"].lower()

def test_14_empty_workbook_rejection(temp_env):
    svc = BackupService(paths=temp_env)
    with open(temp_env.data_dir() / "CSPM.xlsm", "wb") as f:
        f.write(b"")
    res = svc.create_snapshot(reason="Test", force=True)
    assert not res["ok"]

def test_15_excel_lock_detection(temp_env):
    # Lock for backup
    svc = BackupService(paths=temp_env)
    lock_path = temp_env.data_dir() / "~$CSPM.xlsm"
    with open(lock_path, "wb") as f: f.write(b"lock")
    
    # Try prepare_restore
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_name = res["package_name"] if res.get("ok") else "dummy"
    prep = svc.prepare_restore(pkg_name)
    assert not prep["ok"]
    assert prep.get("locked")

def test_recovery_success(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    assert res["ok"]
    pkg_name = res["package_name"]
    pkg_dir = temp_env.backups_snapshots_dir() / pkg_name
    
    cspm_recovery.PATHS = temp_env
    cspm_recovery.APPROVED_ROOTS = [str(temp_env.data_dir()), str(temp_env.state_dir()), str(temp_env.backups_snapshots_dir())]
    with open(pkg_dir / "manifest.json", "r") as f:
        manifest = json.load(f)
        
    # Modify original to prove restore works
    with zipfile.ZipFile(temp_env.data_dir() / "CSPM.xlsm", "w") as zf:
        zf.writestr("test", b"modified")
        
    engine = cspm_recovery.RecoveryEngine(temp_env.state_dir(), temp_env.data_dir())
    result = engine.perform_restore(pkg_dir, manifest)
    assert result["status"] == "completed"
    
    # Verify rollback works by checking file was restored to original
    with open(temp_env.data_dir() / "CSPM.xlsm", "rb") as f:
        content = f.read()
    assert b"modified" not in content

def test_recovery_rollback_on_second_replace_failure(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_name = res["package_name"]
    pkg_dir = temp_env.backups_snapshots_dir() / pkg_name
    
    cspm_recovery.PATHS = temp_env
    cspm_recovery.APPROVED_ROOTS = [str(temp_env.data_dir()), str(temp_env.state_dir()), str(temp_env.backups_snapshots_dir())]
    with open(pkg_dir / "manifest.json", "r") as f:
        manifest = json.load(f)

    # We need to simulate os.replace failing on Dockets.xlsm
    original_replace = os.replace
    def mocked_replace(src, dst):
        if "Dockets.xlsm" in str(dst):
            raise PermissionError("Simulated failure during second replacement")
        return original_replace(src, dst)
        
    with patch("os.replace", side_effect=mocked_replace):
        engine = cspm_recovery.RecoveryEngine(temp_env.state_dir(), temp_env.data_dir())
        result = engine.perform_restore(pkg_dir, manifest)
        
    assert result["status"] != "completed"
    assert "Rolled back" in result["message"] or "failed" in result["message"].lower()

def test_17_independent_pre_restore_safety_backup(temp_env):
    cspm_recovery.PATHS = temp_env
    cspm_recovery.APPROVED_ROOTS = [str(temp_env.data_dir()), str(temp_env.state_dir()), str(temp_env.backups_snapshots_dir())]
    res = cspm_recovery.create_safety_backup()
    assert res["ok"]
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    assert (pkg_dir / "manifest.json").exists()

def test_11_path_traversal_rejection(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    
    cspm_recovery.PATHS = temp_env
    cspm_recovery.APPROVED_ROOTS = [str(temp_env.data_dir()), str(temp_env.state_dir()), str(temp_env.backups_snapshots_dir())]
    with open(pkg_dir / "manifest.json", "r") as f:
        manifest = json.load(f)
    
    # Mutate manifest
    manifest["files"][0]["filename"] = "../traversal.xlsm"
    
    engine = cspm_recovery.RecoveryEngine(temp_env.state_dir(), temp_env.data_dir())
    result = engine.perform_restore(pkg_dir, manifest)
    assert result["status"] != "completed"
    assert "traversal" in result["message"].lower() or "exactly" in result["message"].lower()

def test_09_unexpected_file_rejection(temp_env):
    svc = BackupService(paths=temp_env)
    res = svc.create_snapshot(reason="Test", force=True)
    pkg_dir = temp_env.backups_snapshots_dir() / res["package_name"]
    
    cspm_recovery.PATHS = temp_env
    cspm_recovery.APPROVED_ROOTS = [str(temp_env.data_dir()), str(temp_env.state_dir()), str(temp_env.backups_snapshots_dir())]
    with open(pkg_dir / "manifest.json", "r") as f:
        manifest = json.load(f)
    
    # Mutate manifest
    manifest["files"].append({"filename": "Unexpected.xlsm", "size": 100, "sha256": "ABC"})
    
    engine = cspm_recovery.RecoveryEngine(temp_env.state_dir(), temp_env.data_dir())
    result = engine.perform_restore(pkg_dir, manifest)
    assert result["status"] != "completed"
    assert "exactly two files" in result["message"].lower()
