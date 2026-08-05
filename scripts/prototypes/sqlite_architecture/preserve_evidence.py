import os
import shutil
import subprocess
import hashlib
from datetime import datetime

EVIDENCE_DIR = r"C:\CSPM_EVIDENCE\evidence_" + datetime.now().strftime("%Y%m%d_%H%M%S")
REPO_DIR = r"C:\Projects\__CSPM"
DB_PATH = r"C:\Users\CorySchneider\AppData\Local\CSPM\Data\cspm.db"

def run_cmd(cmd):
    result = subprocess.run(cmd, cwd=REPO_DIR, shell=True, capture_output=True, text=True)
    return result.stdout.strip() + "\n" + result.stderr.strip()

def hash_file(filepath):
    if not os.path.exists(filepath):
        return "NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    print(f"Creating evidence package at {EVIDENCE_DIR}")
    
    with open(os.path.join(EVIDENCE_DIR, "git_status.txt"), "w") as f:
        f.write(run_cmd("git status --short"))
        
    with open(os.path.join(EVIDENCE_DIR, "git_commit.txt"), "w") as f:
        f.write(run_cmd("git log --oneline -1"))
        
    with open(os.path.join(EVIDENCE_DIR, "git_diff_stat.txt"), "w") as f:
        f.write(run_cmd("git diff --stat 14ea570^"))
        
    with open(os.path.join(EVIDENCE_DIR, "git_diff.txt"), "w") as f:
        f.write(run_cmd("git diff 14ea570^"))
        
    with open(os.path.join(EVIDENCE_DIR, "workbooks.txt"), "w") as f:
        for wb in ["CSPM.xlsm", "Dockets.xlsm"]:
            p = os.path.join(REPO_DIR, "data", wb)
            f.write(f"{wb} | {hash_file(p)} | Size: {os.path.getsize(p) if os.path.exists(p) else 0}\n")
            
    with open(os.path.join(EVIDENCE_DIR, "db_inventory.txt"), "w") as f:
        f.write(f"LOCALAPPDATA DB: {DB_PATH}\n")
        if os.path.exists(DB_PATH):
            f.write(f"Size: {os.path.getsize(DB_PATH)}\nHash: {hash_file(DB_PATH)}\n")
        else:
            f.write("DB NOT FOUND\n")
            
    # Copy files
    src_dir = os.path.join(EVIDENCE_DIR, "src_backup")
    os.makedirs(src_dir, exist_ok=True)
    
    sqlite_files = [
        r"src\python\database\schema.sql",
        r"src\python\database\connection.py",
        r"src\python\database\sqlite_repo.py",
        r"src\python\database\migration.py",
        r"src\python\database\attachment_protocol.py",
        r"src\python\backend\repo_facade.py"
    ]
    for rel_path in sqlite_files:
        full_path = os.path.join(REPO_DIR, rel_path)
        if os.path.exists(full_path):
            dest = os.path.join(src_dir, os.path.basename(rel_path))
            shutil.copy2(full_path, dest)
            
    # Copy DB itself
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, os.path.join(EVIDENCE_DIR, "cspm.db"))
        
    print(f"Evidence preservation complete: {EVIDENCE_DIR}")

if __name__ == "__main__":
    main()
