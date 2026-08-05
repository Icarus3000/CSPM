from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "src" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import (  # noqa: E402
    ExcelRepo,
    TBL_CLIENTS,
    TBL_CLIENT_PROFILES,
    _clean_text,
    _is_individual_entity_type,
    _split_person_name_parts,
)
from services.paths import AppPaths  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _client_names_by_id(repo: ExcelRepo) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for row in repo._read_table_rows(TBL_CLIENTS):
        client_id = _clean_text(row.get(sc.COL_CLIENT_ID))
        client_name = _clean_text(row.get(sc.COL_CLIENT_NAME))
        if client_id and client_name:
            names[client_id] = client_name
    return names


def migrate(root: Path, dry_run: bool = False) -> Dict[str, Any]:
    paths = AppPaths(root)
    workbook_path = paths.workbook_path()
    if not workbook_path.exists():
        raise FileNotFoundError(f"Active workbook not found: {workbook_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / "data" / "recovery_backups" / f"individual_client_names_{timestamp}"
    backup_path = backup_dir / workbook_path.name

    before_hash = _sha256(workbook_path)
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workbook_path, backup_path)

    repo = ExcelRepo(paths)
    if dry_run:
        schema_result = {
            "changed": False,
            "dryRunSkippedSchemaWrite": True,
            "schemaRequiresMigration": bool(repo.schema_requires_migration()),
        }
    else:
        schema_result = repo.ensure_schema()

    names_by_id = _client_names_by_id(repo)
    profile_rows = repo._read_table_rows(TBL_CLIENT_PROFILES)
    updated_rows: List[Dict[str, Any]] = []
    changed_profiles: List[Dict[str, str]] = []

    for row in profile_rows:
        next_row = dict(row)
        client_id = _clean_text(next_row.get(sc.COL_PROFILE_CLIENT_ID))
        entity_type = _clean_text(next_row.get(sc.COL_PROFILE_ENTITY_TYPE))
        if _is_individual_entity_type(entity_type):
            first_name = _clean_text(next_row.get(sc.COL_PROFILE_FIRST_NAME))
            middle_name = _clean_text(next_row.get(sc.COL_PROFILE_MIDDLE_NAME))
            last_name = _clean_text(next_row.get(sc.COL_PROFILE_LAST_NAME))
            source_name = (
                _clean_text(next_row.get(sc.COL_PROFILE_DISPLAY_NAME))
                or _clean_text(next_row.get(sc.COL_PROFILE_LEGAL_NAME))
                or names_by_id.get(client_id, "")
            )
            split_first, split_middle, split_last = _split_person_name_parts(source_name)

            changed = False
            if not first_name and split_first:
                next_row[sc.COL_PROFILE_FIRST_NAME] = split_first
                changed = True
            if not middle_name and split_middle:
                next_row[sc.COL_PROFILE_MIDDLE_NAME] = split_middle
                changed = True
            if not last_name and split_last:
                next_row[sc.COL_PROFILE_LAST_NAME] = split_last
                changed = True

            if changed:
                changed_profiles.append(
                    {
                        "clientId": client_id,
                        "displayName": source_name,
                        "firstName": _clean_text(next_row.get(sc.COL_PROFILE_FIRST_NAME)),
                        "middleName": _clean_text(next_row.get(sc.COL_PROFILE_MIDDLE_NAME)),
                        "lastName": _clean_text(next_row.get(sc.COL_PROFILE_LAST_NAME)),
                    }
                )

        updated_rows.append(next_row)

    if changed_profiles and not dry_run:
        repo._replace_table_rows(TBL_CLIENT_PROFILES, updated_rows)

    after_hash = _sha256(workbook_path)
    report = {
        "ok": True,
        "dryRun": bool(dry_run),
        "workbookPath": str(workbook_path),
        "backupPath": "" if dry_run else str(backup_path),
        "beforeSha256": before_hash,
        "afterSha256": after_hash,
        "schemaChanged": bool(schema_result.get("changed")),
        "schemaResult": schema_result,
        "profilesScanned": len(profile_rows),
        "individualProfilesUpdated": len(changed_profiles),
        "changedProfiles": changed_profiles,
    }

    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        report_path = backup_dir / "individual_client_name_migration_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["reportPath"] = str(report_path)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill first/middle/last names for Individual client profiles.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root. Defaults to this repository.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without writing the active workbook.")
    args = parser.parse_args()

    report = migrate(args.root.resolve(), dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
