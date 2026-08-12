"""Repair evidence-backed legacy reconciliation defects in a merge candidate.

This command accepts a directory below ``merge_candidates`` only.  It never
reads configured live data paths and changes only the candidate ``CSPM.xlsm``.
Every expected pre-repair value is asserted before a write so a changed source
cannot be silently normalized as though it were the reviewed August 2026
candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "src" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from domain import schema_constants as sc  # noqa: E402
from repositories.excel_repo import (  # noqa: E402
    ExcelRepo,
    TBL_DISBURSEMENTS,
    TBL_INVOICE_LOG,
    TBL_LEDGER,
    TBL_RECEIVABLES,
    TBL_TIME,
    TBL_TRANSACTION_BUSINESS_UNITS,
    TBL_TRANSACTIONS_MASTER,
)
from services.paths import AppPaths  # noqa: E402


PACKAGE_FILES = ("CSPM.xlsm", "Dockets.xlsm")
ROUNDING_LEDGER_ID = "LEG-LED-25-0070-ROUNDING-0004"
DISBURSEMENT_LEDGER_ID = "LEG-LED-26-0006-DISB-2734"


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _repo_for(candidate_dir: Path) -> ExcelRepo:
    return ExcelRepo(AppPaths(root=PROJECT_ROOT, override_data_dir=candidate_dir))


def _find(rows: list[dict[str, Any]], column: str, value: str) -> list[dict[str, Any]]:
    needle = value.casefold()
    return [row for row in rows if _clean(row.get(column)).casefold() == needle]


def _one(rows: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one {description}; found {len(rows)}.")
    return rows[0]


def _expect_money(row: dict[str, Any], column: str, expected: str, description: str) -> None:
    actual = _money(row.get(column))
    wanted = _money(expected)
    if actual != wanted:
        raise ValueError(f"{description}: expected {column}={wanted}, found {actual}.")


def _blank_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot derive workbook columns from an empty table.")
    return {column: "" for column in rows[0]}


def _set_invoice_snapshot(
    rows: list[dict[str, Any]],
    reference_column: str,
    status_column: str,
    total_column: str,
    paid_column: str,
    balance_column: str,
    invoice: str,
    *,
    status: str,
    total: Decimal,
    paid: Decimal,
    balance: Decimal,
) -> int:
    changed = 0
    for row in rows:
        if _clean(row.get(reference_column)).casefold() != invoice.casefold():
            continue
        row[status_column] = status
        row[total_column] = total
        row[paid_column] = paid
        row[balance_column] = balance
        changed += 1
    return changed


def _append_ledger_row(
    rows: list[dict[str, Any]],
    *,
    ledger_id: str,
    date: str,
    client: str,
    description: str,
    category: str,
    reference: str,
    billings: Decimal,
    hst: Decimal,
    receivable: Decimal,
    external_ref: str,
    created_at: str,
) -> None:
    if _find(rows, sc.COL_LEDGER_ID, ledger_id):
        raise ValueError(f"Ledger ID already exists: {ledger_id}.")
    row = _blank_row(rows)
    row.update(
        {
            sc.COL_LEDGER_ID: ledger_id,
            sc.COL_LEDGER_DATE: date,
            sc.COL_LEDGER_CLIENT_VENDOR: client,
            sc.COL_LEDGER_DESCRIPTION: description,
            sc.COL_LEDGER_CATEGORY: category,
            sc.COL_LEDGER_REFERENCE: reference,
            sc.COL_LEDGER_BILLINGS_EXCL_HST: billings,
            sc.COL_LEDGER_HST_COLLECTED: hst,
            sc.COL_LEDGER_EXPENSES_EXCL_HST: Decimal("0.00"),
            sc.COL_LEDGER_HST_PAID: Decimal("0.00"),
            sc.COL_LEDGER_COLLECTED: Decimal("0.00"),
            sc.COL_LEDGER_WRITE_OFF: Decimal("0.00"),
            sc.COL_LEDGER_RECEIVABLE: receivable,
            sc.COL_LEDGER_TRX_ID: "",
            sc.COL_LEDGER_EXTERNAL_REF_ID: external_ref,
            sc.COL_LEDGER_ORIGINAL_AMOUNT: billings + hst,
            sc.COL_LEDGER_WORK_CLIENT: client,
            sc.COL_LEDGER_CREATED_AT: created_at,
        }
    )
    rows.append(row)


def _append_invoice_log_row(
    rows: list[dict[str, Any]],
    *,
    invoice: str,
    client: str,
    date: str,
    fees: Decimal,
    disbursements: Decimal,
    tax: Decimal,
    total: Decimal,
) -> None:
    if _find(rows, sc.COL_INV_INVOICE_NUM, invoice):
        raise ValueError(f"Invoice Log row already exists for {invoice}.")
    row = _blank_row(rows)
    row.update(
        {
            sc.COL_INV_INVOICE_NUM: invoice,
            sc.COL_INV_CLIENT_NAME: client,
            sc.COL_INV_SUB_CLIENT: "",
            sc.COL_INV_INVOICE_DATE: date,
            sc.COL_INV_TOTAL_FEES: fees,
            sc.COL_INV_TOTAL_DISBURSEMENTS: disbursements,
            sc.COL_INV_TOTAL_TAX: tax,
            sc.COL_INV_AGGREGATE_BILLED: total,
            sc.COL_INV_BILL_TO_CLIENT: client,
            sc.COL_INV_FILE_PATH: "",
        }
    )
    rows.append(row)


def _assert_candidate_directory(candidate_dir: Path) -> None:
    if candidate_dir.name.startswith("CSPM_MergeCandidate_") is False:
        raise ValueError("Candidate directory name must start with CSPM_MergeCandidate_.")
    if candidate_dir.parent.name != "merge_candidates":
        raise ValueError("Candidate must be directly below a merge_candidates directory.")
    for name in PACKAGE_FILES:
        if not (candidate_dir / name).is_file():
            raise ValueError(f"Candidate package file is missing: {candidate_dir / name}")
    if not (candidate_dir / "merge_manifest.json").is_file():
        raise ValueError("Candidate is missing its initial merge_manifest.json.")


def repair(candidate_dir: Path) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    _assert_candidate_directory(candidate_dir)
    dockets_hash_before = _sha256(candidate_dir / "Dockets.xlsm")
    cspm_hash_before = _sha256(candidate_dir / "CSPM.xlsm")
    now = datetime.now(timezone.utc).isoformat()
    repo = _repo_for(candidate_dir)
    tables = repo._read_table_rows_bulk(
        [
            TBL_DISBURSEMENTS,
            TBL_INVOICE_LOG,
            TBL_LEDGER,
            TBL_RECEIVABLES,
            TBL_TIME,
            TBL_TRANSACTION_BUSINESS_UNITS,
            TBL_TRANSACTIONS_MASTER,
        ]
    )
    disbursements = [dict(row) for row in tables[TBL_DISBURSEMENTS.table]]
    invoice_log = [dict(row) for row in tables[TBL_INVOICE_LOG.table]]
    ledger = [dict(row) for row in tables[TBL_LEDGER.table]]
    receivables = [dict(row) for row in tables[TBL_RECEIVABLES.table]]
    time_rows = [dict(row) for row in tables[TBL_TIME.table]]
    business_units = [dict(row) for row in tables[TBL_TRANSACTION_BUSINESS_UNITS.table]]
    transactions = [dict(row) for row in tables[TBL_TRANSACTIONS_MASTER.table]]

    # The incoming Suffolk payment carries Legal Practice as its business unit,
    # but both source packages omit the lookup entry.  Preserve the transaction
    # verbatim and add the only lookup row implied by its Member field.
    suffolk_transaction = _one(
        _find(transactions, sc.COL_TXN_ID, "TXN_59133aca6a"), "incoming Suffolk transaction"
    )
    if _clean(suffolk_transaction.get(sc.COL_TXN_BUSINESS_UNIT)) != "Legal Practice":
        raise ValueError("Incoming Suffolk transaction no longer uses Legal Practice business unit.")
    if _clean(suffolk_transaction.get(sc.COL_TXN_MEMBER)) != "Cory":
        raise ValueError("Incoming Suffolk transaction no longer identifies Cory as its member.")
    legal_practice_rows = _find(business_units, "BusinessUnit", "Legal Practice")
    if legal_practice_rows:
        raise ValueError("Legal Practice business-unit lookup already exists before candidate repair.")
    business_unit = _blank_row(business_units)
    business_unit.update({"BusinessUnit": "Legal Practice", "Owner": "Cory", "Active": 1})
    business_units.append(business_unit)

    # Exact duplicate empty placeholders: keep the original occurrence only.
    removed_placeholders: list[str] = []
    for invoice in ("24-0007", "24-0010"):
        matches = [index for index, row in enumerate(invoice_log) if _clean(row.get(sc.COL_INV_INVOICE_NUM)) == invoice]
        if len(matches) != 2:
            raise ValueError(f"Expected exactly two legacy placeholder logs for {invoice}; found {len(matches)}.")
        if invoice_log[matches[0]] != invoice_log[matches[1]]:
            raise ValueError(f"Duplicate {invoice} Invoice Log rows are not byte-for-byte equivalent.")
        invoice_log.pop(matches[1])
        removed_placeholders.append(invoice)

    # The TEST_CLIENT row is a duplicate of a billable 88 Queen invoice and has
    # no matching receivable, ledger, or docket evidence.
    logs_0071 = _find(invoice_log, sc.COL_INV_INVOICE_NUM, "26-0071")
    if len(logs_0071) != 2:
        raise ValueError(f"Expected two pre-repair Invoice Log rows for 26-0071; found {len(logs_0071)}.")
    test_rows = [row for row in logs_0071 if _clean(row.get(sc.COL_INV_BILL_TO_CLIENT)) == "TEST_CLIENT"]
    bad_row = _one(test_rows, "TEST_CLIENT Invoice Log row for 26-0071")
    invoice_log.remove(bad_row)
    primary_0071 = _one(_find(invoice_log, sc.COL_INV_INVOICE_NUM, "26-0071"), "retained Invoice Log row for 26-0071")
    _expect_money(primary_0071, sc.COL_INV_TOTAL_FEES, "2470.00", "26-0071 legacy log")
    primary_0071[sc.COL_INV_TOTAL_TAX] = Decimal("321.11")
    primary_0071[sc.COL_INV_AGGREGATE_BILLED] = Decimal("2791.11")

    # Existing ledger and receivable evidence supplies the corrected invoice log
    # values.  For 25-0070, the originally omitted $4.54 HST on a disbursement
    # is restored to the aggregate bill.
    log_updates = {
        "25-0030": {"tax": Decimal("87.59"), "total": Decimal("761.34")},
        "25-0064": {"tax": Decimal("69.54"), "total": Decimal("586.99")},
        "25-0070": {"tax": Decimal("1157.63"), "total": Decimal("10027.52")},
        "26-0029": {"tax": Decimal("30.88"), "total": Decimal("268.38")},
    }
    for invoice, values in log_updates.items():
        row = _one(_find(invoice_log, sc.COL_INV_INVOICE_NUM, invoice), f"Invoice Log row for {invoice}")
        row[sc.COL_INV_TOTAL_TAX] = values["tax"]
        row[sc.COL_INV_AGGREGATE_BILLED] = values["total"]

    # These historical invoices are present in the source package's legacy
    # invoice register and have matching Receivable/Ledger evidence, but were
    # omitted from the canonical Invoice Log during the earlier import.
    for values in (
        ("26-0028", "CRLPBC (2016) Trust", "2026-04-25", "2280.00", "0.00", "296.40", "2576.40"),
        ("26-0060", "Next Millennium Farms Inc. (dba Entomo Farms)", "2026-05-31", "1686.65", "0.00", "219.27", "1905.92"),
        ("26-0061", "Cypher Systems Inc.", "2026-05-31", "2280.00", "0.00", "296.40", "2576.40"),
        ("26-0062", "Libra Works Corporation", "2026-05-31", "4655.00", "0.00", "605.15", "5260.15"),
    ):
        _append_invoice_log_row(
            invoice_log,
            invoice=values[0],
            client=values[1],
            date=values[2],
            fees=Decimal(values[3]),
            disbursements=Decimal(values[4]),
            tax=Decimal(values[5]),
            total=Decimal(values[6]),
        )

    # Source transaction and disbursement rows prove the $27.34 charge on
    # 26-0006.  The import retained the disbursements but omitted their ledger
    # posting; this ledger row restores only that omitted billable amount.
    receivable_0006 = _one(_find(receivables, sc.COL_RECV_INVOICE_NUM, "26-0006"), "receivable 26-0006")
    _expect_money(receivable_0006, sc.COL_RECV_TOTAL_INVOICED, "387.25", "26-0006 receivable")
    source_disbursements = [
        _one(_find(disbursements, sc.COL_DISB_ID, value), f"source disbursement {value}")
        for value in ("LEG-DISB-0B17F864371DB4E67F7C", "LEG-DISB-AE56F661F2E12E9785D8")
    ]
    if any(_clean(row.get(sc.COL_DISB_INVOICE_REF)) != "26-0006" for row in source_disbursements):
        raise ValueError("The reviewed 26-0006 disbursements are no longer linked to that invoice.")
    if sum((_money(row.get(sc.COL_DISB_AMOUNT)) for row in source_disbursements), Decimal("0.00")) != Decimal("24.19"):
        raise ValueError("26-0006 source disbursement total is no longer $24.19.")
    _append_ledger_row(
        ledger,
        ledger_id=DISBURSEMENT_LEDGER_ID,
        date="2026-02-05",
        client="A2B Directcare Inc.",
        description="Billed legacy disbursements (Photocopies & Printing; Registered Mail)",
        category="Fees",
        reference="26-0006",
        billings=Decimal("24.19"),
        hst=Decimal("3.15"),
        receivable=Decimal("27.34"),
        external_ref="LEG-DISB-0B17F864371DB4E67F7C|LEG-DISB-AE56F661F2E12E9785D8",
        created_at=now,
    )

    # Existing 25-0070 ledger rows are off by a documented four-cent historical
    # rounding residual.  The adjustment leaves all payment evidence intact.
    _append_ledger_row(
        ledger,
        ledger_id=ROUNDING_LEDGER_ID,
        date="2026-01-28",
        client="Leviathan Private Network",
        description="Historic ledger rounding alignment for 25-0070",
        category="Fees",
        reference="25-0070",
        billings=Decimal("0.04"),
        hst=Decimal("0.00"),
        receivable=Decimal("0.04"),
        external_ref="Historical Dockets ledger reconciliation",
        created_at=now,
    )

    # These two expense transactions and their matching disbursements already
    # exist.  Link them to the billed client invoice while preserving the vendor
    # invoice as ExternalRefID.  Ferreira has no receipt evidence, so its
    # receivable is corrected from an unsupported PAID state to PENDING.
    vendor_links = (
        {
            "ledgerId": "TRX-260717083805",
            "vendorInvoice": "1557960",
            "invoice": "26-0077",
            "client": "Ferreira Inc.",
            "disbursementId": "LEG-DISB-6AAB53B587E531D605CC",
            "charge": Decimal("2179.99"),
            "total": Decimal("2770.42"),
            "paid": Decimal("0.00"),
            "balance": Decimal("2770.42"),
            "status": "PENDING",
        },
        {
            "ledgerId": "TRX-260717085701",
            "vendorInvoice": "1557961",
            "invoice": "26-0078",
            "client": "Modern Life Inc.",
            "disbursementId": "LEG-DISB-7662B53CA65B5BA0C434",
            "charge": Decimal("3344.92"),
            "total": Decimal("3989.02"),
            "paid": Decimal("0.00"),
            "balance": Decimal("3989.02"),
            "status": "PENDING",
        },
    )
    for link in vendor_links:
        vendor_ledger = _one(_find(ledger, sc.COL_LEDGER_ID, link["ledgerId"]), f"vendor ledger {link['ledgerId']}")
        if _clean(vendor_ledger.get(sc.COL_LEDGER_REFERENCE)) != link["vendorInvoice"]:
            raise ValueError(f"{link['ledgerId']} no longer has vendor invoice {link['vendorInvoice']}.")
        vendor_ledger[sc.COL_LEDGER_REFERENCE] = link["invoice"]
        vendor_ledger[sc.COL_LEDGER_EXTERNAL_REF_ID] = link["vendorInvoice"]
        vendor_ledger[sc.COL_LEDGER_WORK_CLIENT] = link["client"]
        vendor_ledger[sc.COL_LEDGER_RECEIVABLE] = link["charge"]
        disbursement = _one(_find(disbursements, sc.COL_DISB_ID, link["disbursementId"]), f"billable disbursement {link['disbursementId']}")
        if _clean(disbursement.get(sc.COL_DISB_INVOICE_REF)):
            raise ValueError(f"{link['disbursementId']} is already linked to another invoice.")
        disbursement[sc.COL_DISB_INVOICE_REF] = link["invoice"]
        disbursement[sc.COL_DISB_PAYMENT_STATUS] = link["status"]
        disbursement[sc.COL_DISB_INVOICE_TOTAL] = link["total"]
        disbursement[sc.COL_DISB_INVOICE_AMOUNT_PAID] = link["paid"]
        disbursement[sc.COL_DISB_INVOICE_BALANCE_DUE] = link["balance"]
        receivable = _one(_find(receivables, sc.COL_RECV_INVOICE_NUM, link["invoice"]), f"receivable {link['invoice']}")
        receivable[sc.COL_RECV_AMOUNT_PAID] = link["paid"]
        receivable[sc.COL_RECV_CREDITS_ADJ] = Decimal("0.00")
        receivable[sc.COL_RECV_BALANCE_DUE] = link["balance"]
        receivable[sc.COL_RECV_STATUS] = link["status"]
        time_count = _set_invoice_snapshot(
            time_rows,
            sc.COL_TIME_INVOICE_REF,
            sc.COL_TIME_PAYMENT_STATUS,
            sc.COL_TIME_INVOICE_TOTAL,
            sc.COL_TIME_INVOICE_AMOUNT_PAID,
            sc.COL_TIME_INVOICE_BALANCE_DUE,
            link["invoice"],
            status=link["status"],
            total=link["total"],
            paid=link["paid"],
            balance=link["balance"],
        )
        if time_count == 0:
            raise ValueError(f"No time entries are linked to {link['invoice']}.")

    repo._write_table_rows_bulk(
        {
            TBL_DISBURSEMENTS: disbursements,
            TBL_INVOICE_LOG: invoice_log,
            TBL_LEDGER: ledger,
            TBL_RECEIVABLES: receivables,
            TBL_TIME: time_rows,
            TBL_TRANSACTION_BUSINESS_UNITS: business_units,
        }
    )

    dockets_hash_after = _sha256(candidate_dir / "Dockets.xlsm")
    if dockets_hash_after != dockets_hash_before:
        raise RuntimeError("Dockets.xlsm changed during a CSPM-only candidate repair.")
    repair_manifest = {
        "operation": "candidate-only legacy reconciliation repair",
        "repairedAtUtc": now,
        "status": "candidate-repaired-awaiting-validation",
        "inputCspmSha256": cspm_hash_before,
        "outputCspmSha256": _sha256(candidate_dir / "CSPM.xlsm"),
        "docketsSha256": dockets_hash_after,
        "removedExactDuplicateInvoiceLogRows": removed_placeholders,
        "removedTestInvoiceLogRow": "26-0071 / TEST_CLIENT",
        "invoiceLogUpdated": sorted(log_updates),
        "invoiceLogRestored": ["26-0028", "26-0060", "26-0061", "26-0062"],
        "ledgerRowsAdded": [ROUNDING_LEDGER_ID, DISBURSEMENT_LEDGER_ID],
        "businessUnitLookupRestored": {
            "businessUnit": "Legal Practice",
            "owner": "Cory",
            "evidenceTransactionId": "TXN_59133aca6a",
        },
        "vendorExpenseInvoiceLinks": [
            {
                "invoice": link["invoice"],
                "ledgerId": link["ledgerId"],
                "vendorInvoicePreservedAsExternalRefId": link["vendorInvoice"],
                "disbursementId": link["disbursementId"],
            }
            for link in vendor_links
        ],
        "unsupportedPaidStateCorrected": {
            "invoice": "26-0077",
            "newStatus": "PENDING",
            "reason": "No receipt transaction or payment-ledger evidence exists in either copied workbook."
        },
    }
    (candidate_dir / "legacy_reconciliation_repair.json").write_text(
        json.dumps(repair_manifest, indent=2, default=str) + "\n", encoding="utf-8"
    )
    manifest_path = candidate_dir / "merge_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["legacyReconciliationRepair"] = repair_manifest
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    return repair_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, "repair": repair(args.candidate_dir)}, indent=2, default=str))
    except Exception as exc:
        print(json.dumps({"ok": False, "candidateDir": str(args.candidate_dir), "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
