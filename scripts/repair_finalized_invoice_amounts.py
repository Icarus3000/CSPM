"""Repair one invoice on an isolated candidate, then publish under a checkout.

Without --apply, only the disposable candidate is changed. Production promotion
requires an expected total, an audit reason, an unchanged source, a protected
backup, no new integrity errors, and a field-level check of all workbook tables.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo
from services.backup_service import BackupService
from services.invoice_draft_service import InvoiceDraftService
from services.paths import AppPaths
from services.sync_service import SyncService
from services.workbook_integrity_service import WorkbookIntegrityService


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def table_snapshot(path: Path) -> dict:
    workbook = load_workbook(path, keep_vba=True, data_only=False)
    try:
        tables = {}
        for sheet in workbook:
            for table in sheet.tables.values():
                left, top, right, bottom = range_boundaries(table.ref)
                headers = [sheet.cell(top, col).value for col in range(left, right + 1)]
                tables[table.name] = [dict(zip(headers, values)) for values in sheet.iter_rows(
                    min_row=top + 1, max_row=bottom, min_col=left,
                    max_col=right, values_only=True)]
        return tables
    finally:
        workbook.close()
        if workbook.vba_archive:
            workbook.vba_archive.close()


def macro_payload(path: Path) -> dict:
    with ZipFile(path) as package:
        return {name: hashlib.sha256(package.read(name)).hexdigest()
                for name in package.namelist() if name.casefold().endswith("vbaproject.bin")}


def equivalent(left, right) -> bool:
    if left == right or left in (None, "") and right in (None, ""):
        return True
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except InvalidOperation:
        return False


def verify_scope(before: dict, after: dict, invoice: str | dict) -> list:
    """Reject changes beyond the selected active invoices and correction types."""
    targets = {invoice: {"repairAmounts": True}} if isinstance(invoice, str) else invoice
    allowed = {
        sc.TBL_TIME: (sc.COL_TIME_INVOICE_REF, {
            sc.COL_TIME_INVOICE_TOTAL, sc.COL_TIME_INVOICE_AMOUNT_PAID,
            sc.COL_TIME_INVOICE_BALANCE_DUE, sc.COL_TIME_INVOICE_DATE,
            sc.COL_TIME_LOCK_AUDIT, sc.COL_TIME_NET, sc.COL_TIME_HST,
            sc.COL_TIME_TOTAL,
        }),
        sc.TBL_INVOICE_LOG: (sc.COL_INV_INVOICE_NUM, {
            sc.COL_INV_TOTAL_FEES, sc.COL_INV_TOTAL_TAX,
            sc.COL_INV_TOTAL_DISBURSEMENTS, sc.COL_INV_AGGREGATE_BILLED,
            sc.COL_INV_BILL_TO_SNAPSHOT,
        }),
        sc.TBL_RECEIVABLES: (sc.COL_RECV_INVOICE_NUM, {
            sc.COL_RECV_TOTAL_INVOICED, sc.COL_RECV_BALANCE_DUE,
        }),
        sc.TBL_LEDGER: (sc.COL_LEDGER_REFERENCE, {
            sc.COL_LEDGER_BILLINGS_EXCL_HST, sc.COL_LEDGER_HST_COLLECTED,
            sc.COL_LEDGER_RECEIVABLE,
        }),
        sc.TBL_TRANSACTIONS_MASTER: (sc.COL_TXN_INVOICE_REF, set()),
    }
    billing_fields = {
        sc.TBL_INVOICE_LOG: {sc.COL_INV_BILL_TO_CLIENT, sc.COL_INV_BILL_TO_SNAPSHOT, sc.COL_INV_SUB_CLIENT},
        sc.TBL_RECEIVABLES: {sc.COL_RECV_CLIENT, sc.COL_RECV_WORK_CLIENT},
        sc.TBL_LEDGER: {sc.COL_LEDGER_CLIENT_VENDOR, sc.COL_LEDGER_WORK_CLIENT},
        sc.TBL_TRANSACTIONS_MASTER: {sc.COL_TXN_CLIENT},
    }
    if before.keys() != after.keys():
        raise RuntimeError("Candidate changed the workbook table set.")
    changes = []
    for table, old_rows in before.items():
        new_rows = after[table]
        if len(old_rows) != len(new_rows):
            raise RuntimeError(f"Candidate changed row count in {table}.")
        for index, (old, new) in enumerate(zip(old_rows, new_rows)):
            if old.keys() != new.keys():
                raise RuntimeError(f"Candidate changed columns in {table}.")
            for field, value in old.items():
                if equivalent(value, new[field]):
                    continue
                reference, fields = allowed.get(table, (None, set()))
                correction = targets.get(old.get(reference), {})
                permitted = set(fields) if correction.get("repairAmounts") else set()
                if correction.get("billingClient"):
                    permitted |= billing_fields.get(table, set())
                if not reference or field not in permitted:
                    raise RuntimeError(f"Unrelated mutation: {table} row {index + 1}, {field}.")
                if table == sc.TBL_LEDGER:
                    category = str(old.get(sc.COL_LEDGER_CATEGORY)).casefold()
                    if category in {"payment", "receipt", "invoice reversal"} or (
                        field in fields and category != "revenue"
                    ):
                        raise RuntimeError("Candidate changed non-issuance ledger evidence.")
                if table == sc.TBL_TRANSACTIONS_MASTER and not (
                    old.get(sc.COL_TXN_FROM_ACCOUNT) == "ACCOUNTS_RECEIVABLE"
                    and old.get(sc.COL_TXN_TO_ACCOUNT) == "LEGAL_REVENUE"
                    and str(old.get(sc.COL_TXN_TYPE)).casefold() == "income"
                    and str(old.get(sc.COL_TXN_CATEGORY_CODE)).casefold() == "inc_legal_fees"
                ):
                    raise RuntimeError("Candidate changed a transaction outside verified invoice issuance.")
                changes.append(dict(table=table, row=index + 1, field=field,
                                    before=value, after=new[field]))
    return changes


def error_counts(report) -> Counter:
    return Counter((issue.code, issue.sheet, issue.table, issue.column, issue.value)
                   for issue in report.issues if issue.severity == "error")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("invoice", nargs="?")
    parser.add_argument("--expected-total", type=Decimal)
    parser.add_argument("--expected-tax", type=Decimal)
    parser.add_argument("--reason")
    parser.add_argument("--corrections-file", type=Path,
                        help="Private JSON array of reviewed invoice corrections.")
    parser.add_argument("--expected-source-sha256", help="Reviewed source hash required before candidate creation.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--runtime-dir", type=Path,
                        default=Path(os.environ["LOCALAPPDATA"]) / "CSPM")
    args = parser.parse_args()
    if args.corrections_file:
        if args.invoice or args.expected_total is not None or args.expected_tax is not None or args.reason:
            parser.error("Use either an invoice with its options or --corrections-file.")
        corrections = json.loads(args.corrections_file.read_text(encoding="utf-8"))
    else:
        corrections = [dict(invoice=args.invoice, expectedTotal=args.expected_total,
                            expectedTax=args.expected_tax, reason=args.reason, repairAmounts=True)]
    if not isinstance(corrections, list) or not corrections:
        parser.error("A nonempty reviewed correction list is required.")
    targets = {}
    for correction in corrections:
        if not isinstance(correction, dict):
            parser.error("Each correction must be a JSON object.")
        invoice = correction.get("invoice")
        reason = correction.get("reason")
        try:
            expected = Decimal(str(correction.get("expectedTotal")))
        except InvalidOperation:
            parser.error("Each correction requires a valid expected total.")
        if (not isinstance(invoice, str) or not invoice.strip() or invoice in targets
                or not isinstance(reason, str) or not reason.strip()
                or not expected.is_finite() or expected <= 0):
            parser.error("Each unique invoice requires a reason and finite positive expected total.")
        if not correction.get("repairAmounts") and not correction.get("billingClient"):
            parser.error("Each correction must select an amount or billing-client repair.")
        targets[invoice] = correction
    runtime = args.runtime_dir.resolve()
    os.environ["CSPM_RUNTIME_DIR"] = str(runtime)
    settings = json.loads((runtime / "user_settings.json").read_text(encoding="utf-8"))
    paths = AppPaths(ROOT, Path(settings["localDataDir"]), Path(settings["masterDataDir"]))
    from backend.data_verification import configure
    configure(settings=settings)
    sync = SyncService(paths)
    committed = False
    result = {"invoices": list(targets), "applied": False}
    candidate = runtime / "reconciliation" / (
        "invoice_amount_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8])
    try:
        if args.apply:
            checkout = sync.checkout_from_cloud()
            if not checkout.get("ok") or checkout.get("readOnly"):
                raise RuntimeError(f"Writable checkout refused: {checkout}")
            sync.assert_write_lease()
            result["checkout"] = checkout
        baseline_hashes = {name: sha(paths.data_dir() / name) for name in sync._FILES}
        if args.expected_source_sha256 and baseline_hashes["CSPM.xlsm"] != args.expected_source_sha256.upper():
            raise RuntimeError("Source differs from the reviewed audit hash; candidate was not created.")
        candidate.mkdir(parents=True, exist_ok=False)
        for name, digest in baseline_hashes.items():
            shutil.copy2(paths.data_dir() / name, candidate / name)
            if sha(candidate / name) != digest:
                raise RuntimeError("Candidate copy differs from source.")
        candidate_paths = AppPaths(ROOT, candidate)
        integrity = WorkbookIntegrityService(candidate_paths)
        before_integrity = integrity.check()
        before = table_snapshot(candidate_paths.workbook_path())
        before_macros = macro_payload(candidate_paths.workbook_path())
        outcomes = []
        service = InvoiceDraftService(ExcelRepo(candidate_paths))
        for correction in corrections:
            invoice = correction["invoice"]
            outcome = {"invoiceNum": invoice}
            if correction.get("billingClient"):
                outcome["billing"] = service.correct_finalized_invoice_billing_client(
                    invoice, correction["billingClient"], correction["reason"])
            if correction.get("repairAmounts"):
                options = dict(expected_total=correction["expectedTotal"], reason=correction["reason"])
                if correction.get("expectedTax") is not None:
                    options["expected_tax"] = correction["expectedTax"]
                outcome["amounts"] = service.repair_finalized_invoice_amounts(invoice, **options)
            outcomes.append(outcome)
        after = table_snapshot(candidate_paths.workbook_path())
        for correction in corrections:
            rows = [row for row in after[sc.TBL_RECEIVABLES] if row[sc.COL_RECV_INVOICE_NUM] == correction["invoice"]]
            if len(rows) != 1 or Decimal(str(rows[0][sc.COL_RECV_TOTAL_INVOICED])) != Decimal(str(correction["expectedTotal"])):
                raise RuntimeError("Candidate does not match the reviewed issued invoice total.")
        changes = verify_scope(before, after, targets)
        if macro_payload(candidate_paths.workbook_path()) != before_macros:
            raise RuntimeError("Candidate changed workbook macro bytes.")
        after_integrity = integrity.check()
        new_errors = error_counts(after_integrity) - error_counts(before_integrity)
        if new_errors:
            raise RuntimeError(f"Candidate introduced integrity errors: {new_errors}")
        if sha(candidate_paths.dockets_workbook_path()) != baseline_hashes["Dockets.xlsm"]:
            raise RuntimeError("Candidate changed historical Dockets workbook.")
        result.update(outcomes=outcomes, changes=changes, sourceHashes=baseline_hashes,
                      integrityBefore=before_integrity.as_dict()["summary"],
                      integrityAfter=after_integrity.as_dict()["summary"])
        report = candidate / "amount_repair_report.json"
        report.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        if args.apply and changes:
            sync.assert_write_lease()
            if any(sha(paths.data_dir() / name) != digest for name, digest in baseline_hashes.items()):
                raise RuntimeError("Source changed during repair; candidate was not promoted.")
            backup = BackupService(paths).create_snapshot(
                reason="Before verified invoice accounting repairs: " + ", ".join(targets),
                protected=True, retention_class="manual", force=True)
            if not backup.get("ok"):
                raise RuntimeError(f"Protected backup failed: {backup}")
            result["backup"] = backup
            pending = paths.workbook_path().with_name("CSPM.amount-pending-" + uuid4().hex + ".xlsm")
            shutil.copy2(candidate_paths.workbook_path(), pending)
            if sha(pending) != sha(candidate_paths.workbook_path()):
                raise RuntimeError("Replacement hash differs from candidate.")
            sync.assert_write_lease()
            if any(sha(paths.data_dir() / name) != digest for name, digest in baseline_hashes.items()):
                raise RuntimeError("Source changed before promotion.")
            os.replace(pending, paths.workbook_path())
            committed = True
            if table_snapshot(paths.workbook_path()) != after:
                raise RuntimeError("Promoted workbook readback differs from verified candidate.")
            result["applied"] = True
            result["publish"] = sync.publish_and_release()
            if not result["publish"].get("ok"):
                raise RuntimeError(f"Local repair saved; publication requires attention: {result['publish']}")
            if any(sha(paths.data_dir() / name) != sha(paths.master_data_dir() / name) for name in sync._FILES):
                raise RuntimeError("Local/shared package differs after publication.")
        result["ok"] = True
        report.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(dict(ok=True, applied=result["applied"], report=str(report),
                              outcomes=outcomes, changedFields=len(changes)), indent=2, default=str))
        return 0
    finally:
        if sync._lease_owned and not sync._shutdown_complete:
            sync._release_checkout_lease()
        if committed and not result.get("ok"):
            print("Verified local repair was saved. Retain the candidate and backup for recovery.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
