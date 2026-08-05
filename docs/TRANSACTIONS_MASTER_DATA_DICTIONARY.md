# Transactions Master Data Dictionary (Draft V1)

## Scope
This is the proposed single-table contract for personal expenses, business expenses, business income, debt repayment, transfers, and client disbursements.

- `Harvest Dockets` is excluded.
- `Sub-Client` is excluded.
- `Parent` is included.
- Fields from both provided forms are merged without duplicate concepts.

## Canonical Table
- Sheet: `Transactions`
- Table: `tblTransactionsMaster`
- Primary key: `TransactionID`

## Column Definitions
| Column | Type | Required | Default | Description |
|---|---|---|---|---|
| `TransactionID` | text | Yes | auto UUID | Stable primary key. |
| `TxnDate` | date | Yes | today | Transaction date. |
| `Class` | enum | Yes | `Family` | `Family`, `Business`. |
| `BusinessUnit` | enum | Conditional | blank | Required when `Class=Business`. |
| `Type` | enum | Yes | `Expense` | `Income`, `Expense`, `Debt Repayment`, `Transfer`. |
| `FromAccount` | enum | Yes | blank | Source account. |
| `ToAccount` | enum | Conditional | blank | Required for `Transfer` and `Debt Repayment`. |
| `Payee` | text | Conditional | blank | Vendor/payee/counterparty. |
| `Parent` | text | Conditional | blank | Parent entity for client-billable flows. |
| `Client` | text | Conditional | blank | Client for disbursements or recoverable expenses. |
| `Matter` | text | Conditional | blank | Matter for disbursements or recoverable expenses. |
| `CategoryCode` | text | Yes | blank | Stable category key from lookup. |
| `CategoryName` | text | Yes | blank | Display category name. |
| `Member` | enum | Yes | `Joint` | `Joint`, `Deborah`, `Cory`, `Alexa`, `Emma`, `Maya`. |
| `Amount` | number(12,2) | Yes | `0.00` | Positive amount before tax. |
| `TaxAmount` | number(12,2) | Yes | `0.00` | HST/tax value in dollars. |
| `TaxFlag` | enum | Yes | `None` | `None`, `HST - Biz`, `Business Deductible`, `Medical`, `Deductible`. |
| `HSTExempt` | bool-int | Yes | `0` | If true, default `TaxAmount` to `0.00`. |
| `GeneralOfficeExpense` | bool-int | Yes | `0` | Marks non-client overhead expense. |
| `Shadow` | bool-int | Yes | `0` | Planned/provisional entry flag. |
| `InvoiceRef` | text | No | blank | Invoice/ref/tracking number. |
| `BillClaimPct` | number(5,2) | Conditional | `0.00` | Percent to bill/claim for disbursements. |
| `TotalClaimAmount` | number(12,2) | Yes | `0.00` | Calculated from amount, tax, and claim percent. |
| `ExpenseDetails` | text | No | blank | Long detail text from disbursement form. |
| `Notes` | text | No | blank | General notes. |
| `Status` | enum | Yes | `Pending` | `Pending`, `Cleared`, `Reconciled`, `Void`. |
| `Currency` | enum | Yes | `CAD` | Currency code. |
| `VoidReason` | text | Conditional | blank | Required when `Status=Void`. |
| `ClearedAt` | date | Conditional | blank | Required when `Status=Cleared` or `Reconciled`. |
| `ReconciledAt` | date | Conditional | blank | Required when `Status=Reconciled`. |
| `CreatedAt` | datetime | Yes | auto now | Audit timestamp. |
| `UpdatedAt` | datetime | Yes | auto now | Audit timestamp. |

## Deduping Decisions (from both forms)
- `Vendor / Payee` and `Payee` are merged into `Payee`.
- `HST ($)` and `Tax ($)` are merged into `TaxAmount`.
- `Invoice / Ref #` is kept as `InvoiceRef`.
- `Expense Details` and `Notes` are both retained as separate fields.
- `Client`, `Matter`, `Parent` are retained.

## Required Lookup Tabs
- `lkpTransactionAccounts`
- `lkpTransactionCategories`
- `lkpPayees` (optional but recommended)
- `lkpBusinessUnits`

## Suggested Save Views
- Personal ledger
- Deborah OT - Private
- Deborah OT - VHA
- Cory business
- Client disbursements (billable)
- Reconciliation queue (`Status in Pending/Cleared`)
