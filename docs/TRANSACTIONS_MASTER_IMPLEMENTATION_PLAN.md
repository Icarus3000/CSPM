# Transactions Master Implementation Plan (Draft V1)

## Goal
Implement one adaptive transaction workflow covering:
- personal income/expense
- business income/expense
- debt repayment
- transfers
- client disbursements

## Phase 1: Schema and Constants
1. Add new table constants in `src/python/domain/schema_constants.py`:
   - `tblTransactionsMaster`
   - `tblTransactionAccounts`
   - `tblTransactionCategories`
   - `tblTransactionBusinessUnits`
   - optional `tblTransactionPayees`
2. Add corresponding sheet names and column constants.
3. Extend `TABLE_COLUMNS` and `TABLE_ALIASES`.
4. Update `schema/workbook_schema.yml` using `schema/workbook_schema.transactions_master.patch.yml`.

## Phase 2: Excel Repo (Backend Contract)
1. Extend `TABLES_IN_ORDER` in `src/python/repositories/excel_repo.py`.
2. Add read methods:
   - `list_transaction_accounts()`
   - `list_transaction_categories(txn_type, txn_class)`
   - `list_transaction_payees()`
   - `list_transactions(filters)`
3. Add save/upsert method:
   - `save_transaction(payload)`
4. Add normalization helpers:
   - enum normalization
   - derived field calculation (`TotalClaimAmount`)
   - cross-field validation (status, transfer, debt, billable context)

## Phase 3: App Controller API
1. Add `@Slot(result="QVariantList")` lookup/list slots.
2. Add `@Slot("QVariant", result="QVariantMap")` save slot for transaction payload.
3. Add `dataChanged` signals for transactions and lookups.

## Phase 4: QML Adaptive Form
1. Add a dedicated view component:
   - `src/qml/views/TransactionsMasterView.qml`
2. Build conditional sections driven by `Class` and `Type`.
3. Wire lookups to controller slots.
4. Apply behavior rules from `docs/TRANSACTIONS_MASTER_UI_BEHAVIOR.md`.
5. Remove/ignore `Harvest Dockets` and omit `Sub-Client`.

## Phase 5: QA and Migration
1. Seed lookup tables from:
   - `schema/transactions_master.accounts.seed.csv`
   - `schema/transactions_master.business_units.seed.csv`
   - `schema/transactions_master.categories.seed.csv`
2. Validate end-to-end save/load for all four transaction types.
3. Reconciliation tests for `Pending -> Cleared -> Reconciled -> Void`.
4. Verify billable disbursement paths with `Parent/Client/Matter`.

## Acceptance Checklist
- One master form handles all transaction contexts without duplicate fields.
- Status and date lifecycle rules enforce data integrity.
- Transfer/debt flows enforce `FromAccount != ToAccount`.
- Billable disbursements compute and persist claim amounts correctly.
- Category lookup is filtered by transaction type.
