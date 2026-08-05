import os
import hashlib

def hash_file(filepath):
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def validate_paths():
    print("--- Path Validation ---")
    
    # 1. Authoritative Workbooks
    cspm_path = r"C:\Projects\__CSPM\data\CSPM.xlsm"
    dockets_path = r"C:\Projects\__CSPM\data\Dockets.xlsm"
    
    print(f"CSPM Path: {cspm_path}")
    print(f"Dockets Path: {dockets_path}")
    
    cspm_hash = hash_file(cspm_path)
    dockets_hash = hash_file(dockets_path)
    
    print(f"CSPM.xlsm SHA256: {cspm_hash}")
    print(f"Dockets.xlsm SHA256: {dockets_hash}")
    
    # 2. Disposable Prototype Root
    proto_root = r"C:\Projects\CSPM_SQLITE_PROTOTYPE"
    print(f"Prototype Root: {proto_root}")
    
    # 3. Check against banned paths
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    onedrive = os.environ.get('OneDrive', '')
    
    banned_paths = [local_appdata, onedrive, r"C:\Projects\__CSPM\data"]
    
    for banned in banned_paths:
        if banned and proto_root.lower().startswith(banned.lower()):
            print(f"ERROR: Prototype root {proto_root} is inside banned path {banned}")
            return False
            
    print("Path isolation successful.")
    
    # Save hashes for later comparison
    import json
    os.makedirs(r"C:\Projects\__CSPM\outputs", exist_ok=True)
    with open(r"C:\Projects\__CSPM\outputs\workbook_hashes_before.json", "w") as f:
        json.dump({"CSPM": cspm_hash, "Dockets": dockets_hash}, f)
        
if __name__ == "__main__":
    validate_paths()
