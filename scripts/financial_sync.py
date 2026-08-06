#!/usr/bin/env python3
"""Run the governed historic-finance synchronization outside the live workbook.

Examples:
  python -I scripts/financial_sync.py preview --source "C:\\...\\Dockets.xlsm"
  python -I scripts/financial_sync.py candidate --source "C:\\...\\Dockets.xlsm"
  python -I scripts/financial_sync.py promote --candidate <candidate> --audit <audit> --confirm-promote
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = ROOT / "src" / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from services.financial_sync_service import FinancialSyncError, FinancialSyncService
from services.paths import AppPaths


DEFAULT_SOURCE = Path(r"C:\Users\cschn\OneDrive - LPN\__Invoices (1)\Dockets.xlsm")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or promote an auditable historic-finance CSPM synchronization.")
    parser.add_argument("command", choices=("preview", "candidate", "promote"))
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Authoritative historic Dockets.xlsm workbook.")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "financial_sync_candidate"), help="Safe candidate/audit directory.")
    parser.add_argument("--candidate", default="", help="Candidate workbook to promote.")
    parser.add_argument("--audit", default="", help="Audit JSON produced with the candidate.")
    parser.add_argument("--confirm-promote", action="store_true", help="Required: permit the explicit live workbook replacement.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    service = FinancialSyncService(AppPaths(ROOT))
    try:
        if args.command == "preview":
            result = service.preview(args.source)
        elif args.command == "candidate":
            result = service.build_candidate(args.source, args.output_dir)
        else:
            if not args.confirm_promote:
                raise FinancialSyncError("Promotion is intentionally blocked. Close CSPM and repeat with --confirm-promote.")
            result = service.promote_candidate(args.candidate, args.audit)
    except FinancialSyncError as exc:
        result = {"ok": False, "message": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
