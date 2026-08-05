# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
import sqlite3
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import uuid
from src.python.database.connection import get_connection

def get_utc_now():
    return datetime.now(timezone.utc).isoformat()

class SqliteFinanceRepo:
    def list_transactions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM TransactionMaster ORDER BY date DESC, created_at DESC"
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        
        results = []
        for row in rows:
            results.append({
                "transactionId": row['transaction_id'],
                "date": row['date'],
                "account": row['account'],
                "amount": row['amount'],
                "type": row['type'],
                "description": row['description']
            })
        return results

    def save_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        txn_id = payload.get("transactionId")
        date = payload.get("date", get_utc_now()[:10])
        account = payload.get("account", "")
        amount = float(payload.get("amount", 0.0))
        txn_type = payload.get("type", "Debit")
        desc = payload.get("description", "")
        now = get_utc_now()

        if txn_id:
            conn.execute(
                "UPDATE TransactionMaster SET date=?, account=?, amount=?, type=?, description=?, updated_at=? WHERE transaction_id=?",
                (date, account, amount, txn_type, desc, now, txn_id)
            )
        else:
            txn_id = f"TXN-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO TransactionMaster (transaction_id, date, account, amount, type, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (txn_id, date, account, amount, txn_type, desc, now, now)
            )
        conn.commit()
        return {"ok": True, "transactionId": txn_id, "amount": amount}

class SqliteClientRepo:
    def list_client_directory(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
        SELECT c.client_id, c.name as client_name, c.status, 
               p.billing_address, p.tax_number, p.payment_terms
        FROM Client c
        LEFT JOIN ClientProfile p ON c.client_id = p.client_id
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        directory = []
        for row in rows:
            client_id = row['client_id']
            client_name = row['client_name']
            directory.append({
                "clientId": client_id,
                "clientName": client_name,
                "displayName": client_name,
                "legalName": client_name,
                "firstName": "",
                "middleName": "",
                "lastName": "",
                "entityType": "Corporate",
                "status": row['status'],
                "active": 1 if row['status'] == 'Active' else 0,
                "primaryEmail": "",
                "primaryPhone": "",
                "parentClientName": "",
                "onboardingStatus": "",
                "kycStatus": "",
                "updatedAt": "",
                "searchText": f"{client_id} {client_name}".lower()
            })
        return directory

    def list_parent_names(self) -> List[str]:
        return []

    def list_client_names(self) -> List[str]:
        conn = get_connection()
        cursor = conn.execute("SELECT name FROM Client ORDER BY name ASC")
        return [row['name'] for row in cursor.fetchall() if row['name']]

    def list_active_client_names(self) -> List[str]:
        conn = get_connection()
        cursor = conn.execute("SELECT name FROM Client WHERE status = 'Active' ORDER BY name ASC")
        return [row['name'] for row in cursor.fetchall() if row['name']]

    def get_all_clients(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Client")
        return [dict(row) for row in cursor.fetchall()]
        
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Client WHERE client_id = ?", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
        
    def add_client(self, client_id: str, name: str, legacy_id: Optional[str] = None):
        conn = get_connection()
        now = get_utc_now()
        conn.execute(
            "INSERT INTO Client (client_id, name, created_at, updated_at, legacy_id) VALUES (?, ?, ?, ?, ?)",
            (client_id, name, now, now, legacy_id)
        )
        conn.commit()

class SqliteMatterRepo:
    def list_matter_directory(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
        SELECT m.matter_id, m.description, m.status, c.name as client_name, c.client_id
        FROM Matter m
        JOIN Client c ON m.client_id = c.client_id
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        directory = []
        for row in rows:
            directory.append({
                "matterId": row['matter_id'],
                "clientId": row['client_id'],
                "clientName": row['client_name'],
                "description": row['description'],
                "status": row['status'],
                "active": 1 if row['status'] == 'Open' else 0,
                "searchText": f"{row['matter_id']} {row['client_name']} {row['description']}".lower()
            })
        return directory

    def get_matters_for_client(self, client_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Matter WHERE client_id = ?", (client_id,))
        return [dict(row) for row in cursor.fetchall()]
        
    def add_matter(self, matter_id: str, client_id: str, description: str, legacy_id: Optional[str] = None):
        conn = get_connection()
        now = get_utc_now()
        conn.execute(
            "INSERT INTO Matter (matter_id, client_id, description, created_at, updated_at, legacy_id) VALUES (?, ?, ?, ?, ?, ?)",
            (matter_id, client_id, description, now, now, legacy_id)
        )
        conn.commit()

class SqliteTimeRepo:
    def list_time_entries(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM TimeEntry ORDER BY date DESC, created_at DESC"
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        
        results = []
        for row in rows:
            results.append({
                "entryId": row['time_id'],
                "matterId": row['matter_id'],
                "date": row['date'],
                "hours": row['hours'],
                "rate": row['rate'],
                "amount": row['amount'],
                "description": row['description'],
                "status": "Billed" if row['is_billed'] else "Draft",
            })
        return results

    def save_time_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        entry_id = payload.get("entryId")
        matter_id = payload.get("matterId")
        date = payload.get("date", get_utc_now()[:10])
        hours = float(payload.get("hours", 0.0))
        rate = float(payload.get("rate", 0.0))
        desc = payload.get("description", "")
        amount = hours * rate
        now = get_utc_now()

        if entry_id:
            conn.execute(
                "UPDATE TimeEntry SET matter_id=?, date=?, hours=?, rate=?, amount=?, description=?, updated_at=? WHERE time_id=?",
                (matter_id, date, hours, rate, amount, desc, now, entry_id)
            )
        else:
            entry_id = f"TIM-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO TimeEntry (time_id, matter_id, date, hours, rate, amount, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry_id, matter_id, date, hours, rate, amount, desc, now, now)
            )
        conn.commit()
        return {"ok": True, "entryId": entry_id, "amount": amount}

    def delete_time_entry(self, entry_id: str) -> bool:
        conn = get_connection()
        cursor = conn.execute("DELETE FROM TimeEntry WHERE time_id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_unbilled_time(self, matter_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM TimeEntry WHERE matter_id = ? AND is_billed = 0", (matter_id,))
        return [dict(row) for row in cursor.fetchall()]
