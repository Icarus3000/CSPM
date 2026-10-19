# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

try:
    from .connection import get_connection
except ImportError:
    from src.python.prototypes.sqlite_architecture.connection import get_connection


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_decimal(val: Any, default: str = "0.00") -> Decimal:
    if val is None or val == "":
        return Decimal(default)
    if isinstance(val, Decimal):
        return val
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        if not cleaned:
            return Decimal(default)
        return Decimal(cleaned)
    except Exception:
        return Decimal(default)


def to_cents(val: Any) -> int:
    d = to_decimal(val, "0.00").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)


def from_cents(cents: Any) -> Decimal:
    if cents is None or cents == "":
        return Decimal("0.00")
    return (Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_iso_date(val: Any, default: str = "") -> str:
    if val is None or val == "":
        return default
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s:
        return default
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10]


def infer_biller_from_date(date_val: Any, cutoff: str = "2026-11-01") -> str:
    iso = normalize_iso_date(date_val)
    if iso and iso >= cutoff:
        return "PC"
    return "SOLE_PROP"


class SqliteFinanceRepo:
    def list_transactions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM TransactionMaster ORDER BY date DESC, created_at DESC"
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]

        results = []
        for row in rows:
            biller = row.get("biller_entity") or infer_biller_from_date(row.get("date"))
            item = {
                "TransactionID": row["transaction_id"],
                "TxnDate": row["date"],
                "Class": row.get("class") or "Business",
                "BusinessUnit": row.get("business_unit") or "Cory Legal",
                "Type": row["type"],
                "FromAccount": row["account"],
                "ToAccount": row.get("to_account") or "",
                "Payee": row.get("payee") or "",
                "Parent": row.get("parent") or "",
                "Client": row.get("client") or "",
                "Matter": row.get("matter") or "",
                "CategoryCode": row.get("category_code") or "",
                "CategoryName": row.get("category_name") or "",
                "Member": row.get("member") or "Cory",
                "Amount": float(row.get("amount") or 0.0),
                "TaxAmount": float(row.get("tax_amount") or 0.0),
                "TaxFlag": row.get("tax_flag") or "None",
                "HSTExempt": int(row.get("hst_exempt") or 0),
                "GeneralOfficeExpense": int(row.get("general_office_expense") or 0),
                "Shadow": int(row.get("shadow") or 0),
                "InvoiceRef": row.get("invoice_ref") or "",
                "BillClaimPct": float(row.get("bill_claim_pct") or 0.0),
                "TotalClaimAmount": float(row.get("total_claim_amount") or 0.0),
                "ExpenseDetails": row.get("description") or "",
                "Notes": row.get("notes") or "",
                "Status": row.get("status") or "Posted",
                "Currency": row.get("currency") or "CAD",
                "BillerEntity": biller,
                "CreatedAt": row.get("created_at") or "",
                "UpdatedAt": row.get("updated_at") or "",
                # Legacy camelCase keys
                "transactionId": row["transaction_id"],
                "date": row["date"],
                "account": row["account"],
                "amount": float(row.get("amount") or 0.0),
                "type": row["type"],
                "description": row.get("description") or "",
                "billerEntity": biller,
            }
            if filters:
                biller_filter = filters.get("biller_entity") or filters.get("BillerEntity")
                if biller_filter and item["BillerEntity"] != biller_filter:
                    continue
            results.append(item)
        return results

    def save_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        txn_id = payload.get("TransactionID") or payload.get("transactionId")
        date = normalize_iso_date(payload.get("TxnDate") or payload.get("date"), get_utc_now()[:10])
        account = payload.get("FromAccount") or payload.get("account") or ""
        to_account = payload.get("ToAccount") or payload.get("toAccount") or ""
        payee = payload.get("Payee") or payload.get("payee") or ""
        txn_class = payload.get("Class") or payload.get("class") or "Business"
        business_unit = payload.get("BusinessUnit") or payload.get("businessUnit") or "Cory Legal"
        category_code = payload.get("CategoryCode") or payload.get("categoryCode") or ""
        category_name = payload.get("CategoryName") or payload.get("categoryName") or ""
        amount_dec = to_decimal(payload.get("Amount") if "Amount" in payload else payload.get("amount", 0.0))
        tax_dec = to_decimal(payload.get("TaxAmount") if "TaxAmount" in payload else payload.get("taxAmount", 0.0))
        amount = float(amount_dec)
        tax_amount = float(tax_dec)
        txn_type = payload.get("Type") or payload.get("type") or "Expense"
        desc = payload.get("ExpenseDetails") or payload.get("description") or ""
        notes = payload.get("Notes") or payload.get("notes") or ""
        biller_entity = (
            payload.get("BillerEntity")
            or payload.get("billerEntity")
            or infer_biller_from_date(date)
        )
        now = get_utc_now()

        if txn_id:
            conn.execute(
                """UPDATE TransactionMaster
                   SET date=?, class=?, business_unit=?, type=?, account=?, to_account=?,
                       payee=?, category_code=?, category_name=?, amount=?, amount_cents=?,
                       tax_amount=?, tax_amount_cents=?, description=?, notes=?,
                       biller_entity=?, updated_at=?
                   WHERE transaction_id=?""",
                (
                    date, txn_class, business_unit, txn_type, account, to_account,
                    payee, category_code, category_name, amount, to_cents(amount_dec),
                    tax_amount, to_cents(tax_dec), desc, notes,
                    biller_entity, now, txn_id
                ),
            )
        else:
            txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
            conn.execute(
                """INSERT INTO TransactionMaster (
                       transaction_id, date, class, business_unit, type, account, to_account,
                       payee, category_code, category_name, amount, amount_cents,
                       tax_amount, tax_amount_cents, description, notes,
                       biller_entity, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    txn_id, date, txn_class, business_unit, txn_type, account, to_account,
                    payee, category_code, category_name, amount, to_cents(amount_dec),
                    tax_amount, to_cents(tax_dec), desc, notes,
                    biller_entity, now, now
                ),
            )
        conn.commit()
        return {"ok": True, "transactionId": txn_id, "TransactionID": txn_id, "amount": amount, "BillerEntity": biller_entity}


class SqliteClientRepo:
    def list_client_directory(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
        SELECT c.client_id, c.name as client_name, c.status,
               c.legal_name as c_legal_name, c.display_name as c_display_name,
               c.entity_type as c_entity_type, c.address as c_address,
               c.primary_contact as c_primary_contact, c.email as c_email, c.phone as c_phone,
               c.default_billing_rate as c_rate, c.hst_exempt as c_hst_exempt,
               c.tax_exemption_reason as c_tax_reason, c.opening_date as c_opening_date,
               c.kyc_status as c_kyc_status, c.kyc_verified_date as c_kyc_verified_date,
               c.kyc_method as c_kyc_method, c.kyc_notes as c_kyc_notes,
               c.referred_by as c_referred_by, c.updated_at as c_updated_at,
               p.display_name, p.legal_name, p.first_name, p.middle_name, p.last_name,
               p.entity_type as p_entity_type, p.billing_address, p.full_address,
               p.tax_number, p.payment_terms,
               p.principal_name, p.principal_position, p.primary_email, p.primary_phone,
               p.address_line1, p.address_line2, p.city, p.state_province, p.postal_code, p.country,
               p.parent_client_id, p.parent_client_name,
               p.referral_from, p.referred_by as p_referred_by,
               p.default_billing_rate as p_rate, p.hst_exempt as p_hst_exempt,
               p.tax_exemption_reason as p_tax_reason, p.opening_date as p_opening_date,
               p.onboarding_status, p.kyc_status as p_kyc_status,
               p.kyc_verified_date as p_kyc_verified_date, p.kyc_method as p_kyc_method,
               p.kyc_notes as p_kyc_notes, p.updated_at as p_updated_at
        FROM Client c
        LEFT JOIN ClientProfile p ON c.client_id = p.client_id
        ORDER BY c.name COLLATE NOCASE ASC
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        directory = []
        for row in rows:
            client_id = row["client_id"]
            client_name = row["client_name"] or ""
            display_name = row["display_name"] or row["c_display_name"] or client_name
            legal_name = row["legal_name"] or row["c_legal_name"] or display_name or client_name
            entity_type = row["p_entity_type"] or row["c_entity_type"] or "Corporate"
            status = row["status"] or "Active"
            active = 1 if status.lower() == "active" else 0
            primary_contact = row["c_primary_contact"] or row["principal_name"] or ""
            primary_email = row["primary_email"] or row["c_email"] or ""
            primary_phone = row["primary_phone"] or row["c_phone"] or ""
            address = row["full_address"] or row["billing_address"] or row["c_address"] or ""
            default_rate = float(row["p_rate"] if row["p_rate"] is not None and float(row["p_rate"] or 0) > 0 else (row["c_rate"] or 0.0))
            hst_exempt = int(row["p_hst_exempt"] if row["p_hst_exempt"] is not None else (row["c_hst_exempt"] or 0))
            tax_reason = row["p_tax_reason"] or row["c_tax_reason"] or ""
            opening_date = row["p_opening_date"] or row["c_opening_date"] or ""
            kyc_status = row["p_kyc_status"] or row["c_kyc_status"] or ""
            kyc_verified_date = row["p_kyc_verified_date"] or row["c_kyc_verified_date"] or ""
            kyc_method = row["p_kyc_method"] or row["c_kyc_method"] or ""
            kyc_notes = row["p_kyc_notes"] or row["c_kyc_notes"] or ""
            referred_by = row["p_referred_by"] or row["c_referred_by"] or row["referral_from"] or ""
            referral_from = row["referral_from"] or referred_by
            updated_at = row["p_updated_at"] or row["c_updated_at"] or ""
            search_chunks = [
                client_id, client_name, display_name, legal_name, entity_type,
                primary_contact, primary_email, primary_phone, address,
                referred_by, kyc_status, kyc_method
            ]
            directory.append({
                "clientId": client_id,
                "clientName": client_name,
                "displayName": display_name,
                "legalName": legal_name,
                "firstName": row["first_name"] or "",
                "middleName": row["middle_name"] or "",
                "lastName": row["last_name"] or "",
                "entityType": entity_type,
                "status": status,
                "active": active,
                "primaryContact": primary_contact,
                "primaryContactName": primary_contact,
                "primaryEmail": primary_email,
                "primaryPhone": primary_phone,
                "address": address,
                "fullAddress": address,
                "parentId": row["parent_client_id"] or "",
                "parentClientName": row["parent_client_name"] or "",
                "defaultBillingRate": default_rate,
                "hstExempt": hst_exempt,
                "taxExemptionReason": tax_reason,
                "openingDate": opening_date,
                "onboardingStatus": row["onboarding_status"] or "",
                "kycStatus": kyc_status,
                "kycVerifiedDate": kyc_verified_date,
                "kycMethod": kyc_method,
                "kycNotes": kyc_notes,
                "referredBy": referred_by,
                "referralFrom": referral_from,
                "updatedAt": updated_at,
                "searchText": " ".join(c for c in search_chunks if c).lower(),
            })
        return directory

    def get_client_profile(self, client_key: str) -> Dict[str, Any]:
        lookup = str(client_key or "").strip().lower()
        if not lookup:
            return {"ok": False, "message": "Client key is required.", "client": {}}
        for item in self.list_client_directory():
            if (
                str(item.get("clientId") or "").lower() == lookup
                or str(item.get("clientName") or "").lower() == lookup
                or str(item.get("displayName") or "").lower() == lookup
                or str(item.get("legalName") or "").lower() == lookup
            ):
                return {"ok": True, "message": "Client loaded.", "client": item}
        return {"ok": False, "message": f"Client not found: {client_key}", "client": {}}

    def list_parent_names(self) -> List[str]:
        return []

    def list_client_names(self) -> List[str]:
        conn = get_connection()
        cursor = conn.execute("SELECT name FROM Client ORDER BY name ASC")
        return [row["name"] for row in cursor.fetchall() if row["name"]]

    def list_active_client_names(self) -> List[str]:
        conn = get_connection()
        cursor = conn.execute("SELECT name FROM Client WHERE status = 'Active' ORDER BY name ASC")
        return [row["name"] for row in cursor.fetchall() if row["name"]]

    def get_all_clients(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Client")
        return [dict(row) for row in cursor.fetchall()]

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Client WHERE client_id = ?", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_client(self, client_id: str, name: str, legacy_id: Optional[str] = None, status: str = "Active"):
        conn = get_connection()
        now = get_utc_now()
        conn.execute(
            "INSERT OR REPLACE INTO Client (client_id, name, status, created_at, updated_at, legacy_id) VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, name, status or "Active", now, now, legacy_id),
        )
        conn.commit()


class SqliteMatterRepo:
    def list_matter_parties(self, matter_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        if matter_id:
            cursor = conn.execute(
                "SELECT * FROM matter_parties WHERE matter_id = ? ORDER BY sort_order ASC, party_id ASC",
                (str(matter_id).strip(),),
            )
        else:
            cursor = conn.execute("SELECT * FROM matter_parties ORDER BY matter_id ASC, sort_order ASC, party_id ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            pid = r["party_id"]
            mid = r["matter_id"]
            cid = r["client_id"] or ""
            cname = r["client_name"] or ""
            role = r["party_role"] or ""
            is_anchor = int(r["is_file_anchor"] or 0)
            is_billing = int(r["is_billing_recipient"] or 0)
            is_client_party = 1 if (cid or is_anchor) else 0
            results.append({
                "matterPartyId": pid,
                "partyId": pid,
                "PartyID": pid,
                "MatterPartyID": pid,
                "matterId": mid,
                "MatterID": mid,
                "clientId": cid,
                "partyClientId": cid,
                "PartyClientID": cid,
                "ClientID": cid,
                "clientName": cname,
                "partyName": cname,
                "PartyName": cname,
                "ClientName": cname,
                "role": role,
                "partyRole": role,
                "PartyRole": role,
                "Role": role,
                "isFileAnchor": is_anchor,
                "isClientParty": is_client_party,
                "IsClientParty": is_client_party,
                "isBillingRecipient": is_billing,
                "isBillingParty": is_billing,
                "IsBillingParty": is_billing,
                "sortOrder": int(r["sort_order"] or 0),
                "feeSharePct": float(r["fee_share_pct"] or 0.0),
                "notes": r["notes"] or "",
                "Notes": r["notes"] or "",
                "addedAt": r["added_at"] or "",
            })
        return results

    def list_matter_directory(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
        SELECT m.*, c.name as c_client_name
        FROM Matter m
        LEFT JOIN Client c ON m.client_id = c.client_id
        ORDER BY COALESCE(m.display_name, m.matter_name, m.description) COLLATE NOCASE ASC
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        directory = []
        for row in rows:
            mid = row["matter_id"]
            matter_num = row["matter_number"] or ""
            client_id = row["client_id"] or ""
            client_name = row["client_name"] or row["c_client_name"] or ""
            matter_name = row["matter_name"] or row["description"] or ""
            display_name = row["display_name"] or matter_name
            desc = row["description"] or display_name
            status = row["status"] or "Open"
            active = 1 if status.lower() in ("open", "active") else 0
            referred_by = row["referred_by"] or row["referral_from"] or ""
            referral_from = row["referral_from"] or referred_by
            default_biller = row["default_biller_entity"] or row["default_biller"] or "SOLE_PROP"
            rep_mode = row["representation_mode"] or "Single Client"
            is_joint = 1 if rep_mode.lower() == "joint retainer" else 0
            kyc_completed = int(row["kyc_completed"] or 0)
            open_date = row["date_opened"] or row["date_of_engagement"] or ""
            joint_doc = row["joint_engagement_document"] or ""
            search_chunks = [
                mid, matter_num, client_id, client_name, matter_name, display_name,
                desc, row["practice_area"] or "", row["matter_type"] or "",
                referred_by, joint_doc
            ]
            directory.append({
                "matterId": mid,
                "matterNumber": matter_num,
                "matterName": matter_name,
                "displayName": display_name,
                "description": desc,
                "clientId": client_id,
                "clientName": client_name,
                "parentId": row["parent_id"] or "",
                "parentName": row["parent_name"] or "",
                "practiceArea": row["practice_area"] or "",
                "matterType": row["matter_type"] or "",
                "status": status,
                "active": active,
                "openDate": open_date,
                "dateOpened": open_date,
                "dateOfEngagement": row["date_of_engagement"] or open_date,
                "closeDate": row["date_closed"] or "",
                "dateClosed": row["date_closed"] or "",
                "targetCompletionDate": row["target_completion_date"] or "",
                "billingArrangement": row["billing_arrangement"] or "",
                "defaultRate": float(row["default_rate"] or 0.0),
                "hourlyRate": float(row["hourly_rate"] or row["default_rate"] or 0.0),
                "feeEstimate": float(row["fee_estimate"] or 0.0),
                "responsibleLawyer": row["responsible_lawyer"] or "",
                "originatingLawyer": row["responsible_lawyer"] or "",
                "referredBy": referred_by,
                "referralFrom": referral_from,
                "representationMode": rep_mode,
                "isJointRetainer": is_joint,
                "jointEngagementStatus": "Signed" if joint_doc else "",
                "jointEngagementDocument": joint_doc,
                "conflictCheckStatus": "Cleared" if is_joint else "",
                "conflictCheckDate": open_date if is_joint else "",
                "kycCompleted": kyc_completed,
                "kycStatus": "Completed" if kyc_completed else "",
                "kycVerifiedDate": open_date if kyc_completed else "",
                "defaultBiller": default_biller,
                "defaultBillerEntity": default_biller,
                "notes": row["notes"] or "",
                "updatedAt": row["updated_at"] or "",
                "searchText": " ".join(c for c in search_chunks if c).lower(),
            })
        return directory

    def get_matter_profile(self, matter_key: str) -> Dict[str, Any]:
        lookup = str(matter_key or "").strip().lower()
        if not lookup:
            return {"ok": False, "message": "Matter key is required.", "matter": {}}
        for item in self.list_matter_directory():
            if (
                str(item.get("matterId") or "").lower() == lookup
                or str(item.get("matterNumber") or "").lower() == lookup
                or str(item.get("matterName") or "").lower() == lookup
                or str(item.get("displayName") or "").lower() == lookup
            ):
                parties = self.list_matter_parties(item["matterId"])
                payload = dict(item)
                payload["parties"] = parties
                return {"ok": True, "message": "Matter loaded.", "matter": payload}
        return {"ok": False, "message": f"Matter not found: {matter_key}", "matter": {}}

    def get_matters_for_client(self, client_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM Matter WHERE client_id = ?", (client_id,))
        return [dict(row) for row in cursor.fetchall()]

    def add_matter(
        self,
        matter_id: str,
        client_id: str,
        description: str,
        legacy_id: Optional[str] = None,
        status: str = "Open",
        default_biller: str = "PC",
    ):
        conn = get_connection()
        now = get_utc_now()
        conn.execute(
            """INSERT OR REPLACE INTO Matter
               (matter_id, client_id, description, status, default_biller, created_at, updated_at, legacy_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (matter_id, client_id, description, status or "Open", default_biller or "PC", now, now, legacy_id),
        )
        conn.commit()


class SqliteTimeRepo:
    def _conn(self) -> sqlite3.Connection:
        db_path = getattr(self, "_db_path", None)
        return get_connection(db_path)

    @staticmethod
    def _format_time_entry_row(row: Dict[str, Any]) -> Dict[str, Any]:
        biller = row.get("biller_entity") or infer_biller_from_date(row.get("date"))
        entry_id = str(row.get("entry_id") or row.get("time_id") or "")
        raw_secs = int(row.get("raw_seconds") or 0)
        hours_val = float(row.get("hours") or 0.0)
        if raw_secs <= 0 and hours_val > 0:
            raw_secs = int(round(hours_val * 3600))
        entry_status = str(row.get("entry_status") or "SAVED").strip().upper() or "SAVED"
        sync_status = str(row.get("legacy_dockets_sync_status") or "PENDING_SYNC").strip().upper() or "PENDING_SYNC"
        return {
            "EntryID": entry_id,
            "MatterID": row.get("matter_id") or "",
            "MatterName": row.get("matter_name") or "",
            "ClientID": row.get("client_id") or "",
            "ClientName": row.get("client_name") or "",
            "ParentID": row.get("parent_id") or "",
            "Date": row.get("date") or "",
            "Hours": hours_val,
            "RawSeconds": raw_secs,
            "ClientRate": float(row.get("rate") or 0.0),
            "SharePct": float(row.get("share_pct") or 100.0),
            "GrossToClient": float(row.get("amount") or 0.0),
            "AmountToYou": float(row.get("amount_to_you") or row.get("amount") or 0.0),
            "HST": float(row.get("hst") or 0.0),
            "TotalInclHST": float(row.get("total_incl_hst") or 0.0),
            "Description": row.get("description") or "",
            "Status": row.get("status") or ("Billed" if row.get("is_billed") else "Unbilled"),
            "EntryStatus": entry_status,
            "StartedAtUTC": row.get("started_at_utc"),
            "LastHeartbeatUTC": row.get("last_heartbeat_utc"),
            "LegacyDocketsSyncStatus": sync_status,
            "LegacyDocketsSyncedAt": row.get("legacy_dockets_synced_at"),
            "LegacyDocketsRowSignature": row.get("legacy_dockets_row_signature"),
            "InvoiceRef": row.get("billed_invoice_id") or "",
            "BillerEntity": biller,
            # Snake & camelCase aliases
            "entry_id": entry_id,
            "entryId": entry_id,
            "matter_id": row.get("matter_id") or "",
            "matterId": row.get("matter_id") or "",
            "matter_name": row.get("matter_name") or "",
            "matterName": row.get("matter_name") or "",
            "client_id": row.get("client_id") or "",
            "clientId": row.get("client_id") or "",
            "client_name": row.get("client_name") or "",
            "clientName": row.get("client_name") or "",
            "date": row.get("date") or "",
            "hours": hours_val,
            "raw_seconds": raw_secs,
            "rawSeconds": raw_secs,
            "rate": float(row.get("rate") or 0.0),
            "amount": float(row.get("amount") or 0.0),
            "description": row.get("description") or "",
            "status": row.get("status") or ("Billed" if row.get("is_billed") else "Draft"),
            "entry_status": entry_status,
            "entryStatus": entry_status,
            "started_at_utc": row.get("started_at_utc"),
            "startedAtUtc": row.get("started_at_utc"),
            "last_heartbeat_utc": row.get("last_heartbeat_utc"),
            "lastHeartbeatUtc": row.get("last_heartbeat_utc"),
            "legacy_dockets_sync_status": sync_status,
            "legacyDocketsSyncStatus": sync_status,
            "legacy_dockets_synced_at": row.get("legacy_dockets_synced_at"),
            "legacyDocketsSyncedAt": row.get("legacy_dockets_synced_at"),
            "legacy_dockets_row_signature": row.get("legacy_dockets_row_signature"),
            "legacyDocketsRowSignature": row.get("legacy_dockets_row_signature"),
            "billerEntity": biller,
        }

    def list_time_entries(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = self._conn()
        seen_ids: set[str] = set()
        results: List[Dict[str, Any]] = []

        for tbl_query in (
            "SELECT * FROM time_entries ORDER BY date DESC, updated_at DESC",
            "SELECT * FROM TimeEntry ORDER BY date DESC, created_at DESC",
        ):
            try:
                cursor = conn.execute(tbl_query)
                rows = [dict(r) for r in cursor.fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                eid = str(row.get("entry_id") or row.get("time_id") or "")
                if not eid or eid in seen_ids:
                    continue
                seen_ids.add(eid)
                item = self._format_time_entry_row(row)
                if filters:
                    biller_filter = filters.get("biller_entity") or filters.get("BillerEntity")
                    if biller_filter and item["BillerEntity"] != biller_filter:
                        continue
                    date_filter = filters.get("date") or filters.get("Date")
                    if date_filter and item["Date"] != normalize_iso_date(date_filter):
                        continue
                results.append(item)
        return results

    def get_time_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        target_id = str(entry_id or "").strip()
        if not target_id:
            return None
        conn = self._conn()
        for sql in (
            "SELECT * FROM time_entries WHERE entry_id = ?",
            "SELECT * FROM TimeEntry WHERE time_id = ?",
        ):
            try:
                row = conn.execute(sql, (target_id,)).fetchone()
                if row is not None:
                    return self._format_time_entry_row(dict(row))
            except sqlite3.Error:
                continue
        return None

    def upsert_live_docket_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Atomic SQLite UPSERT into time_entries for live timer heartbeats and draft edits."""
        import json as _json

        conn = self._conn()
        now = get_utc_now()
        entry_id = str(
            payload.get("entry_id")
            or payload.get("EntryID")
            or payload.get("entryId")
            or payload.get("time_id")
            or ""
        ).strip()
        if not entry_id:
            entry_id = f"TIM-{uuid.uuid4().hex[:8].upper()}"

        existing = self.get_time_entry_by_id(entry_id) or {}
        matter_id = str(
            payload.get("matter_id")
            if "matter_id" in payload
            else (payload.get("MatterID") or payload.get("matterId") or existing.get("MatterID") or "")
        ).strip()
        matter_name = str(
            payload.get("matter_name")
            if "matter_name" in payload
            else (payload.get("MatterName") or payload.get("matterName") or existing.get("MatterName") or "")
        ).strip()
        client_id = str(
            payload.get("client_id")
            if "client_id" in payload
            else (payload.get("ClientID") or payload.get("clientId") or existing.get("ClientID") or "")
        ).strip()
        client_name = str(
            payload.get("client_name")
            if "client_name" in payload
            else (payload.get("ClientName") or payload.get("clientName") or existing.get("ClientName") or "")
        ).strip()
        parent_id = str(
            payload.get("parent_id")
            if "parent_id" in payload
            else (payload.get("ParentID") or payload.get("parentId") or existing.get("ParentID") or "")
        ).strip()
        date_iso = normalize_iso_date(
            payload.get("date") or payload.get("Date") or existing.get("Date"),
            now[:10],
        )

        raw_seconds_val = payload.get(
            "raw_seconds",
            payload.get("RawSeconds", payload.get("rawSeconds", existing.get("RawSeconds", 0))),
        )
        try:
            raw_seconds = max(0, int(round(float(raw_seconds_val or 0))))
        except Exception:
            raw_seconds = 0

        if "hours" in payload or "Hours" in payload:
            try:
                hours = float(payload.get("hours") if "hours" in payload else payload.get("Hours", 0.0))
            except Exception:
                hours = round(raw_seconds / 3600.0, 2)
        else:
            hours = round(raw_seconds / 3600.0, 2)

        if raw_seconds <= 0 and hours > 0:
            raw_seconds = int(round(hours * 3600))

        rate = float(payload.get("rate") if "rate" in payload else payload.get("ClientRate", existing.get("ClientRate", 475.0)))
        share_pct = float(payload.get("share_pct", payload.get("SharePct", existing.get("SharePct", 100.0))))
        desc = str(
            payload.get("description")
            if "description" in payload
            else (payload.get("Description") if "Description" in payload else (existing.get("Description") or ""))
        )

        amount_dec = to_decimal(payload.get("GrossToClient") if "GrossToClient" in payload else hours * rate)
        amount_to_you_dec = to_decimal(
            payload.get("AmountToYou") if "AmountToYou" in payload else (amount_dec * to_decimal(share_pct) / Decimal(100))
        )
        hst_dec = to_decimal(payload.get("HST") if "HST" in payload else (amount_to_you_dec * Decimal("0.13")))
        total_incl_dec = to_decimal(payload.get("TotalInclHST") if "TotalInclHST" in payload else (amount_to_you_dec + hst_dec))

        entry_status = str(
            payload.get("entry_status")
            or payload.get("EntryStatus")
            or payload.get("entryStatus")
            or existing.get("EntryStatus")
            or "RUNNING"
        ).strip().upper()
        if entry_status not in ("RUNNING", "PAUSED", "SAVED"):
            entry_status = "SAVED"

        if "started_at_utc" in payload or "StartedAtUTC" in payload or "startedAtUtc" in payload:
            started_at_utc = (
                payload.get("started_at_utc")
                or payload.get("StartedAtUTC")
                or payload.get("startedAtUtc")
            )
        elif entry_status == "RUNNING":
            started_at_utc = existing.get("StartedAtUTC") or now
        else:
            started_at_utc = None

        last_heartbeat_utc = str(
            payload.get("last_heartbeat_utc")
            or payload.get("LastHeartbeatUTC")
            or payload.get("lastHeartbeatUtc")
            or now
        )

        default_sync_status = "PENDING_CRASH_RECOVERY" if entry_status in ("RUNNING", "PAUSED") else "PENDING_SYNC"
        legacy_sync_status = str(
            payload.get("legacy_dockets_sync_status")
            or payload.get("LegacyDocketsSyncStatus")
            or payload.get("legacyDocketsSyncStatus")
            or default_sync_status
        ).strip().upper()
        if legacy_sync_status not in ("PENDING_CRASH_RECOVERY", "PENDING_SYNC", "SYNCED", "SKIPPED"):
            legacy_sync_status = default_sync_status

        legacy_synced_at = (
            payload.get("legacy_dockets_synced_at")
            or payload.get("LegacyDocketsSyncedAt")
            or payload.get("legacyDocketsSyncedAt")
            or existing.get("LegacyDocketsSyncedAt")
        )

        sig_raw = (
            payload.get("legacy_dockets_row_signature")
            if "legacy_dockets_row_signature" in payload
            else (
                payload.get("LegacyDocketsRowSignature")
                if "LegacyDocketsRowSignature" in payload
                else existing.get("LegacyDocketsRowSignature")
            )
        )
        if isinstance(sig_raw, dict):
            legacy_row_signature = _json.dumps(sig_raw, sort_keys=True)
        elif sig_raw is not None:
            legacy_row_signature = str(sig_raw)
        else:
            legacy_row_signature = None

        status = str(payload.get("Status") or payload.get("status") or ("Draft" if entry_status != "SAVED" else "Unbilled"))
        invoice_ref = str(payload.get("InvoiceRef") or payload.get("billed_invoice_id") or existing.get("InvoiceRef") or "")
        is_billed = 1 if (invoice_ref or status.lower() in ("billed", "invoiced", "paid")) else 0
        biller_entity = str(
            payload.get("BillerEntity")
            or payload.get("billerEntity")
            or existing.get("BillerEntity")
            or infer_biller_from_date(date_iso)
        )
        created_at = str(existing.get("created_at") or now)

        conn.execute(
            """INSERT INTO time_entries (
                   entry_id, time_id, matter_id, matter_name, client_id, client_name, parent_id,
                   date, hours, raw_seconds, rate, rate_cents, share_pct,
                   amount, amount_cents, amount_to_you, amount_to_you_cents,
                   hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                   description, status, entry_status, started_at_utc, last_heartbeat_utc,
                   legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                   is_billed, billed_invoice_id, biller_entity, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(entry_id) DO UPDATE SET
                   time_id=excluded.time_id,
                   matter_id=excluded.matter_id,
                   matter_name=excluded.matter_name,
                   client_id=excluded.client_id,
                   client_name=excluded.client_name,
                   parent_id=excluded.parent_id,
                   date=excluded.date,
                   hours=excluded.hours,
                   raw_seconds=excluded.raw_seconds,
                   rate=excluded.rate,
                   rate_cents=excluded.rate_cents,
                   share_pct=excluded.share_pct,
                   amount=excluded.amount,
                   amount_cents=excluded.amount_cents,
                   amount_to_you=excluded.amount_to_you,
                   amount_to_you_cents=excluded.amount_to_you_cents,
                   hst=excluded.hst,
                   hst_cents=excluded.hst_cents,
                   total_incl_hst=excluded.total_incl_hst,
                   total_incl_hst_cents=excluded.total_incl_hst_cents,
                   description=excluded.description,
                   status=excluded.status,
                   entry_status=excluded.entry_status,
                   started_at_utc=excluded.started_at_utc,
                   last_heartbeat_utc=excluded.last_heartbeat_utc,
                   legacy_dockets_sync_status=excluded.legacy_dockets_sync_status,
                   legacy_dockets_synced_at=excluded.legacy_dockets_synced_at,
                   legacy_dockets_row_signature=excluded.legacy_dockets_row_signature,
                   is_billed=excluded.is_billed,
                   billed_invoice_id=excluded.billed_invoice_id,
                   biller_entity=excluded.biller_entity,
                   updated_at=excluded.updated_at
            """,
            (
                entry_id, entry_id, matter_id, matter_name, client_id, client_name, parent_id,
                date_iso, hours, raw_seconds, rate, to_cents(rate), share_pct,
                float(amount_dec), to_cents(amount_dec),
                float(amount_to_you_dec), to_cents(amount_to_you_dec),
                float(hst_dec), to_cents(hst_dec),
                float(total_incl_dec), to_cents(total_incl_dec),
                desc, status, entry_status, started_at_utc, last_heartbeat_utc,
                legacy_sync_status, legacy_synced_at, legacy_row_signature,
                is_billed, invoice_ref, biller_entity, created_at, now,
            ),
        )

        # Also mirror into TimeEntry if matter_id satisfies FK or FK check succeeds
        if matter_id:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO TimeEntry (
                           time_id, matter_id, matter_name, client_id, client_name, parent_id,
                           date, hours, raw_seconds, rate, rate_cents, share_pct,
                           amount, amount_cents, amount_to_you, amount_to_you_cents,
                           hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                           description, status, entry_status, started_at_utc, last_heartbeat_utc,
                           legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                           is_billed, billed_invoice_id, biller_entity, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry_id, matter_id, matter_name, client_id, client_name, parent_id,
                        date_iso, hours, raw_seconds, rate, to_cents(rate), share_pct,
                        float(amount_dec), to_cents(amount_dec),
                        float(amount_to_you_dec), to_cents(amount_to_you_dec),
                        float(hst_dec), to_cents(hst_dec),
                        float(total_incl_dec), to_cents(total_incl_dec),
                        desc, status, entry_status, started_at_utc, last_heartbeat_utc,
                        legacy_sync_status, legacy_synced_at, legacy_row_signature,
                        is_billed, invoice_ref, biller_entity, created_at, now,
                    ),
                )
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        return self.get_time_entry_by_id(entry_id) or {
            "ok": True,
            "entryId": entry_id,
            "EntryID": entry_id,
            "entry_status": entry_status,
            "raw_seconds": raw_seconds,
            "legacy_dockets_sync_status": legacy_sync_status,
        }

    def save_time_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(payload or {})
        if "entry_status" not in merged and "EntryStatus" not in merged and "entryStatus" not in merged:
            merged["entry_status"] = "SAVED"
        if (
            "legacy_dockets_sync_status" not in merged
            and "LegacyDocketsSyncStatus" not in merged
            and "legacyDocketsSyncStatus" not in merged
        ):
            merged["legacy_dockets_sync_status"] = "PENDING_SYNC"
        saved = self.upsert_live_docket_heartbeat(merged)
        return {
            "ok": True,
            "entryId": saved.get("EntryID"),
            "EntryID": saved.get("EntryID"),
            "amount": float(saved.get("GrossToClient") or 0.0),
            "BillerEntity": saved.get("BillerEntity"),
            **saved,
        }

    def mark_legacy_dockets_sync_status(
        self,
        entry_id: str,
        sync_status: str,
        *,
        synced_at: Optional[str] = None,
        row_signature: Optional[Any] = None,
        entry_status: Optional[str] = None,
        raw_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        import json as _json

        target_id = str(entry_id or "").strip()
        if not target_id:
            return {"ok": False, "message": "entry_id is required"}

        conn = self._conn()
        now = get_utc_now()
        norm_sync = str(sync_status or "PENDING_SYNC").strip().upper()
        if norm_sync == "SYNCED" and not synced_at:
            synced_at = now

        sig_str: Optional[str] = None
        if isinstance(row_signature, dict):
            sig_str = _json.dumps(row_signature, sort_keys=True)
        elif row_signature is not None:
            sig_str = str(row_signature)

        existing = self.get_time_entry_by_id(target_id)
        if existing is None:
            return {"ok": False, "message": f"Entry not found: {target_id}"}

        final_entry_status = str(entry_status or existing.get("EntryStatus") or "SAVED").strip().upper()
        final_raw_secs = int(raw_seconds if raw_seconds is not None else (existing.get("RawSeconds") or 0))
        final_hours = round(final_raw_secs / 3600.0, 2) if raw_seconds is not None else float(existing.get("Hours") or 0.0)
        final_sig = sig_str if sig_str is not None else existing.get("LegacyDocketsRowSignature")
        final_synced_at = synced_at if synced_at is not None else existing.get("LegacyDocketsSyncedAt")
        started_utc = None if final_entry_status != "RUNNING" else existing.get("StartedAtUTC")

        for tbl, pk in (("time_entries", "entry_id"), ("TimeEntry", "time_id")):
            try:
                conn.execute(
                    f"""UPDATE {tbl}
                        SET legacy_dockets_sync_status = ?,
                            legacy_dockets_synced_at = ?,
                            legacy_dockets_row_signature = ?,
                            entry_status = ?,
                            raw_seconds = ?,
                            hours = ?,
                            started_at_utc = ?,
                            last_heartbeat_utc = ?,
                            updated_at = ?
                        WHERE {pk} = ?""",
                    (
                        norm_sync,
                        final_synced_at,
                        final_sig,
                        final_entry_status,
                        final_raw_secs,
                        final_hours,
                        started_utc,
                        now,
                        now,
                        target_id,
                    ),
                )
            except sqlite3.Error:
                continue
        conn.commit()
        return {"ok": True, **(self.get_time_entry_by_id(target_id) or {})}

    def list_unsynced_or_crash_recovery_dockets(self) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            cursor = conn.execute(
                """SELECT * FROM time_entries
                   WHERE legacy_dockets_sync_status IN ('PENDING_SYNC', 'PENDING_CRASH_RECOVERY')
                      OR entry_status IN ('RUNNING', 'PAUSED')
                   ORDER BY date ASC, updated_at ASC"""
            )
            rows = [dict(r) for r in cursor.fetchall()]
        except sqlite3.Error:
            rows = []
        return [self._format_time_entry_row(r) for r in rows]

    def delete_time_entry(self, entry_id: str) -> bool:
        conn = self._conn()
        deleted = 0
        for tbl, pk in (("time_entries", "entry_id"), ("TimeEntry", "time_id")):
            try:
                cursor = conn.execute(f"DELETE FROM {tbl} WHERE {pk} = ?", (entry_id,))
                deleted += cursor.rowcount
            except sqlite3.Error:
                continue
        conn.commit()
        return deleted > 0

    def get_unbilled_time(self, matter_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            cursor = conn.execute("SELECT * FROM time_entries WHERE matter_id = ? AND is_billed = 0", (matter_id,))
            rows = [dict(row) for row in cursor.fetchall()]
            if rows:
                return rows
        except sqlite3.Error:
            pass
        cursor = conn.execute("SELECT * FROM TimeEntry WHERE matter_id = ? AND is_billed = 0", (matter_id,))
        return [dict(row) for row in cursor.fetchall()]


class SQLiteRepository(SqliteFinanceRepo, SqliteClientRepo, SqliteMatterRepo, SqliteTimeRepo):
    """Unified SQLite Repository with full parity to ExcelRepo for Multi-Biller, Shareholder Loan, CCA, HST, and Income Tax."""

    def __init__(self, db_path: Optional[Any] = None):
        self._db_path = db_path
        if db_path is not None:
            try:
                from .connection import init_schema
            except ImportError:
                from src.python.prototypes.sqlite_architecture.connection import init_schema
            init_schema(db_path)

    # ------------------------------------------------------------------
    # Billing Entities (tblBillingEntities / billing_entities)
    # ------------------------------------------------------------------
    def list_billing_entities(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM billing_entities ORDER BY biller_code ASC")
        rows = cursor.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            results.append({
                "BillerCode": r["biller_code"],
                "LegalName": r["legal_name"],
                "PracticeName": r["practice_name"],
                "OCN": r["ocn"] or "",
                "BIN": r["bin"] or "",
                "HSTNumber": r["hst_number"] or "",
                "EffectiveFrom": r["effective_from"] or "",
                "EffectiveTo": r["effective_to"] or "",
                "DefaultAddressLine": r["default_address_line"] or "",
                "AltAddressLine": r["alt_address_line"] or "",
                "Phone": r["phone"] or "",
                "Email": r["email"] or "",
                "PayableToName": r["payable_to_name"] or "",
                "ETransferEmail": r["etransfer_email"] or "",
                "BankAccountCode": r["bank_account_code"] or "",
                "InvoiceNumberSuffix": r["invoice_number_suffix"] or "",
                "FooterDisclosureText": r["footer_disclosure_text"] or "",
                "IsDefault": int(r["is_default"] or 0),
                "Active": int(r["active"] or 0),
                "billerCode": r["biller_code"],
                "legalName": r["legal_name"],
                "practiceName": r["practice_name"],
                "ocn": r["ocn"] or "",
                "bin": r["bin"] or "",
                "hstNumber": r["hst_number"] or "",
                "effectiveFrom": r["effective_from"] or "",
                "effectiveTo": r["effective_to"] or "",
                "defaultAddressLine": r["default_address_line"] or "",
                "altAddressLine": r["alt_address_line"] or "",
                "phone": r["phone"] or "",
                "email": r["email"] or "",
                "payableToName": r["payable_to_name"] or "",
                "eTransferEmail": r["etransfer_email"] or "",
                "bankAccountCode": r["bank_account_code"] or "",
                "invoiceNumberSuffix": r["invoice_number_suffix"] or "",
                "footerDisclosureText": r["footer_disclosure_text"] or "",
                "isDefault": bool(r["is_default"]),
                "active": bool(r["active"]),
            })
        return results

    def get_billing_entity(self, biller_code: str) -> Optional[Dict[str, Any]]:
        target = str(biller_code or "SOLE_PROP").strip().upper()
        for row in self.list_billing_entities():
            if row["BillerCode"] == target:
                return row
        return None

    def save_billing_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        code = str(payload.get("BillerCode") or payload.get("billerCode") or "").strip().upper()
        if not code:
            raise ValueError("BillerCode is required")
        conn.execute(
            """INSERT OR REPLACE INTO billing_entities (
                   biller_code, legal_name, practice_name, ocn, bin, hst_number,
                   effective_from, effective_to, default_address_line, alt_address_line,
                   phone, email, payable_to_name, etransfer_email, bank_account_code,
                   invoice_number_suffix, footer_disclosure_text, is_default, active
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code,
                str(payload.get("LegalName") or payload.get("legalName") or ""),
                str(payload.get("PracticeName") or payload.get("practiceName") or ""),
                str(payload.get("OCN") or payload.get("ocn") or ""),
                str(payload.get("BIN") or payload.get("bin") or ""),
                str(payload.get("HSTNumber") or payload.get("hstNumber") or ""),
                normalize_iso_date(payload.get("EffectiveFrom") or payload.get("effectiveFrom")),
                normalize_iso_date(payload.get("EffectiveTo") or payload.get("effectiveTo")),
                str(payload.get("DefaultAddressLine") or payload.get("defaultAddressLine") or ""),
                str(payload.get("AltAddressLine") or payload.get("altAddressLine") or ""),
                str(payload.get("Phone") or payload.get("phone") or ""),
                str(payload.get("Email") or payload.get("email") or ""),
                str(payload.get("PayableToName") or payload.get("payableToName") or ""),
                str(payload.get("ETransferEmail") or payload.get("eTransferEmail") or ""),
                str(payload.get("BankAccountCode") or payload.get("bankAccountCode") or ""),
                str(payload.get("InvoiceNumberSuffix") or payload.get("invoiceNumberSuffix") or ""),
                str(payload.get("FooterDisclosureText") or payload.get("footerDisclosureText") or ""),
                1 if (payload.get("IsDefault") or payload.get("isDefault")) else 0,
                1 if payload.get("Active", payload.get("active", 1)) else 0,
            ),
        )
        conn.commit()
        return {"ok": True, "BillerCode": code, **(self.get_billing_entity(code) or {})}

    # ------------------------------------------------------------------
    # Shareholder Loan Ledger (tblShareholderLoanLedger / shareholder_loan_ledger)
    # ------------------------------------------------------------------
    def _recalculate_shareholder_loan_balances(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute(
            "SELECT entry_id, loan_delta_cents FROM shareholder_loan_ledger ORDER BY date ASC, entry_id ASC"
        )
        rows = cursor.fetchall()
        running_cents = 0
        for row in rows:
            running_cents += int(row["loan_delta_cents"] or 0)
            running_dec = from_cents(running_cents)
            conn.execute(
                "UPDATE shareholder_loan_ledger SET running_balance = ?, running_balance_cents = ? WHERE entry_id = ?",
                (float(running_dec), running_cents, row["entry_id"]),
            )

    def list_shareholder_loan_entries(self, biller_entity: str = "PC") -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM shareholder_loan_ledger ORDER BY date ASC, entry_id ASC"
        )
        rows = cursor.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            pre_tax = float(from_cents(r["pre_tax_amount_cents"]))
            hst_amt = float(from_cents(r["hst_amount_cents"]))
            gross_amt = float(from_cents(r["gross_amount_cents"]))
            delta_amt = float(from_cents(r["loan_delta_cents"]))
            run_bal = float(from_cents(r["running_balance_cents"]))
            credit_amt = delta_amt if delta_amt > 0 else 0.0
            debit_amt = abs(delta_amt) if delta_amt < 0 else 0.0
            results.append({
                "EntryID": r["entry_id"],
                "Date": r["date"],
                "EntryType": r["entry_type"],
                "Description": r["description"],
                "VendorOrCounterparty": r["vendor_or_counterparty"] or "",
                "SourceAccount": r["source_account"] or "",
                "CategoryCode": r["category_code"] or "",
                "PreTaxAmount": pre_tax,
                "HSTAmount": hst_amt,
                "GrossAmount": gross_amt,
                "LoanDelta": delta_amt,
                "RunningBalance": run_bal,
                "LinkedTransactionID": r["linked_transaction_id"] or "",
                "LinkedAPBillID": r["linked_ap_bill_id"] or "",
                "ReceiptRef": r["receipt_ref"] or "",
                "GIFICode": r["gifi_code"] or "2781",
                "Notes": r["notes"] or "",
                "CreatedAt": r["created_at"] or "",
                "UpdatedAt": r["updated_at"] or "",
                # camelCase keys for ExcelRepo parity
                "shlEntryId": r["entry_id"],
                "entryDate": r["date"],
                "billerEntity": "PC",
                "entryType": r["entry_type"],
                "description": r["description"],
                "vendor": r["vendor_or_counterparty"] or "",
                "receiptRef": r["receipt_ref"] or "",
                "categoryCode": r["category_code"] or "",
                "gifiCode": r["gifi_code"] or "2781",
                "preTaxAmount": pre_tax,
                "hstAmount": hst_amt,
                "hstItcEligible": hst_amt > 0.0,
                "grossCreditToLoan": credit_amt,
                "debitRepaymentFromCorp": debit_amt,
                "runningLoanBalance": run_bal,
                "linkedTransactionId": r["linked_transaction_id"] or "",
                "notes": r["notes"] or "",
                "createdAt": r["created_at"] or "",
            })
        return results

    def append_shareholder_loan_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        now = get_utc_now()
        entry_id = str(
            payload.get("EntryID")
            or payload.get("entryId")
            or payload.get("shlEntryId")
            or ""
        ).strip()
        date_iso = normalize_iso_date(
            payload.get("Date") or payload.get("date") or payload.get("entryDate"),
            now[:10],
        )
        if not entry_id:
            year_prefix = date_iso[:4] if len(date_iso) >= 4 else "2026"
            cur = conn.execute(
                "SELECT entry_id FROM shareholder_loan_ledger WHERE entry_id LIKE ?",
                (f"SHL-{year_prefix}-%",),
            )
            max_seq = 0
            for r in cur.fetchall():
                eid = str(r["entry_id"] or "")
                parts = eid.split("-")
                if len(parts) >= 3 and parts[-1].isdigit():
                    max_seq = max(max_seq, int(parts[-1]))
            entry_id = f"SHL-{year_prefix}-{max_seq + 1:04d}"

        entry_type = str(
            payload.get("EntryType")
            or payload.get("entryType")
            or "EXPENSE_PAID_PERSONALLY"
        ).strip().upper()
        pre_tax_dec = to_decimal(payload.get("PreTaxAmount", payload.get("preTaxAmount", 0)))
        hst_dec = to_decimal(payload.get("HSTAmount", payload.get("hstAmount", 0)))
        gross_credit_dec = to_decimal(payload.get("grossCreditToLoan", 0))
        debit_repay_dec = to_decimal(payload.get("debitRepaymentFromCorp", 0))
        if payload.get("GrossAmount") not in (None, ""):
            gross_dec = to_decimal(payload.get("GrossAmount"))
        elif gross_credit_dec > Decimal("0.00"):
            gross_dec = gross_credit_dec
        elif debit_repay_dec > Decimal("0.00"):
            gross_dec = debit_repay_dec
        else:
            gross_dec = pre_tax_dec + hst_dec

        if payload.get("LoanDelta") not in (None, ""):
            delta_dec = to_decimal(payload.get("LoanDelta"))
        elif debit_repay_dec > Decimal("0.00") and gross_credit_dec == Decimal("0.00"):
            delta_dec = -abs(debit_repay_dec)
        elif entry_type in ("REPAYMENT", "CORP_REPAYMENT", "SHARE_SETOFF", "SHARE_SUBSCRIPTION_SETOFF", "DRAW"):
            delta_dec = -abs(gross_dec)
        else:
            delta_dec = abs(gross_dec)

        conn.execute(
            """INSERT OR REPLACE INTO shareholder_loan_ledger (
                   entry_id, date, entry_type, description, vendor_or_counterparty,
                   source_account, category_code, pre_tax_amount, pre_tax_amount_cents,
                   hst_amount, hst_amount_cents, gross_amount, gross_amount_cents,
                   loan_delta, loan_delta_cents, running_balance, running_balance_cents,
                   linked_transaction_id, linked_ap_bill_id, receipt_ref, gifi_code,
                   notes, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                date_iso,
                entry_type,
                str(payload.get("Description") or payload.get("description") or ""),
                str(payload.get("VendorOrCounterparty") or payload.get("vendorOrCounterparty") or payload.get("vendor") or ""),
                str(payload.get("SourceAccount") or payload.get("sourceAccount") or "PERSONAL_CARD"),
                str(payload.get("CategoryCode") or payload.get("categoryCode") or ""),
                float(pre_tax_dec),
                to_cents(pre_tax_dec),
                float(hst_dec),
                to_cents(hst_dec),
                float(gross_dec),
                to_cents(gross_dec),
                float(delta_dec),
                to_cents(delta_dec),
                str(payload.get("LinkedTransactionID") or payload.get("linkedTransactionId") or ""),
                str(payload.get("LinkedAPBillID") or payload.get("linkedApBillId") or ""),
                str(payload.get("ReceiptRef") or payload.get("receiptRef") or ""),
                str(payload.get("GIFICode") or payload.get("gifiCode") or "2781"),
                str(payload.get("Notes") or payload.get("notes") or ""),
                str(payload.get("CreatedAt") or payload.get("createdAt") or now),
                now,
            ),
        )
        self._recalculate_shareholder_loan_balances(conn)
        conn.commit()
        entries = self.list_shareholder_loan_entries()
        saved = next((e for e in entries if e["EntryID"] == entry_id), {})
        return {"ok": True, "EntryID": entry_id, "shlEntryId": entry_id, **saved, "entry": saved}

    # ------------------------------------------------------------------
    # CCA Assets & Nov 1 Equipment UCC Rollover (tblCCAAssets / cca_assets)
    # ------------------------------------------------------------------
    def list_cca_assets(
        self, biller_entity: Optional[str] = None, tax_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM cca_assets WHERE 1=1"
        params: List[Any] = []
        if biller_entity:
            query += " AND biller_entity = ?"
            params.append(str(biller_entity).strip().upper())
        if tax_year is not None:
            query += " AND tax_year = ?"
            params.append(int(tax_year))
        query += " ORDER BY tax_year ASC, cca_class ASC, asset_id ASC"
        cursor = conn.execute(query, tuple(params))
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            results.append({
                "AssetID": r["asset_id"],
                "BillerEntity": r["biller_entity"],
                "CCAClass": r["cca_class"],
                "CCARatePct": float(r["cca_rate_pct"] or 0.0),
                "Description": r["description"],
                "AcquisitionDate": r["acquisition_date"],
                "OriginalCost": float(from_cents(r["original_cost_cents"])),
                "OpeningUCC": float(from_cents(r["opening_ucc_cents"])),
                "Additions": float(from_cents(r["additions_cents"])),
                "DispositionsProceeds": float(from_cents(r["dispositions_proceeds_cents"])),
                "HalfYearRuleApplies": int(r["half_year_rule_applies"] or 0),
                "ImmediateExpensingApplies": int(r["immediate_expensing_applies"] or 0),
                "CCAClaimed": float(from_cents(r["cca_claimed_cents"])),
                "ClosingUCC": float(from_cents(r["closing_ucc_cents"])),
                "RolloverFromAssetID": r["rollover_from_asset_id"] or "",
                "TaxYear": int(r["tax_year"] or 2026),
                "Notes": r["notes"] or "",
                "CreatedAt": r["created_at"] or "",
                "UpdatedAt": r["updated_at"] or "",
            })
        return results

    def save_cca_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        now = get_utc_now()
        asset_id = str(payload.get("AssetID") or payload.get("assetId") or "").strip()
        if not asset_id:
            asset_id = f"CCA-{uuid.uuid4().hex[:8].upper()}"
        biller = str(payload.get("BillerEntity") or payload.get("billerEntity") or "PC").strip().upper()
        cca_class = str(payload.get("CCAClass") or payload.get("ccaClass") or "50").strip()
        rate_pct = to_decimal(payload.get("CCARatePct", payload.get("ccaRatePct", 55)))
        orig_cost = to_decimal(payload.get("OriginalCost", payload.get("originalCost", 0)))
        opening_ucc = to_decimal(payload.get("OpeningUCC", payload.get("openingUcc", 0)))
        additions = to_decimal(payload.get("Additions", payload.get("additions", 0)))
        dispositions = to_decimal(payload.get("DispositionsProceeds", payload.get("dispositionsProceeds", 0)))
        half_year = 1 if payload.get("HalfYearRuleApplies", 1) else 0
        imm_exp = 1 if payload.get("ImmediateExpensingApplies", 0) else 0

        base_ucc = opening_ucc + additions - dispositions
        if base_ucc < Decimal("0.00"):
            base_ucc = Decimal("0.00")
        if payload.get("CCAClaimed") not in (None, ""):
            cca_claimed = to_decimal(payload.get("CCAClaimed"))
        else:
            net_additions = max(Decimal("0.00"), additions - dispositions)
            if imm_exp:
                cca_claimed = base_ucc
            else:
                effective_base = base_ucc - (net_additions * Decimal("0.5") if half_year else Decimal("0.00"))
                cca_claimed = (effective_base * (rate_pct / Decimal(100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        closing_ucc = (
            to_decimal(payload.get("ClosingUCC"))
            if payload.get("ClosingUCC") not in (None, "")
            else max(Decimal("0.00"), base_ucc - cca_claimed)
        )

        conn.execute(
            """INSERT OR REPLACE INTO cca_assets (
                   asset_id, biller_entity, cca_class, cca_rate_pct, description,
                   acquisition_date, original_cost, original_cost_cents,
                   opening_ucc, opening_ucc_cents, additions, additions_cents,
                   dispositions_proceeds, dispositions_proceeds_cents,
                   half_year_rule_applies, immediate_expensing_applies,
                   cca_claimed, cca_claimed_cents, closing_ucc, closing_ucc_cents,
                   rollover_from_asset_id, tax_year, notes, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                biller,
                cca_class,
                float(rate_pct),
                str(payload.get("Description") or payload.get("description") or ""),
                normalize_iso_date(payload.get("AcquisitionDate") or payload.get("acquisitionDate"), "2026-11-01"),
                float(orig_cost),
                to_cents(orig_cost),
                float(opening_ucc),
                to_cents(opening_ucc),
                float(additions),
                to_cents(additions),
                float(dispositions),
                to_cents(dispositions),
                half_year,
                imm_exp,
                float(cca_claimed),
                to_cents(cca_claimed),
                float(closing_ucc),
                to_cents(closing_ucc),
                str(payload.get("RolloverFromAssetID") or payload.get("rolloverFromAssetId") or ""),
                int(payload.get("TaxYear") or payload.get("taxYear") or 2026),
                str(payload.get("Notes") or payload.get("notes") or ""),
                str(payload.get("CreatedAt") or now),
                now,
            ),
        )
        conn.commit()
        return {"ok": True, "AssetID": asset_id, "CCAClaimed": float(cca_claimed), "ClosingUCC": float(closing_ucc)}

    def record_equipment_ucc_rollover(self, payload_or_date: Any = "2026-11-01") -> Dict[str, Any]:
        if isinstance(payload_or_date, dict):
            payload = dict(payload_or_date)
            iso_date = normalize_iso_date(
                payload.get("transferDate") or payload.get("rolloverDate") or "2026-11-01",
                "2026-11-01",
            )
            explicit_ucc = to_decimal(payload.get("uccAmount") or payload.get("openingUcc") or 0)
            if explicit_ucc > Decimal("0.00"):
                cca_class = str(payload.get("ccaClass") or "50").strip()
                cca_rate = float(to_decimal(payload.get("ccaRatePct") or (55 if cca_class == "50" else 20)))
                desc = str(payload.get("description") or f"Class {cca_class} Office & Computer Equipment Rollover at UCC")
                orig_cost = float(to_decimal(payload.get("originalCost") or explicit_ucc))
                sp_asset_id = str(payload.get("solePropAssetId") or f"CCA-SP-{cca_class}-ROLLOVER")
                pc_asset_id = str(payload.get("pcAssetId") or f"CCA-PC-{cca_class}-ROLLOVER")
                sp_asset = self.save_cca_asset({
                    "AssetID": sp_asset_id,
                    "BillerEntity": "SOLE_PROP",
                    "CCAClass": cca_class,
                    "CCARatePct": cca_rate,
                    "Description": desc,
                    "AcquisitionDate": str(payload.get("acquisitionDate") or "2025-01-01"),
                    "OriginalCost": orig_cost,
                    "OpeningUCC": float(explicit_ucc),
                    "Additions": 0.0,
                    "DispositionsProceeds": float(explicit_ucc),
                    "CCAClaimed": 0.0,
                    "ClosingUCC": 0.0,
                    "TaxYear": int(iso_date[:4]) if iso_date[:4].isdigit() else 2026,
                    "Notes": f"Transferred to PC at tax cost (UCC = ${explicit_ucc:,.2f}) on {iso_date} outside Form T2057; zero recapture",
                })
                pc_asset = self.save_cca_asset({
                    "AssetID": pc_asset_id,
                    "BillerEntity": "PC",
                    "CCAClass": cca_class,
                    "CCARatePct": cca_rate,
                    "Description": desc,
                    "AcquisitionDate": iso_date,
                    "OriginalCost": float(explicit_ucc),
                    "OpeningUCC": 0.0,
                    "Additions": float(explicit_ucc),
                    "DispositionsProceeds": 0.0,
                    "CCAClaimed": 0.0,
                    "ClosingUCC": float(explicit_ucc),
                    "RolloverFromAssetID": sp_asset_id,
                    "TaxYear": int(iso_date[:4]) if iso_date[:4].isdigit() else 2026,
                    "Notes": f"Acquired from Sole Prop at tax cost (UCC = ${explicit_ucc:,.2f}) on {iso_date}; credited to Shareholder Loan (GIFI 2781)",
                })
                shl_entry = self.append_shareholder_loan_entry({
                    "entryDate": iso_date,
                    "billerEntity": "PC",
                    "entryType": "SECTION_85_BOOT_OR_UCC",
                    "description": f"Nov 1 Cutover Equipment Transfer at Tax Cost (Class {cca_class} UCC): {desc}",
                    "vendor": "Cory Schneider",
                    "receiptRef": f"Bill of Sale ({iso_date})",
                    "categoryCode": f"CCA_CLASS_{cca_class}",
                    "gifiCode": "1774" if cca_class == "50" else "1787",
                    "preTaxAmount": float(explicit_ucc),
                    "hstAmount": 0.0,
                    "hstItcEligible": False,
                    "grossCreditToLoan": float(explicit_ucc),
                    "debitRepaymentFromCorp": 0.0,
                    "notes": f"Equipment transferred at UCC (${explicit_ucc:,.2f}) outside Form T2057; credited dollar-for-dollar to Shareholder Loan (GIFI 2781)",
                })
                return {
                    "ok": True,
                    "rolloverDate": iso_date,
                    "solePropAsset": sp_asset,
                    "pcAsset": pc_asset,
                    "shlEntry": shl_entry,
                    "totalRolledUcc": float(explicit_ucc),
                }
        else:
            iso_date = normalize_iso_date(payload_or_date, "2026-11-01")
        tax_year = int(iso_date[:4]) if len(iso_date) >= 4 and iso_date[:4].isdigit() else 2026
        sole_assets = self.list_cca_assets(biller_entity="SOLE_PROP", tax_year=tax_year)
        pc_assets = self.list_cca_assets(biller_entity="PC", tax_year=tax_year)
        existing_rollover_ids = {a.get("RolloverFromAssetID") for a in pc_assets if a.get("RolloverFromAssetID")}

        total_rolled_ucc = Decimal("0.00")
        rolled_assets: List[str] = []

        for asset in sole_assets:
            aid = asset["AssetID"]
            if aid in existing_rollover_ids:
                continue
            ucc_val = to_decimal(asset.get("OpeningUCC") or asset.get("ClosingUCC") or asset.get("OriginalCost") or 0)
            if ucc_val <= Decimal("0.00"):
                continue
            # 1. Update SOLE_PROP asset so DispositionsProceeds = OpeningUCC + Additions (zero recapture)
            total_pool = to_decimal(asset.get("OpeningUCC", 0)) + to_decimal(asset.get("Additions", 0))
            self.save_cca_asset({
                **asset,
                "DispositionsProceeds": float(total_pool),
                "CCAClaimed": 0.0,
                "ClosingUCC": 0.0,
                "Notes": f"Transferred to PC at tax cost (UCC ${total_pool:.2f}) on {iso_date} outside Form T2057.",
            })
            # 2. Create PC asset with OpeningUCC = total_pool
            pc_asset_id = f"{aid}-PC"
            self.save_cca_asset({
                "AssetID": pc_asset_id,
                "BillerEntity": "PC",
                "CCAClass": asset["CCAClass"],
                "CCARatePct": asset["CCARatePct"],
                "Description": f"{asset['Description']} (UCC Rollover from Sole Prop)",
                "AcquisitionDate": iso_date,
                "OriginalCost": float(asset.get("OriginalCost") or total_pool),
                "OpeningUCC": float(total_pool),
                "Additions": 0.0,
                "DispositionsProceeds": 0.0,
                "HalfYearRuleApplies": 0,
                "ImmediateExpensingApplies": 0,
                "RolloverFromAssetID": aid,
                "TaxYear": tax_year,
                "Notes": f"Acquired at UCC (${total_pool:.2f}) from Sole Prop on {iso_date} credited to Shareholder Loan (GIFI 2781).",
            })
            total_rolled_ucc += total_pool
            rolled_assets.append(pc_asset_id)

        shl_entry_id = ""
        if total_rolled_ucc > Decimal("0.00"):
            shl_res = self.append_shareholder_loan_entry({
                "Date": iso_date,
                "EntryType": "SECTION_85_BOOT_OR_UCC",
                "Description": f"Nov 1 Equipment Transfer at Tax Cost (UCC) — {', '.join(rolled_assets)}",
                "VendorOrCounterparty": "Cory Schneider (Sole Prop Equipment Rollover)",
                "SourceAccount": "IN_KIND_ROLLOVER",
                "CategoryCode": "EXP_OFFICE_EQUIPMENT",
                "PreTaxAmount": float(total_rolled_ucc),
                "HSTAmount": 0.0,
                "GrossAmount": float(total_rolled_ucc),
                "LoanDelta": float(total_rolled_ucc),
                "ReceiptRef": f"UCC-ROLLOVER-{iso_date}",
                "GIFICode": "2781",
                "Notes": "Equipment transferred at UCC outside Form T2057; credited dollar-for-dollar to Shareholder Loan.",
            })
            shl_entry_id = shl_res.get("EntryID", "")

        return {
            "ok": True,
            "rolloverDate": iso_date,
            "rolledAssetIds": rolled_assets,
            "totalRolledUcc": float(total_rolled_ucc),
            "shareholderLoanEntryId": shl_entry_id,
        }

    # ------------------------------------------------------------------
    # HST Log (tblHSTLog / hst_log)
    # ------------------------------------------------------------------
    def list_hst_log(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM hst_log WHERE 1=1"
        params: List[Any] = []
        if biller_entity:
            query += " AND biller_entity = ?"
            params.append(str(biller_entity).strip().upper())
        query += " ORDER BY period_start DESC, period_id DESC"
        cursor = conn.execute(query, tuple(params))
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            biller = r["biller_entity"] or "SOLE_PROP"
            l101 = float(from_cents(r["line_101_sales_cents"]))
            l103 = float(from_cents(r["line_103_hst_collected_cents"]))
            l106 = float(from_cents(r["line_106_itcs_cents"]))
            net_tax = float(from_cents(r["net_tax_cents"]))
            results.append({
                "PeriodID": r["period_id"],
                "PeriodStart": r["period_start"],
                "PeriodEnd": r["period_end"],
                "FiledDate": r["filed_date"] or "",
                "ConfNum": r["conf_num"] or "",
                "NetTax": net_tax,
                "PaidDate": r["paid_date"] or "",
                "PaymentRef": r["payment_ref"] or "",
                "BillerEntity": biller,
                "Line101Sales": l101,
                "Line103HSTCollected": l103,
                "Line104Adjustments": float(from_cents(r["line_104_adjustments_cents"])),
                "Line105TotalHST": float(from_cents(r["line_105_total_hst_cents"])),
                "Line106ITCs": l106,
                "Line107ITCAdjustments": float(from_cents(r["line_107_itc_adjustments_cents"])),
                "Line108TotalITCs": float(from_cents(r["line_108_total_itcs_cents"])),
                "Line110Instalments": float(from_cents(r["line_110_instalments_cents"])),
                "Line113Balance": float(from_cents(r["line_113_balance_cents"])),
                "Status": r["status"] or "Draft",
                "Notes": r["notes"] or "",
                "periodId": r["period_id"],
                "billerEntity": biller,
                "periodStart": r["period_start"],
                "periodEnd": r["period_end"],
                "filingDate": r["filed_date"] or "",
                "line101SalesRevenue": l101,
                "hstCollected": l103,
                "hstItcs": l106,
                "netRemitted": net_tax,
                "confirmationNum": r["conf_num"] or "",
                "status": r["status"] or "Draft",
            })
        return results

    def save_hst_filing_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        period_id = str(payload.get("PeriodID") or payload.get("periodId") or "").strip()
        biller = str(payload.get("BillerEntity") or payload.get("billerEntity") or "PC").strip().upper()
        p_start = normalize_iso_date(payload.get("PeriodStart") or payload.get("periodStart"))
        p_end = normalize_iso_date(payload.get("PeriodEnd") or payload.get("periodEnd"))
        if not period_id:
            period_id = f"HST-{biller}-{p_start}-TO-{p_end}"

        l101 = to_decimal(payload.get("Line101Sales", payload.get("line101SalesRevenue", 0)))
        l103 = to_decimal(payload.get("Line103HSTCollected", payload.get("hstCollected", 0)))
        l104 = to_decimal(payload.get("Line104Adjustments", 0))
        l105 = to_decimal(payload.get("Line105TotalHST", l103 + l104))
        l106 = to_decimal(payload.get("Line106ITCs", payload.get("hstItcs", 0)))
        l107 = to_decimal(payload.get("Line107ITCAdjustments", 0))
        l108 = to_decimal(payload.get("Line108TotalITCs", l106 + l107))
        net_tax = to_decimal(payload.get("NetTax", payload.get("netRemitted", l105 - l108)))
        l110 = to_decimal(payload.get("Line110Instalments", 0))
        l113 = to_decimal(payload.get("Line113Balance", net_tax - l110))

        conn.execute(
            """INSERT OR REPLACE INTO hst_log (
                   period_id, period_start, period_end, filed_date, conf_num,
                   net_tax, net_tax_cents, paid_date, payment_ref, biller_entity,
                   line_101_sales, line_101_sales_cents,
                   line_103_hst_collected, line_103_hst_collected_cents,
                   line_104_adjustments, line_104_adjustments_cents,
                   line_105_total_hst, line_105_total_hst_cents,
                   line_106_itcs, line_106_itcs_cents,
                   line_107_itc_adjustments, line_107_itc_adjustments_cents,
                   line_108_total_itcs, line_108_total_itcs_cents,
                   line_110_instalments, line_110_instalments_cents,
                   line_113_balance, line_113_balance_cents,
                   status, notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                period_id, p_start, p_end,
                normalize_iso_date(payload.get("FiledDate") or payload.get("filingDate")),
                str(payload.get("ConfNum") or payload.get("confirmationNum") or ""),
                float(net_tax), to_cents(net_tax),
                normalize_iso_date(payload.get("PaidDate")),
                str(payload.get("PaymentRef") or ""),
                biller,
                float(l101), to_cents(l101),
                float(l103), to_cents(l103),
                float(l104), to_cents(l104),
                float(l105), to_cents(l105),
                float(l106), to_cents(l106),
                float(l107), to_cents(l107),
                float(l108), to_cents(l108),
                float(l110), to_cents(l110),
                float(l113), to_cents(l113),
                str(payload.get("Status") or payload.get("status") or "Filed"),
                str(payload.get("Notes") or payload.get("notes") or ""),
            ),
        )
        conn.commit()
        return {"ok": True, "PeriodID": period_id, "periodId": period_id}

    # ------------------------------------------------------------------
    # Additional Readers for TaxComplianceService Parity
    # ------------------------------------------------------------------
    def list_invoices(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        target = str(biller_entity or "").strip().upper()
        cursor = conn.execute("SELECT * FROM Invoice ORDER BY date ASC, invoice_id ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            inv_num = r["invoice_num"] or r["invoice_id"]
            biller = (r["biller_entity"] or ("PC" if str(inv_num).endswith("-PC") else infer_biller_from_date(r["date"]))).upper()
            if target and biller != target:
                continue
            fees = float(from_cents(r["total_fees_cents"])) if r["total_fees_cents"] else float(r["total_fees"] or 0.0)
            disb = float(from_cents(r["total_disbursements_cents"])) if r["total_disbursements_cents"] else float(r["total_disbursements"] or 0.0)
            tax = float(from_cents(r["tax_amount_cents"])) if r["tax_amount_cents"] else float(r["tax_amount"] or 0.0)
            total = float(from_cents(r["total_amount_cents"])) if r["total_amount_cents"] else float(r["total_amount"] or 0.0)
            results.append({
                "InvoiceNum": inv_num,
                "ClientID": r["client_id"],
                "ClientName": r["client_name"] or "",
                "SubClient": r["sub_client"] or "",
                "InvoiceDate": r["date"],
                "TotalFees": fees,
                "TotalDisbursements": disb,
                "TotalTax": tax,
                "AggregateBilled": fees,
                "Status": r["status"] or "Finalized",
                "BillToClient": r["bill_to_client"] or "",
                "BillToSnapshot": r["bill_to_snapshot"] or "",
                "FilePath": r["file_path"] or "",
                "BillerEntity": biller,
                "BillerAddressOverride": r["biller_address_override"] or "",
                "BillerHSTOverride": r["biller_hst_override"] or "",
                "invoiceNum": inv_num,
                "invoiceDate": r["date"],
                "clientName": r["client_name"] or "",
                "billToClient": r["bill_to_client"] or "",
                "subClient": r["sub_client"] or "",
                "aggregateBilled": fees,
                "hstOnBilled": tax,
                "disbursementsPreHst": disb,
                "hstOnDisbursements": 0.0,
                "totalInvoiceAmount": total,
                "paymentStatus": r["status"] or "Open",
                "billerEntity": biller,
                "billerAddressOverride": r["biller_address_override"] or "",
                "billerHstOverride": r["biller_hst_override"] or "",
            })
        return results

    def list_transaction_categories(
        self,
        txn_type: str = "",
        txn_class: str = "",
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM transaction_categories ORDER BY sort_order ASC, category_code ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            ded_pct = float(r["deductible_pct"] if r["deductible_pct"] is not None else 100.0)
            itc_pct = float(r["itc_claimable_pct"] if r["itc_claimable_pct"] is not None else 100.0)
            results.append({
                "CategoryCode": r["category_code"],
                "CategoryName": r["category_name"],
                "Type": r["type"],
                "ClassScope": r["class_scope"] or "Both",
                "TaxFlagDefault": r["tax_flag_default"] or "None",
                "BillableAllowed": int(r["billable_allowed"] or 0),
                "MedicalEligible": int(r["medical_eligible"] or 0),
                "DeductibleEligible": int(r["deductible_eligible"] or 0),
                "BusinessDeductibleEligible": int(r["business_deductible_eligible"] or 0),
                "Active": int(r["active"] or 1),
                "SortOrder": int(r["sort_order"] or 0),
                "Notes": r["notes"] or "",
                "T2125LineNumber": r["t2125_line_number"] or "",
                "T2125LineLabel": r["t2125_line_label"] or "",
                "GIFISchedule125Code": r["gifi_schedule_125_code"] or "",
                "GIFISchedule125Label": r["gifi_schedule_125_label"] or "",
                "DeductiblePct": ded_pct,
                "ITCClaimablePct": itc_pct,
                "categoryCode": r["category_code"],
                "categoryName": r["category_name"],
                "type": r["type"],
                "classScope": r["class_scope"] or "Both",
                "taxFlagDefault": r["tax_flag_default"] or "None",
                "t2125LineNumber": r["t2125_line_number"] or "",
                "t2125LineLabel": r["t2125_line_label"] or "",
                "gifiSchedule125Code": r["gifi_schedule_125_code"] or "",
                "gifiSchedule125Label": r["gifi_schedule_125_label"] or "",
                "deductiblePct": ded_pct,
                "itcClaimablePct": itc_pct,
            })
        return results

    def list_disbursements(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        target = str(biller_entity or "").strip().upper()
        cursor = conn.execute("SELECT * FROM disbursements ORDER BY date ASC, disbursement_id ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            biller = (r["biller_entity"] or infer_biller_from_date(r["date"])).upper()
            if target and biller != target:
                continue
            amt = float(from_cents(r["amount_cents"])) if r["amount_cents"] else float(r["amount"] or 0.0)
            results.append({
                "DisbursementID": r["disbursement_id"],
                "Date": r["date"],
                "ClientName": r["client_name"] or "",
                "SubClient": r["sub_client"] or "",
                "ClientID": r["client_id"] or "",
                "ParentID": r["parent_id"] or "",
                "MatterID": r["matter_id"] or "",
                "Description": r["description"] or "",
                "Amount": amt,
                "TaxExempt": int(r["tax_exempt"] or 0),
                "BillPct": float(r["bill_pct"] or 100.0),
                "InvoiceRef": r["invoice_ref"] or "",
                "PaymentStatus": r["payment_status"] or "",
                "APBillID": r["ap_bill_id"] or "",
                "SourceTransactionID": r["source_transaction_id"] or "",
                "BillerEntity": biller,
                "disbId": r["disbursement_id"],
                "date": r["date"],
                "matterId": r["matter_id"] or "",
                "clientId": r["client_id"] or "",
                "description": r["description"] or "",
                "amountExclHst": amt,
                "invoiceNum": r["invoice_ref"] or "",
                "status": r["payment_status"] or "",
                "billerEntity": biller,
            })
        return results

    def list_receivables(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        target = str(biller_entity or "").strip().upper()
        cursor = conn.execute("SELECT * FROM Receivable ORDER BY date ASC, receivable_id ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            biller = (r["biller_entity"] or ("PC" if str(r["invoice_id"]).endswith("-PC") else "SOLE_PROP")).upper()
            if target and biller != target:
                continue
            tot_inv = float(from_cents(r["total_invoiced_cents"])) if r["total_invoiced_cents"] else float(r["total_invoiced"] or 0.0)
            amt_paid = float(from_cents(r["amount_paid_cents"])) if r["amount_paid_cents"] else float(r["amount_paid"] or 0.0)
            cred_adj = float(from_cents(r["credits_adj_cents"])) if r["credits_adj_cents"] else float(r["credits_adj"] or 0.0)
            bal_due = float(from_cents(r["amount_due_cents"])) if r["amount_due_cents"] else float(r["amount_due"] or 0.0)
            results.append({
                "InvoiceNum": r["invoice_id"],
                "Date": r["date"] or "",
                "Client": r["client_name"] or "",
                "TotalInvoiced": tot_inv,
                "AmountPaid": amt_paid,
                "CreditsAdj": cred_adj,
                "BalanceDue": bal_due,
                "Status": r["status"] or "Unpaid",
                "WorkClient": r["work_client"] or "",
                "BillerEntity": biller,
                "invoiceNum": r["invoice_id"],
                "client": r["client_name"] or "",
                "workClient": r["work_client"] or "",
                "invoiceDate": r["date"] or "",
                "totalInvoiced": tot_inv,
                "amountPaid": amt_paid,
                "writeOff": cred_adj,
                "balanceDue": bal_due,
                "status": r["status"] or "Unpaid",
                "billerEntity": biller,
            })
        return results

    def list_ap_bills(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        target = str(biller_entity or "").strip().upper()
        cursor = conn.execute("SELECT * FROM AccountsPayable ORDER BY date ASC, ap_id ASC")
        results: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            biller = (r["biller_entity"] or infer_biller_from_date(r["date"])).upper()
            if target and biller != target:
                continue
            sub = float(from_cents(r["subtotal_cents"])) if r["subtotal_cents"] else float(r["subtotal"] or 0.0)
            tax = float(from_cents(r["tax_amount_cents"])) if r["tax_amount_cents"] else float(r["tax_amount"] or 0.0)
            tot = float(from_cents(r["amount_cents"])) if r["amount_cents"] else float(r["amount"] or 0.0)
            paid = float(from_cents(r["amount_paid_cents"])) if r["amount_paid_cents"] else float(r["amount_paid"] or 0.0)
            bal = float(from_cents(r["balance_cents"])) if r["balance_cents"] else float(r["balance"] or 0.0)
            results.append({
                "APBillID": r["ap_id"],
                "Vendor": r["vendor_name"],
                "VendorInvoiceNumber": r["vendor_invoice_number"] or "",
                "InvoiceDate": r["date"],
                "DueDate": r["due_date"] or "",
                "Subtotal": sub,
                "TaxAmount": tax,
                "Total": tot,
                "AmountPaid": paid,
                "Balance": bal,
                "Status": r["status"] or "Unpaid",
                "ExpenseTransactionID": r["expense_transaction_id"] or "",
                "ExpenseTreatment": r["expense_treatment"] or "",
                "CategoryCode": r["category_code"] or "",
                "CategoryName": r["category_name"] or "",
                "SourceAccount": r["source_account"] or "",
                "BillerEntity": biller,
                "apBillId": r["ap_id"],
                "vendorName": r["vendor_name"] or "",
                "invoiceNumber": r["vendor_invoice_number"] or "",
                "invoiceDate": r["date"],
                "dueDate": r["due_date"] or "",
                "status": r["status"] or "Unpaid",
                "expenseType": r["expense_treatment"] or "",
                "categoryCode": r["category_code"] or "",
                "subtotalExclTax": sub,
                "taxTotal": tax,
                "grossTotal": tot,
                "paidTotal": paid,
                "balanceTotal": bal,
                "billerEntity": biller,
            })
        return results

    def list_corp_entities(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM corp_entities ORDER BY entity_id ASC")
        return [
            {
                "EntityID": r["entity_id"],
                "ClientID": r["client_id"] or "",
                "LegalName": r["legal_name"],
                "Jurisdiction": r["jurisdiction"] or "",
                "IncorporationDate": r["incorporation_date"] or "",
                "IncorporationNumber": r["incorporation_number"] or "",
                "FiscalYearEnd": r["fiscal_year_end"] or "",
                "Status": r["status"] or "Active",
                "Notes": r["notes"] or "",
                "CreatedAt": r["created_at"] or "",
            }
            for r in cursor.fetchall()
        ]

    def list_corp_relationships(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM corp_relationships ORDER BY relationship_id ASC")
        return [
            {
                "RelationshipID": r["relationship_id"],
                "SourceEntityID": r["source_entity_id"],
                "TargetEntityID": r["target_entity_id"],
                "RelationshipType": r["relationship_type"],
                "Title": r["title"] or "",
                "ShareClass": r["share_class"] or "",
                "SharesHeld": float(r["shares_held"] or 0.0),
                "OwnershipPercentage": float(r["ownership_percentage"] or 0.0),
                "StartDate": r["start_date"] or "",
                "EndDate": r["end_date"] or "",
                "Active": int(r["active"] or 1),
            }
            for r in cursor.fetchall()
        ]

    def list_corp_transactions(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM corp_transactions ORDER BY date ASC, transaction_id ASC")
        return [
            {
                "TransactionID": r["transaction_id"],
                "EntityID": r["entity_id"],
                "Date": r["date"],
                "TransactionType": r["transaction_type"],
                "FromEntityID": r["from_entity_id"] or "",
                "ToEntityID": r["to_entity_id"] or "",
                "ShareClass": r["share_class"] or "",
                "NumberOfShares": float(r["number_of_shares"] or 0.0),
                "PricePerShare": float(r["price_per_share"] or 0.0),
                "TotalValue": float(from_cents(r["total_value_cents"])) if r["total_value_cents"] else float(r["total_value"] or 0.0),
                "DocumentReference": r["document_reference"] or "",
                "Notes": r["notes"] or "",
                "CreatedAt": r["created_at"] or "",
            }
            for r in cursor.fetchall()
        ]
