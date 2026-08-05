import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = r"C:\Users\CorySchneider\AppData\Local\CSPM\Data\cspm.db"

def hash_file(filepath):
    if not os.path.exists(filepath): return "NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def main():
    print("=== FORENSIC DB ANALYSIS ===")
    print(f"Path: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database not found. Exiting.")
        return
        
    stats = os.stat(DB_PATH)
    print(f"Size: {stats.st_size} bytes")
    print(f"Creation Time: {datetime.fromtimestamp(stats.st_ctime)}")
    print(f"Modified Time: {datetime.fromtimestamp(stats.st_mtime)}")
    print(f"SHA-256: {hash_file(DB_PATH)}")
    
    print(f"WAL Exists: {os.path.exists(DB_PATH + '-wal')}")
    print(f"SHM Exists: {os.path.exists(DB_PATH + '-shm')}")
    
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA user_version;")
        print(f"PRAGMA user_version: {cursor.fetchone()[0]}")
        
        cursor.execute("PRAGMA journal_mode;")
        print(f"PRAGMA journal_mode: {cursor.fetchone()[0]}")
        
        cursor.execute("PRAGMA integrity_check;")
        print(f"PRAGMA integrity_check: {cursor.fetchone()[0]}")
        
        cursor.execute("PRAGMA foreign_key_check;")
        fk_issues = cursor.fetchall()
        print(f"PRAGMA foreign_key_check: {'OK' if not fk_issues else fk_issues}")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables: {tables}")
        
        total_rows = 0
        for table in tables:
            cursor.execute(f"SELECT count(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table '{table}' rows: {count}")
            total_rows += count
            
        print(f"\nTotal User Rows in DB: {total_rows}")
        
    except Exception as e:
        print(f"SQLite Inspection Error: {e}")
        
if __name__ == "__main__":
    main()
