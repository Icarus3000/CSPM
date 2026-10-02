"""Reconcile an invoice reversal on a backed-up candidate under a shared checkout.

Defaults to read-only inspection. --apply runs the normal reversal service on
an isolated copy, checks integrity and saved accounting evidence, atomically
replaces the unchanged local workbook, then publishes through SyncService.
"""
from collections import Counter
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
from repositories.excel_repo import ExcelRepo
from services.backup_service import BackupService
from services.invoice_draft_service import InvoiceDraftService
from services.invoice_reversal_service import TABLES, verify_reversal
from services.paths import AppPaths
from services.sync_service import SyncService
from services.workbook_integrity_service import WorkbookIntegrityService


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def error_counts(report):
    return Counter((i.code, i.sheet, i.table, i.column, i.value)
                   for i in report.issues if i.severity == "error")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("invoice")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--runtime-dir", type=Path,
                        default=Path(os.environ["LOCALAPPDATA"]) / "CSPM")
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    os.environ["CSPM_RUNTIME_DIR"] = str(runtime)
    settings = json.loads((runtime / "user_settings.json").read_text(encoding="utf-8"))
    paths = AppPaths(ROOT, Path(settings["localDataDir"]), Path(settings["masterDataDir"]))
    workbook = paths.workbook_path()
    if not workbook.is_file():
        raise FileNotFoundError(workbook)
    if not args.apply:
        try:
            result = verify_reversal(InvoiceDraftService(ExcelRepo(paths))._read_tables_once(list(TABLES)), args.invoice)
        except ValueError as exc:
            result = {"ok": False, "invoiceNum": args.invoice, "message": str(exc)}
        print(json.dumps(result, indent=2))
        return 0

    sync = SyncService(paths)
    checkout = sync.checkout_from_cloud()
    if not checkout.get("ok"):
        raise RuntimeError(checkout)
    result = {"invoiceNum": args.invoice, "checkout": checkout}
    committed = False
    try:
        sync.assert_write_lease()
        source_hash = sha(workbook)
        backup = BackupService(paths).create_snapshot(
            reason=f"Before verified reversal reconciliation: {args.invoice}",
            protected=True, retention_class="manual", force=True)
        if not backup.get("ok"):
            raise RuntimeError(f"Backup failed: {backup}")
        result["backup"] = backup
        candidate_dir = runtime / "reconciliation" / (
            args.invoice + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{os.getpid()}")
        candidate_dir.mkdir(parents=True, exist_ok=False)
        for name in ("CSPM.xlsm", "Dockets.xlsm"):
            shutil.copy2(paths.data_dir() / name, candidate_dir / name)
        candidate_paths = AppPaths(ROOT, candidate_dir)
        integrity = WorkbookIntegrityService(candidate_paths)
        before = integrity.check()
        repo = ExcelRepo(candidate_paths)
        svc = InvoiceDraftService(repo)
        svc.reverse_invoice(args.invoice)
        evidence = verify_reversal(InvoiceDraftService(ExcelRepo(candidate_paths))._read_tables_once(list(TABLES)), args.invoice)
        after = integrity.check()
        new_errors = error_counts(after) - error_counts(before)
        if new_errors:
            raise RuntimeError(f"Candidate introduced integrity errors: {new_errors}")
        result.update({"candidate": str(candidate_dir), "evidence": evidence,
                       "integrityBefore": before.as_dict()["summary"],
                       "integrityAfter": after.as_dict()["summary"], "beforeSha256": source_hash})
        sync.assert_write_lease()
        if sha(workbook) != source_hash:
            raise RuntimeError("Local workbook changed during repair. Candidate was not promoted.")
        replacement = workbook.with_name("CSPM.reversal-pending.xlsm")
        if replacement.exists():
            raise FileExistsError(replacement)
        shutil.copy2(candidate_paths.workbook_path(), replacement)
        if sha(replacement) != sha(candidate_paths.workbook_path()):
            raise RuntimeError("Replacement hash differs from the verified candidate.")
        os.replace(replacement, workbook)
        committed = True
        result["savedEvidence"] = verify_reversal(
            InvoiceDraftService(ExcelRepo(paths))._read_tables_once(list(TABLES)), args.invoice)
        result["afterSha256"] = sha(workbook)
        result["publish"] = sync.publish_and_release()
        if not result["publish"].get("ok"):
            raise RuntimeError(f"Local repair saved; cloud publication requires attention: {result['publish']}")
        if sha(workbook) != sha(paths.master_data_dir() / "CSPM.xlsm"):
            raise RuntimeError("Local and shared workbook hashes differ after publication.")
        result["ok"] = True
        report = candidate_dir / "reconciliation_report.json"
        report.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "report": str(report), "evidence": result["savedEvidence"],
                          "backup": backup, "publish": result["publish"]}, indent=2, default=str))
    finally:
        # A failed candidate is never published. Once saved, the verified local
        # repair stays available for recovery if cloud promotion was refused.
        if not sync._shutdown_complete:
            sync._release_checkout_lease()
        if committed and not result.get("ok"):
            print("Verified local repair is saved; retain the candidate and backup for recovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
