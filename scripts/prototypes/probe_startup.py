import os
import sys

def run_probe(attempt: int, use_sqlite: bool):
    print(f"\n--- PROBE {attempt} (CSPM_USE_SQLITE={'1' if use_sqlite else '0'}) ---")
    if use_sqlite:
        os.environ["CSPM_USE_SQLITE"] = "1"
    else:
        os.environ.pop("CSPM_USE_SQLITE", None)
        
    try:
        from services.paths import AppPaths
        from backend.repo_facade import LazyRepoFacade
        
        paths = AppPaths(root=r"C:\Projects\__CSPM")
        facade = LazyRepoFacade(paths)
        
        # force evaluation
        _ = facade.list_client_directory
        db_type = type(facade._db).__name__
        
        print(f"Repo instantiated: {db_type}")
        print(f"Is ExcelRepo? {db_type == 'ExcelRepo'}")
        
    except Exception as e:
        print(f"Startup Exception: {e}")
        
    db_path = r"C:\Users\CorySchneider\AppData\Local\CSPM\Data\cspm.db"
    db_exists = os.path.exists(db_path)
    wal_exists = os.path.exists(db_path + "-wal")
    shm_exists = os.path.exists(db_path + "-shm")
    
    print(f"cspm.db exists in LOCALAPPDATA? {db_exists}")
    print(f"WAL exists? {wal_exists}")
    print(f"SHM exists? {shm_exists}")
    
    if db_exists or wal_exists or shm_exists:
        print("WARNING: Database or artifacts were created!")
    else:
        print("PASS: No database created.")

def main():
    repo = r"C:\Projects\__CSPM"
    sys.path.insert(0, os.path.join(repo, "src", "python"))
    
    run_probe(1, use_sqlite=False)
    run_probe(2, use_sqlite=True)

if __name__ == "__main__":
    main()
