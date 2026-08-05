import os
import json

def inventory_settings():
    settings = {
        "user_settings.json": {
            "type": "user-local preference",
            "path": r"C:\Projects\__CSPM\user_settings.json"
        },
        "environment variables": {
            "type": "environment-specific secret / machine-specific state",
            "notes": "System environment variables for DB paths and API keys"
        }
    }
    return settings

def inventory_consumers():
    consumers = {
        "ui_components": "Reads from view models, which read from controllers",
        "controllers": "Injects repositories (e.g. AppController -> ExcelRepo)",
        "dockets_import_service": "Reads staging files, updates ExcelRepo",
        "legacy_macro_scripts": "External VBA scripts that rely on CSPM.xlsm being open"
    }
    return consumers

if __name__ == "__main__":
    out_path = r"C:\Projects\CSPM_SQLITE_PROTOTYPE\reports\inventory_settings.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    report = {
        "settings": inventory_settings(),
        "consumers": inventory_consumers()
    }
    
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Settings and consumers inventory saved to {out_path}")
