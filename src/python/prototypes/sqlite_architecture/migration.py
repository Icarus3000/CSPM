# PROTOTYPE ONLY
# PRODUCTION UNAPPROVED
# MUST NOT RESOLVE TO PRODUCTION PATHS
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_PYTHON = REPO_ROOT / "src" / "python"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

try:
    from .connection import close_connection, get_connection, init_schema
    from .sqlite_repo import (
        SQLiteRepository,
        SqliteClientRepo,
        SqliteMatterRepo,
        SqliteTimeRepo,
        get_utc_now,
        infer_biller_from_date,
        normalize_iso_date,
        to_cents,
        to_decimal,
    )
except ImportError:
    from src.python.prototypes.sqlite_architecture.connection import (
        close_connection,
        get_connection,
        init_schema,
    )
    from src.python.prototypes.sqlite_architecture.sqlite_repo import (
        SQLiteRepository,
        SqliteClientRepo,
        SqliteMatterRepo,
        SqliteTimeRepo,
        get_utc_now,
        infer_biller_from_date,
        normalize_iso_date,
        to_cents,
        to_decimal,
    )

from domain.ap_schema import AP_BILLS_TABLE
from domain.schema_constants import (
    TBL_BILLING_ENTITIES,
    TBL_CCA_ASSETS,
    TBL_CLIENT_PROFILES,
    TBL_CLIENTS,
    TBL_CORP_ENTITIES,
    TBL_CORP_RELATIONSHIPS,
    TBL_CORP_TRANSACTIONS,
    TBL_DISBURSEMENTS,
    TBL_DRAFT_INVOICES,
    TBL_HST_LOG,
    TBL_INVOICE_LOG,
    TBL_LEDGER,
    TBL_MATTER_PARTIES,
    TBL_MATTERS,
    TBL_RECEIVABLES,
    TBL_SHAREHOLDER_LOAN_LEDGER,
    TBL_TIME_ENTRIES,
    TBL_TRANSACTIONS_MASTER,
    TBL_TRANSACTION_CATEGORIES,
)
from repositories.excel_repo import ExcelRepo, TABLES_IN_ORDER
from services.paths import AppPaths

logger = logging.getLogger(__name__)


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def perform_dry_run_migration(workbook_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Reads from the Excel repository, normalizes data types, resolves null references,
    and inserts 100% of legacy and multi-biller/tax tables into the SQLite schema
    in a single atomic transaction.
    """
    logger.info("Initializing SQLite Schema...")
    init_schema()

    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    counts: Dict[str, int] = {}

    try:
        logger.info("Loading Excel Data...")
        paths = AppPaths(root=REPO_ROOT)
        if workbook_path is not None:
            wb_p = Path(workbook_path)
            paths.override_data_dir = wb_p.parent if wb_p.suffix else wb_p
        excel_repo = ExcelRepo(paths)
        excel_repo.ensure_schema()
        bulk_tables = excel_repo._read_table_rows_bulk(list(TABLES_IN_ORDER))
        now = get_utc_now()

        def _read_rows(table_name: str) -> List[Dict[str, Any]]:
            if table_name in bulk_tables:
                return list(bulk_tables.get(table_name) or [])
            if table_name == AP_BILLS_TABLE:
                try:
                    return list(excel_repo.list_ap_bills() or [])
                except Exception:
                    return []
            return []

        sqlite_repo = SQLiteRepository()

        # 1. Billing Entities
        billing_entities = _read_rows(TBL_BILLING_ENTITIES)
        for row in billing_entities:
            code = str(row.get("BillerCode") or "").strip().upper()
            if not code:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO billing_entities (
                       biller_code, legal_name, practice_name, ocn, bin, hst_number,
                       effective_from, effective_to, default_address_line, alt_address_line,
                       phone, email, payable_to_name, etransfer_email, bank_account_code,
                       invoice_number_suffix, footer_disclosure_text, is_default, active
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code,
                    str(row.get("LegalName") or ""),
                    str(row.get("PracticeName") or ""),
                    str(row.get("OCN") or ""),
                    str(row.get("BIN") or ""),
                    str(row.get("HSTNumber") or ""),
                    normalize_iso_date(row.get("EffectiveFrom")),
                    normalize_iso_date(row.get("EffectiveTo")),
                    str(row.get("DefaultAddressLine") or ""),
                    str(row.get("AltAddressLine") or ""),
                    str(row.get("Phone") or ""),
                    str(row.get("Email") or ""),
                    str(row.get("PayableToName") or ""),
                    str(row.get("ETransferEmail") or ""),
                    str(row.get("BankAccountCode") or ""),
                    str(row.get("InvoiceNumberSuffix") or ""),
                    str(row.get("FooterDisclosureText") or ""),
                    1 if str(row.get("IsDefault") or "0") in ("1", "True", "true") else 0,
                    1 if str(row.get("Active", "1")) in ("1", "True", "true") else 0,
                ),
            )
        counts["billing_entities"] = len(billing_entities)

        # 2. Shareholder Loan Ledger (GIFI 2781)
        shl_rows = _read_rows(TBL_SHAREHOLDER_LOAN_LEDGER)
        for row in shl_rows:
            entry_id = str(row.get("SHLEntryID") or row.get("EntryID") or "").strip() or generate_id("SHL")
            pre_tax = to_decimal(row.get("PreTaxAmount", 0))
            hst = to_decimal(row.get("HSTITCAmount", row.get("HSTAmount", 0)))
            gross = to_decimal(row.get("GrossAmount", pre_tax + hst))
            delta = to_decimal(row.get("SignedDelta", row.get("LoanDelta", gross)))
            running = to_decimal(row.get("RunningBalance", 0))
            conn.execute(
                """INSERT OR REPLACE INTO shareholder_loan_ledger (
                       entry_id, date, entry_type, description, vendor_or_counterparty,
                       source_account, category_code, pre_tax_amount, pre_tax_amount_cents,
                       hst_amount, hst_amount_cents, gross_amount, gross_amount_cents,
                       loan_delta, loan_delta_cents, running_balance, running_balance_cents,
                       linked_transaction_id, linked_ap_bill_id, receipt_ref, gifi_code,
                       notes, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    normalize_iso_date(row.get("EffectiveDate") or row.get("Date"), "2026-10-17"),
                    str(row.get("EntryType") or "PERSONAL_EXPENSE"),
                    str(row.get("Description") or ""),
                    str(row.get("VendorPayee") or row.get("VendorOrCounterparty") or ""),
                    str(row.get("SourceAccount") or "CORY_PERSONAL"),
                    str(row.get("CategoryCode") or ""),
                    float(pre_tax),
                    to_cents(pre_tax),
                    float(hst),
                    to_cents(hst),
                    float(gross),
                    to_cents(gross),
                    float(delta),
                    to_cents(delta),
                    float(running),
                    to_cents(running),
                    str(row.get("SourceTxnID") or row.get("LinkedTransactionID") or ""),
                    str(row.get("SourceAPBillID") or row.get("LinkedAPBillID") or ""),
                    str(row.get("ReferenceNumber") or row.get("ReceiptRef") or ""),
                    str(row.get("GIFILine") or row.get("GIFICode") or "2781"),
                    str(row.get("Notes") or ""),
                    str(row.get("CreatedAt") or now),
                    str(row.get("UpdatedAt") or now),
                ),
            )
        sqlite_repo._recalculate_shareholder_loan_balances(conn)
        counts["shareholder_loan_ledger"] = len(shl_rows)

        # 3. CCA Assets
        cca_rows = _read_rows(TBL_CCA_ASSETS)
        for row in cca_rows:
            asset_id = str(row.get("AssetID") or "").strip() or generate_id("CCA")
            orig_cost = to_decimal(row.get("OriginalCost", 0))
            open_ucc = to_decimal(row.get("OpeningUCC", 0))
            adds = to_decimal(row.get("AdditionsAmount", row.get("Additions", 0)))
            disps = to_decimal(row.get("ProceedsOfDisposition", row.get("DispositionsProceeds", 0)))
            claimed = to_decimal(row.get("CCAClaimed", 0))
            close_ucc = to_decimal(row.get("ClosingUCC", 0))
            cca_cls = str(row.get("CCAClass") or "50")
            default_rate = 55 if cca_cls == "50" else (20 if cca_cls == "8" else 30)
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
                    str(row.get("BillerEntity") or "PC"),
                    cca_cls,
                    float(to_decimal(row.get("CCARatePct", default_rate))),
                    str(row.get("Description") or ""),
                    normalize_iso_date(row.get("AcquisitionDate"), "2026-11-01"),
                    float(orig_cost),
                    to_cents(orig_cost),
                    float(open_ucc),
                    to_cents(open_ucc),
                    float(adds),
                    to_cents(adds),
                    float(disps),
                    to_cents(disps),
                    1 if str(row.get("HalfYearRuleApplies", "1")) in ("1", "True", "true") else 0,
                    1 if str(row.get("ImmediateExpensingApplies", "0")) in ("1", "True", "true") else 0,
                    float(claimed),
                    to_cents(claimed),
                    float(close_ucc),
                    to_cents(close_ucc),
                    str(row.get("RolloverFromAssetID") or ""),
                    int(to_decimal(row.get("TaxYear", 2026))),
                    str(row.get("Notes") or ""),
                    str(row.get("CreatedAt") or now),
                    str(row.get("UpdatedAt") or now),
                ),
            )
        counts["cca_assets"] = len(cca_rows)

        # 4. Transaction Categories (with T2125 & GIFI Schedule 125 columns)
        cat_rows = _read_rows(TBL_TRANSACTION_CATEGORIES)
        for row in cat_rows:
            code = str(row.get("CategoryCode") or "").strip()
            if not code:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO transaction_categories (
                       category_code, category_name, type, class_scope, tax_flag_default,
                       billable_allowed, medical_eligible, deductible_eligible,
                       business_deductible_eligible, active, sort_order, notes,
                       t2125_line_number, t2125_line_label, gifi_schedule_125_code,
                       gifi_schedule_125_label, deductible_pct, itc_claimable_pct
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code,
                    str(row.get("CategoryName") or code),
                    str(row.get("Type") or "Expense"),
                    str(row.get("ClassScope") or "Both"),
                    str(row.get("TaxFlagDefault") or "None"),
                    1 if str(row.get("BillableAllowed", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("MedicalEligible", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("DeductibleEligible", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("BusinessDeductibleEligible", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("Active", "1")) in ("1", "True", "true") else 0,
                    int(to_decimal(row.get("SortOrder", 0))),
                    str(row.get("Notes") or ""),
                    str(row.get("T2125LineNumber") or ""),
                    str(row.get("T2125LineLabel") or ""),
                    str(row.get("GIFISchedule125Code") or ""),
                    str(row.get("GIFISchedule125Label") or ""),
                    float(to_decimal(row.get("DeductiblePct", 100))),
                    float(to_decimal(row.get("ITCClaimablePct", 100))),
                ),
            )
        counts["transaction_categories"] = len(cat_rows)

        # 5. Clients, ClientProfiles, Matters & MatterParties
        legacy_clients = _read_rows(TBL_CLIENTS)
        legacy_profiles = _read_rows(TBL_CLIENT_PROFILES)
        profile_by_cid: Dict[str, Dict[str, Any]] = {}
        for prow in legacy_profiles:
            pcid = str(prow.get("ClientID") or "").strip()
            if pcid:
                profile_by_cid[pcid] = prow

        client_id_map: Dict[str, str] = {}
        for row in legacy_clients:
            legacy_id = str(row.get("ClientID") or "").strip()
            name = str(row.get("ClientName") or "Unknown Client").strip()
            cid = legacy_id or generate_id("CLI")
            client_id_map[legacy_id] = cid
            client_id_map[name] = cid
            prow = profile_by_cid.get(cid, {})
            status_val = str(row.get("Status") or "Active").strip() or "Active"
            active_flag = 0 if str(row.get("Active", "1")).strip().lower() in ("0", "false", "no") else 1
            entity_type = str(row.get("EntityType") or prow.get("EntityType") or "Corporate").strip()
            addr = str(row.get("Address") or prow.get("FullAddress") or "").strip()
            primary_contact = str(row.get("PrimaryContact") or prow.get("PrincipalName") or "").strip()
            email = str(row.get("Email") or prow.get("PrimaryEmail") or "").strip()
            phone = str(row.get("Phone") or prow.get("PrimaryPhone") or "").strip()
            default_rate_dec = to_decimal(row.get("DefaultBillingRate") or prow.get("DefaultBillingRate") or 0)
            default_rate = float(default_rate_dec)
            default_rate_cents = to_cents(default_rate_dec)
            hst_exempt = 1 if str(row.get("HSTExempt") or prow.get("HSTExempt") or "0").strip().lower() in ("1", "true", "yes") else 0
            tax_exempt_reason = str(row.get("TaxExemptionReason") or prow.get("TaxExemptionReason") or "").strip()
            opening_date = normalize_iso_date(row.get("OpeningDate") or prow.get("OpeningDate") or prow.get("EngagementStartDate"))
            kyc_status = str(row.get("KYCStatus") or prow.get("KYCStatus") or "").strip()
            kyc_verified_date = normalize_iso_date(row.get("KYCVerifiedDate") or prow.get("KYCVerifiedDate"))
            kyc_method = str(row.get("KYCMethod") or prow.get("KYCMethod") or "").strip()
            kyc_notes = str(row.get("KYCNotes") or prow.get("KYCNotes") or "").strip()
            referred_by = str(row.get("ReferredBy") or prow.get("ReferredBy") or prow.get("ReferralFrom") or "").strip()
            referral_from = str(prow.get("ReferralFrom") or referred_by).strip()
            parent_id = str(row.get("ParentID") or prow.get("ParentClientID") or "").strip()
            parent_name = str(row.get("ParentName") or prow.get("ParentClientName") or "").strip()
            display_name = str(prow.get("DisplayName") or name).strip()
            legal_name = str(prow.get("LegalName") or display_name or name).strip()
            notes_val = str(prow.get("Notes") or row.get("Notes") or "").strip()

            conn.execute(
                """INSERT OR REPLACE INTO Client (
                       client_id, name, legal_name, display_name, entity_type,
                       primary_contact, address, email, phone,
                       default_billing_rate, default_billing_rate_cents,
                       hst_exempt, tax_exemption_reason, status, active,
                       opening_date, kyc_status, kyc_verified_date, kyc_method,
                       kyc_notes, referred_by, notes,
                       created_at, updated_at, legacy_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid, name, legal_name, display_name, entity_type,
                    primary_contact, addr, email, phone,
                    default_rate, default_rate_cents,
                    hst_exempt, tax_exempt_reason, status_val, active_flag,
                    opening_date, kyc_status, kyc_verified_date, kyc_method,
                    kyc_notes, referred_by, notes_val,
                    now, now, legacy_id or None,
                ),
            )

            conn.execute(
                """INSERT OR REPLACE INTO ClientProfile (
                       client_id, display_name, legal_name, first_name, middle_name, last_name,
                       entity_type, principal_name, principal_position,
                       primary_email, primary_phone,
                       secondary_contact_name, secondary_contact_position,
                       secondary_contact_email, secondary_contact_phone,
                       address_line1, address_line2, city, state_province, postal_code, country,
                       full_address, billing_address,
                       parent_client_id, parent_client_name,
                       website, tax_number, industry, billing_email,
                       default_billing_rate, default_billing_rate_cents,
                       hst_exempt, tax_exemption_reason,
                       kyc_status, kyc_verified_date, kyc_method, kyc_notes,
                       onboarding_status, retainer_required, retainer_amount,
                       engagement_start_date, opening_date, date_client_added, birthday,
                       referral_from, referred_by, conflict_notes, notes, payment_terms,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid, display_name, legal_name,
                    str(prow.get("FirstName") or "").strip(),
                    str(prow.get("MiddleName") or "").strip(),
                    str(prow.get("LastName") or "").strip(),
                    entity_type,
                    str(prow.get("PrincipalName") or primary_contact).strip(),
                    str(prow.get("PrincipalPosition") or "").strip(),
                    email, phone,
                    str(prow.get("SecondaryContactName") or "").strip(),
                    str(prow.get("SecondaryContactPosition") or "").strip(),
                    str(prow.get("SecondaryContactEmail") or "").strip(),
                    str(prow.get("SecondaryContactPhone") or "").strip(),
                    str(prow.get("AddressLine1") or "").strip(),
                    str(prow.get("AddressLine2") or "").strip(),
                    str(prow.get("City") or "").strip(),
                    str(prow.get("StateProvince") or "").strip(),
                    str(prow.get("PostalCode") or "").strip(),
                    str(prow.get("Country") or "").strip(),
                    addr, addr,
                    parent_id, parent_name,
                    str(prow.get("Website") or "").strip(),
                    str(prow.get("TaxID") or "").strip(),
                    str(prow.get("Industry") or "").strip(),
                    str(prow.get("BillingEmail") or email).strip(),
                    default_rate, default_rate_cents,
                    hst_exempt, tax_exempt_reason,
                    kyc_status, kyc_verified_date, kyc_method, kyc_notes,
                    str(prow.get("OnboardingStatus") or "").strip(),
                    1 if str(prow.get("RetainerRequired", "0")).strip().lower() in ("1", "true", "yes") else 0,
                    float(to_decimal(prow.get("RetainerAmount", 0))),
                    normalize_iso_date(prow.get("EngagementStartDate") or opening_date),
                    opening_date,
                    normalize_iso_date(prow.get("DateClientAdded") or opening_date),
                    normalize_iso_date(prow.get("Birthday")),
                    referral_from, referred_by,
                    str(prow.get("ConflictNotes") or "").strip(),
                    notes_val,
                    str(prow.get("PaymentTerms") or "Net 30"),
                    now, str(prow.get("UpdatedAt") or now),
                ),
            )
        counts["clients"] = len(legacy_clients)
        counts["client_profiles"] = len(legacy_clients)

        # Clean up any stale duplicate MEGA-CRP-26-0209 matter IDs before inserting
        conn.execute(
            "DELETE FROM Matter WHERE matter_number = 'MEGA-CRP-26-0209' AND matter_id != 'M_megatech_s86_2026'"
        )
        legacy_matters = _read_rows(TBL_MATTERS)
        matter_id_map: Dict[str, str] = {}
        for row in legacy_matters:
            mid = str(row.get("MatterID") or "").strip() or generate_id("MAT")
            matter_num = str(row.get("MatterNumber") or "").strip()
            legacy_client_id = str(row.get("ClientID") or row.get("ClientName") or "").strip()
            cid = client_id_map.get(legacy_client_id)
            if not cid:
                cid = legacy_client_id or generate_id("CLI")
                conn.execute(
                    "INSERT OR IGNORE INTO Client (client_id, name, status, created_at, updated_at, legacy_id) VALUES (?, ?, 'Active', ?, ?, ?)",
                    (cid, str(row.get("ClientName") or "Orphan Recovery Client"), now, now, legacy_client_id or None),
                )
                client_id_map[legacy_client_id] = cid
            matter_name = str(row.get("MatterName") or row.get("DisplayName") or row.get("Description") or "No Description").strip()
            display_name = str(row.get("DisplayName") or matter_name).strip()
            desc = str(row.get("Description") or display_name or matter_name or "No Description").strip()
            status_val = str(row.get("Status") or "Open").strip() or "Open"
            default_biller = str(row.get("DefaultBillerEntity") or row.get("DefaultBiller") or "SOLE_PROP").strip().upper() or "SOLE_PROP"
            referred_by = str(row.get("ReferredBy") or row.get("ReferralFrom") or "").strip()
            referral_from = str(row.get("ReferralFrom") or referred_by).strip()
            rep_mode = str(row.get("RepresentationMode") or "Single Client").strip()
            def_rate_dec = to_decimal(row.get("DefaultRate", row.get("HourlyRate", 0)))
            hr_rate_dec = to_decimal(row.get("HourlyRate", def_rate_dec))
            fee_est_dec = to_decimal(row.get("FeeEstimate", 0))
            kyc_completed = 1 if str(row.get("KYCCompleted", "0")).strip().lower() in ("1", "true", "yes") else 0
            open_date_val = normalize_iso_date(row.get("DateOpened") or row.get("OpenDate") or row.get("DateOfEngagement"))
            eng_date_val = normalize_iso_date(row.get("DateOfEngagement") or open_date_val)
            close_date_val = normalize_iso_date(row.get("DateClosed") or row.get("CloseDate"))
            joint_doc_val = str(row.get("JointEngagementDocument") or "").strip()
            conn.execute(
                """INSERT OR REPLACE INTO Matter (
                       matter_id, matter_number, matter_name, display_name,
                       client_id, client_name, parent_id, parent_name,
                       matter_type, practice_area, description, status,
                       responsible_lawyer, billing_arrangement, billing_contact, billing_email,
                       default_rate, default_rate_cents, hourly_rate, hourly_rate_cents,
                       fee_estimate, fee_estimate_cents, default_share_pct, rate_history,
                       date_of_engagement, date_opened, target_completion_date, date_closed,
                       court_file_number, opposing_party, referral_from, referred_by, notes,
                       representation_mode, joint_no_confidentiality_confirmed,
                       joint_instructions_require_all, joint_engagement_document,
                       default_biller, default_biller_entity, kyc_completed,
                       created_at, updated_at, legacy_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mid,
                    matter_num,
                    matter_name,
                    display_name,
                    cid,
                    str(row.get("ClientName") or "").strip(),
                    str(row.get("ParentID") or "").strip(),
                    str(row.get("ParentName") or "").strip(),
                    str(row.get("MatterType") or "General").strip(),
                    str(row.get("PracticeArea") or "").strip(),
                    desc,
                    status_val,
                    str(row.get("ResponsibleLawyer") or "").strip(),
                    str(row.get("BillingArrangement") or "Hourly").strip(),
                    str(row.get("BillingContact") or "").strip(),
                    str(row.get("BillingEmail") or "").strip(),
                    float(def_rate_dec),
                    to_cents(def_rate_dec),
                    float(hr_rate_dec),
                    to_cents(hr_rate_dec),
                    float(fee_est_dec),
                    to_cents(fee_est_dec),
                    float(to_decimal(row.get("DefaultSharePct", 100))),
                    str(row.get("RateHistory") or "[]").strip(),
                    eng_date_val,
                    open_date_val,
                    normalize_iso_date(row.get("TargetCompletionDate")),
                    close_date_val,
                    str(row.get("CourtFileNumber") or "").strip(),
                    str(row.get("OpposingParty") or "").strip(),
                    referral_from,
                    referred_by,
                    str(row.get("Notes") or "").strip(),
                    rep_mode,
                    1 if str(row.get("JointNoConfidentialityConfirmed", "0")).strip().lower() in ("1", "true", "yes") else 0,
                    1 if str(row.get("JointInstructionsRequireAll", "0")).strip().lower() in ("1", "true", "yes") else 0,
                    joint_doc_val,
                    default_biller,
                    default_biller,
                    kyc_completed,
                    now,
                    str(row.get("UpdatedAt") or now),
                    mid,
                ),
            )
            matter_id_map[mid] = mid
        counts["matters"] = len(legacy_matters)

        # 5b. Matter Parties
        conn.execute("DELETE FROM matter_parties")
        party_rows = _read_rows(TBL_MATTER_PARTIES)
        for idx, row in enumerate(party_rows, start=1):
            pid = str(row.get("MatterPartyID") or row.get("PartyID") or "").strip() or f"MP-{idx:05d}"
            mid = str(row.get("MatterID") or "").strip()
            if not mid:
                continue
            party_cid = str(row.get("ClientID") or row.get("PartyClientID") or "").strip()
            party_name = str(row.get("ClientName") or row.get("PartyName") or "").strip()
            party_role = str(row.get("Role") or row.get("PartyRole") or "").strip()
            is_anchor = 1 if str(row.get("IsFileAnchor", row.get("IsClientParty", "0"))).strip().lower() in ("1", "true", "yes") else 0
            is_billing = 1 if str(row.get("IsBillingRecipient", row.get("IsBillingParty", "0"))).strip().lower() in ("1", "true", "yes") else 0
            conn.execute(
                """INSERT OR REPLACE INTO matter_parties (
                       party_id, matter_id, client_id, client_name, party_role,
                       is_file_anchor, is_billing_recipient, fee_share_pct,
                       sort_order, notes, added_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pid,
                    mid,
                    party_cid,
                    party_name,
                    party_role,
                    is_anchor,
                    is_billing,
                    float(to_decimal(row.get("FeeSharePct", 100.0 if is_billing else 0.0))),
                    int(to_decimal(row.get("SortOrder", idx))),
                    str(row.get("Notes") or "").strip(),
                    str(row.get("CreatedAt") or row.get("UpdatedAt") or now),
                ),
            )
        counts["matter_parties"] = len(party_rows)

        # 6. Time Entries
        time_rows = _read_rows(TBL_TIME_ENTRIES)
        for idx, row in enumerate(time_rows, start=1):
            tid = str(row.get("EntryID") or "").strip() or f"TIM-{idx:05d}"
            mid = str(row.get("MatterID") or "").strip()
            if not mid or mid not in matter_id_map:
                mid = mid or "MAT-DEFAULT"
                if mid not in matter_id_map:
                    default_cid = next(iter(client_id_map.values()), "CLI-DEFAULT")
                    conn.execute(
                        "INSERT OR IGNORE INTO Client (client_id, name, status, created_at, updated_at) VALUES (?, 'Default Client', 'Active', ?, ?)",
                        (default_cid, now, now),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO Matter (matter_id, client_id, description, status, default_biller, created_at, updated_at) VALUES (?, ?, 'Default Matter', 'Open', 'PC', ?, ?)",
                        (mid, default_cid, now, now),
                    )
                    matter_id_map[mid] = mid
            date_iso = normalize_iso_date(row.get("Date"), "2026-01-01")
            hours = float(to_decimal(row.get("Hours", 0)))
            raw_seconds = int(to_decimal(row.get("RawSeconds", round(hours * 3600))))
            rate_dec = to_decimal(row.get("ClientRate", 0))
            share_pct = float(to_decimal(row.get("SharePct", 100)))
            gross_dec = to_decimal(row.get("GrossToClient", hours * float(rate_dec)))
            amt_you_dec = to_decimal(row.get("AmountToYou", gross_dec))
            hst_dec = to_decimal(row.get("HST", 0))
            tot_incl_dec = to_decimal(row.get("TotalInclHST", amt_you_dec + hst_dec))
            inv_ref = str(row.get("InvoiceRef") or "").strip()
            status = str(row.get("Status") or ("Billed" if inv_ref else "Unbilled"))
            entry_status = str(row.get("EntryStatus") or "SAVED").strip().upper() or "SAVED"
            started_at_utc = row.get("StartedAtUTC") or None
            last_heartbeat_utc = str(row.get("LastHeartbeatUTC") or now)
            legacy_sync_status = str(row.get("LegacyDocketsSyncStatus") or "SYNCED").strip().upper() or "SYNCED"
            legacy_synced_at = row.get("LegacyDocketsSyncedAt") or now
            legacy_row_sig = row.get("LegacyDocketsRowSignature") or None
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if inv_ref.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO TimeEntry (
                       time_id, matter_id, client_id, parent_id, date, hours, raw_seconds, rate, rate_cents,
                       share_pct, amount, amount_cents, amount_to_you, amount_to_you_cents,
                       hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                       description, status, entry_status, started_at_utc, last_heartbeat_utc,
                       legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                       is_billed, billed_invoice_id, biller_entity,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tid, mid, str(row.get("ClientID") or ""), str(row.get("ParentID") or ""),
                    date_iso, hours, raw_seconds, float(rate_dec), to_cents(rate_dec),
                    share_pct, float(gross_dec), to_cents(gross_dec),
                    float(amt_you_dec), to_cents(amt_you_dec),
                    float(hst_dec), to_cents(hst_dec),
                    float(tot_incl_dec), to_cents(tot_incl_dec),
                    str(row.get("Description") or ""), status,
                    entry_status, started_at_utc, last_heartbeat_utc,
                    legacy_sync_status, legacy_synced_at, legacy_row_sig,
                    1 if inv_ref else 0, inv_ref, biller, now, now
                ),
            )
            conn.execute(
                """INSERT OR REPLACE INTO time_entries (
                       entry_id, time_id, matter_id, client_id, parent_id, date, hours, raw_seconds, rate, rate_cents,
                       share_pct, amount, amount_cents, amount_to_you, amount_to_you_cents,
                       hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                       description, status, entry_status, started_at_utc, last_heartbeat_utc,
                       legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                       is_billed, billed_invoice_id, biller_entity,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tid, tid, mid, str(row.get("ClientID") or ""), str(row.get("ParentID") or ""),
                    date_iso, hours, raw_seconds, float(rate_dec), to_cents(rate_dec),
                    share_pct, float(gross_dec), to_cents(gross_dec),
                    float(amt_you_dec), to_cents(amt_you_dec),
                    float(hst_dec), to_cents(hst_dec),
                    float(tot_incl_dec), to_cents(tot_incl_dec),
                    str(row.get("Description") or ""), status,
                    entry_status, started_at_utc, last_heartbeat_utc,
                    legacy_sync_status, legacy_synced_at, legacy_row_sig,
                    1 if inv_ref else 0, inv_ref, biller, now, now
                ),
            )
        counts["time_entries"] = len(time_rows)

        # 7. Disbursements
        disb_rows = _read_rows(TBL_DISBURSEMENTS)
        for idx, row in enumerate(disb_rows, start=1):
            did = str(row.get("DisbursementID") or "").strip() or f"DSB-{idx:05d}"
            date_iso = normalize_iso_date(row.get("Date"), "2026-01-01")
            amt_dec = to_decimal(row.get("Amount", 0))
            inv_ref = str(row.get("InvoiceRef") or "").strip()
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if inv_ref.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO disbursements (
                       disbursement_id, date, client_name, sub_client, client_id, parent_id,
                       matter_id, description, amount, amount_cents, tax_exempt, bill_pct,
                       invoice_ref, payment_status, invoice_total, invoice_amount_paid,
                       invoice_balance_due, reissue_invoice_num, ap_bill_id, ap_allocation_id,
                       source_transaction_id, original_currency, original_amount, fx_rate,
                       supplier_invoice_ref, document_path, biller_entity, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    did, date_iso, str(row.get("ClientName") or ""), str(row.get("SubClient") or ""),
                    str(row.get("ClientID") or ""), str(row.get("ParentID") or ""),
                    str(row.get("MatterID") or ""), str(row.get("Description") or ""),
                    float(amt_dec), to_cents(amt_dec),
                    1 if str(row.get("TaxExempt", "0")) in ("1", "True", "true") else 0,
                    float(to_decimal(row.get("BillPct", 100))),
                    inv_ref, str(row.get("PaymentStatus") or ""),
                    str(row.get("InvoiceTotal") or ""), str(row.get("InvoiceAmountPaid") or ""),
                    str(row.get("InvoiceBalanceDue") or ""), str(row.get("ReissueInvoiceNum") or ""),
                    str(row.get("APBillID") or ""), str(row.get("APAllocationID") or ""),
                    str(row.get("SourceTransactionID") or ""), str(row.get("OriginalCurrency") or "CAD"),
                    float(to_decimal(row.get("OriginalAmount", amt_dec))),
                    float(to_decimal(row.get("FXRate", 1))),
                    str(row.get("SupplierInvoiceRef") or ""), str(row.get("DocumentPath") or ""),
                    biller, str(row.get("CreatedAt") or now)
                ),
            )
        counts["disbursements"] = len(disb_rows)

        # 8. Invoices (tblInvoiceLog) & Draft Invoices (tblDraftInvoices)
        inv_rows = _read_rows(TBL_INVOICE_LOG)
        for idx, row in enumerate(inv_rows, start=1):
            inv_num = str(row.get("InvoiceNum") or "").strip() or f"INV-{idx:05d}"
            cname = str(row.get("ClientName") or "Unknown Client")
            cid = client_id_map.get(cname) or "CLI-DEFAULT"
            conn.execute(
                "INSERT OR IGNORE INTO Client (client_id, name, status, created_at, updated_at) VALUES (?, ?, 'Active', ?, ?)",
                (cid, cname, now, now),
            )
            date_iso = normalize_iso_date(row.get("InvoiceDate"), "2026-01-01")
            fees_dec = to_decimal(row.get("TotalFees", 0))
            disb_dec = to_decimal(row.get("TotalDisbursements", 0))
            tax_dec = to_decimal(row.get("TotalTax", 0))
            agg_dec = to_decimal(row.get("AggregateBilled", fees_dec + disb_dec + tax_dec))
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if inv_num.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO Invoice (
                       invoice_id, invoice_num, client_id, client_name, sub_client,
                       date, total_fees, total_fees_cents, total_disbursements, total_disbursements_cents,
                       total_amount, total_amount_cents, tax_amount, tax_amount_cents,
                       status, bill_to_client, bill_to_snapshot, file_path,
                       biller_entity, biller_address_override, biller_hst_override,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Finalized', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    inv_num, inv_num, cid, cname, str(row.get("SubClient") or ""),
                    date_iso, float(fees_dec), to_cents(fees_dec),
                    float(disb_dec), to_cents(disb_dec),
                    float(agg_dec), to_cents(agg_dec),
                    float(tax_dec), to_cents(tax_dec),
                    str(row.get("BillToClient") or ""), str(row.get("BillToSnapshot") or ""),
                    str(row.get("FilePath") or ""), biller,
                    str(row.get("BillerAddressOverride") or ""),
                    str(row.get("BillerHSTOverride") or ""),
                    now, now
                ),
            )
        counts["invoices"] = len(inv_rows)

        draft_rows = _read_rows(TBL_DRAFT_INVOICES)
        for idx, row in enumerate(draft_rows, start=1):
            did = str(row.get("DraftID") or "").strip() or f"DRF-{idx:05d}"
            inv_num = str(row.get("InvoiceNum") or "")
            date_iso = normalize_iso_date(row.get("Date"), "2026-01-01")
            fees_dec = to_decimal(row.get("TotalFees", 0))
            disb_dec = to_decimal(row.get("TotalDisbursements", 0))
            tax_dec = to_decimal(row.get("TotalTax", 0))
            due_dec = to_decimal(row.get("TotalDue", 0))
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if inv_num.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO draft_invoices (
                       draft_id, invoice_num, client_id, client_name, date,
                       discount_type, discount_value, agency_split_percent,
                       total_fees, total_fees_cents, total_disbursements, total_disbursements_cents,
                       total_tax, total_tax_cents, total_due, total_due_cents,
                       grouping_pref, is_flat_fee, flat_fee_desc, flat_fee_amount,
                       reconciliation_mode, show_total_hours, custom_sort_order,
                       reissue_invoice_num, bill_to_snapshot,
                       biller_entity, biller_address_override, biller_hst_override,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    did, inv_num, str(row.get("ClientID") or ""), str(row.get("ClientName") or ""),
                    date_iso, str(row.get("DiscountType") or ""),
                    float(to_decimal(row.get("DiscountValue", 0))),
                    float(to_decimal(row.get("AgencySplitPercent", 100))),
                    float(fees_dec), to_cents(fees_dec),
                    float(disb_dec), to_cents(disb_dec),
                    float(tax_dec), to_cents(tax_dec),
                    float(due_dec), to_cents(due_dec),
                    str(row.get("GroupingPref") or ""),
                    1 if str(row.get("IsFlatFee", "0")) in ("1", "True", "true") else 0,
                    str(row.get("FlatFeeDesc") or ""),
                    float(to_decimal(row.get("FlatFeeAmount", 0))),
                    1 if str(row.get("ReconciliationMode", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("ShowTotalHours", "1")) in ("1", "True", "true") else 0,
                    str(row.get("CustomSortOrder") or ""),
                    str(row.get("ReissueInvoiceNum") or ""),
                    str(row.get("BillToSnapshot") or ""),
                    biller,
                    str(row.get("BillerAddressOverride") or ""),
                    str(row.get("BillerHSTOverride") or ""),
                    str(row.get("CreatedAt") or now),
                    str(row.get("UpdatedAt") or now),
                ),
            )
        counts["draft_invoices"] = len(draft_rows)

        # 9. Receivables & Ledger
        recv_rows = _read_rows(TBL_RECEIVABLES)
        for idx, row in enumerate(recv_rows, start=1):
            inv_num = str(row.get("InvoiceNum") or f"RCV-{idx:05d}").strip()
            rid = f"RCV-{idx:05d}-{inv_num}"
            date_iso = normalize_iso_date(row.get("Date"), "2026-01-01")
            tot_dec = to_decimal(row.get("TotalInvoiced", 0))
            paid_dec = to_decimal(row.get("AmountPaid", 0))
            cred_dec = to_decimal(row.get("CreditsAdj", 0))
            due_dec = to_decimal(row.get("BalanceDue", tot_dec - paid_dec - cred_dec))
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if inv_num.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO Receivable (
                       receivable_id, invoice_id, client_name, work_client, date,
                       total_invoiced, total_invoiced_cents, amount_due, amount_due_cents,
                       amount_paid, amount_paid_cents, credits_adj, credits_adj_cents,
                       status, biller_entity, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid, inv_num, str(row.get("Client") or ""), str(row.get("WorkClient") or ""),
                    date_iso, float(tot_dec), to_cents(tot_dec),
                    float(due_dec), to_cents(due_dec),
                    float(paid_dec), to_cents(paid_dec),
                    float(cred_dec), to_cents(cred_dec),
                    str(row.get("Status") or "Unpaid"), biller, now, now
                ),
            )
        counts["receivables"] = len(recv_rows)

        ledger_rows = _read_rows(TBL_LEDGER)
        for idx, row in enumerate(ledger_rows, start=1):
            lid = str(row.get("LedgerID") or f"LDG-{idx:05d}").strip()
            date_iso = normalize_iso_date(row.get("Date"), "2026-01-01")
            ref = str(row.get("Reference") or "")
            b_dec = to_decimal(row.get("BillingsExclHST", 0))
            hc_dec = to_decimal(row.get("HSTCollected", 0))
            e_dec = to_decimal(row.get("ExpensesExclHST", 0))
            hp_dec = to_decimal(row.get("HSTPaid", 0))
            c_dec = to_decimal(row.get("Collected", 0))
            w_dec = to_decimal(row.get("WriteOff", 0))
            r_dec = to_decimal(row.get("Receivable", 0))
            biller = str(row.get("BillerEntity") or "").strip().upper() or (
                "PC" if ref.endswith("-PC") else infer_biller_from_date(date_iso)
            )
            conn.execute(
                """INSERT OR REPLACE INTO ledger (
                       ledger_id, date, client_vendor, description, category, reference,
                       billings_excl_hst, billings_excl_hst_cents, hst_collected, hst_collected_cents,
                       expenses_excl_hst, expenses_excl_hst_cents, hst_paid, hst_paid_cents,
                       collected, collected_cents, write_off, write_off_cents,
                       receivable, receivable_cents, trx_id, external_ref_id,
                       original_amount, work_client, biller_entity, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lid, date_iso, str(row.get("ClientVendor") or ""),
                    str(row.get("Description") or ""), str(row.get("Category") or ""), ref,
                    float(b_dec), to_cents(b_dec), float(hc_dec), to_cents(hc_dec),
                    float(e_dec), to_cents(e_dec), float(hp_dec), to_cents(hp_dec),
                    float(c_dec), to_cents(c_dec), float(w_dec), to_cents(w_dec),
                    float(r_dec), to_cents(r_dec), str(row.get("TrxID") or ""),
                    str(row.get("ExternalRefID") or ""),
                    float(to_decimal(row.get("OriginalAmount", 0))),
                    str(row.get("WorkClient") or ""), biller, str(row.get("CreatedAt") or now)
                ),
            )
        counts["ledger"] = len(ledger_rows)

        # 10. TransactionsMaster & APBills
        txn_rows = _read_rows(TBL_TRANSACTIONS_MASTER)
        for idx, row in enumerate(txn_rows, start=1):
            tid = str(row.get("TransactionID") or f"TXN-{idx:05d}").strip()
            date_iso = normalize_iso_date(row.get("TxnDate"), "2026-01-01")
            amt_dec = to_decimal(row.get("Amount", 0))
            tax_dec = to_decimal(row.get("TaxAmount", 0))
            claim_dec = to_decimal(row.get("TotalClaimAmount", 0))
            biller = str(row.get("BillerEntity") or "").strip().upper() or infer_biller_from_date(date_iso)
            conn.execute(
                """INSERT OR REPLACE INTO TransactionMaster (
                       transaction_id, date, class, business_unit, type, account, to_account,
                       payee, parent, client, matter, category_code, category_name, member,
                       amount, amount_cents, tax_amount, tax_amount_cents, tax_flag,
                       hst_exempt, general_office_expense, shadow, invoice_ref,
                       bill_claim_pct, total_claim_amount, total_claim_amount_cents,
                       description, notes, status, currency, biller_entity,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tid, date_iso, str(row.get("Class") or "Business"),
                    str(row.get("BusinessUnit") or "Cory Legal"),
                    str(row.get("Type") or "Expense"),
                    str(row.get("FromAccount") or ""), str(row.get("ToAccount") or ""),
                    str(row.get("Payee") or ""), str(row.get("Parent") or ""),
                    str(row.get("Client") or ""), str(row.get("Matter") or ""),
                    str(row.get("CategoryCode") or ""), str(row.get("CategoryName") or ""),
                    str(row.get("Member") or "Cory"),
                    float(amt_dec), to_cents(amt_dec),
                    float(tax_dec), to_cents(tax_dec),
                    str(row.get("TaxFlag") or "None"),
                    1 if str(row.get("HSTExempt", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("GeneralOfficeExpense", "0")) in ("1", "True", "true") else 0,
                    1 if str(row.get("Shadow", "0")) in ("1", "True", "true") else 0,
                    str(row.get("InvoiceRef") or ""),
                    float(to_decimal(row.get("BillClaimPct", 0))),
                    float(claim_dec), to_cents(claim_dec),
                    str(row.get("ExpenseDetails") or ""), str(row.get("Notes") or ""),
                    str(row.get("Status") or "Posted"), str(row.get("Currency") or "CAD"),
                    biller, str(row.get("CreatedAt") or now), str(row.get("UpdatedAt") or now)
                ),
            )
        counts["transactions_master"] = len(txn_rows)

        ap_rows = _read_rows(AP_BILLS_TABLE)
        for idx, row in enumerate(ap_rows, start=1):
            apid = str(row.get("APBillID") or f"APB-{idx:05d}").strip()
            date_iso = normalize_iso_date(row.get("InvoiceDate"), "2026-01-01")
            sub_dec = to_decimal(row.get("Subtotal", 0))
            tax_dec = to_decimal(row.get("TaxAmount", 0))
            tot_dec = to_decimal(row.get("Total", sub_dec + tax_dec))
            paid_dec = to_decimal(row.get("AmountPaid", 0))
            bal_dec = to_decimal(row.get("Balance", tot_dec - paid_dec))
            biller = str(row.get("BillerEntity") or "").strip().upper() or infer_biller_from_date(date_iso)
            conn.execute(
                """INSERT OR REPLACE INTO AccountsPayable (
                       ap_id, vendor_name, vendor_invoice_number, date, due_date,
                       subtotal, subtotal_cents, tax_amount, tax_amount_cents,
                       amount, amount_cents, amount_paid, amount_paid_cents,
                       balance, balance_cents, status, currency, expense_transaction_id,
                       expense_treatment, category_code, category_name, source_account,
                       matter_id, client_id, disbursement_id, biller_entity, notes,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    apid, str(row.get("Vendor") or ""), str(row.get("VendorInvoiceNumber") or ""),
                    date_iso, normalize_iso_date(row.get("DueDate")),
                    float(sub_dec), to_cents(sub_dec),
                    float(tax_dec), to_cents(tax_dec),
                    float(tot_dec), to_cents(tot_dec),
                    float(paid_dec), to_cents(paid_dec),
                    float(bal_dec), to_cents(bal_dec),
                    str(row.get("Status") or "Unpaid"), str(row.get("Currency") or "CAD"),
                    str(row.get("ExpenseTransactionID") or ""),
                    str(row.get("ExpenseTreatment") or ""),
                    str(row.get("CategoryCode") or ""), str(row.get("CategoryName") or ""),
                    str(row.get("SourceAccount") or ""), str(row.get("MatterID") or ""),
                    str(row.get("ClientID") or ""), str(row.get("DisbursementID") or ""),
                    biller, str(row.get("Notes") or ""),
                    str(row.get("CreatedAt") or now), str(row.get("UpdatedAt") or now)
                ),
            )
        counts["ap_bills"] = len(ap_rows)

        # 11. HST Log
        hst_rows = _read_rows(TBL_HST_LOG)
        for idx, row in enumerate(hst_rows, start=1):
            pid = str(row.get("PeriodID") or f"HST-{idx:04d}").strip()
            p_start = normalize_iso_date(row.get("PeriodStart"), "2026-01-01")
            p_end = normalize_iso_date(row.get("PeriodEnd"), "2026-12-31")
            net_dec = to_decimal(row.get("NetTax", 0))
            l101 = to_decimal(row.get("Line101Sales", 0))
            l103 = to_decimal(row.get("Line103HSTCollected", 0))
            l104 = to_decimal(row.get("Line104Adjustments", 0))
            l105 = to_decimal(row.get("Line105TotalHST", l103 + l104))
            l106 = to_decimal(row.get("Line106ITCs", 0))
            l107 = to_decimal(row.get("Line107ITCAdjustments", 0))
            l108 = to_decimal(row.get("Line108TotalITCs", l106 + l107))
            l110 = to_decimal(row.get("Line110Instalments", 0))
            l113 = to_decimal(row.get("Line113Balance", net_dec - l110))
            biller = str(row.get("BillerEntity") or "").strip().upper() or infer_biller_from_date(p_start)
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
                    pid, p_start, p_end, normalize_iso_date(row.get("FiledDate")),
                    str(row.get("ConfNum") or ""), float(net_dec), to_cents(net_dec),
                    normalize_iso_date(row.get("PaidDate")), str(row.get("PaymentRef") or ""),
                    biller, float(l101), to_cents(l101), float(l103), to_cents(l103),
                    float(l104), to_cents(l104), float(l105), to_cents(l105),
                    float(l106), to_cents(l106), float(l107), to_cents(l107),
                    float(l108), to_cents(l108), float(l110), to_cents(l110),
                    float(l113), to_cents(l113), str(row.get("Status") or "Filed"),
                    str(row.get("Notes") or "")
                ),
            )
        counts["hst_log"] = len(hst_rows)

        # 12. Corporate Entities, Relationships & Share Transactions (Firm Corporate Records Only)
        conn.execute("DELETE FROM corp_entities")
        conn.execute("DELETE FROM corp_relationships")
        conn.execute("DELETE FROM corp_transactions")
        corp_entities = [
            row
            for row in _read_rows(TBL_CORP_ENTITIES)
            if "MEGATECH" not in str(row.get("LegalName") or "").upper()
            and "HAMILTON" not in str(row.get("LegalName") or "").upper()
            and str(row.get("ClientID") or "").strip().upper() not in ("MEGA", "HAMI")
        ]
        for row in corp_entities:
            eid = str(row.get("EntityID") or "").strip() or generate_id("ENT")
            conn.execute(
                """INSERT OR REPLACE INTO corp_entities (
                       entity_id, client_id, legal_name, jurisdiction, incorporation_date,
                       incorporation_number, fiscal_year_end, status, notes, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    eid, str(row.get("ClientID") or ""), str(row.get("LegalName") or ""),
                    str(row.get("Jurisdiction") or "Ontario (OBCA)"),
                    normalize_iso_date(row.get("IncorporationDate")),
                    str(row.get("IncorporationNumber") or ""),
                    str(row.get("FiscalYearEnd") or ""),
                    str(row.get("Status") or "Active"),
                    str(row.get("Notes") or ""),
                    str(row.get("CreatedAt") or now),
                ),
            )
        counts["corp_entities"] = len(corp_entities)

        corp_rels = [
            row
            for row in _read_rows(TBL_CORP_RELATIONSHIPS)
            if not str(row.get("RelationshipID") or "").upper().startswith("CR-MEGA")
        ]
        for row in corp_rels:
            rid = str(row.get("RelationshipID") or "").strip() or generate_id("REL")
            conn.execute(
                """INSERT OR REPLACE INTO corp_relationships (
                       relationship_id, source_entity_id, target_entity_id, relationship_type,
                       title, share_class, shares_held, ownership_percentage,
                       start_date, end_date, active
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid, str(row.get("SourceEntityID") or ""),
                    str(row.get("TargetEntityID") or ""),
                    str(row.get("RelationshipType") or ""),
                    str(row.get("Title") or ""),
                    str(row.get("ShareClass") or ""),
                    float(to_decimal(row.get("SharesHeld", 0))),
                    float(to_decimal(row.get("OwnershipPercentage", 0))),
                    normalize_iso_date(row.get("StartDate")),
                    normalize_iso_date(row.get("EndDate")),
                    1 if str(row.get("Active", "1")) in ("1", "True", "true") else 0,
                ),
            )
        counts["corp_relationships"] = len(corp_rels)

        corp_txns = [
            row
            for row in _read_rows(TBL_CORP_TRANSACTIONS)
            if not str(row.get("TransactionID") or "").upper().startswith("CT-MEGA")
        ]
        for row in corp_txns:
            ctid = str(row.get("TransactionID") or "").strip() or generate_id("CTX")
            tot_val = to_decimal(row.get("TotalValue", 0))
            conn.execute(
                """INSERT OR REPLACE INTO corp_transactions (
                       transaction_id, entity_id, date, transaction_type,
                       from_entity_id, to_entity_id, share_class,
                       number_of_shares, price_per_share, total_value, total_value_cents,
                       document_reference, notes, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ctid, str(row.get("EntityID") or ""),
                    normalize_iso_date(row.get("Date"), "2026-10-17"),
                    str(row.get("TransactionType") or ""),
                    str(row.get("FromEntityID") or ""),
                    str(row.get("ToEntityID") or ""),
                    str(row.get("ShareClass") or ""),
                    float(to_decimal(row.get("NumberOfShares", 0))),
                    float(to_decimal(row.get("PricePerShare", 0))),
                    float(tot_val), to_cents(tot_val),
                    str(row.get("DocumentReference") or ""),
                    str(row.get("Notes") or ""),
                    str(row.get("CreatedAt") or now),
                ),
            )
        counts["corp_transactions"] = len(corp_txns)

        conn.commit()
        logger.info("Dry-run Migration completed successfully: %s", counts)
        return {"ok": True, "counts": counts}

    except Exception as e:
        conn.rollback()
        logger.error("Migration Failed! Rolled back completely. Reason: %s", e)
        raise e
    finally:
        close_connection()


class SQLiteMigrator:
    """Object-oriented wrapper around perform_dry_run_migration."""

    def __init__(
        self,
        cspm_path: Optional[Path] = None,
        dockets_path: Optional[Path] = None,
        sqlite_path: Optional[Path] = None,
    ):
        self.cspm_path = Path(cspm_path) if cspm_path else None
        self.dockets_path = Path(dockets_path) if dockets_path else None
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None

    def run_migration(self) -> Dict[str, Any]:
        if self.sqlite_path is not None:
            proto_dir = self.sqlite_path.parent if self.sqlite_path.suffix else self.sqlite_path
            os.environ["CSPM_PROTOTYPE_ROOT"] = str(proto_dir)
        return perform_dry_run_migration(self.cspm_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("--- Executing Production Migration Dry-Run ---")
    perform_dry_run_migration()

