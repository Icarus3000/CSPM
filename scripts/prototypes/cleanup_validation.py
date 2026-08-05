import os
import sys

def main():
    repo = r"C:\Projects\__CSPM"
    sys.path.insert(0, repo)
    
    os.environ["CSPM_USE_SQLITE"] = "1"
    
    try:
        from src.python.services.paths import AppPaths
        from src.python.backend.repo_facade import LazyRepoFacade
        paths = AppPaths(root=None)
        facade = LazyRepoFacade(paths)
        
        # Force lazy evaluation
        clients = facade.list_client_directory
        
        db_type = type(facade._db).__name__
        print(f"Test 11 - CSPM_USE_SQLITE=1 Ignored: {'ExcelRepo' in db_type} (Type is {db_type})")
    except Exception as e:
        print(f"Test 11 - Error: {e}")
        
    try:
        from src.python.database.sqlite_repo import SqliteMatterRepo
        print("Test 9 - Normal startup can import prototype? YES (FAIL)")
    except ImportError:
        print("Test 9 - Normal startup can import prototype? NO (PASS)")
        
    db_path = r"C:\Users\CorySchneider\AppData\Local\CSPM\Data\cspm.db"
    print(f"Test 10 - DB Exists? {os.path.exists(db_path)} (PASS if False)")
    
if __name__ == "__main__":
    main()
