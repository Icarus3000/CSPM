import os
import sys

def main():
    repo = r"C:\Projects\__CSPM"
    sys.path.insert(0, os.path.join(repo, "src", "python"))
    
    # 1. Simulate the exact environment variable state we want to test
    if "--use-sqlite" in sys.argv:
        os.environ["CSPM_USE_SQLITE"] = "1"
        print("\n=== PROBING WITH CSPM_USE_SQLITE=1 ===")
    else:
        os.environ.pop("CSPM_USE_SQLITE", None)
        print("\n=== PROBING WITH CSPM_USE_SQLITE=0 ===")
        
    # 2. Import the real AppController and RuntimeConfig exactly as main.py does
    from backend.app_controller import AppController
    from backend.runtime_config import RuntimeConfig
    
    # 3. Create the real RuntimeConfig
    runtime_config = RuntimeConfig(
        startup_splash_logo_url="",
        startup_splash_static_logo_url="",
    )
    
    # 4. Create the real AppController
    controller = AppController(
        runtime_config=runtime_config,
        defer_settings_load=False,
    )
    
    # 5. Extract the instantiated backend objects
    facade = controller._excel_repo
    
    # Force hydration to ensure the database actually loads
    _ = facade.list_client_directory()
    
    # 6. Report the instantiated types and paths
    db_type = type(facade).__name__
    print(f"Instantiated DB Type: {db_type}")
    print(f"Is ExcelRepo? {db_type == 'ExcelRepo'}")
    print(f"Repo module path: {facade.__class__.__module__}")
    if hasattr(facade, "_paths"):
        print(f"Workbook path: {facade._paths.cspm_data_path}")
        
    # 7. Check for prototype modules in sys.modules
    sqlite_modules = [m for m in sys.modules if "sqlite_architecture" in m]
    print(f"Prototype modules loaded in sys.modules: {sqlite_modules}")
    
    # 8. Check for database file creation in LOCALAPPDATA
    db_path = r"C:\Users\CorySchneider\AppData\Local\CSPM\Data\cspm.db"
    print(f"cspm.db created in LOCALAPPDATA? {os.path.exists(db_path)}")
    print(f"cspm.db-wal created in LOCALAPPDATA? {os.path.exists(db_path + '-wal')}")
    print(f"cspm.db-shm created in LOCALAPPDATA? {os.path.exists(db_path + '-shm')}")
    
    # Clean up PySide6 instances explicitly to avoid crash on exit
    controller.deleteLater()

if __name__ == "__main__":
    main()
