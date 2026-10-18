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

def _ensure_column_migrations(conn: sqlite3.Connection) -> None:
    """Idempotently add any new columns to pre-existing SQLite tables before creating views."""
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


def init_schema():
    """
    Initializes the database schema if it doesn't exist.
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    if not os.path.exists(schema_path):
        raise FileNotFoundError("schema.sql not found in the database module.")
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        
    conn = get_connection()
    try:
        _ensure_column_migrations(conn)
        conn.executescript(schema_sql)
        _ensure_column_migrations(conn)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
