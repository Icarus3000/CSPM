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
               p.billing_address, p.tax_number, p.payment_terms
        FROM Client c
        LEFT JOIN ClientProfile p ON c.client_id = p.client_id
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        directory = []
        for row in rows:
            client_id = row["client_id"]
            client_name = row["client_name"]
            directory.append({
                "clientId": client_id,
                "clientName": client_name,
                "displayName": client_name,
                "legalName": client_name,
                "firstName": "",
                "middleName": "",
                "lastName": "",
                "entityType": "Corporate",
                "status": row["status"],
                "active": 1 if row["status"] == "Active" else 0,
                "primaryEmail": "",
                "primaryPhone": "",
                "parentClientName": "",
                "onboardingStatus": "",
                "kycStatus": "",
                "updatedAt": "",
                "searchText": f"{client_id} {client_name}".lower(),
            })
        return directory

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
    def list_matter_directory(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
        SELECT m.matter_id, m.description, m.status, m.default_biller, c.name as client_name, c.client_id
        FROM Matter m
        JOIN Client c ON m.client_id = c.client_id
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        directory = []
        for row in rows:
            directory.append({
                "matterId": row["matter_id"],
                "clientId": row["client_id"],
                "clientName": row["client_name"],
                "description": row["description"],
                "status": row["status"],
                "defaultBiller": row["default_biller"] or "PC",
                "active": 1 if row["status"] == "Open" else 0,
                "searchText": f"{row['matter_id']} {row['client_name']} {row['description']}".lower(),
            })
        return directory

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
    def list_time_entries(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM TimeEntry ORDER BY date DESC, created_at DESC"
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]

        results = []
        for row in rows:
            biller = row.get("biller_entity") or infer_biller_from_date(row.get("date"))
            item = {
                "EntryID": row["time_id"],
                "MatterID": row["matter_id"],
                "ClientID": row.get("client_id") or "",
                "ParentID": row.get("parent_id") or "",
                "Date": row["date"],
                "Hours": float(row.get("hours") or 0.0),
                "ClientRate": float(row.get("rate") or 0.0),
                "SharePct": float(row.get("share_pct") or 100.0),
                "GrossToClient": float(row.get("amount") or 0.0),
                "AmountToYou": float(row.get("amount_to_you") or row.get("amount") or 0.0),
                "HST": float(row.get("hst") or 0.0),
                "TotalInclHST": float(row.get("total_incl_hst") or 0.0),
                "Description": row.get("description") or "",
                "Status": row.get("status") or ("Billed" if row.get("is_billed") else "Unbilled"),
                "InvoiceRef": row.get("billed_invoice_id") or "",
                "BillerEntity": biller,
                # Legacy camelCase keys
                "entryId": row["time_id"],
                "matterId": row["matter_id"],
                "date": row["date"],
                "hours": float(row.get("hours") or 0.0),
                "rate": float(row.get("rate") or 0.0),
                "amount": float(row.get("amount") or 0.0),
                "description": row.get("description") or "",
                "status": row.get("status") or ("Billed" if row.get("is_billed") else "Draft"),
                "billerEntity": biller,
            }
            if filters:
                biller_filter = filters.get("biller_entity") or filters.get("BillerEntity")
                if biller_filter and item["BillerEntity"] != biller_filter:
                    continue
            results.append(item)
        return results

    def save_time_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        entry_id = payload.get("EntryID") or payload.get("entryId")
        matter_id = payload.get("MatterID") or payload.get("matterId") or ""
        client_id = payload.get("ClientID") or payload.get("clientId") or ""
        parent_id = payload.get("ParentID") or payload.get("parentId") or ""
        date = normalize_iso_date(payload.get("Date") or payload.get("date"), get_utc_now()[:10])
        hours = float(payload.get("Hours") if "Hours" in payload else payload.get("hours", 0.0))
        rate = float(payload.get("ClientRate") if "ClientRate" in payload else payload.get("rate", 0.0))
        share_pct = float(payload.get("SharePct", 100.0))
        desc = payload.get("Description") or payload.get("description") or ""
        amount_dec = to_decimal(payload.get("GrossToClient") if "GrossToClient" in payload else hours * rate)
        amount_to_you_dec = to_decimal(
            payload.get("AmountToYou") if "AmountToYou" in payload else (amount_dec * to_decimal(share_pct) / Decimal(100))
        )
        hst_dec = to_decimal(payload.get("HST") if "HST" in payload else (amount_to_you_dec * Decimal("0.13")))
        total_incl_dec = to_decimal(payload.get("TotalInclHST") if "TotalInclHST" in payload else (amount_to_you_dec + hst_dec))
        status = payload.get("Status") or payload.get("status") or "Unbilled"
        invoice_ref = payload.get("InvoiceRef") or payload.get("billed_invoice_id") or ""
        is_billed = 1 if (invoice_ref or status.lower() in ("billed", "invoiced", "paid")) else 0
        biller_entity = payload.get("BillerEntity") or payload.get("billerEntity") or infer_biller_from_date(date)
        now = get_utc_now()

        if not entry_id:
            entry_id = f"TIM-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """INSERT OR REPLACE INTO TimeEntry (
                   time_id, matter_id, client_id, parent_id, date, hours, rate, rate_cents,
                   share_pct, amount, amount_cents, amount_to_you, amount_to_you_cents,
                   hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                   description, status, is_billed, billed_invoice_id, biller_entity,
                   created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id, matter_id, client_id, parent_id, date, hours, rate, to_cents(rate),
                share_pct, float(amount_dec), to_cents(amount_dec),
                float(amount_to_you_dec), to_cents(amount_to_you_dec),
                float(hst_dec), to_cents(hst_dec),
                float(total_incl_dec), to_cents(total_incl_dec),
                desc, status, is_billed, invoice_ref, biller_entity, now, now
            ),
        )
        conn.commit()
        return {"ok": True, "entryId": entry_id, "EntryID": entry_id, "amount": float(amount_dec), "BillerEntity": biller_entity}

    def delete_time_entry(self, entry_id: str) -> bool:
        conn = get_connection()
        cursor = conn.execute("DELETE FROM TimeEntry WHERE time_id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_unbilled_time(self, matter_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM TimeEntry WHERE matter_id = ? AND is_billed = 0", (matter_id,))
        return [dict(row) for row in cursor.fetchall()]


class SQLiteRepository(SqliteFinanceRepo, SqliteClientRepo, SqliteMatterRepo, SqliteTimeRepo):
    """Unified SQLite Repository with full parity to ExcelRepo for Multi-Biller, Shareholder Loan, CCA, HST, and Income Tax."""

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
