from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.paths import AppPaths


def _calc_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest().upper()


class BackupService:
    def __init__(self, paths: AppPaths, app_version: str = "0.0.1"):
        self.paths = paths
        self.app_version = app_version

    def _get_authoritative_files(self) -> List[Path]:
        return [self.paths.workbook_path(), self.paths.dockets_workbook_path()]

    def create_snapshot(
        self,
        reason: str = "Manual snapshot",
        protected: bool = False,
        retention_class: str = "daily",
        force: bool = False,
    ) -> Dict[str, Any]:
        
        auth_files = self._get_authoritative_files()
        
        # 1. Validation & Source check
        source_metadata = []
        all_exist = True
        for p in auth_files:
            if not p.exists() or p.stat().st_size == 0:
                all_exist = False
                source_metadata.append({"file": p.name, "status": "missing_or_empty"})
            else:
                source_metadata.append({
                    "file": p.name,
                    "path": str(p),
                    "size": p.stat().st_size,
                    "sha256": _calc_sha256(p)
                })
        
        if not all_exist:
            return {"ok": False, "message": "One or more authoritative workbooks missing or empty.", "details": source_metadata}
            
        # 2. Check if changed (avoid redundant)
        if not force:
            last_snapshot = self.get_latest_snapshot()
            if last_snapshot and "files" in last_snapshot:
                # Compare hashes
                last_hashes = {f["filename"]: f["sha256"] for f in last_snapshot["files"]}
                current_hashes = {f["file"]: f["sha256"] for f in source_metadata}
                
                changed = False
                for fname, hsh in current_hashes.items():
                    if last_hashes.get(fname) != hsh:
                        changed = True
                        break
                if not changed:
                    return {"ok": True, "message": "No files changed since last backup.", "skipped": True}

        # 3. Create temp package
        ts_utc = datetime.now(timezone.utc)
        ts_local = datetime.now()
        ts_str = ts_local.strftime("%Y%m%d_%H%M%S")
        batch_id = str(uuid.uuid4())[:8].upper()
        
        pkg_name = f"Backup_{ts_str}_{batch_id}"
        tmp_dir = self.paths.backups_snapshots_dir() / f".tmp_{pkg_name}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        
        copied_metadata = []
        validation_errors = []
        
        try:
            for sm in source_metadata:
                src_path = Path(sm["path"])
                dest_path = tmp_dir / src_path.name
                shutil.copy2(src_path, dest_path)
                
                dest_sha = _calc_sha256(dest_path)
                if dest_sha != sm["sha256"]:
                    validation_errors.append(f"Checksum mismatch for {src_path.name} after copy.")
                elif dest_path.stat().st_size != sm["size"]:
                    validation_errors.append(f"Size mismatch for {src_path.name} after copy.")
                else:
                    copied_metadata.append({
                        "filename": src_path.name,
                        "source_path": str(src_path),
                        "size": sm["size"],
                        "sha256": dest_sha
                    })

            if validation_errors:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"ok": False, "message": "Validation failed during copy.", "errors": validation_errors}

            # 4. Generate manifest
            manifest = {
                "version": "1.0",
                "batch_id": batch_id,
                "timestamp_utc": ts_utc.isoformat(),
                "timestamp_local": ts_local.isoformat(),
                "app_version": self.app_version,
                "reason": reason,
                "protected": protected,
                "retention_class": retention_class,
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

            # 5. Move to final
            final_dir = self.paths.backups_snapshots_dir() / pkg_name
            tmp_dir.rename(final_dir)
            
            return {
                "ok": True,
                "message": "Snapshot created successfully.",
                "skipped": False,
                "package_name": pkg_name,
                "manifest": manifest
            }
            
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"ok": False, "message": f"Backup failed: {e}"}

    def list_snapshots(self) -> List[Dict[str, Any]]:
        snaps_dir = self.paths.backups_snapshots_dir()
        if not snaps_dir.exists():
            return []
            
        snapshots = []
        for d in snaps_dir.iterdir():
            if d.is_dir() and d.name.startswith("Backup_"):
                man_path = d / "manifest.json"
                if man_path.exists():
                    try:
                        with open(man_path, "r", encoding="utf-8") as f:
                            man = json.load(f)
                            man["package_name"] = d.name
                            man["path"] = str(d)
                            snapshots.append(man)
                    except json.JSONDecodeError:
                        pass
                        
        snapshots.sort(key=lambda x: x.get("timestamp_utc", ""), reverse=True)
        return snapshots

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        snaps = self.list_snapshots()
        return snaps[0] if snaps else None
        
    def protect_snapshot(self, package_name: str, protected: bool = True) -> bool:
        snaps_dir = self.paths.backups_snapshots_dir()
        d = snaps_dir / package_name
        man_path = d / "manifest.json"
        if not man_path.exists():
            return False
            
        try:
            with open(man_path, "r", encoding="utf-8") as f:
                man = json.load(f)
            man["protected"] = protected
            with open(man_path, "w", encoding="utf-8") as f:
                json.dump(man, f, indent=2)
            return True
        except Exception:
            return False

    def prune_snapshots(self) -> Dict[str, Any]:
        snaps = self.list_snapshots()
        if not snaps:
            return {"ok": True, "pruned": 0}
            
        # Simplified tiering: keep last 10 session, all protected.
        # In a full implementation, we'd group by day/month.
        
        to_delete = []
        # Keep at least one known good (we assume latest is good if not marked bad)
        latest_unprotected = None
        for s in snaps:
            if not s.get("protected"):
                latest_unprotected = s
                break
                
        session_kept = 0
        for s in snaps:
            if s.get("protected"):
                continue
            if s == latest_unprotected:
                # Keep latest always
                continue
                
            session_kept += 1
            if session_kept > 10:
                to_delete.append(s)
                
        deleted_count = 0
        for s in to_delete:
            p = Path(s["path"])
            if p.exists() and p.name.startswith("Backup_"):
                shutil.rmtree(p, ignore_errors=True)
                deleted_count += 1
                
        return {"ok": True, "pruned": deleted_count}

    def _check_workbook_locks(self) -> List[str]:
        locks = []
        for p in self._get_authoritative_files():
            lock_path = p.parent / f"~${p.name}"
            if lock_path.exists():
                locks.append(p.name)
        return locks

    def prepare_restore(self, package_name: str) -> Dict[str, Any]:
        # 1. Validate package exists
        snaps_dir = self.paths.backups_snapshots_dir()
        pkg_dir = snaps_dir / package_name
        man_path = pkg_dir / "manifest.json"
        
        if not pkg_dir.exists() or not man_path.exists():
            return {"ok": False, "message": f"Backup package '{package_name}' not found or missing manifest."}
            
        try:
            with open(man_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            return {"ok": False, "message": f"Failed to read backup manifest: {e}"}

        # 2. Check locks (Excel locks)
        locked_files = self._check_workbook_locks()
        if locked_files:
            return {
                "ok": False, 
                "message": f"Cannot prepare restore. Workbooks are currently locked/open in Excel: {', '.join(locked_files)}. Please close them.",
                "locked": True
            }

        # 3. Create mandatory pre-restore backup
        pre_backup_res = self.create_snapshot(
            reason=f"Pre-restore safety backup before restoring {package_name}",
            protected=True,
            retention_class="pre_restore",
            force=True
        )
        
        if not pre_backup_res.get("ok"):
            return {
                "ok": False,
                "message": f"Mandatory pre-restore backup failed. Restoration aborted. Reason: {pre_backup_res.get('message')}"
            }

        # 4. Generate restore payload for the external utility
        payload = {
            "target_package": package_name,
            "target_package_path": str(pkg_dir),
            "manifest": manifest,
            "pre_restore_backup": pre_backup_res["package_name"],
            "timestamp": datetime.now().isoformat(),
            "status": "ready_for_external_utility"
        }
        
        payload_path = self.paths.state_dir() / "pending_restore.json"
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        return {
            "ok": True,
            "message": "Pre-restore backup completed successfully. Ready for external recovery utility.",
            "pre_restore_package": pre_backup_res["package_name"],
            "payload_path": str(payload_path)
        }
