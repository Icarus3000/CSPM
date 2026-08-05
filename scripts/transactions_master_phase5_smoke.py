from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise AssertionError(message)


def _assert_true(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _copy_schema_seed_files(src_root: Path, dst_root: Path) -> None:
    src_schema = src_root / "schema"
    dst_schema = dst_root / "schema"
    dst_schema.mkdir(parents=True, exist_ok=True)

    files = [
        "workbook_schema.yml",
        "transactions_master.accounts.seed.csv",
        "transactions_master.business_units.seed.csv",
        "transactions_master.categories.seed.csv",
        "transactions_master.payees.seed.csv",
    ]
    for filename in files:
        src = src_schema / filename
        if not src.exists():
            _fail(f"Missing required schema file: {src}")
        shutil.copy2(src, dst_schema / filename)


def _find_transaction_by_id(repo, transaction_id: str) -> Dict[str, Any]:
    target = str(transaction_id or "").strip().lower()
    rows = repo.list_transactions({"query": transaction_id})
    for row in rows:
        row_id = str(row.get("transactionId", "")).strip().lower()
        if row_id == target:
            return row
    _fail(f"Transaction not found after save: {transaction_id}")
    return {}


def _pick_category(repo, txn_type: str, txn_class: str) -> Tuple[str, str]:
    rows = repo.list_transaction_categories(txn_type=txn_type, txn_class=txn_class, include_inactive=False)
    if not rows:
        _fail(f"No category lookup rows for type={txn_type}, class={txn_class}")
    row = rows[0]
    code = str(row.get("categoryCode", "")).strip()
    name = str(row.get("categoryName", "")).strip()
    if not code or not name:
        _fail(f"Invalid category lookup row for type={txn_type}, class={txn_class}: {row}")
    return code, name


def _pick_billable_expense_category(repo) -> Tuple[str, str]:
    rows = repo.list_transaction_categories(txn_type="Expense", txn_class="Business", include_inactive=False)
    for row in rows:
        if int(row.get("billableAllowed", 0) or 0) == 1:
            code = str(row.get("categoryCode", "")).strip()
            name = str(row.get("categoryName", "")).strip()
            if code and name:
                return code, name
    return _pick_category(repo, "Expense", "Business")


def main() -> int:
    repo_root = _project_root()
    sys.path.insert(0, str(repo_root / "src" / "python"))

    from domain import schema_constants as sc
    from repositories.excel_repo import (  # pylint: disable=import-outside-toplevel
        ExcelRepo,
        TBL_TRANSACTION_ACCOUNTS,
        TBL_TRANSACTION_BUSINESS_UNITS,
        TBL_TRANSACTION_CATEGORIES,
        TBL_TRANSACTION_PAYEES,
    )
    from services.paths import AppPaths  # pylint: disable=import-outside-toplevel

    stamp = int(time.time())
    tmp_root = repo_root / f"tmp_phase5_smoke_{stamp}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)
    (tmp_root / "data").mkdir(parents=True, exist_ok=True)

    _copy_schema_seed_files(repo_root, tmp_root)

    repo = ExcelRepo(AppPaths(tmp_root))
    ensure_result = repo.ensure_schema()
    print(f"ensure_schema: changed={ensure_result.get('changed')} seedChanges={ensure_result.get('seedChanges')}")

    # Verify lookup seeds were physically persisted into workbook tables.
    accounts_rows = repo._read_table_rows(TBL_TRANSACTION_ACCOUNTS)  # pylint: disable=protected-access
    categories_rows = repo._read_table_rows(TBL_TRANSACTION_CATEGORIES)  # pylint: disable=protected-access
    bu_rows = repo._read_table_rows(TBL_TRANSACTION_BUSINESS_UNITS)  # pylint: disable=protected-access
    payee_rows = repo._read_table_rows(TBL_TRANSACTION_PAYEES)  # pylint: disable=protected-access

    _assert_true(len(accounts_rows) > 0, "Transaction account seeds were not persisted.")
    _assert_true(len(categories_rows) > 0, "Transaction category seeds were not persisted.")
    _assert_true(len(bu_rows) > 0, "Transaction business-unit seeds were not persisted.")
    _assert_true(len(payee_rows) > 0, "Transaction payee seeds were not persisted.")

    accounts = repo.list_transaction_accounts()
    business_units = repo.list_transaction_business_units()
    payees = repo.list_transaction_payees()
    _assert_true(len(accounts) >= 2, "Need at least two transaction accounts for transfer tests.")
    _assert_true(len(business_units) > 0, "No active business units available.")
    _assert_true(len(payees) > 0, "No active payees available.")

    from_account = str(accounts[0].get("accountName", "")).strip()
    transfer_to_account = ""
    for row in accounts:
        candidate = str(row.get("accountName", "")).strip()
        if candidate and candidate.lower() != from_account.lower():
            transfer_to_account = candidate
            break
    _assert_true(bool(transfer_to_account), "Could not pick a second account for transfer.")

    debt_to_account = ""
    for row in accounts:
        candidate = str(row.get("accountName", "")).strip()
        kind = str(row.get("accountKind", "")).strip().lower()
        if not candidate or candidate.lower() == from_account.lower():
            continue
        if kind in ("credit-card", "loc", "mortgage", "loan"):
            debt_to_account = candidate
            break
    _assert_true(bool(debt_to_account), "Could not find debt destination account kind for Debt Repayment.")

    payee = str(payees[0].get("payeeName", "")).strip()
    business_unit = str(business_units[0].get("businessUnit", "")).strip()
    _assert_true(bool(payee), "Selected payee is blank.")
    _assert_true(bool(business_unit), "Selected business unit is blank.")

    income_code, income_name = _pick_category(repo, "Income", "Business")
    expense_family_code, expense_family_name = _pick_category(repo, "Expense", "Family")
    transfer_code, transfer_name = _pick_category(repo, "Transfer", "Family")
    debt_code, debt_name = _pick_category(repo, "Debt Repayment", "Family")
    billable_code, billable_name = _pick_billable_expense_category(repo)

    base_payload = {
        "txnDate": "2026-02-27",
        "fromAccount": from_account,
        "member": "Joint",
        "currency": "CAD",
        "status": "Pending",
        "amount": 100.0,
        "taxAmount": 0.0,
    }

    txn_payloads = [
        {
            **base_payload,
            "class": "Business",
            "type": "Income",
            "businessUnit": business_unit,
            "payee": payee,
            "categoryCode": income_code,
            "categoryName": income_name,
            "amount": 1500.0,
            "notes": "phase5-income",
        },
        {
            **base_payload,
            "class": "Family",
            "type": "Expense",
            "payee": payee,
            "categoryCode": expense_family_code,
            "categoryName": expense_family_name,
            "amount": 125.55,
            "taxAmount": 16.32,
            "notes": "phase5-expense",
        },
        {
            **base_payload,
            "class": "Family",
            "type": "Transfer",
            "toAccount": transfer_to_account,
            "payee": "",
            "categoryCode": transfer_code,
            "categoryName": transfer_name,
            "amount": 200.0,
            "notes": "phase5-transfer",
        },
        {
            **base_payload,
            "class": "Family",
            "type": "Debt Repayment",
            "toAccount": debt_to_account,
            "payee": payee,
            "categoryCode": debt_code,
            "categoryName": debt_name,
            "amount": 300.0,
            "notes": "phase5-debt",
        },
    ]

    saved_ids: List[str] = []
    for payload in txn_payloads:
        result = repo.save_transaction(payload)
        _assert_true(bool(result.get("ok")), f"save_transaction failed: {result}")
        txn_id = str(result.get("transactionId", "")).strip()
        _assert_true(bool(txn_id), f"save_transaction returned blank transactionId: {result}")
        saved_ids.append(txn_id)
        row = _find_transaction_by_id(repo, txn_id)
        _assert_true(
            str(row.get("type", "")).strip().lower() == str(payload.get("type", "")).strip().lower(),
            f"Saved transaction type mismatch for {txn_id}: expected {payload.get('type')} got {row.get('type')}",
        )

    # Billable disbursement path should persist claim math and context.
    billable_payload = {
        **base_payload,
        "class": "Business",
        "type": "Expense",
        "businessUnit": business_unit,
        "payee": payee,
        "categoryCode": billable_code,
        "categoryName": billable_name,
        "amount": 100.0,
        "taxAmount": 13.0,
        "billClaimPct": 50.0,
        "parent": "Phase5 Parent",
        "client": "Phase5 Client",
        "matter": "Phase5 Matter",
        "notes": "phase5-billable",
    }
    billable_result = repo.save_transaction(billable_payload)
    _assert_true(bool(billable_result.get("ok")), f"Billable save failed: {billable_result}")
    billable_id = str(billable_result.get("transactionId", "")).strip()
    billable_row = _find_transaction_by_id(repo, billable_id)
    _assert_true(
        abs(float(billable_row.get("totalClaimAmount", 0.0)) - 56.5) < 0.001,
        f"Billable claim amount mismatch for {billable_id}: {billable_row.get('totalClaimAmount')}",
    )
    _assert_true(bool(str(billable_row.get("parent", "")).strip()), "Billable parent context was not persisted.")
    _assert_true(bool(str(billable_row.get("client", "")).strip()), "Billable client context was not persisted.")
    _assert_true(bool(str(billable_row.get("matter", "")).strip()), "Billable matter context was not persisted.")

    # Status lifecycle: Pending -> Cleared -> Reconciled -> Void
    lifecycle_payload = {
        **base_payload,
        "class": "Family",
        "type": "Expense",
        "payee": payee,
        "categoryCode": expense_family_code,
        "categoryName": expense_family_name,
        "amount": 42.0,
        "notes": "phase5-lifecycle",
    }
    lifecycle_result = repo.save_transaction(lifecycle_payload)
    _assert_true(bool(lifecycle_result.get("ok")), f"Lifecycle initial save failed: {lifecycle_result}")
    lifecycle_id = str(lifecycle_result.get("transactionId", "")).strip()
    _assert_true(bool(lifecycle_id), "Lifecycle transaction id was blank.")

    lifecycle_payload["transactionId"] = lifecycle_id
    lifecycle_payload["status"] = "Cleared"
    lifecycle_payload["clearedAt"] = ""
    cleared_result = repo.save_transaction(lifecycle_payload)
    _assert_true(bool(cleared_result.get("ok")), f"Lifecycle Cleared save failed: {cleared_result}")
    cleared_row = _find_transaction_by_id(repo, lifecycle_id)
    _assert_true(str(cleared_row.get("status", "")).strip() == "Cleared", "Expected Cleared status after update.")
    _assert_true(bool(str(cleared_row.get("clearedAt", "")).strip()), "ClearedAt should auto-populate for Cleared.")

    lifecycle_payload["status"] = "Reconciled"
    lifecycle_payload["reconciledAt"] = ""
    reconciled_result = repo.save_transaction(lifecycle_payload)
    _assert_true(bool(reconciled_result.get("ok")), f"Lifecycle Reconciled save failed: {reconciled_result}")
    reconciled_row = _find_transaction_by_id(repo, lifecycle_id)
    _assert_true(
        str(reconciled_row.get("status", "")).strip() == "Reconciled",
        "Expected Reconciled status after update.",
    )
    _assert_true(
        bool(str(reconciled_row.get("reconciledAt", "")).strip()),
        "ReconciledAt should auto-populate for Reconciled.",
    )

    lifecycle_payload["status"] = "Void"
    lifecycle_payload["voidReason"] = "Phase5 QA void"
    void_result = repo.save_transaction(lifecycle_payload)
    _assert_true(bool(void_result.get("ok")), f"Lifecycle Void save failed: {void_result}")
    void_row = _find_transaction_by_id(repo, lifecycle_id)
    _assert_true(str(void_row.get("status", "")).strip() == "Void", "Expected Void status after update.")

    # Void should be terminal.
    lifecycle_payload["status"] = "Pending"
    lifecycle_payload["voidReason"] = ""
    invalid_transition_message = ""
    try:
        invalid_reopen = repo.save_transaction(lifecycle_payload)
        if bool(invalid_reopen.get("ok")):
            _fail("Invalid lifecycle transition Void -> Pending should have failed.")
        invalid_transition_message = str(invalid_reopen.get("message", ""))
    except Exception as exc:
        invalid_transition_message = str(exc)
    _assert_true(
        "Invalid Status transition" in invalid_transition_message,
        f"Unexpected invalid transition message: {invalid_transition_message}",
    )

    all_rows = repo.list_transactions({})
    _assert_true(len(all_rows) >= 6, f"Unexpected transaction row count after smoke run: {len(all_rows)}")

    print("Phase 5 smoke checks passed.")
    print(f"Workspace: {tmp_root}")
    print(f"Saved transactions: {saved_ids}")
    print(f"Lifecycle transaction: {lifecycle_id}")
    print(f"Billable transaction: {billable_id}")
    print(f"Workbook path: {tmp_root / 'data' / 'CSPM.xlsm'}")
    print(f"Txn table: {sc.TBL_TRANSACTIONS_MASTER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
