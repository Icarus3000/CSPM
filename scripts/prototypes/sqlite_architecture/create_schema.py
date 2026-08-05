import sqlite3
import os

def create_schema():
    db_path = r"C:\Projects\CSPM_SQLITE_PROTOTYPE\local_db\prototype.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    
    # 4. Local SQLite Design requirements
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    
    # Schema Definition (Provisional)
    schema_sql = """
    CREATE TABLE IF NOT EXISTS Client (
        client_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS Matter (
        matter_id TEXT PRIMARY KEY,
        client_id TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Open',
        created_at TEXT NOT NULL,
        FOREIGN KEY (client_id) REFERENCES Client(client_id)
    );
    
    CREATE TABLE IF NOT EXISTS TimeEntry (
        time_id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL,
        date TEXT NOT NULL,
        hours REAL NOT NULL,
        rate REAL NOT NULL,
        amount REAL NOT NULL, -- Cached formula value (Rate * Hours)
        is_billed INTEGER DEFAULT 0,
        FOREIGN KEY (matter_id) REFERENCES Matter(matter_id)
    );
    
    CREATE TABLE IF NOT EXISTS SyncMetadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
    
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print(f"PROVISIONAL prototype schema created at {db_path}")

if __name__ == "__main__":
    create_schema()
