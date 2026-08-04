import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "src" / "python"))

from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo

paths = AppPaths(root)
repo = ExcelRepo(paths)
dashboard = repo.financial_dashboard_report(2026)
summary = dashboard.get("summary", {})

rev_wip = summary.get("revenueIncludingWip", 0.0)
prod = summary.get("docketedAmount", 0.0)

target_rev_wip = 176098.21
target_prod = 174950.25

delta_rev = rev_wip - target_rev_wip
delta_prod = prod - target_prod

print(f"Metric                            Python   Excel Target        Delta")
print(f"------------------------- -------------- -------------- ------------")
print(f"Revenue + WIP             ${rev_wip:>12,.2f}  ${target_rev_wip:>12,.2f}  ${delta_rev:>+10,.2f}")
print(f"Adjusted Production       ${prod:>12,.2f}  ${target_prod:>12,.2f}  ${delta_prod:>+10,.2f}")

print(f"\nDashboard details:")
for k in ["billedTimeAmount", "wipAmount", "wipHours", "ledgerBillings", "expenses", "bankedAmount"]:
    v = summary.get(k, "N/A")
    if isinstance(v, float):
        print(f"  {k:30s}: ${v:>12,.2f}")
    else:
        print(f"  {k:30s}: {v}")
