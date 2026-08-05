from __future__ import annotations

from services.paths import AppPaths
from services.backup_service import BackupService


def main() -> int:
    root = AppPaths.project_root()
    svc = BackupService(AppPaths(root))
    out = svc.backup_workbook_if_exists(force=True)
    if out:
        print(f"Backup created: {out}")
        return 0
    print("No workbook found.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
