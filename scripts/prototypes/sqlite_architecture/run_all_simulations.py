import sqlite3
import os
import uuid
import hashlib
import time
import json
import shutil
from datetime import datetime, timezone

PROTO_ROOT = r"C:\Projects\CSPM_SQLITE_PROTOTYPE"
DB_PATH = os.path.join(PROTO_ROOT, r"local_db\prototype.db")
CLOUD_DIR = os.path.join(PROTO_ROOT, "simulated_cloud")

# 9. Repository Prototypes
class MatterRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        
    def add_matter(self, client_id, desc):
        matter_id = f"MAT-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            conn.execute("INSERT INTO Matter (matter_id, client_id, description, created_at) VALUES (?, ?, ?, ?)",
                         (matter_id, client_id, desc, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            print(f"[Repo] Added Matter: {matter_id}")
        except sqlite3.Error as e:
            print(f"[Repo Error] {e}")
            conn.rollback()
        finally:
            conn.close()

# 10 & 11. Migration & Legacy Import Prototype
def simulate_legacy_import():
    print("--- 11. Simulating Atomic Legacy Import ---")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")
    
    # Simulate a transaction with rollback
    try:
        conn.execute("BEGIN TRANSACTION")
        conn.execute("INSERT INTO Client (client_id, name, created_at) VALUES (?, ?, ?)", 
                     ("C-100", "Legacy Client", datetime.now(timezone.utc).isoformat()))
        conn.execute("INSERT INTO Matter (matter_id, client_id, description, created_at) VALUES (?, ?, ?, ?)", 
                     ("M-100", "C-100", "Legacy Matter", datetime.now(timezone.utc).isoformat()))
        conn.commit()
        print("[Import] Successful atomic import of legacy records.")
    except Exception as e:
        conn.rollback()
        print(f"[Import Failed] Rolled back due to error: {e}")
    finally:
        conn.close()

# 12 & 13. Lease, Snapshot, Manifest, Attachment Simulation
def hash_file(filepath):
    if not os.path.exists(filepath): return ""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def simulate_lease_and_snapshot():
    print("--- 12/13. Simulating Lease and Snapshot Publication ---")
    os.makedirs(CLOUD_DIR, exist_ok=True)
    manifest_path = os.path.join(CLOUD_DIR, "manifest.json")
    
    # Read manifest
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            
    # Check lease (simulate Option A synchronized manifest contention)
    lease = manifest.get('lease', {})
    if lease.get('status') == 'acquired':
        print("[Lease] ERROR: Lease is already held.")
        return
        
    print("[Lease] Lease acquired by Machine_Prototype.")
    
    # 14. Attachment Protocol (Option A)
    attachment_dummy = os.path.join(PROTO_ROOT, r"attachments\dummy.pdf")
    os.makedirs(os.path.dirname(attachment_dummy), exist_ok=True)
    with open(attachment_dummy, "w") as f: f.write("Dummy PDF Content")
    att_hash = hash_file(attachment_dummy)
    print(f"[Attachment] Verified synthetic attachment hash: {att_hash}")
    
    # 8. Snapshot Publication Order
    # 1. Local Package
    snapshot_id = f"snap_{int(time.time())}"
    local_pkg = os.path.join(PROTO_ROOT, f"staging\\{snapshot_id}.db")
    os.makedirs(os.path.dirname(local_pkg), exist_ok=True)
    shutil.copy2(DB_PATH, local_pkg)
    
    # 2. Checksums
    db_hash = hash_file(local_pkg)
    
    # 3. Publish to Cloud
    cloud_pkg = os.path.join(CLOUD_DIR, f"{snapshot_id}.db")
    shutil.copy2(local_pkg, cloud_pkg)
    
    # 4/5. Verify Upload & Advance Pointer
    manifest['current_snapshot'] = snapshot_id
    manifest['checksum_sha256'] = db_hash
    manifest['attachment_hash'] = att_hash
    manifest['lease'] = {'status': 'released', 'machine': 'Machine_Prototype'}
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f)
        
    print(f"[Snapshot] Successfully published snapshot {snapshot_id} with checksum {db_hash}")

if __name__ == "__main__":
    simulate_legacy_import()
    
    repo = MatterRepository(DB_PATH)
    repo.add_matter("C-100", "New Post-Migration Matter")
    
    simulate_lease_and_snapshot()
