"""
Diagnostic script: compare Python financial_dashboard_report output against legacy benchmarks.
Targets (YTD 2026):
  Revenue + WIP:       ~$176,098.21
  Adjusted Production: ~$174,950.25
"""
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "python"))

from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo

paths = AppPaths(Path(__file__).resolve().parent)
repo = ExcelRepo(paths)
result = repo.financial_dashboard_report(2026)

summary = result.get("summary", {})

print("=" * 60)
print("FINANCIAL DASHBOARD REPORT — YTD 2026")
print("=" * 60)

for k, v in sorted(summary.items()):
    if isinstance(v, (int, float)):
        print(f"  {k:30s}  ${v:>12,.2f}")
    else:
        print(f"  {k:30s}  {v}")

print()
print("=" * 60)
print("BENCHMARK COMPARISON")
print("=" * 60)

rev_wip = summary.get("revenueIncludingWip", 0.0)
prod    = summary.get("docketedAmount", 0.0)  # Adjusted Production

target_rev_wip = 176098.21
target_prod    = 174950.25

delta_rev = rev_wip - target_rev_wip
delta_prod = prod - target_prod

print(f"  {'Metric':25s} {'Python':>14s} {'Excel Target':>14s} {'Delta':>12s}")
print(f"  {'-'*25} {'-'*14} {'-'*14} {'-'*12}")
print(f"  {'Revenue + WIP':25s} ${rev_wip:>12,.2f}  ${target_rev_wip:>12,.2f}  ${delta_rev:>+10,.2f}")
print(f"  {'Adjusted Production':25s} ${prod:>12,.2f}  ${target_prod:>12,.2f}  ${delta_prod:>+10,.2f}")
print()
if abs(delta_rev) < 50 and abs(delta_prod) < 50:
    print("  PASS -- Both metrics within $50 tolerance.")
else:
    print("  FAIL -- Discrepancy exceeds $50 tolerance. Investigate.")
    print()
    # Additional breakdown for diagnosis
    print("  Additional details:")
    print(f"    billedTimeAmount:  ${summary.get('billedTimeAmount', 0.0):>12,.2f}")
    print(f"    wipAmount:         ${summary.get('wipAmount', 0.0):>12,.2f}")
    print(f"    wipHours:          {summary.get('wipHours', 0.0):>12.1f}")
    print(f"    expenses:          ${summary.get('expenses', 0.0):>12,.2f}")
