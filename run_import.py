import sys
import os
from pathlib import Path

# Add src/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "python"))

from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo
from services.dockets_import_service import DocketsImportService

def run():
    paths = AppPaths(Path(__file__).resolve().parent)
    repo = ExcelRepo(paths)
    source_path = str(Path(__file__).resolve().parent / "data" / "Dockets.xlsm")
    
    def duplicate_callback(payload):
        kind = (payload.get("kind") or "").lower()
        if kind == "client":
            return {"action": "skip", "scope": "one"}
        return {"action": "add", "scope": "one"}
    
    result = DocketsImportService(repo).import_legacy_workbook(
        source_path,
        duplicate_callback=duplicate_callback,
    )
    
    ledger_warns = [w for w in result.get("warnings", []) if "Ledger" in w]
    print(f"Total Ledger warnings: {len(ledger_warns)}")
    print("First 10 ledger warnings:")
    for w in ledger_warns[:10]:
        print(w)

if __name__ == "__main__":
    run()
