import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "python"))

from services.dockets_import_service import LegacyDocketsImportService
from data.excel_repo import ExcelRepo

def main():
    repo = ExcelRepo(os.path.join(os.path.dirname(__file__), "data", "CSPM.xlsm"))
    service = LegacyDocketsImportService(repo)
    
    # Manually trigger _build_duplicate_maps
    existing_clients = list(repo.list_client_names())
    service._build_duplicate_maps(existing_clients)
    
    # Print a few transaction keys to see what they look like
    txn_keys = list(service._duplicate_maps.get("transaction", {}).keys())
    print(f"Total transaction duplicates mapped: {len(txn_keys)}")
    
    print("\nSample Transaction Keys (first 5):")
    for k in txn_keys[:5]:
        print(repr(k))
        
    print("\nLooking for Next Millennium Farms 2025-01-31:")
    for k in txn_keys:
        if "2025-01-31" in k and "next millennium" in k:
            print(repr(k))
            
if __name__ == "__main__":
    main()
