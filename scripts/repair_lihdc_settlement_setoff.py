"""Rebuild the verified 2026-07-29 LIHDC settlement set-off evidence.

This is a one-time, guarded migration for the local CSPM workbook.  It backs
up the workbook before applying any change and refuses to proceed unless all
six legacy allocations still match their invoices and the LIHDC A/P bill.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from repositories.excel_repo import ExcelRepo
from services.ap_setoff_service import APSetoffService
from services.paths import AppPaths


WORKBOOK_DEFAULT = Path.home() / "AppData" / "Local" / "CSPM" / "Data" / "CSPM.xlsm"
PAYMENT_ID = "APP-SET-LIHDC-20260729"
LEGACY_SETTLEMENT_EXPENSE_ID = "TXN_ae49ee9df9"
REPAIR_PAYLOAD = {
    "APPaymentID": PAYMENT_ID,
    "APBillID": "APB-1786049922093",
    "PaymentDate": "2026-07-29",
    "Amount": 5677.41,
    "Reference": "LIHDC settlement agreement — 2026-07-29",
    "Notes": "Reconstructed from verified historic settlement set-off allocations.",
    "Allocations": [
        {"InvoiceID": "26-0042", "Amount": 156.23},
        {"InvoiceID": "26-0054", "Amount": 2117.91},
        {"InvoiceID": "26-0051", "Amount": 187.47},
        {"InvoiceID": "26-0052", "Amount": 316.40},
        {"InvoiceID": "26-0066", "Amount": 249.96},
        {"InvoiceID": "26-0069", "Amount": 2649.44},
    ],
    "LegacyTransactionIDs": [
        "TXN_325ec162ca",
        "TXN_643e8ed2f0",
        "TXN_8a9c5684f8",
        "TXN_85a80a60c4",
        "TXN_85ddc3a0c0",
        "TXN_e0add4a5d6",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=WORKBOOK_DEFAULT)
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "outputs" / "data_backups")
    parser.add_argument("--apply", action="store_true", help="Apply the verified repair after creating a backup.")
    parser.add_argument(
        "--retire-superseded-expense-only",
        action="store_true",
        help="Void only the bank-labelled duplicate settlement expense after the governed set-off exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workbook = args.workbook.expanduser().resolve()
    if not workbook.is_file():
        raise SystemExit(f"Workbook not found: {workbook}")
    if not args.apply:
        print("DRY RUN: no data was changed. Re-run with --apply to create the backup and repair the set-off.")
        print(f"Workbook: {workbook}")
        print(f"A/P payment: {PAYMENT_ID}; allocations: {len(REPAIR_PAYLOAD['Allocations'])}; total: $5,677.41")
        return 0

    backup_dir = args.backup_dir.expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"CSPM_before_LIHDC_setoff_repair_{stamp}.xlsm"
    shutil.copy2(workbook, backup)

    paths = AppPaths(root=PROJECT_ROOT, override_data_dir=workbook.parent)
    repo = ExcelRepo(paths)
    service = APSetoffService(repo)
    if args.retire_superseded_expense_only:
        result = service.retire_superseded_historic_settlement_expense(
            REPAIR_PAYLOAD["APBillID"], PAYMENT_ID, LEGACY_SETTLEMENT_EXPENSE_ID
        )
        print(result["message"])
        print(f"Backup: {backup}")
        print(f"Voided duplicate expense: {result['transactionId']}")
        return 0
    result = service.reconstruct_historic_setoff(REPAIR_PAYLOAD)
    retirement = service.retire_superseded_historic_settlement_expense(
        REPAIR_PAYLOAD["APBillID"], PAYMENT_ID, LEGACY_SETTLEMENT_EXPENSE_ID
    )
    print(result["message"])
    print(retirement["message"])
    print(f"Backup: {backup}")
    print(f"Set-off payment: {result['APPaymentID']}; allocations: {result['allocationCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
