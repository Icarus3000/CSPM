"""Guarded one-time repair for vendor expense rows incorrectly imported as A/R.

By default this command prints a read-only repair plan.  Use ``--apply`` to
create a protected snapshot and atomically remove only the proven artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from repositories.excel_repo import ExcelRepo
from services.backup_service import BackupService
from services.paths import AppPaths


def _default_data_dir() -> Path:
    configured = os.environ.get("CSPM_DATA_DIR", "").strip()
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "CSPM" / "data"
    return PROJECT_ROOT / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", default="CIPO", help="Vendor whose imported A/R artifacts will be repaired.")
    parser.add_argument("--data-dir", type=Path, default=_default_data_dir(), help="Folder containing CSPM.xlsm.")
    parser.add_argument("--apply", action="store_true", help="Back up and apply the repair. Omit for a read-only plan.")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    workbook_path = data_dir / "CSPM.xlsm"
    if not workbook_path.is_file():
        print(json.dumps({"ok": False, "message": f"Workbook not found: {workbook_path}"}, indent=2))
        return 2

    paths = AppPaths(root=PROJECT_ROOT, override_data_dir=data_dir)
    repo = ExcelRepo(paths)
    plan = repo.repair_rogue_vendor_receivables(args.vendor, apply=False)
    if not plan.get("ok"):
        print(json.dumps(plan, indent=2))
        return 1
    if not args.apply:
        print(json.dumps(plan, indent=2))
        return 0
    if not plan.get("removed", {}).get("receivables"):
        print(json.dumps(plan, indent=2))
        return 0

    backup = BackupService(paths).create_snapshot(
        reason=f"Pre-repair snapshot: rogue {args.vendor} vendor receivables",
        protected=True,
        retention_class="manual",
        force=True,
    )
    if not backup.get("ok"):
        print(json.dumps({"ok": False, "message": "Backup failed; repair was not run.", "backup": backup}, indent=2))
        return 1

    result = repo.repair_rogue_vendor_receivables(args.vendor, apply=True)
    verification = repo.repair_rogue_vendor_receivables(args.vendor, apply=False)
    statement_choices = repo.list_statement_billing_clients()
    vendor_still_selectable = any(
        str(row.get("name", "")).strip().casefold() == str(args.vendor).strip().casefold()
        for row in statement_choices
    )
    result["backup"] = {
        "packageName": backup.get("package_name", ""),
        "path": str(paths.backups_snapshots_dir() / str(backup.get("package_name", ""))),
    }
    result["verification"] = {
        "remainingRogueReceivables": verification.get("removed", {}).get("receivables", 0),
        "vendorStillSelectableForStatement": vendor_still_selectable,
    }
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") and not vendor_still_selectable and not result["verification"]["remainingRogueReceivables"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
