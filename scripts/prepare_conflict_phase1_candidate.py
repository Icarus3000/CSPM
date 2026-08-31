"""Prepare or atomically promote the governed conflict Phase 1 workbook repair.

The default action is candidate-only.  Promotion is refused unless all three
reviewed historical receipt records have explicit account mappings and the
candidate passes the canonical integrity checker with zero errors and warnings.
No live/cloud workbook is ever a permitted target.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence
from uuid import uuid4
from zipfile import ZipFile

from openpyxl import load_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "src" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from domain import schema_constants as sc  # noqa: E402
from domain.ap_schema import (  # noqa: E402
    AP_BILLS_HEADERS,
    AP_BILLS_SHEET,
    AP_BILLS_TABLE,
    AP_PAYMENTS_HEADERS,
    AP_PAYMENTS_SHEET,
    AP_PAYMENTS_TABLE,
)
from repositories.ap_workbook_repository import _close_workbook, _table_context  # noqa: E402
from repositories.excel_repo import (  # noqa: E402
    ExcelRepo,
    TBL_TRANSACTION_ACCOUNTS,
    TBL_TRANSACTION_BUSINESS_UNITS,
    TBL_TRANSACTIONS_MASTER,
)
from services.paths import AppPaths  # noqa: E402
from services.workbook_integrity_service import WorkbookIntegrityService  # noqa: E402


REPOSITORY_WORKBOOK = (PROJECT_ROOT / "data" / "CSPM.xlsm").resolve()
BACKUP_ROOT = (PROJECT_ROOT / "backups" / "CSPM").resolve()
REVIEWED_RECEIPT_IDS = (
    "TXN_1ae98b316a",
    "TXN_7cae369d3f",
    "TXN_1ae4c6aaa6",
)


class Phase1RepairRefused(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def package_fingerprint(path: Path) -> dict[str, Any]:
    with ZipFile(path) as package:
        names = set(package.namelist())
        content_types = package.read("[Content_Types].xml")
        vba_name = "xl/vbaProject.bin"
        return {
            "memberCount": len(names),
            "macroEnabled": (
                b"application/vnd.ms-excel.sheet.macroEnabled.main+xml"
                in content_types
            ),
            "vbaPresent": vba_name in names,
            "vbaSha256": (
                hashlib.sha256(package.read(vba_name)).hexdigest().upper()
                if vba_name in names
                else ""
            ),
        }


def _parse_account_mappings(values: Sequence[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for raw in values:
        record_id, separator, account_code = str(raw).partition("=")
        record_id = record_id.strip()
        account_code = account_code.strip()
        if not separator or not record_id or not account_code:
            raise Phase1RepairRefused(
                "Each --account-map must be RECORD_ID=ACCOUNT_CODE."
            )
        if record_id not in REVIEWED_RECEIPT_IDS:
            raise Phase1RepairRefused(
                f"Account mapping is not authorized for record {record_id}."
            )
        if record_id in mappings:
            raise Phase1RepairRefused(f"Duplicate account mapping for {record_id}.")
        mappings[record_id] = account_code
    return mappings


def _assert_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == BACKUP_ROOT or BACKUP_ROOT not in resolved.parents:
        raise Phase1RepairRefused(
            "Candidate output must be a child directory of backups/CSPM."
        )
    if resolved.exists():
        raise Phase1RepairRefused("Candidate output directory already exists.")
    return resolved


def _migrate_ap_headers(path: Path) -> None:
    workbook = load_workbook(path, keep_vba=True, data_only=False)
    try:
        _table_context(
            workbook,
            AP_BILLS_SHEET,
            AP_BILLS_TABLE,
            AP_BILLS_HEADERS,
        )
        _table_context(
            workbook,
            AP_PAYMENTS_SHEET,
            AP_PAYMENTS_TABLE,
            AP_PAYMENTS_HEADERS,
        )
        workbook.save(path)
    finally:
        _close_workbook(workbook)


def _ensure_system_references(repo: ExcelRepo) -> dict[str, int]:
    tables = repo._read_table_rows_bulk(
        [TBL_TRANSACTION_ACCOUNTS, TBL_TRANSACTION_BUSINESS_UNITS]
    )
    accounts = [
        repo._canonicalize_transaction_account_row(row)
        for row in tables.get(TBL_TRANSACTION_ACCOUNTS.table, [])
    ]
    units = [
        repo._canonicalize_transaction_business_unit_row(row)
        for row in tables.get(TBL_TRANSACTION_BUSINESS_UNITS.table, [])
    ]
    account_matches = [
        row
        for row in accounts
        if str(row.get(sc.COL_TXN_ACCOUNT_CODE) or "").strip().casefold()
        == sc.SYSTEM_ACCOUNT_AP_PAYABLE.casefold()
    ]
    if len(account_matches) > 1:
        raise Phase1RepairRefused("The system A/P account is duplicated.")
    if account_matches:
        if repo._to_bool_int(
            account_matches[0].get(sc.COL_TXN_ACCOUNT_ACTIVE), default=1
        ) != 1:
            raise Phase1RepairRefused(
                "The system A/P account exists but is retired; a factual decision is required."
            )
    else:
        accounts.append(
            {
                sc.COL_TXN_ACCOUNT_CODE: sc.SYSTEM_ACCOUNT_AP_PAYABLE,
                sc.COL_TXN_ACCOUNT_NAME: sc.SYSTEM_ACCOUNT_AP_PAYABLE_NAME,
                sc.COL_TXN_ACCOUNT_KIND: sc.SYSTEM_ACCOUNT_AP_PAYABLE_KIND,
                sc.COL_TXN_ACCOUNT_OWNER: "",
                sc.COL_TXN_ACCOUNT_ACTIVE: 1,
                sc.COL_TXN_ACCOUNT_ALIASES: "",
            }
        )

    unit_matches = [
        row
        for row in units
        if str(row.get(sc.COL_TXN_BUSINESS_UNIT_NAME) or "").strip().casefold()
        == sc.SYSTEM_BUSINESS_UNIT_LEGAL_PRACTICE.casefold()
    ]
    if len(unit_matches) > 1:
        raise Phase1RepairRefused("The system legal-practice business unit is duplicated.")
    if unit_matches:
        if repo._to_bool_int(
            unit_matches[0].get(sc.COL_TXN_BUSINESS_UNIT_ACTIVE), default=1
        ) != 1:
            raise Phase1RepairRefused(
                "The legal-practice business unit exists but is retired; a factual decision is required."
            )
    else:
        units.append(
            {
                sc.COL_TXN_BUSINESS_UNIT_NAME: sc.SYSTEM_BUSINESS_UNIT_LEGAL_PRACTICE,
                sc.COL_TXN_BUSINESS_UNIT_OWNER: "",
                sc.COL_TXN_BUSINESS_UNIT_ACTIVE: 1,
            }
        )
    repo._write_table_rows_bulk(
        {
            TBL_TRANSACTION_ACCOUNTS: accounts,
            TBL_TRANSACTION_BUSINESS_UNITS: units,
        }
    )
    return {
        "systemAccountsAdded": 0 if account_matches else 1,
        "systemBusinessUnitsAdded": 0 if unit_matches else 1,
    }


def _apply_account_mappings(repo: ExcelRepo, mappings: Mapping[str, str]) -> int:
    if not mappings:
        return 0
    accounts = repo.list_transaction_accounts(include_inactive=True)
    active_codes = {
        str(row.get("accountCode") or "").strip().casefold(): str(
            row.get("accountCode") or ""
        ).strip()
        for row in accounts
        if int(row.get("active", 0) or 0) == 1
    }
    canonical_mappings: dict[str, str] = {}
    for record_id, account_code in mappings.items():
        canonical = active_codes.get(account_code.casefold())
        if not canonical:
            raise Phase1RepairRefused(
                f"Mapped account for {record_id} is not an active AccountCode."
            )
        canonical_mappings[record_id] = canonical

    rows = [
        repo._canonicalize_transaction_row(row)
        for row in repo._read_table_rows(TBL_TRANSACTIONS_MASTER)
    ]
    counts = {record_id: 0 for record_id in canonical_mappings}
    for row in rows:
        record_id = str(row.get(sc.COL_TXN_ID) or "").strip()
        if record_id in canonical_mappings:
            row[sc.COL_TXN_FROM_ACCOUNT] = canonical_mappings[record_id]
            counts[record_id] += 1
    if any(count != 1 for count in counts.values()):
        raise Phase1RepairRefused(
            "Each reviewed historical receipt mapping must match exactly one row."
        )
    repo._write_table_rows(TBL_TRANSACTIONS_MASTER, rows)
    return len(canonical_mappings)


def _integrity_summary(path: Path) -> dict[str, Any]:
    report = WorkbookIntegrityService(AppPaths(root=PROJECT_ROOT)).check(
        workbook_path=path,
        schema_path=PROJECT_ROOT / "schema" / "workbook_schema.yml",
    )
    return {
        "ok": report.ok,
        "tablesChecked": report.tables_checked,
        "rowsChecked": report.rows_checked,
        "errors": report.error_count,
        "warnings": report.warning_count,
        "issueInventory": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "table": issue.table,
                "field": issue.column,
                "recordId": issue.record_id,
                "referenceIdentifier": issue.value,
                "referenceTarget": issue.reference_target,
                "referenceState": issue.reference_state,
            }
            for issue in report.issues
        ],
    }


def prepare_candidate(
    *,
    output_dir: Path,
    account_mappings: Mapping[str, str],
) -> dict[str, Any]:
    output_dir = _assert_output_dir(output_dir)
    if not REPOSITORY_WORKBOOK.is_file():
        raise Phase1RepairRefused("Repository CSPM workbook is missing.")
    output_dir.mkdir(parents=True)
    source_hash = sha256_file(REPOSITORY_WORKBOOK)
    source_package = package_fingerprint(REPOSITORY_WORKBOOK)
    candidate_path = output_dir / "CSPM.candidate.xlsm"
    backup_path = output_dir / "CSPM.before-phase1.xlsm"
    audit_path = output_dir / "phase1_candidate_audit.json"
    shutil.copy2(REPOSITORY_WORKBOOK, backup_path)
    shutil.copy2(REPOSITORY_WORKBOOK, candidate_path)
    if sha256_file(backup_path) != source_hash or sha256_file(candidate_path) != source_hash:
        raise Phase1RepairRefused("Candidate or backup copy failed hash verification.")

    repo = ExcelRepo(AppPaths(root=PROJECT_ROOT, override_data_dir=output_dir))
    # ExcelRepo expects the governed filename at the override root.
    governed_candidate_path = output_dir / "CSPM.xlsm"
    os.replace(candidate_path, governed_candidate_path)
    schema_result = repo.ensure_schema()
    _migrate_ap_headers(governed_candidate_path)
    reference_result = _ensure_system_references(repo)
    mappings_applied = _apply_account_mappings(repo, account_mappings)
    candidate_package = package_fingerprint(governed_candidate_path)
    if source_package["macroEnabled"] != candidate_package["macroEnabled"]:
        raise Phase1RepairRefused("Candidate macro-enabled package type changed.")
    if source_package["vbaPresent"] != candidate_package["vbaPresent"]:
        raise Phase1RepairRefused("Candidate VBA presence changed.")
    if source_package["vbaSha256"] != candidate_package["vbaSha256"]:
        raise Phase1RepairRefused("Candidate VBA payload changed.")
    integrity = _integrity_summary(governed_candidate_path)
    audit = {
        "operation": "conflict-phase1-candidate-only",
        "createdAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceClassification": "repository_workbook_snapshot",
        "sourceSha256": source_hash,
        "backupSha256": sha256_file(backup_path),
        "candidateSha256": sha256_file(governed_candidate_path),
        "schemaResult": schema_result,
        "referenceRepairs": reference_result,
        "historicalReceiptMappingsApplied": mappings_applied,
        "historicalReceiptMappingRecordIds": sorted(account_mappings),
        "packageBefore": source_package,
        "packageAfter": candidate_package,
        "integrity": integrity,
        "promotion": "not-requested",
        "rollback": {
            "backup": "CSPM.before-phase1.xlsm",
            "expectedSha256": source_hash,
        },
    }
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "outputDirectory": str(output_dir),
        "candidate": str(governed_candidate_path),
        "backup": str(backup_path),
        "audit": str(audit_path),
        "sourceSha256": source_hash,
        "candidateSha256": audit["candidateSha256"],
        "referenceRepairs": reference_result,
        "historicalReceiptMappingsApplied": mappings_applied,
        "integrity": integrity,
    }


def promote_candidate(
    result: Mapping[str, Any],
    *,
    expected_source_sha256: str,
) -> dict[str, Any]:
    integrity = dict(result.get("integrity") or {})
    if integrity.get("errors") != 0 or integrity.get("warnings") != 0:
        raise Phase1RepairRefused(
            "Promotion requires a candidate with zero integrity errors and warnings."
        )
    if int(result.get("historicalReceiptMappingsApplied", 0) or 0) != len(
        REVIEWED_RECEIPT_IDS
    ):
        raise Phase1RepairRefused(
            "Promotion requires all reviewed historical receipt account mappings."
        )
    current_hash = sha256_file(REPOSITORY_WORKBOOK)
    if current_hash != expected_source_sha256.upper():
        raise Phase1RepairRefused("Fresh-source hash guard refused promotion.")
    candidate = Path(str(result["candidate"])).resolve()
    backup = Path(str(result["backup"])).resolve()
    if sha256_file(backup) != current_hash:
        raise Phase1RepairRefused("Verified rollback backup no longer matches the source.")
    staged = REPOSITORY_WORKBOOK.with_name(
        f".{REPOSITORY_WORKBOOK.stem}.phase1-{uuid4().hex}.staged"
        f"{REPOSITORY_WORKBOOK.suffix}"
    )
    try:
        shutil.copy2(candidate, staged)
        if sha256_file(staged) != sha256_file(candidate):
            raise Phase1RepairRefused("Same-volume promotion stage failed hash verification.")
        os.replace(staged, REPOSITORY_WORKBOOK)
    finally:
        staged.unlink(missing_ok=True)
    promoted_integrity = _integrity_summary(REPOSITORY_WORKBOOK)
    if promoted_integrity["errors"] or promoted_integrity["warnings"]:
        raise Phase1RepairRefused(
            "Promoted workbook failed reopen integrity verification; restore the verified backup."
        )
    return {
        "status": "promoted-and-reverified",
        "beforeSha256": current_hash,
        "afterSha256": sha256_file(REPOSITORY_WORKBOOK),
        "rollbackBackup": str(backup),
        "integrity": promoted_integrity,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--account-map", action="append", default=[])
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--expected-source-sha256", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or (
        BACKUP_ROOT / f"conflict_phase1_candidate_{stamp}"
    )
    try:
        mappings = _parse_account_mappings(args.account_map)
        result = prepare_candidate(
            output_dir=output_dir,
            account_mappings=mappings,
        )
        if args.promote:
            if not args.expected_source_sha256:
                raise Phase1RepairRefused(
                    "--expected-source-sha256 is required for promotion."
                )
            result["promotion"] = promote_candidate(
                result,
                expected_source_sha256=args.expected_source_sha256,
            )
        print(json.dumps({"ok": True, **result}, indent=2))
        return 0
    except Phase1RepairRefused as exc:
        print(
            json.dumps(
                {"ok": False, "status": "refused", "message": str(exc)},
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
