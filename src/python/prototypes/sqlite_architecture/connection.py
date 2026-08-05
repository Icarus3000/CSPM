# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
import os
import sqlite3
import threading

# Thread-local storage for SQLite connections to avoid cross-thread blocking issues
_local = threading.local()

def get_db_path() -> str:
    """
    Returns the strict path for the PROTOTYPE database.
    It MUST be inside an explicit CSPM_PROTOTYPE_ROOT.
    """
    proto_root = os.environ.get('CSPM_PROTOTYPE_ROOT')
    if not proto_root:
        raise RuntimeError("PROTOTYPE ISOLATION ERROR: CSPM_PROTOTYPE_ROOT must be explicitly set.")
        
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if local_appdata and local_appdata.lower() in proto_root.lower():
        raise RuntimeError("PROTOTYPE ISOLATION ERROR: Prototype root cannot be in LOCALAPPDATA.")
        
    if "onedrive" in proto_root.lower() or "sharepoint" in proto_root.lower():
        raise RuntimeError("PROTOTYPE ISOLATION ERROR: Prototype root cannot be in OneDrive/SharePoint.")
        
    repo_root = os.path.normcase(os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))))
    norm_proto = os.path.normcase(os.path.normpath(proto_root))
    if norm_proto.startswith(repo_root):
        raise RuntimeError("PROTOTYPE ISOLATION ERROR: Prototype root cannot be inside the live repository.")
    
    os.makedirs(proto_root, exist_ok=True)
    return os.path.join(proto_root, 'cspm_prototype.db')

def get_connection() -> sqlite3.Connection:
    """
    Returns a thread-local SQLite connection with strict pragmas enforced.
    """
    db_path = get_db_path()
    
    if not hasattr(_local, 'conn') or _local.conn is None:
        # uri=True enables WAL mode correctly in some sqlite drivers
        _local.conn = sqlite3.connect(db_path, check_same_thread=True, timeout=5.0)
        _local.conn.row_factory = sqlite3.Row
        
        # Enforce architecture requirements
        _local.conn.execute("PRAGMA foreign_keys = ON;")
        _local.conn.execute("PRAGMA journal_mode = WAL;")
        _local.conn.execute("PRAGMA synchronous = NORMAL;")
    
    return _local.conn

def close_connection():
    """
    Closes the thread-local connection cleanly.
    """
    if hasattr(_local, 'conn') and _local.conn is not None:
        _local.conn.close()
        _local.conn = None

def init_schema():
    """
    Initializes the database schema if it doesn't exist.
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    if not os.path.exists(schema_path):
        raise FileNotFoundError("schema.sql not found in the database module.")
        
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
        
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
