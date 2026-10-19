-- PROVISIONAL REPRESENTATIVE PROTOTYPE SCHEMA
-- NOT APPROVED FOR PRODUCTION MIGRATION
-- Production SQLite Schema for CSPM (Dual-Schema Parity v3)

-- Enforce strict constraints
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

-- 1. Entities Domain
CREATE TABLE IF NOT EXISTS Client (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT DEFAULT '',
    display_name TEXT DEFAULT '',
    entity_type TEXT DEFAULT 'Corporation',
    primary_contact TEXT DEFAULT '',
    address TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    default_billing_rate REAL DEFAULT 0.0,
    default_billing_rate_cents INTEGER DEFAULT 0,
    hst_exempt INTEGER DEFAULT 0,
    tax_exemption_reason TEXT DEFAULT '',
    status TEXT DEFAULT 'Active',
    active INTEGER DEFAULT 1,
    opening_date TEXT DEFAULT '',
    kyc_status TEXT DEFAULT 'Pending',
    kyc_verified_date TEXT DEFAULT '',
    kyc_method TEXT DEFAULT '',
    kyc_notes TEXT DEFAULT '',
    referred_by TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_id TEXT
);

CREATE TABLE IF NOT EXISTS ClientProfile (
    client_id TEXT PRIMARY KEY,
    display_name TEXT DEFAULT '',
    legal_name TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    middle_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    entity_type TEXT DEFAULT 'Corporation',
    principal_name TEXT DEFAULT '',
    principal_position TEXT DEFAULT '',
    primary_email TEXT DEFAULT '',
    primary_phone TEXT DEFAULT '',
    secondary_contact_name TEXT DEFAULT '',
    secondary_contact_position TEXT DEFAULT '',
    secondary_contact_email TEXT DEFAULT '',
    secondary_contact_phone TEXT DEFAULT '',
    address_line1 TEXT DEFAULT '',
    address_line2 TEXT DEFAULT '',
    city TEXT DEFAULT '',
    state_province TEXT DEFAULT '',
    postal_code TEXT DEFAULT '',
    country TEXT DEFAULT '',
    full_address TEXT DEFAULT '',
    billing_address TEXT DEFAULT '',
    parent_client_id TEXT DEFAULT '',
    parent_client_name TEXT DEFAULT '',
    website TEXT DEFAULT '',
    tax_number TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    billing_email TEXT DEFAULT '',
    default_billing_rate REAL DEFAULT 0.0,
    default_billing_rate_cents INTEGER DEFAULT 0,
    hst_exempt INTEGER DEFAULT 0,
    tax_exemption_reason TEXT DEFAULT '',
    kyc_status TEXT DEFAULT 'Pending',
    kyc_verified_date TEXT DEFAULT '',
    kyc_method TEXT DEFAULT '',
    kyc_notes TEXT DEFAULT '',
    onboarding_status TEXT DEFAULT 'Prospect',
    retainer_required INTEGER DEFAULT 0,
    retainer_amount REAL DEFAULT 0.0,
    engagement_start_date TEXT DEFAULT '',
    opening_date TEXT DEFAULT '',
    date_client_added TEXT DEFAULT '',
    birthday TEXT DEFAULT '',
    referral_from TEXT DEFAULT '',
    referred_by TEXT DEFAULT '',
    conflict_notes TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    payment_terms TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE CASCADE
);

-- 2. Matters Domain
CREATE TABLE IF NOT EXISTS Matter (
    matter_id TEXT PRIMARY KEY,
    matter_number TEXT DEFAULT '',
    matter_name TEXT DEFAULT '',
    display_name TEXT DEFAULT '',
    client_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    parent_name TEXT DEFAULT '',
    matter_type TEXT DEFAULT 'General',
    practice_area TEXT DEFAULT '',
    description TEXT NOT NULL,
    status TEXT DEFAULT 'Active',
    responsible_lawyer TEXT DEFAULT '',
    billing_arrangement TEXT DEFAULT 'Hourly',
    billing_contact TEXT DEFAULT '',
    billing_email TEXT DEFAULT '',
    default_rate REAL DEFAULT 0.0,
    default_rate_cents INTEGER DEFAULT 0,
    hourly_rate REAL DEFAULT 0.0,
    hourly_rate_cents INTEGER DEFAULT 0,
    fee_estimate REAL DEFAULT 0.0,
    fee_estimate_cents INTEGER DEFAULT 0,
    default_share_pct REAL DEFAULT 100.0,
    rate_history TEXT DEFAULT '[]',
    date_of_engagement TEXT DEFAULT '',
    date_opened TEXT DEFAULT '',
    target_completion_date TEXT DEFAULT '',
    date_closed TEXT DEFAULT '',
    court_file_number TEXT DEFAULT '',
    opposing_party TEXT DEFAULT '',
    referral_from TEXT DEFAULT '',
    referred_by TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    representation_mode TEXT DEFAULT 'Single Client',
    joint_no_confidentiality_confirmed INTEGER DEFAULT 0,
    joint_instructions_require_all INTEGER DEFAULT 0,
    joint_engagement_document TEXT DEFAULT '',
    default_biller TEXT DEFAULT 'SOLE_PROP',
    default_biller_entity TEXT DEFAULT 'SOLE_PROP',
    kyc_completed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_id TEXT,
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS matter_parties (
    party_id TEXT PRIMARY KEY,
    matter_id TEXT NOT NULL,
    client_id TEXT DEFAULT '',
    client_name TEXT NOT NULL,
    party_role TEXT NOT NULL,
    is_file_anchor INTEGER DEFAULT 0,
    is_billing_recipient INTEGER DEFAULT 0,
    fee_share_pct REAL DEFAULT 0.0,
    sort_order INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    added_at TEXT DEFAULT '',
    FOREIGN KEY (matter_id) REFERENCES Matter(matter_id) ON DELETE CASCADE
);

-- 3. Time & Tasks Domain
CREATE TABLE IF NOT EXISTS TimeEntry (
    time_id TEXT PRIMARY KEY,
    matter_id TEXT NOT NULL,
    matter_name TEXT DEFAULT '',
    client_id TEXT,
    client_name TEXT DEFAULT '',
    parent_id TEXT,
    date TEXT NOT NULL,
    hours REAL NOT NULL,
    raw_seconds INTEGER NOT NULL DEFAULT 0,
    rate REAL NOT NULL,
    rate_cents INTEGER DEFAULT 0,
    share_pct REAL DEFAULT 100.0,
    amount REAL NOT NULL, -- Statically captured formula value to prevent float drift
    amount_cents INTEGER DEFAULT 0,
    amount_to_you REAL DEFAULT 0.0,
    amount_to_you_cents INTEGER DEFAULT 0,
    hst REAL DEFAULT 0.0,
    hst_cents INTEGER DEFAULT 0,
    total_incl_hst REAL DEFAULT 0.0,
    total_incl_hst_cents INTEGER DEFAULT 0,
    description TEXT,
    status TEXT DEFAULT 'Unbilled',
    entry_status TEXT NOT NULL DEFAULT 'SAVED',
    started_at_utc TEXT,
    last_heartbeat_utc TEXT,
    legacy_dockets_sync_status TEXT NOT NULL DEFAULT 'PENDING_SYNC',
    legacy_dockets_synced_at TEXT,
    legacy_dockets_row_signature TEXT,
    is_billed INTEGER DEFAULT 0,
    billed_invoice_id TEXT,
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (matter_id) REFERENCES Matter(matter_id) ON DELETE RESTRICT
    -- billed_invoice_id is intentionally unconstrained to allow invoice deletion without cascading time deletion
);

CREATE TABLE IF NOT EXISTS time_entries (
    entry_id TEXT PRIMARY KEY,
    time_id TEXT,
    matter_id TEXT DEFAULT '',
    matter_name TEXT DEFAULT '',
    client_id TEXT DEFAULT '',
    client_name TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    date TEXT NOT NULL,
    hours REAL NOT NULL DEFAULT 0.0,
    raw_seconds INTEGER NOT NULL DEFAULT 0,
    rate REAL NOT NULL DEFAULT 0.0,
    rate_cents INTEGER DEFAULT 0,
    share_pct REAL DEFAULT 100.0,
    amount REAL NOT NULL DEFAULT 0.0,
    amount_cents INTEGER DEFAULT 0,
    amount_to_you REAL DEFAULT 0.0,
    amount_to_you_cents INTEGER DEFAULT 0,
    hst REAL DEFAULT 0.0,
    hst_cents INTEGER DEFAULT 0,
    total_incl_hst REAL DEFAULT 0.0,
    total_incl_hst_cents INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'Unbilled',
    entry_status TEXT NOT NULL DEFAULT 'SAVED',
    started_at_utc TEXT,
    last_heartbeat_utc TEXT,
    legacy_dockets_sync_status TEXT NOT NULL DEFAULT 'PENDING_SYNC',
    legacy_dockets_synced_at TEXT,
    legacy_dockets_row_signature TEXT,
    is_billed INTEGER DEFAULT 0,
    billed_invoice_id TEXT DEFAULT '',
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 4. Billing Domain
CREATE TABLE IF NOT EXISTS Invoice (
    invoice_id TEXT PRIMARY KEY,
    invoice_num TEXT,
    client_id TEXT NOT NULL,
    client_name TEXT,
    sub_client TEXT,
    matter_id TEXT,
    date TEXT NOT NULL,
    total_fees REAL DEFAULT 0.0,
    total_fees_cents INTEGER DEFAULT 0,
    total_disbursements REAL DEFAULT 0.0,
    total_disbursements_cents INTEGER DEFAULT 0,
    total_amount REAL NOT NULL,
    total_amount_cents INTEGER DEFAULT 0,
    tax_amount REAL DEFAULT 0.0,
    tax_amount_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Draft',
    bill_to_client TEXT,
    bill_to_snapshot TEXT,
    file_path TEXT,
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    biller_address_override TEXT DEFAULT '',
    biller_hst_override TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS draft_invoices (
    draft_id TEXT PRIMARY KEY,
    invoice_num TEXT,
    client_id TEXT,
    client_name TEXT,
    date TEXT,
    discount_type TEXT,
    discount_value REAL DEFAULT 0.0,
    agency_split_percent REAL DEFAULT 100.0,
    total_fees REAL DEFAULT 0.0,
    total_fees_cents INTEGER DEFAULT 0,
    total_disbursements REAL DEFAULT 0.0,
    total_disbursements_cents INTEGER DEFAULT 0,
    total_tax REAL DEFAULT 0.0,
    total_tax_cents INTEGER DEFAULT 0,
    total_due REAL DEFAULT 0.0,
    total_due_cents INTEGER DEFAULT 0,
    grouping_pref TEXT,
    is_flat_fee INTEGER DEFAULT 0,
    flat_fee_desc TEXT,
    flat_fee_amount REAL DEFAULT 0.0,
    reconciliation_mode INTEGER DEFAULT 0,
    show_total_hours INTEGER DEFAULT 1,
    custom_sort_order TEXT,
    reissue_invoice_num TEXT,
    bill_to_snapshot TEXT,
    biller_entity TEXT DEFAULT 'PC',
    biller_address_override TEXT DEFAULT '',
    biller_hst_override TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS Receivable (
    receivable_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    client_name TEXT,
    work_client TEXT,
    date TEXT,
    total_invoiced REAL DEFAULT 0.0,
    total_invoiced_cents INTEGER DEFAULT 0,
    amount_due REAL NOT NULL,
    amount_due_cents INTEGER DEFAULT 0,
    amount_paid REAL DEFAULT 0.0,
    amount_paid_cents INTEGER DEFAULT 0,
    credits_adj REAL DEFAULT 0.0,
    credits_adj_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Unpaid',
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS disbursements (
    disbursement_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    client_name TEXT,
    sub_client TEXT,
    client_id TEXT,
    parent_id TEXT,
    matter_id TEXT,
    description TEXT,
    amount REAL DEFAULT 0.0,
    amount_cents INTEGER DEFAULT 0,
    tax_exempt INTEGER DEFAULT 0,
    bill_pct REAL DEFAULT 100.0,
    invoice_ref TEXT,
    payment_status TEXT,
    invoice_total TEXT,
    invoice_amount_paid TEXT,
    invoice_balance_due TEXT,
    reissue_invoice_num TEXT,
    ap_bill_id TEXT,
    ap_allocation_id TEXT,
    source_transaction_id TEXT,
    original_currency TEXT DEFAULT 'CAD',
    original_amount REAL DEFAULT 0.0,
    fx_rate REAL DEFAULT 1.0,
    supplier_invoice_ref TEXT,
    document_path TEXT,
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT
);

-- 5. Payables Domain
CREATE TABLE IF NOT EXISTS AccountsPayable (
    ap_id TEXT PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    vendor_invoice_number TEXT,
    date TEXT NOT NULL,
    due_date TEXT,
    subtotal REAL DEFAULT 0.0,
    subtotal_cents INTEGER DEFAULT 0,
    tax_amount REAL DEFAULT 0.0,
    tax_amount_cents INTEGER DEFAULT 0,
    amount REAL NOT NULL,
    amount_cents INTEGER DEFAULT 0,
    amount_paid REAL DEFAULT 0.0,
    amount_paid_cents INTEGER DEFAULT 0,
    balance REAL DEFAULT 0.0,
    balance_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Unpaid',
    currency TEXT DEFAULT 'CAD',
    expense_transaction_id TEXT,
    expense_treatment TEXT,
    category_code TEXT,
    category_name TEXT,
    source_account TEXT,
    matter_id TEXT,
    client_id TEXT,
    disbursement_id TEXT,
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 6. Ledger & Transactions Domain
CREATE TABLE IF NOT EXISTS TransactionMaster (
    transaction_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    class TEXT DEFAULT 'Business',
    business_unit TEXT DEFAULT 'Cory Legal',
    type TEXT NOT NULL, -- e.g., 'Expense', 'Income', 'Transfer', 'Debt Repayment'
    account TEXT NOT NULL,
    to_account TEXT DEFAULT '',
    payee TEXT DEFAULT '',
    parent TEXT DEFAULT '',
    client TEXT DEFAULT '',
    matter TEXT DEFAULT '',
    category_code TEXT DEFAULT '',
    category_name TEXT DEFAULT '',
    member TEXT DEFAULT 'Cory',
    amount REAL NOT NULL,
    amount_cents INTEGER DEFAULT 0,
    tax_amount REAL DEFAULT 0.0,
    tax_amount_cents INTEGER DEFAULT 0,
    tax_flag TEXT DEFAULT 'None',
    hst_exempt INTEGER DEFAULT 0,
    general_office_expense INTEGER DEFAULT 0,
    shadow INTEGER DEFAULT 0,
    invoice_ref TEXT DEFAULT '',
    bill_claim_pct REAL DEFAULT 0.0,
    total_claim_amount REAL DEFAULT 0.0,
    total_claim_amount_cents INTEGER DEFAULT 0,
    description TEXT,
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'Posted',
    currency TEXT DEFAULT 'CAD',
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    ledger_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    client_vendor TEXT,
    description TEXT,
    category TEXT,
    reference TEXT,
    billings_excl_hst REAL DEFAULT 0.0,
    billings_excl_hst_cents INTEGER DEFAULT 0,
    hst_collected REAL DEFAULT 0.0,
    hst_collected_cents INTEGER DEFAULT 0,
    expenses_excl_hst REAL DEFAULT 0.0,
    expenses_excl_hst_cents INTEGER DEFAULT 0,
    hst_paid REAL DEFAULT 0.0,
    hst_paid_cents INTEGER DEFAULT 0,
    collected REAL DEFAULT 0.0,
    collected_cents INTEGER DEFAULT 0,
    write_off REAL DEFAULT 0.0,
    write_off_cents INTEGER DEFAULT 0,
    receivable REAL DEFAULT 0.0,
    receivable_cents INTEGER DEFAULT 0,
    trx_id TEXT,
    external_ref_id TEXT,
    original_amount REAL DEFAULT 0.0,
    work_client TEXT,
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS transaction_categories (
    category_code TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    type TEXT NOT NULL,
    class_scope TEXT DEFAULT 'Both',
    tax_flag_default TEXT DEFAULT 'None',
    billable_allowed INTEGER DEFAULT 0,
    medical_eligible INTEGER DEFAULT 0,
    deductible_eligible INTEGER DEFAULT 0,
    business_deductible_eligible INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    t2125_line_number TEXT DEFAULT '',
    t2125_line_label TEXT DEFAULT '',
    gifi_schedule_125_code TEXT DEFAULT '',
    gifi_schedule_125_label TEXT DEFAULT '',
    deductible_pct REAL DEFAULT 100.0,
    itc_claimable_pct REAL DEFAULT 100.0
);

-- 7. Multi-Biller, Shareholder Loan (GIFI 2781), HST & Tax Compliance Domain
CREATE TABLE IF NOT EXISTS billing_entities (
    biller_code TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL,
    practice_name TEXT NOT NULL,
    ocn TEXT DEFAULT '',
    bin TEXT DEFAULT '',
    hst_number TEXT DEFAULT '',
    effective_from TEXT DEFAULT '',
    effective_to TEXT DEFAULT '',
    default_address_line TEXT NOT NULL,
    alt_address_line TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    payable_to_name TEXT NOT NULL,
    etransfer_email TEXT DEFAULT '',
    bank_account_code TEXT DEFAULT '',
    invoice_number_suffix TEXT DEFAULT '',
    footer_disclosure_text TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shareholder_loan_ledger (
    entry_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    description TEXT NOT NULL,
    vendor_or_counterparty TEXT DEFAULT '',
    source_account TEXT DEFAULT '',
    category_code TEXT DEFAULT '',
    pre_tax_amount REAL DEFAULT 0.0,
    pre_tax_amount_cents INTEGER DEFAULT 0,
    hst_amount REAL DEFAULT 0.0,
    hst_amount_cents INTEGER DEFAULT 0,
    gross_amount REAL DEFAULT 0.0,
    gross_amount_cents INTEGER DEFAULT 0,
    loan_delta REAL DEFAULT 0.0,
    loan_delta_cents INTEGER DEFAULT 0,
    running_balance REAL DEFAULT 0.0,
    running_balance_cents INTEGER DEFAULT 0,
    linked_transaction_id TEXT DEFAULT '',
    linked_ap_bill_id TEXT DEFAULT '',
    receipt_ref TEXT DEFAULT '',
    gifi_code TEXT DEFAULT '2781',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cca_assets (
    asset_id TEXT PRIMARY KEY,
    biller_entity TEXT NOT NULL,
    cca_class TEXT NOT NULL,
    cca_rate_pct REAL NOT NULL,
    description TEXT NOT NULL,
    acquisition_date TEXT NOT NULL,
    original_cost REAL DEFAULT 0.0,
    original_cost_cents INTEGER DEFAULT 0,
    opening_ucc REAL DEFAULT 0.0,
    opening_ucc_cents INTEGER DEFAULT 0,
    additions REAL DEFAULT 0.0,
    additions_cents INTEGER DEFAULT 0,
    dispositions_proceeds REAL DEFAULT 0.0,
    dispositions_proceeds_cents INTEGER DEFAULT 0,
    half_year_rule_applies INTEGER DEFAULT 1,
    immediate_expensing_applies INTEGER DEFAULT 0,
    cca_claimed REAL DEFAULT 0.0,
    cca_claimed_cents INTEGER DEFAULT 0,
    closing_ucc REAL DEFAULT 0.0,
    closing_ucc_cents INTEGER DEFAULT 0,
    rollover_from_asset_id TEXT DEFAULT '',
    tax_year INTEGER NOT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hst_log (
    period_id TEXT PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    filed_date TEXT DEFAULT '',
    conf_num TEXT DEFAULT '',
    net_tax REAL DEFAULT 0.0,
    net_tax_cents INTEGER DEFAULT 0,
    paid_date TEXT DEFAULT '',
    payment_ref TEXT DEFAULT '',
    biller_entity TEXT DEFAULT 'SOLE_PROP',
    line_101_sales REAL DEFAULT 0.0,
    line_101_sales_cents INTEGER DEFAULT 0,
    line_103_hst_collected REAL DEFAULT 0.0,
    line_103_hst_collected_cents INTEGER DEFAULT 0,
    line_104_adjustments REAL DEFAULT 0.0,
    line_104_adjustments_cents INTEGER DEFAULT 0,
    line_105_total_hst REAL DEFAULT 0.0,
    line_105_total_hst_cents INTEGER DEFAULT 0,
    line_106_itcs REAL DEFAULT 0.0,
    line_106_itcs_cents INTEGER DEFAULT 0,
    line_107_itc_adjustments REAL DEFAULT 0.0,
    line_107_itc_adjustments_cents INTEGER DEFAULT 0,
    line_108_total_itcs REAL DEFAULT 0.0,
    line_108_total_itcs_cents INTEGER DEFAULT 0,
    line_110_instalments REAL DEFAULT 0.0,
    line_110_instalments_cents INTEGER DEFAULT 0,
    line_113_balance REAL DEFAULT 0.0,
    line_113_balance_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Draft',
    notes TEXT DEFAULT ''
);

-- 8. Corporate Records Domain
CREATE TABLE IF NOT EXISTS corp_entities (
    entity_id TEXT PRIMARY KEY,
    client_id TEXT DEFAULT '',
    legal_name TEXT NOT NULL,
    jurisdiction TEXT DEFAULT 'Ontario (OBCA)',
    incorporation_date TEXT DEFAULT '',
    incorporation_number TEXT DEFAULT '',
    fiscal_year_end TEXT DEFAULT '',
    status TEXT DEFAULT 'Active',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corp_relationships (
    relationship_id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    share_class TEXT DEFAULT '',
    shares_held REAL DEFAULT 0.0,
    ownership_percentage REAL DEFAULT 0.0,
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS corp_transactions (
    transaction_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    from_entity_id TEXT DEFAULT '',
    to_entity_id TEXT DEFAULT '',
    share_class TEXT DEFAULT '',
    number_of_shares REAL DEFAULT 0.0,
    price_per_share REAL DEFAULT 0.0,
    total_value REAL DEFAULT 0.0,
    total_value_cents INTEGER DEFAULT 0,
    document_reference TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- 9. System & Sync Domain
CREATE TABLE IF NOT EXISTS SyncManifest (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS AuditEvent (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    user_id TEXT,
    details TEXT
);

-- 10. Canonical Snake-Case Compatibility Views (Dual-Schema Parity)
DROP VIEW IF EXISTS clients;
CREATE VIEW clients AS
SELECT
    c.client_id,
    c.name AS client_name,
    COALESCE(NULLIF(p.display_name, ''), NULLIF(c.display_name, ''), c.name) AS display_name,
    COALESCE(NULLIF(p.legal_name, ''), NULLIF(c.legal_name, ''), c.name) AS legal_name,
    COALESCE(NULLIF(p.entity_type, ''), NULLIF(c.entity_type, ''), 'Corporation') AS entity_type,
    COALESCE(NULLIF(c.primary_contact, ''), NULLIF(p.principal_name, '')) AS primary_contact,
    COALESCE(NULLIF(p.full_address, ''), NULLIF(c.address, ''), NULLIF(p.billing_address, '')) AS address,
    COALESCE(NULLIF(p.primary_email, ''), NULLIF(c.email, '')) AS email,
    COALESCE(NULLIF(p.primary_phone, ''), NULLIF(c.phone, '')) AS phone,
    COALESCE(p.default_billing_rate, c.default_billing_rate, 0.0) AS default_billing_rate,
    COALESCE(p.default_billing_rate_cents, c.default_billing_rate_cents, 0) AS default_billing_rate_cents,
    COALESCE(p.hst_exempt, c.hst_exempt, 0) AS hst_exempt,
    COALESCE(NULLIF(p.tax_exemption_reason, ''), NULLIF(c.tax_exemption_reason, '')) AS tax_exemption_reason,
    c.status,
    COALESCE(c.active, 1) AS active,
    COALESCE(NULLIF(p.opening_date, ''), NULLIF(c.opening_date, ''), NULLIF(p.date_client_added, '')) AS opening_date,
    COALESCE(NULLIF(p.kyc_status, ''), NULLIF(c.kyc_status, ''), 'Pending') AS kyc_status,
    COALESCE(NULLIF(p.kyc_verified_date, ''), NULLIF(c.kyc_verified_date, '')) AS kyc_verified_date,
    COALESCE(NULLIF(p.kyc_method, ''), NULLIF(c.kyc_method, '')) AS kyc_method,
    COALESCE(NULLIF(p.kyc_notes, ''), NULLIF(c.kyc_notes, '')) AS kyc_notes,
    COALESCE(NULLIF(p.referred_by, ''), NULLIF(c.referred_by, ''), NULLIF(p.referral_from, '')) AS referred_by,
    COALESCE(NULLIF(p.referral_from, ''), NULLIF(p.referred_by, ''), NULLIF(c.referred_by, '')) AS referral_from,
    COALESCE(NULLIF(p.notes, ''), NULLIF(c.notes, '')) AS notes,
    c.created_at,
    c.updated_at
FROM Client c
LEFT JOIN ClientProfile p ON c.client_id = p.client_id;

DROP VIEW IF EXISTS client_profiles;
CREATE VIEW client_profiles AS SELECT * FROM ClientProfile;

DROP VIEW IF EXISTS matters;
CREATE VIEW matters AS SELECT * FROM Matter;

DROP VIEW IF EXISTS corporate_entities;
CREATE VIEW corporate_entities AS SELECT * FROM corp_entities;

DROP VIEW IF EXISTS corporate_relationships;
CREATE VIEW corporate_relationships AS SELECT * FROM corp_relationships;

DROP VIEW IF EXISTS corporate_transactions;
CREATE VIEW corporate_transactions AS SELECT * FROM corp_transactions;

