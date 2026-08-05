import os
import subprocess
import hashlib
import glob
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip() + "\n" + result.stderr.strip()

def hash_file(filepath):
    if not os.path.exists(filepath):
        return "FILE NOT FOUND"
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def main():
    print("=== GIT STATUS ===")
    print(run_cmd("git status --short"))
    
    print("\n=== GIT DIFF STAT ===")
    print(run_cmd("git diff --stat"))
    
    print("\n=== GIT DIFF ===")
    print(run_cmd("git diff"))
    
    print("\n=== GIT LOG ===")
    print(run_cmd("git log --oneline -10"))
    
    print("\n=== WORKBOOK HASHES ===")
    cspm_path = r"C:\Projects\__CSPM\data\CSPM.xlsm"
    dockets_path = r"C:\Projects\__CSPM\data\Dockets.xlsm"
    print(f"CSPM.xlsm: {hash_file(cspm_path)}")
    print(f"Dockets.xlsm: {hash_file(dockets_path)}")
    
    print("\n=== LOCALAPPDATA DB CHECK ===")
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if local_appdata:
        db_path = os.path.join(local_appdata, 'CSPM', 'Data', 'cspm.db')
        print(f"Path: {db_path}")
        print(f"Exists: {os.path.exists(db_path)}")
        if os.path.exists(db_path):
            print(f"Size: {os.path.getsize(db_path)} bytes")
            print(f"Hash: {hash_file(db_path)}")
    else:
        print("LOCALAPPDATA env var not found.")
        
    print("\n=== GLOBAL DB SEARCH ===")
    # Search for cspm.db in project root and prototype root
    project_root = r"C:\Projects\__CSPM"
    proto_root = r"C:\Projects\CSPM_SQLITE_PROTOTYPE"
    
    for root in [project_root, proto_root]:
        if not os.path.exists(root): continue
        for r, d, f in os.walk(root):
            for file in f:
                if file.endswith(".db"):
                    p = os.path.join(r, file)
                    print(f"Found DB: {p} - Size: {os.path.getsize(p)} - Hash: {hash_file(p)}")

    print("\n=== KEYWORD SEARCH ===")
    print(run_cmd(r'findstr /S /I /M "CSPM_USE_SQLITE SqliteRepo sqlite3.connect schema.sql cspm.db" C:\Projects\__CSPM\src\python\*.py'))

if __name__ == "__main__":
    main()
