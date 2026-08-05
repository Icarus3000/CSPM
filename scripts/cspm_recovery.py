import os
import sys
import json
import shutil
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import uuid
import ctypes
from ctypes import wintypes

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "src" / "python"))

try:
    from services.paths import AppPaths
    PATHS = AppPaths(ROOT_DIR)
except ImportError:
    print("WARNING: Could not import AppPaths. Using fallback paths.")
    class FallbackPaths:
        def _persistent_data_root(self):
            env_override = os.environ.get("CSPM_DATA_DIR", "").strip()
            if env_override: return Path(env_override)
            if getattr(sys, 'frozen', False):
                lad = os.environ.get("LOCALAPPDATA", "").strip()
                return Path(lad) / "CSPM" if lad else Path.home() / ".cspm_data"
            return ROOT_DIR
        def data_dir(self): return self._persistent_data_root() / "data"
        def workbook_path(self): return self.data_dir() / "CSPM.xlsm"
        def dockets_workbook_path(self): return self.data_dir() / "Dockets.xlsm"
        def state_dir(self): return self.data_dir() / "state"
        def backups_snapshots_dir(self): return self._persistent_data_root() / "backups" / "CSPM" / "snapshots"
    PATHS = FallbackPaths()

# Approved Roots for Validation
APPROVED_ROOTS = [str(PATHS.data_dir()), str(PATHS.state_dir()), str(PATHS.backups_snapshots_dir())]

def _is_path_approved(path: Path) -> bool:
    resolved = str(path.resolve())
    return any(resolved.startswith(str(Path(r).resolve())) for r in APPROVED_ROOTS)

def _calc_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def _is_file_exclusively_locked(filepath: Path) -> bool:
    """Uses Windows CreateFileW with zero sharing to definitively detect locks."""
    if not filepath.exists():
        return False
        
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, 
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    
    # Use generic read only (non-destructive) but require exclusive access (0 sharing)
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 128
    
    handle = kernel32.CreateFileW(
        str(filepath),
        GENERIC_READ,
        0, # NO SHARING
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error_code = ctypes.GetLastError()
        if error_code == 2: # ERROR_FILE_NOT_FOUND
            return False
        if error_code == 32: # ERROR_SHARING_VIOLATION
            return True
        return True # Any other error conservatively treated as locked
        
    try:
        return False
    finally:
        kernel32.CloseHandle(handle)

def _is_cspm_running() -> bool:
    """Uses Windows CreateToolhelp32Snapshot to cleanly detect the CSPM process."""
    TH32CS_SNAPPROCESS = 0x00000002
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    
    if snapshot == invalid_handle:
        return False
        
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return False
            
        while True:
            if pe.szExeFile.lower() == "cspm.exe":
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
                
        return False
    finally:
        kernel32.CloseHandle(snapshot)

def check_locks(injectable_paths=None) -> list:
    auth_files = injectable_paths or [PATHS.workbook_path(), PATHS.dockets_workbook_path()]
    locks = []
    
    # 1. Excel lock files
    for p in auth_files:
        lock_path = p.parent / f"~${p.name}"
        if lock_path.exists():
            locks.append(f"{p.name} (Excel Lock File)")
        elif _is_file_exclusively_locked(p):
            locks.append(f"{p.name} (Exclusive Process Lock)")
            
    # 2. CSPM.exe running
    if _is_cspm_running():
        locks.append("CSPM.exe (Application Running)")
        
    return locks

def create_safety_backup(reason: str = "Pre-restore safety backup", auth_files=None, backups_dir=None) -> dict:
    auth_files = auth_files or [PATHS.workbook_path(), PATHS.dockets_workbook_path()]
    backups_dir = backups_dir or PATHS.backups_snapshots_dir()
    
    source_metadata = []
    for p in auth_files:
        if p.exists() and p.stat().st_size > 0:
            source_metadata.append({
                "file": p.name,
                "path": str(p),
                "size": p.stat().st_size,
                "sha256": _calc_sha256(p)
            })
        else:
            return {"ok": False, "message": f"Source file missing or empty: {p.name}"}
            
    ts_local = datetime.now()
    batch_id = str(uuid.uuid4())[:8].upper()
    pkg_name = f"Backup_{ts_local.strftime('%Y%m%d_%H%M%S')}_{batch_id}_SAFETY"
    tmp_dir = backups_dir / f".tmp_{pkg_name}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    copied_metadata = []
    for sm in source_metadata:
        src = Path(sm["path"])
        dest = tmp_dir / src.name
        shutil.copy2(src, dest)
        if _calc_sha256(dest) != sm["sha256"] or dest.stat().st_size != sm["size"]:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"ok": False, "message": f"Validation failed during safety copy of {src.name}"}
        copied_metadata.append({
            "filename": src.name,
            "source_path": str(src),
            "size": sm["size"],
            "sha256": sm["sha256"]
        })
        
    manifest = {
        "version": "1.0",
        "batch_id": batch_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_local": ts_local.isoformat(),
        "app_version": "Recovery",
        "reason": reason,
        "protected": True,
        "retention_class": "pre_restore",
        "files": copied_metadata,
        "validation_status": "Passed"
    }
    with open(tmp_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(tmp_dir / "checksums.sha256", "w", encoding="utf-8") as f:
        for cm in copied_metadata:
            f.write(f"{cm['sha256']}  {cm['filename']}\n")
    with open(tmp_dir / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump({"ok": True, "errors": []}, f, indent=2)
        
    final_dir = backups_dir / pkg_name
    tmp_dir.rename(final_dir)
    return {"ok": True, "package_name": pkg_name, "path": str(final_dir)}


class RecoveryEngine:
    def __init__(self, state_dir=None, data_dir=None):
        self.state_dir = state_dir or PATHS.state_dir()
        self.data_dir = data_dir or PATHS.data_dir()
        self.journal_path = self.state_dir / "restore_journal.json"
        self.result_report = {
            "timestamp": datetime.now().isoformat(),
            "package_path": "",
            "status": "failed_safe",
            "message": ""
        }
        
    def _write_journal(self, state: str, data: dict):
        data["current_phase"] = state
        data["last_updated"] = datetime.now().isoformat()
        
        # Validate paths
        for k, v in data.items():
            if k.endswith("_path") and v:
                if not _is_path_approved(Path(v)):
                    raise Exception(f"Unapproved path detected in journal: {v}")
                    
        tmp = self.journal_path.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            # Note: os.fsync on file guarantees file data durability. 
            # Directory entry durability is handled natively by NTFS journaling, but os.fsync on directory is not supported in Windows.
        os.replace(tmp, self.journal_path)
        
    def _read_journal(self) -> dict:
        if not self.journal_path.exists():
            return None
        try:
            with open(self.journal_path, 'r', encoding='utf-8') as f:
                j = json.load(f)
                
            if j.get("journal_version") != "1.1":
                return None
            if "transaction_id" not in j or "current_phase" not in j:
                return None
            return j
        except Exception:
            return None
            
    def _archive_journal(self, status: str):
        if self.journal_path.exists():
            j = self._read_journal() or {}
            txn = j.get("transaction_id", "UNKNOWN")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            
            # Archive journal
            arch_name = f"restore_journal_ARCHIVED_{ts}_{txn}_{status}.json"
            shutil.copy2(self.journal_path, self.state_dir / arch_name)
            self.journal_path.unlink()
            
            # Archive pending payload if present
            pending = self.state_dir / "pending_restore.json"
            if pending.exists():
                pending_arch_name = f"pending_restore_ARCHIVED_{ts}_{txn}_{status}.json"
                shutil.copy2(pending, self.state_dir / pending_arch_name)
                pending.unlink()

    def check_interrupted_transaction(self):
        j = self._read_journal()
        if not j:
            return None
        phase = j.get("current_phase")
        if phase in ("SUCCESS", "ROLLED_BACK", "FAILED_SAFE", "CANCELLED_BEFORE_CHANGE", "UNRESOLVED_REQUIRES_ATTENTION"):
            self._archive_journal(phase)
            return None
        return j

    def resume_interrupted_transaction(self, j: dict):
        phase = j.get("current_phase")
        print(f"\n[RECOVERY] Resuming interrupted transaction from phase: {phase}")
        
        if phase in ("INIT", "SAFETY_CREATED", "STAGED"):
            print("No active destinations were replaced. Safely abandoning.")
            self._write_journal("FAILED_SAFE", j)
            self._archive_journal("FAILED_SAFE")
            return {"status": "failed_safe", "message": "Abandoned incomplete transaction (no data modified)."}
            
        elif phase == "CSPM_REPLACED":
            print("Exactly one destination replaced. Forcing rollback to pre-restore state.")
            return self._execute_rollback(j, "Interrupted after single workbook replacement (CSPM_REPLACED)")
            
        elif phase == "DOCKETS_REPLACED":
            print("Both destinations replaced. Validating final hashes against target hashes...")
            
            # We don't check staged_path because os.replace consumes it.
            # We check the actual live destinations against intended hashes.
            can_finalize = False
            if check_locks() == []: # No locks
                dest_keys = ["CSPM.xlsm", "Dockets.xlsm"]
                if all(Path(j["destinations"][f]["target_path"]).exists() for f in dest_keys):
                    if all(_calc_sha256(Path(j["destinations"][f]["target_path"])) == j["destinations"][f]["intended_hash"] for f in dest_keys):
                        can_finalize = True
                        
            if can_finalize:
                print("Final hashes match intended state. Finalizing success.")
                self._write_journal("SUCCESS", j)
                self._archive_journal("SUCCESS")
                shutil.rmtree(Path(j.get("rollback_path", "")), ignore_errors=True)
                return {"status": "completed", "message": "Restoration verified and successful on restart."}
            else:
                print("Destination hashes do not match intended state. Forcing full rollback...")
                return self._execute_rollback(j, "Interrupted after DOCKETS_REPLACED, hashes invalid.")
                
        elif phase == "ROLLBACK_STARTED":
            print("Interrupted during rollback. Resuming rollback...")
            return self._execute_rollback(j, "Resuming interrupted rollback")
            
        return {"status": "unresolved_requires_attention", "message": f"Unknown phase: {phase}"}

    def _execute_rollback(self, j: dict, reason: str):
        self._write_journal("ROLLBACK_STARTED", j)
        rollback_dir = Path(j.get("rollback_path", ""))
        
        # Verify rollback material hashes
        valid_rollback_available = True
        
        # Check standard rollback dir first
        if rollback_dir.exists():
            for fname in ["CSPM.xlsm", "Dockets.xlsm"]:
                rb = rollback_dir / fname
                if rb.exists() and j["destinations"].get(fname, {}).get("original_hash"):
                    if _calc_sha256(rb) != j["destinations"][fname]["original_hash"]:
                        valid_rollback_available = False
                        break
                else:
                    valid_rollback_available = False
                    break
        else:
            valid_rollback_available = False
            
        # Fallback to safety package
        if not valid_rollback_available:
            safety_pkg = Path(j.get("safety_package", ""))
            if safety_pkg.exists():
                valid_rollback_available = True
                rollback_dir = safety_pkg
                for fname in ["CSPM.xlsm", "Dockets.xlsm"]:
                    rb = rollback_dir / fname
                    if rb.exists() and j["destinations"].get(fname, {}).get("original_hash"):
                        if _calc_sha256(rb) != j["destinations"][fname]["original_hash"]:
                            valid_rollback_available = False
                            break
                    else:
                        valid_rollback_available = False
                        break
                        
        if not valid_rollback_available:
            self._write_journal("UNRESOLVED_REQUIRES_ATTENTION", j)
            self._archive_journal("UNRESOLVED_REQUIRES_ATTENTION")
            return {"status": "unresolved_requires_attention", "message": "Rollback material missing or tampered with!"}
            
        for fname in ["CSPM.xlsm", "Dockets.xlsm"]:
            tgt = Path(j["destinations"][fname]["target_path"])
            rb = rollback_dir / fname
            if rb.exists():
                try:
                    os.replace(rb, tgt)
                except Exception as e:
                    self._write_journal("UNRESOLVED_REQUIRES_ATTENTION", j)
                    self._archive_journal("UNRESOLVED_REQUIRES_ATTENTION")
                    return {"status": "unresolved_requires_attention", "message": f"Failed to rollback {fname}: {e}"}
                    
        self._write_journal("ROLLED_BACK", j)
        self._archive_journal("ROLLED_BACK")
        if rollback_dir.name.startswith(".restore_rollback"):
            shutil.rmtree(rollback_dir, ignore_errors=True)
            
        staging_dir = Path(j.get("staging_path", ""))
        shutil.rmtree(staging_dir, ignore_errors=True)
        return {"status": "rolled_back", "message": f"Rolled back completely. Reason: {reason}"}
        
    def _verify_final(self, j: dict):
        for fname in ["CSPM.xlsm", "Dockets.xlsm"]:
            tgt = Path(j["destinations"][fname]["target_path"])
            expected_hash = j["destinations"][fname]["intended_hash"]
            if _calc_sha256(tgt) != expected_hash:
                return self._execute_rollback(j, f"Final verification failed for {fname}.")
                
        self._write_journal("SUCCESS", j)
        self._archive_journal("SUCCESS")
        rollback_dir = Path(j.get("rollback_path", ""))
        staging_dir = Path(j.get("staging_path", ""))
        shutil.rmtree(staging_dir, ignore_errors=True)
        shutil.rmtree(rollback_dir, ignore_errors=True)
        return {"status": "completed", "message": "Restoration verified and successful."}

    def perform_restore(self, package_path: Path, manifest: dict, skip_locks=False) -> dict:
        self.result_report["package_path"] = str(package_path)
        
        def _fail(msg, status="failed_safe"):
            self.result_report["status"] = status
            self.result_report["message"] = msg
            return self.result_report
            
        if not skip_locks:
            locks = check_locks([PATHS.workbook_path(), PATHS.dockets_workbook_path()])
            if locks:
                return _fail(f"Files in use: {', '.join(locks)}", "failed_safe")
                
        # 1. INIT Journal
        txn_id = str(uuid.uuid4())
        j = {
            "journal_version": "1.1",
            "transaction_id": txn_id,
            "target_package": str(package_path),
            "current_phase": "INIT",
            "destinations": {}
        }
        self._write_journal("INIT", j)
        
        files_to_restore = manifest.get("files", [])
        if len(files_to_restore) != 2:
            return _fail("Manifest does not contain exactly two files.", "failed_safe")
            
        for fmeta in files_to_restore:
            fname = fmeta["filename"]
            if ".." in fname or "/" in fname or "\\" in fname:
                return _fail(f"Path traversal detected in manifest filename: {fname}", "failed_safe")
            if Path(fname).is_absolute():
                return _fail(f"Absolute path detected in manifest filename: {fname}", "failed_safe")
                
        filenames = sorted([f["filename"] for f in files_to_restore])
        if filenames != ["CSPM.xlsm", "Dockets.xlsm"]:
            return _fail("Manifest does not contain exactly CSPM.xlsm and Dockets.xlsm.", "failed_safe")
            
        required_files = ["manifest.json", "checksums.sha256", "validation_report.json", "CSPM.xlsm", "Dockets.xlsm"]
        for rf in required_files:
            if not (package_path / rf).exists():
                return _fail(f"Package missing required artifact: {rf}", "failed_safe")
                
        for fmeta in files_to_restore:
            fname = fmeta["filename"]
            fpath = package_path / fname
            if not fpath.exists():
                return _fail(f"File {fname} missing from backup package!", "failed_safe")
                
            if fpath.stat().st_size == 0:
                return _fail(f"Backup file {fname} is zero bytes.", "failed_safe")
                
            if fpath.stat().st_size != fmeta["size"]:
                return _fail(f"Size mismatch for {fname}.", "failed_safe")
                
            sha = _calc_sha256(fpath)
            if sha != fmeta["sha256"]:
                return _fail(f"Checksum mismatch for {fname}. Expected: {fmeta['sha256']}, Actual: {sha}", "failed_safe")
                
        # SAFETY BACKUP
        safety_res = create_safety_backup()
        if not safety_res["ok"]:
            return _fail(f"Safety backup failed: {safety_res['message']}", "failed_safe")
            
        j["safety_package"] = safety_res["path"]
        self._write_journal("SAFETY_CREATED", j)
        
        # STAGING
        staging_dir = self.data_dir / f".restore_staging_{txn_id[:8]}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        j["staging_path"] = str(staging_dir)
        
        rollback_dir = self.data_dir / f".restore_rollback_{txn_id[:8]}"
        rollback_dir.mkdir(parents=True, exist_ok=True)
        j["rollback_path"] = str(rollback_dir)
        
        for fmeta in files_to_restore:
            src = package_path / fmeta["filename"]
            dest = staging_dir / fmeta["filename"]
            try:
                shutil.copy2(src, dest)
            except Exception as e:
                return _fail(f"Failed to stage {fmeta['filename']}: {e}", "failed_safe")
                
            if dest.stat().st_size != fmeta["size"] or _calc_sha256(dest) != fmeta["sha256"]:
                return _fail(f"Checksum/size mismatch after staging {fmeta['filename']}.", "failed_safe")
                
            target = PATHS.workbook_path() if fmeta["filename"] == "CSPM.xlsm" else PATHS.dockets_workbook_path()
            original_hash = _calc_sha256(target) if target.exists() else ""
            
            j["destinations"][fmeta["filename"]] = {
                "staged_path": str(dest),
                "target_path": str(target),
                "intended_hash": fmeta["sha256"],
                "intended_size": fmeta["size"],
                "original_hash": original_hash,
                "original_size": target.stat().st_size if target.exists() else 0
            }
            
            # Create rollback copy
            try:
                if target.exists():
                    rb = rollback_dir / fmeta["filename"]
                    shutil.copy2(target, rb)
            except Exception as e:
                return _fail(f"Failed to create rollback copy of {fmeta['filename']}: {e}", "failed_safe")
                
        self._write_journal("STAGED", j)
        
        # REPLACEMENT
        cspm_dest = j["destinations"]["CSPM.xlsm"]
        try:
            os.replace(cspm_dest["staged_path"], cspm_dest["target_path"])
            self._write_journal("CSPM_REPLACED", j)
        except Exception as e:
            rb_res = self._execute_rollback(j, f"Failed to replace CSPM.xlsm: {e}")
            return _fail(rb_res["message"], rb_res["status"])
            
        dockets_dest = j["destinations"]["Dockets.xlsm"]
        try:
            os.replace(dockets_dest["staged_path"], dockets_dest["target_path"])
            self._write_journal("DOCKETS_REPLACED", j)
        except Exception as e:
            rb_res = self._execute_rollback(j, f"Failed to replace Dockets.xlsm: {e}")
            return _fail(rb_res["message"], rb_res["status"])
            
        # VERIFICATION
        res = self._verify_final(j)
        if res["status"] == "completed":
            self.result_report["status"] = "completed"
            self.result_report["message"] = "Restoration completed successfully."
        else:
            self.result_report["status"] = res["status"]
            self.result_report["message"] = res["message"]
            
        return self.result_report

def cancel_restore():
    """Cancels a restore request before any changes."""
    engine = RecoveryEngine()
    j = engine._read_journal()
    if j and j.get("current_phase") not in ("INIT", "SAFETY_CREATED", "STAGED", None):
        print("Replacement has already begun. Cannot ordinarily cancel. Resuming interrupted transaction...")
        res = engine.resume_interrupted_transaction(j)
    else:
        if j:
            engine._write_journal("CANCELLED_BEFORE_CHANGE", j)
            engine._archive_journal("CANCELLED_BEFORE_CHANGE")
        else:
            # Archive pending payload if present even if no journal was created
            pending = engine.state_dir / "pending_restore.json"
            if pending.exists():
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                pending.rename(engine.state_dir / f"pending_restore_ARCHIVED_{ts}_cancelled.json")
                
        res = {
            "timestamp": datetime.now().isoformat(),
            "package_path": "N/A",
            "status": "cancelled_before_change",
            "message": "Restoration was cancelled by user."
        }
        
    report_path = PATHS.state_dir() / "recovery_result.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(res["message"])
    sys.exit(0)

def cli_main():
    print("==================================================")
    print("       CSPM EXTERNAL RECOVERY UTILITY")
    print("==================================================")
    
    engine = RecoveryEngine()
    
    j = engine.check_interrupted_transaction()
    if j:
        print("WARNING: An interrupted recovery transaction was detected.")
        res = engine.resume_interrupted_transaction(j)
        print(res["message"])
        report_path = PATHS.state_dir() / "recovery_result.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        sys.exit(0 if res["status"] == "completed" else 1)
        
    locks = check_locks()
    if locks:
        print(f"ERROR: Workbooks are currently locked or in use: {', '.join(locks)}")
        print("Please close Excel and CSPM completely before running the recovery utility.")
        sys.exit(1)
        
    pending_restore = PATHS.state_dir() / "pending_restore.json"
    target_package = None
    manifest = None
    
    if pending_restore.exists():
        try:
            with open(pending_restore, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            print(f"Found pending restore request from CSPM.")
            print(f"Target Backup: {payload['target_package']}")
            target_package = Path(payload["target_package_path"])
            manifest = payload["manifest"]
            
            ans = input("Proceed with restoration? (y/N): ")
            if ans.lower() != 'y':
                cancel_restore()
                
        except Exception as e:
            print(f"Failed to process pending restore: {e}")
            res = {"status": "failed_safe", "message": f"Pending restore invalid: {e}"}
            report_path = PATHS.state_dir() / "recovery_result.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            if pending_restore.exists():
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                pending_restore.rename(PATHS.state_dir() / f"pending_restore_ARCHIVED_{ts}_failed.json")
            sys.exit(1)
    else:
        print("No pending restore request found from CSPM.")
        snaps_dir = PATHS.backups_snapshots_dir()
        if not snaps_dir.exists():
            print("No backups directory found.")
            sys.exit(0)
            
        backups = [d for d in snaps_dir.iterdir() if d.is_dir() and d.name.startswith("Backup_")]
        backups.sort(key=lambda x: x.name, reverse=True)
        if not backups:
            print("No backups found.")
            sys.exit(0)
            
        print("Available Backups:")
        for i, b in enumerate(backups):
            print(f" [{i+1}] {b.name}")
            
        ans = input(f"\nSelect a backup to restore [1-{len(backups)}] or Q to quit: ")
        if ans.lower() == 'q':
            sys.exit(0)
            
        try:
            idx = int(ans) - 1
            if 0 <= idx < len(backups):
                target_package = backups[idx]
                man_path = target_package / "manifest.json"
                if not man_path.exists():
                    print("Backup package is missing manifest.json. Cannot verify.")
                    sys.exit(1)
                    
                with open(man_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    
                ans2 = input("Are you absolutely sure you want to proceed? (y/N): ")
                if ans2.lower() != 'y':
                    cancel_restore()
            else:
                print("Invalid selection.")
                sys.exit(1)
        except ValueError:
            print("Invalid input.")
            sys.exit(1)
            
    res = engine.perform_restore(target_package, manifest, skip_locks=True) 
    
    report_path = PATHS.state_dir() / "recovery_result.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
        
    print(res["message"])
    sys.exit(0 if res["status"] == "completed" else 1)

if __name__ == "__main__":
    cli_main()
