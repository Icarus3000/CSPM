-- PROVISIONAL REPRESENTATIVE PROTOTYPE SCHEMA
-- NOT APPROVED FOR PRODUCTION MIGRATION
-- Production SQLite Schema for CSPM

-- Enforce strict constraints
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

-- 1. Entities Domain
CREATE TABLE IF NOT EXISTS Client (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'Active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_id TEXT
);

CREATE TABLE IF NOT EXISTS ClientProfile (
    client_id TEXT PRIMARY KEY,
    billing_address TEXT,
    tax_number TEXT,
    payment_terms TEXT,
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE CASCADE
);

-- 2. Matters Domain
CREATE TABLE IF NOT EXISTS Matter (
    matter_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'Open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_id TEXT,
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE RESTRICT
);

-- 3. Time & Tasks Domain
CREATE TABLE IF NOT EXISTS TimeEntry (
    time_id TEXT PRIMARY KEY,
    matter_id TEXT NOT NULL,
    date TEXT NOT NULL,
    hours REAL NOT NULL,
    rate REAL NOT NULL,
    amount REAL NOT NULL, -- Statically captured formula value to prevent float drift
    description TEXT,
    is_billed INTEGER DEFAULT 0,
    billed_invoice_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (matter_id) REFERENCES Matter(matter_id) ON DELETE RESTRICT
    -- billed_invoice_id is intentionally unconstrained to allow invoice deletion without cascading time deletion
);

-- 4. Billing Domain
CREATE TABLE IF NOT EXISTS Invoice (
    invoice_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    matter_id TEXT,
    date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    tax_amount REAL DEFAULT 0.0,
    status TEXT DEFAULT 'Draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES Client(client_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Receivable (
    receivable_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount_due REAL NOT NULL,
    amount_paid REAL DEFAULT 0.0,
    status TEXT DEFAULT 'Unpaid',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES Invoice(invoice_id) ON DELETE CASCADE
);

-- 5. Payables Domain
CREATE TABLE IF NOT EXISTS AccountsPayable (
    ap_id TEXT PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'Unpaid',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 6. Ledger Domain
CREATE TABLE IF NOT EXISTS TransactionMaster (
    transaction_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    account TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL, -- e.g., 'Credit', 'Debit'
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 7. System & Sync Domain
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

