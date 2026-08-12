"""Validate a copy-only cross-PC CSPM workbook merge candidate.

The validator is read-only with respect to the workbooks.  It writes only its
JSON report into the candidate directory supplied on the command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "src" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from domain import schema_constants as sc  # noqa: E402
from repositories.excel_repo import (  # noqa: E402
    ExcelRepo,
    TABLES_IN_ORDER,
    TBL_DISBURSEMENTS,
    TBL_INVOICE_LOG,
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
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _repo_for(data_dir: Path) -> ExcelRepo:
    return ExcelRepo(AppPaths(root=PROJECT_ROOT, override_data_dir=data_dir))


def _table_rows(package_dir: Path) -> dict[str, list[dict[str, Any]]]:
    repo = _repo_for(package_dir)
    return repo._read_table_rows_bulk(TABLES_IN_ORDER)


def _rows_exact(rows: list[dict[str, Any]], column: str, value: str) -> list[dict[str, Any]]:
    return [row for row in rows if _clean(row.get(column)).casefold() == value.casefold()]


def _assert_one(
    errors: list[dict[str, Any]], rows: list[dict[str, Any]], description: str
) -> dict[str, Any] | None:
    if len(rows) != 1:
        errors.append({"check": description, "expected": 1, "actual": len(rows)})
        return None
    return rows[0]


def _row_signature(row: dict[str, Any]) -> str:
    return json.dumps(row, default=str, sort_keys=True, separators=(",", ":"))


def _invoice_signatures(
    tables: dict[str, list[dict[str, Any]]], invoice: str
) -> dict[str, list[str]]:
    column_by_table = {
        TBL_TIME.table: sc.COL_TIME_INVOICE_REF,
        TBL_DISBURSEMENTS.table: sc.COL_DISB_INVOICE_REF,
        TBL_LEDGER.table: sc.COL_LEDGER_REFERENCE,
        TBL_RECEIVABLES.table: sc.COL_RECV_INVOICE_NUM,
        TBL_INVOICE_LOG.table: sc.COL_INV_INVOICE_NUM,
        TBL_TRANSACTIONS_MASTER.table: sc.COL_TXN_INVOICE_REF,
    }
    needle = invoice.casefold()
    output: dict[str, list[str]] = {}
    for table_name, column in column_by_table.items():
        matching = [
            _row_signature(row)
            for row in tables.get(table_name, [])
            if _clean(row.get(column)).casefold().startswith(needle)
        ]
        output[table_name] = sorted(matching)
    return output


def _primary_key_for_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    columns = set(rows[0])
    for candidate in (
        "EntryID",
        "TransactionID",
        "LedgerID",
        "DisbursementID",
        "DraftID",
        "MatterPartyID",
        "InvoiceNum",
        "MatterID",
        "TrademarkID",
        "ParentID",
        "ClientID",
        "AccountCode",
        "CategoryCode",
        "BusinessUnit",
        "PayeeName",
        "EntityID",
        "RelationshipID",
        "CorpTransactionID",
    ):
        if candidate in columns:
            return candidate
    return ""


def _duplicate_primary_ids(tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    duplicates: list[dict[str, Any]] = []
    for table_name, rows in tables.items():
        key = _primary_key_for_rows(rows)
        if not key:
            continue
        values = [_clean(row.get(key)) for row in rows if _clean(row.get(key))]
        repeated = sorted(value for value, count in Counter(values).items() if count > 1)
        if repeated:
            duplicates.append({"table": table_name, "primaryKey": key, "values": repeated})
    return duplicates


def _reconciliation(rows: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    receivables = rows.get(TBL_RECEIVABLES.table, [])
    ledgers = rows.get(TBL_LEDGER.table, [])
    invoice_log = rows.get(TBL_INVOICE_LOG.table, [])
    arithmetic_mismatches: list[dict[str, Any]] = []
    ledger_mismatches: list[dict[str, Any]] = []
    invoice_log_mismatches: list[dict[str, Any]] = []
    ledger_by_ref: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for ledger in ledgers:
        reference = _clean(ledger.get(sc.COL_LEDGER_REFERENCE))
        if reference:
            ledger_by_ref[reference] += _money(ledger.get(sc.COL_LEDGER_RECEIVABLE))
    logs_by_invoice: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for log in invoice_log:
        invoice = _clean(log.get(sc.COL_INV_INVOICE_NUM))
        if invoice:
            logs_by_invoice[invoice].append(log)
    excluded = {"void", "superseded", "reversed", "cancelled", "canceled"}
    for receivable in receivables:
        invoice = _clean(receivable.get(sc.COL_RECV_INVOICE_NUM))
        status = _clean(receivable.get(sc.COL_RECV_STATUS)).casefold()
        if not invoice or status in excluded:
            continue
        total = _money(receivable.get(sc.COL_RECV_TOTAL_INVOICED))
        paid = _money(receivable.get(sc.COL_RECV_AMOUNT_PAID))
        credits = _money(receivable.get(sc.COL_RECV_CREDITS_ADJ))
        balance = _money(receivable.get(sc.COL_RECV_BALANCE_DUE))
        expected_balance = total - paid - credits
        if abs(expected_balance - balance) > Decimal("0.02"):
            arithmetic_mismatches.append(
                {
                    "invoice": invoice,
                    "expectedBalance": str(expected_balance),
                    "actualBalance": str(balance),
                    "status": _clean(receivable.get(sc.COL_RECV_STATUS)),
                }
            )
        ledger_balance = ledger_by_ref[invoice]
        if abs(ledger_balance - balance) > Decimal("0.02"):
            ledger_mismatches.append(
                {
                    "invoice": invoice,
                    "ledgerReceivable": str(ledger_balance),
                    "receivableBalance": str(balance),
                    "status": _clean(receivable.get(sc.COL_RECV_STATUS)),
                }
            )
        matching_logs = logs_by_invoice[invoice]
        if len(matching_logs) != 1 or (
            matching_logs
            and abs(_money(matching_logs[0].get(sc.COL_INV_AGGREGATE_BILLED)) - total) > Decimal("0.02")
        ):
            invoice_log_mismatches.append(
                {
                    "invoice": invoice,
                    "invoiceLogRows": len(matching_logs),
                    "invoiceLogAggregate": str(
                        _money(matching_logs[0].get(sc.COL_INV_AGGREGATE_BILLED)) if matching_logs else Decimal("0.00")
                    ),
                    "receivableTotal": str(total),
                }
            )
    return {
        "receivableArithmetic": arithmetic_mismatches,
        "ledgerToReceivable": ledger_mismatches,
        "invoiceLogToReceivable": invoice_log_mismatches,
    }


def _package_openability(package_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for name in PACKAGE_FILES:
        path = package_dir / name
        try:
            with zipfile.ZipFile(path) as archive:
                bad_member = archive.testzip()
                if bad_member:
                    raise ValueError(f"ZIP member failed CRC: {bad_member}")
            workbook = load_workbook(path, read_only=True, data_only=False, keep_vba=True)
            workbook.close()
            checks.append({"file": name, "ok": True})
        except Exception as exc:
            checks.append({"file": name, "ok": False, "error": str(exc)})
    return checks


def validate(candidate_dir: Path, this_package: Path, other_package: Path) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    this_package = this_package.resolve()
    other_package = other_package.resolve()
    errors: list[dict[str, Any]] = []
    candidate_rows = _table_rows(candidate_dir)
    this_rows = _table_rows(this_package)

    package_checks = _package_openability(candidate_dir)
    errors.extend({"check": "workbook-openability", **check} for check in package_checks if not check["ok"])
    candidate_hashes = {name: _sha256(candidate_dir / name) for name in PACKAGE_FILES}
    this_hashes = {name: _sha256(this_package / name) for name in PACKAGE_FILES}
    other_hashes = {name: _sha256(other_package / name) for name in PACKAGE_FILES}
    if candidate_hashes["Dockets.xlsm"] != this_hashes["Dockets.xlsm"]:
        errors.append({"check": "Dockets byte identity", "expected": this_hashes["Dockets.xlsm"], "actual": candidate_hashes["Dockets.xlsm"]})
    if this_hashes["Dockets.xlsm"] != other_hashes["Dockets.xlsm"]:
        errors.append({"check": "Dockets source agreement", "thisPc": this_hashes["Dockets.xlsm"], "otherPc": other_hashes["Dockets.xlsm"]})

    duplicate_ids = _duplicate_primary_ids(candidate_rows)
    if duplicate_ids:
        errors.append({"check": "duplicate primary IDs", "details": duplicate_ids})

    preservation = {}
    for invoice in ("26-0092", "26-0095"):
        original = _invoice_signatures(this_rows, invoice)
        candidate = _invoice_signatures(candidate_rows, invoice)
        preservation[invoice] = original == candidate
        if original != candidate:
            errors.append({"check": f"preserve local invoice correction {invoice}", "expected": original, "actual": candidate})

    receivables = candidate_rows[TBL_RECEIVABLES.table]
    invoice_log = candidate_rows[TBL_INVOICE_LOG.table]
    ledger = candidate_rows[TBL_LEDGER.table]
    transactions = candidate_rows[TBL_TRANSACTIONS_MASTER.table]
    time_rows = candidate_rows[TBL_TIME.table]

    invoice_expectations = {
        "26-0092": {"client": "88 Queen", "total": Decimal("6977.74"), "paid": Decimal("0.00"), "balance": Decimal("6977.74"), "status": "unpaid", "fees": Decimal("6175.00"), "tax": Decimal("802.74")},
        "26-0095": {"client": "Concierge Club", "total": Decimal("429.40"), "paid": Decimal("0.00"), "balance": Decimal("429.40"), "status": "unpaid", "fees": Decimal("380.00"), "tax": Decimal("49.40")},
    }
    invoice_states: dict[str, Any] = {}
    for invoice, expected in invoice_expectations.items():
        receivable = _assert_one(errors, _rows_exact(receivables, sc.COL_RECV_INVOICE_NUM, invoice), f"receivable {invoice}")
        log = _assert_one(errors, _rows_exact(invoice_log, sc.COL_INV_INVOICE_NUM, invoice), f"invoice log {invoice}")
        ledger_rows = _rows_exact(ledger, sc.COL_LEDGER_REFERENCE, invoice)
        if not ledger_rows:
            errors.append({"check": f"ledger evidence {invoice}", "expected": "at least one row", "actual": 0})
        invoice_states[invoice] = {"receivable": receivable, "invoiceLog": log, "ledgerRows": len(ledger_rows)}
        if receivable:
            actual = {
                "client": _clean(receivable.get(sc.COL_RECV_CLIENT)),
                "total": _money(receivable.get(sc.COL_RECV_TOTAL_INVOICED)),
                "paid": _money(receivable.get(sc.COL_RECV_AMOUNT_PAID)),
                "balance": _money(receivable.get(sc.COL_RECV_BALANCE_DUE)),
                "status": _clean(receivable.get(sc.COL_RECV_STATUS)).casefold(),
            }
            if actual != {key: expected[key] for key in actual}:
                errors.append({"check": f"receivable state {invoice}", "expected": {key: str(value) for key, value in expected.items() if key in actual}, "actual": {key: str(value) for key, value in actual.items()}})
        if log and (
            _money(log.get(sc.COL_INV_TOTAL_FEES)) != expected["fees"]
            or _money(log.get(sc.COL_INV_TOTAL_TAX)) != expected["tax"]
            or _money(log.get(sc.COL_INV_AGGREGATE_BILLED)) != expected["total"]
        ):
            errors.append({"check": f"invoice log amount state {invoice}", "expected": {"fees": str(expected["fees"]), "tax": str(expected["tax"]), "total": str(expected["total"])}, "actual": {"fees": str(_money(log.get(sc.COL_INV_TOTAL_FEES))), "tax": str(_money(log.get(sc.COL_INV_TOTAL_TAX))), "total": str(_money(log.get(sc.COL_INV_AGGREGATE_BILLED)))}})

    incoming_transaction = _assert_one(errors, _rows_exact(transactions, sc.COL_TXN_ID, INCOMING_PAYMENT_TRANSACTION_ID), "incoming Suffolk transaction")
    incoming_ledger = _assert_one(errors, _rows_exact(ledger, sc.COL_LEDGER_ID, INCOMING_PAYMENT_LEDGER_ID), "incoming Suffolk ledger")
    stale_transaction = _rows_exact(transactions, sc.COL_TXN_ID, STALE_LOCAL_PAYMENT_TRANSACTION_ID)
    if stale_transaction:
        errors.append({"check": "stale local Suffolk transaction removed", "actual": len(stale_transaction), "transactionId": STALE_LOCAL_PAYMENT_TRANSACTION_ID})
    suffolk_receivable = _assert_one(errors, _rows_exact(receivables, sc.COL_RECV_INVOICE_NUM, SUFFOLK_INVOICE), "Suffolk receivable")
    suffolk_time = [row for row in time_rows if _clean(row.get(sc.COL_TIME_INVOICE_REF)) == SUFFOLK_INVOICE]
    if incoming_transaction and (
        _clean(incoming_transaction.get(sc.COL_TXN_INVOICE_REF)) != SUFFOLK_INVOICE
        or _money(incoming_transaction.get(sc.COL_TXN_AMOUNT)) != Decimal("5650.00")
        or _clean(incoming_transaction.get(sc.COL_TXN_STATUS)).casefold() != "cleared"
    ):
        errors.append({"check": "Suffolk transaction evidence", "actual": incoming_transaction})
    if incoming_ledger and (
        _clean(incoming_ledger.get(sc.COL_LEDGER_TRX_ID)) != INCOMING_PAYMENT_TRANSACTION_ID
        or _clean(incoming_ledger.get(sc.COL_LEDGER_REFERENCE)) != SUFFOLK_INVOICE
        or _money(incoming_ledger.get(sc.COL_LEDGER_COLLECTED)) != Decimal("5650.00")
        or _money(incoming_ledger.get(sc.COL_LEDGER_RECEIVABLE)) != Decimal("-5650.00")
    ):
        errors.append({"check": "Suffolk ledger evidence", "actual": incoming_ledger})
    if suffolk_receivable and (
        _money(suffolk_receivable.get(sc.COL_RECV_AMOUNT_PAID)) != Decimal("5650.00")
        or _money(suffolk_receivable.get(sc.COL_RECV_BALANCE_DUE)) != Decimal("0.00")
        or _clean(suffolk_receivable.get(sc.COL_RECV_STATUS)).casefold() != "paid"
    ):
        errors.append({"check": "Suffolk receivable paid state", "actual": suffolk_receivable})
    invalid_time = [
        _clean(row.get(sc.COL_TIME_ENTRY_ID))
        for row in suffolk_time
        if _clean(row.get(sc.COL_TIME_PAYMENT_STATUS)).casefold() != "paid"
        or _money(row.get(sc.COL_TIME_INVOICE_AMOUNT_PAID)) != Decimal("5650.00")
        or _money(row.get(sc.COL_TIME_INVOICE_BALANCE_DUE)) != Decimal("0.00")
    ]
    if not suffolk_time or invalid_time:
        errors.append({"check": "Suffolk linked time paid state", "rows": len(suffolk_time), "invalidEntryIds": invalid_time})
    invoice_0080_ledger_effect = sum(
        (_money(row.get(sc.COL_LEDGER_RECEIVABLE)) for row in _rows_exact(ledger, sc.COL_LEDGER_REFERENCE, SUFFOLK_INVOICE)),
        Decimal("0.00"),
    )
    if invoice_0080_ledger_effect != Decimal("0.00"):
        errors.append({"check": "Suffolk invoice ledger net receivable", "expected": "0.00", "actual": str(invoice_0080_ledger_effect)})

    cipo_receivable_artifacts = [row for row in receivables if "cipo" in " | ".join(_clean(value).casefold() for value in row.values())]
    cipo_invoice_artifacts = [row for row in invoice_log if "cipo" in " | ".join(_clean(value).casefold() for value in row.values())]
    cipo_transactions = [row for row in transactions if _clean(row.get(sc.COL_TXN_CLIENT)).casefold() == "cipo" and _clean(row.get(sc.COL_TXN_TYPE)).casefold() == "expense"]
    cipo_ledger = [row for row in ledger if _clean(row.get(sc.COL_LEDGER_CLIENT_VENDOR)).casefold() == "cipo" and _money(row.get(sc.COL_LEDGER_EXPENSES_EXCL_HST)) > Decimal("0.00")]
    if cipo_receivable_artifacts or cipo_invoice_artifacts:
        errors.append({"check": "no CIPO billing-client artifacts", "receivables": len(cipo_receivable_artifacts), "invoiceLog": len(cipo_invoice_artifacts)})
    if not cipo_transactions or not cipo_ledger:
        errors.append({"check": "retain valid CIPO vendor expense history", "transactions": len(cipo_transactions), "ledger": len(cipo_ledger)})

    candidate_reconciliation = _reconciliation(candidate_rows)
    baseline_reconciliation = _reconciliation(this_rows)
    for check_name, mismatches in candidate_reconciliation.items():
        if mismatches:
            errors.append({"check": check_name, "details": mismatches})

    return {
        "operation": "cross-PC merge candidate validation",
        "validatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "candidate": str(candidate_dir),
        "hashes": {"candidate": candidate_hashes, "thisPcRecovery": this_hashes, "otherPcExchange": other_hashes},
        "packageOpenability": package_checks,
        "duplicatePrimaryIds": duplicate_ids,
        "localCorrectionPreservation": preservation,
        "invoiceStates": invoice_states,
        "suffolk": {
            "transactionId": INCOMING_PAYMENT_TRANSACTION_ID,
            "ledgerId": INCOMING_PAYMENT_LEDGER_ID,
            "linkedTimeRows": len(suffolk_time),
            "ledgerNetReceivable": str(invoice_0080_ledger_effect),
        },
        "cipo": {"receivableArtifacts": len(cipo_receivable_artifacts), "invoiceLogArtifacts": len(cipo_invoice_artifacts), "expenseTransactions": len(cipo_transactions), "expenseLedgerRows": len(cipo_ledger)},
        "reconciliation": {"candidate": candidate_reconciliation, "thisPcRecoveryBaseline": baseline_reconciliation},
        "ok": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--this-package", type=Path, required=True)
    parser.add_argument("--other-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = validate(args.candidate_dir, args.this_package, args.other_package)
    output_path = args.output or args.candidate_dir / "merge_validation.json"
    output_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
