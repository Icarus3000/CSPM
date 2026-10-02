"""Atomic, amount-verified invoice reversal with retained accounting evidence."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import shutil
from uuid import uuid4

from domain import schema_constants as sc
from repositories.excel_repo import _DB_LOCK


TABLES = (sc.TBL_TIME, sc.TBL_DISBURSEMENTS, sc.TBL_RECEIVABLES,
          sc.TBL_INVOICE_LOG, sc.TBL_LEDGER, sc.TBL_TRANSACTIONS_MASTER,
          sc.TBL_TRANSACTION_ACCOUNTS, sc.TBL_TRANSACTION_BUSINESS_UNITS)
VOID_STATUSES = {"void", "voided", "reversed", "cancelled", "canceled"}
AMOUNT_COLUMNS = {
    sc.TBL_INVOICE_LOG: (sc.COL_INV_TOTAL_FEES, sc.COL_INV_TOTAL_DISBURSEMENTS,
                         sc.COL_INV_TOTAL_TAX, sc.COL_INV_AGGREGATE_BILLED),
    sc.TBL_LEDGER: (sc.COL_LEDGER_BILLINGS_EXCL_HST, sc.COL_LEDGER_HST_COLLECTED,
                   sc.COL_LEDGER_RECEIVABLE),
    sc.TBL_TRANSACTIONS_MASTER: (sc.COL_TXN_AMOUNT, sc.COL_TXN_TAX_AMOUNT),
}
REFERENCE_COLUMNS = {sc.TBL_INVOICE_LOG: sc.COL_INV_INVOICE_NUM,
                     sc.TBL_LEDGER: sc.COL_LEDGER_REFERENCE,
                     sc.TBL_TRANSACTIONS_MASTER: sc.COL_TXN_INVOICE_REF}


def money(value):
    try:
        amount = Decimal(str(value if value not in (None, "") else 0))
        if not amount.is_finite():
            raise ValueError()
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"Invalid financial amount: {value!r}") from exc


def key(value):
    return str(value or "").strip().casefold()


def reversal_rows(tables, table, number):
    reference = key(number) + "-v"
    column = REFERENCE_COLUMNS[table]
    return [row for row in tables[table]
            if key(row.get(column)) == reference
            or key(row.get(column)).startswith(reference + "-adj-")]


def expected_amounts(original):
    fees, disb, tax, total = (money(original.get(col))
                             for col in AMOUNT_COLUMNS[sc.TBL_INVOICE_LOG])
    if total != fees + disb + tax:
        raise ValueError("Invoice components do not reconcile to its total. Reversal was not committed.")
    return {sc.TBL_INVOICE_LOG: (-fees, -disb, -tax, -total),
            sc.TBL_LEDGER: (-(fees + disb), -tax, -total),
            sc.TBL_TRANSACTIONS_MASTER: (-(fees + disb), -tax)}


def evidence_totals(tables, table, number):
    rows = reversal_rows(tables, table, number)
    return tuple(sum((money(row.get(col)) for row in rows), Decimal("0.00"))
                 for col in AMOUNT_COLUMNS[table])


def verify_reversal(tables, number):
    """Verify lifecycle, released WIP, and all three accounting projections."""
    originals = [row for row in tables[sc.TBL_INVOICE_LOG]
                 if key(row.get(sc.COL_INV_INVOICE_NUM)) == key(number)]
    receivables = [row for row in tables[sc.TBL_RECEIVABLES]
                   if key(row.get(sc.COL_RECV_INVOICE_NUM)) == key(number)]
    if len(originals) != 1 or len(receivables) != 1:
        raise ValueError("Invoice reversal requires one unambiguous invoice and receivable.")
    expected = expected_amounts(originals[0])
    recv = receivables[0]
    if (key(recv.get(sc.COL_RECV_STATUS)) not in VOID_STATUSES
            or any(money(recv.get(col)) != 0 for col in
                   (sc.COL_RECV_AMOUNT_PAID, sc.COL_RECV_CREDITS_ADJ, sc.COL_RECV_BALANCE_DUE))):
        raise ValueError("The reversed receivable still has an active balance, payment, or credit.")
    for table, reference in ((sc.TBL_TIME, sc.COL_TIME_INVOICE_REF),
                             (sc.TBL_DISBURSEMENTS, sc.COL_DISB_INVOICE_REF)):
        if any(key(row.get(reference)) == key(number) for row in tables[table]):
            raise ValueError("Reversed invoice still has billed WIP attached.")
    for table, amounts in expected.items():
        if not reversal_rows(tables, table, number) or evidence_totals(tables, table, number) != amounts:
            raise ValueError(f"Reversal evidence does not balance in {table}.")
    return {"ok": True, "invoiceNum": number, "status": "Void",
            "invoiceTotal": str(-expected[sc.TBL_INVOICE_LOG][-1]),
            "reversalTotal": str(expected[sc.TBL_INVOICE_LOG][-1])}


def reverse_invoice(service, number, source_pdf_path="", pdf_action="keep", target_dir=""):
    """Preserve old evidence and append only the difference needed to balance.

    An earlier reversal for a reused or edited number is not proof of a current
    reversal. Differences receive separate -V-ADJ audit references; original
    rows are never overwritten. All workbook changes use one atomic save.
    """
    number = str(number or "").strip()
    if not number:
        raise ValueError("An invoice number is required for reversal.")
    action = key(pdf_action or "keep")
    if action not in {"keep", "move", "delete"}:
        raise ValueError("Unknown invoice PDF action.")
    pdf_path = Path(str(source_pdf_path or "").strip()) if action != "keep" else None
    archive_path = None
    if pdf_path is not None:
        if not pdf_path.is_file():
            raise ValueError("Select the existing invoice PDF before asking CSPM to move or delete it.")
        if action == "move":
            archive_path = (Path(target_dir) if str(target_dir or "").strip()
                            else pdf_path.parent / "REVERSED") / pdf_path.name
            if archive_path.exists():
                raise FileExistsError(f"Refusing to overwrite an existing archived PDF: {archive_path}")

    # Share the repository lock with payments and other financial commands so
    # no writer can change the snapshot between validation and replacement.
    with _DB_LOCK:
        tables = service._read_tables_once(list(TABLES))
        originals = [row for row in tables[sc.TBL_INVOICE_LOG]
                     if key(row.get(sc.COL_INV_INVOICE_NUM)) == key(number)]
        receivables = [row for row in tables[sc.TBL_RECEIVABLES]
                       if key(row.get(sc.COL_RECV_INVOICE_NUM)) == key(number)]
        if len(originals) != 1 or len(receivables) != 1:
            raise ValueError(f"Invoice {number} requires one unambiguous Invoice Log and Receivables entry.")
        original, recv = originals[0], receivables[0]
        active_accounts = {key(row.get(sc.COL_TXN_ACCOUNT_CODE)): row.get(sc.COL_TXN_ACCOUNT_CODE)
                           for row in tables[sc.TBL_TRANSACTION_ACCOUNTS]
                           if str(row.get(sc.COL_TXN_ACCOUNT_ACTIVE, 1)).lower() not in {"0", "false"}}
        active_units = {key(row.get(sc.COL_TXN_BUSINESS_UNIT_NAME)): row.get(sc.COL_TXN_BUSINESS_UNIT_NAME)
                        for row in tables[sc.TBL_TRANSACTION_BUSINESS_UNITS]
                        if str(row.get(sc.COL_TXN_BUSINESS_UNIT_ACTIVE, 1)).lower() not in {"0", "false"}}
        revenue_account = active_accounts.get("legal_revenue")
        business_unit = active_units.get("legal practice") or active_units.get("cory business")
        if not revenue_account or not business_unit:
            raise ValueError("Reversal requires the active Legal Revenue account and legal-practice business unit.")
        if any(money(recv.get(col)) != 0 for col in (sc.COL_RECV_AMOUNT_PAID, sc.COL_RECV_CREDITS_ADJ)):
            raise ValueError(f"Invoice {number} has recorded payments or credits and cannot be reversed here. Reverse those allocations first.")
        expected = expected_amounts(original)
        if money(recv.get(sc.COL_RECV_TOTAL_INVOICED)) != -expected[sc.TBL_INVOICE_LOG][-1]:
            raise ValueError("Invoice Log and Receivables totals differ. Reversal was not committed.")

        changed = {}
        for table, reference in ((sc.TBL_TIME, sc.COL_TIME_INVOICE_REF),
                                 (sc.TBL_DISBURSEMENTS, sc.COL_DISB_INVOICE_REF)):
            for row in tables[table]:
                if key(row.get(reference)) != key(number):
                    continue
                row[reference] = ""
                if table == sc.TBL_TIME:
                    row.update({sc.COL_TIME_INVOICE_STATUS: "Unbilled", sc.COL_TIME_STATUS: "Draft",
                                sc.COL_TIME_INVOICE_DATE: "", sc.COL_TIME_INVOICE_TOTAL: "0.00",
                                sc.COL_TIME_INVOICE_AMOUNT_PAID: "0.00",
                                sc.COL_TIME_INVOICE_BALANCE_DUE: "0.00", sc.COL_TIME_PAYMENT_STATUS: ""})
                changed[table] = tables[table]
        if key(recv.get(sc.COL_RECV_STATUS)) not in VOID_STATUSES or money(recv.get(sc.COL_RECV_BALANCE_DUE)) != 0:
            recv[sc.COL_RECV_BALANCE_DUE] = "0.00"
            recv[sc.COL_RECV_STATUS] = "Void"
            changed[sc.TBL_RECEIVABLES] = tables[sc.TBL_RECEIVABLES]

        now = datetime.now().astimezone().isoformat()
        # Retain the existing -V audit convention so every report excludes
        # this evidence from client-facing invoice lists.
        adjustment_ref = f"{number}-V-ADJ-{uuid4().hex[:12]}-V"
        for table, amounts in expected.items():
            existing = reversal_rows(tables, table, number)
            totals = evidence_totals(tables, table, number)
            delta = tuple(wanted - actual for wanted, actual in zip(amounts, totals))
            if existing and all(amount == 0 for amount in delta):
                continue
            reference = adjustment_ref if existing else f"{number}-V"
            explanation = (f"Reversal reconciliation for invoice {number}; retained prior evidence"
                           if existing else f"Reversal of invoice {number}")
            client = original.get(sc.COL_INV_BILL_TO_CLIENT) or original.get(sc.COL_INV_CLIENT_NAME) or ""
            if table == sc.TBL_INVOICE_LOG:
                row = dict(original)
                row[sc.COL_INV_FILE_PATH] = ""
                if existing:
                    snapshot = service._bill_to_snapshot_payload(original.get(sc.COL_INV_BILL_TO_SNAPSHOT))
                    snapshot["reversalReconciliation"] = {"invoiceNum": number, "recordedAt": now,
                                                         "reason": explanation, "reference": reference}
                    row[sc.COL_INV_BILL_TO_SNAPSHOT] = json.dumps(snapshot)
            elif table == sc.TBL_LEDGER:
                row = {sc.COL_LEDGER_ID: service.repo._new_id("LED"), sc.COL_LEDGER_DATE: now[:10],
                       sc.COL_LEDGER_CLIENT_VENDOR: client, sc.COL_LEDGER_DESCRIPTION: explanation,
                       sc.COL_LEDGER_CATEGORY: "Invoice Reversal", sc.COL_LEDGER_CREATED_AT: now}
            else:
                row = {sc.COL_TXN_ID: service.repo._new_id("TXN"), sc.COL_TXN_DATE: now[:10],
                       sc.COL_TXN_CLASS: "Business", sc.COL_TXN_TYPE: "Income", sc.COL_TXN_CLIENT: client,
                       sc.COL_TXN_FROM_ACCOUNT: revenue_account, sc.COL_TXN_BUSINESS_UNIT: business_unit,
                       sc.COL_TXN_CATEGORY_CODE: "INC_LEGAL_FEES", sc.COL_TXN_CATEGORY_NAME: "Invoice Reversal",
                       sc.COL_TXN_NOTES: explanation, sc.COL_TXN_STATUS: "Cleared", sc.COL_TXN_CURRENCY: "CAD",
                       sc.COL_TXN_CREATED_AT: now, sc.COL_TXN_UPDATED_AT: now}
            row[REFERENCE_COLUMNS[table]] = reference
            row.update({col: str(amount) for col, amount in zip(AMOUNT_COLUMNS[table], delta)})
            tables[table].append(row)
            changed[table] = tables[table]

        verify_reversal(tables, number)
        if changed:
            service._write_tables_once(changed)
        # Re-read the saved workbook, rather than trusting the prepared plan.
        verify_reversal(service._read_tables_once(list(TABLES)), number)

    if action == "delete":
        pdf_path.unlink()
    elif action == "move":
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdf_path), str(archive_path))
    return True
