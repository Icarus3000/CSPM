# CSPM (`__CSPM`) — Architecture, Schema Map & Corporate/Tax Ground Truth

> **Mandatory Post-Change Delivery Gate (Verify -> Recompile `.exe` -> Push to Git Cloud):**
> Whenever any Python (`.py`), QML (`.qml`), schema (`.yml` / `.sql`), or template file is created or modified, Antigravity MUST automatically complete all three steps before finishing the turn—even if the user's prompt does not explicitly ask for a build or push:
> 1. Run `py_compile`, `qmllint`, and targeted verification tests.
> 2. Recompile the local standalone `.exe` so the desktop executable immediately reflects the latest code.
> 3. Commit all source/test/doc changes and run `git push` to synchronize with Git cloud.
>
> *(Automated via `./scripts/build_and_push.py`; see `./.agent/rules/post_change_pipeline.md`.)*

> **PORTABILITY & DUAL-SCHEMA MANDATE:**
> 1. **No Hardcoded Machine Paths:** Always use `PathService` (`./src/python/services/paths.py`), environment variables (`%LOCALAPPDATA%/CSPM`), or repository-relative paths (`./...`). Never hardcode drive letters or workstation usernames.
> 2. **SQLite-First Dual-Schema Parity:** CSPM currently persists live runtime data in structured Excel tables (`CSPM.xlsm` via `openpyxl` with `keep_vba=True`), while an active migration path to **SQLite (`./src/python/prototypes/sqlite_architecture/`)** is maintained in lockstep. Every table or column added to `./schema/workbook_schema.yml`, `./schema/workbook_schema.ap.yml`, or `./src/python/domain/schema_constants.py` **MUST** also be added to:
>    - `./src/python/prototypes/sqlite_architecture/schema.sql` (strict SQLite types, ISO-8601 `YYYY-MM-DD` dates, integer-cent columns, and audit metadata),
>    - `./src/python/prototypes/sqlite_architecture/sqlite_repo.py`, and
>    - `./src/python/prototypes/sqlite_architecture/migration.py`.
> 3. **Zero Storage Leakage in Domain Services/Controllers:** Never place `openpyxl`, worksheet, or raw cell-manipulation logic inside domain services (`./src/python/services/tax_compliance_service.py`, `./src/python/services/invoice_draft_service.py`) or QObject controllers (`./src/python/backend/`). All calculations must operate purely on in-memory Python dicts/dataclasses and `Decimal` values returned by repository interfaces (`ExcelRepo`/`FinanceRepository` and `SQLiteRepository`).

---

## 1. Corporate & Tax Ground Truth (`SOLE_PROP` vs. `PC`)

### 1.1 Dual Billing Entities & Cutover Date (`2026-11-01`)

| Field | `SOLE_PROP` (Pre-Nov 1, 2026 & Legacy WIP/AR) | `PC` (Nov 1, 2026+ Default) |
| :--- | :--- | :--- |
| **Biller Code** | `SOLE_PROP` | `PC` |
| **Legal Name** | `Cory Schneider` | `Cory Schneider Law Professional Corporation` |
| **Practice / Trade Name** | `Cory Schneider Law Office` | `Cory Schneider Law Office` |
| **Ontario Corp. No. (OCN)** | — | `1001781977` (Company Key: `448389332`, Inc. `2026-10-17` under OBCA) |
| **Business Name Reg. (BIN)** | — | `1001782016` (Registered `2026-10-17`) |
| **Fiscal Year-End** | `December 31` | `December 31` |
| **HST Registration No.** | `78621 8222 RT0001` | `PENDING RT0001` *(editable in Settings once CRA assigns 9-digit BN)* |
| **Default Address** | `14 Parsons Court, Thornhill, ON L4K 6Z4` | `7 Saint Thomas Street, Suite 307, Toronto, ON M5S 2B7` |
| **Alternate Address** | `7 Saint Thomas Street, Suite 307, Toronto, ON M5S 2B7` | `14 Parsons Court, Thornhill, ON L4K 6Z4` |
| **Payable To** | `CORY SCHNEIDER` | `Cory Schneider Law Professional Corporation` |
| **E-Transfer Email** | `cory@coryschneiderlaw.ca` | `cory@coryschneiderlaw.ca` |
| **Invoice Number Format** | `YY-NNNN` (e.g., `26-0042`) | `YY-NNNN-PC` (e.g., `26-0043-PC`) — shared sequential counter `NNNN` |
| **Footer Disclosure** | *(empty / optional)* | `Cory Schneider Law Office is a registered business name of Cory Schneider Law Professional Corporation.` |

- **Per-Invoice Address Selector:** Any draft or finalized invoice can use its biller's default address, quick-switch between `14 Parsons Court, Thornhill, ON L4K 6Z4` and `7 Saint Thomas Street, Suite 307, Toronto, ON M5S 2B7`, or specify a custom per-invoice `BillerAddressOverride`.

### 1.2 Share Structure of `Cory Schneider Law Professional Corporation` (Uncertificated, OBCA s. 54(1))
1. **`100 Class 1 Common Shares` (Issued `2026-10-17`):**
   - Holder: `Cory Adam Schneider` (`100%` voting equity)
   - Aggregate Consideration & OBCA Stated Capital / Tax PUC: **`$1.00`** (`$0.01/share`, `GIFI 3500 = $1.00`)
   - Payment Mechanism: Paid in full via **`$1.00` set-off** (`Notice #1 / Doc #10`, OBCA s. 23(3)) against pre-incorporation outlays owed to Cory Adam Schneider.
2. **`100 Class A1 Fixed Value Special Shares (Voting)` (Issued Effective `2026-11-01`):**
   - Holder: `Cory Adam Schneider`
   - Issued pursuant to the **ITA s. 85(1) Joint Election (`Form T2057`)** transferring practice Goodwill from the Sole Proprietorship to the Professional Corporation.
   - Aggregate Fair Market Value & Aggregate Redemption/Retraction Price: **`$100.00`** (`$1.00/share`).
   - Elected Amount (`Form T2057`), OBCA s. 24(3) Stated Capital Addition & Tax PUC: **`$1.00`** (`GIFI 3520 = $1.00`).

### 1.3 Verified October 17, 2026 Opening Shareholder Loan (`GIFI 2781`)
Pre-seeded into `tblShareholderLoanLedger` / `shareholder_loan_ledger` (matching Minute Book Document `10` & Shareholder Loan Register Page 5):

| Entry ID | Date | Entry Type | Vendor / Payee | Reference | Description | Pre-Tax (`$`) | HST ITC (`$`) | Gross (`$`) | Delta (`$`) | Running Balance (`GIFI 2781`) |
| :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `SHL-2026-0001` | `2026-10-17` | `INCORPORATION_PRE_EXPENSE` | `Advanced Consulting & Engineering Inc. (GetNuans.com)` | `Order #GN-MVCNRB7D-802822` | Ontario NUANS corporate name search report | `39.95` | `0.00` | `39.95` | `+39.95` | `39.95` |
| `SHL-2026-0002` | `2026-10-17` | `INCORPORATION_PRE_EXPENSE` | `Ministry of Public and Business Service Delivery (ServiceOntario)` | `Tx #9bccd2c22ddfc3e4` | Statutory Articles of Incorporation filing fee (OCN 1001781977) | `300.00` | `0.00` | `300.00` | `+300.00` | `339.95` |
| `SHL-2026-0003` | `2026-10-17` | `INCORPORATION_PRE_EXPENSE` | `Ministry of Public and Business Service Delivery (ServiceOntario)` | `Tx #9e56c4380e71944a` | Statutory Business Name Registration fee (BIN 1001782016) | `60.00` | `0.00` | `60.00` | `+60.00` | `399.95` |
| `SHL-2026-0004` | `2026-10-17` | `INCORPORATION_PRE_EXPENSE` | `Law Society of Ontario` | `INV-00501458-N9J8W7 (App #534837)` | 2026 Certificate of Authorization application fee | `350.00` | `45.50` | `395.50` | `+395.50` | `795.45` |
| `SHL-2026-0005` | `2026-10-17` | `SHARE_SUBSCRIPTION_SETOFF` | `Cory Schneider Law Professional Corporation (Treasury)` | `Notice #1 / Doc #10` | OBCA s. 23(3) Set-off in full payment of 100 Class 1 Common Shares ($1.00) | `0.00` | `0.00` | `1.00` | `-1.00` | **`794.45`** |

- **Totals as of October 17, 2026:**
  - Pre-Tax Corporate Expense (`T2 Schedule 125`): **`$749.95`**
  - Claimable PC HST Input Tax Credit (`PC RT0001 Line 106/108`): **`$45.50`**
  - Net Tax-Free Shareholder Loan Payable to Cory Adam Schneider (`T2 Schedule 100 GIFI 2781`): **`$794.45`**

### 1.4 November 1, 2026 Section 85 Cutover & Asset Transfer Rules
1. **Goodwill (`Form T2057` Joint Election — Filing Deadline June 15, 2027):**
   - Rolled as a single line item on `Form T2057`:
     - Description: `Goodwill, client relationships, and trade name of Cory Schneider Law Office`
     - Fair Market Value (`FMV`): **`$100.00`**
     - Tax Cost (`ACB` / `UCC` to Transferor): **`$0.00`**
     - Agreed / Elected Amount: **`$1.00`**
     - Non-Share Consideration (`Boot`): **`$0.00`**
     - Share Consideration: **`100 Class A1 Fixed Value Special Shares (Voting)`** (`FMV = $100.00`, `OBCA s. 24(3) Stated Capital / PUC = $1.00`).
     - Transferor (`SOLE_PROP`) reports `$1.00` proceeds on `2026 T1 Schedule 3`.
2. **Depreciable Equipment (`UCC` Transfer Outside `Form T2057`):**
   - Office/computer equipment transferred effective `2026-11-01` at tax cost (`Undepreciated Capital Cost` / `UCC`) outside of `Form T2057`:
     - `SOLE_PROP` (`T2125` Area A CCA): `Proceeds of Disposition = Opening UCC` $\rightarrow$ **`$0.00` recapture** and **`$0.00` terminal loss**.
     - `PC` (`T2 Schedule 8` CCA): Added to the corresponding CCA class pool at the transferred `UCC` amount.
     - Consideration: Credited **dollar-for-dollar (`+UCC`)** to `tblShareholderLoanLedger` (`GIFI 2781`) as an `EQUIPMENT_UCC_ROLLOVER` entry.
3. **Pre-Nov 1, 2026 Billed `AR` and Unbilled `WIP`:**
   - Explicitly excluded from the s. 85 transfer and billed/collected under `SOLE_PROP` (`HST # 78621 8222 RT0001`, reported on `2026 T1 Form T2125`).

---

## 2. Project Architecture & Repository Map

### 2.1 Backend Layer (`./src/python/`)
- **Entrypoint:** `./src/python/main.py` registers 5 QObject controllers into the QML root context:
  - `app` $\rightarrow$ `./src/python/backend/app_controller.py` (`AppController`)
  - `docketApp` $\rightarrow$ `./src/python/backend/controllers/docketing_controller.py` (`DocketingController`)
  - `billingApp` $\rightarrow$ `./src/python/backend/controllers/billing_controller.py` (`BillingController`)
  - `apApp` $\rightarrow$ `./src/python/backend/controllers/ap_controller.py` (`APController`)
  - `corporateApp` $\rightarrow$ `./src/python/backend/controllers/corporate_controller.py` (`CorporateController`)
- **Domain Constants & Schemas:**
  - `./src/python/domain/schema_constants.py` — Sheet, table, and column constants + `EXPECTED_TABLES_BY_SHEET`.
  - `./src/python/domain/ap_schema.py` — Accounts Payable (`tblAPBills`, `tblAPPayments`) schema definitions.
  - `./src/python/domain/tax_rules.py` — CRA deductibility and ITC factor rules (e.g., 50% Meals & Entertainment).
- **Domain Services (`./src/python/services/`):**
  - `./src/python/services/paths.py` — Portable path resolution (`PathService`).
  - `./src/python/services/sync_service.py` — Shared workbook checkout/lock synchronization (`cspm.lock`).
  - `./src/python/services/invoice_draft_service.py` — Draft invoice math, finalization, and void/reissue lifecycle.
  - `./src/python/services/invoice_document_service.py` — Jinja2 HTML & `docxtpl` invoice rendering.
  - `./src/python/services/ap_orchestration_service.py` — AP bill & payment/A/R set-off orchestration.
  - `./src/python/services/tax_compliance_service.py` — Pure, storage-agnostic domain service for Dual HST (`RT0001`), Shareholder Loan (`GIFI 2781`), `2026 T1 Form T2125` / `Schedule 3`, and `T2 Schedules 100, 125, 50, 8` & `Form T2057`.
- **Repositories (`./src/python/repositories/` & `./src/python/prototypes/sqlite_architecture/`):**
  - `./src/python/repositories/excel_db.py` (`ExcelDatabase`) — Self-healing `openpyxl` table persistence against `./schema/workbook_schema*.yml`.
  - `./src/python/repositories/excel_repo.py` (`ExcelRepo`) — Primary repository for clients, matters, dockets, invoices, receivables, and reports.
  - `./src/python/repositories/finance_repo.py` (`FinanceRepository`) — Master transactions, ledger, billing entities, shareholder loan ledger, CCA assets, and HST log persistence.
  - `./src/python/repositories/ap_workbook_repository.py` (`APWorkbookRepository`) — Accounts Payable persistence.
  - `./src/python/prototypes/sqlite_architecture/schema.sql`, `sqlite_repo.py`, `migration.py` — Parallel SQLite 3 / WAL schema, repository, and lossless Excel-to-SQLite migration pipeline.

### 2.2 Schema & Seed Registry (`./schema/`)
- `./schema/workbook_schema.yml` — Primary declarative workbook table contract.
- `./schema/workbook_schema.ap.yml` — Accounts Payable table contract (`tblAPBills`, `tblAPPayments`).
- `./schema/workbook_schema.transactions_master.patch.yml` — Master transaction & lookup tables (`tblTransactionsMaster`, `tblTransactionAccounts`, `tblTransactionCategories`, `tblTransactionBusinessUnits`, `tblTransactionPayees`).
- `./schema/transactions_master.accounts.seed.csv`, `./schema/transactions_master.categories.seed.csv`, `./schema/transactions_master.business_units.seed.csv`, `./schema/transactions_master.enums.json`.

### 2.3 Complete Table Inventory (`CSPM.xlsm` $\leftrightarrow$ SQLite `schema.sql`)

| Domain | Excel Sheet / Table (`CSPM.xlsm`) | SQLite Table (`schema.sql`) | Key Multi-Biller / Tax Columns |
| :--- | :--- | :--- | :--- |
| **Billing Entities** | `Billing_Entities` / `tblBillingEntities` | `billing_entities` | `BillerCode` (`SOLE_PROP` \| `PC`), `LegalName`, `PracticeName`, `OCN`, `BIN`, `HSTNumber`, `DefaultAddressLine`, `AltAddressLine`, `InvoiceNumberSuffix`, `FooterDisclosureText` |
| **Clients & Profiles** | `Clients` / `tblClients`, `ClientProfiles` / `tblClientProfiles`, `Parents` / `tblParents` | `clients` | `ClientID`, `ClientName`, `HSTExempt`, `TaxExemptionReason`, `DefaultBillingRate` |
| **Matters** | `Matters` / `tblMatters`, `MatterParties` / `tblMatterParties` | `matters` | `MatterID`, `MatterNumber`, `ClientID`, `DefaultBillerEntity` (`SOLE_PROP` \| `PC`) |
| **Time & Fees (WIP)** | `Time_Entries` / `tblTimeEntries` | `time_entries` | `EntryID`, `Date`, `FeeCharged`, `HST`, `Total`, `Billed`, `InvoiceRef`, `BillerEntity` |
| **Disbursements** | `Disbursements` / `tblDisbursements` | `disbursements` | `DisbID`, `Date`, `Amount`, `HSTPaid`, `Total`, `Billed`, `InvoiceRef`, `BillerEntity` |
| **Draft Invoices** | `Invoices_Draft` / `tblDraftInvoices` | `invoices_draft` | `DraftID`, `DraftNum`, `TotalFees`, `TotalDisbursements`, `TotalTax`, `GrandTotal`, `BillerEntity`, `BillerAddressOverride`, `BillerHSTOverride` |
| **Finalized Invoices** | `Invoice_Log` / `tblInvoiceLog` | `invoice_log` | `InvoiceID`, `InvoiceNum` (`YY-NNNN` / `YY-NNNN-PC`), `InvoiceDate`, `TotalFees`, `TotalDisbursements`, `TotalTax`, `GrandTotal`, `BillerEntity`, `BillerAddressOverride`, `BillerHSTOverride` |
| **Receivables (A/R)** | `Receivables` / `tblReceivables` | `receivables` | `InvoiceNum`, `InvoiceDate`, `FeesBilled`, `DisbBilled`, `HSTBilled`, `TotalBilled`, `AmountPaid`, `BalanceDue`, `BillerEntity` |
| **General Ledger** | `Ledger` / `tblLedger` | `ledger` | `TransID`, `Date`, `Type`, `Category`, `GrossAmount`, `HSTCollected`, `HSTPaid`, `NetAmount`, `BillerEntity` |
| **Master Transactions** | `Transactions_Master` / `tblTransactionsMaster` | `transactions_master` | `TransactionID`, `EntryDate`, `Class`, `BusinessUnit`, `Type`, `FromAccount`, `ToAccount`, `CategoryCode`, `Amount`, `TaxAmount`, `HSTExempt`, `BillerEntity` |
| **Transaction Categories** | `Transaction_Categories` / `tblTransactionCategories` | `transaction_categories` | `CategoryCode`, `CategoryName`, `T2125LineNumber`, `T2125LineLabel`, `GIFISchedule125Code`, `GIFISchedule125Label`, `DeductiblePct`, `ITCClaimablePct` |
| **Accounts Payable** | `AP_Bills` / `tblAPBills`, `AP_Payments` / `tblAPPayments` | `ap_bills`, `ap_payments` | `APBillID`, `ExpenseClassification`, `SubtotalCAD`, `TaxAmountCAD`, `TotalCAD`, `BillerEntity` |
| **Shareholder Loan (`GIFI 2781`)** | `Shareholder_Loan_Ledger` / `tblShareholderLoanLedger` | `shareholder_loan_ledger` | `SHLEntryID`, `EffectiveDate`, `BillerEntity` (`PC`), `EntryType`, `Direction`, `PreTaxAmount`, `HSTITCAmount`, `GrossAmount`, `SignedDelta`, `RunningBalance`, `GIFILine` (`2781`) |
| **CCA & Equipment Rollover** | `CCA_Assets` / `tblCCAAssets` | `cca_assets` | `AssetID`, `BillerEntity`, `CCAClass`, `OpeningUCC`, `AdditionsAmount`, `ProceedsOfDisposition`, `CCAClaimed`, `ClosingUCC`, `RolloverDate`, `RolloverToEntity`, `ShareholderLoanCredited` |
| **HST Filing Log** | `HST_Log` / `tblHSTLog` | `hst_log` | `PeriodID`, `BillerEntity`, `HSTAccountNumber`, `Line101SalesRevenue`, `Line103HSTCollected`, `Line105TotalHSTAndAdjustments`, `Line106ITCsCurrentPeriod`, `Line108TotalITCsAndAdjustments`, `Line109NetTax`, `Status` |
| **Corporate Cap-Table** | `Corporate_Entities` / `tblCorpEntities`, `tblCorpRelationships`, `tblCorpTransactions` | `corporate_entities`, `corporate_relationships`, `corporate_transactions` | `EntityID`, `LegalName`, `CorpNumber` (`1001781977`), `ShareStructureJSON` |

### 2.4 Invoice Templates & QML Navigation (`./src/templates/invoices/` & `./src/qml/`)
- **Invoice HTML Templates:**
  - `./src/templates/invoices/Concept_A2.html` (Default)
  - `./src/templates/invoices/Standard_Elite.html`
  - `./src/templates/invoices/LIHDC_Format.html`
- **Navigation Registry & Routing:**
  - `./src/qml/standards/ModulePathways.js` — Canonical module/node IDs (`H01`, `A01`–`A23`, `B01`–`B17`, `C01`–`C19`, `D01`–`D21`, `X01`–`X13`).
  - `./src/qml/views/MainContent.qml` — Central view router for Professional and Console shells.
  - `./src/qml/views/InvoiceStudio.qml` — Draft invoice builder with Biller selector (`SOLE_PROP` vs. `PC`) and per-invoice Address selector (`14 Parsons Court` / `7 Saint Thomas Street` / Custom).
  - `./src/qml/views/WIPToBillWorkbenchView.qml` — Unbilled WIP workbench with `BillerEntity` badges and 1-click Pre-Nov 1 (`SOLE_PROP`) vs. Nov 1+ (`PC`) draft splitter.
  - `./src/qml/views/ShareholderLoanLedgerView.qml` (`C19`) — Shareholder Loan (`GIFI 2781`) & Nov 1 Equipment `UCC` Rollover workspace.
  - `./src/qml/views/HSTReturnHelperView.qml` (`D20`) — Dual CRA HST Return (`RT0001`) calculator & filing log (`SOLE_PROP` & `PC`).
  - `./src/qml/views/IncomeTaxHelperView.qml` (`D21`) — Dual Income Tax Filing Helper (`2026 T1 Form T2125` + `Schedule 3` & `T2 Schedules 100, 125, 50, 8` + `Form T2057` + `Billing Entities & Tax Settings`).
