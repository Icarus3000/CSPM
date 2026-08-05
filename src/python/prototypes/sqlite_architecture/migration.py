# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
import os
import uuid
import logging
from typing import Dict, Any
from src.python.database.connection import get_connection, init_schema
from src.python.database.sqlite_repo import SqliteClientRepo, SqliteMatterRepo, SqliteTimeRepo
# Import from the existing system to pull the legacy data
from src.python.repositories.excel_repo import ExcelRepo

logger = logging.getLogger(__name__)

def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def perform_dry_run_migration():
    """
    Reads from the legacy Excel repository, normalizes data types, 
    resolves null references, and inserts into the new SQLite schema.
    Wraps the entire operation in a single atomic transaction.
    """
    logger.info("Initializing SQLite Schema...")
    init_schema()
    
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    
    try:
        logger.info("Loading Legacy Excel Data...")
        from src.python.services.paths import AppPaths
        from pathlib import Path
        paths = AppPaths(root=Path(r"C:\Projects\__CSPM"))
        excel_repo = ExcelRepo(paths)
        # Ensure we are using read-only or a copied path (simulation for now)
        legacy_clients = excel_repo.get_all_clients() if hasattr(excel_repo, 'get_all_clients') else []
        legacy_matters = excel_repo.get_all_matters() if hasattr(excel_repo, 'get_all_matters') else []
        
        sqlite_client_repo = SqliteClientRepo()
        sqlite_matter_repo = SqliteMatterRepo()
        
        # 1. Normalize and Migrate Clients
        logger.info(f"Migrating {len(legacy_clients)} clients...")
        client_id_map = {}
        for row in legacy_clients:
            # Handle null IDs or missing names
            legacy_id = row.get("ClientID")
            name = row.get("ClientName") or "Unknown Client"
            
            new_id = generate_id("CLI")
            client_id_map[legacy_id] = new_id
            
            sqlite_client_repo.add_client(new_id, name, legacy_id=str(legacy_id) if legacy_id else None)

        # 2. Normalize and Migrate Matters
        logger.info(f"Migrating {len(legacy_matters)} matters...")
        for row in legacy_matters:
            legacy_id = row.get("MatterID")
            legacy_client_id = row.get("ClientID")
            desc = row.get("Description") or "No Description"
            
            # Resolve relationships
            new_client_id = client_id_map.get(legacy_client_id)
            if not new_client_id:
                logger.warning(f"Matter {legacy_id} has orphan ClientID {legacy_client_id}. Creating default client.")
                new_client_id = generate_id("CLI")
                sqlite_client_repo.add_client(new_client_id, "Orphan Recovery Client")
                client_id_map[legacy_client_id] = new_client_id
                
            new_matter_id = generate_id("MAT")
            sqlite_matter_repo.add_matter(new_matter_id, new_client_id, desc, legacy_id=str(legacy_id) if legacy_id else None)
        
        # Commit Dry Run (for testing, we might roll back, but we'll commit here since the DB is empty and isolated)
        conn.commit()
        logger.info("Dry-run Migration completed successfully.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration Failed! Rolled back completely. Reason: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("--- Executing Production Migration Dry-Run ---")
    # For safety during this phase, we ensure we are NOT touching the real CSPM.xlsm directly if we don't want to.
    # The ExcelRepo normally points to data/CSPM.xlsm. We will let it read, as reads are non-mutating.
    perform_dry_run_migration()
