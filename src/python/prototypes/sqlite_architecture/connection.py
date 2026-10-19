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

def get_connection(db_path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """
    Returns a thread-local SQLite connection with strict pragmas enforced.
    When db_path is provided (e.g. PathService.sqlite_db_path() -> %LOCALAPPDATA%/CSPM/data/cspm.db),
    connects to that database with WAL mode enabled.
    """
    resolved_path = os.fspath(db_path) if db_path is not None else get_db_path()
    parent_dir = os.path.dirname(os.path.abspath(resolved_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    conn_map = getattr(_local, "conn_map", None)
    if conn_map is None:
        conn_map = {}
        _local.conn_map = conn_map

    norm_key = os.path.normcase(os.path.abspath(resolved_path))
    conn = conn_map.get(norm_key)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
        except sqlite3.Error:
            conn = None
            conn_map.pop(norm_key, None)

    if conn is None:
        conn = sqlite3.connect(resolved_path, check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn_map[norm_key] = conn

    if db_path is None:
        _local.conn = conn
    return conn


def close_connection(db_path: str | os.PathLike | None = None):
    """
    Closes the thread-local connection(s) cleanly.
    """
    conn_map = getattr(_local, "conn_map", None) or {}
    if db_path is not None:
        norm_key = os.path.normcase(os.path.abspath(os.fspath(db_path)))
        conn = conn_map.pop(norm_key, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return

    for conn in list(conn_map.values()):
        try:
            conn.close()
        except Exception:
            pass
    conn_map.clear()
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None


def _ensure_column_migrations(conn: sqlite3.Connection) -> None:
    """Idempotently add any new columns to pre-existing SQLite tables before creating views."""
    time_entry_cols = [
        ("matter_name", "TEXT DEFAULT ''"),
        ("client_name", "TEXT DEFAULT ''"),
        ("raw_seconds", "INTEGER NOT NULL DEFAULT 0"),
        ("entry_status", "TEXT NOT NULL DEFAULT 'SAVED'"),
        ("started_at_utc", "TEXT"),
        ("last_heartbeat_utc", "TEXT"),
        ("legacy_dockets_sync_status", "TEXT NOT NULL DEFAULT 'PENDING_SYNC'"),
        ("legacy_dockets_synced_at", "TEXT"),
        ("legacy_dockets_row_signature", "TEXT"),
    ]
    table_additions = {
        "Client": [
            ("legal_name", "TEXT DEFAULT ''"),
            ("display_name", "TEXT DEFAULT ''"),
            ("entity_type", "TEXT DEFAULT 'Corporation'"),
            ("primary_contact", "TEXT DEFAULT ''"),
            ("address", "TEXT DEFAULT ''"),
            ("email", "TEXT DEFAULT ''"),
            ("phone", "TEXT DEFAULT ''"),
            ("default_billing_rate", "REAL DEFAULT 0.0"),
            ("default_billing_rate_cents", "INTEGER DEFAULT 0"),
            ("hst_exempt", "INTEGER DEFAULT 0"),
            ("tax_exemption_reason", "TEXT DEFAULT ''"),
            ("active", "INTEGER DEFAULT 1"),
            ("opening_date", "TEXT DEFAULT ''"),
            ("kyc_status", "TEXT DEFAULT 'Pending'"),
            ("kyc_verified_date", "TEXT DEFAULT ''"),
            ("kyc_method", "TEXT DEFAULT ''"),
            ("kyc_notes", "TEXT DEFAULT ''"),
            ("referred_by", "TEXT DEFAULT ''"),
            ("notes", "TEXT DEFAULT ''"),
        ],
        "ClientProfile": [
            ("display_name", "TEXT DEFAULT ''"),
            ("legal_name", "TEXT DEFAULT ''"),
            ("first_name", "TEXT DEFAULT ''"),
            ("middle_name", "TEXT DEFAULT ''"),
            ("last_name", "TEXT DEFAULT ''"),
            ("entity_type", "TEXT DEFAULT 'Corporation'"),
            ("principal_name", "TEXT DEFAULT ''"),
            ("principal_position", "TEXT DEFAULT ''"),
            ("primary_email", "TEXT DEFAULT ''"),
            ("primary_phone", "TEXT DEFAULT ''"),
            ("secondary_contact_name", "TEXT DEFAULT ''"),
            ("secondary_contact_position", "TEXT DEFAULT ''"),
            ("secondary_contact_email", "TEXT DEFAULT ''"),
            ("secondary_contact_phone", "TEXT DEFAULT ''"),
            ("address_line1", "TEXT DEFAULT ''"),
            ("address_line2", "TEXT DEFAULT ''"),
            ("city", "TEXT DEFAULT ''"),
            ("state_province", "TEXT DEFAULT ''"),
            ("postal_code", "TEXT DEFAULT ''"),
            ("country", "TEXT DEFAULT ''"),
            ("full_address", "TEXT DEFAULT ''"),
            ("billing_address", "TEXT DEFAULT ''"),
            ("parent_client_id", "TEXT DEFAULT ''"),
            ("parent_client_name", "TEXT DEFAULT ''"),
            ("website", "TEXT DEFAULT ''"),
            ("tax_number", "TEXT DEFAULT ''"),
            ("industry", "TEXT DEFAULT ''"),
            ("billing_email", "TEXT DEFAULT ''"),
            ("default_billing_rate", "REAL DEFAULT 0.0"),
            ("default_billing_rate_cents", "INTEGER DEFAULT 0"),
            ("hst_exempt", "INTEGER DEFAULT 0"),
            ("tax_exemption_reason", "TEXT DEFAULT ''"),
            ("kyc_status", "TEXT DEFAULT 'Pending'"),
            ("kyc_verified_date", "TEXT DEFAULT ''"),
            ("kyc_method", "TEXT DEFAULT ''"),
            ("kyc_notes", "TEXT DEFAULT ''"),
            ("onboarding_status", "TEXT DEFAULT 'Prospect'"),
            ("retainer_required", "INTEGER DEFAULT 0"),
            ("retainer_amount", "REAL DEFAULT 0.0"),
            ("engagement_start_date", "TEXT DEFAULT ''"),
            ("opening_date", "TEXT DEFAULT ''"),
            ("date_client_added", "TEXT DEFAULT ''"),
            ("birthday", "TEXT DEFAULT ''"),
            ("referral_from", "TEXT DEFAULT ''"),
            ("referred_by", "TEXT DEFAULT ''"),
            ("conflict_notes", "TEXT DEFAULT ''"),
            ("notes", "TEXT DEFAULT ''"),
            ("payment_terms", "TEXT DEFAULT ''"),
            ("created_at", "TEXT DEFAULT ''"),
            ("updated_at", "TEXT DEFAULT ''"),
        ],
        "Matter": [
            ("matter_number", "TEXT DEFAULT ''"),
            ("matter_name", "TEXT DEFAULT ''"),
            ("display_name", "TEXT DEFAULT ''"),
            ("client_name", "TEXT DEFAULT ''"),
            ("parent_id", "TEXT DEFAULT ''"),
            ("parent_name", "TEXT DEFAULT ''"),
            ("matter_type", "TEXT DEFAULT 'General'"),
            ("practice_area", "TEXT DEFAULT ''"),
            ("responsible_lawyer", "TEXT DEFAULT ''"),
            ("billing_arrangement", "TEXT DEFAULT 'Hourly'"),
            ("billing_contact", "TEXT DEFAULT ''"),
            ("billing_email", "TEXT DEFAULT ''"),
            ("default_rate", "REAL DEFAULT 0.0"),
            ("default_rate_cents", "INTEGER DEFAULT 0"),
            ("hourly_rate", "REAL DEFAULT 0.0"),
            ("hourly_rate_cents", "INTEGER DEFAULT 0"),
            ("fee_estimate", "REAL DEFAULT 0.0"),
            ("fee_estimate_cents", "INTEGER DEFAULT 0"),
            ("default_share_pct", "REAL DEFAULT 100.0"),
            ("rate_history", "TEXT DEFAULT '[]'"),
            ("date_of_engagement", "TEXT DEFAULT ''"),
            ("date_opened", "TEXT DEFAULT ''"),
            ("target_completion_date", "TEXT DEFAULT ''"),
            ("date_closed", "TEXT DEFAULT ''"),
            ("court_file_number", "TEXT DEFAULT ''"),
            ("opposing_party", "TEXT DEFAULT ''"),
            ("referral_from", "TEXT DEFAULT ''"),
            ("referred_by", "TEXT DEFAULT ''"),
            ("notes", "TEXT DEFAULT ''"),
            ("representation_mode", "TEXT DEFAULT 'Single Client'"),
            ("joint_no_confidentiality_confirmed", "INTEGER DEFAULT 0"),
            ("joint_instructions_require_all", "INTEGER DEFAULT 0"),
            ("joint_engagement_document", "TEXT DEFAULT ''"),
            ("default_biller_entity", "TEXT DEFAULT 'SOLE_PROP'"),
            ("kyc_completed", "INTEGER DEFAULT 0"),
        ],
        "TimeEntry": time_entry_cols,
        "time_entries": time_entry_cols,
    }
    for table_name, cols in table_additions.items():
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cur.fetchone():
            continue
        existing_cols = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for col_name, col_def in cols:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")


def init_schema(db_path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """
    Initializes the database schema if it doesn't exist and returns the connection.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError("schema.sql not found in the database module.")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    try:
        _ensure_column_migrations(conn)
        conn.executescript(schema_sql)
        _ensure_column_migrations(conn)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    return conn
