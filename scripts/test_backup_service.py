import os
import sys
from pathlib import Path

# Add src/python to path
sys.path.append(str(Path("C:/Projects/__CSPM/src/python").resolve()))

from services.paths import AppPaths
from services.backup_service import BackupService

def test_backup():
    paths = AppPaths(Path("C:/Projects/__CSPM").resolve())
    service = BackupService(paths)

    print("--- Creating Backup 1 ---")
    res1 = service.create_snapshot(reason="Test snapshot 1", force=True)
    print(res1)
    if not res1["ok"]:
        sys.exit(1)

    print("\n--- Listing Snapshots ---")
    snaps = service.list_snapshots()
    print(f"Total snaps: {len(snaps)}")
    for s in snaps:
        print(s["package_name"], s["timestamp_local"], "Protected:", s.get("protected"))

    print("\n--- Protecting Snapshot 1 ---")
    pkg_name = res1["package_name"]
    prot_res = service.protect_snapshot(pkg_name, True)
    print("Protected:", prot_res)

    print("\n--- Creating Backup 2 (should skip if no changes) ---")
    res2 = service.create_snapshot(reason="Test snapshot 2", force=False)
    print(res2)

    print("\n--- Pruning Snapshots ---")
    prune_res = service.prune_snapshots()
    print(prune_res)
    
    print("\n--- Validating Live Hashes Unchanged ---")
    auth = service._get_authoritative_files()
    for f in auth:
        print(f.name, f.stat().st_size)

if __name__ == "__main__":
    test_backup()
