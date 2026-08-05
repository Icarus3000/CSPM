import os
import sys
import json
import shutil
import time
import uuid
import subprocess
import hashlib
from pathlib import Path

def get_forbidden_paths():
    """Returns a list of resolved Path objects that are strictly forbidden."""
    forbidden = []
    
    # 1. Project data directory
    forbidden.append(Path(__file__).resolve().parent.parent / "data")
    
    # 2. Configured live local-data directory
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    forbidden.append(local_app_data / "CSPM" / "data")
    
    # 3. Configured live master-data directory
    user_docs = Path.home() / "Documents"
    forbidden.append(user_docs / "CSPM_Protected_Backups")
    
    # 4. OneDrive / SharePoint
    for key, val in os.environ.items():
        if "onedrive" in key.lower() or "sharepoint" in key.lower():
            forbidden.append(Path(val))
    
    # 5. Normal CSPM runtime root
    forbidden.append(local_app_data / "CSPM")
    
    return [p.resolve(strict=False) for p in forbidden if str(p) != '.']

def is_path_forbidden(target_path: Path) -> bool:
    """Case-insensitively checks if target_path equals or is inside any forbidden path."""
    resolved_target = target_path.resolve(strict=False)
    target_str = str(resolved_target).lower()
    
    # Also explicitly block live workbooks
    root_dir = Path(__file__).resolve().parent.parent
    live_c = (root_dir / "data" / "CSPM.xlsm").resolve(strict=False)
    live_d = (root_dir / "data" / "Dockets.xlsm").resolve(strict=False)
    
    if target_str == str(live_c).lower() or target_str == str(live_d).lower():
        return True
        
    for forbidden in get_forbidden_paths():
        forbidden_str = str(forbidden).lower()
        if target_str == forbidden_str or target_str.startswith(forbidden_str + os.sep):
            return True
            
    return False

def get_harness_root():
    """Generates a unique harness session directory."""
    session_id = uuid.uuid4().hex[:8]
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "CSPM_TEST_HARNESS" / f"OfflineSyncTest_{session_id}"
    return root.resolve(strict=False)

def main():
    print("==================================================")
    print("       CSPM OFFLINE CONFLICT TEST HARNESS")
    print("==================================================")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        if len(sys.argv) < 3:
            print("ERROR: Cleanup requires the exact harness root path as the second argument.")
            sys.exit(1)
        
        target_cleanup = Path(sys.argv[2]).resolve(strict=False)
        target_str = str(target_cleanup).lower()
        base_harness_dir = str(Path(os.environ.get("LOCALAPPDATA", "")) / "CSPM_TEST_HARNESS").lower()
        
        if not target_str.startswith(base_harness_dir):
            print(f"ABORT: Cleanup target {target_cleanup} escapes the base harness directory!")
            sys.exit(1)
            
        if target_cleanup.exists():
            shutil.rmtree(target_cleanup)
            print(f"Cleanup complete for: {target_cleanup}")
        return

    root = get_harness_root()
    if is_path_forbidden(root):
        print(f"ABORT: Generated harness root {root} overlaps with forbidden production paths!")
        sys.exit(1)
        
    print(f"Harness Root: {root}")
    print("Supported Scope: PROMPT VISIBILITY ONLY. Do not click 'Keep Local' or 'Use Cloud'.")

    local_data = root / "local_data"
    master_data = root / "master_data"
    state_data = root / "state"
    
    local_data.mkdir(parents=True, exist_ok=True)
    master_data.mkdir(parents=True, exist_ok=True)
    state_data.mkdir(parents=True, exist_ok=True)
    
    master_wb = master_data / "CSPM.xlsm"
    
    # We must use a valid workbook. If governed fixture doesn't exist, we must fail.
    fixture_path = Path(os.environ.get("LOCALAPPDATA", "")) / "CSPM" / "Validation" / "GovernedFixtures" / "DummyMacro.xlsm"
    if not fixture_path.exists():
        print(f"ABORT: Required sanitized fixture not found at {fixture_path}")
        sys.exit(1)
        
    shutil.copy2(fixture_path, master_wb)
    time.sleep(0.1) # ensure time separation
    
    local_state = local_data / "sync_state.json"
    state = {
        "offline_dirty": True,
        "last_push_time": (time.time() - 3600), # 1 hour ago
        "last_pull_time": (time.time() - 3600)
    }
    local_state.write_text(json.dumps(state))
    
    print("\nPreconditions met safely.")
    print(f"Master workbook created at {master_wb} (newer than last push time).")
    print(f"Local state created at {local_state} (offline_dirty=True).")
    
    print("\n--- LAUNCH INSTRUCTIONS ---")
    print("To test manually, open a normal PowerShell and run:")
    print(f"$env:CSPM_DATA_DIR = '{local_data}'")
    print(f"$env:CSPM_MASTER_DIR = '{master_data}'")
    print(f"$env:CSPM_STATE_DIR = '{state_data}'")
    print(".\\dist\\CSPM\\CSPM.exe")
    print(f"After test, run: python scripts/test_offline_conflict_harness.py --cleanup '{root}'")
    print("\nLogs will be captured in the state directory.")

if __name__ == "__main__":
    main()
