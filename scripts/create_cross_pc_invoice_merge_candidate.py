"""Create a non-live, auditable candidate for the August 2026 cross-PC merge.

The command accepts only previously copied workbook packages.  It never reads
or writes the configured live local or shared data locations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "src" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import (  # noqa: E402
    ExcelRepo,
    TABLES_IN_ORDER,
    TBL_DISBURSEMENTS,
    TBL_LEDGER,
    TBL_RECEIVABLES,
    TBL_TIME,
    TBL_TRANSACTIONS_MASTER,
)
from services.paths import AppPaths  # noqa: E402


PACKAGE_FILES = ("CSPM.xlsm", "Dockets.xlsm")
SUFFOLK_INVOICE = "26-0080"
INCOMING_PAYMENT_TRANSACTION_ID = "TXN_59133aca6a"
INCOMING_PAYMENT_LEDGER_ID = "LED_dbc8eeeb2b"
STALE_LOCAL_PAYMENT_TRANSACTION_ID = "TXN_d6597b9128"


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _repo_for(data_dir: Path) -> ExcelRepo:
    return ExcelRepo(AppPaths(root=PROJECT_ROOT, override_data_dir=data_dir))


def _exact_rows(rows: list[dict[str, Any]], column: str, value: str) -> list[dict[str, Any]]:
    needle = value.casefold()
    return [row for row in rows if _clean(row.get(column)).casefold() == needle]


def _one(rows: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one {description}; found {len(rows)}.")
    return dict(rows[0])


def _external_references(repo: ExcelRepo, transaction_id: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    snapshots = repo._read_table_rows_bulk(TABLES_IN_ORDER)
    for table_ref in TABLES_IN_ORDER:
        if table_ref == TBL_TRANSACTIONS_MASTER:
            continue
        for row in snapshots.get(table_ref.table, []):
            for column, value in row.items():
                if _clean(value) == transaction_id:
                    found.append({"table": table_ref.table, "column": column})
    return found


def _write_blocked(candidate_dir: Path, detail: dict[str, Any]) -> None:
    (candidate_dir / "MERGE_BLOCKED.json").write_text(
        json.dumps(detail, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def create_candidate(this_package: Path, other_package: Path, candidate_dir: Path) -> dict[str, Any]:
    this_package = this_package.resolve()
    other_package = other_package.resolve()
    candidate_dir = candidate_dir.resolve()
    if candidate_dir.exists():
        raise ValueError(f"Candidate destination already exists: {candidate_dir}")

    for package in (this_package, other_package):
        for name in PACKAGE_FILES:
            if not (package / name).is_file():
                raise ValueError(f"Required copied package file is absent: {package / name}")

    candidate_dir.mkdir(parents=True, exist_ok=False)
    input_hashes = {
        "thisPc": {name: _sha256(this_package / name) for name in PACKAGE_FILES},
        "otherPc": {name: _sha256(other_package / name) for name in PACKAGE_FILES},
    }
    if input_hashes["thisPc"]["Dockets.xlsm"] != input_hashes["otherPc"]["Dockets.xlsm"]:
        raise ValueError(
            "Dockets.xlsm differs between the copied packages; no candidate mutation is permitted."
        )

    for name in PACKAGE_FILES:
        candidate_file = candidate_dir / name
        shutil.copy2(this_package / name, candidate_file)
        # Recovery snapshots are deliberately read-only.  The isolated
        # candidate must be writable so its atomic replacement can occur.
        os.chmod(candidate_file, candidate_file.stat().st_mode | stat.S_IWRITE)

    this_repo = _repo_for(this_package)
    other_repo = _repo_for(other_package)
    candidate_repo = _repo_for(candidate_dir)
    refs = [TBL_TIME, TBL_DISBURSEMENTS, TBL_LEDGER, TBL_RECEIVABLES, TBL_TRANSACTIONS_MASTER]
    local = this_repo._read_table_rows_bulk(refs)
    incoming = other_repo._read_table_rows_bulk(refs)
    working = candidate_repo._read_table_rows_bulk(refs)

    incoming_transaction = _one(
        _exact_rows(
            incoming[TBL_TRANSACTIONS_MASTER.table],
            sc.COL_TXN_ID,
            INCOMING_PAYMENT_TRANSACTION_ID,
        ),
        f"incoming Suffolk payment transaction {INCOMING_PAYMENT_TRANSACTION_ID}",
    )
    incoming_ledger = _one(
        _exact_rows(incoming[TBL_LEDGER.table], sc.COL_LEDGER_ID, INCOMING_PAYMENT_LEDGER_ID),
        f"incoming Suffolk payment ledger {INCOMING_PAYMENT_LEDGER_ID}",
    )
    incoming_receivable = _one(
        _exact_rows(incoming[TBL_RECEIVABLES.table], sc.COL_RECV_INVOICE_NUM, SUFFOLK_INVOICE),
        f"incoming Suffolk receivable {SUFFOLK_INVOICE}",
    )

    if _clean(incoming_transaction.get(sc.COL_TXN_INVOICE_REF)) != SUFFOLK_INVOICE:
        raise ValueError("Incoming payment transaction is not linked to invoice 26-0080.")
    if _clean(incoming_ledger.get(sc.COL_LEDGER_TRX_ID)) != INCOMING_PAYMENT_TRANSACTION_ID:
        raise ValueError("Incoming payment ledger does not reference the incoming transaction ID.")
    if _clean(incoming_ledger.get(sc.COL_LEDGER_REFERENCE)) != SUFFOLK_INVOICE:
        raise ValueError("Incoming payment ledger is not linked to invoice 26-0080.")
    if _money(incoming_transaction.get(sc.COL_TXN_AMOUNT)) != Decimal("5650.00"):
        raise ValueError("Incoming Suffolk payment transaction amount is not $5,650.00.")
    if _money(incoming_ledger.get(sc.COL_LEDGER_COLLECTED)) != Decimal("5650.00"):
        raise ValueError("Incoming Suffolk payment ledger collected amount is not $5,650.00.")
    if _money(incoming_ledger.get(sc.COL_LEDGER_RECEIVABLE)) != Decimal("-5650.00"):
        raise ValueError("Incoming Suffolk payment ledger receivable effect is not -$5,650.00.")
    if _money(incoming_receivable.get(sc.COL_RECV_TOTAL_INVOICED)) != Decimal("5650.00"):
        raise ValueError("Incoming Suffolk receivable total is not $5,650.00.")
    if _money(incoming_receivable.get(sc.COL_RECV_AMOUNT_PAID)) != Decimal("5650.00"):
        raise ValueError("Incoming Suffolk receivable is not paid in full.")
    if _money(incoming_receivable.get(sc.COL_RECV_BALANCE_DUE)) != Decimal("0.00"):
        raise ValueError("Incoming Suffolk receivable does not have a zero balance.")

    candidate_transactions = [dict(row) for row in working[TBL_TRANSACTIONS_MASTER.table]]
    candidate_ledgers = [dict(row) for row in working[TBL_LEDGER.table]]
    candidate_receivables = [dict(row) for row in working[TBL_RECEIVABLES.table]]
    candidate_time = [dict(row) for row in working[TBL_TIME.table]]
    candidate_disbursements = [dict(row) for row in working[TBL_DISBURSEMENTS.table]]

    if _exact_rows(candidate_transactions, sc.COL_TXN_ID, INCOMING_PAYMENT_TRANSACTION_ID):
        raise ValueError("Candidate already contains the incoming Suffolk transaction ID.")
    if _exact_rows(candidate_ledgers, sc.COL_LEDGER_ID, INCOMING_PAYMENT_LEDGER_ID):
        raise ValueError("Candidate already contains the incoming Suffolk ledger ID.")

    stale_matches = _exact_rows(
        candidate_transactions,
        sc.COL_TXN_ID,
        STALE_LOCAL_PAYMENT_TRANSACTION_ID,
    )
    stale_transaction = _one(stale_matches, f"stale local Suffolk transaction {STALE_LOCAL_PAYMENT_TRANSACTION_ID}")
    if (
        _clean(stale_transaction.get(sc.COL_TXN_INVOICE_REF)) != SUFFOLK_INVOICE
        or _money(stale_transaction.get(sc.COL_TXN_AMOUNT)) != Decimal("5650.00")
        or _clean(stale_transaction.get(sc.COL_TXN_TYPE)).casefold() != "income"
    ):
        raise ValueError("The expected stale local payment row has an unexpected business identity.")
    references = _external_references(candidate_repo, STALE_LOCAL_PAYMENT_TRANSACTION_ID)
    if references:
        raise ValueError(
            f"The stale local payment ID is referenced outside Transactions: {references}."
        )

    candidate_receivable = _one(
        _exact_rows(candidate_receivables, sc.COL_RECV_INVOICE_NUM, SUFFOLK_INVOICE),
        f"candidate receivable {SUFFOLK_INVOICE}",
    )
    if _money(candidate_receivable.get(sc.COL_RECV_TOTAL_INVOICED)) != _money(
        incoming_receivable.get(sc.COL_RECV_TOTAL_INVOICED)
    ):
        raise ValueError("The two copied packages disagree on invoice 26-0080 total invoiced.")
    if _money(candidate_receivable.get(sc.COL_RECV_AMOUNT_PAID)) != Decimal("0.00"):
        raise ValueError("This-PC 26-0080 receivable is not in the expected pre-payment state.")

    for index, row in enumerate(candidate_transactions):
        if _clean(row.get(sc.COL_TXN_ID)) == STALE_LOCAL_PAYMENT_TRANSACTION_ID:
            candidate_transactions[index] = incoming_transaction
            break
    candidate_ledgers.append(incoming_ledger)

    for index, row in enumerate(candidate_receivables):
        if _clean(row.get(sc.COL_RECV_INVOICE_NUM)) == SUFFOLK_INVOICE:
            row[sc.COL_RECV_AMOUNT_PAID] = incoming_receivable.get(sc.COL_RECV_AMOUNT_PAID)
            row[sc.COL_RECV_CREDITS_ADJ] = incoming_receivable.get(sc.COL_RECV_CREDITS_ADJ)
            row[sc.COL_RECV_BALANCE_DUE] = incoming_receivable.get(sc.COL_RECV_BALANCE_DUE)
            row[sc.COL_RECV_STATUS] = incoming_receivable.get(sc.COL_RECV_STATUS)
            candidate_receivables[index] = row
            break

    touched_time = 0
    for row in candidate_time:
        if _clean(row.get(sc.COL_TIME_INVOICE_REF)).casefold() == SUFFOLK_INVOICE:
            row[sc.COL_TIME_PAYMENT_STATUS] = "Paid"
            row[sc.COL_TIME_INVOICE_TOTAL] = incoming_receivable.get(sc.COL_RECV_TOTAL_INVOICED)
            row[sc.COL_TIME_INVOICE_AMOUNT_PAID] = incoming_receivable.get(sc.COL_RECV_AMOUNT_PAID)
            row[sc.COL_TIME_INVOICE_BALANCE_DUE] = incoming_receivable.get(sc.COL_RECV_BALANCE_DUE)
            touched_time += 1
    touched_disbursements = 0
    for row in candidate_disbursements:
        if _clean(row.get(sc.COL_DISB_INVOICE_REF)).casefold() == SUFFOLK_INVOICE:
            row[sc.COL_DISB_PAYMENT_STATUS] = "Paid"
            row[sc.COL_DISB_INVOICE_TOTAL] = incoming_receivable.get(sc.COL_RECV_TOTAL_INVOICED)
            row[sc.COL_DISB_INVOICE_AMOUNT_PAID] = incoming_receivable.get(sc.COL_RECV_AMOUNT_PAID)
            row[sc.COL_DISB_INVOICE_BALANCE_DUE] = incoming_receivable.get(sc.COL_RECV_BALANCE_DUE)
            touched_disbursements += 1
    if touched_time == 0 and touched_disbursements == 0:
        raise ValueError("No candidate time or disbursement rows are linked to invoice 26-0080.")

    candidate_repo._write_table_rows_bulk(
        {
            TBL_TRANSACTIONS_MASTER: candidate_transactions,
            TBL_LEDGER: candidate_ledgers,
            TBL_RECEIVABLES: candidate_receivables,
            TBL_TIME: candidate_time,
            TBL_DISBURSEMENTS: candidate_disbursements,
        }
    )

    cipo_plan = candidate_repo.repair_rogue_vendor_receivables("CIPO", apply=False)
    if not cipo_plan.get("ok"):
        raise ValueError(f"CIPO cleanup plan failed: {cipo_plan}")
    cipo_result = (
        candidate_repo.repair_rogue_vendor_receivables("CIPO", apply=True)
        if any(cipo_plan.get("removed", {}).values())
        else cipo_plan
    )

    output_hashes = {name: _sha256(candidate_dir / name) for name in PACKAGE_FILES}
    if output_hashes["Dockets.xlsm"] != input_hashes["thisPc"]["Dockets.xlsm"]:
        raise ValueError("Candidate Dockets.xlsm changed unexpectedly.")

    manifest = {
        "operation": "copy-only cross-PC invoice merge candidate",
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate-created",
        "inputHashes": input_hashes,
        "outputHashes": output_hashes,
        "docketsByteIdentical": True,
        "sources": {"thisPcRecovery": str(this_package), "otherPcExchange": str(other_package)},
        "suffolkPayment": {
            "invoice": SUFFOLK_INVOICE,
            "replacedStaleTransactionId": STALE_LOCAL_PAYMENT_TRANSACTION_ID,
            "transactionId": INCOMING_PAYMENT_TRANSACTION_ID,
            "ledgerId": INCOMING_PAYMENT_LEDGER_ID,
            "amount": "5650.00",
            "timeRowsUpdated": touched_time,
            "disbursementRowsUpdated": touched_disbursements,
        },
        "cipoCleanup": cipo_result,
        "preservation": {
            "thisPcInvoiceCorrections": ["26-0092", "26-0095"],
            "otherPcWorkbookRowsUsedOnlyFor": "Suffolk payment transaction/ledger/receivable state",
        },
    }
    (candidate_dir / "merge_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--this-package", type=Path, required=True)
    parser.add_argument("--other-package", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    args = parser.parse_args()

    candidate_dir = args.candidate_dir.resolve()
    try:
        manifest = create_candidate(args.this_package, args.other_package, candidate_dir)
    except Exception as exc:
        if candidate_dir.exists():
            _write_blocked(
                candidate_dir,
                {
                    "operation": "copy-only cross-PC invoice merge candidate",
                    "status": "blocked",
                    "error": str(exc),
                },
            )
        print(json.dumps({"ok": False, "candidateDir": str(candidate_dir), "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "candidateDir": str(candidate_dir), "manifest": manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
