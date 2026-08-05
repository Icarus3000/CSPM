import os
import sys
import logging

def configure_logger():
    logging.basicConfig(level=logging.INFO)

def run_parity_test():
    """
    Tests the parity of data read from Excel vs SQLite using strictly
    isolated prototype modules and read-only access.
    THIS IS NOT A DUAL-WRITE IMPLEMENTATION.
    """
    # Require explicit prototype root
    proto_root = os.environ.get('CSPM_PROTOTYPE_ROOT')
    if not proto_root:
        raise RuntimeError("PROTOTYPE ISOLATION FAULT: CSPM_PROTOTYPE_ROOT must be explicitly set.")
        
    print(f"Executing disposable parity comparison inside prototype root: {proto_root}")
        
    repo_root = r"C:\Projects\__CSPM"
    sys.path.insert(0, os.path.join(repo_root, "src", "python"))

    from services.paths import AppPaths
    from repositories.excel_repo import ExcelRepo
    from repositories.client_repo import ClientRepo
    from prototypes.sqlite_architecture.sqlite_repo import SqliteRepo
    from prototypes.sqlite_architecture.sqlite_repo import SqliteClientRepo
    
    paths = AppPaths(root=repo_root)
    
    # 1. Read-only against Excel
    print("\n--- Reading from Excel ---")
    excel_db = ExcelRepo(paths)
    excel_client = ClientRepo(excel_db)
    
    try:
        clients_excel = excel_client.list_client_directory()
        excel_count = len(clients_excel)
        print(f"[Excel] Retrieved {excel_count} clients.")
    except Exception as e:
        print(f"[Excel] Error: {e}")
        excel_count = -1
        
    # 2. Read-only against isolated SQLite Prototype
    print("\n--- Reading from Prototype SQLite ---")
    
    # The SqliteRepo and its underlying connection enforce prototype paths natively
    sqlite_db = SqliteRepo()
    sqlite_client = SqliteClientRepo()
    
    try:
        clients_sqlite = sqlite_client.list_client_directory()
        sqlite_count = len(clients_sqlite)
        print(f"[SQLite] Retrieved {sqlite_count} clients.")
    except Exception as e:
        print(f"[SQLite] Error: {e}")
        sqlite_count = -1
        
    print("\n--- Parity Reconciliation Report ---")
    if excel_count == sqlite_count:
        print("PASS: Both repositories returned the same number of clients.")
    else:
        print(f"WARN: Mismatch! Excel={excel_count}, SQLite={sqlite_count}. The prototype SQLite database may not be hydrated.")
        
    print("\nNOTICE: This script is for prototype verification only. It does not use production dependency injection.")

if __name__ == "__main__":
    configure_logger()
    run_parity_test()
