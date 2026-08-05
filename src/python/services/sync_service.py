import os
import shutil
import logging
import traceback
import json
from pathlib import Path
from typing import Optional
from services.paths import AppPaths
import ctypes

logger = logging.getLogger("sync_service")

class SyncService:
    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.state_file = self.paths.runtime_dir() / "sync_state.json"

    def _get_state(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {"offline_dirty": False, "last_push_time": 0.0}
        return {"offline_dirty": False, "last_push_time": 0.0}

    def _save_state(self, state: dict):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def _get_files_to_sync(self):
        return ["CSPM.xlsm", "Dockets.xlsm"]

    def _sync_file(self, src: Path, dest: Path, file_name: str) -> bool:
        if not src.exists():
            return False
            
        try:
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                logger.info(f"SyncService: Copied {file_name} from {src} to {dest}")
                return True
                
            src_mtime = src.stat().st_mtime
            dest_mtime = dest.stat().st_mtime
            
            # Allow 1 second variance for file system granularity
            if src_mtime > (dest_mtime + 1):
                # We should back up the dest if it's being overwritten just in case!
                backup_dest = dest.with_name(f"{dest.name}.bak")
                shutil.copy2(dest, backup_dest)
                
                shutil.copy2(src, dest)
                logger.info(f"SyncService: Overwrote {file_name} in {dest} because {src} was newer.")
                return True
            else:
                logger.info(f"SyncService: {file_name} is up to date.")
                return True
        except Exception as e:
            logger.error(f"SyncService failed to sync {file_name}: {e}\n{traceback.format_exc()}")
            return False

    def pull_from_master(self) -> None:
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            return
            
        local_dir = self.paths.data_dir()
        state = self._get_state()
        
        if state.get("offline_dirty"):
            logger.warning("SyncService: offline_dirty is TRUE. Checking for conflicts before pull.")
            conflict_detected = False
            for fname in self._get_files_to_sync():
                master_file = master_dir / fname
                if master_file.exists():
                    master_mtime = master_file.stat().st_mtime
                    if master_mtime > state.get("last_push_time", 0):
                        conflict_detected = True
                        break
            
            if conflict_detected:
                # We have a conflict!
                # Show native MessageBox to block startup and ask the user.
                # MB_YESNO = 4, MB_ICONWARNING = 48, IDYES = 6, IDNO = 7
                # Added MB_TOPMOST (0x40000) and MB_SETFOREGROUND (0x10000) to prevent freeze behind splash
                msg = (
                    "Sync Conflict Detected!\n\n"
                    "You have unsaved offline changes locally, but the Cloud Master "
                    "files were also modified by someone else while you were offline.\n\n"
                    "Do you want to Keep your Local changes (Overwrite Cloud)?\n\n"
                    "Click YES to Keep Local (Overwrite Cloud).\n"
                    "Click NO to Use Cloud (Discard Local)."
                )
                response = ctypes.windll.user32.MessageBoxW(0, msg, "CSPM Sync Conflict", 4 | 48 | 0x40000 | 0x10000)
                if response == 6: # YES - Keep Local
                    logger.info("User chose to Keep Local. Pushing to master to resolve conflict.")
                    self.push_to_master()
                    return
                else: # NO - Use Cloud
                    logger.info("User chose to Use Cloud. Proceeding with pull, wiping local offline changes.")
                    state["offline_dirty"] = False
                    self._save_state(state)
            else:
                logger.info("SyncService: offline_dirty is true, but cloud hasn't changed. Skipping pull.")
                return

        logger.info(f"SyncService: PULL from {master_dir} to {local_dir}")
        for fname in self._get_files_to_sync():
            self._sync_file(master_dir / fname, local_dir / fname, fname)

    def push_to_master(self) -> None:
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            return
            
        local_dir = self.paths.data_dir()
        logger.info(f"SyncService: PUSH from {local_dir} to {master_dir}")
        
        success = True
        import time
        current_time = time.time()
        for fname in self._get_files_to_sync():
            if not self._sync_file(local_dir / fname, master_dir / fname, fname):
                success = False
                
        state = self._get_state()
        if success:
            state["offline_dirty"] = False
            state["last_push_time"] = current_time
        else:
            logger.warning("SyncService: Push failed (likely offline). Setting offline_dirty flag.")
            state["offline_dirty"] = True
        self._save_state(state)
