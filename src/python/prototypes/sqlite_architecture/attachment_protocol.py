# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
import os
import hashlib
from typing import Dict, Any
from src.python.database.connection import get_connection

def hash_file(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def migrate_and_link_attachment(source_path: str, entity_id: str, dest_folder: str) -> Dict[str, Any]:
    """
    Option A: Copies an attachment to the cloud-synced destination folder.
    Stores the metadata linking it to the specific entity_id in the SQLite DB.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source attachment not found: {source_path}")
        
    os.makedirs(dest_folder, exist_ok=True)
    filename = os.path.basename(source_path)
    dest_path = os.path.join(dest_folder, filename)
    
    # In a real migration, we would copy the file here:
    # shutil.copy2(source_path, dest_path)
    
    # Generate SHA-256
    file_hash = hash_file(source_path)
    
    # Store metadata in DB
    conn = get_connection()
    try:
        # Assuming we have an Attachment table (will be added to schema later if needed)
        # For now we log it to SyncManifest to represent the attachment manifest link
        key = f"attachment_link_{entity_id}_{file_hash[:8]}"
        value = f"filename={filename};hash={file_hash}"
        conn.execute("INSERT OR REPLACE INTO SyncManifest (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
        
    return {
        "filename": filename,
        "hash": file_hash,
        "status": "Linked"
    }
