import sys
import shutil
from pathlib import Path

# Fix import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import the check script to get the exact list of forbidden paths
try:
    from scripts.check_repo_hygiene import collect_findings, PROJECT_ROOT
except ImportError:
    print("Cannot import check_repo_hygiene. Must run from project root.")
    sys.exit(1)

def clean_hygiene() -> int:
    print("Scanning for hygiene violations...")
    findings = collect_findings()
    if not findings:
        print("Repo is already clean!")
        return 0
    
    deleted_count = 0
    failed_count = 0
    for finding in findings:
        target_path = PROJECT_ROOT / finding.path
        try:
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()
                deleted_count += 1
            elif target_path.is_dir():
                shutil.rmtree(target_path)
                deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {finding.path}: {e}")
            failed_count += 1

    print(f"Deleted {deleted_count} items. Failed {failed_count}.")
    if failed_count > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(clean_hygiene())
